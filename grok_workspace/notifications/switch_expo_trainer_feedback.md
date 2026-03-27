# switch_expo_trainer — Applied + Feedback

**Status:** Applied 2026-03-23. `DEVG_LLM_EXPOSITION_WRITER=claude` added to `.env.local`.

## What you got right

- Correct diagnosis: flat pass rate after 1671+ experiments is the right trigger for a trainer API rotation. The 100-experiment rule exists precisely for this situation.
- Correct target: the router already supported `DEVG_LLM_EXPOSITION_WRITER` — you found a real lever, not a speculative one.
- Evidence cited was concrete: experiment count, trajectory, failure examples.

## What to watch for next

- Success criterion: >5% pass rate after next 20 exposition experiments. Monitor and report.
- If Claude trainer also plateaus, the next step is code changes (hardcoded templates), not another API switch.
- The structural exposition bugs (closing template, fragment injection) are separate from trainer quality. Switching trainers will not fix them. Submit those code proposals separately — the trainer will still be blocked by the templates regardless of which API generates the text.
