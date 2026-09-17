"""RUNNING simulation must not starve Observer control/read APIs."""
from __future__ import annotations

import time

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from mechanistic_mind.ui.psy_observer_web.server import app
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig


CONTROL_TIMEOUT_S = 2.0


@pytest.fixture()
def client(monkeypatch):
    session = ObserverSession(SessionConfig(seed=17, buffer_capacity=64, ui_hz=20))
    import mechanistic_mind.ui.psy_observer_web.server as server
    monkeypatch.setattr(server, "get_session", lambda: session)
    yield TestClient(app), session
    session.stop()


def _timed(fn):
    t0 = time.perf_counter()
    out = fn()
    return out, time.perf_counter() - t0


def test_running_simulation_does_not_starve_control_api(client):
    c, session = client

    play, dt = _timed(lambda: c.post("/api/control/play"))
    assert play.status_code == 200
    body = play.json()
    assert body["control_receipt"]["accepted"]
    assert body["control_receipt"]["new_state"]["status"] == "RUNNING"
    assert dt < CONTROL_TIMEOUT_S
    assert session.runner_count() == 1

    time.sleep(0.25)
    t0 = int(session.runtime.tick)
    time.sleep(0.25)
    t1 = int(session.runtime.tick)
    assert t1 > t0, "PLAY must actually advance ticks"

    state, dt = _timed(lambda: c.get("/api/state"))
    assert state.status_code == 200
    assert dt < CONTROL_TIMEOUT_S
    inspect, dt = _timed(lambda: c.get("/api/inspect/0"))
    assert inspect.status_code == 200
    assert dt < CONTROL_TIMEOUT_S

    pause, dt = _timed(lambda: c.post("/api/control/pause"))
    assert pause.status_code == 200
    paused = pause.json()
    assert paused["control_receipt"]["accepted"]
    assert paused["control_receipt"]["new_state"]["status"] == "PAUSED"
    assert dt < CONTROL_TIMEOUT_S
    frozen = int(session.runtime.tick)
    time.sleep(0.2)
    assert int(session.runtime.tick) == frozen

    step, dt = _timed(lambda: c.post("/api/control/step", json={"n": 1}))
    assert step.status_code == 200
    assert step.json()["control_receipt"]["accepted"]
    assert int(session.runtime.tick) == frozen + 1
    assert dt < CONTROL_TIMEOUT_S

    play2, dt = _timed(lambda: c.post("/api/control/play"))
    assert play2.json()["control_receipt"]["accepted"]
    assert dt < CONTROL_TIMEOUT_S
    time.sleep(0.2)
    assert session.runner_count() == 1
    advancing = int(session.runtime.tick)
    time.sleep(0.2)
    assert int(session.runtime.tick) > advancing

    stop, dt = _timed(lambda: c.post("/api/control/stop"))
    assert stop.status_code == 200
    stopped = stop.json()
    assert stopped["control_receipt"]["accepted"]
    assert stopped["control_receipt"]["new_state"]["status"] == "STOPPED"
    assert dt < CONTROL_TIMEOUT_S
    frozen2 = int(session.runtime.tick)
    time.sleep(0.25)
    assert int(session.runtime.tick) == frozen2
    assert session.runner_count() == 0

    health, dt = _timed(lambda: c.get("/api/health"))
    assert health.status_code == 200
    assert dt < CONTROL_TIMEOUT_S

    for _ in range(3):
        c.post("/api/control/play")
        time.sleep(0.05)
        assert session.runner_count() == 1
        c.post("/api/control/pause")
        time.sleep(0.02)
        assert session.runner_count() == 1
    c.post("/api/control/play")
    time.sleep(0.05)
    assert session.runner_count() == 1
    c.post("/api/control/stop")
    time.sleep(0.05)
    assert session.runner_count() == 0
