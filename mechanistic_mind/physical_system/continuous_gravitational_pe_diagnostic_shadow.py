"""Acanthostega PHASE C · CONTINUOUS GRAVITATIONAL PE DIAGNOSTIC SHADOW.

Preset: ACANTHOSTEGA_PHASE_C_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW
Parent: ACANTHOSTEGA_PHASE_C_DIAGNOSTIC_NORMAL_LOAD_SHADOW
Mechanism: continuous_gravitational_pe_diagnostic_shadow
Profile: CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW_V1

Observes ACTUAL accepted/committed supported displacements and computes the
candidate Policy C endpoint gravitational ΔU:

    ΔU_candidate = m_eff · g · (z_end_authoritative − z_start_authoritative)

where z_* are continuous centre support heights (surface_support_height / CSG).

SHADOW / RESEARCHER-ONLY — never feeds SES, PE authority, friction, cognition,
or motion. CURRENT_PE_AUTHORITY remains PE_AUTHORITY_SES_DDA.
CONTINUOUS_PE_ACTIVE remains False.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from mechanistic_mind.physical_system.diagnostic_normal_load_shadow import (
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
from mechanistic_mind.physical_system.ses_decomposition_contract import (
    PE_AUTHORITY_CONTINUOUS_GRAVITY,
    PE_AUTHORITY_SES_DDA,
    TRANSITION_GEOMETRY_AMBIGUOUS,
    TRANSITION_LEDGE_BLOCK,
    TRANSITION_MICRORELIEF_STEP,
    TRANSITION_OCCUPANT_SUPPORT_RISE,
    TRANSITION_RADIUS_PARTIAL_CONTACT,
    TRANSITION_SMOOTH_PATCH_TRAVERSAL,
    TRANSITION_SUPPORT_DROP_LOS,
    decisive_ses_event,
)

MECHANISM_ID = "continuous_gravitational_pe_diagnostic_shadow"
PROFILE_VERSION = "CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW_V1"
STAGE_ALIAS = "CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW_V1"
STATE_SCHEMA = "CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW_STATE_V1"
RECEIPT_KIND = "CONTINUOUS_GRAVITATIONAL_PE_SHADOW"

ENDPOINT_AUTHORITY = "CONTINUOUS_SUPPORT_HEIGHT_ENDPOINT_DELTA_U"
CURRENT_AUTHORITY = PE_AUTHORITY_SES_DDA
CANDIDATE_AUTHORITY = ENDPOINT_AUTHORITY
MODE = "DIAGNOSTIC_SHADOW"
SEAM = "SES_PATH_GATE_POST_COMMIT"

BANNER = (
    "CONTINUOUS GRAVITATIONAL PE\n"
    "DIAGNOSTIC SHADOW\n"
    "PHYSICAL AUTHORITY: SES_DDA\n"
    "CANDIDATE: ENDPOINT ΔU\n"
    "PHYSICS: UNCHANGED"
)
OVERLAY_CAPTION = BANNER
ANALYZER_SECTION = "CONTINUOUS GRAVITATIONAL PE SHADOW (DIAGNOSTIC)"

HISTORY_LIMIT_DEFAULT = 64
EPS_ZERO = 1e-12
EPS_MATCH = 1e-9

STATUS_ELIGIBLE = "ELIGIBLE_ENDPOINT_PE"
STATUS_PARTIAL_DIAGNOSTIC = "PARTIAL_DIAGNOSTIC_ENDPOINT_PE"
STATUS_BLOCKED_NO_COMMIT = "BLOCKED_NO_COMMIT"
STATUS_SUPPORT_LOSS = "SUPPORT_LOSS_INELIGIBLE"
STATUS_NOT_ELIGIBLE_EDGE = "NOT_ELIGIBLE_EDGE_OR_SPARSE"
STATUS_NOT_ELIGIBLE_AIRBORNE = "NOT_ELIGIBLE_AIRBORNE"
STATUS_NOT_AVAILABLE_HEIGHT = "NOT_AVAILABLE_HEIGHT"
STATUS_INVALID_MASS = "INVALID_MASS"
STATUS_HELD_EXCLUDED = "HELD_OBJECT_NO_INDEPENDENT_GROUND_PE"
STATUS_INACTIVE = "INACTIVE"

CMP_ZERO_BOTH = "ZERO_BOTH"
CMP_MATCH = "MATCH"
CMP_CURRENT_SES_ONLY = "CURRENT_SES_ONLY"
CMP_CANDIDATE_ONLY = "CANDIDATE_ONLY"
CMP_DIFFERENT_MAGNITUDE = "DIFFERENT_MAGNITUDE"
CMP_DIFFERENT_SIGN = "DIFFERENT_SIGN"
CMP_INCOMPARABLE = "INCOMPARABLE"

RESEARCHER_FLAGS = {
    "researcher_only": True,
    "agent_accessible": False,
    "semantic_label": False,
    "influenced_physics": False,
    "candidate_influenced_physics": False,
    "mode": MODE,
    "current_pe_authority": CURRENT_AUTHORITY,
    "candidate_pe_authority": CANDIDATE_AUTHORITY,
    "endpoint_authority": ENDPOINT_AUTHORITY,
    "continuous_pe_active": False,
    "projected_normal_load_active": False,
    "tangent_gravity_active": False,
    "passive_slope_sliding_active": False,
    "current_and_candidate_both_physically_charged": False,
}


@dataclass
class ContinuousGravitationalPeDiagnosticShadowConfig:
    enabled: bool = False
    history_limit: int = HISTORY_LIMIT_DEFAULT
    pe_authority: str = PE_AUTHORITY_SES_DDA
    endpoint_authority: str = ENDPOINT_AUTHORITY

    def to_dict(self) -> dict[str, Any]:
        on = bool(self.enabled)
        return {
            "enabled": on,
            "history_limit": int(self.history_limit),
            "pe_authority": str(self.pe_authority),
            "endpoint_authority": str(self.endpoint_authority),
            "profile_version": PROFILE_VERSION,
            "stage_alias": STAGE_ALIAS,
            "mode": MODE,
            "current_pe_authority": CURRENT_AUTHORITY,
            "candidate_pe_authority": CANDIDATE_AUTHORITY,
            "influenced_physics": False,
            "continuous_pe_active": False,
            "projected_normal_load_active": False,
            "tangent_gravity_active": False,
            "passive_slope_sliding_active": False,
            "candidate_pe_feeds_physics": False,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ContinuousGravitationalPeDiagnosticShadowConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        ver = data.get("profile_version")
        if ver is not None and str(ver) != PROFILE_VERSION:
            raise ValueError(f"unknown continuous_gravitational_pe_diagnostic_shadow profile: {ver}")
        return cls(
            enabled=bool(data.get("enabled", False)),
            history_limit=int(data.get("history_limit", HISTORY_LIMIT_DEFAULT)),
            pe_authority=str(data.get("pe_authority", PE_AUTHORITY_SES_DDA)),
            endpoint_authority=str(data.get("endpoint_authority", ENDPOINT_AUTHORITY)),
        )


def validate_config(cfg: ContinuousGravitationalPeDiagnosticShadowConfig) -> None:
    if not (1 <= int(cfg.history_limit) <= 512):
        raise ValueError("history_limit must be in [1, 512]")
    if str(cfg.endpoint_authority) != ENDPOINT_AUTHORITY:
        raise ValueError(f"endpoint_authority must be {ENDPOINT_AUTHORITY}")
    if str(cfg.pe_authority) != PE_AUTHORITY_SES_DDA:
        raise ValueError("diagnostic shadow must keep pe_authority = PE_AUTHORITY_SES_DDA")


def _line_ok(config: Any) -> bool:
    return (
        config is not None
        and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"
    )


def continuous_gravitational_pe_diagnostic_shadow_is_active(config: Any) -> bool:
    if not _line_ok(config):
        return False
    cfg = getattr(config, "continuous_gravitational_pe_diagnostic_shadow", None)
    if cfg is None or not bool(getattr(cfg, "enabled", False)):
        return False
    return bool(diagnostic_normal_load_shadow_is_active(config))


def continuous_gravitational_pe_diagnostic_shadow_active_on_world(
    world: Any, config: Any | None = None
) -> bool:
    if config is not None:
        return continuous_gravitational_pe_diagnostic_shadow_is_active(config) and state_of(world) is not None
    st = state_of(world)
    return st is not None and bool(st.config.enabled)


def set_continuous_gravitational_pe_diagnostic_shadow(config: Any, enabled: bool) -> None:
    if config is None:
        return
    on = bool(enabled) and _line_ok(config)
    cur = getattr(config, "continuous_gravitational_pe_diagnostic_shadow", None)
    if cur is None:
        if on:
            config.continuous_gravitational_pe_diagnostic_shadow = (
                ContinuousGravitationalPeDiagnosticShadowConfig(enabled=True)
            )
        return
    if isinstance(cur, dict):
        cfg = ContinuousGravitationalPeDiagnosticShadowConfig.from_dict(cur)
        cfg.enabled = on
        config.continuous_gravitational_pe_diagnostic_shadow = cfg
    else:
        cur.enabled = on


@dataclass
class ContinuousGravitationalPeDiagnosticShadowState:
    config: ContinuousGravitationalPeDiagnosticShadowConfig
    last_receipt: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=lambda: _default_counters())
    query_tick: int | None = None
    tick_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    restore_suppress_until_tick: int | None = None
    last_error: str | None = None


def _default_counters() -> dict[str, int]:
    return {
        "queries": 0,
        "unique_entity_queries": 0,
        "duplicate_suppressed": 0,
        "eligible": 0,
        "partial_diagnostic": 0,
        "blocked_no_commit": 0,
        "support_loss": 0,
        "edge_ineligible": 0,
        "airborne_ineligible": 0,
        "height_unavailable": 0,
        "invalid_mass": 0,
        "smooth_count": 0,
        "topological_count": 0,
        "microrelief_count": 0,
        "cmp_zero_both": 0,
        "cmp_match": 0,
        "cmp_current_ses_only": 0,
        "cmp_candidate_only": 0,
        "cmp_different_magnitude": 0,
        "cmp_different_sign": 0,
        "cmp_incomparable": 0,
        "level_nonzero_candidate": 0,
        "body_queries": 0,
        "free_object_queries": 0,
        "experimenter_queries": 0,
        "receipts_emitted": 0,
        "physics_influence_anomalies": 0,
        "restore_false_hit_suppressed": 0,
    }


def state_of(world: Any) -> ContinuousGravitationalPeDiagnosticShadowState | None:
    raw = getattr(world, "continuous_gravitational_pe_diagnostic_shadow_state", None)
    return raw if isinstance(raw, ContinuousGravitationalPeDiagnosticShadowState) else None


def ensure_continuous_gravitational_pe_diagnostic_shadow_for_runtime(
    world: Any, config: Any
) -> ContinuousGravitationalPeDiagnosticShadowState | None:
    if not continuous_gravitational_pe_diagnostic_shadow_is_active(config):
        if state_of(world) is not None:
            world.continuous_gravitational_pe_diagnostic_shadow_state = None
        return None
    st = state_of(world)
    if st is not None:
        return st
    raw = getattr(config, "continuous_gravitational_pe_diagnostic_shadow", None)
    cfg = (
        ContinuousGravitationalPeDiagnosticShadowConfig.from_dict(
            raw.to_dict() if hasattr(raw, "to_dict") else raw
        )
        if raw is not None
        else ContinuousGravitationalPeDiagnosticShadowConfig(enabled=True)
    )
    cfg.enabled = True
    validate_config(cfg)
    st = ContinuousGravitationalPeDiagnosticShadowState(config=cfg)
    world.continuous_gravitational_pe_diagnostic_shadow_state = st
    return st


def compute_endpoint_delta_u(
    *,
    m_eff: float,
    g: float,
    z_start: float,
    z_end: float,
) -> float:
    """Policy C candidate: ΔU = m_eff · g · (z_end − z_start). Higher support ⇒ higher U."""
    return float(m_eff) * float(g) * (float(z_end) - float(z_start))


def ses_signed_gravitational_delta(plan: dict[str, Any] | None) -> float:
    """Signed SES gravitational bookkeeping for comparison.

    Climb (work_debit or kinetic_paid) → positive.
    Micro downhill dissipated_pe → negative PE change.
    """
    if not isinstance(plan, dict):
        return 0.0
    climb = float(plan.get("work_debit") or 0.0) + float(plan.get("kinetic_paid") or 0.0)
    dissipated = 0.0
    for step in plan.get("steps") or []:
        if isinstance(step, dict):
            dissipated += float(step.get("dissipated_pe") or 0.0)
    return float(climb) - float(dissipated)


def compare_ses_vs_candidate(
    *,
    ses_delta: float | None,
    candidate_delta_u: float | None,
) -> str:
    if ses_delta is None or candidate_delta_u is None:
        return CMP_INCOMPARABLE
    s = float(ses_delta)
    c = float(candidate_delta_u)
    s_zero = abs(s) <= EPS_ZERO
    c_zero = abs(c) <= EPS_ZERO
    if s_zero and c_zero:
        return CMP_ZERO_BOTH
    if s_zero and not c_zero:
        return CMP_CANDIDATE_ONLY
    if c_zero and not s_zero:
        return CMP_CURRENT_SES_ONLY
    if s * c < 0.0:
        return CMP_DIFFERENT_SIGN
    if abs(s - c) <= EPS_MATCH:
        return CMP_MATCH
    return CMP_DIFFERENT_MAGNITUDE


def _map_transition_class(
    *,
    event_kind: str,
    accepted: bool,
    support_class: str | None,
    block_reason: str | None,
) -> str:
    """Lightweight researcher taxonomy aligned with G2C1 labels (no physics control)."""
    ek = str(event_kind or "")
    br = str(block_reason or "")
    if br == "RADIUS_FACE_BARRIER" or ek == "RADIUS_FACE_BARRIER":
        return TRANSITION_LEDGE_BLOCK
    if ek in ("LARGE_UPHILL_BLOCKED", "LEDGE_BLOCK"):
        return TRANSITION_LEDGE_BLOCK
    if ek in ("LARGE_DOWNHILL_SUPPORT_LOST", "SUPPORT_DROP_LOS"):
        return TRANSITION_SUPPORT_DROP_LOS
    if ek in ("MICRO_UPHILL", "MICRO_DOWNHILL_INELASTIC", "MICRO_DOWNHILL"):
        return TRANSITION_MICRORELIEF_STEP
    if ek == "OCCUPANT_SUPPORT_RISE" or "OCCUPANT" in ek:
        return TRANSITION_OCCUPANT_SUPPORT_RISE
    if ek in ("GEOMETRY_AMBIGUOUS", "HARD_CAP"):
        return TRANSITION_GEOMETRY_AMBIGUOUS
    if support_class == CLASS_PARTIAL and ek == "LEVEL":
        return TRANSITION_RADIUS_PARTIAL_CONTACT
    if ek == "LEVEL" or (accepted and not ek):
        return TRANSITION_SMOOTH_PATCH_TRAVERSAL
    if not accepted:
        return TRANSITION_LEDGE_BLOCK
    return TRANSITION_GEOMETRY_AMBIGUOUS


def _transition_bucket(transition_class: str | None) -> str:
    cls = str(transition_class or "")
    if cls == TRANSITION_SMOOTH_PATCH_TRAVERSAL:
        return "smooth"
    if cls == TRANSITION_MICRORELIEF_STEP:
        return "microrelief"
    if cls in (
        TRANSITION_LEDGE_BLOCK,
        TRANSITION_SUPPORT_DROP_LOS,
        TRANSITION_OCCUPANT_SUPPORT_RISE,
        TRANSITION_GEOMETRY_AMBIGUOUS,
        TRANSITION_RADIUS_PARTIAL_CONTACT,
    ):
        return "topological"
    return "other"


def entity_key(*, entity_kind: str, entity_id: str) -> str:
    return f"{str(entity_kind)}:{str(entity_id)}"


def observe_path_gate_pe_shadow(
    world: Any,
    config: Any | None,
    *,
    plan: dict[str, Any],
    entity: Any | None,
    entity_kind: str,
    entity_id: str,
    x0: float,
    y0: float,
    z0: float,
    grounded_before: bool,
    m_eff: float,
    g: float,
    held_mass: float | None = None,
    body_mass: float | None = None,
    tick: int | None = None,
) -> dict[str, Any] | None:
    """Post-commit SES path-gate observer. Never mutates physics."""
    if config is not None:
        if not continuous_gravitational_pe_diagnostic_shadow_is_active(config):
            return None
        st = ensure_continuous_gravitational_pe_diagnostic_shadow_for_runtime(world, config)
    else:
        st = state_of(world)
        if st is None or not bool(st.config.enabled):
            return None
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
            "entity_kind": str(entity_kind),
            "entity_id": str(entity_id),
            **RESEARCHER_FLAGS,
        }

    key = entity_key(entity_kind=entity_kind, entity_id=entity_id)
    if st.query_tick != tick_i:
        st.query_tick = tick_i
        st.tick_results = {}
    if key in st.tick_results:
        st.counters["duplicate_suppressed"] = int(st.counters.get("duplicate_suppressed", 0)) + 1
        return st.tick_results[key]

    result = _build_receipt(
        world,
        config,
        st=st,
        plan=plan,
        entity=entity,
        entity_kind=str(entity_kind),
        entity_id=str(entity_id),
        entity_key_s=key,
        x0=float(x0),
        y0=float(y0),
        z0=float(z0),
        grounded_before=bool(grounded_before),
        m_eff=float(m_eff),
        g=float(g),
        held_mass=held_mass,
        body_mass=body_mass,
        tick_i=tick_i,
    )
    st.tick_results[key] = result
    st.counters["queries"] = int(st.counters.get("queries", 0)) + 1
    st.counters["unique_entity_queries"] = int(st.counters.get("unique_entity_queries", 0)) + 1
    _bump_counters(st, result)
    _emit_receipt(st, result)
    return result


def _build_receipt(
    world: Any,
    config: Any | None,
    *,
    st: ContinuousGravitationalPeDiagnosticShadowState,
    plan: dict[str, Any],
    entity: Any | None,
    entity_kind: str,
    entity_id: str,
    entity_key_s: str,
    x0: float,
    y0: float,
    z0: float,
    grounded_before: bool,
    m_eff: float,
    g: float,
    held_mass: float | None,
    body_mass: float | None,
    tick_i: int,
) -> dict[str, Any]:
    accepted = bool(plan.get("accepted", False))
    support_lost = bool(plan.get("support_lost", False))
    block_reason = plan.get("block_reason")
    x_end = float(getattr(entity, "x", plan.get("x", x0)) if entity is not None else plan.get("x", x0))
    y_end = float(getattr(entity, "y", plan.get("y", y0)) if entity is not None else plan.get("y", y0))
    z_pose_end = float(getattr(entity, "z", plan.get("z", z0)) if entity is not None else plan.get("z", z0))
    grounded_after = bool(
        getattr(entity, "grounded", plan.get("grounded", grounded_before))
        if entity is not None
        else plan.get("grounded", grounded_before)
    )
    support_class = read_entity_support_class(entity) if entity is not None else None

    decisive = decisive_ses_event(plan, z_before=float(z0))
    event_kind = str(decisive.get("event_kind") or "")
    transition_class = _map_transition_class(
        event_kind=event_kind,
        accepted=accepted,
        support_class=support_class,
        block_reason=str(block_reason) if block_reason is not None else None,
    )
    ses_delta = ses_signed_gravitational_delta(plan)

    base: dict[str, Any] = {
        "receipt_kind": RECEIPT_KIND,
        "mechanism": MECHANISM_ID,
        "profile_version": PROFILE_VERSION,
        "tick": tick_i,
        "entity_kind": entity_kind,
        "entity_id": entity_id,
        "entity_key": entity_key_s,
        "seam": SEAM,
        "transition_accepted": bool(accepted),
        "physically_committed": bool(accepted),
        "block_reason": str(block_reason) if block_reason is not None else None,
        "support_lost": bool(support_lost),
        "support_class": str(support_class) if support_class is not None else None,
        "event_kind": event_kind,
        "transition_class": transition_class or None,
        "event_kinds": list(plan.get("event_kinds") or []),
        "x_start": float(x0),
        "y_start": float(y0),
        "x_end": float(x_end),
        "y_end": float(y_end),
        "z_pose_start": float(z0),
        "z_pose_end": float(z_pose_end),
        "grounded_before": bool(grounded_before),
        "grounded_after": bool(grounded_after),
        "mass_authority": (
            "m_eff_locomotor_with_held_once"
            if entity_kind in ("body", "experimenter")
            else "object_mass"
        ),
        "m_eff": float(m_eff) if math.isfinite(float(m_eff)) else None,
        "held_mass": float(held_mass) if held_mass is not None else None,
        "body_mass": float(body_mass) if body_mass is not None else None,
        "g": float(g) if math.isfinite(float(g)) else None,
        "current_ses_gravitational_delta": float(ses_delta),
        "current_ses_work_debit": float(plan.get("work_debit") or 0.0),
        "current_ses_kinetic_paid": float(plan.get("kinetic_paid") or 0.0),
        "z_start_authoritative": None,
        "z_end_authoritative": None,
        "delta_z_authoritative": None,
        "candidate_endpoint_delta_u": None,
        "difference": None,
        "comparison_class": CMP_INCOMPARABLE,
        "status": STATUS_INACTIVE,
        **RESEARCHER_FLAGS,
    }

    if not (math.isfinite(float(m_eff)) and float(m_eff) > 0.0 and math.isfinite(float(g)) and float(g) > 0.0):
        base["status"] = STATUS_INVALID_MASS
        return base

    if not accepted:
        base["status"] = STATUS_BLOCKED_NO_COMMIT
        base["physically_committed"] = False
        return base

    if support_lost or (not grounded_after) or support_class in (CLASS_AIRBORNE, CLASS_LOSS):
        base["status"] = (
            STATUS_SUPPORT_LOSS
            if support_lost or support_class == CLASS_LOSS
            else STATUS_NOT_ELIGIBLE_AIRBORNE
        )
        return base

    if not grounded_before and not grounded_after:
        base["status"] = STATUS_NOT_ELIGIBLE_AIRBORNE
        return base

    if support_class == CLASS_EDGE:
        base["status"] = STATUS_NOT_ELIGIBLE_EDGE
        return base

    try:
        from mechanistic_mind.physical_system.surface_elevation_support import (
            surface_support_height,
        )
        z_s = float(surface_support_height(world, float(x0), float(y0), config=config))
        z_e = float(surface_support_height(world, float(x_end), float(y_end), config=config))
    except Exception as exc:
        st.last_error = str(exc)
        base["status"] = STATUS_NOT_AVAILABLE_HEIGHT
        return base

    if not (math.isfinite(z_s) and math.isfinite(z_e)):
        base["status"] = STATUS_NOT_AVAILABLE_HEIGHT
        return base

    delta_z = float(z_e) - float(z_s)
    delta_u = compute_endpoint_delta_u(m_eff=float(m_eff), g=float(g), z_start=z_s, z_end=z_e)
    cmp = compare_ses_vs_candidate(ses_delta=float(ses_delta), candidate_delta_u=float(delta_u))

    status = STATUS_PARTIAL_DIAGNOSTIC if support_class == CLASS_PARTIAL else STATUS_ELIGIBLE
    if support_class in (CLASS_FULL, None, CLASS_PARTIAL):
        pass

    base.update({
        "status": status,
        "z_start_authoritative": float(z_s),
        "z_end_authoritative": float(z_e),
        "delta_z_authoritative": float(delta_z),
        "candidate_endpoint_delta_u": float(delta_u),
        "difference": float(delta_u) - float(ses_delta),
        "comparison_class": cmp,
    })
    return base


def _bump_counters(st: ContinuousGravitationalPeDiagnosticShadowState, result: dict[str, Any]) -> None:
    status = str(result.get("status") or "")
    kind = str(result.get("entity_kind") or "")
    if kind == "body":
        st.counters["body_queries"] = int(st.counters.get("body_queries", 0)) + 1
    elif kind == "experimenter":
        st.counters["experimenter_queries"] = int(st.counters.get("experimenter_queries", 0)) + 1
    elif kind in ("free_object", "resource_object", "object"):
        st.counters["free_object_queries"] = int(st.counters.get("free_object_queries", 0)) + 1

    status_map = {
        STATUS_ELIGIBLE: "eligible",
        STATUS_PARTIAL_DIAGNOSTIC: "partial_diagnostic",
        STATUS_BLOCKED_NO_COMMIT: "blocked_no_commit",
        STATUS_SUPPORT_LOSS: "support_loss",
        STATUS_NOT_ELIGIBLE_EDGE: "edge_ineligible",
        STATUS_NOT_ELIGIBLE_AIRBORNE: "airborne_ineligible",
        STATUS_NOT_AVAILABLE_HEIGHT: "height_unavailable",
        STATUS_INVALID_MASS: "invalid_mass",
    }
    ck = status_map.get(status)
    if ck:
        st.counters[ck] = int(st.counters.get(ck, 0)) + 1

    bucket = _transition_bucket(result.get("transition_class"))
    if bucket == "smooth":
        st.counters["smooth_count"] = int(st.counters.get("smooth_count", 0)) + 1
    elif bucket == "topological":
        st.counters["topological_count"] = int(st.counters.get("topological_count", 0)) + 1
    elif bucket == "microrelief":
        st.counters["microrelief_count"] = int(st.counters.get("microrelief_count", 0)) + 1

    cmp = str(result.get("comparison_class") or "")
    cmp_map = {
        CMP_ZERO_BOTH: "cmp_zero_both",
        CMP_MATCH: "cmp_match",
        CMP_CURRENT_SES_ONLY: "cmp_current_ses_only",
        CMP_CANDIDATE_ONLY: "cmp_candidate_only",
        CMP_DIFFERENT_MAGNITUDE: "cmp_different_magnitude",
        CMP_DIFFERENT_SIGN: "cmp_different_sign",
        CMP_INCOMPARABLE: "cmp_incomparable",
    }
    cm = cmp_map.get(cmp)
    if cm:
        st.counters[cm] = int(st.counters.get(cm, 0)) + 1

    if (
        str(result.get("event_kind") or "") == "LEVEL"
        and result.get("candidate_endpoint_delta_u") is not None
        and abs(float(result["candidate_endpoint_delta_u"])) > EPS_ZERO
    ):
        st.counters["level_nonzero_candidate"] = int(st.counters.get("level_nonzero_candidate", 0)) + 1

    if result.get("influenced_physics") or result.get("candidate_influenced_physics"):
        st.counters["physics_influence_anomalies"] = (
            int(st.counters.get("physics_influence_anomalies", 0)) + 1
        )


def _emit_receipt(st: ContinuousGravitationalPeDiagnosticShadowState, result: dict[str, Any]) -> None:
    receipt = dict(result)
    st.last_receipt = receipt
    st.history.append(receipt)
    lim = int(st.config.history_limit)
    if len(st.history) > lim:
        st.history = st.history[-lim:]
    st.counters["receipts_emitted"] = int(st.counters.get("receipts_emitted", 0)) + 1


def serialize_state(st: ContinuousGravitationalPeDiagnosticShadowState | None) -> dict[str, Any] | None:
    if st is None:
        return None
    return {
        "schema": STATE_SCHEMA,
        "config": st.config.to_dict(),
        "counters": dict(st.counters),
        "researcher_only": True,
    }


def restore_state(
    world: Any, data: dict[str, Any] | None, config: Any,
) -> ContinuousGravitationalPeDiagnosticShadowState | None:
    if not continuous_gravitational_pe_diagnostic_shadow_is_active(config):
        world.continuous_gravitational_pe_diagnostic_shadow_state = None
        return None
    if not isinstance(data, dict) or not data:
        st = ensure_continuous_gravitational_pe_diagnostic_shadow_for_runtime(world, config)
        if st is not None:
            st.restore_suppress_until_tick = int(getattr(world, "tick", 0) or 0)
        return st
    if str(data.get("schema")) != STATE_SCHEMA:
        raise ValueError(
            f"unknown continuous_gravitational_pe_diagnostic_shadow schema: {data.get('schema')}"
        )
    raw_cfg = data.get("config")
    if raw_cfg is None:
        cur = getattr(config, "continuous_gravitational_pe_diagnostic_shadow", None)
        raw_cfg = cur.to_dict() if cur is not None and hasattr(cur, "to_dict") else None
    cfg = ContinuousGravitationalPeDiagnosticShadowConfig.from_dict(raw_cfg)
    validate_config(cfg)
    st = ContinuousGravitationalPeDiagnosticShadowState(
        config=cfg,
        counters={**_default_counters(), **{k: int(v) for k, v in dict(data.get("counters") or {}).items()}},
    )
    st.restore_suppress_until_tick = int(getattr(world, "tick", 0) or 0)
    world.continuous_gravitational_pe_diagnostic_shadow_state = st
    return st


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "label": "Continuous Gravitational PE Diagnostic Shadow V1",
        "config_path": "continuous_gravitational_pe_diagnostic_shadow.enabled",
        "enabled": bool(enabled),
        "promotion_class": "EXPERIMENTAL",
        "provenance": "acanthostega_continuous_gravitational_pe_diagnostic_shadow_v1",
        "default_integrated": True,
        "banner": BANNER,
        "analyzer_section": ANALYZER_SECTION,
        "profile_version": PROFILE_VERSION,
        "endpoint_authority": ENDPOINT_AUTHORITY,
        "pe_authority": PE_AUTHORITY_SES_DDA,
        "candidate_pe_authority": CANDIDATE_AUTHORITY,
        "mode": MODE,
        "influenced_physics": False,
        "continuous_pe_active": False,
        "scope": {
            "bodies": True,
            "experimenter": True,
            "free_objects": True,
            "held_objects": False,
            "physics_unchanged": True,
        },
        "historical_compatibility": "missing key means continuous gravitational PE diagnostic shadow OFF",
    }


def researcher_summary(world: Any) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    last = st.last_receipt or {}
    return {
        "mechanism": MECHANISM_ID,
        "profile_version": PROFILE_VERSION,
        "banner": BANNER,
        "analyzer_section": ANALYZER_SECTION,
        "counters": dict(st.counters),
        "last_receipt": last or None,
        "endpoint_authority": ENDPOINT_AUTHORITY,
        "mode": MODE,
        "current_pe_authority": CURRENT_AUTHORITY,
        "candidate_pe_authority": CANDIDATE_AUTHORITY,
        "influenced_physics": False,
        "continuous_pe_active": False,
        "agent_accessible": False,
        "researcher_only": True,
    }


def status_text(world: Any | None = None) -> str:
    if world is None:
        return BANNER
    st = state_of(world)
    if st is None:
        return BANNER
    c = st.counters
    last = st.last_receipt or {}
    return (
        f"{BANNER}\n"
        f"queries={c.get('queries', 0)} dup={c.get('duplicate_suppressed', 0)} "
        f"eligible={c.get('eligible', 0)} blocked={c.get('blocked_no_commit', 0)} "
        f"cand_only={c.get('cmp_candidate_only', 0)} match={c.get('cmp_match', 0)} "
        f"level_nz={c.get('level_nonzero_candidate', 0)}\n"
        f"last status={last.get('status')} cmp={last.get('comparison_class')} "
        f"ΔU={last.get('candidate_endpoint_delta_u')} ses={last.get('current_ses_gravitational_delta')}"
    )


def overlay_payload(world: Any) -> dict[str, Any] | None:
    summary = researcher_summary(world)
    if summary is None:
        return None
    return {
        "caption": OVERLAY_CAPTION,
        "researcher_only": True,
        "mechanism": MECHANISM_ID,
        "summary": summary,
    }
