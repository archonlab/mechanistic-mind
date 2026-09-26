"""Track A: post-PE-compaction RSS reconciliation. No unattended 40k."""
from __future__ import annotations

import gc
import json
import os
import resource
import sys
import time
import tracemalloc
from array import array
from collections import deque
from pathlib import Path
from types import ModuleType

ROOT = Path("/home/thehost/Desktop/psy")
OUT = ROOT / "results" / "beta31_post_pe_memory_reconciliation"
SEED = 575
CEILING = float(os.environ.get("PSY_RSS_CEILING_DELTA_MB", "2048"))
ROLE = os.environ.get("PSY_MEM_ROLE", "master")


def _proc() -> dict:
    st = Path("/proc/self/status").read_text()
    kv = {}
    for line in st.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            kv[k.strip()] = v.strip()

    def kb(key: str) -> int:
        return int(str(kv.get(key, "0")).split()[0] or 0)

    roll = {}
    rp = Path("/proc/self/smaps_rollup")
    if rp.is_file():
        try:
            for line in rp.read_text().splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    roll[k.strip()] = v.strip()
        except OSError:
            roll = {}

    def rkb(key: str) -> int:
        return int(str(roll.get(key, "0")).split()[0] or 0)

    maps_n = 0
    try:
        maps_n = sum(1 for _ in Path("/proc/self/maps").open())
    except OSError:
        pass
    return {
        "rss_mb": round(kb("VmRSS") / 1024.0, 3),
        "rss_anon_mb": round(kb("RssAnon") / 1024.0, 3),
        "rss_file_mb": round(kb("RssFile") / 1024.0, 3),
        "rss_shmem_mb": round(kb("RssShmem") / 1024.0, 3),
        "vms_mb": round(kb("VmSize") / 1024.0, 3),
        "roll_anon_mb": round(rkb("Anonymous") / 1024.0, 3),
        "roll_private_dirty_mb": round(rkb("Private_Dirty") / 1024.0, 3),
        "maps": maps_n,
        "ru_maxrss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0, 3),
    }


def _sizeof(obj, seen: set[int], budget: list[int]) -> int:
    oid = id(obj)
    if oid in seen:
        return 0
    seen.add(oid)
    budget[0] -= 1
    if budget[0] <= 0:
        return 0
    n = sys.getsizeof(obj)
    if isinstance(obj, dict):
        for k, v in obj.items():
            n += _sizeof(k, seen, budget) + _sizeof(v, seen, budget)
    elif isinstance(obj, (list, tuple, set, deque, frozenset)):
        for x in obj:
            n += _sizeof(x, seen, budget)
    elif isinstance(obj, array):
        return n
    return n


def sizeof_root(obj, budget: int = 800_000) -> int:
    return _sizeof(obj, set(), [budget])


def make_runtime(*, pe: bool = True, stub_forgotten: bool = False):
    from experiments.run_beta31_pe_forgotten_compaction import make_runtime as _mr
    from mechanistic_mind.research import predictive_equivalence as pe_mod

    if stub_forgotten:
        orig = pe_mod.compact_forgotten_class

        def stub(cls):
            if not isinstance(cls, dict) or cls.get("status") != "FORGOTTEN":
                return cls
            orig(cls)
            cls["members"] = {}
            cls["_pack_keys"] = []
            cls["_pe_forgotten_rep"] = "forensic_stub"
            return cls

        pe_mod.compact_forgotten_class = stub  # type: ignore
    rt = _mr()
    if not pe:
        for slot in rt.slots:
            cog_cfg = slot.config.cognition
            cog_cfg.predictive_equivalence = False
            cog_cfg.temporal_predictive_structure = False
            cog_cfg.temporal_prediction_error = False
            cd = slot.cognition.get("config")
            if isinstance(cd, dict):
                cd["predictive_equivalence"] = False
                cd["temporal_predictive_structure"] = False
                cd["temporal_prediction_error"] = False
            eq = slot.cognition.get("equivalence")
            if isinstance(eq, dict):
                eq["enabled"] = False
            inner = ((slot.cognition.get("temporal") or {}).get("inner"))
            if isinstance(inner, dict):
                inner["enabled"] = False
    return rt


def pe_breakdown(store: dict) -> dict:
    from mechanistic_mind.research import predictive_equivalence as pe

    classes = store.get("classes") or {}
    active = forgotten = packed = 0
    shell = compact_payload = aabb_b = mean_b = prov_b = rel_b = keys_b = 0
    n_mem = 0
    for cls in classes.values():
        if not isinstance(cls, dict):
            continue
        members = cls.get("members") or {}
        n_mem += len(members) if isinstance(members, dict) else 0
        sh = {k: v for k, v in cls.items() if k != "members"}
        if cls.get("status") == "FORGOTTEN":
            forgotten += 1
            if pe.is_forgotten_packed(cls):
                packed += 1
            shell += sizeof_root(sh)
            compact_payload += sizeof_root(members)
            aabb_b += sizeof_root(cls.get("aabb"))
            mean_b += sizeof_root(cls.get("mean_c"))
            prov_b += sizeof_root(cls.get("provenance"))
            rel_b += sizeof_root(cls.get("relevance"))
            keys_b += sizeof_root(cls.get("_pack_keys"))
        else:
            active += 1
            shell += sizeof_root(sh)
            compact_payload += sizeof_root(members)
    return {
        "n_classes": len(classes),
        "n_active": active,
        "n_forgotten": forgotten,
        "n_packed": packed,
        "n_members": n_mem,
        "bytes_shell": shell,
        "bytes_members": compact_payload,
        "bytes_aabb": aabb_b,
        "bytes_mean_c": mean_b,
        "bytes_provenance": prov_b,
        "bytes_relevance": rel_b,
        "bytes_pack_keys": keys_b,
        "bytes_store": sizeof_root(store),
    }


def cognition_roots(slot) -> dict:
    cog = slot.cognition if isinstance(slot.cognition, dict) else {}
    out = {}
    for k, v in cog.items():
        out[str(k)] = sizeof_root(v)
    eq = cog.get("equivalence") or {}
    inner = ((cog.get("temporal") or {}).get("inner") if isinstance(cog.get("temporal"), dict) else None) or {}
    return {
        "keys_bytes": out,
        "pe": pe_breakdown(eq) if isinstance(eq, dict) else {},
        "tps_inner_pe": pe_breakdown(inner) if isinstance(inner, dict) else {},
        "cognition_bytes": sizeof_root(cog),
        "smc_n": len((cog.get("sensorimotor_consequence") or {}).get("records") or {}),
        "compression_n": len(cog.get("compression") or {}) if isinstance(cog.get("compression"), dict) else None,
        "prospection_n": len(((cog.get("prospection") or {}).get("transitions") or {})) if isinstance(cog.get("prospection"), dict) else None,
    }


def cheap_card(rt) -> dict:
    agents = []
    for i, slot in enumerate(rt.slots):
        cog = slot.cognition if isinstance(slot.cognition, dict) else {}
        eq = cog.get("equivalence") or {}
        classes = eq.get("classes") or {}
        n_for = sum(1 for c in classes.values() if isinstance(c, dict) and c.get("status") == "FORGOTTEN")
        inner = ((cog.get("temporal") or {}).get("inner") or {}) if isinstance(cog.get("temporal"), dict) else {}
        ic = (inner.get("classes") or {}) if isinstance(inner, dict) else {}
        n_for_i = sum(1 for c in ic.values() if isinstance(c, dict) and c.get("status") == "FORGOTTEN")
        smc = cog.get("sensorimotor_consequence") or {}
        rec = smc.get("records") if isinstance(smc, dict) else None
        pr = cog.get("prospection") or {}
        trans = pr.get("transitions") if isinstance(pr, dict) else None
        pc = cog.get("compression") or {}
        agents.append({
            "slot": i,
            "pe_classes": len(classes) if isinstance(classes, dict) else 0,
            "pe_forgotten": n_for,
            "tps_inner_forgotten": n_for_i,
            "smc_n": len(rec) if isinstance(rec, dict) else None,
            "prospection_n": len(trans) if isinstance(trans, dict) else None,
            "compression_top_keys": len(pc) if isinstance(pc, dict) else None,
        })
    return {"agents": agents}


def card(rt) -> dict:
    agents = []
    world_nbytes = 0
    w = rt.world
    for name in ("T", "M", "vx", "vy", "u", "FIELD_A", "FIELD_B", "OSC_BANDS", "surface_optical", "surface_response"):
        arr = getattr(w, name, None)
        if arr is not None and hasattr(arr, "nbytes"):
            world_nbytes += int(arr.nbytes)
    for i, slot in enumerate(rt.slots):
        agents.append({
            "slot": i,
            "cognition": cognition_roots(slot),
        })
    return {
        "world_nbytes": world_nbytes,
        "agents": agents,
    }


def census() -> dict[str, int]:
    import collections
    c: dict[str, int] = {}
    for obj in gc.get_objects():
        n = type(obj).__name__
        c[n] = c.get(n, 0) + 1
    top = sorted(c.items(), key=lambda kv: -kv[1])[:25]
    return dict(top)


def run_probe(*, pe: bool, stub: bool, ticks: list[int], tracemalloc_window: tuple[int, int] | None) -> dict:
    rt = make_runtime(pe=pe, stub_forgotten=stub)
    t0w = time.perf_counter()
    base = _proc()
    samples = []
    tm_delta = None
    tracing = False
    current = int(rt.tick)
    for target in ticks:
        while current < target:
            if tracemalloc_window and current == tracemalloc_window[0] and not tracing:
                tracemalloc.start(8)
                tracing = True
                tm_snap = tracemalloc.take_snapshot()
            rt.step(n=1)
            current = int(rt.tick)
            if _proc()["rss_mb"] - base["rss_mb"] > CEILING:
                break
            if tracing and tracemalloc_window and current >= tracemalloc_window[1]:
                snap2 = tracemalloc.take_snapshot()
                stats = snap2.compare_to(tm_snap, "lineno")[:20]
                tm_delta = [
                    {
                        "file": str(s.traceback[0]).split(",")[0] if s.traceback else "",
                        "size_diff_mb": round(s.size_diff / (1024 * 1024), 4),
                        "count_diff": s.count_diff,
                        "traceback": [str(f) for f in s.traceback[:4]],
                    }
                    for s in stats if s.size_diff > 0
                ]
                tracemalloc.stop()
                tracing = False
        rec = {
            "tick": int(rt.tick),
            "wall_s": round(time.perf_counter() - t0w, 3),
            "proc": _proc(),
            "cheap": cheap_card(rt),
            "card": None,
            "census": None,
        }
        if int(rt.tick) == ticks[-1]:
            rec["card"] = card(rt)
            rec["census"] = census()
        samples.append(rec)
        if _proc()["rss_mb"] - base["rss_mb"] > CEILING:
            break
    if tracing:
        tracemalloc.stop()
    gc.collect()
    after_gc = _proc()
    return {
        "pe": pe,
        "stub": stub,
        "baseline": base,
        "samples": samples,
        "tracemalloc_delta": tm_delta,
        "after_gc": after_gc,
        "tps": round((samples[-1]["tick"] / samples[-1]["wall_s"]) if samples and samples[-1]["wall_s"] else 0, 4),
    }


def slope(samples, key=lambda s: s["proc"]["rss_mb"]):
    pts = [(s["tick"], key(s)) for s in samples if s.get("tick")]
    if len(pts) < 2:
        return None
    (t0, r0), (t1, r1) = pts[0], pts[-1]
    if t1 == t0:
        return None
    return round((r1 - r0) * 1000.0 / (t1 - t0), 3)


def accounted(sample) -> int:
    n = int((sample.get("card") or {}).get("world_nbytes") or 0)
    for a in (sample.get("card") or {}).get("agents") or []:
        n += int((a.get("cognition") or {}).get("cognition_bytes") or 0)
    return n


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    os.chdir(str(ROOT))
    OUT.mkdir(parents=True, exist_ok=True)
    ticks = [int(x) for x in os.environ.get("PSY_MEM_TICKS", "0,100,250,500,1000").split(",") if x]
    pe = os.environ.get("PSY_MEM_PE", "1") != "0"
    stub = os.environ.get("PSY_MEM_STUB", "0") == "1"
    tm = None
    result = run_probe(pe=pe, stub=stub, ticks=ticks, tracemalloc_window=tm)
    name = os.environ.get("PSY_MEM_OUT", "probe.json")
    (OUT / name).write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"wrote": name, "rss_slope": slope(result["samples"]), "tps": result.get("tps")}))
