#!/usr/bin/env python3
"""Physical signal bridge experiments. Ordinary physics → ordinary learning. No social semantics."""
from __future__ import annotations

import csv
import json
import sys
import time
from copy import deepcopy
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mechanistic_mind.physical_system import PhysicalSystemRuntime, TwoAgentRuntime, available_actions
from mechanistic_mind.physical_system.actions import BRIDGE_MISSING
from mechanistic_mind.physical_system.cognition import empty_cognitive_state
from mechanistic_mind.research import predictive_compression as pc
from mechanistic_mind.research import prospective_composition as pr

OUT = ROOT / "results" / "mm_two_agent_physical_signals"
SEEDS = (17, 23, 41)
DISTANCES = (1, 2, 4, 8, 12)
DELAY = 3
TRIALS = 12
RELAX = 4


def _json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n")


def make_ta(seed, starts, **kw) -> TwoAgentRuntime:
    kw.setdefault("contact_enabled", False)
    kw.setdefault("field_coupling_enabled", False)
    kw.setdefault("signal_enabled", True)
    return TwoAgentRuntime(seed=int(seed), starts=starts, **kw)


def freeze_bodies(ta: TwoAgentRuntime) -> None:
    for rt in ta.slots:
        rt.body.vx = 0.0
        rt.body.vy = 0.0


def bump_T(ta: TwoAgentRuntime, slot: int, amp: float = 0.20) -> float:
    h, w = ta.world.T.shape
    iy, ix = ta.slots[slot].body.cell(w, h)
    before = float(ta.world.T[iy, ix])
    ta.world.T[iy, ix] = float(np.clip(before + amp, 0.0, 1.0))
    return float(ta.world.T[iy, ix])


def pred_T(rt, obs) -> dict:
    p = pc.predict(rt.cognition["compression"], obs, "WAIT", domain="accessible")
    pred = p.get("predicted") or {}
    return {
        "status": p.get("status"),
        "support": p.get("support"),
        "pred_T": float(pred.get("local.T") or 0.0),
        "pred_FA": float(pred.get("local.FIELD_A") or 0.0),
    }


def compose_first(rt, obs) -> dict:
    comp = pr.compose_trajectories(
        rt.cognition["prospection"],
        start=obs,
        max_depth=2,
        branch_actions=list(available_actions()),
    )
    conts = list(comp.get("continuations") or [])
    wait = [c for c in conts if (c.get("actions") or [None])[0] == "WAIT"]
    row = wait[0] if wait else (conts[0] if conts else {})
    states = row.get("states") or []
    nxt = states[1] if len(states) > 1 else {}
    return {
        "n": len(conts),
        "wait_n": len(wait),
        "first_action": (row.get("actions") or [None])[0],
        "next_T": float((nxt or {}).get("local.T") or 0.0),
        "next_FA": float((nxt or {}).get("local.FIELD_A") or 0.0),
    }


def run_transmission() -> tuple[dict, list[dict]]:
    rows = []
    dist_csv = []
    for seed in SEEDS:
        for dist in DISTANCES:
            for amp in (0.45, 1.0):
                for direction in ("A_to_B", "B_to_A"):
                    x0, x1 = 8.0, 8.0 + dist
                    starts = ((x0, 16.0), (x1, 16.0))
                    src, dst = (0, 1) if direction == "A_to_B" else (1, 0)
                    ta = make_ta(seed, starts)
                    freeze_bodies(ta)
                    ta.inject_source(slot=src, channel="A", amplitude=amp, trigger="experimenter_forced_source")
                    series = []
                    first = None
                    for t in range(10):
                        ta.step(1)
                        freeze_bodies(ta)
                        obs = ta.slots[dst].agent_observation()
                        rec_amp = float(obs.get("local.FIELD_A") or 0.0)
                        if first is None and rec_amp > 1e-4:
                            first = t + 1
                        series.append({
                            "tick": t + 1,
                            "world_max": float(ta.world.FIELD_A.max()),
                            "receiver": rec_amp,
                            "sender": float(ta.slots[src].agent_observation().get("local.FIELD_A") or 0),
                        })
                    peak = max(series, key=lambda r: r["receiver"])
                    rows.append({
                        "seed": seed, "distance": dist, "amplitude": amp, "direction": direction,
                        "first_receiver_tick": first,
                        "peak_receiver": peak["receiver"],
                        "peak_tick": peak["tick"],
                        "final_world_max": series[-1]["world_max"],
                        "leaks": [],
                    })
                    dist_csv.append({
                        "seed": seed, "distance": dist, "amplitude": amp, "direction": direction,
                        "first_tick": first if first is not None else "",
                        "peak_receiver": peak["receiver"],
                        "peak_world": peak["world_max"],
                    })
                    blob = repr(ta.slots[dst].agent_observation())
                    assert "agent_0" not in blob and "agent_1" not in blob
    return {
        "delay_rule": "emit end of t, observe at t+1 capture / live agent_observation after step",
        "physics": "source cells only; decay+4-neighbor spread; no teleport",
        "rows": rows,
        "any_distance_effect": (
            max(r["peak_receiver"] for r in rows if r["distance"] == 1)
            > max(r["peak_receiver"] for r in rows if r["distance"] == 12)
        ),
        "emit_in_available_actions": "EMIT" in available_actions(),
        "bridge_missing_emit": "EMIT" in BRIDGE_MISSING,
    }, dist_csv


def run_ablation() -> dict:
    rows = []
    for seed in SEEDS:
        s1 = make_ta(seed, ((10, 16), (12, 16)))
        s0 = make_ta(seed, ((10, 16), (12, 16)), signal_enabled=False)
        s1.inject_source(slot=0, channel="A", amplitude=1.0, trigger="experimenter_forced_source")
        s0.inject_source(slot=0, channel="A", amplitude=1.0, trigger="experimenter_forced_source")
        s1.step(4)
        s0.step(4)
        obs1 = s1.slots[1].agent_observation()
        obs0 = s0.slots[1].agent_observation()
        em = make_ta(seed, ((10, 16), (10, 16)))
        em.slots[0].config.physical_signal.emission_enabled = False
        em.slots[1].config.physical_signal.emission_enabled = False
        em.slots[0].body.vx = 0.25
        em.step(1)
        prp = make_ta(seed, ((10, 16), (16, 16)))
        prp.slots[0].config.physical_signal.propagation_enabled = False
        prp.slots[1].config.physical_signal.propagation_enabled = False
        prp.inject_source(slot=0, channel="A", amplitude=1.0, trigger="experimenter_forced_source")
        prp.step(8)
        perc = make_ta(seed, ((10, 16), (10, 16)))
        perc.slots[0].config.physical_signal.perception_enabled = False
        perc.slots[1].config.physical_signal.perception_enabled = False
        perc.inject_source(slot=0, channel="A", amplitude=1.0, trigger="experimenter_forced_source")
        perc.step(1)
        rows.append({
            "seed": seed,
            "S1_receiver_FA": float(obs1.get("local.FIELD_A") or 0),
            "S0_has_FA_key": "local.FIELD_A" in obs0,
            "S0_world_field": getattr(s0.world, "FIELD_A", None) is not None,
            "emission_off_world_max": float(em.world.FIELD_A.max()) if em.world.FIELD_A is not None else 0.0,
            "prop_off_far_receiver": float(prp.slots[1].agent_observation().get("local.FIELD_A") or 0),
            "perc_off_key_absent": "local.FIELD_A" not in perc.slots[1].agent_observation(),
            "perc_off_world_max": float(perc.world.FIELD_A.max()),
        })
    return {
        "rows": rows,
        "S0_vs_S1_attributable": all((not r["S0_has_FA_key"]) and r["S1_receiver_FA"] > 0 for r in rows),
        "independent_ablations": {
            "emission": "body motion blocked; extra_sources still physical",
            "propagation": "no neighbor spread; far receiver ~0",
            "perception": "field exists, observation keys omitted",
        },
    }


def protocol(ta: TwoAgentRuntime, *, correlated: bool, trials: int, rng: np.random.Generator) -> None:
    freeze_bodies(ta)
    delays = [DELAY] * trials
    if not correlated:
        delays = list(rng.integers(0, DELAY + RELAX + 2, size=trials))
    for d in delays:
        ta.inject_source(slot=0, channel="A", amplitude=1.0, trigger="experimenter_forced_source")
        ta.step(max(1, int(d)))
        freeze_bodies(ta)
        if correlated:
            bump_T(ta, 1, 0.22)
        elif rng.random() < 0.5:
            bump_T(ta, 1, 0.22)
        ta.step(1)
        freeze_bodies(ta)
        ta.step(RELAX)
        freeze_bodies(ta)
        if not correlated:
            bump_T(ta, 1, 0.22)
            ta.step(1)
            freeze_bodies(ta)


def probe(ta: TwoAgentRuntime) -> dict:
    freeze_bodies(ta)
    ta.inject_source(slot=0, channel="A", amplitude=1.0, trigger="experimenter_forced_source")
    ta.step(DELAY)
    freeze_bodies(ta)
    obs_sig = ta.slots[1].agent_observation()
    sel = ta.slots[1].last_selected_action
    src = (ta.slots[1].cognition.get("last_selection") or {}).get("source")
    supported = list(((ta.slots[1].cognition.get("last_selection") or {}).get("competition") or {}).get("supported_actions") or [])
    p = pred_T(ta.slots[1], obs_sig)
    c = compose_first(ta.slots[1], obs_sig)
    hist = ta.slots[1].cognition["compression"]
    n_struct = len(hist.get("structures") or {})
    field_in_raw = any("local.FIELD_A" in (hist.get("raw_log") or {}).get(k, {}).get("fragment") or {}
                       for k in list((hist.get("raw_log") or {}))[:5])
    recent = hist.get("recent") or []
    # structures store mean_predicted; scan for FIELD in antecedent snapshots if present
    field_in_struct = False
    for row in (hist.get("structures") or {}).values():
        mp = row.get("mean_predicted") or {}
        ant = row.get("antecedent") or row.get("fragment") or {}
        if "local.FIELD_A" in mp or "local.FIELD_A" in ant:
            field_in_struct = True
            break
    return {
        "obs_FA": float(obs_sig.get("local.FIELD_A") or 0),
        "obs_T": float(obs_sig.get("local.T") or 0),
        "selected": sel,
        "source": src,
        "supported": supported,
        "prediction": p,
        "prospection": c,
        "n_structures": n_struct,
        "recent_n": len(recent),
        "field_in_structure_scan": field_in_struct,
        "keys": sorted(obs_sig),
    }


def run_learning() -> tuple[dict, dict, dict, dict]:
    traces = []
    deco = []
    pred_rows = []
    beh = []
    for seed in SEEDS:
        rng = np.random.default_rng(seed)
        corr = make_ta(seed, ((10.0, 16.0), (12.0, 16.0)))
        dec = make_ta(seed, ((10.0, 16.0), (12.0, 16.0)))
        protocol(corr, correlated=True, trials=TRIALS, rng=rng)
        protocol(dec, correlated=False, trials=TRIALS, rng=rng)
        pc_corr = probe(corr)
        pc_dec = probe(dec)
        traces.append({"seed": seed, "correlated_probe": pc_corr, "note": "signal X then T bump after DELAY"})
        deco.append({"seed": seed, "decorrelated_probe": pc_dec})
        pred_rows.append({
            "seed": seed,
            "corr_status": pc_corr["prediction"]["status"],
            "corr_pred_T": pc_corr["prediction"]["pred_T"],
            "corr_support": pc_corr["prediction"]["support"],
            "dec_status": pc_dec["prediction"]["status"],
            "dec_pred_T": pc_dec["prediction"]["pred_T"],
            "dec_support": pc_dec["prediction"]["support"],
            "pred_T_corr_minus_dec": pc_corr["prediction"]["pred_T"] - pc_dec["prediction"]["pred_T"],
            "corr_prospection_next_T": pc_corr["prospection"]["next_T"],
            "dec_prospection_next_T": pc_dec["prospection"]["next_T"],
        })
        beh.append({
            "seed": seed,
            "corr_action": pc_corr["selected"],
            "dec_action": pc_dec["selected"],
            "corr_source": pc_corr["source"],
            "dec_source": pc_dec["source"],
            "action_differs": pc_corr["selected"] != pc_dec["selected"],
        })
        # incumbent: WAIT lock then protocol
        inc = make_ta(seed, ((10.0, 16.0), (12.0, 16.0)))
        inc.step(30)
        lock_action = inc.slots[1].last_selected_action
        lock_src = (inc.slots[1].cognition.get("last_selection") or {}).get("source")
        protocol(inc, correlated=True, trials=6, rng=rng)
        after = probe(inc)
        beh[-1]["incumbent_pre_action"] = lock_action
        beh[-1]["incumbent_pre_source"] = lock_src
        beh[-1]["incumbent_post_action"] = after["selected"]
        beh[-1]["incumbent_post_source"] = after["source"]
        beh[-1]["incumbent_post_supported"] = after["supported"]
        beh[-1]["incumbent_pred"] = after["prediction"]
    learned = any(r["corr_status"] == "MATCH" and r["pred_T_corr_minus_dec"] > 0.01 for r in pred_rows)
    action_changed = any(r["action_differs"] for r in beh)
    return (
        {"trials": TRIALS, "delay": DELAY, "consequence": "local T bump at receiver cell", "rows": traces,
         "signal_enters_observation": True},
        {"rows": deco, "same_signal_and_T_counts": "approximately; timing shuffled"},
        {"rows": pred_rows, "signal_dependent_prediction": learned},
        {"rows": beh, "signal_dependent_action": action_changed,
         "note": "Do not treat ENDOGENOUS_VARIATION on a novel fragment as learned meaning."},
    )


def run_source_control() -> dict:
    rows = []
    for seed in SEEDS:
        ag = make_ta(seed, ((10, 16), (10, 16)))
        env = make_ta(seed, ((10, 16), (10, 16)))
        ag.slots[0].config.physical_signal.emission_enabled = False
        env.slots[0].config.physical_signal.emission_enabled = False
        ag.inject_source(slot=0, channel="A", amplitude=0.8, trigger="experimenter_forced_source")
        env.inject_source(iy=16, ix=10, channel="A", amplitude=0.8, trigger="environmental")
        ag.step(1)
        env.step(1)
        oa = ag.slots[1].agent_observation()
        oe = env.slots[1].agent_observation()
        rows.append({
            "seed": seed,
            "keys_equal": sorted(oa) == sorted(oe),
            "d_FA": abs(float(oa.get("local.FIELD_A") or 0) - float(oe.get("local.FIELD_A") or 0)),
            "identity_in_obs": ("agent_0" in repr(oa)) or ("environment" in repr(oe)),
        })
    return {"rows": rows, "source_agnostic": all(r["keys_equal"] and not r["identity_in_obs"] and r["d_FA"] < 0.1 for r in rows)}


def run_bidirectional() -> dict:
    rows = []
    for seed in SEEDS:
        ta = make_ta(seed, ((10, 16), (13, 16)))
        ta.inject_source(slot=0, channel="A", amplitude=1.0, trigger="experimenter_forced_source")
        ta.step(5)
        b_from_a = float(ta.slots[1].agent_observation().get("local.FIELD_A") or 0)
        ta.inject_source(slot=1, channel="A", amplitude=1.0, trigger="experimenter_forced_source")
        ta.step(5)
        a_from_b = float(ta.slots[0].agent_observation().get("local.FIELD_A") or 0)
        rows.append({"seed": seed, "B_sees_A": b_from_a, "A_sees_B": a_from_b})
    return {"rows": rows, "bidirectional": all(r["B_sees_A"] > 0 and r["A_sees_B"] > 0 for r in rows),
            "note": "Not dialogue. Both can deposit into the same FIELD_A."}


def run_history() -> dict:
    rows = []
    for seed in SEEDS:
        ta = make_ta(seed, ((10, 16), (12, 16)))
        protocol(ta, correlated=True, trials=TRIALS, rng=np.random.default_rng(seed))
        keep = deepcopy(ta.snapshot())
        hist = TwoAgentRuntime.restore(deepcopy(keep))
        wipe = TwoAgentRuntime.restore(deepcopy(keep))
        wipe.slots[1].cognition = empty_cognitive_state(wipe.slots[1].config.cognition)
        ph = probe(hist)
        pw = probe(wipe)
        rows.append({
            "seed": seed,
            "kept_pred": ph["prediction"],
            "wiped_pred": pw["prediction"],
            "kept_action": ph["selected"],
            "wiped_action": pw["selected"],
            "prediction_differs": ph["prediction"] != pw["prediction"],
        })
    return {"rows": rows, "history_changes_prediction": any(r["prediction_differs"] for r in rows)}


def run_perf() -> dict:
    base = TwoAgentRuntime(seed=17, starts=((8, 16), (12, 16)), signal_enabled=False, contact_enabled=True)
    sig = TwoAgentRuntime(seed=17, starts=((8, 16), (12, 16)), signal_enabled=True, contact_enabled=True)
    t0 = time.perf_counter()
    base.step(40)
    t1 = time.perf_counter()
    sig.step(40)
    t2 = time.perf_counter()
    return {
        "ticks": 40,
        "two_agent_s": t1 - t0,
        "two_agent_plus_signal_s": t2 - t1,
        "ratio": (t2 - t1) / max(1e-9, t1 - t0),
        "field_history": "none; one (H,W) array pair, decayed in place",
        "telemetry": "bounded receipts, no per-tick field dumps",
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    trans, dist_csv = run_transmission()
    abl = run_ablation()
    traces, deco, pred, beh = run_learning()
    src = run_source_control()
    bi = run_bidirectional()
    hist = run_history()
    perf = run_perf()
    _json(OUT / "TRANSMISSION_RESULTS.json", trans)
    with (OUT / "DISTANCE_RESULTS.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(dist_csv[0].keys()))
        w.writeheader()
        w.writerows(dist_csv)
    _json(OUT / "ABLATION_RESULTS.json", abl)
    _json(OUT / "LEARNING_TRACES.json", traces)
    _json(OUT / "DECORRELATION_RESULTS.json", deco)
    _json(OUT / "PREDICTION_RESULTS.json", pred)
    _json(OUT / "BEHAVIOR_RESULTS.json", beh)
    _json(OUT / "SOURCE_CONTROL_RESULTS.json", src)
    _json(OUT / "_bidirectional.json", bi)
    _json(OUT / "_history.json", hist)
    _json(OUT / "_performance.json", perf)
    print(json.dumps({
        "distance_effect": trans["any_distance_effect"],
        "ablation_ok": abl["S0_vs_S1_attributable"],
        "prediction": pred["signal_dependent_prediction"],
        "action": beh["signal_dependent_action"],
        "source_agnostic": src["source_agnostic"],
        "bidirectional": bi["bidirectional"],
        "history_pred": hist["history_changes_prediction"],
        "perf_ratio": perf["ratio"],
        "emit_canonical": trans["emit_in_available_actions"],
    }, indent=2))


if __name__ == "__main__":
    main()
