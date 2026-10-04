"""Acanthostega HELD object translational impulse MEDIATION V1.

Preset: ACANTHOSTEGA_PHASE_B_HELD_OBJECT_TRANSLATIONAL_IMPULSE
Mechanism: held_resource_object_translational_impulse_mediation
Receipt: HELD_RESOURCE_OBJECT_FOREIGN_BODY_CONTACT_RESPONSE

Parent contact FACT stays authoritative. Fact-only preset must keep working
without this response. V1 applies impulse ONLY when contact-point approach is
explained by accounted holder body translational motion (effector relative work
within tolerance). No swing/rotation work ledger, no auto-release, no damage,
no held-object sound.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

MECHANISM_ID = "held_resource_object_translational_impulse_mediation"
PROFILE_VERSION = "HELD_RESOURCE_OBJECT_TRANSLATIONAL_IMPULSE_MEDIATION_PROFILE_V1"
STATE_SCHEMA = "HELD_RESOURCE_OBJECT_TRANSLATIONAL_IMPULSE_MEDIATION_STATE_V1"
RECEIPT_KIND = "HELD_RESOURCE_OBJECT_FOREIGN_BODY_CONTACT_RESPONSE"
EVENT_STEP = "HELD_RESOURCE_OBJECT_FOREIGN_BODY_CONTACT_RESPONSE_STEP"
SOLVER_PASS = "SINGLE_PASS_V1"
MULTI_CONTACT_POLICY = "ISOLATED_CONSTRAINT_COMPONENT_V1"
MASS_POLICY_ID = "HOLDER_PLUS_ALL_CARRIED_HELD_MASSES_V1"
OVERLAY_CAPTION = (
    "HELD OBJECT TRANSLATIONAL IMPULSE MEDIATION V1 · CONSTRAINED OBJECT → "
    "HOLDER BODY · NO SWING WORK · NO DAMAGE · NO RELEASE · NO SOUND"
)

PHYSICAL_STATE_HELD = "HELD"
DETECTION_SWEPT = "SWEPT_CROSSING"
DETECTION_ENDPOINT = "ENDPOINT_OVERLAP"

TRANSITION_STABLE_HELD = "STABLE_HELD"
TRANSITION_GRASP_SNAP_ENDPOINT_ONLY = "GRASP_SNAP_ENDPOINT_ONLY"
TRANSITION_HOLDER_OR_HAND_CHANGE_ENDPOINT_ONLY = "HOLDER_OR_HAND_CHANGE_ENDPOINT_ONLY"
TRANSITION_RESTORE_OR_MISSING_HISTORY_ENDPOINT_ONLY = "RESTORE_OR_MISSING_HISTORY_ENDPOINT_ONLY"

REASON_APPROACHING = "APPROACHING"
REASON_SEPARATING = "SEPARATING"
REASON_RESTING = "RESTING_NO_APPROACH"
REASON_INVALID_MASS = "INVALID_MASS"
REASON_ALREADY_PROCESSED = "ALREADY_PROCESSED"
REASON_BELOW_THRESHOLD = "BELOW_IMPULSE_THRESHOLD"
REASON_NO_CONTACT = "NO_CONTACT_FACT"
REASON_EFFECTOR_WORK = "EFFECTOR_WORK_NOT_ACCOUNTED"
REASON_GRASP_SNAP = "GRASP_SNAP_UNMEDIATED"
REASON_HOLDER_CHANGE = "HOLDER_CHANGE_UNMEDIATED"
REASON_HAND_CHANGE = "HAND_CHANGE_UNMEDIATED"
REASON_BRING_TOGETHER = "BRING_TOGETHER_WORK_NOT_ACCOUNTED"
REASON_MULTI_CONSTRAINT = "MULTI_CONSTRAINT_CONTACT_NOT_RESOLVED"
REASON_SWEPT_RECON = "SWEPT_CONSTRAINT_RECONSTRUCTION_NOT_ESTABLISHED"
REASON_NOT_STABLE = "TRANSITION_NOT_STABLE_HELD"
REASON_MEDIATION_ELIGIBLE = "TRANSLATIONALLY_MEDIATED"

NEUTRAL_COMPLIANCE = 0.5


@dataclass
class HeldTranslationalImpulseConfig:
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
    effector_unaccounted_speed_tolerance: float = 0.02
    effector_unaccounted_magnitude_tolerance: float = 0.05

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
            "effector_unaccounted_speed_tolerance": float(
                self.effector_unaccounted_speed_tolerance
            ),
            "effector_unaccounted_magnitude_tolerance": float(
                self.effector_unaccounted_magnitude_tolerance
            ),
            "profile_version": PROFILE_VERSION,
            "mass_policy": MASS_POLICY_ID,
            "multi_contact_policy": MULTI_CONTACT_POLICY,
            "solver_pass": SOLVER_PASS,
            "friction": False,
            "sound_emitted": False,
            "damage_applied": False,
            "automatic_release": False,
            "object_remains_held": True,
            "CARRIED_MASS_AFFECTS_CONTACT_RESPONSE": True,
            "CARRIED_MASS_DOES_NOT_YET_AFFECT_LOCOMOTOR_ACCELERATION": True,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "HeldTranslationalImpulseConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        ver = data.get("profile_version")
        if ver is not None and str(ver) != PROFILE_VERSION:
            raise ValueError(
                f"unknown held translational impulse mediation profile: {ver}"
            )
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
            position_correction_enabled=bool(
                data.get("position_correction_enabled", True)
            ),
            effector_unaccounted_speed_tolerance=float(
                data.get("effector_unaccounted_speed_tolerance", 0.02)
            ),
            effector_unaccounted_magnitude_tolerance=float(
                data.get("effector_unaccounted_magnitude_tolerance", 0.05)
            ),
        )


def held_translational_impulse_is_active(config: Any) -> bool:
    cfg = getattr(config, "held_resource_object_translational_impulse_mediation", None)
    return bool(cfg is not None and getattr(cfg, "enabled", False))


def set_held_translational_impulse(config: Any, enabled: bool) -> None:
    on = bool(enabled)
    cur = getattr(config, "held_resource_object_translational_impulse_mediation", None)
    if cur is None:
        config.held_resource_object_translational_impulse_mediation = (
            HeldTranslationalImpulseConfig(enabled=on)
        )
    else:
        cur.enabled = on
    if on:
        from mechanistic_mind.physical_system.held_resource_object_foreign_body_contact import (
            set_held_foreign_body_contact,
        )

        set_held_foreign_body_contact(config, True)


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "config_path": "held_resource_object_translational_impulse_mediation.enabled",
        "enabled": bool(enabled),
        "description": (
            "Acanthostega researcher-only held-object↔foreign-body translational "
            "impulse mediation. Impulse only when approach is accounted by holder "
            "CoM translation. No swing work, damage, release, or sound."
        ),
        "agent_accessible": False,
        "collision_response": True,
        "friction": False,
        "sound": False,
        "damage": False,
        "automatic_release": False,
        "object_remains_held": True,
        "mass_policy": MASS_POLICY_ID,
        "multi_contact_policy": MULTI_CONTACT_POLICY,
        "solver_pass": SOLVER_PASS,
        "CARRIED_MASS_AFFECTS_CONTACT_RESPONSE": True,
        "CARRIED_MASS_DOES_NOT_YET_AFFECT_LOCOMOTOR_ACCELERATION": True,
    }


@dataclass
class HeldTranslationalImpulseState:
    config: HeldTranslationalImpulseConfig
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
        "approaching": 0,
        "separating": 0,
        "resting": 0,
        "invalid_mass": 0,
        "already_processed": 0,
        "below_threshold": 0,
        "effector_work_unresolved": 0,
        "grasp_snap_unmediated": 0,
        "holder_hand_change_unmediated": 0,
        "bring_together_unmediated": 0,
        "multi_constraint_unresolved": 0,
        "swept_recon_not_established": 0,
        "translationally_eligible": 0,
        "clamped_impulse": 0,
        "grace_set": 0,
        "duplicate_processing": 0,
        "automatic_releases": 0,
        "damage": 0,
        "sound": 0,
    }


def state_of(world: Any) -> HeldTranslationalImpulseState | None:
    return getattr(world, "held_translational_impulse_state", None)


def ensure_held_translational_impulse_for_runtime(
    world: Any, config: Any
) -> HeldTranslationalImpulseState | None:
    if not held_translational_impulse_is_active(config):
        return None
    st = state_of(world)
    cfg = getattr(config, "held_resource_object_translational_impulse_mediation", None)
    if not isinstance(cfg, HeldTranslationalImpulseConfig):
        cfg = HeldTranslationalImpulseConfig.from_dict(
            cfg.to_dict() if hasattr(cfg, "to_dict") else (cfg if isinstance(cfg, dict) else None)
        )
        cfg.enabled = True
        config.held_resource_object_translational_impulse_mediation = cfg
    if st is None:
        st = HeldTranslationalImpulseState(config=cfg, counters=_zero_counters())
        world.held_translational_impulse_state = st
    else:
        st.config = cfg
    return st


def serialize_state(st: HeldTranslationalImpulseState | None) -> dict[str, Any] | None:
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
) -> HeldTranslationalImpulseState | None:
    if not held_translational_impulse_is_active(config):
        world.held_translational_impulse_state = None
        return None
    if not isinstance(data, dict) or not data:
        return ensure_held_translational_impulse_for_runtime(world, config)
    if str(data.get("schema_version")) != STATE_SCHEMA:
        raise ValueError(
            f"unknown held translational impulse state schema: {data.get('schema_version')}"
        )
    cfg = HeldTranslationalImpulseConfig.from_dict(data.get("config"))
    cfg.enabled = True
    alloc = data.get("response_allocator") or {}
    st = HeldTranslationalImpulseState(
        config=cfg,
        processed_keys=set(str(k) for k in (data.get("processed_keys") or [])),
        last_approach_signature={
            str(k): str(v)
            for k, v in (data.get("last_approach_signature") or {}).items()
        },
        response_tick=int(alloc.get("tick", -1)),
        response_seq=int(alloc.get("next_sequence", 0)),
        history=list(data.get("history") or []),
        counters={
            **_zero_counters(),
            **{k: int(v) for k, v in (data.get("counters") or {}).items()},
        },
    )
    world.held_translational_impulse_state = st
    config.held_resource_object_translational_impulse_mediation = cfg
    return st


def _alloc_seq(st: HeldTranslationalImpulseState, tick: int) -> int:
    if int(st.response_tick) != int(tick):
        st.response_tick = int(tick)
        st.response_seq = 0
    st.response_seq += 1
    return int(st.response_seq)


def _valid_mass(m: Any) -> bool:
    try:
        v = float(m)
    except (TypeError, ValueError):
        return False
    return bool(math.isfinite(v) and v > 0.0)


def _norm(dx: float, dy: float) -> float:
    return float(math.hypot(dx, dy))


def _set_grace(body: Any, ticks: int = 1) -> None:
    """Reuse B/O external-impulse grace seam so v_stop does not erase impact."""
    try:
        body._boc_impulse_grace_ticks = int(ticks)
    except Exception:
        pass


def _wrap_delta(ax: float, ay: float, bx: float, by: float, width: int, height: int) -> tuple[float, float]:
    from mechanistic_mind.physical_system.physical_body_resource_object_contact import (
        shortest_toroidal_delta,
    )

    return shortest_toroidal_delta(ax, ay, bx, by, width, height)


def _lerp_toroidal(
    x0: float, y0: float, x1: float, y1: float, t: float, width: int, height: int
) -> tuple[float, float]:
    from mechanistic_mind.planet.topology import wrap_coord

    dx, dy = _wrap_delta(x0, y0, x1, y1, width, height)
    return (
        float(wrap_coord(x0 + t * dx, width)),
        float(wrap_coord(y0 + t * dy, height)),
    )


def measured_held_velocity(
    *,
    object_start_pose: list[float] | None,
    object_end_pose: list[float] | None,
    width: int,
    height: int,
) -> tuple[float, float] | None:
    """WRAP-safe held pose delta / tick (scientific dt=1)."""
    if not object_start_pose or not object_end_pose:
        return None
    return _wrap_delta(
        float(object_start_pose[0]),
        float(object_start_pose[1]),
        float(object_end_pose[0]),
        float(object_end_pose[1]),
        width,
        height,
    )


def holder_translational_velocity(holder_body: Any) -> tuple[float, float]:
    return float(getattr(holder_body, "vx", 0.0) or 0.0), float(
        getattr(holder_body, "vy", 0.0) or 0.0
    )


def decompose_held_velocity(
    *,
    v_held: tuple[float, float],
    v_holder: tuple[float, float],
) -> tuple[float, float]:
    """v_effector_relative = v_held_measured - v_holder_translation (WRAP-safe vector subtract)."""
    return float(v_held[0] - v_holder[0]), float(v_held[1] - v_holder[1])


def classify_translational_mediation(
    *,
    transition_policy: str,
    v_held: tuple[float, float] | None,
    v_holder: tuple[float, float],
    contact_normal: tuple[float, float],
    cfg: HeldTranslationalImpulseConfig,
    bring_together_active: bool = False,
) -> dict[str, Any]:
    """Decide whether approach is translationally accounted."""
    out: dict[str, Any] = {
        "mediation_eligible": False,
        "refuse_reason": None,
        "v_held_measured": list(v_held) if v_held else None,
        "v_holder_translation": list(v_holder),
        "v_effector_relative": None,
        "accounted_normal_speed": None,
        "unaccounted_normal_speed": None,
        "unaccounted_magnitude": None,
        "tolerance_normal": float(cfg.effector_unaccounted_speed_tolerance),
        "tolerance_magnitude": float(cfg.effector_unaccounted_magnitude_tolerance),
        "classification": None,
    }
    pol = str(transition_policy or "")
    if pol == TRANSITION_GRASP_SNAP_ENDPOINT_ONLY:
        out["refuse_reason"] = REASON_GRASP_SNAP
        out["classification"] = REASON_GRASP_SNAP
        return out
    if pol == TRANSITION_HOLDER_OR_HAND_CHANGE_ENDPOINT_ONLY:
        out["refuse_reason"] = REASON_HOLDER_CHANGE
        out["classification"] = REASON_HOLDER_CHANGE
        return out
    if pol == TRANSITION_RESTORE_OR_MISSING_HISTORY_ENDPOINT_ONLY:
        out["refuse_reason"] = REASON_NOT_STABLE
        out["classification"] = REASON_NOT_STABLE
        return out
    if pol != TRANSITION_STABLE_HELD:
        out["refuse_reason"] = REASON_NOT_STABLE
        out["classification"] = REASON_NOT_STABLE
        return out
    if v_held is None:
        out["refuse_reason"] = REASON_EFFECTOR_WORK
        out["classification"] = REASON_EFFECTOR_WORK
        return out

    v_rel_eff = decompose_held_velocity(v_held=v_held, v_holder=v_holder)
    out["v_effector_relative"] = list(v_rel_eff)
    nx, ny = float(contact_normal[0]), float(contact_normal[1])
    rel_n = v_rel_eff[0] * nx + v_rel_eff[1] * ny
    held_n = v_held[0] * nx + v_held[1] * ny
    holder_n = v_holder[0] * nx + v_holder[1] * ny
    out["accounted_normal_speed"] = float(holder_n)
    out["unaccounted_normal_speed"] = float(rel_n)
    mag = _norm(v_rel_eff[0], v_rel_eff[1])
    out["unaccounted_magnitude"] = float(mag)

    # BRING_TOGETHER aperture motion is effector-relative by construction.
    if bring_together_active and mag > float(cfg.effector_unaccounted_magnitude_tolerance):
        out["refuse_reason"] = REASON_BRING_TOGETHER
        out["classification"] = REASON_BRING_TOGETHER
        return out

    tol_n = float(cfg.effector_unaccounted_speed_tolerance)
    tol_m = float(cfg.effector_unaccounted_magnitude_tolerance)
    if abs(rel_n) > tol_n or mag > tol_m:
        out["refuse_reason"] = REASON_EFFECTOR_WORK
        out["classification"] = REASON_EFFECTOR_WORK
        return out

    out["mediation_eligible"] = True
    out["classification"] = REASON_MEDIATION_ELIGIBLE
    out["held_normal_speed"] = float(held_n)
    return out


def constraint_mass_for_holder(
    world: Any,
    holder_body_id: str,
    holder_body_cfg: Any,
    *,
    contacting_object_id: str | None = None,
) -> dict[str, Any]:
    """m_constraint = holder_body_mass + sum(mass of ResourceObjects HELD by holder)."""
    m_holder = getattr(holder_body_cfg, "mass", None)
    holder_mass = float(m_holder) if _valid_mass(m_holder) else None
    contacting_mass = None
    other_carried: list[dict[str, Any]] = []
    total = 0.0
    valid = holder_mass is not None
    if holder_mass is not None:
        total += holder_mass
    for obj in list(getattr(world, "resource_objects", None) or []):
        if str(getattr(obj, "physical_state", "")) != PHYSICAL_STATE_HELD:
            continue
        if str(getattr(obj, "holder_body_id", None) or "") != str(holder_body_id):
            continue
        m = getattr(obj, "mass", None)
        oid = str(obj.object_id)
        if not _valid_mass(m):
            valid = False
            entry = {"object_id": oid, "mass": m, "valid": False}
        else:
            mf = float(m)
            total += mf
            entry = {"object_id": oid, "mass": mf, "valid": True}
        if contacting_object_id is not None and oid == str(contacting_object_id):
            contacting_mass = entry["mass"] if entry["valid"] else m
        else:
            other_carried.append(entry)
    return {
        "mass_policy": MASS_POLICY_ID,
        "holder_body_mass": holder_mass,
        "contacting_object_mass": contacting_mass,
        "other_carried_masses": other_carried,
        "total_constraint_mass": float(total) if valid else None,
        "valid": bool(valid and total > 0.0),
        "CARRIED_MASS_AFFECTS_CONTACT_RESPONSE": True,
        "CARRIED_MASS_DOES_NOT_YET_AFFECT_LOCOMOTOR_ACCELERATION": True,
    }


def contact_normal_held_to_foreign(
    meas: dict[str, Any],
    *,
    held_obj: Any,
    foreign_body: Any,
    width: int,
    height: int,
) -> tuple[float, float]:
    """Unit normal held object → foreign body.

    Contact FACT stores foreign→held displacement (body→object style); negate it.
    """
    disp = meas.get("shortest_toroidal_displacement")
    if disp is not None:
        dx, dy = -float(disp[0]), -float(disp[1])
    else:
        dx, dy = _wrap_delta(
            float(held_obj.x),
            float(held_obj.y),
            float(foreign_body.x),
            float(foreign_body.y),
            width,
            height,
        )
    dist = _norm(dx, dy)
    if dist < 1e-12:
        return 1.0, 0.0
    return float(dx) / dist, float(dy) / dist


def classify_constraint_components(
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Nodes = holder constraint systems + foreign bodies; edges = held/foreign contacts.

    Isolated V1 component: exactly 2 physical systems and 1 contact edge.
    Physical systems: one holder_constraint:<id> and one foreign body id.
    """
    # Union-find over system nodes
    parent: dict[str, str] = {}

    def _node_holder(hid: str) -> str:
        return f"holder_constraint:{hid}"

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    edges: list[dict[str, Any]] = []
    for row in candidates:
        hid = str(row.get("holder_body_id") or "")
        fid = str(row.get("foreign_body_id") or "")
        if not hid or not fid:
            continue
        na, nb = _node_holder(hid), fid
        union(na, nb)
        edges.append(row)

    comps: dict[str, dict[str, Any]] = {}
    for row in edges:
        hid = str(row.get("holder_body_id") or "")
        fid = str(row.get("foreign_body_id") or "")
        root = find(_node_holder(hid))
        slot = comps.setdefault(
            root,
            {"holder_ids": set(), "foreign_ids": set(), "edges": []},
        )
        slot["holder_ids"].add(hid)
        slot["foreign_ids"].add(fid)
        slot["edges"].append(row)

    out: list[dict[str, Any]] = []
    for root, slot in comps.items():
        holders = sorted(slot["holder_ids"])
        foreigns = sorted(slot["foreign_ids"])
        n_sys = len(holders) + len(foreigns)
        n_edge = len(slot["edges"])
        isolated = bool(n_sys == 2 and n_edge == 1 and len(holders) == 1 and len(foreigns) == 1)
        label = "|".join([*(f"H:{h}" for h in holders), *(f"F:{f}" for f in foreigns)])
        out.append(
            {
                "holder_ids": holders,
                "foreign_ids": foreigns,
                "edges": slot["edges"],
                "n_systems": n_sys,
                "n_edges": n_edge,
                "isolated_constraint_pair": isolated,
                "component_label": label,
            }
        )
    out.sort(key=lambda c: str(c["component_label"]))
    return out


def _prior_response_phases(world: Any, tick: int) -> list[str]:
    phases: list[str] = []
    for attr, name in (
        ("last_body_object_impulse_step", "body_resource_object_contact_impulse"),
        ("last_resource_object_pair_impulse_step", "resource_object_pair_contact_impulse"),
    ):
        step = getattr(world, attr, None)
        if isinstance(step, dict) and int(step.get("tick", -1)) == int(tick):
            phases.append(name)
    return phases


def _holder_rows_from_bodies(
    bodies: list[tuple[str, Any, Any]], config: Any
) -> list[dict[str, Any]]:
    """Build holders list for update_held_kinematics after pose correction."""
    rows = []
    for bid, body, _bcfg in bodies:
        rows.append(
            {
                "body_id": str(bid),
                "body": body,
                "config": config,
                "runtime": None,
            }
        )
    return rows


def _resnap_held(world: Any, bodies: list[tuple[str, Any, Any]], config: Any) -> None:
    from mechanistic_mind.physical_system.physical_manipulator import update_held_kinematics

    update_held_kinematics(world, _holder_rows_from_bodies(bodies, config))


def apply_held_resource_object_translational_impulse_mediation(
    world: Any,
    bodies: list[tuple[str, Any, Any]],
    *,
    tick: int,
    config: Any,
) -> dict[str, Any] | None:
    """Apply translational mediation AFTER held/foreign contact detect, before LPS.

    bodies: list of (body_id, body, body_cfg).
    """
    if not held_translational_impulse_is_active(config):
        return None
    from mechanistic_mind.physical_system.held_resource_object_foreign_body_contact import (
        held_foreign_body_contact_is_active,
    )
    from mechanistic_mind.physical_system.body_resource_object_contact_impulse import (
        object_compliance,
        restitution_from_compliance,
    )
    from mechanistic_mind.planet.topology import wrap_coord
    from mechanistic_mind.physical_system.physical_manipulator import bring_together_is_active

    if not held_foreign_body_contact_is_active(config):
        return None
    st = ensure_held_translational_impulse_for_runtime(world, config)
    if st is None:
        return None
    cfg = st.config
    contact_step = getattr(world, "last_held_foreign_body_contact_step", None)
    if not isinstance(contact_step, dict):
        return None

    height, width = int(world.T.shape[0]), int(world.T.shape[1])
    body_map = {str(bid): (b, bcfg) for bid, b, bcfg in bodies if b is not None}
    obj_map = {str(o.object_id): o for o in list(getattr(world, "resource_objects", None) or [])}
    bt_active = bool(bring_together_is_active(config))
    prior_phases = _prior_response_phases(world, tick)

    candidates: list[dict[str, Any]] = []
    for row in list(contact_step.get("begin") or []) + list(contact_step.get("persist") or []):
        if not isinstance(row, dict):
            continue
        if not bool(row.get("contact_fact")):
            continue
        oid = str(row.get("held_object_id") or "")
        obj = obj_map.get(oid)
        if obj is None or str(getattr(obj, "physical_state", "")) != PHYSICAL_STATE_HELD:
            continue
        candidates.append(row)

    components = classify_constraint_components(candidates)
    receipts: list[dict[str, Any]] = []
    any_position_changed = False

    for comp in components:
        if not comp["isolated_constraint_pair"]:
            seq = _alloc_seq(st, tick)
            response_key = f"multi:{comp['component_label']}:{int(tick)}:{seq}"
            st.counters["multi_constraint_unresolved"] = (
                int(st.counters.get("multi_constraint_unresolved", 0)) + 1
            )
            st.counters["responses"] = int(st.counters.get("responses", 0)) + 1
            receipt = {
                "receipt_kind": RECEIPT_KIND,
                "tick": int(tick),
                "response_id": response_key,
                "response_key": response_key,
                "response_seq": int(seq),
                "no_response_reason": REASON_MULTI_CONSTRAINT,
                "reason": REASON_MULTI_CONSTRAINT,
                "multi_contact_policy": MULTI_CONTACT_POLICY,
                "component_holder_ids": list(comp["holder_ids"]),
                "component_foreign_ids": list(comp["foreign_ids"]),
                "component_object_count": int(comp["n_systems"]),
                "component_edge_count": int(comp["n_edges"]),
                "component_label": comp["component_label"],
                "impulse_scalar_j": 0.0,
                "impulse_transferred": False,
                "collision_response_applied": False,
                "response_applied": False,
                "position_corrected": False,
                "velocity_changed": False,
                "object_remains_held": True,
                "automatic_release": False,
                "damage_applied": False,
                "sound_emitted": False,
                "solver_pass": SOLVER_PASS,
                "prior_response_phases_applied": list(prior_phases),
                "world_simultaneous_solution": False,
                "agent_accessible": False,
                "researcher_only": True,
                "mechanism": MECHANISM_ID,
                "preset_mechanism": MECHANISM_ID,
                "overlay_caption": OVERLAY_CAPTION,
            }
            receipts.append(receipt)
            st.processed_keys.add(response_key)
            st.history.append(receipt)
            continue

        meas = comp["edges"][0]
        oid = str(meas.get("held_object_id") or "")
        fid = str(meas.get("foreign_body_id") or "")
        hid = str(meas.get("holder_body_id") or "")
        hand = str(meas.get("manipulator_id") or "")
        episode_id = str(meas.get("episode_id") or "")
        pair_key = str(meas.get("pair_key") or f"{oid}|{fid}")
        seq = _alloc_seq(st, tick)
        response_key = f"{episode_id}:{int(tick)}:{seq}"

        obj = obj_map.get(oid)
        holder_pack = body_map.get(hid)
        foreign_pack = body_map.get(fid)
        if obj is None or holder_pack is None or foreign_pack is None:
            continue
        holder_body, holder_cfg = holder_pack
        foreign_body, foreign_cfg = foreign_pack

        # Dedupe
        tick_prefix = f"{episode_id}:{int(tick)}:"
        if any(k.startswith(tick_prefix) for k in st.processed_keys if not k.startswith("multi:")):
            # allow only first response per episode/tick
            already_impulse = any(
                k.startswith(tick_prefix) for k in st.processed_keys
            )
            if already_impulse:
                st.counters["already_processed"] = int(st.counters.get("already_processed", 0)) + 1
                st.counters["duplicate_processing"] = int(st.counters.get("duplicate_processing", 0)) + 1
                receipts.append(
                    _base_receipt(
                        tick, seq, response_key, meas, cfg,
                        reason=REASON_ALREADY_PROCESSED,
                        prior_phases=prior_phases,
                        extra={"mediation_eligible": False, "response_applied": False},
                    )
                )
                continue

        nx, ny = contact_normal_held_to_foreign(
            meas, held_obj=obj, foreign_body=foreign_body, width=width, height=height
        )
        # Measured held velocity from contact fact start/end poses (STABLE_HELD only has start)
        v_held = measured_held_velocity(
            object_start_pose=meas.get("object_start_pose"),
            object_end_pose=meas.get("object_end_pose") or [float(obj.x), float(obj.y)],
            width=width,
            height=height,
        )
        # Prefer CoM pose delta when available for WRAP-safe match to held measurement window
        h0 = None
        # Holder start pose is not in contact fact (fact stores foreign body start).
        # Use body.vx/vy as translational velocity (cells/tick).
        v_holder = holder_translational_velocity(holder_body)
        # If we have prev_held and can reconstruct: when STABLE and effector fixed in body frame,
        # holder translation ≈ held measured. Prefer also CoM delta from world prev if present.
        hfc_st = getattr(world, "held_foreign_body_contact_state", None)
        # Note: prev poses already advanced to current at end of detect — cannot re-read.
        # Use body.vx/vy which equals this tick's CoM displacement when displacement_enabled.

        mediation = classify_translational_mediation(
            transition_policy=str(meas.get("transition_policy") or ""),
            v_held=v_held,
            v_holder=v_holder,
            contact_normal=(nx, ny),
            cfg=cfg,
            bring_together_active=bt_active,
        )

        mass_info = constraint_mass_for_holder(
            world, hid, holder_cfg, contacting_object_id=oid
        )
        m_foreign_raw = getattr(foreign_cfg, "mass", None)
        foreign_mass_ok = _valid_mass(m_foreign_raw)
        mass_f = float(m_foreign_raw) if foreign_mass_ok else None

        compliance, compliance_note = object_compliance(obj, config)
        e = restitution_from_compliance(compliance, e_min=cfg.e_min, e_max=cfg.e_max)

        base_extra = {
            "contact_episode_id": episode_id,
            "contact_receipt_ref": {
                "episode_id": episode_id,
                "pair_key": pair_key,
                "tick": int(tick),
                "detection_mode": meas.get("detection_mode"),
            },
            "held_object_id": oid,
            "holder_body_id": hid,
            "hand": hand,
            "manipulator_id": hand,
            "foreign_body_id": fid,
            "transition_policy": meas.get("transition_policy"),
            "contact_mode": meas.get("detection_mode"),
            "contact_fraction": meas.get("contact_fraction"),
            "normal": [nx, ny],
            "contact_point": meas.get("contact_point"),
            **{k: mediation[k] for k in (
                "v_held_measured", "v_holder_translation", "v_effector_relative",
                "accounted_normal_speed", "unaccounted_normal_speed",
                "unaccounted_magnitude", "tolerance_normal", "tolerance_magnitude",
                "mediation_eligible", "classification",
            )},
            "holder_body_mass": mass_info["holder_body_mass"],
            "contacting_object_mass": mass_info["contacting_object_mass"],
            "other_carried_masses": mass_info["other_carried_masses"],
            "total_constraint_mass": mass_info["total_constraint_mass"],
            "mass_policy": MASS_POLICY_ID,
            "foreign_body_mass": mass_f,
            "compliance": float(compliance),
            "compliance_source": compliance_note,
            "restitution_e": float(e),
            "CARRIED_MASS_AFFECTS_CONTACT_RESPONSE": True,
            "CARRIED_MASS_DOES_NOT_YET_AFFECT_LOCOMOTOR_ACCELERATION": True,
            "provenance_chain": [
                "foreign_body",
                "held_object_contact_surface",
                "rigid_translational_constraint",
                "holder_body",
            ],
            "object_remains_held": True,
            "automatic_release": False,
            "damage_applied": False,
            "sound_emitted": False,
        }

        if not mediation["mediation_eligible"]:
            reason = str(mediation.get("refuse_reason") or REASON_EFFECTOR_WORK)
            _bump_refuse(st, reason)
            receipts.append(
                _base_receipt(
                    tick, seq, response_key, meas, cfg,
                    reason=reason,
                    prior_phases=prior_phases,
                    extra={**base_extra, "response_applied": False, "impulse_scalar_j": 0.0},
                )
            )
            st.processed_keys.add(response_key)
            continue

        st.counters["translationally_eligible"] = (
            int(st.counters.get("translationally_eligible", 0)) + 1
        )

        if not mass_info["valid"] or not foreign_mass_ok:
            st.counters["invalid_mass"] = int(st.counters.get("invalid_mass", 0)) + 1
            receipts.append(
                _base_receipt(
                    tick, seq, response_key, meas, cfg,
                    reason=REASON_INVALID_MASS,
                    prior_phases=prior_phases,
                    extra={**base_extra, "response_applied": False, "impulse_scalar_j": 0.0},
                )
            )
            st.processed_keys.add(response_key)
            continue

        mass_c = float(mass_info["total_constraint_mass"])
        mass_f = float(mass_f)

        # Swept: only if translationally mediated — reconstruct via CoM lerp + resnap
        detection_mode = str(meas.get("detection_mode") or "")
        swept_pose_set = False
        swept_recon_failed = False
        if detection_mode == DETECTION_SWEPT:
            frac = meas.get("contact_fraction")
            o0 = meas.get("object_start_pose")
            o1 = meas.get("object_end_pose")
            f0 = meas.get("body_start_pose")  # foreign
            f1 = meas.get("body_end_pose")
            if frac is None or not o0 or not o1 or not f0 or not f1:
                swept_recon_failed = True
            else:
                t = float(frac)
                # Foreign at TOI
                fx, fy = _lerp_toroidal(
                    float(f0[0]), float(f0[1]), float(f1[0]), float(f1[1]), t, width, height
                )
                # Held at TOI
                ox, oy = _lerp_toroidal(
                    float(o0[0]), float(o0[1]), float(o1[0]), float(o1[1]), t, width, height
                )
                # Holder CoM: since translationally mediated, held motion ≈ holder translation.
                # Reconstruct holder so effector lands on held TOI by translating CoM by
                # (held_toi - held_end) relative offset from current holder pose.
                # Current held is at end; current holder at end. Offset held_end→held_toi
                # applies equally to holder when effector-relative ≈ 0.
                d_hold_x, d_hold_y = _wrap_delta(
                    float(obj.x), float(obj.y), ox, oy, width, height
                )
                hx = float(wrap_coord(float(holder_body.x) + d_hold_x, width))
                hy = float(wrap_coord(float(holder_body.y) + d_hold_y, height))
                holder_body.x, holder_body.y = hx, hy
                foreign_body.x, foreign_body.y = fx, fy
                _resnap_held(world, bodies, config)
                # Verify contacting held landed near TOI
                dx_chk, dy_chk = _wrap_delta(float(obj.x), float(obj.y), ox, oy, width, height)
                if _norm(dx_chk, dy_chk) > 1e-3:
                    swept_recon_failed = True
                else:
                    swept_pose_set = True
                    any_position_changed = True
                    # Recompute normal at TOI poses
                    nx, ny = contact_normal_held_to_foreign(
                        {}, held_obj=obj, foreign_body=foreign_body, width=width, height=height
                    )

        if swept_recon_failed:
            st.counters["swept_recon_not_established"] = (
                int(st.counters.get("swept_recon_not_established", 0)) + 1
            )
            receipts.append(
                _base_receipt(
                    tick, seq, response_key, meas, cfg,
                    reason=REASON_SWEPT_RECON,
                    prior_phases=prior_phases,
                    extra={**base_extra, "response_applied": False, "impulse_scalar_j": 0.0,
                           "normal": [nx, ny]},
                )
            )
            st.processed_keys.add(response_key)
            continue

        # Velocities for impulse: constraint = holder translation; foreign = foreign body
        vhx0, vhy0 = float(holder_body.vx), float(holder_body.vy)
        vfx0, vfy0 = float(foreign_body.vx), float(foreign_body.vy)
        # Use accounted constraint velocity (holder translation), NOT full measured held velocity
        v_rel_x = vfx0 - vhx0
        v_rel_y = vfy0 - vhy0
        v_rel_n = v_rel_x * nx + v_rel_y * ny
        eps = float(cfg.approach_epsilon)
        approaching = v_rel_n < -eps
        separating = v_rel_n > eps
        resting = not approaching and not separating

        approach_sig = (
            "APPROACHING" if approaching else ("SEPARATING" if separating else "RESTING")
        )
        prev_sig = st.last_approach_signature.get(pair_key)
        if (
            not approaching
            and prev_sig == approach_sig
            and prev_sig in ("RESTING", "SEPARATING")
            and any(k.startswith(tick_prefix) for k in st.processed_keys)
        ):
            st.counters["already_processed"] = int(st.counters.get("already_processed", 0)) + 1
            receipts.append(
                _base_receipt(
                    tick, seq, response_key, meas, cfg,
                    reason=REASON_ALREADY_PROCESSED,
                    prior_phases=prior_phases,
                    extra={**base_extra, "response_applied": False, "relative_normal_velocity": v_rel_n},
                )
            )
            continue

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
            inv_sum = (1.0 / mass_c) + (1.0 / mass_f)
            j_raw = -(1.0 + e) * v_rel_n / inv_sum
            j = float(j_raw)
            if j > float(cfg.max_contact_impulse):
                j = float(cfg.max_contact_impulse)
                clamped = True
                st.counters["clamped_impulse"] = int(st.counters.get("clamped_impulse", 0)) + 1
            if abs(j) < float(cfg.impulse_threshold):
                reason = REASON_BELOW_THRESHOLD
                j = 0.0
                st.counters["below_threshold"] = int(st.counters.get("below_threshold", 0)) + 1
            else:
                reason = REASON_APPROACHING
                impulse_applied = True
                st.counters["approaching"] = int(st.counters.get("approaching", 0)) + 1

        dv_hx = dv_hy = dv_fx = dv_fy = 0.0
        if impulse_applied:
            dv_hx = -(j / mass_c) * nx
            dv_hy = -(j / mass_c) * ny
            dv_fx = +(j / mass_f) * nx
            dv_fy = +(j / mass_f) * ny
            holder_body.vx = float(holder_body.vx) + dv_hx
            holder_body.vy = float(holder_body.vy) + dv_hy
            foreign_body.vx = float(foreign_body.vx) + dv_fx
            foreign_body.vy = float(foreign_body.vy) + dv_fy
            # Clamp to body v_max if present
            for b, bcfg in ((holder_body, holder_cfg), (foreign_body, foreign_cfg)):
                vmax = float(getattr(bcfg, "v_max", 1.0) or 1.0)
                sp = math.hypot(float(b.vx), float(b.vy))
                if sp > vmax and sp > 1e-18:
                    s = vmax / sp
                    b.vx = float(b.vx) * s
                    b.vy = float(b.vy) * s
            _set_grace(holder_body, 1)
            _set_grace(foreign_body, 1)
            st.counters["impulses_applied"] = int(st.counters.get("impulses_applied", 0)) + 1
            st.counters["grace_set"] = int(st.counters.get("grace_set", 0)) + 1

        # Held object stays HELD; no independent velocity
        obj.vx = 0.0
        obj.vy = 0.0
        assert str(obj.physical_state) == PHYSICAL_STATE_HELD

        vhx1, vhy1 = float(holder_body.vx), float(holder_body.vy)
        vfx1, vfy1 = float(foreign_body.vx), float(foreign_body.vy)

        # Position correction (endpoint penetration), inverse-mass weighted
        corr_h = [0.0, 0.0]
        corr_f = [0.0, 0.0]
        position_corrected = False
        if cfg.position_correction_enabled and detection_mode != DETECTION_SWEPT:
            pen = float(meas.get("penetration") or 0.0)
            # Recompute penetration at current poses
            dx_hf, dy_hf = _wrap_delta(
                float(obj.x), float(obj.y), float(foreign_body.x), float(foreign_body.y),
                width, height,
            )
            # separation along held→foreign: distance - sum_r
            from mechanistic_mind.physical_system.physical_body_resource_object_contact import (
                BODY_CONTACT_RADIUS,
                CANONICAL_COLLISION_RADIUS,
                ensure_object_collision_radius,
            )
            br = float(BODY_CONTACT_RADIUS)
            orad = ensure_object_collision_radius(obj, CANONICAL_COLLISION_RADIUS)
            dist = _norm(dx_hf, dy_hf)
            sep = dist - (br + orad)
            pen = max(0.0, -sep)
            if pen > float(cfg.penetration_slop):
                depth = pen - float(cfg.penetration_slop)
                depth = min(depth, float(cfg.max_position_correction))
                inv_sum = (1.0 / mass_c) + (1.0 / mass_f)
                share_c = (1.0 / mass_c) / inv_sum
                share_f = (1.0 / mass_f) / inv_sum
                # Separate along normal held→foreign: move holder opposite to n, foreign along n
                # Holder pose change; then resnap all held
                corr_h = [-share_c * depth * nx, -share_c * depth * ny]
                corr_f = [share_f * depth * nx, share_f * depth * ny]
                holder_body.x = float(wrap_coord(float(holder_body.x) + corr_h[0], width))
                holder_body.y = float(wrap_coord(float(holder_body.y) + corr_h[1], height))
                foreign_body.x = float(wrap_coord(float(foreign_body.x) + corr_f[0], width))
                foreign_body.y = float(wrap_coord(float(foreign_body.y) + corr_f[1], height))
                _resnap_held(world, bodies, config)
                position_corrected = True
                any_position_changed = True
                st.counters["position_corrections"] = (
                    int(st.counters.get("position_corrections", 0)) + 1
                )

        ke_pre = 0.5 * mass_c * (vhx0 * vhx0 + vhy0 * vhy0) + 0.5 * mass_f * (
            vfx0 * vfx0 + vfy0 * vfy0
        )
        ke_post = 0.5 * mass_c * (vhx1 * vhx1 + vhy1 * vhy1) + 0.5 * mass_f * (
            vfx1 * vfx1 + vfy1 * vfy1
        )
        mom_pre = [mass_c * vhx0 + mass_f * vfx0, mass_c * vhy0 + mass_f * vfy0]
        mom_post = [mass_c * vhx1 + mass_f * vfx1, mass_c * vhy1 + mass_f * vfy1]
        mom_res = [mom_post[0] - mom_pre[0], mom_post[1] - mom_pre[1]]

        st.last_approach_signature[pair_key] = approach_sig
        st.processed_keys.add(response_key)
        st.counters["responses"] = int(st.counters.get("responses", 0)) + 1

        receipt = {
            "receipt_kind": RECEIPT_KIND,
            "tick": int(tick),
            "response_id": response_key,
            "response_key": response_key,
            "response_seq": int(seq),
            "reason": reason,
            "no_response_reason": (None if impulse_applied or position_corrected else reason),
            "impulse_scalar_j": float(j),
            "impulse_scalar_j_raw": float(j_raw),
            "impulse_clamped": bool(clamped),
            "impulse_holder": [float(dv_hx) * mass_c, float(dv_hy) * mass_c]
            if impulse_applied
            else [0.0, 0.0],
            "impulse_foreign": [float(dv_fx) * mass_f, float(dv_fy) * mass_f]
            if impulse_applied
            else [0.0, 0.0],
            "holder_delta_v": [float(dv_hx), float(dv_hy)],
            "foreign_delta_v": [float(dv_fx), float(dv_fy)],
            "velocity_holder_pre": [vhx0, vhy0],
            "velocity_foreign_pre": [vfx0, vfy0],
            "velocity_holder_post": [vhx1, vhy1],
            "velocity_foreign_post": [vfx1, vfy1],
            "relative_normal_velocity": float(v_rel_n),
            "momentum_before": mom_pre,
            "momentum_after": mom_post,
            "momentum_residual": mom_res,
            "ke_before": float(ke_pre),
            "ke_after": float(ke_post),
            "dissipated_energy": float(max(0.0, ke_pre - ke_post)),
            "correction_holder": corr_h,
            "correction_foreign": corr_f,
            "corrected_holder_pose": [float(holder_body.x), float(holder_body.y)],
            "corrected_foreign_pose": [float(foreign_body.x), float(foreign_body.y)],
            "corrected_held_pose": [float(obj.x), float(obj.y)],
            "position_corrected": bool(position_corrected),
            "swept_pose_set": bool(swept_pose_set),
            "impulse_transferred": bool(impulse_applied),
            "collision_response_applied": bool(impulse_applied or position_corrected),
            "response_applied": bool(impulse_applied or position_corrected),
            "velocity_changed": bool(impulse_applied),
            "grace_ticks_set": 1 if impulse_applied else 0,
            "isolated_constraint_pair": True,
            "multi_contact_policy": MULTI_CONTACT_POLICY,
            "solver_pass": SOLVER_PASS,
            "prior_response_phases_applied": list(prior_phases),
            "world_simultaneous_solution": False,
            "agent_accessible": False,
            "researcher_only": True,
            "mechanism": MECHANISM_ID,
            "preset_mechanism": MECHANISM_ID,
            "overlay_caption": OVERLAY_CAPTION,
            **base_extra,
            "normal": [nx, ny],
        }
        receipts.append(receipt)
        st.history.append(receipt)

    if any_position_changed:
        try:
            from mechanistic_mind.physical_system.spatial_contents import (
                multi_content_spatial_index_is_active,
                reconcile_contents,
            )

            if multi_content_spatial_index_is_active(config):
                body_refs = [(bid, b) for bid, b, _cfg in bodies]
                reconcile_contents(
                    world,
                    body_refs,
                    tick=int(tick),
                    reason="held_resource_object_translational_impulse_mediation",
                    config=config,
                )
        except Exception:
            pass

    lim = int(cfg.history_limit)
    if len(st.history) > lim:
        st.history = st.history[-lim:]

    step = {
        "event": EVENT_STEP,
        "tick": int(tick),
        "mechanism": MECHANISM_ID,
        "receipts": receipts,
        "responses": len(receipts),
        "impulses_applied": sum(1 for r in receipts if r.get("impulse_transferred")),
        "position_corrections": sum(1 for r in receipts if r.get("position_corrected")),
        "translationally_eligible": sum(
            1 for r in receipts if r.get("mediation_eligible")
        ),
        "effector_work_unresolved": sum(
            1 for r in receipts if r.get("reason") == REASON_EFFECTOR_WORK
        ),
        "multi_constraint_unresolved": sum(
            1 for r in receipts if r.get("reason") == REASON_MULTI_CONSTRAINT
        ),
        "solver_pass": SOLVER_PASS,
        "multi_contact_policy": MULTI_CONTACT_POLICY,
        "prior_response_phases_applied": prior_phases,
        "world_simultaneous_solution": False,
        "object_remains_held": True,
        "automatic_release": False,
        "damage_applied": False,
        "sound_emitted": False,
        "agent_accessible": False,
        "researcher_only": True,
        "overlay_caption": OVERLAY_CAPTION,
        "CARRIED_MASS_AFFECTS_CONTACT_RESPONSE": True,
        "CARRIED_MASS_DOES_NOT_YET_AFFECT_LOCOMOTOR_ACCELERATION": True,
        "counters": dict(st.counters),
    }
    st.last_step = step
    world.last_held_translational_impulse_step = step
    return step


def _bump_refuse(st: HeldTranslationalImpulseState, reason: str) -> None:
    st.counters["responses"] = int(st.counters.get("responses", 0)) + 1
    if reason == REASON_EFFECTOR_WORK:
        st.counters["effector_work_unresolved"] = (
            int(st.counters.get("effector_work_unresolved", 0)) + 1
        )
    elif reason == REASON_GRASP_SNAP:
        st.counters["grasp_snap_unmediated"] = (
            int(st.counters.get("grasp_snap_unmediated", 0)) + 1
        )
    elif reason in (REASON_HOLDER_CHANGE, REASON_HAND_CHANGE):
        st.counters["holder_hand_change_unmediated"] = (
            int(st.counters.get("holder_hand_change_unmediated", 0)) + 1
        )
    elif reason == REASON_BRING_TOGETHER:
        st.counters["bring_together_unmediated"] = (
            int(st.counters.get("bring_together_unmediated", 0)) + 1
        )


def _base_receipt(
    tick: int,
    seq: int,
    response_key: str,
    meas: dict[str, Any],
    cfg: HeldTranslationalImpulseConfig,
    *,
    reason: str,
    prior_phases: list[str],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    r = {
        "receipt_kind": RECEIPT_KIND,
        "tick": int(tick),
        "response_id": response_key,
        "response_key": response_key,
        "response_seq": int(seq),
        "reason": reason,
        "no_response_reason": reason,
        "held_object_id": meas.get("held_object_id"),
        "holder_body_id": meas.get("holder_body_id"),
        "hand": meas.get("manipulator_id"),
        "foreign_body_id": meas.get("foreign_body_id"),
        "transition_policy": meas.get("transition_policy"),
        "contact_mode": meas.get("detection_mode"),
        "impulse_scalar_j": 0.0,
        "impulse_transferred": False,
        "collision_response_applied": False,
        "response_applied": False,
        "position_corrected": False,
        "velocity_changed": False,
        "object_remains_held": True,
        "automatic_release": False,
        "damage_applied": False,
        "sound_emitted": False,
        "solver_pass": SOLVER_PASS,
        "multi_contact_policy": MULTI_CONTACT_POLICY,
        "prior_response_phases_applied": list(prior_phases),
        "world_simultaneous_solution": False,
        "agent_accessible": False,
        "researcher_only": True,
        "mechanism": MECHANISM_ID,
        "preset_mechanism": MECHANISM_ID,
        "overlay_caption": OVERLAY_CAPTION,
        "CARRIED_MASS_AFFECTS_CONTACT_RESPONSE": True,
        "CARRIED_MASS_DOES_NOT_YET_AFFECT_LOCOMOTOR_ACCELERATION": True,
    }
    if extra:
        r.update(extra)
    return r


def researcher_summary(world: Any) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    step = st.last_step or {}
    return {
        "mechanism": MECHANISM_ID,
        "last_step": {
            "tick": step.get("tick"),
            "responses": step.get("responses"),
            "impulses_applied": step.get("impulses_applied"),
            "translationally_eligible": step.get("translationally_eligible"),
            "effector_work_unresolved": step.get("effector_work_unresolved"),
            "multi_constraint_unresolved": step.get("multi_constraint_unresolved"),
        },
        "counters": dict(st.counters),
        "overlay_caption": OVERLAY_CAPTION,
        "agent_accessible": False,
        "researcher_only": True,
        "object_remains_held": True,
        "automatic_release": False,
        "damage_applied": False,
        "sound_emitted": False,
        "CARRIED_MASS_AFFECTS_CONTACT_RESPONSE": True,
        "CARRIED_MASS_DOES_NOT_YET_AFFECT_LOCOMOTOR_ACCELERATION": True,
    }


def overlay_payload(world: Any) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    step = st.last_step or {}
    markers = []
    for r in list(step.get("receipts") or []):
        if not isinstance(r, dict):
            continue
        markers.append(
            {
                "contact_point": r.get("contact_point"),
                "normal": r.get("normal"),
                "v_held_measured": r.get("v_held_measured"),
                "v_holder_translation": r.get("v_holder_translation"),
                "v_effector_relative": r.get("v_effector_relative"),
                "accounted_normal_speed": r.get("accounted_normal_speed"),
                "unaccounted_normal_speed": r.get("unaccounted_normal_speed"),
                "total_constraint_mass": r.get("total_constraint_mass"),
                "impulse_holder": r.get("impulse_holder"),
                "impulse_foreign": r.get("impulse_foreign"),
                "corrected_holder_pose": r.get("corrected_holder_pose"),
                "corrected_foreign_pose": r.get("corrected_foreign_pose"),
                "mediation_eligible": r.get("mediation_eligible"),
                "no_response_reason": r.get("no_response_reason") or r.get("reason"),
                "multi_constraint": r.get("reason") == REASON_MULTI_CONSTRAINT,
                "held_object_id": r.get("held_object_id"),
                "holder_body_id": r.get("holder_body_id"),
                "foreign_body_id": r.get("foreign_body_id"),
            }
        )
    return {
        "banner": OVERLAY_CAPTION,
        "markers": markers,
        "researcher_only": True,
        "agent_accessible": False,
    }
