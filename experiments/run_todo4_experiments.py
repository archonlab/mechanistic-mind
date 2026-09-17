"""Deterministic TODO #4 calibration and A/B/C evidence runner."""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "worlds")]

from mechanistic_mind.agent import Action, Agent
from mechanistic_mind.core import Engine
from mechanistic_mind.experiments import CompactEvidenceObserver, CompressionConfig, ExperienceCompressionMechanism, MemoryMode
from mechanistic_mind.mechanisms import MechanismRegistry
from contextual_object_ecology_v034 import ContextualObjectEcologyWorld, default_contextual_object_config


def physiology_horizon(world: ContextualObjectEcologyWorld, policy: str, seed: int, limit: int = 2000) -> dict:
    engine = Engine(world=world, agents={"A001": Agent("A001")}, seed=seed)
    thresholds = {"energy_low": None, "hydration_low": None, "fatigue_high": None, "severe": None}
    actions = Counter()
    for tick in range(1, limit + 1):
        observation = world.observe(engine.state.world, "A001").data
        available = sorted(observation["available_actions"])
        moves = [item for item in available if item.startswith("MOVE:")]
        interactions = [item for item in available if item.startswith(("USE:", "PUSH:", "TAKE:"))]
        action = "WAIT"
        if policy == "move" and moves:
            action = moves[(tick + seed) % len(moves)]
        elif policy == "interaction" and interactions:
            action = interactions[0]
        elif policy == "interaction" and moves:
            action = moves[(tick + seed) % len(moves)]
        engine.step({"A001": Action(action)}); actions[action.split(":", 1)[0]] += 1
        body = engine.state.world.variables["bodies"]["A001"]
        if body["energy_reserve"] <= 1/3 and thresholds["energy_low"] is None: thresholds["energy_low"] = tick
        if body["hydration"] <= 1/3 and thresholds["hydration_low"] is None: thresholds["hydration_low"] = tick
        if body["fatigue"] >= 2/3 and thresholds["fatigue_high"] is None: thresholds["fatigue_high"] = tick
        if min(body["energy_reserve"], body["hydration"]) <= 0.05 or body["fatigue"] >= 0.95:
            thresholds["severe"] = tick; break
    return {"threshold_ticks": thresholds, "ticks_run": tick, "actions": dict(actions), "final_body": body}


def matrix_arm(name: str, seed: int, ticks: int) -> dict:
    old_physiology = name == "A_CURRENT_BASELINE"
    dynamics = name == "C_TODO4"
    world = (ContextualObjectEcologyWorld.legacy_physiology if old_physiology else ContextualObjectEcologyWorld)(world_config=default_contextual_object_config(seed))
    config = CompressionConfig(mode=MemoryMode.COMPRESSED, exploration_gain=0.0 if dynamics else 2.0, perceptual_dynamics_enabled=dynamics, cue_schema_version="bounded-multimodal-cue-v2" if dynamics else "bounded-retrieval-cue-v1")
    mechanism = ExperienceCompressionMechanism(config); registry = MechanismRegistry(); registry.register(mechanism)
    observer = CompactEvidenceObserver(checkpoint_interval=250, retain_records=True)
    engine = Engine(world=world, agents={"A001": Agent("A001")}, seed=seed, mechanisms=registry, observer=observer, run_config={"todo4_arm": name, "memory_parameters": config.to_dict()})
    engine.run(ticks); engine.close()
    rows = [row["agents"]["A001"] for row in observer.continuous]
    actions = Counter(row["action"].split(":", 1)[0] for row in rows)
    memory = engine.state.agents["A001"].mechanism_states[mechanism.mechanism_id]["memory"]
    dynamics_rows = [row.get("memory", {}).get("perceptual_dynamics", {}) for row in rows]
    known = [row for row in dynamics_rows if row.get("mismatch") is not None]
    return {
        "seed": seed, "ticks": ticks, "action_counts": dict(actions),
        "wait_fraction": actions["WAIT"] / max(1, ticks), "move_fraction": actions["MOVE"] / max(1, ticks),
        "interaction_fraction": 1-(actions["WAIT"]+actions["MOVE"])/max(1,ticks),
        "unique_positions": len({tuple(row["position"]) for row in rows}),
        "objects_encountered": len({item for row in rows for item in row["perceived_ids"]}),
        "episodes": len(memory["episodes"]), "patterns": len(memory["patterns"]),
        "unknown_fraction": 1-len(known)/max(1,ticks),
        "mean_mismatch": sum(float(row["mismatch"]) for row in known)/max(1,len(known)),
        "mean_activation": sum(float(row.get("perceptual_activation",0)) for row in dynamics_rows)/max(1,len(dynamics_rows)),
        "max_inspected": max((row.get("retrieval",{}).get("total_candidates_inspected",0) for row in rows), default=0),
        "telemetry": observer.storage_metrics,
        "final_body": engine.state.world.variables["bodies"]["A001"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--ticks", type=int, default=500); parser.add_argument("--output", type=Path, default=ROOT/"experiments"/"todo4_result.json"); args = parser.parse_args()
    seeds = (17, 23, 41)
    result = {
        "schema": "mechanistic-mind/todo4-experiment-v1", "seeds": list(seeds),
        "physiology": {str(seed): {"legacy_wait": physiology_horizon(ContextualObjectEcologyWorld.legacy_physiology(world_config=default_contextual_object_config(seed)), "wait", seed), "calibrated_wait_resource_free": physiology_horizon(ContextualObjectEcologyWorld(world_config=default_contextual_object_config(seed)), "wait", seed), "calibrated_locomotion": physiology_horizon(ContextualObjectEcologyWorld(world_config=default_contextual_object_config(seed)), "move", seed)} for seed in seeds},
        "matrix": {arm: [matrix_arm(arm, seed, args.ticks) for seed in seeds] for arm in ("A_CURRENT_BASELINE", "B_PHYSIOLOGY_ONLY", "C_TODO4")},
        "boundaries": {"temporal_credit_assignment": False, "novelty_reward_in_todo4": False, "forced_exploration": False}
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__": main()
