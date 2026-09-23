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

SURFACE_GENERATOR_VERSION = "surface_observable_v1"
ILLUMINATION_GENERATOR_VERSION = "illumination_cycle_v1"

# Predeclared FOV candidates (degrees, full width). Selected default: 120.
FOV_CANDIDATES_DEG = (60.0, 90.0, 120.0)
DEFAULT_FOV_DEG = 120.0

# Illumination period candidates (ticks). Selected: 240.
ILLUMINATION_PERIOD_CANDIDATES = (160, 240, 320, 400)
DEFAULT_ILLUMINATION_PERIOD = 240

# Angular channel bins inside FOV → cognition keys exo_0..exo_2 (L / F / R).
N_EXO_CHANNELS = 3

# LIVE Observer control: Moore candidate radius (default R=1 = legacy).
VISION_RADIUS_MIN = 1
VISION_RADIUS_MAX = 3
DEFAULT_VISION_RADIUS = 1

SurfaceMode = Literal["INDEPENDENT", "CORRELATED", "SHUFFLED"]


def clamp_vision_radius(radius: Any) -> int:
    """Clamp to {1,2,3}. Missing/invalid → default R=1 (legacy)."""
    try:
        r = int(radius)
    except (TypeError, ValueError):
        return DEFAULT_VISION_RADIUS
    return max(VISION_RADIUS_MIN, min(VISION_RADIUS_MAX, r))


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

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["radius"] = clamp_vision_radius(d.get("radius", DEFAULT_VISION_RADIUS))
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
        bool(getattr(cfg, "body_optics_active", False)),
        bool(getattr(cfg, "vision_contributes", False)),
        _snf_fb_key(foreign_bodies),
    )
    hit = _SNF_CACHE.get(cache_key)
    if hit is not None:
        return hit

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
    neighbor_rows: list[dict[str, Any]] = []
    detectable = 0
    aggregate = 0.0

    half_fov = 0.5 * float(cfg.fov_deg)
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
        if final > 0.0:
            detectable += 1
            aggregate += final
            # Bin by relative angle within FOV: left / forward / right.
            # Map rel ∈ [-half, +half] → [0, N_EXO_CHANNELS).
            u = (rel + math.radians(half_fov)) / max(1e-9, math.radians(2.0 * half_fov))
            bin_i = int(np.clip(math.floor(u * N_EXO_CHANNELS), 0, N_EXO_CHANNELS - 1))
            channels[bin_i] += final

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
            "illumination": illum,
            "raw_observable": float(raw),
            "pre_threshold": float(pre),
            "detectable": bool(above and inside and final > 0.0),
            "final_contribution": float(final),
        })

    # Saturate channel sums into [0,1] cognition fragments.
    fragments: dict[str, float] = {}
    for i, v in enumerate(channels):
        fragments[f"exo_{i}"] = float(max(0.0, min(1.0, v)))

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
        "neighbors": neighbor_rows,
        "surface_meta": dict(getattr(world, "surface_meta", None) or {}),
        "ACTIVE_SENSOR_ORIENTATION": sensor_status,
        "articulated_head_enabled": head_on,
        "optical_composition": "composed = 1 - (1-surf)*(1-body_opt); body_opt = max foreign optical_response",
    }
    _SNF_CACHE[cache_key] = out
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
