"""Source file handling for ingestion."""

from __future__ import annotations

import shutil
from pathlib import Path

from llm_wiki.wiki.wiki_manager import is_wiki_root


class SourcePrepareError(RuntimeError):
    """Raised when a source file cannot be prepared for ingestion."""


def resolve_wiki_root(wikis_dir: Path | str, wiki_name: str) -> Path:
    wiki_root = (Path(wikis_dir) / wiki_name).resolve()
    if not is_wiki_root(wiki_root):
        raise FileNotFoundError(f"Wiki not found: {wiki_root}")
    return wiki_root


def prepare_source(wiki_root: Path | str, source_path: Path | str) -> Path:
    """Copy *source_path* into wiki ``raw/`` if needed and return the raw path.

    The file under ``raw/`` is never modified after copy. If the destination
    already exists, the existing raw file is reused.
    """
    wiki_root = Path(wiki_root).resolve()
    source_path = Path(source_path).resolve()

    if not source_path.is_file():
        raise SourcePrepareError(f"Source file not found: {source_path}")

    raw_dir = wiki_root / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    try:
        source_path.relative_to(raw_dir)
        return source_path
    except ValueError:
        pass

    destination = raw_dir / source_path.name
    if destination.exists():
        return destination

    shutil.copy2(source_path, destination)
    return destination


def load_schema(wiki_root: Path | str) -> str:
    schema_path = Path(wiki_root) / "SCHEMA.md"
    if not schema_path.is_file():
        raise SourcePrepareError(f"SCHEMA.md not found in wiki: {wiki_root}")
    return schema_path.read_text(encoding="utf-8")


def read_source_text(source_path: Path | str) -> str:
    return Path(source_path).read_text(encoding="utf-8")
