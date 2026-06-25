"""Append-only wiki log maintenance."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

LOG_HEADER = "# Wiki Log\n"
LOG_ENTRY_PATTERN = re.compile(
    r"^## \[(\d{4}-\d{2}-\d{2}(?: \d{2}:\d{2}:\d{2})?)\] ([^|]+) \| (.+)$"
)

LOG_EVENT_INGEST = "ingest"
LOG_EVENT_INGEST_FAILED = "ingest-failed"
LOG_EVENT_INDEX_REBUILD = "index-rebuild"
LOG_EVENT_EMBED_SYNC = "embed-sync"
LOG_EVENT_QUERY = "query"
LOG_EVENT_LINT = "lint"
LOG_EVENT_SCHEMA_CHANGE = "schema-change"


def _ensure_log_file(log_path: Path) -> None:
    if not log_path.is_file():
        log_path.write_text(LOG_HEADER, encoding="utf-8")


def now_timestamp_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def format_log_entry(event_type: str, description: str, *, when: str | None = None) -> str:
    timestamp = when or now_timestamp_str()
    return f"## [{timestamp}] {event_type} | {description}"


def append_log_entry(
    wiki_root: Path | str,
    event_type: str,
    description: str,
    *,
    when: str | None = None,
) -> Path:
    """Append one log entry. Skips exact duplicate of the last entry line."""
    wiki_root = Path(wiki_root).resolve()
    log_path = wiki_root / "log.md"
    _ensure_log_file(log_path)

    entry = format_log_entry(event_type, description, when=when)
    existing = log_path.read_text(encoding="utf-8")
    if entry in existing:
        return log_path

    log_path.write_text(existing.rstrip() + f"\n\n{entry}\n", encoding="utf-8")
    return log_path


def list_log_entries(wiki_root: Path | str) -> list[tuple[str, str, str]]:
    """Return parsed log entries as (timestamp, event_type, description)."""
    log_path = Path(wiki_root).resolve() / "log.md"
    if not log_path.is_file():
        return []

    entries: list[tuple[str, str, str]] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        match = LOG_ENTRY_PATTERN.match(line.strip())
        if match:
            entries.append((match.group(1), match.group(2).strip(), match.group(3).strip()))
    return entries
