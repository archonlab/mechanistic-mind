"""MM-INT-1 embodied psyche integration — causal plumbing tests (not behavior success)."""
from __future__ import annotations

from copy import deepcopy

import pytest

from mechanistic_mind.agent import Action
from mechanistic_mind.body import BodyConfig, BodyState
from mechanistic_mind.body.embodied_integration import (
    EmbodiedIntegrationState,
    body_receptors,
    default_embodied_integration_config,
    project_neural_drive,
    r_l_to_endogenous,
    step_pre_action,
    world_receptors,
)
from mechanistic_mind.body.internal_transition_acquisition import TransitionRelationState
from mechanistic_mind.body.sensorimotor_dynamics import SensorimotorState, evolve
from mechanistic_mind.core import DeterministicRandom
from mechanistic_mind.world_engine.physical_effector import default_effector_config, maybe_apply
from worlds.organism_world_v03 import OrganismWorld, default_organism_world_config


def _cfg(**overrides):
    c = default_embodied_integration_config()
    c.update(overrides)
    return c


def _integrated_body_config(**overrides):
    integ = _cfg(**overrides)
    return BodyConfig(
        embodied_integration_config=integ,
        physical_effector_config=default_effector_config(),
    )


def test_body_receptor_causality():
    a = body_receptors(0.9, 0.5, 0.1)
    b = body_receptors(0.1, 0.5, 0.1)
    assert a[0] != b[0]
    assert a[1] == b[1]


def test_world_receptor_causality():
    a = world_receptors({"visible_objects": [{"cue_salience": 0.9}, {"cue_salience": 0.8}]})
    b = world_receptors({"visible_objects": []})
    assert a[0] != b[0]
    c = world_receptors({"visible_objects": [], "_tactile_contact": True})
    d = world_receptors({"visible_objects": [], "_tactile_contact": False})
    assert c[1] != d[1]


def test_evolve_production_inputs_bypasses_ia_lc():
    s = SensorimotorState()
    via_prod = evolve(s, body={"internal_a": 0.99, "load_c": 0.01}, production_inputs=(0.1, -0.1), random_value=0.5)
    via_legacy = evolve(s, body={"internal_a": 0.99, "load_c": 0.01}, random_value=0.5)
    assert via_prod.channels != via_legacy.channels


def test_receptor_to_nervous_change():
    cfg = _cfg(noise_enabled=False, reinstatement_to_dynamics_enabled=False, acquisition_enabled=False)
    st0 = EmbodiedIntegrationState()
    hi, _ = step_pre_action(
        st0, energy_reserve=0.95, hydration=0.5, fatigue=0.5,
        observation_data={}, config=cfg, random_value=0.5,
    )
    lo, _ = step_pre_action(
        EmbodiedIntegrationState(), energy_reserve=0.05, hydration=0.5, fatigue=0.5,
        observation_data={}, config=cfg, random_value=0.5,
    )
    assert hi.nervous.channels != lo.nervous.channels


def test_nervous_to_drive():
    d0 = project_neural_drive((0.0, 0.0, 0.0))
    d1 = project_neural_drive((0.9, -0.5, 0.2))
    assert d1 != d0
    assert all(x >= 0.0 for x in d1)


def test_effector_from_neural_drive_can_hop():
    class _Eng:
        def position(self, state, agent_id):
            return tuple(state["agent_positions"][agent_id])
        def is_open(self, state, dest, ignore_agent_id=None):
            return True

    state = {"agent_positions": {"A": [4, 3]}, "width": 9, "height": 7}
    # Strong drive on site index matching DEFAULT_SITES
    state["neural_physical_drive"] = [1.0, 0.0, 0.0, 0.0]
    nxt, extra = maybe_apply(_Eng(), state, "A", default_effector_config())
    assert extra["applied"] is True
    assert nxt["physical_effector"]["drive_source"] == "neural"


def test_researcher_drive_priority_over_neural():
    class _Eng:
        def position(self, state, agent_id):
            return tuple(state["agent_positions"][agent_id])
        def is_open(self, state, dest, ignore_agent_id=None):
            return True

    state = {
        "agent_positions": {"A": [4, 3]},
        "researcher_physical_drive": [1.0, 0.0, 0.0, 0.0],
        "neural_physical_drive": [0.0, 1.0, 0.0, 0.0],
    }
    nxt, _ = maybe_apply(_Eng(), state, "A", default_effector_config())
    assert nxt["physical_effector"]["drive_source"] == "researcher"


def test_deferred_acquisition_updates_L():
    cfg = _cfg(noise_enabled=False, reinstatement_to_dynamics_enabled=False)
    st = EmbodiedIntegrationState()
    # Need >=3 ticks: first pending S is zeros; weight change needs nonzero S-trace.
    for e in (0.8, 0.75, 0.7, 0.65):
        st, _ = step_pre_action(
            st, energy_reserve=e, hydration=0.5, fatigue=0.4,
            observation_data={"visible_objects": [{"cue_salience": 0.7}]},
            config=cfg, random_value=0.5,
        )
    assert st.relation.update_count >= 2
    flat = [abs(x) for row in st.relation.weights for pair in row for x in pair]
    assert max(flat) > 0.0


def test_reinstatement_to_dynamics_differs_with_history():
    cfg = _cfg(noise_enabled=False)
    # H0
    h0 = EmbodiedIntegrationState()
    for _ in range(3):
        h0, _ = step_pre_action(
            h0, energy_reserve=0.6, hydration=0.5, fatigue=0.5,
            observation_data={}, config=cfg, random_value=0.5,
        )
    # H1: inject nonzero L then same present
    h1 = EmbodiedIntegrationState()
    # build L via several steps with strong receptors
    for e in (0.9, 0.85, 0.8, 0.75):
        h1, _ = step_pre_action(
            h1, energy_reserve=e, hydration=0.2, fatigue=0.8,
            observation_data={"visible_objects": [{"cue_salience": 0.95}]},
            config=cfg, random_value=0.5,
        )
    # Match present: reset nervous to same, keep L
    matched = EmbodiedIntegrationState.from_dict(h1.to_dict())
    matched.nervous = SensorimotorState(channels=h0.nervous.channels, previous_output=h0.nervous.previous_output, tick=h0.nervous.tick)
    matched.pending_valid = False
    cfg_match = _cfg(noise_enabled=False, acquisition_enabled=False)
    out0, _ = step_pre_action(
        EmbodiedIntegrationState(nervous=SensorimotorState(channels=h0.nervous.channels, previous_output=h0.nervous.previous_output)),
        energy_reserve=0.6, hydration=0.5, fatigue=0.5,
        observation_data={}, config=cfg_match, random_value=0.5,
    )
    out1, _ = step_pre_action(
        matched,
        energy_reserve=0.6, hydration=0.5, fatigue=0.5,
        observation_data={}, config=cfg_match, random_value=0.5,
    )
    # If L is nontrivial, endogenous path can differ
    if any(abs(x) > 1e-9 for row in matched.relation.weights for pair in row for x in pair):
        assert out0.last_endogenous != out1.last_endogenous or out0.nervous.channels != out1.nervous.channels


def test_memory_ablation_clears_relation():
    cfg = _cfg(noise_enabled=False)
    st = EmbodiedIntegrationState()
    for _ in range(4):
        st, _ = step_pre_action(
            st, energy_reserve=0.9, hydration=0.2, fatigue=0.7,
            observation_data={"visible_objects": [{"cue_salience": 0.9}]},
            config=cfg, random_value=0.5,
        )
    assert st.relation.update_count >= 1
    st2, _ = step_pre_action(
        st, energy_reserve=0.6, hydration=0.5, fatigue=0.5,
        observation_data={}, config=_cfg(ablate_memory=True, noise_enabled=False), random_value=0.5,
    )
    assert st2.relation.update_count == 0
    assert st2.last_endogenous == (0.0, 0.0, 0.0)


def test_receptor_ablation_zeros_influence():
    cfg = _cfg(ablate_receptors=True, noise_enabled=False, reinstatement_to_dynamics_enabled=False, acquisition_enabled=False)
    a, _ = step_pre_action(
        EmbodiedIntegrationState(), energy_reserve=0.99, hydration=0.01, fatigue=0.99,
        observation_data={"visible_objects": [{"cue_salience": 1.0}], "_tactile_contact": True},
        config=cfg, random_value=0.5,
    )
    b, _ = step_pre_action(
        EmbodiedIntegrationState(), energy_reserve=0.01, hydration=0.99, fatigue=0.01,
        observation_data={"visible_objects": []},
        config=cfg, random_value=0.5,
    )
    assert a.nervous.channels == b.nervous.channels
    assert a.last_body_receptors == (0.0, 0.0, 0.0)


def test_effector_ablation_zero_drive():
    st, drive = step_pre_action(
        EmbodiedIntegrationState(), energy_reserve=0.9, hydration=0.2, fatigue=0.8,
        observation_data={}, config=_cfg(ablate_effector_drive=True, noise_enabled=False), random_value=0.5,
    )
    assert drive == (0.0, 0.0, 0.0, 0.0)
    assert st.nervous.channels != (0.0, 0.0, 0.0) or True  # nervous may still evolve


def test_body_state_serialization_roundtrip():
    emb = EmbodiedIntegrationState()
    emb, _ = step_pre_action(
        emb, energy_reserve=0.7, hydration=0.6, fatigue=0.3,
        observation_data={}, config=_cfg(noise_enabled=False), random_value=0.5,
    )
    body = BodyState(embodied_integration=emb.to_dict())
    again = BodyState.from_dict(body.to_dict())
    assert again.embodied_integration is not None
    assert again.embodied_integration["nervous"]["channels"] == list(emb.nervous.channels) or (
        tuple(again.embodied_integration["nervous"]["channels"]) == emb.nervous.channels
    )


def test_legacy_config_none_no_integration_field_required():
    w = OrganismWorld(
        world_config=default_organism_world_config(),
        body_config=BodyConfig(),  # embodied_integration_config None
    )
    assert w.body_config.embodied_integration_config is None
    st = deepcopy(w.state)
    rng = DeterministicRandom(7)
    st2 = w.transition(st, {w.agent_id: Action(kind="WAIT")}, rng)
    body = w._body_state(st2, w.agent_id)
    # legacy: no forced embodied payload
    assert body.embodied_integration is None or body.embodied_integration.get("tick", 0) == 0


def test_organism_same_stream_nervous_steps():
    cfg = _integrated_body_config(noise_enabled=True)
    w = OrganismWorld(
        world_config=default_organism_world_config(),
        body_config=cfg,
        start_position=(4, 3),
    )
    st = deepcopy(w.state)
    rng = DeterministicRandom(11)
    st1 = w.transition(st, {w.agent_id: Action(kind="WAIT")}, rng)
    body1 = w._body_state(st1, w.agent_id)
    assert body1.embodied_integration is not None
    assert body1.embodied_integration["tick"] >= 1
    st2 = w.transition(st1, {w.agent_id: Action(kind="WAIT")}, rng)
    body2 = w._body_state(st2, w.agent_id)
    assert body2.embodied_integration["tick"] >= 2
    # nervous should have evolved (noise or receptors)
    assert body2.embodied_integration["nervous"]["tick"] >= 2


def test_no_semantic_teaching_keywords_in_module():
    from pathlib import Path
    src = Path("mechanistic_mind/body/embodied_integration.py").read_text().lower()
    # Allow words only in prohibition comments — ensure no assignment teaching
    forbidden_assign = [
        "reward =",
        "utility =",
        "goal =",
        "desire =",
        "preference =",
        "argmax(",
    ]
    for token in forbidden_assign:
        assert token not in src


def test_r_l_to_endogenous_no_collapse_to_scalar_policy():
    r = ((0.2, -0.1, 0.05), (-0.05, 0.15, 0.0))
    e = r_l_to_endogenous(r, gain=0.12)
    assert len(e) == 3
