REJECTED: archive_stale.py v1 — NameError, not run.

Line 24: `completed_at_utc=datetime.now(timezone.utc)...`
`datetime` and `timezone` are not imported in the script. Add the import.

Note: log_experiment in store.py overrides completed_at_utc with _utc_now() regardless of what you pass, so that argument is optional. Either add the import or drop the completed_at_utc argument from the call — both work.

Resubmit v2.
