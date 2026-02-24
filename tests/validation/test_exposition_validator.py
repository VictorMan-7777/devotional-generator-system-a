"""Tests for src/validation/exposition.py — FR-74 exposition validator."""
import pytest

from src.models.artifacts import GroundingMap, GroundingMapEntry
from src.models.devotional import ExpositionSection
from src.validation.exposition import validate_exposition


def _make_exposition(word_count: int, *, include_you: bool = False) -> ExpositionSection:
    """Construct an ExpositionSection whose text has exactly `word_count` words."""
    base_word = "grace"
    words = [base_word] * word_count
    if include_you:
        words[0] = "you"  # inject second-person pronoun at start
    text = " ".join(words)
    return ExpositionSection(
        text=text,
        word_count=word_count,  # stored field (ignored by validator)
        grounding_map_id="gm-test",
    )


def _ids(results) -> set[str]:
    return {a.check_id for a in results}


def _result(results, check_id: str) -> str:
    for a in results:
        if a.check_id == check_id:
            return a.result
    raise KeyError(check_id)


class TestWordCount:
    def test_exactly_500_passes(self):
        section = _make_exposition(500)
        results = validate_exposition(section)
        assert _result(results, "EXPOSITION_WORD_COUNT") == "pass"

    def test_exactly_700_passes(self):
        section = _make_exposition(700)
        results = validate_exposition(section)
        assert _result(results, "EXPOSITION_WORD_COUNT") == "pass"

    def test_midrange_passes(self):
        section = _make_exposition(600)
        results = validate_exposition(section)
        assert _result(results, "EXPOSITION_WORD_COUNT") == "pass"

    def test_499_fails(self):
        section = _make_exposition(499)
        results = validate_exposition(section)
        assert _result(results, "EXPOSITION_WORD_COUNT") == "fail"
        assessment = next(a for a in results if a.check_id == "EXPOSITION_WORD_COUNT")
        assert assessment.reason_code == "EXPOSITION_WORD_COUNT_VIOLATION"

    def test_701_fails(self):
        section = _make_exposition(701)
        results = validate_exposition(section)
        assert _result(results, "EXPOSITION_WORD_COUNT") == "fail"

    def test_word_count_computed_from_text_not_stored_field(self):
        # Stored word_count says 700 (in range) but actual text is 400 words.
        section = ExpositionSection(
            text=" ".join(["word"] * 400),
            word_count=700,  # stored field is wrong
            grounding_map_id="gm-test",
        )
        results = validate_exposition(section)
        # Validator must use len(text.split()) = 400, not the stored 700.
        assert _result(results, "EXPOSITION_WORD_COUNT") == "fail"


class TestVoiceCheck:
    def test_communal_voice_passes(self):
        section = _make_exposition(500)
        results = validate_exposition(section)
        assert _result(results, "EXPOSITION_VOICE") == "pass"

    def test_you_fails(self):
        text = "you " + " ".join(["grace"] * 499)
        section = ExpositionSection(text=text, word_count=500, grounding_map_id="gm-test")
        results = validate_exposition(section)
        assert _result(results, "EXPOSITION_VOICE") == "fail"
        assessment = next(a for a in results if a.check_id == "EXPOSITION_VOICE")
        assert assessment.reason_code == "EXPOSITION_SECOND_PERSON_VIOLATION"

    def test_your_fails(self):
        text = "your " + " ".join(["grace"] * 499)
        section = ExpositionSection(text=text, word_count=500, grounding_map_id="gm-test")
        results = validate_exposition(section)
        assert _result(results, "EXPOSITION_VOICE") == "fail"

    def test_you_case_insensitive(self):
        text = "YOU " + " ".join(["grace"] * 499)
        section = ExpositionSection(text=text, word_count=500, grounding_map_id="gm-test")
        results = validate_exposition(section)
        assert _result(results, "EXPOSITION_VOICE") == "fail"

    def test_we_and_our_are_fine(self):
        text = "we our " + " ".join(["grace"] * 498)
        section = ExpositionSection(text=text, word_count=500, grounding_map_id="gm-test")
        results = validate_exposition(section)
        assert _result(results, "EXPOSITION_VOICE") == "pass"


class TestGroundingMap:
    def _make_entry(self, paragraph_number: int) -> GroundingMapEntry:
        return GroundingMapEntry(
            paragraph_number=paragraph_number,
            paragraph_name=f"Para {paragraph_number}",
            sources_retrieved=["Matthew Henry"],
            excerpts_used=["excerpt text"],
            how_retrieval_informed_paragraph="Informed theological claim.",
        )

    def test_valid_grounding_map_passes(self):
        section = _make_exposition(500)
        gm = GroundingMap(
            id="gm-1",
            exposition_id="exp-1",
            entries=[self._make_entry(i) for i in range(1, 5)],
        )
        results = validate_exposition(section, grounding_map=gm)
        assert _result(results, "EXPOSITION_GROUNDING_MAP") == "pass"

    def test_missing_grounding_map_skips_check(self):
        section = _make_exposition(500)
        results = validate_exposition(section, grounding_map=None)
        assert "EXPOSITION_GROUNDING_MAP" not in _ids(results)

    def test_three_entries_fails_at_model_level(self):
        # GroundingMap model validator enforces exactly 4 entries.
        # Construction with 3 entries raises at the schema level.
        with pytest.raises(Exception):
            GroundingMap(
                id="gm-1",
                exposition_id="exp-1",
                entries=[self._make_entry(i) for i in range(1, 4)],
            )

    def test_five_entries_fails_at_model_level(self):
        with pytest.raises(Exception):
            GroundingMap(
                id="gm-1",
                exposition_id="exp-1",
                entries=[self._make_entry(i) for i in range(1, 6)],
            )

    def test_empty_sources_fails(self):
        section = _make_exposition(500)
        entry = GroundingMapEntry(
            paragraph_number=1,
            paragraph_name="Para 1",
            sources_retrieved=[],  # empty
            excerpts_used=["excerpt"],
            how_retrieval_informed_paragraph="Informed.",
        )
        # GroundingMap model validator rejects empty sources_retrieved.
        with pytest.raises(Exception):
            GroundingMap(
                id="gm-1",
                exposition_id="exp-1",
                entries=[entry] + [self._make_entry(i) for i in range(2, 5)],
            )

    def test_no_grounding_map_check_id_absent(self):
        section = _make_exposition(500)
        results = validate_exposition(section)
        assert "EXPOSITION_GROUNDING_MAP" not in {a.check_id for a in results}
