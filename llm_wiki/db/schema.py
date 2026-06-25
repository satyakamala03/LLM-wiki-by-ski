"""Oracle schema bootstrap for wiki page embeddings (Phase 4)."""

from __future__ import annotations

from llm_wiki.db.connection import oracle_connection

TABLE_NAME = "WIKI_PAGES"
PROJECTS_TABLE_NAME = "WIKI_PROJECTS"


def table_exists(connection, table_name: str = TABLE_NAME) -> bool:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM user_tables
            WHERE UPPER(table_name) = UPPER(:table_name)
            """,
            {"table_name": table_name},
        )
        row = cursor.fetchone()
    return bool(row and row[0])


def _index_exists(connection, index_name: str) -> bool:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM user_indexes
            WHERE UPPER(index_name) = UPPER(:index_name)
            """,
            {"index_name": index_name},
        )
        row = cursor.fetchone()
    return bool(row and row[0])


def _connected_user(connection) -> str:
    with connection.cursor() as cursor:
        cursor.execute("SELECT USER FROM DUAL")
        row = cursor.fetchone()
    return str(row[0]) if row and row[0] else ""


def _default_tablespace(connection) -> str | None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT default_tablespace FROM user_users")
        row = cursor.fetchone()
    return str(row[0]) if row and row[0] else None


def _ensure_vector_tablespace(connection) -> str | None:
    """Vector indexes use the owner's default tablespace; SYSTEM defaults to SYSTEM (MSSM)."""
    current = _default_tablespace(connection)
    if current and current.upper() == "USERS":
        return None

    username = _connected_user(connection)
    with connection.cursor() as cursor:
        cursor.execute(f'ALTER USER "{username}" DEFAULT TABLESPACE USERS')
    return f"set default tablespace to USERS for {username} (was {current})"


def ensure_schema(*, force_rebuild_indexes: bool = False) -> list[str]:
    """Create wiki_pages table and indexes if missing. Returns actions taken."""
    actions: list[str] = []

    with oracle_connection() as connection:
        tablespace_action = _ensure_vector_tablespace(connection)
        if tablespace_action:
            actions.append(tablespace_action)

        if not table_exists(connection):
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE wiki_pages (
                        id              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                        project_name    VARCHAR2(100) NOT NULL,
                        page_path       VARCHAR2(500) NOT NULL,
                        title           VARCHAR2(200),
                        page_type       VARCHAR2(50),
                        tags            VARCHAR2(500),
                        embed_text      CLOB,
                        search_text     CLOB,
                        embedding       VECTOR(768, FLOAT32),
                        content_hash    VARCHAR2(64),
                        updated_at      TIMESTAMP DEFAULT SYSTimestamp NOT NULL,
                        CONSTRAINT wiki_pages_uk UNIQUE (project_name, page_path)
                    ) TABLESPACE USERS
                    """
                )
            actions.append("created table wiki_pages")
        else:
            actions.append("table wiki_pages already exists")

        if force_rebuild_indexes or not _index_exists(connection, "WIKI_PAGES_VEC_IDX"):
            if _index_exists(connection, "WIKI_PAGES_VEC_IDX"):
                with connection.cursor() as cursor:
                    cursor.execute("DROP INDEX wiki_pages_vec_idx")
                actions.append("dropped index wiki_pages_vec_idx")

            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE VECTOR INDEX wiki_pages_vec_idx
                    ON wiki_pages (embedding)
                    ORGANIZATION NEIGHBOR PARTITIONS
                    DISTANCE COSINE
                    WITH TARGET ACCURACY 95
                    """
                )
            actions.append("created vector index wiki_pages_vec_idx")

        if force_rebuild_indexes or not _index_exists(connection, "WIKI_PAGES_FTS_IDX"):
            if _index_exists(connection, "WIKI_PAGES_FTS_IDX"):
                with connection.cursor() as cursor:
                    cursor.execute("DROP INDEX wiki_pages_fts_idx")
                actions.append("dropped index wiki_pages_fts_idx")

            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE INDEX wiki_pages_fts_idx
                    ON wiki_pages (search_text)
                    INDEXTYPE IS CTXSYS.CONTEXT
                    """
                )
            actions.append("created full-text index wiki_pages_fts_idx")

        if not table_exists(connection, PROJECTS_TABLE_NAME):
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE wiki_projects (
                        id                NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                        name              VARCHAR2(100) NOT NULL UNIQUE,
                        wiki_path         VARCHAR2(500),
                        created_at        TIMESTAMP DEFAULT SYSTimestamp NOT NULL,
                        last_ingestion    TIMESTAMP,
                        last_query        TIMESTAMP,
                        page_count        NUMBER DEFAULT 0,
                        source_count      NUMBER DEFAULT 0,
                        embedding_count   NUMBER DEFAULT 0,
                        updated_at        TIMESTAMP DEFAULT SYSTimestamp NOT NULL
                    ) TABLESPACE USERS
                    """
                )
            actions.append("created table wiki_projects")
        else:
            actions.append("table wiki_projects already exists")

    return actions
