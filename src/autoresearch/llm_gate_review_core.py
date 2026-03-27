"""llm_gate_review_core.py — 50-experiment gate review for training workers.

At every 50-experiment boundary (50, 100, 150, ...) the supervisor triggers a gate
review for any worker that has crossed a new gate since the last check.  The gate
review is a meta-evaluation: it looks at the full training history, detects whether
the trainer is repeating the same coaching without change (the "insanity pattern"),
and produces concrete recommendations for structural improvements to the worker or
trainer prompt.

Each gate review is logged as an experiment record so the supervisor can detect
whether a gate has already been evaluated this cycle.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from src.autoresearch.store import list_experiments, log_experiment
from src.llm.router import get_cross_llm_client


_GATE_REVIEW_PROMPT = """\
You are a master training director overseeing the development of a Reformed evangelical \
devotional AI worker. You are conducting a mandatory {gate_number}-experiment gate review \
for the "{worker_name}" worker.

AGGREGATE TRAINING STATISTICS:
{aggregate_stats}

PASS RATE TREND (most recent 50 vs prior 50):
{trend_summary}

MOST REPEATED COACHING NOTES (signs of the insanity pattern — same feedback, no change):
{repeated_coaching}

RECENT FAILURE PATTERNS:
{failure_patterns}

YOUR MANDATORY ASSESSMENT:

1. INSANITY PATTERN CHECK: Is the training repeating the same coaching with no \
meaningful improvement? If the same notes appear 5+ times with no pass-rate \
improvement, this is the insanity pattern. Name it directly.

2. WHAT IS NOT CHANGING: What specific capability gap has persisted across every \
gate? Name the root cause — is it the worker template, the trainer evaluation \
criteria, the passage selection, the benchmark difficulty, or something else?

3. STRUCTURAL CHANGES REQUIRED: What specific changes to the worker code, trainer \
prompt, evaluation criteria, or benchmark selection would actually move the needle? \
Be concrete — "tighten the criterion for X", "the worker needs to change Y logic", \
"the benchmark is systematically too hard/easy because Z".

4. GATE VERDICT:
   - "on_track" — pass rate is improving and the training approach is working
   - "stalled" — flat or declining pass rate; training approach is not working
   - "insanity_loop" — trainer repeating same coaching for 20+ experiments with no \
     improvement; immediate intervention required

Respond with ONLY valid JSON, no explanation:
{{
  "gate_number": {gate_number},
  "worker_name": "{worker_name}",
  "gate_verdict": "<on_track|stalled|insanity_loop>",
  "insanity_pattern_detected": <true|false>,
  "insanity_evidence": "<what is being repeated and for how many experiments>",
  "root_cause": "<the core capability gap that has persisted>",
  "structural_changes": [
    "<specific actionable change 1>",
    "<specific actionable change 2>",
    "<specific actionable change 3>"
  ],
  "coaching_notes": "<brief summary of what the training has tried so far>",
  "priority_intervention": "<the single most important thing to change right now>"
}}
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _aggregate_stats(records: list[Any]) -> str:
    total = len(records)
    by_status: Counter[str] = Counter(r.status for r in records)
    pass_rate = round(by_status.get("pass", 0) / total * 100, 1) if total else 0.0
    by_benchmark: dict[str, Counter[str]] = {}
    for r in records:
        bm = str(r.benchmark_name or "unknown")
        by_benchmark.setdefault(bm, Counter())[r.status] += 1
    lines = [
        f"Total experiments: {total}",
        f"Pass: {by_status.get('pass', 0)}  Revise: {by_status.get('revise', 0)}  "
        f"Fail: {by_status.get('fail', 0)}  Infeasible: {by_status.get('task_infeasible', 0)}",
        f"Overall pass rate: {pass_rate}%",
        "",
        "By benchmark:",
    ]
    for bm, counts in sorted(by_benchmark.items()):
        bm_total = sum(counts.values())
        bm_pass = counts.get("pass", 0)
        lines.append(f"  {bm}: {bm_pass}/{bm_total} pass")
    return "\n".join(lines)


def _trend_summary(records: list[Any]) -> str:
    sorted_records = sorted(records, key=lambda r: r.created_at_utc or "")
    recent = sorted_records[-50:]
    prior = sorted_records[-100:-50] if len(sorted_records) >= 100 else []
    recent_pass = sum(1 for r in recent if r.status == "pass")
    prior_pass = sum(1 for r in prior if r.status == "pass") if prior else None
    recent_rate = round(recent_pass / len(recent) * 100, 1) if recent else 0.0
    lines = [f"Most recent 50: {recent_pass} passes ({recent_rate}%)"]
    if prior_pass is not None:
        prior_rate = round(prior_pass / len(prior) * 100, 1)
        delta = recent_rate - prior_rate
        direction = "▲ improving" if delta > 2 else ("▼ declining" if delta < -2 else "→ flat")
        lines.append(f"Prior 50: {prior_pass} passes ({prior_rate}%)  {direction} ({delta:+.1f}%)")
    else:
        lines.append("Prior 50: insufficient data")
    return "\n".join(lines)


def _repeated_coaching(records: list[Any]) -> str:
    notes: Counter[str] = Counter()
    for r in records:
        try:
            metrics = json.loads(r.metrics_json or "{}")
        except (json.JSONDecodeError, AttributeError):
            metrics = {}
        for note in (metrics.get("coaching_notes") or []):
            note_str = str(note).strip()
            if note_str:
                # Normalise to first 80 chars to catch near-duplicates
                notes[note_str[:80]] += 1
    if not notes:
        return "No coaching notes found in experiment records."
    lines = []
    for note, count in notes.most_common(8):
        flag = "  ⚠ REPEATED" if count >= 5 else ""
        lines.append(f"  [{count}x]{flag} {note}")
    return "\n".join(lines)


def _failure_patterns(records: list[Any]) -> str:
    sorted_records = sorted(records, key=lambda r: r.created_at_utc or "")
    recent_failures = [r for r in sorted_records[-50:] if r.status in ("fail", "revise")]
    if not recent_failures:
        return "No recent failures."
    learning_notes: Counter[str] = Counter()
    for r in recent_failures:
        note = str(r.learning_note or "").strip()
        if note:
            learning_notes[note[:100]] += 1
    lines = [f"Recent failures/revisions in last 50: {len(recent_failures)}"]
    for note, count in learning_notes.most_common(5):
        lines.append(f"  [{count}x] {note}")
    return "\n".join(lines)


def _last_evaluated_gate(worker_name: str) -> int:
    """Return the highest gate number that has already been evaluated for this worker."""
    records = list_experiments(worker_name=worker_name)
    gate_evals = [
        r for r in records
        if str(r.benchmark_name or "").startswith("gate-review-")
    ]
    if not gate_evals:
        return 0
    gates = []
    for r in gate_evals:
        try:
            gates.append(int(str(r.benchmark_name).removeprefix("gate-review-")))
        except ValueError:
            pass
    return max(gates) if gates else 0


def _current_gate(worker_name: str) -> int:
    """Return the current 50-experiment gate for this worker."""
    count = len(list_experiments(worker_name=worker_name))
    return (count // 50) * 50


def pending_gate_reviews(worker_names: list[str]) -> list[tuple[str, int]]:
    """Return (worker_name, gate_number) for any worker that has crossed a new gate
    since the last evaluation.  The supervisor calls this to know what to run."""
    pending = []
    for worker in worker_names:
        current = _current_gate(worker)
        last = _last_evaluated_gate(worker)
        if current > last and current >= 50:
            pending.append((worker, current))
    return pending


def run_gate_review(worker_name: str, gate_number: int) -> dict[str, Any]:
    """Run the gate review LLM call for a worker at a specific gate.  Logs the result
    as an experiment record so it won't be re-run next cycle."""
    records = list_experiments(worker_name=worker_name)
    client = get_cross_llm_client(worker=worker_name)

    prompt = _GATE_REVIEW_PROMPT.format(
        gate_number=gate_number,
        worker_name=worker_name,
        aggregate_stats=_aggregate_stats(records),
        trend_summary=_trend_summary(records),
        repeated_coaching=_repeated_coaching(records),
        failure_patterns=_failure_patterns(records),
    )

    result: dict[str, Any] = {
        "gate_number": gate_number,
        "worker_name": worker_name,
        "gate_verdict": "stalled",
        "insanity_pattern_detected": False,
        "insanity_evidence": "",
        "root_cause": "",
        "structural_changes": [],
        "coaching_notes": "",
        "priority_intervention": "",
        "llm_error": "",
    }

    try:
        raw = client.complete(prompt)
        raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
        raw = re.sub(r"\s*```$", "", raw.strip())
        parsed = json.loads(raw)
        result.update({k: v for k, v in parsed.items() if k in result})
    except Exception as exc:
        result["llm_error"] = str(exc)

    utc_now = _utc_now()
    log_experiment(
        experiment_id=f"{worker_name}__gate-review__{gate_number}__{utc_now}",
        worker_name=worker_name,
        benchmark_name=f"gate-review-{gate_number}",
        benchmark_reference=f"{worker_name} gate review at {gate_number} experiments",
        status="completed",
        attempted_change=f"Gate review at {gate_number} experiments.",
        metrics={
            "gate_verdict": result["gate_verdict"],
            "insanity_pattern_detected": result["insanity_pattern_detected"],
            "structural_changes": result["structural_changes"],
        },
        learning_note=(
            f"Gate {gate_number}: {result['gate_verdict']}. "
            f"Priority: {result['priority_intervention']}"
        ),
        keep_decision="keep",
        created_at_utc=utc_now,
        completed_at_utc=utc_now,
    )

    return result
