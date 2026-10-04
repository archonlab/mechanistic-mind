"""Acanthostega FREE ResourceObject ↔ ResourceObject MASS + COMPLIANCE contact RESPONSE.

Preset: ACANTHOSTEGA_PHASE_B_OBJECT_OBJECT_IMPULSE
Mechanism: resource_object_pair_contact_impulse

Separate response module on top of OO contact FACT.
Contact detector stays authoritative for geometry; contact-fact-only preset
must keep working without this response.

Multi-contact Variant A: resolve ONLY isolated pairs (component with exactly
2 objects and exactly 1 edge). No sequential ID-ordered multi-body solver.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from mechanistic_mind.physical_system.body_resource_object_contact_impulse import (
    _clamp_speed,
    _valid_mass,
    contact_normal_from_displacement,
    object_compliance,
    restitution_from_compliance,
)

MECHANISM_ID = "resource_object_pair_contact_impulse"
PROFILE_VERSION = "RESOURCE_OBJECT_PAIR_CONTACT_IMPULSE_PROFILE_V1"
STATE_SCHEMA = "RESOURCE_OBJECT_PAIR_CONTACT_IMPULSE_STATE_V1"
RECEIPT_KIND = "RESOURCE_OBJECT_PAIR_CONTACT_RESPONSE"
EVENT_STEP = "RESOURCE_OBJECT_PAIR_CONTACT_RESPONSE_STEP"

COMPLIANCE_LAW = "SERIES_SOFTNESS_V1"
SOLVER_PASS = "SINGLE_PASS_V1"
MULTI_CONTACT_POLICY = "VARIANT_A_ISOLATED_PAIRS_ONLY"
REASON_MULTI_CONTACT = "MULTI_CONTACT_COMPONENT_NOT_RESOLVED"

REASON_APPROACHING = "APPROACHING"
REASON_SEPARATING = "SEPARATING"
REASON_RESTING = "RESTING_NO_APPROACH"
REASON_INVALID_MASS = "INVALID_MASS"
REASON_ALREADY_PROCESSED = "ALREADY_PROCESSED"
REASON_BELOW_THRESHOLD = "BELOW_IMPULSE_THRESHOLD"
REASON_NO_CONTACT = "NO_CONTACT_FACT"

PHYSICAL_STATE_FREE_STATIC = "FREE_STATIC"
PHYSICAL_STATE_FREE_MOVING = "FREE_MOVING"
PHYSICAL_STATE_HELD = "HELD"
FREE_STATES = (PHYSICAL_STATE_FREE_STATIC, PHYSICAL_STATE_FREE_MOVING)

DETECTION_SWEPT = "SWEPT_CROSSING"
DETECTION_ENDPOINT = "ENDPOINT_OVERLAP"

OVERLAY_CAPTION = (
    "OBJECT/OBJECT MASS + COMPLIANCE NORMAL RESPONSE · NO FRICTION · NO SOUND · "
    "MULTI-CONTACT: ISOLATED PAIRS ONLY"
)


@dataclass
class ResourceObjectPairContactImpulseConfig:
    enabled: bool = False
    approach_epsilon: float = 1e-9
    max_contact_impulse: float = 2.0
    penetration_slop: float = 0.02
    max_position_correction: float = 0.35
    e_min: float = 0.0
    e_max: float = 0.85
    impulse_threshold: float = 1e-12
    history_limit: int = 64
    position_correction_enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "approach_epsilon": float(self.approach_epsilon),
            "max_contact_impulse": float(self.max_contact_impulse),
            "penetration_slop": float(self.penetration_slop),
            "max_position_correction": float(self.max_position_correction),
            "e_min": float(self.e_min),
            "e_max": float(self.e_max),
            "impulse_threshold": float(self.impulse_threshold),
            "history_limit": int(self.history_limit),
            "position_correction_enabled": bool(self.position_correction_enabled),
            "profile_version": PROFILE_VERSION,
            "compliance_law": COMPLIANCE_LAW,
            "multi_contact_policy": MULTI_CONTACT_POLICY,
            "solver_pass": SOLVER_PASS,
            "friction": False,
            "sound_emitted": False,
            "tangential_impulse": False,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ResourceObjectPairContactImpulseConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        ver = data.get("profile_version")
        if ver is not None and str(ver) != PROFILE_VERSION:
            raise ValueError(f"unknown resource object pair contact impulse profile: {ver}")
        return cls(
            enabled=bool(data.get("enabled", False)),
            approach_epsilon=float(data.get("approach_epsilon", 1e-9)),
            max_contact_impulse=float(data.get("max_contact_impulse", 2.0)),
            penetration_slop=float(data.get("penetration_slop", 0.02)),
            max_position_correction=float(data.get("max_position_correction", 0.35)),
            e_min=float(data.get("e_min", 0.0)),
            e_max=float(data.get("e_max", 0.85)),
            impulse_threshold=float(data.get("impulse_threshold", 1e-12)),
            history_limit=int(data.get("history_limit", 64)),
            position_correction_enabled=bool(data.get("position_correction_enabled", True)),
        )


def resource_object_pair_impulse_is_active(config: Any) -> bool:
    cfg = getattr(config, "resource_object_pair_contact_impulse", None)
    return bool(cfg is not None and getattr(cfg, "enabled", False))


def set_resource_object_pair_impulse(config: Any, enabled: bool) -> None:
    on = bool(enabled)
    cur = getattr(config, "resource_object_pair_contact_impulse", None)
    if cur is None:
        config.resource_object_pair_contact_impulse = ResourceObjectPairContactImpulseConfig(enabled=on)
    else:
        cur.enabled = on
    if on:
        from mechanistic_mind.physical_system.physical_resource_object_pair_contact import (
            set_resource_object_pair_contact,
        )
        set_resource_object_pair_contact(config, True)


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "config_path": "resource_object_pair_contact_impulse.enabled",
        "enabled": bool(enabled),
        "description": (
            "Acanthostega researcher-only FREE ResourceObject↔ResourceObject "
            "mass+compliance normal contact RESPONSE (impulse + position correction). "
            "Isolated pairs only (Variant A). No friction/sound."
        ),
        "agent_accessible": False,
        "collision_response": True,
        "friction": False,
        "sound": False,
        "multi_contact_policy": MULTI_CONTACT_POLICY,
    }


def effective_compliance_series(c_a: float, c_b: float) -> float:
    """c_eff = 1 - (1-c_a)*(1-c_b); series softness, symmetric, bounded [0,1] if c in [0,1]."""
    a = float(c_a)
    b = float(c_b)
    if not math.isfinite(a):
        a = 0.5
    if not math.isfinite(b):
        b = 0.5
    a = max(0.0, min(1.0, a))
    b = max(0.0, min(1.0, b))
    return float(1.0 - (1.0 - a) * (1.0 - b))


@dataclass
class ResourceObjectPairContactImpulseState:
    config: ResourceObjectPairContactImpulseConfig
    processed_keys: set[str] = field(default_factory=set)
    last_approach_signature: dict[str, str] = field(default_factory=dict)
    response_seq: int = 0
    response_tick: int = -1
    last_step: dict[str, Any] | None = None
    history: list[dict[str, Any]] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=dict)


def _zero_counters() -> dict[str, int]:
    return {
        "responses": 0,
        "impulses_applied": 0,
        "position_corrections": 0,
        "separating": 0,
        "resting": 0,
        "already_processed": 0,
        "invalid_mass": 0,
        "below_threshold": 0,
        "swept_pose_set": 0,
        "multi_contact_unresolved": 0,
        "isolated_pairs_resolved": 0,
    }


def state_of(world: Any) -> ResourceObjectPairContactImpulseState | None:
    raw = getattr(world, "resource_object_pair_contact_impulse_state", None)
    return raw if isinstance(raw, ResourceObjectPairContactImpulseState) else None


def ensure_resource_object_pair_impulse_for_runtime(
    world: Any, config: Any
) -> ResourceObjectPairContactImpulseState | None:
    if not resource_object_pair_impulse_is_active(config):
        world.resource_object_pair_contact_impulse_state = None
        return None
    cfg = (
        getattr(config, "resource_object_pair_contact_impulse", None)
        or ResourceObjectPairContactImpulseConfig(enabled=True)
    )
    st = state_of(world)
    if st is None:
        st = ResourceObjectPairContactImpulseState(config=cfg, counters=_zero_counters())
        world.resource_object_pair_contact_impulse_state = st
    else:
        st.config = cfg
    return st


def copy_state(
    st: ResourceObjectPairContactImpulseState | None,
) -> ResourceObjectPairContactImpulseState | None:
    if st is None:
        return None
    return ResourceObjectPairContactImpulseState(
        config=ResourceObjectPairContactImpulseConfig.from_dict(st.config.to_dict()),
        processed_keys=set(st.processed_keys),
        last_approach_signature={k: str(v) for k, v in st.last_approach_signature.items()},
        response_seq=int(st.response_seq),
        response_tick=int(st.response_tick),
        last_step=dict(st.last_step) if st.last_step else None,
        history=[dict(h) for h in st.history],
        counters=dict(st.counters),
    )


def serialize_state(st: ResourceObjectPairContactImpulseState | None) -> dict[str, Any] | None:
    if st is None:
        return None
    return {
        "schema_version": STATE_SCHEMA,
        "config": st.config.to_dict(),
        "processed_keys": sorted(st.processed_keys),
        "last_approach_signature": {
            k: str(v) for k, v in sorted(st.last_approach_signature.items())
        },
        "response_allocator": {
            "tick": int(st.response_tick),
            "next_sequence": int(st.response_seq),
        },
        "counters": dict(st.counters),
        "history": list(st.history)[-int(st.config.history_limit) :],
    }


def restore_state(
    world: Any, data: dict[str, Any] | None, config: Any
) -> ResourceObjectPairContactImpulseState | None:
    if not resource_object_pair_impulse_is_active(config):
        world.resource_object_pair_contact_impulse_state = None
        return None
    if not isinstance(data, dict) or not data:
        return ensure_resource_object_pair_impulse_for_runtime(world, config)
    if str(data.get("schema_version")) != STATE_SCHEMA:
        raise ValueError(
            f"unknown resource object pair contact impulse state schema: {data.get('schema_version')}"
        )
    cfg = ResourceObjectPairContactImpulseConfig.from_dict(data.get("config"))
    cfg.enabled = True
    alloc = data.get("response_allocator") or {}
    st = ResourceObjectPairContactImpulseState(
        config=cfg,
        processed_keys=set(str(k) for k in (data.get("processed_keys") or [])),
        last_approach_signature={
            str(k): str(v) for k, v in (data.get("last_approach_signature") or {}).items()
        },
        response_tick=int(alloc.get("tick", -1)),
        response_seq=int(alloc.get("next_sequence", 0)),
        history=list(data.get("history") or []),
        counters={
            **_zero_counters(),
            **{k: int(v) for k, v in (data.get("counters") or {}).items()},
        },
    )
    world.resource_object_pair_contact_impulse_state = st
    config.resource_object_pair_contact_impulse = cfg
    return st


def _alloc_seq(st: ResourceObjectPairContactImpulseState, tick: int) -> int:
    if int(st.response_tick) != int(tick):
        st.response_tick = int(tick)
        st.response_seq = 0
    st.response_seq += 1
    return int(st.response_seq)


def _fok_thresholds(config: Any) -> tuple[float, float]:
    fok = getattr(config, "free_resource_object_kinematics", None)
    rest = float(getattr(fok, "rest_threshold", 0.01) or 0.01) if fok is not None else 0.01
    vmax = float(getattr(fok, "max_free_object_speed", 0.75) or 0.75) if fok is not None else 0.75
    if not math.isfinite(rest) or rest <= 0.0:
        rest = 0.01
    if not math.isfinite(vmax) or vmax <= 0.0:
        vmax = 0.75
    return rest, vmax


def _lerp_toroidal(
    ax: float, ay: float, bx: float, by: float, t: float, width: int, height: int
) -> tuple[float, float]:
    from mechanistic_mind.physical_system.physical_body_resource_object_contact import (
        shortest_toroidal_delta,
    )
    from mechanistic_mind.planet.topology import wrap_coord

    dx, dy = shortest_toroidal_delta(ax, ay, bx, by, width, height)
    x = float(wrap_coord(ax + float(t) * dx, width))
    y = float(wrap_coord(ay + float(t) * dy, height))
    return x, y


def _body_object_already_applied(world: Any, tick: int) -> bool:
    step = getattr(world, "last_body_object_contact_impulse_step", None) or getattr(
        world, "last_body_object_impulse_step", None
    )
    if not isinstance(step, dict):
        return False
    return int(step.get("tick", -1)) == int(tick)


def classify_contact_components(
    measurements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build undirected contact graph; return components (permutation-invariant).

    Each component dict:
      object_ids: sorted list
      edges: list of measurements (sorted by pair_key)
      n_objects, n_edges
      isolated_pair: True iff n_objects==2 and n_edges==1
      component_label: sorted object ids joined
    """
    # adjacency: oid -> set of neighbour oids; edge map pair_key -> meas
    adj: dict[str, set[str]] = {}
    edge_map: dict[str, dict[str, Any]] = {}
    for m in measurements:
        if not isinstance(m, dict) or not bool(m.get("contact_fact")):
            continue
        oa = str(m.get("object_id_a") or "")
        ob = str(m.get("object_id_b") or "")
        if not oa or not ob or oa == ob:
            continue
        pk = str(m.get("pair_key") or f"{min(oa, ob)}|{max(oa, ob)}")
        edge_map[pk] = m
        adj.setdefault(oa, set()).add(ob)
        adj.setdefault(ob, set()).add(oa)

    visited: set[str] = set()
    components: list[dict[str, Any]] = []
    for start in sorted(adj.keys()):
        if start in visited:
            continue
        # BFS
        queue = [start]
        visited.add(start)
        nodes: set[str] = set()
        while queue:
            u = queue.pop(0)
            nodes.add(u)
            for v in sorted(adj.get(u, ())):
                if v not in visited:
                    visited.add(v)
                    queue.append(v)
        obj_ids = sorted(nodes)
        # edges whose both endpoints are in this component
        edges = []
        for pk, meas in sorted(edge_map.items()):
            a = str(meas.get("object_id_a"))
            b = str(meas.get("object_id_b"))
            if a in nodes and b in nodes:
                edges.append(meas)
        n_obj = len(obj_ids)
        n_edge = len(edges)
        components.append(
            {
                "object_ids": obj_ids,
                "edges": edges,
                "n_objects": n_obj,
                "n_edges": n_edge,
                "isolated_pair": bool(n_obj == 2 and n_edge == 1),
                "component_label": "|".join(obj_ids),
            }
        )
    # Sort components by label for deterministic ordering (not physics order)
    components.sort(key=lambda c: str(c["component_label"]))
    return components


def apply_resource_object_pair_contact_impulse(
    world: Any,
    *,
    tick: int,
    config: Any,
    bodies: list[tuple[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Apply mass+compliance normal impulse AFTER OO contact detect.

    Uses post-B/O-response state. Does NOT re-run B/O detect after OO correction.
    Variant A: only isolated pairs resolve.
    """
    if not resource_object_pair_impulse_is_active(config):
        return None
    from mechanistic_mind.physical_system.physical_resource_object_pair_contact import (
        resource_object_pair_contact_is_active,
    )

    if not resource_object_pair_contact_is_active(config):
        return None
    st = ensure_resource_object_pair_impulse_for_runtime(world, config)
    if st is None:
        return None
    cfg = st.config
    contact_step = getattr(world, "last_resource_object_pair_contact_step", None)
    if not isinstance(contact_step, dict):
        return None

    height, width = int(world.T.shape[0]), int(world.T.shape[1])
    from mechanistic_mind.planet.topology import wrap_coord

    obj_map = {str(o.object_id): o for o in list(getattr(world, "resource_objects", None) or [])}
    rest_thr, max_obj_speed = _fok_thresholds(config)
    bo_applied = _body_object_already_applied(world, tick)

    candidates: list[dict[str, Any]] = []
    for row in list(contact_step.get("begin") or []) + list(contact_step.get("persist") or []):
        if not isinstance(row, dict):
            continue
        if not bool(row.get("contact_fact")):
            continue
        oa = str(row.get("object_id_a") or "")
        ob = str(row.get("object_id_b") or "")
        a = obj_map.get(oa)
        b = obj_map.get(ob)
        if a is None or b is None:
            continue
        if str(getattr(a, "physical_state", "")) not in FREE_STATES:
            continue
        if str(getattr(b, "physical_state", "")) not in FREE_STATES:
            continue
        candidates.append(row)

    components = classify_contact_components(candidates)
    receipts: list[dict[str, Any]] = []
    any_position_changed = False

    for comp in components:
        if not comp["isolated_pair"]:
            # MULTI_CONTACT: no impulse, no position correction
            seq = _alloc_seq(st, tick)
            response_key = f"multi:{comp['component_label']}:{int(tick)}:{seq}"
            st.counters["multi_contact_unresolved"] = (
                int(st.counters.get("multi_contact_unresolved", 0)) + 1
            )
            receipt = {
                "receipt_kind": RECEIPT_KIND,
                "tick": int(tick),
                "response_key": response_key,
                "response_seq": int(seq),
                "reason": REASON_MULTI_CONTACT,
                "multi_contact_policy": MULTI_CONTACT_POLICY,
                "component_object_ids": list(comp["object_ids"]),
                "component_object_count": int(comp["n_objects"]),
                "component_edge_count": int(comp["n_edges"]),
                "component_label": comp["component_label"],
                "impulse_scalar_j": 0.0,
                "impulse_transferred": False,
                "collision_response_applied": False,
                "position_corrected": False,
                "velocity_changed": False,
                "sound_emitted": False,
                "friction": False,
                "conservation_claimed": False,
                "solver_pass": SOLVER_PASS,
                "body_object_response_already_applied": bool(bo_applied),
                "agent_accessible": False,
                "researcher_only": True,
                "mechanism": MECHANISM_ID,
                "preset_mechanism": MECHANISM_ID,
                "overlay_caption": OVERLAY_CAPTION,
            }
            receipts.append(receipt)
            st.processed_keys.add(response_key)
            st.counters["responses"] = int(st.counters.get("responses", 0)) + 1
            st.history.append(receipt)
            continue

        # Isolated pair: exactly one edge
        meas = comp["edges"][0]
        oid_a = str(meas.get("object_id_a"))  # canonical min
        oid_b = str(meas.get("object_id_b"))  # canonical max
        episode_id = str(meas.get("episode_id") or "")
        pair_key = str(meas.get("pair_key") or f"{oid_a}|{oid_b}")
        seq = _alloc_seq(st, tick)
        response_key = f"{episode_id}:{int(tick)}:{seq}"

        obj_a = obj_map.get(oid_a)
        obj_b = obj_map.get(oid_b)
        if obj_a is None or obj_b is None:
            continue

        m_a = getattr(obj_a, "mass", None)
        m_b = getattr(obj_b, "mass", None)
        if not _valid_mass(m_a) or not _valid_mass(m_b):
            st.counters["invalid_mass"] = int(st.counters.get("invalid_mass", 0)) + 1
            receipts.append(
                _diag_receipt(
                    tick,
                    seq,
                    response_key,
                    meas,
                    cfg,
                    reason=REASON_INVALID_MASS,
                    obj_a=obj_a,
                    obj_b=obj_b,
                    config=config,
                    mass_a=m_a,
                    mass_b=m_b,
                    bo_applied=bo_applied,
                )
            )
            st.processed_keys.add(response_key)
            continue
        mass_a = float(m_a)
        mass_b = float(m_b)

        detection_mode = str(meas.get("detection_mode") or "")
        swept_pose_set = False
        if detection_mode == DETECTION_SWEPT:
            frac = meas.get("contact_fraction")
            a0 = meas.get("object_a_start_pose")
            a1 = meas.get("object_a_end_pose")
            b0 = meas.get("object_b_start_pose")
            b1 = meas.get("object_b_end_pose")
            if frac is not None and a0 and a1 and b0 and b1:
                t = float(frac)
                ax, ay = _lerp_toroidal(
                    float(a0[0]), float(a0[1]), float(a1[0]), float(a1[1]), t, width, height
                )
                bx, by = _lerp_toroidal(
                    float(b0[0]), float(b0[1]), float(b1[0]), float(b1[1]), t, width, height
                )
                obj_a.x, obj_a.y = ax, ay
                obj_b.x, obj_b.y = bx, by
                swept_pose_set = True
                any_position_changed = True
                st.counters["swept_pose_set"] = int(st.counters.get("swept_pose_set", 0)) + 1
                # Do NOT touch last_integrated_tick — leave FOK alone (no double-integrate)

        # Normal A→B from measurement displacement (canonical min→max)
        disp = meas.get("shortest_toroidal_displacement")
        if disp is None or swept_pose_set:
            from mechanistic_mind.physical_system.physical_body_resource_object_contact import (
                shortest_toroidal_delta,
            )

            dx, dy = shortest_toroidal_delta(
                float(obj_a.x), float(obj_a.y), float(obj_b.x), float(obj_b.y), width, height
            )
        else:
            dx, dy = float(disp[0]), float(disp[1])
        nx, ny = contact_normal_from_displacement(dx, dy)

        vax0 = float(getattr(obj_a, "vx", 0.0) or 0.0)
        vay0 = float(getattr(obj_a, "vy", 0.0) or 0.0)
        vbx0 = float(getattr(obj_b, "vx", 0.0) or 0.0)
        vby0 = float(getattr(obj_b, "vy", 0.0) or 0.0)
        v_rel_x = vbx0 - vax0
        v_rel_y = vby0 - vay0
        v_rel_n = v_rel_x * nx + v_rel_y * ny
        eps = float(cfg.approach_epsilon)

        approaching = v_rel_n < -eps
        separating = v_rel_n > eps
        resting = not approaching and not separating

        approach_sig = (
            "APPROACHING" if approaching else ("SEPARATING" if separating else "RESTING")
        )
        prev_sig = st.last_approach_signature.get(pair_key)
        already = False
        if response_key in st.processed_keys:
            already = True
        elif not approaching and prev_sig == approach_sig and prev_sig in ("RESTING", "SEPARATING"):
            tick_prefix = f"{episode_id}:{int(tick)}:"
            if any(k.startswith(tick_prefix) for k in st.processed_keys):
                already = True

        if already:
            st.counters["already_processed"] = int(st.counters.get("already_processed", 0)) + 1
            receipts.append(
                _diag_receipt(
                    tick,
                    seq,
                    response_key,
                    meas,
                    cfg,
                    reason=REASON_ALREADY_PROCESSED,
                    obj_a=obj_a,
                    obj_b=obj_b,
                    config=config,
                    normal=[nx, ny],
                    v_rel_n=v_rel_n,
                    mass_a=mass_a,
                    mass_b=mass_b,
                    pre_a=[vax0, vay0],
                    pre_b=[vbx0, vby0],
                    bo_applied=bo_applied,
                )
            )
            continue

        c_a, note_a = object_compliance(obj_a, config)
        c_b, note_b = object_compliance(obj_b, config)
        c_eff = effective_compliance_series(c_a, c_b)
        e = restitution_from_compliance(c_eff, e_min=cfg.e_min, e_max=cfg.e_max)

        j = 0.0
        j_raw = 0.0
        clamped = False
        reason = REASON_RESTING
        impulse_applied = False
        if separating:
            reason = REASON_SEPARATING
            st.counters["separating"] = int(st.counters.get("separating", 0)) + 1
        elif resting:
            reason = REASON_RESTING
            st.counters["resting"] = int(st.counters.get("resting", 0)) + 1
        else:
            inv_sum = (1.0 / mass_a) + (1.0 / mass_b)
            j_raw = -(1.0 + e) * v_rel_n / inv_sum
            j = float(j_raw)
            if j > float(cfg.max_contact_impulse):
                j = float(cfg.max_contact_impulse)
                clamped = True
            if abs(j) < float(cfg.impulse_threshold):
                reason = REASON_BELOW_THRESHOLD
                j = 0.0
                st.counters["below_threshold"] = int(st.counters.get("below_threshold", 0)) + 1
            else:
                reason = REASON_APPROACHING
                impulse_applied = True

        dv_ax = dv_ay = dv_bx = dv_by = 0.0
        if impulse_applied and j > 0.0:
            dv_ax = -(j / mass_a) * nx
            dv_ay = -(j / mass_a) * ny
            dv_bx = +(j / mass_b) * nx
            dv_by = +(j / mass_b) * ny
            obj_a.vx = float(getattr(obj_a, "vx", 0.0) or 0.0) + dv_ax
            obj_a.vy = float(getattr(obj_a, "vy", 0.0) or 0.0) + dv_ay
            obj_b.vx = float(getattr(obj_b, "vx", 0.0) or 0.0) + dv_bx
            obj_b.vy = float(getattr(obj_b, "vy", 0.0) or 0.0) + dv_by
            ovx, ovy, _ = _clamp_speed(float(obj_a.vx), float(obj_a.vy), max_obj_speed)
            obj_a.vx, obj_a.vy = ovx, ovy
            ovx, ovy, _ = _clamp_speed(float(obj_b.vx), float(obj_b.vy), max_obj_speed)
            obj_b.vx, obj_b.vy = ovx, ovy
            # Independent FREE_STATIC / FREE_MOVING per object
            if math.hypot(float(obj_a.vx), float(obj_a.vy)) >= rest_thr:
                obj_a.physical_state = PHYSICAL_STATE_FREE_MOVING
            else:
                obj_a.physical_state = PHYSICAL_STATE_FREE_STATIC
                obj_a.vx, obj_a.vy = 0.0, 0.0
            if math.hypot(float(obj_b.vx), float(obj_b.vy)) >= rest_thr:
                obj_b.physical_state = PHYSICAL_STATE_FREE_MOVING
            else:
                obj_b.physical_state = PHYSICAL_STATE_FREE_STATIC
                obj_b.vx, obj_b.vy = 0.0, 0.0
            try:
                from mechanistic_mind.physical_system.free_resource_object_static_traction_threshold import (
                    set_object_impulse_grace as _fost_grace,
                )
                _fost_grace(obj_a, 1)
                _fost_grace(obj_b, 1)
            except Exception:
                pass
            st.counters["impulses_applied"] = int(st.counters.get("impulses_applied", 0)) + 1

        vax1 = float(getattr(obj_a, "vx", 0.0) or 0.0)
        vay1 = float(getattr(obj_a, "vy", 0.0) or 0.0)
        vbx1 = float(getattr(obj_b, "vx", 0.0) or 0.0)
        vby1 = float(getattr(obj_b, "vy", 0.0) or 0.0)

        corr_a = [0.0, 0.0]
        corr_b = [0.0, 0.0]
        position_corrected = False
        penetration = float(meas.get("penetration") or 0.0)
        if (
            cfg.position_correction_enabled
            and detection_mode != DETECTION_SWEPT
            and penetration > float(cfg.penetration_slop)
        ):
            depth = penetration - float(cfg.penetration_slop)
            inv_sum = (1.0 / mass_a) + (1.0 / mass_b)
            corr_mag = min(float(cfg.max_position_correction), depth)
            share_a = (1.0 / mass_a) / inv_sum
            share_b = (1.0 / mass_b) / inv_sum
            ca = corr_mag * share_a
            cb = corr_mag * share_b
            obj_a.x = float(wrap_coord(float(obj_a.x) - ca * nx, width))
            obj_a.y = float(wrap_coord(float(obj_a.y) - ca * ny, height))
            obj_b.x = float(wrap_coord(float(obj_b.x) + cb * nx, width))
            obj_b.y = float(wrap_coord(float(obj_b.y) + cb * ny, height))
            corr_a = [-ca * nx, -ca * ny]
            corr_b = [cb * nx, cb * ny]
            position_corrected = True
            any_position_changed = True
            st.counters["position_corrections"] = int(st.counters.get("position_corrections", 0)) + 1

        ke_pre = 0.5 * mass_a * (vax0 * vax0 + vay0 * vay0) + 0.5 * mass_b * (
            vbx0 * vbx0 + vby0 * vby0
        )
        ke_post = 0.5 * mass_a * (vax1 * vax1 + vay1 * vay1) + 0.5 * mass_b * (
            vbx1 * vbx1 + vby1 * vby1
        )
        mom_pre = [mass_a * vax0 + mass_b * vbx0, mass_a * vay0 + mass_b * vby0]
        mom_post = [mass_a * vax1 + mass_b * vbx1, mass_a * vay1 + mass_b * vby1]
        mom_residual = [mom_post[0] - mom_pre[0], mom_post[1] - mom_pre[1]]
        residual_n = (
            ((vbx1 - vax1) * nx + (vby1 - vay1) * ny) if impulse_applied else v_rel_n
        )
        dissipated = float(max(0.0, ke_pre - ke_post))
        # Energy residual: post should not exceed pre (no KE creation); clamp noise
        energy_residual = float(ke_post - ke_pre)

        receipt = {
            "receipt_kind": RECEIPT_KIND,
            "tick": int(tick),
            "response_key": response_key,
            "response_seq": int(seq),
            "episode_id": episode_id,
            "object_id_a": oid_a,
            "object_id_b": oid_b,
            "pair_key": pair_key,
            "contact_phase": meas.get("contact_phase"),
            "detection_mode": detection_mode,
            "normal": [float(nx), float(ny)],
            "normal_sign_convention": "object_a_toward_object_b",
            "v_rel_n": float(v_rel_n),
            "approach_epsilon": float(eps),
            "reason": reason,
            "approaching": bool(approaching),
            "impulse_scalar_j": float(j),
            "impulse_scalar_j_raw": float(j_raw),
            "impulse_clamped": bool(clamped),
            "max_contact_impulse": float(cfg.max_contact_impulse),
            "impulse_vector_on_a": [
                float(-(j) * nx) if impulse_applied else 0.0,
                float(-(j) * ny) if impulse_applied else 0.0,
            ],
            "impulse_vector_on_b": [
                float(j * nx) if impulse_applied else 0.0,
                float(j * ny) if impulse_applied else 0.0,
            ],
            "delta_v_a": [float(dv_ax), float(dv_ay)],
            "delta_v_b": [float(dv_bx), float(dv_by)],
            "velocity_a_pre": [vax0, vay0],
            "velocity_a_post": [vax1, vay1],
            "velocity_b_pre": [vbx0, vby0],
            "velocity_b_post": [vbx1, vby1],
            "mass_a": float(mass_a),
            "mass_b": float(mass_b),
            "compliance_a": float(c_a),
            "compliance_b": float(c_b),
            "compliance_a_source": note_a,
            "compliance_b_source": note_b,
            "compliance_eff": float(c_eff),
            "compliance_law": COMPLIANCE_LAW,
            "restitution_e": float(e),
            "e_min": float(cfg.e_min),
            "e_max": float(cfg.e_max),
            "penetration": float(penetration),
            "penetration_slop": float(cfg.penetration_slop),
            "position_corrected": bool(position_corrected),
            "position_correction_a": corr_a,
            "position_correction_b": corr_b,
            "position_correction_is_numerical_constraint": True,
            "swept_pose_set": bool(swept_pose_set),
            "contact_fraction": meas.get("contact_fraction"),
            "ke_pair_pre": float(ke_pre),
            "ke_pair_post": float(ke_post),
            "ke_pair_delta": float(ke_post - ke_pre),
            "dissipated_energy": dissipated,
            "energy_residual": float(energy_residual),
            "momentum_pair_pre": mom_pre,
            "momentum_pair_post": mom_post,
            "momentum_residual": mom_residual,
            "residual_v_rel_n": float(residual_n),
            "conservation_claimed": bool(impulse_applied),
            "collision_response_applied": bool(
                impulse_applied or position_corrected or swept_pose_set
            ),
            "impulse_transferred": bool(impulse_applied),
            "velocity_changed": bool(impulse_applied),
            "sound_emitted": False,
            "friction": False,
            "tangential_impulse": False,
            "object_a_physical_state_post": str(getattr(obj_a, "physical_state", "")),
            "object_b_physical_state_post": str(getattr(obj_b, "physical_state", "")),
            "isolated_pair": True,
            "multi_contact_policy": MULTI_CONTACT_POLICY,
            "solver_pass": SOLVER_PASS,
            "body_object_response_already_applied": bool(bo_applied),
            "agent_accessible": False,
            "researcher_only": True,
            "mechanism": MECHANISM_ID,
            "preset_mechanism": MECHANISM_ID,
            "contact_fact_episode_id": episode_id,
            "overlay_caption": OVERLAY_CAPTION,
        }
        receipts.append(receipt)
        st.processed_keys.add(response_key)
        st.last_approach_signature[pair_key] = approach_sig
        st.counters["responses"] = int(st.counters.get("responses", 0)) + 1
        st.counters["isolated_pairs_resolved"] = (
            int(st.counters.get("isolated_pairs_resolved", 0)) + 1
        )
        st.history.append(receipt)

    lim = int(cfg.history_limit)
    if len(st.history) > lim:
        st.history = st.history[-lim:]
    if len(st.processed_keys) > 4096:
        keep = {
            k
            for k in st.processed_keys
            if f":{int(tick)}:" in k or f":{int(tick) - 1}:" in k
        }
        st.processed_keys = keep if keep else set(list(st.processed_keys)[-512:])

    if any_position_changed:
        try:
            from mechanistic_mind.physical_system.spatial_contents import (
                multi_content_spatial_index_is_active,
                reconcile_contents,
            )

            if multi_content_spatial_index_is_active(config):
                body_refs = list(bodies) if bodies else []
                if not body_refs:
                    # Best-effort: empty body list still reconciles objects
                    body_refs = []
                reconcile_contents(
                    world,
                    body_refs,
                    tick=int(tick),
                    reason="resource_object_pair_contact_impulse",
                    config=config,
                )
        except Exception:
            pass

    step = {
        "event": EVENT_STEP,
        "tick": int(tick),
        "mechanism": MECHANISM_ID,
        "responses": receipts,
        "response_count": len(receipts),
        "impulses_applied": sum(1 for r in receipts if r.get("impulse_transferred")),
        "position_corrections": sum(1 for r in receipts if r.get("position_corrected")),
        "multi_contact_unresolved": sum(
            1 for r in receipts if r.get("reason") == REASON_MULTI_CONTACT
        ),
        "isolated_pairs_resolved": sum(1 for r in receipts if r.get("isolated_pair")),
        "sound_emitted": False,
        "friction": False,
        "solver_pass": SOLVER_PASS,
        "multi_contact_policy": MULTI_CONTACT_POLICY,
        "body_object_response_already_applied": bool(bo_applied),
        "agent_accessible": False,
        "researcher_only": True,
        "overlay_caption": OVERLAY_CAPTION,
    }
    st.last_step = step
    world.last_resource_object_pair_contact_impulse_step = step
    return step


def _diag_receipt(
    tick: int,
    seq: int,
    response_key: str,
    meas: dict[str, Any],
    cfg: ResourceObjectPairContactImpulseConfig,
    *,
    reason: str,
    obj_a: Any,
    obj_b: Any,
    config: Any,
    normal: list[float] | None = None,
    v_rel_n: float | None = None,
    mass_a: Any = None,
    mass_b: Any = None,
    pre_a: list[float] | None = None,
    pre_b: list[float] | None = None,
    bo_applied: bool = False,
) -> dict[str, Any]:
    c_a, note_a = object_compliance(obj_a, config)
    c_b, note_b = object_compliance(obj_b, config)
    c_eff = effective_compliance_series(c_a, c_b)
    e = restitution_from_compliance(c_eff, e_min=cfg.e_min, e_max=cfg.e_max)
    return {
        "receipt_kind": RECEIPT_KIND,
        "tick": int(tick),
        "response_key": response_key,
        "response_seq": int(seq),
        "episode_id": meas.get("episode_id"),
        "object_id_a": meas.get("object_id_a"),
        "object_id_b": meas.get("object_id_b"),
        "pair_key": meas.get("pair_key"),
        "contact_phase": meas.get("contact_phase"),
        "detection_mode": meas.get("detection_mode"),
        "normal": normal,
        "v_rel_n": v_rel_n,
        "reason": reason,
        "approaching": False,
        "impulse_scalar_j": 0.0,
        "impulse_transferred": False,
        "collision_response_applied": False,
        "position_corrected": False,
        "velocity_changed": False,
        "sound_emitted": False,
        "friction": False,
        "conservation_claimed": False,
        "mass_a": (float(mass_a) if _valid_mass(mass_a) else mass_a),
        "mass_b": (float(mass_b) if _valid_mass(mass_b) else mass_b),
        "compliance_a": float(c_a),
        "compliance_b": float(c_b),
        "compliance_eff": float(c_eff),
        "compliance_law": COMPLIANCE_LAW,
        "restitution_e": float(e),
        "velocity_a_pre": pre_a
        or [
            float(getattr(obj_a, "vx", 0.0) or 0.0),
            float(getattr(obj_a, "vy", 0.0) or 0.0),
        ],
        "velocity_b_pre": pre_b
        or [
            float(getattr(obj_b, "vx", 0.0) or 0.0),
            float(getattr(obj_b, "vy", 0.0) or 0.0),
        ],
        "solver_pass": SOLVER_PASS,
        "body_object_response_already_applied": bool(bo_applied),
        "agent_accessible": False,
        "researcher_only": True,
        "mechanism": MECHANISM_ID,
        "preset_mechanism": MECHANISM_ID,
    }


def researcher_summary(world: Any) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    step = st.last_step or {}
    return {
        "mechanism": MECHANISM_ID,
        "last_step": {
            "tick": step.get("tick"),
            "response_count": step.get("response_count"),
            "impulses_applied": step.get("impulses_applied"),
            "position_corrections": step.get("position_corrections"),
            "multi_contact_unresolved": step.get("multi_contact_unresolved"),
            "isolated_pairs_resolved": step.get("isolated_pairs_resolved"),
        },
        "counters": dict(st.counters),
        "overlay_caption": OVERLAY_CAPTION,
        "multi_contact_policy": MULTI_CONTACT_POLICY,
        "compliance_law": COMPLIANCE_LAW,
        "agent_accessible": False,
        "researcher_only": True,
        "friction": False,
        "sound_emitted": False,
    }


def overlay_payload(world: Any) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    step = st.last_step or {}
    rows = []
    for r in list(step.get("responses") or [])[-8:]:
        rows.append(
            {
                "object_id_a": r.get("object_id_a"),
                "object_id_b": r.get("object_id_b"),
                "normal": r.get("normal"),
                "impulse_vector_on_a": r.get("impulse_vector_on_a"),
                "impulse_vector_on_b": r.get("impulse_vector_on_b"),
                "velocity_a_pre": r.get("velocity_a_pre"),
                "velocity_a_post": r.get("velocity_a_post"),
                "velocity_b_pre": r.get("velocity_b_pre"),
                "velocity_b_post": r.get("velocity_b_post"),
                "position_correction_a": r.get("position_correction_a"),
                "position_correction_b": r.get("position_correction_b"),
                "mass_a": r.get("mass_a"),
                "mass_b": r.get("mass_b"),
                "restitution_e": r.get("restitution_e"),
                "compliance_eff": r.get("compliance_eff"),
                "residual_v_rel_n": r.get("residual_v_rel_n"),
                "reason": r.get("reason"),
                "impulse_scalar_j": r.get("impulse_scalar_j"),
                "component_object_count": r.get("component_object_count"),
                "component_edge_count": r.get("component_edge_count"),
            }
        )
    return {
        "caption": (
            "OBJECT/OBJECT MASS + COMPLIANCE NORMAL RESPONSE\n"
            "NO FRICTION · NO SOUND · MULTI-CONTACT: ISOLATED PAIRS ONLY"
        ),
        "responses": rows,
        "summary": researcher_summary(world),
    }
