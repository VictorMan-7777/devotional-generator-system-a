from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from src.rag.acquisition_librarian import escalate_for_passage
from src.rag.library_requests import list_resource_acquisition_requests


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    started = _utc_now()

    # Fetch ALL pending requests regardless of requester (research_librarian, outliner, etc.)
    pending = list_resource_acquisition_requests(status="requested")

    results = []
    for req in pending:
        result = escalate_for_passage(
            scripture_reference=req.scripture_reference,
            topic=req.topic,
            missing_kinds=list(req.requested_resource_kinds or ["exposition"]),
            request_id=req.request_id,
        )
        result["requested_by"] = req.requested_by
        results.append(result)
        time.sleep(1.0)  # polite pause between passages

    completed = _utc_now()
    acquired = sum(1 for r in results if r.get("status") == "acquired")
    skipped = sum(1 for r in results if r.get("status") == "skipped")
    failed = sum(1 for r in results if r.get("status") not in ("acquired", "skipped"))

    payload = {
        "started_at_utc": started,
        "completed_at_utc": completed,
        "pending_count": len(pending),
        "acquired_count": acquired,
        "skipped_count": skipped,
        "failed_count": failed,
        "results": results,
    }

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d__%H%M%S")
    out_path = (
        repo_root / "docs" / "system" / "outputs"
        / f"{stamp}__devg__acquisition-librarian-cycle.json"
    )
    out_path.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps({"output_path": str(out_path), **payload}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
