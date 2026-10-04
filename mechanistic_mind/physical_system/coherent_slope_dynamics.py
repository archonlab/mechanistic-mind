"""Acanthostega PHASE C · Coherent slope dynamics (gated atomic activation).

Preset: ACANTHOSTEGA_PHASE_C_COHERENT_SLOPE_DYNAMICS
Parent: ACANTHOSTEGA_PHASE_C_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW
Mechanism: coherent_slope_dynamics
Profile: COHERENT_SLOPE_DYNAMICS_WORK_IDENTITY_V1

Atomic live bundle (BODY only; FREE objects excluded):
  - tangent gravity via height-field xy reduction of CENTRE_ANALYTIC_CSG_N_HAT g_t
  - projected normal load N = m_eff · g · n_z for BNLT / G2A static+kinetic
  - static hold balances |m g_t| against μ_s N when WAIT-eligible
  - breakaway / passive downhill when demand exceeds capacity
  - Policy C endpoint ΔU = measurement only (no ±ΔU reservoir/KE actuator)

Hard invariants:
  SECOND_INTEGRATION = NO (inject into existing integrate_com_translation)
  FREE_OBJECT_SLOPE_DYNAMICS = NO (separate boundary)
  HELD_MASS_DOUBLE_COUNTING = NO (m_eff once)
  SES / Face Sweep unchanged (gates only)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from mechanistic_mind.physical_system.continuous_gravitational_pe import (
    continuous_gravitational_pe_is_active,
)
from mechanistic_mind.physical_system.continuous_surface_geometry import (
    sample_surface_geometry,
)
from mechanistic_mind.physical_system.diagnostic_normal_load_shadow import (
    NORMAL_SOURCE as G2D_NORMAL_SOURCE,
    compute_projected_normal_load,
    diagnostic_normal_load_shadow_is_active,
)
from mechanistic_mind.physical_system.slope_dynamics_work_identity import (
    WORK_IDENTITY_ABS_TOL,
    build_work_identity_receipt,
    height_field_xy_gravity_acceleration,
    kinetic_energy,
    tangent_demand_impulse,
)
from mechanistic_mind.physical_system.tangent_gravity_diagnostic_shadow import (
    tangent_gravity_diagnostic_shadow_is_active,
)

MECHANISM_ID = "coherent_slope_dynamics"
PROFILE_VERSION = "COHERENT_SLOPE_DYNAMICS_WORK_IDENTITY_V1"
STAGE_ALIAS = "COHERENT_SLOPE_DYNAMICS_WORK_IDENTITY_V1"
STATE_SCHEMA = "COHERENT_SLOPE_DYNAMICS_STATE_V1"
RECEIPT_KIND = "COHERENT_SLOPE_DYNAMICS"

NORMAL_SOURCE = G2D_NORMAL_SOURCE  # CENTRE_ANALYTIC_CSG_N_HAT

BANNER = (
    "SLOPE DYNAMICS: ACTIVE\n"
    "GRAVITY: TANGENT + NORMAL DECOMPOSITION\n"
    "NORMAL LOAD: PROJECTED\n"
    "STATIC HOLD: ACTIVE\n"
    "PASSIVE BREAKAWAY: ACTIVE\n"
    "PE AUTHORITY: CONTINUOUS ENDPOINT ΔU (MEASUREMENT)"
)
OVERLAY_CAPTION = BANNER
ANALYZER_SECTION = "COHERENT SLOPE DYNAMICS"

HISTORY_LIMIT_DEFAULT = 64
EPS_ZERO = 1e-12
EPS_NZ = 1e-9

RESEARCHER_FLAGS = {
    "researcher_only": True,
    "agent_accessible": False,
    "semantic_label": False,
    "influenced_physics": True,
    "normal_source": NORMAL_SOURCE,
    "free_object_slope_dynamics": False,
}


@dataclass
class CoherentSlopeDynamicsConfig:
    enabled: bool = False
    history_limit: int = HISTORY_LIMIT_DEFAULT
    normal_source: str = NORMAL_SOURCE
    # When True: Policy C ±ΔU must not mutate reservoir/KE (measurement only).
    policy_c_measurement_only: bool = True
    # BODY only in this bundle.
    apply_to_body: bool = True
    apply_to_free_objects: bool = False

    def to_dict(self) -> dict[str, Any]:
        on = bool(self.enabled)
        return {
            "enabled": on,
            "history_limit": int(self.history_limit),
            "normal_source": str(self.normal_source),
            "policy_c_measurement_only": bool(self.policy_c_measurement_only),
            "apply_to_body": bool(self.apply_to_body),
            "apply_to_free_objects": bool(self.apply_to_free_objects),
            "profile_version": PROFILE_VERSION,
            "stage_alias": STAGE_ALIAS,
            "tangent_gravity_active": bool(on),
            "projected_normal_load_active": bool(on),
            "static_slope_hold_active": bool(on),
            "passive_slope_sliding_active": bool(on),
            "kinetic_friction_uses_projected_n": bool(on),
            "influenced_physics": bool(on),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "CoherentSlopeDynamicsConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        ver = data.get("profile_version")
        if ver is not None and str(ver) != PROFILE_VERSION:
            raise ValueError(f"unknown coherent_slope_dynamics profile: {ver}")
        return cls(
            enabled=bool(data.get("enabled", False)),
            history_limit=int(data.get("history_limit", HISTORY_LIMIT_DEFAULT)),
            normal_source=str(data.get("normal_source", NORMAL_SOURCE)),
            policy_c_measurement_only=bool(data.get("policy_c_measurement_only", True)),
            apply_to_body=bool(data.get("apply_to_body", True)),
            apply_to_free_objects=bool(data.get("apply_to_free_objects", False)),
        )


def validate_config(cfg: CoherentSlopeDynamicsConfig) -> None:
    if not (1 <= int(cfg.history_limit) <= 512):
        raise ValueError("history_limit must be in [1, 512]")
    if str(cfg.normal_source) != NORMAL_SOURCE:
        raise ValueError(f"normal_source must be {NORMAL_SOURCE}")
    if bool(cfg.apply_to_free_objects):
        raise ValueError("FREE_OBJECT_SLOPE_DYNAMICS_NOT_IN_BUNDLE")


def _line_ok(config: Any) -> bool:
    return (
        config is not None
        and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"
    )


def coherent_slope_dynamics_is_active(config: Any) -> bool:
    if not _line_ok(config):
        return False
    cfg = getattr(config, "coherent_slope_dynamics", None)
    if cfg is None or not bool(getattr(cfg, "enabled", False)):
        return False
    # Parent chain: tangent shadow (⇒ Policy C + G2D) must be present.
    if not tangent_gravity_diagnostic_shadow_is_active(config):
        return False
    if not continuous_gravitational_pe_is_active(config):
        return False
    if not diagnostic_normal_load_shadow_is_active(config):
        return False
    return True


def set_coherent_slope_dynamics(config: Any, enabled: bool) -> None:
    if config is None:
        return
    on = bool(enabled) and _line_ok(config)
    cur = getattr(config, "coherent_slope_dynamics", None)
    if cur is None:
        if on:
            config.coherent_slope_dynamics = CoherentSlopeDynamicsConfig(enabled=True)
        return
    if isinstance(cur, dict):
        cur = CoherentSlopeDynamicsConfig.from_dict(cur)
        config.coherent_slope_dynamics = cur
    cur.enabled = bool(on)


def policy_c_measurement_only_required(config: Any) -> bool:
    """When slope dynamics live, Policy C must not actuator-mutate ±ΔU."""
    if not coherent_slope_dynamics_is_active(config):
        return False
    cfg = getattr(config, "coherent_slope_dynamics", None)
    return bool(getattr(cfg, "policy_c_measurement_only", True))


def tangent_gravity_physically_active(config: Any) -> bool:
    return coherent_slope_dynamics_is_active(config)


def projected_normal_load_physically_active(config: Any) -> bool:
    return coherent_slope_dynamics_is_active(config)


@dataclass
class CoherentSlopeDynamicsState:
    config: CoherentSlopeDynamicsConfig = field(
        default_factory=CoherentSlopeDynamicsConfig
    )
    counters: dict[str, int] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    last_receipt: dict[str, Any] | None = None
    last_work_identity: dict[str, Any] | None = None
    tick_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Per-entity pre-integrate snapshots for work-identity (cleared each tick).
    pre_integrate: dict[str, dict[str, Any]] = field(default_factory=dict)
    last_tick: int = -1
    restore_suppress_until_tick: int | None = None
    last_error: str | None = None

    def reset_tick(self, tick: int) -> None:
        if int(tick) != int(self.last_tick):
            self.tick_results = {}
            self.pre_integrate = {}
            self.last_tick = int(tick)


def state_of(world: Any) -> CoherentSlopeDynamicsState | None:
    return getattr(world, "coherent_slope_dynamics_state", None)


def ensure_coherent_slope_dynamics_for_runtime(
    world: Any, config: Any
) -> CoherentSlopeDynamicsState | None:
    if not coherent_slope_dynamics_is_active(config):
        return state_of(world)
    st = state_of(world)
    cfg = getattr(config, "coherent_slope_dynamics", None)
    if not isinstance(cfg, CoherentSlopeDynamicsConfig):
        cfg = CoherentSlopeDynamicsConfig.from_dict(
            cfg if isinstance(cfg, dict) else None
        )
        validate_config(cfg)
        config.coherent_slope_dynamics = cfg
    else:
        validate_config(cfg)
    if st is None:
        st = CoherentSlopeDynamicsState(config=cfg)
        world.coherent_slope_dynamics_state = st
    else:
        st.config = cfg
    return st


def serialize_state(st: CoherentSlopeDynamicsState | None) -> dict[str, Any] | None:
    if st is None:
        return None
    return {
        "schema": STATE_SCHEMA,
        "config": st.config.to_dict(),
        "counters": dict(st.counters or {}),
        "last_tick": int(st.last_tick),
    }


def restore_state(
    world: Any,
    payload: dict[str, Any] | None,
    config: Any | None = None,
) -> CoherentSlopeDynamicsState | None:
    """Restore flags/counters only — no force/work replay."""
    if not isinstance(payload, dict) or not payload:
        if world is not None:
            world.coherent_slope_dynamics_state = None
        return None
    if config is not None and not coherent_slope_dynamics_is_active(config):
        world.coherent_slope_dynamics_state = None
        return None
    cfg = CoherentSlopeDynamicsConfig.from_dict(payload.get("config"))
    validate_config(cfg)
    st = CoherentSlopeDynamicsState(config=cfg)
    st.counters = {str(k): int(v) for k, v in dict(payload.get("counters") or {}).items()}
    st.last_tick = int(payload.get("last_tick", -1) or -1)
    st.restore_suppress_until_tick = int(getattr(world, "tick", 0) or 0)
    # Clear pending integrate / history to prevent replay.
    st.pre_integrate = {}
    st.history = []
    st.last_receipt = None
    st.last_work_identity = None
    world.coherent_slope_dynamics_state = st
    return st


def observer_banner(config: Any | None) -> str:
    if coherent_slope_dynamics_is_active(config):
        return BANNER
    return (
        "SLOPE DYNAMICS: OFF\n"
        "g_t / PROJECTED N / STATIC HOLD / SLIDE: INACTIVE"
    )


def _sample_n_hat(world: Any, config: Any, x: float, y: float) -> tuple[float, float, float] | None:
    try:
        geom = sample_surface_geometry(world, float(x), float(y), config=config)
    except Exception:
        return None
    if not isinstance(geom, dict):
        return None
    try:
        nx = float(geom["normal_x"])
        ny = float(geom["normal_y"])
        nz = float(geom["normal_z"])
    except Exception:
        return None
    if not all(math.isfinite(v) for v in (nx, ny, nz)):
        return None
    if nz < 0.0:
        return None
    return (nx, ny, nz)


def query_body_slope_forces(
    world: Any,
    config: Any,
    *,
    body: Any,
    m_eff: float,
    g: float,
    grounded: bool,
) -> dict[str, Any] | None:
    """Compute live g_t / a_xy / N_proj for a grounded BODY. None if ineligible."""
    if not coherent_slope_dynamics_is_active(config):
        return None
    if not grounded:
        return None
    x = float(getattr(body, "x", 0.0) or 0.0)
    y = float(getattr(body, "y", 0.0) or 0.0)
    n_hat = _sample_n_hat(world, config, x, y)
    if n_hat is None:
        return None
    red = height_field_xy_gravity_acceleration(n_hat=n_hat, g=float(g))
    ax, ay = red["a_xy"]
    nz = float(red["n_z"])
    proj = compute_projected_normal_load(
        m_eff=float(m_eff),
        g=float(g),
        n_z=float(nz),
        grounded=True,
        support_class=None,
        geometry_ok=True,
    )
    N = float(proj.get("N_projected") or (float(m_eff) * float(g) * float(nz)))
    gt_mag = float(red["candidate_tangent_gravity_magnitude"])
    return {
        "n_hat": n_hat,
        "a_xy": (float(ax), float(ay)),
        "F_gt_xy": (float(m_eff) * float(ax), float(m_eff) * float(ay)),
        "g_t": red["candidate_tangent_gravity_vector"],
        "g_t_magnitude": float(gt_mag),
        "N_projected": float(N),
        "n_z": float(nz),
        "flat": bool(red.get("flat")),
        "normal_source": NORMAL_SOURCE,
        "height_field_reduction": red.get("height_field_reduction"),
        "friction_accel": float(N) / max(float(m_eff), EPS_ZERO),  # = g * n_z
    }


def attach_slope_forces_to_bnlt_ctx(
    ctx: dict[str, Any],
    world: Any,
    config: Any,
    *,
    body: Any,
) -> dict[str, Any]:
    """Mutate BNLT ctx: projected N + slope force payload when mechanism active."""
    if not coherent_slope_dynamics_is_active(config):
        ctx["coherent_slope_dynamics_active"] = False
        return ctx
    if not bool(ctx.get("grounded")):
        ctx["coherent_slope_dynamics_active"] = False
        return ctx
    m_eff = float(ctx.get("m_eff") or 0.0)
    g = float(ctx.get("g") or 0.0)
    q = query_body_slope_forces(
        world, config, body=body, m_eff=m_eff, g=g, grounded=True
    )
    if q is None:
        ctx["coherent_slope_dynamics_active"] = False
        return ctx
    ctx["coherent_slope_dynamics_active"] = True
    ctx["normal_load_N"] = float(q["N_projected"])
    ctx["projected_normal_load_active"] = True
    ctx["N_LAW"] = "N_PROJECTED_M_EFF_G_NZ"
    ctx["slope_a_xy"] = q["a_xy"]
    ctx["slope_F_gt_xy"] = q["F_gt_xy"]
    ctx["slope_g_t_magnitude"] = float(q["g_t_magnitude"])
    ctx["slope_drive_accel"] = float(q["g_t_magnitude"])  # |a_drive| for force-aware rest
    ctx["slope_n_hat"] = q["n_hat"]
    ctx["slope_friction_accel"] = float(q["friction_accel"])  # replaces g in μ_k g
    ctx["tangent_gravity_active"] = True
    return ctx


def compose_slope_force_into_horizontal(
    fx: float,
    fy: float,
    bnlt_ctx: dict[str, Any] | None,
) -> tuple[float, float, dict[str, Any] | None]:
    """Add F_gt_xy AFTER Gentle absorb — single integration entry."""
    if not isinstance(bnlt_ctx, dict) or not bnlt_ctx.get("coherent_slope_dynamics_active"):
        return float(fx), float(fy), None
    fgt = bnlt_ctx.get("slope_F_gt_xy") or (0.0, 0.0)
    fx2 = float(fx) + float(fgt[0])
    fy2 = float(fy) + float(fgt[1])
    meta = {
        "F_gt_xy": (float(fgt[0]), float(fgt[1])),
        "a_xy": bnlt_ctx.get("slope_a_xy"),
        "g_t_magnitude": bnlt_ctx.get("slope_g_t_magnitude"),
        "injected": True,
    }
    return fx2, fy2, meta


def static_hold_uses_tangent_demand(bnlt_ctx: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(bnlt_ctx, dict)
        and bnlt_ctx.get("coherent_slope_dynamics_active")
        and bnlt_ctx.get("slope_g_t_magnitude") is not None
    )


def resolve_static_hold_magnitude(
    *,
    m_eff: float,
    speed_trial: float,
    bnlt_ctx: dict[str, Any],
    dt: float,
) -> tuple[float, str]:
    """Return (j_hold_mag, mode).

    With COULOMB_MATCHED a_xy, residual |m v_trial| from rest equals |m g_t| dt,
    so classic tanθ ≤ μ_s is recovered. Still take max with tangent demand for
    numerical safety when absorb/order differs slightly.
    """
    j_vel = float(m_eff) * float(speed_trial)
    if not static_hold_uses_tangent_demand(bnlt_ctx):
        return j_vel, "RESIDUAL_VELOCITY"
    gt = float(bnlt_ctx.get("slope_g_t_magnitude") or 0.0)
    j_gt = tangent_demand_impulse(m_eff=m_eff, g_t_magnitude=gt, dt=dt)
    return float(max(j_vel, j_gt)), "MAX_RESIDUAL_VELOCITY_AND_TANGENT_DEMAND"


def record_pre_integrate_snapshot(
    world: Any,
    config: Any,
    *,
    entity_id: str,
    m_eff: float,
    vx: float,
    vy: float,
    z: float,
    work_reservoir: float | None = None,
) -> None:
    st = ensure_coherent_slope_dynamics_for_runtime(world, config)
    if st is None:
        return
    tick = int(getattr(world, "tick", 0) or 0)
    st.reset_tick(tick)
    if st.restore_suppress_until_tick is not None and tick <= int(st.restore_suppress_until_tick):
        return
    st.pre_integrate[str(entity_id)] = {
        "k": kinetic_energy(m_eff=m_eff, vx=vx, vy=vy),
        "z": float(z),
        "m_eff": float(m_eff),
        "work_reservoir": float(work_reservoir) if work_reservoir is not None else None,
        "vx": float(vx),
        "vy": float(vy),
    }


def finalize_body_tick_receipt(
    world: Any,
    config: Any,
    *,
    entity_id: str,
    entity_kind: str,
    m_eff: float,
    g: float,
    vx: float,
    vy: float,
    z: float,
    d_friction: float,
    w_motor: float,
    endpoint_delta_u: float | None,
    endpoint_pe_applied: float,
    endpoint_pe_dissipated: float,
    slope_meta: dict[str, Any] | None,
    static_hold: bool | None,
) -> dict[str, Any] | None:
    st = ensure_coherent_slope_dynamics_for_runtime(world, config)
    if st is None or not coherent_slope_dynamics_is_active(config):
        return None
    tick = int(getattr(world, "tick", 0) or 0)
    if st.restore_suppress_until_tick is not None and tick <= int(st.restore_suppress_until_tick):
        return None
    pre = st.pre_integrate.pop(str(entity_id), None) or {}
    k0 = float(pre.get("k") or kinetic_energy(m_eff=m_eff, vx=0.0, vy=0.0))
    z0 = float(pre.get("z") if pre.get("z") is not None else z)
    k1 = kinetic_energy(m_eff=m_eff, vx=vx, vy=vy)
    measurement_only = policy_c_measurement_only_required(config)
    n_hat = None
    gt_mag = None
    N_proj = None
    if isinstance(slope_meta, dict):
        n_hat = slope_meta.get("n_hat") or slope_meta.get("slope_n_hat")
        gt_mag = slope_meta.get("g_t_magnitude") or slope_meta.get("slope_g_t_magnitude")
        N_proj = slope_meta.get("N_projected")
    wi = build_work_identity_receipt(
        tick=tick,
        entity_id=str(entity_id),
        entity_kind=str(entity_kind),
        k_start=k0,
        k_end=k1,
        z_start=z0,
        z_end=float(z),
        m_eff=float(m_eff),
        g=float(g),
        delta_u=endpoint_delta_u,
        d_friction=float(d_friction),
        w_motor=float(w_motor),
        endpoint_pe_applied=float(endpoint_pe_applied),
        endpoint_pe_dissipated=float(endpoint_pe_dissipated),
        measurement_only=bool(measurement_only),
        g_t_magnitude=float(gt_mag) if gt_mag is not None else None,
        n_hat=tuple(n_hat) if n_hat is not None else None,
        N_projected=float(N_proj) if N_proj is not None else None,
        static_hold=static_hold,
    )
    receipt = {
        "receipt_kind": RECEIPT_KIND,
        "mechanism": MECHANISM_ID,
        "profile_version": PROFILE_VERSION,
        "tick": int(tick),
        "entity_id": str(entity_id),
        "entity_kind": str(entity_kind),
        "tangent_gravity_active": True,
        "projected_normal_load_active": True,
        "static_slope_hold_active": True,
        "passive_slope_sliding_active": True,
        "kinetic_friction_uses_projected_n": True,
        "policy_c_measurement_only": bool(measurement_only),
        "banner": BANNER,
        **RESEARCHER_FLAGS,
        "work_identity": wi,
        "slope_meta": slope_meta,
    }
    key = f"{entity_kind}:{entity_id}"
    st.tick_results[key] = receipt
    st.last_receipt = receipt
    st.last_work_identity = wi
    st.history.append(receipt)
    lim = int(st.config.history_limit)
    if len(st.history) > lim:
        st.history = st.history[-lim:]
    st.counters["receipts"] = int(st.counters.get("receipts", 0)) + 1
    if static_hold:
        st.counters["static_holds"] = int(st.counters.get("static_holds", 0)) + 1
    if wi.get("within_tolerance"):
        st.counters["work_identity_ok"] = int(st.counters.get("work_identity_ok", 0)) + 1
    else:
        st.counters["work_identity_residual_exceeded"] = (
            int(st.counters.get("work_identity_residual_exceeded", 0)) + 1
        )
    if abs(float(endpoint_pe_applied or 0.0)) > EPS_ZERO and measurement_only:
        st.counters["policy_c_duplicate_mutation"] = (
            int(st.counters.get("policy_c_duplicate_mutation", 0)) + 1
        )
    if abs(float(endpoint_pe_dissipated or 0.0)) > EPS_ZERO and measurement_only:
        st.counters["policy_c_duplicate_mutation"] = (
            int(st.counters.get("policy_c_duplicate_mutation", 0)) + 1
        )
    return receipt
