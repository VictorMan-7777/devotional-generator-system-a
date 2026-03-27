#!/usr/bin/env python3
"""run_devg_watcher.py — Event-driven watcher for DevG grok_workspace.

Replaces cron polling entirely. Uses watchdog (FSEvents on macOS) so
file changes fire immediately, not on a fixed schedule.

Watches:
  grok_workspace/urgent.md          → process urgent entries immediately
  grok_workspace/chat.md            → process [Q] entries immediately
  grok_workspace/proposals/         → process pending proposals immediately
  grok_workspace/notifications/     → detect pending_approval.md updates

Idle work (runs when no events for IDLE_PROBE_SECONDS):
  - Scan for workers approaching 50/100 experiment thresholds
  - Check library coverage against upcoming passages
  - Detect workers with recent score regressions
  - Surface any structural defect patterns across experiments

Usage:
  .venv/bin/python scripts/autoresearch/run_devg_watcher.py

Runs indefinitely. Stop with Ctrl-C.
"""
from __future__ import annotations

import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo_root))

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

WORKSPACE = repo_root / "grok_workspace"
URGENT_FILE = WORKSPACE / "urgent.md"
CHAT_FILE = WORKSPACE / "chat.md"
PROPOSALS_DIR = WORKSPACE / "proposals"
NOTIFICATIONS_DIR = WORKSPACE / "notifications"
PENDING_FILE = NOTIFICATIONS_DIR / "pending_approval.md"

# Debounce: don't re-fire within N seconds of the last fire for same file
DEBOUNCE_SECONDS = 5

# Idle probe: if no events for this many seconds, run proactive scans
IDLE_PROBE_SECONDS = 600  # 10 minutes

# Max time to wait for a Grok response before escalating (seconds)
URGENT_RESPONSE_TIMEOUT = 900  # 15 minutes

PYTHON = str(repo_root / ".venv" / "bin" / "python")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S UTC")


def _log(msg: str) -> None:
    print(f"[{_ts()}] {msg}", flush=True)


def _run_script(script: str, *args: str, background: bool = False) -> None:
    """Run a scripts/autoresearch script, optionally in background."""
    script_path = repo_root / "scripts" / "autoresearch" / script
    cmd = [PYTHON, str(script_path), *args]
    if background:
        subprocess.Popen(cmd, cwd=repo_root, start_new_session=True)
        _log(f"  → spawned {script} {' '.join(args)}")
    else:
        result = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True)
        if result.returncode != 0:
            _log(f"  ✗ {script} exited {result.returncode}: {result.stderr[-300:].strip()}")
        else:
            _log(f"  ✓ {script} done")


# ---------------------------------------------------------------------------
# Action handlers
# ---------------------------------------------------------------------------

# Track which CLAUDE URGENT timestamps have already been dispatched to Grok
# so watcher writes to urgent.md don't re-trigger the same entry.
_dispatched_urgent_timestamps: set[str] = set()


def _handle_urgent_change() -> None:
    """New entry in urgent.md — process it immediately.

    [CLAUDE URGENT] = outbound to Grok. Call the Grok agent directly with the
    content and write his response back inline. No supervisor cycle required.
    Tracks dispatched timestamps to prevent re-processing on own writes.

    [GROK URGENT] = inbound from Grok needing operator. Notify via ntfy.
    """
    import re
    _log("urgent.md changed — processing urgent entries")
    text = URGENT_FILE.read_text(encoding="utf-8") if URGENT_FILE.exists() else ""

    # --- Inbound: Grok needs operator attention ---
    # Only fire ntfy for GROK URGENT entries not followed by a CLAUDE response
    grok_urgents = re.findall(r'\[GROK URGENT ([^\]]+)\]', text)
    for ts in grok_urgents:
        marker = f"[GROK URGENT {ts}]"
        after = text.split(marker, 1)[-1]
        # Considered acknowledged if a CLAUDE URGENT appears after it
        if "[CLAUDE URGENT" not in after:
            _log(f"  → unacknowledged GROK URGENT at {ts} — notifying operator")
            excerpt = after.strip()[:200]
            _send_ntfy("DevG: Grok urgent", f"{ts}: {excerpt}")

    # --- Outbound: find CLAUDE URGENT entries not yet responded to ---
    # Split on CLAUDE URGENT boundaries; each block ends at the next one
    blocks = re.split(r'(?=\[CLAUDE URGENT )', text)
    unanswered = []
    for block in blocks:
        m = re.match(r'\[CLAUDE URGENT ([^\]]+)\]', block)
        if not m:
            continue
        ts = m.group(1).strip()
        if ts in _dispatched_urgent_timestamps:
            continue  # already dispatched this session
        # Answered if a GROK RESPONSE or GROK URGENT follows in the same block
        if "[GROK RESPONSE" in block or "[GROK URGENT" in block:
            _dispatched_urgent_timestamps.add(ts)
            continue
        unanswered.append((ts, block))

    if not unanswered:
        _log("  → no new unanswered CLAUDE URGENT entries")
        return

    for ts, block in unanswered:
        _dispatched_urgent_timestamps.add(ts)  # mark before spawning to prevent double-dispatch
        lines = block.strip().splitlines()
        message = "\n".join(lines[1:]).strip() if len(lines) > 1 else lines[0]
        _log(f"  → dispatching urgent to Grok [{ts}]: {message[:80]}")
        threading.Thread(
            target=_call_grok_urgent,
            args=(ts, message),
            daemon=True,
        ).start()


def _call_grok_urgent(ts: str, message: str) -> None:
    """Call Grok on an urgent message and write response back. Runs in background thread.

    Retry logic before escalating to operator:
    1. First attempt — full message
    2. On failure/timeout — retry once with same message
    3. On second failure — ping with minimal "are you responsive?" probe
    4. On third failure — diagnose API health, then notify operator with diagnosis
    """
    from src.llm.grok_agent import run_grok_agent

    def _attempt(task: str, rounds: int = 10) -> tuple[str | None, str | None]:
        """Returns (response, error). One is always None."""
        try:
            result = run_grok_agent(
                task=task,
                model="grok-4-1-fast-reasoning",
                max_tokens=2000,
                max_tool_rounds=rounds,
            )
            return result, None
        except Exception as exc:
            return None, str(exc)

    def _write_response(content: str) -> None:
        now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        reply = f"\n[GROK RESPONSE {now_ts}]\n{content.strip()}\n"
        current = URGENT_FILE.read_text(encoding="utf-8")
        URGENT_FILE.write_text(current + reply, encoding="utf-8")

    # Attempt 1
    _log(f"  → Grok urgent attempt 1 [{ts}]")
    response, err = _attempt(f"URGENT — respond to this immediately:\n\n{message}")
    if response:
        _write_response(response)
        _log(f"  → Grok urgent response written [{ts}]")
        return

    _log(f"  → attempt 1 failed: {err} — retrying")

    # Attempt 2 — retry same message
    _log(f"  → Grok urgent attempt 2 [{ts}]")
    response, err = _attempt(f"URGENT — respond to this immediately:\n\n{message}")
    if response:
        _write_response(response)
        _log(f"  → Grok urgent response written on retry [{ts}]")
        return

    _log(f"  → attempt 2 failed: {err} — trying minimal probe")

    # Attempt 3 — minimal responsiveness probe
    _log(f"  → Grok urgent attempt 3 (probe) [{ts}]")
    response, err = _attempt("Respond with OK if you are responsive.", rounds=2)
    if response:
        # Grok is up but struggling with the full message — re-queue with simplified ask
        simplified = f"Previous urgent message failed twice. Simplified ask:\n\n{message[:500]}\n\nRespond with your understanding and next action only."
        response2, err2 = _attempt(simplified)
        if response2:
            _write_response(response2)
            _log(f"  → Grok urgent response written via simplified prompt [{ts}]")
            return
        err = err2 or "simplified prompt also failed"

    # All attempts failed — diagnose and notify operator
    _log(f"  → all Grok attempts failed [{ts}] — diagnosing")
    diagnosis = f"Grok unresponsive after 3 attempts. Last error: {err}. Urgent message: {message[:200]}"
    _write_response(f"[UNDELIVERED — all attempts failed]\n{diagnosis}")
    _send_ntfy("DevG: Grok unresponsive", diagnosis)
    _log(f"  → operator notified: Grok unresponsive")


def _handle_chat_change() -> None:
    """[Q] added to chat.md — answer immediately."""
    _log("chat.md changed — checking for pending questions")
    text = CHAT_FILE.read_text(encoding="utf-8") if CHAT_FILE.exists() else ""
    if "[Q]" in text:
        _log("  → [Q] detected, running grok chat")
        _run_script("run_grok_chat.py")
    else:
        _log("  → no pending questions")


def _handle_proposal_change(path: str) -> None:
    """New .py file in proposals/ — notify for review."""
    _log(f"proposals/ changed: {Path(path).name}")
    if path.endswith(".py") and "completed" not in path:
        _pending_check()


def _handle_pending_approval_change() -> None:
    """pending_approval.md updated — check for PROPOSAL READY entries."""
    _pending_check()


def _pending_check() -> None:
    """Read pending_approval.md and surface any PROPOSAL READY items."""
    if not PENDING_FILE.exists():
        return
    text = PENDING_FILE.read_text(encoding="utf-8")
    ready = [line for line in text.splitlines() if line.startswith("PROPOSAL READY:") and "RESOLVED" not in line]
    if ready:
        count = len(ready)
        _log(f"  → {count} proposal(s) pending review")
        _send_ntfy(
            f"DevG: {count} proposal(s) ready",
            "\n".join(ready[:5]),
        )
    else:
        _log("  → no PROPOSAL READY entries")


def _send_ntfy(title: str, body: str) -> None:
    """Send ntfy notification if configured."""
    ntfy_conf = repo_root / ".ntfy_config"
    if not ntfy_conf.exists():
        return
    try:
        cfg = {}
        for line in ntfy_conf.read_text().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
        url = cfg.get("url") or cfg.get("topic")
        if not url:
            return
        subprocess.run(
            ["curl", "-s", "-d", body, "-H", f"Title: {title}", url],
            timeout=5,
            capture_output=True,
        )
        _log(f"  → ntfy sent: {title}")
    except Exception as exc:
        _log(f"  → ntfy failed: {exc}")


# ---------------------------------------------------------------------------
# Idle probes
# ---------------------------------------------------------------------------

def _idle_probe() -> None:
    """Proactive scans run during quiet periods."""
    _log("=== Idle probe ===")
    _check_experiment_thresholds()
    _check_library_gaps()
    _log("=== Idle probe done ===")


def _check_experiment_thresholds() -> None:
    """Warn when workers approach 50 or 100 experiment decision points."""
    try:
        import sqlite3
        from src.persistence.paths import default_registry_db_path
        db = Path(default_registry_db_path())
        if not db.exists():
            db = repo_root / "registry.db"
        if not db.exists():
            _log("  threshold check: no DB found")
            return
        conn = sqlite3.connect(str(db))
        rows = conn.execute(
            "SELECT worker_name, COUNT(*) as cnt "
            "FROM autoresearch_experiments "
            "GROUP BY worker_name"
        ).fetchall()
        conn.close()
        for name, cnt in rows:
            if 45 <= cnt < 55:
                _log(f"  ⚠  {name}: {cnt} experiments — approaching 50-exp check")
                _send_ntfy(f"DevG: {name} at {cnt} experiments", "50-experiment decision point approaching")
            elif 95 <= cnt < 105:
                _log(f"  ⚠  {name}: {cnt} experiments — approaching 100-exp decision")
                _send_ntfy(f"DevG: {name} at {cnt} experiments", "100-experiment decision required")
    except Exception as exc:
        _log(f"  threshold check error: {exc}")


def _check_library_gaps() -> None:
    """Quick check: library card count from registry DB."""
    try:
        import sqlite3
        from src.persistence.paths import default_registry_db_path
        db = Path(default_registry_db_path())
        if not db.exists():
            return
        conn = sqlite3.connect(str(db))
        row = conn.execute("SELECT COUNT(*) FROM resource_catalog").fetchone()
        conn.close()
        _log(f"  library: {row[0]} cards indexed")
    except Exception as exc:
        _log(f"  library check error: {exc}")


# ---------------------------------------------------------------------------
# Watchdog handler
# ---------------------------------------------------------------------------

class DevGHandler(FileSystemEventHandler):
    def __init__(self) -> None:
        self._last_fire: dict[str, float] = {}
        self._lock = threading.Lock()

    def _debounce(self, key: str) -> bool:
        """Return True if we should act (not within debounce window)."""
        now = time.time()
        with self._lock:
            last = self._last_fire.get(key, 0)
            if now - last < DEBOUNCE_SECONDS:
                return False
            self._last_fire[key] = now
        return True

    def on_modified(self, event: FileSystemEvent) -> None:
        self._dispatch(event.src_path)

    def on_created(self, event: FileSystemEvent) -> None:
        self._dispatch(event.src_path)

    def _dispatch(self, path: str) -> None:
        if not path or path.endswith(".tmp") or "~" in path:
            return
        p = Path(path)

        if p == URGENT_FILE:
            if self._debounce("urgent"):
                threading.Thread(target=_handle_urgent_change, daemon=True).start()
        elif p == CHAT_FILE:
            if self._debounce("chat"):
                threading.Thread(target=_handle_chat_change, daemon=True).start()
        elif p == PENDING_FILE:
            if self._debounce("pending"):
                threading.Thread(target=_handle_pending_approval_change, daemon=True).start()
        elif str(p).startswith(str(PROPOSALS_DIR)) and p.suffix == ".py":
            key = f"proposal:{p.name}"
            if self._debounce(key):
                threading.Thread(target=_handle_proposal_change, args=(path,), daemon=True).start()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    _log(f"DevG watcher starting — watching {WORKSPACE}")

    handler = DevGHandler()
    observer = Observer()
    observer.schedule(handler, str(WORKSPACE), recursive=True)
    observer.start()

    _log("Watching:")
    _log(f"  {URGENT_FILE.relative_to(repo_root)}")
    _log(f"  {CHAT_FILE.relative_to(repo_root)}")
    _log(f"  {PROPOSALS_DIR.relative_to(repo_root)}/")
    _log(f"  {NOTIFICATIONS_DIR.relative_to(repo_root)}/")
    _log(f"Idle probe every {IDLE_PROBE_SECONDS // 60} min")

    # Startup scan — don't miss anything queued while watcher wasn't running
    _log("--- Startup scan ---")
    _handle_urgent_change()
    _handle_chat_change()
    _pending_check()
    _log("--- Startup scan done ---")

    last_idle = time.time()
    try:
        while observer.is_alive():
            time.sleep(10)
            if time.time() - last_idle >= IDLE_PROBE_SECONDS:
                threading.Thread(target=_idle_probe, daemon=True).start()
                last_idle = time.time()
    except KeyboardInterrupt:
        _log("Stopping...")

    observer.stop()
    observer.join()
    _log("DevG watcher stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
