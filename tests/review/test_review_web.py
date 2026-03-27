from __future__ import annotations

import json
import sys
import threading
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "review" / "run_review_web.py"
_SPEC = spec_from_file_location("run_review_web", _SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
run_review_web = module_from_spec(_SPEC)
sys.modules[_SPEC.name] = run_review_web
_SPEC.loader.exec_module(run_review_web)


def test_web_action_reject_advances_to_next_item(tmp_path: Path) -> None:
    report_path = tmp_path / "approval-gate-report.json"
    out_path = tmp_path / "approval-decisions.json"
    report_path.write_text(
        json.dumps(
            {
                "topic": "Genesis 1-2",
                "days": 2,
                "pending_sections": ["day 1 — title", "day 2 — exposition"],
                "section_previews_by_key": {
                    "2:exposition": "Preview exposition text.",
                },
            }
        ),
        encoding="utf-8",
    )

    state = run_review_web.WebReviewState(
        report_path=report_path,
        output_path=out_path,
        reviewed_by="Victor",
        decision_source=None,
        reset=True,
    )

    result: dict[str, dict] = {}
    error: dict[str, Exception] = {}

    def do_reject() -> None:
        try:
            result["payload"] = state.apply_action("reject")
        except Exception as exc:  # pragma: no cover
            error["exc"] = exc

    t = threading.Thread(target=do_reject, daemon=True)
    t.start()
    t.join(1.0)

    assert not t.is_alive(), "apply_action should not deadlock"
    assert "exc" not in error
    payload = result["payload"]
    assert payload["remaining_count"] == 1
    assert payload["current"]["day"] == 2
    assert payload["current"]["section"] == "exposition"
    assert payload["current"]["section_label"] == "Exposition"
    assert payload["current"]["source_preview"] == "Preview exposition text."


def test_web_html_supports_dark_mode() -> None:
    html = run_review_web._html_page()
    assert "prefers-color-scheme: dark" in html
    assert "color-scheme: light dark" in html
