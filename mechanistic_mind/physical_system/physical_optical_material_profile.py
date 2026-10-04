"""Acanthostega O1 · Physical optical material profile V1.

Schema: PHYSICAL_OPTICAL_MATERIAL_PROFILE_V1
Capability: physical_optical_material_profile
Profile: ANONYMOUS_SPECTRAL_REFLECTANCE_MATERIAL_PROFILE_O1_V1
Authority: PHYSICAL_MATERIAL_PROPERTY_NON_SI_NO_LIGHT_TRANSPORT

Attaches anonymous spectral reflectance to material *components* via a
versioned immutable registry. Mixture resolution is quantity-weighted mean of
component reflectance using the existing conserved composition authority.

This slice does **not** implement light sources, transport, surfaces/normals,
organism reception, Observer RGB, or cognition-accessible values. It does not
mutate optical_response, illumination_intensity, mass, quantity, or geometry.

Acoustic LPS also uses six bands; optical_band_* identifiers are a separate
authority and must not be treated as shared frequencies.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any

SCHEMA = "PHYSICAL_OPTICAL_MATERIAL_PROFILE_V1"
CAPABILITY = "physical_optical_material_profile"
PROFILE = "ANONYMOUS_SPECTRAL_REFLECTANCE_MATERIAL_PROFILE_O1_V1"
AUTHORITY = "PHYSICAL_MATERIAL_PROPERTY_NON_SI_NO_LIGHT_TRANSPORT"
MECHANISM_ID = CAPABILITY
REGISTRY_VERSION = PROFILE
MIXTURE_LAW = "QUANTITY_WEIGHTED_MEAN_REFLECTANCE_V1"
OPTICAL_BAND_COUNT = 6
OPTICAL_BAND_IDENTIFIERS = tuple(f"optical_band_{i}" for i in range(OPTICAL_BAND_COUNT))
DERIVATION_TOLERANCE = 1e-12
REFLECTANCE_BOUNDS = (0.0, 1.0)

STATUS_RESOLVED = "PROFILE_RESOLVED"
STATUS_UNKNOWN = "UNKNOWN_PROFILE"
STATUS_INVALID = "INVALID_MATERIAL_COMPOSITION"
STATUS_LEGACY = "LEGACY_FIXED_COMPATIBILITY"

# Reachable Beta 4 terrain / RO components (PSC + spawn). Optical differences
# between components are NOT scientifically established → identical neutral default.
# Values are abstract non-SI; NOT derived from optical_response or Observer RGB.
_NEUTRAL_R = (0.50, 0.50, 0.50, 0.50, 0.50, 0.50)
COMPONENT_REFLECTANCE_O1_V1: dict[str, tuple[float, ...]] = {
    "component_0": _NEUTRAL_R,
    "component_a": _NEUTRAL_R,
    "component_b": _NEUTRAL_R,
}
KNOWN_COMPONENT_IDS = tuple(sorted(COMPONENT_REFLECTANCE_O1_V1.keys()))

COMPONENT_OPTICAL_DISTINCTION = "NOT_SCIENTIFICALLY_ESTABLISHED_NEUTRAL_DEFAULT"

AUTHORITY_FLAGS = {
    "schema": SCHEMA,
    "capability": CAPABILITY,
    "profile": PROFILE,
    "authority": AUTHORITY,
    "registry_version": REGISTRY_VERSION,
    "mixture_law": MIXTURE_LAW,
    "optical_band_count": OPTICAL_BAND_COUNT,
    "optical_band_identifiers": list(OPTICAL_BAND_IDENTIFIERS),
    "optical_bands_share_acoustic_authority": False,
    "si_wavelength_mapping": False,
    "si_radiometry": False,
    "light_transport": False,
    "organism_reception": False,
    "agent_accessible": False,
    "researcher_only": True,
    "behaviorally_dormant_without_light_consumer": True,
    "component_optical_distinction": COMPONENT_OPTICAL_DISTINCTION,
    "not_display_rgb": True,
    "not_optical_response": True,
    "not_illumination_intensity": True,
}

DEFERRED = (
    "absorption_vector",
    "transmission",
    "opacity_path_thickness",
    "emissivity",
    "fluorescence",
    "roughness_specularity",
    "index_of_refraction",
    "polarization",
    "thermal_emission",
    "si_wavelength_centres",
    "rgb_conversion",
)


@dataclass
class PhysicalOpticalMaterialProfileConfig:
    """Fresh default OFF. Missing snapshot field keeps O1 OFF (Tiktaalik unchanged)."""

    enabled: bool = False
    schema: str = SCHEMA
    profile: str = PROFILE
    registry_version: str = REGISTRY_VERSION
    mixture_law: str = MIXTURE_LAW

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "schema": str(self.schema),
            "profile": str(self.profile),
            "registry_version": str(self.registry_version),
            "mixture_law": str(self.mixture_law),
            **AUTHORITY_FLAGS,
            "deferred": list(DEFERRED),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "PhysicalOpticalMaterialProfileConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        return cls(
            enabled=bool(data.get("enabled", False)),
            schema=str(data.get("schema") or SCHEMA),
            profile=str(data.get("profile") or PROFILE),
            registry_version=str(data.get("registry_version") or REGISTRY_VERSION),
            mixture_law=str(data.get("mixture_law") or MIXTURE_LAW),
        )


def physical_optical_material_profile_is_active(config: Any) -> bool:
    if config is None or str(getattr(config, "model_line", "") or "").upper() != "ACANTHOSTEGA":
        return False
    cfg = getattr(config, "physical_optical_material_profile", None)
    return bool(cfg is not None and getattr(cfg, "enabled", False))


def set_physical_optical_material_profile(config: Any, enabled: bool) -> None:
    if config is None:
        return
    on = bool(enabled) and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"
    cur = getattr(config, "physical_optical_material_profile", None)
    if cur is None:
        config.physical_optical_material_profile = PhysicalOpticalMaterialProfileConfig(enabled=on)
    else:
        cur.enabled = on
        cur.schema = SCHEMA
        cur.profile = PROFILE
        cur.registry_version = REGISTRY_VERSION
        cur.mixture_law = MIXTURE_LAW


def physical_optical_material_profile_catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "enabled": bool(enabled),
        "schema": SCHEMA,
        "profile": PROFILE,
        "authority": AUTHORITY,
        "researcher_only": True,
        "agent_accessible": False,
        "light_transport": False,
        "summary": "Anonymous spectral reflectance material profile (O1); dormant without light consumer.",
    }


def registry_digest(registry_version: str = REGISTRY_VERSION) -> str:
    table = _registry_table(registry_version)
    payload = {
        "registry_version": str(registry_version),
        "bands": list(OPTICAL_BAND_IDENTIFIERS),
        "components": {cid: list(table[cid]) for cid in sorted(table)},
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _registry_table(registry_version: str) -> dict[str, tuple[float, ...]]:
    ver = str(registry_version or REGISTRY_VERSION)
    if ver != REGISTRY_VERSION and ver != PROFILE:
        return {}
    return dict(COMPONENT_REFLECTANCE_O1_V1)


def component_profile_reference(
    component_id: str,
    *,
    registry_version: str = REGISTRY_VERSION,
) -> dict[str, Any]:
    """O(1) immutable registry lookup. Does not invent SI wavelengths."""
    cid = str(component_id)
    table = _registry_table(registry_version)
    known = table.get(cid)
    base = {
        "component_id": cid,
        "schema": SCHEMA,
        "profile": PROFILE,
        "registry_version": str(registry_version),
        "authority": AUTHORITY,
        "optical_band_identifiers": list(OPTICAL_BAND_IDENTIFIERS),
        "not_display_rgb": True,
        "not_optical_response": True,
    }
    if known is None:
        return {
            **base,
            "status": STATUS_UNKNOWN,
            "spectral_reflectance": None,
            "source": "UNKNOWN_COMPONENT",
        }
    R = tuple(float(v) for v in known)
    return {
        **base,
        "status": STATUS_RESOLVED,
        "spectral_reflectance": list(R),
        "source": "REGISTRY",
        "component_optical_distinction": COMPONENT_OPTICAL_DISTINCTION,
    }


def _component_rows(composition: Any) -> list[tuple[str, float]]:
    rows: list[tuple[str, float]] = []
    if composition is None:
        return rows
    if isinstance(composition, dict):
        if "composition" in composition and not any(
            k in composition for k in ("component_id", "amount", "quantity_per_area")
        ):
            return _component_rows(composition.get("composition"))
        items = [
            {"component_id": k, "amount": v}
            for k, v in composition.items()
            if k != "composition"
        ]
    else:
        items = list(composition)
    for item in items:
        if isinstance(item, dict):
            cid = str(item.get("component_id") or item.get("id") or "")
            raw = item.get("amount", item.get("quantity_per_area"))
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            cid = str(item[0])
            raw = item[1]
        else:
            cid = str(getattr(item, "component_id", "") or "")
            raw = getattr(item, "amount", None)
            if raw is None:
                raw = getattr(item, "quantity_per_area", None)
        if not cid:
            raise ValueError("missing component id")
        amount = float(raw)
        if not math.isfinite(amount) or amount < 0.0:
            raise ValueError("invalid component amount")
        rows.append((cid, amount))
    return rows


def canonical_amount_totals(composition: Any) -> dict[str, float]:
    """Reuse conserved composition shape: sort ids, fsum duplicates."""
    buckets: dict[str, list[float]] = {}
    for cid, amount in _component_rows(composition):
        buckets.setdefault(cid, []).append(amount)
    return {
        cid: float(math.fsum(buckets[cid]))
        for cid in sorted(buckets)
        if math.fsum(buckets[cid]) > DERIVATION_TOLERANCE
    }


def _clip01(value: float) -> float:
    lo, hi = REFLECTANCE_BOUNDS
    if not math.isfinite(value):
        return float(lo)
    return float(max(lo, min(hi, value)))


def resolve_optical_material_profile(
    composition: Any,
    *,
    registry_version: str = REGISTRY_VERSION,
    legacy_without_composition: bool = False,
) -> dict[str, Any]:
    """Quantity-weighted mixture of component reflectance.

    R_mix[b] = Σ(q_i × R_i[b]) / Σ(q_i)

    Does not mutate composition, mass, quantity, optical_response, or geometry.
    """
    meta = {
        "schema": SCHEMA,
        "capability": CAPABILITY,
        "profile": PROFILE,
        "authority": AUTHORITY,
        "registry_version": str(registry_version),
        "mixture_law": MIXTURE_LAW,
        "optical_band_count": OPTICAL_BAND_COUNT,
        "optical_band_identifiers": list(OPTICAL_BAND_IDENTIFIERS),
        "optical_bands_share_acoustic_authority": False,
        "si_wavelength_mapping": False,
        "si_radiometry": False,
        "light_transport": False,
        "organism_reception": False,
        "not_display_rgb": True,
        "not_optical_response": True,
        "researcher_only": True,
        "agent_accessible": False,
        "registry_digest": registry_digest(registry_version),
        "deferred": list(DEFERRED),
        "component_optical_distinction": COMPONENT_OPTICAL_DISTINCTION,
    }
    if legacy_without_composition and composition is None:
        return {
            **meta,
            "status": STATUS_LEGACY,
            "spectral_reflectance": None,
            "canonical_amounts": {},
            "component_references": [],
            "unknown_component_ids": [],
            "compatibility": STATUS_LEGACY,
            "note": (
                "Legacy object lacks composition provenance; "
                "O1 does not synthesize from optical_response."
            ),
        }
    try:
        totals = canonical_amount_totals(composition)
    except (TypeError, ValueError) as exc:
        return {
            **meta,
            "status": STATUS_INVALID,
            "spectral_reflectance": None,
            "canonical_amounts": {},
            "component_references": [],
            "unknown_component_ids": [],
            "compatibility": STATUS_INVALID,
            "reason": str(exc),
        }
    total_q = float(math.fsum(totals.values())) if totals else 0.0
    if not totals or total_q <= DERIVATION_TOLERANCE or not math.isfinite(total_q):
        return {
            **meta,
            "status": STATUS_INVALID,
            "spectral_reflectance": None,
            "canonical_amounts": {},
            "component_references": [],
            "unknown_component_ids": [],
            "compatibility": STATUS_INVALID,
            "reason": "zero_or_empty_composition",
            "empty_policy": "DO_NOT_FABRICATE_VALID_PROFILE",
        }

    refs: list[dict[str, Any]] = []
    unknown_ids: list[str] = []
    num: list[list[float]] = [[] for _ in range(OPTICAL_BAND_COUNT)]
    den: list[float] = []
    for cid, amount in totals.items():
        ref = component_profile_reference(cid, registry_version=registry_version)
        ref = {**ref, "amount": float(amount)}
        refs.append(ref)
        if ref["status"] != STATUS_RESOLVED or ref.get("spectral_reflectance") is None:
            unknown_ids.append(cid)
            continue
        R = ref["spectral_reflectance"]
        den.append(float(amount))
        for b in range(OPTICAL_BAND_COUNT):
            num[b].append(float(amount) * float(R[b]))

    if unknown_ids:
        return {
            **meta,
            "status": STATUS_UNKNOWN,
            "spectral_reflectance": None,
            "canonical_amounts": {k: float(v) for k, v in totals.items()},
            "component_references": refs,
            "unknown_component_ids": list(unknown_ids),
            "compatibility": STATUS_UNKNOWN,
            "note": "Unknown component profile(s); do not silently substitute.",
        }

    denom = float(math.fsum(den))
    if not math.isfinite(denom) or denom <= DERIVATION_TOLERANCE:
        return {
            **meta,
            "status": STATUS_INVALID,
            "spectral_reflectance": None,
            "canonical_amounts": {k: float(v) for k, v in totals.items()},
            "component_references": refs,
            "unknown_component_ids": [],
            "compatibility": STATUS_INVALID,
            "reason": "invalid_denominator",
        }

    mixed: list[float] = []
    residuals: list[float] = []
    verified = True
    for b in range(OPTICAL_BAND_COUNT):
        raw = float(math.fsum(num[b])) / denom
        clipped = _clip01(raw)
        residual = float(clipped - raw) if math.isfinite(raw) else 0.0
        residuals.append(residual)
        mixed.append(clipped)
        if not math.isfinite(raw) or abs(residual) > DERIVATION_TOLERANCE:
            verified = False

    return {
        **meta,
        "status": STATUS_RESOLVED if verified else STATUS_INVALID,
        "spectral_reflectance": mixed,
        "canonical_amounts": {k: float(v) for k, v in totals.items()},
        "component_references": refs,
        "unknown_component_ids": [],
        "compatibility": STATUS_RESOLVED if verified else STATUS_INVALID,
        "property_derivation_verified": bool(verified),
        "property_derivation_residuals": residuals,
        "total_quantity": float(denom),
    }


def resolve_occupied_interval_profile(
    interval: Any, *, registry_version: str = REGISTRY_VERSION
) -> dict[str, Any]:
    """Read-only: VW1 occupied interval composition → resolved O1 profile."""
    if interval is None:
        return resolve_optical_material_profile(None, registry_version=registry_version)
    if isinstance(interval, dict):
        comp = interval.get("composition")
    else:
        comp = getattr(interval, "composition", None)
    out = resolve_optical_material_profile(comp, registry_version=registry_version)
    out["resolution_target"] = "VW1_OCCUPIED_INTERVAL"
    out["exposed_surface_authority"] = False
    out["light_transport"] = False
    return out


def resolve_resource_object_profile(
    obj: Any, *, registry_version: str = REGISTRY_VERSION
) -> dict[str, Any]:
    if obj is None:
        return resolve_optical_material_profile(
            None, registry_version=registry_version, legacy_without_composition=True
        )
    if isinstance(obj, dict):
        comp = obj.get("composition")
        has_comp_key = "composition" in obj
        optical = obj.get("optical_response")
    else:
        comp = getattr(obj, "composition", None)
        has_comp_key = hasattr(obj, "composition")
        optical = getattr(obj, "optical_response", None)
    if not has_comp_key or comp is None:
        out = resolve_optical_material_profile(
            None, registry_version=registry_version, legacy_without_composition=True
        )
        out["resolution_target"] = "RESOURCE_OBJECT"
        out["legacy_optical_response_present"] = optical is not None
        out["legacy_optical_response_used_for_o1"] = False
        return out
    out = resolve_optical_material_profile(comp, registry_version=registry_version)
    out["resolution_target"] = "RESOURCE_OBJECT"
    out["legacy_optical_response_used_for_o1"] = False
    return out


def researcher_profile_readout(
    composition: Any, *, registry_version: str = REGISTRY_VERSION
) -> dict[str, Any]:
    """Compact researcher-only inspection payload."""
    resolved = resolve_optical_material_profile(composition, registry_version=registry_version)
    return {
        **resolved,
        "label": "MATERIAL PROPERTY ONLY · NO PHYSICAL LIGHT TRANSPORT · NOT DISPLAY RGB",
        "color_swatch": None,
        "feeds_cognition": False,
        "feeds_organism_vision": False,
    }


def coverage_summary(
    *,
    objects: list[Any] | None = None,
    intervals: list[Any] | None = None,
    deposits: list[Any] | None = None,
    registry_version: str = REGISTRY_VERSION,
) -> dict[str, Any]:
    """Analyzer coverage counts — no organism-saw claims."""
    counts = {
        STATUS_RESOLVED: 0,
        STATUS_UNKNOWN: 0,
        STATUS_INVALID: 0,
        STATUS_LEGACY: 0,
    }
    component_hits: dict[str, int] = {cid: 0 for cid in KNOWN_COMPONENT_IDS}
    unknown_component_hits: dict[str, int] = {}

    def _ingest(comp: Any, *, legacy: bool = False) -> None:
        if legacy and comp is None:
            counts[STATUS_LEGACY] += 1
            return
        rep = resolve_optical_material_profile(comp, registry_version=registry_version)
        st = str(rep.get("status") or STATUS_INVALID)
        counts[st] = counts.get(st, 0) + 1
        for cid in (rep.get("canonical_amounts") or {}):
            if cid in component_hits:
                component_hits[cid] += 1
            else:
                unknown_component_hits[cid] = unknown_component_hits.get(cid, 0) + 1

    for obj in objects or []:
        if isinstance(obj, dict):
            if "composition" not in obj:
                _ingest(None, legacy=True)
            else:
                _ingest(obj.get("composition"))
        else:
            if not hasattr(obj, "composition"):
                _ingest(None, legacy=True)
            else:
                _ingest(getattr(obj, "composition", None))
    for it in intervals or []:
        if isinstance(it, dict):
            _ingest(it.get("composition"))
        else:
            _ingest(getattr(it, "composition", None))
    for dep in deposits or []:
        if isinstance(dep, dict):
            _ingest(dep.get("composition"))
        else:
            _ingest(getattr(dep, "composition", None))

    return {
        "schema": SCHEMA,
        "profile": PROFILE,
        "authority": AUTHORITY,
        "researcher_only": True,
        "organism_saw_material": False,
        "exo_interpreted_as_o1": False,
        "status_counts": counts,
        "known_component_coverage": component_hits,
        "unknown_component_hits": unknown_component_hits,
        "registry_version": str(registry_version),
        "registry_digest": registry_digest(registry_version),
        "label": "MATERIAL PROPERTY ONLY · NO PHYSICAL LIGHT TRANSPORT · NOT DISPLAY RGB",
    }


PRIVACY_DENYLIST_TOKENS = (
    CAPABILITY,
    SCHEMA,
    PROFILE,
    AUTHORITY,
    "spectral_reflectance",
    "optical_band_0",
    "optical_band_1",
    "optical_band_2",
    "optical_band_3",
    "optical_band_4",
    "optical_band_5",
    "optical_band_identifiers",
    "PHYSICAL_OPTICAL_MATERIAL_PROFILE",
    "ANONYMOUS_SPECTRAL_REFLECTANCE",
    "PROFILE_RESOLVED",
    "UNKNOWN_PROFILE",
    "INVALID_MATERIAL_COMPOSITION",
    "LEGACY_FIXED_COMPATIBILITY",
    "registry_digest",
    "component_references",
    "mixture_law",
    MIXTURE_LAW,
)
