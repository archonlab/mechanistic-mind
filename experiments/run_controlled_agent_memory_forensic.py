#!/usr/bin/env python3
"""Bounded spawn/remove memory forensic. Does not approach historical ~15 GB OOM.

Abort if RSS exceeds baseline + CEILING_MB. GIT_PUSH=NO. No runtime semantics changes.
"""
from __future__ import annotations

import gc
import json
import os
import resource
import sys
import time
from pathlib import Path
from typing import Any

CEILING_OVER_BASELINE_MB = 800.0
ABORT_PER_CYCLE_MB = 40.0
WARMUP_CYCLES = 2

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.ui.psy_observer_web.experimenter_control import (
    ExperimenterController,
    promote_physical_to_two_agent_host,
    remove_experimenter_body,
    spawn_experimenter_body,
)
from mechanistic_mind.ui.psy_observer_web.session import FULL_PUBLIC_FRAME_RETAIN, ObserverSession, SessionConfig


def _rss_mb() -> float:
    try:
        with open("/proc/self/status", encoding="utf-8") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024.0
    except OSError:
        pass
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def _heap_mb() -> float | None:
    try:
        import tracemalloc

        if tracemalloc.is_tracing():
            cur, _peak = tracemalloc.get_traced_memory()
            return cur / (1024.0 * 1024.0)
    except Exception:
        return None
    return None


def _malloc_trim() -> bool:
    try:
        import ctypes

        libc = ctypes.CDLL("libc.so.6")
        return bool(libc.malloc_trim(0))
    except Exception:
        return False


def _count_psr() -> int:
    gc.collect()
    return sum(1 for o in gc.get_objects() if type(o).__name__ == "PhysicalSystemRuntime")


def _cog_ids(rt: Any) -> list[int]:
    slots = getattr(rt, "slots", None)
    if slots:
        return [id(s.cognition) for s in slots]
    cog = getattr(rt, "cognition", None)
    return [id(cog)] if cog is not None else []


def _n_agents(rt: Any) -> int:
    if hasattr(rt, "slots"):
        return len(rt.slots)
    return 1 if rt is not None else 0


def _snap(rt: Any, extra: dict | None = None) -> dict[str, Any]:
    row = {
        "rss_mb": round(_rss_mb(), 3),
        "heap_mb": None if _heap_mb() is None else round(_heap_mb(), 3),
        "runtime_type": type(rt).__name__,
        "n_agents": _n_agents(rt),
        "experimenter_slot": getattr(rt, "experimenter_slot", None),
        "n_psr_gc": _count_psr(),
        "cog_ids": _cog_ids(rt),
        "tick": int(getattr(rt, "tick", 0) or 0),
    }
    if extra:
        row.update(extra)
    return row


def _abort(baseline: float, msg: str) -> None:
    now = _rss_mb()
    if now > baseline + CEILING_OVER_BASELINE_MB:
        raise SystemExit(f"ABORT RSS ceiling: {now:.1f} MB > baseline {baseline:.1f} + {CEILING_OVER_BASELINE_MB} ({msg})")


def _cycle_two_agent(rt: TwoAgentRuntime, *, ticks: int = 3) -> None:
    ctrl = ExperimenterController()
    out = spawn_experimenter_body(rt, x=10.0, y=10.0, controller=ctrl)
    assert out.get("accepted"), out
    for _ in range(ticks):
        rt.step()
    rem = remove_experimenter_body(rt, ctrl)
    assert rem.get("accepted"), rem
    for _ in range(ticks):
        rt.step()


def run_cycles(n: int, *, ticks: int = 3) -> dict[str, Any]:
    gc.collect()
    baseline = _rss_mb()
    rt = TwoAgentRuntime(seed=17, signal_enabled=False)
    rt.step(2)
    cog0 = tuple(_cog_ids(rt))
    n0 = len(rt.slots)
    psr0 = _count_psr()
    after_spawn = None
    rss_series = [baseline]
    samples = []
    for i in range(n):
        _abort(baseline, f"cycle {i} start")
        spawn = ExperimenterController()
        out = spawn_experimenter_body(rt, x=10.0 + (i % 3), y=10.0, controller=spawn)
        assert out["accepted"]
        assert len(rt.slots) == n0 + 1
        if i == 0:
            after_spawn = _rss_mb()
        for _ in range(ticks):
            rt.step()
        rem = remove_experimenter_body(rt, spawn)
        assert rem["accepted"]
        assert len(rt.slots) == n0
        assert rt.experimenter_slot is None
        for _ in range(ticks):
            rt.step()
        gc.collect()
        rss = _rss_mb()
        rss_series.append(rss)
        samples.append({"cycle": i + 1, "rss_mb": round(rss, 3), "n_psr": _count_psr(), "n_agents": len(rt.slots)})
        if i + 1 > WARMUP_CYCLES:
            d = rss - rss_series[WARMUP_CYCLES]
            per = d / max(1, (i + 1 - WARMUP_CYCLES))
            if per > ABORT_PER_CYCLE_MB:
                raise SystemExit(f"ABORT per-cycle RSS {per:.2f} MB at cycle {i+1}")
        _abort(baseline, f"cycle {i} end")
    gc.collect()
    _malloc_trim()
    gc.collect()
    final = _rss_mb()
    after_remove_last = samples[-1]["rss_mb"] if samples else final
    post_warm = rss_series[WARMUP_CYCLES:] if len(rss_series) > WARMUP_CYCLES else rss_series
    delta = 0.0
    if len(post_warm) >= 2:
        delta = (post_warm[-1] - post_warm[0]) / max(1, len(post_warm) - 1)
    cog1 = tuple(_cog_ids(rt))
    psr1 = _count_psr()
    cls = "STABLE"
    if psr1 > psr0 + 1 or cog1 != cog0:
        cls = "TRUE_OBJECT_RETENTION"
    elif delta > 2.0:
        cls = "ALLOCATOR_RETENTION"
    elif delta > 8.0:
        cls = "RUNAWAY_ALLOCATION"
    return {
        "n_cycles": n,
        "baseline_rss_mb": round(baseline, 3),
        "rss_after_spawn_mb": None if after_spawn is None else round(after_spawn, 3),
        "rss_after_remove_mb": after_remove_last,
        "rss_final_mb": round(final, 3),
        "rss_delta_per_cycle_mb": round(delta, 4),
        "classification": cls,
        "duplicate_cognition": cog1 != cog0,
        "cog_ids_start": list(cog0),
        "cog_ids_end": list(cog1),
        "n_psr_start": psr0,
        "n_psr_end": psr1,
        "n_agents_end": len(rt.slots),
        "runtime_type_end": type(rt).__name__,
        "samples": samples[-8:],
    }


def run_promotion_cases() -> dict[str, Any]:
    out: dict[str, Any] = {}
    # A: single → spawn → TwoAgent → remove (intentionally remains TwoAgentRuntime)
    gc.collect()
    psr = PhysicalSystemRuntime(seed=41)
    psr.step(3)
    cog = id(psr.cognition)
    body = id(psr.body)
    host = promote_physical_to_two_agent_host(psr)
    assert host.slots[0] is psr
    assert id(host.slots[0].cognition) == cog
    ctrl = ExperimenterController()
    spawn_experimenter_body(host, x=8.0, y=8.0, controller=ctrl)
    assert len(host.slots) == 2
    remove_experimenter_body(host, ctrl)
    out["A"] = {
        "runtime_after_remove": type(host).__name__,
        "n_slots": len(host.slots),
        "same_cognition": id(host.slots[0].cognition) == cog,
        "same_body": id(host.slots[0].body) == body,
        "demotes": False,
        "note": "Removal leaves TwoAgentRuntime host by design.",
    }
    # C: spawn remove spawn
    rt = TwoAgentRuntime(seed=7)
    c1, c2 = ExperimenterController(), ExperimenterController()
    spawn_experimenter_body(rt, x=9, y=9, controller=c1)
    remove_experimenter_body(rt, c1)
    spawn_experimenter_body(rt, x=9, y=9, controller=c2)
    out["C"] = {"n_slots_second_spawn": len(rt.slots), "slot": rt.experimenter_slot}
    remove_experimenter_body(rt, c2)
    # D: spawn 100 ticks remove
    rt = TwoAgentRuntime(seed=8)
    c = ExperimenterController()
    spawn_experimenter_body(rt, x=9, y=9, controller=c)
    rt.step(100)
    remove_experimenter_body(rt, c)
    out["D"] = {"n_slots": len(rt.slots), "tick": rt.tick, "psr": _count_psr()}
    return out


def run_observer_cycles(n: int, *, eye: bool = False, sci: bool = False) -> dict[str, Any]:
    gc.collect()
    baseline = _rss_mb()
    mode = "LIVE" if eye else "HEADLESS"
    sess = ObserverSession(SessionConfig(seed=17, cognition_enabled=True, execution_mode=mode))
    exp = {
        "seed": 17,
        "agent_count": 2,
        "cognition_enabled": True,
        "world": {"width": 16, "height": 16, "boundary_mode": "WRAP_PERIODIC"},
        "mechanisms": {"cognition_enabled": True, "predictive_equivalence": True},
    }
    if sci:
        exp["mechanisms"]["scientific_v3"] = True
    sess.apply_experiment(exp)
    if eye:
        sess.set_tiktaalik_eye(rate="PER_TICK", fpv=True)
    builds0 = sess.observer_publication_stats().get("live_frame_builds", 0)
    rt0 = sess.runtime
    cog0 = tuple(_cog_ids(rt0))
    n0 = _n_agents(rt0)
    rss_after_spawn = None
    series = []
    for i in range(n):
        _abort(baseline, f"obs cycle {i}")
        sp = sess.experimenter_spawn(x=10.0, y=10.0)
        assert sp.get("accepted"), sp
        if i == 0:
            rss_after_spawn = _rss_mb()
        sess.step(4)
        if eye:
            sess.experimenter_command(kind="ACTION", action="MOVE:E")
            sess.step(2)
        rem = sess.experimenter_remove()
        assert rem.get("accepted"), rem
        sess.step(3)
        gc.collect()
        series.append(_rss_mb())
        assert _n_agents(sess.runtime) == n0
        assert getattr(sess.runtime, "experimenter_slot", None) is None
        assert len(sess._buffer) <= FULL_PUBLIC_FRAME_RETAIN
    gc.collect()
    _malloc_trim()
    stats = sess.observer_publication_stats()
    delta = 0.0
    if len(series) > WARMUP_CYCLES + 1:
        delta = (series[-1] - series[WARMUP_CYCLES]) / max(1, len(series) - 1 - WARMUP_CYCLES)
    return {
        "n": n,
        "eye": eye,
        "sci": sci,
        "baseline_rss_mb": round(baseline, 3),
        "rss_after_spawn_mb": None if rss_after_spawn is None else round(rss_after_spawn, 3),
        "rss_after_cycles_mb": round(series[-1], 3) if series else None,
        "rss_delta_per_cycle_mb": round(delta, 4),
        "full_frames_retained": len(sess._buffer),
        "full_frame_cap": FULL_PUBLIC_FRAME_RETAIN,
        "live_frame_builds_delta": int(stats.get("live_frame_builds", 0) - builds0),
        "same_autonomous_cognition": tuple(_cog_ids(sess.runtime))[:n0] == cog0[:n0]
        if len(_cog_ids(sess.runtime)) >= n0
        else False,
        "runtime_type": type(sess.runtime).__name__,
        "n_agents": _n_agents(sess.runtime),
        "n_psr": _count_psr(),
        "eye_prev_fpv_keys": list((sess._eye_prev_fpv or {}).keys()),
        "controller_active": bool(getattr(sess._experimenter, "active", False)),
        "s0_snapshot_held": sess._experimenter.s0_snapshot is not None,
        "captures": len(sess._experimenter.captures),
        "event_log": len(sess._experimenter.event_log),
        "scripted_commands": len(sess._experimenter.scripted_commands),
    }


def main() -> int:
    t0 = time.perf_counter()
    try:
        import tracemalloc

        tracemalloc.start()
    except Exception:
        pass
    gc.collect()
    report: dict[str, Any] = {
        "schema": "mm.controlled_agent_memory_forensic.v1",
        "ceiling_over_baseline_mb": CEILING_OVER_BASELINE_MB,
        "historical_oom_note": (
            "PID 269596 2026-09-23 06:52 python anon-rss 15.4GB was Analyzer JSONL load "
            "(docs/BETA3_LONG_RUN_ANALYZER_FAILURE.md); not identified as spawn/remove."
        ),
    }
    report["cycles_10"] = run_cycles(10)
    report["cycles_50"] = run_cycles(50)
    report["promotion"] = run_promotion_cases()
    report["observer_headless_10"] = run_observer_cycles(10, eye=False)
    report["observer_eye_5"] = run_observer_cycles(5, eye=True)
    report["elapsed_s"] = round(time.perf_counter() - t0, 3)
    out_dir = ROOT / "results" / "controlled_agent_memory_forensic"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "summary.json"
    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: report[k] for k in report if k != "promotion"}, indent=2, default=str))
    print("wrote", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
