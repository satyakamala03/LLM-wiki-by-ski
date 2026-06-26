"""Streamlit sidebar: wiki selector and page tree (Phase 8.2)."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from llm_wiki.ui.browse import SECTION_LABELS, SECTION_ORDER, build_page_tree
from llm_wiki.ui.state import (
    clear_chat_messages,
    clear_selected_page,
    get_chat_messages,
    get_chat_top_k,
    get_selected_page,
    get_wiki_name,
    list_wiki_names,
    list_wiki_options,
    set_chat_top_k,
    set_selected_page,
    set_wiki_name,
    wikis_dir,
)


def _page_button_key(rel_path: str) -> str:
    return f"page_{rel_path.replace('/', '_')}"


def render_wiki_selector() -> str | None:
    """Render wiki dropdown in the sidebar; return selected wiki name."""
    options = list_wiki_options()
    if not options:
        st.sidebar.warning(f"No wikis under `{wikis_dir()}`.")
        return None

    names = [name for name, _ in options]
    labels = {name: label for name, label in options}
    current = get_wiki_name()
    if current not in names:
        current = names[0]

    selected = st.sidebar.selectbox(
        "Wiki project",
        options=names,
        index=names.index(current),
        format_func=lambda name: labels.get(name, name),
    )

    if selected != current:
        set_wiki_name(selected)
        clear_selected_page()
        clear_chat_messages()

    return selected


def render_chat_settings(wiki_name: str) -> None:
    """Sidebar chat controls: retrieval depth and clear history."""
    st.sidebar.divider()
    st.sidebar.subheader("Chat settings")

    top_k = st.sidebar.slider(
        "Pages to retrieve",
        min_value=3,
        max_value=20,
        value=get_chat_top_k(),
        help="Wiki pages hybrid search reads before synthesizing an answer.",
    )
    set_chat_top_k(top_k)

    if get_chat_messages():
        if st.sidebar.button("Clear chat history", use_container_width=True):
            clear_chat_messages(wiki_name=wiki_name)
            st.rerun()


def render_settings_expander(wiki_root: Path) -> None:
    """Debug paths tucked into sidebar."""
    with st.sidebar.expander("Settings"):
        st.caption("Wiki root")
        st.code(str(wiki_root), language=None)
        st.caption("Ingest (CLI)")
        st.code(f"python3 cli.py ingest {wiki_root.name} <file.md>", language="bash")
        disk_wikis = list_wiki_names()
        if disk_wikis:
            st.caption("Wikis on disk")
            st.write(", ".join(disk_wikis))


def render_page_tree(wiki_root: Path) -> None:
    """Sidebar browse tree grouped by page type."""
    tree = build_page_tree(wiki_root)
    st.sidebar.subheader("Browse")

    index_path = wiki_root / "index.md"
    if index_path.is_file():
        rel = "index.md"
        is_selected = get_selected_page() == rel
        if st.sidebar.button(
            "Wiki index",
            key="page_index_md",
            use_container_width=True,
            type="primary" if is_selected else "secondary",
        ):
            set_selected_page(rel)

    for page_type in SECTION_ORDER:
        entries = tree[page_type]
        section_label = SECTION_LABELS[page_type]
        with st.sidebar.expander(f"{section_label} ({len(entries)})", expanded=False):
            if not entries:
                st.caption("No pages")
                continue

            for entry in entries:
                is_selected = get_selected_page() == entry.rel_path
                if st.button(
                    entry.title,
                    key=_page_button_key(entry.rel_path),
                    use_container_width=True,
                    type="primary" if is_selected else "secondary",
                ):
                    set_selected_page(entry.rel_path)
