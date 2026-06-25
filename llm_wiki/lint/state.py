"""Lint issue model and workflow state (Phase 7)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TypedDict


class LintSeverity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    SUGGESTION = "suggestion"


class LintCheckType(str, Enum):
    BROKEN_LINK = "broken_link"
    MISSING_PAGE = "missing_page"
    ORPHAN = "orphan"
    INVALID_FRONTMATTER = "invalid_frontmatter"
    CONTRADICTION = "contradiction"
    STALE_CLAIM = "stale_claim"
    DATA_GAP = "data_gap"


class LintFixKind(str, Enum):
    NONE = "none"
    CREATE_STUB = "create_stub"
    ADD_BACKLINK = "add_backlink"
    APPEND_CONTRADICTION = "append_contradiction"
    REVISE_CLAIM = "revise_claim"


SEVERITY_ORDER = (
    LintSeverity.CRITICAL,
    LintSeverity.WARNING,
    LintSeverity.SUGGESTION,
)


@dataclass(frozen=True)
class LintIssue:
    """One lint finding with enough context to report or fix."""

    id: str
    severity: LintSeverity
    check_type: LintCheckType
    pages: tuple[str, ...]
    description: str
    suggested_action: str
    target: str | None = None
    auto_fixable: bool = False
    fix_kind: LintFixKind = LintFixKind.NONE


class LintState(TypedDict, total=False):
    wiki_root: str
    project_name: str
    checks: str
    schema_text: str
    stats: dict[str, int]
    issues: list[LintIssue]
    research_questions: list[str]
    source_suggestions: list[str]
    errors: list[str]


def init_lint_state(
    wiki_root: Path | str,
    *,
    checks: str = "all",
) -> LintState:
    wiki_path = Path(wiki_root).resolve()
    return {
        "wiki_root": str(wiki_path),
        "project_name": wiki_path.name,
        "checks": checks,
        "issues": [],
        "research_questions": [],
        "source_suggestions": [],
        "errors": [],
    }
