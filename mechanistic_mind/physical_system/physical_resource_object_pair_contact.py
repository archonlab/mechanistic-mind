"""Acanthostega FREE ResourceObject ↔ ResourceObject contact FACT (measurement only).

Preset: ACANTHOSTEGA_PHASE_B_OBJECT_OBJECT_CONTACT
Mechanism: physical_resource_object_pair_contact

Measured FREE_STATIC + FREE_MOVING pair contact only. No impulse, position correction,
velocity change, sound, or composition. Objects may still pass through each other.
HELD+HELD left to evaluate_held_object_contact / BRING_TOGETHER.
HELD+FREE = HELD_FREE_OBJECT_PAIR_CONTACT = NOT_IMPLEMENTED (diagnostic skip).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from mechanistic_mind.physical_system.physical_body_resource_object_contact import (
    CANONICAL_COLLISION_RADIUS,
    CONTACT_EPSILON,
    closest_approach_segment,
    ensure_object_collision_radius,
    object_contact_geometry,
    shortest_toroidal_delta,
)

MECHANISM_ID = "physical_resource_object_pair_contact"
PROFILE_VERSION = "RESOURCE_OBJECT_PAIR_CONTACT_PROFILE_V1"
STATE_SCHEMA = "RESOURCE_OBJECT_PAIR_CONTACT_STATE_V1"
RECEIPT_KIND = "RESOURCE_OBJECT_PAIR_CONTACT"
EVENT_STEP = "RESOURCE_OBJECT_PAIR_CONTACT_STEP"

DETECTION_ENDPOINT = "ENDPOINT_OVERLAP"
DETECTION_SWEPT = "SWEPT_CROSSING"
PHASE_BEGIN = "BEGIN"
PHASE_PERSIST = "PERSIST"
PHASE_END = "END"

HELD_FREE_OBJECT_PAIR_CONTACT = "NOT_IMPLEMENTED"
SWEPT_CONTACT = "IMPLEMENTED"
BROAD_PHASE_STRATEGY = "BROAD_PHASE_ALL_PAIRS_V1"
BROAD_PHASE_SOFT_CAP = 256  # warn/count if N*(N-1)/2 exceeds; still compute all
BROAD_PHASE_HARD_CAP = 20000  # fail closed with diagnostic rather than silent miss

PHYSICAL_STATE_FREE_STATIC = "FREE_STATIC"
PHYSICAL_STATE_FREE_MOVING = "FREE_MOVING"
PHYSICAL_STATE_HELD = "HELD"
FREE_STATES = (PHYSICAL_STATE_FREE_STATIC, PHYSICAL_STATE_FREE_MOVING)

TERMINATION_SEPARATION = "SEPARATION"
TERMINATION_OBJECT_REMOVED = "OBJECT_REMOVED"
TERMINATION_COMBINE_REMOVED = "COMBINE_REMOVED"
TERMINATION_STATE_EXCLUSION_HELD = "STATE_EXCLUSION_HELD"

RESPONSE_FLAGS = {
    "contact_fact": True,
    "collision_response_applied": False,
    "impulse_transferred": False,
    "position_corrected": False,
    "velocity_changed": False,
    "sound_emitted": False,
    "composition_changed": False,
}


@dataclass
class ResourceObjectPairContactConfig:
    enabled: bool = False
    default_object_collision_radius: float = CANONICAL_COLLISION_RADIUS
    contact_epsilon: float = CONTACT_EPSILON
    broad_phase_soft_cap: int = BROAD_PHASE_SOFT_CAP
    broad_phase_hard_cap: int = BROAD_PHASE_HARD_CAP
    history_limit: int = 64

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "default_object_collision_radius": float(self.default_object_collision_radius),
            "contact_epsilon": float(self.contact_epsilon),
            "broad_phase_soft_cap": int(self.broad_phase_soft_cap),
            "broad_phase_hard_cap": int(self.broad_phase_hard_cap),
            "broad_phase_strategy": BROAD_PHASE_STRATEGY,
            "history_limit": int(self.history_limit),
            "profile_version": PROFILE_VERSION,
            "held_free_object_pair_contact": HELD_FREE_OBJECT_PAIR_CONTACT,
            "swept_contact": SWEPT_CONTACT,
            "response": dict(RESPONSE_FLAGS),
            "complexity": "O(N^2)",
            "next_scaling_seam": "swept_cell_coverage_or_spatial_hash_NOT_IMPLEMENTED",
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ResourceObjectPairContactConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        ver = data.get("profile_version")
        if ver is not None and str(ver) != PROFILE_VERSION:
            raise ValueError(f"unknown resource object pair contact profile: {ver}")
        return cls(
            enabled=bool(data.get("enabled", False)),
            default_object_collision_radius=float(
                data.get("default_object_collision_radius", CANONICAL_COLLISION_RADIUS)
            ),
            contact_epsilon=float(data.get("contact_epsilon", CONTACT_EPSILON)),
            broad_phase_soft_cap=int(data.get("broad_phase_soft_cap", BROAD_PHASE_SOFT_CAP)),
            broad_phase_hard_cap=int(data.get("broad_phase_hard_cap", BROAD_PHASE_HARD_CAP)),
            history_limit=int(data.get("history_limit", 64)),
        )


def resource_object_pair_contact_is_active(config: Any) -> bool:
    cfg = getattr(config, "physical_resource_object_pair_contact", None)
    return bool(cfg is not None and getattr(cfg, "enabled", False))


def set_resource_object_pair_contact(config: Any, enabled: bool) -> None:
    on = bool(enabled)
    cur = getattr(config, "physical_resource_object_pair_contact", None)
    if cur is None:
        config.physical_resource_object_pair_contact = ResourceObjectPairContactConfig(enabled=on)
    else:
        cur.enabled = on


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "config_path": "physical_resource_object_pair_contact.enabled",
        "enabled": bool(enabled),
        "description": (
            "Acanthostega researcher-only FREE ResourceObject↔ResourceObject contact FACT "
            "(endpoint + swept; all-pairs broad phase). No impulse/response/sound."
        ),
        "agent_accessible": False,
        "collision_response": False,
    }


def _norm(dx: float, dy: float) -> float:
    return float(math.hypot(dx, dy))


def canonical_pair_key(oid_a: str, oid_b: str) -> str:
    a, b = str(oid_a), str(oid_b)
    lo, hi = (a, b) if a <= b else (b, a)
    return f"{lo}|{hi}"


@dataclass
class ResourceObjectPairContactState:
    config: ResourceObjectPairContactConfig
    active: dict[str, dict[str, Any]] = field(default_factory=dict)
    prev_object_poses: dict[str, list[float]] = field(default_factory=dict)
    episode_tick: int = -1
    episode_next: int = 0
    last_processed_tick: int = -1
    last_step: dict[str, Any] | None = None
    history: list[dict[str, Any]] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=dict)


def _zero_counters() -> dict[str, int]:
    return {
        "begin": 0,
        "persist": 0,
        "end": 0,
        "endpoint": 0,
        "swept": 0,
        "broad_candidates": 0,
        "narrow_checks": 0,
        "skipped_held_held": 0,
        "skipped_held_free": 0,
        "broad_phase_soft_cap_warnings": 0,
        "broad_phase_hard_cap_failures": 0,
        "unique_pairs_checked": 0,
        "duplicate_pair_checks_prevented": 0,
        "end_object_removed": 0,
        "end_combine_removed": 0,
        "end_state_exclusion_held": 0,
        "end_separation": 0,
    }


def state_of(world: Any) -> ResourceObjectPairContactState | None:
    raw = getattr(world, "resource_object_pair_contact_state", None)
    return raw if isinstance(raw, ResourceObjectPairContactState) else None


def ensure_resource_object_pair_contact_for_runtime(
    world: Any, config: Any
) -> ResourceObjectPairContactState | None:
    if not resource_object_pair_contact_is_active(config):
        world.resource_object_pair_contact_state = None
        return None
    cfg = getattr(config, "physical_resource_object_pair_contact", None) or ResourceObjectPairContactConfig(
        enabled=True
    )
    st = state_of(world)
    if st is None:
        st = ResourceObjectPairContactState(config=cfg, counters=_zero_counters())
        world.resource_object_pair_contact_state = st
    else:
        st.config = cfg
    for obj in list(getattr(world, "resource_objects", None) or []):
        ensure_object_collision_radius(obj, cfg.default_object_collision_radius)
    return st


def copy_state(st: ResourceObjectPairContactState | None) -> ResourceObjectPairContactState | None:
    if st is None:
        return None
    return ResourceObjectPairContactState(
        config=ResourceObjectPairContactConfig.from_dict(st.config.to_dict()),
        active={k: dict(v) for k, v in st.active.items()},
        prev_object_poses={k: list(v) for k, v in st.prev_object_poses.items()},
        episode_tick=int(st.episode_tick),
        episode_next=int(st.episode_next),
        last_processed_tick=int(st.last_processed_tick),
        last_step=dict(st.last_step) if st.last_step else None,
        history=[dict(h) for h in st.history],
        counters=dict(st.counters),
    )


def serialize_state(st: ResourceObjectPairContactState | None) -> dict[str, Any] | None:
    if st is None:
        return None
    return {
        "schema_version": STATE_SCHEMA,
        "config": st.config.to_dict(),
        "active": {k: dict(v) for k, v in sorted(st.active.items())},
        "prev_object_poses": {
            k: [float(v[0]), float(v[1])] for k, v in sorted(st.prev_object_poses.items())
        },
        "episode_allocator": {"tick": int(st.episode_tick), "next_sequence": int(st.episode_next)},
        "last_processed_tick": int(st.last_processed_tick),
        "counters": dict(st.counters),
        "history": list(st.history)[-int(st.config.history_limit) :],
    }


def restore_state(
    world: Any, data: dict[str, Any] | None, config: Any
) -> ResourceObjectPairContactState | None:
    if not resource_object_pair_contact_is_active(config):
        world.resource_object_pair_contact_state = None
        return None
    if not isinstance(data, dict) or not data:
        return ensure_resource_object_pair_contact_for_runtime(world, config)
    if str(data.get("schema_version")) != STATE_SCHEMA:
        raise ValueError(
            f"unknown resource object pair contact state schema: {data.get('schema_version')}"
        )
    cfg = ResourceObjectPairContactConfig.from_dict(data.get("config"))
    cfg.enabled = True
    alloc = data.get("episode_allocator") or {}
    st = ResourceObjectPairContactState(
        config=cfg,
        active={str(k): dict(v) for k, v in (data.get("active") or {}).items()},
        prev_object_poses={
            str(k): [float(v[0]), float(v[1])]
            for k, v in (data.get("prev_object_poses") or {}).items()
        },
        episode_tick=int(alloc.get("tick", -1)),
        episode_next=int(alloc.get("next_sequence", 0)),
        last_processed_tick=int(data.get("last_processed_tick", -1)),
        history=list(data.get("history") or []),
        counters={**_zero_counters(), **{k: int(v) for k, v in (data.get("counters") or {}).items()}},
    )
    world.resource_object_pair_contact_state = st
    config.physical_resource_object_pair_contact = cfg
    for obj in list(getattr(world, "resource_objects", None) or []):
        ensure_object_collision_radius(obj, cfg.default_object_collision_radius)
    return st


def _alloc_episode(st: ResourceObjectPairContactState, tick: int) -> str:
    if int(st.episode_tick) != int(tick):
        st.episode_tick = int(tick)
        st.episode_next = 0
    st.episode_next += 1
    return f"oopc-{int(tick):06d}-{st.episode_next:04d}"


def measure_pair(
    *,
    obj_a: Any,
    obj_b: Any,
    width: int,
    height: int,
    cfg: ResourceObjectPairContactConfig,
    prev_a: list[float] | None,
    prev_b: list[float] | None,
    allow_swept: bool,
) -> dict[str, Any]:
    ra = ensure_object_collision_radius(obj_a, cfg.default_object_collision_radius)
    rb = ensure_object_collision_radius(obj_b, cfg.default_object_collision_radius)
    sum_r = ra + rb
    ax, ay = float(obj_a.x), float(obj_a.y)
    bx, by = float(obj_b.x), float(obj_b.y)
    dx, dy = shortest_toroidal_delta(ax, ay, bx, by, width, height)
    endpoint_dist = _norm(dx, dy)
    separation = endpoint_dist - sum_r
    endpoint_contact = separation <= float(cfg.contact_epsilon)
    penetration = max(0.0, -separation)

    detection = DETECTION_ENDPOINT if endpoint_contact else None
    closest_swept = endpoint_dist
    contact_fraction = 1.0 if endpoint_contact else None
    swept_contact = False
    contact_point: list[float] | None = None
    contact_point_policy = "LINE_OF_CENTRES_BY_RADII"

    if allow_swept and prev_a is not None and prev_b is not None:
        # Relative: B wrt A in unwrapped frame ending at (dx, dy)
        rel0x, rel0y = shortest_toroidal_delta(
            float(prev_a[0]), float(prev_a[1]), float(prev_b[0]), float(prev_b[1]), width, height
        )
        rel1x, rel1y = dx, dy
        t_star, closest_swept, _ = closest_approach_segment(rel0x, rel0y, rel1x, rel1y)
        if closest_swept <= sum_r + float(cfg.contact_epsilon):
            swept_contact = True
            if not endpoint_contact:
                detection = DETECTION_SWEPT
                contact_fraction = float(t_star)
                # TOI poses then surface point along relative vector at t*
                tox = rel0x + float(t_star) * (rel1x - rel0x)
                toy = rel0y + float(t_star) * (rel1y - rel0y)
                toi_dist = _norm(tox, toy)
                adx, ady = shortest_toroidal_delta(
                    float(prev_a[0]), float(prev_a[1]), ax, ay, width, height
                )
                a_toi_x = (float(prev_a[0]) + float(t_star) * adx) % width
                a_toi_y = (float(prev_a[1]) + float(t_star) * ady) % height
                if toi_dist < 1e-12:
                    nx, ny = 1.0, 0.0
                    contact_point = [a_toi_x + ra * nx, a_toi_y + ra * ny]
                    contact_point_policy = "SWEPT_TOI_COINCIDENT_CENTRES_PLUS_X"
                else:
                    nx, ny = tox / toi_dist, toy / toi_dist
                    contact_point = [a_toi_x + nx * ra, a_toi_y + ny * ra]
                    contact_point_policy = "SWEPT_TOI_SURFACE_POINT"
                contact_point = [contact_point[0] % width, contact_point[1] % height]
            else:
                detection = DETECTION_ENDPOINT
                contact_fraction = 1.0

    in_contact = bool(endpoint_contact or swept_contact)

    if contact_point is None:
        if endpoint_dist < 1e-12:
            nx, ny = 1.0, 0.0
            contact_point = [ax + ra * nx, ay + ra * ny]
            contact_point_policy = "COINCIDENT_CENTRES_PLUS_X"
        else:
            nx, ny = dx / endpoint_dist, dy / endpoint_dist
            contact_point = [ax + nx * ra, ay + ny * ra]
            contact_point_policy = "LINE_OF_CENTRES_BY_RADII"
        contact_point = [contact_point[0] % width, contact_point[1] % height]

    return {
        "in_contact": in_contact,
        "endpoint_contact": bool(endpoint_contact),
        "swept_contact": bool(swept_contact),
        "detection_mode": detection,
        "endpoint_distance": float(endpoint_dist),
        "closest_swept_distance": float(closest_swept),
        "contact_fraction": contact_fraction,
        "separation": float(separation),
        "penetration": float(penetration),
        "displacement": [float(dx), float(dy)],
        "object_a_pose": [ax, ay],
        "object_b_pose": [bx, by],
        "object_a_start_pose": list(prev_a) if prev_a else [ax, ay],
        "object_b_start_pose": list(prev_b) if prev_b else [bx, by],
        "object_a_geometry": object_contact_geometry(obj_a, default_radius=cfg.default_object_collision_radius),
        "object_b_geometry": object_contact_geometry(obj_b, default_radius=cfg.default_object_collision_radius),
        "combined_radius": float(sum_r),
        "contact_point": contact_point,
        "contact_point_policy": contact_point_policy,
        "object_a_physical_state": str(getattr(obj_a, "physical_state", "")),
        "object_b_physical_state": str(getattr(obj_b, "physical_state", "")),
    }


def _free_objects_sorted(objects: list[Any]) -> list[Any]:
    free = [
        o
        for o in objects
        if str(getattr(o, "physical_state", "")) in FREE_STATES
        and not bool(getattr(o, "removed", False))
        and str(getattr(o, "object_id", ""))
    ]
    free.sort(key=lambda o: str(o.object_id))
    return free


def _all_pairs_candidates(
    free_objs: list[Any],
    *,
    soft_cap: int,
    hard_cap: int,
    counters: dict[str, int],
) -> list[tuple[Any, Any]] | None:
    """BROAD_PHASE_ALL_PAIRS_V1: deterministic sorted pairs; no false-negative prune."""
    n = len(free_objs)
    n_pairs = n * (n - 1) // 2
    if n_pairs > int(hard_cap):
        counters["broad_phase_hard_cap_failures"] = int(
            counters.get("broad_phase_hard_cap_failures", 0)
        ) + 1
        return None  # fail closed
    if n_pairs > int(soft_cap):
        counters["broad_phase_soft_cap_warnings"] = int(
            counters.get("broad_phase_soft_cap_warnings", 0)
        ) + 1
    out: list[tuple[Any, Any]] = []
    for i in range(n):
        for j in range(i + 1, n):
            out.append((free_objs[i], free_objs[j]))
    return out


def detect_resource_object_pair_contacts(
    world: Any,
    *,
    tick: int,
    config: Any,
) -> dict[str, Any] | None:
    """One shared-world FREE object↔object contact FACT phase. Read-only w.r.t. poses/velocities."""
    if not resource_object_pair_contact_is_active(config):
        return None
    st = ensure_resource_object_pair_contact_for_runtime(world, config)
    if st is None:
        return None
    te = int(tick)
    if te <= int(st.last_processed_tick):
        return st.last_step
    cfg = st.config
    height, width = int(world.T.shape[0]), int(world.T.shape[1])
    objects = list(getattr(world, "resource_objects", None) or [])
    by_oid = {str(o.object_id): o for o in objects if getattr(o, "object_id", None) is not None}

    # Diagnostics: HELD+HELD left alone; HELD+FREE skipped (NOT_IMPLEMENTED)
    held = [o for o in objects if str(getattr(o, "physical_state", "")) == PHYSICAL_STATE_HELD]
    free_objs = _free_objects_sorted(objects)
    try:
        from mechanistic_mind.physical_system.detached_terrain_material_initial_placement import (
            object_dynamics_eligible,
        )

        free_objs = [o for o in free_objs if object_dynamics_eligible(o, int(tick))]
    except Exception:
        pass
    # Count HELD+HELD pairs (not processed)
    nh = len(held)
    if nh >= 2:
        st.counters["skipped_held_held"] = int(st.counters.get("skipped_held_held", 0)) + (
            nh * (nh - 1) // 2
        )
    # Count HELD+FREE pairs (diagnostic skip)
    if held and free_objs:
        st.counters["skipped_held_free"] = int(st.counters.get("skipped_held_free", 0)) + (
            len(held) * len(free_objs)
        )

    candidates = _all_pairs_candidates(
        free_objs,
        soft_cap=int(cfg.broad_phase_soft_cap),
        hard_cap=int(cfg.broad_phase_hard_cap),
        counters=st.counters,
    )
    if candidates is None:
        step = {
            "event": EVENT_STEP,
            "tick": te,
            "mechanism": MECHANISM_ID,
            "broad_phase_strategy": BROAD_PHASE_STRATEGY,
            "broad_phase_failed_closed": True,
            "broad_phase_hard_cap": int(cfg.broad_phase_hard_cap),
            "free_object_count": len(free_objs),
            "begin": [],
            "persist": [],
            "end": [],
            "active_episodes": len(st.active),
            "held_free_object_pair_contact": HELD_FREE_OBJECT_PAIR_CONTACT,
            "swept_contact": SWEPT_CONTACT,
            "collision_response_applied": False,
            "impulse_transferred": False,
            "position_corrected": False,
            "velocity_changed": False,
            "sound_emitted": False,
            "composition_changed": False,
            "agent_accessible": False,
            "researcher_only": True,
        }
        st.last_step = step
        world.last_resource_object_pair_contact_step = step
        st.last_processed_tick = te
        return step

    # Always include currently active FREE pairs (avoid false END if object still free)
    seen = {(str(a.object_id), str(b.object_id)) for a, b in candidates}
    for pk, ep in list(st.active.items()):
        oa = str(ep.get("object_id_a"))
        ob = str(ep.get("object_id_b"))
        key = (oa, ob) if oa <= ob else (ob, oa)
        if key in seen:
            continue
        if oa in by_oid and ob in by_oid:
            psa = str(getattr(by_oid[oa], "physical_state", ""))
            psb = str(getattr(by_oid[ob], "physical_state", ""))
            if psa in FREE_STATES and psb in FREE_STATES:
                a_obj, b_obj = by_oid[oa], by_oid[ob]
                if oa <= ob:
                    candidates.append((a_obj, b_obj))
                else:
                    candidates.append((b_obj, a_obj))
                seen.add(key)
    candidates.sort(key=lambda t: (str(t[0].object_id), str(t[1].object_id)))
    st.counters["broad_candidates"] = int(st.counters.get("broad_candidates", 0)) + len(candidates)
    st.counters["unique_pairs_checked"] = int(st.counters.get("unique_pairs_checked", 0)) + len(
        candidates
    )

    current_keys: set[str] = set()
    begin_receipts: list[dict[str, Any]] = []
    persist_rows: list[dict[str, Any]] = []
    end_receipts: list[dict[str, Any]] = []
    checked: set[str] = set()

    for obj_a, obj_b in candidates:
        oid_a, oid_b = str(obj_a.object_id), str(obj_b.object_id)
        pk = canonical_pair_key(oid_a, oid_b)
        if pk in checked:
            st.counters["duplicate_pair_checks_prevented"] = int(
                st.counters.get("duplicate_pair_checks_prevented", 0)
            ) + 1
            continue
        checked.add(pk)
        st.counters["narrow_checks"] = int(st.counters.get("narrow_checks", 0)) + 1
        prev_a = st.prev_object_poses.get(oid_a)
        prev_b = st.prev_object_poses.get(oid_b)
        # Active: endpoint-only (anti-t=0 trap). New: endpoint OR swept. Newly released: endpoint only.
        is_active = pk in st.active
        allow_swept = (not is_active) and (prev_a is not None) and (prev_b is not None)
        m = measure_pair(
            obj_a=obj_a,
            obj_b=obj_b,
            width=width,
            height=height,
            cfg=cfg,
            prev_a=prev_a,
            prev_b=prev_b,
            allow_swept=allow_swept,
        )
        m["object_id_a"] = min(oid_a, oid_b)
        m["object_id_b"] = max(oid_a, oid_b)
        m["pair_key"] = pk
        m["broad_phase_candidate"] = True
        m["broad_phase_strategy"] = BROAD_PHASE_STRATEGY
        from mechanistic_mind.physical_system.flat_ground_gravity import (
            apply_vertical_filter_to_measurement,
        )
        apply_vertical_filter_to_measurement(
            world, config, m,
            a=obj_a, b=obj_b, kind_a="object", kind_b="object",
            a_prev=prev_a, b_prev=prev_b,
        )
        if is_active:
            m["in_contact"] = bool(m.get("endpoint_contact")) and bool(m.get("in_contact"))
            if m["in_contact"]:
                m["detection_mode"] = DETECTION_ENDPOINT
        if not m["in_contact"]:
            continue
        current_keys.add(pk)
        if m["detection_mode"] == DETECTION_SWEPT:
            st.counters["swept"] = int(st.counters.get("swept", 0)) + 1
        else:
            st.counters["endpoint"] = int(st.counters.get("endpoint", 0)) + 1

        if pk not in st.active:
            eid = _alloc_episode(st, te)
            phase = PHASE_BEGIN
            lo, hi = (oid_a, oid_b) if oid_a <= oid_b else (oid_b, oid_a)
            st.active[pk] = {
                "episode_id": eid,
                "object_id_a": lo,
                "object_id_b": hi,
                "begin_tick": int(te),
                "last_tick": int(te),
                "detection_mode": m["detection_mode"],
            }
            st.counters["begin"] = int(st.counters.get("begin", 0)) + 1
            receipt = _receipt(te, phase, st.active[pk], m, cfg)
            begin_receipts.append(receipt)
        else:
            ep = st.active[pk]
            ep["last_tick"] = int(te)
            ep["detection_mode"] = m["detection_mode"]
            phase = PHASE_PERSIST
            st.counters["persist"] = int(st.counters.get("persist", 0)) + 1
            persist_rows.append(_receipt(te, phase, ep, m, cfg))

    # ENDs — classify termination
    for pk in sorted(set(st.active) - current_keys):
        ep = st.active.pop(pk)
        oid_a = str(ep["object_id_a"])
        oid_b = str(ep["object_id_b"])
        obj_a = by_oid.get(oid_a)
        obj_b = by_oid.get(oid_b)
        term = TERMINATION_SEPARATION
        if obj_a is None or obj_b is None:
            # COMBINE typically removes one object from the world list
            term = TERMINATION_COMBINE_REMOVED if (
                (obj_a is None and obj_b is not None) or (obj_b is None and obj_a is not None)
            ) else TERMINATION_OBJECT_REMOVED
            if term == TERMINATION_COMBINE_REMOVED:
                st.counters["end_combine_removed"] = int(st.counters.get("end_combine_removed", 0)) + 1
            else:
                st.counters["end_object_removed"] = int(st.counters.get("end_object_removed", 0)) + 1
        else:
            psa = str(getattr(obj_a, "physical_state", ""))
            psb = str(getattr(obj_b, "physical_state", ""))
            if psa == PHYSICAL_STATE_HELD or psb == PHYSICAL_STATE_HELD:
                term = TERMINATION_STATE_EXCLUSION_HELD
                st.counters["end_state_exclusion_held"] = int(
                    st.counters.get("end_state_exclusion_held", 0)
                ) + 1
            elif psa not in FREE_STATES or psb not in FREE_STATES:
                term = TERMINATION_STATE_EXCLUSION_HELD
                st.counters["end_state_exclusion_held"] = int(
                    st.counters.get("end_state_exclusion_held", 0)
                ) + 1
            else:
                st.counters["end_separation"] = int(st.counters.get("end_separation", 0)) + 1

        st.counters["end"] = int(st.counters.get("end", 0)) + 1
        if obj_a is not None and obj_b is not None and str(getattr(obj_a, "physical_state", "")) in FREE_STATES and str(getattr(obj_b, "physical_state", "")) in FREE_STATES:
            m = measure_pair(
                obj_a=obj_a,
                obj_b=obj_b,
                width=width,
                height=height,
                cfg=cfg,
                prev_a=st.prev_object_poses.get(oid_a),
                prev_b=st.prev_object_poses.get(oid_b),
                allow_swept=False,
            )
        else:
            m = {
                "in_contact": False,
                "detection_mode": None,
                "endpoint_distance": None,
                "closest_swept_distance": None,
                "contact_fraction": None,
                "separation": None,
                "penetration": None,
                "displacement": None,
                "object_a_pose": None,
                "object_b_pose": None,
                "object_a_start_pose": None,
                "object_b_start_pose": None,
                "object_a_geometry": None,
                "object_b_geometry": None,
                "combined_radius": None,
                "contact_point": None,
                "contact_point_policy": "UNAVAILABLE",
                "object_a_physical_state": (
                    str(getattr(obj_a, "physical_state", "")) if obj_a is not None else None
                ),
                "object_b_physical_state": (
                    str(getattr(obj_b, "physical_state", "")) if obj_b is not None else None
                ),
            }
        m["termination_reason"] = term
        m["end_reason"] = term
        end_receipts.append(_receipt(te, PHASE_END, ep, m, cfg, contact_fact=False))

    # Store poses for next tick swept (post-response authoritative current)
    st.prev_object_poses = {
        str(o.object_id): ([float(o.x), float(o.y), float(getattr(o, "z", 0.0) or 0.0)] if hasattr(o, "z") else [float(o.x), float(o.y)])
        for o in objects
        if str(getattr(o, "physical_state", ""))
        in (PHYSICAL_STATE_FREE_STATIC, PHYSICAL_STATE_FREE_MOVING, PHYSICAL_STATE_HELD)
    }

    step = {
        "event": EVENT_STEP,
        "tick": te,
        "mechanism": MECHANISM_ID,
        "broad_phase_strategy": BROAD_PHASE_STRATEGY,
        "broad_phase_candidates": len(candidates),
        "narrow_phase_checks": len(checked),
        "free_object_count": len(free_objs),
        "active_episodes": len(st.active),
        "begin": begin_receipts,
        "persist": persist_rows,
        "end": end_receipts,
        "held_free_object_pair_contact": HELD_FREE_OBJECT_PAIR_CONTACT,
        "swept_contact": SWEPT_CONTACT,
        "complexity": "O(N^2)",
        "collision_response_applied": False,
        "impulse_transferred": False,
        "position_corrected": False,
        "velocity_changed": False,
        "sound_emitted": False,
        "composition_changed": False,
        "agent_accessible": False,
        "researcher_only": True,
    }
    st.last_step = step
    world.last_resource_object_pair_contact_step = step
    for r in begin_receipts + end_receipts:
        st.history.append(r)
    lim = int(cfg.history_limit)
    if len(st.history) > lim:
        st.history = st.history[-lim:]
    st.last_processed_tick = te
    return step


def _receipt(
    tick: int,
    phase: str,
    ep: dict[str, Any],
    m: dict[str, Any],
    cfg: ResourceObjectPairContactConfig,
    *,
    contact_fact: bool | None = None,
) -> dict[str, Any]:
    cf = bool(m.get("in_contact")) if contact_fact is None else bool(contact_fact)
    if phase == PHASE_END:
        cf = False
    return {
        "receipt_kind": RECEIPT_KIND,
        "tick": int(tick),
        "contact_phase": phase,
        "episode_id": ep["episode_id"],
        "object_id_a": ep["object_id_a"],
        "object_id_b": ep["object_id_b"],
        "pair_key": canonical_pair_key(ep["object_id_a"], ep["object_id_b"]),
        "object_a_collision_geometry": m.get("object_a_geometry"),
        "object_b_collision_geometry": m.get("object_b_geometry"),
        "object_a_start_pose": m.get("object_a_start_pose"),
        "object_a_end_pose": m.get("object_a_pose"),
        "object_b_start_pose": m.get("object_b_start_pose"),
        "object_b_end_pose": m.get("object_b_pose"),
        "shortest_toroidal_displacement": m.get("displacement"),
        "endpoint_distance": m.get("endpoint_distance"),
        "closest_swept_distance": m.get("closest_swept_distance"),
        "contact_fraction": m.get("contact_fraction"),
        "detection_mode": m.get("detection_mode") if phase != PHASE_END else ep.get("detection_mode"),
        "separation": m.get("separation"),
        "penetration": m.get("penetration"),
        "combined_radius": m.get("combined_radius"),
        "contact_point": m.get("contact_point"),
        "contact_point_policy": m.get("contact_point_policy"),
        "object_a_physical_state": m.get("object_a_physical_state"),
        "object_b_physical_state": m.get("object_b_physical_state"),
        "broad_phase_candidate": True,
        "broad_phase_strategy": BROAD_PHASE_STRATEGY,
        "narrow_phase_result": bool(m.get("in_contact")) if phase != PHASE_END else False,
        "contact_fact": cf,
        "collision_response_applied": False,
        "impulse_transferred": False,
        "position_corrected": False,
        "velocity_changed": False,
        "sound_emitted": False,
        "composition_changed": False,
        "agent_accessible": False,
        "researcher_only": True,
        "mechanism": MECHANISM_ID,
        "preset_mechanism": MECHANISM_ID,
        "termination_reason": m.get("termination_reason"),
        "end_reason": m.get("end_reason"),
        "object_collision_radius_canonical": float(cfg.default_object_collision_radius),
    }


def researcher_summary(world: Any) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    step = st.last_step or {}
    return {
        "mechanism": MECHANISM_ID,
        "active_episodes": [
            {
                "episode_id": v["episode_id"],
                "object_id_a": v["object_id_a"],
                "object_id_b": v["object_id_b"],
                "detection_mode": v.get("detection_mode"),
                "begin_tick": v.get("begin_tick"),
                "last_tick": v.get("last_tick"),
                "status": PHASE_PERSIST,
            }
            for _, v in sorted(st.active.items())
        ],
        "last_step": {
            "tick": step.get("tick"),
            "begin_count": len(step.get("begin") or []),
            "persist_count": len(step.get("persist") or []),
            "end_count": len(step.get("end") or []),
            "broad_phase_candidates": step.get("broad_phase_candidates"),
            "narrow_phase_checks": step.get("narrow_phase_checks"),
            "broad_phase_strategy": BROAD_PHASE_STRATEGY,
            "free_object_count": step.get("free_object_count"),
        },
        "counters": dict(st.counters),
        "overlay_caption": (
            "OBJECT/OBJECT CONTACT FACT ONLY · NO IMPULSE · NO RESPONSE · NO SOUND"
        ),
        "held_free_object_pair_contact": HELD_FREE_OBJECT_PAIR_CONTACT,
        "swept_contact": SWEPT_CONTACT,
        "broad_phase_strategy": BROAD_PHASE_STRATEGY,
        "agent_accessible": False,
        "researcher_only": True,
        "collision_response_applied": False,
        "impulse_transferred": False,
        "position_corrected": False,
        "velocity_changed": False,
        "sound_emitted": False,
        "composition_changed": False,
    }


def overlay_payload(world: Any) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    objects = []
    for obj in list(getattr(world, "resource_objects", None) or []):
        objects.append(
            {
                "object_id": str(obj.object_id),
                "x": float(obj.x),
                "y": float(obj.y),
                "collision_radius": ensure_object_collision_radius(obj),
                "optical_radius": float(getattr(obj, "optical_radius", 0.0) or 0.0),
                "physical_state": str(getattr(obj, "physical_state", "")),
            }
        )
    return {
        "caption": "OBJECT/OBJECT CONTACT FACT ONLY\nNO IMPULSE · NO RESPONSE · NO SOUND",
        "objects": objects,
        "active": researcher_summary(world),
        "broad_phase_strategy": BROAD_PHASE_STRATEGY,
    }
