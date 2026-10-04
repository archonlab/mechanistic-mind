"""Acanthostega Beta 4 · Effector ↔ authoritative terrain contact geometry.

Mechanism: effector_terrain_contact_geometry
Preset: ACANTHOSTEGA_BETA4_EFFECTOR_TERRAIN_CONTACT_GEOMETRY

Geometry-only. No impulse, work, material failure, or SEPARATE_SURFACE_COLUMN_SLICE.

Effector world pose V1:
  xy = existing effector_world_xy (body pose + forward/lateral; WRAP)
  z  = body centre_z = body.z + vertical_half_extent   (BODY_CENTRE_Z authority)
  r  = effector_terrain_contact_radius (default 0 = point probe; NOT grasp radius)

Contact vs continuous surface height h(x,y) from CSG/SES oracle:
  clearance = z - r - h(x,y)
  in_contact iff clearance <= contact_epsilon

Swept: sample previous→current trajectory for clearance zero-crossing / TOI.
Lifecycle: BEGIN / PERSIST / END with researcher-only episode ids.
No cognition exposure. No action-label triggers.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from mechanistic_mind.planet.topology import wrap_coord

MECHANISM_ID = "effector_terrain_contact_geometry"
PROFILE_VERSION = "EFFECTOR_TERRAIN_CONTACT_GEOMETRY_PROFILE_V1"
STATE_SCHEMA = "EFFECTOR_TERRAIN_CONTACT_GEOMETRY_STATE_V1"
RECEIPT_KIND = "EFFECTOR_TERRAIN_CONTACT"
EVENT_STEP = "EFFECTOR_TERRAIN_CONTACT_STEP"

PHASE_BEGIN = "BEGIN"
PHASE_PERSIST = "PERSIST"
PHASE_END = "END"

DETECTION_ENDPOINT = "ENDPOINT_OVERLAP"
DETECTION_SWEPT = "SWEPT_CROSSING"

Z_AUTHORITY = "BODY_CENTRE_Z"
CONTACT_RADIUS_SOURCE = "POINT_PROBE_MECHANISM_LOCAL"
EFFECTOR_GEOMETRY = "POINT_PROBE_AT_BODY_CENTRE_Z"

# Default: point probe. Grasp/optical radii are reach/sensor — not collision.
DEFAULT_CONTACT_RADIUS = 0.0
DEFAULT_CONTACT_EPSILON = 1e-9
# Deterministic sweep: max arc length between samples (world cells).
DEFAULT_SWEEP_STEP = 0.05
DEFAULT_SWEEP_MAX_SAMPLES = 64
HISTORY_LIMIT_DEFAULT = 64

END_SEPARATION = "SEPARATION"
END_EFFECTOR_REMOVED = "EFFECTOR_REMOVED"
END_BODY_REMOVED = "BODY_REMOVED"
END_RESTORE_CLEAR = "RESTORE_OR_MISSING_HISTORY"

RESPONSE_FLAGS = {
    "contact_fact": True,
    "collision_response_applied": False,
    "impulse_transferred": False,
    "position_corrected": False,
    "velocity_changed": False,
    "work_accounted": False,
    "material_failure": False,
    "terrain_separated": False,
    "sound_emitted": False,
}

BANNER = (
    "BETA4 · EFFECTOR–TERRAIN CONTACT GEOMETRY V1 · BODY_CENTRE_Z · "
    "POINT PROBE · SWEPT · NO RESPONSE / NO EXERTION"
)


@dataclass
class EffectorTerrainContactGeometryConfig:
    """Fresh default OFF. Missing snapshot key → mechanism OFF."""

    enabled: bool = False
    effector_terrain_contact_radius: float = DEFAULT_CONTACT_RADIUS
    contact_epsilon: float = DEFAULT_CONTACT_EPSILON
    sweep_step: float = DEFAULT_SWEEP_STEP
    sweep_max_samples: int = DEFAULT_SWEEP_MAX_SAMPLES
    history_limit: int = HISTORY_LIMIT_DEFAULT

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "effector_terrain_contact_radius": float(self.effector_terrain_contact_radius),
            "contact_epsilon": float(self.contact_epsilon),
            "sweep_step": float(self.sweep_step),
            "sweep_max_samples": int(self.sweep_max_samples),
            "history_limit": int(self.history_limit),
            "profile_version": PROFILE_VERSION,
            "z_authority": Z_AUTHORITY,
            "contact_radius_source": CONTACT_RADIUS_SOURCE,
            "effector_geometry": EFFECTOR_GEOMETRY,
            "response": dict(RESPONSE_FLAGS),
            "swept_contact": True,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "EffectorTerrainContactGeometryConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        ver = data.get("profile_version")
        if ver is not None and str(ver) != PROFILE_VERSION:
            raise ValueError(f"unknown effector terrain contact profile: {ver}")
        return cls(
            enabled=bool(data.get("enabled", False)),
            effector_terrain_contact_radius=float(
                data.get("effector_terrain_contact_radius", DEFAULT_CONTACT_RADIUS)
            ),
            contact_epsilon=float(data.get("contact_epsilon", DEFAULT_CONTACT_EPSILON)),
            sweep_step=float(data.get("sweep_step", DEFAULT_SWEEP_STEP)),
            sweep_max_samples=int(data.get("sweep_max_samples", DEFAULT_SWEEP_MAX_SAMPLES)),
            history_limit=int(data.get("history_limit", HISTORY_LIMIT_DEFAULT)),
        )


def validate_config(cfg: EffectorTerrainContactGeometryConfig) -> None:
    if float(cfg.effector_terrain_contact_radius) < 0.0:
        raise ValueError("effector_terrain_contact_radius must be >= 0")
    if float(cfg.contact_epsilon) < 0.0:
        raise ValueError("contact_epsilon must be >= 0")
    if float(cfg.sweep_step) <= 0.0:
        raise ValueError("sweep_step must be > 0")
    if int(cfg.sweep_max_samples) < 2:
        raise ValueError("sweep_max_samples must be >= 2")


def effector_terrain_contact_geometry_is_active(config: Any) -> bool:
    cfg = getattr(config, "effector_terrain_contact_geometry", None)
    return bool(cfg is not None and getattr(cfg, "enabled", False))


def set_effector_terrain_contact_geometry(config: Any, enabled: bool) -> None:
    on = bool(enabled)
    cur = getattr(config, "effector_terrain_contact_geometry", None)
    if cur is None:
        config.effector_terrain_contact_geometry = EffectorTerrainContactGeometryConfig(enabled=on)
    else:
        cur.enabled = on


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "label": "EFFECTOR TERRAIN CONTACT GEOMETRY",
        "config_path": "effector_terrain_contact_geometry.enabled",
        "enabled": bool(enabled),
        "profile_version": PROFILE_VERSION,
        "provenance": "acanthostega_effector_terrain_contact_geometry",
        "banner": BANNER,
        "researcher_only_receipts": True,
        "cognition_exposed": False,
        "response": dict(RESPONSE_FLAGS),
    }


@dataclass
class EffectorTerrainContactGeometryState:
    config: EffectorTerrainContactGeometryConfig
    # key = f"{body_id}|{effector_id}" → last committed world pose [x,y,z,tick]
    prev_poses: dict[str, list[float]] = field(default_factory=dict)
    # active episodes keyed by same key
    active: dict[str, dict[str, Any]] = field(default_factory=dict)
    episode_tick: int = -1
    episode_next: int = 0
    counters: dict[str, int] = field(default_factory=dict)
    last_step: dict[str, Any] | None = None
    history: list[dict[str, Any]] = field(default_factory=list)


def _zero_counters() -> dict[str, int]:
    return {
        "steps": 0,
        "begin": 0,
        "persist": 0,
        "end": 0,
        "endpoint_hits": 0,
        "swept_hits": 0,
        "queries": 0,
    }


def state_of(world: Any) -> EffectorTerrainContactGeometryState | None:
    raw = getattr(world, "effector_terrain_contact_geometry_state", None)
    return raw if isinstance(raw, EffectorTerrainContactGeometryState) else None


def ensure_effector_terrain_contact_geometry_for_runtime(
    world: Any, config: Any
) -> EffectorTerrainContactGeometryState | None:
    if not effector_terrain_contact_geometry_is_active(config):
        if hasattr(world, "effector_terrain_contact_geometry_state"):
            world.effector_terrain_contact_geometry_state = None
        return None
    raw_cfg = getattr(config, "effector_terrain_contact_geometry", None)
    cfg = (
        raw_cfg
        if isinstance(raw_cfg, EffectorTerrainContactGeometryConfig)
        else EffectorTerrainContactGeometryConfig.from_dict(
            raw_cfg.to_dict() if raw_cfg is not None and hasattr(raw_cfg, "to_dict") else None
        )
    )
    validate_config(cfg)
    st = state_of(world)
    if st is None:
        st = EffectorTerrainContactGeometryState(config=cfg, counters=_zero_counters())
        world.effector_terrain_contact_geometry_state = st
    else:
        st.config = cfg
    return st


def copy_state(st: EffectorTerrainContactGeometryState | None) -> EffectorTerrainContactGeometryState | None:
    if st is None:
        return None
    return EffectorTerrainContactGeometryState(
        config=EffectorTerrainContactGeometryConfig.from_dict(st.config.to_dict()),
        prev_poses={k: list(v) for k, v in st.prev_poses.items()},
        active={k: dict(v) for k, v in st.active.items()},
        episode_tick=int(st.episode_tick),
        episode_next=int(st.episode_next),
        counters=dict(st.counters),
        last_step=dict(st.last_step) if st.last_step else None,
        history=[dict(r) for r in st.history],
    )


def serialize_state(st: EffectorTerrainContactGeometryState | None) -> dict[str, Any] | None:
    if st is None:
        return None
    return {
        "schema_version": STATE_SCHEMA,
        "config": st.config.to_dict(),
        "prev_poses": {k: [float(v[0]), float(v[1]), float(v[2]), int(v[3])] for k, v in sorted(st.prev_poses.items())},
        "active": {k: dict(v) for k, v in sorted(st.active.items())},
        "episode_allocator": {"tick": int(st.episode_tick), "next_sequence": int(st.episode_next)},
        "counters": dict(st.counters),
        "last_step": dict(st.last_step) if st.last_step else None,
        "history": list(st.history),
        "banner": BANNER,
        "researcher_only": True,
    }


def restore_state(
    world: Any, data: dict[str, Any] | None, config: Any
) -> EffectorTerrainContactGeometryState | None:
    if not effector_terrain_contact_geometry_is_active(config):
        world.effector_terrain_contact_geometry_state = None
        return None
    if not data:
        return ensure_effector_terrain_contact_geometry_for_runtime(world, config)
    raw_cfg = data.get("config")
    cfg = EffectorTerrainContactGeometryConfig.from_dict(raw_cfg if isinstance(raw_cfg, dict) else None)
    validate_config(cfg)
    alloc = data.get("episode_allocator") or {}
    st = EffectorTerrainContactGeometryState(
        config=cfg,
        prev_poses={
            str(k): [float(v[0]), float(v[1]), float(v[2]), int(v[3])]
            for k, v in (data.get("prev_poses") or {}).items()
        },
        active={str(k): dict(v) for k, v in (data.get("active") or {}).items()},
        episode_tick=int(alloc.get("tick", -1)),
        episode_next=int(alloc.get("next_sequence", 0)),
        counters={**_zero_counters(), **{k: int(v) for k, v in (data.get("counters") or {}).items()}},
        last_step=dict(data["last_step"]) if isinstance(data.get("last_step"), dict) else None,
        history=[dict(r) for r in (data.get("history") or [])],
    )
    world.effector_terrain_contact_geometry_state = st
    return st


def _dims(world: Any) -> tuple[int, int]:
    from mechanistic_mind.physical_system import procedural_surface_columns as psc

    st = psc.state_of(world)
    if st is not None:
        return int(st.width), int(st.height)
    t = getattr(world, "T", None)
    return (int(t.shape[1]), int(t.shape[0])) if t is not None else (32, 32)


def _alloc_episode(st: EffectorTerrainContactGeometryState, tick: int) -> str:
    if int(st.episode_tick) != int(tick):
        st.episode_tick = int(tick)
        st.episode_next = 0
    st.episode_next += 1
    return f"etc-{int(tick):06d}-{st.episode_next:04d}"


def effector_world_pose(
    body: Any,
    *,
    width: int,
    height: int,
    config: Any,
    manipulator_id: str,
    runtime: Any = None,
    world: Any = None,
    body_id: str | None = None,
) -> tuple[float, float, float]:
    """Authoritative effector world (x, y, z).

    Base: xy from effector_world_xy; z = body centre_z.
    When manipulator_relative_world_actuation is ON, z += body-local relative_z.
    """
    from mechanistic_mind.physical_system.flat_ground_gravity import (
        centre_z_of,
        ensure_body_vertical,
        flat_ground_gravity_is_active,
    )
    from mechanistic_mind.physical_system.physical_manipulator import effector_world_xy

    ex, ey = effector_world_xy(
        body, width=width, height=height, config=config, manipulator_id=manipulator_id, runtime=runtime
    )
    if flat_ground_gravity_is_active(config):
        ensure_body_vertical(body, config)
        ez = float(centre_z_of(body, kind="body", config=config))
    else:
        # Without vertical state there is no terrain-contact z; treat as unavailable high.
        ez = float("inf")
    # Relative vertical actuation (kinematic); default 0 preserves prior geometry.
    try:
        from mechanistic_mind.physical_system.manipulator_relative_world_actuation import (
            manipulator_relative_world_actuation_is_active,
            relative_z_of,
        )

        if (
            world is not None
            and body_id is not None
            and manipulator_relative_world_actuation_is_active(config)
        ):
            ez = float(ez) + float(
                relative_z_of(world, str(body_id), str(manipulator_id), config=config)
            )
    except Exception:
        pass
    return float(ex), float(ey), float(ez)


def sample_terrain_at(
    world: Any, x: float, y: float, *, config: Any
) -> dict[str, Any]:
    """Authoritative continuous surface sample (mutated columns included)."""
    from mechanistic_mind.physical_system.continuous_surface_geometry import (
        continuous_surface_geometry_is_active,
        sample_surface_geometry,
    )
    from mechanistic_mind.physical_system.surface_elevation_support import surface_support_height

    w, hh = _dims(world)
    xp = float(wrap_coord(float(x), w))
    yp = float(wrap_coord(float(y), hh))
    cx = int(wrap_coord(math.floor(xp), w))
    cy = int(wrap_coord(math.floor(yp), hh))
    if continuous_surface_geometry_is_active(config):
        s = sample_surface_geometry(world, xp, yp, config=config, record=False)
        return {
            "height": float(s["height"]),
            "normal_x": float(s["normal_x"]),
            "normal_y": float(s["normal_y"]),
            "normal_z": float(s["normal_z"]),
            "cell_x": cx,
            "cell_y": cy,
            "u": float(s["u"]),
            "v": float(s["v"]),
            "cells": dict(s["cells"]),
            "source": "continuous_surface_geometry",
        }
    # SES discrete height fallback (still authoritative world geometry when CSG off).
    h = float(surface_support_height(world, xp, yp, config=config))
    return {
        "height": h,
        "normal_x": 0.0,
        "normal_y": 0.0,
        "normal_z": 1.0,
        "cell_x": cx,
        "cell_y": cy,
        "u": 0.0,
        "v": 0.0,
        "cells": {"00": [cx, cy], "10": [cx, cy], "01": [cx, cy], "11": [cx, cy]},
        "source": "surface_support_height",
    }


def clearance_at(
    world: Any,
    x: float,
    y: float,
    z: float,
    *,
    radius: float,
    config: Any,
) -> dict[str, Any]:
    # VW5: occupancy-aware clearance (floor-below). Legacy max surface is not authority.
    try:
        from mechanistic_mind.physical_system.effector_held_occupancy_exertion_bridge import (
            effector_held_occupancy_exertion_bridge_is_active,
            occupancy_sample_as_terrain,
        )

        if effector_held_occupancy_exertion_bridge_is_active(config):
            terrain = occupancy_sample_as_terrain(
                world, x, y, z, radius=float(radius), config=config
            )
            h = float(terrain["height"])
            # No floor → free (positive clearance).
            if not math.isfinite(h):
                return {
                    "clearance": float("inf"),
                    "height": h,
                    "penetration": 0.0,
                    "terrain": terrain,
                }
            clearance = float(z) - float(radius) - h
            return {
                "clearance": float(clearance),
                "height": h,
                "penetration": float(max(0.0, -clearance)),
                "terrain": terrain,
            }
    except Exception:
        pass
    terrain = sample_terrain_at(world, x, y, config=config)
    h = float(terrain["height"])
    clearance = float(z) - float(radius) - h
    return {
        "clearance": float(clearance),
        "height": h,
        "penetration": float(max(0.0, -clearance)),
        "terrain": terrain,
    }


def _shortest_delta(a: float, b: float, period: int) -> float:
    """Toroidal shortest delta from a to b on [0, period)."""
    d = float(b) - float(a)
    half = 0.5 * float(period)
    if d > half:
        d -= float(period)
    elif d < -half:
        d += float(period)
    return d


def evaluate_probe_contact(
    world: Any,
    *,
    x: float,
    y: float,
    z: float,
    radius: float,
    epsilon: float,
    config: Any,
    prev: tuple[float, float, float] | None = None,
    sweep_step: float = DEFAULT_SWEEP_STEP,
    sweep_max_samples: int = DEFAULT_SWEEP_MAX_SAMPLES,
) -> dict[str, Any]:
    """Pure geometry: endpoint + optional swept probe vs authoritative terrain."""
    w, h = _dims(world)
    end = clearance_at(world, x, y, z, radius=radius, config=config)
    in_end = bool(float(end["clearance"]) <= float(epsilon))
    detection = DETECTION_ENDPOINT if in_end else None
    toi = 1.0 if in_end else None
    contact_x, contact_y, contact_z = float(x), float(y), float(z)
    best = end
    samples = 1

    if prev is not None and not in_end:
        x0, y0, z0 = float(prev[0]), float(prev[1]), float(prev[2])
        dx = _shortest_delta(x0, x, w)
        dy = _shortest_delta(y0, y, h)
        dz = float(z) - z0
        path_len = math.sqrt(dx * dx + dy * dy + dz * dz)
        n = int(max(2, min(int(sweep_max_samples), math.ceil(path_len / float(sweep_step)) + 1)))
        prev_c = clearance_at(world, x0, y0, z0, radius=radius, config=config)
        samples = n
        # Walk t in (0,1]; first non-positive clearance wins.
        for i in range(1, n + 1):
            t = float(i) / float(n)
            xi = wrap_coord(x0 + t * dx, w)
            yi = wrap_coord(y0 + t * dy, h)
            zi = z0 + t * dz
            cur = clearance_at(world, xi, yi, zi, radius=radius, config=config)
            samples += 1
            c0 = float(prev_c["clearance"])
            c1 = float(cur["clearance"])
            crossed = (c0 > float(epsilon) and c1 <= float(epsilon)) or (c1 <= float(epsilon))
            if crossed and c1 <= float(epsilon):
                # Refine TOI between previous sample and this one if sign change.
                if c0 > float(epsilon) and c1 <= float(epsilon):
                    denom = c0 - c1
                    frac = float(c0 / denom) if abs(denom) > 1e-18 else 1.0
                    frac = max(0.0, min(1.0, frac))
                    t_hit = ((i - 1) + frac) / float(n)
                else:
                    t_hit = t
                toi = float(t_hit)
                contact_x = wrap_coord(x0 + toi * dx, w)
                contact_y = wrap_coord(y0 + toi * dy, h)
                contact_z = z0 + toi * dz
                best = clearance_at(
                    world, contact_x, contact_y, contact_z, radius=radius, config=config
                )
                detection = DETECTION_SWEPT
                in_end = True
                break
            prev_c = cur

    terrain = best["terrain"]
    nx, ny, nz = float(terrain["normal_x"]), float(terrain["normal_y"]), float(terrain["normal_z"])
    # Contact point on surface along vertical probe: (x,y,h) when contacting.
    h_s = float(best["height"])
    if in_end:
        px, py, pz = float(contact_x), float(contact_y), float(h_s)
    else:
        px = py = pz = None

    return {
        "in_contact": bool(in_end),
        "detection_mode": detection,
        "toi": toi,
        "clearance": float(best["clearance"]),
        "penetration": float(best["penetration"]),
        "effector_x": float(x),
        "effector_y": float(y),
        "effector_z": float(z),
        "contact_point": None if px is None else [float(px), float(py), float(pz)],
        "normal": [nx, ny, nz],
        "surface_height": h_s,
        "terrain_cell": [int(terrain["cell_x"]), int(terrain["cell_y"])],
        "terrain_cells": dict(terrain["cells"]),
        "terrain_source": str(terrain["source"]),
        "samples": int(samples),
        "radius": float(radius),
        "epsilon": float(epsilon),
    }


def _effector_ids_for(config: Any) -> list[str]:
    from mechanistic_mind.physical_system.physical_manipulator import (
        BILATERAL_IDS,
        MANIPULATOR_ID,
        bilateral_manipulator_is_active,
        manipulator_is_active,
    )

    if bilateral_manipulator_is_active(config):
        return list(BILATERAL_IDS)
    if manipulator_is_active(config):
        mid = str(
            getattr(getattr(config, "single_physical_manipulator", None), "manipulator_id", None)
            or MANIPULATOR_ID
        )
        return [mid]
    return []


def _receipt(
    tick: int,
    phase: str,
    *,
    body_id: str,
    effector_id: str,
    episode_id: str,
    measure: dict[str, Any],
    cfg: EffectorTerrainContactGeometryConfig,
    end_reason: str | None = None,
) -> dict[str, Any]:
    rec = {
        "receipt_kind": RECEIPT_KIND,
        "event_kind": f"EFFECTOR_TERRAIN_CONTACT_{phase}",
        "mechanism": MECHANISM_ID,
        "profile_version": PROFILE_VERSION,
        "tick": int(tick),
        "phase": str(phase),
        "episode_id": str(episode_id),
        "body_id": str(body_id),
        "effector_id": str(effector_id),
        "contact_fact": bool(phase != PHASE_END),
        "detection_mode": measure.get("detection_mode"),
        "toi": measure.get("toi"),
        "clearance": measure.get("clearance"),
        "penetration": measure.get("penetration"),
        "effector_position": [
            measure.get("effector_x"),
            measure.get("effector_y"),
            measure.get("effector_z"),
        ],
        "contact_point": measure.get("contact_point"),
        "normal": measure.get("normal"),
        "surface_height": measure.get("surface_height"),
        "terrain_cell": measure.get("terrain_cell"),
        "terrain_source": measure.get("terrain_source"),
        "z_authority": Z_AUTHORITY,
        "contact_radius": float(cfg.effector_terrain_contact_radius),
        "contact_radius_source": CONTACT_RADIUS_SOURCE,
        "contact_epsilon": float(cfg.contact_epsilon),
        "samples": measure.get("samples"),
        "end_reason": end_reason,
        "researcher_only": True,
        "cognition_exposed": False,
        **RESPONSE_FLAGS,
    }
    return rec


def detect_effector_terrain_contacts(
    world: Any,
    holders: list[dict[str, Any]],
    *,
    tick: int,
    config: Any,
) -> dict[str, Any]:
    """Lifecycle update for all active effectors vs authoritative terrain.

    holders: list of {body_id, body, config, runtime?} sorted externally or here.
    Geometry only — no collision response.
    """
    st = ensure_effector_terrain_contact_geometry_for_runtime(world, config)
    if st is None:
        return {"active": False, "receipts": []}

    cfg = st.config
    w, h = _dims(world)
    radius = float(cfg.effector_terrain_contact_radius)
    eps = float(cfg.contact_epsilon)
    te = int(tick)

    # Deterministic holder / effector order.
    rows = sorted(holders, key=lambda r: str(r.get("body_id") or ""))
    seen_keys: set[str] = set()
    measures: list[tuple[str, str, str, dict[str, Any]]] = []

    for row in rows:
        body = row.get("body")
        body_id = str(row.get("body_id") or "")
        row_cfg = row.get("config", config)
        runtime = row.get("runtime")
        if body is None or not body_id:
            continue
        for mid in _effector_ids_for(row_cfg):
            key = f"{body_id}|{mid}"
            seen_keys.add(key)
            ex, ey, ez = effector_world_pose(
                body,
                width=w,
                height=h,
                config=row_cfg,
                manipulator_id=mid,
                runtime=runtime,
                world=world,
                body_id=body_id,
            )
            prev_raw = st.prev_poses.get(key)
            prev = None
            if prev_raw is not None and len(prev_raw) >= 3:
                # Missing history / restore discontinuity → endpoint only this tick.
                if int(prev_raw[3]) == te - 1 or int(prev_raw[3]) == te:
                    prev = (float(prev_raw[0]), float(prev_raw[1]), float(prev_raw[2]))
            m = evaluate_probe_contact(
                world,
                x=ex,
                y=ey,
                z=ez,
                radius=radius,
                epsilon=eps,
                config=row_cfg,
                prev=prev,
                sweep_step=float(cfg.sweep_step),
                sweep_max_samples=int(cfg.sweep_max_samples),
            )
            st.counters["queries"] = int(st.counters.get("queries", 0)) + 1
            measures.append((key, body_id, mid, m))
            st.prev_poses[key] = [float(ex), float(ey), float(ez), te]

    # Stable order: earliest TOI, then body_id, effector_id.
    def _sort_key(item: tuple[str, str, str, dict[str, Any]]) -> tuple:
        key, body_id, mid, m = item
        toi = m.get("toi")
        toi_v = float(toi) if toi is not None else 2.0
        return (0 if m.get("in_contact") else 1, toi_v, body_id, mid)

    measures.sort(key=_sort_key)

    receipts: list[dict[str, Any]] = []
    still_active: set[str] = set()

    for key, body_id, mid, m in measures:
        if not m.get("in_contact"):
            continue
        still_active.add(key)
        if key in st.active:
            ep = st.active[key]
            phase = PHASE_PERSIST
            st.counters["persist"] = int(st.counters.get("persist", 0)) + 1
            ep["last_tick"] = te
            ep["detection_mode"] = m.get("detection_mode")
            rec = _receipt(
                te, phase, body_id=body_id, effector_id=mid, episode_id=ep["episode_id"], measure=m, cfg=cfg
            )
        else:
            eid = _alloc_episode(st, te)
            phase = PHASE_BEGIN
            st.counters["begin"] = int(st.counters.get("begin", 0)) + 1
            if m.get("detection_mode") == DETECTION_SWEPT:
                st.counters["swept_hits"] = int(st.counters.get("swept_hits", 0)) + 1
            else:
                st.counters["endpoint_hits"] = int(st.counters.get("endpoint_hits", 0)) + 1
            st.active[key] = {
                "episode_id": eid,
                "body_id": body_id,
                "effector_id": mid,
                "begin_tick": te,
                "last_tick": te,
                "detection_mode": m.get("detection_mode"),
            }
            rec = _receipt(
                te, phase, body_id=body_id, effector_id=mid, episode_id=eid, measure=m, cfg=cfg
            )
        receipts.append(rec)

    # ENDs for previously active keys no longer in contact / gone.
    end_receipts: list[dict[str, Any]] = []
    for key in sorted(list(st.active.keys())):
        if key in still_active:
            continue
        ep = st.active.pop(key)
        body_id = str(ep["body_id"])
        mid = str(ep["effector_id"])
        reason = END_SEPARATION
        if key not in seen_keys:
            reason = END_EFFECTOR_REMOVED if "|" in key else END_BODY_REMOVED
        # Use last known pose clearance if available.
        prev_raw = st.prev_poses.get(key)
        if prev_raw is not None:
            m_end = evaluate_probe_contact(
                world,
                x=float(prev_raw[0]),
                y=float(prev_raw[1]),
                z=float(prev_raw[2]),
                radius=radius,
                epsilon=eps,
                config=config,
                prev=None,
            )
        else:
            m_end = {
                "detection_mode": None,
                "toi": None,
                "clearance": None,
                "penetration": 0.0,
                "effector_x": None,
                "effector_y": None,
                "effector_z": None,
                "contact_point": None,
                "normal": None,
                "surface_height": None,
                "terrain_cell": None,
                "terrain_source": None,
                "samples": 0,
            }
        st.counters["end"] = int(st.counters.get("end", 0)) + 1
        end_receipts.append(
            _receipt(
                te,
                PHASE_END,
                body_id=body_id,
                effector_id=mid,
                episode_id=str(ep["episode_id"]),
                measure=m_end,
                cfg=cfg,
                end_reason=reason,
            )
        )

    for k in [k for k in st.prev_poses if k not in seen_keys]:
        del st.prev_poses[k]

    all_receipts = end_receipts + receipts
    # Deterministic receipt order: ENDs first (stable key), then BEGIN/PERSIST by sort already.
    all_receipts.sort(
        key=lambda r: (
            0 if r["phase"] == PHASE_END else 1,
            str(r.get("body_id") or ""),
            str(r.get("effector_id") or ""),
            str(r.get("episode_id") or ""),
        )
    )

    st.counters["steps"] = int(st.counters.get("steps", 0)) + 1
    step = {
        "event": EVENT_STEP,
        "tick": te,
        "receipts": all_receipts,
        "active_episodes": len(st.active),
        "begin": sum(1 for r in all_receipts if r["phase"] == PHASE_BEGIN),
        "persist": sum(1 for r in all_receipts if r["phase"] == PHASE_PERSIST),
        "end": sum(1 for r in all_receipts if r["phase"] == PHASE_END),
        "z_authority": Z_AUTHORITY,
        "response": dict(RESPONSE_FLAGS),
        "researcher_only": True,
    }
    st.last_step = step
    st.history.append(step)
    lim = int(cfg.history_limit)
    if len(st.history) > lim:
        st.history = st.history[-lim:]
    world.last_effector_terrain_contact_step = step
    # Passive researcher reachability traces over the same ETC measures (no re-solve).
    try:
        from mechanistic_mind.physical_system.effector_occupancy_reachability_trace import (
            record_reachability_traces_from_etc_measures,
        )

        record_reachability_traces_from_etc_measures(
            world,
            config=config,
            tick=te,
            measures=measures,
            contact_receipts=all_receipts,
            holders=rows,
        )
    except Exception:
        pass
    return step
