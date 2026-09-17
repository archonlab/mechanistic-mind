from dataclasses import dataclass, field

from .base import Mechanism


@dataclass
class MechanismRegistry:
    """Deterministic registry for installed mechanisms."""

    mechanisms: dict[str, Mechanism] = field(default_factory=dict)

    def register(self, mechanism: Mechanism) -> None:
        mechanism_id = mechanism.mechanism_id
        if not mechanism_id or mechanism_id == "UNASSIGNED":
            raise ValueError("Mechanism must define a stable mechanism_id")
        if mechanism_id in self.mechanisms:
            raise ValueError(f"Mechanism already registered: {mechanism_id}")
        self.mechanisms[mechanism_id] = mechanism

    def get(self, mechanism_id: str) -> Mechanism:
        return self.mechanisms[mechanism_id]

    def ordered(self) -> tuple[Mechanism, ...]:
        """Stable order independent of registration order."""
        return tuple(self.mechanisms[key] for key in sorted(self.mechanisms))
