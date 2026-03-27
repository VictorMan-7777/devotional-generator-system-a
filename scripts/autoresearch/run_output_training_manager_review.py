from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from src.autoresearch.output_training_manager import log_output_training_manager_review


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the output training manager review.")
    return parser.parse_args()


def main() -> None:
    _ = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    payload = log_output_training_manager_review(repo_root)
    output_dir = repo_root / "docs" / "system" / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d__%H%M%S")
    output_path = output_dir / f"{stamp}__devg__output-training-manager-review.json"
    output_path.write_text(json.dumps(payload, indent=2))
    print(json.dumps({"output_path": str(output_path), **payload}, indent=2))


if __name__ == "__main__":
    main()
