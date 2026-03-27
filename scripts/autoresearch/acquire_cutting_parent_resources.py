from __future__ import annotations

import argparse
import json

from src.rag.library_acquisition import acquire_all_cutting_parent_resources


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    print(json.dumps(acquire_all_cutting_parent_resources(limit=args.limit), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
