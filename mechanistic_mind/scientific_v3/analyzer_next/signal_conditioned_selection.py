"""SIGNAL-CONDITIONED SENSORIMOTOR SELECTION — Analyzer aggregation.

Uses only:
- ObservationReceipt.accessible (agent-accessible)
- DecisionReceipt.sensorimotor_consequence / historical_sensorimotor_selection

Observer-only bilateral diagnostics from osc_l_*/osc_r_* in ObservationReceipt
are tagged DERIVED — they do NOT enter SMC/O′ (SENSORY_CHANNELS excludes them).
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

# Channels that actually participate in SMC / predicted O′ today.
SMC_SIGNAL_CHANNELS: tuple[str, ...] = ("local.FIELD_A", "local.FIELD_B")
OSC_SIGNAL_CHANNELS: tuple[str, ...] = tuple(f"osc_l_{i}" for i in range(6)) + tuple(f"osc_r_{i}" for i in range(6))


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                yield row


def _signal_present(acc: dict[str, Any], *, eps: float = 1e-6) -> bool:
    for k in SMC_SIGNAL_CHANNELS:
        try:
            if abs(float(acc.get(k) or 0.0)) > eps:
                return True
        except (TypeError, ValueError):
            continue
    # osc bands are agent-accessible but not SMC — still count as signal present for observation-layer funnel
    for k, v in acc.items():
        if str(k).startswith("osc_") and abs(float(v or 0.0)) > eps:
            return True
    return False


def _field_signal(acc: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for k in SMC_SIGNAL_CHANNELS:
        try:
            out[k] = float(acc.get(k) or 0.0)
        except (TypeError, ValueError):
            out[k] = 0.0
    return out


def _bilateral_derived(acc: dict[str, Any]) -> dict[str, Any] | None:
    """Observer/Analyzer DERIVED from osc bands in ObservationReceipt — not agent variable."""
    L = []
    R = []
    for i in range(16):
        lk, rk = f"osc_l_{i}", f"osc_r_{i}"
        if lk not in acc and rk not in acc:
            if i > 0:
                break
            continue
        L.append(float(acc.get(lk) or 0.0))
        R.append(float(acc.get(rk) or 0.0))
    if not L and not R:
        return None
    tot_l = sum(L)
    tot_r = sum(R)
    return {
        "provenance": "DERIVED_DISPLAY_ONLY",
        "not_an_agent_variable": True,
        "L_bands": L,
        "R_bands": R,
        "total_L": tot_l,
        "total_R": tot_r,
        "R_minus_L": tot_r - tot_l,
        "asymmetry": (tot_r - tot_l) / (tot_r + tot_l + 1e-9),
        "note": "osc_l_*/osc_r_* are agent-accessible in ObservationReceipt but NOT in SMC SENSORY_CHANNELS",
    }



def _osc_delta_from_pred(pred: dict[str, Any]) -> dict[str, float] | None:
    d = pred.get("predicted_delta")
    if not isinstance(d, dict):
        return None
    out = {}
    for k in OSC_SIGNAL_CHANNELS:
        if k in d:
            try:
                out[k] = float(d[k])
            except (TypeError, ValueError):
                continue
    return out or None


def _bilateral_futures_differentiated(preds: list[dict[str, Any]]) -> bool:
    sigs = []
    for p in preds:
        if not isinstance(p, dict):
            continue
        sd = _osc_delta_from_pred(p)
        if sd is None:
            continue
        sigs.append(tuple(sorted((k, round(v, 6)) for k, v in sd.items())))
    return len({s for s in sigs if s}) >= 2

def _signal_delta_from_pred(pred: dict[str, Any]) -> dict[str, float] | None:
    d = pred.get("predicted_delta")
    if not isinstance(d, dict):
        return None
    out = {}
    for k in SMC_SIGNAL_CHANNELS:
        if k in d:
            try:
                out[k] = float(d[k])
            except (TypeError, ValueError):
                continue
    return out or None


def _futures_differentiated(preds: list[dict[str, Any]]) -> bool:
    sigs = []
    for p in preds:
        if not isinstance(p, dict):
            continue
        sd = _signal_delta_from_pred(p)
        if sd is None:
            continue
        # round for equality of near-zeros
        sigs.append(tuple(sorted((k, round(v, 6)) for k, v in sd.items())))
    uniq = {s for s in sigs if s}
    return len(uniq) >= 2


def _load_vision_exposure(run_dir: Path) -> dict[tuple[str, int], bool]:
    """Map (agent, tick) → body_exposure from timeline / optical if present."""
    out: dict[tuple[str, int], bool] = {}
    for name in ("scientific_timeline.jsonl", "scientific_events.jsonl"):
        path = run_dir / name
        if not path.exists():
            continue
        for row in _iter_jsonl(path):
            vo = row.get("vision_optical")
            if not isinstance(vo, dict):
                # nested evidence
                ev = row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
                vo = ev.get("vision_optical") if isinstance(ev, dict) else None
            if not isinstance(vo, dict):
                continue
            tick = row.get("tick")
            aid = row.get("cognitive_agent_id") or row.get("agent_id")
            if tick is None or aid is None:
                continue
            if vo.get("body_exposure") is True or float(vo.get("foreign_body_total") or 0) > 0:
                out[(str(aid), int(tick))] = True
            elif (str(aid), int(tick)) not in out:
                out[(str(aid), int(tick))] = False
    return out


def aggregate_signal_conditioned_selection(run_dir: Path) -> dict[str, Any]:
    run_dir = Path(run_dir)
    obs_by: dict[tuple[str, int], dict[str, Any]] = {}
    for row in _iter_jsonl(run_dir / "scientific_observations.jsonl"):
        aid = str(row.get("cognitive_agent_id") or "")
        tick = int(row.get("tick") or -1)
        acc = row.get("accessible") if isinstance(row.get("accessible"), dict) else {}
        obs_by[(aid, tick)] = acc

    vision = _load_vision_exposure(run_dir)

    path_audit = {
        "PHYSICAL_WORLD": {
            "FIELD_A/B": "AVAILABLE",
            "oscillatory_bands": "AVAILABLE",
        },
        "RECEIVER": {
            "local.FIELD_A/B": "AVAILABLE",
            "osc_l_*/osc_r_*": "AVAILABLE",
        },
        "AGENT_ACCESSIBLE_OBSERVATION": {
            "local.FIELD_A/B": "AVAILABLE",
            "osc_l_*/osc_r_*": "AVAILABLE",
        },
        "SMC_INPUT": {
            "local.FIELD_A/B": "AVAILABLE",
            "osc_l_*/osc_r_*": "AVAILABLE_WHEN_BILATERAL_ON",
            "note": "Default SENSORY_CHANNELS includes osc_l_*/osc_r_*; WITHHELD uses BASE only",
        },
        "O_PRIME_REPRESENTATION": {
            "FIELD components via SMC delta": "AVAILABLE",
            "osc bands": "AVAILABLE_WHEN_BILATERAL_ON",
        },
        "HISTORY_QUERY": {"via_FIELD_in_O_prime": "AVAILABLE_WHEN_HSS_ENABLED"},
        "PSC": {"via_HSS_available_to_psc": "AVAILABLE_WHEN_RECORDED"},
    }

    by_agent: dict[str, dict[str, Any]] = {}
    examples: list[dict[str, Any]] = []
    global_funnel = {
        "SIGNAL_PRESENT": 0,
        "MULTI_CANDIDATE": 0,
        "SIGNAL_SMC_PREDICTIONS_AVAILABLE": 0,
        "SIGNAL_FUTURES_DIFFERENTIATED": 0,
        "O_PRIME_HISTORY_QUERIED": 0,
        "HISTORICAL_SUPPORT_DIFFERENTIATED": 0,
        "HISTORICAL_EVIDENCE_AVAILABLE_TO_PSC": 0,
        "SELECTED_CANDIDATE": 0,
        "FINAL_SELECTION_DIFFERS_FROM_WITHHELD_COUNTERFACTUAL": 0,
        "NO_VISION_SIGNAL_PRESENT": 0,
        "NO_VISION_SIGNAL_FUTURES_DIFFERENTIATED": 0,
        "NO_VISION_HISTORICAL_AVAILABLE_TO_PSC": 0,
        "BILATERAL_SIGNAL_PRESENT": 0,
        "BILATERAL_SMC_PREDICTIONS_AVAILABLE": 0,
        "BILATERAL_FUTURES_DIFFERENTIATED": 0,
        "BILATERAL_O_PRIME_AVAILABLE": 0,
        "BILATERAL_HISTORY_QUERIED": 0,
        "BILATERAL_HISTORY_SUPPORT_DIFFERENTIATED": 0,
        "BILATERAL_EVIDENCE_AVAILABLE_TO_PSC": 0,
        "NO_VISION_BILATERAL_FUTURES_DIFFERENTIATED": 0,
    }

    n_dec = 0
    for row in _iter_jsonl(run_dir / "scientific_decisions.jsonl"):
        n_dec += 1
        aid = str(row.get("cognitive_agent_id") or "")
        tick = int(row.get("tick") or -1)
        acc = obs_by.get((aid, tick)) or {}
        ag = by_agent.setdefault(
            aid,
            {
                "signal_present_psc": 0,
                "signal_smc_predictions": 0,
                "differentiated_signal_futures": 0,
                "o_prime_history_queries": 0,
                "historical_support_differentiated": 0,
                "historical_evidence_available_to_psc": 0,
                "selected_candidates": 0,
                "withheld_cf_changes": 0,
                "no_vision_signal_present": 0,
                "no_vision_differentiated": 0,
                "bilateral_obs_ticks": 0,
                "first_tick": tick,
                "last_tick": tick,
            },
        )
        ag["first_tick"] = min(ag["first_tick"], tick)
        ag["last_tick"] = max(ag["last_tick"], tick)

        sig_present = _signal_present(acc)
        bil = _bilateral_derived(acc)
        if bil and (bil["total_L"] + bil["total_R"]) > 1e-6:
            ag["bilateral_obs_ticks"] += 1

        smc = row.get("sensorimotor_consequence") if isinstance(row.get("sensorimotor_consequence"), dict) else {}
        preds = smc.get("predictions") if isinstance(smc.get("predictions"), list) else []
        hss = row.get("historical_sensorimotor_selection") if isinstance(row.get("historical_sensorimotor_selection"), dict) else {}
        mode = str(row.get("selection_mode") or "")
        psc_on = "SCENARIO" in mode.upper()

        body_vis = vision.get((aid, tick))
        # If unknown, treat as None (do not invent)
        no_vision = body_vis is False

        if sig_present:
            global_funnel["SIGNAL_PRESENT"] += 1
            if no_vision:
                global_funnel["NO_VISION_SIGNAL_PRESENT"] += 1
                ag["no_vision_signal_present"] += 1

        if not psc_on:
            continue

        if sig_present:
            ag["signal_present_psc"] += 1

        if int(row.get("candidate_count") or 0) >= 2 or len(preds) >= 2:
            global_funnel["MULTI_CANDIDATE"] += 1

        signal_preds = []
        for p in preds:
            if not isinstance(p, dict):
                continue
            sd = _signal_delta_from_pred(p)
            if sd is None:
                continue
            signal_preds.append({
                "motor": p.get("motor") or p.get("motor_signature"),
                "status": p.get("status"),
                "support": p.get("support"),
                "signal_predicted_delta": sd,
            })
        if signal_preds:
            global_funnel["SIGNAL_SMC_PREDICTIONS_AVAILABLE"] += 1
            ag["signal_smc_predictions"] += 1

        bil_preds = []
        for p in preds:
            if not isinstance(p, dict):
                continue
            od = _osc_delta_from_pred(p)
            if od is None:
                continue
            bil_preds.append({
                "motor": p.get("motor") or p.get("motor_signature"),
                "status": p.get("status"),
                "support": p.get("support"),
                "osc_predicted_delta": od,
            })
        bil_present = any(
            abs(float(acc.get(k) or 0.0)) > 1e-6 for k in OSC_SIGNAL_CHANNELS if k in acc
        )
        if bil_present:
            global_funnel["BILATERAL_SIGNAL_PRESENT"] += 1
        if bil_preds:
            global_funnel["BILATERAL_SMC_PREDICTIONS_AVAILABLE"] += 1
            global_funnel["BILATERAL_O_PRIME_AVAILABLE"] += 1  # O′ carries same predicted_delta keys
            ag.setdefault("bilateral_smc_predictions", 0)
            ag["bilateral_smc_predictions"] = int(ag.get("bilateral_smc_predictions") or 0) + 1
        bil_diff = _bilateral_futures_differentiated(preds)
        if bil_diff:
            global_funnel["BILATERAL_FUTURES_DIFFERENTIATED"] += 1
            ag.setdefault("bilateral_futures_differentiated", 0)
            ag["bilateral_futures_differentiated"] = int(ag.get("bilateral_futures_differentiated") or 0) + 1
            if no_vision and bil_present:
                global_funnel["NO_VISION_BILATERAL_FUTURES_DIFFERENTIATED"] += 1

        diff = _futures_differentiated(preds)
        if diff:
            global_funnel["SIGNAL_FUTURES_DIFFERENTIATED"] += 1
            ag["differentiated_signal_futures"] += 1
            if no_vision and sig_present:
                global_funnel["NO_VISION_SIGNAL_FUTURES_DIFFERENTIATED"] += 1
                ag["no_vision_differentiated"] += 1

        cands = hss.get("candidates") if isinstance(hss.get("candidates"), list) else []
        n_match = int(hss.get("n_history_match") or 0)
        if n_match > 0 or any(str(c.get("history_status") or "").upper() == "MATCH" for c in cands if isinstance(c, dict)):
            global_funnel["O_PRIME_HISTORY_QUERIED"] += 1
            ag["o_prime_history_queries"] += 1
            if bil_preds:
                global_funnel["BILATERAL_HISTORY_QUERIED"] += 1
        if hss.get("history_support_differentiated"):
            global_funnel["HISTORICAL_SUPPORT_DIFFERENTIATED"] += 1
            ag["historical_support_differentiated"] += 1
            if bil_preds:
                global_funnel["BILATERAL_HISTORY_SUPPORT_DIFFERENTIATED"] += 1
        avail = any(isinstance(c, dict) and c.get("available_to_psc") is True for c in cands) and not hss.get("withheld_from_psc")
        if avail:
            global_funnel["HISTORICAL_EVIDENCE_AVAILABLE_TO_PSC"] += 1
            ag["historical_evidence_available_to_psc"] += 1
            if no_vision and sig_present:
                global_funnel["NO_VISION_HISTORICAL_AVAILABLE_TO_PSC"] += 1
            if bil_preds:
                global_funnel["BILATERAL_EVIDENCE_AVAILABLE_TO_PSC"] += 1

        if row.get("selected_action_legacy") or row.get("selected_candidate_id"):
            global_funnel["SELECTED_CANDIDATE"] += 1
            ag["selected_candidates"] += 1

        if hss.get("selection_differs_from_withheld_cf"):
            global_funnel["FINAL_SELECTION_DIFFERS_FROM_WITHHELD_COUNTERFACTUAL"] += 1
            ag["withheld_cf_changes"] += 1

        # Forensic examples: prefer signal + differentiated + no vision
        if len(examples) < 8 and sig_present and diff and signal_preds:
            score = (2 if no_vision else 0) + (1 if avail else 0) + (1 if bil else 0)
            examples.append({
                "score": score,
                "tick": tick,
                "cognitive_agent_id": aid,
                "decision_id": row.get("decision_id"),
                "observation_id": row.get("observation_id"),
                "selected_action": row.get("selected_action_legacy"),
                "selection_path": row.get("selection_path"),
                "selection_mode": mode,
                "agent_accessible_signal": _field_signal(acc),
                "bilateral_derived": bil,
                "foreign_body_visual_exposure": body_vis,
                "signal_candidate_predictions": signal_preds[:8],
                "hss_candidates": cands[:8],
                "hss_bridge": {
                    "withheld_from_psc": hss.get("withheld_from_psc"),
                    "history_support_differentiated": hss.get("history_support_differentiated"),
                    "selection_differs_from_withheld_cf": hss.get("selection_differs_from_withheld_cf"),
                    "local_counterfactual": hss.get("local_counterfactual"),
                },
                "boundary": {
                    "spatial_use_of_signal": "CANDIDATE" if diff else "NOT_ESTABLISHED",
                    "communicative_interpretation": "NOT_ESTABLISHED",
                    "source_recognition": "NOT_ESTABLISHED",
                    "osc_bands_in_SMC": bool(global_funnel["BILATERAL_SMC_PREDICTIONS_AVAILABLE"] > 0),
                },
            })

    examples.sort(key=lambda e: -int(e.get("score") or 0))
    examples = examples[:6]
    for e in examples:
        e.pop("score", None)

    status = "NOT_RECORDED"
    if global_funnel["SIGNAL_SMC_PREDICTIONS_AVAILABLE"] > 0:
        status = "RECORDED" if global_funnel["SIGNAL_FUTURES_DIFFERENTIATED"] > 0 else "PARTIAL"
    elif global_funnel["SIGNAL_PRESENT"] > 0:
        status = "PARTIAL"

    gates = {
        "GATE_A_signal_join_to_SMC": "PASS" if global_funnel["SIGNAL_SMC_PREDICTIONS_AVAILABLE"] else "NOT_DEMONSTRATED",
        "GATE_B_differentiated_signal_futures": "PASS" if global_funnel["SIGNAL_FUTURES_DIFFERENTIATED"] else "NOT_DEMONSTRATED",
        "GATE_C_join_to_O_prime_history": "PASS" if global_funnel["O_PRIME_HISTORY_QUERIED"] else "NOT_DEMONSTRATED",
        "GATE_D_historical_available_to_PSC": "PASS" if global_funnel["HISTORICAL_EVIDENCE_AVAILABLE_TO_PSC"] else "NOT_DEMONSTRATED",
        "GATE_E_selected_motor_joinable": "PASS" if global_funnel["SELECTED_CANDIDATE"] else "NOT_DEMONSTRATED",
        "GATE_F_no_vision_subset": (
            "PASS" if global_funnel["NO_VISION_SIGNAL_FUTURES_DIFFERENTIATED"] else
            ("PARTIAL" if global_funnel["NO_VISION_SIGNAL_PRESENT"] else "NOT_RECORDED")
        ),
        "GATE_LR_bands_reach_SMC": (
            "PASS" if global_funnel["BILATERAL_SMC_PREDICTIONS_AVAILABLE"] else "NOT_DEMONSTRATED"
        ),
        "GATE_BILATERAL_FUTURES_DIFFERENTIATED": (
            "PASS" if global_funnel["BILATERAL_FUTURES_DIFFERENTIATED"] else "NOT_DEMONSTRATED"
        ),
    }

    return {
        "status": status,
        "section": "SIGNAL-CONDITIONED SENSORIMOTOR SELECTION",
        "path_audit": path_audit,
        "smc_signal_channels": list(SMC_SIGNAL_CHANNELS),
        "osc_bands_in_SMC": bool(global_funnel["BILATERAL_SMC_PREDICTIONS_AVAILABLE"] > 0),
        "funnel": global_funnel,
        "agents": by_agent,
        "examples": examples,
        "gates": gates,
        "n_decisions_scanned": n_dec,
        "n_observations_indexed": len(obs_by),
        "source": "scientific_observations.jsonl + scientific_decisions.jsonl",
        "claims_boundary": {
            "allowed_if_supported": [
                "physical signal exposure",
                "action-conditioned FIELD signal prediction",
                "differentiated predicted FIELD futures",
                "historical support for those futures",
                "signal-conditioned PSC association",
                "signal-conditioned selection under absent visual exposure",
            ],
            "not_established": [
                "understands where the other agent is",
                "knows left/right as semantics",
                "recognizes another agent",
                "follows a voice",
                "communicates",
                "language / semantic message",
                "spatial concept / left-right semantics",
                "source localization / follows voice / communication",
            ],
        },
    }
