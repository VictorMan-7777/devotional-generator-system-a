from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from src.autoresearch.training_manager import build_training_manager_review


def _load_env_local(repo_root: Path) -> dict[str, str]:
    """Load key=value pairs from .env.local if present. Used to inject secrets
    (e.g. OPENAI_API_KEY) into subprocess environments without committing them."""
    env_file = repo_root / ".env.local"
    if not env_file.exists():
        return {}
    pairs: dict[str, str] = {}
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        pairs[key.strip()] = value.strip()
    return pairs

OUTLINER_EVALUATION_LOCK = {
    "enabled": False,
    "reason": (
        "Evaluation lock lifted. Redesigned reasoning outliner won 5-0 comparison (legacy 0.0 vs redesigned 16.0). "
        "Adapter path integrated into training agent (outliner_adapter.py). Broader worker training resumed."
    ),
    "active_workers": (
        "training_manager",
        "outliner",
        "library_trainer",
        "theological_reviewer",
        "policy_guardian",
    ),
}

# Pauses outliner training cycles independently of the evaluation lock.
OUTLINER_TRAINING_PAUSED = {
    "enabled": False,
    "reason": (
        "Resumed 2026-03-16: LLM trainer wired. Outliner now uses reasoning (deterministic) mode; "
        "llm_outliner_core.py is a trainer evaluator, not a worker. OpenAI/Codex API key active."
    ),
}

# Full supervisor suspension — all active training paused while agents are updated.
# Set enabled=False to resume after agent AI calls are implemented and verified.
SUPERVISOR_SUSPENDED = {
    "enabled": False,
    "reason": (
        "Resumed 2026-03-16: LLM agent architecture implemented. All workers labeled 'agent' now make "
        "real AI calls via src/llm/ (Claude or Codex). Trainers evaluate deterministic worker output; "
        "workers are not replaced by LLM agents. OpenAI/Codex API key active. DEVG_LLM_PROVIDER=codex."
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run_step(repo_root: Path, label: str, script_name: str) -> dict[str, object]:
    script_path = repo_root / "scripts" / "autoresearch" / script_name
    started = _utc_now()
    env = {
        **os.environ,
        **_load_env_local(repo_root),
        # Enable LLM burden/lane generation in the outliner training path.
        "DEVG_OUTLINER_LLM_BURDEN": "1",
    }
    result = subprocess.run(
        [str(repo_root / ".venv" / "bin" / "python"), str(script_path)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    completed = _utc_now()
    return {
        "label": label,
        "script": script_name,
        "started_at_utc": started,
        "completed_at_utc": completed,
        "returncode": result.returncode,
        "stdout_tail": result.stdout[-2000:],
        "stderr_tail": result.stderr[-2000:],
    }


def _monitoring_only_plan() -> list[tuple[str, str]]:
    """Steps that run even when training is suspended — quality monitors only, no generation."""
    return [
        ("gate_reviews", "run_gate_reviews.py"),
        ("theological_reviewer", "run_theological_reviewer.py"),
        ("library_trainer", "run_library_trainer_review.py"),
        ("policy_guardian", "run_policy_guardian.py"),
        ("proposal_reviewer", "run_proposal_reviewer.py"),
        ("cross_evaluator", "run_cross_evaluator.py"),
    ]


def _step_plan(review: dict[str, object], *, repo_root: Path) -> list[tuple[str, str]]:
    if SUPERVISOR_SUSPENDED["enabled"]:
        return _monitoring_only_plan()

    if OUTLINER_EVALUATION_LOCK["enabled"]:
        return [
            ("training_manager", "run_training_manager_review.py"),
            ("outliner", "run_outliner_training_cycle.py"),
            ("library_trainer", "run_library_trainer_review.py"),
            ("theological_reviewer", "run_theological_reviewer.py"),
            ("policy_guardian", "run_policy_guardian.py"),
        ]

    bottleneck = str(review.get("current_bottleneck_worker") or "").strip()
    reviews = review.get("reviews", []) if isinstance(review, dict) else []
    active_training = {
        str(item.get("worker_name") or "").strip()
        for item in reviews
        if str(item.get("status") or "").strip() == "active_training"
    }

    plan: list[tuple[str, str]] = [
        ("training_manager", "run_training_manager_review.py"),
        # Gate reviews run before worker cycles so verdicts are visible to trainer agents.
        ("gate_reviews", "run_gate_reviews.py"),
    ]

    # Bottleneck worker always runs first.
    if bottleneck == "outliner" and not OUTLINER_TRAINING_PAUSED["enabled"]:
        plan.append(("outliner", "run_outliner_training_cycle.py"))
    elif bottleneck == "exposition_writer":
        plan.append(("exposition_writer", "run_exposition_training_cycle.py"))
    elif bottleneck == "be_still_writer":
        plan.append(("be_still_writer", "run_be_still_training_cycle.py"))
    elif bottleneck == "action_writer":
        plan.append(("action_writer", "run_action_writer_training_cycle.py"))
    elif bottleneck == "prayer_writer":
        plan.append(("prayer_writer", "run_prayer_writer_training_cycle.py"))

    # Exposition writer always runs in parallel with any bottleneck so the
    # fixed template can accumulate LLM-verified passes without waiting for
    # the outliner to graduate.
    if ("exposition_writer", "run_exposition_training_cycle.py") not in plan:
        plan.append(("exposition_writer", "run_exposition_training_cycle.py"))

    # Downstream workers train in parallel regardless of bottleneck — they are
    # independent of the outliner and should not wait for it to graduate.
    if ("be_still_writer", "run_be_still_training_cycle.py") not in plan:
        plan.append(("be_still_writer", "run_be_still_training_cycle.py"))
    if ("action_writer", "run_action_writer_training_cycle.py") not in plan:
        plan.append(("action_writer", "run_action_writer_training_cycle.py"))

    # Prayer writer runs when its training script is available.
    _prayer_script = repo_root / "scripts" / "autoresearch" / "run_prayer_writer_training_cycle.py"
    if _prayer_script.exists() and ("prayer_writer", "run_prayer_writer_training_cycle.py") not in plan:
        plan.append(("prayer_writer", "run_prayer_writer_training_cycle.py"))

    plan.extend(
        [
            ("output_training_manager", "run_output_training_manager_review.py"),
            ("pdf_workers", "run_pdf_training_cycle.py"),
            ("research_librarian", "run_research_librarian_training_cycle.py"),
            # Acquisition librarian — processes ALL pending requests (research_librarian,
            # outliner, and any other requester) so the library expands proactively.
            ("acquisition_librarian", "run_acquisition_librarian_cycle.py"),
            # Grok outliner monitor — reads recent outliner experiments via file tools,
            # identifies failure patterns, and flags code changes required for human review.
            ("grok_outliner_monitor", "run_grok_outliner_monitor.py"),
            ("library_trainer", "run_library_trainer_review.py"),
            ("theological_reviewer", "run_theological_reviewer.py"),
            ("policy_guardian", "run_policy_guardian.py"),
            # Proposal reviewer — aggregates proposed_code_changes from all trainer cycles.
            ("proposal_reviewer", "run_proposal_reviewer.py"),
            # Cross-evaluator — independent assessment using the OPPOSITE AI provider.
            # Runs last so it has access to all cycle outputs from this supervisor run.
            ("cross_evaluator", "run_cross_evaluator.py"),
            # DevG monitor — Grok reads system state, diagnoses issues, escalates blocking
            # bugs to Grok 4.20 multi-agent for code suggestions shown to the human.
            ("devg_monitor", "run_devg_monitor.py"),
            # Grok chat — checks grok_workspace/chat.md for [Q] questions and answers inline.
            ("grok_chat", "run_grok_chat.py"),
        ]
    )
    return plan


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    initial_review = build_training_manager_review(repo_root)
    steps = _step_plan(initial_review, repo_root=repo_root)

    results: list[dict[str, object]] = []
    for label, script_name in steps:
        results.append(_run_step(repo_root, label, script_name))

    payload = {
        "started_at_utc": _utc_now(),
        "initial_training_manager_review": initial_review,
        "outliner_evaluation_lock": OUTLINER_EVALUATION_LOCK,
        "executed_steps": results,
    }
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d__%H%M%S")
    out_path = repo_root / "docs" / "system" / "outputs" / f"{stamp}__devg__training-supervisor-cycle.json"
    out_path.write_text(json.dumps(payload, indent=2) + "\n")
    summary = {
        "output_path": str(out_path),
        "started_at_utc": payload["started_at_utc"],
        "step_count": len(results),
        "failed_steps": [
            {"label": item["label"], "script": item["script"], "returncode": item["returncode"]}
            for item in results
            if int(item["returncode"]) != 0
        ],
    }
    print(json.dumps(summary, indent=2))
    return 0 if all(int(item["returncode"]) == 0 for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
