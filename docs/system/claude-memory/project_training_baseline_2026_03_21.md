---
name: Training Baseline 2026-03-21
description: Real DB pass rates from registry.db as of 2026-03-21 evening — use to detect fabrication
type: project
---

Actual pass rates from registry.db autoresearch_experiments as of 2026-03-21 ~21:40 local:

| worker | total | passes | pass_pct |
|--------|-------|--------|----------|
| exposition_writer | 1775 | 9 | 0.5% |
| passage_researcher | 938 | 917 | 97.8% (graduated) |
| outliner | 862 | 73 | 8.4% |
| be_still_writer | 463 | 14 | 3.0% |
| prayer_writer | 450 | 30 | 6.7% |
| action_writer | 432 | 28 | 6.5% |
| pdf_art_director | 146 | 107 | 73.3% |
| pdf_layout_engineer | 22 | 19 | 86.4% |

**Why:** Grok was fabricating ~98-99% pass rates by confusing "gate threshold" (graduation target) with actual pass count. These are the real numbers from direct SQL queries.

**How to apply:** If Grok reports pass rates above 20% for outliner, exposition, be_still, prayer, or action workers, it is likely fabricating. Cross-check by running query_db directly.

**Key insight:** Supervisor cycle JSON fields like `experiment_gate_status: {outliner: 815/800}` mean "815 total experiments, 800 needed to graduate" — NOT "815 total, 800 passing."
