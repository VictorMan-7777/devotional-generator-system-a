## PROPOSAL READY: dashboard_v4.py (2026-03-27T07:35 UTC)

**Issue**: Dashboard v4 marked URGENT in grok_workspace/TODO.md line 9. Prior dashboards (devg_web_monitor.py, web_monitor_v2/3.py) hang on SMB globs or stubbed. No live visibility: DB shows 198 assigned experiments stalled; exposition_writer 24 passes in 2018 completed (1.2% rate); outliner 137/940 (14.6%).

**DB Evidence** (live queries pasted in proposals/dashboard_v4.md).

**Files**:
- grok_workspace/proposals/dashboard_v4.py (complete runnable HTML generator, stdlib-only)
- grok_workspace/proposals/dashboard_v4.md (evidence + spec)

**Apply**:
```
cd project_root  # e.g., /path/to/devg
python grok_workspace/proposals/dashboard_v4.py > docs/system/outputs/dashboard_v4.html
python -m http.server 8080 --directory docs/system/outputs/  # optional serve
```

Clears sole URGENT. Stop. Claude applies.