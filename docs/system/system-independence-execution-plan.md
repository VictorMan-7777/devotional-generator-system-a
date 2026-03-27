# DevG System-Independence Execution Plan

## Purpose

This plan defines the work required to make DevG operate correctly without hand-held operator intervention or hidden downstream compensation. The system should improve by assigning responsibility to the right layer, persisting work safely, and proving quality through repeatable runs.

## Governing principles

1. The outliner owns structure.
- It must identify passage movement, natural day boundaries, week turns, genre, and primary burden.
- The writer should not be compensating for weak segmentation.

2. The writer owns prose and exposition research, not interpretation rescue.
- It writes from the outline and passage-analysis contract.
- It should gather and judge passage-relevant exposition support instead of accepting random helper blocks.
- It should not invent a theological lane because the outline was weak.

3. The quote selector owns quote suitability and complete citation readiness.
- The validator does not complete citations.
- The selector must search approved sources until a complete citation is found or the quote is abandoned.

4. The validator owns verification, not content creation.
- It should expose mismatches and insufficiencies.
- It should not quietly normalize weak inputs into passing outputs.

5. Review and export must use durable state.
- Original generated content, edited content, and approved content must persist as first-class records.
- Proof and final export must read approved state, not stale files.

6. Write early, write often.
- Planning, retrieval, section generation, day checks, week checks, and book checks should leave durable checkpoints.
- Work already completed should not be lost because later stages fail.

7. Keep persistence behind the socket boundary.
- The system should not grow direct database dependencies in feature code.
- Backend swaps should affect adapters, not application behavior.
- The socket should serialize writes, retry transient failures, and preserve idempotent semantics so concurrent worker activity does not leak DB instability upward.

8. Teach the worker that owns the job.
- Better upstream workers reduce the need for downstream rescue.
- Workers should improve through shared resources, scoring, debate, and approved outcomes instead of hard-coded crutches.

9. The Agentic RAG is the shared library.
- The resource store is the library.
- The general librarian maintains and catalogs the library.
- The research librarian answers passage-specific research requests for workers.
- Workers should request help from the research librarian instead of relying on private cue maps.
- The live catalog lives at `data/library/resource-catalog.json`.
- Example cards live at `data/library/resource-catalog.examples.json`.

## Current diagnosis

### What is materially better already
- Review state now persists through the persistence socket.
- Early generation checkpoints are written during runs.
- Quote citations are treated more honestly; incomplete Turabian data is a blocker.
- Wrong-book exposition helper filtering exists.
- The first explicit outliner resource layer exists, but it is debt to retire as the librarian flow takes over.

### What is still structurally weak
- Passage interpretation still relies too heavily on ad hoc phrase maps in the writer/editorial path.
- The outliner is not yet owning enough of the real interpretive and structural work.
- The exposition writer is not yet clearly acting as the primary researcher for its own support needs.
- Quote validation can still fail because the validator candidate search is too shallow or the selector/catalog path is not yet fully autonomous.
- Review remains too file-oriented at the artifact layer even though DB-backed truth is now present.
- PDF generation still needs stronger proof/final separation and layout correctness.
- The system records outcomes in several places, but does not yet have a unified worker-training experiment ledger.
- The general-librarian vs research-librarian split was implicit instead of explicit.

## End state

DevG is independent when the following are true:
- A fresh passage can be outlined, sourced, generated, reviewed, and proofed without manual system intervention.
- The outliner produces distinct, coherent day and week movement from passage-aware resources.
- The exposition writer performs passage-true research, writes from it, and improves from approved edits.
- The quote selector either returns a fully citable quote or refuses the slot after exhausting approved sources.
- Exposition support blocks are passage-true and auditable.
- Review edits flow into the reviewed-proof PDF from persisted approved state.
- The system stops at review by default and only advances when explicitly told to do so.
- Worker improvements are evaluated against stable benchmarks and logged through the persistence boundary.
- Production workers are evaluated against a seminary-level production standard rather than a prototype-quality standard.

## DevG autoresearch model

Autoresearch in DevG is not unrestricted self-modification. It is controlled worker training.

### Worker-training rules
- Each worker has one owned surface.
- Each worker is measured against stable passage benchmarks and validator/review metrics.
- Each experiment is either kept or discarded.
- The system records what changed, what passage was used, what metric moved, and what was learned.
- Debate agents are challengers, not silent co-owners. They stress-test the owning worker's output before a benchmark run proceeds.
- Workers should pull from the shared library through the research librarian when they score weak.

### Initial workers to train
1. Training manager
- Owns training-mode orchestration across workers when no live generation request is active.
- Schedules scripture ranges from 6-day / 1-week to 30-day / 5-week.
- Redirects training effort toward the current bottleneck worker instead of training everything evenly.

2. Output training manager
- Owns output-worker orchestration for PDF/product quality when no higher-priority output review is active.
- Keeps proof/final output concerns distinct.
- Redirects training effort toward the current output bottleneck instead of treating product quality as an afterthought.
- Evaluates output workers against premium publishing/design standards, not seminary-style theological standards.

3. Outliner
- Owns structure, segmentation, week turns, and burden assignment.
- Debate agent challenges weak boundaries and repeated burdens.

4. Exposition writer
- Owns exposition research, paragraph movement, readability, and prose quality.
- Learns from approved reviewer edits and approved final expositions.

5. Quote selector
- Owns quote suitability, citation completeness, and source-search order.
- Learns which domains and URLs actually produce complete Turabian data.

6. Exposition retriever
- Owns passage-relevant commentary/support retrieval.
- Learns from what the exposition writer actually uses or rejects.

7. Be Still writer
- Owns meditative stillness prompts that stay anchored to the day's burden.
- Learns from approved review edits and accepted stillness patterns.

8. Action writer
- Owns concrete action steps that obey the text without collapsing into generic advice.
- Learns from approved action-step edits and rejected generic moves.

9. Prayer writer
- Owns closing prayers that remain inside the passage horizon and theological burden.
- Learns from approved prayer edits and theological-boundary corrections.

### Core autoresearch loop
1. Establish a worker baseline on a fixed benchmark passage.
2. Propose one worker-scoped change.
3. Run the benchmark passage or harness case.
4. Measure objective metrics.
5. Keep or discard the change.
6. Log the experiment and learning note through the socket-backed ledger.
7. Escalate to second-eyes or human review only when worker-local remedies are exhausted.

## Execution order

### Phase 1: Strengthen the outliner and passage-analysis layer
Goal: make the top of the system stronger so weak structure does not propagate.

Work:
1. Prepare shared passage resources as soon as Scripture is known.
2. Let an expert outliner-training agent review current outline evidence and assign outline-only drills before downstream generation.
3. Let the outliner request research-librarian help when its initial outline scores weak.
4. Teach the outliner to use shared library resources for:
- genre
- movement detection
- burden assignment
- natural day boundaries
- week transition candidates
5. Add debate-agent challenge for outlines that remain weak after the first pass.
6. Remove hard-coded passage cue dependence instead of extending it.
7. Replace cue dependence with resource-backed outline reasoning from commentary structure, genre signals, reviewer-approved outcomes, and experiment history.
8. Reduce writer-side rescue heuristics that are compensating for weak outline decisions.
9. Add focused tests for difficult books and genres.

Pass criteria:
- Luke/Acts/Exodus/Proverbs/Habakkuk no longer collapse into generic burden lanes for obvious scenes.
- Adjacent-day sameness drops because segmentation improves upstream.
- The outliner can be trained through outline-only drills from 6-day/1-week through 30-day/5-week without requiring full devotional runs.

### Phase 2: Make the exposition writer a first-class researcher
Goal: the exposition writer should gather and judge its own support using shared retrieval infrastructure.

Work:
1. Preposition passage resources for the writer from the shared library before drafting begins.
2. Record which supports the writer used, rejected, or requested again.
3. Learn from approved review deltas between original and approved expositions.
4. Use readability and paragraph-quality metrics as writer benchmarks.

Pass criteria:
- Exposition support blocks shown in review are clearly tied to the passage.
- Writer quality improves from approved edits instead of only from prompt patching.

### Phase 3: Make quote selection fully accountable
Goal: the quote selector must own finding a usable quote with a complete citation.

Work:
1. Probe approved quote sources for citation capability at the URL/domain level.
2. Rank sources by real citation yield, not static guesswork.
3. Require the selector to exhaust viable sources before abandoning a quote.
4. Exclude selector-touched sources from the validator lane for that quote.
5. Only allow generated quotes as a last resort when selector exhaustion is explicit and auditable.

Pass criteria:
- Fresh non-Genesis runs can produce fully citable quotes without hand backfill.
- Validator quote failures are genuine, not shallow-candidate misses.

### Phase 4: Tighten exposition-support trust
Goal: the exposition helpers must prove that the exposition was grounded in real, passage-relevant support.

Work:
1. Keep retrieved candidates, but surface only selected supports.
2. Prefer book-specific commentary resources before whole-Bible fallbacks.
3. Store outline resources used by the outliner in research memory.
4. Add stronger checks for wrong-book or wrong-scene support.

Pass criteria:
- Support blocks shown in review are visibly related to the passage.
- Review confidence no longer depends on assuming the exposition was not hallucinated.

### Phase 5: Review, proof, and export lifecycle
Goal: make the post-generation path deterministic and safe.

Work:
1. Default hard stop at review.
2. Reviewed-proof PDF generated only from approved persisted review state.
3. Final PDF generated only from explicitly approved proof/final command.
4. Watermark reviewed-proof PDFs.
5. Continue improving layout, pagination, title page, introduction, and day separation.

Pass criteria:
- Review edits are provably present in the reviewed-proof PDF.
- No pre-review PDF is created unless explicitly requested.

### Parallel PDF track
Goal: improve the PDF product in parallel with content-worker training so layout quality does not lag behind internal devotional quality.

Work:
1. Train a PDF art director on title page, introduction, typography, and day-boundary presentation.
2. Train a PDF layout engineer on overflow prevention, KDP-safe margins, watermarking, and stable proof/final pagination.
3. Use reviewed-proof PDFs and operator PDF findings as learning inputs.
4. Keep PDF training parallel to outliner work instead of waiting for content training to finish.

Pass criteria:
- PDFs no longer look like draft printer output.
- Day starts are visibly structured.
- Content no longer runs off the page.
- Reviewed-proof and final PDF states are visually and technically distinct.

### Phase 5.5: Socket reliability and write discipline
Goal: keep concurrent worker writes safe without pushing DB concerns up into generator or review code.

Work:
1. Serialize write operations at the socket boundary.
2. Retry transient write failures with bounded backoff.
3. Tune SQLite connection behavior for busy timeout and WAL where appropriate.
4. Keep write paths idempotent so retries do not duplicate state.

Pass criteria:
- Transient concurrent write pressure no longer causes routine review/worker logging failures.
- Reliability behavior remains contained in the persistence layer.

### Phase 6: Section-level durability and unification
Goal: every meaningful stage leaves durable state and receives the right scope of validation.

Work:
1. Persist section-level draft checkpoints, not just day/week/book checkpoints.
2. Add day-level unification checks after all sections for a day are written.
3. Keep week-level and book-level unification checks.
4. Persist remedy attempts and outcomes as first-class records.

Pass criteria:
- Recovery from interruption loses minimal work.
- The system can learn which remedies help by failure class.

### Phase 7: Controlled self-learning
Goal: let the system improve from outcomes without uncontrolled self-rewriting.

Work:
1. Track worker experiments, attempted remedies, outcome quality, and downstream effects.
2. Track source usefulness by task type.
3. Track outline strategy success by book/genre/failure pattern.
4. Escalate automatically to second-eyes, then human review when remedies are exhausted.

Pass criteria:
- The system gets better at picking the next remedy without modifying core logic silently.
- Worker improvements are durable and auditable in the experiment ledger.

## Immediate tranche

This tranche starts now.

1. Add a socket-backed autoresearch experiment ledger.
2. Define the initial DevG worker surfaces and benchmarks.
3. Expand the outliner resource layer beyond Luke and Colossians using Harness A/B passages.
4. Teach the exposition writer to learn from approved edits and writer-selected supports.
5. Keep cycling individual harness passages so each book/genre exposes a different weakness.

## Evidence required before calling the system independent

1. One non-Genesis devotional reaches review with:
- coherent outline
- passage-true exposition support
- complete Turabian quotes
- DB-backed review state

2. Review edits are saved and then shown in a reviewed-proof PDF.

3. One competition-format CSV run completes the same path without special intervention.

4. At least one worker improvement is recorded in the autoresearch ledger with a kept result and a clear learning note.
