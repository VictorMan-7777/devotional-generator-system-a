"""Unit tests for src/grounding_store/store.py.

Tests cover all six required behaviours:
  1. save_then_load_roundtrip — model_dump equality
  2. deterministic_file_content — identical bytes on repeated saves
  3. load_missing_raises — KeyError with clear message
  4. resolve_none_when_no_id — falsy grounding_map_id returns None
  5. resolve_raises_when_id_missing — set id but absent artifact raises KeyError
  6. validator_accepts_loaded_map — full path: save → load → validate_daily_devotional
     with EXPOSITION_GROUNDING_MAP check executed (not skipped) and passing

Plus additional coverage:
  - exists() returns False before save, True after
  - overwrite semantics: second save replaces first
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.generation.generators import MockSectionGenerator
from src.grounding_store.store import GroundingMapStore, resolve_grounding_map
from src.interfaces.rag import RetrievedExcerpt
from src.models.artifacts import GroundingMap
from src.models.devotional import ExpositionSection, SectionApprovalStatus
from src.rag.grounding import GroundingMapBuilder
from src.validation.orchestrator import validate_daily_devotional


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _make_excerpt(text: str, source: str = "Source A") -> RetrievedExcerpt:
    return RetrievedExcerpt(
        text=text,
        source_title=source,
        author="Test Author",
        source_type="commentary",
    )


def _four_paragraph_excerpts() -> dict:
    return {
        1: [_make_excerpt("Declaration: God's steadfast love endures.")],
        2: [_make_excerpt("Context: Historical background of Lamentations."), _make_excerpt("More context.")],
        3: [_make_excerpt("Theological: The nature of divine compassion.")],
        4: [_make_excerpt("Bridge: Application to daily trust.")],
    }


@pytest.fixture
def sample_map() -> GroundingMap:
    return GroundingMapBuilder().build("expo-test-001", _four_paragraph_excerpts())


@pytest.fixture
def store(tmp_path: Path) -> GroundingMapStore:
    return GroundingMapStore(tmp_path)


# ---------------------------------------------------------------------------
# 1. save_then_load_roundtrip
# ---------------------------------------------------------------------------


class TestSaveLoadRoundtrip:
    def test_roundtrip_model_dump_equality(self, store: GroundingMapStore, sample_map: GroundingMap):
        store.save(sample_map)
        loaded = store.load(sample_map.id)
        assert loaded.model_dump() == sample_map.model_dump()

    def test_loaded_exposition_id_matches(self, store: GroundingMapStore, sample_map: GroundingMap):
        store.save(sample_map)
        loaded = store.load(sample_map.id)
        assert loaded.exposition_id == sample_map.exposition_id

    def test_loaded_entries_count(self, store: GroundingMapStore, sample_map: GroundingMap):
        store.save(sample_map)
        loaded = store.load(sample_map.id)
        assert len(loaded.entries) == 4

    def test_loaded_is_valid_grounding_map_instance(self, store: GroundingMapStore, sample_map: GroundingMap):
        store.save(sample_map)
        loaded = store.load(sample_map.id)
        assert isinstance(loaded, GroundingMap)


# ---------------------------------------------------------------------------
# 2. deterministic_file_content
# ---------------------------------------------------------------------------


class TestDeterministicFileContent:
    def test_identical_saves_produce_identical_bytes(self, store: GroundingMapStore, sample_map: GroundingMap):
        store.save(sample_map)
        content_a = (store._dir / f"{sample_map.id}.json").read_bytes()

        store.save(sample_map)
        content_b = (store._dir / f"{sample_map.id}.json").read_bytes()

        assert content_a == content_b

    def test_saved_file_is_valid_json(self, store: GroundingMapStore, sample_map: GroundingMap):
        import json as _json
        store.save(sample_map)
        text = (store._dir / f"{sample_map.id}.json").read_text(encoding="utf-8")
        parsed = _json.loads(text)
        assert isinstance(parsed, dict)
        assert parsed["id"] == sample_map.id


# ---------------------------------------------------------------------------
# 3. load_missing_raises
# ---------------------------------------------------------------------------


class TestLoadMissingRaises:
    def test_raises_key_error(self, store: GroundingMapStore):
        with pytest.raises(KeyError):
            store.load("nonexistent-id")

    def test_error_message_contains_id(self, store: GroundingMapStore):
        missing_id = "missing-gm-999"
        with pytest.raises(KeyError, match=missing_id):
            store.load(missing_id)


# ---------------------------------------------------------------------------
# 4. exists()
# ---------------------------------------------------------------------------


class TestExists:
    def test_returns_false_for_missing(self, store: GroundingMapStore):
        assert store.exists("nonexistent-id") is False

    def test_returns_true_after_save(self, store: GroundingMapStore, sample_map: GroundingMap):
        store.save(sample_map)
        assert store.exists(sample_map.id) is True

    def test_overwrite_does_not_break_exists(self, store: GroundingMapStore, sample_map: GroundingMap):
        store.save(sample_map)
        store.save(sample_map)  # second save overwrites
        assert store.exists(sample_map.id) is True


# ---------------------------------------------------------------------------
# 5. resolve_none_when_no_id
# ---------------------------------------------------------------------------


class TestResolveNoneWhenNoId:
    def _exposition_with_id(self, gm_id: str) -> ExpositionSection:
        return ExpositionSection(
            text="Test exposition text " * 40,
            word_count=120,
            grounding_map_id=gm_id,
            approval_status=SectionApprovalStatus.PENDING,
        )

    def test_empty_string_returns_none(self, store: GroundingMapStore):
        section = self._exposition_with_id("")
        result = resolve_grounding_map(section, store)
        assert result is None

    def test_placeholder_id_in_store_returns_map(self, store: GroundingMapStore, sample_map: GroundingMap):
        """When a real id is saved, resolve returns the GroundingMap."""
        store.save(sample_map)
        section = self._exposition_with_id(sample_map.id)
        result = resolve_grounding_map(section, store)
        assert result is not None
        assert result.id == sample_map.id


# ---------------------------------------------------------------------------
# 6. resolve_raises_when_id_missing
# ---------------------------------------------------------------------------


class TestResolveRaisesWhenIdMissing:
    def test_set_id_not_in_store_raises_key_error(self, store: GroundingMapStore):
        """Non-empty id with no saved artifact → KeyError (no silent skip)."""
        section = ExpositionSection(
            text="Some exposition text " * 40,
            word_count=120,
            grounding_map_id="gm-mock",  # typical mock placeholder, never saved
            approval_status=SectionApprovalStatus.PENDING,
        )
        with pytest.raises(KeyError):
            resolve_grounding_map(section, store)


# ---------------------------------------------------------------------------
# 7. validator_accepts_loaded_map (the key integration check)
# ---------------------------------------------------------------------------


class TestValidatorAcceptsLoadedMap:
    def test_exposition_grounding_map_check_executed_and_passes(
        self, store: GroundingMapStore, sample_map: GroundingMap
    ):
        """Full path: save → load → validate_daily_devotional.

        With a valid GroundingMap, EXPOSITION_GROUNDING_MAP check must be
        present in the results (not skipped) and must pass.
        No generate_devotional() changes; uses MockSectionGenerator directly.
        """
        store.save(sample_map)
        loaded = store.load(sample_map.id)

        # MockSectionGenerator produces a day that passes all other checks.
        day = MockSectionGenerator().generate_day("grace", 1)

        # Pass the loaded GroundingMap to the orchestrator.
        assessments = validate_daily_devotional(day, grounding_map=loaded)

        check_ids = [a.check_id for a in assessments]
        assert "EXPOSITION_GROUNDING_MAP" in check_ids, (
            "EXPOSITION_GROUNDING_MAP check was skipped — GroundingMap was not passed through"
        )

        gm_result = next(a for a in assessments if a.check_id == "EXPOSITION_GROUNDING_MAP")
        assert gm_result.result == "pass", (
            f"EXPOSITION_GROUNDING_MAP check failed: {gm_result.reason_code} — {gm_result.explanation}"
        )

    def test_validator_returns_list_of_assessments(
        self, store: GroundingMapStore, sample_map: GroundingMap
    ):
        store.save(sample_map)
        loaded = store.load(sample_map.id)
        day = MockSectionGenerator().generate_day("grace", 1)
        assessments = validate_daily_devotional(day, grounding_map=loaded)
        assert isinstance(assessments, list)
        assert len(assessments) > 0
