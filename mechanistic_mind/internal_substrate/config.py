"""MM-TRANS-1 structural coupling — not receptors, not EHF ports, not adapters."""
from __future__ import annotations
from dataclasses import dataclass, asdict, field
from typing import Any


@dataclass
class InternalSubstrateConfig:
    """Separate internal continuum S. Driven by local BODY physics only."""
    dim: int = 4
    leak: float = 0.04
    self_couple: float = 0.08
    clip_abs: float = 2.0

    # physical channels from BODY (preregistered structural rates)
    thermal_rate_gain: float = 0.12      # BODY T modulates S reaction rates
    thermal_bias: float = 0.35           # baseline rate factor floor
    surface_chem_gain: float = 0.06      # surface B composition → chemical potential on S
    core_exchange: float = 0.02          # slow mass-like exchange B_core[i] <-> s[i] for i<3
    mech_mod_gain: float = 0.05          # |mech| modulates leak / mixing
    backreact_core: bool = True          # weak reciprocal on B_core when exchanging
    backreact_thermal: float = 0.01      # tiny heat from S activity → BODY T

    # research cuts
    thermal_enabled: bool = True
    surface_enabled: bool = True
    core_enabled: bool = True
    mech_enabled: bool = True
    substrate_enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def default_internal_substrate_config() -> InternalSubstrateConfig:
    return InternalSubstrateConfig()
