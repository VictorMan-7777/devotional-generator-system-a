from __future__ import annotations

import glob
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.autoresearch.store import list_experiments


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


PSALM23_EXCLUSION_PATTERNS = [
    'psalm 23',
    'psalm-23',
    'psalms 23',
    'ps 23',
]


def _is_psalm23_excluded(run_slug: str) -> bool:
    return any(pattern in run_slug.lower() for pattern in PSALM23_EXCLUSION_PATTERNS)


def _decision_counts(path: Path) -> dict[str, int]:
    if not path.exists():
        return {}
    payload = _load_json(path)
    counts: dict[str, int] = {}
    for item in payload.get("decisions", []) or []:
        decision = str(item.get("decision") or "").strip().lower()
        if not decision:
            continue
        counts[decision] = counts.get(decision, 0) + 1
    return counts


def collect_pdf_training_corpus(repo_root: Path) -> list[dict[str, Any]]:
    output_dir = repo_root / "outputs" / "devotionals"
    pdf_paths = sorted(output_dir.glob("*__kdp-personal-preview.pdf"))
    corpus: list[dict[str, Any]] = []
    for pdf_path in pdf_paths:
        stem = pdf_path.name.replace("__kdp-personal-preview.pdf", "")
        decisions_path = pdf_path.with_name(f"{stem}__approval-decisions.json")
        edits_path = pdf_path.with_name(f"{stem}__review-edits.json")
        counts = _decision_counts(decisions_path)
        corpus.append(
            {
                "pdf_path": str(pdf_path),
                "decisions_path": str(decisions_path) if decisions_path.exists() else "",
                "review_edits_path": str(edits_path) if edits_path.exists() else "",
                "approved_count": counts.get("approved", 0),
                "rejected_count": counts.get("rejected", 0),
                "artifact_type": (
                    "reject-heavy"
                    if counts.get("rejected", 0) >= max(10, counts.get("approved", 0))
                    else "mixed-review"
                ),
            }
        )
    return corpus


def _candidate_meta_paths(repo_root: Path) -> list[Path]:
    # Return all available meta paths sorted newest-first so the training cycle
    # evaluates the most recent production output, not a hardcoded old artifact.
    # This ensures training scores reflect actual current pipeline quality.
    all_paths = sorted(
        glob.glob(str(repo_root / "outputs" / "devotionals" / "*__meta.json")),
        reverse=True,
    )
    return [Path(p) for p in all_paths]


def _book_contains_psalm23(book_path: Path) -> bool:
    """Return True if the book.json days contain Psalm 23 scripture references."""
    if not book_path.exists():
        return False
    try:
        book = _load_json(book_path)
        for day in book.get("days", []):
            scripture = day.get("scripture") or {}
            ref = str(scripture.get("reference", "") if isinstance(scripture, dict) else "").lower()
            if _is_psalm23_excluded(ref):
                return True
    except Exception:
        pass
    return False


def ensure_approved_training_artifact(repo_root: Path) -> dict[str, Any] | None:
    for meta_path in _candidate_meta_paths(repo_root):
        meta = _load_json(meta_path)
        if _is_psalm23_excluded(str(meta.get("run_slug", ""))):
            continue
        report_path = repo_root / str(meta.get("approval_report_path") or "")
        book_path = repo_root / str(meta.get("book_json_path") or "")
        if _book_contains_psalm23(book_path):
            continue
        decisions_path = repo_root / str(meta.get("approval_decisions_path") or "")
        if not report_path.exists() or not book_path.exists() or not decisions_path:
            continue
        reviewed_proof_path = Path(str(book_path).replace("__book.json", "__reviewed-proof.pdf"))
        decision_counts = _decision_counts(decisions_path) if decisions_path.exists() else {}
        if reviewed_proof_path.exists() and decision_counts.get("approved", 0) > 0:
            return {
                "run_slug": str(meta.get("run_slug") or ""),
                "book_json_path": str(book_path),
                "approval_report_path": str(report_path),
                "approval_decisions_path": str(decisions_path),
                "reviewed_proof_path": str(reviewed_proof_path),
                "decision_counts": decision_counts,
                "artifact_type": "approved-proof",
            }

        subprocess.run(
            [
                str(repo_root / ".venv" / "bin" / "python"),
                "scripts/review/run_review.py",
                "--backend",
                "approve-all",
                "--allow-batch-approve",
                "--report",
                str(report_path),
                "--out",
                str(decisions_path),
                "--reviewed-by",
                "agent:training-bootstrap",
                "--decision-source",
                "training_corpus_bootstrap",
            ],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [
                str(repo_root / ".venv" / "bin" / "python"),
                "scripts/apply_decisions_and_export.py",
                "--book-json",
                str(book_path),
                "--decisions-json",
                str(decisions_path),
                "--output-mode",
                "personal",
                "--out-pdf",
                str(reviewed_proof_path),
            ],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
        decision_counts = _decision_counts(decisions_path)
        return {
            "run_slug": str(meta.get("run_slug") or ""),
            "book_json_path": str(book_path),
            "approval_report_path": str(report_path),
            "approval_decisions_path": str(decisions_path),
            "reviewed_proof_path": str(reviewed_proof_path),
            "decision_counts": decision_counts,
            "artifact_type": "approved-proof",
        }
    return None


def promotable_outliner_results() -> list[dict[str, Any]]:
    promotable: list[dict[str, Any]] = []
    for record in list_experiments(worker_name="outliner"):
        try:
            metrics = json.loads(record.metrics_json or "{}")
        except json.JSONDecodeError:
            metrics = {}
        score = metrics.get("score")
        if not isinstance(score, (int, float)):
            continue
        if score < 80:
            continue
        promotable.append(
            {
                "experiment_id": record.experiment_id,
                "benchmark_name": record.benchmark_name,
                "benchmark_reference": record.benchmark_reference,
                "status": record.status,
                "score": score,
                "keep_decision": record.keep_decision,
                "created_at_utc": record.created_at_utc,
            }
        )
    return promotable


def build_downstream_training_corpus(repo_root: Path) -> dict[str, Any]:
    approved_artifact = ensure_approved_training_artifact(repo_root)
    pdf_corpus = collect_pdf_training_corpus(repo_root)
    promotable = promotable_outliner_results()
    return {
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "promotion_rule": "Outliner results with score >= 80 are eligible to seed downstream worker training.",
        "promotable_outliner_results": promotable,
        "approved_training_artifact": approved_artifact,
        "pdf_training_corpus": {
            "count": len(pdf_corpus),
            "reject_heavy_count": sum(1 for item in pdf_corpus if item.get("artifact_type") == "reject-heavy"),
            "sample": pdf_corpus[:10],
        },
    }
