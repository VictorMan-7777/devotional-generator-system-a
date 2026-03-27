from __future__ import annotations

import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from src.autoresearch.store import check_worker_alerts
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


def _run_steps_parallel(repo_root: Path, steps: list[tuple[str, str]]) -> list[dict[str, object]]:
    """Run a group of independent steps concurrently and return all results."""
    with ThreadPoolExecutor(max_workers=len(steps)) as executor:
        futures = {
            executor.submit(_run_step, repo_root, label, script): (label, script)
            for label, script in steps
        }
        return [future.result() for future in as_completed(futures)]


# Plan format: list of groups. Each group is a list of (label, script) tuples.
# Single-item groups run alone. Multi-item groups run in parallel.
StepGroup = list[tuple[str, str]]


def _monitoring_only_plan() -> list[StepGroup]:
    """Groups that run even when training is suspended — quality monitors only."""
    return [
        [("grok_chat", "run_grok_chat.py")],
        [("health_check", "run_health_check.py")],
        [("gate_reviews", "run_gate_reviews.py")],
        [
            ("theological_reviewer", "run_theological_reviewer.py"),
            ("library_trainer", "run_library_trainer_review.py"),
            ("policy_guardian", "run_policy_guardian.py"),
        ],
        [
            ("proposal_reviewer", "run_proposal_reviewer.py"),
            ("cross_evaluator", "run_cross_evaluator.py"),
        ],
    ]


def _step_plan(review: dict[str, object], *, repo_root: Path) -> list[StepGroup]:
    if SUPERVISOR_SUSPENDED["enabled"]:
        return _monitoring_only_plan()

    if OUTLINER_EVALUATION_LOCK["enabled"]:
        return [
            [("grok_chat", "run_grok_chat.py")],
            [("training_manager", "run_training_manager_review.py")],
            [("outliner", "run_outliner_training_cycle.py")],
            [
                ("library_trainer", "run_library_trainer_review.py"),
                ("theological_reviewer", "run_theological_reviewer.py"),
                ("policy_guardian", "run_policy_guardian.py"),
            ],
        ]

    bottleneck = str(review.get("current_bottleneck_worker") or "").strip()

    # --- Group 0: Grok reads feedback BEFORE making any decisions this cycle ---
    groups: list[StepGroup] = [
        [("grok_chat", "run_grok_chat.py")],
    ]

    # --- Group 1: Health + infrastructure ---
    groups.append([("health_check", "run_health_check.py")])
    groups.append([("training_manager", "run_training_manager_review.py")])
    groups.append([("gate_reviews", "run_gate_reviews.py")])

    # --- Group 2: Content workers — all independent, run in parallel ---
    _prayer_script = repo_root / "scripts" / "autoresearch" / "run_prayer_writer_training_cycle.py"
    content_workers: StepGroup = []

    if not OUTLINER_TRAINING_PAUSED["enabled"]:
        content_workers.append(("outliner", "run_outliner_training_cycle.py"))
    content_workers.append(("exposition_writer", "run_exposition_training_cycle.py"))
    content_workers.append(("be_still_writer", "run_be_still_training_cycle.py"))
    content_workers.append(("action_writer", "run_action_writer_training_cycle.py"))
    if _prayer_script.exists():
        content_workers.append(("prayer_writer", "run_prayer_writer_training_cycle.py"))

    groups.append(content_workers)

    # --- Group 3: Output managers + PDF + librarian — independent, run in parallel ---
    groups.append([
        ("output_training_manager", "run_output_training_manager_review.py"),
        ("pdf_workers", "run_pdf_training_cycle.py"),
        ("research_librarian", "run_research_librarian_training_cycle.py"),
    ])

    # --- Group 4: Acquisition librarian — sequential (modifies shared library catalog) ---
    groups.append([("acquisition_librarian", "run_acquisition_librarian_cycle.py")])

    # --- Group 5: Monitors — all read-only, run in parallel ---
    groups.append([
        ("grok_outliner_monitor", "run_grok_outliner_monitor.py"),
        ("library_trainer", "run_library_trainer_review.py"),
        ("theological_reviewer", "run_theological_reviewer.py"),
        ("policy_guardian", "run_policy_guardian.py"),
    ])

    # --- Group 6: Final reporters — run in parallel ---
    groups.append([
        ("proposal_reviewer", "run_proposal_reviewer.py"),
        ("cross_evaluator", "run_cross_evaluator.py"),
        ("devg_monitor", "run_devg_monitor.py"),
    ])

    return groups


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    initial_review = build_training_manager_review(repo_root)
    groups = _step_plan(initial_review, repo_root=repo_root)

    results: list[dict[str, object]] = []
    for group in groups:
        if len(group) == 1:
            results.append(_run_step(repo_root, group[0][0], group[0][1]))
        else:
            results.extend(_run_steps_parallel(repo_root, group))

    worker_alerts = check_worker_alerts()

    payload = {
        "started_at_utc": _utc_now(),
        "initial_training_manager_review": initial_review,
        "outliner_evaluation_lock": OUTLINER_EVALUATION_LOCK,
        "worker_alerts": worker_alerts,
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
