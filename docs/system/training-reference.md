# Training Reference — DevG Autoresearch System

**Last updated:** 2026-03-18
**Source:** `src/autoresearch/` source files; `docs/system/devg-autoresearch-implementation-plan.md`

This document describes every worker in the DevG autoresearch training system: what each trainer owns, how it evaluates, what rubrics it applies, and its relationship to PRD requirements.

**Key architectural note:** All positions called "agent" make real AI calls (Claude or Codex). Workers are not AI agents themselves (they are deterministic templates or LLM wrappers); trainers are AI agents that evaluate worker output. The LLM is the experienced evaluator; the deterministic template or LLM generator is what gets trained over time.

**Biblical scholar requirement:** Every trainer agent is a biblical scholar. System prompts must reflect seminary-level theological competence — not generic evaluator behavior. Trainers evaluate with the rigor of a well-trained, Reformed evangelical scholar who knows the biblical languages, the secondary sources, and the pastoral tradition. This applies to ALL trainer agents: theological reviewer, grammar advisor, library trainer, outliner trainer, exposition trainer, be still trainer, action writer trainer, prayer trainer, and quote selector trainer.
> ⚠️ **Implementation gap:** Several trainer system prompts have not yet been updated to the biblical scholar profile. See per-worker notes below.

## Global Training Decision Policy

The following rules apply to all workers and override per-worker graduation logic when triggered:

### 50-Experiment Check (Required)
After every 50 experiments on a worker, the trainer agent must assess:
- Is there measurable improvement from the first 10 baseline experiments?
- If YES: continue training, document what is improving
- If NO improvement after 50 experiments: trainer must flag and escalate to operator with a diagnosis

### 100-Experiment Decision Point (Hard Gate)
At 100 experiments on a worker, a firm decision is required:
- **Graduate** — worker has met or exceeded its pass threshold consistently
- **Change approach** — worker has shown some improvement but not enough; trainer must propose a specific method change
- **Escalate** — worker has not improved; trainer writes a gap report and suspends training until operator reviews

This is the owner's decision, informed by the trainer's analysis. Training does not continue past 100 experiments without a deliberate choice.

### No-improvement cap (L15 analog)
If a worker produces identical failures on 3+ consecutive experiments after 50 runs, the trainer must stop and diagnose before continuing — per L15 retry policy.

---

## 1. Training Manager

**Implementation status:** Implemented
**LLM or deterministic:** Deterministic (orchestrator — no LLM calls; reads experiment ledger and coordinates training cycles)
**Implementation files:**
- `src/autoresearch/training_manager.py`
- `src/autoresearch/workers.py` — `WORKER_TRAINING_ORDER`, `WorkerSpec` definitions
**Current training state:** Always running

### Responsibilities
- Orchestrate the content generation training loop across all workers in `WORKER_TRAINING_ORDER`
- Select benchmark passages and scripture ranges
- Route training cycles to the appropriate training agents
- Track experiment outcomes in the ledger
- Escalate when a worker learning stalls
- Move training through 6-day/1-week through 30-day/5-week range templates
- Schedule training-mode passage runs when no live generation request is active
- Shift attention toward the worker currently limiting generation quality

### Trainer qualifications
No LLM needed — orchestrator role; reads experiment ledger and applies static scheduling logic.

### Trainer duties
- Load `WorkerSpec` for each worker in `WORKER_TRAINING_ORDER`
- Check current experiment ledger for each worker's recent pass/fail record
- Build `WorkerTrainingReview` assessments per worker
- Coordinate with expert trainers (theological reviewer, library trainer, grammar advisor) for supporting context
- Log training cycle results to experiment store
- Read harness checkpoint outputs for Exodus 19-20 and Proverbs 1-2 passage test runs

### Grading criteria
- Pass threshold: orchestrator does not grade directly; it reads results from individual training agents
- Benchmark passages: Luke 15 (6-day short cycle), Exodus 19-20 (12-day medium cycle), Psalms 23-25 (long multi-week cycle)
- Key metrics: `training_cycle_completion_rate`, `benchmark_coverage_rate`, `worker_improvement_rate`

### Known failure modes
- Getting stuck on a single passage range instead of cycling through 6-day through 30-day templates
- Missing which worker is the current quality bottleneck
- Running training cycles when a live generation request should take priority

### Keep / discard criteria
- Keep: cycle completed, experiment record written, worker assessment reasonable
- Discard: cycle crashed without experiment record (L2 violation)

### PRD requirements this worker trains toward
| FR/AC | Description | Training coverage |
|---|---|---|
| (All FRs indirectly) | Quality of all pipeline workers that satisfy PRD FRs | Trains toward indirectly via worker training orchestration |

### Training gap notes
- The training manager does not have a dedicated trainer evaluating it; it is a meta-orchestrator that self-monitors via the experiment ledger.

---

## 2. Output Training Manager

**Implementation status:** Implemented
**LLM or deterministic:** Deterministic (orchestrator — no LLM calls)
**Implementation files:**
- `src/autoresearch/output_training_manager.py`
**Current training state:** Always running

### Responsibilities
- Orchestrate training for output workers: PDF Art Director and PDF Layout Engineer
- Track proof/final state distinction
- Prioritize visible product weaknesses that reduce buyer confidence
- Manage graduation threshold logic (25 consecutive passes for art director graduation)
- Monitor layout engineer graduation status (graduated at 54 consecutive passes)

### Trainer qualifications
No LLM needed — orchestrator role.

### Trainer duties
- Read latest PDF training cycle artifacts from `docs/system/outputs/`
- Read experiment ledger for both PDF workers
- Track art director consecutive pass streak
- Check layout engineer graduation status
- Build `OutputWorkerReview` per worker
- Log output training cycle results

### Grading criteria
- Art Director graduation threshold: 25 consecutive passes
- Layout Engineer: **graduated** (54 consecutive passes as of 2026-03-16); reopen only on regression
- Key metrics: `output_cycle_completion_rate`, `pdf_worker_improvement_rate`, `proof_quality_progress`
- Benchmark passages: Habakkuk 1-3 (proof design), Exodus 19-20 (overflow/margin), Psalms 23-25 (premium rhythm)

### Known failure modes
- Art Director: abstract visual improvements without addressing specific buyer-confidence weaknesses
- Layout Engineer (when active): technical compliance without premium appearance

### Keep / discard criteria
- Keep: PDF artifacts produced; compliance results present; worker assessment written
- Discard: no output artifact produced (L2 violation); same visual error repeated > 3 times (L15 violation)

### PRD requirements this worker trains toward
| FR/AC | Description | Training coverage |
|---|---|---|
| FR-84–FR-94 | KDP PDF compliance: trim size, margins, fonts, front matter, TOC, page numbering, offer page | Trains toward via layout engineer |
| AC-38 | PDF passes KDP compliance checks | Trains toward |

### Training gap notes
- FR-86 (premium font embedding), FR-87–FR-94 (front matter quality): the Layout Engineer covers KDP compliance; the Art Director covers visual premium quality. The Art Director is the active bottleneck.

---

## 3. Policy Guardian

**Implementation status:** Implemented
**LLM or deterministic:** LLM (Claude or Codex via `DEVG_LLM_POLICY_GUARDIAN`)
**Implementation files:**
- `src/autoresearch/policy_guardian_agent.py`
**Current training state:** Always running

### Responsibilities
- Enforce L2 (Evidence Gate): every training session must produce a reviewable output artifact
- Enforce L15 (Retry/Stop Policy): identical failures capped at 3; must halt and escalate
- Enforce scope boundaries: agents must not act outside their defined `owned_surface`
- Read actual agent output artifacts — not just file existence — and apply the written law
- Record "no applicable law" when a situation is not covered by written law; escalate per Art. 1.2
- Write gap annotations to `rules-laws/proposed/` for repo practices lacking a ratified law
- Does NOT invent or extrapolate rules; authority is written law only
- Does NOT assess training quality or worker improvement (those belong to the trainers)

### Trainer qualifications
LLM capability required: must read and reason about actual agent artifacts vs. written law. A deterministic checker can only verify file counts, not apply the law to what agents are actually producing.

### Trainer duties
- Read constitution (Tier 0) and federal laws L1–L16 (Tier 1) as authority base
- Read any local laws in `.laws/` directory (Tier 3)
- Scan recent agent output artifacts for L2 compliance (artifact present per session)
- Scan experiment ledger for L15 violations (same failure repeated > 3 times)
- Check agent action logs for scope boundary violations
- Write `PolicyGuardianFinding` records: title, severity, law_citation, rationale, recommendation
- Log findings to experiment store

### Grading criteria
- Laws currently enforced: L2 (Evidence Gate), L15 (Retry/Stop Policy), Scope Boundary, LLM cross-provider separation (proposed)
- L2 pass: every tracked agent session has a reviewable output artifact
- L15 pass: no worker has hit identical failure > 3 consecutive times without halting
- Scope pass: no agent is acting outside its defined `owned_surface`
- Agents tracked for L2: outliner, exposition_writer, theological_reviewer, library_trainer, research_librarian, pdf_workers, proposal_reviewer, cross_evaluator, be_still_writer, action_writer

### Known failure modes
- Enforcing things not in written law (overreach — prohibited by the guardian's own mandate)
- Missing L15 violations because ledger scan logic is too narrow
- Not escalating "no applicable law" situations (required by Art. 1.2)

### Keep / discard criteria
- Keep: findings produced with law citation; no invented rules
- Discard: findings reference rules not in the written law; report produced without reading actual artifacts

### PRD requirements this worker trains toward
| FR/AC | Description | Training coverage |
|---|---|---|
| (Governance only) | The Policy Guardian enforces DevG system laws, not PRD content FRs | N/A |

### Training gap notes
- The policy guardian enforces system governance laws, not PRD product requirements. It is a process enforcer, not a content quality evaluator.
- L1, L3–L14, L16 are written and ratified but not yet wired into enforcement checks. Each requires an explicit enforcement check to become active.

---

## 4. Theological Reviewer

**Implementation status:** Implemented
**LLM or deterministic:** LLM (Claude or Codex via `DEVG_LLM_THEOLOGICAL_REVIEWER`)
**Implementation files:**
- `src/autoresearch/theological_reviewer_agent.py`
- `src/autoresearch/llm_theological_reviewer_core.py` — `build_llm_theological_review()`, `evaluate_theological_review_quality()`
**Current training state:** Always running

### Responsibilities
- Stage 1 — Resource Review: evaluate whether research librarian resources are theologically appropriate for the passage; flag resources that flatten, contradict, or misrepresent the passage's doctrinal position
- Stage 2 — Quote Review: after resources cleared, verify the selected quote is theologically accurate for the specific passage; quote must strengthen the passage's burden, not just sound devotional
- Stage 3 — Content Review: evaluate exposition, prayer, and application for boundary violations, doctrinal flattening, or sentimental drift
- Primary coaching relationship: exposition writer
- Secondary coaching relationship: outliner (on-demand, after 2+ failures)
- Work with grammar advisor as a coaching pair

### Trainer qualifications
Expert LLM theological reviewer. Must detect:
- Prosperity gospel drift, merit-based language, open theism, universalism, Pelagian anthropology (Section 10.2)
- Quote that fits the theme but softens the passage's theological weight
- Content that flattens, overreaches, or drifts from the passage's actual position

### Trainer duties
- Read source resources returned by the research librarian for the passage
- Evaluate resource appropriateness (Stage 1)
- Read selected quote and evaluate theological fit to the specific passage (Stage 2)
- Read exposition, prayer, and action steps for boundary violations (Stage 3)
- Each stage must clear before the next proceeds
- Run `build_llm_theological_review()` for LLM evaluation
- Run `evaluate_theological_review_quality()` for self-assessment
- Log findings to experiment store

### Grading criteria
- Pass threshold: LLM score >= 80
- Deterministic stage checks (resource strength, quote validation, book-level theological failures) are supporting context, not independent gates
- Benchmark passages: Exodus 19-20 (law/holiness), Luke 15 (mercy/parable), Colossians 3-4 (exhortation/epistle)
- Key metrics: `theological_boundary_review_pass_rate`, `quote_appropriateness_pass_rate`, `manual_review_flag_reduction`

### Known failure modes
- Granting benefit of the doubt to exposition drafts that have surface fluency but doctrinal drift
- Passing a quote that sounds devotional without verifying it strengthens the specific passage burden
- Proceeding to Stage 3 when Stage 1 or 2 resources have failed

### Keep / discard criteria
- Keep: all three stages evaluated; LLM score recorded; boundary violations documented with specific passage evidence
- Discard: review proceeds without reading actual artifacts; invented theological standards not in Section 10; same failure repeated > 3 times (L15)

### PRD requirements this worker trains toward
| FR/AC | Description | Training coverage |
|---|---|---|
| FR-73 | Theological validation pass after generation | Trains toward (autoresearch coaching; not the same as the pipeline validator) |
| FR-74 | Exposition validator criteria | Trains toward |
| FR-77 | Prayer validator criteria | Trains toward |
| FR-09 | No doctrinal claims not supported by passage | Trains toward |
| FR-10 | No reduction to behavioral lesson without theological grounding | Trains toward |
| FR-11 | No softening of genuine difficulty | Trains toward |
| FR-40 | Prayer petition traceable to specific verse | Trains toward |
| FR-45 | No prayer contradicting exposition theology | Trains toward |
| AC-01–AC-11 | Exposition acceptance criteria | Trains toward |
| AC-32 | No content contradicting doctrinal guardrails | Trains toward |

### Training gap notes
- The Theological Reviewer is an autoresearch coaching agent, not the pipeline's deterministic validator (which is `src/validation/`). Both must independently satisfy their roles.

---

## 5. Grammar Advisor

**Implementation status:** Implemented
**LLM or deterministic:** LLM (Claude or Codex via `DEVG_LLM_GRAMMAR_ADVISOR`)
**Implementation files:**
- `src/autoresearch/grammar_advisor_agent.py`
- `src/autoresearch/llm_grammar_advisor_core.py` — `build_llm_grammar_review()`
**Current training state:** Always running

### Responsibilities
- Work alongside theological reviewer as a coaching pair for the exposition writer
- Own prose clarity, sentence discipline, and paragraph rhythm
- Flag mechanical prose failures: overlong sentences, repetitive openings, stacked abstractions
- Distinguish between grammar problems, theology problems, and combined issues; flag which reviewer owns the fix
- Never recommend prose changes that would reduce theological precision

### Trainer qualifications
Expert prose evaluator. Must detect:
- Long sentences carrying no genuine theological weight (flag; defer to theological reviewer when weight justifies length)
- Repetitive sentence openings in consecutive sentences or paragraphs
- Paragraphs that stack disconnected abstractions instead of flowing prose
- Readability issues that do not softening the passage burden

### Trainer duties
- Read `ensure_approved_training_artifact()` to get an approved book.json for review
- Count long sentences (deterministic: sentences over a threshold word count)
- Count repeated paragraph/sentence openings (deterministic: regex)
- Call `build_llm_grammar_review()` for LLM prose quality evaluation
- Log `GrammarAdvisorFinding` records and metrics
- Log findings to experiment store

### Grading criteria
- Pass threshold: LLM score >= 80 (mirrors theological reviewer threshold)
- Deterministic checks (long sentence count, repeated opening count) are supplementary signals
- Benchmark passages: Colossians 3-4, Proverbs 1-2, Habakkuk 1-3
- Key metrics: `grammar_review_pass_rate`, `awkward_sentence_reduction`, `paragraph_clarity_rate`

### Known failure modes
- Flagging grammatically necessary complexity as a problem (passages with genuine theological weight may require long sentences)
- Missing repeated opening patterns across non-adjacent paragraphs

### Keep / discard criteria
- Keep: both deterministic and LLM checks run; findings documented; reviewer owns each finding clearly assigned
- Discard: review blocked (no approved training artifact available); same prose failure repeated > 3 times (L15)

### PRD requirements this worker trains toward
| FR/AC | Description | Training coverage |
|---|---|---|
| FR-02 | Exposition 500–700 words | Trains toward (prose discipline supports staying in range) |
| FR-03 | Communal voice throughout | Trains toward (prose consistency) |
| FR-07 | Context paragraph developed fully | Trains toward (prose development vs. truncation) |
| AC-09 | Communal voice throughout | Trains toward |
| AC-10 | 500–700 words | Trains toward |
| NFR-01 | Readability (implied) | Trains toward |

### Training gap notes
- Grammar Advisor has no FR that directly maps to it as a sole owner — it is a quality-of-prose coach for exposition, not a structural requirements owner.

---

## 6. Library Trainer

**Implementation status:** Implemented
**LLM or deterministic:** LLM (Claude or Codex via `DEVG_LLM_LIBRARY_TRAINER`)
**Implementation files:**
- `src/autoresearch/library_trainer_agent.py`
- `src/autoresearch/llm_library_trainer_core.py` — `evaluate_notes_batch()`
**Current training state:** Always running

### Responsibilities
- Train the research librarian to understand what shelf resources actually contain
- Evaluate whether the librarian uses current holdings before asking for acquisition
- Distinguish premature escalation (holdings sufficient, not used) from legitimate specificity requests (holdings genuinely too shallow)
- Evaluate reading note quality: specificity, passage awareness, accomplished vs. beginner behavior
- Approve or clear acquisition requests; forward legitimate requests to acquisition librarian

### Trainer qualifications
Expert library science evaluator with theological collection knowledge. Must distinguish:
- Premature escalation: current holdings adequate; worker didn't consult shelf
- Legitimate specificity request: shelf exists but lacks passage-specific depth needed
- Accomplished librarian behavior: shelf-first, escalate only when needed, writes notes that improve future requests

### Trainer duties
- Load reading note evaluation files from `data/library/reading-notes/drafts/*.evaluation.json`
- Load raw reading note files for LLM batch evaluation (up to 5 notes per cycle)
- Call `evaluate_notes_batch()` for LLM evaluation of note quality
- Check pending acquisition requests; apply library trainer resolution (clear vs. approve for acquisition)
- Deterministic checks: blank/metadata-only packets (no real note content), pending requests count
- Log `LibraryTrainerFinding` records and metrics

### Grading criteria
- Pass threshold: LLM score evaluating note quality and shelf discipline (threshold not explicitly hardcoded; qualitative pass/fail from LLM)
- Up to 5 notes evaluated per cycle
- Benchmark passages: Exodus 19-20 (law service), Luke 15 (parable service), Colossians 3-4 (epistle service)
- Key metrics: `shared_bundle_helpfulness_rate`, `followup_request_rate`, `thin_library_escalation_accuracy`
- Accomplished milestone: uses shelf first, escalates only when holdings genuinely too shallow, writes improving notes

### Known failure modes
- Research librarian escalates everything without checking current holdings (beginner failure mode)
- Librarian escalates after shelf is already sufficient (resolved training target for this cycle as of 2026-03-16)
- Reading notes that describe the card catalog metadata rather than what the resource actually contains

### Keep / discard criteria
- Keep: notes evaluated; acquisition requests resolved; LLM evaluation score recorded
- Discard: no notes found to evaluate and no acquisition requests pending (empty cycle, not a failure); evaluation run without reading actual note files

### PRD requirements this worker trains toward
| FR/AC | Description | Training coverage |
|---|---|---|
| FR-17 | Retrieve from ten approved theological sources | Trains toward — library trainer ensures the research librarian knows the collection and uses it effectively |
| FR-18 | Commentary → P2/P3; reference works → P2 | Trains toward |
| FR-19 | Grounding Map with non-empty entries per paragraph | Trains toward indirectly (rich bundles enable better grounding) |
| TC-03 | Agentic RAG: plan retrieval across approved sources | Trains toward |

### Training gap notes
- The library trainer evaluates reading notes quality; it does not evaluate the research librarian's actual bundle output directly. That is evaluated in the context of the exposition training cycle when the exposition writer receives the bundle.

---

## 7. Outliner Training Agent

**Implementation status:** Implemented
**LLM or deterministic:** LLM trainer (Claude or Codex, cross-provider via `get_cross_llm_client()`; evaluator is always a different AI from the generator); deterministic outliner worker being trained
**Implementation files:**
- `src/autoresearch/outliner_training_agent.py`
- `src/autoresearch/llm_outliner_core.py` — `build_llm_outliner_trainer_review()` (cross-provider evaluator)
**Current training state:** ⚠️ WALL — stuck on ruth-1 18d template (score ceiling 74/85, as of 2026-03-18 08:30 UTC)

### Responsibilities
- Run the outliner on benchmark passages at various range lengths (6-day through 30-day)
- Score the completed outline artifact for genre-detection accuracy, day boundary quality, burden differentiation, theological lane specificity
- Escalate to the theological reviewer on-demand when the outliner struggles with a passage (2+ failures)
- Rotate through `HARNESS_PASSAGES` at different `RANGE_TEMPLATES` (6/12/18/24/30 days)
- Track "second-eyes" critique via the cross-provider evaluator

### Trainer qualifications
Expert biblical theologian with structural judgment. Must detect:
- Weak day boundaries: adjacent days with identical or interchangeable burdens
- Genre mistakes: treating a narrative as propositional doctrine; allegorizing an epistle
- Week-turn failures: week boundaries that don't correspond to natural movement in the passage
- Scaffold/template fills in pastoral burden or theological lane ("The argument of X rests on Y")
- Keyword extraction instead of genuine theological insight

### Trainer duties
- Select benchmark passage from `HARNESS_PASSAGES` (priority-weighted rotation)
- Select range template (`RANGE_TEMPLATES`) for this cycle
- Retrieve scripture text via `ScriptureRetriever` for the passage
- Prepare passage resource bundle via `prepare_passage_resource_bundle()`
- Call `build_outline_artifact()` to run the outliner
- Call `build_llm_outliner_trainer_review()` for cross-provider LLM evaluation
- Score against BOOK_DAY_PROGRESS, BOOK_WEEK_TRANSITION, BOOK_THEOLOGICAL_BOUNDARY, harness_pass_rate
- Log `OutlineTrainingAssignment` and experiment record
- Record trainer recommendation via `record_trainer_recommendation()`

### Grading criteria
- Pass threshold: score >= 85
- **Current status (2026-03-18):** 570 total experiments; 14 passes (90–100) across john-10, mark-2, romans-5, philippians-2, ruth-1 at 6d and 12d templates. Currently stuck on ruth-1 18d: score ceiling 74 across 50+ consecutive attempts. 100-experiment gate has been breached for total worker count — graduation decision required for this template.
- Benchmark passages: Exodus 19-20 (law/covenant/week-turn pressure), Proverbs 1-2 (adjacent-day sameness), Acts 9 (narrative turn/burden differentiation), Habakkuk 1-3 (prophetic movement)
- Extended harness includes: Genesis 1-2, Job 1-3, Matthew 1-2, Psalms 1-3, Ezekiel 37, 38-39, Genesis 12-13
- Key metrics: BOOK_DAY_PROGRESS, BOOK_WEEK_TRANSITION, BOOK_THEOLOGICAL_BOUNDARY, harness_pass_rate

### Known failure modes
- Burden sentences that sound theological but could be transplanted to any passage unchanged
- Week boundaries at arbitrary verse counts, not at natural passage turns
- Failing to differentiate adjacent days in a single-chapter passage

### Keep / discard criteria
- Keep: LLM trainer score >= 85; burden sentences are passage-specific; day boundaries are argued, not arbitrary
- Discard: LLM score < 85 after 3 consecutive attempts at same passage (L15); scaffold fills in burden/lane fields

### PRD requirements this worker trains toward
| FR/AC | Description | Training coverage |
|---|---|---|
| FR-12 | Genre-aware passage handling | Trains for |
| FR-01 | Four-paragraph structure (editorial direction from outline) | Trains toward indirectly |
| FR-06 | Context paragraph argues, not just orients | Trains toward (strong outliner briefs enable stronger context paragraphs) |
| FR-08 | Theological paragraph internal sequence | Trains toward indirectly |

### Training gap notes
- The outliner's primary product is the `EditorialDayBrief` which directs downstream writers. Outliner training quality directly affects exposition, Be Still, Action Steps, and Prayer quality, though it doesn't own those FRs directly.
- **100-gate alert (2026-03-18):** 570 experiments exceeds the 100-experiment governance gate. Per-template graduation is progressing (6d/12d cleared on 5 passages), but the ruth-1 18d template is a current wall (best score 74, threshold 85). Operator decision required: defer ruth-1 18d, assign more resources, or accept 18d graduation later.
- **Ceiling analysis:** Ruth 1 has 22 verses. The 18d template requires subdividing 22 verses into 18 sections (~1.2 verses/day). The outliner may need stronger librarian support for this passage to differentiate 18 adjacent single-verse studies. See `_needs_research_escalation()` in `outliner_training_agent.py`.
- **Library additions (2026-03-18):** Two Ruth commentaries added and indexed (+1,772 rows): Keil and Delitzsch "Biblical Commentary: Joshua, Judges, Ruth" (verse-by-verse, Hebrew analysis) and Pulpit Commentary Vol. 8: Judges and Ruth (homiletical section outlines). Both live in RAG — 236 and 379 chunks retrievable for Ruth 1 queries respectively.
- **Trainer upgrade (2026-03-18):** Outliner trainer persona elevated to lifelong seminary professor with expertise in passage division for exposition. Trainer receives verse_count, verse_density (verses/day), and a 6th rubric criterion on density. Density < 1.5 verses/day is HIGH RISK; "too_thin" verdict caps score at 84 (below pass). `theological_reviewer_consultation_needed` flag added. `_estimate_verse_count()` in `llm_outliner_core.py`.

---

## 8. Exposition Training Agent

**Implementation status:** Implemented
**LLM or deterministic:** LLM trainer (cross-provider evaluator); LLM exposition writer (DEVG_LLM_EXPOSITION_WRITER) being trained
**Implementation files:**
- `src/autoresearch/exposition_training_agent.py`
- `src/autoresearch/llm_exposition_core.py` — `build_llm_exposition_trainer_review()`
- Works with: `src/autoresearch/theological_reviewer_agent.py`, `src/autoresearch/grammar_advisor_agent.py`
**Current training state:** ✅ TEMPLATE FIXED 2026-03-18 — deterministic scorer now 100/100 on all benchmarks (was stuck at 45–55 for 1,212 experiments)

### Responsibilities
- Generate fresh expositions for benchmark passages via the LLM exposition writer
- Score each exposition on: word count, scaffold avoidance, passage anchoring, paragraph structure
- Coordinate with theological reviewer (Stage 1–3 review) and grammar advisor as a coaching pair
- Rotate through benchmark passages covering diverse genres: narrative, epistle, Psalms, gospel
- Also evaluate expositions from approved training corpus (existing book.json artifacts)

### Trainer qualifications
Expert exposition evaluator. Must detect:
- Generic devotional language that could apply to any passage ("God is faithful and calls us to trust")
- Scaffold fills ("The argument of Romans 5:1 presses through therefore...")
- Passage anchoring failures: smooth-sounding paragraphs that were not informed by the assigned passage
- Word count boundary violations (< 500 or > 700 words)

### Trainer duties
- Call `ensure_approved_training_artifact()` to get latest approved book.json
- Select benchmark passage from `_FRESH_BENCHMARK_PASSAGES`
- Retrieve scripture text for the passage
- Prepare research bundle via `prepare_passage_resource_bundle()`
- Build editorial brief via `build_editorial_day_brief()`
- Call `_build_exposition()` (deterministic template for comparison) and/or LLM exposition writer
- Call `build_llm_exposition_trainer_review()` for trainer evaluation
- Coordinate with `build_theological_reviewer_report()` and `build_grammar_advisor_report()`
- Log experiment record

### Grading criteria
- Pass threshold: LLM benchmark score >= 80
- Fresh benchmark passages: Luke 15:1-2, John 10:11-13, Romans 5:1-5, Psalm 23:1-3, Philippians 2:5-8
- Key metrics: EXPOSITION_VOICE, EXPOSITION_WORD_COUNT, readability_grade_le_8, review_acceptance_rate
- A smooth-sounding paragraph that could apply to any passage is a **fail**, not a partial pass
- Both theological reviewer AND grammar advisor must independently clear

### Known failure modes
- Exposition that paraphrases the chapter theme rather than engaging the specific focal verse
- Communal voice failure (second-person "you" appearing in exposition)
- Paragraph 1 that is a general statement about God rather than a declaration tied to the specific passage
- Paragraph 4 that resolves the tension instead of handing it to God

### Keep / discard criteria
- Keep: score >= 80; passage-specific anchoring verified; both coaching pair reviewers clear
- Discard: generic language present regardless of score; scaffold fills in paragraph structure; API credits exhausted (current blocker)

### PRD requirements this worker trains toward
| FR/AC | Description | Training coverage |
|---|---|---|
| FR-01 | Four-paragraph structure | Trains for |
| FR-02 | 500–700 words | Trains for |
| FR-03 | Communal voice | Trains for |
| FR-04 | Inline secondary scripture references | Not yet training for (not in benchmark rubric) |
| FR-05–FR-16 | Detailed paragraph requirements | Trains for |
| FR-19 | Grounding Map completeness | Trains for indirectly (rich retrieval → better GroundingMap) |
| AC-01–AC-11 | Exposition acceptance criteria | Trains for |

### Training gap notes
- FR-04 (inline scripture references with book/chapter/verse) is not currently part of the exposition benchmark rubric.
- **Template fix (2026-03-18):** Root cause of 1,212-experiment stall identified and fixed: `_build_exposition()` in `src/generation/real_section_generator.py` was building paragraphs from abstract theological scaffolding without quoting actual verse language. The LLM trainer consistently returned `passage_grounded: false` and `generic_phrase_count: 3–5`. Fixed by: (1) embedding `brief.focus_clause` as a direct scripture quote in paragraphs 1 and 2; (2) replacing generic addenda sentences with passage-specific language referencing the focus_clause, key_terms, and scripture_reference; (3) fixing `_scripture_image()` to skip short heading/title clauses and reach actual verse content. Deterministic scorer: 100/100 across all benchmarks post-fix (was 40–55).
- **LLM trainer verification pending:** The LLM trainer in the training loop will confirm the improvement in the next exposition training cycle. Cross-provider LLM uses `.env.local` API key (OpenAI) not available in development shell.

---

## 9. Passage Researcher Training Agent

**Implementation status:** Implemented (deterministic scoring — no LLM in this agent)
**LLM or deterministic:** Deterministic (resource count scoring; no LLM calls)
**Implementation files:**
- `src/autoresearch/passage_researcher_training_agent.py`
**Current training state:** Active (proactive drills on benchmark passages)

### Responsibilities
- Proactively run the passage researcher on benchmark passages before the exposition writer needs them
- Surface thin-bundle passages and give the acquisition librarian concrete targets
- Score bundle coverage: `exposition_resources >= 4` = strong; `< 4` = thin
- Prevent the exposition writer from hitting thin resources during generation

### Trainer qualifications
Deterministic count-based scorer. No theological judgment required — purely structural: "does the bundle have enough resources for each passage?"

### Trainer duties
- Iterate over `_BENCHMARK_PASSAGES` (10 passages across diverse genres)
- Call `prepare_passage_resource_bundle()` for each passage
- Count `exposition_resource_count`, `shared_resource_count`, `outliner_resource_count`
- Score strength: strong (≥ 4 exposition resources) vs. thin (< 4)
- Log `PassageResearcherDrillResult` per passage
- Log overall experiment record with thin-passage identification

### Grading criteria
- Strong threshold: `exposition_resources >= 4`
- Thin: `< 4`; triggers acquisition librarian targeting
- Benchmark passages: Luke 15:11-24, Habakkuk 1:1-7, Colossians 3:1-17, Exodus 20:1-17, Psalm 23:1-6, Proverbs 1:1-9, Romans 5:1-11, John 10:11-18, Acts 9:1-20, Ezekiel 37:1-14
- Key metrics: same_book_support_rate, support_acceptance_rate, wrong_book_helper_rate

### Known failure modes
- All passages scoring thin because the library has not yet been fully indexed (early-stage failure — not a training failure but a collection gap)
- Escalating acquisition for passages where the shelf already has enough but it isn't indexed

### Keep / discard criteria
- Keep: all benchmark passages drilled; thin/strong status recorded; acquisition targets identified
- Discard: exception during bundle preparation and no result logged; same passages repeatedly thin without acquisition action

### PRD requirements this worker trains toward
| FR/AC | Description | Training coverage |
|---|---|---|
| FR-17 | Retrieve from ten approved theological sources | Trains for (surface coverage gaps) |
| FR-18 | Commentary → P2/P3; reference works → P2 | Trains toward (source type coverage) |
| FR-19 | Non-empty Grounding Map entries per paragraph | Trains toward (bundle richness enables grounding) |
| TC-03 | Agentic RAG: plan retrieval across approved sources | Trains toward |

### Training gap notes
- This agent scores resource count only; it does not evaluate resource quality or passage-specificity. Resource quality is evaluated by the Library Trainer and Research Librarian.

---

## 10. PDF Training Agent

**Implementation status:** Implemented
**LLM or deterministic:** LLM (trainer evaluator — Claude or Codex via art director and layout trainer profiles); deterministic compliance checks
**Implementation files:**
- `src/autoresearch/pdf_training_agent.py`
- Training corpus: `src/autoresearch/training_corpus.py` — `collect_pdf_training_corpus()`, `ensure_approved_training_artifact()`
**Current training state:** Active — Art Director 54 consecutive fails (active bottleneck); Layout Engineer graduated

### Responsibilities
- Art Director training: visual hierarchy, title page quality, day boundaries, introduction presentation, premium atmosphere
- Layout Engineer training: pagination stability, overflow prevention, KDP-safe margins, proof watermarking
- Track graduation streaks for both workers
- Layout Engineer graduated: reopen training only on regression

### Trainer qualifications
Expert PDF visual quality evaluator (art director) + layout safety evaluator (layout engineer).

### Trainer duties
- Call `ensure_approved_training_artifact()` to get approved book.json as training input
- Call TypeScript PDF engine subprocess to generate a reviewed-proof PDF from the training corpus
- Evaluate PDF against art director rubric (LLM): does it look elevated enough for above-normal pricing?
- Evaluate PDF against layout engineer rubric (deterministic + LLM): KDP margin compliance, overflow-free pages, watermark correctness
- Track `_layout_engineer_pass_streak()` — layout engineer graduated at 54 consecutive passes
- Track `_pdf_art_director_pass_streak()` — graduation threshold is 25 consecutive passes
- Log `PDFTrainingAssignment` and experiment record

### Grading criteria
- Art Director pass: "looks intentionally elevated enough to justify above-normal pricing" — LLM evaluator judgment
- Art Director graduation threshold: 25 consecutive passes
- Layout Engineer pass: overflow-free pages, KDP margin compliance, watermark correctness
- Layout Engineer: **graduated** (54 consecutive passes)
- Art Director current status: 54 consecutive fails — active bottleneck

### Known failure modes
- Art Director: producing technically compliant PDFs that look like auto-generated drafts
- Art Director: attempting whole-book redesign instead of one small visual target at a time
- Layout Engineer (when active): clipping content, incorrect margin bracket selection

### Keep / discard criteria
- Keep: PDF artifact produced; compliance result present; visual evaluation recorded
- Discard: TypeScript engine subprocess fails with no output; same visual error repeated > 3 times without change (L15)

### PRD requirements this worker trains toward
| FR/AC | Description | Training coverage |
|---|---|---|
| FR-84 | 6x9 trim size | Trains for |
| FR-85 | Margins per page count bracket | Trains for |
| FR-86 | Embedded open-source fonts | Trains for |
| FR-87–FR-94 | Front matter, TOC, page numbering, offer page | Trains for |
| AC-38 | PDF passes KDP compliance | Trains for |

### Training gap notes
- Art Director is the active quality bottleneck. 54 consecutive fails is a major blocker for publish-ready output quality.
- FR-91 (each day on new page), FR-92 (page numbering) are layout engineer responsibilities — graduated.

---

## 11. Be Still Training Agent

**Implementation status:** Implemented
**LLM or deterministic:** LLM trainer evaluator (Claude or Codex via `llm_be_still_core.build_llm_be_still_trainer_review()`); deterministic Be Still writer being trained
**Implementation files:**
- `src/autoresearch/be_still_training_agent.py`
- `src/autoresearch/llm_be_still_core.py` — LLM trainer evaluator
**Current training state:** Waiting (route registered; training agent exists but listed as "waiting" in autoresearch plan)

### Responsibilities
- Evaluate Be Still sections from approved book.json training corpus
- Run fresh benchmark: regenerate Be Still from current templates and score immediately
- Detect generic stillness filler (prompts that could appear in any devotional)
- Verify prompt sequence moves from inward to outward
- Verify final prompt creates a felt need that flows into Action Steps without resolving it

### Trainer qualifications
Expert devotional evaluation with passage anchoring focus. Must detect:
- First prompt that rushes to reflection instead of inviting stillness
- Prompts that stay at the same level throughout (no inward-to-outward movement)
- Generic prompts copy/pasteable to any passage
- Closing prompt that answers itself instead of creating a felt need

### Trainer duties
- Call `ensure_approved_training_artifact()` to get approved book.json
- Iterate over benchmark passages from `_FRESH_BENCHMARK_PASSAGES`
- Retrieve scripture text; build editorial brief
- Call `_build_be_still()` with the brief to get a fresh benchmark Be Still section
- Call `build_llm_be_still_trainer_review()` for LLM evaluation
- Log experiment record

### Grading criteria
- Pass threshold: LLM evaluator judgment (score threshold not explicitly set in code; qualitative pass/fail)
- Benchmark passages: Habakkuk 1:1-4, Psalm 23:1-3, Exodus 20:1-3, Colossians 3:1-4, Luke 15:11-14
- Key metrics: `section_day_unification`, `passage_anchor_rate`, `review_acceptance_rate`
- A prompt that appears verbatim in every output regardless of passage is a structural failure

### Known failure modes
- All three default prompts appearing identically across different passages (current deterministic template state)
- Final prompt that resolves the tension instead of holding it

### Keep / discard criteria
- Keep: passage-specific prompts verified; inward-to-outward movement verified
- Discard: same generic prompt set regardless of passage; same failure repeated > 3 times (L15)

### PRD requirements this worker trains toward
| FR/AC | Description | Training coverage |
|---|---|---|
| FR-22 | Prompts arise from exposition without new concepts | Trains for |
| FR-23 | First prompt: stillness and receptivity | Trains for |
| FR-24 | Inward to outward sequence; final prompt creates felt need | Trains for |
| FR-25 | Second-person | Trains for |
| FR-26 | Questions/directives, not answered | Trains for |
| AC-12–AC-17 | Be Still acceptance criteria | Trains for |

### Training gap notes
- Be Still writer is currently a deterministic template with known generic output. Training agent exists but is in "waiting" state — needs to be activated as priority worker. FR-22 (prompts arise from exposition) is the critical gap.

---

## 12. Action Steps Training Agent

**Implementation status:** Implemented
**LLM or deterministic:** LLM trainer evaluator (Claude or Codex via `llm_action_steps_core.build_llm_action_steps_trainer_review()`); deterministic Action Steps writer being trained
**Implementation files:**
- `src/autoresearch/action_writer_training_agent.py`
- `src/autoresearch/llm_action_steps_core.py` — LLM trainer evaluator
**Current training state:** Waiting (route registered; training agent exists but listed as "waiting" in autoresearch plan)

### Responsibilities
- Evaluate Action Steps sections from approved training corpus
- Run fresh benchmark: regenerate Action Steps from current templates and score immediately
- Detect generic spiritual-productivity steps (failures, not partial passes)
- Verify connector phrase explicitly references what the reader encountered in stillness
- Verify steps are specific enough to be attempted today

### Trainer qualifications
Expert action-step evaluator with pastoral theology judgment. Must detect:
- Connector phrase referencing the exposition rather than the Be Still section (structural failure)
- Steps that could appear in any devotional without modification
- Steps framed as self-improvement effort rather than response to revelation
- Steps that resolve the Be Still tension instead of directing toward faithful response

### Trainer duties
- Call `ensure_approved_training_artifact()` to get approved book.json
- Iterate over benchmark passages from `_FRESH_BENCHMARK_PASSAGES`
- Retrieve scripture text; build editorial brief
- Call `_build_be_still()` and `_build_action_steps()` with the brief for fresh benchmark
- Call `build_llm_action_steps_trainer_review()` for LLM evaluation
- Log experiment record

### Grading criteria
- Pass threshold: LLM evaluator judgment (qualitative; threshold not hardcoded in code reviewed)
- Benchmark passages: Luke 5:27-28, Proverbs 1:7-9, Colossians 3:12-14, Habakkuk 2:1-4, Psalm 23:4-6
- Key metrics: `section_day_unification`, `application_specificity_rate`, `review_acceptance_rate`
- Generic steps that could appear in any devotional: automatic fail

### Known failure modes
- Connector phrase referencing exposition concept instead of Be Still encounter
- Steps that are ongoing dispositions rather than same-day actions ("Seek to trust God more")
- Tonal acknowledgment of unfamiliarity (FR-34) absent from current deterministic template

### Keep / discard criteria
- Keep: connector explicitly references Be Still; at least one step is today-specific and passage-specific
- Discard: all steps are generic; connector phrase points to exposition rather than Be Still

### PRD requirements this worker trains toward
| FR/AC | Description | Training coverage |
|---|---|---|
| FR-29 | Connector phrase referencing Be Still | Trains for |
| FR-30 | 1–3 specific same-day applicable items | Trains for |
| FR-31 | Obedience as response | Trains for |
| FR-33 | Active expectation | Trains for |
| FR-34 | One step acknowledges unfamiliarity | Trains for |
| AC-18–AC-20b | Action Steps acceptance criteria | Trains for |

### Training gap notes
- FR-34 / AC-20b (tonal acknowledgment of unfamiliarity grounded in God's faithfulness) is not yet in the deterministic template and must be a training target.

---

## 13. Prayer Training Agent

**Implementation status:** NOT IMPLEMENTED
**LLM or deterministic:** N/A
**Implementation files:** None — no `prayer_training_agent.py` exists
**Current training state:** [NO TRAINER AGENT — pending]

### Responsibilities (planned per autoresearch plan)
- Train the prayer writer on: closing prayer tone, theological boundary in prayer, passage-faithful devotional response
- Evaluate prayer word count (120–200), Trinity address, PrayerTraceMap completeness
- Benchmark against: Habakkuk 1-3, Ezekiel 38-39, Psalms 23-25

### PRD requirements this worker should train toward
| FR/AC | Description | Training coverage |
|---|---|---|
| FR-35–FR-48 | All prayer requirements | Not yet training |
| AC-21–AC-32 | Prayer acceptance criteria | Not yet training |
| FR-42 | PrayerTraceMap completeness | Not yet training |

### Training gap notes
- The prayer writer is listed in autoresearch plan as "route registered, waiting." Neither a training agent nor an LLM prayer writer core is listed as an active worker. `llm_prayer_generator.py` exists in `src/generation/` as a pipeline generator, but it has no dedicated training cycle in the autoresearch loop.
- This is a significant gap: the prayer section has 14 FRs (FR-35 through FR-48) and 12 ACs (AC-21 through AC-32) — the most of any single section — with no active training evaluation.

---

## 14. Quote Selector Training Agent

**Implementation status:** NOT IMPLEMENTED
**LLM or deterministic:** N/A
**Implementation files:** None — no `quote_selector_training_agent.py` exists
**Current training state:** [NO TRAINER AGENT — pending]

### Responsibilities (planned per autoresearch plan)
- Train the quote selector on: quote suitability, citation completeness, source search order, duplicate avoidance
- Benchmark: Psalms 23-25, Exodus 19-20, Colossians 3-4
- Key metrics: complete Turabian rate, duplicate quote failure rate, validator quote pass rate

### PRD requirements this worker should train toward
| FR/AC | Description | Training coverage |
|---|---|---|
| FR-49 | Quotes from verified catalog only | Not yet training |
| FR-50 | Approved whitelist and source domains | Not yet training |
| FR-52 | Shortage protocol and live fallback | Not yet training |
| FR-53–FR-55 | Turabian attribution, footnote rendering, human approval | Not yet training |
| FR-68 | Author diversity report | Not yet training |
| AC-34 | Turabian attribution, block quote, footnote | Not yet training |
| AC-39 | Quote de-duplication | Not yet training |
| TC-02 | Cached RAG; live fallback | Not yet training |

### Training gap notes
- The quote selector is listed as "route registered, waiting" in the autoresearch plan. No LLM quote selector agent has been implemented.
- FR-52 (live retrieval fallback) is also unimplemented in the pipeline, making this a compound gap: neither the production feature nor its training path exists.

---

## Training Coverage Matrix

| FR | Description | Worker trained | Trainer agent | Training state |
|---|---|---|---|---|
| FR-01 | Four-paragraph exposition structure | Exposition Writer | Exposition Training Agent | Active (blocked by API credits) |
| FR-02 | 500–700 words | Exposition Writer | Exposition Training Agent | Active |
| FR-03 | Communal voice | Exposition Writer | Grammar Advisor / Exposition TA | Active |
| FR-04 | Inline scripture references | Exposition Writer | Not yet in rubric | Gap |
| FR-05–FR-16 | Paragraph-level exposition requirements | Exposition Writer | Exposition Training Agent + Theological Reviewer | Active |
| FR-17 | Retrieve from ten approved sources | Research Librarian | Library Trainer + Passage Researcher TA | Active |
| FR-18 | Commentary P2/P3; reference P2 | Research Librarian | Library Trainer | Active |
| FR-19 | Grounding Map completeness | Exposition Writer | Exposition Training Agent | Active |
| FR-20–FR-28 | Be Still requirements | Be Still Writer | Be Still Training Agent | Waiting |
| FR-29–FR-34 | Action Steps requirements | Action Steps Writer | Action Steps Training Agent | Waiting |
| FR-35–FR-48 | Prayer requirements | Prayer Writer | No trainer agent | Gap — no trainer |
| FR-49–FR-55 | Quote sourcing and attribution | Quote Selector | No trainer agent | Gap — no trainer |
| FR-56 | Archaic language modernization | Modernizer (deterministic) | No trainer needed | N/A (deterministic) |
| FR-57–FR-60 | Scripture retrieval | Scripture Retrieval (deterministic) | No trainer needed | N/A (deterministic) |
| FR-61–FR-63 | PDF quote/scripture block quote, footnotes | PDF Layout Engineer | PDF Training Agent | Graduated |
| FR-64–FR-72 | Series registry, de-duplication, diversity | Pipeline (deterministic) | No trainer needed | N/A |
| FR-73–FR-78 | Theological validation pass | All content workers | Theological Reviewer + section TAs | Active |
| FR-79–FR-83 | Human review UI | UI layer | No trainer | N/A (UI, not AI worker) |
| FR-84–FR-94 | PDF layout and KDP compliance | PDF Layout Engineer | PDF Training Agent | Graduated / Art Director active |
| FR-95–FR-97 | Day 6 sending prompt, Day 7, introduction | Pipeline worker | No trainer | Gap |
| AC-01–AC-11 | Exposition ACs | Exposition Writer | Exposition TA + Theological Reviewer | Active |
| AC-12–AC-17 | Be Still ACs | Be Still Writer | Be Still Training Agent | Waiting |
| AC-18–AC-20b | Action Steps ACs | Action Steps Writer | Action Steps Training Agent | Waiting |
| AC-21–AC-32 | Prayer ACs | Prayer Writer | No trainer agent | Gap — no trainer |
| AC-33 | Validator pass | All workers | All training agents | Active |
| AC-34 | Quote attribution, block quote, footnote | Quote Selector + PDF | No quote trainer | Gap |
| AC-35–AC-36 | Scripture block quote, retrieval | Scripture Retrieval + PDF | N/A | N/A |
| AC-37 | All sections approved | Export Gate (deterministic) | N/A | N/A |
| AC-38 | KDP compliance | PDF Layout Engineer | PDF Training Agent | Graduated |
| AC-39 | Quote de-duplication | Pipeline (deterministic) + Quote Selector | No quote trainer | Partial gap |
| AC-40 | Author diversity report reviewed | Operator + pipeline (report not implemented) | N/A | Gap |
| AC-41–AC-43 | Day 6/7 requirements | Pipeline worker | No trainer | Gap |

---

## PRD Requirements with No Training Coverage

The following FRs and ACs have no training agent covering them as of 2026-03-18:

### Prayer Section — NO TRAINER AGENT
- FR-35 through FR-48 (all prayer requirements)
- AC-21 through AC-32 (all prayer acceptance criteria)

### Quote Selector — NO TRAINER AGENT
- FR-49 (quotes from verified catalog only)
- FR-50 (approved whitelist and source domains)
- FR-51 (cached RAG architecture)
- FR-52 (live fallback; shortage protocol; manual substitution path)
- FR-53 (full Turabian attribution)
- FR-54 (Turabian as footnote, not inline)
- FR-55 (human_approved + public_domain before publish-ready)
- AC-34 (Turabian attribution, public_domain=true, block quote + footnote)
- AC-39 (quote de-duplication)
- TC-02 (cached RAG + live fallback)

### Day 6 / Day 7 / Sending Prompt — NO TRAINER AGENT
- FR-95 (Day 6 sending prompt: 40–80 words, open question, week theme)
- FR-96 (Day 7 page structure: Before/After the Service, Track A/B)
- FR-97 (Introduction Sunday Worship Integration section)
- AC-41 (Day 6 sending prompt requirements)
- AC-42 (Day 7 page requirements)
- AC-43 (Introduction Sunday Worship Integration)

### Series Architecture — NO TRAINER AGENT (deterministic/operator judgment)
- FR-68 (author diversity report — report generation not implemented)
- FR-70 (parent-child volume relationship)
- FR-71 (child volume weighting toward underrepresented authors)
- FR-72 (shared de-duplication registry across parent and child)

### Human Review UI — OUTSIDE TRAINING SCOPE
- FR-79, FR-79a, FR-80, FR-81, FR-82, FR-83 (human review and approval gate)

### AC Scoring Harness — UNVERIFIED IMPLEMENTATION STATUS
- TC-06 (deterministic validator isolation; hash-verified spec; version-recorded scoring)
- Section 18.5 (AC Scoring Harness — immutable shared test specification)

### Exposition Detail — GAP IN RUBRIC (trainer exists but requirement not in rubric)
- FR-04 (inline secondary scripture references with book/chapter/verse — not in exposition benchmark rubric)
