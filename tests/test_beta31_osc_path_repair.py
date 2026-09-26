"""Beta 3.1 OSC path repair: physical plumbing + factorized cognitive reachability.

Does not change PSC scores or force autonomous OSC in naturalistic ticks.
"""
from __future__ import annotations

import time
from types import SimpleNamespace

import numpy as np
import pytest

from mechanistic_mind.physical_system.actions import CANONICAL_ACTIONS, available_actions
from mechanistic_mind.physical_system.articulated_head import ArticulatedHeadConfig
from mechanistic_mind.physical_system.cognition import CognitionConfig, run_cognition_before_action
from mechanistic_mind.physical_system.composite_motor import select_factorized_side_channels
from mechanistic_mind.physical_system.oscillatory_signaling import OscillatorySignalingConfig
from mechanistic_mind.physical_system.physical_push import PhysicalPushConfig
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime


def _osc_cfg(**kw) -> OscillatorySignalingConfig:
    return OscillatorySignalingConfig(mode="EXPERIMENTAL", duration_base=8, **kw)


def _embodied(*, osc: bool = True, cognition: bool = False) -> PhysicalSystemConfig:
    cfg = PhysicalSystemConfig()
    cfg.cognition.cognition_enabled = bool(cognition)
    cfg.cognition.composite_motor = True
    cfg.articulated_head = ArticulatedHeadConfig(mode="EXPERIMENTAL")
    cfg.physical_push = PhysicalPushConfig(mode="EXPERIMENTAL")
    cfg.oscillatory_signaling = _osc_cfg() if osc else OscillatorySignalingConfig(mode="OFF")
    return cfg


def test_compose_does_not_include_osc_actions():
    """SHOULD_OSC_EXIST_IN_COMPOSE_ACTIONS = NO."""
    cfg = CognitionConfig()
    from mechanistic_mind.physical_system.cognition import empty_cognitive_state

    st = empty_cognitive_state(cfg)
    st["available_actions"] = list(
        available_actions(articulated_head=True, physical_push=True, oscillatory_signaling=True)
    )
    r = run_cognition_before_action(
        st, observation={"local.T": 0.1}, tick=0, rng_value=0.3,
    )
    assert tuple(r.actions) == CANONICAL_ACTIONS
    assert "OSC_EMIT" not in r.actions
    assert "NECK_LEFT" not in r.actions
    assert "PUSH" not in r.actions


def test_physical_osc_pipeline_two_bodies():
    cfg = _embodied(cognition=False)
    sys = TwoAgentRuntime(seed=9, config=cfg, starts=((8, 8), (9, 8)), signal_enabled=False)
    a0, a1 = sys.slots
    a0.body.theta = 0.0
    a1.body.theta = 0.0
    a0.body.osc_amp_u = 1.0
    a0._forced_motor_once = {
        "locomotion": "WAIT",
        "neck": "NONE",
        "oscillator": {"frequency_delta": 0, "amplitude_delta": 0, "emit_trigger": True},
        "push": False,
    }
    sys.step()
    energy = float(np.asarray(sys.world.OSC_BANDS).sum())
    obs1 = a1.agent_observation()
    osc_l = [obs1[k] for k in obs1 if k.startswith("osc_l_")]
    osc_r = [obs1[k] for k in obs1 if k.startswith("osc_r_")]
    assert int(a0.body.osc_emit_remaining) >= 0
    assert energy > 0.0
    assert osc_l and osc_r
    assert max(osc_l + osc_r) > 0.0
    # Control: no emit
    sys2 = TwoAgentRuntime(seed=9, config=cfg, starts=((8, 8), (9, 8)), signal_enabled=False)
    sys2.slots[0]._forced_motor_once = {
        "locomotion": "WAIT",
        "neck": "NONE",
        "oscillator": {"frequency_delta": 0, "amplitude_delta": 0, "emit_trigger": False},
        "push": False,
    }
    sys2.step()
    e2 = float(np.asarray(sys2.world.OSC_BANDS).sum()) if getattr(sys2.world, "OSC_BANDS", None) is not None else 0.0
    obs_c = sys2.slots[1].agent_observation()
    assert e2 < 1e-9
    assert max((obs_c.get(k, 0.0) for k in obs_c if str(k).startswith("osc_")), default=0.0) < 1e-9


def test_physical_osc_off_no_emission_or_channels():
    cfg = _embodied(osc=False, cognition=False)
    sys = TwoAgentRuntime(seed=9, config=cfg, starts=((8, 8), (9, 8)), signal_enabled=False)
    sys.slots[0]._forced_motor_once = {
        "locomotion": "WAIT",
        "neck": "NONE",
        "oscillator": {"frequency_delta": 0, "amplitude_delta": 0, "emit_trigger": True},
        "push": False,
    }
    sys.step()
    assert getattr(sys.world, "OSC_BANDS", None) is None or float(np.asarray(sys.world.OSC_BANDS).sum()) < 1e-12
    obs = sys.slots[1].agent_observation()
    assert not any(k.startswith("osc_l_") or k.startswith("osc_r_") for k in obs)
    src = (sys.slots[0].last_motor_apply or {}).get("oscillator") or {}
    assert src.get("enabled") is False or "emit" not in (src.get("detail") or {})


def test_cognitive_osc_component_reachable_via_retained_prediction():
    cfg = _embodied(cognition=True)
    rt = PhysicalSystemRuntime(seed=11, config=cfg)
    rt._sync_embodiment_dofs()
    avail = list(rt.cognition.get("available_actions") or [])
    assert "OSC_EMIT" in avail
    fake = SimpleNamespace(
        predictions=[{
            "action": "OSC_EMIT",
            "source": "compression",
            "result": {"status": "MATCH", "predicted": {"osc_l_0": 0.4}},
        }],
        selection_source="TEST_LOCO",
    )
    motor = rt._factorized_composite_from_cognition(selected="WAIT", cognition_result=fake)
    assert motor.oscillator.emit_trigger is True
    assert motor.locomotion == "WAIT"
    assert motor.selection_source == "COMPOSITE_FACTORIZED"
    rt.step_forced_motor(motor.to_dict())
    assert int(rt.body.osc_emit_remaining) > 0


def test_factorized_osc_unavailable_when_mechanism_off():
    cfg = _embodied(osc=False, cognition=True)
    rt = PhysicalSystemRuntime(seed=11, config=cfg)
    rt._sync_embodiment_dofs()
    avail = list(rt.cognition.get("available_actions") or [])
    assert "OSC_EMIT" not in avail
    fake = SimpleNamespace(
        predictions=[{
            "action": "OSC_EMIT",
            "source": "compression",
            "result": {"status": "MATCH", "predicted": {"osc_l_0": 0.4}},
        }],
        selection_source="TEST_LOCO",
    )
    motor = rt._factorized_composite_from_cognition(selected="MOVE:E", cognition_result=fake)
    assert motor.oscillator.emit_trigger is False
    assert (motor.domain_sources or {}).get("oscillator") == "UNAVAILABLE"


def test_begin_tick_exposes_osc_side_channel_not_unavail():
    cfg = _embodied(cognition=True)
    rt = PhysicalSystemRuntime(seed=21, config=cfg)
    rt.begin_tick()
    mo = rt.last_motor_output or {}
    assert mo.get("selection_source") == "COMPOSITE_FACTORIZED"
    osc_src = (mo.get("domain_sources") or {}).get("oscillator")
    assert osc_src != "UNAVAILABLE"
    assert "OSC_EMIT" in (rt.cognition.get("available_actions") or [])
    # Compose still locomotor-only
    sel = rt.cognition.get("last_selection") or {}
    cands = list(sel.get("candidates") or [])
    assert "OSC_EMIT" not in cands
    rt.finish_tick()


def test_legacy_field_unaffected_by_osc_on():
    cfg = _embodied(osc=True, cognition=False)
    sys = TwoAgentRuntime(
        seed=3, config=cfg, starts=((8, 8), (10, 8)), signal_enabled=True,
    )
    sys.inject_source(channel="A", amplitude=1.0, slot=0)
    sys.step()
    obs = sys.slots[1].agent_observation()
    assert "local.FIELD_A" in obs
    assert float(obs.get("local.FIELD_A") or 0.0) >= 0.0


def test_wait_move_repertoire_unchanged():
    cfg = _embodied(cognition=True)
    rt = PhysicalSystemRuntime(seed=4, config=cfg)
    rt.begin_tick()
    mo = rt.last_motor_output or {}
    assert mo.get("locomotion") in {"WAIT", "MOVE:N", "MOVE:S", "MOVE:E", "MOVE:W"}
    rt.finish_tick()


def test_determinism_forced_osc_and_factorized_idle():
    def forced_pair():
        cfg = _embodied(cognition=False)
        sys = TwoAgentRuntime(seed=41, config=cfg, starts=((8, 8), (9, 8)))
        sys.slots[0].body.osc_amp_u = 0.8
        sys.slots[0]._forced_motor_once = {
            "locomotion": "WAIT",
            "neck": "NONE",
            "oscillator": {"frequency_delta": 0, "amplitude_delta": 0, "emit_trigger": True},
            "push": False,
        }
        sys.step()
        obs = sys.slots[1].agent_observation()
        bands = tuple(float(x) for x in np.asarray(sys.world.OSC_BANDS).ravel()[:24])
        osc = tuple(round(obs[k], 8) for k in sorted(obs) if str(k).startswith("osc_"))
        return bands, osc

    assert forced_pair() == forced_pair()

    def idle_pair():
        cfg = _embodied(cognition=True)
        rt = PhysicalSystemRuntime(seed=55, config=cfg)
        rows = []
        for _ in range(5):
            rt.begin_tick()
            mo = rt.last_motor_output or {}
            osc = mo.get("oscillator") or {}
            rows.append((
                mo.get("locomotion"),
                bool(osc.get("emit_trigger")),
                int(osc.get("frequency_delta") or 0),
                int(osc.get("amplitude_delta") or 0),
            ))
            rt.finish_tick()
        return rows

    assert idle_pair() == idle_pair()


def test_analogue_restored_run_path_available_no_emergence_requirement():
    """Seed 112 analogue (original 80e3abc6 artifacts not on disk). 20 ticks."""
    cfg = _embodied(cognition=True)
    sys = TwoAgentRuntime(seed=112, config=cfg, starts=((8, 16), (12, 16)))
    n_emit = 0
    for _ in range(20):
        sys.step()
        for sl in sys.slots:
            mo = sl.last_motor_output or {}
            src = (mo.get("domain_sources") or {}).get("oscillator")
            assert src != "UNAVAILABLE"
            if (mo.get("oscillator") or {}).get("emit_trigger"):
                n_emit += 1
    # Autonomous emit may be zero; path available is the gate.
    assert n_emit >= 0


def test_tiny_perf_not_pathological():
    cfg = _embodied(cognition=True)
    rt = PhysicalSystemRuntime(seed=2, config=cfg)
    t0 = time.perf_counter()
    for _ in range(8):
        rt.begin_tick()
        rt.finish_tick()
    ms = (time.perf_counter() - t0) / 8 * 1000.0
    assert ms < 500.0  # sanity only; Beta 3.1 perf is frozen
