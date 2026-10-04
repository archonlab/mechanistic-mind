"""Acanthostega Beta 4 · Manipulator relative world actuation channel (kinematic).

Mechanism: manipulator_relative_world_actuation
Preset: ACANTHOSTEGA_BETA4_MANIPULATOR_RELATIVE_WORLD_ACTUATION

Body-local VERTICAL offset per effector (independent LEFT/RIGHT).
Composes AFTER base tip + pair aperture. Default offset = 0 ⇒ prior geometry.

NO mass / momentum / force / work / impulse.
Reach envelope + per-tick rate are KINEMATIC only.
Requested vs achieved relative Δz recorded for future actuator seam.

Cognition: physical channel only — no REACH/TOUCH/DIG actions added.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from mechanistic_mind.physical_system.physical_body_resource_object_contact import (
    BODY_CONTACT_RADIUS,
)

MECHANISM_ID = "manipulator_relative_world_actuation"
PROFILE_VERSION = "MANIPULATOR_RELATIVE_WORLD_ACTUATION_PROFILE_V1"
STATE_SCHEMA = "MANIPULATOR_RELATIVE_WORLD_ACTUATION_STATE_V1"
RECEIPT_KIND = "MANIPULATOR_RELATIVE_ACTUATION"
EVENT_STEP = "MANIPULATOR_RELATIVE_ACTUATION_STEP"

# Body-local vertical DOF (world-up; body has yaw only — z ≡ body-local up).
NEW_DOF = "BODY_LOCAL_VERTICAL_OFFSET"
NEW_DOF_FRAME = "BODY_LOCAL"
NEW_DOF_DIMENSIONS = 1

# Reach: tip starts at centre_z = body.z + BODY_CONTACT_RADIUS.
# Plus procedural elevation_amplitude (0.5) so a grounded body can lower the tip
# onto a nearby lower/higher column under the forward offset.
DEFAULT_MAX_RELATIVE_Z = float(BODY_CONTACT_RADIUS) + 0.5  # 1.075
# Per-tick kinematic rate (~reach/10); not physical velocity / mass.
DEFAULT_MAX_DELTA_Z_PER_TICK = float(DEFAULT_MAX_RELATIVE_Z) / 10.0  # 0.1075
HISTORY_LIMIT_DEFAULT = 64

BANNER = (
    "BETA4 · MANIPULATOR RELATIVE WORLD ACTUATION V1 · BODY-LOCAL Z · "
    "KINEMATIC ONLY · NO FORCE / MASS / WORK"
)


@dataclass
class ManipulatorRelativeWorldActuationConfig:
    """Fresh default OFF. Missing snapshot → mechanism OFF."""

    enabled: bool = False
    max_relative_z: float = DEFAULT_MAX_RELATIVE_Z
    max_delta_z_per_tick: float = DEFAULT_MAX_DELTA_Z_PER_TICK
    history_limit: int = HISTORY_LIMIT_DEFAULT

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "max_relative_z": float(self.max_relative_z),
            "max_delta_z_per_tick": float(self.max_delta_z_per_tick),
            "history_limit": int(self.history_limit),
            "profile_version": PROFILE_VERSION,
            "dof": NEW_DOF,
            "frame": NEW_DOF_FRAME,
            "dimensions": int(NEW_DOF_DIMENSIONS),
            "mass": False,
            "force": False,
            "work": False,
            "impulse": False,
            "momentum": False,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ManipulatorRelativeWorldActuationConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        ver = data.get("profile_version")
        if ver is not None and str(ver) != PROFILE_VERSION:
            raise ValueError(f"unknown relative actuation profile: {ver}")
        return cls(
            enabled=bool(data.get("enabled", False)),
            max_relative_z=float(data.get("max_relative_z", DEFAULT_MAX_RELATIVE_Z)),
            max_delta_z_per_tick=float(
                data.get("max_delta_z_per_tick", DEFAULT_MAX_DELTA_Z_PER_TICK)
            ),
            history_limit=int(data.get("history_limit", HISTORY_LIMIT_DEFAULT)),
        )


def validate_config(cfg: ManipulatorRelativeWorldActuationConfig) -> None:
    if float(cfg.max_relative_z) < 0.0:
        raise ValueError("max_relative_z must be >= 0")
    if float(cfg.max_delta_z_per_tick) < 0.0:
        raise ValueError("max_delta_z_per_tick must be >= 0")


def manipulator_relative_world_actuation_is_active(config: Any) -> bool:
    cfg = getattr(config, "manipulator_relative_world_actuation", None)
    return bool(cfg is not None and getattr(cfg, "enabled", False))


def set_manipulator_relative_world_actuation(config: Any, enabled: bool) -> None:
    on = bool(enabled)
    cur = getattr(config, "manipulator_relative_world_actuation", None)
    if cur is None:
        config.manipulator_relative_world_actuation = ManipulatorRelativeWorldActuationConfig(
            enabled=on
        )
    else:
        cur.enabled = on


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "label": "MANIPULATOR RELATIVE WORLD ACTUATION",
        "config_path": "manipulator_relative_world_actuation.enabled",
        "enabled": bool(enabled),
        "profile_version": PROFILE_VERSION,
        "provenance": "acanthostega_manipulator_relative_world_actuation",
        "banner": BANNER,
        "dof": NEW_DOF,
        "frame": NEW_DOF_FRAME,
        "cognition_exposed": False,
        "mass": False,
        "force": False,
        "work": False,
        "impulse": False,
    }


@dataclass
class ManipulatorRelativeWorldActuationState:
    config: ManipulatorRelativeWorldActuationConfig
    # key = f"{body_id}|{effector_id}" → {"z": float}
    offsets: dict[str, dict[str, float]] = field(default_factory=dict)
    last_step: dict[str, Any] | None = None
    history: list[dict[str, Any]] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=dict)


def _zero_counters() -> dict[str, int]:
    return {
        "steps": 0,
        "requests": 0,
        "rate_clipped": 0,
        "reach_clipped": 0,
        "zero_requests": 0,
    }


def state_of(world: Any) -> ManipulatorRelativeWorldActuationState | None:
    raw = getattr(world, "manipulator_relative_world_actuation_state", None)
    return raw if isinstance(raw, ManipulatorRelativeWorldActuationState) else None


def ensure_manipulator_relative_world_actuation_for_runtime(
    world: Any, config: Any
) -> ManipulatorRelativeWorldActuationState | None:
    if not manipulator_relative_world_actuation_is_active(config):
        if hasattr(world, "manipulator_relative_world_actuation_state"):
            world.manipulator_relative_world_actuation_state = None
        return None
    raw_cfg = getattr(config, "manipulator_relative_world_actuation", None)
    cfg = (
        raw_cfg
        if isinstance(raw_cfg, ManipulatorRelativeWorldActuationConfig)
        else ManipulatorRelativeWorldActuationConfig.from_dict(
            raw_cfg.to_dict() if raw_cfg is not None and hasattr(raw_cfg, "to_dict") else None
        )
    )
    validate_config(cfg)
    st = state_of(world)
    if st is None:
        st = ManipulatorRelativeWorldActuationState(config=cfg, counters=_zero_counters())
        world.manipulator_relative_world_actuation_state = st
    else:
        st.config = cfg
    return st


def serialize_state(st: ManipulatorRelativeWorldActuationState | None) -> dict[str, Any] | None:
    if st is None:
        return None
    return {
        "schema_version": STATE_SCHEMA,
        "config": st.config.to_dict(),
        "offsets": {
            k: {"z": float(v.get("z", 0.0))}
            for k, v in sorted(st.offsets.items())
        },
        "counters": dict(st.counters),
        "last_step": dict(st.last_step) if st.last_step else None,
        "history": list(st.history),
        "banner": BANNER,
        "researcher_only": True,
    }


def restore_state(
    world: Any, data: dict[str, Any] | None, config: Any
) -> ManipulatorRelativeWorldActuationState | None:
    if not manipulator_relative_world_actuation_is_active(config):
        world.manipulator_relative_world_actuation_state = None
        return None
    if not data:
        return ensure_manipulator_relative_world_actuation_for_runtime(world, config)
    cfg = ManipulatorRelativeWorldActuationConfig.from_dict(
        data.get("config") if isinstance(data.get("config"), dict) else None
    )
    validate_config(cfg)
    st = ManipulatorRelativeWorldActuationState(
        config=cfg,
        offsets={
            str(k): {"z": float((v or {}).get("z", 0.0))}
            for k, v in (data.get("offsets") or {}).items()
        },
        counters={**_zero_counters(), **{a: int(b) for a, b in (data.get("counters") or {}).items()}},
        last_step=dict(data["last_step"]) if isinstance(data.get("last_step"), dict) else None,
        history=[dict(r) for r in (data.get("history") or [])],
    )
    world.manipulator_relative_world_actuation_state = st
    return st


def _key(body_id: str, effector_id: str) -> str:
    return f"{str(body_id)}|{str(effector_id)}"


def relative_z_of(
    world: Any,
    body_id: str,
    effector_id: str,
    *,
    config: Any | None = None,
) -> float:
    """Authoritative body-local vertical offset (0 if mechanism OFF / unset)."""
    if config is not None and not manipulator_relative_world_actuation_is_active(config):
        return 0.0
    st = state_of(world)
    if st is None:
        return 0.0
    row = st.offsets.get(_key(body_id, effector_id))
    if not row:
        return 0.0
    return float(row.get("z", 0.0))


def _clip_reach(z: float, max_z: float) -> tuple[float, bool]:
    m = float(max_z)
    if z > m:
        return m, True
    if z < -m:
        return -m, True
    return float(z), False


def request_relative_effector_displacement(
    world: Any,
    *,
    config: Any,
    body_id: str,
    effector_id: str,
    requested_delta_z: float,
    tick: int,
) -> dict[str, Any]:
    """Apply one kinematic relative Δz request (researcher / test fixture).

    Clips by per-tick rate then reach envelope. No force/work/impulse.
    """
    st = ensure_manipulator_relative_world_actuation_for_runtime(world, config)
    if st is None:
        return {
            "receipt_kind": RECEIPT_KIND,
            "status": "INACTIVE",
            "tick": int(tick),
            "body_id": str(body_id),
            "effector_id": str(effector_id),
            "requested_delta_z": float(requested_delta_z),
            "achieved_delta_z": 0.0,
            "relative_z_before": 0.0,
            "relative_z_after": 0.0,
            "rate_clipped": False,
            "reach_clipped": False,
            "mass": False,
            "force": False,
            "work": False,
            "impulse": False,
            "researcher_only": True,
        }
    cfg = st.config
    key = _key(body_id, effector_id)
    before = float(st.offsets.get(key, {}).get("z", 0.0))
    req = float(requested_delta_z)
    st.counters["requests"] = int(st.counters.get("requests", 0)) + 1
    if abs(req) <= 1e-15:
        st.counters["zero_requests"] = int(st.counters.get("zero_requests", 0)) + 1
        rec = {
            "receipt_kind": RECEIPT_KIND,
            "event": EVENT_STEP,
            "status": "ZERO",
            "tick": int(tick),
            "body_id": str(body_id),
            "effector_id": str(effector_id),
            "requested_delta_z": 0.0,
            "achieved_delta_z": 0.0,
            "relative_z_before": before,
            "relative_z_after": before,
            "rate_clipped": False,
            "reach_clipped": False,
            "frame": NEW_DOF_FRAME,
            "dof": NEW_DOF,
            "mass": False,
            "force": False,
            "work": False,
            "impulse": False,
            "researcher_only": True,
            "cognition_exposed": False,
        }
        st.last_step = rec
        return rec

    rate = float(cfg.max_delta_z_per_tick)
    rate_clipped = False
    delta = req
    if abs(delta) > rate + 1e-15:
        delta = math.copysign(rate, delta)
        rate_clipped = True
        st.counters["rate_clipped"] = int(st.counters.get("rate_clipped", 0)) + 1

    tentative = before + delta
    after, reach_clipped = _clip_reach(tentative, float(cfg.max_relative_z))
    if reach_clipped:
        st.counters["reach_clipped"] = int(st.counters.get("reach_clipped", 0)) + 1
    achieved = float(after - before)
    st.offsets[key] = {"z": float(after)}
    st.counters["steps"] = int(st.counters.get("steps", 0)) + 1
    rec = {
        "receipt_kind": RECEIPT_KIND,
        "event": EVENT_STEP,
        "status": "APPLIED",
        "tick": int(tick),
        "body_id": str(body_id),
        "effector_id": str(effector_id),
        "requested_delta_z": req,
        "achieved_delta_z": achieved,
        "relative_z_before": before,
        "relative_z_after": float(after),
        "rate_clipped": bool(rate_clipped),
        "reach_clipped": bool(reach_clipped),
        "max_relative_z": float(cfg.max_relative_z),
        "max_delta_z_per_tick": float(cfg.max_delta_z_per_tick),
        "frame": NEW_DOF_FRAME,
        "dof": NEW_DOF,
        "kinematic_only": True,
        "mass": False,
        "force": False,
        "work": False,
        "impulse": False,
        "researcher_only": True,
        "cognition_exposed": False,
    }
    st.last_step = rec
    st.history.append(dict(rec))
    lim = int(cfg.history_limit)
    if len(st.history) > lim:
        st.history = st.history[-lim:]
    world.last_manipulator_relative_actuation = rec
    return rec


def set_relative_z_absolute(
    world: Any,
    *,
    config: Any,
    body_id: str,
    effector_id: str,
    relative_z: float,
    tick: int,
) -> dict[str, Any]:
    """Researcher absolute set via one-shot request (respects rate/reach by multi-step if needed).

    For tests: uses direct clip to reach without inventing teleport beyond rate —
    callers needing large moves should loop requests. This helper applies ONE
    rate-limited step toward target.
    """
    cur = relative_z_of(world, body_id, effector_id, config=config)
    return request_relative_effector_displacement(
        world,
        config=config,
        body_id=body_id,
        effector_id=effector_id,
        requested_delta_z=float(relative_z) - float(cur),
        tick=tick,
    )


def drive_relative_z_to(
    world: Any,
    *,
    config: Any,
    body_id: str,
    effector_id: str,
    target_z: float,
    tick_start: int,
    max_steps: int = 32,
) -> list[dict[str, Any]]:
    """Deterministic multi-tick drive to target under rate/reach limits."""
    out: list[dict[str, Any]] = []
    t = int(tick_start)
    for _ in range(int(max_steps)):
        cur = relative_z_of(world, body_id, effector_id, config=config)
        if abs(cur - float(target_z)) <= 1e-12:
            break
        rec = request_relative_effector_displacement(
            world,
            config=config,
            body_id=body_id,
            effector_id=effector_id,
            requested_delta_z=float(target_z) - float(cur),
            tick=t,
        )
        out.append(rec)
        t += 1
        if abs(float(rec.get("achieved_delta_z") or 0.0)) <= 1e-15 and rec.get("status") != "ZERO":
            # Stuck at reach
            break
    return out
