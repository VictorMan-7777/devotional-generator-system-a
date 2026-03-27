from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.autoresearch.store import log_experiment
from src.rag.library_reading_notes import draft_and_evaluate_reading_notes


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    started = _utc_now()
    results = draft_and_evaluate_reading_notes()
    accepted = sum(1 for item in results if item.get("decision") == "accepted")
    revise = sum(1 for item in results if item.get("decision") == "revise")
    completed = _utc_now()

    payload = {
        "started_at_utc": started,
        "completed_at_utc": completed,
        "reviewed_count": len(results),
        "accepted_count": accepted,
        "revise_count": revise,
        "results": results,
    }

    log_experiment(
        experiment_id=f"research-librarian__{started}",
        worker_name="research_librarian",
        benchmark_name="research-notes-training",
        benchmark_reference="second-pass shelf reading-note review under library-trainer guidance",
        status="completed" if revise == 0 else "review",
        attempted_change="Re-read shelf resources and produced second-pass research-librarian notes under library-trainer guidance.",
        metrics={
            "reviewed_count": len(results),
            "accepted_count": accepted,
            "revise_count": revise,
        },
        learning_note="Research librarian trained by rereading shelf resources and refining notes under expert library-trainer supervision.",
        keep_decision="keep" if revise == 0 else "review",
        created_at_utc=started,
        completed_at_utc=completed,
    )

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d__%H%M%S")
    out_path = repo_root / "docs" / "system" / "outputs" / f"{stamp}__devg__research-librarian-training-cycle.json"
    out_path.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps({"output_path": str(out_path), **payload}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
