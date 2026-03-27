from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.autoresearch.training_manager import log_training_manager_review


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    payload = log_training_manager_review(repo_root)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d__%H__devg__training-manager-review.json")
    out_path = repo_root / "docs" / "system" / "outputs" / stamp
    out_path.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps({"output_path": str(out_path), **payload}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
