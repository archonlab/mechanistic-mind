from __future__ import annotations

import argparse
from copy import deepcopy
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
    behavioral_metrics,
    memory_metrics,
)
from mechanistic_mind.mechanisms import MechanismRegistry
from mechanistic_mind.observer import canonical_json
from reversal_yield import ReversalYieldWorld


SEED = 17
LEARNING_TICKS = 150
RUN_TICKS = 360
CHECKPOINT_INTERVAL = 250


def _digest(value: Any) -> str:
    from hashlib import sha256
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def run_condition(
    mode: MemoryMode,
    *,
    ticks: int = RUN_TICKS,
    learning_ticks: int = LEARNING_TICKS,
    evidence_path: Path | None = None,
    measure_legacy_full: bool = False,
) -> dict[str, Any]:
    config = CompressionConfig(mode=mode)
    mechanism = ExperienceCompressionMechanism(config)
    registry = MechanismRegistry()
    registry.register(mechanism)
    observer = CompactEvidenceObserver(
        checkpoint_interval=CHECKPOINT_INTERVAL,
        jsonl_path=evidence_path,
        retain_records=True,
        measure_legacy_full=measure_legacy_full,
    )
    world = ReversalYieldWorld(reversal_after=learning_ticks)
    engine = Engine(
        world=world,
        agents={"A001": Agent(agent_id="A001")},
        seed=SEED,
        mechanisms=registry,
        observer=observer,
        run_config={
            "experiment": "EXPERIENCE_COMPRESSION_V01",
            "world_seed": SEED,
            "agent_seed": SEED,
            "memory_mode": mode.value,
            "memory_parameters": config.to_dict(),
            "checkpoint_interval": CHECKPOINT_INTERVAL,
            "perturbation": {
                "kind": "UNANNOUNCED_CONTINGENCY_REVERSAL",
                "effective_after_tick": learning_ticks,
            },
            "runtime_version": "0.3.7",
        },
    )
    initial_world_digest = _digest(engine.state.world)
    initial_agent_digest = _digest(engine.state.agents["A001"])
    actions: list[str] = []
    outcomes: list[float] = []
    for _ in range(ticks):
        result = engine.step()
        actions.append(result.actions["A001"].kind)
        outcomes.append(float(result.state_after.world.variables["last_outcome"]))
    engine.close()

    memory = engine.state.agents["A001"].mechanism_states[
        mechanism.mechanism_id
    ]["memory"]
    pre_actions = actions[:learning_ticks]
    post_actions = actions[learning_ticks:]
    old_action = (
        max(set(pre_actions), key=lambda action: (pre_actions.count(action), action))
        if pre_actions
        else None
    )
    post_yields = {
        "CHOOSE_A": world.state.variables["post_yield_A"],
        "CHOOSE_B": world.state.variables["post_yield_B"],
    }
    new_optimal = max(post_yields, key=post_yields.get)
    adaptation_latency = None
    window = 12
    for index in range(max(0, len(post_actions) - window + 1)):
        if post_actions[index:index + window].count(new_optimal) / window >= 0.75:
            adaptation_latency = index
            break
    memory_event_counts: dict[str, int] = {}
    for event in observer.events:
        event_type = str(event.get("type"))
        memory_event_counts[event_type] = memory_event_counts.get(event_type, 0) + 1

    return {
        "mode": mode.value,
        "provenance": {
            "run_id": observer.run_id,
            "world_seed": SEED,
            "agent_seed": SEED,
            "initial_world_digest": initial_world_digest,
            "initial_agent_digest": initial_agent_digest,
            "memory_parameters": config.to_dict(),
            "checkpoint_interval": CHECKPOINT_INTERVAL,
            "perturbation_tick": learning_ticks,
            "runtime_version": "0.3.7",
        },
        "behavior": {
            **behavioral_metrics(observer.continuous),
            "pre_action_entropy": behavioral_metrics(observer.continuous[:learning_ticks])["action_entropy"],
            "post_action_entropy": behavioral_metrics(observer.continuous[learning_ticks:])["action_entropy"],
            "old_behavior_persistence_first_24": post_actions[:24].count(old_action) / max(1, len(post_actions[:24])),
            "adaptation_latency_ticks": adaptation_latency,
            "new_optimal_action": new_optimal,
            "mean_outcome_pre": sum(outcomes[:learning_ticks]) / max(1, len(outcomes[:learning_ticks])),
            "mean_outcome_post": sum(outcomes[learning_ticks:]) / max(1, len(outcomes[learning_ticks:])),
        },
        "memory": memory_metrics(memory),
        "memory_event_counts": dict(sorted(memory_event_counts.items())),
        "observer_storage": observer.storage_metrics,
    }


def benchmark(ticks: int = 5000) -> dict[str, Any]:
    result = run_condition(
        MemoryMode.COMPRESSED,
        ticks=ticks,
        learning_ticks=ticks // 2,
        measure_legacy_full=True,
    )
    storage = result["observer_storage"]
    return {
        "ticks": ticks,
        "compact_bytes": storage["observer_history_bytes"],
        "legacy_full_bytes": storage["legacy_full_history_bytes"],
        "reduction_ratio": storage["reduction_ratio"],
        "bytes_per_tick": storage["bytes_per_tick"],
        "checkpoint_storage_bytes": storage["checkpoint_storage_bytes"],
        "ram_peak_bytes": storage["ram_peak_bytes"],
        "agent_memory_bytes": result["memory"]["agent_memory_bytes"],
        "provenance_retained": all(
            result["provenance"].get(key) is not None
            for key in (
                "run_id",
                "world_seed",
                "agent_seed",
                "memory_parameters",
                "checkpoint_interval",
                "perturbation_tick",
                "runtime_version",
            )
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Matched experience compression experiment")
    parser.add_argument(
        "--benchmark-ticks",
        type=int,
        nargs="+",
        default=(1000, 5000),
        help="One or more scaling points; 10000/50000 may be added for manual runs.",
    )
    parser.add_argument("--output", type=Path, default=ROOT / "experiments" / "experience_compression_v01_result.json")
    parser.add_argument("--evidence-dir", type=Path)
    args = parser.parse_args()
    conditions = {}
    for mode in MemoryMode:
        evidence_path = (
            args.evidence_dir / f"{mode.value.lower()}.jsonl"
            if args.evidence_dir is not None
            else None
        )
        conditions[mode.value] = run_condition(mode, evidence_path=evidence_path)
    world_digests = {row["provenance"]["initial_world_digest"] for row in conditions.values()}
    agent_digests = {row["provenance"]["initial_agent_digest"] for row in conditions.values()}
    result = {
        "experiment": "EXPERIENCE_COMPRESSION_V01",
        "scientific_question": "Under what mechanisms of experience compression do stable but adaptive behavioral structures emerge?",
        "matched_initial_conditions": len(world_digests) == 1 and len(agent_digests) == 1,
        "conditions": conditions,
        "storage_benchmarks": {
            str(ticks): benchmark(ticks)
            for ticks in args.benchmark_ticks
        },
        "claim_boundary": "Mechanistic finite-memory experiment; no claim of modeling human memory or psychological traits.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
