import sys
from pathlib import Path

import pytest

from mechanistic_mind.agent import Action, Agent
from mechanistic_mind.core import DeterministicRandom, Engine
from mechanistic_mind.mechanisms import MechanismRegistry
from mechanistic_mind.observer import InMemorySink, PsychologyObserver
from mechanistic_mind.psyche import (
    PsycheState,
    SingleAgentPsycheV01,
    build_life_modules,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "worlds"))

from environmental_perturbations import (
    EnvironmentalPerturbationPack,
    PerturbationKind,
    PerturbedSingleAgentLifeWorld,
    ScheduledPerturbation,
    canonical_environmental_conditions,
)


def _event(kind, parameters, *, tick=2, pid="P-1"):
    return ScheduledPerturbation(
        perturbation_id=pid,
        effective_tick=tick,
        kind=kind,
        parameters=parameters,
    )


def test_perturbation_manifest_is_not_agent_observation():
    pack = canonical_environmental_conditions(effective_tick=10)["RELOCATION"]
    world = PerturbedSingleAgentLifeWorld(perturbation_pack=pack)
    observation = world.observe(world.state, "A001")
    assert "perturbation_pack" not in observation.data
    assert "perturbation_log" not in observation.data
    assert "ambient_load" not in observation.data


def test_relocation_has_exact_effective_tick_and_receipt():
    pack = EnvironmentalPerturbationPack(
        pack_id="TEST-RELOCATION",
        perturbations=(
            _event(
                PerturbationKind.RELOCATE_OBJECT,
                {"object_id": "OBJ-23", "position": [1, 5]},
                tick=2,
            ),
        ),
    )
    world = PerturbedSingleAgentLifeWorld(perturbation_pack=pack)
    rng = DeterministicRandom(17)

    state1 = world.transition(world.state, {"A001": Action("WAIT")}, rng)
    assert state1.variables["tick"] == 1
    assert state1.variables["objects"]["OBJ-23"]["position"] == [7, 5]
    assert state1.variables["perturbation_log"] == []

    state2 = world.transition(state1, {"A001": Action("WAIT")}, rng)
    assert state2.variables["tick"] == 2
    assert state2.variables["objects"]["OBJ-23"]["position"] == [1, 5]
    receipt = state2.variables["perturbation_log"][0]
    assert receipt["applied_after_tick"] == 1
    assert receipt["effective_tick"] == 2
    assert receipt["before"]["record"]["position"] == [7, 5]
    assert receipt["after"]["record"]["position"] == [1, 5]


def test_depleted_object_disappears_from_affordances_without_service_flag():
    pack = EnvironmentalPerturbationPack(
        pack_id="TEST-DEPLETION",
        perturbations=(
            _event(
                PerturbationKind.SET_OBJECT_ACTIVE,
                {"object_id": "OBJ-04", "active": False},
                tick=1,
            ),
        ),
    )
    world = PerturbedSingleAgentLifeWorld(perturbation_pack=pack)
    state1 = world.transition(
        world.state,
        {"A001": Action("WAIT")},
        DeterministicRandom(17),
    )
    observation = world.observe(state1, "A001")
    assert "USE:OBJ-04" not in observation.data["available_actions"]
    assert all(
        item.get("id") != "OBJ-04"
        for item in observation.data["visible_objects"]
    )
    assert "perturbation_log" not in observation.data


def test_outcome_noise_is_deterministic_and_starts_after_intervention():
    pack = EnvironmentalPerturbationPack(
        pack_id="TEST-NOISE",
        perturbations=(
            _event(
                PerturbationKind.SET_OUTCOME_NOISE,
                {
                    "object_id": "OBJ-04",
                    "amplitudes": {"energy_delta": 0.05},
                },
                tick=1,
            ),
        ),
    )

    observed = []
    for _ in range(2):
        world = PerturbedSingleAgentLifeWorld(perturbation_pack=pack)
        rng = DeterministicRandom(17)
        state1 = world.transition(
            world.state,
            {"A001": Action("USE:OBJ-04")},
            rng,
        )
        assert state1.variables["last_consequence"]["energy_delta"] == 0.16

        state2 = world.transition(
            state1,
            {"A001": Action("USE:OBJ-04")},
            rng,
        )
        observed.append(state2.variables["last_consequence"]["energy_delta"])
        assert state2.variables["last_environment_effects"]["outcome_noise"]

    assert observed[0] == observed[1]
    assert observed[0] != 0.16


def test_ambient_load_changes_experienced_consequence_only_after_effective_tick():
    pack = EnvironmentalPerturbationPack(
        pack_id="TEST-AMBIENT",
        perturbations=(
            _event(
                PerturbationKind.SET_AMBIENT_LOAD,
                {"load": {"hydration_delta": -0.02, "fatigue_delta": 0.01}},
                tick=1,
            ),
        ),
    )
    world = PerturbedSingleAgentLifeWorld(perturbation_pack=pack)
    rng = DeterministicRandom(17)

    state1 = world.transition(world.state, {"A001": Action("WAIT")}, rng)
    assert state1.variables["last_consequence"]["hydration_delta"] == 0.0

    state2 = world.transition(state1, {"A001": Action("WAIT")}, rng)
    assert state2.variables["last_consequence"]["hydration_delta"] == -0.02
    assert state2.variables["last_consequence"]["fatigue_delta"] == 0.0
    assert state2.variables["last_environment_effects"]["ambient_load"]


def test_shifted_outcome_changes_world_truth_without_announcement():
    pack = EnvironmentalPerturbationPack(
        pack_id="TEST-SHIFT",
        perturbations=(
            _event(
                PerturbationKind.SHIFT_OBJECT_OUTCOME,
                {
                    "object_id": "OBJ-31",
                    "delta": {"hydration_delta": -0.10},
                },
                tick=1,
            ),
        ),
    )
    world = PerturbedSingleAgentLifeWorld(perturbation_pack=pack)
    state1 = world.transition(
        world.state,
        {"A001": Action("WAIT")},
        DeterministicRandom(17),
    )
    assert (
        state1.variables["objects"]["OBJ-31"]["outcome"]["hydration_delta"]
        == pytest.approx(-0.15)
    )
    observation = world.observe(state1, "A001")
    assert "objects" not in observation.data
    assert "perturbation_log" not in observation.data


def _whole_psyche_actions(pack, ticks=30):
    sink = InMemorySink()
    registry = MechanismRegistry()
    registry.register(
        SingleAgentPsycheV01(
            modules=build_life_modules(),
            initial_state=PsycheState.initial_life_v01(),
        )
    )
    engine = Engine(
        world=PerturbedSingleAgentLifeWorld(
            perturbation_pack=pack
        ),
        agents={"A001": Agent(agent_id="A001")},
        seed=17,
        mechanisms=registry,
        observer=PsychologyObserver(sink),
    )
    engine.run(ticks)
    engine.close()
    return [record.actions["A001"]["kind"] for record in sink.records]


def test_matched_conditions_share_behavioral_prefix_before_intervention():
    conditions = canonical_environmental_conditions(effective_tick=20)
    control = _whole_psyche_actions(conditions["CONTROL"])
    relocated = _whole_psyche_actions(conditions["RELOCATION"])
    depleted = _whole_psyche_actions(conditions["DEPLETION"])

    assert control[:20] == relocated[:20]
    assert control[:20] == depleted[:20]
