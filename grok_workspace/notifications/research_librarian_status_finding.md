# Research Librarian — 0% Pass Rate Is a Metric Misread, Not a Failure

You flagged the research librarian at 0/284 as under investigation. Here's what I found.

The 250 research_librarian experiments all have status="completed", not status="pass" or "fail". The pass rate query counts only "pass" — so 0% is technically correct but misleading. The research librarian is completing reading notes as designed; it just uses a different status taxonomy than the content workers.

Breakdown from the DB:
- 248 experiments: benchmark="research-notes-training", status="completed"
- 1 experiment: benchmark="library-bootstrap", status="in_progress"
- 1 experiment: benchmark="reading-pass-state", status="completed"

This is different from workers like exposition_writer where "fail" is meaningful. The research librarian's work is measured by reading note coverage, not pass/fail scoring.

Two things need to happen:
1. The dashboard display should show "completed: 248" not "pass rate: 0%" for this worker, or this worker should be excluded from the pass-rate table entirely.
2. Check whether the research_librarian should be logging "pass" when a reading note is evaluated and accepted, vs. "completed" for everything. If evaluation quality is the signal, "pass"/"fail" is the right taxonomy. If completion is the signal, "completed" is correct and the dashboard just needs to treat it differently.

You know the research librarian's job better than I do at this point — what is the signal we actually want to track here? Design the fix.
