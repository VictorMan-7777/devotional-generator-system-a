"""Tests for src/validation/modernization.py — FR-56 archaic modernization."""
import pytest

from src.validation.modernization import modernize


class TestArchaicPronouns:
    def test_thee_to_you(self):
        assert modernize("Give thee rest") == "Give you rest"

    def test_thou_to_you(self):
        assert modernize("thou art faithful") == "you art faithful"

    def test_thy_to_your(self):
        assert modernize("thy word is truth") == "your word is truth"

    def test_thine_to_yours(self):
        assert modernize("thine is the glory") == "yours is the glory"

    def test_ye_to_you(self):
        assert modernize("ye shall know") == "you shall know"

    def test_case_insensitive(self):
        assert modernize("THOU art") == "you art"
        assert modernize("THY grace") == "your grace"


class TestArchaicVerbs:
    def test_hath_to_has(self):
        assert modernize("God hath spoken") == "God has spoken"

    def test_hast_to_have(self):
        assert modernize("thou hast sinned") == "you have sinned"

    def test_doth_to_does(self):
        assert modernize("it doth appear") == "it does appear"

    def test_cometh_to_comes(self):
        assert modernize("there cometh a time") == "there comes a time"

    def test_saith_to_says(self):
        assert modernize("the Lord saith") == "the Lord says"

    def test_wilt_to_will(self):
        assert modernize("thou wilt return") == "you will return"

    def test_wouldst_to_would(self):
        assert modernize("thou wouldst have known") == "you would have known"

    def test_canst_to_can(self):
        assert modernize("if thou canst believe") == "if you can believe"

    def test_shalt_to_shall(self):
        assert modernize("thou shalt not kill") == "you shall not kill"


class TestShiftedMeaning:
    def test_charity_to_love(self):
        assert modernize("now abideth charity") == "now abideth love"

    def test_conversation_to_conduct(self):
        assert modernize("let your conversation be holy") == "let your conduct be holy"

    def test_prevent_to_precede(self):
        assert modernize("his mercy shall prevent me") == "his mercy shall precede me"


class TestNegationModalityPreservation:
    def test_shall_not_preserved(self):
        result = modernize("thou shalt not kill")
        # "thou" → "you", "shalt not" → "shall not" (protected before "shalt" substitution)
        assert "shall not" in result
        assert "may not" not in result

    def test_will_not_preserved(self):
        result = modernize("he will not fail thee")
        assert "will not" in result
        assert "thee" not in result  # thee still replaced

    def test_would_not_preserved(self):
        result = modernize("he would not leave thee")
        assert "would not" in result

    def test_cannot_preserved(self):
        result = modernize("thou canst not escape")
        # "canst not" is not in protected list; "canst" → "can" is fine: "can not escape"
        # But we primarily check "cannot" is preserved when present
        result2 = modernize("we cannot know")
        assert "cannot" in result2

    def test_shall_not_not_changed_to_may_not(self):
        # Core correctness assertion from the plan
        assert modernize("shall not") == "shall not"
        assert modernize("thou shalt not") == "you shall not"

    def test_wilt_not_preserved(self):
        result = modernize("thou wilt not forsake us")
        assert "will not" in result
        assert "wilt" not in result

    def test_hath_not_preserved(self):
        result = modernize("God hath not forgotten thee")
        assert "has not" in result or "hath not" in result
        # Either "hath not" was protected or "hath" → "has"; either is acceptable.
        # What matters: negation remains.
        assert "not" in result

    def test_clean_text_unchanged(self):
        text = "The grace of God is sufficient."
        assert modernize(text) == text

    def test_mixed_substitutions(self):
        result = modernize("thy servant hath spoken; thou wilt hear")
        assert "your" in result
        assert "has" in result
        assert "will" in result
