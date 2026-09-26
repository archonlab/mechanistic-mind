#!/usr/bin/env python3
"""Packed L1 compose optimization: microbench, aged checkpoint, continuation.

Does not attach to the live Observer process. Reads the committed checkpoint
read-only (json load; runtime restore is in-memory).
"""
from __future__ import annotations

import json
import os
import statistics
import time
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CKPT = (
    ROOT
    / "results/psychology_observer/psy_observer_web"
    / "psyweb-20260925T071301.453542Z-749aeea4"
    / "physical_system_snapshot.json"
)
OUT = ROOT / "results/beta31_compose_packed_l1_optimization"
BENCH_TICKS = 100

CHANNELS_68 = (
    [f"body.{k}" for k in ("T", "B0", "B1", "B2", "mech", "vx", "vy")]
    + [f"local.{k}" for k in ("T", "M0", "M1", "M2", "vx", "vy", "FIELD_A", "FIELD_B")]
    + [f"internal.c{i}" for i in range(5)]
    + [f"exo_{i}" for i in range(3)]
    + [f"surface_c{c}_{i}" for c in range(3) for i in range(3)]
    + [f"spatial_exo_a{i}" for i in range(5)]
    + [f"spatial_surface_c{c}_a{i}" for c in range(3) for i in range(5)]
    + ["vest_0", "vest_1", "prop_neck_0", "prop_neck_1"]
    + [f"osc_{side}_{i}" for i in range(6) for side in ("l", "r")]
)


def _qfrag(seed: int) -> dict[str, float]:
    bins = 5
    out = {}
    x = seed
    for i, k in enumerate(CHANNELS_68):
        x = (x * 1103515245 + 12345 + i) & 0x7FFFFFFF
        q = x % bins
        out[k] = (q + 0.5) / bins
    return out


def _us(fn, loops: int) -> float:
    t0 = time.perf_counter()
    for _ in range(loops):
        fn()
    return (time.perf_counter() - t0) * 1e6 / loops


def microbench() -> list[dict]:
    from mechanistic_mind.research import prospective_composition as pr
    from mechanistic_mind.research import psc_opt

    rows_out = []
    queries = [_qfrag(s) for s in range(24)]
    for n in (1, 8, 16, 32, 64, 96, 128):
        st = pr.empty_store()
        for i in range(n):
            ant = _qfrag(1000 + i)
            for _ in range(3):
                pr.learn_transition(st, tick=i, antecedent=ant, action="WAIT", consequent=ant)
        pack = psc_opt.ensure_pack(st)
        pa = pack["packed_actions"]["WAIT"]
        q0 = queries[0]
        # warmup
        psc_opt.soft_match_packed_dict(pa["rows"], q0)
        psc_opt.soft_match_packed_matrix(pa, q0)
        try:
            psc_opt.soft_match_packed_numpy(pa, q0)
            have_np = True
        except Exception:
            have_np = False
        loops = 400 if n <= 32 else 200
        def legacy():
            psc_opt.soft_match_packed_dict(pa["rows"], queries[i % len(queries)])

        i_holder = {"i": 0}

        def wrap_legacy():
            i_holder["i"] += 1
            return psc_opt.soft_match_packed_dict(pa["rows"], queries[i_holder["i"] % len(queries)])

        def wrap_matrix():
            i_holder["i"] += 1
            return psc_opt.soft_match_packed_matrix(pa, queries[i_holder["i"] % len(queries)])

        def wrap_numpy():
            i_holder["i"] += 1
            return psc_opt.soft_match_packed_numpy(pa, queries[i_holder["i"] % len(queries)])

        i_holder["i"] = 0
        leg = _us(wrap_legacy, loops)
        i_holder["i"] = 0
        mat = _us(wrap_matrix, loops)
        np_us = None
        if have_np:
            i_holder["i"] = 0
            np_us = _us(wrap_numpy, loops)
        # bitwise vs dict on all queries
        bitwise = True
        sel_ok = True
        for q in queries:
            a, da = psc_opt.soft_match_packed_dict(pa["rows"], q)
            b, db = psc_opt.soft_match_packed_matrix(pa, q)
            if a is None or b is None or a["key"] != b["key"]:
                sel_ok = False
            if da != db:
                bitwise = False
        rows_out.append({
            "N": n,
            "legacy_us": round(leg, 3),
            "matrix_us": round(mat, 3),
            "numpy_us": None if np_us is None else round(np_us, 3),
            "speedup_matrix": round(leg / mat, 3) if mat else None,
            "speedup_numpy": None if not np_us else round(leg / np_us, 3),
            "selection_exact": sel_ok,
            "distance_bitwise": bitwise,
        })
    return rows_out


def _rows_by_action(rt) -> dict:
    out = {}
    for i, slot in enumerate(rt.slots[:2]):
        pack = __import__("mechanistic_mind.research.psc_opt", fromlist=["psc_opt"]).ensure_pack(
            slot.cognition["prospection"]
        )
        out[f"agent_{i}"] = {
            a: len(v) for a, v in (pack.get("by_action") or {}).items()
        }
    return out


def _fingerprint(rt) -> dict:
    slot = rt.slots[0]
    slot1 = rt.slots[1]
    cog0 = slot.cognition
    cog1 = slot1.cognition
    sel0 = cog0.get("last_selection") or {}
    sel1 = cog1.get("last_selection") or {}
    prosp0 = cog0.get("prospection") or {}
    tps0 = cog0.get("temporal") or {}
    pe0 = cog0.get("equivalence") or {}

    def _len(x):
        if isinstance(x, dict):
            return len(x)
        if isinstance(x, list):
            return len(x)
        return None

    rec0 = cog0.get("last_decision_receipt") or slot.__dict__.get("last_decision_receipt")
    return {
        "tick": int(rt.tick),
        "seed": int(slot.seed),
        "rng_unit_0": __import__(
            "mechanistic_mind.physical_system.runtime", fromlist=["_rng_unit"]
        )._rng_unit(slot.seed, rt.tick),
        "a0_xy": (round(float(slot.body.x), 12), round(float(slot.body.y), 12)),
        "a1_xy": (round(float(slot1.body.x), 12), round(float(slot1.body.y), 12)),
        "a0_action": slot.last_selected_action,
        "a1_action": slot1.last_selected_action,
        "a0_comp_meta": deepcopy(sel0.get("composition_meta")),
        "a1_comp_meta": deepcopy(sel1.get("composition_meta")),
        "a0_comp_keys": [
            (c.get("actions"), c.get("depth"))
            for c in (sel0.get("continuations") or [])[:8]
            if isinstance(c, dict)
        ],
        "a1_comp_keys": [
            (c.get("actions"), c.get("depth"))
            for c in (sel1.get("continuations") or [])[:8]
            if isinstance(c, dict)
        ],
        "n_trans_0": _len(prosp0.get("transitions")),
        "n_tps_0": _len(tps0.get("inner") or tps0.get("by_sig") or tps0),
        "n_pe_0": _len(pe0.get("classes") or pe0.get("by_key") or pe0),
        "a0_pred_n": len(sel0.get("prediction_matches") or []),
        "receipt_sel_0": (sel0.get("action"), sel0.get("source"), sel0.get("selection_rule")),
        "receipt_sel_1": (sel1.get("action"), sel1.get("source"), sel1.get("selection_rule")),
    }


def _profile_bucket(stats: dict, name: str) -> dict:
    for b in stats.get("buckets") or []:
        if b.get("name") == name:
            return b
    return {}


def run_aged(payload: dict, mode: str, ticks: int) -> dict:
    from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
    from mechanistic_mind.research import psc_opt
    from mechanistic_mind.research import tick_profiler as tp
    from mechanistic_mind.research import pe_cold_archive as cold

    # Isolated restore has incomplete PECA chunks (no Observer writer).
    # Disable archive I/O so both arms can step; PE forget still runs in-RAM.
    # Both dict and matrix arms use the same flags.
    cold.set_cold_archive(False)
    cold.set_cold_eviction(False)

    psc_opt.set_packed_l1_mode(mode)
    rt = TwoAgentRuntime.restore(deepcopy(payload))
    rows = _rows_by_action(rt)
    tp.enable()
    tp.reset()
    snaps = {}
    for i in range(ticks):
        rt.step(1)
        if i + 1 in (1, 10, ticks):
            snaps[i + 1] = _fingerprint(rt)
    stats = tp.snapshot_stats()
    tp.disable()
    psc_opt.set_packed_l1_mode("auto")
    return {
        "mode": mode,
        "rows_by_action": rows,
        "start_tick": int(payload.get("tick")),
        "end_tick": int(rt.tick),
        "ticks": ticks,
        "snaps": snaps,
        "compose": _profile_bucket(stats, "compose"),
        "cognition": _profile_bucket(stats, "cognition"),
        "sim": _profile_bucket(stats, "sim"),
        "tick": _profile_bucket(stats, "tick"),
        "mean_ms_per_tick": stats.get("mean_ms_per_tick"),
        "profiler_ticks": stats.get("ticks"),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    print("microbench...", flush=True)
    micro = microbench()
    (OUT / "kernel_microbench.csv").write_text(
        "N,legacy_us,matrix_us,numpy_us,speedup_matrix,speedup_numpy,selection_exact,distance_bitwise\n"
        + "\n".join(
            f"{r['N']},{r['legacy_us']},{r['matrix_us']},{r['numpy_us']},{r['speedup_matrix']},"
            f"{r['speedup_numpy']},{r['selection_exact']},{r['distance_bitwise']}"
            for r in micro
        )
        + "\n"
    )
    print(json.dumps(micro, indent=2))

    print("load checkpoint", CKPT, flush=True)
    with open(CKPT) as f:
        payload = json.load(f)
    print("aged dict (reference)...", flush=True)
    before = run_aged(payload, "dict", BENCH_TICKS)
    print("aged matrix (optimized)...", flush=True)
    after = run_aged(payload, "auto", BENCH_TICKS)

    def ms(bkt, key="mean_ms_per_tick"):
        return float(bkt.get(key) or 0.0)

    b_comp = before["compose"]
    a_comp = after["compose"]
    aged_row = {
        "source_checkpoint": str(CKPT.relative_to(ROOT)),
        "checkpoint_tick": payload.get("tick"),
        "rows_by_action": before["rows_by_action"],
        "bench_ticks": BENCH_TICKS,
        "BEFORE": {
            "compose_calls_per_tick": b_comp.get("calls_per_tick"),
            "compose_ms_per_call": (b_comp.get("mean_us_per_call") or 0) / 1000.0,
            "compose_ms_per_tick": b_comp.get("mean_ms_per_tick"),
            "cognition_ms_per_tick": before["cognition"].get("mean_ms_per_tick"),
            "simulation_ms_per_tick": before["sim"].get("mean_ms_per_tick"),
            "wall_mean_ms_per_tick": before["mean_ms_per_tick"],
        },
        "AFTER": {
            "compose_calls_per_tick": a_comp.get("calls_per_tick"),
            "compose_ms_per_call": (a_comp.get("mean_us_per_call") or 0) / 1000.0,
            "compose_ms_per_tick": a_comp.get("mean_ms_per_tick"),
            "cognition_ms_per_tick": after["cognition"].get("mean_ms_per_tick"),
            "simulation_ms_per_tick": after["sim"].get("mean_ms_per_tick"),
            "wall_mean_ms_per_tick": after["mean_ms_per_tick"],
        },
    }
    bms = float(b_comp.get("mean_ms_per_tick") or 0)
    ams = float(a_comp.get("mean_ms_per_tick") or 0)
    aged_row["COMPOSE_TIME_SAVED_PER_TICK"] = bms - ams
    aged_row["COMPOSE_SPEEDUP"] = (bms / ams) if ams else None
    bsim = float(before["sim"].get("mean_ms_per_tick") or 0)
    asim = float(after["sim"].get("mean_ms_per_tick") or 0)
    aged_row["TOTAL_SIMULATION_SPEEDUP"] = (bsim / asim) if asim else None

    (OUT / "aged_before_after.csv").write_text(
        "phase,compose_calls_per_tick,compose_ms_per_call,compose_ms_per_tick,"
        "cognition_ms_per_tick,simulation_ms_per_tick,wall_ms_per_tick\n"
        + "\n".join(
            "{phase},{calls},{callms},{tickms},{cog},{sim},{wall}".format(
                phase=phase,
                calls=aged_row[phase]["compose_calls_per_tick"],
                callms=aged_row[phase]["compose_ms_per_call"],
                tickms=aged_row[phase]["compose_ms_per_tick"],
                cog=aged_row[phase]["cognition_ms_per_tick"],
                sim=aged_row[phase]["simulation_ms_per_tick"],
                wall=aged_row[phase]["wall_mean_ms_per_tick"],
            )
            for phase in ("BEFORE", "AFTER")
        )
        + "\n"
    )

    det = {"1_tick": before["snaps"][1] == after["snaps"][1],
           "10_tick": before["snaps"][10] == after["snaps"][10],
           "100_tick": before["snaps"][100] == after["snaps"][100]}
    rng_ok = all(
        before["snaps"][k]["rng_unit_0"] == after["snaps"][k]["rng_unit_0"]
        and before["snaps"][k]["a0_action"] == after["snaps"][k]["a0_action"]
        and before["snaps"][k]["a1_action"] == after["snaps"][k]["a1_action"]
        for k in (1, 10, 100)
    )
    rec_ok = all(
        before["snaps"][k]["receipt_sel_0"] == after["snaps"][k]["receipt_sel_0"]
        and before["snaps"][k]["a0_comp_meta"] == after["snaps"][k]["a0_comp_meta"]
        and before["snaps"][k]["a1_comp_meta"] == after["snaps"][k]["a1_comp_meta"]
        for k in (1, 10, 100)
    )
    if not det["100_tick"]:
        # first divergence
        first = None
        for k in (1, 10, 100):
            if before["snaps"][k] != after["snaps"][k]:
                first = k
                break
        det["first_divergence_tick_offset"] = first
        det["before"] = before["snaps"][first]
        det["after"] = after["snaps"][first]

    (OUT / "deterministic_continuation.json").write_text(json.dumps({
        **det,
        "RNG": rng_ok,
        "scientific_receipts": rec_ok,
        "checkpoint_tick": payload.get("tick"),
    }, indent=2, default=str))

    (OUT / "equivalence_summary.json").write_text(json.dumps({
        "micro_selection_exact": all(r["selection_exact"] for r in micro),
        "micro_distance_bitwise": all(r["distance_bitwise"] for r in micro),
        "continuation": det,
        "RNG": rng_ok,
        "scientific_receipts": rec_ok,
        "aged": aged_row,
        "micro": micro,
    }, indent=2, default=str))

    print(json.dumps({"aged": aged_row, "det": det, "RNG": rng_ok, "receipts": rec_ok}, indent=2, default=str))


if __name__ == "__main__":
    main()
