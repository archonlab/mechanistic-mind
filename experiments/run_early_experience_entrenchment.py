#!/usr/bin/env python3
"""Early-experience entrenchment harness. Does not change CURRENT INTEGRATED MM."""
from __future__ import annotations

import json
import math
import sys
from collections import Counter
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mechanistic_mind.physical_system import PhysicalSystemRuntime
from mechanistic_mind.physical_system.actions import available_actions
from mechanistic_mind.physical_system.runtime import _rng_unit
from mechanistic_mind.research import predictive_compression as pc
from mechanistic_mind.research import prospective_composition as pr
from mechanistic_mind.physical_system import scenario_competition as sc

OUT = ROOT / "results" / "mm_early_experience_entrenchment"
ACTIONS = list(available_actions())
BASE_SEEDS = (17, 23, 41, 59, 83, 66667)
CURVE_NS = (0, 1, 2, 3, 4, 5, 10, 20, 50, 100)
PERSIST = 20
FOLLOW = 80


def _entropy(counts: dict) -> float:
    n = sum(counts.values())
    if n <= 0:
        return 0.0
    h = 0.0
    for c in counts.values():
        if c:
            p = c / n
            h -= p * math.log(p, 2)
    return h


def _physical_fingerprint(rt: PhysicalSystemRuntime) -> dict:
    obs = rt.agent_observation()
    return {
        "tick": int(rt.tick),
        "seed": int(rt.seed),
        "x": float(rt.body.x),
        "y": float(rt.body.y),
        "vx": float(rt.body.vx),
        "vy": float(rt.body.vy),
        "theta": float(getattr(rt.body, "theta", 0.0) or 0.0),
        "omega": float(getattr(rt.body, "omega", 0.0) or 0.0),
        "W": float(getattr(rt.body, "mechanical_work_reservoir", 0.0) or 0.0),
        "T_body": float(rt.body.T),
        "world_T_mean": float(rt.world.T.mean()),
        "internal_c_mean": float(rt.internal.c.mean()) if getattr(rt.internal, "c", None) is not None else None,
        "obs": {k: float(v) for k, v in obs.items()},
        "obs_qsig": pr._sig(pr._q(obs)),
        "obs_csig": pc._sig(obs),
    }


def _same_present(a: dict, b: dict, *, atol: float = 1e-12) -> dict:
    skip = {"obs"}
    diffs = []
    for k in a:
        if k in skip:
            continue
        if a.get(k) != b.get(k):
            try:
                if abs(float(a[k]) - float(b[k])) <= atol:
                    continue
            except (TypeError, ValueError):
                pass
            diffs.append(k)
    obs_diff = [k for k in set(a["obs"]) | set(b["obs"]) if abs(float(a["obs"].get(k, 0)) - float(b["obs"].get(k, 0))) > atol]
    return {"identical_keys_ok": not diffs and not obs_diff, "diff_keys": diffs, "obs_diff": obs_diff}


def _decision_view(rt: PhysicalSystemRuntime) -> dict:
    sel = rt.cognition.get("last_selection") or {}
    obs = rt.last_agent_observation or rt.agent_observation()
    store = rt.cognition["prospection"]
    mem = rt.cognition["compression"]
    groups = sel.get("scenario_groups") or {}
    comp = sel.get("competition") or {}
    observed = Counter(r.get("action") for r in (store.get("transitions") or {}).values())
    supports = {}
    usable = {}
    for act in ACTIONS:
        key = pr.transition_key(pr._q(obs), act)
        row = (store.get("transitions") or {}).get(key)
        supports[act] = int((row or {}).get("support") or 0)
        one = pr.predict_one_step(store, obs, act)
        pred = pc.predict(mem, obs, act, domain="accessible")
        usable[act] = {
            "observed_any": observed.get(act, 0) > 0,
            "exact_support": supports[act],
            "one_step": one.get("status"),
            "one_step_support": one.get("support"),
            "retrieved": pred.get("status") == "MATCH",
            "supported": bool((groups.get(act) or {}).get("supported") or (groups.get(act) or {}).get("count")),
            "competing": act in set(comp.get("supported_actions") or []),
        }
    return {
        "tick": int(rt.tick),
        "available": list(ACTIONS),
        "endogenous_would_be": ACTIONS[min(len(ACTIONS) - 1, int(_rng_unit(rt.seed, rt.tick) * len(ACTIONS)))],
        "rng": _rng_unit(rt.seed, rt.tick),
        "selected": sel.get("action") or rt.last_selected_action,
        "source": sel.get("source"),
        "outcome": (comp or {}).get("outcome_class"),
        "supported_actions": list(comp.get("supported_actions") or [a for a, g in groups.items() if g.get("supported")]),
        "competing_n": len(comp.get("supported_actions") or []),
        "prediction_matches": len(sel.get("prediction_matches") or []),
        "continuations": len(sel.get("continuations") or []),
        "observed_actions": dict(observed),
        "supports_at_obs": supports,
        "per_action": usable,
        "rule": sel.get("selection_rule"),
    }


def _lock_from_trace(trace: list[dict], persist: int = PERSIST) -> dict:
    lock_t = None
    for i, rec in enumerate(trace):
        if rec.get("source") != "PROSPECTIVE_SCENARIO":
            continue
        if rec.get("outcome") != "SINGLE_SUPPORTED":
            continue
        if rec.get("competing_n") != 1:
            continue
        window = trace[i:i + persist]
        if len(window) < persist:
            break
        if all(w.get("selected") == rec["selected"] and w.get("outcome") == "SINGLE_SUPPORTED" for w in window):
            lock_t = rec["tick"]
            break
    last_div = None
    for rec in trace:
        if rec.get("source") == "ENDOGENOUS_VARIATION" or int(rec.get("competing_n") or 0) != 1:
            last_div = rec["tick"]
    return {
        "lock_tick": lock_t,
        "diversity_last_tick": last_div,
        "locked_action": None if lock_t is None else next(r["selected"] for r in trace if r["tick"] == lock_t),
    }


def snapshot_clean(rt: PhysicalSystemRuntime) -> dict:
    return rt.snapshot()


def restore(snap: dict) -> PhysicalSystemRuntime:
    return PhysicalSystemRuntime.restore(deepcopy(snap))


def consequent_for_action(snap: dict, action: str) -> dict[str, float]:
    rt = restore(snap)
    before = rt.agent_observation()
    rt.step_forced_action(action)
    return {"antecedent": before, "consequent": rt.agent_observation(), "after_tick": int(rt.tick)}


def graft_history(snap: dict, *, action: str, n: int, consequent: dict) -> PhysicalSystemRuntime:
    rt = restore(snap)
    rt.cognition["prospection"] = pr.empty_store()
    rt.cognition["compression"] = pc.empty_memory()
    rt.cognition["last_fragment"] = None
    rt.cognition["last_action"] = None
    obs = rt.agent_observation()
    ant = consequent.get("antecedent", obs)
    nxt = consequent.get("consequent", obs)
    for i in range(max(0, n)):
        pr.learn_transition(rt.cognition["prospection"], tick=i + 1, antecedent=ant, action=action, consequent=nxt)
    return rt


def _endogenous_at(seed: int, tick: int) -> str:
    return ACTIONS[min(len(ACTIONS) - 1, int(_rng_unit(seed, tick) * len(ACTIONS)))]


def run_free(rt: PhysicalSystemRuntime, n: int) -> list[dict]:
    out = []
    for _ in range(n):
        rt.step(1)
        out.append(_decision_view(rt))
    return out


def baseline_seed(seed: int, ticks: int = 200) -> dict:
    rt = PhysicalSystemRuntime(seed=seed)
    early = []
    for t in range(min(12, ticks)):
        rt.step(1)
        early.append(_decision_view(rt))
    rest = run_free(rt, ticks - min(12, ticks))
    trace = early + rest
    lock = _lock_from_trace(trace)
    counts = Counter(r["selected"] for r in trace)
    return {
        "seed": seed,
        "ticks": ticks,
        "first_endogenous": ACTIONS[min(len(ACTIONS) - 1, int(_rng_unit(seed, 0) * len(ACTIONS)))],
        "first_rng": _rng_unit(seed, 0),
        "early": early,
        "lock": lock,
        "action_counts": dict(counts),
        "entropy": _entropy(counts),
        "final_source": trace[-1]["source"],
        "final_outcome": trace[-1]["outcome"],
    }


def lived_biography(seed: int, action: str, force_n: int = 10, follow: int = FOLLOW) -> dict:
    rt = PhysicalSystemRuntime(seed=seed)
    forced = []
    for _ in range(force_n):
        rt.step_forced_action(action)
        forced.append(_decision_view(rt))
    free = run_free(rt, follow)
    trace = forced + free
    lock = _lock_from_trace(free if free else trace)
    return {
        "protocol": "L_lived",
        "seed": seed,
        "forced_action": action,
        "force_n": force_n,
        "follow": follow,
        "forced_selected": [r["selected"] for r in forced],
        "free_selected": [r["selected"] for r in free],
        "free_counts": dict(Counter(r["selected"] for r in free)),
        "lock": lock,
        "present_after_force": _physical_fingerprint(rt),
        "note": "Physical state diverges from other biographies after the first forced MOVE.",
    }


def matched_graft(snap: dict, action: str, n: int, consequents: dict, follow: int = FOLLOW) -> dict:
    fp0 = _physical_fingerprint(restore(snap))
    cons = consequents[action]
    rt = graft_history(snap, action=action, n=n, consequent=cons)
    fp1 = _physical_fingerprint(rt)
    identity = _same_present(fp0, fp1)
    pre = {
        "supports": {a: pr.predict_one_step(rt.cognition["prospection"], rt.agent_observation(), a) for a in ACTIONS},
    }
    groups = sc.collect_scenario_groups(
        store=rt.cognition["prospection"],
        observation=rt.agent_observation(),
        continuations=pr.compose_trajectories(
            rt.cognition["prospection"], start=rt.agent_observation(),
            max_depth=3, branch_actions=ACTIONS,
        ).get("continuations") or [],
        actions=ACTIONS,
    )
    supported = [a for a, g in groups.items() if g]
    endogenous = _endogenous_at(rt.seed, rt.tick)
    first = run_free(rt, 1)[0]
    more = run_free(rt, follow - 1)
    free = [first] + more
    lock = _lock_from_trace(free)
    return {
        "protocol": "G_grafted",
        "action": action,
        "n": n,
        "present_identical_before_step": identity,
        "pre_supported": supported,
        "endogenous_would_be": endogenous,
        "history_overrides_sampler": first["selected"] != endogenous,
        "first_selected": first["selected"],
        "first_source": first["source"],
        "first_outcome": first["outcome"],
        "first_competing_n": first["competing_n"],
        "first_supported": first["supported_actions"],
        "follow_counts": dict(Counter(r["selected"] for r in free)),
        "follow_entropy": _entropy(Counter(r["selected"] for r in free)),
        "lock": lock,
        "other_action_appears_at": next((r["tick"] for r in free if r["selected"] != action), None),
        "second_selected": free[1]["selected"] if len(free) > 1 else None,
        "second_source": free[1]["source"] if len(free) > 1 else None,
    }


def mixed_graft(snap: dict, n: int, consequents: dict, follow: int = FOLLOW) -> dict:
    cycle = ACTIONS
    seq = [cycle[i % len(cycle)] for i in range(n)]
    rt = restore(snap)
    rt.cognition["prospection"] = pr.empty_store()
    rt.cognition["compression"] = pc.empty_memory()
    rt.cognition["last_fragment"] = None
    rt.cognition["last_action"] = None
    fp0 = _physical_fingerprint(rt)
    for i, act in enumerate(seq):
        pr.learn_transition(
            rt.cognition["prospection"], tick=i + 1,
            antecedent=consequents[act]["antecedent"],
            action=act,
            consequent=consequents[act]["consequent"],
        )
    first = run_free(rt, 1)[0]
    more = run_free(rt, follow - 1)
    free = [first] + more
    return {
        "protocol": "G_mixed",
        "n": n,
        "sequence_prefix": seq[:20],
        "present_identical_before_step": _same_present(fp0, _physical_fingerprint(restore(snap))),
        "first_selected": first["selected"],
        "first_source": first["source"],
        "first_outcome": first["outcome"],
        "first_supported": first["supported_actions"],
        "follow_counts": dict(Counter(r["selected"] for r in free)),
        "follow_entropy": _entropy(Counter(r["selected"] for r in free)),
        "lock": _lock_from_trace(free),
    }


def wipe_history(rt: PhysicalSystemRuntime) -> None:
    rt.cognition["prospection"] = pr.empty_store()
    rt.cognition["compression"] = pc.empty_memory()
    rt.cognition["last_fragment"] = None
    rt.cognition["last_action"] = None
    rt.cognition["metrics"]["action_counts"] = {}


def targeted_remove(rt: PhysicalSystemRuntime, action: str) -> int:
    tr = rt.cognition["prospection"].setdefault("transitions", {})
    keys = [k for k, row in tr.items() if row.get("action") == action]
    for k in keys:
        del tr[k]
    return len(keys)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    print("baseline", flush=True)
    baselines = [baseline_seed(s, 200) for s in BASE_SEEDS]
    (OUT / "BASELINE_RESULTS.json").write_text(json.dumps(baselines, indent=2, default=str), encoding="utf-8")

    donor = PhysicalSystemRuntime(seed=17)
    snap0 = snapshot_clean(donor)
    consequents = {a: consequent_for_action(snap0, a) for a in ACTIONS}

    print("lived biographies", flush=True)
    lived = [lived_biography(17, a, force_n=10, follow=FOLLOW) for a in ACTIONS]
    lived.append(lived_biography(17, "WAIT", force_n=10, follow=FOLLOW))  # explicit
    # mixed lived
    rt = PhysicalSystemRuntime(seed=17)
    for i in range(10):
        rt.step_forced_action(ACTIONS[i % 5])
    mixed_free = run_free(rt, FOLLOW)
    lived.append({
        "protocol": "L_mixed",
        "seed": 17,
        "force_n": 10,
        "free_counts": dict(Counter(r["selected"] for r in mixed_free)),
        "lock": _lock_from_trace(mixed_free),
        "free_selected_head": [r["selected"] for r in mixed_free[:20]],
        "note": "Forced cycle WAIT,N,S,E,W then free. Physics diverged.",
    })

    print("matched present / curve", flush=True)
    matched = []
    curve = []
    for action in ACTIONS:
        for n in CURVE_NS:
            row = matched_graft(snap0, action, n, consequents, follow=FOLLOW)
            matched.append(row)
            curve.append({
                "action": action,
                "n": n,
                "first_selected": row["first_selected"],
                "first_source": row["first_source"],
                "first_outcome": row["first_outcome"],
                "preserves_early_action": row["first_selected"] == action,
                "history_overrides_sampler": row["history_overrides_sampler"],
                "endogenous_would_be": row["endogenous_would_be"],
                "follow_preserve_frac": row["follow_counts"].get(action, 0) / max(1, sum(row["follow_counts"].values())),
                "other_action_appears_at": row["other_action_appears_at"],
                "second_selected": row["second_selected"],
                "competing_n": row["first_competing_n"],
                "entropy": row["follow_entropy"],
                "lock_tick": (row["lock"] or {}).get("lock_tick"),
                "locked_action": (row["lock"] or {}).get("locked_action"),
                "present_identical": row["present_identical_before_step"]["identical_keys_ok"],
            })
    mixed_rows = [mixed_graft(snap0, n, consequents, follow=FOLLOW) for n in (0, 5, 10, 15, 20)]
    (OUT / "MATCHED_PRESENT_RESULTS.json").write_text(
        json.dumps({
            "grafts": matched,
            "mixed": mixed_rows,
            "identity_protocol": "G on seed-17 tick-0 snapshot",
            "reference_present": _physical_fingerprint(restore(snap0)),
            "identical_across_grafts_before_step": (
                "WORLD/BODY/INTERNAL/tick/seed/observation; stores differ by grafted transitions only. "
                "last_action/last_fragment cleared. compression emptied. Hidden RNG state is seed+tick only."
            ),
            "cannot_make_identical": [
                "prospection.transitions / exposure_log / evidence_ticks",
                "after the first free step, MOVE biographies diverge physically; WAIT may remain in-bin",
            ],
        }, indent=2, default=str),
        encoding="utf-8",
    )
    (OUT / "ENTRENCHMENT_CURVE.json").write_text(json.dumps(curve, indent=2, default=str), encoding="utf-8")

    print("ablations + counterfactual", flush=True)
    # lock WAIT with n=10 on matched present, snapshot after graft before free step
    locked = graft_history(snap0, action="WAIT", n=10, consequent=consequents["WAIT"])
    locked_snap = snapshot_clean(locked)
    fp_locked = _physical_fingerprint(locked)

    def branch(name: str, mutate) -> dict:
        rt = restore(locked_snap)
        mutate(rt)
        ident = _same_present(fp_locked, _physical_fingerprint(rt))
        seq = run_free(rt, FOLLOW)
        return {
            "branch": name,
            "present_identical": ident,
            "first": seq[0] if seq else None,
            "counts": dict(Counter(r["selected"] for r in seq)),
            "sources": dict(Counter(r["source"] for r in seq)),
            "lock": _lock_from_trace(seq),
        }

    branches = [
        branch("A_intact", lambda rt: None),
        branch("B_wipe_history", wipe_history),
        branch("D_targeted_remove_WAIT", lambda rt: targeted_remove(rt, "WAIT")),
    ]
    # C: prospection ablation requires config flag + store flag; rebuild from locked snap
    rt_c = restore(locked_snap)
    rt_c.set_ablations(prospective_composition=False)
    seq_c = run_free(rt_c, FOLLOW)
    branches.append({
        "branch": "C_ablate_prospective_composition",
        "present_identical": _same_present(fp_locked, _physical_fingerprint(restore(locked_snap))),
        "first": seq_c[0],
        "counts": dict(Counter(r["selected"] for r in seq_c)),
        "sources": dict(Counter(r["source"] for r in seq_c)),
        "lock": _lock_from_trace(seq_c),
    })
    (OUT / "ABLATION_RESULTS.json").write_text(json.dumps({
        "locked_action": "WAIT",
        "graft_n": 10,
        "lived": lived,
        "branches_at_matched_WAIT10": branches,
        "note": "MOVE:N matched ablations are in COUNTERFACTUAL_RESULTS.json",
    }, indent=2, default=str), encoding="utf-8")
    locked_n = graft_history(snap0, action="MOVE:N", n=10, consequent=consequents["MOVE:N"])
    locked_n_snap = snapshot_clean(locked_n)
    fp_n = _physical_fingerprint(locked_n)

    def branch_n(name: str, mutate) -> dict:
        rt = restore(locked_n_snap)
        mutate(rt)
        ident = _same_present(fp_n, _physical_fingerprint(rt))
        seq = run_free(rt, FOLLOW)
        return {
            "branch": name,
            "present_identical": ident,
            "first": seq[0] if seq else None,
            "counts": dict(Counter(r["selected"] for r in seq)),
            "sources": dict(Counter(r["source"] for r in seq)),
            "lock": _lock_from_trace(seq),
        }

    branches_n = [
        branch_n("A_intact", lambda rt: None),
        branch_n("B_wipe_history", wipe_history),
        branch_n("D_targeted_remove_MOVE_N", lambda rt: targeted_remove(rt, "MOVE:N")),
    ]
    rt_cn = restore(locked_n_snap)
    rt_cn.set_ablations(prospective_composition=False)
    seq_cn = run_free(rt_cn, FOLLOW)
    branches_n.append({
        "branch": "C_ablate_prospective_composition",
        "present_identical": _same_present(fp_n, _physical_fingerprint(restore(locked_n_snap))),
        "first": seq_cn[0],
        "counts": dict(Counter(r["selected"] for r in seq_cn)),
        "sources": dict(Counter(r["source"] for r in seq_cn)),
        "lock": _lock_from_trace(seq_cn),
    })
    (OUT / "COUNTERFACTUAL_RESULTS.json").write_text(json.dumps({
        "from_WAIT10": "seed-17 tick-0 snapshot + WAIT graft n=10",
        "branches_WAIT": branches,
        "from_MOVE_N10": "seed-17 tick-0 snapshot + MOVE:N graft n=10",
        "branches_MOVE_N": branches_n,
    }, indent=2, default=str), encoding="utf-8")

    print("reversal / hysteresis", flush=True)
    reversal = []
    # uncommitted establish B
    for b in ACTIONS:
        need = None
        for n in range(0, 8):
            row = matched_graft(snap0, b, n, consequents, follow=1)
            if row["first_selected"] == b and row["first_source"] == "PROSPECTIVE_SCENARIO":
                need = n
                break
        reversal.append({"kind": "establish_from_uncommitted", "action": b, "min_n_for_prospective_select": need})

    # entrenched WAIT S_A, grow MOVE:N S_B
    hysteresis = []
    for s_a in (3, 10, 20, 50):
        switch_at = None
        series = []
        for s_b in range(0, s_a + 8):
            rt = restore(snap0)
            rt.cognition["prospection"] = pr.empty_store()
            for i in range(s_a):
                pr.learn_transition(
                    rt.cognition["prospection"], tick=i + 1,
                    antecedent=consequents["WAIT"]["antecedent"],
                    action="WAIT", consequent=consequents["WAIT"]["consequent"],
                )
            for i in range(s_b):
                pr.learn_transition(
                    rt.cognition["prospection"], tick=100 + i,
                    antecedent=consequents["MOVE:N"]["antecedent"],
                    action="MOVE:N", consequent=consequents["MOVE:N"]["consequent"],
                )
            first = run_free(rt, 1)[0]
            series.append({
                "S_WAIT": s_a, "S_MOVE_N": s_b,
                "selected": first["selected"], "source": first["source"],
                "outcome": first["outcome"], "supported": first["supported_actions"],
            })
            if switch_at is None and first["selected"] == "MOVE:N":
                switch_at = s_b
        hysteresis.append({
            "entrenched": "WAIT", "S_A": s_a, "challenger": "MOVE:N",
            "switch_at_S_B": switch_at,
            "series": series,
        })
    reverse = []
    for s_a in (3, 10, 20):
        switch_at = None
        series = []
        for s_b in range(0, s_a + 8):
            rt = restore(snap0)
            rt.cognition["prospection"] = pr.empty_store()
            for i in range(s_a):
                pr.learn_transition(
                    rt.cognition["prospection"], tick=i + 1,
                    antecedent=consequents["MOVE:N"]["antecedent"],
                    action="MOVE:N", consequent=consequents["MOVE:N"]["consequent"],
                )
            for i in range(s_b):
                pr.learn_transition(
                    rt.cognition["prospection"], tick=100 + i,
                    antecedent=consequents["WAIT"]["antecedent"],
                    action="WAIT", consequent=consequents["WAIT"]["consequent"],
                )
            first = run_free(rt, 1)[0]
            series.append({
                "S_MOVE_N": s_a, "S_WAIT": s_b,
                "selected": first["selected"], "source": first["source"],
                "outcome": first["outcome"], "supported": first["supported_actions"],
            })
            if switch_at is None and first["selected"] == "WAIT":
                switch_at = s_b
        reverse.append({
            "entrenched": "MOVE:N", "S_A": s_a, "challenger": "WAIT",
            "switch_at_S_B": switch_at,
            "series": series,
        })
    (OUT / "REVERSAL_RESULTS.json").write_text(json.dumps({
        "establish_from_uncommitted": [r for r in reversal],
        "hysteresis_WAIT_vs_MOVE_N": hysteresis,
        "hysteresis_MOVE_N_vs_WAIT": reverse,
        "tie_note": (
            "At equal support/reliability/depth, compete_scenarios returns EXACT_TIE and "
            "resolves by endogenous index over ACTIONS order. Seed 17 tick 0 samples index 0 (WAIT)."
        ),
    }, indent=2, default=str), encoding="utf-8")
    print("done", flush=True)


if __name__ == "__main__":
    main()
