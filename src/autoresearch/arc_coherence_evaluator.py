"""arc_coherence_evaluator.py — Stage 2 arc coherence evaluation for Hebrews 5-week argument.

Implements the machine-readable rubric specified by the Outliner Trainer (2026-03-25)
against Hebrews Baseline Section 4 criteria.

Runs AFTER per-week WeekOutline validation (Stage 1). Takes all WeekOutlines together
and evaluates cross-week arc coherence. Per-week validation catches intra-week failures;
this module catches cross-week arc failures.

Semantic functions (`semantic_contains_any`, `semantic_equivalent`, etc.) are implemented
as keyword-based heuristics — adequate for the token-level checks the Trainer specified.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from src.autoresearch.argumentative_outliner import ArgumentativeDay, WeekOutline


# ── Generic antecedent detection (Outliner Trainer spec) ──

_GENERIC_ANTECEDENT_PATTERNS = [
    "building on yesterday",
    "continuing our study",
    "as we have seen",
    "following from last time",
    "in our ongoing look at",
    "today we turn to",
    "next we consider",
    "in the previous",
    "picking up where",
]


def _is_generic(text: str) -> bool:
    """Return True if the logical_antecedent is generic/non-specific."""
    text_lower = text.lower().strip()
    if len(text_lower) < 20:
        return True
    for pattern in _GENERIC_ANTECEDENT_PATTERNS:
        if pattern in text_lower:
            return True
    return False


def _contains_any(text: str, tokens: list[str]) -> bool:
    """Case-insensitive substring match for any token."""
    t = text.lower()
    return any(tok.lower() in t for tok in tokens)


def _word_overlap(a: str, b: str) -> float:
    """Jaccard word overlap ratio, stopwords removed."""
    stopwords = {"the", "a", "an", "and", "or", "of", "to", "in", "is", "we", "this",
                 "that", "it", "for", "on", "with", "from", "by", "as", "be", "are"}
    wa = set(a.lower().split()) - stopwords
    wb = set(b.lower().split()) - stopwords
    if not wa and not wb:
        return 1.0
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def _is_equivalent(a: str, b: str) -> bool:
    """True if two strings are semantically equivalent (high overlap)."""
    return _word_overlap(a, b) > 0.60


# ── Warning week ground truth ──

# Only W3 and W5 contain Hebrews warning passages (SF-4 check)
REQUIRED_WARNING_WEEKS = {
    3: "mid_week",    # Heb 5:11-6:12
    5: "end_of_week", # Heb 10:26-31
}


# ── Result types ──

@dataclass
class CheckpointResult:
    checkpoint_id: str
    passed: bool
    verdict_contribution: str   # "fail" | "revise" | "info"
    description: str
    revision_target: str = ""
    cascade_targets: list[str] = field(default_factory=list)


@dataclass
class ArcCoherenceReport:
    weeks_evaluated: int
    checkpoints: list[CheckpointResult] = field(default_factory=list)
    sf_violations: list[str] = field(default_factory=list)
    sd_flags: list[str] = field(default_factory=list)
    verdict: str = "pass"  # "pass" | "revise" | "fail"
    summary: str = ""

    def add(self, result: CheckpointResult) -> None:
        self.checkpoints.append(result)
        if not result.passed:
            if result.verdict_contribution == "fail":
                self.verdict = "fail"
                if result.checkpoint_id.startswith("SF"):
                    self.sf_violations.append(result.checkpoint_id)
            elif result.verdict_contribution == "revise" and self.verdict != "fail":
                self.verdict = "revise"
                if result.checkpoint_id.startswith("SD"):
                    self.sd_flags.append(result.checkpoint_id)


# ── Public entry point ──

def evaluate_arc_coherence(weeks: list[WeekOutline]) -> ArcCoherenceReport:
    """Evaluate 5-week Hebrews arc coherence per Outliner Trainer spec (2026-03-25).

    Checks: 5 weekly arc checkpoints, SF-1 through SF-6, SD-1 through SD-3.
    Verdict: pass (all clear) / revise (SD flags only) / fail (any SF violation).
    """
    n = len(weeks)
    report = ArcCoherenceReport(weeks_evaluated=n)

    # ── Per-week arc checkpoints ──
    if n >= 1:
        _check_week1(weeks[0], report)
    if n >= 2:
        _check_week2(weeks[0], weeks[1], report)
    if n >= 3:
        _check_week3(weeks[1], weeks[2], report)
    if n >= 4:
        _check_week4(weeks[2], weeks[3], report)
    if n >= 5:
        _check_week5(weeks[3], weeks[4], report)

    # ── Cross-week bridge chain (W2-W5 opening must follow prior bridge) ──
    for i in range(1, n):
        bridge = weeks[i - 1].week_to_week_bridge or ""
        opening = weeks[i].week_opening_tension
        # Approximate semantic_is_upstream: bridge and opening share key vocabulary
        bridge_ok = (
            bool(bridge)
            and _word_overlap(bridge, opening) > 0.10  # at minimum some shared premise
        )
        report.add(CheckpointResult(
            checkpoint_id=f"W{i}-to-W{i+1}-bridge",
            passed=bridge_ok,
            verdict_contribution="revise",
            description=(
                f"W{i} week_to_week_bridge does not feed W{i+1} week_opening_tension"
                if not bridge_ok else f"W{i}→W{i+1} bridge chain present"
            ),
            revision_target=f"weeks[{i-1}].week_to_week_bridge",
        ))

    # ── SF-1: interchangeable days ──
    for i, week in enumerate(weeks):
        week_num = i + 1
        days = week.days
        arg_days = [(idx, d) for idx, d in enumerate(days) if d.day_subtype == "argument_step"]
        sf1_violations: list[str] = []

        # Check 1: semantically equivalent arg_advance_claim between any two arg_step days
        for a in range(len(arg_days)):
            for b in range(a + 1, len(arg_days)):
                idx_a, day_a = arg_days[a]
                idx_b, day_b = arg_days[b]
                if _is_equivalent(day_a.arg_advance_claim, day_b.arg_advance_claim):
                    sf1_violations.append(
                        f"days[{idx_a}] and days[{idx_b}] have equivalent arg_advance_claim"
                    )

        # Check 2: logical_antecedent of each arg_step day must reference prior day's claim
        # Skip pairs separated by a warning_beat — W3_C4 handles those separately
        for k in range(1, len(arg_days)):
            prev_idx, prev_day = arg_days[k - 1]
            curr_idx, curr_day = arg_days[k]
            # If any day between prev and curr is a warning_beat, skip — warning disrupts direct chain
            between = [d for d in days[prev_idx + 1:curr_idx] if d.day_subtype == "warning_beat"]
            if between:
                continue
            prev_words = set(prev_day.arg_advance_claim.lower().split())
            curr_ante_words = set(curr_day.logical_antecedent.lower().split())
            stopwords = {"the", "a", "an", "and", "or", "of", "to", "in", "is", "we"}
            shared = (prev_words - stopwords) & (curr_ante_words - stopwords)
            if len(shared) < 1:  # antecedent references nothing from prior day
                sf1_violations.append(
                    f"days[{curr_idx}].logical_antecedent does not reference "
                    f"days[{prev_idx}].arg_advance_claim — days logically detached"
                )

        passed = len(sf1_violations) == 0
        report.add(CheckpointResult(
            checkpoint_id="SF-1",
            passed=passed,
            verdict_contribution="fail",
            description=(
                f"W{week_num} SF-1: {'; '.join(sf1_violations)}"
                if not passed else f"W{week_num}: all days distinct and chained"
            ),
            revision_target="arg_advance_claim and logical_antecedent for flagged days",
        ))

    # ── SF-3: stakes_level not strictly increasing ──
    stakes = [w.stakes_level for w in weeks]
    sf3_violations = [
        f"W{i+1}({stakes[i]}) ≤ W{i}({stakes[i-1]})"
        for i in range(1, n)
        if stakes[i] <= stakes[i - 1]
    ]
    report.add(CheckpointResult(
        checkpoint_id="SF-3",
        passed=len(sf3_violations) == 0,
        verdict_contribution="fail",
        description=(
            f"SF-3: stakes_level not strictly increasing — {', '.join(sf3_violations)}"
            if sf3_violations else f"SF-3: stakes_level strictly increasing {stakes}"
        ),
        revision_target="stakes_level on affected weeks",
    ))

    # ── SF-4: warning passage absent from its required week ──
    for week_num, required_position in REQUIRED_WARNING_WEEKS.items():
        if week_num > n:
            continue
        week = weeks[week_num - 1]
        warning_days = [d for d in week.days if d.warning_slot]
        if not warning_days:
            report.add(CheckpointResult(
                checkpoint_id="SF-4",
                passed=False,
                verdict_contribution="fail",
                description=f"SF-4: W{week_num} has no warning_slot day — Hebrews warning passage absent from its week",
                revision_target=f"weeks[{week_num-1}].days — add warning_beat day with warning_slot=true",
            ))
        else:
            position_ok = all(d.warning_position == required_position for d in warning_days)
            report.add(CheckpointResult(
                checkpoint_id=f"SF-4-W{week_num}-position",
                passed=position_ok,
                verdict_contribution="fail",
                description=(
                    f"SF-4: W{week_num} warning days have wrong warning_position "
                    f"(expected '{required_position}', got {[d.warning_position for d in warning_days]})"
                    if not position_ok else f"SF-4: W{week_num} warning position correct"
                ),
                revision_target=f"weeks[{week_num-1}].days[N].warning_position",
            ))

    # ── SF-5: multiple transitions with missing/generic antecedent ──
    for i, week in enumerate(weeks):
        week_num = i + 1
        short = [
            j + 2 for j, d in enumerate(week.days[1:])
            if not d.logical_antecedent.strip() or _is_generic(d.logical_antecedent)
        ]
        report.add(CheckpointResult(
            checkpoint_id="SF-5",
            passed=len(short) <= 1,
            verdict_contribution="fail",
            description=(
                f"W{week_num} SF-5: generic/empty antecedent on days {short} — "
                "more than 1 transition fails writability test"
                if len(short) > 1 else f"W{week_num}: antecedents writable"
            ),
            revision_target="logical_antecedent for flagged days",
        ))

    # ── SD-1: flat arc (overall spread < 2, or flat stretches) ──
    if n >= 2:
        sd1_reasons: list[str] = []
        if stakes[-1] - stakes[0] < 2:
            sd1_reasons.append(
                f"Total stakes escalation W1({stakes[0]})→W{n}({stakes[-1]}) < 2 — arc too flat"
            )
        for i in range(1, n):
            if stakes[i] == stakes[i - 1]:
                sd1_reasons.append(
                    f"W{i} and W{i+1} both have stakes_level {stakes[i]} — flat stretch"
                )
        report.add(CheckpointResult(
            checkpoint_id="SD-1",
            passed=len(sd1_reasons) == 0,
            verdict_contribution="revise",
            description="; ".join(sd1_reasons) if sd1_reasons else "SD-1: stakes escalation adequate",
            revision_target="stakes_level",
        ))

    # ── SD-2: warning days use application language ──
    _APPLICATION_PATTERNS = [
        "applies to us", "in our lives", "what does this mean for",
        "practically speaking", "application", "how should we respond",
        "action step", "for us today",
    ]
    sd2_violations: list[str] = []
    for i, week in enumerate(weeks):
        week_num = i + 1
        warning_days_enum = [(idx, d) for idx, d in enumerate(week.days) if d.day_subtype == "warning_beat"]
        for day_idx, wday in warning_days_enum:
            if any(pat in wday.arg_advance_claim.lower() for pat in _APPLICATION_PATTERNS):
                sd2_violations.append(
                    f"W{week_num}.days[{day_idx}].arg_advance_claim uses application language"
                )
            # Check: next day's antecedent references the warning content
            if day_idx + 1 < len(week.days):
                next_day = week.days[day_idx + 1]
                shared = set(wday.arg_advance_claim.lower().split()) & set(next_day.logical_antecedent.lower().split())
                stopwords = {"the", "a", "an", "and", "or", "of", "to", "in", "is", "we"}
                if len(shared - stopwords) < 1:
                    sd2_violations.append(
                        f"W{week_num}.days[{day_idx+1}].logical_antecedent does not reference "
                        f"warning content — warning treated as disconnected insert"
                    )
    report.add(CheckpointResult(
        checkpoint_id="SD-2",
        passed=len(sd2_violations) == 0,
        verdict_contribution="revise",
        description="; ".join(sd2_violations) if sd2_violations else "SD-2: warning days integrated correctly",
        revision_target="arg_advance_claim and logical_antecedent on and after warning days",
    ))

    # ── SD-3: forward references to Hebrews 11 in W1-W4 ──
    _HOF_PATTERNS = [
        "hall of faith", "hebrews 11", "chapter 11", "cloud of witnesses",
        "11:1", "we will see in hebrews", "as we'll see next week",
        "abel", "enoch", "noah's faith in chapter", "abraham's faith in chapter",
    ]
    sd3_violations: list[str] = []
    for i in range(min(4, n)):
        week_num = i + 1
        week = weeks[i]
        for d_idx, day in enumerate(week.days):
            for field_name, text in [("arg_advance_claim", day.arg_advance_claim),
                                      ("logical_antecedent", day.logical_antecedent)]:
                if any(p in text.lower() for p in _HOF_PATTERNS):
                    sd3_violations.append(
                        f"W{week_num}.days[{d_idx}].{field_name} references Heb 11 content"
                    )
        if week.week_to_week_bridge:
            if any(p in week.week_to_week_bridge.lower() for p in _HOF_PATTERNS):
                sd3_violations.append(f"W{week_num}.week_to_week_bridge references Heb 11")
    report.add(CheckpointResult(
        checkpoint_id="SD-3",
        passed=len(sd3_violations) == 0,
        verdict_contribution="revise",
        description="; ".join(sd3_violations) if sd3_violations else "SD-3: no premature Heb 11 references",
        revision_target="arg_advance_claim, logical_antecedent, week_to_week_bridge",
    ))

    # Build summary
    fails = [c.checkpoint_id for c in report.checkpoints if not c.passed and c.verdict_contribution == "fail"]
    revises = [c.checkpoint_id for c in report.checkpoints if not c.passed and c.verdict_contribution == "revise"]
    report.summary = (
        f"Arc coherence verdict: {report.verdict.upper()}. "
        + (f"Fails: {', '.join(fails)}. " if fails else "")
        + (f"Flags: {', '.join(revises)}. " if revises else "")
        + f"({n} weeks evaluated)"
    )
    return report


# ── Per-week checkpoint functions ──

def _check_week1(w1: WeekOutline, report: ArcCoherenceReport) -> None:
    """W1 (Chs 1-2): Exaltation of Son → descends into incarnation necessity.
    Day 5 must land on incarnation/identification, not restate opening glory."""
    days = w1.days

    # W1_C2: closing must not be equivalent to opening (arc movement)
    c2_ok = not _is_equivalent(w1.week_closing_location, w1.week_opening_tension)
    report.add(CheckpointResult(
        checkpoint_id="W1_C2",
        passed=c2_ok,
        verdict_contribution="fail",
        description="W1: week_closing_location semantically equivalent to week_opening_tension — no arc advance" if not c2_ok else "W1: closing advances from opening",
        revision_target="week_closing_location",
    ))

    # W1_C3: closing must reference incarnation/identification cluster
    _INCARNATION = ["incarnat", "identif", "human", "necessity", "suffered", "partake",
                    "flesh", "brother", "2:14", "2:17", "2:18", "sympathize", "had to"]
    _GLORY = ["exaltation", "glory", "supremacy", "angels", "better than angels"]
    # Closing must reference incarnation/identification, and must NOT be pure exaltation language
    _closing_lower = w1.week_closing_location.lower()
    _has_incarnation = _contains_any(w1.week_closing_location, _INCARNATION)
    _only_glory = (not _has_incarnation and _contains_any(w1.week_closing_location, _GLORY))
    c3_ok = _has_incarnation and not _only_glory
    report.add(CheckpointResult(
        checkpoint_id="W1_C3",
        passed=c3_ok,
        verdict_contribution="fail",
        description="W1: closing does not reference incarnation/identification — Day 5 must land on Heb 2:14-18 necessity" if not c3_ok else "W1: closing references incarnation",
        revision_target="week_closing_location, days[4].arg_advance_claim",
        cascade_targets=["W2_C2"],
    ))

    # W1_C4: Day 5 arg_advance_claim must not duplicate Day 1
    if len(days) >= 5:
        c4_ok = not _is_equivalent(days[4].arg_advance_claim, days[0].arg_advance_claim)
        report.add(CheckpointResult(
            checkpoint_id="W1_C4",
            passed=c4_ok,
            verdict_contribution="fail",
            description="W1: Day 5 arg_advance_claim duplicates Day 1 — no argumentative advance across the week" if not c4_ok else "W1: Day 5 is distinct from Day 1",
            revision_target="days[4].arg_advance_claim",
        ))


def _check_week2(w1: WeekOutline, w2: WeekOutline, report: ArcCoherenceReport) -> None:
    """W2 (Chs 3-4): Who Jesus is → what his people risk → open invitation (4:14-16).
    Must end with unresolved tension, not closure."""

    # W2_C3: closing must be open invitation, not closure
    _INVITATION = ["throne of grace", "approach", "invitation", "mercy", "help", "4:14", "4:16", "bold", "confiden", "draw near"]
    _CLOSURE = ["resolved", "settled", "concluded", "answered", "complete", "finished"]
    c3_ok = (
        _contains_any(w2.week_closing_location, _INVITATION)
        and not _contains_any(w2.week_closing_location, _CLOSURE)
    )
    report.add(CheckpointResult(
        checkpoint_id="W2_C3",
        passed=c3_ok,
        verdict_contribution="fail",
        description="W2: closing signals resolution instead of open invitation (4:14-16) — tension must remain unresolved" if not c3_ok else "W2: closing holds tension open",
        revision_target="week_closing_location, days[4].arg_advance_claim",
        cascade_targets=["W3_C7"],
    ))

    # W2_C4: at least one day must carry risk/warning content
    _RISK = ["risk", "harden", "drift", "rest", "fall short", "warning", "unbelief", "disobedience", "3:7", "3:11", "4:1"]
    c4_ok = any(
        d.day_subtype == "warning_beat"
        or _contains_any(d.arg_advance_claim, _RISK)
        for d in w2.days
    )
    report.add(CheckpointResult(
        checkpoint_id="W2_C4",
        passed=c4_ok,
        verdict_contribution="revise",
        description="W2: no day carries risk/warning content — W2 must address what Christ's people risk (Heb 3-4)" if not c4_ok else "W2: risk content present",
        revision_target="day arg_advance_claim for risk/warning content",
    ))

    # W2_C5: closing != opening (arc movement)
    c5_ok = not _is_equivalent(w2.week_closing_location, w2.week_opening_tension)
    report.add(CheckpointResult(
        checkpoint_id="W2_C5",
        passed=c5_ok,
        verdict_contribution="fail",
        description="W2: week_closing_location equivalent to week_opening_tension — no arc movement" if not c5_ok else "W2: arc movement confirmed",
        revision_target="week_closing_location",
    ))


def _check_week3(w2: WeekOutline, w3: WeekOutline, report: ArcCoherenceReport) -> None:
    """W3 (Chs 5-7): Three sequential moves: suffering qualification → maturity warning → eternal priesthood.
    Warning (5:11-6:12) must appear as structural beat, not interruption routed around."""
    days = w3.days

    # W3_C1: must have at least one warning_beat day
    warning_days = [d for d in days if d.day_subtype == "warning_beat"]
    c1_ok = len(warning_days) > 0
    report.add(CheckpointResult(
        checkpoint_id="W3_C1",
        passed=c1_ok,
        verdict_contribution="fail",
        description="W3: no warning_beat day — SF-4: Heb 5:11-6:12 maturity warning absent from Week 3" if not c1_ok else "W3: warning_beat day present",
        revision_target="days — add warning_beat day for Heb 5:11-6:12",
    ))

    # W3_C2: warning days must have warning_position == "mid_week"
    if warning_days:
        c2_ok = all(d.warning_position == "mid_week" for d in warning_days)
        report.add(CheckpointResult(
            checkpoint_id="W3_C2",
            passed=c2_ok,
            verdict_contribution="fail",
            description="W3: warning_beat days have wrong warning_position (expected 'mid_week')" if not c2_ok else "W3: warning_position='mid_week' correct",
            revision_target="days[N].warning_position",
        ))

    # W3_C3: sequential moves verified — pre/post warning arg content
    warning_indices = [i for i, d in enumerate(days) if d.day_subtype == "warning_beat"]
    if warning_indices:
        first_wi = min(warning_indices)
        last_wi = max(warning_indices)

        pre_arg_days = [d for i, d in enumerate(days) if i < first_wi and d.day_subtype == "argument_step"]
        post_arg_days = [d for i, d in enumerate(days) if i > last_wi and d.day_subtype == "argument_step"]

        _SUFFERING = ["suffering", "qualification", "learned obedience", "high priest", "5:1", "5:7", "5:10",
                      "appointed", "compassion", "weakness", "tempted", "source of salvation"]
        _PRIESTHOOD = ["melchizedek", "eternal", "priesthood", "7:", "order of", "forever",
                       "unchangeable", "better covenant", "guarantor"]

        c3a_ok = bool(pre_arg_days) and all(_contains_any(d.arg_advance_claim, _SUFFERING) for d in pre_arg_days)
        c3b_ok = bool(post_arg_days) and all(_contains_any(d.arg_advance_claim, _PRIESTHOOD) for d in post_arg_days)

        report.add(CheckpointResult(
            checkpoint_id="W3_C3a",
            passed=c3a_ok,
            verdict_contribution="fail",
            description="W3: pre-warning argument days don't reference suffering/qualification (5:1-10) — Move 1 missing" if not c3a_ok else "W3: Move 1 (suffering qualification) present",
            revision_target="pre-warning days arg_advance_claim",
        ))
        report.add(CheckpointResult(
            checkpoint_id="W3_C3b",
            passed=c3b_ok,
            verdict_contribution="fail",
            description="W3: post-warning days don't reference eternal priesthood/Melchizedek (7:1ff) — Move 3 missing or missing from outline" if not c3b_ok else "W3: Move 3 (eternal priesthood) present",
            revision_target="post-warning days arg_advance_claim",
        ))

        # W3_C4: antecedent chain goes THROUGH the warning (not skipping 5:11-6:12 to jump to 7:1ff)
        _WARNING_BRIDGE = ["warning", "maturity", "6:", "5:11", "drift", "fallen away",
                           "pressing on", "having established the warning", "having addressed the danger",
                           "in light of the warning"]
        if post_arg_days:
            first_post = post_arg_days[0]
            c4_ok = _contains_any(first_post.logical_antecedent, _WARNING_BRIDGE)
            report.add(CheckpointResult(
                checkpoint_id="W3_C4",
                passed=c4_ok,
                verdict_contribution="fail",
                description="W3: first post-warning day's logical_antecedent skips warning content — outliner routes around 5:11-6:12 to jump to 7:1ff (SF-4 / SD-2)" if not c4_ok else "W3: antecedent chain passes through warning",
                revision_target="first post-warning day logical_antecedent",
            ))

        # W3_C5: warning days' own antecedent must reference preceding suffering/qualification
        if warning_days:
            c5_ok = all(
                not _is_generic(d.logical_antecedent)
                and _contains_any(d.logical_antecedent, _SUFFERING + ["established", "because"])
                for d in warning_days
            )
            report.add(CheckpointResult(
                checkpoint_id="W3_C5",
                passed=c5_ok,
                verdict_contribution="fail",
                description="W3: warning day logical_antecedent empty/generic — must reference suffering/qualification content (C2 Theological Reviewer)" if not c5_ok else "W3: warning day antecedent references preceding argument",
                revision_target="warning_beat day logical_antecedent",
            ))

    # W3_C6: closing must reference eternal priesthood / Melchizedek
    _MELCH = ["melchizedek", "eternal priesthood", "7:", "order of melchizedek", "forever", "unchangeable priest"]
    c6_ok = _contains_any(w3.week_closing_location, _MELCH)
    report.add(CheckpointResult(
        checkpoint_id="W3_C6",
        passed=c6_ok,
        verdict_contribution="fail",
        description="W3: week_closing_location does not reference Melchizedek/eternal priesthood — Week 3 must land on 7:1ff" if not c6_ok else "W3: closing references eternal priesthood",
        revision_target="week_closing_location",
    ))


def _check_week4(w3: WeekOutline, w4: WeekOutline, report: ArcCoherenceReport) -> None:
    """W4 (Chs 8-9): Covenant → Tabernacle/Sanctuary → Sacrifice in sequence.
    Day 5 must land on sufficiency of single sacrifice (9:24-28) as bridge to Week 5."""
    days = w4.days
    arg_step_days = [d for d in days if d.day_subtype == "argument_step"]

    # W4_C1: Covenant → Sanctuary → Sacrifice sequence across thirds
    if arg_step_days:
        arg_indices = sorted(d.arg_step_index for d in arg_step_days if d.arg_step_index is not None)
        if len(arg_indices) >= 3:
            third = len(arg_indices) // 3
            early_cutoff = arg_indices[third - 1]
            late_cutoff = arg_indices[2 * third - 1]

            early = [d for d in arg_step_days if d.arg_step_index is not None and d.arg_step_index <= early_cutoff]
            mid = [d for d in arg_step_days if d.arg_step_index is not None and early_cutoff < d.arg_step_index <= late_cutoff]
            late = [d for d in arg_step_days if d.arg_step_index is not None and d.arg_step_index > late_cutoff]

            _COVENANT = ["covenant", "new covenant", "8:", "better promises", "mediator", "better covenant"]
            _SANCTUARY = ["tabernacle", "sanctuary", "tent", "copy", "shadow", "9:1", "9:11", "earthly"]
            _SACRIFICE = ["sacrifice", "blood", "9:24", "9:28", "once", "ephapax", "offered", "put away sin"]

            c1a = any(_contains_any(d.arg_advance_claim, _COVENANT) for d in early)
            c1b = any(_contains_any(d.arg_advance_claim, _SANCTUARY) for d in mid)
            c1c = any(_contains_any(d.arg_advance_claim, _SACRIFICE) for d in late)

            report.add(CheckpointResult(
                checkpoint_id="W4_C1",
                passed=c1a and c1b and c1c,
                verdict_contribution="fail",
                description=(
                    "W4: Covenant→Sanctuary→Sacrifice sequence not present — "
                    + ("Covenant missing. " if not c1a else "")
                    + ("Sanctuary missing. " if not c1b else "")
                    + ("Sacrifice missing." if not c1c else "")
                    if not (c1a and c1b and c1c) else "W4: Covenant→Sanctuary→Sacrifice sequence confirmed"
                ),
                revision_target="arg_advance_claim for early/mid/late argument days",
            ))

    # W4_C2: Day 5 arg_advance_claim references 9:24-28 sufficiency
    _SUFFICIENCY = ["9:24", "9:28", "once for all", "ephapax", "single sacrifice", "offered once", "not repeated", "sufficiency", "appeared once"]
    if len(days) >= 5:
        c2_ok = _contains_any(days[4].arg_advance_claim, _SUFFICIENCY)
        report.add(CheckpointResult(
            checkpoint_id="W4_C2",
            passed=c2_ok,
            verdict_contribution="fail",
            description="W4: Day 5 does not reference sufficiency of single sacrifice (9:24-28) — required as bridge to Week 5 declaration" if not c2_ok else "W4: Day 5 lands on 9:24-28 sufficiency",
            revision_target="days[4].arg_advance_claim",
        ))

    # W4_C3: closing references sacrifice sufficiency
    c3_ok = _contains_any(w4.week_closing_location, _SUFFICIENCY + ["sufficient", "complete", "basis for", "ground of", "10:"])
    report.add(CheckpointResult(
        checkpoint_id="W4_C3",
        passed=c3_ok,
        verdict_contribution="revise",
        description="W4: week_closing_location does not reference sacrifice sufficiency — needed as bridge premise for W5" if not c3_ok else "W4: closing references sacrifice completion",
        revision_target="week_closing_location",
    ))

    # W4_C4: bridge must reference completed sacrifice as premise for W5
    _BRIDGE_TOKENS = ["complete", "sufficient", "single sacrifice", "once", "9:28", "ground", "basis", "therefore", "offered"]
    bridge = w4.week_to_week_bridge or ""
    c4_ok = bool(bridge) and _contains_any(bridge, _BRIDGE_TOKENS)
    report.add(CheckpointResult(
        checkpoint_id="W4_C4",
        passed=c4_ok,
        verdict_contribution="fail",
        description="W4: week_to_week_bridge does not reference completed sacrifice as premise for Week 5" if not c4_ok else "W4: bridge sets up W5 on completed sacrifice",
        revision_target="week_to_week_bridge",
    ))


def _check_week5(w4: WeekOutline, w5: WeekOutline, report: ArcCoherenceReport) -> None:
    """W5 (Ch 10): Declaration (10:1-18) → Warning (10:26-31) → Encouragement (10:32-39).
    All three movements in order. Week 5 concludes Heb 1-10; does not set up Heb 11."""
    days = w5.days

    # SF-2 / W5_C1: three moves in correct order
    warning_indices = [i for i, d in enumerate(days) if d.day_subtype == "warning_beat"]
    c1a = len(warning_indices) >= 1

    _DECLARATION = ["10:1", "10:18", "once for all", "sins remembered no more",
                    "perfected", "single offering", "sat down", "declaration"]
    _ENCOURAGEMENT = ["10:32", "10:39", "endure", "encourage", "confidence",
                      "do not throw away", "persevere", "live by faith", "do not shrink"]

    if warning_indices:
        first_wi = min(warning_indices)
        last_wi = max(warning_indices)
        pre_warn = [d for i, d in enumerate(days) if i < first_wi]
        post_warn = [d for i, d in enumerate(days) if i > last_wi]

        c1b = any(_contains_any(d.arg_advance_claim, _DECLARATION) for d in pre_warn)
        c1c = bool(post_warn) and any(_contains_any(d.arg_advance_claim, _ENCOURAGEMENT) for d in post_warn)
    else:
        c1b = False
        c1c = False

    report.add(CheckpointResult(
        checkpoint_id="SF-2",
        passed=c1a and c1b and c1c,
        verdict_contribution="fail",
        description=(
            "W5 SF-2: Declaration→Warning→Encouragement sequence incomplete — "
            + ("Warning absent. " if not c1a else "")
            + ("Declaration content missing before warning. " if not c1b else "")
            + ("Encouragement content missing after warning." if not c1c else "")
            if not (c1a and c1b and c1c) else "W5: Declaration→Warning→Encouragement in order"
        ),
        revision_target="days — day_subtype and arg_advance_claim for all W5 days",
    ))

    # W5_C3: closing must reference conclusion of Heb 1-10, not Heb 11
    _HEB11 = ["hebrews 11", "hall of faith", "therefore since we are surrounded",
               "cloud of witnesses", "chapter 11", "faith heroes"]
    _CONCLUSION = ["10:39", "conclusion", "perseverance", "confidence", "do not shrink back",
                   "live by faith", "endurance", "completing", "ground of assurance"]
    c3_ok = (
        not _contains_any(w5.week_closing_location, _HEB11)
        and _contains_any(w5.week_closing_location, _CONCLUSION)
    )
    report.add(CheckpointResult(
        checkpoint_id="W5_C3",
        passed=c3_ok,
        verdict_contribution="fail",
        description="W5: closing references Hebrews 11 or lacks Heb 10 conclusion content — SF-6" if not c3_ok else "W5: closing concludes Heb 1-10 correctly",
        revision_target="week_closing_location",
    ))

    # SF-6: bridge must be null; no Heb 11 forward references
    c4_ok = w5.week_to_week_bridge is None
    report.add(CheckpointResult(
        checkpoint_id="SF-6",
        passed=c4_ok,
        verdict_contribution="fail",
        description="SF-6: W5.week_to_week_bridge is not null — this volume must conclude, not bridge to Heb 11" if not c4_ok else "SF-6: W5 bridge correctly null",
        revision_target="week_to_week_bridge (set to null)",
    ))

    # No day in W5 may reference Heb 11 content (SF-6: volume must conclude, not set up next volume)
    _HEB11_CHARS = ["hebrews 11", "hall of faith", "cloud of witnesses", "abel", "enoch", "chapter 11"]
    heb11_day_violations = []
    for d_idx, day in enumerate(days):
        for field_name, text in [("arg_advance_claim", day.arg_advance_claim),
                                  ("logical_antecedent", day.logical_antecedent)]:
            if _contains_any(text, _HEB11_CHARS):
                heb11_day_violations.append(f"days[{d_idx}].{field_name}")
    c6_ok = len(heb11_day_violations) == 0
    report.add(CheckpointResult(
        checkpoint_id="W5_C6",
        passed=c6_ok,
        verdict_contribution="fail",
        description=(
            f"W5: Heb 11 references found in {', '.join(heb11_day_violations)} — "
            "W5 scope is Heb 10:1-39; outline must conclude within volume, not set up Heb 11"
            if not c6_ok else "W5: all days conclude within Heb 1-10"
        ),
        revision_target="arg_advance_claim and logical_antecedent for flagged days",
    ))
