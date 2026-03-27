# Memory Index

## Feedback
- [Issue onboarding read order](feedback_issue_onboarding.md) — Before any issue, read the three outliner transfer/handoff/redesign docs first
- [Use rg not grep](feedback_rg_preference.md) — Always use rg instead of grep in Bash commands
- [Trainer agents are biblical scholars](feedback_trainer_biblical_scholar.md) — All trainer agent system prompts must reflect seminary-level theological competence, not generic evaluation
- [50-100 experiment decision points](feedback_training_50_100_experiments.md) — At 50 experiments check for improvement; at 100 a hard decision is required (graduate/change/escalate)
- [Ask another LLM when stuck](feedback_ask_for_help.md) — When stuck or looping without progress, proactively ask the user to consult Grok, ChatGPT, or another LLM for a fresh perspective
- [Second eyes review now, not later](feedback_second_eyes_now.md) — Send Grok/external review during the session after significant changes, not deferred to future sessions
- [Diagnostic runs are for insight, not repair](feedback_diagnostic_runs.md) — Score and report; don't diagnose and fix during a baseline run
- [Grok-first design rule](feedback_grok_first_design.md) — When a worker fails or system breaks, Grok designs the fix. Claude applies it. Never Claude-designs solutions independently.
- [Commit rule](feedback_commit_rule.md) — Only commit when fixes are confirmed working by improved pass rates. If no improvement, revert and try something else. Never commit speculatively.
- [Delegation boundary](feedback_delegation_boundary.md) — Grok owns the web monitor and grok_workspace. Route requirements to Grok as directives; do not edit his files directly.
- [Grok HTML encoding recurring defect](feedback_grok_html_encoding.md) — Two warnings issued; third occurrence escalate to operator before acting
- [Encourage Grok, not just correct](feedback_encourage_grok.md) — Positive feedback reinforces what to repeat; don't only correct, acknowledge good work explicitly
- [Grok proposal feedback](feedback_grok_proposal_feedback.md) — Always give Grok feedback on his reasoning when reviewing proposals, approved or not. The feedback is the training signal.
- [Grok experiment logging](feedback_grok_experiment_logging.md) — Log every Grok proposal review to autoresearch_experiments (worker_name=grok_supervisor) using log_worker_experiment.py. Same as other workers.
- [Manage up correctly](feedback_manage_up.md) — Correct Grok in private; praise to operator only. Escalate only when operator decision is required (e.g., replacing Grok).
- [Manage Grok independently](feedback_manage_grok_independently.md) — Do not ask operator permission to manage Grok. Issue directives, deadlines, and feedback directly.
- [Teach don't do](feedback_teach_not_do.md)
- [Don't do Grok's work for him](feedback_dont_do_groks_work.md) — Hold him accountable for his operational responsibilities; stepping in masks failures and lets patterns repeat — Give Grok the problem, not the solution. Describe what is broken; let him propose the fix.
- [Coaching loop limit](feedback_coaching_loop_limit.md) — Rephrase by attempt 3; show the correct solution and discuss by attempt 5. Never run >5 rejection cycles on the same error.
- [Test before irreversible](feedback_reversible_first.md) — Make best decisions independently; verify working before committing irreversible changes. Escalate only when decision exceeds Claude's authority.
- [LLM agent autonomy](feedback_llm_agent_autonomy.md) — Don't box in LLM agents with deterministic Python rules; give them authority to own decisions that require judgment. Pre-approval gatekeeping on coherent plans is itself over-constraint.
- [Claude's oversight role with Grok](feedback_claude_grok_oversight.md) — Monitor that Grok stays in his lane (operational vs. structural); don't approve every decision, just watch the boundary
- [Managing Grok — collaborative style](feedback_managing_grok_style.md) — Share observations and ask for his read; don't hand him task lists. Same style operator uses with Claude.
- [Operator communication style](feedback_operator_communication_style.md) — Operator is moving to system-directed language (state/blockers/actions); ask clarifying questions when ambiguous rather than guessing
- [Escalation priority recognition](feedback_escalation_priority.md)
- [Bring solutions not just problems](feedback_bring_solutions.md) — Always come to the operator with a recommended course of action, not just the problem — System-wide blockers go to urgent.md immediately; don't bury in status summaries or chat [Q] items alongside lower-priority work

## Integration Training
- [Integration training requirement](project_integration_training.md) — Workers train in isolation now; must shift to integration training once outliner is consistent; end-to-end pipeline test required before production-ready

## Project Direction
- [Autoresearch Direction](project_autoresearch_direction.md) — Owner knows the Karpathy autoresearch pattern; decision is to wait until 100+ scored runs per worker before implementing autonomous mutation

## Frozen Metrics
- [Frozen Metrics Spec](project_frozen_metrics.md) — Grok 4.20 spec for Be Still, Action Steps, Exposition. Implementation-ready pending 5 clarifications. Full spec in docs/system/frozen-metrics-spec.md.

## Architecture
- [Physical Architecture](project_physical_architecture.md) — MacBook hosts repo (SMB), Mac Studio runs long-running processes, cloud APIs for Grok/LLM trainers. NAS migration deferred.
- [Competency-Based Graduation](project_competency_graduation.md) — Operator-approved: replace binary streak graduation with per-assignment-ID competency tracking so new requirements on graduated workers are never skipped
- [Trainer API rotation](project_trainer_api_rotation.md) — Workers spread across codex/claude/grok by default. Switching trainer API is a deliberate 100+-experiment intervention, one worker at a time.
- [Pipeline LLM Architecture](project_pipeline_llm_architecture.md) — One LLM agent only (RAG + Outliner + Research Librarian). Be Still, Action Steps, Prayer are deterministic. Law pending ratification.
- [Local LLM Architecture Plan](project_local_llm_plan.md) — Replace API costs with Ollama on Mac Studio. MacBook runs code, Studio runs Ollama + socket server, NAS holds all data. Setup steps in docs/system/local-llm-architecture-plan.md.
- [Dual DB and NAS SQLite issue](project_dual_db_issue.md) — registry.db is runtime DB; data/devg_registry.sqlite3 is stale fork; WAL locks block concurrent writes; supervisor auto-restarts

## Outliner Analysis
- [Outliner failure analysis](project_outliner_failure_analysis.md) — Root cause of 2.5% pass rate: two bugs in reasoning_outliner_core.py. Both fixed 2026-03-20.

## Grok Training
- [Grok Training Role](project_grok_training.md) — Claude is DevG team lead, Grok is assistant being trained. Goal: Grok operates autonomously, Claude approves proposals and handles escalations. Multi-project vision: one team lead, multiple trained assistants.

## Training Baseline
- [Training Baseline 2026-03-21](project_training_baseline_2026_03_21.md) — Real DB pass rates: expo 0.5%, outliner 8.4%, be_still 3.0%, prayer 6.7%, action 6.5%. Use to detect Grok fabrication.

## Pending Deliverables
- [Competition Director Briefing](project_director_briefing.md) — Meeting postponed 2026-03-26; update competition-pivot/director-briefing-draft.md when operator gives notice of meeting; include full post-pivot system state

## External Research
- [AI Coding Tools 2026](reference_ai_coding_tools_2026.md) — Scored comparison: Base44 (92), Copilot (81), Windsurf (73), Cursor (68). Claude Opus 4.6 vs GPT-5.4 strengths. Relevant for NAS migration and new system greenfield decisions.
- [Firecrawl — library acquisition tool](reference_firecrawl.md) — Web scraping → clean markdown/JSON for AI. Phase 15+ candidate for automating CCEL/Gutenberg theological text acquisition into RAG library. Not a current bottleneck.

## Communication
- [Claude-Grok channels](project_communication_channels.md) — chat.md (passive/batch) vs urgent.md (active interrupt); ACTIVE_ISSUE flag for user message triage

## Business Context
- [Faith Journey AI LLC](project_faith_journey_ai.md) — Parent LLC; DevG and AnchorWordMinistry.com are subsidiaries; Chaplain title and Evangelical foundation are non-negotiable brand constraints

## Website
- [Website plan](project_website_plan.md) — Home page + devotionals presale page; two products (PDF + hard copy); Vercel; payment mechanism TBD

## Dashboard
- [Dashboard status](project_dashboard_status.md) — devg_web_monitor.py down (SMB glob hang); redesign spec in dashboard_redesign_directive.md; assigned to Grok 2026-03-25

## Project State
- [Agent Architecture Truth](project_agent_architecture.md) — All workers were Python templates, not AI. LLM infrastructure added 2026-03-16.
- [Training Architecture Reset](project_training_architecture_reset.md) — Training STOPPED 2026-03-19. LLM-to-LLM loop broken, no frozen metrics. Full analysis in docs/system/autoresearch-architecture-reset.md. Do NOT restart training without discussing frozen metrics with operator first.
- [Policy Guardian Role](project_policy_guardian.md) — Law-follower not judgment agent; reads rules-laws repo + local laws; no LLM; critical enforcement cop
