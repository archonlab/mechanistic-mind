"""Left Eye dock: demand-driven capture; CLOSED/OPEN and Preview do not change cognition."""
from __future__ import annotations

from copy import deepcopy

from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig
from mechanistic_mind.ui.psy_observer_web.tiktaalik_eye import build_agent_eye


def _pose(rt):
    slots = getattr(rt, "slots", None)
    bodies = slots if slots else [rt]
    return [
        {
            "x": float(b.body.x if hasattr(b, "body") else b.x),
            "y": float(b.body.y if hasattr(b, "body") else b.y),
            "theta": float(getattr(b.body if hasattr(b, "body") else b, "theta", 0.0)),
        }
        for b in bodies
    ]


def _obs(rt):
    slots = getattr(rt, "slots", None)
    if slots:
        return [deepcopy(s.last_agent_observation) for s in slots]
    return deepcopy(rt.last_agent_observation)


def _actions(rt):
    slots = getattr(rt, "slots", None)
    if slots:
        out = []
        for s in slots:
            last = (s.cognition or {}).get("last_selection") or {}
            out.append(last.get("action") or last.get("selected_action") or s.last_selected_action)
        return out
    last = (rt.cognition or {}).get("last_selection") or {}
    return last.get("action") or last.get("selected_action")


def test_eye_closed_vs_open_semantic_equivalence():
    def run(*, capture: bool):
        s = ObserverSession(SessionConfig(seed=91, evidence_mode="SEARCH_COMPACT"))
        if capture:
            s.set_tiktaalik_eye(rate="2FPS", fpv=True)
        else:
            s.set_tiktaalik_eye(rate="OFF", fpv=False)
        for _ in range(8):
            s.step()
        return _actions(s.runtime), _obs(s.runtime), _pose(s.runtime), int(s.runtime.tick)

    a, oa, pa, ta = run(capture=False)
    b, ob, pb, tb = run(capture=True)
    assert ta == tb
    assert a == b
    assert oa == ob
    assert pa == pb


def test_preview_off_vs_2fps_semantic_equivalence():
    def run(rate: str):
        s = ObserverSession(SessionConfig(seed=44, evidence_mode="SEARCH_COMPACT"))
        s.set_tiktaalik_eye(rate=rate, fpv=rate != "OFF")
        for _ in range(6):
            s.step()
        return _actions(s.runtime), _obs(s.runtime), deepcopy(s.runtime.cognition.get("metrics"))

    a, oa, ma = run("OFF")
    b, ob, mb = run("2FPS")
    assert a == b
    assert oa == ob
    assert ma == mb


def test_closed_dock_stops_fpv_receipts():
    s = ObserverSession(SessionConfig(seed=7, evidence_mode="SEARCH_COMPACT"))
    s.set_tiktaalik_eye(rate="5FPS", fpv=True)
    s.step()
    with s._lock:
        on = s._capture_locked()
    assert (on.get("tiktaalik_eye") or {}).get("fpv_included") is True
    s.set_tiktaalik_eye(rate="OFF", fpv=False)
    s.step()
    with s._lock:
        off = s._capture_locked()
    eye = off.get("tiktaalik_eye") or {}
    assert eye.get("status") == "OFF"
    assert eye.get("fpv_included") is False


def test_spatial_surface_bins_observer_only():
    s = ObserverSession(SessionConfig(seed=17, evidence_mode="SEARCH_COMPACT"))
    s.set_spatial_vision("OCCLUSION")
    if hasattr(s.runtime, "set_visual_surface_discrimination"):
        s.runtime.set_visual_surface_discrimination("RICH")
    s.step()
    rt = s.runtime
    obs = rt.last_agent_observation
    nfe = rt.config.near_field_exteroception if hasattr(rt, "config") else rt.slots[0].config.near_field_exteroception
    eye = build_agent_eye(agent_id="agent_0", observation=obs, prev_visual=None, nfe=nfe)
    spat = eye["accessible"].get("spatial_exo") or {}
    assert spat.get("present") is True
    assert len(spat.get("bins") or []) == 5
    assert (eye["accessible"].get("spatial_surface_c0") or {}).get("present") is True
