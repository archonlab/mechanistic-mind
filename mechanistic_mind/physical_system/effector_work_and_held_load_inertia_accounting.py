"""Acanthostega EFFECTOR WORK + HELD-LOAD INERTIA ACCOUNTING V1.

Preset: ACANTHOSTEGA_PHASE_B_EFFECTOR_WORK_ACCOUNTING
Mechanism: effector_work_and_held_load_inertia_accounting
Receipt: EFFECTOR_HELD_LOAD_WORK_ACCOUNTING

Parent: ACANTHOSTEGA_PHASE_B_HELD_OBJECT_TRANSLATIONAL_IMPULSE

Authoritative work source: body.mechanical_work_reservoir (same ledger as
action_work / motor_work / deformation_work). Held ResourceObject load inertia
only — NO arm mass. Empty hand: EMPTY_EFFECTOR_INERTIA_NOT_MODELLED.

Rotation: ROTATIONAL_WORK_NOT_ESTABLISHED (no swing eligibility).
Does NOT extend translational mediation eligibility. No swing impulse, damage,
sound, friction, or gravity.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from .motor_work import ke_increment, scale_positive_ke

MECHANISM_ID = "effector_work_and_held_load_inertia_accounting"
PROFILE_VERSION = "EFFECTOR_WORK_AND_HELD_LOAD_INERTIA_ACCOUNTING_PROFILE_V1"
STATE_SCHEMA = "EFFECTOR_WORK_AND_HELD_LOAD_INERTIA_ACCOUNTING_STATE_V1"
RECEIPT_KIND = "EFFECTOR_HELD_LOAD_WORK_ACCOUNTING"
EVENT_STEP = "EFFECTOR_HELD_LOAD_WORK_ACCOUNTING_STEP"
OVERLAY_CAPTION = (
    "EFFECTOR WORK + HELD-LOAD INERTIA ACCOUNTING V1 · NO ARM MASS · "
    "NO SWING IMPULSE · NO DAMAGE"
)

SOURCE_HOLDER_TRANSLATION = "holder_translation"
SOURCE_HOLDER_ROTATION = "holder_rotation"
SOURCE_RELATIVE_HAND = "relative_hand_actuation"
SOURCE_GRASP_SNAP = "grasp_snap"
SOURCE_CONSTRAINT = "constraint_correction"
SOURCE_RESTORE = "restore"

EMPTY_EFFECTOR = "EMPTY_EFFECTOR_INERTIA_NOT_MODELLED"
ROTATIONAL_NOT_ESTABLISHED = "ROTATIONAL_WORK_NOT_ESTABLISHED"
WORK_SOURCE_ID = "MECHANICAL_WORK_RESERVOIR"

MANIP_LEFT = "LEFT"
MANIP_RIGHT = "RIGHT"
BILATERAL_IDS = (MANIP_LEFT, MANIP_RIGHT)


@dataclass
class EffectorWorkHeldLoadConfig:
    enabled: bool = False
    history_limit: int = 64
    # Safety / scope flags (always fixed in V1 receipts).
    UNACCOUNTED_EFFECTOR_WORK_PRODUCES_IMPULSE: bool = False
    ACCOUNTED_EFFECTOR_WORK_PRODUCES_SWING_IMPULSE: bool = False
    EMPTY_EFFECTOR_INERTIA_MODELLED: bool = False
    ARM_MASS_MODELLED: bool = False
    ROTATIONAL_WORK_STATUS: str = ROTATIONAL_NOT_ESTABLISHED
    # Holder translation load: include held mass in locomotor KE metering.
    holder_translation_load_in_locomotor: bool = True
    # Relative hand (BRING_TOGETHER): KE admission replaces aperture proxy debit.
    relative_hand_ke_admission: bool = True
    phase_dot_epsilon: float = 1e-12

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "history_limit": int(self.history_limit),
            "UNACCOUNTED_EFFECTOR_WORK_PRODUCES_IMPULSE": False,
            "ACCOUNTED_EFFECTOR_WORK_PRODUCES_SWING_IMPULSE": False,
            "EMPTY_EFFECTOR_INERTIA_MODELLED": False,
            "ARM_MASS_MODELLED": False,
            "ROTATIONAL_WORK_STATUS": ROTATIONAL_NOT_ESTABLISHED,
            "holder_translation_load_in_locomotor": bool(
                self.holder_translation_load_in_locomotor
            ),
            "relative_hand_ke_admission": bool(self.relative_hand_ke_admission),
            "phase_dot_epsilon": float(self.phase_dot_epsilon),
            "profile_version": PROFILE_VERSION,
            "work_source": WORK_SOURCE_ID,
            "friction": False,
            "sound_emitted": False,
            "damage_applied": False,
            "swing_impulse": False,
            "gravity": False,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "EffectorWorkHeldLoadConfig":
        if not data:
            return cls()
        return cls(
            enabled=bool(data.get("enabled", False)),
            history_limit=int(data.get("history_limit", 64)),
            holder_translation_load_in_locomotor=bool(
                data.get("holder_translation_load_in_locomotor", True)
            ),
            relative_hand_ke_admission=bool(data.get("relative_hand_ke_admission", True)),
            phase_dot_epsilon=float(data.get("phase_dot_epsilon", 1e-12)),
        )


def effector_work_held_load_is_active(config: Any) -> bool:
    cfg = getattr(config, "effector_work_and_held_load_inertia_accounting", None)
    if cfg is None:
        return False
    if isinstance(cfg, dict):
        return bool(cfg.get("enabled"))
    return bool(getattr(cfg, "enabled", False))


def set_effector_work_held_load(config: Any, enabled: bool) -> None:
    on = bool(enabled)
    cur = getattr(config, "effector_work_and_held_load_inertia_accounting", None)
    if cur is None or isinstance(cur, dict):
        cfg = EffectorWorkHeldLoadConfig.from_dict(cur if isinstance(cur, dict) else None)
        cfg.enabled = on
        config.effector_work_and_held_load_inertia_accounting = cfg
    else:
        cur.enabled = on
    if on:
        # Parent chain: translational impulse mediation must stay available.
        from mechanistic_mind.physical_system.held_resource_object_translational_impulse_mediation import (
            set_held_translational_impulse,
        )

        set_held_translational_impulse(config, True)


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "config_path": "effector_work_and_held_load_inertia_accounting.enabled",
        "enabled": bool(enabled),
        "description": (
            "Acanthostega researcher-only effector work + held-load inertia "
            "accounting. Debits mechanical_work_reservoir for positive KE of "
            "held ResourceObject loads (no arm mass). BRING_TOGETHER aperture "
            "is admission-controlled. Rotation not established. No swing impulse."
        ),
        "agent_accessible": False,
        "work_source": WORK_SOURCE_ID,
        "arm_mass": False,
        "empty_effector_inertia": EMPTY_EFFECTOR,
        "rotational_work": ROTATIONAL_NOT_ESTABLISHED,
        "UNACCOUNTED_EFFECTOR_WORK_PRODUCES_IMPULSE": False,
        "ACCOUNTED_EFFECTOR_WORK_PRODUCES_SWING_IMPULSE": False,
        "friction": False,
        "sound": False,
        "damage": False,
        "swing_impulse": False,
    }


@dataclass
class HandAdmittedState:
    """Per-hand admitted relative velocity (body-lateral frame units / tick)."""

    v_rel: float = 0.0
    last_object_id: str | None = None
    last_source: str | None = None


@dataclass
class EffectorWorkHeldLoadState:
    config: EffectorWorkHeldLoadConfig
    # body_id -> hand_id -> HandAdmittedState
    per_hand: dict[str, dict[str, HandAdmittedState]] = field(default_factory=dict)
    receipt_seq: int = 0
    receipt_tick: int = -1
    last_step: dict[str, Any] | None = None
    history: list[dict[str, Any]] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=dict)


def _zero_counters() -> dict[str, int]:
    return {
        "steps": 0,
        "relative_hand_admissions": 0,
        "relative_hand_work_limited": 0,
        "relative_hand_work_unavailable": 0,
        "holder_translation_load_charges": 0,
        "empty_effector_skips": 0,
        "grasp_snap_no_work": 0,
        "rotation_not_established": 0,
        "restore_no_fake_work": 0,
        "constraint_no_fake_work": 0,
        "two_hand_proportional_scales": 0,
        "debits": 0,
        "overdraft_blocked": 0,
        "damage": 0,
        "sound": 0,
        "swing_impulse": 0,
    }


def state_of(world: Any) -> EffectorWorkHeldLoadState | None:
    return getattr(world, "effector_work_held_load_state", None)


def ensure_effector_work_held_load_for_runtime(
    world: Any, config: Any
) -> EffectorWorkHeldLoadState | None:
    if not effector_work_held_load_is_active(config):
        return None
    st = state_of(world)
    cfg = getattr(config, "effector_work_and_held_load_inertia_accounting", None)
    if not isinstance(cfg, EffectorWorkHeldLoadConfig):
        cfg = EffectorWorkHeldLoadConfig.from_dict(
            cfg.to_dict() if hasattr(cfg, "to_dict") else (cfg if isinstance(cfg, dict) else None)
        )
        cfg.enabled = True
        config.effector_work_and_held_load_inertia_accounting = cfg
    if st is None:
        st = EffectorWorkHeldLoadState(config=cfg, counters=_zero_counters())
        world.effector_work_held_load_state = st
    else:
        st.config = cfg
    return st


def serialize_state(st: EffectorWorkHeldLoadState | None) -> dict[str, Any] | None:
    if st is None:
        return None
    per_hand_out: dict[str, dict[str, dict[str, Any]]] = {}
    for bid, hands in sorted(st.per_hand.items()):
        per_hand_out[str(bid)] = {}
        for hid, hs in sorted(hands.items()):
            per_hand_out[str(bid)][str(hid)] = {
                "v_rel": float(hs.v_rel),
                "last_object_id": hs.last_object_id,
                "last_source": hs.last_source,
            }
    return {
        "schema_version": STATE_SCHEMA,
        "config": st.config.to_dict(),
        "per_hand": per_hand_out,
        "receipt_allocator": {
            "tick": int(st.receipt_tick),
            "next_sequence": int(st.receipt_seq),
        },
        "counters": dict(st.counters),
        "history": list(st.history)[-int(st.config.history_limit) :],
    }


def restore_state(
    world: Any, data: dict[str, Any] | None, config: Any
) -> EffectorWorkHeldLoadState | None:
    if not effector_work_held_load_is_active(config):
        world.effector_work_held_load_state = None
        return None
    if not isinstance(data, dict) or not data:
        st = ensure_effector_work_held_load_for_runtime(world, config)
        if st is not None:
            st.counters["restore_no_fake_work"] = (
                int(st.counters.get("restore_no_fake_work", 0)) + 1
            )
        return st
    if str(data.get("schema_version")) != STATE_SCHEMA:
        raise ValueError(
            f"unknown effector work held-load state schema: {data.get('schema_version')}"
        )
    cfg = EffectorWorkHeldLoadConfig.from_dict(data.get("config"))
    cfg.enabled = True
    alloc = data.get("receipt_allocator") or {}
    per_hand: dict[str, dict[str, HandAdmittedState]] = {}
    for bid, hands in (data.get("per_hand") or {}).items():
        per_hand[str(bid)] = {}
        for hid, hs in (hands or {}).items():
            if not isinstance(hs, dict):
                continue
            per_hand[str(bid)][str(hid)] = HandAdmittedState(
                v_rel=float(hs.get("v_rel") or 0.0),
                last_object_id=(
                    str(hs["last_object_id"]) if hs.get("last_object_id") is not None else None
                ),
                last_source=(
                    str(hs["last_source"]) if hs.get("last_source") is not None else None
                ),
            )
    st = EffectorWorkHeldLoadState(
        config=cfg,
        per_hand=per_hand,
        receipt_tick=int(alloc.get("tick", -1)),
        receipt_seq=int(alloc.get("next_sequence", 0)),
        history=list(data.get("history") or []),
        counters={
            **_zero_counters(),
            **{k: int(v) for k, v in (data.get("counters") or {}).items()},
        },
    )
    st.counters["restore_no_fake_work"] = int(st.counters.get("restore_no_fake_work", 0)) + 1
    world.effector_work_held_load_state = st
    config.effector_work_and_held_load_inertia_accounting = cfg
    return st


def _hand_state(
    st: EffectorWorkHeldLoadState, body_id: str, hand_id: str
) -> HandAdmittedState:
    bid = str(body_id)
    hid = str(hand_id)
    if bid not in st.per_hand:
        st.per_hand[bid] = {}
    if hid not in st.per_hand[bid]:
        st.per_hand[bid][hid] = HandAdmittedState()
    return st.per_hand[bid][hid]


def held_loads_for_holder(world: Any, holder_body_id: str) -> list[dict[str, Any]]:
    """Frozen snapshot of held loads (object_id, hand, mass). Sorted for determinism."""
    from .resource_objects import ensure_resource_object_state

    hid = str(holder_body_id or "")
    rows: list[dict[str, Any]] = []
    for obj in ensure_resource_object_state(world):
        if str(getattr(obj, "physical_state", "")) != "HELD":
            continue
        if str(getattr(obj, "holder_body_id", "") or "") != hid:
            continue
        mass = float(getattr(obj, "mass", 0.0) or 0.0)
        mid = str(getattr(obj, "manipulator_id", "") or "")
        rows.append(
            {
                "object_id": str(getattr(obj, "object_id", "")),
                "manipulator_id": mid,
                "mass": mass,
                "valid_mass": bool(mass > 0.0 and math.isfinite(mass)),
            }
        )
    rows.sort(key=lambda r: (r["manipulator_id"], r["object_id"]))
    return rows


def total_held_mass(world: Any, holder_body_id: str) -> float:
    return float(
        sum(r["mass"] for r in held_loads_for_holder(world, holder_body_id) if r["valid_mass"])
    )


def locomotor_mass_with_held_load(
    *,
    body_mass: float,
    world: Any,
    holder_body_id: str,
    config: Any,
) -> dict[str, Any]:
    """Effective translational mass for action/motor work when mechanism is ON."""
    m_body = float(body_mass)
    out = {
        "body_mass": m_body,
        "held_mass": 0.0,
        "effective_mass": m_body,
        "loads": [],
        "source": SOURCE_HOLDER_TRANSLATION,
        "accounting_active": False,
        "empty_policy": EMPTY_EFFECTOR,
    }
    if not effector_work_held_load_is_active(config):
        return out
    cfg = getattr(config, "effector_work_and_held_load_inertia_accounting", None)
    if isinstance(cfg, EffectorWorkHeldLoadConfig):
        if not cfg.holder_translation_load_in_locomotor:
            return out
    loads = held_loads_for_holder(world, holder_body_id)
    out["loads"] = loads
    out["accounting_active"] = True
    if not loads:
        return out
    m_held = float(sum(r["mass"] for r in loads if r["valid_mass"]))
    out["held_mass"] = m_held
    out["effective_mass"] = float(m_body + m_held)
    return out


def positive_relative_work_request(
    *,
    mass: float,
    v_rel_prev: float,
    v_rel_desired: float,
    phase_eps: float = 1e-12,
) -> dict[str, Any]:
    """Positive work to realize desired relative speed along the 1-D lateral axis.

    Brake (speed reduction / opposite-sign decay) dissipates — not recovered.
    New direction or speed increase requires fresh positive work = ΔK_rel when
    phase-detectable (dot product of prev and desired ≤ 0, or |v_des| > |v_prev|
    in the same direction).
    """
    m = max(0.0, float(mass))
    v0 = float(v_rel_prev)
    v1 = float(v_rel_desired)
    k0 = 0.5 * m * v0 * v0
    k1 = 0.5 * m * v1 * v1
    same_dir = (v0 * v1) > float(phase_eps)
    if abs(v1) <= abs(v0) + 1e-15 and (same_dir or abs(v1) <= 1e-15):
        # Pure brake or hold: dissipative, no positive work.
        return {
            "work_positive_requested": 0.0,
            "k_rel_before": float(k0),
            "k_rel_desired": float(k1),
            "phase": "BRAKE_OR_HOLD",
            "v_rel_prev": v0,
            "v_rel_desired": v1,
            "dissipated_not_recovered": float(max(0.0, k0 - k1)),
        }
    if not same_dir and abs(v0) > 1e-15 and abs(v1) > 1e-15:
        # Reverse: old KE dissipates; pay full new K_rel.
        return {
            "work_positive_requested": float(k1),
            "k_rel_before": float(k0),
            "k_rel_desired": float(k1),
            "phase": "REVERSE_FRESH_POSITIVE",
            "v_rel_prev": v0,
            "v_rel_desired": v1,
            "dissipated_not_recovered": float(k0),
        }
    # Same-direction accelerate (or start from rest).
    w = max(0.0, k1 - k0)
    return {
        "work_positive_requested": float(w),
        "k_rel_before": float(k0),
        "k_rel_desired": float(k1),
        "phase": "ACCELERATE" if abs(v0) > 1e-15 else "START_FROM_REST",
        "v_rel_prev": v0,
        "v_rel_desired": v1,
        "dissipated_not_recovered": 0.0,
    }


def allocate_proportional(w_avail: float, demands: list[float]) -> list[float]:
    """Order-independent proportional allocation. No NaN, no overdraft."""
    avail = max(0.0, float(w_avail))
    reqs = [max(0.0, float(d)) for d in demands]
    tot = sum(reqs)
    if tot <= 1e-15:
        return [0.0 for _ in reqs]
    if tot <= avail + 1e-15:
        return list(reqs)
    if avail <= 1e-15:
        return [0.0 for _ in reqs]
    scale = avail / tot
    out = [float(r * scale) for r in reqs]
    # Cap residual drift.
    s = sum(out)
    if s > avail + 1e-12:
        out = [float(x * avail / s) for x in out]
    return out


def _next_receipt_id(st: EffectorWorkHeldLoadState, tick: int) -> str:
    if st.receipt_tick != int(tick):
        st.receipt_tick = int(tick)
        st.receipt_seq = 0
    rid = f"ehl-{int(tick):08d}-{st.receipt_seq:03d}"
    st.receipt_seq += 1
    return rid


def note_grasp_attachment(
    world: Any,
    config: Any,
    *,
    body_id: str,
    hand_id: str,
    object_id: str | None,
    tick: int,
) -> dict[str, Any] | None:
    """GRASP: init attachment state; no snap trajectory work."""
    st = ensure_effector_work_held_load_for_runtime(world, config)
    if st is None:
        return None
    hs = _hand_state(st, body_id, hand_id)
    hs.v_rel = 0.0
    hs.last_object_id = str(object_id) if object_id is not None else None
    hs.last_source = SOURCE_GRASP_SNAP
    st.counters["grasp_snap_no_work"] = int(st.counters.get("grasp_snap_no_work", 0)) + 1
    return {
        "receipt_kind": RECEIPT_KIND,
        "event": "GRASP_ATTACHMENT_INIT",
        "source": SOURCE_GRASP_SNAP,
        "work_debit": 0.0,
        "body_id": str(body_id),
        "manipulator_id": str(hand_id),
        "object_id": object_id,
        "tick": int(tick),
        "note": "attachment init; no snap trajectory work",
    }


def note_rotation_not_established(
    world: Any, config: Any, *, body_id: str, tick: int
) -> None:
    st = ensure_effector_work_held_load_for_runtime(world, config)
    if st is None:
        return
    st.counters["rotation_not_established"] = (
        int(st.counters.get("rotation_not_established", 0)) + 1
    )


def admit_relative_hand_aperture(
    *,
    world: Any,
    body: Any,
    config: Any,
    body_id: str,
    runtime: Any,
    desired_delta_aperture: float,
    aperture_before: float,
    open_aperture: float,
    min_aperture: float,
    tick: int,
) -> dict[str, Any]:
    """Admission-control pair aperture using held-load relative KE.

    Desired Δaperture is frozen; LEFT/RIGHT demands allocated proportionally
    from mechanical_work_reservoir when insufficient. Empty hands skip inertia.
    """
    st = ensure_effector_work_held_load_for_runtime(world, config)
    cfg = st.config if st is not None else EffectorWorkHeldLoadConfig(enabled=True)
    d_des = float(desired_delta_aperture)
    ap0 = float(aperture_before)
    # Lateral speed per hand: each hand moves by 0.5 * Δaperture (opposite signs).
    # Sign convention: closing (d_des < 0) → hands move inward.
    # v_rel along +lateral for LEFT is +0.5*d_ap (RIGHT opposite). Work uses |v|.
    half = 0.5 * d_des
    loads = held_loads_for_holder(world, body_id)
    by_hand = {MANIP_LEFT: None, MANIP_RIGHT: None}
    for row in loads:
        mid = row["manipulator_id"]
        if mid in by_hand and by_hand[mid] is None:
            by_hand[mid] = row

    demands: list[dict[str, Any]] = []
    for mid, sign in ((MANIP_LEFT, 1.0), (MANIP_RIGHT, -1.0)):
        load = by_hand.get(mid)
        v_des = float(sign * half)  # body-lateral relative rate this tick
        if load is None or not load["valid_mass"]:
            if st is not None:
                st.counters["empty_effector_skips"] = (
                    int(st.counters.get("empty_effector_skips", 0)) + 1
                )
            demands.append(
                {
                    "manipulator_id": mid,
                    "object_id": None,
                    "mass": 0.0,
                    "v_rel_desired": v_des,
                    "work_positive_requested": 0.0,
                    "policy": EMPTY_EFFECTOR,
                    "phase_info": None,
                }
            )
            continue
        hs = _hand_state(st, body_id, mid) if st is not None else HandAdmittedState()
        # Object change → treat as fresh attachment (no inherited relative KE credit).
        if hs.last_object_id is not None and hs.last_object_id != load["object_id"]:
            hs.v_rel = 0.0
        phase = positive_relative_work_request(
            mass=float(load["mass"]),
            v_rel_prev=float(hs.v_rel),
            v_rel_desired=v_des,
            phase_eps=float(cfg.phase_dot_epsilon),
        )
        demands.append(
            {
                "manipulator_id": mid,
                "object_id": load["object_id"],
                "mass": float(load["mass"]),
                "v_rel_desired": v_des,
                "v_rel_prev": float(hs.v_rel),
                "work_positive_requested": float(phase["work_positive_requested"]),
                "policy": SOURCE_RELATIVE_HAND,
                "phase_info": phase,
            }
        )

    w_req_list = [float(d["work_positive_requested"]) for d in demands]
    w0 = float(getattr(body, "mechanical_work_reservoir", 0.0) or 0.0)
    w_alloc = allocate_proportional(w0, w_req_list)
    tot_req = float(sum(w_req_list))
    tot_alloc = float(sum(w_alloc))
    # Common aperture scale from the stricter hand (order-independent via min scale).
    scales = []
    for d, wa in zip(demands, w_alloc):
        wr = float(d["work_positive_requested"])
        if wr <= 1e-15:
            scales.append(1.0)
        else:
            scales.append(float(max(0.0, min(1.0, wa / wr))))
    scale = float(min(scales)) if scales else 1.0
    if tot_req > 1e-12 and any(s < 1.0 - 1e-9 for s in scales):
        # Recompute a single aperture scale that fits all allocated budgets.
        # Using min keeps both hands within their proportional share.
        if st is not None:
            st.counters["two_hand_proportional_scales"] = (
                int(st.counters.get("two_hand_proportional_scales", 0)) + 1
            )

    d_adm = float(d_des * scale)
    ap1 = ap0 + d_adm
    ap1 = float(max(float(min_aperture), min(float(open_aperture), ap1)))
    d_adm = float(ap1 - ap0)

    # Realize per-hand admitted relative velocity and debit exact positive work.
    half_adm = 0.5 * d_adm
    realized_rows: list[dict[str, Any]] = []
    debit_total = 0.0
    for d, sign in zip(demands, (1.0, -1.0)):
        mid = d["manipulator_id"]
        v_adm = float(sign * half_adm)
        wr = float(d["work_positive_requested"])
        if d["policy"] == EMPTY_EFFECTOR or float(d["mass"]) <= 0.0:
            if st is not None:
                hs = _hand_state(st, body_id, mid)
                hs.v_rel = float(v_adm)
                hs.last_source = SOURCE_RELATIVE_HAND
            realized_rows.append(
                {
                    **d,
                    "v_rel_admitted": v_adm,
                    "work_positive_allocated": 0.0,
                    "work_positive_realized": 0.0,
                    "work_limit_fraction": 1.0 if abs(d_des) <= 1e-15 else float(scale),
                }
            )
            continue
        hs = _hand_state(st, body_id, mid) if st is not None else HandAdmittedState()
        phase_adm = positive_relative_work_request(
            mass=float(d["mass"]),
            v_rel_prev=float(d.get("v_rel_prev") or hs.v_rel),
            v_rel_desired=v_adm,
            phase_eps=float(cfg.phase_dot_epsilon),
        )
        w_real = float(phase_adm["work_positive_requested"])
        # Hard cap: never overdraft.
        w_real = float(min(w_real, max(0.0, w0 - debit_total)))
        debit_total += w_real
        if st is not None:
            hs.v_rel = float(v_adm)
            hs.last_object_id = d.get("object_id")
            hs.last_source = SOURCE_RELATIVE_HAND
        realized_rows.append(
            {
                **d,
                "v_rel_admitted": v_adm,
                "work_positive_allocated": float(
                    w_alloc[BILATERAL_IDS.index(mid)] if mid in BILATERAL_IDS else 0.0
                ),
                "work_positive_realized": w_real,
                "work_limit_fraction": 1.0 if wr <= 1e-15 else float(min(1.0, w_real / wr)),
                "phase_admitted": phase_adm.get("phase"),
            }
        )

    if debit_total > w0 + 1e-12:
        debit_total = w0
        if st is not None:
            st.counters["overdraft_blocked"] = int(st.counters.get("overdraft_blocked", 0)) + 1
    body.mechanical_work_reservoir = max(0.0, w0 - debit_total)
    w1 = float(getattr(body, "mechanical_work_reservoir", 0.0) or 0.0)

    work_limited = bool(tot_req > 1e-12 and scale < 1.0 - 1e-6)
    work_unavailable = bool(tot_req > 1e-12 and debit_total <= 1e-12)
    if st is not None:
        st.counters["steps"] = int(st.counters.get("steps", 0)) + 1
        st.counters["relative_hand_admissions"] = (
            int(st.counters.get("relative_hand_admissions", 0)) + 1
        )
        if work_limited:
            st.counters["relative_hand_work_limited"] = (
                int(st.counters.get("relative_hand_work_limited", 0)) + 1
            )
        if work_unavailable:
            st.counters["relative_hand_work_unavailable"] = (
                int(st.counters.get("relative_hand_work_unavailable", 0)) + 1
            )
        if debit_total > 1e-12:
            st.counters["debits"] = int(st.counters.get("debits", 0)) + 1

    receipt = {
        "receipt_kind": RECEIPT_KIND,
        "receipt_id": _next_receipt_id(st, tick) if st is not None else f"ehl-{int(tick)}",
        "event": EVENT_STEP,
        "source": SOURCE_RELATIVE_HAND,
        "body_id": str(body_id),
        "tick": int(tick),
        "aperture_before": ap0,
        "aperture_desired_delta": d_des,
        "aperture_admitted_delta": d_adm,
        "aperture_after": ap1,
        "admission_scale": float(scale),
        "hands": realized_rows,
        "work_positive_requested_total": tot_req,
        "work_positive_allocated_total": tot_alloc,
        "work_debit": float(debit_total),
        "mechanical_work_reservoir_before": w0,
        "mechanical_work_reservoir_after": w1,
        "work_limited": work_limited,
        "work_unavailable": work_unavailable,
        "work_source": WORK_SOURCE_ID,
        "where_did_effector_work_come_from": (
            [WORK_SOURCE_ID] if debit_total > 1e-12 else []
        ),
        "UNACCOUNTED_EFFECTOR_WORK_PRODUCES_IMPULSE": False,
        "ACCOUNTED_EFFECTOR_WORK_PRODUCES_SWING_IMPULSE": False,
        "ROTATIONAL_WORK_STATUS": ROTATIONAL_NOT_ESTABLISHED,
        "ARM_MASS_MODELLED": False,
        "EMPTY_EFFECTOR_INERTIA_MODELLED": False,
        "agent_accessible": False,
        "damage_applied": False,
        "sound_emitted": False,
        "swing_impulse": False,
        "researcher_only": True,
        "negative_work_policy": "TRACKED_DISSIPATIVE_REMOVAL_NOT_RECOVERED",
    }
    if st is not None:
        st.last_step = receipt
        st.history.append(receipt)
        lim = int(st.config.history_limit)
        if len(st.history) > lim:
            st.history = st.history[-lim:]
        world.last_effector_work_held_load_step = receipt
    return receipt


def record_holder_translation_charge(
    world: Any,
    config: Any,
    *,
    body_id: str,
    held_mass: float,
    tick: int,
) -> None:
    st = ensure_effector_work_held_load_for_runtime(world, config)
    if st is None:
        return
    if float(held_mass) > 1e-15:
        st.counters["holder_translation_load_charges"] = (
            int(st.counters.get("holder_translation_load_charges", 0)) + 1
        )


def researcher_summary(world: Any) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    last = st.last_step or {}
    return {
        "mechanism": MECHANISM_ID,
        "profile_version": PROFILE_VERSION,
        "receipt_kind": RECEIPT_KIND,
        "overlay_caption": OVERLAY_CAPTION,
        "work_source": WORK_SOURCE_ID,
        "counters": dict(st.counters),
        "last_work_debit": last.get("work_debit"),
        "last_admission_scale": last.get("admission_scale"),
        "last_work_limited": last.get("work_limited"),
        "ROTATIONAL_WORK_STATUS": ROTATIONAL_NOT_ESTABLISHED,
        "UNACCOUNTED_EFFECTOR_WORK_PRODUCES_IMPULSE": False,
        "ACCOUNTED_EFFECTOR_WORK_PRODUCES_SWING_IMPULSE": False,
        "ARM_MASS_MODELLED": False,
        "EMPTY_EFFECTOR_INERTIA_MODELLED": False,
        "agent_accessible": False,
    }


def overlay_payload(world: Any) -> dict[str, Any] | None:
    summary = researcher_summary(world)
    if summary is None:
        return None
    return {
        "caption": OVERLAY_CAPTION,
        "active": summary,
    }
