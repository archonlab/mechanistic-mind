"""Aged Save/Stop: large cognition + scientific history, FINALIZING recovery, layers."""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from mechanistic_mind.physical_system import TwoAgentRuntime, sensorimotor_consequence as smc
from mechanistic_mind.research import predictive_equivalence as pe
from mechanistic_mind.ui.psy_observer_web.run_finalize import write_finalized_run
from mechanistic_mind.ui.psy_observer_web.server import app
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig


@pytest.fixture()
def client(tmp_path, monkeypatch):
    session = ObserverSession(SessionConfig(seed=41, buffer_capacity=64, ui_hz=20, results_root=tmp_path))
    import mechanistic_mind.ui.psy_observer_web.server as server
    monkeypatch.setattr(server, "get_session", lambda: session)
    yield TestClient(app), session, tmp_path
    try:
        session.stop(save=False, reason="USER_STOP_NO_SAVE")
    except Exception:
        pass


def _fill_aged_cognition(runtime: TwoAgentRuntime) -> None:
    for slot in runtime.slots:
        eq = slot.cognition.setdefault("equivalence", pe.empty_store())
        eq["enabled"] = True
        for i in range(pe.MAX_CLASSES + 80):
            pe.learn(
                eq,
                fragment={f"k{j}": float(i) + 0.01 * j for j in range(8)},
                action=f"A{i % 6}",
                consequent={"out": float(i) * 1.7},
                tick=i,
            )
        inner = ((slot.cognition.get("temporal") or {}).setdefault("inner", pe.empty_store()))
        inner["enabled"] = True
        for i in range(pe.MAX_CLASSES + 40):
            pe.learn(
                inner,
                fragment={f"t{j}": float(i) * 0.2 for j in range(6)},
                action="WAIT",
                consequent={"z": float(i)},
                tick=i,
            )
        store = slot.cognition.setdefault("sensorimotor_consequence", smc.empty_store(enabled=True, capacity=256))
        store["enabled"] = True
        locos = ["WAIT", "MOVE:N", "MOVE:S", "MOVE:E", "MOVE:W"]
        t = 0
        while len(store.get("records") or {}) < 256 and t < 4000:
            obs = {k: 0.2 for k in smc.SENSORY_CHANNELS[:8]}
            obs["exo_0"] = ((t % 5) + 0.5) / 5.0
            obs["exo_1"] = (((t // 5) % 5) + 0.5) / 5.0
            obs["exo_2"] = (((t // 25) % 5) + 0.5) / 5.0
            nxt = dict(obs)
            nxt["exo_0"] = ((t % 4) + 0.5) / 5.0
            smc.update(
                store,
                tick=t,
                observation_t=obs,
                motor={
                    "locomotion": locos[t % 5],
                    "neck": "NONE",
                    "oscillator": {"emit_trigger": bool(t % 3 == 0)},
                    "push": bool(t % 7 == 0),
                },
                observation_t1=nxt,
            )
            t += 1


def _write_aged_jsonl(live: Path, n: int = 2500) -> None:
    live.mkdir(parents=True, exist_ok=True)
    (live / "scientific_meta.json").write_text(
        json.dumps({"run_id": "aged-test", "last_tick_written": n - 1, "rows_written": n}),
        encoding="utf-8",
    )
    with (live / "scientific_timeline.jsonl").open("w", encoding="utf-8") as fh:
        for i in range(n):
            fh.write(json.dumps({"tick": i, "kind": "TIMELINE", "payload": {"i": i, "blob": "x" * 40}}) + "\n")
    with (live / "scientific_decisions.jsonl").open("w", encoding="utf-8") as fh:
        for i in range(n):
            fh.write(json.dumps({"tick": i, "kind": "DECISION", "n": i}) + "\n")


def test_aged_write_finalized_run_large_cognition_and_history(tmp_path):
    rt = TwoAgentRuntime(seed=41)
    for _ in range(12):
        rt.step()
    _fill_aged_cognition(rt)
    live = tmp_path / "live-aged"
    _write_aged_jsonl(live, 1800)
    result = write_finalized_run(
        results_root=tmp_path,
        runtime=rt,
        session_meta={"started_at": "2026-09-22T00:00:00Z", "seed": 41, "buffer": {}},
        timeline=[{"tick": i, "status": "RUNNING"} for i in range(max(0, int(rt.tick) - 8), int(rt.tick) + 1)],
        telemetry=[{"tick": int(rt.tick), "sim_ticks_per_sec": 1.0}],
        termination_reason="USER_STOP_SAVED",
        run_id="aged-save-test",
        scientific_live_dir=live,
    )
    assert result["accepted"] is True
    assert result["saved"] is True
    run_dir = Path(result["run_dir"])
    assert (run_dir / "run.json").is_file()
    assert (run_dir / "physical_system_snapshot.json").stat().st_size > 10_000
    assert (run_dir / "scientific_timeline.jsonl").is_file()
    assert (run_dir / "scientific_decisions.jsonl").is_file()
    snap = json.loads((run_dir / "physical_system_snapshot.json").read_text(encoding="utf-8"))
    assert int(snap["tick"]) == int(rt.tick)
    manifest = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert manifest["final_tick"] == int(rt.tick)
    assert manifest["scientific_history"]["present"] is True


def test_finalize_exception_leaves_save_failed_not_finalizing(client, monkeypatch):
    c, session, _ = client
    c.post("/api/control/step", json={"n": 4})

    def boom(**kwargs):
        raise MemoryError("simulated aged snapshot OOM")

    monkeypatch.setattr(
        "mechanistic_mind.ui.psy_observer_web.session.write_finalized_run",
        boom,
    )
    out = c.post("/api/control/stop", json={"save": True, "wait": True}).json()
    assert session.status == "SAVE_FAILED"
    assert session.status != "FINALIZING"
    assert out["control_receipt"]["accepted"] is False
    assert out["finalize"]["accepted"] is False
    assert "OOM" in out["finalize"]["error"] or "MemoryError" in out["finalize"]["error"] or "simulated" in out["finalize"]["error"]
    job = c.get("/api/control/save-job").json()
    assert job["lifecycle"] == "SAVE_FAILED"
    assert job["layers"]["save"] == "failed"
    assert job["layers"]["http"] == "n/a_server"
    # Retry Save & Stop is legal from SAVE_FAILED
    def ok(**kwargs):
        from mechanistic_mind.ui.psy_observer_web.run_finalize import write_finalized_run as real
        return real(**kwargs)

    monkeypatch.setattr(
        "mechanistic_mind.ui.psy_observer_web.session.write_finalized_run",
        ok,
    )
    out2 = c.post("/api/control/stop", json={"save": True, "wait": True}).json()
    assert out2["control_receipt"]["accepted"] is True
    assert session.status == "STOPPED"


def test_async_save_stop_poll_does_not_hold_http(client, monkeypatch):
    c, session, _ = client
    c.post("/api/control/step", json={"n": 3})
    gate = threading.Event()
    import mechanistic_mind.ui.psy_observer_web.session as sessmod
    real = sessmod.write_finalized_run

    def slow(**kwargs):
        gate.wait(timeout=5.0)
        return real(**kwargs)

    monkeypatch.setattr(sessmod, "write_finalized_run", slow)
    started = c.post("/api/control/stop", json={"save": True, "wait": False, "reason": "USER_STOP_SAVED"}).json()
    assert started["control_receipt"]["accepted"] is True
    assert started["finalize"].get("pending") is True
    assert session.status == "FINALIZING"
    job = c.get("/api/control/save-job").json()
    assert job["pending"] is True
    assert job["layers"]["http"] == "n/a_server"
    gate.set()
    deadline = time.monotonic() + 10.0
    terminal = None
    while time.monotonic() < deadline:
        terminal = c.get("/api/control/save-job").json()
        if terminal.get("lifecycle") in {"STOPPED", "SAVE_FAILED"}:
            break
        time.sleep(0.05)
    assert terminal is not None
    assert terminal["lifecycle"] == "STOPPED"
    assert terminal["save"] == "succeeded"
    assert session.status == "STOPPED"


def test_save_job_clears_zombie_finalizing(client):
    c, session, _ = client
    c.post("/api/control/step", json={"n": 1})
    session.status = "FINALIZING"
    session._save_job = {"job_id": "dead", "save": "pending", "finalize": "pending"}
    session._save_job_thread = None
    job = c.get("/api/control/save-job").json()
    assert session.status == "SAVE_FAILED"
    assert job["lifecycle"] == "SAVE_FAILED"
    assert job["save"] in {"failed", "unknown"}
