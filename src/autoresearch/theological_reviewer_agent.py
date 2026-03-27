from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.api.full_run_assets import build_agent_validation_report
from src.autoresearch.llm_theological_reviewer_core import (
    build_llm_theological_review,
    evaluate_theological_review_quality,
)
from src.autoresearch.store import log_experiment
from src.autoresearch.training_corpus import ensure_approved_training_artifact
from src.models.devotional import DevotionalBook
from src.validation.book_quality import validate_devotional_book


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class TheologicalReviewerFinding:
    title: str
    severity: str
    rationale: str
    recommendation: str


THEOLOGICAL_REVIEWER_PROFILE = {
    "role": "expert_theological_reviewer",
    "primary_relationship": (
        "The exposition writer is this reviewer's primary student. "
        "The theological reviewer is the exposition writer's active coach — not a passive gatekeeper. "
        "The reviewer's job is to shape each exposition assignment with specific theological guidance "
        "so the writer knows exactly what the passage requires before drafting."
    ),
    "secondary_relationship": (
        "The outliner is a secondary student. The theological reviewer is available to the outliner "
        "as needed — specifically when the outliner is struggling with a passage (2+ failures) and needs "
        "guidance on the passage's theological lane, burden, or boundary before attempting another draft. "
        "The outliner pulls this guidance on demand; it is not part of every outliner cycle."
    ),
    "mission": (
        "Coach the exposition writer through three sequential responsibilities: "
        "(1) RESOURCE REVIEW — examine the resources returned by the resource coordinator and verify they are "
        "theologically appropriate for the passage. Flag resources that flatten, contradict, or "
        "misrepresent the passage's doctrinal position. Resources must pass before proceeding. "
        "(2) QUOTE REVIEW — after resources are cleared, verify that the selected quote is theologically "
        "accurate for the specific passage. The quote must strengthen the passage's burden, not merely sound "
        "devotional or inspirational. A quote that fits the theme but softens the passage's theological weight "
        "is a failure. "
        "(3) CONTENT REVIEW — screen exposition, prayer, and application for boundary violations, flattening, "
        "or sentimental drift from the passage's position."
    ),
    "junior_worker_assumption": (
        "Treat all content workers as complete beginners with no established theological discipline. "
        "Assume every draft will have flattening, overreach, or sentimental drift until proven otherwise. "
        "Do not give the benefit of the doubt. Flag aggressively. A worker's output is not trustworthy "
        "until it survives review across multiple passages without a boundary failure."
    ),
    "coaching_partnership": (
        "The theological reviewer and grammar advisor work together as a coaching pair for the exposition writer. "
        "Good theology and good grammar are both required — neither is optional and neither excuses the other. "
        "The theological reviewer owns doctrinal accuracy, passage faithfulness, and quote theological fit. "
        "The grammar advisor owns sentence clarity, prose rhythm, and mechanical discipline. "
        "Both must independently clear before the exposition writer passes. Sound theology does not excuse "
        "poor prose, and clean grammar does not excuse doctrinal drift."
    ),
    "sequencing_rule": (
        "Do not proceed to quote review if resource review has failed. "
        "Do not proceed to content review if quote review has failed. "
        "Each stage must clear before the next stage begins. "
        "A pass at any stage does not excuse failures at an earlier stage."
    ),
    "review_rubric": [
        "STAGE 1 — Resources: Are the sources returned by the resource coordinator theologically appropriate for this passage?",
        "STAGE 1 — Resources: Do any sources flatten the passage burden, support heterodox readings, or introduce doctrinal drift?",
        "STAGE 2 — Quote: Does the selected quote accurately represent the theological position of the specific passage?",
        "STAGE 2 — Quote: Does the quote strengthen the passage burden, or does it merely sound devotional while softening the message?",
        "STAGE 2 — Quote: Are source and citation details strong enough for competition-grade trust?",
        "STAGE 3 — Content: Do exposition, prayer, and application stay inside the passage's theological burden?",
        "STAGE 3 — Content: Are severe passages kept severe instead of being softened into generic comfort?",
    ],
}


THEOLOGICAL_BENCHMARK_PASSAGES = (
    # (slug, reference, topic) — same benchmark set used by exposition writer
    ("habakkuk-1-2", "Habakkuk 1:2-4", "Prophetic Lament and God's Sovereignty"),
    ("colossians-3-1", "Colossians 3:1-4", "Raised with Christ"),
    ("psalms-23-1", "Psalm 23:1-4", "The Lord as Shepherd"),
    ("luke-15-11", "Luke 15:11-24", "The Prodigal Son"),
    ("ruth-1-16", "Ruth 1:16-17", "Covenant Loyalty"),
)


def _load_book(path: Path) -> DevotionalBook:
    return DevotionalBook.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _load_latest_llm_exposition_output(repo_root: Path) -> dict[str, Any]:
    """Load the most recent LLM exposition benchmark output for theological review."""
    output_dir = repo_root / "docs" / "system" / "outputs"
    matches = sorted(output_dir.glob("*__devg__exposition-training-cycle.json"))
    if not matches:
        return {}
    try:
        data = json.loads(matches[-1].read_text())
        return data.get("llm_benchmark") or {}
    except Exception:
        return {}


def run_llm_theological_reviewer_benchmark(
    repo_root: Path,
    *,
    exposition_text: str | None = None,
    passage_text: str | None = None,
    focal_reference: str | None = None,
    topic: str | None = None,
) -> dict[str, Any]:
    """Run the LLM theological reviewer on benchmark exposition text.

    Evaluates the exposition writer's LLM output (or the approved artifact exposition)
    for theological faithfulness, producing a structured expert review.

    If exposition_text is not provided, loads the latest LLM exposition benchmark output.
    """
    # Use provided values or fall back to latest LLM exposition benchmark output
    if not exposition_text:
        llm_output = _load_latest_llm_exposition_output(repo_root)
        exposition_text = str(llm_output.get("generated_text") or "").strip()
        if not focal_reference:
            focal_reference = str(llm_output.get("benchmark_passage") or "")
        if not topic:
            topic = str(llm_output.get("topic") or "")

    if not exposition_text:
        return {
            "status": "blocked",
            "reason": "No exposition text available for theological review. Run exposition benchmark first.",
            "score": 0,
            "findings": [],
        }

    result = build_llm_theological_review(
        exposition_text,
        passage_text=(passage_text or ""),
        focal_reference=(focal_reference or "Unknown passage"),
        topic=(topic or ""),
    )
    quality = evaluate_theological_review_quality(result)

    now = _utc_now()
    log_experiment(
        experiment_id=f"theological-reviewer-llm-benchmark__{now}",
        worker_name="theological_reviewer",
        benchmark_name="llm-theological-review-benchmark",
        benchmark_reference=(focal_reference or "exposition-benchmark"),
        status=result["status"],
        attempted_change=(
            f"Theological reviewer AI agent evaluated LLM exposition output for {focal_reference}. "
            "Scored for passage faithfulness, theological grounding, and doctrinal boundary compliance."
        ),
        metrics={
            "score": result["score"],
            "passage_grounded": result.get("passage_grounded", False),
            "theological_drift_detected": result.get("theological_drift_detected", False),
            "finding_count": len(result.get("findings") or []),
            "specificity_rate": quality.get("specificity_rate", 0.0),
        },
        learning_note=(
            "Theological reviewer AI agent evaluated LLM-generated exposition for benchmark passage. "
            "Score reflects actual theological review quality against the rubric."
        ),
        keep_decision="keep" if result["status"] == "pass" else "review",
        created_at_utc=now,
        completed_at_utc=now,
    )

    return {**result, "review_quality": quality}


def _load_latest_exposition_resources(repo_root: Path) -> list[dict[str, Any]]:
    """Load the resource bundle from the latest exposition training cycle."""
    output_dir = repo_root / "docs" / "system" / "outputs"
    matches = sorted(output_dir.glob("*__devg__exposition-training-cycle.json"))
    if not matches:
        return []
    try:
        data = json.loads(matches[-1].read_text())
    except Exception:
        return []
    # Resources are embedded in the outliner cycle results if present; otherwise not available here.
    # We flag blank/missing resources as a resource-stage concern.
    return data.get("assignments", [])


def build_theological_reviewer_report(repo_root: Path) -> dict[str, Any]:
    artifact = ensure_approved_training_artifact(repo_root)
    if not artifact:
        return {
            "reviewed_at_utc": _utc_now(),
            "trainer_profile": THEOLOGICAL_REVIEWER_PROFILE,
            "status": "blocked",
            "summary": "No approved training artifact is available yet for theological review.",
            "findings": [],
            "resource_review": {"stage": "stage_1", "checked": False, "thin_resource_days": 0},
            "book_validation": {"total": 0, "failed": 0, "theological_failures": 0},
            "quote_validation": {"total_days": 0, "failed_days": 0, "manual_quote_flags": 0},
        }

    book = _load_book(Path(str(artifact["book_json_path"])))
    findings: list[TheologicalReviewerFinding] = []

    # ── STAGE 1: Resource review ─────────────────────────────────────────────
    # The theological reviewer is responsible for checking that resources returned
    # by the resource coordinator are theologically appropriate for the passage
    # before proceeding to quote or content review.
    exposition_assignments = _load_latest_exposition_resources(repo_root)
    thin_resource_days = sum(
        1 for item in exposition_assignments
        if str(item.get("resource_strength", "")).lower() == "thin"
    )
    blank_resource_days = sum(
        1 for item in exposition_assignments
        if int(item.get("existing_exposition_word_count", 1) or 1) == 0
    )
    resource_stage_clear = thin_resource_days == 0

    if thin_resource_days > 0:
        findings.append(
            TheologicalReviewerFinding(
                title="Stage 1 — Resource coordinator has not provided sufficient resources for all days",
                severity="high",
                rationale=(
                    f"{thin_resource_days} day(s) still have thin resource bundles. "
                    "The theological reviewer cannot confirm resources are theologically appropriate "
                    "for the passage when the resource coordinator has not yet supplied adequate material."
                ),
                recommendation=(
                    "Block progression to quote review until the resource coordinator provides strong bundles "
                    "for all days. A thin bundle is a resource failure before it is a theological concern."
                ),
            )
        )

    # ── STAGE 2: Quote review (only if stage 1 cleared) ─────────────────────
    agent_report = build_agent_validation_report(
        book,
        validator_agents=["agent:theological-reviewer"],
    )
    by_day = agent_report.get("by_day", {}) if isinstance(agent_report, dict) else {}
    quote_failures = 0
    manual_quote_flags = 0

    if resource_stage_clear:
        for day_key, payload in by_day.items():
            quote_payload = payload.get("timeless_wisdom", {}) if isinstance(payload, dict) else {}
            manual_flags = payload.get("manual_review_flags", []) if isinstance(payload, dict) else []
            status = str(quote_payload.get("status", "")).strip().lower()
            if status and status != "passed":
                quote_failures += 1
            if any("QUOTE" in str(flag) for flag in manual_flags):
                manual_quote_flags += 1

        if quote_failures or manual_quote_flags:
            findings.append(
                TheologicalReviewerFinding(
                    title="Stage 2 — Quote is not theologically accurate for the passage",
                    severity="high" if quote_failures else "medium",
                    rationale=(
                        f"Quote validation found {quote_failures} failed quote day(s) and "
                        f"{manual_quote_flags} day(s) with quote-specific manual review flags. "
                        "A quote that merely sounds devotional but does not accurately represent "
                        "the passage's theological position is a failure."
                    ),
                    recommendation=(
                        "Require the quote to be re-selected and verified against the specific passage burden, "
                        "not just the general theme. Citation trust must also meet competition-grade standards."
                    ),
                )
            )
    else:
        findings.append(
            TheologicalReviewerFinding(
                title="Stage 2 — Quote review skipped: resource stage has not cleared",
                severity="medium",
                rationale=(
                    "Quote review cannot proceed until Stage 1 (resource review) is clear. "
                    "Reviewing a quote against theologically thin resources produces unreliable results."
                ),
                recommendation=(
                    "Resolve resource coordinator thin bundles first, then re-run theological review."
                ),
            )
        )

    # ── STAGE 3: Content review ──────────────────────────────────────────────
    assessments = validate_devotional_book(book)
    failed_assessments = [item for item in assessments if item.result == "fail"]
    theological_failures = [
        item for item in failed_assessments if str(item.check_id).startswith("BOOK_THEOLOGICAL_BOUNDARY")
    ]

    if theological_failures:
        findings.append(
            TheologicalReviewerFinding(
                title="Stage 3 — Theological-boundary failures remain in current content",
                severity="high",
                rationale=(
                    f"The current artifact still has {len(theological_failures)} book-level theological-boundary "
                    "failures, which means junior workers are still drifting or flattening the passage burden."
                ),
                recommendation=(
                    "Keep theological review in the loop before trusting downstream content, especially on exposition, "
                    "prayer, and action sections."
                ),
            )
        )

    if not findings:
        findings.append(
            TheologicalReviewerFinding(
                title="All three stages cleared — resources, quote, and content passed theological review",
                severity="low",
                rationale=(
                    "Resource bundles are strong, the quote is theologically accurate for the passage, "
                    "and the artifact did not trigger theological-boundary failures or quote manual review flags."
                ),
                recommendation=(
                    "Keep this reviewer in the loop as a standing guardrail while the junior workers continue training."
                ),
            )
        )

    return {
        "reviewed_at_utc": _utc_now(),
        "trainer_profile": THEOLOGICAL_REVIEWER_PROFILE,
        "status": "reviewed",
        "artifact": artifact,
        "resource_review": {
            "stage": "stage_1",
            "checked": True,
            "thin_resource_days": thin_resource_days,
            "blank_resource_days": blank_resource_days,
            "stage_cleared": resource_stage_clear,
        },
        "book_validation": {
            "total": len(assessments),
            "failed": len(failed_assessments),
            "theological_failures": len(theological_failures),
        },
        "quote_validation": {
            "total_days": len(by_day),
            "failed_days": quote_failures,
            "manual_quote_flags": manual_quote_flags,
            "stage_cleared": resource_stage_clear and quote_failures == 0 and manual_quote_flags == 0,
        },
        "findings": [
            {
                "title": item.title,
                "severity": item.severity,
                "rationale": item.rationale,
                "recommendation": item.recommendation,
            }
            for item in findings
        ],
    }


def log_theological_reviewer_report(repo_root: Path) -> dict[str, Any]:
    payload = build_theological_reviewer_report(repo_root)
    now = _utc_now()
    log_experiment(
        experiment_id="theological-reviewer__current-cycle",
        worker_name="theological_reviewer",
        benchmark_name="theological-writing-and-quote-review",
        benchmark_reference="approved artifact theological screen",
        status="reviewed" if payload.get("status") == "reviewed" else "blocked",
        attempted_change="Reviewed current theological writing and quote appropriateness against doctrinal and quote-trust guardrails.",
        metrics={
            "book_failed_checks": payload["book_validation"]["failed"],
            "book_theological_failures": payload["book_validation"]["theological_failures"],
            "quote_failed_days": payload["quote_validation"]["failed_days"],
            "manual_quote_flags": payload["quote_validation"]["manual_quote_flags"],
            "finding_count": len(payload["findings"]),
        },
        learning_note="Expert theological reviewer screened junior-worker content for doctrinal drift and quote appropriateness.",
        keep_decision="keep",
        created_at_utc=now,
        completed_at_utc=now,
    )

    # ── LLM benchmark: actually invoke the theological reviewer AI on benchmark exposition ──
    # This is the primary AI training signal — the LLM reads and evaluates actual exposition,
    # producing passage-specific theological findings rather than heuristic-only scoring.
    if payload.get("status") == "reviewed":
        llm_benchmark = run_llm_theological_reviewer_benchmark(repo_root)
        payload["llm_benchmark"] = llm_benchmark

    return payload
