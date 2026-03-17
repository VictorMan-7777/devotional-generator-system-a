from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.autoresearch.exposition_training_agent import run_exposition_passage_sweep


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    results = run_exposition_passage_sweep(repo_root)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d__%H%M%S")
    payload = {
        "generated_at_utc": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "passage_count": len(results),
        "results": results,
    }
    out_path = (
        repo_root
        / "docs"
        / "system"
        / "outputs"
        / f"{stamp}__devg__exposition-passage-sweep.json"
    )
    out_path.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps({"output_path": str(out_path), **payload}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
