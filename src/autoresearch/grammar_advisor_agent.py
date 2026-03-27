from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.autoresearch.llm_grammar_advisor_core import build_llm_grammar_review
from src.autoresearch.store import log_experiment
from src.autoresearch.training_corpus import ensure_approved_training_artifact
from src.models.devotional import DevotionalBook


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_book(path: Path) -> DevotionalBook:
    return DevotionalBook.model_validate(json.loads(path.read_text(encoding="utf-8")))


@dataclass(frozen=True)
class GrammarAdvisorFinding:
    title: str
    severity: str
    rationale: str
    recommendation: str


GRAMMAR_ADVISOR_PROFILE = {
    "role": "expert_grammar_advisor",
    "mission": (
        "Work alongside the theological reviewer as a coaching pair for the exposition writer. "
        "The theological reviewer owns doctrinal accuracy and passage faithfulness. "
        "The grammar advisor owns prose clarity, sentence discipline, and paragraph rhythm. "
        "These are not competing concerns — clear prose serves the theology; muddled prose obscures it. "
        "Never recommend a prose change that would reduce theological precision. "
        "When a long sentence is carrying genuine theological weight, flag the length but defer to the "
        "theological reviewer on whether the weight justifies it."
    ),
    "coaching_partnership": (
        "The grammar advisor and theological reviewer always coach the exposition writer together. "
        "Good theology and good grammar are both required — neither is optional and neither excuses the other. "
        "The grammar advisor flags mechanical prose failures; the theological reviewer flags doctrinal ones. "
        "Both sets of findings must be resolved independently. The exposition writer cannot pass on theology "
        "alone or grammar alone — both coaches must sign off."
    ),
    "junior_worker_assumption": (
        "Assume the exposition writer is still learning. Expect repetitive sentence openings, overlong sentences, "
        "and abstraction unless the review layer proves otherwise."
    ),
    "review_rubric": [
        "Are sentences clear and grammatically stable?",
        "Do paragraphs flow instead of stacking disconnected abstractions?",
        "Is there unnecessary repetition in sentence openings or cadence?",
        "Does readability improve without softening the passage burden?",
        "Is this a grammar problem, a theology problem, or both? Flag which reviewer owns the fix.",
    ],
}


def build_grammar_advisor_report(repo_root: Path) -> dict[str, Any]:
    artifact = ensure_approved_training_artifact(repo_root)
    if not artifact:
        return {
            "reviewed_at_utc": _utc_now(),
            "trainer_profile": GRAMMAR_ADVISOR_PROFILE,
            "status": "blocked",
            "summary": "No approved training artifact is available yet for grammar review.",
            "findings": [],
            "metrics": {"reviewed_days": 0, "long_sentence_count": 0, "repeated_opening_count": 0},
        }

    book = _load_book(Path(str(artifact["book_json_path"])))
    findings: list[GrammarAdvisorFinding] = []
    long_sentence_count = 0
    repeated_opening_count = 0
    reviewed_days = 0
    openings: list[str] = []

    for day in book.days[:6]:
        reviewed_days += 1
        text = str(day.exposition.text or "").strip()
        sentences = [item.strip() for item in re.split(r"(?<=[.!?])\s+", text) if item.strip()]
        long_sentence_count += sum(1 for sentence in sentences if len(sentence.split()) > 34)
        for sentence in sentences[:3]:
            words = sentence.split()
            if len(words) >= 2:
                openings.append(" ".join(words[:2]).lower())

    repeated_opening_count = sum(count - 1 for count in {item: openings.count(item) for item in set(openings)}.values() if count > 1)

    if long_sentence_count:
        findings.append(
            GrammarAdvisorFinding(
                title="Long exposition sentences still need tightening",
                severity="medium",
                rationale=(
                    f"The reviewed exposition set still contains {long_sentence_count} sentence(s) longer than 34 words, "
                    "which usually makes junior prose harder to read than it needs to be."
                ),
                recommendation="Shorten long exposition sentences and vary cadence without reducing theological precision.",
            )
        )
    if repeated_opening_count:
        findings.append(
            GrammarAdvisorFinding(
                title="Exposition openings are becoming repetitive",
                severity="medium",
                rationale=(
                    f"The reviewed exposition set repeated early sentence openings {repeated_opening_count} time(s), "
                    "which can make the prose feel mechanical."
                ),
                recommendation="Vary paragraph and sentence openings so the exposition reads like shaped prose rather than a template.",
            )
        )
    if not findings:
        findings.append(
            GrammarAdvisorFinding(
                title="Current approved exposition cleared first-pass grammar review",
                severity="low",
                rationale="The approved exposition sample did not trigger the current grammar-advisor heuristics.",
                recommendation="Keep this advisor in the loop as a prose-quality reviewer while the exposition writer is still training.",
            )
        )

    return {
        "reviewed_at_utc": _utc_now(),
        "trainer_profile": GRAMMAR_ADVISOR_PROFILE,
        "status": "reviewed",
        "artifact": artifact,
        "metrics": {
            "reviewed_days": reviewed_days,
            "long_sentence_count": long_sentence_count,
            "repeated_opening_count": repeated_opening_count,
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


def run_llm_grammar_advisor_benchmark(repo_root: Path) -> dict[str, Any]:
    """Run LLM grammar review on the latest LLM exposition benchmark output.

    Evaluates the exposition writer's generated text for prose clarity,
    sentence rhythm, and mechanical discipline via LLM expert review.
    """
    output_dir = repo_root / "docs" / "system" / "outputs"
    matches = sorted(output_dir.glob("*__devg__exposition-training-cycle.json"))
    if not matches:
        return {"status": "blocked", "reason": "No exposition training cycle output found."}

    try:
        data = json.loads(matches[-1].read_text())
    except Exception:
        return {"status": "blocked", "reason": "Could not read exposition training cycle output."}

    llm_benchmark = data.get("llm_benchmark") or {}
    exposition_text = str(llm_benchmark.get("generated_text") or "").strip()
    focal_reference = str(llm_benchmark.get("benchmark_passage") or "exposition-benchmark")

    if not exposition_text:
        return {
            "status": "blocked",
            "reason": "No LLM exposition text in latest training cycle. Run exposition benchmark first.",
        }

    result = build_llm_grammar_review(exposition_text, focal_reference=focal_reference)

    now = _utc_now()
    log_experiment(
        experiment_id=f"grammar-advisor-llm-benchmark__{now}",
        worker_name="grammar_advisor",
        benchmark_name="llm-grammar-review-benchmark",
        benchmark_reference=focal_reference,
        status=result["status"],
        attempted_change=(
            f"Grammar advisor AI agent reviewed LLM exposition output for {focal_reference}. "
            "Evaluated prose clarity, sentence rhythm, and mechanical discipline."
        ),
        metrics={
            "score": result["score"],
            "overlong_sentence_count": int((result.get("metrics") or {}).get("overlong_sentence_count") or 0),
            "repetitive_opening_count": int((result.get("metrics") or {}).get("repetitive_opening_count") or 0),
            "finding_count": len(result.get("findings") or []),
        },
        learning_note=(
            "Grammar advisor AI agent reviewed LLM-generated exposition for benchmark passage. "
            "Score reflects actual prose quality against the rubric."
        ),
        keep_decision="keep" if result["status"] == "pass" else "review",
        created_at_utc=now,
        completed_at_utc=now,
    )

    return result


def log_grammar_advisor_report(repo_root: Path) -> dict[str, Any]:
    payload = build_grammar_advisor_report(repo_root)
    now = _utc_now()
    log_experiment(
        experiment_id="grammar-advisor__current-cycle",
        worker_name="grammar_advisor",
        benchmark_name="exposition-grammar-review",
        benchmark_reference="approved artifact grammar screen",
        status="reviewed" if payload.get("status") == "reviewed" else "blocked",
        attempted_change="Reviewed current exposition prose for grammar, cadence, and paragraph clarity.",
        metrics={
            "reviewed_days": payload["metrics"]["reviewed_days"],
            "long_sentence_count": payload["metrics"]["long_sentence_count"],
            "repeated_opening_count": payload["metrics"]["repeated_opening_count"],
            "finding_count": len(payload["findings"]),
        },
        learning_note="Expert grammar advisor screened approved exposition for prose clarity and repetition.",
        keep_decision="keep",
        created_at_utc=now,
        completed_at_utc=now,
    )

    # ── LLM benchmark: invoke the grammar advisor AI on the latest exposition output ──
    if payload.get("status") == "reviewed":
        llm_benchmark = run_llm_grammar_advisor_benchmark(repo_root)
        payload["llm_benchmark"] = llm_benchmark

    return payload
