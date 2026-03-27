from __future__ import annotations

import argparse
from datetime import datetime, timezone

from src.autoresearch.store import log_experiment


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Log a DevG autoresearch worker experiment.")
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--worker-name", required=True)
    parser.add_argument("--benchmark-name", required=True)
    parser.add_argument("--benchmark-reference", default="")
    parser.add_argument("--run-slug", default="")
    parser.add_argument("--status", default="")
    parser.add_argument("--attempted-change", default="")
    parser.add_argument("--learning-note", default="")
    parser.add_argument("--keep-decision", default="")
    parser.add_argument("--created-at-utc", default="")
    parser.add_argument("--completed-at-utc", default="")
    parser.add_argument("--metric", action="append", default=[], help="Repeatable key=value metric payload")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    metrics: dict[str, str] = {}
    for item in args.metric:
        if "=" not in item:
            raise SystemExit(f"Invalid --metric '{item}'. Expected key=value")
        key, value = item.split("=", 1)
        metrics[key.strip()] = value.strip()
    rec = log_experiment(
        experiment_id=args.experiment_id,
        worker_name=args.worker_name,
        benchmark_name=args.benchmark_name,
        benchmark_reference=args.benchmark_reference,
        run_slug=args.run_slug,
        status=args.status,
        attempted_change=args.attempted_change,
        metrics=metrics,
        learning_note=args.learning_note,
        keep_decision=args.keep_decision,
        created_at_utc=args.created_at_utc or _utc_now(),
        completed_at_utc=args.completed_at_utc or _utc_now(),
    )
    print(f"logged {rec.experiment_id} worker={rec.worker_name} benchmark={rec.benchmark_name} status={rec.status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
