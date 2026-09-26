"""Tiny, test-only forensic for the Beta 3.1 factorized side-channel path.

This test instruments the existing selector by monkeypatching the runtime module.
It does not add production telemetry or change selection behavior.
"""
from __future__ import annotations

from copy import deepcopy

import numpy as np

from mechanistic_mind.physical_system.articulated_head import ArticulatedHeadConfig
from mechanistic_mind.physical_system.oscillatory_signaling import OscillatorySignalingConfig
from mechanistic_mind.physical_system.physical_push import PhysicalPushConfig
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
import mechanistic_mind.physical_system.runtime as runtime_module


def _config() -> PhysicalSystemConfig:
    cfg = PhysicalSystemConfig()
    cfg.cognition.cognition_enabled = True
    cfg.cognition.composite_motor = True
    cfg.articulated_head = ArticulatedHeadConfig(mode="EXPERIMENTAL")
    cfg.physical_push = PhysicalPushConfig(mode="EXPERIMENTAL")
    cfg.oscillatory_signaling = OscillatorySignalingConfig(mode="EXPERIMENTAL")
    return cfg


def _diagnostic(monkeypatch, ticks: int = 4) -> list[dict]:
    calls: list[dict] = []
    original = runtime_module.select_factorized_side_channels

    def traced(**kwargs):
        result = original(**kwargs)
        neck, neck_source, osc, osc_source, push, push_source = result
        available = list(kwargs["available"])
        predictions = deepcopy(list(kwargs["predictions"]))
        calls.append({
            "available": available,
            "predictions": predictions,
            "rng_value": kwargs["rng_value"],
            "enabled": {
                "neck": kwargs["articulated_head"],
                "osc": kwargs["oscillatory"],
                "push": kwargs["physical_push"],
            },
            "repertoire": {
                "neck": [a for a in available if a.startswith("NECK_")],
                "osc": [a for a in available if a.startswith("OSC_")],
                "push": [a for a in available if a == "PUSH"],
            },
            "selected": {
                "neck": neck,
                "neck_source": neck_source,
                "osc": osc.to_dict(),
                "osc_source": osc_source,
                "push": push,
                "push_source": push_source,
            },
        })
        return result

    monkeypatch.setattr(runtime_module, "select_factorized_side_channels", traced)
    system = TwoAgentRuntime(seed=112, config=_config(), starts=((8, 16), (12, 16)))
    rows: list[dict] = []
    for tick in range(ticks):
        before_calls = len(calls)
        before = [deepcopy(slot.last_motor_output) for slot in system.slots]
        system.step()
        assert len(calls) - before_calls == 2
        for agent, slot in enumerate(system.slots):
            call = calls[before_calls + agent]
            motor = deepcopy(slot.last_motor_output)
            obs = slot.agent_observation()
            rows.append({
                "tick": tick,
                "agent": agent,
                "factorized_selector_called": True,
                "call": call,
                "composite_before_factorization": before[agent],
                "composite_after_factorization": motor,
                "motor_apply": deepcopy(slot.last_motor_apply),
                "physical_after": {
                    "head_relative_angle": float(slot.body.head_relative_angle),
                    "head_omega": float(slot.body.head_omega),
                    "neck_motor": float(slot.body.neck_motor),
                    "osc_emit_remaining": int(slot.body.osc_emit_remaining),
                    "osc_emit_active": float(slot.body.osc_emit_active),
                    "push_exertion": float(slot.body.push_exertion),
                    "world_osc_energy": float(np.asarray(system.world.OSC_BANDS).sum()),
                },
                "next_observation": {
                    "prop_neck_0": obs.get("prop_neck_0"),
                    "prop_neck_1": obs.get("prop_neck_1"),
                    "osc_l": [obs[k] for k in sorted(obs) if k.startswith("osc_l_")],
                    "osc_r": [obs[k] for k in sorted(obs) if k.startswith("osc_r_")],
                },
            })
    return rows


def test_fresh_process_factorized_path_is_called_once_per_agent_tick_and_deterministic(monkeypatch):
    first = _diagnostic(monkeypatch)
    monkeypatch.undo()
    second = _diagnostic(monkeypatch)
    assert first == second
    assert len(first) == 8
    assert all(row["composite_after_factorization"]["selection_source"] == "COMPOSITE_FACTORIZED" for row in first)
    assert all(row["call"]["enabled"].values() for row in first)
    assert all(row["call"]["repertoire"]["neck"] for row in first)
    assert all(row["call"]["repertoire"]["osc"] for row in first)
    assert all(row["call"]["repertoire"]["push"] for row in first)
    # Seed 112/113 start inside the existing neck endogenous-variation interval.
    assert all(row["composite_after_factorization"]["neck"] != "NONE" for row in first)

