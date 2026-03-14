#!/usr/bin/env python3
"""Run all SQL migrations from backend/migrations in order.
Uses DATABASE_URL from environment (load .env if python-dotenv is available).
Creates tables/indexes only if not present (migrations use IF NOT EXISTS).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Load .env from repo root if available
try:
    from dotenv import load_dotenv
    repo_root = Path(__file__).resolve().parent.parent
    load_dotenv(repo_root / ".env")
except ImportError:
    pass

import psycopg2


def main() -> int:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL is not set.", file=sys.stderr)
        return 1

    migrations_dir = Path(__file__).resolve().parent / "migrations"
    files = sorted(migrations_dir.glob("*.sql"))
    if not files:
        print("No .sql files in backend/migrations.", file=sys.stderr)
        return 1

    conn = psycopg2.connect(url)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            for f in files:
                print(f"Running {f.name}...")
                sql = f.read_text()
                cur.execute(sql)
                print(f"  OK: {f.name}")
    except Exception as e:
        print(f"Migration failed: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()

    print("All migrations completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
