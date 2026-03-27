REJECTED: l15_enforce.py v2 — four bugs, not run

1. Step 1 replacement drops class header.
   Pattern captures the fields in group 1. Replacement is just `\1 + new_field`.
   The `@dataclass(frozen=True)\nclass WorkerTrainingReview:` prefix is NOT in group 1 and NOT in the replacement — it is consumed by the match but not re-emitted. The class declaration disappears.

2. Step 3 augment pattern is missing one closing paren.
   The actual line at training_manager.py:970 is:
     reviews = [_augment_review_with_advice(item, advice_by_worker.get(item.worker_name, [])) for item in reviews]
   Note the `)` after `[]` that closes `_augment_review_with_advice(`. Your pattern ends `\[\]\) for item in reviews\]` — missing that `)`. Pattern will not match.

3. Step 3 uses `replace(old, ...)` which is `dataclasses.replace`. It is not imported in the script.

4. No assert statements — any of steps 1/2/3 can silently produce 0 substitutions and the file still gets written. All three steps need asserts before writing.

Before resubmitting:
- For step 1: make sure the entire matched block (decorator + class header + fields + new field) appears in the replacement, not just group 1
- For step 3: read line 970 exactly and copy the closing parens into the pattern
- Add `from dataclasses import replace` to the script imports
- Add an assert after each re.sub that at least 1 substitution occurred

Resubmit v3.
