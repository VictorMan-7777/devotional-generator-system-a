# Outliner Crash — Psalms 35 Chapter Boundary

The outliner training cycle in the 12:41 supervisor cycle (2026-03-23__124138) crashed with returncode=1. No outliner assignments ran.

## The error

```
File "src/scripture/planner.py", line 137, in _chapter_last_verse
    raise ValueError(f"Unable to resolve chapter boundary for {book} {chapter}.")
ValueError: Unable to resolve chapter boundary for Psalms 35.
```

Stack trace path:
```
run_outliner_training_cycle.py
  build_outliner_training_cycle()
    run_assignment_with_revision()
      run_outline_assignment()
        suggest_study_window_size()
          _span_verse_count()
            _chapter_last_verse()  ← crash
```

## What this means

When the training cycle selects a passage from Psalms (Psalms 35 in this case), `suggest_study_window_size()` calls `_span_verse_count()` which calls `_chapter_last_verse()` — and that function cannot resolve the last verse of Psalms 35. This raises a hard ValueError that aborts the entire cycle.

This will happen for any Psalms passage where `_chapter_last_verse()` fails to resolve the chapter boundary. It may affect other Psalms chapters too.

## What needs fixing

**Target:** `src/scripture/planner.py`, the `_chapter_last_verse()` function around line 137.

Two options:
1. Fix the chapter boundary lookup so Psalms chapters resolve correctly (check what verse data source it queries and whether Psalms chapter verse counts are missing or miskeyed)
2. Add a graceful fallback in `suggest_study_window_size()` when `_span_verse_count()` raises — catch the ValueError and fall back to a default study window size rather than crashing the entire cycle

Option 2 is a safer short-term fix if the root cause (missing Psalms verse count data) is deeper. Option 1 is the correct long-term fix.

Submit a proposal with the specific change.
