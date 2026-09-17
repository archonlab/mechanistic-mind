from __future__ import annotations

import math
import sys
from pathlib import Path

from mechanistic_mind.agent import Action
from mechanistic_mind.body import BodyConfig, BodyEngine, BodyState

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "worlds"))
from organism_world_v03 import (
    OrganismWorld,
    default_organism_world_config,
)


def test_one_tick_is_one_simulated_day():
    engine = BodyEngine()
    before = BodyState()
    transition = engine.transition(
        before,
        action=Action("WAIT"),
    )
    after = transition.state

    assert after.simulated_days == 1.0
    assert after.life_day == 1
    assert math.isclose(
        after.age_days - before.age_days,
        1.0,
        rel_tol=0.0,
        abs_tol=1e-12,
    )
    assert math.isclose(
        after.age_years - before.age_years,
        1.0 / BodyConfig().days_per_year,
        rel_tol=0.0,
        abs_tol=1e-12,
    )


def test_safe_mass_region_has_zero_mass_risk():
    engine = BodyEngine()
    for mass in (45.0, 70.0, 120.0):
        risk = engine.mass_risk(mass)
        assert risk["low_mass_risk"] == 0.0
        assert risk["high_mass_risk"] == 0.0
        assert risk["physiological_mass_risk"] == 0.0


def test_low_mass_risk_rises_smoothly_below_45kg():
    engine = BodyEngine()
    r44 = engine.mass_risk(44.0)["low_mass_risk"]
    r40 = engine.mass_risk(40.0)["low_mass_risk"]
    r35 = engine.mass_risk(35.0)["low_mass_risk"]

    assert 0.0 < r44 < r40 < r35
    assert r35 == 1.0


def test_high_mass_risk_rises_smoothly_above_120kg():
    engine = BodyEngine()
    r121 = engine.mass_risk(121.0)["high_mass_risk"]
    r130 = engine.mass_risk(130.0)["high_mass_risk"]
    r140 = engine.mass_risk(140.0)["high_mass_risk"]

    assert 0.0 < r121 < r130 < r140
    assert r140 == 1.0


def test_positive_functional_energy_without_metabolic_intake_does_not_add_mass():
    engine = BodyEngine()
    base = BodyState(mass_kg=70.0)

    control = engine.transition(
        base,
        action=Action("WAIT"),
    ).state
    pleasant_recovery = engine.transition(
        base,
        action=Action("WAIT"),
        external_effects={
            "energy_delta": 0.50,
            "fatigue_delta": -0.20,
        },
    ).state

    # Same objective metabolic balance, therefore exactly the same mass change.
    assert math.isclose(
        pleasant_recovery.mass_kg,
        control.mass_kg,
        rel_tol=0.0,
        abs_tol=1e-12,
    )
    assert pleasant_recovery.energy_reserve > control.energy_reserve


def test_metabolic_intake_changes_mass_relative_to_control():
    engine = BodyEngine()
    base = BodyState(mass_kg=70.0)

    control = engine.transition(
        base,
        action=Action("WAIT"),
    ).state
    fed = engine.transition(
        base,
        action=Action("WAIT"),
        external_effects={
            "energy_delta": 0.40,
            "metabolic_energy_intake": 0.22,
        },
    ).state

    assert fed.mass_kg > control.mass_kg
    assert fed.last_daily_metabolic_balance > (
        control.last_daily_metabolic_balance
    )


def test_mass_change_has_daily_rate_limits():
    cfg = BodyConfig(
        max_mass_gain_kg_per_day=0.05,
        max_mass_loss_kg_per_day=0.08,
    )
    engine = BodyEngine(cfg)
    base = BodyState(mass_kg=70.0)

    huge_surplus = engine.transition(
        base,
        action=Action("WAIT"),
        external_effects={
            "metabolic_energy_intake": 1000.0,
        },
    ).state
    huge_deficit = engine.transition(
        base,
        action=Action("WAIT"),
        external_effects={
            "metabolic_energy_expenditure": 1000.0,
        },
    ).state

    assert math.isclose(
        huge_surplus.mass_kg - base.mass_kg,
        0.05,
        abs_tol=1e-12,
    )
    assert math.isclose(
        huge_deficit.mass_kg - base.mass_kg,
        -0.08,
        abs_tol=1e-12,
    )


def test_canonical_progress_site_has_no_metabolic_intake():
    config = default_organism_world_config()
    records = {
        item.object_id: item
        for item in config.objects
    }

    assert (
        records["OBJ-31"].world_effects["progress_delta"]
        == 1.0
    )
    assert "metabolic_energy_intake" not in (
        records["OBJ-31"].body_effects
    )
    assert "mass_energy_balance" not in str(
        records["OBJ-31"].body_effects
    )


def test_canonical_energy_resource_is_explicit_metabolic_intake():
    config = default_organism_world_config()
    records = {
        item.object_id: item
        for item in config.objects
    }
    assert (
        records["OBJ-17"]
        .body_effects["metabolic_energy_intake"]
        > 0.0
    )


def test_mass_risk_and_biological_time_remain_observer_truth():
    world = OrganismWorld(
        initial_body=BodyState(
            mass_kg=40.0,
            age_days=30.0 * BodyConfig().days_per_year,
        )
    )
    observation = world.observe(
        world.state,
        "A001",
    ).data

    forbidden = (
        "mass_kg",
        "low_mass_risk",
        "high_mass_risk",
        "physiological_mass_risk",
        "age_days",
        "age_years",
        "life_day",
        "metabolic_energy",
    )
    serialized = str(observation)
    for key in forbidden:
        assert key not in serialized
