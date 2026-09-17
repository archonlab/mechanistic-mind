"""WORLD + BODY-2 + internal substrate orchestration."""
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
from mechanistic_mind.internal_substrate.config import InternalSubstrateConfig, default_internal_substrate_config
from mechanistic_mind.internal_substrate.dynamics import step_internal_substrate
from mechanistic_mind.internal_substrate.state import initialize_internal_substrate


def run_world_body_substrate(
    *,
    seed: int = 17,
    horizon: int = 800,
    planet_config: PlanetConfig | None = None,
    body_config: PhysicalBodyConfig | None = None,
    substrate_config: InternalSubstrateConfig | None = None,
    snapshot_every: int = 20,
) -> dict[str, Any]:
    pcfg = deepcopy(planet_config) if planet_config is not None else default_planet_config()
    bcfg = deepcopy(body_config) if body_config is not None else default_physical_body2_config()
    scfg = deepcopy(substrate_config) if substrate_config is not None else default_internal_substrate_config()

    planet = initialize_planet(pcfg, seed=seed)
    body = initialize_physical_body(bcfg, width=pcfg.width, height=pcfg.height)
    sub = initialize_internal_substrate(scfg)

    planet_series = [snapshot_stats(planet, pcfg, seed)]
    body_series = [body.snapshot()]
    sub_series = [sub.snapshot()]

    for t in range(horizon):
        step_planet(planet, pcfg, seed=seed)
        step_physical_body(body, planet, bcfg)
        step_internal_substrate(sub, body, scfg)
        if (t + 1) % snapshot_every == 0 or t + 1 == horizon:
            planet_series.append(snapshot_stats(planet, pcfg, seed))
            body_series.append(body.snapshot())
            sub_series.append(sub.snapshot())

    return {
        "seed": seed,
        "horizon": horizon,
        "planet_config": pcfg.to_dict(),
        "body_config": bcfg.to_dict(),
        "substrate_config": scfg.to_dict(),
        "planet_series": planet_series,
        "body_series": body_series,
        "sub_series": sub_series,
        "planet": planet,
        "body": body,
        "substrate": sub,
    }
