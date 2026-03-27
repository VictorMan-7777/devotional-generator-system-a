#!/usr/bin/env python3
"""run_grok_chat.py — Process pending user questions in grok_workspace/chat.md.

Finds lines starting with [Q], sends them to Grok with full repo+DB context,
and writes the answer back inline as [A].

Modes:
  python run_grok_chat.py          — one-shot (used by supervisor cycle)
  python run_grok_chat.py --watch  — adaptive polling loop

Adaptive polling: interval shrinks when questions arrive frequently, grows
when the conversation goes quiet. Never polls faster than 1 minute.
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo_root))

CHAT_FILE = repo_root / "grok_workspace" / "chat.md"

# Adaptive poll intervals (seconds) based on time since last question
_INTERVALS = [
    (5  * 60, 60),    # last Q < 5 min ago  → poll every 1 min
    (15 * 60, 3 * 60),  # last Q < 15 min ago → poll every 3 min
    (60 * 60, 10 * 60), # last Q < 1 hr ago   → poll every 10 min
    (float("inf"), 20 * 60),  # quiet          → poll every 20 min
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _poll_interval(last_question_time: float | None) -> int:
    if last_question_time is None:
        return _INTERVALS[-1][1]
    age = time.time() - last_question_time
    for threshold, interval in _INTERVALS:
        if age < threshold:
            return interval
    return _INTERVALS[-1][1]


def _answer_question(question: str) -> str:
    from src.llm.grok_agent import run_grok_agent

    # Load memory for context without triggering a MEMORY.md update
    _memory_path = repo_root / "grok_workspace" / "MEMORY.md"
    _memory = ""
    if _memory_path.exists():
        try:
            _memory = _memory_path.read_text(encoding="utf-8")
        except Exception:
            pass

    # Override system prompt: chat answers must NOT write files or return session-end markers.
    # The default run_grok_agent system prompt instructs Grok to update MEMORY.md "at the end
    # of every session", which causes the model to write the file and return "Done." or
    # "## Session complete." as its final content — useless as a chat answer.
    system = (
        "You are Grok, monitoring the DevG devotional content generation system. "
        "Use the provided file tools to read what you need, then answer the question directly. "
        "Your final text response MUST be your complete answer to the user's question — "
        "conversational prose, specific numbers and file names where relevant. "
        "Do NOT update MEMORY.md. "
        "You MAY write proposal files to grok_workspace/proposals/ using write_workspace_file — "
        "use this when a [Q] asks you to submit a proposal. For all other responses, do not write files. "
        "Do NOT end with 'Done.', 'Session complete.', or any termination marker. "
        "Your response ends when you have finished answering the question.\n\n"
        + (f"## Your persistent memory (read-only for this call):\n{_memory}" if _memory else "")
    )

    task = f"""A user has asked you a question about the DevG devotional content generation system.
Answer it thoroughly using the file tools to look up current state from the repo and DB as needed.

You have persistent notes in grok_workspace/ from previous sessions — check there first.

User question: {question}

Relevant places to look depending on the question:
- Current training state: list_files("docs/system/outputs/*training-supervisor-cycle.json") newest 1-3
- Outliner status: list_files("docs/system/outputs/*outliner-training-cycle.json") newest 3
- Worker states: list_files("docs/system/outputs/*training-manager-review.json") newest 1
- Library: data/library/resource-catalog.json
- Your own notes: list_files("grok_workspace/**/*")
- Code: src/autoresearch/outliner_training_agent.py, src/llm/router.py, etc.

Respond conversationally and directly. Be specific — use actual numbers and file names from
what you read. Keep the answer under 400 words unless the question requires more detail.
"""
    return run_grok_agent(
        task=task,
        model="grok-4-1-fast-reasoning",
        max_tokens=2000,
        max_tool_rounds=15,
        system=system,
    )


def _process_once() -> tuple[int, float | None]:
    """Process pending questions. Returns (count_answered, timestamp_of_latest_Q_or_None)."""
    if not CHAT_FILE.exists():
        return 0, None

    text = CHAT_FILE.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    pending_indices = [i for i, line in enumerate(lines) if line.startswith("[Q]")]
    if not pending_indices:
        return 0, None

    last_q_time = time.time()
    print(f"Found {len(pending_indices)} pending question(s).", flush=True)

    # Process in reverse so inserted lines don't shift indices
    for idx in reversed(pending_indices):
        question = lines[idx][3:].strip()
        print(f"  Answering: {question[:80]}", flush=True)
        try:
            answer = _answer_question(question)
        except Exception as exc:
            answer = f"[Error: {exc}]"

        stamp = _utc_now()
        lines[idx] = f"[ANSWERED: {stamp}] {question}\n"
        answer_block = f"\n[A] {answer.strip()}\n\n---\n"
        lines.insert(idx + 1, answer_block)

    CHAT_FILE.write_text("".join(lines), encoding="utf-8")
    print(f"Updated: {CHAT_FILE}", flush=True)
    return len(pending_indices), last_q_time


def main() -> int:
    watch_mode = "--watch" in sys.argv

    if not watch_mode:
        count, _ = _process_once()
        if count == 0:
            print("No pending questions.")
        return 0

    # Watch mode — adaptive polling loop
    print(f"Watching {CHAT_FILE} for new [Q] questions. Ctrl-C to stop.", flush=True)
    last_mtime: float | None = None
    last_q_time: float | None = None

    try:
        while True:
            interval = _poll_interval(last_q_time)
            current_mtime = CHAT_FILE.stat().st_mtime if CHAT_FILE.exists() else None

            if current_mtime and current_mtime != last_mtime:
                last_mtime = current_mtime
                count, qt = _process_once()
                if qt:
                    last_q_time = qt

            next_check = datetime.now(timezone.utc).strftime("%H:%M")
            print(f"[{next_check}] Sleeping {interval//60}m (next check in {interval//60} min)", flush=True)
            time.sleep(interval)

    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
