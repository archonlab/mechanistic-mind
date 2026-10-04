"""Acanthostega Beta 4 · Held ResourceObject ↔ authoritative terrain contact geometry.

Mechanism: held_resource_object_terrain_contact_geometry
Preset: ACANTHOSTEGA_BETA4_HELD_RESOURCE_OBJECT_TERRAIN_CONTACT_GEOMETRY

Geometry FACT only. No impulse, work transmission, terrain failure, WMT, sound,
automatic release, or cognition tokens.

Collider (repository-native FGG contract):
  centre = (obj.x, obj.y, centre_z = obj.z + vertical_half_extent)
  radius = collision_radius  (= vertical_half_extent by default)
  NOT optical_radius / glyph / grasp_radius / point-effector substitute

Terrain: same evaluate_probe_contact / CSG oracle as bare-effector ETC.

Transitions (anti-fake-sweep, mirror HFC):
  STABLE_HELD → swept + endpoint
  GRASP_SNAP / holder-hand change / restore gap → endpoint only
  RELEASE / removal → END with explicit reason
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from mechanistic_mind.physical_system.flat_ground_gravity import (
    centre_z_of,
    ensure_object_vertical,
    flat_ground_gravity_is_active,
)
from mechanistic_mind.physical_system.physical_body_resource_object_contact import (
    CANONICAL_COLLISION_RADIUS,
    ensure_object_collision_radius,
)
from mechanistic_mind.physical_system.resource_objects import PHYSICAL_STATE_HELD

MECHANISM_ID = "held_resource_object_terrain_contact_geometry"
PROFILE_VERSION = "HELD_RESOURCE_OBJECT_TERRAIN_CONTACT_GEOMETRY_PROFILE_V1"
STATE_SCHEMA = "HELD_RESOURCE_OBJECT_TERRAIN_CONTACT_GEOMETRY_STATE_V1"
RECEIPT_KIND = "HELD_RESOURCE_OBJECT_TERRAIN_CONTACT"
EVENT_STEP = "HELD_RESOURCE_OBJECT_TERRAIN_CONTACT_STEP"

PHASE_BEGIN = "BEGIN"
PHASE_PERSIST = "PERSIST"
PHASE_END = "END"

DETECTION_ENDPOINT = "ENDPOINT_OVERLAP"
DETECTION_SWEPT = "SWEPT_CROSSING"

TRANSITION_STABLE_HELD = "STABLE_HELD"
TRANSITION_GRASP_SNAP = "GRASP_SNAP"
TRANSITION_HOLDER_CHANGED = "HOLDER_OR_MANIPULATOR_CHANGED"
TRANSITION_NO_HISTORY = "NO_PREVIOUS_HELD_POSE"

Z_AUTHORITY = "OBJECT_LOWER_SUPPORT_Z_PLUS_HALF_EXTENT"
COLLIDER_GEOMETRY = "SPHERE_AT_CENTRE_Z_RADIUS_EQ_COLLISION_RADIUS"
TERRAIN_SOURCE = "continuous_surface_geometry_or_surface_support_height"

DEFAULT_CONTACT_EPSILON = 1e-9
DEFAULT_SWEEP_STEP = 0.05
DEFAULT_SWEEP_MAX_SAMPLES = 64
HISTORY_LIMIT_DEFAULT = 64

END_GEOMETRIC_SEPARATION = "GEOMETRIC_SEPARATION"
END_OBJECT_RELEASED = "OBJECT_RELEASED"
END_OBJECT_REMOVED = "OBJECT_REMOVED"
END_HOLDER_REMOVED = "HOLDER_REMOVED"
END_MANIPULATOR_CHANGED = "MANIPULATOR_CHANGED"
END_PRESET_DISABLED = "PRESET_DISABLED"
END_RESTORE_OR_MISSING = "RESTORE_OR_MISSING_HISTORY"

RESPONSE_FLAGS = {
    "contact_fact": True,
    "collision_response_applied": False,
    "impulse_transferred": False,
    "position_corrected": False,
    "velocity_changed": False,
    "work_accounted": False,
    "work_transmission": False,
    "material_failure": False,
    "terrain_separated": False,
    "wmt_invoked": False,
    "sound_emitted": False,
    "automatic_release": False,
    "damage": False,
}

BANNER = (
    "BETA4 · HELD OBJECT ↔ TERRAIN CONTACT GEOMETRY · RESEARCHER-ONLY · "
    "GEOMETRY FACT ONLY · NO WORK TRANSMISSION · NO TERRAIN FAILURE · "
    "NO IMPULSE · NO SOUND"
)


@dataclass
class HeldResourceObjectTerrainContactGeometryConfig:
    """Fresh default OFF. Missing snapshot → mechanism OFF."""

    enabled: bool = False
    contact_epsilon: float = DEFAULT_CONTACT_EPSILON
    sweep_step: float = DEFAULT_SWEEP_STEP
    sweep_max_samples: int = DEFAULT_SWEEP_MAX_SAMPLES
    history_limit: int = HISTORY_LIMIT_DEFAULT
    default_object_collision_radius: float = CANONICAL_COLLISION_RADIUS

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "contact_epsilon": float(self.contact_epsilon),
            "sweep_step": float(self.sweep_step),
            "sweep_max_samples": int(self.sweep_max_samples),
            "history_limit": int(self.history_limit),
            "default_object_collision_radius": float(self.default_object_collision_radius),
            "profile_version": PROFILE_VERSION,
            "z_authority": Z_AUTHORITY,
            "collider_geometry": COLLIDER_GEOMETRY,
            "terrain_source": TERRAIN_SOURCE,
            "response": dict(RESPONSE_FLAGS),
            "optical_radius_used": False,
            "glyph_geometry_used": False,
            "point_effector_proxy": False,
        }

    @classmethod
    def from_dict(
        cls, data: dict[str, Any] | None
    ) -> "HeldResourceObjectTerrainContactGeometryConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        ver = data.get("profile_version")
        if ver is not None and str(ver) != PROFILE_VERSION:
            raise ValueError(f"unknown held-terrain contact profile: {ver}")
        return cls(
            enabled=bool(data.get("enabled", False)),
            contact_epsilon=float(data.get("contact_epsilon", DEFAULT_CONTACT_EPSILON)),
            sweep_step=float(data.get("sweep_step", DEFAULT_SWEEP_STEP)),
            sweep_max_samples=int(data.get("sweep_max_samples", DEFAULT_SWEEP_MAX_SAMPLES)),
            history_limit=int(data.get("history_limit", HISTORY_LIMIT_DEFAULT)),
            default_object_collision_radius=float(
                data.get("default_object_collision_radius", CANONICAL_COLLISION_RADIUS)
            ),
        )


def validate_config(cfg: HeldResourceObjectTerrainContactGeometryConfig) -> None:
    if float(cfg.contact_epsilon) < 0.0:
        raise ValueError("contact_epsilon must be >= 0")
    if float(cfg.sweep_step) <= 0.0:
        raise ValueError("sweep_step must be > 0")
    if int(cfg.sweep_max_samples) < 2:
        raise ValueError("sweep_max_samples must be >= 2")


def held_resource_object_terrain_contact_geometry_is_active(config: Any) -> bool:
    cfg = getattr(config, "held_resource_object_terrain_contact_geometry", None)
    return bool(cfg is not None and getattr(cfg, "enabled", False))


def set_held_resource_object_terrain_contact_geometry(config: Any, enabled: bool) -> None:
    on = bool(enabled)
    cur = getattr(config, "held_resource_object_terrain_contact_geometry", None)
    if cur is None:
        config.held_resource_object_terrain_contact_geometry = (
            HeldResourceObjectTerrainContactGeometryConfig(enabled=on)
        )
    else:
        cur.enabled = on


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "label": "HELD RESOURCE OBJECT TERRAIN CONTACT GEOMETRY",
        "config_path": "held_resource_object_terrain_contact_geometry.enabled",
        "enabled": bool(enabled),
        "profile_version": PROFILE_VERSION,
        "provenance": "acanthostega_held_resource_object_terrain_contact_geometry",
        "banner": BANNER,
        "cognition_exposed": False,
        "work_transmission": False,
        "terrain_failure": False,
    }


@dataclass
class HeldResourceObjectTerrainContactGeometryState:
    config: HeldResourceObjectTerrainContactGeometryConfig
    # key = object_id → active episode meta
    active: dict[str, dict[str, Any]] = field(default_factory=dict)
    # key = object_id → [x, y, centre_z, tick]
    prev_poses: dict[str, list[float]] = field(default_factory=dict)
    # key = object_id → {holder_body_id, manipulator_id, pose:[x,y,cz]}
    prev_held_identity: dict[str, dict[str, Any]] = field(default_factory=dict)
    episode_tick: int = -1
    episode_next: int = 0
    last_step: dict[str, Any] | None = None
    history: list[dict[str, Any]] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=dict)
    invalid_holder_diagnostics: list[dict[str, Any]] = field(default_factory=list)


def _zero_counters() -> dict[str, int]:
    return {
        "queries": 0,
        "begin": 0,
        "persist": 0,
        "end": 0,
        "swept_hits": 0,
        "endpoint_hits": 0,
        "grasp_snap_endpoint_only": 0,
        "invalid_holder": 0,
    }


def state_of(world: Any) -> HeldResourceObjectTerrainContactGeometryState | None:
    raw = getattr(world, "held_resource_object_terrain_contact_geometry_state", None)
    return raw if isinstance(raw, HeldResourceObjectTerrainContactGeometryState) else None


def ensure_held_resource_object_terrain_contact_geometry_for_runtime(
    world: Any, config: Any
) -> HeldResourceObjectTerrainContactGeometryState | None:
    if not held_resource_object_terrain_contact_geometry_is_active(config):
        if hasattr(world, "held_resource_object_terrain_contact_geometry_state"):
            world.held_resource_object_terrain_contact_geometry_state = None
        return None
    raw_cfg = getattr(config, "held_resource_object_terrain_contact_geometry", None)
    cfg = (
        raw_cfg
        if isinstance(raw_cfg, HeldResourceObjectTerrainContactGeometryConfig)
        else HeldResourceObjectTerrainContactGeometryConfig.from_dict(
            raw_cfg.to_dict() if raw_cfg is not None and hasattr(raw_cfg, "to_dict") else None
        )
    )
    validate_config(cfg)
    st = state_of(world)
    if st is None:
        st = HeldResourceObjectTerrainContactGeometryState(
            config=cfg, counters=_zero_counters()
        )
        world.held_resource_object_terrain_contact_geometry_state = st
    else:
        st.config = cfg
    return st


def serialize_state(
    st: HeldResourceObjectTerrainContactGeometryState | None,
) -> dict[str, Any] | None:
    if st is None:
        return None
    return {
        "schema_version": STATE_SCHEMA,
        "config": st.config.to_dict(),
        "active": {k: dict(v) for k, v in sorted(st.active.items())},
        "prev_poses": {
            k: [float(v[0]), float(v[1]), float(v[2]), int(v[3])]
            for k, v in sorted(st.prev_poses.items())
        },
        "prev_held_identity": {
            k: {
                "holder_body_id": v.get("holder_body_id"),
                "manipulator_id": v.get("manipulator_id"),
                "pose": list(v["pose"]) if v.get("pose") else None,
            }
            for k, v in sorted(st.prev_held_identity.items())
        },
        "episode_tick": int(st.episode_tick),
        "episode_next": int(st.episode_next),
        "counters": dict(st.counters),
        "last_step": dict(st.last_step) if st.last_step else None,
        "history": list(st.history),
        "banner": BANNER,
        "researcher_only": True,
    }


def restore_state(
    world: Any, data: dict[str, Any] | None, config: Any
) -> HeldResourceObjectTerrainContactGeometryState | None:
    if not held_resource_object_terrain_contact_geometry_is_active(config):
        world.held_resource_object_terrain_contact_geometry_state = None
        return None
    if not data:
        return ensure_held_resource_object_terrain_contact_geometry_for_runtime(world, config)
    cfg = HeldResourceObjectTerrainContactGeometryConfig.from_dict(
        data.get("config") if isinstance(data.get("config"), dict) else None
    )
    validate_config(cfg)
    prev_held: dict[str, dict[str, Any]] = {}
    for k, v in (data.get("prev_held_identity") or {}).items():
        if not isinstance(v, dict):
            continue
        prev_held[str(k)] = {
            "holder_body_id": v.get("holder_body_id"),
            "manipulator_id": v.get("manipulator_id"),
            "pose": list(v["pose"]) if isinstance(v.get("pose"), list) else None,
        }
    st = HeldResourceObjectTerrainContactGeometryState(
        config=cfg,
        active={str(k): dict(v) for k, v in (data.get("active") or {}).items()},
        prev_poses={
            str(k): [float(v[0]), float(v[1]), float(v[2]), int(v[3])]
            for k, v in (data.get("prev_poses") or {}).items()
            if isinstance(v, (list, tuple)) and len(v) >= 4
        },
        prev_held_identity=prev_held,
        episode_tick=int(data.get("episode_tick", -1)),
        episode_next=int(data.get("episode_next", 0)),
        counters={
            **_zero_counters(),
            **{a: int(b) for a, b in (data.get("counters") or {}).items()},
        },
        last_step=dict(data["last_step"]) if isinstance(data.get("last_step"), dict) else None,
        history=[dict(r) for r in (data.get("history") or [])],
    )
    world.held_resource_object_terrain_contact_geometry_state = st
    return st


def _alloc_episode(st: HeldResourceObjectTerrainContactGeometryState, tick: int) -> str:
    if int(st.episode_tick) != int(tick):
        st.episode_tick = int(tick)
        st.episode_next = 0
    st.episode_next += 1
    return f"hotc-{int(tick):06d}-{st.episode_next:04d}"


def _transition_policy(
    prev: dict[str, Any] | None,
    *,
    holder_body_id: str,
    manipulator_id: str,
) -> str:
    if not prev or prev.get("pose") is None:
        return TRANSITION_NO_HISTORY
    prev_holder = prev.get("holder_body_id")
    prev_hand = prev.get("manipulator_id")
    if prev_holder is None or prev_hand is None:
        return TRANSITION_GRASP_SNAP
    if str(prev_holder) != str(holder_body_id) or str(prev_hand) != str(manipulator_id):
        return TRANSITION_HOLDER_CHANGED
    return TRANSITION_STABLE_HELD


def _object_centre_pose(obj: Any, config: Any, cfg: HeldResourceObjectTerrainContactGeometryConfig) -> tuple[float, float, float, float]:
    """Return (x, y, centre_z, collision_radius)."""
    ensure_object_collision_radius(obj, cfg.default_object_collision_radius)
    if flat_ground_gravity_is_active(config):
        ensure_object_vertical(obj, config)
    r = float(ensure_object_collision_radius(obj, cfg.default_object_collision_radius))
    x = float(getattr(obj, "x", 0.0) or 0.0)
    y = float(getattr(obj, "y", 0.0) or 0.0)
    cz = float(centre_z_of(obj, kind="object", config=config))
    return x, y, cz, r


def _receipt(
    tick: int,
    phase: str,
    *,
    object_id: str,
    holder_body_id: str,
    manipulator_id: str,
    episode_id: str,
    measure: dict[str, Any],
    cfg: HeldResourceObjectTerrainContactGeometryConfig,
    transition: str | None = None,
    end_reason: str | None = None,
    collision_radius: float | None = None,
) -> dict[str, Any]:
    return {
        "receipt_kind": RECEIPT_KIND,
        "event_kind": f"HELD_RESOURCE_OBJECT_TERRAIN_CONTACT_{phase}",
        "mechanism": MECHANISM_ID,
        "profile_version": PROFILE_VERSION,
        "tick": int(tick),
        "phase": str(phase),
        "episode_id": str(episode_id),
        "object_id": str(object_id),
        "holder_body_id": str(holder_body_id),
        "manipulator_id": str(manipulator_id),
        "contact_fact": bool(phase != PHASE_END),
        "detection_mode": measure.get("detection_mode"),
        "toi": measure.get("toi"),
        "clearance": measure.get("clearance"),
        "penetration": measure.get("penetration"),
        "object_centre_position": [
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
        "collider_geometry": COLLIDER_GEOMETRY,
        "collision_radius": float(
            collision_radius if collision_radius is not None else cfg.default_object_collision_radius
        ),
        "optical_radius_used": False,
        "glyph_geometry_used": False,
        "point_effector_proxy": False,
        "contact_epsilon": float(cfg.contact_epsilon),
        "samples": measure.get("samples"),
        "transition_policy": transition,
        "end_reason": end_reason,
        "researcher_only": True,
        "cognition_exposed": False,
        **RESPONSE_FLAGS,
    }


def detect_held_resource_object_terrain_contacts(
    world: Any,
    holders: list[dict[str, Any]],
    *,
    tick: int,
    config: Any,
) -> dict[str, Any]:
    """One shared-world evaluation of HELD objects vs authoritative terrain.

    Read-only w.r.t. poses/velocities/relative_z/actuator/WMT.
    """
    st = ensure_held_resource_object_terrain_contact_geometry_for_runtime(world, config)
    if st is None:
        return {"active": False, "receipts": []}

    from mechanistic_mind.physical_system.effector_terrain_contact_geometry import (
        evaluate_probe_contact,
    )

    cfg = st.config
    te = int(tick)
    holder_ids = {str(r.get("body_id") or "") for r in holders if r.get("body_id")}
    objs = list(getattr(world, "resource_objects", None) or [])
    # Canonical object-ID order
    objs_sorted = sorted(objs, key=lambda o: str(getattr(o, "object_id", "") or ""))

    measures: list[tuple[str, str, str, dict[str, Any], float, str]] = []
    seen_oids: set[str] = set()
    st.invalid_holder_diagnostics = []

    for obj in objs_sorted:
        if str(getattr(obj, "physical_state", "")) != PHYSICAL_STATE_HELD:
            continue
        oid = str(getattr(obj, "object_id", "") or "")
        if not oid:
            continue
        seen_oids.add(oid)
        hid = str(getattr(obj, "holder_body_id", "") or "")
        mid = str(getattr(obj, "manipulator_id", "") or "")
        if not hid or hid not in holder_ids:
            st.counters["invalid_holder"] = int(st.counters.get("invalid_holder", 0)) + 1
            st.invalid_holder_diagnostics.append(
                {
                    "object_id": oid,
                    "holder_body_id": hid or None,
                    "reason": "INVALID_OR_MISSING_HOLDER",
                    "tick": te,
                    "researcher_only": True,
                }
            )
            continue
        if not mid:
            st.counters["invalid_holder"] = int(st.counters.get("invalid_holder", 0)) + 1
            st.invalid_holder_diagnostics.append(
                {
                    "object_id": oid,
                    "holder_body_id": hid,
                    "reason": "MISSING_MANIPULATOR_ID",
                    "tick": te,
                    "researcher_only": True,
                }
            )
            continue

        x, y, cz, radius = _object_centre_pose(obj, config, cfg)
        prev_id = st.prev_held_identity.get(oid)
        policy = _transition_policy(prev_id, holder_body_id=hid, manipulator_id=mid)
        allow_swept = policy == TRANSITION_STABLE_HELD
        prev = None
        if allow_swept:
            prev_raw = st.prev_poses.get(oid)
            if prev_raw is not None and len(prev_raw) >= 4:
                if int(prev_raw[3]) == te - 1 or int(prev_raw[3]) == te:
                    prev = (float(prev_raw[0]), float(prev_raw[1]), float(prev_raw[2]))
        else:
            st.counters["grasp_snap_endpoint_only"] = int(
                st.counters.get("grasp_snap_endpoint_only", 0)
            ) + 1

        m = evaluate_probe_contact(
            world,
            x=x,
            y=y,
            z=cz,
            radius=float(radius),
            epsilon=float(cfg.contact_epsilon),
            config=config,
            prev=prev,
            sweep_step=float(cfg.sweep_step),
            sweep_max_samples=int(cfg.sweep_max_samples),
        )
        st.counters["queries"] = int(st.counters.get("queries", 0)) + 1
        measures.append((oid, hid, mid, m, float(radius), policy))
        st.prev_poses[oid] = [float(x), float(y), float(cz), te]

    def _sort_key(item: tuple) -> tuple:
        oid, hid, mid, m, _r, _p = item
        toi = m.get("toi")
        toi_v = float(toi) if toi is not None else 2.0
        return (0 if m.get("in_contact") else 1, toi_v, oid, hid, mid)

    measures.sort(key=_sort_key)

    receipts: list[dict[str, Any]] = []
    still_active: set[str] = set()

    for oid, hid, mid, m, radius, policy in measures:
        if not m.get("in_contact"):
            continue
        still_active.add(oid)
        if oid in st.active:
            ep = st.active[oid]
            # Manipulator/holder change while in contact → end old + begin new
            if str(ep.get("holder_body_id")) != hid or str(ep.get("manipulator_id")) != mid:
                end_rec = _receipt(
                    te,
                    PHASE_END,
                    object_id=oid,
                    holder_body_id=str(ep.get("holder_body_id") or hid),
                    manipulator_id=str(ep.get("manipulator_id") or mid),
                    episode_id=str(ep["episode_id"]),
                    measure=m,
                    cfg=cfg,
                    end_reason=END_MANIPULATOR_CHANGED,
                    collision_radius=radius,
                )
                receipts.append(end_rec)
                st.counters["end"] = int(st.counters.get("end", 0)) + 1
                eid = _alloc_episode(st, te)
                st.active[oid] = {
                    "episode_id": eid,
                    "object_id": oid,
                    "holder_body_id": hid,
                    "manipulator_id": mid,
                    "begin_tick": te,
                    "last_tick": te,
                    "detection_mode": m.get("detection_mode"),
                }
                st.counters["begin"] = int(st.counters.get("begin", 0)) + 1
                receipts.append(
                    _receipt(
                        te,
                        PHASE_BEGIN,
                        object_id=oid,
                        holder_body_id=hid,
                        manipulator_id=mid,
                        episode_id=eid,
                        measure=m,
                        cfg=cfg,
                        transition=policy,
                        collision_radius=radius,
                    )
                )
            else:
                ep["last_tick"] = te
                ep["detection_mode"] = m.get("detection_mode")
                st.counters["persist"] = int(st.counters.get("persist", 0)) + 1
                receipts.append(
                    _receipt(
                        te,
                        PHASE_PERSIST,
                        object_id=oid,
                        holder_body_id=hid,
                        manipulator_id=mid,
                        episode_id=str(ep["episode_id"]),
                        measure=m,
                        cfg=cfg,
                        transition=policy,
                        collision_radius=radius,
                    )
                )
        else:
            eid = _alloc_episode(st, te)
            st.active[oid] = {
                "episode_id": eid,
                "object_id": oid,
                "holder_body_id": hid,
                "manipulator_id": mid,
                "begin_tick": te,
                "last_tick": te,
                "detection_mode": m.get("detection_mode"),
            }
            st.counters["begin"] = int(st.counters.get("begin", 0)) + 1
            if m.get("detection_mode") == DETECTION_SWEPT:
                st.counters["swept_hits"] = int(st.counters.get("swept_hits", 0)) + 1
            else:
                st.counters["endpoint_hits"] = int(st.counters.get("endpoint_hits", 0)) + 1
            receipts.append(
                _receipt(
                    te,
                    PHASE_BEGIN,
                    object_id=oid,
                    holder_body_id=hid,
                    manipulator_id=mid,
                    episode_id=eid,
                    measure=m,
                    cfg=cfg,
                    transition=policy,
                    collision_radius=radius,
                )
            )

    # ENDs
    for oid in sorted(list(st.active.keys())):
        if oid in still_active:
            continue
        ep = st.active.pop(oid)
        # Classify end reason
        obj = next(
            (o for o in objs if str(getattr(o, "object_id", "")) == oid),
            None,
        )
        if obj is None:
            reason = END_OBJECT_REMOVED
        elif str(getattr(obj, "physical_state", "")) != PHYSICAL_STATE_HELD:
            reason = END_OBJECT_RELEASED
        elif str(getattr(obj, "holder_body_id", "") or "") not in holder_ids:
            reason = END_HOLDER_REMOVED
        else:
            reason = END_GEOMETRIC_SEPARATION
        empty_m = {
            "detection_mode": None,
            "toi": None,
            "clearance": None,
            "penetration": None,
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
        receipts.append(
            _receipt(
                te,
                PHASE_END,
                object_id=oid,
                holder_body_id=str(ep.get("holder_body_id") or ""),
                manipulator_id=str(ep.get("manipulator_id") or ""),
                episode_id=str(ep["episode_id"]),
                measure=empty_m,
                cfg=cfg,
                end_reason=reason,
            )
        )
        st.counters["end"] = int(st.counters.get("end", 0)) + 1
        st.prev_poses.pop(oid, None)

    # Refresh prev_held_identity for next tick (HELD only)
    new_prev: dict[str, dict[str, Any]] = {}
    for obj in objs_sorted:
        if str(getattr(obj, "physical_state", "")) != PHYSICAL_STATE_HELD:
            continue
        oid = str(getattr(obj, "object_id", "") or "")
        if not oid:
            continue
        x, y, cz, _r = _object_centre_pose(obj, config, cfg)
        new_prev[oid] = {
            "holder_body_id": str(getattr(obj, "holder_body_id", "") or "") or None,
            "manipulator_id": str(getattr(obj, "manipulator_id", "") or "") or None,
            "pose": [float(x), float(y), float(cz)],
        }
    st.prev_held_identity = new_prev

    step = {
        "active": True,
        "tick": te,
        "receipts": receipts,
        "n_begin": sum(1 for r in receipts if r["phase"] == PHASE_BEGIN),
        "n_persist": sum(1 for r in receipts if r["phase"] == PHASE_PERSIST),
        "n_end": sum(1 for r in receipts if r["phase"] == PHASE_END),
        "banner": BANNER,
        "researcher_only": True,
        "invalid_holder_diagnostics": list(st.invalid_holder_diagnostics),
        **{k: False for k in (
            "work_transmission",
            "material_failure",
            "wmt_invoked",
            "impulse_transferred",
            "sound_emitted",
            "automatic_release",
        )},
    }
    st.last_step = step
    st.history.append(
        {
            "tick": te,
            "n_begin": step["n_begin"],
            "n_persist": step["n_persist"],
            "n_end": step["n_end"],
            "n_receipts": len(receipts),
        }
    )
    lim = int(cfg.history_limit)
    if len(st.history) > lim:
        st.history = st.history[-lim:]
    world.last_held_resource_object_terrain_contact_step = step
    return step


def researcher_summary(world: Any) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    step = st.last_step or {}
    latest = None
    for r in reversed(list(step.get("receipts") or [])):
        if isinstance(r, dict):
            latest = r
            break
    return {
        "mechanism": MECHANISM_ID,
        "profile_version": PROFILE_VERSION,
        "banner": BANNER,
        "active_episodes": [
            {
                "episode_id": v.get("episode_id"),
                "object_id": v.get("object_id"),
                "holder_body_id": v.get("holder_body_id"),
                "manipulator_id": v.get("manipulator_id"),
                "detection_mode": v.get("detection_mode"),
                "begin_tick": v.get("begin_tick"),
                "last_tick": v.get("last_tick"),
                "status": PHASE_PERSIST,
            }
            for _, v in sorted(st.active.items())
        ],
        "latest_receipt": latest,
        "last_step": {
            "tick": step.get("tick"),
            "begin_count": step.get("n_begin"),
            "persist_count": step.get("n_persist"),
            "end_count": step.get("n_end"),
        },
        "counters": dict(st.counters),
        "collider_geometry": COLLIDER_GEOMETRY,
        "z_authority": Z_AUTHORITY,
        "terrain_source": "continuous_surface_geometry_or_surface_support_height",
        "work_transmission": False,
        "material_failure": False,
        "impulse_transferred": False,
        "sound_emitted": False,
        "automatic_release": False,
        "wmt_invoked": False,
        "agent_accessible": False,
        "researcher_only": True,
        "penetration_unresolved": True,
        "limitation": (
            "Geometry fact only; held kinematics do not yet resolve terrain penetration."
        ),
    }


def overlay_payload(world: Any) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    step = st.last_step or {}
    contacts = []
    for r in step.get("receipts") or []:
        if not isinstance(r, dict):
            continue
        if r.get("phase") == PHASE_END and not r.get("contact_point"):
            contacts.append(
                {
                    "phase": PHASE_END,
                    "episode_id": r.get("episode_id"),
                    "object_id": r.get("object_id"),
                    "holder_body_id": r.get("holder_body_id"),
                    "manipulator_id": r.get("manipulator_id"),
                    "end_reason": r.get("end_reason"),
                }
            )
            continue
        contacts.append(
            {
                "phase": r.get("phase"),
                "episode_id": r.get("episode_id"),
                "object_id": r.get("object_id"),
                "holder_body_id": r.get("holder_body_id"),
                "manipulator_id": r.get("manipulator_id"),
                "detection_mode": r.get("detection_mode"),
                "toi": r.get("toi"),
                "contact_point": r.get("contact_point"),
                "normal": r.get("normal"),
                "object_centre_position": r.get("object_centre_position"),
                "collision_radius": r.get("collision_radius"),
                "clearance": r.get("clearance"),
                "terrain_cell": r.get("terrain_cell"),
                "end_reason": r.get("end_reason"),
            }
        )
    held = []
    for obj in list(getattr(world, "resource_objects", None) or []):
        if str(getattr(obj, "physical_state", "")) != PHYSICAL_STATE_HELD:
            continue
        held.append(
            {
                "object_id": str(obj.object_id),
                "x": float(obj.x),
                "y": float(obj.y),
                "z": float(getattr(obj, "z", 0.0) or 0.0),
                "collision_radius": float(ensure_object_collision_radius(obj)),
                "holder_body_id": (
                    str(obj.holder_body_id) if getattr(obj, "holder_body_id", None) else None
                ),
                "manipulator_id": (
                    str(obj.manipulator_id) if getattr(obj, "manipulator_id", None) else None
                ),
            }
        )
    return {
        "caption": BANNER,
        "held_objects": held,
        "contacts": contacts,
        "active": researcher_summary(world),
        "visually_distinct_from_effector_terrain": True,
        "researcher_only": True,
    }
