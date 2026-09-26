#!/usr/bin/env python3
"""Cognition residual forensic. Measurement only. Residual spans default off."""
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
OUT = ROOT / "results/beta31_cognition_residual_forensic"
BASE_TICKS = 20
COARSE_TICKS = 50
DET_TICKS = 10
FINE_TICKS = 40

OLD_CHILDREN = [
    "per_realize", "tpe_ingest", "pc_observe", "ms_ingest", "learn_transition",
    "pe_learn", "tps_learn", "tps_append", "cog_predict_loop", "tpb_collect",
    "compose", "tpb_diagnostic", "pcp_collect", "map_collect", "conflict_organize",
    "fsa_groups", "scenario_groups", "compete_scenarios", "pc_purge", "cog_retain",
]
NEW_DIRECT = [
    "prior_pc_pe_retrieve", "pe_rel_refresh", "tps_rel_refresh",
    "pcp_diag_observer", "map_merge_diag", "per_filter_continuations",
    "per_filter_entry", "conflict_diag",
]
# select_receipts nests fsa_groups + compete_scenarios — use SELF only.
NEW_SELF = ["select_receipts"]


def _pctile(xs, p):
    if not xs:
        return None
    ys = sorted(xs)
    i = min(len(ys) - 1, max(0, int(round((p / 100.0) * (len(ys) - 1)))))
    return ys[i]


def _bkt(snap, name):
    for b in snap.get("buckets") or []:
        if b.get("name") == name:
            return b
    return {}


def _row(snap, name, cog_ms):
    b = _bkt(snap, name)
    inc = float(b.get("mean_ms_per_tick") or 0)
    slf = float(b.get("self_ms_per_tick") or 0)
    calls = float(b.get("calls_per_tick") or 0)
    us = float(b.get("mean_us_per_call") or 0)
    return {
        "name": name,
        "calls": calls,
        "inc": inc,
        "self": slf,
        "ms_call": (us / 1000.0) if calls else 0.0,
        "pct": (100.0 * inc / cog_ms) if cog_ms else 0.0,
        "pct_self": (100.0 * slf / cog_ms) if cog_ms else 0.0,
    }


def _fingerprint(rt) -> str:
    from mechanistic_mind.model.tiktaalik import tiktaalik_cognition_config

    slot0 = rt.slots[0]
    cog = slot0.config.cognition
    vis = slot0.config.near_field_exteroception
    fp_src = json.dumps(
        {
            "cognition": cog.to_dict(),
            "ecology": slot0.config.ecology_preset,
            "vision": {
                "enabled": getattr(vis, "enabled", None),
                "surface_discrimination": getattr(vis, "surface_discrimination", None),
                "spatial_vision": getattr(vis, "spatial_vision", None),
                "surface_mode": getattr(vis, "surface_mode", None),
                "radius": getattr(vis, "radius", None),
                "n_sectors": getattr(vis, "n_sectors", None),
            },
            "psc_motor": cog.psc_motor_resolution,
            "seed": rt.seed,
            "agents": len(rt.slots),
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha1(fp_src.encode()).hexdigest()[:16]


def _profile(rt, n):
    from mechanistic_mind.research import tick_profiler as tp

    tp.enable()
    tp.reset()
    walls = []
    for _ in range(n):
        tp.begin_tick()
        t0 = time.perf_counter()
        rt.step(1)
        walls.append((time.perf_counter() - t0) * 1000.0)
        tp.end_tick(int(rt.tick))
    snap = tp.snapshot_stats()
    tp.disable()
    return snap, walls


def _sci(rt):
    from mechanistic_mind.research import predictive_equivalence as pe

    return [
        {
            "tick": int(rt.tick),
            "action": s.last_selected_action,
            "motor": s.last_motor_output,
            "obs": s.last_agent_observation,
            "cog": pe.strip_derived_fields(s.cognition),
        }
        for s in rt.slots
    ]


def main() -> None:
    from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
    from mechanistic_mind.physical_system import cognition as cogmod
    from mechanistic_mind.research import pe_cold_archive as cold
    from mechanistic_mind.research import psc_opt
    from mechanistic_mind.research import temporal_predictive_structure as tps
    from mechanistic_mind.research import predictive_relevance as prl

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

    # --- baseline: residual spans OFF ---
    cogmod.set_residual_spans(False)
    snap_b, walls_b = _profile(restore(), BASE_TICKS)
    cog_b = float(_bkt(snap_b, "cognition").get("mean_ms_per_tick") or 0)
    wall_b = sum(walls_b) / len(walls_b)
    old_sum_b = sum(float(_bkt(snap_b, n).get("mean_ms_per_tick") or 0) for n in OLD_CHILDREN)
    res_b = max(0.0, cog_b - old_sum_b)

    # --- coarse: residual spans ON ---
    cogmod.set_residual_spans(True)
    # cheap refresh counters
    refresh_calls = {"n": 0, "classes": 0}
    orig_refresh = prl.refresh

    def refresh_w(eq_store, *, tick=0, meta=None):
        refresh_calls["n"] += 1
        classes = [c for c in (eq_store.get("classes") or {}).values() if c.get("status") == "ACTIVE"]
        refresh_calls["classes"] += len(classes)
        return orig_refresh(eq_store, tick=tick, meta=meta)

    prl.refresh = refresh_w
    snap_c, walls_c = _profile(restore(), COARSE_TICKS)
    prl.refresh = orig_refresh
    wall_c = sum(walls_c) / len(walls_c)
    cog_c = float(_bkt(snap_c, "cognition").get("mean_ms_per_tick") or 0)
    old_sum = sum(float(_bkt(snap_c, n).get("mean_ms_per_tick") or 0) for n in OLD_CHILDREN)
    # fsa+compete are inside select_receipts inclusive AND in old_sum — don't add select inclusive
    new_direct_sum = sum(float(_bkt(snap_c, n).get("mean_ms_per_tick") or 0) for n in NEW_DIRECT)
    sel = _row(snap_c, "select_receipts", cog_c)
    new_self_sum = sel["self"]
    explained_new = new_direct_sum + new_self_sum
    residual_old_def = max(0.0, cog_c - old_sum)
    remaining = max(0.0, residual_old_def - explained_new)
    accounted = 100.0 * (old_sum + explained_new) / cog_c if cog_c else 0.0
    overhead_pct = 100.0 * (wall_c - wall_b) / wall_b if wall_b else 0.0

    rows = []
    for name in NEW_DIRECT:
        r = _row(snap_c, name, cog_c)
        rows.append((name, r["inc"], r["calls"], r["ms_call"], "inclusive", r["pct"]))
    rows.append(("select_receipts", sel["self"], sel["calls"], sel["ms_call"], "self", sel["pct_self"]))
    rows.sort(key=lambda x: -x[1])

    with (OUT / "cognition_residual_coarse.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["region", "ms_tick", "calls_tick", "ms_call", "timer", "pct_cognition"])
        for r in rows:
            w.writerow(r)
        w.writerow(["OLD_NAMED_CHILDREN_SUM", f"{old_sum:.4f}", "", "", "inclusive", f"{100*old_sum/cog_c:.2f}"])
        w.writerow(["NEW_RESIDUAL_REGIONS_SUM", f"{explained_new:.4f}", "", "", "mix", f"{100*explained_new/cog_c:.2f}"])
        w.writerow(["remaining_unattributed", f"{remaining:.4f}", "", "", "", f"{100*remaining/cog_c:.2f}"])

    print("baseline cog", cog_b, "res", res_b, "wall", wall_b, flush=True)
    print("coarse cog", cog_c, "old_res_def", residual_old_def, "new_explained", explained_new,
          "remaining", remaining, "accounted", accounted, "overhead%", overhead_pct, flush=True)
    print("regions", [(a, round(b, 3)) for a, b, *_ in rows[:8]], flush=True)
    print("refresh_calls/tick", refresh_calls["n"] / COARSE_TICKS,
          "classes/tick", refresh_calls["classes"] / COARSE_TICKS, flush=True)

    # determinism 10 ticks
    cogmod.set_residual_spans(False)
    a_rt = restore()
    cogmod.set_residual_spans(True)
    b_rt = restore()
    det = "PASS"
    for _ in range(DET_TICKS):
        a_rt.step(1)
        b_rt.step(1)
    if _sci(a_rt) != _sci(b_rt):
        det = "FAIL"
    print("determinism", det, flush=True)

    fine = None
    hot = [r for r in rows if r[1] >= 8.0]
    if hot and remaining > 0.10 * cog_c:
        pass  # still do fine if a hot region needs internals
    if any(r[0] in {"pe_rel_refresh", "tps_rel_refresh"} and r[1] >= 8.0 for r in rows):
        # fine: time _relevance_for
        from mechanistic_mind.research.predictive_relevance import _relevance_for as orig_rel

        ns = {"rel": 0, "n": 0}
        orig_r = prl.refresh

        def rel_w(cls, others, *, tau, tick):
            ns["n"] += 1
            t0 = time.perf_counter_ns()
            out = orig_rel(cls, others, tau=tau, tick=tick)
            ns["rel"] += time.perf_counter_ns() - t0
            return out

        prl._relevance_for = rel_w
        # rebind refresh to use wrapped _relevance_for — refresh already imports the name
        # predictive_relevance.refresh calls _relevance_for in same module, so patching prl._relevance_for works.
        cogmod.set_residual_spans(True)
        snap_f, _ = _profile(restore(), FINE_TICKS)
        prl._relevance_for = orig_rel
        fine = {
            "relevance_for_calls_tick": ns["n"] / FINE_TICKS,
            "relevance_for_ms_tick": (ns["rel"] / 1e6) / FINE_TICKS,
            "pe_rel": _row(snap_f, "pe_rel_refresh", float(_bkt(snap_f, "cognition").get("mean_ms_per_tick") or 1)),
            "tps_rel": _row(snap_f, "tps_rel_refresh", float(_bkt(snap_f, "cognition").get("mean_ms_per_tick") or 1)),
        }
        with (OUT / "cognition_residual_fine.csv").open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["metric", "value"])
            for k, v in fine.items():
                w.writerow([k, json.dumps(v, default=str) if isinstance(v, dict) else v])
        print("fine", fine, flush=True)

    cogmod.set_residual_spans(False)

    summary = {
        "source_tick": source_tick,
        "fingerprint": fp,
        "baseline": {"wall": wall_b, "cognition": cog_b, "residual": res_b, "ticks": BASE_TICKS},
        "coarse": {
            "wall": wall_c,
            "cognition": cog_c,
            "old_child_sum": old_sum,
            "old_residual_def": residual_old_def,
            "new_explained": explained_new,
            "remaining": remaining,
            "accounted_pct": accounted,
            "ticks": COARSE_TICKS,
            "regions": [
                {"name": a, "ms": b, "calls": c, "ms_call": d, "timer": e, "pct": p}
                for a, b, c, d, e, p in rows
            ],
            "refresh_calls_tick": refresh_calls["n"] / COARSE_TICKS,
            "refresh_classes_tick": refresh_calls["classes"] / COARSE_TICKS,
        },
        "overhead_pct_vs_20tick_baseline": overhead_pct,
        "determinism": det,
        "fine": fine,
        "agent_begin": {
            "a0": _row(snap_c, "begin_tick_agent_0", cog_c)["inc"],
            "a1": _row(snap_c, "begin_tick_agent_1", cog_c)["inc"],
        },
        "named": {n: _row(snap_c, n, cog_c) for n in ["compose", "tps_retrieve", "tps_learn", "tpe_ingest", "conflict_organize", "pcp_collect", "tpb_collect"]},
    }
    (OUT / "_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print("done", json.dumps({"accounted": accounted, "remaining": remaining, "det": det}, indent=2), flush=True)


if __name__ == "__main__":
    main()
