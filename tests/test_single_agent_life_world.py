import sys
from pathlib import Path
import pytest

from mechanistic_mind.agent import Agent
from mechanistic_mind.core import Engine
from mechanistic_mind.mechanisms import MechanismRegistry
from mechanistic_mind.psyche import PsycheState, SingleAgentPsycheV01, build_life_modules

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "worlds"))
from single_agent_life import SingleAgentLifeWorld


@pytest.fixture(scope="module")
def life_engine():
    registry = MechanismRegistry()
    registry.register(
        SingleAgentPsycheV01(
            modules=build_life_modules(),
            initial_state=PsycheState.initial_life_v01(),
        )
    )
    engine = Engine(
        world=SingleAgentLifeWorld(),
        agents={"A001": Agent(agent_id="A001")},
        seed=17,
        mechanisms=registry,
    )
    engine.run(80)
    return engine


def test_life_world_hides_roles_and_outcomes():
    world = SingleAgentLifeWorld()
    obs = world.observe(world.state, "A001")
    assert "objects" not in obs.data
    assert all(
        "hidden_role" not in item and "outcome" not in item
        for item in obs.data["visible_objects"]
    )


def test_life_world_exposes_local_affordances_and_spatial_actions():
    world = SingleAgentLifeWorld()
    obs = world.observe(world.state, "A001")
    actions = obs.data["available_actions"]
    assert any(action.startswith("MOVE:") for action in actions)
    assert "USE:OBJ-04" in actions
    assert "WAIT" in actions
    assert obs.data["position"] == [4, 3]


def test_life_psyche_explores_and_discovers_objects(life_engine):
    world = life_engine.state.world.variables
    psyche = life_engine.state.agents["A001"].mechanism_states[
        "PSYCHE-SINGLE-AGENT-V01"
    ]["psyche"]
    assert len(world["visited_positions"]) >= 40
    assert len(psyche["memory"]["spatial"]["objects"]) == 4
    assert len(psyche["learning"]["action_models"]) >= 40


def test_life_psyche_uses_multiple_affordances(life_engine):
    counts = life_engine.state.world.variables["object_use_counts"]
    used = {key for key, count in counts.items() if count > 0}
    assert len(used) >= 3


def test_life_psyche_has_multidimensional_internal_state(life_engine):
    internal = life_engine.state.agents["A001"].mechanism_states[
        "PSYCHE-SINGLE-AGENT-V01"
    ]["psyche"]["internal"]
    assert {"energy", "hydration", "fatigue", "progress"} <= set(internal)
    assert all(0.0 <= internal[key] <= 1.0 for key in ("energy", "hydration", "fatigue"))
