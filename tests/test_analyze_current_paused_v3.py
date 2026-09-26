"""Paused Analyze Current: archive countable ≠ reconstruction consumed."""
from __future__ import annotations

import json
from pathlib import Path

from mechanistic_mind.scientific_v3.analyzer_next.job import run_job
from mechanistic_mind.ui.psy_observer_web.scientific_history import load_evidence_package

N_TICKS = 2034
N_AGENTS = 2
N_STORIES = N_TICKS * N_AGENTS


def write_paused_two_agent_v3(dir_path: Path, n_ticks: int = N_TICKS) -> None:
    """Complete V3 O→D→M→C + timeline/events representing a paused TwoAgentRuntime."""
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / "scientific_v3_meta.json").write_text(json.dumps({
        "schema": "mm.scientific_v3.core.v1",
        "run_id": "psyweb-paused-t2034",
        "coverage": {"dimensions": {
            "identity": "COMPLETE", "observation": "COMPLETE",
            "decision": "COMPLETE", "composite_motor": "COMPLETE", "consequence": "COMPLETE",
        }},
    }))
    (dir_path / "identity_map.json").write_text(json.dumps({
        "bodies": [{"physical_body_id": f"body-{i}", "cognitive_agent_id": f"agent_{i}"} for i in range(N_AGENTS)],
    }))
    (dir_path / "scientific_meta.json").write_text(json.dumps({
        "last_tick_written": n_ticks,
        "rows_written": n_ticks * N_AGENTS,
        "events_written": n_ticks,
        "agent_count": N_AGENTS,
    }))
    spine = (dir_path / "scientific_spine.jsonl").open("w")
    obs = (dir_path / "scientific_observations.jsonl").open("w")
    dec = (dir_path / "scientific_decisions.jsonl").open("w")
    mot = (dir_path / "scientific_motors.jsonl").open("w")
    cons = (dir_path / "scientific_consequences.jsonl").open("w")
    tl = (dir_path / "scientific_timeline.jsonl").open("w")
    ev = (dir_path / "scientific_events.jsonl").open("w")
    locos = ["MOVE:E", "MOVE:W", "MOVE:N", "MOVE:S", "WAIT"]
    for t in range(1, n_ticks + 1):
        for i in range(N_AGENTS):
            aid, bid = f"agent_{i}", f"body-{i}"
            oid, did, mid, cid = f"o{t}-{i}", f"d{t}-{i}", f"m{t}-{i}", f"c{t}-{i}"
            loco = locos[(t + i) % 5]
            spine.write(json.dumps({
                "tick": t, "cognitive_agent_id": aid, "physical_body_id": bid,
                "observation_id": oid, "decision_id": did, "motor_id": mid, "consequence_id": cid,
            }) + "\n")
            obs.write(json.dumps({
                "tick": t, "cognitive_agent_id": aid, "physical_body_id": bid,
                "observation_id": oid, "provenance": "AGENT_ACCESSIBLE",
                "accessible": {
                    "local.FIELD_A": 0.2 if t % 7 == 0 else 0.0,
                    "exo_0": 0.4 if t % 11 == 0 else 0.0,
                    "body.T": 0.5,
                },
            }) + "\n")
            dec.write(json.dumps({
                "tick": t, "cognitive_agent_id": aid, "physical_body_id": bid,
                "observation_id": oid, "decision_id": did, "motor_id": mid,
                "selection_path": "COMPOSITE_FACTORIZED",
                "selection_source": "COMPOSITE_FACTORIZED",
                "selected_action_legacy": loco,
                "candidate_count": 2,
            }) + "\n")
            mot.write(json.dumps({
                "tick": t, "cognitive_agent_id": aid, "physical_body_id": bid,
                "decision_id": did, "motor_id": mid, "motor_schema": "COMPOSITE_MOTOR_V1",
                "components": {"locomotion": loco, "neck": "NECK_HOLD", "oscillator": {}, "push": False},
            }) + "\n")
            cons.write(json.dumps({
                "physical_body_id": bid, "tick_from": t, "tick_to": t + 1,
                "motor_id": mid, "consequence_id": cid,
                "pose_delta": {"dx": 0.1 if loco != "WAIT" else 0.0, "dy": 0.0},
                "orientation_delta": {"dtheta": 0.0}, "resource_delta": {}, "attribution": "MOTOR",
            }) + "\n")
            tl.write(json.dumps({
                "tick": t, "agent_id": aid, "body_id": bid,
                "x": (t * 0.1 + i) % 32, "y": 8.0 + i, "vx": 0.1, "vy": 0.0,
                "theta": 0.0, "head_world_heading": 0.1, "contact": False,
                "resource_A": 1.0, "resource_B": 1.0, "work": 0.0, "action": loco,
                "vision_optical": {
                    "body_exposure": (t % 11 == 0),
                    "foreign_body_total": 0.3 if t % 11 == 0 else 0.0,
                },
            }) + "\n")
        if t % 9 == 0:
            ev.write(json.dumps({
                "tick": t, "type": "PHYSICAL_SIGNAL_EMITTED",
                "evidence": {"emitter_agent_id": "agent_0", "channel": "A", "emission_id": f"e{t}"},
            }) + "\n")
            ev.write(json.dumps({
                "tick": t, "type": "PHYSICAL_SIGNAL_RECEIVED",
                "evidence": {"receiver_agent_id": "agent_1", "local.FIELD_A": 0.2},
            }) + "\n")
    for fh in (spine, obs, dec, mot, cons, tl, ev):
        fh.close()


def test_metadata_package_is_not_full_without_consumption(tmp_path):
    run = tmp_path / "paused"
    write_paused_two_agent_v3(run)
    pkg = load_evidence_package(
        evidence_dir=run,
        cutoff_tick=N_TICKS,
        runtime_status="PAUSED",
        identity={"agent_count": 2},
        include_bulk_rows=False,
        include_behavioral=False,
        include_v3_core=False,
    )
    assert pkg["evidence_counts"]["scientific_rows"] == N_STORIES
    assert pkg["scientific_tick_range"][0] == 1
    assert pkg["scientific_tick_range"][1] == N_TICKS
    assert pkg["coverage"] != "FULL"
    assert pkg["complete_tick_level_reanalysis"] is False
    assert pkg.get("behavioral_reconstruction") is None
    assert not pkg.get("timeline")
    assert pkg.get("scientific_v3_core") is None


def test_analyze_current_job_consumes_2034_ticks(tmp_path):
    run = tmp_path / "paused"
    out = tmp_path / "job"
    write_paused_two_agent_v3(run)
    st = run_job(run_dir=run, out_dir=out, max_tick=N_TICKS)
    assert st["status"] == "COMPLETE"
    compact = json.loads((out / "analysis_http_summary.json").read_text())
    assert compact["tick_stories_count"] == N_STORIES
    assert compact["complete_odmc_count"] == N_STORIES
    assert compact["unique_simulation_ticks"] == N_TICKS
    assert compact["scientific_tick_range"] == [1, N_TICKS]
    hist = compact["canonical_history"]
    assert hist["unique_simulation_ticks"] == N_TICKS
    assert hist["agents"]["agent_0"]["move_count"] > 0
    assert hist["agents"]["agent_0"]["pose_ticks"] == N_TICKS
    assert hist["agents"]["agent_0"]["path_available"] is True
    assert float(hist["agents"]["agent_0"]["distance_manhattan_wrap"]) > 0
    assert float(hist["agents"]["agent_0"]["path_length_euclidean"]) > 0
    assert int(hist["agents"]["agent_0"]["unique_cells"]) > 0
    assert hist["agents"]["agent_1"]["visual_exposure_ticks"] > 0
    assert compact["join_summary"]["signal_joins"] > 0
    assert compact["join_summary"]["vision_joins"] > 0
    assert compact["coverage"] == "FULL"
    assert compact["complete_tick_level_reanalysis"] is True
    assert compact["scientific_rows"] == []
    assert compact["scientific_v3_core"]["evidence_version"] == "SCIENTIFIC_V3"
    assert compact["behavioral_reconstruction"]["status"] == "AVAILABLE"
    assert compact["behavioral_reconstruction"]["tick_stories_count"] == N_STORIES
    assert not (run / "analyzer_next").exists()
    assert (out / "analysis_derived_trajectory.jsonl").is_file()
    n_traj = sum(1 for _ in (out / "analysis_derived_trajectory.jsonl").open())
    assert n_traj == N_STORIES
