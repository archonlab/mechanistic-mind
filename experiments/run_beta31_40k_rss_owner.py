#!/usr/bin/env python3
"""Beta 3.1 aged-live RSS owner attribution.

Read-only vs the failed 40k live dir. Isolated temp dirs for probes.
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
from collections import deque
from pathlib import Path

ROOT = Path("/home/thehost/Desktop/psy")
OUT = ROOT / "results" / "beta31_40k_rss_owner"
LIVE = ROOT / "results/psychology_observer/psy_observer_web/.live-psyweb-20260923T180243.860310Z-e02e833b"
CEILING_DELTA_MB = float(os.environ.get("PSY_RSS_CEILING_DELTA_MB", "2048"))
TICKS = [int(x) for x in os.environ.get("PSY_RSS_TICKS", "0,100,250,500,1000,2000").split(",") if x]
SEED = int(os.environ.get("PSY_RSS_SEED", "575"))

PROBES = (
    "RUNTIME_ONLY",
    "NORMAL",
    "HEADLESS",
    "PUBLICATION_SUPPRESSED",
    "V3_ENCODE_SUPPRESSED",
)


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

    roll = {}
    rp = Path(f"/proc/{pid}/smaps_rollup")
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
        maps_n = sum(1 for _ in Path(f"/proc/{pid}/maps").open())
    except OSError:
        maps_n = 0
    return {
        "pid": pid,
        "rss_mb": round(kb("VmRSS") / 1024.0, 3),
        "vms_mb": round(kb("VmSize") / 1024.0, 3),
        "rss_anon_mb": round(kb("RssAnon") / 1024.0, 3),
        "rss_file_mb": round(kb("RssFile") / 1024.0, 3),
        "rss_shmem_mb": round(kb("RssShmem") / 1024.0, 3),
        "threads": int(kv.get("Threads") or 0),
        "roll_pss_mb": round(rkb("Pss") / 1024.0, 3),
        "roll_anon_mb": round(rkb("Anonymous") / 1024.0, 3),
        "roll_private_dirty_mb": round(rkb("Private_Dirty") / 1024.0, 3),
        "maps": maps_n,
        "ru_maxrss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0, 3),
        "gc_counts": list(gc.get_count()),
        "allocated_blocks": int(sys.getallocatedblocks()) if hasattr(sys, "getallocatedblocks") else None,
    }


def _sizeof(obj, seen: set[int] | None = None, budget: int = 500_000) -> int:
    if seen is None:
        seen = set()
    oid = id(obj)
    if oid in seen:
        return 0
    seen.add(oid)
    if len(seen) > budget:
        return 0
    n = sys.getsizeof(obj)
    if hasattr(obj, "nbytes"):
        try:
            return int(obj.nbytes) + n
        except Exception:
            pass
    if isinstance(obj, dict):
        for k, v in obj.items():
            n += _sizeof(k, seen, budget) + _sizeof(v, seen, budget)
    elif isinstance(obj, (list, tuple, set, deque)):
        for x in obj:
            n += _sizeof(x, seen, budget)
    return n


def cognition_card(runtime) -> dict:
    slots = list(getattr(runtime, "slots", None) or [runtime])
    agents = []
    for i, slot in enumerate(slots):
        cog = slot.cognition if isinstance(getattr(slot, "cognition", None), dict) else {}
        pe = cog.get("equivalence") or {}
        classes = pe.get("classes") if isinstance(pe, dict) else {}
        n_cls = len(classes) if isinstance(classes, dict) else 0
        n_for = 0
        n_act = 0
        if isinstance(classes, dict):
            for c in classes.values():
                if isinstance(c, dict) and c.get("status") == "FORGOTTEN":
                    n_for += 1
                else:
                    n_act += 1
        smc = cog.get("sensorimotor_consequence") or {}
        rec = smc.get("records") if isinstance(smc, dict) else None
        pc = cog.get("compression") or {}
        pr = cog.get("prospection") or {}
        trans = pr.get("transitions") if isinstance(pr, dict) else None
        ppc = cog.get("persistent_prospective_control") or {}
        agents.append({
            "slot": i,
            "pe_classes": n_cls,
            "pe_active": n_act,
            "pe_forgotten": n_for,
            "smc_records": len(rec) if isinstance(rec, dict) else None,
            "smc_cap": smc.get("capacity") if isinstance(smc, dict) else None,
            "compression_keys": len(pc) if isinstance(pc, dict) else None,
            "prospection_transitions": len(trans) if isinstance(trans, dict) else None,
            "ppc_keys": len(ppc) if isinstance(ppc, dict) else None,
            "cognition_sizeof_mb": round(_sizeof(cog) / (1024 * 1024), 3),
        })
    return {"n_slots": len(slots), "agents": agents}


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


def configure(probe: str, results_root: Path):
    from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
    from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig

    if probe == "RUNTIME_ONLY":
        from mechanistic_mind.physical_system.ecology_presets import make_ecology_config
        from mechanistic_mind.physical_system.mechanism_configuration import (
            apply_resolved_to_runtime,
            resolve_mechanism_config,
            stamp_config_mechanisms,
        )
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
        return "runtime", rt

    exec_mode = "HEADLESS" if probe == "HEADLESS" else "LIVE"
    s = ObserverSession(SessionConfig(
        seed=SEED,
        buffer_capacity=64,
        ui_hz=10.0,
        results_root=results_root,
        execution_mode=exec_mode,
        evidence_mode="FULL_SCIENTIFIC",
        checkpoint_every_ticks=0,
    ))
    s.apply_experiment({
        "seed": SEED,
        "agent_count": 2,
        "cognition_enabled": True,
        "ecology_preset": "STRUCTURED_WORLD_EXPERIMENTAL",
        "psc_motor_resolution": "OBSERVED_COMPOSITE",
        "vision_radius": 3,
        "checkpoint_every_ticks": 0,
        "mechanisms": failed_run_mechanisms(),
    })
    s.set_vision_radius(3)
    s.set_visual_surface_discrimination("RICH")
    s.set_optical_mapping("CORRELATED")
    s.set_spatial_vision("OCCLUSION")
    s.set_psc_motor_resolution("OBSERVED_COMPOSITE")
    if probe == "HEADLESS":
        s.set_execution_mode("HEADLESS")
    try:
        s.set_tiktaalik_eye(rate="OFF", fpv=False)
    except Exception:
        pass
    if probe == "NORMAL":
        try:
            s.set_tiktaalik_eye(rate="2FPS", fpv=True)
        except Exception:
            pass
    if probe == "SIGNAL_FORENSICS_MINIMAL":
        s._sig_live_enabled = False
    if probe == "PUBLICATION_SUPPRESSED":
        from mechanistic_mind.ui.psy_observer_web import session as sessmod

        def skip_capture(self, detail="compact"):
            tick = int(getattr(self.runtime, "tick", 0) or 0)
            return {"header": {"tick": tick, "status": "SKIPPED_FOR_FORENSIC"}}

        sessmod.ObserverSession._capture_locked = skip_capture
        sessmod.ObserverSession._serialize_published = lambda self, frame: None
        sessmod.ObserverSession._maybe_push = lambda self, *a, **k: None
    if probe in ("V3_ENCODE_SUPPRESSED", "V3_WRITE_SUPPRESSED_BUT_ENCODED"):
        from mechanistic_mind.scientific_v3 import writer as wr

        def append_h(self, runtime):
            if probe == "V3_ENCODE_SUPPRESSED":
                return 0
            from mechanistic_mind.scientific_v3.capture import capture_v3_tick
            pkg = capture_v3_tick(
                runtime,
                run_id=self._run_id or "repro",
                identity_map=self._identity_map,
                generation=self._generation,
            )
            for key in ("spines", "observations", "decisions", "motors", "consequences"):
                for row in pkg.get(key) or []:
                    wr._jsonl_line(row)
            return 0

        wr.ScientificV3Writer.append_runtime_tick = append_h
        if probe == "V3_ENCODE_SUPPRESSED":
            from mechanistic_mind.ui.psy_observer_web.session import ObserverSession

            def skip_sci(self):
                return None

            ObserverSession._append_scientific_locked = skip_sci
    return "session", s


def step_once(kind, obj):
    if kind == "runtime":
        obj.step(n=1)
        return
    obj.step(n=1)


def v3_bytes(results_root: Path) -> int:
    n = 0
    base = results_root / "psychology_observer" / "psy_observer_web"
    if not base.is_dir():
        return 0
    for p in base.rglob("scientific_*.jsonl"):
        try:
            n += p.stat().st_size
        except OSError:
            pass
    return n


def run_probe(probe: str, out_path: Path) -> None:
    sys.path.insert(0, str(ROOT))
    os.chdir(str(ROOT))
    tmp = Path(tempfile.mkdtemp(prefix=f"rss_{probe}_"))
    kind, obj = configure(probe, tmp)
    runtime = obj if kind == "runtime" else obj.runtime
    samples = []
    baseline = _proc()
    t_marks = sorted({int(x) for x in TICKS if int(x) >= 0})
    if 0 not in t_marks:
        t_marks = [0] + t_marks
    next_i = 0
    t0 = time.perf_counter()
    aborted = None
    current = int(getattr(runtime, "tick", 0) or 0)
    while next_i < len(t_marks):
        target = t_marks[next_i]
        while current < target:
            step_once(kind, obj)
            current = int(getattr(runtime, "tick", current + 1) or 0)
            now = _proc()
            if now["rss_mb"] - baseline["rss_mb"] > CEILING_DELTA_MB:
                aborted = {
                    "reason": "RSS_CEILING",
                    "tick": current,
                    "rss_mb": now["rss_mb"],
                    "baseline_rss_mb": baseline["rss_mb"],
                }
                break
        rec = {
            "tick": int(getattr(runtime, "tick", current)),
            "wall_s": round(time.perf_counter() - t0, 3),
            "proc": _proc(),
            "cognition": cognition_card(runtime),
            "v3_disk_bytes": v3_bytes(tmp) if kind == "session" else 0,
            "session_buffer": (
                len(getattr(obj, "_buffer", []) or []) if kind == "session" else 0
            ),
            "timeline": len(getattr(obj, "_timeline", []) or []) if kind == "session" else 0,
            "event_ring": len(getattr(obj, "_event_ring", []) or []) if kind == "session" else 0,
        }
        samples.append(rec)
        next_i += 1
        if aborted:
            break

    gc_info = None
    trim_info = None
    before = _proc()
    n = gc.collect()
    uncol = gc.collect()
    after = _proc()
    gc_info = {
        "collected": n,
        "uncollectable_second": uncol,
        "garbage": len(gc.garbage),
        "rss_before_mb": before["rss_mb"],
        "rss_after_mb": after["rss_mb"],
        "rss_delta_mb": round(after["rss_mb"] - before["rss_mb"], 3),
        "anon_before_mb": before["rss_anon_mb"],
        "anon_after_mb": after["rss_anon_mb"],
    }
    try:
        import ctypes
        libc = ctypes.CDLL("libc.so.6")
        b2 = _proc()
        libc.malloc_trim(0)
        a2 = _proc()
        trim_info = {
            "rss_before_mb": b2["rss_mb"],
            "rss_after_mb": a2["rss_mb"],
            "rss_delta_mb": round(a2["rss_mb"] - b2["rss_mb"], 3),
            "anon_delta_mb": round(a2["rss_anon_mb"] - b2["rss_anon_mb"], 3),
        }
    except Exception as exc:
        trim_info = {"error": str(exc)}

    slopes = {}
    if len(samples) >= 2:
        a, b = samples[0], samples[-1]
        dt = max(1, int(b["tick"]) - int(a["tick"]))
        slopes = {
            "rss_mb_per_1000": round(1000.0 * (b["proc"]["rss_mb"] - a["proc"]["rss_mb"]) / dt, 3),
            "anon_mb_per_1000": round(1000.0 * (b["proc"]["rss_anon_mb"] - a["proc"]["rss_anon_mb"]) / dt, 3),
            "ru_maxrss_mb_per_1000": round(1000.0 * (b["proc"]["ru_maxrss_mb"] - a["proc"]["ru_maxrss_mb"]) / dt, 3),
            "v3_mb_per_1000": round(1000.0 * ((b["v3_disk_bytes"] - a["v3_disk_bytes"]) / (1024 * 1024)) / dt, 3),
            "window": [a["tick"], b["tick"]],
        }
        if a["proc"]["allocated_blocks"] is not None and b["proc"]["allocated_blocks"] is not None:
            slopes["blocks_per_1000"] = round(
                1000.0 * (b["proc"]["allocated_blocks"] - a["proc"]["allocated_blocks"]) / dt, 1
            )
        pe0 = sum(x["pe_forgotten"] for x in a["cognition"]["agents"])
        pe1 = sum(x["pe_forgotten"] for x in b["cognition"]["agents"])
        cog0 = sum(x["cognition_sizeof_mb"] for x in a["cognition"]["agents"])
        cog1 = sum(x["cognition_sizeof_mb"] for x in b["cognition"]["agents"])
        slopes["pe_forgotten_per_1000"] = round(1000.0 * (pe1 - pe0) / dt, 2)
        slopes["cognition_sizeof_mb_per_1000"] = round(1000.0 * (cog1 - cog0) / dt, 3)

    payload = {
        "probe": probe,
        "seed": SEED,
        "kind": kind,
        "tmp": str(tmp),
        "aborted": aborted,
        "baseline": baseline,
        "samples": samples,
        "slopes": slopes,
        "gc_end": gc_info,
        "malloc_trim_end": trim_info,
        "differences_from_failed_run": {
            "failed_run_id": "e02e833b",
            "this_seed": SEED,
            "not_40k": True,
            "session_step_captures_every_tick_unless_headless_or_suppressed": kind == "session",
            "no_websocket_client": True,
            "checkpoint_cadence": "OFF",
            "ecology": "STRUCTURED_WORLD_EXPERIMENTAL",
            "vision": "R3 RICH CORRELATED OCCLUSION",
        },
    }
    out_path.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    if kind == "session":
        try:
            obj.stop(save=False, reason="USER_STOP_NO_SAVE")
        except Exception:
            pass


def main_parent() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    py = sys.executable
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    matrix = []
    for probe in PROBES:
        dest = OUT / f"probe_{probe}.json"
        dest.unlink(missing_ok=True)
        print(f"== {probe} ==", flush=True)
        p = subprocess.run(
            [py, str(Path(__file__).resolve()), "--probe", probe, "--out", str(dest)],
            cwd=str(ROOT),
            env=env,
        )
        rec = {"probe": probe, "returncode": p.returncode}
        if dest.is_file():
            data = json.loads(dest.read_text())
            rec["slopes"] = data.get("slopes")
            rec["aborted"] = data.get("aborted")
            rec["last"] = (data.get("samples") or [{}])[-1]
            rec["gc_end"] = data.get("gc_end")
            rec["malloc_trim_end"] = data.get("malloc_trim_end")
        matrix.append(rec)
        print(json.dumps(rec.get("slopes"), indent=2), flush=True)
    (OUT / "ab_matrix.json").write_text(
        json.dumps({"probes": matrix, "ticks": TICKS, "seed": SEED}, indent=2, default=str) + "\n"
    )


if __name__ == "__main__":
    if "--probe" in sys.argv:
        probe = sys.argv[sys.argv.index("--probe") + 1]
        out = Path(sys.argv[sys.argv.index("--out") + 1])
        run_probe(probe, out)
    else:
        main_parent()
