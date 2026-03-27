#!/usr/bin/env python3
"""db_status.py — Quick diagnostics for the DevG registry database.

Usage:
    python scripts/db_status.py [--db PATH] [--check CHECKS...]

Checks (default: all):
    rows        Total row counts per table
    dupes       Duplicate detection in excerpt_catalog
    sources     Source breakdown in excerpt_catalog
    experiments Recent autoresearch experiment summary
    catalog     Resource catalog stats

Example:
    python scripts/db_status.py
    python scripts/db_status.py --check rows dupes
    python scripts/db_status.py --db data/devg_registry.sqlite3 --check rows
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path


def _connect(db_path: str) -> sqlite3.Connection:
    path = Path(db_path)
    if not path.exists():
        print(f"ERROR: database not found at {path}", file=sys.stderr)
        sys.exit(1)
    return sqlite3.connect(str(path), check_same_thread=False)


def check_rows(conn: sqlite3.Connection) -> None:
    print("=== Row Counts ===")
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()]
    for table in tables:
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  {table}: {count:,}")
        except Exception as exc:
            print(f"  {table}: ERROR ({exc})")
    print()


def check_dupes(conn: sqlite3.Connection) -> None:
    print("=== Excerpt Catalog Duplicates ===")
    try:
        total = conn.execute("SELECT COUNT(*) FROM excerpt_catalog").fetchone()[0]
        # Duplicate = same (source_title, passage_reference, text) triple
        dupe_groups = conn.execute("""
            SELECT COUNT(*) FROM (
                SELECT source_title, passage_reference
                FROM excerpt_catalog
                GROUP BY source_title, passage_reference
                HAVING COUNT(*) > 1
            )
        """).fetchone()[0]
        unique_pairs = conn.execute("""
            SELECT COUNT(DISTINCT source_title || '||' || passage_reference)
            FROM excerpt_catalog
        """).fetchone()[0]
        excess = total - unique_pairs
        print(f"  Total rows:          {total:,}")
        print(f"  Unique (title+ref):  {unique_pairs:,}")
        print(f"  Duplicate groups:    {dupe_groups:,}")
        print(f"  Excess rows:         {excess:,}")
        if dupe_groups > 0:
            print("\n  Top duplicate groups:")
            rows = conn.execute("""
                SELECT source_title, passage_reference, COUNT(*) as cnt
                FROM excerpt_catalog
                GROUP BY source_title, passage_reference
                HAVING cnt > 1
                ORDER BY cnt DESC
                LIMIT 5
            """).fetchall()
            for title, ref, cnt in rows:
                print(f"    [{cnt}x] {title[:40]} | {ref}")
    except Exception as exc:
        print(f"  ERROR: {exc}")
    print()


def check_sources(conn: sqlite3.Connection) -> None:
    print("=== Excerpt Sources ===")
    try:
        rows = conn.execute("""
            SELECT source_title, author, COUNT(*) as cnt
            FROM excerpt_catalog
            GROUP BY source_title, author
            ORDER BY cnt DESC
            LIMIT 20
        """).fetchall()
        for title, author, cnt in rows:
            print(f"  {cnt:5,}  {title[:45]} ({author or 'unknown'})")
    except Exception as exc:
        print(f"  ERROR: {exc}")
    print()


def check_experiments(conn: sqlite3.Connection) -> None:
    print("=== Recent Experiments (last 20) ===")
    try:
        rows = conn.execute("""
            SELECT worker_name, benchmark_name, status, created_at_utc
            FROM autoresearch_experiments
            ORDER BY created_at_utc DESC
            LIMIT 20
        """).fetchall()
        for worker, bench, status, ts in rows:
            print(f"  [{status:8}] {worker:20} {bench[:35]} @ {ts}")
        total = conn.execute("SELECT COUNT(*) FROM autoresearch_experiments").fetchone()[0]
        print(f"  ... {total:,} total experiments")
    except Exception as exc:
        print(f"  ERROR: {exc}")
    print()


def check_catalog(conn: sqlite3.Connection) -> None:
    print("=== Resource Catalog ===")
    try:
        total = conn.execute("SELECT COUNT(*) FROM resource_catalog").fetchone()[0]
        by_status = conn.execute("""
            SELECT status, COUNT(*) FROM resource_catalog GROUP BY status ORDER BY 2 DESC
        """).fetchall()
        print(f"  Total resources: {total:,}")
        for status, cnt in by_status:
            print(f"    {status}: {cnt:,}")
    except Exception as exc:
        print(f"  ERROR: {exc}")
    print()


ALL_CHECKS = {
    "rows": check_rows,
    "dupes": check_dupes,
    "sources": check_sources,
    "experiments": check_experiments,
    "catalog": check_catalog,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="DevG DB diagnostics")
    parser.add_argument("--db", default="registry.db", help="Path to SQLite DB")
    parser.add_argument(
        "--check", nargs="*", choices=list(ALL_CHECKS), default=list(ALL_CHECKS),
        help="Which checks to run (default: all)"
    )
    args = parser.parse_args()

    conn = _connect(args.db)
    for check_name in args.check:
        ALL_CHECKS[check_name](conn)
    conn.close()


if __name__ == "__main__":
    main()
