"""Tests for src/generation/real_section_generator.py — Phase 011 CP1.

Proves the end-to-end artifact lifecycle:
  generator → save → orchestrator auto-resolves → validation runs → audit passes

Required behaviours:
  A. Generator creates and saves a GroundingMap with exactly 4 entries.
  B. validate_daily_devotional() auto-resolves the saved artifact and
     EXPOSITION_GROUNDING_MAP check is present and passes.
  C. audit_devotionals() reports grounding_status="pass" and
     prayer_trace_status="pass".
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.audit.artifact_audit import audit_devotionals
from src.interfaces.rag import QuoteCandidate, RetrievedExcerpt
from src.generation.real_section_generator import DeterministicRealSectionGenerator, _build_prayer
from src.grounding_store.store import GroundingMapStore
from src.models.pipeline import PassageResourceBundle, PassageResourceRecord
from src.prayer_trace_store.store import PrayerTraceMapStore
from src.scripture.retrieval import ScriptureResult
from src.validation.orchestrator import validate_daily_devotional


# ---------------------------------------------------------------------------
# Shared fixture: redirect GroundingMapStore to tmp_path for all tests.
# ---------------------------------------------------------------------------


@pytest.fixture()
def gen_with_store(tmp_path: Path, monkeypatch):
    """Return (generator, store) with DEFAULT_ROOT redirected to tmp_path."""
    gm_dir = tmp_path / "gm"
    ptm_dir = tmp_path / "ptm"
    monkeypatch.setattr(GroundingMapStore, "DEFAULT_ROOT", gm_dir)
    monkeypatch.setattr(PrayerTraceMapStore, "DEFAULT_ROOT", ptm_dir)
    gen = DeterministicRealSectionGenerator()
    store = GroundingMapStore(gm_dir)
    ptm_store = PrayerTraceMapStore(ptm_dir)
    return gen, store, ptm_store


# ---------------------------------------------------------------------------
# Test A — Artifact creation and persistence
# ---------------------------------------------------------------------------


class TestArtifactCreated:
    def test_requires_scripture_reference(self, gen_with_store):
        gen, _store, _ptm_store = gen_with_store
        with pytest.raises(RuntimeError):
            gen.generate_day("grace", 1)

    def test_creates_and_saves_grounding_map(self, gen_with_store):
        gen, store, _ptm_store = gen_with_store
        day = gen.generate_day("grace", 1, scripture_reference="Romans 8:15")

        gm_id = day.exposition.grounding_map_id
        assert gm_id, "grounding_map_id must be truthy"
        assert store.exists(gm_id), "GroundingMap must be persisted in store"

    def test_grounding_map_has_four_entries(self, gen_with_store):
        gen, store, _ptm_store = gen_with_store
        day = gen.generate_day("grace", 1, scripture_reference="Romans 8:15")

        gm = store.load(day.exposition.grounding_map_id)
        assert len(gm.entries) == 4

    def test_grounding_map_uses_multiple_sources(self, gen_with_store):
        gen, store, _ptm_store = gen_with_store
        day = gen.generate_day("grace", 1, scripture_reference="Romans 8:15")
        gm = store.load(day.exposition.grounding_map_id)
        sources = set()
        for entry in gm.entries:
            sources.update(entry.sources_retrieved)
        assert len(sources) >= 2

    def test_grounding_map_id_is_deterministic(self, gen_with_store):
        gen, store, _ptm_store = gen_with_store
        day1 = gen.generate_day("grace", 1, scripture_reference="Romans 8:15")
        day2 = gen.generate_day("grace", 1, scripture_reference="Romans 8:15")
        assert day1.exposition.grounding_map_id == day2.exposition.grounding_map_id

    def test_different_inputs_produce_different_ids(self, gen_with_store):
        gen, store, _ptm_store = gen_with_store
        day1 = gen.generate_day("grace", 1, scripture_reference="Romans 8:15")
        day2 = gen.generate_day("grace", 2, scripture_reference="Romans 8:15")
        assert day1.exposition.grounding_map_id != day2.exposition.grounding_map_id

    def test_quote_selection_balances_authors_when_catalog_allows(self, gen_with_store):
        gen, _store, _ptm_store = gen_with_store
        candidates = [
            QuoteCandidate(
                quote_text="Grace steadies the heart under pressure.",
                author="Author One",
                source_title="Source One",
                publication_year=1900,
                page_or_url="p. 1",
                citation_locator="p. 1",
                publisher="Publisher One",
                publication_city="London",
                public_domain=True,
                relevance_score=1.0,
                citation_completeness=5,
            ),
            QuoteCandidate(
                quote_text="Mercy teaches the soul to rest in God.",
                author="Author Two",
                source_title="Source Two",
                publication_year=1901,
                page_or_url="p. 2",
                citation_locator="p. 2",
                publisher="Publisher Two",
                publication_city="Chicago",
                public_domain=True,
                relevance_score=0.9,
                citation_completeness=5,
            ),
        ]
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "src.generation.real_section_generator.QuoteCatalog.retrieve_quotes",
                lambda self, topic, scripture_reference, author_weights=None, top_k=50: candidates,
            )
            mp.setattr(
                "src.generation.real_section_generator.load_quote_candidates",
                lambda db_path, topic, scripture_reference, limit=50: [],
            )
            authors = []
            for day_num in range(1, 7):
                day = gen.generate_day("grace", day_num, scripture_reference="Romans 8:15")
                authors.append(day.timeless_wisdom.author)
        assert len(set(authors)) >= 2

    def test_quote_selection_respects_forbidden_quote_texts(self, gen_with_store):
        gen, _store, _ptm_store = gen_with_store
        candidates = [
            QuoteCandidate(
                quote_text="Grace steadies the heart under pressure.",
                author="Author One",
                source_title="Source One",
                publication_year=1900,
                page_or_url="p. 1",
                citation_locator="p. 1",
                publisher="Publisher One",
                publication_city="London",
                public_domain=True,
                relevance_score=1.0,
                citation_completeness=5,
            ),
            QuoteCandidate(
                quote_text="Mercy teaches the soul to rest in God.",
                author="Author Two",
                source_title="Source Two",
                publication_year=1901,
                page_or_url="p. 2",
                citation_locator="p. 2",
                publisher="Publisher Two",
                publication_city="Chicago",
                public_domain=True,
                relevance_score=0.9,
                citation_completeness=5,
            ),
        ]
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "src.generation.real_section_generator.QuoteCatalog.retrieve_quotes",
                lambda self, topic, scripture_reference, author_weights=None, top_k=50: candidates,
            )
            mp.setattr(
                "src.generation.real_section_generator.load_quote_candidates",
                lambda db_path, topic, scripture_reference, limit=50: [],
            )
            day1 = gen.generate_day("grace", 1, scripture_reference="Romans 8:15")
            day2 = gen.generate_day(
                "grace",
                2,
                scripture_reference="Romans 8:15",
                forbidden_quote_texts={day1.timeless_wisdom.quote_text},
            )
        assert day2.timeless_wisdom.quote_text != day1.timeless_wisdom.quote_text

    def test_uses_research_librarian_resources_when_live_retrieval_is_empty(self, gen_with_store):
        gen, store, _ptm_store = gen_with_store
        passage_resources = PassageResourceBundle(
            topic="Romans 8",
            scripture_reference="Romans 8:15",
            prepared_at_utc="2026-03-14T00:00:00Z",
            exposition_resources=[
                PassageResourceRecord(
                    purpose="context",
                    role_targets=["outliner", "exposition_writer"],
                    source_title="Library Context",
                    author="Research Librarian",
                    source_type="commentary",
                    excerpt_text="Romans 8 places adoption in the setting of Spirit-given assurance rather than fear.",
                    relevance_score=0.9,
                ),
                PassageResourceRecord(
                    purpose="theological",
                    role_targets=["outliner", "exposition_writer"],
                    source_title="Library Theology",
                    author="Research Librarian",
                    source_type="commentary",
                    excerpt_text="Adoption language in Romans 8 teaches assurance grounded in God's action, not human merit.",
                    relevance_score=0.95,
                ),
            ],
        )
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "src.generation.real_section_generator.ExpositionRAG.retrieve_for_paragraph",
                lambda self, paragraph_type, passage_reference, topic, source_types: [],
            )
            mp.setattr(
                "src.generation.real_section_generator.load_exposition_candidates",
                lambda db_path, paragraph_type, topic, passage_reference, limit=100: [],
            )
            day = gen.generate_day(
                "Romans 8",
                1,
                scripture_reference="Romans 8:15",
                passage_resources=passage_resources,
            )

        gm = store.load(day.exposition.grounding_map_id)
        sources = set()
        for entry in gm.entries:
            sources.update(entry.sources_retrieved)
        assert "Library Context" in sources
        assert "Library Theology" in sources

    def test_quote_selection_stops_after_first_strong_source_and_preserves_validator_headroom(self, gen_with_store):
        gen, _store, _ptm_store = gen_with_store
        variants = [
            QuoteCandidate(
                quote_text="Mercy teaches the soul to rest in God.",
                author="Author Two",
                source_title="Source Two",
                publication_year=1901,
                page_or_url="https://archive.org/details/work/page/2",
                citation_locator="p. 2",
                source_url="https://archive.org/details/work/page/2",
                publisher="Publisher Two",
                publication_city="Chicago",
                public_domain=True,
                relevance_score=0.9,
                citation_completeness=5,
            ),
            QuoteCandidate(
                quote_text="Mercy teaches the soul to rest in God.",
                author="Author Two",
                source_title="Source Two",
                publication_year=1901,
                page_or_url="https://ccel.org/work/source-two",
                source_url="https://ccel.org/work/source-two",
                public_domain=True,
                relevance_score=0.8,
                citation_completeness=1,
            ),
        ]
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "src.generation.real_section_generator.QuoteCatalog.retrieve_quotes",
                lambda self, topic, scripture_reference, author_weights=None, top_k=50: variants,
            )
            mp.setattr(
                "src.generation.real_section_generator.load_quote_candidates",
                lambda db_path, topic, scripture_reference, limit=50: [],
            )
            mp.setattr(
                "src.generation.real_section_generator.load_quote_source_rankings",
                lambda db_path: {"archive.org": 1.0, "ccel.org": 0.1},
            )
            day = gen.generate_day("grace", 1, scripture_reference="Romans 8:15")
        assert day.timeless_wisdom.source_trace == ["https://archive.org/details/work/page/2"]
        assert "ccel.org" not in " ".join(day.timeless_wisdom.source_trace)

    def test_quote_selection_does_not_reuse_forbidden_quote_when_pool_is_exhausted(self, gen_with_store, monkeypatch):
        gen, _store, _ptm_store = gen_with_store
        only_quote = QuoteCandidate(
            quote_text="Grace steadies the heart under pressure.",
            author="Only Author",
            source_title="Only Source",
            publication_year=1900,
            page_or_url="p. 1",
            citation_locator="p. 1",
            publisher="Publisher",
            publication_city="London",
            public_domain=True,
            relevance_score=1.0,
            citation_completeness=5,
        )
        monkeypatch.setattr(
            "src.generation.real_section_generator.QuoteCatalog.retrieve_quotes",
            lambda self, topic, scripture_reference, author_weights=None, top_k=50: [only_quote],
        )
        monkeypatch.setattr(
            "src.generation.real_section_generator.load_quote_candidates",
            lambda db_path, topic, scripture_reference, limit=50: [],
        )

        day = gen.generate_day(
            "grace",
            2,
            scripture_reference="Romans 8:15",
            forbidden_quote_texts={only_quote.quote_text},
        )

        assert day.timeless_wisdom.quote_text != only_quote.quote_text

    def test_non_genesis_passage_does_not_emit_genesis_shaped_exposition(self, gen_with_store):
        gen, _store, _ptm_store = gen_with_store
        day = gen.generate_day("judgment", 1, scripture_reference="Romans 2:1-5")
        text = day.exposition.text
        assert "Genesis instead binds meaning" not in text
        assert "Creation does not unfold as accident or chaos" not in text
        assert "Light is named good" not in text

    def test_matthew_generation_uses_specific_passage_language_and_scripture_grounding(self, tmp_path, monkeypatch):
        gm_dir = tmp_path / "gm"
        ptm_dir = tmp_path / "ptm"
        monkeypatch.setattr(GroundingMapStore, "DEFAULT_ROOT", gm_dir)
        monkeypatch.setattr(PrayerTraceMapStore, "DEFAULT_ROOT", ptm_dir)

        class StubRetriever:
            def retrieve(self, reference, translation, operator_import=None):
                return ScriptureResult(
                    reference="Matthew 26:5-9",
                    text=(
                        "But they were saying, 'Not during the festival, otherwise a riot might occur among the people.' "
                        "Now when Jesus was in Bethany, at the home of Simon the leper, a woman came to Him "
                        "with an alabaster vial of very costly perfume."
                    ),
                    translation="NASB",
                    retrieval_source="operator_import",
                    verification_status="catalog_verified",
                )

        gen = DeterministicRealSectionGenerator(retriever=StubRetriever())
        day = gen.generate_day("Matthew 26-28", 1, scripture_reference="Matthew 26:5-9")

        assert "matthew 26-28" not in day.exposition.text.lower()
        assert "Matthew 26:5-9 opens with a scene marked by costly devotion." in day.exposition.text
        assert "Read the scene of costly devotion slowly" in "\n".join(day.be_still.prompts)
        assert "Matthew 26:5-9 calls for concrete obedience" in day.action_steps.connector_phrase
        assert "In this passage You bring costly devotion into the open" in day.prayer.text

        gm = GroundingMapStore(root_dir=gm_dir).load(day.exposition.grounding_map_id)
        sources = {
            source
            for entry in gm.entries
            for source in entry.sources_retrieved
            if source.strip()
        }
        assert all("Genesis" not in source for source in sources)
        assert len(sources) >= 2

    def test_scripture_fallback_supports_grounding_when_exposition_catalog_is_thin(self, tmp_path, monkeypatch):
        gm_dir = tmp_path / "gm"
        ptm_dir = tmp_path / "ptm"
        monkeypatch.setattr(GroundingMapStore, "DEFAULT_ROOT", gm_dir)
        monkeypatch.setattr(PrayerTraceMapStore, "DEFAULT_ROOT", ptm_dir)
        monkeypatch.setenv("DEVG_DB_PATH", str(tmp_path / "devg.sqlite3"))

        class StubRetriever:
            def retrieve(self, reference, translation, operator_import=None):
                return ScriptureResult(
                    reference="Job 1:1-2",
                    text="There was a man in the land of Uz whose name was Job; and that man was blameless, upright, fearing God and turning away from evil.",
                    translation="NASB",
                    retrieval_source="api_bible",
                    verification_status="catalog_verified",
                )

        monkeypatch.setattr(
            "src.generation.real_section_generator.ExpositionRAG.retrieve_for_paragraph",
            lambda self, paragraph_type, passage_reference, topic, source_types: [],
        )
        monkeypatch.setattr(
            "src.generation.real_section_generator.QuoteCatalog.retrieve_quotes",
            lambda self, topic, scripture_reference, author_weights=None, top_k=50: [
                QuoteCandidate(
                    quote_text="Suffering tests whether integrity still bows before God.",
                    author="Author One",
                    source_title="Source One",
                    publication_year=1900,
                    page_or_url="p. 14",
                    public_domain=True,
                    relevance_score=0.9,
                    citation_completeness=3,
                ),
                QuoteCandidate(
                    quote_text="Steadfast faith speaks truth before easy relief.",
                    author="Author Two",
                    source_title="Source Two",
                    publication_year=1901,
                    page_or_url="p. 28",
                    public_domain=True,
                    relevance_score=0.8,
                    citation_completeness=3,
                ),
            ],
        )

        gen = DeterministicRealSectionGenerator(retriever=StubRetriever())
        day = gen.generate_day("Job 1-3", 1, scripture_reference="Job 1:1-2")
        gm = GroundingMapStore(root_dir=gm_dir).load(day.exposition.grounding_map_id)
        sources = {
            source
            for entry in gm.entries
            for source in entry.sources_retrieved
            if source.strip()
        }
        assert {"Scripture (Job 1:1-2)"} <= sources

    def test_broader_context_search_backfills_empty_theological_pool(self, tmp_path, monkeypatch):
        gm_dir = tmp_path / "gm"
        ptm_dir = tmp_path / "ptm"
        monkeypatch.setattr(GroundingMapStore, "DEFAULT_ROOT", gm_dir)
        monkeypatch.setattr(PrayerTraceMapStore, "DEFAULT_ROOT", ptm_dir)
        monkeypatch.setenv("DEVG_DB_PATH", str(tmp_path / "devg.sqlite3"))

        class StubRetriever:
            def retrieve(self, reference, translation, operator_import=None):
                return ScriptureResult(
                    reference="Job 1:21-22",
                    text="The Lord gave and the Lord has taken away. Blessed be the name of the Lord.",
                    translation="NASB",
                    retrieval_source="api_bible",
                    verification_status="catalog_verified",
                )

        def _retrieve(self, paragraph_type, passage_reference, topic, source_types):
            if paragraph_type == "context":
                return [
                    RetrievedExcerpt(
                        text="Job blesses God in the first wave of grief.",
                        source_title="Context Source",
                        author="Context Author",
                        source_type="commentary",
                        relevance_score=0.9,
                    )
                ]
            if paragraph_type == "theological" and topic == "steadfast integrity in suffering":
                return [
                    RetrievedExcerpt(
                        text="Job's confession keeps reverence alive under severe providence.",
                        source_title="Theological Source",
                        author="Theological Author",
                        source_type="commentary",
                        relevance_score=0.8,
                    )
                ]
            return []

        monkeypatch.setattr(
            "src.generation.real_section_generator.ExpositionRAG.retrieve_for_paragraph",
            _retrieve,
        )
        gen = DeterministicRealSectionGenerator(retriever=StubRetriever())
        day = gen.generate_day("Job 1-2", 8, scripture_reference="Job 1:21-22")
        gm = GroundingMapStore(root_dir=gm_dir).load(day.exposition.grounding_map_id)
        para3_sources = set(gm.entries[2].sources_retrieved)
        assert "Scripture (Job 1:21-22)" not in para3_sources
        assert "Theological Source" in para3_sources

    def test_ezekiel_generation_avoids_christological_drift_and_preserves_case(self, tmp_path, monkeypatch):
        gm_dir = tmp_path / "gm"
        ptm_dir = tmp_path / "ptm"
        monkeypatch.setattr(GroundingMapStore, "DEFAULT_ROOT", gm_dir)
        monkeypatch.setattr(PrayerTraceMapStore, "DEFAULT_ROOT", ptm_dir)

        class StubRetriever:
            def retrieve(self, reference, translation, operator_import=None):
                return ScriptureResult(
                    reference="Ezekiel 38:1-4",
                    text=(
                        "Prophecy about Gog and Future Invasion of Israel\n"
                        "And the word of the Lord came to me saying, Son of man, set your face toward Gog of the land of Magog, "
                        "the prince of Rosh, Meshech and Tubal, and prophesy against him."
                    ),
                    translation="NASB",
                    retrieval_source="api_bible",
                    verification_status="verified",
                )

        gen = DeterministicRealSectionGenerator(retriever=StubRetriever())
        day = gen.generate_day("Ezekiel 38-39", 1, scripture_reference="Ezekiel 38:1-4")

        assert "faithful response to jesus" not in day.exposition.text.lower()
        assert "Prophecy about Gog and Future Invasion of Israel" not in day.scripture.text
        assert "Gog of the land of Magog" in day.exposition.text
        assert "gog of the land of magog" not in day.exposition.text
        assert "Read the scene of steadfast attention under divine warning slowly" in "\n".join(day.be_still.prompts)
        assert (
            "Because Ezekiel 38:1-4 calls for sober obedience that takes God's warning seriously today:"
            == day.action_steps.connector_phrase
        )
        assert "Lord Jesus" not in day.prayer.text


# ---------------------------------------------------------------------------
# Test B — Orchestrator auto-resolution
# ---------------------------------------------------------------------------


class TestOrchestratorIntegration:
    def test_exposition_grounding_map_check_present(self, gen_with_store):
        gen, _store, _ptm_store = gen_with_store
        day = gen.generate_day("grace", 1, scripture_reference="Romans 8:15")

        assessments = validate_daily_devotional(day)
        check_ids = {a.check_id for a in assessments}
        assert "EXPOSITION_GROUNDING_MAP" in check_ids, (
            "EXPOSITION_GROUNDING_MAP check must be present when grounding_map_id is truthy"
        )

    def test_exposition_grounding_map_check_passes(self, gen_with_store):
        gen, _store, _ptm_store = gen_with_store
        day = gen.generate_day("grace", 1, scripture_reference="Romans 8:15")

        assessments = validate_daily_devotional(day)
        grounding_check = next(
            a for a in assessments if a.check_id == "EXPOSITION_GROUNDING_MAP"
        )
        assert grounding_check.result == "pass", (
            f"EXPOSITION_GROUNDING_MAP check failed: {grounding_check.reason_code}"
        )


# ---------------------------------------------------------------------------
# Test C — Audit layer integration
# ---------------------------------------------------------------------------


class TestAuditIntegration:
    def test_grounding_status_pass(self, gen_with_store):
        gen, _store, _ptm_store = gen_with_store
        day = gen.generate_day("grace", 1, scripture_reference="Romans 8:15")

        results = audit_devotionals([day])
        assert len(results) == 1
        assert results[0].grounding_status == "pass"

    def test_prayer_trace_status_pass(self, gen_with_store):
        gen, _store, ptm_store = gen_with_store
        day = gen.generate_day("grace", 1, scripture_reference="Romans 8:15")
        assert day.prayer.prayer_trace_map_id
        assert ptm_store.exists(day.prayer.prayer_trace_map_id)

        results = audit_devotionals([day])
        assert results[0].prayer_trace_status == "pass"


class TestPrayerText:
    def test_build_prayer_does_not_repeat_opening_invocation(self):
        prayer = _build_prayer(
            topic="grace",
            scripture_reference="Romans 8:15",
            scripture_text="For you did not receive a spirit of slavery leading to fear again.",
            exposition_text="God's grace steadies fearful hearts and teaches trust in the Father.",
        )
        opening = "Father, we thank You for the truth of Romans 8:15"
        assert prayer.count(opening) == 0
        assert prayer.count("Father, thank You for speaking clearly in Romans 8:15") == 1
