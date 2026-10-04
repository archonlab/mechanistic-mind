"""Acanthostega PHASE C · G2B RADIUS-AWARE SUPPORT POINTS CONSTRAINED HYBRID C⋆ V1.

Preset:     ACANTHOSTEGA_PHASE_C_RADIUS_AWARE_SUPPORT
Parent:     ACANTHOSTEGA_PHASE_C_FREE_OBJECT_STATIC_TRACTION
Mechanism:  radius_aware_support_points
Profile:    RADIUS_AWARE_SUPPORT_POINTS_V1
  (= Hybrid C⋆ / RECOMMENDED_NEXT_SLICE / RADIUS_AWARE_SUPPORT_CONSTRAINED_HYBRID_CSTAR_V1)

Hard contract:
  CENTRE_Z_AUTHORITY = YES          — support_z = h(centre_x, centre_y) only
  RING_CLASSIFICATION_ONLY = YES    — no max/mean/plane/weighted z from ring
  ONE_PE_AUTHORITY = SES_DDA
  NORMAL_PHYSICAL_EFFECTS_ACTIVE = NO
  LEVEL_1_PLANAR_CLASSIFICATION_ONLY
  No pitch/roll, torque, support polygon, coverage-scaled N, N(n_z),
  tangent gravity, slope sliding, excavation, face-sweep, optical R.

Thresholds: docs/ACANTHOSTEGA_RADIUS_AWARE_SUPPORT_POINTS_G2B_THRESHOLDS_ADDENDUM.md
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from mechanistic_mind.physical_system.continuous_surface_geometry import (
    continuous_surface_geometry_is_active,
    sample_surface_geometry,
)
from mechanistic_mind.physical_system.flat_ground_gravity import (
    flat_ground_gravity_is_active,
)
from mechanistic_mind.physical_system.free_resource_object_static_traction_threshold import (
    free_resource_object_static_traction_threshold_is_active,
)
from mechanistic_mind.physical_system.physical_body_resource_object_contact import (
    BODY_CONTACT_RADIUS,
    ensure_object_collision_radius,
)
from mechanistic_mind.physical_system.surface_elevation_support import (
    MICRORELIEF_THRESHOLD,
    surface_elevation_support_is_active,
    surface_support_height,
)
from mechanistic_mind.planet.topology import wrap_coord

MECHANISM_ID = "radius_aware_support_points"
ARCH_STAGE = "G2B_RADIUS_AWARE_SUPPORT_POINTS_CONSTRAINED_HYBRID_CSTAR"
PROFILE_VERSION = "RADIUS_AWARE_SUPPORT_POINTS_V1"
PROFILE_ALIAS_HYBRID_CSTAR = "RADIUS_AWARE_SUPPORT_CONSTRAINED_HYBRID_CSTAR_V1"
STATE_SCHEMA = "RADIUS_AWARE_SUPPORT_POINTS_STATE_V1"
RECEIPT_KIND = "RADIUS_AWARE_SUPPORT_POINTS"
EVENT_CLASSIFY = "RADIUS_SUPPORT_CLASS"
EVENT_LOST = "RADIUS_SUPPORT_LOST"
EVENT_SAMPLE_SET = "RADIUS_SUPPORT_SAMPLE_SET"

BANNER = (
    "RADIUS-AWARE SUPPORT POINTS V1 · HYBRID C⋆ · "
    "radius samples available · support_z centre authority · "
    "normal physics inactive · SES DDA kept · no pitch/roll"
)
OVERLAY_CAPTION = BANNER
ANALYZER_SECTION = "RADIUS-AWARE SUPPORT POINTS"

# --- stencil (deterministic; no dict iteration; heading does not rotate) ---
SQRT_HALF = math.sqrt(0.5)
# angle_k = k·π/4 for k=0..7 → (cos, sin) fixed table
RING_OFFSETS_NORMALIZED: tuple[tuple[float, float], ...] = (
    (1.0, 0.0),
    (SQRT_HALF, SQRT_HALF),
    (0.0, 1.0),
    (-SQRT_HALF, SQRT_HALF),
    (-1.0, 0.0),
    (-SQRT_HALF, -SQRT_HALF),
    (0.0, -1.0),
    (SQRT_HALF, -SQRT_HALF),
)
N_RING = 8
N_SAMPLES = 1 + N_RING  # centre + ring

# --- SUPPORT_CONTACT_CLASS_V1 (addendum) ---
CLASS_FULL = "FULL_SUPPORT"
CLASS_PARTIAL = "PARTIAL_SUPPORT"
CLASS_EDGE = "EDGE_OR_SPARSE_SUPPORT"
CLASS_LOSS = "LOSS_OF_SUPPORT"
CLASS_AIRBORNE = "AIRBORNE_NO_SUPPORT"

SAMPLE_SUPPORTED = "SUPPORTED"
SAMPLE_GAP = "GAP_TOO_LARGE"
SAMPLE_ABOVE = "SURFACE_ABOVE_ALLOWED_CONTACT"
SAMPLE_AIRBORNE = "NOT_APPLICABLE_AIRBORNE"

TAU_FULL = 1.0
TAU_PARTIAL = 5.0 / 9.0
TAU_LOS = 3.0 / 9.0
TAU_LOS_ENTER = TAU_LOS
TAU_LOS_EXIT = TAU_PARTIAL
EPS_SUPPORT = float(MICRORELIEF_THRESHOLD)  # 0.12
EDGE_SPREAD_THRESHOLD = float(MICRORELIEF_THRESHOLD)

HISTORY_LIMIT_DEFAULT = 64
ENTITY_ATTR_CLASS = "_radius_support_class"
ENTITY_ATTR_FRACTION = "_radius_support_fraction"
ENTITY_ATTR_TICK = "_radius_support_tick"

NORMAL_PHYSICAL_EFFECTS_ACTIVE = False
ONE_PE_AUTHORITY = "SES_DDA"
CENTRE_Z_AUTHORITY = True
RING_CLASSIFICATION_ONLY = True
STABILITY_MODEL = "LEVEL_1_PLANAR_CLASSIFICATION_ONLY"
TANGENT_GRAVITY = "NO"
SLOPE_SLIDING = "NO"
SES_DECOMPOSITION = "NO"
N_LAW = "N_EQUALS_M_G_UNCHANGED_NO_COVERAGE_SCALE"
OPTICAL_RADIUS_FOR_SUPPORT = "FORBIDDEN"
GAIT = "NO"
PITCH_ROLL = "NO"

RESEARCHER_FLAGS = {
    "researcher_only": True,
    "agent_accessible": False,
    "semantic_label": False,
}

PHYSICAL_STATE_HELD = "HELD"
PHYSICAL_STATE_FREE_STATIC = "FREE_STATIC"
PHYSICAL_STATE_FREE_MOVING = "FREE_MOVING"


@dataclass
class RadiusAwareSupportPointsConfig:
    """Fresh default OFF; missing snapshot field = OFF."""

    enabled: bool = False
    history_limit: int = HISTORY_LIMIT_DEFAULT
    eps_support: float = EPS_SUPPORT
    tau_full: float = TAU_FULL
    tau_partial: float = TAU_PARTIAL
    tau_los: float = TAU_LOS
    tau_los_enter: float = TAU_LOS_ENTER
    tau_los_exit: float = TAU_LOS_EXIT
    edge_spread_threshold: float = EDGE_SPREAD_THRESHOLD

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "history_limit": int(self.history_limit),
            "eps_support": float(self.eps_support),
            "tau_full": float(self.tau_full),
            "tau_partial": float(self.tau_partial),
            "tau_los": float(self.tau_los),
            "tau_los_enter": float(self.tau_los_enter),
            "tau_los_exit": float(self.tau_los_exit),
            "edge_spread_threshold": float(self.edge_spread_threshold),
            "profile_version": PROFILE_VERSION,
            "profile_alias_hybrid_cstar": PROFILE_ALIAS_HYBRID_CSTAR,
            "arch_stage": ARCH_STAGE,
            "N_SAMPLES": int(N_SAMPLES),
            "BODY_CONTACT_RADIUS": float(BODY_CONTACT_RADIUS),
            "CENTRE_Z_AUTHORITY": CENTRE_Z_AUTHORITY,
            "RING_CLASSIFICATION_ONLY": RING_CLASSIFICATION_ONLY,
            "ONE_PE_AUTHORITY": ONE_PE_AUTHORITY,
            "NORMAL_PHYSICAL_EFFECTS_ACTIVE": NORMAL_PHYSICAL_EFFECTS_ACTIVE,
            "STABILITY_MODEL": STABILITY_MODEL,
            "TANGENT_GRAVITY": TANGENT_GRAVITY,
            "SLOPE_SLIDING": SLOPE_SLIDING,
            "SES_DECOMPOSITION": SES_DECOMPOSITION,
            "N_LAW": N_LAW,
            "OPTICAL_RADIUS_FOR_SUPPORT": OPTICAL_RADIUS_FOR_SUPPORT,
            "GAIT": GAIT,
            "PITCH_ROLL": PITCH_ROLL,
            "reservoir_credit": False,
            "sound": False,
            "ring_derived_support_z": False,
            "face_sweep": False,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "RadiusAwareSupportPointsConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        ver = data.get("profile_version")
        if ver is not None and str(ver) != PROFILE_VERSION:
            raise ValueError(f"unknown radius-aware support profile: {ver}")
        return cls(
            enabled=bool(data.get("enabled", False)),
            history_limit=int(data.get("history_limit", HISTORY_LIMIT_DEFAULT)),
            eps_support=float(data.get("eps_support", EPS_SUPPORT)),
            tau_full=float(data.get("tau_full", TAU_FULL)),
            tau_partial=float(data.get("tau_partial", TAU_PARTIAL)),
            tau_los=float(data.get("tau_los", TAU_LOS)),
            tau_los_enter=float(data.get("tau_los_enter", TAU_LOS_ENTER)),
            tau_los_exit=float(data.get("tau_los_exit", TAU_LOS_EXIT)),
            edge_spread_threshold=float(data.get("edge_spread_threshold", EDGE_SPREAD_THRESHOLD)),
        )


def validate_config(cfg: RadiusAwareSupportPointsConfig) -> None:
    if not (1 <= int(cfg.history_limit) <= 512):
        raise ValueError("history_limit must be in [1, 512]")
    if not (0.0 < float(cfg.eps_support) <= 2.0):
        raise ValueError("eps_support must be in (0, 2]")
    for name in ("tau_full", "tau_partial", "tau_los", "tau_los_enter", "tau_los_exit"):
        v = float(getattr(cfg, name))
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"{name} must be in [0, 1]")
    if not (float(cfg.tau_los) <= float(cfg.tau_partial) <= float(cfg.tau_full)):
        raise ValueError("require tau_los <= tau_partial <= tau_full")
    if not (float(cfg.tau_los_enter) <= float(cfg.tau_los_exit)):
        raise ValueError("require tau_los_enter <= tau_los_exit (enter harder)")


def _line_ok(config: Any) -> bool:
    return config is not None and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"


def radius_aware_support_points_is_active(config: Any) -> bool:
    if not _line_ok(config):
        return False
    cfg = getattr(config, "radius_aware_support_points", None)
    if cfg is None or not bool(getattr(cfg, "enabled", False)):
        return False
    return bool(
        free_resource_object_static_traction_threshold_is_active(config)
        and continuous_surface_geometry_is_active(config)
        and surface_elevation_support_is_active(config)
        and flat_ground_gravity_is_active(config)
    )


def set_radius_aware_support_points(config: Any, enabled: bool) -> None:
    if config is None:
        return
    raw = getattr(config, "radius_aware_support_points", None)
    if raw is None:
        cfg = RadiusAwareSupportPointsConfig(enabled=bool(enabled))
        config.radius_aware_support_points = cfg
    else:
        raw.enabled = bool(enabled)
    if enabled:
        validate_config(getattr(config, "radius_aware_support_points"))


@dataclass
class RadiusAwareSupportPointsState:
    config: RadiusAwareSupportPointsConfig
    counters: dict[str, int] = field(default_factory=dict)
    # entity_id -> hysteresis / last class (no dense samples)
    entity: dict[str, dict[str, Any]] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    last_step: dict[str, Any] | None = None
    surface_generation: int = 0

    def __post_init__(self) -> None:
        if not self.counters:
            self.counters = {
                "classify_steps": 0,
                "full_support_steps": 0,
                "partial_support_steps": 0,
                "edge_or_sparse_steps": 0,
                "loss_of_support_steps": 0,
                "airborne_steps": 0,
                "loss_forced_airborne": 0,
                "landings_revoked": 0,
                "high_ring_anomaly": 0,
                "entities_classified": 0,
            }


def state_of(world: Any) -> RadiusAwareSupportPointsState | None:
    raw = getattr(world, "radius_aware_support_points_state", None)
    return raw if isinstance(raw, RadiusAwareSupportPointsState) else None


def ensure_radius_aware_support_points_for_runtime(
    world: Any, config: Any
) -> RadiusAwareSupportPointsState | None:
    if not radius_aware_support_points_is_active(config):
        if state_of(world) is not None:
            world.radius_aware_support_points_state = None
        return None
    st = state_of(world)
    if st is not None:
        return st
    raw = getattr(config, "radius_aware_support_points", None)
    cfg = (
        RadiusAwareSupportPointsConfig.from_dict(
            raw.to_dict() if hasattr(raw, "to_dict") else raw
        )
        if raw is not None
        else RadiusAwareSupportPointsConfig(enabled=True)
    )
    cfg.enabled = True
    validate_config(cfg)
    st = RadiusAwareSupportPointsState(config=cfg)
    world.radius_aware_support_points_state = st
    return st


def note_surface_generation(world: Any, generation: int | None = None) -> None:
    st = state_of(world)
    if st is None:
        return
    if generation is None:
        st.surface_generation = int(st.surface_generation) + 1
    else:
        st.surface_generation = int(generation)


def _dims(world: Any) -> tuple[int, int]:
    t = getattr(world, "T", None)
    return (int(t.shape[1]), int(t.shape[0])) if t is not None else (32, 32)


def _is_grounded_flag(entity: Any) -> bool:
    try:
        vz = float(getattr(entity, "vz", 0.0) or 0.0)
    except (TypeError, ValueError):
        vz = 0.0
    if not math.isfinite(vz):
        vz = 0.0
    return bool(getattr(entity, "grounded", False)) and abs(vz) <= 1e-12


def read_entity_support_class(entity: Any) -> str | None:
    raw = getattr(entity, ENTITY_ATTR_CLASS, None)
    return str(raw) if raw is not None else None


def eligible_for_ground_traction(entity: Any, *, mechanism_active: bool) -> bool:
    """grounded ∧ support_class != LOSS (when G2B ON); else grounded-only."""
    if not _is_grounded_flag(entity):
        return False
    if not mechanism_active:
        return True
    cls = read_entity_support_class(entity)
    if cls is None:
        # first tick / missing → treat as eligible if grounded (no false LOS)
        return True
    return cls not in (CLASS_LOSS, CLASS_AIRBORNE)


def body_support_radius(_body: Any = None) -> float:
    """Authoritative body contact radius — never magic literal at call sites."""
    return float(BODY_CONTACT_RADIUS)


def object_support_radius(obj: Any) -> float:
    return float(ensure_object_collision_radius(obj))


def _wrap_xy(x: float, y: float, width: int, height: int) -> tuple[float, float]:
    return float(wrap_coord(float(x), int(width))), float(wrap_coord(float(y), int(height)))


def sample_radius_aware_support(
    world: Any,
    centre_x: float,
    centre_y: float,
    radius: float,
    *,
    config: Any | None = None,
    grounded: bool = True,
    eps_support: float = EPS_SUPPORT,
) -> dict[str, Any]:
    """Pure kernel: centre + 8 ring via sample_surface_geometry only.

    Does NOT mutate world. Authoritative support height remains centre sample.
    Heading does not rotate the circle. WRAP per point.
    """
    w, h = _dims(world)
    R = float(radius)
    cx, cy = _wrap_xy(float(centre_x), float(centre_y), w, h)
    samples: list[dict[str, Any]] = []

    def _one(sx: float, sy: float, role: str, ring_index: int | None) -> dict[str, Any]:
        wx, wy = _wrap_xy(sx, sy, w, h)
        geo = sample_surface_geometry(world, wx, wy, config=config, record=False, reason="radius_aware_support")
        height = float(geo["height"])
        return {
            "role": role,
            "ring_index": ring_index,
            "x": float(wx),
            "y": float(wy),
            "height": height,
            "normal_x": float(geo["normal_x"]),
            "normal_y": float(geo["normal_y"]),
            "normal_z": float(geo["normal_z"]),
            "geometry_profile": geo.get("profile_version"),
        }

    centre = _one(cx, cy, "centre", None)
    h_centre = float(centre["height"])
    samples.append(centre)
    for k, (ox, oy) in enumerate(RING_OFFSETS_NORMALIZED):
        samples.append(_one(cx + R * ox, cy + R * oy, "ring", k))

    # classify each sample vs centre plane
    for s in samples:
        if not grounded:
            s["sample_status"] = SAMPLE_AIRBORNE
            continue
        dh = float(s["height"]) - h_centre
        if abs(dh) <= float(eps_support):
            s["sample_status"] = SAMPLE_SUPPORTED
        elif dh < -float(eps_support):
            s["sample_status"] = SAMPLE_GAP
        else:
            s["sample_status"] = SAMPLE_ABOVE

    # force centre SUPPORTED when grounded (plane definition)
    if grounded:
        samples[0]["sample_status"] = SAMPLE_SUPPORTED

    applicable = [s for s in samples if s["sample_status"] != SAMPLE_AIRBORNE]
    supported = [s for s in applicable if s["sample_status"] == SAMPLE_SUPPORTED]
    n_app = len(applicable)
    n_sup = len(supported)
    fraction = (float(n_sup) / float(n_app)) if n_app > 0 else 0.0
    heights = [float(s["height"]) for s in applicable]
    spread = (max(heights) - min(heights)) if heights else 0.0
    high_ring = any(s["sample_status"] == SAMPLE_ABOVE for s in samples if s["role"] == "ring")

    return {
        "centre_x": float(cx),
        "centre_y": float(cy),
        "radius": float(R),
        "h_centre": float(h_centre),
        "authoritative_support_z": float(h_centre),  # centre only
        "n_samples": int(len(samples)),
        "n_applicable": int(n_app),
        "n_supported": int(n_sup),
        "fraction_supported": float(fraction),
        "height_spread": float(spread),
        "high_ring_anomaly": bool(high_ring),
        "samples": samples,  # caller may omit from durable receipts
        "eps_support": float(eps_support),
        "CENTRE_Z_AUTHORITY": True,
        "RING_CLASSIFICATION_ONLY": True,
        "optical_radius_used": False,
    }


def classify_support_contact(
    sample_set: dict[str, Any],
    *,
    grounded: bool,
    prev_class: str | None,
    cfg: RadiusAwareSupportPointsConfig,
) -> dict[str, Any]:
    """SUPPORT_CONTACT_CLASS_V1 + LOS hysteresis (addendum)."""
    if not grounded:
        return {
            "support_class": CLASS_AIRBORNE,
            "raw_class": CLASS_AIRBORNE,
            "hysteresis_applied": False,
            "fraction_supported": 0.0,
            "height_spread": 0.0,
        }
    fraction = float(sample_set.get("fraction_supported") or 0.0)
    spread = float(sample_set.get("height_spread") or 0.0)
    tau_full = float(cfg.tau_full)
    tau_partial = float(cfg.tau_partial)
    tau_los = float(cfg.tau_los)
    edge_spread = float(cfg.edge_spread_threshold)

    if fraction >= tau_full:
        raw = CLASS_FULL
    elif fraction < tau_los:
        raw = CLASS_LOSS
    elif fraction < tau_partial:
        raw = CLASS_EDGE
    else:
        # tau_partial <= fraction < tau_full
        raw = CLASS_EDGE if spread > edge_spread else CLASS_PARTIAL

    hysteresis = False
    out = raw
    if prev_class == CLASS_LOSS:
        # sticky LOS until fraction recovers to tau_los_exit
        if fraction < float(cfg.tau_los_exit):
            out = CLASS_LOSS
            hysteresis = True
        else:
            out = raw
            hysteresis = True
    elif raw == CLASS_LOSS:
        # enter only if fraction < tau_los_enter (same as tau_los here)
        if fraction < float(cfg.tau_los_enter):
            out = CLASS_LOSS
        else:
            out = CLASS_EDGE

    return {
        "support_class": out,
        "raw_class": raw,
        "hysteresis_applied": bool(hysteresis),
        "fraction_supported": float(fraction),
        "height_spread": float(spread),
        "tau_full": tau_full,
        "tau_partial": tau_partial,
        "tau_los": tau_los,
    }


def _store_entity_class(entity: Any, cls: str, fraction: float, tick: int) -> None:
    try:
        setattr(entity, ENTITY_ATTR_CLASS, str(cls))
        setattr(entity, ENTITY_ATTR_FRACTION, float(fraction))
        setattr(entity, ENTITY_ATTR_TICK, int(tick))
    except Exception:
        pass


def _apply_loss_airborne(entity: Any) -> dict[str, Any]:
    """PE-safe: clear grounded only. No impulse, no sound, no z rewrite."""
    was = bool(getattr(entity, "grounded", False))
    landed_clear = False
    entity.grounded = False
    # do not invent vz; do not move z (centre support_z authority stays for FGG next tick)
    return {
        "forced_airborne": True,
        "was_grounded": was,
        "landing_revoked": landed_clear,
        "impulse": False,
        "sound": False,
        "ring_lift": False,
    }


def classify_entity(
    world: Any,
    entity: Any,
    *,
    entity_id: str,
    entity_kind: str,
    radius: float,
    config: Any,
    tick: int,
    st: RadiusAwareSupportPointsState,
    skip: bool = False,
    skip_reason: str = "",
) -> dict[str, Any]:
    """One classification per entity per tick. No id()."""
    cfg = st.config
    grounded = _is_grounded_flag(entity)
    prev = st.entity.get(str(entity_id), {})
    prev_class = prev.get("support_class")
    # idempotent same-tick guard (TwoAgent / double call)
    if int(prev.get("tick", -1)) == int(tick) and prev.get("entity_kind") == entity_kind:
        receipt = {
            "receipt_kind": RECEIPT_KIND,
            "event_kind": EVENT_CLASSIFY,
            "tick": int(tick),
            "entity_id": str(entity_id),
            "entity_kind": str(entity_kind),
            "skipped_duplicate_same_tick": True,
            "support_class": prev.get("support_class"),
            **RESEARCHER_FLAGS,
        }
        return receipt

    if skip:
        receipt = {
            "receipt_kind": RECEIPT_KIND,
            "event_kind": EVENT_CLASSIFY,
            "tick": int(tick),
            "entity_id": str(entity_id),
            "entity_kind": str(entity_kind),
            "skipped": True,
            "skip_reason": str(skip_reason),
            "support_class": CLASS_AIRBORNE if not grounded else prev_class,
            **RESEARCHER_FLAGS,
        }
        st.entity[str(entity_id)] = {
            "support_class": receipt.get("support_class"),
            "fraction_supported": prev.get("fraction_supported"),
            "tick": int(tick),
            "entity_kind": entity_kind,
            "skipped": True,
        }
        return receipt

    cx = float(getattr(entity, "x", 0.0) or 0.0)
    cy = float(getattr(entity, "y", 0.0) or 0.0)
    sample_set = sample_radius_aware_support(
        world, cx, cy, float(radius),
        config=config, grounded=grounded, eps_support=float(cfg.eps_support),
    )
    # verify centre authority matches SES/CSG oracle
    h_oracle = float(surface_support_height(world, cx, cy, config=config))
    centre_match = abs(float(sample_set["h_centre"]) - h_oracle) <= 1e-12

    classed = classify_support_contact(
        sample_set, grounded=grounded, prev_class=prev_class, cfg=cfg,
    )
    support_class = str(classed["support_class"])
    loss_fx: dict[str, Any] | None = None
    landing_revoked = False
    if support_class == CLASS_LOSS and grounded:
        # revoke grounded; if FGG just landed this tick, revoke landing fact (no sound)
        was_landing = bool(getattr(entity, "_fgg_landed_this_tick", False))
        loss_fx = _apply_loss_airborne(entity)
        if was_landing:
            landing_revoked = True
            loss_fx["landing_revoked"] = True
            try:
                setattr(entity, "_fgg_landed_this_tick", False)
            except Exception:
                pass
        support_class = CLASS_LOSS  # still LOSS; now airborne next traction tick
        grounded = False

    _store_entity_class(entity, support_class, float(classed["fraction_supported"]), int(tick))

    # bounded receipt — omit dense sample list from durable history
    sample_summary = [
        {
            "role": s["role"],
            "ring_index": s["ring_index"],
            "x": s["x"],
            "y": s["y"],
            "height": s["height"],
            "sample_status": s["sample_status"],
        }
        for s in sample_set["samples"]
    ]
    receipt = {
        "receipt_kind": RECEIPT_KIND,
        "event_kind": EVENT_LOST if support_class == CLASS_LOSS and loss_fx else EVENT_CLASSIFY,
        "tick": int(tick),
        "entity_id": str(entity_id),
        "entity_kind": str(entity_kind),
        "support_class": support_class,
        "raw_class": classed["raw_class"],
        "hysteresis_applied": classed["hysteresis_applied"],
        "fraction_supported": float(classed["fraction_supported"]),
        "height_spread": float(classed["height_spread"]),
        "n_samples": int(sample_set["n_samples"]),
        "n_supported": int(sample_set["n_supported"]),
        "n_applicable": int(sample_set["n_applicable"]),
        "radius": float(sample_set["radius"]),
        "h_centre": float(sample_set["h_centre"]),
        "authoritative_support_z": float(sample_set["authoritative_support_z"]),
        "centre_oracle_match": bool(centre_match),
        "grounded_after": bool(getattr(entity, "grounded", False)),
        "high_ring_anomaly": bool(sample_set["high_ring_anomaly"]),
        "loss_effects": loss_fx,
        "landing_revoked": bool(landing_revoked),
        "landing_sound": False,
        "optical_radius_used": False,
        "CENTRE_Z_AUTHORITY": True,
        "RING_CLASSIFICATION_ONLY": True,
        "ONE_PE_AUTHORITY": ONE_PE_AUTHORITY,
        "NORMAL_PHYSICAL_EFFECTS_ACTIVE": False,
        "STABILITY_MODEL": STABILITY_MODEL,
        "sample_summary": sample_summary,  # researcher; trimmed in history if needed
        "surface_generation": int(st.surface_generation),
        **RESEARCHER_FLAGS,
    }
    st.entity[str(entity_id)] = {
        "support_class": support_class,
        "raw_class": classed["raw_class"],
        "fraction_supported": float(classed["fraction_supported"]),
        "height_spread": float(classed["height_spread"]),
        "tick": int(tick),
        "entity_kind": entity_kind,
        "radius": float(radius),
        "h_centre": float(sample_set["h_centre"]),
        "high_ring_anomaly": bool(sample_set["high_ring_anomaly"]),
    }
    _record(st, receipt)
    return receipt


def _record(st: RadiusAwareSupportPointsState, receipt: dict[str, Any]) -> None:
    st.counters["classify_steps"] = int(st.counters.get("classify_steps", 0)) + 1
    st.counters["entities_classified"] = int(st.counters.get("entities_classified", 0)) + 1
    cls = receipt.get("support_class")
    mapping = {
        CLASS_FULL: "full_support_steps",
        CLASS_PARTIAL: "partial_support_steps",
        CLASS_EDGE: "edge_or_sparse_steps",
        CLASS_LOSS: "loss_of_support_steps",
        CLASS_AIRBORNE: "airborne_steps",
    }
    key = mapping.get(str(cls))
    if key:
        st.counters[key] = int(st.counters.get(key, 0)) + 1
    if receipt.get("loss_effects"):
        st.counters["loss_forced_airborne"] = int(st.counters.get("loss_forced_airborne", 0)) + 1
    if receipt.get("landing_revoked"):
        st.counters["landings_revoked"] = int(st.counters.get("landings_revoked", 0)) + 1
    if receipt.get("high_ring_anomaly"):
        st.counters["high_ring_anomaly"] = int(st.counters.get("high_ring_anomaly", 0)) + 1
    # history: omit dense sample_summary to keep bounded
    slim = {k: v for k, v in receipt.items() if k != "sample_summary"}
    st.history.append(slim)
    lim = min(int(st.config.history_limit), HISTORY_LIMIT_DEFAULT)
    if len(st.history) > lim:
        st.history = st.history[-lim:]
    st.last_step = slim


def classify_body(
    world: Any, body: Any, *, body_id: str, config: Any, tick: int,
) -> dict[str, Any] | None:
    st = ensure_radius_aware_support_points_for_runtime(world, config)
    if st is None:
        return None
    return classify_entity(
        world, body,
        entity_id=str(body_id),
        entity_kind="body",
        radius=body_support_radius(body),
        config=config,
        tick=int(tick),
        st=st,
    )


def _iter_resource_objects(world: Any) -> list[tuple[str, Any]]:
    """Support list or dict resource_objects containers (no id())."""
    objs = getattr(world, "resource_objects", None)
    rows: list[tuple[str, Any]] = []
    if isinstance(objs, dict):
        for oid in sorted(objs.keys(), key=lambda x: str(x)):
            rows.append((str(oid), objs[oid]))
    elif isinstance(objs, (list, tuple)):
        for obj in objs:
            oid = str(getattr(obj, "object_id", "") or "")
            if oid:
                rows.append((oid, obj))
        rows.sort(key=lambda r: r[0])
    return rows


def classify_free_objects(world: Any, config: Any, tick: int) -> list[dict[str, Any]]:
    st = ensure_radius_aware_support_points_for_runtime(world, config)
    if st is None:
        return []
    out: list[dict[str, Any]] = []
    for oid, obj in _iter_resource_objects(world):
        state = str(getattr(obj, "physical_state", "") or "")
        if state == PHYSICAL_STATE_HELD:
            out.append(classify_entity(
                world, obj,
                entity_id=str(oid),
                entity_kind="resource_object",
                radius=object_support_radius(obj),
                config=config,
                tick=int(tick),
                st=st,
                skip=True,
                skip_reason="HELD_NO_INDEPENDENT_CLASS",
            ))
            continue
        if state not in (PHYSICAL_STATE_FREE_STATIC, PHYSICAL_STATE_FREE_MOVING, ""):
            continue
        out.append(classify_entity(
            world, obj,
            entity_id=str(oid),
            entity_kind="resource_object",
            radius=object_support_radius(obj),
            config=config,
            tick=int(tick),
            st=st,
        ))
    return out


def step_after_body_vertical(
    world: Any, body: Any, *, body_id: str, config: Any, tick: int,
) -> dict[str, Any] | None:
    return classify_body(world, body, body_id=body_id, config=config, tick=tick)


def step_after_free_objects_vertical(world: Any, config: Any, tick: int) -> list[dict[str, Any]]:
    return classify_free_objects(world, config, tick=tick)


def serialize_state(st: RadiusAwareSupportPointsState | None) -> dict[str, Any] | None:
    if st is None:
        return None
    # minimal: no dense samples
    return {
        "schema": STATE_SCHEMA,
        "profile_version": PROFILE_VERSION,
        "counters": dict(st.counters),
        "entity": {
            eid: {
                "support_class": row.get("support_class"),
                "fraction_supported": row.get("fraction_supported"),
                "tick": row.get("tick"),
                "entity_kind": row.get("entity_kind"),
                # hysteresis needs prior class only
            }
            for eid, row in st.entity.items()
        },
        "surface_generation": int(st.surface_generation),
        # omit history dense; keep last_step slim
        "last_step": (
            {k: v for k, v in st.last_step.items() if k != "sample_summary"}
            if isinstance(st.last_step, dict) else None
        ),
    }


def restore_state(
    world: Any, data: dict[str, Any] | None, config: Any,
) -> RadiusAwareSupportPointsState | None:
    if not radius_aware_support_points_is_active(config):
        world.radius_aware_support_points_state = None
        return None
    raw_cfg = getattr(config, "radius_aware_support_points", None)
    cfg = (
        RadiusAwareSupportPointsConfig.from_dict(
            raw_cfg.to_dict() if hasattr(raw_cfg, "to_dict") else raw_cfg
        )
        if raw_cfg is not None
        else RadiusAwareSupportPointsConfig(enabled=True)
    )
    cfg.enabled = True
    validate_config(cfg)
    st = RadiusAwareSupportPointsState(config=cfg)
    if isinstance(data, dict):
        st.counters.update({k: int(v) for k, v in (data.get("counters") or {}).items()})
        ent = data.get("entity") or {}
        if isinstance(ent, dict):
            for eid, row in ent.items():
                if isinstance(row, dict):
                    st.entity[str(eid)] = {
                        "support_class": row.get("support_class"),
                        "fraction_supported": row.get("fraction_supported"),
                        "tick": row.get("tick"),
                        "entity_kind": row.get("entity_kind"),
                    }
        st.surface_generation = int(data.get("surface_generation") or 0)
        # restore no transition event
    world.radius_aware_support_points_state = st
    return st


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "enabled": bool(enabled),
        "profile_version": PROFILE_VERSION,
        "arch_stage": ARCH_STAGE,
        "promotion_class": "EXPERIMENTAL",
        "banner": BANNER,
        "CENTRE_Z_AUTHORITY": True,
        "RING_CLASSIFICATION_ONLY": True,
        "ONE_PE_AUTHORITY": ONE_PE_AUTHORITY,
        "NORMAL_PHYSICAL_EFFECTS_ACTIVE": False,
        "STABILITY_MODEL": STABILITY_MODEL,
        "researcher_only": True,
    }


def researcher_summary(world: Any) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    return {
        "mechanism": MECHANISM_ID,
        "profile_version": PROFILE_VERSION,
        "banner": BANNER,
        "counters": dict(st.counters),
        "last_step": st.last_step,
        "entities": dict(st.entity),
        "CENTRE_Z_AUTHORITY": True,
        "NORMAL_PHYSICAL_EFFECTS_ACTIVE": False,
        "ONE_PE_AUTHORITY": ONE_PE_AUTHORITY,
        "researcher_only": True,
    }


def overlay_payload(world: Any) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    return {
        "mechanism": MECHANISM_ID,
        "banner": BANNER,
        "caption": OVERLAY_CAPTION,
        "entities": {
            eid: {
                "support_class": row.get("support_class"),
                "fraction_supported": row.get("fraction_supported"),
                "h_centre": row.get("h_centre"),
                "radius": row.get("radius"),
            }
            for eid, row in st.entity.items()
        },
        "normal_implies_slope_forces": False,
        "centre_z_authority": True,
        "read_only": True,
        "researcher_only": True,
    }


def status_text() -> str:
    return BANNER
