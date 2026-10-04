"""Acanthostega HELD ResourceObject ↔ foreign body contact FACT (measurement only).

Preset: ACANTHOSTEGA_PHASE_B_HELD_OBJECT_FOREIGN_BODY_CONTACT
Mechanism: held_resource_object_foreign_body_contact
Receipt: HELD_RESOURCE_OBJECT_FOREIGN_BODY_CONTACT

Parent: OO IMPACT ACOUSTICS chain, then enable this detector.
No impulse, damage, release, sound, holder mediation, or semantic attack labels.
Reuses geometry helpers from physical_body_resource_object_contact without changing
free B/O detector physics. HELD+HELD remains evaluate_held_object_contact / BRING_TOGETHER.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from mechanistic_mind.physical_system.physical_body_resource_object_contact import (
    BODY_CONTACT_RADIUS,
    CANONICAL_COLLISION_RADIUS,
    CONTACT_EPSILON,
    body_contact_geometry,
    closest_approach_segment,
    ensure_object_collision_radius,
    object_contact_geometry,
    shortest_toroidal_delta,
)

MECHANISM_ID = "held_resource_object_foreign_body_contact"
PROFILE_VERSION = "HELD_RESOURCE_OBJECT_FOREIGN_BODY_CONTACT_PROFILE_V1"
STATE_SCHEMA = "HELD_RESOURCE_OBJECT_FOREIGN_BODY_CONTACT_STATE_V1"
RECEIPT_KIND = "HELD_RESOURCE_OBJECT_FOREIGN_BODY_CONTACT"
EVENT_STEP = "HELD_RESOURCE_OBJECT_FOREIGN_BODY_CONTACT_STEP"

DETECTION_ENDPOINT = "ENDPOINT_OVERLAP"
DETECTION_SWEPT = "SWEPT_CROSSING"
PHASE_BEGIN = "BEGIN"
PHASE_PERSIST = "PERSIST"
PHASE_END = "END"

PHYSICAL_STATE_HELD = "HELD"
PHYSICAL_STATE_FREE_STATIC = "FREE_STATIC"
PHYSICAL_STATE_FREE_MOVING = "FREE_MOVING"

TRANSITION_STABLE_HELD = "STABLE_HELD"
TRANSITION_GRASP_SNAP_ENDPOINT_ONLY = "GRASP_SNAP_ENDPOINT_ONLY"
TRANSITION_HOLDER_OR_HAND_CHANGE_ENDPOINT_ONLY = "HOLDER_OR_HAND_CHANGE_ENDPOINT_ONLY"
TRANSITION_RESTORE_OR_MISSING_HISTORY_ENDPOINT_ONLY = "RESTORE_OR_MISSING_HISTORY_ENDPOINT_ONLY"

END_SEPARATION = "SEPARATION"
END_OBJECT_RELEASED = "OBJECT_RELEASED"
END_OBJECT_REMOVED = "OBJECT_REMOVED"
END_FOREIGN_BODY_REMOVED = "FOREIGN_BODY_REMOVED"

DIAG_INVALID_HOLDER = "INVALID_HOLDER_REFERENCE"
DIAG_HOLDER_SELF_EXCLUDED = "HOLDER_SELF_CONTACT_EXCLUDED"

SWEPT_CONTACT = "IMPLEMENTED_WITH_TRANSITION_POLICY"

RESPONSE_FLAGS = {
    "contact_fact": True,
    "collision_response_applied": False,
    "impulse_transferred": False,
    "position_corrected": False,
    "velocity_changed": False,
    "sound_emitted": False,
    "damage_applied": False,
    "auto_release": False,
    "holder_mediation": False,
}


@dataclass
class HeldForeignBodyContactConfig:
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
            "swept_contact": SWEPT_CONTACT,
            "response": dict(RESPONSE_FLAGS),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "HeldForeignBodyContactConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        ver = data.get("profile_version")
        if ver is not None and str(ver) != PROFILE_VERSION:
            raise ValueError(f"unknown held/foreign contact profile: {ver}")
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


def held_foreign_body_contact_is_active(config: Any) -> bool:
    cfg = getattr(config, "held_resource_object_foreign_body_contact", None)
    return bool(cfg is not None and getattr(cfg, "enabled", False))


def set_held_foreign_body_contact(config: Any, enabled: bool) -> None:
    on = bool(enabled)
    cur = getattr(config, "held_resource_object_foreign_body_contact", None)
    if cur is None:
        config.held_resource_object_foreign_body_contact = HeldForeignBodyContactConfig(enabled=on)
    else:
        cur.enabled = on


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "config_path": "held_resource_object_foreign_body_contact.enabled",
        "enabled": bool(enabled),
        "description": (
            "Acanthostega researcher-only HELD ResourceObject↔foreign body contact FACT "
            "(endpoint + transition-gated swept). No impulse/damage/release/sound."
        ),
        "agent_accessible": False,
        "collision_response": False,
    }


def _norm(dx: float, dy: float) -> float:
    return float(math.hypot(dx, dy))


def _pair_key(held_object_id: str, foreign_body_id: str) -> str:
    return f"{held_object_id}|{foreign_body_id}"


@dataclass
class HeldForeignBodyContactState:
    config: HeldForeignBodyContactConfig
    active: dict[str, dict[str, Any]] = field(default_factory=dict)
    # object_id -> {holder_body_id, manipulator_id, pose:[x,y]}
    prev_held_identity: dict[str, dict[str, Any]] = field(default_factory=dict)
    prev_foreign_body_poses: dict[str, list[float]] = field(default_factory=dict)
    episode_tick: int = -1
    episode_next: int = 0
    last_processed_tick: int = -1
    last_step: dict[str, Any] | None = None
    history: list[dict[str, Any]] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=dict)
    diagnostics: list[dict[str, Any]] = field(default_factory=list)


def _zero_counters() -> dict[str, int]:
    return {
        "begin": 0,
        "persist": 0,
        "end": 0,
        "endpoint": 0,
        "swept": 0,
        "broad_candidates": 0,
        "narrow_checks": 0,
        "invalid_holder": 0,
        "holder_self_excluded": 0,
        "grasp_snap_endpoint_only": 0,
        "holder_hand_change_endpoint_only": 0,
        "restore_missing_endpoint_only": 0,
        "stable_held": 0,
        "end_object_released": 0,
        "end_object_removed": 0,
        "end_foreign_body_removed": 0,
    }


def state_of(world: Any) -> HeldForeignBodyContactState | None:
    raw = getattr(world, "held_foreign_body_contact_state", None)
    return raw if isinstance(raw, HeldForeignBodyContactState) else None


def ensure_held_foreign_body_contact_for_runtime(
    world: Any, config: Any
) -> HeldForeignBodyContactState | None:
    if not held_foreign_body_contact_is_active(config):
        world.held_foreign_body_contact_state = None
        return None
    cfg = getattr(config, "held_resource_object_foreign_body_contact", None) or (
        HeldForeignBodyContactConfig(enabled=True)
    )
    st = state_of(world)
    if st is None:
        st = HeldForeignBodyContactState(config=cfg, counters=_zero_counters())
        world.held_foreign_body_contact_state = st
    else:
        st.config = cfg
    for obj in list(getattr(world, "resource_objects", None) or []):
        ensure_object_collision_radius(obj, cfg.default_object_collision_radius)
    return st


def copy_state(st: HeldForeignBodyContactState | None) -> HeldForeignBodyContactState | None:
    if st is None:
        return None
    return HeldForeignBodyContactState(
        config=HeldForeignBodyContactConfig.from_dict(st.config.to_dict()),
        active={k: dict(v) for k, v in st.active.items()},
        prev_held_identity={k: dict(v) for k, v in st.prev_held_identity.items()},
        prev_foreign_body_poses={k: list(v) for k, v in st.prev_foreign_body_poses.items()},
        episode_tick=int(st.episode_tick),
        episode_next=int(st.episode_next),
        last_processed_tick=int(st.last_processed_tick),
        last_step=dict(st.last_step) if st.last_step else None,
        history=[dict(h) for h in st.history],
        counters=dict(st.counters),
        diagnostics=[dict(d) for d in st.diagnostics],
    )


def serialize_state(st: HeldForeignBodyContactState | None) -> dict[str, Any] | None:
    if st is None:
        return None
    return {
        "schema_version": STATE_SCHEMA,
        "config": st.config.to_dict(),
        "active": {k: dict(v) for k, v in sorted(st.active.items())},
        "prev_held_identity": {
            k: {
                "holder_body_id": v.get("holder_body_id"),
                "manipulator_id": v.get("manipulator_id"),
                "pose": [float(v["pose"][0]), float(v["pose"][1])] if v.get("pose") else None,
            }
            for k, v in sorted(st.prev_held_identity.items())
        },
        "prev_foreign_body_poses": {
            k: [float(v[0]), float(v[1])] for k, v in sorted(st.prev_foreign_body_poses.items())
        },
        "episode_allocator": {"tick": int(st.episode_tick), "next_sequence": int(st.episode_next)},
        "last_processed_tick": int(st.last_processed_tick),
        "counters": dict(st.counters),
        "history": list(st.history)[-int(st.config.history_limit) :],
        "diagnostics": list(st.diagnostics)[-int(st.config.history_limit) :],
    }


def restore_state(world: Any, data: dict[str, Any] | None, config: Any) -> HeldForeignBodyContactState | None:
    if not held_foreign_body_contact_is_active(config):
        world.held_foreign_body_contact_state = None
        return None
    if not isinstance(data, dict) or not data:
        return ensure_held_foreign_body_contact_for_runtime(world, config)
    if str(data.get("schema_version")) != STATE_SCHEMA:
        raise ValueError(
            f"unknown held/foreign contact state schema: {data.get('schema_version')}"
        )
    cfg = HeldForeignBodyContactConfig.from_dict(data.get("config"))
    cfg.enabled = True
    alloc = data.get("episode_allocator") or {}
    prev_held: dict[str, dict[str, Any]] = {}
    for k, v in (data.get("prev_held_identity") or {}).items():
        if not isinstance(v, dict):
            continue
        pose = v.get("pose")
        prev_held[str(k)] = {
            "holder_body_id": (str(v["holder_body_id"]) if v.get("holder_body_id") else None),
            "manipulator_id": (str(v["manipulator_id"]) if v.get("manipulator_id") else None),
            "pose": [float(pose[0]), float(pose[1])] if pose else None,
        }
    st = HeldForeignBodyContactState(
        config=cfg,
        active={str(k): dict(v) for k, v in (data.get("active") or {}).items()},
        prev_held_identity=prev_held,
        prev_foreign_body_poses={
            str(k): [float(v[0]), float(v[1])]
            for k, v in (data.get("prev_foreign_body_poses") or {}).items()
        },
        episode_tick=int(alloc.get("tick", -1)),
        episode_next=int(alloc.get("next_sequence", 0)),
        last_processed_tick=int(data.get("last_processed_tick", -1)),
        history=list(data.get("history") or []),
        counters={**_zero_counters(), **{k: int(v) for k, v in (data.get("counters") or {}).items()}},
        diagnostics=list(data.get("diagnostics") or []),
    )
    world.held_foreign_body_contact_state = st
    config.held_resource_object_foreign_body_contact = cfg
    for obj in list(getattr(world, "resource_objects", None) or []):
        ensure_object_collision_radius(obj, cfg.default_object_collision_radius)
    return st


def _alloc_episode(st: HeldForeignBodyContactState, tick: int) -> str:
    if int(st.episode_tick) != int(tick):
        st.episode_tick = int(tick)
        st.episode_next = 0
    st.episode_next += 1
    return f"hfc-{int(tick):06d}-{st.episode_next:04d}"


def _valid_holder_body_id(holder_body_id: Any, body_ids: set[str]) -> bool:
    if holder_body_id is None:
        return False
    hid = str(holder_body_id).strip()
    if not hid:
        return False
    return hid in body_ids


def resolve_transition_policy(
    *,
    object_id: str,
    holder_body_id: str,
    manipulator_id: str,
    prev: dict[str, Any] | None,
) -> str:
    """LOCKED transition policy for swept eligibility."""
    # Not present in prev held identity → newly GRASPED this tick (or first sighting).
    if prev is None:
        return TRANSITION_GRASP_SNAP_ENDPOINT_ONLY
    prev_holder = prev.get("holder_body_id")
    prev_hand = prev.get("manipulator_id")
    prev_pose = prev.get("pose")
    # Held record exists but pose missing (restore / incomplete history).
    if prev_pose is None:
        return TRANSITION_RESTORE_OR_MISSING_HISTORY_ENDPOINT_ONLY
    if prev_holder is None or prev_hand is None:
        # Prior tick was not HELD with a recorded holder/hand → grasp snap.
        return TRANSITION_GRASP_SNAP_ENDPOINT_ONLY
    if str(prev_holder) != str(holder_body_id) or str(prev_hand) != str(manipulator_id):
        return TRANSITION_HOLDER_OR_HAND_CHANGE_ENDPOINT_ONLY
    return TRANSITION_STABLE_HELD


def measure_held_foreign_pair(
    *,
    held_object_id: str,
    obj: Any,
    foreign_body_id: str,
    body: Any,
    width: int,
    height: int,
    cfg: HeldForeignBodyContactConfig,
    prev_obj_pose: list[float] | None,
    prev_body_pose: list[float] | None,
    allow_swept: bool,
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

    if allow_swept and prev_obj_pose is not None and prev_body_pose is not None:
        odx0, ody0 = shortest_toroidal_delta(
            float(prev_body_pose[0]),
            float(prev_body_pose[1]),
            float(prev_obj_pose[0]),
            float(prev_obj_pose[1]),
            width,
            height,
        )
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

    if endpoint_dist < 1e-12:
        nx, ny = 1.0, 0.0
        contact_point = [bx + br * nx, by + br * ny]
        contact_point_policy = "COINCIDENT_CENTRES_PLUS_X"
    else:
        nx, ny = dx / endpoint_dist, dy / endpoint_dist
        contact_point = [bx + nx * br, by + ny * br]
        contact_point_policy = "LINE_OF_CENTRES_BODY_SURFACE"
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
        "body_start_pose": list(prev_body_pose) if prev_body_pose else [bx, by],
        "object_start_pose": list(prev_obj_pose) if prev_obj_pose else [ox, oy],
        "body_geometry": body_contact_geometry(body, radius=br),
        "object_geometry": object_contact_geometry(
            obj, default_radius=cfg.default_object_collision_radius
        ),
        "contact_point": contact_point,
        "contact_point_policy": contact_point_policy,
        "object_physical_state": str(getattr(obj, "physical_state", "")),
        "holder_body_id": (
            str(obj.holder_body_id) if getattr(obj, "holder_body_id", None) else None
        ),
        "manipulator_id": (
            str(obj.manipulator_id) if getattr(obj, "manipulator_id", None) else None
        ),
        "held_object_id": held_object_id,
        "foreign_body_id": foreign_body_id,
    }


def _broad_phase_candidates(
    world: Any,
    held_objects: list[Any],
    foreign_bodies: list[tuple[str, Any]],
    *,
    width: int,
    height: int,
    cfg: HeldForeignBodyContactConfig,
) -> list[tuple[Any, str, Any]]:
    """Candidates: (held_obj, foreign_body_id, foreign_body)."""
    margin = int(cfg.broad_phase_cell_margin)
    max_reach = float(cfg.body_contact_radius) + float(cfg.default_object_collision_radius) + 2.0
    cell_r = max(margin, int(math.ceil(max_reach)) + margin)
    index = getattr(world, "spatial_contents", None)
    out: list[tuple[Any, str, Any]] = []
    seen: set[tuple[str, str]] = set()
    by_oid = {str(o.object_id): o for o in held_objects}

    for body_id, body in foreign_bodies:
        bx, by = float(body.x), float(body.y)
        bcx, bcy = int(math.floor(bx)) % width, int(math.floor(by)) % height
        candidate_objs = held_objects
        if index is not None and getattr(index, "by_cell", None) is not None:
            ids: set[str] = set()
            for dy in range(-cell_r, cell_r + 1):
                for dx in range(-cell_r, cell_r + 1):
                    cell = ((bcx + dx) % width, (bcy + dy) % height)
                    for ref in index.by_cell.get(cell, []) or []:
                        if getattr(ref, "entity_kind", None) == "RESOURCE_OBJECT":
                            ids.add(str(ref.entity_id))
            if ids:
                candidate_objs = [by_oid[i] for i in sorted(ids) if i in by_oid]
        for obj in candidate_objs:
            oid = str(obj.object_id)
            key = (oid, body_id)
            if key in seen:
                continue
            seen.add(key)
            out.append((obj, body_id, body))
    out.sort(key=lambda t: (str(t[0].object_id), t[1]))
    return out


def detect_held_resource_object_foreign_body_contacts(
    world: Any,
    bodies: list[tuple[str, Any]],
    *,
    tick: int,
    config: Any,
) -> dict[str, Any] | None:
    """One shared-world HELD↔foreign-body contact FACT. Read-only w.r.t. poses/velocities."""
    if not held_foreign_body_contact_is_active(config):
        return None
    st = ensure_held_foreign_body_contact_for_runtime(world, config)
    if st is None:
        return None
    te = int(tick)
    if te <= int(st.last_processed_tick):
        return st.last_step
    cfg = st.config
    height, width = int(world.T.shape[0]), int(world.T.shape[1])
    objects = list(getattr(world, "resource_objects", None) or [])
    bodies_sorted = sorted(
        [(str(bid), b) for bid, b in bodies if b is not None], key=lambda t: t[0]
    )
    body_ids = {bid for bid, _ in bodies_sorted}
    by_body = {bid: b for bid, b in bodies_sorted}

    tick_diagnostics: list[dict[str, Any]] = []

    # Eligible HELD objects with valid holder; invalid holder → diagnostic, no contact.
    held_objects: list[Any] = []
    for obj in objects:
        if str(getattr(obj, "physical_state", "")) != PHYSICAL_STATE_HELD:
            continue
        hid = getattr(obj, "holder_body_id", None)
        if not _valid_holder_body_id(hid, body_ids):
            st.counters["invalid_holder"] = int(st.counters.get("invalid_holder", 0)) + 1
            tick_diagnostics.append(
                {
                    "code": DIAG_INVALID_HOLDER,
                    "object_id": str(obj.object_id),
                    "holder_body_id": (str(hid) if hid is not None else None),
                    "tick": te,
                }
            )
            continue
        held_objects.append(obj)

    held_objects.sort(key=lambda o: str(o.object_id))
    candidates = _broad_phase_candidates(
        world, held_objects, bodies_sorted, width=width, height=height, cfg=cfg
    )

    # Always include currently active pairs to avoid false END.
    by_obj = {str(o.object_id): o for o in objects}
    seen_c = {(str(obj.object_id), bid) for obj, bid, _b in candidates}
    for pk, ep in list(st.active.items()):
        oid = str(ep.get("held_object_id") or ep.get("object_id"))
        bid = str(ep.get("foreign_body_id") or ep.get("body_id"))
        if (oid, bid) in seen_c:
            continue
        if oid in by_obj and bid in by_body:
            if str(getattr(by_obj[oid], "physical_state", "")) == PHYSICAL_STATE_HELD:
                candidates.append((by_obj[oid], bid, by_body[bid]))
                seen_c.add((oid, bid))
    candidates.sort(key=lambda row: (str(row[0].object_id), row[1]))
    st.counters["broad_candidates"] = int(st.counters.get("broad_candidates", 0)) + len(candidates)

    current_keys: set[str] = set()
    begin_receipts: list[dict[str, Any]] = []
    persist_rows: list[dict[str, Any]] = []
    end_receipts: list[dict[str, Any]] = []

    # Per-object transition policy (computed once).
    policy_by_oid: dict[str, str] = {}
    for obj in held_objects:
        oid = str(obj.object_id)
        holder = str(obj.holder_body_id)
        hand = str(getattr(obj, "manipulator_id", None) or "")
        prev = st.prev_held_identity.get(oid)
        policy = resolve_transition_policy(
            object_id=oid, holder_body_id=holder, manipulator_id=hand, prev=prev
        )
        policy_by_oid[oid] = policy
        if policy == TRANSITION_STABLE_HELD:
            st.counters["stable_held"] = int(st.counters.get("stable_held", 0)) + 1
        elif policy == TRANSITION_GRASP_SNAP_ENDPOINT_ONLY:
            st.counters["grasp_snap_endpoint_only"] = (
                int(st.counters.get("grasp_snap_endpoint_only", 0)) + 1
            )
        elif policy == TRANSITION_HOLDER_OR_HAND_CHANGE_ENDPOINT_ONLY:
            st.counters["holder_hand_change_endpoint_only"] = (
                int(st.counters.get("holder_hand_change_endpoint_only", 0)) + 1
            )
        else:
            st.counters["restore_missing_endpoint_only"] = (
                int(st.counters.get("restore_missing_endpoint_only", 0)) + 1
            )

    for obj, foreign_body_id, body in candidates:
        st.counters["narrow_checks"] = int(st.counters.get("narrow_checks", 0)) + 1
        oid = str(obj.object_id)
        holder = str(obj.holder_body_id) if getattr(obj, "holder_body_id", None) else None
        hand = str(obj.manipulator_id) if getattr(obj, "manipulator_id", None) else None

        # Self-exclusion: foreign body == holder → no episode.
        if holder is not None and str(foreign_body_id) == str(holder):
            st.counters["holder_self_excluded"] = (
                int(st.counters.get("holder_self_excluded", 0)) + 1
            )
            tick_diagnostics.append(
                {
                    "code": DIAG_HOLDER_SELF_EXCLUDED,
                    "object_id": oid,
                    "holder_body_id": holder,
                    "foreign_body_id": foreign_body_id,
                    "tick": te,
                }
            )
            continue

        pk = _pair_key(oid, foreign_body_id)
        policy = policy_by_oid.get(oid, TRANSITION_RESTORE_OR_MISSING_HISTORY_ENDPOINT_ONLY)
        allow_swept = policy == TRANSITION_STABLE_HELD
        prev_rec = st.prev_held_identity.get(oid)
        prev_obj = list(prev_rec["pose"]) if prev_rec and prev_rec.get("pose") else None
        # Only use held prev pose when STABLE_HELD (same holder+hand). Otherwise endpoint-only.
        if not allow_swept:
            prev_obj = None
        prev_body = st.prev_foreign_body_poses.get(foreign_body_id)

        m = measure_held_foreign_pair(
            held_object_id=oid,
            obj=obj,
            foreign_body_id=foreign_body_id,
            body=body,
            width=width,
            height=height,
            cfg=cfg,
            prev_obj_pose=prev_obj,
            prev_body_pose=prev_body if allow_swept else None,
            allow_swept=allow_swept,
        )
        m["transition_policy"] = policy
        m["pair_key"] = pk
        from mechanistic_mind.physical_system.flat_ground_gravity import (
            apply_vertical_filter_to_measurement,
        )
        apply_vertical_filter_to_measurement(
            world, config, m,
            a=body, b=obj, kind_a="body", kind_b="object",
            a_prev=prev_body, b_prev=prev_obj,
        )

        # Active pairs: ENDPOINT only (anti-t=0 like free B/O).
        if pk in st.active:
            m["in_contact"] = bool(m.get("endpoint_contact")) and bool(m.get("in_contact"))
            if m["in_contact"]:
                m["detection_mode"] = DETECTION_ENDPOINT
                m["swept_contact"] = False

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
            st.active[pk] = {
                "episode_id": eid,
                "held_object_id": oid,
                "foreign_body_id": foreign_body_id,
                "holder_body_id": holder,
                "manipulator_id": hand,
                "begin_tick": int(te),
                "last_tick": int(te),
                "detection_mode": m["detection_mode"],
                "transition_policy": policy,
            }
            st.counters["begin"] = int(st.counters.get("begin", 0)) + 1
            receipt = _receipt(te, phase, st.active[pk], m, cfg)
            begin_receipts.append(receipt)
        else:
            ep = st.active[pk]
            ep["last_tick"] = int(te)
            ep["detection_mode"] = m["detection_mode"]
            ep["holder_body_id"] = holder
            ep["manipulator_id"] = hand
            ep["transition_policy"] = policy
            phase = PHASE_PERSIST
            st.counters["persist"] = int(st.counters.get("persist", 0)) + 1
            persist_rows.append(_receipt(te, phase, ep, m, cfg))

    # ENDs for pairs no longer in contact / ineligible.
    for pk in sorted(set(st.active) - current_keys):
        ep = st.active.pop(pk)
        oid = str(ep.get("held_object_id"))
        bid = str(ep.get("foreign_body_id"))
        obj = by_obj.get(oid)
        body = by_body.get(bid)
        end_reason = END_SEPARATION
        if obj is None:
            end_reason = END_OBJECT_REMOVED
            st.counters["end_object_removed"] = int(st.counters.get("end_object_removed", 0)) + 1
        elif str(getattr(obj, "physical_state", "")) != PHYSICAL_STATE_HELD:
            end_reason = END_OBJECT_RELEASED
            st.counters["end_object_released"] = int(st.counters.get("end_object_released", 0)) + 1
        elif body is None:
            end_reason = END_FOREIGN_BODY_REMOVED
            st.counters["end_foreign_body_removed"] = (
                int(st.counters.get("end_foreign_body_removed", 0)) + 1
            )

        if obj is not None and body is not None:
            m = measure_held_foreign_pair(
                held_object_id=oid,
                obj=obj,
                foreign_body_id=bid,
                body=body,
                width=width,
                height=height,
                cfg=cfg,
                prev_obj_pose=None,
                prev_body_pose=None,
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
                "body_pose": None,
                "object_pose": None,
                "body_start_pose": None,
                "object_start_pose": None,
                "body_geometry": None,
                "object_geometry": None,
                "contact_point": None,
                "contact_point_policy": "UNAVAILABLE",
                "object_physical_state": (
                    str(getattr(obj, "physical_state", "")) if obj is not None else None
                ),
                "holder_body_id": ep.get("holder_body_id"),
                "manipulator_id": ep.get("manipulator_id"),
                "held_object_id": oid,
                "foreign_body_id": bid,
                "transition_policy": ep.get("transition_policy"),
            }
        m["end_reason"] = end_reason
        st.counters["end"] = int(st.counters.get("end", 0)) + 1
        end_receipts.append(_receipt(te, PHASE_END, ep, m, cfg, contact_fact=False))

    # Store poses / held identity for next tick.
    new_prev_held: dict[str, dict[str, Any]] = {}
    for obj in objects:
        if str(getattr(obj, "physical_state", "")) != PHYSICAL_STATE_HELD:
            continue
        hid = getattr(obj, "holder_body_id", None)
        if not _valid_holder_body_id(hid, body_ids):
            continue
        new_prev_held[str(obj.object_id)] = {
            "holder_body_id": str(hid),
            "manipulator_id": (
                str(obj.manipulator_id) if getattr(obj, "manipulator_id", None) else None
            ),
            "pose": [float(obj.x), float(obj.y)] + ([float(getattr(obj, "z", 0.0) or 0.0)] if hasattr(obj, "z") else []),
        }
    st.prev_held_identity = new_prev_held
    st.prev_foreign_body_poses = {
        bid: [float(b.x), float(b.y)] + ([float(getattr(b, "z", 0.0) or 0.0)] if hasattr(b, "z") else []) for bid, b in bodies_sorted
    }

    step = {
        "event": EVENT_STEP,
        "tick": te,
        "mechanism": MECHANISM_ID,
        "broad_phase_candidates": len(candidates),
        "narrow_phase_checks": len(candidates),
        "active_episodes": len(st.active),
        "begin": begin_receipts,
        "persist": persist_rows,
        "end": end_receipts,
        "diagnostics": list(tick_diagnostics),
        "swept_contact": SWEPT_CONTACT,
        "collision_response_applied": False,
        "impulse_transferred": False,
        "position_corrected": False,
        "velocity_changed": False,
        "sound_emitted": False,
        "damage_applied": False,
        "auto_release": False,
        "holder_mediation": False,
        "agent_accessible": False,
        "researcher_only": True,
    }
    st.last_step = step
    world.last_held_foreign_body_contact_step = step
    st.last_processed_tick = te
    st.diagnostics = (st.diagnostics + tick_diagnostics)[-int(cfg.history_limit) :]
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
    cfg: HeldForeignBodyContactConfig,
    *,
    contact_fact: bool | None = None,
) -> dict[str, Any]:
    cf = bool(m.get("in_contact")) if contact_fact is None else bool(contact_fact)
    if phase == PHASE_END:
        cf = False
    held_id = str(ep.get("held_object_id") or m.get("held_object_id"))
    foreign_id = str(ep.get("foreign_body_id") or m.get("foreign_body_id"))
    return {
        "receipt_kind": RECEIPT_KIND,
        "tick": int(tick),
        "contact_phase": phase,
        "episode_id": ep["episode_id"],
        "held_object_id": held_id,
        "foreign_body_id": foreign_id,
        "holder_body_id": ep.get("holder_body_id") or m.get("holder_body_id"),
        "manipulator_id": ep.get("manipulator_id") or m.get("manipulator_id"),
        "pair_key": _pair_key(held_id, foreign_id),
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
        "transition_policy": m.get("transition_policy") or ep.get("transition_policy"),
        "broad_phase_candidate": True,
        "narrow_phase_result": bool(m.get("in_contact")) if phase != PHASE_END else False,
        "contact_fact": cf,
        "collision_response_applied": False,
        "impulse_transferred": False,
        "position_corrected": False,
        "velocity_changed": False,
        "sound_emitted": False,
        "damage_applied": False,
        "auto_release": False,
        "holder_mediation": False,
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
                "held_object_id": v.get("held_object_id"),
                "foreign_body_id": v.get("foreign_body_id"),
                "holder_body_id": v.get("holder_body_id"),
                "manipulator_id": v.get("manipulator_id"),
                "detection_mode": v.get("detection_mode"),
                "transition_policy": v.get("transition_policy"),
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
        "overlay_caption": (
            "HELD OBJECT ↔ FOREIGN BODY CONTACT FACT · NO IMPULSE · NO DAMAGE · NO RELEASE · NO SOUND"
        ),
        "swept_contact": SWEPT_CONTACT,
        "agent_accessible": False,
        "researcher_only": True,
        "collision_response_applied": False,
        "impulse_transferred": False,
        "sound_emitted": False,
        "damage_applied": False,
        "auto_release": False,
        "holder_mediation": False,
    }


def overlay_payload(world: Any) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    objects = []
    for obj in list(getattr(world, "resource_objects", None) or []):
        if str(getattr(obj, "physical_state", "")) != PHYSICAL_STATE_HELD:
            continue
        objects.append(
            {
                "object_id": str(obj.object_id),
                "x": float(obj.x),
                "y": float(obj.y),
                "collision_radius": ensure_object_collision_radius(obj),
                "holder_body_id": (
                    str(obj.holder_body_id) if getattr(obj, "holder_body_id", None) else None
                ),
                "manipulator_id": (
                    str(obj.manipulator_id) if getattr(obj, "manipulator_id", None) else None
                ),
                "physical_state": PHYSICAL_STATE_HELD,
            }
        )
    return {
        "caption": (
            "HELD OBJECT ↔ FOREIGN BODY CONTACT FACT\n"
            "NO IMPULSE · NO DAMAGE · NO RELEASE · NO SOUND"
        ),
        "body_contact_radius": float(st.config.body_contact_radius),
        "held_objects": objects,
        "active": researcher_summary(world),
    }
