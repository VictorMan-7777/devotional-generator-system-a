DIRECTIVE: real_section_generator.py — 51 trainer proposals, single structural defect

The latest trainer_proposals.json (2026-03-24T00:51Z) shows:
  51 distinct proposals
  All 51 target: src/generation/real_section_generator.py
  All single-mention (first cycle seen)
  0 high-confidence (≥3 cycles)

This is not a normal trainer proposal signal. 51 variations of the same complaint about one file in one cycle means the trainers are encountering the same structural defect from multiple angles. The two most representative:

1. "Eliminate the recurring meta-commentary template that describes 'the text' and 'the reader' in place of actual passage content."
   — Sentences like "The text does not X — it Y," "it rewards the reader who Z," "Honest application therefore begins with honest reading," "Devotion trained by this kind of text becomes steadier over time."
   — These appear when the model lacks sufficient passage-specific content.

2. "Remove or isolate the hardcoded section-header string that is being injected mid-prose as a fragment."

The exposition LLM benchmark this cycle: 45/100 fail. generic_phrase_count: 12.

This is a code defect in real_section_generator.py, not a training problem. Training cannot fix a template that injects generic sentences structurally.

Your task:
Read src/generation/real_section_generator.py. Identify where these meta-commentary patterns originate — are they in the prompt template, a post-processing step, a fallback slot, or somewhere else? Then write a proposal (grok_workspace/proposals/fix_meta_commentary_injection.py) that removes or constrains the injection points.

The proposal must be runnable code, not pseudocode. Post to pending_approval.md when ready.

Exposition is at 1/563 pass (0.2%) after 563 experiments. The trainer API switch bought some time but the structural defect is still bleeding through. Fix the source.
