"""Read-only Beta 3.1 mechanism integrity probes. No production patches."""
from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from mechanistic_mind.physical_system.actions import available_actions, CANONICAL_ACTIONS
from mechanistic_mind.physical_system.articulated_head import ArticulatedHeadConfig
from mechanistic_mind.physical_system.cognition import CognitionConfig, empty_cognitive_state, run_cognition_before_action
from mechanistic_mind.physical_system.experiment_canonical import beta31_mechanism_map, preset_canonical
from mechanistic_mind.physical_system.mechanism_configuration import (
    EXPERIMENTAL_COGNITION_EXCLUDE,
    WORLD_SUBSYSTEM_IDS,
    fresh_experiment_default_map,
)
from mechanistic_mind.physical_system.mechanism_registry import MECHANISM_DEFS
from mechanistic_mind.physical_system.oscillatory_signaling import OscillatorySignalingConfig
from mechanistic_mind.physical_system.physical_push import PhysicalPushConfig
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.physical_system.vestibular_proprioception import (
    NeckProprioceptionConfig,
    VestibularConfig,
)
from mechanistic_mind.research import contextual_stack_bridge as csb

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "beta31_full_mechanism_integrity_audit"
OUT.mkdir(parents=True, exist_ok=True)

PROBE_TICKS = 0


def _count(n: int) -> int:
    global PROBE_TICKS
    PROBE_TICKS += n
    return n


def _embodied(cognition=True) -> PhysicalSystemConfig:
    cfg = PhysicalSystemConfig()
    cfg.cognition.cognition_enabled = cognition
    cfg.cognition.composite_motor = True
    cfg.articulated_head = ArticulatedHeadConfig(mode="EXPERIMENTAL")
    cfg.physical_push = PhysicalPushConfig(mode="EXPERIMENTAL")
    cfg.oscillatory_signaling = OscillatorySignalingConfig(mode="EXPERIMENTAL")
    cfg.vestibular = VestibularConfig(mode="EXPERIMENTAL")
    cfg.neck_proprioception = NeckProprioceptionConfig(mode="EXPERIMENTAL")
    return cfg


def probe_smc_and_426():
    cfg = _embodied(True)
    cfg.cognition.sensorimotor_consequence_model = True
    cfg.cognition.historical_sensorimotor_selection_bridge = True
    cfg.cognition.contextual_predictive_organization = True
    cfg.cognition.context_grounded_prospection = True
    cfg.cognition.persistent_prospective_control = True
    rt = PhysicalSystemRuntime(seed=112, config=cfg)
    for _ in range(3):
        rt.begin_tick()
        rt.finish_tick()
    _count(3)
    cog = rt.cognition
    smc = cog.get("sensorimotor_consequence")
    sel = cog.get("last_selection") or {}
    return {
        "ticks": 3,
        "smc_store_present": isinstance(smc, dict),
        "smc_updates": (smc or {}).get("updates") if isinstance(smc, dict) else None,
        "smc_records": len((smc or {}).get("records") or {}) if isinstance(smc, dict) else 0,
        "cpo_store_present": isinstance(cog.get("contextual_organization"), dict),
        "cgp_store_present": isinstance(cog.get("context_grounded_prospection"), dict),
        "ppc_store_present": isinstance(cog.get("persistent_prospective_control"), dict),
        "o_prime_in_last_selection": bool(sel.get("o_prime_history_bridge") or sel.get("o_prime_history_candidates")),
        "hss_enabled_on_selection": bool((sel.get("o_prime_history_bridge") or {}).get("enabled")),
        "smc_enabled_on_selection": bool((sel.get("sensorimotor_consequence") or {}).get("enabled")),
        "cpo_recent": len((cog.get("contextual_organization") or {}).get("recent_coactive") or []),
        "cpo_enabled": bool((cog.get("contextual_organization") or {}).get("enabled")),
        "cgp_enabled": bool((cog.get("context_grounded_prospection") or {}).get("enabled")),
        "ppc_enabled": bool((cog.get("persistent_prospective_control") or {}).get("enabled")),
        "csb_last_selection": bool(sel.get("contextual_stack")),
        "csb_imported_by_cognition": "contextual_stack_bridge" in Path(
            ROOT / "mechanistic_mind/physical_system/cognition.py"
        ).read_text(),
        "motor_selection_source": (rt.last_motor_output or {}).get("selection_source"),
        "osc_domain": ((rt.last_motor_output or {}).get("domain_sources") or {}).get("oscillator"),
        "neck_domain": ((rt.last_motor_output or {}).get("domain_sources") or {}).get("neck"),
        "push_domain": ((rt.last_motor_output or {}).get("domain_sources") or {}).get("push"),
        "compose_candidates": list((sel.get("candidates") or [])[:8]),
        "obs_keys_sample": sorted(k for k in (rt.last_agent_observation or {}) if str(k).startswith(("exo_", "osc_", "vest_", "prop_", "local.FIELD", "spatial_"))),
    }


def probe_neck():
    cfg = _embodied(False)
    rt = PhysicalSystemRuntime(seed=3, config=cfg)
    ang0 = float(rt.body.head_relative_angle)
    obs0 = rt.agent_observation()
    rt.step_forced_motor({
        "locomotion": "WAIT", "neck": "NECK_RIGHT",
        "oscillator": {"frequency_delta": 0, "amplitude_delta": 0, "emit_trigger": False},
        "push": False,
    })
    _count(1)
    obs1 = rt.agent_observation()
    return {
        "head_angle_changed": abs(float(rt.body.head_relative_angle) - ang0) > 1e-12 or abs(float(rt.body.head_omega)) > 1e-12,
        "prop_neck_keys": [k for k in obs1 if str(k).startswith("prop_neck_")],
        "prop_changed": any(abs(float(obs1.get(k, 0)) - float(obs0.get(k, 0))) > 1e-12 for k in obs1 if str(k).startswith("prop_neck_")),
        "body_theta": float(rt.body.theta),
    }


def probe_push():
    cfg = _embodied(False)
    sys = TwoAgentRuntime(seed=5, config=cfg, starts=((8, 8), (8, 8)), contact_enabled=True)
    sys.slots[0]._forced_motor_once = {
        "locomotion": "WAIT", "neck": "NONE",
        "oscillator": {"frequency_delta": 0, "amplitude_delta": 0, "emit_trigger": False},
        "push": True,
    }
    sys.step()
    _count(1)
    mo = sys.slots[0].last_motor_output or {}
    return {
        "push_component": bool(mo.get("push")),
        "contact": bool((sys.last_contact or {}).get("contact")) if isinstance(sys.last_contact, dict) else sys.last_contacts != [],
        "apply_push": (sys.slots[0].last_motor_apply or {}).get("push"),
    }


def probe_vestibular():
    cfg = _embodied(False)
    rt = PhysicalSystemRuntime(seed=8, config=cfg)
    obs0 = rt.agent_observation()
    rt.body.omega = 1.2
    rt.finish_tick() if False else None
    rt.begin_tick()
    rt.finish_tick()
    _count(1)
    obs1 = rt.last_agent_observation or rt.agent_observation()
    vest = [k for k in obs1 if str(k).startswith("vest_")]
    return {
        "vest_keys": vest,
        "vest_changed": any(abs(float(obs1.get(k, 0)) - float(obs0.get(k, 0))) > 1e-9 for k in vest),
        "vest0": float(obs1.get("vest_0", 0)),
    }


def _site_sum(body, attr: str) -> float:
    arr = getattr(body, attr, None)
    if arr is None:
        return 0.0
    return float(np.asarray(arr).sum())


def probe_ecology_and_field():
    from mechanistic_mind.model.tiktaalik import tiktaalik_config

    cfg = tiktaalik_config()
    cfg.cognition.cognition_enabled = False
    cfg.articulated_head = ArticulatedHeadConfig(mode="EXPERIMENTAL")
    cfg.oscillatory_signaling = OscillatorySignalingConfig(mode="EXPERIMENTAL")
    sys = TwoAgentRuntime(seed=6, config=cfg, starts=((8, 8), (12, 8)), signal_enabled=True)
    a0 = sys.slots[0]
    ra0 = _site_sum(a0.body, "R_A_site")
    work0 = float(getattr(a0.body, "mechanical_work_reservoir", 0.0) or 0.0)
    sys.inject_source(channel="A", amplitude=1.0, slot=0)
    sys.step()
    _count(1)
    obs = a0.agent_observation()
    ra1 = _site_sum(a0.body, "R_A_site")
    work1 = float(getattr(a0.body, "mechanical_work_reservoir", 0.0) or 0.0)
    return {
        "field_a_obs": float(obs.get("local.FIELD_A") or 0.0),
        "field_key_present": "local.FIELD_A" in obs,
        "R_A_delta": ra1 - ra0,
        "work_delta": work1 - work0,
        "planet_has_RA": getattr(sys.world, "R_A", None) is not None,
    }


def probe_unknown_action():
    cfg = CognitionConfig(unknown_action_physical_probe=True)
    st = empty_cognitive_state(cfg)
    r = run_cognition_before_action(st, observation={"local.T": 0.2, "exo_0": 0.1}, tick=0, rng_value=0.2)
    _count(0)
    info = (st.get("last_selection") or {}).get("unknown_action_probe") or {}
    return {
        "enabled": bool(info.get("enabled")),
        "unmodeled": list(info.get("unmodeled_first_actions") or [])[:8],
        "selection_effect": info.get("selection_effect"),
        "arbitration": info.get("arbitration"),
        "selected_unchanged_boundary": info.get("selected_probe_action") is None,
        "compose_actions": list(r.actions),
    }


def probe_csb_isolated():
    """Direct bridge still works; production cognition now also calls it (post wiring repair)."""
    cfg = CognitionConfig(
        contextual_predictive_organization=True,
        context_grounded_prospection=True,
        persistent_prospective_control=True,
    )
    st = empty_cognitive_state(cfg)
    obs0 = {"exo_0": 0.2, "local.T": 0.4}
    obs1 = {"exo_0": 0.6, "local.T": 0.41}
    d = csb.on_experience(st, tick=1, previous=obs0, observation=obs1, previous_action="WAIT", cfg=cfg.to_dict())
    _count(0)
    return {
        "on_experience_returns": bool(d),
        "cpo_after_direct_call": bool((st.get("contextual_organization") or {}).get("enabled")),
        "cpo_formed": d.get("cpo_formed"),
    }


def probe_select_observed_unused():
    src = (ROOT / "mechanistic_mind/physical_system/cognition.py").read_text()
    rsrc = (ROOT / "mechanistic_mind/physical_system/runtime.py").read_text()
    return {
        "cognition_calls_select_observed": "select_observed_composite_motor" in src,
        "runtime_calls_select_observed": "select_observed_composite_motor" in rsrc,
        "cognition_calls_smc_update": "smc.update" in src or "sensorimotor_consequence.update" in src,
        "cognition_calls_csb": "contextual_stack_bridge" in src,
        "factorized_helper_present": "_factorized_composite_from_cognition" in rsrc,
    }


def main():
    stock = preset_canonical("TIKTAALIK_BETA31", seed=112)
    fresh = fresh_experiment_default_map()
    research_on = {
        "prospective_scenario_competition": True,
        "unknown_action_physical_probe": True,
        "predictive_equivalence": True,
        "predictive_relevance": True,
        "temporal_predictive_structure": True,
        "temporal_prospection_bridge": True,
        "predictive_conflict": True,
        "future_sensitive_action": True,
        "prediction_error_revision": True,
        "temporal_prediction_error": True,
        "predicted_context_prospection": True,
        "multistep_action_prospection": True,
    }
    wiring = probe_select_observed_unused()
    smc_p = probe_smc_and_426()
    neck = probe_neck()
    push = probe_push()
    vest = probe_vestibular()
    eco = probe_ecology_and_field()
    uap = probe_unknown_action()
    csb_p = probe_csb_isolated()
    payload = {
        "probe_ticks": PROBE_TICKS,
        "stock_beta31": stock["mechanisms"],
        "fresh_defaults_excerpt": {k: fresh.get(k) for k in ("prospective_scenario_competition", "predictive_equivalence", "oscillatory_signaling")},
        "research_overrides_from_analyzer": research_on,
        "wiring": wiring,
        "smc_cpo_path": smc_p,
        "neck": neck,
        "push": push,
        "vestibular": vest,
        "ecology_field": eco,
        "unknown_action_probe": uap,
        "csb_direct": csb_p,
        "canonical_five": list(CANONICAL_ACTIONS),
        "osc_in_flagged_repertoire": "OSC_EMIT" in available_actions(oscillatory_signaling=True),
    }
    (OUT / "targeted_probe_results.json").write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({"probe_ticks": PROBE_TICKS, "smc_present": smc_p["smc_store_present"], "cpo_present": smc_p["cpo_store_present"], "factorized": wiring["factorized_helper_present"]}, indent=2))


if __name__ == "__main__":
    main()
