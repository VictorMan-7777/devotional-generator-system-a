REJECTED: l15_enforce.py v1 — two critical issues

1. Step 3 is a stub. Line 55-56:
   # Find review creation lines approximate replace manual later
   print("L15 patch applied - manual review integration needed in build_training_manager_review for each worker loop")

   The file is written (line 57) but the integration code (lines 37-53) is never applied to the file — it is just a Python string variable that goes unused. This proposal would add _stalled_passages to the file but not wire it to anything. A proposal must be a complete runnable patch.

2. SQL parameter bug in _stalled_passages. The query has:
   datetime('now', '-? days')

   The `?` inside a string literal is not a bind parameter. SQLite will not substitute it. The query will either error or return wrong results. The days_back value must be concatenated or computed differently. Look at how SQLite handles parameterized date arithmetic.

Fix both and resubmit. Do not submit step 3 as a comment or pseudo-code — write the actual re.sub pattern that inserts the stalled block into build_training_manager_review.
