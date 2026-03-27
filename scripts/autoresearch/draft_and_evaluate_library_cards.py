from __future__ import annotations

import json

from src.rag.library_cards import draft_and_evaluate_all_acquired_cards


def main() -> int:
    print(json.dumps(draft_and_evaluate_all_acquired_cards(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
