"""Demand-driven Observer detail: subscriptions, presets, EXACT_MATCH."""
from __future__ import annotations

from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig
from mechanistic_mind.ui.psy_observer_web.subscriptions import (
    PRESET_MINIMAL,
    PRESET_NORMAL,
    PRESET_FULL,
    PRODUCT_SMC,
    PRODUCT_COGNITION,
    PRODUCT_GRAPHS,
)


def _actions(preset: str, n: int = 20) -> list:
    s = ObserverSession(SessionConfig(seed=733, evidence_mode="SEARCH_COMPACT"))
    s.set_observer_detail_preset(preset)
    out = []
    for _ in range(n):
        s.step()
        last = (getattr(s.runtime, "cognition", None) or {}).get("last_selection") or {}
        out.append(last.get("action") or last.get("selected_action"))
    return out, int(s.runtime.tick)


def test_presets_defined():
    assert PRODUCT_SMC in PRESET_NORMAL
    assert PRODUCT_SMC not in PRESET_MINIMAL
    assert PRODUCT_COGNITION in PRESET_FULL
    assert PRODUCT_GRAPHS in PRESET_FULL
    assert PRODUCT_GRAPHS not in PRESET_MINIMAL


def test_minimal_defers_smc_panel():
    s = ObserverSession(SessionConfig(seed=11, evidence_mode="SEARCH_COMPACT"))
    s.set_observer_detail_preset("MINIMAL")
    p = s.sensorimotor_consequence_panel()
    assert p.get("status") == "DEFERRED"
    s.set_observer_detail_preset("NORMAL")
    p2 = s.sensorimotor_consequence_panel()
    assert p2.get("status") != "DEFERRED" or "agents" in p2


def test_mode_switch_no_runtime_reset():
    s = ObserverSession(SessionConfig(seed=41, evidence_mode="SEARCH_COMPACT"))
    for _ in range(5):
        s.step()
    tick = int(s.runtime.tick)
    rt_id = id(s.runtime)
    gen = int(s._runtime_generation)
    s.set_observer_detail_preset("MINIMAL")
    s.set_observer_detail_preset("FULL")
    s.set_observer_detail_preset("NORMAL")
    assert int(s.runtime.tick) == tick
    assert id(s.runtime) == rt_id
    assert int(s._runtime_generation) == gen


def test_subscription_add_remove():
    s = ObserverSession(SessionConfig(seed=7, evidence_mode="SEARCH_COMPACT"))
    s.set_observer_detail_preset("MINIMAL")
    assert not s._observer_interest.wants(PRODUCT_SMC)
    s.update_observer_product(PRODUCT_SMC, True)
    assert s._observer_interest.wants(PRODUCT_SMC)
    s.update_observer_product(PRODUCT_SMC, False)
    assert not s._observer_interest.wants(PRODUCT_SMC)


def test_minimal_skips_cognition_producer():
    s = ObserverSession(SessionConfig(seed=19, evidence_mode="SEARCH_COMPACT"))
    s.set_observer_detail_preset("MINIMAL")
    s._observer_interest.producer_calls.clear()
    for _ in range(8):
        s.step()
    assert s._observer_interest.producer_calls.get(PRODUCT_COGNITION, 0) == 0
    assert s._observer_interest.producer_calls.get("world", 0) >= 8


def test_exact_match_across_presets():
    a_min, t_min = _actions("MINIMAL")
    a_norm, t_norm = _actions("NORMAL")
    a_full, t_full = _actions("FULL")
    assert t_min == t_norm == t_full
    assert a_min == a_norm == a_full


def test_api_route_registered():
    from mechanistic_mind.ui.psy_observer_web import server as srv
    paths = {getattr(r, "path", None) for r in srv.app.routes}
    assert "/api/observer/detail" in paths


def test_frontend_control_present():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    hdr = (root / "web" / "psy-observer" / "src" / "chrome" / "ObserverHeader.tsx").read_text()
    ctrl = (root / "web" / "psy-observer" / "src" / "components" / "ObserverDetailControl.tsx").read_text()
    assert hdr.count("<ObserverDetailControl") == 1
    assert "EVIDENCE" in hdr
    assert "OBSERVER" in ctrl and "MINIMAL" in ctrl and "NORMAL" in ctrl and "FULL" in ctrl
    assert "Panels" in ctrl
    dist_assets = list((root / "mechanistic_mind" / "ui" / "psy_observer_web" / "web_dist" / "assets").glob("index-*.js"))
    assert dist_assets
    blob = dist_assets[0].read_text(errors="ignore")
    assert "OBSERVER" in blob and "MINIMAL" in blob and "Panels" in blob
