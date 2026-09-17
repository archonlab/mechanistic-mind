import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from mechanistic_mind.ui.psy_observer_web.server import app
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig


@pytest.fixture()
def client(monkeypatch):
    session = ObserverSession(SessionConfig(seed=17, buffer_capacity=16, ui_hz=20))
    import mechanistic_mind.ui.psy_observer_web.server as server
    monkeypatch.setattr(server, "get_session", lambda: session)
    return TestClient(app), session


def test_step_returns_atomic_control_receipt(client):
    c, _ = client
    out = c.post("/api/control/step", json={"n": 1}).json()
    assert out["control_receipt"]["operation"] == "STEP"
    assert out["control_receipt"]["accepted"]
    assert out["observation"]["tick_consistent"]


def test_toggle_is_runtime_confirmed_by_followup_api(client):
    c, session = client
    out = c.post(
        "/api/mechanisms/discrete_action_work_accounting",
        json={"enabled": False},
    ).json()
    assert out["control_receipt"]["accepted"]
    assert not session.runtime.config.discrete_action_work.enabled
    followup = c.get("/api/mechanisms").json()
    item = next(
        m for m in followup["mechanisms"]
        if m["id"] == "discrete_action_work_accounting"
    )
    assert item["enabled"] is False


def test_replay_is_read_only_and_missing_history_is_honest(client):
    c, session = client
    c.post("/api/control/step", json={"n": 3})
    before = session.runtime.snapshot()
    recorded_tick = session.history()["newest_tick"]
    recorded = c.get(f"/api/replay/{recorded_tick}").json()
    assert recorded["header"]["mode"] == "REPLAY"
    assert session.runtime.snapshot() == before
    missing = c.get("/api/replay/99999").json()
    assert missing["error"] == "NOT AVAILABLE"
    assert missing["header"]["mode"] == "REPLAY"
    assert missing["reason"].startswith("NOT_RECORDED")
    inspect_missing = c.get("/api/inspect/99999").json()
    assert inspect_missing["error"] == "NOT AVAILABLE"
    assert inspect_missing["header"]["mode"] == "INSPECT"
    assert inspect_missing["reason"].startswith("NOT_RECORDED")
    assert inspect_missing["header"]["live_runtime_tick"] == session.runtime.tick


def test_read_only_mechanism_rejected(client):
    c, session = client
    before = session.runtime.snapshot()
    out = c.post("/api/mechanisms/discrete_action_bridge", json={"enabled": False}).json()
    assert out["control_receipt"]["accepted"] is False
    assert "read-only" in (out["control_receipt"]["reason"] or "").lower()
    assert session.runtime.snapshot() == before


def test_cognition_and_morphology_toggles(client):
    c, session = client
    cognition = c.post("/api/mechanisms/predictive_compression", json={"enabled": False}).json()
    assert cognition["control_receipt"]["accepted"]
    assert cognition["control_receipt"]["operation"] == "TOGGLE_MECHANISM"
    assert not session.runtime.config.cognition.predictive_compression
    morph = c.post("/api/mechanisms/distributed_morphology", json={"enabled": False}).json()
    assert morph["control_receipt"]["accepted"]
    assert morph["control_receipt"]["reason"]
    assert "reset recommended" in morph["control_receipt"]["reason"]
    assert session.runtime.config.morphology_mechanics.mode == "OFF"


def test_world_resolution_labels(client):
    c, _ = client
    world = c.get("/api/state").json()["world"]
    assert world["runtime_resolution"] == {"width": world["width"], "height": world["height"]}
    assert world["transported_resolution"]["width"] == world["grid_shape_transported"]["width"]
    fields = c.get("/api/world/fields").json()
    assert fields["runtime_resolution"]["width"] == world["width"]
    assert fields["transported_resolution"]["height"] == world["transported_resolution"]["height"]


def test_ablations_return_control_receipt(client):
    c, session = client
    out = c.post("/api/ablations", json={"predictive_compression": False}).json()
    assert out["control_receipt"]["accepted"]
    assert out["control_receipt"]["operation"] == "SET_ABLATIONS"
    assert not session.runtime.config.cognition.predictive_compression


def test_integrated_gearbox_and_result_catalog_are_artifacts(client):
    c, _ = client
    graph = c.get("/api/evidence/gearbox").json()
    assert graph["status"] == "AVAILABLE"
    # Historical artifact keeps its recorded name; live registry is Tiktaalik.
    assert graph["integrated"]["runtime_version"] == "CURRENT_INTEGRATED_MM"
    assert graph["live"]["runtime_version"] == "MM_1_0_TIKTAALIK"
    packs = c.get("/api/results/packs").json()
    assert packs["status"] == "CATALOG_ONLY"
    assert packs["analyzer"] == "NOT_AVAILABLE"

