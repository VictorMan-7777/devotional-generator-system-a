#!/usr/bin/env python3
"""IRB Tier-3 runner — Adversarial robustness certification.

Entry point:
    python scripts/irb/run_tier3.py [--target REPO_ROOT] [--dry-run]

Exit codes:
    0  CERTIFIED  (all blocking checks pass)
    1  FAILED     (one or more blocking checks fail)
    2  ERROR      (runner itself errors out)
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

# ──────────────────────────────────────────────────────────────────────────────
# Dataclasses
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class CheckResult:
    check_id: str
    category: str
    name: str
    blocking: bool
    passed: bool
    evidence: dict[str, Any]
    detail: str


@dataclass
class RunReport:
    spec_id: str = "irb-tier-3"
    spec_version: str = "1.0.0"
    run_date: str = ""
    repo_root: str = ""
    outcome: str = ""          # CERTIFIED | FAILED | ERROR
    checks: list[CheckResult] = field(default_factory=list)
    blocking_failures: list[str] = field(default_factory=list)
    advisory_failures: list[str] = field(default_factory=list)
    total_checks: int = 0
    passed_checks: int = 0
    failed_checks: int = 0


# ──────────────────────────────────────────────────────────────────────────────
# Naming-policy utilities
# ──────────────────────────────────────────────────────────────────────────────

_ARTIFACT_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}__(\d{2})__[a-z][a-z0-9]*__[a-z0-9][a-z0-9\-]*\.(md|json)$"
)


def compute_next_nn(output_dir: Path, today: datetime.date) -> str:
    """Return next available two-digit NN for today's date."""
    prefix = today.strftime("%Y-%m-%d")
    existing = [
        f.name for f in output_dir.glob(f"{prefix}__*.md")
    ] + [
        f.name for f in output_dir.glob(f"{prefix}__*.json")
    ]
    used_nns: list[int] = []
    for name in existing:
        m = re.match(r"^\d{4}-\d{2}-\d{2}__(\d{2})__", name)
        if m:
            used_nns.append(int(m.group(1)))
    next_nn = (max(used_nns) + 1) if used_nns else 1
    return f"{next_nn:02d}"


# ──────────────────────────────────────────────────────────────────────────────
# Individual checks
# ──────────────────────────────────────────────────────────────────────────────


def check_t3_repo_001(repo_root: Path) -> CheckResult:
    """T3-REPO-001: scripts/irb/*.py must not invoke grep via subprocess."""
    irb_dir = repo_root / "scripts" / "irb"
    if not irb_dir.exists():
        return CheckResult(
            check_id="T3-REPO-001",
            category="repo",
            name="no_grep_in_irb_scripts",
            blocking=False,
            passed=True,
            evidence={"note": "scripts/irb/ does not exist yet; advisory pass"},
            detail="Advisory: scripts/irb/ not present; trivially no grep calls.",
        )
    py_files = list(irb_dir.glob("*.py"))
    violations: list[str] = []
    grep_pattern = re.compile(r"""subprocess\.(run|call|Popen|check_output).*["']grep""")
    for py_file in py_files:
        text = py_file.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            if "grep" in line and "subprocess" in line:
                if grep_pattern.search(line):
                    violations.append(f"{py_file.name}:{lineno}: {line.strip()}")
    passed = len(violations) == 0
    return CheckResult(
        check_id="T3-REPO-001",
        category="repo",
        name="no_grep_in_irb_scripts",
        blocking=False,
        passed=passed,
        evidence={"files_scanned": [f.name for f in py_files], "violations": violations},
        detail="PASS: no grep subprocess calls." if passed else f"FAIL: {len(violations)} grep calls found.",
    )


def check_t3_repo_002(repo_root: Path) -> CheckResult:
    """T3-REPO-002: Every .md/.json in docs/system/outputs/ must match naming policy."""
    output_dir = repo_root / "docs" / "system" / "outputs"
    if not output_dir.exists():
        return CheckResult(
            check_id="T3-REPO-002",
            category="repo",
            name="artifact_naming_policy",
            blocking=True,
            passed=False,
            evidence={"error": "docs/system/outputs/ does not exist"},
            detail="FAIL: output directory missing.",
        )
    files = sorted(output_dir.iterdir())
    non_conforming: list[str] = []
    conforming: list[str] = []
    for f in files:
        if f.is_file() and f.suffix in (".md", ".json"):
            if _ARTIFACT_PATTERN.match(f.name):
                conforming.append(f.name)
            else:
                non_conforming.append(f.name)
    passed = len(non_conforming) == 0
    return CheckResult(
        check_id="T3-REPO-002",
        category="repo",
        name="artifact_naming_policy",
        blocking=True,
        passed=passed,
        evidence={
            "conforming_count": len(conforming),
            "non_conforming": non_conforming,
            "conforming": conforming,
        },
        detail=(
            f"PASS: all {len(conforming)} artifacts conform to naming policy."
            if passed
            else f"FAIL: {len(non_conforming)} non-conforming artifacts: {non_conforming}"
        ),
    )


def check_t3_doc_001(repo_root: Path) -> CheckResult:
    """T3-DOC-001: Prosperity gospel text must be flagged."""
    from src.validation.doctrinal import check_doctrinal

    text = "God wants you wealthy and God promises financial blessing to the faithful."
    results = check_doctrinal(text)
    codes = [r.reason_code for r in results]
    passed = "DOCTRINAL_PROSPERITY_GOSPEL" in codes
    return CheckResult(
        check_id="T3-DOC-001",
        category="doctrinal",
        name="prosperity_gospel_flagged",
        blocking=True,
        passed=passed,
        evidence={"input_excerpt": text[:80], "returned_codes": codes},
        detail="PASS: prosperity gospel correctly flagged." if passed else f"FAIL: expected DOCTRINAL_PROSPERITY_GOSPEL in {codes}",
    )


def check_t3_doc_002(repo_root: Path) -> CheckResult:
    """T3-DOC-002: Works-merit text must be flagged."""
    from src.validation.doctrinal import check_doctrinal

    text = "You can earn God's love through dedicated service and righteous deeds."
    results = check_doctrinal(text)
    codes = [r.reason_code for r in results]
    passed = "DOCTRINAL_WORKS_MERIT" in codes
    return CheckResult(
        check_id="T3-DOC-002",
        category="doctrinal",
        name="works_merit_flagged",
        blocking=True,
        passed=passed,
        evidence={"input_excerpt": text[:80], "returned_codes": codes},
        detail="PASS: works-merit correctly flagged." if passed else f"FAIL: expected DOCTRINAL_WORKS_MERIT in {codes}",
    )


def check_t3_doc_003(repo_root: Path) -> CheckResult:
    """T3-DOC-003: Clean text must return empty list (no false positives)."""
    from src.validation.doctrinal import check_doctrinal

    text = (
        "We are reminded that God's grace is freely given, not earned through our efforts. "
        "In Christ we find hope and restoration for all who believe."
    )
    results = check_doctrinal(text)
    passed = len(results) == 0
    return CheckResult(
        check_id="T3-DOC-003",
        category="doctrinal",
        name="clean_text_passes",
        blocking=True,
        passed=passed,
        evidence={"input_excerpt": text[:80], "returned_count": len(results), "returned_codes": [r.reason_code for r in results]},
        detail="PASS: clean text returned no violations." if passed else f"FAIL: {len(results)} unexpected violations.",
    )


def check_t3_doc_004(repo_root: Path) -> CheckResult:
    """T3-DOC-004: Combined adversarial text returns exactly 2 assessments."""
    from src.validation.doctrinal import check_doctrinal

    text = (
        "God wants you wealthy through health and wealth gospel principles. "
        "You can earn God's forgiveness through your daily devotional practice."
    )
    results = check_doctrinal(text)
    codes = sorted([r.reason_code for r in results])
    passed = (
        len(results) == 2
        and "DOCTRINAL_PROSPERITY_GOSPEL" in codes
        and "DOCTRINAL_WORKS_MERIT" in codes
    )
    return CheckResult(
        check_id="T3-DOC-004",
        category="doctrinal",
        name="combined_adversarial",
        blocking=True,
        passed=passed,
        evidence={"input_excerpt": text[:80], "returned_count": len(results), "returned_codes": codes},
        detail="PASS: both violation types correctly detected." if passed else f"FAIL: expected 2 assessments with both codes, got {codes}",
    )


def _make_grounding_entries(n: int) -> list[dict]:
    """Build n valid GroundingMapEntry dicts."""
    return [
        {
            "paragraph_number": i + 1,
            "paragraph_name": f"Para {i + 1}",
            "sources_retrieved": [f"Source {i + 1}"],
            "excerpts_used": [f"Excerpt {i + 1}"],
            "how_retrieval_informed_paragraph": f"Informed paragraph {i + 1}.",
        }
        for i in range(n)
    ]


def check_t3_sch_001(repo_root: Path) -> CheckResult:
    """T3-SCH-001: GroundingMap with 3 entries must raise ValidationError."""
    from pydantic import ValidationError

    from src.models.artifacts import GroundingMap

    try:
        GroundingMap(
            id="test-id",
            exposition_id="exp-id",
            entries=_make_grounding_entries(3),
        )
        passed = False
        detail = "FAIL: ValidationError was NOT raised for 3-entry GroundingMap."
        evidence: dict[str, Any] = {"exception": None}
    except ValidationError as e:
        passed = True
        detail = "PASS: ValidationError correctly raised for 3-entry GroundingMap."
        evidence = {"exception_type": "ValidationError", "errors": e.error_count()}
    return CheckResult(
        check_id="T3-SCH-001",
        category="schema",
        name="grounding_map_rejects_three_entries",
        blocking=True,
        passed=passed,
        evidence=evidence,
        detail=detail,
    )


def check_t3_sch_002(repo_root: Path) -> CheckResult:
    """T3-SCH-002: GroundingMap with 0 entries must raise ValidationError."""
    from pydantic import ValidationError

    from src.models.artifacts import GroundingMap

    try:
        GroundingMap(id="test-id", exposition_id="exp-id", entries=[])
        passed = False
        detail = "FAIL: ValidationError was NOT raised for empty GroundingMap."
        evidence: dict[str, Any] = {"exception": None}
    except ValidationError as e:
        passed = True
        detail = "PASS: ValidationError correctly raised for empty GroundingMap."
        evidence = {"exception_type": "ValidationError", "errors": e.error_count()}
    return CheckResult(
        check_id="T3-SCH-002",
        category="schema",
        name="grounding_map_rejects_empty_entries",
        blocking=True,
        passed=passed,
        evidence=evidence,
        detail=detail,
    )


def check_t3_sch_003(repo_root: Path) -> CheckResult:
    """T3-SCH-003: PrayerTraceMap with invalid source_type must raise ValidationError."""
    from pydantic import ValidationError

    from src.models.artifacts import PrayerTraceMap, PrayerTraceMapEntry

    try:
        PrayerTraceMap(
            id="test-id",
            prayer_id="prayer-id",
            entries=[
                PrayerTraceMapEntry(
                    element_text="Lord, hear our prayer.",
                    source_type="llm_hallucination",
                    source_reference="n/a",
                )
            ],
        )
        passed = False
        detail = "FAIL: ValidationError was NOT raised for invalid source_type."
        evidence: dict[str, Any] = {"exception": None}
    except ValidationError as e:
        passed = True
        detail = "PASS: ValidationError correctly raised for source_type='llm_hallucination'."
        evidence = {"exception_type": "ValidationError", "errors": e.error_count()}
    return CheckResult(
        check_id="T3-SCH-003",
        category="schema",
        name="prayer_trace_map_rejects_invalid_source",
        blocking=True,
        passed=passed,
        evidence=evidence,
        detail=detail,
    )


def check_t3_sch_004(repo_root: Path) -> CheckResult:
    """T3-SCH-004: PrayerTraceMap with valid source types must succeed."""
    from src.models.artifacts import PrayerTraceMap, PrayerTraceMapEntry

    valid_types = ["scripture", "exposition", "be_still"]
    try:
        ptm = PrayerTraceMap(
            id="test-id",
            prayer_id="prayer-id",
            entries=[
                PrayerTraceMapEntry(
                    element_text=f"Element {i}",
                    source_type=st,
                    source_reference=f"Ref {i}",
                )
                for i, st in enumerate(valid_types)
            ],
        )
        passed = True
        detail = "PASS: PrayerTraceMap created with all valid source types."
        evidence: dict[str, Any] = {
            "source_types_used": [e.source_type for e in ptm.entries]
        }
    except Exception as e:
        passed = False
        detail = f"FAIL: Unexpected exception: {e}"
        evidence = {"exception": str(e)}
    return CheckResult(
        check_id="T3-SCH-004",
        category="schema",
        name="prayer_trace_map_accepts_valid_types",
        blocking=True,
        passed=passed,
        evidence=evidence,
        detail=detail,
    )


def _make_failing_assessment():
    from src.models.validation import ValidatorAssessment

    return ValidatorAssessment(
        check_id="DOCTRINAL_PROSPERITY",
        result="fail",
        reason_code="DOCTRINAL_PROSPERITY_GOSPEL",
        explanation="Test failure.",
        evidence="test",
    )


def check_t3_rwr_001(repo_root: Path) -> CheckResult:
    """T3-RWR-001: attempt_number=1 must route to AUTO_REWRITE."""
    from src.models.validation import RewriteSignal
    from src.validation.rewrite_router import route

    decision = route([_make_failing_assessment()], attempt_number=1)
    passed = decision.signal == RewriteSignal.AUTO_REWRITE
    return CheckResult(
        check_id="T3-RWR-001",
        category="rewrite",
        name="attempt_one_auto_rewrite",
        blocking=True,
        passed=passed,
        evidence={"signal": decision.signal.value, "failed_count": len(decision.failed_assessments)},
        detail="PASS: attempt 1 routes to AUTO_REWRITE." if passed else f"FAIL: expected AUTO_REWRITE, got {decision.signal.value}",
    )


def check_t3_rwr_002(repo_root: Path) -> CheckResult:
    """T3-RWR-002: attempt_number=2 must route to HUMAN_REVIEW."""
    from src.models.validation import RewriteSignal
    from src.validation.rewrite_router import route

    decision = route([_make_failing_assessment()], attempt_number=2)
    passed = decision.signal == RewriteSignal.HUMAN_REVIEW
    return CheckResult(
        check_id="T3-RWR-002",
        category="rewrite",
        name="attempt_two_human_review",
        blocking=True,
        passed=passed,
        evidence={"signal": decision.signal.value},
        detail="PASS: attempt 2 routes to HUMAN_REVIEW." if passed else f"FAIL: expected HUMAN_REVIEW, got {decision.signal.value}",
    )


def check_t3_rwr_003(repo_root: Path) -> CheckResult:
    """T3-RWR-003: attempt_number=3 must route to HUMAN_REVIEW."""
    from src.models.validation import RewriteSignal
    from src.validation.rewrite_router import route

    decision = route([_make_failing_assessment()], attempt_number=3)
    passed = decision.signal == RewriteSignal.HUMAN_REVIEW
    return CheckResult(
        check_id="T3-RWR-003",
        category="rewrite",
        name="attempt_three_still_human_review",
        blocking=True,
        passed=passed,
        evidence={"signal": decision.signal.value},
        detail="PASS: attempt 3 routes to HUMAN_REVIEW." if passed else f"FAIL: expected HUMAN_REVIEW, got {decision.signal.value}",
    )


def check_t3_adv_001(repo_root: Path) -> CheckResult:
    """T3-ADV-001: SQL injection in topic field must be accepted safely."""
    from src.models.devotional import DevotionalInput

    injection = "; DROP TABLE devotionals; --"
    try:
        inp = DevotionalInput(topic=injection)
        passed = inp.topic == injection
        detail = "PASS: injection string stored verbatim without crash."
        evidence: dict[str, Any] = {"topic_stored": inp.topic}
    except Exception as e:
        passed = False
        detail = f"FAIL: unexpected exception on injection input: {e}"
        evidence = {"exception": str(e)}
    return CheckResult(
        check_id="T3-ADV-001",
        category="adversarial",
        name="injection_topic_accepted_safely",
        blocking=True,
        passed=passed,
        evidence=evidence,
        detail=detail,
    )


def check_t3_adv_002(repo_root: Path) -> CheckResult:
    """T3-ADV-002: validate_exposition must not crash on 10,000-char text."""
    from src.models.devotional import ExpositionSection
    from src.validation.exposition import validate_exposition

    long_text = "We trust in the grace of God. " * 400  # ~10,000 chars
    section = ExpositionSection(
        text=long_text,
        word_count=len(long_text.split()),
        grounding_map_id="gm-test",
    )
    try:
        results = validate_exposition(section)
        passed = isinstance(results, list)
        detail = f"PASS: validator returned list of {len(results)} assessment(s) without crash."
        evidence: dict[str, Any] = {
            "text_length": len(long_text),
            "assessment_count": len(results),
            "result_codes": [r.reason_code for r in results if r.result == "fail"],
        }
    except Exception as e:
        passed = False
        detail = f"FAIL: validate_exposition raised unexpectedly: {e}"
        evidence = {"exception": str(e)}
    return CheckResult(
        check_id="T3-ADV-002",
        category="adversarial",
        name="exposition_validator_no_crash_on_long_text",
        blocking=True,
        passed=passed,
        evidence=evidence,
        detail=detail,
    )


def check_t3_adv_003(repo_root: Path) -> CheckResult:
    """T3-ADV-003: validate_be_still must not crash on empty prompts list."""
    from src.models.devotional import BeStillSection
    from src.validation.be_still import validate_be_still

    section = BeStillSection(prompts=[])
    try:
        results = validate_be_still(section)
        fail_results = [r for r in results if r.result == "fail"]
        passed = isinstance(results, list) and len(fail_results) >= 1
        detail = (
            f"PASS: validator returned {len(results)} assessment(s) with {len(fail_results)} FAIL(s)."
            if passed
            else "FAIL: validator returned no FAIL assessments for empty prompts."
        )
        evidence: dict[str, Any] = {
            "assessment_count": len(results),
            "fail_count": len(fail_results),
            "fail_codes": [r.reason_code for r in fail_results],
        }
    except Exception as e:
        passed = False
        detail = f"FAIL: validate_be_still raised unexpectedly: {e}"
        evidence = {"exception": str(e)}
    return CheckResult(
        check_id="T3-ADV-003",
        category="adversarial",
        name="be_still_validator_no_crash_on_empty_prompts",
        blocking=True,
        passed=passed,
        evidence=evidence,
        detail=detail,
    )


def check_t3_guard_001(repo_root: Path, pre_status: str, post_status: str) -> CheckResult:
    """T3-GUARD-001: repo_mutation_guard — git status must not change."""
    passed = pre_status == post_status
    return CheckResult(
        check_id="T3-GUARD-001",
        category="guard",
        name="repo_mutation_guard",
        blocking=True,
        passed=passed,
        evidence={
            "pre_status": pre_status or "(clean)",
            "post_status": post_status or "(clean)",
            "delta": "" if passed else "STATUS CHANGED",
        },
        detail="PASS: repo unchanged by runner." if passed else "FAIL: runner mutated the repo.",
    )


# ──────────────────────────────────────────────────────────────────────────────
# Report serialization
# ──────────────────────────────────────────────────────────────────────────────


def _render_markdown(report: RunReport) -> str:
    lines = [
        f"# IRB Tier-3 Certification Report",
        f"",
        f"**Spec**: {report.spec_id} v{report.spec_version}",
        f"**Run date**: {report.run_date}",
        f"**Repo root**: {report.repo_root}",
        f"**Outcome**: **{report.outcome}**",
        f"",
        f"## Summary",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total checks | {report.total_checks} |",
        f"| Passed | {report.passed_checks} |",
        f"| Failed | {report.failed_checks} |",
        f"| Blocking failures | {len(report.blocking_failures)} |",
        f"| Advisory failures | {len(report.advisory_failures)} |",
        f"",
        f"## Check Results",
        f"",
        f"| ID | Category | Name | Blocking | Result | Detail |",
        f"|----|----------|------|----------|--------|--------|",
    ]
    for c in report.checks:
        status = "PASS" if c.passed else ("FAIL" if c.blocking else "ADVISORY-FAIL")
        lines.append(
            f"| {c.check_id} | {c.category} | {c.name} | {'yes' if c.blocking else 'no'} | {status} | {c.detail} |"
        )
    lines.append("")

    if report.blocking_failures:
        lines += [
            "## Blocking Failures (Remediation Required)",
            "",
        ]
        for bf in report.blocking_failures:
            lines.append(f"- {bf}")
        lines.append("")

    if report.advisory_failures:
        lines += [
            "## Advisory Failures",
            "",
        ]
        for af in report.advisory_failures:
            lines.append(f"- {af}")
        lines.append("")

    lines += [
        "## Evidence",
        "",
    ]
    for c in report.checks:
        lines.append(f"### {c.check_id} — {c.name}")
        lines.append("```json")
        lines.append(json.dumps(c.evidence, indent=2, sort_keys=True))
        lines.append("```")
        lines.append("")

    return "\n".join(lines)


def _to_json(report: RunReport) -> dict:
    d = asdict(report)
    return d


# ──────────────────────────────────────────────────────────────────────────────
# Main runner
# ──────────────────────────────────────────────────────────────────────────────


def git_status(repo_root: Path) -> str:
    """Return `git status --porcelain` output (empty string if clean)."""
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def run(repo_root: Path, dry_run: bool = False) -> int:
    """Execute Tier-3 and return exit code."""
    today = datetime.date.today()
    report = RunReport(
        run_date=today.isoformat(),
        repo_root=str(repo_root),
    )

    # Capture pre-run git status (mutation guard baseline).
    pre_status = git_status(repo_root)

    # Ordered check registry (sequential, deterministic).
    _CHECKS = [
        check_t3_repo_001,
        check_t3_repo_002,
        check_t3_doc_001,
        check_t3_doc_002,
        check_t3_doc_003,
        check_t3_doc_004,
        check_t3_sch_001,
        check_t3_sch_002,
        check_t3_sch_003,
        check_t3_sch_004,
        check_t3_rwr_001,
        check_t3_rwr_002,
        check_t3_rwr_003,
        check_t3_adv_001,
        check_t3_adv_002,
        check_t3_adv_003,
    ]

    runner_error: Optional[Exception] = None
    try:
        for check_fn in _CHECKS:
            try:
                result = check_fn(repo_root)
            except Exception as e:
                result = CheckResult(
                    check_id=check_fn.__name__.replace("check_", "").upper(),
                    category="unknown",
                    name=check_fn.__name__,
                    blocking=True,
                    passed=False,
                    evidence={"exception": str(e)},
                    detail=f"ERROR: check raised {type(e).__name__}: {e}",
                )
                runner_error = e
            report.checks.append(result)
    finally:
        # Always capture post-run git status.
        post_status = git_status(repo_root)
        guard_result = check_t3_guard_001(repo_root, pre_status, post_status)
        report.checks.append(guard_result)

    # Aggregate results.
    report.total_checks = len(report.checks)
    report.passed_checks = sum(1 for c in report.checks if c.passed)
    report.failed_checks = report.total_checks - report.passed_checks
    report.blocking_failures = [
        c.check_id for c in report.checks if not c.passed and c.blocking
    ]
    report.advisory_failures = [
        c.check_id for c in report.checks if not c.passed and not c.blocking
    ]

    if runner_error is not None:
        report.outcome = "ERROR"
    elif report.blocking_failures:
        report.outcome = "FAILED"
    else:
        report.outcome = "CERTIFIED"

    # Write artifacts (unless dry-run).
    exit_code = 0 if report.outcome == "CERTIFIED" else (2 if report.outcome == "ERROR" else 1)

    if not dry_run:
        output_dir = repo_root / "docs" / "system" / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)
        nn = compute_next_nn(output_dir, today)
        date_str = today.strftime("%Y-%m-%d")
        md_path = output_dir / f"{date_str}__{nn}__builder__irb-tier-3-report.md"
        json_path = output_dir / f"{date_str}__{nn}__builder__irb-tier-3-results.json"

        md_path.write_text(_render_markdown(report), encoding="utf-8")
        json_path.write_text(
            json.dumps(_to_json(report), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        print(f"  Markdown report : {md_path.relative_to(repo_root)}")
        print(f"  JSON results    : {json_path.relative_to(repo_root)}")

    # Print summary.
    print()
    print(f"IRB Tier-3 — {report.outcome}")
    print(f"  Checks: {report.total_checks} total / {report.passed_checks} pass / {report.failed_checks} fail")
    if report.blocking_failures:
        print(f"  Blocking failures: {', '.join(report.blocking_failures)}")
    if report.advisory_failures:
        print(f"  Advisory failures: {', '.join(report.advisory_failures)}")

    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description="IRB Tier-3 runner")
    parser.add_argument(
        "--target",
        default=None,
        help="Repo root (default: two directories up from this script)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run checks but do not write output artifacts",
    )
    args = parser.parse_args()

    if args.target:
        repo_root = Path(args.target).resolve()
    else:
        repo_root = Path(__file__).resolve().parent.parent.parent

    if not repo_root.exists():
        print(f"ERROR: repo_root {repo_root} does not exist", file=sys.stderr)
        return 2

    # Add repo_root to sys.path so src.* imports work.
    root_str = str(repo_root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)

    return run(repo_root, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
