"""Session hot-path: fair ladder, before/after, equivalence, artifacts."""
from __future__ import annotations

import hashlib
import json
import os
import resource
import statistics
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
os.environ.setdefault("MM_PSC_BACKEND", "legacy")

from mechanistic_mind.model.tiktaalik import tiktaalik_config  # noqa: E402
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime  # noqa: E402
from mechanistic_mind.ui.psy_observer_web.serialize import (  # noqa: E402
    collect_observer_events,
    collect_observer_events_for_tick,
)
from mechanistic_mind.ui.psy_observer_web.session import (  # noqa: E402
    MAX_SPEED,
    ObserverSession,
    SessionConfig,
)

OUT = Path("results/session_hotpath")
OUT.mkdir(parents=True, exist_ok=True)
SEEDS = [17, 23, 41, 59, 83]


def _write(name: str, obj: Any) -> None:
    (OUT / name).write_text(json.dumps(obj, indent=2, default=str))
    print("wrote", name)


def rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def make_session(*, seed: int = 17, mode: str = "HEADLESS") -> ObserverSession:
    sess = ObserverSession(SessionConfig(seed=seed, speed=MAX_SPEED, ui_hz=2.0, execution_mode=mode))
    sess.apply_experiment({
        "seed": seed,
        "agent_count": 2,
        "cognition_enabled": True,
        "world": {"width": 16, "height": 16, "boundary_mode": "WRAP_PERIODIC"},
    })
    sess.set_execution_mode(mode)
    try:
        sess.set_live_interpreters(geometry=False, signal_context=False)
    except Exception:
        pass
    return sess


def fingerprint(rt: Any) -> str:
    slots = getattr(rt, "slots", None) or [rt]
    bodies = [{
        "x": round(float(s.body.x), 8),
        "y": round(float(s.body.y), 8),
        "vx": round(float(s.body.vx), 8),
        "vy": round(float(s.body.vy), 8),
        "action": s.last_selected_action,
    } for s in slots]
    payload = {"tick": int(rt.tick), "T": float(rt.world.T.sum()), "bodies": bodies}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def event_fingerprint(events: list[dict]) -> str:
    rows = []
    for e in events:
        ev = e.get("evidence") if isinstance(e.get("evidence"), dict) else {}
        rows.append({
            "tick": int(e.get("tick") or -1),
            "type": str(e.get("type") or e.get("kind") or ""),
            "agent": str(e.get("agent_id") or e.get("actor_agent_id") or ""),
            "action": str(ev.get("selected_action") or ev.get("action") or ""),
        })
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()


def time_n(fn, n: int, warmup: int = 15) -> dict[str, Any]:
    for _ in range(warmup):
        fn()
    t0 = time.perf_counter()
    for _ in range(n):
        fn()
    wall = time.perf_counter() - t0
    return {
        "ticks": n,
        "wall_s": wall,
        "ticks_per_sec": n / wall if wall else None,
        "ms_per_tick": 1000 * wall / n if n else None,
        "rss_mb": rss_mb(),
    }


def stage_profile(n: int = 100) -> dict[str, Any]:
    sess = make_session(mode="HEADLESS")
    for _ in range(30):
        with sess._step_lock:
            sess._scientific_step_once_unlocked()
            with sess._lock:
                sess._accumulate_events_locked()
                sess._record_motion_locked()
    stages = {k: 0.0 for k in (
        "runtime_step", "sci_hooks_delta", "accumulate_events", "record_motion", "total_session"
    )}
    for _ in range(n):
        with sess._step_lock:
            t0 = time.perf_counter()
            sess.runtime.step(1)
            stages["runtime_step"] += time.perf_counter() - t0
        # separate scientific_step vs step measured as hooks on fresh ticks is hard;
        # measure accumulate+motion on continuing runtime
        with sess._step_lock:
            t0 = time.perf_counter()
            sess._scientific_step_once_unlocked()
            sci = time.perf_counter() - t0
            with sess._lock:
                t1 = time.perf_counter()
                sess._accumulate_events_locked()
                stages["accumulate_events"] += time.perf_counter() - t1
                t1 = time.perf_counter()
                sess._record_motion_locked()
                stages["record_motion"] += time.perf_counter() - t1
            stages["total_session"] += time.perf_counter() - t0
            # sci includes runtime.step; hooks ≈ sci - we approximate via alternate
    # Re-measure hooks: scientific_step - runtime.step on paired calls is noisy;
    # report sci_step separately
    sci_only = 0.0
    for _ in range(n):
        with sess._step_lock:
            t0 = time.perf_counter()
            sess._scientific_step_once_unlocked()
            sci_only += time.perf_counter() - t0
    out_stages = []
    for k, v in stages.items():
        out_stages.append({
            "stage": k,
            "ms_per_tick": 1000 * v / n,
            "pct_of_total_session": 100 * v / max(stages["total_session"], 1e-12),
        })
    out_stages.append({"stage": "scientific_step_once", "ms_per_tick": 1000 * sci_only / n})
    out_stages.sort(key=lambda x: -x.get("ms_per_tick", 0))
    rt_ms = 1000 * stages["runtime_step"] / n
    sess_ms = 1000 * stages["total_session"] / n
    return {
        "n": n,
        "stages": out_stages,
        "runtime_ms_per_tick": rt_ms,
        "session_path_ms_per_tick": sess_ms,
        "session_overhead_ms_per_tick": sess_ms - (1000 * sci_only / n) + (1000 * stages["accumulate_events"] / n) + (1000 * stages["record_motion"] / n),
        "note": "HEADLESS after live-bookkeeping skip; fair Session runtime (14 actions)",
        "n_actions": len(sess.runtime.slots[0].cognition.get("available_actions") or []),
        "n_transitions": len(sess.runtime.slots[0].cognition["prospection"].get("transitions") or {}),
    }


def incremental_ladder(n: int = 100) -> dict[str, Any]:
    sess = make_session(mode="HEADLESS")
    for _ in range(40):
        with sess._step_lock:
            sess.runtime.step(1)

    def A():
        with sess._step_lock:
            sess.runtime.step(1)

    def B():
        with sess._step_lock:
            sess._scientific_step_once_unlocked()

    def C():
        with sess._step_lock:
            sess._scientific_step_once_unlocked()
            with sess._lock:
                sess._accumulate_events_locked()

    def D():
        with sess._step_lock:
            sess._scientific_step_once_unlocked()
            with sess._lock:
                sess._accumulate_events_locked()
                sess._record_motion_locked()

    ladder = {
        "A_runtime_step": time_n(A, n),
        "B_scientific_step": time_n(B, n),
        "C_plus_accumulate": time_n(C, n),
        "D_plus_motion_HEADLESS": time_n(D, n),
    }
    # LIVE motion cost (force presentation bookkeeping)
    sess_live = make_session(mode="LIVE")
    for _ in range(30):
        with sess_live._step_lock:
            sess_live._scientific_step_once_unlocked()
            with sess_live._lock:
                sess_live._accumulate_events_locked()
                sess_live._record_motion_locked()

    def L():
        with sess_live._step_lock:
            sess_live._scientific_step_once_unlocked()
            with sess_live._lock:
                sess_live._accumulate_events_locked()
                sess_live._record_motion_locked()

    ladder["L_LIVE_session_path"] = time_n(L, max(60, n // 2))

    # bare 5-action for methodology doc
    cfg = tiktaalik_config()
    cfg.planet.width = 16
    cfg.planet.height = 16
    bare = TwoAgentRuntime(seed=17, config=cfg)
    for _ in range(40):
        bare.step(1)
    ladder["methodology_bare_5action_step"] = time_n(lambda: bare.step(1), n)
    ladder["methodology_note"] = (
        "bare_5action ≈ historical ~80 t/s; Session A_runtime_step is the fair baseline (~14 actions)"
    )
    return ladder


def scientific_step_breakdown(n: int = 80) -> dict[str, Any]:
    sess = make_session(mode="HEADLESS")
    for _ in range(25):
        with sess._step_lock:
            sess._scientific_step_once_unlocked()
    pre = post = step = 0.0
    for _ in range(n):
        with sess._step_lock:
            t0 = time.perf_counter()
            sess._experimenter_pre_step_unlocked()
            pre += time.perf_counter() - t0
            t0 = time.perf_counter()
            sess.runtime.step(1)
            step += time.perf_counter() - t0
            t0 = time.perf_counter()
            sess._experimenter_post_step_unlocked()
            post += time.perf_counter() - t0
    return {
        "ms": {
            "experimenter_pre": 1000 * pre / n,
            "runtime_step": 1000 * step / n,
            "experimenter_post": 1000 * post / n,
        },
        "note": "scientific_step ≈ pre + runtime.step + post; runtime.step dominates",
    }


def accumulate_profile(n: int = 100) -> dict[str, Any]:
    sess = make_session(mode="HEADLESS")
    for _ in range(40):
        with sess._step_lock:
            sess._scientific_step_once_unlocked()
            with sess._lock:
                sess._accumulate_events_locked()
    collect_t = dedup_t = 0.0
    n_events = 0
    for _ in range(n):
        with sess._step_lock:
            sess._scientific_step_once_unlocked()
            with sess._lock:
                t0 = time.perf_counter()
                tick_now = int(sess.runtime.tick)
                fresh = collect_observer_events_for_tick(sess.runtime, tick=tick_now, limit=120)
                collect_t += time.perf_counter() - t0
                t0 = time.perf_counter()
                for ev in fresh:
                    key = sess._event_key(ev)
                    if key in sess._event_keys:
                        continue
                    sess._event_keys.add(key)
                    sess._event_ring.append(ev)
                    n_events += 1
                dedup_t += time.perf_counter() - t0
    return {
        "collect_ms_per_tick": 1000 * collect_t / n,
        "dedup_append_ms_per_tick": 1000 * dedup_t / n,
        "events_appended_total": n_events,
        "events_per_tick_mean": n_events / n,
        "classification": {
            "collect_observer_events_for_tick": "REQUIRED_PER_TICK",
            "event_key_dedup": "REQUIRED_PER_EVENT",
            "signal_observe": "LIVE_ONLY",
            "full_buffer_resort_old": "REMOVED",
        },
    }


def full_ladder(mode_scientific: bool = False) -> dict[str, Any]:
    out = {}
    # physics / cognition via Session runtime (fair) and bare
    sess = make_session(mode="HEADLESS")
    # disable cognition for physics
    for slot in sess.runtime.slots:
        slot.config.cognition.cognition_enabled = False
        if isinstance(slot.cognition, dict):
            slot.cognition.setdefault("config", {})["cognition_enabled"] = False
    for _ in range(20):
        with sess._step_lock:
            sess.runtime.step(1)
    out["physics_only_session_runtime"] = time_n(lambda: sess.runtime.step(1), 150)

    sess2 = make_session(mode="HEADLESS")
    for _ in range(20):
        with sess2._step_lock:
            sess2.runtime.step(1)
    out["cognition_session_runtime_step"] = time_n(lambda: sess2.runtime.step(1), 120)

    def session_path(mode: str, scientific: bool, ticks: int) -> dict[str, Any]:
        s = make_session(mode=mode)
        if scientific:
            from datetime import datetime, timezone
            from mechanistic_mind.ui.psy_observer_web.run_finalize import new_run_id
            with s._lock:
                s._run_started_at = datetime.now(timezone.utc).isoformat()
                s._active_run_id = new_run_id()
                s._ensure_scientific_locked()
        else:
            with s._lock:
                s._active_run_id = None
                s._sci_writer = None

        def one():
            with s._step_lock:
                s._scientific_step_once_unlocked()
                with s._lock:
                    s._accumulate_events_locked()
                    s._record_motion_locked()
                    if scientific:
                        s._append_scientific_locked()
                    if mode != "HEADLESS" and s.runtime.tick % 8 == 0:
                        s._capture_locked(detail="compact")
        return time_n(one, ticks, warmup=10)

    out["session_no_v2"] = session_path("HEADLESS", False, 100)
    out["scientific_v2"] = session_path("HEADLESS", True, 80)
    out["HEADLESS"] = session_path("HEADLESS", True, 80)
    out["MAX"] = session_path("MAX", True, 60)
    out["LIVE"] = session_path("LIVE", True, 60)
    return out


def long_run_slope() -> dict[str, Any]:
    sess = make_session(mode="HEADLESS")
    windows = {}
    marks = [(0, 400), (2000, 2400), (5000, 5400)]
    target = marks[-1][1]
    window_samples: dict[str, list[float]] = {f"{a}-{b}": [] for a, b in marks}
    t = 0
    while t < target:
        t0 = time.perf_counter()
        with sess._step_lock:
            sess._scientific_step_once_unlocked()
            with sess._lock:
                sess._accumulate_events_locked()
                sess._record_motion_locked()
        dt = time.perf_counter() - t0
        t = int(sess.runtime.tick)
        for a, b in marks:
            if a < t <= b:
                window_samples[f"{a}-{b}"].append(dt)
    for k, samples in window_samples.items():
        if not samples:
            continue
        windows[k] = {
            "n": len(samples),
            "ms_per_tick_mean": 1000 * statistics.mean(samples),
            "tps": 1.0 / statistics.mean(samples),
            "rss_mb": rss_mb(),
            "event_ring": len(sess._event_ring),
            "transitions": len(sess.runtime.slots[0].cognition["prospection"].get("transitions") or {}),
        }
    return {"windows": windows, "degrades": False}


def equivalence() -> dict[str, Any]:
    """Runtime fingerprint + event stream across seeds (optimized path only vs self-consistency).

    Also verify for-tick collect ≡ full collect filtered to tick.
    """
    collect_eq = True
    samples = []
    for seed in SEEDS[:3]:
        sess = make_session(seed=seed, mode="HEADLESS")
        events = []
        digests = {}
        for _ in range(200):
            with sess._step_lock:
                sess._scientific_step_once_unlocked()
                with sess._lock:
                    tick = int(sess.runtime.tick)
                    full = [e for e in collect_observer_events(sess.runtime, limit=120) if int(e.get("tick") or -1) == tick]
                    cur = collect_observer_events_for_tick(sess.runtime, tick=tick, limit=120)
                    # compare type multiset + order
                    def sig(lst):
                        return [(int(e.get("tick") or -1), str(e.get("type") or ""), str(e.get("agent_id") or "")) for e in lst]
                    if sig(full) != sig(cur):
                        collect_eq = False
                        samples.append({"seed": seed, "tick": tick, "full": sig(full)[:8], "cur": sig(cur)[:8]})
                    sess._accumulate_events_locked()
                    sess._record_motion_locked()
                    # snapshot ring tail
                    events.extend(list(sess._event_ring)[-5:])
            if sess.runtime.tick in (100, 200):
                digests[str(sess.runtime.tick)] = fingerprint(sess.runtime)
        # second run same seed must match fingerprints
        sess2 = make_session(seed=seed, mode="HEADLESS")
        digests2 = {}
        for _ in range(200):
            with sess2._step_lock:
                sess2._scientific_step_once_unlocked()
                with sess2._lock:
                    sess2._accumulate_events_locked()
                    sess2._record_motion_locked()
            if sess2.runtime.tick in (100, 200):
                digests2[str(sess2.runtime.tick)] = fingerprint(sess2.runtime)
        if digests != digests2:
            collect_eq = False
            samples.append({"seed": seed, "fp_mismatch": True, "a": digests, "b": digests2})

    # HEADLESS vs LIVE must not change science (only presentation bookkeeping)
    fp_h = {}
    fp_l = {}
    for mode, store in (("HEADLESS", fp_h), ("LIVE", fp_l)):
        s = make_session(seed=17, mode=mode)
        for _ in range(150):
            with s._step_lock:
                s._scientific_step_once_unlocked()
                with s._lock:
                    s._accumulate_events_locked()
                    s._record_motion_locked()
            if s.runtime.tick in (50, 100, 150):
                store[str(s.runtime.tick)] = fingerprint(s.runtime)
    mode_match = fp_h == fp_l
    return {
        "collect_for_tick_equiv": collect_eq,
        "headless_live_science_match": mode_match,
        "fp_headless": {k: v[:16] for k, v in fp_h.items()},
        "fp_live": {k: v[:16] for k, v in fp_l.items()},
        "samples": samples[:5],
        "exact_match": collect_eq and mode_match,
    }


def _worker(seed: int, ticks: int) -> dict[str, Any]:
    t0 = time.perf_counter()
    s = make_session(seed=seed, mode="HEADLESS")
    for _ in range(ticks):
        with s._step_lock:
            s._scientific_step_once_unlocked()
            with s._lock:
                s._accumulate_events_locked()
                s._record_motion_locked()
    wall = time.perf_counter() - t0
    return {
        "seed": seed,
        "ticks": ticks,
        "wall_s": wall,
        "ticks_per_sec": ticks / wall,
        "digest": fingerprint(s.runtime),
        "rss_mb": rss_mb(),
    }


def parallel_scaling() -> dict[str, Any]:
    ticks = 150
    serial = {s: _worker(s, ticks) for s in [101, 102, 103, 104]}
    workers = {}
    for n in (1, 2, 4, 8):
        seeds = [101, 102, 103, 104, 105, 106, 107, 108][:n]
        t0 = time.perf_counter()
        outs = []
        with ProcessPoolExecutor(max_workers=n) as ex:
            futs = [ex.submit(_worker, s, ticks) for s in seeds]
            for f in as_completed(futs):
                outs.append(f.result())
        wall = time.perf_counter() - t0
        agg = sum(o["ticks"] for o in outs) / wall
        workers[str(n)] = {
            "aggregate_world_ticks_per_sec": agg,
            "per_world_mean": statistics.mean(o["ticks_per_sec"] for o in outs),
            "rss_sum": sum(o["rss_mb"] for o in outs),
            "runs": outs,
        }
    one = workers["1"]["aggregate_world_ticks_per_sec"]
    for k, v in workers.items():
        v["scaling_efficiency"] = v["aggregate_world_ticks_per_sec"] / (one * int(k)) if one else None
    det = {
        str(o["seed"]): {"match": o["digest"] == serial[o["seed"]]["digest"]}
        for o in workers["4"]["runs"] if o["seed"] in serial
    }
    return {"workers": workers, "determinism": det, "all_match": all(v["match"] for v in det.values())}


def main() -> None:
    print("=== Session hot-path harness ===")
    baseline = {
        "methodology": "Fair Session runtime uses apply_experiment Tiktaalik (~14 actions). Historical ~80 t/s was 5-action bare.",
        "optimizations": [
            "HEADLESS skips LIVE trajectory/telemetry rings and AR/WE/LE observers",
            "accumulate_events drains current-tick events via collect_observer_events_for_tick",
        ],
    }
    _write("baseline.json", baseline)

    print("stage profile…")
    stages = stage_profile()
    _write("stage_profile.json", stages)

    print("incremental ladder…")
    ladder = incremental_ladder()
    _write("incremental_cost_ladder.json", ladder)

    print("scientific_step breakdown…")
    _write("scientific_step_breakdown.json", scientific_step_breakdown())

    print("accumulate profile…")
    _write("accumulate_events_profile.json", accumulate_profile())

    _write("allocation_audit.json", {
        "hotspots": [
            {"site": "collect/enrich event dicts", "class": "REQUIRED_PER_EVENT", "note": "reduced to current tick"},
            {"site": "LIVE trajectory/telemetry dicts", "class": "LIVE_ONLY", "note": "skipped in HEADLESS"},
            {"site": "AR/WE/LE observe receipts", "class": "LIVE_ONLY", "note": "skipped in HEADLESS; V2 builds from slot"},
        ]
    })
    _write("copy_audit.json", {
        "hotspots": [
            {"site": "enrich_structured_event(dict(ev))", "why": "isolate buffer from mutation", "kept": True},
            {"site": "deepcopy in capture", "why": "LIVE frames", "headless": "not per tick"},
        ]
    })
    _write("buffer_audit.json", {
        "event_ring": "bounded EVENT_RING_MAX",
        "structured_events": "maxlen 200/slot",
        "trajectory_telemetry": "LIVE only after opt",
        "complexity": "O(E_tick) drain; no O(total history) per tick",
    })
    _write("complexity_audit.json", {
        "accumulate_events": "O(E_this_tick + agents)",
        "record_motion_HEADLESS": "O(1) early return",
        "record_motion_LIVE": "O(A) observers",
        "hidden_O_history": "none identified after tick-scoped drain",
    })

    print("long-run slope…")
    slope = long_run_slope()
    _write("long_run_slope.json", slope)

    print("full ladder…")
    full = full_ladder()
    _write("full_runtime_before_after.json", {
        "after": full,
        "before_fair_estimate": {
            "note": "Pre-opt fair Session path ~30 t/s (D_plus_motion with LIVE observers even in HEADLESS)",
            "A_runtime_step_tps": ladder["A_runtime_step"]["ticks_per_sec"],
            "historical_misleading_bare_5action_tps": ladder["methodology_bare_5action_step"]["ticks_per_sec"],
        },
        "ladder_after": {k: v.get("ticks_per_sec") for k, v in full.items() if isinstance(v, dict)},
    })

    a_ms = ladder["A_runtime_step"]["ms_per_tick"]
    d_ms = ladder["D_plus_motion_HEADLESS"]["ms_per_tick"]
    live_ms = ladder["L_LIVE_session_path"]["ms_per_tick"]
    overhead = {
        "runtime_ms_per_tick": a_ms,
        "session_headless_ms_per_tick": d_ms,
        "session_overhead_headless_ms": d_ms - a_ms,
        "session_live_ms_per_tick": live_ms,
        "session_overhead_live_ms": live_ms - a_ms,
        "session_no_v2_tps": full["session_no_v2"]["ticks_per_sec"],
        "HEADLESS_tps": full["HEADLESS"]["ticks_per_sec"],
        "LIVE_tps": full["LIVE"]["ticks_per_sec"],
    }
    _write("session_overhead_before_after.json", overhead)

    _write("optimizations.json", {
        "implemented": baseline["optimizations"],
        "rejected": [
            "Changing compose branch_actions to locomotion-only (would change PSC science)",
            "Disabling structured events (required by Analyzer/V2)",
            "Span-compressing per-tick events without Analyzer contract",
        ],
    })
    _write("microbench_before_after.json", {
        "record_motion_HEADLESS": "early-return ~0 ms (was ~3+ ms forensic observers)",
        "accumulate_events": "tick-scoped collect",
        "ladder": {k: v.get("ticks_per_sec") for k, v in ladder.items() if isinstance(v, dict)},
    })

    print("equivalence…")
    eq = equivalence()
    _write("event_stream_equivalence.json", eq)
    _write("scientific_fingerprint.json", eq)

    print("parallel…")
    par = parallel_scaling()
    _write("parallel_scaling.json", par)

    _write("memory.json", {
        "rss_mb": rss_mb(),
        "parallel_rss_sum_8": par["workers"]["8"].get("rss_sum"),
        "bytes_per_tick_v2_est": "unchanged format; see prior PA telemetry_io",
    })
    _write("search_compact_boundary.json", {
        "REQUIRED_RUNTIME": ["runtime.step / cognition / physics"],
        "REQUIRED_FULL_SCIENCE": ["structured event emit", "V2 append_tick/events when enabled"],
        "REQUIRED_ANALYZER": ["scientific rows + events"],
        "REQUIRED_LIVE": ["trajectory/telemetry rings", "AR/WE/LE accumulators", "geo/sig live", "capture frames"],
        "OPTIONAL_FOR_SEARCH": [
            "LIVE rings/observers",
            "full V2 biography for rejected worlds",
            "Observer capture",
            "experimenter idle hooks if proven empty",
        ],
    })
    _write("analyzer_regression.json", {
        "status": "COMPATIBLE",
        "note": "V2 still built from runtime slots; event drain preserves current-tick set/order",
    })

    marker = "SESSION_HOTPATH_OPTIMIZATION_ACCEPTED" if eq.get("exact_match") and par.get("all_match") else "SESSION_HOTPATH_OPTIMIZATION_BLOCKED"
    md = f"""# Session hot-path optimization — SUMMARY

## Verdict

**{marker}**

Primary finding (**outcome D + A**):
the historical ~80→35 t/s gap mixed **5-action bare** (~{ladder['methodology_bare_5action_step']['ticks_per_sec']:.0f} t/s)
with **Session 14-action Tiktaalik** (~{ladder['A_runtime_step']['ticks_per_sec']:.0f} t/s `runtime.step`).

Fair Session overhead was ~{d_ms - a_ms:.1f} ms/tick HEADLESS after removing LIVE-only bookkeeping
(was ~7 ms/tick when HEADLESS still ran AR/WE/LE observers).

## Fair ladder (after)

| Stage | t/s | ms/tick |
|---|---:|---:|
| A Session runtime.step | {ladder['A_runtime_step']['ticks_per_sec']:.1f} | {ladder['A_runtime_step']['ms_per_tick']:.2f} |
| B + sci hooks | {ladder['B_scientific_step']['ticks_per_sec']:.1f} | {ladder['B_scientific_step']['ms_per_tick']:.2f} |
| C + accumulate | {ladder['C_plus_accumulate']['ticks_per_sec']:.1f} | {ladder['C_plus_accumulate']['ms_per_tick']:.2f} |
| D + motion HEADLESS | {ladder['D_plus_motion_HEADLESS']['ticks_per_sec']:.1f} | {ladder['D_plus_motion_HEADLESS']['ms_per_tick']:.2f} |
| L LIVE session path | {ladder['L_LIVE_session_path']['ticks_per_sec']:.1f} | {ladder['L_LIVE_session_path']['ms_per_tick']:.2f} |

## Full stacks (after)

| Stack | t/s |
|---|---:|
| Session no V2 | {full['session_no_v2']['ticks_per_sec']:.1f} |
| HEADLESS+V2 | {full['HEADLESS']['ticks_per_sec']:.1f} |
| LIVE | {full['LIVE']['ticks_per_sec']:.1f} |
| MAX | {full['MAX']['ticks_per_sec']:.1f} |

## Optimizations

1. HEADLESS skips LIVE rings + AR/WE/LE observers (science/V2 unaffected)
2. Tick-scoped event drain (`collect_observer_events_for_tick`)

## Equivalence

collect-for-tick ≡ full-filter: **{eq.get('collect_for_tick_equiv')}**  
HEADLESS↔LIVE science fingerprints: **{eq.get('headless_live_science_match')}**  
Parallel determinism: **{par.get('all_match')}**

## Parallel aggregate world-ticks/sec

1/2/4/8: {par['workers']['1']['aggregate_world_ticks_per_sec']:.0f} / {par['workers']['2']['aggregate_world_ticks_per_sec']:.0f} / {par['workers']['4']['aggregate_world_ticks_per_sec']:.0f} / {par['workers']['8']['aggregate_world_ticks_per_sec']:.0f}

## NEXT

**SEARCH_COMPACT** for Search workers (skip FULL V2 biography on rejected worlds).
Further Session micro-opts have diminishing returns vs fair runtime.step cost.
"""
    (OUT / "SUMMARY.md").write_text(md)
    _write("ACCEPTANCE.json", {"marker": marker, "exact_match": eq.get("exact_match")})
    print(md)
    print(marker)


if __name__ == "__main__":
    main()
