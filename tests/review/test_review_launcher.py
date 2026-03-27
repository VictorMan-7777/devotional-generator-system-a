from __future__ import annotations

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "review" / "run_review.py"
_SPEC = spec_from_file_location("run_review", _SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
run_review = module_from_spec(_SPEC)
sys.modules[_SPEC.name] = run_review
_SPEC.loader.exec_module(run_review)


def test_launcher_defaults_to_ui(monkeypatch) -> None:
    captured: dict[str, list[str]] = {}

    def fake_ui_main(argv):
        captured["argv"] = argv
        return 0

    monkeypatch.setattr(run_review.run_review_ui, "main", fake_ui_main)
    rc = run_review.main(["--report", "r.json"])
    assert rc == 0
    assert captured["argv"] == ["--report", "r.json", "--reviewed-by", "Victor"]


def test_launcher_cli_backend(monkeypatch) -> None:
    captured: dict[str, list[str]] = {}

    def fake_cli_main(argv):
        captured["argv"] = argv
        return 0

    monkeypatch.setattr(run_review.run_pending_approvals, "main", fake_cli_main)
    rc = run_review.main(["--report", "r.json", "--backend", "cli", "--reset"])
    assert rc == 0
    assert captured["argv"] == [
        "--report",
        "r.json",
        "--reset",
        "--reviewed-by",
        "Victor",
        "--mode",
        "interactive",
    ]


def test_launcher_approve_all_backend(monkeypatch) -> None:
    captured: dict[str, list[str]] = {}

    def fake_cli_main(argv):
        captured["argv"] = argv
        return 0

    monkeypatch.setattr(run_review.run_pending_approvals, "main", fake_cli_main)
    rc = run_review.main(["--report", "r.json", "--backend", "approve-all", "--out", "d.json"])
    assert rc == 0
    assert captured["argv"] == [
        "--report",
        "r.json",
        "--out",
        "d.json",
        "--reviewed-by",
        "Victor",
        "--mode",
        "approve-all",
    ]


def test_launcher_forwards_custom_reviewer(monkeypatch) -> None:
    captured: dict[str, list[str]] = {}

    def fake_cli_main(argv):
        captured["argv"] = argv
        return 0

    monkeypatch.setattr(run_review.run_pending_approvals, "main", fake_cli_main)
    rc = run_review.main(
        ["--report", "r.json", "--backend", "reject-all", "--reviewed-by", "operator"]
    )
    assert rc == 0
    assert "--reviewed-by" in captured["argv"]
    idx = captured["argv"].index("--reviewed-by")
    assert captured["argv"][idx + 1] == "operator"


def test_launcher_forwards_allow_batch_approve(monkeypatch) -> None:
    captured: dict[str, list[str]] = {}

    def fake_cli_main(argv):
        captured["argv"] = argv
        return 0

    monkeypatch.setattr(run_review.run_pending_approvals, "main", fake_cli_main)
    rc = run_review.main(
        [
            "--report",
            "r.json",
            "--backend",
            "approve-all",
            "--allow-batch-approve",
        ]
    )
    assert rc == 0
    assert "--allow-batch-approve" in captured["argv"]


def test_launcher_web_backend(monkeypatch) -> None:
    captured: dict[str, list[str]] = {}

    def fake_web_main(argv):
        captured["argv"] = argv
        return 0

    monkeypatch.setattr(run_review.run_review_web, "main", fake_web_main)
    rc = run_review.main(
        [
            "--backend",
            "web",
            "--report",
            "r.json",
            "--host",
            "127.0.0.1",
            "--port",
            "9001",
            "--no-open",
            "--reviewed-by",
            "Victor",
        ]
    )
    assert rc == 0
    assert captured["argv"] == [
        "--report",
        "r.json",
        "--host",
        "127.0.0.1",
        "--port",
        "9001",
        "--reviewed-by",
        "Victor",
        "--no-open",
    ]
