from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.autoresearch.store import (
    list_experiments,
    list_trainer_recommendations,
    log_experiment,
    record_trainer_recommendation,
)
from src.autoresearch.outliner_adapter import build_outline_artifact
from src.autoresearch.llm_outliner_core import build_llm_outliner_trainer_review, build_llm_passage_selection
from src.models.pipeline import EditorialBuildArtifact, PassageResourceBundle
from src.rag.library_requests import (
    list_resource_acquisition_requests,
    request_resource_acquisition,
)
from src.persistence.paths import default_registry_db_path
from src.rag.research_librarian import prepare_passage_resource_bundle
from src.scripture.planner import (
    count_passage_verses,
    plan_scripture_day_references,
    select_daily_key_verses_reference,
    suggest_study_window_size,
)
from src.scripture.retrieval import ScriptureFailureAlert, ScriptureRetriever, ScriptureResult


@dataclass(frozen=True)
class RangeTemplate:
    num_days: int
    num_weeks: int
    label: str


@dataclass(frozen=True)
class HarnessPassage:
    slug: str
    reference: str
    priority: int = 50


@dataclass(frozen=True)
class OutlineTrainingAssignment:
    assignment_id: str
    passage: str
    passage_slug: str
    num_days: int
    num_weeks: int
    rationale: str
    review_focus: tuple[str, ...]
    selection_stage: str
    teaching_method: str = "standard_outline_drill"
    revision_of_assignment_id: str = ""


RANGE_TEMPLATES: tuple[RangeTemplate, ...] = (
    RangeTemplate(6, 1, "6-day / 1-week"),
    RangeTemplate(12, 2, "12-day / 2-week"),
    RangeTemplate(18, 3, "18-day / 3-week"),
    RangeTemplate(24, 4, "24-day / 4-week"),
    RangeTemplate(30, 5, "30-day / 5-week"),
)

CORE_HARNESS_TEMPLATE = RANGE_TEMPLATES[1]

HARNESS_PASSAGES: tuple[HarnessPassage, ...] = (
    HarnessPassage("genesis-1-2", "Genesis 1-2", priority=80),
    HarnessPassage("job-1-3", "Job 1-3", priority=35),
    HarnessPassage("matthew-1-2", "Matthew 1-2", priority=45),
    HarnessPassage("psalms-1-3", "Psalms 1-3", priority=40),
    HarnessPassage("ezekiel-37", "Ezekiel 37", priority=30),
    HarnessPassage("ezekiel-38-39", "Ezekiel 38-39", priority=25),
    HarnessPassage("genesis-12-13", "Genesis 12-13", priority=75),
    HarnessPassage("exodus-19-20", "Exodus 19-20", priority=0),
    HarnessPassage("proverbs-1-2", "Proverbs 1-2", priority=5),
    HarnessPassage("psalms-23-25", "Psalms 23-25", priority=20),
    HarnessPassage("luke-15", "Luke 15", priority=2),
    HarnessPassage("acts-9", "Acts 9", priority=1),
)

PASSAGE_FOCUS = {
    "exodus-19-20": ("holy boundaries", "week turn", "adjacent-day differentiation"),
    "acts-9": ("conversion arc", "theological boundary", "week transition"),
    "luke-15": ("parable movement", "late-week progression", "earned week turn"),
    "proverbs-1-2": ("wisdom progression", "adjacent-day distinction", "day clarity"),
}

TRAINER_PROFILE = {
    "role": "expert_outliner_trainer",
    "mission": (
        "Train the outliner through focused outline-only assignments across a broad scripture curriculum "
        "without relying on crutches or downstream rescue, while preparing outlines that can support the "
        "competition devotional acceptance criteria and an above-normal devotional product standard."
    ),
    "junior_worker_assumption": (
        "Treat the outliner as a complete beginner with zero proven capability. "
        "No prior pass is a reliable signal of mastery. Do not assign a harder passage until the easier one "
        "is stable across multiple distinct runs. Expect failure on anything beyond the simplest "
        "single-movement narratives. Step down aggressively. Never give the benefit of the doubt. "
        "The outliner has not earned trust — it must prove it passage by passage from the easiest material first."
    ),
    "selection_rules": [
        "Treat the harness as completed foundational work, not as the main ongoing curriculum.",
        "Select passages in a genuine easy-to-hard curriculum based on the outliner's demonstrated non-harness capability.",
        "Assign new work primarily from non-harness scripture pools that are distinct from the competition scriptures.",
        "Use the harness only for occasional spot-checks after broader scripture training has already been assigned.",
        "Prioritize passages that still show weak day progression, weak week turns, or theological-boundary flattening.",
        "Let the outliner attempt the passage first and use trainer feedback before escalating to librarians.",
        "After two substandard attempts on the same passage, request stronger librarian support instead of brute-force retries.",
        "After three librarian support requests for the same passage, defer that passage and revisit it later.",
        "Keep the assignments focused on outlining; do not run downstream devotional sections during training drills.",
    ],
    "research_escalation_policy": (
        "Workers are expected to request more specific information from the library when what is currently "
        "available is not detailed enough for the passage at hand. This is not a failure — it is correct behavior "
        "and is how the library collection grows over time. The general librarian sources new materials based "
        "on these requests. The outliner should request passage-specific structural, commentary, and background "
        "resources whenever generic holdings are insufficient. Do not penalize the outliner for making a "
        "legitimate specificity request. Only flag escalation as premature if adequate current holdings "
        "were available and not used."
    ),
    "review_rubric": [
        "Day boundaries should move the passage forward rather than repeat the same burden.",
        "Week turns should feel earned and visible.",
        "Theological lanes should remain distinct across adjacent days.",
        "Research-librarian support should be present before the outliner is graded.",
        "Daily key verses should be specific enough to support a real devotional day rather than a broad unfocused span.",
        "The outline should prepare downstream sections to satisfy the competition devotional standards, especially genre-aware handling and passage-faithful application.",
        "The outline should be strong enough to support a devotional product priced above normal without downstream rescue.",
    ],
    "competition_alignment": {
        "target_standard": "PRD v16 acceptance criteria plus above-normal devotional product quality",
        "relevant_acceptance_criteria": [
            {
                "id": "AC-03",
                "why_it_matters_to_outliner": "The outliner must identify the literary and theological purpose of the passage well enough for exposition context to remain faithful.",
            },
            {
                "id": "AC-05",
                "why_it_matters_to_outliner": "The outliner must keep doctrinal movement close to the passage and its immediate canonical setting.",
            },
            {
                "id": "AC-11",
                "why_it_matters_to_outliner": "The outline must reflect literary genre so downstream writers do not flatten the text.",
            },
            {
                "id": "AC-17",
                "why_it_matters_to_outliner": "The outline must define the conceptual boundary tightly enough that downstream reflection does not introduce alien concepts.",
            },
            {
                "id": "AC-19",
                "why_it_matters_to_outliner": "The outline must set a same-day application lane that is concrete and passage-grounded.",
            },
        ],
    },
}


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _week_assignments(num_days: int, num_weeks: int) -> list[int]:
    if num_days <= 0 or num_weeks <= 0:
        raise ValueError("num_days and num_weeks must be > 0")
    if num_weeks > num_days:
        raise ValueError("num_weeks cannot exceed num_days")
    sizes = [1 for _ in range(num_weeks)]
    remaining = num_days - num_weeks
    while remaining > 0:
        advanced = False
        for idx in range(num_weeks):
            while remaining > 0 and sizes[idx] < 7:
                sizes[idx] += 1
                remaining -= 1
                advanced = True
            if remaining <= 0:
                break
        if not advanced:
            for idx in range(num_weeks):
                if remaining <= 0:
                    break
                sizes[idx] += 1
                remaining -= 1
    assignments: list[int] = []
    for week_number, size in enumerate(sizes, start=1):
        assignments.extend([week_number] * size)
    return assignments


def _experiment_key(passage_slug: str, template: RangeTemplate) -> str:
    return f"{passage_slug}__{template.num_days}d_{template.num_weeks}w"


def _latest_trainer_recommendations(repo_root: Path) -> list[HarnessPassage]:
    records = list_trainer_recommendations(
        trainer_name="expert_outliner_trainer",
        worker_name="outliner",
        status="recommended",
    )
    if records:
        return [
            HarnessPassage(
                slug=record.passage_slug or _slugify(record.scripture_reference),
                reference=record.scripture_reference,
                priority=record.priority,
            )
            for record in records
        ]

    output_dir = repo_root / "docs" / "system" / "outputs"
    matches = sorted(output_dir.glob("*__devg__outliner-trainer-recommendations.json"))
    if not matches:
        return []
    try:
        payload = json.loads(matches[-1].read_text())
    except Exception:
        return []
    recommendations = payload.get("recommended_passages")
    if not isinstance(recommendations, list):
        return []
    passages: list[HarnessPassage] = []
    seen: set[str] = {item.slug for item in HARNESS_PASSAGES}
    ranked: list[tuple[int, int, dict[str, Any]]] = []
    for idx, item in enumerate(recommendations, start=1):
        if not isinstance(item, dict):
            continue
        difficulty = str(item.get("difficulty") or item.get("difficulty_level") or "").strip().lower()
        difficulty_rank = {
            "easy": 0,
            "foundational": 0,
            "moderate": 1,
            "intermediate": 1,
            "challenging": 2,
            "advanced": 3,
        }.get(difficulty, 1)
        ranked.append((difficulty_rank, idx, item))
    for _difficulty_rank, idx, item in sorted(ranked, key=lambda row: (row[0], row[1])):
        reference = str(item.get("reference") or "").strip()
        if not reference:
            continue
        slug = _slugify(str(item.get("slug") or reference))
        if slug in seen:
            continue
        seen.add(slug)
        priority = item.get("priority")
        try:
            priority_value = int(priority)
        except Exception:
            priority_value = 100 + idx
        passages.append(HarnessPassage(slug=slug, reference=reference, priority=priority_value))
    return passages


_INFEASIBLE_SKIP_THRESHOLD = 2  # mark a (passage, template) combo permanently infeasible after this many task_infeasible records


def _tried_outline_benchmarks() -> set[str]:
    """Return (passage, template) combos that should not be assigned again.

    Includes:
    - Combos that have already passed (learned, no need to repeat).
    - Combos with >= _INFEASIBLE_SKIP_THRESHOLD task_infeasible records (structurally
      impossible — stop assigning regardless of LLM evaluation availability).
    """
    passed: set[str] = set()
    infeasible_counts: dict[str, int] = {}
    for record in list_experiments(worker_name="outliner"):
        if not record.benchmark_name.startswith("outline-only-"):
            continue
        key = f"{record.benchmark_reference}__{record.benchmark_name.removeprefix('outline-only-')}"
        if record.status == "pass":
            passed.add(key)
        elif record.status == "task_infeasible":
            infeasible_counts[key] = infeasible_counts.get(key, 0) + 1
    permanently_infeasible = {k for k, n in infeasible_counts.items() if n >= _INFEASIBLE_SKIP_THRESHOLD}
    return passed | permanently_infeasible


def _recent_outline_attempts_for_passage(passage_slug: str) -> list[dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    try:
        records = list_experiments(worker_name="outliner")
    except Exception:
        return attempts
    for record in records:
        if record.benchmark_reference != passage_slug:
            continue
        if not record.benchmark_name.startswith("outline-only-"):
            continue
        try:
            metrics = json.loads(record.metrics_json or "{}")
        except json.JSONDecodeError:
            metrics = {}
        attempts.append(
            {
                "status": record.status,
                "score": metrics.get("score"),
                "benchmark_name": record.benchmark_name,
                "created_at_utc": record.created_at_utc,
            }
        )
    return attempts


def _recent_attempts_for_benchmark(
    passage_slug: str, benchmark_name: str
) -> list[dict[str, Any]]:
    """Return attempts for a specific passage + template combination (e.g. ruth-1 + 18d_3w).

    Used to pass benchmark-specific history to the trainer so it can detect stalls on a
    particular assignment rather than treating all attempts on a passage as equivalent.
    Excludes task_infeasible and deferred_no_resources records — those are infrastructure
    gaps, not outliner failures, and must not inflate the stall count.
    """
    _skip_statuses = {"task_infeasible", "deferred_no_resources"}
    return [
        a
        for a in _recent_outline_attempts_for_passage(passage_slug)
        if a.get("benchmark_name") == benchmark_name and a.get("status") not in _skip_statuses
    ]


_INFRA_SKIP_STATUSES = {"task_infeasible", "deferred_no_resources"}


def _needs_research_escalation(passage_slug: str) -> bool:
    misses = 0
    for attempt in _recent_outline_attempts_for_passage(passage_slug):
        status = str(attempt.get("status") or "")
        if status in _INFRA_SKIP_STATUSES:
            continue
        score = attempt.get("score")
        if isinstance(score, (int, float)):
            if score < 85:
                misses += 1
        elif status in {"revise", "fail"}:
            misses += 1
    return misses >= 2


def _recent_failure_count(passage_slug: str) -> int:
    misses = 0
    for attempt in _recent_outline_attempts_for_passage(passage_slug):
        status = str(attempt.get("status") or "")
        if status in _INFRA_SKIP_STATUSES:
            continue
        score = attempt.get("score")
        if isinstance(score, (int, float)):
            if score < 85:
                misses += 1
        elif status in {"revise", "fail"}:
            misses += 1
    return misses


def _teaching_mode_for_passage(passage_slug: str) -> str:
    failures = _recent_failure_count(passage_slug)
    if failures >= 4:
        return "easier_passage_reset"
    if failures >= 2:
        return "range_step_down_remediation"
    return "standard_outline_drill"


def _templates_for_teaching_mode(teaching_method: str) -> tuple[RangeTemplate, ...]:
    if teaching_method == "easier_passage_reset":
        return (RANGE_TEMPLATES[0],)
    if teaching_method == "range_step_down_remediation":
        return (RANGE_TEMPLATES[0], RANGE_TEMPLATES[1])
    return RANGE_TEMPLATES


def _outliner_research_request_count(scripture_reference: str) -> int:
    """Count only open (not yet answered) requests. Answered requests mean resources arrived
    and the passage should be retried, not kept deferred."""
    try:
        return len(
            list_resource_acquisition_requests(
                requested_by="outliner",
                worker_name="outliner",
                scripture_reference=scripture_reference,
                status="requested",
            )
        )
    except Exception:
        return 0


def _passage_is_deferred_for_now(scripture_reference: str) -> bool:
    return _outliner_research_request_count(scripture_reference) >= 3


def _request_more_research_for_assignment(assignment: OutlineTrainingAssignment) -> bool:
    if _passage_is_deferred_for_now(assignment.passage):
        return False
    existing = list_resource_acquisition_requests(
        requested_by="outliner",
        worker_name="outliner",
        scripture_reference=assignment.passage,
        status="requested",
    )
    if existing:
        return False
    request_resource_acquisition(
        requested_by="outliner",
        scripture_reference=assignment.passage,
        topic=assignment.passage,
        worker_name="outliner",
        reason=(
            "The outliner has missed the required standard multiple times on this passage. "
            "Acquire or surface stronger outline, structure, and background resources before more brute-force retries."
        ),
        requested_resource_kinds=["outline", "structure", "background", "commentary"],
        notes=(
            f"Escalated after repeated substandard outline-only attempts on {assignment.passage_slug}. "
            "The outliner needs stronger research support."
        ),
    )
    return True


def _latest_passage_status(outputs_dir: Path, passage_slug: str) -> str:
    matches = sorted(outputs_dir.glob(f"*{passage_slug}*__meta.json"))
    if not matches:
        return "not_run"
    meta = json.loads(matches[-1].read_text())
    failed = int(meta.get("validation_summary", {}).get("failed") or 0)
    run_state = str(meta.get("run_state") or "")
    if run_state == "validated_pass" and failed == 0:
        return "clean"
    if run_state == "validated_pass":
        return "partial"
    return run_state or "unknown"


def _latest_output_file(repo_root: Path, pattern: str) -> dict[str, Any]:
    output_dir = repo_root / "docs" / "system" / "outputs"
    matches = sorted(output_dir.glob(pattern))
    if not matches:
        return {}
    try:
        return json.loads(matches[-1].read_text())
    except Exception:
        return {}


def _compact_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return " ".join(text.split())


def _library_trainer_guidance(repo_root: Path) -> tuple[str, ...]:
    review = _latest_output_file(repo_root, "*__devg__library-trainer-review.json")
    if not review:
        return ()
    packet_summary = review.get("packet_summary", {}) if isinstance(review, dict) else {}
    findings = review.get("findings", []) if isinstance(review, dict) else []
    guidance: list[str] = []
    metadata_excerpt_count = int(packet_summary.get("metadata_excerpt_count", 0) or 0)
    weak_context_assignments = int(packet_summary.get("weak_context_assignments", 0) or 0)
    if metadata_excerpt_count > 0:
        guidance.append("Use real explanatory cuttings, not metadata-shaped packet entries.")
    if weak_context_assignments > 0:
        guidance.append("Keep the broader study window in view so the outline does not collapse into isolated key verses.")
    for finding in findings[:2]:
        if isinstance(finding, dict):
            rationale = _compact_text(finding.get("rationale"))
            recommendation = _compact_text(finding.get("recommendation"))
            text = recommendation or rationale
        else:
            text = _compact_text(finding)
        if text and text not in guidance:
            guidance.append(text)
    return tuple(guidance[:2])


def _theological_reviewer_guidance(repo_root: Path) -> tuple[str, ...]:
    report = _latest_output_file(repo_root, "*__devg__theological-reviewer-report.json")
    if not report:
        return ()
    findings = report.get("findings", []) if isinstance(report, dict) else []
    guidance: list[str] = []
    for finding in findings[:2]:
        if not isinstance(finding, dict):
            text = _compact_text(finding)
        else:
            text = _compact_text(finding.get("recommendation")) or _compact_text(finding.get("rationale"))
        if text and text not in guidance:
            guidance.append(text)
    return tuple(guidance[:2])


def _expert_revision_guidance(repo_root: Path, passage_slug: str) -> tuple[str, ...]:
    guidance: list[str] = []
    failures = _recent_failure_count(passage_slug)
    if failures >= 1:
        for item in _library_trainer_guidance(repo_root):
            if item not in guidance:
                guidance.append(item)
    if failures >= 2:
        for item in _theological_reviewer_guidance(repo_root):
            if item not in guidance:
                guidance.append(item)
    return tuple(guidance[:3])


def review_current_outliner_work(repo_root: Path) -> dict[str, Any]:
    outputs_dir = repo_root / "outputs" / "devotionals"
    statuses = []
    for passage in HARNESS_PASSAGES:
        statuses.append(
            {
                "passage": passage.reference,
                "passage_slug": passage.slug,
                "latest_status": _latest_passage_status(outputs_dir, passage.slug),
            }
        )
    severity = {
        "validation_failed": 0,
        "failed": 0,
        "partial": 1,
        "planning_started": 2,
        "unknown": 3,
        "not_run": 4,
        "clean": 9,
    }
    weak = [
        item["passage_slug"]
        for item in sorted(
            statuses,
            key=lambda item: (
                severity.get(item["latest_status"], 5),
                next(p.priority for p in HARNESS_PASSAGES if p.slug == item["passage_slug"]),
                item["passage"],
            ),
        )
        if item["latest_status"] in {"partial", "validation_failed", "failed", "not_run", "planning_started", "unknown"}
    ]
    return {
        "reviewed_at_utc": _utc_now(),
        "trainer_profile": TRAINER_PROFILE,
        "statuses": statuses,
        "priority_weak_passages": weak,
        "summary": (
            "Outliner still needs direct training on passages that remain partial, failed, or not yet exercised, "
            "with outline-only drills before full devotional generation."
        ),
    }


def _refresh_trainer_recommendations(repo_root: Path) -> list[HarnessPassage]:
    """Call the trainer LLM to select new passages when the static recommendation pool is
    exhausted.  Persists the results via record_trainer_recommendation() so they survive
    across cycles exactly like manually-written recommendations.  Returns the new list."""
    utc_now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    experiment_history = [
        {
            "passage_slug": r.benchmark_reference,
            "passage": r.benchmark_reference,
            "status": r.status,
        }
        for r in list_experiments(worker_name="outliner")
        if r.benchmark_name and r.benchmark_name.startswith("outline-only-")
    ]
    raw_recs = build_llm_passage_selection(experiment_history=experiment_history, count=5)
    passages: list[HarnessPassage] = []
    for idx, item in enumerate(raw_recs, start=1):
        reference = str(item.get("reference") or "").strip()
        if not reference:
            continue
        slug = str(item.get("slug") or _slugify(reference)).strip()
        try:
            priority_value = int(item.get("priority") or (100 + idx))
        except (TypeError, ValueError):
            priority_value = 100 + idx
        record_trainer_recommendation(
            recommendation_id=f"outliner-trainer::{slug}::{utc_now}",
            trainer_name="expert_outliner_trainer",
            worker_name="outliner",
            scripture_reference=reference,
            passage_slug=slug,
            priority=priority_value,
            rationale=str(item.get("rationale") or ""),
            selection_stage="trainer_llm_selected",
            status="recommended",
            created_at_utc=utc_now,
            consumed_at_utc="",
        )
        passages.append(HarnessPassage(slug=slug, reference=reference, priority=priority_value))
    return passages


def build_assignment_queue(repo_root: Path, *, limit: int = 3) -> list[OutlineTrainingAssignment]:
    tried = _tried_outline_benchmarks()
    assignments: list[OutlineTrainingAssignment] = []

    # Primary curriculum comes from the trainer's LLM-selected passages.
    # If the static recommendation pool is empty (exhausted or never populated),
    # call the trainer LLM directly to select new passages from its biblical knowledge.
    trainer_selected = _latest_trainer_recommendations(repo_root)
    if not trainer_selected:
        print("[build_assignment_queue] no cached recommendations — calling trainer LLM refresh")
        trainer_selected = _refresh_trainer_recommendations(repo_root)
        if not trainer_selected:
            print("[build_assignment_queue] trainer LLM refresh returned empty — will return no_assignments")

    def _effective_templates(passage: HarnessPassage, teaching_method: str) -> tuple[RangeTemplate, ...]:
        """Return templates for this passage's mode, graduating to full RANGE_TEMPLATES if all
        mode-restricted templates are already passed.  This prevents passages from getting stuck
        permanently when a restricted mode's template set is fully exhausted."""
        restricted = _templates_for_teaching_mode(teaching_method)
        if all(_experiment_key(passage.slug, t) in tried for t in restricted):
            # All restricted templates are already passed — graduate to the full curriculum.
            return RANGE_TEMPLATES
        return restricted

    passage_templates: list[tuple[HarnessPassage, str, tuple[RangeTemplate, ...]]] = [
        (passage, _teaching_mode_for_passage(passage.slug), _effective_templates(passage, _teaching_mode_for_passage(passage.slug)))
        for passage in trainer_selected
    ]
    max_template_count = max((len(templates) for _passage, _mode, templates in passage_templates), default=0)
    for template_idx in range(max_template_count):
        for passage, teaching_method, templates in passage_templates:
            if template_idx >= len(templates):
                continue
            template = templates[template_idx]
            if _passage_is_deferred_for_now(passage.reference):
                continue
            key = _experiment_key(passage.slug, template)
            if key in tried:
                continue
            if teaching_method == "easier_passage_reset":
                rationale = (
                    "Reset this passage to the easiest outline drill because repeated failures show the outliner needs a simpler assignment before moving back up."
                )
                review_focus = ("narrow day movement", "key-verse specificity", "simple passage-faithful progression")
                selection_stage = "trainer_selected_easier_reset"
            elif teaching_method == "range_step_down_remediation":
                rationale = (
                    "Step this passage down to a shorter range after repeated misses so the outliner learns the movement on a smaller canvas before broader prep."
                )
                review_focus = ("short-range progression", "key-verse specificity", "reduced complexity outline drill")
                selection_stage = "trainer_selected_range_step_down"
            else:
                rationale = "Extend outliner training into broader scripture coverage from the expert trainer's selected non-harness passages."
                review_focus = ("competition alignment", "key-verse specificity", "passage-faithful progression")
                selection_stage = "trainer_selected_non_harness_coverage"
            assignments.append(
                OutlineTrainingAssignment(
                    assignment_id=key,
                    passage=passage.reference,
                    passage_slug=passage.slug,
                    num_days=template.num_days,
                    num_weeks=template.num_weeks,
                    rationale=rationale,
                    review_focus=review_focus,
                    selection_stage=selection_stage,
                    teaching_method=teaching_method,
                )
            )
            if len(assignments) >= limit:
                return assignments

    if not assignments:
        deferred = sum(1 for p, _, _ in passage_templates if _passage_is_deferred_for_now(p.reference))
        print(
            f"[build_assignment_queue] no_assignments: {len(trainer_selected)} trainer passage(s), "
            f"{deferred} deferred, all remaining combos already tried"
        )
    return assignments


def _scripture_text(retriever: ScriptureRetriever, reference: str) -> str:
    result = retriever.retrieve(reference=reference)
    if isinstance(result, ScriptureResult):
        return result.text
    if isinstance(result, ScriptureFailureAlert):
        return reference
    return reference


def _reference_is_broad(reference: str) -> bool:
    ref = (reference or "").strip()
    if not ref:
        return True
    if ":" not in ref:
        return True
    if ";" in ref or "," in ref:
        return True
    if re.search(r":\d+-\d+:\d+", ref):
        return True
    match = re.search(r":(\d+)(?:-(\d+))?$", ref)
    if not match:
        return True
    start = int(match.group(1))
    end = int(match.group(2) or start)
    return (end - start + 1) > 2


def _normalized(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _meaningful_tokens(text: str) -> set[str]:
    tokens = {
        token.lower()
        for token in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", text or "")
        if token.lower() not in {
            "the", "and", "that", "with", "from", "into", "this", "were", "was", "have",
            "has", "had", "their", "they", "them", "there", "about", "your", "what",
            "you", "when", "while", "would", "could", "should", "among", "during", "after",
            "before", "because", "through", "those", "these", "very", "then", "than", "unto",
            "lord", "god",
        }
    }
    return tokens


def _overlap_count(anchor_terms: set[str], text: str) -> int:
    return len(anchor_terms.intersection(_meaningful_tokens(text)))


def _generic_scaffold_count(text: str, *, patterns: tuple[str, ...]) -> int:
    lowered = _normalized(text)
    return sum(1 for pattern in patterns if lowered.startswith(pattern))


def evaluate_outline_artifact(artifact: EditorialBuildArtifact) -> dict[str, Any]:
    findings: list[str] = []
    adjacent_focus_duplicates = 0
    adjacent_burden_duplicates = 0
    adjacent_lane_duplicates = 0
    adjacent_scene_duplicates = 0
    adjacent_title_duplicates = 0
    broad_key_verse_references = 0
    missing_key_verse_narrowing = 0
    burden_unanchored = 0
    lane_unanchored = 0
    application_unanchored = 0
    burden_generic_scaffolds = 0
    lane_generic_scaffolds = 0
    application_generic_scaffolds = 0
    day_briefs = artifact.day_briefs

    for prev, curr in zip(day_briefs, day_briefs[1:]):
        if _normalized(prev.focus_clause) == _normalized(curr.focus_clause):
            adjacent_focus_duplicates += 1
        if _normalized(prev.pastoral_burden) == _normalized(curr.pastoral_burden):
            adjacent_burden_duplicates += 1
        if _normalized(prev.theological_lane) == _normalized(curr.theological_lane):
            adjacent_lane_duplicates += 1
        if _normalized(prev.scene_summary) == _normalized(curr.scene_summary):
            adjacent_scene_duplicates += 1
        if _normalized(prev.day_title) == _normalized(curr.day_title):
            adjacent_title_duplicates += 1

    for brief in day_briefs:
        key_ref = brief.key_verse_reference or ""
        study_ref = brief.study_window_reference or ""
        if _reference_is_broad(key_ref):
            broad_key_verse_references += 1
        if _normalized(key_ref) == _normalized(study_ref) and _reference_is_broad(study_ref):
            missing_key_verse_narrowing += 1
        anchor_terms = _meaningful_tokens(brief.focus_clause).union({item.lower() for item in brief.key_terms})
        if _overlap_count(anchor_terms, brief.pastoral_burden) == 0:
            burden_unanchored += 1
        if _overlap_count(anchor_terms, brief.theological_lane) == 0:
            lane_unanchored += 1
        if _overlap_count(anchor_terms, brief.application_lane) == 0:
            application_unanchored += 1
        burden_generic_scaffolds += _generic_scaffold_count(
            brief.pastoral_burden,
            patterns=(
                "faithful response to god's word",
                "see how god meets his people through",
                "receive christ's call through",
                "let the passage reshape faith and obedience around",
                "learn wisdom and worship through",
                "attend to god's word through",
            ),
        )
        lane_generic_scaffolds += _generic_scaffold_count(
            brief.theological_lane,
            patterns=(
                "faithful response to god's word",
                "god's providence and covenant mercy seen in",
                "christ's authority and invitation revealed through",
                "doctrinal clarity and obedient response shaped by",
                "worshipful wisdom and faithful fear shaped by",
            ),
        )
        application_generic_scaffolds += _generic_scaffold_count(
            brief.application_lane,
            patterns=(
                "faithful response shaped by",
                "obedience that grows out of",
                "prayerful attention shaped by",
            ),
        )

    if adjacent_focus_duplicates:
        findings.append(f"Adjacent focus clauses repeated {adjacent_focus_duplicates} time(s).")
    if adjacent_burden_duplicates:
        findings.append(f"Adjacent pastoral burdens repeated {adjacent_burden_duplicates} time(s).")
    if adjacent_lane_duplicates:
        findings.append(f"Adjacent theological lanes repeated {adjacent_lane_duplicates} time(s).")
    if adjacent_scene_duplicates:
        findings.append(f"Adjacent scene summaries repeated {adjacent_scene_duplicates} time(s).")
    if adjacent_title_duplicates:
        findings.append(f"Adjacent day titles repeated {adjacent_title_duplicates} time(s).")
    if broad_key_verse_references:
        findings.append(f"Broad or unfocused key verse references appeared {broad_key_verse_references} time(s).")
    if missing_key_verse_narrowing:
        findings.append(f"Study windows were reused as key verses without narrowing {missing_key_verse_narrowing} time(s).")
    if burden_unanchored:
        findings.append(f"Pastoral burdens lacked textual anchoring {burden_unanchored} time(s).")
    if lane_unanchored:
        findings.append(f"Theological lanes lacked textual anchoring {lane_unanchored} time(s).")
    if application_unanchored:
        findings.append(f"Application lanes lacked textual anchoring {application_unanchored} time(s).")
    if burden_generic_scaffolds:
        findings.append(f"Pastoral burdens used generic scaffold language {burden_generic_scaffolds} time(s).")
    if lane_generic_scaffolds:
        findings.append(f"Theological lanes used generic scaffold language {lane_generic_scaffolds} time(s).")
    if application_generic_scaffolds:
        findings.append(f"Application lanes used generic scaffold language {application_generic_scaffolds} time(s).")

    weak_week_turns = 0
    for prev, curr in zip(artifact.week_plans, artifact.week_plans[1:]):
        if _normalized(prev.movement_summary) == _normalized(curr.movement_summary):
            weak_week_turns += 1
        if _normalized(prev.title) == _normalized(curr.title):
            weak_week_turns += 1
    if weak_week_turns:
        findings.append(f"Week movement did not turn clearly {weak_week_turns} time(s).")

    bundle = artifact.passage_resources or PassageResourceBundle(
        topic=artifact.topic,
        scripture_reference=artifact.source_reference or "",
        prepared_at_utc=_utc_now(),
    )
    if len(bundle.outliner_resources) < 2:
        findings.append("Research librarian provided fewer than 2 outliner resources.")

    score = 100
    score -= adjacent_focus_duplicates * 12
    score -= adjacent_burden_duplicates * 18
    score -= adjacent_lane_duplicates * 20
    score -= adjacent_scene_duplicates * 10
    score -= adjacent_title_duplicates * 8
    score -= weak_week_turns * 15
    score -= broad_key_verse_references * 8
    score -= missing_key_verse_narrowing * 12
    score -= burden_unanchored * 8
    score -= lane_unanchored * 8
    score -= application_unanchored * 6
    score -= burden_generic_scaffolds * 5
    score -= lane_generic_scaffolds * 5
    score -= application_generic_scaffolds * 4
    if len(bundle.outliner_resources) < 2:
        score -= 15
    if len(bundle.shared_resources) < 2:
        score -= 10
    score = max(0, score)
    status = "pass" if score >= 85 else "revise" if score >= 65 else "fail"
    return {
        "status": status,
        "score": score,
        "resource_counts": {
            "outliner_resources": len(bundle.outliner_resources),
            "shared_resources": len(bundle.shared_resources),
            "exposition_resources": len(bundle.exposition_resources),
        },
        "metrics": {
            "adjacent_focus_duplicates": adjacent_focus_duplicates,
            "adjacent_burden_duplicates": adjacent_burden_duplicates,
            "adjacent_lane_duplicates": adjacent_lane_duplicates,
            "adjacent_scene_duplicates": adjacent_scene_duplicates,
            "adjacent_title_duplicates": adjacent_title_duplicates,
            "weak_week_turns": weak_week_turns,
            "broad_key_verse_references": broad_key_verse_references,
            "missing_key_verse_narrowing": missing_key_verse_narrowing,
            "burden_unanchored": burden_unanchored,
            "lane_unanchored": lane_unanchored,
            "application_unanchored": application_unanchored,
            "burden_generic_scaffolds": burden_generic_scaffolds,
            "lane_generic_scaffolds": lane_generic_scaffolds,
            "application_generic_scaffolds": application_generic_scaffolds,
        },
        "findings": findings,
        "competition_alignment": TRAINER_PROFILE["competition_alignment"],
    }


def build_revision_assignment(
    assignment: OutlineTrainingAssignment,
    evaluation: dict[str, Any],
    *,
    repo_root: Path | None = None,
) -> OutlineTrainingAssignment:
    findings = [str(item).strip() for item in evaluation.get("findings", []) if str(item).strip()]
    coached_focus = list(findings[:3]) or [
        "tighten day progression",
        "differentiate adjacent burdens",
        "narrow the daily key verse",
    ]
    if repo_root is not None:
        for item in _expert_revision_guidance(repo_root, assignment.passage_slug):
            if item not in coached_focus:
                coached_focus.append(item)
    return replace(
        assignment,
        assignment_id=f"{assignment.assignment_id}__revision",
        rationale=(
            f"{assignment.rationale} Trainer-guided revision: correct the specific failures from the first attempt "
            "before moving on to a different passage. Use expert reviewer guidance and current shelf knowledge rather than brute-force guessing."
        ),
        review_focus=tuple(coached_focus[:5]),
        selection_stage="trainer_guided_revision",
        teaching_method="guided_revision",
        revision_of_assignment_id=assignment.assignment_id,
    )


def run_outline_assignment(
    assignment: OutlineTrainingAssignment,
    *,
    repo_root: Path,
    retriever: ScriptureRetriever | None = None,
) -> dict[str, Any]:
    research_escalated = False
    if _needs_research_escalation(assignment.passage_slug):
        research_escalated = _request_more_research_for_assignment(assignment)

    active_retriever = retriever or ScriptureRetriever()

    # --- Deterministic infeasibility pre-check ---
    # Verse density < 1.5 means the passage is too short for the requested day
    # count regardless of LLM output. Log and bail immediately so we don't burn
    # API credits running a full outline only to have the trainer flag it.
    _VERSE_DENSITY_THRESHOLD = 1.5
    try:
        _total_verses = count_passage_verses(
            assignment.passage,
            retriever=active_retriever,
        )
        _verse_density = _total_verses / assignment.num_days
    except Exception:
        _verse_density = 99.0  # unknown — allow through
        _total_verses = 0

    if _verse_density < _VERSE_DENSITY_THRESHOLD:
        _pre_benchmark = f"outline-only-{assignment.num_days}d_{assignment.num_weeks}w"
        log_experiment(
            experiment_id=f"outliner-training-agent__{assignment.assignment_id}__{_utc_now()}",
            worker_name="outliner",
            benchmark_name=_pre_benchmark,
            benchmark_reference=assignment.passage_slug,
            status="task_infeasible",
            attempted_change="Deterministic pre-flight: verse_density < 1.5 — no LLM call needed.",
            metrics={
                "verse_count": _total_verses,
                "num_days": assignment.num_days,
                "verse_density": round(_verse_density, 2),
            },
            learning_note=(
                f"Infeasible assignment detected before any LLM call: "
                f"{_total_verses} verses / {assignment.num_days} days = "
                f"{_verse_density:.2f} < {_VERSE_DENSITY_THRESHOLD}. "
                "Trainer should select a longer passage or fewer days."
            ),
            keep_decision="defer",
            created_at_utc=_utc_now(),
            completed_at_utc=_utc_now(),
        )
        return {
            "assignment_id": assignment.assignment_id,
            "assignment": asdict(assignment),
            "status": "task_infeasible",
            "verse_count": _total_verses,
            "verse_density": round(_verse_density, 2),
        }
    # --- End pre-check ---

    num_days = assignment.num_days
    study_window_size = suggest_study_window_size(
        reference=assignment.passage,
        num_days=num_days,
    )
    try:
        references = plan_scripture_day_references(
            reference=assignment.passage,
            num_days=num_days,
            max_verses_per_day=study_window_size,
            retriever=active_retriever,
        )
    except ValueError as exc:
        # Passage is too short for the requested day count — reduce to fit.
        import re as _re
        _m = _re.search(r"has (\d+) verses", str(exc))
        max_days = int(_m.group(1)) if _m else max(1, num_days - 1)
        num_days = min(num_days, max_days)
        study_window_size = suggest_study_window_size(
            reference=assignment.passage,
            num_days=num_days,
        )
        references = plan_scripture_day_references(
            reference=assignment.passage,
            num_days=num_days,
            max_verses_per_day=study_window_size,
            retriever=active_retriever,
        )
    bundle = prepare_passage_resource_bundle(
        topic=assignment.passage,
        scripture_reference=assignment.passage,
        db_path=default_registry_db_path(),
    )

    # --- Resource gate: defer when the library has too few resources for a fair evaluation ---
    # evaluate_outline_artifact() deducts -25 automatically (outliner_resources < 2 → -15,
    # shared_resources < 2 → -10), which alone drops the ceiling below the 85 pass threshold.
    # Since the outliner is deterministic, every retry produces an identical artifact and
    # identical score. Skip the LLM call entirely, file an acquisition request so the gap
    # gets resolved, and let the supervisor pick a passage that can actually be scored.
    _MIN_OUTLINER_RESOURCES = 2
    if len(bundle.outliner_resources) < _MIN_OUTLINER_RESOURCES:
        _pre_benchmark = f"outline-only-{assignment.num_days}d_{assignment.num_weeks}w"
        _request_more_research_for_assignment(assignment)
        log_experiment(
            experiment_id=f"outliner-training-agent__{assignment.assignment_id}__{_utc_now()}",
            worker_name="outliner",
            benchmark_name=_pre_benchmark,
            benchmark_reference=assignment.passage_slug,
            status="deferred_no_resources",
            attempted_change="Resource gate pre-flight: outliner_resources < 2 — acquisition request filed.",
            metrics={
                "outliner_resources": len(bundle.outliner_resources),
                "shared_resources": len(bundle.shared_resources),
                "num_days": assignment.num_days,
            },
            learning_note=(
                f"Deferred: only {len(bundle.outliner_resources)} outliner resource(s) indexed for "
                f"{assignment.passage} (minimum {_MIN_OUTLINER_RESOURCES}). "
                "Acquisition request filed. Retry after library is populated."
            ),
            keep_decision="defer",
            created_at_utc=_utc_now(),
            completed_at_utc=_utc_now(),
        )
        return {
            "assignment_id": assignment.assignment_id,
            "assignment": asdict(assignment),
            "status": "deferred_no_resources",
            "outliner_resources": len(bundle.outliner_resources),
            "shared_resources": len(bundle.shared_resources),
        }
    # --- End resource gate ---

    day_inputs: list[dict[str, str]] = []
    for reference in references:
        scripture_text = _scripture_text(active_retriever, reference)
        key_reference = select_daily_key_verses_reference(reference=reference, max_key_verses=2)
        day_inputs.append(
            {
                "scripture_reference": key_reference,
                "study_window_reference": reference,
                "key_verse_reference": key_reference,
                "scripture_text": scripture_text,
            }
        )

    artifact = build_outline_artifact(
        topic=assignment.passage,
        source_reference=assignment.passage,
        num_days=num_days,
        num_weeks=assignment.num_weeks,
        day_inputs=day_inputs,
        passage_resources=bundle,
    )
    evaluation = evaluate_outline_artifact(artifact)

    # Fetch benchmark-specific attempt history so the trainer can detect stalls
    benchmark_name = f"outline-only-{assignment.num_days}d_{assignment.num_weeks}w"
    prior_attempts = _recent_attempts_for_benchmark(assignment.passage_slug, benchmark_name)

    # LLM trainer evaluates the deterministic outline and adjusts the score
    try:
        trainer_review = build_llm_outliner_trainer_review(
            artifact,
            evaluation=evaluation,
            topic=assignment.passage,
            recent_attempts=prior_attempts,
        )
    except Exception:
        trainer_review = None

    final_status = trainer_review["status"] if trainer_review else evaluation["status"]
    final_score = trainer_review["combined_score"] if trainer_review else evaluation["score"]

    trainer_metrics: dict[str, Any] = {}
    if trainer_review:
        trainer_metrics = {
            "trainer_score_adjustment": trainer_review["score_adjustment"],
            "trainer_combined_score": trainer_review["combined_score"],
            "trainer_passage_specificity": trainer_review["passage_specificity"],
            "task_feasibility_verdict": trainer_review.get("task_feasibility_verdict", "feasible"),
            "training_strategy_recommendation": trainer_review.get("training_strategy_recommendation", ""),
        }

    # task_infeasible means the assignment was unreasonable — log it but do not treat it
    # as an outliner failure: keep_decision="defer" so the loop skips this benchmark.
    is_task_infeasible = final_status == "task_infeasible"
    keep_decision = "keep" if final_status == "pass" else "defer" if is_task_infeasible else "review"
    learning_note = (
        "Task was assessed as infeasible by the trainer — the passage/day-count combination "
        "cannot support the required exposition quality. This is an assignment issue, not an "
        "outliner failure. Benchmark should be deferred or the day count reduced."
        if is_task_infeasible
        else "Focused the outliner on structure, burdens, and week turns without running downstream devotional sections."
    )

    log_experiment(
        experiment_id=f"outliner-training-agent__{assignment.assignment_id}__{_utc_now()}",
        worker_name="outliner",
        benchmark_name=benchmark_name,
        benchmark_reference=assignment.passage_slug,
        status=final_status,
        attempted_change="Ran an outline-only training assignment with research-librarian support and outline fitness scoring.",
        metrics={
            "score": final_score,
            "deterministic_score": evaluation["score"],
            "research_escalated": research_escalated,
            "teaching_method": assignment.teaching_method,
            **evaluation["metrics"],
            **evaluation["resource_counts"],
            **trainer_metrics,
        },
        learning_note=learning_note,
        keep_decision=keep_decision,
        created_at_utc=_utc_now(),
        completed_at_utc=_utc_now(),
    )
    return {
        "assignment_id": assignment.assignment_id,
        "assignment": asdict(assignment),
        "editorial_build": artifact.model_dump(mode="json"),
        "evaluation": evaluation,
        "trainer_review": trainer_review,
        "research_escalated": research_escalated,
    }


def run_assignment_with_revision(
    assignment: OutlineTrainingAssignment,
    *,
    repo_root: Path,
    retriever: ScriptureRetriever | None = None,
) -> dict[str, Any]:
    initial_attempt = run_outline_assignment(
        assignment,
        repo_root=repo_root,
        retriever=retriever,
    )
    trainer_review = initial_attempt.get("trainer_review") or {}
    initial_trainer_status = str(trainer_review.get("status") or "")
    initial_eval_status = str(initial_attempt.get("evaluation", {}).get("status") or "")
    # Use the trainer status when available — it takes precedence over the deterministic status.
    initial_status = initial_trainer_status or initial_eval_status

    # task_infeasible: the assignment was structurally unreasonable — no revision makes sense.
    if initial_status not in {"fail", "revise"}:
        return {
            "assignment_id": assignment.assignment_id,
            "assignment": asdict(assignment),
            "initial_attempt": initial_attempt,
            "revision_attempt": None,
            "final_evaluation": initial_attempt.get("evaluation", {}),
        }

    revision_assignment = build_revision_assignment(
        assignment,
        initial_attempt.get("evaluation", {}),
        repo_root=repo_root,
    )
    revision_attempt = run_outline_assignment(
        revision_assignment,
        repo_root=repo_root,
        retriever=retriever,
    )
    return {
        "assignment_id": assignment.assignment_id,
        "assignment": asdict(assignment),
        "initial_attempt": initial_attempt,
        "revision_attempt": revision_attempt,
        "final_evaluation": revision_attempt.get("evaluation", {}),
    }


def build_outliner_training_cycle(repo_root: Path, *, limit: int = 3) -> dict[str, Any]:
    review = review_current_outliner_work(repo_root)
    assignments = build_assignment_queue(repo_root, limit=limit)
    results = [
        run_assignment_with_revision(assignment, repo_root=repo_root)
        for assignment in assignments
    ]
    # Derive top-level status and findings required by policy guardian L2 evidence gate.
    failed_assignments = [
        r for r in results
        if str(r.get("final_evaluation", {}).get("status", "")).lower() in {"fail", "revise"}
    ]
    findings: list[dict[str, Any]] = [
        {
            "assignment_id": r["assignment_id"],
            "passage": r["assignment"]["passage"],
            "status": r["final_evaluation"].get("status"),
            "score": r["final_evaluation"].get("score"),
        }
        for r in failed_assignments
    ]
    status = "pass" if assignments and not failed_assignments else ("fail" if failed_assignments else "no_assignments")
    return {
        "generated_at_utc": _utc_now(),
        "status": status,
        "findings": findings,
        "trainer_profile": TRAINER_PROFILE,
        "agent_review": review,
        "assignments": [asdict(item) for item in assignments],
        "results": results,
    }


def write_outliner_training_cycle(repo_root: Path, payload: dict[str, Any]) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d__%H%M%S")
    output_dir = repo_root / "docs" / "system" / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{stamp}__devg__outliner-training-cycle.json"
    path.write_text(json.dumps(payload, indent=2))
    return path
