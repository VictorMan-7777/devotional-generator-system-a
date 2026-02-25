"""Unit tests for src/prayer_trace_store/store.py — PrayerTraceMapStore.

Minimal mirror of tests/grounding_store/test_store.py.

Required behaviours:
  1. save→load roundtrip equals model_dump
  2. deterministic bytes (identical saves produce identical bytes)
  3. missing id raises KeyError with id in message
  4. exists() returns False before save, True after
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.models.artifacts import PrayerTraceMap, PrayerTraceMapEntry
from src.prayer_trace_store.store import PrayerTraceMapStore


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _sample_trace_map() -> PrayerTraceMap:
    return PrayerTraceMap(
        id="ptm-store-test-001",
        prayer_id="prayer-test-001",
        entries=[
            PrayerTraceMapEntry(
                element_text="Father, thank you for your grace.",
                source_type="scripture",
                source_reference="Romans 8:15",
            ),
            PrayerTraceMapEntry(
                element_text="Lead me in your truth.",
                source_type="exposition",
                source_reference="First paragraph: God's steadfast love.",
            ),
            PrayerTraceMapEntry(
                element_text="Let me rest in your presence.",
                source_type="be_still",
                source_reference="Prompt 2: What word stays with you?",
            ),
        ],
    )


@pytest.fixture
def sample_map() -> PrayerTraceMap:
    return _sample_trace_map()


@pytest.fixture
def store(tmp_path: Path) -> PrayerTraceMapStore:
    return PrayerTraceMapStore(tmp_path)


# ---------------------------------------------------------------------------
# 1. save → load roundtrip
# ---------------------------------------------------------------------------


class TestSaveLoadRoundtrip:
    def test_roundtrip_model_dump_equality(
        self, store: PrayerTraceMapStore, sample_map: PrayerTraceMap
    ):
        store.save(sample_map)
        loaded = store.load(sample_map.id)
        assert loaded.model_dump() == sample_map.model_dump()

    def test_loaded_prayer_id_matches(
        self, store: PrayerTraceMapStore, sample_map: PrayerTraceMap
    ):
        store.save(sample_map)
        loaded = store.load(sample_map.id)
        assert loaded.prayer_id == sample_map.prayer_id

    def test_loaded_entries_count(
        self, store: PrayerTraceMapStore, sample_map: PrayerTraceMap
    ):
        store.save(sample_map)
        loaded = store.load(sample_map.id)
        assert len(loaded.entries) == 3

    def test_loaded_is_prayer_trace_map_instance(
        self, store: PrayerTraceMapStore, sample_map: PrayerTraceMap
    ):
        store.save(sample_map)
        loaded = store.load(sample_map.id)
        assert isinstance(loaded, PrayerTraceMap)


# ---------------------------------------------------------------------------
# 2. deterministic bytes
# ---------------------------------------------------------------------------


class TestDeterministicBytes:
    def test_identical_saves_produce_identical_bytes(
        self, store: PrayerTraceMapStore, sample_map: PrayerTraceMap
    ):
        store.save(sample_map)
        content_a = (store._dir / f"{sample_map.id}.json").read_bytes()
        store.save(sample_map)
        content_b = (store._dir / f"{sample_map.id}.json").read_bytes()
        assert content_a == content_b

    def test_saved_file_is_valid_json(
        self, store: PrayerTraceMapStore, sample_map: PrayerTraceMap
    ):
        store.save(sample_map)
        text = (store._dir / f"{sample_map.id}.json").read_text(encoding="utf-8")
        parsed = json.loads(text)
        assert isinstance(parsed, dict)
        assert parsed["id"] == sample_map.id


# ---------------------------------------------------------------------------
# 3. missing id raises KeyError
# ---------------------------------------------------------------------------


class TestLoadMissingRaises:
    def test_raises_key_error(self, store: PrayerTraceMapStore):
        with pytest.raises(KeyError):
            store.load("nonexistent-id")

    def test_error_message_contains_id(self, store: PrayerTraceMapStore):
        missing_id = "missing-ptm-999"
        with pytest.raises(KeyError, match=missing_id):
            store.load(missing_id)


# ---------------------------------------------------------------------------
# 4. exists()
# ---------------------------------------------------------------------------


class TestExists:
    def test_returns_false_before_save(self, store: PrayerTraceMapStore):
        assert store.exists("nonexistent-id") is False

    def test_returns_true_after_save(
        self, store: PrayerTraceMapStore, sample_map: PrayerTraceMap
    ):
        store.save(sample_map)
        assert store.exists(sample_map.id) is True

    def test_overwrite_does_not_break_exists(
        self, store: PrayerTraceMapStore, sample_map: PrayerTraceMap
    ):
        store.save(sample_map)
        store.save(sample_map)
        assert store.exists(sample_map.id) is True
