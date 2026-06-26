"""Wikilink → in-app markdown links for Streamlit (Phase 8.3)."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import quote

from llm_wiki.wiki.wiki_manager import build_title_index, resolve_wikilink

WIKILINK_WITH_ALIAS = re.compile(
    r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|([^\]]+))?\]\]"
)

PAGE_QUERY_PARAM = "page"


def page_href(rel_path: str, *, param: str = PAGE_QUERY_PARAM) -> str:
    """Relative URL that selects a wiki page in the Streamlit app."""
    return f"?{param}={quote(rel_path, safe='')}"


def linkify_wikilinks(text: str, wiki_root: Path | str) -> str:
    """Replace ``[[Page Title]]`` with markdown links to ``?page=...``."""
    wiki_root = Path(wiki_root).resolve()
    title_index = build_title_index(wiki_root)

    def replace(match: re.Match[str]) -> str:
        target = match.group(1).strip()
        display = (match.group(2) or target).strip()
        resolved = resolve_wikilink(wiki_root, target, title_index)
        if resolved is None:
            return f"**{display}** _(broken link)_"
        rel = resolved.relative_to(wiki_root).as_posix()
        return f"[{display}]({page_href(rel)})"

    return WIKILINK_WITH_ALIAS.sub(replace, text)
