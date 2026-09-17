"""Physically defined internal material medium — MM-SUBSTRATE-1."""
from mechanistic_mind.internal_medium.config import (
    InternalMediumConfig,
    default_internal_medium_config,
    FOOTPRINT,
    EDGES,
    adjacency,
)
from mechanistic_mind.internal_medium.state import InternalMediumState, initialize_internal_medium
from mechanistic_mind.internal_medium.flux import (
    MediumFluxRecord,
    compute_medium_fluxes,
    apply_medium_fluxes,
    step_internal_medium,
)
from mechanistic_mind.internal_medium.runtime import run_world_body_medium

__all__ = [
    "InternalMediumConfig",
    "InternalMediumState",
    "MediumFluxRecord",
    "default_internal_medium_config",
    "initialize_internal_medium",
    "compute_medium_fluxes",
    "apply_medium_fluxes",
    "step_internal_medium",
    "run_world_body_medium",
    "FOOTPRINT",
    "EDGES",
    "adjacency",
]
