"""LangGraph query workflow."""

from __future__ import annotations

from pathlib import Path

from langgraph.graph import END, START, StateGraph

from llm_wiki.ingestion.source import resolve_wiki_root
from llm_wiki.query.nodes import (
    append_query_log,
    load_context,
    read_pages,
    run_hybrid_search,
    synthesize_answer,
)
from llm_wiki.query.state import ChatMessage, QueryState, init_query_state


def build_query_graph():
    graph = StateGraph(QueryState)

    graph.add_node("load_context", load_context)
    graph.add_node("hybrid_search", run_hybrid_search)
    graph.add_node("read_pages", read_pages)
    graph.add_node("synthesize_answer", synthesize_answer)
    graph.add_node("append_query_log", append_query_log)

    graph.add_edge(START, "load_context")
    graph.add_edge("load_context", "hybrid_search")
    graph.add_edge("hybrid_search", "read_pages")
    graph.add_edge("read_pages", "synthesize_answer")
    graph.add_edge("synthesize_answer", "append_query_log")
    graph.add_edge("append_query_log", END)

    return graph.compile()


def run_query(
    wiki_name: str,
    question: str,
    *,
    wikis_dir: Path | str = "wikis",
    messages: list[ChatMessage] | None = None,
    top_k: int = 8,
) -> QueryState:
    wiki_root = resolve_wiki_root(wikis_dir, wiki_name)
    initial = init_query_state(str(wiki_root), question, messages=messages, top_k=top_k)
    app = build_query_graph()
    return app.invoke(initial)
