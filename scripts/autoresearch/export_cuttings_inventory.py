from __future__ import annotations

import json

from src.rag.cuttings_inventory import inventory_as_jsonable


def main() -> int:
    print(json.dumps(inventory_as_jsonable(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
