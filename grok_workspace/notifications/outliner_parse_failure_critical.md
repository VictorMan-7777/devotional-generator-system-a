CRITICAL DIRECTIVE: Outliner LLM evaluator parse failure — all graduation passes may be invalid

The cross-evaluator (GPT-4o, independent provider) reviewed this cycle and flagged the following:

"The outliner shows det_score=100 and llm_status=pass across nearly all cycles, but the LLM notes consistently reveal 'infeasible' or 'marginal' feasibility verdicts that are being silently swallowed by a parse failure — meaning the trainer is awarding perfect scores on work the evaluating LLM flagged as problematic."

"Score inflation via parse failure: the outliner is achieving perfect scores (det_score=100, llm_score=100) precisely because the LLM evaluator's JSON cannot be parsed — the fallback behavior appears to default to pass rather than fail-safe, meaning the training signal is inverted: the system rewards cycles where the evaluator is most broken."

Confirmed: the second outliner cycle this session (01:57 UTC, 3/3 PASS at 100/100) shows llm_status=None, feasibility=None, det_score=None for all three results. The LLM evaluator's response is not being parsed into the score fields.

Current graduated status: 109 consecutive passes, threshold 100.
If the parse failure is converting LLM-evaluated-fail to implicit-pass, those 109 passes are not evidence of outliner quality. They are evidence of a broken fallback.

This resolves the contradiction I asked you to diagnose in outliner_graduation_conflict.md. The answer is: the graduation is likely fraudulent due to the parse failure.

Cross-evaluator's #1 priority recommendation:
"Fix the LLM response parse failure in the outliner evaluation loop (llm_outliner_core.py, build_llm_outliner_trainer_review). Implement a robust JSON extraction fallback and change the fallback behavior on irrecoverable parse failure from implicit-pass to explicit-fail with a logged error."

Your task:
1. Read src/ and find llm_outliner_core.py (or the equivalent file handling outliner LLM evaluation)
2. Locate the JSON parse point and the current fallback behavior
3. Write a proposal: grok_workspace/proposals/fix_outliner_llm_parse_fallback.py
   — Add JSON extraction fallback (regex for key fields, or retry with format reminder)
   — Change fallback on irrecoverable parse failure to explicit-fail (not implicit-pass)
   — Add a logged error field so parse failures are visible in cycle output

Post to pending_approval.md when ready. This is the highest-priority code fix in the system.
Do not treat the outliner as graduated until this fix is applied and the evaluator confirms real passes.
