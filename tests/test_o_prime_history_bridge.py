"""Gates for O′ → history → PSC bridge."""
from __future__ import annotations

from mechanistic_mind.physical_system import o_prime_history_bridge as oph
from mechanistic_mind.physical_system import sensorimotor_consequence as smc
from mechanistic_mind.research import prospective_composition as pr
from mechanistic_mind.physical_system.cognition import (
    CognitionConfig, empty_cognitive_state, run_cognition_before_action,
)


def _obs(**kw):
    base = {
        "exo_0": 0.3, "exo_1": 0.5, "exo_2": 0.3,
        "local.FIELD_A": 0.3, "local.FIELD_B": 0.3,
        "vest_0": 0.5, "vest_1": 0.5,
        "prop_neck_0": 0.5, "prop_neck_1": 0.5,
        "body.T": 0.4, "body.B0": 0.1, "body.B1": 0.1, "body.B2": 0.1,
        "body.mech": 0.0, "body.vx": 0.5, "body.vy": 0.5,
        "local.T": 0.4, "local.M0": 0.1, "local.M1": 0.1, "local.M2": 0.1,
        "local.vx": 0.5, "local.vy": 0.5,
    }
    base.update(kw)
    return base


def test_no_reward_tokens_in_bridge_module():
    text = open("mechanistic_mind/physical_system/o_prime_history_bridge.py").read()
    for bad in ("REWARD", "UTILITY", "APPROACH_SCORE", "VISUAL_SCORE", "DESIRE", "GOAL_SCORE"):
        assert bad not in text


def test_construct_o_prime_accessible_only():
    o = _obs(exo_1=0.4)
    meta = oph.construct_o_prime(o, {"exo_1": 0.2, "ground_truth_distance": 9.0})
    assert "exo_1" in meta["predicted_fields"]
    assert "ground_truth_distance" not in meta["o_prime"]
    assert abs(meta["o_prime"]["exo_1"] - 0.6) < 1e-6


def test_history_query_uses_predict_one_step():
    store = pr.empty_store()
    o = _obs(exo_1=0.55)
    for t in range(10):
        pr.learn_transition(store, tick=t, antecedent=o, action="MOVE:N", consequent=_obs(exo_1=0.7))
    h = oph.query_history_on_o_prime(
        prospection=store, compression=None, o_prime=o,
        actions=["WAIT", "MOVE:N", "MOVE:S"], retrieval_enabled=False,
    )
    assert h["status"] == oph.MATCH
    assert h["historical_support"] >= 1


def test_withhold_flag_in_config():
    cfg = CognitionConfig(
        historical_sensorimotor_selection_bridge=True,
        historical_sensorimotor_selection_withhold=True,
        sensorimotor_consequence_model=True,
    )
    d = cfg.to_dict()
    assert d["historical_sensorimotor_selection_bridge"] is True
    assert d["historical_sensorimotor_selection_withhold"] is True


def test_determinism_bridge_on():
    def run():
        cfg = CognitionConfig(
            sensorimotor_consequence_model=True,
            historical_sensorimotor_selection_bridge=True,
            prospective_selection="SCENARIO_COMPETITION",
        )
        st = empty_cognitive_state(cfg)
        acts = []
        for t in range(1, 40):
            r = run_cognition_before_action(st, observation=_obs(exo_1=0.2+(t%5)*0.05), tick=t, rng_value=0.37)
            acts.append(r.selected_action)
        return acts
    assert run() == run()
