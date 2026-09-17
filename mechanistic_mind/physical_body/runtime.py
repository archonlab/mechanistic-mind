"""Run frozen WORLD-1 with optional PhysicalBody coupling."""
from __future__ import annotations
from copy import deepcopy
from typing import Any
import numpy as np

from mechanistic_mind.planet.config import PlanetConfig, default_planet_config
from mechanistic_mind.planet.dynamics import step_planet
from mechanistic_mind.planet.runtime import snapshot_stats
from mechanistic_mind.planet.state import initialize_planet
from mechanistic_mind.physical_body.config import PhysicalBodyConfig, default_physical_body_config
from mechanistic_mind.physical_body.dynamics import step_physical_body
from mechanistic_mind.physical_body.state import initialize_physical_body


def run_world_with_body(
    *,
    seed: int = 17,
    horizon: int = 800,
    planet_config: PlanetConfig | None = None,
    body_config: PhysicalBodyConfig | None = None,
    snapshot_every: int = 20,
    with_body: bool = True,
) -> dict[str, Any]:
    pcfg = deepcopy(planet_config) if planet_config is not None else default_planet_config()
    # freeze WORLD-1 defaults for irregularity consistency in paired runs
    bcfg = deepcopy(body_config) if body_config is not None else default_physical_body_config()
    planet = initialize_planet(pcfg, seed=seed)
    body = initialize_physical_body(bcfg, width=pcfg.width, height=pcfg.height) if with_body else None

    series = []
    body_series = []
    series.append(snapshot_stats(planet, pcfg, seed))
    if body is not None:
        body_series.append(body.snapshot())

    for t in range(horizon):
        step_planet(planet, pcfg, seed=seed)
        if body is not None:
            step_physical_body(body, planet, bcfg)
        if (t + 1) % snapshot_every == 0 or t + 1 == horizon:
            series.append(snapshot_stats(planet, pcfg, seed))
            if body is not None:
                body_series.append(body.snapshot())

    out: dict[str, Any] = {
        "seed": seed,
        "horizon": horizon,
        "planet_config": pcfg.to_dict(),
        "body_config": bcfg.to_dict() if with_body else None,
        "with_body": with_body,
        "planet_series": series,
        "body_series": body_series,
        "planet": planet,
        "body": body,
    }
    return out
