import sys
from pathlib import Path

from mechanistic_mind.research.h001_outcome_trace import run_h001

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "worlds"))
from two_choice_yield import TwoChoiceYieldWorld


def test_h001_produces_predicted_behavioral_divergence():
    result = run_h001(
        world_factory=TwoChoiceYieldWorld,
        ticks=12,
        seed=17,
    )

    assert result.control.choose_a == 6
    assert result.control.choose_b == 6
    assert result.control.choose_b_rate == 0.5

    assert result.treatment.choose_a == 1
    assert result.treatment.choose_b == 11
    assert result.treatment.choose_b_rate > result.control.choose_b_rate

    assert (
        result.treatment.cumulative_outcome
        > result.control.cumulative_outcome
    )
    assert result.status == "SUPPORTED_IN_DIAGNOSTIC_WORLD"


def test_h001_observer_and_archon_paths_capture_every_tick():
    result = run_h001(
        world_factory=TwoChoiceYieldWorld,
        ticks=12,
        seed=17,
    )

    for condition in (result.control, result.treatment):
        assert condition.observer_ticks == 12
        assert condition.archon_observations == 12
        assert condition.archon_events >= 24


def test_h001_action_provenance_identifies_active_mechanism():
    result = run_h001(
        world_factory=TwoChoiceYieldWorld,
        ticks=6,
        seed=17,
    )

    assert set(result.control.action_sources) == {
        "MECHANISM:H001-CONTROL-ALTERNATOR"
    }
    assert set(result.treatment.action_sources) == {
        "MECHANISM:H001-OUTCOME-TRACE"
    }


def test_h001_same_seed_is_reproducible():
    first = run_h001(
        world_factory=TwoChoiceYieldWorld,
        ticks=12,
        seed=17,
    )
    second = run_h001(
        world_factory=TwoChoiceYieldWorld,
        ticks=12,
        seed=17,
    )

    assert first.observed_effect == second.observed_effect
    assert first.control == second.control
    assert first.treatment == second.treatment
