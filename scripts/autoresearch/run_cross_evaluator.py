"""run_cross_evaluator.py — Independent cross-AI evaluation of the training system.

Uses the OPPOSITE AI provider from the primary training system to independently assess:
  - Training progress (is it working?)
  - Rubric quality (are we measuring the right things?)
  - Code/design alignment (does the code match the design intent?)
  - Structural risks (what are we missing?)

Runs automatically at the end of each supervisor cycle. Results are written to
docs/system/outputs/*__devg__cross-evaluation.json for human review.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.autoresearch.cross_evaluator import build_cross_evaluation


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    evaluation = build_cross_evaluation(repo_root)

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d__%H%M%S")
    out_path = repo_root / "docs" / "system" / "outputs" / f"{stamp}__devg__cross-evaluation.json"
    out_path.write_text(json.dumps(evaluation, indent=2) + "\n")

    result = evaluation.get("evaluation", {})
    print(json.dumps({
        "output_path": str(out_path),
        "training_progress": result.get("training_progress", {}).get("verdict", "?"),
        "rubric_quality": result.get("rubric_quality", {}).get("verdict", "?"),
        "code_design_alignment": result.get("code_design_alignment", {}).get("verdict", "?"),
        "priority_recommendation": result.get("priority_recommendation", "?")[:120],
        "error": result.get("error"),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
