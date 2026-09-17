from mechanistic_mind.agent import Action, Agent
from mechanistic_mind.core import Engine
from mechanistic_mind.environment import World


def make_engine(seed: int = 42) -> Engine:
    return Engine(
        world=World(),
        agents={"A001": Agent(agent_id="A001")},
        seed=seed,
    )


def test_engine_advances_ticks():
    engine = make_engine()

    assert engine.state.tick == 0
    assert engine.step().state_after.tick == 1
    assert engine.step().state_after.tick == 2


def test_run_advances_requested_ticks():
    engine = make_engine()
    final_state = engine.run(10)

    assert final_state.tick == 10


def test_same_seed_has_same_rng_sequence():
    first = make_engine(seed=42)
    second = make_engine(seed=42)

    sequence_a = [first.rng.random() for _ in range(10)]
    sequence_b = [second.rng.random() for _ in range(10)]

    assert sequence_a == sequence_b


def test_reset_restores_tick_and_rng():
    engine = make_engine(seed=42)
    first_value = engine.rng.random()
    engine.run(5)

    engine.reset()

    assert engine.state.tick == 0
    assert engine.rng.random() == first_value


def test_default_action_is_wait():
    engine = make_engine()

    result = engine.step()

    assert result.actions["A001"] == Action.wait()
