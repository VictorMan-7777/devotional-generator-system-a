from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.api.full_run_assets import (
    build_agent_validation_report,
    build_approval_gate_report,
    build_pending_sections_and_previews,
    load_competition_outline_from_csv,
    load_run_input_from_csv,
)
from src.generation.generators import MockSectionGenerator
from src.interfaces.rag import QuoteCandidate
from src.models.devotional import DevotionalBook, DevotionalInput, OutputMode
from src.scripture.retrieval import ScriptureResult


def _book_two_days() -> DevotionalBook:
    gen = MockSectionGenerator()
    day1 = gen.generate_day("grace", 1)
    day2 = gen.generate_day("grace", 2)
    return DevotionalBook(
        id="book-1",
        input=DevotionalInput(topic="grace", num_days=2, output_mode=OutputMode.PUBLISH_READY),
        days=[day1, day2],
        series_id="series-1",
        volume_number=1,
    )


def test_load_run_input_from_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "input.csv"
    csv_path.write_text(
        "topic,num_days,series_id,volume_number,title\nGenesis 1-2,12,series-alpha,1,Genesis Foundations\n",
        encoding="utf-8",
    )
    row = load_run_input_from_csv(csv_path, row_number=1)
    assert row.topic == "Genesis 1-2"
    assert row.num_days == 12
    assert row.series_id == "series-alpha"
    assert row.volume_number == 1
    assert row.title == "Genesis Foundations"


def test_load_competition_outline_from_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "outline.csv"
    csv_path.write_text(
        "Day,Week,Attribute,Scripture,Theme/Focus,Notes,Status\n"
        "1,1,Holiness,1 Samuel 2:2,Theme: God's Uniqueness,first note,Planned\n"
        "2,1,Holiness,Isaiah 6:3,Theme: Transcendent Holiness,second note,Planned\n",
        encoding="utf-8",
    )
    run_input, plan = load_competition_outline_from_csv(csv_path, series_id="series-1", volume_number=1)
    assert run_input.num_days == 2
    assert run_input.title == "outline"
    assert plan[0].day_number == 1
    assert plan[0].scripture_reference == "1 Samuel 2:2"
    assert "Holiness" in plan[0].topic


def test_build_pending_sections_and_previews_contains_content() -> None:
    book = _book_two_days()
    pending, previews, meta = build_pending_sections_and_previews(book)
    assert "day 1 — timeless_wisdom" in pending
    assert "1:timeless_wisdom" in previews
    assert "The steadfast love of the Lord endures forever" in previews["1:timeless_wisdom"]
    assert "approval_status" in meta["1:timeless_wisdom"]


def test_build_pending_sections_excludes_agent_validated_by_default() -> None:
    book = _book_two_days()
    book.days[1].timeless_wisdom.verification_status = "agent_validated"
    book.days[1].scripture.verification_status = "agent_validated"

    pending, previews, meta = build_pending_sections_and_previews(book)
    assert "day 2 — timeless_wisdom" not in pending
    assert "day 2 — scripture" not in pending
    assert "2:timeless_wisdom" not in previews
    assert "2:scripture" not in meta


def test_build_pending_sections_can_include_agent_validated_when_requested() -> None:
    book = _book_two_days()
    book.days[1].timeless_wisdom.verification_status = "agent_validated"
    pending, _, _ = build_pending_sections_and_previews(book, include_agent_validated=True)
    assert "day 2 — timeless_wisdom" in pending


def test_timeless_wisdom_preview_marks_incomplete_turabian_footnote() -> None:
    book = _book_two_days()
    section = book.days[0].timeless_wisdom
    section.page_or_url = "https://monergism.com/example"
    section.citation_locator = ""
    section.publisher = ""
    section.publication_city = ""

    preview = build_pending_sections_and_previews(book)[1]["1:timeless_wisdom"]
    assert "Competition blocker (incomplete Turabian footnote):" in preview


def test_build_agent_validation_report(monkeypatch) -> None:
    book = _book_two_days()
    for day in book.days:
        day.timeless_wisdom.citation_locator = "p. 42"
        day.timeless_wisdom.publisher = "Baker Book House"
        day.timeless_wisdom.publication_city = "Grand Rapids, MI"
    class _FakeRetriever:
        def __init__(self, *args, **kwargs):
            pass
        def _parse_reference(self, reference: str):
            return reference
        def _try_bolls_life(self, parsed, translation: str = "NASB"):
            match = next((d for d in book.days if d.scripture.reference == parsed), book.days[0])
            return ScriptureResult(
                reference=parsed,
                text=match.scripture.text,
                translation=translation,
                retrieval_source="bolls_life",
                verification_status="verified",
            )
        def _try_api_bible(self, reference: str, translation: str = "NASB"):
            match = next((d for d in book.days if d.scripture.reference == reference), book.days[0])
            return ScriptureResult(
                reference=reference,
                text=match.scripture.text,
                translation=translation,
                retrieval_source="api_bible",
                verification_status="verified",
            )
        def retrieve(self, reference: str, translation: str = "NASB", operator_import=None):
            match = next((d for d in book.days if d.scripture.reference == reference), book.days[0])
            return ScriptureResult(
                reference=reference,
                text=match.scripture.text,
                translation=translation,
                retrieval_source="bolls_life",
                verification_status="verified",
            )

    class _FakeCatalog:
        def retrieve_quotes(self, topic: str, scripture_reference: str, author_weights=None, top_k: int = 25):
            out = []
            for day in book.days:
                out.append(
                        QuoteCandidate(
                            quote_text=day.timeless_wisdom.quote_text,
                            author=day.timeless_wisdom.author,
                            source_title=day.timeless_wisdom.source_title,
                            publication_year=day.timeless_wisdom.publication_year,
                            page_or_url=day.timeless_wisdom.page_or_url,
                            citation_locator=day.timeless_wisdom.citation_locator,
                            publisher=day.timeless_wisdom.publisher,
                            publication_city=day.timeless_wisdom.publication_city,
                            public_domain=day.timeless_wisdom.public_domain,
                        )
                    )
            return out

    monkeypatch.setattr("src.api.full_run_assets.ScriptureRetriever", _FakeRetriever)
    monkeypatch.setattr("src.api.full_run_assets.QuoteCatalog", _FakeCatalog)
    report = build_agent_validation_report(book, validator_agents=["agent:validator-1"])
    assert report["overall_passed"] is True
    assert report["overall_status"] == "passed"
    assert report["agents"][0]["agent"] == "agent:validator-1"
    assert report["agents"][0]["failed_checks"] == 0
    assert report["by_day"]["1"]["scripture"]["separate_source"] is True
    assert report["by_day"]["1"]["timeless_wisdom"]["separate_source"] is True


def test_agent_validation_report_treats_cross_source_nasb_1995_as_exact_text_match(monkeypatch) -> None:
    book = _book_two_days()
    book.days[0].scripture.retrieval_source = "api_bible"
    book.days[0].scripture.text = "Job’s Character and Wealth There was a man in the land of Uz."
    book.days[0].scripture.reference = "Job 1:1-2"

    class _FakeRetriever:
        def __init__(self, *args, **kwargs):
            pass

        def _parse_reference(self, reference: str):
            return reference

        def _try_bolls_life(self, parsed, translation: str = "NASB"):
            return ScriptureResult(
                reference=parsed,
                text="There was a man in the land of Uz.",
                translation=translation,
                retrieval_source="bolls_life",
                verification_status="verified",
            )

    class _FakeCatalog:
        def retrieve_quotes(self, topic: str, scripture_reference: str, author_weights=None, top_k: int = 25):
            out = []
            for day in book.days:
                out.append(
                    QuoteCandidate(
                        quote_text=day.timeless_wisdom.quote_text,
                        author=day.timeless_wisdom.author,
                        source_title=day.timeless_wisdom.source_title,
                        publication_year=day.timeless_wisdom.publication_year,
                        page_or_url=day.timeless_wisdom.page_or_url,
                        public_domain=day.timeless_wisdom.public_domain,
                    )
                )
            return out

    monkeypatch.setattr("src.api.full_run_assets.ScriptureRetriever", _FakeRetriever)
    monkeypatch.setattr("src.api.full_run_assets.QuoteCatalog", _FakeCatalog)
    monkeypatch.setenv("API_BIBLE_BIBLE_ID", "b8ee27bcd1cae43a-01")
    report = build_agent_validation_report(book, validator_agents=["agent:validator-1"])
    scripture = report["by_day"]["1"]["scripture"]
    assert scripture["status"] == "passed"
    assert scripture["comparison_mode"] == "exact_text"
    assert scripture["exact_text_compatible"] is True
    assert scripture["text_match"] is True
    assert scripture["discrepancy"] is False
    assert "SCRIPTURE_TEXT_DISCREPANCY" not in report["by_day"]["1"]["failed_check_ids"]
    assert "SCRIPTURE_TEXT_VARIANT" not in report["by_day"]["1"]["manual_review_flags"]


def test_agent_validation_report_fails_when_scripture_source_not_separate(monkeypatch) -> None:
    book = _book_two_days()
    book.days[0].scripture.retrieval_source = "unknown_source"
    class _FakeCatalog:
        def retrieve_quotes(self, topic: str, scripture_reference: str, author_weights=None, top_k: int = 25):
            out = []
            for day in book.days:
                out.append(
                    QuoteCandidate(
                        quote_text=day.timeless_wisdom.quote_text,
                        author=day.timeless_wisdom.author,
                        source_title=day.timeless_wisdom.source_title,
                        publication_year=day.timeless_wisdom.publication_year,
                        page_or_url=day.timeless_wisdom.page_or_url,
                        public_domain=day.timeless_wisdom.public_domain,
                    )
                )
            return out

    monkeypatch.setattr("src.api.full_run_assets.QuoteCatalog", _FakeCatalog)
    report = build_agent_validation_report(book, validator_agents=["agent:validator-1"])
    assert report["overall_passed"] is False
    assert "SCRIPTURE_VALIDATOR_SOURCE_NOT_SEPARATE" in report["by_day"]["1"]["failed_check_ids"]


def test_agent_validation_report_fails_when_scripture_validation_unresolved(monkeypatch) -> None:
    book = _book_two_days()
    book.days[0].scripture.retrieval_source = "bolls_life"
    monkeypatch.delenv("API_BIBLE_KEY", raising=False)
    monkeypatch.delenv("API_BIBLE_BIBLE_ID", raising=False)

    class _FakeCatalog:
        def retrieve_quotes(self, topic: str, scripture_reference: str, author_weights=None, top_k: int = 25):
            out = []
            for day in book.days:
                out.append(
                    QuoteCandidate(
                        quote_text=day.timeless_wisdom.quote_text,
                        author=day.timeless_wisdom.author,
                        source_title=day.timeless_wisdom.source_title,
                        publication_year=day.timeless_wisdom.publication_year,
                        page_or_url=day.timeless_wisdom.page_or_url,
                        public_domain=day.timeless_wisdom.public_domain,
                    )
                )
            return out

    monkeypatch.setattr("src.api.full_run_assets.QuoteCatalog", _FakeCatalog)
    report = build_agent_validation_report(book, validator_agents=["agent:validator-1"])
    assert report["overall_passed"] is False
    assert report["overall_status"] == "blocked_config"
    assert "SCRIPTURE_VALIDATOR_CONFIG_MISSING" in report["by_day"]["1"]["failed_check_ids"]
    assert report["blocking_issues"]
    assert report["by_day"]["1"]["scripture"]["status"] == "blocked_config"


def test_agent_validation_report_fails_when_scripture_validation_failed(monkeypatch) -> None:
    book = _book_two_days()
    book.days[0].scripture.retrieval_source = "api_bible"

    class _FakeRetriever:
        def __init__(self, *args, **kwargs):
            pass

        def _parse_reference(self, reference: str):
            return object()

        def _try_bolls_life(self, parsed, translation: str = "NASB"):
            return None

    class _FakeCatalog:
        def retrieve_quotes(self, topic: str, scripture_reference: str, author_weights=None, top_k: int = 25):
            out = []
            for day in book.days:
                out.append(
                    QuoteCandidate(
                        quote_text=day.timeless_wisdom.quote_text,
                        author=day.timeless_wisdom.author,
                        source_title=day.timeless_wisdom.source_title,
                        publication_year=day.timeless_wisdom.publication_year,
                        page_or_url=day.timeless_wisdom.page_or_url,
                        public_domain=day.timeless_wisdom.public_domain,
                    )
                )
            return out

    monkeypatch.setattr("src.api.full_run_assets.ScriptureRetriever", _FakeRetriever)
    monkeypatch.setattr("src.api.full_run_assets.QuoteCatalog", _FakeCatalog)
    report = build_agent_validation_report(book, validator_agents=["agent:validator-1"])
    assert report["overall_passed"] is False
    assert "SCRIPTURE_VALIDATION_FAILED" in report["by_day"]["1"]["failed_check_ids"]


def test_build_approval_gate_report_includes_source_book_and_previews(tmp_path: Path) -> None:
    book = _book_two_days()
    source_book = tmp_path / "book.json"
    source_book.write_text("{}", encoding="utf-8")
    report = build_approval_gate_report(book, source_book_json=source_book)
    assert report["source_book_json"] == str(source_book)
    assert report["pending_section_count"] > 0
    assert "1:timeless_wisdom" in report["section_previews_by_key"]
    assert datetime.fromisoformat(report["generated_at_utc"]).tzinfo == timezone.utc


def test_build_approval_gate_report_surfaces_agent_validated_sections(tmp_path: Path) -> None:
    """Cycle 1A regression test: agent_validated sections must appear in the pending queue.

    Previously, build_approval_gate_report called build_pending_sections_and_previews
    with include_agent_validated=False (the default), hiding those sections from the
    operator review queue while ExportGate still blocked them from export. This created
    an uncompletable workflow. The fix passes include_agent_validated=True.
    """
    book = _book_two_days()
    # Mark day 2 sections as agent_validated (not yet human-approved)
    book.days[1].timeless_wisdom.verification_status = "agent_validated"
    book.days[1].scripture.verification_status = "agent_validated"

    source_book = tmp_path / "book.json"
    source_book.write_text("{}", encoding="utf-8")
    report = build_approval_gate_report(book, source_book_json=source_book)

    pending = report["pending_sections"]
    # agent_validated sections must be visible in the report so operators can approve them
    assert "day 2 — timeless_wisdom" in pending, (
        "agent_validated section must appear in approval gate pending_sections"
    )
    assert "day 2 — scripture" in pending, (
        "agent_validated section must appear in approval gate pending_sections"
    )
    # ExportGate must still block publish-ready export (fail-closed contract)
    assert report["exportable"] is False
