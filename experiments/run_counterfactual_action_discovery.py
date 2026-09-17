#!/usr/bin/env python3
"""Counterfactual opportunity vs action discovery. Ordinary step() only in live runs."""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mechanistic_mind.physical_system import PhysicalSystemRuntime
from mechanistic_mind.physical_system.actions import available_actions
from mechanistic_mind.physical_system.complementary_resources import place_source_AB
from mechanistic_mind.research import predictive_compression as pc
from mechanistic_mind.research import prospective_composition as pr
from mechanistic_mind.physical_system import scenario_competition as sc
from mechanistic_mind.research import instrumental_observation as io

OUT = ROOT / "results" / "mm_counterfactual_action_discovery"
ACTIONS = list(available_actions())
SEEDS = (17, 66667)
PERSIST = 15
AFTER = 80
ALT = "MOVE:E"


def qsig(obs: dict) -> str:
    return pr._sig(pr._q(obs))


def l1(a: dict, b: dict) -> float:
    keys = set(a) | set(b)
    if not keys:
        return 0.0
    return sum(abs(float(a.get(k, 0.0)) - float(b.get(k, 0.0))) for k in keys) / len(keys)


def restore(snap: dict) -> PhysicalSystemRuntime:
    return PhysicalSystemRuntime.restore(deepcopy(snap))


def east_ix(rt: PhysicalSystemRuntime, delta: int = 2) -> int:
    w = int(rt.config.planet.width)
    return (int(rt.body.x) + delta) % w


def place_east_strip(rt: PhysicalSystemRuntime, *, t: float = 0.95, m0: float = 0.55) -> dict:
    w = int(rt.config.planet.width)
    h = int(rt.config.planet.height)
    ix = east_ix(rt, 2)
    for iy in range(h):
        rt.world.T[iy, ix] = t
        rt.world.M[0, iy, ix] = m0
    return {"ix": ix, "T": t, "M0": m0, "width": w, "height": h}


def place_east_R(rt: PhysicalSystemRuntime, amount: float = 3.0) -> dict:
    h = int(rt.config.planet.height)
    ix = east_ix(rt, 2)
    for iy in range(h):
        place_source_AB(rt.world, iy, ix, A=amount, B=0.0)
    return {"ix": ix, "R_A": amount}


def abrupt_under_body(rt: PhysicalSystemRuntime) -> None:
    rt.config.planet.flow_enabled = False
    rt.world.vx[:, :] = -0.55
    rt.world.T[:, :] = 0.20
    rt.world.M[0, :, :] = 0.15
    rt.world.M[1, :, :] = 0.40


def lock_from(rows: list[dict]) -> dict:
    for i, rec in enumerate(rows):
        if rec.get("source") != "PROSPECTIVE_SCENARIO" or rec.get("outcome") != "SINGLE_SUPPORTED":
            continue
        if rec.get("k") != 1:
            continue
        w = rows[i:i + PERSIST]
        if len(w) < PERSIST:
            break
        if all(x.get("action") == rec["action"] and x.get("outcome") == "SINGLE_SUPPORTED" for x in w):
            return {"lock_tick": rec["tick"], "locked_action": rec["action"]}
    return {"lock_tick": None, "locked_action": None}


def pipeline(rt: PhysicalSystemRuntime, incumbent: str | None) -> dict:
    obs = rt.last_agent_observation or rt.agent_observation()
    sel = rt.cognition.get("last_selection") or {}
    comp = sel.get("competition") or {}
    store = rt.cognition["prospection"]
    mem = rt.cognition["compression"]
    observed = {str(r.get("action")) for r in (store.get("transitions") or {}).values()}
    listed = list(comp.get("supported_actions") or [])
    rows = {}
    for act in ACTIONS:
        one = pr.predict_one_step(store, obs, act)
        pred = pc.predict(mem, obs, act, domain="accessible")
        rows[act] = {
            "available": True,
            "historically_observed": act in observed,
            "retrieved": pred.get("status") == "MATCH",
            "composable": one.get("status") == "MATCH",
            "supported": act in listed or one.get("status") == "MATCH",
            "competing": act in listed and len(listed) >= 2,
            "selected": (sel.get("action") or rt.last_selected_action) == act,
            "one_status": one.get("status"),
            "one_support": int(one.get("support") or 0) if one.get("status") == "MATCH" else 0,
        }
    inc = incumbent
    inc_row = rows.get(inc or "", {})
    return {
        "tick": int(rt.tick),
        "action": sel.get("action") or rt.last_selected_action,
        "source": sel.get("source"),
        "outcome": comp.get("outcome_class"),
        "k": len(listed),
        "supported": listed,
        "qsig": qsig(obs) if obs else None,
        "local_T": float(obs.get("local.T", 0.0)) if obs else None,
        "local_M0": float(obs.get("local.M0", 0.0)) if obs else None,
        "body_x": float(rt.body.x),
        "body_y": float(rt.body.y),
        "W": float(getattr(rt.body, "mechanical_work_reservoir", 0.0) or 0.0),
        "incumbent": inc,
        "inc_match": inc_row.get("one_status"),
        "inc_sup": inc_row.get("one_support"),
        "alt": ALT,
        "alt_hist": rows[ALT]["historically_observed"],
        "alt_comp": rows[ALT]["composable"],
        "alt_sup": rows[ALT]["one_support"],
        "alt_sel": rows[ALT]["selected"],
        "stages": rows,
        "pred_n": len(sel.get("prediction_matches") or []),
        "instr": (sel.get("instrumental_prediction") or {}).get("status"),
        "frac": float((rt.last_action_work_ledger or {}).get("action_work_limit_fraction") or 1.0)
        if rt.last_action_work_ledger else None,
    }


def run_until_lock(seed: int) -> tuple[PhysicalSystemRuntime, list[dict], dict]:
    rt = PhysicalSystemRuntime(seed=seed)
    rows = []
    lock = {"lock_tick": None, "locked_action": None}
    for _ in range(80):
        rt.step()
        rec = pipeline(rt, None)
        rows.append(rec)
        lock = lock_from([{**r, "k": r["k"]} for r in rows])
        if lock["lock_tick"] is not None and rec["tick"] >= lock["lock_tick"] + PERSIST - 1:
            break
    inc = lock["locked_action"]
    for r in rows:
        r["incumbent"] = inc
        st = (r.get("stages") or {}).get(inc or "", {})
        r["inc_match"] = st.get("one_status")
        r["inc_sup"] = st.get("one_support")
    return rt, rows, lock


def continue_run(rt, n, incumbent, *, each=None) -> list[dict]:
    out = []
    for _ in range(n):
        if each:
            each(rt)
        rt.step()
        out.append(pipeline(rt, incumbent))
    return out


def diagnostic_futures(snap: dict) -> list[dict]:
    base = restore(snap)
    obs0 = base.agent_observation()
    x0, y0 = float(base.body.x), float(base.body.y)
    rows = []
    for act in ACTIONS:
        for h in (1, 3, 8):
            rt = restore(snap)
            for _ in range(h):
                rt.step_forced_action(act)
            obs = rt.agent_observation()
            rows.append({
                "action": act, "horizon": h,
                "l1_obs": l1(obs0, obs),
                "dx": float(rt.body.x) - x0,
                "dy": float(rt.body.y) - y0,
                "local_T": float(obs.get("local.T", 0.0)),
                "local_M0": float(obs.get("local.M0", 0.0)),
                "body_vx": float(obs.get("body.vx", 0.0)),
                "qsig": qsig(obs),
                "W": float(getattr(rt.body, "mechanical_work_reservoir", 0.0) or 0.0),
            })
    return rows


def agent_distal(rt: PhysicalSystemRuntime) -> dict:
    obs = rt.last_agent_observation or rt.agent_observation()
    store = rt.cognition["prospection"]
    comp = pr.compose_trajectories(store, start=obs, max_depth=3, branch_actions=ACTIONS)
    cont = comp.get("continuations") or []
    by = {}
    for c in cont:
        fa = (c.get("actions") or ["?"])[0]
        by.setdefault(fa, []).append({
            "depth": c.get("depth"),
            "actions": c.get("actions"),
            "rel": c.get("score_reliability"),
        })
    return {
        "max_depth_reached": comp.get("max_depth_reached"),
        "n_continuations": len(cont),
        "first_actions_represented": sorted(by),
        "untried_represented": [a for a in ACTIONS if a not in by],
        "by_first": {k: v[:4] for k, v in by.items()},
    }


def gates(pre: dict, post: list[dict], physics: list[dict], distal: dict, *, mismatch: bool) -> dict:
    inc = pre.get("incumbent")
    match_window = [r for r in post if r.get("inc_match") == "MATCH"]
    fail = next((r["tick"] for r in post if r.get("inc_match") != "MATCH"), None)
    alt_obs = next((r["tick"] for r in match_window if r.get("alt_hist")), None)
    alt_comp = next((r["tick"] for r in match_window if r.get("alt_comp")), None)
    alt_k2 = next((r["tick"] for r in match_window if int(r.get("k") or 0) >= 2), None)
    alt_sel = next((r["tick"] for r in match_window if r.get("action") != inc), None)
    phys_diff = any(p["action"] == ALT and p["horizon"] >= 1 and p["l1_obs"] > 0.02 for p in physics)
    phys_obs = any(p["action"] == ALT and abs(p["local_T"] - physics[0]["local_T"]) > 0.05 for p in physics if p["horizon"] == 8)
    return {
        "G1_physical_alt_future": bool(phys_diff),
        "G2_observable_after_exec": bool(phys_diff),
        "G3_incumbent_remains_supported": (not mismatch) and len(match_window) >= 20 and fail is None,
        "G3_match_ticks": len(match_window),
        "G3_first_fail": fail,
        "G4_alt_observed_before_fail": alt_obs,
        "G5_alt_represented": alt_comp or (ALT in (distal.get("first_actions_represented") or [])),
        "G6_alt_supported": alt_comp,
        "G7_pre_mismatch_competition": alt_k2,
        "G8_selection_change_before_fail": alt_sel,
        "G9_existing_mechanism": False,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    physics_out = []
    distal_out = []
    ambiguity = []
    abl = []
    resource = []
    pipe_rows = []
    traces = []

    def ingest_pipe(run_id, seed, rows):
        for r in rows:
            stages = r.pop("stages", {})
            compact = {a: {k: int(bool(v)) if k in {
                "available", "historically_observed", "retrieved", "composable",
                "supported", "competing", "selected",
            } else v for k, v in (stages.get(a) or {}).items()} for a in ACTIONS}
            pipe_rows.append({"run_id": run_id, "seed": seed, **r, "stages_json": json.dumps(compact, default=str)})

    for seed in SEEDS:
        print("lock", seed, flush=True)
        rt0, rows0, lock = run_until_lock(seed)
        inc = lock["locked_action"]
        if inc is None:
            traces.append({"seed": seed, "lock": lock, "note": "no incumbent"})
            continue
        snap_lock = rt0.snapshot()
        ingest_pipe(f"s{seed}_establish", seed, rows0)

        # B: opportunity while MATCH
        print("  B opportunity", seed, inc, flush=True)
        rt = restore(snap_lock)
        place = place_east_strip(rt)
        snap_opp = rt.snapshot()
        phys = diagnostic_futures(snap_opp)
        dist = agent_distal(rt)
        post = continue_run(rt, AFTER, inc, each=lambda r: place_east_strip(r))
        ingest_pipe(f"s{seed}_B_opp", seed, post)
        g = gates(post[0] if post else {}, post, phys, dist, mismatch=False)
        physics_out.append({"seed": seed, "incumbent": inc, "place": place, "futures": phys, "gates": g})
        distal_out.append({"seed": seed, "incumbent": inc, "agent_composition": dist, "live_first_actions": dist["first_actions_represented"]})
        traces.append({"seed": seed, "cond": "B_opp", "incumbent": inc, "lock": lock, "gates": g,
                       "post_counts": dict(Counter(r["action"] for r in post)),
                       "match_frac": sum(r["inc_match"] == "MATCH" for r in post) / max(1, len(post)),
                       "alt_ever_selected": any(r["action"] == ALT for r in post),
                       "k2": sum(int(r["k"] or 0) >= 2 for r in post)})

        # ambiguity snapshot: continuation multiplicity at opportunity present
        store = restore(snap_opp).cognition["prospection"]
        obs = restore(snap_opp).agent_observation()
        one = {a: pr.predict_one_step(store, obs, a) for a in ACTIONS}
        ambiguity.append({
            "seed": seed, "incumbent": inc, "qsig": qsig(obs),
            "n_match_actions": sum(v.get("status") == "MATCH" for v in one.values()),
            "inc_reliability": one.get(inc, {}).get("reliability"),
            "inc_support": one.get(inc, {}).get("support"),
            "composition": dist,
            "selection_altered": False,
        })

        # A: no opportunity
        rta = restore(snap_lock)
        posta = continue_run(rta, AFTER, inc)
        ingest_pipe(f"s{seed}_A_none", seed, posta)
        traces.append({"seed": seed, "cond": "A_none", "incumbent": inc,
                       "post_counts": dict(Counter(r["action"] for r in posta)),
                       "match_frac": sum(r["inc_match"] == "MATCH" for r in posta) / max(1, len(posta)),
                       "alt_ever_selected": any(r["action"] == ALT for r in posta)})

        # C: abrupt mismatch control
        rtc = restore(snap_lock)
        postc = continue_run(rtc, 40, inc, each=abrupt_under_body)
        ingest_pipe(f"s{seed}_C_mismatch", seed, postc)
        traces.append({"seed": seed, "cond": "C_mismatch", "incumbent": inc,
                       "first_fail": next((r["tick"] for r in postc if r["inc_match"] != "MATCH"), None),
                       "first_other": next((r["tick"] for r in postc if r["action"] != inc), None),
                       "post_counts": dict(Counter(r["action"] for r in postc))})

        # D: R_A strip, not in observation
        rtd = restore(snap_lock)
        place_east_R(rtd)
        snap_d = rtd.snapshot()
        phys_d = diagnostic_futures(snap_d)
        postd = continue_run(rtd, AFTER, inc, each=place_east_R)
        ingest_pipe(f"s{seed}_D_hiddenR", seed, postd)
        traces.append({"seed": seed, "cond": "D_hiddenR", "incumbent": inc,
                       "match_frac": sum(r["inc_match"] == "MATCH" for r in postd) / max(1, len(postd)),
                       "alt_ever_selected": any(r["action"] == ALT for r in postd),
                       "diag_l1_MOVE_E_h8": next((p["l1_obs"] for p in phys_d if p["action"] == ALT and p["horizon"] == 8), None)})

        # E/F/G ablations on opportunity
        def ablate_p(rt_):
            rt_.set_ablations(prospective_composition=False)
            place_east_strip(rt_)

        def ablate_s(rt_):
            rt_.set_mechanism("prospective_scenario_competition", False)
            place_east_strip(rt_)

        def ablate_i(rt_):
            rt_.set_ablations(instrumental_observation=False)
            place_east_strip(rt_)

        for name, fn in (("E_pros", ablate_p), ("F_comp", ablate_s), ("G_instr", ablate_i)):
            rtx = restore(snap_lock)
            postx = continue_run(rtx, AFTER, inc, each=fn)
            ingest_pipe(f"s{seed}_{name}", seed, postx)
            abl.append({
                "seed": seed, "incumbent": inc, "branch": name,
                "first": postx[0] if postx else None,
                "counts": dict(Counter(r["action"] for r in postx)),
                "match_frac": sum(r["inc_match"] == "MATCH" for r in postx) / max(1, len(postx)),
                "alt_selected": any(r["action"] == ALT for r in postx),
                "k2": sum(int(r["k"] or 0) >= 2 for r in postx),
            })

        # H work constraint (especially MOVE incumbents)
        rth = restore(snap_lock)
        rth.body.mechanical_work_reservoir = 0.02
        posth = continue_run(rth, AFTER, inc)
        ingest_pipe(f"s{seed}_H_work", seed, posth)
        resource.append({
            "seed": seed, "incumbent": inc,
            "W_start": 0.02,
            "W_end": posth[-1]["W"] if posth else None,
            "match_frac": sum(r["inc_match"] == "MATCH" for r in posth) / max(1, len(posth)),
            "first_fail": next((r["tick"] for r in posth if r["inc_match"] != "MATCH"), None),
            "first_other": next((r["tick"] for r in posth if r["action"] != inc), None),
            "min_frac": min((r["frac"] for r in posth if r["frac"] is not None), default=None),
            "counts": dict(Counter(r["action"] for r in posth)),
            "alt_selected": any(r["action"] == ALT for r in posth),
        })

    fields = [
        "run_id", "seed", "tick", "action", "source", "outcome", "k", "incumbent",
        "inc_match", "inc_sup", "alt_hist", "alt_comp", "alt_sup", "alt_sel",
        "qsig", "local_T", "body_x", "body_y", "W", "pred_n", "instr", "frac",
    ]
    with (OUT / "ACTION_PIPELINE.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in pipe_rows:
            w.writerow(r)

    (OUT / "COUNTERFACTUAL_PHYSICS.json").write_text(json.dumps(physics_out, indent=2, default=str), encoding="utf-8")
    (OUT / "DISTAL_DIVERGENCE.json").write_text(json.dumps(distal_out, indent=2, default=str), encoding="utf-8")
    (OUT / "AMBIGUITY_RESULTS.json").write_text(json.dumps(ambiguity, indent=2, default=str), encoding="utf-8")
    (OUT / "ABLATION_RESULTS.json").write_text(json.dumps(abl, indent=2, default=str), encoding="utf-8")
    (OUT / "RESOURCE_CONSTRAINT_RESULTS.json").write_text(json.dumps(resource, indent=2, default=str), encoding="utf-8")
    (OUT / "RUN_SUMMARIES.json").write_text(json.dumps(traces, indent=2, default=str), encoding="utf-8")
    print("done", flush=True)


if __name__ == "__main__":
    main()
