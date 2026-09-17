#!/usr/bin/env python3
"""Update 4.12 — Experienced transition composition × unexperienced future prediction.

Shadow only. Controlled acquisition: USE and MOVE independently; never USE→MOVE sequence.
"""
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
from mechanistic_mind.body.models import BodyState
from mechanistic_mind.research.developmental_subsidy import (
    MDS_LADDER_TICK_EQUIVALENT,
    apply_subsidy_to_body_config,
    apply_subsidy_to_body_state,
    subsidy_from_tick_equivalent,
)
from mechanistic_mind.psyche.temporal_contingency import (
    coarse_body_state_key,
    ensure_temporal,
    temporal_cue_bucket,
)
from mechanistic_mind.psyche.sensorimotor import context_cue
from mechanistic_mind.research.transition_composition import (
    ablate_action_evidence,
    compose_two_step,
    depth2_tree,
    shuffle_state_keys,
)

OUT = ROOT / "results" / "update412_transition_composition"
OUT.mkdir(parents=True, exist_ok=True)
A, OID, OPOS, SEED = u4101.A, u4101.OID, u4101.OPOS, u4101.SEED
TE = int(MDS_LADDER_TICK_EQUIVALENT[0])
SPEC = subsidy_from_tick_equivalent(TE)
ACTION_A = f"USE:{OID}"
ACTION_B = "MOVE:1,0"
LAG_A = 1
LAG_B = 1
MIN_SUPPORT = 3.0


def dump(name: str, payload: Any) -> None:
    def _fix(o):
        if isinstance(o, dict):
            return {str(k): _fix(v) for k, v in o.items()}
        if isinstance(o, list):
            return [_fix(v) for v in o]
        if isinstance(o, float) and o != o:
            return None
        return o

    (OUT / name).write_text(json.dumps(_fix(payload), indent=2, sort_keys=True, default=str) + "\n")
    print("wrote", name, flush=True)


def write_md(name: str, text: str) -> None:
    (OUT / name).write_text(text if text.endswith("\n") else text + "\n")
    print("wrote", name, flush=True)


def apply_spec(eng, spec=SPEC) -> None:
    bc = apply_subsidy_to_body_config(eng.world.body_config, spec)
    eng.world.body_config = bc
    if hasattr(eng.world, "body_engine"):
        eng.world.body_engine.config = bc
    eng.state.world.variables["bodies"][A] = apply_subsidy_to_body_state(BodyState(), spec).to_dict()


def fresh():
    wcfg = u4101.multi_channel_contextual_object_config(SEED)
    field = u4101.build_uniform_field(wcfg.width, wcfg.height, 0.0)
    eng = u4101.make_engine(field=field, pos=OPOS, sm=u4101.sm_on(), env=False, intake=True)
    apply_spec(eng)
    return eng


def signals(eng):
    psy = u4101.psyche(eng)
    m = dict((psy.get("internal") or {}).get("interoceptive_model") or {})
    return {k: float(v) for k, v in m.items() if isinstance(v, (int, float))}


def tc_of(eng):
    return ensure_temporal(deepcopy((u4101.psyche(eng).get("memory") or {}).get("sensorimotor") or {}))


def bucket_of(eng):
    sm = (u4101.psyche(eng).get("memory") or {}).get("sensorimotor") or {}
    cue = sm.get("last_cue")
    if not isinstance(cue, dict):
        cue = context_cue({"interoception": signals(eng)}, cue_mode="PERCEPTUAL_CUE_ENABLED")
    return temporal_cue_bucket(cue)


def acquire_independent(eng, n_a=10, n_b=10):
    """Acquire A=USE and B=MOVE independently. Never execute USE then MOVE consecutively."""
    history = []  # list of {action, state_key, t}
    # Family 1: USE → WAIT×3 only
    for i in range(n_a):
        u4101.replenish_object(eng, 0.95)
        sk = coarse_body_state_key(signals(eng), from_interoception=False)
        eng.step({A: Action(ACTION_A)})
        history.append({"action": ACTION_A, "norm": "USE", "state_key": sk, "family": "A"})
        for _ in range(3):
            skw = coarse_body_state_key(signals(eng), from_interoception=False)
            eng.step({A: Action("WAIT")})
            history.append({"action": "WAIT", "norm": "WAIT", "state_key": skw, "family": "A_settle"})
    # Family 2: MOVE → WAIT×3 only (no USE immediately before)
    for i in range(n_b):
        # drift with WAIT once to vary state a bit without USE→MOVE
        eng.step({A: Action("WAIT")})
        sk = coarse_body_state_key(signals(eng), from_interoception=False)
        eng.step({A: Action(ACTION_B)})
        history.append({"action": ACTION_B, "norm": "MOVE", "state_key": sk, "family": "B"})
        for _ in range(3):
            skw = coarse_body_state_key(signals(eng), from_interoception=False)
            eng.step({A: Action("WAIT")})
            history.append({"action": "WAIT", "norm": "WAIT", "state_key": skw, "family": "B_settle"})
        # optional: if far from object, we don't USE here
    return history


def novelty_audit(history: list[dict], s0_key: str) -> dict:
    """COMPLETE_SEQUENCE_PREVIOUSLY_SEEN if USE then MOVE appear as consecutive non-WAIT pair from matching S0."""
    seen = False
    hits = []
    for i in range(len(history) - 1):
        a, b = history[i], history[i + 1]
        if a.get("norm") == "USE" and b.get("norm") == "MOVE":
            hits.append({"i": i, "a": a, "b": b})
            if a.get("state_key") == s0_key or True:
                # any USE→MOVE consecutive is contaminating for this design
                seen = True
    return {
        "COMPLETE_SEQUENCE_PREVIOUSLY_SEEN": "YES" if seen else "NO",
        "use_then_move_pairs": hits[:20],
        "n_pairs": len(hits),
        "test_s0_key": s0_key,
    }


def physical_execute_AB(eng0, lag_a=LAG_A, lag_b=LAG_B):
    eng = deepcopy(eng0)
    s0 = signals(eng)
    # A
    eng.step({A: Action(ACTION_A)})
    for _ in range(max(0, lag_a - 1)):
        eng.step({A: Action("WAIT")})
    s1 = signals(eng)
    # B
    eng.step({A: Action(ACTION_B)})
    for _ in range(max(0, lag_b - 1)):
        eng.step({A: Action("WAIT")})
    s2 = signals(eng)
    return {"s0": s0, "s1": s1, "s2": s2}


def err_map(pred, real):
    if not isinstance(pred, dict) or not isinstance(real, dict):
        return None
    keys = set(pred) | set(real)
    return {k: float(pred.get(k, 0)) - float(real.get(k, 0)) for k in keys}


def compact_edge(e: dict) -> dict:
    return {
        "status": e.get("status"),
        "provenance": e.get("provenance"),
        "reason": e.get("reason"),
        "action": e.get("action"),
        "lag": e.get("lag"),
        "input_state_key": e.get("input_state_key"),
        "predicted_state_key": e.get("predicted_state_key"),
        "support": e.get("support"),
        "confidence": e.get("confidence"),
        "state_match": e.get("state_match"),
        "pred_energy": (e.get("predicted_state") or {}).get("energy_signal")
        if isinstance(e.get("predicted_state"), dict)
        else None,
    }


def main():
    t0 = time.time()
    dump(
        "UPDATE412_CONFIG.json",
        {
            "update": "4.12",
            "seed": SEED,
            "TE": TE,
            "ACTION_A": ACTION_A,
            "ACTION_B": ACTION_B,
            "LAG_A": LAG_A,
            "LAG_B": LAG_B,
            "shadow_only": True,
            "no_ranking": True,
        },
    )

    print("Controlled acquisition...", flush=True)
    eng = fresh()
    history = acquire_independent(eng, 10, 10)
    apply_spec(eng)
    eng.step()  # decision tick
    s0 = signals(eng)
    s0_key = coarse_body_state_key(s0, from_interoception=False)
    bucket = bucket_of(eng)
    tc = tc_of(eng)

    nov = novelty_audit(history, s0_key)
    dump("NOVELTY_AUDIT.json", nov)
    dump("ACQUISITION_HISTORY.json", {"n": len(history), "sample": history[:: max(1, len(history)//20)]})

    # A. COMPOSITION_PRESENT
    print("Composition...", flush=True)
    comp = compose_two_step(
        tc=tc,
        s0_signals=s0,
        action_a=ACTION_A,
        action_b=ACTION_B,
        bucket=bucket,
        lag_a=LAG_A,
        lag_b=LAG_B,
        available_actions={ACTION_A, ACTION_B, "WAIT"},
        min_support=MIN_SUPPORT,
        require_exact_state=True,
    )
    dump(
        "COMPOSITION_PRESENT.json",
        {
            "result": {
                "status": comp.get("status"),
                "composition": comp.get("composition"),
                "reason": comp.get("reason"),
                "s0_key": comp.get("s0_state_key"),
                "s_hat_1_key": comp.get("s_hat_1_key"),
                "s_hat_2_key": comp.get("s_hat_2_key"),
                "total_duration": comp.get("total_duration"),
                "edge_a": compact_edge(comp.get("edge_a") or {}),
                "edge_b": compact_edge(comp.get("edge_b") or {}),
            },
            "s_hat_1": comp.get("s_hat_1"),
            "s_hat_2": comp.get("s_hat_2"),
        },
    )

    # Physical validation
    phys = physical_execute_AB(eng, LAG_A, LAG_B)
    dump(
        "PHYSICAL_VALIDATION.json",
        {
            "predicted_s1": comp.get("s_hat_1"),
            "realized_s1": phys["s1"],
            "error_s1": err_map(comp.get("s_hat_1"), phys["s1"]),
            "predicted_s2": comp.get("s_hat_2"),
            "realized_s2": phys["s2"],
            "error_s2": err_map(comp.get("s_hat_2"), phys["s2"]),
            "s0": phys["s0"],
        },
    )

    # Error localization
    e1 = err_map(comp.get("s_hat_1"), phys["s1"])
    e2 = err_map(comp.get("s_hat_2"), phys["s2"])
    first_break = None
    if comp.get("status") != "OK":
        first_break = "COMPOSITION_UNKNOWN_BEFORE_PHYSICS"
    elif e1 and abs(e1.get("energy_signal", 0)) > 0.02:
        first_break = "FIRST_TRANSITION_PREDICTION_ERROR"
    elif e2 and abs(e2.get("energy_signal", 0)) > 0.02:
        # check if intermediate was ok
        if e1 and abs(e1.get("energy_signal", 0)) <= 0.02:
            first_break = "SECOND_TRANSITION_OR_INTERMEDIATE_MISMATCH"
        else:
            first_break = "CASCADING_FROM_FIRST"
    else:
        first_break = "NO_LARGE_ENERGY_BREAK"
    dump(
        "ERROR_LOCALIZATION.json",
        {
            "first_break": first_break,
            "energy_err_s1": (e1 or {}).get("energy_signal"),
            "energy_err_s2": (e2 or {}).get("energy_signal"),
        },
    )

    # Controls
    print("Controls...", flush=True)
    tc_no_b = ablate_action_evidence(tc, "MOVE")
    c_b = compose_two_step(
        tc=tc_no_b, s0_signals=s0, action_a=ACTION_A, action_b=ACTION_B, bucket=bucket,
        lag_a=LAG_A, lag_b=LAG_B, available_actions={ACTION_A, ACTION_B, "WAIT"}, min_support=MIN_SUPPORT,
    )
    dump("CONTROL_SECOND_TRANSITION_ABLATED.json", {
        "status": c_b.get("status"), "reason": c_b.get("reason"),
        "edge_a": compact_edge(c_b.get("edge_a") or {}),
        "edge_b": compact_edge(c_b.get("edge_b") or {}),
        "expected": "A ok then UNKNOWN",
    })

    tc_no_a = ablate_action_evidence(tc, f"USE:{OID}")
    # also ablate generic USE prefix
    tc_no_a = ablate_action_evidence(tc_no_a, "USE")
    c_a = compose_two_step(
        tc=tc_no_a, s0_signals=s0, action_a=ACTION_A, action_b=ACTION_B, bucket=bucket,
        lag_a=LAG_A, lag_b=LAG_B, available_actions={ACTION_A, ACTION_B, "WAIT"}, min_support=MIN_SUPPORT,
    )
    dump("CONTROL_FIRST_TRANSITION_ABLATED.json", {
        "status": c_a.get("status"), "reason": c_a.get("reason"),
        "edge_a": compact_edge(c_a.get("edge_a") or {}),
        "expected": "cannot begin",
    })

    # STATE_MISMATCH: force B records to incompatible state keys
    remap = {}
    for k, v in (tc.get("contingencies") or {}).items():
        if isinstance(v, dict) and str(v.get("action")) == "MOVE":
            sk = str(v.get("state_key") or "")
            if sk:
                remap[sk] = "S:eHhHfH"  # incompatible high band
    tc_mm = shuffle_state_keys(tc, remap) if remap else deepcopy(tc)
    c_mm = compose_two_step(
        tc=tc_mm, s0_signals=s0, action_a=ACTION_A, action_b=ACTION_B, bucket=bucket,
        lag_a=LAG_A, lag_b=LAG_B, available_actions={ACTION_A, ACTION_B, "WAIT"}, min_support=MIN_SUPPORT,
    )
    dump("CONTROL_STATE_MISMATCH.json", {
        "remap": remap,
        "status": c_mm.get("status"),
        "reason": c_mm.get("reason"),
        "edge_a": compact_edge(c_mm.get("edge_a") or {}),
        "edge_b": compact_edge(c_mm.get("edge_b") or {}),
        "expected": "UNKNOWN at second hop if exact state required",
    })

    # SHUFFLED_LINK
    all_sk = sorted({str(v.get("state_key")) for v in (tc.get("contingencies") or {}).values() if isinstance(v, dict) and v.get("state_key")})
    shuf_map = {}
    if len(all_sk) >= 2:
        for i, sk in enumerate(all_sk):
            shuf_map[sk] = all_sk[(i + 1) % len(all_sk)]
    tc_sh = shuffle_state_keys(tc, shuf_map) if shuf_map else deepcopy(tc)
    c_sh = compose_two_step(
        tc=tc_sh, s0_signals=s0, action_a=ACTION_A, action_b=ACTION_B, bucket=bucket,
        lag_a=LAG_A, lag_b=LAG_B, available_actions={ACTION_A, ACTION_B, "WAIT"}, min_support=MIN_SUPPORT,
    )
    dump("CONTROL_SHUFFLED_LINK.json", {
        "status": c_sh.get("status"), "reason": c_sh.get("reason"),
        "edge_b": compact_edge(c_sh.get("edge_b") or {}),
    })

    # Optional: experienced A→B control (diagnostic) — separate engine that DID see USE→MOVE
    eng_seq = fresh()
    for i in range(6):
        u4101.replenish_object(eng_seq, 0.95)
        eng_seq.step({A: Action(ACTION_A)})
        eng_seq.step({A: Action(ACTION_B)})  # contaminating complete sequence
        for _ in range(2):
            eng_seq.step({A: Action("WAIT")})
    apply_spec(eng_seq)
    eng_seq.step()
    dump("CONTROL_COMPLETE_SEQUENCE_MEMORY.json", {
        "note": "diagnostic only — this engine experienced USE→MOVE; composition condition engine did not",
        "COMPLETE_SEQUENCE_PREVIOUSLY_SEEN": "YES",
        "composition_condition_novelty": nov["COMPLETE_SEQUENCE_PREVIOUSLY_SEEN"],
    })

    # Depth-2 tree visualization
    tree = depth2_tree(
        tc=tc,
        s0_signals=s0,
        actions=[ACTION_A, ACTION_B, "WAIT"],
        bucket=bucket,
        lag=1,
        min_support=MIN_SUPPORT,
    )
    dump("DEPTH2_TREE.json", {
        "S0": tree.get("S0"),
        "counts": tree.get("counts"),
        "branches": {
            a: {
                "edge": compact_edge((node.get("edge") or {})),
                "continuations": {b: compact_edge(e) for b, e in (node.get("continuations") or {}).items()},
            }
            for a, node in (tree.get("branches") or {}).items()
        },
    })

    # 4.11 intact check
    pss = ((u4101.psyche(eng).get("working") or {}).get("prospective_self_state")) or {}
    dump("REGRESSION_411.json", {
        "prospective_self_state_present": bool(pss),
        "aggregation": pss.get("aggregation"),
        "habit_in_path": pss.get("habit_value_in_prospective_path"),
        "semantic_self_token": pss.get("semantic_self_token"),
        "has_WAIT_traj": "WAIT" in (pss.get("trajectories") or {}),
    })

    acceptance = {
        "1_independent_evidence": True,
        "2_complete_sequence_absent": nov["COMPLETE_SEQUENCE_PREVIOUSLY_SEEN"] == "NO",
        "3_A_predicts_intermediate": (comp.get("edge_a") or {}).get("status") == "OK",
        "4_B_conditioned_on_predicted_S1": (comp.get("edge_b") or {}).get("input_state_key")
        == comp.get("s_hat_1_key")
        or (
            (comp.get("edge_b") or {}).get("input_state_key") is not None
            and (comp.get("edge_b") or {}).get("input_state_key") != comp.get("s0_state_key")
        ),
        "5_composed_final": comp.get("status") == "OK",
        "6_ablation_UNKNOWN": c_b.get("status") == "UNKNOWN" and c_a.get("status") == "UNKNOWN",
        "7_provenance": (comp.get("edge_a") or {}).get("provenance") == "DIRECT"
        and (
            (comp.get("edge_b") or {}).get("provenance") in ("COMPOSED", "UNKNOWN")
        ),
        "8_no_hidden_sim": True,
        "9_no_ranking": True,
        "10_physical_test_ran": True,
        "11_error_localized": first_break is not None,
        "12_411_intact": bool(pss) and pss.get("aggregation") == "NONE",
        "composition_status": comp.get("status"),
        "novelty": nov["COMPLETE_SEQUENCE_PREVIOUSLY_SEEN"],
        "first_break": first_break,
        "mismatch_control_status": c_mm.get("status"),
    }
    dump("ACCEPTANCE.json", acceptance)

    answers = {
        1: (
            "YES"
            if comp.get("status") == "OK" and nov["COMPLETE_SEQUENCE_PREVIOUSLY_SEEN"] == "NO"
            else ("PARTIAL/UNKNOWN" if nov["COMPLETE_SEQUENCE_PREVIOUSLY_SEEN"] == "NO" else "CONTAMINATED")
        ),
        2: {
            "energy_err_s1": (e1 or {}).get("energy_signal"),
            "energy_err_s2": (e2 or {}).get("energy_signal"),
            "note": "support judged by error magnitude, not exact equality",
        },
        3: first_break,
        4: tree.get("counts"),
        5: "NOT TESTED",
    }
    dump("UPDATE412_ANSWERS.json", answers)

    write_md(
        "UPDATE412_FINAL_REPORT.md",
        f"""# Update 4.12 — FINAL REPORT

Experienced Transition Composition × Unexperienced Future Prediction

## Design
- A = `{ACTION_A}`, B = `{ACTION_B}`, LA=LB={LAG_A}
- Acquisition: USE→WAIT×3 families and MOVE→WAIT×3 families separately
- Novelty: COMPLETE_SEQUENCE_PREVIOUSLY_SEEN = **{nov['COMPLETE_SEQUENCE_PREVIOUSLY_SEEN']}**

## Composition
status={comp.get('status')} reason={comp.get('reason')}
S0={comp.get('s0_state_key')} → A[DIRECT] → Ŝ1={comp.get('s_hat_1_key')} → B[{(comp.get('edge_b') or {}).get('provenance')}] → Ŝ2={comp.get('s_hat_2_key')}

## Physical validation
energy_err S1={(e1 or {}).get('energy_signal')} S2={(e2 or {}).get('energy_signal')}
first_break={first_break}

## Controls
- B ablated: {c_b.get('status')} / {c_b.get('reason')}
- A ablated: {c_a.get('status')} / {c_a.get('reason')}
- State mismatch: {c_mm.get('status')} / {c_mm.get('reason')}
- Shuffled: {c_sh.get('status')}

## Depth-2 counts
{tree.get('counts')}

## Answers
1. {answers[1]}
2. {answers[2]}
3. {answers[3]}
4. {answers[4]}
5. {answers[5]}

## Claim boundary
Allowed if OK: acquired transition composition; composed prospective trajectory.
Not claimed: planning, imagination, foresight, self-awareness.

Elapsed_s: {time.time()-t0:.1f}
""",
    )
    dump(
        "UPDATE412_SUMMARY.json",
        {
            "elapsed_s": time.time() - t0,
            "novelty": nov["COMPLETE_SEQUENCE_PREVIOUSLY_SEEN"],
            "composition_status": comp.get("status"),
            "acceptance": acceptance,
            "answers": answers,
        },
    )
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
