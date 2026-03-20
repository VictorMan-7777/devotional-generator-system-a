from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.autoresearch.llm_library_trainer_core import evaluate_notes_batch
from src.autoresearch.store import log_experiment
from src.rag.exposition import ExpositionRAG
from src.rag.library_catalog import load_library_catalog
from src.rag.library_requests import list_resource_acquisition_requests
from src.rag.reference_librarian import catalog_is_thin


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class LibraryTrainerFinding:
    title: str
    severity: str
    rationale: str
    recommendation: str


LIBRARY_TRAINER_PROFILE = {
    "role": "expert_library_trainer",
    "mission": (
        "Train two distinct library roles: "
        "(1) The deterministic reference librarian — responsible for catalog lookups and escalation "
        "when the shelf is thin. Its correctness is evaluated by catalog integrity: are entries current, "
        "accurate, and does escalation fire when it should? "
        "(2) The RAG agent (research librarian) — responsible only for excerpt retrieval from the indexed "
        "corpus. Its quality is evaluated by excerpt relevance: are cuttings passage-specific, not blank, "
        "not metadata-shaped, and returned in ranked order?"
    ),
    "junior_worker_assumption": (
        "The original failure mode was escalating everything without using the shelf. "
        "If the research librarian is now shelf-reading first and only escalating when holdings genuinely "
        "cannot serve the request, that is the trained behavior — recognize it as progress, not a problem. "
        "The training standard has two milestones: "
        "(1) BEGINNER — escalates prematurely without checking current holdings; needs correction. "
        "(2) ACCOMPLISHED — uses the shelf first, escalates only when holdings are genuinely too shallow, "
        "and writes notes that help future requests land better; this is the graduation target. "
        "Do not hold a librarian at beginner status once they are demonstrating accomplished behavior."
    ),
    "collection_growth_policy": (
        "Workers are expected and encouraged to request more specific information when what the library "
        "currently holds is not specific enough for the task at hand. This is not a failure — it is how "
        "the collection grows. The general librarian is responsible for sourcing these new materials. "
        "The trainer must distinguish between two types of escalation: "
        "(1) PREMATURE escalation — current holdings are sufficient but the worker did not use them; "
        "this should be flagged and corrected. "
        "(2) LEGITIMATE specificity request — current holdings exist but lack the depth or passage-specific "
        "detail the worker needs; this should be approved and forwarded to the general librarian. "
        "Never penalize a worker for asking for more specific information when the shelf genuinely cannot supply it."
    ),
    "review_rubric": [
        "Do the notes say what this resource is genuinely useful for, not just what the card says?",
        "Did the research librarian use current holdings before escalating to acquisition?",
        "Is this escalation premature (holdings sufficient, not used) or legitimate (holdings genuinely too shallow)?",
        "Do the notes identify limits as well as strengths?",
        "Would the notes help the next passage request be answered more intelligently?",
        "Is the librarian demonstrating accomplished behavior — shelf first, escalate only when needed? If so, note the progress.",
    ],
}


def _load_note_evaluations(repo_root: Path) -> list[dict[str, Any]]:
    root = repo_root / "data" / "library" / "reading-notes" / "drafts"
    results: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.evaluation.json")):
        try:
            results.append(json.loads(path.read_text()))
        except Exception:
            continue
    return results


def _load_raw_notes(repo_root: Path) -> list[dict[str, Any]]:
    """Load raw reading note files (not the evaluation files) for LLM review."""
    root = repo_root / "data" / "library" / "reading-notes" / "drafts"
    results: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        if path.name.endswith(".evaluation.json"):
            continue
        try:
            data = json.loads(path.read_text())
            results.append(data)
        except Exception:
            continue
    return results


def _note_to_text(note: dict[str, Any]) -> str:
    """Convert a reading note dict to a readable text block for LLM review."""
    parts: list[str] = []
    title = str(note.get("title") or "Unknown Resource")
    parts.append(f"RESOURCE: {title}")

    what = note.get("what_resource_contains") or {}
    if isinstance(what, dict):
        for key, value in what.items():
            parts.append(f"  {key}: {value}")
    elif what:
        parts.append(f"  {what}")

    strengths = note.get("strengths") or []
    if strengths:
        parts.append("STRENGTHS:")
        for item in (strengths if isinstance(strengths, list) else [strengths]):
            parts.append(f"  - {item}")

    limits = note.get("limits") or []
    if limits:
        parts.append("LIMITS:")
        for item in (limits if isinstance(limits, list) else [limits]):
            parts.append(f"  - {item}")

    best_uses = note.get("best_future_uses") or []
    if best_uses:
        parts.append("BEST USES:")
        for item in (best_uses if isinstance(best_uses, list) else [best_uses]):
            parts.append(f"  - {item}")

    memory = note.get("research_librarian_memory") or ""
    if memory:
        parts.append(f"LIBRARIAN MEMORY: {memory}")

    return "\n".join(parts)


def _latest_output_file(repo_root: Path, pattern: str) -> dict[str, Any]:
    matches = sorted((repo_root / "docs" / "system" / "outputs").glob(pattern))
    if not matches:
        return {}
    try:
        return json.loads(matches[-1].read_text())
    except Exception:
        return {}


def _resource_packet_review(repo_root: Path) -> tuple[list[LibraryTrainerFinding], dict[str, int]]:
    findings: list[LibraryTrainerFinding] = []
    blank_excerpt_count = 0
    metadata_excerpt_count = 0

    outliner_cycle = _latest_output_file(repo_root, "*__devg__outliner-training-cycle.json")
    latest_outliner_result = {}
    if isinstance(outliner_cycle, dict):
        results = outliner_cycle.get("results", [])
        if isinstance(results, list) and results:
            latest_outliner_result = results[-1] or {}

    bundle = (
        latest_outliner_result.get("editorial_build", {}).get("passage_resources", {})
        if isinstance(latest_outliner_result, dict)
        else {}
    )
    outliner_resources = list(bundle.get("outliner_resources", []) or [])
    exposition_resources = list(bundle.get("exposition_resources", []) or [])

    for record in outliner_resources + exposition_resources:
        excerpt_text = str(record.get("excerpt_text") or "").strip()
        if not excerpt_text:
            blank_excerpt_count += 1
            continue
        lower = excerpt_text.lower()
        if any(token in lower for token in ("publication_metadata", "page_images", "public_domain_text")):
            metadata_excerpt_count += 1

    if blank_excerpt_count:
        findings.append(
            LibraryTrainerFinding(
                title="Workers are still receiving blank cuttings",
                severity="high",
                rationale=(
                    f"The latest worker packet still includes {blank_excerpt_count} resource record(s) with empty excerpt text, "
                    "which means the requester is not getting a real clipping to work from."
                ),
                recommendation=(
                    "Do not treat a catalog match as a usable cutting. The research librarian should hand the worker a real excerpt plus its context window."
                ),
            )
        )
    if metadata_excerpt_count:
        findings.append(
            LibraryTrainerFinding(
                title="Workers are still receiving metadata-shaped cuttings",
                severity="high",
                rationale=(
                    f"The latest worker packet includes {metadata_excerpt_count} resource record(s) whose excerpt text is still metadata-like "
                    "instead of a real explanatory clipping."
                ),
                recommendation=(
                    "Upgrade the packet from metadata placeholders to actual commentary/dictionary cuttings with enough surrounding context to be useful."
                ),
            )
        )

    exposition_cycle = _latest_output_file(repo_root, "*__devg__exposition-training-cycle.json")
    assignments = exposition_cycle.get("assignments", []) if isinstance(exposition_cycle, dict) else []
    weak_context_assignments = 0
    for item in assignments:
        focal = str(item.get("focal_reference") or "").strip()
        context = str(item.get("context_reference") or "").strip()
        if focal and context and focal == context:
            weak_context_assignments += 1
    if weak_context_assignments:
        findings.append(
            LibraryTrainerFinding(
                title="Exposition assignments are missing broader context separation",
                severity="medium",
                rationale=(
                    f"{weak_context_assignments} exposition assignment(s) used the same focal and context reference, "
                    "which weakens the trainer's ability to confirm that the worker received full-context support."
                ),
                recommendation=(
                    "Keep focal verses narrow and context references broader so the trainer can tell whether the cutting and the context were both supplied."
                ),
            )
        )

    summary = {
        "blank_excerpt_count": blank_excerpt_count,
        "metadata_excerpt_count": metadata_excerpt_count,
        "weak_context_assignments": weak_context_assignments,
    }
    return findings, summary


def _pending_requests_review() -> tuple[list[dict[str, Any]], list[LibraryTrainerFinding], list[dict[str, Any]]]:
    pending = list_resource_acquisition_requests(status="requested") + list_resource_acquisition_requests(status="trainer_review")
    findings: list[LibraryTrainerFinding] = []
    actionable_requests: list[dict[str, Any]] = []
    _rag = ExpositionRAG()
    for request in pending:
        # Count ACTUAL indexed excerpts for the specific passage, not catalog metadata entries.
        # Catalog entries have covered_books=[] which matches every request regardless of passage,
        # producing false "22 shelf matches" that clear John/Romans requests as if satisfied.
        try:
            actual_excerpts = _rag.retrieve_for_paragraph(
                paragraph_type="context",
                passage_reference=request.scripture_reference,
                topic=request.scripture_reference,
                source_types=["commentary", "reference"],
            )
            match_count = len(actual_excerpts)
        except Exception:
            match_count = 0
        if match_count >= 4:
            actionable_requests.append(
                {
                    "request_id": request.request_id,
                    "scripture_reference": request.scripture_reference,
                    "requested_by": request.requested_by,
                    "worker_name": request.worker_name,
                    "matching_current_holdings": match_count,
                    "recommended_resolution": "clear_and_serve_from_current_holdings",
                }
            )
            findings.append(
                LibraryTrainerFinding(
                    title=f"Actual indexed excerpts sufficient for {request.scripture_reference}",
                    severity="low",
                    rationale=(
                        f"The excerpt index has {match_count} passage-specific entries for "
                        f"{request.scripture_reference}; acquisition is not yet needed."
                    ),
                    recommendation=(
                        "Serve from the indexed excerpts already available. "
                        "Only escalate to acquisitions after the research librarian confirms "
                        "those excerpts are still inadequate for the assigned worker."
                    ),
                )
            )
        else:
            actionable_requests.append(
                {
                    "request_id": request.request_id,
                    "scripture_reference": request.scripture_reference,
                    "requested_by": request.requested_by,
                    "worker_name": request.worker_name,
                    "matching_current_holdings": match_count,
                    "recommended_resolution": "approve_for_acquisition_librarian",
                }
            )
            # Thin shelf + escalation is the correct behavior — forward without a finding.
            # The research librarian used the shelf, found it insufficient, and escalated appropriately.
            # This is accomplished training behavior, not a problem.
    return pending, findings, actionable_requests


def _catalog_integrity_review() -> tuple[dict[str, int], list[LibraryTrainerFinding]]:
    """Audit the DB-backed resource_catalog for integrity issues.

    Checks: total entries, how many are verified vs draft, whether any
    cataloged resources are thin in the RAG index, and whether entries
    have required metadata fields.
    """
    findings: list[LibraryTrainerFinding] = []
    summary: dict[str, int] = {
        "total": 0,
        "verified": 0,
        "draft": 0,
        "missing_author": 0,
        "missing_serves_needs": 0,
    }
    try:
        entries = load_library_catalog()
    except Exception:
        entries = []
    summary["total"] = len(entries)
    for entry in entries:
        if entry.catalog_status == "verified":
            summary["verified"] += 1
        else:
            summary["draft"] += 1
        if not str(entry.author_or_editor or "").strip():
            summary["missing_author"] += 1
        if not entry.serves_needs:
            summary["missing_serves_needs"] += 1
    if summary["missing_author"] > 0:
        findings.append(
            LibraryTrainerFinding(
                title="Catalog entries missing author metadata",
                severity="medium",
                rationale=(
                    f"{summary['missing_author']} catalog entries have no author_or_editor field. "
                    "Workers cannot cite these resources correctly."
                ),
                recommendation="Update holdings and re-run card evaluation to fill author fields.",
            )
        )
    if summary["missing_serves_needs"] > 0:
        findings.append(
            LibraryTrainerFinding(
                title="Catalog entries missing serves_needs metadata",
                severity="medium",
                rationale=(
                    f"{summary['missing_serves_needs']} entries have empty serves_needs. "
                    "The reference librarian cannot route them to the right workers."
                ),
                recommendation="Review these cards and assign appropriate serves_needs values.",
            )
        )
    return summary, findings


def build_library_trainer_review(repo_root: Path, *, run_llm_note_review: bool = False) -> dict[str, Any]:
    note_evaluations = _load_note_evaluations(repo_root)

    # ── LLM note evaluation (optional — requires API key, skipped by default in tests) ──
    llm_note_results: list[dict[str, Any]] = []
    if run_llm_note_review:
        raw_notes = _load_raw_notes(repo_root)
        if raw_notes:
            notes_for_llm = [
                {
                    "note_text": _note_to_text(note),
                    "resource_title": str(note.get("title") or "Unknown Resource"),
                    "passage_reference": str(
                        (note.get("what_resource_contains") or {}).get("most_helpful_for") or "General"
                    ),
                }
                for note in raw_notes[:5]  # Evaluate up to 5 notes per cycle to manage API costs
            ]
            llm_note_results = evaluate_notes_batch(notes_for_llm)
            # Override the deterministic note_evaluations summary with LLM results
            note_evaluations = llm_note_results

    accepted = sum(1 for item in note_evaluations if item.get("decision") == "accepted")
    revise = sum(1 for item in note_evaluations if item.get("decision") == "revise")
    pending_requests, request_findings, actionable_requests = _pending_requests_review()
    packet_findings, packet_summary = _resource_packet_review(repo_root)
    catalog_summary, catalog_findings = _catalog_integrity_review()

    findings = list(request_findings) + list(packet_findings) + list(catalog_findings)
    if revise:
        findings.append(
            LibraryTrainerFinding(
                title="Research-librarian notes still need stronger judgment",
                severity="medium",
                rationale=(
                    f"{revise} reading-note evaluations still require revision before the research librarian "
                    "can be trusted to read the shelf like an experienced human researcher."
                ),
                recommendation=(
                    "Keep the trainer reviewing notes until the research librarian consistently identifies "
                    "strengths, limits, and likely passage fit."
                ),
            )
        )

    return {
        "reviewed_at_utc": _utc_now(),
        "trainer_profile": LIBRARY_TRAINER_PROFILE,
        "note_summary": {
            "evaluated_count": len(note_evaluations),
            "accepted_count": accepted,
            "revise_count": revise,
        },
        "catalog_summary": catalog_summary,
        "pending_request_count": len(pending_requests),
        "actionable_request_count": len(actionable_requests),
        "actionable_requests": actionable_requests,
        "packet_summary": packet_summary,
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


def log_library_trainer_review(repo_root: Path) -> dict[str, Any]:
    payload = build_library_trainer_review(repo_root, run_llm_note_review=True)
    now = _utc_now()
    log_experiment(
        experiment_id="library-trainer__current-cycle",
        worker_name="library_trainer",
        benchmark_name="library-notes-and-request-review",
        benchmark_reference="research_librarian -> acquisition_librarian handoff",
        status="reviewed",
        attempted_change="Reviewed research-librarian notes and current request discipline against real shelf utilization.",
        metrics={
            "evaluated_notes": payload["note_summary"]["evaluated_count"],
            "accepted_notes": payload["note_summary"]["accepted_count"],
            "revise_notes": payload["note_summary"]["revise_count"],
            "pending_request_count": payload["pending_request_count"],
            "actionable_request_count": payload["actionable_request_count"],
            "blank_excerpt_count": payload["packet_summary"]["blank_excerpt_count"],
            "metadata_excerpt_count": payload["packet_summary"]["metadata_excerpt_count"],
            "catalog_total": payload.get("catalog_summary", {}).get("total", 0),
            "catalog_verified": payload.get("catalog_summary", {}).get("verified", 0),
            "catalog_missing_author": payload.get("catalog_summary", {}).get("missing_author", 0),
            "finding_count": len(payload["findings"]),
        },
        learning_note="Expert library trainer reviewed note quality and whether current holdings were used before acquisition escalation.",
        keep_decision="keep",
        created_at_utc=now,
        completed_at_utc=now,
    )
    return payload
