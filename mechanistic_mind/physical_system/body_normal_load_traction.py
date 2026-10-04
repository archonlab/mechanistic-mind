"""Acanthostega BODY NORMAL-LOAD TRACTION + PASSIVE SLIDING V1.

Preset: ACANTHOSTEGA_PHASE_C_BODY_NORMAL_LOAD_TRACTION
Parent: ACANTHOSTEGA_PHASE_C_SURFACE_ELEVATION_SUPPORT
Mechanism: body_normal_load_traction
Profile: BODY_NORMAL_LOAD_TRACTION_PASSIVE_SLIDING_V1
Receipt: BODY_NORMAL_LOAD_TRACTION

CRITICAL: when this mechanism is active, Gentle grounded_damping + v_stop are BYPASSED.
  grounded body  → Coulomb kinetic friction (μ_k from surface_affinity; N = m_eff g)
  airborne body  → friction=0; conserve horizontal from ground channel
  NEVER stack Gentle velocity damp/snap with body Coulomb.
  Gentle env absorb (traction_threshold) is KEPT (not a second friction law).

Physics (FLAT_GROUND_V1 / SES microrelief parent):
  m_eff = locomotor_mass_with_held_load (L+R once) when EHL ON; else body.mass
  N     = m_eff * g
  μ_k   = MU_MIN + (MU_MAX-MU_MIN)*clip(aff)   # same helper numbers as FREE FOGF
  a     = μ_k * g   (mass-independent)
  Coulomb against velocity; no reverse; KE never increases; rest exact when enough impulse.
  Affinity MOVE traction gated on grounded for THIS preset only (prior presets unchanged).

Order: horizontal force integrate → passive friction → SES gate → vertical.
STATIC_FRICTION_FORCE_BALANCING = NOT_IMPLEMENTED
CONTINUOUS_SURFACE_NORMALS = NO
NO gait / jump / excavation / lifecycle / air traction.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from mechanistic_mind.physical_system.flat_ground_gravity import (
    GRAVITY_ACCELERATION,
    flat_ground_gravity_is_active,
)
from mechanistic_mind.physical_system.free_resource_object_ground_friction import (
    MU_MAX,
    MU_MIN,
    NEUTRAL_AFFINITY,
    coulomb_kinetic_step,
    mu_k_from_surface_affinity,
    sample_support_surface_affinity,
)
from mechanistic_mind.physical_system.surface_elevation_support import (
    surface_elevation_support_is_active,
)
from mechanistic_mind.planet.topology import wrap_coord

MECHANISM_ID = "body_normal_load_traction"
PROFILE_VERSION = "BODY_NORMAL_LOAD_TRACTION_PASSIVE_SLIDING_V1"
STATE_SCHEMA = "BODY_NORMAL_LOAD_TRACTION_STATE_V1"
RECEIPT_KIND = "BODY_NORMAL_LOAD_TRACTION"
EVENT_STEP = "BODY_NORMAL_LOAD_TRACTION_STEP"

BANNER = (
    "BODY NORMAL-LOAD TRACTION + PASSIVE SLIDING V1 · N=m_eff g · μ(affinity) · "
    "GENTLE DAMP BYPASS · NO AIR TRACTION"
)
OVERLAY_CAPTION = BANNER
ANALYZER_SECTION = "BODY NORMAL-LOAD TRACTION"

SUPPORT_PROFILE = "FLAT_GROUND_V1"
SUPPORT_SAMPLE_POLICY = "BODY_COM_FLOOR_WRAP_V1"
FRICTION_LAW = "COULOMB_KINETIC_MU_N_V1"
INTEGRATOR = "FRICTION_THEN_DRIFT_WRAP_V1"
AIRBORNE_HORIZONTAL = "CONSERVE_HORIZONTAL_V_NO_AIR_TRACTION_V1"
AFFINITY_COUPLING = "SURFACE_AFFINITY_TO_MU_K_LINEAR_V1"
STATIC_FRICTION_FORCE_BALANCING = "NOT_IMPLEMENTED"
FOOTPRINT_MULTI_CELL = "NOT_IMPLEMENTED"
CONTINUOUS_SURFACE_NORMALS = "NO"
AIR_TRACTION = "NO"
GENTLE_VELOCITY_DAMP_WHEN_ACTIVE = "BYPASSED"
GENTLE_ENV_ABSORB_WHEN_ACTIVE = "KEPT"

DT = 1.0
HISTORY_LIMIT_DEFAULT = 64
REST_THRESHOLD_DEFAULT = 0.006

RESEARCHER_FLAGS = {
    "researcher_only": True,
    "agent_accessible": False,
    "semantic_label": False,
}


@dataclass
class BodyNormalLoadTractionConfig:
    """Fresh default OFF; missing snapshot field = OFF."""

    enabled: bool = False
    mu_min: float = MU_MIN
    mu_max: float = MU_MAX
    rest_threshold: float = REST_THRESHOLD_DEFAULT
    history_limit: int = HISTORY_LIMIT_DEFAULT

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "mu_min": float(self.mu_min),
            "mu_max": float(self.mu_max),
            "rest_threshold": float(self.rest_threshold),
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
            "CONTINUOUS_SURFACE_NORMALS": CONTINUOUS_SURFACE_NORMALS,
            "AIR_TRACTION": AIR_TRACTION,
            "gentle_velocity_damp_when_active": GENTLE_VELOCITY_DAMP_WHEN_ACTIVE,
            "gentle_env_absorb_when_active": GENTLE_ENV_ABSORB_WHEN_ACTIVE,
            "reservoir_credit": False,
            "sound": False,
            "mass_independent_deceleration": True,
            "held_mass_in_normal_load": True,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "BodyNormalLoadTractionConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        ver = data.get("profile_version")
        if ver is not None and str(ver) != PROFILE_VERSION:
            raise ValueError(f"unknown body normal-load traction profile: {ver}")
        return cls(
            enabled=bool(data.get("enabled", False)),
            mu_min=float(data.get("mu_min", MU_MIN)),
            mu_max=float(data.get("mu_max", MU_MAX)),
            rest_threshold=float(data.get("rest_threshold", REST_THRESHOLD_DEFAULT)),
            history_limit=int(data.get("history_limit", HISTORY_LIMIT_DEFAULT)),
        )


def validate_config(cfg: BodyNormalLoadTractionConfig) -> None:
    if not (math.isfinite(cfg.mu_min) and math.isfinite(cfg.mu_max)):
        raise ValueError("mu_min/mu_max must be finite")
    if not (0.0 <= float(cfg.mu_min) <= float(cfg.mu_max) <= 20.0):
        raise ValueError("mu_min/mu_max must satisfy 0 <= mu_min <= mu_max <= 20")
    if not (0.0 < float(cfg.rest_threshold) < 1.0):
        raise ValueError("rest_threshold must be in (0, 1)")
    if not (1 <= int(cfg.history_limit) <= 512):
        raise ValueError("history_limit must be in [1, 512]")


def _line_ok(config: Any) -> bool:
    return config is not None and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"


def body_normal_load_traction_is_active(config: Any) -> bool:
    if not _line_ok(config):
        return False
    cfg = getattr(config, "body_normal_load_traction", None)
    if cfg is None or not bool(getattr(cfg, "enabled", False)):
        return False
    return bool(
        flat_ground_gravity_is_active(config)
        and surface_elevation_support_is_active(config)
    )


def set_body_normal_load_traction(config: Any, enabled: bool) -> None:
    if config is None:
        return
    on = bool(enabled) and _line_ok(config)
    cur = getattr(config, "body_normal_load_traction", None)
    if cur is None:
        if on:
            config.body_normal_load_traction = BodyNormalLoadTractionConfig(enabled=True)
        return
    if isinstance(cur, dict):
        cfg = BodyNormalLoadTractionConfig.from_dict(cur)
        cfg.enabled = on
        config.body_normal_load_traction = cfg
    else:
        cur.enabled = on


def resolve_body_support_cell(x: float, y: float, *, width: int, height: int) -> tuple[int, int]:
    """BODY_COM_FLOOR_WRAP_V1 — same floor-then-wrap as FOGF OBJECT_SUPPORT_FLOOR_WRAP_V1."""
    cell_x = int(wrap_coord(int(math.floor(float(x))), int(width)))
    cell_y = int(wrap_coord(int(math.floor(float(y))), int(height)))
    return cell_x, cell_y


def _read_g(world: Any) -> float:
    st = getattr(world, "flat_ground_gravity_state", None)
    if st is not None and getattr(st, "config", None) is not None:
        return float(getattr(st.config, "g", GRAVITY_ACCELERATION))
    return float(GRAVITY_ACCELERATION)


def _dims(world: Any) -> tuple[int, int]:
    t = getattr(world, "T", None)
    return (int(t.shape[1]), int(t.shape[0])) if t is not None else (32, 32)


def _is_body_grounded(body: Any, config: Any | None = None) -> bool:
    """Prior-tick grounded (horizontal runs before vertical this tick).

    Under SES parent, support height may be nonzero so z≠0 while grounded.
    Authority is body.grounded from the previous vertical step (+ |vz|≈0).
    G2B: when radius-aware ON, also require support_class != LOSS.
    """
    try:
        vz = float(getattr(body, "vz", 0.0) or 0.0)
    except (TypeError, ValueError):
        vz = 0.0
    if not math.isfinite(vz):
        vz = 0.0
    flagged = bool(getattr(body, "grounded", False))
    if not (flagged and abs(vz) <= 1e-12):
        return False
    if config is not None:
        try:
            from mechanistic_mind.physical_system.radius_aware_support_points import (
                eligible_for_ground_traction,
                radius_aware_support_points_is_active,
            )
            if radius_aware_support_points_is_active(config):
                return bool(eligible_for_ground_traction(body, mechanism_active=True))
        except Exception:
            pass
    return True


def effective_normal_load_mass(
    *,
    body_mass: float,
    world: Any,
    holder_body_id: str,
    config: Any,
) -> dict[str, Any]:
    """N uses m_eff from locomotor_mass_with_held_load (L+R once) when EHL ON."""
    from mechanistic_mind.physical_system.effector_work_and_held_load_inertia_accounting import (
        locomotor_mass_with_held_load,
    )

    info = locomotor_mass_with_held_load(
        body_mass=float(body_mass),
        world=world,
        holder_body_id=str(holder_body_id),
        config=config,
    )
    return {
        "body_mass": float(info["body_mass"]),
        "held_mass": float(info["held_mass"]),
        "m_eff": float(info["effective_mass"]),
        "accounting_active": bool(info["accounting_active"]),
        "loads": list(info.get("loads") or []),
    }


@dataclass
class BodyNormalLoadTractionState:
    config: BodyNormalLoadTractionConfig
    last_step: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=lambda: {
        "grounded_friction_steps": 0,
        "airborne_conserve_steps": 0,
        "rest_transitions": 0,
        "gentle_velocity_damp_bypassed": 0,
        "affinity_move_gated_airborne": 0,
    })


def state_of(world: Any) -> BodyNormalLoadTractionState | None:
    raw = getattr(world, "body_normal_load_traction_state", None)
    return raw if isinstance(raw, BodyNormalLoadTractionState) else None


def ensure_body_normal_load_traction_for_runtime(world: Any, config: Any) -> BodyNormalLoadTractionState | None:
    if not body_normal_load_traction_is_active(config):
        if state_of(world) is not None:
            world.body_normal_load_traction_state = None
        return None
    st = state_of(world)
    if st is not None:
        return st
    raw = getattr(config, "body_normal_load_traction", None)
    cfg = (
        BodyNormalLoadTractionConfig.from_dict(raw.to_dict() if hasattr(raw, "to_dict") else raw)
        if raw is not None
        else BodyNormalLoadTractionConfig(enabled=True)
    )
    cfg.enabled = True
    validate_config(cfg)
    st = BodyNormalLoadTractionState(config=cfg)
    world.body_normal_load_traction_state = st
    return st


def prepare_body_coulomb_context(
    world: Any,
    body: Any,
    config: Any,
    *,
    body_mass: float,
    body_id: str,
) -> dict[str, Any] | None:
    """Build per-tick context for CoM integrate. None → mechanism OFF."""
    if not body_normal_load_traction_is_active(config):
        return None
    st = ensure_body_normal_load_traction_for_runtime(world, config)
    if st is None:
        return None
    st.counters["gentle_velocity_damp_bypassed"] = int(
        st.counters.get("gentle_velocity_damp_bypassed", 0)
    ) + 1
    grounded = _is_body_grounded(body, config)
    g = _read_g(world)
    mass_info = effective_normal_load_mass(
        body_mass=float(body_mass),
        world=world,
        holder_body_id=str(body_id),
        config=config,
    )
    m_eff = float(mass_info["m_eff"])
    N = float(m_eff) * float(g)  # PHYSICAL flat N — shadow must not replace this
    # G2D diagnostic shadow (researcher-only; never feeds N / friction).
    try:
        from mechanistic_mind.physical_system.diagnostic_normal_load_shadow import (
            maybe_record_body_shadow,
        )
        entity_kind = "experimenter" if str(body_id).startswith("experimenter") else "body"
        maybe_record_body_shadow(
            world,
            config,
            body=body,
            body_id=str(body_id),
            m_eff=float(m_eff),
            g=float(g),
            grounded=bool(grounded),
            held_mass=float(mass_info["held_mass"]),
            body_mass=float(mass_info["body_mass"]),
            entity_kind=entity_kind,
            seam="BNLT_PREPARE",
        )
    except Exception:
        pass
    # Tangent gravity diagnostic shadow (researcher-only; never feeds motion).
    try:
        from mechanistic_mind.physical_system.tangent_gravity_diagnostic_shadow import (
            maybe_record_body_tangent_shadow,
        )
        entity_kind = "experimenter" if str(body_id).startswith("experimenter") else "body"
        maybe_record_body_tangent_shadow(
            world,
            config,
            body=body,
            body_id=str(body_id),
            m_eff=float(m_eff),
            g=float(g),
            grounded=bool(grounded),
            held_mass=float(mass_info["held_mass"]),
            body_mass=float(mass_info["body_mass"]),
            entity_kind=entity_kind,
            seam="BNLT_PREPARE",
        )
    except Exception:
        pass
    base: dict[str, Any] = {
        "active": True,
        "bypass_gentle_grounded_damping": True,
        "bypass_gentle_v_stop": True,
        "keep_gentle_env_absorb": True,
        "grounded": bool(grounded),
        "g": float(g),
        "dt": float(DT),
        "m_eff": float(m_eff),
        "held_mass": float(mass_info["held_mass"]),
        "body_mass": float(mass_info["body_mass"]),
        "normal_load_N": float(N),
        "rest_threshold": float(st.config.rest_threshold),
        "mu_min": float(st.config.mu_min),
        "mu_max": float(st.config.mu_max),
        "body_id": str(body_id),
        "support_profile": SUPPORT_PROFILE,
        "support_sample_policy": SUPPORT_SAMPLE_POLICY,
        "friction_law": FRICTION_LAW,
        "integrator": INTEGRATOR,
        "STATIC_FRICTION_FORCE_BALANCING": STATIC_FRICTION_FORCE_BALANCING,
        "CONTINUOUS_SURFACE_NORMALS": CONTINUOUS_SURFACE_NORMALS,
        "AIR_TRACTION": AIR_TRACTION,
        "reservoir_credit": False,
        "sound": False,
        **RESEARCHER_FLAGS,
    }
    if not grounded:
        st.counters["airborne_conserve_steps"] = int(st.counters.get("airborne_conserve_steps", 0)) + 1
        air = {
            **base,
            "apply_coulomb": False,
            "mode": "AIRBORNE_CONSERVE",
            "mu_k": None,
            "surface_affinity": None,
        }
        return _attach_static_traction_ctx(air, config, world=world, body=body)
    w, h = _dims(world)
    # Reuse FOGF affinity sampler (same deposit → surface_affinity path).
    sample = sample_support_surface_affinity(
        world, float(body.x), float(body.y), width=w, height=h
    )
    # Relabel sample policy for body COM (same floor-wrap math).
    sample = dict(sample)
    sample["support_sample_policy"] = SUPPORT_SAMPLE_POLICY
    mu_k = mu_k_from_surface_affinity(
        sample["surface_affinity"], mu_min=st.config.mu_min, mu_max=st.config.mu_max
    )
    out = {
        **base,
        "apply_coulomb": True,
        "mode": "GROUNDED_COULOMB",
        "mu_k": float(mu_k),
        **sample,
    }
    # Coherent slope dynamics: migrate N → projected + attach g_t force payload.
    try:
        from mechanistic_mind.physical_system.coherent_slope_dynamics import (
            attach_slope_forces_to_bnlt_ctx,
            coherent_slope_dynamics_is_active,
            record_pre_integrate_snapshot,
        )

        if coherent_slope_dynamics_is_active(config):
            out = attach_slope_forces_to_bnlt_ctx(out, world, config, body=body)
            record_pre_integrate_snapshot(
                world,
                config,
                entity_id=str(body_id),
                m_eff=float(m_eff),
                vx=float(getattr(body, "vx", 0.0) or 0.0),
                vy=float(getattr(body, "vy", 0.0) or 0.0),
                z=float(getattr(body, "z", 0.0) or 0.0),
                work_reservoir=float(
                    getattr(body, "mechanical_work_reservoir", 0.0) or 0.0
                ),
            )
    except Exception:
        pass
    return _attach_static_traction_ctx(out, config, st_world=None, world=world, body=body)


def _attach_static_traction_ctx(
    ctx: dict[str, Any],
    config: Any,
    *,
    st_world=None,
    world: Any = None,
    body: Any = None,
) -> dict[str, Any]:
    """If G2A static mechanism ON, attach μ_s + config for integrate_com_translation."""
    try:
        from mechanistic_mind.physical_system.body_static_traction_threshold import (
            body_static_traction_threshold_is_active,
            ensure_body_static_traction_threshold_for_runtime,
            mu_static_from_surface_affinity,
            state_of as static_state_of,
        )
    except Exception:
        ctx["static_traction_active"] = False
        return ctx
    if not body_static_traction_threshold_is_active(config):
        ctx["static_traction_active"] = False
        return ctx
    st_s = ensure_body_static_traction_threshold_for_runtime(world, config) if world is not None else None
    if st_s is None and world is not None:
        st_s = static_state_of(world)
    if st_s is None:
        ctx["static_traction_active"] = False
        return ctx
    ctx["static_traction_active"] = True
    ctx["static_config"] = st_s.config
    aff = ctx.get("surface_affinity")
    if aff is not None and ctx.get("apply_coulomb"):
        pair = mu_static_from_surface_affinity(
            float(aff),
            mu_min=float(st_s.config.mu_min),
            mu_max=float(st_s.config.mu_max),
            static_ratio=float(st_s.config.static_ratio),
        )
        ctx["mu_static"] = float(pair["mu_static"])
        ctx["static_ratio"] = float(pair["static_ratio"])
        # keep mu_k consistent with static helper
        ctx["mu_k"] = float(pair["mu_k"])
    else:
        ctx["mu_static"] = None
    # Beta 4 MOVE breakaway repair: attach tick-local capacity-limited impulse.
    try:
        from mechanistic_mind.physical_system.bnlt_move_breakaway_locomotion_repair import (
            bnlt_move_breakaway_locomotion_repair_is_active,
            read_move_impulse_xy,
        )

        if bnlt_move_breakaway_locomotion_repair_is_active(config) and body is not None:
            ctx["move_breakaway_repair_active"] = True
            ctx["move_impulse_xy"] = read_move_impulse_xy(body)
        else:
            ctx["move_breakaway_repair_active"] = False
    except Exception:
        ctx["move_breakaway_repair_active"] = False
    try:
        from mechanistic_mind.physical_system.active_locomotion_traction_vs_sliding_friction import (
            active_locomotion_traction_vs_sliding_friction_is_active,
        )

        ctx["active_locomotion_traction_vs_sliding_friction_active"] = bool(
            active_locomotion_traction_vs_sliding_friction_is_active(config)
        )
    except Exception:
        ctx["active_locomotion_traction_vs_sliding_friction_active"] = False
    return ctx


def apply_body_coulomb_to_velocity(
    vx: float,
    vy: float,
    ctx: dict[str, Any],
) -> dict[str, Any]:
    """Apply coulomb_kinetic_step when grounded; else conserve. KE never increases."""
    if not ctx or not ctx.get("active"):
        return {
            "vx": float(vx),
            "vy": float(vy),
            "applied": False,
            "mode": "OFF",
        }
    if not ctx.get("apply_coulomb"):
        speed = float(math.hypot(vx, vy))
        return {
            "vx": float(vx),
            "vy": float(vy),
            "applied": False,
            "mode": "AIRBORNE_CONSERVE",
            "speed_before": speed,
            "speed_after": speed,
            "kinetic_dissipated": 0.0,
            "rest_transition": False,
            "gentle_bypassed": True,
        }
    fric_a = ctx.get("slope_friction_accel")
    drive_a = ctx.get("slope_drive_accel")
    if drive_a is None and ctx.get("slope_g_t_magnitude") is not None:
        drive_a = float(ctx.get("slope_g_t_magnitude") or 0.0)
    step = coulomb_kinetic_step(
        float(vx),
        float(vy),
        mu_k=float(ctx["mu_k"]),
        g=float(ctx["g"]),
        dt=float(ctx.get("dt", DT)),
        rest_threshold=float(ctx["rest_threshold"]),
        friction_accel=float(fric_a) if fric_a is not None else None,
        drive_accel=float(drive_a) if drive_a is not None else None,
    )
    m_eff = float(ctx["m_eff"])
    k0 = 0.5 * m_eff * float(step["speed_before"]) ** 2
    k1 = 0.5 * m_eff * float(step["speed_after"]) ** 2
    dissipated = max(0.0, k0 - k1)
    # Invariant: friction never increases KE / never reverses direction.
    assert dissipated >= -1e-15
    assert float(step["speed_after"]) <= float(step["speed_before"]) + 1e-15
    return {
        "vx": float(step["vx"]),
        "vy": float(step["vy"]),
        "applied": True,
        "mode": "GROUNDED_COULOMB",
        "mu_k": float(ctx["mu_k"]),
        "a": float(step["a"]),
        "dv": float(step["dv"]),
        "speed_before": float(step["speed_before"]),
        "speed_after": float(step["speed_after"]),
        "kinetic_before": float(k0),
        "kinetic_after": float(k1),
        "kinetic_dissipated": float(dissipated),
        "rest_transition": bool(step["rest_transition"]),
        "stopped_by_friction": bool(step["stopped_by_friction"]),
        "normal_load_N": float(ctx["normal_load_N"]),
        "m_eff": float(m_eff),
        "held_mass": float(ctx.get("held_mass") or 0.0),
        "mass_independent_a": True,
        "gentle_bypassed": True,
        "surface_affinity": ctx.get("surface_affinity"),
        "cell_x": ctx.get("cell_x"),
        "cell_y": ctx.get("cell_y"),
        "deposit_id": ctx.get("deposit_id"),
        "deposit_present": ctx.get("deposit_present"),
    }


def record_body_traction_receipt(
    world: Any,
    *,
    tick: int,
    body_id: str,
    ctx: dict[str, Any],
    friction: dict[str, Any],
    velocity_before: list[float],
    velocity_after: list[float],
    start_position: list[float],
    end_position: list[float],
    gentle_grounded_damping_bypassed: bool,
    gentle_v_stop_bypassed: bool,
) -> dict[str, Any]:
    st = state_of(world)
    if friction.get("applied"):
        if st is not None:
            st.counters["grounded_friction_steps"] = int(
                st.counters.get("grounded_friction_steps", 0)
            ) + 1
            if friction.get("rest_transition"):
                st.counters["rest_transitions"] = int(st.counters.get("rest_transitions", 0)) + 1
    rec = {
        "receipt_kind": RECEIPT_KIND,
        "event": EVENT_STEP,
        "tick": int(tick),
        "body_id": str(body_id),
        "mechanism": MECHANISM_ID,
        "profile_version": PROFILE_VERSION,
        "banner": BANNER,
        "start_position": list(start_position),
        "end_position": list(end_position),
        "velocity_before": list(velocity_before),
        "velocity_after": list(velocity_after),
        "gentle_grounded_damping_bypassed": bool(gentle_grounded_damping_bypassed),
        "gentle_v_stop_bypassed": bool(gentle_v_stop_bypassed),
        "gentle_env_absorb_kept": True,
        "mode": friction.get("mode") or ctx.get("mode"),
        "grounded": bool(ctx.get("grounded")),
        "mu_k": friction.get("mu_k", ctx.get("mu_k")),
        "a": friction.get("a"),
        "dv": friction.get("dv"),
        "g": ctx.get("g"),
        "dt": ctx.get("dt", DT),
        "normal_load_N": friction.get("normal_load_N", ctx.get("normal_load_N")),
        "m_eff": friction.get("m_eff", ctx.get("m_eff")),
        "held_mass": friction.get("held_mass", ctx.get("held_mass")),
        "body_mass": ctx.get("body_mass"),
        "surface_affinity": friction.get("surface_affinity", ctx.get("surface_affinity")),
        "cell_x": friction.get("cell_x", ctx.get("cell_x")),
        "cell_y": friction.get("cell_y", ctx.get("cell_y")),
        "deposit_id": friction.get("deposit_id", ctx.get("deposit_id")),
        "deposit_present": friction.get("deposit_present", ctx.get("deposit_present")),
        "speed_before": friction.get("speed_before"),
        "speed_after": friction.get("speed_after"),
        "kinetic_before": friction.get("kinetic_before"),
        "kinetic_after": friction.get("kinetic_after"),
        "kinetic_dissipated": friction.get("kinetic_dissipated", 0.0),
        "rest_transition": bool(friction.get("rest_transition")),
        "stopped_by_friction": bool(friction.get("stopped_by_friction")),
        "mass_independent_a": True,
        "friction_law": FRICTION_LAW,
        "integrator": INTEGRATOR,
        "support_sample_policy": SUPPORT_SAMPLE_POLICY,
        "affinity_coupling": AFFINITY_COUPLING,
        "STATIC_FRICTION_FORCE_BALANCING": STATIC_FRICTION_FORCE_BALANCING,
        "CONTINUOUS_SURFACE_NORMALS": CONTINUOUS_SURFACE_NORMALS,
        "AIR_TRACTION": AIR_TRACTION,
        "reservoir_credit": False,
        "sound": False,
        **RESEARCHER_FLAGS,
    }
    if st is not None:
        st.last_step = rec
        st.history.append(rec)
        lim = int(st.config.history_limit)
        if len(st.history) > lim:
            st.history = st.history[-lim:]
        world.last_body_normal_load_traction_step = rec
    return rec


def note_affinity_move_gated_airborne(world: Any) -> None:
    st = state_of(world)
    if st is None:
        return
    st.counters["affinity_move_gated_airborne"] = int(
        st.counters.get("affinity_move_gated_airborne", 0)
    ) + 1


def serialize_state(st: BodyNormalLoadTractionState | None) -> dict[str, Any] | None:
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


def restore_state(world: Any, data: dict[str, Any] | None, config: Any) -> BodyNormalLoadTractionState | None:
    if not body_normal_load_traction_is_active(config):
        world.body_normal_load_traction_state = None
        return None
    if not isinstance(data, dict) or not data:
        return ensure_body_normal_load_traction_for_runtime(world, config)
    if str(data.get("schema")) != STATE_SCHEMA and data.get("schema_version") != STATE_SCHEMA:
        if data.get("schema") is not None or data.get("schema_version") is not None:
            raise ValueError(
                f"unknown body normal-load traction state schema: "
                f"{data.get('schema') or data.get('schema_version')}"
            )
        return ensure_body_normal_load_traction_for_runtime(world, config)
    raw_cfg = data.get("config")
    if raw_cfg is None:
        cur = getattr(config, "body_normal_load_traction", None)
        raw_cfg = cur.to_dict() if cur is not None and hasattr(cur, "to_dict") else None
    cfg = BodyNormalLoadTractionConfig.from_dict(raw_cfg)
    validate_config(cfg)
    st = BodyNormalLoadTractionState(
        config=cfg,
        last_step=dict(data["last_step"]) if isinstance(data.get("last_step"), dict) else {},
        history=list(data.get("history") or []),
        counters={**{
            "grounded_friction_steps": 0,
            "airborne_conserve_steps": 0,
            "rest_transitions": 0,
            "gentle_velocity_damp_bypassed": 0,
            "affinity_move_gated_airborne": 0,
        }, **{k: int(v) for k, v in dict(data.get("counters") or {}).items()}},
    )
    world.body_normal_load_traction_state = st
    return st


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "label": "Body Normal-Load Traction + Passive Sliding V1",
        "config_path": "body_normal_load_traction.enabled",
        "enabled": bool(enabled),
        "promotion_class": "EXPERIMENTAL",
        "provenance": "acanthostega_body_normal_load_traction",
        "default_integrated": True,
        "banner": BANNER,
        "analyzer_section": ANALYZER_SECTION,
        "STATIC_FRICTION_FORCE_BALANCING": STATIC_FRICTION_FORCE_BALANCING,
        "CONTINUOUS_SURFACE_NORMALS": CONTINUOUS_SURFACE_NORMALS,
        "AIR_TRACTION": AIR_TRACTION,
        "gentle_velocity_damp_when_active": GENTLE_VELOCITY_DAMP_WHEN_ACTIVE,
        "gentle_env_absorb_when_active": GENTLE_ENV_ABSORB_WHEN_ACTIVE,
        "scope": {
            "bodies": True,
            "grounded": "coulomb_kinetic",
            "airborne": "no_ground_mu",
            "free_objects": "unchanged_fogf",
            "slopes": False,
            "sound": False,
            "static_cone": False,
        },
        "historical_compatibility": "missing key means body Coulomb OFF / Gentle damp as parent",
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
        "AIR_TRACTION": AIR_TRACTION,
        "STATIC_FRICTION_FORCE_BALANCING": STATIC_FRICTION_FORCE_BALANCING,
        "CONTINUOUS_SURFACE_NORMALS": CONTINUOUS_SURFACE_NORMALS,
        "gentle_velocity_damp_when_active": GENTLE_VELOCITY_DAMP_WHEN_ACTIVE,
        "gentle_env_absorb_when_active": GENTLE_ENV_ABSORB_WHEN_ACTIVE,
        "agent_accessible": False,
        "researcher_only": True,
    }


def overlay_payload(world: Any) -> dict[str, Any] | None:
    summary = researcher_summary(world)
    if summary is None:
        return None
    return {"caption": BANNER, "active": summary}
