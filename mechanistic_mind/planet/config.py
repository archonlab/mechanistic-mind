"""MM-WORLD-1 configuration — outcome-blind physical parameters."""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Any

from mechanistic_mind.planet.climate_ecology import ClimateEcologyConfig


@dataclass
class PlanetConfig:
    width: int = 32
    height: int = 32

    # external forcing
    F_baseline: float = 0.08
    F_fast_amp: float = 0.35
    F_fast_period: int = 40
    F_fast_sigma: float = 6.0
    F_slow_amp: float = 0.25
    F_slow_period: int = 400
    F_irregular_amp: float = 0.05
    forcing_enabled: bool = True
    forcing_origin_x: float = 0.0
    forcing_origin_y: float = 0.0

    # thermal
    heat_gain: float = 0.045
    cool_rate: float = 0.035
    T_ref: float = 0.35
    kappa_base: float = 0.10
    T_min: float = 0.0
    T_max: float = 1.0

    # flow from thermal gradient
    flow_gain: float = 0.55
    flow_damp: float = 0.15
    flow_max: float = 0.45
    flow_enabled: bool = True

    # matter
    n_materials: int = 3
    diff_M0: float = 0.04
    diff_M1: float = 0.02
    advect_M0: float = 0.35
    diffusion_enabled: bool = True
    advection_enabled: bool = True

    # reaction M0+M1 -> M2 (+ heat), rate rises with T
    react_rate: float = 0.02
    react_heat: float = 0.02
    reaction_enabled: bool = True

    # soft phase-like: M2 -> M0 when cool; M0 -> M2 when hot (bounded)
    phase_rate: float = 0.01
    phase_T_hi: float = 0.62
    phase_T_lo: float = 0.38
    phase_enabled: bool = True

    # wave field
    wave_c2: float = 0.25
    wave_damp: float = 0.08
    wave_source_gain: float = 0.15
    wave_enabled: bool = True

    # substrate heterogeneity
    hetero_amp_capacity: float = 0.35
    hetero_amp_conductivity: float = 0.40

    # research cuts (defaults production)
    thermal_from_forcing: bool = True

    # OPEN-5: external material boundary default OFF.
    # Runtime ON state (mask/K/M_ext) lives on PlanetState.external_material_boundary.
    # Missing/legacy config => OFF. No canonical mask/K.
    external_material_boundary_enabled: bool = False

    # Experimental spatiotemporal climate / resource ecology. Default OFF.
    # Missing/legacy config => ClimateEcologyConfig() with enabled=False.
    climate_ecology: ClimateEcologyConfig = field(default_factory=ClimateEcologyConfig)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "PlanetConfig":
        payload = dict(data or {})
        fields = {k: v for k, v in payload.items() if k in cls.__dataclass_fields__}
        ce = fields.get("climate_ecology")
        if isinstance(ce, dict):
            fields["climate_ecology"] = ClimateEcologyConfig.from_dict(ce)
        elif ce is None:
            fields.pop("climate_ecology", None)
        return cls(**fields)


def default_planet_config() -> PlanetConfig:
    return PlanetConfig()
