from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _latest_cycle(repo_root: Path) -> Path | None:
    matches = sorted((repo_root / "docs" / "system" / "outputs").glob("*__devg__pdf-training-cycle.json"))
    return matches[-1] if matches else None


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    cycle_path = _latest_cycle(repo_root)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "trainer_spec_path": str(repo_root / "docs" / "system" / "pdf-trainer-agent-spec.md"),
        "codex_prompt_path": str(repo_root / "docs" / "system" / "pdf-trainer-codex-prompt.md"),
        "latest_cycle_path": str(cycle_path) if cycle_path else "",
        "latest_cycle": json.loads(cycle_path.read_text()) if cycle_path else {},
    }
    output_dir = repo_root / "docs" / "system" / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d__%H')}__devg__pdf-trainer-packet.json"
    output_path.write_text(json.dumps(payload, indent=2))
    print(json.dumps({"output_path": str(output_path)}, indent=2))


if __name__ == "__main__":
    main()
