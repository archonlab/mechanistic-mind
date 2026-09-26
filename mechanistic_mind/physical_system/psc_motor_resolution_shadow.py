
"""PSC motor resolution — SHADOW evaluators (LOCO_ONLY vs OBSERVED_COMPOSITE vs ADAPTIVE).

Does NOT change production PSC selection.
All queries run on a shallow-copied store shell so live store counters/last_query
are not mutated (EXACT_MATCH requirement).
"""
from __future__ import annotations

import copy
import math
import time
from typing import Any

from mechanistic_mind.physical_system import sensorimotor_consequence as smc
from mechanistic_mind.physical_system import o_prime_history_bridge as ohb

SCHEMA = "mm.psc_motor_resolution_shadow.v1"

FAMILY_KEYS: dict[str, tuple[str, ...]] = {
    "optical": (
        "exo_0", "exo_1", "exo_2",
        "surface_c0_0", "surface_c0_1", "surface_c0_2",
        "surface_c1_0", "surface_c1_1", "surface_c1_2",
        "surface_c2_0", "surface_c2_1", "surface_c2_2",
    ),
    "field": ("local.FIELD_A", "local.FIELD_B"),
    "bilateral": tuple(f"osc_l_{i}" for i in range(6)) + tuple(f"osc_r_{i}" for i in range(6)),
    "vestibular": ("vest_0", "vest_1"),
    "proprio": ("prop_neck_0", "prop_neck_1"),
    "local_world": ("local.T", "local.M0", "local.M1", "local.M2", "local.vx", "local.vy"),
    "body": ("body.B0", "body.B1", "body.B2", "body.T", "body.mech", "body.vx", "body.vy"),
    "internal": ("internal.c0", "internal.c1", "internal.c2", "internal.c3", "internal.c4"),
}


def _store_snapshot(store: dict[str, Any]) -> dict[str, Any]:
    """Copy store for read-only shadow queries without mutating production stats."""
    snap = {
        "schema": store.get("schema"),
        "enabled": store.get("enabled"),
        "capacity": store.get("capacity"),
        "records": store.get("records") or {},  # shared read-only records
        "channel_list": list(store.get("channel_list") or smc.SENSORY_CHANNELS),
        "families": dict(store.get("families") or {}),
        "bilateral": store.get("bilateral"),
        "shuffle_motor_labels": False,
        "ticks": store.get("ticks"),
        "updates": 0,
        "queries": 0,
        "matched_queries": 0,
        "unknown_queries": 0,
        "evictions": 0,
        "next_id": store.get("next_id"),
        "last_update": None,
        "last_query": None,
        "metrics_affect_cognition": False,
    }
    return snap


def parse_motor_signature(sig: str) -> dict[str, Any] | None:
    """Parse L:…|N:…|E:…|F:…|A:…|P:… into COMPOSITE_MOTOR_V1-like dict."""
    if not sig or sig.startswith("SHUF:"):
        return None
    parts = {}
    for tok in str(sig).split("|"):
        if ":" not in tok:
            continue
        k, v = tok.split(":", 1)
        parts[k] = v
    if "L" not in parts:
        return None
    return {
        "locomotion": parts.get("L", "WAIT"),
        "neck": parts.get("N", "NONE"),
        "oscillator": {
            "emit_trigger": bool(int(parts.get("E", "0") or 0)),
            "frequency_delta": int(parts.get("F", "0") or 0),
            "amplitude_delta": int(parts.get("A", "0") or 0),
        },
        "push": bool(int(parts.get("P", "0") or 0)),
        "motor_signature": sig,
    }


def observed_composites_for_loco_scan(store: dict[str, Any], loco: str) -> list[dict[str, Any]]:
    """Reference full-record scan. Tests/oracle — same membership/order as production."""
    prefix = f"L:{loco}|"
    out = []
    for row in (store.get("records") or {}).values():
        if not isinstance(row, dict):
            continue
        ms = str(row.get("motor_signature") or "")
        if not ms.startswith(prefix):
            continue
        parsed = parse_motor_signature(ms)
        if not parsed:
            continue
        out.append({
            "motor_signature": ms,
            "motor": parsed,
            "support": int(row.get("support") or 0),
            "record_id": row.get("record_id"),
            "last_tick": row.get("last_tick"),
            "context_signature": row.get("context_signature"),
        })
    by_sig: dict[str, dict] = {}
    for row in out:
        sig = str(row["motor_signature"])
        prev = by_sig.get(sig)
        if prev is None or int(row["support"]) > int(prev["support"]):
            by_sig[sig] = row
    collapsed = list(by_sig.values())
    collapsed.sort(key=lambda r: (-int(r["support"]), str(r["motor_signature"])))
    return collapsed


def observed_composites_for_loco(store: dict[str, Any], loco: str) -> list[dict[str, Any]]:
    """Empirically supported composite signatures sharing locomotion prefix (no Cartesian)."""
    out = []
    for row in smc.iter_records_for_loco(store, str(loco)):
        ms = str(row.get("motor_signature") or "")
        parsed = parse_motor_signature(ms)
        if not parsed:
            continue
        out.append({
            "motor_signature": ms,
            "motor": parsed,
            "support": int(row.get("support") or 0),
            "record_id": row.get("record_id"),
            "last_tick": row.get("last_tick"),
            "context_signature": row.get("context_signature"),
        })
    by_sig: dict[str, dict] = {}
    for row in out:
        sig = str(row["motor_signature"])
        prev = by_sig.get(sig)
        if prev is None or int(row["support"]) > int(prev["support"]):
            by_sig[sig] = row
    collapsed = list(by_sig.values())
    collapsed.sort(key=lambda r: (-int(r["support"]), str(r["motor_signature"])))
    return collapsed


def loco_only_query(store: dict[str, Any], observation: dict[str, float], loco: str, tick: int | None = None) -> dict[str, Any]:
    """Mirror production query_candidates for one locomotion (on snapshot store)."""
    snap = _store_snapshot(store)
    motor = {"locomotion": loco, "neck": "NONE", "oscillator": {}, "push": False}
    pred = smc.query(snap, observation=observation, motor=motor, tick=tick)
    if pred.get("status") == smc.UNKNOWN:
        best = None
        for row in (snap.get("records") or {}).values():
            ms = str(row.get("motor_signature") or "")
            if ms.startswith(f"L:{loco}|"):
                if best is None or int(row.get("support") or 0) > int(best.get("support") or 0):
                    best = row
        if best is not None:
            pred = {
                "kind": "SENSORIMOTOR_CONSEQUENCE_PREDICTED",
                "status": smc.MATCH if int(best.get("support") or 0) >= 3 else smc.LOW_SUPPORT,
                "reason": "loco_prefix_aggregate",
                "motor_signature": best.get("motor_signature"),
                "predicted_delta": smc.mean_delta(best),
                "support": int(best.get("support") or 0),
                "reliability": smc.reliability(best),
                "record_id": best.get("record_id"),
                "tick": tick,
                "candidate_locomotion": loco,
                "aggregation": "MAX_SUPPORT_UNDER_PREFIX",  # not mean across composites
            }
        else:
            pred = {**pred, "candidate_locomotion": loco}
    else:
        pred = {**pred, "candidate_locomotion": loco, "aggregation": "EXACT_NONE_SIDECHANNELS"}
    return pred


def composite_query(store: dict[str, Any], observation: dict[str, float], motor: dict[str, Any], tick: int | None = None) -> dict[str, Any]:
    snap = _store_snapshot(store)
    return smc.query(snap, observation=observation, motor=motor, tick=tick)


def o_prime_from_pred(observation: dict[str, float], pred: dict[str, Any]) -> dict[str, Any]:
    delta = pred.get("predicted_delta") if isinstance(pred.get("predicted_delta"), dict) else None
    return ohb.construct_o_prime(observation, delta)


def channel_divergence(o1: dict[str, float], o2: dict[str, float], channels: tuple[str, ...] | None = None) -> dict[str, Any]:
    """Mean absolute difference on channels (diagnostics only; channels ≈ [0,1] or vest-scale)."""
    keys = channels or tuple(smc.SENSORY_CHANNELS)
    diffs = []
    for k in keys:
        try:
            a = float(o1.get(k, 0.0))
            b = float(o2.get(k, 0.0))
        except (TypeError, ValueError):
            continue
        diffs.append(abs(a - b))
    global_d = sum(diffs) / max(1, len(diffs))
    fam = {}
    for name, fkeys in FAMILY_KEYS.items():
        fd = [abs(float(o1.get(k, 0.0)) - float(o2.get(k, 0.0))) for k in fkeys]
        fam[name] = sum(fd) / max(1, len(fd))
    return {"global": global_d, "families": fam, "n_channels": len(diffs)}


def pairwise_divergences(o_primes: list[dict[str, float]]) -> dict[str, Any]:
    if len(o_primes) < 2:
        return {"n": len(o_primes), "pairwise": [], "max": 0.0, "median": 0.0, "mean": 0.0}
    vals = []
    pairs = []
    for i in range(len(o_primes)):
        for j in range(i + 1, len(o_primes)):
            d = channel_divergence(o_primes[i], o_primes[j])
            vals.append(d["global"])
            pairs.append({"i": i, "j": j, "global": d["global"], "families": d["families"]})
    vals_sorted = sorted(vals)
    mid = len(vals_sorted) // 2
    median = vals_sorted[mid] if len(vals_sorted) % 2 == 1 else 0.5 * (vals_sorted[mid - 1] + vals_sorted[mid])
    return {
        "n": len(o_primes),
        "pairwise": pairs,
        "max": max(vals) if vals else 0.0,
        "median": median,
        "mean": sum(vals) / max(1, len(vals)),
    }


def aggregate_out_of_manifold(
    o_agg: dict[str, float],
    o_composites: list[dict[str, float]],
    *,
    threshold: float = 0.05,
) -> dict[str, Any]:
    if not o_composites:
        return {"status": "INSUFFICIENT_EMPIRICAL_SUPPORT", "nearest": None, "distances": []}
    dists = [channel_divergence(o_agg, oc)["global"] for oc in o_composites]
    nearest = min(dists)
    # Out-of-manifold if aggregate is farther from ALL composites than threshold
    # AND nearest is above threshold (aggregate not near any real composite)
    status = "AGGREGATE_OUT_OF_MANIFOLD" if nearest >= threshold else "NEAR_SOME_COMPOSITE"
    return {"status": status, "nearest": nearest, "distances": dists, "threshold": threshold}


def evaluate_loco_shadow(
    store: dict[str, Any],
    observation: dict[str, float],
    loco: str,
    *,
    tick: int | None = None,
    min_support: int = 1,
    divergence_refine_threshold: float = 0.02,
) -> dict[str, Any]:
    """Shadow pack for one locomotion: LOCO_ONLY vs OBSERVED_COMPOSITE vs ADAPTIVE."""
    t0 = time.perf_counter()
    loco_pred = loco_only_query(store, observation, loco, tick=tick)
    loco_op = o_prime_from_pred(observation, loco_pred)
    o_loco = loco_op.get("o_prime") or observation

    observed = [c for c in observed_composites_for_loco(store, loco) if int(c["support"]) >= min_support]
    composite_rows = []
    o_primes = []
    for c in observed:
        pred = composite_query(store, observation, c["motor"], tick=tick)
        if not pred.get("predicted_delta"):
            continue
        op = o_prime_from_pred(observation, pred)
        o_primes.append(op.get("o_prime") or observation)
        composite_rows.append({
            "motor_signature": c["motor_signature"],
            "support": c["support"],
            "record_id": c["record_id"],
            "query_status": pred.get("status"),
            "query_support": pred.get("support"),
            "reliability": pred.get("reliability"),
            "predicted_fields": op.get("predicted_fields"),
            "divergence_from_loco": channel_divergence(o_loco, op.get("o_prime") or observation),
        })

    pw = pairwise_divergences(o_primes)
    oom = aggregate_out_of_manifold(o_loco, o_primes)

    # Adaptive: refine if pairwise max divergence >= threshold and >=2 composites with predictions
    would_refine = bool(len(composite_rows) >= 2 and pw["max"] >= divergence_refine_threshold)
    adaptive_candidates = composite_rows if would_refine else [{
        "motor_signature": loco_pred.get("motor_signature"),
        "support": loco_pred.get("support"),
        "query_status": loco_pred.get("status"),
        "reason": "KEEP_COARSE" if not would_refine else "REFINED",
        "aggregation": loco_pred.get("aggregation"),
    }]

    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    return {
        "schema": SCHEMA,
        "locomotion": loco,
        "loco_only": {
            "status": loco_pred.get("status"),
            "reason": loco_pred.get("reason"),
            "aggregation": loco_pred.get("aggregation"),
            "motor_signature": loco_pred.get("motor_signature"),
            "support": loco_pred.get("support"),
            "reliability": loco_pred.get("reliability"),
            "predicted_fields": loco_op.get("predicted_fields"),
        },
        "observed_composite_count": len(observed),
        "supported_with_prediction": len(composite_rows),
        "composites": composite_rows,
        "within_loco_divergence": pw,
        "out_of_manifold": oom,
        "adaptive": {
            "would_refine": would_refine,
            "threshold": divergence_refine_threshold,
            "n_candidates": len(adaptive_candidates),
            "reason": (
                "predictive divergence among empirically supported composites"
                if would_refine
                else "low divergence or insufficient composites"
            ),
        },
        "elapsed_ms": round(elapsed_ms, 4),
        "analysis_only": True,
        "does_not_affect_agent": True,
    }


def motor_dimension_ablation(
    store: dict[str, Any],
    observation: dict[str, float],
    motor: dict[str, Any],
    *,
    tick: int | None = None,
) -> dict[str, Any]:
    """Collapse one motor dimension at a time; measure O′ change (diagnostic)."""
    base_pred = composite_query(store, observation, motor, tick=tick)
    if not base_pred.get("predicted_delta"):
        return {"status": "NO_PREDICTION"}
    base_o = o_prime_from_pred(observation, base_pred).get("o_prime") or observation
    contrib = {}
    ablations = {
        "neck": {**motor, "neck": "NONE"},
        "osc_emit": {**motor, "oscillator": {**(motor.get("oscillator") or {}), "emit_trigger": False}},
        "osc_freq": {**motor, "oscillator": {**(motor.get("oscillator") or {}), "frequency_delta": 0}},
        "osc_amp": {**motor, "oscillator": {**(motor.get("oscillator") or {}), "amplitude_delta": 0}},
        "push": {**motor, "push": False},
    }
    for name, m2 in ablations.items():
        if smc.motor_signature_from_composite(motor) == smc.motor_signature_from_composite(m2):
            contrib[name] = {"status": "NOT_APPLICABLE", "global": 0.0}
            continue
        p2 = composite_query(store, observation, m2, tick=tick)
        if not p2.get("predicted_delta"):
            contrib[name] = {"status": "NO_ABLATED_PREDICTION", "global": None}
            continue
        o2 = o_prime_from_pred(observation, p2).get("o_prime") or observation
        d = channel_divergence(base_o, o2)
        contrib[name] = {"status": "OK", "global": d["global"], "families": d["families"]}
    return {"status": "OK", "contributions": contrib}


def shadow_tick(
    store: dict[str, Any],
    observation: dict[str, float],
    loco_candidates: list[str],
    *,
    tick: int | None = None,
    production_selected_loco: str | None = None,
    divergence_refine_threshold: float = 0.02,
) -> dict[str, Any]:
    """Full shadow evaluation for one PSC tick (observational)."""
    per_loco = {}
    for loco in loco_candidates:
        per_loco[loco] = evaluate_loco_shadow(
            store, observation, loco, tick=tick,
            divergence_refine_threshold=divergence_refine_threshold,
        )

    # Shadow "selection" proxy: among locos, pick max support of best composite
    # (does NOT call production compete_scenarios — ranking diagnostic only)
    ranking = []
    for loco, pack in per_loco.items():
        comps = pack.get("composites") or []
        best_c = max(comps, key=lambda c: int(c.get("query_support") or 0), default=None)
        loco_s = int((pack.get("loco_only") or {}).get("support") or 0)
        ranking.append({
            "locomotion": loco,
            "loco_only_support": loco_s,
            "best_composite_support": int((best_c or {}).get("query_support") or 0),
            "best_composite_sig": (best_c or {}).get("motor_signature"),
            "within_max_div": (pack.get("within_loco_divergence") or {}).get("max"),
            "would_refine": (pack.get("adaptive") or {}).get("would_refine"),
        })
    by_loco = sorted(ranking, key=lambda r: (-r["loco_only_support"], r["locomotion"]))
    by_comp = sorted(ranking, key=lambda r: (-r["best_composite_support"], r["locomotion"]))
    shadow_loco = by_loco[0]["locomotion"] if by_loco else None
    shadow_comp_loco = by_comp[0]["locomotion"] if by_comp else None
    shadow_comp_sig = by_comp[0]["best_composite_sig"] if by_comp else None

    class_ = "INSUFFICIENT_COMPOSITE_EVIDENCE"
    if production_selected_loco:
        if shadow_comp_loco == production_selected_loco:
            # same loco — check if refinement differs from NONE aggregate sig
            class_ = "SAME_LOCOMOTION_SAME_REFINEMENT"
            prod_pack = per_loco.get(production_selected_loco) or {}
            if (prod_pack.get("adaptive") or {}).get("would_refine"):
                class_ = "SAME_LOCOMOTION_DIFFERENT_COMPOSITE"
        elif shadow_comp_loco and shadow_comp_loco != production_selected_loco:
            class_ = "DIFFERENT_LOCOMOTION"

    n_with_multi = sum(1 for p in per_loco.values() if int(p.get("supported_with_prediction") or 0) >= 2)
    n_high_div = sum(
        1 for p in per_loco.values()
        if float((p.get("within_loco_divergence") or {}).get("max") or 0) >= divergence_refine_threshold
    )
    n_oom = sum(1 for p in per_loco.values() if (p.get("out_of_manifold") or {}).get("status") == "AGGREGATE_OUT_OF_MANIFOLD")

    return {
        "schema": SCHEMA,
        "tick": tick,
        "analysis_only": True,
        "does_not_affect_agent": True,
        "production_selected_loco": production_selected_loco,
        "per_locomotion": per_loco,
        "ranking_loco_only": by_loco,
        "ranking_observed_composite": by_comp,
        "shadow_selected_loco_by_loco_support": shadow_loco,
        "shadow_selected_loco_by_composite_support": shadow_comp_loco,
        "shadow_selected_composite_signature": shadow_comp_sig,
        "comparison_class": class_,
        "summary": {
            "n_loco_candidates": len(loco_candidates),
            "n_loco_with_multi_composite_pred": n_with_multi,
            "n_loco_high_within_divergence": n_high_div,
            "n_loco_out_of_manifold": n_oom,
            "total_observed_composites": sum(int(p.get("observed_composite_count") or 0) for p in per_loco.values()),
            "total_supported_predictions": sum(int(p.get("supported_with_prediction") or 0) for p in per_loco.values()),
        },
    }
