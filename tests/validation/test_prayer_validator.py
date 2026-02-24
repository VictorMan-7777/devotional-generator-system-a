"""Tests for src/validation/prayer.py — FR-77 prayer validator."""
import pytest

from src.models.artifacts import PrayerTraceMap, PrayerTraceMapEntry
from src.models.devotional import PrayerSection
from src.validation.prayer import validate_prayer


def _make_prayer(word_count: int, *, include_trinity: bool = True) -> PrayerSection:
    """Construct a PrayerSection whose text has exactly `word_count` words."""
    if include_trinity:
        # Start with "Father" then fill remaining words.
        words = ["Father"] + ["grace"] * (word_count - 1)
    else:
        words = ["grace"] * word_count
    text = " ".join(words)
    return PrayerSection(
        text=text,
        word_count=word_count,  # stored field (ignored by validator)
        prayer_trace_map_id="ptm-test",
    )


def _result(results, check_id: str) -> str:
    for a in results:
        if a.check_id == check_id:
            return a.result
    raise KeyError(check_id)


class TestWordCount:
    def test_exactly_120_passes(self):
        section = _make_prayer(120)
        assert _result(validate_prayer(section), "PRAYER_WORD_COUNT") == "pass"

    def test_exactly_200_passes(self):
        section = _make_prayer(200)
        assert _result(validate_prayer(section), "PRAYER_WORD_COUNT") == "pass"

    def test_midrange_passes(self):
        section = _make_prayer(160)
        assert _result(validate_prayer(section), "PRAYER_WORD_COUNT") == "pass"

    def test_119_fails(self):
        section = _make_prayer(119)
        result = _result(validate_prayer(section), "PRAYER_WORD_COUNT")
        assert result == "fail"
        assessment = next(a for a in validate_prayer(section) if a.check_id == "PRAYER_WORD_COUNT")
        assert assessment.reason_code == "PRAYER_WORD_COUNT_VIOLATION"

    def test_201_fails(self):
        section = _make_prayer(201)
        assert _result(validate_prayer(section), "PRAYER_WORD_COUNT") == "fail"

    def test_word_count_computed_from_text_not_stored_field(self):
        # Stored word_count says 160 (in range) but actual text is 100 words.
        section = PrayerSection(
            text="Father " + " ".join(["grace"] * 99),
            word_count=160,  # stored field wrong
            prayer_trace_map_id="ptm-test",
        )
        # len(text.split()) = 100, which is below 120 → should fail
        assert _result(validate_prayer(section), "PRAYER_WORD_COUNT") == "fail"


class TestTrinityAddress:
    def test_father_passes(self):
        section = _make_prayer(120, include_trinity=True)
        assert _result(validate_prayer(section), "PRAYER_TRINITY_ADDRESS") == "pass"

    def test_jesus_passes(self):
        section = PrayerSection(
            text="Jesus " + " ".join(["grace"] * 119),
            word_count=120,
            prayer_trace_map_id="ptm-test",
        )
        assert _result(validate_prayer(section), "PRAYER_TRINITY_ADDRESS") == "pass"

    def test_lord_passes(self):
        section = PrayerSection(
            text="Lord " + " ".join(["grace"] * 119),
            word_count=120,
            prayer_trace_map_id="ptm-test",
        )
        assert _result(validate_prayer(section), "PRAYER_TRINITY_ADDRESS") == "pass"

    def test_spirit_passes(self):
        section = PrayerSection(
            text="Spirit " + " ".join(["grace"] * 119),
            word_count=120,
            prayer_trace_map_id="ptm-test",
        )
        assert _result(validate_prayer(section), "PRAYER_TRINITY_ADDRESS") == "pass"

    def test_no_trinity_name_fails(self):
        section = _make_prayer(120, include_trinity=False)
        result = _result(validate_prayer(section), "PRAYER_TRINITY_ADDRESS")
        assert result == "fail"
        assessment = next(
            a for a in validate_prayer(section) if a.check_id == "PRAYER_TRINITY_ADDRESS"
        )
        assert assessment.reason_code == "PRAYER_TRINITY_ADDRESS_MISSING"

    def test_trinity_case_insensitive(self):
        section = PrayerSection(
            text="FATHER " + " ".join(["grace"] * 119),
            word_count=120,
            prayer_trace_map_id="ptm-test",
        )
        assert _result(validate_prayer(section), "PRAYER_TRINITY_ADDRESS") == "pass"


class TestPrayerTraceMap:
    def _make_entry(self, source_type: str) -> PrayerTraceMapEntry:
        return PrayerTraceMapEntry(
            element_text="The petition element.",
            source_type=source_type,
            source_reference="Romans 8:15",
        )

    def test_valid_trace_map_passes(self):
        section = _make_prayer(120)
        ptm = PrayerTraceMap(
            id="ptm-1",
            prayer_id="prayer-1",
            entries=[self._make_entry("scripture"), self._make_entry("exposition")],
        )
        assert _result(validate_prayer(section, prayer_trace_map=ptm), "PRAYER_TRACE_MAP") == "pass"

    def test_missing_trace_map_skips_check(self):
        section = _make_prayer(120)
        results = validate_prayer(section, prayer_trace_map=None)
        assert "PRAYER_TRACE_MAP" not in {a.check_id for a in results}

    def test_invalid_source_type_fails_at_model_level(self):
        with pytest.raises(Exception):
            PrayerTraceMap(
                id="ptm-1",
                prayer_id="prayer-1",
                entries=[self._make_entry("invalid_type")],
            )

    def test_empty_entries_fails(self):
        section = _make_prayer(120)
        # PrayerTraceMap with empty entries passes model validation
        # but validator should flag it.
        # PrayerTraceMap model doesn't enforce non-empty at schema level.
        ptm = PrayerTraceMap(id="ptm-1", prayer_id="prayer-1", entries=[])
        result = _result(validate_prayer(section, prayer_trace_map=ptm), "PRAYER_TRACE_MAP")
        assert result == "fail"
        assessment = next(
            a for a in validate_prayer(section, prayer_trace_map=ptm)
            if a.check_id == "PRAYER_TRACE_MAP"
        )
        assert assessment.reason_code == "PRAYER_TRACE_MAP_INCOMPLETE"
