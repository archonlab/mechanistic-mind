"""Observer LIVE Spatial Vision control — wiring only, sampler unchanged."""
from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

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


def _nfe(sess):
    rt = sess.runtime
    slots = getattr(rt, "slots", None)
    if slots:
        return getattr(slots[0].config, "near_field_exteroception", None)
    return getattr(getattr(rt, "config", None), "near_field_exteroception", None)


def test_spatial_vision_get_and_post(client):
    c, sess = client
    got = c.get("/api/vision/spatial-vision").json()
    assert got["mode"] == "LEGACY"
    assert got["path"] == "near_field_exteroception.spatial_vision"
    assert got["runtime"] == "PhysicalSystemRuntime.set_spatial_vision"
    assert "ANGULAR" in got["options"]

    out = c.post("/api/vision/spatial-vision", json={"mode": "OCCLUSION"}).json()
    assert out["control_receipt"]["accepted"] is True
    assert out["control_receipt"]["operation"] == "SET_SPATIAL_VISION"
    snap = out["spatial_vision"]
    assert snap["accepted"] is True
    assert snap["new"] == "OCCLUSION"
    assert snap["history_reset"] is False
    assert _nfe(sess).spatial_vision == "OCCLUSION"

    frame = c.get("/api/state").json()
    phys = (frame.get("physical") or {})
    nfe = phys.get("near_field_exteroception") or {}
    assert str(nfe.get("spatial_vision")).upper() == "OCCLUSION"

    obs = (frame.get("perception") or {}).get("agent_observation") or frame.get("agent_observation") or {}
    # Compact state may nest observation; also check selected agent view.
    if "spatial_exo_a0" not in obs:
        av = ((frame.get("agents_views") or {}).get("agent_0") or {}).get("observation") or {}
        obs = av or obs
    assert "exo_0" in obs
    assert "spatial_exo_a0" in obs
    assert "spatial_exo_a4" in obs

    c.post("/api/vision/spatial-vision", json={"mode": "LEGACY"})
    assert _nfe(sess).spatial_vision == "LEGACY"
    frame2 = c.get("/api/state").json()
    obs2 = (frame2.get("perception") or {}).get("agent_observation") or frame2.get("agent_observation") or {}
    if "exo_0" not in obs2:
        obs2 = ((frame2.get("agents_views") or {}).get("agent_0") or {}).get("observation") or obs2
    assert "exo_0" in obs2
    assert "spatial_exo_a0" not in obs2
