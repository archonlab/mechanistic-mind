"""Acanthostega PHASE C · RADIUS-AWARE FACE SWEEP — SES PLAN EVIDENCE V1.

Preset: ACANTHOSTEGA_PHASE_C_RADIUS_AWARE_FACE_SWEEP
Parent: ACANTHOSTEGA_PHASE_C_SES_RUNTIME_CLASSIFIER
Mechanism: radius_aware_face_sweep
Profile: RADIUS_AWARE_FACE_SWEEP_SES_PLAN_EVIDENCE_V1

Policy C: face-sweep geometry evidence → SES single decision/commit.
May propose a topology block. Must NOT charge PE/work, mutate pose, or rollback.

Geometry: RADIUS_EXPANDED_CELL_ENUM_PLUS_SWEPT_DISK_VS_CELL_FACE_DISCONTINUITY_V1
PE authority: PE_AUTHORITY_SES_DDA (unchanged; face_sweep_work_delta=0, face_sweep_pe_delta=0)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable

from mechanistic_mind.physical_system.physical_body_resource_object_contact import (
    BODY_CONTACT_RADIUS,
)
from mechanistic_mind.physical_system.ses_decomposition_contract import (
    PE_AUTHORITY_SES_DDA,
    ses_decomposition_contract_is_active,
)
from mechanistic_mind.physical_system.ses_runtime_transition_classifier import (
    ses_runtime_transition_classifier_is_active,
)
from mechanistic_mind.physical_system.surface_elevation_support import (
    MICRORELIEF_THRESHOLD,
    surface_elevation_support_is_active,
)
from mechanistic_mind.planet.topology import wrap_coord

MECHANISM_ID = "radius_aware_face_sweep"
PROFILE_VERSION = "RADIUS_AWARE_FACE_SWEEP_SES_PLAN_EVIDENCE_V1"
STAGE_ALIAS = "RADIUS_AWARE_FACE_SWEEP_SES_PLAN_EVIDENCE_V1"
STATE_SCHEMA = "RADIUS_AWARE_FACE_SWEEP_STATE_V1"
RECEIPT_KIND = "RADIUS_AWARE_FACE_SWEEP"
GEOMETRY_PROFILE = (
    "RADIUS_EXPANDED_CELL_ENUM_PLUS_SWEPT_DISK_VS_CELL_FACE_DISCONTINUITY_V1"
)

# SES block reason (topology; no PE).
EVENT_RADIUS_FACE_BARRIER = "RADIUS_FACE_BARRIER"

BANNER = (
    "RADIUS-AWARE FACE SWEEP · SES PLAN EVIDENCE · "
    "PE AUTHORITY: SES DDA · NO RADIUS PE"
)
OVERLAY_CAPTION = BANNER
ANALYZER_SECTION = "RADIUS-AWARE FACE-SWEEP EVENTS"

SOFT_CANDIDATE_CELL_CAP = 256
# Hard cap: conservative block rather than silent accept (never drop then claim clear).
HARD_CANDIDATE_CELL_CAP = 1024

EPS_RADIUS = 1e-12
EPS_PATH = 1e-15
EPS_T = 1e-12
EPS_PEN = 1e-9
EPS_DIST = 1e-12

HISTORY_LIMIT_DEFAULT = 64

EVAL_EXACT = "EXACT"
EVAL_SOFT_CAP = "SOFT_CAP_WARNING"
EVAL_HARD_CAP = "HARD_CAP_CONSERVATIVE_BLOCK"
EVAL_SKIPPED_ZERO_RADIUS = "SKIPPED_ZERO_RADIUS"
EVAL_SKIPPED_NO_MOTION = "SKIPPED_NO_MOTION"
EVAL_INACTIVE = "INACTIVE"

PEN_NONE = "NONE"
PEN_OUTWARD = "OUTWARD_ALLOWED"
PEN_DEEPER = "DEEPER_BLOCKED"
PEN_TANGENTIAL = "TANGENTIAL_NO_CHANGE"

SOURCE_CENTRE = "CENTRE_SES_PATH"
SOURCE_RADIUS = "RADIUS_ONLY"
SOURCE_BOTH = "CENTRE_AND_RADIUS"
SOURCE_NONE = "NONE"

RESEARCHER_FLAGS = {
    "researcher_only": True,
    "agent_accessible": False,
    "semantic_label": False,
    "face_sweep_work_delta": 0.0,
    "face_sweep_pe_delta": 0.0,
}


# ---------------------------------------------------------------------------
# Config / activation
# ---------------------------------------------------------------------------


@dataclass
class RadiusAwareFaceSweepConfig:
    enabled: bool = False
    history_limit: int = HISTORY_LIMIT_DEFAULT
    soft_candidate_cell_cap: int = SOFT_CANDIDATE_CELL_CAP
    hard_candidate_cell_cap: int = HARD_CANDIDATE_CELL_CAP
    microrelief_threshold: float = MICRORELIEF_THRESHOLD
    pe_authority: str = PE_AUTHORITY_SES_DDA

    def to_dict(self) -> dict[str, Any]:
        on = bool(self.enabled)
        return {
            "enabled": on,
            "history_limit": int(self.history_limit),
            "soft_candidate_cell_cap": int(self.soft_candidate_cell_cap),
            "hard_candidate_cell_cap": int(self.hard_candidate_cell_cap),
            "microrelief_threshold": float(self.microrelief_threshold),
            "pe_authority": str(self.pe_authority),
            "profile_version": PROFILE_VERSION,
            "stage_alias": STAGE_ALIAS,
            "geometry_profile": GEOMETRY_PROFILE,
            "face_sweep_may_block": True,
            "face_sweep_may_charge_pe": False,
            "face_sweep_work_delta": 0.0,
            "face_sweep_pe_delta": 0.0,
            "classifier_controls_physics": False,
            "normal_physical_effects_active": False,
            "physics_equivalence_version": "RAFS_BIT_IDENTICAL_WHEN_NO_RADIUS_BARRIER_V1",
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "RadiusAwareFaceSweepConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        ver = data.get("profile_version")
        if ver is not None and str(ver) != PROFILE_VERSION:
            raise ValueError(f"unknown radius_aware_face_sweep profile: {ver}")
        return cls(
            enabled=bool(data.get("enabled", False)),
            history_limit=int(data.get("history_limit", HISTORY_LIMIT_DEFAULT)),
            soft_candidate_cell_cap=int(
                data.get("soft_candidate_cell_cap", SOFT_CANDIDATE_CELL_CAP)
            ),
            hard_candidate_cell_cap=int(
                data.get("hard_candidate_cell_cap", HARD_CANDIDATE_CELL_CAP)
            ),
            microrelief_threshold=float(
                data.get("microrelief_threshold", MICRORELIEF_THRESHOLD)
            ),
            pe_authority=str(data.get("pe_authority", PE_AUTHORITY_SES_DDA)),
        )


def validate_config(cfg: RadiusAwareFaceSweepConfig) -> None:
    if not (1 <= int(cfg.history_limit) <= 512):
        raise ValueError("history_limit must be in [1, 512]")
    if not (1 <= int(cfg.soft_candidate_cell_cap) <= int(cfg.hard_candidate_cell_cap)):
        raise ValueError("soft_candidate_cell_cap must be in [1, hard_cap]")
    if int(cfg.hard_candidate_cell_cap) > 4096:
        raise ValueError("hard_candidate_cell_cap too large")
    if float(cfg.microrelief_threshold) <= 0.0:
        raise ValueError("microrelief_threshold must be > 0")


def _line_ok(config: Any) -> bool:
    return (
        config is not None
        and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"
    )


def radius_aware_face_sweep_is_active(config: Any) -> bool:
    if not _line_ok(config):
        return False
    cfg = getattr(config, "radius_aware_face_sweep", None)
    if cfg is None or not bool(getattr(cfg, "enabled", False)):
        return False
    return bool(
        ses_runtime_transition_classifier_is_active(config)
        and ses_decomposition_contract_is_active(config)
        and surface_elevation_support_is_active(config)
    )


def radius_aware_face_sweep_active_on_world(world: Any, config: Any | None = None) -> bool:
    if config is not None:
        return radius_aware_face_sweep_is_active(config) and state_of(world) is not None
    st = state_of(world)
    return st is not None and bool(st.config.enabled)


def set_radius_aware_face_sweep(config: Any, enabled: bool) -> None:
    if config is None:
        return
    on = bool(enabled) and _line_ok(config)
    cur = getattr(config, "radius_aware_face_sweep", None)
    if cur is None:
        if on:
            config.radius_aware_face_sweep = RadiusAwareFaceSweepConfig(enabled=True)
        return
    if isinstance(cur, dict):
        cfg = RadiusAwareFaceSweepConfig.from_dict(cur)
        cfg.enabled = on
        config.radius_aware_face_sweep = cfg
    else:
        cur.enabled = on


def body_face_sweep_radius(_body: Any = None) -> float:
    return float(BODY_CONTACT_RADIUS)


def object_face_sweep_radius(obj: Any) -> float:
    from mechanistic_mind.physical_system.physical_body_resource_object_contact import (
        ensure_object_collision_radius,
    )
    return float(ensure_object_collision_radius(obj))


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class RadiusAwareFaceSweepState:
    config: RadiusAwareFaceSweepConfig
    last_receipt: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=lambda: _default_counters())
    applied_keys_tick: int | None = None
    applied_keys: set = field(default_factory=set)
    restore_suppress_until_tick: int | None = None
    last_error: str | None = None
    # Non-authoritative; never serialized.
    _query_cache: dict = field(default_factory=dict, repr=False)
    _cache_generation: int = 0


def _default_counters() -> dict[str, int]:
    return {
        "evaluations": 0,
        "radius_only_blocks": 0,
        "centre_and_radius_blocks": 0,
        "accepted_with_evidence": 0,
        "outward_allowed": 0,
        "deeper_blocked": 0,
        "soft_cap_warnings": 0,
        "hard_cap_blocks": 0,
        "zero_radius_skips": 0,
        "no_motion_skips": 0,
        "receipts_emitted": 0,
        "duplicate_suppressed": 0,
        "emission_errors": 0,
        "restore_false_hit_suppressed": 0,
    }


def state_of(world: Any) -> RadiusAwareFaceSweepState | None:
    raw = getattr(world, "radius_aware_face_sweep_state", None)
    return raw if isinstance(raw, RadiusAwareFaceSweepState) else None


def ensure_radius_aware_face_sweep_for_runtime(
    world: Any, config: Any
) -> RadiusAwareFaceSweepState | None:
    if not radius_aware_face_sweep_is_active(config):
        if state_of(world) is not None:
            world.radius_aware_face_sweep_state = None
        return None
    st = state_of(world)
    if st is not None:
        return st
    raw = getattr(config, "radius_aware_face_sweep", None)
    cfg = (
        RadiusAwareFaceSweepConfig.from_dict(
            raw.to_dict() if hasattr(raw, "to_dict") else raw
        )
        if raw is not None
        else RadiusAwareFaceSweepConfig(enabled=True)
    )
    cfg.enabled = True
    validate_config(cfg)
    st = RadiusAwareFaceSweepState(config=cfg)
    world.radius_aware_face_sweep_state = st
    return st


def note_surface_generation(world: Any, generation: int | None = None) -> None:
    """Invalidate derived caches on terrain mutation (non-authoritative)."""
    st = state_of(world)
    if st is None:
        return
    st._query_cache.clear()
    if generation is not None:
        st._cache_generation = int(generation)
    else:
        st._cache_generation = int(st._cache_generation) + 1


# ---------------------------------------------------------------------------
# Pure geometry helpers (no entity mutation)
# ---------------------------------------------------------------------------


def unwrap_delta(dx: float, width: float) -> float:
    w = float(width)
    if w <= 0:
        return float(dx)
    d = float(dx)
    while d > 0.5 * w:
        d -= w
    while d < -0.5 * w:
        d += w
    # Exact half-world: prefer non-positive branch (deterministic, matches SES spirit).
    if abs(abs(d) - 0.5 * w) < 1e-15:
        d = -0.5 * w if d > 0 else d
    return d


def _seg_point_dist2(
    px: float, py: float, ax: float, ay: float, bx: float, by: float
) -> float:
    abx, aby = bx - ax, by - ay
    apx, apy = px - ax, py - ay
    ab2 = abx * abx + aby * aby
    if ab2 <= EPS_PATH:
        return apx * apx + apy * apy
    t = max(0.0, min(1.0, (apx * abx + apy * aby) / ab2))
    qx, qy = ax + t * abx, ay + t * aby
    dx, dy = px - qx, py - qy
    return dx * dx + dy * dy


def _segments_distance(
    a0x: float, a0y: float, a1x: float, a1y: float,
    b0x: float, b0y: float, b1x: float, b1y: float,
) -> float:
    """Minimum distance between two finite segments (2D)."""
    # Sample endpoints + clamp projections (exact enough with EPS for grid faces).
    d2 = min(
        _seg_point_dist2(a0x, a0y, b0x, b0y, b1x, b1y),
        _seg_point_dist2(a1x, a1y, b0x, b0y, b1x, b1y),
        _seg_point_dist2(b0x, b0y, a0x, a0y, a1x, a1y),
        _seg_point_dist2(b1x, b1y, a0x, a0y, a1x, a1y),
    )
    # Also project closest approach of infinite lines clamped — covered by endpoint+clamp.
    return math.sqrt(max(0.0, d2))


def _path_param_nearest_to_point(
    px: float, py: float, x0: float, y0: float, dx: float, dy: float
) -> float:
    L2 = dx * dx + dy * dy
    if L2 <= EPS_PATH:
        return 0.0
    t = ((px - x0) * dx + (py - y0) * dy) / L2
    return max(0.0, min(1.0, float(t)))


def _face_segment(
    axis: str, coord: int, cell_lo: int
) -> tuple[float, float, float, float]:
    """Return endpoints of the unit cell face at axis=coord bordering cell_lo."""
    if axis == "x":
        # Vertical face x=coord, y in [cell_lo, cell_lo+1]
        return float(coord), float(cell_lo), float(coord), float(cell_lo + 1)
    # Horizontal face y=coord, x in [cell_lo, cell_lo+1]
    return float(cell_lo), float(coord), float(cell_lo + 1), float(coord)


def enumerate_candidate_faces(
    x0: float, y0: float, dx: float, dy: float, radius: float, *, width: int, height: int
) -> list[dict[str, Any]]:
    """Broad phase: conservative faces the swept disk of radius R may touch.

    Returns deterministic list sorted by (axis, coord, cell_lo).
    Cells are in unwrapped integer space; wrap applied only at height query time.
    """
    R = float(radius)
    if R <= EPS_RADIUS:
        return []
    # AABB of capsule in unwrapped coords.
    xs = [x0, x0 + dx]
    ys = [y0, y0 + dy]
    xmin, xmax = min(xs) - R, max(xs) + R
    ymin, ymax = min(ys) - R, max(ys) + R
    ix0 = int(math.floor(xmin)) - 1
    ix1 = int(math.floor(xmax)) + 1
    iy0 = int(math.floor(ymin)) - 1
    iy1 = int(math.floor(ymax)) + 1

    faces: list[dict[str, Any]] = []
    # Vertical faces between columns ix and ix-1 for ix in range
    for ix in range(ix0 + 1, ix1 + 1):
        for iy in range(iy0, iy1 + 1):
            faces.append({
                "axis": "x",
                "coord": int(ix),
                "cell_lo": int(iy),  # along-face secondary index
                "cell_a": (int(ix - 1), int(iy)),
                "cell_b": (int(ix), int(iy)),
            })
    for iy in range(iy0 + 1, iy1 + 1):
        for ix in range(ix0, ix1 + 1):
            faces.append({
                "axis": "y",
                "coord": int(iy),
                "cell_lo": int(ix),
                "cell_a": (int(ix), int(iy - 1)),
                "cell_b": (int(ix), int(iy)),
            })
    faces.sort(key=lambda f: (0 if f["axis"] == "x" else 1, f["coord"], f["cell_lo"]))
    return faces


def _wrap_cell(cx: int, cy: int, width: int, height: int) -> tuple[int, int]:
    w, h = int(width), int(height)
    return int(wrap_coord(int(cx), w)), int(wrap_coord(int(cy), h))


def evaluate_face_sweep_geometry(
    *,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    radius: float,
    width: int,
    height: int,
    height_at_cell: Callable[[int, int], float],
    microrelief_threshold: float = MICRORELIEF_THRESHOLD,
    soft_cap: int = SOFT_CANDIDATE_CELL_CAP,
    hard_cap: int = HARD_CANDIDATE_CELL_CAP,
    centre_path_blocked: bool = False,
) -> dict[str, Any]:
    """Pure geometry kernel. Returns evidence only — no mutation, no PE."""
    w, h = int(width), int(height)
    R = float(radius)
    thr = float(microrelief_threshold)
    dx = unwrap_delta(float(x1) - float(x0), w)
    dy = unwrap_delta(float(y1) - float(y0), h)
    path_len = math.hypot(dx, dy)

    base = {
        "geometry_profile": GEOMETRY_PROFILE,
        "radius": R,
        "origin_unwrapped": [float(x0), float(y0)],
        "disp_unwrapped": [float(dx), float(dy)],
        "path_length": float(path_len),
        "microrelief_threshold": thr,
        "candidate_count": 0,
        "evaluation_status": EVAL_EXACT,
        "earliest_hit": None,
        "blocking_proposal": False,
        "barrier_magnitude": 0.0,
        "evidence_source": SOURCE_NONE,
        "starting_penetration": {
            "origin_pen": 0.0,
            "proposal_pen": 0.0,
            "disposition": PEN_NONE,
        },
        "face_sweep_work_delta": 0.0,
        "face_sweep_pe_delta": 0.0,
        "pe_authority": PE_AUTHORITY_SES_DDA,
        "centre_path_blocked": bool(centre_path_blocked),
    }

    if R <= EPS_RADIUS:
        base["evaluation_status"] = EVAL_SKIPPED_ZERO_RADIUS
        return base
    if path_len <= EPS_PATH:
        base["evaluation_status"] = EVAL_SKIPPED_NO_MOTION
        return base

    faces = enumerate_candidate_faces(x0, y0, dx, dy, R, width=w, height=h)
    # Unique cells touched by face list (for caps).
    cells: set[tuple[int, int]] = set()
    for f in faces:
        cells.add(f["cell_a"])
        cells.add(f["cell_b"])
    n_cells = len(cells)
    base["candidate_count"] = int(n_cells)

    if n_cells > int(hard_cap):
        base["evaluation_status"] = EVAL_HARD_CAP
        base["blocking_proposal"] = True
        base["evidence_source"] = SOURCE_RADIUS
        return base
    if n_cells > int(soft_cap):
        base["evaluation_status"] = EVAL_SOFT_CAP

    hits: list[dict[str, Any]] = []
    # Penetration: max overlap into the high side of a qualifying barrier face.
    pen_origin = 0.0
    pen_proposal = 0.0

    for f in faces:
        axis = f["axis"]
        coord = int(f["coord"])
        cell_lo = int(f["cell_lo"])
        ca = f["cell_a"]
        cb = f["cell_b"]
        wa = _wrap_cell(ca[0], ca[1], w, h)
        wb = _wrap_cell(cb[0], cb[1], w, h)
        ha = float(height_at_cell(wa[0], wa[1]))
        hb = float(height_at_cell(wb[0], wb[1]))
        dh = hb - ha
        if abs(dh) <= thr + 1e-15:
            continue  # not a LARGE discontinuity
        # High / low sides
        if dh > 0:
            high_cell, low_cell, h_high, h_low = cb, ca, hb, ha
            uphill_sign = +1  # entering b from a is uphill
        else:
            high_cell, low_cell, h_high, h_low = ca, cb, ha, hb
            uphill_sign = -1
        barrier = float(h_high - h_low)
        if barrier <= thr + 1e-15:
            continue

        fx0, fy0, fx1, fy1 = _face_segment(axis, coord, cell_lo)
        dist = _segments_distance(x0, y0, x0 + dx, y0 + dy, fx0, fy0, fx1, fy1)
        if dist > R + EPS_DIST:
            continue  # swept disk misses face

        # Hit parameter along path: nearest point on path to face midpoint.
        midx, midy = 0.5 * (fx0 + fx1), 0.5 * (fy0 + fy1)
        t_hit = _path_param_nearest_to_point(midx, midy, x0, y0, dx, dy)
        # Refine: if face is crossed by expanded path, use geometric t of closest approach.
        # For vertical face: solve for t where path is within R of x=coord.
        if axis == "x" and abs(dx) > EPS_PATH:
            # times when |x0+t*dx - coord| is minimized within segment
            t_line = (coord - x0) / dx
            t_hit = max(0.0, min(1.0, float(t_line)))
        elif axis == "y" and abs(dy) > EPS_PATH:
            t_line = (coord - y0) / dy
            t_hit = max(0.0, min(1.0, float(t_line)))

        # Penetration at a point: how deep the disk overlaps past the face into high cell.
        def _pen_at(px: float, py: float) -> float:
            if axis == "x":
                # signed: positive toward cell_b (increasing x)
                signed = float(px) - float(coord)
                # depth into high side
                if high_cell == cb:  # high is +x
                    # overlap if centre is within R of face from either side toward high
                    return max(0.0, R - abs(signed)) if signed <= R else 0.0
                else:
                    return max(0.0, R - abs(signed)) if signed >= -R else 0.0
            signed = float(py) - float(coord)
            if high_cell == cb:
                return max(0.0, R - abs(signed)) if signed <= R else 0.0
            return max(0.0, R - abs(signed)) if signed >= -R else 0.0

        # More precise penetration: R - distance_to_face if disk intersects high cell AABB.
        def _pen_precise(px: float, py: float) -> float:
            if axis == "x":
                d_face = abs(float(px) - float(coord))
            else:
                d_face = abs(float(py) - float(coord))
            if d_face >= R - EPS_DIST:
                return 0.0
            # Centre on low side overlapping into high, or centre already in high.
            if axis == "x":
                toward_high = (float(px) - float(coord)) * (1 if high_cell == cb else -1)
            else:
                toward_high = (float(py) - float(coord)) * (1 if high_cell == cb else -1)
            # Overlap depth into high half-plane of the disk.
            return float(R - d_face) if toward_high >= -R else 0.0

        po = _pen_precise(x0, y0)
        pp = _pen_precise(x0 + dx, y0 + dy)
        pen_origin = max(pen_origin, po)
        pen_proposal = max(pen_proposal, pp)

        # Blocking relevance: forward motion that approaches/crosses into high cell
        # while disk hits the face. Skip if this is only starting overlap being reduced.
        hits.append({
            "t": float(t_hit),
            "axis": axis,
            "coord": int(coord),
            "cell_lo": int(cell_lo),
            "cell_a_wrapped": [int(wa[0]), int(wa[1])],
            "cell_b_wrapped": [int(wb[0]), int(wb[1])],
            "h_a": float(ha),
            "h_b": float(hb),
            "h_low": float(h_low),
            "h_high": float(h_high),
            "barrier_magnitude": float(barrier),
            "dist_path_to_face": float(dist),
            "uphill_sign": int(uphill_sign),
            "pen_origin": float(po),
            "pen_proposal": float(pp),
        })

    # Deterministic earliest hit: t asc, axis x before y, cell_lo, coord
    hits.sort(
        key=lambda hh: (
            round(float(hh["t"]), 12),
            0 if hh["axis"] == "x" else 1,
            int(hh["coord"]),
            int(hh["cell_lo"]),
        )
    )

    disposition = PEN_NONE
    if pen_origin > EPS_PEN or pen_proposal > EPS_PEN:
        if pen_proposal > pen_origin + EPS_PEN:
            disposition = PEN_DEEPER
        elif pen_proposal < pen_origin - EPS_PEN:
            disposition = PEN_OUTWARD
        else:
            disposition = PEN_TANGENTIAL

    base["starting_penetration"] = {
        "origin_pen": float(pen_origin),
        "proposal_pen": float(pen_proposal),
        "disposition": disposition,
        "metric": "MAX_DISK_OVERLAP_DEPTH_PAST_BARRIER_FACE_V1",
    }

    blocking = False
    earliest = None
    if hits:
        earliest = hits[0]
        # Propose block if there is a qualifying radius hit AND motion is not
        # an allowed outward escape from starting penetration.
        if disposition == PEN_OUTWARD:
            blocking = False
        elif disposition == PEN_DEEPER:
            blocking = True
        else:
            # No starting penetration (or tangential): block if radius hits barrier
            # that centre path would not necessarily see — always propose when hit
            # and barrier > thr (topology).
            blocking = True
            # If centre already blocked, still record but SES owns centre reason.
            if centre_path_blocked:
                blocking = True  # evidence both; SES may prefer centre reason

    base["earliest_hit"] = earliest
    base["blocking_proposal"] = bool(blocking)
    base["barrier_magnitude"] = float(earliest["barrier_magnitude"]) if earliest else 0.0
    if centre_path_blocked and blocking:
        base["evidence_source"] = SOURCE_BOTH
    elif blocking or earliest is not None:
        base["evidence_source"] = SOURCE_RADIUS if not centre_path_blocked else SOURCE_BOTH
    else:
        base["evidence_source"] = SOURCE_NONE
    return base


# ---------------------------------------------------------------------------
# SES plan integration helper
# ---------------------------------------------------------------------------


def apply_face_sweep_to_plan(
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
    tick: int,
) -> dict[str, Any]:
    """Attach face-sweep evidence to an SES plan; may convert accept→radius block.

    Never mutates entities. Never adds work/PE. Called only from evaluate_path_transitions
    (or tests) while plan is still immutable relative to commit.
    """
    if not radius_aware_face_sweep_active_on_world(world, config):
        plan["face_sweep"] = {"evaluation_status": EVAL_INACTIVE, "blocking_proposal": False}
        return plan

    st = state_of(world)
    if st is not None and st.restore_suppress_until_tick is not None:
        if int(tick) <= int(st.restore_suppress_until_tick):
            st.counters["restore_false_hit_suppressed"] = (
                int(st.counters.get("restore_false_hit_suppressed", 0)) + 1
            )
            plan["face_sweep"] = {
                "evaluation_status": "RESTORE_SUPPRESSED",
                "blocking_proposal": False,
                "face_sweep_work_delta": 0.0,
                "face_sweep_pe_delta": 0.0,
            }
            return plan
        st.restore_suppress_until_tick = None

    from mechanistic_mind.physical_system.surface_elevation_support import (
        support_height_at_cell,
        _dims,
    )

    ww, hh = _dims(world)
    cfg = st.config if st is not None else RadiusAwareFaceSweepConfig(enabled=True)
    centre_blocked = not bool(plan.get("accepted", True))

    def _h(cx: int, cy: int) -> float:
        return float(support_height_at_cell(world, int(cx), int(cy), config=config))

    evidence = evaluate_face_sweep_geometry(
        x0=float(x0),
        y0=float(y0),
        x1=float(x1),
        y1=float(y1),
        radius=float(radius),
        width=ww,
        height=hh,
        height_at_cell=_h,
        microrelief_threshold=float(cfg.microrelief_threshold),
        soft_cap=int(cfg.soft_candidate_cell_cap),
        hard_cap=int(cfg.hard_candidate_cell_cap),
        centre_path_blocked=centre_blocked,
    )
    evidence["entity_kind"] = str(entity_kind)
    evidence["entity_id"] = str(entity_id)
    evidence["tick"] = int(tick)

    if st is not None:
        st.counters["evaluations"] = int(st.counters.get("evaluations", 0)) + 1
        if evidence["evaluation_status"] == EVAL_SKIPPED_ZERO_RADIUS:
            st.counters["zero_radius_skips"] = int(st.counters.get("zero_radius_skips", 0)) + 1
        if evidence["evaluation_status"] == EVAL_SKIPPED_NO_MOTION:
            st.counters["no_motion_skips"] = int(st.counters.get("no_motion_skips", 0)) + 1
        if evidence["evaluation_status"] == EVAL_SOFT_CAP:
            st.counters["soft_cap_warnings"] = int(st.counters.get("soft_cap_warnings", 0)) + 1
        if evidence["evaluation_status"] == EVAL_HARD_CAP:
            st.counters["hard_cap_blocks"] = int(st.counters.get("hard_cap_blocks", 0)) + 1
        disp = (evidence.get("starting_penetration") or {}).get("disposition")
        if disp == PEN_OUTWARD:
            st.counters["outward_allowed"] = int(st.counters.get("outward_allowed", 0)) + 1
        if disp == PEN_DEEPER:
            st.counters["deeper_blocked"] = int(st.counters.get("deeper_blocked", 0)) + 1

    # Policy: radius may block only if centre path would have accepted.
    radius_block = bool(evidence.get("blocking_proposal")) and not centre_blocked
    # Outward escape: do not block even if hit list non-empty.
    if (evidence.get("starting_penetration") or {}).get("disposition") == PEN_OUTWARD:
        radius_block = False
        evidence["blocking_proposal"] = False

    if radius_block:
        evidence["evidence_source"] = SOURCE_RADIUS
        # Convert plan to rejected topology block — no work/PE.
        plan["accepted"] = False
        # Hard-cap unresolved → distinct reason so G2C2 maps to GEOMETRY_AMBIGUOUS.
        if evidence.get("evaluation_status") == EVAL_HARD_CAP:
            reason = "RADIUS_FACE_BARRIER_HARD_CAP"
        else:
            reason = EVENT_RADIUS_FACE_BARRIER
        plan["block_reason"] = reason
        plan["x"] = float(x0)
        plan["y"] = float(y0)
        # Velocity: match existing body/object block policy (body keeps vx; object stops).
        if str(entity_kind) == "object":
            plan["vx"] = 0.0
            plan["vy"] = 0.0
        plan["work_debit"] = 0.0
        plan["kinetic_paid"] = 0.0
        plan["support_lost"] = False
        kinds = list(plan.get("event_kinds") or [])
        kinds.append(reason)
        plan["event_kinds"] = kinds
        if st is not None:
            st.counters["radius_only_blocks"] = int(st.counters.get("radius_only_blocks", 0)) + 1
    elif centre_blocked and evidence.get("earliest_hit") is not None:
        evidence["evidence_source"] = SOURCE_BOTH
        if st is not None:
            st.counters["centre_and_radius_blocks"] = (
                int(st.counters.get("centre_and_radius_blocks", 0)) + 1
            )
    elif plan.get("accepted") and evidence.get("earliest_hit") is None:
        if st is not None:
            st.counters["accepted_with_evidence"] = (
                int(st.counters.get("accepted_with_evidence", 0)) + 1
            )

    plan["face_sweep"] = evidence
    plan["face_sweep_work_delta"] = 0.0
    plan["face_sweep_pe_delta"] = 0.0
    return plan


def record_face_sweep_receipt(
    world: Any,
    *,
    plan: dict[str, Any],
    tick: int,
    entity_kind: str,
    entity_id: str,
    x0: float,
    y0: float,
    x_proposed: float,
    y_proposed: float,
    x_realized: float,
    y_realized: float,
    radius: float,
) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    ev = plan.get("face_sweep") if isinstance(plan.get("face_sweep"), dict) else {}
    if not ev or ev.get("evaluation_status") in (EVAL_INACTIVE, "RESTORE_SUPPRESSED"):
        return None
    key = f"{int(tick)}:{entity_kind}:{entity_id}:FACE_SWEEP"
    if st.applied_keys_tick != int(tick):
        st.applied_keys_tick = int(tick)
        st.applied_keys = set()
    if key in st.applied_keys:
        st.counters["duplicate_suppressed"] = int(st.counters.get("duplicate_suppressed", 0)) + 1
        return None
    st.applied_keys.add(key)
    hit = ev.get("earliest_hit") or {}
    receipt = {
        "receipt_kind": RECEIPT_KIND,
        "tick": int(tick),
        "entity_kind": str(entity_kind),
        "entity_id": str(entity_id),
        "profile_version": PROFILE_VERSION,
        "geometry_profile": GEOMETRY_PROFILE,
        "physical_radius": float(radius),
        "origin": [float(x0), float(y0)],
        "proposed_destination": [float(x_proposed), float(y_proposed)],
        "realized_destination": [float(x_realized), float(y_realized)],
        "candidate_count": int(ev.get("candidate_count") or 0),
        "evaluation_status": ev.get("evaluation_status"),
        "earliest_hit_t": hit.get("t"),
        "axis": hit.get("axis"),
        "cell_a": hit.get("cell_a_wrapped"),
        "cell_b": hit.get("cell_b_wrapped"),
        "h_low": hit.get("h_low"),
        "h_high": hit.get("h_high"),
        "barrier_magnitude": float(ev.get("barrier_magnitude") or 0.0),
        "evidence_source": ev.get("evidence_source"),
        "blocking_proposal": bool(ev.get("blocking_proposal")),
        "ses_accepted": bool(plan.get("accepted", True)),
        "ses_block_reason": plan.get("block_reason"),
        "starting_penetration": ev.get("starting_penetration"),
        "pe_authority": PE_AUTHORITY_SES_DDA,
        "face_sweep_work_delta": 0.0,
        "face_sweep_pe_delta": 0.0,
        "application_key": key,
        "dedup_key": key,
        **RESEARCHER_FLAGS,
    }
    st.last_receipt = receipt
    st.history.append(receipt)
    lim = int(st.config.history_limit)
    if len(st.history) > lim:
        st.history = st.history[-lim:]
    st.counters["receipts_emitted"] = int(st.counters.get("receipts_emitted", 0)) + 1
    return receipt


# ---------------------------------------------------------------------------
# Serialization / catalog / overlay
# ---------------------------------------------------------------------------


def serialize_state(st: RadiusAwareFaceSweepState | None) -> dict[str, Any] | None:
    if st is None:
        return None
    return {
        "schema": STATE_SCHEMA,
        "config": st.config.to_dict(),
        "counters": dict(st.counters),
        "researcher_only": True,
    }


def restore_state(
    world: Any, data: dict[str, Any] | None, config: Any,
) -> RadiusAwareFaceSweepState | None:
    if not radius_aware_face_sweep_is_active(config):
        world.radius_aware_face_sweep_state = None
        return None
    if not isinstance(data, dict) or not data:
        st = ensure_radius_aware_face_sweep_for_runtime(world, config)
        if st is not None:
            st.restore_suppress_until_tick = int(getattr(world, "tick", 0) or 0)
        return st
    if str(data.get("schema")) != STATE_SCHEMA:
        raise ValueError(f"unknown radius_aware_face_sweep schema: {data.get('schema')}")
    raw_cfg = data.get("config")
    if raw_cfg is None:
        cur = getattr(config, "radius_aware_face_sweep", None)
        raw_cfg = cur.to_dict() if cur is not None and hasattr(cur, "to_dict") else None
    cfg = RadiusAwareFaceSweepConfig.from_dict(raw_cfg)
    validate_config(cfg)
    st = RadiusAwareFaceSweepState(
        config=cfg,
        counters={**_default_counters(), **{k: int(v) for k, v in dict(data.get("counters") or {}).items()}},
    )
    st.restore_suppress_until_tick = int(getattr(world, "tick", 0) or 0)
    world.radius_aware_face_sweep_state = st
    return st


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "label": "Radius-Aware Face Sweep SES Plan Evidence V1",
        "config_path": "radius_aware_face_sweep.enabled",
        "enabled": bool(enabled),
        "promotion_class": "EXPERIMENTAL",
        "provenance": "acanthostega_radius_aware_face_sweep_ses_plan_evidence_v1",
        "default_integrated": True,
        "banner": BANNER,
        "analyzer_section": ANALYZER_SECTION,
        "profile_version": PROFILE_VERSION,
        "geometry_profile": GEOMETRY_PROFILE,
        "pe_authority": PE_AUTHORITY_SES_DDA,
        "face_sweep_may_block": True,
        "face_sweep_may_charge_pe": False,
        "scope": {
            "bodies": True,
            "free_objects": True,
            "held_objects": False,
            "ses_plan_evidence": True,
            "physics_pe_unchanged": True,
        },
        "historical_compatibility": "missing key means face sweep OFF",
    }


def researcher_summary(world: Any) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    last = st.last_receipt or {}
    return {
        "mechanism": MECHANISM_ID,
        "profile_version": PROFILE_VERSION,
        "banner": BANNER,
        "analyzer_section": ANALYZER_SECTION,
        "counters": dict(st.counters),
        "last_receipt": last or None,
        "pe_authority": PE_AUTHORITY_SES_DDA,
        "face_sweep_work_delta": 0.0,
        "face_sweep_pe_delta": 0.0,
        "geometry_profile": GEOMETRY_PROFILE,
        "agent_accessible": False,
        "researcher_only": True,
    }


def overlay_payload(world: Any) -> dict[str, Any] | None:
    s = researcher_summary(world)
    if s is None:
        return None
    last = s.get("last_receipt") or {}
    return {
        "caption": BANNER,
        "active": s,
        "physical_radius": last.get("physical_radius"),
        "ses_block_reason": last.get("ses_block_reason"),
        "blocking_proposal": last.get("blocking_proposal"),
        "evaluation_status": last.get("evaluation_status"),
        "candidate_count": last.get("candidate_count"),
        "earliest_hit_t": last.get("earliest_hit_t"),
        "starting_penetration": last.get("starting_penetration"),
        "face_sweep_work_delta": 0.0,
        "read_only": True,
    }


def status_text() -> str:
    return BANNER
