"""Crash-safe checkpoint: generations, failed write, continuation, V3 branch identity."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.ui.psy_observer_web.crash_checkpoint import (
    MANIFEST,
    SNAPSHOT,
    load_committed,
    load_snapshot_dict,
    read_manifest,
    write_checkpoint,
)


def _pose(rt: TwoAgentRuntime) -> list[tuple]:
    out = []
    for slot in rt.slots:
        b = slot.body
        out.append((
            int(slot.tick),
            round(float(b.x), 6),
            round(float(b.y), 6),
            round(float(b.vx), 6),
            round(float(b.vy), 6),
            round(float(getattr(b, "theta", 0.0) or 0.0), 6),
            round(float(getattr(b, "head_relative_angle", 0.0) or 0.0), 6),
        ))
    return out


def _cog_card(rt: TwoAgentRuntime) -> list[dict]:
    rows = []
    for slot in rt.slots:
        cog = slot.cognition if isinstance(slot.cognition, dict) else {}
        smc = cog.get("sensorimotor_consequence") or cog.get("smc") or {}
        rec = smc.get("records") if isinstance(smc, dict) else None
        pe = cog.get("predictive_equivalence") or cog.get("pe") or {}
        classes = pe.get("classes") if isinstance(pe, dict) else None
        rows.append({
            "cog_keys": len(cog),
            "smc_records": len(rec) if isinstance(rec, dict) else None,
            "pe_classes": len(classes) if isinstance(classes, dict) else None,
        })
    return rows


def test_generation_rotate_and_previous_survives_failed_write(tmp_path, monkeypatch):
    rt = TwoAgentRuntime(seed=17)
    rt.step(n=12)
    a = write_checkpoint(rt, dest_root=tmp_path, run_id="g1")
    assert a["accepted"]
    t1 = a["tick"]
    rt.step(n=8)
    b = write_checkpoint(rt, dest_root=tmp_path, run_id="g2")
    assert b["accepted"]
    t2 = b["tick"]
    assert t2 > t1
    ck = tmp_path / "runtime_checkpoints"
    assert read_manifest(ck / "current")["tick"] == t2
    assert read_manifest(ck / "previous")["tick"] == t1

    def boom(*_a, **_k):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(
        "mechanistic_mind.ui.psy_observer_web.crash_checkpoint.dump_persist",
        boom,
    )
    with pytest.raises(OSError):
        write_checkpoint(rt, dest_root=tmp_path, run_id="fail")
    man = load_committed(tmp_path)["manifest"]
    assert man["tick"] == t2
    assert read_manifest(ck / "previous")["tick"] == t1
    assert not (ck / "tmp").exists() or not (ck / "tmp" / SNAPSHOT).is_file()


def test_truncated_tmp_is_ignored(tmp_path):
    rt = TwoAgentRuntime(seed=19)
    rt.step(n=10)
    write_checkpoint(rt, dest_root=tmp_path, run_id="ok")
    ck = tmp_path / "runtime_checkpoints"
    tmp = ck / "tmp"
    tmp.mkdir(exist_ok=True)
    (tmp / SNAPSHOT).write_bytes(b"{truncated")
    (tmp / MANIFEST).write_text("not json")
    loaded = load_committed(tmp_path)
    assert loaded["manifest"]["status"] == "COMMITTED"
    assert Path(loaded["dir"]).name == "current"


def test_kill_after_commit_uses_new_generation(tmp_path):
    rt = TwoAgentRuntime(seed=23)
    rt.step(n=6)
    write_checkpoint(rt, dest_root=tmp_path, run_id="n")
    rt.step(n=6)
    write_checkpoint(rt, dest_root=tmp_path, run_id="n1")
    loaded = load_committed(tmp_path)
    snap = load_snapshot_dict(loaded)
    restored = TwoAgentRuntime.restore(snap)
    assert restored.tick == loaded["manifest"]["tick"]


def test_continuation_pose_and_stores(tmp_path):
    seed = 29
    n_ck, extra = 24, 12
    a = TwoAgentRuntime(seed=seed)
    a.step(n=n_ck)
    pose_ck = _pose(a)
    card_ck = _cog_card(a)
    write_checkpoint(a, dest_root=tmp_path, run_id="cont")
    a.step(n=extra)
    pose_unint = _pose(a)
    card_unint = _cog_card(a)

    loaded = load_committed(tmp_path)
    b = TwoAgentRuntime.restore(load_snapshot_dict(loaded))
    assert b.tick == n_ck
    assert _pose(b) == pose_ck
    assert _cog_card(b) == card_ck
    b.step(n=extra)
    # Strongest persistence-supported equivalence: pose/tick/store cardinalities.
    # RNG of numpy/world stochastic extras may differ if not in snapshot.
    assert b.tick == a.tick
    pose_b = _pose(b)
    assert pose_b[0][0] == pose_unint[0][0]
    # Body pose after restore+step: require match on this fixture if snapshot is complete.
    assert pose_b == pose_unint
    assert _cog_card(b) == card_unint


def test_observer_session_v3_new_segment(tmp_path):
    pytest.importorskip("fastapi")
    from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig

    s = ObserverSession(SessionConfig(
        seed=31,
        buffer_capacity=32,
        ui_hz=20,
        results_root=tmp_path,
        checkpoint_every_ticks=10,
    ))
    try:
        s.step(n=22)
        last = s.checkpoint_status().get("last_tick")
        assert last == 20
        live = s._sci_live_dir
        assert live is not None
        ck_dir = live / "runtime_checkpoints" / "current"
        assert (ck_dir / SNAPSHOT).is_file()
        prev_run = s._active_run_id
        out = s.restore_committed_checkpoint(dest_root=live)
        assert out["accepted"]
        assert out["checkpoint_tick"] == 20
        assert int(s.runtime.tick) == 20
        assert s._active_run_id != prev_run
        meta = s._v3_writer.meta_path if s._v3_writer is not None else None
        # reopen after restore
        s.step(n=4)
        new_live = s._sci_live_dir
        assert new_live is not None
        assert new_live != live
        v3 = json.loads((new_live / "scientific_v3_meta.json").read_text())
        assert v3.get("resumed_from_checkpoint") is True
        assert int(v3.get("checkpoint_tick") or 0) == 20
        assert v3.get("previous_run_id") == prev_run
        s.stop(save=False, reason="USER_STOP_NO_SAVE")
        assert (live / "scientific_spine.jsonl").is_file()
        assert (new_live / "scientific_spine.jsonl").is_file()
    finally:
        try:
            s.stop(save=False, reason="USER_STOP_NO_SAVE")
        except Exception:
            pass


def test_checkpoint_apis(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from mechanistic_mind.ui.psy_observer_web.server import app
    from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig
    import mechanistic_mind.ui.psy_observer_web.server as server

    session = ObserverSession(SessionConfig(seed=37, buffer_capacity=16, ui_hz=20, results_root=tmp_path))
    monkeypatch.setattr(server, "get_session", lambda: session)
    try:
        c = TestClient(app)
        r = c.post("/api/checkpoint/cadence", json={"every_ticks": 1000})
        assert r.status_code == 200
        assert r.json()["cadence"] == 1000
        session.step(n=3)
        r2 = c.post("/api/checkpoint/now")
        assert r2.status_code == 200
        body = r2.json()
        assert body.get("accepted") is True
        st = c.get("/api/checkpoint/status").json()
        assert st.get("last_tick") == int(session.runtime.tick)
    finally:
        session.stop(save=False, reason="USER_STOP_NO_SAVE")
