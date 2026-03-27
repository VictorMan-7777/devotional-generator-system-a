#!/usr/bin/env python3
"""
Archive stalled 'assigned' rows that are older than a threshold.
Updates status from 'assigned' to 'archived' so workers can receive fresh assignments.
"""
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / 'registry.db'
STALE_HOURS = 2  # archive anything assigned for longer than this


def archive_stalled(dry_run=False):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Find stalled rows
    cur.execute("""
        SELECT id, worker_name, benchmark_reference, created_at_utc,
               ROUND((julianday('now') - julianday(replace(replace(created_at_utc,'T',' '),'Z',''))) * 24, 1) AS age_hours
        FROM autoresearch_experiments
        WHERE status = 'assigned'
          AND replace(replace(created_at_utc,'T',' '),'Z','') < datetime('now', ?)
        ORDER BY worker_name, created_at_utc
    """, (f'-{STALE_HOURS} hours',))
    rows = cur.fetchall()

    if not rows:
        print("No stalled assignments found.")
        conn.close()
        return 0

    print(f"Found {len(rows)} stalled assignments (>{STALE_HOURS}h old):")
    by_worker = {}
    for r in rows:
        by_worker.setdefault(r['worker_name'], []).append(r)
    for worker, items in sorted(by_worker.items()):
        print(f"  {worker}: {len(items)} rows (oldest: {items[0]['age_hours']}h)")

    if dry_run:
        print("[DRY RUN] No changes made.")
        conn.close()
        return len(rows)

    ids = [r['id'] for r in rows]
    placeholders = ','.join('?' * len(ids))
    now_utc = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    cur.execute(f"""
        UPDATE autoresearch_experiments
        SET status = 'archived',
            completed_at_utc = ?
        WHERE id IN ({placeholders})
    """, [now_utc] + ids)
    conn.commit()
    print(f"Archived {cur.rowcount} rows.")
    conn.close()
    return cur.rowcount


if __name__ == '__main__':
    dry_run = '--dry-run' in sys.argv
    count = archive_stalled(dry_run=dry_run)
    sys.exit(0 if count >= 0 else 1)
