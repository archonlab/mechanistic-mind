from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "worlds"))

from mechanistic_mind.agent import Action
from mechanistic_mind.core import DeterministicRandom
from mechanistic_mind.world_engine import (
    ObjectiveWorldEngine,
    observation_contains_forbidden,
)
from contextual_object_ecology_v034 import (
    dynamic_contextual_object_config,
    static_contextual_object_config,
)


def test_wait_advances_autonomous_in_dynamic_not_static():
    dyn = ObjectiveWorldEngine(dynamic_contextual_object_config(17))
    stat = ObjectiveWorldEngine(static_contextual_object_config(17))
    d_state = dyn.initial_state(start_position=(15, 16))
    s_state = stat.initial_state(start_position=(15, 16))
    d_kinds = []
    s_kinds = []
    for _ in range(12):
        d_res = dyn.transition_action(
            d_state, agent_id="A001", action=Action.wait(), rng=DeterministicRandom(17)
        )
        d_state = d_res.state
        d_kinds.extend(d_res.action_receipt.get("autonomous_update_kinds") or [])
        s_res = stat.transition_action(
            s_state, agent_id="A001", action=Action.wait(), rng=DeterministicRandom(17)
        )
        s_state = s_res.state
        s_kinds.extend(s_res.action_receipt.get("autonomous_update_kinds") or [])
    assert d_kinds, "dynamic world must produce autonomous updates during WAIT"
    assert s_kinds == []


def test_autonomous_config_not_in_observation():
    eng = ObjectiveWorldEngine(dynamic_contextual_object_config(23))
    state = eng.initial_state(start_position=(15, 16))
    for _ in range(6):
        state = eng.transition_action(
            state, agent_id="A001", action=Action.wait(), rng=DeterministicRandom(23)
        ).state
    obs = eng.local_observation(state, agent_id="A001")
    assert not observation_contains_forbidden(obs)
    for item in obs.get("visible_objects") or []:
        assert "autonomous" not in item
        assert "motion_pattern" not in item


def test_deterministic_autonomous_trajectory():
    eng = ObjectiveWorldEngine(dynamic_contextual_object_config(41))
    def trajectory(seed: int):
        state = eng.initial_state(start_position=(15, 16))
        path = []
        rng = DeterministicRandom(seed)
        for _ in range(15):
            result = eng.transition_action(
                state, agent_id="A001", action=Action.wait(), rng=rng
            )
            state = result.state
            path.append(
                tuple(
                    sorted(
                        (oid, tuple(rec["position"]))
                        for oid, rec in state["objects"].items()
                        if isinstance(rec, dict)
                    )
                )
            )
        return path
    assert trajectory(41) == trajectory(41)


def test_periodic_route_moves_without_agent_action():
    from mechanistic_mind.world_engine.models import ObjectiveObject, WorldEngineConfig

    obj = ObjectiveObject(
        "OBJ-M",
        (2, 2),
        autonomous={
            "enabled": True,
            "motion": {
                "pattern": "PERIODIC_ROUTE",
                "period_ticks": 1,
                "route": [[2, 2], [3, 2], [3, 3], [2, 3]],
            },
        },
    )
    cfg = WorldEngineConfig(
        width=8,
        height=8,
        vision_radius=5,
        blocked=(),
        objects=(obj,),
        autonomous_dynamics_enabled=True,
    )
    eng = ObjectiveWorldEngine(cfg)
    state = eng.initial_state(start_position=(0, 0))
    positions = [tuple(state["objects"]["OBJ-M"]["position"])]
    for _ in range(4):
        state = eng.transition_action(
            state, agent_id="A001", action=Action.wait(), rng=DeterministicRandom(7)
        ).state
        positions.append(tuple(state["objects"]["OBJ-M"]["position"]))
    assert len(set(positions)) > 1
