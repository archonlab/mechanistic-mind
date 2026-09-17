"""MM-ECO-1 rich autonomous signal ecology tests."""
from __future__ import annotations
from copy import deepcopy
from mechanistic_mind.agent import Action
from mechanistic_mind.body.embodied_integration import default_embodied_integration_config
from mechanistic_mind.core import DeterministicRandom
from mechanistic_mind.world_engine.perception import passive_wave_signals
from worlds.rich_autonomous_signal_ecology_v01 import (
    HORIZON, SEEDS, make_rich_ecology_world, object_present, object_record,
)

def test_organism_freeze():
    w = make_rich_ecology_world()
    assert w.body_config.embodied_integration_config == default_embodied_integration_config()

def test_multiple_objects_and_signals():
    w = make_rich_ecology_world()
    st = deepcopy(w.state)
    objs = st.variables["world"]["objects"]
    assert set(objs) >= {"SRC_A", "SRC_B", "OBJ_C", "OBJ_D"}
    waves = passive_wave_signals(agent_position=(4, 3), objects=objs, clock=0)
    assert len(waves) >= 1

def test_wave_geometry():
    w = make_rich_ecology_world()
    objs = deepcopy(w.state).variables["world"]["objects"]
    near = max((float(x["amplitude"]) for x in passive_wave_signals(agent_position=(2, 2), objects=objs, clock=0)), default=0)
    far = max((float(x["amplitude"]) for x in passive_wave_signals(agent_position=(8, 6), objects=objs, clock=0)), default=0)
    assert near > far

def test_wait_lifecycle_and_mover():
    w = make_rich_ecology_world()
    st = deepcopy(w.state)
    aid = w.agent_id
    rng = DeterministicRandom(17)
    c_pos = set()
    saw_absent = False
    for _ in range(50):
        st = w.transition(st, {aid: Action(kind="WAIT")}, rng)
        rec = object_record(st, "OBJ_C")
        if rec and rec.get("position"):
            c_pos.add(tuple(rec["position"]))
        if not object_present(st, "SRC_A"):
            saw_absent = True
    assert len(c_pos) >= 2
    assert saw_absent

def test_wait_body_and_n():
    w = make_rich_ecology_world()
    st = deepcopy(w.state)
    aid = w.agent_id
    e0 = w._body_state(st, aid).energy_reserve
    for _ in range(10):
        st = w.transition(st, {aid: Action(kind="WAIT")}, DeterministicRandom(1))
    body = w._body_state(st, aid)
    assert body.energy_reserve < e0
    assert (body.embodied_integration or {}).get("tick", 0) >= 10

def test_contact_src_a_only():
    w = make_rich_ecology_world()
    st = deepcopy(w.state)
    aid = w.agent_id
    # no contact
    st1 = w.transition(deepcopy(st), {aid: Action(kind="WAIT")}, DeterministicRandom(1))
    assert w._body_state(st1, aid).last_intake_transfer == 0.0
    # SRC_A contact
    st2 = deepcopy(st)
    st2.variables["world"]["agent_positions"][aid] = list(object_record(st2, "SRC_A")["position"])
    st2 = w.transition(st2, {aid: Action(kind="WAIT")}, DeterministicRandom(2))
    assert w._body_state(st2, aid).last_intake_transfer > 0.0

def test_signal_poor_no_emission_waves():
    w = make_rich_ecology_world(emission_enabled=False)
    objs = deepcopy(w.state).variables["world"]["objects"]
    waves = passive_wave_signals(agent_position=(2, 2), objects=objs, clock=0)
    assert waves == [] or all(float(x.get("amplitude", 0)) == 0 for x in waves)

def test_memory_and_reinstatement_ablation():
    w = make_rich_ecology_world(ablate_memory=True)
    st = deepcopy(w.state)
    aid = w.agent_id
    for _ in range(8):
        st = w.transition(st, {aid: Action(kind="WAIT")}, DeterministicRandom(3))
    assert int((w._body_state(st, aid).embodied_integration or {}).get("relation", {}).get("update_count", 0)) == 0
    w2 = make_rich_ecology_world(ablate_reinstatement=True)
    st2 = deepcopy(w2.state)
    for _ in range(8):
        st2 = w2.transition(st2, {aid: Action(kind="WAIT")}, DeterministicRandom(3))
    emb = w2._body_state(st2, aid).embodied_integration or {}
    assert emb.get("last_endogenous") == [0.0, 0.0, 0.0] or emb.get("last_endogenous") == (0.0, 0.0, 0.0)

def test_no_coord_leak_in_embodied():
    w = make_rich_ecology_world()
    st = deepcopy(w.state)
    aid = w.agent_id
    st = w.transition(st, {aid: Action(kind="WAIT")}, DeterministicRandom(1))
    blob = str(w._body_state(st, aid).embodied_integration)
    assert "SRC_A" not in blob and "scheduled_reappear" not in blob

def test_horizon_and_seeds():
    assert HORIZON >= 350
    assert len(SEEDS) == 5

def test_serialization_roundtrip_ecology():
    import json
    w = make_rich_ecology_world()
    st = deepcopy(w.state)
    aid = w.agent_id
    for _ in range(30):
        st = w.transition(st, {aid: Action(kind="WAIT")}, DeterministicRandom(17))
    payload = json.loads(json.dumps(st.variables, default=list))
    assert "SRC_A" in payload["world"]["objects"]
    assert "background_fields" in payload["world"]
