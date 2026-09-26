"""Restore historical neck RETAINED_PREDICTION feed (Beta 3 factorized path)."""
from __future__ import annotations

from mechanistic_mind.physical_system.actions import available_actions
from mechanistic_mind.physical_system.articulated_head import ArticulatedHeadConfig
from mechanistic_mind.physical_system.cognition import (
    CognitionConfig,
    empty_cognitive_state,
    run_cognition_before_action,
)
from mechanistic_mind.physical_system.composite_motor import select_factorized_side_channels
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime
from mechanistic_mind.research import predictive_compression as pc


def _O(**extra):
    base = {"exo_0": 0.12, "exo_1": 0.24, "exo_2": 0.36, "prop_neck_0": 0.01}
    base.update(extra)
    return base


def _state(*, left=True, right=False):
    cfg = CognitionConfig(
        prospective_composition=False,
        predictive_equivalence=False,
        temporal_predictive_structure=False,
        sensorimotor_consequence_model=True,
        composite_motor=True,
        retrieval=True,
        bounded_memory=True,
    )
    st = empty_cognitive_state(cfg)
    st["available_actions"] = list(
        available_actions(articulated_head=True, physical_push=True, oscillatory_signaling=True)
    )
    O = _O()
    if left:
        pc.observe(
            st["compression"], tick=1, fragment=O, action="NECK_LEFT",
            realized=_O(exo_0=0.4), domain="accessible",
        )
    if right:
        pc.observe(
            st["compression"], tick=1, fragment=O, action="NECK_RIGHT",
            realized=_O(exo_0=0.05), domain="accessible",
        )
    return st, O


def _neck_pick(st, preds, rng=0.5):
    neck, src, *_ = select_factorized_side_channels(
        available=list(st["available_actions"]),
        predictions=preds,
        rng_value=rng,
        articulated_head=True,
        oscillatory=True,
        physical_push=True,
    )
    return neck, src


def test_neck_retained_prediction_reachable():
    st, O = _state(left=True)
    res = run_cognition_before_action(st, observation=O, tick=2, rng_value=0.5)
    assert "NECK_LEFT" not in res.actions
    assert any(p.get("action") == "NECK_LEFT" for p in res.predictions)
    neck, src = _neck_pick(st, res.predictions, rng=0.5)
    assert src == "RETAINED_PREDICTION"
    assert neck == "NECK_LEFT"


def test_neck_endogenous_fallback_when_no_history():
    st, O = _state(left=False, right=False)
    res = run_cognition_before_action(st, observation=O, tick=2, rng_value=0.5)
    assert not any(str(p.get("action") or "").startswith("NECK_") for p in res.predictions)
    neck, src = _neck_pick(st, res.predictions, rng=0.5)
    assert src == "DEFAULT_NONE"
    assert neck == "NONE"
    neck_e, src_e = _neck_pick(st, res.predictions, rng=0.01)
    assert src_e == "ENDOGENOUS_VARIATION"
    assert neck_e.startswith("NECK_")


def test_neck_evidence_ablation_removes_support():
    st, O = _state(left=True)
    res = run_cognition_before_action(st, observation=O, tick=2, rng_value=0.5)
    _, src = _neck_pick(st, res.predictions, rng=0.5)
    assert src == "RETAINED_PREDICTION"
    st["compression"]["structures"] = {}
    res2 = run_cognition_before_action(st, observation=O, tick=3, rng_value=0.5)
    _, src2 = _neck_pick(st, res2.predictions, rng=0.5)
    assert src2 == "DEFAULT_NONE"


def test_same_optical_history_not_phototaxis():
    """Same O_t; only stored neck action differs → support differs."""
    st_l, O = _state(left=True, right=False)
    st_r, _ = _state(left=False, right=True)
    res_l = run_cognition_before_action(st_l, observation=O, tick=2, rng_value=0.5)
    res_r = run_cognition_before_action(st_r, observation=O, tick=2, rng_value=0.5)
    n_l, s_l = _neck_pick(st_l, res_l.predictions, rng=0.5)
    n_r, s_r = _neck_pick(st_r, res_r.predictions, rng=0.5)
    assert s_l == s_r == "RETAINED_PREDICTION"
    assert n_l == "NECK_LEFT"
    assert n_r == "NECK_RIGHT"


def test_locomotor_actions_unchanged():
    st, O = _state(left=True)
    res = run_cognition_before_action(st, observation=O, tick=2, rng_value=0.5)
    assert res.actions == ["WAIT", "MOVE:N", "MOVE:S", "MOVE:E", "MOVE:W"]
    assert res.selected_action in res.actions


def test_runtime_retained_reaches_head_physics():
    cfg = PhysicalSystemConfig()
    cfg.cognition.retrieval = True
    cfg.cognition.composite_motor = True
    cfg.cognition.prospective_composition = False
    cfg.articulated_head = ArticulatedHeadConfig(mode="EXPERIMENTAL")
    seed = 17
    rt = PhysicalSystemRuntime(seed=seed, config=cfg)
    rt._sync_embodiment_dofs()
    obs = rt.agent_observation()
    pc.observe(
        rt.cognition["compression"],
        tick=0,
        fragment=obs,
        action="NECK_LEFT",
        realized={**obs, "exo_0": min(1.0, float(obs.get("exo_0") or 0.0) + 0.2)},
        domain="accessible",
    )
    before = float(rt.body.head_relative_angle)
    rt.step()
    src = (rt.last_motor_output or {}).get("domain_sources", {}).get("neck")
    assert src == "RETAINED_PREDICTION"
    assert (rt.last_motor_output or {}).get("neck") == "NECK_LEFT"
    assert abs(float(rt.body.head_relative_angle) - before) > 1e-6 or abs(float(rt.body.neck_motor)) > 0.0


def test_wait_plus_neck_projects_last_action():
    cfg = PhysicalSystemConfig()
    cfg.cognition.retrieval = True
    cfg.cognition.composite_motor = True
    cfg.articulated_head = ArticulatedHeadConfig(mode="EXPERIMENTAL")
    rt = PhysicalSystemRuntime(seed=11, config=cfg)
    rt.step_forced_motor({"locomotion": "WAIT", "neck": "NECK_LEFT", "oscillator": {}, "push": False})
    assert rt.cognition.get("last_action") == "NECK_LEFT"
    rt.step_forced_motor({"locomotion": "MOVE:E", "neck": "NECK_RIGHT", "oscillator": {}, "push": False})
    assert rt.cognition.get("last_action") == "MOVE:E"


def test_sidechannel_tokens_not_in_locomotor_actions():
    st, O = _state(left=True)
    res = run_cognition_before_action(st, observation=O, tick=2, rng_value=0.5)
    for tok in ("OSC_EMIT", "PUSH", "NECK_LEFT"):
        assert tok not in res.actions
