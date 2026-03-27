#!/usr/bin/env python3
"""run_grok_outliner_monitor.py — Grok-powered outliner failure analysis.

Grok reads recent outliner experiment files directly via file tools,
identifies failure patterns, and produces a structured report. When
code changes are required, it flags them explicitly for human review
and implementation.

Output: docs/system/outputs/{timestamp}__devg__grok-outliner-monitor.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo_root))


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d__%H%M%S")


def main() -> int:
    from src.llm.grok_agent import run_grok_agent

    task = """
You are monitoring the outliner training agent in a devotional content generation system.
The outliner generates 3-day or 6-day devotional outlines for Bible passages.

Your job:
1. Read the 5 most recent outliner training cycle outputs
2. Read the most recent outliner training cycle in detail
3. Identify patterns in failures — what is the outliner consistently getting wrong?
4. Check whether deferred_no_resources experiments are being filed correctly
5. Determine if any code changes are required to unblock progress

Files to examine:
- Recent outliner cycles: docs/system/outputs/ (glob *__devg__outliner-training-cycle.json, newest 5)
- Outliner training agent: src/autoresearch/outliner_training_agent.py
- Outliner scoring: src/autoresearch/frozen_metrics.py (look for score_outline or evaluate_outline)

Return a JSON object with this structure:
{
  "generated_at_utc": "<ISO timestamp>",
  "experiment_summary": {
    "total_recent": <int>,
    "pass_count": <int>,
    "fail_count": <int>,
    "deferred_no_resources_count": <int>,
    "other_count": <int>
  },
  "failure_patterns": [
    {"pattern": "<description>", "frequency": "<how often>", "example_passage": "<passage>"}
  ],
  "deferred_gate_working": <true|false>,
  "bottleneck_diagnosis": "<1-2 sentence root cause>",
  "code_changes_required": <true|false>,
  "proposed_changes": [
    {
      "file": "<path>",
      "description": "<what needs to change and why>",
      "urgency": "blocking|high|medium|low"
    }
  ],
  "recommended_next_action": "<what should happen next cycle>"
}

Be precise and factual. Only flag code_changes_required=true if you see a clear, specific
bug or structural issue that is causing training failures. Do not propose speculative changes.
"""

    # Override system prompt: the default instructs Grok to update MEMORY.md "at the end of
    # every session", causing the model to write the file and return "Final response complete."
    # as its last message instead of the required JSON. This call needs structured JSON output.
    system = (
        "You are Grok, monitoring the DevG devotional content generation system. "
        "Use the provided file tools to read what you need. "
        "Your final response MUST be a valid JSON object exactly matching the schema in the task. "
        "Do NOT write any files. Do NOT update MEMORY.md. "
        "Do NOT wrap the JSON in prose or end with a session-completion marker. "
        "Return only the JSON object."
    )

    print("Running Grok outliner monitor...", flush=True)
    try:
        response = run_grok_agent(
            task=task,
            model="grok-4-1-fast-reasoning",
            max_tokens=4000,
            max_tool_rounds=20,
            system=system,
        )
    except Exception as exc:
        print(f"ERROR: Grok agent failed: {exc}", file=sys.stderr)
        return 1

    # Try to extract JSON from response
    payload: dict = {}
    try:
        # Grok may wrap JSON in markdown code fences
        text = response.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        payload = json.loads(text)
    except (json.JSONDecodeError, IndexError):
        # Store raw response if JSON parse fails
        payload = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "raw_response": response,
            "parse_error": "Could not extract JSON from Grok response",
        }

    if "generated_at_utc" not in payload:
        payload["generated_at_utc"] = datetime.now(timezone.utc).isoformat()

    out_dir = repo_root / "docs" / "system" / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = _utc_stamp()
    out_path = out_dir / f"{stamp}__devg__grok-outliner-monitor.json"
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))

    print(json.dumps(payload, indent=2))

    # Signal to supervisor: exit 1 only if blocking changes required
    if payload.get("code_changes_required") and any(
        c.get("urgency") == "blocking" for c in payload.get("proposed_changes", [])
    ):
        print("\n[GROK MONITOR] Blocking code changes flagged — review proposed_changes.", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
