"""Streamlit chat panel for wiki queries (Phase 8.4–8.5)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from llm_wiki.env import apply_tf_compat
from llm_wiki.query import run_query, save_answer_as_page
from llm_wiki.query.state import ChatMessage
from llm_wiki.ui.errors import format_user_error
from llm_wiki.ui.state import (
    ensure_chat_wiki,
    get_chat_messages,
    get_chat_top_k,
    set_chat_messages,
    set_selected_page,
    update_chat_message,
    wikis_dir,
)
from llm_wiki.ui.wikilinks import linkify_wikilinks, page_href

MAX_SAVE_TITLE_LEN = 120


def _api_messages(messages: list[dict[str, Any]]) -> list[ChatMessage]:
    return [
        {"role": str(msg["role"]), "content": str(msg["content"])}
        for msg in messages
        if msg.get("role") in {"user", "assistant"} and msg.get("content")
    ]


def _default_save_title(msg: dict[str, Any]) -> str:
    title = (msg.get("suggested_title") or msg.get("question") or "Query answer").strip()
    if len(title) > MAX_SAVE_TITLE_LEN:
        return title[: MAX_SAVE_TITLE_LEN - 3] + "..."
    return title


def _enrich_messages_from_result(
    messages: list[dict[str, Any]],
    result: dict[str, Any],
) -> list[dict[str, Any]]:
    enriched = [dict(msg) for msg in messages]
    if not enriched or enriched[-1].get("role") != "assistant":
        return enriched

    last = dict(enriched[-1])
    coverage = result.get("coverage")
    pages_used = result.get("pages_used")
    if coverage:
        last["coverage"] = coverage
    if pages_used:
        last["pages_used"] = list(pages_used)
    suggested = result.get("suggested_title")
    if suggested:
        last["suggested_title"] = str(suggested).strip()
    question = result.get("question")
    if question:
        last["question"] = str(question).strip()
    enriched[-1] = last
    return enriched


def _save_message_as_page(
    wiki_name: str,
    wiki_root: Path,
    msg_idx: int,
    msg: dict[str, Any],
    title: str,
) -> None:
    body = str(msg.get("content", "")).strip()
    if not body:
        st.warning("Nothing to save — answer is empty.")
        return

    clean_title = title.strip() or _default_save_title(msg)
    with st.spinner("Saving page, rebuilding index, and syncing embeddings…"):
        try:
            page_path = save_answer_as_page(
                wiki_root,
                wiki_name,
                title=clean_title,
                body=body,
            )
        except Exception as exc:
            st.error(format_user_error(exc, wiki_name=wiki_name))
            return

    rel_path = page_path.relative_to(wiki_root).as_posix()
    update_chat_message(
        msg_idx,
        saved_page_path=rel_path,
        save_title=clean_title,
    )
    set_selected_page(rel_path)
    st.success(f"Saved **{clean_title}** as `{rel_path}`. Open it in Browse or the sidebar.")
    st.rerun()


def _render_save_controls(
    msg: dict[str, Any],
    msg_idx: int,
    wiki_name: str,
    wiki_root: Path,
) -> None:
    saved_path = msg.get("saved_page_path")
    if saved_path:
        title = str(msg.get("save_title") or _default_save_title(msg))
        st.markdown(
            f"Saved as wiki page: [{title}]({page_href(str(saved_path))})",
            unsafe_allow_html=False,
        )
        return

    if not str(msg.get("content", "")).strip():
        return

    with st.expander("Save as wiki page"):
        st.caption("Writes an overview page under `topics/`, rebuilds index, and embeds.")
        title = st.text_input(
            "Page title",
            value=_default_save_title(msg),
            key=f"save_title_{msg_idx}",
        )
        if st.button("Save to wiki", key=f"save_btn_{msg_idx}", type="secondary"):
            _save_message_as_page(wiki_name, wiki_root, msg_idx, msg, title)


def _render_message(
    msg: dict[str, Any],
    msg_idx: int,
    wiki_name: str,
    wiki_root: Path,
) -> None:
    role = msg.get("role", "assistant")
    content = str(msg.get("content", ""))

    with st.chat_message(role):
        if role == "assistant":
            st.markdown(linkify_wikilinks(content, wiki_root))
            coverage = msg.get("coverage")
            if coverage:
                st.caption(f"Coverage: {coverage}")
            pages_used = msg.get("pages_used") or []
            if pages_used:
                refs = ", ".join(f"[[{title}]]" for title in pages_used)
                st.caption(linkify_wikilinks(f"Pages used: {refs}", wiki_root))
            _render_save_controls(msg, msg_idx, wiki_name, wiki_root)
        else:
            st.markdown(content)


def render_chat_panel(
    wiki_name: str,
    wiki_root: Path,
) -> None:
    ensure_chat_wiki(wiki_name)
    top_k = get_chat_top_k()

    messages = get_chat_messages()
    for msg_idx, msg in enumerate(messages):
        _render_message(msg, msg_idx, wiki_name, wiki_root)

    prompt = st.chat_input("Ask a question about this wiki…")
    if not prompt:
        return

    with st.spinner("Searching the wiki and synthesizing an answer…"):
        apply_tf_compat()
        try:
            result = run_query(
                wiki_name,
                prompt.strip(),
                wikis_dir=wikis_dir(),
                messages=_api_messages(messages),
                top_k=top_k,
            )
        except FileNotFoundError as exc:
            st.error(format_user_error(exc, wiki_name=wiki_name))
            return
        except Exception as exc:
            st.error(format_user_error(exc, wiki_name=wiki_name))
            return

    errors = result.get("errors") or []
    if errors:
        for error in errors:
            st.error(format_user_error(error, wiki_name=wiki_name))
        return

    set_chat_messages(_enrich_messages_from_result(list(result.get("messages") or []), result))
    st.rerun()
