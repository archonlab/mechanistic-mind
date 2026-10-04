"""Acanthostega PHASE C · G2C1 SES DECOMPOSITION CONTRACT.

Preset: ACANTHOSTEGA_PHASE_C_SES_DECOMPOSITION_CONTRACT
Parent: ACANTHOSTEGA_PHASE_C_RADIUS_AWARE_SUPPORT
Mechanism: ses_decomposition_contract
Profile: SES_TOPOLOGY_VS_CONTINUOUS_PE_SPLIT_V1
Stage alias: G2C1_SES_DECOMPOSITION_CONTRACT

CONTRACT ONLY — no PE law change, no physics mutation.

G2C1 adds:
  - explicit decomposition contract;
  - transition taxonomy;
  - explicit PE authority stamp;
  - researcher-only receipts;
  - snapshot compatibility;
  - Observer/Analyzer representation;
  - equivalence checks.

G2C1 does NOT change:
  - SES numerical physics;
  - SES thresholds;
  - SES DDA;
  - SES energy formula;
  - SES tick order;
  - G2B radius-aware support;
  - body/free-object traction;
  - contact physics;
  - impact acoustics.

ONE_PE_AUTHORITY_CURRENT = SES_DDA
NORMAL_PHYSICAL_EFFECTS_ACTIVE = NO
TANGENT_GRAVITY_IMPLEMENTED = NO
SLOPE_SLIDING_IMPLEMENTED = NO
RADIUS_FACE_SWEEP_IMPLEMENTED = NO
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from mechanistic_mind.physical_system.radius_aware_support_points import (
    radius_aware_support_points_is_active,
)
from mechanistic_mind.physical_system.surface_elevation_support import (
    surface_elevation_support_is_active,
)

MECHANISM_ID = "ses_decomposition_contract"
PROFILE_VERSION = "SES_TOPOLOGY_VS_CONTINUOUS_PE_SPLIT_V1"
STAGE_ALIAS = "G2C1_SES_DECOMPOSITION_CONTRACT"
STATE_SCHEMA = "SES_DECOMPOSITION_CONTRACT_STATE_V1"
RECEIPT_KIND = "SES_DECOMPOSITION_CONTRACT"

BANNER = (
    "SES DECOMPOSITION CONTRACT G2C1 · "
    "PE AUTHORITY: SES DDA · "
    "TRANSITION TAXONOMY ACTIVE · "
    "PHYSICS OUTPUTS IDENTICAL TO PARENT · "
    "NORMAL/TANGENT GRAVITY OFF · NO RADIUS-FACE SWEEP"
)
OVERLAY_CAPTION = BANNER
ANALYZER_SECTION = "SES DECOMPOSITION CONTRACT"

# --- PE Authority enum ---
PE_AUTHORITY_SES_DDA = "PE_AUTHORITY_SES_DDA"
PE_AUTHORITY_CONTINUOUS_GRAVITY = "PE_AUTHORITY_CONTINUOUS_GRAVITY"
PE_AUTHORITIES = (PE_AUTHORITY_SES_DDA, PE_AUTHORITY_CONTINUOUS_GRAVITY)
# G2C1: only SES DDA may be active. CONTINUOUS_GRAVITY is a reserved enum member
# (future G2C2+/G2D) and is rejected by validation; it cannot be activated by payload.
ACTIVE_PE_AUTHORITIES_G2C1 = (PE_AUTHORITY_SES_DDA,)
RESERVED_PE_AUTHORITIES = (PE_AUTHORITY_CONTINUOUS_GRAVITY,)
CURRENT_PE_AUTHORITY = PE_AUTHORITY_SES_DDA

# --- Transition taxonomy classes (from architecture document B4) ---
TRANSITION_SMOOTH_PATCH_TRAVERSAL = "SMOOTH_PATCH_TRAVERSAL"
TRANSITION_MICRORELIEF_STEP = "MICRORELIEF_STEP"
TRANSITION_LEDGE_BLOCK = "LEDGE_BLOCK"
TRANSITION_SUPPORT_DROP_LOS = "SUPPORT_DROP_LOS"
TRANSITION_OCCUPANT_SUPPORT_RISE = "OCCUPANT_SUPPORT_RISE"
TRANSITION_RADIUS_PARTIAL_CONTACT = "RADIUS_PARTIAL_CONTACT"
TRANSITION_CLIFF_NZ_CUTOFF = "CLIFF_NZ_CUTOFF"
TRANSITION_GEOMETRY_AMBIGUOUS = "GEOMETRY_AMBIGUOUS"

TRANSITION_TAXONOMY = (
    TRANSITION_SMOOTH_PATCH_TRAVERSAL,
    TRANSITION_MICRORELIEF_STEP,
    TRANSITION_LEDGE_BLOCK,
    TRANSITION_SUPPORT_DROP_LOS,
    TRANSITION_OCCUPANT_SUPPORT_RISE,
    TRANSITION_RADIUS_PARTIAL_CONTACT,
    TRANSITION_CLIFF_NZ_CUTOFF,
    TRANSITION_GEOMETRY_AMBIGUOUS,
)
# CLIFF_NZ_CUTOFF is RESERVED / diagnostic-only in G2C1: the runtime classifier never
# emits it, and normal_z has no physical effect (no N, friction, tangent gravity, or
# SES decision change). It exists only so the taxonomy enum is stable for G2C2+.
RESERVED_TRANSITION_CLASSES = (TRANSITION_CLIFF_NZ_CUTOFF,)
RUNTIME_EMITTABLE_TRANSITION_CLASSES = tuple(
    c for c in TRANSITION_TAXONOMY if c not in RESERVED_TRANSITION_CLASSES
)

# --- SES seams that emit exactly one contract receipt per entity transition ---
TRANSITION_SOURCE_PATH_GATE = "PATH_GATE"
TRANSITION_SOURCE_SUPPORT_RISE_PREFLIGHT = "SUPPORT_RISE_PREFLIGHT"
TRANSITION_SOURCE_GROUND_LOWERED = "GROUND_LOWERED"
TRANSITION_SOURCES = (
    TRANSITION_SOURCE_PATH_GATE,
    TRANSITION_SOURCE_SUPPORT_RISE_PREFLIGHT,
    TRANSITION_SOURCE_GROUND_LOWERED,
)

# SES event kinds (mirrors surface_elevation_support.EVENT_*; string-equal, no import cycle).
SES_EVENT_LEVEL = "LEVEL"
SES_EVENT_MICRO_UPHILL = "MICRO_UPHILL"
SES_EVENT_LARGE_UPHILL_BLOCKED = "LARGE_UPHILL_BLOCKED"
SES_EVENT_MICRO_DOWNHILL = "MICRO_DOWNHILL_INELASTIC"
SES_EVENT_LARGE_DOWNHILL_SUPPORT_LOST = "LARGE_DOWNHILL_SUPPORT_LOST"
SES_EVENT_INSUFFICIENT_WORK = "INSUFFICIENT_WORK_BLOCKED"
SES_EVENT_INSUFFICIENT_KINETIC = "INSUFFICIENT_KINETIC_BLOCKED"
SES_EVENT_REST_NEVER_CLIMBS = "REST_NEVER_CLIMBS_BLOCKED"
SES_EVENT_AIRBORNE_PASSTHROUGH = "AIRBORNE_PASSTHROUGH"
SES_BLOCKED_MICRO_EVENTS = (
    SES_EVENT_INSUFFICIENT_WORK,
    SES_EVENT_INSUFFICIENT_KINETIC,
    SES_EVENT_REST_NEVER_CLIMBS,
)

# --- Responsibility stamps ---
RESP_ENERGY_AUTHORITY = "energy_authority"
RESP_TOPOLOGY_GATE = "topology_gate"
RESP_MUTATION_SAFETY = "mutation_safety"
RESP_SUPPORT_LOSS_AUTHORITY = "support_loss_authority"
RESP_POSE_COMMIT_AUTHORITY = "pose_commit_authority"
RESP_HEIGHT_ORACLE = "height_oracle"
RESP_RADIUS_CLASSIFICATION = "radius_classification"
RESP_NORMAL = "normal"

# Honest description of the CURRENT seam (stamps never change state).
RESPONSIBILITY_STAMPS = {
    RESP_ENERGY_AUTHORITY: "SES_DDA",
    RESP_TOPOLOGY_GATE: "SES",
    RESP_MUTATION_SAFETY: "SES",
    # Path/mutation support loss is decided by SES (DDA large-downhill / ground-lowered);
    # ring-level LOSS_OF_SUPPORT is G2B post-vertical classification (FGG then falls).
    RESP_SUPPORT_LOSS_AUTHORITY: "SES_DDA_PATH_AND_MUTATION|G2B_RING_POST_VERTICAL",
    RESP_POSE_COMMIT_AUTHORITY: "SES_GATE_WITHIN_EXISTING_RUNTIME",
    RESP_HEIGHT_ORACLE: "CONTINUOUS_SURFACE_GEOMETRY_G1",
    RESP_RADIUS_CLASSIFICATION: "G2B_RADIUS_AWARE_SUPPORT_POINTS",
    RESP_NORMAL: "DIAGNOSTIC_ONLY",
}

# --- Flags ---
NORMAL_PHYSICAL_EFFECTS_ACTIVE = False
TANGENT_GRAVITY_IMPLEMENTED = False
SLOPE_SLIDING_IMPLEMENTED = False
RADIUS_FACE_SWEEP_IMPLEMENTED = False
CONTINUOUS_PE_ACTIVE = False

HISTORY_LIMIT_DEFAULT = 64
EPS_LEVEL = 1e-12

RESEARCHER_FLAGS = {
    "researcher_only": True,
    "agent_accessible": False,
    "semantic_label": False,
}


@dataclass
class SesDecompositionContractConfig:
    """Fresh default OFF. Missing snapshot field = OFF."""

    enabled: bool = False
    history_limit: int = HISTORY_LIMIT_DEFAULT
    pe_authority: str = PE_AUTHORITY_SES_DDA
    classifier_version: str = PROFILE_VERSION

    def to_dict(self) -> dict[str, Any]:
        on = bool(self.enabled)
        return {
            "enabled": on,
            "history_limit": int(self.history_limit),
            "pe_authority": str(self.pe_authority),
            "classifier_version": str(self.classifier_version),
            "profile_version": PROFILE_VERSION,
            "stage_alias": STAGE_ALIAS,
            "transition_taxonomy_active": bool(on),
            "continuous_pe_active": False,
            "tangent_gravity_active": False,
            "normal_physical_effects_active": False,
            "radius_face_sweep_active": False,
            "physics_equivalence_version": "G2C1_BIT_IDENTICAL_V1",
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "SesDecompositionContractConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        ver = data.get("profile_version")
        if ver is not None and str(ver) != PROFILE_VERSION:
            raise ValueError(f"unknown ses_decomposition_contract profile: {ver}")
        # Missing legacy field -> SES DDA. Present field must be a single active authority.
        pe = validate_pe_authority(data.get("pe_authority", PE_AUTHORITY_SES_DDA))
        return cls(
            enabled=bool(data.get("enabled", False)),
            history_limit=int(data.get("history_limit", HISTORY_LIMIT_DEFAULT)),
            pe_authority=pe,
            classifier_version=str(data.get("classifier_version", PROFILE_VERSION)),
        )


def validate_config(cfg: SesDecompositionContractConfig) -> None:
    if not (1 <= int(cfg.history_limit) <= 512):
        raise ValueError("history_limit must be in [1, 512]")
    validate_pe_authority(cfg.pe_authority)


def validate_pe_authority(value: Any) -> str:
    """Return the single valid G2C1 PE authority or raise ValueError.

    - list/tuple/set/dict (mixed or multi-authority) -> rejected;
    - unknown string -> rejected;
    - PE_AUTHORITY_CONTINUOUS_GRAVITY -> reserved, rejected in G2C1;
    - PE_AUTHORITY_SES_DDA -> accepted.
    """
    if isinstance(value, (list, tuple, set, frozenset, dict)):
        raise ValueError(f"MIXED_PE_AUTHORITY_REJECTED: {value!r}")
    if not isinstance(value, str) or not value:
        raise ValueError(f"MISSING_OR_INVALID_PE_AUTHORITY: {value!r}")
    if "|" in value or "+" in value or "," in value:
        raise ValueError(f"MIXED_PE_AUTHORITY_REJECTED: {value!r}")
    if value not in PE_AUTHORITIES:
        raise ValueError(f"UNKNOWN_PE_AUTHORITY: {value!r}")
    if value not in ACTIVE_PE_AUTHORITIES_G2C1:
        raise ValueError(f"RESERVED_PE_AUTHORITY_NOT_ACTIVATABLE_IN_G2C1: {value!r}")
    return value


def _line_ok(config: Any) -> bool:
    return config is not None and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"


def ses_decomposition_contract_is_active(config: Any) -> bool:
    if not _line_ok(config):
        return False
    cfg = getattr(config, "ses_decomposition_contract", None)
    if cfg is None or not bool(getattr(cfg, "enabled", False)):
        return False
    return bool(
        radius_aware_support_points_is_active(config)
        and surface_elevation_support_is_active(config)
    )


def ses_decomposition_contract_active_on_world(world: Any, config: Any | None = None) -> bool:
    """Active if config says so, or (config=None seams, e.g. FREE object gate) if the
    world carries an enabled G2C1 state. Mirrors surface_elevation_support_active_on_world."""
    if config is not None:
        return ses_decomposition_contract_is_active(config) and state_of(world) is not None
    st = state_of(world)
    return st is not None and bool(st.config.enabled)


def set_ses_decomposition_contract(config: Any, enabled: bool) -> None:
    if config is None:
        return
    on = bool(enabled) and _line_ok(config)
    cur = getattr(config, "ses_decomposition_contract", None)
    if cur is None:
        if on:
            config.ses_decomposition_contract = SesDecompositionContractConfig(enabled=True)
        return
    if isinstance(cur, dict):
        cfg = SesDecompositionContractConfig.from_dict(cur)
        cfg.enabled = on
        config.ses_decomposition_contract = cfg
    else:
        cur.enabled = on


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class SesDecompositionContractState:
    config: SesDecompositionContractConfig
    last_receipt: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=lambda: _default_counters())
    # Transient dedup: application keys already recorded in the current tick (not serialized;
    # post-restore ticks are strictly later so no cross-restore collision is possible).
    applied_keys_tick: int | None = None
    applied_keys: set = field(default_factory=set)
    last_error: str | None = None


def _default_counters() -> dict[str, int]:
    return {
        "receipts_emitted": 0,
        "level": 0,
        "micro_uphill_accepted": 0,
        "micro_uphill_blocked": 0,
        "large_uphill_blocked": 0,
        "micro_downhill": 0,
        "large_downhill_support_lost": 0,
        "support_rise_rejected": 0,
        "ground_lowered_airborne": 0,
        "radius_partial": 0,
        "radius_loss": 0,
        "ambiguous": 0,
        "airborne_passthrough": 0,
        "duplicate_application_key_suppressed": 0,
        "contract_emission_errors": 0,
    }


def state_of(world: Any) -> SesDecompositionContractState | None:
    raw = getattr(world, "ses_decomposition_contract_state", None)
    return raw if isinstance(raw, SesDecompositionContractState) else None


def ensure_ses_decomposition_contract_for_runtime(
    world: Any, config: Any
) -> SesDecompositionContractState | None:
    if not ses_decomposition_contract_is_active(config):
        if state_of(world) is not None:
            world.ses_decomposition_contract_state = None
        return None
    st = state_of(world)
    if st is not None:
        return st
    raw = getattr(config, "ses_decomposition_contract", None)
    cfg = (
        SesDecompositionContractConfig.from_dict(
            raw.to_dict() if hasattr(raw, "to_dict") else raw
        )
        if raw is not None
        else SesDecompositionContractConfig(enabled=True)
    )
    cfg.enabled = True
    validate_config(cfg)
    st = SesDecompositionContractState(config=cfg)
    world.ses_decomposition_contract_state = st
    return st


# ---------------------------------------------------------------------------
# Transition taxonomy classifier
# ---------------------------------------------------------------------------


def classify_transition_taxonomy(
    *,
    event_kind: str,
    delta_h: float,
    microrelief_threshold: float,
    support_class: str | None = None,
    radius_fraction: float | None = None,
    radius_spread: float | None = None,
    high_ring_anomaly: bool = False,
    mutation_provenance: str | None = None,
) -> dict[str, Any]:
    """Classify a SES transition into the G2C1 taxonomy.

    This is a READ-ONLY classifier. It does not mutate any state.
    It only labels what SES already decided.
    """
    # Dynamic mutation provenance
    if mutation_provenance is not None:
        if mutation_provenance == "OCCUPIED_SUPPORT_RISE":
            return {
                "transition_class": TRANSITION_OCCUPANT_SUPPORT_RISE,
                "evidence": "mutation_provenance",
                "classifier_version": PROFILE_VERSION,
                "ambiguity_reason": None,
            }
        if mutation_provenance == "GROUND_LOWERED":
            return {
                "transition_class": TRANSITION_SUPPORT_DROP_LOS,
                "evidence": "mutation_provenance",
                "classifier_version": PROFILE_VERSION,
                "ambiguity_reason": None,
            }

    # SES decisive (non-LEVEL) events take precedence over the ring label: the ring class
    # never overrides what SES decided.
    if event_kind == SES_EVENT_LARGE_UPHILL_BLOCKED:
        return {
            "transition_class": TRANSITION_LEDGE_BLOCK,
            "evidence": "ses_event_large_uphill",
            "classifier_version": PROFILE_VERSION,
            "ambiguity_reason": None,
        }
    # Radius face-sweep barrier (SES plan evidence V1): same LEDGE_BLOCK class; no new taxonomy.
    if event_kind == "RADIUS_FACE_BARRIER":
        return {
            "transition_class": TRANSITION_LEDGE_BLOCK,
            "evidence": "radius_face_barrier",
            "classifier_version": PROFILE_VERSION,
            "ambiguity_reason": None,
        }
    if event_kind == "RADIUS_FACE_BARRIER_HARD_CAP":
        return {
            "transition_class": TRANSITION_GEOMETRY_AMBIGUOUS,
            "evidence": "face_sweep_hard_cap",
            "classifier_version": PROFILE_VERSION,
            "ambiguity_reason": "hard_cap_unresolved",
        }
    if event_kind in SES_BLOCKED_MICRO_EVENTS:
        return {
            "transition_class": TRANSITION_MICRORELIEF_STEP,
            "evidence": "ses_event_micro_uphill_rejected",
            "classifier_version": PROFILE_VERSION,
            "ambiguity_reason": None,
        }
    if event_kind in (SES_EVENT_MICRO_UPHILL, SES_EVENT_MICRO_DOWNHILL):
        return {
            "transition_class": TRANSITION_MICRORELIEF_STEP,
            "evidence": "ses_event_micro_uphill" if event_kind == SES_EVENT_MICRO_UPHILL else "ses_event_micro_downhill",
            "classifier_version": PROFILE_VERSION,
            "ambiguity_reason": None,
        }
    if event_kind == SES_EVENT_LARGE_DOWNHILL_SUPPORT_LOST:
        return {
            "transition_class": TRANSITION_SUPPORT_DROP_LOS,
            "evidence": "ses_event_large_downhill",
            "classifier_version": PROFILE_VERSION,
            "ambiguity_reason": None,
        }
    if event_kind == SES_EVENT_AIRBORNE_PASSTHROUGH:
        return {
            "transition_class": TRANSITION_GEOMETRY_AMBIGUOUS,
            "evidence": "ses_airborne_passthrough",
            "classifier_version": PROFILE_VERSION,
            "ambiguity_reason": "airborne_passthrough_no_ses_support_transition",
        }

    # Radius-aware partial contact (LEVEL path only)
    if support_class is not None:
        if support_class == "LOSS_OF_SUPPORT":
            return {
                "transition_class": TRANSITION_SUPPORT_DROP_LOS,
                "evidence": "radius_support_class",
                "classifier_version": PROFILE_VERSION,
                "ambiguity_reason": None,
            }
        if support_class in ("PARTIAL_SUPPORT", "EDGE_OR_SPARSE_SUPPORT"):
            return {
                "transition_class": TRANSITION_RADIUS_PARTIAL_CONTACT,
                "evidence": "radius_support_class",
                "classifier_version": PROFILE_VERSION,
                "ambiguity_reason": None,
            }

    # SES event-based classification
    if event_kind == "LEVEL":
        return {
            "transition_class": TRANSITION_SMOOTH_PATCH_TRAVERSAL,
            "evidence": "ses_event_level",
            "classifier_version": PROFILE_VERSION,
            "ambiguity_reason": None,
        }
    if event_kind == "MICRO_UPHILL":
        return {
            "transition_class": TRANSITION_MICRORELIEF_STEP,
            "evidence": "ses_event_micro_uphill",
            "classifier_version": PROFILE_VERSION,
            "ambiguity_reason": None,
        }
    if event_kind == "LARGE_UPHILL_BLOCKED":
        return {
            "transition_class": TRANSITION_LEDGE_BLOCK,
            "evidence": "ses_event_large_uphill",
            "classifier_version": PROFILE_VERSION,
            "ambiguity_reason": None,
        }
    if event_kind == "MICRO_DOWNHILL_INELASTIC":
        return {
            "transition_class": TRANSITION_MICRORELIEF_STEP,
            "evidence": "ses_event_micro_downhill",
            "classifier_version": PROFILE_VERSION,
            "ambiguity_reason": None,
        }
    if event_kind == "LARGE_DOWNHILL_SUPPORT_LOST":
        return {
            "transition_class": TRANSITION_SUPPORT_DROP_LOS,
            "evidence": "ses_event_large_downhill",
            "classifier_version": PROFILE_VERSION,
            "ambiguity_reason": None,
        }

    # Ambiguous
    return {
        "transition_class": TRANSITION_GEOMETRY_AMBIGUOUS,
        "evidence": "unclassified",
        "classifier_version": PROFILE_VERSION,
        "ambiguity_reason": f"unrecognized event_kind: {event_kind}",
    }


# ---------------------------------------------------------------------------
# Receipt builder
# ---------------------------------------------------------------------------


def build_contract_receipt(
    *,
    tick: int,
    entity_kind: str,
    entity_id: str,
    event_kind: str,
    delta_h: float,
    microrelief_threshold: float,
    accepted: bool,
    block_reason: str | None,
    x_before: float,
    y_before: float,
    x_after: float,
    y_after: float,
    z_before: float,
    z_after: float,
    grounded_before: bool,
    grounded_after: bool,
    work_debit: float,
    kinetic_paid: float,
    support_lost: bool,
    support_class: str | None = None,
    radius_fraction: float | None = None,
    radius_spread: float | None = None,
    high_ring_anomaly: bool = False,
    mutation_provenance: str | None = None,
    pe_authority: str = PE_AUTHORITY_SES_DDA,
    ses_legacy_decision: str | None = None,
    transition_source: str = TRANSITION_SOURCE_PATH_GATE,
    event_kinds: list[str] | None = None,
    support_class_tick: int | None = None,
    support_loss_source: str | None = None,
    cell: list[int] | None = None,
    pose_committed: bool | None = None,
) -> dict[str, Any]:
    """Build a researcher-only SES decomposition contract receipt."""
    pe_authority = validate_pe_authority(pe_authority)
    if transition_source not in TRANSITION_SOURCES:
        raise ValueError(f"unknown transition_source: {transition_source!r}")
    key = application_key(tick, entity_kind, entity_id, transition_source)
    taxonomy = classify_transition_taxonomy(
        event_kind=event_kind,
        delta_h=delta_h,
        microrelief_threshold=microrelief_threshold,
        support_class=support_class,
        radius_fraction=radius_fraction,
        radius_spread=radius_spread,
        high_ring_anomaly=high_ring_anomaly,
        mutation_provenance=mutation_provenance,
    )

    return {
        "receipt_kind": RECEIPT_KIND,
        "tick": int(tick),
        "entity_kind": str(entity_kind),
        "entity_id": str(entity_id),
        "profile_version": PROFILE_VERSION,
        "stage_alias": STAGE_ALIAS,
        "classifier_version": PROFILE_VERSION,
        "transition_class": taxonomy["transition_class"],
        "classification_evidence": taxonomy["evidence"],
        "ambiguity_reason": taxonomy["ambiguity_reason"],
        "event_kind": str(event_kind),
        "delta_h": float(delta_h),
        "microrelief_threshold": float(microrelief_threshold),
        "accepted": bool(accepted),
        "block_reason": str(block_reason) if block_reason else None,
        "pose_before": [float(x_before), float(y_before)],
        "pose_after": [float(x_after), float(y_after)],
        "z_before": float(z_before),
        "z_after": float(z_after),
        "grounded_before": bool(grounded_before),
        "grounded_after": bool(grounded_after),
        "work_debit": float(work_debit),
        "kinetic_paid": float(kinetic_paid),
        "support_lost": bool(support_lost),
        "support_class": str(support_class) if support_class else None,
        "radius_fraction": float(radius_fraction) if radius_fraction is not None else None,
        "radius_spread": float(radius_spread) if radius_spread is not None else None,
        "high_ring_anomaly": bool(high_ring_anomaly),
        "mutation_provenance": str(mutation_provenance) if mutation_provenance else None,
        "pe_authority": str(pe_authority),
        "future_intended_authority": PE_AUTHORITY_CONTINUOUS_GRAVITY,
        "future_intended_authority_active": False,
        "energy_authority": RESPONSIBILITY_STAMPS[RESP_ENERGY_AUTHORITY],
        "topology_gate_authority": RESPONSIBILITY_STAMPS[RESP_TOPOLOGY_GATE],
        "mutation_safety_authority": RESPONSIBILITY_STAMPS[RESP_MUTATION_SAFETY],
        "support_loss_authority": RESPONSIBILITY_STAMPS[RESP_SUPPORT_LOSS_AUTHORITY],
        "pose_commit_authority": RESPONSIBILITY_STAMPS[RESP_POSE_COMMIT_AUTHORITY],
        "height_oracle": RESPONSIBILITY_STAMPS[RESP_HEIGHT_ORACLE],
        "radius_classification": RESPONSIBILITY_STAMPS[RESP_RADIUS_CLASSIFICATION],
        "normal": RESPONSIBILITY_STAMPS[RESP_NORMAL],
        "responsibility_stamps": dict(RESPONSIBILITY_STAMPS),
        "support_loss_source": str(support_loss_source) if support_loss_source else None,
        "support_class_tick": int(support_class_tick) if support_class_tick is not None else None,
        "support_class_source": "G2B_ENTITY_CLASS_FROM_LAST_POST_VERTICAL_STEP" if support_class else None,
        "transition_source": str(transition_source),
        "event_kinds": [str(k) for k in (event_kinds or [event_kind])],
        "cell": [int(c) for c in cell] if cell is not None else None,
        "pose_committed": bool(accepted) if pose_committed is None else bool(pose_committed),
        "application_key": key,
        "ses_legacy_decision": str(ses_legacy_decision) if ses_legacy_decision else None,
        "normal_physical_effects_active": False,
        "tangent_gravity_active": False,
        "radius_face_sweep_active": False,
        "continuous_pe_active": False,
        "physics_equivalence_version": "G2C1_BIT_IDENTICAL_V1",
        "dedup_key": key,
        **RESEARCHER_FLAGS,
    }


def application_key(tick: int, entity_kind: str, entity_id: str, source: str) -> str:
    """Stable per-entity-transition-tick key (never Python id())."""
    return f"{int(tick)}:{str(entity_kind)}:{str(entity_id)}:{str(source)}"


def record_contract_receipt(
    world: Any,
    receipt: dict[str, Any],
) -> None:
    """Record a contract receipt into bounded history."""
    st = state_of(world)
    if st is None:
        return False
    key = str(receipt.get("application_key") or receipt.get("dedup_key") or "")
    tick = int(receipt.get("tick", 0))
    if st.applied_keys_tick != tick:
        st.applied_keys_tick = tick
        st.applied_keys = set()
    if key and key in st.applied_keys:
        # ONE_PE_AUTHORITY_PER_ENTITY_TRANSITION_TICK: never record twice.
        _inc(st, "duplicate_application_key_suppressed")
        return False
    if key:
        st.applied_keys.add(key)
    st.last_receipt = receipt
    st.history.append(receipt)
    lim = int(st.config.history_limit)
    if len(st.history) > lim:
        st.history = st.history[-lim:]
    _inc(st, "receipts_emitted")

    cls = receipt.get("transition_class")
    ek = str(receipt.get("event_kind") or "")
    if cls == TRANSITION_SMOOTH_PATCH_TRAVERSAL:
        _inc(st, "level")
    elif cls == TRANSITION_MICRORELIEF_STEP:
        if ek == SES_EVENT_MICRO_DOWNHILL:
            _inc(st, "micro_downhill")
        elif receipt.get("accepted"):
            _inc(st, "micro_uphill_accepted")
        else:
            _inc(st, "micro_uphill_blocked")
    elif cls == TRANSITION_LEDGE_BLOCK:
        _inc(st, "large_uphill_blocked")
    elif cls == TRANSITION_SUPPORT_DROP_LOS:
        prov = receipt.get("mutation_provenance")
        if prov == "GROUND_LOWERED":
            _inc(st, "ground_lowered_airborne")
        elif receipt.get("support_class") == "LOSS_OF_SUPPORT" and ek == SES_EVENT_LEVEL:
            _inc(st, "radius_loss")
        else:
            _inc(st, "large_downhill_support_lost")
    elif cls == TRANSITION_OCCUPANT_SUPPORT_RISE:
        _inc(st, "support_rise_rejected")
    elif cls == TRANSITION_RADIUS_PARTIAL_CONTACT:
        _inc(st, "radius_partial")
    elif cls == TRANSITION_GEOMETRY_AMBIGUOUS:
        _inc(st, "ambiguous")
        if ek == SES_EVENT_AIRBORNE_PASSTHROUGH:
            _inc(st, "airborne_passthrough")
    return True


def _inc(st: "SesDecompositionContractState", key: str, n: int = 1) -> None:
    st.counters[key] = int(st.counters.get(key, 0)) + int(n)


# ---------------------------------------------------------------------------
# SES seam emitters (READ-ONLY w.r.t. physics; exceptions never escape into SES)
# ---------------------------------------------------------------------------


def decisive_ses_event(plan: dict[str, Any], *, z_before: float) -> dict[str, Any]:
    """Pick the SES event that decided this path, from the SES plan (read-only).

    - rejected -> block_reason (the blocking crossing is the last step);
    - accepted + support_lost -> LARGE_DOWNHILL_SUPPORT_LOST;
    - airborne passthrough -> AIRBORNE_PASSTHROUGH (no SES support transition);
    - accepted with non-LEVEL crossings -> the crossing with the largest |dh|;
    - otherwise LEVEL, delta_h = committed z change (intra-patch CSG surface).
    """
    kinds = [str(k) for k in (plan.get("event_kinds") or [])]
    steps = [s for s in (plan.get("steps") or []) if isinstance(s, dict)]
    z_after = float(plan.get("z", z_before))
    if plan.get("airborne_passthrough"):
        return {"event_kind": SES_EVENT_AIRBORNE_PASSTHROUGH, "delta_h": 0.0, "step_index": None}
    if not plan.get("accepted", True):
        reason = str(plan.get("block_reason") or (kinds[-1] if kinds else SES_EVENT_LEVEL))
        dh = float(steps[-1].get("delta_h", 0.0)) if steps else 0.0
        return {"event_kind": reason, "delta_h": dh, "step_index": len(steps) - 1 if steps else None}
    if plan.get("support_lost"):
        for i, st in enumerate(steps):
            if str(st.get("event_kind")) == SES_EVENT_LARGE_DOWNHILL_SUPPORT_LOST:
                return {"event_kind": SES_EVENT_LARGE_DOWNHILL_SUPPORT_LOST,
                        "delta_h": float(st.get("delta_h", 0.0)), "step_index": i}
        return {"event_kind": SES_EVENT_LARGE_DOWNHILL_SUPPORT_LOST, "delta_h": 0.0, "step_index": None}
    best = None
    for i, st in enumerate(steps):
        k = str(st.get("event_kind"))
        if k == SES_EVENT_LEVEL:
            continue
        dh = float(st.get("delta_h", 0.0))
        if best is None or abs(dh) > abs(best[1]):
            best = (k, dh, i)
    if best is not None:
        return {"event_kind": best[0], "delta_h": best[1], "step_index": best[2]}
    return {"event_kind": SES_EVENT_LEVEL, "delta_h": float(z_after) - float(z_before), "step_index": None}


def _entity_support_class(entity: Any) -> tuple[str | None, float | None, int | None]:
    if entity is None:
        return None, None, None
    try:
        from mechanistic_mind.physical_system.radius_aware_support_points import (
            ENTITY_ATTR_CLASS, ENTITY_ATTR_FRACTION, ENTITY_ATTR_TICK,
        )
    except Exception:  # pragma: no cover
        return None, None, None
    cls = getattr(entity, ENTITY_ATTR_CLASS, None)
    frac = getattr(entity, ENTITY_ATTR_FRACTION, None)
    tk = getattr(entity, ENTITY_ATTR_TICK, None)
    return (
        str(cls) if cls else None,
        float(frac) if frac is not None else None,
        int(tk) if tk is not None else None,
    )


def emit_path_gate_contract_receipt(
    world: Any,
    config: Any,
    *,
    plan: dict[str, Any],
    entity: Any,
    entity_kind: str,
    entity_id: str,
    tick: int,
    x0: float,
    y0: float,
    z0: float,
    grounded_before: bool,
    microrelief_threshold: float,
) -> dict[str, Any] | None:
    """Exactly one contract receipt per SES path-gate evaluation. Reads plan + entity only."""
    if not ses_decomposition_contract_active_on_world(world, config):
        return None
    st = state_of(world)
    try:
        dec = decisive_ses_event(plan, z_before=float(z0))
        sc, frac, sct = _entity_support_class(entity)
        ek = str(dec["event_kind"])
        loss_src = None
        if bool(plan.get("support_lost")):
            loss_src = "SES_DDA"
        elif ek == SES_EVENT_LEVEL and sc == "LOSS_OF_SUPPORT":
            loss_src = "G2B_RADIUS"
        receipt = build_contract_receipt(
            tick=int(tick),
            entity_kind=str(entity_kind),
            entity_id=str(entity_id),
            event_kind=ek,
            delta_h=float(dec["delta_h"]),
            microrelief_threshold=float(microrelief_threshold),
            accepted=bool(plan.get("accepted", True)),
            block_reason=plan.get("block_reason"),
            x_before=float(x0),
            y_before=float(y0),
            x_after=float(getattr(entity, "x", x0)),
            y_after=float(getattr(entity, "y", y0)),
            z_before=float(z0),
            z_after=float(getattr(entity, "z", z0) or 0.0),
            grounded_before=bool(grounded_before),
            grounded_after=bool(getattr(entity, "grounded", True)),
            work_debit=float(plan.get("work_debit") or 0.0),
            kinetic_paid=float(plan.get("kinetic_paid") or 0.0),
            support_lost=bool(plan.get("support_lost")),
            support_class=sc,
            radius_fraction=frac,
            pe_authority=st.config.pe_authority if st is not None else PE_AUTHORITY_SES_DDA,
            ses_legacy_decision=plan.get("block_reason") or ("ACCEPT" if plan.get("accepted", True) else "REJECT"),
            transition_source=TRANSITION_SOURCE_PATH_GATE,
            event_kinds=list(plan.get("event_kinds") or []),
            support_class_tick=sct,
            support_loss_source=loss_src,
            pose_committed=bool(plan.get("accepted", True)),
        )
        record_contract_receipt(world, receipt)
        return receipt
    except Exception as exc:  # contract must never alter SES outcome
        if st is not None:
            _inc(st, "contract_emission_errors")
            st.last_error = f"{type(exc).__name__}:{exc}"
        return None


def emit_mutation_contract_receipts(
    world: Any,
    config: Any,
    *,
    provenance: str,
    cell: tuple[int, int] | list[int],
    rows: list[dict[str, Any]],
    elevation_before: float | None,
    elevation_after: float,
    microrelief_threshold: float,
    tick: int | None = None,
) -> list[dict[str, Any]]:
    """One receipt per affected occupant for an SES terrain-mutation decision.

    provenance: OCCUPIED_SUPPORT_RISE (grounded occupants; mutation rejected, no pose change)
                GROUND_LOWERED (occupants made airborne; z remains, no snap).
    """
    if not ses_decomposition_contract_active_on_world(world, config):
        return []
    st = state_of(world)
    out: list[dict[str, Any]] = []
    try:
        # Runtime tick of the transfer (plan["tick"]) when provided; world.tick otherwise.
        tick = int(tick) if tick is not None else int(getattr(world, "tick", 0) or 0)
        src = (TRANSITION_SOURCE_SUPPORT_RISE_PREFLIGHT if provenance == "OCCUPIED_SUPPORT_RISE"
               else TRANSITION_SOURCE_GROUND_LOWERED)
        for row in rows:
            ent = row.get("entity")
            z = float(row.get("z", getattr(ent, "z", 0.0) or 0.0))
            x = float(getattr(ent, "x", 0.0) or 0.0)
            y = float(getattr(ent, "y", 0.0) or 0.0)
            dh = (float(elevation_after) - float(elevation_before)) if elevation_before is not None \
                else float(elevation_after) - z
            sc, frac, sct = _entity_support_class(ent)
            rise = provenance == "OCCUPIED_SUPPORT_RISE"
            receipt = build_contract_receipt(
                tick=tick,
                entity_kind=str(row.get("kind") or "object"),
                entity_id=str(row.get("id") or ""),
                event_kind=("OCCUPIED_SUPPORT_RISE_REJECTED" if rise else "GROUND_LOWERED_AIRBORNE_NO_SNAP"),
                delta_h=float(dh),
                microrelief_threshold=float(microrelief_threshold),
                accepted=not rise,
                block_reason="OCCUPIED_SUPPORT_RISE_REJECTED" if rise else None,
                x_before=x, y_before=y, x_after=x, y_after=y,
                z_before=z, z_after=float(getattr(ent, "z", z) or z),
                grounded_before=True,
                grounded_after=bool(getattr(ent, "grounded", True)),
                work_debit=0.0,
                kinetic_paid=0.0,
                support_lost=not rise,
                support_class=sc,
                radius_fraction=frac,
                mutation_provenance=str(provenance),
                pe_authority=st.config.pe_authority if st is not None else PE_AUTHORITY_SES_DDA,
                ses_legacy_decision="MUTATION_REJECTED" if rise else "OCCUPANT_AIRBORNE_NO_SNAP",
                transition_source=src,
                event_kinds=[("OCCUPIED_SUPPORT_RISE_REJECTED" if rise else "GROUND_LOWERED_AIRBORNE_NO_SNAP")],
                support_class_tick=sct,
                support_loss_source=None if rise else "SES_DDA",
                cell=[int(cell[0]), int(cell[1])],
                pose_committed=False,
            )
            if record_contract_receipt(world, receipt):
                out.append(receipt)
    except Exception as exc:  # contract must never alter SES outcome
        if st is not None:
            _inc(st, "contract_emission_errors")
            st.last_error = f"{type(exc).__name__}:{exc}"
    return out


# ---------------------------------------------------------------------------
# Authority anomaly detection (Analyzer + tests)
# ---------------------------------------------------------------------------


def detect_authority_anomalies(receipts: list[dict[str, Any]]) -> dict[str, Any]:
    """Cardinality/authority anomalies over a receipt stream (already deduped or raw)."""
    zero, multi, reserved, dup_key, dup_transition = [], [], [], [], []
    by_key: dict[str, dict[str, Any]] = {}
    by_entity_tick: dict[tuple, set] = {}
    for r in receipts:
        if not isinstance(r, dict):
            continue
        key = str(r.get("application_key") or r.get("dedup_key") or "")
        pe = r.get("pe_authority")
        if pe in (None, ""):
            zero.append(key)
        elif isinstance(pe, (list, tuple, set)) or (isinstance(pe, str) and any(c in pe for c in "|+,")):
            multi.append(key)
        elif pe not in ACTIVE_PE_AUTHORITIES_G2C1:
            reserved.append(key)
        if key in by_key:
            prev = by_key[key]
            if prev == r:
                dup_transition.append(key)
            else:
                dup_key.append(key)
        else:
            by_key[key] = r
        et = (r.get("tick"), r.get("entity_kind"), r.get("entity_id"), r.get("transition_source"))
        by_entity_tick.setdefault(et, set()).add(str(pe))
    conflicting = [list(k) for k, v in by_entity_tick.items() if len(v) > 1]
    return {
        "zero_authority": zero,
        "more_than_one_authority": multi,
        "non_active_authority": reserved,
        "conflicting_authority": conflicting,
        "duplicate_application_key": dup_key,
        "duplicate_transition_receipt": dup_transition,
        "anomaly_count": len(zero) + len(multi) + len(reserved) + len(conflicting) + len(dup_key) + len(dup_transition),
    }


# ---------------------------------------------------------------------------
# Serialization / catalog / overlay
# ---------------------------------------------------------------------------


def serialize_state(st: SesDecompositionContractState | None) -> dict[str, Any] | None:
    if st is None:
        return None
    # Minimal: mechanism/profile, PE authority, classifier version (inside config) and
    # continuity counters. Receipt history / last receipt are derived researcher caches
    # (already exported via capture event_refs) and are NOT serialized (no replay source).
    return {
        "schema": STATE_SCHEMA,
        "config": st.config.to_dict(),
        "counters": dict(st.counters),
        "researcher_only": True,
    }


def restore_state(
    world: Any, data: dict[str, Any] | None, config: Any,
) -> SesDecompositionContractState | None:
    if not ses_decomposition_contract_is_active(config):
        world.ses_decomposition_contract_state = None
        return None
    if not isinstance(data, dict) or not data:
        return ensure_ses_decomposition_contract_for_runtime(world, config)
    if str(data.get("schema")) != STATE_SCHEMA:
        raise ValueError(f"unknown ses_decomposition_contract state schema: {data.get('schema')}")
    raw_cfg = data.get("config")
    if raw_cfg is None:
        cur = getattr(config, "ses_decomposition_contract", None)
        raw_cfg = cur.to_dict() if cur is not None and hasattr(cur, "to_dict") else None
    cfg = SesDecompositionContractConfig.from_dict(raw_cfg)
    validate_config(cfg)
    # Legacy payloads that still carry history/last_receipt: ignored (never replayed).
    st = SesDecompositionContractState(
        config=cfg,
        last_receipt={},
        history=[],
        counters={**_default_counters(),
                  **{k: int(v) for k, v in dict(data.get("counters") or {}).items()}},
    )
    world.ses_decomposition_contract_state = st
    return st


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "label": "SES Decomposition Contract G2C1",
        "config_path": "ses_decomposition_contract.enabled",
        "enabled": bool(enabled),
        "promotion_class": "EXPERIMENTAL",
        "provenance": "acanthostega_ses_decomposition_contract_g2c1",
        "default_integrated": True,
        "banner": BANNER,
        "analyzer_section": ANALYZER_SECTION,
        "profile_version": PROFILE_VERSION,
        "stage_alias": STAGE_ALIAS,
        "pe_authority": PE_AUTHORITY_SES_DDA,
        "transition_taxonomy_active": True,
        "continuous_pe_active": False,
        "normal_physical_effects_active": False,
        "tangent_gravity_implemented": False,
        "slope_sliding_implemented": False,
        "radius_face_sweep_implemented": False,
        "physics_equivalence_version": "G2C1_BIT_IDENTICAL_V1",
        "scope": {
            "contract_only": True,
            "physics_mutation": False,
            "ses_energy_unchanged": True,
            "g2b_unchanged": True,
        },
        "historical_compatibility": "missing key means contract OFF / parent SES behavior",
    }


def researcher_summary(world: Any) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    return {
        "mechanism": MECHANISM_ID,
        "profile_version": PROFILE_VERSION,
        "stage_alias": STAGE_ALIAS,
        "banner": BANNER,
        "analyzer_section": ANALYZER_SECTION,
        "counters": dict(st.counters),
        "last_receipt": st.last_receipt or None,
        "pe_authority": st.config.pe_authority,
        "classifier_version": st.config.classifier_version,
        "responsibility_stamps": dict(RESPONSIBILITY_STAMPS),
        "reserved_transition_classes": list(RESERVED_TRANSITION_CLASSES),
        "transition_taxonomy": list(TRANSITION_TAXONOMY),
        "transition_taxonomy_active": True,
        "continuous_pe_active": False,
        "normal_physical_effects_active": False,
        "tangent_gravity_implemented": False,
        "radius_face_sweep_implemented": False,
        "physics_equivalence_version": "G2C1_BIT_IDENTICAL_V1",
        "agent_accessible": False,
        "researcher_only": True,
    }


def overlay_payload(world: Any) -> dict[str, Any] | None:
    """Read-only researcher overlay. Must not change physics when disabled/absent."""
    summary = researcher_summary(world)
    if summary is None:
        return None
    last = summary.get("last_receipt") or {}
    return {
        "caption": BANNER,
        "active": summary,
        "transition_class": last.get("transition_class"),
        "pe_authority": last.get("pe_authority"),
        "event_kind": last.get("event_kind"),
        "delta_h": last.get("delta_h"),
        "support_class": last.get("support_class"),
        "ambiguity_reason": last.get("ambiguity_reason"),
        "mutation_provenance": last.get("mutation_provenance"),
        "normal_implies_slope_forces": False,
        "read_only": True,
    }


def status_text() -> str:
    return "\n".join([
        "SES DECOMPOSITION CONTRACT G2C1",
        "PE AUTHORITY: SES DDA",
        "TRANSITION TAXONOMY ACTIVE",
        "PHYSICS OUTPUTS IDENTICAL TO PARENT",
        "NORMAL/TANGENT GRAVITY OFF · NO RADIUS-FACE SWEEP",
    ])
