"""Shared state for the query LangGraph workflow."""

from __future__ import annotations

from pathlib import Path

from typing import Any, TypedDict


class ChatMessage(TypedDict):
    role: str
    content: str


class PageContent(TypedDict, total=False):
    page_path: str
    title: str
    page_type: str
    body: str
    rrf_score: float


class SearchHit(TypedDict, total=False):
    page_path: str
    title: str
    page_type: str
    snippet: str
    rrf_score: float


class QueryState(TypedDict, total=False):
    wiki_root: str
    project_name: str
    question: str
    schema_text: str
    schema_excerpt: str
    index_text: str
    recent_log: str
    stats: dict[str, int]
    search_results: list[SearchHit]
    pages: list[PageContent]
    answer: str
    coverage: str
    pages_used: list[str]
    suggested_title: str
    messages: list[ChatMessage]
    top_k: int
    saved_page_path: str
    errors: list[str]


def init_query_state(
    wiki_root: str,
    question: str,
    *,
    messages: list[ChatMessage] | None = None,
    top_k: int = 8,
) -> QueryState:
    wiki_path = str(Path(wiki_root).resolve())
    project_name = Path(wiki_root).resolve().name
    return {
        "wiki_root": wiki_path,
        "project_name": project_name,
        "question": question.strip(),
        "messages": list(messages or []),
        "top_k": top_k,
        "search_results": [],
        "pages": [],
        "pages_used": [],
        "errors": [],
    }
