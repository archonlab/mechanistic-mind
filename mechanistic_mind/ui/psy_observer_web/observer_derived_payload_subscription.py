"""P1 Observer derived-payload subscription — researcher delivery only.

Schema: OBSERVER_DERIVED_PAYLOAD_SUBSCRIPTION_V1
Capability: inactive_observer_payload_and_render_suspension
Profile: ACTIVE_CONSUMER_DERIVED_PAYLOAD_GATING_P1_V1
Authority: RESEARCHER_DELIVERY_POLICY_NO_PHYSICAL_EFFECT

Request state is UI/session interest only. Never gates physics, cognition,
O1–O5 authorities, scientific evidence, or Analyzer saved evidence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

SCHEMA = "OBSERVER_DERIVED_PAYLOAD_SUBSCRIPTION_V1"
CAPABILITY = "inactive_observer_payload_and_render_suspension"
PROFILE = "ACTIVE_CONSUMER_DERIVED_PAYLOAD_GATING_P1_V1"
AUTHORITY = "RESEARCHER_DELIVERY_POLICY_NO_PHYSICAL_EFFECT"

# Product IDs (also registered in subscriptions.ALL_PRODUCTS).
PRODUCT_VOLUME_XRAY = "volume_xray"
PRODUCT_SURFACE_LIGHT = "surface_light"
PRODUCT_SELECTED_VISION = "selected_organism_vision_audit"
PRODUCT_HEARING_UI = "hearing_ui"

# Derived payload family ids exposed on the frame.
FAMILY_BASE = "base_compact_frame"
FAMILY_VOLUME = "volume_occupancy_rendering"
FAMILY_SURFACE = "surface_light_rendering"
FAMILY_VISION = "selected_organism_visual_audit"
FAMILY_ACOUSTIC = "acoustic_ui"

OMISSION_NOT_REQUESTED = "NOT_REQUESTED"

# Absent/legacy interest (direct live_frame/world_frame without session interest):
# MAP-only — do not build VOLUME/SURFACE geometry. Explicit products required.
COMPAT_POLICY = "ABSENT_INTEREST_DEFAULTS_MAP_ONLY_NO_VOLUME_SURFACE"

KNOWN_PRODUCTS = frozenset({
    PRODUCT_VOLUME_XRAY,
    PRODUCT_SURFACE_LIGHT,
    PRODUCT_SELECTED_VISION,
    PRODUCT_HEARING_UI,
})

DERIVED_VIEWPORT_PRODUCTS = frozenset({
    PRODUCT_VOLUME_XRAY,
    PRODUCT_SURFACE_LIGHT,
})


@dataclass(frozen=True)
class ResolvedDerivedSubscription:
    """Deterministic resolution of which derived display families to build."""

    schema: str = SCHEMA
    capability: str = CAPABILITY
    profile: str = PROFILE
    authority: str = AUTHORITY
    compat_policy: str = COMPAT_POLICY
    viewport_mode: str = "MAP_2D"
    include_volume: bool = False
    include_surface: bool = False
    include_vision_audit: bool = True  # compact summaries always OK (no central 3D)
    include_acoustic_ui: bool = True
    included_families: tuple[str, ...] = field(default_factory=tuple)
    omitted_families: tuple[str, ...] = field(default_factory=tuple)
    products_requested: tuple[str, ...] = field(default_factory=tuple)
    malformed_ignored: tuple[str, ...] = field(default_factory=tuple)
    interest_present: bool = False

    def as_frame_meta(self, *, runtime_generation: int | None = None) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "capability": self.capability,
            "profile": self.profile,
            "authority": self.authority,
            "compat_policy": self.compat_policy,
            "viewport_mode": self.viewport_mode,
            "interest_present": self.interest_present,
            "products_requested": list(self.products_requested),
            "included_payload_families": list(self.included_families),
            "omitted_payload_families": [
                {"family": f, "reason": OMISSION_NOT_REQUESTED} for f in self.omitted_families
            ],
            "omission_reason_default": OMISSION_NOT_REQUESTED,
            "runtime_generation": runtime_generation,
            "note": (
                "Omitted derived display payload is NOT scientific unavailability. "
                "Physical authorities and full scientific evidence remain unchanged."
            ),
            "analyzer_is_observer_viewport_subscription": False,
        }


def _wants(interest: Any, product: str) -> bool:
    if interest is None:
        return False
    wants = getattr(interest, "wants", None)
    if callable(wants):
        return bool(wants(product))
    products = getattr(interest, "products", None)
    if isinstance(products, (set, frozenset, list, tuple)):
        return product in products
    return False


def resolve_derived_subscription(
    interest: Any = None,
    *,
    explicit_products: Iterable[str] | None = None,
) -> ResolvedDerivedSubscription:
    """Resolve derived payload families from ObserverInterest or explicit product list.

    Rules:
    - MAP (default): no VOLUME, no SURFACE
    - VOLUME: volume yes, surface no (unless also requested)
    - SURFACE: surface yes, volume no (unless also requested)
    - VISION/HEARING compact families do not force central VOLUME/SURFACE
    - Unknown products ignored (fail-safe)
    """
    malformed: list[str] = []
    requested: set[str] = set()

    if explicit_products is not None:
        for p in explicit_products:
            s = str(p)
            if s in KNOWN_PRODUCTS or s in {
                PRODUCT_VOLUME_XRAY,
                PRODUCT_SURFACE_LIGHT,
            }:
                requested.add(s)
            elif s in ("MAP_2D", "map", "world"):
                pass
            elif s in ("VOLUME_XRAY", "VOLUME"):
                requested.add(PRODUCT_VOLUME_XRAY)
            elif s in ("SURFACE_LIGHT", "SURFACE"):
                requested.add(PRODUCT_SURFACE_LIGHT)
            else:
                # Allow subscription products that live in ObserverInterest.ALL_PRODUCTS
                # only when they match our derived ids; else ignore unknown.
                if s not in {
                    "world", "telemetry", "mechanisms", "cognition", "psc", "smc",
                    "historical_sensorimotor_selection", "prediction", "history",
                    "compression", "graphs", "diagnostics", "geometry", "signals",
                    "experimenter", "signal_sensorimotor",
                }:
                    malformed.append(s)

    interest_present = interest is not None
    if interest_present:
        if _wants(interest, PRODUCT_VOLUME_XRAY):
            requested.add(PRODUCT_VOLUME_XRAY)
        if _wants(interest, PRODUCT_SURFACE_LIGHT):
            requested.add(PRODUCT_SURFACE_LIGHT)
        if _wants(interest, PRODUCT_SELECTED_VISION):
            requested.add(PRODUCT_SELECTED_VISION)
        if _wants(interest, PRODUCT_HEARING_UI):
            requested.add(PRODUCT_HEARING_UI)

    include_volume = PRODUCT_VOLUME_XRAY in requested
    include_surface = PRODUCT_SURFACE_LIGHT in requested

    if include_volume and include_surface:
        viewport_mode = "VOLUME_XRAY+SURFACE_LIGHT"
    elif include_volume:
        viewport_mode = "VOLUME_XRAY"
    elif include_surface:
        viewport_mode = "SURFACE_LIGHT"
    else:
        viewport_mode = "MAP_2D"

    included: list[str] = [FAMILY_BASE]
    omitted: list[str] = []
    if include_volume:
        included.append(FAMILY_VOLUME)
    else:
        omitted.append(FAMILY_VOLUME)
    if include_surface:
        included.append(FAMILY_SURFACE)
    else:
        omitted.append(FAMILY_SURFACE)

    # Compact vision/acoustic UI payloads are never forced into central 3D geometry.
    include_vision = True
    include_acoustic = True
    included.append(FAMILY_VISION)
    included.append(FAMILY_ACOUSTIC)

    return ResolvedDerivedSubscription(
        viewport_mode=viewport_mode,
        include_volume=include_volume,
        include_surface=include_surface,
        include_vision_audit=include_vision,
        include_acoustic_ui=include_acoustic,
        included_families=tuple(included),
        omitted_families=tuple(omitted),
        products_requested=tuple(sorted(requested)),
        malformed_ignored=tuple(malformed),
        interest_present=interest_present,
    )


def not_requested_stub(family: str) -> dict[str, Any]:
    """Stub for an omitted derived family (never means scientific unavailable)."""
    return {
        "available": False,
        "status": "OMITTED",
        "omission_reason": OMISSION_NOT_REQUESTED,
        "family": family,
        "schema": SCHEMA,
        "authority": AUTHORITY,
        "scientific_data": "UNCHANGED_NOT_GATED",
        "note": "Derived researcher display payload not requested for this Observer frame.",
    }
