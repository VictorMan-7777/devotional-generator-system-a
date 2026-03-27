from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.run_scripture_harness import (
    HarnessCase,
    _build_outline_csv,
    _parse_run_stdout,
    _week_assignments,
)


def test_build_outline_csv_creates_12_day_two_week_outline(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "scripts.run_scripture_harness.plan_scripture_day_references",
        lambda reference, num_days, max_verses_per_day=5: [
            f"Job 1:{idx}" for idx in range(1, num_days + 1)
        ],
    )
    csv_path = _build_outline_csv(
        HarnessCase(slug="job-1-3__12d_2w", passage="Job 1-3", num_days=12, num_weeks=2),
        output_dir=tmp_path,
    )

    lines = csv_path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "Day,Week,Attribute,Scripture,Theme/Focus,Notes,Status"
    assert len(lines) == 13
    assert lines[1].startswith("1,1,Job 1-3,")
    assert lines[7].startswith("7,1,Job 1-3,")
    assert lines[8].startswith("8,2,Job 1-3,")


def test_week_assignments_keep_period_data_on_the_case() -> None:
    assert _week_assignments(12, 2) == [1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2]
    assert _week_assignments(14, 3) == [1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 3]


def test_parse_run_stdout_extracts_uppercase_key_value_lines() -> None:
    parsed = _parse_run_stdout(
        "\n".join(
            [
                "RUN_SLUG=example-run",
                "BOOK_JSON=outputs/devotionals/example__book.json",
                "ignored line",
                "lowercase=value",
            ]
        )
    )

    assert parsed == {
        "RUN_SLUG": "example-run",
        "BOOK_JSON": "outputs/devotionals/example__book.json",
    }
