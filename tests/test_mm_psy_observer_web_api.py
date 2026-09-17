"""Psy Observer Web adapter — real PSR data, no fabricated stages."""
from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

# Prefer venv-installed fastapi when available via path; otherwise skip if missing.
from mechanistic_mind.ui.psy_observer_web.server import app
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig


@pytest.fixture()
def client(monkeypatch):
    sess = ObserverSession(SessionConfig(seed=17, buffer_capacity=64, ui_hz=100.0))
    import mechanistic_mind.ui.psy_observer_web.session as session_mod
    import mechanistic_mind.ui.psy_observer_web.server as server_mod
    monkeypatch.setattr(session_mod, "_SESSION", sess)
    monkeypatch.setattr(server_mod, "get_session", lambda: sess)
    return TestClient(app), sess


def test_health(client):
    c, _ = client
    r = c.get("/api/health")
    assert r.status_code == 200
    assert r.json()["runtime"] == "PhysicalSystemRuntime"


def test_state_has_real_boundary_fields(client):
    c, _ = client
    data = c.get("/api/state").json()
    assert data["header"]["runtime_model"] == "PhysicalSystemRuntime"
    assert data["header"]["selected_agent"] == "agent_0"
    assert data["header"]["selected_agent_id"] == "agent_0"
    assert data["header"]["selected_body_id"] == "body-0"
    assert data["header"]["agent_body_mapping"][0]["agent_id"] == "agent_0"
    assert data["header"]["agent_body_mapping"][0]["body_id"] == "body-0"
    assert "agent_observation" in data["perception"]
    assert "T" in data["world"]
    assert data["world"]["entities"]["body"]["id"] == "body-0"
    # no fabricated ecology object inventory — only body entity
    assert set(data["world"]["entities"]) <= {"note", "body"}
    assert data["world"]["entities"]["body"]["id"] == "body-0"


def test_step_advances_tick(client):
    c, sess = client
    t0 = c.get("/api/state").json()["header"]["tick"]
    c.post("/api/control/step", json={"n": 3})
    t1 = c.get("/api/state").json()["header"]["tick"]
    assert t1 == t0 + 3


def test_causal_chain_stages_honest(client):
    c, _ = client
    c.post("/api/control/step", json={"n": 2})
    chain = c.get("/api/causal-chain").json()
    stages = chain["stages"]
    for key in ("WORLD", "PERCEPTION", "BODY", "INTERNAL", "PREDICTION", "ACTION", "CONSEQUENCE"):
        assert key in stages
        assert stages[key]["status"] in {"AVAILABLE", "NOT AVAILABLE"}
    assert stages["PERCEPTION"]["note"] == "agent-accessible only"
    why = chain["why_this_action"]
    assert why["status"] in {"AVAILABLE", "CAUSAL ATTRIBUTION NOT AVAILABLE"}


def test_inspect_missing_tick(client):
    c, _ = client
    miss = c.get("/api/inspect/999999").json()
    assert miss.get("error") == "NOT AVAILABLE"


def test_mind_mechanisms_from_config(client):
    c, _ = client
    mind = c.get("/api/mind").json()
    names = {m["name"] for m in mind["mechanisms"]}
    assert "predictive_compression" in names
    assert "prospective_composition" in names


def test_snapshot_roundtrip(client):
    c, _ = client
    c.post("/api/control/step", json={"n": 5})
    snap = c.get("/api/snapshot").json()
    assert snap["schema"] == "mm.physical_system.snapshot.v2"
    c.post("/api/control/step", json={"n": 2})
    c.post("/api/snapshot/restore", json=snap)
    assert c.get("/api/state").json()["header"]["tick"] == 5


def test_perception_not_world_maps(client):
    c, _ = client
    data = c.get("/api/state").json()
    obs = data["perception"]["agent_observation"]
    assert "local.T" in obs
    assert "T_mean" not in obs  # world truth summary stays out of agent obs
