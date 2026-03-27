from __future__ import annotations

import json
import sqlite3
import warnings
from datetime import datetime, timezone
from typing import Any

from src.models.registry import (
    AutoresearchExperimentRecord,
    OutlinerSystemComparisonRecord,
    TrainerRecommendationRecord,
)
from src.persistence.config import PersistenceConfig
from src.persistence.factory import create_socket
from src.persistence.paths import default_registry_db_path


def build_autoresearch_socket():
    cfg = PersistenceConfig.from_env()
    # If no absolute custom DB path was configured (i.e. the default relative
    # "registry.db" is in effect), always route autoresearch writes to the
    # local AppSupport DB.  The old condition was logically impossible:
    # cfg.sqlite_path ("registry.db") can never equal default_registry_db_path()
    # (an absolute path), so the override never fired and all writes went to
    # a relative "registry.db" on whatever the CWD happened to be (NAS).
    if not cfg.sqlite_path.is_absolute():
        cfg = PersistenceConfig(
            default_provider=cfg.default_provider,
            sqlite_path=default_registry_db_path(),
            component_providers=cfg.component_providers,
        )
    return create_socket(cfg, component="registry")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def log_experiment(
    *,
    experiment_id: str,
    worker_name: str,
    benchmark_name: str,
    benchmark_reference: str = "",
    run_slug: str = "",
    status: str = "",
    attempted_change: str = "",
    metrics: dict[str, Any] | None = None,
    learning_note: str = "",
    keep_decision: str = "",
    created_at_utc: str = "",
    completed_at_utc: str = "",
) -> AutoresearchExperimentRecord:
    # Always stamp completed_at_utc at the moment of logging — callers often
    # pass the cycle-start time for both fields, which gives zero duration.
    # created_at_utc (passed by callers) captures when the experiment began;
    # completed_at_utc is always the actual wall-clock time at log time.
    completed_at_utc = _utc_now()
    try:
        socket = build_autoresearch_socket()
        return socket.log_autoresearch_experiment(
            experiment_id=experiment_id,
            worker_name=worker_name,
            benchmark_name=benchmark_name,
            benchmark_reference=benchmark_reference,
            run_slug=run_slug,
            status=status,
            attempted_change=attempted_change,
            metrics_json=json.dumps(metrics or {}, sort_keys=True),
            learning_note=learning_note,
            keep_decision=keep_decision,
            created_at_utc=created_at_utc,
            completed_at_utc=completed_at_utc,
        )
    except Exception as exc:
        # DB lock (NAS/WAL) during supervisor run — warn but don't crash the benchmark.
        # Score was already computed and will be returned by the caller.
        warnings.warn(
            f"log_experiment({experiment_id!r}): DB write failed ({exc}). "
            "Score is valid; experiment will not be recorded.",
            RuntimeWarning,
            stacklevel=2,
        )
        return None  # type: ignore[return-value]


def list_experiments(
    *,
    worker_name: str | None = None,
    benchmark_name: str | None = None,
) -> list[AutoresearchExperimentRecord]:
    socket = build_autoresearch_socket()
    return socket.list_autoresearch_experiments(
        worker_name=worker_name,
        benchmark_name=benchmark_name,
    )


def record_trainer_recommendation(
    *,
    recommendation_id: str,
    trainer_name: str,
    worker_name: str,
    scripture_reference: str,
    passage_slug: str = "",
    priority: int = 0,
    rationale: str = "",
    selection_stage: str = "",
    status: str = "",
    created_at_utc: str = "",
    consumed_at_utc: str = "",
) -> TrainerRecommendationRecord:
    socket = build_autoresearch_socket()
    return socket.record_trainer_recommendation(
        recommendation_id=recommendation_id,
        trainer_name=trainer_name,
        worker_name=worker_name,
        scripture_reference=scripture_reference,
        passage_slug=passage_slug,
        priority=priority,
        rationale=rationale,
        selection_stage=selection_stage,
        status=status,
        created_at_utc=created_at_utc,
        consumed_at_utc=consumed_at_utc,
    )


def list_trainer_recommendations(
    *,
    trainer_name: str | None = None,
    worker_name: str | None = None,
    status: str | None = None,
) -> list[TrainerRecommendationRecord]:
    socket = build_autoresearch_socket()
    return socket.list_trainer_recommendations(
        trainer_name=trainer_name,
        worker_name=worker_name,
        status=status,
    )


def record_outliner_system_comparison(
    *,
    comparison_id: str,
    scripture_reference: str,
    passage_slug: str = "",
    range_label: str = "",
    assignment_payload: dict[str, Any] | None = None,
    interaction_log: dict[str, Any] | None = None,
    packet_snapshot: dict[str, Any] | None = None,
    reviewer_guidance: dict[str, Any] | None = None,
    artifact_paths: dict[str, Any] | None = None,
    legacy_system_name: str = "",
    legacy_system_reference: str = "",
    legacy_status: str = "",
    legacy_score: float | None = None,
    legacy_summary: str = "",
    legacy_metrics: dict[str, Any] | None = None,
    redesigned_system_name: str = "",
    redesigned_system_reference: str = "",
    redesigned_status: str = "",
    redesigned_score: float | None = None,
    redesigned_summary: str = "",
    redesigned_metrics: dict[str, Any] | None = None,
    winner: str = "",
    decision_status: str = "",
    decision_rationale: str = "",
    comparison_notes: str = "",
    reviewed_by: str = "",
    created_at_utc: str = "",
    completed_at_utc: str = "",
) -> OutlinerSystemComparisonRecord:
    socket = build_autoresearch_socket()
    return socket.record_outliner_system_comparison(
        comparison_id=comparison_id,
        scripture_reference=scripture_reference,
        passage_slug=passage_slug,
        range_label=range_label,
        assignment_payload_json=json.dumps(assignment_payload or {}, sort_keys=True),
        interaction_log_json=json.dumps(interaction_log or {}, sort_keys=True),
        packet_snapshot_json=json.dumps(packet_snapshot or {}, sort_keys=True),
        reviewer_guidance_json=json.dumps(reviewer_guidance or {}, sort_keys=True),
        artifact_paths_json=json.dumps(artifact_paths or {}, sort_keys=True),
        legacy_system_name=legacy_system_name,
        legacy_system_reference=legacy_system_reference,
        legacy_status=legacy_status,
        legacy_score=legacy_score,
        legacy_summary=legacy_summary,
        legacy_metrics_json=json.dumps(legacy_metrics or {}, sort_keys=True),
        redesigned_system_name=redesigned_system_name,
        redesigned_system_reference=redesigned_system_reference,
        redesigned_status=redesigned_status,
        redesigned_score=redesigned_score,
        redesigned_summary=redesigned_summary,
        redesigned_metrics_json=json.dumps(redesigned_metrics or {}, sort_keys=True),
        winner=winner,
        decision_status=decision_status,
        decision_rationale=decision_rationale,
        comparison_notes=comparison_notes,
        reviewed_by=reviewed_by,
        created_at_utc=created_at_utc,
        completed_at_utc=completed_at_utc,
    )


def is_benchmark_retired(
    worker_name: str,
    benchmark_reference: str,
    *,
    min_attempts: int = 20,
) -> bool:
    """Return True if a benchmark passage has been attempted min_attempts times with zero passes.

    Training cycles should call this before running an assignment to avoid
    wasting cycles on provably dead passages. Passages are retired by
    run_health_check.py, which archives their experiments automatically.
    """
    if not benchmark_reference:
        return False
    db_path = default_registry_db_path()
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        row = conn.execute(
            """SELECT COUNT(*) as total,
                      SUM(CASE WHEN status = 'pass' THEN 1 ELSE 0 END) as passes
               FROM autoresearch_experiments
               WHERE worker_name = ? AND benchmark_reference = ?
               AND status IN ('pass', 'fail', 'revise')""",
            (worker_name, benchmark_reference),
        ).fetchone()
        conn.close()
        if row and row[0] >= min_attempts and row[1] == 0:
            return True
    except Exception:
        pass
    return False


def check_worker_alerts(
    *,
    structural_threshold: int = 50,
    structural_pass_rate_ceiling: float = 0.05,
    scoreable_statuses: tuple[str, ...] = ("pass", "fail", "revise"),
    exclude_workers: tuple[str, ...] = (
        "research_librarian",  # uses "completed" status, not pass/fail
        "training_manager",
        "output_training_manager",
        "library_trainer",
        "theological_reviewer",
        "policy_guardian",
        "resource_coordinator",
        "general_librarian",
        "grok_supervisor",
    ),
) -> list[dict[str, Any]]:
    """Return a list of alert dicts for workers that warrant structural review.

    Alert types
    -----------
    structural_low_pass_rate
        Worker has >= structural_threshold scoreable experiments and a pass
        rate below structural_pass_rate_ceiling across all of them.  Per
        Competition Director instruction: flag at 50+ experiments / <5% pass.

    Returns a (possibly empty) list of dicts with keys:
        alert_type, worker_name, total_scoreable, pass_count, pass_rate, message
    """
    db_path = default_registry_db_path()
    alerts: list[dict[str, Any]] = []
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        placeholders = ",".join("?" * len(scoreable_statuses))
        exclude_placeholders = ",".join("?" * len(exclude_workers))
        cur.execute(
            f"""
            SELECT
                worker_name,
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'pass' THEN 1 ELSE 0 END) AS passes
            FROM autoresearch_experiments
            WHERE status IN ({placeholders})
              AND worker_name NOT IN ({exclude_placeholders})
            GROUP BY worker_name
            HAVING total >= ?
            """,
            (*scoreable_statuses, *exclude_workers, structural_threshold),
        )
        for worker_name, total, passes in cur.fetchall():
            pass_rate = (passes or 0) / total
            if pass_rate < structural_pass_rate_ceiling:
                alerts.append(
                    {
                        "alert_type": "structural_low_pass_rate",
                        "worker_name": worker_name,
                        "total_scoreable": total,
                        "pass_count": passes or 0,
                        "pass_rate": round(pass_rate, 4),
                        "message": (
                            f"{worker_name}: {passes or 0}/{total} pass "
                            f"({pass_rate * 100:.1f}%) — below {structural_pass_rate_ceiling * 100:.0f}% "
                            f"threshold across {total} experiments. Structural review required."
                        ),
                    }
                )
        conn.close()
    except Exception as exc:
        warnings.warn(
            f"check_worker_alerts: DB query failed ({exc}).",
            RuntimeWarning,
            stacklevel=2,
        )
    return alerts


def list_outliner_system_comparisons(
    *,
    scripture_reference: str | None = None,
    passage_slug: str | None = None,
    decision_status: str | None = None,
) -> list[OutlinerSystemComparisonRecord]:
    socket = build_autoresearch_socket()
    return socket.list_outliner_system_comparisons(
        scripture_reference=scripture_reference,
        passage_slug=passage_slug,
        decision_status=decision_status,
    )
