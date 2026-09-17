"""Opt-in WORLD+BODY-2+InternalMedium orchestration. Defaults leave BODY-2 alone."""
from __future__ import annotations
from copy import deepcopy
from typing import Any

from mechanistic_mind.planet.config import PlanetConfig, default_planet_config
from mechanistic_mind.planet.dynamics import step_planet
from mechanistic_mind.planet.runtime import snapshot_stats
from mechanistic_mind.planet.state import initialize_planet
from mechanistic_mind.physical_body.config import PhysicalBodyConfig, default_physical_body2_config
from mechanistic_mind.physical_body.dynamics import step_physical_body
from mechanistic_mind.physical_body.state import initialize_physical_body
from mechanistic_mind.internal_medium.config import InternalMediumConfig, default_internal_medium_config
from mechanistic_mind.internal_medium.state import initialize_internal_medium
from mechanistic_mind.internal_medium.flux import step_internal_medium


def run_world_body_medium(
    *,
    seed: int = 17,
    horizon: int = 400,
    planet_config: PlanetConfig | None = None,
    body_config: PhysicalBodyConfig | None = None,
    medium_config: InternalMediumConfig | None = None,
    with_medium: bool = True,
    snapshot_every: int = 20,
) -> dict[str, Any]:
    pcfg = deepcopy(planet_config) if planet_config is not None else default_planet_config()
    bcfg = deepcopy(body_config) if body_config is not None else default_physical_body2_config()
    mcfg = deepcopy(medium_config) if medium_config is not None else default_internal_medium_config()

    planet = initialize_planet(pcfg, seed=seed)
    body = initialize_physical_body(bcfg, width=pcfg.width, height=pcfg.height)
    medium = initialize_internal_medium(mcfg) if with_medium else None

    planet_series = [snapshot_stats(planet, pcfg, seed)]
    body_series = [body.snapshot()]
    medium_series = [medium.snapshot()] if medium is not None else []
    residuals = []

    for t in range(horizon):
        step_planet(planet, pcfg, seed=seed)
        step_physical_body(body, planet, bcfg)
        if medium is not None:
            fr = step_internal_medium(medium, body, mcfg)
            residuals.append(fr.material_residual)
        if (t + 1) % snapshot_every == 0 or t + 1 == horizon:
            planet_series.append(snapshot_stats(planet, pcfg, seed))
            body_series.append(body.snapshot())
            if medium is not None:
                medium_series.append(medium.snapshot())

    return {
        "seed": seed,
        "horizon": horizon,
        "with_medium": with_medium,
        "planet_config": pcfg.to_dict(),
        "body_config": bcfg.to_dict(),
        "medium_config": mcfg.to_dict() if with_medium else None,
        "planet_series": planet_series,
        "body_series": body_series,
        "medium_series": medium_series,
        "material_residual_max": float(max(residuals)) if residuals else 0.0,
        "material_residual_mean": float(sum(residuals) / len(residuals)) if residuals else 0.0,
        "planet": planet,
        "body": body,
        "medium": medium,
    }
