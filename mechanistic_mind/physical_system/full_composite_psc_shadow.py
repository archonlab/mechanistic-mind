"""FULL COMPOSITE PSC SHADOW REPLAY — observational only.

Replays empirically observed COMPOSITE_MOTOR_V1 candidates through the REAL
production chain:

    SMC (full signature) → construct_o_prime → HSS/history → PSC evidence
    → compete_scenarios

Production PSC / motors / stores / RNG stream are NOT modified.
Shadow compete uses the deterministic seed+tick unit interval (same formula
as production cognition), never advancing a mutable RNG.

NO proxy ranking. NO invented scores. NO production promotion.
"""
from __future__ import annotations

import copy
import hashlib
import json
import time
from typing import Any

from mechanistic_mind.physical_system import sensorimotor_consequence as smc
from mechanistic_mind.physical_system import o_prime_history_bridge as oph
from mechanistic_mind.physical_system import scenario_competition as sc
from mechanistic_mind.physical_system.psc_motor_resolution_shadow import (
    FAMILY_KEYS,
    _store_snapshot,
    channel_divergence,
    composite_query,
    loco_only_query,
    observed_composites_for_loco,
    o_prime_from_pred,
    pairwise_divergences,
    parse_motor_signature,
)
from mechanistic_mind.physical_system.runtime import _rng_unit

SCHEMA = "mm.full_composite_psc_shadow.v1"

# Production functions reused (documented for the report):
REUSED_PRODUCTION = [
    "sensorimotor_consequence.query (via composite_query / loco_only_query on store snapshot)",
    "o_prime_history_bridge.construct_o_prime",
    "o_prime_history_bridge.query_history_on_o_prime",
    "o_prime_history_bridge.build_psc_scenario",
    "scenario_competition.compete_scenarios",
    "scenario_competition.jsonish_copy (isolated group trees)",
    "runtime._rng_unit (deterministic tie index; no mutable RNG advance)",
]


def _json_hash(obj: Any) -> str:
    blob = json.dumps(obj, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _deepcopy_jsonish(obj: Any) -> Any:
    """Isolated snapshot for history stores (read-only intent + mutation safety)."""
    try:
        return sc.jsonish_copy(obj)
    except Exception:
        return copy.deepcopy(obj)


def _motor_sig_from_realized(motor: dict[str, Any] | None) -> str | None:
    if not isinstance(motor, dict):
        return None
    try:
        return smc.motor_signature_from_composite(motor)
    except Exception:
        # Fall back to display / legacy fields
        return motor.get("motor_signature") or motor.get("display")


def _loco_from_sig(sig: str | None) -> str | None:
    if not sig:
        return None
    parsed = parse_motor_signature(str(sig))
    return str(parsed["locomotion"]) if parsed else None


def _match_kind(pred: dict[str, Any]) -> str:
    st = pred.get("status")
    reason = str(pred.get("reason") or "")
    agg = str(pred.get("aggregation") or "")
    if st == smc.UNKNOWN or not pred.get("predicted_delta"):
        return "UNKNOWN"
    if "loco_prefix" in reason or agg == "MAX_SUPPORT_UNDER_PREFIX":
        return "LOCO_FALLBACK"
    if agg == "EXACT_NONE_SIDECHANNELS":
        return "SOFT_EXISTING_MATCH" if st in {smc.MATCH, smc.LOW_SUPPORT} else "UNKNOWN"
    if st in {smc.MATCH, smc.LOW_SUPPORT}:
        return "EXACT_COMPOSITE_MATCH"
    return "SOFT_EXISTING_MATCH"


def _build_candidate_row(
    *,
    observation: dict[str, float],
    pred: dict[str, Any],
    first_action_key: str,
    loco: str,
    motor_signature: str | None,
    motor: dict[str, Any] | None,
    prospection: dict[str, Any],
    compression: dict[str, Any] | None,
    history_actions: list[str],
    retrieval_enabled: bool,
    provenance: dict[str, Any],
) -> dict[str, Any] | None:
    if pred.get("status") not in {smc.MATCH, smc.LOW_SUPPORT}:
        return None
    if not pred.get("predicted_delta"):
        return None
    meta = oph.construct_o_prime(observation, pred.get("predicted_delta"))
    hist = oph.query_history_on_o_prime(
        prospection=prospection,
        compression=compression,
        o_prime=meta["o_prime"],
        actions=list(history_actions),
        retrieval_enabled=retrieval_enabled,
    )
    # Tag candidate_locomotion for build_psc_scenario / evaluate compatibility
    pred_tagged = {**pred, "candidate_locomotion": loco, "record_id": pred.get("record_id")}
    scn = oph.build_psc_scenario(
        loco=first_action_key,  # unique compete key (loco OR composite sig)
        o_prime=meta["o_prime"],
        history=hist,
        smc_pred=pred_tagged,
        construct_meta=meta,
    )
    return {
        "first_action": first_action_key,
        "locomotion": loco,
        "motor_signature": motor_signature,
        "motor": motor,
        "smc_status": pred.get("status"),
        "smc_match_kind": _match_kind(pred),
        "smc_support": pred.get("support"),
        "smc_reliability": pred.get("reliability"),
        "smc_record_id": pred.get("record_id"),
        "smc_reason": pred.get("reason"),
        "predicted_fields": meta.get("predicted_fields"),
        "o_prime": meta.get("o_prime"),
        "history": hist,
        "scenario": scn,
        "provenance": provenance,
    }


def _compete(
    rows: list[dict[str, Any]],
    *,
    rng_value: float,
) -> dict[str, Any]:
    groups: dict[str, list] = {}
    actions: list[str] = []
    for r in rows:
        scn = r.get("scenario")
        if not scn:
            continue
        key = str(r["first_action"])
        # Isolate scenario dicts so compete_scenarios jsonish_copy cannot alias live state
        groups.setdefault(key, []).append(sc.jsonish_copy(scn))
        if key not in actions:
            actions.append(key)
    if not actions:
        return {
            "status": "NO_SCENARIOS",
            "selected": None,
            "competition": {"outcome_class": "NO_SUPPORT"},
            "n_actions": 0,
            "n_scenarios": 0,
        }
    # Pure function given groups/actions/rng_value — still pass copies
    result = sc.compete_scenarios(
        groups=sc.jsonish_copy(groups),
        actions=list(actions),
        rng_value=float(rng_value),
    )
    return {
        "status": "OK",
        "selected": result.get("selected"),
        "source": result.get("source"),
        "selection_rule": result.get("selection_rule"),
        "competition": result.get("competition") or {},
        "n_actions": len(actions),
        "n_scenarios": sum(len(v) for v in groups.values()),
        "action_keys": list(actions),
    }


def _dimension_diff(sig_a: str | None, sig_b: str | None) -> dict[str, Any]:
    pa = parse_motor_signature(sig_a or "") or {}
    pb = parse_motor_signature(sig_b or "") or {}
    oa = pa.get("oscillator") or {}
    ob = pb.get("oscillator") or {}
    dims = {
        "neck": pa.get("neck") != pb.get("neck"),
        "emit": bool(oa.get("emit_trigger")) != bool(ob.get("emit_trigger")),
        "freq_delta": int(oa.get("frequency_delta") or 0) != int(ob.get("frequency_delta") or 0),
        "amp_delta": int(oa.get("amplitude_delta") or 0) != int(ob.get("amplitude_delta") or 0),
        "push": bool(pa.get("push")) != bool(pb.get("push")),
        "locomotion": pa.get("locomotion") != pb.get("locomotion"),
    }
    changed = [k for k, v in dims.items() if v]
    return {
        "dimensions_differ": dims,
        "contains_neck": bool(dims["neck"]),
        "contains_osc_emit": bool(dims["emit"]),
        "contains_osc_freq": bool(dims["freq_delta"]),
        "contains_osc_amp": bool(dims["amp_delta"]),
        "contains_push": bool(dims["push"]),
        "single_dimension": len(changed) == 1,
        "single_dimension_name": changed[0] if len(changed) == 1 else None,
        "changed": changed,
    }


def _earliest_divergence(
    *,
    prod_row: dict[str, Any] | None,
    shadow_row: dict[str, Any] | None,
    prod_selected: str | None,
    shadow_selected: str | None,
    classification: str,
) -> str:
    if classification in {"INSUFFICIENT_COMPOSITE_EVIDENCE", "SHADOW_NOT_REPLAYABLE"}:
        return "INSUFFICIENT"
    if not prod_row or not shadow_row:
        return "MOTOR_RESOLUTION"
    if str(prod_row.get("motor_signature")) != str(shadow_row.get("motor_signature")):
        # motor resolution always differs when comparing loco-NONE vs composite
        pass
    # Compare O′
    op = prod_row.get("o_prime") or {}
    os_ = shadow_row.get("o_prime") or {}
    if channel_divergence(op, os_)["global"] > 1e-9:
        # motor already different by construction for composite path
        if str(prod_row.get("motor_signature")) != str(shadow_row.get("motor_signature")):
            return "MOTOR_RESOLUTION"
        return "PREDICTED_O_PRIME"
    hs = int((prod_row.get("history") or {}).get("historical_support") or 0)
    hs2 = int((shadow_row.get("history") or {}).get("historical_support") or 0)
    if hs != hs2 or (prod_row.get("history") or {}).get("status") != (shadow_row.get("history") or {}).get("status"):
        return "HISTORY_RETRIEVAL"
    if (prod_row.get("scenario") is None) != (shadow_row.get("scenario") is None):
        return "PSC_EVIDENCE"
    if str(prod_selected) != str(shadow_selected):
        return "COMPETITION_RESULT"
    return "FINAL_MOTOR"


def classify_outcome(
    *,
    production_loco: str | None,
    production_realized_sig: str | None,
    shadow_selected_key: str | None,
    shadow_selected_loco: str | None,
    shadow_selected_sig: str | None,
    n_composite_scenarios: int,
) -> str:
    if n_composite_scenarios <= 0 or shadow_selected_key is None:
        if n_composite_scenarios <= 0:
            return "INSUFFICIENT_COMPOSITE_EVIDENCE"
        return "SHADOW_NOT_REPLAYABLE"
    if production_loco and shadow_selected_loco and shadow_selected_loco != production_loco:
        return "DIFFERENT_LOCOMOTION"
    # same locomotion (or missing production_loco)
    if production_realized_sig and shadow_selected_sig:
        if production_realized_sig == shadow_selected_sig:
            return "SAME_LOCOMOTION_SAME_COMPOSITE"
        return "SAME_LOCOMOTION_DIFFERENT_COMPOSITE"
    # fall back: compare to synthetic NONE query is insufficient — mark insufficient if no realized
    if shadow_selected_sig and production_realized_sig is None:
        return "SAME_LOCOMOTION_DIFFERENT_COMPOSITE"  # cannot prove same; treat as different realization unknown
    return "SAME_LOCOMOTION_SAME_COMPOSITE"


def replay_tick(
    *,
    observation: dict[str, float],
    smc_store: dict[str, Any],
    prospection: dict[str, Any],
    compression: dict[str, Any] | None,
    loco_candidates: list[str],
    seed: int,
    tick: int,
    production_selected_loco: str | None,
    production_realized_motor: dict[str, Any] | None,
    retrieval_enabled: bool = True,
    min_support: int = 1,
    prefer_exact_composite: bool = True,
    divergence_refine_threshold: float = 0.02,
    run_adaptive: bool = True,
) -> dict[str, Any]:
    """One-tick full composite + adaptive shadow replay (observational)."""
    t0 = time.perf_counter()
    rng_value = _rng_unit(int(seed), int(tick))

    # Isolated history snapshots — production stores untouched
    prosp_snap = _deepcopy_jsonish(prospection or {})
    comp_snap = _deepcopy_jsonish(compression) if compression is not None else None
    smc_before = {
        "queries": smc_store.get("queries"),
        "matched_queries": smc_store.get("matched_queries"),
        "unknown_queries": smc_store.get("unknown_queries"),
        "updates": smc_store.get("updates"),
        "last_query": smc_store.get("last_query"),
        "records_n": len(smc_store.get("records") or {}),
    }

    history_actions = list(loco_candidates)
    realized_sig = _motor_sig_from_realized(production_realized_motor)

    # --- Production baseline replay (loco-only candidates through REAL chain) ---
    prod_rows: list[dict[str, Any]] = []
    for loco in loco_candidates:
        pred = loco_only_query(smc_store, observation, loco, tick=tick)
        row = _build_candidate_row(
            observation=observation,
            pred=pred,
            first_action_key=loco,
            loco=loco,
            motor_signature=pred.get("motor_signature"),
            motor={"locomotion": loco, "neck": "NONE", "oscillator": {}, "push": False},
            prospection=prosp_snap,
            compression=comp_snap,
            history_actions=history_actions,
            retrieval_enabled=retrieval_enabled,
            provenance={"path": "PRODUCTION_LOCO_ONLY_REPLAY", "smc_match_kind": _match_kind(pred)},
        )
        if row:
            prod_rows.append(row)
    prod_compete = _compete(prod_rows, rng_value=rng_value)

    # --- Full observed composite ---
    composite_rows: list[dict[str, Any]] = []
    multi_within = 0
    exact_smc = 0
    o_prime_diff_pairs = 0
    hist_support_vals: list[int] = []
    for loco in loco_candidates:
        observed = [c for c in observed_composites_for_loco(smc_store, loco) if int(c["support"]) >= min_support]
        if len(observed) >= 2:
            multi_within += 1
        loco_o_primes: list[dict[str, float]] = []
        for c in observed:
            pred = composite_query(smc_store, observation, c["motor"], tick=tick)
            kind = _match_kind(pred)
            if prefer_exact_composite and kind == "LOCO_FALLBACK":
                # Do not silently collapse: skip loco-fallback for primary composite analysis
                continue
            if kind == "EXACT_COMPOSITE_MATCH":
                exact_smc += 1
            row = _build_candidate_row(
                observation=observation,
                pred=pred,
                first_action_key=str(c["motor_signature"]),
                loco=loco,
                motor_signature=str(c["motor_signature"]),
                motor=c["motor"],
                prospection=prosp_snap,
                compression=comp_snap,
                history_actions=history_actions,
                retrieval_enabled=retrieval_enabled,
                provenance={
                    "path": "FULL_OBSERVED_COMPOSITE",
                    "smc_match_kind": kind,
                    "smc_support_store": c["support"],
                    "record_id": c.get("record_id"),
                    "locomotion_prefix": loco,
                },
            )
            if row:
                composite_rows.append(row)
                loco_o_primes.append(row.get("o_prime") or {})
                if (row.get("history") or {}).get("status") == oph.MATCH:
                    hist_support_vals.append(int((row.get("history") or {}).get("historical_support") or 0))
        if len(loco_o_primes) >= 2:
            pw = pairwise_divergences(loco_o_primes)
            if pw["max"] > 1e-9:
                o_prime_diff_pairs += 1

    full_compete = _compete(composite_rows, rng_value=rng_value)
    shadow_key = full_compete.get("selected")
    shadow_sig = shadow_key if shadow_key and "|" in str(shadow_key) else None
    shadow_loco = _loco_from_sig(shadow_sig) if shadow_sig else (str(shadow_key) if shadow_key else None)
    # Map selected key back to row
    shadow_row = next((r for r in composite_rows if r["first_action"] == shadow_key), None)
    if shadow_row:
        shadow_sig = shadow_row.get("motor_signature")
        shadow_loco = shadow_row.get("locomotion")

    classification = classify_outcome(
        production_loco=production_selected_loco,
        production_realized_sig=realized_sig,
        shadow_selected_key=shadow_key,
        shadow_selected_loco=shadow_loco,
        shadow_selected_sig=shadow_sig,
        n_composite_scenarios=full_compete.get("n_scenarios") or 0,
    )

    # Production row for selected loco (for divergence chain)
    prod_sel_key = prod_compete.get("selected")
    prod_row = next((r for r in prod_rows if r["first_action"] == prod_sel_key), None)
    if production_selected_loco:
        prod_row = next((r for r in prod_rows if r["locomotion"] == production_selected_loco), prod_row)

    earliest = _earliest_divergence(
        prod_row=prod_row,
        shadow_row=shadow_row,
        prod_selected=production_selected_loco,
        shadow_selected=shadow_loco,
        classification=classification,
    )

    dim_attr = _dimension_diff(realized_sig, shadow_sig) if classification != "SAME_LOCOMOTION_SAME_COMPOSITE" else {
        "dimensions_differ": {},
        "contains_neck": False,
        "contains_osc_emit": False,
        "contains_osc_freq": False,
        "contains_osc_amp": False,
        "contains_push": False,
        "single_dimension": False,
        "changed": [],
    }

    sensory_attr = None
    if prod_row and shadow_row:
        sensory_attr = channel_divergence(prod_row.get("o_prime") or {}, shadow_row.get("o_prime") or {})

    # --- Adaptive refinement shadow ---
    adaptive_meta: dict[str, Any] = {"ran": False}
    adaptive_compete: dict[str, Any] = {"status": "SKIPPED"}
    adaptive_classification = "NOT_RUN"
    if run_adaptive:
        adaptive_rows: list[dict[str, Any]] = []
        refined_locos = []
        for loco in loco_candidates:
            observed = [c for c in observed_composites_for_loco(smc_store, loco) if int(c["support"]) >= min_support]
            # Build O′ for observed with exact preds
            cand_local = []
            for c in observed:
                pred = composite_query(smc_store, observation, c["motor"], tick=tick)
                if prefer_exact_composite and _match_kind(pred) == "LOCO_FALLBACK":
                    continue
                if pred.get("status") not in {smc.MATCH, smc.LOW_SUPPORT} or not pred.get("predicted_delta"):
                    continue
                op = o_prime_from_pred(observation, pred).get("o_prime") or observation
                cand_local.append((c, pred, op))
            would_refine = False
            if len(cand_local) >= 2:
                pw = pairwise_divergences([x[2] for x in cand_local])
                would_refine = float(pw["max"]) >= float(divergence_refine_threshold)
            if would_refine:
                refined_locos.append(loco)
                for c, pred, _op in cand_local:
                    row = _build_candidate_row(
                        observation=observation,
                        pred=pred,
                        first_action_key=str(c["motor_signature"]),
                        loco=loco,
                        motor_signature=str(c["motor_signature"]),
                        motor=c["motor"],
                        prospection=prosp_snap,
                        compression=comp_snap,
                        history_actions=history_actions,
                        retrieval_enabled=retrieval_enabled,
                        provenance={"path": "ADAPTIVE_REFINEMENT", "threshold": divergence_refine_threshold},
                    )
                    if row:
                        adaptive_rows.append(row)
            else:
                # keep coarse loco candidate from production replay set
                prow = next((r for r in prod_rows if r["locomotion"] == loco), None)
                if prow:
                    # re-key already loco
                    adaptive_rows.append(prow)
        adaptive_compete = _compete(adaptive_rows, rng_value=rng_value)
        a_key = adaptive_compete.get("selected")
        a_row = next((r for r in adaptive_rows if r["first_action"] == a_key), None)
        a_sig = (a_row or {}).get("motor_signature")
        a_loco = (a_row or {}).get("locomotion") or _loco_from_sig(a_sig) or a_key
        adaptive_classification = classify_outcome(
            production_loco=production_selected_loco,
            production_realized_sig=realized_sig,
            shadow_selected_key=a_key,
            shadow_selected_loco=a_loco,
            shadow_selected_sig=a_sig if a_sig and "|" in str(a_sig) else None,
            n_composite_scenarios=adaptive_compete.get("n_scenarios") or 0,
        )
        # Agreement with full composite
        full_vs_adapt = {
            "same_selected_key": str(a_key) == str(shadow_key),
            "same_locomotion": str(a_loco) == str(shadow_loco),
            "same_composite": str(a_sig) == str(shadow_sig),
            "same_classification": adaptive_classification == classification,
        }
        adaptive_meta = {
            "ran": True,
            "threshold": divergence_refine_threshold,
            "refined_locos": refined_locos,
            "n_candidates": adaptive_compete.get("n_actions"),
            "n_scenarios": adaptive_compete.get("n_scenarios"),
            "selected": a_key,
            "selected_loco": a_loco,
            "selected_sig": a_sig,
            "classification": adaptive_classification,
            "vs_full_composite": full_vs_adapt,
        }

    smc_after = {
        "queries": smc_store.get("queries"),
        "matched_queries": smc_store.get("matched_queries"),
        "unknown_queries": smc_store.get("unknown_queries"),
        "updates": smc_store.get("updates"),
        "last_query": smc_store.get("last_query"),
        "records_n": len(smc_store.get("records") or {}),
    }
    mutation_ok = smc_before == smc_after

    hist_diff = False
    if hist_support_vals:
        hist_diff = (max(hist_support_vals) - min(hist_support_vals)) >= 1

    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    return {
        "schema": SCHEMA,
        "analysis_only": True,
        "does_not_affect_agent": True,
        "tick": tick,
        "seed": seed,
        "rng_value": rng_value,
        "production": {
            "selected_loco": production_selected_loco,
            "realized_composite_sig": realized_sig,
            "realized_motor": production_realized_motor,
            "baseline_replay_selected": prod_compete.get("selected"),
            "baseline_replay_outcome": (prod_compete.get("competition") or {}).get("outcome_class"),
            "baseline_n_scenarios": prod_compete.get("n_scenarios"),
        },
        "full_composite": {
            "n_candidates_built": len(composite_rows),
            "n_scenarios": full_compete.get("n_scenarios"),
            "n_actions": full_compete.get("n_actions"),
            "selected": shadow_key,
            "selected_loco": shadow_loco,
            "selected_sig": shadow_sig,
            "compete_outcome": (full_compete.get("competition") or {}).get("outcome_class"),
            "compete_source": full_compete.get("source"),
            "exact_smc_predictions": exact_smc,
            "multi_composite_within_loco": multi_within,
            "o_prime_differentiated_loco_branches": o_prime_diff_pairs,
            "history_support_differentiated": hist_diff,
        },
        "classification": classification,
        "earliest_divergence": earliest,
        "motor_dimension_attribution": dim_attr,
        "sensory_family_attribution": sensory_attr,
        "adaptive": adaptive_meta,
        "mutation_audit": {
            "smc_counters_unchanged": mutation_ok,
            "smc_before": smc_before,
            "smc_after": smc_after,
            "history_snapshot_isolated": True,
            "compete_uses_copied_groups": True,
            "rng": "deterministic _rng_unit(seed,tick); no mutable RNG advance",
        },
        "reused_production_functions": REUSED_PRODUCTION,
        "elapsed_ms": round(elapsed_ms, 4),
        "forensic_compact": {
            "production_loco": production_selected_loco,
            "production_realized": realized_sig,
            "shadow_winner": shadow_sig,
            "shadow_loco": shadow_loco,
            "classification": classification,
            "earliest_divergence": earliest,
        },
    }


def support_proxy_class_from_prior(prior_shadow_tick: dict[str, Any] | None) -> str | None:
    """Map prior support-proxy comparison_class into the real-replay taxonomy."""
    if not prior_shadow_tick:
        return None
    c = str(prior_shadow_tick.get("comparison_class") or "")
    if c == "SAME_LOCOMOTION_SAME_REFINEMENT":
        return "SAME_LOCOMOTION_SAME_COMPOSITE"
    return c or None
