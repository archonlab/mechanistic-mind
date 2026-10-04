"""Acanthostega PHASE C · G2D DIAGNOSTIC NORMAL-LOAD SHADOW.

Preset: ACANTHOSTEGA_PHASE_C_DIAGNOSTIC_NORMAL_LOAD_SHADOW
Parent: ACANTHOSTEGA_PHASE_C_RADIUS_AWARE_FACE_SWEEP
Mechanism: diagnostic_normal_load_shadow
Profile: CONTINUOUS_NORMAL_LOAD_SHADOW_V1

Computes candidate N_projected = m_eff · g · n_z from centre analytic CSG normal.
SHADOW / RESEARCHER-ONLY — never feeds friction, traction, SES, PE, cognition, or motion.

Physical authority remains FLAT: N_physical = m_eff · g (body) / mass · g (FREE).
PE authority: PE_AUTHORITY_SES_DDA (unchanged).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from mechanistic_mind.physical_system.continuous_surface_geometry import (
    continuous_surface_geometry_is_active,
    sample_surface_geometry,
)
from mechanistic_mind.physical_system.radius_aware_face_sweep import (
    radius_aware_face_sweep_is_active,
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
    PE_AUTHORITY_SES_DDA,
)

MECHANISM_ID = "diagnostic_normal_load_shadow"
PROFILE_VERSION = "CONTINUOUS_NORMAL_LOAD_SHADOW_V1"
STAGE_ALIAS = "CONTINUOUS_NORMAL_LOAD_SHADOW_V1"
STATE_SCHEMA = "DIAGNOSTIC_NORMAL_LOAD_SHADOW_STATE_V1"
RECEIPT_KIND = "CONTINUOUS_NORMAL_LOAD_SHADOW"

NORMAL_SOURCE = "CENTRE_ANALYTIC_CSG_N_HAT"
PHYSICAL_AUTHORITY = "FLAT_NORMAL_LOAD"
CANDIDATE_AUTHORITY = "PROJECTED_NORMAL_LOAD"
MODE = "DIAGNOSTIC_SHADOW"

BANNER = (
    "CONTINUOUS NORMAL LOAD · DIAGNOSTIC SHADOW\n"
    "PHYSICAL N = m·g · CANDIDATE N = m·g·n_z\n"
    "SOURCE = CENTRE ANALYTIC CSG NORMAL · PHYSICS EFFECT = NONE"
)
OVERLAY_CAPTION = BANNER
ANALYZER_SECTION = "CONTINUOUS NORMAL-LOAD SHADOW (DIAGNOSTIC)"

HISTORY_LIMIT_DEFAULT = 64
EPS_FLAT = 1e-12
EPS_NZ = 1e-15

# Eligibility / status
STATUS_PROJECTED = "PROJECTED"
STATUS_FLAT_EQUIVALENT = "FLAT_EQUIVALENT"
STATUS_PARTIAL_DIAGNOSTIC = "PARTIAL_DIAGNOSTIC_NOT_ACTIVATABLE"
STATUS_NOT_ELIGIBLE_EDGE = "NOT_ELIGIBLE_EDGE_OR_SPARSE"
STATUS_NOT_ELIGIBLE_LOSS = "NOT_ELIGIBLE_SUPPORT_LOSS"
STATUS_NOT_ELIGIBLE_AIRBORNE = "NOT_ELIGIBLE_AIRBORNE"
STATUS_NOT_AVAILABLE_GEOMETRY = "NOT_AVAILABLE_GEOMETRY"
STATUS_INVALID_MASS = "INVALID_MASS"
STATUS_INACTIVE = "INACTIVE"
STATUS_HELD_EXCLUDED = "HELD_OBJECT_NO_INDEPENDENT_GROUND_N"

RESEARCHER_FLAGS = {
    "researcher_only": True,
    "agent_accessible": False,
    "semantic_label": False,
    "influenced_physics": False,
    "mode": MODE,
    "physical_authority": PHYSICAL_AUTHORITY,
    "candidate_authority": CANDIDATE_AUTHORITY,
    "normal_projection_charges_work": False,
    "normal_projection_changes_pe": False,
    "pe_authority": PE_AUTHORITY_SES_DDA,
}


# ---------------------------------------------------------------------------
# Config / activation
# ---------------------------------------------------------------------------


@dataclass
class DiagnosticNormalLoadShadowConfig:
    enabled: bool = False
    history_limit: int = HISTORY_LIMIT_DEFAULT
    pe_authority: str = PE_AUTHORITY_SES_DDA
    normal_source: str = NORMAL_SOURCE

    def to_dict(self) -> dict[str, Any]:
        on = bool(self.enabled)
        return {
            "enabled": on,
            "history_limit": int(self.history_limit),
            "pe_authority": str(self.pe_authority),
            "normal_source": str(self.normal_source),
            "profile_version": PROFILE_VERSION,
            "stage_alias": STAGE_ALIAS,
            "mode": MODE,
            "physical_authority": PHYSICAL_AUTHORITY,
            "candidate_authority": CANDIDATE_AUTHORITY,
            "influenced_physics": False,
            "normal_physical_effects_active": False,
            "projected_normal_load_active": False,
            "tangent_gravity": False,
            "passive_slope_sliding": False,
            "continuous_pe": False,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "DiagnosticNormalLoadShadowConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        ver = data.get("profile_version")
        if ver is not None and str(ver) != PROFILE_VERSION:
            raise ValueError(f"unknown diagnostic_normal_load_shadow profile: {ver}")
        return cls(
            enabled=bool(data.get("enabled", False)),
            history_limit=int(data.get("history_limit", HISTORY_LIMIT_DEFAULT)),
            pe_authority=str(data.get("pe_authority", PE_AUTHORITY_SES_DDA)),
            normal_source=str(data.get("normal_source", NORMAL_SOURCE)),
        )


def validate_config(cfg: DiagnosticNormalLoadShadowConfig) -> None:
    if not (1 <= int(cfg.history_limit) <= 512):
        raise ValueError("history_limit must be in [1, 512]")
    if str(cfg.normal_source) != NORMAL_SOURCE:
        raise ValueError(f"normal_source must be {NORMAL_SOURCE}")


def _line_ok(config: Any) -> bool:
    return (
        config is not None
        and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"
    )


def diagnostic_normal_load_shadow_is_active(config: Any) -> bool:
    if not _line_ok(config):
        return False
    cfg = getattr(config, "diagnostic_normal_load_shadow", None)
    if cfg is None or not bool(getattr(cfg, "enabled", False)):
        return False
    # Parent chain: face sweep → G2C2 → G2C1 → SES → CSG (face_sweep gate implies rest).
    return bool(
        radius_aware_face_sweep_is_active(config)
        and continuous_surface_geometry_is_active(config)
    )


def diagnostic_normal_load_shadow_active_on_world(world: Any, config: Any | None = None) -> bool:
    if config is not None:
        return diagnostic_normal_load_shadow_is_active(config) and state_of(world) is not None
    st = state_of(world)
    return st is not None and bool(st.config.enabled)


def set_diagnostic_normal_load_shadow(config: Any, enabled: bool) -> None:
    if config is None:
        return
    on = bool(enabled) and _line_ok(config)
    cur = getattr(config, "diagnostic_normal_load_shadow", None)
    if cur is None:
        if on:
            config.diagnostic_normal_load_shadow = DiagnosticNormalLoadShadowConfig(enabled=True)
        return
    if isinstance(cur, dict):
        cfg = DiagnosticNormalLoadShadowConfig.from_dict(cur)
        cfg.enabled = on
        config.diagnostic_normal_load_shadow = cfg
    else:
        cur.enabled = on


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class DiagnosticNormalLoadShadowState:
    config: DiagnosticNormalLoadShadowConfig
    last_receipt: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=lambda: _default_counters())
    # Dedup: one authoritative result per entity_key per tick.
    query_tick: int | None = None
    tick_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    restore_suppress_until_tick: int | None = None
    last_error: str | None = None


def _default_counters() -> dict[str, int]:
    return {
        "queries": 0,
        "unique_entity_queries": 0,
        "duplicate_suppressed": 0,
        "full_eligible": 0,
        "partial_diagnostic": 0,
        "edge_ineligible": 0,
        "loss_ineligible": 0,
        "airborne_ineligible": 0,
        "geometry_unavailable": 0,
        "invalid_mass": 0,
        "body_queries": 0,
        "free_object_queries": 0,
        "experimenter_queries": 0,
        "receipts_emitted": 0,
        "physics_influence_anomalies": 0,
        "restore_false_hit_suppressed": 0,
    }


def state_of(world: Any) -> DiagnosticNormalLoadShadowState | None:
    raw = getattr(world, "diagnostic_normal_load_shadow_state", None)
    return raw if isinstance(raw, DiagnosticNormalLoadShadowState) else None


def ensure_diagnostic_normal_load_shadow_for_runtime(
    world: Any, config: Any
) -> DiagnosticNormalLoadShadowState | None:
    if not diagnostic_normal_load_shadow_is_active(config):
        if state_of(world) is not None:
            world.diagnostic_normal_load_shadow_state = None
        return None
    st = state_of(world)
    if st is not None:
        return st
    raw = getattr(config, "diagnostic_normal_load_shadow", None)
    cfg = (
        DiagnosticNormalLoadShadowConfig.from_dict(
            raw.to_dict() if hasattr(raw, "to_dict") else raw
        )
        if raw is not None
        else DiagnosticNormalLoadShadowConfig(enabled=True)
    )
    cfg.enabled = True
    validate_config(cfg)
    st = DiagnosticNormalLoadShadowState(config=cfg)
    world.diagnostic_normal_load_shadow_state = st
    return st


# ---------------------------------------------------------------------------
# Pure eligibility / projection
# ---------------------------------------------------------------------------


def _classify_eligibility(
    *,
    grounded: bool,
    support_class: str | None,
) -> str:
    if not grounded:
        return STATUS_NOT_ELIGIBLE_AIRBORNE
    cls = str(support_class) if support_class is not None else None
    if cls == CLASS_AIRBORNE:
        return STATUS_NOT_ELIGIBLE_AIRBORNE
    if cls == CLASS_LOSS:
        return STATUS_NOT_ELIGIBLE_LOSS
    if cls == CLASS_EDGE:
        return STATUS_NOT_ELIGIBLE_EDGE
    if cls == CLASS_PARTIAL:
        return STATUS_PARTIAL_DIAGNOSTIC
    if cls == CLASS_FULL or cls is None:
        # Missing class on first tick → treat as FULL-eligible diagnostic (same as G2B traction).
        return STATUS_PROJECTED
    # Unknown class: conservative not-eligible
    return STATUS_NOT_ELIGIBLE_EDGE


def _authoritative_ground_n(status: str) -> bool:
    """Whether this status would be eligible for a future *active* projected N."""
    return status in (STATUS_PROJECTED, STATUS_FLAT_EQUIVALENT)


def compute_projected_normal_load(
    *,
    m_eff: float,
    g: float,
    n_z: float | None,
    grounded: bool,
    support_class: str | None,
    geometry_ok: bool,
) -> dict[str, Any]:
    """Pure math: flat + projected N and eligibility. No world mutation."""
    if not (math.isfinite(float(m_eff)) and float(m_eff) > 0.0):
        return {
            "status": STATUS_INVALID_MASS,
            "m_eff": float(m_eff) if math.isfinite(float(m_eff)) else None,
            "g": float(g),
            "n_x": None,
            "n_y": None,
            "n_z": None,
            "N_flat": None,
            "N_projected": None,
            "delta_N": None,
            "ratio": None,
            "authoritative_ground_projected_n": False,
            "partial_not_activatable": False,
        }
    if not (math.isfinite(float(g)) and float(g) > 0.0):
        return {
            "status": STATUS_NOT_AVAILABLE_GEOMETRY,
            "m_eff": float(m_eff),
            "g": float(g),
            "n_x": None,
            "n_y": None,
            "n_z": None,
            "N_flat": None,
            "N_projected": None,
            "delta_N": None,
            "ratio": None,
            "authoritative_ground_projected_n": False,
            "partial_not_activatable": False,
        }

    N_flat = float(m_eff) * float(g)
    status = _classify_eligibility(grounded=bool(grounded), support_class=support_class)

    if status == STATUS_NOT_ELIGIBLE_AIRBORNE:
        return {
            "status": status,
            "m_eff": float(m_eff),
            "g": float(g),
            "n_x": None,
            "n_y": None,
            "n_z": None,
            "N_flat": float(N_flat),
            "N_projected": None,
            "delta_N": None,
            "ratio": None,
            "authoritative_ground_projected_n": False,
            "partial_not_activatable": False,
        }

    if status in (STATUS_NOT_ELIGIBLE_LOSS, STATUS_NOT_ELIGIBLE_EDGE):
        return {
            "status": status,
            "m_eff": float(m_eff),
            "g": float(g),
            "n_x": None,
            "n_y": None,
            "n_z": None,
            "N_flat": float(N_flat),
            "N_projected": None,
            "delta_N": None,
            "ratio": None,
            "authoritative_ground_projected_n": False,
            "partial_not_activatable": False,
        }

    if not geometry_ok or n_z is None or not math.isfinite(float(n_z)):
        return {
            "status": STATUS_NOT_AVAILABLE_GEOMETRY,
            "m_eff": float(m_eff),
            "g": float(g),
            "n_x": None,
            "n_y": None,
            "n_z": None,
            "N_flat": float(N_flat),
            "N_projected": None,
            "delta_N": None,
            "ratio": None,
            "authoritative_ground_projected_n": False,
            "partial_not_activatable": status == STATUS_PARTIAL_DIAGNOSTIC,
        }

    nz = float(n_z)
    N_proj = float(N_flat) * nz
    if abs(nz - 1.0) <= EPS_FLAT and status == STATUS_PROJECTED:
        status = STATUS_FLAT_EQUIVALENT
    ratio = (N_proj / N_flat) if abs(N_flat) > EPS_NZ else None
    return {
        "status": status,
        "m_eff": float(m_eff),
        "g": float(g),
        "n_z": float(nz),
        "N_flat": float(N_flat),
        "N_projected": float(N_proj),
        "delta_N": float(N_proj - N_flat),
        "ratio": float(ratio) if ratio is not None else None,
        "authoritative_ground_projected_n": _authoritative_ground_n(status),
        "partial_not_activatable": status == STATUS_PARTIAL_DIAGNOSTIC,
    }


def entity_key(*, entity_kind: str, entity_id: str) -> str:
    """Stable shared-world key — never Python id()."""
    return f"{str(entity_kind)}:{str(entity_id)}"


# ---------------------------------------------------------------------------
# Shared query seam (one result / entity / tick)
# ---------------------------------------------------------------------------


def query_diagnostic_normal_load_shadow(
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
    seam: str = "TRACTION_PREP",
) -> dict[str, Any] | None:
    """Authoritative diagnostic query. Deduped per entity/tick. Never mutates physics.

    Returns the shared result dict (also stored on state). None if mechanism OFF.
    When ``config`` is None (FOST/FOGF world hooks), uses already-ensured world state.
    """
    if config is not None:
        if not diagnostic_normal_load_shadow_is_active(config):
            return None
        st = ensure_diagnostic_normal_load_shadow_for_runtime(world, config)
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

    # Resolve support class (prior-tick G2B attr when present).
    cls = support_class
    if cls is None and entity is not None:
        cls = read_entity_support_class(entity)

    # Centre analytic CSG normal — diagnostic only.
    nx = ny = nz = None
    geometry_ok = False
    try:
        sample = sample_surface_geometry(
            world,
            float(x),
            float(y),
            config=config,
            record=False,
            reason="diagnostic_normal_load_shadow",
        )
        nx = float(sample["normal_x"])
        ny = float(sample["normal_y"])
        nz = float(sample["normal_z"])
        geometry_ok = all(math.isfinite(v) for v in (nx, ny, nz))
    except Exception as exc:  # pragma: no cover — geometry failure → status
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

    # For PARTIAL / PROJECTED / FLAT_EQUIVALENT attach normals when geometry ok.
    if geometry_ok and proj["status"] in (
        STATUS_PROJECTED,
        STATUS_FLAT_EQUIVALENT,
        STATUS_PARTIAL_DIAGNOSTIC,
    ):
        proj["n_x"] = float(nx)  # type: ignore[arg-type]
        proj["n_y"] = float(ny)  # type: ignore[arg-type]
        proj["n_z"] = float(nz)  # type: ignore[arg-type]

    result: dict[str, Any] = {
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
        "support_class": str(cls) if cls is not None else None,
        "normal_source": NORMAL_SOURCE,
        "held_mass": float(held_mass) if held_mass is not None else None,
        "body_mass": float(body_mass) if body_mass is not None else None,
        "physical_normal_load_N": float(m_eff) * float(g)
        if math.isfinite(float(m_eff)) and math.isfinite(float(g)) and float(m_eff) > 0 and float(g) > 0
        else None,
        "influenced_physics": False,
        **proj,
        **RESEARCHER_FLAGS,
    }

    st.tick_results[key] = result
    st.counters["queries"] = int(st.counters.get("queries", 0)) + 1
    st.counters["unique_entity_queries"] = int(st.counters.get("unique_entity_queries", 0)) + 1
    _bump_status_counters(st, result)
    _emit_receipt(st, result)
    return result


def _bump_status_counters(st: DiagnosticNormalLoadShadowState, result: dict[str, Any]) -> None:
    status = str(result.get("status") or "")
    kind = str(result.get("entity_kind") or "")
    if kind == "body":
        st.counters["body_queries"] = int(st.counters.get("body_queries", 0)) + 1
    elif kind == "experimenter":
        st.counters["experimenter_queries"] = int(st.counters.get("experimenter_queries", 0)) + 1
    elif kind in ("free_object", "resource_object", "object"):
        st.counters["free_object_queries"] = int(st.counters.get("free_object_queries", 0)) + 1

    if status in (STATUS_PROJECTED, STATUS_FLAT_EQUIVALENT):
        st.counters["full_eligible"] = int(st.counters.get("full_eligible", 0)) + 1
    elif status == STATUS_PARTIAL_DIAGNOSTIC:
        st.counters["partial_diagnostic"] = int(st.counters.get("partial_diagnostic", 0)) + 1
    elif status == STATUS_NOT_ELIGIBLE_EDGE:
        st.counters["edge_ineligible"] = int(st.counters.get("edge_ineligible", 0)) + 1
    elif status == STATUS_NOT_ELIGIBLE_LOSS:
        st.counters["loss_ineligible"] = int(st.counters.get("loss_ineligible", 0)) + 1
    elif status == STATUS_NOT_ELIGIBLE_AIRBORNE:
        st.counters["airborne_ineligible"] = int(st.counters.get("airborne_ineligible", 0)) + 1
    elif status == STATUS_NOT_AVAILABLE_GEOMETRY:
        st.counters["geometry_unavailable"] = int(st.counters.get("geometry_unavailable", 0)) + 1
    elif status == STATUS_INVALID_MASS:
        st.counters["invalid_mass"] = int(st.counters.get("invalid_mass", 0)) + 1

    if result.get("influenced_physics"):
        st.counters["physics_influence_anomalies"] = (
            int(st.counters.get("physics_influence_anomalies", 0)) + 1
        )


def _emit_receipt(st: DiagnosticNormalLoadShadowState, result: dict[str, Any]) -> None:
    receipt = dict(result)
    st.last_receipt = receipt
    st.history.append(receipt)
    lim = int(st.config.history_limit)
    if len(st.history) > lim:
        st.history = st.history[-lim:]
    st.counters["receipts_emitted"] = int(st.counters.get("receipts_emitted", 0)) + 1


def maybe_record_body_shadow(
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
    seam: str = "TRACTION_PREP",
) -> dict[str, Any] | None:
    """Hook for BNLT prepare / MOVE static — no physics mutation."""
    return query_diagnostic_normal_load_shadow(
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


def maybe_record_free_object_shadow(
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
    """Hook for FOST / FOGF plan — no physics mutation. HELD objects excluded by caller."""
    return query_diagnostic_normal_load_shadow(
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


# ---------------------------------------------------------------------------
# Serialization / catalog / overlay
# ---------------------------------------------------------------------------


def serialize_state(st: DiagnosticNormalLoadShadowState | None) -> dict[str, Any] | None:
    if st is None:
        return None
    return {
        "schema": STATE_SCHEMA,
        "config": st.config.to_dict(),
        "counters": dict(st.counters),
        "researcher_only": True,
        # tick_results / history are derived — not serialized
    }


def restore_state(
    world: Any, data: dict[str, Any] | None, config: Any,
) -> DiagnosticNormalLoadShadowState | None:
    if not diagnostic_normal_load_shadow_is_active(config):
        world.diagnostic_normal_load_shadow_state = None
        return None
    if not isinstance(data, dict) or not data:
        st = ensure_diagnostic_normal_load_shadow_for_runtime(world, config)
        if st is not None:
            st.restore_suppress_until_tick = int(getattr(world, "tick", 0) or 0)
        return st
    if str(data.get("schema")) != STATE_SCHEMA:
        raise ValueError(f"unknown diagnostic_normal_load_shadow schema: {data.get('schema')}")
    raw_cfg = data.get("config")
    if raw_cfg is None:
        cur = getattr(config, "diagnostic_normal_load_shadow", None)
        raw_cfg = cur.to_dict() if cur is not None and hasattr(cur, "to_dict") else None
    cfg = DiagnosticNormalLoadShadowConfig.from_dict(raw_cfg)
    validate_config(cfg)
    st = DiagnosticNormalLoadShadowState(
        config=cfg,
        counters={**_default_counters(), **{k: int(v) for k, v in dict(data.get("counters") or {}).items()}},
    )
    st.restore_suppress_until_tick = int(getattr(world, "tick", 0) or 0)
    world.diagnostic_normal_load_shadow_state = st
    return st


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "label": "Diagnostic Continuous Normal-Load Shadow V1",
        "config_path": "diagnostic_normal_load_shadow.enabled",
        "enabled": bool(enabled),
        "promotion_class": "EXPERIMENTAL",
        "provenance": "acanthostega_diagnostic_normal_load_shadow_v1",
        "default_integrated": True,
        "banner": BANNER,
        "analyzer_section": ANALYZER_SECTION,
        "profile_version": PROFILE_VERSION,
        "normal_source": NORMAL_SOURCE,
        "pe_authority": PE_AUTHORITY_SES_DDA,
        "mode": MODE,
        "influenced_physics": False,
        "projected_normal_load_active": False,
        "scope": {
            "bodies": True,
            "experimenter": True,
            "free_objects": True,
            "held_objects": False,
            "physics_unchanged": True,
        },
        "historical_compatibility": "missing key means diagnostic normal-load shadow OFF",
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
        "normal_source": NORMAL_SOURCE,
        "mode": MODE,
        "physical_authority": PHYSICAL_AUTHORITY,
        "candidate_authority": CANDIDATE_AUTHORITY,
        "influenced_physics": False,
        "pe_authority": PE_AUTHORITY_SES_DDA,
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
    nz = last.get("n_z")
    ratio = last.get("ratio")
    return (
        f"{BANNER}\n"
        f"queries={c.get('queries', 0)} dup_suppressed={c.get('duplicate_suppressed', 0)} "
        f"full={c.get('full_eligible', 0)} partial={c.get('partial_diagnostic', 0)} "
        f"edge={c.get('edge_ineligible', 0)} loss={c.get('loss_ineligible', 0)} "
        f"air={c.get('airborne_ineligible', 0)}\n"
        f"last status={last.get('status')} n_z={nz} ratio={ratio}"
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
