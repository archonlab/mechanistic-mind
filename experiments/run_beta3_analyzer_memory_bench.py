"""Memory benchmark for bounded Analyzer (SHORT/MEDIUM/LONG/STRESS)."""
from __future__ import annotations

import json
import os
import resource
import tempfile
import time
from pathlib import Path


def _rss_kb() -> int:
    with open("/proc/self/status", encoding="utf-8") as f:
        for line in f:
            if line.startswith("VmRSS:"):
                return int(line.split()[1])
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss


def _write_synthetic(dir_path: Path, n_ticks: int, n_agents: int = 2) -> int:
    dir_path.mkdir(parents=True, exist_ok=True)
    meta = {
        "schema": "mm.scientific_v3.core.v1",
        "run_id": f"synth-{n_ticks}",
        "coverage": {"dimensions": {}},
    }
    (dir_path / "scientific_v3_meta.json").write_text(json.dumps(meta))
    (dir_path / "identity_map.json").write_text(json.dumps({"bodies": [f"body-{i}" for i in range(n_agents)]}))
    spine = (dir_path / "scientific_spine.jsonl").open("w")
    obs = (dir_path / "scientific_observations.jsonl").open("w")
    dec = (dir_path / "scientific_decisions.jsonl").open("w")
    mot = (dir_path / "scientific_motors.jsonl").open("w")
    cons = (dir_path / "scientific_consequences.jsonl").open("w")
    tl = (dir_path / "scientific_timeline.jsonl").open("w")
    ev = (dir_path / "scientific_events.jsonl").open("w")
    bytes_in = 0
    for t in range(1, n_ticks + 1):
        for i in range(n_agents):
            aid = f"agent_{i}"
            bid = f"body-{i}"
            oid, did, mid, cid = f"o{t}{i}", f"d{t}{i}", f"m{t}{i}", f"c{t}{i}"
            s = json.dumps({
                "tick": t, "cognitive_agent_id": aid, "physical_body_id": bid,
                "observation_id": oid, "decision_id": did, "motor_id": mid, "consequence_id": cid,
            }) + "\n"
            spine.write(s)
            o = json.dumps({
                "tick": t, "cognitive_agent_id": aid, "physical_body_id": bid, "observation_id": oid,
                "accessible": {"local.FIELD_A": 0.1 * (t % 7), "exo_0": 0.2, "body.T": 0.5},
                "provenance": "AGENT_ACCESSIBLE",
            }) + "\n"
            obs.write(o)
            d = json.dumps({
                "tick": t, "cognitive_agent_id": aid, "physical_body_id": bid,
                "observation_id": oid, "decision_id": did, "motor_id": mid,
                "selection_path": "COMPOSITE", "selection_source": "COMPOSITE_FACTORIZED",
                "selection_mode": "X", "selected_action_legacy": "MOVE:E",
                "selected_candidate_id": "c1", "candidate_count": 2,
            }) + "\n"
            dec.write(d)
            m = json.dumps({
                "tick": t, "cognitive_agent_id": aid, "physical_body_id": bid,
                "decision_id": did, "motor_id": mid, "motor_schema": "COMPOSITE_MOTOR_V1",
                "components": {"locomotion": "MOVE:E" if t % 5 else "WAIT", "neck": "NECK_HOLD", "oscillator": {}, "push": False},
            }) + "\n"
            mot.write(m)
            c = json.dumps({
                "physical_body_id": bid, "tick_from": t, "tick_to": t + 1,
                "motor_id": mid, "consequence_id": cid,
                "pose_delta": {"dx": 0.1, "dy": 0.0},
                "orientation_delta": {"dtheta": 0.0},
                "resource_delta": {}, "attribution": "MOTOR",
            }) + "\n"
            cons.write(c)
            r = json.dumps({
                "tick": t, "agent_id": aid, "body_id": bid, "x": (t * 0.1 + i) % 32,
                "y": 8.0 + i, "vx": 0.1, "vy": 0.0, "theta": 0.0,
                "head_world_heading": 0.1, "contact": False,
                "resource_A": 1.0, "resource_B": 1.0, "work": 0.0,
                "action": "MOVE:E", "vision_optical": {"body_exposure": t % 11 == 0, "foreign_body_total": 0.2},
            }) + "\n"
            tl.write(r)
            if t % 9 == 0:
                e = json.dumps({
                    "tick": t, "type": "PHYSICAL_SIGNAL_EMITTED",
                    "evidence": {"emitter_agent_id": aid, "channel": "A", "emission_id": f"e{t}{i}"},
                }) + "\n"
                ev.write(e)
            bytes_in += len(s) + len(o) + len(d) + len(m) + len(c) + len(r)
    for fh in (spine, obs, dec, mot, cons, tl, ev):
        fh.close()
    (dir_path / "scientific_meta.json").write_text(json.dumps({
        "last_tick_written": n_ticks, "rows_written": n_ticks * n_agents, "events_written": 0,
    }))
    return bytes_in


def bench_one(n_ticks: int) -> dict:
    from mechanistic_mind.scientific_v3.analyzer_next.pipeline import build_behavioral_reconstruction

    td = Path(tempfile.mkdtemp(prefix=f"mm_an_{n_ticks}_"))
    nbytes = _write_synthetic(td, n_ticks)
    baseline = _rss_kb()
    t0 = time.perf_counter()
    out = td / "out"
    payload = build_behavioral_reconstruction(td, write_artifacts=True, artifact_dir=out)
    wall = time.perf_counter() - t0
    peak = _rss_kb()
    art = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    return {
        "label": None,
        "ticks": n_ticks,
        "input_bytes": nbytes,
        "wall_s": round(wall, 4),
        "baseline_rss_kb": baseline,
        "peak_rss_kb": peak,
        "delta_rss_kb": peak - baseline,
        "output_bytes": art,
        "tick_stories": payload.get("tick_stories_count"),
        "episodes": sum((payload.get("episode_counts") or {}).values()) if isinstance(payload.get("episode_counts"), dict) else None,
        "complete_odmc": payload.get("complete_odmc"),
    }


def main() -> None:
    rows = []
    for label, n in (("SHORT", 1000), ("MEDIUM", 5000), ("LONG", 20000), ("STRESS", 50000)):
        row = bench_one(n)
        row["label"] = label
        rows.append(row)
        print(row, flush=True)
    out = Path("results/beta3_analyzer_memory")
    out.mkdir(parents=True, exist_ok=True)
    (out / "memory_benchmark.json").write_text(json.dumps(rows, indent=2))
    keys = ["label", "ticks", "input_bytes", "wall_s", "baseline_rss_kb", "peak_rss_kb", "delta_rss_kb", "output_bytes", "tick_stories", "episodes"]
    lines = [",".join(keys)]
    for r in rows:
        lines.append(",".join(str(r.get(k, "")) for k in keys))
    (out / "memory_benchmark.csv").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
