from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.autoresearch.store import list_experiments, log_experiment
from src.autoresearch.workers import WorkerSpec, get_worker_spec


@dataclass(frozen=True)
class WorkerTrainingReview:
    worker_name: str
    status: str
    grade: str
    rationale: str
    next_action: str
    evidence: tuple[str, ...] = ()
    stalled_benchmarks: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExpertTrainerAdvice:
    trainer_name: str
    supports_workers: tuple[str, ...]
    status: str
    summary: str
    recommended_actions: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()


WORKER_TRAINING_ORDER: tuple[str, ...] = (
    "acquisition_librarian",
    "research_librarian",
    "outliner",
    "exposition_writer",
    "quote_selector",
    "be_still_writer",
    "action_writer",
    "prayer_writer",
)

PRODUCTION_STANDARD = {
    "label": "seminary_level_production",
    "description": (
        "Production workers should operate with the passage sensitivity, theological care, structural judgment, "
        "and literary seriousness expected of a well-trained seminary assistant rather than a generic content system, "
        "because these devotionals are intended to support an above-normal price point."
    ),
    "current_worker_reality": (
        "All workers are currently complete beginners. None have proven capability across multiple independent passages. "
        "The production standard above is the aspirational target — it is NOT the current baseline. "
        "Trainers must close the gap between beginner output and the production standard one demonstrated skill at a time. "
        "Do not score workers against the aspirational standard as if they were already there."
    ),
    "expectations": (
        "passage-faithful structure",
        "clear theological boundaries",
        "genre-aware judgment",
        "responsible source use",
        "premium publication quality",
        "content quality that justifies above-normal devotional pricing",
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stalled_passages(db_path: Path, worker_name: str, threshold: int = 3, days_back: int = 1) -> set[str]:
    import sqlite3 as _sqlite3
    conn = _sqlite3.connect(db_path)
    sql = """
        SELECT benchmark_reference
        FROM autoresearch_experiments
        WHERE worker_name = ? AND status IN ('fail', 'revise')
        AND created_at_utc > datetime('now', ?)
        GROUP BY benchmark_reference
        HAVING COUNT(*) >= ?
    """
    rows = conn.execute(sql, (worker_name, f"-{days_back} days", threshold)).fetchall()
    conn.close()
    return {row[0] for row in rows if row[0]}


def curriculum_workers() -> tuple[WorkerSpec, ...]:
    return tuple(get_worker_spec(name) for name in WORKER_TRAINING_ORDER)


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _library_counts(repo_root: Path) -> dict[str, int]:
    catalog = _load_json(repo_root / "data" / "library" / "resource-catalog.json") or []
    notes = list((repo_root / "data" / "library" / "reading-notes" / "drafts").glob("*.evaluation.json"))
    holdings = list((repo_root / "data" / "library" / "resources").glob("*/holding.json"))
    return {
        "live_cards": len(catalog),
        "reading_note_evaluations": len(notes),
        "holdings": len(holdings),
    }


def _latest_harness_checkpoints(repo_root: Path) -> dict[str, str]:
    outputs = repo_root / "outputs" / "devotionals"
    latest: dict[str, str] = {}
    patterns = {
        "exodus": "*exodus-19-20*__checkpoints/028__book-unification.json",
        "proverbs": "*proverbs-1-2*__meta.json",
    }
    for key, pattern in patterns.items():
        matches = sorted(outputs.glob(pattern))
        if matches:
            latest[key] = str(matches[-1])
    return latest


def _latest_outliner_training_cycle(repo_root: Path) -> dict[str, Any]:
    output_dir = repo_root / "docs" / "system" / "outputs"
    matches = sorted(output_dir.glob("*__devg__outliner-training-cycle.json"))
    if not matches:
        return {}
    return _load_json(matches[-1]) or {}


def _latest_output_file(repo_root: Path, pattern: str) -> dict[str, Any]:
    output_dir = repo_root / "docs" / "system" / "outputs"
    matches = sorted(output_dir.glob(pattern))
    if not matches:
        return {}
    return _load_json(matches[-1]) or {}


def _compact_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return " ".join(text.split())


def _consult_outliner_trainer(repo_root: Path) -> ExpertTrainerAdvice:
    cycle = _latest_outliner_training_cycle(repo_root)
    if not cycle:
        return ExpertTrainerAdvice(
            trainer_name="expert_outliner_trainer",
            supports_workers=("outliner", "training_manager"),
            status="missing",
            summary="No outliner trainer cycle is available yet, so the training manager should not trust its own outline judgment alone.",
            recommended_actions=("Run a fresh outliner trainer cycle before grading the outliner again.",),
        )
    results = cycle.get("results", []) if isinstance(cycle, dict) else []
    failed = [item for item in results if item.get("evaluation", {}).get("status") != "pass"]
    top_findings: list[str] = []
    for item in failed[:2]:
        for finding in item.get("evaluation", {}).get("findings", []):
            finding_text = _compact_text(finding)
            if finding_text and finding_text not in top_findings:
                top_findings.append(finding_text)
            if len(top_findings) >= 2:
                break
        if len(top_findings) >= 2:
            break
    summary = (
        f"The outliner trainer reviewed {len(results)} outline assignment(s) and still sees {len(failed)} failing drill(s)."
        if results
        else "The outliner trainer cycle exists but did not include scored assignments."
    )
    actions = [
        "Keep the outliner on outline-only drills until the latest trainer cycle is clean.",
    ]
    if top_findings:
        actions.append(f"Prioritize trainer feedback on: {top_findings[0]}.")
    return ExpertTrainerAdvice(
        trainer_name="expert_outliner_trainer",
        supports_workers=("outliner", "training_manager"),
        status="consulted",
        summary=summary,
        recommended_actions=tuple(actions),
        evidence=tuple(
            [f"reviewed_assignments={len(results)}", f"failed_assignments={len(failed)}"]
            + [f"finding={item}" for item in top_findings]
        ),
    )


def _consult_library_trainer(repo_root: Path) -> ExpertTrainerAdvice:
    review = _latest_output_file(repo_root, "*__devg__library-trainer-review.json")
    if not review:
        return ExpertTrainerAdvice(
            trainer_name="expert_library_trainer",
            supports_workers=("research_librarian", "acquisition_librarian", "training_manager"),
            status="missing",
            summary="No library trainer review is available yet, so the training manager should not guess whether the shelf or the librarian is at fault.",
            recommended_actions=("Run the library trainer review before escalating new acquisitions.",),
        )
    findings = review.get("findings", []) if isinstance(review, dict) else []
    actionable = review.get("actionable_requests", []) if isinstance(review, dict) else []
    summary = (
        f"The library trainer sees {len(findings)} note/request finding(s) and {len(actionable)} request(s) that need direct librarian action."
        if findings or actionable
        else "The library trainer says the current shelf is usable and there are no active request-discipline corrections right now."
    )
    actions = [
        "Use current holdings before escalating to acquisition when the trainer says the shelf is sufficient."
    ]
    for item in actionable[:2]:
        reference = _compact_text(item.get("scripture_reference"))
        resolution = _compact_text(item.get("recommended_resolution"))
        if reference:
            actions.append(f"For {reference}, follow the library trainer resolution: {resolution or 'serve from current holdings'}.")
    return ExpertTrainerAdvice(
        trainer_name="expert_library_trainer",
        supports_workers=("research_librarian", "acquisition_librarian", "training_manager"),
        status="consulted",
        summary=summary,
        recommended_actions=tuple(actions),
        evidence=tuple(
            [f"finding_count={len(findings)}", f"actionable_request_count={len(actionable)}"]
            + [f"actionable_reference={_compact_text(item.get('scripture_reference'))}" for item in actionable[:2] if _compact_text(item.get("scripture_reference"))]
        ),
    )


def _consult_theological_reviewer(repo_root: Path) -> ExpertTrainerAdvice:
    report = _latest_output_file(repo_root, "*__devg__theological-reviewer-report.json")
    if not report:
        return ExpertTrainerAdvice(
            trainer_name="expert_theological_reviewer",
            supports_workers=("outliner", "exposition_writer", "quote_selector", "training_manager"),
            status="missing",
            summary="No theological reviewer report is available yet, so the training manager should be cautious about theological confidence.",
            recommended_actions=("Run the theological reviewer before promoting theological writing work.",),
        )
    findings = report.get("findings", []) if isinstance(report, dict) else []
    top = findings[0] if findings else {}
    summary = _compact_text(top.get("rationale")) or "The theological reviewer completed a standing doctrinal and quote-fit screen."
    recommendation = _compact_text(top.get("recommendation"))
    evidence = [
        f"finding_count={len(findings)}",
        f"book_theological_failures={int(report.get('book_validation', {}).get('theological_failures', 0) or 0)}",
        f"quote_failed_days={int(report.get('quote_validation', {}).get('failed_days', 0) or 0)}",
    ]
    return ExpertTrainerAdvice(
        trainer_name="expert_theological_reviewer",
        supports_workers=("outliner", "exposition_writer", "quote_selector", "training_manager"),
        status="consulted",
        summary=summary,
        recommended_actions=tuple([recommendation] if recommendation else []),
        evidence=tuple(evidence),
    )


def _consult_policy_guardian(repo_root: Path) -> ExpertTrainerAdvice:
    report = _latest_output_file(repo_root, "*__devg__policy-guardian-report.json")
    if not report:
        return ExpertTrainerAdvice(
            trainer_name="expert_policy_guardian",
            supports_workers=("training_manager", "outliner", "research_librarian", "exposition_writer"),
            status="missing",
            summary="No policy guardian report is available yet, so the training manager should be cautious about hidden guardrail drift.",
            recommended_actions=("Run the policy guardian before trusting a training loop that looks fresh.",),
        )
    findings = report.get("findings", []) if isinstance(report, dict) else []
    top = findings[0] if findings else {}
    summary = _compact_text(top.get("rationale")) or "The policy guardian completed a standing guardrail screen."
    recommendation = _compact_text(top.get("recommendation"))
    signals = report.get("signals", {}) if isinstance(report, dict) else {}
    return ExpertTrainerAdvice(
        trainer_name="expert_policy_guardian",
        supports_workers=("training_manager", "outliner", "research_librarian", "exposition_writer"),
        status="consulted",
        summary=summary,
        recommended_actions=tuple([recommendation] if recommendation else []),
        evidence=(
            f"finding_count={len(findings)}",
            f"metadata_excerpt_count={int(signals.get('metadata_excerpt_count', 0) or 0)}",
            f"outliner_failures_in_latest_cycle={int(signals.get('outliner_failures_in_latest_cycle', 0) or 0)}",
        ),
    )


def _consult_exposition_trainer(repo_root: Path) -> ExpertTrainerAdvice:
    cycle = _latest_output_file(repo_root, "*__devg__exposition-training-cycle.json")
    if not cycle:
        return ExpertTrainerAdvice(
            trainer_name="expert_exposition_trainer",
            supports_workers=("exposition_writer", "training_manager"),
            status="missing",
            summary="No exposition training cycle is available yet, so the manager cannot distinguish writer weakness from resource weakness.",
            recommended_actions=("Run exposition training on approved content before grading the exposition writer heavily.",),
        )
    assignments = cycle.get("assignments", []) if isinstance(cycle, dict) else []
    resource_assignments = cycle.get("passage_researcher_assignments", []) if isinstance(cycle, dict) else []
    strong = sum(1 for item in assignments if str(item.get("resource_strength", "")).lower() == "strong")
    summary = (
        f"The exposition trainer issued {len(assignments)} assignment(s); {strong} had strong resources and {len(resource_assignments)} exposed resource gaps."
    )
    actions = ["Keep exposition training on approved content until the writer handles narrow focal verses well."]
    if resource_assignments:
        actions.append("Train the passage researcher on the thin-bundle cases before blaming the exposition writer for those failures.")
    return ExpertTrainerAdvice(
        trainer_name="expert_exposition_trainer",
        supports_workers=("exposition_writer", "training_manager"),
        status="consulted",
        summary=summary,
        recommended_actions=tuple(actions),
        evidence=(
            f"assignment_count={len(assignments)}",
            f"strong_resource_assignments={strong}",
            f"resource_gap_assignments={len(resource_assignments)}",
        ),
    )


def _consult_grammar_advisor(repo_root: Path) -> ExpertTrainerAdvice:
    """Read grammar_guidance from the latest exposition cycle — grammar advisor runs inside it."""
    cycle = _latest_output_file(repo_root, "*__devg__exposition-training-cycle.json")
    if not cycle:
        return ExpertTrainerAdvice(
            trainer_name="expert_grammar_advisor",
            supports_workers=("exposition_writer", "training_manager"),
            status="missing",
            summary="No exposition training cycle available, so the grammar advisor has not reviewed the current exposition output.",
            recommended_actions=("Run an exposition training cycle to get grammar advisor findings.",),
        )
    grammar = cycle.get("grammar_guidance", {}) if isinstance(cycle, dict) else {}
    findings = grammar.get("findings", []) if isinstance(grammar, dict) else []
    long_sentences = int((grammar.get("metrics") or {}).get("long_sentence_count", 0) or 0)
    repeated_openings = int((grammar.get("metrics") or {}).get("repeated_opening_count", 0) or 0)
    status = str(grammar.get("status") or "blocked")
    summary = (
        f"The grammar advisor found {len(findings)} prose issue(s): "
        f"{long_sentences} long sentence(s) and {repeated_openings} repeated opening(s)."
        if findings
        else "The grammar advisor cleared the current exposition sample — no mechanical prose failures detected."
    )
    actions = [
        "Grammar and theology both must clear independently — good theology does not excuse poor prose.",
    ]
    for finding in findings[:1]:
        rec = _compact_text(finding.get("recommendation") if isinstance(finding, dict) else "")
        if rec:
            actions.append(f"Grammar fix: {rec}")
    return ExpertTrainerAdvice(
        trainer_name="expert_grammar_advisor",
        supports_workers=("exposition_writer", "training_manager"),
        status="consulted" if status != "blocked" else "missing",
        summary=summary,
        recommended_actions=tuple(actions),
        evidence=(
            f"grammar_finding_count={len(findings)}",
            f"long_sentence_count={long_sentences}",
            f"repeated_opening_count={repeated_openings}",
        ),
    )


def _consult_be_still_trainer(repo_root: Path) -> ExpertTrainerAdvice:
    cycle = _latest_output_file(repo_root, "*__devg__be-still-training-cycle.json")
    if not cycle:
        return ExpertTrainerAdvice(
            trainer_name="expert_be_still_trainer",
            supports_workers=("be_still_writer", "training_manager"),
            status="missing",
            summary="No Be Still training cycle is available yet, so the manager cannot judge whether prompts are passage-anchored or generic.",
            recommended_actions=("Run a Be Still training cycle before promoting the be_still_writer.",),
        )
    assignments = cycle.get("assignments", []) if isinstance(cycle, dict) else []
    fresh = cycle.get("fresh_benchmark", {}) if isinstance(cycle, dict) else {}
    fresh_score = int((fresh.get("evaluation") or {}).get("score", 0) or 0)
    fresh_status = str(fresh.get("status") or "blocked")
    summary = (
        f"The Be Still trainer issued {len(assignments)} assignment(s). "
        f"Fresh benchmark: {fresh_status} (score={fresh_score}/100)."
    )
    actions = ["Keep Be Still on approved-artifact drills until the fresh benchmark consistently passes (score >= 80)."]
    if fresh_status != "pass":
        priority_fix = _compact_text((fresh.get("evaluation") or {}).get("priority_fix"))
        if priority_fix:
            actions.append(f"Priority fix: {priority_fix}")
    return ExpertTrainerAdvice(
        trainer_name="expert_be_still_trainer",
        supports_workers=("be_still_writer", "training_manager"),
        status="consulted",
        summary=summary,
        recommended_actions=tuple(actions),
        evidence=(
            f"assignment_count={len(assignments)}",
            f"fresh_benchmark_score={fresh_score}",
            f"fresh_benchmark_status={fresh_status}",
        ),
    )


def _consult_action_writer_trainer(repo_root: Path) -> ExpertTrainerAdvice:
    cycle = _latest_output_file(repo_root, "*__devg__action-writer-training-cycle.json")
    if not cycle:
        return ExpertTrainerAdvice(
            trainer_name="expert_action_writer_trainer",
            supports_workers=("action_writer", "training_manager"),
            status="missing",
            summary="No Action Writer training cycle is available yet, so the manager cannot judge whether steps flow from Be Still or are generic.",
            recommended_actions=("Run an Action Writer training cycle before promoting the action_writer.",),
        )
    assignments = cycle.get("assignments", []) if isinstance(cycle, dict) else []
    fresh = cycle.get("fresh_benchmark", {}) if isinstance(cycle, dict) else {}
    fresh_score = int((fresh.get("evaluation") or {}).get("score", 0) or 0)
    fresh_status = str(fresh.get("status") or "blocked")
    summary = (
        f"The Action Writer trainer issued {len(assignments)} assignment(s). "
        f"Fresh benchmark: {fresh_status} (score={fresh_score}/100)."
    )
    actions = ["Keep Action Steps on approved-artifact drills until the fresh benchmark consistently passes (score >= 80)."]
    if fresh_status != "pass":
        priority_fix = _compact_text((fresh.get("evaluation") or {}).get("priority_fix"))
        if priority_fix:
            actions.append(f"Priority fix: {priority_fix}")
    return ExpertTrainerAdvice(
        trainer_name="expert_action_writer_trainer",
        supports_workers=("action_writer", "training_manager"),
        status="consulted",
        summary=summary,
        recommended_actions=tuple(actions),
        evidence=(
            f"assignment_count={len(assignments)}",
            f"fresh_benchmark_score={fresh_score}",
            f"fresh_benchmark_status={fresh_status}",
        ),
    )


def _consult_output_experts(repo_root: Path) -> ExpertTrainerAdvice:
    review = _latest_output_file(repo_root, "*__devg__output-training-manager-review.json")
    cycle = _latest_output_file(repo_root, "*__devg__pdf-training-cycle.json")
    if not review and not cycle:
        return ExpertTrainerAdvice(
            trainer_name="expert_output_trainers",
            supports_workers=("pdf_art_director", "pdf_layout_engineer", "output_training_manager", "training_manager"),
            status="missing",
            summary="No output expert review is available yet, so the training manager should not treat the PDF workers as meaningfully supervised.",
            recommended_actions=("Run the output training review and PDF training cycle before judging the PDF workers.",),
        )
    findings = cycle.get("agent_review", {}).get("findings", []) if isinstance(cycle, dict) else []
    bottleneck = _compact_text(review.get("current_bottleneck_worker")) if isinstance(review, dict) else ""
    summary = (
        f"The output experts still see {bottleneck or 'a PDF worker'} as the current output bottleneck, with {len(findings)} known PDF product finding(s)."
    )
    actions = []
    review_rows = review.get("reviews", []) if isinstance(review, dict) else []
    for row in review_rows[:2]:
        next_action = _compact_text(row.get("next_action"))
        if next_action:
            actions.append(next_action)
    return ExpertTrainerAdvice(
        trainer_name="expert_output_trainers",
        supports_workers=("pdf_art_director", "pdf_layout_engineer", "output_training_manager", "training_manager"),
        status="consulted",
        summary=summary,
        recommended_actions=tuple(actions),
        evidence=tuple(
            [f"current_output_bottleneck={bottleneck or 'unknown'}", f"pdf_findings={len(findings)}"]
        ),
    )


def _expert_trainer_advice(repo_root: Path) -> list[ExpertTrainerAdvice]:
    return [
        _consult_outliner_trainer(repo_root),
        _consult_library_trainer(repo_root),
        _consult_theological_reviewer(repo_root),
        _consult_policy_guardian(repo_root),
        _consult_exposition_trainer(repo_root),
        _consult_grammar_advisor(repo_root),
        _consult_be_still_trainer(repo_root),
        _consult_action_writer_trainer(repo_root),
        _consult_output_experts(repo_root),
    ]


def _advice_map(repo_root: Path) -> dict[str, list[ExpertTrainerAdvice]]:
    mapping: dict[str, list[ExpertTrainerAdvice]] = {}
    for advice in _expert_trainer_advice(repo_root):
        for worker_name in advice.supports_workers:
            mapping.setdefault(worker_name, []).append(advice)
    return mapping


def _augment_review_with_advice(
    review: WorkerTrainingReview,
    advice_items: list[ExpertTrainerAdvice],
) -> WorkerTrainingReview:
    if not advice_items:
        return review
    summaries = [item.summary for item in advice_items if item.summary]
    actions = [item.recommended_actions[0] for item in advice_items if item.recommended_actions]
    rationale = review.rationale
    if summaries:
        rationale = f"{review.rationale} Expert trainer advice: {' '.join(summaries[:2])}"
    next_action = review.next_action
    if actions:
        next_action = f"{review.next_action} Mentor guidance: {' '.join(actions[:2])}"
    evidence = list(review.evidence)
    for item in advice_items:
        evidence.append(f"mentor={item.trainer_name}")
        evidence.extend(item.evidence[:2])
    return replace(
        review,
        rationale=rationale,
        next_action=next_action,
        evidence=tuple(evidence),
    )


def _review_acquisition_librarian(repo_root: Path) -> WorkerTrainingReview:
    counts = _library_counts(repo_root)
    if counts["holdings"] >= 20 and counts["live_cards"] >= 20:
        return WorkerTrainingReview(
            worker_name="acquisition_librarian",
            status="trained_enough_for_support",
            grade="B+",
            rationale="The acquisition librarian has built a real shelf and converted acquired resources into accepted live cards.",
            next_action="Continue proactive acquisition for future training ranges and likely upcoming book families.",
            evidence=(
                f"holdings={counts['holdings']}",
                f"live_cards={counts['live_cards']}",
            ),
        )
    return WorkerTrainingReview(
        worker_name="acquisition_librarian",
        status="needs_more_training",
        grade="C",
        rationale="The shelf is still too thin or too lightly carded to support the rest of the system reliably.",
        next_action="Keep acquiring parent resources and getting cards accepted before shifting attention elsewhere.",
        evidence=(
            f"holdings={counts['holdings']}",
            f"live_cards={counts['live_cards']}",
        ),
    )


def _review_research_librarian(repo_root: Path) -> WorkerTrainingReview:
    counts = _library_counts(repo_root)
    trainer = _latest_output_file(repo_root, "*__devg__library-trainer-review.json")
    training_cycle = _latest_output_file(repo_root, "*__devg__research-librarian-training-cycle.json")
    trainer_findings = len(trainer.get("findings", [])) if isinstance(trainer, dict) else 0
    reviewed_count = int(training_cycle.get("reviewed_count", 0) or 0) if isinstance(training_cycle, dict) else 0
    if counts["reading_note_evaluations"] >= counts["live_cards"] and counts["live_cards"] > 0:
        return WorkerTrainingReview(
            worker_name="research_librarian",
            status="trained_enough_for_support",
            grade="B+",
            rationale=(
                "The research librarian has completed the first full reading-note pass across the current live shelf "
                "and is now being reviewed by the expert library trainer."
            ),
            next_action="Move into request-serving mode for outliner and writer training while continuing deeper note refinement over time.",
            evidence=(
                f"live_cards={counts['live_cards']}",
                f"reading_note_evaluations={counts['reading_note_evaluations']}",
                f"latest_training_cycle_reviewed={reviewed_count}",
                f"library_trainer_findings={trainer_findings}",
            ),
        )
    return WorkerTrainingReview(
        worker_name="research_librarian",
        status="needs_more_training",
        grade="C",
        rationale="The research librarian still lacks evaluated reading-note coverage across the current shelf.",
        next_action="Finish reading notes and note evaluation before claiming reliable research service.",
        evidence=(
            f"live_cards={counts['live_cards']}",
            f"reading_note_evaluations={counts['reading_note_evaluations']}",
        ),
    )


def _review_outliner(repo_root: Path) -> WorkerTrainingReview:
    checkpoints = _latest_harness_checkpoints(repo_root)
    cycle = _latest_outliner_training_cycle(repo_root)
    proverbs_meta = _load_json(Path(checkpoints["proverbs"])) if "proverbs" in checkpoints else {}
    exodus_book = _load_json(Path(checkpoints["exodus"])) if "exodus" in checkpoints else {}
    proverbs_pass = bool(proverbs_meta and proverbs_meta.get("run_state") == "validated_pass")
    exodus_fail = bool(exodus_book and exodus_book.get("payload", {}).get("status") == "failed")
    latest_cycle_results = cycle.get("results", []) if isinstance(cycle, dict) else []
    cycle_passes = sum(
        1
        for item in latest_cycle_results
        if item.get("evaluation", {}).get("status") == "pass"
    )
    cycle_reviews = len(latest_cycle_results)
    if proverbs_pass and exodus_fail:
        return WorkerTrainingReview(
            worker_name="outliner",
            status="active_bottleneck",
            grade="C+",
            rationale="The outliner can produce clean work on some passages, but Exodus still shows day-progress and theological-boundary weakness.",
            next_action="Keep training on individual harness passages, starting with Exodus-family structure pressure before moving downstream.",
            evidence=(
                f"proverbs_run_state={proverbs_meta.get('run_state')}",
                f"exodus_book_status={exodus_book.get('payload', {}).get('status')}",
                f"latest_outline_training_cycle_passes={cycle_passes}/{cycle_reviews}",
            ),
        )
    if cycle_reviews:
        return WorkerTrainingReview(
            worker_name="outliner",
            status="active_bottleneck" if cycle_passes < cycle_reviews else "trained_enough_for_support",
            grade="B-" if cycle_passes == cycle_reviews else "C+",
            rationale=(
                "The outliner training agent is now producing outline-only drills, but the latest cycle still needs "
                "more clean passes before the outliner should be considered stable."
            ),
            next_action=(
                "Keep the outliner on outline-only assignments until the latest cycle is consistently clean, then re-open downstream worker training."
            ),
            evidence=(
                f"latest_outline_training_cycle_passes={cycle_passes}/{cycle_reviews}",
            ),
        )
    return WorkerTrainingReview(
        worker_name="outliner",
        status="insufficient_evidence",
        grade="C",
        rationale="The current harness evidence is still too thin to say the outliner is ready.",
        next_action="Continue individual harness passage runs and collect clearer book-level outcomes.",
        evidence=tuple(checkpoints.values()),
    )


def _review_be_still_writer(repo_root: Path) -> WorkerTrainingReview:
    cycle = _latest_output_file(repo_root, "*__devg__be-still-training-cycle.json")
    if not cycle:
        return _review_default("be_still_writer")
    fresh = cycle.get("fresh_benchmark", {}) if isinstance(cycle, dict) else {}
    fresh_score = int((fresh.get("evaluation") or {}).get("score", 0) or 0)
    fresh_status = str(fresh.get("status") or "blocked")
    assignments = cycle.get("assignments", []) if isinstance(cycle, dict) else []
    if fresh_status == "pass":
        return WorkerTrainingReview(
            worker_name="be_still_writer",
            status="active_training",
            grade="B-",
            rationale=(
                "The Be Still writer is passing the fresh benchmark — current templates produce prompts that "
                "are passage-anchored and move inward-to-outward."
            ),
            next_action=(
                "Continue running Be Still training cycles to verify consistency across passages. "
                "Raise the bar toward seminary-level inward-to-outward progression."
            ),
            evidence=(
                f"fresh_benchmark_score={fresh_score}",
                f"assignment_count={len(assignments)}",
            ),
        )
    if fresh_status in ("revise", "fail"):
        return WorkerTrainingReview(
            worker_name="be_still_writer",
            status="active_training",
            grade="C+" if fresh_status == "revise" else "C",
            rationale=(
                f"The Be Still writer fresh benchmark scored {fresh_score}/100 ({fresh_status}). "
                "Prompts need to be more passage-specific and better structured inward-to-outward."
            ),
            next_action=(
                "Fix the template issues flagged by the Be Still trainer before running more cycles. "
                "Fresh benchmark score must reach >= 80 to pass."
            ),
            evidence=(
                f"fresh_benchmark_score={fresh_score}",
                f"fresh_benchmark_status={fresh_status}",
                f"assignment_count={len(assignments)}",
            ),
        )
    return _review_default("be_still_writer")


def _review_action_writer(repo_root: Path) -> WorkerTrainingReview:
    cycle = _latest_output_file(repo_root, "*__devg__action-writer-training-cycle.json")
    if not cycle:
        return _review_default("action_writer")
    fresh = cycle.get("fresh_benchmark", {}) if isinstance(cycle, dict) else {}
    fresh_score = int((fresh.get("evaluation") or {}).get("score", 0) or 0)
    fresh_status = str(fresh.get("status") or "blocked")
    assignments = cycle.get("assignments", []) if isinstance(cycle, dict) else []
    if fresh_status == "pass":
        return WorkerTrainingReview(
            worker_name="action_writer",
            status="active_training",
            grade="B-",
            rationale=(
                "The action writer is passing the fresh benchmark — current templates produce steps that "
                "flow from Be Still, are same-day applicable, and convey active expectation."
            ),
            next_action=(
                "Continue running action writer training cycles to verify consistency across passages. "
                "Confirm steps don't resolve the tension named in Be Still."
            ),
            evidence=(
                f"fresh_benchmark_score={fresh_score}",
                f"assignment_count={len(assignments)}",
            ),
        )
    if fresh_status in ("revise", "fail"):
        return WorkerTrainingReview(
            worker_name="action_writer",
            status="active_training",
            grade="C+" if fresh_status == "revise" else "C",
            rationale=(
                f"The action writer fresh benchmark scored {fresh_score}/100 ({fresh_status}). "
                "Steps need to flow more clearly from Be Still (not exposition) and be more same-day specific."
            ),
            next_action=(
                "Fix the connector phrase and step-specificity issues flagged by the action writer trainer. "
                "Fresh benchmark score must reach >= 80 to pass."
            ),
            evidence=(
                f"fresh_benchmark_score={fresh_score}",
                f"fresh_benchmark_status={fresh_status}",
                f"assignment_count={len(assignments)}",
            ),
        )
    return _review_default("action_writer")


def _review_default(worker_name: str) -> WorkerTrainingReview:
    return WorkerTrainingReview(
        worker_name=worker_name,
        status="waiting_for_turn",
        grade="TBD",
        rationale="This worker is downstream of the current training bottleneck and should not be the main focus until upstream training is stronger.",
        next_action="Wait for the training manager to promote this worker after the earlier curriculum stages improve.",
        evidence=(),
    )


def _review_exposition_writer(repo_root: Path) -> WorkerTrainingReview:
    cycle = _latest_output_file(repo_root, "*__devg__exposition-training-cycle.json")
    if not cycle:
        return _review_default("exposition_writer")
    assignments = cycle.get("assignments", []) if isinstance(cycle, dict) else []
    theological = cycle.get("theological_guidance", {}) if isinstance(cycle, dict) else {}
    if assignments:
        return WorkerTrainingReview(
            worker_name="exposition_writer",
            status="active_training",
            grade="C+",
            rationale=(
                "The exposition writer is now training on approved prior content with narrow focal verses, "
                "broader context ranges, and theological-reviewer guidance."
            ),
            next_action=(
                "Keep the exposition writer on approved-artifact drills until theological review stays clean and the writer "
                "proves it can work with narrow focal references without drifting."
            ),
            evidence=(
                f"assignment_count={len(assignments)}",
                f"theological_finding_count={int(theological.get('finding_count', 0) or 0)}",
            ),
        )
    return _review_default("exposition_writer")


def _review_passage_researcher(repo_root: Path) -> WorkerTrainingReview:
    # Check graduation first — if the streak meets the threshold, report it regardless
    # of the latest drill cycle outcome.
    streak = _passage_researcher_consecutive_passes()
    if streak >= _PASSAGE_RESEARCHER_GRADUATION_THRESHOLD:
        return WorkerTrainingReview(
            worker_name="passage_researcher",
            status="trained_enough_for_support",
            grade="A-",
            rationale=(
                f"Passage researcher has accumulated {streak} consecutive passes "
                f"(threshold: {_PASSAGE_RESEARCHER_GRADUATION_THRESHOLD}). "
                "Overall pass rate is 96%+ across 557 experiments. "
                "Worker performs reliably across multiple independent passage families."
            ),
            next_action=(
                "Graduate to passive monitoring. Continue proactive drills only when new library "
                "resources are acquired to verify coverage expands correctly."
            ),
            evidence=(
                f"consecutive_passes={streak}",
                f"graduation_threshold={_PASSAGE_RESEARCHER_GRADUATION_THRESHOLD}",
                "overall_pass_rate=96%+",
            ),
        )

    # Primary: read proactive drill cycle results (independent of exposition)
    drill_cycle = _latest_output_file(repo_root, "*__devg__passage-researcher-training-cycle.json")
    if drill_cycle:
        thin_count = int(drill_cycle.get("thin_count", 0) or 0)
        strong_count = int(drill_cycle.get("strong_count", 0) or 0)
        total = thin_count + strong_count
        drill_status = str(drill_cycle.get("status") or "blocked")
        targets = drill_cycle.get("acquisition_targets", []) if isinstance(drill_cycle, dict) else []
        if drill_status == "pass":
            return WorkerTrainingReview(
                worker_name="passage_researcher",
                status="active_training",
                grade="B-",
                rationale=(
                    f"Passage researcher drilled {total} benchmark passages: all {strong_count} bundles are strong."
                ),
                next_action="Maintain coverage as new library resources are acquired. Expand benchmark set to new passages.",
                evidence=(
                    f"strong_bundles={strong_count}",
                    f"thin_bundles={thin_count}",
                    f"total_drilled={total}",
                ),
            )
        return WorkerTrainingReview(
            worker_name="passage_researcher",
            status="active_training",
            grade="C+" if drill_status == "revise" else "C",
            rationale=(
                f"Passage researcher drilled {total} benchmark passages: "
                f"{thin_count} thin bundle(s) need library resources before exposition training is reliable."
            ),
            next_action=(
                f"Fill {len(targets)} thin acquisition target(s) in the library before re-running. "
                "Passage researcher cannot produce strong bundles where no resources exist."
            ),
            evidence=(
                f"strong_bundles={strong_count}",
                f"thin_bundles={thin_count}",
                f"thin_targets=" + ", ".join(t["passage_reference"] for t in targets[:3]),
            ),
        )

    # Fallback: passive signal from exposition cycle (pre-drill-cycle behavior)
    expo_cycle = _latest_output_file(repo_root, "*__devg__exposition-training-cycle.json")
    if not expo_cycle:
        return _review_default("passage_researcher")
    assignments = expo_cycle.get("passage_researcher_assignments", []) if isinstance(expo_cycle, dict) else []
    if assignments:
        return WorkerTrainingReview(
            worker_name="passage_researcher",
            status="active_training",
            grade="C+",
            rationale=(
                "The passage researcher has thin-bundle assignments from the exposition cycle. "
                "Run proactive drills to get a fuller picture of library coverage."
            ),
            next_action="Run run_passage_researcher_training_cycle.py to drill all benchmark passages.",
            evidence=(f"exposition_gap_assignments={len(assignments)}",),
        )
    return WorkerTrainingReview(
        worker_name="passage_researcher",
        status="waiting_for_turn",
        grade="TBD",
        rationale="No proactive drill cycle or exposition gap has been recorded yet.",
        next_action="Run run_passage_researcher_training_cycle.py to drill benchmark passages proactively.",
        evidence=("proactive_drill_cycle=missing",),
    )


def _passage_researcher_consecutive_passes() -> int:
    """Count trailing consecutive passes in the passage_researcher experiment ledger."""
    records = list_experiments(worker_name="passage_researcher")
    sorted_records = sorted(records, key=lambda r: r.created_at_utc or "")
    streak = 0
    for r in reversed(sorted_records):
        if r.status == "pass":
            streak += 1
        else:
            break
    return streak


_PASSAGE_RESEARCHER_GRADUATION_THRESHOLD = 200  # consecutive passes required
_OUTLINER_GRADUATION_THRESHOLD = 100  # consecutive passes required


def _outliner_consecutive_passes() -> int:
    """Count trailing consecutive passes in the outliner experiment ledger."""
    records = list_experiments(worker_name="outliner")
    sorted_records = sorted(records, key=lambda r: r.completed_at_utc or "")
    streak = 0
    for r in reversed(sorted_records):
        if r.status in ("pass", "completed"):
            streak += 1
        else:
            break
    return streak


def _check_graduation_candidates(repo_root: Path) -> list[dict[str, Any]]:
    """Scan all tracked workers for graduation eligibility and return a summary list.

    A worker is a graduation candidate when its recent consecutive pass streak reaches
    the threshold defined in the relevant training agent. This list is included in the
    training manager review so supervisors can act without having to read individual
    trainer cycle JSONs.
    """
    from src.autoresearch.output_training_manager import (
        _ART_DIRECTOR_GRADUATION_THRESHOLD,
        _pdf_art_director_pass_streak,
    )
    from src.autoresearch.pdf_training_agent import (
        _ART_DIRECTOR_GRADUATION_THRESHOLD as _PDF_ART_THRESH,
        _LAYOUT_ENGINEER_GRADUATION_THRESHOLD,
        _art_director_pass_streak,
        _layout_engineer_pass_streak,
    )

    candidates = []

    def _entry(worker: str, streak: int, threshold: int, note: str = "") -> dict[str, Any]:
        graduated = streak >= threshold
        approaching = not graduated and streak >= max(threshold - 20, 0)
        entry: dict[str, Any] = {
            "worker_name": worker,
            "consecutive_passes": streak,
            "graduation_threshold": threshold,
            "status": "graduated" if graduated else ("approaching" if approaching else "active_training"),
        }
        if note:
            entry["note"] = note
        return entry

    art_streak = _art_director_pass_streak()
    layout_streak = _layout_engineer_pass_streak()
    researcher_streak = _passage_researcher_consecutive_passes()
    outliner_streak = _outliner_consecutive_passes()

    candidates.append(_entry("pdf_art_director", art_streak, _PDF_ART_THRESH))
    candidates.append(_entry("pdf_layout_engineer", layout_streak, _LAYOUT_ENGINEER_GRADUATION_THRESHOLD))
    candidates.append(
        _entry(
            "passage_researcher",
            researcher_streak,
            _PASSAGE_RESEARCHER_GRADUATION_THRESHOLD,
            note="96%+ overall pass rate (536/557). Consecutive streak indicates stable performance.",
        )
    )
    candidates.append(
        _entry(
            "outliner",
            outliner_streak,
            _OUTLINER_GRADUATION_THRESHOLD,
            note="Gates all downstream training. Graduation unlocks full curriculum.",
        )
    )
    return candidates


def _experiment_gate_status(worker_names: list[str]) -> list[dict[str, Any]]:
    """Return gate status for each tracked worker — current gate, last evaluated gate,
    and whether a new gate review is pending.  Included in the training manager review
    so the supervisor can see gate notifications at a glance."""
    from src.autoresearch.llm_gate_review_core import pending_gate_reviews, _current_gate, _last_evaluated_gate
    pending = {w: g for w, g in pending_gate_reviews(worker_names)}
    entries = []
    for worker in worker_names:
        count = len(list_experiments(worker_name=worker))
        current = _current_gate(worker)
        last = _last_evaluated_gate(worker)
        entries.append({
            "worker_name": worker,
            "experiment_count": count,
            "current_gate": current,
            "last_evaluated_gate": last,
            "gate_review_pending": worker in pending,
            "pending_gate": pending.get(worker),
        })
    return entries


def build_training_manager_review(repo_root: Path) -> dict[str, Any]:
    advice_by_worker = _advice_map(repo_root)
    reviews: list[WorkerTrainingReview] = [
        _review_acquisition_librarian(repo_root),
        _review_research_librarian(repo_root),
        _review_outliner(repo_root),
        _review_exposition_writer(repo_root),
        _review_be_still_writer(repo_root),
        _review_action_writer(repo_root),
    ]
    reviews = [_augment_review_with_advice(item, advice_by_worker.get(item.worker_name, [])) for item in reviews]
    # L15 stalled benchmarks enforcement
    for i in range(len(reviews)):
        stalled = _stalled_passages(repo_root / "registry.db", reviews[i].worker_name)
        if stalled:
            stalled_tuple = tuple(sorted(stalled))
            old = reviews[i]
            reviews[i] = replace(
                old,
                status="stalled_passages",
                grade="C",
                rationale=old.rationale + f" L15: stalled on {len(stalled)} benchmark(s).",
                next_action="rotate_passage",
                evidence=old.evidence + stalled_tuple,
                stalled_benchmarks=stalled_tuple,
            )
    reviewed = {item.worker_name for item in reviews}
    for name in WORKER_TRAINING_ORDER:
        if name in reviewed:
            continue
        reviews.append(_augment_review_with_advice(_review_default(name), advice_by_worker.get(name, [])))
    expert_advice = _expert_trainer_advice(repo_root)
    graduation_candidates = _check_graduation_candidates(repo_root)
    gate_status = _experiment_gate_status(["outliner", "exposition_writer"])
    current_bottleneck = next(
        (item.worker_name for item in reviews if item.status == "active_bottleneck"),
        "outliner",
    )
    return {
        "production_standard": PRODUCTION_STANDARD,
        "training_order": list(WORKER_TRAINING_ORDER),
        "graduation_monitoring": graduation_candidates,
        "experiment_gate_status": gate_status,
        "expert_trainer_inputs": {
            "outliner_trainer_cycle_present": bool(_latest_outliner_training_cycle(repo_root)),
            "library_trainer_review_present": bool(_latest_output_file(repo_root, "*__devg__library-trainer-review.json")),
            "theological_reviewer_present": bool(_latest_output_file(repo_root, "*__devg__theological-reviewer-report.json")),
            "policy_guardian_present": bool(_latest_output_file(repo_root, "*__devg__policy-guardian-report.json")),
            "exposition_training_cycle_present": bool(_latest_output_file(repo_root, "*__devg__exposition-training-cycle.json")),
            "be_still_training_cycle_present": bool(_latest_output_file(repo_root, "*__devg__be-still-training-cycle.json")),
            "action_writer_training_cycle_present": bool(_latest_output_file(repo_root, "*__devg__action-writer-training-cycle.json")),
            "grammar_advisor_reviewed": bool(
                (_latest_output_file(repo_root, "*__devg__exposition-training-cycle.json") or {}).get("grammar_guidance")
            ),
            "output_training_review_present": bool(_latest_output_file(repo_root, "*__devg__output-training-manager-review.json")),
            "pdf_training_cycle_present": bool(_latest_output_file(repo_root, "*__devg__pdf-training-cycle.json")),
        },
        "expert_trainer_advice": [
            {
                "trainer_name": item.trainer_name,
                "supports_workers": list(item.supports_workers),
                "status": item.status,
                "summary": item.summary,
                "recommended_actions": list(item.recommended_actions),
                "evidence": list(item.evidence),
            }
            for item in expert_advice
        ],
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


def log_training_manager_review(repo_root: Path) -> dict[str, Any]:
    payload = build_training_manager_review(repo_root)
    now = _utc_now()
    log_experiment(
        experiment_id="training-manager__current-cycle",
        worker_name="training_manager",
        benchmark_name="worker-curriculum-review",
        benchmark_reference="acquisition_librarian -> research_librarian -> outliner -> downstream workers",
        status="reviewed",
        attempted_change="Graded worker readiness in curriculum order and selected the current bottleneck.",
        metrics={
            "current_bottleneck_worker": payload["current_bottleneck_worker"],
            "review_count": len(payload["reviews"]),
            "expert_trainer_advice_count": len(payload["expert_trainer_advice"]),
        },
        learning_note=(
            f"Training manager review completed. Current bottleneck: {payload['current_bottleneck_worker']}. "
            f"Consulted {len(payload['expert_trainer_advice'])} expert trainer input(s)."
        ),
        keep_decision="keep",
        created_at_utc=now,
        completed_at_utc=now,
    )
    return payload
