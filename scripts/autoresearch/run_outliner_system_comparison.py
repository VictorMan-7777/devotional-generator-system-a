from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.autoresearch.outliner_system_comparison import (
    compare_outliner_systems,
    default_passage_slug,
)

def main() -> int:
    parser = argparse.ArgumentParser(description="Record the current outliner old-vs-new system comparison state.")
    parser.add_argument("--passage", required=True, help="Scripture reference to compare, e.g. 'Ruth 1'")
    parser.add_argument("--days", type=int, default=6, help="Devotional day count")
    parser.add_argument("--weeks", type=int, default=1, help="Devotional week count")
    parser.add_argument("--reviewed-by", default="training_manager", help="Reviewer identity")
    args = parser.parse_args()

    passage = args.passage.strip()
    payload = compare_outliner_systems(
        scripture_reference=passage,
        passage_slug=default_passage_slug(passage),
        num_days=args.days,
        num_weeks=args.weeks,
        reviewed_by=args.reviewed_by.strip(),
    )

    repo_root = Path(__file__).resolve().parents[2]
    output_dir = repo_root / "docs" / "system" / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    record = payload["record"]
    out_path = output_dir / f"{record['created_at_utc'][:10]}__outliner-system-comparison__{record['passage_slug']}__{record['range_label']}.json"
    out_path.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps({"output_path": str(out_path), **payload}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
