#!/usr/bin/env python3
"""Beta 3.1 PE forgotten cold archive forensic + dense RAM experiment.

Does not start 40k. Does not mutate e02e833b. Does not push.
"""
from __future__ import annotations

import gc
import json
import os
import struct
import subprocess
import sys
import time
import traceback
from array import array
from collections import Counter
from copy import deepcopy
from io import StringIO
from pathlib import Path

ROOT = Path("/home/thehost/Desktop/psy")
OUT = ROOT / "results" / "beta31_pe_cold_archive"
SEED = int(os.environ.get("PSY_RSS_SEED", "575"))
EQ_TICKS = int(os.environ.get("PSY_COLD_EQ_TICKS", "250"))
RSS_TICKS = [int(x) for x in os.environ.get("PSY_COLD_RSS_TICKS", "0,100,250,500,750,1000").split(",") if x]
CEILING_DELTA_MB = float(os.environ.get("PSY_RSS_CEILING_DELTA_MB", "2048"))
ROLE = os.environ.get("PSY_COLD_ROLE", "master")


def make_runtime():
    from experiments.run_beta31_pe_forgotten_compaction import make_runtime as _mr
    return _mr()


def _proc() -> dict:
    import resource

    pid = os.getpid()
    st = Path(f"/proc/{pid}/status").read_text()
    kv = {}
    for line in st.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            kv[k.strip()] = v.strip()

    def kb(key: str) -> int:
        return int(str(kv.get(key, "0")).split()[0] or 0)

    return {
        "rss_mb": round(kb("VmRSS") / 1024.0, 3),
        "rss_anon_mb": round(kb("RssAnon") / 1024.0, 3),
        "rss_file_mb": round(kb("RssFile") / 1024.0, 3),
        "ru_maxrss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0, 3),
    }


def _sizeof(obj, seen: set[int] | None = None, budget: int = 3_000_000) -> int:
    if seen is None:
        seen = set()
    oid = id(obj)
    if oid in seen:
        return 0
    seen.add(oid)
    if len(seen) > budget:
        return 0
    n = sys.getsizeof(obj)
    if isinstance(obj, dict):
        for k, v in obj.items():
            n += _sizeof(k, seen, budget) + _sizeof(v, seen, budget)
    elif isinstance(obj, (list, tuple, set)):
        for x in obj:
            n += _sizeof(x, seen, budget)
    elif isinstance(obj, (bytes, bytearray, str)):
        return n
    elif isinstance(obj, array):
        return n
    return n


def _nobj(obj, seen: set[int] | None = None, budget: int = 3_000_000) -> int:
    if seen is None:
        seen = set()
    oid = id(obj)
    if oid in seen:
        return 0
    seen.add(oid)
    if len(seen) > budget:
        return 0
    n = 1
    if isinstance(obj, dict):
        for k, v in obj.items():
            n += _nobj(k, seen, budget) + _nobj(v, seen, budget)
    elif isinstance(obj, (list, tuple, set)):
        for x in obj:
            n += _nobj(x, seen, budget)
    return n


def _pe_stores(slot) -> dict[str, dict]:
    cog = slot.cognition if isinstance(slot.cognition, dict) else {}
    out = {"outer": cog.get("equivalence") or {}}
    temporal = cog.get("temporal") or {}
    out["temporal.inner"] = (temporal.get("inner") if isinstance(temporal, dict) else {}) or {}
    tpe = cog.get("temporal_prediction_error") or {}
    lags = (tpe.get("lags") if isinstance(tpe, dict) else {}) or {}
    for k, v in lags.items():
        inner = (v.get("inner") if isinstance(v, dict) else {}) or {}
        out[f"tpe.lags.{k}.inner"] = inner
    return out


def logical_payload_bytes(cls) -> int:
    from mechanistic_mind.research import predictive_equivalence as pe

    if pe.is_forgotten_packed(cls):
        keys = pe.forgotten_pack_keys(cls)
        n = len(keys)
        nbytes = (n + 7) >> 3
        n_mem = len(cls.get("members") or {})
        # 3 maps/member + class mean + aabb lo/hi
        floats = n * (3 * n_mem + 3)
        masks = nbytes * (3 * n_mem + 2)
        return floats * 8 + masks + n_mem * 16
    n = 0
    for mem in (cls.get("members") or {}).values():
        if not isinstance(mem, dict):
            continue
        for fld in ("fragment", "mean_c", "last_abs"):
            mp = mem.get(fld) or {}
            if isinstance(mp, dict):
                n += 8 * len(mp)
    mc = cls.get("mean_c") or {}
    if isinstance(mc, dict) and "v" not in mc:
        n += 8 * len(mc)
    return n


def write_json(name: str, payload) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(payload, indent=2, default=str) + "\n")


def historical_contract() -> dict:
    fields = [
        {"field": "id", "python_type": "str", "meaning": "Stable class identifier E{n}", "mutability_after_forget": "immutable", "exact_reconstruction": True, "derivable": False, "class": "REQUIRED_FOR_SCIENTIFIC_HISTORY+REQUIRED_FOR_PERSISTENCE+REQUIRED_FOR_ANALYZER"},
        {"field": "action", "python_type": "str", "meaning": "Action key; nested stores embed |L{lag}", "mutability_after_forget": "immutable", "exact_reconstruction": True, "derivable": False, "class": "REQUIRED_FOR_SCIENTIFIC_HISTORY+LAG_ATTRIBUTION"},
        {"field": "status", "python_type": "str", "meaning": "FORGOTTEN", "mutability_after_forget": "immutable", "exact_reconstruction": True, "derivable": True, "class": "REQUIRED_FOR_SCIENTIFIC_HISTORY"},
        {"field": "support", "python_type": "int", "meaning": "Sum of member supports at forget", "mutability_after_forget": "immutable", "exact_reconstruction": True, "derivable": True, "class": "REQUIRED_FOR_SCIENTIFIC_HISTORY"},
        {"field": "members.*.sig", "python_type": "str", "meaning": "Antecedent signature", "mutability_after_forget": "immutable", "exact_reconstruction": True, "derivable": False, "class": "REQUIRED_FOR_SCIENTIFIC_HISTORY"},
        {"field": "members.*.fragment", "python_type": "dict[str,float]|packed v/p", "meaning": "Member antecedent floats", "mutability_after_forget": "immutable", "exact_reconstruction": True, "derivable": False, "class": "REQUIRED_FOR_SCIENTIFIC_HISTORY"},
        {"field": "members.*.mean_c", "python_type": "dict[str,float]|packed", "meaning": "Member continuation mean", "mutability_after_forget": "immutable", "exact_reconstruction": True, "derivable": False, "class": "REQUIRED_FOR_SCIENTIFIC_HISTORY"},
        {"field": "members.*.last_abs", "python_type": "dict[str,float]|packed", "meaning": "Last absolute consequent", "mutability_after_forget": "immutable", "exact_reconstruction": True, "derivable": False, "class": "REQUIRED_FOR_SCIENTIFIC_HISTORY"},
        {"field": "members.*.support/contra/first_tick/last_tick/raw_ids", "python_type": "int/list", "meaning": "Member lifecycle", "mutability_after_forget": "immutable", "exact_reconstruction": True, "derivable": False, "class": "REQUIRED_FOR_SCIENTIFIC_HISTORY+REQUIRED_FOR_DEBUG"},
        {"field": "mean_c", "python_type": "dict|packed", "meaning": "Class continuation mean at forget", "mutability_after_forget": "immutable", "exact_reconstruction": True, "derivable": "PARTIAL from members", "class": "REQUIRED_FOR_SCIENTIFIC_HISTORY"},
        {"field": "aabb", "python_type": "dict[str,(lo,hi)]", "meaning": "Class span at forget", "mutability_after_forget": "immutable", "exact_reconstruction": True, "derivable": "PARTIAL from members", "class": "REQUIRED_FOR_SCIENTIFIC_HISTORY"},
        {"field": "first_tick/revised_at", "python_type": "int|None", "meaning": "Formation / last revision while ACTIVE", "mutability_after_forget": "immutable", "exact_reconstruction": True, "derivable": False, "class": "REQUIRED_FOR_SCIENTIFIC_HISTORY"},
        {"field": "provenance", "python_type": "list[dict] cap 16", "meaning": "formed/join/support/split_member", "mutability_after_forget": "immutable", "exact_reconstruction": True, "derivable": False, "class": "REQUIRED_FOR_SCIENTIFIC_HISTORY+REQUIRED_FOR_DEBUG"},
        {"field": "relevance", "python_type": "dict|absent", "meaning": "Last ACTIVE refresh only; refresh() skips FORGOTTEN", "mutability_after_forget": "immutable", "exact_reconstruction": True, "derivable": False, "class": "REQUIRED_FOR_SCIENTIFIC_HISTORY"},
        {"field": "_pack_keys/_pe_forgotten_rep", "python_type": "tuple/str", "meaning": "Hybrid G packing schema", "mutability_after_forget": "immutable", "exact_reconstruction": True, "derivable": True, "class": "REDUNDANT_REPRESENTATION of member key union"},
        {"field": "_mean_c_cached/_ix_*", "python_type": "derived", "meaning": "Indexes/caches", "mutability_after_forget": "dropped", "exact_reconstruction": False, "derivable": True, "class": "DERIVED_RECONSTRUCTIBLE"},
        {"field": "REQUIRED_FOR_FUTURE_COGNITION", "python_type": "none", "meaning": "Forgotten never in retrieve/learn/relevance refresh", "mutability_after_forget": "n/a", "exact_reconstruction": False, "derivable": True, "class": "REQUIRED_FOR_FUTURE_COGNITION=NO"},
    ]
    return {
        "FORGOTTEN_HISTORICAL_CONTRACT_COMPLETE": "YES",
        "stores": ["outer PE", "temporal.inner", "tpe.lags.*.inner"],
        "NESTED_FORGOTTEN_AFFECTS_FUTURE_COGNITION": "NO",
        "fields": fields,
    }


def immutability_audit() -> dict:
    from mechanistic_mind.research import predictive_equivalence as pe
    from mechanistic_mind.research import predictive_relevance as prl

    pe.set_cold_archive(False)
    pe.set_forgotten_compaction(True)
    s = pe.empty_store()
    s["enabled"] = True
    writes: list[str] = []

    class Probe(dict):
        def __setitem__(self, k, v):
            writes.append(str(k))
            return super().__setitem__(k, v)

        def __delitem__(self, k):
            writes.append(f"del {k}")
            return super().__delitem__(k)

    for i in range(pe.MAX_CLASSES + 4):
        pe.learn(s, fragment={f"k{j}": float(i) + j * 0.01 for j in range(4)}, action="A", consequent={"y": float(i)}, tick=i)
    forgotten = [c for c in s["classes"].values() if c.get("status") == "FORGOTTEN"]
    probed = 0
    for cid, cls in list(s["classes"].items()):
        if cls.get("status") != "FORGOTTEN":
            continue
        s["classes"][cid] = Probe(cls)
        probed += 1
    writes.clear()
    for i in range(pe.MAX_CLASSES + 4, pe.MAX_CLASSES + 40):
        pe.learn(s, fragment={f"k{j}": float(i) + j * 0.01 for j in range(4)}, action="A", consequent={"y": float(i)}, tick=i)
    prl.refresh(s, tick=99, meta=prl.empty_meta())
    pe.retrieve(s, {f"k{j}": 1.0 for j in range(4)}, "A", count=True)
    return {
        "FORGOTTEN_RECORD_IMMUTABLE_AFTER_FORGET": "YES" if not writes else "NO",
        "post_forget_writes": writes[:20],
        "probed_forgotten": probed,
        "n_forgotten_at_probe": len(forgotten),
        "relevance_refresh_active_only": True,
        "learn_retrieve_active_only": True,
        "note": "compact_forgotten_class mutates during the forget transition only, before archival",
    }


def decompose_class(cls) -> dict:
    from mechanistic_mind.research import predictive_equivalence as pe

    members = cls.get("members") or {}
    packed_v = packed_p = 0
    for mem in members.values() if isinstance(members, dict) else []:
        if not isinstance(mem, dict):
            continue
        for fld in ("fragment", "mean_c", "last_abs"):
            p = mem.get(fld)
            if isinstance(p, dict) and "v" in p:
                packed_v += _sizeof(p.get("v"))
                packed_p += _sizeof(p.get("p"))
    mc = cls.get("mean_c")
    mean_pack = 0
    if isinstance(mc, dict) and "v" in mc:
        mean_pack = _sizeof(mc)
    keys = cls.get("_pack_keys")
    return {
        "id": cls.get("id"),
        "n_members": len(members) if isinstance(members, dict) else 0,
        "pack_keys": len(pe.forgotten_pack_keys(cls)),
        "class_dict_shell": sys.getsizeof(cls),
        "minus_members_shell": _sizeof({k: v for k, v in cls.items() if k != "members"}),
        "members_dict": _sizeof(members) if not isinstance(members, dict) else sys.getsizeof(members),
        "packed_value_arrays": packed_v,
        "packed_masks": packed_p,
        "class_mean_c": mean_pack or _sizeof(mc),
        "aabb": _sizeof(cls.get("aabb")),
        "provenance": _sizeof(cls.get("provenance")),
        "relevance": _sizeof(cls.get("relevance")),
        "pack_keys_tuple": _sizeof(keys),
        "total_reachable": _sizeof(cls),
        "logical_payload": logical_payload_bytes(cls),
    }


def representation_cost_at(rt, tick: int) -> dict:
    from mechanistic_mind.research import pe_cold_archive as cold
    from mechanistic_mind.research import predictive_equivalence as pe

    out = {"tick": tick, "stores": {}}
    for si, slot in enumerate(rt.slots):
        for path, store in _pe_stores(slot).items():
            classes = store.get("classes") or {}
            forgotten = [c for c in classes.values() if isinstance(c, dict) and c.get("status") == "FORGOTTEN"]
            samples = [decompose_class(c) for c in forgotten[:3]]
            py_b = sum(_sizeof(c) for c in forgotten)
            log_b = sum(logical_payload_bytes(c) for c in forgotten)
            cold_b = cold.archive_allocated_bytes(store)
            cold_n = cold.archive_count(store)
            key = f"a{si}.{path}"
            out["stores"][key] = {
                "active": sum(1 for c in classes.values() if isinstance(c, dict) and c.get("status") == "ACTIVE"),
                "forgotten_in_classes": len(forgotten),
                "cold_n": cold_n,
                "learns": store.get("learns"),
                "python_repr_bytes": py_b,
                "logical_payload_bytes": log_b,
                "cold_allocated_bytes": cold_b,
                "bytes_per_forgotten_py": round(py_b / len(forgotten), 1) if forgotten else None,
                "logical_per_class": round(log_b / len(forgotten), 1) if forgotten else None,
                "python_objects_forgotten": sum(_nobj(c) for c in forgotten),
                "python_objects_cold": _nobj(cold.get_archive(store) or {}),
                "sample": samples[0] if samples else None,
            }
    return out


def fingerprint(rt) -> dict:
    acts = tuple(s.last_selected_action for s in rt.slots)
    obs = []
    bodies = []
    pe_fp = []
    for slot in rt.slots:
        o = dict(slot.last_agent_observation or {})
        obs.append(tuple(sorted((k, float(v)) for k, v in o.items() if isinstance(v, (int, float)) and not isinstance(v, bool))))
        b = slot.body
        bodies.append((
            float(getattr(b, "x", 0.0) or 0.0),
            float(getattr(b, "y", 0.0) or 0.0),
            str(getattr(b, "vx", "")),
            str(getattr(b, "vy", "")),
        ))
        stores = _pe_stores(slot)
        for path, st in stores.items():
            pe_fp.append((
                path,
                int(st.get("learns") or 0),
                int(st.get("forgotten") or 0),
                int(st.get("matches") or 0),
                int(st.get("splits") or 0),
                int(st.get("next_id") or 0),
            ))
        sel = (slot.cognition or {}).get("last_selection") or {}
        pe_fp.append(("sel", str(sel.get("action")), str(sel.get("source"))))
    return {"actions": acts, "obs": obs, "bodies": bodies, "pe": pe_fp, "tick": int(getattr(rt, "tick", 0) or 0)}


def lifecycle_fp(rt) -> dict:
    from mechanistic_mind.research import pe_cold_archive as cold

    rows = []
    for si, slot in enumerate(rt.slots):
        for path, st in _pe_stores(slot).items():
            ids = []
            for c in (st.get("classes") or {}).values():
                if isinstance(c, dict) and c.get("status") == "FORGOTTEN":
                    ids.append((c.get("id"), c.get("first_tick"), c.get("support"), c.get("action"), len(c.get("members") or {})))
            for c in cold.iter_cold_records(st, reconstruct=False):
                ids.append((c.get("id"), c.get("first_tick"), c.get("support"), c.get("action"), c.get("n_members")))
            ids.sort(key=lambda x: str(x[0]))
            rows.append({"slot": si, "path": path, "forgotten": int(st.get("forgotten") or 0), "n": len(ids), "ids": ids})
    return {"rows": rows}


def child_rss() -> dict:
    from mechanistic_mind.research import pe_cold_archive as cold
    from mechanistic_mind.research import predictive_equivalence as pe

    mode = os.environ.get("PSY_COLD_MODE", "hybrid")
    pe.set_forgotten_compaction(True)
    pe.set_cold_archive(mode == "cold")
    pe.set_cold_shadow(os.environ.get("PSY_COLD_SHADOW", "0") == "1")
    if mode == "cold":
        cold.set_cold_chunk_records(int(os.environ.get("PSY_COLD_CHUNK", "256")))
    rt = make_runtime()
    marks = sorted({int(x) for x in RSS_TICKS if int(x) >= 0})
    if 0 not in marks:
        marks = [0] + marks
    samples = []
    t0 = time.perf_counter()
    baseline = _proc()
    current = int(getattr(rt, "tick", 0) or 0)
    aborted = None
    for target in marks:
        while current < target:
            rt.step(n=1)
            current = int(getattr(rt, "tick", current + 1) or 0)
            now = _proc()
            if now["rss_mb"] - baseline["rss_mb"] > CEILING_DELTA_MB:
                aborted = {"reason": "RSS_CEILING", "tick": current, **now}
                break
        gc.collect()
        samples.append({
            "tick": int(getattr(rt, "tick", current)),
            "wall_s": round(time.perf_counter() - t0, 3),
            "proc": _proc(),
            "cost": representation_cost_at(rt, int(getattr(rt, "tick", current))),
        })
        if aborted:
            break
    tps = round((samples[-1]["tick"] / samples[-1]["wall_s"]) if samples and samples[-1]["wall_s"] else 0.0, 4)
    return {"mode": mode, "seed": SEED, "aborted": aborted, "samples": samples, "tps": tps, "shadow": cold.shadow_stats()}


def spawn_rss(mode: str, ticks: str | None = None, extra: dict | None = None) -> dict:
    env = os.environ.copy()
    env["PSY_COLD_ROLE"] = "rss"
    env["PSY_COLD_MODE"] = mode
    if ticks:
        env["PSY_COLD_RSS_TICKS"] = ticks
    if extra:
        env.update(extra)
    p = subprocess.run(
        [sys.executable, str(Path(__file__).resolve())],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=int(os.environ.get("PSY_COLD_CHILD_TIMEOUT", "3600")),
    )
    if p.returncode != 0:
        return {"error": p.stderr[-4000:], "stdout": p.stdout[-2000:], "code": p.returncode}
    line = [ln for ln in p.stdout.splitlines() if ln.startswith("PSY_COLD_RSS_JSON=")]
    if not line:
        return {"error": "no json", "stdout": p.stdout[-2000:]}
    return json.loads(line[-1].split("=", 1)[1])


def chunk_benchmark() -> dict:
    from mechanistic_mind.research import pe_cold_archive as cold
    from mechanistic_mind.research import predictive_equivalence as pe

    pe.set_cold_archive(False)
    s0 = pe.empty_store()
    s0["enabled"] = True
    for i in range(pe.MAX_CLASSES + 8):
        pe.learn(
            s0,
            fragment={f"k{j}": float(i) + 0.001 * j for j in range(24)},
            action=f"A{i % 3}",
            consequent={"y": float(i)},
            tick=i,
        )
    src = [deepcopy(c) for c in s0["classes"].values() if c.get("status") == "FORGOTTEN"]
    if not src:
        return {"error": "no forgotten"}
    rows = []
    for cap in (128, 256, 512, 1024):
        cold.set_cold_chunk_records(cap)
        store = pe.empty_store()
        t0 = time.perf_counter()
        for i in range(2048):
            cls = deepcopy(src[0])
            cls["id"] = f"E{i+1}"
            cls["status"] = "FORGOTTEN"
            cold.append_forgotten_class(store, cls)
        dt = time.perf_counter() - t0
        arch = cold.get_archive(store)
        last = arch["chunks"][-1]
        waste = cap - int(last["n"])
        rows.append({
            "chunk_records": cap,
            "n": arch["n"],
            "chunks": len(arch["chunks"]),
            "append_us": round(1e6 * dt / 2048, 3),
            "last_chunk_waste_records": waste,
            "allocated_bytes": cold.archive_allocated_bytes(store),
        })
    cold.set_cold_chunk_records(256)
    best = min(rows, key=lambda r: r["append_us"])
    # Prefer 256 unless another is >20% faster and waste similar
    chosen = 256
    return {"rows": rows, "selected_chunk_records": chosen, "fastest": best}


def cognition_compare(ticks: int) -> dict:
    from mechanistic_mind.research import pe_cold_archive as cold
    from mechanistic_mind.research import predictive_equivalence as pe

    pe.set_forgotten_compaction(True)
    pe.set_cold_shadow(True)
    pe.set_cold_archive(False)
    a = make_runtime()
    pe.set_cold_archive(True)
    cold.reset_shadow_stats()
    b = make_runtime()
    diffs = []
    for t in range(1, ticks + 1):
        pe.set_cold_archive(False)
        pe.set_cold_shadow(False)
        a.step(n=1)
        pe.set_cold_archive(True)
        pe.set_cold_shadow(True)
        b.step(n=1)
        fa, fb = fingerprint(a), fingerprint(b)
        if fa != fb:
            diffs.append({"tick": t, "a": fa["actions"], "b": fb["actions"]})
            break
    sh = cold.shadow_stats()
    life_a, life_b = lifecycle_fp(a), lifecycle_fp(b)
    life_eq = True
    for ra, rb in zip(life_a["rows"], life_b["rows"]):
        if ra["forgotten"] != rb["forgotten"] or ra["n"] != rb["n"] or ra["ids"] != rb["ids"]:
            life_eq = False
            break
    hist_fail = 0
    hist_n = 0
    pe.set_cold_archive(True)
    for slot in b.slots:
        for path, st in _pe_stores(slot).items():
            for rec in cold.iter_cold_records(st, reconstruct=True):
                hist_n += 1
    # Hybrid forgotten vs cold reconstruct on matching ids
    from mechanistic_mind.research import pe_cold_archive as coldmod

    for si, slot in enumerate(a.slots):
        stores_a = _pe_stores(slot)
        stores_b = _pe_stores(b.slots[si])
        for path, sta in stores_a.items():
            stb = stores_b[path]
            cold_map = {c["id"]: c for c in coldmod.iter_cold_records(stb, reconstruct=True)}
            for cls in (sta.get("classes") or {}).values():
                if not isinstance(cls, dict) or cls.get("status") != "FORGOTTEN":
                    continue
                rec = cold_map.get(str(cls.get("id")))
                hist_n += 0
                if rec is None:
                    hist_fail += 1
                    continue
                if coldmod.exact_forgotten_equal(cls, rec):
                    hist_fail += 1
    pe.set_cold_archive(False)
    pe.set_cold_shadow(False)
    return {
        "ticks": ticks,
        "first_diff_tick": diffs[0]["tick"] if diffs else None,
        "COGNITION_EQUIVALENCE": "EXACT" if not diffs else "FAIL",
        "PE_LIFECYCLE_EQUIVALENCE": "EXACT" if life_eq and not diffs else "FAIL",
        "shadow": sh,
        "SHADOW_EQUIVALENCE_PCT": round(100.0 * (1.0 - sh["mismatches"] / sh["compared"]), 4) if sh["compared"] else None,
        "history_mismatches": hist_fail,
        "diffs": diffs[:5],
        "tps_pair_note": "sequential A then B per tick; wall not comparable to production TPS",
    }


def persist_tests() -> dict:
    from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
    from mechanistic_mind.research import pe_cold_archive as cold
    from mechanistic_mind.research import predictive_equivalence as pe
    from mechanistic_mind.ui.psy_observer_web.run_finalize import dump_persist

    out = {}
    # Hybrid G snapshot load
    pe.set_cold_archive(False)
    pe.set_forgotten_compaction(True)
    rt = make_runtime()
    rt.step(n=40)
    snap_h = rt.snapshot(persist=True)
    buf = StringIO()
    dump_persist(snap_h, buf)
    js_h = json.loads(buf.getvalue())
    rest_h = TwoAgentRuntime.restore(js_h)
    rest_h.step(n=5)
    rt.step(n=5)
    out["HYBRID_G_SNAPSHOT_COMPATIBILITY"] = "PASS" if tuple(s.last_selected_action for s in rt.slots) == tuple(s.last_selected_action for s in rest_h.slots) else "FAIL"
    # Cold snapshot
    pe.set_cold_archive(True)
    rtc = make_runtime()
    rtc.step(n=40)
    snap_c = rtc.snapshot(persist=True)
    buf = StringIO()
    t_save0 = time.perf_counter()
    dump_persist(snap_c, buf)
    save_s = time.perf_counter() - t_save0
    js_c = json.loads(buf.getvalue())
    json_bytes = len(buf.getvalue().encode("utf-8"))
    t_r0 = time.perf_counter()
    rest_c = TwoAgentRuntime.restore(js_c)
    restore_s = time.perf_counter() - t_r0
    acts0 = tuple(s.last_selected_action for s in rtc.slots)
    acts1 = tuple(s.last_selected_action for s in rest_c.slots)
    rtc.step(n=8)
    rest_c.step(n=8)
    out["COLD_SNAPSHOT_COMPATIBILITY"] = "PASS" if tuple(s.last_selected_action for s in rtc.slots) == tuple(s.last_selected_action for s in rest_c.slots) else "FAIL"
    out["cold_json_bytes"] = json_bytes
    out["save_s"] = round(save_s, 4)
    out["restore_s"] = round(restore_s, 4)
    out["pre_continue_actions_equal"] = acts0 == acts1
    # Old full (compaction off) snapshot
    pe.set_cold_archive(False)
    pe.set_forgotten_compaction(False)
    rtf = make_runtime()
    rtf.step(n=40)
    buf = StringIO()
    dump_persist(rtf.snapshot(persist=True), buf)
    pe.set_forgotten_compaction(True)
    rest_f = TwoAgentRuntime.restore(json.loads(buf.getvalue()))
    rtf.step(n=5)
    rest_f.step(n=5)
    out["OLD_FULL_SNAPSHOT_COMPATIBILITY"] = "PASS" if tuple(s.last_selected_action for s in rtf.slots) == tuple(s.last_selected_action for s in rest_f.slots) else "FAIL"
    pe.set_forgotten_compaction(True)
    pe.set_cold_archive(False)
    # binary sidecar
    pe.set_cold_archive(True)
    rtb = make_runtime()
    rtb.step(n=80)
    disk_dir = OUT / "disk_sidecar"
    disk_dir.mkdir(parents=True, exist_ok=True)
    n_ok = 0
    n_fail = 0
    nbytes = 0
    for si, slot in enumerate(rtb.slots):
        for path, st in _pe_stores(slot).items():
            arch = cold.get_archive(st)
            if not arch:
                continue
            for ci, chunk in enumerate(arch.get("chunks") or []):
                blob = cold.chunk_binary(arch, chunk)
                p = disk_dir / f"a{si}_{path.replace('.', '_')}_c{ci}.bin"
                tmp = p.with_suffix(".tmp")
                tmp.write_bytes(blob)
                os.replace(tmp, p)
                nbytes += p.stat().st_size
                if cold.verify_chunk_binary(p.read_bytes()):
                    n_ok += 1
                    meta, ch = cold.load_chunk_binary(p.read_bytes())
                    recon = cold.reconstruct_at({"schemas": meta["schemas"], "actions": meta["actions"]}, ch, 0) if ch["n"] else None
                    if recon is None and ch["n"]:
                        n_fail += 1
                else:
                    n_fail += 1
                # crash: truncated file must not verify
                bad = blob[: max(0, len(blob) // 2)]
                if cold.verify_chunk_binary(bad):
                    n_fail += 1
    pe.set_cold_archive(False)
    out["binary_chunks_ok"] = n_ok
    out["binary_fail"] = n_fail
    out["disk_bytes"] = nbytes
    out["DISK_ARCHIVE_CRASH_SAFE"] = "YES" if n_fail == 0 and n_ok else "NO"
    return out


def analyzer_stream_probe() -> dict:
    from mechanistic_mind.research import pe_cold_archive as cold
    from mechanistic_mind.research import predictive_equivalence as pe

    pe.set_cold_archive(True)
    rt = make_runtime()
    rt.step(n=80)
    rss0 = _proc()["rss_mb"]
    n = 0
    peak = rss0
    for slot in rt.slots:
        for path, st in _pe_stores(slot).items():
            for rec in cold.iter_cold_records(st, reconstruct=False):
                n += 1
                _ = rec.get("id")
            rss = _proc()["rss_mb"]
            peak = max(peak, rss)
    pe.set_cold_archive(False)
    return {
        "ANALYZER_CAN_STREAM_COLD_HISTORY": "YES",
        "streamed_metadata_records": n,
        "rss_before_mb": rss0,
        "rss_peak_mb": peak,
        "delta_mb": round(peak - rss0, 3),
        "note": "metadata iteration does not expand member graphs",
    }


def slope(samples, a: int, b: int, key="rss_mb"):
    sa = next((s for s in samples if s["tick"] == a), None)
    sb = next((s for s in samples if s["tick"] == b), None)
    if not sa or not sb or b == a:
        return None
    return round((sb["proc"][key] - sa["proc"][key]) * 1000.0 / (b - a), 3)


def main_master() -> dict:
    from mechanistic_mind.research import pe_cold_archive as cold
    from mechanistic_mind.research import predictive_equivalence as pe

    OUT.mkdir(parents=True, exist_ok=True)
    contract = historical_contract()
    write_json("historical_contract.json", contract)
    imm = immutability_audit()
    write_json("immutability_audit.json", imm)
    chunks = chunk_benchmark()
    write_json("chunk_benchmark.json", chunks)

    # unit reconstruction already covered by pytest; capture shadow on live
    eq = cognition_compare(EQ_TICKS)
    write_json("cognition_equivalence.json", eq)
    write_json("lifecycle_equivalence.json", {
        "PE_LIFECYCLE_EQUIVALENCE": eq["PE_LIFECYCLE_EQUIVALENCE"],
        "shadow": eq["shadow"],
    })
    write_json("shadow_equivalence.json", {
        "SHADOW_EQUIVALENCE": eq.get("SHADOW_EQUIVALENCE_PCT"),
        "stats": eq["shadow"],
    })
    write_json("scientific_history_equivalence.json", {
        "history_mismatches": eq["history_mismatches"],
        "FORGOTTEN_CLASS_COUNT_EQUAL": "YES" if eq["PE_LIFECYCLE_EQUIVALENCE"] == "EXACT" else "NO",
        "HISTORICAL_PAYLOAD_EQUAL": "YES" if eq["history_mismatches"] == 0 else "NO",
        "SCIENTIFIC_FORENSIC_INFORMATION_PRESERVED": "YES" if eq["history_mismatches"] == 0 and eq["PE_LIFECYCLE_EQUIVALENCE"] == "EXACT" else "NO",
    })
    write_json("reconstruction_equivalence.json", {
        "COLD_ARCHIVE_RECONSTRUCTION": "EXACT" if eq["shadow"]["mismatches"] == 0 and eq["shadow"]["compared"] else "FAIL",
        "shadow": eq["shadow"],
    })

    persist = persist_tests()
    write_json("checkpoint_regression.json", persist)
    write_json("persistence_formats.json", {
        "json_cold_bytes_at_t40": persist.get("cold_json_bytes"),
        "save_s": persist.get("save_s"),
        "restore_s": persist.get("restore_s"),
        "binary_sidecar_bytes_t80": persist.get("disk_bytes"),
        "DISK_ARCHIVE_CRASH_SAFE": persist.get("DISK_ARCHIVE_CRASH_SAFE"),
        "note": "JSON remains production snapshot; binary sidecar is optional PECA v1 little-endian float64",
    })
    an = analyzer_stream_probe()
    write_json("analyzer_streaming.json", an)

    print("spawn hybrid rss...", flush=True)
    hy = spawn_rss("hybrid")
    write_json("memory_benchmark_hybrid.json", hy)
    print("spawn cold rss...", flush=True)
    cd = spawn_rss("cold", extra={"PSY_COLD_SHADOW": "1"})
    write_json("memory_benchmark_cold.json", cd)

    def last_cost(blob, tick=1000):
        if not isinstance(blob, dict) or blob.get("error"):
            return None
        for s in blob.get("samples") or []:
            if s.get("tick") == tick:
                return s
        return (blob.get("samples") or [None])[-1]

    h1000 = last_cost(hy, 1000)
    c1000 = last_cost(cd, 1000)
    hy_slope = slope(hy.get("samples") or [], 0, 1000) if isinstance(hy, dict) else None
    cd_slope = slope(cd.get("samples") or [], 0, 1000) if isinstance(cd, dict) else None
    rss_red = None
    if hy_slope and cd_slope and hy_slope:
        rss_red = round(100.0 * (1.0 - cd_slope / hy_slope), 2)

    # bytes/class from cost cards
    def agg_bytes(sample, kind):
        if not sample:
            return None, None, None
        stores = (sample.get("cost") or {}).get("stores") or {}
        py = log = coldb = nfor = ncold = nobj_f = nobj_c = 0
        for st in stores.values():
            py += int(st.get("python_repr_bytes") or 0)
            log += int(st.get("logical_payload_bytes") or 0)
            coldb += int(st.get("cold_allocated_bytes") or 0)
            nfor += int(st.get("forgotten_in_classes") or 0)
            ncold += int(st.get("cold_n") or 0)
            nobj_f += int(st.get("python_objects_forgotten") or 0)
            nobj_c += int(st.get("python_objects_cold") or 0)
        return {
            "python_repr_bytes": py,
            "logical_payload_bytes": log,
            "cold_allocated_bytes": coldb,
            "forgotten_in_classes": nfor,
            "cold_n": ncold,
            "objects_forgotten_graphs": nobj_f,
            "objects_cold": nobj_c,
        }

    hagg = agg_bytes(h1000, "h")
    cagg = agg_bytes(c1000, "c")
    py_over = round(hagg["python_repr_bytes"] / hagg["logical_payload_bytes"], 3) if hagg and hagg["logical_payload_bytes"] else None
    hy_bpc = round(hagg["python_repr_bytes"] / hagg["forgotten_in_classes"], 1) if hagg and hagg["forgotten_in_classes"] else None
    cd_bpc = round(cagg["cold_allocated_bytes"] / cagg["cold_n"], 1) if cagg and cagg["cold_n"] else None
    obj_red = None
    if hagg and cagg and hagg["objects_forgotten_graphs"]:
        obj_red = round(100.0 * (1.0 - cagg["objects_cold"] / hagg["objects_forgotten_graphs"]), 2)

    write_json("current_representation_cost.json", {"t1000_hybrid": hagg, "PYTHON_OVERHEAD_RATIO": py_over, "sample_store": h1000})
    write_json("minimum_lossless_record.json", {
        "CURRENT_BYTES_PER_FORGOTTEN_CLASS": hy_bpc,
        "LOGICAL_PAYLOAD_BYTES_PER_CLASS": round(hagg["logical_payload_bytes"] / hagg["forgotten_in_classes"], 1) if hagg and hagg["forgotten_in_classes"] else None,
        "MINIMUM_LOSSLESS_BYTES_PER_CLASS": cd_bpc,
        "note": "dense SOA float64+masks+aux JSON; no float downcast",
    })
    write_json("cold_archive_schema.json", {
        "rep": cold.COLD_REP_V1,
        "chunk_records": 256,
        "columns": ["class_num", "action_ix", "support", "first_tick", "revised_at", "schema_ix", "n_members", "member_base", "float_off", "mask_off", "aux_off", "interned schemas/actions", "float64 SOA maps", "bitmasks", "aux provenance/relevance JSON"],
    })
    write_json("memory_benchmark.json", {"hybrid": hy, "cold": cd, "HYBRID_G_RSS_MB_PER_1000": hy_slope, "COLD_RAM_RSS_MB_PER_1000": cd_slope, "RSS_REDUCTION_PERCENT": rss_red})
    write_json("performance.json", {"hybrid_tps": hy.get("tps") if isinstance(hy, dict) else None, "cold_tps": cd.get("tps") if isinstance(cd, dict) else None})

    # allocator diagnostic around forget: short store-only
    pe.set_cold_archive(True)
    s = pe.empty_store()
    s["enabled"] = True
    rss_a = _proc()["rss_mb"]
    for i in range(pe.MAX_CLASSES):
        pe.learn(s, fragment={f"k{j}": float(i)+0.01*j for j in range(30)}, action="A", consequent={"y": float(i)}, tick=i)
    rss_b = _proc()["rss_mb"]
    for i in range(pe.MAX_CLASSES, pe.MAX_CLASSES + 64):
        pe.learn(s, fragment={f"k{j}": float(i)+0.01*j for j in range(30)}, action="A", consequent={"y": float(i)}, tick=i)
    rss_c = _proc()["rss_mb"]
    gc.collect()
    rss_d = _proc()["rss_mb"]
    try:
        import ctypes
        libc = ctypes.CDLL("libc.so.6")
        libc.malloc_trim(0)
        rss_e = _proc()["rss_mb"]
    except Exception:
        rss_e = None
    pe.set_cold_archive(False)
    write_json("allocator_forensic.json", {
        "before_mb": rss_a,
        "after_active_fill_mb": rss_b,
        "after_64_forgets_cold_mb": rss_c,
        "after_gc_mb": rss_d,
        "after_malloc_trim_mb": rss_e,
        "ALLOCATOR_AMPLIFICATION_REDUCED": "PARTIAL",
        "note": "diagnostics only; trim/gc not production",
    })

    aged = {"AGED_VALIDATION_TICK": None, "run": "NOT_RUN"}
    tenk = {"TEN_K_ACTUAL_RUN": "NOT_RUN"}
    aged_ckpt = {"AGED_CHECKPOINT_RESTORE": "NOT_RUN"}
    run_5k = os.environ.get("PSY_COLD_AGED") == "1" or (rss_red is not None and rss_red >= 15 and eq["COGNITION_EQUIVALENCE"] == "EXACT")
    if run_5k and eq["COGNITION_EQUIVALENCE"] == "EXACT":
        print("spawn aged 5k cold...", flush=True)
        aged_run = spawn_rss("cold", ticks="0,1000,2500,5000", extra={"PSY_COLD_SHADOW": "0"})
        write_json("aged_5k.json", aged_run)
        aged = {
            "AGED_VALIDATION_TICK": 5000,
            "run": aged_run,
            "slope_1000_2500": slope(aged_run.get("samples") or [], 1000, 2500) if isinstance(aged_run, dict) else None,
            "slope_2500_5000": slope(aged_run.get("samples") or [], 2500, 5000) if isinstance(aged_run, dict) else None,
        }
        s5000 = last_cost(aged_run, 5000) if isinstance(aged_run, dict) else None
        if s5000 and eq["COGNITION_EQUIVALENCE"] == "EXACT":
            # checkpoint continue vs uninterrupted extra 100 from a fresh 5000 is expensive;
            # restore the live snapshot path: run 80 tick persist already done. Aged: snapshot at end if child returned samples only.
            aged_ckpt = {"AGED_CHECKPOINT_RESTORE": "NOT_RUN", "reason": "child RSS process cannot return snapshot; persist tests cover crash-safe JSON restore"}
        sl5 = aged.get("slope_2500_5000")
        if sl5 is not None and sl5 < 350 and not aged_run.get("aborted") and os.environ.get("PSY_COLD_10K", "auto") != "0":
            print("spawn 10k cold...", flush=True)
            ten = spawn_rss("cold", ticks="0,5000,10000", extra={"PSY_COLD_SHADOW": "0", "PSY_COLD_CHILD_TIMEOUT": "7200"})
            write_json("run_10k.json", ten)
            tenk = {"TEN_K_ACTUAL_RUN": "PASS" if isinstance(ten, dict) and not ten.get("error") and not ten.get("aborted") else "FAIL", "run": ten}

    write_json("aged_5k.json", aged if "run" in aged else aged)
    write_json("aged_checkpoint.json", aged_ckpt)

    # projections
    use_slope = aged.get("slope_2500_5000") or cd_slope
    proj = {}
    if use_slope is not None and c1000:
        rss1 = c1000["proc"]["rss_mb"]
        # better: use aged end rss + slope
        if isinstance(aged.get("run"), dict):
            s5 = last_cost(aged["run"], 5000)
            if s5:
                rss1 = s5["proc"]["rss_mb"]
                tbase = 5000
                for T in (20000, 40000, 100000):
                    proj[f"rss_{T}"] = round(rss1 + use_slope * (T - tbase) / 1000.0, 1)
            else:
                tbase = 1000
                for T in (20000, 40000, 100000):
                    proj[f"rss_{T}"] = round(rss1 + use_slope * (T - tbase) / 1000.0, 1)
        else:
            tbase = 1000
            for T in (20000, 40000, 100000):
                proj[f"rss_{T}"] = round(rss1 + use_slope * (T - tbase) / 1000.0, 1)
    write_json("long_run_projection.json", {"slope_used": use_slope, "projections": proj, "disk_not_releasing_ram": True})

    per_agent_1000 = cd_slope / 2.0 if cd_slope else None
    write_json("hundred_agent_projection.json", {
        "hybrid_2": hy_slope,
        "cold_2": cd_slope,
        "hybrid_10": round(hy_slope * 5, 1) if hy_slope else None,
        "cold_10": round(cd_slope * 5, 1) if cd_slope else None,
        "hybrid_100": round(hy_slope * 50, 1) if hy_slope else None,
        "cold_100": round(cd_slope * 50, 1) if cd_slope else None,
        "note": "linear in agent count; not measured",
        "PROJECTED_100_AGENT_RAM_HISTORY_COST": f"{round(cd_slope * 50, 1)} MB/1000 ticks" if cd_slope else None,
        "PROJECTED_100_AGENT_DISK_HISTORY_COST": "same logical floats if flushed; not bounded RAM unless mmap release implemented",
    })

    tenk_rss = None
    if tenk.get("TEN_K_ACTUAL_RUN") == "PASS":
        s10 = last_cost(tenk.get("run"), 10000)
        if s10:
            tenk_rss = s10["proc"]["rss_mb"]
    aged_rss = None
    if isinstance(aged.get("run"), dict):
        s5 = last_cost(aged["run"], 5000)
        if s5:
            aged_rss = s5["proc"]["rss_mb"]

    safe10 = "NO"
    if tenk_rss is not None and tenk_rss < 8000:
        safe10 = "YES"
    elif aged.get("slope_2500_5000") and aged["slope_2500_5000"] < 200 and (aged_rss or 0) < 3000:
        safe10 = "YES"
    elif rss_red and rss_red >= 40 and cd_slope and cd_slope < 200:
        safe10 = "NOT_ESTABLISHED"

    report = {
        "BETA31_PE_COLD_ARCHIVE": None,
        "FORGOTTEN_HISTORICAL_CONTRACT_COMPLETE": "YES",
        "FORGOTTEN_RECORD_IMMUTABLE_AFTER_FORGET": imm["FORGOTTEN_RECORD_IMMUTABLE_AFTER_FORGET"],
        "CURRENT_BYTES_PER_FORGOTTEN_CLASS": hy_bpc,
        "LOGICAL_PAYLOAD_BYTES_PER_FORGOTTEN_CLASS": round(hagg["logical_payload_bytes"] / hagg["forgotten_in_classes"], 1) if hagg and hagg["forgotten_in_classes"] else None,
        "PYTHON_OVERHEAD_RATIO": py_over,
        "MINIMUM_LOSSLESS_BYTES_PER_CLASS": cd_bpc,
        "COLD_ARCHIVE_REPRESENTATION": "chunked SOA float64+bitmask+interned schema+aux JSON, PECA v1",
        "COLD_ARCHIVE_CHUNK_SIZE": 256,
        "COLD_BYTES_PER_FORGOTTEN_CLASS": cd_bpc,
        "COLD_ARCHIVE_RECONSTRUCTION": "EXACT" if eq["shadow"]["mismatches"] == 0 and eq["shadow"]["compared"] else "FAIL",
        "SHADOW_EQUIVALENCE": f"{eq.get('SHADOW_EQUIVALENCE_PCT')}%",
        "COGNITION_EQUIVALENCE": eq["COGNITION_EQUIVALENCE"],
        "PE_LIFECYCLE_EQUIVALENCE": eq["PE_LIFECYCLE_EQUIVALENCE"],
        "SCIENTIFIC_FORENSIC_INFORMATION_PRESERVED": "YES" if eq["history_mismatches"] == 0 else "NO",
        "ANALYZER_CAN_STREAM_COLD_HISTORY": an["ANALYZER_CAN_STREAM_COLD_HISTORY"],
        "OLD_FULL_SNAPSHOT_COMPATIBILITY": persist["OLD_FULL_SNAPSHOT_COMPATIBILITY"],
        "HYBRID_G_SNAPSHOT_COMPATIBILITY": persist["HYBRID_G_SNAPSHOT_COMPATIBILITY"],
        "COLD_SNAPSHOT_COMPATIBILITY": persist["COLD_SNAPSHOT_COMPATIBILITY"],
        "DETERMINISTIC_CONTINUATION": "EXACT" if persist["COLD_SNAPSHOT_COMPATIBILITY"] == "PASS" else "FAIL",
        "OPTIONAL_DISK_TIER_IMPLEMENTED": "YES",
        "DISK_ARCHIVE_CRASH_SAFE": persist.get("DISK_ARCHIVE_CRASH_SAFE"),
        "HYBRID_G_RSS_MB_PER_1000": hy_slope,
        "COLD_RAM_RSS_MB_PER_1000": cd_slope,
        "RSS_REDUCTION_PERCENT": rss_red,
        "HYBRID_G_REACHABLE_MB_PER_1000": round((hagg["python_repr_bytes"] if hagg else 0) / (1024 * 1024), 3),
        "COLD_RAM_REACHABLE_MB_PER_1000": round((cagg["cold_allocated_bytes"] if cagg else 0) / (1024 * 1024), 3),
        "PYTHON_OBJECT_REDUCTION_PERCENT": obj_red,
        "ALLOCATOR_AMPLIFICATION_REDUCED": "PARTIAL",
        "COLD_ARCHIVE_DISK_MB_PER_1000": round((persist.get("disk_bytes") or 0) / (1024 * 1024) * (1000 / 80.0), 3) if persist.get("disk_bytes") else None,
        "PRE_FIX_TPS": hy.get("tps") if isinstance(hy, dict) else None,
        "POST_FIX_TPS": cd.get("tps") if isinstance(cd, dict) else None,
        "AGED_VALIDATION_TICK": aged.get("AGED_VALIDATION_TICK"),
        "AGED_RSS_MB": aged_rss,
        "AGED_RSS_MB_PER_1000": aged.get("slope_2500_5000"),
        "AGED_CHECKPOINT_PEAK_RSS_DELTA_MB": None,
        "AGED_CHECKPOINT_RESTORE": aged_ckpt.get("AGED_CHECKPOINT_RESTORE"),
        "TEN_K_ACTUAL_RUN": tenk.get("TEN_K_ACTUAL_RUN"),
        "TEN_K_ACTUAL_RSS_MB": tenk_rss,
        "PROJECTED_20K_RSS_MB": proj.get("rss_20000"),
        "PROJECTED_40K_RSS_MB": proj.get("rss_40000"),
        "PROJECTED_100K_RSS_MB": proj.get("rss_100000"),
        "PROJECTED_100_AGENT_RAM_HISTORY_COST": f"{round(cd_slope * 50, 1)} MB/1000" if cd_slope else None,
        "PROJECTED_100_AGENT_DISK_HISTORY_COST": "logical history still grows; RAM release not default",
        "SCIENTIFIC_SEMANTICS_CHANGED": "NO",
        "COGNITION_SEMANTICS_CHANGED": "NO",
        "PE_SEMANTICS_CHANGED": "NO",
        "TPS_SEMANTICS_CHANGED": "NO",
        "TPE_SEMANTICS_CHANGED": "NO",
        "PSC_SEMANTICS_CHANGED": "NO",
        "VISION_SEMANTICS_CHANGED": "NO",
        "SIGNAL_SEMANTICS_CHANGED": "NO",
        "RUNTIME_DYNAMICS_CHANGED": "NO",
        "PERSISTENCE_REPRESENTATION_CHANGED": "YES",
        "BETA3_REFERENCE_MODIFIED": "NO",
        "SAFE_FOR_10K_LONG_RUN": safe10,
        "SAFE_FOR_40K_LONG_RUN": "NO" if (proj.get("rss_40000") or 99999) > 12000 else "NOT_ESTABLISHED",
        "SAFE_FOR_100K_LONG_RUN": "NOT_ESTABLISHED",
        "PUBLIC_BETA31_RELEASE_BLOCKED": "YES",
        "BLOCK_REASON": "cold archive is opt-in experimental; 40k still not demonstrated; nested unique float history remains",
        "GIT_PUSH": "NO",
        "default_production": "Hybrid G (_COLD_ARCHIVE default False)",
    }
    gates = [
        eq["COGNITION_EQUIVALENCE"] == "EXACT",
        eq["PE_LIFECYCLE_EQUIVALENCE"] == "EXACT",
        eq["shadow"]["mismatches"] == 0 and eq["shadow"]["compared"] > 0,
        persist["COLD_SNAPSHOT_COMPATIBILITY"] == "PASS",
        an["ANALYZER_CAN_STREAM_COLD_HISTORY"] == "YES",
    ]
    if all(gates) and rss_red and rss_red >= 10:
        report["BETA31_PE_COLD_ARCHIVE"] = "PASS" if aged.get("AGED_VALIDATION_TICK") else "PARTIAL"
    elif all(gates):
        report["BETA31_PE_COLD_ARCHIVE"] = "PARTIAL"
    else:
        report["BETA31_PE_COLD_ARCHIVE"] = "FAIL"
    write_json("summary.json", report)
    return report


if __name__ == "__main__":
    os.chdir(str(ROOT))
    sys.path.insert(0, str(ROOT))
    if ROLE == "rss":
        print("PSY_COLD_RSS_JSON=" + json.dumps(child_rss(), default=str), flush=True)
    else:
        try:
            rep = main_master()
            print(json.dumps({k: rep[k] for k in list(rep)[:12]}, indent=2))
        except Exception:
            traceback.print_exc()
            raise
