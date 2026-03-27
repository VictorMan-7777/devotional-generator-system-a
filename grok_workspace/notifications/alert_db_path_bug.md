# Bug: check_worker_alerts() queries the wrong database

The `check_worker_alerts()` function in `src/autoresearch/store.py` uses `default_registry_db_path()` to find the database. That resolves to the app support path, not the runtime database the supervisor actually writes to.

The runtime database is set via `DEVG_DB_PATH` in `.env.local` and resolves to `registry.db` in the project root. `check_worker_alerts()` needs to respect that same path resolution — the same logic that `build_autoresearch_socket()` uses.

Fix this so the alert function queries the correct database. Submit a complete proposal.
