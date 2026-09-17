from __future__ import annotations

import sys
from pathlib import Path

from mechanistic_mind.agent import Agent
from mechanistic_mind.core import Engine
from mechanistic_mind.experiments import CompressionConfig, ExperienceCompressionMechanism, MemoryMode
from mechanistic_mind.experiments.experience_compression import (
    build_retrieval_cue, perceptual_features, perceptual_mismatch,
)
from mechanistic_mind.mechanisms import MechanismRegistry

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "worlds"))
from contextual_object_ecology_v034 import ContextualObjectEcologyWorld


def test_multimodal_percept_is_lawful_and_compact():
    world = ContextualObjectEcologyWorld()
    observation = world.observe(world.state, "A001").data
    context = observation["perceptual_context"]
    assert {"visual", "physical_field", "proprioceptive", "interoceptive"} <= set(context["modalities"])
    assert len(context["fragments"]) <= 24
    encoded = str(context).lower()
    assert "hidden_role" not in encoded
    assert "body_effects" not in encoded
    assert "world_effects" not in encoded


def test_cross_modal_features_do_not_enumerate_combinations():
    cue = build_retrieval_cue({"perceptual_context": {"modalities": {"visual": True, "tactile": True}, "fragments": [{"modality": "visual", "x": 1}, {"modality": "tactile", "x": 2}]}})
    features = perceptual_features(cue, 24)
    assert len(features) == 4
    assert all("visual+tactile" not in row for row in features)


def test_unknown_is_not_maximum_mismatch():
    assert perceptual_mismatch((), ()) == 0.0
    assert perceptual_mismatch(("a",), ("a",)) == 0.0
    assert perceptual_mismatch(("a",), ("b",)) == 1.0


def test_todo4_activation_is_bounded_and_does_not_force_move():
    config = CompressionConfig(mode=MemoryMode.COMPRESSED, exploration_gain=0.0, perceptual_dynamics_enabled=True, perceptual_activation_decay=0.5)
    mechanism = ExperienceCompressionMechanism(config)
    registry = MechanismRegistry(); registry.register(mechanism)
    engine = Engine(world=ContextualObjectEcologyWorld(), agents={"A001": Agent("A001")}, seed=17, mechanisms=registry)
    for _ in range(80):
        engine.step()
        memory = engine.state.agents["A001"].mechanism_states[mechanism.mechanism_id]["memory"]
        assert 0.0 <= memory["perceptual_activation"] <= 1.0
    assert len(memory["episodes"]) <= 64
    assert len(memory["patterns"]) <= 256
    # Activation is absent from the direct outcome-value equation and the
    # exploration term is explicitly zero in this condition.
    assert config.exploration_gain == 0.0


def test_calibrated_physiology_is_finite_but_longer_than_legacy():
    calibrated = ContextualObjectEcologyWorld()
    legacy = ContextualObjectEcologyWorld.legacy_physiology()
    assert calibrated.body_config.basal_energy_drain_per_day < legacy.body_config.basal_energy_drain_per_day
    assert calibrated.ambient_energy_cost < legacy.ambient_energy_cost
