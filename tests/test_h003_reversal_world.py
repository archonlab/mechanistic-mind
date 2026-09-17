import sys
from pathlib import Path

from mechanistic_mind.research.h003_reversal_world import run_h003

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "worlds"))
from reversal_yield import ReversalYieldWorld


def run():
    return run_h003(
        world_factory=lambda: ReversalYieldWorld(reversal_after=6),
        ticks=18,
        seed=17,
    )


def test_h003_reversal_is_hidden_from_observation_contract():
    world = ReversalYieldWorld(reversal_after=6)
    observation = world.observe(world.state, "A001")

    assert "phase" not in observation.data
    assert "pre_yield_A" not in observation.data
    assert "post_yield_A" not in observation.data


def test_h003_both_existing_models_fail_to_adapt():
    result = run()

    assert result.running_means.adapted is False
    assert result.best_seen.adapted is False
    assert result.running_means.post_a == 0
    assert result.best_seen.post_a == 0
    assert result.status == "BOTH_MODELS_FAIL_REVERSAL_ADAPTATION"


def test_h003_both_models_remain_on_old_optimal_action():
    result = run()

    assert result.running_means.post_b == 12
    assert result.best_seen.post_b == 12
    assert result.running_means.post_optimal_rate == 0.0
    assert result.best_seen.post_optimal_rate == 0.0


def test_h003_reversal_creates_regret_against_oracle():
    result = run()

    assert result.running_means.regret > 0
    assert result.best_seen.regret > 0


def test_h003_observer_and_archon_capture_full_run():
    result = run()

    for condition in (result.running_means, result.best_seen):
        assert condition.observer_ticks == 18
        assert condition.archon_observations == 18
        assert condition.archon_events >= 36


def test_h003_is_reproducible():
    first = run()
    second = run()

    assert first.to_dict() == second.to_dict()
