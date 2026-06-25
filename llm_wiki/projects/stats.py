"""Compute wiki project statistics from disk and logs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from llm_wiki.embeddings.sync import count_project_pages
from llm_wiki.index_log.log_writer import LOG_EVENT_INGEST, LOG_EVENT_QUERY, list_log_entries
from llm_wiki.wiki.wiki_manager import iter_content_pages


@dataclass(frozen=True)
class ProjectStats:
    page_count: int
    source_count: int
    embedding_count: int
    last_ingestion: datetime | None
    last_query: datetime | None


def parse_log_timestamp(timestamp: str) -> datetime | None:
    cleaned = timestamp.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    return None


def last_log_event_time(wiki_root: Path | str, event_type: str) -> datetime | None:
    entries = list_log_entries(wiki_root)
    for timestamp, etype, _description in reversed(entries):
        if etype.strip().lower() == event_type.lower():
            return parse_log_timestamp(timestamp)
    return None


def collect_disk_stats(project_name: str, wiki_root: Path | str) -> ProjectStats:
    wiki_root = Path(wiki_root).resolve()
    page_count = len(iter_content_pages(wiki_root))

    raw_dir = wiki_root / "raw"
    source_count = len(list(raw_dir.glob("*"))) if raw_dir.is_dir() else 0

    try:
        embedding_count = count_project_pages(project_name)
    except Exception:
        embedding_count = 0

    return ProjectStats(
        page_count=page_count,
        source_count=source_count,
        embedding_count=embedding_count,
        last_ingestion=last_log_event_time(wiki_root, LOG_EVENT_INGEST),
        last_query=last_log_event_time(wiki_root, LOG_EVENT_QUERY),
    )
