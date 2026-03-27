"""run_proposal_reviewer.py — Surface code-change proposals from trainer agents.

Scans recent exposition and outliner training cycle JSONs for `proposed_code_changes`
entries emitted by LLM trainers. Groups them by recurrence and writes a prioritised
review package for human evaluation.

Nothing is implemented automatically. This script only reads and reports.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.autoresearch.proposal_reviewer import build_proposal_review


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    review = build_proposal_review(repo_root)

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d__%H%M%S")
    out_path = repo_root / "docs" / "system" / "outputs" / f"{stamp}__devg__trainer-proposals.json"
    out_path.write_text(json.dumps(review, indent=2) + "\n")

    proposals = review.get("proposals", [])
    print(json.dumps({
        "output_path": str(out_path),
        "proposal_count": len(proposals),
        "summary": review.get("summary", ""),
        "top_proposals": [
            {
                "rank": p["rank"],
                "recurrence": p["recurrence"],
                "file_path": p["file_path"],
                "objective": p["objective"],
            }
            for p in proposals[:5]
        ],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
