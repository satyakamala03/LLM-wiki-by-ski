"""Format lint findings for CLI output (Phase 7)."""

from __future__ import annotations

from collections import defaultdict

from llm_wiki.lint.state import SEVERITY_ORDER, LintIssue, LintSeverity


def group_issues_by_severity(issues: list[LintIssue]) -> dict[LintSeverity, list[LintIssue]]:
    grouped: dict[LintSeverity, list[LintIssue]] = defaultdict(list)
    for issue in issues:
        grouped[issue.severity].append(issue)
    return grouped


def format_lint_report(
    issues: list[LintIssue],
    *,
    wiki_name: str | None = None,
    research_questions: list[str] | None = None,
    source_suggestions: list[str] | None = None,
) -> str:
    if wiki_name:
        header = f"Lint report: {wiki_name} ({len(issues)} issue(s))"
    else:
        header = f"Lint report ({len(issues)} issue(s))"

    lines: list[str] = [header]

    if not issues and not research_questions and not source_suggestions:
        return f"{header}\n\nNo issues found."

    if issues:
        lines.append("")
        grouped = group_issues_by_severity(issues)

        for severity in SEVERITY_ORDER:
            bucket = grouped.get(severity, [])
            if not bucket:
                continue
            label = severity.value.upper()
            lines.append(f"=== {label} ({len(bucket)}) ===")
            for issue in bucket:
                pages = ", ".join(f"`{p}`" for p in issue.pages) if issue.pages else "(none)"
                lines.append(f"[{issue.check_type.value}] {pages}")
                if issue.target:
                    lines.append(f"  Target: [[{issue.target}]]")
                lines.append(f"  {issue.description}")
                lines.append(f"  Suggested action: {issue.suggested_action}")
                if issue.auto_fixable:
                    lines.append(f"  Fix: {issue.fix_kind.value}")
            lines.append("")

    research_questions = [q for q in (research_questions or []) if q.strip()]
    source_suggestions = [s for s in (source_suggestions or []) if s.strip()]

    if research_questions or source_suggestions:
        lines.append("=== RESEARCH ===")
        if research_questions:
            lines.append(f"Questions to investigate ({len(research_questions)}):")
            for question in research_questions:
                lines.append(f"  - {question}")
        if source_suggestions:
            lines.append(f"Sources to look for ({len(source_suggestions)}):")
            for suggestion in source_suggestions:
                lines.append(f"  - {suggestion}")

    return "\n".join(lines).rstrip()
