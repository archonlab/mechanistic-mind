#!/usr/bin/env python3
"""Update 4.7 experiment matrix: Shared Ecology × Independent Psyches."""

from __future__ import annotations

import json
import sys
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "worlds"))

from mechanistic_mind.agent import Action
from mechanistic_mind.core import Engine
from mechanistic_mind.multi_agent.v047 import (
    build_multi_agent_engine,
    derived_seed,
)
from mechanistic_mind.observer import CompositeSink, JSONLSink, PsychologyObserver

OUT = ROOT / "results" / "update47_multi_agent_v047"
OUT.mkdir(parents=True, exist_ok=True)

SEED = 17
AGENT_A = "A001"
AGENT_B = "B001"


def _action_counts(engine: Engine) -> dict[str, Counter]:
    history = engine.state.world.variables.get("developmental_history", [])
    counts: dict[str, Counter] = {}
    for row in history:
        if not isinstance(row, dict):
            continue
        aid = str(row.get("agent_id") or AGENT_A)
        kind = str(row.get("action") or "WAIT")
        bucket = kind.split(":", 1)[0]
        counts.setdefault(aid, Counter())[bucket] += 1
    return counts


def _psyche_memory(engine: Engine, agent_id: str) -> dict[str, Any]:
    agent_state = engine.state.agents.get(agent_id)
    if agent_state is None:
        return {}
    for mechanism_id, payload in agent_state.mechanism_states.items():
        if not isinstance(payload, dict):
            continue
        psyche = payload.get("psyche")
        if isinstance(psyche, dict):
            return deepcopy(psyche.get("memory") or {})
    return {}


def _episode_fingerprints(memory: dict[str, Any]) -> set[str]:
    episodes = memory.get("episodes") or []
    out: set[str] = set()
    for ep in episodes:
        if not isinstance(ep, dict):
            continue
        # Stable fingerprint without agent labels.
        key = json.dumps(
            {
                "action": ep.get("action"),
                "tick": ep.get("tick"),
                "effects": ep.get("experienced_effects") or ep.get("effects"),
                "position": ep.get("position"),
            },
            sort_keys=True,
            default=str,
        )
        out.add(key)
    return out


def _object_quantity(engine: Engine, object_id: str) -> float | None:
    world = engine.state.world.variables.get("world") or {}
    objects = world.get("objects") or {}
    record = objects.get(object_id)
    if not isinstance(record, dict):
        return None
    if "quantity" in record:
        return float(record["quantity"])
    return None


def run_condition(
    *,
    name: str,
    agent_ids: tuple[str, ...],
    start_positions: dict[str, tuple[int, int]],
    ticks: int,
    forced_actions: dict[str, list[str]] | None = None,
    compact: bool = True,
    world_kind: str = "contextual",
) -> dict[str, Any]:
    jsonl_path = OUT / f"{name.lower()}_telemetry.jsonl"
    if jsonl_path.exists():
        jsonl_path.unlink()
    observer = PsychologyObserver(
        CompositeSink((JSONLSink(jsonl_path),)),
        compact_ticks=True,
    )
    engine = build_multi_agent_engine(
        agent_ids=agent_ids,
        start_positions=start_positions,
        world_seed=SEED,
        world_kind=world_kind,
        compact=compact,
        observer=observer,
        run_config={"condition": name, "ticks": ticks},
    )

    forced = forced_actions or {}
    schedules = {
        aid: list(seq) for aid, seq in forced.items()
    }

    object_trace: list[dict[str, Any]] = []
    for tick in range(ticks):
        overrides: dict[str, Action] = {}
        for aid, seq in schedules.items():
            if tick < len(seq):
                overrides[aid] = Action(seq[tick])
        # Passive remaining agents endogenous via psyche.
        result = engine.step(overrides or None)
        if name == "SHARED_OBJECT_TRACE":
            object_trace.append(
                {
                    "tick": tick + 1,
                    "quantity_OBJ12": _object_quantity(engine, "OBJ-12"),
                    "actions": {
                        aid: result.actions[aid].kind
                        for aid in sorted(result.actions)
                    },
                    "positions": deepcopy(
                        engine.state.world.variables["world"]["agent_positions"]
                    ),
                }
            )

    engine.close()
    counts = {aid: dict(counter) for aid, counter in _action_counts(engine).items()}
    memories = {aid: _psyche_memory(engine, aid) for aid in agent_ids}
    episode_sets = {aid: _episode_fingerprints(mem) for aid, mem in memories.items()}

    metrics: dict[str, Any] = {
        "condition": name,
        "seed": SEED,
        "ticks": ticks,
        "agent_ids": list(agent_ids),
        "start_positions": {
            aid: list(pos) for aid, pos in start_positions.items()
        },
        "derived_seeds": {
            aid: derived_seed(SEED, aid) for aid in agent_ids
        },
        "action_counts": counts,
        "final_positions": deepcopy(
            engine.state.world.variables["world"]["agent_positions"]
        ),
        "final_bodies": {
            aid: deepcopy(engine.state.world.variables["bodies"].get(aid))
            for aid in agent_ids
        },
        "memory_episode_counts": {
            aid: len(mem.get("episodes") or [])
            for aid, mem in memories.items()
        },
        "telemetry_jsonl": str(jsonl_path.relative_to(ROOT)),
    }

    if len(agent_ids) >= 2:
        a, b = agent_ids[0], agent_ids[1]
        overlap = episode_sets[a] & episode_sets[b]
        metrics["memory_isolation"] = {
            "shared_episode_fingerprints": len(overlap),
            "pass": len(overlap) == 0,
            "episodes_A": len(episode_sets[a]),
            "episodes_B": len(episode_sets[b]),
        }

    if name == "SHARED_OBJECT_TRACE":
        qty_series = [
            row["quantity_OBJ12"]
            for row in object_trace
            if row["quantity_OBJ12"] is not None
        ]
        metrics["shared_object_trace"] = {
            "object_id": "OBJ-12",
            "quantity_series_head": qty_series[:12],
            "quantity_series_tail": qty_series[-12:],
            "depleted": (
                qty_series[-1] < qty_series[0] if len(qty_series) >= 2 else False
            ),
            "trace_rows": object_trace[:40],
        }

    # Occupancy: other agent blocked cells
    if len(agent_ids) >= 2:
        world = engine.state.world.variables["world"]
        positions = world["agent_positions"]
        metrics["occupancy"] = {
            aid: list(positions[aid]) for aid in agent_ids
        }
        metrics["distinct_positions"] = (
            len({tuple(positions[aid]) for aid in agent_ids}) == len(agent_ids)
        )

    out_json = OUT / f"{name.lower()}_metrics.json"
    out_json.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n")
    metrics["metrics_path"] = str(out_json.relative_to(ROOT))
    return metrics


def main() -> None:
    results: dict[str, Any] = {}

    # Compact protocol geometry: start (2,3), OBJ-12 at (2,3).
    results["SINGLE"] = run_condition(
        name="SINGLE",
        agent_ids=(AGENT_A,),
        start_positions={AGENT_A: (2, 3)},
        ticks=200,
        compact=True,
    )

    results["TWO_NEAR"] = run_condition(
        name="TWO_NEAR",
        agent_ids=(AGENT_A, AGENT_B),
        start_positions={AGENT_A: (2, 3), AGENT_B: (3, 3)},
        ticks=200,
        compact=True,
    )

    results["TWO_FAR"] = run_condition(
        name="TWO_FAR",
        agent_ids=(AGENT_A, AGENT_B),
        start_positions={AGENT_A: (1, 1), AGENT_B: (6, 5)},
        ticks=200,
        compact=True,
    )

    # A uses depleting object; B waits nearby and should see shared quantity drop.
    # OBJ-12 at (2,3) in physical_protocol_object_config.
    use_then_wait_a = ["USE:OBJ-12"] * 5 + ["WAIT"] * 15
    wait_b = ["WAIT"] * 20
    results["SHARED_OBJECT_TRACE"] = run_condition(
        name="SHARED_OBJECT_TRACE",
        agent_ids=(AGENT_A, AGENT_B),
        start_positions={AGENT_A: (2, 3), AGENT_B: (3, 3)},
        ticks=20,
        forced_actions={AGENT_A: use_then_wait_a, AGENT_B: wait_b},
        compact=True,
    )

    # Force divergent experiences then compare memories.
    results["MEMORY_ISOLATION"] = run_condition(
        name="MEMORY_ISOLATION",
        agent_ids=(AGENT_A, AGENT_B),
        start_positions={AGENT_A: (2, 3), AGENT_B: (5, 4)},
        ticks=40,
        forced_actions={
            AGENT_A: ["USE:OBJ-12"] * 8 + ["WAIT"] * 32,
            AGENT_B: ["WAIT"] * 40,
        },
        compact=True,
    )

    # Optional cheap controls
    results["PASSIVE_BODY"] = run_condition(
        name="PASSIVE_BODY",
        agent_ids=(AGENT_A, AGENT_B),
        start_positions={AGENT_A: (2, 3), AGENT_B: (4, 4)},
        ticks=30,
        forced_actions={
            AGENT_A: ["WAIT"] * 30,
            AGENT_B: ["WAIT"] * 30,
        },
        compact=True,
    )

    summary_path = OUT / "MATRIX_SUMMARY.json"
    summary_path.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: {
        "action_counts": v.get("action_counts"),
        "memory_isolation": v.get("memory_isolation"),
        "shared_object_trace": {
            "depleted": (v.get("shared_object_trace") or {}).get("depleted"),
            "head": (v.get("shared_object_trace") or {}).get("quantity_series_head"),
        } if "shared_object_trace" in v else None,
        "metrics_path": v.get("metrics_path"),
    } for k, v in results.items()}, indent=2))
    print(f"Wrote {summary_path}")


if __name__ == "__main__":
    main()
