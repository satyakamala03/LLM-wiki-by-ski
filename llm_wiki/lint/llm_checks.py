"""LLM-powered wiki lint checks (Phase 7.2)."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from llm_wiki.index_log.readers import get_index_stats, read_index
from llm_wiki.ingestion.llm import invoke_llm, load_prompt, parse_json_response
from llm_wiki.ingestion.source import load_schema
from llm_wiki.lint.state import (
    LintCheckType,
    LintFixKind,
    LintIssue,
    LintSeverity,
)
from llm_wiki.lint.structural import _collect_link_refs
from llm_wiki.wiki.frontmatter import parse_page
from llm_wiki.wiki.wiki_manager import iter_content_pages

MAX_BODY_CHARS = 4000
MAX_SCHEMA_CHARS = 2000
MAX_INDEX_CHARS = 6000
MAX_CONTRADICTION_PAIRS = 15
MAX_STALE_PAGES = 12
SCHEMA_EXCERPT_CHARS = 1200


@dataclass
class PageInfo:
    rel_path: str
    title: str
    page_type: str
    updated: str
    tags: tuple[str, ...]
    sources: tuple[str, ...]
    body: str


@dataclass
class LintLLMResult:
    issues: list[LintIssue] = field(default_factory=list)
    research_questions: list[str] = field(default_factory=list)
    source_suggestions: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _issue_id(*parts: str) -> str:
    slug = ":".join(parts)
    slug = re.sub(r"[^a-zA-Z0-9:_-]+", "-", slug.lower())
    return slug.strip("-")


def _truncate(text: str, limit: int) -> str:
    cleaned = text.strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def _schema_excerpt(schema_text: str) -> str:
    return _truncate(schema_text, SCHEMA_EXCERPT_CHARS)


def _as_str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _load_pages(wiki_root: Path) -> dict[str, PageInfo]:
    pages: dict[str, PageInfo] = {}
    for page_path in iter_content_pages(wiki_root):
        rel = page_path.relative_to(wiki_root).as_posix()
        try:
            meta, body = parse_page(page_path)
        except Exception:
            continue
        title = str(meta.get("title", page_path.stem)).strip()
        page_type = str(meta.get("type", "entity")).strip()
        updated = str(meta.get("updated", "")).strip()
        tags = tuple(sorted({str(t).strip() for t in (meta.get("tags") or []) if str(t).strip()}))
        sources = tuple(_as_str_list(meta.get("sources")))
        pages[rel] = PageInfo(
            rel_path=rel,
            title=title,
            page_type=page_type,
            updated=updated,
            tags=tags,
            sources=sources,
            body=body,
        )
    return pages


def _contradiction_pairs(
    pages: dict[str, PageInfo],
    link_refs: list[tuple[str, str, str | None]],
    *,
    max_pairs: int = MAX_CONTRADICTION_PAIRS,
) -> list[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()

    outbound: dict[str, set[str]] = defaultdict(set)
    for source_rel, _target, resolved_rel in link_refs:
        if resolved_rel and not resolved_rel.startswith("summaries/"):
            outbound[source_rel].add(resolved_rel)

    for page_a, targets in outbound.items():
        if page_a not in pages or page_a.startswith("summaries/"):
            continue
        for page_b in targets:
            if page_b not in pages or page_b.startswith("summaries/"):
                continue
            if page_a in outbound.get(page_b, set()):
                pairs.add(tuple(sorted((page_a, page_b))))

    tag_to_pages: dict[str, list[str]] = defaultdict(list)
    for rel, info in pages.items():
        if rel.startswith("summaries/"):
            continue
        for tag in info.tags:
            tag_to_pages[tag.lower()].append(rel)

    for rels in tag_to_pages.values():
        unique = sorted(set(rels))
        for index, page_a in enumerate(unique):
            for page_b in unique[index + 1 :]:
                pairs.add(tuple(sorted((page_a, page_b))))

    return sorted(pairs)[:max_pairs]


def _summaries_for_page(
    page: PageInfo,
    pages: dict[str, PageInfo],
) -> list[PageInfo]:
    """Summaries whose raw source overlaps this page's sources list."""
    summaries: list[PageInfo] = []
    seen: set[str] = set()
    page_sources = set(page.sources)
    if not page_sources:
        return summaries

    for rel, info in pages.items():
        if info.page_type != "summary":
            continue
        if not page_sources.intersection(info.sources):
            continue
        if rel in seen:
            continue
        seen.add(rel)
        summaries.append(info)
    return summaries


def _should_check_stale(page: PageInfo, summaries: list[PageInfo]) -> bool:
    """Run stale check when a related summary is same age or newer than the page."""
    if not summaries:
        return False
    if not page.updated:
        return True
    return any(not s.updated or s.updated >= page.updated for s in summaries)


def check_contradictions(
    wiki_root: Path,
    *,
    schema_text: str = "",
    max_pairs: int = MAX_CONTRADICTION_PAIRS,
) -> tuple[list[LintIssue], list[str]]:
    wiki_root = wiki_root.resolve()
    pages = _load_pages(wiki_root)
    if len(pages) < 2:
        return [], []

    schema_excerpt = _schema_excerpt(schema_text or load_schema(wiki_root))
    link_refs = _collect_link_refs(wiki_root)
    pairs = _contradiction_pairs(pages, link_refs, max_pairs=max_pairs)
    issues: list[LintIssue] = []
    errors: list[str] = []

    template = load_prompt("lint_contradiction.md")
    for page_a, page_b in pairs:
        info_a = pages[page_a]
        info_b = pages[page_b]
        try:
            prompt = template.format(
                schema_excerpt=schema_excerpt,
                page_a_path=page_a,
                page_a_title=info_a.title,
                page_a_body=_truncate(info_a.body, MAX_BODY_CHARS),
                page_b_path=page_b,
                page_b_title=info_b.title,
                page_b_body=_truncate(info_b.body, MAX_BODY_CHARS),
            )
            result = parse_json_response(invoke_llm(prompt, temperature=0))
        except Exception as exc:
            errors.append(f"contradiction check {page_a} vs {page_b}: {exc}")
            continue

        if not result.get("has_contradiction"):
            continue

        note = str(result.get("note", "")).strip()
        if not note:
            continue

        suggested = str(result.get("suggested_action", "")).strip() or (
            "Review both pages and reconcile or document the disagreement."
        )
        issues.append(
            LintIssue(
                id=_issue_id("contradiction", page_a, page_b),
                severity=LintSeverity.CRITICAL,
                check_type=LintCheckType.CONTRADICTION,
                pages=(page_a, page_b),
                description=note,
                suggested_action=suggested,
                auto_fixable=True,
                fix_kind=LintFixKind.APPEND_CONTRADICTION,
            )
        )

    return issues, errors


def check_stale_claims(
    wiki_root: Path,
    *,
    schema_text: str = "",
    max_pages: int = MAX_STALE_PAGES,
) -> tuple[list[LintIssue], list[str]]:
    wiki_root = wiki_root.resolve()
    pages = _load_pages(wiki_root)
    schema_excerpt = _schema_excerpt(schema_text or load_schema(wiki_root))
    template = load_prompt("lint_stale_claim.md")
    issues: list[LintIssue] = []
    errors: list[str] = []

    candidates: list[tuple[str, list[PageInfo]]] = []
    for rel, info in sorted(pages.items()):
        if info.page_type in ("summary",):
            continue
        if info.page_type not in ("entity", "concept", "overview"):
            continue
        summaries = _summaries_for_page(info, pages)
        if _should_check_stale(info, summaries):
            candidates.append((rel, summaries))

    for rel, summaries in candidates[:max_pages]:
        info = pages[rel]
        summaries_block = "\n\n".join(
            f"---\n`{summary.rel_path}` ({summary.title}, updated {summary.updated}):\n"
            f"{_truncate(summary.body, MAX_BODY_CHARS // 2)}"
            for summary in summaries[:3]
        )
        try:
            prompt = template.format(
                schema_excerpt=schema_excerpt,
                page_path=rel,
                page_title=info.title,
                page_updated=info.updated or "unknown",
                page_body=_truncate(info.body, MAX_BODY_CHARS),
                summaries_block=summaries_block,
            )
            result = parse_json_response(invoke_llm(prompt, temperature=0))
        except Exception as exc:
            errors.append(f"stale claim check {rel}: {exc}")
            continue

        if not result.get("has_stale_claim"):
            continue

        note = str(result.get("note", "")).strip()
        if not note:
            continue

        superseded = str(result.get("superseded_by", "")).strip()
        stale_claim = str(result.get("stale_claim", "")).strip()
        description = note
        if stale_claim:
            description = f"{note} Stale claim: {stale_claim}"
        if superseded:
            description = f"{description} Superseded by: {superseded}"

        suggested = str(result.get("suggested_action", "")).strip() or (
            "Revise the page to reflect newer summaries or document the conflict."
        )
        summary_paths = tuple(s.rel_path for s in summaries[:3])
        issue_pages = (rel, *summary_paths) if summary_paths else (rel,)

        issues.append(
            LintIssue(
                id=_issue_id("stale-claim", rel),
                severity=LintSeverity.CRITICAL,
                check_type=LintCheckType.STALE_CLAIM,
                pages=issue_pages,
                description=description,
                suggested_action=suggested,
                auto_fixable=True,
                fix_kind=LintFixKind.REVISE_CLAIM,
            )
        )

    return issues, errors


def check_data_gaps(
    wiki_root: Path,
    *,
    schema_text: str = "",
) -> LintLLMResult:
    wiki_root = wiki_root.resolve()
    schema_text = schema_text or load_schema(wiki_root)
    index_text = read_index(wiki_root)
    stats = get_index_stats(wiki_root)

    template = load_prompt("lint_gaps.md")
    result = LintLLMResult()

    try:
        prompt = template.format(
            schema_text=_truncate(schema_text, MAX_SCHEMA_CHARS),
            index_text=_truncate(index_text, MAX_INDEX_CHARS),
            stats_json=json.dumps(stats, indent=2),
        )
        parsed = parse_json_response(invoke_llm(prompt, temperature=0.2))
    except Exception as exc:
        result.errors.append(f"data gap check: {exc}")
        return result

    result.research_questions = _as_str_list(parsed.get("research_questions"))
    result.source_suggestions = _as_str_list(parsed.get("source_suggestions"))

    gaps = parsed.get("gaps") or []
    if not isinstance(gaps, list):
        return result

    for index, gap in enumerate(gaps):
        if not isinstance(gap, dict):
            continue
        title = str(gap.get("title", f"Gap {index + 1}")).strip()
        description = str(gap.get("description", "")).strip()
        if not description:
            continue
        suggested = str(gap.get("suggested_action", "")).strip() or (
            "Ingest additional sources or create a dedicated page."
        )
        page_list = _as_str_list(gap.get("pages"))
        result.issues.append(
            LintIssue(
                id=_issue_id("data-gap", title),
                severity=LintSeverity.SUGGESTION,
                check_type=LintCheckType.DATA_GAP,
                pages=tuple(page_list),
                target=title,
                description=description,
                suggested_action=suggested,
                auto_fixable=False,
                fix_kind=LintFixKind.NONE,
            )
        )

    return result


def run_llm_checks(
    wiki_root: Path | str,
    *,
    schema_text: str | None = None,
) -> LintLLMResult:
    """Run all LLM lint passes and merge results."""
    wiki_root = Path(wiki_root).resolve()
    schema = schema_text if schema_text is not None else load_schema(wiki_root)
    merged = LintLLMResult()

    contradiction_issues, contradiction_errors = check_contradictions(
        wiki_root, schema_text=schema
    )
    merged.issues.extend(contradiction_issues)
    merged.errors.extend(contradiction_errors)

    stale_issues, stale_errors = check_stale_claims(wiki_root, schema_text=schema)
    merged.issues.extend(stale_issues)
    merged.errors.extend(stale_errors)

    gap_result = check_data_gaps(wiki_root, schema_text=schema)
    merged.issues.extend(gap_result.issues)
    merged.research_questions.extend(gap_result.research_questions)
    merged.source_suggestions.extend(gap_result.source_suggestions)
    merged.errors.extend(gap_result.errors)

    return merged
