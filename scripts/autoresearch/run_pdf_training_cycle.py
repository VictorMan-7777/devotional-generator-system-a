from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.autoresearch.pdf_training_agent import build_pdf_training_cycle, write_pdf_training_cycle


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the PDF worker training cycle.")
    return parser.parse_args()


def main() -> None:
    _ = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    payload = build_pdf_training_cycle(repo_root)
    output_path = write_pdf_training_cycle(repo_root, payload)
    print(json.dumps({"output_path": str(output_path), "assignments": len(payload["assignments"])}, indent=2))


if __name__ == "__main__":
    main()
