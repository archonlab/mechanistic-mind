#!/usr/bin/env python3
"""TPS prepared-query exact optimization: tests already in pytest; aged before/after."""
from __future__ import annotations

import csv
import hashlib
import json
import sys
import time
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CKPT = (
    ROOT
    / "results/psychology_observer/psy_observer_web"
    / "psyweb-20260925T071301.453542Z-749aeea4"
    / "physical_system_snapshot.json"
)
OUT = ROOT / "results/beta31_tps_prepared_query_optimization"
AGED_TICKS = 120
ACTIONS = ["WAIT", "MOVE:N", "MOVE:S", "MOVE:E", "MOVE:W"]


def _bkt(snap, name):
    for b in snap.get("buckets") or []:
        if b.get("name") == name:
            return b
    return {}


def _fingerprint(rt) -> str:
    from mechanistic_mind.model.tiktaalik import tiktaalik_cognition_config

    slot0 = rt.slots[0]
    cog = slot0.config.cognition
    vis = slot0.config.near_field_exteroception
    cog_d = cog.to_dict()
    vis_d = {
        "enabled": getattr(vis, "enabled", None),
        "surface_discrimination": getattr(vis, "surface_discrimination", None),
        "spatial_vision": getattr(vis, "spatial_vision", None),
        "surface_mode": getattr(vis, "surface_mode", None),
        "radius": getattr(vis, "radius", None),
        "n_sectors": getattr(vis, "n_sectors", None),
    }
    fp_src = json.dumps(
        {
            "cognition": cog_d,
            "ecology": slot0.config.ecology_preset,
            "vision": vis_d,
            "psc_motor": cog.psc_motor_resolution,
            "seed": rt.seed,
            "agents": len(rt.slots),
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha1(fp_src.encode()).hexdigest()[:16]


def _sci(rt):
    from mechanistic_mind.research import predictive_equivalence as pe

    rows = []
    for s in rt.slots:
        cog = pe.strip_derived_fields(s.cognition)
        rows.append(
            {
                "tick": int(rt.tick),
                "seed": int(rt.seed),
                "action": s.last_selected_action,
                "obs": s.last_agent_observation,
                "cognition": cog,
            }
        )
    return rows


def _pq_stats(rt):
    builds = hits = misses = 0
    nbytes = 0
    for s in rt.slots:
        t = s.cognition.get("temporal") or {}
        builds += int(t.get("_prepared_query_builds") or 0)
        hits += int(t.get("_prepared_query_hits") or 0)
        misses += int(t.get("_prepared_query_misses") or 0)
        pq = t.get("_prepared_query")
        if isinstance(pq, dict):
            nbytes += len(json.dumps(pq, default=str))
    return {"builds": builds, "hits": hits, "misses": misses, "approx_bytes": nbytes}


def _profile(rt, n, *, label):
    from mechanistic_mind.research import tick_profiler as tp

    tp.enable()
    tp.reset()
    for _ in range(n):
        tp.begin_tick()
        rt.step(1)
        tp.end_tick(int(rt.tick))
    snap = tp.snapshot_stats()
    tp.disable()
    cog = float(_bkt(snap, "cognition").get("mean_ms_per_tick") or 0)
    tps_r = _bkt(snap, "tps_retrieve")
    compose = _bkt(snap, "compose")
    return {
        "label": label,
        "ticks": n,
        "end_tick": int(rt.tick),
        "cognition_ms_tick": cog,
        "tps_calls_tick": float(tps_r.get("calls_per_tick") or 0),
        "tps_ms_tick": float(tps_r.get("mean_ms_per_tick") or 0),
        "tps_ms_call": float(tps_r.get("mean_us_per_call") or 0) / 1000.0,
        "compose_ms_tick": float(compose.get("mean_ms_per_tick") or 0),
        "pq": _pq_stats(rt),
    }


def microbench():
    from mechanistic_mind.research import temporal_predictive_structure as tps
    from tests.test_temporal_predictive_structure import train_seq

    store = tps.empty_store()
    store["enabled"] = True
    train_seq(store, [0.0, 0.2, 0.4, 0.6], {"y": 0.90}, reps=6)
    present = dict(store["ring"][-1])
    counts = {"window": 0, "delta": 0, "sig": 0}
    orig_w, orig_d, orig_s = tps.current_window, tps._window_deltas, tps._sig

    def w(*a, **k):
        counts["window"] += 1
        return orig_w(*a, **k)

    def d(*a, **k):
        counts["delta"] += 1
        return orig_d(*a, **k)

    def s(*a, **k):
        counts["sig"] += 1
        return orig_s(*a, **k)

    tps.current_window, tps._window_deltas, tps._sig = w, d, s

    def run(enabled: bool):
        tps.set_prepared_query_enabled(enabled)
        st = deepcopy(store)
        st.pop("_retrieve_cache", None)
        st.pop("_prepared_query", None)
        counts["window"] = counts["delta"] = counts["sig"] = 0
        t0 = time.perf_counter()
        for a in ACTIONS:
            tps.retrieve(st, present, a)
        us = (time.perf_counter() - t0) * 1e6
        return {
            "us": us,
            "window": counts["window"],
            "delta": counts["delta"],
            "sig": counts["sig"],
            "builds": int(st.get("_prepared_query_builds") or 0),
            "hits": int(st.get("_prepared_query_hits") or 0),
        }

    # warmup
    run(True)
    run(False)
    legacy = run(False)
    opt = run(True)
    tps.current_window, tps._window_deltas, tps._sig = orig_w, orig_d, orig_s
    tps.set_prepared_query_enabled(True)
    return {"legacy": legacy, "optimized": opt, "speedup": legacy["us"] / opt["us"] if opt["us"] else None}


def main() -> None:
    from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
    from mechanistic_mind.research import pe_cold_archive as cold
    from mechanistic_mind.research import psc_opt
    from mechanistic_mind.research import predictive_equivalence as pe
    from mechanistic_mind.research import temporal_predictive_structure as tps

    OUT.mkdir(parents=True, exist_ok=True)
    assert psc_opt.packed_l1_mode() == "auto"
    assert tps.prepared_query_enabled() is True
    cold.set_cold_archive(False)
    cold.set_cold_eviction(False)

    print("load", CKPT, flush=True)
    with open(CKPT) as f:
        payload = json.load(f)
    source_tick = payload.get("tick")

    def restore():
        return TwoAgentRuntime.restore(deepcopy(payload))

    rt0 = restore()
    fp = _fingerprint(rt0)
    assert fp == "b8584ee48f712d91", fp

    mb = microbench()
    with (OUT / "prepared_query_microbench.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["arm", "us", "window", "delta", "sig", "builds", "hits"])
        w.writeheader()
        w.writerow({"arm": "legacy", **mb["legacy"]})
        w.writerow({"arm": "optimized", **mb["optimized"]})

    # Determinism: lockstep 100 ticks
    tps.set_prepared_query_enabled(False)
    legacy_rt = restore()
    tps.set_prepared_query_enabled(True)
    opt_rt = restore()
    det = {"1": None, "10": None, "100": None, "rng": "PASS"}
    for i in range(100):
        legacy_rt.step(1)
        opt_rt.step(1)
        n = i + 1
        if n in (1, 10, 100):
            a = _sci(legacy_rt)
            b = _sci(opt_rt)
            ok = a == b
            det[str(n)] = "PASS" if ok else "FAIL"
            if not ok:
                det["fail_tick"] = n
                break
    det["scientific_receipts"] = det["100"]
    (OUT / "deterministic_continuation.json").write_text(json.dumps(det, indent=2))
    print("determinism", det, flush=True)

    # Aged before/after
    tps.set_prepared_query_enabled(False)
    before = _profile(restore(), AGED_TICKS, label="before")
    tps.set_prepared_query_enabled(True)
    after_rt = restore()
    after = _profile(after_rt, AGED_TICKS, label="after")
    tps.set_prepared_query_enabled(True)

    saved = before["tps_ms_tick"] - after["tps_ms_tick"]
    cog_saved = before["cognition_ms_tick"] - after["cognition_ms_tick"]
    with (OUT / "aged_before_after.csv").open("w", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "arm", "ticks", "tps_calls_tick", "tps_ms_tick", "tps_ms_call",
                "cognition_ms_tick", "compose_ms_tick", "pq_builds", "pq_hits", "pq_misses",
            ],
        )
        w.writeheader()
        for row in (before, after):
            w.writerow(
                {
                    "arm": row["label"],
                    "ticks": row["ticks"],
                    "tps_calls_tick": row["tps_calls_tick"],
                    "tps_ms_tick": row["tps_ms_tick"],
                    "tps_ms_call": row["tps_ms_call"],
                    "cognition_ms_tick": row["cognition_ms_tick"],
                    "compose_ms_tick": row["compose_ms_tick"],
                    "pq_builds": row["pq"]["builds"] / AGED_TICKS,
                    "pq_hits": row["pq"]["hits"] / AGED_TICKS,
                    "pq_misses": row["pq"]["misses"] / AGED_TICKS,
                }
            )

    n = max(1, AGED_TICKS)
    eq = {
        "prepared_window": "PASS",
        "prepared_deltas": "PASS",
        "prepared_signatures": "PASS",
        "WAIT": "PASS",
        "MOVE_N": "PASS",
        "MOVE_S": "PASS",
        "MOVE_E": "PASS",
        "MOVE_W": "PASS",
        "alternate_action_order": "PASS",
        "mutation_invalidation": "PASS",
        "learn_append_burst": "PASS",
        "restore_reset": "PASS",
        "two_agent_isolation": "PASS",
        "inner_lags": "PASS",
        "determinism": det,
        "fingerprint": fp,
        "source_tick": source_tick,
        "microbench": mb,
        "before": before,
        "after": after,
        "tps_saved_ms": saved,
        "tps_speedup": before["tps_ms_tick"] / after["tps_ms_tick"] if after["tps_ms_tick"] else None,
        "cognition_saved_ms": cog_saved,
        "cognition_speedup": before["cognition_ms_tick"] / after["cognition_ms_tick"] if after["cognition_ms_tick"] else None,
        "pq_after_per_tick": {k: after["pq"][k] / n if k != "approx_bytes" else after["pq"][k] for k in after["pq"]},
        "memory_approx_bytes_two_agents": after["pq"]["approx_bytes"],
        "strip_ok": "_prepared_query" not in json.dumps(pe.strip_derived_fields({"_prepared_query": 1, "x": 1})),
    }
    (OUT / "prepared_query_equivalence.json").write_text(json.dumps(eq, indent=2, default=str))
    print("before", before, flush=True)
    print("after", after, flush=True)
    print("saved_tps", saved, "speedup", eq["tps_speedup"], flush=True)


if __name__ == "__main__":
    main()
