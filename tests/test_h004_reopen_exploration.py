import sys
from pathlib import Path

from mechanistic_mind.research.h004_reopen_exploration import run_h004

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "worlds"))
from reversal_yield import ReversalYieldWorld


def run():
    return run_h004(
        world_factory=lambda: ReversalYieldWorld(reversal_after=6),
        ticks=30,
        seed=17,
        epsilon=0.25,
        drop_threshold=0.75,
    )


def test_h004_drop_trigger_restores_post_reversal_adaptation():
    result = run()

    assert result.drop_triggered.post_optimal_rate > 0.5
    assert result.drop_triggered.first_post_a_tick is not None


def test_h004_random_exploration_is_reproducible():
    first = run()
    second = run()

    assert first.to_dict() == second.to_dict()


def test_h004_both_conditions_are_fully_observed_and_bridged():
    result = run()

    for condition in (
        result.random_exploration,
        result.drop_triggered,
    ):
        assert condition.observer_ticks == 30
        assert condition.archon_observations == 30
        assert condition.archon_events >= 60


def test_h004_reports_exploration_events():
    result = run()

    assert result.random_exploration.exploration_events > 0
    assert result.drop_triggered.exploration_events > 0
