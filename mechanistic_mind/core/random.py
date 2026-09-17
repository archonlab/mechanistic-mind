import random
from dataclasses import dataclass, field


@dataclass(slots=True)
class DeterministicRandom:
    """Single controlled source of pseudo-randomness for a run."""

    seed: int
    _rng: random.Random = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    def random(self) -> float:
        return self._rng.random()

    def randint(self, a: int, b: int) -> int:
        return self._rng.randint(a, b)

    def choice(self, sequence):
        return self._rng.choice(sequence)

    def reset(self) -> None:
        self._rng.seed(self.seed)
