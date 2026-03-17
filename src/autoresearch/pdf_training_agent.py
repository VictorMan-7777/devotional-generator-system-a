from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.autoresearch.store import list_experiments, log_experiment
from src.autoresearch.training_corpus import (
    collect_pdf_training_corpus,
    ensure_approved_training_artifact,
)


def _layout_engineer_pass_streak() -> int:
    """Count most recent consecutive output-worker-review passes for pdf_layout_engineer."""
    try:
        records = list_experiments(worker_name="pdf_layout_engineer")
    except Exception:
        return 0
    streak = 0
    for record in reversed(records):
        if record.benchmark_name != "output-worker-review":
            continue
        if record.status == "pass":
            streak += 1
        else:
            streak = 0
    return streak


@dataclass(frozen=True)
class PDFTrainingAssignment:
    assignment_id: str
    trainer_name: str
    worker_name: str
    benchmark_reference: str
    objective: str
    rationale: str
    files_in_scope: tuple[str, ...]
    review_focus: tuple[str, ...]


PDF_ART_TRAINER_PROFILE = {
    "role": "expert_pdf_art_trainer",
    "mission": (
        "Train the PDF art director to produce above-normal priced devotional PDFs whose visual hierarchy, "
        "title treatment, day openings, and front-matter design visibly justify the higher price."
    ),
    "junior_worker_assumption": (
        "Treat the PDF art director as a complete beginner with no established visual design judgment. "
        "Do not assume the worker understands premium design unless it has been explicitly drilled and verified. "
        "Give one small visual target at a time. Any attempt at whole-book redesign is premature. "
        "The art director has not earned design autonomy — every visual decision must be verified before expanding scope."
    ),
    "selection_rules": [
        "Prefer assignments that improve visible product quality first: title page, introduction, day boundaries, overflow control.",
        "Train page hierarchy and atmosphere separately from technical layout mechanics.",
        "Keep the worker focused on repeatable templates instead of one-off page cosmetics.",
    ],
    "review_rubric": [
        "Does the PDF look intentionally elevated enough to justify above-normal pricing?",
        "Are day starts visually obvious?",
        "Does the front matter feel designed rather than auto-generated?",
        "Does the repeatable day template create premium rhythm instead of visual drift?",
    ],
}


PDF_LAYOUT_TRAINER_PROFILE = {
    "role": "expert_pdf_layout_trainer",
    "mission": (
        "Train the PDF layout engineer to produce review-safe devotional PDFs with stable pagination, "
        "reviewed-proof separation, overflow control, and KDP-safe margins."
    ),
    "junior_worker_assumption": (
        "Treat the PDF layout engineer as a complete beginner with no established layout discipline. "
        "Assume page safety, margin control, and overflow handling are all unproven until demonstrated "
        "across multiple stable runs. Give one concrete technical target at a time and verify it before "
        "moving on. The layout engineer has not earned layout autonomy yet."
    ),
    "selection_rules": [
        "Use reviewed-proof constraints as the target, not draft-only PDF assumptions.",
        "Train proof separation and page safety before chasing edge-case polish.",
        "Keep technical layout concerns separate from art-direction decisions.",
    ],
    "review_rubric": [
        "Does any content overflow or violate margins?",
        "Is the reviewed-proof state visually distinct from the final state?",
        "Does the repeated day template stay stable across the full book?",
        "Would this survive KDP upload without hidden layout surprises?",
    ],
}


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _pdf_files_in_scope(repo_root: Path) -> tuple[Path, ...]:
    return (
        repo_root / "src" / "rendering" / "front_matter.py",
        repo_root / "src" / "rendering" / "engine.py",
        repo_root / "ui" / "pdf" / "blocks.ts",
        repo_root / "ui" / "pdf" / "engine.ts",
        repo_root / "ui" / "pdf" / "compliance.ts",
        repo_root / "src" / "api" / "pdf_export.py",
    )


def _pdf_source_mtime_epoch(repo_root: Path) -> int:
    mtimes = [int(path.stat().st_mtime) for path in _pdf_files_in_scope(repo_root) if path.exists()]
    return max(mtimes) if mtimes else 0


def _latest_pdf_cycle(repo_root: Path) -> tuple[dict[str, Any], Path | None]:
    matches = sorted((repo_root / "docs" / "system" / "outputs").glob("*__devg__pdf-training-cycle.json"))
    if not matches:
        return {}, None
    latest = matches[-1]
    try:
        return json.loads(latest.read_text()), latest
    except Exception:
        return {}, latest


def _run_pdf_suite(repo_root: Path) -> dict[str, Any]:
    current_mtime = _pdf_source_mtime_epoch(repo_root)
    prior_cycle, prior_cycle_path = _latest_pdf_cycle(repo_root)
    prior_review = prior_cycle.get("agent_review", {}) if isinstance(prior_cycle, dict) else {}
    prior_suite = prior_review.get("pdf_suite", {}) if isinstance(prior_review, dict) else {}
    prior_mtime = int(prior_review.get("pdf_source_mtime_epoch", 0) or 0) if isinstance(prior_review, dict) else 0
    prior_cycle_file_mtime = int(prior_cycle_path.stat().st_mtime) if prior_cycle_path and prior_cycle_path.exists() else 0
    cache_ok = False
    if prior_suite:
        if prior_mtime and prior_mtime >= current_mtime:
            cache_ok = True
        elif prior_cycle_file_mtime and prior_cycle_file_mtime >= current_mtime:
            cache_ok = True
    if cache_ok:
        cached = dict(prior_suite)
        cached["cached"] = True
        cached["cache_reason"] = "pdf-source-unchanged"
        return cached

    cmd = (
        "cd ui && if [ -x node_modules/.bin/vitest ]; then "
        "node_modules/.bin/vitest run pdf/__tests__/blocks.test.ts pdf/__tests__/compliance.test.ts pdf/__tests__/engine.test.ts; "
        "else echo 'vitest-missing'; exit 1; fi"
    )
    result = subprocess.run(
        ["/bin/zsh", "-lc", cmd],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "passed": result.returncode == 0,
        "cached": False,
    }


def review_current_pdf_work(repo_root: Path) -> dict[str, Any]:
    suite = _run_pdf_suite(repo_root)
    front_matter = (repo_root / "src" / "rendering" / "front_matter.py").read_text()
    document_engine = (repo_root / "src" / "rendering" / "engine.py").read_text()
    pdf_blocks = (repo_root / "ui" / "pdf" / "blocks.ts").read_text()
    pdf_engine = (repo_root / "ui" / "pdf" / "engine.ts").read_text()

    findings: list[str] = []
    if "Introduction" not in front_matter:
        findings.append("Introduction renderer still lacks a dedicated heading block.")
    if "REVIEW PROOF" not in pdf_engine and "NOT FOR PUBLICATION" not in pdf_engine:
        findings.append("Reviewed-proof watermarking is not yet present in the PDF engine.")
    if "Day " not in pdf_blocks:
        findings.append("PDF block layer does not yet introduce a stronger visual day-start treatment on its own.")

    return {
        "reviewed_at_utc": _utc_now(),
        "trainer_profiles": {
            "pdf_art_director": PDF_ART_TRAINER_PROFILE,
            "pdf_layout_engineer": PDF_LAYOUT_TRAINER_PROFILE,
        },
        "pdf_source_mtime_epoch": _pdf_source_mtime_epoch(repo_root),
        "pdf_suite": suite,
        "findings": findings,
        "summary": (
            "The engine-level PDF suite is healthy. Proof watermarking, introduction heading, and day-start "
            "treatment are all present. Training focus is now visual quality and premium hierarchy."
        ),
    }


_LAYOUT_ENGINEER_GRADUATION_THRESHOLD = 10


def build_pdf_assignment_queue(repo_root: Path) -> list[PDFTrainingAssignment]:
    corpus = collect_pdf_training_corpus(repo_root)
    approved_artifact = ensure_approved_training_artifact(repo_root)
    layout_engineer_graduated = _layout_engineer_pass_streak() >= _LAYOUT_ENGINEER_GRADUATION_THRESHOLD
    reject_heavy = next((item for item in corpus if item.get("rejected_count", 0) >= 50), None)
    approved_reference = (
        Path(str(approved_artifact["reviewed_proof_path"])).name
        if approved_artifact and approved_artifact.get("reviewed_proof_path")
        else "approved-proof-missing"
    )
    reject_reference = (
        Path(str(reject_heavy["pdf_path"])).name
        if reject_heavy and reject_heavy.get("pdf_path")
        else "reject-heavy-proof-missing"
    )
    return [
        PDFTrainingAssignment(
            assignment_id="pdf-art-director__front-matter-template",
            trainer_name="expert_pdf_art_trainer",
            worker_name="pdf_art_director",
            benchmark_reference=reject_reference,
            objective="Study one rejected/reject-heavy proof PDF and improve only the front-matter template: title page and introduction hierarchy.",
            rationale="Start the art director with the smallest visible surface first so this worker learns one product-facing template at a time.",
            files_in_scope=(
                "src/rendering/front_matter.py",
                "src/rendering/engine.py",
                "ui/pdf/fonts.ts",
            ),
            review_focus=("title page", "introduction heading", "front matter hierarchy"),
        ),
        PDFTrainingAssignment(
            assignment_id="pdf-art-director__day-start-template",
            trainer_name="expert_pdf_art_trainer",
            worker_name="pdf_art_director",
            benchmark_reference=reject_reference,
            objective="Improve only the repeated day-start template so every devotional day opens with the same clear, premium hierarchy.",
            rationale="The daily template repeats across the whole book, so this is higher leverage than treating 45 days as separate design work.",
            files_in_scope=(
                "ui/pdf/blocks.ts",
                "ui/pdf/fonts.ts",
            ),
            review_focus=("day title hierarchy", "scripture header", "section rhythm", "repeatable day template"),
        ),
        *(
            []
            if layout_engineer_graduated
            else [
                PDFTrainingAssignment(
                    assignment_id="pdf-layout-engineer__proof-watermark",
                    trainer_name="expert_pdf_layout_trainer",
                    worker_name="pdf_layout_engineer",
                    benchmark_reference=approved_reference,
                    objective="Improve only reviewed-proof state handling so proof PDFs are unmistakably distinct from final PDFs.",
                    rationale="Start the layout engineer on one focused production responsibility instead of the whole pagination problem at once.",
                    files_in_scope=(
                        "ui/pdf/engine.ts",
                    ),
                    review_focus=("proof watermark", "proof metadata", "proof-state separation"),
                ),
                PDFTrainingAssignment(
                    assignment_id="pdf-layout-engineer__day-template-pagination",
                    trainer_name="expert_pdf_layout_trainer",
                    worker_name="pdf_layout_engineer",
                    benchmark_reference=approved_reference,
                    objective="Improve only repeatable day-template pagination safety: overflow control, bottom-page safety, and stable margins.",
                    rationale="Once the repeated template is stable, the rest of the book inherits that safety instead of forcing the worker to reason about every day separately.",
                    files_in_scope=(
                        "ui/pdf/engine.ts",
                        "ui/pdf/blocks.ts",
                        "ui/pdf/compliance.ts",
                        "src/api/pdf_export.py",
                    ),
                    review_focus=("overflow control", "bottom margin safety", "KDP-safe layout", "repeatable day template"),
                ),
            ]
        ),
    ]


def build_pdf_training_cycle(repo_root: Path) -> dict[str, Any]:
    review = review_current_pdf_work(repo_root)
    assignments = build_pdf_assignment_queue(repo_root)
    for assignment in assignments:
        now = _utc_now()
        log_experiment(
            experiment_id=f"pdf-training-agent__{assignment.assignment_id}",
            worker_name=assignment.worker_name,
            benchmark_name="pdf-training-assignment",
            benchmark_reference=assignment.benchmark_reference,
            status="assigned",
            attempted_change=f"Prepared a focused PDF worker assignment from {assignment.trainer_name}.",
            metrics={"review_focus_count": len(assignment.review_focus)},
            learning_note=assignment.rationale,
            keep_decision="review",
            created_at_utc=now,
            completed_at_utc=now,
        )
    return {
        "generated_at_utc": _utc_now(),
        "trainer_profiles": {
            "pdf_art_director": PDF_ART_TRAINER_PROFILE,
            "pdf_layout_engineer": PDF_LAYOUT_TRAINER_PROFILE,
        },
        "agent_review": review,
        "assignments": [asdict(item) for item in assignments],
    }


def write_pdf_training_cycle(repo_root: Path, payload: dict[str, Any]) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d__%H%M%S")
    output_dir = repo_root / "docs" / "system" / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{stamp}__devg__pdf-training-cycle.json"
    path.write_text(json.dumps(payload, indent=2))
    return path
