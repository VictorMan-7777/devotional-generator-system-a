from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_REVIEWED_BY = "Victor"
ALLOW_BATCH_APPROVE_ENV = "DEVG_ALLOW_BATCH_APPROVE_ALL"


@dataclass(frozen=True)
class PendingItem:
    day: int
    section: str


SECTION_LABELS = {
    "timeless_wisdom": "Timeless Wisdom",
    "scripture": "Scripture",
    "exposition": "Exposition",
    "be_still": "Be Still",
    "action_steps": "Action Steps",
    "prayer": "Prayer",
    "sending_prompt": "Sending Prompt",
    "day7": "Day 7 Reflection",
}


def format_section_label(section: str) -> str:
    key = section.strip().lower()
    if not key:
        return section
    if key in SECTION_LABELS:
        return SECTION_LABELS[key]
    cleaned = key.replace("_", " ").replace("-", " ")
    return " ".join(part.capitalize() for part in cleaned.split())


def parse_pending_item(raw: str) -> PendingItem:
    # Expected format: "day 3 — exposition"
    text = raw.strip()
    if "—" not in text:
        raise ValueError(f"Invalid pending item format: {raw!r}")
    left, right = [part.strip() for part in text.split("—", 1)]
    if not left.lower().startswith("day "):
        raise ValueError(f"Invalid day prefix: {raw!r}")
    day = int(left.split()[1])
    if day <= 0:
        raise ValueError(f"Invalid day number: {raw!r}")
    if not right:
        raise ValueError(f"Missing section name: {raw!r}")
    return PendingItem(day=day, section=right)


def load_report(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "pending_sections" not in data:
        raise ValueError("Approval report missing pending_sections")
    return data


def _build_output_path(report_path: Path, explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    base = report_path.name
    if base.endswith("__approval-gate-report.json"):
        base = base.replace("__approval-gate-report.json", "__approval-decisions.json")
    else:
        base = base.replace(".json", "") + "__approval-decisions.json"
    return report_path.parent / base


def _decision_key(day: int, section: str) -> str:
    return f"{day}:{section.strip().lower()}"


def _atomic_write_json(path: Path, payload: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(path)


def default_reviewed_by() -> str:
    raw = os.getenv("DEVG_REVIEWED_BY", DEFAULT_REVIEWED_BY).strip()
    return raw or DEFAULT_REVIEWED_BY


def _is_agent_reviewer(reviewed_by: str) -> bool:
    return reviewed_by.strip().lower().startswith("agent:")


def _ensure_decision_source_policy(reviewed_by: str, decision_source: str | None) -> None:
    if _is_agent_reviewer(reviewed_by) and not (decision_source or "").strip():
        raise ValueError(
            "Agent decisions require decision_source. "
            "Pass --decision-source (e.g., secondary_source_crosscheck)."
        )


def _allow_batch_approve(flag: bool) -> bool:
    if flag:
        return True
    return os.getenv(ALLOW_BATCH_APPROVE_ENV, "").strip() == "1"


def _normalize_decision_record(raw: dict) -> dict:
    day = int(raw["day"])
    section = str(raw["section"]).strip()
    decision = str(raw["decision"]).strip().lower()
    if decision not in {"approved", "rejected", "skipped"}:
        raise ValueError(f"Invalid decision value: {decision!r}")
    if not section:
        raise ValueError("Decision record has empty section")

    reviewed_at_utc = str(raw.get("reviewed_at_utc") or "")
    reviewed_by = str(raw.get("reviewed_by") or default_reviewed_by())
    decision_source_raw = raw.get("decision_source")
    decision_source = None if decision_source_raw is None else str(decision_source_raw).strip()
    if decision_source == "":
        decision_source = None

    _ensure_decision_source_policy(reviewed_by, decision_source)
    normalized = {
        "day": day,
        "section": section,
        "decision": decision,
        "reviewed_by": reviewed_by,
    }
    if decision_source is not None:
        normalized["decision_source"] = decision_source
    if reviewed_at_utc:
        normalized["reviewed_at_utc"] = reviewed_at_utc
    elif decision in {"approved", "rejected"}:
        raise ValueError("Final decisions must include reviewed_at_utc")
    return normalized


def load_existing_decisions(
    output_path: Path,
    expected_source_report: Path | None = None,
) -> dict[str, dict]:
    if not output_path.exists():
        return {}
    data = json.loads(output_path.read_text(encoding="utf-8"))
    if expected_source_report is not None:
        source_report = str(data.get("source_report") or "").strip()
        if source_report and source_report != str(expected_source_report):
            # Prevent decision bleed-over when a reused --out file points to a different report.
            return {}
    decisions = data.get("decisions", [])
    mapping: dict[str, dict] = {}
    for d in decisions:
        normalized = _normalize_decision_record(d)
        key = _decision_key(int(normalized["day"]), str(normalized["section"]))
        mapping[key] = normalized
    return mapping


def _sorted_decisions(decision_map: dict[str, dict]) -> list[dict]:
    return sorted(
        decision_map.values(),
        key=lambda d: (int(d["day"]), str(d["section"]).lower()),
    )


def _is_resolved_decision(record: dict | None) -> bool:
    if not record:
        return False
    return str(record.get("decision", "")).lower() in {"approved", "rejected"}


def write_decisions(
    output_path: Path,
    report: dict,
    decision_map: dict[str, dict],
    mode: str,
    total_pending: int,
) -> None:
    decisions = _sorted_decisions(decision_map)
    approved = sum(1 for d in decisions if d["decision"] == "approved")
    rejected = sum(1 for d in decisions if d["decision"] == "rejected")
    skipped = sum(1 for d in decisions if d["decision"] == "skipped")
    completed = len(decisions)

    payload = {
        "source_report": str(report.get("source_report", "")),
        "topic": report.get("topic"),
        "days": report.get("days"),
        "mode": mode,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "approved": approved,
            "rejected": rejected,
            "skipped": skipped,
            "completed": completed,
            "remaining": max(total_pending - completed, 0),
            "total_pending": total_pending,
        },
        "decisions": decisions,
    }
    _atomic_write_json(output_path, payload)


def unresolved_items(items: list[PendingItem], decision_map: dict[str, dict]) -> list[PendingItem]:
    unresolved: list[PendingItem] = []
    for item in items:
        key = _decision_key(item.day, item.section)
        if not _is_resolved_decision(decision_map.get(key)):
            unresolved.append(item)
    return unresolved


def run_interactive(
    items: list[PendingItem],
    decision_map: dict[str, dict],
    persist_fn,
    reviewed_by: str,
    decision_source: str | None = None,
) -> dict[str, dict]:
    _ensure_decision_source_policy(reviewed_by, decision_source)
    if not sys.stdin.isatty():
        raise RuntimeError("Interactive mode requires a TTY.")

    total = len(items)
    remaining = unresolved_items(items, decision_map)
    if not remaining:
        print("No unresolved pending sections. Approval set is complete.")
        return decision_map

    print(f"Pending sections: {total} (remaining: {len(remaining)})")
    print("Choices: [a]pprove  [r]eject  [s]kip  [q]uit")

    for idx, item in enumerate(remaining, start=1):
        while True:
            choice = input(
                f"[{idx}/{len(remaining)}] day {item.day} — {item.section}: "
            ).strip().lower()
            if choice in {"a", "approve", "approved"}:
                decision = "approved"
                break
            if choice in {"r", "reject", "rejected"}:
                decision = "rejected"
                break
            if choice in {"s", "skip", "skipped", ""}:
                # Skip leaves this section pending; do not mark it resolved.
                print("Skipped (remains pending).")
                break
            if choice in {"q", "quit"}:
                print("Stopped by user.")
                return decision_map
            print("Invalid choice. Use a/r/s/q.")

        if choice in {"s", "skip", "skipped", ""}:
            continue

        record = {
            "day": item.day,
            "section": item.section,
            "decision": decision,
            "reviewed_at_utc": datetime.now(timezone.utc).isoformat(),
            "reviewed_by": reviewed_by,
        }
        if decision_source is not None:
            record["decision_source"] = decision_source
        decision_map[_decision_key(item.day, item.section)] = record
        persist_fn(decision_map)

    return decision_map


def run_batch(
    items: list[PendingItem],
    decision: str,
    decision_map: dict[str, dict],
    reviewed_by: str,
    decision_source: str,
) -> dict[str, dict]:
    _ensure_decision_source_policy(reviewed_by, decision_source)
    now = datetime.now(timezone.utc).isoformat()
    for item in unresolved_items(items, decision_map):
        decision_map[_decision_key(item.day, item.section)] = {
            "day": item.day,
            "section": item.section,
            "decision": decision,
            "reviewed_at_utc": now,
            "reviewed_by": reviewed_by,
            "decision_source": decision_source,
        }
    return decision_map


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run pending section approvals from an approval-gate report."
    )
    parser.add_argument("--report", required=True, help="Path to approval-gate report JSON")
    parser.add_argument(
        "--mode",
        choices=["interactive", "approve-all", "reject-all"],
        default="interactive",
        help="Approval workflow mode",
    )
    parser.add_argument("--out", help="Output decisions JSON path")
    parser.add_argument(
        "--reviewed-by",
        default=default_reviewed_by(),
        help="Reviewer identifier stored in decision metadata.",
    )
    parser.add_argument(
        "--decision-source",
        help=(
            "Decision provenance label. Required when --reviewed-by starts with 'agent:'. "
            "Examples: secondary_source_crosscheck, cli_batch_reject_all."
        ),
    )
    parser.add_argument(
        "--allow-batch-approve",
        action="store_true",
        help=(
            "Enable --mode approve-all (debug-only). "
            f"Otherwise blocked unless {ALLOW_BATCH_APPROVE_ENV}=1."
        ),
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Ignore existing decisions file and start this report from scratch.",
    )
    args = parser.parse_args(argv)

    report_path = Path(args.report)
    report = load_report(report_path)
    report["source_report"] = str(report_path)

    items = [parse_pending_item(raw) for raw in report.get("pending_sections", [])]
    output_path = _build_output_path(report_path, args.out)
    total_pending = len(items)

    decision_map = (
        {}
        if args.reset
        else load_existing_decisions(output_path, expected_source_report=report_path)
    )

    decision_source = args.decision_source.strip() if args.decision_source else None
    _ensure_decision_source_policy(args.reviewed_by, decision_source)

    def persist(current_map: dict[str, dict]) -> None:
        write_decisions(
            output_path=output_path,
            report=report,
            decision_map=current_map,
            mode=args.mode,
            total_pending=total_pending,
        )

    # Persist initial state so a runner invocation always materializes status.
    persist(decision_map)

    if args.mode == "interactive":
        decision_map = run_interactive(
            items,
            decision_map=decision_map,
            persist_fn=persist,
            reviewed_by=args.reviewed_by,
            decision_source=decision_source,
        )
    elif args.mode == "approve-all":
        if not _allow_batch_approve(args.allow_batch_approve):
            raise ValueError(
                "approve-all is disabled by default. Use --allow-batch-approve "
                f"or set {ALLOW_BATCH_APPROVE_ENV}=1."
            )
        decision_map = run_batch(
            items,
            decision="approved",
            decision_map=decision_map,
            reviewed_by=args.reviewed_by,
            decision_source=decision_source or "cli_batch_approve_all",
        )
    else:
        decision_map = run_batch(
            items,
            decision="rejected",
            decision_map=decision_map,
            reviewed_by=args.reviewed_by,
            decision_source=decision_source or "cli_batch_reject_all",
        )

    persist(decision_map)
    decisions = _sorted_decisions(decision_map)
    print(f"DECISIONS={output_path}")
    print(f"COUNT={len(decisions)}")
    print(f"REMAINING={max(total_pending - len(decisions), 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
