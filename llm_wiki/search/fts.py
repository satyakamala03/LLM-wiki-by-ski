"""Oracle Text full-text search."""

from __future__ import annotations

from llm_wiki.db.connection import oracle_connection
from llm_wiki.search.types import SearchResult


def _snippet(text: str | None, *, max_len: int = 160) -> str:
    if not text:
        return ""
    cleaned = " ".join(text.split())
    return cleaned[:max_len]


def _oracle_text_query(query: str) -> str:
    """Escape simple terms for CONTAINS; wrap multi-word queries in phrase braces."""
    cleaned = query.strip()
    if not cleaned:
        return ""
    if " " in cleaned:
        escaped = cleaned.replace("{", "").replace("}", "")
        return "{" + escaped + "}"
    return cleaned.replace("{", "").replace("}", "")


def fts_search(
    project_name: str,
    query: str,
    *,
    top_k: int = 10,
    page_type: str | None = None,
) -> list[SearchResult]:
    text_query = _oracle_text_query(query)
    if not text_query:
        return []

    filters = ["project_name = :project_name"]
    binds: dict = {
        "project_name": project_name,
        "text_query": text_query,
        "top_k": top_k,
    }

    if page_type:
        filters.append("page_type = :page_type")
        binds["page_type"] = page_type

    where_clause = " AND ".join(filters)
    sql = f"""
        SELECT page_path, title, page_type, search_text, SCORE(1) AS relevance
        FROM wiki_pages
        WHERE {where_clause}
          AND CONTAINS(search_text, :text_query, 1) > 0
        ORDER BY relevance DESC
        FETCH FIRST :top_k ROWS ONLY
    """

    results: list[SearchResult] = []
    with oracle_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, binds)
            for page_path, title, ptype, search_text, relevance in cursor:
                results.append(
                    SearchResult(
                        page_path=str(page_path),
                        title=str(title or ""),
                        page_type=str(ptype or ""),
                        snippet=_snippet(str(search_text) if search_text else ""),
                        fts_score=float(relevance) if relevance is not None else 0.0,
                    )
                )
    return results
