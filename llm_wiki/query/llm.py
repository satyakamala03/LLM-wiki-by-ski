"""LLM helpers for query synthesis."""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from llm_wiki.ingestion.llm import get_llm

QUERY_SYSTEM_PROMPT = (
    "You are a careful wiki research assistant. Answer only from provided wiki pages. "
    "Cite sources with [[Page Title]] wikilinks. If the wiki does not cover the question, say so clearly."
)


def invoke_query_llm(prompt: str, *, model: str = "gpt-4o-mini", temperature: float = 0) -> str:
    llm = get_llm(model=model, temperature=temperature)
    response = llm.invoke(
        [
            SystemMessage(content=QUERY_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]
    )
    return (response.content or "").strip()
