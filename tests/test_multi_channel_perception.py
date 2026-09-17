from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "worlds"))

from contextual_object_ecology_v034 import (  # noqa: E402
    contact_only_contextual_object_config,
    multi_channel_contextual_object_config,
)
from mechanistic_mind.agent import Action
from mechanistic_mind.body import BodyConfig, BodyEngine, BodyState
from mechanistic_mind.core.random import DeterministicRandom
from mechanistic_mind.world_engine import ObjectiveWorldEngine
from mechanistic_mind.world_engine.perception import (
    PERCEPTION_FORBIDDEN_KEYS,
    distant_structural_signals,
)


def test_four_channels_exist_in_multi_channel_mode() -> None:
    eng = ObjectiveWorldEngine(multi_channel_contextual_object_config(17))
    state = eng.initial_state(start_position=(16, 16))
    obs = eng.local_observation(state, agent_id="A001")
    channels = obs["physical_perception"]["channels"]
    assert set(channels) >= {
        "DISTANT_STRUCTURAL",
        "PASSIVE_WAVE",
        "ACTIVE_RETURN",
        "NEAR_CONTACT",
    }
    assert len(channels["DISTANT_STRUCTURAL"]) >= 1


def test_contact_only_hides_distant_and_passive() -> None:
    eng = ObjectiveWorldEngine(contact_only_contextual_object_config(17))
    state = eng.initial_state(start_position=(16, 16))
    obs = eng.local_observation(state, agent_id="A001")
    channels = obs["physical_perception"]["channels"]
    assert channels["DISTANT_STRUCTURAL"] == []
    assert channels["PASSIVE_WAVE"] == []
    assert channels["NEAR_CONTACT"]  # near still present


def test_distance_reduces_information_content() -> None:
    eng = ObjectiveWorldEngine(multi_channel_contextual_object_config(17))
    state = eng.initial_state(start_position=(16, 16))
    objects = eng._objects(state)
    near = distant_structural_signals(
        agent_position=(16, 16), objects=objects, radius=8
    )
    far = distant_structural_signals(
        agent_position=(0, 0), objects=objects, radius=8
    )
    assert near
    mean = lambda rows: sum(r["feature_count"] for r in rows) / len(rows)
    if far:
        assert mean(near) >= mean(far)


def test_emit_returns_without_object_ids() -> None:
    eng = ObjectiveWorldEngine(multi_channel_contextual_object_config(17))
    state = eng.initial_state(start_position=(16, 16))
    assert "EMIT" in eng.local_observation(state, agent_id="A001")["available_actions"]
    result = eng.transition_action(
        state,
        agent_id="A001",
        action=Action("EMIT"),
        rng=DeterministicRandom(17),
    )
    assert result.action_receipt.get("emit", {}).get("return_count", 0) >= 1
    obs = eng.local_observation(result.state, agent_id="A001")
    blob = json.dumps(obs["physical_perception"]["channels"])
    for key in PERCEPTION_FORBIDDEN_KEYS:
        assert f'"{key}"' not in blob
    assert obs["physical_perception"]["channels"]["ACTIVE_RETURN"]


def test_wait_recovery_bounded_and_optional() -> None:
    loaded = BodyState(activity_load=0.9, fatigue=0.55)
    on = BodyEngine(BodyConfig(recovery_dynamics_enabled=True)).transition(
        loaded.clone(), action=Action("WAIT"), distance=0.0
    )
    off = BodyEngine(BodyConfig(recovery_dynamics_enabled=False)).transition(
        loaded.clone(), action=Action("WAIT"), distance=0.0
    )
    assert on.state.fatigue < off.state.fatigue
    assert on.state.activity_load < 0.9
    assert on.state.consecutive_wait_ticks == 1
    # Long wait does not create unlimited improvement: recovery scales with load.
    state = on.state
    fatigues = [state.fatigue]
    for _ in range(40):
        state = BodyEngine(BodyConfig(recovery_dynamics_enabled=True)).transition(
            state, action=Action("WAIT"), distance=0.0
        ).state
        fatigues.append(state.fatigue)
    assert fatigues[-1] >= 0.0
    # After load drains, fatigue should stop falling from recovery alone
    # (passive gain may still raise it).
    assert state.activity_load < 0.05


def test_no_wait_reward_in_body_transition() -> None:
    # Sanity: WAIT never adds energy as a reward.
    engine = BodyEngine(BodyConfig(recovery_dynamics_enabled=True))
    before = BodyState(energy_reserve=0.5, activity_load=0.2)
    after = engine.transition(before, action=Action("WAIT"), distance=0.0).state
    assert after.energy_reserve <= before.energy_reserve
