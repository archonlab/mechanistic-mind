"""Canonical experiment config: cross-tab Apply/Reset must not wipe unrelated fields.

BUG_REPRODUCED (pre-fix): YES
Trigger: APPLY & RESET WORLD with public_preset=BETA3_RECOMMENDED and no mechanisms
  (Observer default dropdown) OR a partial mechanisms dict + apply_fresh_defaults.
Root cause: apply_experiment treated Beta 3 preset as a full replacement and filled
  omitted experimental keys from fresh defaults (OFF).
"""
from __future__ import annotations

from mechanistic_mind.physical_system.experiment_canonical import (
    PRESET_BETA31,
    canonical_fingerprint,
    compare_requested_runtime,
    mechanism_intent_table,
    merge_canonical,
    preset_canonical,
    registered_mechanism_ids,
    runtime_readback,
)
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig

WORLD = {"width": 16, "height": 16, "boundary_mode": "WRAP_PERIODIC"}

BETA31_ON = {
    "sensorimotor_consequence_model": True,
    "historical_sensorimotor_selection_bridge": True,
    "contextual_predictive_organization": True,
    "context_grounded_prospection": True,
    "persistent_prospective_control": True,
    "predictive_conflict": True,
    "future_sensitive_action": True,
    "prediction_error_revision": True,
    "temporal_prediction_error": True,
    "predicted_context_prospection": True,
    "multistep_action_prospection": True,
    "physical_near_field_vision": True,
}

VISION_RICH = {
    "enabled": True,
    "radius": 3,
    "visual_surface_discrimination": "RICH",
    "optical_mapping": "INDEPENDENT",
    "spatial_vision": "OCCLUSION",
}


def _en(sess: ObserverSession) -> dict:
    return dict((sess.runtime.mechanisms() or {}).get("enabled") or {})


def _nfe(sess: ObserverSession):
    slots = getattr(sess.runtime, "slots", None)
    cfg = slots[0].config if slots else sess.runtime.config
    return getattr(cfg, "near_field_exteroception", None)


def _assert_on(en: dict, keys=BETA31_ON) -> None:
    missing = [k for k, v in keys.items() if v is True and en.get(k) is not True]
    assert not missing, missing


def test_historical_beta3_preset_without_map_is_explicit_load():
    """Documented old UI path: named preset + omitted mechanisms still loads that preset."""
    s = ObserverSession(SessionConfig(seed=17, buffer_capacity=8))
    s.apply_experiment({"seed": 17, "agent_count": 2, "world": WORLD, "mechanisms": dict(BETA31_ON)})
    assert _en(s).get("predictive_conflict") is True
    s.apply_experiment({
        "seed": 17,
        "cognition_enabled": True,
        "public_preset": "BETA3_RECOMMENDED",
        "world": WORLD,
    })
    after = _en(s)
    assert after.get("predictive_conflict") is not True
    assert after.get("physical_near_field_vision") is True


def test_partial_payload_preserves_unrelated_mechanisms_and_vision():
    s = ObserverSession(SessionConfig(seed=21, buffer_capacity=8))
    s.apply_experiment({
        "seed": 21,
        "agent_count": 2,
        "world": WORLD,
        "mechanisms": dict(BETA31_ON),
        "vision": dict(VISION_RICH),
        "agent_body": {"mass": 2.5, "v_max": 0.25},
        "ecology_preset": "BASELINE_CLIMATE_DEFAULT",
    })
    # Vision-only apply (the researcher World/Vision tab path).
    s.apply_experiment({
        "seed": 21,
        "agent_count": 2,
        "world": WORLD,
        "vision": {
            "radius": 3,
            "visual_surface_discrimination": "RICH",
            "spatial_vision": "OCCLUSION",
        },
    })
    _assert_on(_en(s))
    nfe = _nfe(s)
    assert str(nfe.spatial_vision).upper() == "OCCLUSION"
    assert str(nfe.visual_surface_discrimination).upper() == "RICH"
    assert int(nfe.radius) == 3
    assert abs(float(s.runtime.slots[0].config.body.mass) - 2.5) < 1e-9


def test_cognition_apply_preserves_vision():
    s = ObserverSession(SessionConfig(seed=22, buffer_capacity=8))
    s.apply_experiment({
        "seed": 22,
        "agent_count": 2,
        "world": WORLD,
        "mechanisms": dict(BETA31_ON),
        "vision": dict(VISION_RICH),
    })
    s.apply_experiment({
        "seed": 22,
        "mechanisms": {
            "predictive_conflict": True,
            "future_sensitive_action": True,
        },
    })
    nfe = _nfe(s)
    assert str(nfe.spatial_vision).upper() == "OCCLUSION"
    assert str(nfe.visual_surface_discrimination).upper() == "RICH"
    _assert_on(_en(s))


def test_ecology_apply_preserves_predictive_and_vision():
    s = ObserverSession(SessionConfig(seed=23, buffer_capacity=8))
    s.apply_experiment({
        "seed": 23,
        "agent_count": 2,
        "world": WORLD,
        "mechanisms": dict(BETA31_ON),
        "vision": dict(VISION_RICH),
    })
    s.apply_experiment({
        "seed": 23,
        "ecology_preset": "CURRENT_LEGACY",
        "world": WORLD,
    })
    _assert_on(_en(s))
    nfe = _nfe(s)
    assert str(nfe.spatial_vision).upper() == "OCCLUSION"


def test_body_apply_preserves_cognition():
    s = ObserverSession(SessionConfig(seed=24, buffer_capacity=8))
    s.apply_experiment({
        "seed": 24,
        "agent_count": 2,
        "world": WORLD,
        "mechanisms": dict(BETA31_ON),
        "vision": dict(VISION_RICH),
        "agent_body": {"mass": 1.0, "v_max": 0.4},
    })
    s.apply_experiment({"seed": 24, "agent_body": {"mass": 3.0, "v_max": 0.2}})
    _assert_on(_en(s))
    assert abs(float(s.runtime.slots[0].config.body.mass) - 3.0) < 1e-9
    nfe = _nfe(s)
    assert str(nfe.spatial_vision).upper() == "OCCLUSION"


def test_multi_apply_sequence_preserves_full_config():
    s = ObserverSession(SessionConfig(seed=25, buffer_capacity=8))
    s.apply_experiment({
        "seed": 25,
        "load_preset": True,
        "public_preset": PRESET_BETA31,
        "world": WORLD,
        "mechanisms": dict(BETA31_ON),
        "vision": dict(VISION_RICH),
        "agent_body": {"mass": 2.0, "v_max": 0.3},
    })
    s.apply_experiment({"vision": {"radius": 2, "spatial_vision": "ANGULAR"}})
    s.apply_experiment({"mechanisms": {"temporal_prediction_error": True}})
    s.apply_experiment({"agent_body": {"mass": 2.2}})
    s.apply_experiment({"vision": {"radius": 3, "spatial_vision": "OCCLUSION", "visual_surface_discrimination": "RICH"}})
    en = _en(s)
    _assert_on(en)
    nfe = _nfe(s)
    assert int(nfe.radius) == 3
    assert str(nfe.spatial_vision).upper() == "OCCLUSION"
    assert abs(float(s.runtime.slots[0].config.body.mass) - 2.2) < 1e-9
    rec = s.applied_configuration_receipt()
    assert rec["runtime"]["source"].startswith("runtime")
    cmp = compare_requested_runtime(s._canonical_requested, runtime_readback(s.runtime, pe_cold=True))
    mech_mismatch = [m for m in cmp["mismatches"] if str(m["field"]).startswith("mechanisms.")]
    # Every requested True/False that exists on runtime must match.
    for k, v in BETA31_ON.items():
        assert bool(en.get(k)) is bool(v), (k, en.get(k), v)


def test_beta31_preset_registered_mechanisms_match_runtime():
    s = ObserverSession(SessionConfig(seed=31, buffer_capacity=8))
    expected = preset_canonical(PRESET_BETA31, seed=31)
    s.apply_experiment({"seed": 31, "load_preset": True, "public_preset": PRESET_BETA31, "world": WORLD})
    rec = s.applied_configuration_receipt()
    assert rec["match"] or not [
        m for m in rec["mismatches"]
        if str(m["field"]).startswith("mechanisms.")
        or str(m["field"]).startswith("vision.")
    ], rec["mismatches"]
    en = _en(s)
    for mid, want in expected["mechanisms"].items():
        if mid not in en:
            continue
        assert bool(en[mid]) is bool(want), (mid, en[mid], want)
    intent = {r["mechanism"]: r for r in mechanism_intent_table()}
    assert intent["contextual_predictive_organization"]["beta31"] is True
    assert intent["predictive_conflict"]["beta31"] is False


def test_fingerprint_stable_and_causal():
    a = preset_canonical(PRESET_BETA31, seed=17)
    b = preset_canonical(PRESET_BETA31, seed=17)
    assert canonical_fingerprint(a) == canonical_fingerprint(b)
    c = merge_canonical(a, {"vision": {"spatial_vision": "OCCLUSION", "visual_surface_discrimination": "RICH"}})
    assert canonical_fingerprint(c) != canonical_fingerprint(a)
    # Observer-only keys must not exist on the canonical payload / must not change fp.
    noisy = dict(a)
    noisy["observer_theme"] = "light"
    noisy["selected_tab"] = "vision"
    noisy["fpv_preview_rate"] = "5 FPS"
    assert canonical_fingerprint(noisy) == canonical_fingerprint(a)


def test_runtime_readback_is_not_request_echo():
    s = ObserverSession(SessionConfig(seed=41, buffer_capacity=8))
    s.apply_experiment({
        "seed": 41,
        "agent_count": 2,
        "world": WORLD,
        "mechanisms": dict(BETA31_ON),
        "vision": dict(VISION_RICH),
    })
    rec = s.applied_configuration_receipt()
    assert rec["runtime"]["source"].startswith("runtime")
    assert rec["requested"]["fingerprint"]
    assert rec["runtime"]["fingerprint"]
    assert rec["runtime"]["vision"]["spatial_vision"] == "OCCLUSION"


def test_registered_ids_nonempty():
    ids = registered_mechanism_ids()
    assert "physical_near_field_vision" in ids
    assert "contextual_predictive_organization" in ids
    assert len(ids) >= 20
