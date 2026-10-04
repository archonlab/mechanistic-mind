"""Acanthostega VERTICAL STATE + UNIFORM GRAVITY + FLAT INELASTIC SUPPORT V1.

Preset: ACANTHOSTEGA_PHASE_C_FLAT_GROUND_GRAVITY
Parent: ACANTHOSTEGA_PHASE_B_EFFECTOR_WORK_ACCOUNTING

Umbrella mechanism: flat_ground_gravity
Capability flags (always co-gated with the umbrella — never independently toggleable):
  vertical_physical_state, uniform_gravity, flat_ground_support, vertical_contact_filter

Justification: CRITICAL ORDER forbids z existing while XY contacts ignore height.
Separate toggles would allow that invalid mid-state; one umbrella + four always-on
capability flags keeps atomic enablement while naming each concern in receipts.

Convention (locked):
  z = lower support point height above flat ground (NOT centre)
  centre_z = z + vertical_half_extent
  interval [z, z + 2*half_extent]
  ground_z = 0, upward positive, cells / cells·tick⁻¹
  grounded: z = 0, vz = 0
  Bodies: vertical_half_extent = BODY_CONTACT_RADIUS
  Objects: vertical_half_extent = collision_radius
  NOT optical / glyph / grasp radii

FULL_3D_ENTITY_COLLISION = NOT_IMPLEMENTED
VERTICAL_FILTER_FOR_EXISTING_HORIZONTAL_CONTACTS = IMPLEMENTED
Support: FLAT_GROUND_V1, restitution=0, inelastic, no bounce/sound/friction.
surface_elevation = METADATA_ONLY; terrain_potential is not height.
Spatial index stays 2D broadphase. No slopes, stacking, vertical impulse, landing sound.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

from mechanistic_mind.physical_system.physical_body_resource_object_contact import (
    BODY_CONTACT_RADIUS,
    CANONICAL_COLLISION_RADIUS,
)

# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------

MECHANISM_ID = "flat_ground_gravity"
CAPABILITY_VERTICAL_PHYSICAL_STATE = "vertical_physical_state"
CAPABILITY_UNIFORM_GRAVITY = "uniform_gravity"
CAPABILITY_FLAT_GROUND_SUPPORT = "flat_ground_support"
CAPABILITY_VERTICAL_CONTACT_FILTER = "vertical_contact_filter"
CAPABILITY_FLAGS = (
    CAPABILITY_VERTICAL_PHYSICAL_STATE,
    CAPABILITY_UNIFORM_GRAVITY,
    CAPABILITY_FLAT_GROUND_SUPPORT,
    CAPABILITY_VERTICAL_CONTACT_FILTER,
)

PROFILE_VERSION = "FLAT_GROUND_GRAVITY_PROFILE_V1"
STATE_SCHEMA = "FLAT_GROUND_GRAVITY_STATE_V1"
SUPPORT_PROFILE = "FLAT_GROUND_V1"

RECEIPT_VERTICAL_STEP = "VERTICAL_PHYSICAL_STEP"
RECEIPT_FLAT_SUPPORT = "FLAT_GROUND_SUPPORT"
EVENT_VERTICAL_STEP = "VERTICAL_PHYSICAL_STEP"
EVENT_LANDING = "FLAT_GROUND_LANDING"

END_REASON_VERTICAL_SEPARATION = "VERTICAL_SEPARATION"

FULL_3D_ENTITY_COLLISION = "NOT_IMPLEMENTED"
VERTICAL_FILTER_STATUS = "IMPLEMENTED"
SURFACE_ELEVATION_STATUS = "METADATA_ONLY"

BANNER = (
    "PHASE C · FLAT GROUND GRAVITY V1 · UNIFORM g · INELASTIC SUPPORT · "
    "SURFACE ELEVATION NOT ACTIVE · NO SLOPES · NO STACKING"
)
OVERLAY_CAPTION = BANNER
ANALYZER_SECTION = "VERTICAL STATE / GRAVITY / FLAT SUPPORT"

GROUND_Z = 0.0
DT = 1.0
# Calibrated so fall from z=1, vz=0 reaches ground in exactly 10 ticks
# (semi-implicit Euler: z_n = 1 - g*n*(n+1)/2 = 0  ⇒  g = 2/(10*11)).
GRAVITY_ACCELERATION = 2.0 / 110.0
FALL_FROM_UNIT_HEIGHT_TICKS = 10
MAX_VZ = 2.0
HELD_VERTICAL_OFFSET = 0.0
HISTORY_LIMIT_DEFAULT = 64
VERTICAL_STEP_HISTORY_BOUND = 64

PHYSICAL_STATE_HELD = "HELD"
PHYSICAL_STATE_FREE_STATIC = "FREE_STATIC"
PHYSICAL_STATE_FREE_MOVING = "FREE_MOVING"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass
class FlatGroundGravityConfig:
    enabled: bool = False
    g: float = GRAVITY_ACCELERATION
    ground_z: float = GROUND_Z
    max_vz: float = MAX_VZ
    dt: float = DT
    restitution: float = 0.0
    body_vertical_half_extent: float = BODY_CONTACT_RADIUS
    default_object_vertical_half_extent: float = CANONICAL_COLLISION_RADIUS
    held_vertical_offset: float = HELD_VERTICAL_OFFSET
    history_limit: int = HISTORY_LIMIT_DEFAULT
    # Capability flags — always True when enabled; never independently false.
    vertical_physical_state: bool = True
    uniform_gravity: bool = True
    flat_ground_support: bool = True
    vertical_contact_filter: bool = True

    def to_dict(self) -> dict[str, Any]:
        on = bool(self.enabled)
        return {
            "enabled": on,
            "g": float(self.g),
            "ground_z": float(self.ground_z),
            "max_vz": float(self.max_vz),
            "dt": float(self.dt),
            "restitution": 0.0,
            "body_vertical_half_extent": float(self.body_vertical_half_extent),
            "default_object_vertical_half_extent": float(self.default_object_vertical_half_extent),
            "held_vertical_offset": float(self.held_vertical_offset),
            "history_limit": int(self.history_limit),
            "profile_version": PROFILE_VERSION,
            "support_profile": SUPPORT_PROFILE,
            "vertical_physical_state": bool(on and self.vertical_physical_state),
            "uniform_gravity": bool(on and self.uniform_gravity),
            "flat_ground_support": bool(on and self.flat_ground_support),
            "vertical_contact_filter": bool(on and self.vertical_contact_filter),
            "FULL_3D_ENTITY_COLLISION": FULL_3D_ENTITY_COLLISION,
            "VERTICAL_FILTER_FOR_EXISTING_HORIZONTAL_CONTACTS": VERTICAL_FILTER_STATUS,
            "surface_elevation": SURFACE_ELEVATION_STATUS,
            "terrain_potential_is_height": False,
            "bounce": False,
            "landing_sound": False,
            "friction": False,
            "vertical_entity_impulse": False,
            "slopes": False,
            "stacking": False,
            "mass_independent_acceleration": True,
            "earth_g_981": False,
            "calibrated_fall_ticks_from_z1": int(FALL_FROM_UNIT_HEIGHT_TICKS),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "FlatGroundGravityConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        ver = data.get("profile_version")
        if ver is not None and str(ver) != PROFILE_VERSION:
            raise ValueError(f"unknown flat ground gravity profile: {ver}")
        return cls(
            enabled=bool(data.get("enabled", False)),
            g=float(data.get("g", GRAVITY_ACCELERATION)),
            ground_z=float(data.get("ground_z", GROUND_Z)),
            max_vz=float(data.get("max_vz", MAX_VZ)),
            dt=float(data.get("dt", DT)),
            restitution=0.0,
            body_vertical_half_extent=float(
                data.get("body_vertical_half_extent", BODY_CONTACT_RADIUS)
            ),
            default_object_vertical_half_extent=float(
                data.get("default_object_vertical_half_extent", CANONICAL_COLLISION_RADIUS)
            ),
            held_vertical_offset=float(data.get("held_vertical_offset", HELD_VERTICAL_OFFSET)),
            history_limit=int(data.get("history_limit", HISTORY_LIMIT_DEFAULT)),
            vertical_physical_state=True,
            uniform_gravity=True,
            flat_ground_support=True,
            vertical_contact_filter=True,
        )


def flat_ground_gravity_is_active(config: Any) -> bool:
    cfg = getattr(config, "flat_ground_gravity", None)
    if cfg is None:
        return False
    if isinstance(cfg, dict):
        return bool(cfg.get("enabled"))
    return bool(getattr(cfg, "enabled", False))


def set_flat_ground_gravity(config: Any, enabled: bool) -> None:
    on = bool(enabled)
    cur = getattr(config, "flat_ground_gravity", None)
    if cur is None or isinstance(cur, dict):
        cfg = FlatGroundGravityConfig.from_dict(cur if isinstance(cur, dict) else None)
        cfg.enabled = on
        config.flat_ground_gravity = cfg
    else:
        cur.enabled = on
        for name in CAPABILITY_FLAGS:
            setattr(cur, name, True)


def capability_flags(config: Any) -> dict[str, bool]:
    on = flat_ground_gravity_is_active(config)
    return {flag: bool(on) for flag in CAPABILITY_FLAGS}


# ---------------------------------------------------------------------------
# World state
# ---------------------------------------------------------------------------


@dataclass
class FlatGroundGravityState:
    config: FlatGroundGravityConfig
    last_vertical_integrated_tick: int = -1
    last_body_vertical_ticks: dict[str, int] = field(default_factory=dict)
    vertical_step_history: list[dict[str, Any]] = field(default_factory=list)
    support_history: list[dict[str, Any]] = field(default_factory=list)
    last_step: dict[str, Any] | None = None
    last_support: dict[str, Any] | None = None
    counters: dict[str, int] = field(default_factory=lambda: {
        "vertical_steps": 0,
        "landings": 0,
        "support_rest": 0,
        "held_snaps": 0,
        "filter_rejects": 0,
        "vertical_separations": 0,
        "reintegration_suppressed": 0,
        "bodies_integrated": 0,
        "objects_integrated": 0,
    })


def state_of(world: Any) -> FlatGroundGravityState | None:
    st = getattr(world, "flat_ground_gravity_state", None)
    return st if isinstance(st, FlatGroundGravityState) else None


def ensure_flat_ground_gravity_for_runtime(world: Any, config: Any) -> FlatGroundGravityState | None:
    if not flat_ground_gravity_is_active(config):
        return None
    st = state_of(world)
    if st is not None:
        return st
    raw = getattr(config, "flat_ground_gravity", None)
    cfg = (
        FlatGroundGravityConfig.from_dict(raw.to_dict() if hasattr(raw, "to_dict") else raw)
        if raw is not None
        else FlatGroundGravityConfig(enabled=True)
    )
    cfg.enabled = True
    st = FlatGroundGravityState(config=cfg)
    world.flat_ground_gravity_state = st
    _init_all_entities_grounded(world, config)
    return st


def _init_all_entities_grounded(world: Any, config: Any) -> None:
    """Apply init: all z=0, vz=0, grounded; no initial fall event."""
    cfg = getattr(config, "flat_ground_gravity", None)
    half_b = float(getattr(cfg, "body_vertical_half_extent", BODY_CONTACT_RADIUS) or BODY_CONTACT_RADIUS)
    for obj in list(getattr(world, "resource_objects", None) or []):
        ensure_object_vertical(obj, config)
        obj.z = 0.0
        obj.vz = 0.0
        obj.grounded = True
    # Bodies are attached via runtime; world may not list them. Init happens per-body ensure.


def ensure_body_vertical(body: Any, config: Any | None = None) -> None:
    if not hasattr(body, "z") or getattr(body, "z", None) is None:
        body.z = 0.0
    if not hasattr(body, "vz") or getattr(body, "vz", None) is None:
        body.vz = 0.0
    if not hasattr(body, "grounded") or getattr(body, "grounded", None) is None:
        body.grounded = True
    if not hasattr(body, "vertical_half_extent") or getattr(body, "vertical_half_extent", None) is None:
        half = BODY_CONTACT_RADIUS
        if config is not None:
            cfg = getattr(config, "flat_ground_gravity", None)
            if cfg is not None:
                half = float(getattr(cfg, "body_vertical_half_extent", BODY_CONTACT_RADIUS))
        body.vertical_half_extent = float(half)


def ensure_object_vertical(obj: Any, config: Any | None = None) -> None:
    if not hasattr(obj, "z") or getattr(obj, "z", None) is None:
        obj.z = 0.0
    if not hasattr(obj, "vz") or getattr(obj, "vz", None) is None:
        obj.vz = 0.0
    if not hasattr(obj, "grounded") or getattr(obj, "grounded", None) is None:
        obj.grounded = True
    if not hasattr(obj, "vertical_half_extent") or getattr(obj, "vertical_half_extent", None) is None:
        from mechanistic_mind.physical_system.physical_body_resource_object_contact import ensure_object_collision_radius
        default = CANONICAL_COLLISION_RADIUS
        if config is not None:
            cfg = getattr(config, "flat_ground_gravity", None)
            if cfg is not None:
                default = float(getattr(cfg, "default_object_vertical_half_extent", CANONICAL_COLLISION_RADIUS))
        obj.vertical_half_extent = float(ensure_object_collision_radius(obj, default))


# ---------------------------------------------------------------------------
# Shared vertical geometry / filter contract
# ---------------------------------------------------------------------------


def vertical_half_extent_of(entity: Any, *, kind: str = "object", config: Any | None = None) -> float:
    he = getattr(entity, "vertical_half_extent", None)
    if he is not None:
        return float(he)
    if kind == "body":
        if config is not None:
            cfg = getattr(config, "flat_ground_gravity", None)
            if cfg is not None:
                return float(getattr(cfg, "body_vertical_half_extent", BODY_CONTACT_RADIUS))
        return float(BODY_CONTACT_RADIUS)
    from mechanistic_mind.physical_system.physical_body_resource_object_contact import ensure_object_collision_radius
    default = CANONICAL_COLLISION_RADIUS
    if config is not None:
        cfg = getattr(config, "flat_ground_gravity", None)
        if cfg is not None:
            default = float(getattr(cfg, "default_object_vertical_half_extent", CANONICAL_COLLISION_RADIUS))
    return float(ensure_object_collision_radius(entity, default))


def read_z(entity: Any) -> float:
    try:
        if isinstance(entity, (list, tuple)):
            if len(entity) >= 3:
                z = float(entity[2])
            else:
                z = 0.0
        else:
            z = float(getattr(entity, "z", 0.0) or 0.0)
    except (TypeError, ValueError):
        z = 0.0
    return z if math.isfinite(z) else 0.0


def read_vz(entity: Any) -> float:
    try:
        vz = float(getattr(entity, "vz", 0.0) or 0.0)
    except (TypeError, ValueError):
        vz = 0.0
    return vz if math.isfinite(vz) else 0.0


def centre_z_of(entity: Any, *, kind: str = "object", config: Any | None = None) -> float:
    return read_z(entity) + vertical_half_extent_of(entity, kind=kind, config=config)


def vertical_interval(
    entity: Any,
    *,
    kind: str = "object",
    config: Any | None = None,
    z_override: float | None = None,
) -> tuple[float, float]:
    """Return [z_lo, z_hi] = [z, z + 2*half_extent] (lower support → top)."""
    z = float(z_override) if z_override is not None else read_z(entity)
    he = vertical_half_extent_of(entity, kind=kind, config=config)
    return (float(z), float(z + 2.0 * he))


def intervals_overlap(a: tuple[float, float], b: tuple[float, float], *, eps: float = 1e-12) -> bool:
    return not (a[1] < b[0] - eps or b[1] < a[0] - eps)


def vertical_overlap_at_endpoint(
    a: Any,
    b: Any,
    *,
    kind_a: str = "object",
    kind_b: str = "object",
    config: Any | None = None,
) -> bool:
    return intervals_overlap(
        vertical_interval(a, kind=kind_a, config=config),
        vertical_interval(b, kind=kind_b, config=config),
    )


def _lerp(a: float, b: float, t: float) -> float:
    return float(a) + (float(b) - float(a)) * float(t)


def vertical_overlap_at_fraction(
    a_start: Any,
    a_end: Any,
    b_start: Any,
    b_end: Any,
    fraction: float,
    *,
    kind_a: str = "object",
    kind_b: str = "object",
    config: Any | None = None,
) -> bool:
    """Interpolate each entity's z at the horizontal contact fraction, then test overlap."""
    t = float(fraction)
    if not math.isfinite(t):
        t = 1.0
    t = max(0.0, min(1.0, t))
    za = _lerp(read_z(a_start), read_z(a_end), t)
    zb = _lerp(read_z(b_start), read_z(b_end), t)
    return intervals_overlap(
        vertical_interval(a_end, kind=kind_a, config=config, z_override=za),
        vertical_interval(b_end, kind=kind_b, config=config, z_override=zb),
    )


def vertical_filter_allows_contact(
    config: Any,
    *,
    a: Any,
    b: Any,
    kind_a: str = "object",
    kind_b: str = "object",
    contact_fraction: float | None = None,
    a_prev: Any | None = None,
    b_prev: Any | None = None,
    detection_mode: str | None = None,
) -> bool:
    """Prior presets / mechanism OFF: bypass filter entirely (always allow).

    When ON: endpoint uses current z; swept interpolates z at horizontal contact fraction.
    """
    if not flat_ground_gravity_is_active(config):
        return True
    cfg = getattr(config, "flat_ground_gravity", None)
    if cfg is not None and not bool(getattr(cfg, "vertical_contact_filter", True)):
        return True
    mode = str(detection_mode or "")
    frac = contact_fraction
    if mode == "SWEPT_CROSSING" and frac is not None and a_prev is not None and b_prev is not None:
        # Prev pose may be [x,y] or [x,y,z]. Missing z → use current z (no vertical sweep history).
        za0 = read_z(a_prev) if (not isinstance(a_prev, (list, tuple)) or len(a_prev) >= 3) else read_z(a)
        zb0 = read_z(b_prev) if (not isinstance(b_prev, (list, tuple)) or len(b_prev) >= 3) else read_z(b)
        a_start = SimpleNamespace(z=za0)
        b_start = SimpleNamespace(z=zb0)
        return vertical_overlap_at_fraction(
            a_start, a, b_start, b, float(frac),
            kind_a=kind_a, kind_b=kind_b, config=config,
        )
    return vertical_overlap_at_endpoint(a, b, kind_a=kind_a, kind_b=kind_b, config=config)


def apply_vertical_filter_to_measurement(
    world: Any,
    config: Any,
    measurement: dict[str, Any],
    *,
    a: Any,
    b: Any,
    kind_a: str,
    kind_b: str,
    a_prev: Any | None = None,
    b_prev: Any | None = None,
) -> dict[str, Any]:
    """Mutate measurement: if XY contact but no vertical overlap → reject / mark separation."""
    if not flat_ground_gravity_is_active(config):
        measurement["vertical_filter"] = "BYPASSED"
        return measurement
    if not bool(measurement.get("in_contact")):
        measurement["vertical_filter"] = "N_A_NO_XY"
        return measurement
    allowed = vertical_filter_allows_contact(
        config,
        a=a, b=b, kind_a=kind_a, kind_b=kind_b,
        contact_fraction=measurement.get("contact_fraction"),
        a_prev=a_prev, b_prev=b_prev,
        detection_mode=measurement.get("detection_mode"),
    )
    ia = vertical_interval(a, kind=kind_a, config=config)
    ib = vertical_interval(b, kind=kind_b, config=config)
    measurement["vertical_interval_a"] = [ia[0], ia[1]]
    measurement["vertical_interval_b"] = [ib[0], ib[1]]
    measurement["vertical_overlap"] = bool(allowed)
    if allowed:
        measurement["vertical_filter"] = "PASS"
        return measurement
    measurement["in_contact"] = False
    measurement["endpoint_contact"] = False
    measurement["swept_contact"] = False
    measurement["vertical_filter"] = "REJECT"
    measurement["vertical_separation_reason"] = END_REASON_VERTICAL_SEPARATION
    st = state_of(world)
    if st is not None:
        st.counters["filter_rejects"] = int(st.counters.get("filter_rejects", 0)) + 1
    return measurement


# ---------------------------------------------------------------------------
# Energy helpers (researcher-only; NO reservoir credit; no global conservation claim)
# ---------------------------------------------------------------------------


def kinetic_z(mass: float, vz: float) -> float:
    return 0.5 * float(mass) * float(vz) * float(vz)


def potential_z(mass: float, g: float, z: float) -> float:
    """U = m g z with z = lower support height."""
    return float(mass) * float(g) * float(z)


# ---------------------------------------------------------------------------
# Gravity + flat inelastic support
# ---------------------------------------------------------------------------


def _clamp_vz(vz: float, max_vz: float) -> float:
    m = float(max_vz)
    if not math.isfinite(vz):
        return 0.0
    if vz > m:
        return m
    if vz < -m:
        return -m
    return float(vz)


def integrate_vertical_entity(
    entity: Any,
    *,
    mass: float,
    config: FlatGroundGravityConfig,
    tick: int,
    entity_id: str,
    entity_kind: str,
    skip_gravity: bool = False,
    support_z: float | None = None,
    world: Any | None = None,
    runtime_config: Any | None = None,
) -> dict[str, Any]:
    """One vertical step: gravity then inelastic support. Returns receipt dict.

    When surface elevation support is active, support_z is the local elevation height
    (not flat ground_z=0). Absent/None → flat ground_z (prior presets unchanged).
    """
    ensure_body_vertical(entity) if entity_kind == "body" else ensure_object_vertical(entity)
    z0 = read_z(entity)
    vz0 = read_vz(entity)
    g = float(config.g)
    dt = float(config.dt)
    ground = float(config.ground_z)
    elev_support_used = False
    if support_z is not None and math.isfinite(float(support_z)):
        ground = float(support_z)
        elev_support_used = True
    elif world is not None:
        from mechanistic_mind.physical_system.surface_elevation_support import (
            surface_elevation_support_active_on_world,
            support_z_for_entity,
        )
        if surface_elevation_support_active_on_world(world, runtime_config):
            ground = float(support_z_for_entity(
                world, runtime_config, float(getattr(entity, "x", 0.0) or 0.0),
                float(getattr(entity, "y", 0.0) or 0.0),
                z=float(z0),
            ))
            elev_support_used = True
            # VW2: no occupied support below → do not invent flat ground_z=0 clamp.
            try:
                from mechanistic_mind.physical_system.occupancy_support_and_contact_queries import (
                    NO_SUPPORT_SENTINEL,
                    occupancy_support_and_contact_queries_is_active,
                )

                if (
                    occupancy_support_and_contact_queries_is_active(runtime_config)
                    and ground <= float(NO_SUPPORT_SENTINEL) * 0.5
                ):
                    elev_support_used = True  # still "elevation path" but unreachable floor
            except Exception:
                pass
    was_grounded = bool(getattr(entity, "grounded", False)) and abs(z0 - ground) <= 1e-12 and abs(vz0) <= 1e-12

    u0 = potential_z(mass, g, z0)
    k0 = kinetic_z(mass, vz0)

    gravity_skip_reason: str | None = None
    # Free-Space V1A: supported-rest gravity gate (parent tip OFF → unchanged always-apply path).
    if (
        not skip_gravity
        and runtime_config is not None
        and world is not None
    ):
        try:
            from mechanistic_mind.physical_system.free_space_state_and_pe_authority_contract import (
                GRAVITY_SKIP_VALID_SUPPORT,
                free_space_state_and_pe_authority_contract_is_active,
                should_skip_gravity_for_supported_rest,
            )

            if free_space_state_and_pe_authority_contract_is_active(runtime_config):
                if should_skip_gravity_for_supported_rest(
                    z=z0,
                    vz=vz0,
                    support_z=ground,
                    grounded=bool(getattr(entity, "grounded", False)),
                    config=runtime_config,
                ):
                    skip_gravity = True
                    gravity_skip_reason = GRAVITY_SKIP_VALID_SUPPORT
        except Exception:
            pass

    if skip_gravity:
        vz1 = vz0
        z1 = z0
        gravity_applied = False
    else:
        vz1 = _clamp_vz(vz0 - g * dt, config.max_vz)
        z1 = z0 + vz1 * dt
        gravity_applied = True

    landed = False
    support_dissipated = 0.0
    support_applied = False
    landing_rec: dict[str, Any] | None = None
    z1_proposed = float(z1)
    vz1_proposed = float(vz1)
    # SES lock: no free upward snap into higher support (ΔU must be SES-paid).
    _ses_below_support = bool(elev_support_used and z0 < ground - 1e-12)

    # Free-Space V1B: plan→fact→response→commit replaces old inelastic clamp when ON.
    _landing_on = False
    if runtime_config is not None and world is not None:
        try:
            from mechanistic_mind.physical_system.vertical_terrain_landing_contact_response import (
                apply_vertical_landing,
                vertical_terrain_landing_contact_response_is_active,
            )

            _landing_on = bool(
                vertical_terrain_landing_contact_response_is_active(runtime_config)
            )
        except Exception:
            _landing_on = False

    if _landing_on:
        landing_rec = apply_vertical_landing(
            entity,
            world=world,
            runtime_config=runtime_config,
            tick=int(tick),
            entity_id=str(entity_id),
            entity_kind=str(entity_kind),
            mass=float(mass),
            z0=float(z0),
            vz0=float(vz0),
            z1_proposed=float(z1_proposed),
            vz1_proposed=float(vz1_proposed),
            support_z=float(ground),
            was_grounded=bool(was_grounded),
            skip_gravity=bool(skip_gravity),
            gravity_applied=bool(gravity_applied),
            ses_below_support=bool(_ses_below_support),
            fgg_config=config,
        )
        if landing_rec is not None:
            z1 = float(landing_rec.get("_fgg_z", entity.z))
            vz1 = float(landing_rec.get("_fgg_vz", entity.vz))
            landed = bool(landing_rec.get("_fgg_landed"))
            support_applied = bool(landing_rec.get("_fgg_support_applied"))
            support_dissipated = float(landing_rec.get("_fgg_support_dissipated") or 0.0)
            grounded = bool(landing_rec.get("_fgg_grounded"))
        else:
            grounded = bool(abs(z1 - ground) <= 1e-12 and abs(vz1) <= 1e-12)
            entity.z = float(z1)
            entity.vz = float(vz1)
            entity.grounded = bool(grounded)
    elif _ses_below_support:
        support_applied = False
        grounded = bool(abs(z1 - ground) <= 1e-12 and abs(vz1) <= 1e-12)
        entity.z = float(z1)
        entity.vz = float(vz1)
        entity.grounded = bool(grounded)
    elif z1 < ground or (abs(z1 - ground) <= 1e-12 and vz1 < 0.0):
        # Parent path: inelastic support clamp (restitution=0). Bypassed when V1B ON.
        support_applied = True
        k_impact = kinetic_z(mass, vz1)
        u_over = potential_z(mass, g, z1) - potential_z(mass, g, ground)
        support_dissipated = float(k_impact) + max(0.0, -float(u_over))
        z1 = ground
        vz1 = 0.0
        if not was_grounded:
            landed = True
        grounded = bool(abs(z1 - ground) <= 1e-12 and abs(vz1) <= 1e-12)
        entity.z = float(z1)
        entity.vz = float(vz1)
        entity.grounded = bool(grounded)
    else:
        grounded = bool(abs(z1 - ground) <= 1e-12 and abs(vz1) <= 1e-12)
        entity.z = float(z1)
        entity.vz = float(vz1)
        entity.grounded = bool(grounded)

    if not _landing_on:
        try:
            setattr(entity, "_fgg_landed_this_tick", bool(landed))
        except Exception:
            pass

    u1 = potential_z(mass, g, z1)
    k1 = kinetic_z(mass, vz1)

    receipt = {
        "receipt_kind": RECEIPT_VERTICAL_STEP,
        "tick": int(tick),
        "entity_id": str(entity_id),
        "entity_kind": str(entity_kind),
        "z_before": float(z0),
        "vz_before": float(vz0),
        "z_after": float(z1),
        "vz_after": float(vz1),
        "centre_z_after": float(z1) + vertical_half_extent_of(entity, kind=entity_kind),
        "g": float(g),
        "dt": float(dt),
        "gravity_applied": bool(gravity_applied),
        "skip_gravity": bool(skip_gravity),
        "support_applied": bool(support_applied),
        "landed": bool(landed),
        "grounded": bool(grounded),
        "was_grounded": bool(was_grounded),
        "support_profile": SUPPORT_PROFILE,
        "restitution": 0.0,
        "bounce": False,
        "landing_sound": False,
        "friction": False,
        "K_z_before": float(k0),
        "K_z_after": float(k1),
        "U_before": float(u0),
        "U_after": float(u1),
        "support_dissipated": float(support_dissipated),
        "mass": float(mass),
        "reservoir_credit": False,
        "global_conservation_claim": False,
        "surface_elevation_used": bool(elev_support_used),
        "support_z": float(ground),
        "terrain_potential_used": False,
        "z1_proposed_pre_support": float(z1_proposed),
        "vz1_proposed_pre_support": float(vz1_proposed),
        "landing_v1b_active": bool(_landing_on),
        "old_clamp_bypassed": bool(_landing_on),
        "researcher_only": True,
        "agent_accessible": False,
    }
    if landed:
        receipt["support_receipt_kind"] = RECEIPT_FLAT_SUPPORT
        receipt["landing_event"] = EVENT_LANDING
    if gravity_skip_reason is not None:
        receipt["gravity_skip_reason"] = gravity_skip_reason
    if landing_rec is not None:
        receipt["vertical_terrain_landing_v1"] = {
            "episode_id": landing_rec.get("episode_id"),
            "episode_phase": landing_rec.get("episode_phase"),
            "toi": landing_rec.get("toi"),
            "impulse_magnitude": landing_rec.get("impulse_magnitude"),
            "dissipated_energy": landing_rec.get("dissipated_energy"),
            "response_applied": landing_rec.get("response_applied"),
            "impact_sound_emitted": False,
        }
    # Free-Space V1A researcher contract receipt (no cognition; no new integrator).
    if runtime_config is not None and world is not None:
        try:
            from mechanistic_mind.physical_system.free_space_state_and_pe_authority_contract import (
                free_space_state_and_pe_authority_contract_is_active,
                record_vertical_contract_receipt,
            )

            if free_space_state_and_pe_authority_contract_is_active(runtime_config):
                he = vertical_half_extent_of(entity, kind=entity_kind, config=runtime_config)
                fs_rec = record_vertical_contract_receipt(
                    world,
                    runtime_config,
                    tick=int(tick),
                    entity_id=str(entity_id),
                    entity_kind=str(entity_kind),
                    body_slot=str(entity_id) if entity_kind == "body" else None,
                    z_before=float(z0),
                    vz_before=float(vz0),
                    z_after=float(z1),
                    vz_after=float(vz1),
                    centre_z_after=float(z1) + float(he),
                    vertical_half_extent=float(he),
                    support_z=float(ground),
                    was_grounded=bool(was_grounded),
                    grounded_after=bool(grounded),
                    gravity_applied=bool(gravity_applied),
                    skip_gravity=bool(skip_gravity),
                    gravity_skip_reason=gravity_skip_reason,
                    support_applied=bool(support_applied),
                    landed=bool(landed),
                    support_dissipated=float(support_dissipated),
                    mass=float(mass),
                )
                if fs_rec is not None:
                    receipt["free_space_support_state_v1"] = {
                        "support_state": fs_rec.get("support_state"),
                        "transition_reason": fs_rec.get("transition_reason"),
                        "active_pe_authority": fs_rec.get("active_pe_authority"),
                        "double_pe_authority": fs_rec.get("double_pe_authority"),
                        "gravity_skip_reason": fs_rec.get("gravity_skip_reason"),
                    }
        except Exception:
            pass
    return receipt


def integrate_body_vertical(
    body: Any,
    *,
    body_id: str,
    body_cfg: Any,
    config: Any,
    tick: int,
    world: Any,
) -> dict[str, Any] | None:
    st = ensure_flat_ground_gravity_for_runtime(world, config)
    if st is None:
        return None
    bid = str(body_id)
    prev = int(st.last_body_vertical_ticks.get(bid, -1))
    if int(tick) <= prev:
        st.counters["reintegration_suppressed"] = int(st.counters.get("reintegration_suppressed", 0)) + 1
        return None
    st.last_body_vertical_ticks[bid] = int(tick)
    ensure_body_vertical(body, config)
    mass = float(getattr(body_cfg, "mass", 1.0) or 1.0)
    rec = integrate_vertical_entity(
        body, mass=mass, config=st.config, tick=tick, entity_id=bid, entity_kind="body",
        world=world, runtime_config=config,
    )
    _record_vertical_receipt(st, world, rec)
    st.counters["bodies_integrated"] = int(st.counters.get("bodies_integrated", 0)) + 1
    return rec


def integrate_free_objects_vertical(world: Any, config: Any, tick: int) -> list[dict[str, Any]]:
    """After horizontal FOK → gravity → support for FREE_STATIC / FREE_MOVING (shared world once)."""
    st = ensure_flat_ground_gravity_for_runtime(world, config)
    if st is None:
        return []
    if int(tick) <= int(st.last_vertical_integrated_tick):
        st.counters["reintegration_suppressed"] = int(st.counters.get("reintegration_suppressed", 0)) + 1
        return []
    st.last_vertical_integrated_tick = int(tick)
    from mechanistic_mind.physical_system.resource_objects import ensure_resource_object_state

    rows: list[dict[str, Any]] = []
    for obj in sorted(ensure_resource_object_state(world), key=lambda o: str(o.object_id)):
        ps = str(getattr(obj, "physical_state", ""))
        if ps == PHYSICAL_STATE_HELD:
            continue
        if ps not in (PHYSICAL_STATE_FREE_STATIC, PHYSICAL_STATE_FREE_MOVING):
            continue
        try:
            from mechanistic_mind.physical_system.detached_terrain_material_initial_placement import (
                object_dynamics_eligible,
            )

            if not object_dynamics_eligible(obj, int(tick)):
                continue
        except Exception:
            pass
        ensure_object_vertical(obj, config)
        # Already grounded at rest: still run once (support rest; no repeated landing).
        mass = float(getattr(obj, "mass", 1.0) or 1.0)
        rec = integrate_vertical_entity(
            obj, mass=mass, config=st.config, tick=tick,
            entity_id=str(obj.object_id), entity_kind="object",
            world=world, runtime_config=config,
        )
        _record_vertical_receipt(st, world, rec)
        st.counters["objects_integrated"] = int(st.counters.get("objects_integrated", 0)) + 1
        rows.append(rec)
    world.last_vertical_physical_step = {
        "tick": int(tick),
        "n_objects": len(rows),
        "receipts": rows[-VERTICAL_STEP_HISTORY_BOUND:],
    }
    return rows


def snap_held_vertical_from_holders(world: Any, holders: list[dict[str, Any]], config: Any) -> int:
    """HELD: z/vz = holder (fixed offset 0); no independent gravity."""
    if not flat_ground_gravity_is_active(config):
        return 0
    st = ensure_flat_ground_gravity_for_runtime(world, config)
    if st is None:
        return 0
    by_holder = {str(h["body_id"]): h for h in holders}
    offset = float(st.config.held_vertical_offset)
    n = 0
    for obj in list(getattr(world, "resource_objects", None) or []):
        if str(getattr(obj, "physical_state", "")) != PHYSICAL_STATE_HELD:
            continue
        hid = str(getattr(obj, "holder_body_id", "") or "")
        row = by_holder.get(hid)
        if row is None:
            continue
        body = row.get("body")
        if body is None:
            continue
        ensure_body_vertical(body, config)
        ensure_object_vertical(obj, config)
        held_z = float(read_z(body) + offset)
        # Relative tip vertical DOF: held lower point tracks body.z + relative_z.
        try:
            from mechanistic_mind.physical_system.manipulator_relative_world_actuation import (
                manipulator_relative_world_actuation_is_active,
                relative_z_of,
            )

            if manipulator_relative_world_actuation_is_active(config):
                mid = str(getattr(obj, "manipulator_id", "") or "")
                if mid:
                    held_z = float(held_z) + float(
                        relative_z_of(world, hid, mid, config=config)
                    )
        except Exception:
            pass
        obj.z = float(held_z)
        obj.vz = float(read_vz(body))
        obj.grounded = bool(getattr(body, "grounded", False))
        n += 1
        st.counters["held_snaps"] = int(st.counters.get("held_snaps", 0)) + 1
    return n


def apply_release_vertical(
    obj: Any,
    holder_body: Any,
    config: Any,
    *,
    world: Any | None = None,
    tick: int | None = None,
    holder_body_id: str | None = None,
    manipulator_id: str | None = None,
) -> None:
    """RELEASE: object.z = held z, vz = holder.vz. No gravity this tick (FOK pattern)."""
    if not flat_ground_gravity_is_active(config):
        return
    ensure_body_vertical(holder_body, config)
    ensure_object_vertical(obj, config)
    # Held pose already mirrored holder; release keeps that z and takes holder vz.
    obj.z = float(read_z(obj))  # held z (== holder z + offset)
    obj.vz = float(read_vz(holder_body))
    t = int(tick) if tick is not None else (
        int(getattr(world, "tick", -1) or -1) if world is not None else -1
    )
    # Free-Space V1D: stamp T+1 eligibility + release support classification (shared chain).
    try:
        from mechanistic_mind.physical_system.release_and_excavation_support_loss_integration import (
            process_release_entry,
            release_and_excavation_support_loss_integration_is_active,
        )

        if (
            world is not None
            and release_and_excavation_support_loss_integration_is_active(config)
        ):
            process_release_entry(
                world,
                config,
                obj,
                holder_body,
                tick=t,
                holder_body_id=holder_body_id,
                manipulator_id=manipulator_id,
            )
            return
    except Exception:
        pass
    # Free-Space V1A: classify grounded vs local support_z (not flat z≈0 only).
    try:
        from mechanistic_mind.physical_system.free_space_state_and_pe_authority_contract import (
            GRAVITY_SKIP_HELD,
            free_space_state_and_pe_authority_contract_is_active,
            record_vertical_contract_receipt,
        )

        if free_space_state_and_pe_authority_contract_is_active(config) and world is not None:
            from mechanistic_mind.physical_system.surface_elevation_support import (
                support_z_for_entity,
            )

            sz = float(
                support_z_for_entity(
                    world,
                    config,
                    float(getattr(obj, "x", 0.0) or 0.0),
                    float(getattr(obj, "y", 0.0) or 0.0),
                    z=float(obj.z),
                )
            )
            z = float(obj.z)
            vz = float(obj.vz)
            he = vertical_half_extent_of(obj, kind="object", config=config)
            obj.grounded = bool(abs(z - sz) <= 1e-12 and abs(vz) <= 1e-12)
            record_vertical_contract_receipt(
                world,
                config,
                tick=t,
                entity_id=str(getattr(obj, "object_id", getattr(obj, "id", "released"))),
                entity_kind="object",
                body_slot=str(holder_body_id or getattr(obj, "holder_body_id", None) or ""),
                z_before=z,
                vz_before=vz,
                z_after=z,
                vz_after=vz,
                centre_z_after=z + float(he),
                vertical_half_extent=float(he),
                support_z=sz,
                was_grounded=False,
                grounded_after=bool(obj.grounded),
                gravity_applied=False,
                skip_gravity=True,
                gravity_skip_reason=GRAVITY_SKIP_HELD,
                support_applied=False,
                landed=False,
                support_dissipated=0.0,
                mass=float(getattr(obj, "mass", 1.0) or 1.0),
                vertical_integration_eligible=False,
                vertical_integration_applied=False,
                release_transition=True,
            )
            return
    except Exception:
        pass
    obj.grounded = bool(abs(obj.z) <= 1e-12 and abs(obj.vz) <= 1e-12)


def grasp_vertical_reachable(
    body: Any,
    obj: Any,
    config: Any,
) -> bool:
    """GRASP: XY already checked elsewhere; vertical reach = endpoint overlap only (no sweep)."""
    if not flat_ground_gravity_is_active(config):
        return True
    return vertical_overlap_at_endpoint(body, obj, kind_a="body", kind_b="object", config=config)


def _record_vertical_receipt(st: FlatGroundGravityState, world: Any, rec: dict[str, Any]) -> None:
    st.counters["vertical_steps"] = int(st.counters.get("vertical_steps", 0)) + 1
    if rec.get("landed"):
        st.counters["landings"] = int(st.counters.get("landings", 0)) + 1
        support_rec = {
            "receipt_kind": RECEIPT_FLAT_SUPPORT,
            "tick": rec.get("tick"),
            "entity_id": rec.get("entity_id"),
            "entity_kind": rec.get("entity_kind"),
            "support_dissipated": rec.get("support_dissipated"),
            "z_after": rec.get("z_after"),
            "vz_after": rec.get("vz_after"),
            "restitution": 0.0,
            "bounce": False,
            "landing_sound": False,
            "researcher_only": True,
        }
        st.last_support = support_rec
        st.support_history.append(support_rec)
        lim = int(st.config.history_limit)
        if len(st.support_history) > lim:
            st.support_history = st.support_history[-lim:]
        world.last_flat_ground_support = support_rec
    elif rec.get("grounded") and rec.get("was_grounded"):
        st.counters["support_rest"] = int(st.counters.get("support_rest", 0)) + 1
    st.last_step = rec
    st.vertical_step_history.append(rec)
    lim = min(int(st.config.history_limit), VERTICAL_STEP_HISTORY_BOUND)
    if len(st.vertical_step_history) > lim:
        st.vertical_step_history = st.vertical_step_history[-lim:]


# ---------------------------------------------------------------------------
# Serialization / catalog / overlay
# ---------------------------------------------------------------------------


def serialize_state(st: FlatGroundGravityState | None) -> dict[str, Any] | None:
    if st is None:
        return None
    return {
        "schema": STATE_SCHEMA,
        "config": st.config.to_dict(),
        "last_vertical_integrated_tick": int(st.last_vertical_integrated_tick),
        "last_body_vertical_ticks": {k: int(v) for k, v in st.last_body_vertical_ticks.items()},
        "counters": dict(st.counters),
        "last_step": dict(st.last_step) if st.last_step else None,
        "last_support": dict(st.last_support) if st.last_support else None,
        "vertical_step_history": list(st.vertical_step_history),
        "support_history": list(st.support_history),
        "banner": BANNER,
        "researcher_only": True,
    }


def restore_state(world: Any, data: dict[str, Any] | None, config: Any) -> FlatGroundGravityState | None:
    if not data or not flat_ground_gravity_is_active(config):
        return None
    raw_cfg = data.get("config")
    if raw_cfg is None:
        cur = getattr(config, "flat_ground_gravity", None)
        raw_cfg = cur.to_dict() if cur is not None and hasattr(cur, "to_dict") else None
    cfg = FlatGroundGravityConfig.from_dict(raw_cfg)
    st = FlatGroundGravityState(
        config=cfg,
        last_vertical_integrated_tick=int(data.get("last_vertical_integrated_tick", -1)),
        last_body_vertical_ticks={str(k): int(v) for k, v in dict(data.get("last_body_vertical_ticks") or {}).items()},
        vertical_step_history=list(data.get("vertical_step_history") or []),
        support_history=list(data.get("support_history") or []),
        last_step=data.get("last_step"),
        last_support=data.get("last_support"),
        counters=dict(data.get("counters") or {}),
    )
    world.flat_ground_gravity_state = st
    return st


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "label": "Flat Ground Gravity V1",
        "config_path": "flat_ground_gravity.enabled",
        "enabled": bool(enabled),
        "promotion_class": "EXPERIMENTAL",
        "provenance": "acanthostega_flat_ground_gravity",
        "default_integrated": True,
        "capabilities": {f: bool(enabled) for f in CAPABILITY_FLAGS},
        "banner": BANNER,
        "FULL_3D_ENTITY_COLLISION": FULL_3D_ENTITY_COLLISION,
        "VERTICAL_FILTER_FOR_EXISTING_HORIZONTAL_CONTACTS": VERTICAL_FILTER_STATUS,
        "surface_elevation": SURFACE_ELEVATION_STATUS,
        "historical_compatibility": "missing key means vertical OFF / 2D contacts",
        "scope": {
            "gravity": True,
            "flat_support": True,
            "vertical_filter": True,
            "slopes": False,
            "stacking": False,
            "landing_sound": False,
        },
    }


def researcher_summary(world: Any) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    return {
        "mechanism": MECHANISM_ID,
        "profile_version": PROFILE_VERSION,
        "banner": BANNER,
        "analyzer_section": ANALYZER_SECTION,
        "capabilities": {f: True for f in CAPABILITY_FLAGS},
        "g": float(st.config.g),
        "ground_z": float(st.config.ground_z),
        "support_profile": SUPPORT_PROFILE,
        "counters": dict(st.counters),
        "last_step": st.last_step,
        "last_support": st.last_support,
        "FULL_3D_ENTITY_COLLISION": FULL_3D_ENTITY_COLLISION,
        "VERTICAL_FILTER_FOR_EXISTING_HORIZONTAL_CONTACTS": VERTICAL_FILTER_STATUS,
        "surface_elevation": SURFACE_ELEVATION_STATUS,
        "agent_accessible": False,
        "researcher_only": True,
    }


def overlay_payload(world: Any) -> dict[str, Any] | None:
    summary = researcher_summary(world)
    if summary is None:
        return None
    return {"caption": BANNER, "active": summary}


def body_vertical_dict(body: Any) -> dict[str, Any]:
    return {
        "z": read_z(body),
        "vz": read_vz(body),
        "grounded": bool(getattr(body, "grounded", True)),
        "vertical_half_extent": float(getattr(body, "vertical_half_extent", BODY_CONTACT_RADIUS) or BODY_CONTACT_RADIUS),
        "centre_z": centre_z_of(body, kind="body"),
    }


def object_vertical_dict(obj: Any) -> dict[str, Any]:
    he = float(getattr(obj, "vertical_half_extent", None) or getattr(obj, "collision_radius", CANONICAL_COLLISION_RADIUS) or CANONICAL_COLLISION_RADIUS)
    return {
        "z": read_z(obj),
        "vz": read_vz(obj),
        "grounded": bool(getattr(obj, "grounded", True)),
        "vertical_half_extent": he,
        "centre_z": read_z(obj) + he,
    }
