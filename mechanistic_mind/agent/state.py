from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class AgentState:
    """Explicit internal state owned by an agent.

    ``variables`` are generic agent-level state.
    ``mechanism_states`` are isolated namespaces keyed by mechanism_id.
    """

    variables: dict[str, Any] = field(default_factory=dict)
    mechanism_states: dict[str, dict[str, Any]] = field(default_factory=dict)
