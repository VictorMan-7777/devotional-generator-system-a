from __future__ import annotations

from src.validation.readability import grade_band_label, score_text, section_readability_report


def test_score_text_returns_expected_fields() -> None:
    score = score_text("God is holy. We should listen carefully and obey with joy.")
    assert score.word_count > 0
    assert score.sentence_count == 2
    assert isinstance(score.flesch_reading_ease, float)
    assert isinstance(score.flesch_kincaid_grade, float)


def test_grade_band_label_targets_eighth_grade_and_below() -> None:
    easy = score_text("God is good. We trust Him.")
    assert grade_band_label(easy) in {"very_easy", "target"}


def test_section_readability_report_contains_grade_band() -> None:
    report = section_readability_report("The Lord is in His holy temple. Let all the earth be silent before Him.")
    assert "flesch_kincaid_grade" in report
    assert "flesch_reading_ease" in report
    assert "grade_band" in report
