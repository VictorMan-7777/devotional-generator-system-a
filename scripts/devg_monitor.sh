#!/usr/bin/env bash
# devg_monitor.sh — Zero-cost system monitor. No Claude. No LLM calls.
# Writes status to STATUS_FILE every run. View with: cat /tmp/devg_status.txt
#
# Run manually:  bash scripts/devg_monitor.sh
# Install cron:  crontab -e  →  */15 * * * * /path/to/scripts/devg_monitor.sh

set -uo pipefail
trap '' PIPE

REPO="/Volumes/claude-projects/projects/devotional-generator-system-a"
OUTPUTS="$REPO/docs/system/outputs"
DB="$REPO/registry.db"
STATUS_FILE="/tmp/devg_status.txt"
ALERT_FILE="/tmp/devg_alert.txt"
GROK_ALERT_FILE="$REPO/grok_workspace/notifications/system_alerts.md"
GROK_HEALTH="http://localhost:8001/health"

NOW=$(date '+%a %b %-d %H:%M %Z')
NOW_EPOCH=$(date +%s)

# ── helpers ──────────────────────────────────────────────────────────────────

newest() { ls -t "$OUTPUTS"/$1 2>/dev/null | head -1; }
age_min() { echo $(( ($NOW_EPOCH - $(stat -f %m "$1" 2>/dev/null || echo $NOW_EPOCH)) / 60 )); }

# Convert a UTC filename timestamp (2026-03-21__184649) to local 24hr time (18:46 EDT)
utc_fname_to_local() {
  python3 -c "
from datetime import datetime, timezone
s='$1'[:16].replace('__','T').replace('-','')
try:
    dt=datetime.strptime(s,'%Y%m%dT%H%M').replace(tzinfo=timezone.utc)
    print(dt.astimezone().strftime('%H:%M %Z'))
except Exception:
    print('$1'[:16])
" 2>/dev/null || echo "$1"
}

# Convert an ISO timestamp string to local 24hr display.
# If it has explicit tz (Z or +offset) treat as UTC; if bare, treat as local already.
iso_to_local_display() {
  python3 -c "
from datetime import datetime, timezone
s='$1'
try:
    if s.endswith('Z') or '+' in s[10:]:
        dt=datetime.fromisoformat(s.replace('Z','+00:00')).astimezone()
    else:
        dt=datetime.fromisoformat(s)  # already local, naive
    tz=datetime.now().astimezone().strftime('%Z')
    print(dt.strftime('%a %H:%M ')+tz)
except Exception:
    print(s)
" 2>/dev/null || echo "$1"
}

# Return minutes since an ISO timestamp. Same tz logic as above.
iso_age_min() {
  python3 -c "
from datetime import datetime, timezone
s='$1'
try:
    if s.endswith('Z') or '+' in s[10:]:
        dt=datetime.fromisoformat(s.replace('Z','+00:00'))
        now=datetime.now(timezone.utc)
    else:
        dt=datetime.fromisoformat(s)
        now=datetime.now()
    print(int((now-dt).total_seconds()//60))
except Exception:
    print(9999)
" 2>/dev/null || echo "9999"
}

# ── gather data ───────────────────────────────────────────────────────────────

# Grok health
GROK_STATUS=$(curl -s --max-time 3 "$GROK_HEALTH" 2>/dev/null | \
  python3 -c "
import sys,json
d=json.load(sys.stdin)
ctx=d.get('context',{})
perf=ctx.get('performance',{})
model=ctx.get('model','?')
msgs=ctx.get('messages','?')
interv=perf.get('interventions','?')
pending=ctx.get('pending_injections','?')
print(f'{model} msgs={msgs} pending={pending} interventions={interv}')
" 2>/dev/null || echo "UNREACHABLE")

# Supervisor cycle
SUP_FILE=$(newest "*training-supervisor-cycle.json")
SUP_TS="none"
SUP_AGE_MIN=9999
if [ -n "$SUP_FILE" ]; then
  SUP_TS=$(utc_fname_to_local "$(basename "$SUP_FILE")")
  SUP_AGE_MIN=$(age_min "$SUP_FILE")
fi

# Outliner cycle (newest 3 for no_assignments check)
OUT_FILES=$(ls -t "$OUTPUTS"/*outliner-training-cycle.json 2>/dev/null | head -3)
OUT_FILE=$(echo "$OUT_FILES" | head -1)
OUT_TS="none"; OUT_STATUS="?"; OUT_PASSAGE="?"; OUT_SCORE="?"; OUT_AGE_MIN=9999
if [ -n "$OUT_FILE" ]; then
  OUT_TS=$(utc_fname_to_local "$(basename "$OUT_FILE")")
  OUT_AGE_MIN=$(age_min "$OUT_FILE")
  OUT_STATUS=$(python3 -c "import json; d=json.load(open('$OUT_FILE')); print(d.get('status','?'))" 2>/dev/null || echo "?")
  OUT_PASSAGE=$(python3 -c "
import json; d=json.load(open('$OUT_FILE'))
r=(d.get('results') or [{}])[0]
print(r.get('assignment',{}).get('passage','?') if r else '?')
" 2>/dev/null || echo "?")
  OUT_SCORE=$(python3 -c "
import json; d=json.load(open('$OUT_FILE'))
r=(d.get('results') or [{}])[0]
tr=(r.get('initial_attempt',{}) or {}).get('trainer_review',{}) or {}
print(tr.get('combined_score','?'))
" 2>/dev/null || echo "?")
fi

# no_assignments check across 3 newest
NO_ASSIGN_COUNT=0
for f in $OUT_FILES; do
  val=$(python3 -c "import json; d=json.load(open('$f')); print(d.get('no_assignments') or d.get('status',''))" 2>/dev/null || echo "")
  if [[ "$val" == "True" ]] || [[ "$val" == "no_assignments" ]]; then
    NO_ASSIGN_COUNT=$((NO_ASSIGN_COUNT+1))
  fi
done

# Generic worker stats script: args = db worker_name grad_threshold(0=none)
# Output: total passes streak gate_trend (last field absorbs spaces)
_STAT_TMP=$(mktemp /tmp/devg_stat_XXXX)
cat > "$_STAT_TMP" << 'PYEOF'
import sqlite3, sys
db, worker = sys.argv[1], sys.argv[2]
grad = int(sys.argv[3]) if len(sys.argv) > 3 else 0
try:
    con = sqlite3.connect(db, timeout=5)
    statuses = [s for (s,) in con.execute(
        "SELECT status FROM autoresearch_experiments WHERE worker_name=? ORDER BY completed_at_utc ASC",
        (worker,)
    ).fetchall()]
    total = len(statuses)
    passes = sum(1 for s in statuses if s == 'pass')
    streak = 0
    for s in reversed(statuses):
        if s == 'assigned':
            continue  # skip in-flight experiments
        if s in ('pass', 'completed'):
            streak += 1
        else:
            break
    streak_str = f'{streak}/{grad}' if grad else str(streak)
    backlog = con.execute("""
        SELECT COUNT(*) FROM autoresearch_experiments
        WHERE worker_name=? AND status='assigned'
        AND CAST(STRFTIME('%s', REPLACE(REPLACE(created_at_utc,'T',' '),'Z','')) AS INTEGER)
            >= CAST(STRFTIME('%s','now','-2 hours') AS INTEGER)
    """, (worker,)).fetchone()[0]
    W = 50
    cg = (total // W) * W
    def rate(start, end):
        if start < 0 or end > total or start >= end: return None
        w = statuses[start:end]
        return round(sum(1 for s in w if s == 'pass') / len(w) * 100)
    cp = rate(cg - W, cg)
    pp = rate(cg - W*2, cg - W)
    if cp is not None and pp is not None:
        arrow = '+' if cp > pp else ('-' if cp < pp else '=')
        trend = f'{pp}% -> {cp}% {arrow}'
    elif cp is not None:
        trend = f'{cp}%'
    else:
        trend = '?'
    print(total, passes, streak_str, backlog, trend)
except Exception:
    print('ERR ? ? 0 ?')
PYEOF

# Outliner stats
read -r EXP_COUNT EXP_PASS EXP_STREAK EXP_BACKLOG EXP_GATE < <(python3 "$_STAT_TMP" "$DB" outliner 100 2>/dev/null || echo "ERR ? ? 0 ?")

# Stall file
STALL_FILE=$(newest "*stall*.json")
STALL_AGE_MIN=9999
STALL_NAME="none"
if [ -n "$STALL_FILE" ]; then
  STALL_NAME=$(basename "$STALL_FILE")
  STALL_AGE_MIN=$(age_min "$STALL_FILE")
fi

# Downstream: fresh score + experiment stats
# DB worker names: replace hyphens with underscores, append _writer
DOWNSTREAM_LINES=""
for worker in exposition be-still action prayer; do
  f=$(newest "*${worker}-*training-cycle.json")
  score="?"
  if [ -n "$f" ]; then
    score=$(python3 -c "
import json; d=json.load(open('$f'))
fb=d.get('fresh_benchmark',{}) or {}
print((fb.get('evaluation',{}) or {}).get('score','?'))
" 2>/dev/null || echo "?")
  fi
  db_worker="${worker//-/_}_writer"
  read -r W_TOTAL W_PASS W_STREAK W_BACKLOG W_GATE < <(python3 "$_STAT_TMP" "$DB" "$db_worker" 2>/dev/null || echo "? ? ? 0 ?")
  W_FLAG=""
  [ "${W_BACKLOG:-0}" -gt 10 ] 2>/dev/null && W_FLAG=" !"
  W_AGE_MIN=9999
  [ -n "$f" ] && W_AGE_MIN=$(age_min "$f")
  W_PFX="  "
  if [ "${W_AGE_MIN:-9999}" -gt 30 ] 2>/dev/null; then
    W_FLAG=" [IDLE ${W_AGE_MIN}m]"
    W_PFX="  !!"
  fi
  DOWNSTREAM_LINES="${DOWNSTREAM_LINES}${W_PFX} ${worker}=${score}${W_FLAG}
    ${W_TOTAL} total, ${W_PASS} pass | streak ${W_STREAK} | ${W_GATE}

"
done
rm -f "$_STAT_TMP"

# Grok chat_log recency
CHAT_LOG="$REPO/grok_workspace/chat_log.jsonl"
GROK_LAST_TS="none"
GROK_LAST_RAW=""
GROK_IDLE_MIN=9999
if [ -f "$CHAT_LOG" ]; then
  GROK_LAST_RAW=$(tail -1 "$CHAT_LOG" | python3 -c "
import sys,json
line=sys.stdin.read().strip()
if line:
    d=json.loads(line)
    print(d.get('timestamp','?')[:19])
" 2>/dev/null || echo "")
  if [ -n "$GROK_LAST_RAW" ]; then
    GROK_LAST_TS=$(iso_to_local_display "$GROK_LAST_RAW")
    GROK_IDLE_MIN=$(iso_age_min "$GROK_LAST_RAW")
  fi
fi

# ── alerts ────────────────────────────────────────────────────────────────────

ALERTS=()

[ "$NO_ASSIGN_COUNT" -ge 3 ] && ALERTS+=("OUTLINER NO_ASSIGNMENTS x${NO_ASSIGN_COUNT}")
[ "$OUT_AGE_MIN" -gt 60 ] && ALERTS+=("OUTLINER IDLE: no cycle in ${OUT_AGE_MIN}min (last: ${OUT_TS})")
[ "$STALL_AGE_MIN" -lt 30 ] && ALERTS+=("STALL FILE RECENT: ${STALL_NAME} (${STALL_AGE_MIN}min)")
[ "$SUP_AGE_MIN" -gt 90 ] && ALERTS+=("SUPERVISOR STALE: last run ${SUP_AGE_MIN}min ago")
[ "$GROK_STATUS" = "UNREACHABLE" ] && ALERTS+=("GROK HEALTH UNREACHABLE")
[ "$GROK_IDLE_MIN" -gt 30 ] && ALERTS+=("GROK IDLE: last active ${GROK_IDLE_MIN}min ago (${GROK_LAST_TS})")

# ── write status ──────────────────────────────────────────────────────────────

{
  echo "=============================="
  echo "DevG Monitor — $NOW"
  echo "=============================="
  echo ""
  echo "OUTLINER"
  _OUT_FLAG=""
  [ "${EXP_BACKLOG:-0}" -gt 10 ] 2>/dev/null && _OUT_FLAG=" !"
  echo "  experiments : $EXP_COUNT total, $EXP_PASS pass | streak $EXP_STREAK | $EXP_GATE${_OUT_FLAG}"
  echo "  last cycle  : $OUT_TS | status=$OUT_STATUS | $OUT_PASSAGE | score=$OUT_SCORE"
  echo "  no_assign   : $NO_ASSIGN_COUNT/3 recent cycles"
  echo ""
  echo "SUPERVISOR"
  echo "  last cycle  : $SUP_TS (${SUP_AGE_MIN}min ago)"
  echo ""
  echo "DOWNSTREAM"
  echo "$DOWNSTREAM_LINES"
  echo ""
  echo "STALL"
  echo "  newest      : $STALL_NAME (${STALL_AGE_MIN}min ago)"
  echo ""
  echo "GROK"
  echo "  health      : $GROK_STATUS"
  echo "  last active : $GROK_LAST_TS (${GROK_IDLE_MIN}min ago)"
  echo ""
  if [ ${#ALERTS[@]} -gt 0 ]; then
    echo "🚨 ALERTS"
    for a in "${ALERTS[@]}"; do echo "  !! $a"; done
  else
    echo "✅ NO ALERTS"
  fi
  echo ""
  echo "=============================="
} > "$STATUS_FILE"

# Write alert file separately (empty = all clear)
if [ ${#ALERTS[@]} -gt 0 ]; then
  printf '%s\n' "${ALERTS[@]}" > "$ALERT_FILE"
  # macOS notification (only if running interactively / GUI session)
  osascript -e "display notification \"${ALERTS[0]}\" with title \"DevG Alert\"" 2>/dev/null || true
  # Write to Grok notifications dir so Grok sees active alerts
  {
    echo "# System Alerts — $NOW"
    echo ""
    printf '%s\n' "${ALERTS[@]}"
    echo ""
    echo "## System Snapshot"
    echo "- supervisor_age_min: $SUP_AGE_MIN"
    echo "- outliner: $EXP_COUNT total, $EXP_PASS pass | streak $EXP_STREAK | $EXP_GATE"
    echo "- outliner_last_cycle_min: $OUT_AGE_MIN"
    echo "- no_assign_recent: $NO_ASSIGN_COUNT/3"
    echo "- downstream:"
    echo "$DOWNSTREAM_LINES"
    echo "- grok_health: $GROK_STATUS"
    echo "- grok_idle_min: $GROK_IDLE_MIN"
  } > "$GROK_ALERT_FILE"
else
  echo "" > "$ALERT_FILE"
  # Clear Grok alert file when all clear
  echo "# No Alerts — $NOW" > "$GROK_ALERT_FILE"
fi

cat "$STATUS_FILE"
