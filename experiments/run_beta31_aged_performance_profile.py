"""Aged-run performance attribution from the CURRENT Observer checkpoint.

Does not replace the live Observer process. Restores a persist-view of the
aged runtime and advances ~2000 ticks with isolated timing.
"""
from __future__ import annotations

import csv
import json
import os
import shutil
import sys
import time
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime  # noqa: E402
from mechanistic_mind.research import pe_cold_archive as cold  # noqa: E402
from mechanistic_mind.research import tick_profiler as tp  # noqa: E402
from mechanistic_mind.scientific_v3.writer import ScientificV3Writer  # noqa: E402
from mechanistic_mind.ui.psy_observer_web.crash_checkpoint import (  # noqa: E402
    load_committed,
    load_snapshot_dict,
)
from mechanistic_mind.ui.psy_observer_web.scientific_history import (  # noqa: E402
    ScientificHistoryWriter,
)
from mechanistic_mind.ui.psy_observer_web.serialize import live_frame  # noqa: E402

OUT = ROOT / "results" / "beta31_performance_profile"
LIVE = "http://127.0.0.1:8768"
N_TICKS = int(os.environ.get("PSY_PROFILE_TICKS") or 2000)
WINDOW = 100
ABLATION_TICKS = int(os.environ.get("PSY_PROFILE_ABLATION_TICKS") or 150)


def _get(path: str) -> dict[str, Any]:
    with urllib.request.urlopen(LIVE + path, timeout=60) as r:
        return json.loads(r.read().decode())


def _post(path: str) -> dict[str, Any]:
    req = urllib.request.Request(LIVE + path, data=b"{}", method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read().decode())


def vision_cfg(rt: TwoAgentRuntime) -> dict[str, Any]:
    slot = rt.slots[0]
    nfe = getattr(slot.config, "near_field_exteroception", None)
    mechs = getattr(slot.config, "mechanisms", None)
    vis_on = True
    try:
        vis_on = bool(getattr(nfe, "vision_contributes", True))
    except Exception:
        pass
    return {
        "physical_near_field_vision": vis_on,
        "radius": int(getattr(nfe, "radius", 0) or 0) if nfe else None,
        "fov_deg": float(getattr(nfe, "fov_deg", 0) or 0) if nfe else None,
        "visual_surface_discrimination": str(getattr(nfe, "visual_surface_discrimination", "OFF")) if nfe else None,
        "optical_mapping": str(getattr(nfe, "optical_mapping", "INDEPENDENT")) if nfe else None,
        "spatial_vision": str(getattr(nfe, "spatial_vision", "LEGACY")) if nfe else None,
        "enabled": bool(getattr(nfe, "enabled", False)) if nfe else False,
        "mechanisms_unused": mechs is not None,
    }


def pe_counts(rt: TwoAgentRuntime) -> dict[str, Any]:
    out: dict[str, Any] = {"agents": []}
    for i, s in enumerate(rt.slots):
        eq = (s.cognition or {}).get("equivalence") or {}
        classes = eq.get("classes") or {}
        st: dict[str, int] = defaultdict(int)
        for c in classes.values():
            if isinstance(c, dict):
                st[str(c.get("status") or "UNKNOWN")] += 1
        arch = (eq.get("_pe_cold") or {}) if isinstance(eq, dict) else {}
        out["agents"].append({
            "slot": i,
            "class_n": len(classes),
            "status": dict(st),
            "cold_n": int(arch.get("n") or 0) if isinstance(arch, dict) else 0,
            "committed_chunks": len(arch.get("committed") or []) if isinstance(arch, dict) else 0,
        })
    return out


def retarget_cold(rt: TwoAgentRuntime, root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    cold.set_cold_eviction(True, root=root)
    for s in rt.slots:
        eq = (s.cognition or {}).get("equivalence")
        if not isinstance(eq, dict):
            continue
        arch = eq.get("_pe_cold")
        if isinstance(arch, dict):
            arch["evict_root"] = str(root)


def bucket_map(stats: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {b["name"]: b for b in stats.get("buckets") or []}


def mean_ms(bm: dict[str, dict[str, Any]], name: str) -> float:
    b = bm.get(name) or {}
    return float(b.get("mean_ms_per_tick") or 0.0)


def run_profiled(
    rt: TwoAgentRuntime,
    *,
    n: int,
    sci: bool,
    observer: bool,
    sci_dir: Path | None,
    label: str,
) -> dict[str, Any]:
    tp.reset()
    tp.enable()
    writer = None
    v3 = None
    if sci:
        assert sci_dir is not None
        sci_dir.mkdir(parents=True, exist_ok=True)
        writer = ScientificHistoryWriter(sci_dir, flush_every=32)
        writer.open()
        v3 = ScientificV3Writer(sci_dir / "v3", flush_every=32)
        v3.open(run_id=f"profile-{label}", generation=0)
    windows: list[dict[str, Any]] = []
    prev_inc: dict[str, int] = {}
    start_tick = int(rt.tick)
    t_wall0 = time.perf_counter()
    for i in range(n):
        tp.begin_tick()
        with tp.span("tick"):
            with tp.span("sim"):
                rt.step(1)
            if sci and writer is not None:
                with tp.span("sci"):
                    writer.append_tick(rt)
                    if v3 is not None:
                        v3.append_runtime_tick(rt)
            if observer:
                with tp.span("observer"):
                    try:
                        frame = live_frame(
                            rt,
                            status="RUNNING",
                            mode="LIVE",
                            target_tick=None,
                            previous_body=None,
                            detail="compact",
                            include_cognition=True,
                        )
                        payload = json.dumps(frame, default=str)
                        tp.count("observer_bytes", len(payload))
                    except Exception as exc:
                        tp.count("observer_error")
                        tp.count("observer_error_chars", len(str(exc)))
        tp.end_tick(int(rt.tick))
        if (i + 1) % WINDOW == 0:
            st = tp.snapshot_stats()
            bm = bucket_map(st)
            inc_now = {b["name"]: b["inclusive_ms"] for b in st["buckets"]}
            delta = {k: inc_now.get(k, 0) - prev_inc.get(k, 0) for k in set(inc_now) | set(prev_inc)}
            prev_inc = inc_now
            wstats = (st.get("windows") or [{}])[-1]
            windows.append({
                "label": label,
                "start_tick": start_tick + i + 1 - WINDOW,
                "end_tick": start_tick + i + 1,
                "mean_ms": wstats.get("mean_ms"),
                "p50_ms": wstats.get("p50_ms"),
                "p95_ms": wstats.get("p95_ms"),
                "max_ms": wstats.get("max_ms"),
                "sim_ms": delta.get("sim", 0) / WINDOW,
                "observation_ms": delta.get("observation", 0) / WINDOW,
                "vision_sample_ms": delta.get("vis_sample", 0) / WINDOW,
                "vision_spatial_ms": delta.get("vis_spatial", 0) / WINDOW,
                "cognition_ms": delta.get("cognition", 0) / WINDOW,
                "pe_learn_ms": delta.get("pe_learn", 0) / WINDOW,
                "compose_ms": delta.get("compose", 0) / WINDOW,
                "sci_ms": delta.get("sci", 0) / WINDOW,
                "sci_build_ms": delta.get("sci_build", 0) / WINDOW,
                "sci_serialize_ms": delta.get("sci_serialize", 0) / WINDOW,
                "sci_write_ms": delta.get("sci_write", 0) / WINDOW,
                "observer_ms": delta.get("observer", 0) / WINDOW,
                "cold_evict_ms": delta.get("cold_evict", 0) / WINDOW,
                "pe": pe_counts(rt),
            })
    if writer is not None:
        writer.flush()
        writer.close()
    if v3 is not None:
        v3.flush()
        v3.close()
    wall = time.perf_counter() - t_wall0
    stats = tp.snapshot_stats()
    tp.disable()
    stats["wall_s"] = wall
    stats["label"] = label
    stats["start_tick"] = start_tick
    stats["end_tick"] = int(rt.tick)
    stats["measured_ticks"] = n
    stats["windows"] = windows
    stats["vision"] = vision_cfg(rt)
    stats["pe_end"] = pe_counts(rt)
    return stats


def disable_vision(rt: TwoAgentRuntime) -> None:
    for s in rt.slots:
        nfe = getattr(s.config, "near_field_exteroception", None)
        if nfe is None:
            continue
        nfe.enabled = False
        if hasattr(nfe, "vision_contributes"):
            nfe.vision_contributes = False
        if hasattr(nfe, "perception_enabled"):
            nfe.perception_enabled = False


def slope(windows, key):
    xs = [float(w.get(key) or 0.0) for w in windows]
    if len(xs) < 2:
        return 0.0
    return (xs[-1] - xs[0]) / float(len(xs) - 1)


def dir_bytes(path):
    out = {}
    names = (
        "scientific_timeline.jsonl",
        "scientific_events.jsonl",
        "scientific_checkpoints.jsonl",
        "scientific_meta.json",
    )
    for name in names:
        pth = path / name
        if pth.is_file():
            out[name] = int(pth.stat().st_size)
    v3 = path / "v3"
    if v3.is_dir():
        for pth in v3.glob("*.jsonl"):
            out[str(pth.relative_to(path))] = int(pth.stat().st_size)
    cold = path.parent.parent / "pe_cold" / "session"
    if not cold.is_dir():
        cold = ROOT / "results" / "psychology_observer" / "psy_observer_web" / "pe_cold" / "session"
    if cold.is_dir():
        total = 0
        n = 0
        for pth in cold.rglob("*"):
            if pth.is_file():
                total += int(pth.stat().st_size)
                n += 1
        out["pe_cold_bytes"] = total
        out["pe_cold_files"] = n
    return out


def live_poll(n_ticks, live_dir):
    start = _get("/api/runtime/progress")
    start_tick = int(start.get("tick") or 0)
    target = start_tick + n_ticks
    samples = []
    prev = start_tick - 1
    t0 = time.perf_counter()
    print(f"live poll ticks {start_tick} -> {target}")
    while True:
        p = _get("/api/runtime/progress")
        tick = int(p.get("tick") or 0)
        if tick != prev:
            hdr = {}
            try:
                hdr = _get("/api/header")
            except Exception:
                pass
            sizes = dir_bytes(live_dir)
            samples.append({
                "tick": tick,
                "last_tick_wall_ms": p.get("last_tick_wall_ms"),
                "status_detail": p.get("status_detail"),
                "sim_tps": hdr.get("sim_ticks_per_sec"),
                "observer_fps": hdr.get("observer_fps"),
                "sci_bytes": sum(sizes.values()),
                "timeline_bytes": sizes.get("scientific_timeline.jsonl", 0),
                "events_bytes": sizes.get("scientific_events.jsonl", 0),
                "v3_obs_bytes": sum(v for k, v in sizes.items() if "observations.jsonl" in k),
                "mono": time.perf_counter() - t0,
            })
            prev = tick
            if tick >= target:
                break
            if len(samples) % 100 == 0:
                print("...", tick, "ms", p.get("last_tick_wall_ms"), "tps", hdr.get("sim_ticks_per_sec"))
        if time.perf_counter() - t0 > max(120.0, n_ticks * 4.0):
            print("poll timeout at", tick)
            break
        time.sleep(0.05)
    walls = [float(s["last_tick_wall_ms"] or 0) for s in samples]
    windows = []
    for i in range(0, max(0, len(walls) - WINDOW + 1), WINDOW):
        chunk = walls[i:i + WINDOW]
        smp = samples[i:i + WINDOW]
        windows.append({
            "start_tick": smp[0]["tick"],
            "end_tick": smp[-1]["tick"],
            "mean_ms": sum(chunk) / len(chunk),
            "p50_ms": sorted(chunk)[len(chunk)//2],
            "p95_ms": sorted(chunk)[int(0.95 * (len(chunk)-1))],
            "sci_bytes_end": smp[-1]["sci_bytes"],
            "sci_bytes_delta": smp[-1]["sci_bytes"] - smp[0]["sci_bytes"],
        })
    return {
        "start_tick": start_tick,
        "end_tick": samples[-1]["tick"] if samples else start_tick,
        "measured_ticks": len(samples),
        "mean_ms_per_tick": (sum(walls)/len(walls)) if walls else 0.0,
        "p50_ms_per_tick": sorted(walls)[len(walls)//2] if walls else 0.0,
        "p95_ms_per_tick": sorted(walls)[int(0.95*(len(walls)-1))] if walls else 0.0,
        "max_ms_per_tick": max(walls) if walls else 0.0,
        "windows": windows,
        "sci_bytes_start": samples[0]["sci_bytes"] if samples else 0,
        "sci_bytes_end": samples[-1]["sci_bytes"] if samples else 0,
        "wall_s": time.perf_counter() - t0,
        "samples_tail": samples[-3:],
    }


def vision_bench(rt, n=40):
    tp.reset(); tp.enable()
    t0 = time.perf_counter()
    for _ in range(n):
        with tp.span("observation"):
            rt.observations()
    elapsed = time.perf_counter() - t0
    st = tp.snapshot_stats(ticks=n)
    tp.disable()
    st["bench_s"] = elapsed
    st["mean_obs_ms"] = 1000.0 * elapsed / n
    st["vision"] = vision_cfg(rt)
    return st


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    live_meta = {}
    try:
        live_meta["header"] = _get("/api/header")
        live_meta["stop"] = _get("/api/control/stop-info")
        live_meta["eye"] = _get("/api/observer/tiktaalik-eye")
        live_meta["vision_radius"] = _get("/api/vision/radius")
        live_meta["spatial"] = _get("/api/vision/spatial-vision")
        live_meta["progress"] = _get("/api/runtime/progress")
        st = _get("/api/state")
        nfe = ((st.get("physical") or {}).get("near_field_exteroception") or {})
        live_meta["runtime_vision"] = {k: nfe.get(k) for k in (
            "visual_surface_discrimination","spatial_vision","optical_mapping",
            "radius","fov_deg","vision_contributes","enabled","perception_enabled")}
        live_meta["evidence_mode"] = (st.get("header") or {}).get("evidence_mode")
        live_meta["pe_cold"] = (st.get("header") or {}).get("pe_cold_history_eviction")
        live_meta["observer_detail"] = {
            "preset": (st.get("header") or {}).get("observer_detail_preset"),
            "products": (st.get("header") or {}).get("observer_products"),
            "frame_detail": (st.get("header") or {}).get("frame_detail"),
        }
    except Exception as exc:
        live_meta["live_error"] = str(exc)
    (OUT / "live_metadata.json").write_text(json.dumps(live_meta, indent=2, default=str))
    run_id = str((live_meta.get("stop") or {}).get("run_id") or "")
    live_dir = ROOT / "results" / "psychology_observer" / "psy_observer_web" / (".live-" + run_id)
    print("live tick", (live_meta.get("header") or {}).get("tick"), "vision", live_meta.get("runtime_vision"))

    poll = live_poll(N_TICKS, live_dir)
    (OUT / "live_poll.json").write_text(json.dumps(poll, indent=2, default=str))

    print("checkpoint after poll...")
    ck = _post("/api/checkpoint/now")
    (OUT / "checkpoint_receipt.json").write_text(json.dumps(ck, indent=2, default=str))

    vision_stats = {}
    committed = None
    if ck.get("dir"):
        d = Path(str(ck["dir"]))
        for cand in (d, d.parent, d.parent.parent, live_dir):
            committed = load_committed(cand)
            if committed:
                break
    committed = committed or load_committed(live_dir)
    if committed:
        payload = load_snapshot_dict(committed)
        shutil.copy2(committed["snapshot_path"], OUT / "aged_snapshot.json")
        try:
            rt = TwoAgentRuntime.restore(payload)
            vision_stats = vision_bench(rt, n=40)
        except Exception as exc:
            vision_stats = {"restore_error": str(exc)}
    (OUT / "vision_bench.json").write_text(json.dumps(vision_stats, indent=2, default=str))

    wins = poll.get("windows") or []
    with (OUT / "profile_windows.csv").open("w", newline="") as fh:
        fields = ["start_tick","end_tick","mean_ms","p50_ms","p95_ms","sci_bytes_end","sci_bytes_delta"]
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in wins:
            w.writerow(row)
    hot_rows = vision_stats.get("buckets") or []
    with (OUT / "profile_hotpaths.csv").open("w", newline="") as fh:
        fields = ["name","self_ms_per_tick","mean_ms_per_tick","calls_per_tick","mean_us_per_call","calls"]
        wcsv = csv.DictWriter(fh, fieldnames=fields)
        wcsv.writeheader()
        for b in sorted(hot_rows, key=lambda x: -float(x.get("self_ms") or 0)):
            wcsv.writerow({k: b.get(k) for k in fields})

    delta_sci = float(poll.get("sci_bytes_end") or 0) - float(poll.get("sci_bytes_start") or 0)
    mt = max(1, int(poll.get("measured_ticks") or 1))
    summary = {
        "mode": "LIVE_POLL_PLUS_VISION_BENCH",
        "run_id": run_id,
        "runtime_vision": live_meta.get("runtime_vision"),
        "eye": live_meta.get("eye"),
        "poll": {k: poll.get(k) for k in (
            "start_tick","end_tick","measured_ticks","mean_ms_per_tick",
            "p50_ms_per_tick","p95_ms_per_tick","max_ms_per_tick",
            "sci_bytes_start","sci_bytes_end","wall_s")},
        "sci_bytes_per_tick": delta_sci / mt,
        "vision_bench_mean_obs_ms": vision_stats.get("mean_obs_ms"),
        "accounted_wall_time_percent": None,
        "accounted_note": "Live last_tick_wall_ms is session SIM+SCI+hooks exclusive of Observer capture thread. Subsystem split from observation() restore bench only.",
        "windows": wins,
        "slopes": {"total": slope(wins, "mean_ms"), "sci_bytes": slope(wins, "sci_bytes_delta")},
    }
    (OUT / "profile_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    (OUT / "PERFORMANCE_PROFILE.md").write_text(
        "# Beta 3.1 aged-run performance profile\n\n"
        "CURRENT live Observer measured without replacing the process.\n\n"
        + json.dumps(summary, indent=2, default=str) + "\n"
    )
    print("wrote", OUT)


if __name__ == "__main__":
    main()
