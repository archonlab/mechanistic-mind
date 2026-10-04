"""Supervisor liveness and Analyzer job instance ownership.

Never treats a busy port as ownership. Never kills a PID from a name or port alone.
"""
from __future__ import annotations

import json
import os
import signal
import threading
import time
from pathlib import Path
from typing import Any

from .instance_lifecycle import linux_pdeathsig_preexec, pid_matches_record, pid_starttime

ENV_SUPERVISOR_PID = "PSY_OBSERVER_SUPERVISOR_PID"
ENV_SUPERVISOR_STARTTIME = "PSY_OBSERVER_SUPERVISOR_STARTTIME"
INTERRUPTED_BY_APPLICATION_EXIT = "INTERRUPTED_BY_APPLICATION_EXIT"
NONTERMINAL_JOB_STATES = {
    "RUNNING",
    "CANCEL_REQUESTED",
    "QUEUED",
    "WORKING",
    "LOAD_AND_VALIDATE",
    "BUILD_TICK_STORIES",
    "BUILD_SUMMARIES",
    "RENDER_EXPORT_PAYLOADS",
    "AGGREGATING",
}
TERMINAL_JOB_STATES = {
    "COMPLETED",
    "COMPLETE",
    "FAILED",
    "CANCELLED",
    INTERRUPTED_BY_APPLICATION_EXIT,
}

_WATCHDOG_STARTED = False


def current_instance_owner() -> dict[str, Any]:
    pid = os.getpid()
    return {
        "owner_instance_id": os.environ.get("PSY_OBSERVER_INSTANCE_ID"),
        "owner_package_identity": os.environ.get("PSY_OBSERVER_PACKAGE_IDENTITY"),
        "owner_backend_pid": pid,
        "owner_backend_starttime": pid_starttime(pid),
        "owner_supervisor_pid": _env_int(ENV_SUPERVISOR_PID),
        "owner_supervisor_starttime": os.environ.get(ENV_SUPERVISOR_STARTTIME),
    }


def _env_int(name: str) -> int | None:
    raw = os.environ.get(name)
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def supervisor_is_alive() -> bool:
    pid = _env_int(ENV_SUPERVISOR_PID)
    start = os.environ.get(ENV_SUPERVISOR_STARTTIME)
    if pid is None or not start:
        # No supervisor contract (TestClient / ad-hoc uvicorn): do not self-terminate.
        return True
    return pid_matches_record(pid, starttime=start)


def start_supervisor_watchdog(*, interval_s: float = 1.0) -> None:
    """Backend exits if the recorded launcher supervisor disappears.

    Complements Linux PR_SET_PDEATHSIG. Uvicorn may fork; this poll still holds.
    """
    global _WATCHDOG_STARTED
    if _WATCHDOG_STARTED:
        return
    if _env_int(ENV_SUPERVISOR_PID) is None:
        return
    linux_pdeathsig_preexec()
    _WATCHDOG_STARTED = True

    def _loop() -> None:
        while True:
            time.sleep(max(0.25, float(interval_s)))
            if supervisor_is_alive():
                continue
            try:
                interrupt_unowned_jobs(reason="supervisor_missing")
            except Exception:
                pass
            try:
                os.kill(os.getpid(), signal.SIGTERM)
            except Exception:
                os._exit(1)

    threading.Thread(target=_loop, name="mm-supervisor-watchdog", daemon=True).start()


def _progress_path(out_dir: Path) -> Path:
    return Path(out_dir) / "progress.json"


def read_progress(out_dir: Path) -> dict[str, Any]:
    path = _progress_path(out_dir)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def write_interrupted_progress(out_dir: Path, prog: dict[str, Any], *, reason: str) -> dict[str, Any]:
    from mechanistic_mind.scientific_v3.analyzer_next.job import write_progress

    out = dict(prog or {})
    out["state"] = INTERRUPTED_BY_APPLICATION_EXIT
    out["status"] = INTERRUPTED_BY_APPLICATION_EXIT
    out["phase"] = "CANCELLED"
    out["terminal"] = True
    out["complete"] = False
    out["scientific_complete"] = False
    out["cancel_requested"] = bool(out.get("cancel_requested"))
    out["interrupted_reason"] = reason
    out["status_text"] = "Previous analysis was interrupted when MM Observer closed."
    out["message"] = out["status_text"]
    write_progress(_progress_path(out_dir), out)
    return out


def job_is_terminal(prog: dict[str, Any] | None) -> bool:
    if not prog:
        return False
    if prog.get("terminal") is True:
        return True
    state = str(prog.get("state") or prog.get("status") or "").upper()
    return state in TERMINAL_JOB_STATES


def job_owned_by_this_backend(prog: dict[str, Any] | None) -> bool:
    if not prog:
        return False
    inst = os.environ.get("PSY_OBSERVER_INSTANCE_ID")
    ident = os.environ.get("PSY_OBSERVER_PACKAGE_IDENTITY")
    if not inst or not ident:
        return False
    if str(prog.get("owner_instance_id") or "") != str(inst):
        return False
    if str(prog.get("owner_package_identity") or "") != str(ident):
        return False
    pid = prog.get("owner_backend_pid")
    start = prog.get("owner_backend_starttime")
    if pid and start:
        return pid_matches_record(int(pid), starttime=str(start))
    return True


def interrupt_unowned_jobs(*, jobs_root: Path | None = None, reason: str = "owner_instance_gone") -> list[str]:
    """Persisted RUNNING / CANCEL_REQUESTED jobs whose owner died become interrupted."""
    from mechanistic_mind.ui.psy_observer_web.run_finalize import default_results_root

    if jobs_root is None:
        try:
            from mechanistic_mind.ui.psy_observer_web.server import get_session

            sess = get_session()
            root = Path(sess.config.results_root) if getattr(sess.config, "results_root", None) else default_results_root()
        except Exception:
            root = default_results_root()
        jobs_root = Path(root) / "analysis_jobs"
    changed: list[str] = []
    if not jobs_root.is_dir():
        return changed
    for child in jobs_root.iterdir():
        if not child.is_dir():
            continue
        prog = read_progress(child)
        if not prog or job_is_terminal(prog):
            continue
        state = str(prog.get("state") or prog.get("status") or "RUNNING").upper()
        if state not in NONTERMINAL_JOB_STATES and not prog.get("cancel_requested"):
            continue
        if job_owned_by_this_backend(prog):
            continue
        write_interrupted_progress(child, prog, reason=reason)
        changed.append(child.name)
    return changed


def stamp_job_owner(prog: dict[str, Any], extra: dict[str, Any] | None = None) -> dict[str, Any]:
    out = dict(prog or {})
    out.update(current_instance_owner())
    if extra:
        out.update(extra)
    return out
