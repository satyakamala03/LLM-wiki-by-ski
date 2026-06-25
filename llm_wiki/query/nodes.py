"""LangGraph node functions for wiki query."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from llm_wiki.index_log import LOG_EVENT_QUERY, append_log_entry, load_wiki_context
from llm_wiki.ingestion.llm import load_prompt, parse_json_response, strip_code_fence
from llm_wiki.ingestion.source import load_schema
from llm_wiki.query.llm import invoke_query_llm
from llm_wiki.query.state import ChatMessage, PageContent, QueryState, SearchHit
from llm_wiki.search.hybrid import hybrid_search
from llm_wiki.wiki.frontmatter import parse_page

MAX_PAGE_CHARS = 18_000
SCHEMA_EXCERPT_CHARS = 2_500


def _wiki_root(state: QueryState) -> Path:
    return Path(state["wiki_root"])


def append_error(state: QueryState, message: str) -> dict[str, list[str]]:
    errors = list(state.get("errors", []))
    errors.append(message)
    return {"errors": errors}


def _format_chat_history(messages: list[ChatMessage]) -> str:
    if not messages:
        return "(none — first question in session)"
    lines: list[str] = []
    for msg in messages[-6:]:
        role = msg.get("role", "user")
        content = str(msg.get("content", "")).strip()
        if content:
            lines.append(f"{role.upper()}: {content[:800]}")
    return "\n\n".join(lines)


def _search_query(state: QueryState) -> str:
    """Build search query; prepend recent topic context for follow-ups."""
    question = state.get("question", "").strip()
    messages = state.get("messages") or []
    if len(messages) < 2:
        return question

    prior_user = [m for m in messages if m.get("role") == "user"]
    if len(prior_user) >= 2:
        last_topic = str(prior_user[-2].get("content", "")).strip()
        if last_topic and last_topic.lower() not in question.lower():
            return f"{last_topic} {question}"
    return question


def _split_answer_and_meta(raw: str) -> tuple[str, dict[str, Any]]:
    text = raw.strip()
    fence = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        answer = text[: fence.start()].strip()
        try:
            meta = json.loads(fence.group(1))
            return answer, meta
        except json.JSONDecodeError:
            pass

    try:
        meta = parse_json_response(text)
        if isinstance(meta, dict) and "coverage" in meta:
            answer = text[: text.find("{")].strip()
            return answer or text, meta
    except Exception:
        pass

    return strip_code_fence(text), {"coverage": "partial", "pages_used": [], "suggested_title": ""}


def load_context(state: QueryState) -> dict[str, Any]:
    wiki_root = _wiki_root(state)
    try:
        context = load_wiki_context(wiki_root)
        schema_text = load_schema(wiki_root)
        excerpt = schema_text[:SCHEMA_EXCERPT_CHARS]
        if len(schema_text) > SCHEMA_EXCERPT_CHARS:
            excerpt += "\n...(truncated)"
        return {
            "schema_text": schema_text,
            "index_text": str(context.get("index", "")),
            "recent_log": str(context.get("recent_log", "")),
            "stats": dict(context.get("stats") or {}),
            "schema_excerpt": excerpt,
        }
    except Exception as exc:
        return append_error(state, f"load_context failed: {exc}")


def run_hybrid_search(state: QueryState) -> dict[str, Any]:
    if state.get("errors"):
        return {}

    project_name = state.get("project_name", "")
    top_k = int(state.get("top_k") or 8)
    query = _search_query(state)

    try:
        results = hybrid_search(project_name, query, top_k=top_k, candidate_k=max(20, top_k * 2))
        hits: list[SearchHit] = [
            {
                "page_path": item.page_path,
                "title": item.title,
                "page_type": item.page_type,
                "snippet": item.snippet,
                "rrf_score": item.rrf_score,
            }
            for item in results
        ]
        return {"search_results": hits}
    except Exception as exc:
        return append_error(state, f"hybrid_search failed: {exc}")


def read_pages(state: QueryState) -> dict[str, Any]:
    if state.get("errors"):
        return {}

    wiki_root = _wiki_root(state)
    hits = state.get("search_results") or []
    pages: list[PageContent] = []
    budget = MAX_PAGE_CHARS

    for hit in hits:
        rel_path = hit.get("page_path", "")
        page_path = wiki_root / rel_path
        if not page_path.is_file():
            continue
        try:
            meta, body = parse_page(page_path)
        except Exception:
            continue

        title = str(meta.get("title", page_path.stem))
        chunk = body.strip()
        if len(chunk) > budget:
            chunk = chunk[:budget] + "\n...(truncated)"
        budget -= len(chunk)
        if budget <= 0 and pages:
            break

        pages.append(
            {
                "page_path": rel_path,
                "title": title,
                "page_type": str(meta.get("type", "")),
                "body": chunk,
                "rrf_score": float(hit.get("rrf_score") or 0),
            }
        )

    if not pages and hits:
        return append_error(state, "read_pages failed: no readable pages from search hits")
    return {"pages": pages}


def synthesize_answer(state: QueryState) -> dict[str, Any]:
    if state.get("errors"):
        return {}

    pages = state.get("pages") or []
    if not pages:
        return append_error(state, "synthesize_answer failed: no pages to synthesize from")

    page_blocks: list[str] = []
    for page in pages:
        page_blocks.append(
            f"### [[{page.get('title', '')}]] (`{page.get('page_path', '')}`)\n"
            f"type: {page.get('page_type', '')}\n\n"
            f"{page.get('body', '')}"
        )

    schema_excerpt = state.get("schema_excerpt") or state.get("schema_text", "")[:SCHEMA_EXCERPT_CHARS]

    try:
        template = load_prompt("query_synthesize.md")
        prompt = template.format(
            schema_excerpt=schema_excerpt,
            index_text=state.get("index_text", "")[:4000],
            recent_log=state.get("recent_log", "")[:1500],
            chat_history=_format_chat_history(state.get("messages") or []),
            question=state.get("question", ""),
            page_contents="\n\n---\n\n".join(page_blocks),
        )
        raw = invoke_query_llm(prompt, temperature=0.2)
        answer, meta = _split_answer_and_meta(raw)
        coverage = str(meta.get("coverage", "partial")).strip().lower()
        if coverage not in {"full", "partial", "none"}:
            coverage = "partial"

        pages_used = meta.get("pages_used") or []
        if not isinstance(pages_used, list):
            pages_used = []
        pages_used = [str(title).strip() for title in pages_used if str(title).strip()]

        suggested_title = str(meta.get("suggested_title", "")).strip()

        return {
            "answer": answer,
            "coverage": coverage,
            "pages_used": pages_used,
            "suggested_title": suggested_title,
        }
    except Exception as exc:
        return append_error(state, f"synthesize_answer failed: {exc}")


def append_query_log(state: QueryState) -> dict[str, Any]:
    wiki_root = _wiki_root(state)
    question = state.get("question", "").strip()
    coverage = state.get("coverage", "unknown")
    errors = state.get("errors") or []

    if errors:
        append_log_entry(wiki_root, LOG_EVENT_QUERY, f"FAILED | {question[:80]}")
    else:
        append_log_entry(
            wiki_root,
            LOG_EVENT_QUERY,
            f"{question[:80]} → coverage={coverage}",
        )

    messages = list(state.get("messages") or [])
    if question:
        messages.append({"role": "user", "content": question})
    answer = state.get("answer", "")
    if answer and not errors:
        messages.append({"role": "assistant", "content": answer})

    return {"messages": messages}
