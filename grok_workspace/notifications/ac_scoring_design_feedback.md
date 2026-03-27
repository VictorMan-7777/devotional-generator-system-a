FEEDBACK: ac_scoring_design.md — DESIGN ACKNOWLEDGED, CODE PROPOSAL REQUIRED

The design structure is sound. Per-worker AC criteria split (deterministic vs semantic defer) is the right approach. Schema shape (ac_scores TEXT + ac_score INTEGER on autoresearch_experiments) is correct.

**What is missing — the divergence layer:**

The design only adds a second score. It does not detect when trainer score and AC score tell different stories. That gap is the primary value of running AC at all.

Example: trainer gives exposition 85/100. AC gives 40/100 (wordcount low, no grounding). What do you do? If you have no divergence detection, you accumulate two numbers with no logic connecting them.

What needs to happen:
- When trainer_score >= 70 AND ac_score < 50 → flag as "suspicious pass" (trainer reward hacking)
- When trainer_score < 50 AND ac_score >= 70 → flag as "suppressed quality" (trainer penalizing correct output)
- Both divergence flags should appear in the experiment log and surface in the monitor

**Next step:**

Write the code proposal: src/validation/ac_scorer.py
Include:
- score_exposition(), score_be_still(), score_action(), score_prayer() functions
- calculate_ac_score() aggregation
- detect_divergence(trainer_score, ac_score) → "suspicious_pass" | "suppressed_quality" | "aligned" | None

Submit as a .py file in grok_workspace/proposals/. Post to pending_approval.md.
