"""YAML frontmatter template and helpers for wiki pages (Phase 1, Step 1 substep 3)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import frontmatter

REQUIRED_FIELDS = ("title", "type", "created", "updated", "tags", "sources")
PAGE_TYPES = ("entity", "concept", "summary", "overview")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class FrontmatterValidationError(ValueError):
    """Raised when wiki page frontmatter fails validation."""


@dataclass(frozen=True)
class FrontmatterConfig:
    required_fields: tuple[str, ...] = REQUIRED_FIELDS
    allowed_types: tuple[str, ...] = PAGE_TYPES


DEFAULT_FRONTMATTER_CONFIG = FrontmatterConfig()


def today_str() -> str:
    return date.today().isoformat()


def new_frontmatter(
    title: str,
    page_type: str,
    *,
    tags: list[str] | None = None,
    sources: list[str] | None = None,
    created: str | None = None,
    updated: str | None = None,
) -> dict[str, Any]:
    """Build a frontmatter dict for a new wiki page.

    ``created`` and ``updated`` default to today's date (YYYY-MM-DD) when omitted.
    """
    return {
        "title": title.strip(),
        "type": page_type.strip(),
        "created": created or today_str(),
        "updated": updated or today_str(),
        "tags": list(tags or []),
        "sources": list(sources or []),
    }


def touch_updated(meta: dict[str, Any], *, when: str | None = None) -> dict[str, Any]:
    """Return a copy of *meta* with ``updated`` set to today (or *when*)."""
    updated = dict(meta)
    updated["updated"] = when or today_str()
    return updated


def validate_frontmatter(
    meta: dict[str, Any],
    config: FrontmatterConfig = DEFAULT_FRONTMATTER_CONFIG,
) -> list[str]:
    """Return a list of validation error messages (empty if valid)."""
    errors: list[str] = []

    for field in config.required_fields:
        if field not in meta:
            errors.append(f"Missing required field: {field}")

    page_type = meta.get("type")
    if page_type is not None and page_type not in config.allowed_types:
        errors.append(
            f"Invalid type {page_type!r}; must be one of: {', '.join(config.allowed_types)}"
        )

    title = meta.get("title")
    if title is not None and (not isinstance(title, str) or not title.strip()):
        errors.append("title must be a non-empty string")

    for date_field in ("created", "updated"):
        value = meta.get(date_field)
        if value is None:
            continue
        if not isinstance(value, str) or not DATE_PATTERN.fullmatch(value):
            errors.append(f"{date_field} must be a string in YYYY-MM-DD format")

    for list_field in ("tags", "sources"):
        value = meta.get(list_field)
        if value is None:
            continue
        if not isinstance(value, list):
            errors.append(f"{list_field} must be a list")
        elif not all(isinstance(item, str) for item in value):
            errors.append(f"{list_field} must be a list of strings")

    return errors


def assert_valid_frontmatter(
    meta: dict[str, Any],
    config: FrontmatterConfig = DEFAULT_FRONTMATTER_CONFIG,
) -> None:
    errors = validate_frontmatter(meta, config)
    if errors:
        raise FrontmatterValidationError("; ".join(errors))


def render_page(meta: dict[str, Any], body: str) -> str:
    """Serialize frontmatter and body into a markdown wiki page string."""
    post = frontmatter.Post(body, **meta)
    text = frontmatter.dumps(post)
    if not text.endswith("\n"):
        text += "\n"
    return text


def parse_page(path: Path | str) -> tuple[dict[str, Any], str]:
    """Read a wiki page and return (metadata, body)."""
    path = Path(path)
    post = frontmatter.load(path)
    return dict(post.metadata), post.content


def write_page(
    path: Path | str,
    meta: dict[str, Any],
    body: str,
    *,
    config: FrontmatterConfig = DEFAULT_FRONTMATTER_CONFIG,
) -> Path:
    """Validate and write a wiki page to disk."""
    assert_valid_frontmatter(meta, config)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_page(meta, body), encoding="utf-8")
    return path
