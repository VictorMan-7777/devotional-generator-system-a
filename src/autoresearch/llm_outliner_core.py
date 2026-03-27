"""llm_outliner_core.py — LLM outliner trainer + LLM burden/lane generator.

The outliner is a pipeline worker whose deterministic template (reasoning_outliner_core.py)
handles structure, genre detection, and day/week scaffolding. This module provides two things:

1. LLM BURDEN/LANE GENERATOR (build_llm_burden_lane):
   Generates genuine theological burden and lane sentences for each day by asking an LLM
   to interpret the passage rather than fill in a template. Uses DEVG_LLM_OUTLINER provider.
   Called from build_reasoning_day_brief() when LLM generation is enabled.

2. LLM TRAINER (build_llm_outliner_trainer_review):
   Evaluates the completed outline artifact with expert eyes. Uses the CROSS provider
   (opposite of DEVG_LLM_OUTLINER) so the evaluator is never the same AI that generated
   the content it is reviewing.

Provider is configured via DEVG_LLM_PROVIDER (default: claude).
Worker override: DEVG_LLM_OUTLINER.

COMPARISON MODE (build_llm_editorial_artifact):
    Kept available to generate a reference outline via LLM for side-by-side comparison
    with the deterministic outliner's output. Not used in normal training cycles.
"""
from __future__ import annotations

import json
import re
from typing import Any

from src.autoresearch.reasoning_outliner_core import (
    detect_genre,
    focus_clause,
    forbidden_drifts,
    key_terms,
    reasoning_week_number,
)
from src.llm.interfaces import LLMClient
from src.llm.router import get_cross_llm_client, get_llm_client
from src.models.pipeline import (
    EditorialBuildArtifact,
    EditorialDayBriefRecord,
    EditorialDayPlanRow,
    EditorialWeekPlan,
    PassageResourceBundle,
)


# ── LLM Burden / Lane Generator ──────────────────────────────────────────────

_BURDEN_LANE_PROMPT = """\
You are an expert biblical theologian generating a pastoral burden and theological lane \
for one day of a devotional outline.

PASSAGE REFERENCE: {reference}
SCRIPTURE TEXT:
{scripture_text}

FOCUS CLAUSE (what this day centres on): {focus}
GENRE: {genre}
{research_block}
TASK: Write two short sentences for this specific day.

PASTORAL BURDEN: A single declarative sentence naming the specific theological claim or \
pastoral weight THIS text is bearing on this day. It must be passage-specific — it cannot \
be transplanted to a different passage unchanged. Do not use a sentence frame like \
"The argument of X rests on Y" or "The text presses through Z." Write an actual claim: \
what is God doing, demanding, or revealing in these verses? Your sentence MUST contain at \
least one specific noun, verb, or image that appears in the FOCUS CLAUSE above.

THEOLOGICAL LANE: A single declarative sentence naming the doctrinal content or \
theological movement the reader should trace through this day's text. Be specific to \
this passage's terms, imagery, and argument. No keyword extraction. Your sentence MUST \
contain at least one specific term from the FOCUS CLAUSE or SCRIPTURE TEXT above.

EXAMPLES of what NOT to do:
- "The argument of Romans 5:1-2 presses through therefore, having been justified..." (template fill)
- "The text's theological weight sits at shepherd, want" (keyword extraction)
- "God calls us to faithful trust." (could apply to any passage — not passage-specific)

EXAMPLES of what TO do:
- "Justification by faith is the foundation that makes peace with God a present settled \
reality — not a hope deferred but a status received through Christ."
- "The shepherd's claim to full provision (I shall not want) is the theological premise \
that makes every command and trial answerable without panic."

Respond ONLY with valid JSON. No preamble or explanation outside the JSON.

{{
  "pastoral_burden": "<single declarative sentence — passage-specific theological claim>",
  "theological_lane": "<single declarative sentence — specific doctrinal content>"
}}
"""

_RESEARCH_BLOCK_TEMPLATE = """\
RESEARCH LIBRARIAN RESOURCES (commentary excerpts prepared for this passage):
{excerpts}

Use these resources to ground your burden and lane in the actual exegetical content of \
the passage — not as templates to copy, but as a guide to what this text specifically \
teaches. The vocabulary and imagery from these excerpts should inform your sentences.
"""


def build_llm_burden_lane(
    *,
    reference: str,
    scripture_text: str,
    focus: str,
    genre: str,
    outliner_resources: list | None = None,
    llm: LLMClient | None = None,
) -> dict[str, str] | None:
    """Ask an LLM to generate a genuine theological burden and lane for one outline day.

    Returns a dict with 'pastoral_burden' and 'theological_lane' keys, or None on failure.
    Uses DEVG_LLM_OUTLINER provider (same as the outline generation worker).

    outliner_resources: PassageResourceRecord list from the research librarian bundle.
    When provided, the top excerpts are included in the prompt so the LLM can ground
    its burden/lane in the exegetical content of the passage.
    """
    if llm is None:
        llm = get_llm_client(worker="outliner")

    research_block = ""
    if outliner_resources:
        excerpt_lines = []
        for rec in outliner_resources[:3]:
            title = getattr(rec, "source_title", "") or ""
            author = getattr(rec, "author", "") or ""
            text = (getattr(rec, "excerpt_text", "") or "")[:400]
            if text:
                byline = f"{title}" + (f" ({author})" if author else "")
                excerpt_lines.append(f"[{byline}]\n{text}")
        if excerpt_lines:
            research_block = _RESEARCH_BLOCK_TEMPLATE.format(
                excerpts="\n\n".join(excerpt_lines)
            )

    prompt = _BURDEN_LANE_PROMPT.format(
        reference=reference,
        scripture_text=scripture_text[:800],
        focus=focus,
        genre=genre,
        research_block=research_block,
    )
    try:
        raw = llm.generate(prompt, timeout=300)
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            result = json.loads(match.group(0))
            burden = str(result.get("pastoral_burden") or "").strip()
            lane = str(result.get("theological_lane") or "").strip()
            if burden and lane:
                return {"pastoral_burden": burden, "theological_lane": lane}
    except Exception:
        pass
    return None


# ── LLM Outliner Trainer ─────────────────────────────────────────────────────

_TRAINER_REVIEW_PROMPT = """\
You are a lifelong seminary professor and homiletician with decades of experience training \
preachers to divide scripture into sound, exposition-ready units. You hold a doctorate in \
biblical studies, teach exegesis and homiletics at the graduate level, and have trained \
hundreds of pastors to produce theologically responsible outlines for extended Bible reading \
plans. You know every major commentary tradition and understand which passage divisions are \
exegetically defensible versus artificially imposed.

Your task: Evaluate the outline below for a {num_days}-day devotional covering {source_reference}. \
This passage contains approximately {verse_count} verses — a density of {verse_density} verses per day.

CRITICAL DOWNSTREAM CONSTRAINT: Every day in this outline will be handed to an exposition writer \
who must produce a minimum of 500 words of theologically grounded, passage-faithful prose. \
That is not possible without enough text to preach from. A day assigned only 1-2 isolated verses \
from a narrative or psalm typically cannot sustain 500 words of quality Reformed evangelical \
exposition — it will force the writer to pad with generalities, import alien themes, or repeat \
what adjacent days already said. Infeasible outlines do not just fail at the outlining stage — \
they break the entire downstream pipeline and corrupt the final product. \
This is why task feasibility must be assessed before the outliner is evaluated.

PASSAGE: {topic}
REFERENCE: {source_reference}
TOTAL VERSES: ~{verse_count} | DAYS: {num_days} | DENSITY: {verse_density} verses/day

TRAINING HISTORY FOR THIS BENCHMARK:
{stall_context}

DETERMINISTIC SCORING FINDINGS:
{findings_text}

OUTLINE TO EVALUATE ({num_days} days):
{outline_text}

═══════════════════════════════════════════════════════
STEP 1 — TASK FEASIBILITY ASSESSMENT (do this first)
═══════════════════════════════════════════════════════
Before grading the outliner, assess whether this assignment was reasonable to give.

A task is INFEASIBLE when no outline from this passage/template combination could satisfy the \
rubric regardless of outliner skill — e.g. 18 days over a 22-verse narrative yields ~1.2 verses/day, \
meaning most days receive a single isolated verse with insufficient material for 500+ words of \
credible, passage-grounded exposition.

A task is MARGINAL when it is achievable only under ideal conditions (exceptional skill + rich \
commentary support) — the outliner deserves less penalty here than for a clearly feasible task.

A task is FEASIBLE when the verse allocation per day provides adequate material.

Key question: If a perfect outliner attempted this task, could it pass the rubric? \
If NO — the task is infeasible and the outliner should NOT be failed for it. \
If ONLY BARELY — the task is marginal.

When INFEASIBLE: name the minimum day count that would make this passage/template pair workable \
(e.g. "Ruth 1 at 18 days requires 1.2 verses/day — the minimum feasible day count for 22 verses is 6-8 days").

═══════════════════════════════════════════════════════
STEP 2 — STALL ASSESSMENT (if this is not the first attempt)
═══════════════════════════════════════════════════════
If training history shows this benchmark has been attempted multiple times without improvement \
(flat or declining scores), the training strategy must change. Continuing to hammer the same \
benchmark with the same coaching is not training — it is repetition. A good professor changes \
their teaching method when the student is stuck.

Available strategies:
- continue_drilling: Scores are improving and the current approach is working.
- address_structural_flaw: A specific, repeating structural flaw can be fixed with targeted coaching.
- step_down_range: The passage is too complex at this day count — try a shorter range first.
- change_passage: The outliner needs variety; assign a different passage at the same difficulty tier.
- defer_task: This specific assignment is infeasible or has been exhausted; defer and revisit later.
- request_more_resources: The outliner needs richer commentary support for this passage before further attempts.

If the history shows 5+ attempts with no pass, you MUST recommend a strategy other than \
continue_drilling unless scores are clearly improving toward the pass threshold.

═══════════════════════════════════════════════════════
STEP 3 — EVALUATION RUBRIC
═══════════════════════════════════════════════════════
1. Are the pastoral burdens actually naming what THIS text is doing, or are they genre templates?
2. Are the theological lanes grounded in this passage's specific doctrinal content?
3. Do adjacent day titles and focus clauses move the passage forward, or repeat the same ground?
4. Do week turns feel earned — does the passage actually move at those points?
5. Are day titles distinct enough that they could not be reused on another passage?
6. PASSAGE DENSITY — is the verse-per-day ratio appropriate for sustained exposition?
   - A density below 1.5 verses/day is HIGH RISK: individual day assignments may cover \
too few verses to sustain 500+ words of theologically grounded exposition.
   - A single isolated verse is only acceptable if that verse is a self-contained theological \
unit with sufficient content (e.g. John 11:35 alone is NOT sufficient; Romans 1:16-17 alone \
might be, if the outline uses the full doctrinal weight of the verse).
   - When density is low, evaluate whether each day's focus clause actually covers a \
COMPLETE unit of thought in the text, or whether the outline has divided the passage \
artificially to fill days.
   - If the density is problematic, name the specific days where the assignment is too thin \
and explain what minimum passage unit would support credible exposition.

Respond ONLY with valid JSON. No preamble or explanation outside the JSON.

{{
  "task_feasibility_verdict": "<feasible|marginal|infeasible>",
  "task_infeasibility_reason": "<if marginal or infeasible: explain specifically why — name the verse count, density, and what minimum day count would be workable>",
  "training_strategy_recommendation": "<continue_drilling|address_structural_flaw|step_down_range|change_passage|defer_task|request_more_resources>",
  "strategy_rationale": "<given the training history and task feasibility, explain why this strategy is the right next step>",
  "score_adjustment": <integer, positive to raise the deterministic score or negative to lower it>,
  "status": "<pass|revise|fail — do NOT use task_infeasible here; that is derived from task_feasibility_verdict>",
  "passage_specificity": "<high|medium|low>",
  "verse_density_verdict": "<acceptable|borderline|too_thin — based on rubric 6>",
  "coaching_notes": [
    "<specific observation about what is wrong or right, referencing actual outline content>"
  ],
  "priority_fix": "<the single most important improvement the outliner should make next — must be different from the most recent coaching if history shows it was already given>",
  "theological_reviewer_consultation_needed": <true|false>,
  "theological_reviewer_question": "<if true, the specific question to put to the theological reviewer>",
  "proposed_code_changes": [
    {{
      "file_path": "<relative path to the source file that should change>",
      "objective": "<one-line description of the change>",
      "change_description": "<concrete description: what to change, where, and to what>",
      "rationale": "<why this is a structural code problem, not a training problem that repetition would fix>"
    }}
  ]
}}

Score adjustment guide: +5 to +15 if the outline is more passage-specific than the heuristics \
detected; -5 to -25 if generic scaffolding is present or verse density is too thin to sustain \
credible exposition.
Status should match the adjusted combined score: pass >= 85, revise >= 65, fail < 65.
When verse density is 'too_thin', cap status at 'revise' regardless of other criteria.
When task_feasibility_verdict is 'infeasible': set score_adjustment to 0 and status to 'revise' — \
the caller will override status to 'task_infeasible'. Do not penalize the outliner for an impossible task.
When task_feasibility_verdict is 'marginal': reduce any negative score_adjustment by half.

proposed_code_changes guide: Only populate if you observe a structural pattern that CANNOT be \
fixed by running more training cycles. If the problem is a training issue, leave the list empty.
"""


def _build_stall_context(recent_attempts: list[dict] | None, *, benchmark_label: str) -> str:
    """Summarise recent attempt history for this benchmark into a plain-English stall context string."""
    if not recent_attempts:
        return f"First attempt on this benchmark ({benchmark_label})."

    n = len(recent_attempts)
    sorted_attempts = sorted(recent_attempts, key=lambda a: str(a.get("created_at_utc") or ""))
    scores = [a["score"] for a in sorted_attempts if isinstance(a.get("score"), (int, float))]
    statuses = [str(a.get("status") or "") for a in sorted_attempts]

    pass_count = statuses.count("pass")
    revise_count = statuses.count("revise")
    fail_count = statuses.count("fail")
    score_str = ", ".join(str(int(s)) for s in scores[-5:]) if scores else "not recorded"

    trend = "unknown"
    if len(scores) >= 3:
        recent_avg = sum(scores[-3:]) / 3
        early_avg = sum(scores[:min(3, len(scores))]) / min(3, len(scores))
        if recent_avg > early_avg + 3:
            trend = "improving"
        elif recent_avg < early_avg - 3:
            trend = "declining"
        else:
            trend = "flat (no meaningful improvement)"

    lines = [
        f"Benchmark: {benchmark_label} — {n} prior attempt(s).",
        f"Results: {pass_count} pass, {revise_count} revise, {fail_count} fail.",
        f"Recent scores (up to last 5): {score_str}.",
        f"Score trend: {trend}.",
    ]
    if n >= 5 and pass_count == 0:
        lines.append(
            f"WARNING: {n} attempts with zero passes. If scores are flat or declining, "
            "a strategy change is required — continuing the same approach is not training."
        )
    return " ".join(lines)


def _outline_to_text(artifact: EditorialBuildArtifact) -> str:
    """Summarize an outline artifact into a readable text block for LLM review."""
    lines: list[str] = []
    for brief in artifact.day_briefs[:12]:  # cap at 12 days to stay within token limits
        lines.append(
            f"Day {brief.day_number} (Week {brief.week_number}): {brief.day_title}\n"
            f"  Focus: {brief.focus_clause}\n"
            f"  Burden: {brief.pastoral_burden}\n"
            f"  Lane: {brief.theological_lane}\n"
            f"  Application: {brief.application_lane}"
        )
    if artifact.week_plans:
        lines.append("\nWeek turns:")
        for plan in artifact.week_plans:
            lines.append(f"  Week {plan.week_number}: {plan.movement_summary}")
    return "\n".join(lines)


def _parse_trainer_response(raw: str) -> dict[str, Any]:
    """Extract and parse JSON from LLM trainer response, with fallback."""
    text = raw.strip()
    # Strip markdown code fences first (LLMs frequently wrap JSON in ```json ... ```)
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1)
    else:
        # Fall back to the outermost {...} block
        brace_match = re.search(r"\{.*\}", text, re.DOTALL)
        if brace_match:
            text = brace_match.group(0)
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass
    return {
        "score_adjustment": 0,
        "status": "revise",
        "passage_specificity": "low",
        "coaching_notes": [f"Trainer could not parse LLM response: {raw[:200]}"],
        "priority_fix": "Re-run trainer evaluation and inspect LLM output format.",
        "parse_failed": True,
    }


def _estimate_verse_count(artifact: EditorialBuildArtifact) -> int:
    """Estimate total verse count from day brief scripture references.

    Parses each day brief's scripture_reference (e.g. 'Ruth 1:6-10') and sums
    the verse spans. Falls back to counting day briefs if references can't be parsed.
    """
    import re as _re
    total = 0
    verse_re = _re.compile(r":(\d+)(?:\s*[-–]\s*(\d+))?$")
    for brief in artifact.day_briefs:
        ref = str(getattr(brief, "scripture_reference", "") or "")
        m = verse_re.search(ref)
        if m:
            start = int(m.group(1))
            end = int(m.group(2)) if m.group(2) else start
            total += max(1, end - start + 1)
        else:
            # No verse range found — count as 1 verse equivalent
            total += 1
    # If we got nothing useful, default to num_days (1 verse/day minimum)
    return total if total > 0 else len(artifact.day_briefs)


def build_llm_outliner_trainer_review(
    artifact: EditorialBuildArtifact,
    *,
    evaluation: dict[str, Any],
    topic: str = "",
    recent_attempts: list[dict] | None = None,
    llm: LLMClient | None = None,
) -> dict[str, Any]:
    """LLM trainer evaluates a deterministic outline artifact and provides expert coaching.

    Reads the outline produced by the deterministic outliner and checks whether burdens,
    theological lanes, and day progressions are genuinely passage-specific or generic.
    Also evaluates verse density and task feasibility — distinguishing between "the outliner
    failed" and "the task assignment itself was unreasonable."

    Args:
        artifact: The EditorialBuildArtifact produced by the deterministic outliner.
        evaluation: The dict returned by evaluate_outline_artifact() — provides deterministic score.
        topic: The passage topic label (e.g. "Habakkuk 1-3").
        recent_attempts: Prior attempts on this specific benchmark (passage + day count). Used to
            detect stalls and recommend strategy changes. Each dict should have keys: status, score,
            benchmark_name, created_at_utc.
        llm: Optional LLMClient override (uses CROSS provider by default).

    Returns:
        Dict with: score_adjustment (int), combined_score (int), status (str),
        task_feasibility_verdict (str), training_strategy_recommendation (str),
        passage_specificity (str), coaching_notes (list), priority_fix (str),
        verse_density_verdict (str), theological_reviewer_consultation_needed (bool).
        When status is 'task_infeasible', the outliner should NOT be penalised.
    """
    if llm is None:
        # Trainer deliberately uses the CROSS provider — the AI evaluating the outline
        # must be different from the AI that generated the burden/lane content.
        llm = get_cross_llm_client(worker="outliner")

    deterministic_score = int(evaluation.get("score") or 0)
    findings = list(evaluation.get("findings") or [])
    findings_text = "\n".join(f"- {f}" for f in findings) if findings else "No heuristic findings."

    num_days = len(artifact.day_briefs)
    verse_count = _estimate_verse_count(artifact)
    verse_density = round(verse_count / num_days, 2) if num_days > 0 else 0.0

    benchmark_label = f"{artifact.source_reference or topic}, {num_days}-day"
    stall_context = _build_stall_context(recent_attempts, benchmark_label=benchmark_label)

    prompt = _TRAINER_REVIEW_PROMPT.format(
        topic=topic or str(artifact.topic or ""),
        source_reference=str(artifact.source_reference or ""),
        findings_text=findings_text,
        num_days=num_days,
        verse_count=verse_count,
        verse_density=verse_density,
        stall_context=stall_context,
        outline_text=_outline_to_text(artifact),
    )

    raw = llm.generate(prompt, timeout=300)
    result = _parse_trainer_response(raw)
    if result.get("parse_failed"):
        result["score_adjustment"] = -36
        result["coaching_notes"] = [f"LLM trainer parse failed — evaluation error, not pass. Raw: {raw[:200]}"]


    # Task feasibility — if infeasible, do not penalise the outliner
    feasibility = str(result.get("task_feasibility_verdict") or "feasible").lower()
    if feasibility == "infeasible":
        # Neutralise any negative adjustment — the task was unreasonable
        adjustment = 0
    elif feasibility == "marginal":
        # Soften any negative adjustment by half
        raw_adjustment = int(result.get("score_adjustment") or 0)
        adjustment = raw_adjustment // 2 if raw_adjustment < 0 else raw_adjustment
    else:
        adjustment = int(result.get("score_adjustment") or 0)

    combined_score = max(0, min(100, deterministic_score + adjustment))

    # Enforce density cap: too_thin verse density cannot pass
    density_verdict = str(result.get("verse_density_verdict") or "acceptable")
    if density_verdict == "too_thin" and combined_score >= 85:
        combined_score = 84

    if feasibility == "infeasible":
        combined_status = "task_infeasible"
    elif combined_score >= 85:
        combined_status = "pass"
    elif combined_score >= 65:
        combined_status = "revise"
    else:
        combined_status = "fail"

    return {
        "deterministic_score": deterministic_score,
        "score_adjustment": adjustment,
        "combined_score": combined_score,
        "status": combined_status,
        "task_feasibility_verdict": feasibility,
        "task_infeasibility_reason": str(result.get("task_infeasibility_reason") or ""),
        "training_strategy_recommendation": str(
            result.get("training_strategy_recommendation") or "continue_drilling"
        ),
        "strategy_rationale": str(result.get("strategy_rationale") or ""),
        "passage_specificity": result.get("passage_specificity", "unknown"),
        "verse_density_verdict": density_verdict,
        "verse_count_estimated": verse_count,
        "verse_density": verse_density,
        "theological_reviewer_consultation_needed": bool(
            result.get("theological_reviewer_consultation_needed")
        ),
        "theological_reviewer_question": str(
            result.get("theological_reviewer_question") or ""
        ),
        "coaching_notes": result.get("coaching_notes") or [],
        "priority_fix": result.get("priority_fix") or "",
        "proposed_code_changes": result.get("proposed_code_changes") or [],
    }


# ── LLM Passage Selector ─────────────────────────────────────────────────────

_PASSAGE_SELECTION_PROMPT = """\
You are a seminary professor and expert outliner trainer. Your student (the outliner) is learning \
to structure multi-day Reformed evangelical devotionals across a broad scripture curriculum.

EXPERIMENT HISTORY (passages the outliner has already worked on):
{experiment_summary}

YOUR TASK:
Select {count} scripture passage + day-range combinations for the outliner's next training \
assignments. Draw on your full biblical knowledge — you do not need a list. Choose passages \
the outliner has NOT yet mastered and that represent a genuine curriculum progression.

CRITICAL RULE — FEASIBILITY BEFORE DIFFICULTY:
Difficulty is NOT a property of a passage alone. It is a property of the COMBINATION \
(passage, day_range). You MUST calculate verse density before assigning any label:

  verse_density = verse_count / day_range

HARD CONSTRAINTS:
- verse_density < 1.5  → INFEASIBLE. Do not recommend this combination under any label.
- verse_density 1.5-3  → feasible but thin; only valid for easy/moderate if passage has \
  sustained theological depth throughout.
- verse_density > 3    → comfortably feasible.

EXAMPLE: Ruth 1 has 22 verses.
  Ruth 1 at 6 days  → 3.7 verses/day → feasible, easy
  Ruth 1 at 14 days → 1.6 verses/day → barely feasible, only if every verse has exposition depth
  Ruth 1 at 30 days → 0.7 verses/day → INFEASIBLE. Never recommend this combination.

SELECTION CRITERIA:
1. Do not re-assign passages where the outliner already has multiple passes — it needs breadth.
2. Include a range of scripture families: OT narrative, OT poetry/wisdom, OT prophetic, NT \
gospel, NT epistle, NT apocalyptic. A Reformed student must know the whole Bible.
3. Longer day ranges (21/30) require longer passages (full epistles, multi-chapter narratives). \
Short chapters must only be paired with short day ranges.
4. Difficulty should step from the outliner's current demonstrated capability.
5. Each outline day will require 500+ words of exposition downstream. Only recommend passages \
with genuine theological depth throughout every section of the range.

Respond with ONLY valid JSON, no explanation:
{{
  "recommended_passages": [
    {{
      "reference": "<book chapter-range, e.g. Philippians 1-4>",
      "slug": "<kebab-case, e.g. philippians-1-4>",
      "verse_count": <integer>,
      "suggested_day_range": <7|14|21|30>,
      "verse_density": <verse_count / suggested_day_range, rounded to 1 decimal>,
      "difficulty": "<easy|moderate|challenging — relative to this passage AT this day range>",
      "rationale": "<one sentence: why this passage+range now, what it trains>"
    }}
  ]
}}
"""


def _summarise_experiments(experiment_history: list[dict[str, Any]]) -> str:
    """Condense experiment history to a compact per-passage summary for the selection prompt."""
    by_passage: dict[str, dict[str, Any]] = {}
    for exp in experiment_history:
        slug = str(exp.get("passage_slug") or exp.get("benchmark_reference") or "")
        ref = str(exp.get("passage") or exp.get("scripture_reference") or slug)
        if not slug:
            continue
        if slug not in by_passage:
            by_passage[slug] = {"reference": ref, "pass": 0, "fail": 0, "revise": 0}
        status = str(exp.get("status") or "").lower()
        if status == "pass":
            by_passage[slug]["pass"] += 1
        elif status in ("fail", "task_infeasible"):
            by_passage[slug]["fail"] += 1
        elif status == "revise":
            by_passage[slug]["revise"] += 1
    if not by_passage:
        return (
            "No experiments recorded yet. "
            "This is the bootstrap phase. "
            "Select fresh beginner-friendly passages (short clear narratives with strong movement) "
            "from your biblical knowledge for an absolute novice outliner."
        )
    lines = []
    for slug, counts in sorted(by_passage.items(), key=lambda kv: -kv[1]["pass"]):
        ref = counts["reference"]
        lines.append(
            f"- {ref}: {counts['pass']} pass / {counts['revise']} revise / {counts['fail']} fail"
        )
    return "\n".join(lines)


def build_llm_passage_selection(
    *,
    experiment_history: list[dict[str, Any]],
    count: int = 5,
    client: LLMClient | None = None,
) -> list[dict[str, Any]]:
    """Ask the trainer LLM to select the next benchmark passages from its biblical knowledge.

    Returns a list of passage dicts with keys: reference, slug, difficulty,
    suggested_day_range, rationale. Falls back to [] on any error so callers
    can degrade gracefully to cached recommendations.
    """
    if client is None:
        client = get_cross_llm_client(worker="outliner")
    experiment_summary = _summarise_experiments(experiment_history)
    prompt = _PASSAGE_SELECTION_PROMPT.format(
        experiment_summary=experiment_summary,
        count=count,
    )
    try:
        raw = client.generate(prompt, timeout=300)
        raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
        raw = re.sub(r"\s*```$", "", raw.strip())
        result = json.loads(raw)
        passages = result.get("recommended_passages")
        if not isinstance(passages, list):
            return []
        valid = []
        for p in passages:
            if not isinstance(p, dict) or not p.get("reference"):
                continue
            # Enforce feasibility: reject combinations where the LLM's own math
            # shows < 1.5 verses/day, or where we can compute it ourselves.
            verse_count = p.get("verse_count")
            day_range = p.get("suggested_day_range")
            if verse_count and day_range:
                density = float(verse_count) / float(day_range)
                if density < 1.5:
                    print(f"[build_llm_passage_selection] dropped {p.get('reference')!r}: density {density:.2f} < 1.5")
                    continue  # infeasible
            valid.append(p)
        return valid
    except Exception as exc:
        print(f"[build_llm_passage_selection] LLM call failed: {exc}")
    return []


# ── Comparison baseline (not the training path) ──────────────────────────────

def _resource_summary(bundle: PassageResourceBundle | None) -> str:
    if not bundle:
        return "No commentary resources provided."
    lines: list[str] = []
    for resource in (bundle.outliner_resources + bundle.shared_resources)[:6]:
        title = str(resource.source_title or "Unknown")
        excerpt = str(resource.excerpt_text or resource.notes or "").strip()
        if excerpt and len(excerpt) > 20:
            lines.append(f"- {title}: {excerpt[:300]}")
        else:
            lines.append(f"- {title}: (no excerpt available)")
    return "\n".join(lines) if lines else "No commentary excerpts available."


def _build_day_brief_prompt(
    *,
    day_number: int,
    scripture_reference: str,
    study_window_reference: str,
    key_verse_reference: str,
    scripture_text: str,
    genre: str,
    resource_summary: str,
    topic: str,
) -> str:
    return f"""You are an expert biblical outliner preparing a single day's outline brief for a devotional book.

PASSAGE ASSIGNMENT
Day: {day_number}
Topic: {topic}
Scripture reference (this day's segment): {scripture_reference}
Study window (broader context): {study_window_reference}
Key verse focus: {key_verse_reference}
Literary genre: {genre}

SCRIPTURE TEXT
{scripture_text}

AVAILABLE COMMENTARY RESOURCES
{resource_summary}

YOUR TASK
Generate a structured day brief. Each field must be grounded in the SPECIFIC text above.

Rules:
1. pastoral_burden: Must name what THIS specific text is doing. Not a genre template.
2. theological_lane: Must identify the specific doctrinal movement of THIS passage.
3. application_lane: Must name what faithful response looks like given THIS text.
4. focus_clause: The central action or claim of this day's text — specific to this passage.
5. day_title: A distinct title that could not be reused on any other passage.

Respond with ONLY valid JSON, no explanation:
{{
  "focus_clause": "<central action or claim, 5-15 words>",
  "pastoral_burden": "<what this text asks the reader to receive, 8-20 words>",
  "theological_lane": "<the specific doctrinal truth this passage anchors, 8-20 words>",
  "application_lane": "<faithful response given this text, 8-20 words>",
  "day_title": "<a distinct title for this day, 4-10 words>",
  "scene_summary": "<one sentence describing what the text is doing literarily>",
  "forbidden_drifts": ["<one or two specific wrong turns this text tempts>"]
}}"""


def _parse_llm_brief(
    response: str,
    *,
    fallback_focus: str,
    fallback_terms: list[str],
    genre: str,
    scripture_reference: str,
) -> dict[str, Any]:
    text = response.strip()
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        text = match.group(1)
    elif not text.startswith("{"):
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            text = match.group(0)

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        from src.autoresearch.reasoning_outliner_core import (
            application_lane,
            pastoral_burden,
            theological_lane,
        )
        data = {
            "focus_clause": fallback_focus,
            "pastoral_burden": pastoral_burden(genre, scripture_reference),
            "theological_lane": theological_lane(genre, scripture_reference),
            "application_lane": application_lane(genre, scripture_reference),
            "day_title": f"Day at {scripture_reference}",
            "scene_summary": f"The text of {scripture_reference} unfolds.",
            "forbidden_drifts": forbidden_drifts(genre),
        }

    return {
        "focus_clause": str(data.get("focus_clause") or fallback_focus),
        "pastoral_burden": str(data.get("pastoral_burden") or ""),
        "theological_lane": str(data.get("theological_lane") or ""),
        "application_lane": str(data.get("application_lane") or ""),
        "day_title": str(data.get("day_title") or f"Day at {scripture_reference}"),
        "scene_summary": str(data.get("scene_summary") or ""),
        "forbidden_drifts": [str(item) for item in (data.get("forbidden_drifts") or [])],
    }


def build_llm_day_brief(
    *,
    day_number: int,
    week_number: int,
    scripture_reference: str,
    study_window_reference: str,
    key_verse_reference: str,
    scripture_text: str,
    topic: str,
    passage_resources: PassageResourceBundle | None = None,
    llm: LLMClient | None = None,
) -> EditorialDayBriefRecord:
    """Generate a single day brief via LLM. Comparison baseline — not the training path."""
    if llm is None:
        llm = get_llm_client(worker="outliner")

    genre = detect_genre(scripture_reference, scripture_text)
    fallback_focus = focus_clause(genre, scripture_reference)
    fallback_terms = key_terms(scripture_text)
    resource_text = _resource_summary(passage_resources)

    prompt = _build_day_brief_prompt(
        day_number=day_number,
        scripture_reference=scripture_reference,
        study_window_reference=study_window_reference,
        key_verse_reference=key_verse_reference,
        scripture_text=scripture_text[:1500],
        genre=genre,
        resource_summary=resource_text,
        topic=topic,
    )

    response = llm.generate(prompt, timeout=300)
    parsed = _parse_llm_brief(
        response,
        fallback_focus=fallback_focus,
        fallback_terms=fallback_terms,
        genre=genre,
        scripture_reference=scripture_reference,
    )

    return EditorialDayBriefRecord(
        day_number=day_number,
        week_number=week_number,
        scripture_reference=scripture_reference,
        study_window_reference=study_window_reference,
        key_verse_reference=key_verse_reference,
        day_title=parsed["day_title"],
        focus_clause=parsed["focus_clause"],
        pastoral_burden=parsed["pastoral_burden"],
        genre=genre,
        scene_summary=parsed["scene_summary"],
        theological_lane=parsed["theological_lane"],
        application_lane=parsed["application_lane"],
        forbidden_drifts=parsed["forbidden_drifts"],
        key_terms=fallback_terms,
    )


def build_llm_week_plans(day_briefs: list[EditorialDayBriefRecord]) -> list[EditorialWeekPlan]:
    """Build week plans from day briefs. Used by comparison baseline."""
    by_week: dict[int, list[EditorialDayBriefRecord]] = {}
    for brief in day_briefs:
        by_week.setdefault(brief.week_number, []).append(brief)
    plans: list[EditorialWeekPlan] = []
    for week_number in sorted(by_week):
        items = sorted(by_week[week_number], key=lambda item: item.day_number)
        first = items[0]
        last = items[-1]
        plans.append(
            EditorialWeekPlan(
                week_number=week_number,
                title=f"Week {week_number}: {first.day_title}",
                days=[item.day_number for item in items],
                movement_summary=(
                    f"Opens with {first.focus_clause.lower()} and moves toward {last.focus_clause.lower()}."
                ),
            )
        )
    return plans


def build_llm_editorial_artifact(
    *,
    topic: str,
    source_reference: str,
    num_days: int,
    num_weeks: int,
    day_inputs: list[dict[str, str]],
    passage_resources: PassageResourceBundle | None,
    llm: LLMClient | None = None,
) -> EditorialBuildArtifact:
    """Build a full outline artifact via LLM. Comparison baseline — not the training path.

    Use this to generate a reference outline for side-by-side comparison with the
    deterministic outliner's output. Not invoked in normal training cycles.
    """
    if llm is None:
        llm = get_llm_client(worker="outliner")

    day_plan: list[EditorialDayPlanRow] = []
    day_briefs: list[EditorialDayBriefRecord] = []

    for idx, row in enumerate(day_inputs, start=1):
        week_number = reasoning_week_number(idx, num_days=num_days, num_weeks=num_weeks)
        scripture_reference = str(row["scripture_reference"]).strip()
        study_window_reference = str(row["study_window_reference"]).strip()
        key_verse_reference = str(row["key_verse_reference"]).strip()
        scripture_text = str(row["scripture_text"]).strip()

        day_plan.append(
            EditorialDayPlanRow(
                day_number=idx,
                week_number=week_number,
                topic=topic,
                scripture_reference=scripture_reference,
                study_window_reference=study_window_reference,
            )
        )
        day_briefs.append(
            build_llm_day_brief(
                day_number=idx,
                week_number=week_number,
                scripture_reference=scripture_reference,
                study_window_reference=study_window_reference,
                key_verse_reference=key_verse_reference,
                scripture_text=scripture_text,
                topic=topic,
                passage_resources=passage_resources,
                llm=llm,
            )
        )

    return EditorialBuildArtifact(
        topic=topic,
        num_days=num_days,
        source_reference=source_reference,
        week_count=max((item.week_number for item in day_briefs), default=0),
        passage_resources=passage_resources,
        day_plan=day_plan,
        day_briefs=day_briefs,
        week_plans=build_llm_week_plans(day_briefs),
    )
