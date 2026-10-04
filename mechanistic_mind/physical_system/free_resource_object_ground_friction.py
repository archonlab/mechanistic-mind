"""Acanthostega FREE RESOURCE OBJECT FLAT-GROUND FRICTION V1.

Preset: ACANTHOSTEGA_PHASE_C_FREE_OBJECT_GROUND_FRICTION
Parent: ACANTHOSTEGA_PHASE_C_FLAT_GROUND_GRAVITY
Mechanism: free_resource_object_ground_friction
Receipt: FREE_RESOURCE_OBJECT_GROUND_FRICTION

CRITICAL: when this mechanism is active, legacy FOK exponential damping is BYPASSED.
  grounded FREE_MOVING  → Coulomb kinetic friction only (friction → position)
  airborne FREE_MOVING  → no ground friction, conserve horizontal v (AIR_DRAG=NO)
  FREE_STATIC           → untouched (friction never starts resting objects)
  HELD / bodies         → out of scope

Physics (FLAT_GROUND_V1 only):
  N = m g
  F = μ_k N
  a = μ_k g          (mass-independent deceleration for same μ)
  μ_k = bounded monotonic fn(surface_affinity) at support cell
  surface_affinity from deposit mix (or neutral 0.5 if empty)
  NO recipes / IDs / optical. Body traction law UNCHANGED.

STATIC_FRICTION_FORCE_BALANCING = NOT_IMPLEMENTED
FOOTPRINT_MULTI_CELL = NOT_IMPLEMENTED (single support cell)
AIR_DRAG = NO
Landing: friction next tick after support (horizontal runs before vertical).
Tick order: object horizontal friction/integration → vertical gravity/support → contacts.
No re-friction after collision same tick. K dissipates; no reservoir credit; no sound.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from mechanistic_mind.physical_system.flat_ground_gravity import (
    GRAVITY_ACCELERATION,
    flat_ground_gravity_is_active,
)
from mechanistic_mind.physical_system.free_resource_object_kinematics import (
    free_resource_object_kinematics_is_active,
)
from mechanistic_mind.physical_system.passive_material_properties import (
    DERIVATION_VERSION,
    derive_effective_properties,
)
from mechanistic_mind.physical_system.explicit_surface_deposition import (
    deposit_id_for_cell,
    ensure_surface_deposits,
)
from mechanistic_mind.planet.topology import wrap_coord

MECHANISM_ID = "free_resource_object_ground_friction"
PROFILE_VERSION = "FREE_OBJECT_GROUND_FRICTION_PROFILE_V1"
STATE_SCHEMA = "FREE_RESOURCE_OBJECT_GROUND_FRICTION_STATE_V1"
RECEIPT_KIND = "FREE_RESOURCE_OBJECT_GROUND_FRICTION"
EVENT_STEP = "FREE_RESOURCE_OBJECT_GROUND_FRICTION_STEP"

BANNER = (
    "FREE OBJECT FLAT-GROUND FRICTION V1 · F=μN · MATERIAL-DERIVED SURFACE COUPLING · "
    "BODIES UNCHANGED · NO AIR DRAG · NO SLOPES"
)
OVERLAY_CAPTION = BANNER
ANALYZER_SECTION = "FREE RESOURCE OBJECT GROUND FRICTION"

SUPPORT_PROFILE = "FLAT_GROUND_V1"
SUPPORT_SAMPLE_POLICY = "OBJECT_SUPPORT_FLOOR_WRAP_V1"
FRICTION_LAW = "COULOMB_KINETIC_MU_N_V1"
INTEGRATOR = "FRICTION_THEN_DRIFT_WRAP_V1"
AIRBORNE_HORIZONTAL = "CONSERVE_HORIZONTAL_V_NO_AIR_DRAG_V1"
AFFINITY_COUPLING = "SURFACE_AFFINITY_TO_MU_K_LINEAR_V1"
STATIC_FRICTION_FORCE_BALANCING = "NOT_IMPLEMENTED"
FOOTPRINT_MULTI_CELL = "NOT_IMPLEMENTED"
AIR_DRAG = "NO"
LEGACY_FOK_DAMPING_WHEN_ACTIVE = "BYPASSED"

# μ_k = MU_MIN + (MU_MAX - MU_MIN) * clip(surface_affinity, 0, 1)
# Calibrated against flat-ground g=2/110 so mid-affinity (~0.5) stops |v|=0.3 in ~10 ticks.
MU_MIN = 0.5
MU_MAX = 3.0
NEUTRAL_AFFINITY = 0.5
DT = 1.0
HISTORY_LIMIT_DEFAULT = 64

PHYSICAL_STATE_FREE_MOVING = "FREE_MOVING"
PHYSICAL_STATE_FREE_STATIC = "FREE_STATIC"
PHYSICAL_STATE_HELD = "HELD"

RESEARCHER_FLAGS = {
    "researcher_only": True,
    "agent_accessible": False,
    "semantic_label": False,
}


@dataclass
class FreeObjectGroundFrictionConfig:
    """Fresh default OFF; missing snapshot field = OFF."""

    enabled: bool = False
    mu_min: float = MU_MIN
    mu_max: float = MU_MAX
    history_limit: int = HISTORY_LIMIT_DEFAULT

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "mu_min": float(self.mu_min),
            "mu_max": float(self.mu_max),
            "history_limit": int(self.history_limit),
            "dt": float(DT),
            "profile_version": PROFILE_VERSION,
            "support_profile": SUPPORT_PROFILE,
            "support_sample_policy": SUPPORT_SAMPLE_POLICY,
            "friction_law": FRICTION_LAW,
            "integrator": INTEGRATOR,
            "airborne_horizontal": AIRBORNE_HORIZONTAL,
            "affinity_coupling": AFFINITY_COUPLING,
            "STATIC_FRICTION_FORCE_BALANCING": STATIC_FRICTION_FORCE_BALANCING,
            "FOOTPRINT_MULTI_CELL": FOOTPRINT_MULTI_CELL,
            "AIR_DRAG": AIR_DRAG,
            "legacy_fok_damping_when_active": LEGACY_FOK_DAMPING_WHEN_ACTIVE,
            "body_traction_unchanged": True,
            "slopes": False,
            "sound": False,
            "reservoir_credit": False,
            "held_objects": False,
            "bodies": False,
            "mass_independent_deceleration": True,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "FreeObjectGroundFrictionConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        ver = data.get("profile_version")
        if ver is not None and str(ver) != PROFILE_VERSION:
            raise ValueError(f"unknown free object ground friction profile: {ver}")
        return cls(
            enabled=bool(data.get("enabled", False)),
            mu_min=float(data.get("mu_min", MU_MIN)),
            mu_max=float(data.get("mu_max", MU_MAX)),
            history_limit=int(data.get("history_limit", HISTORY_LIMIT_DEFAULT)),
        )


def validate_config(cfg: FreeObjectGroundFrictionConfig) -> None:
    if not (math.isfinite(cfg.mu_min) and math.isfinite(cfg.mu_max)):
        raise ValueError("mu_min/mu_max must be finite")
    if not (0.0 <= float(cfg.mu_min) <= float(cfg.mu_max) <= 20.0):
        raise ValueError("mu_min/mu_max must satisfy 0 <= mu_min <= mu_max <= 20")
    if not (1 <= int(cfg.history_limit) <= 512):
        raise ValueError("history_limit must be in [1, 512]")


def _line_ok(config: Any) -> bool:
    return config is not None and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"


def free_resource_object_ground_friction_is_active(config: Any) -> bool:
    if not _line_ok(config):
        return False
    cfg = getattr(config, "free_resource_object_ground_friction", None)
    if cfg is None or not bool(getattr(cfg, "enabled", False)):
        return False
    return bool(
        flat_ground_gravity_is_active(config)
        and free_resource_object_kinematics_is_active(config)
    )


def set_free_resource_object_ground_friction(config: Any, enabled: bool) -> None:
    if config is None:
        return
    on = bool(enabled) and _line_ok(config)
    cur = getattr(config, "free_resource_object_ground_friction", None)
    if cur is None:
        if on:
            config.free_resource_object_ground_friction = FreeObjectGroundFrictionConfig(enabled=True)
        return
    if isinstance(cur, dict):
        cfg = FreeObjectGroundFrictionConfig.from_dict(cur)
        cfg.enabled = on
        config.free_resource_object_ground_friction = cfg
    else:
        cur.enabled = on


def mu_k_from_surface_affinity(surface_affinity: float, *, mu_min: float = MU_MIN, mu_max: float = MU_MAX) -> float:
    """Bounded monotonic linear map. Independent of body traction_multiplier."""
    a = float(surface_affinity)
    if not math.isfinite(a):
        a = NEUTRAL_AFFINITY
    a = max(0.0, min(1.0, a))
    return float(mu_min + (mu_max - mu_min) * a)


def resolve_support_cell(x: float, y: float, *, width: int, height: int) -> tuple[int, int]:
    """OBJECT_SUPPORT_FLOOR_WRAP_V1 — single cell under object pose (no multi-cell footprint)."""
    cell_x = int(wrap_coord(int(math.floor(float(x))), int(width)))
    cell_y = int(wrap_coord(int(math.floor(float(y))), int(height)))
    return cell_x, cell_y


def sample_support_surface_affinity(world: Any, x: float, y: float, *, width: int, height: int) -> dict[str, Any]:
    """Read deposit mix affinity at support cell; empty → neutral 0.5. No recipes/IDs/optical."""
    cell_x, cell_y = resolve_support_cell(x, y, width=width, height=height)
    out: dict[str, Any] = {
        "cell_x": int(cell_x),
        "cell_y": int(cell_y),
        "support_sample_policy": SUPPORT_SAMPLE_POLICY,
        "FOOTPRINT_MULTI_CELL": FOOTPRINT_MULTI_CELL,
        "deposit_id": "NONE",
        "surface_affinity": float(NEUTRAL_AFFINITY),
        "deposit_present": False,
        "derivation_version": DERIVATION_VERSION,
        "recipe_match": False,
        "optical_used": False,
    }
    deposits = ensure_surface_deposits(world)
    deposit = deposits.get(deposit_id_for_cell(cell_x, cell_y))
    if deposit is None:
        return out
    derived = derive_effective_properties(deposit.composition)
    affinity = float(derived["surface_affinity"])
    out.update({
        "deposit_id": str(deposit.deposit_id),
        "surface_affinity": affinity,
        "deposit_present": True,
        "deposit_mass": float(getattr(deposit, "mass", 0.0) or 0.0),
    })
    return out


def _read_g(world: Any) -> float:
    st = getattr(world, "flat_ground_gravity_state", None)
    if st is not None and getattr(st, "config", None) is not None:
        return float(getattr(st.config, "g", GRAVITY_ACCELERATION))
    return float(GRAVITY_ACCELERATION)


def _dims(world: Any) -> tuple[int, int]:
    t = getattr(world, "T", None)
    return (int(t.shape[1]), int(t.shape[0])) if t is not None else (32, 32)


def _is_grounded(obj: Any) -> bool:
    """Support state from previous vertical step (horizontal runs before vertical this tick)."""
    try:
        z = float(getattr(obj, "z", 0.0) or 0.0)
        vz = float(getattr(obj, "vz", 0.0) or 0.0)
    except (TypeError, ValueError):
        z, vz = 0.0, 0.0
    if not (math.isfinite(z) and math.isfinite(vz)):
        z, vz = 0.0, 0.0
    flagged = bool(getattr(obj, "grounded", False))
    return bool(flagged and abs(z) <= 1e-12 and abs(vz) <= 1e-12)


def coulomb_kinetic_step(
    vx: float,
    vy: float,
    *,
    mu_k: float,
    g: float,
    dt: float = DT,
    rest_threshold: float,
    friction_accel: float | None = None,
    drive_accel: float | None = None,
) -> dict[str, Any]:
    """Friction-then-rest: dv = μ_k · a_n dt; stop → exact zero; else scale direction.

    Default a_n = g (flat N = m g ⇒ a = μ_k N/m).
    When projected N is live, pass friction_accel = N_projected / m_eff (= g n_z).

    rest_threshold is a numerical settling clamp for near-zero residual speed when
    kinetic friction has already removed physical drive. It must NOT impersonate
    static friction: if a persistent drive_accel exceeds friction accel a, do not
    erase the post-friction residual solely because it is below rest_threshold.
    """
    speed = float(math.hypot(vx, vy))
    a_n = float(g) if friction_accel is None else float(friction_accel)
    a = float(mu_k) * float(a_n)
    dv = float(a) * float(dt)
    drive = None if drive_accel is None else float(drive_accel)
    persistent_unbalanced = (
        drive is not None
        and math.isfinite(drive)
        and float(drive) > float(a) + 1e-15
    )
    if speed <= 0.0 or not math.isfinite(speed):
        # From rest: if drive exceeds kinetic capacity, leave one-tick residual
        # so persistent force can accumulate across ticks (static already broken).
        if persistent_unbalanced:
            leftover = float(drive) - float(a)
            # Direction unknown with zero speed — caller should have integrated
            # drive into vx,vy already. Keep exact zero here.
            return {
                "vx": 0.0,
                "vy": 0.0,
                "speed_before": 0.0,
                "speed_after": 0.0,
                "dv": float(dv),
                "a": float(a),
                "rest_transition": True,
                "stopped_by_friction": True,
                "rest_clamp_suppressed_by_drive": False,
                "drive_accel": drive,
            }
        return {
            "vx": 0.0,
            "vy": 0.0,
            "speed_before": 0.0,
            "speed_after": 0.0,
            "dv": float(dv),
            "a": float(a),
            "rest_transition": True,
            "stopped_by_friction": True,
            "rest_clamp_suppressed_by_drive": False,
            "drive_accel": drive,
        }
    if dv >= speed:
        # Friction exhausted this tick's speed.
        if persistent_unbalanced:
            # Keep direction; residual = (drive − a)·dt projected on prior heading.
            leftover = (float(drive) - float(a)) * float(dt)
            if leftover > 1e-15 and speed > 1e-15:
                scale = leftover / speed
                vx1, vy1 = float(vx) * scale, float(vy) * scale
                return {
                    "vx": float(vx1),
                    "vy": float(vy1),
                    "speed_before": speed,
                    "speed_after": float(math.hypot(vx1, vy1)),
                    "dv": float(dv),
                    "a": float(a),
                    "rest_transition": False,
                    "stopped_by_friction": False,
                    "rest_clamp_suppressed_by_drive": True,
                    "drive_accel": drive,
                }
        return {
            "vx": 0.0,
            "vy": 0.0,
            "speed_before": speed,
            "speed_after": 0.0,
            "dv": float(dv),
            "a": float(a),
            "rest_transition": True,
            "stopped_by_friction": True,
            "rest_clamp_suppressed_by_drive": False,
            "drive_accel": drive,
        }
    remaining = speed - dv
    if remaining < float(rest_threshold):
        if persistent_unbalanced and remaining > 1e-15:
            scale = remaining / speed
            vx1, vy1 = float(vx) * scale, float(vy) * scale
            return {
                "vx": float(vx1),
                "vy": float(vy1),
                "speed_before": speed,
                "speed_after": float(math.hypot(vx1, vy1)),
                "dv": float(dv),
                "a": float(a),
                "rest_transition": False,
                "stopped_by_friction": False,
                "rest_clamp_suppressed_by_drive": True,
                "drive_accel": drive,
            }
        return {
            "vx": 0.0,
            "vy": 0.0,
            "speed_before": speed,
            "speed_after": 0.0,
            "dv": float(dv),
            "a": float(a),
            "rest_transition": True,
            "stopped_by_friction": True,
            "rest_clamp_suppressed_by_drive": False,
            "drive_accel": drive,
        }
    scale = remaining / speed
    vx1, vy1 = float(vx) * scale, float(vy) * scale
    return {
        "vx": vx1,
        "vy": vy1,
        "speed_before": speed,
        "speed_after": float(math.hypot(vx1, vy1)),
        "dv": float(dv),
        "a": float(a),
        "rest_transition": False,
        "stopped_by_friction": False,
        "rest_clamp_suppressed_by_drive": False,
        "drive_accel": drive,
    }


@dataclass
class FreeObjectGroundFrictionState:
    config: FreeObjectGroundFrictionConfig
    last_step: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=lambda: {
        "grounded_friction_steps": 0,
        "airborne_conserve_steps": 0,
        "rest_transitions": 0,
        "legacy_damping_bypassed": 0,
        "held_skipped": 0,
        "static_untouched": 0,
    })


def state_of(world: Any) -> FreeObjectGroundFrictionState | None:
    raw = getattr(world, "free_resource_object_ground_friction_state", None)
    return raw if isinstance(raw, FreeObjectGroundFrictionState) else None


def ensure_free_object_ground_friction_for_runtime(world: Any, config: Any) -> FreeObjectGroundFrictionState | None:
    if not free_resource_object_ground_friction_is_active(config):
        if state_of(world) is not None:
            world.free_resource_object_ground_friction_state = None
        return None
    st = state_of(world)
    if st is not None:
        return st
    raw = getattr(config, "free_resource_object_ground_friction", None)
    cfg = (
        FreeObjectGroundFrictionConfig.from_dict(raw.to_dict() if hasattr(raw, "to_dict") else raw)
        if raw is not None
        else FreeObjectGroundFrictionConfig(enabled=True)
    )
    cfg.enabled = True
    validate_config(cfg)
    st = FreeObjectGroundFrictionState(config=cfg)
    world.free_resource_object_ground_friction_state = st
    return st


def plan_free_object_horizontal_step(
    world: Any,
    obj: Any,
    vx: float,
    vy: float,
    fok_cfg: Any,
) -> dict[str, Any] | None:
    """FOK hook: when friction ON, replace exponential damping. Return None → legacy damping.

    Order consistency with FOK: friction (or conserve) THEN position drift (caller integrates).
    """
    st = state_of(world)
    if st is None:
        return None
    st.counters["legacy_damping_bypassed"] = int(st.counters.get("legacy_damping_bypassed", 0)) + 1
    rest_threshold = float(getattr(fok_cfg, "rest_threshold", 0.01))
    grounded = _is_grounded(obj)
    w, h = _dims(world)
    g = _read_g(world)
    base: dict[str, Any] = {
        "friction_active": True,
        "legacy_fok_damping": False,
        "AIR_DRAG": AIR_DRAG,
        "STATIC_FRICTION_FORCE_BALANCING": STATIC_FRICTION_FORCE_BALANCING,
        "g": float(g),
        "dt": float(DT),
        "grounded": bool(grounded),
        "support_profile": SUPPORT_PROFILE,
        "integrator": INTEGRATOR,
        "friction_law": FRICTION_LAW,
        "reservoir_credit": False,
        "sound": False,
        **RESEARCHER_FLAGS,
    }
    if not grounded:
        st.counters["airborne_conserve_steps"] = int(st.counters.get("airborne_conserve_steps", 0)) + 1
        speed = float(math.hypot(vx, vy))
        # Conserve horizontal v; no air drag; do not apply rest via friction while airborne.
        return {
            **base,
            "mode": "AIRBORNE_CONSERVE",
            "vx": float(vx),
            "vy": float(vy),
            "rest_transition": False,
            "mu_k": None,
            "surface_affinity": None,
            "speed_before": speed,
            "speed_after": speed,
            "kinetic_dissipated": 0.0,
            "damping_factor": 1.0,
            "damping_law": AIRBORNE_HORIZONTAL,
        }

    sample = sample_support_surface_affinity(world, float(obj.x), float(obj.y), width=w, height=h)
    mu_k = mu_k_from_surface_affinity(
        sample["surface_affinity"], mu_min=st.config.mu_min, mu_max=st.config.mu_max
    )
    step = coulomb_kinetic_step(vx, vy, mu_k=mu_k, g=g, dt=DT, rest_threshold=rest_threshold)
    mass = float(getattr(obj, "mass", 1.0) or 1.0)
    # G2D diagnostic shadow (researcher-only; never feeds N / friction).
    try:
        from mechanistic_mind.physical_system.diagnostic_normal_load_shadow import (
            maybe_record_free_object_shadow,
        )
        maybe_record_free_object_shadow(
            world,
            None,
            obj=obj,
            object_id=str(getattr(obj, "object_id", "") or ""),
            mass=float(mass),
            g=float(g),
            grounded=True,
            seam="FOGF_PLAN",
        )
    except Exception:
        pass
    try:
        from mechanistic_mind.physical_system.tangent_gravity_diagnostic_shadow import (
            maybe_record_free_object_tangent_shadow,
        )
        maybe_record_free_object_tangent_shadow(
            world,
            None,
            obj=obj,
            object_id=str(getattr(obj, "object_id", "") or ""),
            mass=float(mass),
            g=float(g),
            grounded=True,
            seam="FOGF_PLAN",
        )
    except Exception:
        pass
    # K = 1/2 m |v|^2 — dissipate difference; no reservoir credit.
    k0 = 0.5 * mass * float(step["speed_before"]) ** 2
    k1 = 0.5 * mass * float(step["speed_after"]) ** 2
    dissipated = max(0.0, k0 - k1)
    st.counters["grounded_friction_steps"] = int(st.counters.get("grounded_friction_steps", 0)) + 1
    if step["rest_transition"]:
        st.counters["rest_transitions"] = int(st.counters.get("rest_transitions", 0)) + 1
    return {
        **base,
        "mode": "GROUNDED_COULOMB",
        "vx": float(step["vx"]),
        "vy": float(step["vy"]),
        "rest_transition": bool(step["rest_transition"]),
        "stopped_by_friction": bool(step["stopped_by_friction"]),
        "mu_k": float(mu_k),
        "a": float(step["a"]),
        "dv": float(step["dv"]),
        "normal_load_N": float(mass) * float(g),
        "mass": float(mass),
        "mass_independent_a": True,
        "speed_before": float(step["speed_before"]),
        "speed_after": float(step["speed_after"]),
        "kinetic_before": float(k0),
        "kinetic_after": float(k1),
        "kinetic_dissipated": float(dissipated),
        "damping_factor": None,
        "damping_law": FRICTION_LAW,
        "affinity_coupling": AFFINITY_COUPLING,
        **sample,
    }


def record_friction_receipt(
    world: Any,
    *,
    tick: int,
    object_id: str,
    plan: dict[str, Any],
    start_position: list[float],
    end_position: list[float],
    end_state: str,
) -> dict[str, Any]:
    st = state_of(world)
    rec = {
        "receipt_kind": RECEIPT_KIND,
        "event": EVENT_STEP,
        "tick": int(tick),
        "object_id": str(object_id),
        "start_position": list(start_position),
        "end_position": list(end_position),
        "end_state": str(end_state),
        "banner": BANNER,
        **{k: plan.get(k) for k in (
            "mode", "grounded", "vx", "vy", "mu_k", "a", "dv", "g", "dt",
            "surface_affinity", "cell_x", "cell_y", "deposit_id", "deposit_present",
            "speed_before", "speed_after", "kinetic_before", "kinetic_after",
            "kinetic_dissipated", "rest_transition", "stopped_by_friction",
            "legacy_fok_damping", "AIR_DRAG", "friction_law", "integrator",
            "support_profile", "support_sample_policy", "affinity_coupling",
            "normal_load_N", "mass", "mass_independent_a", "reservoir_credit",
            "sound", "FOOTPRINT_MULTI_CELL", "STATIC_FRICTION_FORCE_BALANCING",
        )},
        **RESEARCHER_FLAGS,
    }
    if st is not None:
        st.last_step = rec
        st.history.append(rec)
        lim = int(st.config.history_limit)
        if len(st.history) > lim:
            st.history = st.history[-lim:]
        world.last_free_object_ground_friction_step = rec
    return rec


def serialize_state(st: FreeObjectGroundFrictionState | None) -> dict[str, Any] | None:
    if st is None:
        return None
    return {
        "schema": STATE_SCHEMA,
        "config": st.config.to_dict(),
        "counters": dict(st.counters),
        "last_step": dict(st.last_step) if st.last_step else None,
        "history": list(st.history),
        "banner": BANNER,
        "researcher_only": True,
    }


def restore_state(world: Any, data: dict[str, Any] | None, config: Any) -> FreeObjectGroundFrictionState | None:
    if not free_resource_object_ground_friction_is_active(config):
        world.free_resource_object_ground_friction_state = None
        return None
    if not isinstance(data, dict) or not data:
        return ensure_free_object_ground_friction_for_runtime(world, config)
    if str(data.get("schema")) != STATE_SCHEMA and data.get("schema_version") != STATE_SCHEMA:
        # Accept fresh ensure if schema missing from older tooling; otherwise require match.
        if data.get("schema") is not None or data.get("schema_version") is not None:
            raise ValueError(f"unknown free object ground friction state schema: {data.get('schema') or data.get('schema_version')}")
        return ensure_free_object_ground_friction_for_runtime(world, config)
    raw_cfg = data.get("config")
    if raw_cfg is None:
        cur = getattr(config, "free_resource_object_ground_friction", None)
        raw_cfg = cur.to_dict() if cur is not None and hasattr(cur, "to_dict") else None
    cfg = FreeObjectGroundFrictionConfig.from_dict(raw_cfg)
    validate_config(cfg)
    st = FreeObjectGroundFrictionState(
        config=cfg,
        last_step=dict(data["last_step"]) if isinstance(data.get("last_step"), dict) else {},
        history=list(data.get("history") or []),
        counters={**{
            "grounded_friction_steps": 0,
            "airborne_conserve_steps": 0,
            "rest_transitions": 0,
            "legacy_damping_bypassed": 0,
            "held_skipped": 0,
            "static_untouched": 0,
        }, **{k: int(v) for k, v in dict(data.get("counters") or {}).items()}},
    )
    world.free_resource_object_ground_friction_state = st
    return st


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "label": "Free Object Flat-Ground Friction V1",
        "config_path": "free_resource_object_ground_friction.enabled",
        "enabled": bool(enabled),
        "promotion_class": "EXPERIMENTAL",
        "provenance": "acanthostega_free_object_ground_friction",
        "default_integrated": True,
        "banner": BANNER,
        "analyzer_section": ANALYZER_SECTION,
        "STATIC_FRICTION_FORCE_BALANCING": STATIC_FRICTION_FORCE_BALANCING,
        "FOOTPRINT_MULTI_CELL": FOOTPRINT_MULTI_CELL,
        "AIR_DRAG": AIR_DRAG,
        "legacy_fok_damping_when_active": LEGACY_FOK_DAMPING_WHEN_ACTIVE,
        "body_traction_unchanged": True,
        "scope": {
            "free_moving_grounded": True,
            "free_static": "untouched",
            "airborne": "conserve_horizontal_v",
            "held": False,
            "bodies": False,
            "slopes": False,
            "sound": False,
        },
        "historical_compatibility": "missing key means friction OFF / legacy FOK damping",
    }


def researcher_summary(world: Any) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    return {
        "mechanism": MECHANISM_ID,
        "profile_version": PROFILE_VERSION,
        "banner": BANNER,
        "analyzer_section": ANALYZER_SECTION,
        "counters": dict(st.counters),
        "last_step": st.last_step or None,
        "mu_min": float(st.config.mu_min),
        "mu_max": float(st.config.mu_max),
        "AIR_DRAG": AIR_DRAG,
        "STATIC_FRICTION_FORCE_BALANCING": STATIC_FRICTION_FORCE_BALANCING,
        "legacy_fok_damping_when_active": LEGACY_FOK_DAMPING_WHEN_ACTIVE,
        "body_traction_unchanged": True,
        "agent_accessible": False,
        "researcher_only": True,
    }


def overlay_payload(world: Any) -> dict[str, Any] | None:
    summary = researcher_summary(world)
    if summary is None:
        return None
    return {"caption": BANNER, "active": summary}
