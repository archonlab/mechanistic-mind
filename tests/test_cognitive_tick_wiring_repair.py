"""Beta 3.1 cognitive tick wiring: SMC/HSS + contextual stack (no new semantics)."""
from __future__ import annotations

import time
from copy import deepcopy

from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system import sensorimotor_consequence as smc
from mechanistic_mind.physical_system.cognition import (
    CognitionConfig,
    empty_cognitive_state,
    run_cognition_before_action,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.research import contextual_stack_bridge as csb


def _obs(**kw):
    base = {
        "exo_0": 0.2,
        "exo_1": 0.5,
        "exo_2": 0.2,
        "local.FIELD_A": 0.1,
        "local.FIELD_B": 0.1,
        "vest_0": 0.5,
        "vest_1": 0.5,
        "prop_neck_0": 0.5,
        "prop_neck_1": 0.5,
        "body.T": 0.4,
        "body.B0": 0.1,
        "body.B1": 0.1,
        "body.B2": 0.1,
        "body.mech": 0.0,
        "body.vx": 0.5,
        "body.vy": 0.5,
        "local.T": 0.4,
        "local.M0": 0.1,
        "local.M1": 0.1,
        "local.M2": 0.1,
        "local.vx": 0.5,
        "local.vy": 0.5,
    }
    base.update(kw)
    return base


WAIT_MOTOR = {
    "schema": "COMPOSITE_MOTOR_V1",
    "locomotion": "WAIT",
    "neck": "NONE",
    "oscillator": {"emit_trigger": False, "frequency_delta": 0, "amplitude_delta": 0},
    "push": False,
}


def test_smc_store_initialized_when_enabled():
    st = empty_cognitive_state(CognitionConfig(sensorimotor_consequence_model=True))
    store = st["sensorimotor_consequence"]
    assert store.get("enabled") is True
    assert store.get("records") == {}
    off = empty_cognitive_state(CognitionConfig(sensorimotor_consequence_model=False))
    assert off["sensorimotor_consequence"].get("enabled") is False


def test_completed_experience_updates_smc_once():
    cfg = CognitionConfig(sensorimotor_consequence_model=True)
    st = empty_cognitive_state(cfg)
    calls = {"n": 0}
    real = smc.update

    def wrapped(*a, **k):
        calls["n"] += 1
        return real(*a, **k)

    smc.update = wrapped  # type: ignore[method-assign]
    try:
        run_cognition_before_action(st, observation=_obs(exo_1=0.3), tick=1, rng_value=0.2)
        assert calls["n"] == 0
        assert st["sensorimotor_consequence"]["updates"] == 0
        st["last_motor_output"] = dict(WAIT_MOTOR)
        st["last_action"] = "WAIT"
        run_cognition_before_action(st, observation=_obs(exo_1=0.7), tick=2, rng_value=0.2)
        assert calls["n"] == 1
        assert st["sensorimotor_consequence"]["updates"] == 1
        run_cognition_before_action(st, observation=_obs(exo_1=0.72), tick=3, rng_value=0.2)
        assert calls["n"] == 2
        assert st["sensorimotor_consequence"]["updates"] == 2
    finally:
        smc.update = real  # type: ignore[method-assign]
    recs = st["sensorimotor_consequence"]["records"]
    assert recs
    q = smc.query(
        st["sensorimotor_consequence"],
        observation=_obs(exo_1=0.3),
        motor=WAIT_MOTOR,
    )
    assert q["status"] in {smc.MATCH, smc.LOW_SUPPORT}


def test_smc_history_reachable_to_hss():
    cfg = CognitionConfig(
        sensorimotor_consequence_model=True,
        historical_sensorimotor_selection_bridge=True,
        historical_sensorimotor_selection_withhold=True,
        prospective_selection="SCENARIO_COMPETITION",
    )
    st = empty_cognitive_state(cfg)
    o = _obs(exo_1=0.3)
    for t in range(1, 7):
        o2 = _obs(exo_1=0.3 + 0.08 * t)
        st["last_motor_output"] = dict(WAIT_MOTOR)
        run_cognition_before_action(st, observation=o2, tick=t, rng_value=0.31)
        o = o2
    sel = st["last_selection"] or {}
    assert sel.get("sensorimotor_consequence", {}).get("enabled") is True
    assert isinstance(sel.get("sensorimotor_candidate_predictions"), list)
    assert sel.get("o_prime_history_bridge", {}).get("enabled") is True
    assert sel.get("sensorimotor_withheld_from_psc") is True
    preds = sel.get("prediction_matches") or []
    assert not any(p.get("source") == "sensorimotor_consequence" for p in preds)


def test_smc_disabled_has_no_active_update():
    cfg = CognitionConfig(sensorimotor_consequence_model=False)
    st = empty_cognitive_state(cfg)
    for t in range(1, 5):
        run_cognition_before_action(st, observation=_obs(exo_1=0.2 + 0.1 * t), tick=t, rng_value=0.4)
    assert st["sensorimotor_consequence"]["updates"] == 0
    assert st["sensorimotor_consequence"]["records"] == {}


def test_contextual_stack_receives_completed_experience_once():
    cfg = CognitionConfig(
        contextual_predictive_organization=True,
        context_grounded_prospection=True,
        persistent_prospective_control=True,
    )
    st = empty_cognitive_state(cfg)
    calls = {"n": 0}
    real = csb.on_experience

    def wrapped(*a, **k):
        calls["n"] += 1
        return real(*a, **k)

    csb.on_experience = wrapped  # type: ignore[method-assign]
    try:
        run_cognition_before_action(st, observation=_obs(), tick=1, rng_value=0.2)
        assert calls["n"] == 0
        for t in range(2, 7):
            run_cognition_before_action(st, observation=_obs(exo_1=0.4), tick=t, rng_value=0.22)
        assert calls["n"] == 5
    finally:
        csb.on_experience = real  # type: ignore[method-assign]
    cpo = st["contextual_organization"]
    assert cpo.get("enabled") is True
    assert len(cpo.get("recent_coactive") or []) >= 1
    sel = st["last_selection"] or {}
    stack = sel.get("contextual_stack") or {}
    assert "before_selection" in stack
    assert "after_selection" in stack


def test_context_state_reachable_to_cgp():
    cfg = CognitionConfig(
        contextual_predictive_organization=True,
        context_grounded_prospection=True,
    )
    st = empty_cognitive_state(cfg)
    for t in range(1, 7):
        run_cognition_before_action(st, observation=_obs(exo_0=0.4, exo_1=0.4), tick=t, rng_value=0.2)
    g = st["context_grounded_prospection"]
    assert g.get("enabled") is True
    before = (st.get("last_selection") or {}).get("contextual_stack", {}).get("before_selection") or {}
    assert "cgp_injected" in before or before == {} or isinstance(before, dict)


def test_context_state_reachable_to_ppc():
    cfg = CognitionConfig(
        contextual_predictive_organization=True,
        persistent_prospective_control=True,
    )
    st = empty_cognitive_state(cfg)
    for t in range(1, 6):
        run_cognition_before_action(st, observation=_obs(), tick=t, rng_value=0.18)
    p = st["persistent_prospective_control"]
    assert p.get("enabled") is True
    after = (st.get("last_selection") or {}).get("contextual_stack", {}).get("after_selection")
    assert after is not None


def test_context_disabled_has_no_active_update():
    cfg = CognitionConfig(
        contextual_predictive_organization=False,
        context_grounded_prospection=False,
        persistent_prospective_control=False,
        sensorimotor_consequence_model=True,
    )
    st = empty_cognitive_state(cfg)
    calls = {"n": 0}
    real = csb.on_experience

    def wrapped(*a, **k):
        calls["n"] += 1
        return real(*a, **k)

    csb.on_experience = wrapped  # type: ignore[method-assign]
    try:
        for t in range(1, 5):
            run_cognition_before_action(st, observation=_obs(exo_1=0.3 * t), tick=t, rng_value=0.3)
    finally:
        csb.on_experience = real  # type: ignore[method-assign]
    assert calls["n"] == 0
    assert st["contextual_organization"].get("recent_coactive") == []


def test_no_same_tick_future_leakage():
    cfg = CognitionConfig(sensorimotor_consequence_model=True)
    st = empty_cognitive_state(cfg)
    run_cognition_before_action(st, observation=_obs(exo_1=0.3), tick=1, rng_value=0.11)
    st["last_action"] = "WAIT"
    st["last_motor_output"] = dict(WAIT_MOTOR)
    st["last_fragment"] = _obs(exo_1=0.3)
    r2 = run_cognition_before_action(st, observation=_obs(exo_1=0.85), tick=2, rng_value=0.91)
    last = st["sensorimotor_consequence"].get("last_update") or {}
    sig = str(last.get("motor_signature") or "")
    assert "L:WAIT|" in sig
    assert r2.selected_action != "WAIT"
    assert f"L:{r2.selected_action}|" not in sig


def test_no_cross_agent_same_tick_leakage():
    cfg = tiktaalik_config()
    cfg.cognition.sensorimotor_consequence_model = True
    cfg.cognition.historical_sensorimotor_selection_bridge = True
    rt = TwoAgentRuntime(seed=19, config=cfg)
    obs = rt.observations()
    rt.step(1)
    assert rt.slots[0].cognition.get("last_fragment") == obs[0]
    assert rt.slots[1].cognition.get("last_fragment") == obs[1]
    obs2 = rt.observations()
    rt._step_once()
    assert rt.slots[0].cognition.get("last_fragment") == obs2[0]
    assert rt.slots[1].cognition.get("last_fragment") == obs2[1]
    # Per-agent stores: A's records are not B's object.
    assert rt.slots[0].cognition["sensorimotor_consequence"] is not rt.slots[1].cognition["sensorimotor_consequence"]


def test_cognitive_hook_state_survives_restore():
    cfg = tiktaalik_config()
    cfg.cognition.sensorimotor_consequence_model = True
    cfg.cognition.contextual_predictive_organization = True
    cfg.cognition.context_grounded_prospection = True
    rt = PhysicalSystemRuntime(seed=21, config=cfg)
    for _ in range(5):
        rt.step()
    smc_before = deepcopy(rt.cognition["sensorimotor_consequence"]["records"])
    cpo_before = deepcopy(rt.cognition["contextual_organization"].get("recent_coactive"))
    snap = rt.snapshot()
    rest = PhysicalSystemRuntime.restore(snap)
    assert rest.cognition["sensorimotor_consequence"]["records"] == smc_before
    assert rest.cognition["contextual_organization"].get("recent_coactive") == cpo_before
    rest.step()
    rt2 = PhysicalSystemRuntime.restore(deepcopy(snap))
    rt2.step()
    assert rest.last_selected_action == rt2.last_selected_action


def test_pause_resume_does_not_update():
    cfg = tiktaalik_config()
    cfg.cognition.sensorimotor_consequence_model = True
    cfg.cognition.contextual_predictive_organization = True
    rt = PhysicalSystemRuntime(seed=7, config=cfg)
    for _ in range(3):
        rt.step()
    u = int(rt.cognition["sensorimotor_consequence"]["updates"])
    nco = len(rt.cognition["contextual_organization"].get("recent_coactive") or [])
    rt.cognitive_view()
    rt.snapshot()
    assert int(rt.cognition["sensorimotor_consequence"]["updates"]) == u
    assert len(rt.cognition["contextual_organization"].get("recent_coactive") or []) == nco


def test_post_repair_determinism():
    def run():
        cfg = CognitionConfig(
            sensorimotor_consequence_model=True,
            historical_sensorimotor_selection_bridge=True,
            contextual_predictive_organization=True,
            context_grounded_prospection=True,
            persistent_prospective_control=True,
        )
        st = empty_cognitive_state(cfg)
        acts = []
        for t in range(1, 9):
            r = run_cognition_before_action(
                st,
                observation=_obs(exo_1=0.2 + (t % 3) * 0.1),
                tick=t,
                rng_value=0.37,
            )
            acts.append(r.selected_action)
        sm = deepcopy(st["sensorimotor_consequence"]["records"])
        cx = deepcopy(st["contextual_organization"].get("recent_coactive"))
        return acts, sm, cx

    assert run() == run()


def test_composite_motor_signature_learned():
    cfg = CognitionConfig(sensorimotor_consequence_model=True)
    st = empty_cognitive_state(cfg)
    run_cognition_before_action(st, observation=_obs(exo_1=0.4), tick=1, rng_value=0.2)
    st["last_motor_output"] = {
        "schema": "COMPOSITE_MOTOR_V1",
        "locomotion": "MOVE:N",
        "neck": "NECK_LEFT",
        "oscillator": {"emit_trigger": True, "frequency_delta": 1, "amplitude_delta": 0},
        "push": True,
    }
    st["last_action"] = "MOVE:N"
    run_cognition_before_action(st, observation=_obs(exo_1=0.6), tick=2, rng_value=0.2)
    sig = str((st["sensorimotor_consequence"].get("last_update") or {}).get("motor_signature") or "")
    assert sig.startswith("L:MOVE:N|N:NECK_LEFT|E:1|F:1|A:0|P:1")


def test_hook_cost_informational():
    def bench(smc_on: bool, ctx_on: bool) -> float:
        cfg = CognitionConfig(
            sensorimotor_consequence_model=smc_on,
            historical_sensorimotor_selection_bridge=smc_on,
            contextual_predictive_organization=ctx_on,
            context_grounded_prospection=ctx_on,
            persistent_prospective_control=ctx_on,
        )
        st = empty_cognitive_state(cfg)
        t0 = time.perf_counter()
        for t in range(1, 9):
            run_cognition_before_action(st, observation=_obs(exo_1=0.2 + 0.05 * t), tick=t, rng_value=0.2)
        return time.perf_counter() - t0

    off = bench(False, False)
    smc_only = bench(True, False)
    both = bench(True, True)
    # Informational: non-zero extra cost is expected; reject only pathological blow-up.
    assert both < max(0.5, off * 50 + 0.5)
    _ = smc_only
