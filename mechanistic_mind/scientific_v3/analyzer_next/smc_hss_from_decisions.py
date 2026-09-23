"""Aggregate SMC / O′ historical-selection evidence from scientific_decisions.jsonl.

Does not invent quantities — only summarizes what DecisionReceipt already stores.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


def _iter_decisions(run_dir: Path) -> Iterable[dict[str, Any]]:
    path = Path(run_dir) / "scientific_decisions.jsonl"
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


def aggregate_sensorimotor_consequence_model(run_dir: Path) -> dict[str, Any]:
    """Build Analyzer payload for ACTION-CONDITIONED SENSORIMOTOR MODEL."""
    by_agent: dict[str, dict[str, Any]] = {}
    examples: list[dict[str, Any]] = []
    any_enabled = False
    first_tick = None
    last_tick = None
    total_queries = 0
    total_updates = 0
    matched = 0
    unknown = 0
    motors: set[str] = set()
    differentiated_ticks = 0

    for row in _iter_decisions(run_dir):
        smc = row.get("sensorimotor_consequence")
        if not isinstance(smc, dict):
            continue
        if not smc.get("enabled") and not smc.get("predictions") and not smc.get("last_update"):
            continue
        any_enabled = any_enabled or bool(smc.get("enabled"))
        tick = int(row.get("tick") or 0)
        aid = str(row.get("cognitive_agent_id") or "agent")
        first_tick = tick if first_tick is None else min(first_tick, tick)
        last_tick = tick if last_tick is None else max(last_tick, tick)
        ag = by_agent.setdefault(
            aid,
            {
                "queries": 0,
                "updates": 0,
                "matched_queries": 0,
                "unknown_queries": 0,
                "predictions_available": 0,
                "decisions": 0,
                "motors": set(),
                "first_tick": tick,
                "last_tick": tick,
            },
        )
        ag["decisions"] += 1
        ag["first_tick"] = min(ag["first_tick"], tick)
        ag["last_tick"] = max(ag["last_tick"], tick)
        # Store diagnostics are cumulative snapshots — keep latest per agent, and
        # count this-tick prediction / update events separately.
        ag["queries"] = int(smc.get("queries") or ag["queries"])
        ag["matched_queries"] = int(smc.get("matched_queries") or ag["matched_queries"])
        ag["unknown_queries"] = int(smc.get("unknown_queries") or ag["unknown_queries"])
        total_queries = max(total_queries, int(smc.get("queries") or 0))
        matched = max(matched, int(smc.get("matched_queries") or 0))
        unknown = max(unknown, int(smc.get("unknown_queries") or 0))
        if smc.get("last_update"):
            ag["updates"] += 1
            total_updates += 1
        preds = smc.get("predictions") if isinstance(smc.get("predictions"), list) else []
        statuses = []
        for pred in preds:
            if not isinstance(pred, dict):
                continue
            motor = pred.get("motor") or pred.get("motor_signature")
            if motor:
                motors.add(str(motor))
                ag["motors"].add(str(motor))
            st = str(pred.get("status") or "")
            statuses.append(st)
            if st and st.upper() not in {"UNKNOWN", "NONE", ""}:
                ag["predictions_available"] += 1
        # differentiated predicted futures: >1 distinct statuses or deltas among candidates
        deltas = [
            tuple(sorted((pred.get("predicted_delta") or {}).items()))
            for pred in preds
            if isinstance(pred, dict) and isinstance(pred.get("predicted_delta"), dict)
        ]
        if len({d for d in deltas if d}) >= 2:
            differentiated_ticks += 1
        if len(examples) < 8 and any(
            isinstance(pred, dict) and pred.get("predicted_delta") for pred in preds
        ):
            examples.append({
                "tick": tick,
                "cognitive_agent_id": aid,
                "decision_id": row.get("decision_id"),
                "observation_id": row.get("observation_id"),
                "selected_action": row.get("selected_action_legacy"),
                "predictions": preds[:6],
                "last_update": smc.get("last_update"),
            })

    if not any_enabled and total_queries == 0 and total_updates == 0:
        return {"status": "NOT_RECORDED"}

    agents_out = {}
    for aid, ag in by_agent.items():
        agents_out[aid] = {
            **{k: v for k, v in ag.items() if k != "motors"},
            "candidate_motors_represented": sorted(ag["motors"])[:24],
            "n_motors": len(ag["motors"]),
        }

    return {
        "status": "RECORDED",
        "enabled": True,
        "queries": total_queries,
        "updates": total_updates,
        "matched_queries": matched,
        "unknown_queries": unknown,
        "occupancy": None,
        "capacity": None,
        "mean_support": None,
        "channels": None,
        "differentiated_predicted_futures_ticks": differentiated_ticks,
        "candidate_motors_represented": sorted(motors)[:48],
        "first_tick": first_tick,
        "last_tick": last_tick,
        "agents": agents_out,
        "examples": examples,
        "source": "scientific_decisions.jsonl#sensorimotor_consequence",
    }


def aggregate_historical_sensorimotor_selection(run_dir: Path) -> dict[str, Any]:
    """Build Analyzer payload for HISTORICAL SENSORIMOTOR SELECTION."""
    by_agent: dict[str, dict[str, Any]] = {}
    examples: list[dict[str, Any]] = []
    any_enabled = False
    first_tick = None
    last_tick = None
    funnel = {
        "psc_competitions": 0,
        "multi_candidate": 0,
        "smc_preds_available": 0,
        "predicted_futures_differentiated": 0,
        "o_prime_history_queried": 0,
        "historical_support_differentiated": 0,
        "historical_evidence_available_to_psc": 0,
        "withheld_evaluations": 0,
        "psc_ranking_changed_by_history_evidence": "NOT_RECORDED",
        "final_selection_differs_from_withheld_counterfactual": 0,
    }

    for row in _iter_decisions(run_dir):
        hss = row.get("historical_sensorimotor_selection")
        if not isinstance(hss, dict):
            continue
        if not hss.get("enabled") and not hss.get("candidates"):
            continue
        any_enabled = any_enabled or bool(hss.get("enabled"))
        tick = int(row.get("tick") or 0)
        aid = str(row.get("cognitive_agent_id") or "agent")
        first_tick = tick if first_tick is None else min(first_tick, tick)
        last_tick = tick if last_tick is None else max(last_tick, tick)
        ag = by_agent.setdefault(
            aid,
            {
                "candidate_evaluations": 0,
                "o_prime_history_queries": 0,
                "differentiated_support_competitions": 0,
                "historical_evidence_available_to_psc": 0,
                "withheld_evaluations": 0,
                "selection_differs_from_withheld_cf": 0,
                "first_tick": tick,
                "last_tick": tick,
            },
        )
        ag["first_tick"] = min(ag["first_tick"], tick)
        ag["last_tick"] = max(ag["last_tick"], tick)
        cands = hss.get("candidates") if isinstance(hss.get("candidates"), list) else []
        n_eval = int(hss.get("n_candidates_evaluated") or len(cands) or 0)
        ag["candidate_evaluations"] += n_eval
        if n_eval >= 2:
            funnel["multi_candidate"] += 1
        mode = str(row.get("selection_mode") or row.get("selection_path") or "")
        if "SCENARIO" in mode.upper() or "PROSPECTIVE" in str(row.get("selection_path") or "").upper():
            funnel["psc_competitions"] += 1
        if hss.get("withheld_from_psc"):
            funnel["withheld_evaluations"] += 1
            ag["withheld_evaluations"] += 1
        n_match = int(hss.get("n_history_match") or 0)
        if n_match > 0 or any(str(c.get("history_status") or "").upper() == "MATCH" for c in cands if isinstance(c, dict)):
            funnel["o_prime_history_queried"] += 1
            ag["o_prime_history_queries"] += 1
        if hss.get("history_support_differentiated"):
            funnel["historical_support_differentiated"] += 1
            ag["differentiated_support_competitions"] += 1
        avail = [
            c for c in cands
            if isinstance(c, dict) and c.get("available_to_psc") is True
        ]
        if avail and not hss.get("withheld_from_psc"):
            funnel["historical_evidence_available_to_psc"] += 1
            ag["historical_evidence_available_to_psc"] += 1
        if hss.get("selection_differs_from_withheld_cf"):
            funnel["final_selection_differs_from_withheld_counterfactual"] += 1
            ag["selection_differs_from_withheld_cf"] += 1
        # SMC preds available this tick (join sibling block)
        smc = row.get("sensorimotor_consequence") if isinstance(row.get("sensorimotor_consequence"), dict) else {}
        preds = smc.get("predictions") if isinstance(smc.get("predictions"), list) else []
        if any(isinstance(p, dict) and str(p.get("status") or "").upper() not in {"UNKNOWN", "NONE", ""} for p in preds):
            funnel["smc_preds_available"] += 1
        deltas = [
            tuple(sorted((p.get("predicted_delta") or {}).items()))
            for p in preds
            if isinstance(p, dict) and isinstance(p.get("predicted_delta"), dict)
        ]
        if len({d for d in deltas if d}) >= 2:
            funnel["predicted_futures_differentiated"] += 1

        if len(examples) < 6 and len(cands) >= 1 and n_match > 0:
            examples.append({
                "tick": tick,
                "cognitive_agent_id": aid,
                "decision_id": row.get("decision_id"),
                "observation_id": row.get("observation_id"),
                "selected_action": row.get("selected_action_legacy"),
                "selection_path": row.get("selection_path"),
                "selection_mode": row.get("selection_mode"),
                "bridge": {
                    "withheld_from_psc": hss.get("withheld_from_psc"),
                    "shuffle": hss.get("shuffle"),
                    "history_support_differentiated": hss.get("history_support_differentiated"),
                    "selection_differs_from_withheld_cf": hss.get("selection_differs_from_withheld_cf"),
                    "local_counterfactual": hss.get("local_counterfactual"),
                },
                "candidates": cands[:8],
                "smc_predictions": preds[:6],
            })

    if not any_enabled:
        return {"status": "NOT_RECORDED"}

    return {
        "status": "RECORDED",
        "activation_tick": first_tick,
        "first_tick": first_tick,
        "last_tick": last_tick,
        "funnel": funnel,
        "agents": by_agent,
        "examples": examples,
        "source": "scientific_decisions.jsonl#historical_sensorimotor_selection",
        "note": (
            "psc_ranking_changed_by_history_evidence is NOT_RECORDED unless an "
            "authoritative ranking-delta field exists on the receipt."
        ),
    }
