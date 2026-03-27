from __future__ import annotations

from src.rag.library_maintenance import queue_json


def main() -> int:
    print(queue_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
