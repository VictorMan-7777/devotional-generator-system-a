"""run_health_check.py — Automated system health check and self-healing.

Runs at the START of every supervisor cycle. Catches accumulation problems
before they compound into multi-hour waste loops.

Actions taken automatically (no human required):
  1. Archive stuck 'assigned' experiments older than STUCK_THRESHOLD_HOURS
  2. Retire benchmark passages with zero passes after RETIRE_THRESHOLD attempts
  3. Archive all experiments for retired passages so schedulers skip them

Reports emitted (for human and policy guardian review):
  - L15 violations: consecutive failures >= L15_CAP per worker/benchmark
  - Zero-pass workers: workers with 0 passes in 50+ total experiments
  - Worker pass rates
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from src.persistence.paths import default_registry_db_path

STUCK_THRESHOLD_HOURS = 2
RETIRE_THRESHOLD = 20       # zero passes after this many attempts → retire passage
L15_CAP = 3                 # consecutive failures cap (matches federal law)
ZERO_PASS_MINIMUM = 50      # alert if worker has 0 passes after this many experiments


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _archive_stuck(conn: sqlite3.Connection) -> int:
    """Archive assigned experiments older than STUCK_THRESHOLD_HOURS."""
    result = conn.execute(
        """UPDATE autoresearch_experiments
           SET status = 'archived'
           WHERE status = 'assigned'
           AND created_at_utc < datetime('now', ?)""",
        (f"-{STUCK_THRESHOLD_HOURS} hours",),
    )
    return result.rowcount


def _retire_dead_benchmarks(conn: sqlite3.Connection) -> list[dict]:
    """Find and retire benchmark passages with zero passes after RETIRE_THRESHOLD attempts."""
    candidates = conn.execute(
        """SELECT worker_name, benchmark_reference,
                  COUNT(*) as total,
                  SUM(CASE WHEN status = 'pass' THEN 1 ELSE 0 END) as passes
           FROM autoresearch_experiments
           WHERE benchmark_reference IS NOT NULL AND benchmark_reference != ''
           AND status IN ('pass', 'fail', 'revise')
           GROUP BY worker_name, benchmark_reference
           HAVING total >= ? AND passes = 0
           ORDER BY total DESC""",
        (RETIRE_THRESHOLD,),
    ).fetchall()

    retired = []
    for worker, ref, total, passes in candidates:
        archived = conn.execute(
            """UPDATE autoresearch_experiments
               SET status = 'archived'
               WHERE worker_name = ? AND benchmark_reference = ?
               AND status IN ('assigned', 'fail', 'revise')""",
            (worker, ref),
        ).rowcount
        retired.append({
            "worker_name": worker,
            "benchmark_reference": ref,
            "total_attempts": total,
            "passes": passes,
            "archived_now": archived,
        })
    return retired


def _l15_violations(conn: sqlite3.Connection) -> list[dict]:
    """Find worker/benchmark pairs with >= L15_CAP consecutive failures (today)."""
    rows = conn.execute(
        """SELECT worker_name, benchmark_reference, COUNT(*) as consec
           FROM autoresearch_experiments
           WHERE status IN ('fail', 'revise')
           AND benchmark_reference IS NOT NULL AND benchmark_reference != ''
           AND created_at_utc > datetime('now', '-1 day')
           GROUP BY worker_name, benchmark_reference
           HAVING consec >= ?
           ORDER BY consec DESC""",
        (L15_CAP,),
    ).fetchall()
    return [
        {"worker_name": w, "benchmark_reference": r, "consecutive_failures": c}
        for w, r, c in rows
    ]


def _zero_pass_workers(conn: sqlite3.Connection) -> list[dict]:
    """Workers with 0 passes in 50+ scored experiments."""
    rows = conn.execute(
        """SELECT worker_name,
                  COUNT(*) as total,
                  SUM(CASE WHEN status = 'pass' THEN 1 ELSE 0 END) as passes
           FROM autoresearch_experiments
           WHERE status IN ('pass', 'fail', 'revise')
           GROUP BY worker_name
           HAVING total >= ? AND passes = 0""",
        (ZERO_PASS_MINIMUM,),
    ).fetchall()
    return [{"worker_name": w, "total": t, "passes": p} for w, t, p in rows]


def _worker_pass_rates(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """SELECT worker_name,
                  COUNT(*) as total,
                  SUM(CASE WHEN status = 'pass' THEN 1 ELSE 0 END) as passes
           FROM autoresearch_experiments
           WHERE status IN ('pass', 'fail', 'revise')
           GROUP BY worker_name
           ORDER BY worker_name"""
    ).fetchall()
    out = []
    for w, total, passes in rows:
        rate = round(passes / total * 100, 1) if total else 0.0
        out.append({"worker_name": w, "passes": passes, "total": total, "pass_rate_pct": rate})
    return out


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    db_path = default_registry_db_path()

    conn = sqlite3.connect(db_path)
    try:
        stuck_archived = _archive_stuck(conn)
        retired = _retire_dead_benchmarks(conn)
        l15 = _l15_violations(conn)
        zero_pass = _zero_pass_workers(conn)
        rates = _worker_pass_rates(conn)
        conn.commit()
    finally:
        conn.close()

    payload = {
        "generated_at_utc": _utc_now(),
        "auto_actions": {
            "stuck_experiments_archived": stuck_archived,
            "benchmarks_retired": len(retired),
            "retired_detail": retired,
        },
        "l15_violations": l15,
        "zero_pass_workers": zero_pass,
        "worker_pass_rates": rates,
        "summary": (
            f"Archived {stuck_archived} stuck experiments. "
            f"Retired {len(retired)} dead benchmark(s). "
            f"{len(l15)} L15 violation(s). "
            f"{len(zero_pass)} zero-pass worker(s)."
        ),
    }

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d__%H%M%S")
    out_path = (
        repo_root / "docs" / "system" / "outputs"
        / f"{stamp}__devg__health-check.json"
    )
    out_path.write_text(json.dumps(payload, indent=2) + "\n")

    print(json.dumps({
        "output_path": str(out_path),
        "summary": payload["summary"],
        "stuck_archived": stuck_archived,
        "benchmarks_retired": len(retired),
        "l15_violations": len(l15),
        "zero_pass_workers": len(zero_pass),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
