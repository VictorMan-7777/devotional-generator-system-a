# Competition Director Briefing
## DevG — Status and Proposed Collaboration

**Date:** 2026-03-25
**From:** [Operator name]
**To:** Competition Director
**Status:** DRAFT — for operator review before submission

---

## Summary

DevG is a multi-agent devotional content generation system being prepared for competition
submission. This briefing covers three items:

1. Our current state and what we are working toward
2. A proposed shared verification standard for Hebrews 1–10 — submitted for your review
   and validation
3. A question about the competition evaluation framework

---

## Current State

We have a working pipeline that produces structured daily devotionals (Be Still, Exposition,
Application, Prayer) from scripture passages. The system has accumulated over 4,000 scored
training experiments across seven workers and has graduated its research infrastructure workers
to 99%+ production reliability.

The content generation workers (Exposition, Outliner, Prayer, etc.) are still in training.
Current pass rates are in the range of 10–50% per worker depending on passage complexity.
We are working toward competition-level output quality, with the primary bottleneck being
the ability to handle theologically dense, argumentative texts (Hebrews, Romans) at the
precision standard required.

---

## Proposed Hebrews Verification Standard

We have been developing an internal quality standard for Hebrews 1–10 as a test passage
at competition-level difficulty. We would like to propose this standard as a shared gate
— applicable to our system and potentially to any system the competition evaluates.

The standard was developed by three domain reviewers on our team:
a theological reviewer, a structural/outliner specialist, and an operational data analyst.

**We are submitting it for your validation**, specifically requesting:

1. Confirmation that our theological scoring weights align with the competition's evaluation
   criteria (Christological precision 25%, Atonement precision 25%, Warning passage handling
   20%, Typological logic 20%, Pastoral-theological integration 10%)
2. Any additions, deletions, or weight adjustments you believe are appropriate
3. Whether our disqualifying failure categories (DF-1 through DF-6) align with your standards
4. Whether the structural automatic-fail conditions (SF-1 through SF-6) are appropriate

The full document is attached. [Attach: hebrews-passing-baseline.md]

---

## The Verification Proposal

We propose that Hebrews 1–10 be used as a verification test before any system is given
the actual competition input. Our reasoning:

- Romans 12:1-2 (a well-structured, familiar passage) is below competition difficulty.
  A system that passes on that passage has not demonstrated readiness for the Attributes
  of God territory the competition operates in.
- Hebrews 1–10 requires: sustained typological argument, Christological precision,
  careful handling of the warning passages (6:4-6, 10:26-31), and week-to-week arc
  coherence across a complex argument. These are the same demands the competition input
  will make.
- Using a pre-agreed, Director-validated standard means both systems — ours and any
  competing systems — are evaluated against the same criteria before the competition
  input is introduced.

We are not requesting an advantage. We are requesting a shared standard that protects
the integrity of the competition evaluation.

---

## A Question for the Director

We want to be honest about where we stand. We have missed the initial deadline. We are
continuing to work toward competition-level output, and we are using the Hebrews 1–10
standard as our internal readiness gate. When we can demonstrate that our system passes
that gate, we intend to come to you and ask whether it is still possible to submit.

We are not asking for that conversation now. We are asking for clarity on one thing
so we can make that request honestly when the time comes:

**If a team missed the initial deadline but can demonstrate competition-standard output
on the Hebrews verification passage, is there any pathway for a late submission — or
is the initial deadline a hard close?**

Understanding this now lets us focus our effort appropriately. If there is a pathway,
we will pursue it. If there is not, we will know that before we ask.

---

## Next Steps

We are preparing our system to run Hebrews 1–10 as an internal readiness test. We will
share those results once complete.

We welcome your feedback on the proposed Hebrews standard, and look forward to the
conversation.

---

*[Operator signature / contact]*
