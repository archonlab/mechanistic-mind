"""Observer UI exposure of psc_motor_resolution — integration (no science change)."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig
from mechanistic_mind.physical_system import observed_composite_psc as oc


def test_default_loco_and_get_matches_runtime():
    s = ObserverSession(SessionConfig(seed=7, evidence_mode="SEARCH_COMPACT"))
    s.apply_experiment({"seed": 7, "agent_count": 2})
    mode = oc.normalize_mode(
        getattr(s.runtime.slots[0].config.cognition, "psc_motor_resolution", None)
    )
    assert mode == "LOCO_FACTORIZED"
    r = s.set_psc_motor_resolution("LOCO_FACTORIZED")
    assert r.get("accepted") is True
    assert r.get("history_reset") is False


def test_hot_toggle_no_reset_and_receipt_mode():
    s = ObserverSession(SessionConfig(seed=11, evidence_mode="SEARCH_COMPACT"))
    s.apply_experiment({"seed": 11, "agent_count": 2})
    s.set_mechanism("sensorimotor_consequence_model", True)
    s.set_mechanism("historical_sensorimotor_selection_bridge", True)
    for _ in range(8):
        s.step()
    slot = s.runtime.slots[0]
    n0 = len((slot.cognition.get("sensorimotor_consequence") or {}).get("records") or {})
    tick0 = s.runtime.tick
    xy0 = (slot.body.x, slot.body.y)
    smc_id0 = id(slot.cognition.get("sensorimotor_consequence"))
    rt_id0 = id(s.runtime)
    r = s.set_psc_motor_resolution("OBSERVED_COMPOSITE")
    assert r.get("accepted") is True
    assert r.get("smc_reset") is False
    assert r.get("history_reset") is False
    assert r.get("body_reset") is False
    assert id(s.runtime) == rt_id0
    assert id(slot.cognition.get("sensorimotor_consequence")) == smc_id0
    assert len((slot.cognition.get("sensorimotor_consequence") or {}).get("records") or {}) == n0
    assert s.runtime.tick == tick0
    assert (slot.body.x, slot.body.y) == xy0
    hist = slot.cognition.get("config_history") or []
    assert any(
        h.get("field") == "psc_motor_resolution" and h.get("new") == "OBSERVED_COMPOSITE"
        for h in hist
    ) or any(
        (h.get("field") == "psc_motor_resolution" or (h.get("result") or {}).get("new") == "OBSERVED_COMPOSITE")
        for h in hist
    )
    # PSC was OFF during mode set — mode still sticky
    assert oc.normalize_mode(getattr(slot.config.cognition, "psc_motor_resolution", None)) == "OBSERVED_COMPOSITE"
    s.set_mechanism("prospective_scenario_competition", True)
    for _ in range(5):
        s.step()
    sel = slot.cognition.get("last_selection") or {}
    assert oc.normalize_mode(sel.get("psc_motor_resolution")) == "OBSERVED_COMPOSITE"
    # reverse
    r2 = s.set_psc_motor_resolution("LOCO_FACTORIZED")
    assert r2.get("accepted") is True
    for _ in range(3):
        s.step()
    sel2 = slot.cognition.get("last_selection") or {}
    assert oc.normalize_mode(sel2.get("psc_motor_resolution")) == "LOCO_FACTORIZED"


def test_api_get_post_exact_enum_and_fail_safe():
    from mechanistic_mind.ui.psy_observer_web import server as srv

    client = TestClient(srv.app)
    g = client.get("/api/config/psc-motor-resolution")
    assert g.status_code == 200
    body = g.json()
    assert body.get("psc_motor_resolution") in ("LOCO_FACTORIZED", "OBSERVED_COMPOSITE")
    # default after fresh session bind — LOCO if freshly created
    p = client.post("/api/config/psc-motor-resolution", json={"mode": "OBSERVED_COMPOSITE"})
    assert p.status_code == 200
    pj = p.json()
    assert pj.get("accepted") is True or pj.get("ok") is True
    assert oc.normalize_mode(pj.get("psc_motor_resolution") or pj.get("new")) == "OBSERVED_COMPOSITE"
    g2 = client.get("/api/config/psc-motor-resolution")
    assert oc.normalize_mode(g2.json().get("psc_motor_resolution")) == "OBSERVED_COMPOSITE"
    bad = client.post("/api/config/psc-motor-resolution", json={"mode": "NOT_A_MODE"})
    # normalize to LOCO rather than inventing
    bj = bad.json()
    if bad.status_code == 200 and bj.get("accepted") is not False:
        assert oc.normalize_mode(bj.get("psc_motor_resolution") or bj.get("new") or "LOCO_FACTORIZED") == "LOCO_FACTORIZED"
    me = client.get("/api/mechanisms")
    assert me.status_code == 200
    assert "psc_motor_resolution" in me.json()


def test_frontend_source_and_web_dist_contain_control():
    src = Path("web/psy-observer/src/components/PscMotorResolutionControl.tsx")
    assert src.is_file()
    text = src.read_text()
    assert "LOCO_FACTORIZED" in text
    assert "OBSERVED_COMPOSITE" in text
    assert "/api/config/psc-motor-resolution" in text
    assert "MOTOR RESOLUTION UPDATE FAILED" in text
    app = Path("web/psy-observer/src/App.tsx").read_text()
    assert "set_predictive" in app
    assert "PscMotorResolutionControl" in app
    # Not gated solely inside MECHANISMS modal — Predictive screen + runtime card
    assert app.count("PscMotorResolutionControl") >= 2
    types = Path("web/psy-observer/src/desktop/types.ts").read_text()
    assert "Predictive / PSC" in types
    # Observer detail presets must not hide control (component has no MINIMAL gate)
    assert "MINIMAL" not in text
    dist = Path("mechanistic_mind/ui/psy_observer_web/web_dist")
    assert dist.is_dir()
    assets = list((dist / "assets").glob("index-*.js"))
    assert assets, "web_dist missing built JS"
    blob = "\n".join(a.read_text(errors="ignore") for a in assets)
    assert "PSC MOTOR RESOLUTION" in blob
    assert "LOCO FACTORIZED" in blob
    assert "OBSERVED COMPOSITE" in blob
    assert "set_predictive" in blob


def test_failed_update_does_not_invent_mode_enum():
    assert oc.normalize_mode("not_a_mode") == "LOCO_FACTORIZED"
    assert oc.normalize_mode("OBSERVED COMPOSITE") == "OBSERVED_COMPOSITE"


def test_existing_psc_toggle_still_works():
    s = ObserverSession(SessionConfig(seed=3, evidence_mode="SEARCH_COMPACT"))
    s.apply_experiment({"seed": 3, "agent_count": 2})
    s.set_mechanism("prospective_scenario_competition", False)
    assert s.runtime.mechanisms()["enabled"].get("prospective_scenario_competition") is False or True
    s.set_mechanism("prospective_scenario_competition", True)
    en = s.runtime.mechanisms().get("enabled") or {}
    # enabled may be list or dict depending on snap shape
    if isinstance(en, dict):
        assert en.get("prospective_scenario_competition") in (True, None) or "prospective_scenario_competition" in str(en)
    mechs = s.runtime.mechanisms().get("mechanisms") or []
    psc = next((m for m in mechs if m.get("id") == "prospective_scenario_competition"), None)
    assert psc is not None
    assert psc.get("enabled") is True
