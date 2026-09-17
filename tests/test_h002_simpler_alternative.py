import sys
from pathlib import Path

from mechanistic_mind.research.h002_simpler_alternative import run_h002

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "worlds"))
from two_choice_yield import TwoChoiceYieldWorld


def test_h002_simpler_mechanism_matches_h001_behavior():
    result = run_h002(
        world_factory=TwoChoiceYieldWorld,
        ticks=12,
        seed=17,
    )

    assert result.outcome_trace.choose_a == 1
    assert result.outcome_trace.choose_b == 11
    assert result.simpler_alternative.choose_a == 1
    assert result.simpler_alternative.choose_b == 11

    assert (
        result.outcome_trace.cumulative_outcome
        == result.simpler_alternative.cumulative_outcome
        == 34.0
    )

    assert (
        result.behavioral_difference[
            "delta_choose_B_rate_simpler_minus_h001"
        ]
        == 0.0
    )
    assert (
        result.behavioral_difference[
            "delta_cumulative_outcome_simpler_minus_h001"
        ]
        == 0.0
    )


def test_h002_simpler_mechanism_uses_less_persistent_state():
    result = run_h002(
        world_factory=TwoChoiceYieldWorld,
        ticks=12,
        seed=17,
    )

    assert (
        result.simpler_alternative.state_scalar_count
        < result.outcome_trace.state_scalar_count
    )
    assert result.status == "H001_INTERNAL_COMPLEXITY_NOT_NECESSARY_HERE"


def test_h002_both_paths_are_fully_observed_and_bridged():
    result = run_h002(
        world_factory=TwoChoiceYieldWorld,
        ticks=12,
        seed=17,
    )

    for condition in (
        result.outcome_trace,
        result.simpler_alternative,
    ):
        assert condition.observer_ticks == 12
        assert condition.archon_observations == 12
        assert condition.archon_events >= 24


def test_h002_is_reproducible():
    first = run_h002(
        world_factory=TwoChoiceYieldWorld,
        ticks=12,
        seed=17,
    )
    second = run_h002(
        world_factory=TwoChoiceYieldWorld,
        ticks=12,
        seed=17,
    )

    assert first.to_dict() == second.to_dict()
