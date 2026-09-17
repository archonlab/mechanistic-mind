from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Action:
    """An explicit request to affect the environment."""

    kind: str
    parameters: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def wait(cls) -> "Action":
        """Canonical no-op action."""
        return cls(kind="WAIT")
