"""Smoke + gate regression for 4.26–4.28 modules."""
from mechanistic_mind.research import contextual_predictive_organization as cpo
from mechanistic_mind.research import context_grounded_prospection as cgp
from mechanistic_mind.research import persistent_prospective_control as ppc
from mechanistic_mind.physical_system.cognition import CognitionConfig, empty_cognitive_state


def test_forbidden_tokens_absent_in_empty_stores():
    for store in (cpo.empty_store(), cgp.empty_store(), ppc.empty_store()):
        assert cpo.audit_forbidden(store) == []


def test_config_defaults_off():
    cfg = CognitionConfig()
    assert cfg.contextual_predictive_organization is False
    assert cfg.context_grounded_prospection is False
    assert cfg.persistent_prospective_control is False
    st = empty_cognitive_state(cfg)
    assert st["contextual_organization"]["enabled"] is False


def test_partial_reactivation_and_ablation():
    store = cpo.empty_store()
    store["enabled"] = True
    members = ["A:t:1", "A:m0:2", "A:opt:1", "A:vest:0"]
    for i in range(6):
        cpo.observe_coactivation(store, tick=i + 1, members=members, continuation={"t": 0.4}, action="WAIT")
    assert store["formation_events"] >= 1
    r = cpo.reactivate(store, tick=10, evidence_members=members[:3], mode="PARTIAL")
    assert r["status"] in {"MATCH", "WEAK"}
    pred = cpo.predict_from_context(store, r)
    store["ablate_predictive_use"] = True
    assert cpo.predict_from_context(store, r)["status"] == "ABLATED"


def test_context_composition_and_persistence():
    cgp_s = cgp.empty_store(); cgp_s["enabled"] = True
    for _ in range(3):
        cgp.learn_context_transition(cgp_s, tick=1, from_id="CX1", to_id="CX2", action="M1")
        cgp.learn_context_transition(cgp_s, tick=2, from_id="CX2", to_id="CX3", action="M2")
    comp = cgp.compose_context_trajectories(cgp_s, start_id="CX1", max_depth=3)
    assert comp["max_depth"] >= 2
    conts = cgp.inject_as_prospection_continuations(comp)
    ppc_s = ppc.empty_store(); ppc_s["enabled"] = True
    active = ppc.select_continuation(ppc_s, tick=1, continuation=conts[0])
    assert active is not None
    assert ppc.preferred_action(ppc_s) == conts[0]["actions"][0]
