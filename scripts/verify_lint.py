#!/usr/bin/env python3
"""Phase 7.5 verification: lint checks on controlled wikis/lint-test fixtures."""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from llm_wiki.lint import run_lint, run_structural_checks
from llm_wiki.lint.fixes import apply_fix, finalize_wiki_changes
from llm_wiki.lint.state import LintCheckType, LintFixKind
from llm_wiki.wiki.frontmatter import new_frontmatter, parse_page, write_page
from llm_wiki.wiki.wiki_manager import create_wiki

FIXTURE_WIKI = ROOT / "wikis" / "lint-test"

FIXTURE_PAGES: list[tuple[str, dict, str]] = [
    (
        "entities/test-alpha.md",
        new_frontmatter("Test Alpha", "entity", tags=["lint-test", "fixture"], sources=[]),
        """# Test Alpha

Test Alpha is a fictional egg substitute that **works in all cookie recipes** without exception.
Laboratory tests show a 100% success rate in chocolate chip cookies and oatmeal cookies.
""",
    ),
    (
        "entities/test-beta.md",
        new_frontmatter("Test Beta", "entity", tags=["lint-test", "fixture"], sources=[]),
        """# Test Beta

Test Beta is a fictional egg substitute that **fails in all cookie recipes** and should never be used for cookies.
Every cookie batch tested with Test Beta collapsed completely.
""",
    ),
    (
        "topics/orphan-fixture.md",
        new_frontmatter("Orphan Fixture", "concept", tags=["lint-test", "fixture"], sources=[]),
        """# Orphan Fixture

This page intentionally has no inbound wikilinks from index or other pages.
""",
    ),
    (
        "topics/linker-fixture.md",
        new_frontmatter("Linker Fixture", "overview", tags=["lint-test", "fixture"], sources=[]),
        """# Linker Fixture

See [[Ghost Page Never Created]] for background on this broken reference.
""",
    ),
    (
        "topics/overview-enzyme-gap.md",
        new_frontmatter("Overview Enzyme Gap", "overview", tags=["lint-test"], sources=[]),
        """# Overview Enzyme Gap

Eggless baking sometimes relies on enzyme kinetics to understand protein coagulation.
Enzyme kinetics also explains how alternative binders set in batter.
Several pages discuss enzyme kinetics but there is no dedicated enzyme kinetics page.
""",
    ),
]


def seed_fixture_wiki(target: Path) -> Path:
    """Create a fresh lint-test fixture tree under target (temp dir)."""
    if target.exists():
        shutil.rmtree(target)
    create_wiki(target.name, target.parent)
    for rel, meta, body in FIXTURE_PAGES:
        write_page(target / rel, meta, body)
    return target


def _types(issues) -> set[str]:
    return {issue.check_type.value for issue in issues}


def verify_structural_detection() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        wiki_root = seed_fixture_wiki(Path(tmp) / "lint-test")
        issues = run_structural_checks(wiki_root)
        found = _types(issues)

        required = {
            LintCheckType.ORPHAN.value,
            LintCheckType.BROKEN_LINK.value,
            LintCheckType.MISSING_PAGE.value,
        }
        missing = required - found
        if missing:
            raise AssertionError(f"Structural lint missing issue types: {sorted(missing)}")

        orphan = [i for i in issues if i.check_type == LintCheckType.ORPHAN]
        if not any("orphan-fixture" in p for i in orphan for p in i.pages):
            raise AssertionError("Expected orphan-fixture page in orphan issues")

        broken = [i for i in issues if i.check_type == LintCheckType.BROKEN_LINK]
        if not any(i.target and "Ghost Page" in i.target for i in broken):
            raise AssertionError("Expected broken link to Ghost Page Never Created")

    print("OK structural detection:", sorted(found))


def verify_structural_auto_fix_clears_issues() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        wiki_root = seed_fixture_wiki(Path(tmp) / "lint-test")
        before = len(run_structural_checks(wiki_root))
        if before == 0:
            raise AssertionError("Expected structural issues before auto-fix")

        from llm_wiki.lint.fixes import apply_fix

        issues = [i for i in run_structural_checks(wiki_root) if i.auto_fixable]
        pages_touched: list[str] = []
        fixed_targets: set[str] = set()
        for issue in issues:
            if issue.target and issue.target.lower() in fixed_targets:
                continue
            result = apply_fix(wiki_root, issue, schema_text="")
            if result.applied:
                pages_touched.extend(result.pages_touched)
                if issue.target and issue.fix_kind == LintFixKind.CREATE_STUB:
                    fixed_targets.add(issue.target.strip().lower())

        finalize_wiki_changes(
            wiki_root,
            "lint-test",
            pages_touched,
            issue_count=before,
            fixes_applied=len(pages_touched),
            fix_kinds=["auto"],
        )
        after = len(run_structural_checks(wiki_root))
        if after != 0:
            raise AssertionError(f"Expected 0 structural issues after fixes, got {after}")

    print("OK structural auto-fix clears fixture issues")


def verify_reject_no_disk_changes() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        copy_root = seed_fixture_wiki(Path(tmp) / "lint-test")

        before = {
            p.relative_to(copy_root).as_posix(): p.read_text(encoding="utf-8")
            for p in copy_root.rglob("*.md")
            if p.is_file() and p.name != "log.md"
        }

        result = run_lint(copy_root, checks="structural")
        finalize_wiki_changes(
            copy_root,
            "lint-test",
            [],
            issue_count=len(result.get("issues") or []),
            fixes_applied=0,
        )

        after = {
            p.relative_to(copy_root).as_posix(): p.read_text(encoding="utf-8")
            for p in copy_root.rglob("*.md")
            if p.is_file() and p.name != "log.md"
        }

        for path, content in before.items():
            if path not in after:
                raise AssertionError(f"Page removed unexpectedly: {path}")
            if content != after[path]:
                raise AssertionError(f"Page changed on reject/report-only: {path}")

        log_text = (copy_root / "log.md").read_text(encoding="utf-8")
        if "lint" not in log_text:
            raise AssertionError("Expected lint log entry after report-only run")

    print("OK reject/report-only leaves fixture pages unchanged")


def verify_llm_contradiction_detection() -> None:
    import os

    if not os.getenv("OPENAI_API_KEY"):
        print("SKIP LLM contradiction detection (OPENAI_API_KEY not set)")
        return

    with tempfile.TemporaryDirectory() as tmp:
        wiki_root = seed_fixture_wiki(Path(tmp) / "lint-test")
        result = run_lint(wiki_root, checks="llm")
        issues = list(result.get("issues") or [])
        contradictions = [i for i in issues if i.check_type == LintCheckType.CONTRADICTION]
        alpha_beta = [
            i
            for i in contradictions
            if "entities/test-alpha.md" in i.pages and "entities/test-beta.md" in i.pages
        ]
        if not alpha_beta:
            raise AssertionError("LLM did not flag test-alpha vs test-beta contradiction")

        gaps = [i for i in issues if i.check_type == LintCheckType.DATA_GAP]
        if not gaps:
            raise AssertionError("LLM did not return any data_gap suggestions")

    print("OK LLM detection: contradiction (alpha/beta) + data gaps")


def verify_accept_contradiction_fix() -> None:
    import os

    if not os.getenv("OPENAI_API_KEY"):
        print("SKIP contradiction fix (OPENAI_API_KEY not set)")
        return

    with tempfile.TemporaryDirectory() as tmp:
        copy_root = seed_fixture_wiki(Path(tmp) / "lint-test")

        result = run_lint(copy_root, checks="llm")
        issues = list(result.get("issues") or [])
        target = next(
            (
                i
                for i in issues
                if i.check_type == LintCheckType.CONTRADICTION
                and i.fix_kind == LintFixKind.APPEND_CONTRADICTION
                and "entities/test-alpha.md" in i.pages
                and "entities/test-beta.md" in i.pages
            ),
            None,
        )
        if target is None:
            raise AssertionError("Could not find alpha/beta contradiction issue for fix test")

        fix = apply_fix(copy_root, target, schema_text=str(result.get("schema_text") or ""))
        if not fix.applied:
            raise AssertionError(f"Contradiction fix not applied: {fix.message}")

        for rel in ("entities/test-alpha.md", "entities/test-beta.md"):
            _, body = parse_page(copy_root / rel)
            if "## Contradictions" not in body:
                raise AssertionError(f"Expected Contradictions section on {rel}")

    print("OK accept contradiction fix appends Contradictions sections")


def main() -> int:
    if not FIXTURE_WIKI.is_dir():
        raise SystemExit(f"Committed fixture wiki missing: {FIXTURE_WIKI}")

    verify_structural_detection()
    verify_structural_auto_fix_clears_issues()
    verify_reject_no_disk_changes()
    verify_llm_contradiction_detection()
    verify_accept_contradiction_fix()
    print("\nAll Phase 7.5 lint verifications passed.")
    return 0


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv(ROOT / "llm_wiki" / "config" / ".env")
    sys.exit(main())
