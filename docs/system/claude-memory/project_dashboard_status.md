---
name: Dashboard status
description: devg_web_monitor.py is broken; redesign spec written; dashboard rebuild assigned to Grok
type: project
---

`scripts/devg_web_monitor.py` is down. Hangs in uninterruptible I/O (UN state) because it globs `docs/system/outputs/` (~5000+ files) over SMB on every refresh.

**Why:** Design didn't hold at scale — worked at launch but outputs directory grew indefinitely.

**Redesign spec:** `grok_workspace/notifications/dashboard_redesign_directive.md` — full operator-written spec.

Key constraints:
- New Grok supervisor (`run_grok_supervisor.py`) does NOT write JSON to `docs/system/outputs/` — old monitor's data source is gone
- Redesign requires: `supervisor_cycles` DB table, Grok supervisor writes summary row each cycle, monitor reads from DB with zero filesystem globs

**Status:** Assigned to Grok via chat.md 2026-03-25. He has proposals to write.

**How to apply:** Operator wants dashboard working before next check-in. When Grok's proposals arrive, review and apply promptly — this is a visibility blocker for the operator.
