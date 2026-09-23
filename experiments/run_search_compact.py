#!/usr/bin/env python3
"""SEARCH_COMPACT evidence tier — equivalence, storage, performance, parallel."""
from __future__ import annotations

import hashlib
import json
import os
import resource
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "search_compact"
OUT.mkdir(parents=True, exist_ok=True)

SEEDS = (17, 23, 41, 59, 83)


def _write(name: str, obj) -> None:
    path = OUT / name
    if isinstance(obj, str):
        path.write_text(obj)
    else:
        path.write_text(json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n")
    print("wrote", path)


def _rss_kb() -> int:
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


def _runtime_digest(session) -> str:
    rt = session.runtime
    body = getattr(rt, "body", None)
    slots = getattr(rt, "slots", None)
    bodies = []
    if slots:
        for i, sl in enumerate(slots):
            b = getattr(sl, "body", None)
            if b is None:
                continue
            bodies.append({
                "i": i,
                "x": round(float(b.x), 8),
                "y": round(float(b.y), 8),
                "vx": round(float(b.vx), 8),
                "vy": round(float(b.vy), 8),
                "theta": round(float(getattr(b, "theta", 0.0)), 8),
            })
    elif body is not None:
        bodies.append({
            "i": 0,
            "x": round(float(body.x), 8),
            "y": round(float(body.y), 8),
            "vx": round(float(body.vx), 8),
            "vy": round(float(body.vy), 8),
            "theta": round(float(getattr(body, "theta", 0.0)), 8),
        })
    obs = getattr(rt, "last_agent_observation", None) or {}
    exo = {k: round(float(obs.get(k, 0) or 0), 8) for k in ("exo_0", "exo_1", "exo_2")}
    payload = {
        "tick": int(rt.tick),
        "seed": int(getattr(rt, "seed", 0)),
        "bodies": bodies,
        "exo": exo,
    }
    return hashlib.sha1(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _run_session(seed: int, ticks: int, evidence_mode: str, results_root: Path):
    from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig
    from mechanistic_mind.ui.psy_observer_web.run_finalize import new_run_id

    cfg = SessionConfig(
        seed=seed,
        ui_hz=1.0,
        execution_mode="HEADLESS",
        evidence_mode=evidence_mode,
        results_root=results_root,
        search_compact_trigger_threshold=5,
        search_compact_pre_window=16,
        search_compact_post_window=16,
        search_compact_max_candidates=4,
    )
    s = ObserverSession(cfg)
    s.set_execution_mode("HEADLESS")
    s.set_evidence_mode(evidence_mode)
    # Ensure run id for scientific writer
    if s._active_run_id is None:
        s._active_run_id = new_run_id()
        s._run_started_at = datetime.now(timezone.utc).isoformat()
    t0 = time.perf_counter()
    rss0 = _rss_kb()
    s.step(ticks)
    dt = time.perf_counter() - t0
    rss1 = _rss_kb()
    digest = _runtime_digest(s)
    # Close writers
    with s._lock:
        s._close_scientific_locked(clear_live_dir=False)
    live = s._sci_live_dir
    bytes_total = 0
    if live and live.exists():
        for p in live.rglob("*"):
            if p.is_file():
                bytes_total += p.stat().st_size
    return {
        "seed": seed,
        "ticks": ticks,
        "evidence_mode": evidence_mode,
        "seconds": dt,
        "ticks_per_sec": ticks / dt if dt > 0 else 0,
        "ms_per_tick": (dt * 1000) / ticks if ticks else 0,
        "rss_kb_delta": rss1 - rss0,
        "rss_kb_end": rss1,
        "digest": digest,
        "artifact_bytes": bytes_total,
        "bytes_per_tick": bytes_total / ticks if ticks else 0,
        "live_dir": str(live) if live else None,
        "final_tick": int(s.runtime.tick),
        "config_fingerprint": (
            s._resolved_mechanism_config.fingerprint()
            if s._resolved_mechanism_config is not None else None
        ),
    }


def _worker(args):
    seed, ticks, mode, root = args
    return _run_session(seed, ticks, mode, Path(root))


def main() -> int:
    scratch = OUT / "runs"
    scratch.mkdir(parents=True, exist_ok=True)

    # Contracts
    _write("evidence_mode.json", {
        "modes": ["FULL_SCIENTIFIC", "SEARCH_COMPACT"],
        "orthogonal_to": ["LIVE", "FAST", "MAX", "HEADLESS"],
        "principle": "Same runtime; different retained notebook",
    })
    _write("provenance_contract.json", {
        "required": [
            "run_id", "seed", "config_fingerprint", "mechanism_configuration_fingerprint",
            "world_dimensions", "agent_count", "target_ticks", "final_tick",
            "runtime_version", "evidence_mode", "start_end_status", "digest",
        ],
        "cognition_access": False,
    })
    _write("metric_inventory.json", {
        "metrics": [
            "tick_count", "distance_travelled", "visited_cells", "action_counts",
            "composite_motor_commands", "contact_ticks", "osc_emit_ticks",
            "osc_recv_ticks", "full_duplex_ticks", "vision_nonzero_ticks",
            "prediction_ticks",
        ],
        "forbidden_labels": [
            "curious", "social", "intelligent", "communicating", "hungry", "afraid", "goal-directed",
        ],
    })
    _write("rolling_window.json", {
        "pre_default": 32, "post_default": 32, "bounded": True, "hardcoded_huge_defaults": False,
    })
    _write("trigger_contract.json", {
        "interface": "TriggerFn(tick, runtime, events, metrics) -> dict|None",
        "observer_side": True,
        "consumes_runtime_rng": False,
        "alters_physics": False,
        "test_triggers": ["ACTION_COUNT_THRESHOLD", "FIRST_EVENT_TYPE"],
        "not_interestingness": True,
    })
    _write("candidate_contract.json", {
        "fields": [
            "candidate_id", "run_id", "seed", "config_fingerprint", "trigger_type",
            "trigger_tick", "trigger_values", "pre_window_range", "post_window_range",
            "metrics_at_trigger", "evidence",
        ],
        "no_interpretive_conclusions": True,
    })
    _write("worker_result_contract.json", {
        "SearchWorkerResult": [
            "run_id", "seed", "config_fingerprint", "target_tick", "final_tick",
            "status", "metrics", "triggers", "candidates", "digest", "artifact_paths",
        ],
        "intelligence_score": None,
    })

    # Equivalence FULL vs COMPACT
    equiv = []
    for seed in SEEDS:
        full = _run_session(seed, 120, "FULL_SCIENTIFIC", scratch / f"full_{seed}")
        compact = _run_session(seed, 120, "SEARCH_COMPACT", scratch / f"compact_{seed}")
        equiv.append({
            "seed": seed,
            "full_digest": full["digest"],
            "compact_digest": compact["digest"],
            "exact_match": full["digest"] == compact["digest"],
            "full_bytes_per_tick": full["bytes_per_tick"],
            "compact_bytes_per_tick": compact["bytes_per_tick"],
        })
    all_match = all(r["exact_match"] for r in equiv)
    _write("full_vs_compact_equivalence.json", {
        "verdict": "EXACT_MATCH" if all_match else "MISMATCH",
        "seeds": equiv,
    })
    _write("scientific_fingerprint.json", {
        "verdict": "EXACT_MATCH" if all_match else "MISMATCH",
        "note": "FULL_SCIENTIFIC vs SEARCH_COMPACT runtime digests across seeds",
    })
    _write("retained_event_equivalence.json", {
        "note": "COMPACT retains trigger windows only; FULL retains V2 timeline",
        "policy": "Retained compact window event type/tick must match FULL when both present",
        "status": "INFRASTRUCTURE_READY",
    })

    # Storage / performance at 2k ticks (practical); extrapolate
    bench_ticks = 2000
    full_b = _run_session(17, bench_ticks, "FULL_SCIENTIFIC", scratch / "bench_full")
    compact_b = _run_session(17, bench_ticks, "SEARCH_COMPACT", scratch / "bench_compact")
    ratio = (full_b["artifact_bytes"] / compact_b["artifact_bytes"]) if compact_b["artifact_bytes"] else None

    def estimate(bytes_per_tick: float, n: int) -> dict:
        return {"ticks": n, "bytes": bytes_per_tick * n, "MB": (bytes_per_tick * n) / (1024 * 1024)}

    storage = {
        "measured_ticks": bench_ticks,
        "FULL_SCIENTIFIC": {
            "bytes_per_tick": full_b["bytes_per_tick"],
            "bytes_total": full_b["artifact_bytes"],
            "ticks_per_sec": full_b["ticks_per_sec"],
        },
        "SEARCH_COMPACT_no_or_triggered": {
            "bytes_per_tick": compact_b["bytes_per_tick"],
            "bytes_total": compact_b["artifact_bytes"],
            "ticks_per_sec": compact_b["ticks_per_sec"],
        },
        "compression_ratio_full_over_compact": ratio,
        "estimates": {
            "10k": {
                "FULL": estimate(full_b["bytes_per_tick"], 10_000),
                "COMPACT": estimate(compact_b["bytes_per_tick"], 10_000),
            },
            "100k": {
                "FULL": estimate(full_b["bytes_per_tick"], 100_000),
                "COMPACT": estimate(compact_b["bytes_per_tick"], 100_000),
            },
            "1M": {
                "FULL": estimate(full_b["bytes_per_tick"], 1_000_000),
                "COMPACT": estimate(compact_b["bytes_per_tick"], 1_000_000),
            },
            "10M": {
                "FULL": estimate(full_b["bytes_per_tick"], 10_000_000),
                "COMPACT": estimate(compact_b["bytes_per_tick"], 10_000_000),
            },
        },
    }
    _write("storage_benchmark.json", storage)
    _write("performance_benchmark.json", {
        "HEADLESS_FULL_SCIENTIFIC": full_b,
        "HEADLESS_SEARCH_COMPACT": compact_b,
        "disk_MB_s_full": (full_b["artifact_bytes"] / (1024 * 1024)) / max(full_b["seconds"], 1e-9),
        "disk_MB_s_compact": (compact_b["artifact_bytes"] / (1024 * 1024)) / max(compact_b["seconds"], 1e-9),
    })

    # Memory slope
    slope = []
    for n in (200, 1000, 2000):
        r = _run_session(17, n, "SEARCH_COMPACT", scratch / f"slope_{n}")
        slope.append({
            "ticks": n,
            "rss_kb_end": r["rss_kb_end"],
            "artifact_bytes": r["artifact_bytes"],
            "bytes_per_tick": r["bytes_per_tick"],
        })
    _write("memory_slope.json", {
        "points": slope,
        "expected": "no O(total ticks) RAM for metrics; visited_cells ≤ world cells",
    })

    # Parallel workers
    parallel = {}
    for n_workers in (1, 2, 4, 8):
        root = scratch / f"par_{n_workers}"
        root.mkdir(exist_ok=True)
        jobs = [(SEEDS[i % len(SEEDS)], 400, "SEARCH_COMPACT", str(root / f"w{i}")) for i in range(n_workers)]
        t0 = time.perf_counter()
        results = []
        if n_workers == 1:
            results = [_worker(jobs[0])]
        else:
            with ProcessPoolExecutor(max_workers=n_workers) as ex:
                futs = [ex.submit(_worker, j) for j in jobs]
                for f in as_completed(futs):
                    results.append(f.result())
        dt = time.perf_counter() - t0
        total_ticks = sum(r["ticks"] for r in results)
        parallel[str(n_workers)] = {
            "workers": n_workers,
            "wall_seconds": dt,
            "aggregate_world_ticks_per_sec": total_ticks / dt if dt else 0,
            "per_world_ticks_per_sec_mean": sum(r["ticks_per_sec"] for r in results) / len(results),
            "digests": [r["digest"] for r in results],
            "scaling_efficiency": None,
        }
    base = parallel["1"]["aggregate_world_ticks_per_sec"] or 1
    for k, v in parallel.items():
        n = int(k)
        v["scaling_efficiency"] = (v["aggregate_world_ticks_per_sec"] / (base * n)) if n else None
    _write("parallel_scaling.json", parallel)

    _write("analyzer_compatibility.json", {
        "FULL_SCIENTIFIC": "ANALYZER_FULL_COMPATIBLE",
        "SEARCH_COMPACT_default": "COMPACT_ONLY",
        "SEARCH_COMPACT_candidate_window": "CANDIDATE_WINDOW_COMPATIBLE",
        "signal_forensics": "Must report evidence limitations for COMPACT",
        "observe_v2": "Live frame OK; historical compact limited",
    })
    _write("search_dimensions.json", {
        "note": "Classification only — not every UI control is searchable",
        "SEARCH_SAFE_DIMENSION": ["seed", "vision_radius", "ecology_preset"],
        "FIXED_SCIENTIFIC_CONSTANT": ["dt", "action_repertoire_schema", "world_boundary_topology"],
        "NOT_SEARCHABLE_BY_DESIGN": ["observer_hz", "execution_mode", "evidence_mode"],
    })
    _write("scheduler_boundary.json", {
        "flow": "SEARCH SCHEDULER → workers → SEARCH_COMPACT runtime → SearchWorkerResult",
        "future": [
            "generate configs/seeds",
            "dispatch workers",
            "receive compact results",
            "preserve candidates",
            "rerun candidates under FULL_SCIENTIFIC",
        ],
        "ready_for_scheduler": all_match,
    })

    summary = f"""# SEARCH_COMPACT Summary

Generated: {datetime.now(timezone.utc).isoformat()}

## Equivalence
{('EXACT_MATCH' if all_match else 'MISMATCH')} across seeds {list(SEEDS)}

## Storage (measured {bench_ticks} ticks)
- FULL bytes/tick: {full_b['bytes_per_tick']:.1f}
- COMPACT bytes/tick: {compact_b['bytes_per_tick']:.1f}
- Ratio FULL/COMPACT: {ratio}

## Performance HEADLESS
- FULL: {full_b['ticks_per_sec']:.1f} t/s
- COMPACT: {compact_b['ticks_per_sec']:.1f} t/s

## Parallel aggregate t/s
{json.dumps({k: v['aggregate_world_ticks_per_sec'] for k,v in parallel.items()}, indent=2)}
"""
    _write("SUMMARY.md", summary)
    return 0 if all_match else 1


if __name__ == "__main__":
    raise SystemExit(main())
