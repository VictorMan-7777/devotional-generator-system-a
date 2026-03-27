# Library Trainer — Missing `status` Field (Policy Violation, 2+ Cycles)

The policy guardian has flagged the library_trainer artifact as missing required fields across at least two consecutive supervisor cycles:

- 19:04 cycle: `2026-03-23__164502__devg__library-trainer-review.json` — missing `['status']`
- 21:25 cycle: `2026-03-23__185632__devg__library-trainer-review.json` — missing `['status']`

**Art. 7 — Evidence Integrity:** All claims, completions, and state transitions require verified artifact evidence. Unverified claims are not admissible.

## What to fix

The library_trainer agent (wherever it writes its output JSON) must include a `status` field. The policy guardian requires both `status` and `findings` in the artifact.

Look at the script that produces `*devg__library-trainer-review.json` and ensure the output schema includes:

```json
{
  "status": "...",
  "findings": [...]
}
```

The `status` field should reflect whether the reviewed reading notes passed, need revision, or have outstanding issues. This is a one-line addition to the artifact builder — find it and add the field.

## Urgency

This is not blocking training, but it is generating 18 policy_guardian findings per cycle (the policy guardian flags all downstream workers when evidence is unverified). Fix it before the next library trainer review runs.
