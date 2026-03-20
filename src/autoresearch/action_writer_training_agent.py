"""action_writer_training_agent.py — Action Steps section training orchestrator.

The action writer is a deterministic pipeline worker. This agent:
  1. Reads approved book.json artifacts and evaluates the Action Steps the
     deterministic writer produced.
  2. Runs a fresh benchmark: regenerates Action Steps from current templates
     and scores immediately — so template improvements show up in scores
     without needing a new production run.
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

from src.autoresearch.llm_action_steps_core import build_llm_action_steps_trainer_review
from src.autoresearch.store import log_experiment
from src.autoresearch.training_corpus import ensure_approved_training_artifact
from src.generation.editorial import build_editorial_day_brief
from src.generation.real_section_generator import (
    _build_action_steps,
    _build_be_still,
    _build_exposition,
)
from src.models.devotional import DevotionalBook
from src.scripture.planner import select_daily_key_verses_reference
from src.scripture.retrieval import ScriptureRetriever, ScriptureResult


_FRESH_BENCHMARK_PASSAGES = [
    ("Luke 5:27-28", "Luke 5:27-32"),
    ("Proverbs 1:7-9", "Proverbs 1:1-19"),
    ("Colossians 3:12-14", "Colossians 3:1-17"),
    ("Habakkuk 2:1-4", "Habakkuk 1:1-17"),
    ("Psalm 23:4-6", "Psalm 23:1-6"),
]

ACTION_WRITER_TRAINER_PROFILE = {
    "role": "expert_action_writer_trainer",
    "mission": (
        "Train the action writer to produce steps that are specific, same-day applicable, "
        "and genuinely flow from the Be Still section — not from the exposition directly. "
        "Generic spiritual-productivity steps are failures, not partial passes."
    ),
    "junior_worker_assumption": (
        "Treat the action writer as a complete beginner. Assume every step set will be "
        "generic until proven passage-specific and same-day applicable. A connector phrase "
        "that references the exposition instead of Be Still is a structural failure. "
        "Steps that could appear in any devotional do not pass."
    ),
    "review_rubric": [
        "Does the connector phrase explicitly reference what the reader encountered in stillness?",
        "Is each step specific enough to be attempted today — not a vague ongoing disposition?",
        "Is obedience framed as response to revelation, not as self-improvement effort?",
        "Does at least one step acknowledge unfamiliarity grounded in God's faithfulness?",
        "Do the steps avoid resolving the tension named in the Be Still section?",
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


def run_fresh_action_steps_benchmark(repo_root: Path) -> dict[str, Any]:
    """Regenerate Action Steps from current templates and evaluate with LLM trainer.

    Score changes immediately reflect template improvements — no new production
    run needed. Also regenerates Be Still so the trainer can check the flow.
    Rotates through benchmark passages by hour.
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
    )
    action_connector, action_items = _build_action_steps(
        brief=brief,
        day_number=1,
        exposition_text=exposition_text,
        scripture_text=scripture_text,
    )

    try:
        review = build_llm_action_steps_trainer_review(
            action_items,
            action_connector,
            passage_reference=focal_reference,
            passage_text=scripture_text,
            be_still_prompts=be_still_prompts,
        )
    except Exception as exc:
        return {
            "status": "blocked",
            "benchmark_passage": focal_reference,
            "error": str(exc),
            "evaluation": None,
        }

    slug = re.sub(r"[^a-z0-9]+", "-", focal_reference.lower()).strip("-")
    log_experiment(
        experiment_id=f"action-steps-fresh-benchmark__{slug}__{now}",
        worker_name="action_writer",
        benchmark_name="llm-fresh-action-steps-benchmark",
        benchmark_reference=slug,
        status=review["status"],
        attempted_change=(
            f"Fresh benchmark: LLM trainer evaluated dynamically-generated Action Steps for {focal_reference}. "
            "Score reflects current template quality without requiring a new production run."
        ),
        metrics={
            "score": review["score"],
            "flows_from_be_still": review["flows_from_be_still"],
            "same_day_applicable": review["same_day_applicable"],
        },
        learning_note=(
            "Fresh benchmark regenerates Action Steps from current deterministic templates each cycle. "
            "Score changes directly track template improvements."
        ),
        keep_decision="keep" if review["status"] == "pass" else "review",
        created_at_utc=now,
        completed_at_utc=now,
    )

    return {
        "status": review["status"],
        "benchmark_passage": focal_reference,
        "action_connector": action_connector,
        "action_items": action_items,
        "be_still_prompts": be_still_prompts,
        "evaluation": review,
    }


def run_llm_action_steps_trainer_review(
    repo_root: Path, *, artifact: dict[str, Any]
) -> dict[str, Any]:
    """LLM trainer evaluates Action Steps from an approved artifact."""
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
        items = list(day.action_steps.items or [])
        if not items:
            continue

        connector_phrase = str(day.action_steps.connector_phrase or "").strip()
        be_still_prompts = list(day.be_still.prompts or [])
        context_reference = str(day.scripture.reference or "").strip()
        focal_reference = select_daily_key_verses_reference(
            reference=context_reference, max_key_verses=2
        )
        slug = re.sub(r"[^a-z0-9]+", "-", focal_reference.lower()).strip("-")
        scripture_text = _scripture_text(retriever, context_reference)
        if not scripture_text or scripture_text == context_reference:
            scripture_text = context_reference

        try:
            review = build_llm_action_steps_trainer_review(
                items,
                connector_phrase,
                passage_reference=focal_reference,
                passage_text=scripture_text,
                be_still_prompts=be_still_prompts,
            )
        except Exception as exc:
            return {
                "status": "blocked",
                "benchmark_passage": focal_reference,
                "error": str(exc),
                "evaluation": None,
            }

        log_experiment(
            experiment_id=f"action-writer-trainer-review__{slug}__{now}",
            worker_name="action_writer",
            benchmark_name="llm-action-steps-trainer-review",
            benchmark_reference=slug,
            status=review["status"],
            attempted_change=(
                f"LLM trainer evaluated deterministic Action Steps for {focal_reference}."
            ),
            metrics={
                "score": review["score"],
                "flows_from_be_still": review["flows_from_be_still"],
                "same_day_applicable": review["same_day_applicable"],
            },
            learning_note=(
                "LLM trainer reviewed the deterministic action writer's actual output. "
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
        "error": "No day with Action Steps found in the approved artifact.",
        "evaluation": None,
    }


@dataclass(frozen=True)
class ActionWriterTrainingAssignment:
    day_number: int
    focal_reference: str
    context_reference: str
    item_count: int
    connector_phrase: str
    rationale: str


def build_action_writer_training_cycle(repo_root: Path) -> dict[str, Any]:
    """Build a full Action Steps training cycle report."""
    artifact = ensure_approved_training_artifact(repo_root)
    if not artifact:
        return {
            "generated_at_utc": _utc_now(),
            "status": "blocked",
            "summary": "No approved artifact available for action writer training.",
            "assignments": [],
        }

    book = _load_book(Path(str(artifact["book_json_path"])))
    assignments: list[ActionWriterTrainingAssignment] = []

    for day in book.days[:6]:
        items = list(day.action_steps.items or [])
        context_reference = str(day.scripture.reference or "").strip()
        focal_reference = select_daily_key_verses_reference(
            reference=context_reference, max_key_verses=2
        )
        assignments.append(
            ActionWriterTrainingAssignment(
                day_number=int(day.day_number),
                focal_reference=focal_reference,
                context_reference=context_reference,
                item_count=len(items),
                connector_phrase=str(day.action_steps.connector_phrase or ""),
                rationale=(
                    "Evaluate whether Action Steps flow from Be Still (not exposition), "
                    "are same-day applicable, and convey active expectation."
                ),
            )
        )

    return {
        "generated_at_utc": _utc_now(),
        "status": "ready",
        "artifact": artifact,
        "trainer_profile": ACTION_WRITER_TRAINER_PROFILE,
        "assignments": [asdict(a) for a in assignments],
    }


def log_action_writer_training_cycle(repo_root: Path) -> dict[str, Any]:
    payload = build_action_writer_training_cycle(repo_root)
    now = _utc_now()

    if payload.get("status") != "ready":
        return payload

    for item in payload["assignments"]:
        log_experiment(
            experiment_id=f"action-writer__{item['context_reference']}__{item['day_number']}__{now}",
            worker_name="action_writer",
            benchmark_name="approved-artifact-action-writer-training",
            benchmark_reference=item["context_reference"],
            status="assigned",
            attempted_change=(
                f"Train action writer on focal reference {item['focal_reference']} "
                f"with context {item['context_reference']}."
            ),
            metrics={
                "day_number": item["day_number"],
                "item_count": item["item_count"],
            },
            learning_note="Action writer trained on approved prior content.",
            keep_decision="review",
            created_at_utc=now,
            completed_at_utc=now,
        )

    fresh_benchmark = run_fresh_action_steps_benchmark(repo_root)
    payload["fresh_benchmark"] = fresh_benchmark
    fresh_score = int((fresh_benchmark.get("evaluation") or {}).get("score", 0) or 0)
    fresh_status = str(fresh_benchmark.get("status") or "blocked")

    artifact_benchmark = run_llm_action_steps_trainer_review(repo_root, artifact=payload["artifact"])
    payload["artifact_benchmark"] = artifact_benchmark

    gate_score = fresh_score
    gate_status = fresh_status

    if gate_status == "blocked":
        action_status = "fail"
    elif gate_score >= 80:
        action_status = "pass"
    elif gate_score >= 60:
        action_status = "revise"
    else:
        action_status = "fail"

    log_experiment(
        experiment_id=f"action-writer-review__{now}",
        worker_name="action_writer",
        benchmark_name="approved-artifact-action-writer-review",
        benchmark_reference=str(payload["artifact"]["run_slug"]),
        status=action_status,
        attempted_change=(
            "Reviewed action writer training: fresh benchmark regenerated steps from current "
            "templates and scored. Pass = fresh score >= 80."
        ),
        metrics={
            "fresh_benchmark_score": gate_score,
            "fresh_benchmark_status": gate_status,
            "assignment_count": len(payload["assignments"]),
        },
        learning_note=(
            "Action writer fresh benchmark score (>= 80 = pass) is the quality gate. "
            "Score directly reflects current template quality."
        ),
        keep_decision="keep" if action_status == "pass" else "review",
        created_at_utc=now,
        completed_at_utc=now,
    )

    return payload
