from __future__ import annotations

import json
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from src.models.artifacts import GroundingMap, GroundingMapEntry

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "review" / "run_review_studio.py"
_SPEC = spec_from_file_location("run_review_studio", _SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
run_review_studio = module_from_spec(_SPEC)
sys.modules[_SPEC.name] = run_review_studio
_SPEC.loader.exec_module(run_review_studio)


def _write_report(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "topic": "Genesis 1-2",
                "days": 2,
                "pending_sections": ["day 1 — title", "day 2 — exposition"],
                "section_previews_by_key": {"2:exposition": "Preview exposition text."},
            }
        ),
        encoding="utf-8",
    )


def test_studio_reject_advances_and_reduces_remaining(tmp_path: Path) -> None:
    report_path = tmp_path / "approval-gate-report.json"
    _write_report(report_path)
    state = run_review_studio.StudioState(
        report_path=report_path,
        output_path=tmp_path / "approval-decisions.json",
        edits_path=tmp_path / "review-edits.json",
        book_json_path=None,
        reviewed_by="Victor",
        decision_source=None,
        reset=True,
    )

    payload = state.apply_action("reject")
    assert payload["remaining_count"] == 1
    assert payload["current"]["day"] == 2
    assert payload["current"]["section"] == "exposition"
    assert payload["current"]["section_label"] == "Exposition"
    assert payload["current"]["source_preview"] == "Preview exposition text."


def test_studio_saves_edit_payload(tmp_path: Path) -> None:
    report_path = tmp_path / "approval-gate-report.json"
    _write_report(report_path)
    edits_path = tmp_path / "review-edits.json"
    state = run_review_studio.StudioState(
        report_path=report_path,
        output_path=tmp_path / "approval-decisions.json",
        edits_path=edits_path,
        book_json_path=None,
        reviewed_by="Victor",
        decision_source=None,
        reset=True,
    )

    state.save_edit(
        editor_html="<p>Human title draft</p>",
        editor_plain="Human title draft",
        note="Smoother language for reader tone.",
    )
    written = json.loads(edits_path.read_text(encoding="utf-8"))
    assert written["edits"][0]["day"] == 1
    assert written["edits"][0]["section"] == "title"
    assert written["edits"][0]["editor_plain"] == "Human title draft"
    assert written["edits"][0]["note"] == "Smoother language for reader tone."


def test_studio_save_edit_updates_book_json(tmp_path: Path) -> None:
    report_path = tmp_path / "approval-gate-report.json"
    report_path.write_text(
        json.dumps(
            {
                "topic": "Genesis 1-2",
                "days": 1,
                "pending_sections": ["day 1 — exposition"],
                "section_previews_by_key": {"1:exposition": "Old text"},
                "source_book_json": "book.json",
            }
        ),
        encoding="utf-8",
    )
    book_path = tmp_path / "book.json"
    book_path.write_text(
        json.dumps(
            {
                "days": [
                    {
                        "day_number": 1,
                        "exposition": {"text": "Old text", "word_count": 2, "grounding_map_id": "gm-1"}
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    state = run_review_studio.StudioState(
        report_path=report_path,
        output_path=tmp_path / "approval-decisions.json",
        edits_path=tmp_path / "review-edits.json",
        book_json_path=book_path,
        reviewed_by="Victor",
        decision_source=None,
        reset=True,
    )
    state.save_edit(
        editor_html="<p>Updated exposition content.</p>",
        editor_plain="Updated exposition content.",
        note="refresh wording",
    )
    updated_book = json.loads(book_path.read_text(encoding="utf-8"))
    assert updated_book["days"][0]["exposition"]["text"] == "Updated exposition content."


def test_studio_save_edit_persists_to_review_store(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("DEVG_SQLITE_PATH", str(tmp_path / "review.sqlite3"))
    report_path = tmp_path / "approval-gate-report.json"
    report_path.write_text(
        json.dumps(
            {
                "topic": "Genesis 1-2",
                "days": 1,
                "pending_sections": ["day 1 — exposition"],
                "section_previews_by_key": {"1:exposition": "Old text"},
                "source_book_json": "book.json",
            }
        ),
        encoding="utf-8",
    )
    book_path = tmp_path / "book.json"
    book_path.write_text(
        json.dumps(
            {
                "days": [
                    {
                        "day_number": 1,
                        "exposition": {"text": "Old text", "word_count": 2, "grounding_map_id": "gm-1"}
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    state = run_review_studio.StudioState(
        report_path=report_path,
        output_path=tmp_path / "approval-decisions.json",
        edits_path=tmp_path / "review-edits.json",
        book_json_path=book_path,
        reviewed_by="Victor",
        decision_source=None,
        reset=True,
    )
    state.save_edit(
        editor_html="<p>Updated exposition content.</p>",
        editor_plain="Updated exposition content.",
        note="refresh wording",
    )
    records = run_review_studio.load_review_edits_map(
        socket=state.review_socket,
        run_slug=state.run_slug,
    )
    assert records["1:exposition"]["editor_plain"] == "Updated exposition content."


def test_studio_html_has_dark_mode_and_wysiwyg() -> None:
    html = run_review_studio._html_page()
    assert "prefers-color-scheme: dark" in html
    assert "contenteditable=\"true\"" in html
    assert "id=\"filter\"" in html
    assert "id=\"jump\"" in html
    assert "id=\"audit\"" in html


def test_studio_section_preview_from_book() -> None:
    preview = run_review_studio._section_preview_from_book(
        {
            "days": [
                {
                    "day_number": 1,
                    "scripture": {
                        "reference": "John 3:16",
                        "text": "For God so loved the world...",
                        "translation": "NASB",
                    }
                }
            ]
        },
        day=1,
        section="scripture",
    )
    assert "John 3:16" in preview
    assert "For God so loved the world..." in preview
    assert "NASB" not in preview


def test_studio_timeless_wisdom_preview_contains_turabian_label() -> None:
    preview = run_review_studio._section_preview_from_book(
        {
            "days": [
                {
                    "day_number": 1,
                    "timeless_wisdom": {
                        "quote_text": "Sample quote",
                        "author": "Author Name",
                        "source_title": "Source Title",
                        "publication_year": 1901,
                        "page_or_url": "p. 42",
                        "citation_locator": "p. 42",
                        "publisher": "Publisher",
                        "publication_city": "Chicago",
                    },
                }
            ]
        },
        day=1,
        section="timeless_wisdom",
    )
    assert "Turabian Footnote:" in preview
    assert "- Author Name, Source Title" in preview


def test_studio_timeless_wisdom_preview_omits_raw_url_from_footnote() -> None:
    preview = run_review_studio._section_preview_from_book(
        {
            "days": [
                {
                    "day_number": 1,
                    "timeless_wisdom": {
                        "quote_text": "Sample quote",
                        "author": "Author Name",
                        "source_title": "Source Title",
                        "publication_year": 1901,
                        "page_or_url": "https://archive.org/example",
                    },
                }
            ]
        },
        day=1,
        section="timeless_wisdom",
    )
    assert "archive.org" not in preview


def test_studio_timeless_wisdom_preview_marks_incomplete_turabian_footnote() -> None:
    preview = run_review_studio._section_preview_from_book(
        {
            "days": [
                {
                    "day_number": 1,
                    "timeless_wisdom": {
                        "quote_text": "Sample quote",
                        "author": "Author Name",
                        "source_title": "Source Title",
                        "publication_year": 1901,
                        "page_or_url": "https://archive.org/example",
                    },
                }
            ]
        },
        day=1,
        section="timeless_wisdom",
    )
    assert "Competition blocker (incomplete Turabian footnote):" in preview


def test_studio_timeless_wisdom_preview_shows_original_when_language_modernized() -> None:
    preview = run_review_studio._section_preview_from_book(
        {
            "days": [
                {
                    "day_number": 1,
                    "timeless_wisdom": {
                        "quote_text": "Give you rest",
                        "original_quote_text": "Give thee rest",
                        "language_modernized": True,
                        "modernization_label": "Language modernized by AI",
                        "author": "Author Name",
                        "source_title": "Source Title",
                        "publication_year": 1901,
                        "page_or_url": "p. 42",
                        "citation_locator": "p. 42",
                        "publisher": "Publisher",
                        "publication_city": "Chicago",
                    },
                }
            ]
        },
        day=1,
        section="timeless_wisdom",
    )
    assert "Original wording:" in preview
    assert "Give thee rest" in preview
    assert "Language modernized by AI" in preview


def test_exposition_grounding_evidence_from_store(tmp_path: Path, monkeypatch) -> None:
    gm_root = tmp_path / "grounding"
    monkeypatch.setattr(run_review_studio.GroundingMapStore, "DEFAULT_ROOT", gm_root)
    store = run_review_studio.GroundingMapStore(root_dir=gm_root)
    gm = GroundingMap(
        id="gm-1",
        exposition_id="expo-1",
        entries=[
            GroundingMapEntry(
                paragraph_number=1,
                paragraph_name="declaration",
                sources_retrieved=["src_1 | Commentary"],
                excerpts_used=["created with intention and order"],
                original_excerpts_used=["created with intention and order"],
                excerpts_modernized=[False],
                how_retrieval_informed_paragraph="Sets theological frame.",
            ),
            GroundingMapEntry(
                paragraph_number=2,
                paragraph_name="context",
                sources_retrieved=["src_2 | Dictionary"],
                excerpts_used=["you will find rest in the promise"],
                original_excerpts_used=["thou wilt find rest in the promise"],
                excerpts_modernized=[True],
                modernization_label="Language modernized by AI",
                how_retrieval_informed_paragraph="Anchors practical implication.",
            ),
            GroundingMapEntry(
                paragraph_number=3,
                paragraph_name="theological",
                sources_retrieved=["src_3 | Commentary"],
                excerpts_used=["obedience in grace"],
                original_excerpts_used=["obedience in grace"],
                excerpts_modernized=[False],
                how_retrieval_informed_paragraph="Clarifies doctrine.",
            ),
            GroundingMapEntry(
                paragraph_number=4,
                paragraph_name="bridge",
                sources_retrieved=["src_4 | Commentary"],
                excerpts_used=["daily conduct aligns"],
                original_excerpts_used=["daily conduct aligns"],
                excerpts_modernized=[False],
                how_retrieval_informed_paragraph="Connects to application.",
            ),
        ],
    )
    store.save(gm)

    evidence = run_review_studio._exposition_grounding_evidence(
        {
            "days": [
                {
                    "day_number": 1,
                    "exposition": {
                        "grounding_map_id": "gm-1",
                        "text": "God creates with intention and order, inviting trust rather than anxiety.",
                    },
                }
            ]
        },
        day=1,
    )
    assert len(evidence) == 4
    assert evidence[0]["source_titles"][0] == "src_1 | Commentary"
    assert evidence[1]["excerpts_modernized"] == [True]
    assert evidence[1]["original_excerpts_used"] == ["thou wilt find rest in the promise"]


def test_studio_filter_and_jump(tmp_path: Path) -> None:
    report_path = tmp_path / "approval-gate-report.json"
    _write_report(report_path)
    state = run_review_studio.StudioState(
        report_path=report_path,
        output_path=tmp_path / "approval-decisions.json",
        edits_path=tmp_path / "review-edits.json",
        book_json_path=None,
        reviewed_by="Victor",
        decision_source=None,
        reset=True,
    )

    state.apply_action("approve")
    payload = state.set_filter("approved")
    assert payload["filter_mode"] == "approved"
    assert payload["filter_count"] == 1
    assert payload["current"]["day"] == 1
    assert payload["current"]["section"] == "title"

    state.set_filter("all")
    payload = state.jump_to("2:exposition")
    assert payload["current"]["day"] == 2
    assert payload["current"]["section"] == "exposition"


def test_resolve_report_relative_prefers_existing_repo_relative(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "repo"
    report_dir = root / "outputs" / "devotionals"
    report_dir.mkdir(parents=True)
    report_path = report_dir / "sample__approval-gate-report.json"
    report_path.write_text("{}", encoding="utf-8")

    book_path = root / "outputs" / "devotionals" / "sample__book.json"
    book_path.write_text("{}", encoding="utf-8")

    monkeypatch.chdir(root)
    resolved = run_review_studio._resolve_report_relative(
        "outputs/devotionals/sample__book.json",
        report_path,
    )
    assert resolved == Path("outputs/devotionals/sample__book.json")
