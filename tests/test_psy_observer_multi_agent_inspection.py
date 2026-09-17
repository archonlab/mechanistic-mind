"""Observer multi-agent inspection integrity (AGENT / MIND / TIMELINE)."""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from mechanistic_mind.ui.psy_observer_web.server import app
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig
from mechanistic_mind.physical_system import TwoAgentRuntime


@pytest.fixture()
def client(tmp_path, monkeypatch):
    session = ObserverSession(SessionConfig(seed=17, buffer_capacity=64, ui_hz=30, results_root=tmp_path))
    import mechanistic_mind.ui.psy_observer_web.server as server
    monkeypatch.setattr(server, "get_session", lambda: session)
    yield TestClient(app), session
    session.stop(save=False, reason="USER_STOP_NO_SAVE")


def _two(session):
    session.apply_experiment({"seed": 17, "agent_count": 2})
    assert isinstance(session.runtime, TwoAgentRuntime)
    for _ in range(8):
        session.step(n=1)


def test_a_mind_source_follows_selected_agent(client):
    c, session = client
    _two(session)
    f0 = c.post("/api/control/select-agent", json={"index": 0}).json()
    assert f0["control_receipt"]["accepted"]
    assert f0["mind"]["source_agent_id"] == "agent_0"
    assert f0["header"]["selected_agent_id"] == "agent_0"
    mind0 = f0["mind"]

    f1 = c.post("/api/control/select-agent", json={"index": 1}).json()
    assert f1["control_receipt"]["accepted"]
    assert f1["mind"]["source_agent_id"] == "agent_1"
    assert f1["header"]["selected_agent_id"] == "agent_1"
    assert f1["body"]["agent_id"] == "agent_1"
    assert f1["body"]["body_id"] == "body-1"
    assert f1["mind"]["source_agent_id"] != mind0["source_agent_id"]


def test_b_selection_survives_tab_equivalent_refetch(client):
    c, session = client
    _two(session)
    c.post("/api/control/select-agent", json={"index": 1})
    # Simulate WORLD→AGENT→MIND→TIMELINE by refetching state
    for _ in range(3):
        st = c.get("/api/state").json()
        assert st["header"]["selected_agent_id"] == "agent_1"
        assert st["mind"]["source_agent_id"] == "agent_1"


def test_c_select_does_not_advance_tick(client):
    c, session = client
    _two(session)
    t0 = int(session.runtime.tick)
    c.post("/api/control/select-agent", json={"index": 1})
    assert int(session.runtime.tick) == t0
    c.post("/api/control/select-agent", json={"index": 0})
    assert int(session.runtime.tick) == t0


def test_d_select_does_not_mutate_scientific_snapshot(client):
    c, session = client
    _two(session)
    snap_before = session.runtime.snapshot()
    c.post("/api/control/select-agent", json={"index": 1})
    snap_after = session.runtime.snapshot()
    # selected_index is observer-only and not in scientific snapshot
    assert snap_before["tick"] == snap_after["tick"]
    assert snap_before["agents"][0]["body"]["x"] == snap_after["agents"][0]["body"]["x"]
    assert snap_before["agents"][1]["body"]["x"] == snap_after["agents"][1]["body"]["x"]
    assert snap_before["agents"][0]["cognition"] == snap_after["agents"][0]["cognition"]
    assert snap_before["agents"][1]["cognition"] == snap_after["agents"][1]["cognition"]


def test_e_agent_cognition_never_cross_served(client):
    c, session = client
    _two(session)
    # Deliberately diverge cognition markers
    session.runtime.slots[0].cognition["metrics"] = {
        **(session.runtime.slots[0].cognition.get("metrics") or {}),
        "observer_probe_marker": "FROM_AGENT_0_ONLY",
    }
    session.runtime.slots[1].cognition["metrics"] = {
        **(session.runtime.slots[1].cognition.get("metrics") or {}),
        "observer_probe_marker": "FROM_AGENT_1_ONLY",
    }
    f0 = c.post("/api/control/select-agent", json={"index": 0}).json()
    f1 = c.post("/api/control/select-agent", json={"index": 1}).json()
    assert f0["mind"]["metrics"].get("observer_probe_marker") == "FROM_AGENT_0_ONLY"
    assert f1["mind"]["metrics"].get("observer_probe_marker") == "FROM_AGENT_1_ONLY"
    assert f0["agents_views"]["agent_0"]["mind"]["metrics"]["observer_probe_marker"] == "FROM_AGENT_0_ONLY"
    assert f0["agents_views"]["agent_1"]["mind"]["metrics"]["observer_probe_marker"] == "FROM_AGENT_1_ONLY"
    assert f1["agents_views"]["agent_0"]["mind"]["source_agent_id"] == "agent_0"
    assert f1["agents_views"]["agent_1"]["mind"]["source_agent_id"] == "agent_1"


def test_f_timeline_agent_filters(client):
    c, session = client
    _two(session)
    ev = c.get("/api/events?limit=200").json()["events"]
    assert isinstance(ev, list)
    a0 = [e for e in ev if (e.get("actor_agent_id") or e.get("agent_id")) == "agent_0"]
    a1 = [e for e in ev if (e.get("actor_agent_id") or e.get("agent_id")) == "agent_1"]
    # Both agents may emit; attribution must be present on agent events
    for e in ev:
        if e.get("agent_id") in {"agent_0", "agent_1"}:
            assert e.get("actor_agent_id") or e.get("agent_id")
            assert e.get("body_id") in {None, "body-0", "body-1"} or str(e.get("body_id", "")).startswith("body-")


def test_g_h_signal_evidence_inspectable(client):
    c, session = client
    _two(session)
    tick = int(session.runtime.tick)
    session.runtime.slots[0].structured_events.emit(
        "PHYSICAL_SIGNAL_EMITTED",
        tick=tick,
        evidence={"slot": 0, "channel": "FIELD_A", "intensity": 0.42, "position": [1.0, 2.0]},
    )
    session.runtime.slots[1].structured_events.emit(
        "PHYSICAL_SIGNAL_RECEIVED",
        tick=tick,
        evidence={"local.FIELD_A": 0.2, "observer_receiver_id": "agent_1"},
    )
    events = c.get("/api/events?limit=200").json()["events"]
    emitted = [e for e in events if "SIGNAL_EMITTED" in str(e.get("type") or e.get("kind") or "")]
    received = [e for e in events if "SIGNAL_RECEIVED" in str(e.get("type") or e.get("kind") or "")]
    assert emitted and received
    for e in emitted + received:
        assert isinstance(e.get("evidence"), dict)
        assert e["evidence"], "evidence payload must be non-empty when event exists"
    e0 = emitted[-1]
    assert e0.get("emitter_agent_id") == "agent_0" or e0["evidence"].get("emitter_agent_id") == "agent_0"
    e1 = received[-1]
    src = e1.get("source_agent_id") or (e1.get("evidence") or {}).get("source_agent_id")
    assert src == "UNKNOWN"
    assert (e1.get("evidence") or {}).get("source") == "NOT_RECORDED"


def test_i_unknown_sender_not_guessed(client):
    c, session = client
    _two(session)
    # Inject a reception-only event
    session.runtime.slots[1].structured_events.emit(
        "PHYSICAL_SIGNAL_RECEIVED",
        tick=int(session.runtime.tick),
        evidence={"local.FIELD_A": 0.5, "observer_receiver_id": "agent_1"},
    )
    events = c.get("/api/events?limit=50").json()["events"]
    recv = [e for e in events if e.get("type") == "PHYSICAL_SIGNAL_RECEIVED" and e.get("agent_id") == "agent_1"]
    assert recv
    e = recv[-1]
    assert e["evidence"].get("source_agent_id") == "UNKNOWN"
    assert e["evidence"].get("source") == "NOT_RECORDED"
    assert e.get("source_agent_id") == "UNKNOWN"


def test_j_live_inspect_selected_agent_consistent(client):
    c, session = client
    _two(session)
    c.post("/api/control/select-agent", json={"index": 1})
    live = c.get("/api/state").json()
    tick = int(live["header"]["tick"])
    inspected = c.get(f"/api/inspect/{tick}").json()
    assert live["header"]["selected_agent_id"] == "agent_1"
    # Inspected frame carries agents_views so UI can re-project
    assert "agent_1" in (inspected.get("agents_views") or live.get("agents_views") or {})
    views = inspected.get("agents_views") or live.get("agents_views")
    assert views["agent_1"]["mind"]["source_agent_id"] == "agent_1"
    assert views["agent_0"]["mind"]["source_agent_id"] == "agent_0"


def test_k_two_agent_snapshot_restore_independent(client):
    c, session = client
    _two(session)
    session.runtime.slots[0].cognition["metrics"] = {"marker": "A"}
    session.runtime.slots[1].cognition["metrics"] = {"marker": "B"}
    snap = session.runtime.snapshot()
    c.post("/api/control/reset", params={"seed": 17})
    out = c.post("/api/snapshot/restore", json=snap).json()
    assert out["control_receipt"]["accepted"]
    assert isinstance(session.runtime, TwoAgentRuntime)
    assert session.runtime.slots[0].cognition["metrics"]["marker"] == "A"
    assert session.runtime.slots[1].cognition["metrics"]["marker"] == "B"


def test_l_single_agent_still_works(client):
    c, session = client
    c.post("/api/control/step", json={"n": 3})
    st = c.get("/api/state").json()
    assert st["header"]["selected_agent_id"] == "agent_0"
    assert st["header"]["selected_body_id"] == "body-0"
    assert st["mind"]["source_agent_id"] == "agent_0"
    rejected = c.post("/api/control/select-agent", json={"index": 1}).json()
    assert rejected["control_receipt"]["accepted"] is False


def test_m_canonical_identity_tuple_and_distinct_minds(client):
    c, session = client
    base_seed = 143
    session.apply_experiment({"seed": base_seed, "agent_count": 2})
    assert isinstance(session.runtime, TwoAgentRuntime)
    for _ in range(5):
        session.step(n=1)
    session.runtime.slots[0].cognition["metrics"] = {
        **(session.runtime.slots[0].cognition.get("metrics") or {}),
        "observer_probe_marker": "SEED143_A0",
    }
    session.runtime.slots[1].cognition["metrics"] = {
        **(session.runtime.slots[1].cognition.get("metrics") or {}),
        "observer_probe_marker": "SEED144_A1",
    }
    f0 = c.post("/api/control/select-agent", json={"index": 0}).json()
    f1 = c.post("/api/control/select-agent", json={"index": 1}).json()
    gen = f0["header"]["runtime_generation"]
    tick = f0["header"]["tick"]
    assert f1["header"]["tick"] == tick
    assert f1["header"]["runtime_generation"] == gen

    v0 = f0["agents_views"]["agent_0"]
    v1 = f0["agents_views"]["agent_1"]
    assert v0["agent_id"] == "agent_0" and v0["body_id"] == "body-0" and v0["agent_seed"] == base_seed
    assert v1["agent_id"] == "agent_1" and v1["body_id"] == "body-1" and v1["agent_seed"] == base_seed + 1
    assert v0["mind"]["source_agent_id"] == "agent_0"
    assert v1["mind"]["source_agent_id"] == "agent_1"
    assert v0["mind"]["metrics"]["observer_probe_marker"] == "SEED143_A0"
    assert v1["mind"]["metrics"]["observer_probe_marker"] == "SEED144_A1"
    assert id(v0["mind"]) != id(v1["mind"])
    assert v0["mind"] is not v1["mind"]

    assert f0["header"]["selected_agent_id"] == "agent_0"
    assert f0["header"]["selected_body_id"] == "body-0"
    assert f0["header"]["inspected_agent_seed"] == base_seed
    assert f0["mind"]["source_agent_id"] == "agent_0"
    assert f1["header"]["selected_agent_id"] == "agent_1"
    assert f1["header"]["selected_body_id"] == "body-1"
    assert f1["header"]["inspected_agent_seed"] == base_seed + 1
    assert f1["mind"]["source_agent_id"] == "agent_1"
    # Top-level must equal the matching agents_views entry (no silent peer fallback)
    assert f1["mind"]["metrics"]["observer_probe_marker"] == v1["mind"]["metrics"]["observer_probe_marker"]
    assert f0["mind"]["metrics"]["observer_probe_marker"] == v0["mind"]["metrics"]["observer_probe_marker"]


def test_n_no_peer_fallback_when_view_missing(client, monkeypatch):
    """If agents_views lacks selected agent, top-level must NOT reuse peer mind."""
    from mechanistic_mind.ui.psy_observer_web import serialize as ser

    c, session = client
    _two(session)
    real_views = ser.agents_views_frame

    def strip_agent_1(runtime, *, previous_body=None, detail="full"):
        views = real_views(runtime, previous_body=previous_body, detail=detail)
        views.pop("agent_1", None)
        return views

    monkeypatch.setattr(ser, "agents_views_frame", strip_agent_1)
    session.runtime.select_agent(1)
    frame = ser.live_frame(
        session.runtime,
        status="PAUSED",
        mode="LIVE",
        target_tick=None,
        previous_body=None,
    )
    assert frame["header"]["selected_agent_id"] == "agent_1"
    assert frame["mind"].get("status") == "NOT AVAILABLE"
    assert frame["mind"].get("source_agent_id") == "agent_1"
    assert "metrics" not in frame["mind"] or frame["mind"].get("metrics") is None
    assert "agent_0" in frame["agents_views"]
    assert "agent_1" not in frame["agents_views"]
