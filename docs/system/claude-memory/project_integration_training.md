---
name: Integration training requirement
description: Workers train in isolation now; integration training phase needed once outliner reaches consistent output
type: project
---

Workers currently train independently. This is a known gap — individually trained workers may fail when assembled into the real pipeline for the first time.

**Why:** The pipeline hinges on the outliner. Downstream workers consume outliner output. If they never train on real outliner output, integration failures are invisible until final assembly.

**Core requirement (operator direction 2026-03-25):**
Each worker must understand not only how to create its own section but how to integrate the input coming through the pipeline. Training must include full upstream context:
Pipeline order (operator-confirmed 2026-03-25):
Outliner → Quote Worker → Exposition Writer → Theological Reviewer → [Exposition output] → Be Still → Action Steps → Prayer

- Outliner: identifies scripture, produces structure; output feeds both Quote Worker and Exposition Writer
- Quote Worker: receives outliner output; selects quote based on scripture identified
- Exposition Writer: receives outliner output; finalizes day's direction (first pass); output also provides focus context for all downstream workers
- Theological Reviewer: receives day's direction from exposition; validates quote choice is appropriate for that direction
- Be Still: receives exposition output as primary frame
- Action Steps: receives exposition output as primary frame
- Prayer: receives exposition output as primary frame; closes what the full chain opened

Trainer agents must also be updated — they cannot score a section in isolation without penalizing work that ignores upstream context.

**Required design (Grok task, posted 2026-03-25):**
- Trigger: outliner reaches consistent (not perfect) output
- Phase shift: downstream workers train on real outliner output with full upstream context
- Workers interact across the chain during training
- Trainer agents updated to evaluate integration quality, not just section quality in isolation
- End-to-end pipeline test required before any worker is declared production-ready

**Exposition Writer helpers:**
Grammar assistant and theological reviewer assist the exposition writer to produce quality content — they are not standalone pipeline stages. Exposition writer training must include working with these helpers so their presence is not a surprise in production.

**Pipeline code status:**
Training mode has been the focus; current pipeline code may not reflect the intended architecture above. A pipeline verification pass is required before integration training begins — confirm the code matches the design, then tweak as needed.

**How to apply:** Do not declare training complete based on isolated pass rates alone. Pipeline code must be verified against intended architecture first. Integration training phase must complete and pipeline test must pass before workers are production-ready. Flag this if anyone proposes graduating the full set without integration validation.
