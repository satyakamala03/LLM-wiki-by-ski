"""User-facing error messages for the Streamlit UI (Phase 8.6)."""

from __future__ import annotations


def format_user_error(exc: BaseException | str, *, wiki_name: str | None = None) -> str:
    text = str(exc).strip()
    lower = text.lower()

    if "oracle" in lower or "oracledb" in lower or "dpi-" in lower:
        return (
            "**Database unavailable** — Oracle could not be reached. "
            "Start the database, verify `ORACLE_*` in `llm_wiki/config/.env`, "
            "then run `python3 cli.py db-ping`."
        )

    if "openai" in lower or "api key" in lower or "authentication" in lower:
        return (
            "**OpenAI API error** — check `OPENAI_API_KEY` in `llm_wiki/config/.env`."
        )

    if "keras" in lower or "tf_keras" in lower or "transformers.modeling_tf" in lower:
        return (
            "**Embedding model conflict** — add `USE_TF=0` and `TRANSFORMERS_NO_TF=1` "
            "to `.env`, then restart Streamlit."
        )

    if "hybrid_search" in lower or "vector_search" in lower:
        hint = (
            f" Run `python3 cli.py embed-wiki {wiki_name}` to sync embeddings."
            if wiki_name
            else " Run `python3 cli.py embed-wiki <wiki>` to sync embeddings."
        )
        return f"**Search failed** — {text}.{hint}"

    if "embed" in lower and ("model" in lower or "sentence" in lower):
        return f"**Embedding error** — {text}"

    if "wiki not found" in lower or "filenotfounderror" in lower:
        return f"**Wiki not found** — {text}"

    if text.startswith("**"):
        return text

    return text
