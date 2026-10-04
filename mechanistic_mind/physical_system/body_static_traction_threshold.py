"""Acanthostega PHASE C · G2A STATIC TRACTION THRESHOLD V1.

Implements architecture stage G2A_STATIC_TRACTION_THRESHOLD
(alias body_static_traction — arch TBD name).

Preset:   ACANTHOSTEGA_PHASE_C_STATIC_TRACTION
Parent:   ACANTHOSTEGA_PHASE_C_CONTINUOUS_SURFACE_GEOMETRY
Mechanism: body_static_traction_threshold
Profile:  BODY_STATIC_TRACTION_THRESHOLD_V1
Receipt:  BODY_STATIC_TRACTION

Hard bounds:
  N = m_eff · g (NO n_z)
  NORMAL_PHYSICAL_EFFECTS_ACTIVE = false
  ONE_PE_AUTHORITY = SES DDA
  NO tangent gravity / slope sliding / radius support / slope PE / SES split / gait
  Gentle grounded_damping + v_stop remain BYPASSED (BNLT path)

Physics (impulse space):
  J_static_max = μ_static · N · dt
  |J_hold| ≤ J_max  → STATIC_HOLD (v→0, work=0)
  |J_hold| > J_max  → STATIC_BREAKAWAY → existing BNLT kinetic once (no double response)
  MOVE: begin-tick requested→limited→realized (|J|≤J_max); not canceled as passive
  External impulse grace → NOT_ELIGIBLE (consequence kept)
  Airborne → NO_SUPPORT

μ_s = STATIC_RATIO · μ_k(affinity) with STATIC_RATIO≥1 ⇒ μ_s ≥ μ_k always.
FOGF static twin = DEFERRED (body-only V1).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from mechanistic_mind.physical_system.body_normal_load_traction import (
    body_normal_load_traction_is_active,
)
from mechanistic_mind.physical_system.continuous_surface_geometry import (
    continuous_surface_geometry_is_active,
)
from mechanistic_mind.physical_system.flat_ground_gravity import (
    GRAVITY_ACCELERATION,
    flat_ground_gravity_is_active,
)
from mechanistic_mind.physical_system.free_resource_object_ground_friction import (
    MU_MAX,
    MU_MIN,
    NEUTRAL_AFFINITY,
    coulomb_kinetic_step as _coulomb_kinetic_step,
    mu_k_from_surface_affinity,
)
from mechanistic_mind.physical_system.surface_elevation_support import (
    surface_elevation_support_is_active,
)

# Avoid circular import of coulomb via BNLT — use FOGF directly.
coulomb_kinetic_step = _coulomb_kinetic_step

MECHANISM_ID = "body_static_traction_threshold"
ARCH_STAGE = "G2A_STATIC_TRACTION_THRESHOLD"
ARCH_ALIAS = "body_static_traction"
PROFILE_VERSION = "BODY_STATIC_TRACTION_THRESHOLD_V1"
STATE_SCHEMA = "BODY_STATIC_TRACTION_THRESHOLD_STATE_V1"
RECEIPT_KIND = "BODY_STATIC_TRACTION"
EVENT_STEP = "BODY_STATIC_TRACTION_STEP"

BANNER = (
    "BODY STATIC TRACTION THRESHOLD V1 · G2A · μ_s·N · "
    "STATIC_HOLD/BREAKAWAY · GENTLE DAMP BYPASS · NO n_z / NO g_t"
)
OVERLAY_CAPTION = BANNER
ANALYZER_SECTION = "BODY STATIC TRACTION"

# μ_s = STATIC_RATIO * μ_k(affinity); ratio≥1 guarantees μ_s ≥ μ_k for all affinity.
STATIC_RATIO_DEFAULT = 1.25
DT = 1.0
HISTORY_LIMIT_DEFAULT = 64
REST_THRESHOLD_DEFAULT = 0.006
NUMERICAL_ZERO_EPS = 1e-15

STATE_STATIC_HOLD = "STATIC_HOLD"
STATE_STATIC_BREAKAWAY = "STATIC_BREAKAWAY"
STATE_KINETIC_SLIDE = "KINETIC_SLIDE"
STATE_NO_SUPPORT = "NO_SUPPORT"
STATE_NOT_ELIGIBLE = "NOT_ELIGIBLE"
STATE_OFF = "OFF"

NORMAL_PHYSICAL_EFFECTS_ACTIVE = False
ONE_PE_AUTHORITY = "SES_DDA"
N_LAW = "N_EQUALS_M_EFF_G_NO_NZ"
TANGENT_GRAVITY = "NO"
SLOPE_SLIDING = "NO"
RADIUS_AWARE_SUPPORT = "NO"
SES_DECOMPOSITION = "NO"
GAIT = "NO"
FOGF_STATIC_TWIN = "DEFERRED"
ACTIVE_MOVE_TRACTION_LIMIT = "IN_SCOPE_BEGIN_TICK"
GENTLE_VELOCITY_DAMP_WHEN_ACTIVE = "BYPASSED"
GENTLE_ENV_ABSORB_WHEN_ACTIVE = "KEPT"

RESEARCHER_FLAGS = {
    "researcher_only": True,
    "agent_accessible": False,
    "semantic_label": False,
}


@dataclass
class BodyStaticTractionThresholdConfig:
    """Fresh default OFF; missing snapshot field = OFF."""

    enabled: bool = False
    static_ratio: float = STATIC_RATIO_DEFAULT
    rest_threshold: float = REST_THRESHOLD_DEFAULT
    history_limit: int = HISTORY_LIMIT_DEFAULT
    mu_min: float = MU_MIN
    mu_max: float = MU_MAX

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "static_ratio": float(self.static_ratio),
            "rest_threshold": float(self.rest_threshold),
            "history_limit": int(self.history_limit),
            "mu_min": float(self.mu_min),
            "mu_max": float(self.mu_max),
            "dt": float(DT),
            "profile_version": PROFILE_VERSION,
            "arch_stage": ARCH_STAGE,
            "arch_alias": ARCH_ALIAS,
            "N_LAW": N_LAW,
            "NORMAL_PHYSICAL_EFFECTS_ACTIVE": NORMAL_PHYSICAL_EFFECTS_ACTIVE,
            "ONE_PE_AUTHORITY": ONE_PE_AUTHORITY,
            "TANGENT_GRAVITY": TANGENT_GRAVITY,
            "SLOPE_SLIDING": SLOPE_SLIDING,
            "RADIUS_AWARE_SUPPORT": RADIUS_AWARE_SUPPORT,
            "SES_DECOMPOSITION": SES_DECOMPOSITION,
            "GAIT": GAIT,
            "FOGF_STATIC_TWIN": FOGF_STATIC_TWIN,
            "ACTIVE_MOVE_TRACTION_LIMIT": ACTIVE_MOVE_TRACTION_LIMIT,
            "gentle_velocity_damp_when_active": GENTLE_VELOCITY_DAMP_WHEN_ACTIVE,
            "gentle_env_absorb_when_active": GENTLE_ENV_ABSORB_WHEN_ACTIVE,
            "reservoir_credit": False,
            "sound": False,
            "mu_s_mapping": "STATIC_RATIO_TIMES_MU_K_AFFINITY_V1",
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "BodyStaticTractionThresholdConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        ver = data.get("profile_version")
        if ver is not None and str(ver) != PROFILE_VERSION:
            raise ValueError(f"unknown body static traction profile: {ver}")
        return cls(
            enabled=bool(data.get("enabled", False)),
            static_ratio=float(data.get("static_ratio", STATIC_RATIO_DEFAULT)),
            rest_threshold=float(data.get("rest_threshold", REST_THRESHOLD_DEFAULT)),
            history_limit=int(data.get("history_limit", HISTORY_LIMIT_DEFAULT)),
            mu_min=float(data.get("mu_min", MU_MIN)),
            mu_max=float(data.get("mu_max", MU_MAX)),
        )


def validate_config(cfg: BodyStaticTractionThresholdConfig) -> None:
    if not (math.isfinite(cfg.static_ratio) and float(cfg.static_ratio) >= 1.0):
        raise ValueError("static_ratio must be finite and >= 1 (μ_s ≥ μ_k)")
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


def body_static_traction_threshold_is_active(config: Any) -> bool:
    if not _line_ok(config):
        return False
    cfg = getattr(config, "body_static_traction_threshold", None)
    if cfg is None or not bool(getattr(cfg, "enabled", False)):
        return False
    # Parent chain: CSG + BNLT + SES + FGG
    return bool(
        continuous_surface_geometry_is_active(config)
        and body_normal_load_traction_is_active(config)
        and surface_elevation_support_is_active(config)
        and flat_ground_gravity_is_active(config)
    )


def set_body_static_traction_threshold(config: Any, enabled: bool) -> None:
    if config is None:
        return
    on = bool(enabled) and _line_ok(config)
    cur = getattr(config, "body_static_traction_threshold", None)
    if cur is None:
        if on:
            config.body_static_traction_threshold = BodyStaticTractionThresholdConfig(enabled=True)
        return
    if isinstance(cur, dict):
        cfg = BodyStaticTractionThresholdConfig.from_dict(cur)
        cfg.enabled = on
        config.body_static_traction_threshold = cfg
    else:
        cur.enabled = on


def mu_static_from_surface_affinity(
    surface_affinity: float,
    *,
    mu_min: float = MU_MIN,
    mu_max: float = MU_MAX,
    static_ratio: float = STATIC_RATIO_DEFAULT,
) -> dict[str, float]:
    """Shared pure helper: μ_k(aff) then μ_s = ratio·μ_k with ratio≥1 ⇒ μ_s≥μ_k.

    No semantic surface classes. Mapping documented as STATIC_RATIO_TIMES_MU_K_AFFINITY_V1.
    """
    ratio = float(static_ratio)
    if not math.isfinite(ratio) or ratio < 1.0:
        ratio = STATIC_RATIO_DEFAULT
    mu_k = float(mu_k_from_surface_affinity(surface_affinity, mu_min=mu_min, mu_max=mu_max))
    mu_s = float(ratio) * float(mu_k)
    return {
        "mu_k": mu_k,
        "mu_static": mu_s,
        "static_ratio": float(ratio),
        "surface_affinity": float(
            NEUTRAL_AFFINITY if not math.isfinite(float(surface_affinity))
            else max(0.0, min(1.0, float(surface_affinity)))
        ),
    }


def j_static_max(*, mu_static: float, normal_load_N: float, dt: float = DT) -> float:
    return float(mu_static) * float(normal_load_N) * float(dt)


@dataclass
class BodyStaticTractionThresholdState:
    config: BodyStaticTractionThresholdConfig
    last_step: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=lambda: {
        "static_hold_steps": 0,
        "static_breakaway_steps": 0,
        "kinetic_slide_steps": 0,
        "no_support_steps": 0,
        "not_eligible_steps": 0,
        "move_limited_steps": 0,
        "gentle_velocity_damp_bypassed": 0,
    })


def state_of(world: Any) -> BodyStaticTractionThresholdState | None:
    raw = getattr(world, "body_static_traction_threshold_state", None)
    return raw if isinstance(raw, BodyStaticTractionThresholdState) else None


def ensure_body_static_traction_threshold_for_runtime(
    world: Any, config: Any
) -> BodyStaticTractionThresholdState | None:
    if not body_static_traction_threshold_is_active(config):
        if state_of(world) is not None:
            world.body_static_traction_threshold_state = None
        return None
    st = state_of(world)
    if st is not None:
        return st
    raw = getattr(config, "body_static_traction_threshold", None)
    cfg = (
        BodyStaticTractionThresholdConfig.from_dict(
            raw.to_dict() if hasattr(raw, "to_dict") else raw
        )
        if raw is not None
        else BodyStaticTractionThresholdConfig(enabled=True)
    )
    cfg.enabled = True
    validate_config(cfg)
    st = BodyStaticTractionThresholdState(config=cfg)
    world.body_static_traction_threshold_state = st
    return st


def rest_eligibility_predicate(
    *,
    grounded: bool,
    locomotor_active: bool,
    external_impulse_ineligible: bool,
    mechanism_active: bool,
) -> tuple[bool, str]:
    """Derived eligibility — no hysteresis. Returns (eligible, reason)."""
    if not mechanism_active:
        return False, "MECHANISM_OFF"
    if not grounded:
        return False, "NO_SUPPORT"
    if external_impulse_ineligible:
        return False, "EXTERNAL_IMPULSE_GRACE"
    if locomotor_active:
        return False, "LOCOMOTOR_ACTIVE"
    return True, "REST_ELIGIBLE"


def build_pre_integration_demand_ledger(
    *,
    vx0: float,
    vy0: float,
    f_pass_x: float,
    f_pass_y: float,
    m_eff: float,
    dt: float,
    locomotor_active: bool,
    grounded: bool,
    external_impulse_ineligible: bool,
    mu_static: float | None,
    normal_load_N: float | None,
    move_impulse_xy: tuple[float, float] | None = None,
) -> dict[str, Any]:
    """Minimal explicit demand ledger BEFORE irreversible velocity commit."""
    j_px = float(f_pass_x) * float(dt)
    j_py = float(f_pass_y) * float(dt)
    j_passive_mag = float(math.hypot(j_px, j_py))
    j_max = (
        j_static_max(mu_static=float(mu_static), normal_load_N=float(normal_load_N), dt=dt)
        if mu_static is not None and normal_load_N is not None
        else None
    )
    move_jx = float(move_impulse_xy[0]) if move_impulse_xy else 0.0
    move_jy = float(move_impulse_xy[1]) if move_impulse_xy else 0.0
    taxonomy = {
        "A_passive_supported_demand": {
            "j_passive": [j_px, j_py],
            "j_passive_mag": j_passive_mag,
            "residual_speed": float(math.hypot(vx0, vy0)),
        },
        "B_active_locomotor_demand": {
            "locomotor_active": bool(locomotor_active),
            "move_impulse": [move_jx, move_jy],
            "move_impulse_mag": float(math.hypot(move_jx, move_jy)),
        },
        "C_collision_contact": {
            "external_impulse_ineligible": bool(external_impulse_ineligible),
        },
        "D_numerical_residue": {
            "note": "separated at resolution via physical_static_hold vs numerical_zero_normalization",
        },
    }
    return {
        "vx0": float(vx0),
        "vy0": float(vy0),
        "m_eff": float(m_eff),
        "dt": float(dt),
        "grounded": bool(grounded),
        "locomotor_active": bool(locomotor_active),
        "external_impulse_ineligible": bool(external_impulse_ineligible),
        "j_passive": [j_px, j_py],
        "j_passive_mag": j_passive_mag,
        "j_static_max": j_max,
        "mu_static": float(mu_static) if mu_static is not None else None,
        "normal_load_N": float(normal_load_N) if normal_load_N is not None else None,
        "taxonomy": taxonomy,
        "ledger_before_mutation": True,
    }


def limit_move_impulse_by_static_traction(
    dv_x: float,
    dv_y: float,
    *,
    m_eff: float,
    mu_static: float,
    normal_load_N: float,
    dt: float = DT,
    grounded: bool,
) -> dict[str, Any]:
    """Begin-tick active MOVE clamp: requested → limited (|J|≤μ_s N dt). Airborne: no ground MOVE scale here (caller gates)."""
    req = [float(dv_x), float(dv_y)]
    if not grounded:
        return {
            "dv_requested": req,
            "dv_limited": req,
            "limited": False,
            "reason": "AIRBORNE_NO_GROUND_MOVE_LIMIT",
            "j_requested_mag": float(m_eff) * float(math.hypot(dv_x, dv_y)),
            "j_static_max": None,
            "scale": 1.0,
        }
    j_max = j_static_max(mu_static=mu_static, normal_load_N=normal_load_N, dt=dt)
    speed = float(math.hypot(dv_x, dv_y))
    j_req = float(m_eff) * speed
    if j_max <= 0.0 or j_req <= j_max + 1e-15 or speed <= 0.0:
        return {
            "dv_requested": req,
            "dv_limited": req,
            "limited": False,
            "reason": "WITHIN_CAPACITY" if grounded else "NO_LIMIT",
            "j_requested_mag": j_req,
            "j_static_max": float(j_max),
            "scale": 1.0,
        }
    scale = float(j_max) / float(j_req)
    lim = [float(dv_x) * scale, float(dv_y) * scale]
    return {
        "dv_requested": req,
        "dv_limited": lim,
        "limited": True,
        "reason": "STATIC_TRACTION_CAPACITY",
        "j_requested_mag": j_req,
        "j_static_max": float(j_max),
        "j_limited_mag": float(m_eff) * float(math.hypot(lim[0], lim[1])),
        "scale": float(scale),
    }


def apply_static_then_kinetic(
    vx_trial: float,
    vy_trial: float,
    *,
    bnlt_ctx: dict[str, Any],
    static_cfg: BodyStaticTractionThresholdConfig,
    locomotor_active: bool,
    external_impulse_ineligible: bool,
    demand_ledger: dict[str, Any],
) -> dict[str, Any]:
    """Resolve STATIC_HOLD / BREAKAWAY / KINETIC / NO_SUPPORT / NOT_ELIGIBLE.

    Breakaway uses existing BNLT kinetic once (no double static+kinetic cancel).
    """
    grounded = bool(bnlt_ctx.get("grounded"))
    m_eff = float(bnlt_ctx.get("m_eff") or 1.0)
    g = float(bnlt_ctx.get("g") or GRAVITY_ACCELERATION)
    dt = float(bnlt_ctx.get("dt") or DT)
    N = float(bnlt_ctx.get("normal_load_N") or (m_eff * g))
    rest_thr = float(static_cfg.rest_threshold)

    eligible, reason = rest_eligibility_predicate(
        grounded=grounded,
        locomotor_active=locomotor_active,
        external_impulse_ineligible=external_impulse_ineligible,
        mechanism_active=True,
    )

    mu_pair = None
    mu_k = bnlt_ctx.get("mu_k")
    mu_s = None
    if grounded and bnlt_ctx.get("surface_affinity") is not None:
        mu_pair = mu_static_from_surface_affinity(
            float(bnlt_ctx["surface_affinity"]),
            mu_min=float(static_cfg.mu_min),
            mu_max=float(static_cfg.mu_max),
            static_ratio=float(static_cfg.static_ratio),
        )
        mu_k = float(mu_pair["mu_k"])
        mu_s = float(mu_pair["mu_static"])
    elif mu_k is not None:
        mu_s = float(static_cfg.static_ratio) * float(mu_k)

    j_max = j_static_max(mu_static=float(mu_s), normal_load_N=N, dt=dt) if mu_s is not None else 0.0
    speed_trial = float(math.hypot(vx_trial, vy_trial))
    j_hold_mode = "RESIDUAL_VELOCITY"
    try:
        from mechanistic_mind.physical_system.coherent_slope_dynamics import (
            resolve_static_hold_magnitude,
        )

        j_hold_mag, j_hold_mode = resolve_static_hold_magnitude(
            m_eff=m_eff,
            speed_trial=speed_trial,
            bnlt_ctx=bnlt_ctx,
            dt=dt,
        )
    except Exception:
        j_hold_mag = float(m_eff) * speed_trial

    base = {
        "gentle_bypassed": True,
        "mu_k": float(mu_k) if mu_k is not None else None,
        "mu_static": float(mu_s) if mu_s is not None else None,
        "static_ratio": float(static_cfg.static_ratio),
        "normal_load_N": float(N),
        "m_eff": float(m_eff),
        "g": float(g),
        "dt": float(dt),
        "j_static_max": float(j_max),
        "j_hold_mag": float(j_hold_mag),
        "j_hold_mode": str(j_hold_mode),
        "speed_before": speed_trial,
        "demand_ledger": demand_ledger,
        "eligibility_reason": reason,
        "N_LAW": N_LAW,
        "NORMAL_PHYSICAL_EFFECTS_ACTIVE": NORMAL_PHYSICAL_EFFECTS_ACTIVE,
        "reservoir_credit": False,
        "work": 0.0,
        **RESEARCHER_FLAGS,
    }

    if not grounded or not bnlt_ctx.get("apply_coulomb"):
        return {
            **base,
            "vx": float(vx_trial),
            "vy": float(vy_trial),
            "applied": False,
            "state_class": STATE_NO_SUPPORT,
            "mode": STATE_NO_SUPPORT,
            "physical_static_hold": False,
            "numerical_zero_normalization": False,
            "kinetic_applied": False,
            "speed_after": speed_trial,
            "kinetic_dissipated": 0.0,
            "rest_transition": False,
        }

    if external_impulse_ineligible:
        # Consequence kept: no static erase; still allow kinetic slide (BNLT once).
        fric_a = bnlt_ctx.get("slope_friction_accel")
        drive_a = bnlt_ctx.get("slope_drive_accel")
        if drive_a is None and bnlt_ctx.get("slope_g_t_magnitude") is not None:
            drive_a = float(bnlt_ctx.get("slope_g_t_magnitude") or 0.0)
        step = coulomb_kinetic_step(
            float(vx_trial), float(vy_trial),
            mu_k=float(mu_k), g=g, dt=dt, rest_threshold=rest_thr,
            friction_accel=float(fric_a) if fric_a is not None else None,
            drive_accel=float(drive_a) if drive_a is not None else None,
        )
        k0 = 0.5 * m_eff * float(step["speed_before"]) ** 2
        k1 = 0.5 * m_eff * float(step["speed_after"]) ** 2
        return {
            **base,
            "vx": float(step["vx"]),
            "vy": float(step["vy"]),
            "applied": True,
            "state_class": STATE_NOT_ELIGIBLE,
            "mode": STATE_NOT_ELIGIBLE,
            "physical_static_hold": False,
            "numerical_zero_normalization": bool(step["rest_transition"]),
            "kinetic_applied": True,
            "speed_after": float(step["speed_after"]),
            "kinetic_before": float(k0),
            "kinetic_after": float(k1),
            "kinetic_dissipated": max(0.0, k0 - k1),
            "rest_transition": bool(step["rest_transition"]),
            "a": float(step["a"]),
            "dv": float(step["dv"]),
        }

    if locomotor_active:
        # Active MOVE already capacity-limited at begin_tick; kinetic only (no static cancel).
        fric_a = bnlt_ctx.get("slope_friction_accel")
        drive_a = bnlt_ctx.get("slope_drive_accel")
        if drive_a is None and bnlt_ctx.get("slope_g_t_magnitude") is not None:
            drive_a = float(bnlt_ctx.get("slope_g_t_magnitude") or 0.0)
        move_j = (
            bnlt_ctx.get("move_impulse_xy")
            or (demand_ledger.get("B_active_locomotor_demand") or {}).get("move_impulse")
            or (0.0, 0.0)
        )
        # Beta 4 child: traction-protect capacity-limited MOVE Δv; kinetic on slip only.
        # Parent BNLT path (protection OFF) keeps Option C drive_accel residual.
        traction_vs_slide_on = bool(
            bnlt_ctx.get("active_locomotion_traction_vs_sliding_friction_active")
        )
        if traction_vs_slide_on:
            from mechanistic_mind.physical_system.active_locomotion_traction_vs_sliding_friction import (
                apply_traction_protected_kinetic,
            )

            step = apply_traction_protected_kinetic(
                float(vx_trial),
                float(vy_trial),
                move_impulse_xy=move_j,
                m_eff=m_eff,
                mu_k=float(mu_k),
                g=g,
                dt=dt,
                rest_threshold=rest_thr,
                friction_accel=float(fric_a) if fric_a is not None else None,
                slope_drive_accel=float(drive_a) if drive_a is not None else None,
            )
            k0 = 0.5 * m_eff * float(step["speed_before"]) ** 2
            k1 = 0.5 * m_eff * float(step["speed_after"]) ** 2
            return {
                **base,
                "vx": float(step["vx"]),
                "vy": float(step["vy"]),
                "applied": True,
                "state_class": STATE_KINETIC_SLIDE,
                "mode": STATE_KINETIC_SLIDE,
                "physical_static_hold": False,
                "numerical_zero_normalization": bool(
                    step["rest_transition"] and float(step["speed_before"]) < rest_thr
                ),
                "kinetic_applied": True,
                "speed_after": float(step["speed_after"]),
                "kinetic_before": float(k0),
                "kinetic_after": float(k1),
                "kinetic_dissipated": max(0.0, k0 - k1),
                "rest_transition": bool(step["rest_transition"]),
                "a": float(step["a"]),
                "dv": float(step["dv"]),
                "drive_accel": float(drive_a) if drive_a is not None else None,
                "move_breakaway_repair_active": bool(
                    bnlt_ctx.get("move_breakaway_repair_active")
                ),
                "active_locomotion_traction_vs_sliding_friction_active": True,
                "traction_protection_applied": bool(step.get("traction_protection_applied")),
                "full_drive_protected": bool(step.get("full_drive_protected")),
                "protected_mag": step.get("protected_mag"),
                "slip_speed_before": step.get("slip_speed_before"),
                "slip_speed_after": step.get("slip_speed_after"),
                "legacy_trial_speed_drive_proxy": (
                    float(speed_trial) / float(dt) if float(dt) > 0.0 else 0.0
                ),
            }
        # Force-aware rest: an active locomotor impulse is a real drive this tick.
        # Do not let rest_threshold erase post-friction residual when that drive
        # exceeds kinetic friction capacity (same rule as unbalanced slope g_t).
        #
        # Legacy (Phase C / parent): loc_a proxy = |v_trial|/dt — fails after env absorb
        # when speed_trial ≤ μ_k g dt even though |Δv_lim| = μ_s g > μ_k g.
        # Beta 4 repair (gated): loc_a = |J_move|/(m_eff dt) from capacity-limited impulse.
        loc_a = float(speed_trial) / float(dt) if float(dt) > 0.0 else 0.0
        repair_drive = None
        repair_on = bool(bnlt_ctx.get("move_breakaway_repair_active"))
        if repair_on:
            from mechanistic_mind.physical_system.bnlt_move_breakaway_locomotion_repair import (
                active_drive_accel_from_impulse,
            )

            repair_drive = active_drive_accel_from_impulse(
                move_impulse_xy=move_j, m_eff=m_eff, dt=dt
            )
            if repair_drive is not None:
                loc_a = float(repair_drive)
        if drive_a is None:
            drive_a = float(loc_a) if loc_a > 0.0 else None
        else:
            drive_a = max(float(drive_a), float(loc_a))
        step = coulomb_kinetic_step(
            float(vx_trial), float(vy_trial),
            mu_k=float(mu_k), g=g, dt=dt, rest_threshold=rest_thr,
            friction_accel=float(fric_a) if fric_a is not None else None,
            drive_accel=float(drive_a) if drive_a is not None else None,
        )
        k0 = 0.5 * m_eff * float(step["speed_before"]) ** 2
        k1 = 0.5 * m_eff * float(step["speed_after"]) ** 2
        return {
            **base,
            "vx": float(step["vx"]),
            "vy": float(step["vy"]),
            "applied": True,
            "state_class": STATE_KINETIC_SLIDE,
            "mode": STATE_KINETIC_SLIDE,
            "physical_static_hold": False,
            "numerical_zero_normalization": bool(
                step["rest_transition"] and float(step["speed_before"]) < rest_thr
            ),
            "kinetic_applied": True,
            "speed_after": float(step["speed_after"]),
            "kinetic_before": float(k0),
            "kinetic_after": float(k1),
            "kinetic_dissipated": max(0.0, k0 - k1),
            "rest_transition": bool(step["rest_transition"]),
            "a": float(step["a"]),
            "dv": float(step["dv"]),
            "drive_accel": float(drive_a) if drive_a is not None else None,
            "move_breakaway_repair_active": bool(repair_on),
            "move_breakaway_repair_drive_accel": (
                float(repair_drive) if repair_drive is not None else None
            ),
            "active_locomotion_traction_vs_sliding_friction_active": False,
            "legacy_trial_speed_drive_proxy": float(speed_trial) / float(dt) if float(dt) > 0.0 else 0.0,
        }

    # Passive / WAIT path — static cone
    if j_hold_mag <= j_max + 1e-15:
        # Ideal support reaction does no work.
        physical = speed_trial > NUMERICAL_ZERO_EPS
        numerical = not physical
        return {
            **base,
            "vx": 0.0,
            "vy": 0.0,
            "applied": True,
            "state_class": STATE_STATIC_HOLD,
            "mode": STATE_STATIC_HOLD,
            "physical_static_hold": bool(physical),
            "numerical_zero_normalization": bool(numerical),
            "kinetic_applied": False,
            "speed_after": 0.0,
            "kinetic_before": 0.5 * m_eff * speed_trial ** 2,
            "kinetic_after": 0.0,
            "kinetic_dissipated": 0.0,  # held by static reaction, not kinetic dissipator
            "static_work": 0.0,
            "rest_transition": True,
            "j_static": [-m_eff * float(vx_trial), -m_eff * float(vy_trial)],
        }

    # STATIC_BREAKAWAY → kinetic once
    fric_a = bnlt_ctx.get("slope_friction_accel")
    drive_a = bnlt_ctx.get("slope_drive_accel")
    if drive_a is None and bnlt_ctx.get("slope_g_t_magnitude") is not None:
        drive_a = float(bnlt_ctx.get("slope_g_t_magnitude") or 0.0)
    step = coulomb_kinetic_step(
        float(vx_trial), float(vy_trial),
        mu_k=float(mu_k), g=g, dt=dt, rest_threshold=rest_thr,
        friction_accel=float(fric_a) if fric_a is not None else None,
        drive_accel=float(drive_a) if drive_a is not None else None,
    )
    k0 = 0.5 * m_eff * float(step["speed_before"]) ** 2
    k1 = 0.5 * m_eff * float(step["speed_after"]) ** 2
    return {
        **base,
        "vx": float(step["vx"]),
        "vy": float(step["vy"]),
        "applied": True,
        "state_class": STATE_STATIC_BREAKAWAY,
        "mode": STATE_STATIC_BREAKAWAY,
        "physical_static_hold": False,
        "numerical_zero_normalization": False,
        "kinetic_applied": True,
        "speed_after": float(step["speed_after"]),
        "kinetic_before": float(k0),
        "kinetic_after": float(k1),
        "kinetic_dissipated": max(0.0, k0 - k1),
        "rest_transition": bool(step["rest_transition"]),
        "a": float(step["a"]),
        "dv": float(step["dv"]),
    }


def record_static_traction_receipt(
    world: Any,
    *,
    tick: int,
    body_id: str,
    result: dict[str, Any],
    velocity_before: list[float],
    velocity_after: list[float],
    start_position: list[float],
    end_position: list[float],
    gentle_grounded_damping_bypassed: bool,
    gentle_v_stop_bypassed: bool,
) -> dict[str, Any]:
    st = state_of(world)
    cls = str(result.get("state_class") or STATE_OFF)
    if st is not None:
        key = {
            STATE_STATIC_HOLD: "static_hold_steps",
            STATE_STATIC_BREAKAWAY: "static_breakaway_steps",
            STATE_KINETIC_SLIDE: "kinetic_slide_steps",
            STATE_NO_SUPPORT: "no_support_steps",
            STATE_NOT_ELIGIBLE: "not_eligible_steps",
        }.get(cls)
        if key:
            st.counters[key] = int(st.counters.get(key, 0)) + 1
        st.counters["gentle_velocity_damp_bypassed"] = int(
            st.counters.get("gentle_velocity_damp_bypassed", 0)
        ) + 1

    rec = {
        "receipt_kind": RECEIPT_KIND,
        "event": EVENT_STEP,
        "tick": int(tick),
        "body_id": str(body_id),
        "mechanism": MECHANISM_ID,
        "arch_stage": ARCH_STAGE,
        "arch_alias": ARCH_ALIAS,
        "profile_version": PROFILE_VERSION,
        "banner": BANNER,
        "state_class": cls,
        "mode": result.get("mode"),
        "start_position": list(start_position),
        "end_position": list(end_position),
        "velocity_before": list(velocity_before),
        "velocity_after": list(velocity_after),
        "gentle_grounded_damping_bypassed": bool(gentle_grounded_damping_bypassed),
        "gentle_v_stop_bypassed": bool(gentle_v_stop_bypassed),
        "gentle_env_absorb_kept": True,
        "mu_k": result.get("mu_k"),
        "mu_static": result.get("mu_static"),
        "static_ratio": result.get("static_ratio"),
        "normal_load_N": result.get("normal_load_N"),
        "m_eff": result.get("m_eff"),
        "g": result.get("g"),
        "dt": result.get("dt"),
        "j_static_max": result.get("j_static_max"),
        "j_hold_mag": result.get("j_hold_mag"),
        "j_static": result.get("j_static"),
        "speed_before": result.get("speed_before"),
        "speed_after": result.get("speed_after"),
        "kinetic_before": result.get("kinetic_before"),
        "kinetic_after": result.get("kinetic_after"),
        "kinetic_dissipated": result.get("kinetic_dissipated", 0.0),
        "static_work": result.get("static_work", 0.0),
        "work": result.get("work", 0.0),
        "physical_static_hold": bool(result.get("physical_static_hold")),
        "numerical_zero_normalization": bool(result.get("numerical_zero_normalization")),
        "kinetic_applied": bool(result.get("kinetic_applied")),
        "rest_transition": bool(result.get("rest_transition")),
        "eligibility_reason": result.get("eligibility_reason"),
        "demand_ledger": result.get("demand_ledger"),
        "N_LAW": N_LAW,
        "NORMAL_PHYSICAL_EFFECTS_ACTIVE": NORMAL_PHYSICAL_EFFECTS_ACTIVE,
        "ONE_PE_AUTHORITY": ONE_PE_AUTHORITY,
        "TANGENT_GRAVITY": TANGENT_GRAVITY,
        "FOGF_STATIC_TWIN": FOGF_STATIC_TWIN,
        "ACTIVE_MOVE_TRACTION_LIMIT": ACTIVE_MOVE_TRACTION_LIMIT,
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
        world.last_body_static_traction_step = rec
    return rec


def note_move_limited(world: Any) -> None:
    st = state_of(world)
    if st is None:
        return
    st.counters["move_limited_steps"] = int(st.counters.get("move_limited_steps", 0)) + 1


def serialize_state(st: BodyStaticTractionThresholdState | None) -> dict[str, Any] | None:
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


def restore_state(
    world: Any, data: dict[str, Any] | None, config: Any
) -> BodyStaticTractionThresholdState | None:
    if not body_static_traction_threshold_is_active(config):
        world.body_static_traction_threshold_state = None
        return None
    if not isinstance(data, dict) or not data:
        return ensure_body_static_traction_threshold_for_runtime(world, config)
    if str(data.get("schema")) != STATE_SCHEMA and data.get("schema_version") != STATE_SCHEMA:
        if data.get("schema") is not None or data.get("schema_version") is not None:
            raise ValueError(
                f"unknown body static traction state schema: "
                f"{data.get('schema') or data.get('schema_version')}"
            )
        return ensure_body_static_traction_threshold_for_runtime(world, config)
    raw_cfg = data.get("config")
    if raw_cfg is None:
        cur = getattr(config, "body_static_traction_threshold", None)
        raw_cfg = cur.to_dict() if cur is not None and hasattr(cur, "to_dict") else None
    cfg = BodyStaticTractionThresholdConfig.from_dict(raw_cfg)
    validate_config(cfg)
    st = BodyStaticTractionThresholdState(
        config=cfg,
        last_step=dict(data["last_step"]) if isinstance(data.get("last_step"), dict) else {},
        history=list(data.get("history") or []),
        counters={**{
            "static_hold_steps": 0,
            "static_breakaway_steps": 0,
            "kinetic_slide_steps": 0,
            "no_support_steps": 0,
            "not_eligible_steps": 0,
            "move_limited_steps": 0,
            "gentle_velocity_damp_bypassed": 0,
        }, **{k: int(v) for k, v in dict(data.get("counters") or {}).items()}},
    )
    world.body_static_traction_threshold_state = st
    return st


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "label": "Body Static Traction Threshold V1 (G2A)",
        "config_path": "body_static_traction_threshold.enabled",
        "enabled": bool(enabled),
        "promotion_class": "EXPERIMENTAL",
        "provenance": "acanthostega_body_static_traction_threshold",
        "default_integrated": True,
        "banner": BANNER,
        "analyzer_section": ANALYZER_SECTION,
        "arch_stage": ARCH_STAGE,
        "arch_alias": ARCH_ALIAS,
        "N_LAW": N_LAW,
        "NORMAL_PHYSICAL_EFFECTS_ACTIVE": NORMAL_PHYSICAL_EFFECTS_ACTIVE,
        "ONE_PE_AUTHORITY": ONE_PE_AUTHORITY,
        "FOGF_STATIC_TWIN": FOGF_STATIC_TWIN,
        "ACTIVE_MOVE_TRACTION_LIMIT": ACTIVE_MOVE_TRACTION_LIMIT,
        "gentle_velocity_damp_when_active": GENTLE_VELOCITY_DAMP_WHEN_ACTIVE,
        "scope": {
            "bodies": True,
            "static_cone": True,
            "free_objects": "FOGF_TWIN_DEFERRED",
            "slopes": False,
            "n_z": False,
            "g_tangent": False,
        },
        "historical_compatibility": "missing key means static traction OFF",
    }


def researcher_summary(world: Any) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    return {
        "mechanism": MECHANISM_ID,
        "arch_stage": ARCH_STAGE,
        "profile_version": PROFILE_VERSION,
        "banner": BANNER,
        "analyzer_section": ANALYZER_SECTION,
        "counters": dict(st.counters),
        "last_step": st.last_step or None,
        "static_ratio": float(st.config.static_ratio),
        "N_LAW": N_LAW,
        "NORMAL_PHYSICAL_EFFECTS_ACTIVE": NORMAL_PHYSICAL_EFFECTS_ACTIVE,
        "ONE_PE_AUTHORITY": ONE_PE_AUTHORITY,
        "FOGF_STATIC_TWIN": FOGF_STATIC_TWIN,
        "ACTIVE_MOVE_TRACTION_LIMIT": ACTIVE_MOVE_TRACTION_LIMIT,
        "gentle_velocity_damp_when_active": GENTLE_VELOCITY_DAMP_WHEN_ACTIVE,
        "agent_accessible": False,
        "researcher_only": True,
    }


def overlay_payload(world: Any) -> dict[str, Any] | None:
    summary = researcher_summary(world)
    if summary is None:
        return None
    return {"caption": BANNER, "active": summary}
