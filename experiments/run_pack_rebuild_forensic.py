#!/usr/bin/env python3
"""Pack rebuild forensic on saved aged snapshot. No production code change."""
from __future__ import annotations

import json
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
OUT = ROOT / "results/beta31_pack_rebuild_optimization"
BENCH_TICKS = 100


def main() -> None:
    from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
    from mechanistic_mind.research import pe_cold_archive as cold
    from mechanistic_mind.research import psc_opt
    from mechanistic_mind.research import tick_profiler as tp
    from mechanistic_mind.research import prospective_composition as pr

    OUT.mkdir(parents=True, exist_ok=True)
    cold.set_cold_archive(False)
    cold.set_cold_eviction(False)

    orig_ensure = psc_opt.ensure_pack
    orig_bump = psc_opt.bump_pack_version
    orig_learn = pr.learn_transition

    stats = {
        "ensure_calls": 0,
        "rebuilds": 0,
        "hits": 0,
        "invalidations": 0,
        "learn": 0,
        "learn_update": 0,
        "learn_insert": 0,
        "learn_evict": 0,
        "rebuild_ns": [],
        "stage_by_action_ns": [],
        "stage_ante_ns": [],
        "rows_rebuilt": [],
        "channels": [],
        "actions_rebuilt": [],
        "versions_consumed": set(),
        "rebuild_never_hit_after": 0,
        "learn_actions": [],
    }

    def bump(store):
        stats["invalidations"] += 1
        return orig_bump(store)

    def learn(store, **kw):
        stats["learn"] += 1
        act = str(kw.get("action") or "")
        stats["learn_actions"].append(act)
        tr = store.get("transitions") or {}
        from mechanistic_mind.research.prospective_composition import transition_key, _q
        key = transition_key(_q(kw["antecedent"]), act)
        existed = key in tr
        would_evict = (not existed) and len(tr) >= 128
        if existed:
            stats["learn_update"] += 1
        else:
            stats["learn_insert"] += 1
            if would_evict:
                stats["learn_evict"] += 1
        return orig_learn(store, **kw)

    def ensure(store):
        stats["ensure_calls"] += 1
        pack = store.get("_psc_pack")
        ver = int(store.get("_psc_pack_version") or 0)
        hit = isinstance(pack, dict) and int(pack.get("version") or -1) == ver
        t0 = time.perf_counter_ns()
        out = orig_ensure(store)
        dt = time.perf_counter_ns() - t0
        if hit:
            stats["hits"] += 1
            return out
        stats["rebuilds"] += 1
        stats["rebuild_ns"].append(dt)
        pa = out.get("packed_actions") or {}
        ba = out.get("by_action") or {}
        nrows = sum(len(v) for v in ba.values())
        mmax = max((int(p.get("m") or 0) for p in pa.values()), default=0)
        stats["rows_rebuilt"].append(nrows)
        stats["channels"].append(mmax)
        stats["actions_rebuilt"].append(list(ba.keys()))
        stats["versions_consumed"].add((id(store), ver))
        return out

    psc_opt.ensure_pack = ensure
    psc_opt.bump_pack_version = bump
    pr.bump_pack_version = bump  # if rebound; learn imports bump at call time from psc_opt
    pr.learn_transition = learn

    print("load", CKPT, flush=True)
    with open(CKPT) as f:
        payload = json.load(f)

    rt = TwoAgentRuntime.restore(deepcopy(payload))
    tp.enable()
    tp.reset()
    rebuilds_before_step = 0
    per_tick = []
    for i in range(BENCH_TICKS):
        r0 = stats["rebuilds"]
        e0 = stats["ensure_calls"]
        inv0 = stats["invalidations"]
        ln0 = stats["learn"]
        tp.begin_tick()
        rt.step(1)
        rec = tp.end_tick(int(rt.tick))
        per_tick.append({
            "rebuilds": stats["rebuilds"] - r0,
            "ensure": stats["ensure_calls"] - e0,
            "inv": stats["invalidations"] - inv0,
            "learn": stats["learn"] - ln0,
            "compose_ns": (rec or {}).get("inc", {}).get("compose", 0) if rec else 0,
        })
    snap = tp.snapshot_stats()
    tp.disable()

    def bkt(name):
        for b in snap.get("buckets") or []:
            if b.get("name") == name:
                return b
        return {}

    ns = stats["rebuild_ns"]
    def pct(xs, p):
        if not xs:
            return None
        ys = sorted(xs)
        i = min(len(ys) - 1, max(0, int(round((p / 100.0) * (len(ys) - 1)))))
        return ys[i] / 1e6

    ticks = BENCH_TICKS
    compose = bkt("compose")
    cog = bkt("cognition")
    out = {
        "checkpoint_tick": payload.get("tick"),
        "bench_ticks": ticks,
        "end_tick": int(rt.tick),
        "ensure_pack_calls_per_tick": stats["ensure_calls"] / ticks,
        "ensure_pack_hits_per_tick": stats["hits"] / ticks,
        "actual_rebuilds_per_tick": stats["rebuilds"] / ticks,
        "invalidations_per_tick": stats["invalidations"] / ticks,
        "learn_events_per_tick": stats["learn"] / ticks,
        "learn_update_per_tick": stats["learn_update"] / ticks,
        "learn_insert_per_tick": stats["learn_insert"] / ticks,
        "learn_evict_per_tick": stats["learn_evict"] / ticks,
        "rows_per_rebuild_mean": (sum(stats["rows_rebuilt"]) / len(stats["rows_rebuilt"])) if stats["rows_rebuilt"] else 0,
        "channels_per_row": (sum(stats["channels"]) / len(stats["channels"])) if stats["channels"] else 0,
        "ensure_pack_ms_per_tick": (sum(ns) / 1e6) / ticks,
        "ms_per_rebuild": (sum(ns) / 1e6 / stats["rebuilds"]) if stats["rebuilds"] else 0,
        "p50_ms": pct(ns, 50),
        "p95_ms": pct(ns, 95),
        "max_ms": (max(ns) / 1e6) if ns else 0,
        "stage_by_action_ms_per_tick": None,
        "stage_ante_ms_per_tick": None,
        "unique_store_versions_consumed": len(stats["versions_consumed"]),
        "actions_per_rebuild_mean": (
            sum(len(a) for a in stats["actions_rebuilt"]) / len(stats["actions_rebuilt"])
            if stats["actions_rebuilt"] else 0
        ),
        "compose_ms_per_tick": compose.get("mean_ms_per_tick"),
        "compose_calls_per_tick": compose.get("calls_per_tick"),
        "cognition_ms_per_tick": cog.get("mean_ms_per_tick"),
        "tick_mean_ms": snap.get("mean_ms_per_tick"),
        "rebuilds_eq_learn": stats["rebuilds"] == stats["learn"] == stats["invalidations"],
        "learn_action_counts": {a: stats["learn_actions"].count(a) for a in sorted(set(stats["learn_actions"]))},
        "per_tick_rebuilds_unique": sorted(set(p["rebuilds"] for p in per_tick)),
        "per_tick_ensure_unique": sorted(set(p["ensure"] for p in per_tick)),
    }
    # redundant: all action partitions rebuilt vs 1 action learned
    avoidable = []
    for i, acts in enumerate(stats["actions_rebuilt"]):
        learn_act = stats["learn_actions"][i] if i < len(stats["learn_actions"]) else None
        rows = stats["rows_rebuilt"][i]
        # rows for learned action unknown here; store ratio rebuilt-all / 1-partition
        avoidable.append((len(acts) - 1) / max(1, len(acts)))
    out["mean_fraction_unrelated_partitions_rebuilt"] = (
        sum(avoidable) / len(avoidable) if avoidable else None
    )
    # rows changed = 1 per learn typically
    out["rows_changed_per_tick"] = stats["learn"] / ticks
    out["rows_rebuilt_per_tick"] = sum(stats["rows_rebuilt"]) / ticks
    out["redundant_rows_ratio"] = (
        1.0 - (out["rows_changed_per_tick"] / out["rows_rebuilt_per_tick"])
        if out["rows_rebuilt_per_tick"] else None
    )
    compose_ms = float(out["compose_ms_per_tick"] or 0)
    pack_ms = float(out["ensure_pack_ms_per_tick"] or 0)
    out["pack_frac_of_compose"] = (pack_ms / compose_ms) if compose_ms else None
    material = pack_ms >= 3.0 or (compose_ms and pack_ms >= 0.10 * compose_ms)
    out["rebuild_cost_material"] = bool(material)
    out["justified_by_3ms"] = pack_ms >= 3.0
    out["justified_by_10pct_compose"] = bool(compose_ms and pack_ms >= 0.10 * compose_ms)
    out["below_1ms"] = pack_ms < 1.0

    (OUT / "_forensic_raw.json").write_text(json.dumps(out, indent=2, default=str))
    print(json.dumps(out, indent=2, default=str))

    psc_opt.ensure_pack = orig_ensure
    psc_opt.bump_pack_version = orig_bump
    pr.learn_transition = orig_learn


if __name__ == "__main__":
    main()
