#!/usr/bin/env python3
"""
run_devg_monitor.py — DevG system monitoring, diagnosis, and escalation.

On first run (or when --onboard flag is set), Grok reads the full repo and DB
to build familiarity. Subsequent runs diagnose issues as they arise and optionally
escalate blocking issues to Grok 4.20 multi-agent for code suggestions.

Enhanced for consecutive cycle stall detection and soft stall escalation reports.

Output: docs/system/outputs/{timestamp}__devg__monitor-report.json
STALL output: docs/system/outputs/{timestamp}__devg__stall-report.json (if persistent soft stalls)

Exit 0: healthy or low/medium issues only.
Exit 1: blocking issues found (supervisor surfaces this).
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo_root))


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d__%H%M%S")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"parse_error": "Invalid JSON", "raw_response": text}


_ONBOARD_TASK = """
You are Grok, monitoring the DevG devotional content generation system.
This is your ONBOARDING pass — read the repo and DB to build full familiarity.
You will monitor this system autonomously going forward.

Read the following and build a complete mental map:

ARCHITECTURE (read these files):
 - README.md (project overview)
 - scripts/autoresearch/run_training_supervisor.py (main orchestrator)
 - scripts/autoresearch/devg-watch (monitoring dashboard)
 - src/llm/router.py (AI provider routing)
 - src/autoresearch/training_manager.py (worker status + bottleneck logic)
 - src/autoresearch/outliner_training_agent.py (outliner — current bottleneck)
 - src/rag/acquisition_librarian.py (library acquisition pipeline)
 - src/rag/library_cards.py (card creation + indexing guard)

DB SCHEMA (registry.db):
 - list_files("registry.db") to confirm path
 - Key tables: autoresearch_experiments (worker experiments), resource_acquisition_requests (library queue)
 - Query pattern (use search_file on a .py file that uses the table):
   search_file("src/autoresearch/store.py", "CREATE TABLE|INSERT INTO|autoresearch_experiments")

OUTPUT LOCATIONS:
 - list_files("docs/system/outputs/*.json") — see what kinds of cycle outputs exist
 - list_files("data/library") — see library structure

CURRENT STATE:
 - list_files("docs/system/outputs/*training-supervisor-cycle.json") newest 3 — read most recent
 - list_files("docs/system/outputs/*outliner-training-cycle.json") newest 3 — read most recent
 - list_files("data/library/resource-catalog.json") — read to count cards

Return a JSON onboarding summary:
{
  "generated_at_utc": "...",
  "onboarding": true,
  "architecture_summary": "brief description of how the system works",
  "current_bottleneck": "which worker and why",
  "library_card_count": N,
  "active_workers": ["..."],
  "graduated_workers": ["..."],
  "health": "healthy|stalled|broken",
  "critical_issues": ["..."],
  "suggested_fixes": [],
  "code_changes_required": false
}
"""


_MONITOR_TASK = """
You are Grok, monitoring the DevG devotional content generation system.
You already know the codebase. Diagnose the current state and flag issues.
Pay special attention to patterns ACROSS CONSECUTIVE CYCLES.

Read (sort list_files results by filename DESC for newest first):
1. Newest 3 supervisor cycles: list_files("docs/system/outputs/*training-supervisor-cycle.json")
   - Read contents of newest 3.
   - For EACH worker (outliner, exposition, be_still, action, library, etc.), check for REPEATED STALLS across these 3 cycles:
     e.g. same worker shows no progress (0 experiments, stalled status, soft fail) 2+ consecutive cycles.
2. Newest 3 outliner cycles: list_files("docs/system/outputs/*outliner-training-cycle.json")
   - Read all 3 newest.
   - Detect if 'no_assignments' (or equivalent stall like no outlines generated, infeasible assignments) appears 2+ CONSECUTIVE times.
3. Newest 3 cycles each for other key workers:
   - *exposition-trainer-cycle.json
   - *be_still-trainer-cycle.json
   - *action-trainer-cycle.json
   - Check for repeated no-progress (e.g. 0 experiments recorded, benchmark stalls).
4. Library: newest *library-trainer-review.json, *acquisition-librarian-cycle.json — check for acquisition stalls over cycles.
5. Recent DB experiments: use tools to count new autoresearch_experiments in last few cycles.
6. list_files("data/library") — card growth.
7. Check failed_steps, returncode != 0 anywhere.

Return ONLY valid JSON:
{
  "generated_at_utc": "...",
  "health": "healthy|stalled|broken",
  "persistent_soft_stalls": [  // NEW: list stalls persisting 2+ consecutive cycles WITHOUT returncode !=0
    {
      "worker": "outliner|exposition|...",
      "stall_type": "no_assignments|no_experiments|no_progress|acquisition_stalled|...",
      "consecutive_cycles": 2,  // or 3
      "cycle_timestamps": ["2024-10-05__143022", "2024-10-05__144512"],  // newest first
      "details": "Description of the stall pattern."
    }
  ],
  "critical_issues": ["Include soft stalls here too, e.g. 'Outliner no_assignments x3'"],
  "suggested_fixes": [
    {"file": "path/to/file.py", "description": "what and why", "urgency": "blocking|high|medium|low"}
  ],
  "code_changes_required": false  // true ONLY if specific code bugs (hard or soft)
}

IMPORTANT:
 - Detect SOFT STALLS even if NO returncode !=0. E.g. no_assignments, 0 experiments added over 2+ cycles.
 - Sort cycles by timestamp DESC (newest first) to check CONSECUTIVE (recent-most).
 - code_changes_required = true ONLY for clear, specific code bugs causing failures/stalls.
 - urgency=blocking ONLY for hard crashes (returncode !=0). Use high/medium for persistent stalls.
 - ALWAYS finish by updating grok_workspace/MEMORY.md via write_workspace_file with current state.
"""


def _escalate_to_grok42(diagnosis: dict[str, Any]) -> list[dict[str, Any]]:
    """Escalate blocking issues to Grok 4.20 multi-agent via Responses API."""
    from src.llm.grok_client import _load_dotenv
    _load_dotenv()

    try:
        import openai
    except ImportError:
        return [{"error": "openai not installed", "escalation_failed": True}]

    fixes = diagnosis.get("suggested_fixes", [])
    file_context_parts = []
    for fix in fixes:
        fp = fix.get("file", "")
        if fp:
            target = repo_root / fp
            if target.exists():
                try:
                    content = target.read_text(encoding="utf-8")
                    file_context_parts.append(f"=== {fp} ===\n{content}\n")
                except Exception:
                    pass

    escalation_prompt = (
        "You are a code repair specialist. Provide EXACT minimal fixes for these blocking issues.\n\n"
        f"Diagnosis:\n{json.dumps(diagnosis, indent=2)}\n\n"
        "Relevant file contents:\n" + "\n".join(file_context_parts) +
        "\n\nReturn ONLY valid JSON:\n"
        '{"changes": [{"file": "path", "description": "why", "old_code": "exact lines", '
        '"new_code": "replacement lines"}]}'
    )

    client = openai.OpenAI(
        api_key=os.environ.get("XAI_API_KEY"),
        base_url="https://api.x.ai/v1",
    )

    try:
        # Responses API — grok-4.20 multi-agent requires this endpoint
        response = client.responses.create(  # type: ignore[attr-defined]
            model="grok-4-20-0309",
            input=escalation_prompt,
            max_output_tokens=8000,
        )
        raw = getattr(response, "output_text", None) or str(response)
        result = _parse_json(raw)
        return result.get("changes", [])
    except Exception as exc:
        return [{"error": str(exc), "escalation_failed": True}]


def _print_summary(payload: dict[str, Any]) -> None:
    print(f"\n=== DevG Monitor ({payload.get('generated_at_utc', '?')}) ===")
    print(f"Health: {payload.get('health', 'unknown').upper()}")
    stalls = payload.get("persistent_soft_stalls", [])
    if stalls:
        print("🚨 PERSISTENT SOFT STALLS:")
        for stall in stalls:
            consec = stall.get("consecutive_cycles", 0)
            if consec >= 2:
                print(f"  {stall.get('worker', '?')}: {stall.get('stall_type', '?')} x{consec} — {stall.get('details', '')}")
    for issue in payload.get("critical_issues", []):
        print(f"  🚨 {issue}")
    urgency_icon = {"blocking": "🚫", "high": "🔥", "medium": "⚠️", "low": "ℹ️"}
    for fix in payload.get("suggested_fixes", []):
        if isinstance(fix, str):
            print(f"  ⚠️  {fix}")
            continue
        icon = urgency_icon.get(fix.get("urgency", "low"), "ℹ️")
        print(f"  {icon} {fix.get('file', '?')}: {fix.get('description', '')} [{fix.get('urgency', 'low')}]")
    for change in payload.get("code_suggestions", []):
        if "error" in change:
            print(f"  ❌ Escalation error: {change['error']}")
        else:
            print(f"\n  📝 {change.get('file', '?')}: {change.get('description', '')}")
            if change.get("old_code"):
                print(f"  OLD:\n{change['old_code']}")
            if change.get("new_code"):
                print(f"  NEW:\n{change['new_code']}")


def main() -> int:
    from src.llm.grok_agent import run_grok_agent

    onboard = "--onboard" in sys.argv
    task = _ONBOARD_TASK if onboard else _MONITOR_TASK

    label = "onboarding" if onboard else "monitoring"
    print(f"🚀 Grok {label} pass...", flush=True)

    try:
        response = run_grok_agent(
            task=task,
            model="grok-4-1-fast-reasoning",
            max_tokens=6000,
            max_tool_rounds=30,
        )
    except Exception as exc:
        print(f"ERROR: Grok agent failed: {exc}", file=sys.stderr)
        return 1

    payload = _parse_json(response)
    payload.setdefault("generated_at_utc", _utc_now())

    # Write main monitor report
    out_dir = repo_root / "docs" / "system" / "outputs"
    out_dir.mkdir(exist_ok=True)
    timestamp = _utc_stamp()
    out_path = out_dir / f"{timestamp}__devg__monitor-report.json"
    out_path.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"Monitor report: {out_path}", flush=True)

    # Check for persistent soft stalls and write dedicated report
    stalls = payload.get("persistent_soft_stalls", [])
    has_persistent_stalls = any(s.get("consecutive_cycles", 0) >= 10 for s in stalls)
    if has_persistent_stalls:
        stall_report = {
            "generated_at_utc": payload["generated_at_utc"],
            "monitor_report": out_path.name,
            "persistent_soft_stalls": stalls,
            "escalation_type": "persistent_soft_stalls"
        }
        stall_path = out_dir / f"{timestamp}__devg__stall-report.json"
        stall_path.write_text(json.dumps(stall_report, indent=2) + "\n")
        print(f"🚨 Stall REPORT written: {stall_path}", flush=True)

    # Escalation to Grok 4.20 multi-agent
    fixes = payload.get("suggested_fixes", [])
    if payload.get("code_changes_required") and any(f.get("urgency") == "blocking" for f in fixes):
        print("🚨 Blocking issue — escalating to Grok 4.20 multi-agent...", flush=True)
        payload["code_suggestions"] = _escalate_to_grok42(payload)

        # Re-write monitor report with suggestions
        out_path.write_text(json.dumps(payload, indent=2) + "\n")

    _print_summary(payload)

    has_blocking = any(f.get("urgency") == "blocking" for f in fixes)
    return 1 if has_blocking else 0


if __name__ == "__main__":
    sys.exit(main())
