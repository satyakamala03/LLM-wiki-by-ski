"""Read index and log for query/session bootstrap (Phase 5 prep)."""

from __future__ import annotations

from pathlib import Path

from llm_wiki.index_log.log_writer import list_log_entries
from llm_wiki.wiki.frontmatter import parse_page
from llm_wiki.wiki.wiki_manager import iter_content_pages


def read_index(wiki_root: Path | str) -> str:
    index_path = Path(wiki_root).resolve() / "index.md"
    if not index_path.is_file():
        return ""
    return index_path.read_text(encoding="utf-8")


def read_log(wiki_root: Path | str) -> str:
    log_path = Path(wiki_root).resolve() / "log.md"
    if not log_path.is_file():
        return ""
    return log_path.read_text(encoding="utf-8")


def read_log_tail(wiki_root: Path | str, n: int = 5) -> str:
    entries = list_log_entries(wiki_root)
    if not entries:
        return ""
    tail = entries[-n:]
    lines = [
        format_log_entry_line(date, event_type, description)
        for date, event_type, description in tail
    ]
    return "\n".join(lines) + "\n"


def format_log_entry_line(timestamp: str, event_type: str, description: str) -> str:
    return f"## [{timestamp}] {event_type} | {description}"


def get_index_stats(wiki_root: Path | str) -> dict[str, int]:
    wiki_root = Path(wiki_root).resolve()
    stats: dict[str, int] = {
        "summary": 0,
        "entity": 0,
        "concept": 0,
        "overview": 0,
        "total": 0,
    }
    for page_path in iter_content_pages(wiki_root):
        try:
            meta, _ = parse_page(page_path)
        except Exception:
            continue
        page_type = str(meta.get("type", "entity"))
        if page_type not in stats:
            page_type = "entity"
        stats[page_type] += 1
        stats["total"] += 1
    return stats


def load_wiki_context(wiki_root: Path | str, *, log_tail: int = 5) -> dict[str, str | dict[str, int]]:
    """Bundle index + recent log + counts for session/query bootstrap."""
    return {
        "index": read_index(wiki_root),
        "recent_log": read_log_tail(wiki_root, log_tail),
        "stats": get_index_stats(wiki_root),
    }
