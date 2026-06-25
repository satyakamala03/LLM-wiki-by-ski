"""Index one-liner generation: Ollama at write time with heuristic fallback."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
ENV_PATH = Path(__file__).resolve().parent.parent / "config" / ".env"
INDEX_SUMMARY_FIELD = "index_summary"


def _load_prompt(name: str) -> str:
    path = PROMPTS_DIR / name
    if not path.is_file():
        raise FileNotFoundError(f"Prompt not found: {path}")
    return path.read_text(encoding="utf-8")


def heuristic_oneliner(body: str, *, max_len: int = 160) -> str:
    """Extract a catalogue line from page body without calling an LLM."""
    for line in body.splitlines():
        text = line.strip()
        if not text:
            continue
        if text.startswith("#"):
            continue
        if text.startswith(">"):
            continue
        if text.startswith("---"):
            continue
        cleaned = re.sub(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", r"\1", text)
        cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
        return cleaned[:max_len].strip()
    return ""


def _body_excerpt(body: str, *, max_chars: int = 1500) -> str:
    text = body.strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."


def generate_index_summary(title: str, body: str) -> str:
    """Generate a one-line catalogue summary; falls back to heuristic on failure."""
    load_dotenv(ENV_PATH)
    provider = os.getenv("INDEX_ONELINER_PROVIDER", "heuristic").lower().strip()

    if provider == "ollama":
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            from langchain_ollama import ChatOllama

            model = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
            base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            template = _load_prompt("index_oneliner.md")
            prompt = template.format(
                title=title,
                body_excerpt=_body_excerpt(body),
            )
            llm = ChatOllama(model=model, base_url=base_url, temperature=0)
            response = llm.invoke(
                [
                    SystemMessage(content="You write concise wiki index catalogue lines."),
                    HumanMessage(content=prompt),
                ]
            )
            summary = (response.content or "").strip()
            summary = summary.splitlines()[0].strip().strip('"')
            if summary:
                return summary[:200]
        except Exception:
            pass

    return heuristic_oneliner(body)


def enrich_meta_with_index_summary(meta: dict[str, Any], body: str) -> dict[str, Any]:
    """Return a copy of meta with index_summary set from LLM or heuristic."""
    updated = dict(meta)
    title = str(updated.get("title", "")).strip() or "Untitled"
    updated[INDEX_SUMMARY_FIELD] = generate_index_summary(title, body)
    return updated
