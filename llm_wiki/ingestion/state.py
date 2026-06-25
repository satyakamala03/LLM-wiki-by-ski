"""Shared state for the ingestion LangGraph workflow."""

from __future__ import annotations

from typing import Any, TypedDict


class ExtractionEntity(TypedDict, total=False):
    name: str
    description: str
    tags: list[str]


class ExtractionConcept(TypedDict, total=False):
    name: str
    description: str
    tags: list[str]


class ExtractionOverview(TypedDict, total=False):
    name: str
    description: str
    tags: list[str]


class ExtractionResult(TypedDict, total=False):
    source_title: str
    entities: list[ExtractionEntity]
    concepts: list[ExtractionConcept]
    overviews: list[ExtractionOverview]
    key_claims: list[str]
    mentioned_without_pages: list[str]


class ContradictionRecord(TypedDict, total=False):
    page: str
    claim: str
    note: str


class IngestionState(TypedDict, total=False):
    wiki_root: str
    source_input_path: str
    source_path: str
    source_filename: str
    source_title: str
    source_text: str
    schema_text: str
    extraction: ExtractionResult
    summary_path: str
    pages_written: list[str]
    contradictions: list[ContradictionRecord]
    gaps_flagged: list[str]
    embed_embedded: int
    embed_skipped: int
    embed_warnings: list[str]
    errors: list[str]


def init_ingestion_state(wiki_root: str, source_input_path: str) -> IngestionState:
    return {
        "wiki_root": wiki_root,
        "source_input_path": source_input_path,
        "pages_written": [],
        "contradictions": [],
        "gaps_flagged": [],
        "embed_embedded": 0,
        "embed_skipped": 0,
        "embed_warnings": [],
        "errors": [],
    }


def append_error(state: IngestionState, message: str) -> dict[str, list[str]]:
    errors = list(state.get("errors", []))
    errors.append(message)
    return {"errors": errors}


def track_page(state: IngestionState, relative_path: str) -> dict[str, list[str]]:
    pages = list(state.get("pages_written", []))
    if relative_path not in pages:
        pages.append(relative_path)
    return {"pages_written": pages}
