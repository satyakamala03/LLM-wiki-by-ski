"""Streamlit app entry (Phase 8)."""

from __future__ import annotations

import streamlit as st

from llm_wiki.index_log.readers import get_index_stats
from llm_wiki.ingestion.source import resolve_wiki_root
from llm_wiki.ui.browse import build_page_tree, count_tree_pages
from llm_wiki.ui.chat import render_chat_panel
from llm_wiki.ui.sidebar import (
    render_chat_settings,
    render_page_tree,
    render_settings_expander,
    render_wiki_selector,
)
from llm_wiki.ui.state import (
    get_selected_page,
    init_session_state,
    sync_page_from_query_params,
    wikis_dir,
)
from llm_wiki.ui.viewer import render_page_viewer


def render_app() -> None:
    st.set_page_config(
        page_title="LLM Wiki",
        page_icon="📚",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    init_session_state()
    sync_page_from_query_params()

    wiki_name = render_wiki_selector()
    if not wiki_name:
        st.title("LLM Wiki")
        st.warning(
            f"No wikis found under `{wikis_dir()}`. "
            "Create one with `python3 cli.py create-wiki <name>`."
        )
        return

    try:
        wiki_root = resolve_wiki_root(wikis_dir(), wiki_name)
    except FileNotFoundError as exc:
        st.title("LLM Wiki")
        st.error(str(exc))
        return

    render_page_tree(wiki_root)
    render_chat_settings(wiki_name)
    render_settings_expander(wiki_root)

    st.title("LLM Wiki")
    st.caption(f"**{wiki_name}**")

    stats = get_index_stats(wiki_root)
    tree = build_page_tree(wiki_root)
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Pages", count_tree_pages(tree))
    col2.metric("Sources", stats["summary"])
    col3.metric("Entities", stats["entity"])
    col4.metric("Concepts", stats["concept"])
    col5.metric("Overviews", stats["overview"])

    tab_browse, tab_chat = st.tabs(["Browse", "Chat"])

    with tab_browse:
        selected = get_selected_page()
        if selected:
            render_page_viewer(wiki_root, selected)
        else:
            st.info("Select a page in the sidebar to browse.")

    with tab_chat:
        render_chat_panel(wiki_name, wiki_root)
