"""Observer Web: O′→history→PSC bridge defaults, panel, and PSC hot-toggle."""
from __future__ import annotations

from pathlib import Path

from mechanistic_mind.physical_system.mechanism_configuration import (
    CLIMATE_MECHANISM_ID,
    fresh_experiment_default_map,
)
from mechanistic_mind.physical_system.mechanism_registry import MECHANISM_DEFS, mechanism_snapshot
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig

ROOT = Path(__file__).resolve().parents[1]


def test_fresh_defaults_experience_first():
    m = fresh_experiment_default_map()
    assert m["prospective_scenario_competition"] is False
    assert m[CLIMATE_MECHANISM_ID] is False
    assert m["sensorimotor_consequence_model"] is True
    assert m["historical_sensorimotor_selection_bridge"] is True


def test_new_observer_session_stamps_experience_first_defaults():
    s = ObserverSession(SessionConfig(seed=733))
    snap = mechanism_snapshot(s.runtime.config)
    en = snap["enabled"]
    assert en["prospective_scenario_competition"] is False
    assert en[CLIMATE_MECHANISM_ID] is False
    assert en["sensorimotor_consequence_model"] is True
    assert en["historical_sensorimotor_selection_bridge"] is True
    cog = s.runtime.config.cognition
    assert cog.sensorimotor_consequence_model is True
    assert cog.historical_sensorimotor_selection_bridge is True
    assert str(cog.prospective_selection).upper() != "SCENARIO_COMPETITION"
    store = s.runtime.cognition.get("sensorimotor_consequence") or {}
    assert store.get("enabled") is True


def test_mechanism_defs_and_snapshot_include_bridge():
    ids = {d["id"] for d in MECHANISM_DEFS}
    assert "sensorimotor_consequence_model" in ids
    assert "historical_sensorimotor_selection_bridge" in ids
    s = ObserverSession(SessionConfig(seed=11))
    snap = mechanism_snapshot(s.runtime.config)
    assert "sensorimotor_consequence_model" in snap["enabled"]
    assert "historical_sensorimotor_selection_bridge" in snap["enabled"]
    mechs = {m["id"]: m for m in snap["mechanisms"]}
    assert "historical_sensorimotor_selection_bridge" in mechs
    desc = (mechs["historical_sensorimotor_selection_bridge"].get("description") or "").lower()
    assert "history" in desc and "prospective" in desc


def test_panel_ready_then_active_on_psc_hot_toggle():
    s = ObserverSession(SessionConfig(seed=41))
    p0 = s.historical_sensorimotor_selection_panel()
    assert p0["ui_state"] == "READY"
    assert p0["bridge_enabled"] is True
    assert p0["psc_enabled"] is False

    smc_id = id(s.runtime.cognition.get("sensorimotor_consequence"))
    prosp_id = id(s.runtime.cognition.get("prospection"))
    rt_id = id(s.runtime)

    for _ in range(8):
        s.step()

    out = s.set_mechanism("prospective_scenario_competition", True)
    en = (out.get("mechanism_result") or {}).get("enabled") or mechanism_snapshot(s.runtime.config)["enabled"]
    assert en["prospective_scenario_competition"] is True
    assert id(s.runtime) == rt_id
    assert id(s.runtime.cognition.get("sensorimotor_consequence")) == smc_id
    assert id(s.runtime.cognition.get("prospection")) == prosp_id

    p1 = s.historical_sensorimotor_selection_panel()
    assert p1["ui_state"] == "ACTIVE"
    assert p1["psc_enabled"] is True
    assert p1["psc_enabled_after_ticks"] == 8


def test_diagnostics_api_route_registered():
    from mechanistic_mind.ui.psy_observer_web import server as srv

    paths = {getattr(r, "path", None) for r in srv.app.routes}
    assert "/api/diagnostics/historical-sensorimotor-selection" in paths


def test_frontend_sources_mount_panel_and_psc_guidance():
    app = (ROOT / "web" / "psy-observer" / "src" / "App.tsx").read_text()
    panel = (ROOT / "web" / "psy-observer" / "src" / "components" / "HistoricalSensorimotorSelectionPanel.tsx").read_text()
    assert "HistoricalSensorimotorSelectionPanel" in app
    assert "Recommended: let the organism explore" in app
    assert "historical-sensorimotor-selection" in panel
    dist = ROOT / "mechanistic_mind" / "ui" / "psy_observer_web" / "web_dist" / "index.html"
    assert dist.exists()
    assets = list((ROOT / "mechanistic_mind" / "ui" / "psy_observer_web" / "web_dist" / "assets").glob("index-*.js"))
    assert assets, "web_dist JS missing"
    blob = assets[0].read_text(errors="ignore")
    assert "HISTORICAL SENSORIMOTOR SELECTION" in blob or "HistoricalSensorimotor" in blob


def test_cognition_config_roundtrip_bridge_flags():
    from mechanistic_mind.physical_system.cognition import CognitionConfig

    cfg = CognitionConfig(
        sensorimotor_consequence_model=True,
        historical_sensorimotor_selection_bridge=True,
        historical_sensorimotor_selection_withhold=False,
        historical_sensorimotor_selection_shuffle=False,
    )
    d = cfg.to_dict()
    back = CognitionConfig.from_dict(d)
    assert back.historical_sensorimotor_selection_bridge is True
    assert back.sensorimotor_consequence_model is True


def test_two_agent_parity_bridge_defaults_if_available():
    try:
        from mechanistic_mind.physical_system.two_agent_runtime import TwoAgentRuntime
    except Exception:
        return
    # Prefer Observer two-agent session if SessionConfig supports it
    try:
        s = ObserverSession(SessionConfig(seed=733, n_agents=2))
    except TypeError:
        return
    if not hasattr(s.runtime, "slots"):
        return
    for slot in s.runtime.slots:
        cog = slot.config.cognition
        assert cog.sensorimotor_consequence_model is True
        assert cog.historical_sensorimotor_selection_bridge is True
        assert str(cog.prospective_selection).upper() != "SCENARIO_COMPETITION"
    p = s.historical_sensorimotor_selection_panel()
    assert p["ui_state"] == "READY"
    assert len(p["agents"]) >= 2
