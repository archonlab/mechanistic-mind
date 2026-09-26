#!/usr/bin/env python3
"""Scientific Telemetry V2 — storage audit, equivalence, long-run benchmark."""
from __future__ import annotations

import hashlib
import json
import os
import resource
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from mechanistic_mind.ui.psy_observer_web.scientific_history import (  # noqa: E402
    ScientificHistoryWriter,
    collect_scientific_tick_rows,
    load_evidence_package,
)
from mechanistic_mind.ui.psy_observer_web.scientific_telemetry_v2 import (  # noqa: E402
    TELEMETRY_MODE_V1,
    TELEMETRY_MODE_V2,
    evidence_requirements_matrix,
    event_exhaustiveness_policy,
    write_json,
)
from mechanistic_mind.ui.psy_observer_web.session import (  # noqa: E402
    ObserverSession,
    SessionConfig,
)
from mechanistic_mind.ui.psy_observer_web.run_finalize import new_run_id  # noqa: E402

OUT = Path("results/performance/scientific_telemetry_v2")
SEED = 17


def rss_mb() -> float:
    return float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) / 1024.0


def sci_fp(rt) -> str:
    slots = getattr(rt, "slots", None) or [rt]
    bodies = []
    actions = []
    for s in slots:
        bodies.append({
            "x": round(float(s.body.x), 8),
            "y": round(float(s.body.y), 8),
            "vx": round(float(s.body.vx), 8),
            "vy": round(float(s.body.vy), 8),
            "seed": int(s.seed),
        })
        actions.append(getattr(s, "last_selected_action", None))
    payload = {
        "tick": int(rt.tick),
        "bodies": bodies,
        "actions": actions,
        "T_sum": round(float(rt.world.T.sum()), 6),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def make_session(results_root: Path, *, mode: str, target: int) -> ObserverSession:
    os.environ["SCIENTIFIC_TELEMETRY_MODE"] = mode
    sess = ObserverSession(
        SessionConfig(
            seed=SEED,
            cognition_enabled=True,
            buffer_capacity=128,
            ui_hz=10.0,
            speed=50.0,
            target_tick=target,
            results_root=results_root,
        )
    )
    sess.apply_experiment({
        "seed": SEED,
        "world": {"width": 24, "height": 24, "boundary_mode": "WRAP_PERIODIC"},
        "agent_count": 2,
        "cognition_enabled": True,
        "mechanisms": {
            "cognition_enabled": True,
            "experimental_physical_signal": True,
            "physical_near_field_vision": True,
            "illumination_cycle": True,
            "physical_body_optical_response": True,
            "spatiotemporal_climate_ecology": False,
            "prospective_scenario_competition": True,
        },
        "observer": {"ui_hz": 10, "buffer_capacity": 128, "speed": 50},
    })
    sess._run_started_at = datetime.now(timezone.utc).isoformat()
    sess._active_run_id = new_run_id()
    with sess._lock:
        # Re-open writer with explicit mode (env may have been read at first open).
        sess._close_scientific_locked()
        from mechanistic_mind.ui.psy_observer_web.scientific_history import live_scientific_dir

        live = live_scientific_dir(sess._results_root(), sess._active_run_id)
        writer = ScientificHistoryWriter(live, telemetry_mode=mode, checkpoint_every=10_000)
        writer.open({
            "run_id": sess._active_run_id,
            "seed": SEED,
            "agent_count": 2,
            "runtime_type": type(sess.runtime).__name__,
        })
        sess._sci_writer = writer
        sess._sci_live_dir = live
    return sess


def scientific_only(sess: ObserverSession, n: int) -> list[float]:
    samples = []
    for _ in range(n):
        t0 = time.perf_counter()
        with sess._step_lock:
            sess._scientific_step_once_unlocked()
            with sess._lock:
                sess._accumulate_events_locked()
                sess._record_motion_locked()
                sess._append_scientific_locked()
        samples.append((time.perf_counter() - t0) * 1000.0)
    return samples


def dir_bytes(d: Path) -> dict[str, int]:
    out = {}
    total = 0
    if not d.is_dir():
        return {"total": 0}
    for p in d.iterdir():
        if p.is_file():
            sz = p.stat().st_size
            out[p.name] = sz
            total += sz
    out["total"] = total
    return out


def analyzer_fingerprint_from_dir(live: Path) -> dict:
    """Python-side Analyzer-comparable fingerprint (mirrors scientificCoreFingerprint)."""
    pkg = load_evidence_package(evidence_dir=live, runtime_status="STOPPED", run_id=live.name)
    rows = pkg.get("scientific_rows") or []
    events = pkg.get("events") or []
    by_agent: dict[str, dict] = {}
    ticks = set()
    contact_ticks = set()
    for r in rows:
        aid = str(r.get("agent_id") or "agent_0")
        ticks.add(int(r["tick"]))
        if r.get("contact"):
            contact_ticks.add(int(r["tick"]))
        a = by_agent.setdefault(aid, {
            "wait": 0, "move": 0, "scenario_selected": 0, "scenario_wait": 0,
            "scenario_move": 0, "discrete": 0, "deform": 0, "conversion": 0,
            "emit": 0, "recv": 0, "xs": [],
        })
        act = str(r.get("action") or "")
        if act == "WAIT":
            a["wait"] += 1
        elif act.startswith("MOVE"):
            a["move"] += 1
        a["xs"].append((float(r.get("x") or 0), float(r.get("y") or 0)))

    for ev in events:
        et = str(ev.get("type") or ev.get("kind") or "")
        evidence = ev.get("evidence") or {}
        if et == "SCENARIO_SELECTED":
            aid = str(ev.get("actor_agent_id") or ev.get("agent_id") or evidence.get("actor_agent_id") or "agent_0")
            a = by_agent.setdefault(aid, {
                "wait": 0, "move": 0, "scenario_selected": 0, "scenario_wait": 0,
                "scenario_move": 0, "discrete": 0, "deform": 0, "conversion": 0,
                "emit": 0, "recv": 0, "xs": [],
            })
            a["scenario_selected"] += 1
            act = str(evidence.get("selected_action") or evidence.get("action") or "")
            if act == "WAIT":
                a["scenario_wait"] += 1
            elif act.startswith("MOVE"):
                a["scenario_move"] += 1
        if et == "DISCRETE_ACTION_SELECTED":
            aid = str(ev.get("actor_agent_id") or ev.get("agent_id") or "agent_0")
            by_agent.setdefault(aid, {
                "wait": 0, "move": 0, "scenario_selected": 0, "scenario_wait": 0,
                "scenario_move": 0, "discrete": 0, "deform": 0, "conversion": 0,
                "emit": 0, "recv": 0, "xs": [],
            })["discrete"] += 1
        if "DEFORM" in et:
            aid = str(ev.get("agent_id") or "agent_0")
            by_agent.setdefault(aid, {
                "wait": 0, "move": 0, "scenario_selected": 0, "scenario_wait": 0,
                "scenario_move": 0, "discrete": 0, "deform": 0, "conversion": 0,
                "emit": 0, "recv": 0, "xs": [],
            })["deform"] += 1
        if "CONVERSION" in et or "RESOURCE_CONVERTED" in et:
            aid = str(ev.get("agent_id") or "agent_0")
            by_agent.setdefault(aid, {
                "wait": 0, "move": 0, "scenario_selected": 0, "scenario_wait": 0,
                "scenario_move": 0, "discrete": 0, "deform": 0, "conversion": 0,
                "emit": 0, "recv": 0, "xs": [],
            })["conversion"] += 1
        if "SIGNAL_EMITTED" in et:
            aid = str(ev.get("emitter_agent_id") or evidence.get("emitter_agent_id") or "UNKNOWN")
            if aid.startswith("agent_"):
                by_agent.setdefault(aid, {
                    "wait": 0, "move": 0, "scenario_selected": 0, "scenario_wait": 0,
                    "scenario_move": 0, "discrete": 0, "deform": 0, "conversion": 0,
                    "emit": 0, "recv": 0, "xs": [],
                })["emit"] += 1
        if "SIGNAL_RECEIVED" in et:
            aid = str(ev.get("receiver_agent_id") or evidence.get("receiver_agent_id") or "agent_0")
            by_agent.setdefault(aid, {
                "wait": 0, "move": 0, "scenario_selected": 0, "scenario_wait": 0,
                "scenario_move": 0, "discrete": 0, "deform": 0, "conversion": 0,
                "emit": 0, "recv": 0, "xs": [],
            })["recv"] += 1

    # Path length (unwrapped not needed for equality of same run length)
    agents_out = {}
    for aid, a in by_agent.items():
        dist = 0.0
        xs = a["xs"]
        for i in range(1, len(xs)):
            dx = xs[i][0] - xs[i - 1][0]
            dy = xs[i][1] - xs[i - 1][1]
            dist += (dx * dx + dy * dy) ** 0.5
        agents_out[aid] = {
            "wait": a["wait"],
            "move": a["move"],
            "dist": round(dist, 6),
            "scenario_selected": a["scenario_selected"],
            "scenario_wait": a["scenario_wait"],
            "scenario_move": a["scenario_move"],
            "discrete": a["discrete"],
            "deform": a["deform"],
            "conversion": a["conversion"],
            "emit": a["emit"],
            "recv": a["recv"],
        }

    # Vision exposure ticks
    exposure = 0
    for r in rows:
        vo = r.get("vision_optical") or {}
        if vo.get("body_exposure"):
            exposure += 1

    return {
        "telemetry_schema": pkg.get("telemetry_schema"),
        "coverage": pkg.get("coverage"),
        "unique_ticks": len(ticks),
        "contact_ticks": len(contact_ticks),
        "first_contact": min(contact_ticks) if contact_ticks else None,
        "agents": agents_out,
        "body_exposure_ticks": exposure,
        "event_count": len(events),
        "row_count": len(rows),
    }


def vf_exposure_series(live: Path) -> list[tuple[int, str, bool]]:
    pkg = load_evidence_package(evidence_dir=live, runtime_status="STOPPED")
    out = []
    for r in pkg.get("scientific_rows") or []:
        vo = r.get("vision_optical") or {}
        out.append((int(r["tick"]), str(r.get("agent_id")), bool(vo.get("body_exposure"))))
    return out


def run_mode(mode: str, n: int, root: Path) -> dict:
    print(f"[bench] mode={mode} n={n}", flush=True)
    rss0 = rss_mb()
    sess = make_session(root / mode, mode=mode, target=n)
    t0 = time.perf_counter()
    samples = scientific_only(sess, n)
    wall = time.perf_counter() - t0
    with sess._lock:
        if sess._sci_writer:
            sess._sci_writer.flush()
            sess._sci_writer.close()
    live = sess._sci_live_dir
    assert live is not None
    sizes = dir_bytes(live)
    rss1 = rss_mb()
    fp = sci_fp(sess.runtime)
    analysis = analyzer_fingerprint_from_dir(live)
    vf = vf_exposure_series(live)
    return {
        "mode": mode,
        "ticks": n,
        "wall_s": wall,
        "tick_ms_mean": sum(samples) / max(1, len(samples)),
        "bytes": sizes,
        "bytes_per_tick": sizes["total"] / max(1, n),
        "rss_start_mb": rss0,
        "rss_end_mb": rss1,
        "rss_delta_mb": rss1 - rss0,
        "sci_fingerprint": fp,
        "analyzer": analysis,
        "vf_exposure_hash": hashlib.sha256(
            json.dumps(vf, separators=(",", ":")).encode()
        ).hexdigest(),
        "live_dir": str(live),
        "writer_seen_ticks": len(getattr(sess._sci_writer, "_seen_by_tick", {}) or {}),
    }


def v1_storage_breakdown_from_existing() -> dict:
    """Ranked breakdown from Phase-1 10k live if present."""
    base = Path("results/performance/long_run_observer_audit/runs/psychology_observer/psy_observer_web")
    candidates = sorted(base.glob(".live-*")) if base.is_dir() else []
    if not candidates:
        return {"available": False}
    live = candidates[-1]
    sizes = dir_bytes(live)
    # Sample first 200 event lines for type histogram
    ev_path = live / "scientific_events.jsonl"
    type_bytes: dict[str, int] = {}
    type_n: dict[str, int] = {}
    if ev_path.is_file():
        with ev_path.open("r", encoding="utf-8") as fh:
            for i, line in enumerate(fh):
                if i >= 5000:
                    break
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                et = str(row.get("type") or row.get("kind") or "?")
                b = len(line.encode("utf-8"))
                type_bytes[et] = type_bytes.get(et, 0) + b
                type_n[et] = type_n.get(et, 0) + 1
    ranked = sorted(type_bytes.items(), key=lambda kv: -kv[1])[:20]
    return {
        "available": True,
        "sample_dir": str(live),
        "file_bytes": sizes,
        "event_type_sample_top": [
            {"type": t, "bytes": b, "n": type_n[t], "avg_b": b / max(1, type_n[t])}
            for t, b in ranked
        ],
        "notes": (
            "Phase-1 audit: ~41 KB/tick with ~73% events (SCENARIO_SELECTED dominant) "
            "and ~27% timeline (vision_optical + GEO nests)."
        ),
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    max_n = int(os.environ.get("ST_V2_MAX_TICK", "10000"))
    checkpoints = [n for n in (1_000, 10_000, 50_000) if n <= max_n]
    if not checkpoints:
        checkpoints = [min(1_000, max_n)]

    breakdown = v1_storage_breakdown_from_existing()
    write_json(OUT / "v1_storage_breakdown.json", breakdown)
    write_json(OUT / "evidence_requirements_matrix.json", {
        "matrix": evidence_requirements_matrix(),
        "exhaustiveness": event_exhaustiveness_policy(),
    })

    def core(x):
        return {
            "unique_ticks": x["analyzer"]["unique_ticks"],
            "contact_ticks": x["analyzer"]["contact_ticks"],
            "first_contact": x["analyzer"]["first_contact"],
            "agents": {
                k: {kk: vv for kk, vv in v.items() if kk != "xs"}
                for k, v in x["analyzer"]["agents"].items()
            },
            "body_exposure_ticks": x["analyzer"]["body_exposure_ticks"],
        }

    # Simulation equivalence short run
    with tempfile.TemporaryDirectory(dir=str(OUT)) as td:
        td_path = Path(td)
        a = run_mode(TELEMETRY_MODE_V1, 120, td_path / "equiv")
        b = run_mode(TELEMETRY_MODE_V2, 120, td_path / "equiv")
        sim_match = a["sci_fingerprint"] == b["sci_fingerprint"]
        ana_match = core(a) == core(b)
        vf_match = a["vf_exposure_hash"] == b["vf_exposure_hash"]
        equiv = {
            "simulation_exact_match": sim_match,
            "analyzer_core_exact_match": ana_match,
            "vf_exposure_exact_match": vf_match,
            "v1": {"sci_fp": a["sci_fingerprint"], "analyzer": a["analyzer"], "bpt": a["bytes_per_tick"]},
            "v2": {"sci_fp": b["sci_fingerprint"], "analyzer": b["analyzer"], "bpt": b["bytes_per_tick"]},
        }
        write_json(OUT / "equivalence_120.json", equiv)
        print(f"[equiv] sim={sim_match} analyzer={ana_match} vf={vf_match}", flush=True)
        if not (sim_match and ana_match and vf_match):
            print("[equiv] FAILED detail:", json.dumps(equiv, indent=2)[:2000], flush=True)

    # Storage benchmarks
    bench_rows = []
    root = OUT / "bench_runs"
    root.mkdir(parents=True, exist_ok=True)
    for n in checkpoints:
        v1 = run_mode(TELEMETRY_MODE_V1, n, root)
        v2 = run_mode(TELEMETRY_MODE_V2, n, root)
        ratio = (v1["bytes_per_tick"] / v2["bytes_per_tick"]) if v2["bytes_per_tick"] else None
        row = {
            "ticks": n,
            "v1_bytes_per_tick": v1["bytes_per_tick"],
            "v2_bytes_per_tick": v2["bytes_per_tick"],
            "compression_ratio_v1_over_v2": ratio,
            "v1_file_bytes": v1["bytes"],
            "v2_file_bytes": v2["bytes"],
            "v1_tick_ms": v1["tick_ms_mean"],
            "v2_tick_ms": v2["tick_ms_mean"],
            "v1_rss_delta_mb": v1["rss_delta_mb"],
            "v2_rss_delta_mb": v2["rss_delta_mb"],
            "sim_match": v1["sci_fingerprint"] == v2["sci_fingerprint"],
            "analyzer_match": core(v1) == core(v2),
            "vf_match": v1["vf_exposure_hash"] == v2["vf_exposure_hash"],
        }
        bench_rows.append(row)
        print(
            f"[bench] n={n} v1={v1['bytes_per_tick']:.0f} B/t v2={v2['bytes_per_tick']:.0f} B/t "
            f"ratio={ratio:.1f}x sim={row['sim_match']} ana={row['analyzer_match']}",
            flush=True,
        )

    # Steady-state from largest checkpoint
    last = bench_rows[-1] if bench_rows else None
    estimates = {}
    if last:
        bpt = last["v2_bytes_per_tick"]
        estimates = {
            "v2_bytes_per_tick_steady": bpt,
            "est_100k_mb": bpt * 100_000 / (1024 * 1024),
            "est_1M_gb": bpt * 1_000_000 / (1024 ** 3),
            "est_10M_gb": bpt * 10_000_000 / (1024 ** 3),
            "v1_bytes_per_tick": last["v1_bytes_per_tick"],
            "target_4kb": bpt <= 4096,
            "stretch_2kb": bpt <= 2048,
        }

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "checkpoints": bench_rows,
        "estimates": estimates,
        "equivalence_120": equiv,
        "v1_breakdown_ref": breakdown.get("notes"),
    }
    write_json(OUT / "benchmark.json", report)

    md = [
        "# Scientific Telemetry V2 — benchmark",
        "",
        f"Generated: {report['generated_at']}",
        "",
        "## Bytes/tick",
        "",
        "| ticks | V1 B/tick | V2 B/tick | ratio | sim | analyzer | VF |",
        "|---:|---:|---:|---:|:---:|:---:|:---:|",
    ]
    for r in bench_rows:
        md.append(
            f"| {r['ticks']} | {r['v1_bytes_per_tick']:.0f} | {r['v2_bytes_per_tick']:.0f} | "
            f"{r['compression_ratio_v1_over_v2']:.1f}× | {r['sim_match']} | {r['analyzer_match']} | {r['vf_match']} |"
        )
    md.extend([
        "",
        "## Estimates (V2 steady-state)",
        "",
        "```json",
        json.dumps(estimates, indent=2),
        "```",
        "",
        f"## Equivalence (120 ticks): sim={equiv['simulation_exact_match']} "
        f"analyzer={equiv['analyzer_core_exact_match']} vf={equiv['vf_exposure_exact_match']}",
        "",
    ])
    (OUT / "benchmark.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    ok = equiv["simulation_exact_match"] and equiv["analyzer_core_exact_match"] and equiv["vf_exposure_exact_match"]
    if last and not last["sim_match"]:
        ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
