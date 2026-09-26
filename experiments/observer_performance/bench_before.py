#!/usr/bin/env python3
"""BEFORE Observer performance benchmark (demand-driven UI work)."""
from __future__ import annotations
import json, os, time, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig
from mechanistic_mind.ui.psy_observer_web.serialize import live_frame

SEED, WARMUP, N = 733, 20, 60
OUT = ROOT / "results" / "observer_performance"
OUT.mkdir(parents=True, exist_ok=True)

def pct(xs, p):
    if not xs:
        return None
    s = sorted(xs)
    return s[min(len(s) - 1, max(0, int(round((p / 100) * (len(s) - 1)))))]

def stats(ms):
    if not ms:
        return {}
    mean = sum(ms) / len(ms)
    return {
        "n": len(ms),
        "p50_ms": pct(ms, 50),
        "p90_ms": pct(ms, 90),
        "mean_ms": mean,
        "ticks_per_sec": 1000.0 / mean if mean else None,
    }

def main():
    rows = []
    rt = PhysicalSystemRuntime(seed=SEED)
    for _ in range(WARMUP):
        rt.step()
    ms = []
    t0 = time.perf_counter()
    for _ in range(N):
        a = time.perf_counter(); rt.step(); ms.append((time.perf_counter() - a) * 1000)
    rows.append({"mode": "A_headless_runtime", **stats(ms), "wall_ms": (time.perf_counter() - t0) * 1000, "payload_bytes_p50": 0})
    print("A done", rows[-1]["p50_ms"], flush=True)

    s = ObserverSession(SessionConfig(seed=SEED, execution_mode="HEADLESS", evidence_mode="SEARCH_COMPACT"))
    if hasattr(s, "set_execution_mode"):
        try:
            s.set_execution_mode("HEADLESS")
        except Exception as e:
            print("set_execution_mode", e, flush=True)
    for _ in range(WARMUP):
        s.step()
    ms = []
    t0 = time.perf_counter()
    for _ in range(N):
        a = time.perf_counter(); s.step(); ms.append((time.perf_counter() - a) * 1000)
    rows.append({"mode": "B_session_headless_search_compact", **stats(ms), "wall_ms": (time.perf_counter() - t0) * 1000})
    print("B done", rows[-1]["p50_ms"], flush=True)

    def bench_capture(label, detail, sample_json_every=5):
        sess = ObserverSession(SessionConfig(seed=SEED, evidence_mode="SEARCH_COMPACT"))
        sess.status = "PAUSED"
        for _ in range(WARMUP):
            sess.step()
        ms_step, ms_build, ms_ser, sizes = [], [], [], []
        t0 = time.perf_counter()
        for i in range(N):
            a = time.perf_counter(); sess.step(); ms_step.append((time.perf_counter() - a) * 1000)
            b = time.perf_counter()
            frame = sess._capture_locked(detail=detail, serialize=False)
            ms_build.append((time.perf_counter() - b) * 1000)
            if i % sample_json_every == 0:
                c = time.perf_counter()
                blob = json.dumps(frame, default=str)
                ms_ser.append((time.perf_counter() - c) * 1000)
                sizes.append(len(blob.encode("utf-8")))
        return {
            "mode": label,
            "detail": detail,
            "step": stats(ms_step),
            "frame_build": stats(ms_build),
            "json_serialize_sampled": stats(ms_ser),
            "payload_bytes_p50": pct(sizes, 50),
            "payload_bytes_p90": pct(sizes, 90),
            "wall_ms": (time.perf_counter() - t0) * 1000,
        }

    rows.append(bench_capture("D_capture_compact", "compact"))
    print("D done", rows[-1]["frame_build"].get("p50_ms"), "bytes", rows[-1]["payload_bytes_p50"], flush=True)
    rows.append(bench_capture("E_capture_full", "full", sample_json_every=10))
    print("E done", rows[-1]["frame_build"].get("p50_ms"), "bytes", rows[-1]["payload_bytes_p50"], flush=True)

    sess = ObserverSession(SessionConfig(seed=SEED, evidence_mode="SEARCH_COMPACT"))
    sess.status = "PAUSED"
    for _ in range(WARMUP):
        sess.step()
    ms = []
    t0 = time.perf_counter()
    for i in range(N):
        a = time.perf_counter()
        sess.step()
        frame = sess._capture_locked(detail="full", serialize=False)
        sess.sensorimotor_consequence_panel()
        sess.historical_sensorimotor_selection_panel()
        if i % 10 == 0:
            json.dumps(frame, default=str)
        ms.append((time.perf_counter() - a) * 1000)
    rows.append({"mode": "F_full_plus_diag_panels", **stats(ms), "wall_ms": (time.perf_counter() - t0) * 1000})
    print("F done", rows[-1]["p50_ms"], flush=True)

    sess = ObserverSession(SessionConfig(seed=SEED, evidence_mode="SEARCH_COMPACT"))
    for _ in range(30):
        sess.step()
    stages = {}
    for detail in ("compact", "full"):
        t0 = time.perf_counter()
        for _ in range(15):
            live_frame(sess.runtime, status="PAUSED", mode="LIVE", target_tick=None, previous_body=sess.runtime.body.snapshot(), detail=detail)
        stages[f"live_frame_{detail}_ms"] = (time.perf_counter() - t0) / 15 * 1000
        t0 = time.perf_counter()
        for _ in range(15):
            sess._capture_locked(detail=detail, serialize=False)
        stages[f"capture_locked_{detail}_ms"] = (time.perf_counter() - t0) / 15 * 1000
    print("stages", stages, flush=True)

    out = {"seed": SEED, "warmup": WARMUP, "n": N, "rows": rows, "stages": stages}
    (OUT / "before_benchmark.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    main()
