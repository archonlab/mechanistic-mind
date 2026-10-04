"""Focused process-lifecycle tests: supervisor ownership, stale jobs, fixture cleanup."""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread

import pytest

from mechanistic_mind.physical_system.experiment_canonical import (
    PRESET_ACANTHOSTEGA_BETA4,
    PRESET_BETA31,
    canonical_fingerprint,
    preset_canonical,
)
from mechanistic_mind.ui.psy_observer_web import instance_lifecycle as IL
from mechanistic_mind.ui.psy_observer_web import launcher as L
from mechanistic_mind.ui.psy_observer_web.process_ownership import (
    INTERRUPTED_BY_APPLICATION_EXIT,
    interrupt_unowned_jobs,
    job_owned_by_this_backend,
    supervisor_is_alive,
)

FROZEN_B31 = "1621ef2c154864d1"
FROZEN_B4 = "3666b58d67932821"
ROOT = Path(__file__).resolve().parents[1]


def _isolate(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PSY_OBSERVER_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg-state"))
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "xdg-run"))
    monkeypatch.setenv("PSY_OBSERVER_NO_GUI", "1")


def _wait_our_health_gone(url: str, instance_id: str, timeout: float = 8.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not L.is_our_health(L.probe_health(url), instance_id):
            return
        time.sleep(0.05)
    raise AssertionError(f"owned health still present at {url}")


def test_final_window_close_and_more_exit_invoke_authenticated_shutdown():
    src = Path(L.__file__).read_text(encoding="utf-8")
    assert "if window_proc is not None and window_proc.poll() is not None" in src
    assert "shutdown_owned" in src
    assert "request_instance_shutdown" in src
    header = (ROOT / "web/psy-observer/src/chrome/ObserverHeader.tsx").read_text(encoding="utf-8")
    assert "/api/instance/shutdown" in header
    assert "Exit MM Observer" in header
    app = (ROOT / "web/psy-observer/src/App.tsx").read_text(encoding="utf-8")
    assert "beforeunload" not in app
    assert "sendBeacon" not in app


def test_refresh_and_temporary_disconnect_do_not_stop_backend():
    src = Path(L.__file__).read_text(encoding="utf-8")
    assert "beforeunload" not in src
    assert "visibilitychange" not in src
    server = Path(L.__file__).with_name("server.py").read_text(encoding="utf-8")
    assert "start_supervisor_watchdog" in server
    assert "hub.clients" in server  # WS demand does not imply process death


def test_supervisor_liveness_requires_matching_starttime(monkeypatch):
    monkeypatch.delenv("PSY_OBSERVER_SUPERVISOR_PID", raising=False)
    monkeypatch.delenv("PSY_OBSERVER_SUPERVISOR_STARTTIME", raising=False)
    assert supervisor_is_alive() is True
    monkeypatch.setenv("PSY_OBSERVER_SUPERVISOR_PID", str(os.getpid()))
    monkeypatch.setenv("PSY_OBSERVER_SUPERVISOR_STARTTIME", IL.pid_starttime(os.getpid()) or "")
    assert supervisor_is_alive() is True
    monkeypatch.setenv("PSY_OBSERVER_SUPERVISOR_STARTTIME", "1")
    assert supervisor_is_alive() is False


def test_stale_instance_reconciliation_and_pid_reuse(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setattr(L, "state_dir", lambda _root: tmp_path)
    live = os.getpid()
    L.write_lock(tmp_path, {
        "schema": L.LOCK_SCHEMA,
        "instance_id": "stale",
        "owner_pid": live,
        "owner_starttime": "1",
        "server_pid": 999991,
        "server_starttime": "1",
        "url": "http://127.0.0.1:59991/",
    })
    assert L.recover_stale_lock(tmp_path) == "stale_cleared"
    assert L.read_lock(tmp_path) is None


def test_unrelated_http_never_killed_and_dynamic_port_fallback():
    httpd = HTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
    port = httpd.server_address[1]
    thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        chosen = L.choose_port(port)
        assert chosen != port
        assert L.port_in_use(port)
        # Busy port is not ownership; do not request_stop.
        L.request_stop(f"http://127.0.0.1:{port}/")
        assert L.port_in_use(port)
    finally:
        httpd.shutdown()


def test_old_package_is_not_reused(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setattr(L, "state_dir", lambda _root: tmp_path)
    ident = IL.package_identity(tmp_path / "new-root")
    L.write_lock(tmp_path, {
        "schema": L.LOCK_SCHEMA,
        "instance_id": "old",
        "package_identity": "0.2.0:oldpkg",
        "url": "http://127.0.0.1:59992/",
        "port": 59992,
        "owner_pid": 1,
        "owner_starttime": "1",
        "server_pid": 1,
        "server_starttime": "1",
    })
    monkeypatch.setattr(L, "probe_health", lambda _url: {
        "ok": True,
        "app": L.APP_NAME,
        "instance_id": "old",
        "package_identity": "0.2.0:oldpkg",
        "runtime": "PhysicalSystemRuntime",
    })
    monkeypatch.setattr(L, "package_identity", lambda _root: ident)
    assert L.existing_healthy(tmp_path) is None
    foreign = L.foreign_healthy_instance(tmp_path)
    assert foreign is not None
    assert foreign.get("cross_version") is True


def test_persisted_running_and_cancel_requested_become_interrupted(tmp_path, monkeypatch):
    jobs = tmp_path / "analysis_jobs"
    for name, state in (("run-old", "RUNNING"), ("cancel-old", "CANCEL_REQUESTED")):
        d = jobs / name
        d.mkdir(parents=True)
        (d / "progress.json").write_text(json.dumps({
            "job_id": name,
            "state": state,
            "status": state,
            "terminal": False,
            "complete": False,
            "owner_instance_id": "dead-instance",
            "owner_package_identity": "0.2.0:dead",
            "owner_backend_pid": 999999,
            "owner_backend_starttime": "1",
            "phase_index": 6,
            "phase_count": 8,
            "overall_processed": 2150,
            "overall_total": 25802,
        }), encoding="utf-8")
    monkeypatch.setenv("PSY_OBSERVER_INSTANCE_ID", "live-instance")
    monkeypatch.setenv("PSY_OBSERVER_PACKAGE_IDENTITY", "0.2.0:live")
    changed = interrupt_unowned_jobs(jobs_root=jobs, reason="owner_instance_gone")
    assert set(changed) == {"run-old", "cancel-old"}
    for name in ("run-old", "cancel-old"):
        prog = json.loads((jobs / name / "progress.json").read_text(encoding="utf-8"))
        assert prog["state"] == INTERRUPTED_BY_APPLICATION_EXIT
        assert prog["terminal"] is True
        assert prog["complete"] is False
        assert prog["scientific_complete"] is False
        assert "Previous analysis was interrupted when MM Observer closed." in prog["status_text"]
        assert not job_owned_by_this_backend(prog)


def test_stale_localstorage_restore_rejected_in_frontend_helpers():
    src = (ROOT / "web/psy-observer/src/analysis/analyzerJobProgress.ts").read_text(encoding="utf-8")
    assert "jobRestoreAllowed" in src
    app = (ROOT / "web/psy-observer/src/App.tsx").read_text(encoding="utf-8")
    assert "jobRestoreAllowed" in app
    assert "INTERRUPTED_BY_APPLICATION_EXIT" in app


def test_fingerprints_unchanged():
    assert canonical_fingerprint(preset_canonical(PRESET_BETA31, seed=17)) == FROZEN_B31
    assert canonical_fingerprint(preset_canonical(PRESET_ACANTHOSTEGA_BETA4, seed=17)) == FROZEN_B4


def test_psc_ui_authority_module_still_exports_current_runtime():
    src = (ROOT / "web/psy-observer/src/components/pscUiAuthority.ts").read_text(encoding="utf-8")
    assert "currentRuntimePresentation" in src
    assert "CURRENT RUNTIME" in src or "current runtime" in src.lower()


def test_dual_fpv_lifecycle_module_present():
    src = (ROOT / "web/psy-observer/src/components/eyeDockDualFpvLifecycle.ts").read_text(encoding="utf-8")
    assert "eye_dock_dual_fpv" in src or "dual" in src.lower()


def test_launcher_records_supervisor_on_backend_spawn():
    src = Path(L.__file__).read_text(encoding="utf-8")
    assert "ENV_SUPERVISOR_PID" in src
    assert "ENV_SUPERVISOR_STARTTIME" in src
    assert "loopback_foreign_mm" in src
    assert "An older MM Observer instance is still running" in src


def test_supervisor_disappearance_stops_backend(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    port = L.choose_port(8910)
    script = r"""
import os, sys, time
from pathlib import Path
from mechanistic_mind.ui.psy_observer_web import launcher as L
root = Path(sys.argv[1])
port = int(sys.argv[2])
os.environ["PSY_OBSERVER_NO_GUI"] = "1"
os.environ["PSY_OBSERVER_STATE_DIR"] = sys.argv[3]
lock = L.launch(root=root, preferred_port=port, open_ui=False, ownership_ui=False, wait=False)
print(json_line := __import__("json").dumps({"url": lock["url"], "instance_id": lock["instance_id"], "server_pid": lock["server_pid"], "port": lock["port"]}), flush=True)
while True:
    time.sleep(0.2)
"""
    env = dict(os.environ)
    env["PSY_OBSERVER_NO_GUI"] = "1"
    env["PSY_OBSERVER_STATE_DIR"] = str(tmp_path / "state")
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.Popen(
        [sys.executable, "-c", script, str(ROOT), str(port), str(tmp_path / "state")],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=str(ROOT),
        env=env,
        start_new_session=True,
    )
    rec = None
    try:
        deadline = time.monotonic() + 25
        buf = b""
        while time.monotonic() < deadline:
            line = proc.stdout.readline() if proc.stdout else b""
            if not line:
                if proc.poll() is not None:
                    break
                continue
            buf += line
            try:
                rec = json.loads(line.decode("utf-8", errors="replace").strip())
                if rec.get("url"):
                    break
            except Exception:
                continue
        assert rec and rec.get("url"), buf.decode("utf-8", errors="replace")[-2000:]
        L.wait_for_health(rec["url"], rec["instance_id"], timeout=20)
        os.kill(proc.pid, signal.SIGKILL)
        try:
            proc.wait(timeout=3)
        except Exception:
            pass
        _wait_our_health_gone(rec["url"], rec["instance_id"], timeout=12)
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline and L.port_in_use(rec["port"]):
            if not L.is_our_health(L.probe_health(rec["url"]), rec["instance_id"]):
                break
            time.sleep(0.05)
        assert not L.is_our_health(L.probe_health(rec["url"]), rec["instance_id"])
    finally:
        if proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except Exception:
                proc.kill()
        if rec:
            L.shutdown_owned(ROOT, {
                "url": rec.get("url"),
                "shutdown_token": None,
                "instance_id": rec.get("instance_id"),
                "server_pid": rec.get("server_pid"),
                "port": rec.get("port"),
            })


def test_three_sequential_launch_close_cycles_leave_zero_orphans(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    root = L.project_root()
    ports = []
    for _ in range(3):
        port = L.choose_port(8920)
        rec = None
        try:
            rec = L.launch(root=root, preferred_port=port, open_ui=False, ownership_ui=False, wait=False)
            L.wait_for_health(rec["url"], rec["instance_id"], timeout=20)
            ports.append(rec["port"])
            L.shutdown_owned(root, rec)
            _wait_our_health_gone(rec["url"], rec["instance_id"])
            assert not L.is_our_health(L.probe_health(rec["url"]), rec["instance_id"])
        finally:
            L.quit_existing(root)
            if rec:
                _wait_our_health_gone(rec["url"], rec["instance_id"], timeout=6)
    assert L.existing_healthy(root) is None


def test_owned_launch_fixture_releases_port(tmp_path, monkeypatch):
    """The 8890 wait=False helper must always drop its own child."""
    _isolate(tmp_path, monkeypatch)
    root = L.project_root()
    rec = None
    port = L.choose_port(8890)
    try:
        rec = L.launch(root=root, preferred_port=port, open_ui=False, ownership_ui=False, wait=False)
        L.wait_for_health(rec["url"], rec["instance_id"], timeout=20)
        assert rec.get("owner_pid") == os.getpid()
        assert L.pid_matches_record(rec["owner_pid"], starttime=rec.get("owner_starttime"))
    finally:
        if rec:
            L.shutdown_owned(root, rec)
        L.quit_existing(root)
        if rec:
            _wait_our_health_gone(rec["url"], rec["instance_id"], timeout=8)
            assert not L.is_our_health(L.probe_health(rec["url"]), rec["instance_id"])
