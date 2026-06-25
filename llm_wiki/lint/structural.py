"""Deterministic wiki lint checks (Phase 7.1)."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from llm_wiki.lint.state import (
    LintCheckType,
    LintFixKind,
    LintIssue,
    LintSeverity,
)
from llm_wiki.wiki.frontmatter import parse_page, validate_frontmatter
from llm_wiki.wiki.wiki_manager import (
    build_title_index,
    find_wikilinks,
    iter_content_pages,
    resolve_wikilink,
    title_to_slug,
)

ORPHAN_EXCLUDE_PREFIXES = ("summaries/",)


def _issue_id(*parts: str) -> str:
    slug = ":".join(parts)
    slug = re.sub(r"[^a-zA-Z0-9:_-]+", "-", slug.lower())
    return slug.strip("-")


def _iter_link_bodies(wiki_root: Path) -> list[tuple[str, str]]:
    """Return (source_rel_path, text) for index.md and all content pages."""
    sources: list[tuple[str, str]] = []
    index_path = wiki_root / "index.md"
    if index_path.is_file():
        sources.append(("index.md", index_path.read_text(encoding="utf-8")))

    for page_path in iter_content_pages(wiki_root):
        rel = page_path.relative_to(wiki_root).as_posix()
        try:
            _, body = parse_page(page_path)
        except Exception:
            body = page_path.read_text(encoding="utf-8")
        sources.append((rel, body))
    return sources


def _collect_link_refs(wiki_root: Path) -> list[tuple[str, str, str | None]]:
    """Return (source_rel, target, resolved_rel_or_none) for each unique wikilink."""
    title_index = build_title_index(wiki_root)
    seen: set[tuple[str, str]] = set()
    refs: list[tuple[str, str, str | None]] = []

    for source_rel, body in _iter_link_bodies(wiki_root):
        for target in find_wikilinks(body):
            key = (source_rel, target.strip())
            if key in seen:
                continue
            seen.add(key)
            resolved = resolve_wikilink(wiki_root, target, title_index)
            resolved_rel = resolved.relative_to(wiki_root).as_posix() if resolved else None
            refs.append((source_rel, target.strip(), resolved_rel))
    return refs


def _build_inbound_map(
    link_refs: list[tuple[str, str, str | None]],
) -> dict[str, set[str]]:
    inbound: dict[str, set[str]] = defaultdict(set)
    for source_rel, _target, resolved_rel in link_refs:
        if resolved_rel:
            inbound[resolved_rel].add(source_rel)
    return inbound


def check_broken_links(wiki_root: Path) -> list[LintIssue]:
    issues: list[LintIssue] = []
    for source_rel, target, resolved_rel in _collect_link_refs(wiki_root):
        if resolved_rel is not None:
            continue
        issues.append(
            LintIssue(
                id=_issue_id("broken-link", source_rel, target),
                severity=LintSeverity.WARNING,
                check_type=LintCheckType.BROKEN_LINK,
                pages=(source_rel,),
                target=target,
                description=(
                    f"`{source_rel}` links to [[{target}]], but no matching wiki page exists."
                ),
                suggested_action=(
                    f"Create a stub page for [[{target}]], or remove/replace the link in `{source_rel}`."
                ),
                auto_fixable=True,
                fix_kind=LintFixKind.CREATE_STUB,
            )
        )
    return issues


def check_missing_pages(wiki_root: Path) -> list[LintIssue]:
    """One issue per unresolved wikilink target, listing all referrers."""
    by_target: dict[str, tuple[str, set[str]]] = {}
    for source_rel, target, resolved_rel in _collect_link_refs(wiki_root):
        if resolved_rel is not None:
            continue
        key = target.lower()
        if key not in by_target:
            by_target[key] = (target, set())
        by_target[key][1].add(source_rel)

    issues: list[LintIssue] = []
    for key in sorted(by_target):
        display_target, referrers = by_target[key]
        referrer_list = tuple(sorted(referrers))
        issues.append(
            LintIssue(
                id=_issue_id("missing-page", display_target),
                severity=LintSeverity.WARNING,
                check_type=LintCheckType.MISSING_PAGE,
                pages=referrer_list,
                target=display_target,
                description=(
                    f"[[{display_target}]] is referenced from {len(referrer_list)} page(s) "
                    "but has no dedicated wiki page."
                ),
                suggested_action=(
                    f"Create a stub page for [[{display_target}]] "
                    f"(e.g. `{_suggest_stub_path(display_target)}`)."
                ),
                auto_fixable=True,
                fix_kind=LintFixKind.CREATE_STUB,
            )
        )
    return issues


def _suggest_stub_path(title: str) -> str:
    slug = title_to_slug(title)
    return f"entities/{slug}.md" if slug else "entities/<slug>.md"


def check_orphan_pages(wiki_root: Path) -> list[LintIssue]:
    link_refs = _collect_link_refs(wiki_root)
    inbound = _build_inbound_map(link_refs)
    issues: list[LintIssue] = []

    for page_path in iter_content_pages(wiki_root):
        rel = page_path.relative_to(wiki_root).as_posix()
        if rel.startswith(ORPHAN_EXCLUDE_PREFIXES):
            continue
        if inbound.get(rel):
            continue
        issues.append(
            LintIssue(
                id=_issue_id("orphan", rel),
                severity=LintSeverity.WARNING,
                check_type=LintCheckType.ORPHAN,
                pages=(rel,),
                description=f"`{rel}` has no inbound wikilinks from other wiki pages or index.md.",
                suggested_action=(
                    f"Add a wikilink to [[{_page_title(page_path)}]] from a related page or index.md."
                ),
                auto_fixable=True,
                fix_kind=LintFixKind.ADD_BACKLINK,
            )
        )
    return issues


def _page_title(page_path: Path) -> str:
    try:
        meta, _ = parse_page(page_path)
        title = meta.get("title")
        if isinstance(title, str) and title.strip():
            return title.strip()
    except Exception:
        pass
    return page_path.stem.replace("-", " ").title()


def check_invalid_frontmatter(wiki_root: Path) -> list[LintIssue]:
    issues: list[LintIssue] = []
    for page_path in iter_content_pages(wiki_root):
        rel = page_path.relative_to(wiki_root).as_posix()
        try:
            meta, _ = parse_page(page_path)
        except Exception as exc:
            issues.append(
                LintIssue(
                    id=_issue_id("invalid-frontmatter", rel, "parse"),
                    severity=LintSeverity.WARNING,
                    check_type=LintCheckType.INVALID_FRONTMATTER,
                    pages=(rel,),
                    description=f"`{rel}` could not be parsed: {exc}",
                    suggested_action="Fix YAML frontmatter so the page can be read.",
                    auto_fixable=False,
                    fix_kind=LintFixKind.NONE,
                )
            )
            continue

        errors = validate_frontmatter(meta)
        if not errors:
            continue
        issues.append(
            LintIssue(
                id=_issue_id("invalid-frontmatter", rel),
                severity=LintSeverity.WARNING,
                check_type=LintCheckType.INVALID_FRONTMATTER,
                pages=(rel,),
                description=f"`{rel}` has invalid frontmatter: {'; '.join(errors)}",
                suggested_action="Add or correct required frontmatter fields (title, type, dates, tags, sources).",
                auto_fixable=False,
                fix_kind=LintFixKind.NONE,
            )
        )
    return issues


def run_structural_checks(wiki_root: Path | str) -> list[LintIssue]:
    """Run all deterministic lint checks and return combined issues."""
    wiki_root = Path(wiki_root).resolve()
    issues: list[LintIssue] = []
    issues.extend(check_invalid_frontmatter(wiki_root))
    issues.extend(check_broken_links(wiki_root))
    issues.extend(check_missing_pages(wiki_root))
    issues.extend(check_orphan_pages(wiki_root))
    return issues
