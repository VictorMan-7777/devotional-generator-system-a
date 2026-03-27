from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.autoresearch.exposition_training_agent import log_exposition_training_cycle


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    payload = log_exposition_training_cycle(repo_root)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d__%H%M%S")
    out_path = repo_root / "docs" / "system" / "outputs" / f"{stamp}__devg__exposition-training-cycle.json"
    out_path.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps({"output_path": str(out_path), **payload}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
