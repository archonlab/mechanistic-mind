"""SMC + O′ historical-selection evidence on ordinary SCIENTIFIC_V3 DecisionReceipts."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from mechanistic_mind.physical_system.cognition import (
    CognitionConfig,
    empty_cognitive_state,
    run_cognition_before_action,
)
from mechanistic_mind.scientific_v3.receipts import build_decision_receipt
from mechanistic_mind.scientific_v3.analyzer_next.smc_hss_from_decisions import (
    aggregate_sensorimotor_consequence_model,
    aggregate_historical_sensorimotor_selection,
)
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig


def _obs(t: int = 0):
    return {
        "exo_0": 0.3, "exo_1": 0.2 + (t % 5) * 0.05, "exo_2": 0.3,
        "local.FIELD_A": 0.3, "local.FIELD_B": 0.3,
        "vest_0": 0.5, "vest_1": 0.5,
        "prop_neck_0": 0.5, "prop_neck_1": 0.5,
        "body.T": 0.4, "body.B0": 0.1, "body.B1": 0.1, "body.B2": 0.1,
        "body.mech": 0.0, "body.vx": 0.5, "body.vy": 0.5,
        "local.T": 0.4, "local.M0": 0.1, "local.M1": 0.1, "local.M2": 0.1,
        "local.vx": 0.5, "local.vy": 0.5,
    }


def test_decision_receipt_includes_smc_and_hss_fields():
    cfg = CognitionConfig(
        sensorimotor_consequence_model=True,
        historical_sensorimotor_selection_bridge=True,
        prospective_selection="SCENARIO_COMPETITION",
    )
    st = empty_cognitive_state(cfg)
    for t in range(1, 25):
        run_cognition_before_action(st, observation=_obs(t), tick=t, rng_value=0.41)
    sel = st["last_selection"]
    rec = build_decision_receipt(
        run_id="runX",
        tick=24,
        cognitive_agent_id="agent_0",
        physical_body_id="body-0",
        observation_id_value="o",
        motor_id_value="m",
        last_selection=sel,
        selected_action=sel.get("action"),
        selection_source=sel.get("source"),
        selection_rule=sel.get("selection_rule"),
    )
    smc = rec["sensorimotor_consequence"]
    assert smc.get("enabled") is True
    assert isinstance(smc.get("predictions"), list) and smc["predictions"]
    assert "motor" in smc["predictions"][0] or smc["predictions"][0].get("motor")
    hss = rec["historical_sensorimotor_selection"]
    assert hss.get("enabled") is True
    assert isinstance(hss.get("candidates"), list)


def test_withheld_vs_available_represented():
    sel = {
        "action": "WAIT",
        "sensorimotor_consequence": {"enabled": True},
        "sensorimotor_candidate_predictions": [],
        "o_prime_history_bridge": {
            "enabled": True,
            "withheld_from_psc": True,
            "shuffle": False,
            "n_candidates_evaluated": 1,
            "n_history_match": 1,
            "history_support_differentiated": False,
            "selection_differs_from_withheld_cf": False,
        },
        "o_prime_history_candidates": [
            {
                "candidate_locomotion": "WAIT",
                "history_status": "MATCH",
                "history_support": 3,
                "available_to_psc": False,
                "history_shuffled": False,
                "predicted_fields": ["exo_1"],
            }
        ],
    }
    rec = build_decision_receipt(
        run_id="r", tick=1, cognitive_agent_id="a0", physical_body_id="b0",
        observation_id_value="o", motor_id_value="m", last_selection=sel,
        selected_action="WAIT", selection_source="X", selection_rule="Y",
    )
    assert rec["historical_sensorimotor_selection"]["withheld_from_psc"] is True
    assert rec["historical_sensorimotor_selection"]["candidates"][0]["available_to_psc"] is False


def test_no_gt_leakage_in_hss_block():
    text = Path("mechanistic_mind/scientific_v3/receipts.py").read_text()
    # helpers must not invent GT peer fields
    for bad in ("ground_truth_distance", "peer_bearing", "APPROACH", "REWARD", "SEEK"):
        assert bad not in text.split("def _hss_decision_block")[1].split("def build_")[0]


def test_aggregator_from_decisions_jsonl(tmp_path: Path):
    rows = []
    for tick in range(1, 6):
        rows.append({
            "tick": tick,
            "cognitive_agent_id": "agent_0",
            "decision_id": f"d{tick}",
            "observation_id": f"o{tick}",
            "selected_action_legacy": "MOVE:N",
            "selection_mode": "SCENARIO_COMPETITION",
            "selection_path": "COMPOSITE_FACTORIZED",
            "sensorimotor_consequence": {
                "enabled": True,
                "queries": 3,
                "updates": 1,
                "matched_queries": 1,
                "unknown_queries": 2,
                "predictions": [
                    {
                        "motor": "L:MOVE:N|N:NONE|E:0|F:0|A:0|P:0",
                        "status": "MATCH",
                        "support": 2,
                        "predicted_delta": {"exo_1": 0.1},
                    },
                    {
                        "motor": "L:WAIT|N:NONE|E:0|F:0|A:0|P:0",
                        "status": "MATCH",
                        "support": 1,
                        "predicted_delta": {"exo_1": -0.05},
                    },
                ],
                "last_update": {"record_id": "SMC1", "motor_signature": "L:MOVE:N|N:NONE|E:0|F:0|A:0|P:0", "mean_delta": {"exo_1": 0.1}},
            },
            "historical_sensorimotor_selection": {
                "enabled": True,
                "withheld_from_psc": False,
                "shuffle": False,
                "n_candidates_evaluated": 2,
                "n_history_match": 2,
                "history_support_differentiated": True,
                "selection_differs_from_withheld_cf": False,
                "candidates": [
                    {"candidate_locomotion": "MOVE:N", "history_status": "MATCH", "history_support": 4, "available_to_psc": True, "predicted_fields": ["exo_1"]},
                    {"candidate_locomotion": "WAIT", "history_status": "MATCH", "history_support": 1, "available_to_psc": True, "predicted_fields": ["exo_1"]},
                ],
            },
        })
    path = tmp_path / "scientific_decisions.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    sm = aggregate_sensorimotor_consequence_model(tmp_path)
    assert sm["status"] == "RECORDED"
    assert sm["updates"] >= 1
    hss = aggregate_historical_sensorimotor_selection(tmp_path)
    assert hss["status"] == "RECORDED"
    assert hss["funnel"]["o_prime_history_queried"] >= 1
    assert hss["funnel"]["historical_evidence_available_to_psc"] >= 1


def test_observer_session_persists_hss_on_decisions(tmp_path: Path):
    s = ObserverSession(SessionConfig(seed=17, evidence_mode="FULL_SCIENTIFIC", results_root=tmp_path))
    s.set_mechanism("sensorimotor_consequence_model", True)
    s.set_mechanism("historical_sensorimotor_selection_bridge", True)
    s.set_mechanism("prospective_scenario_competition", False)
    for _ in range(25):
        s.step()
    s.set_mechanism("prospective_scenario_competition", True)
    for _ in range(20):
        s.step()
    # Find live sci dir
    roots = list(tmp_path.rglob("scientific_decisions.jsonl"))
    assert roots, "no scientific_decisions.jsonl written"
    dec_path = roots[0]
    run_dir = dec_path.parent
    # Flush writers if any
    if hasattr(s, "stop"):
        try:
            s.stop(reason="test")
        except Exception:
            pass
    # Re-scan after stop
    roots = list(tmp_path.rglob("scientific_decisions.jsonl"))
    dec_path = max(roots, key=lambda p: p.stat().st_mtime)
    run_dir = dec_path.parent
    n_hss = 0
    n_smc = 0
    with dec_path.open() as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            if (row.get("sensorimotor_consequence") or {}).get("enabled"):
                n_smc += 1
            if (row.get("historical_sensorimotor_selection") or {}).get("enabled"):
                n_hss += 1
    assert n_smc >= 1
    assert n_hss >= 1
    sm = aggregate_sensorimotor_consequence_model(run_dir)
    hss = aggregate_historical_sensorimotor_selection(run_dir)
    assert sm["status"] == "RECORDED"
    assert hss["status"] == "RECORDED"


def test_psc_mechanism_toggle_enters_configuration_history():
    s = ObserverSession(SessionConfig(seed=9, evidence_mode="SEARCH_COMPACT"))
    s.set_mechanism("prospective_scenario_competition", False)
    for _ in range(2):
        s.step()
    n0 = len(s._world_interventions)
    s.set_mechanism("prospective_scenario_competition", True)
    assert len(s._world_interventions) == n0 + 1
    ev = s._world_interventions[-1]
    changes = ev.get("changes") or (ev.get("evidence") or {}).get("changes") or {}
    assert "mechanism.prospective_scenario_competition" in changes


def test_exact_match_actions_with_receipt_enrichment():
    def run():
        cfg = CognitionConfig(
            sensorimotor_consequence_model=True,
            historical_sensorimotor_selection_bridge=True,
            prospective_selection="SCENARIO_COMPETITION",
        )
        st = empty_cognitive_state(cfg)
        acts = []
        for t in range(1, 30):
            r = run_cognition_before_action(st, observation=_obs(t), tick=t, rng_value=0.37)
            acts.append(r.selected_action)
            build_decision_receipt(
                run_id="r", tick=t, cognitive_agent_id="a0", physical_body_id="b0",
                observation_id_value="o", motor_id_value="m",
                last_selection=st["last_selection"], selected_action=r.selected_action,
                selection_source=r.selection_source, selection_rule=None,
            )
        return acts
    assert run() == run()


def test_minimal_observer_detail_still_leaves_cognition_evidence():
    """UI MINIMAL must not remove scientific SMC fields from last_selection."""
    s = ObserverSession(SessionConfig(seed=11, evidence_mode="SEARCH_COMPACT"))
    s.set_observer_detail_preset("MINIMAL")
    s.set_mechanism("sensorimotor_consequence_model", True)
    s.set_mechanism("historical_sensorimotor_selection_bridge", True)
    for _ in range(15):
        s.step()
    sel = s.runtime.cognition.get("last_selection") or {}
    assert (sel.get("sensorimotor_consequence") or {}).get("enabled") is True
