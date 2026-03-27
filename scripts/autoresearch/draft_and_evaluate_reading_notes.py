from __future__ import annotations

import json

from src.rag.library_reading_notes import draft_and_evaluate_reading_notes


def main() -> int:
    print(json.dumps(draft_and_evaluate_reading_notes(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
