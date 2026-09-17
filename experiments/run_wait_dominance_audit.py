#!/usr/bin/env python3
"""Observational WAIT-dominance audit. Does not change CURRENT INTEGRATED MM."""
from __future__ import annotations

import csv
import json
import math
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mechanistic_mind.physical_system import CognitionConfig, PhysicalSystemConfig, PhysicalSystemRuntime
from mechanistic_mind.physical_system.actions import available_actions
from mechanistic_mind.physical_system.runtime import _rng_unit
from mechanistic_mind.research import predictive_compression as pc
from mechanistic_mind.research import prospective_composition as pr
from mechanistic_mind.physical_system import scenario_competition as sc

OUT = ROOT / "results" / "mm_wait_dominance"
ACTIONS = list(available_actions())
SEEDS = (17, 23, 41, 59, 83)
TICKS = 5000
WINDOWS = ((0, 500, "early"), (2000, 2500, "middle"), (4500, 5000, "late"))


def _qsig(obs: dict) -> str:
    return pr._sig(pr._q(obs))


def _csig(obs: dict) -> str:
    return pc._sig(obs)


def _stage_row(rt: PhysicalSystemRuntime, obs: dict) -> dict[str, dict]:
    store = rt.cognition["prospection"]
    mem = rt.cognition["compression"]
    sel = rt.cognition.get("last_selection") or {}
    groups = sel.get("scenario_groups") or {}
    comp = sel.get("competition") or {}
    selected = sel.get("action")
    competing = set(comp.get("supported_actions") or [])
    unsupported = set(comp.get("unsupported_actions") or [])
    observed = {str(r.get("action")) for r in (store.get("transitions") or {}).values()}
    rows = {}
    for act in ACTIONS:
        one = pr.predict_one_step(store, obs, act)
        pred = pc.predict(mem, obs, act, domain="accessible")
        tr_key = pr.transition_key(pr._q(obs), act)
        tr = (store.get("transitions") or {}).get(tr_key)
        g = groups.get(act) or {}
        rows[act] = {
            "available": True,
            "observed": act in observed,
            "transition_support": int((tr or {}).get("support") or 0),
            "retrieved": pred.get("status") == "MATCH",
            "compression_status": pred.get("status"),
            "composable": one.get("status") == "MATCH",
            "one_step_status": one.get("status"),
            "one_step_support": one.get("support"),
            "one_step_reliability": one.get("reliability"),
            "supported": bool(g.get("supported") or g.get("count") or g.get("scenarios")),
            "scenario_count": int(g.get("count") or 0),
            "competing": act in competing,
            "unsupported_listed": act in unsupported,
            "selected": act == selected,
            "rejection": None,
        }
    for cand in sel.get("competition", {}).get("candidates_considered") or []:
        pass
    receipt = rt.cognition.get("last_decision_receipt") or {}
    for c in receipt.get("candidates") or []:
        a = c.get("candidate")
        if a in rows:
            rows[a]["rejection"] = c.get("rejection_reason")
    return rows


def _compact_receipt(rt: PhysicalSystemRuntime, body_before: dict, tick: int) -> dict:
    sel = rt.cognition.get("last_selection") or {}
    obs = rt.last_agent_observation or {}
    aw = rt.last_action_work_ledger or {}
    alloc = rt.last_work_allocation or {}
    mw = rt.last_motor_work_ledger or {}
    dw = rt.last_work_ledger or {}
    stages = _stage_row(rt, obs)
    selected = sel.get("action")
    win = (sel.get("competition") or {}).get("selected_scenario") or {}
    dx = float(rt.body.x) - float(body_before.get("x", rt.body.x))
    dy = float(rt.body.y) - float(body_before.get("y", rt.body.y))
    dvx = float(rt.body.vx) - float(body_before.get("vx", 0.0))
    dvy = float(rt.body.vy) - float(body_before.get("vy", 0.0))
    req = aw.get("action_dv_requested") or [0.0, 0.0]
    real = aw.get("action_dv_realized") or [0.0, 0.0]
    force = rt.last_force_contributions or {}
    return {
        "t": tick,
        "sel": selected,
        "src": sel.get("source"),
        "rule": sel.get("selection_rule"),
        "out": (sel.get("competition") or {}).get("outcome_class"),
        "qsig": _qsig(obs) if obs else None,
        "csig": _csig(obs) if obs else None,
        "pred_n": len(sel.get("prediction_matches") or []),
        "cont_n": len(sel.get("continuations") or []),
        "metrics": {
            "pc": rt.cognition["metrics"].get("prediction_count"),
            "pe": rt.cognition["metrics"].get("prediction_error_sum"),
            "pr": rt.cognition["metrics"].get("prospective_compositions"),
            "nov": rt.cognition["metrics"].get("novel_compositions"),
            "ia": rt.cognition["metrics"].get("instrumental_acquired"),
        },
        "hs": win.get("historical_support"),
        "rel": win.get("reliability"),
        "dep": win.get("depth"),
        "stages": {a: {
            "o": int(s["observed"]), "r": int(s["retrieved"]), "c": int(s["composable"]),
            "s": int(s["supported"]), "k": int(s["competing"]), "w": int(s["selected"]),
            "sup": s["transition_support"], "rej": s["rejection"],
        } for a, s in stages.items()},
        "dv_req": [float(req[0]), float(req[1])],
        "dv_real": [float(real[0]), float(real[1])],
        "dx": dx, "dy": dy, "disp": math.hypot(dx, dy),
        "dv": math.hypot(dvx, dvy),
        "x": float(rt.body.x), "y": float(rt.body.y),
        "th": float(getattr(rt.body, "theta", 0.0) or 0.0),
        "om": float(getattr(rt.body, "omega", 0.0) or 0.0),
        "vx": float(rt.body.vx), "vy": float(rt.body.vy),
        "W": float(getattr(rt.body, "mechanical_work_reservoir", 0.0) or 0.0),
        "w_act_req": float(alloc.get("requested_action") or 0.0),
        "w_act_all": float(alloc.get("allocated_action") or 0.0),
        "w_mot_req": float(alloc.get("requested_motor") or 0.0),
        "w_mot_all": float(alloc.get("allocated_motor") or 0.0),
        "w_def_req": float(alloc.get("requested_deformation") or 0.0),
        "w_def_all": float(alloc.get("allocated_deformation") or 0.0),
        "w_act_real": float(aw.get("action_work_realized") or 0.0),
        "w_mot_real": float(mw.get("motor_work_realized") or mw.get("work_realized") or 0.0),
        "w_def_real": float(dw.get("deformation_work_realized") or dw.get("work_realized") or 0.0),
        "RA": float(getattr(rt.body, "R_A_site", 0.0).sum()) if getattr(rt.body, "R_A_site", None) is not None else 0.0,
        "RB": float(getattr(rt.body, "R_B_site", 0.0).sum()) if getattr(rt.body, "R_B_site", None) is not None else 0.0,
        "env_fx": (force.get("environment") or force.get("env") or [None])[0] if isinstance(force.get("environment") or force.get("env"), (list, tuple)) else force.get("environment"),
    }


def _transition_census(rt: PhysicalSystemRuntime) -> dict:
    rows = []
    for key, row in (rt.cognition["prospection"].get("transitions") or {}).items():
        rows.append({
            "key": key,
            "action": row.get("action"),
            "support": int(row.get("support") or 0),
            "usable": int(row.get("support") or 0) >= 3,
            "reliability": pr.reliability(row),
        })
    by_act = Counter(r["action"] for r in rows)
    usable = Counter(r["action"] for r in rows if r["usable"])
    return {"n": len(rows), "by_action": dict(by_act), "usable_by_action": dict(usable), "rows": rows}


def run_seed(seed: int, ticks: int, *, config: PhysicalSystemConfig | None = None, label: str = "baseline") -> dict:
    rt = PhysicalSystemRuntime(seed=seed, config=config)
    trace_path = OUT / f"DECISION_TRACE_s{seed}_{label}.jsonl"
    work_rows = []
    stage_counts = {a: Counter() for a in ACTIONS}
    hist_dyn = []
    first_actions_sel = Counter()
    retrieve_hits = Counter()
    compose_hits = Counter()
    support_hits = Counter()
    compete_hits = Counter()
    t0 = time.perf_counter()
    with trace_path.open("w", encoding="utf-8") as fh:
        for i in range(ticks):
            before = {
                "x": float(rt.body.x), "y": float(rt.body.y),
                "vx": float(rt.body.vx), "vy": float(rt.body.vy),
                "theta": float(getattr(rt.body, "theta", 0.0) or 0.0),
                "W": float(getattr(rt.body, "mechanical_work_reservoir", 0.0) or 0.0),
            }
            rt.step(1)
            rec = _compact_receipt(rt, before, i)
            fh.write(json.dumps(rec, separators=(",", ":")) + "\n")
            first_actions_sel[rec["sel"]] += 1
            for a, st in rec["stages"].items():
                if st["r"]:
                    retrieve_hits[a] += 1
                if st["c"]:
                    compose_hits[a] += 1
                if st["s"]:
                    support_hits[a] += 1
                if st["k"]:
                    compete_hits[a] += 1
                for flag, name in (("o", "observed"), ("r", "retrieved"), ("c", "composable"),
                                   ("s", "supported"), ("k", "competing"), ("w", "selected")):
                    if st[flag]:
                        stage_counts[a][name] += 1
                stage_counts[a]["available"] += 1
            work_rows.append({
                "seed": seed, "label": label, "tick": i, "sel": rec["sel"],
                "W": rec["W"],
                "w_act_req": rec["w_act_req"], "w_act_all": rec["w_act_all"], "w_act_real": rec["w_act_real"],
                "w_mot_req": rec["w_mot_req"], "w_mot_all": rec["w_mot_all"], "w_mot_real": rec["w_mot_real"],
                "w_def_req": rec["w_def_req"], "w_def_all": rec["w_def_all"], "w_def_real": rec["w_def_real"],
                "RA": rec["RA"], "RB": rec["RB"], "disp": rec["disp"],
                "dv_req": math.hypot(*rec["dv_req"]), "dv_real": math.hypot(*rec["dv_real"]),
            })
            if i in {0, 2, 9, 49, 199, 499, 999, 2499, ticks - 1} or i % 250 == 0:
                census = _transition_census(rt)
                hist_dyn.append({
                    "seed": seed, "label": label, "tick": i,
                    "selected": rec["sel"],
                    "metrics": rec["metrics"],
                    "transitions": census["by_action"],
                    "usable": census["usable_by_action"],
                    "W": rec["W"],
                })
    elapsed = time.perf_counter() - t0
    return {
        "seed": seed, "label": label, "ticks": ticks, "seconds": elapsed,
        "action_counts": dict(first_actions_sel),
        "retrieve_hits": dict(retrieve_hits),
        "compose_hits": dict(compose_hits),
        "support_hits": dict(support_hits),
        "compete_hits": dict(compete_hits),
        "stage_counts": {a: dict(c) for a, c in stage_counts.items()},
        "metrics_end": dict(rt.cognition["metrics"]),
        "first_tick_rng": _rng_unit(seed, 0),
        "first_tick_index": min(len(ACTIONS) - 1, int(_rng_unit(seed, 0) * len(ACTIONS))),
        "first_tick_endogenous": ACTIONS[min(len(ACTIONS) - 1, int(_rng_unit(seed, 0) * len(ACTIONS)))],
        "trace": str(trace_path),
        "work_rows": work_rows,
        "hist_dyn": hist_dyn,
        "census_end": _transition_census(rt),
        "runtime": rt,
    }


def window_stats(path: Path, start: int, end: int) -> dict:
    n = 0
    wait = 0
    move = 0
    disp = 0.0
    rot = 0.0
    by = Counter()
    support_ticks = Counter()
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            t = rec["t"]
            if t < start or t >= end:
                continue
            n += 1
            by[rec["sel"]] += 1
            if rec["sel"] == "WAIT":
                wait += 1
            elif str(rec["sel"]).startswith("MOVE"):
                move += 1
            disp += float(rec.get("disp") or 0.0)
            rot += abs(float(rec.get("om") or 0.0))
            for a, st in rec["stages"].items():
                if st["s"]:
                    support_ticks[a] += 1
    return {
        "n": n, "wait_frac": wait / max(1, n), "move_frac": move / max(1, n),
        "counts": dict(by), "mean_disp": disp / max(1, n), "mean_abs_omega": rot / max(1, n),
        "support_frac": {a: support_ticks[a] / max(1, n) for a in ACTIONS},
    }


def write_csv(path: Path, rows: list[dict], fieldnames: list[str] | None = None) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = fieldnames or list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def ablation_run(seed: int, ticks: int, **cog_flags) -> dict:
    cog = CognitionConfig(**{**CognitionConfig().to_dict(), **cog_flags})
    cfg = PhysicalSystemConfig(cognition=cog)
    return run_seed(seed, ticks, config=cfg, label="abl_" + "_".join(f"{k}-{int(v)}" for k, v in cog_flags.items()))


def matched_history_probe(seed: int, learn_ticks: int = 80, probe_ticks: int = 20) -> dict:
    """Same later physical fork is not constructed; instead compare wiped vs intact stores at a snapshot."""
    base = run_seed(seed, learn_ticks, label=f"hist_learn_{learn_ticks}")
    rt = base.pop("runtime")
    snap = rt.snapshot()
    intact_sel = []
    wiped_sel = []
    # intact continuation
    rt_i = PhysicalSystemRuntime.restore(snap)
    for _ in range(probe_ticks):
        rt_i.step(1)
        intact_sel.append(rt_i.last_selected_action)
    # wipe prospection + compression, keep body/world
    rt_w = PhysicalSystemRuntime.restore(snap)
    rt_w.cognition["prospection"] = pr.empty_store()
    rt_w.cognition["compression"] = pc.empty_memory()
    rt_w.cognition["last_fragment"] = None
    rt_w.cognition["last_action"] = None
    rt_w.cognition["metrics"] = {
        **rt_w.cognition["metrics"],
        "prediction_count": 0, "prospective_compositions": 0, "prediction_error_sum": 0.0,
        "novel_compositions": 0, "action_counts": {},
    }
    for _ in range(probe_ticks):
        rt_w.step(1)
        wiped_sel.append(rt_w.last_selected_action)
    return {
        "seed": seed,
        "learn_ticks": learn_ticks,
        "probe_ticks": probe_ticks,
        "intact_actions": intact_sel,
        "wiped_actions": wiped_sel,
        "intact_wait_frac": sum(1 for a in intact_sel if a == "WAIT") / max(1, len(intact_sel)),
        "wiped_wait_frac": sum(1 for a in wiped_sel if a == "WAIT") / max(1, len(wiped_sel)),
        "different": intact_sel != wiped_sel,
        "note": (
            "Same restored WORLD/BODY/INTERNAL snapshot; wiped run clears prospection+compression "
            "and last_fragment so the next decisions cannot use retained WAIT transitions. "
            "Not a bit-identical present observation after tick 1 of the probe, because WAIT vs "
            "endogenous MOVE changes subsequent physics. Tick-0 of the probe shares the snapshot."
        ),
        "first_probe_intact": intact_sel[0] if intact_sel else None,
        "first_probe_wiped": wiped_sel[0] if wiped_sel else None,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    summaries = []
    hist_rows = []
    work_all = []
    stage_rows = []

    print(f"baseline seeds={SEEDS} ticks={TICKS}", flush=True)
    results = []
    for seed in SEEDS:
        print(f"  seed {seed} ...", flush=True)
        res = run_seed(seed, TICKS, label="baseline")
        rt = res.pop("runtime")
        del rt
        results.append(res)
        print(f"    {res['seconds']:.1f}s counts={res['action_counts']} pc={res['metrics_end'].get('prediction_count')} pr={res['metrics_end'].get('prospective_compositions')}", flush=True)

    for res in results:
        seed = res["seed"]
        for act, counts in res["stage_counts"].items():
            stage_rows.append({"seed": seed, "action": act, **{k: counts.get(k, 0) for k in
                ("available", "observed", "retrieved", "composable", "supported", "competing", "selected")}})
        work_all.extend(res["work_rows"])
        hist_rows.extend(res["hist_dyn"])
        path = Path(res["trace"])
        win = {name: window_stats(path, a, b) for a, b, name in WINDOWS}
        summaries.append({
            "seed": seed,
            "first_endogenous": res["first_tick_endogenous"],
            "first_rng": res["first_tick_rng"],
            "action_counts": res["action_counts"],
            "metrics_end": res["metrics_end"],
            "retrieve_hits": res["retrieve_hits"],
            "compose_hits": res["compose_hits"],
            "support_hits": res["support_hits"],
            "compete_hits": res["compete_hits"],
            "usable_transitions": res["census_end"]["usable_by_action"],
            "all_transitions": res["census_end"]["by_action"],
            "windows": win,
            "seconds": res["seconds"],
        })

    write_csv(OUT / "ACTION_STAGE_MATRIX.csv", stage_rows)
    write_csv(OUT / "HISTORY_DYNAMICS.csv", [
        {
            "seed": h["seed"], "tick": h["tick"], "selected": h["selected"],
            "prediction_count": (h["metrics"] or {}).get("pc"),
            "prospective_compositions": (h["metrics"] or {}).get("pr"),
            "trans_WAIT": (h["transitions"] or {}).get("WAIT", 0),
            "trans_MOVE": sum(v for k, v in (h["transitions"] or {}).items() if str(k).startswith("MOVE")),
            "usable_WAIT": (h["usable"] or {}).get("WAIT", 0),
            "usable_MOVE": sum(v for k, v in (h["usable"] or {}).items() if str(k).startswith("MOVE")),
            "W": h.get("W"),
        }
        for h in hist_rows
    ])
    write_csv(OUT / "WORK_ACCOUNTING.csv", work_all)
    (OUT / "BASELINE_SUMMARY.json").write_text(json.dumps(summaries, indent=2, default=str), encoding="utf-8")

    # Concatenate compact traces into one file pointer list (keep per-seed files; also index)
    index = [{"seed": r["seed"], "path": r["trace"], "ticks": r["ticks"]} for r in results]
    (OUT / "DECISION_TRACE.jsonl").write_text(
        json.dumps({"schema": "mm.wait_dominance.trace_index.v1", "files": index}) + "\n",
        encoding="utf-8",
    )

    print("ablations seed=17 ticks=1500", flush=True)
    abl = []
    for flags in (
        {"retrieval": False},
        {"prospective_composition": False},
        {"bounded_memory": False},
        {"prospective_selection": "LEGACY_FIRST"},
    ):
        print(f"  {flags}", flush=True)
        if "prospective_selection" in flags:
            cog = CognitionConfig(prospective_selection="LEGACY_FIRST")
            cfg = PhysicalSystemConfig(cognition=cog)
            r = run_seed(17, 1500, config=cfg, label="abl_legacy_first")
        else:
            r = ablation_run(17, 1500, **flags)
        r.pop("runtime", None)
        abl.append({
            "flags": flags,
            "action_counts": r["action_counts"],
            "metrics_end": r["metrics_end"],
            "stage_counts": r["stage_counts"],
            "usable": r["census_end"]["usable_by_action"],
            "seconds": r["seconds"],
        })
    print("matched-history probe", flush=True)
    hist_probe = [matched_history_probe(s) for s in SEEDS]
    (OUT / "ABLATION_RAW.json").write_text(json.dumps({"ablations": abl, "history_probe": hist_probe}, indent=2, default=str), encoding="utf-8")
    print("done", flush=True)


if __name__ == "__main__":
    main()
