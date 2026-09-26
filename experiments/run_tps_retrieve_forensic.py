#!/usr/bin/env python3
"""TPS retrieve exact-work forensic. Measurement only — no TPS/TPE/compose change."""
from __future__ import annotations

import csv
import hashlib
import json
import sys
import time
from collections import Counter, defaultdict
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
OUT = ROOT / "results/beta31_tps_retrieve_forensic"
BENCH_TICKS = 80
OVERHEAD_TICKS = 20

# Stage timers around retrieve internals only (not per class item).
STAGES = (
    "cache_lookup",
    "query_window",
    "query_deltas",
    "query_sigs",
    "inner_retrieve",
    "matching_partial_in",
    "other_uncached",
)


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


def _csv(path: Path, headers, rows):
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for r in rows:
            w.writerow(r)


def caller_class(frame) -> str:
    name = frame.f_code.co_name
    file = frame.f_code.co_filename
    bn = Path(file).name
    if bn == "cognition.py" and name == "run_cognition_before_action":
        return "cog_predict_loop"
    if bn == "temporal_predictive_structure.py" and name == "diagnostic":
        return "tps_diagnostic"
    if bn == "temporal_prospection_bridge.py":
        return "tpb_collect"
    if bn == "predicted_context_prospection.py":
        return "pcp_collect"
    if bn == "temporal_prediction_error.py":
        return "tpe_retrieve"
    return f"{bn}:{name}"


def store_snapshot(tstore: dict) -> dict:
    inner = tstore.get("inner") or {}
    classes = inner.get("classes") or {}
    active = [c for c in classes.values() if isinstance(c, dict) and c.get("status") == "ACTIVE"]
    forgotten = [c for c in classes.values() if isinstance(c, dict) and c.get("status") == "FORGOTTEN"]
    ix = inner.get("_ix_action") or {}
    buckets = []
    for act, ids in sorted(ix.items(), key=lambda kv: -len(kv[1] or ())):
        buckets.append((act, len(ids or ())))
    ring = tstore.get("ring") or []
    sample_frag = ring[-1] if ring else {}
    return {
        "ring_n": len(ring),
        "ring_cap": int(tstore.get("window") and 16 or 16),
        "window": int(tstore.get("window") or 4),
        "lags": list(tstore.get("lags") or []),
        "inner_classes": len(classes),
        "inner_active": len(active),
        "inner_forgotten": len(forgotten),
        "inner_max_classes": 32,
        "ix_action_buckets": len(ix),
        "ix_bucket_sizes": buckets[:24],
        "mean_bucket": (sum(n for _, n in buckets) / len(buckets)) if buckets else 0,
        "max_bucket": max((n for _, n in buckets), default=0),
        "query_fields_last_obs": len(sample_frag) if isinstance(sample_frag, dict) else 0,
        "retrieve_cache_gen": int(tstore.get("_retrieve_cache_gen") or 0),
        "inner_ix_gen": int(inner.get("_ix_gen") or 0),
        "learns": int(tstore.get("learns") or 0),
        "retrieves": int(tstore.get("retrieves") or 0),
        "structure": "TPS outer {ring, lags, inner=PE store}; inner classes dict + _ix_action",
    }


def install_hooks(tps, pe, prl, store_ids: dict[int, int]):
    """Wrap retrieve internals. Restored by caller. No semantic change."""
    F = {
        "ns": {k: 0 for k in STAGES},
        "ns_cog": {k: 0 for k in STAGES},
        "scope_cog": False,
        "cog_uncached": 0,
        "cog_inner_prl": 0,
        "cog_inspected": 0,
        "cog_partial": 0,
        "cog_partial_ok": 0,
        "cog_window": 0,
        "cog_delta": 0,
        "cog_sigs": 0,
        "calls_outer": 0,
        "calls_uncached": 0,
        "calls_cached": 0,
        "calls_disabled": 0,
        "inner_prl": 0,
        "inner_pe": 0,
        "partial_in": 0,
        "partial_ok": 0,
        "partial_reject": 0,
        "items_inspected": 0,
        "items_accepted": 0,
        "hits_inner": 0,
        "window_builds": 0,
        "delta_builds": 0,
        "sigs": 0,
        "floats": 0,
        "recent_copies": 0,
        "result_dicts": 0,
        "sort_max_hits": 0,
        "sort_ops": 0,
        "dfrag_fields": 0,
        "dfrag_n": 0,
        "window_n_sum": 0,
        "query_ident_tick": [],
        "seq": [],
        "by_caller": Counter(),
        "by_agent_caller": Counter(),
        "by_action": Counter(),
        "by_lag": Counter(),
        "by_status": Counter(),
        "by_agent": Counter(),
        "agent_inspected": Counter(),
        "agent_ns": Counter(),
        "agent_calls": Counter(),
        "lag_inner_inspected": Counter(),
        "lag_inner_calls": Counter(),
        "lag_inner_ns": Counter(),
        "gen_at_call": [],
        "pcp_lag_calls": 0,
        "diag_calls": 0,
        "tpb_calls": 0,
        "cog_calls": 0,
        "in_uncached": 0,
        "in_retrieve": 0,
        "in_inner": False,
        "inner_act": None,
        "current_agent": None,
        "current_outer_lag": None,
        "tick_events": [],
        "store_versions_tick": [],
        "ident_hits": 0,
        "ident_miss": 0,
        "dfrag_sig_repeats": 0,
        "last_dfrag_sig": None,
        "alloc_dict": 0,
        "alloc_list": 0,
        "alloc_tuple": 0,
        "cache_hits_store": 0,
        "cache_miss_store": 0,
        "mean_c_calls": 0,
        "predict_delta_calls": 0,
        "cont_view_calls": 0,
        "linf_calls": 0,
        "relevant_key_lens": [],
    }

    orig = {
        "retrieve": tps.retrieve,
        "uncached": tps._retrieve_uncached,
        "window": tps.current_window,
        "deltas": tps._window_deltas,
        "copyf": tps._copy_window_fragment,
        "cont": tps._cont_view,
        "prl": prl.retrieve,
        "pe": pe.retrieve,
        "partial": prl._partial_in,
        "iter_act": pe.iter_active_classes_for_action,
        "floats": pe._floats,
        "sig": None,
        "mean_c": pe._class_mean_c,
        "pred": pe._predict_from_delta,
        "linf": pe._linf,
        "learn": tps.learn,
        "append": tps.append,
    }
    from mechanistic_mind.research.predictive_compression import _sig as orig_sig

    orig["sig"] = orig_sig

    def add_ns(stage, dt):
        F["ns"][stage] += dt
        if F["scope_cog"]:
            F["ns_cog"][stage] += dt

    def window_w(store, present=None):
        F["window_builds"] += 1
        if F["in_retrieve"]:
            t0 = time.perf_counter_ns()
            out = orig["window"](store, present)
            add_ns("query_window", time.perf_counter_ns() - t0)
            if F["scope_cog"]:
                F["cog_window"] += 1
            F["window_n_sum"] += len(out)
            F["alloc_list"] += 1
            return out
        return orig["window"](store, present)

    def deltas_w(frags):
        F["delta_builds"] += 1
        if F["in_retrieve"]:
            t0 = time.perf_counter_ns()
            out = orig["deltas"](frags)
            add_ns("query_deltas", time.perf_counter_ns() - t0)
            if F["scope_cog"]:
                F["cog_delta"] += 1
            F["dfrag_fields"] += len(out)
            F["dfrag_n"] += 1
            F["alloc_dict"] += 1
            return out
        return orig["deltas"](frags)

    def sig_w(payload):
        F["sigs"] += 1
        if F["in_retrieve"]:
            t0 = time.perf_counter_ns()
            out = orig["sig"](payload)
            add_ns("query_sigs", time.perf_counter_ns() - t0)
            if F["scope_cog"]:
                F["cog_sigs"] += 1
            return out
        return orig["sig"](payload)

    def floats_w(d):
        F["floats"] += 1
        if F["in_retrieve"]:
            F["alloc_dict"] += 1
        return orig["floats"](d)

    def copyf_w(f):
        F["recent_copies"] += 1
        F["alloc_dict"] += 1
        return orig["copyf"](f)

    def cont_w(pred, dfrag):
        F["cont_view_calls"] += 1
        F["alloc_dict"] += 1
        return orig["cont"](pred, dfrag)

    def partial_w(fragment, aabb, keys):
        F["partial_in"] += 1
        F["relevant_key_lens"].append(len(keys or []))
        if F["in_inner"]:
            t0 = time.perf_counter_ns()
            g = orig["partial"](fragment, aabb, keys)
            add_ns("matching_partial_in", time.perf_counter_ns() - t0)
            if F["scope_cog"]:
                F["cog_partial"] += 1
        else:
            g = orig["partial"](fragment, aabb, keys)
        if g.get("ok"):
            F["partial_ok"] += 1
            F["items_accepted"] += 1
            if F["scope_cog"]:
                F["cog_partial_ok"] += 1
        else:
            F["partial_reject"] += 1
        return g

    def iter_w(store, action):
        n = 0
        for cls in orig["iter_act"](store, action):
            n += 1
            F["items_inspected"] += 1
            if F["scope_cog"]:
                F["cog_inspected"] += 1
            ag = F["current_agent"]
            if ag is not None:
                F["agent_inspected"][ag] += 1
            lag = F["inner_act"]
            if lag is not None:
                F["lag_inner_inspected"][str(lag)] += 1
            yield cls

    def mean_w(cls):
        F["mean_c_calls"] += 1
        return orig["mean_c"](cls)

    def pred_w(q, d):
        F["predict_delta_calls"] += 1
        F["alloc_dict"] += 1
        return orig["pred"](q, d)

    def linf_w(a, b):
        F["linf_calls"] += 1
        return orig["linf"](a, b)

    def prl_w(eq_store, fragment, action, *, meta=None, count=True):
        if F["in_uncached"]:
            F["inner_prl"] += 1
            if F["scope_cog"]:
                F["cog_inner_prl"] += 1
            F["inner_act"] = action
            F["in_inner"] = True
            F["lag_inner_calls"][str(action)] += 1
            t0 = time.perf_counter_ns()
            try:
                got = orig["prl"](eq_store, fragment, action, meta=meta, count=count)
            finally:
                dt = time.perf_counter_ns() - t0
                add_ns("inner_retrieve", dt)
                F["lag_inner_ns"][str(action)] += dt
                F["in_inner"] = False
                F["inner_act"] = None
            if got.get("status") in {"MATCH", "CONFLICT"}:
                F["hits_inner"] += 1
            return got
        return orig["prl"](eq_store, fragment, action, meta=meta, count=count)

    def pe_w(store, fragment, action, *, count=True):
        if F["in_uncached"]:
            F["inner_pe"] += 1
            t0 = time.perf_counter_ns()
            got = orig["pe"](store, fragment, action, count=count)
            add_ns("inner_retrieve", time.perf_counter_ns() - t0)
            return got
        return orig["pe"](store, fragment, action, count=count)

    def uncached_w(store, present, action, *, lag=None, meta=None):
        F["calls_uncached"] += 1
        if F["scope_cog"]:
            F["cog_uncached"] += 1
        F["in_uncached"] += 1
        inner0 = F["ns"]["inner_retrieve"]
        match0 = F["ns"]["matching_partial_in"]
        q0 = F["ns"]["query_window"] + F["ns"]["query_deltas"] + F["ns"]["query_sigs"]
        t0 = time.perf_counter_ns()
        try:
            got = orig["uncached"](store, present, action, lag=lag, meta=meta)
        finally:
            dt = time.perf_counter_ns() - t0
            accounted = (
                (F["ns"]["inner_retrieve"] - inner0)
                + (F["ns"]["matching_partial_in"] - match0)
                + (F["ns"]["query_window"] + F["ns"]["query_deltas"] + F["ns"]["query_sigs"] - q0)
            )
            add_ns("other_uncached", max(0, dt - accounted))
            F["in_uncached"] -= 1
        F["result_dicts"] += 1
        F["alloc_dict"] += 1
        F["by_status"][str(got.get("status"))] += 1
        n_cand = len(got.get("candidates") or [])
        if n_cand > 1:
            F["sort_ops"] += 1
            F["sort_max_hits"] += n_cand
        return got

    def retrieve_w(store, present, action, *, lag=None, count=True, meta=None):
        F["calls_outer"] += 1
        fr = sys._getframe(1)
        cc = caller_class(fr)
        F["in_retrieve"] += 1
        F["scope_cog"] = cc == "cog_predict_loop"
        ag = store_ids.get(id(store))
        F["current_agent"] = ag
        F["current_outer_lag"] = lag
        if ag is not None:
            F["agent_calls"][ag] += 1
        F["by_caller"][cc] += 1
        F["by_agent_caller"][(ag, cc)] += 1
        F["by_action"][str(action)] += 1
        F["by_lag"][str(lag)] += 1
        if cc == "cog_predict_loop":
            F["cog_calls"] += 1
        elif cc == "tps_diagnostic":
            F["diag_calls"] += 1
        elif cc == "tpb_collect":
            F["tpb_calls"] += 1
        elif cc == "pcp_collect":
            F["pcp_lag_calls"] += 1

        gen = (
            int(store.get("_retrieve_cache_gen") or 0),
            int((store.get("inner") or {}).get("_ix_gen") or 0),
        )
        w = int(store.get("window") or 4)
        ring = store.get("ring") or []
        window_key = tuple(orig["sig"](f) for f in ring[-w:])
        F["alloc_tuple"] += 1
        use_rel = bool(meta is not None and meta.get("enabled"))
        ident = (ag, gen, window_key, str(action), None if lag is None else int(lag), use_rel)
        F["query_ident_tick"].append(ident)
        F["gen_at_call"].append((ag, gen, cc, str(action), lag))
        F["seq"].append(("retrieve", ag, cc, str(action), lag, gen))

        hits_before = int(store.get("_retrieve_cache_hits") or 0)
        t0 = time.perf_counter_ns()
        try:
            got = orig["retrieve"](store, present, action, lag=lag, count=count, meta=meta)
        finally:
            dt = time.perf_counter_ns() - t0
            F["ns"]["retrieve_wall"] = F["ns"].get("retrieve_wall", 0) + dt
            if int(store.get("_retrieve_cache_hits") or 0) > hits_before:
                add_ns("cache_lookup", dt)
                F["calls_cached"] += 1
            if ag is not None:
                F["agent_ns"][ag] += dt
            F["in_retrieve"] -= 1
            F["scope_cog"] = False
            F["current_agent"] = None
        return got

    def learn_w(store, **kw):
        ag = store_ids.get(id(store))
        gen = (
            int(store.get("_retrieve_cache_gen") or 0),
            int((store.get("inner") or {}).get("_ix_gen") or 0),
        )
        F["seq"].append(("learn", ag, "tps_learn", kw.get("action"), None, gen))
        return orig["learn"](store, **kw)

    def append_w(store, fragment):
        ag = store_ids.get(id(store))
        gen = (
            int(store.get("_retrieve_cache_gen") or 0),
            int((store.get("inner") or {}).get("_ix_gen") or 0),
        )
        F["seq"].append(("append", ag, "tps_append", None, None, gen))
        return orig["append"](store, fragment)

    tps.current_window = window_w
    tps._window_deltas = deltas_w
    tps._copy_window_fragment = copyf_w
    tps._cont_view = cont_w
    tps._retrieve_uncached = uncached_w
    tps.retrieve = retrieve_w
    tps.learn = learn_w
    tps.append = append_w
    prl.retrieve = prl_w
    pe.retrieve = pe_w
    prl._partial_in = partial_w
    pe.iter_active_classes_for_action = iter_w
    pe._floats = floats_w
    pe._class_mean_c = mean_w
    pe._predict_from_delta = pred_w
    pe._linf = linf_w
    tps._sig = sig_w
    prl._floats = floats_w

    def uninstall():
        tps.current_window = orig["window"]
        tps._window_deltas = orig["deltas"]
        tps._copy_window_fragment = orig["copyf"]
        tps._cont_view = orig["cont"]
        tps._retrieve_uncached = orig["uncached"]
        tps.retrieve = orig["retrieve"]
        tps.learn = orig["learn"]
        tps.append = orig["append"]
        prl.retrieve = orig["prl"]
        pe.retrieve = orig["pe"]
        prl._partial_in = orig["partial"]
        pe.iter_active_classes_for_action = orig["iter_act"]
        pe._floats = orig["floats"]
        pe._class_mean_c = orig["mean_c"]
        pe._predict_from_delta = orig["pred"]
        pe._linf = orig["linf"]
        tps._sig = orig["sig"]
        prl._floats = orig["floats"]

    return F, uninstall, orig


def analyze_seq(seq):
    """Per-tick retrieve vs learn order on agent TPS stores only (agent not None)."""
    ticks = []
    cur = []
    # seq is global; we split by seeing learn after a stretch of retrieves
    # Better: group by agent consecutive events in cognition order (learn, append, retrieves...)
    by_agent_blocks = defaultdict(list)
    for ev in seq:
        kind, ag, *_ = ev
        if ag is None:
            continue
        by_agent_blocks[ag].append(ev)
    # Reconstruct per (agent, cycle): learn/append then retrieves until next learn
    orders = Counter()
    version_changes_during_retrieve_run = []
    retrieve_runs = []
    for ag, evs in by_agent_blocks.items():
        run = []
        last_kind = None
        for ev in evs:
            kind = ev[0]
            if kind == "learn" and run and any(x[0] == "retrieve" for x in run):
                retrieve_runs.append((ag, run))
                run = [ev]
            else:
                run.append(ev)
            last_kind = kind
        if run:
            retrieve_runs.append((ag, run))
    for ag, run in retrieve_runs:
        kinds = [e[0] for e in run]
        compact = []
        for k in kinds:
            if not compact or compact[-1] != k:
                compact.append(k)
        orders["-".join(compact)] += 1
        gens = [e[5] for e in run if e[0] == "retrieve"]
        version_changes_during_retrieve_run.append(len(set(gens)))
    return orders, version_changes_during_retrieve_run


def dup_stats(idents, n_ticks):
    # idents is flat list across ticks — we need per-tick. We'll chunk by recording
    # length per tick in the driver.
    return {}


def main() -> None:
    from mechanistic_mind.model.tiktaalik import tiktaalik_cognition_config
    from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
    from mechanistic_mind.research import pe_cold_archive as cold
    from mechanistic_mind.research import psc_opt
    from mechanistic_mind.research import tick_profiler as tp
    from mechanistic_mind.research import temporal_predictive_structure as tps
    from mechanistic_mind.research import predictive_equivalence as pe
    from mechanistic_mind.research import predictive_relevance as prl
    from mechanistic_mind.physical_system.actions import available_actions, OSC_ACTIONS

    OUT.mkdir(parents=True, exist_ok=True)

    assert psc_opt.packed_l1_mode() == "auto"
    src = Path(psc_opt.__file__).read_text()
    assert "def soft_match_packed_matrix" in src
    assert "hit = soft_match_packed_matrix" in src
    tps_src = Path(tps.__file__).read_text()
    assert "def _retrieve_uncached" in tps_src
    assert "Same-tick memo" in tps_src

    cold.set_cold_archive(False)
    cold.set_cold_eviction(False)

    print("load", CKPT, flush=True)
    with open(CKPT) as f:
        payload = json.load(f)
    source_tick = payload.get("tick")

    def restore():
        return TwoAgentRuntime.restore(deepcopy(payload))

    rt = restore()
    slot0 = rt.slots[0]
    cog = slot0.config.cognition
    vis = slot0.config.near_field_exteroception
    stock = tiktaalik_cognition_config()
    cog_d = cog.to_dict()
    stock_d = stock.to_dict()
    diffs = {k: {"stock": stock_d.get(k), "runtime": cog_d.get(k)} for k in cog_d if cog_d.get(k) != stock_d.get(k)}
    classification = "STOCK_BETA31" if not diffs else "BETA31_WITH_RESEARCH_OVERRIDES"
    fp_src = json.dumps(
        {
            "cognition": cog_d,
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
    fingerprint = hashlib.sha1(fp_src.encode()).hexdigest()[:16]
    assert fingerprint == "b8584ee48f712d91", fingerprint

    stores0 = [store_snapshot(rt.slots[i].cognition.get("temporal") or {}) for i in range(2)]
    tpe0 = [rt.slots[i].cognition.get("temporal_prediction_error") or {} for i in range(2)]

    # --- overhead baseline (uninstrumented) ---
    rt_oh = restore()
    cold.set_cold_archive(False)
    cold.set_cold_eviction(False)
    tp.enable()
    tp.reset()
    walls_oh = []
    for _ in range(OVERHEAD_TICKS):
        tp.begin_tick()
        t0 = time.perf_counter()
        rt_oh.step(1)
        walls_oh.append((time.perf_counter() - t0) * 1000.0)
        tp.end_tick(int(rt_oh.tick))
    snap_oh = tp.snapshot_stats()
    tp.disable()
    tps_oh = float(_bkt(snap_oh, "tps_retrieve").get("mean_ms_per_tick") or 0)

    # --- instrumented ---
    rt = restore()
    store_ids = {id(rt.slots[i].cognition["temporal"]): i for i in range(2)}
    F, uninstall, _orig = install_hooks(tps, pe, prl, store_ids)

    ident_per_tick = []
    gen_per_tick = []
    seq_marks = [0]
    cache_hits_tick = []
    cache_miss_tick = []

    tp.enable()
    tp.reset()
    walls = []
    for ti in range(BENCH_TICKS):
        # refresh store ids (dicts persist)
        store_ids.clear()
        for i in range(2):
            store_ids[id(rt.slots[i].cognition["temporal"])] = i
        n_ident0 = len(F["query_ident_tick"])
        n_seq0 = len(F["seq"])
        hits0 = sum(int((rt.slots[i].cognition.get("temporal") or {}).get("_retrieve_cache_hits") or 0) for i in range(2))
        miss0 = sum(int((rt.slots[i].cognition.get("temporal") or {}).get("_retrieve_cache_misses") or 0) for i in range(2))
        tp.begin_tick()
        t0 = time.perf_counter()
        rt.step(1)
        walls.append((time.perf_counter() - t0) * 1000.0)
        tp.end_tick(int(rt.tick))
        ident_per_tick.append(F["query_ident_tick"][n_ident0:])
        gen_per_tick.append(F["gen_at_call"][n_ident0:])
        seq_marks.append(len(F["seq"]))
        hits1 = sum(int((rt.slots[i].cognition.get("temporal") or {}).get("_retrieve_cache_hits") or 0) for i in range(2))
        miss1 = sum(int((rt.slots[i].cognition.get("temporal") or {}).get("_retrieve_cache_misses") or 0) for i in range(2))
        cache_hits_tick.append(hits1 - hits0)
        cache_miss_tick.append(miss1 - miss0)

    snap = tp.snapshot_stats()
    tp.disable()
    uninstall()

    n = max(1, BENCH_TICKS)
    cog_ms = float(_bkt(snap, "cognition").get("mean_ms_per_tick") or 0)
    tps_r = _bkt(snap, "tps_retrieve")
    tps_ms = float(tps_r.get("mean_ms_per_tick") or 0)
    tps_calls = float(tps_r.get("calls_per_tick") or 0)
    tps_us = float(tps_r.get("mean_us_per_call") or 0)

    stores1 = [store_snapshot(rt.slots[i].cognition.get("temporal") or {}) for i in range(2)]

    # Duplicate queries: cog_predict_loop only (the 10-call span)
    def cog_idents(chunk):
        # ident includes agent; we don't have caller in ident — use gen_per_tick parallel
        return chunk

    dup_rows = []
    unique_tick = []
    dup_tick = []
    ident_cog_unique = []
    for i, chunk in enumerate(ident_per_tick):
        gens = gen_per_tick[i]
        cog = [ident for ident, g in zip(chunk, gens) if g[2] == "cog_predict_loop"]
        u = len(set(cog))
        tot = len(cog)
        unique_tick.append(u)
        dup_tick.append(max(0, tot - u))
        ident_cog_unique.append(u)
        dup_rows.append((i, tot, u, max(0, tot - u), (tot - u) / tot if tot else 0))

    # all callers
    unique_all = []
    for chunk in ident_per_tick:
        unique_all.append(len(set(chunk)))

    mean = lambda xs: sum(xs) / len(xs) if xs else 0.0

    # overlap: same (agent, gen, window) different action among cog calls
    overlap_high = []
    overlap_ident = []
    for chunk, gens in zip(ident_per_tick, gen_per_tick):
        cog = [(ident, g) for ident, g in zip(chunk, gens) if g[2] == "cog_predict_loop"]
        bases = [ident[:3] for ident, _ in cog]  # agent, gen, window
        tot = len(cog)
        uniq_base = len(set(bases))
        overlap_high.append((tot - uniq_base) / tot if tot else 0)
        overlap_ident.append(uniq_base)

    # store version uniqueness among cog retrieves per tick
    ver_unique = []
    ver_changes = []
    for gens in gen_per_tick:
        cog = [g for g in gens if g[2] == "cog_predict_loop"]
        by_ag = defaultdict(list)
        for g in cog:
            by_ag[g[0]].append(g[1])
        ch = 0
        for ag, vs in by_ag.items():
            ch += max(0, len(set(vs)) - 1)
        ver_changes.append(ch)
        ver_unique.append(len(set((g[0], g[1]) for g in cog)))

    orders, vers_runs = analyze_seq(F["seq"])

    # stage ms
    def ns_to_ms_tick(ns):
        return (ns / 1e6) / n

    stage_rows = []
    stage_sum = 0.0
    for k in STAGES:
        ms = ns_to_ms_tick(F["ns"][k])
        stage_sum += ms
        calls = tps_calls if tps_calls else F["cog_calls"] / n
        stage_rows.append((k, ms, ms / calls if calls else 0, 100.0 * ms / tps_ms if tps_ms else 0))

    # Note: cache_lookup + query_* wrap includes work outside tps_retrieve span
    # (diagnostic/pcp/tpb). Split by attributing only cog fraction.
    cog_frac = (F["cog_calls"] / F["calls_outer"]) if F["calls_outer"] else 1.0
    # inner_retrieve and matching are only counted in uncached; uncached mostly cog
    uncached_frac = (F["calls_uncached"] / max(1, F["calls_outer"]))

    overhead_pct = None
    if tps_oh > 0:
        overhead_pct = 100.0 * (tps_ms - tps_oh) / tps_oh

    actions = list(available_actions())
    osc_in = [a for a in actions if a in OSC_ACTIONS]

    # write CSVs
    _csv(
        OUT / "tps_call_classes.csv",
        ["call_class", "calls_total", "calls_tick", "caller", "agent", "lag", "query", "store", "consumer"],
        [
            (
                f"agent_{ag}_cog_{act}",
                F["by_agent_caller"].get((ag, "cog_predict_loop"), 0) and "see_by_action",
                "",
                "run_cognition_before_action.cog_predict_loop",
                ag,
                "None(all LAGS 1-4 inner)",
                f"current_window+deltas + action={act}",
                "state['temporal'].inner PE classes",
                "predictions / compose entry via TPB",
            )
            for ag in (0, 1)
            for act in actions
        ],
    )
    # overwrite with accurate action split
    act_rows = []
    for (ag, cc), c in sorted(F["by_agent_caller"].items()):
        act_rows.append((f"agent_{ag}_{cc}", c, c / n, cc, ag, "see_by_lag", "window+action", "temporal.inner", cc))
    _csv(
        OUT / "tps_call_classes.csv",
        ["call_class", "calls_total", "calls_tick", "caller", "agent", "lag", "query", "store", "consumer"],
        act_rows,
    )
    _csv(
        OUT / "tps_stage_costs.csv",
        ["stage", "ns_total_cog", "ms_tick_cog", "ms_call", "pct_tps_retrieve_instrumented", "note"],
        [
            (
                k,
                F["ns_cog"][k],
                (F["ns_cog"][k] / 1e6) / n,
                ((F["ns_cog"][k] / 1e6) / n) / tps_calls if tps_calls else 0,
                100.0 * ((F["ns_cog"][k] / 1e6) / n) / tps_ms if tps_ms else 0,
                "cog_predict_loop tps_retrieve span only; matching nested inside inner_retrieve",
            )
            for k in STAGES
        ],
    )
    _csv(
        OUT / "tps_work_counts.csv",
        ["metric", "total", "per_tick", "per_outer_call", "per_cog_call"],
        [
            ("outer_retrieve_all_callers", F["calls_outer"], F["calls_outer"] / n, 1, F["calls_outer"] / max(1, F["cog_calls"])),
            ("cog_predict_tps_retrieve", F["cog_calls"], F["cog_calls"] / n, "", 1),
            ("uncached", F["calls_uncached"], F["calls_uncached"] / n, F["calls_uncached"] / max(1, F["calls_outer"]), F["calls_uncached"] / max(1, F["cog_calls"])),
            ("inner_prl_retrieve", F["inner_prl"], F["inner_prl"] / n, F["inner_prl"] / max(1, F["calls_outer"]), F["inner_prl"] / max(1, F["cog_calls"])),
            ("items_inspected", F["items_inspected"], F["items_inspected"] / n, F["items_inspected"] / max(1, F["calls_outer"]), F["items_inspected"] / max(1, F["cog_calls"])),
            ("partial_in", F["partial_in"], F["partial_in"] / n, F["partial_in"] / max(1, F["calls_outer"]), F["partial_in"] / max(1, F["cog_calls"])),
            ("partial_ok", F["partial_ok"], F["partial_ok"] / n, "", ""),
            ("partial_reject", F["partial_reject"], F["partial_reject"] / n, "", ""),
            ("window_builds", F["window_builds"], F["window_builds"] / n, "", ""),
            ("delta_builds", F["delta_builds"], F["delta_builds"] / n, "", ""),
            ("sigs", F["sigs"], F["sigs"] / n, "", ""),
            ("floats_copies", F["floats"], F["floats"] / n, "", ""),
            ("recent_fragment_copies", F["recent_copies"], F["recent_copies"] / n, "", ""),
            ("mean_c", F["mean_c_calls"], F["mean_c_calls"] / n, "", ""),
            ("linf", F["linf_calls"], F["linf_calls"] / n, "", ""),
            ("predict_from_delta", F["predict_delta_calls"], F["predict_delta_calls"] / n, "", ""),
            ("cont_view", F["cont_view_calls"], F["cont_view_calls"] / n, "", ""),
            ("dfrag_fields_sum", F["dfrag_fields"], F["dfrag_fields"] / n, "", F["dfrag_fields"] / max(1, F["dfrag_n"])),
            ("pcp_tps_retrieve", F["pcp_lag_calls"], F["pcp_lag_calls"] / n, "", ""),
            ("diag_tps_retrieve", F["diag_calls"], F["diag_calls"] / n, "", ""),
            ("tpb_tps_retrieve", F["tpb_calls"], F["tpb_calls"] / n, "", ""),
        ],
    )
    _csv(
        OUT / "tps_duplicate_queries.csv",
        ["tick_i", "cog_calls", "unique_identities", "duplicate_calls", "duplicate_fraction", "unique_window_store", "overlap_same_window_frac", "store_version_changes_across_agents"],
        [
            (
                i,
                ident_per_tick[i] and len([1 for g in gen_per_tick[i] if g[2] == "cog_predict_loop"]),
                unique_tick[i],
                dup_tick[i],
                (dup_tick[i] / unique_tick[i] if False else (dup_tick[i] / max(1, unique_tick[i] + dup_tick[i]))),
                overlap_ident[i],
                overlap_high[i],
                ver_changes[i],
            )
            for i in range(n)
        ],
    )
    _csv(
        OUT / "tps_store_structure.csv",
        ["when", "agent", "ring_n", "window", "lags", "inner_classes", "inner_active", "inner_forgotten", "ix_buckets", "mean_bucket", "max_bucket", "learns", "retrieves", "ix_gen"],
        [
            (
                when,
                i,
                s["ring_n"],
                s["window"],
                "|".join(map(str, s["lags"])),
                s["inner_classes"],
                s["inner_active"],
                s["inner_forgotten"],
                s["ix_action_buckets"],
                f"{s['mean_bucket']:.3f}",
                s["max_bucket"],
                s["learns"],
                s["retrieves"],
                s["inner_ix_gen"],
            )
            for when, ss in (("start", stores0), ("end", stores1))
            for i, s in enumerate(ss)
        ],
    )
    bucket_rows = []
    for i, s in enumerate(stores1):
        for act, sz in s["ix_bucket_sizes"]:
            bucket_rows.append((i, act, sz))
    _csv(OUT / "tps_inner_action_buckets.csv", ["agent", "action_lag_key", "active_classes"], bucket_rows)

    _csv(
        OUT / "tps_agent_lag_split.csv",
        ["split", "key", "calls_total", "calls_tick", "items_inspected_total", "ms_tick_wall_wrap"],
        (
            [("agent", ag, F["agent_calls"][ag], F["agent_calls"][ag] / n, F["agent_inspected"][ag], (F["agent_ns"][ag] / 1e6) / n) for ag in (0, 1)]
            + [("lag_inner_action", k, F["lag_inner_calls"][k], F["lag_inner_calls"][k] / n, F["lag_inner_inspected"].get(k.split("|L")[-1] if "|L" in k else k, 0), (F["lag_inner_ns"][k] / 1e6) / n) for k in sorted(F["lag_inner_calls"])]
        ),
    )

    mean_rel = mean(F["relevant_key_lens"]) if F["relevant_key_lens"] else 0
    dfrag_mean = F["dfrag_fields"] / max(1, F["dfrag_n"])

    summary = {
        "source_run": "psyweb-20260925T071301.453542Z-749aeea4",
        "source_tick": source_tick,
        "profile_start_tick": source_tick,
        "profile_end_tick": int(rt.tick),
        "intentional_ticks": BENCH_TICKS,
        "overhead_ticks": OVERHEAD_TICKS,
        "runtime_fingerprint": fingerprint,
        "classification": classification,
        "packed_l1_mode": psc_opt.packed_l1_mode(),
        "actions": actions,
        "n_actions": len(actions),
        "physical_OSC_compose_candidates": len(osc_in),
        "cognition_ms_tick": cog_ms,
        "tps_retrieve_profiler": {
            "calls_per_tick": tps_calls,
            "ms_tick": tps_ms,
            "ms_call": tps_us / 1000.0,
            "percent_cognition": 100.0 * tps_ms / cog_ms if cog_ms else 0,
        },
        "tps_retrieve_uninstrumented_ms_tick": tps_oh,
        "profiler_overhead_pct_vs_uninstrumented_tps": overhead_pct,
        "outer_calls_tick_all": F["calls_outer"] / n,
        "cog_calls_tick": F["cog_calls"] / n,
        "uncached_tick": F["calls_uncached"] / n,
        "inner_prl_tick": F["inner_prl"] / n,
        "items_inspected_tick": F["items_inspected"] / n,
        "items_inspected_per_cog_call": F["cog_inspected"] / max(1, F["cog_calls"]),
        "cog_uncached_tick": F["cog_uncached"] / n,
        "cog_inner_prl_tick": F["cog_inner_prl"] / n,
        "cog_inspected_tick": F["cog_inspected"] / n,
        "cog_partial_tick": F["cog_partial"] / n,
        "cog_partial_ok_tick": F["cog_partial_ok"] / n,
        "stage_ms_tick_cog_only": {k: (F["ns_cog"][k] / 1e6) / n for k in STAGES},
        "stage_sum_ms_tick_cog": sum((F["ns_cog"][k] / 1e6) / n for k in STAGES),
        "partial_in_tick": F["partial_in"] / n,
        "partial_ok_tick": F["partial_ok"] / n,
        "accepted_per_cog_call": F["partial_ok"] / max(1, F["cog_calls"]),
        "dfrag_fields_mean": dfrag_mean,
        "relevant_keys_mean": mean_rel,
        "duplicate_cog": {
            "mean_calls": mean([dup_rows[i][1] for i in range(n)]),
            "mean_unique": mean(unique_tick),
            "mean_duplicate_calls": mean(dup_tick),
            "mean_duplicate_fraction": mean([r[4] for r in dup_rows]),
            "mean_unique_window_store": mean(overlap_ident),
            "mean_overlap_same_window": mean(overlap_high),
        },
        "store_version": {
            "mean_changes_during_cog_retrieves": mean(ver_changes),
            "mean_unique_agent_gen_pairs": mean(ver_unique),
            "order_counter": dict(orders),
        },
        "cache_hits_per_tick": mean(cache_hits_tick),
        "cache_misses_per_tick": mean(cache_miss_tick),
        "by_caller": dict(F["by_caller"]),
        "by_action": dict(F["by_action"]),
        "by_lag": dict(F["by_lag"]),
        "by_status": dict(F["by_status"]),
        "agent_calls": dict(F["agent_calls"]),
        "agent_ms_tick": {str(k): (v / 1e6) / n for k, v in F["agent_ns"].items()},
        "stage_ms_tick_all_callers": {k: ns_to_ms_tick(F["ns"][k]) for k in STAGES},
        "stage_sum_ms_tick": stage_sum,
        "stores_start": stores0,
        "stores_end": stores1,
        "tpe_lag_keys": [list((t.get("lags") or {}).keys()) for t in tpe0],
        "seq_sample": F["seq"][:40],
    }
    (OUT / "tps_forensic_raw.json").write_text(json.dumps(summary, indent=2, default=str))

    # compact reports written after this JSON so the markdown can use numbers
    (OUT / "_summary_for_md.json").write_text(json.dumps(summary, indent=2, default=str))
    print("TPS retrieve forensic ticks", BENCH_TICKS, "calls/tick", tps_calls, "ms/tick", tps_ms, flush=True)
    print("cog_calls/tick", F["cog_calls"] / n, "unique identities", mean(unique_tick), "dup frac", mean([r[4] for r in dup_rows]), flush=True)
    print("inner_prl/tick", F["inner_prl"] / n, "inspected/tick", F["items_inspected"] / n, flush=True)
    print("stages_cog", {k: round((F["ns_cog"][k] / 1e6) / n, 3) for k in STAGES}, flush=True)
    print("cog_inner", F["cog_inner_prl"] / n, "cog_inspected", F["cog_inspected"] / n, "cog_partial_ok", F["cog_partial_ok"] / n, flush=True)
    print("overhead_pct", overhead_pct, "uninstr", tps_oh, flush=True)
    print("callers", dict(F["by_caller"]), flush=True)
    print("orders", dict(orders), flush=True)


if __name__ == "__main__":
    main()
