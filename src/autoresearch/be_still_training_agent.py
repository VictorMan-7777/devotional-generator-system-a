"""be_still_training_agent.py — Be Still section training orchestrator.

The Be Still writer is a deterministic pipeline worker. This agent:
  1. Reads approved book.json artifacts and evaluates the Be Still sections
     the deterministic writer produced.
  2. Runs a fresh benchmark: regenerates Be Still from current templates and
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

from src.autoresearch.llm_be_still_core import build_llm_be_still_trainer_review
from src.autoresearch.store import log_experiment
from src.autoresearch.training_corpus import ensure_approved_training_artifact
from src.generation.editorial import build_editorial_day_brief
from src.generation.real_section_generator import _build_be_still, _build_exposition
from src.models.devotional import BeStillSection, DevotionalBook
from src.validation.ac_scorer import ac_scores_to_metrics, score_be_still
from src.scripture.planner import select_daily_key_verses_reference
from src.scripture.retrieval import ScriptureFailureAlert, ScriptureRetriever, ScriptureResult


_FRESH_BENCHMARK_PASSAGES = [
    ("Habakkuk 1:1-4", "Habakkuk 1:1-11"),
    ("Isaiah 40:28-31", "Isaiah 40:27-31"),
    ("Exodus 20:1-3", "Exodus 20:1-21"),    # was 19:1-20:21 (cross-chapter, blocks retriever)
    ("Colossians 3:1-4", "Colossians 3:1-17"),
    ("Luke 15:11-14", "Luke 15:11-32"),
]

BE_STILL_TRAINER_PROFILE = {
    "role": "expert_be_still_trainer",
    "mission": (
        "Train the Be Still writer to produce prompts that genuinely guide the reader "
        "from inward receptivity to a felt need for action — anchored to the specific "
        "passage, never generic stillness filler."
    ),
    "junior_worker_assumption": (
        "Treat the Be Still writer as a complete beginner. Assume every prompt set will "
        "be generic until proven passage-specific. A closing prompt that appears verbatim "
        "in every output regardless of passage is a structural failure, not a training issue. "
        "Do not pass based on second-person language alone — require genuine passage anchoring."
    ),
    "review_rubric": [
        "Does the first prompt genuinely invite stillness — or does it rush to reflection?",
        "Do prompts move inward then outward, or do they stay at the same level throughout?",
        "Does the final prompt create a felt need that flows into action without resolving it?",
        "Are prompts passage-specific or could they appear in any devotional?",
        "Do prompts arise from the exposition, or do they introduce new concepts?",
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


def run_fresh_be_still_benchmark(repo_root: Path) -> dict[str, Any]:
    """Regenerate Be Still from current templates and evaluate with LLM trainer.

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

    # Retrieve focal passage text separately so focus_clause checks are scoped to the
    # focal passage, not the full study window (avoids false positive cross-verse matches).
    focal_scripture_text = _scripture_text(retriever, focal_reference)
    if not focal_scripture_text or focal_scripture_text == focal_reference:
        focal_scripture_text = scripture_text  # fall back to context if focal fails

    brief = build_editorial_day_brief(
        day_number=1,
        scripture_reference=focal_reference,
        scripture_text=scripture_text,
        study_window_reference=context_reference,
    )
    exposition_text = _build_exposition(brief=brief, scripture_text=scripture_text)
    be_still_prompts = _build_be_still(
        brief=brief,
        scripture_text=scripture_text,
        exposition_text=exposition_text,
        focal_scripture_text=focal_scripture_text,
    )

    try:
        review = build_llm_be_still_trainer_review(
            be_still_prompts,
            passage_reference=focal_reference,
            passage_text=scripture_text,
            exposition_text=exposition_text,
        )
    except Exception as exc:
        return {
            "status": "blocked",
            "benchmark_passage": focal_reference,
            "error": str(exc),
            "evaluation": None,
        }

    slug = re.sub(r"[^a-z0-9]+", "-", focal_reference.lower()).strip("-")
    _section = BeStillSection(prompts=be_still_prompts)
    _ac = ac_scores_to_metrics(score_be_still(_section))
    log_experiment(
        experiment_id=f"be-still-fresh-benchmark__{slug}__{now}",
        worker_name="be_still_writer",
        benchmark_name="llm-fresh-be-still-benchmark",
        benchmark_reference=slug,
        status=review["status"],
        attempted_change=(
            f"Fresh benchmark: LLM trainer evaluated dynamically-generated Be Still prompts for {focal_reference}. "
            "Score reflects current template quality without requiring a new production run."
        ),
        metrics={
            "score": review["score"],
            "passage_anchored": review["passage_anchored"],
            "inward_to_outward": review["inward_to_outward"],
            **_ac,
        },
        learning_note=(
            "Fresh benchmark regenerates Be Still from current deterministic templates each cycle. "
            "Score changes directly track template improvements."
        ),
        keep_decision="keep" if review["status"] == "pass" else "review",
        created_at_utc=now,
        completed_at_utc=now,
    )

    return {
        "status": review["status"],
        "benchmark_passage": focal_reference,
        "be_still_prompts": be_still_prompts,
        "evaluation": review,
    }


def run_llm_be_still_trainer_review(
    repo_root: Path, *, artifact: dict[str, Any]
) -> dict[str, Any]:
    """LLM trainer evaluates Be Still sections from an approved artifact."""
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
        prompts = list(day.be_still.prompts or [])
        if not prompts:
            continue

        context_reference = str(day.scripture.reference or "").strip()
        focal_reference = select_daily_key_verses_reference(
            reference=context_reference, max_key_verses=2
        )
        slug = re.sub(r"[^a-z0-9]+", "-", focal_reference.lower()).strip("-")
        scripture_text = _scripture_text(retriever, context_reference)
        if not scripture_text or scripture_text == context_reference:
            scripture_text = context_reference

        exposition_text = str(day.exposition.text or "").strip()

        try:
            review = build_llm_be_still_trainer_review(
                prompts,
                passage_reference=focal_reference,
                passage_text=scripture_text,
                exposition_text=exposition_text,
            )
        except Exception as exc:
            return {
                "status": "blocked",
                "benchmark_passage": focal_reference,
                "error": str(exc),
                "evaluation": None,
            }

        log_experiment(
            experiment_id=f"be-still-trainer-review__{slug}__{now}",
            worker_name="be_still_writer",
            benchmark_name="llm-be-still-trainer-review",
            benchmark_reference=slug,
            status=review["status"],
            attempted_change=(
                f"LLM trainer evaluated deterministic Be Still prompts for {focal_reference}."
            ),
            metrics={
                "score": review["score"],
                "passage_anchored": review["passage_anchored"],
                "inward_to_outward": review["inward_to_outward"],
            },
            learning_note=(
                "LLM trainer reviewed the deterministic Be Still writer's actual output. "
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
        "error": "No day with Be Still prompts found in the approved artifact.",
        "evaluation": None,
    }


@dataclass(frozen=True)
class BeStillTrainingAssignment:
    day_number: int
    focal_reference: str
    context_reference: str
    prompt_count: int
    rationale: str


def build_be_still_training_cycle(repo_root: Path) -> dict[str, Any]:
    """Build a full Be Still training cycle report."""
    artifact = ensure_approved_training_artifact(repo_root)
    if not artifact:
        return {
            "generated_at_utc": _utc_now(),
            "status": "blocked",
            "summary": "No approved artifact available for Be Still training.",
            "assignments": [],
        }

    book = _load_book(Path(str(artifact["book_json_path"])))
    assignments: list[BeStillTrainingAssignment] = []

    for day in book.days[:6]:
        prompts = list(day.be_still.prompts or [])
        context_reference = str(day.scripture.reference or "").strip()
        focal_reference = select_daily_key_verses_reference(
            reference=context_reference, max_key_verses=2
        )
        assignments.append(
            BeStillTrainingAssignment(
                day_number=int(day.day_number),
                focal_reference=focal_reference,
                context_reference=context_reference,
                prompt_count=len(prompts),
                rationale=(
                    "Evaluate whether Be Still prompts are genuinely passage-specific "
                    "and move inward-to-outward without resolving the tension."
                ),
            )
        )

    return {
        "generated_at_utc": _utc_now(),
        "status": "ready",
        "artifact": artifact,
        "trainer_profile": BE_STILL_TRAINER_PROFILE,
        "assignments": [asdict(a) for a in assignments],
    }


def log_be_still_training_cycle(repo_root: Path) -> dict[str, Any]:
    payload = build_be_still_training_cycle(repo_root)
    now = _utc_now()

    if payload.get("status") != "ready":
        return payload

    for item in payload["assignments"]:
        log_experiment(
            experiment_id=f"be-still-writer__{item['context_reference']}__{item['day_number']}__{now}",
            worker_name="be_still_writer",
            benchmark_name="approved-artifact-be-still-training",
            benchmark_reference=item["context_reference"],
            status="assigned",
            attempted_change=(
                f"Train Be Still writer on focal reference {item['focal_reference']} "
                f"with context {item['context_reference']}."
            ),
            metrics={
                "day_number": item["day_number"],
                "prompt_count": item["prompt_count"],
            },
            learning_note="Be Still writer trained on approved prior content.",
            keep_decision="review",
            created_at_utc=now,
            completed_at_utc=now,
        )

    fresh_benchmark = run_fresh_be_still_benchmark(repo_root)
    payload["fresh_benchmark"] = fresh_benchmark
    fresh_score = int((fresh_benchmark.get("evaluation") or {}).get("score", 0) or 0)
    fresh_status = str(fresh_benchmark.get("status") or "blocked")

    artifact_benchmark = run_llm_be_still_trainer_review(repo_root, artifact=payload["artifact"])
    payload["artifact_benchmark"] = artifact_benchmark

    # Primary gate uses fresh benchmark (current template quality)
    gate_score = fresh_score
    gate_status = fresh_status

    if gate_status == "blocked":
        be_still_status = "fail"
    elif gate_score >= 80:
        be_still_status = "pass"
    elif gate_score >= 60:
        be_still_status = "revise"
    else:
        be_still_status = "fail"

    log_experiment(
        experiment_id=f"be-still-writer-review__{now}",
        worker_name="be_still_writer",
        benchmark_name="approved-artifact-be-still-review",
        benchmark_reference=str(payload["artifact"]["run_slug"]),
        status=be_still_status,
        attempted_change=(
            "Reviewed Be Still training: fresh benchmark regenerated prompts from current "
            "templates and scored. Pass = fresh score >= 80."
        ),
        metrics={
            "fresh_benchmark_score": gate_score,
            "fresh_benchmark_status": gate_status,
            "assignment_count": len(payload["assignments"]),
        },
        learning_note=(
            "Be Still writer fresh benchmark score (>= 80 = pass) is the quality gate. "
            "Score directly reflects current template quality."
        ),
        keep_decision="keep" if be_still_status == "pass" else "review",
        created_at_utc=now,
        completed_at_utc=now,
    )

    return payload
