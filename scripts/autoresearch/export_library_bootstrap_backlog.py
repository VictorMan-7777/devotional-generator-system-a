from __future__ import annotations

from src.rag.library_bootstrap import bootstrap_summary_json


def main() -> int:
    print(bootstrap_summary_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
