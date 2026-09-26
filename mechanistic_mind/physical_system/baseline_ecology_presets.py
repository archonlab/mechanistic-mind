"""Candidate Tiktaalik baseline ecology presets (calibration apparatus).

Observer / experiment configs only. Do not encode food/goal/seek into cognition.
These presets are opt-in; they do not silently replace CURRENT factory defaults
until a calibration report recommends promotion.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

import numpy as np

from mechanistic_mind.physical_system.complementary_resources import ensure_field, place_source_AB
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig
from mechanistic_mind.planet.climate_ecology import ClimateEcologyConfig
from mechanistic_mind.planet.state import PlanetState

# Named candidates for habitability calibration (also registered in ecology_presets)
ECOLOGY_A_STATIC_PATCHES = "BASELINE_A_STATIC_PATCHES"
ECOLOGY_B_MIGRATING = "BASELINE_B_MIGRATING_RESOURCES"
ECOLOGY_C_CHANGING = "BASELINE_C_CHANGING_LANDSCAPE"
ECOLOGY_CLIMATE_DEFAULT = "BASELINE_CLIMATE_DEFAULT"

KNOWN_BASELINE_ECOLOGIES = (
    ECOLOGY_A_STATIC_PATCHES,
    ECOLOGY_B_MIGRATING,
    ECOLOGY_C_CHANGING,
    ECOLOGY_CLIMATE_DEFAULT,
)


def normalize_baseline_ecology(name: str | None) -> str:
    if name is None or str(name).strip() == "":
        return ECOLOGY_CLIMATE_DEFAULT
    key = str(name).strip().upper().replace("-", "_").replace(" ", "_")
    aliases = {
        "A": ECOLOGY_A_STATIC_PATCHES,
        "STATIC": ECOLOGY_A_STATIC_PATCHES,
        "STATIC_PATCHES": ECOLOGY_A_STATIC_PATCHES,
        ECOLOGY_A_STATIC_PATCHES: ECOLOGY_A_STATIC_PATCHES,
        "B": ECOLOGY_B_MIGRATING,
        "MIGRATING": ECOLOGY_B_MIGRATING,
        ECOLOGY_B_MIGRATING: ECOLOGY_B_MIGRATING,
        "C": ECOLOGY_C_CHANGING,
        "CHANGING": ECOLOGY_C_CHANGING,
        ECOLOGY_C_CHANGING: ECOLOGY_C_CHANGING,
        "CLIMATE": ECOLOGY_CLIMATE_DEFAULT,
        "CLIMATE_DEFAULT": ECOLOGY_CLIMATE_DEFAULT,
        ECOLOGY_CLIMATE_DEFAULT: ECOLOGY_CLIMATE_DEFAULT,
    }
    if key not in aliases:
        raise ValueError(f"unknown baseline ecology {name!r}; known={list(KNOWN_BASELINE_ECOLOGIES)}")
    return aliases[key]


def _base_config(*, flow_soft: bool = False) -> PhysicalSystemConfig:
    cfg = PhysicalSystemConfig()
    # Calibration apparatus: no cognition unless caller enables it.
    cfg.cognition.cognition_enabled = False
    cfg.endogenous_motor.mode = "OFF"
    # Keep trickle explicitly configurable; default OFF for candidates.
    cfg.deformation_work.passive_reservoir_trickle = 0.0
    if flow_soft:
        cfg.planet.flow_gain = 0.12
        cfg.planet.flow_max = 0.14
        cfg.body.flow_coupling = 0.08
    return cfg


def make_baseline_ecology_config(
    name: str | None = ECOLOGY_CLIMATE_DEFAULT,
    *,
    trickle: float = 0.0,
    base: PhysicalSystemConfig | None = None,
) -> PhysicalSystemConfig:
    """Build an opt-in baseline ecology config. Does not mutate CURRENT factory."""
    key = normalize_baseline_ecology(name)
    cfg = deepcopy(base) if base is not None else _base_config()
    cfg.deformation_work.passive_reservoir_trickle = float(trickle)
    cfg.baseline_ecology = key  # type: ignore[attr-defined]

    if key == ECOLOGY_A_STATIC_PATCHES:
        # Negligible directional flow; climate resources OFF; patches seeded post-init.
        cfg.planet.flow_enabled = True
        cfg.planet.flow_gain = 0.04
        cfg.planet.flow_max = 0.05
        cfg.planet.F_fast_amp = 0.02
        cfg.planet.F_slow_amp = 0.02
        cfg.planet.F_irregular_amp = 0.0
        cfg.body.flow_coupling = 0.03
        cfg.planet.climate_ecology = ClimateEcologyConfig(
            enabled=False,
            resources_enabled=False,
            resource_ecology_A_enabled=False,
            resource_ecology_B_enabled=False,
        )
        cfg._baseline_seed_patches = True  # type: ignore[attr-defined]
        cfg._baseline_patch_spec = {  # type: ignore[attr-defined]
            "n_patches": 6,
            "A": 1.8,
            "B": 1.4,
            "radius": 2,
            "replenish_period": 36,
            "replenish_frac": 0.40,
        }
    elif key == ECOLOGY_B_MIGRATING:
        # Climate ON with independent resource phase → patches migrate on schedule.
        cfg.planet.flow_gain = 0.10
        cfg.planet.flow_max = 0.12
        cfg.body.flow_coupling = 0.07
        cfg.planet.climate_ecology = ClimateEcologyConfig(
            enabled=True,
            resources_enabled=True,
            resource_ecology_A_enabled=True,
            resource_ecology_B_enabled=True,
            season_period=96,
            cycle_mode="periodic",
            resource_suitability_source="independent_phase",
            resource_phase_mode="independent",
            resource_phase_offset=0.27,
            resource_diffuse=0.018,
            RA_productivity=0.036,
            RB_productivity=0.032,
            RA_decay=0.020,
            RB_decay=0.030,
            resource_seed_frac=0.07,
        )
    elif key == ECOLOGY_C_CHANGING:
        # Aperiodic climate → profitable regions shift without teleportation.
        cfg.planet.flow_gain = 0.12
        cfg.planet.flow_max = 0.14
        cfg.body.flow_coupling = 0.08
        cfg.planet.climate_ecology = ClimateEcologyConfig(
            enabled=True,
            resources_enabled=True,
            resource_ecology_A_enabled=True,
            resource_ecology_B_enabled=True,
            season_period=72,
            cycle_mode="aperiodic",
            aperiodic_jitter=0.40,
            resource_suitability_source="local_T",
            resource_phase_mode="coupled",
            resource_diffuse=0.028,
            RA_productivity=0.052,
            RB_productivity=0.046,
            RA_decay=0.022,
            RB_decay=0.032,
            resource_seed_frac=0.09,
        )
    else:  # ECOLOGY_CLIMATE_DEFAULT
        # Stock experimental climate planet with softened flow (reduce flow→food confound).
        # PASSIVE_TRANSPORT_01: force_scale 0.15 (promoted with make_ecology_config baseline).
        cfg.planet.flow_gain = 0.14
        cfg.planet.flow_max = 0.16
        cfg.body.flow_coupling = 0.09
        cfg.body_orientation.force_scale = 0.15
        cfg.planet.climate_ecology = ClimateEcologyConfig(
            enabled=True,
            resources_enabled=True,
            resource_ecology_A_enabled=True,
            resource_ecology_B_enabled=True,
        )
    return cfg


def seed_static_patches(world: PlanetState, *, seed: int, spec: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Place separated co-located A+B patches. Experiment setup only."""
    spec = spec or {
        "n_patches": 5,
        "A": 1.6,
        "B": 1.2,
        "radius": 1,
    }
    h, w = world.T.shape
    ensure_field(world, "R_A")
    ensure_field(world, "R_B")
    world.R_A[:] = 0.0
    world.R_B[:] = 0.0
    rng = np.random.default_rng(int(seed) + 44021)
    placed: list[dict[str, Any]] = []
    n = int(spec.get("n_patches", 5))
    rad = int(spec.get("radius", 1))
    A = float(spec.get("A", 1.6))
    B = float(spec.get("B", 1.2))
    # Deterministic lattice with jitter — separated patches
    cols = max(2, int(np.ceil(np.sqrt(n))))
    rows = max(1, int(np.ceil(n / cols)))
    idx = 0
    for ry in range(rows):
        for cx in range(cols):
            if idx >= n:
                break
            cy = int((ry + 0.5) * h / rows) + int(rng.integers(-1, 2))
            cx_i = int((cx + 0.5) * w / cols) + int(rng.integers(-1, 2))
            cy %= h
            cx_i %= w
            for dy in range(-rad, rad + 1):
                for dx in range(-rad, rad + 1):
                    if dy * dy + dx * dx > rad * rad:
                        continue
                    iy = (cy + dy) % h
                    ix = (cx_i + dx) % w
                    place_source_AB(world, iy, ix, A=A, B=B)
            placed.append({"iy": cy, "ix": cx_i, "A": A, "B": B, "radius": rad})
            idx += 1
    return placed


def maybe_replenish_static_patches(
    world: PlanetState,
    *,
    tick: int,
    seed: int,
    spec: dict[str, Any],
    centers: list[dict[str, Any]],
) -> None:
    """Slow local replenishment of static patches (ordinary field write)."""
    period = max(1, int(spec.get("replenish_period", 40)))
    if int(tick) % period != 0 or int(tick) == 0:
        return
    frac = float(spec.get("replenish_frac", 0.35))
    A = float(spec.get("A", 1.6)) * frac
    B = float(spec.get("B", 1.2)) * frac
    rad = int(spec.get("radius", 1))
    h, w = world.T.shape
    for c in centers:
        cy, cx = int(c["iy"]), int(c["ix"])
        for dy in range(-rad, rad + 1):
            for dx in range(-rad, rad + 1):
                if dy * dy + dx * dx > rad * rad:
                    continue
                iy = (cy + dy) % h
                ix = (cx + dx) % w
                world.R_A[iy, ix] = min(float(spec.get("A", 1.6)), float(world.R_A[iy, ix]) + A)
                world.R_B[iy, ix] = min(float(spec.get("B", 1.2)), float(world.R_B[iy, ix]) + B)


def make_current_uninhabitable_reference(*, trickle: float | None = None) -> PhysicalSystemConfig:
    """CURRENT_LEGACY path (climate OFF, empty env R_A/R_B) for controls / ablation."""
    from mechanistic_mind.physical_system.ecology_presets import (
        ECOLOGY_CURRENT_LEGACY,
        make_ecology_config,
    )

    cfg = make_ecology_config(ECOLOGY_CURRENT_LEGACY, trickle=trickle)
    cfg.cognition.cognition_enabled = False
    cfg.endogenous_motor.mode = "OFF"
    return cfg


def ecology_summary(cfg: PhysicalSystemConfig) -> dict[str, Any]:
    ce = cfg.planet.climate_ecology
    return {
        "baseline_ecology": getattr(cfg, "baseline_ecology", None),
        "ecology_preset": getattr(cfg, "ecology_preset", None),
        "climate_enabled": bool(ce.enabled),
        "resources_enabled": bool(getattr(ce, "resources_enabled", False)),
        "passive_reservoir_trickle": float(cfg.deformation_work.passive_reservoir_trickle),
        "flow_gain": float(cfg.planet.flow_gain),
        "flow_coupling": float(cfg.body.flow_coupling),
        "complementary_enabled": bool(cfg.complementary_resources.enabled),
        "conversion_enabled": bool(cfg.complementary_resources.conversion_enabled),
    }
