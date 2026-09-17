from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "worlds"))

from mechanistic_mind.agent import Agent
from mechanistic_mind.core import Engine
from mechanistic_mind.experiments import (
    CompactEvidenceObserver,
    CompressionConfig,
    ExperienceCompressionMechanism,
    MemoryMode,
    RetrievalMode,
    memory_metrics,
    structural_retrieval_probe,
)
from mechanistic_mind.mechanisms import MechanismRegistry
from contextual_object_ecology_v034 import (
    ContextualObjectEcologyWorld,
    default_contextual_object_config,
)
from reversal_yield import ReversalYieldWorld


SEED = 17


def execute(world: Any, config: CompressionConfig, ticks: int):
    mechanism = ExperienceCompressionMechanism(config)
    registry = MechanismRegistry()
    registry.register(mechanism)
    observer = CompactEvidenceObserver(
        checkpoint_interval=250,
        retain_runtime_timings=True,
    )
    engine = Engine(
        world=world,
        agents={"A001": Agent(agent_id="A001")},
        seed=SEED,
        mechanisms=registry,
        observer=observer,
        run_config={
            "experiment": "BOUNDED_COGNITION_TODO_01",
            "agent_seed": SEED,
            "memory": config.to_dict(),
        },
    )
    actions = []
    for _ in range(ticks):
        result = engine.step()
        actions.append(result.actions["A001"].kind)
    engine.close()
    memory = engine.state.agents["A001"].mechanism_states[
        mechanism.mechanism_id
    ]["memory"]
    return actions, observer, memory


def work_window(
    records: list[dict[str, Any]],
    runtime_timings: list[dict[str, int]],
) -> dict[str, float]:
    work = [
        row["agents"]["A001"].get("retrieval", {})
        for row in records
        if "A001" in row.get("agents", {})
    ]
    totals = [float(row.get("total_candidates_inspected", 0)) for row in work]
    ticks = {int(row["tick"]) for row in records}
    selected_timings = [
        row for row in runtime_timings if int(row["tick"]) in ticks
    ]
    result = {
        "mean_candidates": sum(totals) / max(1, len(totals)),
        "max_candidates": max(totals, default=0.0),
    }
    for name in (
        "pattern_lookup_time_ns",
        "exception_fallback_time_ns",
        "episode_fallback_time_ns",
        "retrieval_time_ns",
        "decision_time_ns",
    ):
        values = [float(row.get(name, 0)) for row in selected_timings]
        result[f"mean_{name}"] = sum(values) / max(1, len(values))
        result[f"max_{name}"] = max(values, default=0.0)
    return result


def experiment_a() -> dict[str, Any]:
    probes = {
        str(size): structural_retrieval_probe(size)
        for size in (100, 1000, 10000)
    }
    return {
        "name": "STRUCTURAL_SCALING",
        "probes": probes,
        "candidate_bound_constant": len(
            {
                row["retrieval"]["total_candidates_inspected"]
                for row in probes.values()
            }
        ) == 1,
        "full_store_iterations": sum(
            row["full_store_iterations"] for row in probes.values()
        ),
    }


def experiment_b(ticks: int = 1200) -> dict[str, Any]:
    results = {}
    comparison_episode_capacity = 256
    for retrieval_mode in (
        RetrievalMode.LEGACY_UNBOUNDED,
        RetrievalMode.HIERARCHICAL_BOUNDED,
    ):
        config = CompressionConfig(
            mode=MemoryMode.RAW,
            retrieval_mode=retrieval_mode,
            raw_episodic_capacity=comparison_episode_capacity,
        )
        actions, observer, memory = execute(
            ReversalYieldWorld(reversal_after=ticks // 2), config, ticks
        )
        width = min(100, ticks // 3)
        early = work_window(
            observer.continuous[:width], observer.runtime_retrieval_timings
        )
        middle_start = max(0, ticks // 2 - width // 2)
        middle = work_window(
            observer.continuous[middle_start:middle_start + width],
            observer.runtime_retrieval_timings,
        )
        late = work_window(
            observer.continuous[-width:], observer.runtime_retrieval_timings
        )
        results[retrieval_mode.value] = {
            "early": early,
            "middle": middle,
            "late": late,
            "late_early_candidate_ratio": late["mean_candidates"]
            / max(1e-9, early["mean_candidates"]),
            "action_counts": dict(sorted(Counter(actions).items())),
            "outcomes": {
                "cumulative": float(
                    observer.continuous[-1]["objective_world_scalars"].get(
                        "cumulative_outcome", 0.0
                    )
                ),
                "mean_per_tick": float(
                    observer.continuous[-1]["objective_world_scalars"].get(
                        "cumulative_outcome", 0.0
                    )
                ) / max(1, ticks),
            },
            "final_memory": memory_metrics(memory),
            "observer_retrieval_aggregates": observer.storage_metrics[
                "retrieval_metrics"
            ],
        }
    return {
        "name": "LEGACY_VS_BOUNDED",
        "ticks": ticks,
        "matched_episode_capacity": comparison_episode_capacity,
        "conditions": results,
    }


def experiment_c() -> dict[str, Any]:
    config = CompressionConfig(
        mode=MemoryMode.COMPRESSED,
        retrieval_mode=RetrievalMode.HIERARCHICAL_BOUNDED,
        high_error_threshold=0.2,
        invalidation_streak=2,
    )
    _actions, observer, memory = execute(
        ReversalYieldWorld(reversal_after=40), config, 100
    )
    reasons = Counter(
        str(row["agents"]["A001"].get("retention", {}).get("reason"))
        for row in observer.continuous
        if row["agents"]["A001"].get("retention")
    )
    patterns = list(memory["patterns"].values())
    return {
        "name": "NOVELTY_SENSITIVE_RETENTION",
        "retention_reasons": dict(sorted(reasons.items())),
        "episodes": len(memory["episodes"]),
        "patterns": len(patterns),
        "representatives": sum(len(row.get("representatives", [])) for row in patterns),
        "exceptions": sum(len(row.get("exceptions", [])) for row in patterns),
        "max_representatives_per_pattern": max((len(row.get("representatives", [])) for row in patterns), default=0),
        "max_exceptions_per_pattern": max((len(row.get("exceptions", [])) for row in patterns), default=0),
        "memory_event_counts": dict(sorted(Counter(str(row.get("type")) for row in observer.events).items())),
        "novelty_changes_action_value": False,
    }


def vision_measurement(records: list[dict[str, Any]], actions: list[str]) -> dict[str, Any]:
    precontact = []
    movement_directions = []
    for row, action in zip(records, actions):
        fragments = row["agents"]["A001"].get("visual_fragments", [])
        if any(float(fragment.get("distance", 0)) > 0 for fragment in fragments):
            precontact.append(row["tick"])
        if action.startswith("MOVE:"):
            movement_directions.append(action)
    return {
        "visible_precontact_ticks": len(precontact),
        "first_visible_precontact_tick": min(precontact, default=None),
        "action_changes": sum(a != b for a, b in zip(actions, actions[1:])),
        "movement_action_diversity": len(set(movement_directions)),
        "object_interactions": sum(action.startswith("USE:") for action in actions),
    }


def experiment_d(ticks: int = 160) -> dict[str, Any]:
    conditions = {}
    for horizon in (0, 2):
        world_config = replace(
            default_contextual_object_config(SEED),
            vision_radius=horizon,
        )
        actions, observer, _memory = execute(
            ContextualObjectEcologyWorld(world_config=world_config),
            CompressionConfig(
                mode=MemoryMode.COMPRESSED,
                retrieval_mode=RetrievalMode.HIERARCHICAL_BOUNDED,
            ),
            ticks,
        )
        conditions[str(horizon)] = vision_measurement(observer.continuous, actions)
    return {
        "name": "VISION_ABLATION",
        "ticks": ticks,
        "matched_seed": SEED,
        "conditions": conditions,
        "interpretation": "Behavioral differences or a null result are measurements, not a built-in vision policy.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="TODO 01 bounded-cognition experiments A-D")
    parser.add_argument("--legacy-ticks", type=int, default=1200)
    parser.add_argument("--vision-ticks", type=int, default=160)
    parser.add_argument("--output", type=Path, default=ROOT / "experiments" / "bounded_cognition_v01_result.json")
    args = parser.parse_args()
    result = {
        "program": "HIERARCHICAL_BOUNDED_RETRIEVAL_V01",
        "runtime_version": "0.3.7",
        "seed": SEED,
        "experiments": {
            "A": experiment_a(),
            "B": experiment_b(args.legacy_ticks),
            "C": experiment_c(),
            "D": experiment_d(args.vision_ticks),
        },
        "claim_boundary": "Bounded mechanistic retrieval; no claim of human cognition, understanding, curiosity, or optimality.",
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
