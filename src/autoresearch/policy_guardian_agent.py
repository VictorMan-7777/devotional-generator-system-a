"""policy_guardian_agent.py — Law-anchored compliance enforcement for DevG agents.

The policy guardian is an LLM agent whose authority comes exclusively from:
  1. The rules-laws constitution (Tier 0) — supreme governance
  2. The federal laws (Tier 1, L1–L16) — system-wide enforcement
  3. Any local laws in this repo's .laws/ directory (Tier 3)

LLM capability is required to actually read and evaluate agent artifacts against
the written law. A deterministic checker can only verify file existence and fail
counts — the cop needs to read what agents are producing and apply the law to it.

The LLM is the reading/reasoning capability. The written law is the only authority.
It does NOT invent or extrapolate rules. When a situation is not covered by written
law, the guardian records "no applicable law" rather than inferring a rule.

The guardian currently enforces:
  L2  — Evidence Gate: every session must produce a reviewable output artifact
  L15 — Retry/Stop Policy: identical failures must not be retried indefinitely (cap = 3)
  Scope Boundaries — agents must not act outside their defined role

Additional laws will be added as they are ratified.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.autoresearch.store import list_experiments, log_experiment


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class PolicyGuardianFinding:
    title: str
    severity: str
    law_citation: str  # e.g. "L15", "Art. 7", "L2"
    rationale: str
    recommendation: str


POLICY_GUARDIAN_PROFILE = {
    "role": "expert_policy_guardian",
    "authority": (
        "The policy guardian derives its authority from the rules-laws constitution (Tier 0) "
        "and the federal laws (Tier 1, L1–L16). It enforces only what is written. "
        "It does not interpret, extrapolate, or invent rules. "
        "When a situation is not addressed by written law, it records 'no applicable law' "
        "and escalates to human authority per Art. 1.2. "
        "The LLM capability is used to read and reason about agent output artifacts — "
        "the written law remains the sole authority for all findings."
    ),
    "scope_boundary": (
        "The policy guardian does NOT assess training quality, grade worker output, or evaluate "
        "whether an agent is improving. Those judgments belong to the relevant trainers and reviewers. "
        "The policy guardian only flags when an agent violates a written law or defined procedure. "
        "It reads actual agent artifacts to make this determination — not just file existence."
    ),
    "laws_currently_enforced": [
        "L2 — Evidence Gate and Mandatory Session Artifact",
        "L15 — Retry, Stop, and Budget Policy (federal maximum: 3 identical failures)",
        "Scope Boundary — agents acting outside their defined owned_surface",
        "LLM Cross-Provider Separation — evaluator AI must differ from generator AI (repo practice, proposed law pending ratification)",
    ],
    "agents_tracked_for_l2": [
        "outliner", "exposition_writer", "theological_reviewer", "library_trainer",
        "research_librarian", "pdf_workers", "proposal_reviewer", "cross_evaluator",
        "be_still_writer", "action_writer",
    ],
    "laws_not_yet_enforced_reason": (
        "Additional federal laws (L1, L3–L14, L16) are written and ratified but not yet "
        "wired into deterministic checks. Each law requires an explicit enforcement check "
        "before it is active in the guardian. This is intentional — the guardian enforces "
        "only what it can verify from observable artifacts."
    ),
}

DEFAULT_RULES_LAWS_ROOT = Path("/Volumes/claude-projects/projects/rules-laws")
DEFAULT_PROPOSED_RULES_DIR = DEFAULT_RULES_LAWS_ROOT / "proposed"

# Key law text excerpts — cited verbatim in findings for traceability
_LAW_TEXT = {
    "L2": (
        "L2 — Evidence Gate and Mandatory Session Artifact: "
        "Every session MUST produce a reviewable output artifact. No claim of completion, PASS, "
        "SUCCEEDED, or equivalent terminal-positive state may be accepted without verified artifact evidence. "
        "(Constitutional basis: Art. 7 — evidence integrity, Art. 11 — auditability)"
    ),
    "L15": (
        "L15 — Retry, Stop, and Budget Policy: "
        "Identical failures must not be retried indefinitely. A Federal maximum cap of 3 applies "
        "across all sessions for the same declared task scope and failure signature. "
        "When the cap is reached or an identical failure loop is detected, the system MUST halt and escalate. "
        "(Constitutional basis: Art. 1.2 — HALT on gaps, Art. 5 — human authority)"
    ),
    "Art.1.2": (
        "Art. 1.2 — Epistemic Humility: "
        "When the system encounters a situation not addressed by any applicable rule, it SHALL HALT "
        "and escalate to human authority. The system MUST NOT infer, extrapolate, or assume an answer from silence."
    ),
    "Art.7": (
        "Art. 7 — Evidence Integrity: "
        "All claims, completions, and state transitions require verified artifact evidence. "
        "Unverified claims are not admissible."
    ),
}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _latest_output_file(repo_root: Path, pattern: str) -> dict[str, Any]:
    matches = sorted((repo_root / "docs" / "system" / "outputs").glob(pattern))
    if not matches:
        return {}
    return _load_json(matches[-1])


def _latest_output_path(repo_root: Path, pattern: str) -> Path | None:
    matches = sorted((repo_root / "docs" / "system" / "outputs").glob(pattern))
    return matches[-1] if matches else None


def _guardrail_sources(repo_root: Path) -> dict[str, str]:
    local_rules = repo_root / ".laws"
    payload = {
        "tier0_constitution": str(DEFAULT_RULES_LAWS_ROOT / "constitution.md"),
        "tier0_index": str(DEFAULT_RULES_LAWS_ROOT / "index.md"),
        "tier1_federal_laws": str(DEFAULT_RULES_LAWS_ROOT / "phases" / "002-federal-laws.md"),
    }
    if local_rules.exists():
        payload["tier3_local_rules_root"] = str(local_rules)
    return payload


def _enforcement_scope(repo_root: Path) -> dict[str, Any]:
    local_rules = repo_root / ".laws"
    return {
        "enforce_constitutional_rules": True,
        "enforce_federal_rules": True,
        "enforce_local_rules": local_rules.exists(),
        "local_laws_present": local_rules.exists(),
        "note": (
            "Laws are still in development. The guardian enforces only what is written. "
            "Situations not covered by written law are escalated, not resolved by inference."
        ),
    }


# ── L2 — Evidence Gate ────────────────────────────────────────────────────────

# These output patterns map each training agent to the artifact file it is required
# to produce each cycle. If no artifact exists, that is an L2 violation.
_REQUIRED_ARTIFACTS: dict[str, str] = {
    "outliner": "*__devg__outliner-training-cycle.json",
    "exposition_writer": "*__devg__exposition-training-cycle.json",
    "theological_reviewer": "*__devg__theological-reviewer-report.json",
    "library_trainer": "*__devg__library-trainer-review.json",
    "policy_guardian": "*__devg__policy-guardian-report.json",
    "research_librarian": "*__devg__research-librarian-training-cycle.json",
    "pdf_workers": "*__devg__pdf-training-cycle.json",
    # LLM pipeline components — added 2026-03-17
    "proposal_reviewer": "*__devg__trainer-proposals.json",
    "cross_evaluator": "*__devg__cross-evaluation.json",
    # Content section trainers — added 2026-03-17
    "be_still_writer": "*__devg__be-still-training-cycle.json",
    "action_writer": "*__devg__action-writer-training-cycle.json",
}

# Required top-level fields each artifact must include for L2 compliance
_REQUIRED_ARTIFACT_FIELDS = ("status", "findings")


def _check_l2_evidence_gate(repo_root: Path) -> list[PolicyGuardianFinding]:
    """L2: Every training agent must produce a reviewable output artifact.

    A missing artifact = no evidence of session activity = L2 violation.
    An artifact missing required fields = incomplete evidence = L2 violation.
    """
    findings: list[PolicyGuardianFinding] = []
    outputs_dir = repo_root / "docs" / "system" / "outputs"

    for agent_name, pattern in _REQUIRED_ARTIFACTS.items():
        if agent_name == "policy_guardian":
            continue  # Self-exemption — we are the artifact being produced now

        matches = sorted(outputs_dir.glob(pattern))
        if not matches:
            findings.append(
                PolicyGuardianFinding(
                    title=f"L2 violation — {agent_name} has no session artifact on record",
                    severity="high",
                    law_citation="L2",
                    rationale=(
                        f"No output artifact found matching '{pattern}' for agent '{agent_name}'. "
                        f"{_LAW_TEXT['L2']}"
                    ),
                    recommendation=(
                        f"Run a {agent_name} training cycle to produce the required session artifact "
                        "before claiming that agent has been active or passing."
                    ),
                )
            )
            continue

        latest = _load_json(matches[-1])
        missing_fields = [
            field for field in _REQUIRED_ARTIFACT_FIELDS
            if field not in latest
        ]
        if missing_fields:
            findings.append(
                PolicyGuardianFinding(
                    title=f"L2 violation — {agent_name} artifact is missing required evidence fields",
                    severity="medium",
                    law_citation="L2",
                    rationale=(
                        f"The latest {agent_name} artifact ({matches[-1].name}) is missing "
                        f"required fields: {missing_fields}. "
                        f"{_LAW_TEXT['Art.7']}"
                    ),
                    recommendation=(
                        f"Ensure the {agent_name} agent produces artifacts with all required fields: "
                        f"{_REQUIRED_ARTIFACT_FIELDS}."
                    ),
                )
            )

    return findings


# ── L15 — Retry / Stop Policy ─────────────────────────────────────────────────

_L15_CAP = 3  # Federal maximum: 3 consecutive identical failures

# Workers tracked for L15 enforcement — those that produce scorable experiment records
_L15_TRACKED_WORKERS = (
    "outliner",
    "exposition_writer",
    "passage_researcher",
    "pdf_layout_engineer",
    "pdf_art_director",
    "research_librarian",
    "be_still_writer",
    "action_writer",
)


def _check_l15_retry_policy() -> list[PolicyGuardianFinding]:
    """L15: Identical failures must not be retried more than 3 times without escalation.

    Checks consecutive fail streaks per (worker, benchmark_reference) pair.
    A streak of 3+ identical failures with no method change = L15 violation.
    """
    findings: list[PolicyGuardianFinding] = []

    for worker_name in _L15_TRACKED_WORKERS:
        try:
            records = list_experiments(worker_name=worker_name)
        except Exception:
            continue

        # Group by benchmark_reference, check consecutive fail streaks
        streaks: dict[str, int] = {}
        for record in records:
            ref = str(record.benchmark_reference or "").strip()
            status = str(record.status or "").strip().lower()
            if status == "fail":
                streaks[ref] = streaks.get(ref, 0) + 1
            else:
                streaks[ref] = 0  # Reset on any non-fail

        violations = {ref: count for ref, count in streaks.items() if count >= _L15_CAP}
        for ref, count in violations.items():
            findings.append(
                PolicyGuardianFinding(
                    title=f"L15 violation — {worker_name} has {count} consecutive identical failures on '{ref}'",
                    severity="high",
                    law_citation="L15",
                    rationale=(
                        f"Worker '{worker_name}' has failed the same benchmark reference '{ref}' "
                        f"{count} consecutive time(s), reaching or exceeding the federal cap of {_L15_CAP}. "
                        f"{_LAW_TEXT['L15']}"
                    ),
                    recommendation=(
                        f"The {worker_name} trainer MUST halt retries on '{ref}' and escalate: "
                        "step down to an easier passage, change teaching method, or request human review. "
                        "Repeating the same failing approach is a procedure violation."
                    ),
                )
            )

    return findings


# ── Library quality (custom repo rule — not a ratified federal law) ───────────

def _check_library_quality(repo_root: Path) -> list[PolicyGuardianFinding]:
    """Custom repo rule: research cuttings must be real explanatory text, not metadata placeholders.

    Note: This is a repo-level quality standard enforced by DevG practice,
    not yet a ratified law in the rules-laws constitution. If it is not ratified,
    it cannot be enforced with law-level authority.
    """
    findings: list[PolicyGuardianFinding] = []
    library_review = _latest_output_file(repo_root, "*library-trainer-review.json")

    packet_summary = library_review.get("packet_summary", {}) if isinstance(library_review, dict) else {}
    metadata_excerpt_count = int(packet_summary.get("metadata_excerpt_count", 0) or 0)
    if metadata_excerpt_count > 0:
        findings.append(
            PolicyGuardianFinding(
                title="Repo quality rule — workers are being served metadata-shaped cuttings instead of real excerpts",
                severity="high",
                law_citation="repo-practice (not yet ratified law)",
                rationale=(
                    f"The latest library trainer review reports {metadata_excerpt_count} metadata-shaped excerpt(s). "
                    "DevG practice requires real explanatory cuttings — metadata shapes are not usable as research support."
                ),
                recommendation=(
                    "Do not count metadata placeholders as research support. "
                    "Require real cuttings with explanatory text before serving them to workers."
                ),
            )
        )

    actionable_requests = library_review.get("actionable_requests", []) if isinstance(library_review, dict) else []
    clearable = [
        item for item in actionable_requests
        if str(item.get("recommended_resolution", "")).strip() == "clear_and_serve_from_current_holdings"
    ]
    if clearable:
        findings.append(
            PolicyGuardianFinding(
                title=f"Repo quality rule — {len(clearable)} premature escalation(s): current holdings were sufficient but unused",
                severity="medium",
                law_citation="repo-practice (not yet ratified law)",
                rationale=(
                    f"{len(clearable)} active request(s) could be resolved from current holdings. "
                    "Workers must use the shelf before escalating to acquisition."
                ),
                recommendation=(
                    "Resolve these requests using current library holdings before filing new acquisition requests."
                ),
            )
        )

    return findings


# ── Theological gate (repo practice) ─────────────────────────────────────────

def _check_theological_gate(repo_root: Path) -> list[PolicyGuardianFinding]:
    findings: list[PolicyGuardianFinding] = []
    theological_review = _latest_output_file(repo_root, "*theological-reviewer-report.json")

    theological_fails = int(theological_review.get("book_validation", {}).get("theological_failures", 0) or 0)
    quote_fails = int(theological_review.get("quote_validation", {}).get("failed_days", 0) or 0)
    if theological_fails or quote_fails:
        findings.append(
            PolicyGuardianFinding(
                title="Repo practice — downstream content should remain gated until theological review clears",
                severity="medium",
                law_citation="repo-practice (not yet ratified law)",
                rationale=(
                    f"The theological reviewer reports {theological_fails} theological failure(s) and "
                    f"{quote_fails} quote-failure day(s). "
                    "Downstream workers (exposition, quote selection) should not be treated as trustworthy "
                    "while these failures are open."
                ),
                recommendation=(
                    "Keep theological review in the loop before treating downstream content as passing. "
                    "Clear theological failures before advancing the exposition writer."
                ),
            )
        )

    return findings


# ── LLM cross-provider separation (repo practice) ────────────────────────────

_KNOWN_PROVIDERS = ("claude", "openai", "codex")


def _check_llm_cross_provider_separation(repo_root: Path) -> list[PolicyGuardianFinding]:
    """Repo practice: the AI that evaluates training must differ from the AI that generated it.

    Verifies by reading the latest cross-evaluation artifact and checking that
    `evaluator_provider` is recorded and plausibly indicates a different system
    from the primary DEVG_LLM_PROVIDER setting.

    This is a repo practice, not a ratified law. It enforces the principle that
    no model may validate its own output.
    """
    import os
    findings: list[PolicyGuardianFinding] = []
    path = _latest_output_path(repo_root, "*__devg__cross-evaluation.json")
    if not path:
        # No artifact yet — L2 will catch the missing artifact; nothing extra here
        return findings

    data = _load_json(path)
    evaluation = data.get("evaluation") or {}
    evaluator_provider = str(evaluation.get("evaluator_provider") or "").strip().lower()

    if not evaluator_provider:
        findings.append(
            PolicyGuardianFinding(
                title="Repo practice — cross-evaluator did not record its provider identity",
                severity="medium",
                law_citation="repo-practice (LLM cross-provider separation)",
                rationale=(
                    f"The latest cross-evaluation artifact ({path.name}) does not include "
                    "an 'evaluator_provider' field. The cross-evaluator is required to declare "
                    "which AI system produced the evaluation so independence can be verified."
                ),
                recommendation=(
                    "Ensure build_cross_evaluation() prompts the model to declare its identity "
                    "and that the 'evaluator_provider' field is present in the returned JSON."
                ),
            )
        )
        return findings

    # Check that the evaluator is not the same as the primary provider
    primary = str(os.environ.get("DEVG_LLM_PROVIDER", "claude")).strip().lower()
    # Normalize: codex and openai are the same family
    def _family(p: str) -> str:
        return "openai" if p in ("codex", "openai") else p

    if _family(evaluator_provider) == _family(primary):
        findings.append(
            PolicyGuardianFinding(
                title="Repo practice violation — cross-evaluator used the SAME AI family as the primary provider",
                severity="high",
                law_citation="repo-practice (LLM cross-provider separation)",
                rationale=(
                    f"The cross-evaluator declared provider '{evaluator_provider}', which is the same "
                    f"AI family as the primary DEVG_LLM_PROVIDER='{primary}'. "
                    "The independence principle requires a DIFFERENT AI system for evaluation — "
                    "a model must not validate its own output."
                ),
                recommendation=(
                    "Verify that get_cross_llm_client() is returning the opposite provider. "
                    "If DEVG_LLM_PROVIDER=claude, the cross evaluator must use codex/openai, and vice versa. "
                    "Check that .env.local OPENAI_API_KEY is set and that the router is wired correctly."
                ),
            )
        )

    return findings


# ── Gap annotation — proposed rules ──────────────────────────────────────────

# Gaps the guardian currently enforces as "repo-practice" but that are not yet
# ratified laws. Each entry is (slug, title, proposed_text).
# The guardian writes annotations to the rules-laws/proposed/ area so gaps
# can enter the amendment process. It will not overwrite an existing annotation.
_LAW_GAPS: tuple[tuple[str, str, str], ...] = (
    (
        "devg-llm-cross-provider-separation",
        "Proposed Law — LLM Cross-Provider Separation for Training Evaluation (DevG)",
        (
            "# Proposed Law — LLM Cross-Provider Separation for Training Evaluation (DevG)\n\n"
            "**Proposed Tier**: Tier 1 — Federal / Global Law\n"
            "**Proposed Phase**: Phase 2\n"
            "**Status**: Proposed — gap identified by policy guardian\n"
            f"**Proposed**: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n"
            "**Origin**: DevG repo-practice — policy guardian gap annotation\n\n"
            "---\n\n"
            "## Proposed Rule Text\n\n"
            "**When an LLM is used in a content generation pipeline, the LLM evaluating that output "
            "MUST be from a different AI provider family than the generator.**\n\n"
            "- Applies to: all LLM-assisted generation + LLM trainer pairings in DevG.\n"
            "- 'Different AI provider family' means: Claude (Anthropic) vs OpenAI/Codex are different; "
            "GPT-4 and GPT-3.5 are the same family.\n"
            "- The cross-evaluator MUST declare its provider identity in output artifacts.\n"
            "- A trainer using the same AI family as the generator it evaluates is a violation.\n\n"
            "## Gap Rationale\n\n"
            "LLM models tend to agree with their own outputs. If the same AI generates training content "
            "and also evaluates whether that content is good, evaluation bias is structurally guaranteed. "
            "The cross-provider principle prevents this. It is currently enforced as a repo practice "
            "through get_cross_llm_client() but has no ratified law backing.\n"
        ),
    ),
    (
        "devg-library-quality-rule",
        "Proposed Law — Library Research Quality Gate (DevG)",
        (
            "# Proposed Law — Library Research Quality Gate (DevG)\n\n"
            "**Proposed Tier**: Tier 1 — Federal / Global Law\n"
            "**Proposed Phase**: Phase 2\n"
            "**Status**: Proposed — gap identified by policy guardian\n"
            f"**Proposed**: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n"
            "**Origin**: DevG repo-practice — policy guardian gap annotation\n\n"
            "---\n\n"
            "## Proposed Rule Text\n\n"
            "**All research cuttings served to content workers must be real explanatory excerpts — "
            "not metadata-shaped placeholders.**\n\n"
            "- Applies to: research librarian, library trainer, general librarian, and any agent "
            "that prepares resource bundles for content workers.\n"
            "- Metadata-shaped cuttings (entries that only contain bibliographic information without "
            "explanatory or contextual text) are not admissible as research support.\n"
            "- Workers must receive usable explanatory content before being assigned to produce "
            "passage-faithful output.\n\n"
            "## Gap Rationale\n\n"
            "The policy guardian currently enforces this as a repo practice but has no ratified "
            "law to cite. Premature escalation and metadata-quality violations are frequent "
            "training blockers that warrant formal enforcement authority.\n"
        ),
    ),
    (
        "devg-theological-gate-rule",
        "Proposed Law — Theological Gate Before Downstream Content (DevG)",
        (
            "# Proposed Law — Theological Gate Before Downstream Content (DevG)\n\n"
            "**Proposed Tier**: Tier 1 — Federal / Global Law\n"
            "**Proposed Phase**: Phase 2\n"
            "**Status**: Proposed — gap identified by policy guardian\n"
            f"**Proposed**: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n"
            "**Origin**: DevG repo-practice — policy guardian gap annotation\n\n"
            "---\n\n"
            "## Proposed Rule Text\n\n"
            "**No downstream content worker (exposition writer, quote selector) may be treated as "
            "passing while the theological reviewer's current cycle reports active failures.**\n\n"
            "- Applies to: exposition_writer, quote_selector, and any worker that depends on "
            "theologically sound content to do its job correctly.\n"
            "- The theological reviewer's gate must clear (zero theological failures, zero quote "
            "failed days) before downstream workers can be advanced in training.\n\n"
            "## Gap Rationale\n\n"
            "The policy guardian enforces this as a repo practice but has no ratified law to cite. "
            "Downstream quality depends on upstream theological integrity. This dependency should be "
            "a formal governance gate.\n"
        ),
    ),
)


def _annotate_gaps_to_proposed(proposed_dir: Path) -> list[str]:
    """Write gap annotations to the proposed rules area for unratified practices.

    Only writes if the annotation does not already exist (idempotent).
    Returns list of file paths written.
    """
    if not proposed_dir.exists():
        return []

    written: list[str] = []
    existing_files = list(proposed_dir.glob("*.md"))
    # A slug is already annotated if it appears anywhere in an existing filename
    existing_slugs = {p.stem.lower() for p in existing_files}
    # Also check if slug is a suffix of any existing stem (e.g. "002-devg-library-quality-rule")
    def _slug_already_present(slug: str) -> bool:
        return any(slug in stem for stem in existing_slugs)

    for slug, _title, content in _LAW_GAPS:
        safe_slug = slug.lower().replace(" ", "-")
        if _slug_already_present(safe_slug):
            continue  # Already annotated — do not overwrite

        # Find next available sequence number
        existing_nums = [
            int(p.name[:3])
            for p in proposed_dir.glob("*.md")
            if p.name[:3].isdigit()
        ]
        next_num = max(existing_nums, default=0) + 1
        filename = f"{next_num:03d}-{safe_slug}.md"
        out_path = proposed_dir / filename
        out_path.write_text(content, encoding="utf-8")
        written.append(str(out_path))

    return written


# ── Main report ───────────────────────────────────────────────────────────────

def build_policy_guardian_report(repo_root: Path) -> dict[str, Any]:
    rules_paths = _guardrail_sources(repo_root)
    findings: list[PolicyGuardianFinding] = []

    # Enforce written federal laws
    findings.extend(_check_l2_evidence_gate(repo_root))
    findings.extend(_check_l15_retry_policy())

    # Enforce repo practices (custom quality standards, not yet ratified laws)
    findings.extend(_check_library_quality(repo_root))
    findings.extend(_check_theological_gate(repo_root))
    findings.extend(_check_llm_cross_provider_separation(repo_root))

    # Annotate unratified gaps to the proposed rules area for the amendment process
    gap_annotations_written = _annotate_gaps_to_proposed(DEFAULT_PROPOSED_RULES_DIR)

    if not findings:
        findings.append(
            PolicyGuardianFinding(
                title="No violations detected — all enforced laws and practices are currently satisfied",
                severity="low",
                law_citation="all",
                rationale=(
                    "L2 (evidence gate) and L15 (retry policy) checks passed. "
                    "No library quality or theological gate violations found. "
                    "The guardian will continue monitoring."
                ),
                recommendation=(
                    "Keep the policy guardian in the monitoring loop. "
                    "Laws are still in development — additional enforcement checks will be added as laws are ratified."
                ),
            )
        )

    high_count = sum(1 for f in findings if f.severity == "high")
    medium_count = sum(1 for f in findings if f.severity == "medium")

    return {
        "reviewed_at_utc": _utc_now(),
        "rules_paths": rules_paths,
        "enforcement_scope": _enforcement_scope(repo_root),
        "trainer_profile": POLICY_GUARDIAN_PROFILE,
        "status": "reviewed",
        "finding_summary": {
            "total": len(findings),
            "high": high_count,
            "medium": medium_count,
        },
        "laws_enforced": list(POLICY_GUARDIAN_PROFILE["laws_currently_enforced"]),
        "gap_annotations_written": gap_annotations_written,
        "findings": [
            {
                "title": f.title,
                "severity": f.severity,
                "law_citation": f.law_citation,
                "rationale": f.rationale,
                "recommendation": f.recommendation,
            }
            for f in findings
        ],
    }


def log_policy_guardian_report(repo_root: Path) -> dict[str, Any]:
    payload = build_policy_guardian_report(repo_root)
    now = _utc_now()
    summary = payload.get("finding_summary", {})
    log_experiment(
        experiment_id="policy-guardian__current-cycle",
        worker_name="policy_guardian",
        benchmark_name="agent-guardrail-review",
        benchmark_reference="constitution + federal laws L2, L15",
        status="reviewed",
        attempted_change=(
            "Reviewed all training agents against the rules-laws constitution and federal laws. "
            "Enforced L2 (evidence gate) and L15 (retry policy) across all tracked workers."
        ),
        metrics={
            "finding_count": int(summary.get("total", 0) or 0),
            "high_severity_findings": int(summary.get("high", 0) or 0),
            "medium_severity_findings": int(summary.get("medium", 0) or 0),
        },
        learning_note=(
            "Policy guardian enforced written law: L2 (evidence gate) and L15 (retry/stop policy). "
            "Law citations are included in each finding for traceability. "
            "Repo practices are flagged separately from ratified laws."
        ),
        keep_decision="keep",
        created_at_utc=now,
        completed_at_utc=now,
    )
    return payload
