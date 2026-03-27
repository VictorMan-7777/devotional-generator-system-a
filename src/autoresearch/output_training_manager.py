from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.autoresearch.store import list_experiments, log_experiment


@dataclass(frozen=True)
class OutputWorkerReview:
    worker_name: str
    status: str
    grade: str
    rationale: str
    next_action: str
    evidence: tuple[str, ...] = ()


OUTPUT_TRAINER_PROFILE = {
    "role": "expert_output_trainer",
    "mission": (
        "Manage the training of PDF art director and layout engineer so the output path produces "
        "visually intentional, layout-safe, premium-quality devotional PDFs."
    ),
    "junior_worker_assumption": (
        "Treat both PDF workers as complete beginners with no established production discipline. "
        "Assume visual hierarchy is unproven, layout safety is unproven, and premium output quality "
        "is not yet present. Do not grant readiness status based on one good cycle. "
        "Require stability across multiple independent runs before expanding scope."
    ),
}

OUTPUT_PRODUCTION_STANDARD = {
    "label": "elevated_premium_publishing_output",
    "description": (
        "Output workers should produce a reviewed-proof and final publication path that feels elevated, "
        "layout-safe, visually intentional, and visibly worth an above-normal devotional price rather than merely technically valid."
    ),
    "expectations": (
        "elevated visual hierarchy",
        "book design that supports above-normal pricing",
        "clear day starts",
        "stable pagination",
        "proof/final distinction",
        "KDP-safe margins and overflow handling",
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _latest_pdf_cycle(repo_root: Path) -> dict[str, Any]:
    matches = sorted((repo_root / "docs" / "system" / "outputs").glob("*__devg__pdf-training-cycle.json"))
    if not matches:
        return {}
    return _load_json(matches[-1]) or {}


_ART_DIRECTOR_GRADUATION_THRESHOLD = 25


def _pdf_art_director_pass_streak() -> int:
    """Count the most recent consecutive pass records for the art director.

    Only output-worker-review records count — assignment/training rows are excluded
    so they don't interrupt an established streak.
    """
    try:
        records = list_experiments(worker_name="pdf_art_director")
    except Exception:
        return 0
    review_records = [r for r in records if r.benchmark_name == "output-worker-review"]
    streak = 0
    for record in reversed(review_records):
        if record.status == "pass":
            streak += 1
        else:
            break
    return streak


def _review_pdf_art_director(repo_root: Path) -> OutputWorkerReview:
    streak = _pdf_art_director_pass_streak()
    if streak >= _ART_DIRECTOR_GRADUATION_THRESHOLD:
        return OutputWorkerReview(
            worker_name="pdf_art_director",
            status="graduated",
            grade="A",
            rationale=(
                f"The PDF art director has passed {streak} consecutive training reviews. "
                "Visual hierarchy, title treatment, day openings, and front-matter design are stable. "
                "No further training cycles are needed at this time."
            ),
            next_action="Monitor during production runs. Reopen training only if regression appears in real output.",
            evidence=(f"consecutive_passes={streak}",),
        )
    cycle = _latest_pdf_cycle(repo_root)
    assignments = cycle.get("assignments", []) if isinstance(cycle, dict) else []
    findings = cycle.get("agent_review", {}).get("findings", []) if isinstance(cycle, dict) else []
    if assignments:
        return OutputWorkerReview(
            worker_name="pdf_art_director",
            status="active_training",
            grade="C+",
            rationale="The PDF art director now has a defined premium-design assignment, but the visual system is not yet improved enough to claim readiness.",
            next_action="Execute the title page, introduction, and day-hierarchy redesign and then review the resulting proof output.",
            evidence=(
                f"consecutive_passes={streak}",
                f"assignment_count={len(assignments)}",
                f"known_findings={len(findings)}",
            ),
        )
    return OutputWorkerReview(
        worker_name="pdf_art_director",
        status="needs_assignment",
        grade="C",
        rationale="No active PDF art-direction training cycle is present yet.",
        next_action="Run a PDF training cycle and assign the art-direction worker visible product improvements.",
        evidence=(f"consecutive_passes={streak}",),
    )


def _pdf_layout_engineer_pass_streak() -> int:
    """Count the most recent consecutive pass records for the layout engineer.

    Only output-worker-review records count — assignment/training rows are excluded
    so they don't interrupt an established streak.
    """
    try:
        records = list_experiments(worker_name="pdf_layout_engineer")
    except Exception:
        return 0
    review_records = [r for r in records if r.benchmark_name == "output-worker-review"]
    streak = 0
    for record in reversed(review_records):
        if record.status == "pass":
            streak += 1
        else:
            break
    return streak


def _review_pdf_layout_engineer(repo_root: Path) -> OutputWorkerReview:
    streak = _pdf_layout_engineer_pass_streak()
    if streak >= 10:
        return OutputWorkerReview(
            worker_name="pdf_layout_engineer",
            status="graduated",
            grade="A",
            rationale=(
                f"The PDF layout engineer has passed {streak} consecutive training reviews. "
                "Layout safety, overflow protection, and proof-state discipline are stable. "
                "No further training cycles are needed at this time."
            ),
            next_action="Monitor during production runs. Reopen training only if regression appears in real output.",
            evidence=(f"consecutive_passes={streak}",),
        )
    cycle = _latest_pdf_cycle(repo_root)
    suite = cycle.get("agent_review", {}).get("pdf_suite", {}) if isinstance(cycle, dict) else {}
    findings = cycle.get("agent_review", {}).get("findings", []) if isinstance(cycle, dict) else []
    watermark_missing = any("watermark" in str(item).lower() for item in findings)
    if suite:
        return OutputWorkerReview(
            worker_name="pdf_layout_engineer",
            status="active_training",
            grade="B-" if suite.get("passed") else "C+",
            rationale="The engine-level PDF suite is healthy, but product-critical layout work remains, especially proof-state separation and stronger page-safety guarantees.",
            next_action="Add reviewed-proof watermarking and tighten overflow/bottom-margin protection, then rerun the PDF suite and proof checks.",
            evidence=(
                f"pdf_suite_passed={bool(suite.get('passed'))}",
                f"watermark_missing={watermark_missing}",
            ),
        )
    return OutputWorkerReview(
        worker_name="pdf_layout_engineer",
        status="needs_assignment",
        grade="C",
        rationale="No active PDF layout-engineering training cycle is present yet.",
        next_action="Run a PDF training cycle and assign the layout engineer overflow, margin, and proof-state work.",
    )


def build_output_training_manager_review(repo_root: Path) -> dict[str, Any]:
    reviews = [
        _review_pdf_art_director(repo_root),
        _review_pdf_layout_engineer(repo_root),
    ]
    # Graduated workers are complete — only count non-graduated workers as bottleneck candidates
    current_bottleneck = next(
        (item.worker_name for item in reviews if item.status == "active_training"),
        next(
            (item.worker_name for item in reviews if item.status not in {"graduated"}),
            "pdf_art_director",
        ),
    )
    return {
        "production_standard": OUTPUT_PRODUCTION_STANDARD,
        "training_order": ["pdf_art_director", "pdf_layout_engineer"],
        "current_bottleneck_worker": current_bottleneck,
        "reviews": [
            {
                "worker_name": item.worker_name,
                "status": item.status,
                "grade": item.grade,
                "rationale": item.rationale,
                "next_action": item.next_action,
                "evidence": list(item.evidence),
            }
            for item in reviews
        ],
    }


def log_output_training_manager_review(repo_root: Path) -> dict[str, Any]:
    payload = build_output_training_manager_review(repo_root)
    now = _utc_now()
    for review in payload["reviews"]:
        worker_name = str(review["worker_name"])
        review_status = str(review.get("status") or "")
        if review_status == "graduated":
            # Graduated workers are done — no further experiment logging to avoid noise.
            continue
        evidence = [str(item) for item in review.get("evidence", [])]
        if worker_name == "pdf_art_director":
            # Must have run at least one assignment cycle AND have zero known findings.
            # No evidence = no cycle ran = cannot pass.
            has_assignments = any(
                "assignment_count=" in item and not item.endswith("=0")
                for item in evidence
            )
            has_findings = any(
                "known_findings=" in item and not item.endswith("=0")
                for item in evidence
            )
            status = "pass" if (has_assignments and not has_findings) else "fail"
        else:
            # Must have run a PDF suite AND passed it AND have no watermark gap.
            # No evidence = no suite ran = cannot pass.
            suite_ran = any("pdf_suite_passed=" in item for item in evidence)
            suite_passed = any("pdf_suite_passed=True" in item for item in evidence)
            watermark_ok = not any("watermark_missing=True" in item for item in evidence)
            status = "pass" if (suite_ran and suite_passed and watermark_ok) else "fail"
        log_experiment(
            experiment_id=f"{worker_name}-review__{now}",
            worker_name=worker_name,
            benchmark_name="output-worker-review",
            benchmark_reference="reviewed-proof output training",
            status=status,
            attempted_change=f"Reviewed {worker_name} against premium output standards.",
            metrics={
                "evidence_count": len(evidence),
            },
            learning_note=str(review["rationale"]),
            keep_decision="keep" if status == "pass" else "review",
            created_at_utc=now,
            completed_at_utc=now,
        )
    log_experiment(
        experiment_id="output-training-manager__current-cycle",
        worker_name="output_training_manager",
        benchmark_name="output-worker-review",
        benchmark_reference="pdf_art_director -> pdf_layout_engineer",
        status="reviewed",
        attempted_change="Graded output workers against premium publication output standards.",
        metrics={
            "current_bottleneck_worker": payload["current_bottleneck_worker"],
            "review_count": len(payload["reviews"]),
        },
        learning_note=(
            f"Output training manager review completed. Current output bottleneck: {payload['current_bottleneck_worker']}."
        ),
        keep_decision="keep",
        created_at_utc=now,
        completed_at_utc=now,
    )
    return payload
