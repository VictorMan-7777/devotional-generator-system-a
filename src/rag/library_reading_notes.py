from __future__ import annotations

import json
from pathlib import Path
from typing import Any


LIBRARY_ROOT = Path(__file__).resolve().parents[2] / "data" / "library"
LIVE_CATALOG_PATH = LIBRARY_ROOT / "resource-catalog.json"
NOTES_DRAFT_ROOT = LIBRARY_ROOT / "reading-notes" / "drafts"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")


def _slug(text: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in text).strip("-").replace("--", "-")


def _resource_major_sections(card: dict[str, Any]) -> str:
    contains = card.get("contains") or []
    if not contains:
        return "Not yet determined from reading."
    return ", ".join(contains)


def _best_help(card: dict[str, Any]) -> str:
    needs = card.get("serves_needs") or []
    if not needs:
        return "unclear until further reading"
    return ", ".join(needs)


def build_reading_note(card: dict[str, Any]) -> dict[str, Any]:
    title = str(card.get("title") or "").strip()
    needs = card.get("serves_needs") or []
    workers = card.get("supports_workers") or []
    contains = card.get("contains") or []
    quote_ready = str(card.get("citation_quality") or "").strip().lower() == "high"
    note = {
        "title": title,
        "author_or_editor": str(card.get("author_or_editor") or "").strip(),
        "resource_type": str(card.get("resource_type") or "").strip(),
        "what_resource_contains": {
            "major_sections": _resource_major_sections(card),
            "toc_structurally_useful": "yes" if "section_outlines" in contains or "table_of_contents_outline" in contains else "limited",
            "introductions_useful": "yes" if "book_introduction" in contains else "unknown",
            "indexes_useful": "yes" if "term_articles" in contains or "background_articles" in contains else "unknown",
            "most_helpful_for": _best_help(card),
        },
        "strengths": [
            f"Best used for {', '.join(needs)}." if needs else "Needs more reading to determine primary strength.",
            "Holding is citation-ready for quote work." if quote_ready else "Not currently strong enough for competition-grade quote citation use.",
        ],
        "limits": [
            "Do not overstate quote usefulness unless citation components are complete." if not quote_ready else "Still verify locator-level quote accuracy at section selection time.",
            "Card-level metadata is not enough; use passage-level reading before heavy reliance.",
        ],
        "best_future_uses": {
            "likely_helpful_for": "Passages aligned with this resource family and its stated needs.",
            "workers_likely_to_benefit": workers,
        },
        "research_librarian_memory": (
            f"Remember {title} first for {', '.join(needs)}."
            if needs
            else f"Remember {title} as a shelf resource that still needs deeper reading."
        ),
    }
    return note


def evaluate_reading_note(note: dict[str, Any]) -> dict[str, Any]:
    feedback: list[str] = []
    if not str(note.get("research_librarian_memory") or "").strip():
        feedback.append("Need a stronger first-memory cue for future requests.")
    strengths = note.get("strengths") or []
    limits = note.get("limits") or []
    if not strengths:
        feedback.append("Strengths are missing.")
    if not limits:
        feedback.append("Limits are missing.")
    best_future = note.get("best_future_uses") or {}
    if not (best_future.get("workers_likely_to_benefit") or []):
        feedback.append("Future worker guidance is missing.")
    if "most_helpful_for" not in (note.get("what_resource_contains") or {}):
        feedback.append("The note does not say what the resource is really good for.")

    decision = "accepted" if not feedback else "revise"
    return {
        "decision": decision,
        "feedback": feedback,
    }


def draft_and_evaluate_reading_notes() -> list[dict[str, Any]]:
    cards = _load_json(LIVE_CATALOG_PATH)
    results: list[dict[str, Any]] = []
    for card in cards:
        title = str(card.get("title") or "").strip()
        slug = _slug(title)
        note = build_reading_note(card)
        note_path = NOTES_DRAFT_ROOT / f"{slug}.json"
        evaluation = evaluate_reading_note(note)
        evaluation_path = NOTES_DRAFT_ROOT / f"{slug}.evaluation.json"
        _write_json(note_path, note)
        _write_json(
            evaluation_path,
            {
                "title": title,
                "note_path": str(note_path),
                **evaluation,
            },
        )
        results.append(
            {
                "title": title,
                "note_path": str(note_path),
                "evaluation_path": str(evaluation_path),
                **evaluation,
            }
        )
    return results
