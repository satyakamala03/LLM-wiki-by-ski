"""Vector similarity search via Oracle AI Vector Search."""

from __future__ import annotations

import array

import llm_wiki.env  # noqa: F401

from llm_wiki.db.connection import oracle_connection
from llm_wiki.embeddings.model import embed_query
from llm_wiki.search.types import SearchResult


def _snippet(text: str | None, *, max_len: int = 160) -> str:
    if not text:
        return ""
    cleaned = " ".join(text.split())
    return cleaned[:max_len]


def vector_search(
    project_name: str,
    query: str,
    *,
    top_k: int = 10,
    page_type: str | None = None,
) -> list[SearchResult]:
    query_vector = array.array("f", embed_query(query))
    filters = ["project_name = :project_name", "embedding IS NOT NULL"]
    binds: dict = {"project_name": project_name, "query_vec": query_vector, "top_k": top_k}

    if page_type:
        filters.append("page_type = :page_type")
        binds["page_type"] = page_type

    where_clause = " AND ".join(filters)
    sql = f"""
        SELECT page_path, title, page_type, embed_text,
               VECTOR_DISTANCE(embedding, :query_vec, COSINE) AS distance
        FROM wiki_pages
        WHERE {where_clause}
        ORDER BY distance
        FETCH FIRST :top_k ROWS ONLY
    """

    results: list[SearchResult] = []
    with oracle_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, binds)
            for page_path, title, ptype, embed_text, distance in cursor:
                # Cosine distance: lower is better; convert to similarity-ish score
                dist = float(distance) if distance is not None else 1.0
                score = max(0.0, 1.0 - dist)
                results.append(
                    SearchResult(
                        page_path=str(page_path),
                        title=str(title or ""),
                        page_type=str(ptype or ""),
                        snippet=_snippet(str(embed_text) if embed_text else ""),
                        vector_score=score,
                    )
                )
    return results
