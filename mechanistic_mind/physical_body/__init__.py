"""Physical body substrate — BODY-1 defaults; BODY-2 multi-cell + slow core."""
from mechanistic_mind.physical_body.config import (
    PhysicalBodyConfig,
    default_physical_body_config,
    default_physical_body2_config,
)
from mechanistic_mind.physical_body.state import PhysicalBodyState, initialize_physical_body
from mechanistic_mind.physical_body.dynamics import step_physical_body
from mechanistic_mind.physical_body.runtime import run_world_with_body

__all__ = [
    "PhysicalBodyConfig",
    "PhysicalBodyState",
    "default_physical_body_config",
    "default_physical_body2_config",
    "initialize_physical_body",
    "step_physical_body",
    "run_world_with_body",
]
