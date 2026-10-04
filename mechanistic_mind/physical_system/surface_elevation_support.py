"""Acanthostega ENERGY-ACCOUNTED SURFACE ELEVATION SUPPORT V1.

Preset: ACANTHOSTEGA_PHASE_C_SURFACE_ELEVATION_SUPPORT
Parent: ACANTHOSTEGA_PHASE_C_FREE_OBJECT_GROUND_FRICTION
Mechanism: surface_elevation_support
Profile: SUBGRID_MICRORELIEF_RAMP_V1

CRITICAL CONTRACT
  surface_elevation becomes physical support height.
  EVERY upward ΔU is paid or rejected. NO free snap. NO free PE gain.
  physical_height_scale = 1.0 (SCALE GATE — stop if evidence needs otherwise).
  microrelief_threshold = 0.12 (NOT BODY_CONTACT_RADIUS).
  Centre-path DDA / grid-boundary traversal.
  ENTITY_RADIUS_FACE_SWEEP = NOT_IMPLEMENTED.

Tick order (FREE): source-cell friction → proposal → elev transitions → commit → vertical.
Body: same elev gate after CoM proposal; W_climb debit-on-accept from mechanical_work_reservoir.
Transfer: OCCUPIED_SUPPORT_RISE_REJECTED atomic; ground lower → airborne, no snap.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from mechanistic_mind.planet.topology import wrap_coord

MECHANISM_ID = "surface_elevation_support"
PROFILE_VERSION = "SUBGRID_MICRORELIEF_RAMP_V1"
STATE_SCHEMA = "SURFACE_ELEVATION_SUPPORT_STATE_V1"
RECEIPT_KIND = "SURFACE_ELEVATION_TRANSITION"
EVENT_TRANSITION = "SURFACE_ELEVATION_TRANSITION"

BANNER = (
    "PHASE C · SURFACE ELEVATION SUPPORT V1 · ENERGY-ACCOUNTED MICRORELIEF · "
    "NO FREE PE · CENTRE-PATH DDA · NO RADIUS-FACE · NO SLOPES"
)
OVERLAY_CAPTION = BANNER
ANALYZER_SECTION = "SURFACE ELEVATION SUPPORT / ENERGY-ACCOUNTED MICRORELIEF"

PHYSICAL_HEIGHT_SCALE = 1.0  # SCALE GATE — locked
MICRORELIEF_THRESHOLD = 0.12  # NOT BODY_CONTACT_RADIUS
ENTITY_RADIUS_FACE_SWEEP = "NOT_IMPLEMENTED"
CONTINUOUS_SLOPES = "NOT_IMPLEMENTED"
CLIMB_ACTION = "NOT_IMPLEMENTED"
STACKING = "NOT_IMPLEMENTED"
EXCAVATION = "NOT_IMPLEMENTED"

SUPPORT_SAMPLE_POLICY = "CENTRE_CELL_FLOOR_WRAP_V1"
TRAVERSAL_POLICY = "CENTRE_PATH_DDA_GRID_BOUNDARY_V1"
INITIAL_SUPPORT_PLACEMENT = "INITIAL_SUPPORT_PLACEMENT_V1"
PLACEMENT_POLICY = "EXACT_SUPPORT_HEIGHT_NO_NORMALIZE_V1"

EVENT_LEVEL = "LEVEL"
EVENT_MICRO_UPHILL = "MICRO_UPHILL"
EVENT_LARGE_UPHILL_BLOCKED = "LARGE_UPHILL_BLOCKED"
EVENT_MICRO_DOWNHILL_INELASTIC = "MICRO_DOWNHILL_INELASTIC"
EVENT_LARGE_DOWNHILL_SUPPORT_LOST = "LARGE_DOWNHILL_SUPPORT_LOST"
EVENT_INSUFFICIENT_WORK = "INSUFFICIENT_WORK_BLOCKED"
EVENT_INSUFFICIENT_KINETIC = "INSUFFICIENT_KINETIC_BLOCKED"
EVENT_REST_NEVER_CLIMBS = "REST_NEVER_CLIMBS_BLOCKED"
EVENT_INITIAL_PLACEMENT = "INITIAL_SUPPORT_PLACEMENT"
EVENT_OCCUPIED_RISE_REJECTED = "OCCUPIED_SUPPORT_RISE_REJECTED"
EVENT_GROUND_LOWERED_AIRBORNE = "GROUND_LOWERED_AIRBORNE_NO_SNAP"

HISTORY_LIMIT_DEFAULT = 64
EPS_LEVEL = 1e-12
REST_SPEED_EPS = 1e-9

RESEARCHER_FLAGS = {
    "researcher_only": True,
    "agent_accessible": False,
    "semantic_label": False,
}


# ---------------------------------------------------------------------------
# Scale gate
# ---------------------------------------------------------------------------


class SurfaceElevationScaleGateError(RuntimeError):
    """Raised when physical_height_scale must differ from 1.0 — do not ship free PE."""


def assert_physical_height_scale_gate(scale: float = PHYSICAL_HEIGHT_SCALE) -> float:
    """SCALE GATE: evidence requiring scale≠1.0 is a hard stop (no free PE workaround)."""
    s = float(scale)
    if not math.isfinite(s) or abs(s - 1.0) > 1e-15:
        raise SurfaceElevationScaleGateError(
            f"SCALE_GATE_FAIL: physical_height_scale must be 1.0, got {s!r}. "
            "Do not ship free PE / silent rescale."
        )
    return 1.0


assert_physical_height_scale_gate(PHYSICAL_HEIGHT_SCALE)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass
class SurfaceElevationSupportConfig:
    """Fresh default OFF. Missing snapshot field = OFF."""

    enabled: bool = False
    physical_height_scale: float = PHYSICAL_HEIGHT_SCALE
    microrelief_threshold: float = MICRORELIEF_THRESHOLD
    history_limit: int = HISTORY_LIMIT_DEFAULT
    # Capability flags — always co-gated with the umbrella.
    elevation_as_support: bool = True
    energy_accounted_transitions: bool = True
    centre_path_dda: bool = True
    initial_support_placement: bool = True

    def to_dict(self) -> dict[str, Any]:
        on = bool(self.enabled)
        scale = assert_physical_height_scale_gate(self.physical_height_scale)
        return {
            "enabled": on,
            "physical_height_scale": float(scale),
            "microrelief_threshold": float(self.microrelief_threshold),
            "history_limit": int(self.history_limit),
            "profile_version": PROFILE_VERSION,
            "support_sample_policy": SUPPORT_SAMPLE_POLICY,
            "traversal_policy": TRAVERSAL_POLICY,
            "initial_support_placement": INITIAL_SUPPORT_PLACEMENT,
            "placement_policy": PLACEMENT_POLICY,
            "elevation_as_support": bool(on and self.elevation_as_support),
            "energy_accounted_transitions": bool(on and self.energy_accounted_transitions),
            "centre_path_dda": bool(on and self.centre_path_dda),
            "ENTITY_RADIUS_FACE_SWEEP": ENTITY_RADIUS_FACE_SWEEP,
            "CONTINUOUS_SLOPES": CONTINUOUS_SLOPES,
            "CLIMB_ACTION": CLIMB_ACTION,
            "STACKING": STACKING,
            "EXCAVATION": EXCAVATION,
            "free_pe_snap": False,
            "free_pe_gain": False,
            "body_contact_radius_is_threshold": False,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "SurfaceElevationSupportConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        ver = data.get("profile_version")
        if ver is not None and str(ver) != PROFILE_VERSION:
            raise ValueError(f"unknown surface elevation support profile: {ver}")
        scale = float(data.get("physical_height_scale", PHYSICAL_HEIGHT_SCALE))
        assert_physical_height_scale_gate(scale)
        thr = float(data.get("microrelief_threshold", MICRORELIEF_THRESHOLD))
        if not (math.isfinite(thr) and 0.0 < thr <= 2.0):
            raise ValueError("microrelief_threshold must be in (0, 2]")
        return cls(
            enabled=bool(data.get("enabled", False)),
            physical_height_scale=1.0,
            microrelief_threshold=thr,
            history_limit=int(data.get("history_limit", HISTORY_LIMIT_DEFAULT)),
            elevation_as_support=True,
            energy_accounted_transitions=True,
            centre_path_dda=True,
            initial_support_placement=True,
        )


def validate_config(cfg: SurfaceElevationSupportConfig) -> None:
    assert_physical_height_scale_gate(cfg.physical_height_scale)
    thr = float(cfg.microrelief_threshold)
    if not (math.isfinite(thr) and 0.0 < thr <= 2.0):
        raise ValueError("microrelief_threshold must be in (0, 2]")
    if not (1 <= int(cfg.history_limit) <= 512):
        raise ValueError("history_limit must be in [1, 512]")
    # Threshold must NOT be BODY_CONTACT_RADIUS (0.35).
    from mechanistic_mind.physical_system.physical_body_resource_object_contact import (
        BODY_CONTACT_RADIUS,
    )
    if abs(thr - float(BODY_CONTACT_RADIUS)) < 1e-15:
        raise ValueError(
            "microrelief_threshold must NOT equal BODY_CONTACT_RADIUS; locked at 0.12"
        )


def _line_ok(config: Any) -> bool:
    return config is not None and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"


def surface_elevation_support_is_active(config: Any) -> bool:
    if not _line_ok(config):
        return False
    cfg = getattr(config, "surface_elevation_support", None)
    if cfg is None or not bool(getattr(cfg, "enabled", False)):
        return False
    from mechanistic_mind.physical_system.free_resource_object_ground_friction import (
        free_resource_object_ground_friction_is_active,
    )
    from mechanistic_mind.physical_system.procedural_surface_columns import (
        procedural_surface_columns_is_active,
    )
    return bool(
        free_resource_object_ground_friction_is_active(config)
        and procedural_surface_columns_is_active(config)
    )



def set_surface_elevation_support(config: Any, enabled: bool) -> None:
    if config is None:
        return
    on = bool(enabled) and _line_ok(config)
    cur = getattr(config, "surface_elevation_support", None)
    if cur is None:
        if on:
            config.surface_elevation_support = SurfaceElevationSupportConfig(enabled=True)
        return
    if isinstance(cur, dict):
        cfg = SurfaceElevationSupportConfig.from_dict(cur)
        cfg.enabled = on
        config.surface_elevation_support = cfg
    else:
        cur.enabled = on


def capability_flags(config: Any) -> dict[str, bool]:
    on = surface_elevation_support_is_active(config)
    return {
        "elevation_as_support": bool(on),
        "energy_accounted_transitions": bool(on),
        "centre_path_dda": bool(on),
        "initial_support_placement": bool(on),
    }


# ---------------------------------------------------------------------------
# Shared support-height helper (no silent 0 when elev active)
# ---------------------------------------------------------------------------


def _dims(world: Any) -> tuple[int, int]:
    t = getattr(world, "T", None)
    return (int(t.shape[1]), int(t.shape[0])) if t is not None else (32, 32)


def cell_of(x: float, y: float, *, width: int, height: int) -> tuple[int, int]:
    return (
        int(wrap_coord(int(math.floor(float(x))), int(width))),
        int(wrap_coord(int(math.floor(float(y))), int(height))),
    )


def surface_support_height(world: Any, x: float, y: float, *, config: Any | None = None) -> float:
    """Physical support height at (x,y). When elevation support is active: never silent 0.

    physical_support_height = physical_height_scale * raw_elevation  (scale locked at 1.0).
    Inactive / columns absent with mechanism OFF → 0.0 (flat ground).
    Active without column state → raises (no silent zero).

    When continuous_surface_geometry is ON: bilinear cell-centre lattice h(x,y)
    (G1). At cell centres this equals the discrete sample. SES DDA still uses
    support_height_at_cell (exact centres) for energy/blocking.
    """
    scale = assert_physical_height_scale_gate(PHYSICAL_HEIGHT_SCALE)
    active = surface_elevation_support_active_on_world(world, config)

    from mechanistic_mind.physical_system import procedural_surface_columns as psc

    st = psc.state_of(world)
    if not active:
        return 0.0
    if st is None:
        raise RuntimeError(
            "surface_support_height: elevation support active but procedural columns "
            "state missing — refusing silent 0"
        )
    # G1 continuous support (optional child of BNLT). Missing key → discrete path.
    if config is not None:
        from mechanistic_mind.physical_system.continuous_surface_geometry import (
            continuous_surface_geometry_is_active,
            continuous_support_height,
        )
        if continuous_surface_geometry_is_active(config):
            csg_st = getattr(world, "continuous_surface_geometry_state", None)
            if csg_st is not None:
                csg_st.counters["support_queries"] = int(
                    csg_st.counters.get("support_queries", 0)
                ) + 1
            return float(continuous_support_height(world, x, y, config=config))
    col = psc.resolved_column_at(world, x, y, record=False)
    raw = float(col["surface_elevation"])
    if not math.isfinite(raw):
        raise RuntimeError(
            f"surface_support_height: non-finite elevation at ({x},{y}) — refusing silent 0"
        )
    return float(scale) * raw


def support_height_at_cell(world: Any, cell_x: int, cell_y: int, *, config: Any | None = None) -> float:
    return surface_support_height(world, float(cell_x) + 0.5, float(cell_y) + 0.5, config=config)


# ---------------------------------------------------------------------------
# Centre-path DDA / grid-boundary traversal
# ---------------------------------------------------------------------------


def _unwrap_delta(dx: float, width: float) -> float:
    """Shortest signed wrap delta on a periodic axis of length width."""
    w = float(width)
    if w <= 0:
        return float(dx)
    d = float(dx)
    while d > 0.5 * w:
        d -= w
    while d < -0.5 * w:
        d += w
    return d


def centre_path_boundary_crossings(
    x0: float, y0: float, x1: float, y1: float, *, width: int, height: int,
) -> list[dict[str, Any]]:
    """DDA-style grid boundary crossings along the centre path (unwrap short wrap).

    Returns ordered crossings: each has from_cell, to_cell, t in (0,1], position.
    ENTITY_RADIUS_FACE_SWEEP is NOT_IMPLEMENTED — centre only.
    """
    w, h = int(width), int(height)
    dx = _unwrap_delta(float(x1) - float(x0), w)
    dy = _unwrap_delta(float(y1) - float(y0), h)
    if abs(dx) < 1e-15 and abs(dy) < 1e-15:
        return []

    # Work in unwrapped coordinates from start.
    sx, sy = float(x0), float(y0)
    ex, ey = sx + dx, sy + dy

    crossings: list[dict[str, Any]] = []
    # Collect candidate boundary parameters t.
    candidates: list[tuple[float, str, int]] = []  # (t, axis, boundary_index)

    if abs(dx) > 1e-15:
        x_lo = math.floor(min(sx, ex)) + (1 if dx > 0 else 0)
        x_hi = math.ceil(max(sx, ex)) - (0 if dx > 0 else 1)
        # Vertical lines x = integer between sx and ex
        if dx > 0:
            xb = math.floor(sx) + 1
            while xb < ex - 1e-15:
                t = (xb - sx) / dx
                if 0.0 < t <= 1.0 + 1e-15:
                    candidates.append((float(t), "x", int(xb)))
                xb += 1
        else:
            xb = math.ceil(sx) - 1
            while xb > ex + 1e-15:
                t = (xb - sx) / dx
                if 0.0 < t <= 1.0 + 1e-15:
                    candidates.append((float(t), "x", int(xb)))
                xb -= 1

    if abs(dy) > 1e-15:
        if dy > 0:
            yb = math.floor(sy) + 1
            while yb < ey - 1e-15:
                t = (yb - sy) / dy
                if 0.0 < t <= 1.0 + 1e-15:
                    candidates.append((float(t), "y", int(yb)))
                yb += 1
        else:
            yb = math.ceil(sy) - 1
            while yb > ey + 1e-15:
                t = (yb - sy) / dy
                if 0.0 < t <= 1.0 + 1e-15:
                    candidates.append((float(t), "y", int(yb)))
                yb -= 1

    # Sort by t; resolve corner hits (same t) as sequential x then y for determinism.
    candidates.sort(key=lambda c: (round(c[0], 12), 0 if c[1] == "x" else 1, c[2]))

    prev_cell = cell_of(sx, sy, width=w, height=h)
    seen_t: set[float] = set()
    for t, axis, _b in candidates:
        tr = round(t, 12)
        if tr in seen_t and False:
            pass
        seen_t.add(tr)
        # Position just after boundary to determine to_cell.
        eps = 1e-9
        px = sx + dx * min(1.0, t + eps)
        py = sy + dy * min(1.0, t + eps)
        to_cell = cell_of(px, py, width=w, height=h)
        if to_cell == prev_cell:
            continue
        crossings.append({
            "t": float(t),
            "axis": axis,
            "from_cell": [int(prev_cell[0]), int(prev_cell[1])],
            "to_cell": [int(to_cell[0]), int(to_cell[1])],
            "position": [float(sx + dx * t), float(sy + dy * t)],
            "traversal_policy": TRAVERSAL_POLICY,
            "ENTITY_RADIUS_FACE_SWEEP": ENTITY_RADIUS_FACE_SWEEP,
        })
        prev_cell = to_cell

    # Ensure final cell transition is recorded if start/end cells differ with no crossing
    # (e.g. started exactly on a boundary). Compare wrapped end cell.
    end_cell = cell_of(float(x0) + dx, float(y0) + dy, width=w, height=h)
    start_cell = cell_of(sx, sy, width=w, height=h)
    if end_cell != start_cell and (not crossings or tuple(crossings[-1]["to_cell"]) != end_cell):
        # If we never crossed but cells differ, synthesize a terminal crossing at t=1.
        if not crossings:
            crossings.append({
                "t": 1.0,
                "axis": "terminal",
                "from_cell": [int(start_cell[0]), int(start_cell[1])],
                "to_cell": [int(end_cell[0]), int(end_cell[1])],
                "position": [float(x0) + dx, float(y0) + dy],
                "traversal_policy": TRAVERSAL_POLICY,
                "ENTITY_RADIUS_FACE_SWEEP": ENTITY_RADIUS_FACE_SWEEP,
            })
    return crossings


def classify_elevation_transition(
    h_from: float, h_to: float, *, threshold: float = MICRORELIEF_THRESHOLD,
) -> dict[str, Any]:
    dh = float(h_to) - float(h_from)
    thr = float(threshold)
    if abs(dh) <= EPS_LEVEL:
        kind = EVENT_LEVEL
    elif dh > 0.0:
        kind = EVENT_MICRO_UPHILL if dh <= thr + EPS_LEVEL else EVENT_LARGE_UPHILL_BLOCKED
    else:
        kind = EVENT_MICRO_DOWNHILL_INELASTIC if abs(dh) <= thr + EPS_LEVEL else EVENT_LARGE_DOWNHILL_SUPPORT_LOST
    return {
        "event_kind": kind,
        "h_from": float(h_from),
        "h_to": float(h_to),
        "delta_h": float(dh),
        "microrelief_threshold": thr,
        "uphill": bool(dh > EPS_LEVEL),
        "downhill": bool(dh < -EPS_LEVEL),
        "level": bool(abs(dh) <= EPS_LEVEL),
    }


# ---------------------------------------------------------------------------
# Energy helpers
# ---------------------------------------------------------------------------


def climb_work(mass: float, g: float, delta_h: float) -> float:
    """W_climb = m_eff * g * Δh for upward Δh > 0; else 0."""
    dh = float(delta_h)
    if dh <= EPS_LEVEL:
        return 0.0
    return float(mass) * float(g) * dh


def normal_kinetic(mass: float, vx: float, vy: float, nx: float, ny: float) -> tuple[float, float, float]:
    """K_normal = 1/2 m v_n^2 along unit normal (nx,ny) pointing into the step (uphill direction of travel).

    Returns (K_n, v_n, speed).
    """
    nlen = math.hypot(nx, ny)
    if nlen <= 1e-15:
        return 0.0, 0.0, float(math.hypot(vx, vy))
    ux, uy = nx / nlen, ny / nlen
    vn = float(vx) * ux + float(vy) * uy
    # Only the approaching (positive into step) component pays.
    vn_pay = max(0.0, vn)
    kn = 0.5 * float(mass) * vn_pay * vn_pay
    return float(kn), float(vn), float(math.hypot(vx, vy))


def reduce_normal_velocity(
    vx: float, vy: float, nx: float, ny: float, *, energy_paid: float, mass: float,
) -> tuple[float, float]:
    """Remove enough of the normal component that Δ(1/2 m v_n^2) ~= energy_paid."""
    nlen = math.hypot(nx, ny)
    if nlen <= 1e-15 or mass <= 0.0:
        return float(vx), float(vy)
    ux, uy = nx / nlen, ny / nlen
    vn = float(vx) * ux + float(vy) * uy
    if vn <= 0.0:
        return float(vx), float(vy)
    kn = 0.5 * float(mass) * vn * vn
    kn1 = max(0.0, kn - float(energy_paid))
    vn1 = math.sqrt(2.0 * kn1 / float(mass)) if kn1 > 0.0 else 0.0
    # Keep tangential; replace normal.
    vtx = float(vx) - vn * ux
    vty = float(vy) - vn * uy
    return vtx + vn1 * ux, vty + vn1 * uy


def _read_g(world: Any) -> float:
    from mechanistic_mind.physical_system.flat_ground_gravity import GRAVITY_ACCELERATION
    st = getattr(world, "flat_ground_gravity_state", None)
    if st is not None and getattr(st, "config", None) is not None:
        return float(getattr(st.config, "g", GRAVITY_ACCELERATION))
    return float(GRAVITY_ACCELERATION)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class SurfaceElevationSupportState:
    config: SurfaceElevationSupportConfig
    last_transition: dict[str, Any] | None = None
    history: list[dict[str, Any]] = field(default_factory=list)
    placement_done: bool = False
    counters: dict[str, int] = field(default_factory=lambda: {
        "transitions": 0,
        "level": 0,
        "micro_uphill_accepted": 0,
        "micro_uphill_blocked": 0,
        "large_uphill_blocked": 0,
        "micro_downhill": 0,
        "large_downhill_support_lost": 0,
        "initial_placements": 0,
        "occupied_rise_rejected": 0,
        "ground_lowered_airborne": 0,
        "body_work_debits": 0,
        "free_kinetic_payments": 0,
        "paths_blocked": 0,
        "paths_committed": 0,
    })


def state_of(world: Any) -> SurfaceElevationSupportState | None:
    raw = getattr(world, "surface_elevation_support_state", None)
    return raw if isinstance(raw, SurfaceElevationSupportState) else None


def surface_elevation_support_active_on_world(world: Any, config: Any | None = None) -> bool:
    """World-step helper: use config when provided; else require SES+FOGF+columns state."""
    if config is not None:
        return surface_elevation_support_is_active(config)
    st = state_of(world)
    if st is None or not bool(getattr(st.config, "enabled", False)):
        return False
    from mechanistic_mind.physical_system.free_resource_object_ground_friction import state_of as fogf_state
    from mechanistic_mind.physical_system.procedural_surface_columns import state_of as psc_state
    return fogf_state(world) is not None and psc_state(world) is not None


def ensure_surface_elevation_support_for_runtime(
    world: Any, config: Any,
) -> SurfaceElevationSupportState | None:
    if not surface_elevation_support_is_active(config):
        if state_of(world) is not None:
            world.surface_elevation_support_state = None
        return None
    st = state_of(world)
    if st is not None:
        return st
    raw = getattr(config, "surface_elevation_support", None)
    cfg = (
        SurfaceElevationSupportConfig.from_dict(raw.to_dict() if hasattr(raw, "to_dict") else raw)
        if raw is not None
        else SurfaceElevationSupportConfig(enabled=True)
    )
    cfg.enabled = True
    validate_config(cfg)
    st = SurfaceElevationSupportState(config=cfg)
    world.surface_elevation_support_state = st
    return st


# ---------------------------------------------------------------------------
# INITIAL_SUPPORT_PLACEMENT
# ---------------------------------------------------------------------------


def apply_initial_support_placement(world: Any, config: Any, *, bodies: list[Any] | None = None) -> dict[str, Any]:
    """Place every grounded entity exactly on local support height. No normalize to 0.

    Restore must call with exact heights (no re-normalize). Idempotent per state.placement_done
    except when forced via bodies/objects already present after Apply/reset.
    """
    st = ensure_surface_elevation_support_for_runtime(world, config)
    if st is None:
        return {"applied": False, "reason": "inactive"}
    placed: list[dict[str, Any]] = []
    # Objects
    for obj in list(getattr(world, "resource_objects", None) or []):
        ps = str(getattr(obj, "physical_state", "") or "")
        if ps == "HELD":
            continue
        h = surface_support_height(world, float(obj.x), float(obj.y), config=config)
        obj.z = float(h)  # EXACT — no normalize
        obj.vz = 0.0
        obj.grounded = True
        placed.append({"kind": "object", "id": str(obj.object_id), "z": float(h)})
        st.counters["initial_placements"] = int(st.counters.get("initial_placements", 0)) + 1
    for body in list(bodies or []):
        if body is None:
            continue
        h = surface_support_height(world, float(body.x), float(body.y), config=config)
        body.z = float(h)
        body.vz = 0.0
        body.grounded = True
        bid = str(getattr(body, "body_id", None) or getattr(body, "id", None) or "body")
        placed.append({"kind": "body", "id": bid, "z": float(h)})
        st.counters["initial_placements"] = int(st.counters.get("initial_placements", 0)) + 1
    st.placement_done = True
    receipt = {
        "receipt_kind": RECEIPT_KIND,
        "event_kind": EVENT_INITIAL_PLACEMENT,
        "placement_policy": PLACEMENT_POLICY,
        "n_placed": len(placed),
        "placed": placed[:32],
        "normalize": False,
        "free_pe_snap": False,
        **RESEARCHER_FLAGS,
    }
    _record(st, world, receipt)
    return {"applied": True, "receipt": receipt}


# ---------------------------------------------------------------------------
# Transactional transition gate
# ---------------------------------------------------------------------------


def evaluate_path_transitions(
    world: Any,
    config: Any,
    *,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    vx: float,
    vy: float,
    mass: float,
    entity_kind: str,
    entity_id: str,
    work_reservoir: float | None = None,
    grounded: bool = True,
    z: float = 0.0,
    radius: float = 0.0,
    tick: int | None = None,
) -> dict[str, Any]:
    """Transactional elev gate over centre-path crossings. No mutation.

    Returns plan with accept/reject, event_kinds, final pose/velocity proposal,
    work debit / kinetic payment, support-lost flag.
    """
    st = state_of(world)
    if st is None or not surface_elevation_support_active_on_world(world, config):
        return {
            "active": False,
            "accepted": True,
            "x": float(x1),
            "y": float(y1),
            "vx": float(vx),
            "vy": float(vy),
            "z": float(z),
            "grounded": bool(grounded),
            "event_kinds": [],
            "work_debit": 0.0,
            "kinetic_paid": 0.0,
            "support_lost": False,
        }

    w, h = _dims(world)
    thr = float(st.config.microrelief_threshold)
    g = _read_g(world)
    crossings = centre_path_boundary_crossings(x0, y0, x1, y1, width=w, height=h)

    # Policy C mutex: when endpoint owns gravitational PE, SES still gates
    # topology / affordability but must not charge climb/descent PE.
    try:
        from mechanistic_mind.physical_system.continuous_gravitational_pe import (
            ses_gravitational_charge_suppressed as _ses_pe_suppressed,
        )
        _endpoint_owns_pe = bool(_ses_pe_suppressed(config))
    except Exception:
        _endpoint_owns_pe = False

    vx_c, vy_c = float(vx), float(vy)
    z_c = float(z)
    grounded_c = bool(grounded)
    work_left = None if work_reservoir is None else float(work_reservoir)
    work_debit = 0.0
    kinetic_paid = 0.0
    event_kinds: list[str] = []
    steps: list[dict[str, Any]] = []
    support_lost = False

    # If already airborne (support lost previously), horizontal proposal passes;
    # elevation transitions apply only while supported / contacting support.
    if not grounded_c:
        return {
            "active": True,
            "accepted": True,
            "x": float(x1),
            "y": float(y1),
            "vx": vx_c,
            "vy": vy_c,
            "z": z_c,
            "grounded": False,
            "event_kinds": [EVENT_LEVEL],
            "work_debit": 0.0,
            "kinetic_paid": 0.0,
            "support_lost": False,
            "crossings": [],
            "airborne_passthrough": True,
        }

    for cross in crossings:
        fc = (int(cross["from_cell"][0]), int(cross["from_cell"][1]))
        tc = (int(cross["to_cell"][0]), int(cross["to_cell"][1]))
        h0 = support_height_at_cell(world, fc[0], fc[1], config=config)
        h1 = support_height_at_cell(world, tc[0], tc[1], config=config)
        cls = classify_elevation_transition(h0, h1, threshold=thr)
        kind = cls["event_kind"]
        dh = float(cls["delta_h"])
        step = {**cls, **cross, "entity_kind": entity_kind, "entity_id": entity_id}

        if kind == EVENT_LEVEL:
            event_kinds.append(EVENT_LEVEL)
            steps.append(step)
            continue

        if kind == EVENT_LARGE_UPHILL_BLOCKED:
            event_kinds.append(EVENT_LARGE_UPHILL_BLOCKED)
            step["accepted"] = False
            steps.append(step)
            return _maybe_apply_face_sweep(
                world, config,
                {
                    "active": True,
                    "accepted": False,
                    "block_reason": EVENT_LARGE_UPHILL_BLOCKED,
                    "x": float(x0),
                    "y": float(y0),
                    "vx": 0.0 if entity_kind == "object" else float(vx),  # FREE: stop into face
                    "vy": 0.0 if entity_kind == "object" else float(vy),
                    "z": z_c,
                    "grounded": grounded_c,
                    "event_kinds": event_kinds,
                    "work_debit": work_debit,
                    "kinetic_paid": kinetic_paid,
                    "support_lost": False,
                    "steps": steps,
                    "crossings": crossings,
                },
                x0=float(x0), y0=float(y0), x1=float(x1), y1=float(y1),
                radius=float(radius), entity_kind=str(entity_kind), entity_id=str(entity_id),
                tick=tick,
            )

        if kind == EVENT_MICRO_UPHILL:
            w_climb = climb_work(mass, g, dh)
            speed = math.hypot(vx_c, vy_c)
            # Rest never climbs (FREE only). Body CoM proposals pay from work reservoir
            # even when instantaneous speed is ~0 after a locomotor step.
            if speed <= REST_SPEED_EPS and str(entity_kind) != "body":
                event_kinds.append(EVENT_REST_NEVER_CLIMBS)
                step["accepted"] = False
                step["block_reason"] = EVENT_REST_NEVER_CLIMBS
                steps.append(step)
                return {
                    "active": True,
                    "accepted": False,
                    "block_reason": EVENT_REST_NEVER_CLIMBS,
                    "x": float(x0), "y": float(y0),
                    "vx": 0.0, "vy": 0.0,
                    "z": z_c, "grounded": True,
                    "event_kinds": event_kinds,
                    "work_debit": work_debit,
                    "kinetic_paid": kinetic_paid,
                    "support_lost": False,
                    "steps": steps,
                    "crossings": crossings,
                }

            # Step normal ≈ direction of travel into the higher cell.
            nx = float(tc[0] - fc[0])
            ny = float(tc[1] - fc[1])
            if abs(nx) < 1e-15 and abs(ny) < 1e-15:
                nx, ny = dx_hat(x0, y0, x1, y1, w, h)

            if entity_kind == "body":
                if work_left is None or work_left + 1e-15 < w_climb:
                    event_kinds.append(EVENT_INSUFFICIENT_WORK)
                    step["accepted"] = False
                    step["W_climb"] = w_climb
                    step["work_available"] = work_left
                    steps.append(step)
                    return {
                        "active": True,
                        "accepted": False,
                        "block_reason": EVENT_INSUFFICIENT_WORK,
                        "x": float(x0), "y": float(y0),
                        "vx": float(vx), "vy": float(vy),
                        "z": z_c, "grounded": True,
                        "event_kinds": event_kinds,
                        "work_debit": work_debit,
                        "kinetic_paid": kinetic_paid,
                        "support_lost": False,
                        "steps": steps,
                        "W_climb": w_climb,
                        "crossings": crossings,
                    }
                work_left = float(work_left) - w_climb  # affordability reservation
                if not _endpoint_owns_pe:
                    work_debit += w_climb
                z_c = float(h1)  # follow support up
                event_kinds.append(EVENT_MICRO_UPHILL)
                step["accepted"] = True
                step["W_climb"] = w_climb
                step["payment"] = (
                    "endpoint_authority_deferred"
                    if _endpoint_owns_pe
                    else "mechanical_work_reservoir"
                )
                step["ses_gravitational_charge_suppressed"] = bool(_endpoint_owns_pe)
                steps.append(step)
            else:
                # FREE: gate on K_normal; pay from K_normal unless endpoint owns PE.
                kn, vn, _spd = normal_kinetic(mass, vx_c, vy_c, nx, ny)
                if kn + 1e-15 < w_climb:
                    event_kinds.append(EVENT_INSUFFICIENT_KINETIC)
                    step["accepted"] = False
                    step["W_climb"] = w_climb
                    step["K_normal"] = kn
                    steps.append(step)
                    return {
                        "active": True,
                        "accepted": False,
                        "block_reason": EVENT_INSUFFICIENT_KINETIC,
                        "x": float(x0), "y": float(y0),
                        "vx": 0.0, "vy": 0.0,
                        "z": z_c, "grounded": True,
                        "event_kinds": event_kinds,
                        "work_debit": work_debit,
                        "kinetic_paid": kinetic_paid,
                        "support_lost": False,
                        "steps": steps,
                        "W_climb": w_climb,
                        "K_normal": kn,
                        "crossings": crossings,
                    }
                if not _endpoint_owns_pe:
                    vx_c, vy_c = reduce_normal_velocity(
                        vx_c, vy_c, nx, ny, energy_paid=w_climb, mass=mass
                    )
                    kinetic_paid += w_climb
                z_c = float(h1)
                event_kinds.append(EVENT_MICRO_UPHILL)
                step["accepted"] = True
                step["W_climb"] = w_climb
                step["K_normal_before"] = kn
                step["payment"] = (
                    "endpoint_authority_deferred" if _endpoint_owns_pe else "K_normal"
                )
                step["ses_gravitational_charge_suppressed"] = bool(_endpoint_owns_pe)
                steps.append(step)
            continue

        if kind == EVENT_MICRO_DOWNHILL_INELASTIC:
            # Follow support down; PE loss dissipated (no KE gain) unless endpoint owns PE.
            pe_drop = float(mass) * g * abs(dh)
            z_c = float(h1)
            event_kinds.append(EVENT_MICRO_DOWNHILL_INELASTIC)
            step["accepted"] = True
            if _endpoint_owns_pe:
                step["dissipated_pe"] = 0.0
                step["dissipated_pe_suppressed_for_endpoint_authority"] = pe_drop
                step["ses_gravitational_charge_suppressed"] = True
            else:
                step["dissipated_pe"] = pe_drop
            step["ke_gain"] = 0.0
            steps.append(step)
            continue

        if kind == EVENT_LARGE_DOWNHILL_SUPPORT_LOST:
            # Support drops; z remains; become airborne. NO snap.
            support_lost = True
            grounded_c = False
            # z_c unchanged
            event_kinds.append(EVENT_LARGE_DOWNHILL_SUPPORT_LOST)
            step["accepted"] = True
            step["support_lost"] = True
            step["z_remains"] = z_c
            step["new_support"] = float(h1)
            step["snap"] = False
            steps.append(step)
            # Further crossings while airborne: passthrough
            break

    # Wrap final position for commit proposal.
    x_out = float(wrap_coord(float(x0) + _unwrap_delta(float(x1) - float(x0), w), w))
    y_out = float(wrap_coord(float(y0) + _unwrap_delta(float(y1) - float(y0), h), h))
    # If still grounded and no large drop, snap z to destination support (paid path).
    if grounded_c and not support_lost:
        z_c = surface_support_height(world, x_out, y_out, config=config)

    if not event_kinds:
        event_kinds.append(EVENT_LEVEL)

    plan = {
        "active": True,
        "accepted": True,
        "x": x_out,
        "y": y_out,
        "vx": float(vx_c),
        "vy": float(vy_c),
        "z": float(z_c),
        "grounded": bool(grounded_c),
        "event_kinds": event_kinds,
        "work_debit": float(work_debit),
        "kinetic_paid": float(kinetic_paid),
        "support_lost": bool(support_lost),
        "steps": steps,
        "crossings": crossings,
        "mass": float(mass),
        "g": float(g),
        "microrelief_threshold": thr,
        "free_pe_snap": False,
        "free_pe_gain": False,
        "ses_gravitational_charge_suppressed": bool(_endpoint_owns_pe),
    }
    plan = _maybe_apply_face_sweep(
        world, config, plan,
        x0=float(x0), y0=float(y0), x1=float(x1), y1=float(y1),
        radius=float(radius), entity_kind=str(entity_kind), entity_id=str(entity_id),
        tick=tick,
    )
    # Policy C: compute exclusive endpoint ΔU after topology/face-sweep gate.
    if _endpoint_owns_pe:
        from mechanistic_mind.physical_system.continuous_gravitational_pe import (
            annotate_plan_endpoint_pe,
        )
        plan = annotate_plan_endpoint_pe(
            world, config, plan,
            x0=float(x0), y0=float(y0), mass=float(mass),
            entity_kind=str(entity_kind),
            work_reservoir=None if work_reservoir is None else float(work_reservoir),
        )
    return plan


def _maybe_apply_face_sweep(
    world: Any,
    config: Any,
    plan: dict[str, Any],
    *,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    radius: float,
    entity_kind: str,
    entity_id: str,
    tick: int | None,
) -> dict[str, Any]:
    """Attach radius-aware face-sweep evidence before commit (Policy C). No PE/work."""
    try:
        from mechanistic_mind.physical_system.radius_aware_face_sweep import (
            apply_face_sweep_to_plan,
            radius_aware_face_sweep_active_on_world,
        )
    except Exception:
        return plan
    if not radius_aware_face_sweep_active_on_world(world, config):
        return plan
    tk = int(tick) if tick is not None else int(getattr(world, "tick", 0) or 0)
    return apply_face_sweep_to_plan(
        world, config, plan,
        x0=float(x0), y0=float(y0), x1=float(x1), y1=float(y1),
        radius=float(radius), entity_kind=str(entity_kind), entity_id=str(entity_id),
        tick=tk,
    )


def dx_hat(x0, y0, x1, y1, w, h):
    dx = _unwrap_delta(float(x1) - float(x0), w)
    dy = _unwrap_delta(float(y1) - float(y0), h)
    L = math.hypot(dx, dy)
    if L <= 1e-15:
        return 1.0, 0.0
    return dx / L, dy / L


def commit_free_object_elevation_gate(
    world: Any,
    config: Any,
    obj: Any,
    *,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    vx: float,
    vy: float,
    tick: int,
) -> dict[str, Any]:
    """Apply elev gate to a FREE object proposal. Mutates obj on accept/reject."""
    st = state_of(world)
    if st is None:
        if config is not None:
            st = ensure_surface_elevation_support_for_runtime(world, config)
    if st is None or not surface_elevation_support_active_on_world(world, config):
        return {"active": False, "accepted": True, "x": x1, "y": y1, "vx": vx, "vy": vy}

    mass = float(getattr(obj, "mass", 1.0) or 1.0)
    z0 = float(getattr(obj, "z", 0.0) or 0.0)
    grounded = bool(getattr(obj, "grounded", True))
    from mechanistic_mind.physical_system.radius_aware_face_sweep import (
        object_face_sweep_radius as _obj_fs_r,
    )
    plan = evaluate_path_transitions(
        world, config,
        x0=x0, y0=y0, x1=x1, y1=y1,
        vx=vx, vy=vy, mass=mass,
        entity_kind="object",
        entity_id=str(getattr(obj, "object_id", "")),
        work_reservoir=None,
        grounded=grounded,
        z=z0,
        radius=float(_obj_fs_r(obj)),
        tick=int(tick),
    )
    if not plan.get("active"):
        return plan

    if plan["accepted"]:
        # Policy C: apply exclusive endpoint PE to plan velocities before pose write.
        try:
            from mechanistic_mind.physical_system.continuous_gravitational_pe import (
                apply_endpoint_pe_to_free_object as _apply_ep_free,
                endpoint_pe_physically_active as _ep_active,
                record_policy_c_receipt as _rec_pc,
            )
            if _ep_active(config):
                _apply_ep_free(plan, mass=float(mass))
                _rec_pc(
                    world, config, plan,
                    entity_kind="object",
                    entity_id=str(getattr(obj, "object_id", "")),
                    tick=int(tick),
                )
                st.counters["endpoint_pe_free_charges"] = (
                    int(st.counters.get("endpoint_pe_free_charges", 0)) + 1
                )
        except Exception:
            pass
        obj.x = float(plan["x"])
        obj.y = float(plan["y"])
        obj.vx = float(plan["vx"])
        obj.vy = float(plan["vy"])
        obj.z = float(plan["z"])
        obj.grounded = bool(plan["grounded"])
        if plan.get("support_lost"):
            st.counters["large_downhill_support_lost"] = int(st.counters.get("large_downhill_support_lost", 0)) + 1
        if EVENT_MICRO_UPHILL in plan.get("event_kinds", []):
            st.counters["micro_uphill_accepted"] = int(st.counters.get("micro_uphill_accepted", 0)) + 1
            st.counters["free_kinetic_payments"] = int(st.counters.get("free_kinetic_payments", 0)) + 1
        if EVENT_MICRO_DOWNHILL_INELASTIC in plan.get("event_kinds", []):
            st.counters["micro_downhill"] = int(st.counters.get("micro_downhill", 0)) + 1
        if EVENT_LEVEL in plan.get("event_kinds", []) and len(set(plan.get("event_kinds", []))) == 1:
            st.counters["level"] = int(st.counters.get("level", 0)) + 1
        st.counters["paths_committed"] = int(st.counters.get("paths_committed", 0)) + 1
    else:
        obj.x = float(plan["x"])
        obj.y = float(plan["y"])
        obj.vx = float(plan["vx"])
        obj.vy = float(plan["vy"])
        reason = str(plan.get("block_reason") or "")
        if reason == EVENT_LARGE_UPHILL_BLOCKED:
            st.counters["large_uphill_blocked"] = int(st.counters.get("large_uphill_blocked", 0)) + 1
        elif reason == "RADIUS_FACE_BARRIER":
            st.counters["radius_face_barrier_blocked"] = int(st.counters.get("radius_face_barrier_blocked", 0)) + 1
        elif reason in (EVENT_INSUFFICIENT_KINETIC, EVENT_REST_NEVER_CLIMBS):
            st.counters["micro_uphill_blocked"] = int(st.counters.get("micro_uphill_blocked", 0)) + 1
        st.counters["paths_blocked"] = int(st.counters.get("paths_blocked", 0)) + 1
        try:
            from mechanistic_mind.physical_system.continuous_gravitational_pe import (
                endpoint_pe_physically_active as _ep_active2,
                record_policy_c_receipt as _rec_pc2,
            )
            if _ep_active2(config):
                plan["endpoint_pe_applied"] = 0.0
                plan["endpoint_pe_dissipated"] = 0.0
                plan["kinetic_paid"] = 0.0
                _rec_pc2(
                    world, config, plan,
                    entity_kind="object",
                    entity_id=str(getattr(obj, "object_id", "")),
                    tick=int(tick),
                )
        except Exception:
            pass

    receipt = {
        "receipt_kind": RECEIPT_KIND,
        "event": EVENT_TRANSITION,
        "tick": int(tick),
        "entity_kind": "object",
        "entity_id": str(getattr(obj, "object_id", "")),
        "event_kinds": list(plan.get("event_kinds") or []),
        "accepted": bool(plan["accepted"]),
        "block_reason": plan.get("block_reason"),
        "start_position": [float(x0), float(y0)],
        "end_position": [float(obj.x), float(obj.y)],
        "z_before": float(z0),
        "z_after": float(obj.z),
        "grounded_after": bool(obj.grounded),
        "work_debit": float(plan.get("work_debit") or 0.0),
        "kinetic_paid": float(plan.get("kinetic_paid") or 0.0),
        "support_lost": bool(plan.get("support_lost")),
        "microrelief_threshold": float(st.config.microrelief_threshold),
        "physical_height_scale": 1.0,
        "traversal_policy": TRAVERSAL_POLICY,
        "ENTITY_RADIUS_FACE_SWEEP": ENTITY_RADIUS_FACE_SWEEP,
        "free_pe_snap": False,
        "free_pe_gain": False,
        "banner": BANNER,
        **RESEARCHER_FLAGS,
    }
    _record(st, world, receipt)
    plan["receipt"] = receipt

    # G2C1: exactly one SES decomposition contract receipt per path-gate evaluation
    # (researcher-only, read-only; config may be None on this seam -> world-state activity).
    from mechanistic_mind.physical_system.ses_decomposition_contract import (
        emit_path_gate_contract_receipt as _sdc_emit,
    )
    _sdc_emit(
        world, config, plan=plan, entity=obj, entity_kind="object",
        entity_id=str(getattr(obj, "object_id", "")), tick=int(tick),
        x0=float(x0), y0=float(y0), z0=float(z0), grounded_before=bool(grounded),
        microrelief_threshold=float(st.config.microrelief_threshold),
    )
    # G2C2: runtime transition classification AFTER SES resolution (read-only; PE-safe).
    from mechanistic_mind.physical_system.ses_runtime_transition_classifier import (
        emit_path_gate_classification as _srtc_emit,
    )
    _srtc_emit(
        world, config, plan=plan, entity=obj, entity_kind="object",
        entity_id=str(getattr(obj, "object_id", "")), tick=int(tick),
        x0=float(x0), y0=float(y0),
        x_proposed=float(x1), y_proposed=float(y1),
        z0=float(z0), grounded_before=bool(grounded),
        microrelief_threshold=float(st.config.microrelief_threshold),
    )
    try:
        from mechanistic_mind.physical_system.radius_aware_face_sweep import (
            object_face_sweep_radius as _ofr,
            record_face_sweep_receipt as _fs_rec,
        )
        _fs_rec(
            world, plan=plan, tick=int(tick), entity_kind="object",
            entity_id=str(getattr(obj, "object_id", "")),
            x0=float(x0), y0=float(y0), x_proposed=float(x1), y_proposed=float(y1),
            x_realized=float(obj.x), y_realized=float(obj.y),
            radius=float(_ofr(obj)),
        )
    except Exception:
        pass

    # Continuous gravitational PE diagnostic shadow (researcher-only; post-commit; PE-safe).
    try:
        from mechanistic_mind.physical_system.continuous_gravitational_pe_diagnostic_shadow import (
            observe_path_gate_pe_shadow as _cgpe_obs,
        )
        _cgpe_obs(
            world, config, plan=plan, entity=obj, entity_kind="object",
            entity_id=str(getattr(obj, "object_id", "")),
            x0=float(x0), y0=float(y0), z0=float(z0),
            grounded_before=bool(grounded),
            m_eff=float(mass), g=float(_read_g(world)),
            tick=int(tick),
        )
    except Exception:
        pass

    return plan


def commit_body_elevation_gate(
    world: Any,
    config: Any,
    body: Any,
    *,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    body_id: str,
    body_mass: float,
    tick: int,
) -> dict[str, Any]:
    """Apply elev gate to a body CoM proposal. Debits mechanical_work_reservoir on accept."""
    st = ensure_surface_elevation_support_for_runtime(world, config)
    if st is None:
        return {"active": False, "accepted": True, "x": x1, "y": y1}

    from mechanistic_mind.physical_system.effector_work_and_held_load_inertia_accounting import (
        locomotor_mass_with_held_load,
    )
    mass_info = locomotor_mass_with_held_load(
        body_mass=float(body_mass),
        world=world,
        holder_body_id=str(body_id),
        config=config,
    )
    m_eff = float(mass_info.get("effective_mass") or body_mass)
    w0 = float(getattr(body, "mechanical_work_reservoir", 0.0) or 0.0)
    z0 = float(getattr(body, "z", 0.0) or 0.0)
    grounded = bool(getattr(body, "grounded", True))
    vx = float(getattr(body, "vx", 0.0) or 0.0)
    vy = float(getattr(body, "vy", 0.0) or 0.0)

    from mechanistic_mind.physical_system.radius_aware_face_sweep import (
        body_face_sweep_radius as _body_fs_r,
    )
    plan = evaluate_path_transitions(
        world, config,
        x0=x0, y0=y0, x1=x1, y1=y1,
        vx=vx, vy=vy, mass=m_eff,
        entity_kind="body",
        entity_id=str(body_id),
        work_reservoir=w0,
        grounded=grounded,
        z=z0,
        radius=float(_body_fs_r(body)),
        tick=int(tick),
    )
    if not plan.get("active"):
        return plan

    if plan["accepted"]:
        body.x = float(plan["x"])
        body.y = float(plan["y"])
        body.z = float(plan["z"])
        body.grounded = bool(plan["grounded"])
        # Policy C: exclusive endpoint gravitational PE replaces SES work_debit.
        _endpoint_pe = False
        try:
            from mechanistic_mind.physical_system.continuous_gravitational_pe import (
                apply_endpoint_pe_to_body as _apply_ep_body,
                endpoint_pe_physically_active as _ep_active,
                record_policy_c_receipt as _rec_pc,
            )
            _endpoint_pe = bool(_ep_active(config))
        except Exception:
            _endpoint_pe = False
        if _endpoint_pe:
            _apply_ep_body(body, plan, work_reservoir_before=w0)
            debit = float(plan.get("work_debit") or 0.0)
            if debit > 0.0 or float(plan.get("endpoint_pe_dissipated") or 0.0) > 0.0:
                st.counters["body_work_debits"] = int(st.counters.get("body_work_debits", 0)) + 1
                st.counters["endpoint_pe_body_charges"] = (
                    int(st.counters.get("endpoint_pe_body_charges", 0)) + 1
                )
            _rec_pc(
                world, config, plan,
                entity_kind="body", entity_id=str(body_id), tick=int(tick),
            )
        else:
            debit = float(plan.get("work_debit") or 0.0)
            if debit > 0.0:
                body.mechanical_work_reservoir = max(0.0, w0 - debit)
                st.counters["body_work_debits"] = int(st.counters.get("body_work_debits", 0)) + 1
        if EVENT_MICRO_UPHILL in plan.get("event_kinds", []):
            st.counters["micro_uphill_accepted"] = int(st.counters.get("micro_uphill_accepted", 0)) + 1
        if EVENT_MICRO_DOWNHILL_INELASTIC in plan.get("event_kinds", []):
            st.counters["micro_downhill"] = int(st.counters.get("micro_downhill", 0)) + 1
        if plan.get("support_lost"):
            st.counters["large_downhill_support_lost"] = int(st.counters.get("large_downhill_support_lost", 0)) + 1
        st.counters["paths_committed"] = int(st.counters.get("paths_committed", 0)) + 1
    else:
        body.x = float(plan["x"])
        body.y = float(plan["y"])
        # Rejected displacement must not keep the velocity that proposed it
        # (no delayed barrier launch). Cancel proposal-aligned velocity and
        # record explicit KE dissipation. Orthogonal residual is conserved.
        reason = str(plan.get("block_reason") or "")
        vx_b = float(getattr(body, "vx", 0.0) or 0.0)
        vy_b = float(getattr(body, "vy", 0.0) or 0.0)
        dx_p = float(x1) - float(x0)
        dy_p = float(y1) - float(y0)
        plen = float(math.hypot(dx_p, dy_p))
        ke_before = 0.5 * float(m_eff) * (vx_b * vx_b + vy_b * vy_b)
        if plen > 1e-15:
            ux, uy = dx_p / plen, dy_p / plen
            v_par = vx_b * ux + vy_b * uy
            # Remove only the component into the rejected displacement.
            if v_par > 0.0:
                vx_b = vx_b - v_par * ux
                vy_b = vy_b - v_par * uy
            elif v_par < 0.0 and reason in (
                EVENT_LARGE_UPHILL_BLOCKED,
                "RADIUS_FACE_BARRIER",
                "RADIUS_FACE_BARRIER_HARD_CAP",
            ):
                # Against a barrier from either approach: kill normal approach.
                vx_b = vx_b - v_par * ux
                vy_b = vy_b - v_par * uy
        else:
            # Zero-length proposal but blocked (shouldn't): leave velocity.
            pass
        body.vx = float(vx_b)
        body.vy = float(vy_b)
        ke_after = 0.5 * float(m_eff) * (vx_b * vx_b + vy_b * vy_b)
        plan["blocked_velocity_ke_before"] = float(ke_before)
        plan["blocked_velocity_ke_after"] = float(ke_after)
        plan["blocked_velocity_ke_dissipated"] = float(max(0.0, ke_before - ke_after))
        plan["blocked_velocity_response"] = "REMOVE_PROPOSAL_ALIGNED_COMPONENT"
        if reason == EVENT_LARGE_UPHILL_BLOCKED:
            st.counters["large_uphill_blocked"] = int(st.counters.get("large_uphill_blocked", 0)) + 1
        elif reason == "RADIUS_FACE_BARRIER":
            st.counters["radius_face_barrier_blocked"] = int(st.counters.get("radius_face_barrier_blocked", 0)) + 1
        elif reason in (EVENT_INSUFFICIENT_WORK, EVENT_REST_NEVER_CLIMBS):
            st.counters["micro_uphill_blocked"] = int(st.counters.get("micro_uphill_blocked", 0)) + 1
        st.counters["paths_blocked"] = int(st.counters.get("paths_blocked", 0)) + 1
        if float(plan.get("blocked_velocity_ke_dissipated") or 0.0) > 1e-15:
            st.counters["blocked_velocity_ke_dissipated_events"] = int(
                st.counters.get("blocked_velocity_ke_dissipated_events", 0)
            ) + 1
        try:
            from mechanistic_mind.physical_system.continuous_gravitational_pe import (
                endpoint_pe_physically_active as _ep_active2,
                record_policy_c_receipt as _rec_pc2,
            )
            if _ep_active2(config):
                # Ensure no charge fields on reject.
                plan["endpoint_pe_applied"] = 0.0
                plan["endpoint_pe_dissipated"] = 0.0
                plan["work_debit"] = 0.0
                _rec_pc2(
                    world, config, plan,
                    entity_kind="body", entity_id=str(body_id), tick=int(tick),
                )
        except Exception:
            pass

    receipt = {
        "receipt_kind": RECEIPT_KIND,
        "event": EVENT_TRANSITION,
        "tick": int(tick),
        "entity_kind": "body",
        "entity_id": str(body_id),
        "event_kinds": list(plan.get("event_kinds") or []),
        "accepted": bool(plan["accepted"]),
        "block_reason": plan.get("block_reason"),
        "start_position": [float(x0), float(y0)],
        "end_position": [float(body.x), float(body.y)],
        "z_before": float(z0),
        "z_after": float(getattr(body, "z", z0)),
        "grounded_after": bool(getattr(body, "grounded", True)),
        "m_eff": float(m_eff),
        "held_mass": float(mass_info.get("held_mass") or 0.0),
        "work_debit": float(plan.get("work_debit") or 0.0),
        "mechanical_work_reservoir_before": float(w0),
        "mechanical_work_reservoir_after": float(getattr(body, "mechanical_work_reservoir", w0) or 0.0),
        "support_lost": bool(plan.get("support_lost")),
        "microrelief_threshold": float(st.config.microrelief_threshold),
        "physical_height_scale": 1.0,
        "traversal_policy": TRAVERSAL_POLICY,
        "free_pe_snap": False,
        "free_pe_gain": False,
        "banner": BANNER,
        **RESEARCHER_FLAGS,
    }
    _record(st, world, receipt)
    plan["receipt"] = receipt

    # G2C1: exactly one SES decomposition contract receipt per path-gate evaluation
    # (researcher-only, read-only).
    from mechanistic_mind.physical_system.ses_decomposition_contract import (
        emit_path_gate_contract_receipt as _sdc_emit,
    )
    _sdc_emit(
        world, config, plan=plan, entity=body, entity_kind="body",
        entity_id=str(body_id), tick=int(tick),
        x0=float(x0), y0=float(y0), z0=float(z0), grounded_before=bool(grounded),
        microrelief_threshold=float(st.config.microrelief_threshold),
    )
    # G2C2: runtime transition classification AFTER SES resolution (read-only; PE-safe).
    from mechanistic_mind.physical_system.ses_runtime_transition_classifier import (
        emit_path_gate_classification as _srtc_emit,
    )
    _srtc_emit(
        world, config, plan=plan, entity=body, entity_kind="body",
        entity_id=str(body_id), tick=int(tick),
        x0=float(x0), y0=float(y0),
        x_proposed=float(x1), y_proposed=float(y1),
        z0=float(z0), grounded_before=bool(grounded),
        microrelief_threshold=float(st.config.microrelief_threshold),
    )
    # Face-sweep receipt (researcher-only; zero PE/work).
    try:
        from mechanistic_mind.physical_system.radius_aware_face_sweep import (
            body_face_sweep_radius as _bfr,
            record_face_sweep_receipt as _fs_rec,
        )
        _fs_rec(
            world, plan=plan, tick=int(tick), entity_kind="body", entity_id=str(body_id),
            x0=float(x0), y0=float(y0), x_proposed=float(x1), y_proposed=float(y1),
            x_realized=float(body.x), y_realized=float(body.y),
            radius=float(_bfr(body)),
        )
    except Exception:
        pass

    # Continuous gravitational PE diagnostic shadow (researcher-only; post-commit; PE-safe).
    try:
        from mechanistic_mind.physical_system.continuous_gravitational_pe_diagnostic_shadow import (
            observe_path_gate_pe_shadow as _cgpe_obs,
        )
        _cgpe_obs(
            world, config, plan=plan, entity=body, entity_kind="body",
            entity_id=str(body_id),
            x0=float(x0), y0=float(y0), z0=float(z0),
            grounded_before=bool(grounded),
            m_eff=float(m_eff), g=float(_read_g(world)),
            held_mass=float(mass_info.get("held_mass") or 0.0),
            body_mass=float(body_mass),
            tick=int(tick),
        )
    except Exception:
        pass

    return plan


# ---------------------------------------------------------------------------
# Mutation preflight: occupied support rise
# ---------------------------------------------------------------------------


def occupied_entities_at_cell(world: Any, cell_x: int, cell_y: int, *, width: int, height: int) -> list[dict[str, Any]]:
    """Bodies + FREE objects whose floor-wrap cell matches (held excluded from ground occupancy)."""
    cx = int(wrap_coord(int(cell_x), int(width)))
    cy = int(wrap_coord(int(cell_y), int(height)))
    out: list[dict[str, Any]] = []
    for obj in list(getattr(world, "resource_objects", None) or []):
        ps = str(getattr(obj, "physical_state", "") or "")
        if ps == "HELD":
            continue
        ocx, ocy = cell_of(float(obj.x), float(obj.y), width=width, height=height)
        if ocx == cx and ocy == cy:
            out.append({
                "kind": "object",
                "id": str(obj.object_id),
                "z": float(getattr(obj, "z", 0.0) or 0.0),
                "grounded": bool(getattr(obj, "grounded", True)),
                "entity": obj,
            })
    return out


def preflight_occupied_support_rise(
    world: Any,
    config: Any,
    *,
    cell_x: int,
    cell_y: int,
    elevation_before: float,
    elevation_after: float,
    tick: int | None = None,
) -> dict[str, Any]:
    """Atomic reject if any grounded occupant would gain free PE from a support rise.

    ``tick`` is G2C1 provenance metadata only (never read by the decision)."""
    if not surface_elevation_support_is_active(config):
        return {"reject": False, "reason": None, "active": False}
    dh = float(elevation_after) - float(elevation_before)
    w, h = _dims(world)
    occupants = occupied_entities_at_cell(world, cell_x, cell_y, width=w, height=h)
    grounded_occ = [o for o in occupants if o["grounded"]]
    if dh > EPS_LEVEL and grounded_occ:
        st = state_of(world)
        if st is not None:
            st.counters["occupied_rise_rejected"] = int(st.counters.get("occupied_rise_rejected", 0)) + 1
            receipt = {
                "receipt_kind": RECEIPT_KIND,
                "event_kind": EVENT_OCCUPIED_RISE_REJECTED,
                "cell": [int(cell_x), int(cell_y)],
                "elevation_before": float(elevation_before),
                "elevation_after": float(elevation_after),
                "delta_h": float(dh),
                "occupants": [{"kind": o["kind"], "id": o["id"], "z": o["z"]} for o in grounded_occ],
                "free_pe_prevented": True,
                **RESEARCHER_FLAGS,
            }
            _record(st, world, receipt)
            # G2C1: one contract receipt per grounded occupant (read-only).
            from mechanistic_mind.physical_system.ses_decomposition_contract import (
                emit_mutation_contract_receipts as _sdc_emit_mut,
            )
            _sdc_emit_mut(
                world, config, provenance="OCCUPIED_SUPPORT_RISE",
                cell=(int(cell_x), int(cell_y)), rows=grounded_occ,
                elevation_before=float(elevation_before), elevation_after=float(elevation_after),
                microrelief_threshold=float(st.config.microrelief_threshold), tick=tick,
            )
            # G2C2: runtime classification of mutation-associated support rise (read-only).
            from mechanistic_mind.physical_system.ses_runtime_transition_classifier import (
                emit_mutation_classifications as _srtc_emit_mut,
            )
            _srtc_emit_mut(
                world, config, provenance="OCCUPIED_SUPPORT_RISE",
                cell=(int(cell_x), int(cell_y)), rows=grounded_occ,
                elevation_before=float(elevation_before), elevation_after=float(elevation_after),
                microrelief_threshold=float(st.config.microrelief_threshold), tick=tick,
            )
        return {
            "reject": True,
            "reason": EVENT_OCCUPIED_RISE_REJECTED,
            "active": True,
            "occupants": grounded_occ,
            "delta_h": float(dh),
        }
    return {"reject": False, "reason": None, "active": True, "occupants": occupants, "delta_h": float(dh)}


def apply_ground_lowered_to_occupants(
    world: Any,
    config: Any,
    *,
    cell_x: int,
    cell_y: int,
    elevation_after: float,
    tick: int | None = None,
    elevation_before: float | None = None,
    transaction_id: str | None = None,
    sparse_revision: int | None = None,
) -> list[dict[str, Any]]:
    """When support lowers under grounded occupants: become airborne, z remains (no snap).

    ``tick`` is G2C1 provenance metadata only (never read by the decision).
    When Free-Space V1D is ON, delegates to the shared release/excavation refresh
    (bodies + FREE + bilinear + RASP + per-entity/tick dedup)."""
    if not surface_elevation_support_is_active(config):
        return []
    try:
        from mechanistic_mind.physical_system.release_and_excavation_support_loss_integration import (
            refresh_support_after_terrain_mutation,
            release_and_excavation_support_loss_integration_is_active,
        )

        if release_and_excavation_support_loss_integration_is_active(config):
            return refresh_support_after_terrain_mutation(
                world,
                config,
                cell_x=int(cell_x),
                cell_y=int(cell_y),
                elevation_before=elevation_before,
                elevation_after=float(elevation_after),
                tick=tick,
                transaction_id=transaction_id,
                sparse_revision=sparse_revision,
            )
    except Exception:
        pass
    w, h = _dims(world)
    scale = assert_physical_height_scale_gate()
    new_h = float(scale) * float(elevation_after)
    changed: list[dict[str, Any]] = []
    changed_rows: list[dict[str, Any]] = []  # G2C1 read-only provenance
    st = state_of(world)
    for row in occupied_entities_at_cell(world, cell_x, cell_y, width=w, height=h):
        ent = row["entity"]
        if not row["grounded"]:
            continue
        z = float(row["z"])
        if z > new_h + EPS_LEVEL:
            ent.grounded = False
            # z remains — NO snap
            changed.append({
                "id": row["id"],
                "kind": row["kind"],
                "z_remains": z,
                "new_support": new_h,
                "event_kind": EVENT_GROUND_LOWERED_AIRBORNE,
                "snap": False,
            })
            changed_rows.append(row)
            if st is not None:
                st.counters["ground_lowered_airborne"] = int(st.counters.get("ground_lowered_airborne", 0)) + 1
            try:
                from mechanistic_mind.physical_system.free_space_state_and_pe_authority_contract import (
                    free_space_state_and_pe_authority_contract_is_active,
                    note_support_loss_terrain_mutation,
                )
                from mechanistic_mind.physical_system.flat_ground_gravity import (
                    vertical_half_extent_of,
                )

                if free_space_state_and_pe_authority_contract_is_active(config):
                    he = vertical_half_extent_of(
                        ent,
                        kind="body" if row["kind"] == "body" else "object",
                        config=config,
                    )
                    note_support_loss_terrain_mutation(
                        world,
                        config,
                        tick=int(tick) if tick is not None else -1,
                        entity_id=str(row["id"]),
                        entity_kind=str(row["kind"]),
                        z=float(z),
                        vz=float(getattr(ent, "vz", 0.0) or 0.0),
                        support_z_after=float(new_h),
                        half_extent=float(he),
                    )
                from mechanistic_mind.physical_system.vertical_terrain_landing_contact_response import (
                    end_episode_for_entity,
                )

                end_episode_for_entity(
                    world,
                    config,
                    entity_kind=str(row["kind"]),
                    entity_id=str(row["id"]),
                    tick=int(tick) if tick is not None else -1,
                    reason="SUPPORT_LOSS_TERRAIN_MUTATION",
                )
            except Exception:
                pass
    if changed and st is not None:
        _record(st, world, {
            "receipt_kind": RECEIPT_KIND,
            "event_kind": EVENT_GROUND_LOWERED_AIRBORNE,
            "cell": [int(cell_x), int(cell_y)],
            "changed": changed,
            "snap": False,
            **RESEARCHER_FLAGS,
        })
    if changed_rows and st is not None:
        # G2C1: one contract receipt per occupant made airborne (read-only).
        from mechanistic_mind.physical_system.ses_decomposition_contract import (
            emit_mutation_contract_receipts as _sdc_emit_mut,
        )
        _sdc_emit_mut(
            world, config, provenance="GROUND_LOWERED",
            cell=(int(cell_x), int(cell_y)), rows=changed_rows,
            elevation_before=None, elevation_after=float(new_h),
            microrelief_threshold=float(st.config.microrelief_threshold), tick=tick,
        )
        # G2C2: runtime classification of ground-lowered support loss (read-only).
        from mechanistic_mind.physical_system.ses_runtime_transition_classifier import (
            emit_mutation_classifications as _srtc_emit_mut,
        )
        _srtc_emit_mut(
            world, config, provenance="GROUND_LOWERED",
            cell=(int(cell_x), int(cell_y)), rows=changed_rows,
            elevation_before=None, elevation_after=float(new_h),
            microrelief_threshold=float(st.config.microrelief_threshold), tick=tick,
        )
    return changed


# ---------------------------------------------------------------------------
# Vertical support_z hook for FGG
# ---------------------------------------------------------------------------


def support_z_for_entity(
    world: Any,
    config: Any,
    x: float,
    y: float,
    *,
    z: float | None = None,
) -> float:
    """Support height used by vertical integrator. Flat 0 when mechanism OFF.

    When VW2 is active, ``z`` (entity lower extent) is provided, **and** the XY
    cell has a sparse VW1 occupancy override, support is derived from volumetric
    occupancy at/below ``z`` — never from legacy max projected surface alone.
    Missing support below returns ``NO_SUPPORT_SENTINEL``.

    Ordinary PSC/CSG columns without a sparse override keep the pre-VW2
    ``surface_support_height`` path so continuous bilinear support remains
    bit-stable until VW3 materializes occupancy mutations. Cavity / multi-Z
    columns must be sparse overrides (VW1 ``set_volumetric_column`` / future VW3).
    """
    if not surface_elevation_support_is_active(config):
        return 0.0
    try:
        from mechanistic_mind.physical_system.occupancy_support_and_contact_queries import (
            NO_SUPPORT_SENTINEL,
            occupancy_support_and_contact_queries_is_active,
            support_boundary_z_for_vertical_integrator,
        )
        from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
            state_of as vo_state,
            wrap_cell,
        )

        if occupancy_support_and_contact_queries_is_active(config) and z is not None and math.isfinite(float(z)):
            st = vo_state(world)
            if st is not None:
                cell = wrap_cell(st, x, y)
                if cell in st.columns:
                    boundary, _ = support_boundary_z_for_vertical_integrator(
                        world, x, y, float(z), config=config
                    )
                    if boundary is None:
                        return float(NO_SUPPORT_SENTINEL)
                    return float(boundary)
    except Exception:
        pass
    return surface_support_height(world, x, y, config=config)


# ---------------------------------------------------------------------------
# Serialization / catalog / overlay
# ---------------------------------------------------------------------------


def _record(st: SurfaceElevationSupportState, world: Any, receipt: dict[str, Any]) -> None:
    st.counters["transitions"] = int(st.counters.get("transitions", 0)) + 1
    st.last_transition = receipt
    st.history.append(receipt)
    lim = int(st.config.history_limit)
    if len(st.history) > lim:
        st.history = st.history[-lim:]
    world.last_surface_elevation_transition = receipt


def serialize_state(st: SurfaceElevationSupportState | None) -> dict[str, Any] | None:
    if st is None:
        return None
    return {
        "schema": STATE_SCHEMA,
        "config": st.config.to_dict(),
        "counters": dict(st.counters),
        "last_transition": dict(st.last_transition) if st.last_transition else None,
        "history": list(st.history),
        "placement_done": bool(st.placement_done),
        "banner": BANNER,
        "researcher_only": True,
    }


def restore_state(world: Any, data: dict[str, Any] | None, config: Any) -> SurfaceElevationSupportState | None:
    if not surface_elevation_support_is_active(config):
        world.surface_elevation_support_state = None
        return None
    if not isinstance(data, dict) or not data:
        return ensure_surface_elevation_support_for_runtime(world, config)
    if data.get("schema") not in (None, STATE_SCHEMA) and str(data.get("schema")) != STATE_SCHEMA:
        raise ValueError(f"unknown surface elevation support state schema: {data.get('schema')}")
    raw_cfg = data.get("config")
    if raw_cfg is None:
        cur = getattr(config, "surface_elevation_support", None)
        raw_cfg = cur.to_dict() if cur is not None and hasattr(cur, "to_dict") else None
    cfg = SurfaceElevationSupportConfig.from_dict(raw_cfg)
    validate_config(cfg)
    st = SurfaceElevationSupportState(
        config=cfg,
        last_transition=dict(data["last_transition"]) if isinstance(data.get("last_transition"), dict) else None,
        history=list(data.get("history") or []),
        placement_done=bool(data.get("placement_done", False)),
        counters={**{
            "transitions": 0, "level": 0, "micro_uphill_accepted": 0, "micro_uphill_blocked": 0,
            "large_uphill_blocked": 0, "micro_downhill": 0, "large_downhill_support_lost": 0,
            "initial_placements": 0, "occupied_rise_rejected": 0, "ground_lowered_airborne": 0,
            "body_work_debits": 0, "free_kinetic_payments": 0, "paths_blocked": 0, "paths_committed": 0,
        }, **{k: int(v) for k, v in dict(data.get("counters") or {}).items()}},
    )
    world.surface_elevation_support_state = st
    # Restore exact support heights — NO normalize.
    return st


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "label": "Surface Elevation Support V1",
        "config_path": "surface_elevation_support.enabled",
        "enabled": bool(enabled),
        "promotion_class": "EXPERIMENTAL",
        "provenance": "acanthostega_surface_elevation_support",
        "default_integrated": True,
        "banner": BANNER,
        "analyzer_section": ANALYZER_SECTION,
        "profile_version": PROFILE_VERSION,
        "physical_height_scale": 1.0,
        "microrelief_threshold": MICRORELIEF_THRESHOLD,
        "ENTITY_RADIUS_FACE_SWEEP": ENTITY_RADIUS_FACE_SWEEP,
        "CONTINUOUS_SLOPES": CONTINUOUS_SLOPES,
        "free_pe_snap": False,
        "free_pe_gain": False,
        "capabilities": {
            "elevation_as_support": bool(enabled),
            "energy_accounted_transitions": bool(enabled),
            "centre_path_dda": bool(enabled),
            "initial_support_placement": bool(enabled),
        },
        "scope": {
            "bodies": True,
            "free_objects": True,
            "held": False,
            "slopes": False,
            "stacking": False,
            "climb_action": False,
            "radius_face": False,
        },
        "historical_compatibility": "missing key means elevation support OFF / flat ground_z=0",
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
        "counters": dict(st.counters),
        "last_transition": st.last_transition,
        "physical_height_scale": 1.0,
        "microrelief_threshold": float(st.config.microrelief_threshold),
        "ENTITY_RADIUS_FACE_SWEEP": ENTITY_RADIUS_FACE_SWEEP,
        "free_pe_snap": False,
        "free_pe_gain": False,
        "agent_accessible": False,
        "researcher_only": True,
    }


def overlay_payload(world: Any) -> dict[str, Any] | None:
    summary = researcher_summary(world)
    if summary is None:
        return None
    return {"caption": BANNER, "active": summary}
