"""PhysicalBodyState — bounded matter system, not an agent."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import numpy as np

from mechanistic_mind.physical_body.config import PhysicalBodyConfig, default_physical_body_config
from mechanistic_mind.planet.topology import wrap_coord


@dataclass
class PhysicalBodyState:
    tick: int
    x: float
    y: float
    vx: float
    vy: float
    T: float
    B: np.ndarray  # surface (3,)
    B_core: np.ndarray  # slow core (3,); unused if core disabled
    mech: float
    motor_ux: float = 0.0  # experimental endogenous motor (default unused when coupling OFF)
    motor_uy: float = 0.0
    B_site: np.ndarray | None = None  # experimental local material (n_sites, 3); unused when morphology OFF
    theta: float = 0.0  # experimental orientation (rad); unused when body_orientation OFF
    omega: float = 0.0  # experimental angular velocity (rad/tick)
    # Articulated head / neck DOF (unused when articulated_head OFF → remain 0).
    head_relative_angle: float = 0.0
    head_omega: float = 0.0
    neck_motor: float = 0.0  # last motor command [-1, 1]
    push_exertion: float = 0.0  # armed contact push this tick [0, 1]
    # Oscillatory signaling motor state (unused when oscillatory_signaling OFF).
    osc_freq_u: float = 0.5
    osc_amp_u: float = 0.5
    osc_emit_remaining: int = 0
    osc_emit_active: float = 0.0
    osc_frequency: float = 0.0  # last physical freq (WORLD GT cache)
    osc_amplitude: float = 0.0
    matter_in: float = 0.0
    matter_out: float = 0.0
    heat_from_world: float = 0.0
    heat_to_world: float = 0.0
    react_consumed: float = 0.0
    core_exchange_cum: float = 0.0
    deformation: np.ndarray | None = None
    mechanical_work_reservoir: float = 0.0
    deformation_env_force: np.ndarray | None = None
    R_site: np.ndarray | None = None
    R_A_site: np.ndarray | None = None
    R_B_site: np.ndarray | None = None

    def copy(self) -> "PhysicalBodyState":
        return PhysicalBodyState(
            tick=self.tick, x=self.x, y=self.y, vx=self.vx, vy=self.vy,
            T=self.T, B=self.B.copy(), B_core=self.B_core.copy(), mech=self.mech,
            motor_ux=self.motor_ux, motor_uy=self.motor_uy,
            B_site=None if self.B_site is None else self.B_site.copy(),
            theta=float(getattr(self, "theta", 0.0)), omega=float(getattr(self, "omega", 0.0)),
            head_relative_angle=float(getattr(self, "head_relative_angle", 0.0) or 0.0),
            head_omega=float(getattr(self, "head_omega", 0.0) or 0.0),
            neck_motor=float(getattr(self, "neck_motor", 0.0) or 0.0),
            push_exertion=float(getattr(self, "push_exertion", 0.0) or 0.0),
            osc_freq_u=float(getattr(self, "osc_freq_u", 0.5) or 0.5),
            osc_amp_u=float(getattr(self, "osc_amp_u", 0.5) or 0.5),
            osc_emit_remaining=int(getattr(self, "osc_emit_remaining", 0) or 0),
            osc_emit_active=float(getattr(self, "osc_emit_active", 0.0) or 0.0),
            osc_frequency=float(getattr(self, "osc_frequency", 0.0) or 0.0),
            osc_amplitude=float(getattr(self, "osc_amplitude", 0.0) or 0.0),
            matter_in=self.matter_in, matter_out=self.matter_out,
            heat_from_world=self.heat_from_world, heat_to_world=self.heat_to_world,
            react_consumed=self.react_consumed, core_exchange_cum=self.core_exchange_cum,
            deformation=None if getattr(self, "deformation", None) is None else np.asarray(self.deformation, dtype=np.float64).copy(),
            mechanical_work_reservoir=float(getattr(self, "mechanical_work_reservoir", 0.0) or 0.0),
            deformation_env_force=(
                None if getattr(self, "deformation_env_force", None) is None
                else np.asarray(self.deformation_env_force, dtype=np.float64).copy()
            ),
            R_site=None if getattr(self, "R_site", None) is None else np.asarray(self.R_site, dtype=np.float64).copy(),
            R_A_site=None if getattr(self, "R_A_site", None) is None else np.asarray(self.R_A_site, dtype=np.float64).copy(),
            R_B_site=None if getattr(self, "R_B_site", None) is None else np.asarray(self.R_B_site, dtype=np.float64).copy(),
        )

    def cell(self, width: int, height: int) -> tuple[int, int]:
        ix = int(wrap_coord(int(np.floor(self.x)), width))
        iy = int(wrap_coord(int(np.floor(self.y)), height))
        return iy, ix

    def cells(self, width: int, height: int, footprint: tuple[tuple[int, int], ...]) -> list[tuple[int, int]]:
        cy, cx = self.cell(width, height)
        out = []
        for dy, dx in footprint:
            iy = int(wrap_coord(cy + dy, height))
            ix = int(wrap_coord(cx + dx, width))
            out.append((iy, ix))
        return out

    def snapshot(self) -> dict[str, Any]:
        return {
            "tick": self.tick,
            "x": float(self.x), "y": float(self.y),
            "vx": float(self.vx), "vy": float(self.vy),
            "T": float(self.T),
            "B": [float(v) for v in self.B],
            "B_core": [float(v) for v in self.B_core],
            "B_sum": float(self.B.sum() + self.B_core.sum()),
            "mech": float(self.mech),
            "motor_ux": float(self.motor_ux),
            "motor_uy": float(self.motor_uy),
            "B_site": None if self.B_site is None else np.asarray(self.B_site, dtype=float).tolist(),
            "theta": float(getattr(self, "theta", 0.0)),
            "omega": float(getattr(self, "omega", 0.0)),
            "head_relative_angle": float(getattr(self, "head_relative_angle", 0.0) or 0.0),
            "head_omega": float(getattr(self, "head_omega", 0.0) or 0.0),
            "neck_motor": float(getattr(self, "neck_motor", 0.0) or 0.0),
            "push_exertion": float(getattr(self, "push_exertion", 0.0) or 0.0),
            "osc_freq_u": float(getattr(self, "osc_freq_u", 0.5) or 0.5),
            "osc_amp_u": float(getattr(self, "osc_amp_u", 0.5) or 0.5),
            "osc_emit_remaining": int(getattr(self, "osc_emit_remaining", 0) or 0),
            "osc_emit_active": float(getattr(self, "osc_emit_active", 0.0) or 0.0),
            "matter_in": self.matter_in,
            "matter_out": self.matter_out,
            "heat_from_world": self.heat_from_world,
            "heat_to_world": self.heat_to_world,
            "react_consumed": self.react_consumed,
            "core_exchange_cum": self.core_exchange_cum,
            "deformation": None if getattr(self, "deformation", None) is None else np.asarray(self.deformation, dtype=float).tolist(),
            "mechanical_work_reservoir": float(getattr(self, "mechanical_work_reservoir", 0.0) or 0.0),
            "deformation_env_force": (
                None if getattr(self, "deformation_env_force", None) is None
                else np.asarray(self.deformation_env_force, dtype=float).tolist()
            ),
            "R_site": None if getattr(self, "R_site", None) is None else np.asarray(self.R_site, dtype=float).tolist(),
            "R_A_site": None if getattr(self, "R_A_site", None) is None else np.asarray(self.R_A_site, dtype=float).tolist(),
            "R_B_site": None if getattr(self, "R_B_site", None) is None else np.asarray(self.R_B_site, dtype=float).tolist(),
        }


def initialize_physical_body(
    config: PhysicalBodyConfig | None = None,
    *,
    width: int = 32,
    height: int = 32,
    T0: float | None = None,
    B0: tuple[float, float, float] | None = None,
    B_core0: tuple[float, float, float] | None = None,
) -> PhysicalBodyState:
    cfg = config or default_physical_body_config()
    B = np.asarray(B0 if B0 is not None else (0.25, 0.20, 0.05), dtype=np.float64)
    if B_core0 is not None:
        Bc = np.asarray(B_core0, dtype=np.float64)
    elif cfg.core_enabled:
        Bc = np.asarray((0.20, 0.15, 0.10), dtype=np.float64)
    else:
        Bc = np.zeros(3, dtype=np.float64)
    return PhysicalBodyState(
        tick=0,
        x=float(cfg.start_x) + 0.5,
        y=float(cfg.start_y) + 0.5,
        vx=0.0, vy=0.0,
        T=float(0.4 if T0 is None else T0),
        B=np.clip(B, 0.0, cfg.B_max),
        B_core=np.clip(Bc, 0.0, cfg.B_max),
        mech=0.0,
    )
