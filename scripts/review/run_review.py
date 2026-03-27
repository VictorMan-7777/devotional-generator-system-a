from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.review import run_pending_approvals, run_review_ui, run_review_web


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Review pending approvals. Defaults to UI mode."
    )
    parser.add_argument("--report", required=True, help="Path to approval-gate report JSON")
    parser.add_argument("--out", help="Output decisions JSON path")
    parser.add_argument(
        "--backend",
        choices=["ui", "web", "cli", "approve-all", "reject-all"],
        default="ui",
        help="Review backend: desktop UI default, web UI, or CLI/batch fallback.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Ignore existing decisions file and start this report from scratch.",
    )
    parser.add_argument(
        "--reviewed-by",
        default=run_pending_approvals.default_reviewed_by(),
        help="Reviewer identifier stored in decision metadata.",
    )
    parser.add_argument(
        "--decision-source",
        help=(
            "Decision provenance label. Required when --reviewed-by starts with 'agent:'. "
            "For humans this is optional."
        ),
    )
    parser.add_argument(
        "--allow-batch-approve",
        action="store_true",
        help="Enable --backend approve-all (debug-only).",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host bind address for web backend.")
    parser.add_argument("--port", type=int, default=8765, help="Port bind address for web backend.")
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Do not auto-open browser when using web backend.",
    )
    args = parser.parse_args(argv)

    if args.backend == "ui":
        ui_args = ["--report", args.report]
        if args.out:
            ui_args.extend(["--out", args.out])
        if args.reset:
            ui_args.append("--reset")
        ui_args.extend(["--reviewed-by", args.reviewed_by])
        if args.decision_source:
            ui_args.extend(["--decision-source", args.decision_source])
        return run_review_ui.main(ui_args)
    if args.backend == "web":
        web_args = ["--report", args.report, "--host", args.host, "--port", str(args.port)]
        if args.out:
            web_args.extend(["--out", args.out])
        if args.reset:
            web_args.append("--reset")
        web_args.extend(["--reviewed-by", args.reviewed_by])
        if args.decision_source:
            web_args.extend(["--decision-source", args.decision_source])
        if args.no_open:
            web_args.append("--no-open")
        return run_review_web.main(web_args)

    cli_args = ["--report", args.report]
    if args.out:
        cli_args.extend(["--out", args.out])
    if args.reset:
        cli_args.append("--reset")
    cli_args.extend(["--reviewed-by", args.reviewed_by])
    if args.decision_source:
        cli_args.extend(["--decision-source", args.decision_source])
    if args.backend == "cli":
        cli_args.extend(["--mode", "interactive"])
    elif args.backend == "approve-all":
        if args.allow_batch_approve:
            cli_args.append("--allow-batch-approve")
        cli_args.extend(["--mode", "approve-all"])
    else:
        cli_args.extend(["--mode", "reject-all"])
    return run_pending_approvals.main(cli_args)


if __name__ == "__main__":
    raise SystemExit(main())
