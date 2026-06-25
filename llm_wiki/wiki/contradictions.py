"""Shared helpers for recording contradictions on wiki pages."""

from __future__ import annotations


def append_contradiction(body: str, note: str, source_label: str) -> str:
    entry = f"- **{source_label}:** {note.strip()}"
    marker = "## Contradictions"
    if marker in body:
        return body.rstrip() + f"\n{entry}\n"
    return body.rstrip() + f"\n\n{marker}\n\n{entry}\n"
