"""Public Beta 3 recommended Observer preset (packaging / UI, not CognitionConfig)."""
from __future__ import annotations

from mechanistic_mind.physical_system import CognitionConfig
from mechanistic_mind.physical_system import observed_composite_psc as oc
from mechanistic_mind.physical_system.mechanism_configuration import (
    CLIMATE_MECHANISM_ID,
    fresh_experiment_default_map,
)
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig


def test_low_level_cognition_default_remains_loco_factorized():
    assert CognitionConfig().psc_motor_resolution == "LOCO_FACTORIZED"


def test_fresh_map_psc_and_climate_off():
    d = fresh_experiment_default_map()
    assert d["prospective_scenario_competition"] is False
    assert d[CLIMATE_MECHANISM_ID] is False


def test_apply_experiment_without_preset_keeps_loco():
    s = ObserverSession(config=SessionConfig(seed=7))
    s.apply_experiment({"seed": 7, "agent_count": 2})
    mode = oc.normalize_mode(
        getattr(s.runtime.slots[0].config.cognition, "psc_motor_resolution", None)
    )
    assert mode == "LOCO_FACTORIZED"
    en = s.runtime.mechanisms()["enabled"]
    assert en.get("prospective_scenario_competition") is False
    assert en.get(CLIMATE_MECHANISM_ID) is False


def test_beta3_recommended_preset_two_agent_observed_composite():
    s = ObserverSession(config=SessionConfig(seed=19))
    out = s.apply_experiment({
        "seed": 19,
        "public_preset": "BETA3_RECOMMENDED",
        "cognition_enabled": True,
    })
    assert out.get("preflight", {}).get("status") == "READY"
    assert hasattr(s.runtime, "slots")
    assert len(s.runtime.slots) == 2
    mode = oc.normalize_mode(
        getattr(s.runtime.slots[0].config.cognition, "psc_motor_resolution", None)
    )
    assert mode == "OBSERVED_COMPOSITE"
    en = s.runtime.mechanisms()["enabled"]
    assert en.get("prospective_scenario_competition") is False
    assert en.get(CLIMATE_MECHANISM_ID) is False
    assert en.get("physical_near_field_vision") is True
    assert en.get("experimental_physical_signal") is True
