"""Persistence integrity: Save & Stop must persist the live runtime generation.

Regression for the failure class where Save → Play continue → Save reused the
prior run_id and returned a stale idempotent artifact while the UI showed the
advanced live tick (forensic case d463612b: UI ~17730 vs persisted 3077).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from mechanistic_mind.ui.psy_observer_web.server import app
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig
from mechanistic_mind.ui.psy_observer_web.run_finalize import (
    read_run_manifest,
    read_run_snapshot,
    write_finalized_run,
)
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


def test_generation_a_save_then_continue_persists_generation_b(client):
    """Exact failure class: gen A saved ~T1; continue to T2; Save must persist T2."""
    c, session, root = client
    session.apply_experiment({"seed": 17, "agent_count": 2})
    assert isinstance(session.runtime, TwoAgentRuntime)
    gen_a = session._runtime_generation

    c.post("/api/control/step", json={"n": 25})
    t1 = int(session.runtime.tick)
    out1 = c.post("/api/control/stop", json={"save": True, "reason": "USER_STOP_SAVED"}).json()
    assert out1["finalize"]["accepted"] is True
    assert out1["finalize"]["final_tick"] == t1
    assert out1["control_receipt"]["tick"] == t1
    assert out1["control_receipt"].get("verified_final_tick") == t1
    rid_a = out1["finalize"]["run_id"]
    assert session._active_run_id is None  # released after save

    # Continue without Reset — same runtime generation, new run identity
    c.post("/api/control/play")
    assert session._active_run_id is not None
    assert session._active_run_id != rid_a
    c.post("/api/control/pause")
    c.post("/api/control/step", json={"n": 40})
    t2 = int(session.runtime.tick)
    assert t2 > t1
    assert session._runtime_generation == gen_a  # same object generation; new run_id

    live_tick = int(session.runtime.tick)
    assert live_tick == t2

    out2 = c.post("/api/control/stop", json={"save": True, "reason": "USER_STOP_SAVED"}).json()
    assert out2["finalize"]["accepted"] is True, out2["finalize"]
    assert out2["finalize"].get("idempotent") is not True
    assert out2["finalize"]["final_tick"] == t2
    assert out2["control_receipt"]["tick"] == t2
    assert out2["finalize"]["run_id"] != rid_a

    dirs = _run_dirs(root)
    assert len(dirs) == 2
    by_id = {read_run_manifest(d)["run_id"]: read_run_manifest(d) for d in dirs}
    assert by_id[rid_a]["final_tick"] == t1
    assert by_id[out2["finalize"]["run_id"]]["final_tick"] == t2
    snap_b = read_run_snapshot(Path(out2["finalize"]["run_dir"]))
    assert int(snap_b["tick"]) == t2
    assert len(snap_b["agents"]) == 2
    assert int(snap_b["agents"][0]["tick"]) == t2
    assert int(snap_b["agents"][1]["tick"]) == t2


def test_stale_run_id_reuse_rejected_not_idempotent_success(client):
    """Inject the exact d463612b failure: same run_id, advanced live tick → SAVE_FAILED."""
    c, session, root = client
    session.apply_experiment({"seed": 17, "agent_count": 2})
    c.post("/api/control/step", json={"n": 12})
    t1 = int(session.runtime.tick)
    out1 = c.post("/api/control/stop", json={"save": True}).json()
    assert out1["finalize"]["accepted"]
    rid = out1["finalize"]["run_id"]

    # Force the stale-reference bug: re-bind the old run_id after continuing
    c.post("/api/control/step", json={"n": 20})
    t2 = int(session.runtime.tick)
    assert t2 > t1
    session._active_run_id = rid
    session._run_started_at = "forced-stale"
    session._finalize_key = None

    out2 = c.post("/api/control/stop", json={"save": True}).json()
    assert out2["control_receipt"]["accepted"] is False
    assert out2["finalize"]["accepted"] is False
    assert out2["finalize"].get("persistence_integrity_error") is True
    assert out2["finalize"]["live_tick"] == t2
    assert out2["finalize"]["captured_tick"] == t1
    assert session.status == "SAVE_FAILED"
    # Original artifact untouched
    assert read_run_manifest(Path(out1["finalize"]["run_dir"]))["final_tick"] == t1
    assert len(_run_dirs(root)) == 1


def test_reset_then_new_run_cannot_finalize_old_generation(client):
    c, session, root = client
    c.post("/api/control/step", json={"n": 8})
    t_old = int(session.runtime.tick)
    gen_old = session._runtime_generation
    out1 = c.post("/api/control/stop", json={"save": True}).json()
    assert out1["finalize"]["final_tick"] == t_old

    c.post("/api/control/reset", params={"seed": 17})
    assert session._runtime_generation != gen_old
    c.post("/api/control/step", json={"n": 5})
    t_new = int(session.runtime.tick)
    out2 = c.post("/api/control/stop", json={"save": True}).json()
    assert out2["finalize"]["accepted"]
    assert out2["finalize"]["final_tick"] == t_new
    assert out2["finalize"]["run_id"] != out1["finalize"]["run_id"]
    assert len(_run_dirs(root)) == 2


def test_snapshot_restore_then_continue_saves_continued_runtime(client):
    c, session, root = client
    session.apply_experiment({"seed": 21, "agent_count": 2})
    c.post("/api/control/step", json={"n": 6})
    c.post("/api/control/stop", json={"save": True})
    snap = read_run_snapshot(_run_dirs(root)[0])
    t0 = int(snap["tick"])
    c.post("/api/snapshot/restore", json=snap)
    assert int(session.runtime.tick) == t0
    c.post("/api/control/step", json={"n": 7})
    t1 = int(session.runtime.tick)
    out = c.post("/api/control/stop", json={"save": True}).json()
    assert out["finalize"]["final_tick"] == t1
    assert int(read_run_snapshot(Path(out["finalize"]["run_dir"]))["tick"]) == t1


def test_pause_then_save_and_stop_tick(client):
    c, session, root = client
    c.post("/api/control/play")
    c.post("/api/control/step", json={"n": 4})  # step forces pause path
    c.post("/api/control/pause")
    tick = int(session.runtime.tick)
    out = c.post("/api/control/stop", json={"save": True}).json()
    assert out["finalize"]["final_tick"] == tick
    assert read_run_manifest(_run_dirs(root)[0])["final_tick"] == tick


def test_buffers_do_not_exceed_final_tick(client):
    c, session, root = client
    session.apply_experiment({"seed": 17, "agent_count": 2})
    c.post("/api/control/step", json={"n": 15})
    out = c.post("/api/control/stop", json={"save": True}).json()
    run_dir = Path(out["finalize"]["run_dir"])
    final = int(out["finalize"]["final_tick"])
    timeline = [
        json.loads(line)
        for line in (run_dir / "session_timeline.jsonl").read_text().splitlines()
        if line.strip()
    ]
    telemetry = json.loads((run_dir / "session_telemetry.json").read_text())["series"]
    events = json.loads((run_dir / "structured_events.json").read_text())["events"]
    for row in timeline:
        assert int(row["tick"]) <= final
    for row in telemetry:
        assert int(row["tick"]) <= final
    for row in events:
        assert int(row["tick"]) <= final


def test_write_finalized_run_rejects_stale_idempotent_without_session(tmp_path):
    """Unit-level: existing run.json at T1 + live runtime at T2 ⇒ not accepted."""
    from mechanistic_mind.physical_system import PhysicalSystemRuntime

    rt = PhysicalSystemRuntime(seed=3)
    for _ in range(5):
        rt.step(1)
    r1 = write_finalized_run(
        results_root=tmp_path,
        runtime=rt,
        session_meta={"started_at": "t0", "seed": 3, "buffer": {}},
        timeline=[{"tick": int(rt.tick)}],
        telemetry=[{"tick": int(rt.tick)}],
        termination_reason="USER_STOP_SAVED",
        run_id="psyweb-stale-test",
        identity={"expected_final_tick": int(rt.tick), "runtime_generation": 1},
    )
    assert r1["accepted"] and r1["final_tick"] == 5
    for _ in range(10):
        rt.step(1)
    r2 = write_finalized_run(
        results_root=tmp_path,
        runtime=rt,
        session_meta={"started_at": "t0", "seed": 3, "buffer": {}},
        timeline=[{"tick": int(rt.tick)}],
        telemetry=[{"tick": int(rt.tick)}],
        termination_reason="USER_STOP_SAVED",
        run_id="psyweb-stale-test",
        identity={"expected_final_tick": int(rt.tick), "runtime_generation": 1},
    )
    assert r2["accepted"] is False
    assert r2["persistence_integrity_error"] is True
    assert r2["live_tick"] == 15
    assert r2["captured_tick"] == 5
