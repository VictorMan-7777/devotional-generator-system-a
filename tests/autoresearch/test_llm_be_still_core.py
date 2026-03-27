from __future__ import annotations

from src.autoresearch.llm_be_still_core import evaluate_be_still_section


def test_evaluate_be_still_section_passes_clean_prompts() -> None:
    prompts = [
        "Sit quietly and read the opening verses of Habakkuk again.",
        "What specific complaint does Habakkuk bring before God in these verses?",
        "What in the prophet's lament do you find yourself carrying today?",
        "What would it look like to bring that specific weight honestly before God rather than resolving it on your own?",
    ]
    result = evaluate_be_still_section(
        prompts,
        passage_reference="Habakkuk 1:1-4",
        passage_text="Habakkuk opens with an unresolved complaint...",
    )
    assert result["status"] in {"pass", "revise"}
    assert result["score"] >= 60
    assert "prompt_count" in result["metrics"]


def test_evaluate_be_still_section_fails_wrong_count() -> None:
    # Only 2 prompts — below minimum of 3
    prompts = [
        "Sit quietly and read the passage.",
        "What does this mean for your life?",
    ]
    result = evaluate_be_still_section(
        prompts,
        passage_reference="Psalm 23:1-3",
        passage_text="The shepherd leads his sheep...",
    )
    assert result["score"] < 100
    assert any("count" in f.lower() or "2" in f for f in result["findings"])


def test_evaluate_be_still_section_penalizes_generic_phrases() -> None:
    prompts = [
        "Sit quietly and trust in him.",
        "God is with you. Open your heart to his presence.",
        "What would it look like to draw near today?",
    ]
    result = evaluate_be_still_section(
        prompts,
        passage_reference="Colossians 3:1-4",
        passage_text="Paul calls believers to set their minds on things above...",
    )
    assert result["score"] < 100
    assert result["metrics"]["generic_phrase_count"] >= 1


def test_evaluate_be_still_section_requires_second_person() -> None:
    # Prompts all in third person — no "you/your"
    prompts = [
        "The reader should sit with the text.",
        "Consider what the passage reveals about God.",
        "The believer is called to respond with trust.",
    ]
    result = evaluate_be_still_section(
        prompts,
        passage_reference="Exodus 20:1-3",
        passage_text="God speaks from the mountain...",
    )
    assert result["score"] < 100
    assert result["metrics"]["has_second_person"] is False
