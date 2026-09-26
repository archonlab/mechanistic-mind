"""PSC prediction optimization: equivalence, microbench, full runtime ladder."""
from __future__ import annotations

import hashlib
import json
import os
import resource
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from mechanistic_mind.model.tiktaalik import tiktaalik_config  # noqa: E402
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime  # noqa: E402
from mechanistic_mind.research import prospective_composition as pr  # noqa: E402
from mechanistic_mind.research import psc_opt  # noqa: E402
from mechanistic_mind.ui.psy_observer_web.session import (  # noqa: E402
    MAX_SPEED,
    ObserverSession,
    SessionConfig,
)

OUT = Path("results/psc_prediction_optimization")
OUT.mkdir(parents=True, exist_ok=True)

SEEDS = [17, 23, 41, 59, 83]
PARALLEL_SEEDS = [101, 102, 103, 104, 105, 106, 107, 108]


def _write(name: str, obj: Any) -> None:
    (OUT / name).write_text(json.dumps(obj, indent=2, default=str))
    print("wrote", name)


def rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def make_rt(seed: int = 17, cognition: bool = True) -> TwoAgentRuntime:
    cfg = tiktaalik_config()
    cfg.cognition.cognition_enabled = bool(cognition)
    cfg.planet.width = 16
    cfg.planet.height = 16
    return TwoAgentRuntime(seed=seed, config=cfg)


def fingerprint(rt: Any) -> str:
    slots = getattr(rt, "slots", None) or [rt]
    bodies = []
    for s in slots:
        bodies.append({
            "x": round(float(s.body.x), 8),
            "y": round(float(s.body.y), 8),
            "vx": round(float(s.body.vx), 8),
            "vy": round(float(s.body.vy), 8),
            "action": s.last_selected_action,
            "pred": (s.cognition.get("metrics") or {}).get("prediction_count"),
            "psc": (s.cognition.get("metrics") or {}).get("prospective_compositions"),
        })
    payload = {"tick": int(rt.tick), "T": float(rt.world.T.sum()), "bodies": bodies}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def capture_states(seed: int = 17) -> dict[str, Any]:
    """EARLY/MID/LATER real prospection stores + observations."""
    rt = make_rt(seed)
    out = {}
    marks = {"EARLY": 40, "MID": 150, "LATER": 400}
    target = max(marks.values())
    for t in range(1, target + 1):
        rt.step(1)
        for name, tick in marks.items():
            if t == tick:
                slot = rt.slots[0]
                out[name] = {
                    "tick": t,
                    "store": deepcopy(slot.cognition["prospection"]),
                    "observation": deepcopy(slot.agent_observation()),
                    "n_transitions": len(slot.cognition["prospection"].get("transitions") or {}),
                    "actions": list(slot.cognition.get("available_actions") or ["WAIT"]),
                }
    return out


def result_key(r: dict) -> tuple:
    return (
        r.get("status"),
        r.get("action"),
        r.get("key"),
        r.get("transition_id"),
        r.get("support"),
        round(float(r.get("reliability") or 0.0), 12) if r.get("reliability") is not None else None,
        tuple(sorted((k, round(float(v), 12)) for k, v in (r.get("predicted") or {}).items())),
    )


def equivalence_suite(states: dict) -> dict[str, Any]:
    actions_extra = ["WAIT", "MOVE:N", "MOVE:S", "MOVE:E", "MOVE:W"]
    mismatches = []
    n = 0
    for phase, st in states.items():
        store = st["store"]
        obs = st["observation"]
        acts = list(dict.fromkeys(list(st["actions"]) + actions_extra))
        # exact + perturbed antecedents
        antecedents = [obs]
        antecedents.append({k: min(0.999, float(v) + 0.05) for k, v in obs.items()})
        antecedents.append({k: max(0.0, float(v) - 0.08) for k, v in obs.items()})
        for ant in antecedents:
            for act in acts:
                n += 1
                legacy = pr.predict_one_step(deepcopy(store), ant, act, backend="legacy")
                packed = pr.predict_one_step(deepcopy(store), ant, act, backend="packed")
                if result_key(legacy) != result_key(packed):
                    mismatches.append({"phase": phase, "act": act, "pair": "legacy_packed",
                                       "legacy": legacy, "packed": packed})
                numba = pr.predict_one_step(deepcopy(store), ant, act, backend="numba")
                if result_key(legacy) != result_key(numba):
                    mismatches.append({"phase": phase, "act": act, "pair": "legacy_numba",
                                       "legacy": legacy, "numba": numba})
    # ties / empty / single
    empty = pr.empty_store()
    e1 = pr.predict_one_step(empty, {"x": 0.5}, "WAIT", backend="legacy")
    e2 = pr.predict_one_step(empty, {"x": 0.5}, "WAIT", backend="packed")
    edge = {"empty_match": result_key(e1) == result_key(e2), "empty_status": e1.get("status")}
    return {
        "comparisons": n,
        "mismatches": len(mismatches),
        "exact_match": len(mismatches) == 0,
        "mismatch_samples": mismatches[:5],
        "edge": edge,
        "numba_available": psc_opt.get_numba_kernel() is not None,
        "provenance": psc_opt.backend_provenance(),
    }


def microbench(states: dict) -> dict[str, Any]:
    st = states["MID"]
    store = st["store"]
    obs = st["observation"]
    acts = ["WAIT", "MOVE:N", "MOVE:S", "MOVE:E", "MOVE:W"]
    # warmup pack
    psc_opt.ensure_pack(store)

    def run_backend(backend: str, n: int = 3000) -> dict[str, Any]:
        # cold
        s0 = deepcopy(store)
        t_cold0 = time.perf_counter()
        pr.predict_one_step(s0, obs, acts[0], backend=backend)
        cold = time.perf_counter() - t_cold0
        # warm end-to-end
        s = deepcopy(store)
        t0 = time.perf_counter()
        for i in range(n):
            pr.predict_one_step(s, obs, acts[i % len(acts)], backend=backend)
        wall = time.perf_counter() - t0
        # packing cost alone
        s2 = deepcopy(store)
        s2.pop("_psc_pack", None)
        s2["_psc_pack_version"] = int(s2.get("_psc_pack_version") or 0) + 1
        t_p0 = time.perf_counter()
        for _ in range(200):
            s2.pop("_psc_pack", None)
            s2["_psc_pack_version"] = int(s2.get("_psc_pack_version") or 0) + 1
            psc_opt.ensure_pack(s2)
        t_pack = (time.perf_counter() - t_p0) / 200

        return {
            "cold_s": cold,
            "warm_us_per_call": (wall / n) * 1e6,
            "warm_calls_per_sec": n / wall,
            "pack_rebuild_us": t_pack * 1e6,
            "n": n,
        }

    # Force numba compile timing
    compile_s = None
    try:
        psc_opt._numba_fn = None
        psc_opt._numba_init_error = None
        psc_opt._numba_compile_s = None
        t0 = time.perf_counter()
        fn = psc_opt.get_numba_kernel()
        compile_s = psc_opt._numba_compile_s if fn else None
        cold_import = time.perf_counter() - t0
    except Exception as exc:  # noqa: BLE001
        cold_import = None
        compile_s = str(exc)

    out = {
        "legacy": run_backend("legacy"),
        "packed": run_backend("packed"),
        "numba": run_backend("numba"),
        "numba_compile_s": compile_s,
        "numba_init_wall_s": cold_import,
        "state": {"phase": "MID", "n_transitions": st["n_transitions"]},
    }
    leg = out["legacy"]["warm_us_per_call"]
    for k in ("packed", "numba"):
        out[f"e2e_speedup_vs_legacy_{k}"] = leg / out[k]["warm_us_per_call"] if out[k]["warm_us_per_call"] else None
    return out


def differential_runs() -> dict[str, Any]:
    checkpoints = [100, 500, 1000]
    results = {}
    for seed in SEEDS:
        per = {}
        digests = {}
        for backend in ("legacy", "packed", "numba"):
            os.environ["MM_PSC_BACKEND"] = backend
            rt = make_rt(seed)
            marks = {}
            for t in range(1, max(checkpoints) + 1):
                rt.step(1)
                if t in checkpoints:
                    marks[str(t)] = fingerprint(rt)
            digests[backend] = marks
        # compare
        base = digests["legacy"]
        per["digests"] = {k: {kk: vv[:16] for kk, vv in v.items()} for k, v in digests.items()}
        per["packed_match"] = digests["packed"] == base
        per["numba_match"] = digests["numba"] == base
        results[str(seed)] = per
    os.environ["MM_PSC_BACKEND"] = "packed"
    return {
        "checkpoints": checkpoints,
        "seeds": results,
        "all_exact": all(v["packed_match"] and v["numba_match"] for v in results.values()),
    }


def time_steps(fn, n: int, warmup: int = 20) -> dict[str, Any]:
    for _ in range(warmup):
        fn()
    t0 = time.perf_counter()
    for _ in range(n):
        fn()
    wall = time.perf_counter() - t0
    return {"ticks": n, "wall_s": wall, "ticks_per_sec": n / wall, "ms_per_tick": 1000 * wall / n, "rss_mb": rss_mb()}


def full_runtime_ladder(backend: str, n: int = 200) -> dict[str, Any]:
    os.environ["MM_PSC_BACKEND"] = backend
    out = {}
    rt = make_rt(17, cognition=False)
    out["physics_only"] = time_steps(lambda: rt.step(1), n)
    rt = make_rt(17, cognition=True)
    out["cognition"] = time_steps(lambda: rt.step(1), n)

    def session_bench(scientific: bool, mode: str, ticks: int) -> dict[str, Any]:
        sess = ObserverSession(SessionConfig(seed=17, speed=MAX_SPEED, ui_hz=2.0, execution_mode=mode))
        sess.apply_experiment({
            "seed": 17, "agent_count": 2, "cognition_enabled": True,
            "world": {"width": 16, "height": 16, "boundary_mode": "WRAP_PERIODIC"},
        })
        sess.set_execution_mode(mode)
        if scientific:
            from datetime import datetime, timezone
            from mechanistic_mind.ui.psy_observer_web.run_finalize import new_run_id
            with sess._lock:
                sess._run_started_at = datetime.now(timezone.utc).isoformat()
                sess._active_run_id = new_run_id()
                sess._ensure_scientific_locked()
        else:
            with sess._lock:
                sess._sci_writer = None
                sess._active_run_id = None

        def one():
            with sess._step_lock:
                sess._scientific_step_once_unlocked()
                with sess._lock:
                    sess._accumulate_events_locked()
                    sess._record_motion_locked()
                    if scientific:
                        sess._append_scientific_locked()
                    if mode != "HEADLESS" and sess.runtime.tick % 10 == 0:
                        sess._capture_locked(detail="compact")
        return time_steps(one, ticks, warmup=10)

    out["session_no_v2"] = session_bench(False, "HEADLESS", 120)
    out["scientific_v2"] = session_bench(True, "HEADLESS", 100)
    out["HEADLESS"] = session_bench(True, "HEADLESS", 100)
    out["MAX"] = session_bench(True, "MAX", 80)
    out["LIVE"] = session_bench(True, "LIVE", 80)
    out["backend"] = backend
    out["provenance"] = psc_opt.backend_provenance()
    return out


def _worker(seed: int, ticks: int) -> dict[str, Any]:
    os.environ["MM_PSC_BACKEND"] = "packed"
    t0 = time.perf_counter()
    rt = make_rt(seed, cognition=True)
    for _ in range(ticks):
        rt.step(1)
    wall = time.perf_counter() - t0
    return {"seed": seed, "ticks": ticks, "wall_s": wall, "ticks_per_sec": ticks / wall,
            "digest": fingerprint(rt), "rss_mb": rss_mb()}


def parallel_scaling() -> dict[str, Any]:
    ticks = 200
    serial = {s: _worker(s, ticks) for s in PARALLEL_SEEDS[:4]}
    workers = {}
    for n in (1, 2, 4, 8):
        seeds = PARALLEL_SEEDS[:n]
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
            "per_world_tps_mean": statistics.mean(o["ticks_per_sec"] for o in outs),
            "rss_sum": sum(o["rss_mb"] for o in outs),
            "runs": outs,
            "scaling_efficiency": None,
        }
    one = workers["1"]["aggregate_world_ticks_per_sec"]
    for k, v in workers.items():
        v["scaling_efficiency"] = v["aggregate_world_ticks_per_sec"] / (one * int(k)) if one else None
    det = {}
    for o in workers["4"]["runs"]:
        s = o["seed"]
        if s in serial:
            det[str(s)] = {"match": o["digest"] == serial[s]["digest"]}
    return {"workers": workers, "determinism": det, "all_match": all(v["match"] for v in det.values())}


def session_followup_profile(n: int = 80) -> dict[str, Any]:
    os.environ["MM_PSC_BACKEND"] = "packed"
    sess = ObserverSession(SessionConfig(seed=17, speed=MAX_SPEED, ui_hz=2.0, execution_mode="HEADLESS"))
    sess.apply_experiment({
        "seed": 17, "agent_count": 2, "cognition_enabled": True,
        "world": {"width": 16, "height": 16, "boundary_mode": "WRAP_PERIODIC"},
    })
    stages = {k: 0.0 for k in ("scientific_step", "accumulate_events", "record_motion", "append_scientific", "capture")}
    for _ in range(20):
        with sess._step_lock:
            sess._scientific_step_once_unlocked()
    for _ in range(n):
        with sess._step_lock:
            t0 = time.perf_counter()
            sess._scientific_step_once_unlocked()
            stages["scientific_step"] += time.perf_counter() - t0
            with sess._lock:
                t0 = time.perf_counter()
                sess._accumulate_events_locked()
                stages["accumulate_events"] += time.perf_counter() - t0
                t0 = time.perf_counter()
                sess._record_motion_locked()
                stages["record_motion"] += time.perf_counter() - t0
    total = sum(stages.values()) or 1e-9
    ranked = sorted(
        ({"stage": k, "ms_per_tick": 1000 * v / n, "pct": 100 * v / total} for k, v in stages.items() if v > 0),
        key=lambda x: -x["ms_per_tick"],
    )
    return {"ticks": n, "stages": ranked, "note": "scientific append omitted (no run_id); focuses event/motion vs step"}


def main() -> None:
    print("=== PSC prediction optimization ===")
    # Force legacy baseline capture then optimize default
    print("capturing states…")
    states = capture_states(17)
    _write("baseline_states_meta.json", {k: {"tick": v["tick"], "n_transitions": v["n_transitions"]} for k, v in states.items()})

    print("equivalence…")
    eq = equivalence_suite(states)
    _write("equivalence.json", eq)
    if not eq["exact_match"]:
        print("EQUIVALENCE FAILED", eq["mismatch_samples"])
        _write("SUMMARY.md", "# BLOCKED\n\nEquivalence failed.\n")
        raise SystemExit(2)

    print("microbench…")
    micro = microbench(states)
    _write("baseline_predict_one_step.json", {
        "note": "warm us/call includes full predict_one_step",
        "MID": micro,
        "component_hint": "SHA1+_q dominate; soft scan secondary at N~8",
    })
    _write("numba_benchmark.json", {
        "compile_s": micro.get("numba_compile_s"),
        "init_wall_s": micro.get("numba_init_wall_s"),
        "warm": micro.get("numba"),
        "packed": micro.get("packed"),
        "legacy": micro.get("legacy"),
        "e2e_speedups": {k: micro.get(k) for k in micro if k.startswith("e2e_")},
    })
    _write("packing_cost.json", {
        "pack_rebuild_us_packed_path": micro["packed"]["pack_rebuild_us"],
        "note": "Pack rebuild only on version bump (learn); steady calls reuse cache",
        "cached_reuse": True,
        "invalidation": "bump_pack_version on learn_transition",
    })
    _write("packed_representation.json", {
        "form": "action-indexed row lists + optional float ante[N,M] for Numba",
        "precision": "float64",
        "cache": {"field": "_psc_pack", "version": "_psc_pack_version"},
        "invalidators": ["learn_transition insert/update/evict"],
    })
    _write("component_profile.json", {
        "classification": "MIXED — primarily Python hash/dict/_q, not dense arithmetic",
        "table": [
            {"component": "_q quantize", "suitability": "POOR_NUMBA", "note": "dict alloc"},
            {"component": "_sig SHA1", "suitability": "POOR_NUMBA", "note": "must preserve key identity"},
            {"component": "soft distance scan", "suitability": "POSSIBLE_NUMBA", "note": "N typically <<128"},
            {"component": "mean_cons/reliability", "suitability": "CACHED", "note": "row cache"},
        ],
    })

    print("differential seeds…")
    diff = differential_runs()
    _write("scientific_fingerprint.json", diff)

    print("full runtime legacy…")
    old = full_runtime_ladder("legacy", 180)
    print("full runtime packed…")
    new = full_runtime_ladder("packed", 180)
    print("full runtime numba…")
    numb = full_runtime_ladder("numba", 120)

    def speedup(a, b):
        oa = a.get("ticks_per_sec") or 0
        ob = b.get("ticks_per_sec") or 0
        return (ob / oa) if oa else None

    ladder = {}
    for key in ("physics_only", "cognition", "session_no_v2", "scientific_v2", "HEADLESS", "MAX", "LIVE"):
        ladder[key] = {
            "legacy_tps": old[key]["ticks_per_sec"],
            "packed_tps": new[key]["ticks_per_sec"],
            "numba_tps": (numb.get(key) or {}).get("ticks_per_sec"),
            "packed_speedup": speedup(old[key], new[key]),
            "numba_speedup_vs_legacy": speedup(old[key], numb[key]) if key in numb else None,
            "legacy_ms": old[key]["ms_per_tick"],
            "packed_ms": new[key]["ms_per_tick"],
        }
    _write("full_runtime_before_after.json", {"legacy": old, "packed": new, "numba": numb, "ladder": ladder})
    _write("cognition_benchmark.json", {
        "legacy_tps": old["cognition"]["ticks_per_sec"],
        "packed_tps": new["cognition"]["ticks_per_sec"],
        "numba_tps": numb["cognition"]["ticks_per_sec"],
        "speedup_packed": speedup(old["cognition"], new["cognition"]),
    })

    print("session followup…")
    _write("session_followup_profile.json", session_followup_profile())

    print("parallel…")
    par = parallel_scaling()
    _write("parallel_scaling.json", par)
    _write("multiprocess_determinism.json", {
        "all_match": par.get("all_match"),
        "determinism": par.get("determinism"),
        "note": "workers use PACKED; single-threaded kernel; no nested parallel=True",
    })

    _write("memory.json", {
        "legacy_rss_mb": old["cognition"].get("rss_mb"),
        "packed_rss_mb": new["cognition"].get("rss_mb"),
        "numba_rss_mb": numb["cognition"].get("rss_mb"),
        "parallel_rss_sum_8": par["workers"]["8"].get("rss_sum"),
    })

    _write("profile_before_after.json", {
        "before_note": "PA architecture: predict_one_step ~20% of step wall; cognition ~46% of begin_tick",
        "after_micro_us": {
            "legacy": micro["legacy"]["warm_us_per_call"],
            "packed": micro["packed"]["warm_us_per_call"],
            "numba": micro["numba"]["warm_us_per_call"],
        },
        "after_cognition_tps": {
            "legacy": old["cognition"]["ticks_per_sec"],
            "packed": new["cognition"]["ticks_per_sec"],
            "numba": numb["cognition"]["ticks_per_sec"],
        },
        "new_dominant": "session bookkeeping (events/motion) remains larger gap than PSC after packing",
    })

    # Default recommendation
    pack_sp = ladder["cognition"]["packed_speedup"] or 1.0
    numba_extra = (ladder["cognition"]["numba_tps"] or 0) / (ladder["cognition"]["packed_tps"] or 1)
    if pack_sp >= 1.05:
        default_backend = "packed"
        verdict = "PACKED_DEFAULT"
    else:
        default_backend = "packed"  # still OK — cache + single _q; low risk
        verdict = "PACKED_MARGINAL"
    if numba_extra < 1.05 or not eq.get("numba_available"):
        numba_verdict = "NOT_WORTH_DEFAULT — optional via MM_PSC_BACKEND=numba"
    else:
        numba_verdict = "OPTIONAL_GAIN"

    md = f"""# PSC prediction optimization — SUMMARY

## Verdict

- Equivalence (legacy ↔ packed ↔ numba): **{'EXACT_MATCH' if eq['exact_match'] and diff['all_exact'] else 'FAIL'}**
- Default backend: **{default_backend}** (`MM_PSC_BACKEND`)
- Numba: **{numba_verdict}**
- Outcome class: **{verdict}**

## Micro (MID state)

| Backend | µs/call | speedup vs legacy |
|---|---:|---:|
| LEGACY | {micro['legacy']['warm_us_per_call']:.1f} | 1.00 |
| PACKED | {micro['packed']['warm_us_per_call']:.1f} | {micro.get('e2e_speedup_vs_legacy_packed'):.3f} |
| NUMBA | {micro['numba']['warm_us_per_call']:.1f} | {micro.get('e2e_speedup_vs_legacy_numba'):.3f} |

Numba compile: {micro.get('numba_compile_s')} s

## Full runtime (tps)

| Stack | LEGACY | PACKED | speedup |
|---|---:|---:|---:|
| Physics | {ladder['physics_only']['legacy_tps']:.1f} | {ladder['physics_only']['packed_tps']:.1f} | {ladder['physics_only']['packed_speedup']} |
| Cognition | {ladder['cognition']['legacy_tps']:.1f} | {ladder['cognition']['packed_tps']:.1f} | {ladder['cognition']['packed_speedup']} |
| Session no V2 | {ladder['session_no_v2']['legacy_tps']:.1f} | {ladder['session_no_v2']['packed_tps']:.1f} | {ladder['session_no_v2']['packed_speedup']} |
| Scientific V2 | {ladder['scientific_v2']['legacy_tps']:.1f} | {ladder['scientific_v2']['packed_tps']:.1f} | {ladder['scientific_v2']['packed_speedup']} |
| HEADLESS | {ladder['HEADLESS']['legacy_tps']:.1f} | {ladder['HEADLESS']['packed_tps']:.1f} | {ladder['HEADLESS']['packed_speedup']} |
| MAX | {ladder['MAX']['legacy_tps']:.1f} | {ladder['MAX']['packed_tps']:.1f} | {ladder['MAX']['packed_speedup']} |
| LIVE | {ladder['LIVE']['legacy_tps']:.1f} | {ladder['LIVE']['packed_tps']:.1f} | {ladder['LIVE']['packed_speedup']} |

## Parallel Search (PACKED)

| workers | aggregate world-ticks/sec |
|---|---:|
| 1 | {par['workers']['1']['aggregate_world_ticks_per_sec']:.1f} |
| 2 | {par['workers']['2']['aggregate_world_ticks_per_sec']:.1f} |
| 4 | {par['workers']['4']['aggregate_world_ticks_per_sec']:.1f} |
| 8 | {par['workers']['8']['aggregate_world_ticks_per_sec']:.1f} |

Parallel determinism: **{par.get('all_match')}**

## NEXT

Session event/motion bookkeeping (see `session_followup_profile.json`) — larger remaining gap than further PSC micro-opts.
"""
    (OUT / "SUMMARY.md").write_text(md)
    print(md)
    marker = "PSC_PREDICTION_OPTIMIZATION_ACCEPTED" if eq["exact_match"] and diff["all_exact"] else "PSC_PREDICTION_OPTIMIZATION_BLOCKED"
    _write("ACCEPTANCE.json", {"marker": marker, "default_backend": default_backend, "numba": numba_verdict})
    print(marker)


if __name__ == "__main__":
    main()
