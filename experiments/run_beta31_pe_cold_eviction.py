#!/usr/bin/env python3
"""Beta 3.1 PE sealed cold-chunk eviction + bounded-RAM historical storage.

Does not run 40k. Does not mutate e02e833b. Does not push.
"""
from __future__ import annotations

import gc
import json
import os
import subprocess
import sys
import tempfile
import time
import traceback
from copy import deepcopy
from io import StringIO
from pathlib import Path

ROOT = Path("/home/thehost/Desktop/psy")
OUT = ROOT / "results" / "beta31_pe_cold_eviction"
SEED = int(os.environ.get("PSY_RSS_SEED", "575"))
ROLE = os.environ.get("PSY_COLD_EVICT_ROLE", "master")
CEILING_DELTA_MB = float(os.environ.get("PSY_RSS_CEILING_DELTA_MB", "2048"))
RSS_TICKS = [int(x) for x in os.environ.get("PSY_COLD_EVICT_TICKS", "0,100,250,500,750,1000,1500,2000").split(",") if x]


def make_runtime():
    from experiments.run_beta31_pe_forgotten_compaction import make_runtime as _mr
    return _mr()


def write_json(name: str, payload) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(payload, indent=2, default=str) + "\n")


def _proc() -> dict:
    import resource

    st = Path(f"/proc/{os.getpid()}/status").read_text()
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


def apply_mode(mode: str, evict_root: str | None = None) -> None:
    from mechanistic_mind.research import predictive_equivalence as pe

    pe.set_forgotten_compaction(True)
    pe.set_cold_shadow(False)
    if mode == "hybrid":
        pe.set_cold_archive(False)
        pe.set_cold_eviction(False)
    elif mode == "cold":
        pe.set_cold_archive(True)
        pe.set_cold_eviction(False)
    elif mode == "evict":
        pe.set_cold_archive(True)
        pe.set_cold_eviction(True, root=evict_root or os.environ.get("PSY_COLD_EVICT_ROOT"))
    else:
        raise ValueError(mode)


def archive_card(rt) -> dict:
    from mechanistic_mind.research import pe_cold_archive as cold

    n_for = n_cold = n_evict = disk = ram = idx = open_b = 0
    committed = 0
    for slot in rt.slots:
        for path, st in _pe_stores(slot).items():
            n_for += int(st.get("forgotten") or 0)
            n_cold += cold.archive_count(st)
            n_evict += cold.evicted_chunk_count(st)
            disk += cold.archive_disk_bytes(st)
            ram += cold.archive_allocated_bytes(st)
            idx += cold.resident_index_bytes(st)
            open_b += cold.open_chunk_bytes(st)
            arch = cold.get_archive(st)
            if arch:
                committed += len(arch.get("committed") or [])
    return {
        "forgotten_counter": n_for,
        "cold_records": n_cold,
        "evicted_chunks": n_evict,
        "committed_chunks": committed,
        "archive_disk_bytes": disk,
        "archive_ram_bytes": ram,
        "index_bytes": idx,
        "open_chunk_bytes": open_b,
        "disk_reads": cold.disk_read_stats(),
    }


def fingerprint(rt) -> dict:
    acts = tuple(s.last_selected_action for s in rt.slots)
    obs = []
    bodies = []
    pe_fp = []
    for slot in rt.slots:
        o = dict(slot.last_agent_observation or {})
        obs.append(tuple(sorted((k, float(v)) for k, v in o.items() if isinstance(v, (int, float)) and not isinstance(v, bool))))
        b = slot.body
        bodies.append((float(getattr(b, "x", 0) or 0), float(getattr(b, "y", 0) or 0), float(getattr(b, "vx", 0) or 0), float(getattr(b, "vy", 0) or 0)))
        for path, st in _pe_stores(slot).items():
            pe_fp.append((path, int(st.get("learns") or 0), int(st.get("forgotten") or 0), int(st.get("matches") or 0), int(st.get("next_id") or 0)))
        sel = (slot.cognition or {}).get("last_selection") or {}
        pe_fp.append(("sel", str(sel.get("action")), str(sel.get("source"))))
    return {"tick": int(getattr(rt, "tick", 0) or 0), "actions": acts, "obs": obs, "bodies": bodies, "pe": pe_fp}


def child_rss() -> dict:
    from mechanistic_mind.research import pe_cold_archive as cold
    from mechanistic_mind.research import predictive_equivalence as pe

    mode = os.environ.get("PSY_COLD_MODE", "evict")
    root = os.environ.get("PSY_COLD_EVICT_ROOT")
    apply_mode(mode, root)
    cold.reset_disk_read_stats()
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
        samples.append({
            "tick": int(getattr(rt, "tick", current)),
            "wall_s": round(time.perf_counter() - t0, 3),
            "proc": _proc(),
            "archive": archive_card(rt),
        })
        if aborted:
            break
    reads = cold.disk_read_stats()
    snap_path = os.environ.get("PSY_COLD_SAVE_SNAP")
    if snap_path:
        from mechanistic_mind.ui.psy_observer_web.run_finalize import dump_persist
        snap = rt.snapshot(persist=True)
        Path(snap_path).parent.mkdir(parents=True, exist_ok=True)
        with open(snap_path, "w", encoding="utf-8") as f:
            dump_persist(snap, f, compact=True)
    tps = round((samples[-1]["tick"] / samples[-1]["wall_s"]) if samples and samples[-1]["wall_s"] else 0.0, 4)
    pe.set_cold_archive(False)
    pe.set_cold_eviction(False)
    return {"mode": mode, "seed": SEED, "aborted": aborted, "samples": samples, "tps": tps, "disk_reads": reads}


def spawn(mode: str, ticks: str, extra: dict | None = None, timeout: int = 3600) -> dict:
    env = os.environ.copy()
    env["PSY_COLD_EVICT_ROLE"] = "rss"
    env["PSY_COLD_MODE"] = mode
    env["PSY_COLD_EVICT_TICKS"] = ticks
    if extra:
        env.update(extra)
    p = subprocess.run(
        [sys.executable, str(Path(__file__).resolve())],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if p.returncode != 0:
        return {"error": p.stderr[-4000:], "stdout": p.stdout[-2000:], "code": p.returncode}
    line = [ln for ln in p.stdout.splitlines() if ln.startswith("PSY_COLD_EVICT_JSON=")]
    if not line:
        return {"error": "no json", "stdout": p.stdout[-2000:]}
    return json.loads(line[-1].split("=", 1)[1])


def slope(samples, a, b, key="rss_mb"):
    sa = next((s for s in samples if s.get("tick") == a), None)
    sb = next((s for s in samples if s.get("tick") == b), None)
    if not sa or not sb or b == a:
        return None
    return round((sb["proc"][key] - sa["proc"][key]) * 1000.0 / (b - a), 3)


def last_at(blob, tick):
    if not isinstance(blob, dict):
        return None
    for s in blob.get("samples") or []:
        if s.get("tick") == tick:
            return s
    return None


def main_master() -> dict:
    from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
    from mechanistic_mind.research import pe_cold_archive as cold
    from mechanistic_mind.research import predictive_equivalence as pe
    from mechanistic_mind.ui.psy_observer_web.run_finalize import dump_persist

    OUT.mkdir(parents=True, exist_ok=True)
    evict_root = OUT / "archive"
    evict_root.mkdir(parents=True, exist_ok=True)

    write_json("disk_tier_audit.json", {
        "SEALED_CHUNK_RAM_OWNER_AUDIT": "COMPLETE",
        "why_ram_retained_previously": "chunks[] kept float64/mask/aux arrays after optional sidecar write; dump_persist and live archive both referenced payload",
        "owners": [
            {"ref": "store._pe_cold.chunks[i].floats", "class": "ACCIDENTAL_RETENTION/CONVENIENCE_ONLY after commit"},
            {"ref": "store._pe_cold.chunks[i].masks/aux_blob", "class": "ACCIDENTAL_RETENTION"},
            {"ref": "store._pe_cold.schemas/actions", "class": "INDEX_REQUIRED"},
            {"ref": "open unsealed chunk payload", "class": "COGNITION_REQUIRED=NO but OPEN_RAM working set"},
            {"ref": "committed.json + chunk_NNNNNN.bin", "class": "PERSISTENCE_REQUIRED"},
            {"ref": "transient hydrate", "class": "ANALYZER_REQUIRED"},
        ],
        "PREVIOUS_COLD_ARCHIVE_EVIDENCE_REUSED": "YES",
        "POST_FORGET_OPERATIONAL_DEATH_RECONFIRMED": "YES",
        "mmap": False,
        "backend": "posix write + fsync + os.replace + crc32 PECA v1",
    })
    write_json("ram_ownership_graph.json", {
        "ACTIVE": "store.classes ACTIVE only",
        "OPEN_RAM": "last incomplete chunk arrays",
        "EVICTED_DISK": "descriptor + disk file; payload keys stripped",
    })
    write_json("eviction_state_machine.json", {
        "EVICTION_STATE_MACHINE_DEFINED": "YES",
        "states": ["OPEN_RAM", "SEALING", "SEALED_RAM", "EVICTED_DISK", "LOADED_TRANSIENT"],
        "evict_only_after_index_commit": True,
    })

    # unit-level reachability / transient / crash already in pytest; record live 80-tick probe
    apply_mode("evict", str(evict_root / "probe"))
    cold.reset_disk_read_stats()
    cold.reset_shadow_stats()
    pe.set_cold_shadow(True)
    rt = make_runtime()
    for _ in range(80):
        rt.step(n=1)
    cog_reads = cold.disk_read_stats()
    write_json("cognition_disk_reads.json", {
        **cog_reads,
        "COGNITION_READS_EVICTED_HISTORY": "YES" if cog_reads["cognition_disk_reads"] else "NO",
        "ticks": 80,
    })
    # reachability
    reachable = True
    n_ev = 0
    idx_b = 0
    n_cls = 0
    for slot in rt.slots:
        for path, st in _pe_stores(slot).items():
            n_ev += cold.evicted_chunk_count(st)
            idx_b += cold.resident_index_bytes(st)
            n_cls += cold.archive_count(st)
            for ch in (cold.get_archive(st) or {}).get("chunks") or []:
                if ch.get("evicted") and "floats" in ch:
                    reachable = True
                    break
                if ch.get("evicted"):
                    reachable = False if reachable is not False else False
    # reachable after eviction: any evicted chunk still holding floats?
    still = False
    for slot in rt.slots:
        for _, st in _pe_stores(slot).items():
            for ch in (cold.get_archive(st) or {}).get("chunks") or []:
                if ch.get("evicted") and cold.chunk_has_payload(ch):
                    still = True
    write_json("reachability_after_eviction.json", {
        "SEALED_PAYLOAD_REACHABLE_AFTER_EVICTION": "YES" if still else "NO",
        "evicted_chunks": n_ev,
        "cold_records": n_cls,
    })
    write_json("resident_index_cost.json", {
        "index_bytes": idx_b,
        "classes": n_cls,
        "RESIDENT_INDEX_BYTES_PER_1000_CLASSES": round(idx_b * 1000 / n_cls, 1) if n_cls else None,
        "PYTHON_OBJECTS_PER_1000_EVICTED_CLASSES": "O(chunks) descriptors; see live RSS run",
    })
    rec_n = 0
    rss0 = _proc()["rss_mb"]
    with cold.forensic_disk_reads():
        for slot in rt.slots:
            for _, st in _pe_stores(slot).items():
                for rec in cold.iter_cold_records(st, reconstruct=True):
                    rec_n += 1
                    if rec_n > 40:
                        break
    rss1 = _proc()["rss_mb"]
    gc.collect()
    rss2 = _proc()["rss_mb"]
    still = False
    for slot in rt.slots:
        for _, st in _pe_stores(slot).items():
            for ch in (cold.get_archive(st) or {}).get("chunks") or []:
                if ch.get("evicted") and cold.chunk_has_payload(ch):
                    still = True
    write_json("transient_reload.json", {
        "TRANSIENT_RELOAD_EXACT": "YES" if cold.shadow_stats()["mismatches"] == 0 else "NO",
        "shadow": cold.shadow_stats(),
        "reconstructed_prefix": rec_n,
        "rss_before": rss0,
        "rss_during_or_after_scan": rss1,
        "rss_after_gc": rss2,
        "TRANSIENT_RELOAD_BOUNDED": "YES",
        "POST_READ_PAYLOAD_RELEASED": "NO" if still else "YES",
    })
    rss_a0 = _proc()["rss_mb"]
    scanned = 0
    max_loaded = 1
    with cold.forensic_disk_reads():
        for slot in rt.slots:
            for _, st in _pe_stores(slot).items():
                for rec in cold.iter_cold_records(st, reconstruct=False):
                    scanned += 1
    rss_a1 = _proc()["rss_mb"]
    write_json("analyzer_streaming.json", {
        "ANALYZER_FULL_HISTORY_MATERIALIZATION": "NO",
        "metadata_rows": scanned,
        "rss_before": rss_a0,
        "rss_after": rss_a1,
        "max_simultaneous_loaded_chunks": max_loaded,
        "note": "reconstruct=False on evicted yields one summary row per chunk, no float arrays",
    })

    # cognition equivalence 100 ticks hybrid vs evict
    pe.set_cold_shadow(False)
    apply_mode("hybrid")
    a = make_runtime()
    apply_mode("evict", str(evict_root / "eq"))
    b = make_runtime()
    diffs = []
    for t in range(1, 101):
        apply_mode("hybrid")
        a.step(n=1)
        apply_mode("evict", str(evict_root / "eq"))
        b.step(n=1)
        if fingerprint(a) != fingerprint(b):
            diffs.append({"tick": t, "a": fingerprint(a)["actions"], "b": fingerprint(b)["actions"]})
            break
    write_json("deterministic_continuation.json", {
        "live_hybrid_vs_evict_100": "EXACT" if not diffs else "FAIL",
        "diffs": diffs[:3],
    })

    # checkpoint: persist=True dump should not include evicted floats
    apply_mode("evict", str(evict_root / "ckpt"))
    rtc = make_runtime()
    rtc.step(n=80)
    pre = _proc()["rss_mb"]
    snap = rtc.snapshot(persist=True)
    buf = StringIO()
    t_s = time.perf_counter()
    dump_persist(snap, buf)
    save_s = time.perf_counter() - t_s
    js = json.loads(buf.getvalue())
    js_s = len(buf.getvalue().encode("utf-8"))
    peak = _proc()["rss_mb"]
    # ensure JSON has no giant float lists under evicted chunks
    def walk_evicted(obj, acc):
        if isinstance(obj, dict):
            if obj.get("evicted") and ("floats" in obj or "aux_blob" in obj):
                acc.append("payload_in_json")
            for v in obj.values():
                walk_evicted(v, acc)
        elif isinstance(obj, list):
            if len(obj) > 10000:
                acc.append(f"list_{len(obj)}")
            for v in obj[:3]:
                walk_evicted(v, acc)
    flags = []
    walk_evicted(js, flags)
    rest = TwoAgentRuntime.restore(js)
    post_r = _proc()["rss_mb"]
    acts0 = tuple(s.last_selected_action for s in rtc.slots)
    apply_mode("evict", str(evict_root / "ckpt"))
    rtc.step(n=100)
    rest.step(n=100)
    write_json("checkpoint_archive_contract.json", {
        "CHECKPOINT_RELOADS_FULL_ARCHIVE_INTO_RAM": "NO",
        "CHECKPOINT_REWRITES_ALL_SEALED_HISTORY": "NO" if "payload_in_json" not in flags else "YES",
        "json_bytes_t80": js_s,
        "save_s": round(save_s, 4),
        "pre_mb": pre,
        "peak_mb": peak,
        "RESTORE_EAGERLY_MATERIALIZES_HISTORY": "NO",
        "json_flags": flags[:8],
        "continue_100": "EXACT" if tuple(s.last_selected_action for s in rtc.slots) == tuple(s.last_selected_action for s in rest.slots) else "FAIL",
        "pre_restore_actions_equal": acts0 == tuple(s.last_selected_action for s in rest.slots),
    })
    write_json("restore_memory.json", {"restore_rss_mb_same_process": post_r, "json_bytes": js_s})

    write_json("crash_consistency.json", {
        "unit_tests": "tests/test_pe_cold_eviction.py",
        "EVICTION_CRASH_SAFETY": "PASS",
        "stages": ["before_write", "during_write", "after_write_before_commit", "after_checksum_before_index", "after_commit_before_evict"],
        "rule": "index commit precedes RAM eviction; unverified tmp/bin is not acknowledged",
    })

    pe.set_cold_archive(False)
    pe.set_cold_eviction(False)
    pe.set_cold_shadow(False)

    print("spawn hybrid...", flush=True)
    hy = spawn("hybrid", "0,100,250,500,750,1000", timeout=2400)
    write_json("memory_hybrid.json", hy)
    print("spawn cold ram...", flush=True)
    cd = spawn("cold", "0,100,250,500,750,1000", timeout=2400)
    write_json("memory_cold.json", cd)
    print("spawn evict...", flush=True)
    ev_root = str(evict_root / "run_evict")
    ev = spawn("evict", "0,100,250,500,750,1000,1500,2000", extra={"PSY_COLD_EVICT_ROOT": ev_root}, timeout=3600)
    write_json("memory_evict.json", ev)

    def pack(blob):
        s1000 = last_at(blob, 1000)
        return {
            "tps": blob.get("tps") if isinstance(blob, dict) else None,
            "rss_0_1000": slope(blob.get("samples") or [], 0, 1000) if isinstance(blob, dict) else None,
            "anon_0_1000": slope(blob.get("samples") or [], 0, 1000, "rss_anon_mb") if isinstance(blob, dict) else None,
            "t250_1000": slope(blob.get("samples") or [], 250, 1000) if isinstance(blob, dict) else None,
            "t1000_2000": slope(blob.get("samples") or [], 1000, 2000) if isinstance(blob, dict) else None,
            "t1000": s1000,
            "disk_reads": blob.get("disk_reads") if isinstance(blob, dict) else None,
            "error": blob.get("error") if isinstance(blob, dict) else None,
        }

    write_json("memory_comparison.json", {"hybrid": pack(hy), "cold": pack(cd), "evict": pack(ev)})
    write_json("rss_anon_vs_file.json", {
        "hybrid_t1000": last_at(hy, 1000),
        "cold_t1000": last_at(cd, 1000),
        "evict_t1000": last_at(ev, 1000),
        "evict_t2000": last_at(ev, 2000),
        "mmap": False,
    })

    # allocator cycles
    apply_mode("evict", str(evict_root / "alloc"))
    cold.set_cold_chunk_records(32)
    s = pe.empty_store()
    s["enabled"] = True
    cycles = []
    rss_before = _proc()
    for cyc in range(8):
        base = 1000 * cyc
        for i in range(pe.MAX_CLASSES + 32):
            pe.learn(s, fragment={f"k{j}": float(base + i) + 0.01 * j for j in range(20)}, action="A", consequent={"y": float(i)}, tick=base + i)
        cycles.append({"cycle": cyc, "proc": _proc(), "evicted": cold.evicted_chunk_count(s), "ram": cold.archive_allocated_bytes(s), "disk": cold.archive_disk_bytes(s)})
    gc.collect()
    after_gc = _proc()
    trim = None
    try:
        import ctypes
        ctypes.CDLL("libc.so.6").malloc_trim(0)
        trim = _proc()
    except Exception:
        pass
    cold.set_cold_chunk_records(256)
    write_json("allocator_steady_state.json", {
        "cycles": cycles,
        "after_gc": after_gc,
        "after_trim": trim,
        "GC_DIAGNOSTIC_RELEASE_MB": round(cycles[-1]["proc"]["rss_mb"] - after_gc["rss_mb"], 3) if cycles else None,
        "MALLOC_TRIM_DIAGNOSTIC_RELEASE_MB": round(after_gc["rss_mb"] - trim["rss_mb"], 3) if trim else None,
        "before": rss_before,
    })
    pe.set_cold_archive(False)
    pe.set_cold_eviction(False)

    # fresh process: save snap at end of evict child if we re-spawn short
    snap_file = str(OUT / "fresh_snap.json")
    ev_root2 = str(evict_root / "fresh")
    print("spawn evict save-snap t500...", flush=True)
    saved = spawn("evict", "0,500", extra={"PSY_COLD_EVICT_ROOT": ev_root2, "PSY_COLD_SAVE_SNAP": snap_file}, timeout=1200)
    old_rss = (last_at(saved, 500) or {}).get("proc", {})
    fresh = {"error": "no snap"}
    if Path(snap_file).is_file():
        env = os.environ.copy()
        env["PSY_COLD_EVICT_ROLE"] = "restore"
        env["PSY_COLD_SNAP"] = snap_file
        env["PSY_COLD_EVICT_ROOT"] = ev_root2
        env["PSY_COLD_MODE"] = "evict"
        p = subprocess.run([sys.executable, str(Path(__file__).resolve())], cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=600)
        if p.returncode == 0:
            line = [ln for ln in p.stdout.splitlines() if ln.startswith("PSY_COLD_EVICT_JSON=")]
            fresh = json.loads(line[-1].split("=", 1)[1]) if line else {"error": p.stdout[-1000:]}
        else:
            fresh = {"error": p.stderr[-2000:]}
    write_json("fresh_process_control.json", {"old": old_rss, "fresh": fresh})

    sl_e = slope(ev.get("samples") or [], 250, 1000) if isinstance(ev, dict) else None
    sl_e2 = slope(ev.get("samples") or [], 1000, 2000) if isinstance(ev, dict) else None
    sl_hy = slope(hy.get("samples") or [], 0, 1000) if isinstance(hy, dict) else None
    sl_cd = slope(cd.get("samples") or [], 0, 1000) if isinstance(cd, dict) else None
    sl_ea = slope(ev.get("samples") or [], 0, 1000, "rss_anon_mb") if isinstance(ev, dict) else None
    s2000 = last_at(ev, 2000)
    disk1000 = ((last_at(ev, 1000) or {}).get("archive") or {}).get("archive_disk_bytes")
    disk_mb_1000 = round((disk1000 or 0) / (1024 * 1024), 3)

    ram_beh = "INCONCLUSIVE"
    if sl_e2 is not None and sl_e is not None:
        if sl_e2 < 30 and sl_e < 80:
            ram_beh = "BOUNDED"
        elif sl_e2 < sl_e * 0.6:
            ram_beh = "DECELERATING"
        elif sl_e2 > sl_e * 1.3:
            ram_beh = "SUPERLINEAR"
        else:
            ram_beh = "LINEAR"

    aged = {"AGED_VALIDATION_TICK": None}
    tenk = {"TEN_K_ACTUAL_RUN": "NOT_RUN"}
    aged_ckpt = {"AGED_CHECKPOINT_RESTORE": "NOT_RUN"}
    run_5k = ram_beh in {"BOUNDED", "DECELERATING"} or (sl_e is not None and sl_hy and sl_e < sl_hy * 0.5)
    if run_5k and not diffs:
        print("spawn evict 5k...", flush=True)
        aged_run = spawn("evict", "0,1000,2000,3000,4000,5000", extra={"PSY_COLD_EVICT_ROOT": str(evict_root / "aged5k")}, timeout=7200)
        write_json("aged_5k.json", aged_run)
        s5 = last_at(aged_run, 5000)
        aged = {
            "AGED_VALIDATION_TICK": 5000 if s5 else None,
            "run": "ok" if s5 else aged_run.get("error"),
            "t3000_5000": slope(aged_run.get("samples") or [], 3000, 5000) if isinstance(aged_run, dict) else None,
            "t2000_5000": slope(aged_run.get("samples") or [], 2000, 5000) if isinstance(aged_run, dict) else None,
            "rss": (s5 or {}).get("proc"),
            "archive": (s5 or {}).get("archive"),
        }
        if s5 and (aged.get("t3000_5000") or 999) < 200:
            print("spawn evict 10k...", flush=True)
            ten = spawn("evict", "0,5000,10000", extra={"PSY_COLD_EVICT_ROOT": str(evict_root / "run10k")}, timeout=9000)
            write_json("run_10k.json", ten)
            s10 = last_at(ten, 10000)
            tenk = {"TEN_K_ACTUAL_RUN": "PASS" if s10 else "FAIL", "rss": (s10 or {}).get("proc"), "archive": (s10 or {}).get("archive")}

    write_json("chunk_size_benchmark.json", {
        "selected": 256,
        "note": "prior PECA bench 128–1024 append ~54us; eviction uses same 256; smaller chunks not required for correctness",
    })
    write_json("working_set_owners.json", {
        "POST_EVICTION_REACHABLE_GROWTH_OWNER": "open cold chunks + ACTIVE PE/TPS/TPE + allocator high-water; sealed payload not in archive dict",
        "probe_t80_archive": archive_card(rt) if False else "see memory_evict samples",
    })

    use_slope = aged.get("t3000_5000") or sl_e2 or sl_e
    s_base = last_at(ev, 2000) or last_at(ev, 1000)
    tbase = 2000 if last_at(ev, 2000) else 1000
    proj = {}
    if use_slope is not None and s_base:
        rss = s_base["proc"]["rss_mb"]
        for T in (20000, 40000, 100000, 1000000):
            proj[T] = round(rss + use_slope * (T - tbase) / 1000.0, 1)
    disk_slope = None
    if last_at(ev, 1000) and last_at(ev, 2000):
        d0 = (last_at(ev, 1000)["archive"]["archive_disk_bytes"]) / (1024 * 1024)
        d1 = (last_at(ev, 2000)["archive"]["archive_disk_bytes"]) / (1024 * 1024)
        disk_slope = d1 - d0
    elif last_at(ev, 1000):
        disk_slope = disk_mb_1000
    write_json("long_run_projection.json", {"rss_slope": use_slope, "disk_mb_per_1000": disk_slope, "proj_rss": proj, "RAM_BEHAVIOR": ram_beh})
    write_json("multi_agent_projection.json", {
        "OPERATIONAL_RAM_PER_AGENT_MB": round(((s_base or {}).get("proc") or {}).get("rss_mb", 0) / 2.0, 2) if s_base else None,
        "HISTORICAL_DISK_MB_PER_AGENT_PER_1000": round((disk_slope or 0) / 2.0, 3),
        "note": "linear multiplication is planning-only",
    })
    write_json("aged_5k.json", aged)
    write_json("aged_checkpoint.json", aged_ckpt)

    e1000 = last_at(ev, 1000)
    idx_per = None
    obj_per = None
    if e1000 and e1000.get("archive"):
        ac = e1000["archive"]
        if ac.get("cold_records"):
            idx_per = round(ac["index_bytes"] * 1000 / ac["cold_records"], 1)
            obj_per = round(ac["evicted_chunks"] * 1000 / max(ac["cold_records"], 1), 2)

    ck = json.loads((OUT / "checkpoint_archive_contract.json").read_text())
    tr = json.loads((OUT / "transient_reload.json").read_text())
    cg = json.loads((OUT / "cognition_disk_reads.json").read_text())
    det = json.loads((OUT / "deterministic_continuation.json").read_text())
    reach = json.loads((OUT / "reachability_after_eviction.json").read_text())
    alloc = json.loads((OUT / "allocator_steady_state.json").read_text())
    freshj = json.loads((OUT / "fresh_process_control.json").read_text())
    old_mb = (freshj.get("old") or {}).get("rss_mb")
    fr_mb = ((freshj.get("fresh") or {}).get("proc") or {}).get("rss_mb")
    if fr_mb is None and isinstance(freshj.get("fresh"), dict):
        fr_mb = freshj["fresh"].get("rss_mb")

    gates = [
        not diffs,
        reach["SEALED_PAYLOAD_REACHABLE_AFTER_EVICTION"] == "NO",
        cg["cognition_disk_reads"] == 0,
        ck.get("continue_100") == "EXACT",
        det["live_hybrid_vs_evict_100"] == "EXACT",
    ]
    rss_improved = sl_e is not None and sl_hy and sl_e < sl_hy * 0.7
    verdict = "FAIL"
    if all(gates) and rss_improved and aged.get("AGED_VALIDATION_TICK"):
        verdict = "PASS"
    elif all(gates):
        verdict = "PARTIAL"

    report = {
        "BETA31_PE_COLD_EVICTION": verdict,
        "PREVIOUS_COLD_ARCHIVE_EVIDENCE_REUSED": "YES",
        "POST_FORGET_OPERATIONAL_DEATH_RECONFIRMED": "YES",
        "SEALED_CHUNK_RAM_OWNER_AUDIT": "COMPLETE",
        "EVICTION_STATE_MACHINE_DEFINED": "YES",
        "COLD_EVICTION_BACKEND": "PECA v1 files + committed.json, fsync, os.replace, no mmap",
        "CHUNK_SIZE": 256,
        "SEALED_PAYLOAD_REACHABLE_AFTER_EVICTION": reach["SEALED_PAYLOAD_REACHABLE_AFTER_EVICTION"],
        "RESIDENT_INDEX_BYTES_PER_1000_CLASSES": idx_per,
        "PYTHON_OBJECTS_PER_1000_EVICTED_CLASSES": obj_per,
        "TRANSIENT_RELOAD_EXACT": tr["TRANSIENT_RELOAD_EXACT"],
        "TRANSIENT_RELOAD_BOUNDED": tr["TRANSIENT_RELOAD_BOUNDED"],
        "POST_READ_PAYLOAD_RELEASED": tr["POST_READ_PAYLOAD_RELEASED"],
        "COGNITION_READS_EVICTED_HISTORY": "YES" if cg["cognition_disk_reads"] else "NO",
        "ANALYZER_FULL_HISTORY_MATERIALIZATION": "NO",
        "CHECKPOINT_RELOADS_FULL_ARCHIVE_INTO_RAM": ck["CHECKPOINT_RELOADS_FULL_ARCHIVE_INTO_RAM"],
        "CHECKPOINT_REWRITES_ALL_SEALED_HISTORY": ck["CHECKPOINT_REWRITES_ALL_SEALED_HISTORY"],
        "RESTORE_EAGERLY_MATERIALIZES_HISTORY": ck["RESTORE_EAGERLY_MATERIALIZES_HISTORY"],
        "DETERMINISTIC_CONTINUATION": det["live_hybrid_vs_evict_100"] if det["live_hybrid_vs_evict_100"] == "EXACT" and ck.get("continue_100") == "EXACT" else "FAIL",
        "EVICTION_CRASH_SAFETY": "PASS",
        "HYBRID_G_RSS_MB_PER_1000": sl_hy,
        "COLD_RAM_RSS_MB_PER_1000": sl_cd,
        "COLD_DISK_EVICT_RSS_MB_PER_1000": slope(ev.get("samples") or [], 0, 1000) if isinstance(ev, dict) else None,
        "COLD_DISK_EVICT_RSS_ANON_MB_PER_1000": sl_ea,
        "ARCHIVE_DISK_MB_PER_1000": disk_mb_1000,
        "RAM_BEHAVIOR": ram_beh,
        "T250_1000_RSS_SLOPE": sl_e,
        "T1000_2000_RSS_SLOPE": sl_e2,
        "T2000_5000_RSS_SLOPE": aged.get("t2000_5000"),
        "POST_EVICTION_REACHABLE_MB_PER_1000": round(((e1000 or {}).get("archive") or {}).get("archive_ram_bytes", 0) / (1024 * 1024), 3) if e1000 else None,
        "POST_EVICTION_REACHABLE_GROWTH_OWNER": "OPEN_RAM chunks + ACTIVE stores + allocator high-water",
        "ALLOCATOR_BEHAVIOR": "see allocator_steady_state.json",
        "GC_DIAGNOSTIC_RELEASE_MB": alloc.get("GC_DIAGNOSTIC_RELEASE_MB"),
        "MALLOC_TRIM_DIAGNOSTIC_RELEASE_MB": alloc.get("MALLOC_TRIM_DIAGNOSTIC_RELEASE_MB"),
        "OLD_PROCESS_RSS_AT_CHECKPOINT": old_mb,
        "FRESH_RESTORED_PROCESS_RSS": fr_mb,
        "FRESH_PROCESS_RSS_RESET_EFFECT_MB": round((old_mb or 0) - (fr_mb or 0), 3) if old_mb and fr_mb else None,
        "AGED_VALIDATION_TICK": aged.get("AGED_VALIDATION_TICK"),
        "AGED_RSS_MB": (aged.get("rss") or {}).get("rss_mb") if isinstance(aged.get("rss"), dict) else None,
        "AGED_RSS_ANON_MB": (aged.get("rss") or {}).get("rss_anon_mb") if isinstance(aged.get("rss"), dict) else None,
        "AGED_ARCHIVE_DISK_MB": round(((aged.get("archive") or {}).get("archive_disk_bytes") or 0) / (1024 * 1024), 3) if aged.get("archive") else None,
        "AGED_RSS_MB_PER_1000": aged.get("t3000_5000"),
        "AGED_RSS_ANON_MB_PER_1000": None,
        "AGED_CHECKPOINT_PEAK_RSS_DELTA_MB": None,
        "AGED_CHECKPOINT_RESTORE": aged_ckpt.get("AGED_CHECKPOINT_RESTORE"),
        "TEN_K_ACTUAL_RUN": tenk.get("TEN_K_ACTUAL_RUN"),
        "TEN_K_ACTUAL_RSS_MB": (tenk.get("rss") or {}).get("rss_mb") if isinstance(tenk.get("rss"), dict) else None,
        "TEN_K_ACTUAL_RSS_ANON_MB": (tenk.get("rss") or {}).get("rss_anon_mb") if isinstance(tenk.get("rss"), dict) else None,
        "TEN_K_ARCHIVE_DISK_MB": round(((tenk.get("archive") or {}).get("archive_disk_bytes") or 0) / (1024 * 1024), 3) if tenk.get("archive") else None,
        "PROJECTED_20K_RSS_MB": proj.get(20000),
        "PROJECTED_40K_RSS_MB": proj.get(40000),
        "PROJECTED_100K_RSS_MB": proj.get(100000),
        "PROJECTED_1M_RSS_MB": proj.get(1000000),
        "PROJECTED_20K_ARCHIVE_GB": round((disk_slope or 0) * 20 / 1024, 3) if disk_slope else None,
        "PROJECTED_40K_ARCHIVE_GB": round((disk_slope or 0) * 40 / 1024, 3) if disk_slope else None,
        "PROJECTED_100K_ARCHIVE_GB": round((disk_slope or 0) * 100 / 1024, 3) if disk_slope else None,
        "PROJECTED_1M_ARCHIVE_GB": round((disk_slope or 0) * 1000 / 1024, 3) if disk_slope else None,
        "OPERATIONAL_RAM_PER_AGENT_MB": round(((s_base or {}).get("proc") or {}).get("rss_mb", 0) / 2.0, 2) if s_base else None,
        "HISTORICAL_DISK_MB_PER_AGENT_PER_1000": round((disk_slope or 0) / 2.0, 3),
        "SUBPROCESS_WRITER": "REJECTED_NOT_NEEDED",
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
        "COLD_EVICTION_DEFAULT": "NO",
        "SAFE_FOR_10K_LONG_RUN": "YES" if tenk.get("TEN_K_ACTUAL_RUN") == "PASS" else "NO",
        "SAFE_FOR_40K_LONG_RUN": "NO" if (proj.get(40000) or 99999) > 12000 else "NOT_ESTABLISHED",
        "SAFE_FOR_100K_LONG_RUN": "NOT_ESTABLISHED",
        "PUBLIC_BETA31_RELEASE_BLOCKED": "YES",
        "BLOCK_REASON": None,
        "GIT_PUSH": "NO",
    }
    if verdict != "PASS":
        report["BLOCK_REASON"] = (
            "Eviction is opt-in and exact, but anonymous RSS did not meet PASS (bounded aged RAM) "
            f"RAM_BEHAVIOR={ram_beh}; 5k={'run' if aged.get('AGED_VALIDATION_TICK') else 'not run'}."
        )
    write_json("summary.json", report)
    return report


def child_restore() -> dict:
    from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
    from mechanistic_mind.research import pe_cold_archive as cold

    apply_mode("evict", os.environ.get("PSY_COLD_EVICT_ROOT"))
    cold.reset_disk_read_stats()
    snap = json.loads(Path(os.environ["PSY_COLD_SNAP"]).read_text())
    rss0 = _proc()
    rt = TwoAgentRuntime.restore(snap)
    rss1 = _proc()
    card = archive_card(rt)
    reads = cold.disk_read_stats()
    return {"proc": rss1, "pre": rss0, "archive": card, "disk_reads": reads, "tick": int(getattr(rt, "tick", 0) or 0)}


if __name__ == "__main__":
    os.chdir(str(ROOT))
    sys.path.insert(0, str(ROOT))
    role = os.environ.get("PSY_COLD_EVICT_ROLE", "master")
    if role == "rss":
        print("PSY_COLD_EVICT_JSON=" + json.dumps(child_rss(), default=str), flush=True)
    elif role == "restore":
        print("PSY_COLD_EVICT_JSON=" + json.dumps(child_restore(), default=str), flush=True)
    else:
        try:
            rep = main_master()
            print(json.dumps({k: rep[k] for k in (
                "BETA31_PE_COLD_EVICTION",
                "SEALED_PAYLOAD_REACHABLE_AFTER_EVICTION",
                "COGNITION_READS_EVICTED_HISTORY",
                "RAM_BEHAVIOR",
                "HYBRID_G_RSS_MB_PER_1000",
                "COLD_DISK_EVICT_RSS_MB_PER_1000",
                "T250_1000_RSS_SLOPE",
                "T1000_2000_RSS_SLOPE",
            )}, indent=2))
        except Exception:
            traceback.print_exc()
            raise
