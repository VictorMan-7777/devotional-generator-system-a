from __future__ import annotations

import json

from src.autoresearch.outliner_training_agent import (
    CORE_HARNESS_TEMPLATE,
    HarnessPassage,
    TRAINER_PROFILE,
    _reference_is_broad,
    build_revision_assignment,
    build_assignment_queue,
    evaluate_outline_artifact,
    OutlineTrainingAssignment,
    run_assignment_with_revision,
    run_outline_assignment,
    review_current_outliner_work,
)
from src.models.registry import AutoresearchExperimentRecord
from src.models.pipeline import (
    EditorialBuildArtifact,
    EditorialDayBriefRecord,
    EditorialDayPlanRow,
    EditorialWeekPlan,
    PassageResourceBundle,
    PassageResourceRecord,
)


def test_review_current_outliner_work_includes_trainer_profile(tmp_path) -> None:
    repo_root = tmp_path
    (repo_root / "outputs" / "devotionals").mkdir(parents=True)
    payload = review_current_outliner_work(repo_root)
    assert payload["trainer_profile"]["role"] == TRAINER_PROFILE["role"]
    assert payload["priority_weak_passages"]


def test_build_assignment_queue_starts_with_non_harness_shape(tmp_path, monkeypatch) -> None:
    repo_root = tmp_path
    (repo_root / "outputs" / "devotionals").mkdir(parents=True)
    monkeypatch.setattr(
        "src.autoresearch.outliner_training_agent._tried_outline_benchmarks",
        lambda: set(),
    )
    monkeypatch.setattr(
        "src.autoresearch.outliner_training_agent._latest_trainer_recommendations",
        lambda repo_root: [
            HarnessPassage("ruth-1", "Ruth 1", priority=10),
            HarnessPassage("mark-2", "Mark 2", priority=11),
        ],
    )
    monkeypatch.setattr(
        "src.autoresearch.outliner_training_agent._passage_is_deferred_for_now",
        lambda scripture_reference: False,
    )
    monkeypatch.setattr(
        "src.autoresearch.outliner_training_agent._recent_failure_count",
        lambda passage_slug: 0,
    )
    assignments = build_assignment_queue(repo_root, limit=2)
    assert len(assignments) == 2
    assert [item.passage for item in assignments] == ["Ruth 1", "Mark 2"]
    assert all(item.selection_stage == "trainer_selected_non_harness_coverage" for item in assignments)


def test_build_assignment_queue_expands_to_non_harness_passages_after_harness(tmp_path, monkeypatch) -> None:
    repo_root = tmp_path
    (repo_root / "outputs" / "devotionals").mkdir(parents=True)
    tried = {
        f"{slug}__{template}"
        for slug in (
            "genesis-1-2",
            "job-1-3",
            "matthew-1-2",
            "psalms-1-3",
            "ezekiel-37",
            "ezekiel-38-39",
            "genesis-12-13",
            "exodus-19-20",
            "proverbs-1-2",
            "psalms-23-25",
            "luke-15",
            "acts-9",
        )
        for template in ("6d_1w", "12d_2w", "18d_3w", "24d_4w", "30d_5w")
    }
    monkeypatch.setattr(
        "src.autoresearch.outliner_training_agent._tried_outline_benchmarks",
        lambda: tried,
    )
    monkeypatch.setattr(
        "src.autoresearch.outliner_training_agent._latest_trainer_recommendations",
        lambda repo_root: [HarnessPassage("ruth-1", "Ruth 1", priority=10)],
    )
    monkeypatch.setattr(
        "src.autoresearch.outliner_training_agent._passage_is_deferred_for_now",
        lambda scripture_reference: False,
    )
    monkeypatch.setattr(
        "src.autoresearch.outliner_training_agent._recent_failure_count",
        lambda passage_slug: 0,
    )
    assignments = build_assignment_queue(repo_root, limit=1)
    assert len(assignments) == 1
    assert assignments[0].passage == "Ruth 1"
    assert assignments[0].selection_stage == "trainer_selected_non_harness_coverage"


def test_build_assignment_queue_skips_deferred_passages(tmp_path, monkeypatch) -> None:
    repo_root = tmp_path
    (repo_root / "outputs" / "devotionals").mkdir(parents=True)
    monkeypatch.setattr(
        "src.autoresearch.outliner_training_agent._tried_outline_benchmarks",
        lambda: set(),
    )
    monkeypatch.setattr(
        "src.autoresearch.outliner_training_agent._latest_trainer_recommendations",
        lambda repo_root: [
            HarnessPassage("john-10", "John 10", priority=10),
            HarnessPassage("mark-2", "Mark 2", priority=11),
        ],
    )
    monkeypatch.setattr(
        "src.autoresearch.outliner_training_agent._passage_is_deferred_for_now",
        lambda scripture_reference: scripture_reference == "John 10",
    )
    assignments = build_assignment_queue(repo_root, limit=1)
    assert len(assignments) == 1
    assert assignments[0].passage == "Mark 2"


def test_build_assignment_queue_steps_down_after_repeated_failures(tmp_path, monkeypatch) -> None:
    repo_root = tmp_path
    (repo_root / "outputs" / "devotionals").mkdir(parents=True)
    monkeypatch.setattr(
        "src.autoresearch.outliner_training_agent._tried_outline_benchmarks",
        lambda: set(),
    )
    monkeypatch.setattr(
        "src.autoresearch.outliner_training_agent._latest_trainer_recommendations",
        lambda repo_root: [HarnessPassage("james-1", "James 1", priority=10)],
    )
    monkeypatch.setattr(
        "src.autoresearch.outliner_training_agent._passage_is_deferred_for_now",
        lambda scripture_reference: False,
    )
    monkeypatch.setattr(
        "src.autoresearch.outliner_training_agent._recent_failure_count",
        lambda passage_slug: 4,
    )
    assignments = build_assignment_queue(repo_root, limit=1)
    assert len(assignments) == 1
    assert assignments[0].num_days == 6
    assert assignments[0].num_weeks == 1
    assert assignments[0].selection_stage == "trainer_selected_easier_reset"
    assert assignments[0].teaching_method == "easier_passage_reset"


def test_evaluate_outline_artifact_flags_adjacent_duplicates() -> None:
    artifact = EditorialBuildArtifact(
        topic="Acts 9",
        num_days=2,
        source_reference="Acts 9",
        week_count=1,
        passage_resources=PassageResourceBundle(
            topic="Acts 9",
            scripture_reference="Acts 9",
            prepared_at_utc="2026-03-14T00:00:00Z",
        ),
        day_plan=[
            EditorialDayPlanRow(day_number=1, week_number=1, topic="Acts 9", scripture_reference="Acts 9:1-3", study_window_reference="Acts 9:1-3"),
            EditorialDayPlanRow(day_number=2, week_number=1, topic="Acts 9", scripture_reference="Acts 9:4-6", study_window_reference="Acts 9:4-6"),
        ],
        day_briefs=[
            EditorialDayBriefRecord(
                day_number=1,
                week_number=1,
                scripture_reference="Acts 9:1-3",
                study_window_reference="Acts 9:1-3",
                key_verse_reference="Acts 9:1-3",
                day_title="A",
                focus_clause="Same focus",
                pastoral_burden="Same burden",
                genre="narrative",
                scene_summary="One",
                theological_lane="Same lane",
                application_lane="App one",
                forbidden_drifts=[],
                key_terms=[],
            ),
            EditorialDayBriefRecord(
                day_number=2,
                week_number=1,
                scripture_reference="Acts 9:4-6",
                study_window_reference="Acts 9:4-6",
                key_verse_reference="Acts 9:4-6",
                day_title="B",
                focus_clause="Same focus",
                pastoral_burden="Same burden",
                genre="narrative",
                scene_summary="Two",
                theological_lane="Same lane",
                application_lane="App two",
                forbidden_drifts=[],
                key_terms=[],
            ),
        ],
        week_plans=[
            EditorialWeekPlan(
                week_number=1,
                title="Week 1",
                days=[1, 2],
                movement_summary="Moves from x toward y.",
            )
        ],
    )
    evaluation = evaluate_outline_artifact(artifact)
    assert evaluation["status"] in {"revise", "fail"}
    assert evaluation["metrics"]["adjacent_focus_duplicates"] == 1
    assert evaluation["metrics"]["adjacent_burden_duplicates"] == 1
    assert evaluation["metrics"]["adjacent_lane_duplicates"] == 1


def test_evaluate_outline_artifact_flags_broad_key_references() -> None:
    artifact = EditorialBuildArtifact(
        topic="Luke 15",
        num_days=1,
        source_reference="Luke 15",
        week_count=1,
        passage_resources=PassageResourceBundle(
            topic="Luke 15",
            scripture_reference="Luke 15",
            prepared_at_utc="2026-03-14T00:00:00Z",
        ),
        day_plan=[
            EditorialDayPlanRow(day_number=1, week_number=1, topic="Luke 15", scripture_reference="Luke 15:11-24", study_window_reference="Luke 15:11-24"),
        ],
        day_briefs=[
            EditorialDayBriefRecord(
                day_number=1,
                week_number=1,
                scripture_reference="Luke 15:11-24",
                study_window_reference="Luke 15:11-24",
                key_verse_reference="Luke 15:11-24",
                day_title="The Return",
                focus_clause="The father runs toward the returning son.",
                pastoral_burden="Return to the mercy of the Father.",
                genre="parable",
                scene_summary="The son comes home and is received with joy.",
                theological_lane="restoring mercy",
                application_lane="repentant return that trusts mercy more than self-atonement",
                forbidden_drifts=[],
                key_terms=[],
            ),
        ],
        week_plans=[
            EditorialWeekPlan(
                week_number=1,
                title="Week 1",
                days=[1],
                movement_summary="The lost are sought and welcomed home.",
            )
        ],
    )
    evaluation = evaluate_outline_artifact(artifact)
    assert evaluation["status"] in {"revise", "fail"}


def test_reference_is_broad_treats_two_verse_ranges_as_narrow() -> None:
    assert _reference_is_broad("Ruth 1:2-3") is False
    assert _reference_is_broad("Ruth 1:16-17") is False
    assert _reference_is_broad("Ruth 1:1-3") is True
    assert _reference_is_broad("Ruth 1") is True


def test_evaluate_outline_artifact_penalizes_generic_unanchored_language() -> None:
    artifact = EditorialBuildArtifact(
        topic="John 10",
        num_days=1,
        source_reference="John 10",
        week_count=1,
        passage_resources=PassageResourceBundle(
            topic="John 10",
            scripture_reference="John 10",
            prepared_at_utc="2026-03-16T00:00:00Z",
            shared_resources=[],
            outliner_resources=[],
            exposition_resources=[],
        ),
        day_plan=[
            EditorialDayPlanRow(day_number=1, week_number=1, topic="John 10", scripture_reference="John 10:11-12", study_window_reference="John 10:11-12"),
        ],
        day_briefs=[
            EditorialDayBriefRecord(
                day_number=1,
                week_number=1,
                scripture_reference="John 10:11-12",
                study_window_reference="John 10:11-12",
                key_verse_reference="John 10:11-12",
                day_title="The Shepherd",
                focus_clause="the good shepherd lays down his life",
                pastoral_burden="faithful response to God's word",
                genre="gospel_discourse",
                scene_summary="Jesus speaks as the shepherd.",
                theological_lane="faithful response to God's word",
                application_lane="faithful response shaped by faithful response to God's word",
                forbidden_drifts=[],
                key_terms=["good", "shepherd", "lays", "life"],
            ),
        ],
        week_plans=[
            EditorialWeekPlan(week_number=1, title="Week 1", days=[1], movement_summary="Moves forward."),
        ],
    )
    evaluation = evaluate_outline_artifact(artifact)
    assert evaluation["metrics"]["burden_unanchored"] == 1
    assert evaluation["metrics"]["lane_unanchored"] == 1
    assert evaluation["metrics"]["burden_generic_scaffolds"] == 1
    assert evaluation["metrics"]["lane_generic_scaffolds"] == 1
    assert evaluation["status"] in {"revise", "fail"}


def test_build_revision_assignment_uses_findings_as_coaching_focus() -> None:
    assignment = OutlineTrainingAssignment(
        assignment_id="ruth-1__6d_1w",
        passage="Ruth 1",
        passage_slug="ruth-1",
        num_days=6,
        num_weeks=1,
        rationale="Initial drill.",
        review_focus=("baseline",),
        selection_stage="trainer_selected_non_harness_coverage",
    )
    revised = build_revision_assignment(
        assignment,
        {
            "findings": [
                "Adjacent pastoral burdens repeated 2 time(s).",
                "Broad or unfocused key verse references appeared 3 time(s).",
            ]
        },
    )
    assert revised.teaching_method == "guided_revision"
    assert revised.revision_of_assignment_id == assignment.assignment_id
    assert revised.selection_stage == "trainer_guided_revision"
    assert revised.review_focus == (
        "Adjacent pastoral burdens repeated 2 time(s).",
        "Broad or unfocused key verse references appeared 3 time(s).",
    )


def test_build_revision_assignment_adds_expert_guidance_after_failures(tmp_path, monkeypatch) -> None:
    assignment = OutlineTrainingAssignment(
        assignment_id="john-10__6d_1w",
        passage="John 10",
        passage_slug="john-10",
        num_days=6,
        num_weeks=1,
        rationale="Initial drill.",
        review_focus=("baseline",),
        selection_stage="trainer_selected_non_harness_coverage",
    )
    output_dir = tmp_path / "docs" / "system" / "outputs"
    output_dir.mkdir(parents=True)
    (output_dir / "2026-03-16__devg__library-trainer-review.json").write_text(
        json.dumps(
            {
                "packet_summary": {"metadata_excerpt_count": 2, "weak_context_assignments": 0},
                "findings": [],
            }
        )
    )
    (output_dir / "2026-03-16__devg__theological-reviewer-report.json").write_text(
        json.dumps(
            {
                "findings": [
                    {"recommendation": "Keep the day burden inside the passage's real theological weight."}
                ]
            }
        )
    )
    monkeypatch.setattr(
        "src.autoresearch.outliner_training_agent._recent_failure_count",
        lambda passage_slug: 3,
    )

    revised = build_revision_assignment(
        assignment,
        {"findings": ["Adjacent day titles repeated 1 time(s)."]},
        repo_root=tmp_path,
    )

    assert "Adjacent day titles repeated 1 time(s)." in revised.review_focus
    assert "Use real explanatory cuttings, not metadata-shaped packet entries." in revised.review_focus
    assert "Keep the day burden inside the passage's real theological weight." in revised.review_focus


def test_run_assignment_with_revision_retries_after_fail(monkeypatch, tmp_path) -> None:
    assignment = OutlineTrainingAssignment(
        assignment_id="ruth-1__6d_1w",
        passage="Ruth 1",
        passage_slug="ruth-1",
        num_days=6,
        num_weeks=1,
        rationale="Initial drill.",
        review_focus=("baseline",),
        selection_stage="trainer_selected_non_harness_coverage",
    )
    calls: list[OutlineTrainingAssignment] = []

    def _fake_run_outline_assignment(current_assignment, *, repo_root, retriever=None):
        calls.append(current_assignment)
        status = "fail" if len(calls) == 1 else "pass"
        return {
            "assignment_id": current_assignment.assignment_id,
            "assignment": current_assignment,
            "evaluation": {
                "status": status,
                "score": 40 if status == "fail" else 90,
                "findings": ["Adjacent day titles repeated 1 time(s)."] if status == "fail" else [],
            },
        }

    monkeypatch.setattr(
        "src.autoresearch.outliner_training_agent.run_outline_assignment",
        _fake_run_outline_assignment,
    )

    result = run_assignment_with_revision(assignment, repo_root=tmp_path)

    assert len(calls) == 2
    assert calls[0].teaching_method == "standard_outline_drill"
    assert calls[1].teaching_method == "guided_revision"
    assert result["initial_attempt"]["evaluation"]["status"] == "fail"
    assert result["revision_attempt"]["evaluation"]["status"] == "pass"
    assert result["final_evaluation"]["status"] == "pass"


def test_run_outline_assignment_escalates_research_after_two_misses(tmp_path, monkeypatch) -> None:
    requested: list[dict[str, object]] = []
    logged: list[dict[str, object]] = []

    monkeypatch.setattr(
        "src.autoresearch.outliner_training_agent.list_experiments",
        lambda worker_name=None: [
            AutoresearchExperimentRecord(
                experiment_id="old-1",
                worker_name="outliner",
                benchmark_name="outline-only-6d_1w",
                benchmark_reference="ruth-1",
                run_slug="",
                status="fail",
                attempted_change="",
                metrics_json=json.dumps({"score": 40}),
                learning_note="",
                keep_decision="review",
                created_at_utc="2026-03-16T00:00:00Z",
                completed_at_utc="2026-03-16T00:01:00Z",
            ),
            AutoresearchExperimentRecord(
                experiment_id="old-2",
                worker_name="outliner",
                benchmark_name="outline-only-12d_2w",
                benchmark_reference="ruth-1",
                run_slug="",
                status="revise",
                attempted_change="",
                metrics_json=json.dumps({"score": 60}),
                learning_note="",
                keep_decision="review",
                created_at_utc="2026-03-16T00:02:00Z",
                completed_at_utc="2026-03-16T00:03:00Z",
            ),
        ],
    )
    monkeypatch.setattr(
        "src.autoresearch.outliner_training_agent._tried_outline_benchmarks",
        lambda: set(),
    )
    monkeypatch.setattr(
        "src.autoresearch.outliner_training_agent._latest_trainer_recommendations",
        lambda repo_root: [HarnessPassage("ruth-1", "Ruth 1", priority=10)],
    )
    monkeypatch.setattr(
        "src.autoresearch.outliner_training_agent.list_resource_acquisition_requests",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        "src.autoresearch.outliner_training_agent.request_resource_acquisition",
        lambda **kwargs: requested.append(kwargs),
    )
    monkeypatch.setattr(
        "src.autoresearch.outliner_training_agent.log_experiment",
        lambda **kwargs: logged.append(kwargs),
    )
    monkeypatch.setattr(
        "src.autoresearch.outliner_training_agent.suggest_study_window_size",
        lambda **kwargs: 5,
    )
    monkeypatch.setattr(
        "src.autoresearch.outliner_training_agent.plan_scripture_day_references",
        lambda **kwargs: ["Ruth 1:1-5"],
    )
    _dummy_resource = PassageResourceRecord(source_title="Test Resource", purpose="outliner")
    monkeypatch.setattr(
        "src.autoresearch.outliner_training_agent.prepare_passage_resource_bundle",
        lambda **kwargs: PassageResourceBundle(
            topic="Ruth 1",
            scripture_reference="Ruth 1",
            prepared_at_utc="2026-03-16T00:00:00Z",
            shared_resources=[_dummy_resource, _dummy_resource],
            outliner_resources=[_dummy_resource, _dummy_resource],
            exposition_resources=[],
        ),
    )
    monkeypatch.setattr(
        "src.autoresearch.outliner_training_agent.select_daily_key_verses_reference",
        lambda **kwargs: "Ruth 1:1-2",
    )
    monkeypatch.setattr(
        "src.autoresearch.outliner_training_agent.build_outline_artifact",
        lambda **kwargs: EditorialBuildArtifact(
            topic="Ruth 1",
            num_days=1,
            source_reference="Ruth 1",
            week_count=1,
            passage_resources=kwargs["passage_resources"],
            day_plan=[
                EditorialDayPlanRow(
                    day_number=1,
                    week_number=1,
                    topic="Ruth 1",
                    scripture_reference="Ruth 1:1-2",
                    study_window_reference="Ruth 1:1-5",
                )
            ],
            day_briefs=[
                EditorialDayBriefRecord(
                    day_number=1,
                    week_number=1,
                    scripture_reference="Ruth 1:1-2",
                    study_window_reference="Ruth 1:1-5",
                    key_verse_reference="Ruth 1:1-2",
                    day_title="Empty Hands",
                    focus_clause="Naomi begins in grief.",
                    pastoral_burden="Name grief honestly before the Lord.",
                    genre="narrative",
                    scene_summary="Naomi is emptied and on the road.",
                    theological_lane="honest lament",
                    application_lane="bring grief into honest prayer",
                    forbidden_drifts=[],
                    key_terms=[],
                )
            ],
            week_plans=[
                EditorialWeekPlan(
                    week_number=1,
                    title="Week 1",
                    days=[1],
                    movement_summary="A family enters loss and uncertainty.",
                )
            ],
        ),
    )

    monkeypatch.setattr(
        "src.autoresearch.outliner_training_agent._scripture_text",
        lambda retriever, reference: "dummy text",
    )

    class DummyRetriever:
        pass

    assignment = build_assignment_queue(tmp_path, limit=1)[0]
    result = run_outline_assignment(assignment, repo_root=tmp_path, retriever=DummyRetriever())

    assert result["research_escalated"] is True
    assert requested
    assert requested[0]["requested_by"] == "outliner"
    assert requested[0]["scripture_reference"] == "Ruth 1"
    assert logged
    assert logged[0]["created_at_utc"]
    assert logged[0]["completed_at_utc"]
