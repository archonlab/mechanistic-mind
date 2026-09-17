"""Canonical WORLD + BODY + INTERNAL physical runtime (+ optional cognition)."""

from .runtime import PhysicalSystemConfig, PhysicalSystemRuntime
from .observation import accessible_observation, audit_cognition_payload, observation_bundle
from .actions import available_actions, apply_physical_action, BRIDGE_MISSING, BRIDGE_ID
from .cognition import CognitionConfig
from .action_work import DiscreteActionWorkConfig
from .two_agent import TwoAgentRuntime

__all__ = [
    "PhysicalSystemConfig",
    "PhysicalSystemRuntime",
    "TwoAgentRuntime",
    "CognitionConfig",
    "DiscreteActionWorkConfig",
    "accessible_observation",
    "audit_cognition_payload",
    "observation_bundle",
    "available_actions",
    "apply_physical_action",
    "BRIDGE_MISSING",
    "BRIDGE_ID",
]
