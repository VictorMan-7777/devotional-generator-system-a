# Gap Resolution Record

Use this template in every proposal `.md` file. A proposal without a completed Gap Resolution Record will be returned for redo.

---

## Gap Resolution Record

**Gap:**
[What is broken or missing — one sentence, system-directed]

**Root Cause:**
[Why it happened — the structural reason, not the symptom]

**Fix:**
[What changed — file(s), function(s), specific behavior]

**Rule:**
[What must always be true going forward — phrased as an invariant]

**Validation:**
[How we enforce the rule — test, gate, monitoring query, or review step]

---

## Example

**Gap:**
Workers assigned Psalm 23 passages on every cycle despite 144+ consecutive failures.

**Root Cause:**
No exclusion list exists in the passage queue builder; L15 enforcement blocks retries but does not prevent new assignments from being created.

**Fix:**
Added `EXCLUDED_PASSAGES` set to `build_assignment_queue()` in all four worker training agents; Psalm 23:1-2, 23:3-4, 23:5-6 added to the set.

**Rule:**
No passage with >50 consecutive failures across any worker may appear in a new assignment queue without operator re-authorization.

**Validation:**
`test_passage_exclusion.py` — asserts excluded passages never appear in queue output. Supervisor cycle query: `SELECT COUNT(*) FROM autoresearch_experiments WHERE benchmark_reference LIKE 'Psalm 23%' AND status='assigned' AND created_at_utc > datetime('now', '-1 hour')` must return 0.
