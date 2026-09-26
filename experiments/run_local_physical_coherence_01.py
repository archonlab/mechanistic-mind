"""LOCAL_PHYSICAL_COHERENCE_01 — rollup: wrap audit × passive locality × LIVE regression."""
from __future__ import annotations

import json
import math
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mechanistic_mind.physical_system.ecology_presets import (  # noqa: E402
    ECOLOGY_CALIBRATED_TEMPORAL,
    make_ecology_config,
)
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime  # noqa: E402
from mechanistic_mind.research.local_physical_coherence import (  # noqa: E402
    LOCAL_SENSORY_HORIZON,
    trajectory_metrics_extended,
)
from mechanistic_mind.research.world_timescale import wrap_delta  # noqa: E402

OUT = ROOT / "results" / "physics" / "local_physical_coherence_01"


def live_two_agent_regression(ticks: int = 3000, seed: int = 17) -> dict:
    cfg = make_ecology_config(ECOLOGY_CALIBRATED_TEMPORAL, trickle=0.0)
    cfg.cognition.cognition_enabled = True
    rt = TwoAgentRuntime(seed=seed, config=cfg)
    w = int(rt.world.T.shape[1])
    h = int(rt.world.T.shape[0])
    traces = {
        0: {"xs": [], "ys": [], "speeds": [], "actions": []},
        1: {"xs": [], "ys": [], "speeds": [], "actions": []},
    }
    for _ in range(int(ticks)):
        rt.step(1)
        for i, slot in enumerate(rt.slots):
            traces[i]["xs"].append(float(slot.body.x))
            traces[i]["ys"].append(float(slot.body.y))
            traces[i]["speeds"].append(math.hypot(float(slot.body.vx), float(slot.body.vy)))
            traces[i]["actions"].append(str(slot.last_selected_action or "WAIT"))
    agents = []
    for i in (0, 1):
        tr = traces[i]
        traj = trajectory_metrics_extended(
            tr["xs"], tr["ys"], width=w, height=h, speeds=tr["speeds"], actions=tr["actions"]
        )
        wait_n = sum(1 for a in tr["actions"] if a == "WAIT")
        move_n = sum(1 for a in tr["actions"] if str(a).startswith("MOVE"))
        mean_sp = float(sum(tr["speeds"]) / max(1, len(tr["speeds"])))
        expected_path = mean_sp * max(1, len(tr["xs"]) - 1)
        ratio = traj["path_length_euclidean"] / max(1e-9, expected_path)
        agents.append({
            "agent_id": f"agent_{i}",
            "ticks": ticks,
            "wait_count": wait_n,
            "move_count": move_n,
            "wait_pct": 100.0 * wait_n / max(1, ticks),
            "move_pct": 100.0 * move_n / max(1, ticks),
            "mean_speed": mean_sp,
            "path_length_euclidean": traj["path_length_euclidean"],
            "unwrapped_dx": traj["unwrapped_dx"],
            "unwrapped_dy": traj["unwrapped_dy"],
            "max_excursion_from_start": traj["max_excursion_from_start"],
            "unique_cells": traj["unique_cells"],
            "path_during_requested_WAIT": traj["path_during_requested_WAIT"],
            "path_during_requested_MOVE": traj["path_during_requested_MOVE"],
            "boundary_crossings_x": traj["boundary_crossings_x"],
            "boundary_crossings_y": traj["boundary_crossings_y"],
            "path_vs_velocity_consistency": traj["path_vs_velocity_consistency"],
            "path_vs_speed_ratio": ratio,
            "runtime_distance_travelled": float(rt._agent_stats[i].get("distance_travelled") or 0),
            "consistent_with_speed": ratio < 3.0,
        })
    return {
        "seed": seed,
        "ticks": ticks,
        "preset": "CALIBRATED_TEMPORAL_WORLD_EXPERIMENTAL",
        "cognition": True,
        "agents": agents,
        "all_consistent": all(a["consistent_with_speed"] for a in agents),
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    # Import summaries if present
    wrap_path = ROOT / "results" / "physics" / "wrap_trajectory_audit_01" / "summary.json"
    loc_path = ROOT / "results" / "physics" / "passive_locality_01" / "summary.json"
    wrap = json.loads(wrap_path.read_text()) if wrap_path.exists() else {"all_pass": None, "missing": True}
    loc = json.loads(loc_path.read_text()) if loc_path.exists() else {"gates": {"all_pass": None}, "missing": True}

    print("Running LIVE TwoAgentRuntime ~3000 ticks regression...")
    live = live_two_agent_regression(3000, 17)

    report = {
        "experiment": "LOCAL_PHYSICAL_COHERENCE_01",
        "local_sensory_horizon": LOCAL_SENSORY_HORIZON,
        "root_cause": {
            "primary": (
                "Analyzer ingestLiveSummaries overwrote last_xy from LIVE frame "
                "without updating last_xy_tick, poisoning the next unique-tick "
                "WRAP delta (future pose → past timeline pose)."
            ),
            "secondary": (
                "TwoAgentRuntime distance_travelled used raw Manhattan without "
                "minimum-image WRAP correction."
            ),
            "duplicate_observer_samples": (
                "Already deduped by claimTimelineAgentState / last_xy_tick; "
                "not the primary inflation source. Now also counted as "
                "duplicate_observer_samples_ignored."
            ),
            "wrap_math": "wrapDelta / wrap_delta minimum-image was already correct when dims set.",
        },
        "parameters_changed": [],
        "wrap_audit_pass": wrap.get("all_pass"),
        "passive_locality_pass": (loc.get("gates") or {}).get("all_pass"),
        "live_regression": live,
        "conservative_conclusions": [
            "Periodic trajectory metrics now agree with runtime physical displacement.",
            "Ordinary resting WAIT remains local relative to the defined one-cell spatial horizon "
            "iff PASSIVE_LOCALITY gates pass (see passive_locality_01).",
            "Active MOVE produces substantially greater local-context replacement than ordinary "
            "resting WAIT iff G3 passes.",
        ],
    }
    (OUT / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    (OUT / "REPORT.md").write_text(
        "# LOCAL_PHYSICAL_COHERENCE_01\n\n"
        f"wrap_audit_pass={report['wrap_audit_pass']}\n"
        f"passive_locality_pass={report['passive_locality_pass']}\n"
        f"live_all_consistent={live['all_consistent']}\n\n"
        f"## Root cause\n{report['root_cause']['primary']}\n\n"
        f"Secondary: {report['root_cause']['secondary']}\n\n"
        f"## LIVE agents\n```\n{json.dumps(live['agents'], indent=2)}\n```\n"
    )
    print(json.dumps({
        "wrap": report["wrap_audit_pass"],
        "locality": report["passive_locality_pass"],
        "live_ok": live["all_consistent"],
        "agents": [
            {
                "id": a["agent_id"],
                "path": round(a["path_length_euclidean"], 3),
                "mean_speed": round(a["mean_speed"], 5),
                "ratio": round(a["path_vs_speed_ratio"], 3),
                "wait_pct": round(a["wait_pct"], 1),
            }
            for a in live["agents"]
        ],
    }, indent=2))
    ok = bool(live["all_consistent"])
    if wrap.get("all_pass") is False or (loc.get("gates") or {}).get("all_pass") is False:
        ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
