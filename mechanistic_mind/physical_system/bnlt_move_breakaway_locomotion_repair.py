"""Acanthostega Beta 4 · BNLT MOVE breakaway locomotion repair V1.

Mechanism: bnlt_move_breakaway_locomotion_repair
Preset: ACANTHOSTEGA_BETA4_BNLT_MOVE_BREAKAWAY_LOCOMOTION_REPAIR
Parent: ACANTHOSTEGA_BETA4_DETACHED_TERRAIN_MATERIAL_INITIAL_PLACEMENT
Profile: BNLT_MOVE_BREAKAWAY_LOCOMOTION_REPAIR_V1

Repairs force-aware kinetic residual during active MOVE:
  drive_accel := |J_move_limited| / (m_eff · dt)
instead of the legacy proxy |v_trial|/dt, which fails after Gentle env absorb
when speed_trial ≤ μ_k g dt even though |Δv_lim| = μ_s g > μ_k g.

Does not weaken μ_k, add displacement floors, or change Phase C / parent DTIP
when this mechanism is OFF.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

MECHANISM_ID = "bnlt_move_breakaway_locomotion_repair"
PROFILE_VERSION = "BNLT_MOVE_BREAKAWAY_LOCOMOTION_REPAIR_V1"
STATE_SCHEMA = "BNLT_MOVE_BREAKAWAY_LOCOMOTION_REPAIR_STATE_V1"
RECEIPT_KIND = "BNLT_MOVE_BREAKAWAY_LOCOMOTION_REPAIR"
BODY_ATTR_IMPULSE = "_bnlt_repair_move_impulse_xy"
BODY_ATTR_DV = "_bnlt_repair_move_dv_xy"

BANNER = (
    "BETA4 · BNLT MOVE BREAKAWAY LOCOMOTION REPAIR · "
    "ACTIVE-DRIVE drive_accel FROM CAPACITY-LIMITED MOVE IMPULSE · "
    "NO μ_k WEAKEN · NO MAGIC FLOOR · PHASE C / PARENT DTIP UNCHANGED WHEN OFF"
)

# Researcher classifications (not cognition tokens)
CLS_STATIC_HOLD = "STATIC_HOLD"
CLS_STATIC_BREAKAWAY = "STATIC_BREAKAWAY"
CLS_ACTIVE_DRIVE_TRANSLATION = "ACTIVE_DRIVE_TRANSLATION"
CLS_ACTIVE_DRIVE_BLOCKED_INSUFFICIENT = "ACTIVE_DRIVE_BLOCKED_INSUFFICIENT"
CLS_PASSIVE_KINETIC_BRAKING = "PASSIVE_KINETIC_BRAKING"
CLS_EXTERNAL_IMPULSE_RESPONSE = "EXTERNAL_IMPULSE_RESPONSE"
CLS_AIRBORNE_NOT_ELIGIBLE = "AIRBORNE_NOT_ELIGIBLE"
CLS_INACTIVE = "REPAIR_INACTIVE"


@dataclass
class BnltMoveBreakawayLocomotionRepairConfig:
    enabled: bool = False
    history_limit: int = 64

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "history_limit": int(self.history_limit),
            "profile_version": PROFILE_VERSION,
            "drive_accel_authority": "CAPACITY_LIMITED_MOVE_IMPULSE_OVER_M_EFF_DT",
            "mu_k_weakened": False,
            "magic_displacement_floor": False,
            "phase_c_behavior_when_off": "UNCHANGED",
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "BnltMoveBreakawayLocomotionRepairConfig":
        d = dict(data or {})
        return cls(
            enabled=bool(d.get("enabled", False)),
            history_limit=int(d.get("history_limit", 64)),
        )


def validate_config(cfg: BnltMoveBreakawayLocomotionRepairConfig) -> None:
    if int(cfg.history_limit) < 1:
        raise ValueError("history_limit must be >= 1")


def _line_ok(config: Any) -> bool:
    return config is not None and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"


def bnlt_move_breakaway_locomotion_repair_is_active(config: Any) -> bool:
    if not _line_ok(config):
        return False
    cfg = getattr(config, "bnlt_move_breakaway_locomotion_repair", None)
    return cfg is not None and bool(getattr(cfg, "enabled", False))


def set_bnlt_move_breakaway_locomotion_repair(config: Any, enabled: bool) -> None:
    if config is None:
        return
    on = bool(enabled) and _line_ok(config)
    cur = getattr(config, "bnlt_move_breakaway_locomotion_repair", None)
    if cur is None:
        if on:
            config.bnlt_move_breakaway_locomotion_repair = BnltMoveBreakawayLocomotionRepairConfig(
                enabled=True
            )
        return
    if isinstance(cur, dict):
        cfg = BnltMoveBreakawayLocomotionRepairConfig.from_dict(cur)
        cfg.enabled = on
        config.bnlt_move_breakaway_locomotion_repair = cfg
    else:
        cur.enabled = on


@dataclass
class BnltMoveBreakawayLocomotionRepairState:
    config: BnltMoveBreakawayLocomotionRepairConfig
    last_step: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    counters: dict[str, int] = field(
        default_factory=lambda: {
            "active_drive_ticks": 0,
            "translation_ticks": 0,
            "blocked_insufficient_ticks": 0,
            "legacy_proxy_bypassed": 0,
        }
    )


def state_of(world: Any) -> BnltMoveBreakawayLocomotionRepairState | None:
    raw = getattr(world, "bnlt_move_breakaway_locomotion_repair_state", None)
    return raw if isinstance(raw, BnltMoveBreakawayLocomotionRepairState) else None


def ensure_bnlt_move_breakaway_locomotion_repair_for_runtime(
    world: Any, config: Any
) -> BnltMoveBreakawayLocomotionRepairState | None:
    if not bnlt_move_breakaway_locomotion_repair_is_active(config):
        if state_of(world) is not None:
            world.bnlt_move_breakaway_locomotion_repair_state = None
        return None
    st = state_of(world)
    if st is not None:
        return st
    raw = getattr(config, "bnlt_move_breakaway_locomotion_repair", None)
    cfg = (
        BnltMoveBreakawayLocomotionRepairConfig.from_dict(
            raw.to_dict() if hasattr(raw, "to_dict") else raw
        )
        if raw is not None
        else BnltMoveBreakawayLocomotionRepairConfig(enabled=True)
    )
    cfg.enabled = True
    validate_config(cfg)
    st = BnltMoveBreakawayLocomotionRepairState(config=cfg)
    world.bnlt_move_breakaway_locomotion_repair_state = st
    return st


def stamp_move_impulse_on_body(
    body: Any,
    *,
    impulse_xy: tuple[float, float] | list[float],
    dv_xy: tuple[float, float] | list[float] | None = None,
) -> None:
    """Tick-local MOVE impulse authority for BNLT integrate (cleared after use)."""
    jx, jy = float(impulse_xy[0]), float(impulse_xy[1])
    setattr(body, BODY_ATTR_IMPULSE, (jx, jy))
    if dv_xy is not None:
        setattr(body, BODY_ATTR_DV, (float(dv_xy[0]), float(dv_xy[1])))


def clear_move_impulse_on_body(body: Any) -> None:
    for attr in (BODY_ATTR_IMPULSE, BODY_ATTR_DV):
        if hasattr(body, attr):
            try:
                delattr(body, attr)
            except Exception:
                setattr(body, attr, (0.0, 0.0))


def read_move_impulse_xy(body: Any) -> tuple[float, float]:
    raw = getattr(body, BODY_ATTR_IMPULSE, None)
    if not raw or not isinstance(raw, (tuple, list)) or len(raw) < 2:
        return (0.0, 0.0)
    return (float(raw[0]), float(raw[1]))


def active_drive_accel_from_impulse(
    *,
    move_impulse_xy: tuple[float, float] | list[float],
    m_eff: float,
    dt: float,
) -> float | None:
    """Authoritative locomotor drive acceleration for force-aware Coulomb residual."""
    jx, jy = float(move_impulse_xy[0]), float(move_impulse_xy[1])
    mag = float(math.hypot(jx, jy))
    m = float(m_eff)
    d = float(dt)
    if mag <= 1e-18 or m <= 1e-18 or d <= 1e-18:
        return None
    return mag / (m * d)


def classify_active_move_outcome(
    *,
    locomotor_active: bool,
    grounded: bool,
    external_ineligible: bool,
    displacement_mag: float,
    speed_after: float,
    drive_accel: float | None,
    friction_a: float | None,
    rest_transition: bool,
    state_class: str | None,
) -> str:
    if external_ineligible:
        return CLS_EXTERNAL_IMPULSE_RESPONSE
    if not grounded:
        return CLS_AIRBORNE_NOT_ELIGIBLE
    if not locomotor_active:
        if str(state_class or "") == "STATIC_HOLD":
            return CLS_STATIC_HOLD
        if str(state_class or "") == "STATIC_BREAKAWAY":
            return CLS_STATIC_BREAKAWAY
        return CLS_PASSIVE_KINETIC_BRAKING
    if displacement_mag > 1e-12 or speed_after > 1e-12:
        return CLS_ACTIVE_DRIVE_TRANSLATION
    if (
        drive_accel is not None
        and friction_a is not None
        and float(drive_accel) <= float(friction_a) + 1e-15
        and rest_transition
    ):
        return CLS_ACTIVE_DRIVE_BLOCKED_INSUFFICIENT
    if rest_transition:
        return CLS_ACTIVE_DRIVE_BLOCKED_INSUFFICIENT
    return CLS_ACTIVE_DRIVE_TRANSLATION


def record_repair_step(
    world: Any,
    config: Any,
    *,
    receipt: dict[str, Any],
) -> dict[str, Any]:
    st = ensure_bnlt_move_breakaway_locomotion_repair_for_runtime(world, config)
    if st is None:
        return dict(receipt)
    st.last_step = dict(receipt)
    st.history.append(dict(receipt))
    lim = int(st.config.history_limit)
    if len(st.history) > lim:
        st.history = st.history[-lim:]
    cls = str(receipt.get("classification") or "")
    st.counters["active_drive_ticks"] = int(st.counters.get("active_drive_ticks", 0)) + 1
    st.counters["legacy_proxy_bypassed"] = int(st.counters.get("legacy_proxy_bypassed", 0)) + 1
    if cls == CLS_ACTIVE_DRIVE_TRANSLATION:
        st.counters["translation_ticks"] = int(st.counters.get("translation_ticks", 0)) + 1
    elif cls == CLS_ACTIVE_DRIVE_BLOCKED_INSUFFICIENT:
        st.counters["blocked_insufficient_ticks"] = int(
            st.counters.get("blocked_insufficient_ticks", 0)
        ) + 1
    world.last_bnlt_move_breakaway_repair = dict(receipt)
    return dict(receipt)


def serialize_state(st: BnltMoveBreakawayLocomotionRepairState | None) -> dict[str, Any] | None:
    if st is None:
        return None
    return {
        "schema": STATE_SCHEMA,
        "config": st.config.to_dict(),
        "last_step": dict(st.last_step) if st.last_step else {},
        "history": list(st.history[-int(st.config.history_limit) :]),
        "counters": {k: int(v) for k, v in st.counters.items()},
    }


def restore_state(
    world: Any, data: dict[str, Any] | None, config: Any
) -> BnltMoveBreakawayLocomotionRepairState | None:
    if not bnlt_move_breakaway_locomotion_repair_is_active(config):
        world.bnlt_move_breakaway_locomotion_repair_state = None
        return None
    if not isinstance(data, dict) or not data:
        return ensure_bnlt_move_breakaway_locomotion_repair_for_runtime(world, config)
    cfg = BnltMoveBreakawayLocomotionRepairConfig.from_dict(data.get("config") or {})
    cfg.enabled = True
    validate_config(cfg)
    st = BnltMoveBreakawayLocomotionRepairState(config=cfg)
    st.last_step = dict(data.get("last_step") or {})
    st.history = [dict(r) for r in (data.get("history") or []) if isinstance(r, dict)]
    st.counters = {
        str(k): int(v) for k, v in dict(data.get("counters") or {}).items()
    }
    world.bnlt_move_breakaway_locomotion_repair_state = st
    return st


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "label": "BNLT MOVE breakaway locomotion repair",
        "enabled": bool(enabled),
        "researcher_only": True,
        "agent_action": False,
        "profile_version": PROFILE_VERSION,
        "banner": BANNER,
    }


def researcher_summary(world: Any) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    return {
        "mechanism": MECHANISM_ID,
        "profile_version": PROFILE_VERSION,
        "banner": BANNER,
        "counters": dict(st.counters),
        "last_step": dict(st.last_step) if st.last_step else {},
        "agent_accessible": False,
        "researcher_only": True,
    }
