from __future__ import annotations

from src.autoresearch.workers import get_worker_spec, list_worker_specs


def test_list_worker_specs_contains_expected_workers() -> None:
    names = {spec.name for spec in list_worker_specs()}
    assert {
        "training_manager",
        "acquisition_librarian",
        "research_librarian",
        "outliner",
        "exposition_writer",
        "quote_selector",
        "policy_guardian",
        "grammar_advisor",
        "passage_researcher",
        "be_still_writer",
        "action_writer",
        "prayer_writer",
        "pdf_art_director",
        "pdf_layout_engineer",
    }.issubset(names)


def test_get_worker_spec_for_acquisition_librarian_has_acquisition_metrics() -> None:
    spec = get_worker_spec("acquisition_librarian")
    refs = {benchmark.reference for benchmark in spec.benchmark_passages}
    assert "Habakkuk 1-3" in refs
    assert "acquisition_fulfillment_rate" in spec.objective_metrics
    assert spec.idle_duties


def test_get_worker_spec_for_training_manager_has_range_metrics() -> None:
    spec = get_worker_spec("training_manager")
    refs = {benchmark.reference for benchmark in spec.benchmark_passages}
    assert "Luke 15" in refs
    assert "training_cycle_completion_rate" in spec.objective_metrics
    assert spec.idle_duties


def test_get_worker_spec_for_research_librarian_has_shared_bundle_metrics() -> None:
    spec = get_worker_spec("research_librarian")
    refs = {benchmark.reference for benchmark in spec.benchmark_passages}
    assert "Colossians 3-4" in refs
    assert "shared_bundle_helpfulness_rate" in spec.objective_metrics
    assert spec.idle_duties


def test_get_worker_spec_for_outliner_has_expected_benchmarks() -> None:
    spec = get_worker_spec("outliner")
    refs = {benchmark.reference for benchmark in spec.benchmark_passages}
    assert "Exodus 19-20" in refs
    assert "Habakkuk 1-3" in refs
    assert "BOOK_DAY_PROGRESS" in spec.objective_metrics
    assert spec.debate_role


def test_get_worker_spec_for_prayer_writer_has_prophetic_benchmark() -> None:
    spec = get_worker_spec("prayer_writer")
    refs = {benchmark.reference for benchmark in spec.benchmark_passages}
    assert "Ezekiel 38-39" in refs
    assert "theological_boundary_pass_rate" in spec.objective_metrics


def test_get_worker_spec_alias_for_exposition_retriever_points_to_passage_researcher() -> None:
    spec = get_worker_spec("exposition_retriever")
    assert spec.name == "passage_researcher"


def test_get_worker_spec_for_pdf_workers_have_expected_metrics() -> None:
    art = get_worker_spec("pdf_art_director")
    layout = get_worker_spec("pdf_layout_engineer")
    assert "title_page_quality" in art.objective_metrics
    assert "Psalms 23-25" in {benchmark.reference for benchmark in art.benchmark_passages}
    assert "kdp_margin_compliance" in layout.objective_metrics
    assert "Exodus 19-20" in {benchmark.reference for benchmark in layout.benchmark_passages}


def test_get_worker_spec_for_policy_guardian_has_guardrail_metrics() -> None:
    spec = get_worker_spec("policy_guardian")
    refs = {benchmark.reference for benchmark in spec.benchmark_passages}
    assert "Luke 15" in refs
    assert "crutch_detection_rate" in spec.objective_metrics
