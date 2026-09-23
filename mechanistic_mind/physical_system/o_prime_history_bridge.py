
"""O′ → existing historical retrieval → PSC evidence (no new value store).

Queries the organism's existing prospection / compression stores with a
hypothetical accessible future observation O′ produced by SMC.

PSC evidence uses the SAME dimensions as ordinary scenarios:
  (historical_support, reliability, depth)

Aggregation rule (documented, not a magic coefficient):
  Among MATCH continuations from O′ via predict_one_step, take the
  argmax-support match (same pattern as RETAINED_PREDICTION fallback).
  Compression MATCH may contribute if prospection has no MATCH.

Does NOT invent reward/utility/goal.
Does NOT use Observer GT.
"""
from __future__ import annotations

from typing import Any

from mechanistic_mind.research import prospective_composition as pr
from mechanistic_mind.research import predictive_compression as pc
from mechanistic_mind.physical_system import sensorimotor_consequence as smc

SCHEMA = "mm.o_prime_history_bridge.v1"
NO_MATCH = "NO_MATCH"
MATCH = "MATCH"


def construct_o_prime(
    observation: dict[str, float],
    predicted_delta: dict[str, float] | None,
) -> dict[str, Any]:
    """Build O′ from accessible O and SMC Δ̂ only.

    Predicted channels: overwritten via apply_predicted_to_observation.
    Other channels: carried unchanged from O.
    No GT fill-in.
    """
    o = dict(observation or {})
    delta = dict(predicted_delta or {})
    predicted_fields = sorted(k for k in delta if k in smc.SENSORY_CHANNELS and abs(float(delta[k])) > 1e-12)
    o_prime = smc.apply_predicted_to_observation(o, delta)
    carried = sorted(k for k in o if k not in predicted_fields)
    return {
        "o_prime": o_prime,
        "predicted_fields": predicted_fields,
        "carried_fields_count": len(carried),
        "unknown_fields": [],  # SMC does not invent channels outside observation∪SENSORY
        "delta_used": {k: float(delta[k]) for k in predicted_fields},
    }


def query_history_on_o_prime(
    *,
    prospection: dict[str, Any],
    compression: dict[str, Any] | None,
    o_prime: dict[str, float],
    actions: list[str],
    retrieval_enabled: bool = True,
) -> dict[str, Any]:
    """EXISTING APIs only: predict_one_step(O′, a) and optional pc.predict(O′, a)."""
    matches: list[dict[str, Any]] = []
    start_q = pr._q(o_prime) if o_prime else {}
    for a in actions:
        step = pr.predict_one_step(prospection, o_prime, a, _ant_q=start_q)
        if step.get("status") == "MATCH":
            matches.append({
                "source": "prospection_predict_one_step",
                "action": str(a),
                "support": int(step.get("support") or 0),
                "reliability": float(step.get("reliability") or 0.0),
                "transition_id": step.get("transition_id") or step.get("key"),
                "key": step.get("key"),
            })
    cmp_matches: list[dict[str, Any]] = []
    if retrieval_enabled and isinstance(compression, dict):
        ant_sig = pc._sig(o_prime)
        for a in actions:
            pred = pc.predict(
                compression, o_prime, a, domain="accessible", antecedent_sig=ant_sig
            )
            if pred.get("status") == "MATCH":
                cmp_matches.append({
                    "source": "compression_predict",
                    "action": str(a),
                    "support": int(pred.get("support") or 0),
                    "reliability": float(pred.get("reliability") or 0.5),
                    "structure_id": pred.get("structure_id"),
                })

    # Prefer prospection matches; else compression (existing retrieval cascade spirit)
    pool = matches if matches else cmp_matches
    if not pool:
        return {
            "schema": SCHEMA,
            "kind": "O_PRIME_HISTORY_QUERIED",
            "status": NO_MATCH,
            "historical_support": 0,
            "reliability": 0.0,
            "depth": 1,
            "match_count": 0,
            "matches": [],
            "support_spread": 0,
            "differentiated_across_actions": False,
            "aggregation": "argmax_support_among_MATCH_continuations_from_O_prime",
        }

    best = max(pool, key=lambda m: (int(m["support"]), float(m["reliability"])))
    supports = [int(m["support"]) for m in pool]
    return {
        "schema": SCHEMA,
        "kind": "O_PRIME_HISTORY_QUERIED",
        "status": MATCH,
        "historical_support": int(best["support"]),
        "reliability": float(best["reliability"]),
        "depth": 1,
        "match_count": len(pool),
        "matches": pool[:8],
        "best_match": best,
        "support_spread": int(max(supports) - min(supports)) if supports else 0,
        "differentiated_across_actions": bool(supports) and (max(supports) - min(supports)) >= 1,
        "aggregation": "argmax_support_among_MATCH_continuations_from_O_prime",
        "prospection_match_count": len(matches),
        "compression_match_count": len(cmp_matches),
    }


def build_psc_scenario(
    *,
    loco: str,
    o_prime: dict[str, float],
    history: dict[str, Any],
    smc_pred: dict[str, Any],
    construct_meta: dict[str, Any],
) -> dict[str, Any] | None:
    """One PSC scenario whose evidence vector comes from history-on-O′, not SMC counts."""
    if history.get("status") != MATCH:
        return None
    rid = smc_pred.get("record_id") or "none"
    return {
        "scenario_id": f"o_prime_hist:{rid}:{loco}",
        "source_structure_ids": [
            (history.get("best_match") or {}).get("transition_id")
            or (history.get("best_match") or {}).get("structure_id")
            or (history.get("best_match") or {}).get("key")
        ],
        "provenance": {
            "path": "o_prime_history_bridge",
            "smc_record_id": rid,
            "aggregation": history.get("aggregation"),
        },
        "action_sequence": [loco],
        "first_action": loco,
        "depth": int(history.get("depth") or 1),
        "historical_support": int(history.get("historical_support") or 0),
        "historical_support_raw": history.get("historical_support"),
        "reliability": float(history.get("reliability") or 0.0),
        "reliability_raw": history.get("reliability"),
        "current_match_evidence": history.get("best_match"),
        "predicted_state_fragments": o_prime,
        "predicted_body_fragments": "NOT_AVAILABLE",
        "predicted_environment_fragments": "NOT_AVAILABLE",
        "composition_path": [smc_pred, history],
        "score_reliability_path": history.get("reliability"),
        "o_prime_history_bridge": True,
        "o_prime_construct": {
            "predicted_fields": construct_meta.get("predicted_fields"),
            "carried_fields_count": construct_meta.get("carried_fields_count"),
        },
        "historical_sensorimotor_selection": {
            "candidate_locomotion": loco,
            "sensorimotor_record_id": rid,
            "o_prime_predicted_fields": construct_meta.get("predicted_fields"),
            "history_status": history.get("status"),
            "history_support": history.get("historical_support"),
            "history_match_count": history.get("match_count"),
            "history_uncertainty": 1.0 - float(history.get("reliability") or 0.0),
            "available_to_psc": True,  # caller may flip when withholding
        },
    }


def evaluate_candidates(
    *,
    observation: dict[str, float],
    smc_preds: list[dict[str, Any]],
    prospection: dict[str, Any],
    compression: dict[str, Any] | None,
    actions: list[str],
    retrieval_enabled: bool = True,
    shuffle_o_prime_history: bool = False,
    tick: int = 0,
) -> list[dict[str, Any]]:
    """Per SMC candidate: construct O′, query history, build receipt (+ optional scenario).

    shuffle_o_prime_history: rotate history results across candidates (control D).
    """
    rows: list[dict[str, Any]] = []
    for pred in smc_preds:
        if pred.get("status") not in {smc.MATCH, smc.LOW_SUPPORT}:
            continue
        if not pred.get("predicted_delta"):
            continue
        loco = str(pred.get("candidate_locomotion") or "")
        if not loco:
            continue
        meta = construct_o_prime(observation, pred.get("predicted_delta"))
        hist = query_history_on_o_prime(
            prospection=prospection,
            compression=compression,
            o_prime=meta["o_prime"],
            actions=list(actions),
            retrieval_enabled=retrieval_enabled,
        )
        rows.append({
            "candidate_locomotion": loco,
            "smc_pred": pred,
            "construct": meta,
            "history": hist,
            "scenario": None,  # filled after optional shuffle
        })

    if shuffle_o_prime_history and len(rows) >= 2:
        # Deterministic rotation of history payloads across candidates
        shift = 1 + (int(tick) % max(1, len(rows) - 1))
        hist_cycle = [r["history"] for r in rows]
        for i, r in enumerate(rows):
            r["history"] = hist_cycle[(i + shift) % len(hist_cycle)]
            r["history_shuffled"] = True

    for r in rows:
        scn = build_psc_scenario(
            loco=r["candidate_locomotion"],
            o_prime=r["construct"]["o_prime"],
            history=r["history"],
            smc_pred=r["smc_pred"],
            construct_meta=r["construct"],
        )
        r["scenario"] = scn
    return rows
