from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any


LIBRARY_ROOT = Path(__file__).resolve().parents[2] / "data" / "library"
RESOURCES_ROOT = LIBRARY_ROOT / "resources"
CARDS_DRAFT_ROOT = LIBRARY_ROOT / "cards" / "drafts"
LIVE_CATALOG_PATH = LIBRARY_ROOT / "resource-catalog.json"


def _excerpt_count(title: str) -> int:
    """Return number of excerpt_catalog rows for this resource title."""
    try:
        from src.persistence.paths import default_registry_db_path
        db_path = default_registry_db_path()
        conn = sqlite3.connect(str(db_path))
        row = conn.execute(
            "SELECT COUNT(*) FROM excerpt_catalog WHERE source_title = ?", (title,)
        ).fetchone()
        conn.close()
        return int(row[0]) if row else 0
    except Exception:
        return -1  # unknown — don't block on DB error


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")


def _infer_resource_type(title: str) -> str:
    text = str(title or "").lower()
    if "dictionary" in text:
        return "dictionary"
    if "encyclopedia" in text:
        return "encyclopedia"
    if "commentary" in text or "exposition" in text:
        return "whole_bible_commentary"
    if "sermon" in text:
        return "sermon_collection"
    return "reference_work"


def _infer_scope(title: str, resource_type: str) -> str:
    text = str(title or "").lower()
    if resource_type in {"dictionary", "encyclopedia", "whole_bible_commentary"}:
        return "whole_bible"
    if "repentance" in text or "prayer" in text or "mortification" in text:
        return "topical"
    return "whole_bible"


def _infer_contains(holding: dict[str, Any]) -> list[str]:
    contains = ["publication_metadata"]
    if holding.get("local_asset_path"):
        contains.append("public_domain_text")
    if "archive.org/details/" in str(holding.get("selected_source_url", "")):
        contains.append("page_images")
    return contains


def _infer_serves_needs(title: str, resource_type: str, quote_ready: bool) -> list[str]:
    text = str(title or "").lower()
    needs: list[str] = []
    if resource_type in {"dictionary", "encyclopedia"}:
        needs.extend(["terms", "background"])
    elif resource_type == "whole_bible_commentary":
        needs.extend(["exposition", "background"])
    else:
        needs.append("quotes" if quote_ready else "background")
    if quote_ready:
        needs.extend(["quotes", "citation"])
    return sorted(dict.fromkeys(needs))


def _infer_supports_workers(resource_type: str, needs: list[str]) -> list[str]:
    workers = ["acquisition_librarian", "research_librarian"]
    if any(item in needs for item in ["quotes", "citation"]):
        workers.append("quote_selector")
    if resource_type in {"dictionary", "encyclopedia", "whole_bible_commentary"}:
        workers.extend(["exposition_writer", "exposition_retriever"])
    if resource_type == "whole_bible_commentary":
        workers.append("outliner")
    return sorted(dict.fromkeys(workers))


def build_draft_card_from_holding(holding_path: Path) -> dict[str, Any]:
    holding = _load_json(holding_path)
    title = str(holding.get("title") or "").strip()
    author = str(holding.get("author_or_editor") or "").strip()
    resource_type = _infer_resource_type(title)
    scope = _infer_scope(title, resource_type)
    citation = holding.get("citation_components") or {}
    quote_ready = bool(citation.get("quote_citation_ready"))
    contains = _infer_contains(holding)
    serves_needs = _infer_serves_needs(title, resource_type, quote_ready)
    supports_workers = _infer_supports_workers(resource_type, serves_needs)

    card = {
        "resource_id": f"res-{_slug(title)}",
        "title": title,
        "author_or_editor": author,
        "resource_type": resource_type,
        "scope": scope,
        "covered_books": [],
        "covered_topics": [],
        "supports_workers": supports_workers,
        "contains": contains,
        "serves_needs": serves_needs,
        "source_form": "local",
        "source_locator": str(holding_path),
        "citation_quality": "high" if quote_ready else "unknown",
        "approved_for_validator": False,
        "preferred_order": 100,
        "acquisition_status": "acquired",
        "catalog_status": "draft",
        "notes": (
            "Draft card created from acquired holding. Needs librarian inspection beyond metadata before live acceptance."
        ),
    }
    return card


def evaluate_draft_card(card: dict[str, Any], holding: dict[str, Any], holding_path: Path | None = None) -> dict[str, Any]:
    feedback: list[str] = []
    title = str(card.get("title") or "").strip()
    if title != str(holding.get("title") or "").strip():
        feedback.append("Card title does not match holding title.")
    if not str(card.get("author_or_editor") or "").strip():
        feedback.append("Author/editor is missing.")
    if not card.get("contains"):
        feedback.append("Card does not describe what the resource contains.")
    if not card.get("serves_needs"):
        feedback.append("Card does not describe what research needs the resource serves.")
    if "quote_selector" in card.get("supports_workers", []) and not (holding.get("citation_components") or {}).get("quote_citation_ready"):
        feedback.append("Card marks quote_selector support without full citation components.")
    selected_match_type = str(holding.get("selected_match_type") or "").strip()
    if selected_match_type == "weak":
        feedback.append("Acquisition match is weak and should not become a live card yet.")

    # Guard: card must not be accepted unless the resource has been indexed into excerpt_catalog.
    # A resource with source.txt but zero indexed rows means the RAG system cannot use it.
    if holding_path is not None:
        resource_dir = holding_path.parent
        has_source_txt = (resource_dir / "source.txt").exists()
    else:
        has_source_txt = bool(holding.get("local_asset_path"))
    if has_source_txt:
        excerpt_rows = _excerpt_count(title)
        if excerpt_rows == 0:
            feedback.append(
                "Resource has source.txt but no rows in excerpt_catalog — "
                "run index_source_texts.py before accepting this card."
            )

    decision = "accepted" if not feedback else "revise"
    return {
        "decision": decision,
        "feedback": feedback,
    }


def _upsert_card_to_db(card: dict[str, Any]) -> None:
    """Write an accepted card into the resource_catalog DB table."""
    try:
        from src.persistence.paths import default_registry_db_path
        db_path = default_registry_db_path()
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            """INSERT OR REPLACE INTO resource_catalog
               (resource_id, title, author_or_editor, resource_type, scope,
                covered_books, covered_topics, supports_workers, contains, serves_needs,
                source_form, source_locator, citation_quality, approved_for_validator,
                preferred_order, acquisition_status, catalog_status, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                str(card.get("resource_id") or "").strip(),
                str(card.get("title") or "").strip(),
                str(card.get("author_or_editor") or "").strip(),
                str(card.get("resource_type") or "reference_work").strip(),
                str(card.get("scope") or "whole_bible").strip(),
                json.dumps(card.get("covered_books") or []),
                json.dumps(card.get("covered_topics") or []),
                json.dumps(card.get("supports_workers") or []),
                json.dumps(card.get("contains") or []),
                json.dumps(card.get("serves_needs") or []),
                str(card.get("source_form") or "local").strip(),
                str(card.get("source_locator") or "").strip(),
                str(card.get("citation_quality") or "unknown").strip(),
                1 if card.get("approved_for_validator") else 0,
                int(card.get("preferred_order") or 100),
                str(card.get("acquisition_status") or "acquired").strip(),
                str(card.get("catalog_status") or "draft").strip(),
                str(card.get("notes") or "").strip(),
            ),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass  # DB write failure must not block card acceptance


def draft_and_evaluate_card(holding_path: Path) -> dict[str, Any]:
    holding = _load_json(holding_path)
    card = build_draft_card_from_holding(holding_path)
    slug = _slug(card["title"])
    card_path = CARDS_DRAFT_ROOT / f"{slug}.json"
    evaluation_path = CARDS_DRAFT_ROOT / f"{slug}.evaluation.json"
    _write_json(card_path, card)
    evaluation = evaluate_draft_card(card, holding, holding_path)
    _write_json(
        evaluation_path,
        {
            "holding_path": str(holding_path),
            "card_path": str(card_path),
            **evaluation,
        },
    )
    if evaluation["decision"] == "accepted":
        card["catalog_status"] = "verified"
        card["acquisition_status"] = "cataloged"
        # Write to DB (primary store)
        _upsert_card_to_db(card)
        # Keep JSON in sync as a read-only backup
        live_cards = _load_json(LIVE_CATALOG_PATH)
        existing = [row for row in live_cards if row.get("resource_id") != card["resource_id"]]
        existing.append(card)
        _write_json(LIVE_CATALOG_PATH, existing)
    return {
        "card_path": str(card_path),
        "evaluation_path": str(evaluation_path),
        **evaluation,
    }


def draft_and_evaluate_all_acquired_cards() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for holding_path in sorted(RESOURCES_ROOT.glob("*/holding.json")):
        holding = _load_json(holding_path)
        if str(holding.get("status") or "").strip() != "acquired":
            continue
        results.append(
            {
                "title": str(holding.get("title") or "").strip(),
                **draft_and_evaluate_card(holding_path),
            }
        )
    return results
