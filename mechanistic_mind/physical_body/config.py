"""Physical body structural parameters — BODY-1 defaults preserved; BODY-2 adds slow core."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class PhysicalBodyConfig:
    # geometry / inertia
    mass: float = 1.0
    drag: float = 0.25
    flow_coupling: float = 0.40
    wave_coupling: float = 0.20
    v_max: float = 0.35
    start_x: int = 8
    start_y: int = 16

    # thermal
    heat_capacity: float = 2.5
    thermal_conductance: float = 0.18
    thermal_backreact: float = 0.05
    T_min: float = 0.0
    T_max: float = 1.0

    # material
    permeability: tuple[float, float, float] = (0.12, 0.08, 0.04)
    material_backreact: bool = True
    B_max: float = 2.0

    # internal surface reaction B0+B1 -> B2
    react_rate: float = 0.025
    react_heat: float = 0.015
    reaction_enabled: bool = True

    # research cuts
    thermal_enabled: bool = True
    material_enabled: bool = True
    mechanical_enabled: bool = True
    displacement_enabled: bool = True

    # --- MM-BODY-2 extensions (defaults keep BODY-1 behavior) ---
    # footprint: list of (dy, dx) cell offsets from center; BODY-1 = [(0,0)]
    footprint: tuple[tuple[int, int], ...] = ((0, 0),)
    # slow core compartment: exchanges only with surface B, not WORLD
    core_enabled: bool = False
    core_exchange: float = 0.02  # surface <-> core rate
    # optional slower surface (used by body2 preset)
    # (BODY-1 defaults unchanged above)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["permeability"] = list(self.permeability)
        d["footprint"] = [list(p) for p in self.footprint]
        return d


def default_physical_body_config() -> PhysicalBodyConfig:
    """MM-BODY-1 single-cell defaults (regressions)."""
    return PhysicalBodyConfig()


def default_physical_body2_config() -> PhysicalBodyConfig:
    """MM-BODY-2: 5-cell plus footprint, slower surface exchange, slow core.

    Parameters chosen for slower equilibration / multi-cell extent — not for
    viability, behavior, or cognition.
    """
    return PhysicalBodyConfig(
        mass=2.0,
        drag=0.30,
        flow_coupling=0.35,
        wave_coupling=0.15,
        v_max=0.30,
        heat_capacity=6.0,
        thermal_conductance=0.06,
        thermal_backreact=0.04,
        permeability=(0.035, 0.025, 0.012),
        react_rate=0.015,
        react_heat=0.01,
        footprint=((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)),
        core_enabled=True,
        core_exchange=0.015,
    )
