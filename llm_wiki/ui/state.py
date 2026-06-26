"""Streamlit UI helpers (Phase 8)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from llm_wiki.ui.wikilinks import PAGE_QUERY_PARAM
from llm_wiki.projects import list_all_projects
from llm_wiki.query.state import ChatMessage
from llm_wiki.wiki.wiki_manager import list_wikis

DEFAULT_WIKIS_DIR = Path("wikis")
DEFAULT_CHAT_TOP_K = 8
MIN_CHAT_TOP_K = 3
MAX_CHAT_TOP_K = 20


def init_session_state() -> None:
    if "wikis_dir" not in st.session_state:
        st.session_state.wikis_dir = str(DEFAULT_WIKIS_DIR.resolve())
    if "wiki_name" not in st.session_state:
        st.session_state.wiki_name = None
    if "selected_page" not in st.session_state:
        st.session_state.selected_page = None
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    if "chat_wiki" not in st.session_state:
        st.session_state.chat_wiki = None
    if "chat_top_k" not in st.session_state:
        st.session_state.chat_top_k = DEFAULT_CHAT_TOP_K


def clear_chat_messages(*, wiki_name: str | None = None) -> None:
    st.session_state.chat_messages = []
    st.session_state.chat_wiki = wiki_name


def get_chat_top_k() -> int:
    return int(st.session_state.get("chat_top_k", DEFAULT_CHAT_TOP_K))


def set_chat_top_k(value: int) -> None:
    st.session_state.chat_top_k = max(MIN_CHAT_TOP_K, min(MAX_CHAT_TOP_K, int(value)))


def ensure_chat_wiki(wiki_name: str) -> None:
    if st.session_state.get("chat_wiki") != wiki_name:
        st.session_state.chat_wiki = wiki_name
        st.session_state.chat_messages = []


def get_chat_messages() -> list[dict[str, Any]]:
    return list(st.session_state.get("chat_messages") or [])


def set_chat_messages(messages: list[ChatMessage] | list[dict[str, Any]]) -> None:
    st.session_state.chat_messages = list(messages)


def update_chat_message(index: int, **fields: Any) -> None:
    messages = list(st.session_state.get("chat_messages") or [])
    if index < 0 or index >= len(messages):
        return
    updated = dict(messages[index])
    updated.update(fields)
    messages[index] = updated
    st.session_state.chat_messages = messages


def clear_selected_page() -> None:
    st.session_state.selected_page = None
    if PAGE_QUERY_PARAM in st.query_params:
        del st.query_params[PAGE_QUERY_PARAM]


def set_selected_page(rel_path: str | None) -> None:
    st.session_state.selected_page = rel_path
    if rel_path:
        st.query_params[PAGE_QUERY_PARAM] = rel_path
    elif PAGE_QUERY_PARAM in st.query_params:
        del st.query_params[PAGE_QUERY_PARAM]


def get_selected_page() -> str | None:
    return st.session_state.get("selected_page")


def sync_page_from_query_params() -> None:
    """Apply ``?page=...`` from the URL to session state (enables wikilink navigation)."""
    raw = st.query_params.get(PAGE_QUERY_PARAM)
    if isinstance(raw, list):
        raw = raw[0] if raw else None
    if isinstance(raw, str) and raw.strip():
        st.session_state.selected_page = raw.strip()


def wikis_dir() -> Path:
    raw = st.session_state.get("wikis_dir")
    if raw:
        return Path(raw).resolve()
    return DEFAULT_WIKIS_DIR.resolve()


def list_wiki_names() -> list[str]:
    """Wiki folder names on disk (always available without Oracle)."""
    return [path.name for path in list_wikis(wikis_dir())]


def list_wiki_options() -> list[tuple[str, str]]:
    """Return (name, label) pairs for the wiki selector."""
    try:
        records = list_all_projects(wikis_dir())
    except Exception:
        records = []

    if records:
        options: list[tuple[str, str]] = []
        for record in records:
            flags: list[str] = []
            if record.on_disk:
                flags.append("disk")
            if record.in_oracle:
                flags.append("oracle")
            flag_text = f" [{', '.join(flags)}]" if flags else ""
            options.append(
                (
                    record.name,
                    f"{record.name} — {record.page_count} pages{flag_text}",
                )
            )
        return options

    return [(name, name) for name in list_wiki_names()]


def set_wiki_name(name: str | None) -> None:
    st.session_state.wiki_name = name


def get_wiki_name() -> str | None:
    return st.session_state.get("wiki_name")
