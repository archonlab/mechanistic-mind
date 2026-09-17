"""Internal medium state — concentration field on BODY footprint sites."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import numpy as np

from mechanistic_mind.internal_medium.config import InternalMediumConfig, default_internal_medium_config


@dataclass
class InternalMediumState:
    tick: int
    c: np.ndarray  # (n_sites, n_species)

    def copy(self) -> "InternalMediumState":
        return InternalMediumState(tick=self.tick, c=self.c.copy())

    def snapshot(self) -> dict[str, Any]:
        return {
            "tick": self.tick,
            "c": self.c.astype(float).tolist(),
            "c_sum": float(self.c.sum()),
            "c_norm": float(np.linalg.norm(self.c)),
        }


def initialize_internal_medium(
    config: InternalMediumConfig | None = None,
    *,
    c0: float | None = None,
) -> InternalMediumState:
    cfg = config or default_internal_medium_config()
    fill = cfg.c0 if c0 is None else float(c0)
    c = np.full((cfg.n_sites, cfg.n_species), fill, dtype=np.float64)
    return InternalMediumState(tick=0, c=np.clip(c, 0.0, cfg.C_max))
