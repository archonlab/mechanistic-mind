"""Acanthostega PHASE C · G2C2 SES RUNTIME TRANSITION CLASSIFIER V1.

Preset: ACANTHOSTEGA_PHASE_C_SES_RUNTIME_CLASSIFIER
Parent: ACANTHOSTEGA_PHASE_C_SES_DECOMPOSITION_CONTRACT
Mechanism: ses_runtime_transition_classifier
Profile: SES_RUNTIME_TRANSITION_CLASSIFIER_V1
Stage alias: G2C2_SES_RUNTIME_TRANSITION_CLASSIFIER

CLASSIFICATION / PROVENANCE / OBSERVABILITY / MIGRATION-READINESS ONLY.
Does NOT change physical outcomes.

G2C2 applies the G2C1 transition taxonomy to authoritative SES runtime transitions.
It labels what SES already decided (proposed vs realized vs blocked).
It does NOT:
  - alter transition acceptance;
  - alter position / velocity / work / PE;
  - alter grounded state / support classification / contacts / sounds / cognition;
  - activate continuous PE, normal forces, tangent gravity, slope sliding, or face-sweep.

PE_AUTHORITY = PE_AUTHORITY_SES_DDA (imported from G2C1; never overridden).
Taxonomy constants are imported from G2C1 — never renamed or duplicated.
CLIFF_NZ_CUTOFF remains reserved: no n_z cutoff evidence exists in current CSG.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from mechanistic_mind.physical_system.ses_decomposition_contract import (
    PE_AUTHORITY_CONTINUOUS_GRAVITY,
    PE_AUTHORITY_SES_DDA,
    TRANSITION_CLIFF_NZ_CUTOFF,
    TRANSITION_GEOMETRY_AMBIGUOUS,
    TRANSITION_LEDGE_BLOCK,
    TRANSITION_MICRORELIEF_STEP,
    TRANSITION_OCCUPANT_SUPPORT_RISE,
    TRANSITION_RADIUS_PARTIAL_CONTACT,
    TRANSITION_SMOOTH_PATCH_TRAVERSAL,
    TRANSITION_SUPPORT_DROP_LOS,
    TRANSITION_TAXONOMY,
    TRANSITION_SOURCE_GROUND_LOWERED,
    TRANSITION_SOURCE_PATH_GATE,
    TRANSITION_SOURCE_SUPPORT_RISE_PREFLIGHT,
    TRANSITION_SOURCES,
    SES_EVENT_AIRBORNE_PASSTHROUGH,
    SES_EVENT_LARGE_DOWNHILL_SUPPORT_LOST,
    SES_EVENT_LARGE_UPHILL_BLOCKED,
    SES_EVENT_LEVEL,
    SES_EVENT_MICRO_DOWNHILL,
    SES_EVENT_MICRO_UPHILL,
    SES_BLOCKED_MICRO_EVENTS,
    CURRENT_PE_AUTHORITY,
    RESERVED_TRANSITION_CLASSES,
    classify_transition_taxonomy,
    decisive_ses_event,
    ses_decomposition_contract_is_active,
    validate_pe_authority,
)
from mechanistic_mind.physical_system.surface_elevation_support import (
    surface_elevation_support_is_active,
)

MECHANISM_ID = "ses_runtime_transition_classifier"
PROFILE_VERSION = "SES_RUNTIME_TRANSITION_CLASSIFIER_V1"
STAGE_ALIAS = "G2C2_SES_RUNTIME_TRANSITION_CLASSIFIER"
STATE_SCHEMA = "SES_RUNTIME_TRANSITION_CLASSIFIER_STATE_V1"
RECEIPT_KIND = "SES_RUNTIME_TRANSITION_CLASSIFICATION"

BANNER = (
    "SES RUNTIME CLASSIFIER · RESEARCHER-ONLY · "
    "PE AUTHORITY: SES DDA · "
    "CLASSIFICATION DOES NOT CONTROL PHYSICS"
)
OVERLAY_CAPTION = BANNER
ANALYZER_SECTION = "SES RUNTIME TRANSITION CLASSIFICATIONS"

# Outcome kinds (proposed vs realized vs non-traversal).
OUTCOME_REALIZED = "REALIZED"
OUTCOME_BLOCKED = "BLOCKED"
OUTCOME_NO_HORIZONTAL = "NO_HORIZONTAL"
OUTCOME_SUPPORT_MUTATION = "SUPPORT_MUTATION"
OUTCOME_AIRBORNE_PASSTHROUGH = "AIRBORNE_PASSTHROUGH"
OUTCOME_SUPPRESSED_STATIONARY = "SUPPRESSED_STATIONARY"

# Explicit precedence (causal specificity). Documented + tested.
# mutation/support rise → blocked ledge → support loss → radius partial
# → discrete microrelief → smooth traversal → ambiguous
PRECEDENCE_ORDER = (
    TRANSITION_OCCUPANT_SUPPORT_RISE,
    TRANSITION_LEDGE_BLOCK,
    TRANSITION_SUPPORT_DROP_LOS,
    TRANSITION_RADIUS_PARTIAL_CONTACT,
    TRANSITION_MICRORELIEF_STEP,
    TRANSITION_SMOOTH_PATCH_TRAVERSAL,
    TRANSITION_GEOMETRY_AMBIGUOUS,
)

NORMAL_PHYSICAL_EFFECTS_ACTIVE = False
TANGENT_GRAVITY_IMPLEMENTED = False
SLOPE_SLIDING_IMPLEMENTED = False
RADIUS_FACE_SWEEP_IMPLEMENTED = False
CONTINUOUS_PE_ACTIVE = False
CLASSIFIER_CONTROLS_PHYSICS = False

HISTORY_LIMIT_DEFAULT = 64
EPS_HORIZONTAL = 1e-12
NOT_AVAILABLE = "NOT_AVAILABLE"

RESEARCHER_FLAGS = {
    "researcher_only": True,
    "agent_accessible": False,
    "semantic_label": False,
    "classification_controls_physics": False,
}


@dataclass
class SesRuntimeTransitionClassifierConfig:
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
            "classifier_controls_physics": False,
            "physics_equivalence_version": "G2C2_BIT_IDENTICAL_TO_G2C1_V1",
            "parent_contract": "ses_decomposition_contract",
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "SesRuntimeTransitionClassifierConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        ver = data.get("profile_version")
        if ver is not None and str(ver) != PROFILE_VERSION:
            raise ValueError(f"unknown ses_runtime_transition_classifier profile: {ver}")
        pe = validate_pe_authority(data.get("pe_authority", PE_AUTHORITY_SES_DDA))
        return cls(
            enabled=bool(data.get("enabled", False)),
            history_limit=int(data.get("history_limit", HISTORY_LIMIT_DEFAULT)),
            pe_authority=pe,
            classifier_version=str(data.get("classifier_version", PROFILE_VERSION)),
        )


def validate_config(cfg: SesRuntimeTransitionClassifierConfig) -> None:
    if not (1 <= int(cfg.history_limit) <= 512):
        raise ValueError("history_limit must be in [1, 512]")
    validate_pe_authority(cfg.pe_authority)


def _line_ok(config: Any) -> bool:
    return config is not None and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"


def ses_runtime_transition_classifier_is_active(config: Any) -> bool:
    if not _line_ok(config):
        return False
    cfg = getattr(config, "ses_runtime_transition_classifier", None)
    if cfg is None or not bool(getattr(cfg, "enabled", False)):
        return False
    # Requires G2C1 contract + SES elevation path (same dependency chain as G2C1).
    return bool(
        ses_decomposition_contract_is_active(config)
        and surface_elevation_support_is_active(config)
    )


def ses_runtime_transition_classifier_active_on_world(world: Any, config: Any | None = None) -> bool:
    if config is not None:
        return ses_runtime_transition_classifier_is_active(config) and state_of(world) is not None
    st = state_of(world)
    return st is not None and bool(st.config.enabled)


def set_ses_runtime_transition_classifier(config: Any, enabled: bool) -> None:
    if config is None:
        return
    on = bool(enabled) and _line_ok(config)
    cur = getattr(config, "ses_runtime_transition_classifier", None)
    if cur is None:
        if on:
            config.ses_runtime_transition_classifier = SesRuntimeTransitionClassifierConfig(enabled=True)
        return
    if isinstance(cur, dict):
        cfg = SesRuntimeTransitionClassifierConfig.from_dict(cur)
        cfg.enabled = on
        config.ses_runtime_transition_classifier = cfg
    else:
        cur.enabled = on


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class SesRuntimeTransitionClassifierState:
    config: SesRuntimeTransitionClassifierConfig
    last_receipt: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=lambda: _default_counters())
    # Transient dedup within a tick (not serialized).
    applied_keys_tick: int | None = None
    applied_keys: set = field(default_factory=set)
    # Per-entity last classified tick (serialized minimally for restore dedup continuity).
    last_classified_tick_by_entity: dict[str, int] = field(default_factory=dict)
    last_error: str | None = None
    # Restore mark: suppress false traversal on first post-restore gate call.
    restore_suppress_until_tick: int | None = None


def _default_counters() -> dict[str, int]:
    return {
        "receipts_emitted": 0,
        "realized": 0,
        "blocked": 0,
        "no_horizontal_emitted": 0,
        "stationary_suppressed": 0,
        "smooth_patch_traversal": 0,
        "microrelief_step": 0,
        "ledge_block": 0,
        "support_drop_los": 0,
        "occupant_support_rise": 0,
        "radius_partial_contact": 0,
        "geometry_ambiguous": 0,
        "support_mutation": 0,
        "duplicate_application_key_suppressed": 0,
        "classifier_emission_errors": 0,
        "restore_false_traversal_suppressed": 0,
    }


def state_of(world: Any) -> SesRuntimeTransitionClassifierState | None:
    raw = getattr(world, "ses_runtime_transition_classifier_state", None)
    return raw if isinstance(raw, SesRuntimeTransitionClassifierState) else None


def ensure_ses_runtime_transition_classifier_for_runtime(
    world: Any, config: Any
) -> SesRuntimeTransitionClassifierState | None:
    if not ses_runtime_transition_classifier_is_active(config):
        if state_of(world) is not None:
            world.ses_runtime_transition_classifier_state = None
        return None
    st = state_of(world)
    if st is not None:
        return st
    raw = getattr(config, "ses_runtime_transition_classifier", None)
    cfg = (
        SesRuntimeTransitionClassifierConfig.from_dict(
            raw.to_dict() if hasattr(raw, "to_dict") else raw
        )
        if raw is not None
        else SesRuntimeTransitionClassifierConfig(enabled=True)
    )
    cfg.enabled = True
    validate_config(cfg)
    st = SesRuntimeTransitionClassifierState(config=cfg)
    world.ses_runtime_transition_classifier_state = st
    return st


# ---------------------------------------------------------------------------
# Classification policy (G2C2 runtime layer over G2C1 taxonomy)
# ---------------------------------------------------------------------------


def _horizontal_moved(x0: float, y0: float, x1: float, y1: float) -> bool:
    return math.hypot(float(x1) - float(x0), float(y1) - float(y0)) > EPS_HORIZONTAL


def _entity_support_class(entity: Any) -> tuple[str | None, float | None, int | None]:
    if entity is None:
        return None, None, None
    try:
        from mechanistic_mind.physical_system.radius_aware_support_points import (
            ENTITY_ATTR_CLASS,
            ENTITY_ATTR_FRACTION,
            ENTITY_ATTR_TICK,
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


def _continuous_height_delta(
    world: Any, config: Any, x0: float, y0: float, x1: float, y1: float
) -> float | None:
    """Diagnostic continuous height delta when CSG is active; else None (= NOT_AVAILABLE)."""
    try:
        from mechanistic_mind.physical_system.continuous_surface_geometry import (
            continuous_surface_geometry_is_active,
            sample_surface_geometry,
        )
    except Exception:  # pragma: no cover
        return None
    if not continuous_surface_geometry_is_active(config):
        return None
    try:
        a = sample_surface_geometry(world, float(x0), float(y0), config=config)
        b = sample_surface_geometry(world, float(x1), float(y1), config=config)
        ha = a.get("height") if isinstance(a, dict) else None
        hb = b.get("height") if isinstance(b, dict) else None
        if ha is None or hb is None:
            return None
        return float(hb) - float(ha)
    except Exception:
        return None


def classify_runtime_transition(
    *,
    event_kind: str,
    delta_h: float,
    microrelief_threshold: float,
    accepted: bool,
    support_lost: bool,
    support_class: str | None = None,
    radius_fraction: float | None = None,
    mutation_provenance: str | None = None,
    horizontal_moved: bool = True,
    grounded_before: bool = True,
    grounded_after: bool = True,
) -> dict[str, Any]:
    """Deterministic G2C2 class selection using G2C1 taxonomy + documented precedence.

    Reuses ``classify_transition_taxonomy`` (G2C1) so constants are never renamed.
    Precedence is enforced by feeding the most specific evidence first into G2C1,
    then applying the documented override order when multiple facts co-apply.
    """
    # Build candidate classes from each evidence channel, then pick by PRECEDENCE_ORDER.
    candidates: list[tuple[str, str, str | None]] = []  # (class, evidence, ambiguity)

    if mutation_provenance == "OCCUPIED_SUPPORT_RISE":
        candidates.append((TRANSITION_OCCUPANT_SUPPORT_RISE, "mutation_provenance", None))
    if mutation_provenance == "GROUND_LOWERED":
        candidates.append((TRANSITION_SUPPORT_DROP_LOS, "mutation_provenance", None))

    base = classify_transition_taxonomy(
        event_kind=event_kind,
        delta_h=delta_h,
        microrelief_threshold=microrelief_threshold,
        support_class=support_class,
        radius_fraction=radius_fraction,
        mutation_provenance=None,  # handled above so we can merge with SES facts
    )
    candidates.append((
        str(base["transition_class"]),
        str(base["evidence"]),
        base.get("ambiguity_reason"),
    ))

    # Explicit support-loss from SES or grounded flip (even if event was LEVEL via G2B).
    if support_lost or (grounded_before and not grounded_after):
        candidates.append((TRANSITION_SUPPORT_DROP_LOS, "support_lost_or_grounded_flip", None))

    # Blocked ledge is decisive when SES rejected for large uphill.
    if (not accepted) and event_kind == SES_EVENT_LARGE_UPHILL_BLOCKED:
        candidates.append((TRANSITION_LEDGE_BLOCK, "ses_event_large_uphill", None))
    # Radius face-sweep topology block → existing LEDGE_BLOCK (no new taxonomy class).
    if (not accepted) and event_kind == "RADIUS_FACE_BARRIER":
        candidates.append((TRANSITION_LEDGE_BLOCK, "radius_face_barrier", None))
    # Hard-cap unresolved geometry → GEOMETRY_AMBIGUOUS when plan carries that status.
    if (not accepted) and event_kind == "RADIUS_FACE_BARRIER_HARD_CAP":
        candidates.append((TRANSITION_GEOMETRY_AMBIGUOUS, "face_sweep_hard_cap", "hard_cap_unresolved"))

    # Radius partial only when no higher-precedence SES topology event.
    if support_class in ("PARTIAL_SUPPORT", "EDGE_OR_SPARSE_SUPPORT"):
        candidates.append((TRANSITION_RADIUS_PARTIAL_CONTACT, "radius_support_class", None))

    chosen = None
    for pref in PRECEDENCE_ORDER:
        for c, ev, amb in candidates:
            if c == pref:
                chosen = (c, ev, amb)
                break
        if chosen is not None:
            break
    if chosen is None:
        chosen = (
            TRANSITION_GEOMETRY_AMBIGUOUS,
            "unclassified",
            f"unrecognized evidence for event_kind={event_kind}",
        )

    # CLIFF_NZ_CUTOFF: never emit — no n_z cutoff evidence in current architecture.
    if chosen[0] == TRANSITION_CLIFF_NZ_CUTOFF:
        chosen = (
            TRANSITION_GEOMETRY_AMBIGUOUS,
            "cliff_nz_reserved_no_evidence",
            "CLIFF_NZ_CUTOFF reserved; normal physics inactive; no cutoff evidence",
        )

    return {
        "transition_class": chosen[0],
        "evidence": chosen[1],
        "ambiguity_reason": chosen[2],
        "classifier_version": PROFILE_VERSION,
        "precedence": list(PRECEDENCE_ORDER),
        "horizontal_moved": bool(horizontal_moved),
    }


def application_key(tick: int, entity_kind: str, entity_id: str, source: str) -> str:
    """Stable per-entity-transition-tick key (never Python id())."""
    return f"{int(tick)}:{str(entity_kind)}:{str(entity_id)}:{str(source)}"


def _should_emit_path_gate(
    *,
    horizontal_moved: bool,
    accepted: bool,
    support_lost: bool,
    event_kind: str,
    mutation_provenance: str | None,
    grounded_before: bool,
    grounded_after: bool,
) -> tuple[bool, str]:
    """Stationary / unchanged-support ticks must not spam traversal events."""
    if mutation_provenance is not None:
        return True, OUTCOME_SUPPORT_MUTATION
    if not accepted:
        return True, OUTCOME_BLOCKED
    if support_lost or (grounded_before and not grounded_after):
        return True, OUTCOME_REALIZED if horizontal_moved else OUTCOME_NO_HORIZONTAL
    if event_kind == SES_EVENT_AIRBORNE_PASSTHROUGH:
        if horizontal_moved:
            return True, OUTCOME_AIRBORNE_PASSTHROUGH
        return False, OUTCOME_SUPPRESSED_STATIONARY
    if not horizontal_moved:
        # No horizontal displacement and no support-state transition → suppress.
        if grounded_before == grounded_after and not support_lost:
            return False, OUTCOME_SUPPRESSED_STATIONARY
        return True, OUTCOME_NO_HORIZONTAL
    return True, OUTCOME_REALIZED


def build_classification_receipt(
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
    x_proposed: float,
    y_proposed: float,
    x_realized: float,
    y_realized: float,
    z_before: float,
    z_after: float,
    grounded_before: bool,
    grounded_after: bool,
    work_debit: float,
    kinetic_paid: float,
    support_lost: bool,
    support_class: str | None = None,
    radius_fraction: float | None = None,
    mutation_provenance: str | None = None,
    pe_authority: str = PE_AUTHORITY_SES_DDA,
    transition_source: str = TRANSITION_SOURCE_PATH_GATE,
    event_kinds: list[str] | None = None,
    support_class_tick: int | None = None,
    continuous_height_delta: float | None = None,
    origin_support_height: float | None = None,
    destination_support_height: float | None = None,
    cell: list[int] | None = None,
    outcome: str = OUTCOME_REALIZED,
) -> dict[str, Any]:
    pe_authority = validate_pe_authority(pe_authority)
    if transition_source not in TRANSITION_SOURCES:
        raise ValueError(f"unknown transition_source: {transition_source!r}")
    horizontal_moved = _horizontal_moved(x_before, y_before, x_proposed, y_proposed)
    taxonomy = classify_runtime_transition(
        event_kind=event_kind,
        delta_h=delta_h,
        microrelief_threshold=microrelief_threshold,
        accepted=accepted,
        support_lost=support_lost,
        support_class=support_class,
        radius_fraction=radius_fraction,
        mutation_provenance=mutation_provenance,
        horizontal_moved=horizontal_moved,
        grounded_before=grounded_before,
        grounded_after=grounded_after,
    )
    key = application_key(tick, entity_kind, entity_id, transition_source)
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
        "precedence": taxonomy["precedence"],
        "outcome": str(outcome),
        "event_kind": str(event_kind),
        "event_kinds": [str(k) for k in (event_kinds or [event_kind])],
        "delta_h": float(delta_h),
        "ses_dda_elevation_delta": float(delta_h),
        "microrelief_threshold": float(microrelief_threshold),
        "accepted": bool(accepted),
        "blocked": not bool(accepted),
        "block_reason": str(block_reason) if block_reason else None,
        "origin": [float(x_before), float(y_before)],
        "proposed_destination": [float(x_proposed), float(y_proposed)],
        "realized_destination": [float(x_realized), float(y_realized)],
        "z_before": float(z_before),
        "z_after": float(z_after),
        "origin_support_height": (
            float(origin_support_height) if origin_support_height is not None else NOT_AVAILABLE
        ),
        "destination_support_height": (
            float(destination_support_height)
            if destination_support_height is not None
            else NOT_AVAILABLE
        ),
        "continuous_height_delta": (
            float(continuous_height_delta)
            if continuous_height_delta is not None
            else NOT_AVAILABLE
        ),
        "grounded_before": bool(grounded_before),
        "grounded_after": bool(grounded_after),
        "work_debit": float(work_debit),
        "kinetic_paid": float(kinetic_paid),
        "support_lost": bool(support_lost),
        "support_class": str(support_class) if support_class else None,
        "support_class_tick": int(support_class_tick) if support_class_tick is not None else None,
        "radius_fraction": float(radius_fraction) if radius_fraction is not None else None,
        "mutation_provenance": str(mutation_provenance) if mutation_provenance else None,
        "pe_authority": str(pe_authority),
        "future_intended_authority": PE_AUTHORITY_CONTINUOUS_GRAVITY,
        "future_intended_authority_active": False,
        "transition_source": str(transition_source),
        "cell": [int(c) for c in cell] if cell is not None else None,
        "application_key": key,
        "dedup_key": key,
        "normal_physical_effects_active": False,
        "tangent_gravity_active": False,
        "radius_face_sweep_active": False,
        "continuous_pe_active": False,
        "classifier_controls_physics": False,
        "physics_equivalence_version": "G2C2_BIT_IDENTICAL_TO_G2C1_V1",
        "reserved_transition_classes": list(RESERVED_TRANSITION_CLASSES),
        **RESEARCHER_FLAGS,
    }


def record_classification_receipt(world: Any, receipt: dict[str, Any]) -> bool:
    st = state_of(world)
    if st is None:
        return False
    key = str(receipt.get("application_key") or receipt.get("dedup_key") or "")
    tick = int(receipt.get("tick", 0))
    if st.applied_keys_tick != tick:
        st.applied_keys_tick = tick
        st.applied_keys = set()
    if key and key in st.applied_keys:
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
    entity_key = f"{receipt.get('entity_kind')}:{receipt.get('entity_id')}"
    st.last_classified_tick_by_entity[entity_key] = tick

    outcome = str(receipt.get("outcome") or "")
    if outcome == OUTCOME_REALIZED:
        _inc(st, "realized")
    elif outcome == OUTCOME_BLOCKED:
        _inc(st, "blocked")
    elif outcome == OUTCOME_NO_HORIZONTAL:
        _inc(st, "no_horizontal_emitted")
    elif outcome == OUTCOME_SUPPORT_MUTATION:
        _inc(st, "support_mutation")

    cls = receipt.get("transition_class")
    _cls_counter = {
        TRANSITION_SMOOTH_PATCH_TRAVERSAL: "smooth_patch_traversal",
        TRANSITION_MICRORELIEF_STEP: "microrelief_step",
        TRANSITION_LEDGE_BLOCK: "ledge_block",
        TRANSITION_SUPPORT_DROP_LOS: "support_drop_los",
        TRANSITION_OCCUPANT_SUPPORT_RISE: "occupant_support_rise",
        TRANSITION_RADIUS_PARTIAL_CONTACT: "radius_partial_contact",
        TRANSITION_GEOMETRY_AMBIGUOUS: "geometry_ambiguous",
    }.get(cls)
    if _cls_counter:
        _inc(st, _cls_counter)
    return True


def _inc(st: "SesRuntimeTransitionClassifierState", key: str, n: int = 1) -> None:
    st.counters[key] = int(st.counters.get(key, 0)) + int(n)


# ---------------------------------------------------------------------------
# SES seam emitters (READ-ONLY w.r.t. physics)
# ---------------------------------------------------------------------------


def emit_path_gate_classification(
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
    x_proposed: float,
    y_proposed: float,
    z0: float,
    grounded_before: bool,
    microrelief_threshold: float,
) -> dict[str, Any] | None:
    """Exactly one G2C2 classification per SES path-gate evaluation (when emitted).

    Called AFTER SES has committed/reverted pose. Never mutates plan or entity.
    """
    if not ses_runtime_transition_classifier_active_on_world(world, config):
        return None
    st = state_of(world)
    try:
        # Restore guard: do not invent a traversal from pose initialization.
        if st is not None and st.restore_suppress_until_tick is not None:
            if int(tick) <= int(st.restore_suppress_until_tick):
                _inc(st, "restore_false_traversal_suppressed")
                return None
            st.restore_suppress_until_tick = None

        dec = decisive_ses_event(plan, z_before=float(z0))
        sc, frac, sct = _entity_support_class(entity)
        ek = str(dec["event_kind"])
        x_real = float(getattr(entity, "x", x0))
        y_real = float(getattr(entity, "y", y0))
        accepted = bool(plan.get("accepted", True))
        support_lost = bool(plan.get("support_lost"))
        grounded_after = bool(getattr(entity, "grounded", True))
        horizontal = _horizontal_moved(x0, y0, x_proposed, y_proposed)

        emit, outcome = _should_emit_path_gate(
            horizontal_moved=horizontal,
            accepted=accepted,
            support_lost=support_lost,
            event_kind=ek,
            mutation_provenance=None,
            grounded_before=bool(grounded_before),
            grounded_after=grounded_after,
        )
        if not emit:
            if st is not None:
                _inc(st, "stationary_suppressed")
            return None

        # Origin/destination centre support heights from plan steps when available.
        origin_h = None
        dest_h = None
        steps = [s for s in (plan.get("steps") or []) if isinstance(s, dict)]
        if steps:
            first = steps[0]
            last = steps[-1]
            # Crossing steps carry h_from/h_to from classify_elevation_transition.
            if "h_from" in first:
                origin_h = float(first["h_from"])
            if "h_to" in last:
                dest_h = float(last["h_to"])
            elif "h_from" in last:
                dest_h = float(last["h_from"])

        c_delta = _continuous_height_delta(world, config, x0, y0, x_proposed, y_proposed)

        receipt = build_classification_receipt(
            tick=int(tick),
            entity_kind=str(entity_kind),
            entity_id=str(entity_id),
            event_kind=ek,
            delta_h=float(dec["delta_h"]),
            microrelief_threshold=float(microrelief_threshold),
            accepted=accepted,
            block_reason=plan.get("block_reason"),
            x_before=float(x0),
            y_before=float(y0),
            x_proposed=float(x_proposed),
            y_proposed=float(y_proposed),
            x_realized=x_real,
            y_realized=y_real,
            z_before=float(z0),
            z_after=float(getattr(entity, "z", z0) or 0.0),
            grounded_before=bool(grounded_before),
            grounded_after=grounded_after,
            work_debit=float(plan.get("work_debit") or 0.0),
            kinetic_paid=float(plan.get("kinetic_paid") or 0.0),
            support_lost=support_lost,
            support_class=sc,
            radius_fraction=frac,
            pe_authority=st.config.pe_authority if st is not None else PE_AUTHORITY_SES_DDA,
            transition_source=TRANSITION_SOURCE_PATH_GATE,
            event_kinds=list(plan.get("event_kinds") or []),
            support_class_tick=sct,
            continuous_height_delta=c_delta,
            origin_support_height=origin_h,
            destination_support_height=dest_h,
            outcome=outcome,
        )
        # Bounded face-sweep provenance (researcher-only; never controls physics).
        fs = plan.get("face_sweep") if isinstance(plan.get("face_sweep"), dict) else None
        if fs:
            receipt["face_sweep_evidence_source"] = fs.get("evidence_source")
            receipt["face_sweep_evaluation_status"] = fs.get("evaluation_status")
            receipt["face_sweep_blocking_proposal"] = bool(fs.get("blocking_proposal"))
            receipt["face_sweep_starting_penetration"] = fs.get("starting_penetration")
            receipt["face_sweep_work_delta"] = 0.0
            receipt["face_sweep_pe_delta"] = 0.0
        record_classification_receipt(world, receipt)
        return receipt
    except Exception as exc:  # classifier must never alter SES outcome
        if st is not None:
            _inc(st, "classifier_emission_errors")
            st.last_error = f"{type(exc).__name__}:{exc}"
        return None


def emit_mutation_classifications(
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
    """One G2C2 classification per affected occupant for SES terrain-mutation decisions."""
    if not ses_runtime_transition_classifier_active_on_world(world, config):
        return []
    st = state_of(world)
    out: list[dict[str, Any]] = []
    try:
        tick_i = int(tick) if tick is not None else int(getattr(world, "tick", 0) or 0)
        if st is not None and st.restore_suppress_until_tick is not None:
            if tick_i <= int(st.restore_suppress_until_tick):
                _inc(st, "restore_false_traversal_suppressed")
                return []
            st.restore_suppress_until_tick = None
        src = (
            TRANSITION_SOURCE_SUPPORT_RISE_PREFLIGHT
            if provenance == "OCCUPIED_SUPPORT_RISE"
            else TRANSITION_SOURCE_GROUND_LOWERED
        )
        for row in rows:
            ent = row.get("entity")
            z = float(row.get("z", getattr(ent, "z", 0.0) or 0.0))
            x = float(getattr(ent, "x", 0.0) or 0.0)
            y = float(getattr(ent, "y", 0.0) or 0.0)
            dh = (
                (float(elevation_after) - float(elevation_before))
                if elevation_before is not None
                else float(elevation_after) - z
            )
            sc, frac, sct = _entity_support_class(ent)
            rise = provenance == "OCCUPIED_SUPPORT_RISE"
            receipt = build_classification_receipt(
                tick=tick_i,
                entity_kind=str(row.get("kind") or "object"),
                entity_id=str(row.get("id") or ""),
                event_kind=(
                    "OCCUPIED_SUPPORT_RISE_REJECTED" if rise else "GROUND_LOWERED_AIRBORNE_NO_SNAP"
                ),
                delta_h=float(dh),
                microrelief_threshold=float(microrelief_threshold),
                accepted=not rise,
                block_reason="OCCUPIED_SUPPORT_RISE_REJECTED" if rise else None,
                x_before=x,
                y_before=y,
                x_proposed=x,
                y_proposed=y,
                x_realized=x,
                y_realized=y,
                z_before=z,
                z_after=float(getattr(ent, "z", z) or z),
                grounded_before=True,
                grounded_after=bool(getattr(ent, "grounded", True)),
                work_debit=0.0,
                kinetic_paid=0.0,
                support_lost=not rise,
                support_class=sc,
                radius_fraction=frac,
                mutation_provenance=str(provenance),
                pe_authority=st.config.pe_authority if st is not None else PE_AUTHORITY_SES_DDA,
                transition_source=src,
                event_kinds=[
                    "OCCUPIED_SUPPORT_RISE_REJECTED" if rise else "GROUND_LOWERED_AIRBORNE_NO_SNAP"
                ],
                support_class_tick=sct,
                origin_support_height=elevation_before,
                destination_support_height=elevation_after,
                cell=[int(cell[0]), int(cell[1])],
                outcome=OUTCOME_SUPPORT_MUTATION,
            )
            if record_classification_receipt(world, receipt):
                out.append(receipt)
    except Exception as exc:
        if st is not None:
            _inc(st, "classifier_emission_errors")
            st.last_error = f"{type(exc).__name__}:{exc}"
    return out


# ---------------------------------------------------------------------------
# Serialization / catalog / overlay
# ---------------------------------------------------------------------------


def serialize_state(st: SesRuntimeTransitionClassifierState | None) -> dict[str, Any] | None:
    if st is None:
        return None
    # Minimal: config + continuity counters + last_classified_tick map for dedup.
    # History / last_receipt are researcher caches (capture event_refs) — not serialized.
    return {
        "schema": STATE_SCHEMA,
        "config": st.config.to_dict(),
        "counters": dict(st.counters),
        "last_classified_tick_by_entity": {
            str(k): int(v) for k, v in sorted(st.last_classified_tick_by_entity.items())
        },
        "researcher_only": True,
    }


def restore_state(
    world: Any, data: dict[str, Any] | None, config: Any,
) -> SesRuntimeTransitionClassifierState | None:
    if not ses_runtime_transition_classifier_is_active(config):
        world.ses_runtime_transition_classifier_state = None
        return None
    if not isinstance(data, dict) or not data:
        st = ensure_ses_runtime_transition_classifier_for_runtime(world, config)
        if st is not None:
            # Fresh init on G2C2 preset: suppress false traversal on tick-0 gate.
            tick0 = int(getattr(world, "tick", 0) or 0)
            st.restore_suppress_until_tick = tick0
        return st
    if str(data.get("schema")) != STATE_SCHEMA:
        raise ValueError(
            f"unknown ses_runtime_transition_classifier state schema: {data.get('schema')}"
        )
    raw_cfg = data.get("config")
    if raw_cfg is None:
        cur = getattr(config, "ses_runtime_transition_classifier", None)
        raw_cfg = cur.to_dict() if cur is not None and hasattr(cur, "to_dict") else None
    cfg = SesRuntimeTransitionClassifierConfig.from_dict(raw_cfg)
    validate_config(cfg)
    st = SesRuntimeTransitionClassifierState(
        config=cfg,
        last_receipt={},
        history=[],
        counters={
            **_default_counters(),
            **{k: int(v) for k, v in dict(data.get("counters") or {}).items()},
        },
        last_classified_tick_by_entity={
            str(k): int(v)
            for k, v in dict(data.get("last_classified_tick_by_entity") or {}).items()
        },
    )
    # Suppress false first-tick traversal after restore (pose init ≠ traversal).
    tick_now = int(getattr(world, "tick", 0) or 0)
    st.restore_suppress_until_tick = tick_now
    world.ses_runtime_transition_classifier_state = st
    return st


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "label": "SES Runtime Transition Classifier G2C2",
        "config_path": "ses_runtime_transition_classifier.enabled",
        "enabled": bool(enabled),
        "promotion_class": "EXPERIMENTAL",
        "provenance": "acanthostega_ses_runtime_transition_classifier_g2c2",
        "default_integrated": True,
        "banner": BANNER,
        "analyzer_section": ANALYZER_SECTION,
        "profile_version": PROFILE_VERSION,
        "stage_alias": STAGE_ALIAS,
        "pe_authority": PE_AUTHORITY_SES_DDA,
        "transition_taxonomy_active": True,
        "classifier_controls_physics": False,
        "continuous_pe_active": False,
        "normal_physical_effects_active": False,
        "tangent_gravity_implemented": False,
        "slope_sliding_implemented": False,
        "radius_face_sweep_implemented": False,
        "physics_equivalence_version": "G2C2_BIT_IDENTICAL_TO_G2C1_V1",
        "scope": {
            "classification_only": True,
            "physics_mutation": False,
            "ses_energy_unchanged": True,
            "g2c1_unchanged": True,
            "g2b_unchanged": True,
            "entities": ["body", "object"],
            "free_objects": True,
            "bodies": True,
        },
        "historical_compatibility": "missing key means classifier OFF / parent G2C1 behavior",
    }


def researcher_summary(world: Any) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    last = st.last_receipt or {}
    return {
        "mechanism": MECHANISM_ID,
        "profile_version": PROFILE_VERSION,
        "stage_alias": STAGE_ALIAS,
        "banner": BANNER,
        "analyzer_section": ANALYZER_SECTION,
        "counters": dict(st.counters),
        "last_receipt": last or None,
        "latest_transition_class": last.get("transition_class"),
        "latest_accepted": last.get("accepted"),
        "latest_blocked": last.get("blocked"),
        "latest_origin": last.get("origin"),
        "latest_proposed_destination": last.get("proposed_destination"),
        "latest_realized_destination": last.get("realized_destination"),
        "pe_authority": st.config.pe_authority,
        "classifier_version": st.config.classifier_version,
        "transition_taxonomy": list(TRANSITION_TAXONOMY),
        "reserved_transition_classes": list(RESERVED_TRANSITION_CLASSES),
        "precedence": list(PRECEDENCE_ORDER),
        "classifier_controls_physics": False,
        "continuous_pe_active": False,
        "normal_physical_effects_active": False,
        "tangent_gravity_implemented": False,
        "radius_face_sweep_implemented": False,
        "physics_equivalence_version": "G2C2_BIT_IDENTICAL_TO_G2C1_V1",
        "agent_accessible": False,
        "researcher_only": True,
    }


def overlay_payload(world: Any) -> dict[str, Any] | None:
    summary = researcher_summary(world)
    if summary is None:
        return None
    last = summary.get("last_receipt") or {}
    return {
        "caption": BANNER,
        "active": summary,
        "transition_class": last.get("transition_class"),
        "accepted": last.get("accepted"),
        "blocked": last.get("blocked"),
        "origin": last.get("origin"),
        "proposed_destination": last.get("proposed_destination"),
        "realized_destination": last.get("realized_destination"),
        "pe_authority": last.get("pe_authority") or summary.get("pe_authority"),
        "classifier_version": summary.get("classifier_version"),
        "classifier_controls_physics": False,
        "read_only": True,
    }


def status_text() -> str:
    return "\n".join([
        "SES RUNTIME CLASSIFIER · RESEARCHER-ONLY",
        "PE AUTHORITY: SES DDA",
        "CLASSIFICATION DOES NOT CONTROL PHYSICS",
    ])
