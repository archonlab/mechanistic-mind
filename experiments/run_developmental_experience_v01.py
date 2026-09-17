#!/usr/bin/env python3
"""DEVELOPMENTAL vs ADULT_FROM_TICK_0 comparison.

Compares cognitive accessibility regimes with identical world/seed/duration.
Does not claim superiority of either condition.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "worlds"))

from mechanistic_mind.agent import Agent
from mechanistic_mind.core import Engine
from mechanistic_mind.mechanisms import MechanismRegistry
from mechanistic_mind.psyche import (
    DevelopmentalCondition,
    DevelopmentalConfig,
    SingleOrganismPsycheV05,
)
from contextual_object_ecology_v034 import (
    ContextualObjectEcologyWorld,
    default_contextual_object_config,
)


def _load_config(path: Path | None) -> dict[str, Any]:
    default = ROOT / "configs" / "developmental_experience_v01.json"
    payload = json.loads((path or default).read_text(encoding="utf-8"))
    return payload


def _metrics(actions: list[str], gates: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(actions)
    total = max(1, len(actions))
    unique = len(counts)
    top = counts.most_common(1)[0][1] / total if counts else 0.0
    interaction = sum(
        1
        for action in actions
        if action.startswith(("USE:", "TAKE:", "PUSH:", "RELEASE:"))
    )
    gate_series = [float(row.get("gate_factor", 1.0)) for row in gates if row]
    maturity = [float(row.get("developmental_maturity", 0.0)) for row in gates if row]
    stages = Counter(str(row.get("developmental_stage")) for row in gates if row)
    return {
        "action_diversity": unique,
        "repeated_action_concentration": round(top, 6),
        "interaction_fraction": round(interaction / total, 6),
        "action_counts": dict(counts),
        "mean_gate_factor": round(sum(gate_series) / max(1, len(gate_series)), 6),
        "final_gate_factor": gate_series[-1] if gate_series else None,
        "mean_maturity": round(sum(maturity) / max(1, len(maturity)), 6),
        "final_maturity": maturity[-1] if maturity else None,
        "stage_counts": dict(stages),
    }


def run_condition(
    *,
    condition: str,
    seed: int,
    developmental_ticks: int,
    common_life_ticks: int,
    developmental_cfg: dict[str, Any],
) -> dict[str, Any]:
    world_config = default_contextual_object_config(seed)
    world = ContextualObjectEcologyWorld(world_config=world_config)
    cfg = DevelopmentalConfig.from_dict(developmental_cfg)
    registry = MechanismRegistry()
    registry.register(SingleOrganismPsycheV05(developmental=cfg))
    engine = Engine(
        world=world,
        agents={"A001": Agent(agent_id="A001")},
        seed=seed,
        mechanisms=registry,
        run_config={
            "experiment": "developmental_experience_v01",
            "condition": condition,
            "developmental": cfg.to_dict(),
            "world_seed": seed,
        },
    )
    total_ticks = developmental_ticks + common_life_ticks
    actions: list[str] = []
    gates: list[dict[str, Any]] = []
    matured_at = None
    for tick in range(1, total_ticks + 1):
        result = engine.step()
        actions.append(result.actions["A001"].kind)
        psyche = (
            result.state_after.agents["A001"]
            .mechanism_states.get("PSYCHE-SENSORIMOTOR-V05", {})
            .get("psyche", {})
        )
        memory = psyche.get("memory", {}) if isinstance(psyche, dict) else {}
        gate = memory.get("developmental") if isinstance(memory, dict) else None
        if isinstance(gate, dict):
            gates.append(gate)
            if matured_at is None and gate.get("matured"):
                matured_at = tick
        else:
            gates.append({})
    engine.close()
    early = actions[:developmental_ticks]
    late = actions[developmental_ticks:]
    return {
        "condition": condition,
        "seed": seed,
        "developmental_ticks": developmental_ticks,
        "common_life_ticks": common_life_ticks,
        "matured_at_tick": matured_at,
        "early": _metrics(early, gates[:developmental_ticks]),
        "late": _metrics(late, gates[developmental_ticks:]),
        "full": _metrics(actions, gates),
        "final_developmental": gates[-1] if gates else {},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--ticks-dev", type=int, default=None)
    parser.add_argument("--ticks-life", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()
    payload = _load_config(args.config)
    seed = int(args.seed if args.seed is not None else payload["seed"])
    dev_ticks = int(
        args.ticks_dev if args.ticks_dev is not None else payload["developmental_ticks"]
    )
    life_ticks = int(
        args.ticks_life if args.ticks_life is not None else payload["common_life_ticks"]
    )
    results = {}
    for name, cfg in payload["conditions"].items():
        results[name] = run_condition(
            condition=name,
            seed=seed,
            developmental_ticks=dev_ticks,
            common_life_ticks=life_ticks,
            developmental_cfg=cfg,
        )
    out = {
        "experiment": "developmental_experience_v01",
        "seed": seed,
        "developmental_ticks": dev_ticks,
        "common_life_ticks": life_ticks,
        "results": results,
        "claim_boundary": (
            "Compares developmental gating vs adult-from-tick-0. "
            "Does not claim superiority, consciousness, or infant psychology."
        ),
    }
    out_path = ROOT / "experiments" / "developmental_experience_v01_result.json"
    out_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"wrote": str(out_path), "conditions": list(results)}, indent=2))


if __name__ == "__main__":
    main()
