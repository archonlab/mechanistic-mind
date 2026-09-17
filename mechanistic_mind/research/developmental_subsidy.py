"""Update 4.2 — Minimal Developmental Subsidy (MDS) parameterization.

Subsidy is initial physical reserve only. No free energy during the run,
no rewards, no action-cost changes.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from mechanistic_mind.body.models import BodyConfig, BodyState

# Experimental ladder labels (tick-equivalent targets under WAIT-like drain).
MDS_LADDER_TICK_EQUIVALENT = (250, 500, 750, 1000, 1250, 1500, 2000)

# Calibrated ecology WAIT-ish energy drain ≈ basal(0.0008)+ambient(0.0008).
DEFAULT_WAIT_ENERGY_DRAIN_PER_TICK = 0.0016
DEFAULT_WAIT_HYDRATION_DRAIN_PER_TICK = 0.0016


@dataclass(frozen=True, slots=True)
class DevelopmentalSubsidySpec:
    """Physical initial-reserve specification derived from a tick-equivalent label."""

    tick_equivalent: int
    energy_reserve: float
    hydration: float
    fatigue: float
    energy_capacity: float
    hydration_capacity: float
    estimated_wait_energy_drain_per_tick: float
    estimated_wait_hydration_drain_per_tick: float
    note: str = "initial physical reserve only; normal physics thereafter"

    def to_dict(self) -> dict[str, Any]:
        return {
            "tick_equivalent": int(self.tick_equivalent),
            "energy_reserve": float(self.energy_reserve),
            "hydration": float(self.hydration),
            "fatigue": float(self.fatigue),
            "energy_capacity": float(self.energy_capacity),
            "hydration_capacity": float(self.hydration_capacity),
            "estimated_wait_energy_drain_per_tick": float(
                self.estimated_wait_energy_drain_per_tick
            ),
            "estimated_wait_hydration_drain_per_tick": float(
                self.estimated_wait_hydration_drain_per_tick
            ),
            "note": self.note,
        }


def subsidy_from_tick_equivalent(
    tick_equivalent: int,
    *,
    energy_drain_per_tick: float = DEFAULT_WAIT_ENERGY_DRAIN_PER_TICK,
    hydration_drain_per_tick: float = DEFAULT_WAIT_HYDRATION_DRAIN_PER_TICK,
    fatigue: float = 0.14,
    capacity_margin: float = 1.05,
) -> DevelopmentalSubsidySpec:
    """Map a runway label to continuous initial reserves + capacities.

    Does not guarantee survival for ``tick_equivalent`` ticks under EMIT binge.
    It sizes the initial tank for approximately that WAIT-equivalent runway.
    """
    te = int(tick_equivalent)
    if te < 1:
        raise ValueError("tick_equivalent must be >= 1")
    e_need = float(te) * float(energy_drain_per_tick)
    h_need = float(te) * float(hydration_drain_per_tick)
    e_cap = max(1.0, e_need * capacity_margin)
    h_cap = max(1.0, h_need * capacity_margin)
    return DevelopmentalSubsidySpec(
        tick_equivalent=te,
        energy_reserve=e_need,
        hydration=h_need,
        fatigue=float(fatigue),
        energy_capacity=e_cap,
        hydration_capacity=h_cap,
        estimated_wait_energy_drain_per_tick=float(energy_drain_per_tick),
        estimated_wait_hydration_drain_per_tick=float(hydration_drain_per_tick),
    )


def apply_subsidy_to_body_config(
    config: BodyConfig, spec: DevelopmentalSubsidySpec
) -> BodyConfig:
    return replace(
        config,
        energy_capacity=float(spec.energy_capacity),
        hydration_capacity=float(spec.hydration_capacity),
    )


def apply_subsidy_to_body_state(
    state: BodyState | None, spec: DevelopmentalSubsidySpec
) -> BodyState:
    st = state.clone() if state is not None else BodyState()
    st.energy_reserve = float(spec.energy_reserve)
    st.hydration = float(spec.hydration)
    st.fatigue = float(spec.fatigue)
    return st


def baseline_unsubsidized_spec() -> DevelopmentalSubsidySpec:
    """Canonical pre-4.2 initial state (BodyState defaults, capacity 1)."""
    return DevelopmentalSubsidySpec(
        tick_equivalent=0,
        energy_reserve=0.76,
        hydration=0.78,
        fatigue=0.14,
        energy_capacity=1.0,
        hydration_capacity=1.0,
        estimated_wait_energy_drain_per_tick=DEFAULT_WAIT_ENERGY_DRAIN_PER_TICK,
        estimated_wait_hydration_drain_per_tick=DEFAULT_WAIT_HYDRATION_DRAIN_PER_TICK,
        note="canonical baseline initial reserves (capacity 1.0)",
    )
