"""Acanthostega Beta 4 · Detached material amount-scaled collision radius V1.

Mechanism: detached_material_amount_scaled_collision_radius
Preset: ACANTHOSTEGA_BETA4_DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS
Parent: ACANTHOSTEGA_BETA4_EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT
Profile: DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS_V1

Creation-time quantity∛ scaling of collision_radius for ResourceObjects
spawned by SEPARATE_SURFACE_COLUMN_SLICE under this child preset only.

Does NOT:
  - resize after creation (COMBINE / deposition / ticks)
  - change optical / grasp / interaction radii
  - change K=16 / candidate order / far-SW gap
  - introduce density as a material property
  - resize preset-spawned or legacy objects
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

MECHANISM_ID = "detached_material_amount_scaled_collision_radius"
PROFILE_VERSION = "DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS_V1"
STATE_SCHEMA = "DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS_STATE_V1"
RECEIPT_KIND = "DETACHED_MATERIAL_SIZE_GEOMETRY"
GEOMETRY_MODEL = "BOUNDED_QUANTITY_CBRT_REF_SCALING_DETACHED_CREATION_ONLY"
RADIUS_AUTHORITY = "SERIALIZED_COLLISION_RADIUS"
SCALING_EXPONENT = 1.0 / 3.0
QUANTITY_REFERENCE = 1.0
RADIUS_REFERENCE = 0.25
MIN_RADIUS = 0.08
MAX_RADIUS = 0.25

BANNER = (
    "DETACHED MATERIAL AMOUNT-SCALED COLLISION RADIUS V1\n"
    "CREATION-TIME ONLY\n"
    "r = clamp(0.25 × quantity^(1/3), 0.08, 0.25)\n"
    "SERIALIZED RADIUS\n"
    "NO POST-CREATION RESIZE\n"
    "OPTICAL / GRASP GEOMETRY UNCHANGED"
)

RESEARCHER_FLAGS = {"researcher_only": True, "agent_accessible": False}

CLAMP_SCALED = "SCALED_FROM_QUANTITY"
CLAMP_MIN = "CLAMPED_MIN"
CLAMP_MAX = "CLAMPED_MAX"
CLAMP_REFERENCE = "REFERENCE_RADIUS"
SCOPE_SCALED = "SCALED_FROM_QUANTITY"
SCOPE_LEGACY = "LEGACY_FIXED_RADIUS"
SCOPE_OUT = "OUT_OF_SCOPE_FIXED_RADIUS"
INVALID_QUANTITY = "INVALID_QUANTITY_REJECTED"

R_INVALID_QUANTITY = "INVALID_DETACHED_QUANTITY_FOR_RADIUS"

HISTORY_LIMIT_DEFAULT = 64


@dataclass(frozen=True)
class DetachedMaterialSizeGeometryProfile:
    """Authoritative creation-time radius profile (immutable constants)."""

    quantity_ref: float = QUANTITY_REFERENCE
    radius_ref: float = RADIUS_REFERENCE
    radius_min: float = MIN_RADIUS
    radius_max: float = MAX_RADIUS
    exponent: float = SCALING_EXPONENT
    profile_version: str = PROFILE_VERSION
    geometry_model: str = GEOMETRY_MODEL

    def to_dict(self) -> dict[str, Any]:
        return {
            "quantity_ref": float(self.quantity_ref),
            "radius_ref": float(self.radius_ref),
            "radius_min": float(self.radius_min),
            "radius_max": float(self.radius_max),
            "exponent": float(self.exponent),
            "profile_version": str(self.profile_version),
            "geometry_model": str(self.geometry_model),
            "radius_authority": RADIUS_AUTHORITY,
            "size_mutable_after_creation": False,
            "optical_radius_changed": False,
            "amount_authority": "quantity",
        }


DEFAULT_PROFILE = DetachedMaterialSizeGeometryProfile()


@dataclass(frozen=True)
class RadiusDerivation:
    quantity: float
    quantity_ref: float
    radius_ref: float
    exponent: float
    raw_radius: float
    radius_min: float
    radius_max: float
    final_radius: float
    clamp_status: str
    profile_version: str
    valid: bool
    rejection_reason: str | None = None
    geometry_model: str = GEOMETRY_MODEL
    scope_classification: str = SCOPE_SCALED

    def to_dict(self) -> dict[str, Any]:
        return {
            "quantity": float(self.quantity) if math.isfinite(self.quantity) else None,
            "quantity_ref": float(self.quantity_ref),
            "radius_ref": float(self.radius_ref),
            "exponent": float(self.exponent),
            "raw_radius": float(self.raw_radius) if math.isfinite(self.raw_radius) else None,
            "radius_min": float(self.radius_min),
            "radius_max": float(self.radius_max),
            "final_radius": float(self.final_radius) if math.isfinite(self.final_radius) else None,
            "clamp_status": str(self.clamp_status),
            "profile_version": str(self.profile_version),
            "geometry_model": str(self.geometry_model),
            "scope_classification": str(self.scope_classification),
            "valid": bool(self.valid),
            "rejection_reason": self.rejection_reason,
            "radius_authority": RADIUS_AUTHORITY,
            "size_derived_at_creation": True,
            "size_mutable_after_creation": False,
            "optical_radius_unchanged": True,
            "post_creation_resizing_disabled": True,
            "researcher_only": True,
            "agent_accessible": False,
        }


def derive_detached_material_collision_radius(
    quantity: float,
    profile: DetachedMaterialSizeGeometryProfile | None = None,
) -> RadiusDerivation:
    """Pure, deterministic creation-time radius from detached quantity.

    Independent of object ID, rendering, optical radius, mass, and semantic identity.
    Invalid (non-finite / non-positive) quantity → valid=False (no fabricated r_min).
    """
    prof = profile or DEFAULT_PROFILE
    q_ref = float(prof.quantity_ref)
    r_ref = float(prof.radius_ref)
    r_min = float(prof.radius_min)
    r_max = float(prof.radius_max)
    exp = float(prof.exponent)

    try:
        q = float(quantity)
    except (TypeError, ValueError):
        q = float("nan")

    if not math.isfinite(q) or q <= 0.0:
        return RadiusDerivation(
            quantity=q if math.isfinite(q) else float("nan"),
            quantity_ref=q_ref,
            radius_ref=r_ref,
            exponent=exp,
            raw_radius=float("nan"),
            radius_min=r_min,
            radius_max=r_max,
            final_radius=float("nan"),
            clamp_status=INVALID_QUANTITY,
            profile_version=str(prof.profile_version),
            valid=False,
            rejection_reason=R_INVALID_QUANTITY,
            geometry_model=str(prof.geometry_model),
            scope_classification=INVALID_QUANTITY,
        )

    if not math.isfinite(q_ref) or q_ref <= 0.0:
        raise ValueError("quantity_ref must be finite and positive")
    if not math.isfinite(r_ref) or r_ref <= 0.0:
        raise ValueError("radius_ref must be finite and positive")
    if not math.isfinite(exp) or exp <= 0.0:
        raise ValueError("exponent must be finite and positive")
    if r_min <= 0.0 or r_max < r_min:
        raise ValueError("radius bounds invalid")

    ratio = q / q_ref
    raw = r_ref * (ratio ** exp)
    if not math.isfinite(raw) or raw <= 0.0:
        return RadiusDerivation(
            quantity=q,
            quantity_ref=q_ref,
            radius_ref=r_ref,
            exponent=exp,
            raw_radius=float(raw) if math.isfinite(raw) else float("nan"),
            radius_min=r_min,
            radius_max=r_max,
            final_radius=float("nan"),
            clamp_status=INVALID_QUANTITY,
            profile_version=str(prof.profile_version),
            valid=False,
            rejection_reason=R_INVALID_QUANTITY,
            geometry_model=str(prof.geometry_model),
            scope_classification=INVALID_QUANTITY,
        )

    final = float(min(r_max, max(r_min, raw)))
    if abs(q - q_ref) <= 1e-15 and abs(final - r_ref) <= 1e-15:
        clamp_status = CLAMP_REFERENCE
    elif raw < r_min - 1e-15:
        clamp_status = CLAMP_MIN
    elif raw > r_max + 1e-15:
        clamp_status = CLAMP_MAX
    else:
        clamp_status = CLAMP_SCALED

    return RadiusDerivation(
        quantity=q,
        quantity_ref=q_ref,
        radius_ref=r_ref,
        exponent=exp,
        raw_radius=float(raw),
        radius_min=r_min,
        radius_max=r_max,
        final_radius=float(final),
        clamp_status=clamp_status,
        profile_version=str(prof.profile_version),
        valid=True,
        rejection_reason=None,
        geometry_model=str(prof.geometry_model),
        scope_classification=SCOPE_SCALED,
    )


@dataclass
class DetachedMaterialAmountScaledCollisionRadiusConfig:
    enabled: bool = False
    history_limit: int = HISTORY_LIMIT_DEFAULT

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "history_limit": int(self.history_limit),
            "profile_version": PROFILE_VERSION,
            "geometry_model": GEOMETRY_MODEL,
            "radius_authority": RADIUS_AUTHORITY,
            "quantity_ref": float(QUANTITY_REFERENCE),
            "radius_ref": float(RADIUS_REFERENCE),
            "exponent": float(SCALING_EXPONENT),
            "radius_min": float(MIN_RADIUS),
            "radius_max": float(MAX_RADIUS),
            "size_mutable_after_creation": False,
            "optical_radius_changed": False,
            "combine_resize": False,
            "deposition_resize": False,
            "placement_candidate_count_unchanged": 16,
        }

    @classmethod
    def from_dict(
        cls, data: dict[str, Any] | None
    ) -> "DetachedMaterialAmountScaledCollisionRadiusConfig":
        d = dict(data or {})
        return cls(
            enabled=bool(d.get("enabled", False)),
            history_limit=int(d.get("history_limit", HISTORY_LIMIT_DEFAULT)),
        )


def validate_config(cfg: DetachedMaterialAmountScaledCollisionRadiusConfig) -> None:
    if int(cfg.history_limit) < 1:
        raise ValueError("history_limit must be >= 1")
    if MAX_RADIUS > RADIUS_REFERENCE + 1e-15:
        raise ValueError("r_max must not exceed r_ref (0.25) in V1")


def _line_ok(config: Any) -> bool:
    return (
        config is not None
        and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"
    )


def detached_material_amount_scaled_collision_radius_is_active(config: Any) -> bool:
    if not _line_ok(config):
        return False
    cfg = getattr(config, "detached_material_amount_scaled_collision_radius", None)
    return cfg is not None and bool(getattr(cfg, "enabled", False))


def set_detached_material_amount_scaled_collision_radius(config: Any, enabled: bool) -> None:
    if config is None:
        return
    on = bool(enabled) and _line_ok(config)
    cur = getattr(config, "detached_material_amount_scaled_collision_radius", None)
    if cur is None:
        if on:
            config.detached_material_amount_scaled_collision_radius = (
                DetachedMaterialAmountScaledCollisionRadiusConfig(enabled=True)
            )
        return
    if isinstance(cur, dict):
        cfg = DetachedMaterialAmountScaledCollisionRadiusConfig.from_dict(cur)
        cfg.enabled = on
        config.detached_material_amount_scaled_collision_radius = cfg
    else:
        cur.enabled = on


@dataclass
class DetachedMaterialAmountScaledCollisionRadiusState:
    config: DetachedMaterialAmountScaledCollisionRadiusConfig
    last_step: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    counters: dict[str, int] = field(
        default_factory=lambda: {
            "derivations": 0,
            "scaled": 0,
            "clamped_min": 0,
            "clamped_max": 0,
            "reference": 0,
            "invalid_rejected": 0,
            "objects_created": 0,
        }
    )


def state_of(world: Any) -> DetachedMaterialAmountScaledCollisionRadiusState | None:
    raw = getattr(world, "detached_material_amount_scaled_collision_radius_state", None)
    return raw if isinstance(raw, DetachedMaterialAmountScaledCollisionRadiusState) else None


def ensure_detached_material_amount_scaled_collision_radius_for_runtime(
    world: Any, config: Any
) -> DetachedMaterialAmountScaledCollisionRadiusState | None:
    if not detached_material_amount_scaled_collision_radius_is_active(config):
        if state_of(world) is not None:
            world.detached_material_amount_scaled_collision_radius_state = None
        return None
    st = state_of(world)
    if st is not None:
        return st
    raw = getattr(config, "detached_material_amount_scaled_collision_radius", None)
    cfg = (
        DetachedMaterialAmountScaledCollisionRadiusConfig.from_dict(
            raw.to_dict() if hasattr(raw, "to_dict") else raw
        )
        if raw is not None
        else DetachedMaterialAmountScaledCollisionRadiusConfig(enabled=True)
    )
    cfg.enabled = True
    validate_config(cfg)
    st = DetachedMaterialAmountScaledCollisionRadiusState(config=cfg)
    world.detached_material_amount_scaled_collision_radius_state = st
    return st


def record_size_geometry_receipt(
    world: Any,
    config: Any,
    derivation: RadiusDerivation,
    *,
    object_id: str | None = None,
    transaction_id: str | None = None,
    source_cell: list[int] | tuple[int, int] | None = None,
    creation_tick: int | None = None,
    mass: float | None = None,
    vertical_half_extent: float | None = None,
    optical_radius: float | None = None,
    committed: bool = False,
) -> dict[str, Any]:
    """Researcher-only DETACHED_MATERIAL_SIZE_GEOMETRY receipt."""
    st = ensure_detached_material_amount_scaled_collision_radius_for_runtime(world, config)
    payload = {
        "receipt_kind": RECEIPT_KIND,
        "mechanism": MECHANISM_ID,
        "event_family": RECEIPT_KIND,
        **derivation.to_dict(),
        "object_id": object_id,
        "transaction_id": transaction_id,
        "source_cell": (
            [int(source_cell[0]), int(source_cell[1])] if source_cell is not None else None
        ),
        "creation_tick": int(creation_tick) if creation_tick is not None else None,
        "mass": float(mass) if mass is not None and math.isfinite(float(mass)) else None,
        "vertical_half_extent": (
            float(vertical_half_extent)
            if vertical_half_extent is not None and math.isfinite(float(vertical_half_extent))
            else None
        ),
        "optical_radius": (
            float(optical_radius)
            if optical_radius is not None and math.isfinite(float(optical_radius))
            else None
        ),
        "committed": bool(committed),
        "collision_radius": (
            float(derivation.final_radius) if derivation.valid else None
        ),
    }
    if st is None:
        return payload
    st.counters["derivations"] = int(st.counters.get("derivations", 0)) + 1
    status = derivation.clamp_status
    if not derivation.valid:
        st.counters["invalid_rejected"] = int(st.counters.get("invalid_rejected", 0)) + 1
    elif status == CLAMP_MIN:
        st.counters["clamped_min"] = int(st.counters.get("clamped_min", 0)) + 1
        st.counters["scaled"] = int(st.counters.get("scaled", 0)) + 1
    elif status == CLAMP_MAX:
        st.counters["clamped_max"] = int(st.counters.get("clamped_max", 0)) + 1
        st.counters["scaled"] = int(st.counters.get("scaled", 0)) + 1
    elif status == CLAMP_REFERENCE:
        st.counters["reference"] = int(st.counters.get("reference", 0)) + 1
        st.counters["scaled"] = int(st.counters.get("scaled", 0)) + 1
    else:
        st.counters["scaled"] = int(st.counters.get("scaled", 0)) + 1
    if committed and derivation.valid:
        st.counters["objects_created"] = int(st.counters.get("objects_created", 0)) + 1
    st.last_step = dict(payload)
    st.history.append(dict(payload))
    lim = int(st.config.history_limit)
    if len(st.history) > lim:
        st.history = st.history[-lim:]
    world.last_detached_material_size_geometry = dict(payload)
    return payload


def build_object_size_provenance(derivation: RadiusDerivation) -> dict[str, Any]:
    """Stamp onto ResourceObject.provenance (researcher-only reconstruction)."""
    return {
        "size_geometry_profile": derivation.profile_version,
        "size_geometry_model": derivation.geometry_model,
        "size_geometry_clamp_status": derivation.clamp_status,
        "size_geometry_scope": derivation.scope_classification,
        "size_geometry_quantity": float(derivation.quantity) if derivation.valid else None,
        "size_geometry_raw_radius": float(derivation.raw_radius) if derivation.valid else None,
        "size_geometry_final_radius": float(derivation.final_radius) if derivation.valid else None,
        "size_geometry_quantity_ref": float(derivation.quantity_ref),
        "size_geometry_radius_ref": float(derivation.radius_ref),
        "size_geometry_exponent": float(derivation.exponent),
        "size_mutable_after_creation": False,
        "optical_radius_unchanged": True,
        "researcher_only": True,
    }


def serialize_state(st: Any) -> dict[str, Any] | None:
    if not isinstance(st, DetachedMaterialAmountScaledCollisionRadiusState):
        return None
    return {
        "schema": STATE_SCHEMA,
        "config": st.config.to_dict(),
        "last_step": dict(st.last_step) if st.last_step else {},
        "history": [dict(h) for h in st.history],
        "counters": {k: int(v) for k, v in st.counters.items()},
    }


def restore_state(world: Any, data: dict[str, Any] | None, config: Any) -> Any:
    if not detached_material_amount_scaled_collision_radius_is_active(config):
        world.detached_material_amount_scaled_collision_radius_state = None
        return None
    if not isinstance(data, dict):
        return ensure_detached_material_amount_scaled_collision_radius_for_runtime(
            world, config
        )
    cfg_raw = data.get("config")
    cfg = DetachedMaterialAmountScaledCollisionRadiusConfig.from_dict(
        cfg_raw if isinstance(cfg_raw, dict) else None
    )
    cfg.enabled = True
    validate_config(cfg)
    st = DetachedMaterialAmountScaledCollisionRadiusState(config=cfg)
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
    world.detached_material_amount_scaled_collision_radius_state = st
    return st


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "label": "Detached material amount-scaled collision radius",
        "enabled": bool(enabled),
        "profile_version": PROFILE_VERSION,
        "banner": BANNER,
        "researcher_only": True,
        "agent_accessible": False,
        "arch_stage": "BETA4_DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS",
        "geometry_model": GEOMETRY_MODEL,
        "radius_authority": RADIUS_AUTHORITY,
    }


def researcher_summary(world: Any) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    return {
        "mechanism": MECHANISM_ID,
        "profile_version": PROFILE_VERSION,
        "banner": BANNER,
        "geometry_model": GEOMETRY_MODEL,
        "radius_authority": RADIUS_AUTHORITY,
        "quantity_ref": float(QUANTITY_REFERENCE),
        "radius_ref": float(RADIUS_REFERENCE),
        "exponent": float(SCALING_EXPONENT),
        "radius_min": float(MIN_RADIUS),
        "radius_max": float(MAX_RADIUS),
        "size_mutable_after_creation": False,
        "optical_radius_changed": False,
        "combine_resize": False,
        "deposition_resize": False,
        "counters": {k: int(v) for k, v in st.counters.items()},
        "last_step": dict(st.last_step) if st.last_step else {},
        **RESEARCHER_FLAGS,
    }
