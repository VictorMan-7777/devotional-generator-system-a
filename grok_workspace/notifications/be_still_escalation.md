# Action Required: Be Still — luke-15-11-14 failure loop

Policy guardian has flagged a failure loop on luke-15-11-14 and is requiring a halt. Do not retry that passage again. Step down to an easier passage and change the teaching method before returning to it.

Separately: the trainer is finding that prompt 3 partially answers itself (pre-selecting the emotional register). That is a structural template problem — the template is closing off tension rather than leaving the reader with a felt need. Look at how prompt 3 is built in the generator and address it.

---

**Update — 14:35 cycle (fresh benchmark regression):**

Be Still fresh benchmark dropped from 82/100 (pass) to **61/100 (revise)** on a new passage (Exodus-family, commandment context). This means the 82 on Psalm 23 was passage-specific, not a structural improvement.

The trainer's priority fix:

> "Insert a genuine inward prompt between Prompt 1 and Prompt 2 that asks what the posture of being made to lie down reveals about the reader's interior life before pivoting to outward obedience. Rewrite Prompt 2 to first surface what the passage reveals about God — specifically His identity as liberator and His claim of exclusive allegiance rooted in that prior act — before moving to self-examination about divided loyalty. The inward movement must begin with God, not with the reader's fear."

**Root cause confirmed across two passages:** The current template skips the inward layer entirely — jumping from stillness (Prompt 1) directly to action (Prompt 2) without an intermediate prompt asking what the scene reveals about God or about the reader's interior resistance. This is a structural template gap that recurs regardless of passage.

**Update — 16:54 cycle: fresh benchmark now 34/100 FAIL.** Three cycles, three passages, consistent regression: 82 (pass) → 61 (revise) → 34 (fail). Grade dropped to C.

This cycle's passage was Luke 15:11-14 (younger son's departure, vv.11-14 only — not the full parable). Trainer findings:
- Prompts reference the elder son's reaction, which does not appear in the assigned verses at all — misattributed quotation
- Prompts are not anchored to the specific movement of Luke 15:11-14: request, division, departure, squandering, famine, impoverishment
- First prompt should place the reader inside the act of gathering and leaving; second should press into what that departure posture reveals about the reader's own relationship to the Father's house; third should surface a felt need without resolving it

**This is now a code fix, not a training fix.** The inward layer must be structurally required by the Be Still template. Propose a change to how the Be Still prompts are built in `src/generation/real_section_generator.py` that enforces the sequence: (1) stillness → (2) inward/God-revealing → (3) outward/response.

The misattributed quotation issue also needs a post-generation guard: the Be Still output must be checked against the assigned focal verses to ensure no content references characters or events outside the passage range.

---

**Update — 19:04 cycle (Be Still 78/100 REVISE, closing prompt identified as hardcoded):**

Score recovered to 78 (revise) but still not passing. New specific code target confirmed:

The closing Be Still prompt (Prompt 3) is generated from a hardcoded template that produces "answer God with one honest sentence of trust, repentance, or gratitude" regardless of passage. This tripartite formula is structurally passage-agnostic — it fires unchanged for any passage content.

**Target:** `src/generation/real_section_generator.py` — the closing-prompt template for Be Still Prompt 3. Replace the hardcoded category list with a `passage_tension` variable that the generator must derive from the exposition's named tension or image. The closing prompt template should require the generator to surface the specific unresolved weight of the passage (e.g., the force of "makes" in Psalm 23) rather than offering a fixed menu of postures.

Trainer's priority fix this cycle: Replace Prompt 2 with a genuinely inward prompt that stays inside the passage — specifically asking the reader to notice where they are in the Psalm's landscape (lying down, being led, walking through the valley) before any application is offered. Current Prompt 2 introduces "striving" which is not in the text.

**Summary of all Be Still code targets (in priority order):**
1. Closing prompt: replace tripartite fallback with `passage_tension` variable interpolation
2. Prompt 2: add mandatory inward layer (what does the passage reveal about God) before moving to application
3. Post-generation guard: check that no content references characters/events outside the assigned focal verse range

---

**Update — 21:25 cycle (Be Still 91/100 PASS — benchmark cleared):**

Be Still fresh benchmark jumped from 78 to **91/100 (pass)**. Grade: B-. This is the first clean pass on the fresh benchmark. Something in the recent training cycles is working.

The trainer still recommends keeping Be Still on approved-artifact drills until the pass is consistent, but this is a meaningful positive signal. If the next two benchmark cycles also pass ≥80, consider whether Be Still has cleared its structural blocker.

The three code targets above (closing prompt, inward layer, post-gen guard) are still open — the 91 pass may reflect a favorable passage rather than a structural fix. Do not close those until you've confirmed the template changes are in place.

---

**Update — 23:13 cycle: Be Still 84/100 PASS — second consecutive pass.**

Two consecutive fresh benchmark passes (91, 84). Grade holding at B-. This is the first sustained run above the 80 threshold. The trainer still recommends approved-artifact drills but the structural trajectory is positive.

Watch for a third consecutive pass before declaring the template issues resolved. The three code targets (closing prompt, inward layer, post-gen guard) remain open until confirmed fixed in code — two passing benchmarks on possibly favorable passages don't prove the template is structurally sound.
