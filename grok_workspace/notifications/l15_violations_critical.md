CRITICAL DIRECTIVE: L15 violations — multiple workers exceeding consecutive-failure cap

The policy guardian reports 9 high-severity L15 violations this cycle. L15 caps retries at 3 consecutive identical failures on the same benchmark. These are all far beyond the cap:

exposition_writer:
  psalm-23-1-2:            144 consecutive identical failures
  proverbs-1-2 (book):      93 consecutive identical failures
  proverbs-1-4-5:            88 consecutive identical failures
  philippians-2-5-8:         25 consecutive identical failures
  john-10-11-13:             22 consecutive identical failures
  competition-volume-1:       9 consecutive identical failures
  trusting-god-in-uncertainty: 8 consecutive identical failures

be_still_writer:
  luke-15-11-14:             15 consecutive identical failures

action_writer:
  psalm-23-1-2:              84 consecutive identical failures

This means the training loop has been running the same deterministic code against the same benchmarks and getting the same failures — hundreds of times — without triggering any stop or rotation.

The cross-evaluator explains why for exposition: real_section_generator.py makes no LLM calls and uses fixed templates. Training feedback has no mechanism to change the templates. The loop is structurally open — retrying will never produce a different result until the templates change.

What you need to diagnose:
1. Where is L15 supposed to be enforced? What code is supposed to stop retrying after 3 consecutive failures on the same benchmark?
2. Is that enforcement code present, missing, or present but not wired to the training loop?
3. For exposition specifically: how does the training loop select which benchmark to run next? Is it always running psalm-23 and proverbs as fixed benchmarks, or is there supposed to be rotation?

What you need to propose:
Write a diagnosis to grok_workspace/notifications/l15_enforcement_diagnosis.md with answers to the three questions above and a recommendation for where to add the enforcement. I will decide whether to act on it.

Do not propose "rotate passages" as a substitute for enforcing L15. The law exists to prevent wasted cycles. Find where the enforcement belongs and propose adding it there.
