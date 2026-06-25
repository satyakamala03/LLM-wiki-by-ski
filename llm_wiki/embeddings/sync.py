"""Sync wiki pages to Oracle embeddings table."""

from __future__ import annotations

import array
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from llm_wiki.db.connection import oracle_connection
from llm_wiki.embeddings.model import embed_text
from llm_wiki.embeddings.text import PageRecord, page_to_record
from llm_wiki.wiki.wiki_manager import iter_content_pages


@dataclass
class SyncStats:
    embedded: int = 0
    skipped: int = 0
    deleted: int = 0
    errors: list[str] | None = None

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []


def _existing_hash(connection, project_name: str, page_path: str) -> str | None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT content_hash
            FROM wiki_pages
            WHERE project_name = :project_name AND page_path = :page_path
            """,
            {"project_name": project_name, "page_path": page_path},
        )
        row = cursor.fetchone()
    if not row or row[0] is None:
        return None
    return str(row[0])


def _upsert_record(connection, record: PageRecord, embedding: list[float]) -> None:
    vector = array.array("f", embedding)
    updated_at = record.updated_at or datetime.now()

    with connection.cursor() as cursor:
        cursor.execute(
            """
            MERGE INTO wiki_pages dst
            USING (
                SELECT :project_name AS project_name, :page_path AS page_path FROM dual
            ) src
            ON (dst.project_name = src.project_name AND dst.page_path = src.page_path)
            WHEN MATCHED THEN UPDATE SET
                title = :title,
                page_type = :page_type,
                tags = :tags,
                embed_text = :embed_text,
                search_text = :search_text,
                embedding = :embedding,
                content_hash = :content_hash,
                updated_at = :updated_at
            WHEN NOT MATCHED THEN INSERT (
                project_name, page_path, title, page_type, tags,
                embed_text, search_text, embedding, content_hash, updated_at
            ) VALUES (
                :project_name, :page_path, :title, :page_type, :tags,
                :embed_text, :search_text, :embedding, :content_hash, :updated_at
            )
            """,
            {
                "project_name": record.project_name,
                "page_path": record.page_path,
                "title": record.title[:200],
                "page_type": record.page_type[:50],
                "tags": record.tags[:500],
                "embed_text": record.embed_text,
                "search_text": record.search_text,
                "embedding": vector,
                "content_hash": record.content_hash,
                "updated_at": updated_at,
            },
        )


def sync_page_paths(
    project_name: str,
    wiki_root: Path | str,
    page_paths: list[str],
    *,
    force: bool = False,
) -> SyncStats:
    """Upsert embeddings for specific wiki pages (incremental ingest sync)."""
    wiki_root = Path(wiki_root).resolve()
    stats = SyncStats()

    if not page_paths:
        return stats

    with oracle_connection() as connection:
        for rel_path in page_paths:
            page_file = wiki_root / rel_path
            if not page_file.is_file():
                stats.errors.append(f"missing page: {rel_path}")
                continue
            try:
                record = page_to_record(project_name, wiki_root, page_file)
                if not force:
                    existing = _existing_hash(connection, project_name, record.page_path)
                    if existing == record.content_hash:
                        stats.skipped += 1
                        continue
                embedding = embed_text(record.embed_text)
                _upsert_record(connection, record, embedding)
                stats.embedded += 1
            except Exception as exc:
                stats.errors.append(f"{rel_path}: {exc}")

    return stats


def sync_wiki(
    project_name: str,
    wiki_root: Path | str,
    *,
    force: bool = False,
    prune: bool = False,
) -> SyncStats:
    """Embed all content pages under a wiki; optionally remove stale Oracle rows."""
    wiki_root = Path(wiki_root).resolve()
    page_paths = [p.relative_to(wiki_root).as_posix() for p in iter_content_pages(wiki_root)]
    stats = sync_page_paths(project_name, wiki_root, page_paths, force=force)

    if prune:
        disk_paths = set(page_paths)
        with oracle_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT page_path FROM wiki_pages WHERE project_name = :project_name
                    """,
                    {"project_name": project_name},
                )
                db_paths = {str(row[0]) for row in cursor.fetchall()}

            stale = db_paths - disk_paths
            if stale:
                with connection.cursor() as cursor:
                    for page_path in stale:
                        cursor.execute(
                            """
                            DELETE FROM wiki_pages
                            WHERE project_name = :project_name AND page_path = :page_path
                            """,
                            {"project_name": project_name, "page_path": page_path},
                        )
                stats.deleted = len(stale)

    return stats


def count_project_pages(project_name: str) -> int:
    with oracle_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM wiki_pages WHERE project_name = :project_name",
                {"project_name": project_name},
            )
            row = cursor.fetchone()
    return int(row[0]) if row else 0
