"""LangGraph ingestion workflow."""

from __future__ import annotations

from pathlib import Path

from langgraph.graph import END, START, StateGraph

from llm_wiki.ingestion.nodes import (
    append_log,
    detect_contradictions,
    extract_info,
    flag_gaps,
    read_source,
    sync_embeddings,
    update_concept_pages,
    update_entity_pages,
    update_index,
    update_topic_pages,
    write_summary_page,
)
from llm_wiki.ingestion.source import resolve_wiki_root
from llm_wiki.ingestion.state import IngestionState, init_ingestion_state


def build_ingestion_graph():
    graph = StateGraph(IngestionState)

    graph.add_node("read_source", read_source)
    graph.add_node("extract_info", extract_info)
    graph.add_node("write_summary_page", write_summary_page)
    graph.add_node("update_entity_pages", update_entity_pages)
    graph.add_node("update_concept_pages", update_concept_pages)
    graph.add_node("update_topic_pages", update_topic_pages)
    graph.add_node("detect_contradictions", detect_contradictions)
    graph.add_node("flag_gaps", flag_gaps)
    graph.add_node("sync_embeddings", sync_embeddings)
    graph.add_node("update_index", update_index)
    graph.add_node("append_log", append_log)

    graph.add_edge(START, "read_source")
    graph.add_edge("read_source", "extract_info")
    graph.add_edge("extract_info", "write_summary_page")
    graph.add_edge("write_summary_page", "update_entity_pages")
    graph.add_edge("update_entity_pages", "update_concept_pages")
    graph.add_edge("update_concept_pages", "update_topic_pages")
    graph.add_edge("update_topic_pages", "detect_contradictions")
    graph.add_edge("detect_contradictions", "flag_gaps")
    graph.add_edge("flag_gaps", "sync_embeddings")
    graph.add_edge("sync_embeddings", "update_index")
    graph.add_edge("update_index", "append_log")
    graph.add_edge("append_log", END)

    return graph.compile()


def run_ingestion(
    wiki_name: str,
    source_path: Path | str,
    *,
    wikis_dir: Path | str = "wikis",
) -> IngestionState:
    wiki_root = resolve_wiki_root(wikis_dir, wiki_name)
    initial = init_ingestion_state(str(wiki_root), str(Path(source_path).resolve()))
    app = build_ingestion_graph()
    return app.invoke(initial)
