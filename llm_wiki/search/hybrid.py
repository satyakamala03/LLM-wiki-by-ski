"""Hybrid search: reciprocal rank fusion of vector + full-text results."""

from __future__ import annotations

from llm_wiki.search.fts import fts_search
from llm_wiki.search.types import SearchResult
from llm_wiki.search.vector import vector_search

RRF_K = 60


def _rrf_score(rank: int, *, k: int = RRF_K) -> float:
    return 1.0 / (k + rank)


def rrf_merge(
    vector_results: list[SearchResult],
    fts_results: list[SearchResult],
    *,
    k: int = RRF_K,
) -> list[SearchResult]:
    merged: dict[str, SearchResult] = {}
    scores: dict[str, float] = {}

    for rank, item in enumerate(vector_results, start=1):
        scores[item.page_path] = scores.get(item.page_path, 0.0) + _rrf_score(rank, k=k)
        merged[item.page_path] = item

    for rank, item in enumerate(fts_results, start=1):
        scores[item.page_path] = scores.get(item.page_path, 0.0) + _rrf_score(rank, k=k)
        existing = merged.get(item.page_path)
        if existing:
            merged[item.page_path] = SearchResult(
                page_path=existing.page_path,
                title=existing.title or item.title,
                page_type=existing.page_type or item.page_type,
                snippet=existing.snippet or item.snippet,
                vector_score=existing.vector_score,
                fts_score=item.fts_score,
            )
        else:
            merged[item.page_path] = item

    ordered = sorted(scores.items(), key=lambda pair: pair[1], reverse=True)
    output: list[SearchResult] = []
    for page_path, rrf in ordered:
        base = merged[page_path]
        output.append(
            SearchResult(
                page_path=base.page_path,
                title=base.title,
                page_type=base.page_type,
                snippet=base.snippet,
                vector_score=base.vector_score,
                fts_score=base.fts_score,
                rrf_score=rrf,
            )
        )
    return output


def hybrid_search(
    project_name: str,
    query: str,
    *,
    top_k: int = 10,
    page_type: str | None = None,
    candidate_k: int = 20,
) -> list[SearchResult]:
    vector_results = vector_search(
        project_name, query, top_k=candidate_k, page_type=page_type
    )
    fts_results = fts_search(project_name, query, top_k=candidate_k, page_type=page_type)
    merged = rrf_merge(vector_results, fts_results)
    return merged[:top_k]
