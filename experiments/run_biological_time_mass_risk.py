from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mechanistic_mind.agent import Action
from mechanistic_mind.body import BodyEngine, BodyState


def one_day(
    engine: BodyEngine,
    state: BodyState,
    *,
    label: str,
    effects: dict | None = None,
) -> dict:
    transition = engine.transition(
        state,
        action=Action("WAIT"),
        external_effects=effects,
    )
    body = transition.state
    return {
        "case": label,
        "mass_kg_before": state.mass_kg,
        "mass_kg_after": body.mass_kg,
        "mass_delta_kg": body.last_mass_delta_kg,
        "metabolic_balance": body.last_daily_metabolic_balance,
        "energy_reserve_after": body.energy_reserve,
        "life_day": body.life_day,
        "age_years": body.age_years,
        "low_mass_risk": body.low_mass_risk,
        "high_mass_risk": body.high_mass_risk,
        "physiological_mass_risk": body.physiological_mass_risk,
    }


def main() -> None:
    engine = BodyEngine()

    cases = [
        one_day(
            engine,
            BodyState(mass_kg=70.0),
            label="CONTROL",
        ),
        one_day(
            engine,
            BodyState(mass_kg=70.0),
            label="FUNCTIONAL_RECOVERY_NO_FOOD",
            effects={
                "energy_delta": 0.50,
                "fatigue_delta": -0.20,
            },
        ),
        one_day(
            engine,
            BodyState(mass_kg=70.0),
            label="METABOLIC_INTAKE",
            effects={
                "energy_delta": 0.40,
                "metabolic_energy_intake": 0.22,
            },
        ),
        one_day(
            engine,
            BodyState(mass_kg=40.0),
            label="LOW_MASS_RISK",
        ),
        one_day(
            engine,
            BodyState(mass_kg=130.0),
            label="HIGH_MASS_RISK",
        ),
    ]

    result = {
        "experiment": "BIOLOGICAL_TIME_AND_MASS_RISK_V031",
        "version": "0.3.1",
        "time_contract": {
            "tick_duration_days": engine.config.tick_duration_days,
            "days_per_year": engine.config.days_per_year,
        },
        "mass_contract": {
            "safe_operating_region_kg": [
                engine.config.low_mass_safe_boundary_kg,
                engine.config.high_mass_safe_boundary_kg,
            ],
            "low_mass_critical_kg": (
                engine.config.low_mass_critical_kg
            ),
            "high_mass_critical_kg": (
                engine.config.high_mass_critical_kg
            ),
            "hard_simulator_bounds_kg": [
                engine.config.minimum_mass_kg,
                engine.config.maximum_mass_kg,
            ],
            "mass_gain_requires_metabolic_intake": True,
            "progress_directly_changes_mass": False,
        },
        "cases": cases,
        "interpretation": (
            "Functional energy/recovery and metabolic intake are separate. "
            "Only objective metabolic balance changes long-term body mass. "
            "Mass risk is simulator/Observer truth and reaches the psyche only "
            "through downstream experienced physical consequences."
        ),
    }

    output = (
        ROOT
        / "experiments/biological_time_mass_risk_v031_result.json"
    )
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
