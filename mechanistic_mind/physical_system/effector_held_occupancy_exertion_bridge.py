"""Acanthostega VW5 · Effector/held occupancy exertion bridge.

Mechanism: effector_held_occupancy_exertion_bridge
Schema: VW5_EFFECTOR_HELD_OCCUPANCY_EXERTION_BRIDGE_V1
Authority: AUTHORITATIVE_EFFECTOR_HELD_OCCUPANCY_EXERTION_BRIDGE

Bridges existing effector contact + bounded effort + surface resistance into
VW1 occupancy geometry and VW3 WMT separation. Does not invent DIG/BUILD/PLACE.
Does not manually edit occupancy. Does not implement VW4 reintegration trigger
(no scientifically distinct physical event beyond overlay APPLY_TO_SURFACE /
mere contact / RELEASE — see REINTEGRATION_BLOCKER).

Deterministic contact selection rule (floor-primary):
  For probe elevation z_eff = effector_z - radius:
    1. If z_eff lies inside an occupied interval → contact that interval
       (boundary = interval.z_max for downward nonpenetration; penetration > 0).
    2. Else choose the occupied interval with greatest z_max among those with
       z_max <= z_eff + eps (floor-below). Tie-break: lowest z_min, then
       denser material first (density desc), then composition id lexicographic.
    3. Legacy compatibility max surface is never used as contact authority.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

SCHEMA = "VW5_EFFECTOR_HELD_OCCUPANCY_EXERTION_BRIDGE_V1"
CAPABILITY = "organism_physical_interaction_with_volumetric_world"
PROFILE = "EFFECTOR_HELD_OCCUPANCY_EXERTION_BRIDGE_V1"
AUTHORITY = "AUTHORITATIVE_EFFECTOR_HELD_OCCUPANCY_EXERTION_BRIDGE"
MECHANISM_ID = "effector_held_occupancy_exertion_bridge"
WORLD_ATTR = "effector_held_occupancy_exertion_bridge_state"
HISTORY_LIMIT = 32
CONTACT_EPS_DEFAULT = 1e-9

REINTEGRATION_BLOCKER = (
    "NO_PHYSICAL_DEPOSITION_INTO_OCCUPANCY_EVENT: "
    "APPLY_TO_SURFACE writes surface-deposit overlay (not VW4); "
    "mere held-object/terrain contact and RELEASE do not scientifically "
    "distinguish ordinary rest from world-material incorporation"
)

AUTHORITY_FLAGS = {
    "schema": SCHEMA,
    "capability": CAPABILITY,
    "profile": PROFILE,
    "authority": AUTHORITY,
    "occupancy_owner": "volumetric_world_material_occupancy",
    "separation_authority": "volumetric_world_material_separation",
    "reintegration_authority": "volumetric_world_material_reintegration",
    "wmt_authority": "world_material_transactions",
    "work_authority": "surface_exertion_terrain_material_resistance",
    "semantic_dig": False,
    "semantic_build": False,
    "semantic_place": False,
    "agent_accessible": False,
    "researcher_only": True,
    "vw4_physical_trigger": False,
    "reintegration_blocker": REINTEGRATION_BLOCKER,
}


class EffectorHeldOccupancyExertionBridgeValidationError(ValueError):
    """Raised when VW5 config is invalid."""


@dataclass
class EffectorHeldOccupancyExertionBridgeConfig:
    enabled: bool = False
    profile: str = PROFILE
    schema: str = SCHEMA
    contact_epsilon: float = CONTACT_EPS_DEFAULT

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "profile": str(self.profile),
            "schema": str(self.schema),
            "contact_epsilon": float(self.contact_epsilon),
            **AUTHORITY_FLAGS,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "EffectorHeldOccupancyExertionBridgeConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        profile = str(data.get("profile") or PROFILE)
        schema = str(data.get("schema") or SCHEMA)
        if profile != PROFILE:
            raise EffectorHeldOccupancyExertionBridgeValidationError(
                f"unsupported VW5 profile: {profile!r}"
            )
        if schema != SCHEMA:
            raise EffectorHeldOccupancyExertionBridgeValidationError(
                f"unsupported VW5 schema: {schema!r}"
            )
        return cls(
            enabled=bool(data.get("enabled", False)),
            profile=profile,
            schema=schema,
            contact_epsilon=float(data.get("contact_epsilon", CONTACT_EPS_DEFAULT)),
        )


def effector_held_occupancy_exertion_bridge_is_active(config: Any) -> bool:
    if config is None or str(getattr(config, "model_line", "") or "").upper() != "ACANTHOSTEGA":
        return False
    cfg = getattr(config, "effector_held_occupancy_exertion_bridge", None)
    if cfg is None or not bool(getattr(cfg, "enabled", False)):
        return False
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        volumetric_world_material_occupancy_is_active,
    )

    return bool(volumetric_world_material_occupancy_is_active(config))


def set_effector_held_occupancy_exertion_bridge(config: Any, enabled: bool) -> None:
    if config is None:
        return
    on = bool(enabled) and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"
    cur = getattr(config, "effector_held_occupancy_exertion_bridge", None)
    if cur is None:
        config.effector_held_occupancy_exertion_bridge = EffectorHeldOccupancyExertionBridgeConfig(
            enabled=on
        )
    else:
        cur.enabled = on
    if on:
        from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
            set_volumetric_world_material_occupancy,
        )
        from mechanistic_mind.physical_system.occupancy_support_and_contact_queries import (
            set_occupancy_support_and_contact_queries,
        )
        from mechanistic_mind.physical_system.volumetric_world_material_separation import (
            set_volumetric_world_material_separation,
        )
        from mechanistic_mind.physical_system.world_material_transaction import (
            set_world_material_transactions,
        )
        from mechanistic_mind.physical_system.effector_terrain_contact_geometry import (
            set_effector_terrain_contact_geometry,
        )
        from mechanistic_mind.physical_system.surface_exertion_terrain_material_resistance import (
            set_surface_exertion_terrain_material_resistance,
        )

        set_volumetric_world_material_occupancy(config, True)
        set_occupancy_support_and_contact_queries(config, True)
        set_world_material_transactions(config, True)
        set_volumetric_world_material_separation(config, True)
        set_effector_terrain_contact_geometry(config, True)
        set_surface_exertion_terrain_material_resistance(config, True)


@dataclass
class EffectorHeldOccupancyExertionBridgeState:
    config: EffectorHeldOccupancyExertionBridgeConfig
    last_probe: dict[str, Any] = field(default_factory=dict)
    last_exertion_bridge: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=dict)


def state_of(world: Any) -> EffectorHeldOccupancyExertionBridgeState | None:
    raw = getattr(world, WORLD_ATTR, None)
    return raw if isinstance(raw, EffectorHeldOccupancyExertionBridgeState) else None


def ensure_state(world: Any, config: Any) -> EffectorHeldOccupancyExertionBridgeState | None:
    if not effector_held_occupancy_exertion_bridge_is_active(config):
        if getattr(world, WORLD_ATTR, None) is not None:
            setattr(world, WORLD_ATTR, None)
        return None
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        ensure_state as ensure_vw1,
    )

    ensure_vw1(world, config)
    st = state_of(world)
    if st is not None:
        return st
    raw = getattr(config, "effector_held_occupancy_exertion_bridge", None)
    cfg = (
        raw
        if isinstance(raw, EffectorHeldOccupancyExertionBridgeConfig)
        else EffectorHeldOccupancyExertionBridgeConfig.from_dict(
            raw if isinstance(raw, dict) else None
        )
    )
    cfg.enabled = True
    st = EffectorHeldOccupancyExertionBridgeState(config=cfg)
    setattr(world, WORLD_ATTR, st)
    return st


def _eps(config: Any) -> float:
    cfg = getattr(config, "effector_held_occupancy_exertion_bridge", None)
    try:
        return float(getattr(cfg, "contact_epsilon", CONTACT_EPS_DEFAULT) or CONTACT_EPS_DEFAULT)
    except (TypeError, ValueError):
        return CONTACT_EPS_DEFAULT


def _interval_sort_key(it: Any) -> tuple:
    """Deterministic tie-break among equal floor candidates (unused when unique max)."""
    comp0 = ""
    if it.composition:
        comp0 = str(it.composition[0][0])
    return (-float(it.z_max), float(it.z_min), -float(it.density), comp0)


def select_floor_contact_interval(
    intervals: tuple[Any, ...] | list[Any],
    query_z: float,
    *,
    eps: float = CONTACT_EPS_DEFAULT,
) -> tuple[Any | None, str]:
    """Select contacted/floor interval for probe elevation query_z.

    Rule documented in module docstring. Returns (interval|None, relation).
    """
    zz = float(query_z)
    eps = float(eps)
    containing = [it for it in intervals if it.contains(zz)]
    if containing:
        # Deterministic: prefer highest z_max among containing (deepest top).
        containing.sort(key=_interval_sort_key)
        return containing[0], "INSIDE_OCCUPIED"

    candidates = [it for it in intervals if float(it.z_max) <= zz + eps]
    if not candidates:
        return None, "NO_SUPPORT_BELOW"
    candidates.sort(key=_interval_sort_key)
    best = candidates[0]
    clearance = zz - float(best.z_max)
    if abs(clearance) <= eps:
        return best, "AT_SUPPORT"
    if clearance > eps:
        return best, "ABOVE_SUPPORT"
    return best, "BELOW_SUPPORT"


def select_ceiling_interval(
    intervals: tuple[Any, ...] | list[Any],
    query_z: float,
    *,
    eps: float = CONTACT_EPS_DEFAULT,
) -> Any | None:
    zz = float(query_z)
    eps = float(eps)
    best = None
    best_lo = math.inf
    for it in intervals:
        lo = float(it.z_min)
        if lo + eps >= zz and lo < best_lo:
            best = it
            best_lo = lo
    return best


def occupancy_probe_geometry_at(
    world: Any,
    x: float,
    y: float,
    z: float,
    *,
    radius: float = 0.0,
    config: Any = None,
) -> dict[str, Any]:
    """Occupancy-aware probe geometry. Clearance = absence of overlapping matter.

    Floor-primary clearance for downward nonpenetration:
      clearance = (z - radius) - floor_boundary_z
    Legacy compatibility max surface recorded but never used as authority.
    """
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        compatibility_surface_elevation,
        occupied_intervals_at,
        wrap_cell,
        state_of as vo_state,
    )

    eps = _eps(config)
    z_eff = float(z) - float(radius)
    intervals = occupied_intervals_at(world, x, y)
    legacy = compatibility_surface_elevation(world, x, y)
    st_vo = vo_state(world)
    if st_vo is not None:
        cell = wrap_cell(st_vo, int(math.floor(float(x))), int(math.floor(float(y))))
        cx, cy = int(cell[0]), int(cell[1])
    else:
        cx = int(math.floor(float(x)))
        cy = int(math.floor(float(y)))

    it, relation = select_floor_contact_interval(intervals, z_eff, eps=eps)
    ceiling = select_ceiling_interval(intervals, z_eff, eps=eps)

    if it is None:
        clearance = None if legacy is None else float("inf")
        # No floor: free relative to occupancy; report large positive clearance.
        clearance = float("inf")
        penetration = 0.0
        boundary = None
        in_contact = False
        normal = (0.0, 0.0, 1.0)
    else:
        boundary = float(it.z_max)
        if relation == "INSIDE_OCCUPIED":
            # Penetrating occupied matter from above-model: tip below material top.
            clearance = z_eff - boundary
            penetration = max(0.0, boundary - z_eff)
            in_contact = True
            normal = (0.0, 0.0, 1.0)
        else:
            clearance = z_eff - boundary
            penetration = max(0.0, -clearance)
            in_contact = clearance <= eps
            normal = (0.0, 0.0, 1.0)

    ceiling_z = None if ceiling is None else float(ceiling.z_min)
    ceiling_clearance = None if ceiling_z is None else float(ceiling_z) - z_eff

    overlaps_occupied = any(it2.contains(z_eff) for it2 in intervals)
    # Overlap with material at probe = contact regardless of floor model.
    if overlaps_occupied and it is not None:
        in_contact = True

    out = {
        "authority": AUTHORITY,
        "geometry_source": "volumetric_occupancy",
        "legacy_source_label": "LEGACY / DERIVED SURFACE PROJECTION (not contact authority)",
        "x": float(x),
        "y": float(y),
        "z": float(z),
        "z_eff": float(z_eff),
        "radius": float(radius),
        "cell_x": cx,
        "cell_y": cy,
        "clearance": None if clearance is None or not math.isfinite(clearance) else float(clearance),
        "clearance_infinite": clearance is not None and not math.isfinite(float(clearance)),
        "penetration": float(penetration),
        "in_contact": bool(in_contact),
        "boundary_z": boundary,
        "relation": relation,
        "normal": list(normal),
        "source_interval": None if it is None else it.as_dict(),
        "ceiling_z_min": ceiling_z,
        "ceiling_clearance": None if ceiling_clearance is None else float(ceiling_clearance),
        "ceiling_interval": None if ceiling is None else ceiling.as_dict(),
        "legacy_projected_surface": None if legacy is None else float(legacy),
        "contradicts_legacy_projected_surface": bool(
            legacy is not None
            and boundary is not None
            and abs(float(legacy) - float(boundary)) > eps
        ),
        "false_heightfield_contact_prevented": bool(
            legacy is not None
            and not in_contact
            and (float(z) - float(legacy)) <= eps
        ),
        "researcher_only": True,
        "selection_rule": "FLOOR_BELOW_GREATEST_ZMAX_THEN_DETERMINISTIC_TIEBREAK",
    }
    st = state_of(world)
    if st is not None:
        st.last_probe = dict(out)
        st.counters["probes"] = int(st.counters.get("probes", 0)) + 1
    return out


def occupancy_sample_as_terrain(
    world: Any,
    x: float,
    y: float,
    z: float,
    *,
    radius: float = 0.0,
    config: Any = None,
) -> dict[str, Any]:
    """Adapter: occupancy floor boundary presented like sample_terrain_at fields."""
    geom = occupancy_probe_geometry_at(world, x, y, z, radius=radius, config=config)
    boundary = geom.get("boundary_z")
    # If no floor, use -inf so clearance stays positive / free.
    height = float(boundary) if boundary is not None else float("-inf")
    nx, ny, nz = geom["normal"]
    return {
        "height": height,
        "normal_x": float(nx),
        "normal_y": float(ny),
        "normal_z": float(nz),
        "cell_x": int(geom["cell_x"]),
        "cell_y": int(geom["cell_y"]),
        "u": 0.0,
        "v": 0.0,
        "cells": {
            "00": [geom["cell_x"], geom["cell_y"]],
            "10": [geom["cell_x"], geom["cell_y"]],
            "01": [geom["cell_x"], geom["cell_y"]],
            "11": [geom["cell_x"], geom["cell_y"]],
        },
        "source": "volumetric_occupancy_floor_below",
        "occupancy_probe": geom,
        "legacy_projected_surface": geom.get("legacy_projected_surface"),
    }


def contacted_occupancy_material_info(
    world: Any,
    contact_point: list[float] | tuple[float, ...] | None,
    *,
    config: Any = None,
) -> dict[str, Any] | None:
    """Resolve resistance material from the contacted occupancy interval."""
    if not contact_point or len(contact_point) < 2:
        return None
    from mechanistic_mind.physical_system.passive_material_properties import (
        derive_separation_work_per_quantity,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        occupied_intervals_at,
    )

    x = float(contact_point[0])
    y = float(contact_point[1])
    cz = float(contact_point[2]) if len(contact_point) >= 3 else float("nan")
    intervals = occupied_intervals_at(world, x, y)
    if not intervals:
        return None
    eps = _eps(config)
    it = None
    if math.isfinite(cz):
        # Prefer interval whose top matches contact z (floor contact).
        for cand in intervals:
            if abs(float(cand.z_max) - cz) <= eps:
                it = cand
                break
        if it is None:
            for cand in intervals:
                if cand.contains(cz):
                    it = cand
                    break
        if it is None:
            it, _ = select_floor_contact_interval(intervals, cz, eps=eps)
    else:
        # Fallback: topmost interval (last resort; should be rare with VW5 contact_point z).
        it = max(intervals, key=lambda t: float(t.z_max))
    if it is None:
        return None

    thickness = float(it.z_max) - float(it.z_min)
    comp_rows = [
        {"component_id": str(cid), "amount": float(amt)} for cid, amt in (it.composition or ())
    ]
    sep = derive_separation_work_per_quantity(comp_rows)
    return {
        "thickness": float(thickness),
        "composition": comp_rows,
        "separation_work_per_quantity": float(sep["separation_work_per_quantity"]),
        "cell_x": int(math.floor(x)),
        "cell_y": int(math.floor(y)),
        "surface_elevation": float(it.z_max),
        "boundary_z": float(it.z_max),
        "z_min": float(it.z_min),
        "z_max": float(it.z_max),
        "density": float(it.density),
        "interval": it.as_dict(),
        "sep_report": sep,
        "material_authority": "volumetric_occupancy_contacted_interval",
        "accumulator_key_suffix": f"{float(it.z_min):.9g}:{float(it.z_max):.9g}",
    }


def apply_physical_volumetric_separation_from_failure(
    world: Any,
    config: Any,
    *,
    material_info: dict[str, Any],
    requested_thickness: float,
    tick: int,
    researcher_id: str,
) -> dict[str, Any]:
    """Route material failure into VW3. VW5 does not subtract occupancy itself."""
    from mechanistic_mind.physical_system.volumetric_world_material_separation import (
        apply_volumetric_material_separation,
    )

    z_hi = float(material_info["z_max"])
    z_lo_iv = float(material_info["z_min"])
    q = float(requested_thickness)
    z_lo = max(z_lo_iv, z_hi - q)
    if z_hi <= z_lo + 1e-15:
        return {
            "legacy": None,
            "receipt": {
                "status": "REJECTED",
                "rejection_reason": "ZERO_REMOVAL",
                "schema": "VW3_VOLUMETRIC_MATERIAL_SEPARATION_V1",
            },
        }
    cx = int(material_info["cell_x"])
    cy = int(material_info["cell_y"])
    out = apply_volumetric_material_separation(
        world,
        config,
        cell_x=cx,
        cell_y=cy,
        z_remove_lo=z_lo,
        z_remove_hi=z_hi,
        tick=int(tick),
        researcher_id=str(researcher_id),
    )
    # Annotate bridge provenance on receipt (researcher-only).
    rec = (out or {}).get("receipt")
    if isinstance(rec, dict):
        rec = dict(rec)
        rec["vw5_bridge"] = True
        rec["physical_failure_routed_via"] = MECHANISM_ID
        rec["applied_separation_thickness"] = float(z_hi - z_lo)
        rec["separated_thickness"] = float(z_hi - z_lo)
        out = {**(out or {}), "receipt": rec}
        st = state_of(world)
        if st is not None:
            st.last_exertion_bridge = {
                "tick": int(tick),
                "vw3_receipt": rec,
                "material_info": {
                    "z_min": z_lo_iv,
                    "z_max": z_hi,
                    "composition": material_info.get("composition"),
                },
                "removal": {"z_lo": z_lo, "z_hi": z_hi},
            }
            st.history.append(dict(st.last_exertion_bridge))
            if len(st.history) > HISTORY_LIMIT:
                del st.history[: len(st.history) - HISTORY_LIMIT]
            st.counters["vw3_routed"] = int(st.counters.get("vw3_routed", 0)) + 1
    return out


def held_object_occupancy_contact(
    world: Any,
    config: Any,
    *,
    object_id: str,
) -> dict[str, Any] | None:
    """Geometry-only: relate held/free ResourceObject pose to occupancy.

    Does NOT trigger VW4 reintegration.
    """
    objs = list(getattr(world, "resource_objects", None) or [])
    obj = next((o for o in objs if str(getattr(o, "object_id", "")) == str(object_id)), None)
    if obj is None:
        return None
    x = float(getattr(obj, "x", 0.0) or 0.0)
    y = float(getattr(obj, "y", 0.0) or 0.0)
    z = float(getattr(obj, "z", 0.0) or 0.0)
    r = float(getattr(obj, "collision_radius", 0.0) or 0.0)
    geom = occupancy_probe_geometry_at(world, x, y, z, radius=r, config=config)
    return {
        "object_id": str(object_id),
        "physical_state": str(getattr(obj, "physical_state", "") or ""),
        "pose": {"x": x, "y": y, "z": z, "collision_radius": r},
        "occupancy_contact": geom,
        "reintegration_eligible": False,
        "reintegration_blocker": REINTEGRATION_BLOCKER,
        "vw4_trigger": False,
        "researcher_only": True,
    }


def researcher_payload(world: Any) -> dict[str, Any]:
    st = state_of(world)
    if st is None:
        return {}
    return {
        "effector_held_occupancy_exertion_bridge": {
            "schema": SCHEMA,
            "capability": CAPABILITY,
            "authority": AUTHORITY,
            "mechanism_id": MECHANISM_ID,
            "last_probe": dict(st.last_probe) if st.last_probe else None,
            "last_exertion_bridge": dict(st.last_exertion_bridge) if st.last_exertion_bridge else None,
            "receipts": list(st.history)[-HISTORY_LIMIT:],
            "counters": dict(st.counters),
            "reintegration_blocker": REINTEGRATION_BLOCKER,
            **AUTHORITY_FLAGS,
        }
    }


def observer_bridge_inspector_payload(world: Any, config: Any | None = None) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    return {
        "mechanism": MECHANISM_ID,
        "schema": SCHEMA,
        "authority_label": "AUTHORITATIVE VW5 EFFECTOR/HELD OCCUPANCY EXERTION BRIDGE",
        "legacy_label": "LEGACY / DERIVED SURFACE PROJECTION (not contact/exertion authority)",
        "last_probe": dict(st.last_probe) if st.last_probe else None,
        "last_exertion_bridge": dict(st.last_exertion_bridge) if st.last_exertion_bridge else None,
        "reintegration_blocker": REINTEGRATION_BLOCKER,
        "researcher_only_view": True,
        "not_agent_accessible": True,
        "source_kind": "VW5_BRIDGE_INSPECTION",
    }


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "config_path": "effector_held_occupancy_exertion_bridge.enabled",
        "enabled": bool(enabled),
        "scientific_status": "IMPLEMENTED",
        "promotion_class": "EXPERIMENTAL",
        "schema": SCHEMA,
        "profile": PROFILE,
        "description": (
            "Occupancy-aware effector clearance/contact + resistance from contacted "
            "interval; physical failure routes to VW3. No DIG/BUILD/PLACE. "
            "VW4 physical reintegration trigger blocked (no distinct deposition event)."
        ),
    }
