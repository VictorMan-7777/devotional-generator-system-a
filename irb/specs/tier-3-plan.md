# IRB Tier 3 Plan — Devotional Generator System A

**Spec ID**: irb-tier-3
**Version**: 1.0.0
**Date**: 2026-03-05
**Status**: PLAN (pending operator review before Phase B build)

---

## Discovery Summary

| Item | Finding |
|------|---------|
| Existing IRB tiers | Tier 1 (structural/build), Tier 1.5 (hygiene/security), Tier 2 (integration/smoke) |
| Tier 2 explicit note | "Adversarial simulation belongs to Tier 3" |
| Test suite | 724 tests passing; pytest + mypy; Python 3.11 + Pydantic v2 |
| Runner infrastructure | No existing `scripts/irb/` — Tier 3 runner must be built from scratch |
| Validation layer | `check_doctrinal`, `validate_exposition`, `validate_be_still`, `validate_prayer`, `validate_action_steps`, `route()` |
| Schema invariants | GroundingMap (exactly 4 entries), PrayerTraceMap (traceable source_types only) |
| Rewrite routing | attempt 1 → AUTO_REWRITE; attempt 2+ → HUMAN_REVIEW |
| Artifact naming | `YYYY-MM-DD__NN__ROLE__description.{md,json}` in `docs/system/outputs/` |
| AC Scoring Harness | Not yet built (Phase 004A out-of-scope) |

---

## Purpose Statement

IRB Tier 3 certifies that System A's validation, guardrail, and schema layers are **adversarially robust**: they correctly reject malformed, malicious, and edge-case inputs without crashing, silently skipping checks, or producing incorrect pass/fail signals. Tier 3 also verifies:
- The runner itself follows repo hygiene rules (rg over grep)
- All existing output artifacts comply with the naming policy
- The repo is not mutated by the runner

Tier 3 is **SINGLE-AGENT**, **OFFLINE**, and **DETERMINISTIC**. No LLM calls. No network access.

---

## Threat Model

| Threat | Attack Vector | Mitigation Under Test |
|--------|--------------|----------------------|
| Doctrinal bypass | Prosperity gospel / works-merit language injected into generated text | `check_doctrinal()` must flag with correct reason_code |
| Schema smuggling | GroundingMap or PrayerTraceMap constructed with invalid entry counts or source types | Pydantic validators must raise `ValidationError` |
| Rewrite loop escape | Caller supplies invalid attempt numbers or expects wrong routing signal | `route()` must return correct `RewriteSignal` for all attempt counts |
| Prompt injection | Injection-like strings in topic/title fields | Pydantic models must accept safely (no crash); validators handle downstream |
| Validator crash | Boundary inputs (empty lists, extremal word counts) | Validators must return structured assessments, never raise unhandled exceptions |
| Runner self-contamination | Runner uses `grep` subprocess instead of `rg`/Python re | Self-scan of scripts/irb/ for grep subprocess calls |
| Naming policy drift | New output artifact breaks NN or kebab-case convention | Scan docs/system/outputs/ for non-conforming files |
| Repo mutation | Runner writes to tracked files or alters git state | Pre/post git status delta must be empty |

---

## Check Catalog

### Category: REPO (repository integrity)

| ID | Name | Blocking | Description |
|----|------|----------|-------------|
| T3-REPO-001 | no_grep_in_irb_scripts | false | `scripts/irb/*.py` must not invoke `grep` via subprocess. Evidence: Python source scan. Advisory (scripts may not exist before runner build). |
| T3-REPO-002 | artifact_naming_policy | true | Every `.md` and `.json` in `docs/system/outputs/` must match `YYYY-MM-DD__NN__ROLE__desc.ext`. Evidence: file list + pattern match result. |

### Category: DOCTRINAL (adversarial guardrail simulation)

| ID | Name | Blocking | Description |
|----|------|----------|-------------|
| T3-DOC-001 | prosperity_gospel_flagged | true | `check_doctrinal(prosperity_text)` returns ≥1 assessment with `reason_code == DOCTRINAL_PROSPERITY_GOSPEL`. |
| T3-DOC-002 | works_merit_flagged | true | `check_doctrinal(works_text)` returns ≥1 assessment with `reason_code == DOCTRINAL_WORKS_MERIT`. |
| T3-DOC-003 | clean_text_passes | true | `check_doctrinal(clean_text)` returns `[]` (no false positives). |
| T3-DOC-004 | combined_adversarial | true | Text with both violation types returns 2 assessments (one per category). |

### Category: SCHEMA (invariant adversarial validation)

| ID | Name | Blocking | Description |
|----|------|----------|-------------|
| T3-SCH-001 | grounding_map_rejects_three_entries | true | `GroundingMap(entries=[...3 entries...])` raises `ValidationError`. |
| T3-SCH-002 | grounding_map_rejects_empty_entries | true | `GroundingMap(entries=[])` raises `ValidationError`. |
| T3-SCH-003 | prayer_trace_map_rejects_invalid_source | true | `PrayerTraceMap` with entry `source_type="llm_hallucination"` raises `ValidationError`. |
| T3-SCH-004 | prayer_trace_map_accepts_valid_types | true | PrayerTraceMap with all valid source types (`scripture`, `exposition`, `be_still`) creates successfully. |

### Category: REWRITE (routing logic adversarial)

| ID | Name | Blocking | Description |
|----|------|----------|-------------|
| T3-RWR-001 | attempt_one_auto_rewrite | true | `route(failing_assessments, attempt_number=1).signal == AUTO_REWRITE`. |
| T3-RWR-002 | attempt_two_human_review | true | `route(failing_assessments, attempt_number=2).signal == HUMAN_REVIEW`. |
| T3-RWR-003 | attempt_three_still_human_review | true | `route(failing_assessments, attempt_number=3).signal == HUMAN_REVIEW`. |

### Category: ADVERSARIAL (simulation)

| ID | Name | Blocking | Description |
|----|------|----------|-------------|
| T3-ADV-001 | injection_topic_accepted_safely | true | `DevotionalInput(topic="; DROP TABLE devotionals; --")` creates model without crash. |
| T3-ADV-002 | exposition_validator_no_crash_on_long_text | true | `validate_exposition(ExpositionSection(text=10_000_char_string, ...))` returns list, does not raise. |
| T3-ADV-003 | be_still_validator_no_crash_on_empty_prompts | true | `validate_be_still(BeStillSection(prompts=[]))` returns list with FAIL assessments, does not raise. |

### Category: GUARD

| ID | Name | Blocking | Description |
|----|------|----------|-------------|
| T3-GUARD-001 | repo_mutation_guard | true | `git status --porcelain` output identical before and after all checks. |

**Total checks: 18 (16 blocking, 2 advisory)**

---

## Runner Design

**Entry point**: `scripts/irb/run_tier3.py`
**Execution**: `python scripts/irb/run_tier3.py [--target REPO_ROOT]`
**Exit codes**:
- `0` — CERTIFIED (all blocking checks pass)
- `1` — FAILED (one or more blocking checks fail)
- `2` — ERROR (runner itself errors)

**Architecture**:
- Pure Python stdlib + project venv imports (no external tools in subprocess except `git`)
- Each check is a Python function returning `CheckResult` dataclass
- Evidence collected as structured dict per check
- All checks run sequentially; blocking failures recorded but runner continues (non-halting)
- Mutation guard runs in `finally` block

**Imports from project**:
- `src.validation.doctrinal.check_doctrinal`
- `src.validation.be_still.validate_be_still`
- `src.validation.exposition.validate_exposition`
- `src.validation.rewrite_router.route`
- `src.models.artifacts.GroundingMap, PrayerTraceMap, PrayerTraceMapEntry, GroundingMapEntry`
- `src.models.devotional.DevotionalInput, BeStillSection, ExpositionSection`
- `src.models.validation.ValidatorAssessment`
- `pydantic.ValidationError`

---

## Artifact Outputs

| Artifact | Path | Format |
|----------|------|--------|
| Markdown report | `docs/system/outputs/YYYY-MM-DD__NN__builder__irb-tier-3-report.md` | Markdown |
| JSON results | `docs/system/outputs/YYYY-MM-DD__NN__builder__irb-tier-3-results.json` | JSON |

NN is computed dynamically by scanning existing files in `docs/system/outputs/` — not hardcoded.

---

## Test Plan (Phase C)

**File**: `tests/irb/test_tier3_runner.py`

| Test | What it verifies |
|------|-----------------|
| `test_check_result_structure` | `CheckResult` dataclass has required fields: check_id, category, passed, evidence, detail |
| `test_doctrinal_checks_return_correct_results` | Each T3-DOC check function returns expected pass/fail |
| `test_schema_invariant_checks` | T3-SCH checks return correct pass/fail |
| `test_rewrite_routing_checks` | T3-RWR checks return correct signals |
| `test_adversarial_simulation_checks` | T3-ADV checks do not raise; return correct structure |
| `test_compute_next_nn` | NN computation is correct for various existing file sets |
| `test_runner_json_schema` | Full runner produces JSON with required top-level fields |

---

## Determinism Guarantees

1. All checks use fixed inputs (no external state)
2. No LLM calls, no network, no random seed
3. Checks execute sequentially (no parallel state)
4. Git status captured with `git status --porcelain` (stable output format)
5. Output filenames use `datetime.date.today()` — same-day runs increment NN, not overwrite
6. JSON report uses `sort_keys=True` for canonical serialization

---

## Questions for Operator (if any)

None. Discovery is complete; threat model and check catalog are self-contained.

---

## STOP POINT #1 Deliverables

**Check list (18 checks)**:
- T3-REPO-001, T3-REPO-002
- T3-DOC-001, T3-DOC-002, T3-DOC-003, T3-DOC-004
- T3-SCH-001, T3-SCH-002, T3-SCH-003, T3-SCH-004
- T3-RWR-001, T3-RWR-002, T3-RWR-003
- T3-ADV-001, T3-ADV-002, T3-ADV-003
- T3-GUARD-001

**Files to be created in Phase B**:
1. `irb/specs/tier-3-spec.yaml` — machine-readable spec
2. `scripts/irb/__init__.py` — package marker
3. `scripts/irb/run_tier3.py` — runner (~350 lines)
4. `tests/irb/__init__.py` — package marker
5. `tests/irb/test_tier3_runner.py` — tests (~120 lines)

**No open questions.** Proceeding to Phase B.
