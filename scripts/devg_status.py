#!/usr/bin/env python3
"""devg_status.py — Single-call system health summary for DevG.

Usage:
    python scripts/devg_status.py [--db PATH] [--worker WORKER] [--n N]

Shows:
  - Per-worker score trends (last N experiments)
  - Score summary table with pass/revise/fail counts
  - Library stats (sources, excerpts)
  - DB health (table counts, lock detection)

Example:
    python scripts/devg_status.py
    python scripts/devg_status.py --worker exposition --n 20
    python scripts/devg_status.py --db registry.db
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


_WORKERS = [
    "exposition",
    "prayer_writer",
    "action_writer",
    "be_still",
    "outliner",
    "research_librarian",
    "library_trainer",
]

_SCORE_GATE = 80  # >= pass, >= 60 revise, < 60 fail


def _connect(db_path: str) -> sqlite3.Connection | None:
    path = Path(db_path)
    if not path.exists():
        print(f"  DB not found: {path}", file=sys.stderr)
        return None
    try:
        conn = sqlite3.connect(str(path), check_same_thread=False)
        # Probe connectivity
        conn.execute("SELECT 1").fetchone()
        return conn
    except Exception as exc:
        print(f"  DB connect error: {exc}", file=sys.stderr)
        return None


def _score_bar(score: int | None, width: int = 20) -> str:
    if score is None:
        return "?" * width
    filled = int(round((score / 100) * width))
    bar = "#" * filled + "-" * (width - filled)
    return f"[{bar}] {score:3d}"


def _trend_arrow(scores: list[int]) -> str:
    if len(scores) < 2:
        return " "
    delta = scores[0] - scores[-1]  # most recent first
    if delta <= -5:
        return "↑"
    if delta >= 5:
        return "↓"
    return "→"


def show_scores(conn: sqlite3.Connection, worker: str | None, n: int) -> None:
    print("=== Worker Score Summary ===")
    workers = [worker] if worker else _WORKERS
    for w in workers:
        try:
            rows = conn.execute(
                """
                SELECT status, metrics, created_at_utc
                FROM autoresearch_experiments
                WHERE worker_name = ?
                  AND metrics IS NOT NULL
                  AND metrics != '{}'
                ORDER BY created_at_utc DESC
                LIMIT ?
                """,
                (w, n),
            ).fetchall()
        except Exception as exc:
            print(f"  {w}: ERROR ({exc})")
            continue

        if not rows:
            print(f"  {w:25s}  no experiments")
            continue

        scores: list[int] = []
        statuses: dict[str, int] = {"pass": 0, "revise": 0, "fail": 0, "blocked": 0}
        for status, metrics_json, ts in rows:
            statuses[status] = statuses.get(status, 0) + 1
            try:
                m = json.loads(metrics_json) if metrics_json else {}
                s = m.get("score") or m.get("fresh_benchmark_score")
                if s is not None:
                    scores.append(int(s))
            except Exception:
                pass

        latest_score = scores[0] if scores else None
        bar = _score_bar(latest_score)
        trend = _trend_arrow(scores)
        counts = f"P:{statuses['pass']} R:{statuses['revise']} F:{statuses['fail']} B:{statuses.get('blocked', 0)}"
        print(f"  {w:25s}  {bar}  {trend}  ({counts} of last {len(rows)})")
        if scores and len(scores) > 1:
            recent = scores[:5]
            print(f"    Last 5 scores: {recent}")
    print()


def show_library(conn: sqlite3.Connection) -> None:
    print("=== Library ===")
    try:
        excerpt_count = conn.execute("SELECT COUNT(*) FROM excerpt_catalog").fetchone()[0]
        source_count = conn.execute(
            "SELECT COUNT(DISTINCT source_title) FROM excerpt_catalog"
        ).fetchone()[0]
        print(f"  Excerpts: {excerpt_count:,}")
        print(f"  Sources:  {source_count:,}")
    except Exception as exc:
        print(f"  ERROR: {exc}")
    try:
        res_count = conn.execute("SELECT COUNT(*) FROM resource_catalog").fetchone()[0]
        by_status = conn.execute(
            "SELECT status, COUNT(*) FROM resource_catalog GROUP BY status ORDER BY 2 DESC"
        ).fetchall()
        print(f"  Resources: {res_count:,}")
        for s, c in by_status:
            print(f"    {s}: {c:,}")
    except Exception as exc:
        print(f"  Resources: ERROR ({exc})")
    print()


def show_experiments_total(conn: sqlite3.Connection) -> None:
    print("=== Experiment Store ===")
    try:
        total = conn.execute("SELECT COUNT(*) FROM autoresearch_experiments").fetchone()[0]
        latest = conn.execute(
            "SELECT worker_name, status, created_at_utc FROM autoresearch_experiments ORDER BY created_at_utc DESC LIMIT 3"
        ).fetchall()
        print(f"  Total experiments: {total:,}")
        print("  Latest:")
        for w, s, ts in latest:
            print(f"    [{s:8}] {w:25s} @ {ts}")
    except Exception as exc:
        print(f"  ERROR: {exc}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="DevG system health summary")
    parser.add_argument("--db", default="registry.db", help="Path to SQLite DB")
    parser.add_argument("--worker", default=None, help="Filter to one worker")
    parser.add_argument("--n", type=int, default=30, help="Last N experiments per worker")
    args = parser.parse_args()

    conn = _connect(args.db)
    if conn is None:
        sys.exit(1)

    show_scores(conn, args.worker, args.n)
    show_library(conn)
    show_experiments_total(conn)
    conn.close()


if __name__ == "__main__":
    main()
