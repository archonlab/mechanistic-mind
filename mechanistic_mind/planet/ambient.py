"""Static spatially correlated ambient horizontal force fields.

Physical vector fields (Fx, Fy) only — not semantic WIND/CURRENT/ROUTE.
Independent RNG namespace from terrain / resources / cognition.
Default OFF. Never credits mechanical_work_reservoir.
Never enters agent cognition as ambient GT.
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from mechanistic_mind.planet.topology import laplacian


AMBIENT_GENERATOR_VERSION = "ambient_v1"


@dataclass
class AmbientConfig:
    """Weak static horizontal environmental force. Default OFF."""

    enabled: bool = False
    # Peak force amplitude (world units / tick² · mass-scaled later in integrator).
    amplitude: float = 0.018
    correlation_scale: float = 8.0
    large_scale_weight: float = 0.65
    medium_scale_weight: float = 0.35
    # Near-rest WAIT attenuation (kinetic WAIT keeps full force).
    wait_force_scale: float = 0.15
    kinetic_speed_threshold: float = 0.025
    # Absolute bound on |F| components after generation.
    max_component: float = 0.05
    ambient_seed: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "AmbientConfig":
        if not data:
            return cls()
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})


def deterministic_ambient_seed(experiment_seed: int, namespace: str = "ambient_horizontal") -> int:
    payload = f"{int(experiment_seed)}\0{namespace}\0{AMBIENT_GENERATOR_VERSION}".encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    return int.from_bytes(digest[:8], "big") & 0x7FFFFFFF


def resolve_ambient_seed(experiment_seed: int, config: AmbientConfig) -> tuple[int, str]:
    if config.ambient_seed is not None:
        return int(config.ambient_seed), "override"
    return deterministic_ambient_seed(int(experiment_seed)), "namespace"


def ambient_field_checksum(fx: np.ndarray | None, fy: np.ndarray | None) -> str:
    h = hashlib.sha256()
    h.update(AMBIENT_GENERATOR_VERSION.encode("utf-8"))
    if fx is None or fy is None:
        h.update(b"absent")
        return h.hexdigest()[:16]
    h.update(np.ascontiguousarray(fx, dtype=np.float64).tobytes())
    h.update(np.ascontiguousarray(fy, dtype=np.float64).tobytes())
    return h.hexdigest()[:16]


def _smooth(z: np.ndarray, passes: int) -> np.ndarray:
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


def _octave(rng: np.random.Generator, h: int, w: int, *, coarse_div: int, smooth_passes: int) -> np.ndarray:
    ch = max(2, h // max(1, int(coarse_div)))
    cw = max(2, w // max(1, int(coarse_div)))
    coarse = rng.standard_normal((ch, cw))
    up = _bilinear_upsample(coarse, h, w)
    up = _smooth(up, max(1, int(smooth_passes)))
    return (up - up.mean()) / (up.std() + 1e-8)


def generate_ambient_fields(
    *,
    height: int,
    width: int,
    ambient_seed: int,
    config: AmbientConfig,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (Fx, Fy) static force grids. Correlated, bounded, not cell-noise."""
    h, w = int(height), int(width)
    if not config.enabled:
        return np.zeros((h, w), dtype=np.float64), np.zeros((h, w), dtype=np.float64)

    root = np.random.SeedSequence(int(ambient_seed) & 0xFFFFFFFF)
    fx_ss, fy_ss = root.spawn(2)
    fx_rng = np.random.default_rng(fx_ss)
    fy_rng = np.random.default_rng(fy_ss)
    scale = max(2.0, float(config.correlation_scale))
    wl = max(0.0, float(config.large_scale_weight))
    wm = max(0.0, float(config.medium_scale_weight))
    s = wl + wm
    if s < 1e-12:
        wl, wm, s = 1.0, 0.0, 1.0

    def component(rng: np.random.Generator) -> np.ndarray:
        large = _octave(rng, h, w, coarse_div=max(4, int(round(scale * 1.3))), smooth_passes=max(5, int(scale)))
        medium = _octave(rng, h, w, coarse_div=max(3, int(round(scale * 0.5))), smooth_passes=max(2, int(scale * 0.4)))
        mix = (wl * large + wm * medium) / s
        return (mix - mix.mean()) / (mix.std() + 1e-8)

    fx = float(config.amplitude) * component(fx_rng)
    fy = float(config.amplitude) * component(fy_rng)
    bound = max(1e-9, float(config.max_component))
    fx = np.clip(fx, -bound, bound)
    fy = np.clip(fy, -bound, bound)
    return fx, fy


def build_ambient_metadata(
    *,
    experiment_seed: int,
    config: AmbientConfig,
    fx: np.ndarray | None,
    fy: np.ndarray | None,
    height: int,
    width: int,
) -> dict[str, Any]:
    resolved, source = resolve_ambient_seed(experiment_seed, config)
    stats: dict[str, Any] = {}
    if fx is not None and fy is not None:
        mag = np.hypot(fx, fy)
        stats = {
            "fx_min": float(np.min(fx)),
            "fx_max": float(np.max(fx)),
            "fy_min": float(np.min(fy)),
            "fy_max": float(np.max(fy)),
            "magnitude_min": float(np.min(mag)),
            "magnitude_max": float(np.max(mag)),
            "magnitude_mean": float(np.mean(mag)),
        }
    return {
        "experiment_seed": int(experiment_seed),
        "ambient_seed": int(resolved),
        "ambient_seed_source": source,
        "generator_version": AMBIENT_GENERATOR_VERSION,
        "config": config.to_dict(),
        "checksum": ambient_field_checksum(fx, fy),
        "shape": [int(height), int(width)],
        "static": True,
        "observer_only": True,
        "enabled": bool(config.enabled),
        "note": (
            "Static ambient horizontal force from ambient_horizontal namespace. "
            "Not WIND/CURRENT labels. Not agent observation."
        ),
        **stats,
    }


def install_ambient_on_planet(
    planet: Any,
    *,
    experiment_seed: int,
    config: AmbientConfig,
) -> dict[str, Any]:
    h, w = int(planet.T.shape[0]), int(planet.T.shape[1])
    if not config.enabled:
        planet.ambient_fx = None
        planet.ambient_fy = None
        meta = build_ambient_metadata(
            experiment_seed=experiment_seed, config=config, fx=None, fy=None, height=h, width=w
        )
        meta["enabled"] = False
        planet.ambient_meta = meta
        return meta
    resolved, _ = resolve_ambient_seed(experiment_seed, config)
    fx, fy = generate_ambient_fields(height=h, width=w, ambient_seed=resolved, config=config)
    planet.ambient_fx = fx
    planet.ambient_fy = fy
    meta = build_ambient_metadata(
        experiment_seed=experiment_seed, config=config, fx=fx, fy=fy, height=h, width=w
    )
    meta["enabled"] = True
    planet.ambient_meta = meta
    return meta


def set_uniform_ambient(
    planet: Any,
    *,
    fx: float = 0.0,
    fy: float = 0.0,
    experiment_seed: int = 0,
    config: AmbientConfig | None = None,
) -> None:
    """Experiment helper: constant ambient force (ZERO / CROSS / ALIGNED controls)."""
    h, w = int(planet.T.shape[0]), int(planet.T.shape[1])
    afx = np.full((h, w), float(fx), dtype=np.float64)
    afy = np.full((h, w), float(fy), dtype=np.float64)
    planet.ambient_fx = afx
    planet.ambient_fy = afy
    cfg = config or AmbientConfig(enabled=True, amplitude=max(abs(fx), abs(fy), 1e-9))
    planet.ambient_meta = build_ambient_metadata(
        experiment_seed=experiment_seed, config=cfg, fx=afx, fy=afy, height=h, width=w
    )
    planet.ambient_meta["synthetic"] = "uniform"
    planet.ambient_meta["enabled"] = True


def sample_ambient_force(
    planet: Any,
    cells: list[tuple[int, int]],
    *,
    ambient_cfg: AmbientConfig,
    body_vx: float,
    body_vy: float,
    locomotor_active: bool,
) -> dict[str, Any]:
    """Mean site ambient force. External only — never credits work reservoir."""
    empty = {
        "fx": 0.0,
        "fy": 0.0,
        "mean_fx": 0.0,
        "mean_fy": 0.0,
        "magnitude": 0.0,
        "enabled": False,
        "kinetic_wait": False,
        "scale": 0.0,
    }
    if not ambient_cfg.enabled:
        return empty
    afx = getattr(planet, "ambient_fx", None)
    afy = getattr(planet, "ambient_fy", None)
    if afx is None or afy is None:
        return empty
    n = max(1, len(cells))
    mean_fx = 0.0
    mean_fy = 0.0
    for iy, ix in cells:
        mean_fx += float(afx[iy, ix])
        mean_fy += float(afy[iy, ix])
    mean_fx /= n
    mean_fy /= n
    scale = 1.0
    speed = float(np.hypot(body_vx, body_vy))
    kinetic_wait = False
    if not locomotor_active:
        thr = float(getattr(ambient_cfg, "kinetic_speed_threshold", 0.025) or 0.025)
        if speed >= thr:
            kinetic_wait = True
        else:
            scale = float(ambient_cfg.wait_force_scale)
    fx = mean_fx * scale
    fy = mean_fy * scale
    return {
        "fx": fx,
        "fy": fy,
        "mean_fx": mean_fx,
        "mean_fy": mean_fy,
        "magnitude": float(np.hypot(fx, fy)),
        "enabled": True,
        "kinetic_wait": bool(kinetic_wait),
        "scale": scale,
        "speed": speed,
    }
