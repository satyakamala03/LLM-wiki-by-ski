"""Generate wiki SCHEMA.md via LLM (Phase 1, Step 1 substep 2)."""

from __future__ import annotations

import re
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from llm_wiki.wiki.wiki_manager import WIKI_SUBDIRS

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "schema_generation.md"
ENV_PATH = Path(__file__).resolve().parent.parent / "config" / ".env"

LINK_STYLE_DESCRIPTIONS = {
    "wikilink": "Obsidian-style wikilinks: `[[Page Title]]` (preferred)",
    "markdown": "standard markdown links: `[Page Title](relative/path/to/page.md)`",
}


class SchemaGenerationError(RuntimeError):
    """Raised when schema generation fails."""


def _load_prompt_template() -> str:
    if not PROMPT_PATH.is_file():
        raise FileNotFoundError(f"Prompt template not found: {PROMPT_PATH}")
    return PROMPT_PATH.read_text(encoding="utf-8")


def _validate_wiki_root(wiki_root: Path) -> Path:
    wiki_root = wiki_root.resolve()
    if not wiki_root.is_dir():
        raise FileNotFoundError(f"Wiki directory not found: {wiki_root}")

    missing = [name for name in WIKI_SUBDIRS if not (wiki_root / name).is_dir()]
    if missing:
        raise FileNotFoundError(
            f"Not a valid wiki root (missing {', '.join(missing)}): {wiki_root}"
        )
    return wiki_root


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    match = re.match(r"^```(?:markdown|md)?\s*\n(.*)\n```\s*$", stripped, re.DOTALL)
    if match:
        return match.group(1).strip()
    return stripped


def generate_schema(
    wiki_root: Path | str,
    *,
    domain: str,
    link_style: str = "wikilink",
    model: str = "gpt-4o-mini",
) -> Path:
    """Generate SCHEMA.md at wiki_root/SCHEMA.md. Overwrites existing SCHEMA.md only."""
    wiki_root = _validate_wiki_root(Path(wiki_root))

    if link_style not in LINK_STYLE_DESCRIPTIONS:
        raise ValueError(
            f"link_style must be one of {list(LINK_STYLE_DESCRIPTIONS)}; got {link_style!r}"
        )

    load_dotenv(ENV_PATH)
    template = _load_prompt_template()
    prompt = template.format(
        domain=domain,
        link_style_description=LINK_STYLE_DESCRIPTIONS[link_style],
    )

    llm = ChatOpenAI(model=model, temperature=0.3)
    response = llm.invoke(
        [
            SystemMessage(
                content=(
                    "You write clear, practical wiki schema documents for knowledge base projects. "
                    "Follow the user's structure exactly."
                )
            ),
            HumanMessage(content=prompt),
        ]
    )

    content = _strip_code_fences(response.content or "")
    if not content:
        raise SchemaGenerationError("LLM returned empty SCHEMA.md content")

    schema_path = wiki_root / "SCHEMA.md"
    schema_path.write_text(content + "\n", encoding="utf-8")
    return schema_path
