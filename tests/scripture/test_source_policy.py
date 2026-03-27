from __future__ import annotations

from src.scripture.source_policy import scripture_exact_text_compatible


def test_api_bible_and_bolls_nasb_1995_are_exact_text_compatible(monkeypatch) -> None:
    monkeypatch.setenv("API_BIBLE_BIBLE_ID", "b8ee27bcd1cae43a-01")
    assert scripture_exact_text_compatible(
        original_source="api_bible",
        validator_source="bolls_life",
        translation="NASB",
    )
