
"""FULL EMBODIED PREDICTIVE MODEL — coverage + composite motor acceptance."""
from __future__ import annotations

from mechanistic_mind.physical_system import o_prime_history_bridge as ohb
from mechanistic_mind.physical_system import sensorimotor_consequence as smc
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig


def test_sensory_coverage_matches_accessible_allowlist():
    s = ObserverSession(SessionConfig(seed=5, evidence_mode="SEARCH_COMPACT"))
    s.apply_experiment({"seed": 5, "agent_count": 2})
    s.set_mechanism("sensorimotor_consequence_model", True)
    for mid in ("near_field_exteroception", "vestibular_proprioception", "oscillatory_signaling", "articulated_head"):
        try:
            s.set_mechanism(mid, True)
        except Exception:
            pass
    s.step()
    slot = s.runtime.slots[0]
    try:
        o = slot.agent_observation(foreign_bodies=[s.runtime.slots[1].body])
    except TypeError:
        o = slot.agent_observation()
    missing = sorted(set(o) - set(smc.SENSORY_CHANNELS))
    assert missing == [], f"accessible but not SMC allowlist: {missing}"
    assert len(smc.SENSORY_CHANNELS) == 39


def test_family_withhold_removes_only_that_family():
    store = smc.empty_store(enabled=True, families={"visual": False})
    assert not any(c.startswith("exo_") for c in store["channel_list"])
    assert "local.FIELD_A" in store["channel_list"]
    assert "body.B0" in store["channel_list"]


def _train(store, base, after, motor, n=4):
    for t in range(n):
        smc.update(store, tick=t, observation_t=base, motor=motor, observation_t1=after)


def test_motor_differentiation_loco_neck_emit_push():
    store = smc.empty_store(enabled=True)
    base = {k: 0.2 for k in smc.SENSORY_CHANNELS}
    cases = {
        "loco_N": ({"locomotion": "MOVE:N", "neck": "NONE", "oscillator": {}, "push": False}, {**base, "exo_0": 0.9}),
        "loco_E": ({"locomotion": "MOVE:E", "neck": "NONE", "oscillator": {}, "push": False}, {**base, "exo_0": 0.1}),
        "neck_L": ({"locomotion": "WAIT", "neck": "NECK_LEFT", "oscillator": {}, "push": False}, {**base, "prop_neck_0": 0.9}),
        "neck_R": ({"locomotion": "WAIT", "neck": "NECK_RIGHT", "oscillator": {}, "push": False}, {**base, "prop_neck_0": 0.1}),
        "emit": ({"locomotion": "WAIT", "neck": "NONE", "oscillator": {"emit_trigger": True, "frequency_delta": 0, "amplitude_delta": 0}, "push": False}, {**base, "osc_l_0": 0.8}),
        "no_emit": ({"locomotion": "WAIT", "neck": "NONE", "oscillator": {"emit_trigger": False}, "push": False}, {**base, "osc_l_0": 0.0}),
        "push": ({"locomotion": "WAIT", "neck": "NONE", "oscillator": {}, "push": True}, {**base, "body.mech": 0.7}),
        "no_push": ({"locomotion": "WAIT", "neck": "NONE", "oscillator": {}, "push": False}, {**base, "body.mech": 0.0}),
    }
    results = {}
    for name, (motor, after) in cases.items():
        _train(store, base, after, motor)
        pred = smc.query(store, observation=base, motor=motor)
        results[name] = pred
        assert pred.get("predicted_delta"), name
    assert smc.motor_signature_from_composite(cases["loco_N"][0]) != smc.motor_signature_from_composite(cases["loco_E"][0])
    assert smc.motor_signature_from_composite(cases["neck_L"][0]) != smc.motor_signature_from_composite(cases["neck_R"][0])
    assert smc.motor_signature_from_composite(cases["emit"][0]) != smc.motor_signature_from_composite(cases["no_emit"][0])
    assert smc.motor_signature_from_composite(cases["push"][0]) != smc.motor_signature_from_composite(cases["no_push"][0])
    assert results["loco_N"]["predicted_delta"].get("exo_0") != results["loco_E"]["predicted_delta"].get("exo_0")


def test_composite_motor_prediction_demonstrated():
    store = smc.empty_store(enabled=True)
    base = {k: 0.25 for k in smc.SENSORY_CHANNELS}
    m1 = {"locomotion": "MOVE:N", "neck": "NECK_LEFT", "oscillator": {"emit_trigger": True, "frequency_delta": 1, "amplitude_delta": 0}, "push": False}
    m2 = {"locomotion": "MOVE:N", "neck": "NECK_RIGHT", "oscillator": {"emit_trigger": False, "frequency_delta": 0, "amplitude_delta": 0}, "push": False}
    a1 = {**base, "exo_0": 0.9, "osc_l_0": 0.7, "prop_neck_0": 0.8}
    a2 = {**base, "exo_0": 0.1, "osc_l_0": 0.0, "prop_neck_0": 0.2}
    _train(store, base, a1, m1, n=5)
    _train(store, base, a2, m2, n=5)
    p1 = smc.query(store, observation=base, motor=m1)
    p2 = smc.query(store, observation=base, motor=m2)
    assert p1["status"] == "MATCH" and p2["status"] == "MATCH"
    assert p1["predicted_delta"]["exo_0"] != p2["predicted_delta"]["exo_0"]
    qc = smc.query_candidates(store, observation=base, loco_candidates=["MOVE:N"])
    assert len(qc) == 1
    assert qc[0].get("candidate_locomotion") == "MOVE:N"


def test_one_action_multimodal_future_demonstrated():
    store = smc.empty_store(enabled=True)
    base = {k: 0.2 for k in smc.SENSORY_CHANNELS}
    after = dict(base)
    after.update({
        "exo_0": 0.9, "local.FIELD_A": 0.5, "osc_l_0": 0.6, "osc_r_0": 0.1,
        "prop_neck_0": 0.7, "body.vx": 0.8, "internal.c0": 0.4,
    })
    motor = {"locomotion": "MOVE:E", "neck": "NECK_LEFT", "oscillator": {"emit_trigger": True}, "push": False}
    _train(store, base, after, motor, n=5)
    pred = smc.query(store, observation=base, motor=motor)
    d = pred["predicted_delta"]
    families = {
        "vision": any(k.startswith("exo_") for k in d),
        "field": "local.FIELD_A" in d,
        "bilateral": any(k.startswith("osc_") for k in d),
        "proprio": any(k.startswith("prop_") for k in d),
        "body": any(k.startswith("body.") for k in d),
    }
    assert sum(families.values()) >= 4, families
    op = ohb.construct_o_prime(base, d)
    assert len(op["predicted_fields"]) >= 4


def test_exact_match_presets_with_full_channels():
    def traj(preset):
        s = ObserverSession(SessionConfig(seed=23, evidence_mode="SEARCH_COMPACT"))
        s.set_observer_detail_preset(preset)
        s.set_mechanism("sensorimotor_consequence_model", True)
        acts = []
        for _ in range(18):
            s.step()
            acts.append(getattr(s.runtime, "last_action", None))
        return acts
    assert traj("MINIMAL") == traj("NORMAL") == traj("FULL")
