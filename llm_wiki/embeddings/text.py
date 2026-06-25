"""Build embed/search text and content hashes from wiki pages."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from llm_wiki.index_log.oneliner import INDEX_SUMMARY_FIELD, heuristic_oneliner
from llm_wiki.wiki.frontmatter import parse_page


@dataclass(frozen=True)
class PageRecord:
    project_name: str
    page_path: str
    title: str
    page_type: str
    tags: str
    embed_text: str
    search_text: str
    content_hash: str
    updated_at: datetime | None = None


def compute_content_hash(embed_text: str) -> str:
    normalized = embed_text.strip().replace("\r\n", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _summary_from_meta(meta: dict[str, Any], body: str) -> str:
    stored = meta.get(INDEX_SUMMARY_FIELD)
    if isinstance(stored, str) and stored.strip():
        return stored.strip()
    return heuristic_oneliner(body)


def _tags_string(meta: dict[str, Any]) -> str:
    tags = meta.get("tags") or []
    if not isinstance(tags, list):
        return ""
    return ", ".join(str(tag).strip() for tag in tags if str(tag).strip())


def _parse_updated(meta: dict[str, Any]) -> datetime | None:
    updated = meta.get("updated")
    if not isinstance(updated, str) or not updated.strip():
        return None
    try:
        return datetime.fromisoformat(updated.strip())
    except ValueError:
        return None


def build_page_texts(meta: dict[str, Any], body: str) -> tuple[str, str]:
    title = str(meta.get("title", "")).strip() or "Untitled"
    summary = _summary_from_meta(meta, body)
    body_clean = body.strip()

    embed_text = f"{title}\n\n{summary}".strip()
    search_text = f"{title}\n\n{summary}\n\n{body_clean}".strip()
    return embed_text, search_text


def page_to_record(project_name: str, wiki_root: Path, page_path: Path) -> PageRecord:
    meta, body = parse_page(page_path)
    embed_text, search_text = build_page_texts(meta, body)
    rel_path = page_path.relative_to(wiki_root).as_posix()

    return PageRecord(
        project_name=project_name,
        page_path=rel_path,
        title=str(meta.get("title", page_path.stem)),
        page_type=str(meta.get("type", "entity")),
        tags=_tags_string(meta),
        embed_text=embed_text,
        search_text=search_text,
        content_hash=compute_content_hash(embed_text),
        updated_at=_parse_updated(meta),
    )
