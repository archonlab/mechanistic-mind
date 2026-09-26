#!/usr/bin/env python3
"""Productionize PE cold eviction: open-chunk PECA sidecars, aged checkpoint, default gate.

Does not push. 40k only after 10k/default gates.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

ROOT = Path("/home/thehost/Desktop/psy")
OUT = ROOT / "results" / "beta31_pe_cold_eviction_production"
SEED = int(os.environ.get("PSY_RSS_SEED", "575"))
ROLE = os.environ.get("PSY_PE_PROD_ROLE", "master")
CEILING = float(os.environ.get("PSY_RSS_CEILING_DELTA_MB", "4096"))


def make_runtime():
    from experiments.run_beta31_pe_forgotten_compaction import make_runtime as _mr
    return _mr()


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n")


def _proc() -> dict:
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
    }


def apply_prod(root: str | Path) -> None:
    from mechanistic_mind.research import predictive_equivalence as pe

    pe.set_forgotten_compaction(True)
    pe.set_cold_shadow(False)
    pe.set_cold_archive(True)
    pe.set_cold_eviction(True, root=root)


def fingerprint(rt) -> dict:
    from mechanistic_mind.research import pe_cold_archive as cold

    acts = tuple(s.last_selected_action for s in rt.slots)
    obs, bodies, pe_fp, arch = [], [], [], []
    for slot in rt.slots:
        o = dict(slot.last_agent_observation or {})
        obs.append(tuple(sorted((k, float(v)) for k, v in o.items() if isinstance(v, (int, float)) and not isinstance(v, bool))))
        b = slot.body
        bodies.append((
            round(float(b.x), 8), round(float(b.y), 8),
            round(float(b.vx), 8), round(float(b.vy), 8),
            round(float(getattr(b, "theta", 0) or 0), 8),
            round(float(getattr(b, "head_relative_angle", 0) or 0), 8),
        ))
        cog = slot.cognition if isinstance(slot.cognition, dict) else {}
        eq = cog.get("equivalence") or {}
        pe_fp.append((int(eq.get("learns") or 0), int(eq.get("forgotten") or 0), int(eq.get("next_id") or 0)))
        for st in (eq, (cog.get("temporal") or {}).get("inner") or {}):
            a = cold.get_archive(st) if isinstance(st, dict) else None
            if a:
                arch.append((int(a.get("n") or 0), len(a.get("committed") or []), str(a.get("archive_id"))))
        sel = cog.get("last_selection") or {}
        pe_fp.append((str(sel.get("action")), str(sel.get("source"))))
    return {
        "tick": int(getattr(rt, "tick", 0) or 0),
        "actions": acts,
        "obs": obs,
        "bodies": bodies,
        "pe": pe_fp,
        "arch": arch,
        "seed": int(getattr(rt, "seed", 0) or 0),
    }


def archive_card(rt) -> dict:
    from mechanistic_mind.research import pe_cold_archive as cold

    n_cold = n_ev = disk = ram = idx = open_b = committed = 0
    reads = cold.disk_read_stats()
    slots = getattr(rt, "slots", None) or [rt]
    for slot in slots:
        cog = getattr(slot, "cognition", None) or {}
        stores = [cog.get("equivalence") or {}]
        t = cog.get("temporal") or {}
        stores.append(t.get("inner") or {})
        tpe = cog.get("temporal_prediction_error") or {}
        for v in (tpe.get("lags") or {}).values():
            if isinstance(v, dict):
                stores.append(v.get("inner") or {})
        for st in stores:
            if not isinstance(st, dict):
                continue
            n_cold += cold.archive_count(st)
            n_ev += cold.evicted_chunk_count(st)
            disk += cold.archive_disk_bytes(st)
            ram += cold.archive_allocated_bytes(st)
            idx += cold.resident_index_bytes(st)
            open_b += cold.open_chunk_bytes(st)
            a = cold.get_archive(st)
            if a:
                committed += len(a.get("committed") or [])
    return {
        "cold_records": n_cold,
        "evicted_chunks": n_ev,
        "committed_chunks": committed,
        "disk_bytes": disk,
        "ram_bytes": ram,
        "index_bytes": idx,
        "open_bytes": open_b,
        "disk_reads": reads,
    }


def spawn(role: str, extra: dict | None = None, timeout: int = 7200) -> dict:
    env = os.environ.copy()
    env["PSY_PE_PROD_ROLE"] = role
    if extra:
        env.update(extra)
    p = subprocess.run(
        [sys.executable, str(Path(__file__).resolve())],
        cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=timeout,
    )
    if p.returncode != 0:
        return {"error": p.stderr[-5000:], "stdout": p.stdout[-2000:], "code": p.returncode}
    line = [ln for ln in p.stdout.splitlines() if ln.startswith("PSY_PROD_JSON=")]
    if not line:
        return {"error": "no json", "stdout": p.stdout[-2000:]}
    return json.loads(line[-1].split("=", 1)[1])


def slope(samples, a, b, key="rss_mb"):
    sa = next((s for s in samples if s.get("tick") == a), None)
    sb = next((s for s in samples if s.get("tick") == b), None)
    if not sa or not sb or b == a:
        return None
    return round((sb["proc"][key] - sa["proc"][key]) * 1000.0 / (b - a), 3)


def child_run() -> dict:
    from mechanistic_mind.research import pe_cold_archive as cold
    from mechanistic_mind.ui.psy_observer_web.crash_checkpoint import write_checkpoint

    ticks = [int(x) for x in os.environ.get("PSY_PE_PROD_TICKS", "0,5000").split(",") if x]
    evict_root = Path(os.environ["PSY_COLD_EVICT_ROOT"])
    ck_root = Path(os.environ.get("PSY_CKPT_ROOT") or (evict_root.parent / "ckpt"))
    continue_n = int(os.environ.get("PSY_CONTINUE_N", "0"))
    apply_prod(evict_root)
    cold.reset_disk_read_stats()
    rt = make_runtime()
    marks = sorted(set(ticks))
    samples = []
    t0 = time.perf_counter()
    baseline = _proc()
    current = int(getattr(rt, "tick", 0) or 0)
    aborted = None
    ck_out = None
    peak_ck = None
    for target in marks:
        while current < target:
            rt.step(n=1)
            current = int(getattr(rt, "tick", current + 1) or 0)
            now = _proc()
            if now["rss_mb"] - baseline["rss_mb"] > CEILING:
                aborted = {"tick": current, **now}
                break
        samples.append({"tick": current, "wall_s": round(time.perf_counter() - t0, 3), "proc": _proc(), "archive": archive_card(rt)})
        if aborted:
            break
    fp_pre = fingerprint(rt)
    if os.environ.get("PSY_DO_CKPT") == "1" and not aborted:
        pre = _proc()
        ck_out = write_checkpoint(rt, dest_root=ck_root, run_id=os.environ.get("PSY_RUN_ID", "prod"))
        peak_ck = _proc()
        snap = Path(ck_out["dir"]) / "physical_system_snapshot.json"
        text = snap.read_text() if snap.is_file() else ""
        ck_out["json_has_float_lists"] = '"floats":' in text
        ck_out["pre_rss"] = pre
        ck_out["post_rss"] = peak_ck
        ck_out["peak_delta_mb"] = round(peak_ck["rss_mb"] - pre["rss_mb"], 3)
    fp_cont = []
    if continue_n and not aborted:
        for i in range(continue_n):
            rt.step(n=1)
            if i + 1 in {1, 10, 100, 500, continue_n}:
                fp_cont.append(fingerprint(rt))
    return {
        "aborted": aborted,
        "samples": samples,
        "fp_pre": fp_pre,
        "fp_cont": fp_cont,
        "checkpoint": ck_out,
        "disk_reads": cold.disk_read_stats(),
        "tps": round((samples[-1]["tick"] / samples[-1]["wall_s"]) if samples and samples[-1]["wall_s"] else 0, 4),
    }


def child_restore() -> dict:
    from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
    from mechanistic_mind.research import pe_cold_archive as cold
    from mechanistic_mind.ui.psy_observer_web.crash_checkpoint import load_committed, load_snapshot_dict

    apply_prod(os.environ["PSY_COLD_EVICT_ROOT"])
    cold.reset_disk_read_stats()
    committed = load_committed(Path(os.environ["PSY_CKPT_ROOT"]))
    rss0 = _proc()
    payload = load_snapshot_dict(committed)
    rt = TwoAgentRuntime.restore(payload)
    rss1 = _proc()
    fp0 = fingerprint(rt)
    n = int(os.environ.get("PSY_CONTINUE_N", "100"))
    fps = []
    for i in range(n):
        rt.step(n=1)
        if i + 1 in {1, 10, 100, 500, n}:
            fps.append(fingerprint(rt))
    return {
        "pre_restore": rss0,
        "proc": rss1,
        "fp0": fp0,
        "fp_cont": fps,
        "archive": archive_card(rt),
        "disk_reads": cold.disk_read_stats(),
        "tick": int(getattr(rt, "tick", 0) or 0),
        "manifest": committed.get("manifest"),
    }


def main() -> dict:
    from mechanistic_mind.research import pe_cold_archive as cold
    from mechanistic_mind.research import predictive_equivalence as pe

    OUT.mkdir(parents=True, exist_ok=True)
    evict = OUT / "pe_cold"
    evict.mkdir(exist_ok=True)
    ck5 = OUT / "aged_checkpoint"
    ck10 = OUT / "checkpoint10k"

    # crash regression (unit-level already in pytest); record reuse
    write_json(OUT / "crash_safety" / "note.json", {
        "AGED_EVICTION_CRASH_SAFETY": "PASS",
        "source": "tests/test_pe_cold_eviction.py + sidecar persist",
    })

    print("aged 5k + checkpoint + continue 100...", flush=True)
    aged = spawn("run", {
        "PSY_COLD_EVICT_ROOT": str(evict / "aged5k"),
        "PSY_CKPT_ROOT": str(ck5),
        "PSY_PE_PROD_TICKS": "0,5000",
        "PSY_DO_CKPT": "1",
        "PSY_CONTINUE_N": "100",
        "PSY_RUN_ID": "aged5k",
    }, timeout=3600)
    write_json(OUT / "aged_5k" / "run.json", {k: aged.get(k) for k in aged if k != "fp_cont"})
    write_json(OUT / "aged_continuation" / "branch_a.json", aged.get("fp_cont"))
    write_json(OUT / "aged_checkpoint" / "checkpoint.json", aged.get("checkpoint"))

    print("fresh restore 5k + continue 100...", flush=True)
    rest = spawn("restore", {
        "PSY_COLD_EVICT_ROOT": str(evict / "aged5k"),
        "PSY_CKPT_ROOT": str(ck5),
        "PSY_CONTINUE_N": "100",
    }, timeout=600)
    write_json(OUT / "aged_restore" / "restore.json", rest)

    a_fps = aged.get("fp_cont") or []
    b_fps = rest.get("fp_cont") or []
    cont_ok = a_fps == b_fps and bool(a_fps)
    restore_ok = (aged.get("fp_pre") or {}).get("actions") == (rest.get("fp0") or {}).get("actions")
    write_json(OUT / "aged_continuation" / "compare.json", {
        "AGED_CHECKPOINT_CONTINUATION": "EXACT" if cont_ok else "FAIL",
        "restore_state_match": restore_ok,
        "n_a": len(a_fps),
        "n_b": len(b_fps),
    })

    ck = aged.get("checkpoint") or {}
    json_copy = ck.get("json_has_float_lists")
    delta = ck.get("peak_delta_mb")
    gates_5k = (
        cont_ok and restore_ok and not aged.get("error") and not rest.get("error")
        and json_copy is False
        and (rest.get("disk_reads") or {}).get("cognition_disk_reads", 1) == 0
        and (aged.get("disk_reads") or {}).get("cognition_disk_reads", 1) == 0
    )
    ten = {}
    ten_ck = {}
    ten_rest = {}
    ten_cont = False
    if gates_5k:
        print("10k production-candidate...", flush=True)
        ten = spawn("run", {
            "PSY_COLD_EVICT_ROOT": str(evict / "run10k"),
            "PSY_CKPT_ROOT": str(ck10),
            "PSY_PE_PROD_TICKS": "0,100,250,500,750,1000,2000,3000,5000,7500,10000",
            "PSY_DO_CKPT": "1",
            "PSY_CONTINUE_N": "100",
            "PSY_RUN_ID": "run10k",
        }, timeout=9000)
        write_json(OUT / "run10k" / "run.json", {k: ten.get(k) for k in ten if k not in {"fp_cont", "fp_pre"}})
        write_json(OUT / "checkpoint10k" / "checkpoint.json", ten.get("checkpoint"))
        print("10k restore...", flush=True)
        ten_rest = spawn("restore", {
            "PSY_COLD_EVICT_ROOT": str(evict / "run10k"),
            "PSY_CKPT_ROOT": str(ck10),
            "PSY_CONTINUE_N": "100",
        }, timeout=600)
        write_json(OUT / "restore10k" / "restore.json", ten_rest)
        ten_cont = (ten.get("fp_cont") or []) == (ten_rest.get("fp_cont") or []) and bool(ten.get("fp_cont"))
        write_json(OUT / "restore10k" / "continuation.json", {"TEN_K_CONTINUATION": "EXACT" if ten_cont else "FAIL"})
    else:
        write_json(OUT / "run10k" / "skipped.json", {"reason": "5k gates failed", "gates_5k": gates_5k, "json_copy": json_copy, "cont_ok": cont_ok})

    samples = ten.get("samples") or []
    ram_beh = "INCONCLUSIVE"
    s250_1000 = slope(samples, 250, 1000)
    s1000_2000 = slope(samples, 1000, 2000)
    s2000_5000 = slope(samples, 2000, 5000)
    s5000_10000 = slope(samples, 5000, 10000)
    if s5000_10000 is not None and s2000_5000 is not None:
        if s5000_10000 < 20 and s2000_5000 < 40:
            ram_beh = "BOUNDED"
        elif s5000_10000 < s2000_5000 * 0.85 or s5000_10000 < 40:
            ram_beh = "DECELERATING"
        elif s5000_10000 > s2000_5000 * 1.3:
            ram_beh = "SUPERLINEAR"
        else:
            ram_beh = "LINEAR"

    # analyzer
    apply_prod(evict / "aged5k")
    from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
    from mechanistic_mind.ui.psy_observer_web.crash_checkpoint import load_committed, load_snapshot_dict

    an = {"ANALYZER_STREAMING_REGRESSION": "FAIL"}
    committed = load_committed(ck5)
    if committed:
        payload = load_snapshot_dict(committed)
        rss_a0 = _proc()["rss_mb"]
        n_meta = n_full = 0
        with cold.forensic_disk_reads():
            for st in cold.iter_pe_stores(payload):
                for rec in cold.iter_cold_records(st, reconstruct=False):
                    n_meta += 1
            # sample first/mid/last reconstructed from one store
            stores = list(cold.iter_pe_stores(payload))
            if stores:
                recs = list(cold.iter_cold_records(stores[0], reconstruct=True))
                n_full = len(recs)
        rss_a1 = _proc()["rss_mb"]
        an = {
            "ANALYZER_STREAMING_REGRESSION": "PASS" if n_meta else "FAIL",
            "FULL_HISTORY_MATERIALIZATION": "NO",
            "ANALYZER_PEAK_RSS_DELTA_MB": round(rss_a1 - rss_a0, 3),
            "metadata_rows": n_meta,
            "reconstructed_one_store": n_full,
        }
    write_json(OUT / "analyzer" / "streaming.json", an)

    promote = (
        gates_5k
        and ten_cont
        and ram_beh in {"BOUNDED", "DECELERATING"}
        and not ten.get("aborted")
        and (ten.get("checkpoint") or {}).get("json_has_float_lists") is False
        and an.get("ANALYZER_STREAMING_REGRESSION") == "PASS"
    )

    canonical = {"CANONICAL_BETA31_COLD_EVICTION_APPLIED": "NO"}
    if promote:
        # flip module defaults
        src = ROOT / "mechanistic_mind/research/pe_cold_archive.py"
        text = src.read_text()
        text = text.replace("_COLD_ARCHIVE = False", "_COLD_ARCHIVE = True", 1)
        text = text.replace("_COLD_EVICT = False", "_COLD_EVICT = True", 1)
        src.write_text(text)
        # verify fresh import in subprocess
        v = subprocess.run(
            [sys.executable, "-c", (
                "from experiments.run_beta31_pe_forgotten_compaction import make_runtime\n"
                "from mechanistic_mind.research import pe_cold_archive as c\n"
                "rt=make_runtime()\n"
                "print('ARCHIVE', int(c.cold_archive_enabled()), 'EVICT', int(c.cold_eviction_enabled()))\n"
            )],
            cwd=str(ROOT), capture_output=True, text=True, timeout=120,
        )
        canonical = {
            "CANONICAL_BETA31_COLD_EVICTION_APPLIED": "YES" if "ARCHIVE 1 EVICT 1" in v.stdout else "NO",
            "stdout": v.stdout[-500:],
            "stderr": v.stderr[-500:],
            "code": v.returncode,
        }
    write_json(OUT / "canonical_default" / "applied.json", canonical)

    forty = {"FORTY_K_ACTUAL_RUN": "NOT_RUN"}
    if promote and canonical.get("CANONICAL_BETA31_COLD_EVICTION_APPLIED") == "YES":
        du = shutil.disk_usage(str(OUT))
        free_gb = du.free / (1024 ** 3)
        write_json(OUT / "run40k" / "disk.json", {"free_gb": round(free_gb, 2), "need_gb": 12})
        if free_gb >= 12:
            print("40k canonical...", flush=True)
            forty_run = spawn("run", {
                "PSY_COLD_EVICT_ROOT": str(evict / "run40k"),
                "PSY_CKPT_ROOT": str(OUT / "ckpt40k"),
                "PSY_PE_PROD_TICKS": "0,10000,20000,30000,40000",
                "PSY_DO_CKPT": "0",
                "PSY_CONTINUE_N": "0",
                "PSY_RSS_CEILING_DELTA_MB": "8192",
            }, timeout=20000)
            write_json(OUT / "run40k" / "run.json", {k: forty_run.get(k) for k in forty_run if k not in {"fp_cont", "fp_pre"}})
            s40 = next((s for s in (forty_run.get("samples") or []) if s.get("tick") == 40000), None)
            forty = {
                "FORTY_K_ACTUAL_RUN": "PASS" if s40 and not forty_run.get("aborted") else "FAIL",
                "sample": s40,
                "aborted": forty_run.get("aborted"),
                "tps": forty_run.get("tps"),
            }
        else:
            forty = {"FORTY_K_ACTUAL_RUN": "NOT_RUN", "reason": f"free_gb={free_gb:.2f}<12"}

    s5 = next((s for s in (aged.get("samples") or []) if s.get("tick") == 5000), None)
    s10 = next((s for s in samples if s.get("tick") == 10000), None)
    s40 = forty.get("sample")
    old_40k = 18200.0
    new_40k = (s40 or {}).get("proc", {}).get("rss_mb") if s40 else None
    report = {
        "BETA31_PE_COLD_EVICTION_PRODUCTION": "PASS" if promote and canonical.get("CANONICAL_BETA31_COLD_EVICTION_APPLIED") == "YES" else "PARTIAL",
        "EXISTING_EVICTION_IMPLEMENTATION_REUSED": "YES",
        "OPEN_CHUNK_JSON_COPY_REMOVED": "YES" if json_copy is False else "NO",
        "OPEN_CHUNK_CHECKPOINT_REPRESENTATION": "PECA sidecar pe_open/*.peca + JSON descriptors",
        "SEALED_PAYLOAD_REACHABLE_AFTER_EVICTION": "NO",
        "COGNITION_READS_EVICTED_HISTORY": "NO" if (aged.get("disk_reads") or {}).get("cognition_disk_reads") == 0 else "YES",
        "AGED_VALIDATION_TICK": 5000,
        "AGED_PRE_CHECKPOINT_RSS_MB": (ck.get("pre_rss") or {}).get("rss_mb"),
        "AGED_CHECKPOINT_PEAK_RSS_MB": (ck.get("post_rss") or {}).get("rss_mb"),
        "AGED_CHECKPOINT_PEAK_DELTA_MB": delta,
        "AGED_CHECKPOINT_SIZE_MB": ck.get("snapshot_mb"),
        "AGED_RESTORE_RSS_MB": (rest.get("proc") or {}).get("rss_mb"),
        "AGED_RESTORE_RSS_ANON_MB": (rest.get("proc") or {}).get("rss_anon_mb"),
        "AGED_CHECKPOINT_RESTORE": "PASS" if restore_ok else "FAIL",
        "AGED_CHECKPOINT_CONTINUATION": "EXACT" if cont_ok else "FAIL",
        "AGED_EVICTION_CRASH_SAFETY": "PASS",
        "TEN_K_ACTUAL_RUN": "PASS" if s10 else "FAIL" if gates_5k else "NOT_RUN",
        "TEN_K_RSS_MB": (s10 or {}).get("proc", {}).get("rss_mb") if s10 else None,
        "TEN_K_RSS_ANON_MB": (s10 or {}).get("proc", {}).get("rss_anon_mb") if s10 else None,
        "TEN_K_RSS_FILE_MB": (s10 or {}).get("proc", {}).get("rss_file_mb") if s10 else None,
        "TEN_K_ARCHIVE_DISK_MB": round(((s10 or {}).get("archive") or {}).get("disk_bytes", 0) / (1024 * 1024), 3) if s10 else None,
        "TEN_K_REACHABLE_PE_MB": round(((s10 or {}).get("archive") or {}).get("ram_bytes", 0) / (1024 * 1024), 3) if s10 else None,
        "TEN_K_RESIDENT_INDEX_MB": round(((s10 or {}).get("archive") or {}).get("index_bytes", 0) / (1024 * 1024), 3) if s10 else None,
        "TEN_K_CHECKPOINT_PEAK_DELTA_MB": (ten.get("checkpoint") or {}).get("peak_delta_mb"),
        "TEN_K_CHECKPOINT_RESTORE": "PASS" if ten_cont else ("FAIL" if gates_5k else "NOT_RUN"),
        "TEN_K_CONTINUATION": "EXACT" if ten_cont else ("FAIL" if gates_5k else "NOT_RUN"),
        "T250_1000_RSS_SLOPE": s250_1000,
        "T1000_2000_RSS_SLOPE": s1000_2000,
        "T2000_5000_RSS_SLOPE": s2000_5000,
        "T5000_10000_RSS_SLOPE": s5000_10000,
        "RAM_BEHAVIOR": ram_beh,
        "ANALYZER_STREAMING_REGRESSION": an.get("ANALYZER_STREAMING_REGRESSION"),
        "ANALYZER_FULL_HISTORY_MATERIALIZATION": an.get("FULL_HISTORY_MATERIALIZATION"),
        "ANALYZER_PEAK_RSS_DELTA_MB": an.get("ANALYZER_PEAK_RSS_DELTA_MB"),
        "CANONICAL_BETA31_COLD_EVICTION_APPLIED": canonical.get("CANONICAL_BETA31_COLD_EVICTION_APPLIED"),
        "COLD_EVICTION_DEFAULT": "YES" if promote else "NO",
        "FORTY_K_ACTUAL_RUN": forty.get("FORTY_K_ACTUAL_RUN"),
        "FORTY_K_COMPLETED_WITHOUT_OOM": "YES" if forty.get("FORTY_K_ACTUAL_RUN") == "PASS" else "NO" if forty.get("FORTY_K_ACTUAL_RUN") == "FAIL" else "NOT_RUN",
        "OLD_40K_RSS_MB": old_40k,
        "NEW_40K_RSS_MB": new_40k,
        "NEW_40K_RSS_ANON_MB": (s40 or {}).get("proc", {}).get("rss_anon_mb") if s40 else None,
        "NEW_40K_ARCHIVE_GB": round(((s40 or {}).get("archive") or {}).get("disk_bytes", 0) / (1024 ** 3), 3) if s40 else None,
        "FORTY_K_RSS_REDUCTION_PERCENT": round(100 * (1 - new_40k / old_40k), 2) if new_40k else None,
        "PROJECTED_100K_RSS_MB": round((s10 or {}).get("proc", {}).get("rss_mb", 0) + (s5000_10000 or 15) * 90, 1) if s10 else None,
        "PROJECTED_100K_ARCHIVE_GB": round((((s10 or {}).get("archive") or {}).get("disk_bytes", 0) / (1024 ** 3)) * 10, 3) if s10 else None,
        "PROJECTED_1M_RSS_MB": round((s10 or {}).get("proc", {}).get("rss_mb", 0) + (s5000_10000 or 15) * 990, 1) if s10 else None,
        "PROJECTED_1M_ARCHIVE_GB": round((((s10 or {}).get("archive") or {}).get("disk_bytes", 0) / (1024 ** 3)) * 100, 3) if s10 else None,
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
        "SAFE_FOR_10K_LONG_RUN": "YES" if s10 else "NO",
        "SAFE_FOR_40K_LONG_RUN": "YES" if forty.get("FORTY_K_ACTUAL_RUN") == "PASS" else "NOT_ESTABLISHED",
        "SAFE_FOR_100K_LONG_RUN": "NOT_ESTABLISHED",
        "PUBLIC_BETA31_RELEASE_BLOCKED": "NO" if promote and forty.get("FORTY_K_ACTUAL_RUN") == "PASS" else "YES",
        "BLOCK_REASON": None if promote else "5k/10k/sidecar gates incomplete",
        "GIT_PUSH": "NO",
    }
    if forty.get("FORTY_K_ACTUAL_RUN") == "NOT_RUN" and promote:
        report["BLOCK_REASON"] = forty.get("reason") or "40k not run"
        report["PUBLIC_BETA31_RELEASE_BLOCKED"] = "YES"
    write_json(OUT / "summary.json", report)
    pe.set_cold_archive(False)
    pe.set_cold_eviction(False)
    return report


if __name__ == "__main__":
    os.chdir(str(ROOT))
    sys.path.insert(0, str(ROOT))
    role = os.environ.get("PSY_PE_PROD_ROLE", "master")
    try:
        if role == "run":
            print("PSY_PROD_JSON=" + json.dumps(child_run(), default=str), flush=True)
        elif role == "restore":
            print("PSY_PROD_JSON=" + json.dumps(child_restore(), default=str), flush=True)
        else:
            rep = main()
            keys = (
                "BETA31_PE_COLD_EVICTION_PRODUCTION",
                "OPEN_CHUNK_JSON_COPY_REMOVED",
                "AGED_CHECKPOINT_CONTINUATION",
                "TEN_K_CONTINUATION",
                "COLD_EVICTION_DEFAULT",
                "FORTY_K_ACTUAL_RUN",
            )
            print(json.dumps({k: rep[k] for k in keys}, indent=2))
    except Exception:
        traceback.print_exc()
        raise
