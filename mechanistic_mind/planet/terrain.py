"""Spatial terrain drag + potential — physical fields only.

Observer may interpret structures; runtime stores only:
  terrain_drag >= 0
  terrain_potential (scalar)
  precomputed ∇potential

Never credits mechanical_work_reservoir.
Never enters agent cognition as ground-truth terrain labels.

Seeding:
  Default terrain_seed = deterministic_namespace_seed(experiment_seed, \"terrain\").
  Terrain uses its own RNG stream (numpy SeedSequence from terrain_seed only).
  Climate / cognition / agent RNG consumption cannot alter terrain.
  Optional TerrainConfig.terrain_seed override for matched controls.
"""
from __future__ import annotations

import hashlib
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

import numpy as np

from mechanistic_mind.planet.topology import gradient, laplacian


TerrainMode = Literal["FLAT", "CORRELATED", "RUGGED"]

# Bump when generator algorithm / acceptance gates change (breaks bit-identity).
TERRAIN_GENERATOR_VERSION = "terrain_v2"


@dataclass
class TraversabilityGates:
    """Conservative physical geography acceptance gates (serializable)."""

    max_feasible_delta_potential: float = 0.22
    extreme_gradient: float = 0.28
    min_feasible_transition_frac: float = 0.58
    min_largest_component_frac: float = 0.52
    max_extreme_gradient_frac: float = 0.18
    max_generation_attempts: int = 8

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "TraversabilityGates":
        if not data:
            return cls()
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})


@dataclass
class TerrainConfig:
    """Bounded terrain parameters. Default OFF — baseline ecology unchanged."""

    enabled: bool = False
    mode: str = "FLAT"  # FLAT | CORRELATED | RUGGED
    drag_base: float = 0.0
    drag_amplitude: float = 0.0
    potential_amplitude: float = 0.0
    correlation_scale: float = 6.0
    # Multi-scale mix (weights re-normalized). Large/medium/small geography.
    large_scale_weight: float = 0.55
    medium_scale_weight: float = 0.30
    small_scale_weight: float = 0.15
    # Rare sharp discontinuities (ledges). 0 disables.
    discontinuity_rate: float = 0.012
    discontinuity_amplitude: float = 0.55
    force_scale: float = 0.06  # κ for F += -κ ∇Φ (conservative external)
    drag_coupling: float = 1.0  # adds to body.drag: F -= (drag + coupling*γ) v
    max_gradient: float = 0.40
    # Near-rest WAIT attenuates κ. Kinetic WAIT (speed >= threshold) keeps full κ.
    wait_force_scale: float = 0.20
    kinetic_speed_threshold: float = 0.025
    # Optional explicit seed for matched-control experiments. None => namespace seed.
    terrain_seed: int | None = None
    traversability: TraversabilityGates = field(default_factory=TraversabilityGates)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "TerrainConfig":
        if not data:
            return cls()
        kw = {k: data[k] for k in cls.__dataclass_fields__ if k in data and k != "traversability"}
        tv = data.get("traversability")
        if isinstance(tv, dict):
            kw["traversability"] = TraversabilityGates.from_dict(tv)
        elif isinstance(tv, TraversabilityGates):
            kw["traversability"] = tv
        return cls(**kw)


def deterministic_namespace_seed(experiment_seed: int, namespace: str) -> int:
    """Derive an independent seed stream from experiment_seed + namespace.

    Does not consume shared runtime / climate / cognition RNG.
    Stable across process runs; independent of unrelated RNG call order.
    """
    payload = f"{int(experiment_seed)}\0{namespace}\0{TERRAIN_GENERATOR_VERSION}".encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    # Positive 31-bit int suitable for numpy SeedSequence / default_rng.
    return int.from_bytes(digest[:8], "big") & 0x7FFFFFFF


def resolve_terrain_seed(experiment_seed: int, config: TerrainConfig) -> tuple[int, str]:
    """Return (resolved_terrain_seed, source) where source is override|namespace."""
    if config.terrain_seed is not None:
        return int(config.terrain_seed), "override"
    return deterministic_namespace_seed(int(experiment_seed), "terrain"), "namespace"


def attempt_stream_seed(terrain_seed: int, attempt: int) -> int:
    """Deterministic per-attempt stream derived from resolved terrain_seed."""
    payload = f"{int(terrain_seed)}\0gen_attempt\0{int(attempt)}\0{TERRAIN_GENERATOR_VERSION}".encode(
        "utf-8"
    )
    digest = hashlib.sha256(payload).digest()
    return int.from_bytes(digest[:8], "big") & 0x7FFFFFFF


def terrain_field_checksum(
    potential: np.ndarray | None,
    drag: np.ndarray | None,
) -> str:
    """Short stable hash of terrain grids for metadata / Observer GT."""
    h = hashlib.sha256()
    h.update(TERRAIN_GENERATOR_VERSION.encode("utf-8"))
    if potential is None or drag is None:
        h.update(b"absent")
        return h.hexdigest()[:16]
    h.update(np.ascontiguousarray(potential, dtype=np.float64).tobytes())
    h.update(np.ascontiguousarray(drag, dtype=np.float64).tobytes())
    return h.hexdigest()[:16]


def _smooth_field(z: np.ndarray, passes: int) -> np.ndarray:
    out = np.asarray(z, dtype=np.float64)
    for _ in range(max(0, int(passes))):
        out = out - 0.25 * laplacian(out)
    return out


def _bilinear_upsample(coarse: np.ndarray, h: int, w: int) -> np.ndarray:
    ch, cw = coarse.shape
    yy = np.linspace(0, ch - 1, h)
    xx = np.linspace(0, cw - 1, w)
    yi, xi = np.meshgrid(yy, xx, indexing="ij")
    y0 = np.floor(yi).astype(int)
    x0 = np.floor(xi).astype(int)
    y1 = np.clip(y0 + 1, 0, ch - 1)
    x1 = np.clip(x0 + 1, 0, cw - 1)
    wy = yi - y0
    wx = xi - x0
    return (
        (1 - wy) * (1 - wx) * coarse[y0, x0]
        + (1 - wy) * wx * coarse[y0, x1]
        + wy * (1 - wx) * coarse[y1, x0]
        + wy * wx * coarse[y1, x1]
    )


def _octave_field(
    rng: np.random.Generator,
    h: int,
    w: int,
    *,
    coarse_div: int,
    smooth_passes: int,
) -> np.ndarray:
    """Coarse correlated field upsampled + lightly smoothed (continuous geography)."""
    ch = max(2, h // max(1, int(coarse_div)))
    cw = max(2, w // max(1, int(coarse_div)))
    coarse = rng.standard_normal((ch, cw))
    up = _bilinear_upsample(coarse, h, w)
    up = _smooth_field(up, max(1, int(smooth_passes)))
    return (up - up.mean()) / (up.std() + 1e-8)


def _multi_scale_geography(
    rng: np.random.Generator,
    h: int,
    w: int,
    cfg: TerrainConfig,
) -> np.ndarray:
    """Broad lowlands/elevations + hills/basins + local variation (not cell noise)."""
    scale = max(2.0, float(cfg.correlation_scale))
    large = _octave_field(
        rng, h, w, coarse_div=max(4, int(round(scale * 1.2))), smooth_passes=max(4, int(scale))
    )
    medium = _octave_field(
        rng, h, w, coarse_div=max(3, int(round(scale * 0.55))), smooth_passes=max(2, int(scale * 0.45))
    )
    small = _octave_field(
        rng, h, w, coarse_div=max(2, int(round(scale * 0.25))), smooth_passes=max(1, int(scale * 0.2))
    )
    wl = max(0.0, float(cfg.large_scale_weight))
    wm = max(0.0, float(cfg.medium_scale_weight))
    ws = max(0.0, float(cfg.small_scale_weight))
    s = wl + wm + ws
    if s < 1e-12:
        wl, wm, ws, s = 1.0, 0.0, 0.0, 1.0
    mix = (wl * large + wm * medium + ws * small) / s
    return (mix - mix.mean()) / (mix.std() + 1e-8)


def _apply_rare_discontinuities(
    pot: np.ndarray,
    rng: np.random.Generator,
    cfg: TerrainConfig,
) -> np.ndarray:
    """Sparse ledge-like steps. Rare; most neighbors stay smooth."""
    rate = float(cfg.discontinuity_rate)
    amp = float(cfg.discontinuity_amplitude)
    if rate <= 0.0 or amp <= 0.0:
        return pot
    h, w = pot.shape
    out = pot.copy()
    n_events = int(max(0, round(rate * h * w)))
    n_events = min(n_events, max(1, (h * w) // 40)) if rate > 0 else 0
    for _ in range(n_events):
        cy = int(rng.integers(0, h))
        cx = int(rng.integers(0, w))
        ang = float(rng.uniform(0.0, 2.0 * np.pi))
        ux, uy = float(np.cos(ang)), float(np.sin(ang))
        sign = 1.0 if rng.random() < 0.5 else -1.0
        radius = float(rng.uniform(1.5, 3.5))
        yy, xx = np.ogrid[:h, :w]
        dy = ((yy - cy + h // 2) % h) - h // 2
        dx = ((xx - cx + w // 2) % w) - w // 2
        dist = np.hypot(dx, dy)
        side = dx * ux + dy * uy
        edge = 0.5 * (1.0 + np.tanh(side / 0.75))
        mask = np.exp(-(dist * dist) / (2.0 * radius * radius))
        out = out + sign * amp * edge * mask
    return out


def _clamp_gradient(
    pot: np.ndarray, max_gradient: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    gy, gx = gradient(pot)
    max_g = max(1e-9, float(max_gradient))
    mag = np.hypot(gx, gy)
    over = mag > max_g
    if np.any(over):
        scale_g = np.ones_like(mag)
        scale_g[over] = max_g / mag[over]
        gx = gx * scale_g
        gy = gy * scale_g
    return pot, gy, gx


def _correlated_noise_from_rng(rng: np.random.Generator, h: int, w: int, scale: float) -> np.ndarray:
    """Legacy helper retained for tests / RUGGED mix; prefer multi-scale geography."""
    return _octave_field(
        rng, h, w, coarse_div=max(2, int(round(max(2.0, scale) * 0.5))), smooth_passes=max(1, int(scale))
    )


def generate_terrain_fields_raw(
    *,
    height: int,
    width: int,
    attempt_seed: int,
    config: TerrainConfig,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Single generation attempt (no traversability loop)."""
    h, w = int(height), int(width)
    cfg = config
    mode = str(cfg.mode or "FLAT").upper()
    if not cfg.enabled or mode == "FLAT":
        pot = np.zeros((h, w), dtype=np.float64)
        drag = np.full((h, w), max(0.0, float(cfg.drag_base)), dtype=np.float64)
        gy, gx = gradient(pot)
        return pot, drag, gy, gx

    root = np.random.SeedSequence(int(attempt_seed) & 0xFFFFFFFF)
    pot_ss, drag_ss, disc_ss, rugged_ss = root.spawn(4)
    pot_rng = np.random.default_rng(pot_ss)
    drag_rng = np.random.default_rng(drag_ss)
    disc_rng = np.random.default_rng(disc_ss)
    rugged_rng = np.random.default_rng(rugged_ss)

    amp_p = float(cfg.potential_amplitude)
    amp_d = float(cfg.drag_amplitude)
    base_d = max(0.0, float(cfg.drag_base))

    pot_n = _multi_scale_geography(pot_rng, h, w, cfg)
    drag_n = _multi_scale_geography(drag_rng, h, w, cfg)
    if mode == "RUGGED":
        pot_n = pot_n + 0.25 * _octave_field(rugged_rng, h, w, coarse_div=3, smooth_passes=2)
        drag_n = drag_n + 0.30 * _octave_field(rugged_rng, h, w, coarse_div=3, smooth_passes=2)
        pot_n = (pot_n - pot_n.mean()) / (pot_n.std() + 1e-8)
        drag_n = (drag_n - drag_n.mean()) / (drag_n.std() + 1e-8)

    pot = amp_p * pot_n
    pot = _apply_rare_discontinuities(pot, disc_rng, cfg)
    pot = pot - pot.mean()
    if amp_p > 1e-12:
        pot = pot * (amp_p / (float(np.max(np.abs(pot))) + 1e-8)) * 0.92

    drag = base_d + amp_d * 0.5 * (drag_n + 1.0)
    drag = np.maximum(drag, 0.0)
    pot, gy, gx = _clamp_gradient(pot, float(cfg.max_gradient))
    return pot, drag, gy, gx


def audit_physical_traversability(
    potential: np.ndarray,
    grad_y: np.ndarray,
    grad_x: np.ndarray,
    gates: TraversabilityGates,
) -> dict[str, Any]:
    """Deterministic physical transition audit (no cognition / pathfinding agent)."""
    pot = np.asarray(potential, dtype=np.float64)
    h, w = pot.shape
    max_d = float(gates.max_feasible_delta_potential)
    extreme_g = float(gates.extreme_gradient)
    mag = np.hypot(np.asarray(grad_x, dtype=np.float64), np.asarray(grad_y, dtype=np.float64))

    n_edges = 0
    n_feasible = 0
    feasible_nbrs: list[list[tuple[int, int]]] = [[] for _ in range(h * w)]

    def cell_idx(y: int, x: int) -> int:
        return y * w + x

    for y in range(h):
        for x in range(w):
            for dy, dx in ((0, 1), (1, 0)):
                y2 = (y + dy) % h
                x2 = (x + dx) % w
                n_edges += 1
                dphi = abs(float(pot[y, x] - pot[y2, x2]))
                if dphi <= max_d:
                    n_feasible += 1
                    a, b = cell_idx(y, x), cell_idx(y2, x2)
                    feasible_nbrs[a].append((y2, x2))
                    feasible_nbrs[b].append((y, x))

    seen = np.zeros(h * w, dtype=bool)
    sizes: list[int] = []
    largest = 0
    for start in range(h * w):
        if seen[start]:
            continue
        q: deque[int] = deque([start])
        seen[start] = True
        size = 0
        while q:
            u = q.popleft()
            size += 1
            for vy, vx in feasible_nbrs[u]:
                v = cell_idx(vy, vx)
                if not seen[v]:
                    seen[v] = True
                    q.append(v)
        sizes.append(size)
        if size > largest:
            largest = size

    n_cells = h * w
    feasible_frac = float(n_feasible) / float(max(1, n_edges))
    largest_frac = float(largest) / float(max(1, n_cells))
    extreme_frac = float(np.mean(mag >= extreme_g))
    n_components = len(sizes)
    isolated = int(sum(1 for s in sizes if s <= max(2, n_cells // 100)))
    neighbor_deltas = [
        abs(float(pot[y, x] - pot[y, (x + 1) % w])) for y in range(h) for x in range(w)
    ]
    passed = (
        feasible_frac >= float(gates.min_feasible_transition_frac)
        and largest_frac >= float(gates.min_largest_component_frac)
        and extreme_frac <= float(gates.max_extreme_gradient_frac)
    )
    return {
        "passed": bool(passed),
        "feasible_transition_frac": feasible_frac,
        "largest_component_size": int(largest),
        "largest_component_frac": largest_frac,
        "n_components": int(n_components),
        "n_isolated_small_components": isolated,
        "extreme_gradient_frac": extreme_frac,
        "gradient_mag_mean": float(np.mean(mag)),
        "gradient_mag_p90": float(np.percentile(mag, 90)),
        "neighbor_delta_phi_mean": float(np.mean(neighbor_deltas)),
        "gates": gates.to_dict(),
    }


def generate_terrain_fields(
    *,
    height: int,
    width: int,
    terrain_seed: int,
    config: TerrainConfig,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    """Return (potential, drag, grad_y, grad_x, generation_info).

    Traversability-gated attempts from deterministic attempt streams.
    Same terrain_seed + config ⇒ same accepted attempt and fields.
    """
    h, w = int(height), int(width)
    cfg = config
    mode = str(cfg.mode or "FLAT").upper()
    gates = cfg.traversability if isinstance(cfg.traversability, TraversabilityGates) else TraversabilityGates()

    if not cfg.enabled or mode == "FLAT":
        pot, drag, gy, gx = generate_terrain_fields_raw(
            height=h, width=w, attempt_seed=int(terrain_seed), config=cfg
        )
        audit = audit_physical_traversability(pot, gy, gx, gates)
        info = {
            "generation_attempt": 0,
            "accepted": True,
            "fallback": False,
            "audit": audit,
            "attempt_seed": int(terrain_seed),
        }
        return pot, drag, gy, gx, info

    max_attempts = max(1, int(gates.max_generation_attempts))
    best: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict[str, Any]] | None = None
    best_score = -1.0

    for attempt in range(max_attempts):
        aseed = attempt_stream_seed(int(terrain_seed), attempt)
        pot, drag, gy, gx = generate_terrain_fields_raw(
            height=h, width=w, attempt_seed=aseed, config=cfg
        )
        audit = audit_physical_traversability(pot, gy, gx, gates)
        score = (
            float(audit["largest_component_frac"])
            + 0.5 * float(audit["feasible_transition_frac"])
            - float(audit["extreme_gradient_frac"])
        )
        info = {
            "generation_attempt": int(attempt),
            "accepted": bool(audit["passed"]),
            "fallback": False,
            "audit": audit,
            "attempt_seed": int(aseed),
        }
        if audit["passed"]:
            return pot, drag, gy, gx, info
        if score > best_score:
            best_score = score
            best = (pot, drag, gy, gx, info)

    assert best is not None
    soft_cfg = TerrainConfig.from_dict(cfg.to_dict())
    soft_cfg.discontinuity_rate = float(cfg.discontinuity_rate) * 0.25
    soft_cfg.discontinuity_amplitude = float(cfg.discontinuity_amplitude) * 0.4
    soft_cfg.potential_amplitude = float(cfg.potential_amplitude) * 0.75
    soft_cfg.max_gradient = float(cfg.max_gradient) * 0.85
    aseed = attempt_stream_seed(int(terrain_seed), max_attempts)
    pot, drag, gy, gx = generate_terrain_fields_raw(
        height=h, width=w, attempt_seed=aseed, config=soft_cfg
    )
    audit = audit_physical_traversability(pot, gy, gx, gates)
    info = {
        "generation_attempt": int(max_attempts),
        "accepted": bool(audit["passed"]),
        "fallback": True,
        "audit": audit,
        "attempt_seed": int(aseed),
        "fallback_note": "softened geography after max attempts",
    }
    return pot, drag, gy, gx, info


def build_terrain_metadata(
    *,
    experiment_seed: int,
    config: TerrainConfig,
    potential: np.ndarray | None,
    drag: np.ndarray | None,
    height: int,
    width: int,
    generation_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved, source = resolve_terrain_seed(experiment_seed, config)
    gen = generation_info or {}
    audit = gen.get("audit") or {}
    return {
        "experiment_seed": int(experiment_seed),
        "terrain_seed": int(resolved),
        "terrain_seed_source": source,
        "generator_version": TERRAIN_GENERATOR_VERSION,
        "generation_attempt": gen.get("generation_attempt", 0),
        "generation_accepted": gen.get("accepted", True),
        "generation_fallback": bool(gen.get("fallback", False)),
        "attempt_seed": gen.get("attempt_seed"),
        "config": config.to_dict(),
        "checksum": terrain_field_checksum(potential, drag),
        "shape": [int(height), int(width)],
        "static": True,
        "observer_only": True,
        "traversability_audit": {
            "feasible_transition_frac": audit.get("feasible_transition_frac"),
            "largest_component_frac": audit.get("largest_component_frac"),
            "largest_component_size": audit.get("largest_component_size"),
            "n_components": audit.get("n_components"),
            "n_isolated_small_components": audit.get("n_isolated_small_components"),
            "extreme_gradient_frac": audit.get("extreme_gradient_frac"),
            "gradient_mag_mean": audit.get("gradient_mag_mean"),
            "gradient_mag_p90": audit.get("gradient_mag_p90"),
            "neighbor_delta_phi_mean": audit.get("neighbor_delta_phi_mean"),
            "passed": audit.get("passed"),
        },
        "note": (
            "Terrain generated once at world creation from terrain_seed stream "
            "with traversability-gated attempts. Independent of climate/cognition/agent RNG. "
            "Not agent observation."
        ),
    }


def install_terrain_on_planet(
    planet: Any,
    *,
    experiment_seed: int,
    config: TerrainConfig,
) -> dict[str, Any]:
    """Attach generated terrain grids onto PlanetState (static for the run).

    Returns terrain metadata (also stored on planet.terrain_meta).
    """
    if not config.enabled:
        planet.terrain_potential = None
        planet.terrain_drag = None
        planet.terrain_grad_y = None
        planet.terrain_grad_x = None
        meta = build_terrain_metadata(
            experiment_seed=experiment_seed,
            config=config,
            potential=None,
            drag=None,
            height=int(planet.T.shape[0]),
            width=int(planet.T.shape[1]),
        )
        meta["enabled"] = False
        planet.terrain_meta = meta
        return meta

    h, w = int(planet.T.shape[0]), int(planet.T.shape[1])
    resolved, _src = resolve_terrain_seed(experiment_seed, config)
    pot, drag, gy, gx, gen_info = generate_terrain_fields(
        height=h, width=w, terrain_seed=resolved, config=config
    )
    planet.terrain_potential = pot
    planet.terrain_drag = drag
    planet.terrain_grad_y = gy
    planet.terrain_grad_x = gx
    meta = build_terrain_metadata(
        experiment_seed=experiment_seed,
        config=config,
        potential=pot,
        drag=drag,
        height=h,
        width=w,
        generation_info=gen_info,
    )
    meta["enabled"] = True
    planet.terrain_meta = meta
    return meta


def set_uniform_terrain(
    planet: Any,
    *,
    potential: float = 0.0,
    drag: float = 0.0,
    grad_x: float = 0.0,
    grad_y: float = 0.0,
    experiment_seed: int = 0,
    config: TerrainConfig | None = None,
) -> None:
    """Experiment helper: constant fields (e.g. FLAT / UPHILL controls)."""
    h, w = int(planet.T.shape[0]), int(planet.T.shape[1])
    pot = np.full((h, w), float(potential), dtype=np.float64)
    dr = np.full((h, w), max(0.0, float(drag)), dtype=np.float64)
    planet.terrain_potential = pot
    planet.terrain_drag = dr
    planet.terrain_grad_x = np.full((h, w), float(grad_x), dtype=np.float64)
    planet.terrain_grad_y = np.full((h, w), float(grad_y), dtype=np.float64)
    cfg = config or TerrainConfig(enabled=True, mode="FLAT", drag_base=float(drag))
    planet.terrain_meta = build_terrain_metadata(
        experiment_seed=experiment_seed,
        config=cfg,
        potential=pot,
        drag=dr,
        height=h,
        width=w,
    )
    planet.terrain_meta["synthetic"] = "uniform"


def set_linear_potential_ramp(
    planet: Any,
    *,
    axis: str = "x",
    amplitude: float = 1.0,
    drag: float = 0.0,
    experiment_seed: int = 0,
    config: TerrainConfig | None = None,
) -> None:
    """Linear potential ramp → constant gradient (uphill/downhill controls)."""
    h, w = int(planet.T.shape[0]), int(planet.T.shape[1])
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    if axis.lower() == "y":
        pot = amplitude * (yy / max(1.0, h - 1.0))
        gy = np.full((h, w), amplitude / max(1.0, h - 1.0), dtype=np.float64)
        gx = np.zeros((h, w), dtype=np.float64)
    else:
        pot = amplitude * (xx / max(1.0, w - 1.0))
        gx = np.full((h, w), amplitude / max(1.0, w - 1.0), dtype=np.float64)
        gy = np.zeros((h, w), dtype=np.float64)
    dr = np.full((h, w), max(0.0, float(drag)), dtype=np.float64)
    planet.terrain_potential = pot
    planet.terrain_drag = dr
    planet.terrain_grad_x = gx
    planet.terrain_grad_y = gy
    cfg = config or TerrainConfig(enabled=True, mode="FLAT", drag_base=float(drag))
    planet.terrain_meta = build_terrain_metadata(
        experiment_seed=experiment_seed,
        config=cfg,
        potential=pot,
        drag=dr,
        height=h,
        width=w,
    )
    planet.terrain_meta["synthetic"] = f"linear_ramp_{axis}"


def set_profile_terrain(
    planet: Any,
    potential_row: np.ndarray,
    *,
    drag: float | np.ndarray = 0.0,
    experiment_seed: int = 0,
    config: TerrainConfig | None = None,
    label: str = "profile",
    max_gradient: float = 2.0,
) -> None:
    """1D potential profile extruded in y (controlled DESCENT / DROP tests)."""
    h, w = int(planet.T.shape[0]), int(planet.T.shape[1])
    row = np.asarray(potential_row, dtype=np.float64).reshape(-1)
    if row.size != w:
        xp = np.linspace(0, 1, row.size)
        xq = np.linspace(0, 1, w)
        row = np.interp(xq, xp, row)
    pot = np.repeat(row[None, :], h, axis=0)
    if np.ndim(drag) == 0:
        dr = np.full((h, w), max(0.0, float(drag)), dtype=np.float64)
    else:
        drow = np.asarray(drag, dtype=np.float64).reshape(-1)
        if drow.size != w:
            xp = np.linspace(0, 1, drow.size)
            xq = np.linspace(0, 1, w)
            drow = np.interp(xq, xp, drow)
        dr = np.repeat(np.maximum(drow, 0.0)[None, :], h, axis=0)
    pot, gy, gx = _clamp_gradient(pot, float(max_gradient))
    planet.terrain_potential = pot
    planet.terrain_drag = dr
    planet.terrain_grad_x = gx
    planet.terrain_grad_y = gy
    cfg = config or TerrainConfig(enabled=True, mode="FLAT", drag_base=0.0, max_gradient=float(max_gradient))
    planet.terrain_meta = build_terrain_metadata(
        experiment_seed=experiment_seed,
        config=cfg,
        potential=pot,
        drag=dr,
        height=h,
        width=w,
        generation_info={"generation_attempt": 0, "accepted": True, "fallback": False, "audit": {}},
    )
    planet.terrain_meta["synthetic"] = label


def sample_terrain_force(
    planet: Any,
    cells: list[tuple[int, int]],
    *,
    terrain_cfg: TerrainConfig,
    body_vx: float,
    body_vy: float,
    locomotor_active: bool,
) -> dict[str, Any]:
    """Mean site terrain force + extra drag. Never credits work reservoir."""
    empty = {
        "fx": 0.0,
        "fy": 0.0,
        "extra_drag": 0.0,
        "mean_drag": 0.0,
        "mean_potential": 0.0,
        "mean_grad": [0.0, 0.0],
        "potential_work_proxy": 0.0,
        "drag_dissipation_proxy": 0.0,
        "enabled": False,
    }
    if not terrain_cfg.enabled:
        return empty
    pot = getattr(planet, "terrain_potential", None)
    drag = getattr(planet, "terrain_drag", None)
    gx = getattr(planet, "terrain_grad_x", None)
    gy = getattr(planet, "terrain_grad_y", None)
    if pot is None or drag is None or gx is None or gy is None:
        return empty
    n = max(1, len(cells))
    mean_d = 0.0
    mean_p = 0.0
    mean_gx = 0.0
    mean_gy = 0.0
    for iy, ix in cells:
        mean_d += float(drag[iy, ix])
        mean_p += float(pot[iy, ix])
        mean_gx += float(gx[iy, ix])
        mean_gy += float(gy[iy, ix])
    mean_d /= n
    mean_p /= n
    mean_gx /= n
    mean_gy /= n
    max_g = max(1e-9, float(terrain_cfg.max_gradient))
    mag = float(np.hypot(mean_gx, mean_gy))
    if mag > max_g:
        s = max_g / mag
        mean_gx *= s
        mean_gy *= s
    kappa = float(terrain_cfg.force_scale)
    speed = float(np.hypot(body_vx, body_vy))
    kinetic_wait = False
    if not locomotor_active:
        thr = float(getattr(terrain_cfg, "kinetic_speed_threshold", 0.025) or 0.025)
        if speed >= thr:
            # Accumulated kinetic state — full potential force (ordinary inertia).
            kinetic_wait = True
        else:
            kappa *= float(terrain_cfg.wait_force_scale)
    fx = -kappa * mean_gx
    fy = -kappa * mean_gy
    extra_drag = max(0.0, float(terrain_cfg.drag_coupling) * max(0.0, mean_d))
    pot_work = fx * float(body_vx) + fy * float(body_vy)
    drag_diss = extra_drag * (float(body_vx) ** 2 + float(body_vy) ** 2)
    return {
        "fx": fx,
        "fy": fy,
        "extra_drag": extra_drag,
        "mean_drag": mean_d,
        "mean_potential": mean_p,
        "mean_grad": [mean_gx, mean_gy],
        "potential_work_proxy": pot_work,
        "drag_dissipation_proxy": drag_diss,
        "enabled": True,
        "kappa": kappa,
        "locomotor_active": bool(locomotor_active),
        "kinetic_wait": bool(kinetic_wait),
        "speed": speed,
        "accel_proxy": float(np.hypot(fx, fy)),
    }
