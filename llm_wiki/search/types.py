from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchResult:
    page_path: str
    title: str
    page_type: str
    snippet: str
    vector_score: float | None = None
    fts_score: float | None = None
    rrf_score: float = 0.0
