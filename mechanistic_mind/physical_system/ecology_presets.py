"""World ecology presets for Tiktaalik Observer / runtime.

Promoted baseline (post calibration 20260918T225541Z):
    BASELINE_CLIMATE_DEFAULT
        climate ecology ON
        environmental R_A/R_B present
        softened flow
        passive_reservoir_trickle = 0

Legacy / experimental presets remain explicitly selectable:
    CURRENT_LEGACY          — pre-promotion empty-resource CURRENT
    GENTLE_FREE_MOVEMENT    — locomotion softening, climate OFF
    BASELINE_A_STATIC_PATCHES / B_MIGRATING / C_CHANGING

Observer/runtime ground truth only. Never enters agent observation.
Does not bypass physics: same causal chain, different generated ecology.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig
from mechanistic_mind.planet.climate_ecology import ClimateEcologyConfig

# ---------------------------------------------------------------------------
# Preset identifiers
# ---------------------------------------------------------------------------

ECOLOGY_BASELINE = "BASELINE_CLIMATE_DEFAULT"
ECOLOGY_CURRENT_LEGACY = "CURRENT_LEGACY"
# Historical GEO alias: CURRENT == CURRENT_LEGACY (do not reinterpret as climate).
ECOLOGY_CURRENT = ECOLOGY_CURRENT_LEGACY
ECOLOGY_GENTLE = "GENTLE_FREE_MOVEMENT"

ECOLOGY_A_STATIC_PATCHES = "BASELINE_A_STATIC_PATCHES"
ECOLOGY_B_MIGRATING = "BASELINE_B_MIGRATING_RESOURCES"
ECOLOGY_C_CHANGING = "BASELINE_C_CHANGING_LANDSCAPE"
ECOLOGY_STRUCTURED_TERRAIN = "STRUCTURED_TERRAIN_EXPERIMENTAL"
ECOLOGY_STRUCTURED_WORLD = "STRUCTURED_WORLD_EXPERIMENTAL"
# Post WORLD_TIMESCALE_CALIBRATION_01 (20260919): season_period=800 (SHORT_DERIVED).
# Does NOT replace BASELINE_CLIMATE_DEFAULT.
ECOLOGY_CALIBRATED_TEMPORAL = "CALIBRATED_TEMPORAL_WORLD_EXPERIMENTAL"

KNOWN_ECOLOGY_PRESETS = (
    ECOLOGY_BASELINE,
    ECOLOGY_CURRENT_LEGACY,
    ECOLOGY_GENTLE,
    ECOLOGY_A_STATIC_PATCHES,
    ECOLOGY_B_MIGRATING,
    ECOLOGY_C_CHANGING,
    ECOLOGY_STRUCTURED_TERRAIN,
    ECOLOGY_STRUCTURED_WORLD,
    ECOLOGY_CALIBRATED_TEMPORAL,
)

# Promoted default when callers omit / pass None.
DEFAULT_ECOLOGY_PRESET = ECOLOGY_BASELINE

# BODY-01: trickle mechanism retained but OFF for promoted baseline.
# Explicit controls may set 0.0005 / 0.002. Dataclass default remains 0.
BODY01_PASSIVE_RESERVOIR_TRICKLE = 0.0

# Human UI labels (Observer only)
ECOLOGY_UI_LABELS = {
    ECOLOGY_BASELINE: "Baseline Climate Ecology",
    ECOLOGY_CURRENT_LEGACY: "Current Legacy (no env R_A/R_B)",
    ECOLOGY_GENTLE: "Gentle / Free Movement",
    ECOLOGY_A_STATIC_PATCHES: "Static Resource Patches",
    ECOLOGY_B_MIGRATING: "Migrating Resources",
    ECOLOGY_C_CHANGING: "Changing Causal Landscape",
    ECOLOGY_STRUCTURED_TERRAIN: "Structured Terrain (experimental)",
    ECOLOGY_STRUCTURED_WORLD: "Structured World (terrain + ambient)",
    ECOLOGY_CALIBRATED_TEMPORAL: "Calibrated Temporal World (experimental)",
}

# Parameter overrides applied ON TOP of factory defaults (BODY-2 / PlanetConfig).
# GENTLE softens passive flow / site force while slightly increasing MOVE impulse
# authority — still ordinary physics. Climate remains OFF (legacy locomotion axis).
GENTLE_OVERRIDES: dict[str, Any] = {
    "planet": {
        "flow_gain": 0.20,
        "flow_max": 0.22,
        "F_fast_amp": 0.15,
        "F_slow_amp": 0.12,
        "F_irregular_amp": 0.02,
        "kappa_base": 0.14,
    },
    "body": {
        "flow_coupling": 0.14,
        "drag": 0.36,
        "wave_coupling": 0.06,
    },
    "body_orientation": {
        "force_scale": 0.50,
    },
    "discrete_action_work": {
        "impulse_scale": 0.55,
    },
    "endogenous_motor": {
        "strength": 0.035,
        "saturation": 0.14,
    },
}

# Exact calibrated BASELINE_CLIMATE_DEFAULT from calibration experiment
# (mechanistic_mind/physical_system/baseline_ecology_presets.py — do not retune flow).
# PASSIVE_TRANSPORT_01 promotion (20260918T234435Z): force_scale 1.0 → 0.15.
BASELINE_CLIMATE_FLOW = {
    "flow_gain": 0.14,
    "flow_max": 0.16,
}
BASELINE_CLIMATE_BODY = {
    "flow_coupling": 0.09,
}
BASELINE_CLIMATE_ORIENTATION = {
    "force_scale": 0.15,
}
# Stronger candidate from PASSIVE_TRANSPORT_01 — not promoted; keep for controls.
PASSIVE_TRANSPORT_FORCE_SCALE_STRONG = 0.10
PASSIVE_TRANSPORT_FORCE_SCALE_PROMOTED = 0.15
PASSIVE_TRANSPORT_FORCE_SCALE_PRE = 1.0


def normalize_ecology_preset(name: str | None) -> str:
    if name is None or str(name).strip() == "":
        return DEFAULT_ECOLOGY_PRESET
    key = str(name).strip().upper().replace("-", "_").replace(" ", "_")
    aliases = {
        # Promoted baseline
        "BASELINE": ECOLOGY_BASELINE,
        "BASELINE_CLIMATE": ECOLOGY_BASELINE,
        "BASELINE_CLIMATE_DEFAULT": ECOLOGY_BASELINE,
        "CLIMATE": ECOLOGY_BASELINE,
        "CLIMATE_DEFAULT": ECOLOGY_BASELINE,
        "TIKTAALIK": ECOLOGY_BASELINE,
        "DEFAULT": ECOLOGY_BASELINE,
        # Legacy CURRENT (empty resource fields) — never silently upgrade to climate
        "CURRENT": ECOLOGY_CURRENT_LEGACY,
        "CURRENT_LEGACY": ECOLOGY_CURRENT_LEGACY,
        "HARSH": ECOLOGY_CURRENT_LEGACY,
        "CURRENT_PHYSICAL_ECOLOGY": ECOLOGY_CURRENT_LEGACY,
        "LEGACY": ECOLOGY_CURRENT_LEGACY,
        # Gentle locomotion
        "GENTLE": ECOLOGY_GENTLE,
        "GENTLE_FREE_MOVEMENT": ECOLOGY_GENTLE,
        "FREE_MOVEMENT": ECOLOGY_GENTLE,
        "GENTLE_FREE": ECOLOGY_GENTLE,
        # Calibration candidates
        "A": ECOLOGY_A_STATIC_PATCHES,
        "STATIC": ECOLOGY_A_STATIC_PATCHES,
        "STATIC_PATCHES": ECOLOGY_A_STATIC_PATCHES,
        ECOLOGY_A_STATIC_PATCHES: ECOLOGY_A_STATIC_PATCHES,
        "B": ECOLOGY_B_MIGRATING,
        "MIGRATING": ECOLOGY_B_MIGRATING,
        ECOLOGY_B_MIGRATING: ECOLOGY_B_MIGRATING,
        "C": ECOLOGY_C_CHANGING,
        "CHANGING": ECOLOGY_C_CHANGING,
        ECOLOGY_C_CHANGING: ECOLOGY_C_CHANGING,
        # Experimental structured terrain
        "TERRAIN": ECOLOGY_STRUCTURED_TERRAIN,
        "STRUCTURED_TERRAIN": ECOLOGY_STRUCTURED_TERRAIN,
        "STRUCTURED_TERRAIN_EXPERIMENTAL": ECOLOGY_STRUCTURED_TERRAIN,
        ECOLOGY_STRUCTURED_TERRAIN: ECOLOGY_STRUCTURED_TERRAIN,
        # Terrain + weak static ambient horizontal force
        "WORLD": ECOLOGY_STRUCTURED_WORLD,
        "STRUCTURED_WORLD": ECOLOGY_STRUCTURED_WORLD,
        "STRUCTURED_WORLD_EXPERIMENTAL": ECOLOGY_STRUCTURED_WORLD,
        ECOLOGY_STRUCTURED_WORLD: ECOLOGY_STRUCTURED_WORLD,
        "CALIBRATED": ECOLOGY_CALIBRATED_TEMPORAL,
        "CALIBRATED_TEMPORAL": ECOLOGY_CALIBRATED_TEMPORAL,
        "CALIBRATED_TEMPORAL_WORLD": ECOLOGY_CALIBRATED_TEMPORAL,
        "CALIBRATED_TEMPORAL_WORLD_EXPERIMENTAL": ECOLOGY_CALIBRATED_TEMPORAL,
        ECOLOGY_CALIBRATED_TEMPORAL: ECOLOGY_CALIBRATED_TEMPORAL,
    }
    if key not in aliases:
        raise ValueError(f"unknown ecology_preset={name!r}; known={list(KNOWN_ECOLOGY_PRESETS)}")
    return aliases[key]


def parameter_diff(current: PhysicalSystemConfig, gentle: PhysicalSystemConfig) -> dict[str, Any]:
    """Observer audit: which knobs differ between two configs."""
    rows = []

    def _cmp(path: str, a: Any, b: Any) -> None:
        if isinstance(a, float) or isinstance(b, float):
            if abs(float(a) - float(b)) > 1e-12:
                rows.append({"path": path, "current": a, "gentle": b})
        elif a != b:
            rows.append({"path": path, "current": a, "gentle": b})

    _cmp("planet.flow_gain", current.planet.flow_gain, gentle.planet.flow_gain)
    _cmp("planet.flow_max", current.planet.flow_max, gentle.planet.flow_max)
    _cmp("planet.F_fast_amp", current.planet.F_fast_amp, gentle.planet.F_fast_amp)
    _cmp("planet.F_slow_amp", current.planet.F_slow_amp, gentle.planet.F_slow_amp)
    _cmp("planet.F_irregular_amp", current.planet.F_irregular_amp, gentle.planet.F_irregular_amp)
    _cmp("planet.kappa_base", current.planet.kappa_base, gentle.planet.kappa_base)
    _cmp("planet.climate_ecology.enabled", current.planet.climate_ecology.enabled, gentle.planet.climate_ecology.enabled)
    _cmp("body.flow_coupling", current.body.flow_coupling, gentle.body.flow_coupling)
    _cmp("body.drag", current.body.drag, gentle.body.drag)
    _cmp("body.wave_coupling", current.body.wave_coupling, gentle.body.wave_coupling)
    _cmp("body.mass", current.body.mass, gentle.body.mass)
    _cmp("body.v_max", current.body.v_max, gentle.body.v_max)
    _cmp(
        "body_orientation.force_scale",
        current.body_orientation.force_scale,
        gentle.body_orientation.force_scale,
    )
    _cmp(
        "discrete_action_work.impulse_scale",
        current.discrete_action_work.impulse_scale,
        gentle.discrete_action_work.impulse_scale,
    )
    _cmp(
        "endogenous_motor.strength",
        current.endogenous_motor.strength,
        gentle.endogenous_motor.strength,
    )
    _cmp(
        "endogenous_motor.saturation",
        current.endogenous_motor.saturation,
        gentle.endogenous_motor.saturation,
    )
    _cmp(
        "deformation_work.passive_reservoir_trickle",
        current.deformation_work.passive_reservoir_trickle,
        gentle.deformation_work.passive_reservoir_trickle,
    )
    return {
        "n_diffs": len(rows),
        "diffs": rows,
        "note": "Ecology preset changes physical generation/coupling only — not cognition.",
    }


def _apply_dict(cfg: PhysicalSystemConfig, section: str, overrides: dict[str, Any]) -> None:
    target = getattr(cfg, section)
    for k, v in overrides.items():
        setattr(target, k, v)


def apply_ecology_preset(
    config: PhysicalSystemConfig,
    preset: str | None,
    *,
    inplace: bool = True,
) -> PhysicalSystemConfig:
    """Apply ecology preset overrides.

    Does not modify cognition. Does not disable deformation, work, contact,
    orientation, or complementary conversion.
    """
    cfg = config if inplace else deepcopy(config)
    name = normalize_ecology_preset(preset)
    cfg.ecology_preset = name

    # Explicit trickle stamp for ecology-built configs (baseline = 0).
    cfg.deformation_work.passive_reservoir_trickle = float(BODY01_PASSIVE_RESERVOIR_TRICKLE)

    if name == ECOLOGY_CURRENT_LEGACY:
        # Identity on factory defaults: climate OFF, no environmental R_A/R_B.
        # Explicit vision OFF — do not inherit calibrated NFE if base had it.
        from mechanistic_mind.physical_system.near_field_exteroception import NearFieldExteroceptionConfig
        cfg.planet.climate_ecology = ClimateEcologyConfig(
            enabled=False,
            resources_enabled=False,
            resource_ecology_A_enabled=False,
            resource_ecology_B_enabled=False,
        )
        cfg.near_field_exteroception = NearFieldExteroceptionConfig(mode="OFF")
        return cfg

    if name == ECOLOGY_GENTLE:
        from mechanistic_mind.physical_system.near_field_exteroception import NearFieldExteroceptionConfig
        cfg.planet.climate_ecology = ClimateEcologyConfig(
            enabled=False,
            resources_enabled=False,
            resource_ecology_A_enabled=False,
            resource_ecology_B_enabled=False,
        )
        cfg.near_field_exteroception = NearFieldExteroceptionConfig(mode="OFF")
        ov = GENTLE_OVERRIDES
        _apply_dict(cfg, "planet", ov.get("planet") or {})
        _apply_dict(cfg, "body", ov.get("body") or {})
        _apply_dict(cfg, "body_orientation", ov.get("body_orientation") or {})
        _apply_dict(cfg, "discrete_action_work", ov.get("discrete_action_work") or {})
        _apply_dict(cfg, "endogenous_motor", ov.get("endogenous_motor") or {})
        return cfg

    if name == ECOLOGY_BASELINE:
        # Exact calibrated climate default — do not retune flow/climate timing here.
        # PASSIVE_TRANSPORT_01: force_scale only (1.0 → 0.15).
        _apply_dict(cfg, "planet", BASELINE_CLIMATE_FLOW)
        _apply_dict(cfg, "body", BASELINE_CLIMATE_BODY)
        _apply_dict(cfg, "body_orientation", BASELINE_CLIMATE_ORIENTATION)
        cfg.planet.climate_ecology = ClimateEcologyConfig(
            enabled=True,
            resources_enabled=True,
            resource_ecology_A_enabled=True,
            resource_ecology_B_enabled=True,
        )
        return cfg

    if name == ECOLOGY_STRUCTURED_TERRAIN:
        from mechanistic_mind.planet.terrain import TerrainConfig
        from mechanistic_mind.physical_system.near_field_exteroception import calibrated_near_field_config

        # Calibrated body/climate baseline + spatial terrain; flow kept non-dominant.
        _apply_dict(cfg, "planet", BASELINE_CLIMATE_FLOW)
        _apply_dict(cfg, "body", BASELINE_CLIMATE_BODY)
        _apply_dict(cfg, "body_orientation", BASELINE_CLIMATE_ORIENTATION)
        cfg.planet.climate_ecology = ClimateEcologyConfig(
            enabled=True,
            resources_enabled=True,
            resource_ecology_A_enabled=True,
            resource_ecology_B_enabled=True,
            geography_resources_enabled=True,
            geography_mix=0.55,
        )
        # Explicit vision stamp — validated constants; not inherited accidentally.
        cfg.near_field_exteroception = calibrated_near_field_config()
        # Further reduce global flow so terrain/self-locomotion dominate.
        cfg.planet.flow_gain = 0.06
        cfg.planet.flow_max = 0.10
        cfg.planet.terrain = TerrainConfig(
            enabled=True,
            mode="CORRELATED",
            drag_base=0.02,
            drag_amplitude=0.55,
            potential_amplitude=0.85,
            correlation_scale=7.0,
            large_scale_weight=0.55,
            medium_scale_weight=0.30,
            small_scale_weight=0.15,
            discontinuity_rate=0.012,
            discontinuity_amplitude=0.55,
            force_scale=0.08,
            drag_coupling=1.0,
            max_gradient=0.35,
            wait_force_scale=0.20,
            kinetic_speed_threshold=0.025,
            terrain_seed=None,  # namespace from experiment seed
        )
        cfg.deformation_work.passive_reservoir_trickle = float(BODY01_PASSIVE_RESERVOIR_TRICKLE)
        return cfg

    if name == ECOLOGY_STRUCTURED_WORLD:
        from mechanistic_mind.planet.ambient import AmbientConfig

        # Terrain geography + weak static ambient (not enabled in baseline presets).
        cfg = apply_ecology_preset(cfg, ECOLOGY_STRUCTURED_TERRAIN, inplace=True)
        cfg.planet.ambient = AmbientConfig(
            enabled=True,
            amplitude=0.018,
            correlation_scale=8.0,
            large_scale_weight=0.65,
            medium_scale_weight=0.35,
            wait_force_scale=0.15,
            kinetic_speed_threshold=0.025,
            max_component=0.045,
            ambient_seed=None,
        )
        cfg.ecology_preset = ECOLOGY_STRUCTURED_WORLD
        return cfg

    if name == ECOLOGY_CALIBRATED_TEMPORAL:
        # HABITABLE_WORLD_CALIBRATION_01 / WORLD_TIMESCALE_CALIBRATION_01.
        # season_period=800 (SHORT_DERIVED). Breaks equatorial double-peak via
        # subsolar_bias so one climate pulse/cycle spans T_history. Soft local
        # F_fast weather remains, slower than climate envelope. Terrain/ambient static.
        # Does NOT change BASELINE / STRUCTURED_WORLD / cognition / force_scale.
        cfg = apply_ecology_preset(cfg, ECOLOGY_STRUCTURED_WORLD, inplace=True)
        ce = cfg.planet.climate_ecology
        ce.season_period = 800
        ce.subsolar_bias = 0.35
        ce.subsolar_amp = 0.45
        ce.belt_width = 0.50
        ce.belt_amp = 0.28
        ce.local_var_amp = 0.010
        ce.local_var_period = 80  # redraw local noise on history scale, not every 11 ticks
        # Soft traveling weather lobe: period between T_history and climate.
        cfg.planet.F_fast_period = 320
        cfg.planet.F_fast_amp = 0.06
        cfg.planet.F_fast_sigma = 10.0
        cfg.planet.F_slow_period = 1600
        cfg.planet.F_slow_amp = 0.08
        cfg.planet.F_irregular_amp = 0.005
        # Resource temporal + spatial habitability: persist across history, not ubiquitous.
        # Equilibrium R*≈prod*suit/decay; keep prod/decay low enough that weak-suit
        # regions stay below encounter threshold while geography concentrates patches.
        ce.geography_mix = 0.88
        ce.RA_potential_width = 0.18
        ce.RB_potential_width = 0.20
        ce.RA_grad_penalty = 2.0
        ce.RB_grad_penalty = 1.2
        ce.RA_drag_width = 0.15
        ce.RB_drag_width = 0.16
        ce.RA_T_width = 0.06
        ce.RB_T_width = 0.07
        ce.RA_productivity = 0.015
        ce.RB_productivity = 0.012
        ce.RA_decay = 0.055
        ce.RB_decay = 0.070
        ce.resource_diffuse = 0.006
        ce.resource_seed_frac = 0.02
        ce.RA_capacity = 1.10
        ce.RB_capacity = 0.85
        # Vision already stamped by STRUCTURED_WORLD → STRUCTURED_TERRAIN; reaffirm.
        from mechanistic_mind.physical_system.near_field_exteroception import calibrated_near_field_config
        cfg.near_field_exteroception = calibrated_near_field_config()
        cfg.ecology_preset = ECOLOGY_CALIBRATED_TEMPORAL
        return cfg

    # Delegate remaining candidates to baseline_ecology_presets (same calibrated params).
    from mechanistic_mind.physical_system.baseline_ecology_presets import (
        make_baseline_ecology_config,
    )

    built = make_baseline_ecology_config(name, trickle=float(BODY01_PASSIVE_RESERVOIR_TRICKLE), base=cfg)
    # Copy critical fields back onto cfg (inplace already is cfg when base=cfg via deepcopy in maker)
    cfg.planet = built.planet
    cfg.body = built.body
    cfg.deformation_work.passive_reservoir_trickle = float(BODY01_PASSIVE_RESERVOIR_TRICKLE)
    cfg.ecology_preset = name
    for attr in ("_baseline_seed_patches", "_baseline_patch_spec", "baseline_ecology"):
        if hasattr(built, attr):
            setattr(cfg, attr, getattr(built, attr))
    return cfg


def make_ecology_config(
    preset: str | None = None,
    *,
    base: PhysicalSystemConfig | None = None,
    trickle: float | None = None,
) -> PhysicalSystemConfig:
    """Build a PhysicalSystemConfig with the requested ecology.

    Default preset is the promoted BASELINE_CLIMATE_DEFAULT.
    Pass CURRENT / CURRENT_LEGACY for historical empty-resource physics.
    Optional ``trickle`` overrides BODY01_PASSIVE_RESERVOIR_TRICKLE for controls.
    """
    cfg = deepcopy(base) if base is not None else PhysicalSystemConfig()
    name = normalize_ecology_preset(preset)
    cfg = apply_ecology_preset(cfg, name, inplace=True)
    if trickle is not None:
        cfg.deformation_work.passive_reservoir_trickle = float(trickle)
    return cfg


def ecology_metadata(config: PhysicalSystemConfig | None) -> dict[str, Any]:
    if config is None:
        return {
            "ecology_preset": DEFAULT_ECOLOGY_PRESET,
            "ui_label": ECOLOGY_UI_LABELS[DEFAULT_ECOLOGY_PRESET],
            "observer_only": True,
            "passive_reservoir_trickle": float(BODY01_PASSIVE_RESERVOIR_TRICKLE),
            "body_orientation_force_scale": float(PASSIVE_TRANSPORT_FORCE_SCALE_PROMOTED),
        }
    name = normalize_ecology_preset(getattr(config, "ecology_preset", None) or DEFAULT_ECOLOGY_PRESET)
    ce = getattr(config.planet, "climate_ecology", None)
    te = getattr(config.planet, "terrain", None)
    nfe = getattr(config, "near_field_exteroception", None)
    return {
        "ecology_preset": name,
        "ui_label": ECOLOGY_UI_LABELS.get(name, name),
        "observer_only": True,
        "climate_ecology_enabled": bool(getattr(ce, "enabled", False)) if ce is not None else False,
        "passive_reservoir_trickle": float(
            getattr(config.deformation_work, "passive_reservoir_trickle", 0.0) or 0.0
        ),
        "body_orientation_force_scale": float(
            getattr(config.body_orientation, "force_scale", 1.0) or 0.0
        ),
        "terrain_enabled": bool(getattr(te, "enabled", False)) if te is not None else False,
        "terrain_mode": str(getattr(te, "mode", "FLAT")) if te is not None else "FLAT",
        "terrain_config": te.to_dict() if te is not None and hasattr(te, "to_dict") else None,
        "physical_near_field_vision": bool(getattr(nfe, "vision_contributes", False)) if nfe else False,
        "illumination_cycle": bool(
            getattr(nfe, "enabled", False) and getattr(nfe, "illumination_enabled", False)
        ) if nfe else False,
        "honesty": {
            "not_agent_observation": True,
            "not_cognition_input": True,
            "not_locomotion_bypass": True,
            "ordinary_physics": True,
            "not_semantic_food": True,
        },
    }
