"""LangGraph node functions for wiki lint (Phase 7.3)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from llm_wiki.index_log.readers import get_index_stats
from llm_wiki.ingestion.source import load_schema
from llm_wiki.lint.llm_checks import run_llm_checks as collect_llm_issues
from llm_wiki.lint.state import SEVERITY_ORDER, LintIssue, LintState
from llm_wiki.lint.structural import run_structural_checks as collect_structural_issues


def _wiki_root(state: LintState) -> Path:
    return Path(state["wiki_root"])


def _checks_mode(state: LintState) -> str:
    return str(state.get("checks") or "all").strip().lower()


def load_context(state: LintState) -> dict[str, Any]:
    wiki_root = _wiki_root(state)
    return {
        "schema_text": load_schema(wiki_root),
        "stats": get_index_stats(wiki_root),
    }


def structural_checks(state: LintState) -> dict[str, Any]:
    if _checks_mode(state) not in ("structural", "all"):
        return {}

    issues = list(state.get("issues") or [])
    issues.extend(collect_structural_issues(_wiki_root(state)))
    return {"issues": issues}


def llm_checks(state: LintState) -> dict[str, Any]:
    if _checks_mode(state) not in ("llm", "all"):
        return {}

    wiki_root = _wiki_root(state)
    schema_text = state.get("schema_text") or load_schema(wiki_root)
    result = collect_llm_issues(wiki_root, schema_text=schema_text)

    issues = list(state.get("issues") or [])
    issues.extend(result.issues)
    errors = list(state.get("errors") or [])
    errors.extend(result.errors)
    research_questions = list(state.get("research_questions") or [])
    research_questions.extend(result.research_questions)
    source_suggestions = list(state.get("source_suggestions") or [])
    source_suggestions.extend(result.source_suggestions)

    return {
        "issues": issues,
        "errors": errors,
        "research_questions": research_questions,
        "source_suggestions": source_suggestions,
    }


def _severity_rank(issue: LintIssue) -> int:
    try:
        return SEVERITY_ORDER.index(issue.severity)
    except ValueError:
        return len(SEVERITY_ORDER)


def prioritize_findings(state: LintState) -> dict[str, Any]:
    issues = list(state.get("issues") or [])
    if not issues:
        return {"issues": []}

    by_id: dict[str, LintIssue] = {}
    for issue in issues:
        by_id[issue.id] = issue

    deduped = sorted(by_id.values(), key=lambda item: (_severity_rank(item), item.check_type.value, item.id))
    return {"issues": deduped}


def append_error(state: LintState, message: str) -> dict[str, list[str]]:
    errors = list(state.get("errors") or [])
    errors.append(message)
    return {"errors": errors}
