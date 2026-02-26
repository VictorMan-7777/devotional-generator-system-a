"""Unit tests for src/prayer_trace_store/id_policy.py — create_prayer_trace_map_id.

Required behaviours:
  1) Deterministic: same prayer_id always produces same prayer_trace_map_id.
  2) Distinct: different prayer_ids produce different prayer_trace_map_ids.
  3) Format: output matches "ptm_<8 hex chars>" (12 chars total, hex after prefix).
"""
from __future__ import annotations

import re

import pytest

from src.prayer_trace_store.id_policy import create_prayer_trace_map_id

_PTM_ID_PATTERN = re.compile(r"^ptm_[0-9a-f]{8}$")


class TestDeterminism:
    def test_same_input_returns_same_id(self):
        id_a = create_prayer_trace_map_id("prayer-001")
        id_b = create_prayer_trace_map_id("prayer-001")
        assert id_a == id_b

    def test_deterministic_across_multiple_calls(self):
        results = [create_prayer_trace_map_id("prayer-42") for _ in range(10)]
        assert len(set(results)) == 1

    def test_empty_string_is_stable(self):
        id_a = create_prayer_trace_map_id("")
        id_b = create_prayer_trace_map_id("")
        assert id_a == id_b


class TestDistinctness:
    def test_different_ids_for_different_inputs(self):
        id_a = create_prayer_trace_map_id("prayer-001")
        id_b = create_prayer_trace_map_id("prayer-002")
        assert id_a != id_b

    def test_ordering_matters(self):
        """Reversed string should produce a different id."""
        id_a = create_prayer_trace_map_id("abc")
        id_b = create_prayer_trace_map_id("cba")
        assert id_a != id_b

    def test_whitespace_is_significant(self):
        id_a = create_prayer_trace_map_id("prayer 001")
        id_b = create_prayer_trace_map_id("prayer-001")
        assert id_a != id_b


class TestFormat:
    def test_prefix_is_ptm_underscore(self):
        result = create_prayer_trace_map_id("prayer-001")
        assert result.startswith("ptm_")

    def test_total_length_is_12(self):
        result = create_prayer_trace_map_id("prayer-001")
        assert len(result) == 12  # "ptm_" (4) + 8 hex chars

    def test_suffix_is_8_lowercase_hex_chars(self):
        result = create_prayer_trace_map_id("prayer-001")
        suffix = result[4:]
        assert len(suffix) == 8
        assert all(c in "0123456789abcdef" for c in suffix)

    def test_full_format_matches_pattern(self):
        for prayer_id in ("prayer-001", "prayer-999", "", "some-long-id-string"):
            result = create_prayer_trace_map_id(prayer_id)
            assert _PTM_ID_PATTERN.match(result), (
                f"create_prayer_trace_map_id({prayer_id!r}) = {result!r} does not match pattern"
            )

    def test_returns_string(self):
        result = create_prayer_trace_map_id("prayer-001")
        assert isinstance(result, str)
