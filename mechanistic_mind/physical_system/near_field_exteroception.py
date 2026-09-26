"""PHYSICAL_PERCEPTION_01 — directional near-field exteroception.

Bounded Moore-radius-1 source domain × body-oriented FOV × illumination ×
surface_response. Cognition receives only anonymous exo_* fragments.

Default OFF. Observational only — does not alter body/terrain/ambient/thermal
forces, work, or resources. No TURN/LOOK actions. No sensor memory.
No semantic vision labels.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

import numpy as np

from mechanistic_mind.physical_body.state import PhysicalBodyState
from mechanistic_mind.planet.state import PlanetState
from mechanistic_mind.planet.terrain import deterministic_namespace_seed
from mechanistic_mind.planet.topology import toroidal_delta, wrap_coord
from mechanistic_mind.research.tick_profiler import count as _prof_count
from mechanistic_mind.research.tick_profiler import span as _prof_span

SURFACE_GENERATOR_VERSION = "surface_observable_v1"
SURFACE_OPTICAL_GENERATOR_VERSION = "surface_optical_v1"
ILLUMINATION_GENERATOR_VERSION = "illumination_cycle_v1"

# Predeclared FOV candidates (degrees, full width). Selected default: 120.
FOV_CANDIDATES_DEG = (60.0, 90.0, 120.0)
DEFAULT_FOV_DEG = 120.0

# Illumination period candidates (ticks). Selected: 240.
ILLUMINATION_PERIOD_CANDIDATES = (160, 240, 320, 400)
DEFAULT_ILLUMINATION_PERIOD = 240

# Angular channel bins inside FOV → cognition keys exo_0..exo_2 (L / F / R).
N_EXO_CHANNELS = 3

# Phase 4 spatial vision (2D angular/occlusion). Not depth, not 3D.
SPATIAL_VISION_MODES = ("LEGACY", "ANGULAR", "OCCLUSION", "TEMPORAL_SPATIAL")
DEFAULT_SPATIAL_VISION = "LEGACY"
SPATIAL_SECTOR_CANDIDATES = (3, 5, 7)
DEFAULT_SPATIAL_SECTORS = 5  # occupancy/cost: see Phase 4 design + experiment
SpatialVisionMode = Literal["LEGACY", "ANGULAR", "OCCLUSION", "TEMPORAL_SPATIAL"]

# LIVE Observer control: Moore candidate radius (default R=1 = legacy).
VISION_RADIUS_MIN = 1
VISION_RADIUS_MAX = 3
DEFAULT_VISION_RADIUS = 1

SurfaceMode = Literal["INDEPENDENT", "CORRELATED", "SHUFFLED"]
OpticalMapping = Literal["INDEPENDENT", "CORRELATED", "SHUFFLED", "UNIFORM"]
SurfaceDiscriminationMode = Literal["OFF", "LOW", "RICH"]

N_SURFACE_OPTICAL_CHANNELS = 3
SURFACE_DISCRIMINATION_MODES = ("OFF", "LOW", "RICH")
OPTICAL_MAPPING_MODES = ("INDEPENDENT", "CORRELATED", "SHUFFLED", "UNIFORM")


def clamp_vision_radius(radius: Any) -> int:
    """Clamp to {1,2,3}. Missing/invalid → default R=1 (legacy)."""
    try:
        r = int(radius)
    except (TypeError, ValueError):
        return DEFAULT_VISION_RADIUS
    return max(VISION_RADIUS_MIN, min(VISION_RADIUS_MAX, r))


def clamp_surface_discrimination(mode: Any) -> str:
    """OFF | LOW | RICH. Missing/invalid → OFF (Beta 3 control)."""
    s = str(mode or "OFF").strip().upper()
    if s in SURFACE_DISCRIMINATION_MODES:
        return s
    return "OFF"


def clamp_optical_mapping(mode: Any) -> str:
    s = str(mode or "INDEPENDENT").strip().upper()
    if s in OPTICAL_MAPPING_MODES:
        return s
    return "INDEPENDENT"


def clamp_spatial_vision(mode: Any) -> str:
    s = str(mode or DEFAULT_SPATIAL_VISION).strip().upper().replace("-", "_").replace(" ", "_")
    aliases = {
        "OFF": "LEGACY",
        "NONE": "LEGACY",
        "CURRENT": "LEGACY",
        "ANGULAR_ONLY": "ANGULAR",
        "OCCLUDE": "OCCLUSION",
        "TEMPORAL": "TEMPORAL_SPATIAL",
        "SPATIAL": "TEMPORAL_SPATIAL",
    }
    s = aliases.get(s, s)
    if s in SPATIAL_VISION_MODES:
        return s
    return DEFAULT_SPATIAL_VISION


def clamp_spatial_sectors(n: Any) -> int:
    try:
        k = int(n)
    except (TypeError, ValueError):
        return DEFAULT_SPATIAL_SECTORS
    if k in SPATIAL_SECTOR_CANDIDATES:
        return k
    return DEFAULT_SPATIAL_SECTORS


def spatial_vision_uses_extra_bins(mode: Any) -> bool:
    return clamp_spatial_vision(mode) != "LEGACY"


def spatial_vision_uses_occlusion(mode: Any) -> bool:
    return clamp_spatial_vision(mode) in {"OCCLUSION", "TEMPORAL_SPATIAL"}


def spatial_observation_keys(
    *,
    spatial_mode: Any,
    discrimination: Any,
    n_sectors: Any = DEFAULT_SPATIAL_SECTORS,
) -> tuple[str, ...]:
    if not spatial_vision_uses_extra_bins(spatial_mode):
        return ()
    n = clamp_spatial_sectors(n_sectors)
    keys: list[str] = [f"spatial_exo_a{k}" for k in range(n)]
    n_surf = surface_channel_count(discrimination)
    for c in range(n_surf):
        for k in range(n):
            keys.append(f"spatial_surface_c{c}_a{k}")
    return tuple(keys)


def surface_channel_count(mode: Any) -> int:
    m = clamp_surface_discrimination(mode)
    if m == "LOW":
        return 1
    if m == "RICH":
        return N_SURFACE_OPTICAL_CHANNELS
    return 0


def surface_observation_keys(mode: Any) -> tuple[str, ...]:
    n = surface_channel_count(mode)
    return tuple(
        f"surface_c{c}_{b}"
        for c in range(n)
        for b in range(N_EXO_CHANNELS)
    )


def moore_max_candidates(radius: int) -> int:
    """Theoretical unique Moore cells excluding own: (2R+1)^2 - 1."""
    r = clamp_vision_radius(radius)
    return int((2 * r + 1) ** 2 - 1)


@dataclass
class NearFieldExteroceptionConfig:
    """Directional near-field sensor. Factory default OFF (legacy-safe).

    Beta 2 authority:
      - ``perception_enabled`` — physical_near_field_vision (exo_* contribution)
      - ``illumination_enabled`` — illumination_cycle dynamics
      - ``radius`` — Moore candidate neighborhood (R=1 default; LIVE R=1/2/3)
    Surface structure is independent of the vision toggle once installed.
    """

    mode: str = "OFF"  # OFF | EXPERIMENTAL
    # When True and mode EXPERIMENTAL, exo_* fragments enter cognition.
    perception_enabled: bool = True
    fov_deg: float = DEFAULT_FOV_DEG
    # Angular response: raised-cosine within FOV half-width.
    angular_power: float = 2.0
    # Distance attenuation: strength *= 1 / (1 + k*(d - 1)); d in cells.
    distance_k: float = 0.85
    gain: float = 1.0
    threshold: float = 0.04
    saturation: float = 1.0
    # Illumination (global scalar; architecture allows spatial later).
    illumination_enabled: bool = True
    illumination_period: int = DEFAULT_ILLUMINATION_PERIOD
    illumination_min: float = 0.15
    illumination_max: float = 1.0
    # Frozen intensity when illumination_cycle is LIVE-OFF (no comfort substitution).
    illumination_frozen: float | None = None
    # Surface field.
    surface_enabled: bool = True
    surface_mode: str = "INDEPENDENT"  # INDEPENDENT | CORRELATED | SHUFFLED
    surface_correlation: float = 0.35  # used when CORRELATED
    surface_seed: int | None = None
    # Optional tiny deterministic hash noise on raw signal (not biological garnish).
    signal_hash_noise: float = 0.0
    # Physical body optical contribution into local composed response (Beta 2).
    # Does not mutate planet surface_response. Irrelevant when vision package OFF.
    body_optical_enabled: bool = True
    # Moore candidate radius. R=1 preserves legacy 8-neighbor domain.
    # R only expands candidates; FOV/distance/illumination filters unchanged.
    radius: int = DEFAULT_VISION_RADIUS
    # Beta 3.1: additional FOV-gated optical appearance channels (not RGB labels).
    # OFF = Beta 3 exo_* only. LOW = surface_c0_* bins. RICH = surface_c0..c2 bins.
    visual_surface_discrimination: str = "OFF"
    # Ablation mapping for surface_optical WORLD GT (independent of exo intensity field).
    optical_mapping: str = "INDEPENDENT"
    optical_correlation: float = 0.35
    # Phase 4: 2D spatial vision control. LEGACY = exact Beta 3.1 contract.
    spatial_vision: str = DEFAULT_SPATIAL_VISION
    spatial_sectors: int = DEFAULT_SPATIAL_SECTORS

    @property
    def enabled(self) -> bool:
        return str(self.mode).upper() == "EXPERIMENTAL"

    @property
    def vision_contributes(self) -> bool:
        """True when exo_* may enter cognition."""
        return self.enabled and bool(self.perception_enabled)

    @property
    def body_optics_active(self) -> bool:
        return self.enabled and bool(getattr(self, "body_optical_enabled", True))

    @property
    def vision_radius(self) -> int:
        return clamp_vision_radius(getattr(self, "radius", DEFAULT_VISION_RADIUS))

    @property
    def surface_discrimination(self) -> str:
        return clamp_surface_discrimination(
            getattr(self, "visual_surface_discrimination", "OFF")
        )

    @property
    def spatial_vision_mode(self) -> str:
        return clamp_spatial_vision(getattr(self, "spatial_vision", DEFAULT_SPATIAL_VISION))

    @property
    def n_spatial_sectors(self) -> int:
        return clamp_spatial_sectors(getattr(self, "spatial_sectors", DEFAULT_SPATIAL_SECTORS))

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["radius"] = clamp_vision_radius(d.get("radius", DEFAULT_VISION_RADIUS))
        d["visual_surface_discrimination"] = clamp_surface_discrimination(
            d.get("visual_surface_discrimination", "OFF")
        )
        d["optical_mapping"] = clamp_optical_mapping(d.get("optical_mapping", "INDEPENDENT"))
        d["spatial_vision"] = clamp_spatial_vision(d.get("spatial_vision", DEFAULT_SPATIAL_VISION))
        d["spatial_sectors"] = clamp_spatial_sectors(d.get("spatial_sectors", DEFAULT_SPATIAL_SECTORS))
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "NearFieldExteroceptionConfig":
        if not data:
            return cls(mode="OFF")
        kwargs = {k: data[k] for k in cls.__dataclass_fields__ if k in data}
        if "radius" in kwargs:
            kwargs["radius"] = clamp_vision_radius(kwargs["radius"])
        elif "radius" not in data:
            kwargs.setdefault("radius", DEFAULT_VISION_RADIUS)
        if "visual_surface_discrimination" in kwargs:
            kwargs["visual_surface_discrimination"] = clamp_surface_discrimination(
                kwargs["visual_surface_discrimination"]
            )
        if "optical_mapping" in kwargs:
            kwargs["optical_mapping"] = clamp_optical_mapping(kwargs["optical_mapping"])
        if "spatial_vision" in kwargs:
            kwargs["spatial_vision"] = clamp_spatial_vision(kwargs["spatial_vision"])
        if "spatial_sectors" in kwargs:
            kwargs["spatial_sectors"] = clamp_spatial_sectors(kwargs["spatial_sectors"])
        return cls(**kwargs)


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------

# Legacy R=1 offsets (dy, dx). Enumeration order preserved for EXACT_MATCH.
MOORE_OFFSETS: tuple[tuple[int, int], ...] = (
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1),           (0, 1),
    (1, -1),  (1, 0),  (1, 1),
)


def moore_neighbor_cells(
    cx: int,
    cy: int,
    width: int,
    height: int,
    radius: int = DEFAULT_VISION_RADIUS,
) -> list[tuple[int, int]]:
    """WRAP_PERIODIC Moore candidates within radius R; own cell excluded.

    R=1 yields the legacy 8-cell set in the same enumeration order as
    ``MOORE_OFFSETS`` (required for scientific EXACT_MATCH).
    Duplicate wrapped cells (tiny maps) are deduplicated, first-seen wins.
    """
    r = clamp_vision_radius(radius)
    out: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx == 0 and dy == 0:
                continue
            nx = int(wrap_coord(cx + dx, width))
            ny = int(wrap_coord(cy + dy, height))
            key = (nx, ny)
            if key in seen:
                continue
            seen.add(key)
            out.append(key)
    return out


def wrap_angle(a: float) -> float:
    """Wrap radians into (-π, π]."""
    x = float(a)
    while x <= -math.pi:
        x += 2.0 * math.pi
    while x > math.pi:
        x -= 2.0 * math.pi
    return x


def angular_sensitivity(rel_angle: float, fov_deg: float, power: float = 2.0) -> float:
    """Continuous FOV response. Exactly 0 outside half-FOV; 1 at forward axis."""
    half = math.radians(0.5 * float(fov_deg))
    if half <= 1e-12:
        return 0.0
    a = abs(wrap_angle(rel_angle))
    if a > half:
        return 0.0
    # Raised cosine: cos(π/2 * a/half)^power
    return float(math.cos(0.5 * math.pi * (a / half)) ** float(power))


def distance_attenuation(distance: float, k: float = 0.85) -> float:
    d = max(1e-9, float(distance))
    return float(1.0 / (1.0 + float(k) * max(0.0, d - 1.0)))


def fov_sector_index(rel_angle: float, fov_deg: float, n: int = N_EXO_CHANNELS) -> int | None:
    """LEFT/FORWARD/RIGHT bin used by sample_near_field, or None outside FOV.

    Same mapping as the accumulation loop:
    rel ∈ [-half, +half] → u ∈ [0, 1) → floor(u * n) clipped to {0..n-1}.
    """
    if angular_sensitivity(rel_angle, fov_deg) <= 0.0:
        return None
    half = 0.5 * float(fov_deg)
    u = (wrap_angle(rel_angle) + math.radians(half)) / max(1e-9, math.radians(2.0 * half))
    return int(np.clip(math.floor(u * int(n)), 0, int(n) - 1))


def apply_spatial_visibility(
    rows: list[dict[str, Any]],
    *,
    mode: Any,
    fov_deg: float,
    n_sectors: int,
) -> None:
    """In-place 2D nearest-in-sector occlusion. LEGACY/ANGULAR leave finals unchanged.

    Diagnostic fields only: visibility, occluded_by, spatial_sector, visible_contribution.
    """
    n_sec = clamp_spatial_sectors(n_sectors)
    occlude = spatial_vision_uses_occlusion(mode)
    for i, row in enumerate(rows):
        rel = float(row.get("relative_angle_rad") or 0.0)
        spat = fov_sector_index(rel, fov_deg, n_sec) if row.get("inside_fov") else None
        row["spatial_sector"] = spat
        row["spatial_sector_label"] = None if spat is None else f"a{int(spat)}"
        row["occluded_by"] = None
        final = float(row.get("final_contribution") or 0.0)
        if not occlude:
            row["visibility"] = "LEGACY_NO_OCCLUSION" if clamp_spatial_vision(mode) == "LEGACY" else "ANGULAR_NO_OCCLUSION"
            if final <= 0.0:
                row["visibility"] = "NOT_DETECTABLE"
            row["visible_contribution"] = final
            continue
        row["visible_contribution"] = final
        row["visibility"] = "VISIBLE" if final > 0.0 else "NOT_DETECTABLE"

    if not occlude:
        return

    groups: dict[int, list[int]] = {}
    for i, row in enumerate(rows):
        spat = row.get("spatial_sector")
        if spat is None or float(row.get("final_contribution") or 0.0) <= 0.0:
            continue
        groups.setdefault(int(spat), []).append(i)
    for _sector, idxs in groups.items():
        idxs.sort(key=lambda j: (float(rows[j].get("distance") or 0.0), j))
        winner = idxs[0]
        rows[winner]["visibility"] = "VISIBLE"
        rows[winner]["visible_contribution"] = float(rows[winner].get("final_contribution") or 0.0)
        wcell = rows[winner].get("cell")
        for j in idxs[1:]:
            rows[j]["visibility"] = "OCCLUDED"
            rows[j]["occluded_by"] = list(wcell) if isinstance(wcell, (list, tuple)) else wcell
            rows[j]["visible_contribution"] = 0.0


def sensor_frame_xy(dx: float, dy: float, heading: float) -> tuple[float, float]:
    """Rotate world Δ into sensor frame: +fwd along heading, +left to port.

    HUMAN DIAGNOSTIC TRANSFORM — not a cognition coordinate.
    """
    c = math.cos(float(heading))
    s = math.sin(float(heading))
    fwd = float(dx) * c + float(dy) * s
    left = -float(dx) * s + float(dy) * c
    return fwd, left


_FPV_SECTORS = ("LEFT", "FORWARD", "RIGHT")


def compact_fpv_receipts(
    sample: dict[str, Any] | None,
    *,
    prev_finals: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Compact pre-aggregation receipts from a canonical sample_near_field result.

    Does not resample the world. Does not alter fragments.
    """
    sample = sample if isinstance(sample, dict) else {}
    heading = float(sample.get("sensor_forward_axis") or sample.get("head_world_heading") or 0.0)
    fov = float(sample.get("fov_deg") or 120.0)
    radius = clamp_vision_radius(sample.get("vision_radius") or sample.get("radius") or 1)
    disc = clamp_surface_discrimination(sample.get("visual_surface_discrimination") or "OFF")
    n_surf = surface_channel_count(disc)
    rows = sample.get("neighbors") or []
    prev = prev_finals or {}
    out_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        dx = float(row.get("dx") or 0.0)
        dy = float(row.get("dy") or 0.0)
        fwd, left = sensor_frame_xy(dx, dy, heading)
        rel = float(row.get("relative_angle_rad") or 0.0)
        bin_i = fov_sector_index(rel, fov)
        inside = bool(row.get("inside_fov"))
        final = float(row.get("final_contribution") or 0.0)
        vis = str(row.get("visibility") or "")
        vis_c = row.get("visible_contribution")
        contrib = float(vis_c) if vis_c is not None else final
        above = bool(row.get("detectable")) and final > 0.0
        if not inside:
            status = "outside_fov"
        elif vis == "OCCLUDED":
            status = "occluded"
        elif not above:
            status = "below_threshold"
        else:
            status = "accepted"
        cell = row.get("cell")
        key = f"{cell[0]},{cell[1]}" if isinstance(cell, (list, tuple)) and len(cell) >= 2 else ""
        pf = prev.get(key)
        temporal = None
        if pf is None:
            temporal = "new_sample" if final > 0.0 else None
        elif pf <= 0.0 and final > 0.0:
            temporal = "newly_detected"
        elif pf > 0.0 and final <= 0.0:
            temporal = "no_longer_detected"
        elif final > pf + 1e-9:
            temporal = "increased"
        elif final < pf - 1e-9:
            temporal = "decreased"
        opt = row.get("surface_optical") or [0.0, 0.0, 0.0]
        rec: dict[str, Any] = {
            "fwd": round(fwd, 5),
            "left": round(left, 5),
            "status": status,
            "sector": None if bin_i is None else _FPV_SECTORS[int(bin_i)],
            "sector_index": bin_i,
            "spatial_sector_index": row.get("spatial_sector"),
            "spatial_sector_label": row.get("spatial_sector_label"),
            "visibility": vis or None,
            "occluded_by": row.get("occluded_by"),
            "visible_contribution": round(contrib, 6),
            "dist_f": round(float(row.get("distance_factor") or 0.0), 6),
            "illumination": round(float(row.get("illumination") or 0.0), 6),
            "surface_response": round(float(row.get("surface_response") or 0.0), 6),
            "body_optical": round(float(row.get("body_optical") or 0.0), 6),
            "composed": round(float(row.get("composed_optical") or 0.0), 6),
            "final": round(final, 6),
            "world_cell": cell,
            "temporal": temporal,
        }
        if n_surf <= 0:
            rec["surface_channels"] = "ABSENT"
        else:
            rec["c0"] = round(float(opt[0] if len(opt) > 0 else 0.0), 6)
            if n_surf >= 2:
                rec["c1"] = round(float(opt[1] if len(opt) > 1 else 0.0), 6)
            if n_surf >= 3:
                rec["c2"] = round(float(opt[2] if len(opt) > 2 else 0.0), 6)
        out_rows.append(rec)
    out_rows.append({
        "fwd": 0.0,
        "left": 0.0,
        "status": "own_cell_excluded",
        "sector": None,
        "sector_index": None,
        "dist_f": None,
        "illumination": None,
        "final": 0.0,
        "world_cell": sample.get("body_cell"),
        "temporal": None,
        "note": "Own cell is excluded from Moore visual sampling.",
    })
    return {
        "layer": "FPV_SENSOR_FIELD",
        "observer_only": True,
        "not_agent_accessible": True,
        "feeds_cognition": False,
        "heading": heading,
        "heading_source": "HEAD" if sample.get("articulated_head_enabled") else "BODY",
        "fov_deg": fov,
        "radius": int(radius),
        "surface_discrimination": disc,
        "optical_mapping": sample.get("optical_mapping"),
        "spatial_vision": sample.get("spatial_vision") or "LEGACY",
        "spatial_sectors": sample.get("spatial_sectors"),
        "n_occluded": int(sample.get("n_occluded") or sum(1 for r in out_rows if r.get("status") == "occluded")),
        "n_samples": len(out_rows),
        "samples": out_rows,
        "honesty": (
            "Diagnostic spatial reconstruction of canonical sensor samples. "
            "Not a camera, retina, or cognition input. Coordinates are a human transform. "
            "FALSE-COLOR C0/C1/C2→display RGB is researcher-only."
        ),
    }


# ---------------------------------------------------------------------------
# Surface + illumination (WORLD GT)
# ---------------------------------------------------------------------------

def illumination_intensity(tick: int, cfg: NearFieldExteroceptionConfig) -> float:
    """Smooth continuous cycle. No DAY/NIGHT labels.

    When ``illumination_enabled`` is False, return the frozen physical value
    (set at LIVE OFF) — never a substituted comfort constant. If no freeze
    was recorded, hold at the cycle midpoint of [min, max].
    """
    if not bool(getattr(cfg, "illumination_enabled", True)):
        frozen = getattr(cfg, "illumination_frozen", None)
        if frozen is not None:
            return float(frozen)
        lo = float(cfg.illumination_min)
        hi = float(cfg.illumination_max)
        return float(0.5 * (lo + hi))
    p = max(1, int(cfg.illumination_period))
    phase = 2.0 * math.pi * (float(tick) % p) / float(p)
    # Cosine: peak at phase 0, trough at π. Smooth, no discontinuity.
    unit = 0.5 * (1.0 + math.cos(phase))
    lo = float(cfg.illumination_min)
    hi = float(cfg.illumination_max)
    return float(lo + (hi - lo) * unit)


def illumination_phase_gt(tick: int, period: int) -> float:
    """Observer GT only — never cognition."""
    p = max(1, int(period))
    return float((float(tick) % p) / float(p))


def generate_surface_response(
    *,
    height: int,
    width: int,
    experiment_seed: int,
    cfg: NearFieldExteroceptionConfig,
    terrain_potential: np.ndarray | None = None,
    terrain_drag: np.ndarray | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Independent deterministic surface_response field (WORLD GT)."""
    resolved = (
        int(cfg.surface_seed)
        if cfg.surface_seed is not None
        else deterministic_namespace_seed(int(experiment_seed), "surface_observable")
    )
    rng = np.random.default_rng(resolved)
    # Smooth independent field.
    z = rng.standard_normal((height, width))
    z = (
        z
        + np.roll(z, 1, 0) + np.roll(z, -1, 0)
        + np.roll(z, 1, 1) + np.roll(z, -1, 1)
    ) / 5.0
    z = (z - z.mean()) / (z.std() + 1e-8)
    base = 0.5 + 0.35 * np.tanh(z)

    mode = str(cfg.surface_mode).upper()
    if mode == "CORRELATED" and terrain_potential is not None:
        pot = np.asarray(terrain_potential, dtype=np.float64)
        pot_n = (pot - pot.mean()) / (pot.std() + 1e-8)
        mix = float(np.clip(cfg.surface_correlation, 0.0, 1.0))
        # Imperfect correlation: mix independent base with potential-shaped signal.
        shaped = 0.5 + 0.35 * np.tanh(pot_n)
        if terrain_drag is not None:
            drag = np.asarray(terrain_drag, dtype=np.float64)
            drag_n = (drag - drag.mean()) / (drag.std() + 1e-8)
            shaped = 0.7 * shaped + 0.3 * (0.5 + 0.35 * np.tanh(drag_n))
        field = (1.0 - mix) * base + mix * shaped
    elif mode == "SHUFFLED" and terrain_potential is not None:
        # Same histogram as a correlated mix, then spatially shuffle.
        pot = np.asarray(terrain_potential, dtype=np.float64)
        pot_n = (pot - pot.mean()) / (pot.std() + 1e-8)
        mix = float(np.clip(cfg.surface_correlation, 0.0, 1.0))
        shaped = 0.5 + 0.35 * np.tanh(pot_n)
        field = (1.0 - mix) * base + mix * shaped
        flat = field.ravel().copy()
        rng.shuffle(flat)
        field = flat.reshape(field.shape)
    else:
        field = base
        mode = "INDEPENDENT"

    field = np.clip(field, 0.0, 1.0).astype(np.float64)
    checksum = hashlib.sha256(field.tobytes()).hexdigest()[:16]
    meta = {
        "experiment_seed": int(experiment_seed),
        "resolved_surface_seed": int(resolved),
        "source": "surface_seed_override" if cfg.surface_seed is not None else "namespace:surface_observable",
        "generator_version": SURFACE_GENERATOR_VERSION,
        "surface_mode": mode,
        "surface_correlation": float(cfg.surface_correlation) if mode == "CORRELATED" else 0.0,
        "config": {
            "surface_mode": mode,
            "surface_correlation": float(cfg.surface_correlation),
            "surface_seed": cfg.surface_seed,
        },
        "checksum": checksum,
        "min": float(field.min()),
        "max": float(field.max()),
        "mean": float(field.mean()),
        "std": float(field.std()),
    }
    return field, meta


def install_surface_on_planet(
    planet: PlanetState,
    *,
    experiment_seed: int,
    cfg: NearFieldExteroceptionConfig,
) -> None:
    if not cfg.surface_enabled:
        planet.surface_response = None
        planet.surface_meta = None
        return
    h, w = int(planet.T.shape[0]), int(planet.T.shape[1])
    field, meta = generate_surface_response(
        height=h,
        width=w,
        experiment_seed=int(experiment_seed),
        cfg=cfg,
        terrain_potential=getattr(planet, "terrain_potential", None),
        terrain_drag=getattr(planet, "terrain_drag", None),
    )
    planet.surface_response = field
    planet.surface_meta = meta
    install_surface_optical_on_planet(planet, experiment_seed=experiment_seed, cfg=cfg)


def _smooth_unit_field(rng: np.random.Generator, height: int, width: int) -> np.ndarray:
    z = rng.standard_normal((height, width))
    z = (
        z
        + np.roll(z, 1, 0) + np.roll(z, -1, 0)
        + np.roll(z, 1, 1) + np.roll(z, -1, 1)
    ) / 5.0
    z = (z - z.mean()) / (z.std() + 1e-8)
    return np.clip(0.5 + 0.35 * np.tanh(z), 0.0, 1.0).astype(np.float64)


def generate_surface_optical(
    *,
    height: int,
    width: int,
    experiment_seed: int,
    cfg: NearFieldExteroceptionConfig,
    terrain_potential: np.ndarray | None = None,
    terrain_drag: np.ndarray | None = None,
    terrain_grad_x: np.ndarray | None = None,
    terrain_grad_y: np.ndarray | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """WORLD GT optical appearance tensor (3, H, W). Not cognition.

    Channels are anonymous optical measurements. Mapping may correlate with
    mechanics without exposing class labels.
    """
    mapping = clamp_optical_mapping(getattr(cfg, "optical_mapping", "INDEPENDENT"))
    mix = float(np.clip(getattr(cfg, "optical_correlation", 0.35), 0.0, 1.0))
    stacks: list[np.ndarray] = []
    channel_meta: list[dict[str, Any]] = []
    mechanics: list[np.ndarray | None] = []
    if terrain_potential is not None:
        mechanics.append(np.asarray(terrain_potential, dtype=np.float64))
    else:
        mechanics.append(None)
    if terrain_drag is not None:
        mechanics.append(np.asarray(terrain_drag, dtype=np.float64))
    else:
        mechanics.append(None)
    if terrain_grad_x is not None and terrain_grad_y is not None:
        mechanics.append(
            np.hypot(
                np.asarray(terrain_grad_x, dtype=np.float64),
                np.asarray(terrain_grad_y, dtype=np.float64),
            )
        )
    else:
        mechanics.append(None)

    for k in range(N_SURFACE_OPTICAL_CHANNELS):
        resolved = deterministic_namespace_seed(
            int(experiment_seed), f"surface_optical_c{k}"
        )
        rng = np.random.default_rng(resolved)
        base = _smooth_unit_field(rng, height, width)
        mech = mechanics[k] if k < len(mechanics) else None
        if mapping == "UNIFORM":
            field = np.full((height, width), 0.5, dtype=np.float64)
            used = "UNIFORM"
        elif mapping == "CORRELATED" and mech is not None:
            n = (mech - mech.mean()) / (mech.std() + 1e-8)
            shaped = 0.5 + 0.35 * np.tanh(n)
            field = (1.0 - mix) * base + mix * shaped
            used = "CORRELATED"
        elif mapping == "SHUFFLED":
            if mech is not None:
                n = (mech - mech.mean()) / (mech.std() + 1e-8)
                shaped = 0.5 + 0.35 * np.tanh(n)
                field = (1.0 - mix) * base + mix * shaped
            else:
                field = base
            flat = field.ravel().copy()
            rng.shuffle(flat)
            field = flat.reshape(field.shape)
            used = "SHUFFLED"
        else:
            field = base
            used = "INDEPENDENT"
        field = np.clip(field, 0.0, 1.0).astype(np.float64)
        stacks.append(field)
        channel_meta.append({
            "channel": k,
            "resolved_seed": int(resolved),
            "mapping_applied": used,
            "checksum": hashlib.sha256(field.tobytes()).hexdigest()[:16],
        })
    tensor = np.stack(stacks, axis=0)
    meta = {
        "experiment_seed": int(experiment_seed),
        "generator_version": SURFACE_OPTICAL_GENERATOR_VERSION,
        "optical_mapping": mapping,
        "optical_correlation": mix if mapping == "CORRELATED" else 0.0,
        "n_channels": N_SURFACE_OPTICAL_CHANNELS,
        "channels": channel_meta,
        "checksum": hashlib.sha256(tensor.tobytes()).hexdigest()[:16],
        "note": "WORLD GT optical appearance; cognition receives FOV-gated surface_c* only",
    }
    return tensor, meta


def install_surface_optical_on_planet(
    planet: PlanetState,
    *,
    experiment_seed: int,
    cfg: NearFieldExteroceptionConfig,
    force: bool = False,
) -> None:
    """Install optical tensor when discrimination is LOW/RICH (or force)."""
    mode = clamp_surface_discrimination(getattr(cfg, "visual_surface_discrimination", "OFF"))
    if mode == "OFF" and not force:
        if getattr(planet, "surface_optical", None) is None:
            planet.surface_optical = None
            planet.surface_optical_meta = None
        return
    existing = getattr(planet, "surface_optical", None)
    if existing is not None and not force:
        return
    h, w = int(planet.T.shape[0]), int(planet.T.shape[1])
    tensor, meta = generate_surface_optical(
        height=h,
        width=w,
        experiment_seed=int(experiment_seed),
        cfg=cfg,
        terrain_potential=getattr(planet, "terrain_potential", None),
        terrain_drag=getattr(planet, "terrain_drag", None),
        terrain_grad_x=getattr(planet, "terrain_grad_x", None),
        terrain_grad_y=getattr(planet, "terrain_grad_y", None),
    )
    planet.surface_optical = tensor
    planet.surface_optical_meta = meta


def surface_terrain_correlations(planet: PlanetState) -> dict[str, float | None]:
    """Observer audit: correlation of surface with terrain mechanics."""
    s = getattr(planet, "surface_response", None)
    if s is None:
        return {"vs_potential": None, "vs_drag": None, "vs_abs_grad": None}

    def _corr(a: np.ndarray, b: np.ndarray) -> float:
        aa = a.ravel().astype(np.float64)
        bb = b.ravel().astype(np.float64)
        if aa.std() < 1e-12 or bb.std() < 1e-12:
            return 0.0
        return float(np.corrcoef(aa, bb)[0, 1])

    out: dict[str, float | None] = {"vs_potential": None, "vs_drag": None, "vs_abs_grad": None}
    pot = getattr(planet, "terrain_potential", None)
    drag = getattr(planet, "terrain_drag", None)
    gx = getattr(planet, "terrain_grad_x", None)
    gy = getattr(planet, "terrain_grad_y", None)
    if pot is not None:
        out["vs_potential"] = _corr(s, pot)
    if drag is not None:
        out["vs_drag"] = _corr(s, drag)
    if gx is not None and gy is not None:
        out["vs_abs_grad"] = _corr(s, np.hypot(gx, gy))
    return out


# ---------------------------------------------------------------------------
# Sensor pipeline (instantaneous — no memory)
# ---------------------------------------------------------------------------

def _hash_noise(tick: int, ix: int, iy: int, amp: float) -> float:
    if amp <= 0.0:
        return 0.0
    x = (int(tick) * 1000003 + int(ix) * 9176 + int(iy) * 31337 + 7) % 2147483647
    u = (x % 1000000) / 1000000.0  # [0,1)
    return float(amp) * (2.0 * u - 1.0)


def compose_surface_and_body_optical(surf: float, body_opt: float) -> float:
    """Bounded soft-OR composition (deterministic, [0,1]).

    composed = 1 - (1 - surf) * (1 - body_opt)

    Does not mutate planet surface_response. No semantic branching.
    """
    s = float(np.clip(surf, 0.0, 1.0))
    b = float(np.clip(body_opt, 0.0, 1.0))
    return float(1.0 - (1.0 - s) * (1.0 - b))


def body_optical_occupancy(
    foreign_bodies: list[tuple[Any, Any]] | tuple[tuple[Any, Any], ...] | None,
    *,
    width: int,
    height: int,
) -> dict[tuple[int, int], float]:
    """Map (iy, ix) → max optical_response over foreign body sites.

    Anonymous physical occupancy only — no agent/experimenter/cognition labels.
    Multiple sites in one cell: take max (bounded; no additive explosion).
    """
    if not foreign_bodies:
        return {}
    from mechanistic_mind.physical_system.body_contact import footprint_cells

    occ: dict[tuple[int, int], float] = {}
    for body, body_cfg in foreign_bodies:
        if body is None or body_cfg is None:
            continue
        opt = float(np.clip(getattr(body_cfg, "optical_response", 0.65), 0.0, 1.0))
        if opt <= 0.0:
            continue
        for iy, ix in footprint_cells(body, body_cfg, width, height):
            key = (int(iy), int(ix))
            prev = occ.get(key, 0.0)
            if opt > prev:
                occ[key] = opt
    return occ


# Tick-scoped sample_near_field reuse (identical inputs → identical output object
# graph). Cleared whenever world.tick changes. Callers must treat results as
# read-only (existing code only reads).
_SNF_TICK: int | None = None
_SNF_CACHE: dict[tuple[Any, ...], dict[str, Any]] = {}


def _snf_fb_key(
    foreign_bodies: list[tuple[Any, Any]] | tuple[tuple[Any, Any], ...] | None,
) -> tuple[tuple[int, float, float, float], ...]:
    if not foreign_bodies:
        return ()
    out: list[tuple[int, float, float, float]] = []
    for item in foreign_bodies:
        if len(item) < 1:
            continue
        b = item[0]
        out.append(
            (
                id(b),
                float(getattr(b, "x", 0.0) or 0.0),
                float(getattr(b, "y", 0.0) or 0.0),
                float(getattr(b, "theta", 0.0) or 0.0),
            )
        )
    return tuple(out)


def sample_near_field(
    *,
    world: PlanetState,
    body: PhysicalBodyState,
    cfg: NearFieldExteroceptionConfig,
    tick: int | None = None,
    foreign_bodies: list[tuple[Any, Any]] | tuple[tuple[Any, Any], ...] | None = None,
    diagnostic: bool = False,
) -> dict[str, Any]:
    """Full physical sensor evaluation + Observer diagnostics.

    Cognition-visible fragments are only under key ``fragments`` (exo_0..exo_2).
    Optional ``foreign_bodies``: sequence of (PhysicalBodyState, PhysicalBodyConfig)
    excluding the observing body (self-exclusion by caller).
    """
    global _SNF_TICK, _SNF_CACHE
    h, w = int(world.T.shape[0]), int(world.T.shape[1])
    t = int(world.tick if tick is None else tick)
    if _SNF_TICK != t:
        _SNF_CACHE.clear()
        _SNF_TICK = t
    bx = float(body.x)
    by = float(body.y)
    body_theta = float(getattr(body, "theta", 0.0) or 0.0)
    head_on = bool(getattr(body, "_articulated_head_enabled", False))
    head_rel = float(getattr(body, "head_relative_angle", 0.0) or 0.0)
    radius = clamp_vision_radius(getattr(cfg, "radius", DEFAULT_VISION_RADIUS))
    cache_key = (
        id(world),
        id(body),
        t,
        round(bx, 6),
        round(by, 6),
        round(body_theta, 6),
        round(head_rel, 6),
        head_on,
        radius,
        float(getattr(cfg, "fov_deg", 0.0) or 0.0),
        float(getattr(cfg, "illumination_min", 0.0) or 0.0),
        float(getattr(cfg, "illumination_max", 0.0) or 0.0),
        bool(getattr(cfg, "illumination_enabled", True)),
        float(getattr(cfg, "threshold", 0.0) or 0.0),
        bool(getattr(cfg, "body_optics_active", False)),
        bool(getattr(cfg, "vision_contributes", False)),
        clamp_surface_discrimination(getattr(cfg, "visual_surface_discrimination", "OFF")),
        clamp_spatial_vision(getattr(cfg, "spatial_vision", DEFAULT_SPATIAL_VISION)),
        clamp_spatial_sectors(getattr(cfg, "spatial_sectors", DEFAULT_SPATIAL_SECTORS)),
        id(getattr(world, "surface_optical", None)),
        float(np.sum(world.surface_response)) if getattr(world, "surface_response", None) is not None else 0.0,
        _snf_fb_key(foreign_bodies),
    )
    hit = _SNF_CACHE.get(cache_key)
    if hit is not None:
        _prof_count("vision_cache_hit")
        if diagnostic:
            tagged = dict(hit)
            tagged["fpv_receipts"] = compact_fpv_receipts(hit)
            return tagged
        return hit
    _prof_count("vision_cache_miss")

    # Sensor orientation authority: head_world when articulated head enabled on body.
    if head_on:
        from mechanistic_mind.physical_system.articulated_head import head_world_heading

        theta = head_world_heading(body)
        sensor_status = "AVAILABLE"
    else:
        theta = body_theta
        sensor_status = "NOT_AVAILABLE"
    cx = int(math.floor(bx)) % w
    cy = int(math.floor(by)) % h
    neighbors = moore_neighbor_cells(cx, cy, w, h, radius=radius)
    illum = illumination_intensity(t, cfg)
    surface = getattr(world, "surface_response", None)
    body_occ = (
        body_optical_occupancy(foreign_bodies, width=w, height=h)
        if cfg.body_optics_active
        else {}
    )

    channels = [0.0] * N_EXO_CHANNELS
    disc_mode = clamp_surface_discrimination(
        getattr(cfg, "visual_surface_discrimination", "OFF")
    )
    n_surf = surface_channel_count(disc_mode)
    optical = getattr(world, "surface_optical", None)
    if n_surf > 0 and optical is None:
        n_surf = 0
    surf_acc = [[0.0] * N_EXO_CHANNELS for _ in range(n_surf)] if n_surf else []
    neighbor_rows: list[dict[str, Any]] = []
    detectable = 0
    aggregate = 0.0

    with _prof_span("vis_sample"):
        for nix, niy in neighbors:
            # Relative displacement: body center → neighbor cell center.
            ncx = float(nix) + 0.5
            ncy = float(niy) + 0.5
            dx = toroidal_delta(bx, ncx, w)
            dy = toroidal_delta(by, ncy, h)
            dist = float(math.hypot(dx, dy))
            direction = math.atan2(dy, dx)
            rel = wrap_angle(direction - theta)
            ang = angular_sensitivity(rel, cfg.fov_deg, cfg.angular_power)
            inside = ang > 0.0
            surf = float(surface[niy, nix]) if surface is not None else 0.0
            body_opt = float(body_occ.get((int(niy), int(nix)), 0.0))
            composed = compose_surface_and_body_optical(surf, body_opt)
            raw = composed * illum
            dist_f = distance_attenuation(dist, cfg.distance_k)
            noise = _hash_noise(t, nix, niy, cfg.signal_hash_noise)
            pre = float(cfg.gain) * raw * dist_f * ang + noise
            pre = max(0.0, pre)
            sat = min(float(cfg.saturation), pre)
            above = sat >= float(cfg.threshold)
            final = float(sat) if above and inside else 0.0
            opt_triplet = [0.0, 0.0, 0.0]
            if optical is not None:
                for ck in range(min(N_SURFACE_OPTICAL_CHANNELS, int(optical.shape[0]))):
                    opt_triplet[ck] = float(optical[ck, niy, nix])
            if final > 0.0:
                detectable += 1
                aggregate += final

            neighbor_rows.append({
                "cell": [int(nix), int(niy)],
                "dx": dx,
                "dy": dy,
                "distance": dist,
                "relative_angle_rad": rel,
                "relative_angle_deg": float(math.degrees(rel)),
                "inside_fov": bool(inside),
                "angular_factor": float(ang),
                "distance_factor": float(dist_f),
                "surface_response": surf,
                "body_optical": body_opt,
                "composed_optical": composed,
                "surface_optical": opt_triplet,
                "illumination": illum,
                "raw_observable": float(raw),
                "pre_threshold": float(pre),
                "detectable": bool(above and inside and final > 0.0),
                "final_contribution": float(final),
            })

    spatial_mode = clamp_spatial_vision(getattr(cfg, "spatial_vision", DEFAULT_SPATIAL_VISION))
    n_spat = clamp_spatial_sectors(getattr(cfg, "spatial_sectors", DEFAULT_SPATIAL_SECTORS))
    with _prof_span("vis_spatial"):
        apply_spatial_visibility(
            neighbor_rows, mode=spatial_mode, fov_deg=float(cfg.fov_deg), n_sectors=n_spat
        )
    occlude = spatial_vision_uses_occlusion(spatial_mode)
    spatial_exo = [0.0] * n_spat if spatial_vision_uses_extra_bins(spatial_mode) else []
    spatial_surf = (
        [[0.0] * n_spat for _ in range(n_surf)]
        if spatial_exo and n_surf
        else []
    )
    with _prof_span("vis_assemble"):
        for row in neighbor_rows:
            contrib = float(row.get("visible_contribution") or 0.0) if occlude else float(row.get("final_contribution") or 0.0)
            if contrib <= 0.0:
                continue
            rel = float(row.get("relative_angle_rad") or 0.0)
            bin_i = fov_sector_index(rel, cfg.fov_deg)
            if bin_i is None:
                bin_i = 0
            channels[bin_i] += contrib
            opt_triplet = row.get("surface_optical") or [0.0, 0.0, 0.0]
            for ck in range(n_surf):
                surf_acc[ck][bin_i] += float(opt_triplet[ck] if ck < len(opt_triplet) else 0.0) * contrib
            spat = row.get("spatial_sector")
            if spatial_exo and spat is not None:
                si = int(spat)
                if 0 <= si < n_spat:
                    spatial_exo[si] += contrib
                    for ck in range(len(spatial_surf)):
                        spatial_surf[ck][si] += float(opt_triplet[ck] if ck < len(opt_triplet) else 0.0) * contrib

    # Saturate channel sums into [0,1] cognition fragments.
    fragments: dict[str, float] = {}
    for i, v in enumerate(channels):
        fragments[f"exo_{i}"] = float(max(0.0, min(1.0, v)))
    surface_fragments: dict[str, float] = {}
    for ck, bins in enumerate(surf_acc):
        for bi, v in enumerate(bins):
            surface_fragments[f"surface_c{ck}_{bi}"] = float(max(0.0, min(1.0, v)))
    spatial_fragments: dict[str, float] = {}
    for i, v in enumerate(spatial_exo):
        spatial_fragments[f"spatial_exo_a{i}"] = float(max(0.0, min(1.0, v)))
    for ck, bins in enumerate(spatial_surf):
        for i, v in enumerate(bins):
            spatial_fragments[f"spatial_surface_c{ck}_a{i}"] = float(max(0.0, min(1.0, v)))

    out = {
        "tick": t,
        "body_xy": [bx, by],
        "body_cell": [cx, cy],
        "body_theta": body_theta,
        "head_relative_angle": head_rel,
        "head_world_heading": float(theta),
        "head_omega": float(getattr(body, "head_omega", 0.0) or 0.0),
        "neck_motor": float(getattr(body, "neck_motor", 0.0) or 0.0),
        "sensor_forward_axis": float(theta),
        "fov_deg": float(cfg.fov_deg),
        "vision_radius": int(radius),
        "radius": int(radius),
        "max_candidates": moore_max_candidates(radius),
        "illumination": illum,
        "illumination_enabled": bool(getattr(cfg, "illumination_enabled", True)),
        "illumination_phase_gt": illumination_phase_gt(t, cfg.illumination_period),
        "perception_enabled": bool(cfg.perception_enabled),
        "vision_contributes": bool(cfg.vision_contributes),
        "body_optical_enabled": bool(cfg.body_optics_active),
        "n_candidates": len(neighbors),
        "n_inside_fov": sum(1 for r in neighbor_rows if r["inside_fov"]),
        "n_detectable": detectable,
        "n_body_optical_cells": sum(1 for r in neighbor_rows if r["body_optical"] > 0.0),
        "aggregate_intensity": float(aggregate),
        "fragments": fragments,
        "surface_fragments": surface_fragments,
        "spatial_fragments": spatial_fragments,
        "visual_surface_discrimination": disc_mode,
        "optical_mapping": clamp_optical_mapping(getattr(cfg, "optical_mapping", "INDEPENDENT")),
        "spatial_vision": spatial_mode,
        "spatial_sectors": int(n_spat),
        "n_occluded": sum(1 for r in neighbor_rows if r.get("visibility") == "OCCLUDED"),
        "neighbors": neighbor_rows,
        "surface_meta": dict(getattr(world, "surface_meta", None) or {}),
        "ACTIVE_SENSOR_ORIENTATION": sensor_status,
        "articulated_head_enabled": head_on,
        "optical_composition": "composed = 1 - (1-surf)*(1-body_opt); body_opt = max foreign optical_response",
    }
    _SNF_CACHE[cache_key] = out
    if diagnostic:
        tagged = dict(out)
        tagged["fpv_receipts"] = compact_fpv_receipts(out)
        return tagged
    return out


def cognition_exo_fragments(
    *,
    world: PlanetState,
    body: PhysicalBodyState,
    cfg: NearFieldExteroceptionConfig,
    foreign_bodies: list[tuple[Any, Any]] | tuple[tuple[Any, Any], ...] | None = None,
) -> dict[str, float]:
    """Cognition-only: anonymous exo_* floats.

    When vision contributes: always returns exo_0/1/2 (zeros allowed).
    Empty dict only when vision is OFF / ablated — never when ON-but-dark.
    """
    if not cfg.vision_contributes:
        return {}
    sample = sample_near_field(
        world=world, body=body, cfg=cfg, foreign_bodies=foreign_bodies
    )
    # Guarantee channel keys even if sample path is empty.
    out = {f"exo_{i}": 0.0 for i in range(N_EXO_CHANNELS)}
    out.update({k: float(v) for k, v in (sample.get("fragments") or {}).items()})
    return out


def cognition_surface_fragments(
    *,
    world: PlanetState,
    body: PhysicalBodyState,
    cfg: NearFieldExteroceptionConfig,
    foreign_bodies: list[tuple[Any, Any]] | tuple[tuple[Any, Any], ...] | None = None,
) -> dict[str, float]:
    """Cognition-only: anonymous surface_c* floats. Empty when OFF / vision ablated."""
    if not cfg.vision_contributes:
        return {}
    mode = clamp_surface_discrimination(getattr(cfg, "visual_surface_discrimination", "OFF"))
    if mode == "OFF":
        return {}
    sample = sample_near_field(
        world=world, body=body, cfg=cfg, foreign_bodies=foreign_bodies
    )
    keys = surface_observation_keys(mode)
    out = {k: 0.0 for k in keys}
    out.update({k: float(v) for k, v in (sample.get("surface_fragments") or {}).items() if k in out})
    return out


def cognition_spatial_fragments(
    *,
    world: PlanetState,
    body: PhysicalBodyState,
    cfg: NearFieldExteroceptionConfig,
    foreign_bodies: list[tuple[Any, Any]] | tuple[tuple[Any, Any], ...] | None = None,
) -> dict[str, float]:
    """Cognition-only spatial angular bins. Empty in LEGACY / vision OFF."""
    if not cfg.vision_contributes:
        return {}
    mode = clamp_spatial_vision(getattr(cfg, "spatial_vision", DEFAULT_SPATIAL_VISION))
    if not spatial_vision_uses_extra_bins(mode):
        return {}
    sample = sample_near_field(
        world=world, body=body, cfg=cfg, foreign_bodies=foreign_bodies
    )
    keys = spatial_observation_keys(
        spatial_mode=mode,
        discrimination=getattr(cfg, "visual_surface_discrimination", "OFF"),
        n_sectors=getattr(cfg, "spatial_sectors", DEFAULT_SPATIAL_SECTORS),
    )
    out = {k: 0.0 for k in keys}
    out.update({k: float(v) for k, v in (sample.get("spatial_fragments") or {}).items() if k in out})
    return out


def calibrated_near_field_config() -> NearFieldExteroceptionConfig:
    """Beta 2 calibrated/structured preset stamp — validated constants unchanged."""
    return NearFieldExteroceptionConfig(
        mode="EXPERIMENTAL",
        perception_enabled=True,
        illumination_enabled=True,
        body_optical_enabled=True,
        radius=DEFAULT_VISION_RADIUS,
        fov_deg=DEFAULT_FOV_DEG,
        illumination_period=DEFAULT_ILLUMINATION_PERIOD,
        illumination_min=0.15,
        illumination_max=1.0,
        surface_enabled=True,
        surface_mode="INDEPENDENT",
    )


ACCEPTANCE_GATES = {
    "P1_LOCAL_SOURCE_DOMAIN": "Only Moore-radius-R cells may contribute (default R=1)",
    "P2_EIGHT_NEIGHBOR_GEOMETRY": "R=1 → exactly 8 neighbors under WRAP_PERIODIC",
    "P3_NOT_360_DEGREES": "Outside FOV contribute exactly zero",
    "P4_REAR_BLIND": "Directly rear source unavailable",
    "P5_ROTATION_REVEALS": "Physical rotation brings rear source into FOV",
    "P6_DISTANCE_PHYSICAL": "Diagonal vs cardinal distance differs",
    "P7_ANGULAR_CONTINUITY": "Response continuous with relative angle inside FOV",
    "P8_ILLUMINATION_CAUSAL": "Illumination changes sensor signal",
    "P9_DARK_REDUCES_AVAILABILITY": "Lower illumination reduces detectable fragments",
    "P10_NO_MECHANICAL_GT_LEAK": "Terrain mechanics not directly exposed",
    "P11_APPEARANCE_MECHANICS_SEPARABLE": "Appearance and mechanics independently variable",
    "P12_NO_RESOURCE_GT_LEAK": "R_A/R_B/suitability not exposed",
    "P13_NO_DISTANT_MAP_ACCESS": "No source beyond configured Moore radius",
    "P14_SENSOR_ABLATION_CLEAN": "Ablation removes only new sensor channel",
    "P15_PHYSICS_UNCHANGED": "Sensor does not alter controlled body physics",
    "P16_NO_FREE_WORK": "Illumination/perception creates no work",
    "P17_TEMPORAL_CONTINUITY": "Illumination changes smoothly",
    "P18_TIMESCALE_SEPARATED": "Illumination period quantitatively justified",
    "P19_DETERMINISTIC_REPLAY": "Same seed/config/tick/pose → same sensor state",
    "P20_OBSERVER_COGNITION_BOUNDARY": "Observer GT richer than cognition input",
    "P21_SENSOR_HAS_NO_MEMORY": "Sensor depends only on current physical state",
    "P22_ORIENTATION_STATUS_EXPLICIT": "ACTIVE_SENSOR_ORIENTATION reported",
}

ACTIVE_SENSOR_ORIENTATION = "NOT_AVAILABLE"  # overridden per-sample when articulated head ON

FOV_SELECTION_RATIONALE = {
    "candidates_deg": list(FOV_CANDIDATES_DEG),
    "selected_deg": DEFAULT_FOV_DEG,
    "rationale": (
        "On a Moore grid, FOV=60° often admits only the forward cell (flicker). "
        "FOV=90° places diagonals at the hard edge. FOV=120° (±60°) includes the "
        "forward cardinal plus both forward diagonals under cardinal heading, "
        "strongly privileges forward space, zeros rear (±180°), and keeps side "
        "cardinals out — making physical rotation meaningful without 360° vision."
    ),
}

ILLUMINATION_SELECTION_RATIONALE = {
    "candidates": list(ILLUMINATION_PERIOD_CANDIDATES),
    "selected": DEFAULT_ILLUMINATION_PERIOD,
    "hierarchy": {
        "T_body_onset": 1,
        "T_body_relax": "4-19",
        "T_cell": 6,
        "T_region": 25,
        "T_history": 80,
        "T_climate": 800,
        "F_fast_calibrated": 320,
    },
    "rationale": (
        "Period 240 = 3×T_history, well above body/cell/region scales, clearly "
        "below T_climate=800, and distinct from calibrated F_fast=320 to avoid "
        "aliasing. Not mapped to Earth hours."
    ),
}
