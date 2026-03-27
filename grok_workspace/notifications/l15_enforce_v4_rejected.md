REJECTED: l15_enforce.py v4 — not run. Augment pattern fixed (good). Three remaining bugs.

Bug 2 (step 1): replacement still puts two fields on ONE line with a comma:
  `evidence: tuple[str, ...] = (),        stalled_benchmarks: tuple[str, ...] = ()`
  This is invalid Python. A dataclass field cannot follow another field on the same line.
  The replacement must produce two separate lines. The stalled_benchmarks field belongs on its own newline with 4-space indent.

Bug 3 (step 2): the stalled_def replacement still contains `\n\n\n def curriculum_workers()` — note the space before `def`. That space is extra and produces invalid indentation. Remove the leading space before `def`.

Bug 4: no asserts after any re.sub. Use re.subn to get count, assert count == 1 (or > 0) before writing.

Fix bugs 2, 3, 4 and resubmit v5.
