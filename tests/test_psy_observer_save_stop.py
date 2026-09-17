"""Save & Stop / finalize_run lifecycle for Psy Observer Web."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from mechanistic_mind.ui.psy_observer_web.server import app
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig
from mechanistic_mind.ui.psy_observer_web.run_finalize import read_run_manifest, read_run_snapshot
from mechanistic_mind.physical_system import TwoAgentRuntime


@pytest.fixture()
def client(tmp_path, monkeypatch):
    session = ObserverSession(SessionConfig(seed=17, buffer_capacity=64, ui_hz=20, results_root=tmp_path))
    import mechanistic_mind.ui.psy_observer_web.server as server
    monkeypatch.setattr(server, "get_session", lambda: session)
    yield TestClient(app), session, tmp_path
    session.stop(save=False, reason="USER_STOP_NO_SAVE")


def _run_dirs(root: Path) -> list[Path]:
    base = root / "psychology_observer" / "psy_observer_web"
    if not base.is_dir():
        return []
    return sorted(p for p in base.iterdir() if p.is_dir() and (p / "run.json").is_file())


def test_a_save_and_stop_persists_final_tick_and_metadata(client):
    c, session, root = client
    c.post("/api/control/step", json={"n": 7})
    tick = int(session.runtime.tick)
    out = c.post("/api/control/stop", json={"save": True, "reason": "USER_STOP_SAVED"}).json()
    assert out["control_receipt"]["accepted"]
    assert out["control_receipt"]["new_state"]["status"] == "STOPPED"
    fin = out["finalize"]
    assert fin["accepted"]
    assert fin["final_tick"] == tick
    dirs = _run_dirs(root)
    assert len(dirs) == 1
    manifest = read_run_manifest(dirs[0])
    assert manifest["final_tick"] == tick
    assert manifest["termination_reason"] == "USER_STOP_SAVED"
    assert manifest["seed"] == 17
    assert manifest["capabilities"]["inspectable"] is True


def test_b_save_and_stop_flushes_buffered_telemetry(client):
    c, session, root = client
    c.post("/api/control/step", json={"n": 5})
    assert len(session._telemetry) > 0
    tel_before = list(session._telemetry)
    c.post("/api/control/stop", json={"save": True}).json()
    dirs = _run_dirs(root)
    tel = json.loads((dirs[0] / "session_telemetry.json").read_text())
    assert tel["count"] >= len(tel_before)
    assert len(tel["series"]) >= len(tel_before)
    # Pre-stop samples are present in the flushed artifact
    before_ticks = {row["tick"] for row in tel_before}
    saved_ticks = {row["tick"] for row in tel["series"]}
    assert before_ticks.issubset(saved_ticks)


def test_c_save_and_stop_preserves_world_body_state(client):
    c, session, root = client
    c.post("/api/control/step", json={"n": 4})
    body = session.runtime.body.snapshot()
    world_tick = int(session.runtime.world.tick)
    c.post("/api/control/stop", json={"save": True})
    snap = read_run_snapshot(_run_dirs(root)[0])
    assert snap["tick"] == world_tick
    assert abs(float(snap["body"]["x"]) - float(body["x"])) < 1e-9
    assert abs(float(snap["body"]["y"]) - float(body["y"])) < 1e-9


def test_d_two_agent_saves_both_agents(client):
    c, session, root = client
    session.apply_experiment({"seed": 17, "agent_count": 2})
    assert isinstance(session.runtime, TwoAgentRuntime)
    c.post("/api/control/step", json={"n": 3})
    # Change observer selection — must not affect which agents are saved
    c.post("/api/control/select-agent", json={"index": 1})
    a0 = session.runtime.slots[0].body.snapshot()
    a1 = session.runtime.slots[1].body.snapshot()
    out = c.post("/api/control/stop", json={"save": True}).json()
    assert out["finalize"]["accepted"]
    snap = read_run_snapshot(_run_dirs(root)[0])
    assert snap["schema"] == "mm.physical_system.two_agent.snapshot.v1"
    assert len(snap["agents"]) == 2
    assert abs(float(snap["agents"][0]["body"]["x"]) - float(a0["x"])) < 1e-9
    assert abs(float(snap["agents"][1]["body"]["x"]) - float(a1["x"])) < 1e-9
    manifest = read_run_manifest(_run_dirs(root)[0])
    assert manifest["agent_count"] == 2
    assert len(manifest["agents"]) == 2


def test_e_cancel_does_not_alter_runtime(client):
    c, session, _ = client
    c.post("/api/control/step", json={"n": 3})
    tick = int(session.runtime.tick)
    info = c.get("/api/control/stop-info").json()
    assert info["tick"] == tick
    assert int(session.runtime.tick) == tick
    assert session.status != "STOPPED"


def test_f_stop_without_saving_creates_no_completed_run(client):
    c, session, root = client
    c.post("/api/control/step", json={"n": 4})
    out = c.post("/api/control/stop", json={"save": False, "reason": "USER_STOP_NO_SAVE"}).json()
    assert out["control_receipt"]["accepted"]
    assert out["finalize"]["saved"] is False
    assert out["finalize"]["termination_reason"] == "USER_STOP_NO_SAVE"
    assert _run_dirs(root) == []


def test_g_double_save_and_stop_is_idempotent(client):
    c, session, root = client
    c.post("/api/control/step", json={"n": 3})
    out1 = c.post("/api/control/stop", json={"save": True}).json()
    assert out1["finalize"]["accepted"]
    # Second finalize with same key via finalize_run
    fin2 = session.finalize_run(reason="USER_STOP_SAVED")
    assert fin2["accepted"]
    assert fin2.get("idempotent") is True
    assert len(_run_dirs(root)) == 1


def test_h_save_failure_is_visible_not_success(client, monkeypatch):
    c, session, root = client
    c.post("/api/control/step", json={"n": 2})

    def boom(**kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(
        "mechanistic_mind.ui.psy_observer_web.session.write_finalized_run",
        boom,
    )
    out = c.post("/api/control/stop", json={"save": True}).json()
    assert out["control_receipt"]["accepted"] is False
    assert out["control_receipt"]["new_state"]["status"] == "SAVE_FAILED"
    assert out["finalize"]["accepted"] is False
    assert "disk full" in out["finalize"]["error"]
    assert session.status == "SAVE_FAILED"
    assert int(session.runtime.tick) == 2  # preserved
    assert _run_dirs(root) == []


def test_i_saved_artifact_readable_and_restorable(client):
    c, session, root = client
    c.post("/api/control/step", json={"n": 5})
    tick = int(session.runtime.tick)
    x = float(session.runtime.body.x)
    c.post("/api/control/stop", json={"save": True})
    snap = read_run_snapshot(_run_dirs(root)[0])
    assert snap["schema"] == "mm.physical_system.snapshot.v2"
    restored = c.post("/api/snapshot/restore", json=snap).json()
    assert restored["control_receipt"]["accepted"]
    assert int(session.runtime.tick) == tick
    assert abs(float(session.runtime.body.x) - x) < 1e-9
    caps = read_run_manifest(_run_dirs(root)[0])["capabilities"]
    assert caps["inspectable"] is True
    assert caps["resumable"] is True


def test_two_agent_restore_from_saved_run(client):
    c, session, root = client
    session.apply_experiment({"seed": 21, "agent_count": 2})
    c.post("/api/control/step", json={"n": 2})
    c.post("/api/control/stop", json={"save": True})
    snap = read_run_snapshot(_run_dirs(root)[0])
    out = c.post("/api/snapshot/restore", json=snap).json()
    assert out["control_receipt"]["accepted"]
    assert isinstance(session.runtime, TwoAgentRuntime)
    assert len(session.runtime.slots) == 2
