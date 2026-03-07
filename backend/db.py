"""PostgreSQL connection pool and query helpers."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from typing import Any

import psycopg2
from psycopg2 import pool as pg_pool
from psycopg2.extras import RealDictCursor

_pool: pg_pool.SimpleConnectionPool | None = None


def _get_pool() -> pg_pool.SimpleConnectionPool:
    global _pool
    if _pool is None:
        url = os.environ.get("DATABASE_URL")
        if not url:
            raise RuntimeError("DATABASE_URL environment variable is not set")
        _pool = pg_pool.SimpleConnectionPool(minconn=1, maxconn=10, dsn=url)
    return _pool


@contextmanager
def get_conn():
    """Context manager: borrow a connection from the pool, return on exit."""
    p = _get_pool()
    conn = p.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        p.putconn(conn)


def execute(sql: str, params: tuple = ()) -> None:
    """Execute a statement that returns no rows."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)


def fetchone(sql: str, params: tuple = ()) -> dict[str, Any] | None:
    """Execute and return the first row as a dict, or None."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            return dict(row) if row else None


def fetchall(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    """Execute and return all rows as a list of dicts."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]


def fetchone_with_return(sql: str, params: tuple = ()) -> dict[str, Any] | None:
    """Execute a statement with RETURNING and return the first row."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            return dict(row) if row else None
