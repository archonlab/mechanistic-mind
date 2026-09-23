"""Bilateral oscillatory channels in SMC — sensory extension only."""
from __future__ import annotations

import json
from pathlib import Path

from mechanistic_mind.physical_system import o_prime_history_bridge as ohb
from mechanistic_mind.physical_system import sensorimotor_consequence as smc
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig


def _base_obs(**extra):
    o = {k: 0.1 for k in smc.SENSORY_CHANNELS}
    o.update({f"osc_l_{i}": 0.2 for i in range(6)})
    o.update({f"osc_r_{i}": 0.5 for i in range(6)})
    o["local.FIELD_A"] = 0.3
    o.update(extra)
    return o


def test_exact_osc_keys_in_smc():
    assert smc.OSC_SENSORY_CHANNELS == tuple(f"osc_l_{i}" for i in range(6)) + tuple(
        f"osc_r_{i}" for i in range(6)
    )
    for k in smc.OSC_SENSORY_CHANNELS:
        assert k in smc.SENSORY_CHANNELS
    store = smc.empty_store(bilateral=True)
    for k in smc.OSC_SENSORY_CHANNELS:
        assert k in store["channel_list"]


def test_no_directional_logic_in_smc_module():
    src = Path(smc.__file__).read_text(encoding="utf-8")
    for forbidden in (
        "TURN_TOWARD",
        "source_direction",
        "target_bearing",
        "approach_signal",
        "SOURCE_LEFT",
        "SOURCE_RIGHT",
    ):
        assert forbidden not in src


def test_action_conditioned_bilateral_prediction_differentiated():
    store = smc.empty_store(enabled=True, bilateral=True)
    base = _base_obs()
    after_n = dict(base)
    after_e = dict(base)
    for i in range(6):
        after_n[f"osc_l_{i}"] = 0.05
        after_n[f"osc_r_{i}"] = 0.55
        after_e[f"osc_l_{i}"] = 0.55
        after_e[f"osc_r_{i}"] = 0.05
    mn = {"locomotion": "MOVE:N", "neck": "NONE", "oscillator": {}, "push": False}
    me = {"locomotion": "MOVE:E", "neck": "NONE", "oscillator": {}, "push": False}
    for t in range(5):
        smc.update(store, tick=t, observation_t=base, motor=mn, observation_t1=after_n)
        smc.update(store, tick=t + 20, observation_t=base, motor=me, observation_t1=after_e)
    pn = smc.query(store, observation=base, motor=mn)
    pe = smc.query(store, observation=base, motor=me)
    assert pn["status"] == "MATCH" and pe["status"] == "MATCH"
    assert pn["predicted_delta"]["osc_l_0"] != pe["predicted_delta"]["osc_l_0"]


def test_o_prime_carries_bilateral():
    store = smc.empty_store(enabled=True, bilateral=True)
    base = _base_obs()
    after = dict(base)
    after["osc_l_0"] = 0.01
    motor = {"locomotion": "MOVE:N", "neck": "NONE", "oscillator": {}, "push": False}
    for t in range(4):
        smc.update(store, tick=t, observation_t=base, motor=motor, observation_t1=after)
    pred = smc.query(store, observation=base, motor=motor)
    op = ohb.construct_o_prime(base, pred["predicted_delta"])
    assert "osc_l_0" in (op.get("predicted_fields") or [])


def test_withheld_excludes_osc_from_smc_keeps_field():
    store = smc.empty_store(enabled=True, bilateral=False)
    assert not any(c.startswith("osc_") for c in store["channel_list"])
    base = _base_obs()
    after = dict(base)
    after["local.FIELD_A"] = 0.6
    after["osc_l_0"] = 0.9  # physical change present but WITHHELD from SMC
    motor = {"locomotion": "WAIT", "neck": "NONE", "oscillator": {}, "push": False}
    for t in range(4):
        smc.update(store, tick=t, observation_t=base, motor=motor, observation_t1=after)
    pred = smc.query(store, observation=base, motor=motor)
    delta = pred.get("predicted_delta") or {}
    assert not any(k.startswith("osc_") for k in delta)
    assert "local.FIELD_A" in delta


def test_observer_panel_bilateral_status_and_exact_match():
    def traj(preset: str):
        s = ObserverSession(SessionConfig(seed=41, evidence_mode="SEARCH_COMPACT"))
        s.set_observer_detail_preset(preset)
        s.set_mechanism("sensorimotor_consequence_model", True)
        # bilateral default ON via CognitionConfig
        acts = []
        for _ in range(20):
            s.step()
            s.signal_sensorimotor_panel()
            acts.append(getattr(s.runtime, "last_action", None))
        return acts

    assert traj("MINIMAL") == traj("NORMAL") == traj("FULL")


def test_analyzer_detects_bilateral_in_mock(tmp_path: Path):
    from mechanistic_mind.scientific_v3.analyzer_next.signal_conditioned_selection import (
        aggregate_signal_conditioned_selection,
    )

    obs = tmp_path / "scientific_observations.jsonl"
    dec = tmp_path / "scientific_decisions.jsonl"
    obs.write_text(
        json.dumps(
            {
                "tick": 50,
                "cognitive_agent_id": "agent_0",
                "accessible": {
                    "local.FIELD_A": 0.2,
                    **{f"osc_l_{i}": 0.1 for i in range(6)},
                    **{f"osc_r_{i}": 0.4 for i in range(6)},
                },
            }
        )
        + "\n"
    )
    dec.write_text(
        json.dumps(
            {
                "tick": 50,
                "cognitive_agent_id": "agent_0",
                "selection_mode": "SCENARIO_COMPETITION",
                "selected_action_legacy": "MOVE:N",
                "candidate_count": 2,
                "sensorimotor_consequence": {
                    "predictions": [
                        {
                            "motor": "MOVE:N",
                            "status": "MATCH",
                            "support": 4,
                            "predicted_delta": {
                                "local.FIELD_A": 0.01,
                                "osc_l_0": -0.1,
                                "osc_r_0": 0.05,
                            },
                        },
                        {
                            "motor": "MOVE:E",
                            "status": "MATCH",
                            "support": 3,
                            "predicted_delta": {
                                "local.FIELD_A": -0.02,
                                "osc_l_0": 0.2,
                                "osc_r_0": -0.15,
                            },
                        },
                    ]
                },
                "historical_sensorimotor_selection": {
                    "enabled": True,
                    "withheld_from_psc": False,
                    "n_history_match": 2,
                    "history_support_differentiated": True,
                    "candidates": [
                        {"candidate_locomotion": "MOVE:N", "history_status": "MATCH", "available_to_psc": True},
                        {"candidate_locomotion": "MOVE:E", "history_status": "MATCH", "available_to_psc": True},
                    ],
                },
            }
        )
        + "\n"
    )
    payload = aggregate_signal_conditioned_selection(tmp_path)
    assert payload["funnel"]["BILATERAL_SMC_PREDICTIONS_AVAILABLE"] >= 1
    assert payload["funnel"]["BILATERAL_FUTURES_DIFFERENTIATED"] >= 1
    assert payload["gates"]["GATE_LR_bands_reach_SMC"] == "PASS"
    assert payload["osc_bands_in_SMC"] is True
