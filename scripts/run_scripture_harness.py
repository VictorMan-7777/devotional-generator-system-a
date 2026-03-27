from __future__ import annotations

import argparse
import contextlib
import csv
import json
import io
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import time

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.scripture.planner import plan_scripture_day_references  # noqa: E402
from src.persistence.paths import default_registry_db_path  # noqa: E402
from src.rag.sqlite_catalog import bootstrap_catalog_tables  # noqa: E402
from src.rag.research_memory import store_outline_research  # noqa: E402
from src.validation.failure_remedies import remedy_suggestions  # noqa: E402
from scripts.clean_regenerate_run import main as clean_regenerate_run_main  # noqa: E402
from scripts.run_devotional_full import main as run_devotional_full_main  # noqa: E402


@dataclass(frozen=True)
class HarnessCase:
    slug: str
    passage: str
    num_days: int
    num_weeks: int


HARNESS_SET_A: tuple[HarnessCase, ...] = (
    HarnessCase(slug="genesis-1-2__12d_2w", passage="Genesis 1-2", num_days=12, num_weeks=2),
    HarnessCase(slug="job-1-3__12d_2w", passage="Job 1-3", num_days=12, num_weeks=2),
    HarnessCase(slug="matthew-1-2__12d_2w", passage="Matthew 1-2", num_days=12, num_weeks=2),
    HarnessCase(slug="psalms-1-3__12d_2w", passage="Psalms 1-3", num_days=12, num_weeks=2),
    HarnessCase(slug="ezekiel-37__12d_2w", passage="Ezekiel 37", num_days=12, num_weeks=2),
    HarnessCase(slug="ezekiel-38-39__12d_2w", passage="Ezekiel 38-39", num_days=12, num_weeks=2),
)

HARNESS_SET_B: tuple[HarnessCase, ...] = (
    HarnessCase(slug="genesis-12-13__12d_2w", passage="Genesis 12-13", num_days=12, num_weeks=2),
    HarnessCase(slug="exodus-19-20__12d_2w", passage="Exodus 19-20", num_days=12, num_weeks=2),
    HarnessCase(slug="proverbs-1-2__12d_2w", passage="Proverbs 1-2", num_days=12, num_weeks=2),
    HarnessCase(slug="psalms-23-25__12d_2w", passage="Psalms 23-25", num_days=12, num_weeks=2),
    HarnessCase(slug="luke-15__12d_2w", passage="Luke 15", num_days=12, num_weeks=2),
    HarnessCase(slug="acts-9__12d_2w", passage="Acts 9", num_days=12, num_weeks=2),
)

HARNESS_SETS: dict[str, tuple[HarnessCase, ...]] = {
    "a": HARNESS_SET_A,
    "b": HARNESS_SET_B,
}

DEFAULT_CASES: tuple[HarnessCase, ...] = HARNESS_SET_A
_DEFAULT_QUOTE_SEED = Path(__file__).resolve().parents[1] / "data" / "quotes" / "seed-quotes.json"
_DEFAULT_EXCERPT_SEED = Path(__file__).resolve().parents[1] / "data" / "excerpts" / "seed-excerpts.json"

_CURATED_HARNESS_OUTLINES: dict[str, list[dict[str, str | int]]] = {
    "exodus-19-20__12d_2w": [
        {"day": 1, "week": 1, "reference": "Exodus 19:1-4", "focus": "Remembered mercy before covenant demand"},
        {"day": 2, "week": 1, "reference": "Exodus 19:5-8", "focus": "Covenant identity received through obedience"},
        {"day": 3, "week": 1, "reference": "Exodus 19:9-13", "focus": "Consecration and holy boundaries"},
        {"day": 4, "week": 1, "reference": "Exodus 19:14-19", "focus": "Meeting God with trembling reverence"},
        {"day": 5, "week": 1, "reference": "Exodus 19:20-25", "focus": "Nearness without presumption"},
        {"day": 6, "week": 1, "reference": "Exodus 20:1-3", "focus": "Exclusive worship under holy authority"},
        {"day": 7, "week": 1, "reference": "Exodus 20:4-6", "focus": "Rejecting false worship on the way to gathered worship"},
        {"day": 8, "week": 2, "reference": "Exodus 20:7-11", "focus": "Reverent speech and sabbath-shaped life"},
        {"day": 9, "week": 2, "reference": "Exodus 20:12-14", "focus": "Holy obedience in family and neighbor life"},
        {"day": 10, "week": 2, "reference": "Exodus 20:15-17", "focus": "Truthful desire and neighborly integrity"},
        {"day": 11, "week": 2, "reference": "Exodus 20:18-21", "focus": "Fear, distance, and mediated nearness"},
        {"day": 12, "week": 2, "reference": "Exodus 20:22-26", "focus": "Worship ordered by God's own terms"},
    ],
    "proverbs-1-2__12d_2w": [
        {"day": 1, "week": 1, "reference": "Proverbs 1:1-7", "focus": "Wisdom begins in the fear of the Lord"},
        {"day": 2, "week": 1, "reference": "Proverbs 1:8-13", "focus": "Refusing the first pull of sinful company"},
        {"day": 3, "week": 1, "reference": "Proverbs 1:14-19", "focus": "Seeing where violent greed finally leads"},
        {"day": 4, "week": 1, "reference": "Proverbs 1:20-23", "focus": "Hearing wisdom's public call"},
        {"day": 5, "week": 1, "reference": "Proverbs 1:24-28", "focus": "The cost of refusing wisdom's warning"},
        {"day": 6, "week": 1, "reference": "Proverbs 1:29-33", "focus": "Security for the one who listens"},
        {"day": 7, "week": 1, "reference": "Proverbs 2:1-5", "focus": "Seeking wisdom like hidden treasure for gathered worship"},
        {"day": 8, "week": 2, "reference": "Proverbs 2:6-8", "focus": "Wisdom given and guarded by the Lord"},
        {"day": 9, "week": 2, "reference": "Proverbs 2:9-11", "focus": "Discernment shaping the whole path"},
        {"day": 10, "week": 2, "reference": "Proverbs 2:12-15", "focus": "Delivered from crooked speech and paths"},
        {"day": 11, "week": 2, "reference": "Proverbs 2:16-19", "focus": "Delivered from seductive unfaithfulness"},
        {"day": 12, "week": 2, "reference": "Proverbs 2:20-22", "focus": "Walking with the upright to the end"},
    ],
    "acts-9__12d_2w": [
        {"day": 1, "week": 1, "reference": "Acts 9:1-3", "focus": "Hostile zeal on the road to Damascus"},
        {"day": 2, "week": 1, "reference": "Acts 9:4-6", "focus": "Confronted directly by the risen Lord"},
        {"day": 3, "week": 1, "reference": "Acts 9:7-9", "focus": "Helplessness after proud certainty"},
        {"day": 4, "week": 1, "reference": "Acts 9:10-12", "focus": "Ananias summoned into costly obedience"},
        {"day": 5, "week": 1, "reference": "Acts 9:13-16", "focus": "Mercy for the least expected person"},
        {"day": 6, "week": 1, "reference": "Acts 9:17-19", "focus": "Restored sight and received fellowship"},
        {"day": 7, "week": 1, "reference": "Acts 9:20-22", "focus": "New allegiance becoming public witness"},
        {"day": 8, "week": 2, "reference": "Acts 9:23-25", "focus": "Preserved through danger and opposition"},
        {"day": 9, "week": 2, "reference": "Acts 9:26-31", "focus": "The church strengthened in holy peace"},
        {"day": 10, "week": 2, "reference": "Acts 9:32-35", "focus": "Healing that turns hearts toward the Lord"},
        {"day": 11, "week": 2, "reference": "Acts 9:36-39", "focus": "Mercy remembered in a grieving community"},
        {"day": 12, "week": 2, "reference": "Acts 9:40-43", "focus": "Resurrection mercy and ordinary readiness"},
    ],
}


def _week_assignments(num_days: int, num_weeks: int) -> list[int]:
    if num_days <= 0 or num_weeks <= 0:
        raise ValueError("num_days and num_weeks must be > 0")
    if num_weeks > num_days:
        raise ValueError("num_weeks cannot exceed num_days")

    sizes = [1 for _ in range(num_weeks)]
    remaining = num_days - num_weeks
    while remaining > 0:
        advanced = False
        for idx in range(num_weeks):
            while remaining > 0 and sizes[idx] < 7:
                sizes[idx] += 1
                remaining -= 1
                advanced = True
            if remaining <= 0:
                break
        if not advanced:
            for idx in range(num_weeks):
                if remaining <= 0:
                    break
                sizes[idx] += 1
                remaining -= 1

    assignments: list[int] = []
    for week_number, size in enumerate(sizes, start=1):
        assignments.extend([week_number] * size)
    return assignments


def _day_focus_label(reference: str, day_number: int) -> str:
    normalized = " ".join(reference.split())
    return f"Day {day_number} focus | {normalized}"


def _build_outline_csv(case: HarnessCase, *, output_dir: Path) -> Path:
    curated_rows = _CURATED_HARNESS_OUTLINES.get(case.slug)
    if curated_rows is not None:
        references = [str(row["reference"]) for row in curated_rows]
        weeks = [int(row["week"]) for row in curated_rows]
        focuses = [str(row["focus"]) for row in curated_rows]
    else:
        references = plan_scripture_day_references(reference=case.passage, num_days=case.num_days, max_verses_per_day=5)
        weeks = _week_assignments(case.num_days, case.num_weeks)
        focuses = [_day_focus_label(reference, day_number) for day_number, reference in enumerate(references, start=1)]
    csv_path = output_dir / f"{case.slug}__outline.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["Day", "Week", "Attribute", "Scripture", "Theme/Focus", "Notes", "Status"],
        )
        writer.writeheader()
        for day_number, reference in enumerate(references, start=1):
            writer.writerow(
                {
                    "Day": day_number,
                    "Week": weeks[day_number - 1],
                    "Attribute": case.passage,
                    "Scripture": reference,
                    "Theme/Focus": focuses[day_number - 1],
                    "Notes": "Generated by scripture harness",
                    "Status": "planned",
                }
            )
    return csv_path


def _store_outline_memory(case: HarnessCase, *, db_path: Path) -> None:
    curated_rows = _CURATED_HARNESS_OUTLINES.get(case.slug)
    if curated_rows is not None:
        store_outline_research(
            db_path=db_path,
            outline_key=case.slug,
            rows=curated_rows,
            source_kind="curated_harness_outline",
            source_title=case.passage,
            notes="Harness-curated devotional arc for quality testing.",
        )
        return
    references = plan_scripture_day_references(reference=case.passage, num_days=case.num_days, max_verses_per_day=5)
    weeks = _week_assignments(case.num_days, case.num_weeks)
    rows = [
        {
            "day": idx,
            "week": weeks[idx - 1],
            "reference": ref,
            "focus": _day_focus_label(ref, idx),
        }
        for idx, ref in enumerate(references, start=1)
    ]
    store_outline_research(
        db_path=db_path,
        outline_key=case.slug,
        rows=rows,
        source_kind="planner_outline",
        source_title=case.passage,
        notes="Planner-generated outline used by scripture harness.",
    )


def _attempted_harness_remedies(case: HarnessCase) -> list[str]:
    remedies = ["automatic targeted regeneration of affected days/clusters"]
    if case.slug in _CURATED_HARNESS_OUTLINES:
        remedies.append("curated whole-outline revision")
    else:
        remedies.append("planner-generated outline")
    return remedies


def _parse_run_stdout(stdout: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.isupper():
            parsed[key] = value
    return parsed


def _discover_latest_meta(*, repo_root: Path, started_at: float) -> Path | None:
    output_dir = repo_root / "outputs" / "devotionals"
    candidates = sorted(
        (
            path for path in output_dir.glob("*__meta.json")
            if path.stat().st_mtime >= started_at
        ),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _run_case(
    case: HarnessCase,
    *,
    generator: str,
    reviewed_by: str,
    harness_dir: Path,
    db_path: Path,
    reset_after_run: bool,
) -> dict[str, Any]:
    outline_csv = _build_outline_csv(case, output_dir=harness_dir)
    _store_outline_memory(case, db_path=db_path)
    bootstrap_catalog_tables(
        db_path=db_path,
        quote_seed_path=_DEFAULT_QUOTE_SEED,
        excerpt_seed_path=_DEFAULT_EXCERPT_SEED,
    )
    repo_root = Path(__file__).resolve().parents[1]
    cmd = [
        "scripts/run_devotional_full.py",
        "--csv",
        str(outline_csv),
        "--generator",
        generator,
        "--reviewed-by",
        reviewed_by,
        "--db-path",
        str(db_path),
    ]
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    started_at = time.time()
    with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stderr_buffer):
        try:
            exit_code = run_devotional_full_main(cmd[1:])
        except SystemExit as exc:
            exit_code = int(exc.code) if isinstance(exc.code, int) else 1
    stdout_text = stdout_buffer.getvalue()
    stderr_text = stderr_buffer.getvalue()
    parsed = _parse_run_stdout(stdout_text)
    if not parsed.get("META"):
        discovered_meta = _discover_latest_meta(repo_root=repo_root, started_at=started_at)
        if discovered_meta is not None:
            parsed["META"] = str(discovered_meta.relative_to(repo_root))
    result: dict[str, Any] = {
        "case_slug": case.slug,
        "passage": case.passage,
        "num_days": case.num_days,
        "num_weeks": case.num_weeks,
        "outline_csv": str(outline_csv),
        "command": f"{sys.executable} " + " ".join(cmd),
        "db_path": str(db_path),
        "reset_after_run": reset_after_run,
        "exit_code": exit_code,
        "stdout": stdout_text.strip(),
        "stderr": stderr_text.strip(),
        "run_slug": parsed.get("RUN_SLUG", ""),
        "book_json": parsed.get("BOOK_JSON", ""),
        "editorial_build": parsed.get("EDITORIAL_BUILD", ""),
        "approval_report": parsed.get("APPROVAL_REPORT", ""),
        "agent_validation": parsed.get("AGENT_VALIDATION", ""),
        "audit_linkage": parsed.get("AUDIT_LINKAGE", ""),
        "meta": parsed.get("META", ""),
    }
    if parsed.get("META"):
        meta_path = repo_root / parsed["META"]
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            attempted_remedies = _attempted_harness_remedies(case)
            validation_summary = meta.get("validation_summary") or {}
            if isinstance(validation_summary, dict):
                existing_attempts = validation_summary.get("attempted_remedies") or []
                merged_attempts: list[str] = []
                for item in [*existing_attempts, *attempted_remedies]:
                    text = str(item).strip()
                    if text and text not in merged_attempts:
                        merged_attempts.append(text)
                validation_summary["attempted_remedies"] = merged_attempts
                failed_check_ids = [
                    check_id
                    for event in validation_summary.get("rewrite_events", [])
                    if isinstance(event, dict)
                    for check_id in event.get("failed_check_ids", [])
                ]
                meta["validation_summary"] = validation_summary
                meta["remedy_suggestions"] = remedy_suggestions(
                    failed_check_ids,
                    attempted_remedies=merged_attempts,
                )
                meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
            result["meta_summary"] = {
                "run_state": meta.get("run_state"),
                "agent_validation_overall_status": meta.get("agent_validation_overall_status"),
                "agent_validation_overall_passed": meta.get("agent_validation_overall_passed"),
                "blocking_issues": meta.get("blocking_issues", []),
            }
            result["run_slug"] = str(meta.get("run_slug") or result["run_slug"])
            result["book_json"] = str(meta.get("book_json_path") or result["book_json"])
            result["editorial_build"] = str(meta.get("editorial_build_path") or result["editorial_build"])
            result["approval_report"] = str(meta.get("approval_report_path") or result["approval_report"])
            result["agent_validation"] = str(meta.get("agent_validation_report_path") or result["agent_validation"])
            result["audit_linkage"] = str(meta.get("audit_linkage_path") or result["audit_linkage"])
    if parsed.get("AGENT_VALIDATION"):
        report_path = repo_root / parsed["AGENT_VALIDATION"]
        if report_path.exists():
            report = json.loads(report_path.read_text(encoding="utf-8"))
            result["agent_validation_summary"] = {
                "overall_status": report.get("overall_status"),
                "overall_passed": report.get("overall_passed"),
                "discrepancy_count": len(report.get("discrepancies", [])),
                "blocking_issues": report.get("blocking_issues", []),
            }
    if parsed.get("APPROVAL_REPORT"):
        approval_path = repo_root / parsed["APPROVAL_REPORT"]
        if approval_path.exists():
            approval = json.loads(approval_path.read_text(encoding="utf-8"))
            result["approval_summary"] = {
                "exportable": approval.get("exportable"),
                "pending_sections": len(approval.get("pending_sections", [])),
                "blocked_reason": approval.get("blocked_reason", ""),
            }
    if reset_after_run and result.get("meta"):
        cleanup_stdout = io.StringIO()
        cleanup_stderr = io.StringIO()
        cleanup_cmd = [
            "--meta",
            result["meta"],
            "--db-path",
            str(db_path),
            "--keep-artifacts",
        ]
        with contextlib.redirect_stdout(cleanup_stdout), contextlib.redirect_stderr(cleanup_stderr):
            try:
                cleanup_exit = clean_regenerate_run_main(cleanup_cmd)
            except SystemExit as exc:
                cleanup_exit = int(exc.code) if isinstance(exc.code, int) else 1
        result["cleanup"] = {
            "exit_code": cleanup_exit,
            "stdout": cleanup_stdout.getvalue().strip(),
            "stderr": cleanup_stderr.getvalue().strip(),
            "parsed": _parse_run_stdout(cleanup_stdout.getvalue()),
        }
    return result


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_markdown(path: Path, *, generated_at: str, results: list[dict[str, Any]]) -> None:
    lines = [
        "# Scripture Harness Results",
        "",
        f"Generated at: {generated_at}",
        "",
        "| Case | Passage | Period | Exit | Run State | Validation | Discrepancies | Pending Sections |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for result in results:
        meta_summary = result.get("meta_summary", {})
        validation_summary = result.get("agent_validation_summary", {})
        approval_summary = result.get("approval_summary", {})
        lines.append(
            "| {case} | {passage} | {period} | {exit_code} | {run_state} | {validation} | {discrepancies} | {pending} |".format(
                case=result["case_slug"],
                passage=result["passage"],
                period=f"{result['num_days']}d/{result['num_weeks']}w",
                exit_code=result["exit_code"],
                run_state=meta_summary.get("run_state", ""),
                validation=validation_summary.get("overall_status", ""),
                discrepancies=validation_summary.get("discrepancy_count", ""),
                pending=approval_summary.get("pending_sections", ""),
            )
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the scripture benchmark harness against a fixed passage suite."
    )
    parser.add_argument(
        "--harness-set",
        choices=tuple(sorted(HARNESS_SETS)),
        default="a",
        help="Named scripture harness set to run when --case-spec is not provided.",
    )
    parser.add_argument(
        "--case-spec",
        action="append",
        default=[],
        help="Repeatable custom case in the form slug|passage|num_days|num_weeks.",
    )
    parser.add_argument(
        "--cases",
        nargs="*",
        help="Optional subset of case slugs to run. Default: full benchmark suite.",
    )
    parser.add_argument("--num-days", type=int, help="Optional override num_days for all selected cases.")
    parser.add_argument("--num-weeks", type=int, help="Optional override num_weeks for all selected cases.")
    parser.add_argument("--generator", choices=("mock", "real"), default="real")
    parser.add_argument("--reviewed-by", default="Victor")
    parser.add_argument(
        "--output-dir",
        default="outputs/harness",
        help="Directory for harness artifacts.",
    )
    parser.add_argument(
        "--db-path",
        default=None,
        help="Canonical SQLite registry DB path used by the harness.",
    )
    parser.add_argument(
        "--no-reset-after-run",
        action="store_true",
        help="Keep harness run utilization markers instead of resetting them after each case.",
    )
    args = parser.parse_args(argv)

    if args.case_spec:
        selected: list[HarnessCase] = []
        for raw in args.case_spec:
            parts = [piece.strip() for piece in raw.split("|")]
            if len(parts) != 4:
                raise SystemExit(f"Invalid --case-spec '{raw}'. Use slug|passage|num_days|num_weeks.")
            slug, passage, num_days_raw, num_weeks_raw = parts
            selected.append(
                HarnessCase(
                    slug=slug,
                    passage=passage,
                    num_days=int(num_days_raw),
                    num_weeks=int(num_weeks_raw),
                )
            )
    else:
        selected = list(HARNESS_SETS[args.harness_set])
    if args.cases:
        wanted = {item.strip().lower() for item in args.cases if item.strip()}
        selected = [case for case in selected if case.slug in wanted]
        if not selected:
            raise SystemExit("No matching harness cases selected.")
    if args.num_days is not None or args.num_weeks is not None:
        selected = [
            HarnessCase(
                slug=case.slug,
                passage=case.passage,
                num_days=args.num_days if args.num_days is not None else case.num_days,
                num_weeks=args.num_weeks if args.num_weeks is not None else case.num_weeks,
            )
            for case in selected
        ]

    repo_root = Path(__file__).resolve().parents[1]
    harness_dir = repo_root / args.output_dir
    db_path = Path(args.db_path) if args.db_path else default_registry_db_path()
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%S%z")
    run_dir = harness_dir / f"scripture-harness__{generated_at}"
    run_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for case in selected:
        print(f"[HARNESS] Running {case.slug} ({case.passage}) ...", flush=True)
        results.append(
            _run_case(
                case,
                generator=args.generator,
                reviewed_by=args.reviewed_by,
                harness_dir=run_dir,
                db_path=db_path,
                reset_after_run=not args.no_reset_after_run,
            )
        )

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "generator": args.generator,
        "harness_set": args.harness_set,
        "db_path": str(db_path),
        "reset_after_run": not args.no_reset_after_run,
        "cases": [asdict(case) for case in selected],
        "results": results,
    }
    json_path = run_dir / "scripture-harness-results.json"
    md_path = run_dir / "scripture-harness-results.md"
    _write_json(json_path, payload)
    _write_markdown(md_path, generated_at=payload["generated_at_utc"], results=results)

    print(f"HARNESS_JSON={json_path.relative_to(repo_root)}")
    print(f"HARNESS_MARKDOWN={md_path.relative_to(repo_root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
