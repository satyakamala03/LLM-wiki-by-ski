"""Oracle wiki_projects registry (Phase 6)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from llm_wiki.db.connection import oracle_connection
from llm_wiki.projects.stats import ProjectStats, collect_disk_stats


@dataclass(frozen=True)
class ProjectRecord:
    name: str
    wiki_path: str
    created_at: datetime | None
    last_ingestion: datetime | None
    last_query: datetime | None
    page_count: int
    source_count: int
    embedding_count: int
    updated_at: datetime | None
    on_disk: bool = True
    in_oracle: bool = True


def _row_to_record(row: tuple, *, on_disk: bool = True) -> ProjectRecord:
    return ProjectRecord(
        name=str(row[0]),
        wiki_path=str(row[1] or ""),
        created_at=row[2],
        last_ingestion=row[3],
        last_query=row[4],
        page_count=int(row[5] or 0),
        source_count=int(row[6] or 0),
        embedding_count=int(row[7] or 0),
        updated_at=row[8],
        on_disk=on_disk,
        in_oracle=True,
    )


def register_project(project_name: str, wiki_root: Path | str) -> None:
    """Insert project row if missing."""
    wiki_root = Path(wiki_root).resolve()
    stats = collect_disk_stats(project_name, wiki_root)
    now = datetime.now()

    with oracle_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                MERGE INTO wiki_projects dst
                USING (SELECT :name AS name FROM dual) src
                ON (dst.name = src.name)
                WHEN NOT MATCHED THEN INSERT (
                    name, wiki_path, created_at, last_ingestion, last_query,
                    page_count, source_count, embedding_count, updated_at
                ) VALUES (
                    :name, :wiki_path, :created_at, :last_ingestion, :last_query,
                    :page_count, :source_count, :embedding_count, :updated_at
                )
                """,
                {
                    "name": project_name,
                    "wiki_path": str(wiki_root),
                    "created_at": now,
                    "last_ingestion": stats.last_ingestion,
                    "last_query": stats.last_query,
                    "page_count": stats.page_count,
                    "source_count": stats.source_count,
                    "embedding_count": stats.embedding_count,
                    "updated_at": now,
                },
            )


def sync_project_metadata(
    project_name: str,
    wiki_root: Path | str,
    *,
    last_ingestion: datetime | None = None,
    last_query: datetime | None = None,
) -> ProjectRecord:
    """Upsert project metadata from disk + Oracle embedding counts."""
    wiki_root = Path(wiki_root).resolve()
    stats = collect_disk_stats(project_name, wiki_root)
    now = datetime.now()

    ingestion_ts = last_ingestion if last_ingestion is not None else stats.last_ingestion
    query_ts = last_query if last_query is not None else stats.last_query

    with oracle_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                MERGE INTO wiki_projects dst
                USING (SELECT :name AS name FROM dual) src
                ON (dst.name = src.name)
                WHEN MATCHED THEN UPDATE SET
                    wiki_path = :wiki_path,
                    last_ingestion = :last_ingestion,
                    last_query = :last_query,
                    page_count = :page_count,
                    source_count = :source_count,
                    embedding_count = :embedding_count,
                    updated_at = :updated_at
                WHEN NOT MATCHED THEN INSERT (
                    name, wiki_path, created_at, last_ingestion, last_query,
                    page_count, source_count, embedding_count, updated_at
                ) VALUES (
                    :name, :wiki_path, :created_at, :last_ingestion, :last_query,
                    :page_count, :source_count, :embedding_count, :updated_at
                )
                """,
                {
                    "name": project_name,
                    "wiki_path": str(wiki_root),
                    "created_at": now,
                    "last_ingestion": ingestion_ts,
                    "last_query": query_ts,
                    "page_count": stats.page_count,
                    "source_count": stats.source_count,
                    "embedding_count": stats.embedding_count,
                    "updated_at": now,
                },
            )

    return get_project(project_name) or ProjectRecord(
        name=project_name,
        wiki_path=str(wiki_root),
        created_at=now,
        last_ingestion=ingestion_ts,
        last_query=query_ts,
        page_count=stats.page_count,
        source_count=stats.source_count,
        embedding_count=stats.embedding_count,
        updated_at=now,
    )


def get_project(project_name: str) -> ProjectRecord | None:
    with oracle_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT name, wiki_path, created_at, last_ingestion, last_query,
                       page_count, source_count, embedding_count, updated_at
                FROM wiki_projects
                WHERE name = :name
                """,
                {"name": project_name},
            )
            row = cursor.fetchone()
    if not row:
        return None
    return _row_to_record(row)


def list_oracle_projects() -> list[ProjectRecord]:
    with oracle_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT name, wiki_path, created_at, last_ingestion, last_query,
                       page_count, source_count, embedding_count, updated_at
                FROM wiki_projects
                ORDER BY name
                """
            )
            rows = cursor.fetchall()
    return [_row_to_record(row) for row in rows]


def list_all_projects(wikis_dir: Path | str) -> list[ProjectRecord]:
    """Merge disk wikis with Oracle registry rows."""
    from llm_wiki.wiki.wiki_manager import list_wikis

    wikis_dir = Path(wikis_dir).resolve()
    disk_by_name = {path.name: path for path in list_wikis(wikis_dir)}

    try:
        oracle_rows = {row.name: row for row in list_oracle_projects()}
    except Exception:
        oracle_rows = {}

    names = sorted(set(disk_by_name) | set(oracle_rows))
    merged: list[ProjectRecord] = []

    for name in names:
        disk_path = disk_by_name.get(name)
        oracle_row = oracle_rows.get(name)

        if oracle_row and disk_path:
            merged.append(
                ProjectRecord(
                    name=oracle_row.name,
                    wiki_path=str(disk_path),
                    created_at=oracle_row.created_at,
                    last_ingestion=oracle_row.last_ingestion,
                    last_query=oracle_row.last_query,
                    page_count=oracle_row.page_count,
                    source_count=oracle_row.source_count,
                    embedding_count=oracle_row.embedding_count,
                    updated_at=oracle_row.updated_at,
                    on_disk=True,
                    in_oracle=True,
                )
            )
        elif disk_path:
            stats = collect_disk_stats(name, disk_path)
            merged.append(
                ProjectRecord(
                    name=name,
                    wiki_path=str(disk_path),
                    created_at=None,
                    last_ingestion=stats.last_ingestion,
                    last_query=stats.last_query,
                    page_count=stats.page_count,
                    source_count=stats.source_count,
                    embedding_count=stats.embedding_count,
                    updated_at=None,
                    on_disk=True,
                    in_oracle=False,
                )
            )
        elif oracle_row:
            merged.append(
                ProjectRecord(
                    name=oracle_row.name,
                    wiki_path=oracle_row.wiki_path,
                    created_at=oracle_row.created_at,
                    last_ingestion=oracle_row.last_ingestion,
                    last_query=oracle_row.last_query,
                    page_count=oracle_row.page_count,
                    source_count=oracle_row.source_count,
                    embedding_count=oracle_row.embedding_count,
                    updated_at=oracle_row.updated_at,
                    on_disk=False,
                    in_oracle=True,
                )
            )

    return merged


def try_sync_project(
    project_name: str,
    wiki_root: Path | str,
    *,
    last_ingestion: datetime | None = None,
    last_query: datetime | None = None,
) -> str | None:
    """Sync metadata; return error message on failure (non-fatal helper)."""
    try:
        sync_project_metadata(
            project_name,
            wiki_root,
            last_ingestion=last_ingestion,
            last_query=last_query,
        )
        return None
    except Exception as exc:
        return str(exc)
