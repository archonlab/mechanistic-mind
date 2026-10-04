"""Acanthostega Beta 4 · Held deposition radius shrink transaction V1.

Mechanism: held_deposition_radius_shrink_transaction
Preset: ACANTHOSTEGA_BETA4_HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION
Parent: ACANTHOSTEGA_BETA4_HELD_COMBINE_RADIUS_RESIZE_TRANSACTION
Profile: HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION_V1

Extends APPLY_TO_SURFACE / WMT deposition so a partially depleted,
profile-stamped held ResourceObject updates collision_radius from the
exact post-transfer quantity. Growth is out of scope; full exhaustion
removes the object (no r_min survivor). Released survivor PE is
dissipated / non-recoverable (no agent credit).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from mechanistic_mind.physical_system.detached_material_amount_scaled_collision_radius import (
    PROFILE_VERSION as SIZE_GEOMETRY_PROFILE,
    derive_detached_material_collision_radius,
)
from mechanistic_mind.physical_system.explicit_surface_deposition import (
    CANONICAL_DEPOSIT_AMOUNT,
    QUANTITY_EPSILON,
)
from mechanistic_mind.physical_system.physical_body_resource_object_contact import (
    ensure_object_collision_radius,
)

MECHANISM_ID = "held_deposition_radius_shrink_transaction"
PROFILE_VERSION = "HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION_V1"
STATE_SCHEMA = "HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION_STATE_V1"
RECEIPT_KIND = "HELD_DEPOSITION_GEOMETRY_SHRINK"
ANCHOR_POLICY = "HELD_BASE_FEET_SNAP_RETAINED"
PE_LEDGER = "SURVIVOR_GEOMETRY_DISSIPATED_NON_RECOVERABLE"

BANNER = (
    "HELD DEPOSITION RADIUS SHRINK TRANSACTION V1\n"
    "EXPLICIT APPLY_TO_SURFACE ONLY\n"
    "PROFILE-STAMPED SOURCE ONLY\n"
    "HELD BASE ANCHOR\n"
    "PARTIAL SHRINK · FULL EXHAUSTION REMOVES\n"
    "PE DISSIPATED · NO AGENT CREDIT\n"
    "NO IMPULSE · NO IMPACT SOUND\n"
    "NO DEPOSIT COLLISION BODY"
)

RESEARCHER_FLAGS = {"researcher_only": True, "agent_accessible": False}

GEOMETRY_EPS = 1e-12

CLS_FIXED = "SOURCE_FIXED_GEOMETRY_NO_SHRINK"
CLS_NO_CHANGE = "SHRINK_NO_CHANGE_CLAMPED_OR_EQUAL"
CLS_SHRINK_ADMITTED = "SHRINK_ADMITTED"
CLS_COMMITTED = "COMMITTED_SHRINK"
CLS_EXHAUSTED = "SOURCE_EXHAUSTED_OBJECT_REMOVED"
CLS_UNEXPECTED_GROWTH = "REJECTED_UNEXPECTED_GROWTH"
CLS_STALE = "REJECTED_STALE_SHRINK_PLAN"
CLS_INACTIVE = "SHRINK_MECHANISM_INACTIVE"
CLS_INVALID = "REJECTED_INVALID_QUANTITY"

HISTORY_LIMIT_DEFAULT = 64


@dataclass
class HeldDepositionRadiusShrinkTransactionConfig:
    enabled: bool = False
    history_limit: int = HISTORY_LIMIT_DEFAULT

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "history_limit": int(self.history_limit),
            "profile_version": PROFILE_VERSION,
            "anchor_policy": ANCHOR_POLICY,
            "size_geometry_profile_required": SIZE_GEOMETRY_PROFILE,
            "shrink_only": True,
            "growth_implemented": False,
            "deposition_resize": True,
            "combine_resize": False,
            "pe_ledger": PE_LEDGER,
            "released_pe_credited_to_agent": False,
            "global_energy_conservation_claimed": False,
            "shrink_created_impact_sound": False,
            "geometry_conflict_admission": False,
            "geometry_eps": float(GEOMETRY_EPS),
        }

    @classmethod
    def from_dict(
        cls, data: dict[str, Any] | None
    ) -> "HeldDepositionRadiusShrinkTransactionConfig":
        d = dict(data or {})
        return cls(
            enabled=bool(d.get("enabled", False)),
            history_limit=int(d.get("history_limit", HISTORY_LIMIT_DEFAULT)),
        )


def validate_config(cfg: HeldDepositionRadiusShrinkTransactionConfig) -> None:
    if int(cfg.history_limit) < 1:
        raise ValueError("history_limit must be >= 1")


def _line_ok(config: Any) -> bool:
    return (
        config is not None
        and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"
    )


def held_deposition_radius_shrink_transaction_is_active(config: Any) -> bool:
    if not _line_ok(config):
        return False
    cfg = getattr(config, "held_deposition_radius_shrink_transaction", None)
    return cfg is not None and bool(getattr(cfg, "enabled", False))


def set_held_deposition_radius_shrink_transaction(config: Any, enabled: bool) -> None:
    if config is None:
        return
    on = bool(enabled) and _line_ok(config)
    cur = getattr(config, "held_deposition_radius_shrink_transaction", None)
    if cur is None:
        if on:
            config.held_deposition_radius_shrink_transaction = (
                HeldDepositionRadiusShrinkTransactionConfig(enabled=True)
            )
        return
    if isinstance(cur, dict):
        cfg = HeldDepositionRadiusShrinkTransactionConfig.from_dict(cur)
        cfg.enabled = on
        config.held_deposition_radius_shrink_transaction = cfg
    else:
        cur.enabled = on


@dataclass
class HeldDepositionRadiusShrinkTransactionState:
    config: HeldDepositionRadiusShrinkTransactionConfig
    last_step: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    counters: dict[str, int] = field(
        default_factory=lambda: {
            "plans": 0,
            "fixed_no_shrink": 0,
            "no_change": 0,
            "shrink_admitted": 0,
            "committed": 0,
            "exhausted": 0,
            "rejected_stale": 0,
            "rejected_growth": 0,
        }
    )


def state_of(world: Any) -> HeldDepositionRadiusShrinkTransactionState | None:
    raw = getattr(world, "held_deposition_radius_shrink_transaction_state", None)
    return raw if isinstance(raw, HeldDepositionRadiusShrinkTransactionState) else None


def ensure_held_deposition_radius_shrink_transaction_for_runtime(
    world: Any, config: Any
) -> HeldDepositionRadiusShrinkTransactionState | None:
    if not held_deposition_radius_shrink_transaction_is_active(config):
        if state_of(world) is not None:
            world.held_deposition_radius_shrink_transaction_state = None
        return None
    st = state_of(world)
    if st is not None:
        return st
    raw = getattr(config, "held_deposition_radius_shrink_transaction", None)
    cfg = (
        HeldDepositionRadiusShrinkTransactionConfig.from_dict(
            raw.to_dict() if hasattr(raw, "to_dict") else raw
        )
        if raw is not None
        else HeldDepositionRadiusShrinkTransactionConfig(enabled=True)
    )
    cfg.enabled = True
    validate_config(cfg)
    st = HeldDepositionRadiusShrinkTransactionState(config=cfg)
    world.held_deposition_radius_shrink_transaction_state = st
    return st


def source_has_size_geometry_profile(obj: Any) -> bool:
    prov = getattr(obj, "provenance", None) or {}
    if not isinstance(prov, dict):
        return False
    return str(prov.get("size_geometry_profile") or "") == SIZE_GEOMETRY_PROFILE


def gravity_g(config: Any) -> float:
    from mechanistic_mind.physical_system.flat_ground_gravity import (
        GRAVITY_ACCELERATION,
        flat_ground_gravity_is_active,
    )

    if flat_ground_gravity_is_active(config):
        cfg = getattr(config, "flat_ground_gravity", None)
        if cfg is not None:
            return float(getattr(cfg, "g", GRAVITY_ACCELERATION) or GRAVITY_ACCELERATION)
    return float(GRAVITY_ACCELERATION)


def preview_deposition_transfer(quantity_before: float) -> dict[str, Any]:
    """Mirror apply_explicit_surface_deposition transfer law (pure)."""
    q = float(quantity_before)
    if not math.isfinite(q) or q <= QUANTITY_EPSILON:
        return {
            "valid": False,
            "quantity_before": q,
            "transferred": 0.0,
            "quantity_after": q,
            "depleted": False,
        }
    nominal = min(float(CANONICAL_DEPOSIT_AMOUNT), q)
    depleted = (q - nominal) <= QUANTITY_EPSILON
    transferred = q if depleted else nominal
    q_after = 0.0 if depleted else q - transferred
    return {
        "valid": True,
        "quantity_before": float(q),
        "transferred": float(transferred),
        "quantity_after": float(q_after),
        "depleted": bool(depleted),
        "nominal_limit": float(CANONICAL_DEPOSIT_AMOUNT),
    }


def plan_held_deposition_geometry_shrink(
    *,
    world: Any,
    config: Any,
    source: Any,
    body_id: str,
    deposit_id: str | None = None,
) -> dict[str, Any]:
    """Pure admit for deposition geometry. Does not mutate world."""
    ensure_held_deposition_radius_shrink_transaction_for_runtime(world, config)
    st = state_of(world)
    if st is not None:
        st.counters["plans"] = int(st.counters.get("plans", 0)) + 1

    base: dict[str, Any] = {
        "receipt_kind": RECEIPT_KIND,
        "mechanism": MECHANISM_ID,
        "profile_version": PROFILE_VERSION,
        "anchor_policy": ANCHOR_POLICY,
        "pe_ledger": PE_LEDGER,
        "source_id": str(getattr(source, "object_id", "") or "") if source is not None else None,
        "holder_body_id": str(body_id),
        "manipulator_id": "LEFT",
        "deposit_id": deposit_id,
        "impact_sound_emitted": False,
        "impulse_emitted": False,
        "released_pe_credited_to_agent": False,
        "global_energy_conservation_claimed": False,
        "geometry_conflict_admission": False,
        "researcher_only": True,
        "agent_accessible": False,
    }

    if not held_deposition_radius_shrink_transaction_is_active(config):
        return {
            **base,
            "geometry_eligible": False,
            "resize_classification": CLS_INACTIVE,
            "shrink_required": False,
            "admitted": True,
            "status": "SKIPPED",
        }

    if source is None:
        return {
            **base,
            "geometry_eligible": False,
            "resize_classification": CLS_INVALID,
            "shrink_required": False,
            "admitted": False,
            "status": "REJECTED",
            "rejection_reason": CLS_INVALID,
        }

    preview = preview_deposition_transfer(float(getattr(source, "quantity", 0.0) or 0.0))
    if not preview["valid"]:
        return {
            **base,
            "geometry_eligible": source_has_size_geometry_profile(source),
            "resize_classification": CLS_INVALID,
            "shrink_required": False,
            "admitted": False,
            "status": "REJECTED",
            "rejection_reason": CLS_INVALID,
            **{k: preview[k] for k in ("quantity_before", "transferred", "quantity_after", "depleted")},
        }

    mass_before = float(getattr(source, "mass", 0.0) or 0.0)
    q_before = float(preview["quantity_before"])
    transferred = float(preview["transferred"])
    q_after = float(preview["quantity_after"])
    depleted = bool(preview["depleted"])
    mass_after = 0.0 if depleted else mass_before * (q_after / q_before) if q_before > 0 else 0.0

    payload = {
        **base,
        "quantity_before": q_before,
        "quantity_transferred": transferred,
        "quantity_after": q_after,
        "mass_before": mass_before,
        "mass_after": float(mass_after),
        "depleted": depleted,
    }

    if depleted:
        if st is not None:
            st.counters["exhausted"] = int(st.counters.get("exhausted", 0)) + 1
        return {
            **payload,
            "geometry_eligible": source_has_size_geometry_profile(source),
            "geometry_profile": (
                SIZE_GEOMETRY_PROFILE if source_has_size_geometry_profile(source) else None
            ),
            "resize_classification": CLS_EXHAUSTED,
            "shrink_required": False,
            "admitted": True,
            "status": "PLANNED",
            "radius_before": float(ensure_object_collision_radius(source)),
            "released_pe_magnitude": 0.0,
        }

    if not source_has_size_geometry_profile(source):
        if st is not None:
            st.counters["fixed_no_shrink"] = int(st.counters.get("fixed_no_shrink", 0)) + 1
        r = float(ensure_object_collision_radius(source))
        return {
            **payload,
            "geometry_eligible": False,
            "geometry_profile": None,
            "resize_classification": CLS_FIXED,
            "shrink_required": False,
            "admitted": True,
            "status": "PLANNED",
            "radius_before": r,
            "radius_proposed": r,
            "released_pe_magnitude": 0.0,
        }

    r_before = float(ensure_object_collision_radius(source))
    vhe_before = float(
        getattr(source, "vertical_half_extent", None)
        if getattr(source, "vertical_half_extent", None) is not None
        else r_before
    )
    z_before = float(getattr(source, "z", 0.0) or 0.0)
    derivation = derive_detached_material_collision_radius(q_after)
    if not derivation.valid:
        return {
            **payload,
            "geometry_eligible": True,
            "geometry_profile": SIZE_GEOMETRY_PROFILE,
            "resize_classification": CLS_INVALID,
            "shrink_required": True,
            "admitted": False,
            "status": "REJECTED",
            "rejection_reason": CLS_INVALID,
        }

    r_raw = float(derivation.raw_radius)
    r_proposed = float(derivation.final_radius)
    payload.update(
        {
            "geometry_eligible": True,
            "geometry_profile": SIZE_GEOMETRY_PROFILE,
            "radius_before": float(r_before),
            "radius_raw": float(r_raw),
            "radius_proposed": float(r_proposed),
            "vertical_extent_before": float(vhe_before),
            "vertical_extent_proposed": float(r_proposed),
            "base_z_before": float(z_before),
            "base_z_after": float(z_before),
            "centre_z_before": float(z_before) + float(r_before),
            "centre_z_after": float(z_before) + float(r_proposed),
            "delta_r": float(r_before - r_proposed),
            "clamp_status": derivation.clamp_status,
            "gravity": float(gravity_g(config)),
        }
    )

    # Shrink-only: unexpected growth rejects the geometry plan (deposition still
    # should not grow radius under this law). Prefer reject classification.
    if r_proposed > r_before + GEOMETRY_EPS:
        if st is not None:
            st.counters["rejected_growth"] = int(st.counters.get("rejected_growth", 0)) + 1
        return {
            **payload,
            "resize_classification": CLS_UNEXPECTED_GROWTH,
            "shrink_required": True,
            "admitted": False,
            "status": "REJECTED",
            "rejection_reason": CLS_UNEXPECTED_GROWTH,
        }

    if abs(r_proposed - r_before) <= GEOMETRY_EPS:
        if st is not None:
            st.counters["no_change"] = int(st.counters.get("no_change", 0)) + 1
        return {
            **payload,
            "resize_classification": CLS_NO_CHANGE,
            "shrink_required": False,
            "admitted": True,
            "status": "PLANNED",
            "released_pe_magnitude": 0.0,
        }

    delta_r = float(r_before - r_proposed)
    released = float(max(0.0, float(mass_after) * float(gravity_g(config)) * delta_r))
    if st is not None:
        st.counters["shrink_admitted"] = int(st.counters.get("shrink_admitted", 0)) + 1
    return {
        **payload,
        "resize_classification": CLS_SHRINK_ADMITTED,
        "shrink_required": True,
        "admitted": True,
        "status": "PLANNED",
        "released_pe_magnitude": released,
        "energy_classification": PE_LEDGER,
    }


def validate_shrink_commit_preconditions(
    *,
    source: Any,
    geometry_plan: dict[str, Any],
) -> str | None:
    """Return rejection classification if commit must abort before mutation; else None."""
    if not geometry_plan:
        return None
    if geometry_plan.get("depleted") or not geometry_plan.get("shrink_required"):
        return None
    if source is None:
        return CLS_STALE
    if str(getattr(source, "object_id", "") or "") != str(geometry_plan.get("source_id") or ""):
        return CLS_STALE
    if not source_has_size_geometry_profile(source):
        return CLS_STALE
    r_now = float(ensure_object_collision_radius(source))
    if abs(r_now - float(geometry_plan.get("radius_before") or r_now)) > GEOMETRY_EPS:
        return CLS_STALE
    q_now = float(getattr(source, "quantity", 0.0) or 0.0)
    if abs(q_now - float(geometry_plan.get("quantity_before") or q_now)) > GEOMETRY_EPS:
        return CLS_STALE
    z_now = float(getattr(source, "z", 0.0) or 0.0)
    if abs(z_now - float(geometry_plan.get("base_z_before") or z_now)) > GEOMETRY_EPS:
        return CLS_STALE
    return None


def apply_shrink_on_commit(
    *,
    world: Any,
    config: Any,
    source: Any,
    geometry_plan: dict[str, Any],
) -> dict[str, Any]:
    """Apply radius/vhe after successful partial material publish. No work debit."""
    st = ensure_held_deposition_radius_shrink_transaction_for_runtime(world, config)
    cls = str(geometry_plan.get("resize_classification") or "")

    if geometry_plan.get("depleted"):
        rec = {
            **geometry_plan,
            "committed": True,
            "status": "COMMITTED",
            "resize_classification": CLS_EXHAUSTED,
            "shrink_required": False,
            "released_pe_magnitude": 0.0,
            "impact_sound_emitted": False,
            "impulse_emitted": False,
        }
        _record(world, st, rec)
        return rec

    if not geometry_plan.get("shrink_required"):
        rec = {
            **geometry_plan,
            "committed": True,
            "work_debited": 0.0,
            "result": cls,
            "impact_sound_emitted": False,
            "impulse_emitted": False,
            "released_pe_credited_to_agent": False,
        }
        _record(world, st, rec)
        return rec

    r_before = float(geometry_plan.get("radius_before") or ensure_object_collision_radius(source))
    r_after = float(geometry_plan.get("radius_proposed") or r_before)
    z = float(getattr(source, "z", 0.0) or 0.0)
    source.collision_radius = float(r_after)
    source.vertical_half_extent = float(r_after)
    source.z = float(z)

    prov = dict(getattr(source, "provenance", None) or {})
    prov["last_held_deposition_geometry_shrink"] = {
        "profile_version": PROFILE_VERSION,
        "radius_before": float(r_before),
        "radius_after": float(r_after),
        "delta_r": float(r_before) - float(r_after),
        "released_pe_magnitude": float(geometry_plan.get("released_pe_magnitude") or 0.0),
        "pe_ledger": PE_LEDGER,
        "transaction_id": geometry_plan.get("transaction_id"),
        "researcher_only": True,
    }
    source.provenance = prov

    rec = {
        **geometry_plan,
        "committed": True,
        "status": "COMMITTED",
        "resize_classification": CLS_COMMITTED,
        "radius_after": float(r_after),
        "vertical_extent_after": float(r_after),
        "base_z_after": float(z),
        "centre_z_after": float(z) + float(r_after),
        "work_debited": 0.0,
        "released_pe_credited_to_agent": False,
        "global_energy_conservation_claimed": False,
        "energy_classification": PE_LEDGER,
        "impact_sound_emitted": False,
        "impulse_emitted": False,
    }
    if st is not None:
        st.counters["committed"] = int(st.counters.get("committed", 0)) + 1
    _record(world, st, rec)
    return rec


def _record(world: Any, st: Any, rec: dict[str, Any]) -> None:
    world.last_held_deposition_geometry_shrink = dict(rec)
    if st is None:
        return
    st.last_step = dict(rec)
    st.history.append(dict(rec))
    lim = int(st.config.history_limit)
    if len(st.history) > lim:
        st.history = st.history[-lim:]


def serialize_state(st: Any) -> dict[str, Any] | None:
    if not isinstance(st, HeldDepositionRadiusShrinkTransactionState):
        return None
    return {
        "schema": STATE_SCHEMA,
        "config": st.config.to_dict(),
        "last_step": dict(st.last_step) if st.last_step else {},
        "history": [dict(h) for h in st.history],
        "counters": {k: int(v) for k, v in st.counters.items()},
    }


def restore_state(world: Any, data: dict[str, Any] | None, config: Any) -> Any:
    if not held_deposition_radius_shrink_transaction_is_active(config):
        world.held_deposition_radius_shrink_transaction_state = None
        return None
    if not isinstance(data, dict):
        return ensure_held_deposition_radius_shrink_transaction_for_runtime(world, config)
    cfg_raw = data.get("config")
    cfg = HeldDepositionRadiusShrinkTransactionConfig.from_dict(
        cfg_raw if isinstance(cfg_raw, dict) else None
    )
    cfg.enabled = True
    validate_config(cfg)
    st = HeldDepositionRadiusShrinkTransactionState(config=cfg)
    last = data.get("last_step") or {}
    if isinstance(last, dict):
        st.last_step = dict(last)
    hist = data.get("history") or []
    if isinstance(hist, list):
        st.history = [dict(h) for h in hist if isinstance(h, dict)]
    ctr = data.get("counters") or {}
    if isinstance(ctr, dict):
        for k in st.counters:
            if k in ctr:
                st.counters[k] = int(ctr[k])
    world.held_deposition_radius_shrink_transaction_state = st
    return st


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "label": "Held deposition radius shrink transaction",
        "enabled": bool(enabled),
        "profile_version": PROFILE_VERSION,
        "banner": BANNER,
        "researcher_only": True,
        "agent_accessible": False,
        "arch_stage": "BETA4_HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION",
    }


def researcher_summary(world: Any) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    return {
        "mechanism": MECHANISM_ID,
        "profile_version": PROFILE_VERSION,
        "banner": BANNER,
        "anchor_policy": ANCHOR_POLICY,
        "pe_ledger": PE_LEDGER,
        "counters": {k: int(v) for k, v in st.counters.items()},
        "last_step": dict(st.last_step) if st.last_step else {},
        "shrink_created_impact_sound": False,
        "released_pe_credited_to_agent": False,
        "global_energy_conservation_claimed": False,
        **RESEARCHER_FLAGS,
    }
