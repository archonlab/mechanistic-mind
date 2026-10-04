"""Acanthostega Free-Space V1A · Support state + PE authority contract.

Mechanism: free_space_state_and_pe_authority_contract
Preset: ACANTHOSTEGA_BETA4_FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT
Parent: ACANTHOSTEGA_BETA4_HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION
Profile: FREE_SPACE_STATE_PE_AUTHORITY_PROFILE_V1
Receipt: FREE_SPACE_SUPPORT_STATE_V1

Formalizes SUPPORTED / UNSUPPORTED / TERRAIN_INTERSECT / REBOUND classification,
mutually exclusive PE authority, and supported-rest gravity skip on top of
existing FGG semi-implicit integration. Does NOT implement landing contact
episodes, compliance impulse, restitution, or impact acoustics.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

MECHANISM_ID = "free_space_state_and_pe_authority_contract"
PROFILE_VERSION = "FREE_SPACE_STATE_PE_AUTHORITY_PROFILE_V1"
STATE_SCHEMA = "FREE_SPACE_STATE_PE_AUTHORITY_STATE_V1"
RECEIPT_KIND = "FREE_SPACE_SUPPORT_STATE_V1"
ARCHITECTURE_STAGE = "FREE_SPACE_V1A_STATE_AND_PE_AUTHORITY_CONTRACT"

BANNER = (
    "FREE-SPACE V1A · SUPPORT/PE AUTHORITY CONTRACT · "
    "EXISTING FGG FALLING · SUPPORTED REST GRAVITY GATED · "
    "NO LANDING IMPULSE · NO IMPACT SOUND"
)

RESEARCHER_FLAGS = {"researcher_only": True, "agent_accessible": False}

# Support states (repository enum)
STATE_SUPPORTED = "SUPPORTED"
STATE_UNSUPPORTED = "UNSUPPORTED"
STATE_TERRAIN_INTERSECT = "TERRAIN_INTERSECT"
STATE_REBOUND = "REBOUND"  # reserved / inactive under current inelastic clamp
STATE_HELD_CONSTRAINT = "CONSTRAINED_HELD_NOT_INDEPENDENT"
STATE_NOT_APPLICABLE = "NOT_APPLICABLE"

# Transition reasons
REASON_REMAINS_SUPPORTED = "REMAINS_SUPPORTED"
REASON_SUPPORT_LOST_HORIZONTAL_MOTION = "SUPPORT_LOST_HORIZONTAL_MOTION"
REASON_SUPPORT_LOST_RADIUS_CLASS = "SUPPORT_LOST_RADIUS_CLASS"
REASON_SUPPORT_LOST_TERRAIN_MUTATION = "SUPPORT_LOST_TERRAIN_MUTATION"
REASON_RELEASE_TRANSITION = "RELEASE_TRANSITION"
REASON_RESTORE_CLASSIFICATION = "RESTORE_CLASSIFICATION"
REASON_NEWBORN_ELIGIBILITY = "NEWBORN_ELIGIBILITY"
REASON_TERRAIN_INTERSECTION = "TERRAIN_INTERSECTION"
REASON_SUPPORT_ACQUIRED_INELASTIC_CLAMP = "SUPPORT_ACQUIRED_INELASTIC_CLAMP"
REASON_REBOUND = "REBOUND"
REASON_HELD_CONSTRAINT = "HELD_CONSTRAINT"
REASON_NOT_APPLICABLE = "NOT_APPLICABLE"
REASON_UNSUPPORTED_CONTINUES = "UNSUPPORTED_CONTINUES"
REASON_SUPPORTED_REST = "SUPPORTED_REST"

# PE authorities (mutually exclusive per entity/tick)
PE_SUPPORTED_TERRAIN = "PE_AUTHORITY_SUPPORTED_TERRAIN"
PE_UNSUPPORTED_FREE_SPACE = "PE_AUTHORITY_UNSUPPORTED_FREE_SPACE"
PE_HELD_NONE = "PE_AUTHORITY_HELD_NO_INDEPENDENT"
PE_NONE = "PE_AUTHORITY_NONE"

GRAVITY_SKIP_VALID_SUPPORT = "GRAVITY_SKIPPED_VALID_SUPPORT"
GRAVITY_SKIP_HELD = "GRAVITY_SKIPPED_HELD"
GRAVITY_SKIP_NEWBORN = "GRAVITY_SKIPPED_NEWBORN_NOT_ELIGIBLE"
GRAVITY_SKIP_INACTIVE = "GRAVITY_SKIPPED_CONTRACT_INACTIVE"
CLAMP_DISSIPATION_CLASS = "CURRENT_INELASTIC_CLAMP_DISSIPATION"

HISTORY_LIMIT_DEFAULT = 64
EPS = 1e-12

PHYSICAL_STATE_HELD = "HELD"
PHYSICAL_STATE_FREE_STATIC = "FREE_STATIC"
PHYSICAL_STATE_FREE_MOVING = "FREE_MOVING"


@dataclass
class FreeSpaceStateAndPeAuthorityContractConfig:
    enabled: bool = False
    history_limit: int = HISTORY_LIMIT_DEFAULT
    # Reuse FGG grounded tolerance (ε); no unrelated constants.
    rest_eps: float = EPS

    def to_dict(self) -> dict[str, Any]:
        on = bool(self.enabled)
        return {
            "enabled": on,
            "history_limit": int(self.history_limit),
            "rest_eps": float(self.rest_eps),
            "profile_version": PROFILE_VERSION,
            "architecture_stage": ARCHITECTURE_STAGE,
            "receipt_kind": RECEIPT_KIND,
            "landing_contact_fact_implemented": False,
            "vertical_compliance_impulse_implemented": False,
            "rebound_implemented": False,
            "vertical_impact_sound_implemented": False,
            "fgg_integrator_replaced": False,
            "global_energy_conservation_claimed": False,
            "banner": BANNER if on else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "FreeSpaceStateAndPeAuthorityContractConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        ver = data.get("profile_version")
        if ver is not None and str(ver) != PROFILE_VERSION:
            raise ValueError(f"unknown free-space state/PE profile: {ver}")
        return cls(
            enabled=bool(data.get("enabled", False)),
            history_limit=int(data.get("history_limit", HISTORY_LIMIT_DEFAULT)),
            rest_eps=float(data.get("rest_eps", EPS)),
        )


def validate_config(cfg: FreeSpaceStateAndPeAuthorityContractConfig) -> None:
    if int(cfg.history_limit) < 1:
        raise ValueError("history_limit must be >= 1")
    if float(cfg.rest_eps) < 0.0:
        raise ValueError("rest_eps must be >= 0")


def free_space_state_and_pe_authority_contract_is_active(config: Any) -> bool:
    cfg = getattr(config, "free_space_state_and_pe_authority_contract", None)
    if cfg is None:
        return False
    if isinstance(cfg, dict):
        return bool(cfg.get("enabled"))
    return bool(getattr(cfg, "enabled", False))


def set_free_space_state_and_pe_authority_contract(config: Any, enabled: bool) -> None:
    on = bool(enabled)
    cur = getattr(config, "free_space_state_and_pe_authority_contract", None)
    if cur is None or isinstance(cur, dict):
        cfg = FreeSpaceStateAndPeAuthorityContractConfig.from_dict(
            cur if isinstance(cur, dict) else None
        )
        cfg.enabled = on
        config.free_space_state_and_pe_authority_contract = cfg
    else:
        cur.enabled = on


@dataclass
class FreeSpaceStateAndPeAuthorityContractState:
    config: FreeSpaceStateAndPeAuthorityContractConfig
    # entity_id -> last support state string
    last_state_by_entity: dict[str, str] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    last_receipt: dict[str, Any] | None = None
    counters: dict[str, int] = field(
        default_factory=lambda: {
            "receipts": 0,
            "supported_rest_skips": 0,
            "unsupported_integrations": 0,
            "terrain_intersects": 0,
            "support_acquired_clamps": 0,
            "double_pe_violations": 0,
        }
    )


def state_of(world: Any) -> FreeSpaceStateAndPeAuthorityContractState | None:
    return getattr(world, "free_space_state_and_pe_authority_contract_state", None)


def ensure_free_space_state_and_pe_authority_contract_for_runtime(
    world: Any, config: Any
) -> FreeSpaceStateAndPeAuthorityContractState | None:
    if not free_space_state_and_pe_authority_contract_is_active(config):
        return None
    st = state_of(world)
    if st is not None:
        return st
    raw = getattr(config, "free_space_state_and_pe_authority_contract", None)
    cfg = (
        raw
        if isinstance(raw, FreeSpaceStateAndPeAuthorityContractConfig)
        else FreeSpaceStateAndPeAuthorityContractConfig.from_dict(
            raw if isinstance(raw, dict) else None
        )
    )
    cfg.enabled = True
    st = FreeSpaceStateAndPeAuthorityContractState(config=cfg)
    world.free_space_state_and_pe_authority_contract_state = st
    return st


def ground_forces_eligible(entity: Any, *, config: Any | None = None) -> bool:
    """Shared predicate: ground traction/friction may act iff entity is grounded.

    When Free-Space V1A is ON, ``grounded`` is kept coherent with SUPPORTED rest /
    unsupported fall via FGG + this contract. When OFF, legacy ``grounded`` applies.
    """
    return bool(getattr(entity, "grounded", False))


def _eps(config: Any | None) -> float:
    if config is None:
        return EPS
    cfg = getattr(config, "free_space_state_and_pe_authority_contract", None)
    if cfg is None:
        return EPS
    return float(getattr(cfg, "rest_eps", EPS) or EPS)


def is_supported_rest(
    *,
    z: float,
    vz: float,
    support_z: float,
    grounded: bool,
    eps: float,
) -> bool:
    return (
        bool(grounded)
        and abs(float(z) - float(support_z)) <= float(eps)
        and abs(float(vz)) <= float(eps)
    )


def should_skip_gravity_for_supported_rest(
    *,
    z: float,
    vz: float,
    support_z: float,
    grounded: bool,
    config: Any | None,
) -> bool:
    """True when V1A is active and entity begins vertical step at valid supported rest."""
    if not free_space_state_and_pe_authority_contract_is_active(config):
        return False
    return is_supported_rest(
        z=z, vz=vz, support_z=support_z, grounded=grounded, eps=_eps(config)
    )


def classify_after_vertical_step(
    *,
    was_grounded: bool,
    grounded_after: bool,
    landed: bool,
    gravity_applied: bool,
    support_applied: bool,
    z_before: float,
    support_z: float,
    eps: float,
) -> tuple[str, str]:
    """Return (support_state, transition_reason)."""
    if landed and grounded_after:
        return STATE_TERRAIN_INTERSECT, REASON_SUPPORT_ACQUIRED_INELASTIC_CLAMP
    if grounded_after and not gravity_applied:
        return STATE_SUPPORTED, REASON_SUPPORTED_REST
    if grounded_after and was_grounded:
        return STATE_SUPPORTED, REASON_REMAINS_SUPPORTED
    if grounded_after and not was_grounded:
        return STATE_SUPPORTED, REASON_SUPPORT_ACQUIRED_INELASTIC_CLAMP
    if not grounded_after and was_grounded:
        # Below support without free upward snap path leaves unsupported.
        if float(z_before) < float(support_z) - float(eps):
            return STATE_UNSUPPORTED, REASON_UNSUPPORTED_CONTINUES
        return STATE_UNSUPPORTED, REASON_SUPPORT_LOST_HORIZONTAL_MOTION
    return STATE_UNSUPPORTED, REASON_UNSUPPORTED_CONTINUES


def pe_authority_for(
    *,
    support_state: str,
    gravity_applied: bool,
    held: bool = False,
) -> str:
    if held:
        return PE_HELD_NONE
    if support_state == STATE_SUPPORTED and not gravity_applied:
        return PE_SUPPORTED_TERRAIN
    if support_state in (STATE_UNSUPPORTED, STATE_TERRAIN_INTERSECT, STATE_REBOUND):
        return PE_UNSUPPORTED_FREE_SPACE
    if gravity_applied:
        return PE_UNSUPPORTED_FREE_SPACE
    return PE_SUPPORTED_TERRAIN


def record_vertical_contract_receipt(
    world: Any,
    config: Any,
    *,
    tick: int,
    entity_id: str,
    entity_kind: str,
    body_slot: str | None,
    z_before: float,
    vz_before: float,
    z_after: float,
    vz_after: float,
    centre_z_after: float,
    vertical_half_extent: float,
    support_z: float,
    was_grounded: bool,
    grounded_after: bool,
    gravity_applied: bool,
    skip_gravity: bool,
    gravity_skip_reason: str | None,
    support_applied: bool,
    landed: bool,
    support_dissipated: float,
    mass: float,
    vertical_integration_eligible: bool = True,
    vertical_integration_applied: bool = True,
    held: bool = False,
    release_transition: bool = False,
    newborn_creation_tick: int | None = None,
    newborn_eligible: bool | None = None,
    transition_reason_override: str | None = None,
) -> dict[str, Any] | None:
    if not free_space_state_and_pe_authority_contract_is_active(config):
        return None
    st = ensure_free_space_state_and_pe_authority_contract_for_runtime(world, config)
    if st is None:
        return None
    eps = float(st.config.rest_eps)
    if held:
        support_state = STATE_HELD_CONSTRAINT
        reason = REASON_HELD_CONSTRAINT
        pe = PE_HELD_NONE
    else:
        support_state, reason = classify_after_vertical_step(
            was_grounded=was_grounded,
            grounded_after=grounded_after,
            landed=landed,
            gravity_applied=gravity_applied,
            support_applied=support_applied,
            z_before=z_before,
            support_z=support_z,
            eps=eps,
        )
        if transition_reason_override:
            reason = str(transition_reason_override)
        if release_transition:
            reason = REASON_RELEASE_TRANSITION
        pe = pe_authority_for(
            support_state=support_state, gravity_applied=gravity_applied, held=False
        )

    prev = st.last_state_by_entity.get(str(entity_id), STATE_NOT_APPLICABLE)
    st.last_state_by_entity[str(entity_id)] = support_state

    # Mutual exclusion: exactly one PE authority token.
    pe_count = 1 if pe not in (PE_NONE, PE_HELD_NONE) else 0
    if held:
        pe_count = 0
    double_pe = False
    # Supported + gravity_applied would be a double-claim; rest gate must prevent it.
    if support_state == STATE_SUPPORTED and gravity_applied:
        double_pe = True
        st.counters["double_pe_violations"] = int(st.counters.get("double_pe_violations", 0)) + 1

    removed_ke = max(0.0, float(support_dissipated or 0.0)) if (landed or support_applied) else 0.0
    clamp_class = CLAMP_DISSIPATION_CLASS if (landed and removed_ke > 0.0) else None

    if skip_gravity and gravity_skip_reason == GRAVITY_SKIP_VALID_SUPPORT:
        st.counters["supported_rest_skips"] = int(st.counters.get("supported_rest_skips", 0)) + 1
    if gravity_applied:
        st.counters["unsupported_integrations"] = int(
            st.counters.get("unsupported_integrations", 0)
        ) + 1
    if landed:
        st.counters["terrain_intersects"] = int(st.counters.get("terrain_intersects", 0)) + 1
        st.counters["support_acquired_clamps"] = int(
            st.counters.get("support_acquired_clamps", 0)
        ) + 1

    receipt = {
        "receipt_kind": RECEIPT_KIND,
        "tick": int(tick),
        "entity_id": str(entity_id),
        "entity_kind": str(entity_kind),
        "body_slot": body_slot,
        "previous_support_state": prev,
        "support_state": support_state,
        "transition_reason": reason,
        "base_z": float(z_after),
        "base_z_before": float(z_before),
        "centre_z": float(centre_z_after),
        "vertical_half_extent": float(vertical_half_extent),
        "support_height": float(support_z),
        "z_support_separation": float(z_after) - float(support_z),
        "vz_before": float(vz_before),
        "vz_after": float(vz_after),
        "vertical_integration_eligible": bool(vertical_integration_eligible),
        "vertical_integration_applied": bool(vertical_integration_applied),
        "gravity_applied": bool(gravity_applied),
        "gravity_skipped": bool(skip_gravity),
        "gravity_skip_reason": gravity_skip_reason,
        "grounded_rest_tolerance_ok": is_supported_rest(
            z=z_after, vz=vz_after, support_z=support_z, grounded=grounded_after, eps=eps
        ),
        "ground_force_eligibility": bool(grounded_after) and not held,
        "active_pe_authority": pe,
        "active_pe_authority_count": int(pe_count),
        "double_pe_authority": bool(double_pe),
        "terrain_intersection": bool(landed),
        "current_inelastic_clamp": bool(landed or (support_applied and not was_grounded)),
        "clamp_dissipation_class": clamp_class,
        "removed_vertical_ke": float(removed_ke) if clamp_class else 0.0,
        "landing_contact_fact_implemented": False,
        "vertical_compliance_impulse_implemented": False,
        "rebound_implemented": False,
        "vertical_impact_sound_implemented": False,
        "impact_sound_emitted": False,
        "impulse_emitted": False,
        "held_exclusion": bool(held),
        "release_transition": bool(release_transition),
        "newborn_creation_tick": newborn_creation_tick,
        "newborn_eligible": newborn_eligible,
        "mass": float(mass),
        "authoritative": True,
        "derived": False,
        "profile_version": PROFILE_VERSION,
        **RESEARCHER_FLAGS,
    }
    st.counters["receipts"] = int(st.counters.get("receipts", 0)) + 1
    st.last_receipt = receipt
    st.history.append(receipt)
    lim = int(st.config.history_limit)
    if len(st.history) > lim:
        st.history = st.history[-lim:]
    world.last_free_space_support_state = receipt
    return receipt


def note_held_constraint(
    world: Any,
    config: Any,
    *,
    tick: int,
    entity_id: str,
    holder_body_id: str | None,
    z: float,
    vz: float,
    centre_z: float,
    half_extent: float,
) -> dict[str, Any] | None:
    if not free_space_state_and_pe_authority_contract_is_active(config):
        return None
    return record_vertical_contract_receipt(
        world,
        config,
        tick=tick,
        entity_id=entity_id,
        entity_kind="object",
        body_slot=holder_body_id,
        z_before=z,
        vz_before=vz,
        z_after=z,
        vz_after=vz,
        centre_z_after=centre_z,
        vertical_half_extent=half_extent,
        support_z=z,
        was_grounded=False,
        grounded_after=False,
        gravity_applied=False,
        skip_gravity=True,
        gravity_skip_reason=GRAVITY_SKIP_HELD,
        support_applied=False,
        landed=False,
        support_dissipated=0.0,
        mass=float(getattr(world, "_unused", 0.0) or 0.0),
        vertical_integration_eligible=False,
        vertical_integration_applied=False,
        held=True,
    )


def note_support_loss_terrain_mutation(
    world: Any,
    config: Any,
    *,
    tick: int,
    entity_id: str,
    entity_kind: str,
    z: float,
    vz: float,
    support_z_after: float,
    half_extent: float,
) -> dict[str, Any] | None:
    """Record SAME_TICK support loss without vertical integration."""
    if not free_space_state_and_pe_authority_contract_is_active(config):
        return None
    centre = float(z) + float(half_extent)
    return record_vertical_contract_receipt(
        world,
        config,
        tick=int(tick) if tick is not None else -1,
        entity_id=entity_id,
        entity_kind=entity_kind,
        body_slot=None,
        z_before=z,
        vz_before=vz,
        z_after=z,
        vz_after=vz,
        centre_z_after=centre,
        vertical_half_extent=half_extent,
        support_z=support_z_after,
        was_grounded=True,
        grounded_after=False,
        gravity_applied=False,
        skip_gravity=True,
        gravity_skip_reason=None,
        support_applied=False,
        landed=False,
        support_dissipated=0.0,
        mass=1.0,
        vertical_integration_eligible=True,
        vertical_integration_applied=False,
        transition_reason_override=REASON_SUPPORT_LOST_TERRAIN_MUTATION,
    )


def serialize_state(st: FreeSpaceStateAndPeAuthorityContractState | None) -> dict[str, Any] | None:
    if st is None:
        return None
    return {
        "schema": STATE_SCHEMA,
        "config": st.config.to_dict(),
        "last_state_by_entity": dict(st.last_state_by_entity),
        "counters": dict(st.counters),
        "last_receipt": dict(st.last_receipt) if st.last_receipt else None,
        "history": list(st.history),
        "banner": BANNER,
        **RESEARCHER_FLAGS,
    }


def restore_state(
    world: Any, data: dict[str, Any] | None, config: Any
) -> FreeSpaceStateAndPeAuthorityContractState | None:
    if not data or not free_space_state_and_pe_authority_contract_is_active(config):
        return None
    raw_cfg = data.get("config")
    if raw_cfg is None:
        cur = getattr(config, "free_space_state_and_pe_authority_contract", None)
        raw_cfg = cur.to_dict() if cur is not None and hasattr(cur, "to_dict") else None
    cfg = FreeSpaceStateAndPeAuthorityContractConfig.from_dict(raw_cfg)
    cfg.enabled = True
    st = FreeSpaceStateAndPeAuthorityContractState(
        config=cfg,
        last_state_by_entity={
            str(k): str(v) for k, v in dict(data.get("last_state_by_entity") or {}).items()
        },
        history=list(data.get("history") or []),
        last_receipt=dict(data["last_receipt"]) if data.get("last_receipt") else None,
        counters=dict(data.get("counters") or {}),
    )
    world.free_space_state_and_pe_authority_contract_state = st
    return st


def copy_state(
    st: FreeSpaceStateAndPeAuthorityContractState | None,
) -> FreeSpaceStateAndPeAuthorityContractState | None:
    if st is None:
        return None
    return FreeSpaceStateAndPeAuthorityContractState(
        config=FreeSpaceStateAndPeAuthorityContractConfig.from_dict(st.config.to_dict()),
        last_state_by_entity=dict(st.last_state_by_entity),
        history=[dict(r) for r in st.history],
        last_receipt=dict(st.last_receipt) if st.last_receipt else None,
        counters=dict(st.counters),
    )


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "enabled": bool(enabled),
        "profile_version": PROFILE_VERSION,
        "architecture_stage": ARCHITECTURE_STAGE,
        "receipt_kind": RECEIPT_KIND,
        "banner": BANNER if enabled else None,
        "landing_contact_fact_implemented": False,
        "vertical_compliance_impulse_implemented": False,
        "vertical_impact_sound_implemented": False,
        **RESEARCHER_FLAGS,
    }


def researcher_summary(world: Any) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    last = dict(st.last_receipt) if st.last_receipt else None
    return {
        "mechanism": MECHANISM_ID,
        "profile_version": PROFILE_VERSION,
        "architecture_stage": ARCHITECTURE_STAGE,
        "receipt_kind": RECEIPT_KIND,
        "counters": dict(st.counters),
        "last_receipt": last,
        "last_step": last,  # Observer panel alias
        "landing_contact_fact_implemented": False,
        "vertical_compliance_impulse_implemented": False,
        "rebound_implemented": False,
        "vertical_impact_sound_implemented": False,
        "banner": BANNER,
        **RESEARCHER_FLAGS,
    }
