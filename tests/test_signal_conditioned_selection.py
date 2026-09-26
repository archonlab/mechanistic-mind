"""SIGNAL-CONDITIONED SENSORIMOTOR SELECTION — Analyzer + Observer product."""
from __future__ import annotations

import json
from pathlib import Path

from mechanistic_mind.scientific_v3.analyzer_next.signal_conditioned_selection import (
    SMC_SIGNAL_CHANNELS,
    aggregate_signal_conditioned_selection,
    _futures_differentiated,
    _signal_delta_from_pred,
)
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig
from mechanistic_mind.ui.psy_observer_web.subscriptions import PRODUCT_SIGNAL_SENSORIMOTOR


def test_smc_channels_exclude_osc_bands():
    assert "local.FIELD_A" in SMC_SIGNAL_CHANNELS
    assert "local.FIELD_B" in SMC_SIGNAL_CHANNELS
    assert all(not c.startswith("osc_") for c in SMC_SIGNAL_CHANNELS)


def test_signal_delta_extracts_field_only():
    pred = {
        "predicted_delta": {
            "local.FIELD_A": 0.1,
            "exo_0": 0.5,
            "osc_l_0": 0.9,  # must be ignored even if present
        }
    }
    sd = _signal_delta_from_pred(pred)
    assert sd == {"local.FIELD_A": 0.1}
    assert "osc_l_0" not in sd


def test_futures_differentiated():
    preds = [
        {"predicted_delta": {"local.FIELD_A": 0.1, "local.FIELD_B": 0.0}},
        {"predicted_delta": {"local.FIELD_A": 0.2, "local.FIELD_B": 0.0}},
    ]
    assert _futures_differentiated(preds) is True
    same = [
        {"predicted_delta": {"local.FIELD_A": 0.1}},
        {"predicted_delta": {"local.FIELD_A": 0.1}},
    ]
    assert _futures_differentiated(same) is False


def test_aggregator_from_mock_run(tmp_path: Path):
    obs = tmp_path / "scientific_observations.jsonl"
    dec = tmp_path / "scientific_decisions.jsonl"
    obs.write_text(
        json.dumps({
            "tick": 10,
            "cognitive_agent_id": "agent_1",
            "accessible": {
                "local.FIELD_A": 0.4,
                "local.FIELD_B": 0.0,
                "osc_l_0": 0.1,
                "osc_r_0": 0.3,
            },
        })
        + "\n"
    )
    dec.write_text(
        json.dumps({
            "tick": 10,
            "cognitive_agent_id": "agent_1",
            "selection_mode": "SCENARIO_COMPETITION",
            "selected_action_legacy": "MOVE:N",
            "candidate_count": 2,
            "sensorimotor_consequence": {
                "predictions": [
                    {
                        "motor": "MOVE:N",
                        "status": "MATCH",
                        "support": 3,
                        "predicted_delta": {"local.FIELD_A": 0.05, "local.FIELD_B": 0.0},
                    },
                    {
                        "motor": "MOVE:E",
                        "status": "MATCH",
                        "support": 2,
                        "predicted_delta": {"local.FIELD_A": -0.02, "local.FIELD_B": 0.0},
                    },
                ]
            },
            "historical_sensorimotor_selection": {
                "enabled": True,
                "withheld_from_psc": False,
                "n_history_match": 2,
                "history_support_differentiated": True,
                "selection_differs_from_withheld_cf": True,
                "candidates": [
                    {"candidate_locomotion": "MOVE:N", "history_status": "MATCH", "available_to_psc": True},
                    {"candidate_locomotion": "MOVE:E", "history_status": "MATCH", "available_to_psc": True},
                ],
            },
        })
        + "\n"
    )
    payload = aggregate_signal_conditioned_selection(tmp_path)
    assert payload["status"] == "RECORDED"
    assert payload["osc_bands_in_SMC"] is False
    assert payload["gates"]["GATE_A_signal_join_to_SMC"] == "PASS"
    assert payload["gates"]["GATE_B_differentiated_signal_futures"] == "PASS"
    assert payload["gates"]["GATE_LR_bands_reach_SMC"] == "NOT_DEMONSTRATED"
    assert "source_id" not in json.dumps(payload)
    assert "OTHER_AGENT" not in json.dumps(payload)


def test_minimal_defers_panel_product():
    s = ObserverSession(SessionConfig(seed=3, evidence_mode="SEARCH_COMPACT"))
    s.set_observer_detail_preset("MINIMAL")
    for _ in range(3):
        s.step()
    p = s.signal_sensorimotor_panel()
    assert p.get("status") == "DEFERRED"
    s.set_observer_detail_preset("NORMAL")
    p2 = s.signal_sensorimotor_panel()
    assert p2.get("status") != "DEFERRED"
    assert "signal_input" in p2
    assert PRODUCT_SIGNAL_SENSORIMOTOR


def test_exact_match_unaffected_by_panel():
    def traj(preset: str):
        s = ObserverSession(SessionConfig(seed=19, evidence_mode="SEARCH_COMPACT"))
        s.set_observer_detail_preset(preset)
        s.set_mechanism("sensorimotor_consequence_model", True)
        acts = []
        for _ in range(25):
            s.step()
            if hasattr(s, "signal_sensorimotor_panel"):
                s.signal_sensorimotor_panel()
            acts.append(getattr(s.runtime, "last_action", None) or getattr(s, "last_actions", None))
        return acts

    a = traj("MINIMAL")
    b = traj("NORMAL")
    c = traj("FULL")
    assert a == b == c
