"""Oracle connection helpers (Phase 4)."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import oracledb
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent.parent / "config" / ".env"


def _load_config() -> tuple[str, str, str]:
    load_dotenv(ENV_PATH)
    user = os.getenv("ORACLE_USER", "").strip()
    password = os.getenv("ORACLE_PASSWORD", "").strip()
    dsn = os.getenv("ORACLE_DSN", "").strip()
    if not user or not password or not dsn:
        raise ValueError(
            "Oracle credentials missing. Set ORACLE_USER, ORACLE_PASSWORD, and ORACLE_DSN in llm_wiki/config/.env"
        )
    return user, password, dsn


def get_connection() -> oracledb.Connection:
    user, password, dsn = _load_config()
    return oracledb.connect(user=user, password=password, dsn=dsn)


@contextmanager
def oracle_connection() -> Iterator[oracledb.Connection]:
    connection = get_connection()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def ping_oracle() -> str:
    with oracle_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 'ok' FROM DUAL")
            row = cursor.fetchone()
    return str(row[0]) if row else "ok"
