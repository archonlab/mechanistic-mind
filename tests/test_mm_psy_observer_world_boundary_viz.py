"""World boundary honesty + field discovery + size apply for Psy Observer Web."""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from mechanistic_mind.ui.psy_observer_web.server import app
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig
from mechanistic_mind.ui.psy_observer_web.serialize import BOUNDARY_MODES, discover_world_fields, boundary_metadata
from mechanistic_mind.physical_system import PhysicalSystemRuntime


@pytest.fixture()
def client(monkeypatch):
    sess = ObserverSession(SessionConfig(seed=17, buffer_capacity=64, ui_hz=100.0))
    import mechanistic_mind.ui.psy_observer_web.session as session_mod
    import mechanistic_mind.ui.psy_observer_web.server as server_mod
    monkeypatch.setattr(session_mod, "_SESSION", sess)
    monkeypatch.setattr(server_mod, "get_session", lambda: sess)
    return TestClient(app), sess


def test_boundary_modes_honest():
    assert BOUNDARY_MODES["WRAP_PERIODIC"]["status"] == "SUPPORTED"
    assert BOUNDARY_MODES["CLOSED"]["status"] == "UNSUPPORTED"
    assert BOUNDARY_MODES["OPEN"]["status"] == "UNSUPPORTED"


def test_runtime_metadata_wrap_only():
    r = PhysicalSystemRuntime(seed=3)
    meta = boundary_metadata(r)
    assert meta["spatial_topology"] == "WRAP_PERIODIC"
    assert meta["modes"]["CLOSED"]["status"] == "UNSUPPORTED"
    fields = discover_world_fields(r)
    ids = {f["id"] for f in fields}
    assert "T" in ids and "flow" in ids


def test_api_exposes_boundary_and_fields(client):
    c, _ = client
    b = c.get("/api/world/boundary").json()
    assert b["spatial_topology"] == "WRAP_PERIODIC"
    f = c.get("/api/world/fields").json()
    assert any(x["id"] == "T" for x in f["fields_available"])
    assert "SMOOTH" in f["render_modes"]
    state = c.get("/api/state").json()
    assert state["header"]["boundary_topology"] == "WRAP_PERIODIC"
    assert "scalars" in state["world"]
    assert state["world"]["interpolation_policy"].startswith("SMOOTH")


def test_reject_unsupported_boundary_mode(client):
    c, _ = client
    bad = c.post("/api/experiment", json={"seed": 1, "world": {"boundary_mode": "CLOSED"}})
    assert bad.status_code == 400
    bad2 = c.post("/api/experiment", json={"seed": 1, "world": {"boundary_mode": "OPEN"}})
    assert bad2.status_code == 400


def test_wrap_mode_and_size_apply(client):
    c, _ = client
    ok = c.post(
        "/api/experiment",
        json={"seed": 9, "world": {"width": 24, "height": 16, "boundary_mode": "WRAP_PERIODIC"}},
    )
    assert ok.status_code == 200
    data = ok.json()
    assert data["world"]["width"] == 24
    assert data["world"]["height"] == 16
    assert data["world"]["aspect"] == 24 / 16
    assert data["header"]["world_size"] == {"width": 24, "height": 16}
    # body still on torus after steps
    c.post("/api/control/step", json={"n": 5})
    body = c.get("/api/state").json()["body"]
    assert 0 <= body["x"] < 24
    assert 0 <= body["y"] < 16


def test_supported_boundary_mode_in_experiment_panel(client):
    c, _ = client
    exp = c.get("/api/experiment").json()
    modes = exp["world"]["boundary"]["modes"]
    assert modes["WRAP_PERIODIC"]["status"] == "SUPPORTED"
    assert modes["CLOSED"]["status"] == "UNSUPPORTED"
