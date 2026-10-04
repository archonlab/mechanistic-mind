"""Acanthostega PHASE C · TANGENT GRAVITY DIAGNOSTIC SHADOW.

Preset: ACANTHOSTEGA_PHASE_C_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW
Parent: ACANTHOSTEGA_PHASE_C_CONTINUOUS_PE_POLICY_C
Mechanism: tangent_gravity_diagnostic_shadow
Profile: TANGENT_GRAVITY_DIAGNOSTIC_SHADOW_V1

Researcher-only decomposition of world gravity against centre analytic CSG n̂:

    g_vec = (0, 0, −g)                         # FGG vertical convention
    g_n   = (g_vec · n_hat) n_hat
    g_t   = g_vec − g_n

Shares NORMAL_SOURCE = CENTRE_ANALYTIC_CSG_N_HAT with G2D projected-N shadow.
N_projected candidate = m_eff · g · n_z (same formula as G2D).

SHADOW ONLY — never feeds motion, friction, SES, Policy C PE, or cognition.
TANGENT_GRAVITY_ACTIVE = NO
PROJECTED_NORMAL_LOAD_ACTIVE = NO
PASSIVE_SLOPE_SLIDING_ACTIVE = NO
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from mechanistic_mind.physical_system.continuous_gravitational_pe import (
    continuous_gravitational_pe_is_active,
    endpoint_pe_physically_active,
)
from mechanistic_mind.physical_system.continuous_surface_geometry import (
    sample_surface_geometry,
)
from mechanistic_mind.physical_system.diagnostic_normal_load_shadow import (
    NORMAL_SOURCE as G2D_NORMAL_SOURCE,
    compute_projected_normal_load,
    diagnostic_normal_load_shadow_is_active,
)
from mechanistic_mind.physical_system.radius_aware_support_points import (
    CLASS_AIRBORNE,
    CLASS_EDGE,
    CLASS_FULL,
    CLASS_LOSS,
    CLASS_PARTIAL,
    read_entity_support_class,
)

MECHANISM_ID = "tangent_gravity_diagnostic_shadow"
PROFILE_VERSION = "TANGENT_GRAVITY_DIAGNOSTIC_SHADOW_V1"
STAGE_ALIAS = "TANGENT_GRAVITY_DIAGNOSTIC_SHADOW_V1"
STATE_SCHEMA = "TANGENT_GRAVITY_DIAGNOSTIC_SHADOW_STATE_V1"
RECEIPT_KIND = "TANGENT_GRAVITY_SHADOW"

NORMAL_SOURCE = G2D_NORMAL_SOURCE  # CENTRE_ANALYTIC_CSG_N_HAT
MODE = "DIAGNOSTIC_SHADOW"

BANNER = (
    "TANGENT GRAVITY\n"
    "DIAGNOSTIC SHADOW\n"
    "NORMAL SOURCE: CENTRE ANALYTIC CSG\n"
    "g_t: SHADOW ONLY\n"
    "PROJECTED N: SHADOW ONLY\n"
    "STATIC HOLD: DIAGNOSTIC ONLY\n"
    "PASSIVE SLIDING: OFF"
)
OVERLAY_CAPTION = BANNER
ANALYZER_SECTION = "TANGENT GRAVITY SHADOW (DIAGNOSTIC)"

HISTORY_LIMIT_DEFAULT = 64
EPS_FLAT = 1e-12
EPS_ORTH = 1e-9
EPS_ZERO = 1e-12

STATUS_ELIGIBLE = "ELIGIBLE_TANGENT_GRAVITY"
STATUS_FLAT = "FLAT_EQUIVALENT_GT_ZERO"
STATUS_PARTIAL = "PARTIAL_DIAGNOSTIC_NOT_ACTIVATABLE"
STATUS_NOT_ELIGIBLE_EDGE = "NOT_ELIGIBLE_EDGE_OR_SPARSE"
STATUS_NOT_ELIGIBLE_LOSS = "NOT_ELIGIBLE_SUPPORT_LOSS"
STATUS_NOT_ELIGIBLE_AIRBORNE = "NOT_ELIGIBLE_AIRBORNE"
STATUS_NOT_AVAILABLE_GEOMETRY = "NOT_AVAILABLE_GEOMETRY"
STATUS_INVALID_MASS = "INVALID_MASS"
STATUS_HELD_EXCLUDED = "HELD_OBJECT_NO_INDEPENDENT_GROUND_GT"
STATUS_INACTIVE = "INACTIVE"

HOLD_CAPABLE = "HOLD_CAPABLE"
BREAKAWAY_EXPECTED = "BREAKAWAY_EXPECTED"
HOLD_INDETERMINATE = "HOLD_INDETERMINATE"

RESEARCHER_FLAGS = {
    "researcher_only": True,
    "agent_accessible": False,
    "semantic_label": False,
    "influenced_physics": False,
    "mode": MODE,
    "tangent_gravity_active": False,
    "projected_normal_load_active": False,
    "static_slope_hold_active": False,
    "passive_slope_sliding_active": False,
    "normal_source": NORMAL_SOURCE,
}


# ---------------------------------------------------------------------------
# Pure geometry / gravity decomposition (shared mathematical authority)
# ---------------------------------------------------------------------------


def gravity_vector(*, g: float) -> tuple[float, float, float]:
    """World gravity acceleration (FGG): pulls toward −z."""
    return (0.0, 0.0, -float(g))


def decompose_gravity(
    *,
    n_hat: tuple[float, float, float],
    g: float,
) -> dict[str, Any]:
    """g = g_n + g_t with g_n = (g·n) n, g_t = g − g_n.

    n_hat must be the upward centre-analytic CSG unit normal (n_z ≥ 0).
    """
    nx, ny, nz = float(n_hat[0]), float(n_hat[1]), float(n_hat[2])
    gx, gy, gz = gravity_vector(g=g)
    g_dot_n = gx * nx + gy * ny + gz * nz
    gnx, gny, gnz = g_dot_n * nx, g_dot_n * ny, g_dot_n * nz
    gtx, gty, gtz = gx - gnx, gy - gny, gz - gnz
    gt_mag = math.sqrt(gtx * gtx + gty * gty + gtz * gtz)
    gt_xy = math.hypot(gtx, gty)
    # Orthogonality residual (should be ~0).
    orth = gtx * nx + gty * ny + gtz * nz
    # Reconstruct residual |g − (g_n+g_t)| (exact by construction → 0).
    return {
        "gravity_vector": (gx, gy, gz),
        "n_hat": (nx, ny, nz),
        "g_dot_n": float(g_dot_n),
        "candidate_normal_gravity_vector": (float(gnx), float(gny), float(gnz)),
        "candidate_tangent_gravity_vector": (float(gtx), float(gty), float(gtz)),
        "candidate_tangent_gravity_magnitude": float(gt_mag),
        "candidate_tangent_gravity_xy_magnitude": float(gt_xy),
        "tangent_normal_dot": float(orth),
        "flat": bool(abs(gt_mag) <= EPS_FLAT and abs(nz - 1.0) <= EPS_FLAT),
    }


def static_hold_diagnostic(
    *,
    m_eff: float,
    g_t_xy_magnitude: float,
    mu_s: float | None,
    N_projected: float | None,
) -> dict[str, Any]:
    """Compare |F_t_xy| = m |g_t_xy| to μ_s N_projected (diagnostic only)."""
    f_t = float(m_eff) * float(g_t_xy_magnitude)
    if mu_s is None or N_projected is None:
        return {
            "F_tangent_xy": float(f_t),
            "mu_s": None,
            "N_projected": None,
            "static_friction_capacity_candidate": None,
            "static_hold_margin": None,
            "static_hold_classification": HOLD_INDETERMINATE,
        }
    capacity = float(mu_s) * float(N_projected)
    margin = float(capacity) - float(f_t)
    cls = HOLD_CAPABLE if margin >= -EPS_ZERO else BREAKAWAY_EXPECTED
    return {
        "F_tangent_xy": float(f_t),
        "mu_s": float(mu_s),
        "N_projected": float(N_projected),
        "static_friction_capacity_candidate": float(capacity),
        "static_hold_margin": float(margin),
        "static_hold_classification": cls,
    }


def pe_sign_consistency(
    *,
    delta_u: float | None,
    g_t: tuple[float, float, float] | None,
    dx: float,
    dy: float,
) -> str | None:
    """Compare Policy C endpoint ΔU sign to −sign(g_t · Δr_xy).

    Gravity does work downhill (ΔU decreases). g_t · Δr > 0 when moving with g_t
    (downhill) ⇒ expect ΔU < 0. Independent of motor intention.
    """
    if delta_u is None or g_t is None:
        return None
    du = float(delta_u)
    work_proxy = float(g_t[0]) * float(dx) + float(g_t[1]) * float(dy)
    if abs(du) <= EPS_ZERO and abs(work_proxy) <= EPS_ZERO:
        return "BOTH_ZERO"
    if abs(du) <= EPS_ZERO or abs(work_proxy) <= EPS_ZERO:
        return "INCOMPARABLE_ONE_ZERO"
    # Downhill: work_proxy > 0 and du < 0 ⇒ opposite signs ⇒ consistent.
    if du * work_proxy < 0.0:
        return "CONSISTENT"
    return "INCONSISTENT"


# ---------------------------------------------------------------------------
# Config / state
# ---------------------------------------------------------------------------


@dataclass
class TangentGravityDiagnosticShadowConfig:
    enabled: bool = False
    history_limit: int = HISTORY_LIMIT_DEFAULT
    normal_source: str = NORMAL_SOURCE
    # Diagnostic μ_s fallback when surface affinity unavailable (researcher-only).
    diagnostic_mu_s_default: float = 0.6

    def to_dict(self) -> dict[str, Any]:
        on = bool(self.enabled)
        return {
            "enabled": on,
            "history_limit": int(self.history_limit),
            "normal_source": str(self.normal_source),
            "diagnostic_mu_s_default": float(self.diagnostic_mu_s_default),
            "profile_version": PROFILE_VERSION,
            "stage_alias": STAGE_ALIAS,
            "mode": MODE,
            "tangent_gravity_active": False,
            "projected_normal_load_active": False,
            "passive_slope_sliding_active": False,
            "influenced_physics": False,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "TangentGravityDiagnosticShadowConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        ver = data.get("profile_version")
        if ver is not None and str(ver) != PROFILE_VERSION:
            raise ValueError(f"unknown tangent_gravity_diagnostic_shadow profile: {ver}")
        return cls(
            enabled=bool(data.get("enabled", False)),
            history_limit=int(data.get("history_limit", HISTORY_LIMIT_DEFAULT)),
            normal_source=str(data.get("normal_source", NORMAL_SOURCE)),
            diagnostic_mu_s_default=float(data.get("diagnostic_mu_s_default", 0.6)),
        )


def validate_config(cfg: TangentGravityDiagnosticShadowConfig) -> None:
    if not (1 <= int(cfg.history_limit) <= 512):
        raise ValueError("history_limit must be in [1, 512]")
    if str(cfg.normal_source) != NORMAL_SOURCE:
        raise ValueError(f"normal_source must be {NORMAL_SOURCE}")
    if not (math.isfinite(float(cfg.diagnostic_mu_s_default)) and float(cfg.diagnostic_mu_s_default) >= 0.0):
        raise ValueError("diagnostic_mu_s_default must be finite >= 0")


def _line_ok(config: Any) -> bool:
    return (
        config is not None
        and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"
    )


def tangent_gravity_diagnostic_shadow_is_active(config: Any) -> bool:
    if not _line_ok(config):
        return False
    cfg = getattr(config, "tangent_gravity_diagnostic_shadow", None)
    if cfg is None or not bool(getattr(cfg, "enabled", False)):
        return False
    # Requires Policy C parent chain (endpoint PE) + G2D shadow available.
    if not continuous_gravitational_pe_is_active(config):
        return False
    return bool(diagnostic_normal_load_shadow_is_active(config))


def set_tangent_gravity_diagnostic_shadow(config: Any, enabled: bool) -> None:
    if config is None:
        return
    on = bool(enabled) and _line_ok(config)
    cur = getattr(config, "tangent_gravity_diagnostic_shadow", None)
    if cur is None:
        if on:
            config.tangent_gravity_diagnostic_shadow = TangentGravityDiagnosticShadowConfig(
                enabled=True
            )
        return
    if isinstance(cur, dict):
        cur = TangentGravityDiagnosticShadowConfig.from_dict(cur)
        config.tangent_gravity_diagnostic_shadow = cur
    cur.enabled = bool(on)


@dataclass
class TangentGravityDiagnosticShadowState:
    config: TangentGravityDiagnosticShadowConfig = field(
        default_factory=TangentGravityDiagnosticShadowConfig
    )
    counters: dict[str, int] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    last_receipt: dict[str, Any] | None = None
    tick_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    last_tick: int = -1
    restore_suppress_until_tick: int | None = None
    last_error: str | None = None

    def reset_tick(self, tick: int) -> None:
        if int(tick) != int(self.last_tick):
            self.tick_results = {}
            self.last_tick = int(tick)


def state_of(world: Any) -> TangentGravityDiagnosticShadowState | None:
    return getattr(world, "tangent_gravity_diagnostic_shadow_state", None)


def ensure_tangent_gravity_diagnostic_shadow_for_runtime(
    world: Any, config: Any
) -> TangentGravityDiagnosticShadowState | None:
    if not tangent_gravity_diagnostic_shadow_is_active(config):
        return state_of(world)
    st = state_of(world)
    cfg = getattr(config, "tangent_gravity_diagnostic_shadow", None)
    if not isinstance(cfg, TangentGravityDiagnosticShadowConfig):
        cfg = TangentGravityDiagnosticShadowConfig.from_dict(
            cfg if isinstance(cfg, dict) else None
        )
        validate_config(cfg)
        config.tangent_gravity_diagnostic_shadow = cfg
    else:
        validate_config(cfg)
    if st is None:
        st = TangentGravityDiagnosticShadowState(config=cfg)
        world.tangent_gravity_diagnostic_shadow_state = st
    else:
        st.config = cfg
    return st


def serialize_state(st: TangentGravityDiagnosticShadowState | None) -> dict[str, Any] | None:
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
) -> TangentGravityDiagnosticShadowState | None:
    if not isinstance(payload, dict) or not payload:
        if world is not None:
            world.tangent_gravity_diagnostic_shadow_state = None
        return None
    if config is not None and not tangent_gravity_diagnostic_shadow_is_active(config):
        world.tangent_gravity_diagnostic_shadow_state = None
        return None
    cfg = TangentGravityDiagnosticShadowConfig.from_dict(payload.get("config"))
    validate_config(cfg)
    st = TangentGravityDiagnosticShadowState(config=cfg)
    st.counters = {str(k): int(v) for k, v in dict(payload.get("counters") or {}).items()}
    st.last_tick = int(payload.get("last_tick", -1) or -1)
    st.restore_suppress_until_tick = int(getattr(world, "tick", 0) or 0)
    world.tangent_gravity_diagnostic_shadow_state = st
    return st


def status_text(world: Any) -> str:
    st = state_of(world)
    if st is None:
        return BANNER
    last = st.last_receipt or {}
    gt = last.get("candidate_tangent_gravity_magnitude")
    hold = last.get("static_hold_classification")
    return (
        f"{BANNER}\n"
        f"last |g_t|={gt} hold={hold} "
        f"receipts={st.counters.get('receipts', 0)}"
    )


def observer_banner(config: Any | None = None) -> str:
    return BANNER


def researcher_summary(world: Any) -> dict[str, Any]:
    st = state_of(world)
    if st is None:
        return {"active": False}
    return {
        "active": True,
        "mode": MODE,
        "normal_source": NORMAL_SOURCE,
        "tangent_gravity_active": False,
        "projected_normal_load_active": False,
        "counters": dict(st.counters or {}),
        "last": dict(st.last_receipt) if st.last_receipt else None,
        "researcher_only": True,
    }


def overlay_payload(world: Any) -> dict[str, Any]:
    return {"caption": OVERLAY_CAPTION, "summary": researcher_summary(world)}


# ---------------------------------------------------------------------------
# Query seam
# ---------------------------------------------------------------------------


def entity_key(*, entity_kind: str, entity_id: str) -> str:
    return f"{str(entity_kind)}:{str(entity_id)}"


def _resolve_mu_s(world: Any, config: Any, *, default: float) -> float:
    try:
        from mechanistic_mind.physical_system.body_static_traction_threshold import (
            mu_static_from_surface_affinity,
        )
        # Neutral affinity diagnostic default when no local sample is forced.
        pair = mu_static_from_surface_affinity(0.5)
        return float(pair["mu_static"])
    except Exception:
        return float(default)


def query_tangent_gravity_diagnostic_shadow(
    world: Any,
    config: Any | None,
    *,
    entity_kind: str,
    entity_id: str,
    x: float,
    y: float,
    m_eff: float,
    g: float,
    grounded: bool,
    entity: Any | None = None,
    support_class: str | None = None,
    held_mass: float | None = None,
    body_mass: float | None = None,
    tick: int | None = None,
    seam: str = "BNLT_PREPARE",
    displacement_xy: tuple[float, float] | None = None,
    policy_c_delta_u: float | None = None,
) -> dict[str, Any] | None:
    """Diagnostic query. Deduped per entity/tick. Never mutates physics."""
    if config is not None:
        if not tangent_gravity_diagnostic_shadow_is_active(config):
            return None
        st = ensure_tangent_gravity_diagnostic_shadow_for_runtime(world, config)
    else:
        st = state_of(world)
    if st is None:
        return None

    tick_i = int(tick if tick is not None else getattr(world, "tick", 0) or 0)
    if st.restore_suppress_until_tick is not None and tick_i <= int(st.restore_suppress_until_tick):
        st.counters["restore_false_hit_suppressed"] = (
            int(st.counters.get("restore_false_hit_suppressed", 0)) + 1
        )
        return {
            "status": "RESTORE_SUPPRESSED",
            "influenced_physics": False,
            "tick": tick_i,
            **RESEARCHER_FLAGS,
        }

    st.reset_tick(tick_i)
    key = entity_key(entity_kind=entity_kind, entity_id=entity_id)
    # Displacement-aware queries use a distinct key suffix so TRACTION_PREP and
    # fixture PE-consistency samples do not collide within a tick.
    store_key = key if displacement_xy is None else f"{key}:disp"
    if store_key in st.tick_results and displacement_xy is None:
        st.counters["duplicate_suppressed"] = int(st.counters.get("duplicate_suppressed", 0)) + 1
        return st.tick_results[store_key]

    cls = support_class
    if cls is None and entity is not None:
        cls = read_entity_support_class(entity)

    base: dict[str, Any] = {
        "receipt_kind": RECEIPT_KIND,
        "mechanism": MECHANISM_ID,
        "profile_version": PROFILE_VERSION,
        "tick": tick_i,
        "entity_kind": str(entity_kind),
        "entity_id": str(entity_id),
        "entity_key": key,
        "seam": str(seam),
        "x": float(x),
        "y": float(y),
        "grounded": bool(grounded),
        "support_classification": str(cls) if cls is not None else None,
        "held_mass": float(held_mass) if held_mass is not None else None,
        "body_mass": float(body_mass) if body_mass is not None else None,
        "m_eff": float(m_eff) if math.isfinite(float(m_eff)) else None,
        "g": float(g) if math.isfinite(float(g)) else None,
        "policy_c_active": bool(endpoint_pe_physically_active(config)),
        "eligible": False,
        "status": STATUS_INACTIVE,
        **RESEARCHER_FLAGS,
    }

    if str(entity_kind) in ("held_object", "held"):
        base["status"] = STATUS_HELD_EXCLUDED
        st.tick_results[store_key] = base
        _bump(st, base)
        _emit(st, base)
        return base

    if not (math.isfinite(float(m_eff)) and float(m_eff) > 0.0 and math.isfinite(float(g)) and float(g) > 0.0):
        base["status"] = STATUS_INVALID_MASS
        st.tick_results[store_key] = base
        _bump(st, base)
        _emit(st, base)
        return base

    # Reuse G2D eligibility via compute_projected_normal_load (geometry filled next).
    nx = ny = nz = None
    geometry_ok = False
    try:
        sample = sample_surface_geometry(
            world, float(x), float(y), config=config, record=False,
            reason="tangent_gravity_diagnostic_shadow",
        )
        nx = float(sample["normal_x"])
        ny = float(sample["normal_y"])
        nz = float(sample["normal_z"])
        geometry_ok = all(math.isfinite(v) for v in (nx, ny, nz))
    except Exception as exc:
        st.last_error = str(exc)
        geometry_ok = False

    proj = compute_projected_normal_load(
        m_eff=float(m_eff),
        g=float(g),
        n_z=nz if geometry_ok else None,
        grounded=bool(grounded),
        support_class=cls,
        geometry_ok=geometry_ok,
    )
    status = str(proj.get("status") or STATUS_NOT_AVAILABLE_GEOMETRY)
    # Map G2D statuses onto tangent statuses.
    status_map = {
        "PROJECTED": STATUS_ELIGIBLE,
        "FLAT_EQUIVALENT": STATUS_FLAT,
        "PARTIAL_DIAGNOSTIC_NOT_ACTIVATABLE": STATUS_PARTIAL,
        "NOT_ELIGIBLE_EDGE_OR_SPARSE": STATUS_NOT_ELIGIBLE_EDGE,
        "NOT_ELIGIBLE_SUPPORT_LOSS": STATUS_NOT_ELIGIBLE_LOSS,
        "NOT_ELIGIBLE_AIRBORNE": STATUS_NOT_ELIGIBLE_AIRBORNE,
        "NOT_AVAILABLE_GEOMETRY": STATUS_NOT_AVAILABLE_GEOMETRY,
        "INVALID_MASS": STATUS_INVALID_MASS,
    }
    tg_status = status_map.get(status, status)
    base["status"] = tg_status
    base["candidate_projected_normal_load"] = proj.get("N_projected")
    base["N_flat"] = proj.get("N_flat")
    base["n_z"] = proj.get("n_z")

    if tg_status in (
        STATUS_NOT_ELIGIBLE_AIRBORNE,
        STATUS_NOT_ELIGIBLE_LOSS,
        STATUS_NOT_ELIGIBLE_EDGE,
        STATUS_NOT_AVAILABLE_GEOMETRY,
        STATUS_INVALID_MASS,
    ):
        st.tick_results[store_key] = base
        _bump(st, base)
        _emit(st, base)
        return base

    if not geometry_ok or nx is None:
        base["status"] = STATUS_NOT_AVAILABLE_GEOMETRY
        st.tick_results[store_key] = base
        _bump(st, base)
        _emit(st, base)
        return base

    decomp = decompose_gravity(n_hat=(nx, ny, nz), g=float(g))
    mu_s = _resolve_mu_s(world, config, default=float(st.config.diagnostic_mu_s_default))
    hold = static_hold_diagnostic(
        m_eff=float(m_eff),
        g_t_xy_magnitude=float(decomp["candidate_tangent_gravity_xy_magnitude"]),
        mu_s=float(mu_s),
        N_projected=proj.get("N_projected"),
    )

    # Kinetic friction candidate magnitude μ_k N_proj (readiness only).
    try:
        from mechanistic_mind.physical_system.body_static_traction_threshold import (
            mu_static_from_surface_affinity,
        )
        pair = mu_static_from_surface_affinity(0.5)
        mu_k = float(pair["mu_k"])
    except Exception:
        mu_k = float(mu_s) / 1.2 if mu_s else None
    kinetic_cand = None
    if mu_k is not None and proj.get("N_projected") is not None:
        kinetic_cand = float(mu_k) * float(proj["N_projected"])

    pe_cmp = None
    if displacement_xy is not None:
        pe_cmp = pe_sign_consistency(
            delta_u=policy_c_delta_u,
            g_t=decomp["candidate_tangent_gravity_vector"],
            dx=float(displacement_xy[0]),
            dy=float(displacement_xy[1]),
        )

    eligible = tg_status in (STATUS_ELIGIBLE, STATUS_FLAT, STATUS_PARTIAL)
    if decomp["flat"] and tg_status == STATUS_ELIGIBLE:
        tg_status = STATUS_FLAT

    base.update({
        "status": tg_status,
        "eligible": bool(eligible),
        "n_hat": list(decomp["n_hat"]),
        "gravity_vector": list(decomp["gravity_vector"]),
        "candidate_normal_gravity_vector": list(decomp["candidate_normal_gravity_vector"]),
        "candidate_tangent_gravity_vector": list(decomp["candidate_tangent_gravity_vector"]),
        "candidate_tangent_gravity_magnitude": float(decomp["candidate_tangent_gravity_magnitude"]),
        "candidate_tangent_gravity_xy_magnitude": float(
            decomp["candidate_tangent_gravity_xy_magnitude"]
        ),
        "tangent_normal_dot": float(decomp["tangent_normal_dot"]),
        "flat": bool(decomp["flat"]),
        **hold,
        "kinetic_friction_candidate": kinetic_cand,
        "policy_c_delta_u": float(policy_c_delta_u) if policy_c_delta_u is not None else None,
        "displacement_xy": list(displacement_xy) if displacement_xy is not None else None,
        "pe_sign_consistency": pe_cmp,
        "n_x": float(nx),
        "n_y": float(ny),
        "n_z": float(nz),
    })
    st.tick_results[store_key] = base
    _bump(st, base)
    _emit(st, base)
    return base


def _bump(st: TangentGravityDiagnosticShadowState, result: dict[str, Any]) -> None:
    st.counters["queries"] = int(st.counters.get("queries", 0)) + 1
    status = str(result.get("status") or "")
    if result.get("eligible"):
        st.counters["eligible"] = int(st.counters.get("eligible", 0)) + 1
    if result.get("flat"):
        st.counters["flat"] = int(st.counters.get("flat", 0)) + 1
    gt = result.get("candidate_tangent_gravity_magnitude")
    if gt is not None and abs(float(gt)) > EPS_FLAT:
        st.counters["nonzero_gt"] = int(st.counters.get("nonzero_gt", 0)) + 1
    hold = str(result.get("static_hold_classification") or "")
    if hold == HOLD_CAPABLE:
        st.counters["hold_capable"] = int(st.counters.get("hold_capable", 0)) + 1
    elif hold == BREAKAWAY_EXPECTED:
        st.counters["breakaway_expected"] = int(st.counters.get("breakaway_expected", 0)) + 1
    pe = str(result.get("pe_sign_consistency") or "")
    if pe == "CONSISTENT":
        st.counters["pe_sign_consistent"] = int(st.counters.get("pe_sign_consistent", 0)) + 1
    elif pe == "INCONSISTENT":
        st.counters["pe_sign_inconsistent"] = int(st.counters.get("pe_sign_inconsistent", 0)) + 1
    if status == STATUS_NOT_ELIGIBLE_AIRBORNE and result.get("candidate_tangent_gravity_magnitude"):
        st.counters["airborne_leakage"] = int(st.counters.get("airborne_leakage", 0)) + 1
    if result.get("influenced_physics"):
        st.counters["physics_influence_anomalies"] = (
            int(st.counters.get("physics_influence_anomalies", 0)) + 1
        )
    if status == STATUS_HELD_EXCLUDED:
        st.counters["held_excluded"] = int(st.counters.get("held_excluded", 0)) + 1


def _emit(st: TangentGravityDiagnosticShadowState, result: dict[str, Any]) -> None:
    receipt = dict(result)
    st.last_receipt = receipt
    st.history.append(receipt)
    lim = int(st.config.history_limit)
    if len(st.history) > lim:
        st.history = st.history[-lim:]
    st.counters["receipts"] = int(st.counters.get("receipts", 0)) + 1


def maybe_record_body_tangent_shadow(
    world: Any,
    config: Any,
    *,
    body: Any,
    body_id: str,
    m_eff: float,
    g: float,
    grounded: bool,
    held_mass: float | None = None,
    body_mass: float | None = None,
    entity_kind: str = "body",
    seam: str = "BNLT_PREPARE",
) -> dict[str, Any] | None:
    return query_tangent_gravity_diagnostic_shadow(
        world,
        config,
        entity_kind=entity_kind,
        entity_id=str(body_id),
        x=float(getattr(body, "x", 0.0)),
        y=float(getattr(body, "y", 0.0)),
        m_eff=float(m_eff),
        g=float(g),
        grounded=bool(grounded),
        entity=body,
        held_mass=held_mass,
        body_mass=body_mass,
        seam=seam,
    )


def maybe_record_free_object_tangent_shadow(
    world: Any,
    config: Any | None,
    *,
    obj: Any,
    object_id: str,
    mass: float,
    g: float,
    grounded: bool,
    seam: str = "TRACTION_PREP",
) -> dict[str, Any] | None:
    return query_tangent_gravity_diagnostic_shadow(
        world,
        config,
        entity_kind="free_object",
        entity_id=str(object_id),
        x=float(getattr(obj, "x", 0.0)),
        y=float(getattr(obj, "y", 0.0)),
        m_eff=float(mass),
        g=float(g),
        grounded=bool(grounded),
        entity=obj,
        seam=seam,
    )
