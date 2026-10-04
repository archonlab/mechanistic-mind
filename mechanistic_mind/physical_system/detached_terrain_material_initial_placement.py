"""Acanthostega Beta 4 · Detached terrain material initial placement V1.

Mechanism: detached_terrain_material_initial_placement
Preset: ACANTHOSTEGA_BETA4_DETACHED_TERRAIN_MATERIAL_INITIAL_PLACEMENT
Parent: ACANTHOSTEGA_BETA4_HELD_MEDIATED_SURFACE_EXERTION_INTEGRATION

Integration: replaces informal SEPARATE_SURFACE_COLUMN_SLICE spawn pose with
post-mutation local support + bounded deterministic candidates (K<=16).
No new transmission/resistance law; no second WMT/spawn path; no ejection impulse.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from mechanistic_mind.physical_system.resource_objects import CANONICAL_COLLISION_RADIUS

MECHANISM_ID = "detached_terrain_material_initial_placement"
PROFILE_VERSION = "DETACHED_TERRAIN_MATERIAL_INITIAL_PLACEMENT_PROFILE_V1"
STATE_SCHEMA = "DETACHED_TERRAIN_MATERIAL_INITIAL_PLACEMENT_STATE_V1"
RECEIPT_KIND = "DETACHED_TERRAIN_MATERIAL_INITIAL_PLACEMENT"
PLACEMENT_POLICY = "DETACHED_TERRAIN_PLACEMENT_POST_MUTATION_SUPPORT_V1"
EVENT_PLACED = "DETACHED_TERRAIN_MATERIAL_PLACED"
EVENT_REJECTED = "DETACHED_TERRAIN_MATERIAL_PLACEMENT_REJECTED"

BANNER = (
    "DETACHED TERRAIN MATERIAL INITIAL PLACEMENT · "
    "POST-MUTATION SUPPORT · BOUNDED DETERMINISTIC CANDIDATES · "
    "ZERO INITIAL VELOCITY · DYNAMICS BEGIN T+1"
)

HISTORY_LIMIT_DEFAULT = 64
MAX_CANDIDATES = 16
BODY_CONTACT_RADIUS_DEFAULT = 0.575
OVERLAP_MARGIN = 0.95  # match legacy _placement_ok

# Versioned candidate offsets from cell centre (cell_x+0.5, cell_y+0.5).
# Index 0 = natural seed (cell centre). Then ring-1 (legacy 0.35), then ring-2 (0.70).
CANDIDATE_OFFSETS_V1: tuple[tuple[float, float], ...] = (
    (0.00, 0.00),
    (0.35, 0.00),
    (-0.35, 0.00),
    (0.00, 0.35),
    (0.00, -0.35),
    (0.35, 0.35),
    (0.35, -0.35),
    (-0.35, 0.35),
    (-0.35, -0.35),
    (0.70, 0.00),
    (-0.70, 0.00),
    (0.00, 0.70),
    (0.00, -0.70),
    (0.70, 0.70),
    (0.70, -0.70),
    (-0.70, 0.70),
)
assert len(CANDIDATE_OFFSETS_V1) == MAX_CANDIDATES

# Vertical convention (FGG/SES): object.z is feet/support reference;
# centre_z = object.z + collision_radius (diagnostic).
SUPPORT_TO_CENTRE_Z = "object.z = support_z; centre_z = object.z + collision_radius"


@dataclass
class DetachedTerrainMaterialInitialPlacementConfig:
    enabled: bool = False
    max_candidates: int = MAX_CANDIDATES
    history_limit: int = HISTORY_LIMIT_DEFAULT

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "max_candidates": int(self.max_candidates),
            "history_limit": int(self.history_limit),
            "profile_version": PROFILE_VERSION,
            "placement_policy": PLACEMENT_POLICY,
            "support_to_centre_z": SUPPORT_TO_CENTRE_Z,
            "max_candidates_hard_cap": MAX_CANDIDATES,
            "separation_impulse": False,
            "dynamics_deferred_to_t_plus_1": True,
            "new_transmission_law": False,
            "new_resistance_law": False,
            "second_spawn_path": False,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "DetachedTerrainMaterialInitialPlacementConfig":
        d = dict(data or {})
        return cls(
            enabled=bool(d.get("enabled", False)),
            max_candidates=min(int(d.get("max_candidates", MAX_CANDIDATES)), MAX_CANDIDATES),
            history_limit=int(d.get("history_limit", HISTORY_LIMIT_DEFAULT)),
        )


def validate_config(cfg: DetachedTerrainMaterialInitialPlacementConfig) -> None:
    if int(cfg.max_candidates) < 1 or int(cfg.max_candidates) > MAX_CANDIDATES:
        raise ValueError(f"max_candidates must be in [1, {MAX_CANDIDATES}]")
    if int(cfg.history_limit) < 1:
        raise ValueError("history_limit must be >= 1")


def detached_terrain_material_initial_placement_is_active(config: Any) -> bool:
    cfg = getattr(config, "detached_terrain_material_initial_placement", None)
    return cfg is not None and bool(getattr(cfg, "enabled", False))


def set_detached_terrain_material_initial_placement(config: Any, enabled: bool) -> None:
    cur = getattr(config, "detached_terrain_material_initial_placement", None)
    if cur is None:
        config.detached_terrain_material_initial_placement = (
            DetachedTerrainMaterialInitialPlacementConfig(enabled=bool(enabled))
        )
    else:
        cur.enabled = bool(enabled)


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "mechanism_id": MECHANISM_ID,
        "profile_version": PROFILE_VERSION,
        "enabled": bool(enabled),
        "config_path": "detached_terrain_material_initial_placement.enabled",
        "provenance": "acanthostega_detached_terrain_material_initial_placement",
        "placement_policy": PLACEMENT_POLICY,
        "banner": BANNER,
    }


@dataclass
class DetachedTerrainMaterialInitialPlacementState:
    config: DetachedTerrainMaterialInitialPlacementConfig
    counters: dict[str, int] = field(default_factory=dict)
    last_step: dict[str, Any] | None = None
    history: list[dict[str, Any]] = field(default_factory=list)


def _zero_counters() -> dict[str, int]:
    return {
        "plans": 0,
        "placed": 0,
        "rejected_no_candidate": 0,
        "candidates_tried": 0,
        "body_rejects": 0,
        "object_rejects": 0,
        "support_rejects": 0,
    }


def state_of(world: Any) -> DetachedTerrainMaterialInitialPlacementState | None:
    raw = getattr(world, "detached_terrain_material_initial_placement_state", None)
    return raw if isinstance(raw, DetachedTerrainMaterialInitialPlacementState) else None


def ensure_detached_terrain_material_initial_placement_for_runtime(
    world: Any, config: Any
) -> DetachedTerrainMaterialInitialPlacementState | None:
    if not detached_terrain_material_initial_placement_is_active(config):
        if hasattr(world, "detached_terrain_material_initial_placement_state"):
            world.detached_terrain_material_initial_placement_state = None
        return None
    raw_cfg = getattr(config, "detached_terrain_material_initial_placement", None)
    cfg = (
        raw_cfg
        if isinstance(raw_cfg, DetachedTerrainMaterialInitialPlacementConfig)
        else DetachedTerrainMaterialInitialPlacementConfig.from_dict(
            raw_cfg.to_dict() if hasattr(raw_cfg, "to_dict") else raw_cfg
        )
    )
    validate_config(cfg)
    st = state_of(world)
    if st is None:
        st = DetachedTerrainMaterialInitialPlacementState(config=cfg, counters=_zero_counters())
        world.detached_terrain_material_initial_placement_state = st
    else:
        st.config = cfg
    return st


def serialize_state(st: DetachedTerrainMaterialInitialPlacementState | None) -> dict[str, Any] | None:
    if st is None:
        return None
    return {
        "schema_version": STATE_SCHEMA,
        "config": st.config.to_dict(),
        "counters": dict(st.counters),
        "last_step": dict(st.last_step) if st.last_step else None,
        "history": list(st.history),
        "banner": BANNER,
        "researcher_only": True,
    }


def restore_state(
    world: Any, data: dict[str, Any] | None, config: Any
) -> DetachedTerrainMaterialInitialPlacementState | None:
    if not detached_terrain_material_initial_placement_is_active(config):
        world.detached_terrain_material_initial_placement_state = None
        return None
    if not data:
        return ensure_detached_terrain_material_initial_placement_for_runtime(world, config)
    cfg = DetachedTerrainMaterialInitialPlacementConfig.from_dict(
        data.get("config") if isinstance(data.get("config"), dict) else None
    )
    validate_config(cfg)
    st = DetachedTerrainMaterialInitialPlacementState(
        config=cfg,
        counters={**_zero_counters(), **{a: int(b) for a, b in (data.get("counters") or {}).items()}},
        last_step=dict(data["last_step"]) if isinstance(data.get("last_step"), dict) else None,
        history=[dict(r) for r in (data.get("history") or [])],
    )
    world.detached_terrain_material_initial_placement_state = st
    return st


def object_dynamics_eligible(obj: Any, tick: int) -> bool:
    """Legacy objects (missing field) are immediately eligible."""
    raw = getattr(obj, "dynamics_eligible_tick", None)
    if raw is None:
        prov = getattr(obj, "provenance", None) or {}
        if isinstance(prov, dict) and prov.get("dynamics_eligible_tick") is not None:
            raw = prov.get("dynamics_eligible_tick")
        else:
            return True
    try:
        return int(tick) >= int(raw)
    except (TypeError, ValueError):
        return True


def candidate_offsets(*, max_candidates: int = MAX_CANDIDATES) -> tuple[tuple[float, float], ...]:
    k = max(1, min(int(max_candidates), MAX_CANDIDATES))
    return CANDIDATE_OFFSETS_V1[:k]


def _world_dims(world: Any) -> tuple[int, int]:
    t = getattr(world, "T", None)
    if t is not None and hasattr(t, "shape"):
        return int(t.shape[1]), int(t.shape[0])
    return 32, 32


def _wrap_xy(x: float, y: float, *, width: int, height: int) -> tuple[float, float]:
    try:
        from mechanistic_mind.planet.topology import wrap_coord

        return wrap_coord(float(x), float(y), width=width, height=height)
    except Exception:
        return float(x) % width, float(y) % height


def _shortest_xy(ax: float, ay: float, bx: float, by: float, *, width: int, height: int) -> float:
    try:
        from mechanistic_mind.planet.topology import shortest_toroidal_delta

        dx, dy = shortest_toroidal_delta(ax, ay, bx, by, width, height)
        return float(math.hypot(dx, dy))
    except Exception:
        return float(math.hypot(ax - bx, ay - by))


def collect_body_refs(world: Any, config: Any | None = None) -> list[tuple[str, Any]]:
    """Authoritative body list for occupancy — never PlanetState.body."""
    raw = getattr(world, "detached_placement_body_refs", None)
    if isinstance(raw, list) and raw:
        out: list[tuple[str, Any]] = []
        for row in raw:
            if isinstance(row, (tuple, list)) and len(row) >= 2 and row[1] is not None:
                out.append((str(row[0]), row[1]))
            elif isinstance(row, dict) and row.get("body") is not None:
                out.append((str(row.get("body_id") or "body"), row["body"]))
        if out:
            return sorted(out, key=lambda r: r[0])
    # Fallback: single-agent runtime may stash body on world via ensure hook.
    rt = getattr(world, "_host_runtime", None)
    if rt is not None:
        try:
            from mechanistic_mind.physical_system.spatial_contents import body_refs_for_runtime

            return sorted(body_refs_for_runtime(rt), key=lambda r: r[0])
        except Exception:
            pass
    return []


def _body_radius(config: Any) -> float:
    try:
        boc = getattr(config, "physical_body_resource_object_contact", None)
        if boc is not None:
            return float(getattr(boc, "body_contact_radius", BODY_CONTACT_RADIUS_DEFAULT))
    except Exception:
        pass
    return float(BODY_CONTACT_RADIUS_DEFAULT)


def _with_provisional_delta(world: Any, src_delta: Any):
    """Context: install planned column delta for support queries; restore after."""

    class _Ctx:
        def __enter__(self_inner):
            self_inner._prev = getattr(world, "surface_column_deltas", None)
            deltas = dict(self_inner._prev or {})
            cell = (int(src_delta.cell_x), int(src_delta.cell_y))
            deltas[cell] = src_delta
            world.surface_column_deltas = deltas
            return world

        def __exit__(self_inner, *exc):
            world.surface_column_deltas = self_inner._prev
            return False

    return _Ctx()


def plan_detached_material_initial_placement(
    world: Any,
    config: Any,
    *,
    source_cell: tuple[int, int],
    src_delta: Any,
    tick: int,
    collision_radius: float = CANONICAL_COLLISION_RADIUS,
    body_refs: list[tuple[str, Any]] | None = None,
    extra_obstacles: list[dict[str, Any]] | None = None,
    acting_body_id: str | None = None,
    transmitting_object_id: str | None = None,
) -> dict[str, Any]:
    """Pure planner: no ID alloc, no commit, no spatial mutate, temporary delta only."""
    st = ensure_detached_terrain_material_initial_placement_for_runtime(world, config)
    max_k = int(st.config.max_candidates) if st is not None else MAX_CANDIDATES
    offsets = candidate_offsets(max_candidates=max_k)
    width, height = _world_dims(world)
    seed_x = float(source_cell[0]) + 0.5
    seed_y = float(source_cell[1]) + 0.5
    radius = float(collision_radius)
    bodies = body_refs if body_refs is not None else collect_body_refs(world, config)
    brad = _body_radius(config)
    extras = list(extra_obstacles or [])
    objects = sorted(
        list(getattr(world, "resource_objects", None) or []),
        key=lambda o: str(getattr(o, "object_id", "")),
    )

    attempts: list[dict[str, Any]] = []
    accepted: dict[str, Any] | None = None

    with _with_provisional_delta(world, src_delta):
        from mechanistic_mind.physical_system.surface_elevation_support import (
            surface_support_height,
        )

        for idx, (dx, dy) in enumerate(offsets):
            cx, cy = _wrap_xy(seed_x + dx, seed_y + dy, width=width, height=height)
            row: dict[str, Any] = {
                "candidate_index": int(idx),
                "offset": [float(dx), float(dy)],
                "x": float(cx),
                "y": float(cy),
                "accepted": False,
            }
            try:
                support_z = float(surface_support_height(world, cx, cy, config=config))
            except Exception as exc:
                row["status"] = "SUPPORT_QUERY_FAILED"
                row["reason"] = type(exc).__name__
                attempts.append(row)
                if st is not None:
                    st.counters["support_rejects"] = int(st.counters.get("support_rejects", 0)) + 1
                continue
            if not math.isfinite(support_z):
                row["status"] = "SUPPORT_NONFINITE"
                row["reason"] = "nonfinite_support_z"
                attempts.append(row)
                if st is not None:
                    st.counters["support_rejects"] = int(st.counters.get("support_rejects", 0)) + 1
                continue
            row["support_z"] = float(support_z)
            row["object_z"] = float(support_z)  # feet / support reference
            row["centre_z"] = float(support_z) + float(radius)

            # Body conflicts
            body_hit = None
            for bid, body in bodies:
                bx = float(getattr(body, "x", 0.0) or 0.0)
                by = float(getattr(body, "y", 0.0) or 0.0)
                if _shortest_xy(cx, cy, bx, by, width=width, height=height) < (radius + brad) * OVERLAP_MARGIN:
                    body_hit = str(bid)
                    break
            if body_hit is not None:
                row["status"] = "BODY_OVERLAP"
                row["reason"] = f"body:{body_hit}"
                attempts.append(row)
                if st is not None:
                    st.counters["body_rejects"] = int(st.counters.get("body_rejects", 0)) + 1
                continue

            # ResourceObject conflicts (held transmitting object IS an obstacle)
            obj_hit = None
            for o in objects:
                oid = str(getattr(o, "object_id", "") or "")
                ox = float(getattr(o, "x", 0.0) or 0.0)
                oy = float(getattr(o, "y", 0.0) or 0.0)
                orad = float(
                    getattr(o, "collision_radius", CANONICAL_COLLISION_RADIUS)
                    or CANONICAL_COLLISION_RADIUS
                )
                if _shortest_xy(cx, cy, ox, oy, width=width, height=height) < (radius + orad) * OVERLAP_MARGIN:
                    obj_hit = oid or "object"
                    break
            if obj_hit is None:
                for ex in extras:
                    oid = str(ex.get("object_id") or "newborn")
                    ox = float(ex.get("x") or 0.0)
                    oy = float(ex.get("y") or 0.0)
                    orad = float(ex.get("collision_radius") or radius)
                    if _shortest_xy(cx, cy, ox, oy, width=width, height=height) < (radius + orad) * OVERLAP_MARGIN:
                        obj_hit = oid
                        break
            if obj_hit is not None:
                row["status"] = "OBJECT_OVERLAP"
                row["reason"] = f"object:{obj_hit}"
                attempts.append(row)
                if st is not None:
                    st.counters["object_rejects"] = int(st.counters.get("object_rejects", 0)) + 1
                continue

            row["status"] = "ACCEPTED"
            row["accepted"] = True
            attempts.append(row)
            accepted = row
            break

    if st is not None:
        st.counters["plans"] = int(st.counters.get("plans", 0)) + 1
        st.counters["candidates_tried"] = int(st.counters.get("candidates_tried", 0)) + len(attempts)

    base = {
        "receipt_kind": RECEIPT_KIND,
        "mechanism": MECHANISM_ID,
        "profile_version": PROFILE_VERSION,
        "placement_policy": PLACEMENT_POLICY,
        "support_to_centre_z": SUPPORT_TO_CENTRE_Z,
        "tick": int(tick),
        "source_cell": [int(source_cell[0]), int(source_cell[1])],
        "seed": [float(seed_x), float(seed_y)],
        "max_candidates": int(max_k),
        "candidates_tried": len(attempts),
        "attempts": attempts,
        "acting_body_id": acting_body_id,
        "transmitting_object_id": transmitting_object_id,
        "collision_radius": float(radius),
        "researcher_only": True,
        "cognition_exposed": False,
        "dynamics_eligible_tick": int(tick) + 1,
        "creation_tick": int(tick),
    }
    if accepted is None:
        if st is not None:
            st.counters["rejected_no_candidate"] = int(st.counters.get("rejected_no_candidate", 0)) + 1
        rec = {
            **base,
            "status": "REJECTED_NO_VALID_CANDIDATE",
            "event": EVENT_REJECTED,
            "accepted": False,
        }
        if st is not None:
            st.last_step = rec
            st.history.append(dict(rec))
            lim = int(st.config.history_limit)
            if len(st.history) > lim:
                st.history = st.history[-lim:]
        return rec

    if st is not None:
        st.counters["placed"] = int(st.counters.get("placed", 0)) + 1
    rec = {
        **base,
        "status": "PLACED",
        "event": EVENT_PLACED,
        "accepted": True,
        "candidate_index": int(accepted["candidate_index"]),
        "x": float(accepted["x"]),
        "y": float(accepted["y"]),
        "support_z": float(accepted["support_z"]),
        "z": float(accepted["object_z"]),
        "centre_z": float(accepted["centre_z"]),
        "physical_state": "FREE_STATIC",
        "grounded": True,
        "vx": 0.0,
        "vy": 0.0,
        "vz": 0.0,
    }
    if st is not None:
        st.last_step = rec
        st.history.append(dict(rec))
        lim = int(st.config.history_limit)
        if len(st.history) > lim:
            st.history = st.history[-lim:]
    world.last_detached_terrain_material_initial_placement = rec
    return rec


def record_same_tick_newborn_obstacle(world: Any, placement: dict[str, Any], object_id: str) -> None:
    """Register accepted newborn as obstacle for later same-tick separations."""
    rows = list(getattr(world, "detached_placement_same_tick_newborns", None) or [])
    rows.append(
        {
            "object_id": str(object_id),
            "x": float(placement.get("x") or 0.0),
            "y": float(placement.get("y") or 0.0),
            "collision_radius": float(placement.get("collision_radius") or CANONICAL_COLLISION_RADIUS),
            "tick": int(placement.get("tick") or 0),
        }
    )
    world.detached_placement_same_tick_newborns = rows


def same_tick_newborn_obstacles(world: Any, tick: int) -> list[dict[str, Any]]:
    rows = []
    for row in list(getattr(world, "detached_placement_same_tick_newborns", None) or []):
        if int(row.get("tick") or -1) == int(tick):
            rows.append(dict(row))
    return rows


def clear_same_tick_newborns_if_new_tick(world: Any, tick: int) -> None:
    rows = list(getattr(world, "detached_placement_same_tick_newborns", None) or [])
    if not rows:
        return
    if any(int(r.get("tick") or -1) != int(tick) for r in rows):
        world.detached_placement_same_tick_newborns = [
            r for r in rows if int(r.get("tick") or -1) == int(tick)
        ]


def overlay_dict(world: Any) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    return {
        "enabled": True,
        "banner": BANNER,
        "counters": dict(st.counters),
        "last_step": dict(st.last_step) if st.last_step else None,
        "placement_policy": PLACEMENT_POLICY,
        "researcher_only": True,
    }


def overlay_payload(world: Any) -> dict[str, Any] | None:
    return overlay_dict(world)


def researcher_summary(world: Any) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    ls = dict(st.last_step) if st.last_step else {}
    return {
        "enabled": True,
        "banner": BANNER,
        "counters": dict(st.counters),
        "last_step": ls,
        "placement_policy": PLACEMENT_POLICY,
        "max_candidates": MAX_CANDIDATES,
        "support_to_centre_z": SUPPORT_TO_CENTRE_Z,
        "researcher_only": True,
        "cognition_exposed": False,
    }
