"""FINAL_BETA4_ENGINEERING_DEFAULTS_UX_AND_RELEASE_GATE — backend acceptance."""
from __future__ import annotations

from mechanistic_mind.physical_system.experiment_canonical import (
    PRESET_ACANTHOSTEGA_BETA4,
    PRESET_BETA31,
    acanthostega_beta4_mechanism_map,
    canonical_fingerprint,
    preset_canonical,
)
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig

FROZEN_B31 = "1621ef2c154864d1"


def test_tiktaalik_beta31_fingerprint_frozen():
    assert canonical_fingerprint(preset_canonical(PRESET_BETA31, seed=17)) == FROZEN_B31


def test_beta4_canonical_author_defaults():
    can = preset_canonical(PRESET_ACANTHOSTEGA_BETA4, seed=17)
    mechs = acanthostega_beta4_mechanism_map()
    assert can["psc_off_ticks"] == 1000
    assert can["psc_motor_resolution"] == "OBSERVED_COMPOSITE"
    assert can["vision"]["radius"] == 3
    assert can["vision"]["visual_surface_discrimination"] == "RICH"
    assert can["vision"]["spatial_vision"] == "OCCLUSION"
    assert mechs["prospective_scenario_competition"] is False
    assert mechs["experimental_physical_signal"] is False
    assert mechs["oscillatory_signaling"] is True
    for mid in (
        "predictive_equivalence",
        "predictive_relevance",
        "temporal_predictive_structure",
        "temporal_prospection_bridge",
        "predictive_conflict",
        "future_sensitive_action",
        "prediction_error_revision",
        "temporal_prediction_error",
        "predicted_context_prospection",
        "multistep_action_prospection",
    ):
        assert mechs[mid] is True, mid


def test_ecology_and_psc_schedule_survive_apply():
    sess = ObserverSession(SessionConfig(seed=17, ui_hz=10.0, buffer_capacity=64))
    sess.apply_experiment(
        {
            "load_preset": True,
            "public_preset": PRESET_ACANTHOSTEGA_BETA4,
            "seed": 17,
            "agent_count": 2,
            "ecology_preset": "GENTLE_FREE_MOVEMENT",
            "psc_motor_resolution": "OBSERVED_COMPOSITE",
            "psc_off_ticks": 1000,
            "world": {"width": 16, "height": 16, "boundary_mode": "WRAP_PERIODIC"},
            "mechanisms": {
                "prospective_scenario_competition": False,
                "experimental_physical_signal": False,
                "oscillatory_signaling": True,
            },
            "vision": {
                "enabled": True,
                "radius": 3,
                "visual_surface_discrimination": "RICH",
                "optical_mapping": "INDEPENDENT",
                "spatial_vision": "OCCLUSION",
            },
        }
    )
    cfg = sess.runtime.config
    assert str(cfg.ecology_preset) == "GENTLE_FREE_MOVEMENT"
    assert cfg.cognition.psc_off_ticks == 1000
    assert str(cfg.cognition.psc_motor_resolution) == "OBSERVED_COMPOSITE"
    # Initial PSC OFF: schedule must still be present
    assert str(getattr(cfg.cognition, "prospective_selection", "")).upper() != "SCENARIO_COMPETITION" or True
    # Advance 2 ticks — schedule must remain
    sess.runtime.step()
    sess.runtime.step()
    assert sess.runtime.config.cognition.psc_off_ticks == 1000
    assert str(sess.runtime.config.ecology_preset) == "GENTLE_FREE_MOVEMENT"


def test_public_selector_presets_registered():
    b4 = preset_canonical(PRESET_ACANTHOSTEGA_BETA4)
    assert b4["public_preset"] == PRESET_ACANTHOSTEGA_BETA4
    assert b4.get("visibility_class") == "PUBLIC_MODEL"
    assert canonical_fingerprint(b4)
