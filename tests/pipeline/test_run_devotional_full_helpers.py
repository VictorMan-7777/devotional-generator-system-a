from __future__ import annotations

from scripts.run_devotional_full import (
    _attach_audit_meta_to_approval_report,
    _build_registry_socket,
    _build_standard_day_plan,
    _build_child_scripture_plan,
    _build_second_eyes_review_packet,
    _week_assignments,
)


def test_build_child_scripture_plan_avoids_parent_week_refs(monkeypatch) -> None:
    refs = [
        "Genesis 1:1-3",
        "Genesis 1:4-5",
        "Genesis 1:6-8",
        "Genesis 1:9-11",
        "Genesis 1:12-14",
        "Genesis 1:15-17",
        "Genesis 1:18-20",
        "Genesis 1:21-23",
    ]

    def _fake_plan(**kwargs):
        return refs

    monkeypatch.setattr("scripts.run_devotional_full.plan_scripture_day_references", _fake_plan)
    monkeypatch.setattr("scripts.run_devotional_full.suggest_study_window_size", lambda **kwargs: 5)
    plan = _build_child_scripture_plan(
        reference_seed="Genesis 1",
        num_days=2,
        week_by_day={1: 1, 2: 1},
        parent_week_refs={1: {"Genesis 1:1-3"}},
    )
    picked = {entry["scripture_reference"] for entry in plan}
    assert "Genesis 1:1-3" not in {entry["study_window_reference"] for entry in plan}
    assert len(picked) == 2
    assert all("study_window_reference" in entry for entry in plan)
    assert all(entry["study_window_reference"] for entry in plan)


def test_attach_audit_meta_to_approval_report_merges_fields() -> None:
    report = {"section_meta_by_key": {"1:scripture": {"existing": "ok"}}}
    bundle = {
        "entries": [
            {
                "section_key": "day-1:scripture",
                "day_number": 1,
                "section": "scripture",
                "validator_source": "api_bible",
                "validator_status": "passed",
                "validator_discrepancy": False,
                "retrieval_reference": "Genesis 1:1-3",
                "retrieved_at_utc": "2026-03-09T00:00:00+00:00",
                "grounding_map_id": "",
                "prayer_trace_map_id": "",
            }
        ]
    }
    _attach_audit_meta_to_approval_report(report, bundle)
    meta = report["section_meta_by_key"]["1:scripture"]
    assert meta["existing"] == "ok"
    assert meta["section_key"] == "day-1:scripture"
    assert meta["validator_source"] == "api_bible"


def test_build_registry_socket_uses_memory_for_standalone(tmp_path) -> None:
    socket_a = _build_registry_socket(
        db_path=tmp_path / "persist.db",
        standalone_volume=True,
    )
    socket_a.create_series("s1")
    socket_a.create_volume("v1", "s1", 1)

    socket_b = _build_registry_socket(
        db_path=tmp_path / "persist.db",
        standalone_volume=True,
    )
    assert socket_b.get_volume_by_number("s1", 1) is None


def test_build_registry_socket_uses_sqlite_file_for_series_runs(tmp_path) -> None:
    db = tmp_path / "persist.db"
    socket_a = _build_registry_socket(
        db_path=db,
        standalone_volume=False,
    )
    socket_a.create_series("s1")
    socket_a.create_volume("v1", "s1", 1)

    socket_b = _build_registry_socket(
        db_path=db,
        standalone_volume=False,
    )
    assert socket_b.get_volume_by_number("s1", 1) is not None


def test_build_second_eyes_review_packet_contains_human_review_days() -> None:
    packet = _build_second_eyes_review_packet(
        run_slug="run-123",
        topic="Exodus 19-20",
        validation_summary={
            "total_checks": 10,
            "passed": 7,
            "failed": 3,
            "rewrite_events": [
                {
                    "day_number": None,
                    "attempt_number": 2,
                    "signal": "human_review",
                    "failed_check_ids": ["BOOK_DAY_PROGRESS"],
                    "scope": "book",
                    "target_day_numbers": [3, 4],
                }
            ],
        },
        editorial_build_payload={
            "day_briefs": [
                {},
                {},
                {
                    "scripture_reference": "Exodus 19:9-12",
                    "focus_clause": "Then Moses told the words of the people to the Lord",
                    "pastoral_burden": "truthfulness under pressure",
                    "theological_lane": "truthfulness under pressure",
                    "application_lane": "concrete obedience under the authority of the passage",
                    "forbidden_drifts": ["generic encouragement detached from the scene"],
                },
                {
                    "scripture_reference": "Exodus 19:13-17",
                    "focus_clause": "Moses brought the people out of the camp to meet God",
                    "pastoral_burden": "prepared reverence before holy encounter",
                    "theological_lane": "holy encounter under consecrated fear",
                    "application_lane": "prepared reverence before God's holy presence",
                    "forbidden_drifts": ["generic encouragement detached from the scene"],
                },
            ]
        },
        book_payload={
            "days": [
                {},
                {},
                {
                    "day_focus": "Exodus 19:9-12 - Then Moses told the words of the people to the Lord",
                    "scripture": {"reference": "Exodus 19:9-12"},
                    "exposition": {"text": "Exposition text for day three."},
                    "action_steps": {"items": ["Step one", "Step two"]},
                    "prayer": {"text": "Prayer text for day three."},
                },
                {
                    "day_focus": "Exodus 19:13-17 - Moses brought the people out of the camp to meet God",
                    "scripture": {"reference": "Exodus 19:13-17"},
                    "exposition": {"text": "Exposition text for day four."},
                    "action_steps": {"items": ["Step three", "Step four"]},
                    "prayer": {"text": "Prayer text for day four."},
                },
            ]
        },
    )
    assert "DevG Second-Eyes Review Packet" in packet
    assert "Run slug: `run-123`" in packet
    assert "### Day 3" in packet
    assert "Exodus 19:9-12" in packet
    assert "BOOK_DAY_PROGRESS" in packet


def test_week_assignments_distributes_days_across_weeks() -> None:
    assert _week_assignments(12, 2) == [1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2]


def test_build_standard_day_plan_uses_generated_references(monkeypatch) -> None:
    refs = ["Habakkuk 1:1-4", "Habakkuk 1:5-7", "Habakkuk 1:8-11", "Habakkuk 1:12-17"]

    def _fake_plan(**kwargs):
        return refs

    monkeypatch.setattr("scripts.run_devotional_full.plan_scripture_day_references", _fake_plan)
    monkeypatch.setattr("scripts.run_devotional_full.suggest_study_window_size", lambda **kwargs: 5)
    plan = _build_standard_day_plan(
        reference="Habakkuk 1-3",
        num_days=4,
        num_weeks=2,
        topic="Habakkuk 1-3",
    )
    assert [row["study_window_reference"] for row in plan] == refs
    assert [row["scripture_reference"] for row in plan] == [
        "Habakkuk 1:2-3",
        "Habakkuk 1:6-7",
        "Habakkuk 1:9-10",
        "Habakkuk 1:14-15",
    ]
    assert [row["week_number"] for row in plan] == ["1", "1", "2", "2"]
    assert all(row["topic"] == "Habakkuk 1-3" for row in plan)
