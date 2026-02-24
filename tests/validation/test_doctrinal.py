"""Tests for src/validation/doctrinal.py — doctrinal guardrail engine."""
import pytest

from src.validation.doctrinal import check_doctrinal


class TestCleanText:
    def test_empty_string_is_clean(self):
        assert check_doctrinal("") == []

    def test_orthodox_exposition_is_clean(self):
        text = (
            "The grace of God reaches into the ordinary moments of life. "
            "When we trust in Christ's finished work, we find rest. "
            "The Holy Spirit guides us into all truth."
        )
        assert check_doctrinal(text) == []

    def test_love_not_flagged_as_charity(self):
        # "love" itself should not trigger patterns
        assert check_doctrinal("God's love is unconditional.") == []


class TestProsperityGospel:
    def test_god_wants_you_rich_flagged(self):
        results = check_doctrinal("God wants you rich and blessed.")
        ids = {a.check_id for a in results}
        assert "DOCTRINAL_PROSPERITY" in ids
        assert results[0].reason_code == "DOCTRINAL_PROSPERITY_GOSPEL"

    def test_god_wants_you_wealthy_flagged(self):
        results = check_doctrinal("God wants you wealthy beyond measure.")
        assert any(a.check_id == "DOCTRINAL_PROSPERITY" for a in results)

    def test_financial_blessing_flagged(self):
        results = check_doctrinal("Claim your financial blessing today.")
        assert any(a.check_id == "DOCTRINAL_PROSPERITY" for a in results)

    def test_name_it_claim_it_flagged(self):
        results = check_doctrinal("Just name it and claim it by faith.")
        assert any(a.check_id == "DOCTRINAL_PROSPERITY" for a in results)

    def test_health_and_wealth_flagged(self):
        results = check_doctrinal("The health and wealth gospel is spreading.")
        assert any(a.check_id == "DOCTRINAL_PROSPERITY" for a in results)

    def test_case_insensitive(self):
        results = check_doctrinal("GOD WANTS YOU RICH.")
        assert any(a.check_id == "DOCTRINAL_PROSPERITY" for a in results)

    def test_only_one_assessment_per_category(self):
        # Multiple matches in the same text produce ONE assessment for the category.
        results = check_doctrinal(
            "God wants you rich and God wants you wealthy and financial blessing."
        )
        prosperity_results = [a for a in results if a.check_id == "DOCTRINAL_PROSPERITY"]
        assert len(prosperity_results) == 1


class TestWorksMerit:
    def test_earn_gods_love_flagged(self):
        results = check_doctrinal("You must earn God's love through obedience.")
        assert any(a.check_id == "DOCTRINAL_WORKS_MERIT" for a in results)
        assert results[0].reason_code == "DOCTRINAL_WORKS_MERIT"

    def test_earn_your_salvation_flagged(self):
        results = check_doctrinal("Work hard to earn your salvation.")
        assert any(a.check_id == "DOCTRINAL_WORKS_MERIT" for a in results)

    def test_deserve_grace_flagged(self):
        results = check_doctrinal("Those who try harder deserve grace.")
        assert any(a.check_id == "DOCTRINAL_WORKS_MERIT" for a in results)

    def test_good_enough_for_god_flagged(self):
        results = check_doctrinal("You must become good enough for God to accept you.")
        assert any(a.check_id == "DOCTRINAL_WORKS_MERIT" for a in results)

    def test_case_insensitive(self):
        results = check_doctrinal("EARN GOD'S LOVE.")
        assert any(a.check_id == "DOCTRINAL_WORKS_MERIT" for a in results)


class TestBothCategories:
    def test_both_violations_return_two_assessments(self):
        text = (
            "God wants you rich and you must earn God's love through obedience."
        )
        results = check_doctrinal(text)
        ids = {a.check_id for a in results}
        assert "DOCTRINAL_PROSPERITY" in ids
        assert "DOCTRINAL_WORKS_MERIT" in ids
        assert len(results) == 2
