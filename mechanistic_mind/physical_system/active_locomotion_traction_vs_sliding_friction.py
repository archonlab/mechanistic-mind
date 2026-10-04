"""Acanthostega Beta 4 · Active locomotion traction vs sliding friction V1.

Mechanism: active_locomotion_traction_vs_sliding_friction
Preset: ACANTHOSTEGA_BETA4_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION
Parent: ACANTHOSTEGA_BETA4_REPEATED_CONSERVATIVE_SURFACE_COLUMN_SEPARATION
Profile: ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION_V1

Cumulative Beta 4 tip: RCSS world + active locomotion traction/sliding repair.
Protects co-directed |J_act|/m_eff from Coulomb; kinetic on slip residual only.

Does not weaken μ_k, inflate MOVE, add displacement floors, or change
Tiktaalik / Phase C / parent BNLT when this mechanism is OFF.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

MECHANISM_ID = "active_locomotion_traction_vs_sliding_friction"
PROFILE_VERSION = "ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION_V1"
STATE_SCHEMA = "ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION_STATE_V1"
RECEIPT_KIND = "ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION"

BANNER = (
    "BETA4 · ACTIVE LOCOMOTION TRACTION VS SLIDING FRICTION V1 · "
    "TRACTION-PROTECTED Δv FROM CAPACITY-LIMITED MOVE · "
    "KINETIC ON SLIP ONLY · NO μ_k WEAKEN · NO MAGIC FLOOR · "
    "PARENT BNLT UNCHANGED WHEN OFF"
)

RESEARCHER_FLAGS = {
    "researcher_only": True,
    "agent_accessible": False,
}


@dataclass
class ActiveLocomotionTractionVsSlidingFrictionConfig:
    enabled: bool = False
    history_limit: int = 64

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "history_limit": int(self.history_limit),
            "profile_version": PROFILE_VERSION,
            "traction_protection": "CO_DIRECTED_CAPACITY_LIMITED_MOVE_DV",
            "kinetic_on": "SLIP_RESIDUAL_ONLY",
            "mu_k_weakened": False,
            "magic_displacement_floor": False,
            "move_strength_inflated": False,
            "parent_bnlt_behavior_when_off": "UNCHANGED",
        }

    @classmethod
    def from_dict(
        cls, data: dict[str, Any] | None
    ) -> "ActiveLocomotionTractionVsSlidingFrictionConfig":
        d = dict(data or {})
        return cls(
            enabled=bool(d.get("enabled", False)),
            history_limit=int(d.get("history_limit", 64)),
        )


def validate_config(cfg: ActiveLocomotionTractionVsSlidingFrictionConfig) -> None:
    if int(cfg.history_limit) < 1:
        raise ValueError("history_limit must be >= 1")


def _line_ok(config: Any) -> bool:
    return (
        config is not None
        and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"
    )


def active_locomotion_traction_vs_sliding_friction_is_active(config: Any) -> bool:
    if not _line_ok(config):
        return False
    cfg = getattr(config, "active_locomotion_traction_vs_sliding_friction", None)
    return cfg is not None and bool(getattr(cfg, "enabled", False))


def set_active_locomotion_traction_vs_sliding_friction(config: Any, enabled: bool) -> None:
    if config is None:
        return
    on = bool(enabled) and _line_ok(config)
    cur = getattr(config, "active_locomotion_traction_vs_sliding_friction", None)
    if cur is None:
        if on:
            config.active_locomotion_traction_vs_sliding_friction = (
                ActiveLocomotionTractionVsSlidingFrictionConfig(enabled=True)
            )
        return
    if isinstance(cur, dict):
        cfg = ActiveLocomotionTractionVsSlidingFrictionConfig.from_dict(cur)
        cfg.enabled = on
        config.active_locomotion_traction_vs_sliding_friction = cfg
    else:
        cur.enabled = on


@dataclass
class ActiveLocomotionTractionVsSlidingFrictionState:
    config: ActiveLocomotionTractionVsSlidingFrictionConfig
    last_step: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    counters: dict[str, int] = field(
        default_factory=lambda: {
            "traction_protect_ticks": 0,
            "slip_kinetic_ticks": 0,
            "full_drive_protected_ticks": 0,
            "no_impulse_passthrough_ticks": 0,
        }
    )


def state_of(world: Any) -> ActiveLocomotionTractionVsSlidingFrictionState | None:
    raw = getattr(world, "active_locomotion_traction_vs_sliding_friction_state", None)
    return raw if isinstance(raw, ActiveLocomotionTractionVsSlidingFrictionState) else None


def ensure_active_locomotion_traction_vs_sliding_friction_for_runtime(
    world: Any, config: Any
) -> ActiveLocomotionTractionVsSlidingFrictionState | None:
    if not active_locomotion_traction_vs_sliding_friction_is_active(config):
        if state_of(world) is not None:
            world.active_locomotion_traction_vs_sliding_friction_state = None
        return None
    st = state_of(world)
    if st is not None:
        return st
    raw = getattr(config, "active_locomotion_traction_vs_sliding_friction", None)
    cfg = (
        ActiveLocomotionTractionVsSlidingFrictionConfig.from_dict(
            raw.to_dict() if hasattr(raw, "to_dict") else raw
        )
        if raw is not None
        else ActiveLocomotionTractionVsSlidingFrictionConfig(enabled=True)
    )
    cfg.enabled = True
    validate_config(cfg)
    st = ActiveLocomotionTractionVsSlidingFrictionState(config=cfg)
    world.active_locomotion_traction_vs_sliding_friction_state = st
    return st


def decompose_traction_protected_velocity(
    vx_trial: float,
    vy_trial: float,
    *,
    move_impulse_xy: tuple[float, float] | list[float],
    m_eff: float,
) -> dict[str, Any]:
    """Split trial velocity into traction-protected drive and kinetic slip residual."""
    jx = float(move_impulse_xy[0]) if move_impulse_xy is not None else 0.0
    jy = float(move_impulse_xy[1]) if move_impulse_xy is not None else 0.0
    m = float(m_eff)
    if m <= 1e-18:
        return {
            "vx_protected": 0.0,
            "vy_protected": 0.0,
            "vx_slip": float(vx_trial),
            "vy_slip": float(vy_trial),
            "protected_mag": 0.0,
            "drive_speed": 0.0,
            "along": 0.0,
            "has_drive": False,
        }
    dvx, dvy = jx / m, jy / m
    drive_speed = float(math.hypot(dvx, dvy))
    if drive_speed <= 1e-15:
        return {
            "vx_protected": 0.0,
            "vy_protected": 0.0,
            "vx_slip": float(vx_trial),
            "vy_slip": float(vy_trial),
            "protected_mag": 0.0,
            "drive_speed": 0.0,
            "along": 0.0,
            "has_drive": False,
        }
    ux, uy = dvx / drive_speed, dvy / drive_speed
    along = float(vx_trial) * ux + float(vy_trial) * uy
    protected_mag = float(min(max(along, 0.0), drive_speed))
    vx_p, vy_p = protected_mag * ux, protected_mag * uy
    return {
        "vx_protected": float(vx_p),
        "vy_protected": float(vy_p),
        "vx_slip": float(vx_trial) - float(vx_p),
        "vy_slip": float(vy_trial) - float(vy_p),
        "protected_mag": float(protected_mag),
        "drive_speed": float(drive_speed),
        "along": float(along),
        "has_drive": True,
        "unit": [float(ux), float(uy)],
        "dv_drive": [float(dvx), float(dvy)],
    }


def apply_traction_protected_kinetic(
    vx_trial: float,
    vy_trial: float,
    *,
    move_impulse_xy: tuple[float, float] | list[float],
    m_eff: float,
    mu_k: float,
    g: float,
    dt: float,
    rest_threshold: float,
    friction_accel: float | None = None,
    slope_drive_accel: float | None = None,
) -> dict[str, Any]:
    """Kinetic Coulomb on slip residual only; re-add traction-protected drive."""
    from mechanistic_mind.physical_system.free_resource_object_ground_friction import (
        coulomb_kinetic_step,
    )

    decomp = decompose_traction_protected_velocity(
        float(vx_trial),
        float(vy_trial),
        move_impulse_xy=move_impulse_xy,
        m_eff=m_eff,
    )
    if not decomp["has_drive"]:
        step = coulomb_kinetic_step(
            float(vx_trial),
            float(vy_trial),
            mu_k=float(mu_k),
            g=float(g),
            dt=float(dt),
            rest_threshold=float(rest_threshold),
            friction_accel=float(friction_accel) if friction_accel is not None else None,
            drive_accel=float(slope_drive_accel) if slope_drive_accel is not None else None,
        )
        return {
            **decomp,
            "vx": float(step["vx"]),
            "vy": float(step["vy"]),
            "speed_before": float(step["speed_before"]),
            "speed_after": float(step["speed_after"]),
            "dv": float(step["dv"]),
            "a": float(step["a"]),
            "rest_transition": bool(step["rest_transition"]),
            "stopped_by_friction": bool(step.get("stopped_by_friction")),
            "kinetic_applied_to_slip": True,
            "traction_protection_applied": False,
            "full_drive_protected": False,
            "slip_speed_before": float(step["speed_before"]),
            "slip_speed_after": float(step["speed_after"]),
        }

    step = coulomb_kinetic_step(
        float(decomp["vx_slip"]),
        float(decomp["vy_slip"]),
        mu_k=float(mu_k),
        g=float(g),
        dt=float(dt),
        rest_threshold=float(rest_threshold),
        friction_accel=float(friction_accel) if friction_accel is not None else None,
        # Slope unbalanced drive may still act on the slip channel; locomotor
        # drive itself is already protected and must not be re-taxed here.
        drive_accel=float(slope_drive_accel) if slope_drive_accel is not None else None,
    )
    vx_out = float(step["vx"]) + float(decomp["vx_protected"])
    vy_out = float(step["vy"]) + float(decomp["vy_protected"])
    slip_before = float(math.hypot(float(decomp["vx_slip"]), float(decomp["vy_slip"])))
    full = float(decomp["protected_mag"]) + 1e-15 >= float(decomp["drive_speed"])
    return {
        **decomp,
        "vx": float(vx_out),
        "vy": float(vy_out),
        "speed_before": float(math.hypot(float(vx_trial), float(vy_trial))),
        "speed_after": float(math.hypot(vx_out, vy_out)),
        "dv": float(step["dv"]),
        "a": float(step["a"]),
        "rest_transition": bool(step["rest_transition"])
        and float(decomp["protected_mag"]) <= 1e-15,
        "stopped_by_friction": bool(step.get("stopped_by_friction"))
        and float(decomp["protected_mag"]) <= 1e-15,
        "kinetic_applied_to_slip": True,
        "traction_protection_applied": True,
        "full_drive_protected": bool(full),
        "slip_speed_before": float(slip_before),
        "slip_speed_after": float(step["speed_after"]),
        "slip_rest_transition": bool(step["rest_transition"]),
    }


def record_traction_vs_sliding_step(
    world: Any,
    config: Any,
    *,
    receipt: dict[str, Any],
) -> dict[str, Any]:
    st = ensure_active_locomotion_traction_vs_sliding_friction_for_runtime(world, config)
    if st is None:
        return dict(receipt)
    st.last_step = dict(receipt)
    st.history.append(dict(receipt))
    lim = int(st.config.history_limit)
    if len(st.history) > lim:
        st.history = st.history[-lim:]
    if receipt.get("traction_protection_applied"):
        st.counters["traction_protect_ticks"] = int(
            st.counters.get("traction_protect_ticks", 0)
        ) + 1
        if float(receipt.get("slip_speed_before") or 0.0) > 1e-15:
            st.counters["slip_kinetic_ticks"] = int(
                st.counters.get("slip_kinetic_ticks", 0)
            ) + 1
        if receipt.get("full_drive_protected"):
            st.counters["full_drive_protected_ticks"] = int(
                st.counters.get("full_drive_protected_ticks", 0)
            ) + 1
    else:
        st.counters["no_impulse_passthrough_ticks"] = int(
            st.counters.get("no_impulse_passthrough_ticks", 0)
        ) + 1
    world.last_active_locomotion_traction_vs_sliding_friction = dict(receipt)
    return dict(receipt)


def serialize_state(
    st: ActiveLocomotionTractionVsSlidingFrictionState | None,
) -> dict[str, Any] | None:
    if st is None:
        return None
    return {
        "schema": STATE_SCHEMA,
        "config": st.config.to_dict(),
        "last_step": dict(st.last_step) if st.last_step else {},
        "history": list(st.history[-int(st.config.history_limit) :]),
        "counters": {k: int(v) for k, v in st.counters.items()},
        "banner": BANNER,
        **RESEARCHER_FLAGS,
    }


def restore_state(
    world: Any, data: dict[str, Any] | None, config: Any
) -> ActiveLocomotionTractionVsSlidingFrictionState | None:
    if not active_locomotion_traction_vs_sliding_friction_is_active(config):
        world.active_locomotion_traction_vs_sliding_friction_state = None
        return None
    if not isinstance(data, dict) or not data:
        return ensure_active_locomotion_traction_vs_sliding_friction_for_runtime(world, config)
    cfg = ActiveLocomotionTractionVsSlidingFrictionConfig.from_dict(data.get("config") or {})
    cfg.enabled = True
    validate_config(cfg)
    st = ActiveLocomotionTractionVsSlidingFrictionState(config=cfg)
    st.last_step = dict(data.get("last_step") or {})
    hist = data.get("history") or []
    if isinstance(hist, list):
        st.history = [dict(h) for h in hist if isinstance(h, dict)]
    ctr = data.get("counters") or {}
    if isinstance(ctr, dict):
        for k in st.counters:
            if k in ctr:
                st.counters[k] = int(ctr[k])
    world.active_locomotion_traction_vs_sliding_friction_state = st
    return st


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "label": "Active locomotion traction vs sliding friction",
        "enabled": bool(enabled),
        "profile_version": PROFILE_VERSION,
        "banner": BANNER,
        "researcher_only": True,
        "agent_accessible": False,
        "arch_stage": "BETA4_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION",
    }


def researcher_summary(world: Any) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    return {
        "mechanism": MECHANISM_ID,
        "profile_version": PROFILE_VERSION,
        "banner": BANNER,
        "counters": {k: int(v) for k, v in st.counters.items()},
        "last_step": dict(st.last_step) if st.last_step else {},
        **RESEARCHER_FLAGS,
    }


def world_observer_payload(world: Any) -> dict[str, Any] | None:
    return researcher_summary(world)
