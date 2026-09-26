"""CLIMATE_AUTHORITY_AUDIT_01 — effective world config, fingerprint, authority.

Observer / experiment only. No cognition retune. No perception GT leak.
Derives EFFECTIVE WORLD CONFIGURATION from instantiated runtime config+world.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

import numpy as np

from mechanistic_mind.physical_system.ecology_presets import (
    ECOLOGY_BASELINE,
    ECOLOGY_CALIBRATED_TEMPORAL,
    ECOLOGY_STRUCTURED_WORLD,
    make_ecology_config,
    normalize_ecology_preset,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime


# Presets that stamp climate_ecology.enabled=True at construction.
CLIMATE_BEARING_PRESETS = frozenset({
    ECOLOGY_BASELINE,
    "STRUCTURED_TERRAIN_EXPERIMENTAL",
    ECOLOGY_STRUCTURED_WORLD,
    ECOLOGY_CALIBRATED_TEMPORAL,
    "A_STATIC_PATCHES",
    "B_MIGRATING_SEASONAL",
    "C_CHANGING_WORLD",
})


def climate_package_implies_on(ecology_preset: str | None) -> bool:
    try:
        eco = normalize_ecology_preset(ecology_preset or ECOLOGY_BASELINE)
    except Exception:
        eco = str(ecology_preset or "")
    return eco in CLIMATE_BEARING_PRESETS or "CALIBRATED" in eco or "STRUCTURED" in eco or eco == ECOLOGY_BASELINE


def effective_world_configuration(runtime: PhysicalSystemRuntime | TwoAgentRuntime) -> dict[str, Any]:
    """What the runtime is ACTUALLY executing (Observer GT only)."""
    if isinstance(runtime, TwoAgentRuntime):
        cfg = runtime.config
        world = runtime.world
        body_cfg = runtime.slots[0].config.body
        nfe = getattr(runtime.slots[0].config, "near_field_exteroception", None)
        flow_coupling = float(getattr(body_cfg, "flow_coupling", 0.0) or 0.0)
        orient = getattr(runtime.slots[0].config, "body_orientation", None)
    else:
        cfg = runtime.config
        world = runtime.world
        body_cfg = cfg.body
        nfe = getattr(cfg, "near_field_exteroception", None)
        flow_coupling = float(getattr(body_cfg, "flow_coupling", 0.0) or 0.0)
        orient = getattr(cfg, "body_orientation", None)

    planet = cfg.planet
    ce = getattr(planet, "climate_ecology", None)
    te = getattr(planet, "terrain", None)
    ae = getattr(planet, "ambient", None)
    eco = str(getattr(cfg, "ecology_preset", "CURRENT") or "CURRENT")
    ce_on = bool(ce is not None and getattr(ce, "enabled", False))
    from mechanistic_mind.planet.climate_ecology import (
        resource_ecology_A_on,
        resource_ecology_B_on,
        resource_ecology_any,
    )
    res_a = resource_ecology_A_on(ce)
    res_b = resource_ecology_B_on(ce)
    res_on = resource_ecology_any(ce)
    flow_on = bool(getattr(planet, "flow_enabled", True))
    wave_coupling = float(getattr(body_cfg, "wave_coupling", 0.0) or 0.0)
    morph = None
    if isinstance(runtime, TwoAgentRuntime):
        morph = getattr(runtime.slots[0].config, "morphology_mechanics", None)
    else:
        morph = getattr(cfg, "morphology_mechanics", None)
    include_wave = True
    if morph is not None and hasattr(morph, "include_wave"):
        include_wave = bool(getattr(morph, "include_wave", True))
    # Orientation path: flow_coupling*vx PLUS wave_coupling*u*unit(vx,vy).
    # Zeroing flow_coupling alone does NOT isolate thermal body transport.
    direct_flow_body = flow_on and flow_coupling > 0.0
    wave_flow_steering = flow_on and wave_coupling > 0.0 and include_wave
    thermal_body_coupling = direct_flow_body or wave_flow_steering

    package_implies = climate_package_implies_on(eco)
    climate_ablated = package_implies and not ce_on

    illum_on = bool(
        nfe is not None
        and getattr(nfe, "enabled", False)
        and getattr(nfe, "illumination_enabled", True)
    )
    perc_on = bool(
        nfe is not None
        and getattr(nfe, "vision_contributes", False)
    )

    tmeta = getattr(world, "terrain_meta", None) or {}
    ameta = getattr(world, "ambient_meta", None) or {}
    smeta = getattr(world, "surface_meta", None) or {}

    ra = getattr(world, "R_A", None)
    rb = getattr(world, "R_B", None)

    def _res_stats(arr) -> dict[str, float] | None:
        if arr is None:
            return None
        a = np.asarray(arr, dtype=np.float64)
        return {
            "mean": float(np.mean(a)),
            "min": float(np.min(a)),
            "max": float(np.max(a)),
            "frac_gt_0_01": float(np.mean(a > 0.01)),
            "frac_gt_0_001": float(np.mean(a > 0.001)),
        }

    overrides: list[str] = []
    if climate_ablated:
        overrides.append("CLIMATE_ECOLOGY_ABLATED")
    if package_implies and not res_a:
        overrides.append("RESOURCE_ECOLOGY_A_OFF")
    if package_implies and not res_b:
        overrides.append("RESOURCE_ECOLOGY_B_OFF")
    if package_implies and not res_on:
        overrides.append("RESOURCES_DISABLED")
    if not flow_on:
        overrides.append("THERMAL_FLOW_OFF")
    if flow_on and flow_coupling <= 0.0 and wave_flow_steering:
        overrides.append("DIRECT_FLOW_COUPLING_OFF_WAVE_STEERING_REMAINS")
    if flow_on and not thermal_body_coupling:
        overrides.append("THERMAL_BODY_COUPLING_OFF")
    if te is not None and not getattr(te, "enabled", False) and "STRUCTURED" in eco:
        overrides.append("TERRAIN_OFF")
    if ae is not None and not getattr(ae, "enabled", False) and "WORLD" in eco:
        overrides.append("AMBIENT_OFF")

    return {
        "requested_preset": eco,
        "normalized_preset": normalize_ecology_preset(eco) if eco else eco,
        "climate_package_implies_climate": package_implies,
        "climate_ablated": climate_ablated,
        "subsystems": {
            "temperature_dynamics": True,  # step_thermal always runs
            "climate_equilibrium_T_eq": ce_on,
            "slow_climate_cycle": ce_on and int(getattr(ce, "season_period", 0) or 0) > 0,
            "fast_local_forcing_F_fast": bool(getattr(planet, "forcing_enabled", True))
            and float(getattr(planet, "F_fast_amp", 0) or 0) > 0,
            "slow_forcing_F_slow": bool(getattr(planet, "forcing_enabled", True))
            and float(getattr(planet, "F_slow_amp", 0) or 0) > 0,
            "climate_insolation_addon": ce_on,
            "thermal_flow_vx_vy": flow_on,
            "thermal_body_coupling": thermal_body_coupling,
            "direct_flow_coupling": direct_flow_body,
            "wave_flow_steering": wave_flow_steering,
            "terrain": bool(te is not None and getattr(te, "enabled", False)),
            "ambient_horizontal_force": bool(ae is not None and getattr(ae, "enabled", False)),
            "resource_A_production": res_a,
            "resource_B_production": res_b,
            "resource_decay": res_on,
            "resource_geography_coupling": res_on and bool(getattr(ce, "geography_resources_enabled", False)),
            "illumination": illum_on,
            "near_field_perception": perc_on,
            "physical_near_field_vision": perc_on,
            "illumination_cycle": illum_on,
            "physical_body_optical_response": bool(
                nfe is not None
                and getattr(nfe, "enabled", False)
                and getattr(nfe, "body_optical_enabled", True)
            ),
        },
        "near_field_exteroception": {
            "mode": str(getattr(nfe, "mode", "OFF")) if nfe else "OFF",
            "enabled": bool(getattr(nfe, "enabled", False)) if nfe else False,
            "perception_enabled": bool(getattr(nfe, "perception_enabled", False)) if nfe else False,
            "illumination_enabled": bool(getattr(nfe, "illumination_enabled", False)) if nfe else False,
            "body_optical_enabled": bool(getattr(nfe, "body_optical_enabled", False)) if nfe else False,
            "fov_deg": float(getattr(nfe, "fov_deg", 0) or 0) if nfe else None,
            "radius": int(getattr(nfe, "vision_radius", 1) if nfe else 1),
            "vision_radius": int(getattr(nfe, "vision_radius", 1) if nfe else 1),
            "illumination_period": int(getattr(nfe, "illumination_period", 0) or 0) if nfe else None,
            "ACTIVE_SENSOR_ORIENTATION": "NOT_AVAILABLE",
        },
        "climate_ecology": {
            "enabled": ce_on,
            "resources_enabled": res_on,
            "resource_ecology_A_enabled": res_a,
            "resource_ecology_B_enabled": res_b,
            "season_period": int(getattr(ce, "season_period", 0) or 0) if ce else None,
            "subsolar_bias": float(getattr(ce, "subsolar_bias", 0) or 0) if ce else None,
            "cycle_mode": str(getattr(ce, "cycle_mode", "")) if ce else None,
        },
        "planet_forcing": {
            "forcing_enabled": bool(getattr(planet, "forcing_enabled", True)),
            "F_fast_amp": float(getattr(planet, "F_fast_amp", 0) or 0),
            "F_fast_period": int(getattr(planet, "F_fast_period", 0) or 0),
            "F_slow_amp": float(getattr(planet, "F_slow_amp", 0) or 0),
            "F_slow_period": int(getattr(planet, "F_slow_period", 0) or 0),
            "flow_enabled": flow_on,
            "flow_gain": float(getattr(planet, "flow_gain", 0) or 0),
            "flow_max": float(getattr(planet, "flow_max", 0) or 0),
        },
        "body_flow_coupling": flow_coupling,
        "body_wave_coupling": wave_coupling,
        "terrain": {
            "enabled": bool(te is not None and getattr(te, "enabled", False)),
            "checksum": tmeta.get("checksum"),
            "terrain_seed": tmeta.get("terrain_seed"),
        },
        "ambient": {
            "enabled": bool(ae is not None and getattr(ae, "enabled", False)),
            "checksum": ameta.get("checksum"),
            "ambient_seed": ameta.get("ambient_seed") or ameta.get("resolved_ambient_seed"),
        },
        "illumination": {
            "enabled": illum_on,
            "period": int(getattr(nfe, "illumination_period", 0) or 0) if nfe else None,
            "perception_enabled": perc_on,
        },
        "surface": {
            "present": getattr(world, "surface_response", None) is not None,
            "checksum": smeta.get("checksum"),
        },
        "resources_now": {
            "R_A": _res_stats(ra),
            "R_B": _res_stats(rb),
        },
        "overrides": overrides,
        "authority": {
            "preset_stamps_climate_package": True,
            "climate_dynamics_gate": "planet.climate_ecology.enabled",
            "resource_ecology_A_gate": "planet.climate_ecology.resource_ecology_A_enabled",
            "resource_ecology_B_gate": "planet.climate_ecology.resource_ecology_B_enabled",
            "mechanism_toggle_controls": "planet.climate_ecology.enabled",
            "physics_gate": "planet.climate_ecology.enabled",
            "note": (
                "Preset applies climate + resource ecology defaults at construction. "
                "Climate toggle flips climate dynamics only. "
                "R_A/R_B environmental ecology use independent LIVE toggles. "
                "When climate is OFF, resource ecology continues against current physical T "
                "(no substituted comfort constants)."
            ),
        },
        "dependency_graph": DEPENDENCY_GRAPH,
        "vx_vy_semantics": VX_VY_SEMANTICS,
    }


DEPENDENCY_GRAPH = {
    "note": "Derived from step_planet + body_orientation; Beta 2 separates climate vs resource ecology",
    "nodes": {
        "PlanetConfig.forcing_enabled + F_fast/F_slow": "forcing_field → F",
        "climate_ecology.enabled": [
            "equilibrium_temperature → T_eq",
            "climate_insolation → add to F",
            "init: initial_temperature_field",
        ],
        "resource_ecology_A_enabled": [
            "step_climate_resources → R_A production/decay (uses current physical T)",
            "init: initial_resource_fields for R_A",
        ],
        "resource_ecology_B_enabled": [
            "step_climate_resources → R_B production/decay (uses current physical T)",
            "init: initial_resource_fields for R_B",
        ],
        "step_thermal": "always; cools toward T_eq if climate ON else T_ref",
        "step_flow": "vx,vy ≈ -flow_gain·∇T if flow_enabled (NOT gated by climate)",
        "body.flow_coupling × planet.vx/vy": "direct site force (orientation/morphology)",
        "body.wave_coupling × u × unit(vx,vy)": (
            "wave/site force steered by thermal-flow direction; "
            "NOT gated by flow_coupling — latent locomotor channel"
        ),
        "terrain.enabled": "static potential/drag/grad → body forces (independent)",
        "ambient.enabled": "static Fx/Fy → body forces (independent)",
        "near_field_exteroception": "illumination + surface_response (observational; independent)",
    },
    "edges": [
        "F_fast/F_slow --independent--> F",
        "climate_enabled --> T_eq --> step_thermal(T)",
        "climate_enabled --> climate_insolation --> F",
        "T --> ∇T --> vx/vy (if flow_enabled)",
        "vx/vy --> body force (if flow_coupling>0)",
        "vx/vy --> unit direction --> wave body force (if wave_coupling>0; independent of flow_coupling)",
        "resource_ecology_A_enabled --> R_A production/decay (uses current T; NOT gated by climate_enabled)",
        "resource_ecology_B_enabled --> R_B production/decay (uses current T; NOT gated by climate_enabled)",
        "T (+ geo_suit) --> resource productivity modulation",
        "terrain --independent--> body",
        "ambient --independent--> body",
        "illumination --independent--> exo sensor only",
    ],
}

VX_VY_SEMANTICS = {
    "formula": "ax,ay = -flow_gain * ∇T; vx,vy damped and clipped by flow_max",
    "source": "mechanistic_mind/planet/dynamics.py::step_flow",
    "comment_in_code": "pressure-like tendency ~ -grad T (warm rises conceptually as outflow from hot)",
    "interpretation": (
        "Temperature-derived proxy horizontal flow field on the planet grid — "
        "not a labeled fluid/wind/current. Used for matter advection and as the "
        "velocity sampled into body site forces via body.flow_coupling, and as the "
        "direction unit for wave_coupling*u site forces (orientation path)."
    ),
    "body_coupling_channels": [
        "direct: flow_coupling * vx/vy * force_scale",
        "wave_steering: 0.15 * wave_coupling * u * unit(vx,vy) * force_scale",
    ],
    "ablation_note": (
        "Setting flow_coupling=0 alone does not remove thermal locomotor coupling "
        "while flow_enabled keeps non-zero vx/vy; wave steering remains. "
        "Clean body-transport ablation requires flow_enabled=False (T still evolves)."
    ),
    "gated_by_climate_ecology_enabled": False,
    "gated_by_flow_enabled": True,
}


def effective_world_fingerprint(eff: dict[str, Any] | None = None, *, runtime=None) -> str:
    """Compact hash of physically relevant effective configuration (no cognition)."""
    if eff is None:
        if runtime is None:
            raise ValueError("runtime or eff required")
        eff = effective_world_configuration(runtime)
    payload = {
        "preset": eff.get("normalized_preset") or eff.get("requested_preset"),
        "climate": eff.get("climate_ecology"),
        "forcing": eff.get("planet_forcing"),
        "body_flow_coupling": eff.get("body_flow_coupling"),
        "terrain_checksum": (eff.get("terrain") or {}).get("checksum"),
        "ambient_checksum": (eff.get("ambient") or {}).get("checksum"),
        "illumination": eff.get("illumination"),
        "overrides": sorted(eff.get("overrides") or []),
        "subsystems": eff.get("subsystems"),
    }
    blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def compare_configs(a: PhysicalSystemConfig, b: PhysicalSystemConfig) -> dict[str, Any]:
    """Compare resolved physical knobs between two configs."""
    diffs: list[dict[str, Any]] = []

    def _cmp(path: str, x: Any, y: Any) -> None:
        if isinstance(x, float) or isinstance(y, float):
            if abs(float(x or 0) - float(y or 0)) > 1e-12:
                diffs.append({"path": path, "a": x, "b": y})
        elif x != y:
            diffs.append({"path": path, "a": x, "b": y})

    _cmp("ecology_preset", a.ecology_preset, b.ecology_preset)
    pa, pb = a.planet, b.planet
    cea, ceb = pa.climate_ecology, pb.climate_ecology
    _cmp("climate.enabled", cea.enabled, ceb.enabled)
    _cmp("climate.season_period", cea.season_period, ceb.season_period)
    _cmp("climate.subsolar_bias", getattr(cea, "subsolar_bias", None), getattr(ceb, "subsolar_bias", None))
    _cmp("climate.resources_enabled", cea.resources_enabled, ceb.resources_enabled)
    _cmp(
        "climate.resource_ecology_A_enabled",
        getattr(cea, "resource_ecology_A_enabled", True),
        getattr(ceb, "resource_ecology_A_enabled", True),
    )
    _cmp(
        "climate.resource_ecology_B_enabled",
        getattr(cea, "resource_ecology_B_enabled", True),
        getattr(ceb, "resource_ecology_B_enabled", True),
    )
    _cmp("F_fast_amp", pa.F_fast_amp, pb.F_fast_amp)
    _cmp("F_fast_period", pa.F_fast_period, pb.F_fast_period)
    _cmp("F_slow_amp", pa.F_slow_amp, pb.F_slow_amp)
    _cmp("flow_enabled", pa.flow_enabled, pb.flow_enabled)
    _cmp("flow_gain", pa.flow_gain, pb.flow_gain)
    _cmp("terrain.enabled", pa.terrain.enabled, pb.terrain.enabled)
    _cmp("ambient.enabled", pa.ambient.enabled, pb.ambient.enabled)
    _cmp("body.flow_coupling", a.body.flow_coupling, b.body.flow_coupling)
    return {"n_diffs": len(diffs), "diffs": diffs, "match": len(diffs) == 0}


def harness_calibrated_config() -> PhysicalSystemConfig:
    """Same construction as HABITABLE_WORLD_CALIBRATION_01 style."""
    return make_ecology_config(ECOLOGY_CALIBRATED_TEMPORAL, trickle=0.0)


def interactive_calibrated_config() -> PhysicalSystemConfig:
    """Interactive Apply path: make_ecology_config on bare PSR base."""
    base = PhysicalSystemConfig()
    return make_ecology_config(ECOLOGY_CALIBRATED_TEMPORAL, base=base, trickle=0.0)


AUDIT_GATES = {
    "C1_CONFIG_AUTHORITY_KNOWN": "Every climate-related subsystem has traceable authority",
    "C2_PRESET_EFFECTIVE_MATCH": "Canonical calibrated preset produces expected effective config",
    "C3_OBSERVER_GT_MATCH": "Observer reports actual runtime state",
    "C4_ACTIVE_MECHANISM_MATCH": "Active mechanisms correspond to climate_ecology.enabled",
    "C5_TERRAIN_INDEPENDENT": "Climate toggle does not alter static terrain",
    "C6_AMBIENT_INDEPENDENT": "Climate toggle does not alter static ambient",
    "C7_ILLUMINATION_INDEPENDENT": "Climate toggle does not silently disable illumination",
    "C8_RESOURCE_DEPENDENCY_KNOWN": "R_A/R_B dependency on climate explicitly traced",
    "C9_THERMAL_FLOW_DEPENDENCY_KNOWN": "T→flow→body path explicitly traced",
    "C10_CALIBRATION_RUNTIME_MATCH": "Harness and interactive construct equivalent worlds",
    "C11_ABLATION_EXPLICIT": "Deviation from canonical preset visible as override",
    "C12_NO_COGNITION_CHANGE": "No cognition architecture/parameter changes",
    "C13_NO_PERCEPTION_GT_LEAK": "Climate decomposition does not expose new GT",
    "C14_WORLD_FINGERPRINT_DIFFERENTIATES": "Different effective worlds → different fingerprints",
    "C15_TRAJECTORY_METRICS_VALID": "Decomposition movement metrics pass path/velocity consistency",
}
