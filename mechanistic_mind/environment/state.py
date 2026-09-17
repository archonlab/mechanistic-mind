from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class WorldState:
    """Explicit state of the environment."""

    variables: dict[str, Any] = field(default_factory=dict)
