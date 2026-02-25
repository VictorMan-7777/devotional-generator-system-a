"""Unit tests for src/grounding_store/id_policy.py — create_grounding_map_id.

Required behaviours:
  1) Deterministic: same exposition_id always produces same grounding_map_id.
  2) Distinct: different exposition_ids produce different grounding_map_ids.
  3) Format: output matches "gm_<8 hex chars>" (12 chars total, hex after prefix).
"""
from __future__ import annotations

import re

import pytest

from src.grounding_store.id_policy import create_grounding_map_id

_GM_ID_PATTERN = re.compile(r"^gm_[0-9a-f]{8}$")


class TestDeterminism:
    def test_same_input_returns_same_id(self):
        id_a = create_grounding_map_id("expo-001")
        id_b = create_grounding_map_id("expo-001")
        assert id_a == id_b

    def test_deterministic_across_multiple_calls(self):
        results = [create_grounding_map_id("expo-42") for _ in range(10)]
        assert len(set(results)) == 1

    def test_empty_string_is_stable(self):
        id_a = create_grounding_map_id("")
        id_b = create_grounding_map_id("")
        assert id_a == id_b


class TestDistinctness:
    def test_different_ids_for_different_inputs(self):
        id_a = create_grounding_map_id("expo-001")
        id_b = create_grounding_map_id("expo-002")
        assert id_a != id_b

    def test_ordering_matters(self):
        """Reversed string should produce a different id."""
        id_a = create_grounding_map_id("abc")
        id_b = create_grounding_map_id("cba")
        assert id_a != id_b

    def test_whitespace_is_significant(self):
        id_a = create_grounding_map_id("expo 001")
        id_b = create_grounding_map_id("expo-001")
        assert id_a != id_b


class TestFormat:
    def test_prefix_is_gm_underscore(self):
        result = create_grounding_map_id("expo-001")
        assert result.startswith("gm_")

    def test_total_length_is_11(self):
        result = create_grounding_map_id("expo-001")
        assert len(result) == 11  # "gm_" (3) + 8 hex chars

    def test_suffix_is_8_lowercase_hex_chars(self):
        result = create_grounding_map_id("expo-001")
        suffix = result[3:]
        assert len(suffix) == 8
        assert all(c in "0123456789abcdef" for c in suffix)

    def test_full_format_matches_pattern(self):
        for expo_id in ("expo-001", "expo-999", "", "some-long-id-string"):
            result = create_grounding_map_id(expo_id)
            assert _GM_ID_PATTERN.match(result), (
                f"create_grounding_map_id({expo_id!r}) = {result!r} does not match pattern"
            )

    def test_returns_string(self):
        result = create_grounding_map_id("expo-001")
        assert isinstance(result, str)
