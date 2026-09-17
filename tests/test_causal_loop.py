import sys
from pathlib import Path

from mechanistic_mind.agent import Action, Agent
from mechanistic_mind.core import Engine
from mechanistic_mind.environment import WorldState

# Diagnostic worlds are intentionally kept outside the core package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "worlds"))
from diagnostic_counter import CounterWorld


def make_counter_engine(seed: int = 7) -> Engine:
    return Engine(
        world=CounterWorld(
            state=WorldState(variables={"counter": 0})
        ),
        agents={"A001": Agent(agent_id="A001")},
        seed=seed,
    )


def test_observation_action_transition_loop():
    engine = make_counter_engine()

    result = engine.step(
        actions={"A001": Action("INCREMENT", {"amount": 3})}
    )

    assert result.state_before.world.variables["counter"] == 0
    assert result.observations["A001"].data["counter"] == 0
    assert result.actions["A001"].kind == "INCREMENT"
    assert result.state_after.world.variables["counter"] == 3
    assert result.state_after.tick == 1


def test_step_result_is_a_snapshot_not_a_live_alias():
    engine = make_counter_engine()

    first = engine.step(
        actions={"A001": Action("INCREMENT", {"amount": 2})}
    )
    engine.step(
        actions={"A001": Action("INCREMENT", {"amount": 5})}
    )

    assert first.state_before.world.variables["counter"] == 0
    assert first.state_after.world.variables["counter"] == 2
    assert engine.state.world.variables["counter"] == 7


def test_unknown_agent_action_is_rejected():
    engine = make_counter_engine()

    try:
        engine.step(actions={"UNKNOWN": Action.wait()})
    except KeyError:
        pass
    else:
        raise AssertionError("Expected KeyError for unknown agent")
