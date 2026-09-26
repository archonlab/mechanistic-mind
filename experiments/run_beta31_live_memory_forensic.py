#!/usr/bin/env python3
"""Read-only memory forensic for the current live Observer + a separate reproduction.

Does not reset, stop, or mutate the live experiment. Reproduction uses a new
ObserverSession in-process and never attaches to the live PID.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "beta31_live_memory_forensic"
LIVE_PORT = int(os.environ.get("PSY_LIVE_PORT", "8768"))
LIVE_PID = int(os.environ.get("PSY_LIVE_PID", "368895"))
SAMPLES = int(os.environ.get("PSY_LIVE_SAMPLES", "4"))
INTERVAL_S = float(os.environ.get("PSY_LIVE_INTERVAL_S", "25"))


def _get(path: str, timeout: float = 8.0) -> dict:
    url = f"http://127.0.0.1:{LIVE_PORT}{path}"
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode())


def proc_sample(pid: int) -> dict:
    st = Path(f"/proc/{pid}/status").read_text()
    kv = {}
    for line in st.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            kv[k.strip()] = v.strip()
    fd_n = 0
    try:
        fd_n = len(os.listdir(f"/proc/{pid}/fd"))
    except OSError:
        pass
    rss_kb = int(str(kv.get("VmRSS", "0")).split()[0] or 0)
    vms_kb = int(str(kv.get("VmSize", "0")).split()[0] or 0)
    shared_kb = int(str(kv.get("RssFile", kv.get("RssShmem", "0 kB")).split()[0] or 0) or 0)
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
    return {
        "pid": pid,
        "rss_mb": round(rss_kb / 1024.0, 2),
        "vms_mb": round(vms_kb / 1024.0, 2),
        "shared_mb": round(shared_kb / 1024.0, 2) if shared_kb else None,
        "threads": int(kv.get("Threads") or 0),
        "fd_count": fd_n,
        "smaps_pss_mb": round(int(str(roll.get("Pss", "0")).split()[0] or 0) / 1024.0, 2) if roll else None,
        "smaps_anon_mb": round(int(str(roll.get("Anonymous", "0")).split()[0] or 0) / 1024.0, 2) if roll else None,
        "voluntary_ctxt": kv.get("voluntary_ctxt_switches"),
    }


def find_live_dirs() -> list[dict]:
    hits = []
    for base in (ROOT / "results", ROOT):
        if not base.is_dir():
            continue
        for p in base.rglob(".live-*"):
            if not p.is_dir():
                continue
            try:
                mtime = p.stat().st_mtime
            except OSError:
                continue
            if time.time() - mtime > 86400 * 2:
                continue
            sizes = {}
            total = 0
            for f in p.iterdir():
                if f.is_file():
                    b = f.stat().st_size
                    sizes[f.name] = b
                    total += b
            hits.append({"path": str(p), "bytes": total, "files": sizes, "mtime": mtime})
    hits.sort(key=lambda x: -x["mtime"])
    return hits[:12]


def cheap_live_science() -> dict:
    out: dict = {}
    for path in (
        "/api/runtime/progress",
        "/api/header",
        "/api/vision/spatial-vision",
        "/api/vision/radius",
        "/api/config/psc-motor-resolution",
        "/api/observer/tiktaalik-eye",
        "/api/observer/detail",
        "/api/snapshot/meta",
        "/api/evidence/gearbox",
    ):
        try:
            out[path] = _get(path, timeout=12.0)
        except Exception as exc:  # noqa: BLE001
            out[path] = {"error": str(exc)}
    return out


def estimate_sizes(obj, budget=80) -> dict:
    """Shallow size notes without recursive deepcopy of giant stores."""
    if not isinstance(obj, dict):
        return {"type": type(obj).__name__}
    note = {}
    for k, v in list(obj.items())[:budget]:
        if isinstance(v, (list, tuple)):
            note[k] = {"n": len(v), "kind": "seq"}
        elif isinstance(v, dict):
            note[k] = {"n": len(v), "kind": "map", "keys": list(v)[:12]}
        else:
            note[k] = v if isinstance(v, (int, float, str, bool)) or v is None else type(v).__name__
    return note


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    live_id = {
        "CURRENT_RUN_INSPECTED": "YES",
        "port": LIVE_PORT,
        "pid": LIVE_PID,
        "launcher_instance": json.loads((ROOT / ".psy_observer" / "instance.json").read_text())
        if (ROOT / ".psy_observer" / "instance.json").is_file()
        else None,
        "note": "Read-only /proc + HTTP. No reset/stop/mechanism mutation.",
    }
    samples = []
    science_snaps = []
    t0 = time.time()
    for i in range(max(3, SAMPLES)):
        prog = {}
        try:
            prog = _get("/api/runtime/progress", timeout=5)
        except Exception as exc:  # noqa: BLE001
            prog = {"error": str(exc)}
        try:
            hdr = _get("/api/header", timeout=8)
        except Exception as exc:  # noqa: BLE001
            hdr = {"error": str(exc)}
        ps = proc_sample(LIVE_PID)
        tick = (prog.get("tick") if isinstance(prog, dict) else None) or (hdr.get("tick") if isinstance(hdr, dict) else None)
        rec = {
            "i": i,
            "wall_s": round(time.time() - t0, 2),
            "tick": tick,
            "status": prog.get("status") if isinstance(prog, dict) else None,
            "tps": (hdr.get("sim_ticks_per_sec") if isinstance(hdr, dict) else None)
            or (prog.get("sim_ticks_per_sec") if isinstance(prog, dict) else None),
            **ps,
            "evidence_dirs": find_live_dirs(),
        }
        if i == 0:
            rec["science"] = cheap_live_science()
            rec["science_sizes"] = {k: estimate_sizes(v) if isinstance(v, dict) else v for k, v in rec["science"].items()}
        samples.append(rec)
        science_snaps.append({"i": i, "tick": tick, "rss_mb": ps["rss_mb"], "vms_mb": ps["vms_mb"]})
        (OUT / "process_samples.json").write_text(json.dumps(samples, indent=2, default=str))
        if i + 1 < max(3, SAMPLES):
            time.sleep(INTERVAL_S)

    slopes = {}
    if len(samples) >= 2 and samples[0].get("tick") and samples[-1].get("tick"):
        dtick = int(samples[-1]["tick"]) - int(samples[0]["tick"])
        drss = float(samples[-1]["rss_mb"]) - float(samples[0]["rss_mb"])
        slopes = {
            "tick0": samples[0]["tick"],
            "tick1": samples[-1]["tick"],
            "dtick": dtick,
            "d_rss_mb": round(drss, 3),
            "rss_per_1000_ticks_mb": round(drss / max(dtick, 1) * 1000.0, 3) if dtick else None,
            "wall_s": samples[-1]["wall_s"],
        }
    (OUT / "live_identity.json").write_text(json.dumps(live_id, indent=2))
    repro = reproduction_evidence()
    (OUT / "store_cardinality.json").write_text(json.dumps(repro.get("stores") or {}, indent=2, default=str))
    (OUT / "heap_top_allocations.json").write_text(json.dumps(repro.get("heap") or {}, indent=2, default=str))
    (OUT / "fpv_memory_modes.json").write_text(json.dumps(repro.get("fpv") or {}, indent=2, default=str))
    (OUT / "allocation_hotspots.json").write_text(json.dumps(repro.get("hotspots") or {}, indent=2, default=str))
    (OUT / "memory_slopes.json").write_text(
        json.dumps({"live": slopes, "samples": science_snaps, "reproduction": repro.get("slopes")}, indent=2, default=str)
    )
    print(json.dumps({"live_pid": LIVE_PID, "samples": len(samples), "slopes": slopes, "repro": repro.get("slopes")}, indent=2))


def _slots(rt):
    sl = getattr(rt, "slots", None)
    return list(sl) if sl else [rt]


def _est_bytes(obj, cap: int = 250_000) -> int | None:
    try:
        s = json.dumps(obj, default=str, separators=(",", ":"))
        n = len(s.encode())
        return min(n, cap)
    except Exception:
        return None


def store_cardinality(rt, *, label: str) -> list[dict]:
    rows = []
    for i, slot in enumerate(_slots(rt)):
        cog = getattr(slot, "cognition", None) or {}
        smc = cog.get("sensorimotor_consequence") or {}
        recs = smc.get("records") if isinstance(smc.get("records"), dict) else {}
        pc = cog.get("compression") or {}
        pe = cog.get("equivalence") or {}
        pr = cog.get("prospection") or {}
        obs = getattr(slot, "last_agent_observation", None) or {}
        trans = pr.get("transitions")
        if not isinstance(trans, dict):
            trans = pr.get("by_id") if isinstance(pr.get("by_id"), dict) else {}
        rows.append({
            "label": label,
            "agent": f"agent_{i}",
            "observation_keys": len(obs) if isinstance(obs, dict) else None,
            "spatial_keys": len([k for k in (obs or {}) if str(k).startswith("spatial_")]),
            "smc_records": len(recs),
            "smc_capacity": smc.get("capacity"),
            "smc_evictions": smc.get("evictions"),
            "smc_est_bytes": _est_bytes({"n": len(recs), "sample": next(iter(recs.values()), None)}),
            "pc_raw_log": len(pc.get("raw_log") or {}),
            "pc_recent": len(pc.get("recent") or []),
            "pc_structures": len(pc.get("structures") or {}),
            "pc_exceptions": len(pc.get("exceptions") or {}),
            "pc_forgotten_structures": pc.get("forgotten_structures"),
            "pc_recent_capacity": pc.get("recent_capacity"),
            "pc_structure_capacity": pc.get("structure_capacity"),
            "pe_classes": len(pe.get("classes") or {}),
            "pe_episodes": len(pe.get("episodes") or []),
            "pe_forgotten": pe.get("forgotten"),
            "prospection_transitions": len(trans) if isinstance(trans, dict) else None,
            "prospection_workspace": len(pr.get("workspace") or []),
        })
    return rows


def reproduction_evidence() -> dict:
    """Independent in-process session. Never attaches to the live PID."""
    import gc
    import resource
    import tracemalloc

    from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig

    out: dict = {"kind": "REPRODUCTION_EVIDENCE"}
    try:
        tracemalloc.start(8)
    except Exception:
        pass

    def make(spatial: str):
        sess = ObserverSession(SessionConfig(seed=373, evidence_mode="FULL_SCIENTIFIC", buffer_capacity=512, ui_hz=4.0))
        sess.apply_experiment({"seed": 373, "agent_count": 2, "cognition_enabled": True})
        try:
            sess.set_spatial_vision(spatial)
        except Exception as exc:  # noqa: BLE001
            out.setdefault("spatial_errors", []).append(str(exc))
        try:
            sess.set_vision_radius(3)
        except Exception:
            if hasattr(sess.runtime, "set_vision_radius"):
                sess.runtime.set_vision_radius(3)
        try:
            if hasattr(sess.runtime, "set_visual_surface_discrimination"):
                sess.runtime.set_visual_surface_discrimination("RICH")
        except Exception:
            pass
        return sess

    s = make("OCCLUSION")
    rss0 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    cards = []
    heap_snaps = []
    n = int(os.environ.get("PSY_REPRO_TICKS", "80"))
    mid = max(1, n // 2)
    t_marks = {0, mid, n}
    t0 = time.time()
    for i in range(n + 1):
        if i:
            s.step()
        if i in t_marks:
            gc.collect()
            card = store_cardinality(s.runtime, label=f"occ_t{i}")
            rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
            rec = {
                "tick": i,
                "stores": card,
                "buffer_n": len(s._buffer),
                "buffer_maxlen": s._buffer.maxlen,
                "rss_max_mb": rss,
                "published_json_kb": round(len(s._published_json or "") / 1024.0, 2) if getattr(s, "_published_json", None) else None,
                "eye_payload_bytes": (getattr(s, "_eye_last_payload", None) or {}).get("payload_bytes"),
            }
            v3 = getattr(s, "_v3_writer", None)
            if v3 is not None:
                rec["v3_health"] = v3.health
                rec["v3_queue"] = sum(len(v) for v in v3._bufs.values())
            cards.append(rec)
            if tracemalloc.is_tracing():
                snap = tracemalloc.take_snapshot()
                stats = snap.statistics("traceback")[:10]
                heap_snaps.append({
                    "tick": i,
                    "top": [{"size_mb": round(st.size / 1e6, 3), "count": st.count, "tb": " | ".join(st.traceback.format()[-2:])} for st in stats],
                })
    wall = round(time.time() - t0, 2)
    s_leg = make("LEGACY")
    for _ in range(n):
        s_leg.step()
    cards.append({"tick": n, "stores": store_cardinality(s_leg.runtime, label="legacy_tN")})

    fpv = {}
    for rate, fpv_on in (("OFF", False), ("SNAPSHOT", False), ("2FPS", True), ("5FPS", True), ("PER_TICK", True)):
        s.set_tiktaalik_eye(rate=rate, fpv=fpv_on)
        s.step()
        with s._lock:
            fr = s._capture_locked()
        eye = fr.get("tiktaalik_eye") or {}
        agents = eye.get("agents") or {}
        fpv[rate] = {
            "fpv_flag": fpv_on,
            "status": eye.get("status"),
            "fpv_included": eye.get("fpv_included"),
            "agents_with_fpv": sum(1 for a in agents.values() if (a or {}).get("fpv")),
            "payload_bytes": eye.get("payload_bytes") or (getattr(s, "_eye_last_payload") or {}).get("payload_bytes"),
            "prev_fpv_keys": len(getattr(s, "_eye_prev_fpv", {}) or {}),
        }
    s.set_tiktaalik_eye(rate="OFF", fpv=False)
    occ = [c for c in cards if c.get("stores") and str((c["stores"][0] or {}).get("label", "")).startswith("occ_")]
    slope = {}
    if len(occ) >= 2:
        dt = max(1, int(occ[-1]["tick"]) - int(occ[0]["tick"]))
        r0, r1 = occ[0].get("rss_max_mb"), occ[-1].get("rss_max_mb")
        slope = {
            "tick0": occ[0]["tick"],
            "tick1": occ[-1]["tick"],
            "dtick": dt,
            "rss0_max_mb": r0,
            "rss1_max_mb": r1,
            "rss_per_1000_ticks_mb": round(((r1 or 0) - (r0 or 0)) / dt * 1000.0, 3) if r0 is not None and r1 is not None else None,
            "note": "ru_maxrss is high-water mark. Distinguishes from live /proc RSS.",
            "wall_s": wall,
        }
    out.update({
        "stores": {"samples": cards},
        "heap": {"snapshots": heap_snaps},
        "fpv": fpv,
        "hotspots": heap_snaps[-1] if heap_snaps else {},
        "slopes": slope,
        "rss_max_start_mb": rss0,
        "rss_max_end_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0,
        "CURRENT_RUN_MUTATED": False,
    })
    if tracemalloc.is_tracing():
        tracemalloc.stop()
    s.status = "STOPPED"
    s_leg.status = "STOPPED"
    return out


if __name__ == "__main__":
    main()
