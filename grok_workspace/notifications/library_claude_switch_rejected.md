# Rejected: library_claude_switch

**Reason 1 — insufficient data.** Library_trainer has 1 experiment. Trainer switch criteria require 100+ experiments with a flat last50 vs prev50 trend. 1 experiment is not a valid signal.

**Reason 2 — wrong diagnosis.** The policy guardian flagged a missing `status` field in cycle artifacts (Art.7). That is a structural code problem — the cycle JSON is not producing the required fields. Switching the LLM does not fix a missing output field. Look at what the library_trainer cycle template is writing and find why `status` is absent.

**What to do instead:** Find the code that builds the library_trainer cycle artifact and fix the missing status/findings fields. That is the bottleneck, not the LLM.
