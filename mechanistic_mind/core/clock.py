from dataclasses import dataclass


@dataclass(slots=True)
class Clock:
    """Discrete simulation clock."""

    tick: int = 0

    def step(self) -> int:
        self.tick += 1
        return self.tick

    def reset(self) -> None:
        self.tick = 0
