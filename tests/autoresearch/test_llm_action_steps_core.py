from __future__ import annotations

from src.autoresearch.llm_action_steps_core import evaluate_action_steps_section


def test_evaluate_action_steps_section_passes_clean_steps() -> None:
    items = [
        "Write down one specific thing from your time in stillness that surprised or unsettled you.",
        "Tell one person today what you heard God call you toward in this passage.",
    ]
    connector = "In light of what you encountered in stillness today,"
    result = evaluate_action_steps_section(
        items,
        connector,
        passage_reference="Luke 5:27-28",
        be_still_prompts=["Sit with the image of Levi leaving his table.", "What would you have left behind?"],
    )
    assert result["status"] in {"pass", "revise"}
    assert result["score"] >= 60
    assert result["metrics"]["item_count"] == 2


def test_evaluate_action_steps_section_fails_no_connector() -> None:
    items = ["Pray about it.", "Read your Bible today."]
    result = evaluate_action_steps_section(
        items,
        connector_phrase="",
        passage_reference="Proverbs 1:7-9",
        be_still_prompts=["What does the fear of the Lord look like for you today?"],
    )
    assert result["score"] < 100
    assert any("connector" in f.lower() for f in result["findings"])


def test_evaluate_action_steps_section_fails_too_many_items() -> None:
    items = [
        "Pray about your fears.",
        "Read the passage again.",
        "Journal about it.",
        "Share with a friend.",
    ]
    result = evaluate_action_steps_section(
        items,
        connector_phrase="Based on what you heard in stillness,",
        passage_reference="Colossians 3:12-14",
        be_still_prompts=["What virtue from this passage do you most lack?"],
    )
    assert result["score"] < 100
    assert any("4" in f or "count" in f.lower() for f in result["findings"])


def test_evaluate_action_steps_section_penalizes_generic_phrases() -> None:
    items = [
        "Trust God with your situation.",
        "Show kindness to those around you.",
    ]
    result = evaluate_action_steps_section(
        items,
        connector_phrase="Having sat with the passage today,",
        passage_reference="Psalm 23:4-6",
        be_still_prompts=["Where are you in the valley right now?"],
    )
    assert result["score"] < 100
    assert result["metrics"]["generic_phrase_count"] >= 1


def test_evaluate_action_steps_section_penalizes_short_vague_items() -> None:
    items = ["Trust him.", "Read it."]
    result = evaluate_action_steps_section(
        items,
        connector_phrase="From your time in stillness,",
        passage_reference="Habakkuk 2:1-4",
        be_still_prompts=["What are you waiting on God for?"],
    )
    assert result["score"] < 100
    assert result["metrics"]["short_item_count"] == 2
