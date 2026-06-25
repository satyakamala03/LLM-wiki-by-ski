"""LLM helpers for ingestion prompts."""

from __future__ import annotations

import json
import re
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
ENV_PATH = Path(__file__).resolve().parent.parent / "config" / ".env"

SYSTEM_PROMPT = (
    "You help maintain a structured markdown wiki. Follow instructions exactly. "
    "Use only facts supported by the provided source text. If uncertain, say so."
)


def load_prompt(name: str) -> str:
    path = PROMPTS_DIR / name
    if not path.is_file():
        raise FileNotFoundError(f"Prompt not found: {path}")
    return path.read_text(encoding="utf-8")


def get_llm(*, model: str = "gpt-4o-mini", temperature: float = 0) -> ChatOpenAI:
    load_dotenv(ENV_PATH)
    return ChatOpenAI(model=model, temperature=temperature)


def invoke_llm(prompt: str, *, model: str = "gpt-4o-mini", temperature: float = 0) -> str:
    llm = get_llm(model=model, temperature=temperature)
    response = llm.invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]
    )
    return (response.content or "").strip()


def strip_code_fence(text: str) -> str:
    stripped = text.strip()
    match = re.match(r"^```(?:json|markdown|md)?\s*\n(.*)\n```\s*$", stripped, re.DOTALL)
    if match:
        return match.group(1).strip()
    return stripped


def parse_json_response(text: str) -> dict:
    cleaned = strip_code_fence(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(cleaned[start : end + 1])
        raise
