"""Historical factorized OSC / PUSH prediction feed (shared with neck)."""
from __future__ import annotations

from mechanistic_mind.physical_system.actions import available_actions
from mechanistic_mind.physical_system.cognition import (
    CognitionConfig,
    empty_cognitive_state,
    run_cognition_before_action,
)
from mechanistic_mind.physical_system.composite_motor import select_factorized_side_channels
from mechanistic_mind.physical_system.oscillatory_signaling import OscillatorySignalingConfig
from mechanistic_mind.physical_system.physical_push import PhysicalPushConfig
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.research import predictive_compression as pc

import numpy as np


def _O(**extra):
    base = {"exo_0": 0.12, "exo_1": 0.24, "exo_2": 0.36}
    base.update(extra)
    return base


def _st():
    cfg = CognitionConfig(
        prospective_composition=False,
        predictive_equivalence=False,
        temporal_predictive_structure=False,
        composite_motor=True,
        retrieval=True,
        bounded_memory=True,
    )
    st = empty_cognitive_state(cfg)
    st["available_actions"] = list(
        available_actions(articulated_head=True, physical_push=True, oscillatory_signaling=True)
    )
    return st, _O()


def _pick(st, preds, rng=0.5):
    return select_factorized_side_channels(
        available=list(st["available_actions"]),
        predictions=preds,
        rng_value=rng,
        articulated_head=True,
        oscillatory=True,
        physical_push=True,
    )


def test_osc_emit_retained_and_ablation():
    st, O = _st()
    pc.observe(st["compression"], tick=1, fragment=O, action="OSC_EMIT", realized=_O(exo_0=0.5), domain="accessible")
    res = run_cognition_before_action(st, observation=O, tick=2, rng_value=0.5)
    assert "OSC_EMIT" not in res.actions
    assert any(p.get("action") == "OSC_EMIT" for p in res.predictions)
    _neck, nsrc, osc, osc_src, push, psrc = _pick(st, res.predictions, rng=0.5)
    assert "emit:RETAINED_PREDICTION" in osc_src
    assert osc.emit_trigger is True
    st["compression"]["structures"] = {}
    res2 = run_cognition_before_action(st, observation=O, tick=3, rng_value=0.5)
    *_, osc2, osc_src2, _, _ = _pick(st, res2.predictions, rng=0.5)
    assert "emit:DEFAULT_NONE" in osc_src2
    assert osc2.emit_trigger is False


def test_osc_freq_and_amp_retained_separately():
    st, O = _st()
    pc.observe(st["compression"], tick=1, fragment=O, action="OSC_FREQ_UP", realized=_O(exo_0=0.5), domain="accessible")
    pc.observe(st["compression"], tick=1, fragment=O, action="OSC_AMP_DOWN", realized=_O(exo_0=0.5), domain="accessible")
    res = run_cognition_before_action(st, observation=O, tick=2, rng_value=0.5)
    *_, osc, osc_src, _, _ = _pick(st, res.predictions, rng=0.5)
    assert "freq:RETAINED_PREDICTION" in osc_src
    assert "amp:RETAINED_PREDICTION" in osc_src
    assert osc.frequency_delta == 1
    assert osc.amplitude_delta == -1
    assert osc.emit_trigger is False


def test_push_retained_and_ablation():
    st, O = _st()
    pc.observe(st["compression"], tick=1, fragment=O, action="PUSH", realized=_O(exo_0=0.5), domain="accessible")
    res = run_cognition_before_action(st, observation=O, tick=2, rng_value=0.5)
    assert "PUSH" not in res.actions
    *_, push, psrc = _pick(st, res.predictions, rng=0.5)
    assert psrc == "RETAINED_PREDICTION"
    assert push is True
    st["compression"]["structures"] = {}
    res2 = run_cognition_before_action(st, observation=O, tick=3, rng_value=0.5)
    *_, push2, psrc2 = _pick(st, res2.predictions, rng=0.5)
    assert psrc2 == "DEFAULT_NONE"
    assert push2 is False


def test_same_observation_push_vs_emit_is_history_not_heuristic():
    st_e, O = _st()
    st_p, _ = _st()
    pc.observe(st_e["compression"], tick=1, fragment=O, action="OSC_EMIT", realized=_O(exo_0=0.5), domain="accessible")
    pc.observe(st_p["compression"], tick=1, fragment=O, action="PUSH", realized=_O(exo_0=0.5), domain="accessible")
    re = run_cognition_before_action(st_e, observation=O, tick=2, rng_value=0.5)
    rp = run_cognition_before_action(st_p, observation=O, tick=2, rng_value=0.5)
    *_, osc_e, src_e, push_e, _ = _pick(st_e, re.predictions, rng=0.5)
    *_, osc_p, src_p, push_p, psrc = _pick(st_p, rp.predictions, rng=0.5)
    assert osc_e.emit_trigger is True and push_e is False
    assert osc_p.emit_trigger is False and push_p is True and psrc == "RETAINED_PREDICTION"


def test_wait_osc_emit_and_push_last_action_projection():
    cfg = PhysicalSystemConfig()
    cfg.cognition.composite_motor = True
    cfg.oscillatory_signaling = OscillatorySignalingConfig(mode="EXPERIMENTAL", duration_base=4)
    cfg.physical_push = PhysicalPushConfig(mode="EXPERIMENTAL")
    rt = PhysicalSystemRuntime(seed=11, config=cfg)
    rt.step_forced_motor({
        "locomotion": "WAIT", "neck": "NONE",
        "oscillator": {"emit_trigger": True, "frequency_delta": 0, "amplitude_delta": 0},
        "push": False,
    })
    assert rt.cognition.get("last_action") == "OSC_EMIT"
    rt.step_forced_motor({
        "locomotion": "WAIT", "neck": "NONE",
        "oscillator": {"emit_trigger": False, "frequency_delta": 0, "amplitude_delta": 0},
        "push": True,
    })
    assert rt.cognition.get("last_action") == "PUSH"
    rt.step_forced_motor({
        "locomotion": "MOVE:N", "neck": "NONE",
        "oscillator": {"emit_trigger": True, "frequency_delta": 0, "amplitude_delta": 0},
        "push": True,
    })
    assert rt.cognition.get("last_action") == "MOVE:N"


def test_osc_retained_reaches_bands_and_peer():
    cfg = PhysicalSystemConfig()
    cfg.cognition.cognition_enabled = True
    cfg.cognition.retrieval = True
    cfg.cognition.composite_motor = True
    cfg.cognition.prospective_composition = False
    cfg.oscillatory_signaling = OscillatorySignalingConfig(mode="EXPERIMENTAL", duration_base=8)
    sys = TwoAgentRuntime(seed=9, config=cfg, starts=((8, 8), (9, 8)), signal_enabled=False)
    a0, a1 = sys.slots
    a0.body.theta = 0.0
    a1.body.theta = 0.0
    a0.body.osc_amp_u = 1.0
    a0._sync_embodiment_dofs()
    obs = a0.agent_observation()
    pc.observe(
        a0.cognition["compression"], tick=0, fragment=obs, action="OSC_EMIT",
        realized=dict(obs), domain="accessible",
    )
    sys.step()
    osc_src = ((a0.last_motor_output or {}).get("domain_sources") or {}).get("oscillator") or ""
    assert "emit:RETAINED_PREDICTION" in osc_src
    assert bool((a0.last_motor_output or {}).get("oscillator", {}).get("emit_trigger"))
    energy = float(np.asarray(sys.world.OSC_BANDS).sum())
    obs1 = a1.agent_observation()
    osc = [float(obs1[k]) for k in obs1 if str(k).startswith("osc_l_") or str(k).startswith("osc_r_")]
    assert energy > 0.0
    assert osc and max(osc) > 0.0


def test_push_retained_sets_exertion():
    cfg = PhysicalSystemConfig()
    cfg.cognition.retrieval = True
    cfg.cognition.composite_motor = True
    cfg.cognition.prospective_composition = False
    cfg.physical_push = PhysicalPushConfig(mode="EXPERIMENTAL")
    rt = PhysicalSystemRuntime(seed=4, config=cfg)
    rt._sync_embodiment_dofs()
    obs = rt.agent_observation()
    pc.observe(rt.cognition["compression"], tick=0, fragment=obs, action="PUSH", realized=dict(obs), domain="accessible")
    rt.step()
    assert (rt.last_motor_output or {}).get("domain_sources", {}).get("push") == "RETAINED_PREDICTION"
    assert bool((rt.last_motor_output or {}).get("push"))
    assert float(getattr(rt.body, "push_exertion", 0.0) or 0.0) > 0.0
