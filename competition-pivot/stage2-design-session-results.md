# Stage 2 Design Session Results

**Date:** 2026-03-25
**Status:** Outliner Trainer response — awaiting implementation

---

## Script Output

# Stage 2 Arc Coherence Evaluation — Machine-Readable Specification

**Authority:** Outliner Trainer
**Input:** List of 5 WeekOutline objects, indexed `W[1]` through `W[5]`
**Scope:** Cross-week arc evaluation. Per-day validation is Stage 1 / per-week pass. This pass runs after all 5 WeekOutlines are valid at the per-week level.

---

## Part 1: Weekly Arc Checkpoint Checks

Each checkpoint operates on a single `WeekOutline` object plus cross-week comparisons where specified.

---

### Checkpoint W1 — Hebrews 1–2 (Exaltation → Incarnation Necessity)

**Baseline requirement:** Opens on exaltation of Son → descends into necessity of incarnation. Day 5 must land on incarnation/identification, not restate opening glory.

```python
# W1_CHECK_1: week_opening_tension must reference exaltation / Son's supremacy
# Not machine-verifiable by field value alone — flag for semantic review
# Operationalized as: week_opening_tension must be non-empty (already enforced Stage 1)
# Stage 2 adds: semantic classifier checks for "exaltation" | "Son" | "supremacy" cluster
W1_C1 = W[1]["week_opening_tension"] != "" and not is_null(W[1]["week_opening_tension"])

# W1_CHECK_2: week_closing_location must NOT be semantically equivalent to week_opening_tension
# Hard fail condition (already Stage 1 per-week) — re-confirmed at arc level
W1_C2 = not semantic_equivalent(W[1]["week_closing_location"], W[1]["week_opening_tension"])

# W1_CHECK_3: week_closing_location must reference incarnation OR identification OR humanity
# Operationalized: semantic classifier checks for "incarnation" | "identification" | 
# "humanity" | "suffering" | "had to" cluster
# NOT flagged if contains "glory" | "exaltation" as primary claim
W1_C3 = semantic_contains_any(
    W[1]["week_closing_location"],
    ["incarnation", "identification", "humanity", "necessity", "suffered"]
) and not semantic_primary_claim(
    W[1]["week_closing_location"],
    ["exaltation", "glory", "supremacy"]
)

# W1_CHECK_4: Day 5 arg_advance_claim must not duplicate Day 1 arg_advance_claim
# Operationalized by field comparison
day1 = W[1]["days"][0]
day5 = W[1]["days"][4]
W1_C4 = not semantic_equivalent(day5["arg_advance_claim"], day1["arg_advance_claim"])

# W1_CHECK_5: stakes_level baseline — Week 1 establishes floor
# Checked here for record; cross-week escalation checked in SD-1 block
W1_C5 = isinstance(W[1]["stakes_level"], int) and 1 <= W[1]["stakes_level"] <= 5

# W1 VERDICT
W1_PASS = W1_C1 and W1_C2 and W1_C3 and W1_C4 and W1_C5
W1_HARD_FAIL_FLAGS = [
    ("W1_C2", not W1_C2, "HARD_FAIL"),   # closing == opening is SF-1 territory
    ("W1_C3", not W1_C3, "HARD_FAIL"),   # Day 5 not at incarnation = arc failure
    ("W1_C4", not W1_C4, "HARD_FAIL"),   # Day 5 duplicates Day 1
    ("W1_C1", not W1_C1, "FLAG"),
    ("W1_C5", not W1_C5, "FLAG"),
]
```

---

### Checkpoint W2 — Hebrews 3–4 (Identity → Risk → Open Invitation)

**Baseline requirement:** Moves from who Jesus is to what his people risk. Week must end with open invitation of 4:14-16, not closure — tension unresolved.

```python
# W2_CHECK_1: week_opening_tension must reference identity / "who Jesus is" cluster
# Confirms forward movement from W1 close (incarnation) into W2 open (positional identity)
W2_C1 = semantic_contains_any(
    W[2]["week_opening_tension"],
    ["identity", "who", "faithful", "Moses", "Son over house", "apostle", "high priest"]
)

# W2_CHECK_2: week_to_week_bridge from W1 must be upstream of W2 opening
# W[1]["week_to_week_bridge"] must be semantically upstream of W[2]["week_opening_tension"]
# Upstream = bridge premise is necessary antecedent to opening tension
W2_C2 = semantic_is_upstream(W[1]["week_to_week_bridge"], W[2]["week_opening_tension"])

# W2_CHECK_3: week_closing_location must NOT signal closure/resolution
# Must contain open invitation language, not conclusory language
# Operationalized: must contain "therefore approach" | "throne of grace" | "invitation" cluster
# Must NOT contain "therefore we know" | "settled" | "conclusion" as primary claim
W2_C3 = (
    semantic_contains_any(
        W[2]["week_closing_location"],
        ["throne of grace", "approach", "invitation", "mercy", "help", "4:14", "4:16"]
    )
    and not semantic_primary_claim(
        W[2]["week_closing_location"],
        ["resolved", "settled", "concluded", "answered"]
    )
)

# W2_CHECK_4: At least one day must carry warning/risk content
# day_subtype == "warning_beat" OR arg_advance_claim contains risk cluster
W2_C4 = any(
    d["day_subtype"] == "warning_beat"
    or semantic_contains_any(d["arg_advance_claim"], ["risk", "harden", "drift", "rest", "fall short", "warning"])
    for d in W[2]["days"]
)

# W2_CHECK_5: week_closing_location != week_opening_tension (arc movement)
W2_C5 = not semantic_equivalent(W[2]["week_closing_location"], W[2]["week_opening_tension"])

# W2 VERDICT
W2_PASS = W2_C1 and W2_C2 and W2_C3 and W2_C4 and W2_C5
W2_HARD_FAIL_FLAGS = [
    ("W2_C2", not W2_C2, "HARD_FAIL"),   # W1 bridge not feeding W2 open
    ("W2_C3", not W2_C3, "HARD_FAIL"),   # W2 closes instead of holding tension open
    ("W2_C5", not W2_C5, "HARD_FAIL"),   # No arc movement
    ("W2_C4", not W2_C4, "FLAG"),
    ("W2_C1", not W2_C1, "FLAG"),
]
```

---

### Checkpoint W3 — Hebrews 5–7 (Three Sequential Moves)

**Baseline requirement:** Three sequential moves: suffering qualification → maturity warning → eternal priesthood. Warning passage (5:11–6:12) must appear as structural beat, not interruption routed around.

```python
# W3 requires exactly 3 structural moves in sequence:
# Move 1: suffering qualification (5:1-10) — arg_step days
# Move 2: warning beat (5:11-6:12) — warning_beat day(s)
# Move 3: eternal priesthood (7:1ff) — arg_step days

days = W[3]["days"]

# W3_CHECK_1: At least one day_subtype == "warning_beat" exists in W3
W3_C1 = any(d["day_subtype"] == "warning_beat" for d in days)

# W3_CHECK_2: warning_position on warning day(s) == "mid_week"
warning_days = [d for d in days if d["day_subtype"] == "warning_beat"]
W3_C2 = all(d["warning_position"] == "mid_week" for d in warning_days)

# W3_CHECK_3: Sequential move order enforced
# All arg_step days BEFORE the warning day must have arg_advance_claim in 
# suffering/qualification cluster
# All arg_step days AFTER the warning day must have arg_advance_claim in 
# priesthood/Melchizedek/eternal cluster
warning_indices = [i for i, d in enumerate(days) if d["day_subtype"] == "warning_beat"]
first_warning_idx = min(warning_indices)
last_warning_idx = max(warning_indices)

pre_warning_arg_days = [d for i, d in enumerate(days) 
                         if i < first_warning_idx and d["day_subtype"] == "argument_step"]
post_warning_arg_days = [d for i, d in enumerate(days) 
                          if i > last_warning_idx and d["day_subtype"] == "argument_step"]

W3_C3a = all(
    semantic_contains_any(d["arg_advance_claim"], 
        ["suffering", "qualification", "learned obedience", "high priest", "5:1", "5:7", "5:10"])
    for d in pre_warning_arg_days
) if pre_warning_arg_days else False  # Pre-warning days must exist

W3_C3b = all(
    semantic_contains_any(d["arg_advance_claim"],
        ["Melchizedek", "eternal", "priesthood", "7:", "order of", "forever"])
    for d in post_warning_arg_days
) if post_warning_arg_days else False  # Post-warning days must exist

W3_C3 = W3_C3a and W3_C3b

# W3_CHECK_4: Antecedent chain writable THROUGH warning day
# logical_antecedent on first post-warning arg_step day must reference warning content
# Not skipping 5:11-6:12 to jump to 7:1ff
W3_C4 = False  # default
if post_warning_arg_days:
    first_post = post_warning_arg_days[0]
    W3_C4 = semantic_contains_any(
        first_post["logical_antecedent"],
        ["warning", "maturity", "6:", "5:11", "drift", "fallen away", "pressing on",
         "having established the warning", "having addressed the danger"]
    )

# W3_CHECK_5: Warning days themselves have non-empty logical_antecedent 
# referencing suffering/qualification content (C2 from Theological Reviewer)
W3_C5 = all(
    d["logical_antecedent"] != "" and not is_generic(d["logical_antecedent"])
    and semantic_contains_any(d["logical_antecedent"],
        ["suffering", "qualification", "learned", "5:1", "5:10", "established"])
    for d in warning_days
)

# W3_CHECK_6: week_closing_location references eternal priesthood / Melchizedek
W3_C6 = semantic_contains_any(
    W[3]["week_closing_location"],
    ["Melchizedek", "eternal priesthood", "7:", "order of Melchizedek", "forever"]
)

# W3_CHECK_7: week_to_week_bridge from W2 is upstream of W3 opening
W3_C7 = semantic_is_upstream(W[2]["week_to_week_bridge"], W[3]["week_opening_tension"])

# W3 VERDICT
W3_PASS = W3_C1 and W3_C2 and W3_C3 and W3_C4 and W3_C5 and W3_C6 and W3_C7
W3_HARD_FAIL_FLAGS = [
    ("W3_C1", not W3_C1, "HARD_FAIL"),   # No warning beat — SF-4
    ("W3_C2", not W3_C2, "HARD_FAIL"),   # Warning not mid_week
    ("W3_C3", not W3_C3, "HARD_FAIL"),   # Sequence violated
    ("W3_C4", not W3_C4, "HARD_FAIL"),   # Skip from 5:10 to 7:1 — SF-4 / SD-2
    ("W3_C5", not W3_C5, "HARD_FAIL"),   # Warning day antecedent empty/generic — C2
    ("W3_C6", not W3_C6, "HARD_FAIL"),   # Week doesn't land on priesthood
    ("W3_C7", not W3_C7, "FLAG"),
]
```

---

### Checkpoint W4 — Hebrews 8–9 (Covenant → Sanctuary → Sacrifice)

**Baseline requirement:** Covenant → Tabernacle/Sanctuary → Sacrifice in sequence. Day 5 must land on sufficiency of single sacrifice (9:24-28) as bridge to Week 5.

```python
days = W[4]["days"]

# W4_CHECK_1: Sequence confirmed by arg_advance_claim content across argument_step days
# Sequence: Covenant cluster → Sanctuary/Tabernacle cluster → Sacrifice cluster
arg_step_days = [d for d in days if d["day_subtype"] == "argument_step"]

# Divide into thirds by arg_step_index (early / middle / late)
arg_indices = sorted([d["arg_step_index"] for d in arg_step_days])
early_cutoff = arg_indices[len(arg_indices)//3]
late_cutoff = arg_indices[2*len(arg_indices)//3]

early_days = [d for d in arg_step_days if d["arg_step_index"] <= early_cutoff]
mid_days = [d for d in arg_step_days 
             if early_cutoff < d["arg_step_index"] <= late_cutoff]
late_days = [d for d in arg_step_days if d["arg_step_index"] > late_cutoff]

W4_C1a = any(
    semantic_contains_any(d["arg_advance_claim"],
        ["covenant", "new covenant", "8:", "better promises", "mediator"])
    for d in early_days
)
W4_C1b = any(
    semantic_contains_any(d["arg_advance_claim"],
        ["tabernacle", "sanctuary", "tent", "copy", "shadow", "9:1", "9:11"])
    for d in mid_days
)
W4_C1c = any(
    semantic_contains_any(d["arg_advance_claim"],
        ["sacrifice", "blood", "9:24", "9:28", "once", "ephapax", "offered"])
    for d in late_days
)
W4_C1 = W4_C1a and W4_C1b and W4_C1c

# W4_CHECK_2: Day 5 (index 4) arg_advance_claim references 9:24-28 / single sacrifice sufficiency
day5 = days[4]
W4_C2 = semantic_contains_any(
    day5["arg_advance_claim"],
    ["9:24", "9:28", "once for all", "ephapax", "single sacrifice", 
     "offered once", "sufficiency", "not repeated"]
)

# W4_CHECK_3: week_closing_location references sacrifice sufficiency as bridge to W5
W4_C3 = semantic_contains_any(
    W[4]["week_closing_location"],
    ["sufficient", "once", "9:28", "sacrifice complete", "offered once", 
     "basis for", "ground of", "10:"]
)

# W4_CHECK_4: week_to_week_bridge must reference completed sacrifice as premise for W5
# W5 opens on declaration (10:1-18) — bridge must make that opening possible
W4_C4 = (
    W[4]["week_to_week_bridge"] is not None
    and semantic_contains_any(
        W[4]["week_to_week_bridge"],
        ["complete", "sufficient", "single sacrifice", "once", "9:28", 
         "ground", "basis", "therefore"]
    )
)

# W4_CHECK_5: week_to_week_bridge from W3 is upstream of W4 opening
W4_C5 = semantic_is_upstream(W[3]["week_to_week_bridge"], W[4]["week_opening_tension"])

# W4_CHECK_6: No arg_step_index regression in W4
step_indices = [d["arg_step_index"] for d in arg_step_days]
W4_C6 = step_indices == sorted(step_indices) and len(step_indices) == len(set(step_indices))

# W4 VERDICT
W4_PASS = W4_C1 and W4_C2 and W4_C3 and W4_C4 and W4_C5 and W4_C6
W4_HARD_FAIL_FLAGS = [
    ("W4_C1", not W4_C1, "HARD_FAIL"),   # Sequence violated
    ("W4_C2", not W4_C2, "HARD_FAIL"),   # Day 5 not at 9:24-28
    ("W4_C4", not W4_C4, "HARD_FAIL"),   # Bridge doesn't set up W5
    ("W4_C6", not W4_C6, "HARD_FAIL"),   # Index regression
    ("W4_C3", not W4_C3, "FLAG"),
    ("W4_C5", not W4_C5, "FLAG"),
]
```

---

### Checkpoint W5 — Hebrews 10 (Declaration → Warning → Encouragement)

**Baseline requirement:** Declaration (10:1-18) → Warning (10:26-31) → Encouragement (10:32-39). All three present in order. Week 5 concludes this volume, does not set up Hebrews 11.

```python
days = W[5]["days"]

# W5_CHECK_1: Exactly the three structural moves present and in order
# Move 1 (Declaration): arg_step days with 10:1-18 cluster, appearing before warning
# Move 2 (Warning): day_subtype == "warning_beat" 
# Move 3 (Encouragement): arg_step or exhortation days with 10:32-39 cluster, after warning

warning_days_w5 = [i for i, d in enumerate(days) if d["day_subtype"] == "warning_beat"]
W5_C1a = len(warning_days_w5) >= 1  # Warning present

first_warn_idx = min(warning_days_w5) if warning_days_w5 else None
last_warn_idx = max(warning_days_w5) if warning_days_w5 else None

pre_warn_days = [d for i, d in enumerate(days) if first_warn_idx is not None and i < first_warn_idx]
post_warn_days = [d for i, d in enumerate(days) if last_warn_idx is not None and i > last_warn_idx]

W5_C1b = any(  # Declaration days exist before warning
    semantic_contains_any(d["arg_advance_claim"],
        ["10:1", "10:18", "declaration", "once for all", "sins remembered no more",
         "perfected", "offering", "single offering"])
    for d in pre_warn_days
)

W5_C1c = any(  # Encouragement days exist after warning
    semantic_contains_any(d["arg_advance_claim"],
        ["10:32", "10:39", "endure", "encourage", "confidence", 
         "do not throw away", "persevere", "live by faith"])
    for d in post_warn_days
) if post_warn_days else False

W5_C1 = W5_C1a and W5_C1b and W5_C1c

# W5_CHECK_2: warning_position on W5 warning day(s) == "end_of_week"
W5_warning_objs = [d for d in days if d["day_subtype"] == "warning_beat"]
W5_C2 = all(d["warning_position"] == "end_of_week" for d in W5_warning_objs)
# Note: "end_of_week" here means structurally after Declaration and before Encouragement
# within the week — the field value enforced as specified, position order enforced by W5_C1

# W5_CHECK_3: week_closing_location references conclusion of Hebrews 1-10 arc
# Must NOT reference Hebrews 11 / Hall of Faith / "faith heroes" as forward setup
W5_C3 = (
    not semantic_contains_any(
        W[5]["week_closing_location"],
        ["Hebrews 11", "hall of faith", "therefore since we are surrounded", 
         "cloud of witnesses", "chapter 11", "faith heroes"]
    )
    and semantic_contains_any(
        W[5]["week_closing_location"],
        ["10:39", "conclusion", "perseverance", "confidence", "do not shrink back",
         "live by faith", "endurance", "completing", "ground of assurance"]
    )
)

# W5_CHECK_4: week_to_week_bridge must be null for Week 5
W5_C4 = W[5]["week_to_week_bridge"] is None

# W5_CHECK_5: week_to_week_bridge from W4 is upstream of W5 opening
W5_C5 = semantic_is_upstream(W[4]["week_to_week_bridge"], W[5]["week_opening_tension"])

# W5_CHECK_6: Day 5 arg_advance_claim does not reference Hebrews 11 content as primary move
day5_w5 = days[4]
W5_C6 = not semantic_primary_claim(
    day5_w5["arg_advance_claim"],
    ["Hebrews 11", "hall of faith", "cloud of witnesses", "Abel", "Enoch", 
     "Noah", "Abraham", "chapter 11"]
)

# W5 VERDICT
W5_PASS = W5_C1 and W5_C2 and W5_C3 and W5_C4 and W5_C5 and W5_C6
W5_HARD_FAIL_FLAGS = [
    ("W5_C1", not W5_C1, "HARD_FAIL"),   # Missing move or order violated — SF-2
    ("W5_C2", not W5_C2, "HARD_FAIL"),   # Warning not in correct position field
    ("W5_C3", not W5_C3, "HARD_FAIL"),   # Week closes on Heb 11 setup — SF-6
    ("W5_C4", not W5_C4, "HARD_FAIL"),   # Bridge not null — volume not concluded
    ("W5_C6", not W5_C6, "HARD_FAIL"),   # Day 5 forward-references Heb 11 — SF-6
    ("W5_C5", not W5_C5, "FLAG"),
]
```

---

## Part 2: SF Condition Detection

Each SF maps to boolean expressions over WeekOutline fields.

---

### SF-1: Any two days within a week are interchangeable without loss of argument

```python
def detect_SF1(week: dict) -> bool:
    """
    Returns True (SF-1 triggered) if any two argument_step days in the week
    are interchangeable without loss of argument.
    Operationalized as:
    - Two arg_step days share semantically equivalent arg_advance_claim, OR
    - Two arg_step days have arg_step_index gap > 1 with no intermediate days
      (index skip indicates missing step, making surrounding days functionally adjacently swappable), OR
    - logical_antecedent of Day N+1 does not reference Day N content
    """
    days = week["days"]
    arg_step_days = [(i, d) for i, d in enumerate(days) if d["day_subtype"] == "argument_step"]
    
    SF1_triggered = False
    SF1_reasons = []

    # Check 1: Semantically equivalent arg_advance_claim between any two arg_step days
    for i in range(len(arg_step_days)):
        for j in range(i+1, len(arg_step_days)):
            idx_i, day_i = arg_step_days[i]
            idx_j, day_j = arg_step_days[j]
            if semantic_equivalent(day_i["arg_advance_claim"], day_j["arg_advance_claim"]):
                SF1_triggered = True
                SF1_reasons.append(
                    f"SF-1: Days at positions {idx_i} and {idx_j} have equivalent "
                    f"arg_advance_claim. Fields: days[{idx_i}].arg_advance_claim, "
                    f"days[{idx_j}].arg_advance_claim"
                )

    # Check 2: logical_antecedent of each arg_step day (Day 2+) must reference prior day
    for k in range(1, len(arg_step_days)):
        prev_idx, prev_day = arg_step_days[k-1]
        curr_idx, curr_day = arg_step_days[k]
        if not semantic_contains_upstream(
            curr_day["logical_antecedent"], 
            prev_day["arg_advance_claim"]
        ):
            SF1_triggered = True
            SF1_reasons.append(
                f"SF-1: days[{curr_idx}].logical_antecedent does not reference "
                f"days[{prev_idx}].arg_advance_claim — days are logically detached "
                f"and therefore interchangeable."
            )

    return SF1_triggered, SF1_reasons
```

**Fields used:** `days[N].day_subtype`, `days[N].arg_advance_claim`, `days[N].logical_antecedent`, `days[N].arg_step_index`

---

### SF-2: Week 5 does not contain Declaration → Warning → Encouragement in sequence

```python
def detect_SF2(W5: dict) -> bool:
    """
    Directly maps to W5_C1 check above.
    SF-2 is triggered when any of the three moves is absent OR when order is violated.
    """
    # Already computed as W5_C1a, W5_C1b, W5_C1c above
    # Re-run or import result
    SF2_triggered = not W5_C1
    SF2_reasons = []

    if not W5_C1a:
        SF2_reasons.append(
            "SF-2: No warning_beat day found in W5.days — "
            "warning move (10:26-31) absent."
        )
    if not W5_C1b:
        SF2_reasons.append(
            "SF-2: No pre-warning arg_step day with Declaration content (10:1-18) — "
            "Declaration move absent or mispositioned."
        )
    if not W5_C1c:
        SF2_reasons.append(
            "SF-2: No post-warning day with Encouragement content (10:32-39) — "
            "Encouragement move absent or mispositioned."
        )
    
    # Order violation: warning index must be between declaration and encouragement indices
    if W5_C1a and W5_C1b:
        decl_indices = [i for i, d in enumerate(W5["days"]) 
                        if semantic_contains_any(d["arg_advance_claim"],
                            ["10:1", "10:18", "once for all", "single offering"])]
        if decl_indices and warning_days_w5:
            if max(decl_indices) > min(warning_days_w5):
                SF2_triggered = True
                SF2_reasons.append(
                    "SF-2: Declaration days appear AFTER warning day — sequence inverted. "
                    "Check days[N].arg_advance_claim ordering vs days[M].day_subtype=='warning_beat'."
                )

    return SF2_triggered, SF2_reasons
```

**Fields used:** `days[N].day_subtype`, `days[N].arg_advance_claim`, `days[N].warning_position`

---

### SF-3: Escalating "better than" progression absent or inverted across any two consecutive weeks

```python
def detect_SF3(weeks: list) -> bool:
    """
    stakes_level must be strictly increasing W1 → W5.
    Additionally: week_to_week_bridge must introduce a premise that is 
    demonstrably more advanced (further in the argument) than the 
    prior week's week_opening_tension.
    """
    SF3_triggered = False
    SF3_reasons = []

    # Check 1: stakes_level strictly increasing
    for i in range(1, 5):  # weeks index 0-4
        if weeks[i]["stakes_level"] <= weeks[i-1]["stakes_level"]:
            SF3_triggered = True
            SF3_reasons.append(
                f"SF-3: W[{i+1}].stakes_level ({weeks[i]['stakes_level']}) "
                f"not greater than W[{i}].stakes_level ({weeks[i-1]['stakes_level']}). "
                f"Field: weeks[{i}].stakes_level"
            )

    # Check 2: week_to_week_bridge escalates across weeks
    # Bridge N must be semantically more advanced than Bridge N-1
    # Operationalized: bridge N+1 is downstream of bridge N
    for i in range(1, 4):  # W1→W2, W2→W3, W3→W4 bridges (W5 has none)
        if weeks[i]["week_to_week_bridge"] is not None and weeks[i-1]["week_to_week_bridge"] is not None:
            if not semantic_is_downstream(
                weeks[i]["week_to_week_bridge"],
                weeks[i-1]["week_to_week_bridge"]
            ):
                SF3_triggered = True
                SF3_reasons.append(
                    f"SF-3: W[{i+1}].week_to_week_bridge is not downstream of "
                    f"W[{i}].week_to_week_bridge — escalation inverted or flat. "
                    f"Fields: weeks[{i}].week_to_week_bridge, weeks[{i-1}].week_to_week_bridge"
                )

    return SF3_triggered, SF3_reasons
```

**Fields used:** `weeks[N].stakes_level`, `weeks[N].week_to_week_bridge`

---

### SF-4: Any warning passage absent from the week in which it textually appears

```python
# Ground truth map: which weeks must contain warning beats
REQUIRED_WARNING_WEEKS = {
    3: "mid_week",   # Heb 5:11-6:12
    5: "end_of_week" # Heb 10:26-31
}
# Note: W2 may contain warning-register content (Heb 3-4) but as arg_step, not warning_beat
# W4 does not contain a warning passage in Heb 8-9 — no warning_beat required

def detect_SF4(weeks: list) -> bool:
    SF4_triggered = False
    SF4_reasons = []

    for week_num, required_position in REQUIRED_WARNING_WEEKS.items():
        week = weeks[week_num - 1]  # 0-indexed
        warning_days = [d for d in week["days"] if d["day_subtype"] == "warning_beat"]
        
        if not warning_days:
            SF4_triggered = True
            SF4_reasons.append(
                f"SF-4: W{week_num} contains no warning_beat day. "
                f"Warning passage present in source text but absent from outline. "
                f"Field: weeks[{week_num-1}].days[N].day_subtype"
            )
        else:
            # Check warning_position matches required
            position_correct = all(d["warning_position"] == required_position 
                                   for d in warning_days)
            if not position_correct:
                SF4_reasons.append(
                    f"SF-4 (position mismatch): W{week_num} warning_beat days have "
                    f"warning_position != '{required_position}'. "
                    f"Field: weeks[{week_num-1}].days[N].warning_position"
                )
                # Position mismatch is HARD FAIL at checkpoint level but not SF-4 proper
                # SF-4 proper = absence; log separately

    return SF4_triggered, SF4_reasons
```

**Fields used:** `days[N].day_subtype`, `days[N].warning_position`

---

### SF-5: Logical antecedent sentence cannot be written for more than one day transition

```python
def detect_SF5(week: dict) -> bool:
    """
    SF-5 triggers when more than one day transition in a week has a missing, 
    empty, or generic logical_antecedent.
    Per-week: Day 2-5 must have non-empty, non-generic logical_antecedent.
    SF-5 = count of violations > 1.
    Single violation = HARD FAIL at per-week level (Stage 1).
    Multiple violations at arc level = SF-5.
    """
    days = week["days"]
    violations = []

    for i in range(1, len(days)):  # Day 2 through Day 5 (index 1-4)
        d = days[i]
        if d["logical_antecedent"] == "" or is_null(d["logical_antecedent"]) or is_generic(d["logical_antecedent"]):
            violations.append(
                f"SF-5: days[{i}].logical_antecedent is empty/null/generic. "
                f"Value: '{d['logical_antecedent']}'"
            )

    SF5_triggered = len(violations) > 1
    # Note: even 1 violation is a per-week HARD FAIL already.
    # At arc level, >1 indicates systemic failure, elevating to SF-5.
    return SF5_triggered, violations
```

**Fields used:** `days[N].logical_antecedent` (N=1..4, 0-indexed)

**`is_generic()` definition for implementation:**
```python
GENERIC_ANTECEDENT_PATTERNS = [
    "building on yesterday",
    "continuing our study",
    "as we have seen",
    "following from last time",
    "in our ongoing look at",
    "today we turn to",
    "next we consider",
]

def is_generic(text: str) -> bool:
    text_lower = text.lower().strip()
    if len(text_lower) < 20:
        return True
    for pattern in GENERIC_ANTECEDENT_PATTERNS:
        if pattern in text_lower:
            return True
    # Generic if it makes no specific claim about what was established
    if not semantic_contains_specific_premise(text_lower):
        return True
    return False
```

---

### SF-6: Week 5 functions primarily as setup for Hebrews 11 rather than conclusion

```python
def detect_SF6(W5: dict) -> bool:
    """
    SF-6 triggers on any of three conditions.
    """
    SF6_triggered = False
    SF6_reasons = []

    # Condition A: week_closing_location references Heb 11 content
    if semantic_contains_any(
        W5["week_closing_location"],
        ["Hebrews 11", "hall of faith", "cloud of witnesses", 
         "chapter 11", "faith heroes", "surrounded by witnesses"]
    ):
        SF6_triggered = True
        SF6_reasons.append(
            "SF-6: W5.week_closing_location references Hebrews 11 content. "
            "Field: weeks[4].week_closing_location"
        )

    # Condition B: Day 5 arg_advance_claim treats Heb 11 as primary forward move
    day5 = W5["days"][4]
    if semantic_primary_claim(
        day5["arg_advance_claim"],
        ["Hebrews 11", "hall of faith", "cloud of witnesses", 
         "what comes next", "leading into", "sets up"]
    ):
        SF6_triggered = True
        SF6_reasons.append(
            "SF-6: W5.days[4].arg_advance_claim primarily references Heb 11 forward. "
            "Field: weeks[4].days[4].arg_advance_claim"
        )

    # Condition C: week_to_week_bridge is NOT null (W5 must not bridge forward)
    if W5["week_to_week_bridge"] is not None:
        SF6_triggered = True
        SF6_reasons.append(
            "SF-6: W5.week_to_week_bridge is not null — volume not concluded. "
            "Field: weeks[4].week_to_week_bridge. Expected: null."
        )

    # Condition D: Any day's arg_advance_claim in W5 references Heb 11 characters 
    # as primary content (not incidental mention)
    for i, d in enumerate(W5["days"]):
        if semantic_primary_claim(
            d["arg_advance_claim"],
            ["Abel", "Enoch", "Noah", "Abraham", "Moses", 
             "hall of faith", "11:1", "chapter 11"]
        ):
            SF6_triggered = True
            SF6_reasons.append(
                f"SF-6: W5.days[{i}].arg_advance_claim primarily references "
                f"Heb 11 content. Field: weeks[4].days[{i}].arg_advance_claim"
            )

    return SF6_triggered, SF6_reasons
```

**Fields used:** `week_closing_location`, `week_to_week_bridge`, `days[N].arg_advance_claim`

---

## Part 3: SD Condition Detection

SD conditions produce flags, not hard fails. They feed the revision loop as revision-recommended, not revision-required.

---

### SD-1: Five-week arc does not escalate in stakes from Week 1 to Week 5

```python
def detect_SD1(weeks: list) -> tuple:
    """
    SD-1: stakes_level does not strictly escalate W1→W5.
    Note: SF-3 already catches strict inversions between consecutive weeks.
    SD-1 catches the overall arc — e.g., W1=2, W2=2, W3=3, W4=3, W5=4 
    (flat stretches even if never inverted).
    SD-1 is a FLAG, not hard fail.
    """
    stakes = [w["stakes_level"] for w in weeks]
    
    SD1_triggered = False
    SD1_reasons = []

    # Overall arc must show meaningful escalation
    if stakes[4] - stakes[0] < 2:
        SD1_triggered = True
        SD1_reasons.append(
            f"SD-1: Total stakes escalation from W1 ({stakes[0]}) to W5 ({stakes[4]}) "
            f"is less than 2 points. Arc is too flat. "
            f"Fields: weeks[0].stakes_level, weeks[4].stakes_level"
        )

    # Flat stretches: any two consecutive weeks with same stakes_level
    for i in range(1, 5):
        if stakes[i] == stakes[i-1]:
            SD1_reasons.append(
                f"SD-1 (flat): weeks[{i}].stakes_level == weeks[{i-1}].stakes_level "
                f"({stakes[i]}). "
                f"Fields: weeks[{i}].stakes_level, weeks[{i-1}].stakes_level"
            )
            SD1_triggered = True

    return SD1_triggered, SD1_reasons
```

**Fields used:** `weeks[N].stakes_level`

---

### SD-2: Warning passages structurally positioned as "application" rather than integrated argument

```python
def detect_SD2(weeks: list) -> tuple:
    """
    SD-2: Warning days are present (SF-4 not triggered) but positioned as 
    application rather than argument.
    Operationalized: 
    - warning_beat day has empty/generic logical_antecedent (already HARD FAIL, 
      but if somehow passed, SD-2 catches the structural intent)
    - warning_beat day's arg_advance_claim uses application language 
      rather than argument-advance language
    - No post-warning day's logical_antecedent references the warning content
      (warning treated as a standalone insert, not integrated)
    """
    SD2_triggered = False
    SD2_reasons = []

    APPLICATION_PATTERNS = [
        "applies to us", "in our lives", "what does this mean for",
        "practically speaking", "application", "how should we respond",
        "action step", "for us today"
    ]

    for w_idx, week in enumerate(weeks):
        warning_days = [(i, d) for i, d in enumerate(week["days"]) 
                        if d["day_subtype"] == "warning_beat"]
        
        for day_idx, wday in warning_days:
            # Check: arg_advance_claim uses application language
            if any(pat in wday["arg_advance_claim"].lower() for pat in APPLICATION_PATTERNS):
                SD2_triggered = True
                SD2_reasons.append(
                    f"SD-2: W{w_idx+1}.days[{day_idx}].arg_advance_claim uses "
                    f"application language on a warning_beat day. "
                    f"Field: weeks[{w_idx}].days[{day_idx}].arg_advance_claim"
                )

            # Check: Is the warning integrated? 
            # Post-warning days should reference it in logical_antecedent
            post_warning_days = [(i, d) for i, d in enumerate(week["days"]) 
                                 if i > day_idx]
            if post_warning_days:
                next_day_idx, next_day = post_warning_days[0]
                if not semantic_contains_upstream(
                    next_day["logical_antecedent"],
                    wday["arg_advance_claim"]
                ):
                    SD2_triggered = True
                    SD2_reasons.append(
                        f"SD-2: W{w_idx+1}.days[{next_day_idx}].logical_antecedent "
                        f"does not reference warning beat content — warning treated as "
                        f"disconnected insert. "
                        f"Fields: weeks[{w_idx}].days[{next_day_idx}].logical_antecedent, "
                        f"weeks[{w_idx}].days[{day_idx}].arg_advance_claim"
                    )

    return SD2_triggered, SD2_reasons
```

**Fields used:** `days[N].day_subtype`, `days[N].arg_advance_claim`, `days[N].logical_antecedent`

---

### SD-3: Forward references to Hall of Faith figures undercut Week 5's culmination

```python
def detect_SD3(weeks: list) -> tuple:
    """
    SD-3: Any day in W1-W4 makes forward reference to Heb 11 figures or 
    Hall of Faith as a primary content claim, undermining W5's culmination.
    Incidental mention is not SD-3. Primary claim is SD-3.
    """
    SD3_triggered = False
    SD3_reasons = []

    HOF_PATTERNS = [
        "hall of faith", "Hebrews 11", "chapter 11", "cloud of witnesses",
        "Abel", "Enoch", "Noah and his faith", "Abraham's faith in chapter",
        "we will see in Hebrews 11", "as we'll see next week"
    ]

    for w_idx in range(4):  # W1-W4 only
        week = weeks[w_idx]
        for d_idx, day in enumerate(week["days"]):
            for field in ["arg_advance_claim", "logical_antecedent"]:
                if semantic_primary_claim(day[field], HOF_PATTERNS):
                    SD3_triggered = True
                    SD3_reasons.append(
                        f"SD-3: W{w_idx+1}.days[{d_idx}].{field} makes primary "
                        f"reference to Heb 11 Hall of Faith content. "
                        f"Field: weeks[{w_idx}].days[{d_idx}].{field}"
                    )

        # Also check week_to_week_bridge forward-referencing Heb 11
        if week["week_to_week_bridge"] and semantic_primary_claim(
            week["week_to_week_bridge"], HOF_PATTERNS
        ):
            SD3_triggered = True
            SD3_reasons.append(
                f"SD-3: W{w_idx+1}.week_to_week_bridge primarily references Heb 11. "
                f"Field: weeks[{w_idx}].week_to_week_bridge"
            )

    return SD3_triggered, SD3_reasons
```

**Fields used:** `days[N].arg_advance_claim`, `days[N].logical_antecedent`, `weeks[N].week_to_week_bridge`

---

## Part 4: Verdict Logic

```python
def arc_coherence_verdict(weeks: list) -> dict:
    """
    Runs all arc coherence checks and returns structured verdict.
    Input: list of 5 WeekOutline dicts, weeks[0]-weeks[4]
    Output: verdict dict
    """

    hard_fails = []
    flags = []

    # --- Run checkpoint checks ---
    checkpoint_results = {
        "W1": run_W1_checks(weeks[0]),
        "W2": run_W2_checks(weeks[0], weeks[1]),
        "W3": run_W3_checks(weeks[1], weeks[2]),
        "W4": run_W4_checks(weeks[2], weeks[3]),
        "W5": run_W5_checks(weeks[3], weeks[4]),
    }

    for wk, result in checkpoint_results.items():
        for check_id, triggered, severity in result["flags"]:
            if severity == "HARD_FAIL" and triggered:
                hard_fails.append({
                    "source": f"checkpoint_{wk}",
                    "check": check_id,
                    "severity": "HARD_FAIL"
                })
            elif severity == "FLAG" and triggered:
                flags.append({
                    "source": f"checkpoint_{wk}",
                    "check": check_id,
                    "severity": "FLAG"
                })

    # --- Run SF checks ---
    sf_checks = [
        ("SF-1", [detect_SF1(w) for w in weeks]),  # Per-week
        ("SF-2", [detect_SF2(weeks[4])]),            # W5 only
        ("SF-3", [detect_SF3(weeks)]),               # Cross-week
        ("SF-4", [detect_SF4(weeks)]),               # Cross-week
        ("SF-5", [detect_SF5(w) for w in weeks]),   # Per-week
        ("SF-6", [detect_SF6(weeks[4])]),            # W5 only
    ]

    for sf_id, results in sf_checks:
        for triggered, reasons in results:
            if triggered:
                hard_fails.append({
                    "source": sf_id,
                    "reasons": reasons,
                    "severity": "HARD_FAIL"
                })

    # --- Run SD checks ---
    sd_checks = [
        ("SD-1", detect_SD1(weeks)),
        ("SD-2", detect_SD2(weeks)),
        ("SD-3", detect_SD3(weeks)),
    ]

    for sd_id, (triggered, reasons) in sd_checks:
        if triggered:
            flags.append({
                "source": sd_id,
                "reasons": reasons,
                "severity": "FLAG"
            })

    # --- Verdict determination ---
    """
    FAIL:   Any hard_fail present
    REVISE: No hard_fail, but ≥1 flag present
    PASS:   No hard_fail, no flags
    """
    if hard_fails:
        verdict = "FAIL"
    elif flags:
        verdict = "REVISE"
    else:
        verdict = "PASS"

    return {
        "verdict": verdict,
        "hard_fails": hard_fails,
        "flags": flags,
        "hard_fail_count": len(hard_fails),
        "flag_count": len(flags),
        "checkpoint_results": checkpoint_results,
    }
```

### Verdict Decision Table

| Condition | Verdict |
|---|---|
| Any HARD_FAIL (checkpoint or SF) | `FAIL` — no regeneration prompt, structured error returned immediately |
| Zero HARD_FAIL, ≥1 FLAG (SD or checkpoint flag-tier) | `REVISE` — revision loop initiated, fields specified |
| Zero HARD_FAIL, zero FLAG | `PASS` — arc coherence confirmed, proceed to exposition |

**Hard fails do not stack into revision.** A single SF or checkpoint HARD_FAIL returns `FAIL` immediately. The revision loop is only for `REVISE` verdicts.

---

## Part 5: Revision Loop Design

When verdict is `REVISE`, the following procedure identifies exactly which fields to regenerate and in what order. When verdict is `FAIL`, the same field mapping is returned as structured error data for the Outliner to receive as regeneration input.

---

### Revision Target Map

For each failure condition, the revision loop specifies: which week, which fields, and what constraint the regenerated content must satisfy.

```python
REVISION_TARGET_MAP = {

    # Checkpoint W1 failures
    "W1_C2": {
        "week": 1,
        "fields": ["week_closing_location"],
        "constraint": "Must not be semantically equivalent to week_opening_tension. "
                      "Must reference incarnation/identification/necessity cluster.",
        "may_cascade_to": []
    },
    "W1_C3": {
        "week": 1,
        "fields": ["week_closing_location", "days[4].arg_advance_claim"],
        "constraint": "week_closing_location must reference incarnation, identification, "
                      "or humanity of Son. days[4].arg_advance_claim must not restate "
                      "opening exaltation claim as primary move.",
        "may_cascade_to": ["W2_C2"]  # W1 closing feeds W2 bridge
    },
    "W1_C4": {
        "week": 1,
        "fields": ["days[4].arg_advance_claim"],
        "constraint": "Day 5 arg_advance_claim must be semantically distinct from "
                      "days[0].arg_advance_claim. No restatement of Day 1 claim.",
        "may_cascade_to": []
    },

    # Checkpoint W2 failures
    "W2_C2": {
        "week": 1,
        "fields": ["week_to_week_bridge"],
        "constraint": "W1.week_to_week_bridge must be upstream premise of "
                      "W2.week_opening_tension. Regenerate W1 bridge to feed W2 open.",
        "may_cascade_to": []
    },
    "W2_C3": {
        "week": 2,
        "fields": ["week_closing_location", "days[4].arg_advance_claim"],
        "constraint": "Week 2 must close on open invitation (4:14-16), not resolution. "
                      "week_closing_location must contain throne of grace / approach cluster. "
                      "Must not contain resolved/settled/concluded language.",
        "may_cascade_to": ["W3_C7"]
    },
    "W2_C5": {
        "week": 2,
        "fields": ["week_closing_location"],
        "constraint": "week_closing_location must not be semantically equivalent to "
                      "week_opening_tension. Arc movement required.",
        "may_cascade_to": []
    },

    # Checkpoint W3 failures
    "W3_C1": {
        "week": 3,
        "fields": ["days — full regeneration required"],
        "constraint": "W3 must contain at least one day with day_subtype='warning_beat'. "
                      "Hebrews 5:11-6:12 is present in W3 source text. SF-4 triggered.",
        "may_cascade_to": ["W3_C2", "W3_C3", "W3_C4", "W3_C5"]
    },
    "W3_C2": {
        "week": 3,
        "fields": ["days[N].warning_position for all warning_beat days"],
        "constraint": "warning_position must be 'mid_week' for all W3 warning_beat days.",
        "may_cascade_to": []
    },
    "W3_C3": {
        "week": 3,
        "fields": [
            "days[N].arg_advance_claim for pre-warning arg_step days",
            "days[N].arg_advance_claim for post-warning arg_step days"
        ],
        "constraint": "Pre-warning arg_step days: arg_advance_claim must reference "
                      "suffering/qualification cluster (5:1-10). "
                      "Post-warning arg_step days: arg_advance_claim must reference "
                      "Melchizedek/eternal priesthood cluster (7:1ff). "
                      "Sequence Move1→Move2→Move3 is non-negotiable.",
        "may_cascade_to": []
    },
    "W3_C4": {
        "week": 3,
        "fields": ["days[first_post_warning_idx].logical_antecedent"],
        "constraint": "First post-warning arg_step day's logical_antecedent must reference "
                      "warning content (5:11-6:12 / maturity / danger). "
                      "Cannot jump from 5:10 to 7:1 without antecedent through the warning.",
        "may_cascade_to": []
    },
    "W3_C5": {
        "week": 3,
        "fields": ["days[N].logical_antecedent for all warning_beat days"],
        "constraint": "Warning day logical_antecedent must be non-empty, non-generic, "
                      "and reference suffering/qualification content from prior days. "
                      "Full antecedent enforcement applies — same as any arg_step day.",
        "may_cascade_to": []
    },
    "W3_C6": {
        "week": 3,
        "fields": ["week_closing_location"],
        "constraint": "W3 must close on eternal priesthood/Melchizedek (7:1ff). "
                      "week_closing_location must reference Melchizedek or eternal priesthood.",
        "may_cascade_to": ["W4_C5"]
    },

    # Checkpoint W4 failures
    "W4_C1": {
        "week": 4,
        "fields": [
            "days[N].arg_advance_claim for early arg_step days",
            "days[N].arg_advance_claim for mid arg_step days",
            "days[N].arg_advance_claim for late arg_step days"
        ],
        "constraint": "Early days: covenant/8: cluster. Mid days: tabernacle/sanctuary/9:1-11 "
                      "cluster. Late days: sacrifice/blood/9:24-28 cluster. "
                      "Sequence is non-negotiable.",
        "may_cascade_to": []
    },
    "W4_C2": {
        "week": 4,
        "fields": ["days[4].arg_advance_claim"],
        "constraint": "Day 5 must land on 9:24-28 / single sacrifice sufficiency. "
                      "arg_advance_claim must reference ephapax / once for all / offered once.",
        "may_cascade_to": ["W4_C3", "W4_C4"]
    },
    "W4_C4": {
        "week": 4,
        "fields": ["week_to_week_bridge"],
        "constraint": "W4.week_to_week_bridge must reference completed sacrifice as premise "
                      "for W5. Must contain sufficient/once/9:28/ground/basis cluster. "
                      "This is the bridge that makes W5 Declaration (10:1-18) possible.",
        "may_cascade_to": ["W5_C5"]
    },
    "W4_C6": {
        "week": 4,
        "fields": ["days[N].arg_step_index for all arg_step days"],
        "constraint": "arg_step_index must be strictly increasing, no duplicates, "
                      "no gaps that would indicate missing steps. "
                      "Regenerate all arg_step_index values in W4.",
        "may_cascade_to": []
    },

    # Checkpoint W5 failures
    "W5_C1": {
        "week": 5,
        "fields": ["days — full regeneration required"],
        "constraint": "W5 must contain all three moves in order: "
                      "(1) Declaration days (10:1-18) before warning, "
                      "(2) at least one warning_beat day (10:26-31), "
                      "(3) Encouragement days (10:32-39) after warning. "
                      "SF-2 triggered if any move absent or order violated.",
        "may_cascade_to": []
    },
    "W5_C2": {
        "week": 5,
        "fields": ["days[N].warning_position for all warning_beat days in W5"],
        "constraint": "warning_position must be 'end_of_week' for all W5 warning_beat days. "
                      "Note: end_of_week means after Declaration, before Encouragement — "
                      "not necessarily the literal last day.",
        "may_cascade_to": []
    },
    "W5_C3": {
        "week": 5,
        "fields": ["week_closing_location"],
        "constraint": "Must reference 10:39 / do not shrink back / live by faith / "
                      "perseverance / ground of assurance. "
                      "Must NOT reference Hebrews 11 / hall of faith / cloud of witnesses. "
                      "SF-6 triggered if Heb 11 content is primary.",
        "may_cascade_to": []
    },
    "W5_C4": {
        "week": 5,
        "fields": ["week_to_week_bridge"],
        "constraint": "W5.week_to_week_bridge must be null. "
                      "Volume concludes at Hebrews 1-10. No forward bridge. "
                      "SF-6 triggered if non-null.",
        "may_cascade_to": []
    },
    "W5_C6": {
        "week": 5,
        "fields": ["days[4].arg_advance_claim"],
        "constraint": "Day 5 must not primarily reference Hebrews 11 content. "
                      "arg_advance_claim must close the Heb 1-10 arc, not open Heb 11. "
                      "SF-6 triggered if Heb 11 is primary claim.",
        "may_cascade_to": []
    },

    # SF conditions — all require full week regeneration
    "SF-1": {
        "week": "see reason field for specific week",
        "fields": [
            "days[N].arg_advance_claim for interchangeable days",
            "days[N].logical_antecedent for detached days"
        ],
        "constraint": "Every argument_step day must advance a claim not present in any "
                      "other day. Every day N+1 must have logical_antecedent that references "
                      "day N arg_advance_claim specifically.",
        "may_cascade_to": []
    },
    "SF-3": {
        "week": "all weeks — stakes_level cascade",
        "fields": ["weeks[N].stakes_level for all weeks where escalation fails"],
        "constraint": "stakes_level must be strictly increasing W1→W5. "
                      "Also: week_to_week_bridge must escalate in argument-advance. "
                      "Regenerate stakes_level for affected weeks.",
        "may_cascade_to": ["SD-1"]
    },
    "SF-4": {
        "week": "W3 and/or W5",
        "fields": [
            "W3: days — full regeneration, warning_beat day must be present",
            "W5: days — full regeneration, warning_beat day must be present"
        ],
        "constraint": "Warning passage must appear as warning_beat day in the week "
                      "where it textually occurs. Not optional. Not routeable around.",
        "may_cascade_to": ["W3_C1", "W5_C1"]
    },
    "SF-5": {
        "week": "see reason field for specific week",
        "fields": ["days[N].logical_antecedent for all failing days"],
        "constraint": "Every day 2-5 must have non-empty, non-generic logical_antecedent. "
                      "Format: 'Because we established [specific claim from Day N], "
                      "today we address [specific new ground].' "
                      "Generic phrases ('building on yesterday') are hard fails.",
        "may_cascade_to": []
    },
    "SF-6": {
        "week": 5,
        "fields": [
            "week_closing_location",
            "week_to_week_bridge",
            "days[4].arg_advance_claim",
            "days[N].arg_advance_claim for any day referencing Heb 11"
        ],
        "constraint": "W5 must conclude Hebrews 1-10. No Hebrews 11 content as primary "
                      "claim anywhere in W5. week_to_week_bridge must be null.",
        "may_cascade_to": []
    },

    # SD conditions — revision recommended, not required
    "SD-1": {
        "week": "all weeks",
        "fields": ["weeks[N].stakes_level"],
        "constraint": "Revise stakes_level to achieve strict escalation W1→W5 "
                      "with total spread ≥ 2 points. No flat consecutive weeks.",
        "severity": "REVISION_RECOMMENDED"
    },
    "SD-2": {
        "week": "W3
