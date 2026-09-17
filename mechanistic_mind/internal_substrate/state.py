"""Internal substrate state — continuous dynamical system, not N/L/R_L."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import numpy as np

from mechanistic_mind.internal_substrate.config import InternalSubstrateConfig, default_internal_substrate_config


@dataclass
class InternalSubstrateState:
    tick: int
    s: np.ndarray  # (dim,)
    drive_thermal: float = 0.0
    drive_surface: float = 0.0
    drive_core: float = 0.0
    drive_mech: float = 0.0
    core_exchanged: float = 0.0

    def copy(self) -> "InternalSubstrateState":
        return InternalSubstrateState(
            tick=self.tick, s=self.s.copy(),
            drive_thermal=self.drive_thermal, drive_surface=self.drive_surface,
            drive_core=self.drive_core, drive_mech=self.drive_mech,
            core_exchanged=self.core_exchanged,
        )

    def snapshot(self) -> dict[str, Any]:
        return {
            "tick": self.tick,
            "s": [float(v) for v in self.s],
            "s_norm": float(np.linalg.norm(self.s)),
            "drive_thermal": self.drive_thermal,
            "drive_surface": self.drive_surface,
            "drive_core": self.drive_core,
            "drive_mech": self.drive_mech,
            "core_exchanged": self.core_exchanged,
        }


def initialize_internal_substrate(
    config: InternalSubstrateConfig | None = None,
    *,
    s0: tuple[float, ...] | None = None,
) -> InternalSubstrateState:
    cfg = config or default_internal_substrate_config()
    if s0 is None:
        s = np.zeros(cfg.dim, dtype=np.float64)
    else:
        s = np.asarray(s0, dtype=np.float64)
        if s.shape != (cfg.dim,):
            raise ValueError(f"s0 shape {s.shape} != ({cfg.dim},)")
    return InternalSubstrateState(tick=0, s=s)
