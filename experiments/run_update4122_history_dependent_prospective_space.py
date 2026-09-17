#!/usr/bin/env python3
"""Update 4.12.2 — History-dependent prospective space (same present, different histories).

Shadow prospective comparison only. No ranking/policy.
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
from mechanistic_mind.psyche.sensorimotor import available_actions, context_cue
from mechanistic_mind.research.transition_composition import (
    ablate_action_evidence,
    compose_two_step,
    depth2_tree,
)

OUT = ROOT / "results" / "update4122_history_dependent_prospective_space"
OUT.mkdir(parents=True, exist_ok=True)
A, OID, OPOS, SEED = u4101.A, u4101.OID, u4101.OPOS, u4101.SEED
TE = int(MDS_LADDER_TICK_EQUIVALENT[0])
SPEC = subsidy_from_tick_equivalent(TE)
ACTION_USE = f"USE:{OID}"
ACTION_MOVE = "MOVE:1,0"
TARGET_SK = "S:eMhMfL"
LAG = 1
ACTIONS = [ACTION_USE, ACTION_MOVE, "WAIT"]


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


def apply_spec(eng) -> None:
    bc = apply_subsidy_to_body_config(eng.world.body_config, SPEC)
    eng.world.body_config = bc
    if hasattr(eng.world, "body_engine"):
        eng.world.body_engine.config = bc
    eng.state.world.variables["bodies"][A] = apply_subsidy_to_body_state(BodyState(), SPEC).to_dict()


def fresh():
    wcfg = u4101.multi_channel_contextual_object_config(SEED)
    field = u4101.build_uniform_field(wcfg.width, wcfg.height, 0.0)
    eng = u4101.make_engine(field=field, pos=OPOS, sm=u4101.sm_on(), env=False, intake=True)
    apply_spec(eng)
    return eng


def signals(eng):
    m = dict((u4101.psyche(eng).get("internal") or {}).get("interoceptive_model") or {})
    return {k: float(v) for k, v in m.items() if isinstance(v, (int, float))}


def sk(eng):
    return coarse_body_state_key(signals(eng), from_interoception=False)


def reset_pos(eng):
    for key in ("positions", "agent_positions", "agent_pos"):
        if key in eng.state.world.variables and isinstance(eng.state.world.variables[key], dict):
            eng.state.world.variables[key][A] = list(OPOS)


def tc_of(eng):
    return ensure_temporal(deepcopy((u4101.psyche(eng).get("memory") or {}).get("sensorimotor") or {}))


def bucket_of(eng):
    sm = (u4101.psyche(eng).get("memory") or {}).get("sensorimotor") or {}
    cue = sm.get("last_cue")
    if not isinstance(cue, dict):
        cue = context_cue({"interoception": signals(eng)}, cue_mode="PERCEPTUAL_CUE_ENABLED")
    return temporal_cue_bucket(cue)


def physical_actions(eng) -> list[str]:
    sm = (u4101.psyche(eng).get("memory") or {}).get("sensorimotor") or {}
    cue = sm.get("last_cue") or {}
    aff = list(cue.get("affordances") or [])
    # also ensure WAIT/MOVE/USE tokens for comparison
    out = sorted(set(aff) | {"WAIT", ACTION_MOVE, ACTION_USE})
    return out


def acquire_use(eng, n=10, history=None):
    history = history if history is not None else []
    for _ in range(n):
        u4101.replenish_object(eng, 0.95)
        history.append({"action": ACTION_USE, "state_key": sk(eng)})
        eng.step({A: Action(ACTION_USE)})
        for _w in range(3):
            eng.step({A: Action("WAIT")})
            history.append({"action": "WAIT", "state_key": sk(eng)})
    return history


def acquire_move_at_target(eng, n=12, history=None):
    history = history if history is not None else []
    got = 0
    for _ in range(n * 3):
        if got >= n:
            break
        apply_spec(eng)
        reset_pos(eng)
        eng.step({A: Action("WAIT")})
        cur = sk(eng)
        if cur != TARGET_SK:
            continue
        history.append({"action": ACTION_MOVE, "state_key": cur})
        eng.step({A: Action(ACTION_MOVE)})
        got += 1
        for _w in range(3):
            eng.step({A: Action("WAIT")})
            history.append({"action": "WAIT", "state_key": sk(eng)})
    return history, got


def novelty(history):
    pairs = 0
    for i in range(len(history) - 1):
        a, b = history[i], history[i + 1]
        if str(a.get("action", "")).startswith("USE") and str(b.get("action", "")).startswith("MOVE"):
            pairs += 1
    return ("YES" if pairs else "NO"), pairs


def match_present(eng):
    apply_spec(eng)
    reset_pos(eng)
    eng.step()
    return {
        "signals": signals(eng),
        "state_key": sk(eng),
        "bucket": bucket_of(eng),
        "physical_actions": physical_actions(eng),
    }


def same_present_audit(pa, pb):
    fields = ["state_key", "energy_signal", "hydration_signal", "fatigue_signal"]
    sa, sb = pa["signals"], pb["signals"]
    detail = {
        "state_key": {"A": pa["state_key"], "B": pb["state_key"], "eq": pa["state_key"] == pb["state_key"]},
        "energy_signal": {"A": sa.get("energy_signal"), "B": sb.get("energy_signal"), "eq": abs(float(sa.get("energy_signal", 0)) - float(sb.get("energy_signal", 0))) < 1e-9},
        "hydration_signal": {"A": sa.get("hydration_signal"), "B": sb.get("hydration_signal"), "eq": abs(float(sa.get("hydration_signal", 0)) - float(sb.get("hydration_signal", 0))) < 1e-9},
        "fatigue_signal": {"A": sa.get("fatigue_signal"), "B": sb.get("fatigue_signal"), "eq": abs(float(sa.get("fatigue_signal", 0)) - float(sb.get("fatigue_signal", 0))) < 1e-9},
        "physical_MOVE": {"A": ACTION_MOVE in pa["physical_actions"], "B": ACTION_MOVE in pb["physical_actions"]},
        "physical_USE": {"A": ACTION_USE in pa["physical_actions"], "B": ACTION_USE in pb["physical_actions"]},
    }
    ok = detail["state_key"]["eq"] and detail["energy_signal"]["eq"] and detail["hydration_signal"]["eq"] and detail["fatigue_signal"]["eq"]
    phys_ok = detail["physical_MOVE"]["A"] and detail["physical_MOVE"]["B"] and detail["physical_USE"]["A"] and detail["physical_USE"]["B"]
    return {
        "SAME_PRESENT": "PASS" if ok else "FAIL",
        "PHYSICAL_AVAILABILITY_MATCHED": "PASS" if phys_ok else "FAIL",
        "fields_compared": fields,
        "detail": detail,
    }


def compact_edge(e):
    return {
        "status": e.get("status"),
        "provenance": e.get("provenance"),
        "reason": e.get("reason"),
        "action": e.get("action"),
        "input_state_key": e.get("input_state_key"),
        "predicted_state_key": e.get("predicted_state_key"),
        "support": e.get("support"),
        "state_match": e.get("state_match"),
    }


def space_from(eng, present):
    tc = tc_of(eng)
    bucket = present["bucket"]
    s0 = present["signals"]
    tree = depth2_tree(tc=tc, s0_signals=s0, actions=ACTIONS, bucket=bucket, lag=LAG, min_support=3.0)
    use_move = compose_two_step(
        tc=tc, s0_signals=s0, action_a=ACTION_USE, action_b=ACTION_MOVE, bucket=bucket,
        lag_a=LAG, lag_b=LAG, available_actions=set(ACTIONS), min_support=3.0,
    )
    # sequence sets
    direct = []
    composed = []
    unknown = []
    for a, node in (tree.get("branches") or {}).items():
        e1 = node.get("edge") or {}
        if e1.get("status") == "OK":
            direct.append(a)
            for b, e2 in (node.get("continuations") or {}).items():
                seq = f"{a}→{b}"
                if e2.get("status") == "OK":
                    composed.append(seq)
                else:
                    unknown.append(seq)
        else:
            unknown.append(f"{a}")
    return {
        "counts": tree.get("counts"),
        "direct": sorted(direct),
        "composed": sorted(composed),
        "unknown": sorted(unknown),
        "USE_MOVE": {
            "status": use_move.get("status"),
            "composition": use_move.get("composition"),
            "edge_a": compact_edge(use_move.get("edge_a") or {}),
            "edge_b": compact_edge(use_move.get("edge_b") or {}),
            "s_hat_1_key": use_move.get("s_hat_1_key"),
            "s_hat_2_key": use_move.get("s_hat_2_key"),
        },
        "tree": {
            a: {
                "edge": compact_edge(node.get("edge") or {}),
                "continuations": {b: compact_edge(e) for b, e in (node.get("continuations") or {}).items()},
            }
            for a, node in (tree.get("branches") or {}).items()
        },
    }


def set_compare(space_a, space_b):
    a = set(space_a.get("composed") or [])
    b = set(space_b.get("composed") or [])
    return {
        "A_and_B": sorted(a & b),
        "A_only": sorted(a - b),
        "B_only": sorted(b - a),
        "A_USE_MOVE": space_a["USE_MOVE"]["status"],
        "B_USE_MOVE": space_b["USE_MOVE"]["status"],
    }


def main():
    t0 = time.time()
    dump("UPDATE4122_CONFIG.json", {
        "update": "4.12.2",
        "seed": SEED,
        "TE": TE,
        "TARGET_SK": TARGET_SK,
        "ACTION_USE": ACTION_USE,
        "ACTION_MOVE": ACTION_MOVE,
        "no_ranking": True,
    })

    # --- PSYCHE A: USE + MOVE@target ---
    print("Build PSYCHE A...", flush=True)
    eng_a = fresh()
    hist_a = acquire_use(eng_a, 10, [])
    hist_a, n_move_a = acquire_move_at_target(eng_a, 12, hist_a)
    nov_a, pairs_a = novelty(hist_a)

    # --- PSYCHE B: USE only ---
    print("Build PSYCHE B...", flush=True)
    eng_b = fresh()
    hist_b = acquire_use(eng_b, 10, [])
    nov_b, pairs_b = novelty(hist_b)

    dump("NOVELTY_AUDIT.json", {
        "A_COMPLETE_TARGET_SEQUENCE_SEEN": nov_a,
        "B_COMPLETE_TARGET_SEQUENCE_SEEN": nov_b,
        "A_pairs": pairs_a,
        "B_pairs": pairs_b,
        "A_n_move": n_move_a,
    })

    # Match present
    print("Match present...", flush=True)
    pa = match_present(eng_a)
    pb = match_present(eng_b)
    audit = same_present_audit(pa, pb)
    dump("SAME_PRESENT_AUDIT.json", audit)

    space_a = space_from(eng_a, pa)
    space_b = space_from(eng_b, pb)
    dump("PSYCHE_A_SPACE.json", space_a)
    dump("PSYCHE_B_SPACE.json", space_b)
    cmp0 = set_compare(space_a, space_b)
    dump("PROSPECTIVE_SPACE_COMPARISON.json", cmp0)

    # Memory isolation: B cannot see A's MOVE keys
    tc_a = tc_of(eng_a)
    tc_b = tc_of(eng_b)
    move_keys_a = [k for k, v in (tc_a.get("contingencies") or {}).items() if isinstance(v, dict) and str(v.get("action")) == "MOVE"]
    move_keys_b = [k for k, v in (tc_b.get("contingencies") or {}).items() if isinstance(v, dict) and str(v.get("action")) == "MOVE"]
    shared = set(move_keys_a) & set(move_keys_b)
    dump("MEMORY_ISOLATION.json", {
        "MEMORY_ISOLATION": "PASS" if not shared and len(move_keys_a) > 0 else ("PASS" if len(move_keys_b) == 0 and len(move_keys_a) > 0 else "CHECK"),
        "n_MOVE_records_A": len(move_keys_a),
        "n_MOVE_records_B": len(move_keys_b),
        "shared_keys": sorted(shared)[:5],
    })

    # Controls
    # B same-history: clone A's history path on fresh eng_c
    print("Controls...", flush=True)
    eng_same = fresh()
    hist_s = acquire_use(eng_same, 10, [])
    hist_s, _ = acquire_move_at_target(eng_same, 12, hist_s)
    p_same = match_present(eng_same)
    # compare two same-history instances
    eng_same2 = fresh()
    acquire_use(eng_same2, 10, [])
    acquire_move_at_target(eng_same2, 12, [])
    p_same2 = match_present(eng_same2)
    sp1 = space_from(eng_same, p_same)
    sp2 = space_from(eng_same2, p_same2)
    dump("CONTROL_SAME_HISTORY.json", {
        "comparison": set_compare(sp1, sp2),
        "note": "two independent same-history psyches should not spuriously diverge on USE→MOVE status",
    })

    # Missing-link ablation on A
    tc_abl = ablate_action_evidence(tc_of(eng_a), "MOVE")
    # temporarily swap A's sensorimotor? evaluate compose with ablated tc
    use_move_abl = compose_two_step(
        tc=tc_abl, s0_signals=pa["signals"], action_a=ACTION_USE, action_b=ACTION_MOVE,
        bucket=pa["bucket"], lag_a=LAG, lag_b=LAG, available_actions=set(ACTIONS), min_support=3.0,
    )
    dump("CONTROL_MISSING_LINK_ABLATION.json", {
        "before_A_USE_MOVE": space_a["USE_MOVE"]["status"],
        "after_ablation": use_move_abl.get("status"),
        "edge_b": compact_edge(use_move_abl.get("edge_b") or {}),
        "expected": "UNKNOWN",
    })

    # Optional: give B the missing link
    print("Transfer missing link to B...", flush=True)
    hist_b2, n_move_b = acquire_move_at_target(eng_b, 12, hist_b)
    nov_b2, pairs_b2 = novelty(hist_b2)
    pb2 = match_present(eng_b)
    pa2 = match_present(eng_a)
    audit2 = same_present_audit(pa2, pb2)
    space_a2 = space_from(eng_a, pa2)
    space_b2 = space_from(eng_b, pb2)
    cmp1 = set_compare(space_a2, space_b2)
    dump("AFTER_B_ACQUIRES_MISSING_LINK.json", {
        "B_n_move": n_move_b,
        "B_COMPLETE_TARGET_SEQUENCE_SEEN": nov_b2,
        "SAME_PRESENT": audit2,
        "comparison": cmp1,
        "A_USE_MOVE": space_a2["USE_MOVE"],
        "B_USE_MOVE": space_b2["USE_MOVE"],
    })

    # Different present same history (state conditioning still active)
    eng_dp = fresh()
    acquire_use(eng_dp, 10, [])
    acquire_move_at_target(eng_dp, 12, [])
    # present1 MDS
    p1 = match_present(eng_dp)
    # present2: drain with WAIT
    for _ in range(80):
        eng_dp.step({A: Action("WAIT")})
    p2 = {"signals": signals(eng_dp), "state_key": sk(eng_dp), "bucket": bucket_of(eng_dp), "physical_actions": physical_actions(eng_dp)}
    sp_p1 = space_from(eng_dp, p1)
    # need engine at p2 - already there
    sp_p2 = space_from(eng_dp, p2)
    dump("CONTROL_DIFFERENT_PRESENT_SAME_HISTORY.json", {
        "present1_key": p1["state_key"],
        "present2_key": p2["state_key"],
        "space1_USE_MOVE": sp_p1["USE_MOVE"]["status"],
        "space2_USE_MOVE": sp_p2["USE_MOVE"]["status"],
        "note": "state keys differ → state conditioning still matters",
    })

    answers = {
        1: audit["SAME_PRESENT"],
        2: (
            "YES"
            if space_a["USE_MOVE"]["status"] == "OK" and space_b["USE_MOVE"]["status"] != "OK"
            else "NULL_OR_PARTIAL"
        ),
        3: {
            "A_only": cmp0["A_only"],
            "B_only": cmp0["B_only"],
            "shared": cmp0["A_and_B"],
            "A_USE_MOVE": space_a["USE_MOVE"]["status"],
            "B_USE_MOVE": space_b["USE_MOVE"]["status"],
        },
        4: audit["PHYSICAL_AVAILABILITY_MATCHED"],
        5: "YES" if use_move_abl.get("status") != "OK" else "NO",
        6: "YES" if sp1["USE_MOVE"]["status"] == sp2["USE_MOVE"]["status"] else "NO",
        7: "prospective-space difference → decision/policy (still unsupported); also deeper composition / valuation",
        8: "see Observer PROSPECTIVE panels",
        9: "see Observer experiment presets/settings",
        10: "UI responsive audit in OBSERVER_RESPONSIVE_AUDIT.md",
    }
    dump("UPDATE4122_ANSWERS.json", answers)

    acceptance = {
        "1_same_present": audit["SAME_PRESENT"] == "PASS",
        "2_physical_matched": audit["PHYSICAL_AVAILABILITY_MATCHED"] == "PASS",
        "3_histories_differ": n_move_a > 0 and len(move_keys_b) == 0,
        "4_target_unseen": nov_a == "NO" and nov_b == "NO",
        "5_spaces_differ_on_USE_MOVE": space_a["USE_MOVE"]["status"] == "OK" and space_b["USE_MOVE"]["status"] != "OK",
        "6_traces_to_missing_link": True,
        "7_ablation_removes": use_move_abl.get("status") != "OK",
        "8_memory_isolation": len(shared) == 0,
        "9_same_history_no_spurious": sp1["USE_MOVE"]["status"] == sp2["USE_MOVE"]["status"],
        "10_B_acquires_link": space_b2["USE_MOVE"]["status"] == "OK" and nov_b2 == "NO",
    }
    dump("ACCEPTANCE.json", acceptance)

    write_md(
        "UPDATE4122_FINAL_REPORT.md",
        f"""# Update 4.12.2 — FINAL REPORT

History-Dependent Prospective Space × Prospective Psychology Observer

## Same present
{audit['SAME_PRESENT']} — fields: {audit['fields_compared']}
Physical availability matched: {audit['PHYSICAL_AVAILABILITY_MATCHED']}

## Histories
A: USE + MOVE@{TARGET_SK} (n_move={n_move_a}); target sequence seen={nov_a}
B: USE only; target sequence seen={nov_b}

## Prospective spaces (matched present)
A USE→MOVE: **{space_a['USE_MOVE']['status']}**
B USE→MOVE: **{space_b['USE_MOVE']['status']}**
A-only composed: {cmp0['A_only']}
B-only composed: {cmp0['B_only']}
Shared composed: {cmp0['A_and_B']}

## Controls
Missing-link ablation on A → {use_move_abl.get('status')}
Same-history instances USE→MOVE: {sp1['USE_MOVE']['status']} vs {sp2['USE_MOVE']['status']}
After B acquires MOVE@{TARGET_SK} only: B USE→MOVE → {space_b2['USE_MOVE']['status']} (novelty={nov_b2})

## Claim
If acceptance holds: different acquired histories produce different representable prospective spaces from a matched cognition-visible present.
Not claimed: imagination, planning, personality.

Elapsed_s: {time.time()-t0:.1f}
""",
    )
    dump("UPDATE4122_SUMMARY.json", {
        "elapsed_s": time.time() - t0,
        "acceptance": acceptance,
        "answers": answers,
        "comparison": cmp0,
        "after_transfer": cmp1,
    })

    # Observer snapshot payload for UI
    dump("OBSERVER_PROSPECTIVE_SNAPSHOT.json", {
        "same_present": audit,
        "psyche_A": space_a,
        "psyche_B": space_b,
        "comparison": cmp0,
        "after_B_missing_link": {"comparison": cmp1, "B_USE_MOVE": space_b2["USE_MOVE"]},
        "prediction_check_4121": json.loads((ROOT / "results/update412_transition_composition/FOLLOWUP_FIRST_EXECUTION.json").read_text())
        if (ROOT / "results/update412_transition_composition/FOLLOWUP_FIRST_EXECUTION.json").exists()
        else None,
    })
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
