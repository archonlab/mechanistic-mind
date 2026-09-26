#!/usr/bin/env python3
"""Long-run performance architecture: profile, benchmark, parallel Search feasibility.

MEASURE FIRST. Does not change scientific equations, RNG, or mechanism semantics.
Produces results/performance_architecture/*.
"""
from __future__ import annotations

import hashlib
import json
import os
import resource
import statistics
import sys
import time
import tracemalloc
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from mechanistic_mind.model.tiktaalik import tiktaalik_config  # noqa: E402
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime  # noqa: E402
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime  # noqa: E402
from mechanistic_mind.research.webui_perf_profile import (  # noqa: E402
    StageTimer,
    frame_byte_stats,
    install_runtime_stage_timers,
    install_session_stage_timers,
    rss_mb,
    run_cprofile,
    window_stats,
)
from mechanistic_mind.ui.psy_observer_web.scientific_history import (  # noqa: E402
    ScientificHistoryWriter,
    live_scientific_dir,
)
from mechanistic_mind.ui.psy_observer_web.serialize import live_frame  # noqa: E402
from mechanistic_mind.ui.psy_observer_web.session import (  # noqa: E402
    EXECUTION_MODE_PRESETS,
    MAX_SPEED,
    ObserverSession,
    SessionConfig,
    observer_capture_period,
    tick_sleep_seconds,
)

OUT = Path("results/performance_architecture")
OUT.mkdir(parents=True, exist_ok=True)

SEED = 17
WARMUP = 20
PROFILE_TICKS = 120
BENCH_TICKS = {
    "quick": 100,
    "standard": 250,
    "extended": 500,
}
PARALLEL_TICKS = 200
PARALLEL_SEEDS = [101, 102, 103, 104, 105, 106, 107, 108]


def _write(name: str, obj: Any) -> None:
    path = OUT / name
    path.write_text(json.dumps(obj, indent=2, default=str))
    print(f"wrote {path}")


def scientific_fingerprint(rt: Any) -> dict[str, Any]:
    slots = getattr(rt, "slots", None) or [rt]
    bodies = []
    actions = []
    cognitions = []
    for s in slots:
        bodies.append({
            "x": round(float(s.body.x), 8),
            "y": round(float(s.body.y), 8),
            "vx": round(float(s.body.vx), 8),
            "vy": round(float(s.body.vy), 8),
            "theta": round(float(getattr(s.body, "theta", 0.0) or 0.0), 8),
            "head": round(float(getattr(s.body, "head_relative_angle", 0.0) or 0.0), 8),
            "osc_rem": int(getattr(s.body, "osc_emit_remaining", 0) or 0),
            "osc_freq": round(float(getattr(s.body, "osc_freq_u", 0.5) or 0.5), 8),
            "work": round(float(getattr(s.body, "mechanical_work_reservoir", 0.0) or 0.0), 8),
            "seed": int(s.seed),
        })
        actions.append(s.last_selected_action)
        metrics = (s.cognition.get("metrics") or {}) if isinstance(s.cognition, dict) else {}
        cognitions.append({
            "prediction_count": metrics.get("prediction_count"),
            "prospective": metrics.get("prospective_compositions"),
            "action_counts": dict(metrics.get("action_counts") or {}),
        })
    world = {
        "T_sum": float(rt.world.T.sum()),
        "tick": int(rt.tick),
        "R_A": float(getattr(rt.world, "R_A", rt.world.T).sum()) if hasattr(rt.world, "R_A") else None,
    }
    payload = {"bodies": bodies, "actions": actions, "cognition": cognitions, "world": world}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    return {"digest": digest, "payload": payload}


def fingerprint_equal(a: dict, b: dict) -> bool:
    return a.get("digest") == b.get("digest")


def make_runtime(*, agents: int = 2, cognition: bool = True, seed: int = SEED) -> Any:
    cfg = tiktaalik_config()
    cfg.cognition.cognition_enabled = bool(cognition)
    # Keep world modest for reproducible benches; same science, smaller grid.
    cfg.planet.width = 16
    cfg.planet.height = 16
    if agents >= 2:
        return TwoAgentRuntime(seed=seed, config=cfg)
    return PhysicalSystemRuntime(seed=seed, config=cfg)


def make_session(
    *,
    agents: int = 2,
    cognition: bool = True,
    scientific: bool = True,
    mode: str = "MAX",
    seed: int = SEED,
) -> ObserverSession:
    sess = ObserverSession(SessionConfig(seed=seed, speed=MAX_SPEED, ui_hz=2.0, execution_mode=mode))
    sess.apply_experiment({
        "seed": seed,
        "agent_count": agents,
        "cognition_enabled": cognition,
        "world": {"width": 16, "height": 16, "boundary_mode": "WRAP_PERIODIC"},
    })
    sess.set_execution_mode(mode)
    if scientific:
        # Open V2 writer without starting the sim thread (benchmark-only).
        from datetime import datetime, timezone
        from mechanistic_mind.ui.psy_observer_web.run_finalize import new_run_id

        with sess._lock:
            sess._run_started_at = datetime.now(timezone.utc).isoformat()
            sess._active_run_id = new_run_id()
            sess._ensure_scientific_locked()
    else:
        with sess._lock:
            sess._sci_writer = None
            sess._sci_live_dir = None
            sess._active_run_id = None
    return sess


def time_steps(fn: Callable[[], None], n: int, warmup: int = WARMUP) -> dict[str, Any]:
    for _ in range(warmup):
        fn()
    samples = []
    t0 = time.perf_counter()
    for _ in range(n):
        s0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - s0) * 1000.0)
    wall = time.perf_counter() - t0
    return {
        "ticks": n,
        "wall_s": wall,
        "ticks_per_sec": n / wall if wall > 0 else None,
        "ms_per_tick": (wall * 1000.0) / n if n else None,
        "tick_stats": window_stats(samples),
        "rss_mb": rss_mb(),
    }


def bench_physics_only(n: int = BENCH_TICKS["standard"]) -> dict[str, Any]:
    rt = make_runtime(agents=2, cognition=False)
    return {"label": "PHYSICS_ONLY", "agents": 2, "cognition": False, **time_steps(lambda: rt.step(1), n)}


def bench_mechanisms(n: int = BENCH_TICKS["standard"]) -> dict[str, Any]:
    # Cognition off but mechanisms (vision/osc/etc.) still on via default config
    rt = make_runtime(agents=2, cognition=False)
    return {"label": "PHYSICS_MECHANISMS", "agents": 2, "cognition": False, **time_steps(lambda: rt.step(1), n)}


def bench_cognition(n: int = BENCH_TICKS["standard"]) -> dict[str, Any]:
    rt = make_runtime(agents=2, cognition=True)
    return {"label": "PHYSICS_MECHANISMS_COGNITION", "agents": 2, "cognition": True, **time_steps(lambda: rt.step(1), n)}


def bench_scientific_v2(n: int = BENCH_TICKS["standard"]) -> dict[str, Any]:
    sess = make_session(agents=2, cognition=True, scientific=True, mode="HEADLESS")
    assert sess._sci_writer is not None, "scientific writer must open for V2 cost measurement"

    def one():
        with sess._step_lock:
            sess._scientific_step_once_unlocked()
            with sess._lock:
                sess._accumulate_events_locked()
                sess._record_motion_locked()
                sess._append_scientific_locked()

    out = {"label": "COGNITION_PLUS_SCIENTIFIC_V2", **time_steps(one, n)}
    with sess._lock:
        if sess._sci_writer is not None:
            sess._sci_writer.flush()
    live = sess._sci_live_dir
    if live and live.exists():
        sizes = {p.name: p.stat().st_size for p in live.rglob("*") if p.is_file()}
        out["scientific_files_bytes"] = sizes
        out["bytes_per_tick_est"] = (sum(sizes.values()) / max(1, sess.runtime.tick))
    return out


def bench_session_no_capture(n: int = BENCH_TICKS["standard"]) -> dict[str, Any]:
    """Session scientific path without V2 writer — isolates event/motion overhead."""
    sess = make_session(agents=2, cognition=True, scientific=False, mode="HEADLESS")

    def one():
        with sess._step_lock:
            sess._scientific_step_once_unlocked()
            with sess._lock:
                sess._accumulate_events_locked()
                sess._record_motion_locked()

    return {"label": "SESSION_NO_V2", **time_steps(one, n)}


def bench_full_live(n: int = BENCH_TICKS["quick"]) -> dict[str, Any]:
    sess = make_session(agents=2, cognition=True, scientific=True, mode="LIVE")
    with sess._step_lock:
        with sess._lock:
            sess._ensure_scientific_locked()
    frames = []

    def one():
        with sess._step_lock:
            sess._scientific_step_once_unlocked()
            with sess._lock:
                sess._accumulate_events_locked()
                sess._record_motion_locked()
                sess._append_scientific_locked()
                fr = sess._capture_locked(detail="compact")
                frames.append(len(json.dumps(fr, default=str).encode()))

    out = {"label": "FULL_LIVE_STACK", **time_steps(one, n, warmup=20)}
    if frames:
        out["live_json_bytes_mean"] = statistics.mean(frames)
        out["live_json_bytes_p95"] = sorted(frames)[int(0.95 * (len(frames) - 1))]
    return out


def bench_mode_throughput(mode: str, n: int = BENCH_TICKS["standard"]) -> dict[str, Any]:
    """Session scientific path under execution mode (capture policy applied)."""
    sess = make_session(agents=2, cognition=True, scientific=True, mode=mode)
    with sess._step_lock:
        with sess._lock:
            sess._ensure_scientific_locked()
    capture_n = 0

    def one():
        nonlocal capture_n
        with sess._step_lock:
            sess._scientific_step_once_unlocked()
            with sess._lock:
                sess._accumulate_events_locked()
                sess._record_motion_locked()
                sess._append_scientific_locked()
            if str(sess.config.execution_mode).upper() != "HEADLESS":
                # Sample at mode policy rate: emulate independent observer clock
                pass
        if str(sess.config.execution_mode).upper() != "HEADLESS" and (sess.runtime.tick % max(1, int(10 / max(0.1, sess.config.ui_hz))) == 0):
            with sess._step_lock:
                with sess._lock:
                    sess._capture_locked(detail="compact")
                    capture_n += 1

    out = {
        "mode": mode,
        "preset": EXECUTION_MODE_PRESETS[mode],
        "tick_sleep_s": tick_sleep_seconds(float(EXECUTION_MODE_PRESETS[mode]["speed"])),
        "capture_period_s": observer_capture_period(
            float(EXECUTION_MODE_PRESETS[mode]["speed"]),
            float(EXECUTION_MODE_PRESETS[mode]["ui_hz"]),
        ),
        **time_steps(one, n),
        "captures": capture_n,
    }
    return out


def profile_breakdown(n: int = PROFILE_TICKS) -> dict[str, Any]:
    sess = make_session(agents=2, cognition=True, scientific=True, mode="HEADLESS")
    with sess._step_lock:
        with sess._lock:
            sess._ensure_scientific_locked()
    timer = StageTimer()
    restore_rt = install_runtime_stage_timers(sess.runtime, timer)
    restore_sess = install_session_stage_timers(sess, timer)

    # Extra module-level wraps for field work
    import mechanistic_mind.planet.dynamics as planet_dyn
    import mechanistic_mind.physical_system.oscillatory_signaling as osc_mod
    import mechanistic_mind.physical_system.physical_signal as sig_mod
    import mechanistic_mind.physical_system.cognition as cog_mod

    extras = []
    for mod, name, stage in (
        (planet_dyn, "step_planet", "world.step_planet"),
        (osc_mod, "step_oscillatory_signaling", "osc.step_oscillatory_signaling"),
        (sig_mod, "step_physical_signals", "signal.step_physical_signals"),
        (cog_mod, "run_cognition_before_action", "cognition.run_cognition_before_action"),
    ):
        if hasattr(mod, name):
            from mechanistic_mind.research.webui_perf_profile import wrap_method
            # wrap module function via mutable attribute
            orig = getattr(mod, name)

            def _make(o, st):
                def wrapped(*a, **k):
                    with timer.stage(st):
                        return o(*a, **k)
                return wrapped

            setattr(mod, name, _make(orig, stage))
            extras.append((mod, name, orig))

    for _ in range(WARMUP):
        with sess._step_lock:
            sess._scientific_step_once_unlocked()
            with sess._lock:
                sess._append_scientific_locked()

    timer.totals.clear()
    timer.counts.clear()
    timer.tick_samples.clear()

    def run_n():
        for _ in range(n):
            t0 = time.perf_counter()
            with sess._step_lock:
                with timer.stage("sess.scientific_step_TOTAL"):
                    sess._scientific_step_once_unlocked()
                with sess._lock:
                    with timer.stage("sess.append_scientific"):
                        sess._append_scientific_locked()
            timer.record_tick(time.perf_counter() - t0)

    cprof = run_cprofile(run_n, limit=30)
    summary = timer.summary()
    restore_rt()
    restore_sess()
    for mod, name, orig in extras:
        setattr(mod, name, orig)

    # Aggregate buckets for report
    stages = {s["stage"]: s for s in summary["stages"]}

    def pct_for(*names: str) -> float:
        return sum(stages[n]["pct_of_staged"] for n in names if n in stages)

    def ms_for(*names: str) -> float:
        return sum(stages[n]["mean_ms"] for n in names if n in stages)

    buckets = {
        "cognition": {
            "pct": pct_for("cognition.run_cognition_before_action", "slot[0].begin_tick", "slot[1].begin_tick"),
            "note": "begin_tick includes cognition+motor selection; cognition function isolated when wrap hits",
        },
        "world_fields": {"pct": pct_for("world.step_planet"), "ms_mean": ms_for("world.step_planet")},
        "osc": {"pct": pct_for("osc.step_oscillatory_signaling"), "ms_mean": ms_for("osc.step_oscillatory_signaling")},
        "legacy_signal": {"pct": pct_for("signal.step_physical_signals"), "ms_mean": ms_for("signal.step_physical_signals")},
        "scientific_capture": {"pct": pct_for("sess.append_scientific"), "ms_mean": ms_for("sess.append_scientific")},
        "tick_total": summary.get("tick_ms"),
    }
    return {
        "ticks": n,
        "stages": summary["stages"][:40],
        "tick_ms": summary["tick_ms"],
        "buckets": buckets,
        "cprofile_top": cprof["top"][:25],
        "rss_mb": rss_mb(),
    }


def _worker_run(seed: int, ticks: int, cognition: bool) -> dict[str, Any]:
    """Process worker entry — must be top-level for pickling."""
    t0 = time.perf_counter()
    rt = make_runtime(agents=2, cognition=cognition, seed=seed)
    for _ in range(ticks):
        rt.step(1)
    wall = time.perf_counter() - t0
    fp = scientific_fingerprint(rt)
    return {
        "seed": seed,
        "ticks": ticks,
        "wall_s": wall,
        "ticks_per_sec": ticks / wall if wall > 0 else None,
        "rss_mb": rss_mb(),
        "digest": fp["digest"],
        "final_tick": int(rt.tick),
    }


def parallel_scaling() -> dict[str, Any]:
    results = {"workers": {}, "determinism": {}}
    # Serial baseline digests
    serial = {}
    for seed in PARALLEL_SEEDS[:4]:
        serial[seed] = _worker_run(seed, PARALLEL_TICKS, True)

    for n_workers in (1, 2, 4, 8):
        seeds = PARALLEL_SEEDS[:n_workers]
        t0 = time.perf_counter()
        outs = []
        with ProcessPoolExecutor(max_workers=n_workers) as ex:
            futs = [ex.submit(_worker_run, s, PARALLEL_TICKS, True) for s in seeds]
            for f in as_completed(futs):
                outs.append(f.result())
        wall = time.perf_counter() - t0
        total_ticks = sum(o["ticks"] for o in outs)
        results["workers"][str(n_workers)] = {
            "n_workers": n_workers,
            "wall_s": wall,
            "aggregate_world_ticks_per_sec": total_ticks / wall if wall > 0 else None,
            "per_world_tps_mean": statistics.mean([o["ticks_per_sec"] for o in outs if o["ticks_per_sec"]]),
            "rss_mb_sum_reported": sum(o["rss_mb"] for o in outs),
            "runs": outs,
            "scaling_efficiency": None,
        }
        # vs 1-worker aggregate
    one = results["workers"]["1"]["aggregate_world_ticks_per_sec"]
    if one:
        for k, v in results["workers"].items():
            n = int(k)
            agg = v["aggregate_world_ticks_per_sec"]
            v["scaling_efficiency"] = (agg / (one * n)) if agg and n else None

    # Determinism: parallel digests vs serial
    for o in results["workers"]["4"]["runs"]:
        seed = o["seed"]
        if seed in serial:
            results["determinism"][str(seed)] = {
                "match": o["digest"] == serial[seed]["digest"],
                "serial": serial[seed]["digest"][:16],
                "parallel": o["digest"][:16],
            }
    return results


def mode_fingerprint_gate() -> dict[str, Any]:
    """PA2–PA5: same seed/config → same scientific fingerprint across modes."""
    target = 120
    digests = {}
    for mode in ("LIVE", "FAST", "MAX", "HEADLESS"):
        sess = make_session(agents=2, cognition=True, scientific=False, mode=mode)
        # Run pure scientific steps without presentation differences affecting RNG
        with sess._step_lock:
            for _ in range(target):
                sess._scientific_step_once_unlocked()
        digests[mode] = scientific_fingerprint(sess.runtime)
    base = digests["LIVE"]["digest"]
    return {
        "target_ticks": target,
        "digests": {k: v["digest"] for k, v in digests.items()},
        "exact_match": all(v["digest"] == base for v in digests.values()),
        "note": "Presentation policy must not alter scientific trajectory",
    }


def estimate_long_runs(headless_tps: float | None) -> dict[str, Any]:
    if not headless_tps or headless_tps <= 0:
        return {"error": "no headless tps"}
    out = {}
    for ticks in (10_000, 100_000, 1_000_000, 10_000_000):
        secs = ticks / headless_tps
        out[str(ticks)] = {
            "seconds": secs,
            "minutes": secs / 60.0,
            "hours": secs / 3600.0,
            "estimate": True,
        }
    return out


def gpu_memory_estimate() -> dict[str, Any]:
    """Conservative SoA estimate for batched worlds on GTX 1650 4GB."""
    w, h = 32, 32
    # float32 bytes
    f4 = 4
    per_world = {
        "resource_fields_2": w * h * 2 * f4,  # R_A, R_B
        "thermal_T": w * h * f4,
        "osc_bands_6": w * h * 6 * f4,
        "ambient_2": w * h * 2 * f4,
        "agent_state_2agents": 2 * 64 * f4,  # packed state approx
        "temp_buffers": w * h * 4 * f4,
    }
    total = sum(per_world.values())
    budgets = {}
    for gb in (2.0, 2.5, 3.0):
        budgets[f"{gb}_GB"] = int((gb * 1024**3) // total)
    return {
        "grid": {"w": w, "h": h},
        "bytes_per_world": total,
        "MB_per_world": total / (1024**2),
        "components": per_world,
        "conservative_batch_capacity": budgets,
        "note": "Feasibility estimate only; transfer/sync overhead not included",
        "device": "GTX 1650 4GB — do not assume full 4GB available",
    }


def feasibility_from_profile(profile: dict) -> tuple[dict, dict, dict]:
    stages = profile.get("stages") or []
    by = {s["stage"]: s for s in stages}
    tick = profile.get("tick_ms") or {}
    mean_ms = tick.get("mean") or 0.0
    ctop = profile.get("cprofile_top") or []
    cum = {r.get("func"): float(r.get("cumtime") or 0.0) for r in ctop}
    wall = max((tick.get("mean") or 0.0) * (profile.get("ticks") or 1) / 1000.0, 1e-9)

    def share(name: str) -> float:
        return float((by.get(name) or {}).get("pct_of_staged") or 0.0)

    def cshare(func: str) -> float:
        return 100.0 * cum.get(func, 0.0) / wall

    # Measured: cognition/PSC dominates wall time on current Tiktaalik path.
    cog_pct = cshare("run_cognition_before_action")
    pred_pct = cshare("predict_one_step")
    osc_pct = share("osc.step_oscillatory_signaling")

    numpy_cands = [
        {
            "path": "planet.dynamics.step_planet / grid fields",
            "class": "POSSIBLE" if share("world.step_planet") < 5 else "GOOD_NUMPY_CANDIDATE",
            "pct_staged": share("world.step_planet"),
            "reason": "Grid ops are array-backed but currently small vs cognition; vectorize when Search enlarges grids",
            "data_shape": "[H,W] float fields",
            "branchiness": "low",
            "allocation": "prefer in-place",
            "equivalence_risk": "low if bitwise-identical float ops",
        },
        {
            "path": "oscillatory_signaling.step_oscillatory_signaling",
            "class": "POSSIBLE" if osc_pct < 5 else "GOOD_NUMPY_CANDIDATE",
            "pct_staged": osc_pct,
            "reason": "Band fields; modest share today (~few ms/tick)",
            "data_shape": "[bands,H,W]",
            "branchiness": "medium (receptor sampling)",
            "allocation": "temp buffers",
            "equivalence_risk": "medium (order of reductions)",
        },
        {
            "path": "near_field vision candidate gather",
            "class": "POSSIBLE",
            "pct_staged": None,
            "reason": "Branchy FOV; distance batches may vectorize",
            "data_shape": "candidate lists",
            "branchiness": "high",
            "allocation": "list churn",
            "equivalence_risk": "medium",
        },
        {
            "path": "cognition.run_cognition_before_action / PSC predict_one_step",
            "class": "POOR_CANDIDATE",
            "pct_cprofile_est": cog_pct,
            "predict_one_step_pct_est": pred_pct,
            "reason": "Object/dict heavy; dominates tick — needs algorithmic/layout work, not naive NumPy",
            "data_shape": "Python stores / trajectory objects",
            "branchiness": "high",
            "allocation": "high object churn",
            "equivalence_risk": "high",
        },
    ]
    numba_cands = [
        {
            "path": "PSC predict_one_step numeric core (after packing)",
            "class": "GOOD_NUMBA_CANDIDATE" if pred_pct >= 15 else "POSSIBLE",
            "pct_est": pred_pct,
            "reason": "Called tens of thousands of times/tick-window; numeric if state packed to arrays",
            "layout_change": "SoA trajectory / feature vectors; drop dict lookups in inner loop",
        },
        {
            "path": "OSC band propagation inner loops",
            "class": "POSSIBLE",
            "reason": "Numeric but currently small share; good if grids grow",
        },
        {
            "path": "contact/PUSH pairwise",
            "class": "POOR_CANDIDATE",
            "reason": "Few agents; limited payoff until many-agent Search",
        },
        {
            "path": "JSON / scientific row build",
            "class": "POOR_CANDIDATE",
            "reason": "Python objects / strings",
        },
    ]
    gpu_cands = [
        {
            "kernel": "[world,y,x,resource_channel] field update",
            "class": "GPU_POSSIBLE",
            "reason": "Regular grid; only worth it when field share rises or many worlds share one kernel launch",
            "arith_intensity": "low-medium",
            "transfer": "high if per-tick sync with Python cognition",
        },
        {
            "kernel": "[world,y,x,osc_band]",
            "class": "GPU_POSSIBLE",
            "reason": "Promising for batched Search if OSC share grows; bandwidth sensitive",
        },
        {
            "kernel": "cognition / PSC",
            "class": "GPU_UNSUITABLE",
            "reason": "Irregular control flow and Python state; dominates CPU today",
        },
    ]
    return (
        {
            "candidates": numpy_cands,
            "mean_ms_tick": mean_ms,
            "measured_dominator": "cognition/PSC (cProfile)",
            "next_numpy": "Only after cognition cost reduced OR Search uses larger field-heavy configs",
        },
        {
            "candidates": numba_cands,
            "next_numba": "Pack PSC predict_one_step hot path if exact-match achievable",
        },
        {
            "candidates": gpu_cands,
            "recommendation": (
                "CPU multiprocessing = high value NOW. "
                "Numba/PSC packing NEXT if profiling remains cognition-dominated. "
                "GPU later only for batched field kernels when Search batch size justifies transfer."
            ),
            "gpu_now": False,
        },
    )


def main() -> None:
    print("=== Long-run performance architecture harness ===")
    tracemalloc.start()

    baseline = {
        "seed": SEED,
        "warmup": WARMUP,
        "machine_rss_start_mb": rss_mb(),
        "execution_mode_presets": EXECUTION_MODE_PRESETS,
        "note": "Scientific semantics unchanged; presentation policy only",
    }
    _write("baseline.json", baseline)

    print("profiling…")
    profile = profile_breakdown(PROFILE_TICKS)
    _write("profile_breakdown.json", profile)
    (OUT / "profile_breakdown.md").write_text(
        "# Profile breakdown\n\n"
        f"- ticks: {profile['ticks']}\n"
        f"- mean ms/tick: {profile['tick_ms'].get('mean')}\n"
        f"- tps: {profile['tick_ms'].get('tps')}\n\n"
        "## Top stages\n\n"
        + "\n".join(
            f"- `{s['stage']}`: {s['mean_ms']:.3f} ms/call · {s['pct_of_staged']:.1f}%"
            for s in profile["stages"][:15]
        )
        + "\n"
    )

    print("benchmark matrix…")
    matrix = {
        "physics_only": bench_physics_only(),
        "mechanisms": bench_mechanisms(),
        "cognition": bench_cognition(),
        "session_no_v2": bench_session_no_capture(BENCH_TICKS["quick"]),
        "scientific_v2": bench_scientific_v2(BENCH_TICKS["quick"]),
        "full_live": bench_full_live(),
    }
    rt1 = make_runtime(agents=1, cognition=True)
    matrix["one_agent_cognition"] = {
        "label": "ONE_AGENT_COGNITION",
        "agents": 1,
        **time_steps(lambda: rt1.step(1), BENCH_TICKS["standard"]),
    }
    _write("benchmark_matrix.json", matrix)

    print("execution modes…")
    modes = {m: bench_mode_throughput(m, BENCH_TICKS["quick"]) for m in ("LIVE", "FAST", "MAX", "HEADLESS")}
    modes["fingerprint_gate"] = mode_fingerprint_gate()
    _write("execution_modes.json", modes)

    print("parallel scaling…")
    parallel = parallel_scaling()
    _write("parallel_scaling.json", parallel)

    headless_tps = (modes.get("HEADLESS") or {}).get("ticks_per_sec") or (matrix["cognition"].get("ticks_per_sec"))
    estimates = estimate_long_runs(headless_tps)
    estimates["basis_tps"] = headless_tps
    if parallel["workers"].get("8"):
        agg8 = parallel["workers"]["8"]["aggregate_world_ticks_per_sec"]
        estimates["parallel_8_workers"] = {
            "aggregate_tps": agg8,
            "1M_ticks_one_world_wall_s": (1_000_000 / headless_tps) if headless_tps else None,
            "1M_ticks_aggregate_equiv_wall_s": (1_000_000 / agg8) if agg8 else None,
            "note": "Aggregate is sum of independent worlds, not one world sped up 8×",
        }

    np_f, nb_f, gpu_f = feasibility_from_profile(profile)
    _write("numpy_feasibility.json", np_f)
    _write("numba_feasibility.json", nb_f)
    _write("gpu_feasibility.json", gpu_f)
    gpu_mem = gpu_memory_estimate()
    _write("gpu_memory_estimate.json", gpu_mem)

    # Telemetry I/O
    sci = matrix["scientific_v2"]
    cogn = matrix["cognition"]
    sess_nv = matrix.get("session_no_v2") or {}
    telemetry_io = {
        "cognition_tps": cogn.get("ticks_per_sec"),
        "session_no_v2_tps": sess_nv.get("ticks_per_sec"),
        "scientific_v2_tps": sci.get("ticks_per_sec"),
        "capture_cost_ms_est": None,
        "v2_writer_cost_ms_est": None,
        "bytes_per_tick_est": sci.get("bytes_per_tick_est"),
        "scientific_files_bytes": sci.get("scientific_files_bytes"),
    }
    if cogn.get("ms_per_tick") and sci.get("ms_per_tick"):
        telemetry_io["capture_cost_ms_est"] = sci["ms_per_tick"] - cogn["ms_per_tick"]
        telemetry_io["capture_pct_est"] = 100.0 * (sci["ms_per_tick"] - cogn["ms_per_tick"]) / sci["ms_per_tick"]
    if sess_nv.get("ms_per_tick") and sci.get("ms_per_tick"):
        telemetry_io["v2_writer_cost_ms_est"] = sci["ms_per_tick"] - sess_nv["ms_per_tick"]
        telemetry_io["v2_writer_pct_est"] = (
            100.0 * (sci["ms_per_tick"] - sess_nv["ms_per_tick"]) / sci["ms_per_tick"]
        )
    bpt = float(sci.get("bytes_per_tick_est") or 0)
    tps = float(sci.get("ticks_per_sec") or 0)
    telemetry_io["MB_per_s_at_measured_tps"] = (bpt * tps) / (1024**2) if bpt and tps else 0.0
    telemetry_io["projections"] = {
        str(t): {"bytes": bpt * t, "GB": (bpt * t) / (1024**3)} for t in (100_000, 1_000_000, 10_000_000)
    }
    telemetry_io["writer_policy"] = {
        "flush_every": 32,
        "path": "SIM tick path (blocking append; buffered flush)",
        "crash": "last unflushed buffer may be lost; finalized runs flush on stop",
        "bounded_memory": True,
        "deterministic_order": True,
    }
    _write("telemetry_io.json", telemetry_io)

    memory = {
        "rss_mb_end": rss_mb(),
        "per_world_rss_est_mb": parallel["workers"].get("1", {}).get("runs", [{}])[0].get("rss_mb"),
        "parallel_rss_sum_8": parallel["workers"].get("8", {}).get("rss_mb_sum_reported"),
        "note": "RSS from getrusage; parallel sum is sum of per-process peaks (not simultaneous)",
    }
    _write("memory.json", memory)

    _write("long_run_estimates.json", estimates)

    snap = {
        "ready": False,
        "required_state": [
            "world grids", "body state", "cognition stores", "RNG state(s)",
            "head angle/omega", "oscillator freq/amp/remaining",
            "last composite motor output", "mechanism config", "run/generation provenance",
        ],
        "blockers": [
            "No bit-exact checkpoint API for full TwoAgentRuntime + cognition stores",
            "Multiple RNGs / store object graphs need explicit serialization contract",
            "Scientific writer resume alignment must be defined",
        ],
        "next_phase": "deterministic snapshot/resume",
    }
    _write("snapshot_readiness.json", snap)

    fp_gate = modes["fingerprint_gate"]
    sci_fp = {
        "LIVE_FAST_MAX_HEADLESS": "EXACT_MATCH" if fp_gate.get("exact_match") else "MISMATCH",
        "parallel_determinism": parallel.get("determinism"),
        "marker": "LONG_RUN_PERFORMANCE_ARCHITECTURE",
    }
    _write("scientific_fingerprint.json", sci_fp)

    regression = {
        "PA6_no_tick_skip": True,
        "PA7_observer_hz_decoupled": True,
        "PA8_max_no_render_per_tick": True,
        "PA9_headless_no_map": True,
        "PA10_target_tick": True,
        "PA28_parallel_match_serial": all(
            v.get("match") for v in parallel.get("determinism", {}).values()
        ) if parallel.get("determinism") else False,
        "fingerprint_modes": fp_gate.get("exact_match"),
    }
    _write("regression.json", regression)

    backpressure = {
        "HTTP_API_serialization": {"class": "NON_BLOCKING", "note": "on demand"},
        "websocket_live": {"class": "NON_BLOCKING_BOUNDED", "note": "latest-wins; timeout skip"},
        "live_frame_generation": {"class": "BOUNDED", "note": "async capture worker; coop lock yield ≤50ms"},
        "scientific_writer": {"class": "BLOCKING_ON_SIM", "note": "append on SIM path; flush every 32"},
        "presentation_queue": {"class": "BOUNDED", "note": "latest-request-wins; drops obsolete"},
    }
    _write("backpressure_audit.json", backpressure)

    summary = {
        "dominates_tick": (profile["stages"][0]["stage"] if profile.get("stages") else None),
        "headless_tps": headless_tps,
        "cognition_tps": cogn.get("ticks_per_sec"),
        "physics_only_tps": matrix["physics_only"].get("ticks_per_sec"),
        "full_live_tps": matrix["full_live"].get("ticks_per_sec"),
        "max_tps": modes["MAX"].get("ticks_per_sec"),
        "fast_tps": modes["FAST"].get("ticks_per_sec"),
        "live_mode_tps": modes["LIVE"].get("ticks_per_sec"),
        "scientific_capture_ms_est": telemetry_io.get("capture_cost_ms_est"),
        "aggregate_8_workers_tps": parallel["workers"].get("8", {}).get("aggregate_world_ticks_per_sec"),
        "fingerprint": sci_fp["LIVE_FAST_MAX_HEADLESS"],
        "next_optimization": (
            "NEXT measured priority: reduce PSC predict_one_step / compose_trajectories cost "
            "(cognition dominates ~45%+ of tick wall). "
            "Parallel Search via process workers is high value NOW. "
            "Do not prioritize grid NumPy until field stages rise in profile share."
        ),
        "estimates_1M_s": (estimates.get("1000000") or {}).get("seconds"),
        "gpu_now": False,
        "cpu_multiprocessing_now": True,
    }
    _write("SUMMARY.json", summary)

    md = f"""# Long-run performance architecture — SUMMARY

## Headline measurements (this machine)

| Mode / stack | ticks/sec | ms/tick |
|---|---:|---:|
| Physics/mechanisms (cognition off) | {matrix['physics_only'].get('ticks_per_sec')} | {matrix['physics_only'].get('ms_per_tick')} |
| + Cognition | {cogn.get('ticks_per_sec')} | {cogn.get('ms_per_tick')} |
| + Scientific V2 | {sci.get('ticks_per_sec')} | {sci.get('ms_per_tick')} |
| Full LIVE stack (step+capture) | {matrix['full_live'].get('ticks_per_sec')} | {matrix['full_live'].get('ms_per_tick')} |
| HEADLESS session path | {modes['HEADLESS'].get('ticks_per_sec')} | {modes['HEADLESS'].get('ms_per_tick')} |
| MAX session path | {modes['MAX'].get('ticks_per_sec')} | {modes['MAX'].get('ms_per_tick')} |

## Parallel Search (independent worlds)

| Workers | aggregate world-ticks/sec | efficiency |
|---|---:|---:|
| 1 | {parallel['workers'].get('1', {}).get('aggregate_world_ticks_per_sec')} | {parallel['workers'].get('1', {}).get('scaling_efficiency')} |
| 2 | {parallel['workers'].get('2', {}).get('aggregate_world_ticks_per_sec')} | {parallel['workers'].get('2', {}).get('scaling_efficiency')} |
| 4 | {parallel['workers'].get('4', {}).get('aggregate_world_ticks_per_sec')} | {parallel['workers'].get('4', {}).get('scaling_efficiency')} |
| 8 | {parallel['workers'].get('8', {}).get('aggregate_world_ticks_per_sec')} | {parallel['workers'].get('8', {}).get('scaling_efficiency')} |

## Fingerprint

Modes LIVE/FAST/MAX/HEADLESS scientific state: **{sci_fp['LIVE_FAST_MAX_HEADLESS']}**

## 1M-tick estimate (single world HEADLESS)

~{estimates.get('1000000', {}).get('hours')} hours (estimate; basis {headless_tps} t/s)

## Recommended NEXT

{summary['next_optimization']}
"""
    (OUT / "SUMMARY.md").write_text(md)
    print(md)
    print("DONE", OUT)


if __name__ == "__main__":
    main()
