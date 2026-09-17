"""MM-ECO-1 living signal ecology — world plumbing tests (organism frozen)."""
from __future__ import annotations

from copy import deepcopy

from mechanistic_mind.agent import Action
from mechanistic_mind.body.embodied_integration import default_embodied_integration_config
from mechanistic_mind.core import DeterministicRandom
from mechanistic_mind.world_engine.perception import passive_wave_signals
from worlds.living_signal_ecology_v01 import (
    ABSENCE_DELAY_TICKS,
    HORIZON,
    RESIDENCE_TICKS,
    SOURCE_ID,
    SOURCE_ROUTE,
    make_living_ecology_world,
    source_present,
    source_record,
)


def test_mm_int1_config_unchanged():
    w = make_living_ecology_world()
    assert w.body_config.embodied_integration_config == default_embodied_integration_config()


def test_source_emits_passive_wave_when_present():
    w = make_living_ecology_world()
    st = deepcopy(w.state)
    world = st.variables["world"]
    waves = passive_wave_signals(agent_position=(4, 3), objects=world["objects"], clock=0)
    assert any(float(x.get("amplitude", 0)) > 0 for x in waves)


def test_wave_changes_with_geometry():
    w = make_living_ecology_world()
    st = deepcopy(w.state)
    world = st.variables["world"]
    near = passive_wave_signals(agent_position=(2, 2), objects=world["objects"], clock=0)
    far = passive_wave_signals(agent_position=(8, 6), objects=world["objects"], clock=0)
    a_near = max((float(x["amplitude"]) for x in near), default=0.0)
    a_far = max((float(x["amplitude"]) for x in far), default=0.0)
    assert a_near > a_far


def test_wave_absent_when_source_absent():
    w = make_living_ecology_world()
    st = deepcopy(w.state)
    aid = w.agent_id
    rng = DeterministicRandom(7)
    # advance past residence
    for _ in range(RESIDENCE_TICKS + 2):
        st = w.transition(st, {aid: Action(kind="WAIT")}, rng)
    assert source_present(st) is False
    world = st.variables["world"]
    waves = passive_wave_signals(agent_position=(4, 3), objects=world["objects"], clock=99)
    assert waves == [] or all(float(x.get("amplitude", 0)) == 0 for x in waves)


def test_wait_does_not_freeze_lifecycle():
    w = make_living_ecology_world()
    st = deepcopy(w.state)
    aid = w.agent_id
    rng = DeterministicRandom(20260913)
    seen_absent = False
    seen_reappear = False
    was_absent = False
    for _ in range(RESIDENCE_TICKS + ABSENCE_DELAY_TICKS + 5):
        st = w.transition(st, {aid: Action(kind="WAIT")}, rng)
        present = source_present(st)
        if not present:
            seen_absent = True
            was_absent = True
        if was_absent and present:
            seen_reappear = True
            break
    assert seen_absent and seen_reappear


def test_relocation_follows_route():
    w = make_living_ecology_world()
    st = deepcopy(w.state)
    aid = w.agent_id
    rng = DeterministicRandom(20260913)
    positions = []
    for _ in range(120):
        st = w.transition(st, {aid: Action(kind="WAIT")}, rng)
        if source_present(st):
            pos = tuple(source_record(st)["position"])
            if not positions or positions[-1] != pos:
                positions.append(pos)
    assert positions[0] == SOURCE_ROUTE[0]
    assert SOURCE_ROUTE[1] in positions


def test_wait_body_continues():
    w = make_living_ecology_world()
    st = deepcopy(w.state)
    aid = w.agent_id
    e0 = w._body_state(st, aid).energy_reserve
    for _ in range(8):
        st = w.transition(st, {aid: Action(kind="WAIT")}, DeterministicRandom(1))
    e1 = w._body_state(st, aid).energy_reserve
    assert e1 < e0


def test_contact_transfer_and_no_contact():
    w = make_living_ecology_world()
    st = deepcopy(w.state)
    aid = w.agent_id
    # no contact at start (agent 4,3 source 2,2)
    st1 = w.transition(st, {aid: Action(kind="WAIT")}, DeterministicRandom(1))
    assert w._body_state(st1, aid).last_intake_transfer == 0.0
    # force same cell
    st2 = deepcopy(w.state)
    st2.variables["world"]["agent_positions"][aid] = list(source_record(st2)["position"])
    st2 = w.transition(st2, {aid: Action(kind="WAIT")}, DeterministicRandom(2))
    body = w._body_state(st2, aid)
    assert body.last_intake_transfer > 0.0
    assert sum(body.internal_materials.values()) > 0.0


def test_signal_only_no_transfer():
    w = make_living_ecology_world(contact_transfer=False)
    st = deepcopy(w.state)
    aid = w.agent_id
    st.variables["world"]["agent_positions"][aid] = list(source_record(st)["position"])
    st = w.transition(st, {aid: Action(kind="WAIT")}, DeterministicRandom(2))
    assert w._body_state(st, aid).last_intake_transfer == 0.0


def test_world_receptors_respond_to_visible_source():
    w = make_living_ecology_world()
    # place agent adjacent/same as source within vision
    st = deepcopy(w.state)
    aid = w.agent_id
    spos = list(source_record(st)["position"])
    st.variables["world"]["agent_positions"][aid] = spos
    st = w.transition(st, {aid: Action(kind="WAIT")}, DeterministicRandom(4))
    emb = w._body_state(st, aid).embodied_integration
    assert emb is not None
    # visible count receptor should differ from empty
    st2 = deepcopy(w.state)
    # move far and wait until absent? simpler: compare with source absent state
    for _ in range(RESIDENCE_TICKS + 2):
        st2 = w.transition(st2, {aid: Action(kind="WAIT")}, DeterministicRandom(9))
    # force agent away
    st2.variables["world"]["agent_positions"][aid] = [0, 0]
    st2 = w.transition(st2, {aid: Action(kind="WAIT")}, DeterministicRandom(10))
    emb_abs = w._body_state(st2, aid).embodied_integration
    assert emb["last_world_receptors"] != emb_abs["last_world_receptors"] or emb["nervous"]["channels"] != emb_abs["nervous"]["channels"]


def test_no_source_coords_in_embodied_state():
    w = make_living_ecology_world()
    st = deepcopy(w.state)
    aid = w.agent_id
    st = w.transition(st, {aid: Action(kind="WAIT")}, DeterministicRandom(1))
    emb = w._body_state(st, aid).embodied_integration
    blob = str(emb)
    assert "SOURCE_A" not in blob
    assert "scheduled_reappear" not in blob
    assert "hidden_next_position" not in blob


def test_natural_acquisition_runs():
    w = make_living_ecology_world()
    st = deepcopy(w.state)
    aid = w.agent_id
    for _ in range(6):
        st = w.transition(st, {aid: Action(kind="WAIT")}, DeterministicRandom(11))
    rel = (w._body_state(st, aid).embodied_integration or {}).get("relation") or {}
    assert int(rel.get("update_count", 0)) >= 1


def test_memory_ablation_control():
    w = make_living_ecology_world(ablate_memory=True)
    st = deepcopy(w.state)
    aid = w.agent_id
    for _ in range(6):
        st = w.transition(st, {aid: Action(kind="WAIT")}, DeterministicRandom(11))
    rel = (w._body_state(st, aid).embodied_integration or {}).get("relation") or {}
    assert int(rel.get("update_count", 0)) == 0


def test_horizon_constant():
    assert HORIZON >= 4 * (RESIDENCE_TICKS + ABSENCE_DELAY_TICKS)


def test_serialization_source_state():
    w = make_living_ecology_world()
    st = deepcopy(w.state)
    aid = w.agent_id
    for _ in range(RESIDENCE_TICKS + 3):
        st = w.transition(st, {aid: Action(kind="WAIT")}, DeterministicRandom(20260913))
    # roundtrip world variables
    import json
    payload = json.loads(json.dumps(st.variables, default=list))
    assert SOURCE_ID in payload["world"]["objects"]
    assert payload["world"]["objects"][SOURCE_ID]["existence"]["present"] is False
