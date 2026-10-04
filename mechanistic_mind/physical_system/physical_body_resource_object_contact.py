"""Acanthostega body ↔ ResourceObject contact FACT (measurement only).

Preset: ACANTHOSTEGA_PHASE_B_BODY_OBJECT_CONTACT
Mechanism: physical_body_resource_object_contact

No impulse, position correction, velocity change, sound, grasp, or composition.
Object may still pass through body — expected limitation of this stage.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

MECHANISM_ID = "physical_body_resource_object_contact"
PROFILE_VERSION = "BODY_RESOURCE_OBJECT_CONTACT_PROFILE_V1"
STATE_SCHEMA = "BODY_RESOURCE_OBJECT_CONTACT_STATE_V1"
RECEIPT_KIND = "BODY_RESOURCE_OBJECT_CONTACT"
EVENT_STEP = "BODY_RESOURCE_OBJECT_CONTACT_STEP"

# Continuous body radius matching body-body soft-contact CoM threshold 1.15
# when two equal bodies touch: each contributes 0.575. Documented adapter only;
# does NOT change body-body results.
BODY_CONTACT_RADIUS = 0.575
# Canonical object collision radius (world cells). Distinct from optical (0.45)
# and interaction/held-contact (0.20). Not glyph size.
CANONICAL_COLLISION_RADIUS = 0.25
CONTACT_EPSILON = 1e-9

DETECTION_ENDPOINT = "ENDPOINT_OVERLAP"
DETECTION_SWEPT = "SWEPT_CROSSING"
PHASE_BEGIN = "BEGIN"
PHASE_PERSIST = "PERSIST"
PHASE_END = "END"

HELD_OBJECT_BODY_CONTACT = "NOT_IMPLEMENTED"
SWEPT_CONTACT = "IMPLEMENTED"

PHYSICAL_STATE_FREE_STATIC = "FREE_STATIC"
PHYSICAL_STATE_FREE_MOVING = "FREE_MOVING"
PHYSICAL_STATE_HELD = "HELD"

RESPONSE_FLAGS = {
    "contact_fact": True,
    "collision_response_applied": False,
    "impulse_transferred": False,
    "position_corrected": False,
    "velocity_changed": False,
    "sound_emitted": False,
}


@dataclass
class BodyObjectContactConfig:
    enabled: bool = False
    body_contact_radius: float = BODY_CONTACT_RADIUS
    default_object_collision_radius: float = CANONICAL_COLLISION_RADIUS
    contact_epsilon: float = CONTACT_EPSILON
    broad_phase_cell_margin: int = 1
    history_limit: int = 64

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "body_contact_radius": float(self.body_contact_radius),
            "default_object_collision_radius": float(self.default_object_collision_radius),
            "contact_epsilon": float(self.contact_epsilon),
            "broad_phase_cell_margin": int(self.broad_phase_cell_margin),
            "history_limit": int(self.history_limit),
            "profile_version": PROFILE_VERSION,
            "held_object_body_contact": HELD_OBJECT_BODY_CONTACT,
            "swept_contact": SWEPT_CONTACT,
            "response": dict(RESPONSE_FLAGS),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "BodyObjectContactConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        ver = data.get("profile_version")
        if ver is not None and str(ver) != PROFILE_VERSION:
            raise ValueError(f"unknown body/object contact profile: {ver}")
        return cls(
            enabled=bool(data.get("enabled", False)),
            body_contact_radius=float(data.get("body_contact_radius", BODY_CONTACT_RADIUS)),
            default_object_collision_radius=float(
                data.get("default_object_collision_radius", CANONICAL_COLLISION_RADIUS)
            ),
            contact_epsilon=float(data.get("contact_epsilon", CONTACT_EPSILON)),
            broad_phase_cell_margin=int(data.get("broad_phase_cell_margin", 1)),
            history_limit=int(data.get("history_limit", 64)),
        )


def body_object_contact_is_active(config: Any) -> bool:
    cfg = getattr(config, "physical_body_resource_object_contact", None)
    return bool(cfg is not None and getattr(cfg, "enabled", False))


def set_body_object_contact(config: Any, enabled: bool) -> None:
    on = bool(enabled)
    cur = getattr(config, "physical_body_resource_object_contact", None)
    if cur is None:
        config.physical_body_resource_object_contact = BodyObjectContactConfig(enabled=on)
    else:
        cur.enabled = on


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "config_path": "physical_body_resource_object_contact.enabled",
        "enabled": bool(enabled),
        "description": (
            "Acanthostega researcher-only body↔ResourceObject contact FACT "
            "(endpoint + swept). No impulse/response/sound."
        ),
        "agent_accessible": False,
        "collision_response": False,
    }


def clip_collision_radius(raw: Any, default: float = CANONICAL_COLLISION_RADIUS) -> float:
    try:
        r = float(raw)
    except (TypeError, ValueError):
        r = float(default)
    if not math.isfinite(r) or r <= 0.0:
        r = float(default)
    return float(max(1e-6, min(8.0, r)))


def ensure_object_collision_radius(obj: Any, default: float = CANONICAL_COLLISION_RADIUS) -> float:
    """Authoritative field on ResourceObject; missing → canonical (not optical/interaction)."""
    raw = getattr(obj, "collision_radius", None)
    if raw is None:
        r = clip_collision_radius(default)
        try:
            obj.collision_radius = r
        except Exception:
            pass
        return r
    r = clip_collision_radius(raw, default)
    try:
        obj.collision_radius = r
    except Exception:
        pass
    return r


def body_contact_geometry(body: Any, *, radius: float = BODY_CONTACT_RADIUS) -> dict[str, Any]:
    """Narrow adapter: continuous circle at body CoM. Does not alter body-body solver."""
    return {
        "shape": "CIRCLE",
        "center": [float(body.x), float(body.y)],
        "radius": float(radius),
        "source": "BODY_SOFT_CONTACT_HALF_THRESHOLD_V1",
        "body_body_threshold": 1.15,
        "researcher_glyph": False,
        "vision_footprint_as_solid": False,
    }


def object_contact_geometry(obj: Any, *, default_radius: float = CANONICAL_COLLISION_RADIUS) -> dict[str, Any]:
    r = ensure_object_collision_radius(obj, default_radius)
    return {
        "shape": "CIRCLE",
        "center": [float(obj.x), float(obj.y)],
        "radius": float(r),
        "source": "RESOURCE_OBJECT_COLLISION_RADIUS_V1",
        "optical_radius": float(getattr(obj, "optical_radius", 0.0) or 0.0),
        "interaction_radius": float(getattr(obj, "interaction_radius", 0.0) or 0.0),
        "glyph_size_used": False,
    }


def shortest_toroidal_delta(ax: float, ay: float, bx: float, by: float, width: int, height: int) -> tuple[float, float]:
    dx = float(bx) - float(ax)
    dy = float(by) - float(ay)
    w, h = float(width), float(height)
    if dx > w / 2.0:
        dx -= w
    elif dx < -w / 2.0:
        dx += w
    if dy > h / 2.0:
        dy -= h
    elif dy < -h / 2.0:
        dy += h
    return dx, dy


def _norm(dx: float, dy: float) -> float:
    return float(math.hypot(dx, dy))


@dataclass
class BodyObjectContactState:
    config: BodyObjectContactConfig
    active: dict[str, dict[str, Any]] = field(default_factory=dict)  # pair_key -> episode
    prev_body_poses: dict[str, list[float]] = field(default_factory=dict)
    prev_object_poses: dict[str, list[float]] = field(default_factory=dict)
    episode_tick: int = -1
    episode_next: int = 0
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
        "skipped_held": 0,
    }


def state_of(world: Any) -> BodyObjectContactState | None:
    raw = getattr(world, "body_object_contact_state", None)
    return raw if isinstance(raw, BodyObjectContactState) else None


def ensure_body_object_contact_for_runtime(world: Any, config: Any) -> BodyObjectContactState | None:
    if not body_object_contact_is_active(config):
        world.body_object_contact_state = None
        return None
    cfg = getattr(config, "physical_body_resource_object_contact", None) or BodyObjectContactConfig(enabled=True)
    st = state_of(world)
    if st is None:
        st = BodyObjectContactState(config=cfg, counters=_zero_counters())
        world.body_object_contact_state = st
    else:
        st.config = cfg
    # Ensure all resource objects carry collision_radius
    for obj in list(getattr(world, "resource_objects", None) or []):
        ensure_object_collision_radius(obj, cfg.default_object_collision_radius)
    return st


def copy_state(st: BodyObjectContactState | None) -> BodyObjectContactState | None:
    if st is None:
        return None
    return BodyObjectContactState(
        config=BodyObjectContactConfig.from_dict(st.config.to_dict()),
        active={k: dict(v) for k, v in st.active.items()},
        prev_body_poses={k: list(v) for k, v in st.prev_body_poses.items()},
        prev_object_poses={k: list(v) for k, v in st.prev_object_poses.items()},
        episode_tick=int(st.episode_tick),
        episode_next=int(st.episode_next),
        last_step=dict(st.last_step) if st.last_step else None,
        history=[dict(h) for h in st.history],
        counters=dict(st.counters),
    )


def serialize_state(st: BodyObjectContactState | None) -> dict[str, Any] | None:
    if st is None:
        return None
    return {
        "schema_version": STATE_SCHEMA,
        "config": st.config.to_dict(),
        "active": {k: dict(v) for k, v in sorted(st.active.items())},
        "prev_body_poses": {k: [float(v[0]), float(v[1])] for k, v in sorted(st.prev_body_poses.items())},
        "prev_object_poses": {k: [float(v[0]), float(v[1])] for k, v in sorted(st.prev_object_poses.items())},
        "episode_allocator": {"tick": int(st.episode_tick), "next_sequence": int(st.episode_next)},
        "counters": dict(st.counters),
        "history": list(st.history)[-int(st.config.history_limit):],
    }


def restore_state(world: Any, data: dict[str, Any] | None, config: Any) -> BodyObjectContactState | None:
    if not body_object_contact_is_active(config):
        world.body_object_contact_state = None
        return None
    if not isinstance(data, dict) or not data:
        return ensure_body_object_contact_for_runtime(world, config)
    if str(data.get("schema_version")) != STATE_SCHEMA:
        raise ValueError(f"unknown body/object contact state schema: {data.get('schema_version')}")
    cfg = BodyObjectContactConfig.from_dict(data.get("config"))
    cfg.enabled = True
    alloc = data.get("episode_allocator") or {}
    st = BodyObjectContactState(
        config=cfg,
        active={str(k): dict(v) for k, v in (data.get("active") or {}).items()},
        prev_body_poses={str(k): [float(v[0]), float(v[1])] for k, v in (data.get("prev_body_poses") or {}).items()},
        prev_object_poses={str(k): [float(v[0]), float(v[1])] for k, v in (data.get("prev_object_poses") or {}).items()},
        episode_tick=int(alloc.get("tick", -1)),
        episode_next=int(alloc.get("next_sequence", 0)),
        history=list(data.get("history") or []),
        counters={**_zero_counters(), **{k: int(v) for k, v in (data.get("counters") or {}).items()}},
    )
    world.body_object_contact_state = st
    config.physical_body_resource_object_contact = cfg
    for obj in list(getattr(world, "resource_objects", None) or []):
        ensure_object_collision_radius(obj, cfg.default_object_collision_radius)
    return st


def _pair_key(body_id: str, object_id: str) -> str:
    return f"{body_id}|{object_id}"


def _alloc_episode(st: BodyObjectContactState, tick: int) -> str:
    if int(st.episode_tick) != int(tick):
        st.episode_tick = int(tick)
        st.episode_next = 0
    st.episode_next += 1
    return f"boc-{int(tick):06d}-{st.episode_next:04d}"


def closest_approach_segment(
    p0x: float, p0y: float, p1x: float, p1y: float,
) -> tuple[float, float, float]:
    """Closest approach of origin to segment p0→p1. Returns (t*, dist, dist²)."""
    dx = p1x - p0x
    dy = p1y - p0y
    denom = dx * dx + dy * dy
    if denom <= 1e-18:
        d2 = p0x * p0x + p0y * p0y
        return 0.0, math.sqrt(d2), d2
    t = max(0.0, min(1.0, - (p0x * dx + p0y * dy) / denom))
    cx = p0x + t * dx
    cy = p0y + t * dy
    d2 = cx * cx + cy * cy
    return float(t), float(math.sqrt(d2)), float(d2)


def measure_pair(
    *,
    body_id: str,
    body: Any,
    obj: Any,
    width: int,
    height: int,
    cfg: BodyObjectContactConfig,
    prev_body: list[float] | None,
    prev_obj: list[float] | None,
) -> dict[str, Any]:
    br = float(cfg.body_contact_radius)
    orad = ensure_object_collision_radius(obj, cfg.default_object_collision_radius)
    sum_r = br + orad
    bx, by = float(body.x), float(body.y)
    ox, oy = float(obj.x), float(obj.y)
    dx, dy = shortest_toroidal_delta(bx, by, ox, oy, width, height)
    endpoint_dist = _norm(dx, dy)
    separation = endpoint_dist - sum_r
    endpoint_contact = separation <= float(cfg.contact_epsilon)
    penetration = max(0.0, -separation)

    detection = DETECTION_ENDPOINT if endpoint_contact else None
    closest_swept = endpoint_dist
    contact_fraction = 1.0 if endpoint_contact else None
    swept_contact = False

    # Swept: relative motion of object wrt body in unwrapped frame of end delta
    if prev_body is not None and prev_obj is not None:
        # body start → end and object start → end along shortest wrap branches to current
        bdx0, bdy0 = shortest_toroidal_delta(bx, by, float(prev_body[0]), float(prev_body[1]), width, height)
        # prev relative to current body: start_rel = (prev_obj - prev_body) in unwrapped coords
        # Use: object_prev relative to body_prev via toroidal; then map so end_rel = (dx,dy)
        odx0, ody0 = shortest_toroidal_delta(
            float(prev_body[0]), float(prev_body[1]), float(prev_obj[0]), float(prev_obj[1]), width, height
        )
        # start relative (object - body) at t=0, end relative at t=1
        rel0x, rel0y = odx0, ody0
        rel1x, rel1y = dx, dy
        t_star, closest_swept, _ = closest_approach_segment(rel0x, rel0y, rel1x, rel1y)
        if closest_swept <= sum_r + float(cfg.contact_epsilon):
            swept_contact = True
            if not endpoint_contact:
                detection = DETECTION_SWEPT
                contact_fraction = float(t_star)
            else:
                detection = DETECTION_ENDPOINT
                contact_fraction = 1.0

    in_contact = bool(endpoint_contact or swept_contact)

    # Contact point estimate (researcher-only)
    if endpoint_dist < 1e-12:
        # coincident centres: deterministic +X from body
        nx, ny = 1.0, 0.0
        contact_point = [bx + br * nx, by + br * ny]
        contact_point_policy = "COINCIDENT_CENTRES_PLUS_X"
    else:
        nx, ny = dx / endpoint_dist, dy / endpoint_dist
        # point on line of centres at body surface toward object
        contact_point = [bx + nx * br, by + ny * br]
        contact_point_policy = "LINE_OF_CENTRES_BODY_SURFACE"
    # wrap contact point into world
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
        "body_pose": [bx, by],
        "object_pose": [ox, oy],
        "body_start_pose": list(prev_body) if prev_body else [bx, by],
        "object_start_pose": list(prev_obj) if prev_obj else [ox, oy],
        "body_geometry": body_contact_geometry(body, radius=br),
        "object_geometry": object_contact_geometry(obj, default_radius=cfg.default_object_collision_radius),
        "contact_point": contact_point,
        "contact_point_policy": contact_point_policy,
        "object_physical_state": str(getattr(obj, "physical_state", "")),
        "holder_body_id": (str(obj.holder_body_id) if getattr(obj, "holder_body_id", None) else None),
    }


def _broad_phase_candidates(
    world: Any,
    bodies: list[tuple[str, Any]],
    objects: list[Any],
    *,
    width: int,
    height: int,
    cfg: BodyObjectContactConfig,
) -> list[tuple[str, Any, Any]]:
    """Use spatial index when present; always fall back to all FREE_* objects × bodies."""
    margin = int(cfg.broad_phase_cell_margin)
    # +2.0 margin covers relative motion up to ~1.5 cell/tick (body+object) for swept.
    max_reach = float(cfg.body_contact_radius) + float(cfg.default_object_collision_radius) + 2.0
    cell_r = max(margin, int(math.ceil(max_reach)) + margin)
    index = getattr(world, "spatial_contents", None)
    out: list[tuple[str, Any, Any]] = []
    seen: set[tuple[str, str]] = set()
    free_objs = [
        o for o in objects
        if str(getattr(o, "physical_state", "")) in (PHYSICAL_STATE_FREE_STATIC, PHYSICAL_STATE_FREE_MOVING)
    ]
    for body_id, body in bodies:
        bx, by = float(body.x), float(body.y)
        bcx, bcy = int(math.floor(bx)) % width, int(math.floor(by)) % height
        candidate_objs = free_objs
        if index is not None and getattr(index, "by_cell", None) is not None:
            ids: set[str] = set()
            for dy in range(-cell_r, cell_r + 1):
                for dx in range(-cell_r, cell_r + 1):
                    cell = ((bcx + dx) % width, (bcy + dy) % height)
                    for ref in index.by_cell.get(cell, []) or []:
                        if getattr(ref, "entity_kind", None) == "RESOURCE_OBJECT":
                            ids.add(str(ref.entity_id))
            if ids:
                by_id = {str(o.object_id): o for o in free_objs}
                candidate_objs = [by_id[i] for i in sorted(ids) if i in by_id]
        for obj in candidate_objs:
            key = (body_id, str(obj.object_id))
            if key in seen:
                continue
            seen.add(key)
            out.append((body_id, body, obj))
    out.sort(key=lambda t: (t[0], str(t[2].object_id)))
    return out


def detect_body_resource_object_contacts(
    world: Any,
    bodies: list[tuple[str, Any]],
    *,
    tick: int,
    config: Any,
) -> dict[str, Any] | None:
    """One shared-world contact FACT phase. Read-only w.r.t. poses/velocities."""
    if not body_object_contact_is_active(config):
        return None
    st = ensure_body_object_contact_for_runtime(world, config)
    if st is None:
        return None
    cfg = st.config
    height, width = int(world.T.shape[0]), int(world.T.shape[1])
    objects = list(getattr(world, "resource_objects", None) or [])
    # Skip HELD entirely this stage (holder + foreign deferred)
    held_skipped = sum(1 for o in objects if str(getattr(o, "physical_state", "")) == PHYSICAL_STATE_HELD)
    st.counters["skipped_held"] = int(st.counters.get("skipped_held", 0)) + int(held_skipped)

    # Sort bodies for determinism
    bodies_sorted = sorted([(str(bid), b) for bid, b in bodies if b is not None], key=lambda t: t[0])
    candidates = _broad_phase_candidates(world, bodies_sorted, objects, width=width, height=height, cfg=cfg)
    try:
        from mechanistic_mind.physical_system.detached_terrain_material_initial_placement import (
            object_dynamics_eligible,
        )

        candidates = [
            row for row in candidates if object_dynamics_eligible(row[2], int(tick))
        ]
    except Exception:
        pass
    # Always include currently active pairs (avoid false END if broad phase is tight).
    by_body = {bid: b for bid, b in bodies_sorted}
    by_obj = {str(o.object_id): o for o in objects}
    seen_c = {(bid, str(obj.object_id)) for bid, _b, obj in candidates}
    for pk, ep in list(st.active.items()):
        bid = str(ep.get("body_id"))
        oid = str(ep.get("object_id"))
        if (bid, oid) in seen_c:
            continue
        if bid in by_body and oid in by_obj:
            ps = str(getattr(by_obj[oid], "physical_state", ""))
            if ps in (PHYSICAL_STATE_FREE_STATIC, PHYSICAL_STATE_FREE_MOVING):
                candidates.append((bid, by_body[bid], by_obj[oid]))
                seen_c.add((bid, oid))
    candidates.sort(key=lambda row: (row[0], str(row[2].object_id)))
    st.counters["broad_candidates"] = int(st.counters.get("broad_candidates", 0)) + len(candidates)

    current_keys: set[str] = set()
    measurements: list[dict[str, Any]] = []
    begin_receipts: list[dict[str, Any]] = []
    persist_rows: list[dict[str, Any]] = []
    end_receipts: list[dict[str, Any]] = []

    for body_id, body, obj in candidates:
        st.counters["narrow_checks"] = int(st.counters.get("narrow_checks", 0)) + 1
        oid = str(obj.object_id)
        pk = _pair_key(body_id, oid)
        prev_b = st.prev_body_poses.get(body_id)
        prev_o = st.prev_object_poses.get(oid)
        m = measure_pair(
            body_id=body_id, body=body, obj=obj, width=width, height=height, cfg=cfg,
            prev_body=prev_b, prev_obj=prev_o,
        )
        m["body_id"] = body_id
        m["object_id"] = oid
        m["pair_key"] = pk
        m["broad_phase_candidate"] = True
        from mechanistic_mind.physical_system.flat_ground_gravity import (
            apply_vertical_filter_to_measurement,
        )
        apply_vertical_filter_to_measurement(
            world, config, m,
            a=body, b=obj, kind_a="body", kind_b="object",
            a_prev=prev_b, b_prev=prev_o,
        )
        # Active pairs: ENDPOINT only (swept t=0 would otherwise prevent END after separation).
        # New pairs: endpoint OR swept crossing.
        if pk in st.active:
            m["in_contact"] = bool(m.get("endpoint_contact")) and bool(m.get("in_contact"))
            if m["in_contact"]:
                m["detection_mode"] = DETECTION_ENDPOINT
            elif m.get("vertical_separation_reason"):
                # XY still overlaps but height lost → END via normal inactive path below
                pass
        if not m["in_contact"]:
            continue
        current_keys.add(pk)
        if m["detection_mode"] == DETECTION_SWEPT:
            st.counters["swept"] = int(st.counters.get("swept", 0)) + 1
        else:
            st.counters["endpoint"] = int(st.counters.get("endpoint", 0)) + 1

        if pk not in st.active:
            eid = _alloc_episode(st, tick)
            phase = PHASE_BEGIN
            st.active[pk] = {
                "episode_id": eid,
                "body_id": body_id,
                "object_id": oid,
                "begin_tick": int(tick),
                "last_tick": int(tick),
                "detection_mode": m["detection_mode"],
            }
            st.counters["begin"] = int(st.counters.get("begin", 0)) + 1
            receipt = _receipt(tick, phase, st.active[pk], m, cfg)
            begin_receipts.append(receipt)
            measurements.append(receipt)
        else:
            ep = st.active[pk]
            ep["last_tick"] = int(tick)
            ep["detection_mode"] = m["detection_mode"]
            phase = PHASE_PERSIST
            st.counters["persist"] = int(st.counters.get("persist", 0)) + 1
            row = _receipt(tick, phase, ep, m, cfg)
            persist_rows.append(row)
            measurements.append(row)

    # ENDs
    for pk in sorted(set(st.active) - current_keys):
        ep = st.active.pop(pk)
        phase = PHASE_END
        st.counters["end"] = int(st.counters.get("end", 0)) + 1
        # reconstruct last measurement with contact_fact false
        body = next((b for bid, b in bodies_sorted if bid == ep["body_id"]), None)
        obj = next((o for o in objects if str(o.object_id) == ep["object_id"]), None)
        if body is not None and obj is not None:
            m = measure_pair(
                body_id=ep["body_id"], body=body, obj=obj, width=width, height=height, cfg=cfg,
                prev_body=st.prev_body_poses.get(ep["body_id"]),
                prev_obj=st.prev_object_poses.get(ep["object_id"]),
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
                "body_pose": None,
                "object_pose": None,
                "body_start_pose": None,
                "object_start_pose": None,
                "body_geometry": None,
                "object_geometry": None,
                "contact_point": None,
                "contact_point_policy": "UNAVAILABLE",
                "object_physical_state": None,
                "holder_body_id": None,
                "body_id": ep["body_id"],
                "object_id": ep["object_id"],
            }
        m["end_reason"] = (
            "VERTICAL_SEPARATION"
            if (m.get("vertical_separation_reason") == "VERTICAL_SEPARATION"
                or m.get("vertical_filter") == "REJECT")
            else "SEPARATION"
        )
        receipt = _receipt(tick, phase, ep, m, cfg, contact_fact=False)
        end_receipts.append(receipt)
        measurements.append(receipt)

    # Store poses for next tick swept (authoritative current)
    def _pose3(ent):
        row = [float(ent.x), float(ent.y)]
        if hasattr(ent, "z"):
            row.append(float(getattr(ent, "z", 0.0) or 0.0))
        return row
    st.prev_body_poses = {bid: _pose3(b) for bid, b in bodies_sorted}
    st.prev_object_poses = {
        str(o.object_id): _pose3(o)
        for o in objects
        if str(getattr(o, "physical_state", "")) in (PHYSICAL_STATE_FREE_STATIC, PHYSICAL_STATE_FREE_MOVING, PHYSICAL_STATE_HELD)
    }

    step = {
        "event": EVENT_STEP,
        "tick": int(tick),
        "mechanism": MECHANISM_ID,
        "broad_phase_candidates": len(candidates),
        "narrow_phase_checks": len(candidates),
        "active_episodes": len(st.active),
        "begin": begin_receipts,
        "persist": persist_rows,
        "end": end_receipts,
        "held_object_body_contact": HELD_OBJECT_BODY_CONTACT,
        "swept_contact": SWEPT_CONTACT,
        **{k: False for k in ("collision_response_applied", "impulse_transferred", "position_corrected", "velocity_changed", "sound_emitted")},
        "agent_accessible": False,
        "researcher_only": True,
    }
    st.last_step = step
    world.last_body_object_contact_step = step
    # Bounded history: BEGIN/END only (PERSIST stays in last_step)
    for r in begin_receipts + end_receipts:
        st.history.append(r)
    lim = int(cfg.history_limit)
    if len(st.history) > lim:
        st.history = st.history[-lim:]
    return step


def _receipt(
    tick: int,
    phase: str,
    ep: dict[str, Any],
    m: dict[str, Any],
    cfg: BodyObjectContactConfig,
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
        "body_id": ep["body_id"],
        "object_id": ep["object_id"],
        "pair_key": _pair_key(ep["body_id"], ep["object_id"]),
        "body_physical_geometry": m.get("body_geometry"),
        "object_collision_geometry": m.get("object_geometry"),
        "body_start_pose": m.get("body_start_pose"),
        "body_end_pose": m.get("body_pose"),
        "object_start_pose": m.get("object_start_pose"),
        "object_end_pose": m.get("object_pose"),
        "shortest_toroidal_displacement": m.get("displacement"),
        "endpoint_distance": m.get("endpoint_distance"),
        "closest_swept_distance": m.get("closest_swept_distance"),
        "contact_fraction": m.get("contact_fraction"),
        "detection_mode": m.get("detection_mode") if phase != PHASE_END else ep.get("detection_mode"),
        "separation": m.get("separation"),
        "penetration": m.get("penetration"),
        "contact_point": m.get("contact_point"),
        "contact_point_policy": m.get("contact_point_policy"),
        "object_physical_state": m.get("object_physical_state"),
        "holder_relation": (
            "HOLDER_SKIPPED" if m.get("holder_body_id") == ep["body_id"]
            else ("FOREIGN_HELD_NOT_IMPLEMENTED" if m.get("holder_body_id") else "NONE")
        ),
        "broad_phase_candidate": True,
        "narrow_phase_result": bool(m.get("in_contact")) if phase != PHASE_END else False,
        "contact_fact": cf,
        "collision_response_applied": False,
        "impulse_transferred": False,
        "position_corrected": False,
        "velocity_changed": False,
        "sound_emitted": False,
        "agent_accessible": False,
        "researcher_only": True,
        "mechanism": MECHANISM_ID,
        "preset_mechanism": MECHANISM_ID,
        "end_reason": m.get("end_reason"),
        "body_contact_radius": float(cfg.body_contact_radius),
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
                "body_id": v["body_id"],
                "object_id": v["object_id"],
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
        },
        "counters": dict(st.counters),
        "overlay_caption": "CONTACT FACT ONLY — NO IMPULSE · NO RESPONSE · NO SOUND",
        "held_object_body_contact": HELD_OBJECT_BODY_CONTACT,
        "swept_contact": SWEPT_CONTACT,
        "agent_accessible": False,
        "researcher_only": True,
        "collision_response_applied": False,
    }


def overlay_payload(world: Any) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    objects = []
    for obj in list(getattr(world, "resource_objects", None) or []):
        objects.append({
            "object_id": str(obj.object_id),
            "x": float(obj.x),
            "y": float(obj.y),
            "collision_radius": ensure_object_collision_radius(obj),
            "optical_radius": float(getattr(obj, "optical_radius", 0.0) or 0.0),
            "physical_state": str(getattr(obj, "physical_state", "")),
        })
    return {
        "caption": "CONTACT FACT ONLY\nNO IMPULSE · NO RESPONSE · NO SOUND",
        "body_contact_radius": float(st.config.body_contact_radius),
        "objects": objects,
        "active": researcher_summary(world),
    }
