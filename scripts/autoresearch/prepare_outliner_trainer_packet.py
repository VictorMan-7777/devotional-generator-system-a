from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from src.autoresearch.store import record_trainer_recommendation
from src.autoresearch.training_manager import build_training_manager_review


def _latest_cycle(repo_root: Path) -> Path | None:
    matches = sorted((repo_root / "docs" / "system" / "outputs").glob("*__devg__outliner-training-cycle.json"))
    return matches[-1] if matches else None


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    cycle_path = _latest_cycle(repo_root)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "trainer_spec_path": str(repo_root / "docs" / "system" / "outliner-trainer-agent-spec.md"),
        "codex_prompt_path": str(repo_root / "docs" / "system" / "outliner-trainer-codex-prompt.md"),
        "expected_recommendations_output_path": str(
            (repo_root / "docs" / "system" / "outputs" / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d__%H')}__devg__outliner-trainer-recommendations.json")
        ),
        "latest_cycle_path": str(cycle_path) if cycle_path else "",
        "latest_cycle": json.loads(cycle_path.read_text()) if cycle_path else {},
        "training_manager_review": build_training_manager_review(repo_root),
    }
    output_dir = repo_root / "docs" / "system" / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d__%H')}__devg__outliner-trainer-packet.json"
    output_path.write_text(json.dumps(payload, indent=2))

    recommendations_path = repo_root / "docs" / "system" / "outputs" / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}__devg__outliner-trainer-recommendations.json"
    if recommendations_path.exists():
        recommendations_payload = json.loads(recommendations_path.read_text())
        for idx, item in enumerate(recommendations_payload.get("recommended_passages", []), start=1):
            reference = str(item.get("reference") or "").strip()
            if not reference:
                continue
            slug = str(item.get("slug") or _slugify(reference)).strip()
            record_trainer_recommendation(
                recommendation_id=f"outliner-trainer::{slug}",
                trainer_name="expert_outliner_trainer",
                worker_name="outliner",
                scripture_reference=reference,
                passage_slug=slug,
                priority=int(item.get("priority") or (100 + idx)),
                rationale=str(item.get("training_reason") or ""),
                selection_stage="trainer_selected_non_harness_coverage",
                status="recommended",
                created_at_utc=payload["generated_at_utc"],
                consumed_at_utc="",
            )
    print(json.dumps({"output_path": str(output_path)}, indent=2))


if __name__ == "__main__":
    main()
