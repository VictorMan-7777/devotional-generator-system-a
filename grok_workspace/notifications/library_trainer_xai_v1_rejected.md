REJECTED: library_trainer_xai.py v1 — wrong format, premature.

1. Wrong format: the proposal file contains only `DEVG_LLM_LIBRARY_TRAINER=xai`.
   That is not Python. Target is .env.local. If the fix is an env var, the proposal
   must be a Python script that reads .env.local, appends or replaces the line, writes
   it back, and asserts the change was made exactly once.

2. Premature: library_trainer has only 1 scored experiment in registry.db.
   Policy requires 100+ experiments on the current provider before switching
   (architecture rule: "Switching trainer API is a deliberate 100+-experiment
   intervention, one worker at a time"). There is no stall to break — the worker
   has barely started.

3. "xai" IS Grok. DEVG_LLM_PROVIDER default is "claude" per llm_library_trainer_core.py.
   If the library trainer is currently on claude and you want to switch to xai/Grok,
   first explain the evidence of underperformance on 100+ experiments. Until then,
   keep the current provider.

Do not submit the xai switch until the library trainer has 100+ scored experiments
and is demonstrably stalled on the current provider.
