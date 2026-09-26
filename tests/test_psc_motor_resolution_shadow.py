
"""PSC motor resolution shadow — observational only."""
from __future__ import annotations
import json
from mechanistic_mind.physical_system import sensorimotor_consequence as smc
from mechanistic_mind.physical_system import psc_motor_resolution_shadow as shadow
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig


def _base():
    return {k: 0.25 for k in smc.SENSORY_CHANNELS}


def _train(store, base, after, motor, n=5, t0=0):
    for i in range(n):
        smc.update(store, tick=t0 + i, observation_t=base, motor=motor, observation_t1=after)


def test_case_a_low_divergence_no_refine():
    store = smc.empty_store(enabled=True)
    base = _base()
    after = {**base, "exo_0": 0.5}
    m1 = {"locomotion": "MOVE:E", "neck": "NECK_LEFT", "oscillator": {}, "push": False}
    m2 = {"locomotion": "MOVE:E", "neck": "NECK_RIGHT", "oscillator": {}, "push": False}
    _train(store, base, after, m1)
    _train(store, base, after, m2, t0=10)
    pack = shadow.evaluate_loco_shadow(store, base, "MOVE:E", divergence_refine_threshold=0.02)
    assert pack["adaptive"]["would_refine"] is False
    assert pack["within_loco_divergence"]["max"] == 0.0


def test_case_b_neck_matters_refines():
    store = smc.empty_store(enabled=True)
    base = _base()
    m1 = {"locomotion": "MOVE:E", "neck": "NECK_LEFT", "oscillator": {}, "push": False}
    m2 = {"locomotion": "MOVE:E", "neck": "NECK_RIGHT", "oscillator": {}, "push": False}
    _train(store, base, {**base, "exo_0": 0.95, "prop_neck_0": 0.9}, m1)
    _train(store, base, {**base, "exo_0": 0.05, "prop_neck_0": 0.1}, m2, t0=10)
    pack = shadow.evaluate_loco_shadow(store, base, "MOVE:E", divergence_refine_threshold=0.02)
    assert pack["adaptive"]["would_refine"] is True
    assert pack["within_loco_divergence"]["max"] > 0.02


def test_no_cartesian_invented():
    store = smc.empty_store(enabled=True)
    base = _base()
    m1 = {"locomotion": "MOVE:E", "neck": "NECK_LEFT", "oscillator": {"emit_trigger": True}, "push": False}
    m2 = {"locomotion": "MOVE:E", "neck": "NECK_RIGHT", "oscillator": {}, "push": True}
    _train(store, base, {**base, "exo_0": 0.9}, m1)
    _train(store, base, {**base, "exo_0": 0.1}, m2, t0=10)
    obs = shadow.observed_composites_for_loco(store, "MOVE:E")
    assert len(obs) == 2


def test_shadow_exact_match_actions():
    def traj(with_shadow: bool):
        s = ObserverSession(SessionConfig(seed=91, evidence_mode="SEARCH_COMPACT"))
        s.apply_experiment({"seed": 91, "agent_count": 2})
        s.set_observer_detail_preset("MINIMAL")
        s.set_mechanism("sensorimotor_consequence_model", True)
        s.set_mechanism("prospective_scenario_competition", True)
        acts = []
        for _ in range(20):
            s.step()
            if with_shadow:
                slot = s.runtime.slots[0]
                store = slot.cognition.get("sensorimotor_consequence") or {}
                obs = slot.agent_observation(foreign_bodies=s.runtime.foreign_bodies_for(0))
                locos = list((slot.cognition.get("last_selection") or {}).get("select_actions") or ["WAIT"])
                shadow.shadow_tick(store, obs, locos)
            acts.append(json.dumps(s.runtime.slots[0].cognition.get("last_motor_output"), sort_keys=True, default=str))
        return acts
    assert traj(False) == traj(True)


def test_loco_prefix_is_max_support_not_mean():
    """Document production semantics: fallback picks max-support composite, not average."""
    store = smc.empty_store(enabled=True)
    base = _base()
    # two composites under MOVE:N with different futures; query NONE sidechannels misses exact
    m1 = {"locomotion": "MOVE:N", "neck": "NECK_LEFT", "oscillator": {}, "push": False}
    m2 = {"locomotion": "MOVE:N", "neck": "NECK_RIGHT", "oscillator": {}, "push": False}
    _train(store, base, {**base, "exo_0": 0.9}, m1, n=6)  # higher support
    _train(store, base, {**base, "exo_0": 0.1}, m2, n=3, t0=20)
    pred = shadow.loco_only_query(store, base, "MOVE:N")
    assert pred.get("aggregation") in {"MAX_SUPPORT_UNDER_PREFIX", "EXACT_NONE_SIDECHANNELS"}
    if pred.get("aggregation") == "MAX_SUPPORT_UNDER_PREFIX":
        assert "NECK_LEFT" in str(pred.get("motor_signature"))
