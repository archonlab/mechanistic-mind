"""Acanthostega Phase 0 is a canonical preset with its own identity; Tiktaalik is unchanged."""
from __future__ import annotations

from copy import deepcopy

from mechanistic_mind.model.acanthostega import (
    MODEL_LINE as ACANTHOSTEGA_LINE,
    PHASE_LABEL,
    PUBLIC_PRESET as ACANTHOSTEGA_PRESET,
    RUNTIME_STAGE,
    acanthostega_config,
)
from mechanistic_mind.model.identity import RUNTIME_VERSION as TIKTAALIK_RUNTIME
from mechanistic_mind.model.lines import identity_for_config, stamp_config_from_preset
from mechanistic_mind.model.tiktaalik import MODEL_CODENAME, tiktaalik_config
from mechanistic_mind.physical_system.experiment_canonical import (
    PRESET_ACANTHOSTEGA,
    PRESET_BETA31,
    canonical_fingerprint,
    normalize_preset_name,
    preset_canonical,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.ui.psy_observer_web.serialize import header_info
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig

FROZEN_BETA31_FP_SEED17 = "1621ef2c154864d1"


def test_beta31_fingerprint_unchanged():
    assert canonical_fingerprint(preset_canonical(PRESET_BETA31, seed=17)) == FROZEN_BETA31_FP_SEED17


def test_unknown_preset_name_still_falls_through_to_beta31():
    assert normalize_preset_name("NOT_A_REAL_PRESET") is None
    body = preset_canonical("NOT_A_REAL_PRESET", seed=17)
    assert body["public_preset"] == PRESET_BETA31
    assert canonical_fingerprint(body) == FROZEN_BETA31_FP_SEED17


def test_acanthostega_phase0_is_distinct_preset():
    assert normalize_preset_name("Acanthostega Phase 0") == PRESET_ACANTHOSTEGA
    assert PRESET_ACANTHOSTEGA == "ACANTHOSTEGA_PHASE0"
    a = preset_canonical(PRESET_ACANTHOSTEGA, seed=17)
    t = preset_canonical(PRESET_BETA31, seed=17)
    assert a["public_preset"] == ACANTHOSTEGA_PRESET
    assert a["model_line"] == ACANTHOSTEGA_LINE
    assert t["public_preset"] == PRESET_BETA31
    assert a["public_preset"] != t["public_preset"]
    mech_a = dict(a["mechanisms"])
    mech_t = dict(t["mechanisms"])
    assert mech_a == mech_t
    assert a["psc_motor_resolution"] == t["psc_motor_resolution"]
    assert a["agent_count"] == t["agent_count"]


def test_default_runtime_identity_is_tiktaalik():
    rt = PhysicalSystemRuntime(seed=17)
    meta = rt.model_identity()
    assert meta["model_codename"] == MODEL_CODENAME
    assert meta["model_line"] == "TIKTAALIK"
    assert meta["runtime_version"] == TIKTAALIK_RUNTIME
    cfg = tiktaalik_config()
    assert identity_for_config(cfg)["model_codename"] == "Tiktaalik"


def test_tiktaalik_named_constructor_unchanged():
    rt = PhysicalSystemRuntime(model="tiktaalik", seed=17)
    meta = rt.model_identity()
    assert meta["model_codename"] == "Tiktaalik"
    assert meta["runtime_version"] == TIKTAALIK_RUNTIME
    snap = rt.snapshot()
    assert snap["model"]["model_codename"] == "Tiktaalik"
    assert snap["config"]["runtime_version"] == TIKTAALIK_RUNTIME


def test_acanthostega_identity_and_compatible_runtime():
    rt = PhysicalSystemRuntime(model="acanthostega", seed=17)
    meta = rt.model_identity()
    assert meta["model_line"] == ACANTHOSTEGA_LINE
    assert meta["model_codename"] == "Acanthostega"
    assert meta["public_preset"] == ACANTHOSTEGA_PRESET
    assert meta["runtime_version"] == TIKTAALIK_RUNTIME
    assert meta["runtime_stage"] == RUNTIME_STAGE
    assert meta["lifecycle_implemented"] is False
    assert PHASE_LABEL in meta["display_name"]
    assert rt.config.runtime_version == TIKTAALIK_RUNTIME
    rt.step()
    assert rt.tick == 1


def test_preset_is_authority_over_stray_model_line():
    cfg = tiktaalik_config()
    cfg.model_line = "ACANTHOSTEGA"
    cfg.public_preset = PRESET_BETA31
    stamp_config_from_preset(cfg, PRESET_BETA31)
    meta = identity_for_config(cfg)
    assert meta["model_line"] == "TIKTAALIK"
    assert meta["model_codename"] == "Tiktaalik"
    assert cfg.public_preset == PRESET_BETA31


def test_observer_apply_tiktaalik_and_acanthostega():
    s = ObserverSession(SessionConfig(seed=17, buffer_capacity=8))
    s.apply_experiment({
        "seed": 17,
        "load_preset": True,
        "public_preset": PRESET_BETA31,
        "world": {"width": 16, "height": 16, "boundary_mode": "WRAP_PERIODIC"},
    })
    ident = s.runtime.model_identity()
    assert ident["model_line"] == "TIKTAALIK"
    assert ident["model_codename"] == "Tiktaalik"
    assert s.runtime.config.runtime_version == TIKTAALIK_RUNTIME
    hdr = header_info(s.runtime, status="PAUSED", mode="LIVE", target_tick=None)
    assert hdr["model_line"] == "TIKTAALIK"
    assert hdr["snapshot_compatibility"] == "TIKTAALIK"
    assert "Tiktaalik" in str(hdr["experiment"])

    s.apply_experiment({
        "seed": 17,
        "load_preset": True,
        "public_preset": PRESET_ACANTHOSTEGA,
        "world": {"width": 16, "height": 16, "boundary_mode": "WRAP_PERIODIC"},
    })
    ident = s.runtime.model_identity()
    assert ident["model_line"] == ACANTHOSTEGA_LINE
    assert ident["public_preset"] == ACANTHOSTEGA_PRESET
    assert ident["runtime_version"] == TIKTAALIK_RUNTIME
    assert isinstance(s.runtime, TwoAgentRuntime)
    hdr = header_info(s.runtime, status="PAUSED", mode="LIVE", target_tick=None)
    assert hdr["model_line"] == ACANTHOSTEGA_LINE
    assert hdr["snapshot_compatibility"] == "ACANTHOSTEGA"
    assert "Acanthostega" in str(hdr["model_display_name"])
    s.runtime.step()
    assert int(s.runtime.tick) == 1


def test_incompatible_model_line_cannot_override_tiktaalik_preset():
    s = ObserverSession(SessionConfig(seed=17, buffer_capacity=8))
    s.apply_experiment({
        "seed": 17,
        "load_preset": True,
        "public_preset": PRESET_BETA31,
        "model_line": "ACANTHOSTEGA",
        "world": {"width": 16, "height": 16, "boundary_mode": "WRAP_PERIODIC"},
    })
    ident = s.runtime.model_identity()
    assert ident["model_line"] == "TIKTAALIK"
    assert ident["model_codename"] == "Tiktaalik"


def test_snapshot_restore_missing_identity_is_tiktaalik():
    rt = PhysicalSystemRuntime(model="tiktaalik", seed=17)
    rt.step()
    snap = rt.snapshot()
    snap = deepcopy(snap)
    snap["config"].pop("model_line", None)
    snap["config"].pop("public_preset", None)
    restored = PhysicalSystemRuntime.restore(snap)
    meta = restored.model_identity()
    assert meta["model_line"] == "TIKTAALIK"
    assert meta["model_codename"] == "Tiktaalik"


def test_acanthostega_snapshot_roundtrip():
    cfg = acanthostega_config()
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    snap = rt.snapshot()
    assert snap["model"]["model_line"] == ACANTHOSTEGA_LINE
    assert snap["config"]["model_line"] == ACANTHOSTEGA_LINE
    restored = PhysicalSystemRuntime.restore(snap)
    assert restored.model_identity()["model_line"] == ACANTHOSTEGA_LINE
    assert restored.config.runtime_version == TIKTAALIK_RUNTIME


def test_reset_without_preset_stays_tiktaalik():
    s = ObserverSession(SessionConfig(seed=17, buffer_capacity=8))
    s.apply_experiment({
        "seed": 17,
        "load_preset": True,
        "public_preset": PRESET_ACANTHOSTEGA,
        "world": {"width": 16, "height": 16, "boundary_mode": "WRAP_PERIODIC"},
    })
    s.reset(seed=17)
    assert s.runtime.model_identity()["model_codename"] == "Tiktaalik"
    s.reset(seed=17, public_preset=PRESET_ACANTHOSTEGA)
    assert s.runtime.model_identity()["model_line"] == ACANTHOSTEGA_LINE


def test_apply_experiment_returns_active_experiment_round_trip():
    s = ObserverSession(SessionConfig(seed=17, buffer_capacity=8))
    complete = deepcopy(preset_canonical(PRESET_ACANTHOSTEGA, seed=17))
    complete["ecology_preset"] = "GENTLE_FREE_MOVEMENT"
    complete["psc_motor_resolution"] = "OBSERVED_COMPOSITE"
    complete["pe_cold_history_eviction"] = False
    complete["agent_body"] = {"mass": 2.5, "v_max": 0.2}
    mechs = dict(complete.get("mechanisms") or {})
    mechs["spatiotemporal_climate_ecology"] = False
    mechs["prospective_scenario_competition"] = True
    complete["mechanisms"] = mechs
    vis = dict(complete.get("vision") or {})
    vis["radius"] = 1
    complete["vision"] = vis
    f = s.apply_experiment(complete)
    active = f.get("active_experiment") or {}
    assert f["header"]["tick"] == 0
    assert active.get("ecology_preset") == "GENTLE_FREE_MOVEMENT"
    assert active.get("psc_motor_resolution") == "OBSERVED_COMPOSITE"
    assert active.get("pe_cold_history_eviction") is False
    assert (active.get("mechanisms") or {}).get("spatiotemporal_climate_ecology") is False
    assert (active.get("mechanisms") or {}).get("prospective_scenario_competition") is True
    assert float((active.get("agent_body") or {}).get("mass") or 0) == 2.5
    assert int((active.get("vision") or {}).get("radius") or 0) == 1
    assert s.runtime.model_identity()["model_line"] == ACANTHOSTEGA_LINE
    live = s.current_frame()
    live_active = (live.get("experiment") or {}).get("active_experiment") or live.get("active_experiment") or {}
    assert live_active.get("ecology_preset") == "GENTLE_FREE_MOVEMENT"
    assert live_active.get("psc_motor_resolution") == "OBSERVED_COMPOSITE"
    assert live_active.get("pe_cold_history_eviction") is False
    rt_block = (live.get("experiment") or {}).get("runtime") or {}
    assert rt_block.get("psc_motor_resolution") == "OBSERVED_COMPOSITE"
    assert str(getattr(s.runtime.config, "ecology_preset", "")) == "GENTLE_FREE_MOVEMENT"
    assert str(getattr(s.runtime.config.cognition, "psc_motor_resolution", "")) == "OBSERVED_COMPOSITE"



def test_apply_experiment_atomic_acanthostega_with_tab_overrides():
    s = ObserverSession(SessionConfig(seed=17, buffer_capacity=8))
    complete = deepcopy(preset_canonical(PRESET_ACANTHOSTEGA, seed=17))
    complete["ecology_preset"] = "GENTLE_FREE_MOVEMENT"
    complete["agent_body"] = {"mass": 2.5, "v_max": 0.2}
    complete["cognition_enabled"] = True
    vis = dict(complete.get("vision") or {})
    vis["radius"] = 1
    complete["vision"] = vis
    f = s.apply_experiment(complete)
    assert f["control_receipt"]["accepted"]
    assert f["header"]["tick"] == 0
    ident = s.runtime.model_identity()
    assert ident["model_line"] == ACANTHOSTEGA_LINE
    assert ident["public_preset"] == PRESET_ACANTHOSTEGA
    eco = str(
        f.get("experiment", {}).get("ecology_preset")
        or getattr(s.runtime.config, "ecology_preset", "")
    )
    assert "GENTLE" in eco.upper()
    body = (f.get("experiment") or {}).get("agent_body") or {}
    mass = body.get("mass")
    if mass is None:
        cfg0 = (getattr(s.runtime, "slots", None) or [None])[0]
        mass = getattr(getattr(cfg0, "config", None), "mass", None) or getattr(
            getattr(s.runtime, "config", None), "mass", None
        )
    assert float(mass) == 2.5
    nfe = getattr(s.runtime.config, "near_field_exteroception", None)
    radius = int(getattr(nfe, "radius", 0) or 0)
    assert radius == 1


def test_acanthostega_overrides_keep_identity_and_mark_modified():
    s = ObserverSession(SessionConfig(seed=17, buffer_capacity=8))
    complete = deepcopy(preset_canonical(PRESET_ACANTHOSTEGA, seed=17))
    complete["ecology_preset"] = "GENTLE_FREE_MOVEMENT"
    complete["psc_motor_resolution"] = "OBSERVED_COMPOSITE"
    complete["pe_cold_history_eviction"] = False
    complete["agent_body"] = {"mass": 2.5, "v_max": 0.2}
    complete["cognition_enabled"] = True
    complete["model_line"] = "TIKTAALIK"
    vis = dict(complete.get("vision") or {})
    vis["radius"] = 1
    complete["vision"] = vis
    mechs = dict(complete.get("mechanisms") or {})
    mechs["prospective_scenario_competition"] = True
    complete["mechanisms"] = mechs
    f = s.apply_experiment(complete)
    ident = s.runtime.model_identity()
    assert ident["model_line"] == ACANTHOSTEGA_LINE
    assert ident["public_preset"] == PRESET_ACANTHOSTEGA
    assert ident["model_codename"] == "Acanthostega"
    active = f.get("active_experiment") or {}
    assert active.get("public_preset") == PRESET_ACANTHOSTEGA
    assert active.get("model_line") == ACANTHOSTEGA_LINE
    assert active.get("ecology_preset") == "GENTLE_FREE_MOVEMENT"
    assert active.get("psc_motor_resolution") == "OBSERVED_COMPOSITE"
    assert active.get("preset_modified") is True
    assert active.get("canonical") is False
    live = s.current_frame()
    live_active = (live.get("experiment") or {}).get("active_experiment") or live.get("active_experiment") or {}
    assert live_active.get("public_preset") == PRESET_ACANTHOSTEGA
    assert live_active.get("preset_modified") is True
    snap = s.snapshot()
    s2 = ObserverSession(SessionConfig(seed=17, buffer_capacity=8))
    out = s2.restore(snap)
    assert (out.get("control_receipt") or {}).get("accepted") is not False
    ident2 = s2.runtime.model_identity()
    assert ident2["model_line"] == ACANTHOSTEGA_LINE
    assert ident2["public_preset"] == PRESET_ACANTHOSTEGA
    assert str(getattr(s2.runtime.config, "ecology_preset", "")) == "GENTLE_FREE_MOVEMENT"
    restored = s2._canonical_config or {}
    assert restored.get("preset_modified") is True
    assert restored.get("public_preset") == PRESET_ACANTHOSTEGA


def test_tiktaalik_overrides_keep_identity_and_frozen_baseline():
    assert canonical_fingerprint(preset_canonical(PRESET_BETA31, seed=17)) == FROZEN_BETA31_FP_SEED17
    s = ObserverSession(SessionConfig(seed=17, buffer_capacity=8))
    complete = deepcopy(preset_canonical(PRESET_BETA31, seed=17))
    complete["ecology_preset"] = "GENTLE_FREE_MOVEMENT"
    f = s.apply_experiment(complete)
    ident = s.runtime.model_identity()
    assert ident["model_line"] == "TIKTAALIK"
    assert ident["public_preset"] == PRESET_BETA31
    active = f.get("active_experiment") or {}
    assert active.get("ecology_preset") == "GENTLE_FREE_MOVEMENT"
    assert active.get("preset_modified") is True
    assert active.get("canonical") is False
    assert canonical_fingerprint(preset_canonical(PRESET_BETA31, seed=17)) == FROZEN_BETA31_FP_SEED17


def test_acanthostega_exact_apply_is_canonical_match():
    s = ObserverSession(SessionConfig(seed=17, buffer_capacity=8))
    f = s.apply_experiment(deepcopy(preset_canonical(PRESET_ACANTHOSTEGA, seed=17)))
    ident = s.runtime.model_identity()
    assert ident["model_line"] == ACANTHOSTEGA_LINE
    active = f.get("active_experiment") or {}
    assert active.get("public_preset") == PRESET_ACANTHOSTEGA
    assert active.get("preset_modified") is False
    assert active.get("canonical") is True


def test_legacy_payload_without_public_preset_is_tiktaalik():
    s = ObserverSession(SessionConfig(seed=17, buffer_capacity=8))
    f = s.apply_experiment({
        "seed": 17,
        "ecology_preset": "GENTLE_FREE_MOVEMENT",
        "world": {"width": 16, "height": 16, "boundary_mode": "WRAP_PERIODIC"},
        "mechanisms": {"physical_near_field_vision": True},
    })
    ident = s.runtime.model_identity()
    assert ident["model_line"] == "TIKTAALIK"
    assert ident["model_codename"] == "Tiktaalik"
    assert f.get("active_experiment", {}).get("ecology_preset") == "GENTLE_FREE_MOVEMENT"

