"""Tests for the IRB Tier-3 runner harness.

Verifies:
- CheckResult dataclass structure
- Individual check functions return correct pass/fail
- NN computation logic
- Full runner produces correct output schema (dry-run)
"""
from __future__ import annotations

import datetime
import json
import subprocess
import sys
from pathlib import Path

import pytest

# Ensure repo root is on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.irb.run_tier3 import (
    CheckResult,
    RunReport,
    check_t3_adv_001,
    check_t3_adv_002,
    check_t3_adv_003,
    check_t3_doc_001,
    check_t3_doc_002,
    check_t3_doc_003,
    check_t3_doc_004,
    check_t3_guard_001,
    check_t3_repo_001,
    check_t3_repo_002,
    check_t3_rwr_001,
    check_t3_rwr_002,
    check_t3_rwr_003,
    check_t3_sch_001,
    check_t3_sch_002,
    check_t3_sch_003,
    check_t3_sch_004,
    compute_next_nn,
)


# ──────────────────────────────────────────────────────────────────────────────
# CheckResult structure
# ──────────────────────────────────────────────────────────────────────────────


def test_check_result_structure():
    """CheckResult dataclass has all required fields."""
    r = CheckResult(
        check_id="T3-TEST-001",
        category="test",
        name="test_check",
        blocking=True,
        passed=True,
        evidence={"key": "val"},
        detail="PASS: test.",
    )
    assert r.check_id == "T3-TEST-001"
    assert r.category == "test"
    assert r.name == "test_check"
    assert isinstance(r.blocking, bool)
    assert isinstance(r.passed, bool)
    assert isinstance(r.evidence, dict)
    assert isinstance(r.detail, str)


# ──────────────────────────────────────────────────────────────────────────────
# NN computation
# ──────────────────────────────────────────────────────────────────────────────


def test_compute_next_nn_empty_dir(tmp_path):
    """Empty output dir → NN = 01."""
    assert compute_next_nn(tmp_path, datetime.date(2026, 3, 5)) == "01"


def test_compute_next_nn_existing_files(tmp_path):
    """Existing files → NN = max + 1."""
    (tmp_path / "2026-03-05__01__builder__something.md").touch()
    (tmp_path / "2026-03-05__03__builder__something.json").touch()
    assert compute_next_nn(tmp_path, datetime.date(2026, 3, 5)) == "04"


def test_compute_next_nn_different_date(tmp_path):
    """Existing files from a different date don't affect today's NN."""
    (tmp_path / "2026-03-04__08__builder__old.md").touch()
    assert compute_next_nn(tmp_path, datetime.date(2026, 3, 5)) == "01"


# ──────────────────────────────────────────────────────────────────────────────
# Doctrinal checks
# ──────────────────────────────────────────────────────────────────────────────


def test_t3_doc_001_prosperity_flagged():
    result = check_t3_doc_001(_REPO_ROOT)
    assert result.check_id == "T3-DOC-001"
    assert result.passed is True
    assert "DOCTRINAL_PROSPERITY_GOSPEL" in result.evidence["returned_codes"]


def test_t3_doc_002_works_merit_flagged():
    result = check_t3_doc_002(_REPO_ROOT)
    assert result.check_id == "T3-DOC-002"
    assert result.passed is True
    assert "DOCTRINAL_WORKS_MERIT" in result.evidence["returned_codes"]


def test_t3_doc_003_clean_text_passes():
    result = check_t3_doc_003(_REPO_ROOT)
    assert result.check_id == "T3-DOC-003"
    assert result.passed is True
    assert result.evidence["returned_count"] == 0


def test_t3_doc_004_combined_adversarial():
    result = check_t3_doc_004(_REPO_ROOT)
    assert result.check_id == "T3-DOC-004"
    assert result.passed is True
    assert result.evidence["returned_count"] == 2


# ──────────────────────────────────────────────────────────────────────────────
# Schema invariant checks
# ──────────────────────────────────────────────────────────────────────────────


def test_t3_sch_001_grounding_map_rejects_three():
    result = check_t3_sch_001(_REPO_ROOT)
    assert result.check_id == "T3-SCH-001"
    assert result.passed is True
    assert result.evidence["exception_type"] == "ValidationError"


def test_t3_sch_002_grounding_map_rejects_empty():
    result = check_t3_sch_002(_REPO_ROOT)
    assert result.check_id == "T3-SCH-002"
    assert result.passed is True
    assert result.evidence["exception_type"] == "ValidationError"


def test_t3_sch_003_prayer_trace_rejects_invalid():
    result = check_t3_sch_003(_REPO_ROOT)
    assert result.check_id == "T3-SCH-003"
    assert result.passed is True
    assert result.evidence["exception_type"] == "ValidationError"


def test_t3_sch_004_prayer_trace_accepts_valid():
    result = check_t3_sch_004(_REPO_ROOT)
    assert result.check_id == "T3-SCH-004"
    assert result.passed is True
    assert set(result.evidence["source_types_used"]) == {"scripture", "exposition", "be_still"}


# ──────────────────────────────────────────────────────────────────────────────
# Rewrite routing checks
# ──────────────────────────────────────────────────────────────────────────────


def test_t3_rwr_001_attempt_one():
    result = check_t3_rwr_001(_REPO_ROOT)
    assert result.check_id == "T3-RWR-001"
    assert result.passed is True
    assert result.evidence["signal"] == "auto_rewrite"


def test_t3_rwr_002_attempt_two():
    result = check_t3_rwr_002(_REPO_ROOT)
    assert result.check_id == "T3-RWR-002"
    assert result.passed is True
    assert result.evidence["signal"] == "human_review"


def test_t3_rwr_003_attempt_three():
    result = check_t3_rwr_003(_REPO_ROOT)
    assert result.check_id == "T3-RWR-003"
    assert result.passed is True
    assert result.evidence["signal"] == "human_review"


# ──────────────────────────────────────────────────────────────────────────────
# Adversarial simulation checks
# ──────────────────────────────────────────────────────────────────────────────


def test_t3_adv_001_injection_safe():
    result = check_t3_adv_001(_REPO_ROOT)
    assert result.check_id == "T3-ADV-001"
    assert result.passed is True
    assert "; DROP TABLE" in result.evidence["topic_stored"]


def test_t3_adv_002_long_text_no_crash():
    result = check_t3_adv_002(_REPO_ROOT)
    assert result.check_id == "T3-ADV-002"
    assert result.passed is True
    assert result.evidence["text_length"] >= 5000


def test_t3_adv_003_empty_prompts_no_crash():
    result = check_t3_adv_003(_REPO_ROOT)
    assert result.check_id == "T3-ADV-003"
    assert result.passed is True
    assert result.evidence["fail_count"] >= 1


# ──────────────────────────────────────────────────────────────────────────────
# Guard check
# ──────────────────────────────────────────────────────────────────────────────


def test_t3_guard_001_no_mutation():
    """Guard passes when pre and post status are identical."""
    r = check_t3_guard_001(_REPO_ROOT, "some status", "some status")
    assert r.passed is True


def test_t3_guard_001_mutation_detected():
    """Guard fails when status differs."""
    r = check_t3_guard_001(_REPO_ROOT, "", "M  src/foo.py")
    assert r.passed is False


# ──────────────────────────────────────────────────────────────────────────────
# Full runner dry-run — JSON schema
# ──────────────────────────────────────────────────────────────────────────────


def test_runner_json_schema(tmp_path):
    """Full runner (dry-run) produces a RunReport with required top-level fields."""
    from scripts.irb.run_tier3 import run

    exit_code = run(_REPO_ROOT, dry_run=True)

    # Exit code must be 0 (CERTIFIED) or 1 (FAILED); never 2 (ERROR) in normal run.
    assert exit_code in (0, 1), f"Unexpected exit code {exit_code}"
