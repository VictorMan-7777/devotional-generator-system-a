from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path


def _local_now() -> str:
    return datetime.now().strftime("%Y-%m-%d %I:%M:%S %p %Z")


def _append_log(active_log: Path, message: str) -> None:
    active_log.parent.mkdir(parents=True, exist_ok=True)
    with active_log.open("a", encoding="utf-8") as handle:
        handle.write(f"[{_local_now()}] {message}\n")


def _run_supervisor(repo_root: Path) -> dict[str, object]:
    script_path = repo_root / "scripts" / "autoresearch" / "run_training_supervisor.py"
    started_at = time.time()
    result = subprocess.run(
        [str(repo_root / ".venv" / "bin" / "python"), str(script_path)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    duration_seconds = round(time.time() - started_at, 2)
    payload: dict[str, object] = {
        "returncode": result.returncode,
        "duration_seconds": duration_seconds,
        "stdout_tail": result.stdout[-4000:],
        "stderr_tail": result.stderr[-4000:],
    }
    try:
        parsed = json.loads(result.stdout)
        if isinstance(parsed, dict):
            payload["supervisor_output"] = parsed
    except Exception:
        pass
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run DevG training cycles continuously.")
    parser.add_argument("--interval-seconds", type=int, default=30, help="Pause between supervisor cycles.")
    parser.add_argument("--max-cycles", type=int, default=0, help="Optional cap for smoke runs; 0 means run forever.")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    active_log = Path("/tmp/devg-active.log")
    cycle = 0

    _append_log(active_log, f"START training_loop interval={args.interval_seconds}s max_cycles={args.max_cycles or 'infinite'}")
    try:
        while True:
            cycle += 1
            _append_log(active_log, f"START supervisor_cycle #{cycle}")
            payload = _run_supervisor(repo_root)
            returncode = int(payload["returncode"])
            duration = payload["duration_seconds"]
            _append_log(
                active_log,
                f"END supervisor_cycle #{cycle} returncode={returncode} duration={duration}s",
            )
            if returncode != 0:
                stderr_tail = str(payload.get("stderr_tail") or "").strip()
                if stderr_tail:
                    _append_log(active_log, f"supervisor_cycle #{cycle} stderr_tail={stderr_tail[-500:]}")
            if args.max_cycles and cycle >= args.max_cycles:
                break
            time.sleep(max(args.interval_seconds, 1))
    except KeyboardInterrupt:
        _append_log(active_log, "STOP training_loop interrupted")
        return 130

    _append_log(active_log, f"STOP training_loop completed cycles={cycle}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
