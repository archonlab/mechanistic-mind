from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Observation:
    """Information exposed to an agent, distinct from world truth."""

    data: dict[str, Any] = field(default_factory=dict)
