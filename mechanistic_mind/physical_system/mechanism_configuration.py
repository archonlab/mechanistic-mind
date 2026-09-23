"""Single resolved mechanism configuration authority + startup preflight.

Scientific rule: a checkbox / saved config is not evidence a mechanism existed.
A mechanism is active for a run only when the constructed runtime verifies it.

Precedence for a NEW experiment (no explicit persisted mechanism map):
  NORMAL_DEFAULTS  (all normal ON except climate OFF)
  ← ecology preset stamps (may enable vision/terrain/etc.)
  ← explicit user overrides

Legacy configs with explicit values are preserved; missing new fields use
documented migration (DEFAULT for newly introduced normal mechanisms).
"""
from __future__ import annotations

import hashlib
import json
import time
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Iterable

from mechanistic_mind.physical_system.mechanism_registry import (
    MECHANISM_DEFS,
    mechanism_snapshot,
    set_mechanism,
)

RESOLVED_CONFIG_VERSION = "ci_mech_cfg_v1"
MANIFEST_SCHEMA = "mm.runtime_mechanism_manifest.v1"

# --- Catalog classification -------------------------------------------------

# Experimental cognition adapters — NOT part of normal full MM organism.
EXPERIMENTAL_COGNITION_EXCLUDE: frozenset[str] = frozenset({
    "unknown_action_physical_probe",
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
})

# Always present structural bridges — not user-default toggles for "full organism".
READ_ONLY_STRUCTURAL: frozenset[str] = frozenset({
    "discrete_action_bridge",
    "shared_work_allocation",
    "environmental_site_mechanics",
})

# Climate remains intentionally OFF for fresh experiments.
CLIMATE_MECHANISM_ID = "spatiotemporal_climate_ecology"

# World subsystems tracked alongside registry mechanisms (not MECHANISM_DEFS).
WORLD_SUBSYSTEM_IDS: tuple[str, ...] = (
    "terrain_geography",
    "ambient_physical_dynamics",
)

# Fresh-experiment vision Moore radius (R3). Does not change legacy DEFAULT_VISION_RADIUS=1.
NEW_EXPERIMENT_VISION_RADIUS = 3


def _registry_ids() -> list[str]:
    return [str(d["id"]) for d in MECHANISM_DEFS]


def normal_mechanism_ids() -> list[str]:
    """Mechanisms intended ON for a full normal MM organism (except climate)."""
    out: list[str] = []
    for d in MECHANISM_DEFS:
        mid = str(d["id"])
        if mid in EXPERIMENTAL_COGNITION_EXCLUDE:
            continue
        if mid in READ_ONLY_STRUCTURAL:
            continue  # always-on structural; not part of default toggle policy map
        if mid == CLIMATE_MECHANISM_ID:
            continue  # intentional OFF
        out.append(mid)
    return out


def excluded_mechanism_catalog() -> list[dict[str, Any]]:
    """Documented exclusions from normal-default ON policy."""
    rows: list[dict[str, Any]] = []
    for mid in sorted(EXPERIMENTAL_COGNITION_EXCLUDE):
        rows.append({
            "id": mid,
            "category": "EXPERIMENTAL_COGNITION",
            "default": False,
            "reason": "Unpromoted experimental cognition adapter; unsafe/incomplete for normal default ON",
        })
    rows.append({
        "id": "prospective_scenario_competition",
        "category": "COGNITION",
        "default": False,
        "reason": "Experience-first: PSC default OFF; enable after sensorimotor/history accumulate. Hot-toggle safe.",
    })
    rows.append({
        "id": CLIMATE_MECHANISM_ID,
        "category": "WORLD",
        "default": False,
        "reason": "Climate Ecology intentionally independent; default OFF; Resource Ecology remains ON",
    })
    for mid in sorted(READ_ONLY_STRUCTURAL):
        rows.append({
            "id": mid,
            "category": "STRUCTURAL_READ_ONLY",
            "default": True,
            "reason": "Always-on structural bridge; not an ablatable normal-default toggle",
        })
    return rows


def fresh_experiment_default_map() -> dict[str, bool]:
    """Authoritative defaults for a genuinely NEW experiment (no explicit map)."""
    m: dict[str, bool] = {}
    for mid in normal_mechanism_ids():
        m[mid] = True
    m[CLIMATE_MECHANISM_ID] = False
    # Experience-first: PSC OFF so history/SMC accumulate before prospection competes.
    m["prospective_scenario_competition"] = False
    for mid in EXPERIMENTAL_COGNITION_EXCLUDE:
        m[mid] = False
    # World subsystems (tracked, applied via planet config stamps).
    m["terrain_geography"] = True
    m["ambient_physical_dynamics"] = True
    return m


def mechanism_catalog() -> dict[str, Any]:
    """Full audited catalog for artifacts / Observer schema."""
    defaults = fresh_experiment_default_map()
    registry = []
    for d in MECHANISM_DEFS:
        mid = str(d["id"])
        registry.append({
            **{k: d[k] for k in ("id", "label", "description", "default_integrated", "ablatable") if k in d},
            "classification": (
                "EXPERIMENTAL_EXCLUDE" if mid in EXPERIMENTAL_COGNITION_EXCLUDE
                else "CLIMATE_DEFAULT_OFF" if mid == CLIMATE_MECHANISM_ID
                else "STRUCTURAL_READ_ONLY" if mid in READ_ONLY_STRUCTURAL
                else "NORMAL"
            ),
            "fresh_default": defaults.get(mid),
        })
    return {
        "resolved_config_version": RESOLVED_CONFIG_VERSION,
        "registry_mechanisms": registry,
        "world_subsystems": [
            {"id": "terrain_geography", "fresh_default": True, "classification": "NORMAL"},
            {"id": "ambient_physical_dynamics", "fresh_default": True, "classification": "NORMAL"},
        ],
        "params": {"vision_radius": NEW_EXPERIMENT_VISION_RADIUS},
        "excluded": excluded_mechanism_catalog(),
        "normal_ids": normal_mechanism_ids(),
    }


# --- Resolution -------------------------------------------------------------

@dataclass
class ResolvedMechanismConfig:
    """One authoritative resolved mechanism configuration for runtime construction."""

    mechanisms: dict[str, bool]
    params: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, str] = field(default_factory=dict)  # id → DEFAULT|EXPLICIT|PRESET|MIGRATED
    version: str = RESOLVED_CONFIG_VERSION
    source: str = "NEW_EXPERIMENT"  # NEW_EXPERIMENT | EXPLICIT | LEGACY

    def fingerprint(self) -> str:
        payload = {
            "version": self.version,
            "mechanisms": {k: bool(self.mechanisms[k]) for k in sorted(self.mechanisms)},
            "params": self.params,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "source": self.source,
            "mechanisms": dict(self.mechanisms),
            "params": dict(self.params),
            "provenance": dict(self.provenance),
            "fingerprint": self.fingerprint(),
        }


def _coerce_bool(v: Any) -> bool | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)) and v in (0, 1):
        return bool(v)
    if isinstance(v, str):
        s = v.strip().upper()
        if s in {"1", "TRUE", "ON", "YES", "EXPERIMENTAL"}:
            return True
        if s in {"0", "FALSE", "OFF", "NO"}:
            return False
    return None


def resolve_mechanism_config(
    requested: dict[str, Any] | None = None,
    *,
    vision_radius: int | None = None,
    source_hint: str | None = None,
    apply_fresh_defaults: bool | None = None,
) -> ResolvedMechanismConfig:
    """Resolve requested/explicit overrides against fresh defaults.

    If ``requested`` is None/empty and apply_fresh_defaults is True (default),
    use fresh NEW_EXPERIMENT defaults.

    If ``requested`` has any explicit mechanism keys, those win; missing keys
    for newly introduced normal mechanisms are MIGRATED to fresh defaults
    unless ``apply_fresh_defaults`` is False (strict legacy → leave absent).
    """
    req = dict(requested or {})
    # Flatten nested cognition-style maps if present.
    if "mechanisms" in req and isinstance(req["mechanisms"], dict):
        nested = dict(req["mechanisms"])
        req = {**nested, **{k: v for k, v in req.items() if k != "mechanisms"}}

    explicit_keys = {
        k for k, v in req.items()
        if k not in {"vision_radius", "cognition_enabled"}
        and _coerce_bool(v) is not None
        and (k in _registry_ids() or k in WORLD_SUBSYSTEM_IDS or k == "cognition")
    }
    # cognition_enabled alias
    if "cognition_enabled" in req and _coerce_bool(req.get("cognition_enabled")) is not None:
        explicit_keys.add("cognition")

    use_fresh = apply_fresh_defaults if apply_fresh_defaults is not None else True
    base = fresh_experiment_default_map() if use_fresh else {}
    # When any explicit overrides exist, non-overridden filled defaults are MIGRATED.
    base_prov = "MIGRATED" if (use_fresh and explicit_keys) else "DEFAULT"
    provenance: dict[str, str] = {k: base_prov for k in base}
    mechanisms = dict(base)

    if "cognition_enabled" in req and _coerce_bool(req.get("cognition_enabled")) is not None:
        mechanisms["cognition"] = bool(_coerce_bool(req["cognition_enabled"]))
        provenance["cognition"] = "EXPLICIT"

    for k in explicit_keys:
        if k == "cognition" and "cognition_enabled" in req:
            continue  # already handled
        bv = _coerce_bool(req.get(k))
        if bv is None:
            continue
        mechanisms[k] = bv
        provenance[k] = "EXPLICIT"

    # Migration fill already handled via base_prov when explicit_keys present.
    if use_fresh and explicit_keys:
        for mid, default_on in fresh_experiment_default_map().items():
            if mid not in mechanisms:
                mechanisms[mid] = default_on
                provenance[mid] = "MIGRATED"

    params: dict[str, Any] = {
        "vision_radius": int(vision_radius) if vision_radius is not None
        else int(req.get("vision_radius") or NEW_EXPERIMENT_VISION_RADIUS),
    }
    if vision_radius is not None or "vision_radius" in req:
        provenance["vision_radius"] = "EXPLICIT" if (vision_radius is not None or "vision_radius" in req) else "DEFAULT"
    else:
        provenance["vision_radius"] = "DEFAULT"

    source = source_hint or ("EXPLICIT" if explicit_keys else "NEW_EXPERIMENT")
    return ResolvedMechanismConfig(
        mechanisms=mechanisms,
        params=params,
        provenance=provenance,
        source=source,
    )


def stamp_config_world_subsystems(config: Any, resolved: ResolvedMechanismConfig) -> None:
    """Stamp terrain/ambient onto planet config before runtime construction."""
    from mechanistic_mind.planet.ambient import AmbientConfig
    from mechanistic_mind.planet.terrain import TerrainConfig

    planet = getattr(config, "planet", None)
    if planet is None:
        return
    if resolved.mechanisms.get("terrain_geography", False):
        existing = getattr(planet, "terrain", None)
        if existing is None or not bool(getattr(existing, "enabled", False)):
            planet.terrain = TerrainConfig(
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
                terrain_seed=None,
            )
        else:
            existing.enabled = True
    else:
        te = getattr(planet, "terrain", None)
        if te is not None:
            te.enabled = False

    if resolved.mechanisms.get("ambient_physical_dynamics", False):
        existing_a = getattr(planet, "ambient", None)
        if existing_a is None or not bool(getattr(existing_a, "enabled", False)):
            planet.ambient = AmbientConfig(
                enabled=True,
                amplitude=0.018,
                correlation_scale=8.0,
                large_scale_weight=0.65,
                medium_scale_weight=0.35,
                wait_force_scale=0.15,
                kinetic_speed_threshold=0.025,
            )
        else:
            existing_a.enabled = True
    else:
        amb = getattr(planet, "ambient", None)
        if amb is not None:
            amb.enabled = False


def stamp_config_mechanisms(config: Any, resolved: ResolvedMechanismConfig) -> None:
    """Apply resolved toggles onto a PhysicalSystemConfig (pre-construction)."""
    stamp_config_world_subsystems(config, resolved)
    # Vision radius before enabling so construction installs correct NFE.
    from mechanistic_mind.physical_system.near_field_exteroception import (
        NearFieldExteroceptionConfig,
        clamp_vision_radius,
    )
    nfe = getattr(config, "near_field_exteroception", None)
    if nfe is None:
        config.near_field_exteroception = NearFieldExteroceptionConfig()
        nfe = config.near_field_exteroception
    nfe.radius = clamp_vision_radius(resolved.params.get("vision_radius", NEW_EXPERIMENT_VISION_RADIUS))

    for mid, enabled in resolved.mechanisms.items():
        if mid in WORLD_SUBSYSTEM_IDS:
            continue
        if mid in READ_ONLY_STRUCTURAL:
            continue
        try:
            set_mechanism(config, mid, bool(enabled))
        except KeyError:
            continue

    # Climate OFF must not disable resource ecology when resources requested ON.
    ce = getattr(getattr(config, "planet", None), "climate_ecology", None)
    if ce is not None:
        if resolved.mechanisms.get("resource_ecology_A") is not None:
            ce.resource_ecology_A_enabled = bool(resolved.mechanisms["resource_ecology_A"])
        if resolved.mechanisms.get("resource_ecology_B") is not None:
            ce.resource_ecology_B_enabled = bool(resolved.mechanisms["resource_ecology_B"])
        ce.resources_enabled = bool(
            getattr(ce, "resource_ecology_A_enabled", False)
            or getattr(ce, "resource_ecology_B_enabled", False)
        )
        if CLIMATE_MECHANISM_ID in resolved.mechanisms:
            ce.enabled = bool(resolved.mechanisms[CLIMATE_MECHANISM_ID])


def apply_resolved_to_runtime(runtime: Any, resolved: ResolvedMechanismConfig) -> dict[str, Any]:
    """Post-construction bind: set_mechanism for world side-effects + verify path.

    Prefer stamp_config_mechanisms before construction; this re-applies to catch
    ecology preset overwrites and install surface/signal fields.
    """
    applied: list[str] = []
    errors: list[str] = []
    # Re-stamp config in case ecology overwrote.
    cfg = getattr(runtime, "config", None)
    if cfg is not None:
        stamp_config_mechanisms(cfg, resolved)

    setter = getattr(runtime, "set_mechanism", None)
    for mid, enabled in resolved.mechanisms.items():
        if mid in WORLD_SUBSYSTEM_IDS or mid in READ_ONLY_STRUCTURAL:
            continue
        if setter is None:
            break
        try:
            setter(mid, bool(enabled))
            applied.append(mid)
        except Exception as exc:  # noqa: BLE001 — collect, fail in preflight
            errors.append(f"{mid}: {exc}")

    # Vision radius LIVE path.
    if hasattr(runtime, "set_vision_radius"):
        try:
            runtime.set_vision_radius(int(resolved.params.get("vision_radius", NEW_EXPERIMENT_VISION_RADIUS)))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"vision_radius: {exc}")

    # Ensure terrain / ambient fields if enabled.
    planet_cfg = getattr(getattr(runtime, "config", None), "planet", None)
    te = getattr(planet_cfg, "terrain", None) if planet_cfg else None
    if te is not None and bool(getattr(te, "enabled", False)):
        try:
            from mechanistic_mind.planet.terrain import install_terrain_on_planet
            install_terrain_on_planet(
                runtime.world, experiment_seed=int(getattr(runtime, "seed", 0)), config=te,
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"terrain: {exc}")

    amb = getattr(planet_cfg, "ambient", None) if planet_cfg else None
    if amb is not None and bool(getattr(amb, "enabled", False)):
        try:
            from mechanistic_mind.planet.ambient import install_ambient_on_planet
            install_ambient_on_planet(
                runtime.world, experiment_seed=int(getattr(runtime, "seed", 0)), config=amb,
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"ambient: {exc}")

    return {"applied": applied, "errors": errors}


# --- Preflight / availability ----------------------------------------------

def _runtime_enabled_map(runtime: Any) -> dict[str, bool | None]:
    snap = mechanism_snapshot(runtime.config) if hasattr(runtime, "config") else {"enabled": {}}
    enabled = dict(snap.get("enabled") or {})
    # Fill from mechanisms list if needed.
    for m in snap.get("mechanisms") or []:
        mid = m.get("id")
        if mid is not None and mid not in enabled:
            enabled[mid] = m.get("enabled")
    planet = getattr(getattr(runtime, "config", None), "planet", None)
    te = getattr(planet, "terrain", None) if planet else None
    amb = getattr(planet, "ambient", None) if planet else None
    enabled["terrain_geography"] = bool(getattr(te, "enabled", False)) if te is not None else False
    enabled["ambient_physical_dynamics"] = bool(getattr(amb, "enabled", False)) if amb is not None else False
    return enabled


def _sensor_availability(runtime: Any, mechanism_id: str) -> dict[str, Any]:
    """Capability checks — zero readings are valid."""
    cfg = getattr(runtime, "config", None)
    body = getattr(runtime, "body", None)
    world = getattr(runtime, "world", None)
    out: dict[str, Any] = {"available": False, "details": {}}
    if mechanism_id == "physical_near_field_vision":
        nfe = getattr(cfg, "near_field_exteroception", None)
        contributes = bool(getattr(nfe, "vision_contributes", False)) if nfe else False
        surface = getattr(world, "surface_response", None) is not None
        radius = int(getattr(nfe, "effective_radius", getattr(nfe, "radius", 1)) or 1) if nfe else None
        out["available"] = bool(contributes and surface and nfe is not None)
        out["details"] = {
            "vision_contributes": contributes,
            "surface_installed": surface,
            "radius": radius,
            "exo_channels": ["exo_0", "exo_1", "exo_2"],
        }
    elif mechanism_id == "illumination_cycle":
        nfe = getattr(cfg, "near_field_exteroception", None)
        on = bool(getattr(nfe, "enabled", False) and getattr(nfe, "illumination_enabled", False)) if nfe else False
        out["available"] = on
        out["details"] = {"illumination_enabled": on}
    elif mechanism_id == "physical_body_optical_response":
        nfe = getattr(cfg, "near_field_exteroception", None)
        on = bool(getattr(nfe, "enabled", False) and getattr(nfe, "body_optical_enabled", False)) if nfe else False
        out["available"] = on
    elif mechanism_id == "physical_vestibular_sensing":
        vest = getattr(cfg, "vestibular", None)
        on = bool(getattr(vest, "enabled", False)) if vest else False
        out["available"] = on
        out["details"] = {"channels": ["vest_0", "vest_1"], "note": "zero is valid"}
    elif mechanism_id == "neck_proprioception":
        prop = getattr(cfg, "neck_proprioception", None)
        head = getattr(cfg, "articulated_head", None)
        on = bool(getattr(prop, "enabled", False) and getattr(head, "enabled", False)) if prop else False
        out["available"] = on
        out["details"] = {"channels": ["prop_neck_0", "prop_neck_1"], "requires_articulated_head": True}
    elif mechanism_id == "articulated_head":
        head = getattr(cfg, "articulated_head", None)
        on = bool(getattr(head, "enabled", False)) if head else False
        has_fields = body is not None and hasattr(body, "head_relative_angle")
        out["available"] = bool(on and has_fields)
        out["details"] = {
            "neck_motors": ["NECK_LEFT", "NECK_RIGHT", "NECK_HOLD"] if on else [],
            "body_fields": has_fields,
        }
    elif mechanism_id == "physical_push":
        push = getattr(cfg, "physical_push", None)
        on = bool(getattr(push, "enabled", False)) if push else False
        out["available"] = on
        out["details"] = {"action": "PUSH", "note": "registration only; usage not required"}
    elif mechanism_id == "experimental_physical_signal":
        sig = getattr(cfg, "physical_signal", None)
        on = str(getattr(sig, "mode", "OFF")).upper() == "EXPERIMENTAL" if sig else False
        out["available"] = on
    elif mechanism_id == "oscillatory_signaling":
        osc = getattr(cfg, "oscillatory_signaling", None)
        on = bool(getattr(osc, "enabled", False)) if osc else False
        bands = getattr(getattr(runtime, "world", None), "OSC_BANDS", None)
        n = int(getattr(osc, "n_bands", 6) or 6) if osc else 6
        channels = [f"osc_l_{i}" for i in range(n)] + [f"osc_r_{i}" for i in range(n)]
        out["available"] = bool(on and bands is not None)
        out["details"] = {
            "channels": channels,
            "emitter_actions": ["OSC_FREQ_UP", "OSC_FREQ_DOWN", "OSC_AMP_UP", "OSC_AMP_DOWN", "OSC_EMIT"],
            "note": "zero band energy is valid; availability ≠ nonzero activity",
            "finite_propagation": getattr(osc, "finite_propagation", "NOT_IMPLEMENTED") if osc else None,
        }
    elif mechanism_id == "resource_ecology_A":
        ce = getattr(getattr(cfg, "planet", None), "climate_ecology", None)
        out["available"] = bool(getattr(ce, "resource_ecology_A_enabled", False)) if ce else False
    elif mechanism_id == "resource_ecology_B":
        ce = getattr(getattr(cfg, "planet", None), "climate_ecology", None)
        out["available"] = bool(getattr(ce, "resource_ecology_B_enabled", False)) if ce else False
    elif mechanism_id == CLIMATE_MECHANISM_ID:
        ce = getattr(getattr(cfg, "planet", None), "climate_ecology", None)
        out["available"] = bool(getattr(ce, "enabled", False)) if ce else False
    elif mechanism_id == "terrain_geography":
        te = getattr(getattr(cfg, "planet", None), "terrain", None)
        out["available"] = bool(getattr(te, "enabled", False)) if te else False
    elif mechanism_id == "ambient_physical_dynamics":
        amb = getattr(getattr(cfg, "planet", None), "ambient", None)
        out["available"] = bool(getattr(amb, "enabled", False)) if amb else False
    elif mechanism_id == "cognition":
        cog = getattr(cfg, "cognition", None)
        out["available"] = bool(getattr(cog, "cognition_enabled", False)) if cog else False
    else:
        # Generic: available iff runtime enabled matches expectation path via snapshot.
        en = _runtime_enabled_map(runtime).get(mechanism_id)
        out["available"] = bool(en)
    return out


@dataclass
class PreflightResult:
    status: str  # READY | PREFLIGHT_FAILED
    rows: list[dict[str, Any]]
    mismatches: list[dict[str, Any]]
    latency_ms: float
    resolved_fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "rows": self.rows,
            "mismatches": self.mismatches,
            "latency_ms": self.latency_ms,
            "resolved_fingerprint": self.resolved_fingerprint,
            "ready": self.status == "READY",
        }


def run_preflight(runtime: Any, resolved: ResolvedMechanismConfig) -> PreflightResult:
    """Compare CONFIGURED vs actual RUNTIME + AVAILABLE. Does not start ticks."""
    t0 = time.perf_counter()
    runtime_map = _runtime_enabled_map(runtime)
    rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []

    # Keys to verify: union of resolved + critical world subsystems.
    keys = sorted(set(resolved.mechanisms) | set(WORLD_SUBSYSTEM_IDS))
    for mid in keys:
        if mid in READ_ONLY_STRUCTURAL:
            continue
        configured = bool(resolved.mechanisms.get(mid, False))
        runtime_val = runtime_map.get(mid)
        runtime_on = bool(runtime_val) if runtime_val is not None else False
        avail = _sensor_availability(runtime, mid)
        available = bool(avail.get("available")) if configured else (not bool(avail.get("available")) or True)
        # Availability required only when configured ON.
        if configured:
            status = "READY" if (runtime_on and bool(avail.get("available"))) else "CONFIGURATION_MISMATCH"
        else:
            status = "READY" if (not runtime_on) else "CONFIGURATION_MISMATCH"
        row = {
            "mechanism": mid,
            "configured": configured,
            "runtime": runtime_on,
            "available": bool(avail.get("available")) if configured else None,
            "status": status,
            "provenance": resolved.provenance.get(mid, "DEFAULT"),
            "details": avail.get("details") or {},
        }
        if mid == "physical_near_field_vision":
            nfe = getattr(getattr(runtime, "config", None), "near_field_exteroception", None)
            row["radius"] = int(getattr(nfe, "radius", NEW_EXPERIMENT_VISION_RADIUS) or NEW_EXPERIMENT_VISION_RADIUS) if nfe else None
            want_r = int(resolved.params.get("vision_radius", NEW_EXPERIMENT_VISION_RADIUS))
            row["configured_radius"] = want_r
            row["runtime_radius"] = row.get("radius")
            if configured and row.get("radius") != want_r:
                row["status"] = "CONFIGURATION_MISMATCH"
                row["details"] = {
                    **(row["details"] or {}),
                    "expected_radius": want_r,
                    "configured_radius": want_r,
                    "runtime_radius": row.get("radius"),
                }
        rows.append(row)
        if row["status"] != "READY":
            mismatches.append(row)

    # Composite motor routing integrity (does not weaken existing checks).
    cog = getattr(getattr(runtime, "config", None), "cognition", None)
    composite_on = bool(getattr(cog, "composite_motor", True)) if cog else True
    head_on = bool(getattr(getattr(getattr(runtime, "config", None), "articulated_head", None), "enabled", False))
    osc_on = bool(getattr(getattr(getattr(runtime, "config", None), "oscillatory_signaling", None), "enabled", False))
    push_on = bool(getattr(getattr(getattr(runtime, "config", None), "physical_push", None), "enabled", False))
    acts = []
    try:
        from mechanistic_mind.physical_system.actions import available_actions as _aa
        acts = list(_aa(articulated_head=head_on, physical_push=push_on, oscillatory_signaling=osc_on))
    except Exception:  # noqa: BLE001
        acts = []
    motor_row = {
        "mechanism": "composite_motor_control",
        "configured": composite_on,
        "runtime": composite_on,
        "available": True,
        "status": "READY",
        "provenance": "DEFAULT",
        "details": {
            "motor_control_schema": "COMPOSITE_MOTOR_V1" if composite_on else "LEGACY_SINGLE_SLOT",
            "locomotion_component": any(a == "WAIT" or str(a).startswith("MOVE:") for a in acts),
            "neck_component": (not head_on) or any(str(a).startswith("NECK_") for a in acts),
            "oscillator_component": (not osc_on) or any(str(a).startswith("OSC_") for a in acts),
            "push_component": (not push_on) or ("PUSH" in acts),
            "sensors_not_in_action_space": True,
            "note": "Perception is continuous; no LISTEN/SEE action required.",
        },
    }
    if composite_on:
        ok = bool(motor_row["details"]["locomotion_component"])
        if head_on and not motor_row["details"]["neck_component"]:
            ok = False
        if osc_on and not motor_row["details"]["oscillator_component"]:
            ok = False
        if push_on and not motor_row["details"]["push_component"]:
            ok = False
        if not ok:
            motor_row["status"] = "CONFIGURATION_MISMATCH"
            mismatches.append(motor_row)
    rows.append(motor_row)

    status = "READY" if not mismatches else "PREFLIGHT_FAILED"
    return PreflightResult(
        status=status,
        rows=rows,
        mismatches=mismatches,
        latency_ms=(time.perf_counter() - t0) * 1000.0,
        resolved_fingerprint=resolved.fingerprint(),
    )


def build_runtime_manifest(
    *,
    runtime: Any,
    resolved: ResolvedMechanismConfig,
    preflight: PreflightResult,
    run_id: str | None,
    generation: int,
) -> dict[str, Any]:
    """Compact immutable run-start manifest (once per scientific run)."""
    nfe = getattr(getattr(runtime, "config", None), "near_field_exteroception", None)
    head = getattr(getattr(runtime, "config", None), "articulated_head", None)
    vest = getattr(getattr(runtime, "config", None), "vestibular", None)
    prop = getattr(getattr(runtime, "config", None), "neck_proprioception", None)
    push = getattr(getattr(runtime, "config", None), "physical_push", None)
    planet = getattr(getattr(runtime, "config", None), "planet", None)
    te = getattr(planet, "terrain", None) if planet else None
    amb = getattr(planet, "ambient", None) if planet else None
    ce = getattr(planet, "climate_ecology", None) if planet else None

    manifest = {
        "schema": MANIFEST_SCHEMA,
        "resolved_config_version": RESOLVED_CONFIG_VERSION,
        "run_id": run_id,
        "generation": int(generation),
        "preflight_tick_marker": "BEFORE_TICK_1",
        "runtime_tick_at_manifest": int(getattr(runtime, "tick", 0) or 0),
        "preflight_status": preflight.status,
        "resolved_fingerprint": resolved.fingerprint(),
        "source": resolved.source,
        "mechanisms": [
            {
                "id": r["mechanism"],
                "configured": r["configured"],
                "runtime": r["runtime"],
                "available": r["available"],
                "status": r["status"],
                "provenance": r.get("provenance"),
            }
            for r in preflight.rows
        ],
        "params": {
            "vision": {
                "enabled": bool(resolved.mechanisms.get("physical_near_field_vision")),
                "radius": int(resolved.params.get("vision_radius", NEW_EXPERIMENT_VISION_RADIUS)),
                "illumination": bool(resolved.mechanisms.get("illumination_cycle")),
                "body_optical": bool(resolved.mechanisms.get("physical_body_optical_response")),
                "fov_deg": float(getattr(nfe, "fov_deg", 120.0) or 120.0) if nfe else None,
            },
            "articulated_head": {
                "enabled": bool(getattr(head, "enabled", False)) if head else False,
                "neck_angle_limit": float(getattr(head, "neck_angle_limit", 0.0) or 0.0) if head else None,
            },
            "vestibular": {
                "enabled": bool(getattr(vest, "enabled", False)) if vest else False,
                "channels": ["vest_0", "vest_1"],
            },
            "neck_proprioception": {
                "enabled": bool(getattr(prop, "enabled", False)) if prop else False,
                "channels": ["prop_neck_0", "prop_neck_1"],
            },
            "push": {"enabled": bool(getattr(push, "enabled", False)) if push else False},
            "motor_control_schema": (
                "COMPOSITE_MOTOR_V1"
                if bool(getattr(getattr(getattr(runtime, "config", None), "cognition", None), "composite_motor", True))
                else "LEGACY_SINGLE_SLOT"
            ),
            "oscillatory_signaling": {
                "enabled": bool(
                    getattr(getattr(getattr(runtime, "config", None), "oscillatory_signaling", None), "enabled", False)
                ),
            },
            "resource_ecology": {
                "A": bool(getattr(ce, "resource_ecology_A_enabled", False)) if ce else False,
                "B": bool(getattr(ce, "resource_ecology_B_enabled", False)) if ce else False,
            },
            "climate": {"enabled": bool(getattr(ce, "enabled", False)) if ce else False},
            "terrain": {"enabled": bool(getattr(te, "enabled", False)) if te else False},
            "ambient": {"enabled": bool(getattr(amb, "enabled", False)) if amb else False},
        },
        "checksum": "",
    }
    raw = json.dumps(
        {k: v for k, v in manifest.items() if k != "checksum"},
        sort_keys=True, separators=(",", ":"), default=str,
    )
    manifest["checksum"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]
    return manifest


def summarize_mechanism_integrity(
    *,
    manifest: dict[str, Any] | None,
    interventions: Iterable[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Analyzer section: RUNTIME MECHANISM INTEGRITY (conservative)."""
    if not manifest:
        return {
            "section": "RUNTIME MECHANISM INTEGRITY",
            "runtime_mechanism_manifest": "NOT_AVAILABLE",
            "preflight_status": "NOT_AVAILABLE",
            "note": "Do not infer verified startup state from config fields alone.",
        }
    live = []
    for ev in interventions or []:
        t = str(ev.get("type") or ev.get("operation") or "")
        if "MECHANISM" in t.upper() or "INTERVENTION" in t.upper():
            live.append({
                "tick": ev.get("tick"),
                "type": t,
                "mechanism": ev.get("mechanism") or ev.get("mechanism_id"),
                "old": ev.get("old_value") or ev.get("old"),
                "new": ev.get("new_value") or ev.get("new"),
            })
    return {
        "section": "RUNTIME MECHANISM INTEGRITY",
        "runtime_mechanism_manifest": "AVAILABLE",
        "preflight_status": manifest.get("preflight_status"),
        "configuration_fingerprint": manifest.get("resolved_fingerprint"),
        "checksum": manifest.get("checksum"),
        "start_state": manifest.get("mechanisms"),
        "params": manifest.get("params"),
        "live_mechanism_interventions": live,
        "mismatches_at_start": [
            m for m in (manifest.get("mechanisms") or []) if m.get("status") != "READY"
        ],
    }
