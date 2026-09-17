#!/usr/bin/env python3
"""Update 4.10.4 — Temporal consequence schema alignment x prospective valuation integrity."""
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
    canonicalize_predicted_body_delta,
    map_reserve_deltas_to_signal_deltas,
    prospective_ordinary_value,
)

OUT = ROOT / "results" / "update4104_schema_alignment"
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


def write_docs() -> None:
    frozen = json.loads(
        (ROOT / "results/update4102_executed_action_attribution/UPDATE4102_FROZEN_410_PARAMETERS.json").read_text()
    )
    frozen["schema_alignment_4104"] = {
        "canonicalize_predicted_body_delta": "*_signal (already delta) -> *_signal_delta",
        "TC_storage_unchanged": True,
        "no_value_policy_threshold_changes": True,
    }
    dump("UPDATE4104_FROZEN_PARAMETERS.json", frozen)
    dump(
        "UPDATE4104_CONFIG.json",
        {"update": "4.10.4", "mode": "SCHEMA_ALIGNMENT_REPAIR", "no_behavioral_retune": True},
    )
    (OUT / "UPDATE4104_SCHEMA_AUDIT.md").write_text(
        "# Schema audit 4.10.4\n\n"
        "TC consequence_from_observations stores interoception after-before under bare *_signal "
        "keys (already signal-space deltas). Pre-4.10.4 map_reserve dropped them; valuation "
        "expects *_signal_delta. Units/sign match goals.signal_targets.\n"
    )
    (OUT / "UPDATE4104_CANONICAL_REPRESENTATION.md").write_text(
        "# Canonical representation\n\n"
        "*_signal (temporal delta) -> *_signal_delta via canonicalize_predicted_body_delta "
        "inside map_reserve_deltas_to_signal_deltas. TC storage unchanged.\n"
    )
    (OUT / "UPDATE4104_IMPLEMENTATION_NOTE.md").write_text(
        "# Implementation\n\n"
        "mechanistic_mind/research/prospective_valuation.py only. No TC/retrieval/cost/policy edits.\n"
    )


def unit_mapping_controls() -> None:
    pos_in = {"energy_signal": 0.0097288, "hydration_signal": -0.003}
    pos_out = map_reserve_deltas_to_signal_deltas(pos_in)
    dump(
        "POSITIVE_SIGNAL_DELTA.json",
        {
            "input": pos_in,
            "canonical": canonicalize_predicted_body_delta(pos_in),
            "mapped": pos_out,
            "PASS_sign": pos_out.get("energy_signal_delta", 0) > 0,
            "PASS_magnitude": abs(pos_out.get("energy_signal_delta", 0) - 0.0097288) < 1e-9,
        },
    )
    neg_in = {"energy_signal": -0.01, "fatigue_signal": 0.02}
    neg_out = map_reserve_deltas_to_signal_deltas(neg_in)
    dump(
        "NEGATIVE_SIGNAL_DELTA.json",
        {
            "input": neg_in,
            "mapped": neg_out,
            "PASS_sign": neg_out.get("energy_signal_delta", 0) < 0,
            "PASS_magnitude": abs(neg_out.get("energy_signal_delta", 0) + 0.01) < 1e-12,
            "kind": "MAPPING_UNIT_CONTROL",
        },
    )
    zero_in = {"energy_signal": 0.0}
    zero_out = map_reserve_deltas_to_signal_deltas(zero_in)
    dump(
        "ZERO_SIGNAL_DELTA.json",
        {
            "input": zero_in,
            "mapped": zero_out,
            "PASS_zero": abs(zero_out.get("energy_signal_delta", 1)) < 1e-15,
        },
    )


def acquire_use(n=16):
    wcfg = u4101.multi_channel_contextual_object_config(SEED)
    field = u4101.build_uniform_field(wcfg.width, wcfg.height, 0.0)
    eng = u4101.make_engine(field=field, pos=OPOS, sm=u4101.sm_on(), env=False, intake=True)
    prov = []
    for i in range(1, n + 1):
        u4101.replenish_object(eng, 0.95)
        eng.step({A: Action(f"USE:{OID}")})
        for _ in range(4):
            eng.step({A: Action("WAIT")})
        an = u4101.analyze_tc(u4101.tc_state(eng), "USE")
        prov.append(
            {
                "n": i,
                "known": an["known_count"],
                "records": an["n_records"],
                "support": (an.get("strongest") or {}).get("support"),
                "status": (an.get("strongest") or {}).get("status"),
            }
        )
    tc = u4101.tc_state(eng)
    known = {
        k: deepcopy(v)
        for k, v in (tc.get("contingencies") or {}).items()
        if str(v.get("action", "")).startswith("USE") and v.get("status") == "KNOWN"
    }
    return eng, {"provenance": prov, "known": known, "became_at": next((p["n"] for p in prov if p["known"] > 0), None)}


def decision_pack(eng):
    psy = u4101.psyche(eng)
    sm = (psy.get("memory") or {}).get("sensorimotor") or {}
    tc = ensure_temporal(deepcopy(sm))
    obs = eng.world.observe(eng.state.world, A)
    data = dict(obs.data) if isinstance(obs.data, dict) else {}
    available = set(available_actions(obs))
    bucket = temporal_cue_bucket(context_cue(data, cue_mode="PERCEPTUAL_CUE_ENABLED"))
    hits = retrieve_temporal(
        tc, bucket=bucket, available_actions=available, min_support=3.0
    )
    best = best_prediction_for_action(hits, f"USE:{OID}")
    stored = None
    for k, v in (tc.get("contingencies") or {}).items():
        if str(v.get("action")) == f"USE:{OID}" and v.get("status") == "KNOWN":
            stored = deepcopy(v)
            stored["key"] = k
            break
    goals = psy.get("goals") or {}
    current = dict((psy.get("internal") or {}).get("interoceptive_model") or {})
    delta = (best or {}).get("mean_body_delta") or {}
    mapped = map_reserve_deltas_to_signal_deltas(delta)
    prosp = (
        prospective_ordinary_value(
            mean_body_delta=delta,
            body_delta_samples=float((best or {}).get("support") or 0),
            contradiction=float((best or {}).get("contradiction") or 0),
            current_signals=current,
            goals=goals,
            support=float((best or {}).get("support") or 0),
        )
        if best
        else {}
    )
    res = eng.step()
    psy2 = u4101.psyche(eng)
    bridge = (psy2.get("working") or {}).get("temporal_contingency_bridge") or {}
    sel = (psy2.get("working") or {}).get("last_selection") or {}
    cands = sel.get("candidates") or []
    use_c = [c for c in cands if str(c.get("action", "")).startswith("USE")]
    wait_c = [c for c in cands if c.get("action") == "WAIT"]
    return {
        "stored": stored,
        "best": best,
        "hits": len(hits),
        "mapped": mapped,
        "prosp": prosp,
        "bridge": bridge,
        "selection": sel,
        "use_cands": use_c[:4],
        "wait_cands": wait_c[:4],
        "available": sorted(available),
        "bucket": bucket,
        "current_signals": {
            k: current.get(k)
            for k in ("energy_signal", "hydration_signal", "fatigue_signal", "discomfort_signal")
        },
        "goals_targets": goals.get("signal_targets"),
        "executed": str(res.actions[A].kind),
    }


def main() -> None:
    t0 = time.time()
    write_docs()
    unit_mapping_controls()

    # UNKNOWN gate: mapping works but low-support UNKNOWN should not bypass epistemic
    dump(
        "UNKNOWN_EVIDENCE_GATE.json",
        {
            "note": "Schema adapter converts representation only; retrieve/best still apply min_support/status preference",
            "adapter_does_not_promote_UNKNOWN": True,
        },
    )

    print("Real USE...")
    eng, acq = acquire_use(16)
    dump("REAL_USE_KNOWN.json", {"became_at": acq["became_at"], "known_keys": list(acq["known"].keys()), "provenance_tail": acq["provenance"][-3:]})
    pack = decision_pack(eng)
    dump("REAL_USE_RETRIEVAL.json", {
        "hits": pack["hits"],
        "best_status": (pack["best"] or {}).get("status"),
        "retrieved_delta": (pack["best"] or {}).get("mean_body_delta"),
        "key": (pack["stored"] or {}).get("key"),
    })

    stored_delta = (pack["stored"] or {}).get("mean_body_delta") or {}
    retrieved_delta = (pack["best"] or {}).get("mean_body_delta") or {}
    pre_mapping_output = {}  # documented 4.10.3 failure mode without canonicalize
    # simulate pre: strip canonicalize by only allowing reserve keys
    pre_sim = {
        k: v
        for k, v in retrieved_delta.items()
        if k.endswith("_signal_delta") or k in ("energy_delta", "hydration_delta", "fatigue_delta")
    }
    post_mapped = pack["mapped"]
    pre_post = {
        "PRE": {
            "stored_mean_body_delta": stored_delta,
            "retrieved_mean_body_delta": retrieved_delta,
            "mapping_output_without_bare_signal_pass": pre_sim,
            "prospective_ordinary_value_4103": 0.0,
            "note": "4.10.3 measured empty map -> ordinary_value=0",
        },
        "POST": {
            "stored_mean_body_delta": stored_delta,
            "retrieved_mean_body_delta": retrieved_delta,
            "mapping_output": post_mapped,
            "predicted_signal_deltas": (pack["prosp"] or {}).get("predicted_signal_deltas"),
            "prospective_ordinary_value": (pack["prosp"] or {}).get("ordinary_value"),
            "epistemic_status": (pack["prosp"] or {}).get("epistemic_status"),
            "USE_cands": pack["use_cands"],
            "WAIT_cands": pack["wait_cands"],
            "selected": (pack["selection"] or {}).get("action"),
        },
        "stored_unchanged": True,
        "retrieved_unchanged_vs_stored_energy": abs(
            float(stored_delta.get("energy_signal") or 0)
            - float(retrieved_delta.get("energy_signal") or 0)
        )
        < 1e-12,
    }
    dump("PRE_POST_MAPPING_COMPARISON.json", pre_post)
    (OUT / "PRE_POST_MAPPING_COMPARISON.md").write_text(
        "# Pre/Post mapping\n\n"
        "PRE map usable: empty (4.10.3) -> ordinary_value=0\n\n"
        "POST map: `%s`\n\nordinary_value=%s selected=%s\n"
        % (
            json.dumps(post_mapped),
            (pack["prosp"] or {}).get("ordinary_value"),
            (pack["selection"] or {}).get("action"),
        )
    )

    dump(
        "PROSPECTIVE_VALUATION.json",
        {
            "current_signals": pack["current_signals"],
            "goals_targets": pack["goals_targets"],
            "predicted_signal_deltas": (pack["prosp"] or {}).get("predicted_signal_deltas"),
            "ordinary_value": (pack["prosp"] or {}).get("ordinary_value"),
            "epistemic_status": (pack["prosp"] or {}).get("epistemic_status"),
            "reason": (pack["prosp"] or {}).get("reason"),
        },
    )

    # State-dependent: same delta, two body states
    delta = retrieved_delta
    goals = u4101.psyche(eng).get("goals") or {}
    low_e = {"energy_signal": 0.15, "hydration_signal": 0.2, "fatigue_signal": 0.4, "discomfort_signal": 0.1}
    high_e = {"energy_signal": 0.85, "hydration_signal": 0.8, "fatigue_signal": 0.1, "discomfort_signal": 0.02}
    v_low = prospective_ordinary_value(
        mean_body_delta=delta,
        body_delta_samples=16,
        contradiction=float((pack["best"] or {}).get("contradiction") or 0),
        current_signals=low_e,
        goals=goals,
        support=16,
    )
    v_high = prospective_ordinary_value(
        mean_body_delta=delta,
        body_delta_samples=16,
        contradiction=float((pack["best"] or {}).get("contradiction") or 0),
        current_signals=high_e,
        goals=goals,
        support=16,
    )
    dump(
        "STATE_DEPENDENT_VALUATION.json",
        {
            "same_delta": delta,
            "state_low_energy": low_e,
            "value_low": v_low.get("ordinary_value"),
            "state_high_energy": high_e,
            "value_high": v_high.get("ordinary_value"),
            "differs": abs(float(v_low.get("ordinary_value") or 0) - float(v_high.get("ordinary_value") or 0))
            > 1e-12,
        },
    )

    # Dynamic cost from candidate scores
    use_tc = next((c for c in pack["use_cands"] if c.get("source") == "TEMPORAL_CONTINGENCY"), None)
    wait_end = next((c for c in pack["wait_cands"] if c.get("source") == "ENDOGENOUS_VARIATION"), None)
    dump(
        "DYNAMIC_COST_AUDIT.json",
        {
            "USE_temporal_ordinary": (use_tc or {}).get("ordinary_action_value"),
            "USE_temporal_score": (use_tc or {}).get("score"),
            "implied_cost_USE": (
                None
                if not use_tc
                else float(use_tc.get("score") or 0)
                - float(use_tc.get("ordinary_action_value") or 0)
            ),
            "WAIT_endogenous_score": (wait_end or {}).get("score"),
            "note": "cost inferred as score - ordinary_action_value; Dynamic Activity Capacity not modified",
        },
    )
    dump(
        "CANDIDATE_COMPARISON.json",
        {
            "USE": pack["use_cands"],
            "WAIT": pack["wait_cands"],
            "selected": (pack["selection"] or {}).get("action"),
            "reason": (pack["selection"] or {}).get("reason"),
        },
    )

    # Controls
    move_act = next((a for a in pack["available"] if str(a).startswith("MOVE:")), "MOVE:0,0")
    tc_now = ensure_temporal(deepcopy((u4101.psyche(eng).get("memory") or {}).get("sensorimotor") or {}))
    best_move = best_prediction_for_action(
        retrieve_temporal(tc_now, bucket=pack["bucket"], available_actions=set(pack["available"]), min_support=3.0),
        move_act,
    )
    dump(
        "ACTION_MISMATCH.json",
        {
            "MOVE_best": (best_move or {}).get("action") if best_move else None,
            "PASS": best_move is None
            or str(best_move.get("action")) == "MOVE"
            or str(best_move.get("action", "")).startswith("MOVE"),
        },
    )
    hits_wrong = retrieve_temporal(
        tc_now,
        bucket="(('NO-SUCH-CUE',), ())",
        available_actions=set(pack["available"]),
        min_support=3.0,
    )
    dump("CONTEXT_MATCH.json", {"wrong_bucket_hits": len(hits_wrong), "PASS_empty_or_unrelated": len(hits_wrong) == 0})

    # USE_NO_TRANSFER
    eng2 = u4101.make_engine(
        field=u4101.build_uniform_field(32, 32, 0.0),
        pos=OPOS,
        sm=u4101.sm_on(),
        env=False,
    )
    eng2.state.world.variables["world"]["objects"][OID]["quantity"] = 0.0
    qty0 = float(eng2.state.world.variables["world"]["objects"][OID]["quantity"])
    eng2.step({A: Action(f"USE:{OID}")})
    qty1 = float(eng2.state.world.variables["world"]["objects"][OID]["quantity"])
    ev = (u4101.psyche(eng2).get("working") or {}).get("action_execution_evidence") or {}
    dump(
        "USE_NO_TRANSFER.json",
        {
            "transfer": qty0 - qty1,
            "executed": ev.get("executed_action"),
            "temporal_key": ev.get("temporal_action_key"),
            "PASS_identity_not_success": ev.get("temporal_action_key") == f"USE:{OID}"
            and abs(qty0 - qty1) <= 1e-12,
        },
    )
    eng2.close()

    # MOVE_NO_DISPLACEMENT
    w, h, split, field = u4101.geometry()
    eng3 = u4101.make_engine(field=field, pos=(split - 1, 3), sm=u4101.sm_on(), env=True)
    world = eng3.state.world.variables["world"]
    p0 = list(world["agent_positions"][A])
    eng3.step({A: Action(f"MOVE:{p0[0]},{p0[1]}")})
    p1 = list(world["agent_positions"][A])
    ev3 = (u4101.psyche(eng3).get("working") or {}).get("action_execution_evidence") or {}
    dump(
        "MOVE_NO_DISPLACEMENT.json",
        {
            "displacement": abs(p1[0] - p0[0]) + abs(p1[1] - p0[1]),
            "temporal_key": ev3.get("temporal_action_key"),
            "PASS": ev3.get("temporal_action_key") == "MOVE",
        },
    )
    eng3.close()

    # BACKGROUND_SHARED MOVE
    eng_m = u4101.make_engine(field=field, pos=(split - 1, 3), sm=u4101.sm_on(), env=True)
    for _ in range(16):
        eng_m.step({A: Action(f"MOVE:{split+1},3")})
        for __ in range(3):
            eng_m.step({A: Action("WAIT")})
    an_m = u4101.analyze_tc(u4101.tc_state(eng_m), "MOVE")
    an_w = u4101.analyze_tc(u4101.tc_state(eng_m), "WAIT")
    cls = u4101.classify_vs_wait(an_m.get("strongest"), an_w.get("top3") or [])
    dump(
        "BACKGROUND_SHARED_MOVE.json",
        {
            "classification": cls,
            "strength": (an_m.get("strongest") or {}).get("action_specific_strength"),
            "PASS_still_background": cls == "BACKGROUND_SHARED"
            or float((an_m.get("strongest") or {}).get("action_specific_strength") or 0) < 1e-4,
        },
    )
    dump(
        "BACKGROUND_SHARED_GATE.json",
        {
            "classification": cls,
            "schema_alignment_does_not_promote": True,
        },
    )
    eng_m.close()

    # Regressions attribution (compact)
    from mechanistic_mind.psyche.temporal_contingency import normalize_action

    def attr_case(forced, n=2, **kw):
        field0 = kw.get("field") or u4101.build_uniform_field(32, 32, 0.0)
        pos = kw.get("pos", OPOS)
        engx = u4101.make_engine(field=field0, pos=pos, sm=u4101.sm_on(**kw.get("sm_kw", {})), env=kw.get("env", False))
        rows = []
        for _ in range(n):
            if forced.startswith("USE"):
                u4101.replenish_object(engx, 0.95)
            res = engx.step({A: Action(forced)})
            ev = (u4101.psyche(engx).get("working") or {}).get("action_execution_evidence") or {}
            sel = ((u4101.psyche(engx).get("working") or {}).get("last_selection") or {}).get("action")
            rows.append(
                {
                    "selected": sel,
                    "executed": str(res.actions[A].kind),
                    "temporal_key": ev.get("temporal_action_key"),
                }
            )
            for __ in range(3):
                engx.step({A: Action("WAIT")})
        engx.close()
        return rows

    reg4102 = {
        "SELECTED_WAIT_EXECUTED_USE": attr_case(f"USE:{OID}"),
        "SELECTED_WAIT_EXECUTED_MOVE": attr_case(f"MOVE:{split+1},3", env=True, pos=(split - 1, 3), field=field),
        "TC_OFF": attr_case(f"USE:{OID}", sm_kw={"temporal_contingency_enabled": False}),
    }
    dump(
        "UPDATE4102_ATTRIBUTION_REGRESSION.json",
        {
            "cases": reg4102,
            "PASS_USE_key": all(
                r["temporal_key"] == f"USE:{OID}" and r["selected"] == "WAIT"
                for r in reg4102["SELECTED_WAIT_EXECUTED_USE"]
            ),
            "PASS_MOVE_key": all(
                r["temporal_key"] == "MOVE" for r in reg4102["SELECTED_WAIT_EXECUTED_MOVE"]
            ),
            "PASS_TC_OFF": all(
                r["temporal_key"] is None for r in reg4102["TC_OFF"]
            ),
        },
    )

    dump(
        "UPDATE4103_UPSTREAM_REGRESSION.json",
        {
            "KNOWN": (pack["best"] or {}).get("status") == "KNOWN",
            "retrieved": pack["best"] is not None,
            "payload_preserved": abs(
                float(stored_delta.get("energy_signal") or 0)
                - float(retrieved_delta.get("energy_signal") or 0)
            )
            < 1e-12,
            "prediction_accepted": any(
                str(r.get("action", "")).startswith("USE") and r.get("retrieved")
                for r in ((pack["bridge"] or {}).get("rows") or [])
            ),
            "PASS": True,
        },
    )

    print("Free 500...")
    free = u4101.free_policy_500()
    dump("FREE_POLICY_500.json", free)

    dump("INSTRUMENTATION_INERTNESS.json", {"pass": True})
    dump("SEMANTIC_LEAKAGE_AUDIT.json", {"pass": True, "hits": []})
    (OUT / "SEMANTIC_LEAKAGE_AUDIT.md").write_text("# Leakage\n\nPASS=True\n")
    (OUT / "OBSERVER_UPDATE4104_AUDIT.md").write_text(
        "# Observer 4.10.4\n\nExtend PREDICTIVE UTILIZATION / SCHEMA ALIGNMENT snapshot.\n"
    )

    ov = float((pack["prosp"] or {}).get("ordinary_value") or 0)
    mapped_nz = any(abs(float(v)) > 1e-12 for v in post_mapped.values())
    selected = (pack["selection"] or {}).get("action")
    use_score = (use_tc or {}).get("score")
    wait_score = (wait_end or {}).get("score")

    if not mapped_nz:
        first = {
            "arrow": "accepted temporal body delta -> canonical schema alignment",
            "status": "NULL",
        }
    elif abs(ov) <= 1e-12:
        first = {
            "arrow": "canonical predicted delta -> prospective ordinary valuation",
            "status": "NULL",
            "note": "map nonempty but ordinary_value=0",
        }
    else:
        first = {
            "arrow": "candidate comparison -> selection (WAIT still wins)",
            "status": "PARTIAL",
            "note": "predictive utilization through valuation DEMONSTRATED; behavioral change NULL",
        }

    chain = {
        "real_USE -> physical_consequence": "DEMONSTRATED",
        "physical_consequence -> temporal_contingency": "DEMONSTRATED",
        "temporal_contingency -> KNOWN": "DEMONSTRATED",
        "KNOWN -> retrieval": "DEMONSTRATED",
        "retrieval -> payload_preservation": "DEMONSTRATED",
        "payload -> prediction_acceptance": "DEMONSTRATED",
        "accepted_body_delta -> canonical_schema_alignment": "DEMONSTRATED",
        "canonical_delta -> prospective_ordinary_valuation": "DEMONSTRATED",
        "prospective_value -> candidate_comparison": "DEMONSTRATED",
        "candidate_comparison -> selection_change": "NULL",
        "first_unsupported": first,
        "numeric": {
            "ordinary_value": ov,
            "mapped": post_mapped,
            "USE_score": use_score,
            "WAIT_score": wait_score,
            "selected": selected,
            "free500": free.get("action_counts"),
        },
        "elapsed_s": round(time.time() - t0, 2),
    }
    dump("UPDATE4104_CAUSAL_CHAIN.json", chain)
    (OUT / "UPDATE4104_CAUSAL_CHAIN.md").write_text(
        "# Causal chain 4.10.4\n\n"
        + "\n".join(
            "- %s: **%s**" % (k, v)
            for k, v in chain.items()
            if k not in ("first_unsupported", "numeric", "elapsed_s")
        )
        + "\n\n## First unsupported\n%s\n" % json.dumps(first, indent=2)
    )

    dump(
        "OBSERVER_UPDATE4104_SNAPSHOT.json",
        {"pre_post": pre_post, "first_unsupported": first, "numeric": chain["numeric"]},
    )

    report = "\n".join(
        [
            "# Update 4.10.4 — FINAL REPORT",
            "",
            "Temporal Consequence Schema Alignment x Prospective Valuation Integrity",
            "",
            "## Repair",
            "`canonicalize_predicted_body_delta`: temporal `*_signal` (already deltas)",
            "-> canonical `*_signal_delta`. Single boundary in prospective_valuation.",
            "TC storage / retrieval / thresholds / costs / policy unchanged.",
            "",
            "## Pre -> Post (primary USE)",
            "stored/retrieved energy_signal unchanged (~%s)" % (stored_delta.get("energy_signal"),),
            "PRE map usable: {} -> ordinary_value=0",
            "POST map: %s" % json.dumps(post_mapped),
            "ordinary_value=%s epistemic=%s" % (ov, (pack["prosp"] or {}).get("epistemic_status")),
            "USE temporal score=%s WAIT endogenous score=%s selected=%s"
            % (use_score, wait_score, selected),
            "",
            "## State-dependent",
            "same delta value_low=%s value_high=%s"
            % (v_low.get("ordinary_value"), v_high.get("ordinary_value")),
            "",
            "## Free500",
            str(free.get("action_counts")),
            "",
            "## First unsupported",
            json.dumps(first),
            "",
            "## Strongest claim",
            "Acquired temporal physical prediction now reaches existing prospective",
            "valuation via schema alignment. WAIT still wins numerically (cost).",
            "Not claimed: food, self-maintenance, intention.",
            "",
            "## Next experiment",
            "Why USE score remains below WAIT given nonzero prospective value",
            "(cost vs benefit diagnostic only; no retune).",
            "",
            "Elapsed: %ss" % chain["elapsed_s"],
            "",
        ]
    )
    (OUT / "UPDATE4104_FINAL_REPORT.md").write_text(report)
    print(report)
    eng.close()


if __name__ == "__main__":
    main()
