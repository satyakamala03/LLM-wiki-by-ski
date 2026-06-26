"""Wiki page viewer for Streamlit (Phase 8.3)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import streamlit as st

from llm_wiki.ui.browse import SECTION_LABELS
from llm_wiki.ui.wikilinks import linkify_wikilinks
from llm_wiki.wiki.frontmatter import parse_page


@dataclass(frozen=True)
class PageView:
    rel_path: str
    title: str
    body: str
    meta: dict[str, Any] | None


def resolve_page_path(wiki_root: Path | str, rel_path: str) -> Path | None:
    """Return an absolute page path if *rel_path* is a safe markdown file under *wiki_root*."""
    wiki_root = Path(wiki_root).resolve()
    if not rel_path or rel_path.startswith("/"):
        return None

    candidate = (wiki_root / rel_path).resolve()
    try:
        candidate.relative_to(wiki_root)
    except ValueError:
        return None

    if candidate.is_file() and candidate.suffix.lower() == ".md":
        return candidate
    return None


def load_page_view(wiki_root: Path | str, rel_path: str) -> PageView | None:
    page_path = resolve_page_path(wiki_root, rel_path)
    if page_path is None:
        return None

    rel = page_path.relative_to(Path(wiki_root).resolve()).as_posix()
    if rel == "index.md":
        body = page_path.read_text(encoding="utf-8")
        return PageView(rel_path=rel, title="Wiki Index", body=body, meta=None)

    try:
        meta, body = parse_page(page_path)
    except Exception:
        return None

    title = meta.get("title")
    if not isinstance(title, str) or not title.strip():
        title = page_path.stem.replace("-", " ").title()

    return PageView(rel_path=rel, title=title.strip(), body=body, meta=meta)


def render_page_viewer(wiki_root: Path, rel_path: str) -> None:
    page = load_page_view(wiki_root, rel_path)
    if page is None:
        st.error(f"Page not found: `{rel_path}`")
        return

    st.subheader(page.title)
    st.caption(f"`{page.rel_path}`")

    if page.meta:
        page_type = page.meta.get("type")
        type_label = SECTION_LABELS.get(page_type, page_type)
        tags = page.meta.get("tags") or []
        created = page.meta.get("created", "")
        updated = page.meta.get("updated", "")

        meta_bits: list[str] = []
        if type_label:
            meta_bits.append(str(type_label))
        if created:
            meta_bits.append(f"created {created}")
        if updated and updated != created:
            meta_bits.append(f"updated {updated}")
        if meta_bits:
            st.caption(" · ".join(meta_bits))

        if isinstance(tags, list) and tags:
            st.caption(", ".join(f"`{tag}`" for tag in tags if isinstance(tag, str)))

    rendered = linkify_wikilinks(page.body, wiki_root)
    st.markdown(rendered)
