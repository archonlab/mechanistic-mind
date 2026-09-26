"""Canonical Beta 3.1 experiment configuration — one complete authority.

Tabs edit this structure. Apply resolves one snapshot, then constructs runtime.
Omitted payload fields mean preserve, not default.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from mechanistic_mind.physical_system.mechanism_configuration import (
    CLIMATE_MECHANISM_ID,
    NEW_EXPERIMENT_VISION_RADIUS,
    WORLD_SUBSYSTEM_IDS,
    _coerce_bool,
    _registry_ids,
    fresh_experiment_default_map,
)
from mechanistic_mind.physical_system.mechanism_registry import MECHANISM_DEFS
from mechanistic_mind.physical_system.near_field_exteroception import (
    clamp_optical_mapping,
    clamp_spatial_vision,
    clamp_surface_discrimination,
    clamp_vision_radius,
)

PRESET_BETA31 = "TIKTAALIK_BETA31"
PRESET_BETA3 = "BETA3_RECOMMENDED"

BETA3_ALIASES = {
    "BETA3_RECOMMENDED",
    "BETA3",
    "MM_1_0_TIKTAALIK_PUBLIC_BETA_3",
    "MM 1.0 — TIKTAALIK PUBLIC BETA 3",
}
BETA31_ALIASES = {
    PRESET_BETA31,
    "BETA31",
    "BETA_3_1",
    "MM 1.0 — TIKTAALIK BETA 3.1",
    "TIKTAALIK BETA 3.1",
}

# 4.26–4.28: promoted as Beta 3.1 experimental organism layer (tiktaalik.py
# EXPERIMENTAL_COGNITION_KEYS + Observer model_metadata experimental_overrides).
BETA31_EXPERIMENTAL_ON: dict[str, bool] = {
    "contextual_predictive_organization": True,
    "context_grounded_prospection": True,
    "persistent_prospective_control": True,
}

VISION_DEFAULT = {
    "enabled": True,
    "radius": NEW_EXPERIMENT_VISION_RADIUS,
    "visual_surface_discrimination": "OFF",
    "optical_mapping": "INDEPENDENT",
    "spatial_vision": "LEGACY",
    "fov_deg": 120.0,
}


def registered_mechanism_ids() -> list[str]:
    ids = list(_registry_ids())
    for mid in WORLD_SUBSYSTEM_IDS:
        if mid not in ids:
            ids.append(mid)
    return ids


def normalize_preset_name(raw: Any) -> str | None:
    s = str(raw or "").strip().upper().replace("—", "-")
    if not s:
        return None
    compact = " ".join(s.replace("_", " ").split())
    if s in BETA31_ALIASES or compact in {a.upper() for a in BETA31_ALIASES}:
        return PRESET_BETA31
    if s in BETA3_ALIASES or "PUBLIC BETA 3" in compact and "3.1" not in compact:
        return PRESET_BETA3
    if "BETA 3.1" in compact or "BETA31" in s.replace(" ", ""):
        return PRESET_BETA31
    return None


def beta3_mechanism_map() -> dict[str, bool]:
    """Public Beta 3: fresh normal defaults (experimental cognition OFF)."""
    return dict(fresh_experiment_default_map())


def beta31_mechanism_map() -> dict[str, bool]:
    m = dict(fresh_experiment_default_map())
    m.update(BETA31_EXPERIMENTAL_ON)
    return m


def _world_default() -> dict[str, Any]:
    return {"width": 32, "height": 32, "boundary_mode": "WRAP_PERIODIC"}


def _body_default() -> dict[str, Any]:
    return {"mass": 1.0, "v_max": 0.4}


def preset_canonical(name: str | None, *, seed: int = 17) -> dict[str, Any]:
    n = normalize_preset_name(name) or PRESET_BETA31
    if n == PRESET_BETA3:
        return {
            "public_preset": PRESET_BETA3,
            "seed": int(seed),
            "agent_count": 2,
            "cognition_enabled": True,
            "ecology_preset": "BASELINE_CLIMATE_DEFAULT",
            "world": _world_default(),
            "agent_body": _body_default(),
            "mechanisms": beta3_mechanism_map(),
            "vision": dict(VISION_DEFAULT),
            "psc_motor_resolution": "OBSERVED_COMPOSITE",
            "pe_cold_history_eviction": True,
        }
    return {
        "public_preset": PRESET_BETA31,
        "seed": int(seed),
        "agent_count": 2,
        "cognition_enabled": True,
        "ecology_preset": "BASELINE_CLIMATE_DEFAULT",
        "world": _world_default(),
        "agent_body": _body_default(),
        "mechanisms": beta31_mechanism_map(),
        "vision": dict(VISION_DEFAULT),
        "psc_motor_resolution": "LOCO_FACTORIZED",
        "pe_cold_history_eviction": True,
    }


def vision_from_nfe(nfe: Any) -> dict[str, Any]:
    if nfe is None:
        return dict(VISION_DEFAULT)
    return {
        "enabled": bool(getattr(nfe, "enabled", False) or str(getattr(nfe, "mode", "")).upper() == "EXPERIMENTAL"),
        "radius": clamp_vision_radius(getattr(nfe, "radius", NEW_EXPERIMENT_VISION_RADIUS)),
        "visual_surface_discrimination": clamp_surface_discrimination(
            getattr(nfe, "visual_surface_discrimination", "OFF")
        ),
        "optical_mapping": clamp_optical_mapping(getattr(nfe, "optical_mapping", "INDEPENDENT")),
        "spatial_vision": clamp_spatial_vision(getattr(nfe, "spatial_vision", "LEGACY")),
        "fov_deg": float(getattr(nfe, "fov_deg", 120.0) or 120.0),
    }


def stamp_vision_on_config(config: Any, vision: dict[str, Any] | None) -> None:
    """Write experiment vision onto PhysicalSystemConfig before construction."""
    if not vision or config is None:
        return
    from mechanistic_mind.physical_system.near_field_exteroception import (
        NearFieldExteroceptionConfig,
    )

    nfe = getattr(config, "near_field_exteroception", None)
    if nfe is None:
        config.near_field_exteroception = NearFieldExteroceptionConfig()
        nfe = config.near_field_exteroception
    if vision.get("radius") is not None:
        nfe.radius = clamp_vision_radius(vision.get("radius"))
    if vision.get("visual_surface_discrimination") is not None:
        nfe.visual_surface_discrimination = clamp_surface_discrimination(
            vision.get("visual_surface_discrimination")
        )
    if vision.get("optical_mapping") is not None:
        nfe.optical_mapping = clamp_optical_mapping(vision.get("optical_mapping"))
    if vision.get("spatial_vision") is not None:
        nfe.spatial_vision = clamp_spatial_vision(vision.get("spatial_vision"))
    if vision.get("fov_deg") is not None:
        nfe.fov_deg = float(vision.get("fov_deg") or 120.0)
    if vision.get("enabled") is not None:
        on = bool(vision["enabled"])
        nfe.mode = "EXPERIMENTAL" if on else "OFF"
        nfe.perception_enabled = on


def canonical_from_runtime(runtime: Any) -> dict[str, Any]:
    cfg = getattr(runtime, "config", None)
    slots = getattr(runtime, "slots", None)
    slot0 = slots[0] if slots else runtime
    cfg = getattr(slot0, "config", cfg)
    nfe = getattr(cfg, "near_field_exteroception", None) if cfg is not None else None
    planet = getattr(cfg, "planet", None) if cfg is not None else None
    body = getattr(cfg, "body", None) if cfg is not None else None
    cog = getattr(cfg, "cognition", None)
    snap = {}
    try:
        snap = runtime.mechanisms() or {}
    except Exception:
        snap = {}
    enabled = dict(snap.get("enabled") or {})
    mechs = dict(fresh_experiment_default_map())
    mechs.update({k: bool(v) for k, v in enabled.items()})
    return {
        "public_preset": None,
        "seed": int(getattr(runtime, "seed", 17) or 17),
        "agent_count": int(len(slots) if slots else 1),
        "cognition_enabled": bool(getattr(cog, "cognition_enabled", True)) if cog is not None else True,
        "ecology_preset": str(getattr(cfg, "ecology_preset", None) or "BASELINE_CLIMATE_DEFAULT"),
        "world": {
            "width": int(getattr(planet, "width", 32) or 32),
            "height": int(getattr(planet, "height", 32) or 32),
            "boundary_mode": "WRAP_PERIODIC",
        },
        "agent_body": {
            "mass": float(getattr(body, "mass", 1.0) or 1.0),
            "v_max": float(getattr(body, "v_max", 0.4) or 0.4),
        },
        "mechanisms": mechs,
        "vision": vision_from_nfe(nfe),
        "psc_motor_resolution": str(getattr(cog, "psc_motor_resolution", None) or "LOCO_FACTORIZED"),
        "pe_cold_history_eviction": None,
    }


def merge_canonical(base: dict[str, Any], patch: dict[str, Any] | None) -> dict[str, Any]:
    """PATCH: omitted keys keep base. Nested mechanisms/vision/world/body merge."""
    out = deepcopy(base or {})
    if not patch:
        return out
    out.setdefault("mechanisms", {})
    out.setdefault("vision", dict(VISION_DEFAULT))
    out.setdefault("world", _world_default())
    out.setdefault("agent_body", _body_default())

    skip = {"load_preset", "replace_with_preset", "replace"}
    for k, v in patch.items():
        if k in skip or v is None:
            continue
        if k in {"mechanisms", "cognition"} and isinstance(v, dict):
            for mk, mv in v.items():
                if mk in {"vision_radius"}:
                    out["vision"]["radius"] = clamp_vision_radius(mv)
                    continue
                bv = _coerce_bool(mv)
                if bv is None and mk not in {"prospective_selection", "psc_motor_resolution"}:
                    continue
                if mk == "psc_motor_resolution":
                    out["psc_motor_resolution"] = str(mv)
                    continue
                if mk == "prospective_selection":
                    out["mechanisms"]["prospective_scenario_competition"] = (
                        str(mv).upper() == "SCENARIO_COMPETITION"
                    )
                    continue
                if bv is not None:
                    out["mechanisms"][str(mk)] = bv
            continue
        if k == "vision" and isinstance(v, dict):
            vis = dict(out.get("vision") or {})
            if v.get("radius") is not None or v.get("vision_radius") is not None:
                vis["radius"] = clamp_vision_radius(v.get("radius", v.get("vision_radius")))
            if v.get("visual_surface_discrimination") is not None or v.get("surface_discrimination") is not None:
                vis["visual_surface_discrimination"] = clamp_surface_discrimination(
                    v.get("visual_surface_discrimination", v.get("surface_discrimination"))
                )
            if v.get("optical_mapping") is not None:
                vis["optical_mapping"] = clamp_optical_mapping(v["optical_mapping"])
            if v.get("spatial_vision") is not None:
                vis["spatial_vision"] = clamp_spatial_vision(v["spatial_vision"])
            if v.get("enabled") is not None:
                vis["enabled"] = bool(v["enabled"])
            if v.get("fov_deg") is not None:
                vis["fov_deg"] = float(v["fov_deg"])
            out["vision"] = vis
            continue
        if k == "world" and isinstance(v, dict):
            w = dict(out.get("world") or {})
            w.update({kk: vv for kk, vv in v.items() if vv is not None})
            out["world"] = w
            continue
        if k in {"agent_body", "body"} and isinstance(v, dict):
            b = dict(out.get("agent_body") or {})
            b.update({kk: vv for kk, vv in v.items() if vv is not None})
            out["agent_body"] = b
            continue
        if k == "vision_radius":
            out.setdefault("vision", dict(VISION_DEFAULT))
            out["vision"]["radius"] = clamp_vision_radius(v)
            continue
        if k == "cognition_enabled":
            out["cognition_enabled"] = bool(v)
            out.setdefault("mechanisms", {})["cognition"] = bool(v)
            continue
        if k == "public_preset":
            out["public_preset"] = v
            continue
        out[k] = v
    return out


def canonical_fingerprint(canonical: dict[str, Any]) -> str:
    mechs = canonical.get("mechanisms") or {}
    vis = canonical.get("vision") or {}
    world = canonical.get("world") or {}
    body = canonical.get("agent_body") or {}
    authority = beta31_mechanism_map()
    mech_keys = sorted(set(authority) | {k for k in mechs if k in authority or k in beta3_mechanism_map()})
    payload = {
        "agent_count": int(canonical.get("agent_count") or 1),
        "cognition_enabled": bool(canonical.get("cognition_enabled", True)),
        "ecology_preset": str(canonical.get("ecology_preset") or ""),
        "mechanisms": {k: bool(mechs.get(k, authority.get(k, False))) for k in mech_keys},
        "pe_cold_history_eviction": bool(canonical.get("pe_cold_history_eviction") or False),
        "psc_motor_resolution": str(canonical.get("psc_motor_resolution") or "LOCO_FACTORIZED"),
        "seed": int(canonical.get("seed") or 0),
        "vision": {
            "enabled": bool(vis.get("enabled", True)),
            "fov_deg": float(vis.get("fov_deg") or 120.0),
            "optical_mapping": str(vis.get("optical_mapping") or "INDEPENDENT"),
            "radius": int(vis.get("radius") or NEW_EXPERIMENT_VISION_RADIUS),
            "spatial_vision": str(vis.get("spatial_vision") or "LEGACY"),
            "visual_surface_discrimination": str(vis.get("visual_surface_discrimination") or "OFF"),
        },
        "world": {
            "boundary_mode": str(world.get("boundary_mode") or "WRAP_PERIODIC"),
            "height": int(world.get("height") or 0),
            "width": int(world.get("width") or 0),
            "terrain_seed": world.get("terrain_seed"),
        },
        "agent_body": {
            "mass": float(body.get("mass") or 0.0),
            "v_max": float(body.get("v_max") or 0.0),
        },
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def runtime_readback(runtime: Any, *, pe_cold: bool | None = None) -> dict[str, Any]:
    can = canonical_from_runtime(runtime)
    if pe_cold is not None:
        can["pe_cold_history_eviction"] = bool(pe_cold)
    can["fingerprint"] = canonical_fingerprint(can)
    return can


def compare_requested_runtime(requested: dict[str, Any], runtime: dict[str, Any]) -> dict[str, Any]:
    req_m = requested.get("mechanisms") or {}
    rt_m = runtime.get("mechanisms") or {}
    mismatches: list[dict[str, Any]] = []
    # Compare requested experiment keys only. Runtime-only structural always-on
    # mechanisms are not independent experiment authorities.
    for k in sorted(req_m):
        if bool(req_m.get(k)) != bool(rt_m.get(k)):
            mismatches.append({
                "field": f"mechanisms.{k}",
                "requested": req_m.get(k),
                "runtime": rt_m.get(k),
            })
    rv, vv = requested.get("vision") or {}, runtime.get("vision") or {}
    for vk in ("radius", "visual_surface_discrimination", "optical_mapping", "spatial_vision"):
        if vk in rv or vk in vv:
            if str(rv.get(vk)) != str(vv.get(vk)):
                mismatches.append({"field": f"vision.{vk}", "requested": rv.get(vk), "runtime": vv.get(vk)})
    for k in ("cognition_enabled", "agent_count", "psc_motor_resolution"):
        if requested.get(k) is not None and str(requested.get(k)) != str(runtime.get(k)):
            mismatches.append({"field": k, "requested": requested.get(k), "runtime": runtime.get(k)})
    return {
        "match": not mismatches,
        "mismatches": mismatches,
        "requested_fingerprint": canonical_fingerprint(requested),
        "runtime_fingerprint": canonical_fingerprint(runtime),
    }


def mechanism_intent_table() -> list[dict[str, Any]]:
    """Document Beta 3.1 intended state vs source."""
    b3 = beta3_mechanism_map()
    b31 = beta31_mechanism_map()
    rows = []
    labels = {str(d["id"]): str(d.get("label") or d["id"]) for d in MECHANISM_DEFS}
    for mid in sorted(set(b3) | set(b31)):
        src = "fresh_experiment_default_map"
        if mid in BETA31_EXPERIMENTAL_ON:
            src = "tiktaalik EXPERIMENTAL_COGNITION_KEYS / 4.26–4.28 + model_metadata"
        if mid == CLIMATE_MECHANISM_ID:
            src = "mechanism_configuration climate default OFF"
        if mid == "prospective_scenario_competition":
            src = "experience-first PSC default OFF"
        rows.append({
            "mechanism": mid,
            "label": labels.get(mid, mid),
            "beta3": bool(b3.get(mid)),
            "beta31": bool(b31.get(mid)),
            "source": src,
        })
    return rows
