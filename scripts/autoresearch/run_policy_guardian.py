from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.autoresearch.policy_guardian_agent import log_policy_guardian_report


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    payload = log_policy_guardian_report(repo_root)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d__%H%M%S")
    out_path = repo_root / "docs" / "system" / "outputs" / f"{stamp}__devg__policy-guardian-report.json"
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output_path": str(out_path), **payload}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
