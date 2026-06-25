"""LangGraph lint workflow (Phase 7.3)."""

from __future__ import annotations

from pathlib import Path

from langgraph.graph import END, START, StateGraph

from llm_wiki.ingestion.source import resolve_wiki_root
from llm_wiki.lint.nodes import (
    llm_checks,
    load_context,
    prioritize_findings,
    structural_checks,
)
from llm_wiki.lint.state import LintState, init_lint_state


def build_lint_graph():
    graph = StateGraph(LintState)

    graph.add_node("load_context", load_context)
    graph.add_node("structural_checks", structural_checks)
    graph.add_node("llm_checks", llm_checks)
    graph.add_node("prioritize_findings", prioritize_findings)

    graph.add_edge(START, "load_context")
    graph.add_edge("load_context", "structural_checks")
    graph.add_edge("structural_checks", "llm_checks")
    graph.add_edge("llm_checks", "prioritize_findings")
    graph.add_edge("prioritize_findings", END)

    return graph.compile()


def run_lint(
    wiki_name: str,
    *,
    wikis_dir: Path | str = "wikis",
    checks: str = "all",
) -> LintState:
    wiki_root = resolve_wiki_root(wikis_dir, wiki_name)
    initial = init_lint_state(wiki_root, checks=checks)
    app = build_lint_graph()
    return app.invoke(initial)
