"""Rebuild wiki index.md from page frontmatter."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from llm_wiki.index_log.oneliner import INDEX_SUMMARY_FIELD, heuristic_oneliner
from llm_wiki.wiki.frontmatter import parse_page
from llm_wiki.wiki.wiki_manager import iter_content_pages

INDEX_SECTIONS: tuple[tuple[str, str], ...] = (
    ("summary", "Sources"),
    ("entity", "Entities"),
    ("concept", "Concepts"),
    ("overview", "Overviews"),
)


@dataclass
class IndexEntry:
    title: str
    one_liner: str
    rel_path: Path
    created: str
    source_count: int


def _one_liner_from_page(meta: dict, body: str) -> str:
    stored = meta.get(INDEX_SUMMARY_FIELD)
    if isinstance(stored, str) and stored.strip():
        return stored.strip()
    return heuristic_oneliner(body)


def _collect_entries(wiki_root: Path) -> dict[str, list[IndexEntry]]:
    grouped: dict[str, list[IndexEntry]] = {key: [] for key, _ in INDEX_SECTIONS}

    for page_path in iter_content_pages(wiki_root):
        try:
            meta, body = parse_page(page_path)
        except Exception:
            continue

        page_type = str(meta.get("type", "entity"))
        if page_type not in grouped:
            page_type = "entity"

        sources = meta.get("sources") or []
        source_count = len(sources) if isinstance(sources, list) else 0
        created = str(meta.get("created", "")).strip()

        grouped[page_type].append(
            IndexEntry(
                title=str(meta.get("title", page_path.stem)),
                one_liner=_one_liner_from_page(meta, body),
                rel_path=page_path.relative_to(wiki_root),
                created=created,
                source_count=source_count,
            )
        )

    return grouped


def _format_entry(entry: IndexEntry) -> str:
    meta_bits: list[str] = [f"`{entry.rel_path}`"]
    if entry.created:
        meta_bits.append(f"created {entry.created}")
    if entry.source_count:
        meta_bits.append(f"{entry.source_count} source{'s' if entry.source_count != 1 else ''}")

    meta_suffix = ", ".join(meta_bits)
    one_liner = f" — {entry.one_liner}" if entry.one_liner else ""
    return f"- [[{entry.title}]]{one_liner} ({meta_suffix})"


def rebuild_index(wiki_root: Path | str) -> Path:
    """Rewrite index.md from all wiki pages. Removes stale entries automatically."""
    wiki_root = Path(wiki_root).resolve()
    grouped = _collect_entries(wiki_root)

    lines = ["# Wiki Index", ""]
    for page_type, heading in INDEX_SECTIONS:
        lines.append(f"## {heading}")
        lines.append("")
        entries = sorted(grouped[page_type], key=lambda item: item.title.lower())
        if not entries:
            lines.append("- _(none yet)_")
        else:
            lines.extend(_format_entry(entry) for entry in entries)
        lines.append("")

    index_path = wiki_root / "index.md"
    index_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return index_path
