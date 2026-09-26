#!/usr/bin/env python3
"""Beta 3.1 PE forgotten-history compaction: memory, equivalence, projection.

Does not start an unattended 40k run. Does not mutate e02e833b.
"""
from __future__ import annotations

import gc
import json
import os
import resource
import subprocess
import sys
import tempfile
import time
import traceback
from collections import deque
from copy import deepcopy
from io import StringIO
from pathlib import Path

ROOT = Path("/home/thehost/Desktop/psy")
OUT = ROOT / "results" / "beta31_pe_forgotten_compaction"
LIVE = ROOT / "results/psychology_observer/psy_observer_web/.live-psyweb-20260923T180243.860310Z-e02e833b"
SEED = int(os.environ.get("PSY_RSS_SEED", "575"))
TICKS = [int(x) for x in os.environ.get("PSY_PE_COMPACT_TICKS", "0,250,500,1000").split(",") if x]
CEILING_DELTA_MB = float(os.environ.get("PSY_RSS_CEILING_DELTA_MB", "2048"))
ROLE = os.environ.get("PSY_PE_COMPACT_ROLE", "master")


def _proc() -> dict:
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
        "ru_maxrss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0, 3),
    }


def _sizeof(obj, seen: set[int] | None = None, budget: int = 2_000_000) -> int:
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
    elif isinstance(obj, (list, tuple, set, deque)):
        for x in obj:
            n += _sizeof(x, seen, budget)
    elif isinstance(obj, (bytes, bytearray, str)):
        return n
    else:
        try:
            from array import array as _array

            if isinstance(obj, _array):
                return n
        except Exception:
            pass
    return n


def failed_run_mechanisms() -> dict[str, bool]:
    meta_path = LIVE / "scientific_meta.json"
    if not meta_path.is_file():
        return {"predictive_equivalence": True, "sensorimotor_consequence_model": True}
    meta = json.loads(meta_path.read_text())
    out: dict[str, bool] = {}
    for row in (meta.get("runtime_mechanism_manifest") or {}).get("mechanisms") or []:
        if row.get("configured"):
            out[str(row["id"])] = True
    return out


def make_runtime():
    from mechanistic_mind.physical_system.ecology_presets import make_ecology_config
    from mechanistic_mind.physical_system.mechanism_configuration import (
        apply_resolved_to_runtime,
        resolve_mechanism_config,
        stamp_config_mechanisms,
    )
    from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime

    cfg = make_ecology_config("STRUCTURED_WORLD_EXPERIMENTAL")
    mech = failed_run_mechanisms()
    resolved = resolve_mechanism_config(mech, vision_radius=3, apply_fresh_defaults=True)
    stamp_config_mechanisms(cfg, resolved)
    rt = TwoAgentRuntime(seed=SEED, config=cfg, signal_enabled=True)
    apply_resolved_to_runtime(rt, resolved)
    for fn, arg in (
        ("set_vision_radius", 3),
        ("set_visual_surface_discrimination", "RICH"),
        ("set_optical_mapping", "CORRELATED"),
        ("set_spatial_vision", "OCCLUSION"),
    ):
        m = getattr(rt, fn, None)
        if callable(m):
            m(arg)
        else:
            for slot in rt.slots:
                sm = getattr(slot, fn, None)
                if callable(sm):
                    sm(arg)
    setter = getattr(rt, "set_psc_motor_resolution", None)
    if callable(setter):
        setter("OBSERVED_COMPOSITE")
    return rt


def pe_card(runtime) -> dict:
    from mechanistic_mind.research import predictive_equivalence as pe

    agents = []
    for i, slot in enumerate(runtime.slots):
        store = (slot.cognition or {}).get("equivalence") or {}
        classes = store.get("classes") or {}
        n_for = 0
        n_act = 0
        packed = 0
        mem_bytes = 0
        shell_bytes = 0
        frag_bytes = 0
        mean_bytes = 0
        last_bytes = 0
        member_shell = 0
        for cls in classes.values():
            if not isinstance(cls, dict):
                continue
            if cls.get("status") == "FORGOTTEN":
                n_for += 1
                if pe.is_forgotten_packed(cls):
                    packed += 1
                shell_bytes += _sizeof({k: v for k, v in cls.items() if k != "members"})
                members = cls.get("members") or {}
                member_shell += _sizeof(members)
                for mem in members.values() if isinstance(members, dict) else []:
                    if not isinstance(mem, dict):
                        continue
                    member_shell += _sizeof({k: v for k, v in mem.items() if k not in ("fragment", "mean_c", "last_abs")})
                    frag_bytes += _sizeof(mem.get("fragment"))
                    mean_bytes += _sizeof(mem.get("mean_c"))
                    last_bytes += _sizeof(mem.get("last_abs"))
            else:
                n_act += 1
        mem_bytes = shell_bytes + member_shell + frag_bytes + mean_bytes + last_bytes
        agents.append({
            "slot": i,
            "pe_classes": len(classes),
            "pe_active": n_act,
            "pe_forgotten": n_for,
            "pe_forgotten_packed": packed,
            "forgotten_reachable_bytes": mem_bytes,
            "bytes_class_shell": shell_bytes,
            "bytes_member_shell": member_shell,
            "bytes_fragment": frag_bytes,
            "bytes_mean_c": mean_bytes,
            "bytes_last_abs": last_bytes,
            "bytes_per_forgotten": round(mem_bytes / n_for, 1) if n_for else None,
            "store_sizeof_mb": round(_sizeof(store) / (1024 * 1024), 3),
        })
    return {"agents": agents}


def run_rss_child() -> dict:
    from mechanistic_mind.research import predictive_equivalence as pe

    compact = os.environ.get("PSY_PE_FORGOTTEN_COMPACT", "1") != "0"
    pe.set_forgotten_compaction(compact)
    rt = make_runtime()
    t_marks = sorted({int(x) for x in TICKS if int(x) >= 0})
    if 0 not in t_marks:
        t_marks = [0] + t_marks
    samples = []
    t0 = time.perf_counter()
    baseline = _proc()
    current = int(getattr(rt, "tick", 0) or 0)
    aborted = None
    for target in t_marks:
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
            "pe": pe_card(rt),
        })
        if aborted:
            break
    actions = []
    # short continuation fingerprint
    for _ in range(8):
        rt.step(n=1)
        actions.append(tuple(s.last_selected_action for s in rt.slots))
    return {
        "compact": compact,
        "seed": SEED,
        "aborted": aborted,
        "samples": samples,
        "continuation_actions": actions,
        "tps": round((samples[-1]["tick"] / samples[-1]["wall_s"]) if samples and samples[-1]["wall_s"] else 0.0, 4),
    }


def unit_gates() -> dict:
    from mechanistic_mind.research import predictive_equivalence as pe
    from mechanistic_mind.ui.psy_observer_web.run_finalize import dump_persist

    pe.set_forgotten_compaction(False)
    s = pe.empty_store()
    s["enabled"] = True

    def frag(n, w=24):
        return {f"ch{i}": float(n) + 0.001 * i for i in range(w)}

    for i in range(pe.MAX_CLASSES + 40):
        pe.learn(
            s,
            fragment=frag(float(i)),
            action=f"A{i % 4}",
            consequent={"y": float(i), "q": float(i) % 5},
            tick=i,
            raw_id=f"u{i}",
        )
    forgotten = [c for c in s["classes"].values() if c.get("status") == "FORGOTTEN"]
    mismatches = []
    compared = 0
    bytes_full = 0
    bytes_pack = 0
    for cls in forgotten:
        original = deepcopy(cls)
        bytes_full += _sizeof(original)
        packed = pe.compact_forgotten_class(deepcopy(cls))
        bytes_pack += _sizeof(packed)
        expanded = pe.expand_forgotten_class(packed)
        compared += 1
        for sig, om in original["members"].items():
            em = expanded["members"][sig]
            for fld in ("fragment", "mean_c", "last_abs"):
                if om.get(fld) != em.get(fld):
                    mismatches.append({"class_id": original.get("id"), "sig": sig, "field": fld})
                    break
        q = frag(3.0)
        before = pe.retrieve(s, q, "A0", count=False)
    for cls in forgotten:
        pe.compact_forgotten_class(cls)
    after = pe.retrieve(s, frag(3.0), "A0", count=False)
    buf = StringIO()
    dump_persist({"eq": s}, buf)
    loaded = json.loads(buf.getvalue())
    pe.set_forgotten_compaction(True)
    pe.clear_derived_caches(loaded["eq"])
    packed_n = sum(
        1
        for c in (loaded["eq"].get("classes") or {}).values()
        if isinstance(c, dict) and c.get("status") == "FORGOTTEN" and pe.is_forgotten_packed(c)
    )
    n = max(1, len(forgotten))
    return {
        "forgotten_n": len(forgotten),
        "compared": compared,
        "mismatches": mismatches[:8],
        "shadow_read_equivalence_pct": 100.0 if not mismatches and before == after else 0.0,
        "retrieve_after_pack_equal": before == after,
        "bytes_per_forgotten_full": round(bytes_full / n, 1),
        "bytes_per_forgotten_compact": round(bytes_pack / n, 1),
        "legacy_json_restore_packed": packed_n,
        "FORGOTTEN_COMPACTION_LOSSLESS": "YES" if not mismatches else "NO",
    }


def slope_mb_per_1000(samples: list[dict]) -> float | None:
    pts = [(s["tick"], s["proc"]["rss_mb"]) for s in samples if s.get("tick")]
    if len(pts) < 2:
        return None
    (t0, r0), (t1, r1) = pts[0], pts[-1]
    dt = t1 - t0
    if dt <= 0:
        return None
    return round((r1 - r0) * 1000.0 / dt, 3)


def project(slope, base_rss, ticks):
    if slope is None:
        return None
    return round(base_rss + slope * (ticks / 1000.0), 1)


def write_json(name: str, payload) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def launch_child(compact: bool) -> dict:
    dest = OUT / ("rss_full.json" if not compact else "rss_compact.json")
    env = os.environ.copy()
    env["PSY_PE_COMPACT_ROLE"] = "rss_child"
    env["PSY_PE_FORGOTTEN_COMPACT"] = "1" if compact else "0"
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    dest.unlink(missing_ok=True)
    proc = subprocess.run(
        [sys.executable, str(Path(__file__).resolve())],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=900,
    )
    if proc.returncode != 0:
        return {
            "ok": False,
            "returncode": proc.returncode,
            "stderr": (proc.stderr or "")[-4000:],
            "stdout": (proc.stdout or "")[-2000:],
        }
    if dest.is_file():
        return json.loads(dest.read_text())
    try:
        return json.loads(proc.stdout)
    except Exception:
        return {"ok": False, "stdout": (proc.stdout or "")[-2000:], "stderr": (proc.stderr or "")[-2000:]}


def master() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ROOT))
    os.chdir(str(ROOT))
    gates = unit_gates()
    write_json("roundtrip_equivalence.json", gates)

    full = launch_child(False)
    compact = launch_child(True)
    write_json("rss_full.json", full)
    write_json("rss_compact.json", compact)

    fs = slope_mb_per_1000(full.get("samples") or []) if full.get("samples") else None
    cs = slope_mb_per_1000(compact.get("samples") or []) if compact.get("samples") else None
    f_last = (full.get("samples") or [{}])[-1]
    c_last = (compact.get("samples") or [{}])[-1]
    f_pe = ((f_last.get("pe") or {}).get("agents") or [{}])[0]
    c_pe = ((c_last.get("pe") or {}).get("agents") or [{}])[0]
    f0 = (full.get("samples") or [{}])[0].get("proc", {}).get("rss_mb")
    c0 = (compact.get("samples") or [{}])[0].get("proc", {}).get("rss_mb")

    reduction = None
    if fs and cs and fs:
        reduction = round(100.0 * (1.0 - cs / fs), 2) if fs else None

    projection = {
        "full_mb_per_1000": fs,
        "compact_mb_per_1000": cs,
        "full_40k": project(fs, f0 or 0, 40_000),
        "compact_40k": project(cs, c0 or 0, 40_000),
        "full_100k": project(fs, f0 or 0, 100_000),
        "compact_100k": project(cs, c0 or 0, 100_000),
        "caveat": "Linear extrapolation from measured window only; not a 40k execution.",
    }
    write_json("memory_benchmark.json", {
        "seed": SEED,
        "ticks": TICKS,
        "full": full,
        "compact": compact,
        "slope": projection,
        "rss_reduction_percent_slope": reduction,
    })
    write_json("long_run_projection.json", projection)
    write_json("forgotten_memory_decomposition.json", {
        "full_last": f_pe,
        "compact_last": c_pe,
        "unit_bytes_per_forgotten_full": gates.get("bytes_per_forgotten_full"),
        "unit_bytes_per_forgotten_compact": gates.get("bytes_per_forgotten_compact"),
    })

    # Aged checkpoint on compact child path if last tick >= 500
    aged = {"AGED_CHECKPOINT_RESTORE": "NOT_RUN"}
    last_tick = int(c_last.get("tick") or 0)
    if last_tick >= 250 and compact.get("ok", True) and compact.get("samples"):
        try:
            from mechanistic_mind.research import predictive_equivalence as pe
            from mechanistic_mind.physical_system import PhysicalSystemRuntime
            from mechanistic_mind.ui.psy_observer_web.run_finalize import dump_persist

            pe.set_forgotten_compaction(True)
            rt = make_runtime()
            n = min(500, last_tick)
            t_ck = time.perf_counter()
            rss0 = _proc()["rss_mb"]
            for _ in range(n):
                rt.step(n=1)
            snap = rt.snapshot()
            ckpt = OUT / "aged_checkpoint_payload.json"
            with ckpt.open("w", encoding="utf-8") as fh:
                dump_persist(snap, fh, compact=True)
            write_s = time.perf_counter() - t_ck
            rss1 = _proc()["rss_mb"]
            t_r = time.perf_counter()
            payload = json.loads(ckpt.read_text(encoding="utf-8"))
            from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
            rest = TwoAgentRuntime.restore(payload)
            restore_s = time.perf_counter() - t_r
            rt.step(n=1)
            rest.step(n=1)
            a1 = tuple(s.last_selected_action for s in rt.slots) if hasattr(rt, "slots") else (rt.last_selected_action,)
            b1 = tuple(s.last_selected_action for s in rest.slots) if hasattr(rest, "slots") else (rest.last_selected_action,)
            aged = {
                "tick": n,
                "checkpoint_json_bytes": ckpt.stat().st_size,
                "write_s": round(write_s, 3),
                "restore_s": round(restore_s, 3),
                "peak_rss_delta_mb": round(rss1 - rss0, 3),
                "continuation_equal": a1 == b1,
                "AGED_CHECKPOINT_RESTORE": "PASS" if a1 == b1 else "FAIL",
            }
            try:
                ckpt.unlink()
            except OSError:
                pass
        except Exception as exc:
            aged = {
                "AGED_CHECKPOINT_RESTORE": "FAIL",
                "error": f"{type(exc).__name__}: {exc}",
                "trace": traceback.format_exc()[-2500:],
            }
    write_json("aged_checkpoint.json", aged)
    return {
        "gates": gates,
        "projection": projection,
        "aged": aged,
        "rss_reduction_percent_slope": reduction,
        "full_tps": full.get("tps"),
        "compact_tps": compact.get("tps"),
    }


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    os.chdir(str(ROOT))
    OUT.mkdir(parents=True, exist_ok=True)
    if ROLE == "rss_child":
        from mechanistic_mind.research import predictive_equivalence as pe

        compact = os.environ.get("PSY_PE_FORGOTTEN_COMPACT", "1") != "0"
        pe.set_forgotten_compaction(compact)
        result = run_rss_child()
        dest = OUT / ("rss_compact.json" if compact else "rss_full.json")
        dest.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        print(json.dumps({"wrote": str(dest), "tps": result.get("tps"), "compact": compact}))
        raise SystemExit(0)
    summary = master()
    (OUT / "run_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"out": str(OUT), "reduction": summary.get("rss_reduction_percent_slope")}, indent=2))
