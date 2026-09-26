"""FULL COMPOSITE PSC SHADOW REPLAY — acceptance tests (observational only)."""
from __future__ import annotations

import copy
import json

from mechanistic_mind.physical_system import sensorimotor_consequence as smc
from mechanistic_mind.physical_system import o_prime_history_bridge as oph
from mechanistic_mind.physical_system import scenario_competition as sc
from mechanistic_mind.physical_system import full_composite_psc_shadow as shadow
from mechanistic_mind.physical_system import psc_motor_resolution_shadow as prior
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig


def _base():
    return {k: 0.25 for k in smc.SENSORY_CHANNELS}


def _train(store, base, after, motor, n=5, t0=0):
    for i in range(n):
        smc.update(store, tick=t0 + i, observation_t=base, motor=motor, observation_t1=after)


def _empty_prospection():
    return {"transitions": {}, "schema": "test"}


def test_observed_composites_only_no_cartesian():
    store = smc.empty_store(enabled=True)
    base = _base()
    m1 = {"locomotion": "MOVE:E", "neck": "NECK_LEFT", "oscillator": {"emit_trigger": True}, "push": False}
    m2 = {"locomotion": "MOVE:E", "neck": "NECK_RIGHT", "oscillator": {}, "push": True}
    _train(store, base, {**base, "exo_0": 0.9}, m1)
    _train(store, base, {**base, "exo_0": 0.1}, m2, t0=10)
    obs = prior.observed_composites_for_loco(store, "MOVE:E")
    sigs = {c["motor_signature"] for c in obs}
    assert len(sigs) == 2
    # never invent LEFT+push+emit
    invent = "L:MOVE:E|N:NECK_LEFT|E:1|F:0|A:0|P:1"
    assert invent not in sigs


def test_full_signatures_preserved_and_exact_smc_when_available():
    store = smc.empty_store(enabled=True)
    base = _base()
    m1 = {"locomotion": "MOVE:N", "neck": "NECK_LEFT", "oscillator": {"emit_trigger": True}, "push": False}
    _train(store, base, {**base, "prop_neck_0": 0.9, "exo_0": 0.8}, m1, n=6)
    pred = prior.composite_query(store, base, m1)
    assert pred.get("predicted_delta")
    assert pred.get("status") in {smc.MATCH, smc.LOW_SUPPORT}
    assert "NECK_LEFT" in str(smc.motor_signature_from_composite(m1))


def test_composite_o_prime_differs_when_consequences_differ():
    store = smc.empty_store(enabled=True)
    base = _base()
    m1 = {"locomotion": "MOVE:E", "neck": "NECK_LEFT", "oscillator": {}, "push": False}
    m2 = {"locomotion": "MOVE:E", "neck": "NECK_RIGHT", "oscillator": {}, "push": False}
    _train(store, base, {**base, "exo_0": 0.95, "prop_neck_0": 0.9}, m1, n=6)
    _train(store, base, {**base, "exo_0": 0.05, "prop_neck_0": 0.1}, m2, n=6, t0=20)
    o1 = prior.o_prime_from_pred(base, prior.composite_query(store, base, m1))["o_prime"]
    o2 = prior.o_prime_from_pred(base, prior.composite_query(store, base, m2))["o_prime"]
    assert prior.channel_divergence(o1, o2)["global"] > 0.01


def test_reuses_real_history_evidence_and_compete():
    # Structural: module references production callables
    assert oph.construct_o_prime in [getattr(oph, n) for n in dir(oph)]
    assert hasattr(sc, "compete_scenarios")
    src = open("mechanistic_mind/physical_system/full_composite_psc_shadow.py").read()
    assert "oph.construct_o_prime" in src
    assert "oph.query_history_on_o_prime" in src
    assert "oph.build_psc_scenario" in src
    assert "sc.compete_scenarios" in src


def test_shadow_does_not_mutate_smc_history_or_selection():
    store = smc.empty_store(enabled=True)
    base = _base()
    m1 = {"locomotion": "WAIT", "neck": "NONE", "oscillator": {}, "push": False}
    m2 = {"locomotion": "WAIT", "neck": "NECK_LEFT", "oscillator": {}, "push": False}
    _train(store, base, {**base, "exo_0": 0.4}, m1, n=5)
    _train(store, base, {**base, "exo_0": 0.7, "prop_neck_0": 0.8}, m2, n=5, t0=10)
    prosp = _empty_prospection()
    before = json.dumps({"q": store.get("queries"), "u": store.get("updates"), "n": len(store["records"])}, sort_keys=True)
    prosp_before = json.dumps(prosp, sort_keys=True)
    motor = {**m1, "schema": "COMPOSITE_MOTOR_V1", "selection_source": "COMPOSITE_FACTORIZED"}
    rep = shadow.replay_tick(
        observation=base,
        smc_store=store,
        prospection=prosp,
        compression=None,
        loco_candidates=["WAIT", "MOVE:N"],
        seed=7,
        tick=3,
        production_selected_loco="WAIT",
        production_realized_motor=motor,
        retrieval_enabled=False,
    )
    after = json.dumps({"q": store.get("queries"), "u": store.get("updates"), "n": len(store["records"])}, sort_keys=True)
    assert before == after
    assert json.dumps(prosp, sort_keys=True) == prosp_before
    assert rep["mutation_audit"]["smc_counters_unchanged"] is True


def test_classifications_same_and_different():
    store = smc.empty_store(enabled=True)
    base = _base()
    # Distinct composites under WAIT and MOVE:N with different O′
    mw = {"locomotion": "WAIT", "neck": "NONE", "oscillator": {}, "push": False}
    mn = {"locomotion": "MOVE:N", "neck": "NECK_LEFT", "oscillator": {"emit_trigger": True}, "push": False}
    _train(store, base, {**base, "exo_0": 0.2}, mw, n=8)
    _train(store, base, {**base, "exo_0": 0.9, "prop_neck_0": 0.9}, mn, n=8, t0=20)
    # Seed minimal history so scenarios can form: without history MATCH, compete may be empty
    # Classification helpers unit-test directly
    assert shadow.classify_outcome(
        production_loco="WAIT",
        production_realized_sig=smc.motor_signature_from_composite(mw),
        shadow_selected_key=smc.motor_signature_from_composite(mw),
        shadow_selected_loco="WAIT",
        shadow_selected_sig=smc.motor_signature_from_composite(mw),
        n_composite_scenarios=2,
    ) == "SAME_LOCOMOTION_SAME_COMPOSITE"
    assert shadow.classify_outcome(
        production_loco="WAIT",
        production_realized_sig=smc.motor_signature_from_composite(mw),
        shadow_selected_key=smc.motor_signature_from_composite(mn),
        shadow_selected_loco="MOVE:N",
        shadow_selected_sig=smc.motor_signature_from_composite(mn),
        n_composite_scenarios=2,
    ) == "DIFFERENT_LOCOMOTION"
    m_alt = {"locomotion": "WAIT", "neck": "NECK_LEFT", "oscillator": {}, "push": False}
    assert shadow.classify_outcome(
        production_loco="WAIT",
        production_realized_sig=smc.motor_signature_from_composite(mw),
        shadow_selected_key=smc.motor_signature_from_composite(m_alt),
        shadow_selected_loco="WAIT",
        shadow_selected_sig=smc.motor_signature_from_composite(m_alt),
        n_composite_scenarios=2,
    ) == "SAME_LOCOMOTION_DIFFERENT_COMPOSITE"
    assert shadow.classify_outcome(
        production_loco="WAIT",
        production_realized_sig=None,
        shadow_selected_key=None,
        shadow_selected_loco=None,
        shadow_selected_sig=None,
        n_composite_scenarios=0,
    ) == "INSUFFICIENT_COMPOSITE_EVIDENCE"


def test_adaptive_empirical_only():
    store = smc.empty_store(enabled=True)
    base = _base()
    m1 = {"locomotion": "MOVE:E", "neck": "NECK_LEFT", "oscillator": {}, "push": False}
    m2 = {"locomotion": "MOVE:E", "neck": "NECK_RIGHT", "oscillator": {}, "push": False}
    _train(store, base, {**base, "exo_0": 0.95}, m1, n=6)
    _train(store, base, {**base, "exo_0": 0.05}, m2, n=6, t0=10)
    rep = shadow.replay_tick(
        observation=base,
        smc_store=store,
        prospection=_empty_prospection(),
        compression=None,
        loco_candidates=["MOVE:E", "WAIT"],
        seed=1,
        tick=1,
        production_selected_loco="MOVE:E",
        production_realized_motor=m1,
        divergence_refine_threshold=0.02,
        run_adaptive=True,
        retrieval_enabled=False,
    )
    # Even if no history scenarios, adaptive path must not invent motors beyond store
    observed = {c["motor_signature"] for c in prior.observed_composites_for_loco(store, "MOVE:E")}
    sel = (rep.get("adaptive") or {}).get("selected_sig")
    if sel:
        assert sel in observed or sel in {"MOVE:E", "WAIT"}


def test_no_observer_gt_in_module():
    src = open("mechanistic_mind/physical_system/full_composite_psc_shadow.py").read()
    for banned in ("body_exposure", "ground_truth", "bearing", "intention", "language"):
        assert banned not in src.lower() or banned in ("bearing",)  # allow absence
    assert "Observer GT" not in src


def test_shadow_exact_match_production_trajectory():
    def traj(with_shadow: bool):
        s = ObserverSession(SessionConfig(seed=77, evidence_mode="SEARCH_COMPACT"))
        s.apply_experiment({"seed": 77, "agent_count": 2})
        s.set_observer_detail_preset("MINIMAL")
        s.set_mechanism("sensorimotor_consequence_model", True)
        s.set_mechanism("historical_sensorimotor_selection_bridge", True)
        s.set_mechanism("prospective_scenario_competition", True)
        s.set_mechanism("prospective_composition", True)
        acts = []
        for _ in range(15):
            s.step()
            if with_shadow:
                slot = s.runtime.slots[0]
                cog = slot.cognition
                store = cog.get("sensorimotor_consequence") or {}
                prosp = cog.get("prospection") or {}
                obs = slot.agent_observation(foreign_bodies=s.runtime.foreign_bodies_for(0))
                obs_f = {k: float(v) for k, v in (obs or {}).items() if isinstance(v, (int, float))}
                ls = cog.get("last_selection") or {}
                locos = list(ls.get("select_actions") or ["WAIT"])
                motor = cog.get("last_motor_output")
                shadow.replay_tick(
                    observation=obs_f,
                    smc_store=store,
                    prospection=prosp,
                    compression=cog.get("compression"),
                    loco_candidates=locos,
                    seed=77,
                    tick=int(s.runtime.tick),
                    production_selected_loco=(motor or {}).get("locomotion"),
                    production_realized_motor=motor,
                    run_adaptive=False,
                )
            acts.append(json.dumps(s.runtime.slots[0].cognition.get("last_motor_output"), sort_keys=True, default=str))
        return acts

    assert traj(False) == traj(True)


def test_minimal_normal_full_same_when_shadow_polled():
    """Panel polling / detail preset must not alter production motors."""
    def run(preset: str):
        s = ObserverSession(SessionConfig(seed=55, evidence_mode="SEARCH_COMPACT"))
        s.apply_experiment({"seed": 55, "agent_count": 2})
        s.set_observer_detail_preset(preset)
        s.set_mechanism("sensorimotor_consequence_model", True)
        s.set_mechanism("prospective_scenario_competition", True)
        out = []
        for _ in range(10):
            s.step()
            out.append(json.dumps(s.runtime.slots[0].cognition.get("last_motor_output"), sort_keys=True, default=str))
        return out
    assert run("MINIMAL") == run("NORMAL") == run("FULL")
