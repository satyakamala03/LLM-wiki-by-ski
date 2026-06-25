"""LangGraph node functions for source ingestion."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from llm_wiki.embeddings.sync import sync_page_paths
from llm_wiki.index_log import (
    LOG_EVENT_EMBED_SYNC,
    LOG_EVENT_INGEST,
    LOG_EVENT_INGEST_FAILED,
    append_log_entry,
    enrich_meta_with_index_summary,
    rebuild_index,
)
from llm_wiki.ingestion.llm import invoke_llm, load_prompt, parse_json_response
from llm_wiki.ingestion.source import load_schema, prepare_source, read_source_text
from llm_wiki.ingestion.state import (
    IngestionState,
    append_error,
    track_page,
)
from llm_wiki.wiki.contradictions import append_contradiction
from llm_wiki.wiki.frontmatter import (
    new_frontmatter,
    parse_page,
    touch_updated,
    write_page,
)
from llm_wiki.wiki.wiki_manager import title_to_slug


def _wiki_root(state: IngestionState) -> Path:
    return Path(state["wiki_root"])


def _source_filename(state: IngestionState) -> str:
    return state.get("source_filename") or Path(state.get("source_path", "")).name


def _merge_sources(existing: list[str], source_filename: str) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for item in [*existing, source_filename]:
        if item and item not in seen:
            seen.add(item)
            merged.append(item)
    return merged


def find_page(
    wiki_root: Path,
    title: str,
    *,
    page_type: str | None = None,
    directory: str | None = None,
) -> Path | None:
    directories = [directory] if directory else ["summaries", "entities", "topics"]
    normalized = title.strip().lower()

    for subdir in directories:
        folder = wiki_root / subdir
        if not folder.is_dir():
            continue
        for page_path in folder.glob("*.md"):
            try:
                meta, _ = parse_page(page_path)
            except Exception:
                continue
            page_title = str(meta.get("title", "")).strip().lower()
            if page_title == normalized and (page_type is None or meta.get("type") == page_type):
                return page_path

    slug = title_to_slug(title)
    if not slug:
        return None
    for subdir in directories:
        candidate = wiki_root / subdir / f"{slug}.md"
        if candidate.is_file():
            try:
                meta, _ = parse_page(candidate)
            except Exception:
                return candidate
            if page_type is None or meta.get("type") == page_type:
                return candidate
    return None


def _write_page_with_summary(page_path: Path, meta: dict, body: str) -> None:
    meta = enrich_meta_with_index_summary(meta, body)
    write_page(page_path, meta, body)


def read_source(state: IngestionState) -> dict[str, Any]:
    wiki_root = _wiki_root(state)
    try:
        raw_path = prepare_source(wiki_root, state["source_input_path"])
        schema_text = load_schema(wiki_root)
        source_text = read_source_text(raw_path)
    except Exception as exc:
        return {**append_error(state, f"read_source failed: {exc}")}

    return {
        "source_path": str(raw_path),
        "source_filename": raw_path.name,
        "source_text": source_text,
        "schema_text": schema_text,
    }


def extract_info(state: IngestionState) -> dict[str, Any]:
    if state.get("errors"):
        return {}
    try:
        template = load_prompt("ingest_extract.md")
        prompt = template.format(
            schema_text=state.get("schema_text", ""),
            source_filename=_source_filename(state),
            source_text=state.get("source_text", ""),
        )
        raw = invoke_llm(prompt, temperature=0)
        extraction = parse_json_response(raw)
        source_title = str(extraction.get("source_title") or Path(_source_filename(state)).stem)
        return {"extraction": extraction, "source_title": source_title}
    except Exception as exc:
        return append_error(state, f"extract_info failed: {exc}")


def write_summary_page(state: IngestionState) -> dict[str, Any]:
    if state.get("errors") or "extraction" not in state:
        return {}

    wiki_root = _wiki_root(state)
    extraction = state["extraction"]
    source_filename = _source_filename(state)
    slug = Path(source_filename).stem
    summary_path = wiki_root / "summaries" / f"{slug}.md"

    try:
        template = load_prompt("ingest_summary.md")
        prompt = template.format(
            schema_text=state.get("schema_text", ""),
            source_filename=source_filename,
            source_title=state.get("source_title", slug),
            source_text=state.get("source_text", ""),
            entities=[item.get("name") for item in extraction.get("entities", [])],
            concepts=[item.get("name") for item in extraction.get("concepts", [])],
        )
        body = invoke_llm(prompt, temperature=0.2)
        title = f"Summary: {state.get('source_title', slug)}"
        meta = new_frontmatter(
            title,
            "summary",
            tags=["summary", "ingested"],
            sources=[source_filename],
        )
        _write_page_with_summary(summary_path, meta, body)
        return {
            "summary_path": str(summary_path.relative_to(wiki_root)),
            **track_page(state, str(summary_path.relative_to(wiki_root))),
        }
    except Exception as exc:
        return append_error(state, f"write_summary_page failed: {exc}")


def _write_typed_pages(
    state: IngestionState,
    items: list[dict[str, Any]],
    *,
    page_type: str,
    directory: str,
    prompt_name: str,
) -> dict[str, Any]:
    if not items:
        return {}

    wiki_root = _wiki_root(state)
    source_filename = _source_filename(state)
    updates: dict[str, Any] = {}
    pages_written = list(state.get("pages_written", []))

    for item in items:
        title = str(item.get("name", "")).strip()
        if not title:
            continue

        page_path = find_page(wiki_root, title, page_type=page_type, directory=directory)
        if page_path is None:
            page_path = wiki_root / directory / f"{title_to_slug(title)}.md"

        existing_body = ""
        meta = new_frontmatter(
            title,
            page_type,
            tags=list(item.get("tags") or []),
            sources=[source_filename],
        )

        if page_path.is_file():
            existing_meta, existing_body = parse_page(page_path)
            meta = touch_updated(existing_meta)
            meta["title"] = existing_meta.get("title", title)
            meta["type"] = page_type
            meta["tags"] = sorted(set([*(meta.get("tags") or []), *(item.get("tags") or [])]))
            meta["sources"] = _merge_sources(list(existing_meta.get("sources") or []), source_filename)
            if "created" in existing_meta:
                meta["created"] = existing_meta["created"]

        template = load_prompt(prompt_name)
        prompt = template.format(
            schema_text=state.get("schema_text", ""),
            title=title,
            source_filename=source_filename,
            new_info=item.get("description", ""),
            existing_body=existing_body or "(none)",
        )
        body = invoke_llm(prompt, temperature=0.2)
        _write_page_with_summary(page_path, meta, body)

        rel = str(page_path.relative_to(wiki_root))
        if rel not in pages_written:
            pages_written.append(rel)

    return {"pages_written": pages_written}


def update_entity_pages(state: IngestionState) -> dict[str, Any]:
    if state.get("errors") or "extraction" not in state:
        return {}
    try:
        entities = state["extraction"].get("entities", [])
        return _write_typed_pages(
            state,
            entities,
            page_type="entity",
            directory="entities",
            prompt_name="ingest_entity.md",
        )
    except Exception as exc:
        return append_error(state, f"update_entity_pages failed: {exc}")


def update_concept_pages(state: IngestionState) -> dict[str, Any]:
    if state.get("errors") or "extraction" not in state:
        return {}
    try:
        concepts = state["extraction"].get("concepts", [])
        return _write_typed_pages(
            state,
            concepts,
            page_type="concept",
            directory="topics",
            prompt_name="ingest_concept.md",
        )
    except Exception as exc:
        return append_error(state, f"update_concept_pages failed: {exc}")


def update_topic_pages(state: IngestionState) -> dict[str, Any]:
    if state.get("errors") or "extraction" not in state:
        return {}
    try:
        overviews = state["extraction"].get("overviews", [])
        return _write_typed_pages(
            state,
            overviews,
            page_type="overview",
            directory="topics",
            prompt_name="ingest_topic.md",
        )
    except Exception as exc:
        return append_error(state, f"update_topic_pages failed: {exc}")


def detect_contradictions(state: IngestionState) -> dict[str, Any]:
    if state.get("errors") or "extraction" not in state:
        return {}

    wiki_root = _wiki_root(state)
    source_filename = _source_filename(state)
    claims = state["extraction"].get("key_claims", [])
    contradictions = list(state.get("contradictions", []))

    candidate_pages = list(state.get("pages_written", []))
    if not candidate_pages:
        return {"contradictions": contradictions}

    checked: set[str] = set()
    template = load_prompt("ingest_contradiction.md")

    for claim in claims[:8]:
        claim_text = str(claim).strip()
        if not claim_text:
            continue
        for rel_path in candidate_pages:
            if rel_path.startswith("summaries/"):
                continue
            if rel_path in checked:
                continue
            page_path = wiki_root / rel_path
            if not page_path.is_file():
                continue
            try:
                meta, body = parse_page(page_path)
                prompt = template.format(
                    page_title=meta.get("title", page_path.stem),
                    existing_body=body,
                    source_filename=source_filename,
                    claim=claim_text,
                )
                result = parse_json_response(invoke_llm(prompt, temperature=0))
                if result.get("has_contradiction"):
                    note = str(result.get("note", "")).strip()
                    if note:
                        updated_body = append_contradiction(body, note, source_filename)
                        _write_page_with_summary(page_path, touch_updated(meta), updated_body)
                        contradictions.append(
                            {
                                "page": rel_path,
                                "claim": claim_text,
                                "note": note,
                            }
                        )
                checked.add(rel_path)
            except Exception:
                continue

    return {"contradictions": contradictions}


def flag_gaps(state: IngestionState) -> dict[str, Any]:
    if state.get("errors") or "extraction" not in state:
        return {}

    wiki_root = _wiki_root(state)
    extraction = state["extraction"]
    source_filename = _source_filename(state)
    gaps_flagged = list(state.get("gaps_flagged", []))
    pages_written = list(state.get("pages_written", []))

    mentioned = extraction.get("mentioned_without_pages", [])
    template = load_prompt("ingest_gap_stub.md")

    for name in mentioned:
        title = str(name).strip()
        if not title:
            continue
        if find_page(wiki_root, title) is not None:
            continue

        kind = "entity"
        page_path = wiki_root / "entities" / f"{title_to_slug(title)}.md"
        try:
            prompt = template.format(
                schema_text=state.get("schema_text", ""),
                title=title,
                kind=kind,
                source_filename=source_filename,
                context=title,
            )
            body = invoke_llm(prompt, temperature=0.2)
            meta = new_frontmatter(
                title,
                "entity",
                tags=["stub", "gap"],
                sources=[source_filename],
            )
            _write_page_with_summary(page_path, meta, body)
            rel = str(page_path.relative_to(wiki_root))
            gaps_flagged.append(rel)
            if rel not in pages_written:
                pages_written.append(rel)
        except Exception:
            continue

    return {"gaps_flagged": gaps_flagged, "pages_written": pages_written}


def sync_embeddings(state: IngestionState) -> dict[str, Any]:
    """Sync Oracle embeddings for pages touched this run (non-fatal on failure)."""
    if state.get("errors"):
        return {}

    wiki_root = _wiki_root(state)
    project_name = wiki_root.name
    page_paths = list(state.get("pages_written") or [])
    if not page_paths:
        return {"embed_embedded": 0, "embed_skipped": 0, "embed_warnings": []}

    try:
        stats = sync_page_paths(project_name, wiki_root, page_paths)
        if stats.embedded or stats.skipped:
            append_log_entry(
                wiki_root,
                LOG_EVENT_EMBED_SYNC,
                f"{stats.embedded} embedded, {stats.skipped} skipped",
            )
        return {
            "embed_embedded": stats.embedded,
            "embed_skipped": stats.skipped,
            "embed_warnings": stats.errors or [],
        }
    except Exception as exc:
        return {
            "embed_embedded": 0,
            "embed_skipped": 0,
            "embed_warnings": [f"sync_embeddings failed: {exc}"],
        }


def update_index(state: IngestionState) -> dict[str, Any]:
    wiki_root = _wiki_root(state)
    rebuild_index(wiki_root)
    return {}


def append_log(state: IngestionState) -> dict[str, Any]:
    wiki_root = _wiki_root(state)
    title = state.get("source_title") or _source_filename(state)
    errors = state.get("errors") or []

    if errors:
        detail = "; ".join(str(error) for error in errors[:3])
        if len(errors) > 3:
            detail += f" (+{len(errors) - 3} more)"
        append_log_entry(wiki_root, LOG_EVENT_INGEST_FAILED, f"{title} — {detail}")
    else:
        pages = len(state.get("pages_written") or [])
        append_log_entry(wiki_root, LOG_EVENT_INGEST, f"{title} ({pages} pages)")
    return {}
