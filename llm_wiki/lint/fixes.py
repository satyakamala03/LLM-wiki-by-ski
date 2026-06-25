"""Apply lint fixes and post-fix wiki hooks (Phase 7.4)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from llm_wiki.embeddings.sync import sync_page_paths
from llm_wiki.index_log import append_log_entry, enrich_meta_with_index_summary, rebuild_index
from llm_wiki.index_log.log_writer import LOG_EVENT_LINT
from llm_wiki.ingestion.llm import invoke_llm, load_prompt
from llm_wiki.ingestion.nodes import find_page
from llm_wiki.lint.state import LintCheckType, LintFixKind, LintIssue
from llm_wiki.projects import try_sync_project
from llm_wiki.wiki.contradictions import append_contradiction
from llm_wiki.wiki.frontmatter import new_frontmatter, parse_page, touch_updated, write_page
from llm_wiki.wiki.wiki_manager import title_to_slug

INDEX_HEADING_BY_TYPE = {
    "summary": "Sources",
    "entity": "Entities",
    "concept": "Concepts",
    "overview": "Overviews",
}

LINT_SOURCE_LABEL = "lint"


@dataclass
class FixResult:
    applied: bool
    pages_touched: list[str] = field(default_factory=list)
    message: str = ""


def preview_fix(issue: LintIssue) -> str:
    if issue.fix_kind == LintFixKind.CREATE_STUB:
        title = issue.target or "page"
        slug = title_to_slug(title)
        return f"Create stub page `entities/{slug}.md` for [[{title}]]"
    if issue.fix_kind == LintFixKind.ADD_BACKLINK:
        page = issue.pages[0] if issue.pages else "page"
        return f"Add index entry linking to orphan page `{page}`"
    if issue.fix_kind == LintFixKind.APPEND_CONTRADICTION:
        pages = ", ".join(f"`{p}`" for p in issue.pages)
        return f"Append Contradictions note on {pages}"
    if issue.fix_kind == LintFixKind.REVISE_CLAIM:
        page = issue.pages[0] if issue.pages else "page"
        return f"Append Revision note on `{page}`"
    return issue.suggested_action


def _write_page_with_summary(page_path: Path, meta: dict, body: str) -> None:
    meta = enrich_meta_with_index_summary(meta, body)
    write_page(page_path, meta, body)


def _append_revision_note(body: str, description: str, suggested_action: str) -> str:
    marker = "## Revision note"
    note = f"{description.strip()}\n\nSuggested: {suggested_action.strip()}"
    if marker in body:
        return body.rstrip() + f"\n\n{note}\n"
    return body.rstrip() + f"\n\n{marker}\n\n{note}\n"


def _append_index_entry(wiki_root: Path, page_path: Path) -> str:
    meta, body = parse_page(page_path)
    title = str(meta.get("title", page_path.stem)).strip()
    page_type = str(meta.get("type", "entity"))
    heading = INDEX_HEADING_BY_TYPE.get(page_type, "Entities")
    rel = page_path.relative_to(wiki_root).as_posix()
    created = str(meta.get("created", "")).strip()
    sources = meta.get("sources") or []
    source_count = len(sources) if isinstance(sources, list) else 0

    one_liner = str(meta.get("index_summary", "")).strip()
    if not one_liner:
        one_liner = " ".join(body.split())[:120]

    meta_bits = [f"`{rel}`"]
    if created:
        meta_bits.append(f"created {created}")
    if source_count:
        meta_bits.append(f"{source_count} source{'s' if source_count != 1 else ''}")
    line = f"- [[{title}]] — {one_liner} ({', '.join(meta_bits)})"

    index_path = wiki_root / "index.md"
    content = index_path.read_text(encoding="utf-8") if index_path.is_file() else "# Wiki Index\n"
    if f"[[{title}]]" in content:
        return "index.md"

    pattern = re.compile(rf"(^## {re.escape(heading)}\s*$)", re.MULTILINE)
    match = pattern.search(content)
    if not match:
        content = content.rstrip() + f"\n\n## {heading}\n\n{line}\n"
    else:
        start = match.end()
        next_heading = re.search(r"^## ", content[start:], re.MULTILINE)
        insert_at = start + next_heading.start() if next_heading else len(content)
        prefix = content[:insert_at].rstrip()
        suffix = content[insert_at:].lstrip("\n")
        content = f"{prefix}\n{line}\n" + (f"\n{suffix}" if suffix else "")

    index_path.write_text(content, encoding="utf-8")
    return "index.md"


def _fix_create_stub(
    wiki_root: Path,
    issue: LintIssue,
    *,
    schema_text: str,
) -> FixResult:
    title = (issue.target or "").strip()
    if not title:
        return FixResult(False, message="Missing target title for stub.")

    if find_page(wiki_root, title) is not None:
        return FixResult(False, message=f"Page [[{title}]] already exists.")

    page_path = wiki_root / "entities" / f"{title_to_slug(title)}.md"
    referrers = ", ".join(issue.pages) if issue.pages else "wiki links"
    template = load_prompt("ingest_gap_stub.md")
    prompt = template.format(
        schema_text=schema_text,
        title=title,
        kind="entity",
        source_filename=LINT_SOURCE_LABEL,
        context=f"Lint reported: {issue.description} (referenced from {referrers})",
    )
    body = invoke_llm(prompt, temperature=0.2)
    meta = new_frontmatter(
        title,
        "entity",
        tags=["stub", "lint"],
        sources=[],
    )
    _write_page_with_summary(page_path, meta, body)
    rel = page_path.relative_to(wiki_root).as_posix()
    return FixResult(True, pages_touched=[rel], message=f"Created stub: {rel}")


def _fix_add_backlink(wiki_root: Path, issue: LintIssue) -> FixResult:
    if not issue.pages:
        return FixResult(False, message="No orphan page path in issue.")
    rel = issue.pages[0]
    page_path = wiki_root / rel
    if not page_path.is_file():
        return FixResult(False, message=f"Page not found: {rel}")

    touched = _append_index_entry(wiki_root, page_path)
    pages = [rel]
    if touched not in pages:
        pages.append(touched)
    return FixResult(True, pages_touched=pages, message=f"Added index link for `{rel}`")


def _fix_append_contradiction(wiki_root: Path, issue: LintIssue) -> FixResult:
    if not issue.pages:
        return FixResult(False, message="No pages listed for contradiction fix.")

    touched: list[str] = []
    note = issue.description.strip() or issue.suggested_action
    for rel in issue.pages[:2]:
        page_path = wiki_root / rel
        if not page_path.is_file():
            continue
        meta, body = parse_page(page_path)
        updated_body = append_contradiction(body, note, LINT_SOURCE_LABEL)
        _write_page_with_summary(page_path, touch_updated(meta), updated_body)
        touched.append(rel)

    if not touched:
        return FixResult(False, message="Could not update contradiction pages.")
    return FixResult(True, pages_touched=touched, message=f"Noted contradiction on {', '.join(touched)}")


def _fix_revise_claim(wiki_root: Path, issue: LintIssue) -> FixResult:
    if not issue.pages:
        return FixResult(False, message="No page listed for stale claim fix.")

    rel = issue.pages[0]
    page_path = wiki_root / rel
    if not page_path.is_file():
        return FixResult(False, message=f"Page not found: {rel}")

    meta, body = parse_page(page_path)
    updated_body = _append_revision_note(body, issue.description, issue.suggested_action)
    _write_page_with_summary(page_path, touch_updated(meta), updated_body)
    return FixResult(True, pages_touched=[rel], message=f"Added revision note on `{rel}`")


def apply_fix(
    wiki_root: Path | str,
    issue: LintIssue,
    *,
    schema_text: str = "",
) -> FixResult:
    """Apply a single lint fix. Does not rebuild index or sync embeddings."""
    wiki_root = Path(wiki_root).resolve()

    if not issue.auto_fixable:
        return FixResult(False, message="Issue is not auto-fixable.")

    if issue.fix_kind == LintFixKind.CREATE_STUB:
        return _fix_create_stub(wiki_root, issue, schema_text=schema_text)
    if issue.fix_kind == LintFixKind.ADD_BACKLINK:
        return _fix_add_backlink(wiki_root, issue)
    if issue.fix_kind == LintFixKind.APPEND_CONTRADICTION:
        return _fix_append_contradiction(wiki_root, issue)
    if issue.fix_kind == LintFixKind.REVISE_CLAIM:
        return _fix_revise_claim(wiki_root, issue)

    return FixResult(False, message=f"No handler for fix kind {issue.fix_kind.value}.")


def finalize_wiki_changes(
    wiki_root: Path | str,
    project_name: str,
    pages_touched: list[str],
    *,
    issue_count: int,
    fixes_applied: int,
    fix_kinds: list[str] | None = None,
) -> None:
    """Rebuild index, sync embeddings, log lint pass, refresh project metadata."""
    wiki_root = Path(wiki_root).resolve()
    unique_pages = sorted({p for p in pages_touched if p})

    if unique_pages:
        rebuild_index(wiki_root)
        sync_page_paths(project_name, wiki_root, unique_pages)

    kinds = ", ".join(fix_kinds or []) or "none"
    append_log_entry(
        wiki_root,
        LOG_EVENT_LINT,
        f"{issue_count} issues reported, {fixes_applied} fixes applied ({kinds})",
    )
    try_sync_project(project_name, wiki_root)


def should_skip_issue(issue: LintIssue, fixed_targets: set[str]) -> bool:
    """Skip duplicate broken/missing page issues after stub created."""
    if issue.check_type not in (LintCheckType.BROKEN_LINK, LintCheckType.MISSING_PAGE):
        return False
    if not issue.target:
        return False
    return issue.target.strip().lower() in fixed_targets
