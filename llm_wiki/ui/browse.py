"""Wiki page tree for the Streamlit sidebar (Phase 8.2)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from llm_wiki.wiki.frontmatter import PAGE_TYPES, parse_page
from llm_wiki.wiki.wiki_manager import iter_content_pages

SECTION_LABELS: dict[str, str] = {
    "summary": "Sources",
    "entity": "Entities",
    "concept": "Concepts",
    "overview": "Overviews",
}

SECTION_ORDER: tuple[str, ...] = PAGE_TYPES


@dataclass(frozen=True)
class WikiPageEntry:
    title: str
    rel_path: str
    page_type: str


def build_page_tree(wiki_root: Path | str) -> dict[str, list[WikiPageEntry]]:
    """Group wiki content pages by frontmatter ``type``, sorted by title."""
    wiki_root = Path(wiki_root).resolve()
    tree: dict[str, list[WikiPageEntry]] = {page_type: [] for page_type in PAGE_TYPES}

    for page_path in iter_content_pages(wiki_root):
        try:
            meta, _ = parse_page(page_path)
        except Exception:
            continue

        page_type = meta.get("type")
        title = meta.get("title")
        if page_type not in tree or not isinstance(title, str) or not title.strip():
            continue

        tree[page_type].append(
            WikiPageEntry(
                title=title.strip(),
                rel_path=page_path.relative_to(wiki_root).as_posix(),
                page_type=page_type,
            )
        )

    for entries in tree.values():
        entries.sort(key=lambda entry: entry.title.lower())

    return tree


def count_tree_pages(tree: dict[str, list[WikiPageEntry]]) -> int:
    return sum(len(entries) for entries in tree.values())
