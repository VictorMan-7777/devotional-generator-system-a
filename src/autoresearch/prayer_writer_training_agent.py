"""prayer_writer_training_agent.py — Prayer Writer section training orchestrator.

The Prayer writer is a deterministic pipeline worker. This agent:
  1. Reads approved book.json artifacts and evaluates the Prayer sections
     the deterministic writer produced.
  2. Runs a fresh benchmark: regenerates Prayer from current templates and
     scores immediately — so template improvements show up in scores without
     needing a new production run.
  3. Logs all findings to the experiment store for the training manager.

The LLM in this agent is the TRAINER (evaluator), not a pipeline generator.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.autoresearch.llm_prayer_writer_core import build_llm_prayer_trainer_review
from src.autoresearch.store import log_experiment
from src.autoresearch.training_corpus import ensure_approved_training_artifact
from src.generation.editorial import build_editorial_day_brief
from src.generation.real_section_generator import _build_prayer, _build_exposition
from src.models.devotional import DevotionalBook, PrayerSection
from src.validation.ac_scorer import ac_scores_to_metrics, score_prayer
from src.scripture.planner import select_daily_key_verses_reference
from src.scripture.retrieval import ScriptureFailureAlert, ScriptureRetriever, ScriptureResult


_FRESH_BENCHMARK_PASSAGES = [
    ("Habakkuk 1:1-4", "Habakkuk 1:1-11"),
    ("Isaiah 40:28-31", "Isaiah 40:27-31"),
    ("Ruth 1:6-10", "Ruth 1:1-18"),
    ("Colossians 3:1-4", "Colossians 3:1-17"),
    ("Luke 15:11-14", "Luke 15:11-32"),
]

PRAYER_WRITER_TRAINER_PROFILE = {
    "role": "expert_prayer_writer_trainer",
    "mission": (
        "Train the Prayer writer to produce closing prayers that are genuinely anchored "
        "to the day's specific passage and pastoral burden — not generic devotional filler "
        "that could close any reading anywhere."
    ),
    "junior_worker_assumption": (
        "Treat the Prayer writer as a complete beginner. Assume every prayer will be "
        "generic until proven passage-specific. A petition that appears verbatim in "
        "every output regardless of passage is a structural failure, not a training issue. "
        "Do not pass based on 'Amen.' alone — require genuine passage anchoring, tone "
        "matching, and at least one petition drawn from the day's focus clause."
    ),
    "review_rubric": [
        "Does the prayer stay inside the passage horizon — no concepts imported from outside today's text?",
        "Does it address God in a mode appropriate to the passage (Father/Lord/Holy Spirit)?",
        "Does it reflect the specific pastoral burden of this day, not a universal burden?",
        "Does it contain specific vocabulary or images from the actual passage text?",
        "Is the tone matched to the passage — lament requires lament, not comfort?",
        "Does it end with 'Amen.'?",
        "Does it contain at least one petition grounded in the day's focus clause?",
        "Does it avoid answering its own questions?",
    ],
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_book(path: Path) -> DevotionalBook:
    return DevotionalBook.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _scripture_text(retriever: ScriptureRetriever, reference: str) -> str:
    result = retriever.retrieve(reference=reference)
    if isinstance(result, ScriptureResult):
        return result.text
    return reference


def run_fresh_prayer_benchmark(repo_root: Path) -> dict[str, Any]:
    """Regenerate Prayer from current templates and evaluate with LLM trainer.

    Score changes immediately reflect template improvements — no new production
    run needed. Rotates through benchmark passages by hour.
    """
    retriever = ScriptureRetriever()
    now = _utc_now()

    hour_index = datetime.now(timezone.utc).hour % len(_FRESH_BENCHMARK_PASSAGES)
    focal_reference, context_reference = _FRESH_BENCHMARK_PASSAGES[hour_index]

    scripture_text = _scripture_text(retriever, context_reference)
    if not scripture_text or scripture_text == context_reference:
        return {
            "status": "blocked",
            "benchmark_passage": focal_reference,
            "error": "Scripture retrieval failed for fresh benchmark.",
            "evaluation": None,
        }

    # Retrieve focal passage text separately so focus_clause horizon checks are
    # scoped to the focal pericope, not the full study window.
    focal_scripture_text = _scripture_text(retriever, focal_reference)
    if not focal_scripture_text or focal_scripture_text == focal_reference:
        focal_scripture_text = scripture_text  # fall back to full context if focal fails

    brief = build_editorial_day_brief(
        day_number=1,
        scripture_reference=focal_reference,
        scripture_text=scripture_text,
        study_window_reference=context_reference,
    )
    exposition_text = _build_exposition(brief=brief, scripture_text=scripture_text)
    prayer_text = _build_prayer(
        brief=brief,
        scripture_text=scripture_text,
        exposition_text=exposition_text,
        focal_scripture_text=focal_scripture_text,
    )

    editorial_brief_text = (
        f"Pastoral burden: {brief.pastoral_burden}. "
        f"Theological lane: {brief.theological_lane}. "
        f"Focus clause: {brief.focus_clause}."
    )

    try:
        review = build_llm_prayer_trainer_review(
            prayer_text,
            passage_reference=focal_reference,
            passage_text=focal_scripture_text,
            editorial_brief=editorial_brief_text,
        )
    except Exception as exc:
        return {
            "status": "blocked",
            "benchmark_passage": focal_reference,
            "error": str(exc),
            "evaluation": None,
        }

    slug = re.sub(r"[^a-z0-9]+", "-", focal_reference.lower()).strip("-")
    _section = PrayerSection(
        text=prayer_text,
        word_count=len(prayer_text.split()),
        prayer_trace_map_id="",
    )
    _ac = ac_scores_to_metrics(score_prayer(_section))
    log_experiment(
        experiment_id=f"prayer-writer-fresh-benchmark__{slug}__{now}",
        worker_name="prayer_writer",
        benchmark_name="llm-fresh-prayer-benchmark",
        benchmark_reference=slug,
        status=review["status"],
        attempted_change=(
            f"Fresh benchmark: LLM trainer evaluated dynamically-generated Prayer for {focal_reference}. "
            "Score reflects current template quality without requiring a new production run."
        ),
        metrics={
            "score": review["score"],
            "passage_anchored": review["passage_anchored"],
            "tone_matched": review["tone_matched"],
            **_ac,
        },
        learning_note=(
            "Fresh benchmark regenerates Prayer from current deterministic templates each cycle. "
            "Score changes directly track template improvements."
        ),
        keep_decision="keep" if review["status"] == "pass" else "review",
        created_at_utc=now,
        completed_at_utc=now,
    )

    return {
        "status": review["status"],
        "benchmark_passage": focal_reference,
        "prayer_text": prayer_text,
        "evaluation": review,
    }


def run_llm_prayer_writer_trainer_review(
    repo_root: Path, *, artifact: dict[str, Any]
) -> dict[str, Any]:
    """LLM trainer evaluates Prayer sections from an approved artifact."""
    retriever = ScriptureRetriever()
    now = _utc_now()

    try:
        book = _load_book(Path(str(artifact["book_json_path"])))
    except Exception as exc:
        return {
            "status": "blocked",
            "error": f"Could not load approved book: {exc}",
            "benchmark_passage": None,
            "evaluation": None,
        }

    for day in book.days[:6]:
        prayer_text = str(getattr(day.prayer, "text", None) or "").strip()
        if not prayer_text:
            continue

        context_reference = str(day.scripture.reference or "").strip()
        focal_reference = select_daily_key_verses_reference(
            reference=context_reference, max_key_verses=2
        )
        slug = re.sub(r"[^a-z0-9]+", "-", focal_reference.lower()).strip("-")
        scripture_text = _scripture_text(retriever, context_reference)
        if not scripture_text or scripture_text == context_reference:
            scripture_text = context_reference

        editorial_brief_text = (
            f"Scripture reference: {focal_reference}. "
            f"Context reference: {context_reference}."
        )

        try:
            review = build_llm_prayer_trainer_review(
                prayer_text,
                passage_reference=focal_reference,
                passage_text=scripture_text,
                editorial_brief=editorial_brief_text,
            )
        except Exception as exc:
            return {
                "status": "blocked",
                "benchmark_passage": focal_reference,
                "error": str(exc),
                "evaluation": None,
            }

        log_experiment(
            experiment_id=f"prayer-writer-trainer-review__{slug}__{now}",
            worker_name="prayer_writer",
            benchmark_name="llm-prayer-writer-trainer-review",
            benchmark_reference=slug,
            status=review["status"],
            attempted_change=(
                f"LLM trainer evaluated deterministic Prayer for {focal_reference}."
            ),
            metrics={
                "score": review["score"],
                "passage_anchored": review["passage_anchored"],
                "tone_matched": review["tone_matched"],
            },
            learning_note=(
                "LLM trainer reviewed the deterministic Prayer writer's actual output. "
                "Score reflects production quality, not AI-generated text."
            ),
            keep_decision="keep" if review["status"] == "pass" else "review",
            created_at_utc=now,
            completed_at_utc=now,
        )

        return {
            "status": review["status"],
            "benchmark_passage": focal_reference,
            "evaluation": review,
        }

    return {
        "status": "blocked",
        "benchmark_passage": None,
        "error": "No day with Prayer text found in the approved artifact.",
        "evaluation": None,
    }


@dataclass(frozen=True)
class PrayerWriterTrainingAssignment:
    day_number: int
    focal_reference: str
    context_reference: str
    sentence_count: int
    rationale: str


def build_prayer_writer_training_cycle(repo_root: Path) -> dict[str, Any]:
    """Build a full Prayer Writer training cycle report."""
    artifact = ensure_approved_training_artifact(repo_root)
    if not artifact:
        return {
            "generated_at_utc": _utc_now(),
            "status": "blocked",
            "summary": "No approved artifact available for Prayer Writer training.",
            "assignments": [],
        }

    book = _load_book(Path(str(artifact["book_json_path"])))
    assignments: list[PrayerWriterTrainingAssignment] = []

    for day in book.days[:6]:
        prayer_text = str(getattr(day.prayer, "text", None) or "").strip()
        context_reference = str(day.scripture.reference or "").strip()
        focal_reference = select_daily_key_verses_reference(
            reference=context_reference, max_key_verses=2
        )
        import re as _re
        sentence_count = len(
            [s for s in _re.split(r"(?<=[.!?])\s+", prayer_text) if s.strip()]
        ) if prayer_text else 0
        assignments.append(
            PrayerWriterTrainingAssignment(
                day_number=int(day.day_number),
                focal_reference=focal_reference,
                context_reference=context_reference,
                sentence_count=sentence_count,
                rationale=(
                    "Evaluate whether the closing prayer is genuinely anchored to "
                    "the passage horizon, addresses God appropriately, and contains "
                    "at least one petition from the day's focus clause."
                ),
            )
        )

    return {
        "generated_at_utc": _utc_now(),
        "status": "ready",
        "artifact": artifact,
        "trainer_profile": PRAYER_WRITER_TRAINER_PROFILE,
        "assignments": [asdict(a) for a in assignments],
    }


def log_prayer_writer_training_cycle(repo_root: Path) -> dict[str, Any]:
    payload = build_prayer_writer_training_cycle(repo_root)
    now = _utc_now()

    if payload.get("status") != "ready":
        return payload

    for item in payload["assignments"]:
        log_experiment(
            experiment_id=f"prayer-writer__{item['context_reference']}__{item['day_number']}__{now}",
            worker_name="prayer_writer",
            benchmark_name="approved-artifact-prayer-writer-training",
            benchmark_reference=item["context_reference"],
            status="assigned",
            attempted_change=(
                f"Train Prayer writer on focal reference {item['focal_reference']} "
                f"with context {item['context_reference']}."
            ),
            metrics={
                "day_number": item["day_number"],
                "sentence_count": item["sentence_count"],
            },
            learning_note="Prayer writer trained on approved prior content.",
            keep_decision="review",
            created_at_utc=now,
            completed_at_utc=now,
        )

    fresh_benchmark = run_fresh_prayer_benchmark(repo_root)
    payload["fresh_benchmark"] = fresh_benchmark
    fresh_score = int((fresh_benchmark.get("evaluation") or {}).get("score", 0) or 0)
    fresh_status = str(fresh_benchmark.get("status") or "blocked")

    artifact_benchmark = run_llm_prayer_writer_trainer_review(repo_root, artifact=payload["artifact"])
    payload["artifact_benchmark"] = artifact_benchmark

    # Primary gate uses fresh benchmark (current template quality)
    gate_score = fresh_score
    gate_status = fresh_status

    if gate_status == "blocked":
        prayer_writer_status = "fail"
    elif gate_score >= 80:
        prayer_writer_status = "pass"
    elif gate_score >= 60:
        prayer_writer_status = "revise"
    else:
        prayer_writer_status = "fail"

    log_experiment(
        experiment_id=f"prayer-writer-review__{now}",
        worker_name="prayer_writer",
        benchmark_name="approved-artifact-prayer-writer-review",
        benchmark_reference=str(payload["artifact"]["run_slug"]),
        status=prayer_writer_status,
        attempted_change=(
            "Reviewed Prayer Writer training: fresh benchmark regenerated prayer from current "
            "templates and scored. Pass = fresh score >= 80."
        ),
        metrics={
            "fresh_benchmark_score": gate_score,
            "fresh_benchmark_status": gate_status,
            "assignment_count": len(payload["assignments"]),
        },
        learning_note=(
            "Prayer writer fresh benchmark score (>= 80 = pass) is the quality gate. "
            "Score directly reflects current template quality."
        ),
        keep_decision="keep" if prayer_writer_status == "pass" else "review",
        created_at_utc=now,
        completed_at_utc=now,
    )

    return payload
