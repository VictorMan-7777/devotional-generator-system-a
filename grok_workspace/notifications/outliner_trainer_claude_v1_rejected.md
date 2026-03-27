REJECTED: outliner_trainer_claude.py v1 — wrong file format, premature.

1. Wrong format: the proposal is a .py file containing an env var assignment (`DEVG_LLM_OUTLINER=claude`).
   That is not Python. Target is .env.local. If the fix is an env var, the proposal should modify .env.local directly — read the file, append the line, write it back.

2. Premature: the stall is a scheduler problem — the assignment queue is empty because all harness combos hit the infeasible threshold. Fix the assignment generation problem first (infeasible threshold). If the scheduler generates assignments and the outliner still plateaus after 50+ new experiments, then consider the LLM provider switch.

Do not submit the Claude switch proposal until the infeasible threshold is fixed and the outliner has run at least one full cycle with assignments.
