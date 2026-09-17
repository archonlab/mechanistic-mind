"""Launcher lifecycle: lock, identity, stale recovery, port collision."""
from __future__ import annotations

import json
import os
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from mechanistic_mind.ui.psy_observer_web import launcher as L


def _serve(payload: dict, port: int = 0):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            return

    httpd = HTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


def test_project_root_independent_of_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = L.project_root()
    assert (root / "mechanistic_mind").is_dir()
    assert (root / "PsyObserver").exists()
    assert (root / "launch_psy_observer.sh").exists()


def test_python_candidates_include_windows_scripts_layout():
    root = Path("/tmp/fake-root")
    cands = [str(p).replace("\\", "/") for p in L.python_candidates(root)]
    assert any(s.endswith(".venv_psy_web/Scripts/python.exe") for s in cands)
    assert any(s.endswith(".venv_psy_web/bin/python") for s in cands)


def test_spa_missing_is_human(tmp_path):
    with pytest.raises(L.LaunchError, match="not built"):
        L.verify_spa(tmp_path)


def test_spa_present_on_this_repo():
    root = L.project_root()
    assert L.verify_spa(root).is_file()


def test_is_our_health_rejects_unrelated():
    assert not L.is_our_health({"ok": True, "app": "nginx"})
    assert not L.is_our_health({"ok": True})
    token = "abc"
    ours = {
        "ok": True,
        "app": L.APP_NAME,
        "runtime": "PhysicalSystemRuntime",
        "instance_id": token,
    }
    assert L.is_our_health(ours, token)
    assert not L.is_our_health(ours, "other")


def test_stale_lock_is_cleared(tmp_path):
    L.write_lock(tmp_path, {
        "schema": L.LOCK_SCHEMA,
        "instance_id": "dead",
        "owner_pid": 999999,
        "server_pid": 999998,
        "url": "http://127.0.0.1:59999/",
    })
    assert L.existing_healthy(tmp_path) is None
    assert L.read_lock(tmp_path) is None


def test_healthy_lock_is_reused(tmp_path):
    token = "live-token"
    httpd = _serve({
        "ok": True,
        "app": L.APP_NAME,
        "runtime": "PhysicalSystemRuntime",
        "instance_id": token,
    })
    port = httpd.server_address[1]
    L.write_lock(tmp_path, {
        "schema": L.LOCK_SCHEMA,
        "instance_id": token,
        "owner_pid": os.getpid(),
        "server_pid": os.getpid(),
        "url": f"http://127.0.0.1:{port}/",
        "port": port,
    })
    found = L.existing_healthy(tmp_path)
    httpd.shutdown()
    assert found is not None
    assert found["instance_id"] == token


def test_unrelated_port_occupant_is_not_our_instance():
    httpd = _serve({"ok": True, "service": "someone-else"})
    port = httpd.server_address[1]
    health = L.probe_health(f"http://127.0.0.1:{port}/")
    httpd.shutdown()
    assert health is not None
    assert not L.is_our_health(health)


def test_choose_port_skips_occupied():
    occupier = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    occupier.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    occupier.bind(("127.0.0.1", 0))
    occupier.listen(1)
    busy = occupier.getsockname()[1]
    try:
        chosen = L.choose_port(busy)
        assert chosen != busy
        assert not L.port_in_use(chosen)
    finally:
        occupier.close()


def test_one_click_lifecycle_reuses_and_quits(tmp_path):
    root = L.project_root()
    # One instance per checkout: clear any leftover audit/dev server lock first.
    L.quit_existing(root)
    time.sleep(0.2)
    port = L.choose_port(8876)
    env_port = port
    try:
        first = L.launch(
            root=root,
            preferred_port=env_port,
            open_ui=False,
            ownership_ui=False,
            wait=False,
        )
        assert first.get("reused") is False
        url = first["url"]
        health = L.wait_for_health(url, first["instance_id"], timeout=20)
        assert health["model"] == "MM 1.0 — Tiktaalik"
        assert L.existing_healthy(root)["instance_id"] == first["instance_id"]

        second = L.launch(
            root=root,
            preferred_port=env_port,
            open_ui=False,
            ownership_ui=False,
            wait=False,
        )
        assert second.get("reused") is True
        assert second["instance_id"] == first["instance_id"]
        assert second["port"] == first["port"]
    finally:
        L.quit_existing(root)
        time.sleep(0.2)
        assert L.existing_healthy(root) is None


def test_is_our_health_accepts_two_agent_runtime():
    token = "two"
    ours = {
        "ok": True,
        "app": L.APP_NAME,
        "runtime": "TwoAgentRuntime",
        "instance_id": token,
    }
    assert L.is_our_health(ours, token)
    assert not L.is_our_health({**ours, "runtime": "SomethingElse"}, token)


def test_health_endpoint_identifies_app():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from mechanistic_mind.ui.psy_observer_web.server import app
    os.environ["PSY_OBSERVER_INSTANCE_ID"] = "test-instance"
    out = TestClient(app).get("/api/health").json()
    assert out["ok"] is True
    assert out["app"] == "Psy Observer"
    assert out["model"] == "MM 1.0 — Tiktaalik"
    assert out["runtime"] == "PhysicalSystemRuntime"
    assert out["local"] is True
    assert out["instance_id"] == "test-instance"
    ident = TestClient(app).get("/api/instance").json()
    assert ident["identity"] == "Psy Observer · local"
