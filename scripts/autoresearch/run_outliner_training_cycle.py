from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.autoresearch.outliner_training_agent import (
    build_outliner_training_cycle,
    write_outliner_training_cycle,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the outline-only training cycle for the outliner.")
    parser.add_argument("--limit", type=int, default=1, help="Maximum number of assignments to run in this cycle.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    payload = build_outliner_training_cycle(repo_root, limit=args.limit)
    output_path = write_outliner_training_cycle(repo_root, payload)
    print(json.dumps({"output_path": str(output_path), "assignments": len(payload["assignments"])}, indent=2))


if __name__ == "__main__":
    main()
