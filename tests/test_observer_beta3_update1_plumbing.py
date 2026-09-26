"""Beta 3 Update 1 — Observer plumbing (lifecycle, shadow, catalog, receipts)."""
from __future__ import annotations

import copy
import hashlib
import json
import time

import pytest

from mechanistic_mind.ui.psy_observer_web.serialize import experiment_config_frame, live_frame
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig
from mechanistic_mind.ui.psy_observer_web.subscriptions import PRODUCT_SIGNAL_SENSORIMOTOR


def _fp(rt) -> str:
    slots = getattr(rt, "slots", None) or [rt]
    bodies = []
    for s in slots:
        bodies.append({
            "x": round(float(s.body.x), 8),
            "y": round(float(s.body.y), 8),
            "vx": round(float(s.body.vx), 8),
            "vy": round(float(s.body.vy), 8),
            "action": s.last_selected_action,
        })
    payload = {"bodies": bodies, "tick": int(rt.tick), "T": float(rt.world.T.sum())}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _sess(**kw) -> ObserverSession:
    cfg = SessionConfig(seed=19, evidence_mode="SEARCH_COMPACT", buffer_capacity=32, **kw)
    return ObserverSession(cfg)


def test_save_failed_error_code_and_retryable_status():
    s = _sess()
    s.step(n=2)
    s.status = "SAVE_FAILED"
    err = s._lifecycle_error("STOP", "persistence_integrity_error: tick mismatch", code=None)
    assert err["code"] == "SAVE_FAILED"
    assert err["recoverable"] is True
    rec = s._with_receipt(
        s.current_frame(), "STOP", {"save": True}, s._control_state(),
        accepted=False, reason="persistence_integrity_error: tick mismatch",
    )["control_receipt"]
    assert rec["error"]["code"] == "SAVE_FAILED"
    assert rec["lifecycle_state"] == "SAVE_FAILED"
    assert rec["ok"] is False


def test_stop_without_save_succeeds_independently():
    s = _sess()
    s.step(n=1)
    out = s.stop(save=False, reason="USER_STOP_NO_SAVE")
    assert out["control_receipt"]["accepted"] is True
    assert s.status == "STOPPED"
    assert out["finalize"]["saved"] is False


def test_play_rejected_while_finalizing_has_code():
    s = _sess()
    s.status = "FINALIZING"
    out = s.play()
    rec = out["control_receipt"]
    assert rec["accepted"] is False
    assert rec["error"]["code"] == "INVALID_TRANSITION"
    assert "finalization" in rec["error"]["message"].lower()


def test_shadow_default_does_not_replay():
    s = _sess()
    s.set_observer_detail_preset("NORMAL")
    s.set_observer_product = getattr(s, "update_observer_product", None)
    if not s._observer_interest.wants(PRODUCT_SIGNAL_SENSORIMOTOR):
        s.update_observer_product(PRODUCT_SIGNAL_SENSORIMOTOR, True)
    for _ in range(4):
        s.step()
    before = int(s._psc_shadow_replay_count)
    p = s.signal_sensorimotor_panel()
    assert p.get("motor_resolution_shadow", {}).get("status") == "DEFERRED"
    assert int(s._psc_shadow_replay_count) == before


def test_shadow_requested_exact_and_increments():
    s = _sess()
    s.set_observer_detail_preset("NORMAL")
    if not s._observer_interest.wants(PRODUCT_SIGNAL_SENSORIMOTOR):
        s.update_observer_product(PRODUCT_SIGNAL_SENSORIMOTOR, True)
    for _ in range(6):
        s.step()
    a = s.signal_sensorimotor_panel(include_shadow=True)
    n = int(s._psc_shadow_replay_count)
    assert n >= 1
    b = s.signal_sensorimotor_panel(include_shadow=True)
    assert int(s._psc_shadow_replay_count) == n + 1
    assert a.get("motor_resolution_shadow", {}).get("status") != "DEFERRED" or a.get("motor_resolution_shadow")
    sa = json.dumps(a.get("motor_resolution_shadow"), sort_keys=True, default=str)
    sb = json.dumps(b.get("motor_resolution_shadow"), sort_keys=True, default=str)
    # Same tick, same store → exact shadow payload
    assert sa == sb


def test_hidden_panel_product_off_no_shadow():
    s = _sess()
    s.set_observer_detail_preset("MINIMAL")
    for _ in range(3):
        s.step()
    before = int(s._psc_shadow_replay_count)
    p = s.signal_sensorimotor_panel(include_shadow=True)
    shadow = p.get("motor_resolution_shadow") or {}
    top = str(p.get("status") or "")
    assert top == "DEFERRED" or shadow.get("status") == "DEFERRED"
    assert int(s._psc_shadow_replay_count) == before


def test_mechanism_warm_state_omits_catalog():
    s = _sess()
    warm = s.mechanisms_warm_state()
    assert warm["catalog_included"] is False
    assert "catalog" not in warm
    assert warm["mechanisms"]
    assert "label" not in (warm["mechanisms"][0] or {}) or warm["mechanisms"][0].get("label") is None
    blob = json.dumps(warm, default=str)
    assert len(blob.encode()) < 12_000


def test_toggle_updates_warm_state(monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    import mechanistic_mind.ui.psy_observer_web.server as server

    s = _sess()
    monkeypatch.setattr(server, "get_session", lambda: s)
    c = TestClient(server.app)
    full = c.get("/api/mechanisms").json()
    assert full.get("catalog_included") is True
    mid = "discrete_action_work_accounting"
    out = c.post(f"/api/mechanisms/{mid}", json={"enabled": False}).json()
    assert out["control_receipt"]["accepted"]
    warm = c.get("/api/mechanisms/state").json()
    row = next(m for m in warm["mechanisms"] if m["id"] == mid)
    assert row["enabled"] is False


def test_compact_experiment_omits_planet_dict():
    s = _sess()
    s.step(n=1)
    full = experiment_config_frame(s.runtime, detail="full")
    compact = experiment_config_frame(s.runtime, detail="compact")
    assert "mechanisms" not in compact
    assert compact["runtime"]["cognition_enabled"] == full["runtime"]["cognition_enabled"]
    assert len(json.dumps(compact, default=str)) < len(json.dumps(full, default=str))


def test_compact_frame_still_has_world_for_renderer():
    s = _sess()
    s.step(n=2)
    fr = live_frame(
        s.runtime, status="RUNNING", mode="LIVE", target_tick=None,
        previous_body=None, detail="compact",
    )
    assert fr["world"]["width"]
    assert fr["experiment"]["detail"] == "compact"
    assert "scalars" in fr["world"] or fr["world"].get("T") is not None or fr["world"].get("fields_available") is not None


def test_control_receipt_does_not_deepcopy_nested_identity():
    s = _sess()
    s.step(n=1)
    frame = s.current_frame()
    world_obj = frame.get("world")
    before = s._control_state()
    out = s._with_receipt(frame, "PAUSE", {}, before)
    assert out["world"] is world_obj
    assert "lifecycle_state" in out["control_receipt"]
    assert out["control_receipt"]["ok"] is True


def test_headless_display_frozen_no_new_capture_semantics():
    s = ObserverSession(SessionConfig(seed=19, execution_mode="HEADLESS", evidence_mode="SEARCH_COMPACT"))
    s.set_execution_mode("HEADLESS")
    s.status = "RUNNING"
    # Published compact frame at t0
    with s._step_lock:
        with s._lock:
            s._capture_locked(detail="compact")
    captured = int((s._published or {}).get("header", {}).get("tick") or 0)
    drops0 = int(s._capture_queue_drops)
    with s._step_lock:
        for _ in range(8):
            s._scientific_step_once_unlocked()
            with s._lock:
                s._accumulate_events_locked()
                s._append_scientific_locked()
    cur = s.current_frame()
    assert cur["header"]["display_frozen"] is True
    assert int(cur["header"]["sim_tick"]) >= captured
    assert int(s._capture_queue_drops) == drops0


def test_scientific_fingerprint_exact_match_live_headless():
    def run(mode: str) -> str:
        s = ObserverSession(SessionConfig(seed=19, execution_mode=mode, evidence_mode="SEARCH_COMPACT"))
        s.set_execution_mode(mode)
        with s._step_lock:
            for _ in range(30):
                s._scientific_step_once_unlocked()
        return _fp(s.runtime)

    assert run("LIVE") == run("HEADLESS")


def test_pause_play_step_isolated():
    s = _sess()
    p = s.play()
    assert p["control_receipt"]["accepted"]
    assert s.status == "RUNNING"
    pa = s.pause()
    assert pa["control_receipt"]["accepted"]
    assert s.status == "PAUSED"
    st = s.step(n=1)
    assert st["control_receipt"]["accepted"]
    assert s.status == "PAUSED"


def test_frontend_surfaces_save_failed_and_headless_copy():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    src = ""
    for rel in (
        "web/psy-observer/src/App.tsx",
        "web/psy-observer/src/chrome/LifecycleBanners.tsx",
        "web/psy-observer/src/chrome/ObserverHeader.tsx",
    ):
        src += (root / rel).read_text()
    assert "SAVE_FAILED" in src
    assert "void saveBanner" not in src
    assert "DISPLAY FROZEN" in src
    assert "/api/mechanisms/state" in (root / "web" / "psy-observer" / "src" / "App.tsx").read_text()
    panel = (root / "web" / "psy-observer" / "src" / "components" / "SignalSensorimotorPanel.tsx").read_text()
    assert "include_shadow" in panel
    dist = root / "mechanistic_mind" / "ui" / "psy_observer_web" / "web_dist"
    assets = list((dist / "assets").glob("index-*.js"))
    assert assets, "web_dist JS missing"
    blob = assets[0].read_text()
    assert "SAVE_FAILED" in blob
    assert "DISPLAY FROZEN" in blob
    assert "/api/mechanisms/state" in blob
