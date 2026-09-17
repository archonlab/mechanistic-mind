from dataclasses import dataclass, field

from .state import AgentState


@dataclass(slots=True)
class Agent:
    """Foundation-level agent container with no psychological assumptions."""

    agent_id: str
    state: AgentState = field(default_factory=AgentState)
