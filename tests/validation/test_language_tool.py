from __future__ import annotations

import shutil

import pytest

from src.validation.language_tool import (
    LanguageToolIssue,
    apply_safe_fixes,
    check_text,
    collect_book_advisories,
)


pytestmark = pytest.mark.skipif(
    shutil.which("languagetool") is None,
    reason="languagetool not installed",
)


def test_check_text_finds_sentence_start_capitalization_issue() -> None:
    issues = check_text("the lord said to Gog. this is a test.", ignored_words={"Gog"})
    assert any(issue.rule_id == "UPPERCASE_SENTENCE_START" for issue in issues)


def test_apply_safe_fixes_caps_sentence_starts_without_touching_ignored_words() -> None:
    fixed = apply_safe_fixes("the lord said to Gog. this is a test.", ignored_words={"Gog"})
    assert fixed.startswith("The lord said to Gog.")
    assert "Gog" in fixed
    assert "This is a test." in fixed


def test_collect_book_advisories_returns_section_scoped_findings(monkeypatch) -> None:
    def _fake_check_text(text: str, *, language: str = "en-US", ignored_words=None):
        if "bad grammar" not in text:
            return []
        return [
            LanguageToolIssue(
                rule_id="TEST_RULE",
                message="Test message",
                offset=text.index("bad"),
                length=3,
                replacements=("good",),
                category="TYPOS",
            )
        ]

    monkeypatch.setattr("src.validation.language_tool.check_text", _fake_check_text)
    advisories = collect_book_advisories(
        {
            "days": [
                {
                    "day_number": 1,
                    "day_focus": "Gog gathers",
                    "scripture": {"reference": "Ezekiel 38:1-4"},
                    "exposition": {"text": "This has bad grammar inside the exposition."},
                    "be_still": {"prompts": ["Sit quietly."]},
                    "action_steps": {"connector_phrase": "", "items": ["Walk carefully."]},
                    "prayer": {"text": "Prayer text."},
                }
            ]
        },
        editorial_build_payload={
            "day_briefs": [
                {
                    "focus_clause": "Say to Gog",
                    "key_terms": ["Gog", "Magog"],
                }
            ]
        },
    )
    assert len(advisories) == 1
    assert advisories[0].day_number == 1
    assert advisories[0].section == "exposition"
    assert advisories[0].rule_id == "TEST_RULE"
