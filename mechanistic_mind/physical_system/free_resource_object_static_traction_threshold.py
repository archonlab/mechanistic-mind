"""Acanthostega PHASE C · FOGF STATIC TRACTION TWIN V1.

Arch stage: FOGF_STATIC_TRACTION_TWIN
Preset:     ACANTHOSTEGA_PHASE_C_FREE_OBJECT_STATIC_TRACTION
Parent:     ACANTHOSTEGA_PHASE_C_STATIC_TRACTION
Mechanism:  free_resource_object_static_traction_threshold
Profile:    FREE_RESOURCE_OBJECT_STATIC_TRACTION_THRESHOLD_V1
Receipt:    FREE_RESOURCE_OBJECT_STATIC_TRACTION

Hard bounds:
  N = object.mass · g (NO n_z)
  NORMAL_PHYSICAL_EFFECTS_ACTIVE = false
  ONE_PE_AUTHORITY = SES_DDA
  NO tangent gravity / slope sliding / SES decomp / radius support / rolling /
    object motor / multi-contact solver / body G2A changes
  Legacy FOK damp stays bypassed under FOGF; double_ground_friction = false

Physics (impulse space):
  J_static_max = μ_s · N · dt
  |J_hold| ≤ J_max → STATIC_HOLD (v→0, FREE_STATIC, pose unchanged, work=0)
  |J_hold| > J_max → STATIC_BREAKAWAY → FOGF kinetic once (same tick)
  RELEASE first integrate → RELEASE_TRANSITION_NOT_ELIGIBLE (inherited v kept)
  Collision grace → NOT_ELIGIBLE (impulse+acoustics causal)
  Airborne / unsupported → NO_SUPPORT

μ_s via shared body helper STATIC_RATIO·μ_k(affinity); coefficients not diverged.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from mechanistic_mind.physical_system.body_static_traction_threshold import (
    STATIC_RATIO_DEFAULT,
    j_static_max,
    mu_static_from_surface_affinity,
)
from mechanistic_mind.physical_system.body_static_traction_threshold import (
    body_static_traction_threshold_is_active,
)
from mechanistic_mind.physical_system.flat_ground_gravity import (
    GRAVITY_ACCELERATION,
    flat_ground_gravity_is_active,
)
from mechanistic_mind.physical_system.free_resource_object_ground_friction import (
    MU_MAX,
    MU_MIN,
    NEUTRAL_AFFINITY,
    coulomb_kinetic_step,
    free_resource_object_ground_friction_is_active,
    mu_k_from_surface_affinity,
    sample_support_surface_affinity,
)
from mechanistic_mind.physical_system.free_resource_object_kinematics import (
    free_resource_object_kinematics_is_active,
)
from mechanistic_mind.physical_system.surface_elevation_support import (
    surface_elevation_support_is_active,
)

MECHANISM_ID = "free_resource_object_static_traction_threshold"
ARCH_STAGE = "FOGF_STATIC_TRACTION_TWIN"
PROFILE_VERSION = "FREE_RESOURCE_OBJECT_STATIC_TRACTION_THRESHOLD_V1"
STATE_SCHEMA = "FREE_RESOURCE_OBJECT_STATIC_TRACTION_THRESHOLD_STATE_V1"
RECEIPT_KIND = "FREE_RESOURCE_OBJECT_STATIC_TRACTION"
EVENT_STEP = "FREE_RESOURCE_OBJECT_STATIC_TRACTION_STEP"

BANNER = (
    "FREE RESOURCE OBJECT STATIC TRACTION TWIN V1 · FOGF · μ_s·N · "
    "STATIC_HOLD/BREAKAWAY · LEGACY FOK DAMP BYPASS · NO n_z / NO g_t"
)
OVERLAY_CAPTION = BANNER
ANALYZER_SECTION = "FREE RESOURCE OBJECT STATIC TRACTION"

DT = 1.0
HISTORY_LIMIT_DEFAULT = 64
REST_THRESHOLD_DEFAULT = 0.006
NUMERICAL_ZERO_EPS = 1e-15
OBJECT_IMPULSE_GRACE_ATTR = "_fost_impulse_grace_ticks"

STATE_STATIC_HOLD = "STATIC_HOLD"
STATE_STATIC_BREAKAWAY = "STATIC_BREAKAWAY"
STATE_KINETIC_SLIDE = "KINETIC_SLIDE"
STATE_NO_SUPPORT = "NO_SUPPORT"
STATE_NOT_ELIGIBLE = "NOT_ELIGIBLE"
STATE_RELEASE_TRANSITION_NOT_ELIGIBLE = "RELEASE_TRANSITION_NOT_ELIGIBLE"
STATE_OFF = "OFF"
STATE_SKIPPED = "SKIPPED"

PHYSICAL_STATE_FREE_MOVING = "FREE_MOVING"
PHYSICAL_STATE_FREE_STATIC = "FREE_STATIC"
PHYSICAL_STATE_HELD = "HELD"
PHYSICAL_STATE_COMBINE_REMOVED = "COMBINE_REMOVED"

NORMAL_PHYSICAL_EFFECTS_ACTIVE = False
ONE_PE_AUTHORITY = "SES_DDA"
N_LAW = "N_EQUALS_OBJECT_MASS_G_NO_NZ"
TANGENT_GRAVITY = "NO"
SLOPE_SLIDING = "NO"
RADIUS_AWARE_SUPPORT = "NO"
SES_DECOMPOSITION = "NO"
ROLLING = "NO"
OBJECT_MOTOR = "NO"
MULTI_CONTACT_SOLVER = "NO"
G2A_BODY_STATIC_TRACTION_CHANGED = "NO"
LEGACY_OBJECT_DAMPING_BYPASSED = True
DOUBLE_GROUND_FRICTION = False
BREAKAWAY_POLICY = "SAME_TICK_FOGF_KINETIC_ONCE"

RESEARCHER_FLAGS = {
    "researcher_only": True,
    "agent_accessible": False,
    "semantic_label": False,
}


@dataclass
class FreeResourceObjectStaticTractionThresholdConfig:
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
            "N_LAW": N_LAW,
            "NORMAL_PHYSICAL_EFFECTS_ACTIVE": NORMAL_PHYSICAL_EFFECTS_ACTIVE,
            "ONE_PE_AUTHORITY": ONE_PE_AUTHORITY,
            "TANGENT_GRAVITY": TANGENT_GRAVITY,
            "SLOPE_SLIDING": SLOPE_SLIDING,
            "RADIUS_AWARE_SUPPORT": RADIUS_AWARE_SUPPORT,
            "SES_DECOMPOSITION": SES_DECOMPOSITION,
            "ROLLING": ROLLING,
            "OBJECT_MOTOR": OBJECT_MOTOR,
            "MULTI_CONTACT_SOLVER": MULTI_CONTACT_SOLVER,
            "G2A_BODY_STATIC_TRACTION_CHANGED": G2A_BODY_STATIC_TRACTION_CHANGED,
            "legacy_object_damping_bypassed": LEGACY_OBJECT_DAMPING_BYPASSED,
            "double_ground_friction": DOUBLE_GROUND_FRICTION,
            "breakaway_policy": BREAKAWAY_POLICY,
            "reservoir_credit": False,
            "sound": False,
            "ses_debit_from_twin": False,
            "mu_s_mapping": "STATIC_RATIO_TIMES_MU_K_AFFINITY_V1_SHARED",
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "FreeResourceObjectStaticTractionThresholdConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        ver = data.get("profile_version")
        if ver is not None and str(ver) != PROFILE_VERSION:
            raise ValueError(f"unknown free object static traction profile: {ver}")
        return cls(
            enabled=bool(data.get("enabled", False)),
            static_ratio=float(data.get("static_ratio", STATIC_RATIO_DEFAULT)),
            rest_threshold=float(data.get("rest_threshold", REST_THRESHOLD_DEFAULT)),
            history_limit=int(data.get("history_limit", HISTORY_LIMIT_DEFAULT)),
            mu_min=float(data.get("mu_min", MU_MIN)),
            mu_max=float(data.get("mu_max", MU_MAX)),
        )


def validate_config(cfg: FreeResourceObjectStaticTractionThresholdConfig) -> None:
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


def free_resource_object_static_traction_threshold_is_active(config: Any) -> bool:
    if not _line_ok(config):
        return False
    cfg = getattr(config, "free_resource_object_static_traction_threshold", None)
    if cfg is None or not bool(getattr(cfg, "enabled", False)):
        return False
    # Parent chain: body G2A + FOGF + FOK + SES + FGG
    return bool(
        body_static_traction_threshold_is_active(config)
        and free_resource_object_ground_friction_is_active(config)
        and free_resource_object_kinematics_is_active(config)
        and surface_elevation_support_is_active(config)
        and flat_ground_gravity_is_active(config)
    )


def set_free_resource_object_static_traction_threshold(config: Any, enabled: bool) -> None:
    if config is None:
        return
    on = bool(enabled) and _line_ok(config)
    cur = getattr(config, "free_resource_object_static_traction_threshold", None)
    if cur is None:
        if on:
            config.free_resource_object_static_traction_threshold = (
                FreeResourceObjectStaticTractionThresholdConfig(enabled=True)
            )
        return
    if isinstance(cur, dict):
        cfg = FreeResourceObjectStaticTractionThresholdConfig.from_dict(cur)
        cfg.enabled = on
        config.free_resource_object_static_traction_threshold = cfg
    else:
        cur.enabled = on


@dataclass
class FreeResourceObjectStaticTractionThresholdState:
    config: FreeResourceObjectStaticTractionThresholdConfig
    last_step: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    # object_id -> last tick applied (one application per object/tick; not Python id())
    applied_this_tick: dict[str, int] = field(default_factory=dict)
    counters: dict[str, int] = field(default_factory=lambda: {
        "static_hold_steps": 0,
        "static_breakaway_steps": 0,
        "kinetic_slide_steps": 0,
        "no_support_steps": 0,
        "not_eligible_steps": 0,
        "release_transition_not_eligible_steps": 0,
        "skipped_steps": 0,
        "legacy_object_damping_bypassed": 0,
        "double_ground_friction_guard": 0,
    })


def state_of(world: Any) -> FreeResourceObjectStaticTractionThresholdState | None:
    raw = getattr(world, "free_resource_object_static_traction_threshold_state", None)
    return raw if isinstance(raw, FreeResourceObjectStaticTractionThresholdState) else None


def ensure_free_resource_object_static_traction_threshold_for_runtime(
    world: Any, config: Any
) -> FreeResourceObjectStaticTractionThresholdState | None:
    if not free_resource_object_static_traction_threshold_is_active(config):
        if state_of(world) is not None:
            world.free_resource_object_static_traction_threshold_state = None
        return None
    st = state_of(world)
    if st is not None:
        return st
    raw = getattr(config, "free_resource_object_static_traction_threshold", None)
    cfg = (
        FreeResourceObjectStaticTractionThresholdConfig.from_dict(
            raw.to_dict() if hasattr(raw, "to_dict") else raw
        )
        if raw is not None
        else FreeResourceObjectStaticTractionThresholdConfig(enabled=True)
    )
    cfg.enabled = True
    validate_config(cfg)
    st = FreeResourceObjectStaticTractionThresholdState(config=cfg)
    world.free_resource_object_static_traction_threshold_state = st
    return st


def _is_grounded(obj: Any) -> bool:
    try:
        z = float(getattr(obj, "z", 0.0) or 0.0)
        vz = float(getattr(obj, "vz", 0.0) or 0.0)
    except (TypeError, ValueError):
        z, vz = 0.0, 0.0
    if not (math.isfinite(z) and math.isfinite(vz)):
        z, vz = 0.0, 0.0
    flagged = bool(getattr(obj, "grounded", False))
    return bool(flagged and abs(z) <= 1e-12 and abs(vz) <= 1e-12)



def _traction_ok(obj: Any, config: Any | None = None) -> bool:
    """G2B: grounded ∧ class != LOSS when radius-aware class is present on entity.

    Missing class attribute ⇒ G2B OFF or not yet classified ⇒ eligible if grounded.
    """
    if not _is_grounded(obj):
        return False
    cls = getattr(obj, "_radius_support_class", None)
    if cls is None:
        return True
    return str(cls) not in ("LOSS_OF_SUPPORT", "AIRBORNE_NO_SUPPORT")


def _read_g(world: Any) -> float:
    st = getattr(world, "flat_ground_gravity_state", None)
    if st is not None and getattr(st, "config", None) is not None:
        return float(getattr(st.config, "g", GRAVITY_ACCELERATION))
    return float(GRAVITY_ACCELERATION)


def _dims(world: Any) -> tuple[int, int]:
    t = getattr(world, "T", None)
    return (int(t.shape[1]), int(t.shape[0])) if t is not None else (32, 32)


def set_object_impulse_grace(obj: Any, ticks: int = 1) -> None:
    """Mark object ineligible for static hold after collision impulse (causal keep)."""
    try:
        setattr(obj, OBJECT_IMPULSE_GRACE_ATTR, int(ticks))
    except Exception:
        pass


def consume_object_impulse_grace(obj: Any) -> bool:
    grace = int(getattr(obj, OBJECT_IMPULSE_GRACE_ATTR, 0) or 0)
    if grace <= 0:
        return False
    try:
        setattr(obj, OBJECT_IMPULSE_GRACE_ATTR, grace - 1)
    except Exception:
        pass
    return True


def object_eligibility(
    obj: Any,
    *,
    tick: int,
    episode: dict[str, Any] | None,
    mechanism_active: bool,
) -> tuple[bool, str]:
    """Explicit static-recapture / hold eligibility. No speed<eps as sole law."""
    if not mechanism_active:
        return False, "MECHANISM_OFF"
    ps = str(getattr(obj, "physical_state", "") or "")
    if ps == PHYSICAL_STATE_HELD:
        return False, "HELD"
    if ps == PHYSICAL_STATE_COMBINE_REMOVED or "COMBINE" in ps:
        return False, "COMBINE_REMOVED"
    if ps not in (PHYSICAL_STATE_FREE_STATIC, PHYSICAL_STATE_FREE_MOVING):
        return False, "NOT_FREE"
    if getattr(obj, "holder_body_id", None):
        return False, "HELD_ATTACHMENT"
    # deposits / columns are not ResourceObject free kinematics targets
    kind = str(getattr(obj, "kind", "") or getattr(obj, "object_kind", "") or "")
    if kind.upper() in ("DEPOSIT", "SURFACE_DEPOSIT", "COLUMN", "SURFACE_COLUMN"):
        return False, "DEPOSIT_OR_COLUMN"
    try:
        mass = float(getattr(obj, "mass", 0.0) or 0.0)
    except (TypeError, ValueError):
        mass = 0.0
    if not (math.isfinite(mass) and mass > 0.0):
        return False, "INVALID_MASS"
    if not _is_grounded(obj):
        return False, "NO_SUPPORT"
    # RELEASE: first integration tick = release_tick + 1
    if isinstance(episode, dict):
        rel_t = episode.get("release_tick")
        if rel_t is not None and int(tick) == int(rel_t) + 1:
            return False, "RELEASE_TRANSITION_NOT_ELIGIBLE"
    grace = int(getattr(obj, OBJECT_IMPULSE_GRACE_ATTR, 0) or 0)
    if grace > 0:
        return False, "EXTERNAL_IMPULSE_GRACE"
    return True, "REST_ELIGIBLE"


def build_pre_integration_demand_ledger(
    *,
    object_id: str,
    vx0: float,
    vy0: float,
    mass: float,
    dt: float,
    grounded: bool,
    physical_state: str,
    eligible: bool,
    eligibility_reason: str,
    mu_static: float | None,
    normal_load_N: float | None,
    release_transition: bool,
    collision_grace: bool,
) -> dict[str, Any]:
    """Minimal explicit demand ledger BEFORE irreversible velocity commit.

    Continuous passive demand = residual momentum impulse (no env site forces on FREE).
    """
    j_x = float(mass) * float(vx0)
    j_y = float(mass) * float(vy0)
    j_mag = float(math.hypot(j_x, j_y))
    j_max = (
        j_static_max(mu_static=float(mu_static), normal_load_N=float(normal_load_N), dt=dt)
        if mu_static is not None and normal_load_N is not None
        else None
    )
    taxonomy = {
        "A_continuous_passive_residual_momentum": {
            "j_demand": [j_x, j_y],
            "j_demand_mag": j_mag,
            "note": "FREE objects have no continuous env/Φ/ambient force; demand is m·v",
        },
        "B_active_object_motor": {
            "present": False,
            "note": "OBJECT_MOTOR=NO",
        },
        "C_collision_contact": {
            "external_impulse_grace": bool(collision_grace),
        },
        "D_transition": {
            "release_transition": bool(release_transition),
            "eligibility_reason": str(eligibility_reason),
        },
        "E_numerical_residue": {
            "note": "separated at resolution via physical_static_hold vs numerical_zero_normalization",
        },
    }
    return {
        "object_id": str(object_id),
        "vx0": float(vx0),
        "vy0": float(vy0),
        "mass": float(mass),
        "dt": float(dt),
        "grounded": bool(grounded),
        "physical_state": str(physical_state),
        "eligible": bool(eligible),
        "eligibility_reason": str(eligibility_reason),
        "j_demand": [j_x, j_y],
        "j_demand_mag": j_mag,
        "j_static_max": j_max,
        "mu_static": float(mu_static) if mu_static is not None else None,
        "normal_load_N": float(normal_load_N) if normal_load_N is not None else None,
        "taxonomy": taxonomy,
        "ledger_before_mutation": True,
        "continuous_env_force_on_free_object": False,
    }


def apply_static_then_fogf_kinetic(
    vx: float,
    vy: float,
    *,
    mass: float,
    mu_k: float,
    mu_static: float,
    g: float,
    dt: float,
    rest_threshold: float,
    grounded: bool,
    eligible: bool,
    eligibility_reason: str,
    demand_ledger: dict[str, Any],
) -> dict[str, Any]:
    """Resolve STATIC_HOLD / BREAKAWAY / KINETIC / NO_SUPPORT / NOT_ELIGIBLE.

    Breakaway uses existing FOGF kinetic once (no double static+kinetic cancel).
    """
    N = float(mass) * float(g)
    j_max = j_static_max(mu_static=float(mu_static), normal_load_N=N, dt=dt)
    speed = float(math.hypot(vx, vy))
    j_hold_mag = float(mass) * speed

    base = {
        "legacy_object_damping_bypassed": True,
        "double_ground_friction": False,
        "mu_k": float(mu_k),
        "mu_static": float(mu_static),
        "static_ratio": float(mu_static) / float(mu_k) if mu_k > 0 else None,
        "normal_load_N": float(N),
        "mass": float(mass),
        "g": float(g),
        "dt": float(dt),
        "j_static_max": float(j_max),
        "j_hold_mag": float(j_hold_mag),
        "speed_before": speed,
        "demand_ledger": demand_ledger,
        "eligibility_reason": eligibility_reason,
        "N_LAW": N_LAW,
        "NORMAL_PHYSICAL_EFFECTS_ACTIVE": NORMAL_PHYSICAL_EFFECTS_ACTIVE,
        "ONE_PE_AUTHORITY": ONE_PE_AUTHORITY,
        "breakaway_policy": BREAKAWAY_POLICY,
        "reservoir_credit": False,
        "work": 0.0,
        "ses_debit_from_twin": False,
        "sound": False,
        **RESEARCHER_FLAGS,
    }

    if not grounded:
        return {
            **base,
            "vx": float(vx),
            "vy": float(vy),
            "applied": False,
            "state_class": STATE_NO_SUPPORT,
            "mode": STATE_NO_SUPPORT,
            "physical_static_hold": False,
            "numerical_zero_normalization": False,
            "kinetic_applied": False,
            "speed_after": speed,
            "kinetic_dissipated": 0.0,
            "rest_transition": False,
            "end_state": PHYSICAL_STATE_FREE_MOVING,
        }

    if not eligible:
        # Consequence kept: FOGF kinetic once; do not static-erase.
        step = coulomb_kinetic_step(
            float(vx), float(vy), mu_k=float(mu_k), g=g, dt=dt, rest_threshold=rest_threshold,
        )
        k0 = 0.5 * mass * float(step["speed_before"]) ** 2
        k1 = 0.5 * mass * float(step["speed_after"]) ** 2
        cls = (
            STATE_RELEASE_TRANSITION_NOT_ELIGIBLE
            if eligibility_reason == "RELEASE_TRANSITION_NOT_ELIGIBLE"
            else STATE_NOT_ELIGIBLE
        )
        end_state = (
            PHYSICAL_STATE_FREE_STATIC if step["rest_transition"] else PHYSICAL_STATE_FREE_MOVING
        )
        return {
            **base,
            "vx": float(step["vx"]),
            "vy": float(step["vy"]),
            "applied": True,
            "state_class": cls,
            "mode": cls,
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
            "end_state": end_state,
        }

    # Eligible static cone
    if j_hold_mag <= j_max + 1e-15:
        physical = speed > NUMERICAL_ZERO_EPS
        return {
            **base,
            "vx": 0.0,
            "vy": 0.0,
            "applied": True,
            "state_class": STATE_STATIC_HOLD,
            "mode": STATE_STATIC_HOLD,
            "physical_static_hold": bool(physical),
            "numerical_zero_normalization": (not physical),
            "kinetic_applied": False,
            "speed_after": 0.0,
            "kinetic_before": 0.5 * mass * speed ** 2,
            "kinetic_after": 0.0,
            "kinetic_dissipated": 0.0,
            "static_work": 0.0,
            "rest_transition": True,
            "j_static": [-mass * float(vx), -mass * float(vy)],
            "end_state": PHYSICAL_STATE_FREE_STATIC,
            "pose_unchanged": True,
        }

    # STATIC_BREAKAWAY → FOGF kinetic once (same tick)
    step = coulomb_kinetic_step(
        float(vx), float(vy), mu_k=float(mu_k), g=g, dt=dt, rest_threshold=rest_threshold,
    )
    k0 = 0.5 * mass * float(step["speed_before"]) ** 2
    k1 = 0.5 * mass * float(step["speed_after"]) ** 2
    end_state = (
        PHYSICAL_STATE_FREE_STATIC if step["rest_transition"] else PHYSICAL_STATE_FREE_MOVING
    )
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
        "end_state": end_state,
        "pose_unchanged": False,
    }


def plan_free_object_static_traction_step(
    world: Any,
    obj: Any,
    vx: float,
    vy: float,
    fok_cfg: Any,
    *,
    tick: int,
    episode: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """FOK hook when FOST ON: static cone then FOGF kinetic. Return None → caller uses FOGF-only.

    One application per object_id per tick (explicit key, not Python id()).
    """
    st = state_of(world)
    if st is None:
        return None
    oid = str(getattr(obj, "object_id", "") or "")
    if not oid:
        return None
    if int(st.applied_this_tick.get(oid, -1)) == int(tick):
        st.counters["skipped_steps"] = int(st.counters.get("skipped_steps", 0)) + 1
        return {
            "mode": STATE_SKIPPED,
            "state_class": STATE_SKIPPED,
            "vx": float(vx),
            "vy": float(vy),
            "rest_transition": False,
            "skipped_duplicate_same_tick": True,
            "legacy_fok_damping": False,
            "legacy_object_damping_bypassed": True,
            "double_ground_friction": False,
            "friction_active": True,
            **RESEARCHER_FLAGS,
        }
    st.applied_this_tick[oid] = int(tick)
    # prune old keys
    if len(st.applied_this_tick) > 256:
        st.applied_this_tick = {k: v for k, v in st.applied_this_tick.items() if int(v) >= int(tick) - 2}

    st.counters["legacy_object_damping_bypassed"] = int(
        st.counters.get("legacy_object_damping_bypassed", 0)
    ) + 1
    st.counters["double_ground_friction_guard"] = int(
        st.counters.get("double_ground_friction_guard", 0)
    ) + 1

    rest_thr = float(getattr(fok_cfg, "rest_threshold", st.config.rest_threshold))
    grounded = _is_grounded(obj)
    if grounded and not _traction_ok(obj):
        grounded = False  # LOSS/airborne class: not traction-eligible this tick
    # Consume grace for eligibility check (like body)
    collision_grace = consume_object_impulse_grace(obj)
    eligible, reason = object_eligibility(
        obj, tick=int(tick), episode=episode, mechanism_active=True,
    )
    # If we just consumed grace, reason should reflect it
    if collision_grace and eligible:
        eligible, reason = False, "EXTERNAL_IMPULSE_GRACE"
    elif collision_grace and reason == "EXTERNAL_IMPULSE_GRACE":
        pass
    elif (not collision_grace) and reason == "EXTERNAL_IMPULSE_GRACE":
        # grace was present at eligibility read before consume — already handled
        pass
    # Re-evaluate after consume: if grace was the only blocker and we consumed it for THIS tick
    # eligibility already saw grace>0 before consume via object_eligibility. Good.

    release_transition = reason == "RELEASE_TRANSITION_NOT_ELIGIBLE"
    w, h = _dims(world)
    g = _read_g(world)
    mass = float(getattr(obj, "mass", 1.0) or 1.0)
    if not (math.isfinite(mass) and mass > 0.0):
        mass = 1.0
    sample = sample_support_surface_affinity(world, float(obj.x), float(obj.y), width=w, height=h)
    mu_pair = mu_static_from_surface_affinity(
        float(sample["surface_affinity"]),
        mu_min=float(st.config.mu_min),
        mu_max=float(st.config.mu_max),
        static_ratio=float(st.config.static_ratio),
    )
    mu_k = float(mu_pair["mu_k"])
    mu_s = float(mu_pair["mu_static"])
    N = float(mass) * float(g)  # PHYSICAL flat N — shadow must not replace
    try:
        from mechanistic_mind.physical_system.diagnostic_normal_load_shadow import (
            maybe_record_free_object_shadow,
        )
        maybe_record_free_object_shadow(
            world,
            None,  # world-state gate; config already ensured on runtime
            obj=obj,
            object_id=str(oid),
            mass=float(mass),
            g=float(g),
            grounded=bool(grounded),
            seam="FOST_PLAN",
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
            object_id=str(oid),
            mass=float(mass),
            g=float(g),
            grounded=bool(grounded),
            seam="FOST_PLAN",
        )
    except Exception:
        pass

    demand = build_pre_integration_demand_ledger(
        object_id=oid,
        vx0=float(vx),
        vy0=float(vy),
        mass=mass,
        dt=DT,
        grounded=grounded,
        physical_state=str(getattr(obj, "physical_state", "")),
        eligible=eligible,
        eligibility_reason=reason,
        mu_static=mu_s,
        normal_load_N=N,
        release_transition=release_transition,
        collision_grace=bool(collision_grace or reason == "EXTERNAL_IMPULSE_GRACE"),
    )

    result = apply_static_then_fogf_kinetic(
        float(vx), float(vy),
        mass=mass,
        mu_k=mu_k,
        mu_static=mu_s,
        g=g,
        dt=DT,
        rest_threshold=rest_thr,
        grounded=grounded,
        eligible=eligible,
        eligibility_reason=reason,
        demand_ledger=demand,
    )
    return {
        "friction_active": True,
        "legacy_fok_damping": False,
        "static_traction_twin": True,
        "arch_stage": ARCH_STAGE,
        "mechanism": MECHANISM_ID,
        "g": float(g),
        "dt": float(DT),
        "grounded": bool(grounded),
        "support_profile": "FLAT_GROUND_V1",
        "integrator": "STATIC_THEN_FOGF_KINETIC_V1",
        "friction_law": "STATIC_CONE_THEN_COULOMB_KINETIC_V1",
        "damping_law": "STATIC_THEN_FOGF_KINETIC_V1",
        "damping_factor": None,
        "reservoir_credit": False,
        "sound": False,
        "AIR_DRAG": "NO",
        "mode": result.get("mode"),
        "state_class": result.get("state_class"),
        "vx": float(result["vx"]),
        "vy": float(result["vy"]),
        "rest_transition": bool(result.get("rest_transition")),
        "stopped_by_friction": bool(result.get("rest_transition")),
        "mu_k": float(mu_k),
        "mu_static": float(mu_s),
        "a": result.get("a"),
        "dv": result.get("dv"),
        "normal_load_N": float(N),
        "mass": float(mass),
        "mass_independent_a": True,
        "speed_before": float(result.get("speed_before") or 0.0),
        "speed_after": float(result.get("speed_after") or 0.0),
        "kinetic_before": result.get("kinetic_before"),
        "kinetic_after": result.get("kinetic_after"),
        "kinetic_dissipated": float(result.get("kinetic_dissipated") or 0.0),
        "affinity_coupling": "SURFACE_AFFINITY_TO_MU_K_LINEAR_V1",
        "static_result": result,
        "end_state_hint": result.get("end_state"),
        "pose_unchanged": bool(result.get("pose_unchanged")),
        "physical_static_hold": bool(result.get("physical_static_hold")),
        "numerical_zero_normalization": bool(result.get("numerical_zero_normalization")),
        "kinetic_applied": bool(result.get("kinetic_applied")),
        "j_static_max": result.get("j_static_max"),
        "j_hold_mag": result.get("j_hold_mag"),
        "j_static": result.get("j_static"),
        "static_work": result.get("static_work", 0.0),
        "demand_ledger": demand,
        "eligibility_reason": reason,
        "legacy_object_damping_bypassed": True,
        "double_ground_friction": False,
        **sample,
        **RESEARCHER_FLAGS,
    }


def record_static_traction_receipt(
    world: Any,
    *,
    tick: int,
    object_id: str,
    plan: dict[str, Any],
    start_position: list[float],
    end_position: list[float],
    end_state: str,
    velocity_before: list[float],
    velocity_after: list[float],
) -> dict[str, Any]:
    st = state_of(world)
    result = plan.get("static_result") if isinstance(plan.get("static_result"), dict) else plan
    cls = str(result.get("state_class") or plan.get("state_class") or STATE_OFF)
    if st is not None:
        key = {
            STATE_STATIC_HOLD: "static_hold_steps",
            STATE_STATIC_BREAKAWAY: "static_breakaway_steps",
            STATE_KINETIC_SLIDE: "kinetic_slide_steps",
            STATE_NO_SUPPORT: "no_support_steps",
            STATE_NOT_ELIGIBLE: "not_eligible_steps",
            STATE_RELEASE_TRANSITION_NOT_ELIGIBLE: "release_transition_not_eligible_steps",
            STATE_SKIPPED: "skipped_steps",
        }.get(cls)
        if key:
            st.counters[key] = int(st.counters.get(key, 0)) + 1

    rec = {
        "receipt_kind": RECEIPT_KIND,
        "event": EVENT_STEP,
        "tick": int(tick),
        "object_id": str(object_id),
        "mechanism": MECHANISM_ID,
        "arch_stage": ARCH_STAGE,
        "profile_version": PROFILE_VERSION,
        "banner": BANNER,
        "state_class": cls,
        "mode": plan.get("mode") or result.get("mode"),
        "start_position": list(start_position),
        "end_position": list(end_position),
        "velocity_before": list(velocity_before),
        "velocity_after": list(velocity_after),
        "end_state": str(end_state),
        "legacy_object_damping_bypassed": True,
        "double_ground_friction": False,
        "mu_k": plan.get("mu_k"),
        "mu_static": plan.get("mu_static"),
        "normal_load_N": plan.get("normal_load_N"),
        "mass": plan.get("mass"),
        "g": plan.get("g"),
        "dt": plan.get("dt"),
        "j_static_max": result.get("j_static_max"),
        "j_hold_mag": result.get("j_hold_mag"),
        "j_static": result.get("j_static"),
        "speed_before": plan.get("speed_before"),
        "speed_after": plan.get("speed_after"),
        "kinetic_before": plan.get("kinetic_before"),
        "kinetic_after": plan.get("kinetic_after"),
        "kinetic_dissipated": plan.get("kinetic_dissipated", 0.0),
        "static_work": result.get("static_work", 0.0),
        "work": 0.0,
        "physical_static_hold": bool(result.get("physical_static_hold")),
        "numerical_zero_normalization": bool(result.get("numerical_zero_normalization")),
        "kinetic_applied": bool(result.get("kinetic_applied")),
        "rest_transition": bool(plan.get("rest_transition")),
        "eligibility_reason": plan.get("eligibility_reason") or result.get("eligibility_reason"),
        "demand_ledger": plan.get("demand_ledger") or result.get("demand_ledger"),
        "surface_affinity": plan.get("surface_affinity"),
        "cell_x": plan.get("cell_x"),
        "cell_y": plan.get("cell_y"),
        "deposit_id": plan.get("deposit_id"),
        "N_LAW": N_LAW,
        "NORMAL_PHYSICAL_EFFECTS_ACTIVE": NORMAL_PHYSICAL_EFFECTS_ACTIVE,
        "ONE_PE_AUTHORITY": ONE_PE_AUTHORITY,
        "TANGENT_GRAVITY": TANGENT_GRAVITY,
        "breakaway_policy": BREAKAWAY_POLICY,
        "ses_debit_from_twin": False,
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
        world.last_free_resource_object_static_traction_step = rec
    return rec


def serialize_state(st: FreeResourceObjectStaticTractionThresholdState | None) -> dict[str, Any] | None:
    if st is None:
        return None
    return {
        "schema": STATE_SCHEMA,
        "config": st.config.to_dict(),
        "counters": dict(st.counters),
        "last_step": dict(st.last_step) if st.last_step else None,
        "history": list(st.history),
        "applied_this_tick": {str(k): int(v) for k, v in dict(st.applied_this_tick).items()},
        "banner": BANNER,
        "researcher_only": True,
    }


def restore_state(
    world: Any, data: dict[str, Any] | None, config: Any
) -> FreeResourceObjectStaticTractionThresholdState | None:
    if not free_resource_object_static_traction_threshold_is_active(config):
        world.free_resource_object_static_traction_threshold_state = None
        return None
    if not isinstance(data, dict) or not data:
        return ensure_free_resource_object_static_traction_threshold_for_runtime(world, config)
    if str(data.get("schema")) != STATE_SCHEMA and data.get("schema_version") != STATE_SCHEMA:
        if data.get("schema") is not None or data.get("schema_version") is not None:
            raise ValueError(
                f"unknown free object static traction state schema: "
                f"{data.get('schema') or data.get('schema_version')}"
            )
        return ensure_free_resource_object_static_traction_threshold_for_runtime(world, config)
    raw_cfg = data.get("config")
    if raw_cfg is None:
        cur = getattr(config, "free_resource_object_static_traction_threshold", None)
        raw_cfg = cur.to_dict() if cur is not None and hasattr(cur, "to_dict") else None
    cfg = FreeResourceObjectStaticTractionThresholdConfig.from_dict(raw_cfg)
    validate_config(cfg)
    st = FreeResourceObjectStaticTractionThresholdState(
        config=cfg,
        last_step=dict(data["last_step"]) if isinstance(data.get("last_step"), dict) else {},
        history=list(data.get("history") or []),
        applied_this_tick={
            str(k): int(v) for k, v in dict(data.get("applied_this_tick") or {}).items()
        },
        counters={**{
            "static_hold_steps": 0,
            "static_breakaway_steps": 0,
            "kinetic_slide_steps": 0,
            "no_support_steps": 0,
            "not_eligible_steps": 0,
            "release_transition_not_eligible_steps": 0,
            "skipped_steps": 0,
            "legacy_object_damping_bypassed": 0,
            "double_ground_friction_guard": 0,
        }, **{k: int(v) for k, v in dict(data.get("counters") or {}).items()}},
    )
    world.free_resource_object_static_traction_threshold_state = st
    return st


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "label": "Free Resource Object Static Traction Twin V1 (FOGF)",
        "config_path": "free_resource_object_static_traction_threshold.enabled",
        "enabled": bool(enabled),
        "promotion_class": "EXPERIMENTAL",
        "provenance": "acanthostega_free_resource_object_static_traction_threshold",
        "default_integrated": True,
        "banner": BANNER,
        "analyzer_section": ANALYZER_SECTION,
        "arch_stage": ARCH_STAGE,
        "N_LAW": N_LAW,
        "NORMAL_PHYSICAL_EFFECTS_ACTIVE": NORMAL_PHYSICAL_EFFECTS_ACTIVE,
        "ONE_PE_AUTHORITY": ONE_PE_AUTHORITY,
        "G2A_BODY_STATIC_TRACTION_CHANGED": G2A_BODY_STATIC_TRACTION_CHANGED,
        "legacy_object_damping_bypassed": LEGACY_OBJECT_DAMPING_BYPASSED,
        "double_ground_friction": DOUBLE_GROUND_FRICTION,
        "breakaway_policy": BREAKAWAY_POLICY,
        "scope": {
            "free_static": True,
            "free_moving": True,
            "held": False,
            "bodies": "unchanged_G2A",
            "slopes": False,
            "n_z": False,
            "g_tangent": False,
            "sound": False,
        },
        "historical_compatibility": "missing key means FOST OFF",
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
        "legacy_object_damping_bypassed": LEGACY_OBJECT_DAMPING_BYPASSED,
        "double_ground_friction": DOUBLE_GROUND_FRICTION,
        "breakaway_policy": BREAKAWAY_POLICY,
        "G2A_BODY_STATIC_TRACTION_CHANGED": G2A_BODY_STATIC_TRACTION_CHANGED,
        "agent_accessible": False,
        "researcher_only": True,
    }


def overlay_payload(world: Any) -> dict[str, Any] | None:
    summary = researcher_summary(world)
    if summary is None:
        return None
    return {"caption": BANNER, "active": summary}
