#!/usr/bin/env python3
"""Experience-gated cognitive depth experiments (Update 2).

A: EXPERIENCE_GATED vs ADULT_FROM_TICK_0
B: mature agent encounters novelty (memory preserved)
C: architecture hooks for amnesia control (prepared, optional short smoke)
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "worlds"))

from mechanistic_mind.agent import Agent
from mechanistic_mind.core import Engine
from mechanistic_mind.mechanisms import MechanismRegistry
from mechanistic_mind.psyche import DevelopmentalConfig, SingleOrganismPsycheV05
from contextual_object_ecology_v034 import (
    ContextualObjectEcologyWorld,
    default_contextual_object_config,
)


def _load(path: Path | None) -> dict[str, Any]:
    default = ROOT / "configs" / "experience_gated_depth_v02.json"
    return json.loads((path or default).read_text(encoding="utf-8"))


def _gate_from_engine(engine: Engine) -> dict[str, Any]:
    psyche = engine.state.agents["A001"].mechanism_states.get("PSYCHE-SENSORIMOTOR-V05", {}).get("psyche", {})
    memory = psyche.get("memory", {}) if isinstance(psyche, dict) else {}
    gate = memory.get("developmental")
    return gate if isinstance(gate, dict) else {}


def _summarize(actions: list[str], gates: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(actions)
    total = max(1, len(actions))
    depths = [float(g.get("cognitive_depth", 0.0)) for g in gates if g]
    locals_ = [float(g.get("local_experience_maturity", 0.0)) for g in gates if g]
    globals_ = [float(g.get("developmental_maturity", 0.0)) for g in gates if g]
    reasons = Counter(str(g.get("depth_limitation_reason")) for g in gates if g)
    return {
        "action_diversity": len(counts),
        "repeated_action_concentration": round((counts.most_common(1)[0][1] / total) if counts else 0.0, 6),
        "interaction_fraction": round(
            sum(1 for a in actions if a.startswith(("USE:", "TAKE:", "PUSH:", "RELEASE:"))) / total, 6
        ),
        "mean_cognitive_depth": round(sum(depths) / max(1, len(depths)), 6),
        "final_cognitive_depth": depths[-1] if depths else None,
        "mean_local_maturity": round(sum(locals_) / max(1, len(locals_)), 6),
        "final_local_maturity": locals_[-1] if locals_ else None,
        "mean_global_maturity": round(sum(globals_) / max(1, len(globals_)), 6),
        "final_global_maturity": globals_[-1] if globals_ else None,
        "depth_reason_counts": dict(reasons),
        "action_counts": dict(counts),
    }


def _run_ticks(engine: Engine, ticks: int) -> tuple[list[str], list[dict[str, Any]]]:
    actions: list[str] = []
    gates: list[dict[str, Any]] = []
    for _ in range(ticks):
        result = engine.step()
        actions.append(result.actions["A001"].kind)
        gates.append(_gate_from_engine(engine))
    return actions, gates


def experiment_a(payload: dict[str, Any], seed: int, ticks: int) -> dict[str, Any]:
    results = {}
    for name, cfg in payload["conditions"].items():
        world = ContextualObjectEcologyWorld(world_config=default_contextual_object_config(seed))
        registry = MechanismRegistry()
        registry.register(SingleOrganismPsycheV05(developmental=DevelopmentalConfig.from_dict(cfg)))
        engine = Engine(
            world=world,
            agents={"A001": Agent(agent_id="A001")},
            seed=seed,
            mechanisms=registry,
            run_config={"experiment": "experience_gated_depth_v02_A", "condition": name},
        )
        actions, gates = _run_ticks(engine, ticks)
        engine.close()
        results[name] = {
            "summary": _summarize(actions, gates),
            "final": gates[-1] if gates else {},
        }
    return results


def experiment_b(payload: dict[str, Any], seed: int, phase_a: int, phase_b: int) -> dict[str, Any]:
    cfg = DevelopmentalConfig.from_dict(payload["conditions"]["EXPERIENCE_GATED"])
    world_a = ContextualObjectEcologyWorld(world_config=default_contextual_object_config(seed))
    registry = MechanismRegistry()
    registry.register(SingleOrganismPsycheV05(developmental=cfg))
    engine = Engine(
        world=world_a,
        agents={"A001": Agent(agent_id="A001")},
        seed=seed,
        mechanisms=registry,
        run_config={"experiment": "experience_gated_depth_v02_B", "phase": "A"},
    )
    actions_a, gates_a = _run_ticks(engine, phase_a)
    psyche_after_a = deepcopy(engine.state.agents["A001"].mechanism_states["PSYCHE-SENSORIMOTOR-V05"]["psyche"])
    familiar_gate = gates_a[-1] if gates_a else {}

    # Swap to novel ecology without clearing agent mechanism state.
    novel_seed = seed + int(payload.get("novelty", {}).get("novel_world_seed_offset", 1000))
    world_b = ContextualObjectEcologyWorld(world_config=default_contextual_object_config(novel_seed))
    engine.world = world_b
    engine.state.world = deepcopy(world_b.state)
    # Preserve psyche memory inside mechanism state (already on agent).
    actions_b, gates_b = _run_ticks(engine, phase_b)
    novel_early = gates_b[: min(5, len(gates_b))]
    novel_late = gates_b[-min(5, len(gates_b)) :] if gates_b else []
    psyche_after_b = engine.state.agents["A001"].mechanism_states["PSYCHE-SENSORIMOTOR-V05"]["psyche"]
    # Continuity: contingencies from A still present.
    store_a = (psyche_after_a.get("memory") or {}).get("sensorimotor") or {}
    store_b = (psyche_after_b.get("memory") or {}).get("sensorimotor") or {}
    keys_a = set((store_a.get("contingencies") or {}).keys())
    keys_b = set((store_b.get("contingencies") or {}).keys())
    engine.close()
    return {
        "phase_a": _summarize(actions_a, gates_a),
        "familiar_final": familiar_gate,
        "phase_b": _summarize(actions_b, gates_b),
        "novel_early_mean_depth": round(
            sum(float(g.get("cognitive_depth", 0)) for g in novel_early) / max(1, len(novel_early)), 6
        ),
        "novel_late_mean_depth": round(
            sum(float(g.get("cognitive_depth", 0)) for g in novel_late) / max(1, len(novel_late)), 6
        ),
        "memory_keys_preserved": len(keys_a & keys_b),
        "memory_keys_phase_a": len(keys_a),
        "memory_keys_phase_b": len(keys_b),
        "novel_world_seed": novel_seed,
    }


def experiment_c_prepare(payload: dict[str, Any], seed: int, ticks: int = 20) -> dict[str, Any]:
    """Smoke the three architectural arms without claiming results."""
    cfg = DevelopmentalConfig.from_dict(payload["conditions"]["EXPERIENCE_GATED"])
    # MATURE_WITH_HISTORY
    world = ContextualObjectEcologyWorld(world_config=default_contextual_object_config(seed))
    registry = MechanismRegistry()
    registry.register(SingleOrganismPsycheV05(developmental=cfg))
    engine = Engine(world=world, agents={"A001": Agent(agent_id="A001")}, seed=seed, mechanisms=registry)
    _run_ticks(engine, ticks)
    hist = deepcopy(engine.state.agents["A001"].mechanism_states["PSYCHE-SENSORIMOTOR-V05"]["psyche"])
    # MATURE_MEMORY_CLEARED
    cleared = deepcopy(hist)
    memory = cleared.setdefault("memory", {})
    memory["sensorimotor"] = {"contingencies": {}, "index": {}, "last_cue": None, "last_observation": None, "last_action": None}
    memory["episodes"] = []
    memory.pop("developmental", None)
    engine.state.agents["A001"].mechanism_states["PSYCHE-SENSORIMOTOR-V05"]["psyche"] = cleared
    _run_ticks(engine, 5)
    cleared_gate = _gate_from_engine(engine)
    engine.close()
    # NEW_EXPERIENCE_GATED
    world2 = ContextualObjectEcologyWorld(world_config=default_contextual_object_config(seed))
    registry2 = MechanismRegistry()
    registry2.register(SingleOrganismPsycheV05(developmental=cfg))
    engine2 = Engine(world=world2, agents={"A001": Agent(agent_id="A001")}, seed=seed, mechanisms=registry2)
    _run_ticks(engine2, 5)
    new_gate = _gate_from_engine(engine2)
    engine2.close()
    return {
        "prepared": True,
        "arms": payload.get("amnesia_control_prepared", {}),
        "smoke": {
            "MATURE_WITH_HISTORY_keys": len(((hist.get("memory") or {}).get("sensorimotor") or {}).get("contingencies") or {}),
            "MATURE_MEMORY_CLEARED_depth": cleared_gate.get("cognitive_depth"),
            "NEW_EXPERIENCE_GATED_depth": new_gate.get("cognitive_depth"),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--phase-a", type=int, default=None)
    parser.add_argument("--phase-b", type=int, default=None)
    parser.add_argument("--skip-c", action="store_true")
    args = parser.parse_args()
    payload = _load(args.config)
    seed = int(args.seed if args.seed is not None else payload["seed"])
    phase_a = int(args.phase_a if args.phase_a is not None else payload["phase_a_ticks"])
    phase_b = int(args.phase_b if args.phase_b is not None else payload["phase_b_ticks"])
    out = {
        "experiment": "experience_gated_depth_v02",
        "seed": seed,
        "claim_boundary": (
            "Compares experience-gated cognitive depth vs adult-from-tick-0 and "
            "probes novelty-local depth. No superiority or psychological claims."
        ),
        "A_emergence": experiment_a(payload, seed, phase_a),
        "B_novelty": experiment_b(payload, seed, phase_a, phase_b),
    }
    if not args.skip_c:
        out["C_amnesia_prepared"] = experiment_c_prepare(payload, seed, ticks=max(10, phase_a // 3))
    path = ROOT / "experiments" / "experience_gated_depth_v02_result.json"
    path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"wrote": str(path), "keys": list(out)}, indent=2))


if __name__ == "__main__":
    main()
