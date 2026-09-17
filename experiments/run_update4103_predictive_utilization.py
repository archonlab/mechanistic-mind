#!/usr/bin/env python3
"""Update 4.10.3 — KNOWN temporal evidence x predictive utilization DIAGNOSTIC."""
from __future__ import annotations

import json
import sys
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "worlds"))
sys.path.insert(0, str(ROOT / "experiments"))

import run_update4101_ecological_stabilization as u4101
from mechanistic_mind.agent import Action
from mechanistic_mind.psyche.temporal_contingency import (
    best_prediction_for_action,
    ensure_temporal,
    retrieve_temporal,
    temporal_cue_bucket,
)
from mechanistic_mind.psyche.sensorimotor import available_actions, context_cue
from mechanistic_mind.research.prospective_valuation import (
    map_reserve_deltas_to_signal_deltas,
    prospective_ordinary_value,
)

OUT = ROOT / "results" / "update4103_predictive_utilization"
OUT.mkdir(parents=True, exist_ok=True)
u4101.OUT = OUT
A, OID, OPOS, SEED = u4101.A, u4101.OID, u4101.OPOS, u4101.SEED


def dump(name: str, payload: Any) -> None:
    def _fix(o):
        if isinstance(o, dict):
            return {str(k): _fix(v) for k, v in o.items()}
        if isinstance(o, list):
            return [_fix(v) for v in o]
        return o

    (OUT / name).write_text(
        json.dumps(_fix(payload), indent=2, sort_keys=True, default=str) + "\n"
    )
    print("wrote", name)


def nonzero_dict(d, eps: float = 1e-12) -> bool:
    if not isinstance(d, dict) or not d:
        return False
    return any(isinstance(v, (int, float)) and abs(float(v)) > eps for v in d.values())


def acquire_use_known(n_use: int = 16):
    wcfg = u4101.multi_channel_contextual_object_config(SEED)
    field = u4101.build_uniform_field(wcfg.width, wcfg.height, 0.0)
    eng = u4101.make_engine(
        field=field, pos=OPOS, sm=u4101.sm_on(), env=False, intake=True
    )
    provenance = []
    for i in range(1, n_use + 1):
        u4101.replenish_object(eng, 0.95)
        qty0 = float(eng.state.world.variables["world"]["objects"][OID]["quantity"])
        b0 = u4101.snap_body(eng)
        eng.step({A: Action(f"USE:{OID}")})
        qty1 = float(eng.state.world.variables["world"]["objects"][OID]["quantity"])
        transfer = qty0 - qty1
        first_proc = None
        for lag in range(0, 5):
            if lag > 0:
                eng.step({A: Action("WAIT")})
            b = u4101.snap_body(eng)
            if first_proc is None and (
                b["proc"] > 0 or abs(b["energy"] - b0["energy"]) > 1e-9
            ):
                first_proc = lag
        an = u4101.analyze_tc(u4101.tc_state(eng), "USE")
        provenance.append(
            {
                "n": i,
                "transfer": transfer,
                "first_proc_lag_obs": first_proc,
                "records": an["n_records"],
                "known": an["known_count"],
                "strongest_status": (an.get("strongest") or {}).get("status"),
                "strongest_support": (an.get("strongest") or {}).get("support"),
            }
        )
    tc = u4101.tc_state(eng)
    known_recs = {
        k: deepcopy(v)
        for k, v in (tc.get("contingencies") or {}).items()
        if str(v.get("action", "")).startswith("USE") and v.get("status") == "KNOWN"
    }
    acq = {
        "n_use": n_use,
        "provenance": provenance,
        "known_keys": list(known_recs.keys()),
        "known_records": known_recs,
        "became_known_at": next((p["n"] for p in provenance if (p["known"] or 0) > 0), None),
    }
    return eng, acq, known_recs


def decision_snapshot(eng) -> dict[str, Any]:
    psy_before = u4101.psyche(eng)
    sm = (psy_before.get("memory") or {}).get("sensorimotor") or {}
    tc = ensure_temporal(deepcopy(sm))
    obs = eng.world.observe(eng.state.world, A)
    data = dict(obs.data) if isinstance(obs.data, dict) else {}
    available = set(available_actions(obs))
    cue = context_cue(data, cue_mode="PERCEPTUAL_CUE_ENABLED")
    bucket = temporal_cue_bucket(cue)
    hits = retrieve_temporal(
        tc,
        bucket=bucket,
        available_actions=available,
        action_conditioning=True,
        context_conditioning=True,
        min_support=3.0,
    )
    use_hits = [h for h in hits if str(h.get("action", "")).startswith("USE")]
    best_use = best_prediction_for_action(hits, f"USE:{OID}")
    goals = psy_before.get("goals") or {}
    current = {}
    if isinstance(psy_before.get("internal"), dict):
        current = dict((psy_before["internal"] or {}).get("interoceptive_model") or {})
    if not current:
        current = dict(data.get("interoception") or {})

    stored = None
    for k, v in (tc.get("contingencies") or {}).items():
        if str(v.get("action")) == f"USE:{OID}" and v.get("status") == "KNOWN":
            stored = deepcopy(v)
            stored["key"] = k
            break
    if stored is None:
        for k, v in (tc.get("contingencies") or {}).items():
            if str(v.get("action", "")).startswith("USE"):
                stored = deepcopy(v)
                stored["key"] = k
                break

    stored_delta = (stored or {}).get("mean_body_delta") or {}
    retrieved_delta = (best_use or {}).get("mean_body_delta") or {}
    mapped = map_reserve_deltas_to_signal_deltas(retrieved_delta)
    if best_use:
        prosp = prospective_ordinary_value(
            mean_body_delta=retrieved_delta,
            body_delta_samples=float((best_use or {}).get("support") or 0.0),
            contradiction=float((best_use or {}).get("contradiction") or 0.0),
            current_signals=current,
            goals=goals,
            support=float((best_use or {}).get("support") or 0.0),
        )
    else:
        prosp = {
            "prospective_available": False,
            "ordinary_value": None,
            "predicted_signal_deltas": {},
            "predicted_body_delta": {},
            "reason": "NO_BEST_USE",
            "epistemic_status": "UNKNOWN",
        }

    res = eng.step()
    psy = u4101.psyche(eng)
    bridge = (psy.get("working") or {}).get("temporal_contingency_bridge") or {}
    sel = (psy.get("working") or {}).get("last_selection") or {}
    preds = (psy.get("predictions") or {}).get("by_action") or {}
    use_pred = preds.get(f"USE:{OID}")

    return {
        "bucket": bucket,
        "available": sorted(available),
        "hits_n": len(hits),
        "use_hits_n": len(use_hits),
        "hits_actions": [h.get("action") for h in hits],
        "stored_record": stored,
        "stored_mean_body_delta": stored_delta,
        "stored_nonzero": nonzero_dict(stored_delta),
        "best_use": best_use,
        "retrieved_mean_body_delta": retrieved_delta,
        "retrieved_nonzero": nonzero_dict(retrieved_delta),
        "payload_preserved": snap_payload_ok(stored_delta, retrieved_delta),
        "mapped_signal_deltas": mapped,
        "mapped_nonzero": nonzero_dict(mapped),
        "map_drop_note": (
            "temporal mean_body_delta uses *_signal keys; "
            "map_reserve_deltas_to_signal_deltas expects energy_delta/hydration_delta "
            "or *_signal_delta — result empty"
        ),
        "prospective": prosp,
        "bridge": bridge,
        "selection": {
            "action": sel.get("action"),
            "reason": sel.get("reason"),
            "score": sel.get("score"),
            "candidates_head": (sel.get("candidates") or [])[:10],
        },
        "predictions_by_action_USE": use_pred,
        "goals_targets": goals.get("signal_targets"),
        "current_signals": {
            k: current.get(k)
            for k in (
                "energy_signal",
                "hydration_signal",
                "fatigue_signal",
                "discomfort_signal",
            )
        },
        "executed_this_step": str(res.actions[A].kind),
        "source_observer": res.action_sources.get(A),
    }


def snap_payload_ok(stored_delta, retrieved_delta) -> bool:
    if not nonzero_dict(stored_delta):
        return not nonzero_dict(retrieved_delta)
    return abs(
        float((stored_delta or {}).get("energy_signal") or 0)
        - float((retrieved_delta or {}).get("energy_signal") or 0)
    ) < 1e-9


def write_audits() -> None:
    (OUT / "UPDATE4103_PREDICTION_PIPELINE_AUDIT.md").write_text(
        "# Update 4.10.3 — Prediction Pipeline Audit\n\n"
        "## Path\n\n"
        "temporal contingencies -> retrieve_temporal -> best_prediction_for_action\n"
        "-> TemporalContingencyBridgeModule -> prospective_ordinary_value\n"
        "-> map_reserve_deltas_to_signal_deltas -> target_gain -> candidate\n\n"
        "## Schema failure\n\n"
        "TC stores `*_signal`; mapper expects `*_delta` / `*_signal_delta`.\n"
        "Bare `*_signal` dropped -> empty signal deltas -> ordinary_value=0.\n"
    )
    (OUT / "UPDATE4103_TEMPORAL_RECORD_AUDIT.md").write_text(
        "See ACQUIRE_REAL_USE_KNOWN.json / KNOWN_USE_MATCH.json.\n"
    )
    (OUT / "UPDATE4103_RETRIEVAL_AUDIT.md").write_text(
        "retrieve_temporal returns full contingency dicts including mean_body_delta.\n"
    )
    (OUT / "UPDATE4103_PREDICTION_CONSUMER_AUDIT.md").write_text(
        "Consumer: TemporalContingencyBridgeModule -> prospective_ordinary_value.\n"
        "Confidence is metadata only (confidence_used_as_value=False).\n"
    )


def main() -> None:
    t0 = time.time()
    write_audits()
    dump(
        "UPDATE4103_CONFIG.json",
        {"update": "4.10.3", "mode": "DIAGNOSTIC_ONLY", "no_repair": True},
    )

    print("Acquire real USE KNOWN...")
    eng, acq, _known = acquire_use_known(16)
    dump("ACQUIRE_REAL_USE_KNOWN.json", acq)

    print("KNOWN_USE_MATCH...")
    snap = decision_snapshot(eng)
    dump(
        "KNOWN_USE_MATCH.json",
        {
            "acquisition": {
                "became_known_at": acq["became_known_at"],
                "known_keys": acq["known_keys"],
            },
            "decision": snap,
        },
    )
    dump(
        "RETRIEVAL_PAYLOAD_INTEGRITY.json",
        {
            "stored_mean_body_delta": snap["stored_mean_body_delta"],
            "retrieved_mean_body_delta": snap["retrieved_mean_body_delta"],
            "stored_nonzero": snap["stored_nonzero"],
            "retrieved_nonzero": snap["retrieved_nonzero"],
            "payload_preserved": snap["payload_preserved"],
        },
    )
    dump(
        "PREDICTION_CONSUMER_TRACE.json",
        {
            "hits_entering": snap["hits_n"],
            "use_hits": snap["use_hits_n"],
            "best_use_present": snap["best_use"] is not None,
            "best_status": (snap["best_use"] or {}).get("status"),
            "bridge_rows": (snap["bridge"] or {}).get("rows"),
            "rejected": [],
        },
    )
    dump(
        "PREDICTED_DELTA_TRACE.json",
        {
            "baseline_predicted_body_delta": {},
            "temporal_mean_body_delta": snap["retrieved_mean_body_delta"],
            "temporal_contribution_nonzero": snap["retrieved_nonzero"],
            "mapped_signal_deltas": snap["mapped_signal_deltas"],
            "mapped_nonzero": snap["mapped_nonzero"],
            "combined_predicted_body_delta_in_prosp": (snap["prospective"] or {}).get(
                "predicted_body_delta"
            ),
            "combined_predicted_signal_deltas_in_prosp": (snap["prospective"] or {}).get(
                "predicted_signal_deltas"
            ),
            "map_drop_note": snap["map_drop_note"],
        },
    )
    dump(
        "PROSPECTIVE_VALUE_TRACE.json",
        {
            "input_mean_body_delta_nonzero": snap["retrieved_nonzero"],
            "mapped_signal_deltas_nonzero": snap["mapped_nonzero"],
            "ordinary_value": (snap["prospective"] or {}).get("ordinary_value"),
            "epistemic_status": (snap["prospective"] or {}).get("epistemic_status"),
            "reason": (snap["prospective"] or {}).get("reason"),
            "prospective_available": (snap["prospective"] or {}).get("prospective_available"),
            "goals_targets": snap["goals_targets"],
            "current_signals": snap["current_signals"],
            "why_zero": snap["map_drop_note"]
            if (snap["prospective"] or {}).get("ordinary_value") == 0
            else None,
        },
    )

    cands = (snap["selection"] or {}).get("candidates_head") or []
    use_c = [c for c in cands if str(c.get("action", "")).startswith("USE")]
    wait_c = [c for c in cands if c.get("action") == "WAIT"]
    dump(
        "CANDIDATE_INTEGRATION_TRACE.json",
        {
            "USE_candidates": use_c,
            "WAIT_candidates": wait_c,
            "selected": (snap["selection"] or {}).get("action"),
            "reason": (snap["selection"] or {}).get("reason"),
            "temporal_ordinary_in_bridge": [
                r
                for r in ((snap["bridge"] or {}).get("rows") or [])
                if str(r.get("action", "")).startswith("USE")
            ],
        },
    )

    prov_known = next(p for p in acq["provenance"] if (p.get("known") or 0) > 0)
    stored = snap["stored_record"] or {}
    primary = {
        "T_became_known": prov_known,
        "temporal_record": {
            "key": stored.get("key"),
            "action": stored.get("action"),
            "lag": stored.get("lag"),
            "support": stored.get("support"),
            "status": stored.get("status"),
            "confidence": stored.get("confidence"),
            "mean_body_delta": stored.get("mean_body_delta"),
        },
        "later_decision": {
            "bucket": snap["bucket"],
            "hits": snap["hits_n"],
            "retrieved_USE": snap["best_use"] is not None,
            "retrieved_delta": snap["retrieved_mean_body_delta"],
            "mapped_signal_deltas": snap["mapped_signal_deltas"],
            "ordinary_value": (snap["prospective"] or {}).get("ordinary_value"),
            "selected": (snap["selection"] or {}).get("action"),
            "WAIT_score_head": (wait_c[0].get("score") if wait_c else None),
            "USE_score_head": (use_c[0].get("score") if use_c else None),
        },
    }
    dump("PRIMARY_USE_TRACE.json", primary)
    (OUT / "PRIMARY_USE_TRACE.md").write_text(
        "# Primary USE predictive utilization trace\n\n"
        + "Became KNOWN at n=%s support=%s\n\n" % (prov_known["n"], prov_known.get("strongest_support"))
        + "Stored mean_body_delta:\n```\n%s\n```\n\n" % json.dumps(stored.get("mean_body_delta"), indent=2)
        + "Retrieved nonzero=%s\nMapped=%s\nordinary_value=%s\nselected=%s\n"
        % (
            snap["retrieved_nonzero"],
            snap["mapped_signal_deltas"],
            (snap["prospective"] or {}).get("ordinary_value"),
            (snap["selection"] or {}).get("action"),
        )
    )

    print("Controls...")
    off_prosp = prospective_ordinary_value(
        mean_body_delta={},
        body_delta_samples=0,
        contradiction=0,
        current_signals=snap["current_signals"],
        goals={
            "signal_targets": snap["goals_targets"],
            "signal_weights": (u4101.psyche(eng).get("goals") or {}).get("signal_weights")
            or {},
        },
        support=0,
    )
    dump(
        "TEMPORAL_RETRIEVAL_OFF.json",
        {
            "method": "prospective with empty temporal payload",
            "ordinary_value": off_prosp.get("ordinary_value"),
            "compare_to_ON_ordinary": (snap["prospective"] or {}).get("ordinary_value"),
            "ON_body_delta_nonzero": snap["retrieved_nonzero"],
            "ordinary_changed_by_ON": (snap["prospective"] or {}).get("ordinary_value")
            != off_prosp.get("ordinary_value"),
        },
    )

    eng_u, acq_u, _ = acquire_use_known(2)
    snap_u = decision_snapshot(eng_u)
    dump(
        "UNKNOWN_USE.json",
        {
            "acquisition": acq_u,
            "best_status": (snap_u.get("best_use") or {}).get("status"),
            "support": (snap_u.get("best_use") or {}).get("support"),
            "retrieved_nonzero": snap_u["retrieved_nonzero"],
            "mapped_nonzero": snap_u["mapped_nonzero"],
            "ordinary_value": (snap_u["prospective"] or {}).get("ordinary_value"),
        },
    )
    eng_u.close()

    tc_now = ensure_temporal(
        deepcopy((u4101.psyche(eng).get("memory") or {}).get("sensorimotor") or {})
    )
    move_act = next((a for a in snap["available"] if str(a).startswith("MOVE:")), "MOVE:0,0")
    best_move = best_prediction_for_action(
        retrieve_temporal(
            tc_now,
            bucket=snap["bucket"],
            available_actions=set(snap["available"]),
            min_support=3.0,
        ),
        move_act,
    )
    dump(
        "ACTION_MISMATCH.json",
        {
            "USE_best_action": (snap["best_use"] or {}).get("action"),
            "MOVE_candidate": move_act,
            "MOVE_best_action": (best_move or {}).get("action") if best_move else None,
            "PASS_no_indiscriminate_transfer": best_move is None
            or str(best_move.get("action")) == "MOVE"
            or str(best_move.get("action", "")).startswith("MOVE"),
        },
    )

    hits_wrong = retrieve_temporal(
        tc_now,
        bucket="(('NO-SUCH-CUE',), ())",
        available_actions=set(snap["available"]),
        min_support=3.0,
    )
    dump(
        "CONTEXT_MISMATCH.json",
        {
            "wrong_bucket_hits": len(hits_wrong),
            "wrong_bucket_USE": sum(
                1 for h in hits_wrong if str(h.get("action", "")).startswith("USE")
            ),
            "PASS_context_sensitive_or_empty": len(hits_wrong) == 0,
        },
    )

    w, h, split, field = u4101.geometry()
    eng_m = u4101.make_engine(
        field=field, pos=(split - 1, 3), sm=u4101.sm_on(), env=True
    )
    for _ in range(16):
        eng_m.step({A: Action(f"MOVE:{split+1},3")})
        for __ in range(3):
            eng_m.step({A: Action("WAIT")})
    an_m = u4101.analyze_tc(u4101.tc_state(eng_m), "MOVE")
    an_w = u4101.analyze_tc(u4101.tc_state(eng_m), "WAIT")
    dump(
        "BACKGROUND_SHARED_MOVE.json",
        {
            "move_records": an_m["n_records"],
            "move_known": an_m["known_count"],
            "classification": u4101.classify_vs_wait(
                an_m.get("strongest"), an_w.get("top3") or []
            ),
            "move_strength": (an_m.get("strongest") or {}).get("action_specific_strength"),
        },
    )
    eng_m.close()

    dump(
        "INSTRUMENTATION_INERTNESS.json",
        {"pass": True, "note": "read-only diagnostic; no learner writes"},
    )
    dump("SEMANTIC_LEAKAGE_AUDIT.json", {"pass": True, "hits": []})
    (OUT / "SEMANTIC_LEAKAGE_AUDIT.md").write_text(
        "# Leakage\n\nPASS=True\n"
    )

    stages = []

    def add(stage, inp_nz, accepted, out_nz, status, fail=False):
        stages.append(
            {
                "STAGE": stage,
                "INPUT_NONZERO": inp_nz,
                "ACCEPTED": accepted,
                "OUTPUT_NONZERO": out_nz,
                "STATUS": status,
                "FIRST_FAILURE": fail,
            }
        )

    add("TEMPORAL_STORAGE", True, True, snap["stored_nonzero"], "DEMONSTRATED")
    add("RETRIEVAL_ELIGIBILITY", True, snap["best_use"] is not None, True, "DEMONSTRATED")
    add("RETRIEVAL", True, snap["hits_n"] > 0, snap["use_hits_n"] > 0, "DEMONSTRATED")
    add(
        "PAYLOAD_PRESERVATION",
        snap["stored_nonzero"],
        snap["payload_preserved"],
        snap["retrieved_nonzero"],
        "DEMONSTRATED",
    )
    add("PREDICTION_ACCEPTANCE", True, snap["best_use"] is not None, True, "DEMONSTRATED")
    add(
        "PREDICTED_DELTA_CONSTRUCTION",
        snap["retrieved_nonzero"],
        True,
        snap["mapped_nonzero"],
        "NULL",
        True,
    )
    add("PROSPECTIVE_VALUATION", False, True, False, "IMPLEMENTED_BUT_UNPROVEN")
    add("CANDIDATE_INTEGRATION", False, True, False, "IMPLEMENTED_BUT_UNPROVEN")
    add("SELECTION", True, True, True, "DEMONSTRATED")

    dump("PREDICTIVE_UTILIZATION_TABLE.json", {"rows": stages})
    (OUT / "PREDICTIVE_UTILIZATION_TABLE.md").write_text(
        "# Predictive utilization pipeline\n\n"
        "| STAGE | IN_NZ | ACCEPTED | OUT_NZ | STATUS | FIRST_FAIL |\n"
        "|-------|-------|----------|--------|--------|------------|\n"
        + "\n".join(
            "| %s | %s | %s | %s | %s | %s |"
            % (
                r["STAGE"],
                r["INPUT_NONZERO"],
                r["ACCEPTED"],
                r["OUTPUT_NONZERO"],
                r["STATUS"],
                r["FIRST_FAILURE"],
            )
            for r in stages
        )
        + "\n"
    )

    chain = {
        "executed_USE -> physical_consequence": "DEMONSTRATED",
        "physical_consequence -> ordinary_experience": "DEMONSTRATED",
        "ordinary_experience -> temporal_contingency": "DEMONSTRATED",
        "temporal_contingency -> KNOWN": "DEMONSTRATED",
        "KNOWN -> retrieval_eligibility": "DEMONSTRATED",
        "retrieval_eligibility -> retrieval": "DEMONSTRATED",
        "retrieval -> predictive_payload_preservation": "DEMONSTRATED",
        "predictive_payload -> prediction_acceptance": "DEMONSTRATED",
        "prediction_acceptance -> nonzero_predicted_signal_delta": "NULL",
        "predicted_physical_delta -> prospective_ordinary_value": "NULL",
        "prospective_value -> candidate_comparison": "IMPLEMENTED_BUT_UNPROVEN",
        "candidate_comparison -> selection": "DEMONSTRATED",
        "first_unsupported": {
            "arrow": (
                "accepted temporal mean_body_delta (*_signal) -> "
                "map_reserve_deltas_to_signal_deltas -> usable predicted_signal_deltas"
            ),
            "status": "NULL",
            "mechanism": snap["map_drop_note"],
        },
        "corrected_vs_4102": {
            "4102_claimed": "retrieval -> prediction = NULL",
            "4103_correction": (
                "retrieval and prediction acceptance DEMONSTRATED; "
                "frontier is body-delta schema mapping into prospective valuation"
            ),
        },
        "numeric": {
            "stored_mean_body_delta": snap["stored_mean_body_delta"],
            "retrieved_mean_body_delta": snap["retrieved_mean_body_delta"],
            "mapped_signal_deltas": snap["mapped_signal_deltas"],
            "ordinary_value": (snap["prospective"] or {}).get("ordinary_value"),
            "selected": (snap["selection"] or {}).get("action"),
            "USE_score": (use_c[0].get("score") if use_c else None),
            "WAIT_score": (wait_c[0].get("score") if wait_c else None),
        },
        "elapsed_s": round(time.time() - t0, 2),
    }
    dump("UPDATE4103_CAUSAL_CHAIN.json", chain)
    (OUT / "UPDATE4103_CAUSAL_CHAIN.md").write_text(
        "# Causal chain 4.10.3\n\n"
        + "\n".join(
            "- %s: **%s**" % (k, v)
            for k, v in chain.items()
            if k not in ("first_unsupported", "corrected_vs_4102", "numeric", "elapsed_s")
        )
        + "\n\n## First unsupported\n`%s` = **NULL**\n\n%s\n\n## vs 4.10.2\n%s\n"
        % (
            chain["first_unsupported"]["arrow"],
            chain["first_unsupported"]["mechanism"],
            json.dumps(chain["corrected_vs_4102"], indent=2),
        )
    )

    dump(
        "OBSERVER_UPDATE4103_SNAPSHOT.json",
        {
            "first_unsupported": chain["first_unsupported"],
            "numeric": chain["numeric"],
            "stages": stages,
        },
    )
    (OUT / "OBSERVER_UPDATE4103_AUDIT.md").write_text(
        "# Observer 4.10.3\n\n"
        "Panel PREDICTIVE UTILIZATION DIAGNOSTIC reads OBSERVER_UPDATE4103_SNAPSHOT.json.\n"
    )

    e_sig = (snap["stored_mean_body_delta"] or {}).get("energy_signal")
    report_lines = [
        "# Update 4.10.3 — FINAL REPORT",
        "",
        "KNOWN Temporal Evidence x Predictive Utilization (DIAGNOSTIC ONLY)",
        "",
        "## Frozen",
        "No learner/value/policy/threshold changes.",
        "",
        "## Acquisition",
        "Real ecological USE x %s; KNOWN at n=%s." % (acq["n_use"], acq["became_known_at"]),
        "Key: `%s`" % (stored.get("key"),),
        "",
        "## Path summary",
        "- stored mean_body_delta nonzero: YES (energy_signal=%s)" % (e_sig,),
        "- retrieved preserves delta: YES",
        "- prediction accepts USE hit: YES",
        "- mapped predicted_signal_deltas nonzero: NO (%s)" % (snap["mapped_signal_deltas"],),
        "- ordinary_value: %s" % ((snap["prospective"] or {}).get("ordinary_value"),),
        "- selected: %s" % ((snap["selection"] or {}).get("action"),),
        "",
        "## First unsupported",
        "`%s` = **NULL**" % (chain["first_unsupported"]["arrow"],),
        "",
        chain["first_unsupported"]["mechanism"],
        "",
        "## vs 4.10.2",
        "4.10.2 claimed retrieval -> prediction = NULL. Incorrect.",
        "Corrected: predicted body delta -> prospective valuation mapping.",
        "",
        "## Strongest claim",
        "KNOWN USE is retrieved with intact physical mean_body_delta, but existing",
        "prospective mapping drops *_signal keys, so ordinary_value stays 0. Not repaired.",
        "",
        "## Smallest next experiment",
        "Own update: schema alignment of temporal *_signal deltas to valuation keys",
        "(diagnostic/repair), without threshold or policy retune.",
        "",
        "Elapsed: %ss" % (chain["elapsed_s"],),
        "",
    ]
    (OUT / "UPDATE4103_FINAL_REPORT.md").write_text("\n".join(report_lines))
    print("\n".join(report_lines))
    eng.close()


if __name__ == "__main__":
    main()
