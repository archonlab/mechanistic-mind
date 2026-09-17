from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any


DAYS_PER_YEAR = 365.2425


@dataclass(frozen=True, slots=True)
class BodyConfig:
    """Objective toy physiology for one simulated day per tick.

    The numbers are research-model parameters, not medical thresholds or a
    realistic human metabolic model.
    """

    # Biological time.
    tick_duration_days: float = 1.0
    days_per_year: float = DAYS_PER_YEAR

    # Reference body used by the toy movement-cost equation.
    reference_mass_kg: float = 70.0

    # Per-day passive physiology.
    basal_energy_drain_per_day: float = 0.035
    basal_hydration_drain_per_day: float = 0.045
    passive_fatigue_gain_per_day: float = 0.025

    # Per-action physical cost.
    movement_energy_cost_per_cell: float = 0.012
    movement_hydration_cost_per_cell: float = 0.004
    movement_fatigue_cost_per_cell: float = 0.010
    movement_metabolic_expenditure_per_effort: float = 0.030

    damage_effort_multiplier: float = 1.5
    fatigue_effort_multiplier: float = 0.8
    mass_effort_exponent: float = 1.0
    mass_risk_effort_multiplier: float = 0.75

    # Objective metabolic balance → slow body-mass change.
    basal_metabolic_expenditure_per_day: float = 0.080
    kg_per_metabolic_balance_unit: float = 0.120
    max_mass_gain_kg_per_day: float = 0.050
    max_mass_loss_kg_per_day: float = 0.080

    # Hard simulator bounds. These are not the "safe" region.
    minimum_mass_kg: float = 25.0
    maximum_mass_kg: float = 180.0

    # User-selected toy risk region.
    low_mass_safe_boundary_kg: float = 45.0
    low_mass_critical_kg: float = 35.0
    high_mass_safe_boundary_kg: float = 120.0
    high_mass_critical_kg: float = 140.0

    # Objective consequences of living outside the operating region.
    mass_risk_fatigue_per_day: float = 0.012
    mass_risk_damage_per_day: float = 0.0010
    low_mass_extra_energy_drain_per_day: float = 0.012
    mass_risk_recovery_penalty: float = 0.35

    # Generic persistent internal loads and physical carried-load costs.
    internal_load_decay_per_day: float = 0.04
    carried_energy_cost_per_kg_day: float = 0.0010
    carried_hydration_cost_per_kg_day: float = 0.0003
    carried_fatigue_cost_per_kg_day: float = 0.0008
    # Update 4 activity–recovery (off by default).
    recovery_dynamics_enabled: bool = False
    # Update 4.8 — bounded physical intake (not cognition; no food semantics).
    physical_intake_enabled: bool = False
    intake_transfer_enabled: bool = True
    intake_processing_enabled: bool = True
    intake_per_interaction_capacity: float = 0.03
    intake_internal_capacity: float = 0.20
    intake_processing_rate_per_tick: float = 0.25
    intake_max_process_per_tick: float = 0.01
    # Update 4.9 — continuous environmental exchange into same internal_materials.
    env_exchange_enabled: bool = False
    env_exchange_transfer_enabled: bool = True
    env_exchange_material_id: str = "material_a"
    env_exchange_per_tick_capacity: float = 0.008
    env_exchange_coefficient: float = 1.0
    activity_load_gain_per_effort: float = 0.08
    activity_load_decay_per_day: float = 0.12
    inactivity_fatigue_recovery_per_day: float = 0.018
    inactivity_load_recovery_per_day: float = 0.06
    max_inactivity_fatigue_recovery_per_day: float = 0.035
    # Update 4.5.1: marginal motor cost rises with activity_load (physiology).
    activity_load_effort_multiplier: float = 1.2
    # Motor demand without displacement still loads the activity system.
    motor_demand_energy_cost: float = 0.004
    motor_demand_hydration_cost: float = 0.0012
    motor_demand_fatigue_cost: float = 0.003

    # Update 4.2: physical capacity for developmental subsidy (default 1.0 = legacy).
    # Interoceptive signals remain bounded; reserves may exceed 1.0 when capacity > 1.
    energy_capacity: float = 1.0
    hydration_capacity: float = 1.0
    # Update 4.20 — optional generic persistent processes (researcher config).
    persistent_process_config: dict | None = None
    # Update 4.56 — optional generic physical transduction (experimental; default off).
    physical_transduction_config: dict | None = None
    # Update 4.59 — optional generic physical effector (experimental; default off).
    physical_effector_config: dict | None = None
    # Update 4.60 — optional fixed physical coupling (experimental; default off).
    physical_coupling_config: dict | None = None
    # Update 4.65 — optional minimal passive physical exchange (experimental; default off).
    passive_physical_exchange_config: dict | None = None
    # Update 4.75 — optional bounded internal transition relation (experimental; default off).
    internal_transition_acquisition_config: dict | None = None
    # Update 4.76 — optional current S query of frozen L (experimental; default off).
    acquired_transition_reinstatement_config: dict | None = None
    # PHYS-4.76-E1A — optional generic contact→intake transfer (experimental; default off).
    contact_material_transfer_config: dict | None = None
    # MM-INT-1 — optional embodied psyche integration (designed substrate; default off = legacy).
    embodied_integration_config: dict | None = None

    def validate(self) -> None:
        if self.tick_duration_days <= 0:
            raise ValueError("tick_duration_days must be > 0")
        if self.days_per_year <= 0:
            raise ValueError("days_per_year must be > 0")
        if not (
            self.minimum_mass_kg
            < self.low_mass_critical_kg
            < self.low_mass_safe_boundary_kg
            < self.high_mass_safe_boundary_kg
            < self.high_mass_critical_kg
            < self.maximum_mass_kg
        ):
            raise ValueError("Mass bounds/risk boundaries are inconsistent")
        if self.max_mass_gain_kg_per_day < 0:
            raise ValueError("max_mass_gain_kg_per_day must be >= 0")
        if self.max_mass_loss_kg_per_day < 0:
            raise ValueError("max_mass_loss_kg_per_day must be >= 0")
        if not (0.0 <= self.internal_load_decay_per_day <= 1.0):
            raise ValueError("internal_load_decay_per_day must be in [0, 1]")
        if self.energy_capacity <= 0:
            raise ValueError("energy_capacity must be > 0")
        if self.hydration_capacity <= 0:
            raise ValueError("hydration_capacity must be > 0")


@dataclass(slots=True)
class BodyState:
    """Objective physical state of one organism.

    Default v0.3.1 organism is deliberately adult-like so the configured
    45–120 kg operating region is interpretable. Developmental growth remains
    future work.
    """

    mass_kg: float = 70.0
    height_m: float = 1.75
    age_days: float = 18.0 * DAYS_PER_YEAR
    simulated_days: float = 0.0

    energy_reserve: float = 0.76
    hydration: float = 0.78
    fatigue: float = 0.14
    damage: float = 0.0
    last_effort_cost: float = 0.0

    # Observer-truth diagnostics, recomputed by BodyEngine.
    low_mass_risk: float = 0.0
    high_mass_risk: float = 0.0
    physiological_mass_risk: float = 0.0
    last_daily_metabolic_balance: float = 0.0
    last_mass_delta_kg: float = 0.0
    internal_loads: dict[str, float] = field(default_factory=dict)
    activity_load: float = 0.0
    consecutive_wait_ticks: int = 0
    # Update 4.8: nonsemantic internal material reservoirs (pre-consequence).
    internal_materials: dict[str, float] = field(default_factory=dict)
    last_intake_transfer: float = 0.0
    last_intake_processed: float = 0.0
    last_process_receipt: dict[str, Any] = field(default_factory=dict)
    last_env_exchange: float = 0.0
    last_env_availability: float = 0.0
    # Update 4.56 experimental transducer state (inactive unless config on).
    transducer_state: tuple[float, float, float] = (0.0, 0.0, 0.0)
    transducer_prev: tuple[float, float, float] | None = None
    # MM-INT-1 embodied integration persistent state (None = legacy / absent).
    embodied_integration: dict | None = None

    @property
    def activity_capacity(self) -> float:
        """Available shorter-timescale activity capacity = 1 - load.
        Not metabolic energy. Bounded [0,1]."""
        return max(0.0, min(1.0, 1.0 - float(self.activity_load)))

    @property
    def age_years(self) -> float:
        return self.age_days / DAYS_PER_YEAR

    @property
    def life_day(self) -> int:
        return int(round(self.simulated_days))

    def clone(self) -> "BodyState":
        return deepcopy(self)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mass_kg": float(self.mass_kg),
            "height_m": float(self.height_m),
            "age_days": float(self.age_days),
            "age_years": float(self.age_years),
            "simulated_days": float(self.simulated_days),
            "life_day": int(self.life_day),
            "energy_reserve": float(self.energy_reserve),
            "hydration": float(self.hydration),
            "fatigue": float(self.fatigue),
            "damage": float(self.damage),
            "last_effort_cost": float(self.last_effort_cost),
            "low_mass_risk": float(self.low_mass_risk),
            "high_mass_risk": float(self.high_mass_risk),
            "physiological_mass_risk": float(
                self.physiological_mass_risk
            ),
            "last_daily_metabolic_balance": float(
                self.last_daily_metabolic_balance
            ),
            "last_mass_delta_kg": float(self.last_mass_delta_kg),
            "internal_loads": deepcopy(self.internal_loads),
            "activity_load": float(self.activity_load),
            "consecutive_wait_ticks": int(self.consecutive_wait_ticks),
            "internal_materials": deepcopy(self.internal_materials),
            "last_process_receipt": deepcopy(self.last_process_receipt),
            "last_intake_transfer": float(self.last_intake_transfer),
            "last_intake_processed": float(self.last_intake_processed),
            "last_env_exchange": float(self.last_env_exchange),
            "last_env_availability": float(self.last_env_availability),
            "transducer_state": tuple(float(x) for x in (self.transducer_state or (0.0, 0.0, 0.0))),
            "transducer_prev": None if self.transducer_prev is None else tuple(float(x) for x in self.transducer_prev),
            "embodied_integration": deepcopy(self.embodied_integration) if self.embodied_integration is not None else None,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "BodyState":
        if "age_days" in payload:
            age_days = float(payload["age_days"])
        else:
            # Backward compatibility with v0.3 telemetry/state.
            age_days = float(payload.get("age_years", 18.0)) * DAYS_PER_YEAR

        return cls(
            mass_kg=float(payload.get("mass_kg", 70.0)),
            height_m=float(payload.get("height_m", 1.75)),
            age_days=age_days,
            simulated_days=float(payload.get("simulated_days", 0.0)),
            energy_reserve=float(payload.get("energy_reserve", 0.76)),
            hydration=float(payload.get("hydration", 0.78)),
            fatigue=float(payload.get("fatigue", 0.14)),
            damage=float(payload.get("damage", 0.0)),
            last_effort_cost=float(payload.get("last_effort_cost", 0.0)),
            low_mass_risk=float(payload.get("low_mass_risk", 0.0)),
            high_mass_risk=float(payload.get("high_mass_risk", 0.0)),
            physiological_mass_risk=float(
                payload.get("physiological_mass_risk", 0.0)
            ),
            last_daily_metabolic_balance=float(
                payload.get("last_daily_metabolic_balance", 0.0)
            ),
            last_mass_delta_kg=float(
                payload.get("last_mass_delta_kg", 0.0)
            ),
            activity_load=float(payload.get("activity_load", 0.0)),
            internal_materials={
                str(k): float(v)
                for k, v in dict(payload.get("internal_materials") or {}).items()
                if isinstance(v, (int, float))
            },
            last_intake_transfer=float(payload.get("last_intake_transfer", 0.0)),
            last_intake_processed=float(payload.get("last_intake_processed", 0.0)),
            last_process_receipt=dict(payload.get("last_process_receipt") or {}),
            last_env_exchange=float(payload.get("last_env_exchange", 0.0)),
            last_env_availability=float(payload.get("last_env_availability", 0.0)),
            consecutive_wait_ticks=int(payload.get("consecutive_wait_ticks", 0)),
            internal_loads={
                str(key): float(value)
                for key, value in payload.get("internal_loads", {}).items()
                if isinstance(value, (int, float)) and not isinstance(value, bool)
            } if isinstance(payload.get("internal_loads", {}), dict) else {},
            transducer_state=tuple(float(x) for x in (payload.get("transducer_state") or (0.0, 0.0, 0.0)))
            if isinstance(payload.get("transducer_state"), (list, tuple)) else (0.0, 0.0, 0.0),
            transducer_prev=tuple(float(x) for x in payload["transducer_prev"])
            if isinstance(payload.get("transducer_prev"), (list, tuple)) else None,
            embodied_integration=deepcopy(payload["embodied_integration"])
            if isinstance(payload.get("embodied_integration"), dict) else None,
        )


@dataclass(frozen=True, slots=True)
class InteroceptiveSignals:
    """Signals available to the psyche.

    No body mass, age, risk boundary, calorie balance, or physiological formula
    is exposed to the agent.
    """

    energy_signal: float
    hydration_signal: float
    fatigue_signal: float
    discomfort_signal: float
    effort_signal: float
    # Update 4.5.1 — physical activity-capacity channels (not motivation).
    activity_load_signal: float = 0.0
    activity_capacity_signal: float = 1.0

    def to_dict(self) -> dict[str, float]:
        return {
            "energy_signal": float(self.energy_signal),
            "hydration_signal": float(self.hydration_signal),
            "fatigue_signal": float(self.fatigue_signal),
            "discomfort_signal": float(self.discomfort_signal),
            "effort_signal": float(self.effort_signal),
            "activity_load_signal": float(self.activity_load_signal),
            "activity_capacity_signal": float(self.activity_capacity_signal),
        }
