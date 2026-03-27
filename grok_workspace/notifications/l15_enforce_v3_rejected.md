REJECTED: l15_enforce.py v3 — assert fired, file safe. 4 bugs.

Assert output:
  dataclass pattern OK
  AssertionError: augment pattern fail

Bug 1 (step 3 = same): `augment_test` pattern ends with `\[\]\) for item in reviews\]`.
The actual line 970 is:
  reviews = [_augment_review_with_advice(item, advice_by_worker.get(item.worker_name, [])) for item in reviews]
Count the closing parens after `[]`: `)` closes `.get(`, `)` closes `_augment_review_with_advice(`. Pattern has one `)`, needs two. Fix: `\[\]\)\) for item in reviews\]`. Same fix needed on the augment_pattern line (step 3).

Bug 2 (step 1): replacement joins two fields on one line:
  `evidence: tuple[str, ...] = (),        stalled_benchmarks: tuple[str, ...] = ()`
  This is not valid Python. Two dataclass fields on the same line separated by `,` is a syntax error.
  Each field must be on its own line with consistent indentation (4 spaces).

Bug 3 (step 2): replacement string contains ` def curriculum_workers()` (extra leading space). That would produce ` def curriculum_workers():` with 1-space indent — invalid Python.

Bug 4 (step 3): The `stalled_benchmarks` field is referenced in `replace()` call but step 1 may fail silently (no assert after the re.sub). Add asserts after each re.sub to count substitutions.

Fix all 4 and resubmit v4.
