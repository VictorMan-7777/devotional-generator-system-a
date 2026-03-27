"""cross_evaluator.py — Independent training system evaluation using the cross AI provider.

Principle: the AI that evaluates training quality must be different from the AI that generated
the training content. If the outliner generator uses Claude, this evaluator uses OpenAI, and
vice versa. This prevents a model from validating its own output.

The cross-evaluator reads three things:
1. Recent training cycle outputs (coaching notes, scores, proposals)
2. Key source code files (worker implementations, trainer prompts)
3. Training agent design (trainer profiles, rubrics, selection rules)

It produces an independent assessment of: whether training is making progress, whether the
trainer rubrics are well-designed, and whether the code matches the design intent.

Provider: always get_cross_llm_client() — the opposite of DEVG_LLM_PROVIDER.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_SCAN_LIMIT = 5  # recent cycles per worker to include in context

_CODE_FILES_IN_SCOPE = [
    "src/autoresearch/reasoning_outliner_core.py",
    "src/autoresearch/llm_outliner_core.py",
    "src/autoresearch/exposition_training_agent.py",
    "src/autoresearch/llm_exposition_core.py",
    "src/generation/real_section_generator.py",
]

_MAX_CODE_CHARS = 800   # per file — keep prompt manageable
_MAX_CYCLE_CHARS = 600  # per cycle JSON summary

_CROSS_EVAL_PROMPT = """\
You are an independent AI system conducting a quality audit of a devotional content \
training pipeline. This evaluation was commissioned specifically because you use a \
DIFFERENT AI architecture than the agents whose work you are reviewing. Your independence \
is the point — do not defer to prior trainer judgments.

You will review three things: (1) recent training cycle results, (2) key source code, \
and (3) trainer agent design. Then give an honest assessment.

══════════════════════════════════════════════════════════
SECTION 1 — RECENT TRAINING CYCLE RESULTS
══════════════════════════════════════════════════════════
{cycle_summaries}

══════════════════════════════════════════════════════════
SECTION 2 — KEY SOURCE CODE (excerpts)
══════════════════════════════════════════════════════════
{code_excerpts}

══════════════════════════════════════════════════════════
SECTION 3 — TRAINER AGENT DESIGN (profiles and rubrics)
══════════════════════════════════════════════════════════
{trainer_profiles}

══════════════════════════════════════════════════════════
YOUR EVALUATION TASK
══════════════════════════════════════════════════════════

Assess the following independently:

A. TRAINING PROGRESS: Is the training system making genuine progress, or cycling in place? \
What evidence supports your view?

B. RUBRIC QUALITY: Are the trainer rubrics (what counts as pass/fail) well-designed? \
Are they asking for the right things? Are there gaps?

C. CODE–DESIGN ALIGNMENT: Does the worker code match the trainer's design intent? \
Where do they diverge?

D. STRUCTURAL RISKS: What risks do you see that the existing trainers may be too close \
to notice? (e.g., training on wrong signal, evaluation bias, scope creep)

E. PRIORITY RECOMMENDATION: What single change would most improve training quality?

Respond ONLY with valid JSON. No preamble or explanation outside the JSON.

{{
  "training_progress": {{
    "verdict": "<progressing|stalled|regressing>",
    "evidence": "<2-3 sentences citing specific observations from the cycle data>"
  }},
  "rubric_quality": {{
    "verdict": "<strong|adequate|weak>",
    "gaps": ["<specific gap or improvement>"]
  }},
  "code_design_alignment": {{
    "verdict": "<aligned|partial|misaligned>",
    "divergences": ["<specific divergence between code and design intent>"]
  }},
  "structural_risks": [
    "<specific risk the existing trainers may be missing>"
  ],
  "priority_recommendation": "<single most impactful change, with specific file/function if applicable>",
  "evaluator_provider": "<which AI system produced this evaluation>"
}}
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _summarise_cycle(path: Path) -> str:
    """Extract a compact summary from one cycle JSON file."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return f"[unreadable: {path.name}]"

    lines = [f"File: {path.name}"]
    lines.append(f"Status: {data.get('status', '?')}")

    # Outliner cycle
    for result in (data.get("results") or [])[:3]:
        ia = result.get("initial_attempt") or {}
        tr = ia.get("trainer_review") or {}
        passage = (result.get("assignment") or {}).get("passage", "?")
        fe = result.get("final_evaluation") or {}
        lines.append(
            f"  Passage={passage} det_score={fe.get('score')} "
            f"llm_score={tr.get('combined_score')} llm_status={tr.get('status')}"
        )
        notes = (tr.get("coaching_notes") or [])[:1]
        if notes:
            lines.append(f"  LLM note: {notes[0][:120]}")

    # Exposition cycle benchmarks
    for key in ("fresh_benchmark", "llm_benchmark"):
        bm = data.get(key) or {}
        ev = bm.get("evaluation") or {}
        if ev:
            lines.append(
                f"  {key}: score={ev.get('score')} grounded={ev.get('passage_grounded')} "
                f"phrases={ev.get('generic_phrase_count')}"
            )
            pf = ev.get("priority_fix", "")
            if pf:
                lines.append(f"  priority_fix: {pf[:120]}")

    return "\n".join(lines)[:_MAX_CYCLE_CHARS]


def _collect_cycle_summaries(repo_root: Path) -> str:
    output_dir = repo_root / "docs" / "system" / "outputs"
    patterns = [
        ("outliner", "*__devg__outliner-training-cycle.json"),
        ("exposition", "*__devg__exposition-training-cycle.json"),
    ]
    sections: list[str] = []
    for label, pattern in patterns:
        files = sorted(output_dir.glob(pattern), reverse=True)[:_SCAN_LIMIT]
        if not files:
            continue
        sections.append(f"--- {label.upper()} (last {len(files)} cycles) ---")
        for f in files:
            sections.append(_summarise_cycle(f))
    return "\n\n".join(sections) if sections else "No cycle data found."


def _collect_code_excerpts(repo_root: Path) -> str:
    parts: list[str] = []
    for rel_path in _CODE_FILES_IN_SCOPE:
        full = repo_root / rel_path
        if not full.exists():
            continue
        text = full.read_text(encoding="utf-8")
        # Take the first _MAX_CODE_CHARS characters as a representative excerpt
        excerpt = text[:_MAX_CODE_CHARS].strip()
        parts.append(f"--- {rel_path} (first {_MAX_CODE_CHARS} chars) ---\n{excerpt}")
    return "\n\n".join(parts) if parts else "No code files found."


def _collect_trainer_profiles(repo_root: Path) -> str:
    """Extract trainer profiles from the most recent cycle files."""
    output_dir = repo_root / "docs" / "system" / "outputs"
    profiles: dict[str, str] = {}

    for pattern in ["*__devg__outliner-training-cycle.json", "*__devg__exposition-training-cycle.json"]:
        files = sorted(output_dir.glob(pattern), reverse=True)[:1]
        for f in files:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                tp = data.get("trainer_profile") or {}
                if tp:
                    role = str(tp.get("role", f.stem))
                    mission = str(tp.get("mission", ""))[:300]
                    rubric = tp.get("review_rubric") or []
                    profiles[role] = f"Role: {role}\nMission: {mission}\nRubric:\n" + "\n".join(
                        f"  - {r}" for r in rubric[:4]
                    )
            except Exception:
                continue

    return "\n\n".join(profiles.values()) if profiles else "No trainer profiles found."


def build_cross_evaluation(repo_root: Path) -> dict[str, Any]:
    """Run an independent cross-AI evaluation of the training system.

    The evaluator AI is the opposite provider from the primary training AI.
    Returns the evaluation dict ready for JSON serialisation.
    """
    from src.llm.router import get_cross_llm_client

    llm = get_cross_llm_client(worker="outliner")

    cycle_summaries = _collect_cycle_summaries(repo_root)
    code_excerpts = _collect_code_excerpts(repo_root)
    trainer_profiles = _collect_trainer_profiles(repo_root)

    prompt = _CROSS_EVAL_PROMPT.format(
        cycle_summaries=cycle_summaries,
        code_excerpts=code_excerpts,
        trainer_profiles=trainer_profiles,
    )

    try:
        raw = llm.generate(prompt)
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            result = json.loads(match.group(0))
        else:
            result = {"raw_response": raw[:500], "parse_error": "No JSON found in response"}
    except Exception as exc:
        result = {"error": str(exc)[:200]}

    return {
        "generated_at_utc": _utc_now(),
        "evaluator_note": (
            "This evaluation was produced by the cross-AI provider — the opposite AI system "
            "from the one generating training content. It has not seen prior trainer judgments "
            "and is not optimising for agreement with existing assessments."
        ),
        "evaluation": result,
    }
