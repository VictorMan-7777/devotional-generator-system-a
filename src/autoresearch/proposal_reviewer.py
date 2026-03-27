"""proposal_reviewer.py — Aggregate and surface code-change proposals from trainer agents.

Each LLM trainer (outliner, exposition) can emit `proposed_code_changes` when it identifies
a structural code defect — something that cannot be fixed by more training cycles alone.

This module:
  1. Scans recent training cycle JSONs for `proposed_code_changes` entries.
  2. Groups proposals by (file_path, objective) similarity.
  3. Counts recurrence — a proposal appearing across N cycles is stronger evidence.
  4. Returns a prioritized list for human review before any code is touched.

Nothing in this module modifies code. It only reads and aggregates proposals.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_CYCLE_PATTERNS = [
    "*__devg__exposition-training-cycle.json",
    "*__devg__outliner-training-cycle.json",
]

# How many recent cycle files to scan per worker type.
_SCAN_LIMIT = 20


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalise_objective(obj: str) -> str:
    """Lowercase + strip punctuation for grouping similar proposals together."""
    return re.sub(r"[^a-z0-9 ]", "", obj.lower()).strip()


def _extract_proposals_from_file(path: Path) -> list[dict[str, Any]]:
    """Return all proposed_code_changes entries found anywhere in a cycle JSON."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []

    proposals: list[dict[str, Any]] = []
    cycle_time = data.get("generated_at_utc", path.stem[:16])

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            changes = node.get("proposed_code_changes")
            if isinstance(changes, list):
                for item in changes:
                    if isinstance(item, dict) and item.get("file_path") and item.get("objective"):
                        proposals.append({**item, "_cycle_file": path.name, "_cycle_time": cycle_time})
            for v in node.values():
                _walk(v)
        elif isinstance(node, list):
            for v in node:
                _walk(v)

    _walk(data)
    return proposals


def collect_recent_proposals(repo_root: Path, *, scan_limit: int = _SCAN_LIMIT) -> list[dict[str, Any]]:
    """Scan recent cycle files and return all raw proposals found."""
    output_dir = repo_root / "docs" / "system" / "outputs"
    all_proposals: list[dict[str, Any]] = []
    for pattern in _CYCLE_PATTERNS:
        files = sorted(output_dir.glob(pattern), reverse=True)[:scan_limit]
        for path in files:
            all_proposals.extend(_extract_proposals_from_file(path))
    return all_proposals


def _group_proposals(proposals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group proposals by (file_path, normalised_objective) and count recurrence."""
    groups: dict[tuple[str, str], dict[str, Any]] = {}

    for prop in proposals:
        file_path = str(prop.get("file_path", "")).strip()
        objective = str(prop.get("objective", "")).strip()
        key = (file_path, _normalise_objective(objective))

        if key not in groups:
            groups[key] = {
                "file_path": file_path,
                "objective": objective,
                "change_description": prop.get("change_description", ""),
                "rationale": prop.get("rationale", ""),
                "recurrence": 0,
                "first_seen": prop.get("_cycle_time", ""),
                "last_seen": prop.get("_cycle_time", ""),
                "seen_in_cycles": [],
            }
        g = groups[key]
        g["recurrence"] += 1
        g["seen_in_cycles"].append(prop.get("_cycle_file", ""))
        # Keep the most recent description/rationale
        if prop.get("_cycle_time", "") >= g["last_seen"]:
            g["last_seen"] = prop.get("_cycle_time", "")
            if prop.get("change_description"):
                g["change_description"] = prop["change_description"]
            if prop.get("rationale"):
                g["rationale"] = prop["rationale"]

    # Sort: highest recurrence first, then alphabetically by file
    ranked = sorted(groups.values(), key=lambda x: (-x["recurrence"], x["file_path"]))
    for i, item in enumerate(ranked, 1):
        item["rank"] = i
    return ranked


def build_proposal_review(repo_root: Path, *, scan_limit: int = _SCAN_LIMIT) -> dict[str, Any]:
    """Aggregate trainer proposals from recent cycles into a prioritised review package.

    Returns a dict ready to be JSON-serialised and written as a review file.
    """
    raw = collect_recent_proposals(repo_root, scan_limit=scan_limit)
    grouped = _group_proposals(raw)

    # Classify by confidence tier based on recurrence
    high = [p for p in grouped if p["recurrence"] >= 3]
    medium = [p for p in grouped if 1 < p["recurrence"] < 3]
    low = [p for p in grouped if p["recurrence"] == 1]

    return {
        "generated_at_utc": _utc_now(),
        "summary": (
            f"{len(grouped)} distinct proposal(s) from {len(raw)} raw mention(s) "
            f"across recent training cycles. "
            f"{len(high)} high-confidence (seen ≥3 cycles), "
            f"{len(medium)} medium, {len(low)} single-mention."
        ),
        "review_instructions": (
            "These proposals come from LLM trainers observing structural code defects "
            "across multiple training cycles. High-confidence proposals (recurrence ≥ 3) "
            "are candidates for immediate implementation. Single-mention proposals should "
            "be monitored for a few more cycles before acting. "
            "Nothing is implemented automatically — each change requires explicit approval."
        ),
        "proposals": grouped,
        "raw_mention_count": len(raw),
        "files_scanned": scan_limit * len(_CYCLE_PATTERNS),
    }
