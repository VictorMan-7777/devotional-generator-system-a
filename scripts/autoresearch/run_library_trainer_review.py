from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.autoresearch.library_trainer_agent import log_library_trainer_review
from src.rag.research_librarian import apply_library_trainer_review


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    payload = log_library_trainer_review(repo_root)
    request_updates = apply_library_trainer_review(
        payload.get("actionable_requests", [])
    )
    payload.update(request_updates)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d__%H%M%S")
    out_path = repo_root / "docs" / "system" / "outputs" / f"{stamp}__devg__library-trainer-review.json"
    out_path.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps({"output_path": str(out_path), **payload}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
