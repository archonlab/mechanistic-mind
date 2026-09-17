from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

from mechanistic_mind.agent import Action, Agent
from mechanistic_mind.body import BodyConfig, BodyEngine, BodyState
from mechanistic_mind.core import DeterministicRandom, Engine
from mechanistic_mind.mechanisms import MechanismRegistry
from mechanistic_mind.psyche import PsycheState, SingleOrganismPsycheV03
from mechanistic_mind.world_engine import (
    ExogenousEventKind,
    ScheduledExogenousEvent,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "worlds"))
from organism_world_v03 import OrganismWorld, default_organism_world_config


FORBIDDEN_PRESET_KEYS = {
    "trust",
    "anxiety",
    "avoidance",
    "personality",
    "resource_preference",
    "world_reliability_belief",
}


def _engine(world: OrganismWorld, *, seed: int = 17) -> Engine:
    registry = MechanismRegistry()
    registry.register(SingleOrganismPsycheV03())
    return Engine(
        world=world,
        agents={"A001": Agent(agent_id="A001")},
        seed=seed,
        mechanisms=registry,
    )


def test_psyche_starts_without_preset_personality_or_body_truth():
    state = PsycheState.initial_organism_v03()
    payload = state.to_dict()
    keys = set()

    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                keys.add(str(key))
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(payload)
    assert not (FORBIDDEN_PRESET_KEYS & keys)
    assert "mass_kg" not in keys
    assert "age_years" not in keys
    assert state.learning["action_models"] == {}
    assert state.memory["episodes"] == []
    assert state.habits["strength"] == {}


def test_agent_observation_hides_body_truth_and_object_outcomes():
    world = OrganismWorld()
    observation = world.observe(world.state, "A001").data

    assert "interoception" in observation
    assert "mass_kg" not in observation
    assert "age_years" not in observation
    assert "body_effects" not in observation
    assert "hidden_role" not in observation

    for item in observation["visible_objects"]:
        assert "hidden_role" not in item
        assert "body_effects" not in item
        assert "world_effects" not in item


def test_same_movement_costs_more_for_heavier_body():
    engine = BodyEngine(BodyConfig(reference_mass_kg=40.0))
    light = BodyState(mass_kg=30.0, fatigue=0.1, damage=0.0)
    heavy = BodyState(mass_kg=90.0, fatigue=0.1, damage=0.0)

    light_cost = engine.movement_cost(light, distance=1.0)
    heavy_cost = engine.movement_cost(heavy, distance=1.0)

    assert abs(heavy_cost["energy_delta"]) > abs(light_cost["energy_delta"])
    assert heavy_cost["effort"] > light_cost["effort"]


def test_exogenous_event_receipt_is_observer_only():
    event = ScheduledExogenousEvent(
        event_id="EXO-RELOCATE-1",
        effective_tick=2,
        kind=ExogenousEventKind.RELOCATE_OBJECT,
        parameters={
            "object_id": "OBJ-17",
            "position": [8, 6],
        },
    )
    world = OrganismWorld(
        world_config=default_organism_world_config(
            exogenous_events=(event,),
        )
    )
    engine = _engine(world)

    first = engine.step(
        actions={"A001": Action("WAIT")}
    )
    second = engine.step(
        actions={"A001": Action("WAIT")}
    )

    obs = second.observations["A001"].data
    assert "event_id" not in str(obs)
    assert "RELOCATE_OBJECT" not in str(obs)

    truth = second.state_after.world.variables
    receipts = truth["observer_receipts"]["exogenous_events"]
    assert receipts
    assert receipts[-1]["event_id"] == "EXO-RELOCATE-1"
    assert receipts[-1]["kind"] == "RELOCATE_OBJECT"


def test_exogenous_event_occurs_regardless_of_agent_action():
    event = ScheduledExogenousEvent(
        event_id="EXO-DAMAGE-1",
        effective_tick=1,
        kind=ExogenousEventKind.DAMAGE_ORGANISM,
        parameters={"damage_delta": 0.2},
    )

    outcomes = []
    for action in ("WAIT", "USE:OBJ-04"):
        world = OrganismWorld(
            world_config=default_organism_world_config(
                exogenous_events=(event,),
            )
        )
        engine = _engine(world)
        result = engine.step(
            actions={"A001": Action(action)}
        )
        body = result.state_after.world.variables["bodies"]["A001"]
        receipts = result.state_after.world.variables[
            "observer_receipts"
        ]["exogenous_events"]
        outcomes.append((body["damage"], receipts[-1]["event_id"]))

    assert outcomes[0][0] == outcomes[1][0] == 0.2
    assert outcomes[0][1] == outcomes[1][1] == "EXO-DAMAGE-1"


def test_developmental_history_separates_experienced_effects_from_truth():
    world = OrganismWorld()
    engine = _engine(world)
    result = engine.step(
        actions={"A001": Action("USE:OBJ-04")}
    )

    history = result.state_after.world.variables["developmental_history"]
    assert len(history) == 1
    row = history[0]
    assert "experienced_effects" in row
    assert "body_truth_before" in row
    assert "body_truth_after" in row

    observation = world.observe(
        result.state_after.world,
        "A001",
    ).data
    assert observation["last_experienced_effects"] == row["experienced_effects"]
    assert "body_truth_after" not in observation


def test_random_exogenous_histories_can_diverge_by_seed():
    config = default_organism_world_config(
        random_event_rate=0.25,
    )

    logs = []
    for seed in (11, 29):
        world = OrganismWorld(world_config=config)
        engine = _engine(world, seed=seed)
        for _ in range(20):
            engine.step(
                actions={"A001": Action("WAIT")}
            )
        logs.append(
            deepcopy(
                engine.state.world.variables["world"]["exogenous_event_log"]
            )
        )

    assert logs[0] != logs[1]


def test_whole_organism_psyche_runs_without_body_truth_in_mechanism_state():
    world = OrganismWorld()
    engine = _engine(world)
    engine.run(20)

    psyche = (
        engine.state.agents["A001"]
        .mechanism_states["PSYCHE-SINGLE-ORGANISM-V03"]["psyche"]
    )

    assert "interoceptive_model" in psyche["internal"]
    assert "mass_kg" not in str(psyche)
    assert "hidden_role" not in str(psyche)
    assert len(psyche["memory"]["episodes"]) > 0


def test_delayed_outcome_is_experienced_later_without_causal_label():
    config = default_organism_world_config()
    config = type(config)(
        width=config.width,
        height=config.height,
        vision_radius=config.vision_radius,
        blocked=config.blocked,
        terrain_factors=config.terrain_factors,
        objects=config.objects,
        exogenous_events=config.exogenous_events,
        random_event_rate=config.random_event_rate,
        random_event_kinds=config.random_event_kinds,
        causal_reliability=config.causal_reliability,
        outcome_delay_ticks=2,
    )
    world = OrganismWorld(world_config=config)
    engine = _engine(world)

    engine.step(actions={"A001": Action("USE:OBJ-04")})
    engine.step(actions={"A001": Action("WAIT")})
    third = engine.step(actions={"A001": Action("WAIT")})

    receipts = third.state_after.world.variables[
        "observer_receipts"
    ]["delayed_effects"]
    assert receipts
    assert receipts[-1]["source_action"] == "USE:OBJ-04"
    assert receipts[-1]["effective_tick"] == 3

    observation = world.observe(
        third.state_after.world,
        "A001",
    ).data
    assert "source_action" not in str(
        observation["last_experienced_effects"]
    )
    assert observation["last_action"] == "WAIT"


def test_identical_architecture_diverges_across_objective_world_layouts():
    action_sequences = []
    for layout in ("near", "distributed"):
        world = OrganismWorld(
            world_config=default_organism_world_config(
                resource_layout=layout,
            )
        )
        engine = _engine(world, seed=17)
        sequence = []
        for _ in range(16):
            result = engine.step()
            sequence.append(
                result.actions["A001"].kind
            )
        action_sequences.append(sequence)

    assert action_sequences[0] != action_sequences[1]
