"""run_gate_reviews.py — Run pending 50-experiment gate reviews for tracked workers.

The supervisor calls this every cycle.  It detects which workers have crossed a new
50-experiment gate since the last evaluation and runs the gate review LLM call for each.
If no gates are pending, it exits cleanly with an empty results list.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.autoresearch.llm_gate_review_core import pending_gate_reviews, run_gate_review

_TRACKED_WORKERS = ["outliner", "exposition_writer"]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    started = _utc_now()

    pending = pending_gate_reviews(_TRACKED_WORKERS)
    results = []
    for worker_name, gate_number in pending:
        review = run_gate_review(worker_name, gate_number)
        results.append(review)
        verdict = review.get("gate_verdict", "unknown")
        insanity = review.get("insanity_pattern_detected", False)
        flag = "🚨 INSANITY LOOP" if verdict == "insanity_loop" else ("⚠ STALLED" if verdict == "stalled" else "✓ on_track")
        print(f"  [{flag}] {worker_name} gate {gate_number}: {review.get('priority_intervention', '')[:80]}")
        if insanity:
            print(f"    Insanity evidence: {review.get('insanity_evidence', '')[:100]}")

    payload = {
        "started_at_utc": started,
        "completed_at_utc": _utc_now(),
        "pending_gates_found": len(pending),
        "pending_gates": [{"worker": w, "gate": g} for w, g in pending],
        "results": results,
    }

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d__%H%M%S")
    out_path = (
        repo_root / "docs" / "system" / "outputs"
        / f"{stamp}__devg__gate-reviews.json"
    )
    out_path.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps({"output_path": str(out_path), "gates_reviewed": len(results)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
