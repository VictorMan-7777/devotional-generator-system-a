from __future__ import annotations

import json
from pathlib import Path

from src.autoresearch.policy_guardian_agent import build_policy_guardian_report


def test_build_policy_guardian_report_uses_global_rules_laws_and_flags_metadata_packets(tmp_path: Path) -> None:
    repo_root = tmp_path
    (repo_root / "docs" / "system" / "outputs").mkdir(parents=True)

    library_review = {
        "status": "reviewed",
        "findings": [],
        "packet_summary": {
            "metadata_excerpt_count": 3,
        },
        "actionable_requests": [
            {
                "scripture_reference": "Luke 15",
                "recommended_resolution": "clear_and_serve_from_current_holdings",
            }
        ],
    }
    outliner_cycle = {
        "status": "completed",
        "findings": [],
        "results": [
            {"assignment": {"teaching_method": "standard_outline_drill"}, "evaluation": {"status": "fail"}},
            {"assignment": {"teaching_method": "standard_outline_drill"}, "evaluation": {"status": "fail"}},
            {"assignment": {"teaching_method": "standard_outline_drill"}, "evaluation": {"status": "fail"}},
        ],
    }
    theological_review = {
        "status": "reviewed",
        "findings": [],
        "book_validation": {"theological_failures": 1},
        "quote_validation": {"failed_days": 0},
    }
    exposition_cycle = {
        "status": "ready",
        "findings": [],
        "grammar_guidance": {"finding_count": 2},
    }

    (repo_root / "docs" / "system" / "outputs" / "2026-03-16__library-trainer-review.json").write_text(json.dumps(library_review))
    (repo_root / "docs" / "system" / "outputs" / "2026-03-16__outliner-training-cycle.json").write_text(json.dumps(outliner_cycle))
    (repo_root / "docs" / "system" / "outputs" / "2026-03-16__theological-reviewer-report.json").write_text(json.dumps(theological_review))
    (repo_root / "docs" / "system" / "outputs" / "2026-03-16__exposition-training-cycle.json").write_text(json.dumps(exposition_cycle))

    payload = build_policy_guardian_report(repo_root)

    # Profile and authority
    assert payload["trainer_profile"]["role"] == "expert_policy_guardian"
    assert "authority" in payload["trainer_profile"]

    # Rules paths point to the correct constitution location
    assert payload["rules_paths"]["tier0_constitution"].endswith("/rules-laws/constitution.md")

    # Enforcement scope
    assert payload["enforcement_scope"]["enforce_constitutional_rules"] is True
    assert payload["enforcement_scope"]["enforce_federal_rules"] is True
    assert payload["enforcement_scope"]["enforce_local_rules"] is False  # no .laws/ dir in tmp_path

    # Finding summary is present
    assert "finding_summary" in payload
    assert payload["finding_summary"]["total"] >= 1

    # All findings include law_citation for traceability
    for finding in payload["findings"]:
        assert "law_citation" in finding, f"Finding missing law_citation: {finding['title']}"
        assert "severity" in finding
        assert "rationale" in finding
        assert "recommendation" in finding

    # Metadata quality finding is present
    titles = {item["title"] for item in payload["findings"]}
    assert any("metadata" in title.lower() for title in titles), f"Expected metadata finding, got: {titles}"

    # Laws-enforced list is documented
    assert "laws_enforced" in payload
    assert len(payload["laws_enforced"]) >= 1
