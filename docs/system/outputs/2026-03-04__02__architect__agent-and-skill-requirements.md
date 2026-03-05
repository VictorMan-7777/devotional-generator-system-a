# Architect Output — Agent & Skill Requirements

**Date**: 2026-03-04
**Sequence**: 02
**Context**: architect
**Description**: agent-and-skill-requirements
**Project**: devotional-generator-system-a

---

## Summary

Analysis of agents and skills needed to complete the Devotional Generator system, derived from review of planning documents (phases 001–004) and the current build state. Identifies what has been built, what remains, and the specific capability required for each remaining deliverable.

---

## Current Build State

### Completed

| Layer | Files |
|---|---|
| Phase 001 — Data models, schemas, mock RAG, scripture retrieval, series registry | `src/models/`, `src/interfaces/`, `src/scripture/`, `src/registry/` |
| Phase 002 — Document representation, rendering engine, all section renderers, front matter | `src/models/document.py`, `src/rendering/` |
| Phase 003 — TypeScript PDF engine (margins, compliance, blocks, engine, fonts) | `ui/pdf/` |
| Phase 004-B — Theological validators (exposition, be still, action steps, prayer, doctrinal, modernization, rewrite router, orchestrator) | `src/validation/` |
| Generation layer — LLM generators, real section generator, prayer/exposition generators | `src/generation/` |
| RAG layer — Quote catalog, exposition RAG, semantic RAG, index builder, retrieval engine, corpus, grounding | `src/rag/` |
| Artifact stores — Grounding map store, prayer trace store, audit | `src/grounding_store/`, `src/prayer_trace_store/`, `src/audit/` |
| API layer — Export gate, generation pipeline, PDF export integration | `src/api/` |
| LLM interfaces | `src/llm/` |

### Not Yet Built

| Deliverable | Phase | Priority |
|---|---|---|
| AC Scoring Harness (`scoring/`) | 004-A CP1 | Critical — competition instrument |
| Human Review UI (`ui/src/`) | 004-C CP3 | High |
| Encryption at rest (`src/security/`) | 004-D CP5 | High |
| Database socket / persistence layer (`src/persistence/`) | Migration plan | High |
| End-to-end system test (`tests/system/test_volume_1.py`) | 004-D CP8 | Blocking for completion |

---

## Agent & Skill Requirements by Deliverable

---

### 1. AC Scoring Harness

**Deliverable:** `scoring/` directory — the competition measurement instrument.

**Why critical:** This is the structural foundation of the competition. It was specified to be built first within Phase 004. It is the only major Phase 004 deliverable with zero implementation.

**Files required:**
- `scoring/harness.py` — single public `score(content, spec_path)` entry point
- `scoring/spec_loader.py` — loads and validates YAML spec from any operator-provided path
- `scoring/spec_verifier.py` — SHA-256 hash verification before every run; raises `SpecIntegrityError` on mismatch
- `scoring/ac_checks.py` — registry of check functions for all 9 check types; no LLM inference
- `scoring/models.py` — `ScoredContent`, `ACResult`, `ScoringResult` dataclasses
- `scoring/draft_spec/provisional-dev-spec.yaml` — labeled `authority: provisional-development-only`
- `tests/scoring/test_harness.py`
- `tests/scoring/test_spec_integrity.py`

**Required check types (all deterministic, no LLM inference — TC-06):**

| Check type | Examples |
|---|---|
| `word_count` | Exposition 500–700w (AC-10), prayer 120–200w (AC-31) |
| `structural` | 4-paragraph exposition structure (AC-01), 3–5 Be Still prompts (AC-12) |
| `pronoun_check` | "you/your" as subject in exposition (AC-09) |
| `artifact_completeness` | Grounding Map present and non-empty (AC-19), Prayer Trace Map (AC-27) |
| `field_presence` | Prayer addressed to named Trinity person (AC-21) |
| `keyword_check` | Connector phrase in Action Steps (AC-18) |
| `count_range` | 1–3 Action Steps (AC-19) |
| `approval_status` | All sections approved (AC-37) |
| `flag_from_validator` | Pass/fail mirrors FR-74–77 `ValidatorAssessment` result (AC-33) |

**Agent constraints:**
- Zero imports from any generation module — isolation is structural, not just conventional
- `score()` function must be spec-agnostic: accepts any conformant YAML at any path
- Spec format is a fixed contract (documented so PRD Designer can author canonical spec without code changes)
- `ScoringResult` must contain: `spec_version`, `spec_hash`, `authority`, `scored_at`, `total_acs`, `passed`, `failed`, `results`, `overall_pass`

---

### 2. Human Review UI

**Deliverable:** `ui/src/` — local TypeScript/React web UI for operator review, editing, and approval.

**Files required:**
- `ui/src/App.tsx`
- `ui/src/pages/ReviewPage.tsx`
- `ui/src/components/DayCard.tsx` — per-day review card with all 6 sections
- `ui/src/components/SectionEditor.tsx` — editable section with approval control (PENDING → APPROVED)
- `ui/src/components/GroundingMapPanel.tsx` — side panel showing 4-entry Grounding Map alongside exposition (FR-79a)
- `ui/src/components/SnapshotManager.tsx` — 3 saved states per section; restore reverts content (NFR-02)
- `ui/src/components/DiversityReport.tsx` — author diversity report display
- `ui/src/components/AlertPanel.tsx` — quote shortage and scripture shortage alerts
- `ui/src/api/client.ts` — TypeScript API client for Python FastAPI
- `ui/src/__tests__/` — Vitest unit tests + Playwright E2E tests

**Agent constraints:**
- WCAG AA compliance required (NFR-04): keyboard accessible, 4.5:1 color contrast, screen reader labels, focus management on modals
- Export must be blocked in publish-ready mode when any section has `approval_status = PENDING`
- Grounding Map panel is a UI-only artifact — it is not in the PDF (Grounding Map is never rendered into `DocumentRepresentation`)
- Snapshot list shows up to 3 states per section per day; restore is per-section
- Day 7 Track A and Track B must have equal visual weight (FR-96, D056)
- Quote shortage alert: display available candidates even if < 3; allow operator manual entry with Turabian attribution fields

---

### 3. Encryption at Rest

**Deliverable:** `src/security/encryption.py` — AES-256 file-level encryption for the registry, workspace, and ChromaDB data.

**Files required:**
- `src/security/encryption.py`
- `tests/security/test_encryption.py`

**Agent constraints:**
- Primary key source: macOS Keychain Services (currently local-only deployment)
- Fallback: operator passphrase → PBKDF2 key derivation
- Encrypted: Series Registry SQLite file, workspace directory, Quote Catalog index, operator-provided import files
- NOT encrypted: exported PDFs (KDP deliverable — must open without passphrase)
- The key backend must be abstracted so it can be swapped to cloud KMS for web deployment (see web deployment requirements artifact)

---

### 4. Database Socket / Persistence Layer

**Deliverable:** `src/persistence/` — hexagonal port/adapter persistence layer enabling provider-swappable database backends.

**Files required (new):**
- `src/persistence/socket.py` — `DatabaseSocket` Protocol (stable contract for all business logic)
- `src/persistence/factory.py` — builds socket instance from config
- `src/persistence/config.py` — typed config model and loader
- `src/persistence/adapters/sqlite_adapter.py`
- `src/persistence/adapters/postgres_adapter.py`
- `src/persistence/adapters/legacy_json_adapter.py` — read bridge for existing JSON artifacts
- `src/persistence/schema/models.py` — SQLAlchemy ORM for all tables
- `src/persistence/migration/runner.py` — `swap_provider` orchestration
- `src/persistence/migration/verify.py` — row-count and checksum verification
- `scripts/db/swap_provider.py` — operator CLI (`--from`, `--to`, `--dry-run`)
- `tests/persistence/test_socket_contract.py` — contract tests every adapter must pass
- `tests/persistence/test_swap_migration.py` — end-to-end swap tests

**Files to modify (refactor existing):**
- `src/registry/registry.py` — delegate persistence to injected `DatabaseSocket`
- `src/grounding_store/store.py` — route `save/load/exists` via socket backend
- `src/prayer_trace_store/store.py` — same refactor
- `src/validation/orchestrator.py` — resolve artifacts through socket-backed stores
- `src/api/generation_pipeline.py` — build persistence from factory and inject consistently
- `pyproject.toml` — add `alembic`, `psycopg[binary]` (optional)

**Agent constraints (from adversarial revision 3 — `__07__` document):**
- `try/finally` safety: `src` initialization and snapshot cleanup must never raise `UnboundLocalError`
- Exactly-once semantics are cursor-range-based (immutable PK window), not batch-shape-based
- Cross-volume quote dedup remains deterministic with explicit override path (structural `quote_use_overrides` table)
- Single-active-provider invariant enforced by concrete DB constraints:
  - Postgres: partial unique index `WHERE state = 'active'`
  - SQLite: singleton row table `active_provider_singleton(id CHECK(id=1), provider_name UNIQUE)`
- Migration lock includes TTL, owner token, and fencing token monotonic counter
- All state-mutating operations validate fencing token (prevents stale-owner writes)
- All terminal outcomes persisted to `migration_events` table with secret redaction
- Dry-run must close all open snapshot transactions
- `legacy_json` is read-only bridge; blocked as migration target at runtime

**Database schema (from migration plan):**
`series`, `volumes`, `quote_uses`, `quote_use_overrides`, `scripture_uses`, `grounding_maps`, `prayer_trace_maps`, `devotional_books`, `devotional_days`, `section_states`, `section_snapshots`, `provider_states`, `migration_events`, `schema_migrations`

---

### 5. End-to-End System Test

**Deliverable:** `tests/system/test_volume_1.py` — full pipeline test generating Volume 1 with real RAG.

**Agent constraints:**
- Must generate a complete 6-day devotional with all sections using real RAG
- All FR-74–77 validators must pass for generated content
- AC Scoring Harness must score all 43 ACs (requires harness to be built first — hard dependency)
- PDF export must produce KDP-compliant output with `complianceResult.passes === true`
- Registry must be updated with all quotes and scriptures used; backup created

---

### 6. Operator-Only Deliverables (Human Required — Not Agent Work)

These cannot be delegated to an agent:

| Deliverable | Reason | Blocking |
|---|---|---|
| Canonical AC scoring spec (YAML) | Authored by PRD Designer + Operator per governance constraint (Phase 004-A architecture note) | Blocks competition evaluation scoring |
| Theological smoke test approval (`tests/validation/smoke_tests.py`) | Operator must review known-bad inputs and confirm guardrails trigger correctly (Phase 004 CP7) | Blocks CP7 commit |
| Font selection | Operator selects body text and heading fonts from presented options (Phase 003 Step 2) | Already unblocked — Phase 003 is complete; fonts may already be selected |
| `templates/introduction_sunday.md` | Operator-authored static content; planner drafts, operator finalizes | Already in codebase — confirm operator has reviewed |
| `templates/offer_page.md` | Same as above | Same |

---

## Dependency Order

```
AC Scoring Harness (no deps — build first)
    |
    +-- End-to-End System Test (requires harness + real RAG)

Database Socket Layer (no deps on above — can parallelize)
    |
    +-- Encryption at Rest (can use socket for key registry)

Human Review UI (no deps on scoring harness — can parallelize)
    |
    +-- End-to-End System Test (requires UI for approval workflow test)

Operator: canonical AC spec (unblocks competition evaluation only — not build completion)
```

---

## Summary Table

| Deliverable | Agent type | Operator gate required |
|---|---|---|
| AC Scoring Harness | Python builder — deterministic, zero-inference, isolated | No (provisional spec only) |
| Human Review UI | TypeScript/React builder — WCAG AA, async API client | No (build); Yes (smoke test approval) |
| Encryption at rest | Python security engineer | No |
| Database socket layer | Python database architect — SQLAlchemy, migration safety | No |
| End-to-end system test | Python integration test engineer | Yes (smoke tests, canonical spec) |
| Canonical AC scoring spec | PRD Designer + Operator | This IS the operator gate |

---

*Output artifact created. Derived from phase plans 001–004 and adversarial migration plan revisions __04__–__07__.*
