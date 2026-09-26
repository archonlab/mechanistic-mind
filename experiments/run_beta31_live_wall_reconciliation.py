"""In-process Observer wall-time reconciliation (100–250 ticks).

Requires PSY_TICK_PROFILE=1 in the Observer process. Restores the aged
Beta 3.1 checkpoint into that same process, then plays a short window.
"""
from __future__ import annotations

import csv
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime  # noqa: E402
from mechanistic_mind.research import tick_profiler as tp  # noqa: E402
from mechanistic_mind.scientific_v3.writer import ScientificV3Writer  # noqa: E402
from mechanistic_mind.ui.psy_observer_web.crash_checkpoint import (  # noqa: E402
    load_committed,
    load_snapshot_dict,
)
from mechanistic_mind.ui.psy_observer_web.scientific_history import (  # noqa: E402
    ScientificHistoryWriter,
)

LIVE = os.environ.get("PSY_OBSERVER_URL") or "http://127.0.0.1:8768"
N_TICKS = int(os.environ.get("PSY_RECONCILE_TICKS") or 150)
ABLATION_TICKS = int(os.environ.get("PSY_RECONCILE_ABLATION_TICKS") or 80)
CK_LIVE = ROOT / (
    "results/psychology_observer/psy_observer_web/"
    ".live-psyweb-20260925T051335.153498Z-3c040b03"
)
OUT = ROOT / "results" / "beta31_performance_profile" / "live_reconciled"


def _req(path: str, method: str = "GET", payload: dict[str, Any] | None = None, timeout: float = 600.0) -> dict[str, Any]:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(LIVE + path, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode()
        return json.loads(raw) if raw else {}


def _bucket_map(snap: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {b["name"]: b for b in (snap.get("buckets") or [])}


def _ms(bmap: dict[str, dict[str, Any]], name: str, field: str = "mean_ms_per_tick") -> float:
    row = bmap.get(name) or {}
    return float(row.get(field) or 0.0)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("")
        return
    keys = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def overhead_fixture() -> dict[str, Any]:
    from mechanistic_mind.model.tiktaalik import tiktaalik_config

    def run(profile: bool, n: int = 12) -> float:
        tp.reset()
        if profile:
            tp.enable()
        else:
            tp.disable()
        cfg = tiktaalik_config()
        rt = TwoAgentRuntime(seed=17, config=cfg)
        t0 = time.perf_counter()
        for _ in range(n):
            if profile:
                tp.begin_tick()
            rt.step(1)
            if profile:
                tp.end_tick(rt.tick)
        dt = time.perf_counter() - t0
        tp.disable()
        return dt

    off = run(False)
    on = run(True)
    pct = 100.0 * (on - off) / off if off > 0 else 0.0
    return {"off_s": off, "on_s": on, "overhead_percent": round(pct, 3), "ticks": 12}


def sci_ablation(snapshot: dict[str, Any]) -> dict[str, Any]:
    tmp = ROOT / "results" / "beta31_performance_profile" / "live_reconciled" / "_ablation"
    if tmp.exists():
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True, exist_ok=True)

    def once(label: str, with_sci: bool) -> dict[str, Any]:
        rt = TwoAgentRuntime.restore(snapshot)
        tp.reset()
        tp.enable()
        w2 = w3 = None
        if with_sci:
            d2 = tmp / f"{label}_v2"
            d3 = tmp / f"{label}_v3"
            d2.mkdir(parents=True, exist_ok=True)
            d3.mkdir(parents=True, exist_ok=True)
            w2 = ScientificHistoryWriter(d2)
            w2.open()
            w3 = ScientificV3Writer(d3)
            w3.open(run_id=f"ablation-{label}")
        t0 = time.perf_counter()
        for _ in range(ABLATION_TICKS):
            tp.begin_tick()
            with tp.span("tick"):
                with tp.span("sim"):
                    rt.step(1)
                if with_sci and w2 is not None and w3 is not None:
                    with tp.span("sci"):
                        w2.append_tick(rt)
                        w3.append_runtime_tick(rt)
            tp.end_tick(rt.tick)
        wall = time.perf_counter() - t0
        if w2 is not None:
            w2.close()
        if w3 is not None:
            w3.close()
        snap = tp.snapshot_stats()
        tp.disable()
        b = _bucket_map(snap)
        return {
            "label": label,
            "with_sci": with_sci,
            "ticks": ABLATION_TICKS,
            "wall_s": wall,
            "mean_ms_per_tick": snap["mean_ms_per_tick"],
            "sim_ms": _ms(b, "sim"),
            "sci_ms": _ms(b, "sci"),
            "cognition_ms": _ms(b, "cognition"),
        }

    on = once("sci_on", True)
    off = once("sci_off", False)
    return {
        "on": on,
        "off": off,
        "delta_mean_ms": on["mean_ms_per_tick"] - off["mean_ms_per_tick"],
        "note": "Sibling restored process, not the live Observer play thread.",
    }


def sample_jsonl(path: Path, n: int = 4) -> dict[str, Any]:
    if not path.is_file():
        return {"exists": False, "path": str(path)}
    sizes: list[int] = []
    keys: list[str] = []
    with path.open("r", encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            if i >= n:
                break
            line = line.strip()
            sizes.append(len(line) + 1)
            try:
                obj = json.loads(line)
                keys = sorted(obj.keys())
            except Exception:
                pass
    st = path.stat()
    return {
        "exists": True,
        "path": str(path),
        "bytes": int(st.st_size),
        "sample_line_bytes": sizes,
        "sample_mean_line_bytes": (sum(sizes) / len(sizes)) if sizes else 0,
        "sample_keys": keys,
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    health = _req("/api/health")
    header0 = _req("/api/header")
    start_meta = {
        "health": health,
        "header_before": {k: header0.get(k) for k in ("tick", "status", "run_id", "execution_mode") if k in header0 or True},
        "header_raw_keys": list(header0.keys())[:40],
    }
    tick0 = int(header0.get("tick") or 0)

    restore = _req(
        "/api/checkpoint/restore",
        method="POST",
        payload={"dest_root": str(CK_LIVE)},
        timeout=900.0,
    )
    if not restore.get("accepted"):
        (OUT / "restore_failed.json").write_text(json.dumps(restore, indent=2, default=str))
        print("RESTORE_FAILED", restore)
        return 2

    start_tick = int(restore.get("runtime_tick") or restore.get("checkpoint_tick") or 0)
    _req("/api/control/execution-mode", method="POST", payload={"mode": "MAX"})
    _req("/api/tick-profile")  # ensure route exists
    tp_before = _req("/api/tick-profile")
    _req("/api/control/play", method="POST", payload={})

    target = start_tick + N_TICKS
    t_wait0 = time.perf_counter()
    last = start_tick
    while time.perf_counter() - t_wait0 < 900.0:
        try:
            hdr = _req("/api/header")
        except Exception:
            time.sleep(0.5)
            continue
        last = int(hdr.get("tick") or hdr.get("sim_tick") or last)
        if last >= target:
            break
        time.sleep(0.25)
    _req("/api/control/pause", method="POST", payload={})
    time.sleep(0.4)
    snap = _req("/api/tick-profile")
    end_tick = int(snap.get("runtime_tick") or last)
    run_id = snap.get("run_id")

    bmap = _bucket_map(snap)
    buckets_sorted = sorted(
        snap.get("buckets") or [],
        key=lambda r: -float(r.get("mean_ms_per_tick") or 0),
    )
    cog_names = [
        "cognition",
        "compose",
        "pe_learn",
        "cog_predict_loop",
        "pc_predict",
        "pc_observe",
        "learn_transition",
        "tps_learn",
        "tps_append",
        "tps_retrieve",
        "pe_retrieve",
        "prl_retrieve",
        "tpb_collect",
        "pcp_collect",
        "map_collect",
        "conflict_organize",
        "fsa_groups",
        "scenario_groups",
        "compete_scenarios",
        "pe_diagnostic",
        "tps_diagnostic",
        "pc_purge",
        "cog_retain",
        "per_realize",
        "tpe_ingest",
        "ms_ingest",
        "begin_tick_agent_0",
        "begin_tick_agent_1",
    ]
    cog_rows = []
    for name in cog_names:
        row = bmap.get(name)
        if row:
            cog_rows.append(row)
    cog_rows.sort(key=lambda r: -float(r.get("self_ms_per_tick") or 0))

    live_dir = Path(snap["sci_live_dir"]) if snap.get("sci_live_dir") else None
    sci_files = {}
    if live_dir and live_dir.is_dir():
        for p in sorted(live_dir.glob("scientific_*.jsonl")):
            sci_files[p.name] = sample_jsonl(p, n=3)

    measured = max(1, end_tick - start_tick)
    sim_ms = _ms(bmap, "sim")
    sci_ms = _ms(bmap, "sci")
    session_ms = _ms(bmap, "session_events") + _ms(bmap, "yield_capture") + _ms(bmap, "live_apply_queue")
    obs_req = _ms(bmap, "observer_request")
    persist = _ms(bmap, "checkpoint")
    throttle = _ms(bmap, "throttle")
    una = float(snap.get("tick_unattributed_self_ms_per_tick") or 0.0)
    wall_mean = float(snap.get("mean_ms_per_tick") or 0.0)

    summary = {
        "run_id": run_id,
        "restore": restore,
        "start_tick": start_tick,
        "end_tick": end_tick,
        "measured_ticks": measured,
        "profiler_ticks": snap.get("ticks"),
        "live_wall": {
            "mean_ms_per_tick": snap.get("mean_ms_per_tick"),
            "p50_ms_per_tick": snap.get("p50_ms_per_tick"),
            "p95_ms_per_tick": snap.get("p95_ms_per_tick"),
            "max_ms_per_tick": snap.get("max_ms_per_tick"),
            "last_tick_wall_ms": snap.get("last_tick_wall_ms"),
        },
        "accounted_wall_time_percent": snap.get("accounted_wall_time_percent"),
        "top_level_exclusive_ms_per_tick": {
            "simulation_core": sim_ms,
            "scientific_capture": sci_ms,
            "observer_request": obs_req,
            "persistence": persist,
            "session_other": session_ms + throttle,
            "unattributed": una,
            "experimenter_pre": _ms(bmap, "experimenter_pre"),
            "experimenter_post": _ms(bmap, "experimenter_post"),
        },
        "science": {
            "sci_v2_ms": _ms(bmap, "sci_v2"),
            "V2_build_ms": _ms(bmap, "sci_build"),
            "V2_serialize_ms": _ms(bmap, "sci_serialize"),
            "V2_write_ms": _ms(bmap, "sci_write"),
            "sci_v3_ms": _ms(bmap, "sci_v3"),
            "V3_build_ms": _ms(bmap, "sci_v3_capture"),
            "V3_serialize_ms": _ms(bmap, "sci_v3_serialize"),
            "V3_write_ms": _ms(bmap, "sci_v3_write"),
            "sci_vision_optical_ms": _ms(bmap, "sci_vision_optical"),
            "counters": snap.get("counters") or {},
        },
        "cognition": {
            "total_ms_per_tick": _ms(bmap, "cognition"),
            "self_ms_per_tick": _ms(bmap, "cognition", "self_ms_per_tick"),
            "hotspots": cog_rows[:16],
        },
        "observer_async": {
            "observer_frame_ms": _ms(bmap, "observer_frame"),
            "observer_serialize_ms": _ms(bmap, "observer_serialize"),
            "observer_publish_ms": _ms(bmap, "observer_publish"),
            "observer_eye_ms": _ms(bmap, "observer_eye"),
            "eye": snap.get("eye"),
            "capture": snap.get("capture"),
        },
        "vision_ms": _ms(bmap, "vis_sample") + _ms(bmap, "vis_spatial") + _ms(bmap, "vis_assemble"),
        "cold_ms": _ms(bmap, "cold_seal") + _ms(bmap, "cold_evict") + _ms(bmap, "cold_disk_write"),
        "slow_ticks": snap.get("slow_ticks") or [],
        "sci_files": sci_files,
        "tick0_before_restore": tick0,
        "start_meta": start_meta,
        "tp_before_play_ticks": (tp_before or {}).get("ticks"),
    }
    (OUT / "live_profile_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    write_csv(OUT / "live_hotpaths.csv", buckets_sorted)
    write_csv(OUT / "cognition_hotpaths.csv", cog_rows)
    write_csv(OUT / "slow_ticks.csv", summary["slow_ticks"] or [{"tick": "", "total_ms": ""}])
    windows = snap.get("windows") or []
    write_csv(OUT / "live_profile_windows.csv", windows or [{"n": 0}])

    overhead = overhead_fixture()
    (OUT / "profiler_overhead.json").write_text(json.dumps(overhead, indent=2))

    committed = load_committed(CK_LIVE)
    ablation = {"skipped": True, "reason": "no committed checkpoint"}
    if committed:
        payload = load_snapshot_dict(committed)
        ablation = sci_ablation(payload)
    (OUT / "sci_ablation.json").write_text(json.dumps(ablation, indent=2, default=str))

    print(json.dumps({
        "run_id": run_id,
        "start_tick": start_tick,
        "end_tick": end_tick,
        "measured": measured,
        "mean_ms": snap.get("mean_ms_per_tick"),
        "accounted": snap.get("accounted_wall_time_percent"),
        "sim_ms": sim_ms,
        "sci_ms": sci_ms,
        "cognition_ms": _ms(bmap, "cognition"),
        "overhead_percent": overhead.get("overhead_percent"),
        "ablation_delta_ms": ablation.get("delta_mean_ms") if isinstance(ablation, dict) else None,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
