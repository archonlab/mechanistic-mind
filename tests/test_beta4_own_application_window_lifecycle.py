"""Beta 4 own application window + authenticated process lifecycle."""
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
from mechanistic_mind.ui.psy_observer_web import instance_lifecycle as IL


def test_application_window_argv_uses_app_mode_and_private_profile(tmp_path):
    chrome = Path("/usr/bin/google-chrome-stable")
    argv = IL.application_window_argv(chrome, "http://127.0.0.1:8768/", tmp_path / "prof")
    joined = " ".join(argv)
    assert "--app=http://127.0.0.1:8768/" in joined
    assert f"--user-data-dir={tmp_path / 'prof'}" in joined
    assert "--new-window" in argv
    assert "xdg-open" not in joined
    assert "--app=" in joined


def test_pid_reuse_rejected(tmp_path):
    live = os.getpid()
    rec_start = IL.pid_starttime(live)
    assert IL.pid_matches_record(live, starttime=rec_start)
    # Wrong starttime (PID reuse).
    assert not IL.pid_matches_record(live, starttime="1")
    # Dead pid.
    assert not IL.pid_matches_record(99999999, starttime="1")


def test_unrelated_port_is_not_ownership():
    occupier = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    occupier.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    occupier.bind(("127.0.0.1", 0))
    occupier.listen(1)
    busy = occupier.getsockname()[1]
    try:
        chosen = L.choose_port(busy)
        assert chosen != busy
        assert L.port_in_use(busy)
        assert not L.port_in_use(chosen)
    finally:
        occupier.close()


def test_stale_lock_recovery_does_not_kill(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "state_dir", lambda _root: tmp_path)
    L.write_lock(tmp_path, {
        "schema": L.LOCK_SCHEMA,
        "instance_id": "dead",
        "owner_pid": 999999,
        "owner_starttime": "1",
        "server_pid": 999998,
        "server_starttime": "1",
        "url": "http://127.0.0.1:59999/",
    })
    assert L.recover_stale_lock(tmp_path) == "stale_cleared"
    assert L.read_lock(tmp_path) is None


def test_package_identity_differs_across_roots(tmp_path):
    a = IL.package_identity(tmp_path / "A")
    b = IL.package_identity(tmp_path / "B")
    assert a != b


def test_tokens_match_is_constant_time():
    tok = IL.new_ownership_token()
    assert IL.tokens_match(tok, tok)
    assert not IL.tokens_match(tok, tok[:-1] + "x")
    assert not IL.tokens_match(None, tok)


def test_lock_write_is_user_restricted(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "state_dir", lambda _root: tmp_path)
    L.write_lock(tmp_path, {"schema": L.LOCK_SCHEMA, "instance_id": "x"})
    mode = L.lock_path(tmp_path).stat().st_mode & 0o777
    assert mode & 0o077 == 0


def test_health_omits_shutdown_token():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from mechanistic_mind.ui.psy_observer_web.server import app

    os.environ["PSY_OBSERVER_INSTANCE_ID"] = "life-1"
    os.environ["PSY_OBSERVER_SHUTDOWN_TOKEN"] = "secret-token-value"
    os.environ["PSY_OBSERVER_PACKAGE_IDENTITY"] = "0.2.0:abcd"
    client = TestClient(app)
    out = client.get("/api/health").json()
    blob = json.dumps(out)
    assert "secret-token-value" not in blob
    assert out["instance_id"] == "life-1"
    assert out["package_identity"] == "0.2.0:abcd"
    denied = client.post("/api/instance/shutdown", headers={"X-MM-Shutdown-Token": "not-the-token"})
    assert denied.status_code == 403
    ok = client.post("/api/instance/shutdown", headers={"X-MM-Shutdown-Token": "secret-token-value"})
    assert ok.status_code == 200
    assert ok.json().get("shutting_down") is True


def test_chrome_argv_not_reusing_default_profile():
    argv = IL.application_window_argv(
        Path("/usr/bin/chromium"),
        "http://127.0.0.1:9/",
        Path("/tmp/mm-profile-xyz"),
    )
    assert any(a.startswith("--user-data-dir=") for a in argv)
    assert not any("Default" == a for a in argv)


def test_launcher_does_not_use_tab_close_as_authority():
    src = Path(L.__file__).read_text(encoding="utf-8")
    assert "start_new_session=True" not in src
    assert "spawn_application_window" in src
    assert "request_instance_shutdown" in src
    assert "webbrowser.open" not in src.split("def launch")[1].split("def quit_existing")[0]


def test_one_supervisor_one_backend_no_wait(tmp_path, monkeypatch):
    root = L.project_root()
    # Isolate XDG so a host orphan on 8768 is not this instance.
    monkeypatch.setenv("PSY_OBSERVER_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg-state"))
    L.quit_existing(root)
    port = L.choose_port(8890)
    first: dict | None = None
    try:
        first = L.launch(
            root=root,
            preferred_port=port,
            open_ui=False,
            ownership_ui=False,
            wait=False,
        )
        assert first.get("reused") is False
        assert first.get("shutdown_token")
        assert first.get("package_identity")
        health = L.wait_for_health(first["url"], first["instance_id"], timeout=20)
        assert health.get("ok") is True
        assert L.pid_alive(first["server_pid"])
        assert L.port_in_use(first["port"])
        second = L.launch(
            root=root,
            preferred_port=port,
            open_ui=False,
            wait=False,
        )
        assert second.get("reused") is True
        assert second["instance_id"] == first["instance_id"]
        L.shutdown_owned(root, first)
        time.sleep(0.3)
        assert not L.port_in_use(first["port"]) or not L.is_our_health(
            L.probe_health(first["url"]), first["instance_id"]
        )
        assert L.existing_healthy(root) is None
    finally:
        L.quit_existing(root)
        if first is None:
            return
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and L.port_in_use(first.get("port", -1)):
            if not L.is_our_health(L.probe_health(first["url"]), first["instance_id"]):
                break
            time.sleep(0.05)
        assert not L.is_our_health(L.probe_health(first["url"]), first.get("instance_id"))


def test_refresh_semantics_documented_not_shutdown():
    src = Path(L.__file__).read_text(encoding="utf-8")
    assert "beforeunload" not in src
    assert "sendBeacon" not in src


def test_dynamic_port_fallback_skips_unrelated_http():
    httpd = HTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        chosen = L.choose_port(port)
        assert chosen != port
    finally:
        httpd.shutdown()
