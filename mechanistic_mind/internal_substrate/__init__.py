"""Internal dynamical substrate — physically coupled from BODY, not psyche."""
from mechanistic_mind.internal_substrate.config import InternalSubstrateConfig, default_internal_substrate_config
from mechanistic_mind.internal_substrate.state import InternalSubstrateState, initialize_internal_substrate
from mechanistic_mind.internal_substrate.dynamics import step_internal_substrate
from mechanistic_mind.internal_substrate.runtime import run_world_body_substrate

__all__ = [
    "InternalSubstrateConfig",
    "InternalSubstrateState",
    "default_internal_substrate_config",
    "initialize_internal_substrate",
    "step_internal_substrate",
    "run_world_body_substrate",
]
