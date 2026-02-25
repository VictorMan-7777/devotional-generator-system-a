# Iteration Log — Devotional Generator System A

**Project**: devotional-generator-system-a
**Last Updated**: 2026-02-24

---

## Iteration 1 (2026-02-24)

**Status**: Initial planning complete — submitted for Gatekeeper review

**Inputs Received From Operator:**
- Project slug: `devotional-generator-system-a`
- Authoritative PRD: `../competition-2026/input/PRD_v16.md` (v16, 2026-02-23)
- Competition role: System A (builds first)
- Core requirements: all FRs from PRD v16 as stated
- Non-negotiable: TC-06 deterministic scoring equivalence
- Planner instructions: 5 explicit directives (PRD flags, constitution.md, MVP-first order)

**Files Created:**
- `index.md` — Navigation hub and overview
- `prd.md` — System A build plan with requirements mapping, PRD flags, acceptance criteria, MVP order
- `roadmap.md` — 4 phases with milestones, dependencies, risk register
- `iteration-log.md` — This file
- `constitution.md` — Python/TypeScript boundary definition (TC-04)
- `phases/001-data-model-and-inputs.md` — Phase 001 detailed plan with commit points
- `phases/002-template-system.md` — Phase 002 detailed plan with commit points
- `phases/003-kdp-pdf-export.md` — Phase 003 detailed plan with commit points
- `phases/004-validation-review-and-scoring-harness.md` — Phase 004 detailed plan with commit points
- `docs/system/outputs/2026-02-24__01__planner__initial-planning-complete.md` — Planning output artifact

**Key Decisions Documented:**
- Python/TypeScript boundary defined in `constitution.md` (TC-04 compliance)
- AC Scoring Harness identified as competition-critical first deliverable within Phase 004
- MVP-first execution order: schemas → mock RAG → templates → PDF engine → AC harness → validators → UI
- 4 PRD implementation-prescription flags raised for operator review (not blocking)
- 6 open assumptions documented for operator confirmation

**Rationale:**
First planning iteration. Authoritative source fully read (PRD v16, 1,152 lines). All FRs, TCs, ACs, and NFRs incorporated. Planner instructions honored: PRD flagged, constitution defined, MVP-first order specified, scoring harness prioritized, layer separation explicit.

**Submitted for review**: 2026-02-24

---

## Iteration 2 (2026-02-24)

**Status**: Operator corrections applied — submitted for Gatekeeper review

**Changes:**

1. **`constitution.md` — APPROVED**
   - Marked as operator-approved (v1.1)
   - Section 2.4 (AC Scoring Harness) updated to reflect corrected spec extraction protocol
   - Approval statement added verbatim

2. **Assumption A-01 — CORRECTED** (affects `prd.md`, `phases/004`, `constitution.md`)
   - Original: shared external `ac-test-spec.yaml` file delivered to both systems
   - Corrected: No shared external file. Spec is derived from PRD_v16.md (the sole source of truth).
   - System A derives and materializes spec to `../competition-2026/outputs/ac-test-spec.extracted.yaml`
   - spec_hash = SHA256(extracted yaml) — recorded in every scoring output
   - Matching spec_hash between systems confirms equivalent PRD interpretation; mismatch is a competition finding

3. **Competition artifact structure — CREATED** (`../competition-2026/`)
   - `outputs/README.md` — append-only policy, naming convention, expected artifacts
   - `notes/README.md` — journal policy, entry types, naming convention
   - `notes/2026-02-24__01__post-planner__system-a-planning-complete.md` — first journal entry

4. **`phases/004` — Updated**
   - Removed references to shared external spec file
   - Replaced with PRD-derived spec extraction protocol
   - CP1 updated: `spec_extractor.py` writes derived YAML to `../competition-2026/outputs/`
   - `spec_extractor.py` added to outputs list

5. **`prd.md` — Updated**
   - Assumption A-01 corrected and strikethrough applied to superseded content
   - Competition Input Asymmetry table added (System A receives seed files; Agent Zero receives PRD only)
   - Competition Artifact Structure section added

**Rationale:** Operator provided four explicit responses to the Planner's output: constitution approval, A-01 protocol correction, competition artifact structure enforcement, and Gatekeeper submission request. All changes applied before Gatekeeper review.

**Submitted for review**: 2026-02-24

---

## Iteration 3 (2026-02-24)

**Status**: Gatekeeper APPROVE received — planning complete; Phase 001 authorized

**Changes:**

1. **`phases/004` — Harness architecture updated (Gatekeeper binding clarification)**
   - Builder implements infrastructure only: spec loader, hash verifier, check dispatch engine
   - Canonical evaluation spec authored by PRD Designer + Operator at evaluation time (not Builder)
   - `spec_extractor.py` removed from Builder scope entirely
   - Provisional dev spec added (`scoring/draft_spec/provisional-dev-spec.yaml`; `authority: provisional-development-only`)
   - Provisional spec explicitly excluded from `../competition-2026/outputs/`
   - Harness is spec-agnostic: accepts any conformant spec at any operator-provided path
   - Sub-phase A acceptance criteria updated to reflect infrastructure-only scope

2. **`constitution.md` (v1.2) — Section 2.4 updated**
   - Builder/PRD Designer scope boundary documented
   - Provisional dev spec governance rule added

3. **Competition notes — Gatekeeper decision recorded**
   - `../competition-2026/notes/2026-02-24__02__gatekeeper__iteration-2-approved-phase-001-authorized.md`

**Rationale:**
Gatekeeper APPROVE with clarification: harness infrastructure is Builder's work; canonical scoring rules are PRD Designer + Operator's work. Preserves evaluation fairness by preventing Builder from encoding implementation choices into the evaluation spec.

**Planning phase complete. Phase 001 Builder execution authorized. No further planning iterations required.**

---

## Phase 001 Builder Execution — 2026-02-24

**Status**: COMPLETE — 2026-02-24

**Commits (chronological):**

| Hash | Message |
|------|---------|
| `e70b22e` | CP1: project scaffold |
| `e0eb72e` | CP2: core pydantic schemas |
| `c5b77bf` | CP3: mock RAG interface contract |
| `fdff29c` | CP4: scripture retrieval (initial; had git staging defect) |
| `57615a1` | CP4-fix: correct bolls.life endpoint and response parsing |
| `baa7cc2` | CP5: series registry — sqlite persistence, de-duplication, author distribution |

**Test suite**: 102 tests, all passing (CP1–CP5 cumulative)

**Notable findings:**
- Bolls.life API endpoint changed: `/get-text/` → `/get-verse/` for verse-level requests; response format changed from JSON list to JSON dict with no book/chapter fields. Fix applied in `57615a1`. Competition journal entry written (`competition-2026/notes/2026-02-24__03__...`). PRD Appendix A update flagged for future pass.
- Git staging defect in CP4: `git reset --soft HEAD~1` + edit + `git commit` without re-staging caused initial CP4 commit to contain pre-fix code. Resolved by subsequent fix commit before CP5.

**Build reports (automated-builder/docs/system/outputs/):**
- CP1: `2026-02-24__02__builder__phase-001-cp1-build-report.md`
- CP2: `2026-02-24__03__builder__phase-001-cp2-build-report.md`
- CP3: `2026-02-24__04__builder__phase-001-cp3-build-report.md`
- CP4: `2026-02-24__05__builder__phase-001-cp4-build-report.md`
- CP5: `2026-02-24__06__builder__phase-001-cp5-build-report.md`

**Phase 001 APPROVED by operator — 2026-02-24. Phase 002 planning initiated.**

---

## Phase 002 Builder Execution — 2026-02-24

**Status**: COMPLETE — 2026-02-24

**Commits (chronological):**

| Hash | Message |
|------|---------|
| `ddb8c28` | CP1: document representation schema — frozen contract for PDF engine |
| `1d2303e` | CP2: section renderers — all 6 daily sections plus sending prompt and day 7 |
| `a1e9bad` | CP3: front matter renderers and static templates |
| `ba139ae` | CP4: rendering engine — end-to-end document representation from mock devotional book |

**Test suite**: 123 tests added in Phase 002; 225 cumulative (Phase 001 + 002), all passing

**Notable findings:**
- `src/rendering/day7.py` listed in the phase plan Outputs table but not in CP staging. Resolution: all section renderers (including Day 7 and sending prompt) consolidated in `src/rendering/sections.py` per CP2 staging, which is authoritative.
- `DailyDevotional.day_number` constraint (`le=7`) prevents creating 12-day fixtures for TOC tests using real Pydantic models. Resolution: `_DayStub` dataclass used in `tests/test_front_matter.py` for TOC tests (accesses only `day_number` and `day_focus`).
- `templates/introduction_sunday.md` drafted by Builder; operator-approved 2026-02-24 (minor revision: final sentence italicized).

**Build reports (automated-builder/docs/system/outputs/):**
- CP1: `2026-02-24__07__builder__phase-002-cp1-build-report.md`
- CP2: `2026-02-24__08__builder__phase-002-cp2-build-report.md`
- CP3: `2026-02-24__09__builder__phase-002-cp3-build-report.md`
- CP4: `2026-02-24__10__builder__phase-002-cp4-build-report.md`

**Phase 002 APPROVED by operator — 2026-02-24. Phase 003 planning initiated.**

---

## Phase 003 Planning — 2026-02-24

**Status**: APPROVED — operator decisions confirmed; CP1 execution authorized

**Decision gate (pre-CP1):**

| Decision | Selected |
|----------|----------|
| PDF library | `pdf-lib` (explicit layout control; required for FR-63 footnote placement and FR-85 two-pass margins) |
| Fonts | EB Garamond Regular/Bold/Italic (OFL, classical serif, Google Fonts) |
| TypeScript invocation | `tsx` subprocess (no compile step; Python calls `npx tsx ui/pdf/engine.ts`) |

**Decision record**: `automated-builder/docs/system/outputs/2026-02-24__11__builder__phase-003-pre-cp1-decisions.md`

**Phase 003 CP map:**

| CP | Description | Build Report |
|----|-------------|--------------|
| CP1 | TypeScript scaffold + EB Garamond fonts | `__12__` |
| CP2 | Margin calculation + compliance checker | `__13__` |
| CP3 | Block-type renderers | `__14__` |
| CP4 | PDF engine end-to-end | `__15__` |
| CP5 | Python-TypeScript integration + `constitution.md` v1.3 | `__16__` |

**Phase 003 execution authorized — 2026-02-24. Proceeding to CP1.**

---

## Phase 003 Builder Execution — 2026-02-24

**Status**: COMPLETE — 2026-02-24

**Commits (chronological):**

| Hash | Message |
|------|---------|
| `1537d3c` | CP1: TypeScript project scaffold and bundled EB Garamond fonts |
| `bf373cf` | CP2: KDP margin calculation and compliance checker |
| `5e15949` | CP3: Block-type PDF renderers — all 12 DocumentBlock types |
| `99853fc` | CP4: PDF engine — DocumentRepresentation → KDP-compliant 6×9 PDF |
| `e8a91ae` | CP5: Python-TypeScript PDF integration + constitution.md v1.3 |

**Test suite**: 70 TypeScript tests + 5 Python integration tests added in Phase 003. 300 total (230 Python + 70 TypeScript), all passing.

**Notable findings:**
- `@pdf-lib/fontkit` must be registered before embedding custom TTF fonts: `doc.registerFontkit(fontkit)`. Discovered via `FontkitNotRegisteredError` in tests.
- `wrapText('')` returned `['']` — required empty-string guard added to `wrapText()`.
- 7-day devotional produces ~12 PDF pages, below KDP commercial minimum of 24. `page_count_warning: true` is correct FR-93 behavior (warning ≠ violation).
- `pnpm.onlyBuiltDependencies: ["esbuild"]` required in `package.json` for esbuild postinstall.

**Build reports (automated-builder/docs/system/outputs/):**
- Pre-CP1: `2026-02-24__11__builder__phase-003-pre-cp1-decisions.md`
- CP1: `2026-02-24__12__builder__phase-003-cp1-build-report.md`
- CP2: `2026-02-24__13__builder__phase-003-cp2-build-report.md`
- CP3: `2026-02-24__14__builder__phase-003-cp3-build-report.md`
- CP4: `2026-02-24__15__builder__phase-003-cp4-build-report.md`
- CP5: `2026-02-24__16__builder__phase-003-cp5-build-report.md`

**Phase 003 COMPLETE — 2026-02-24. Halting and awaiting Phase 004 instruction.**
