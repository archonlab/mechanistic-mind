from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "worlds"))

from mechanistic_mind.adapters.archon import (
    ArchonAdapterSink,
    InMemoryArchonSink,
)
from mechanistic_mind.agent import Agent
from mechanistic_mind.core import Engine
from mechanistic_mind.mechanisms import MechanismRegistry
from mechanistic_mind.observer import (
    CompositeSink,
    InMemorySink,
    PsychologyObserver,
)
from mechanistic_mind.psyche import (
    PsycheState,
    SingleAgentPsycheV01,
    build_life_modules,
)
from environmental_perturbations import (
    EnvironmentalPerturbationPack,
    PerturbedSingleAgentLifeWorld,
    canonical_environmental_conditions,
)


TICKS = 160
SEED = 17
EFFECTIVE_TICK = 80
AGENT_ID = "A001"
MECHANISM_ID = "PSYCHE-SINGLE-AGENT-V01"


def _build_engine(
    pack: EnvironmentalPerturbationPack,
) -> Engine:
    registry = MechanismRegistry()
    registry.register(
        SingleAgentPsycheV01(
            modules=build_life_modules(),
            initial_state=PsycheState.initial_life_v01(),
        )
    )

    return Engine(
        world=PerturbedSingleAgentLifeWorld(
            perturbation_pack=pack
        ),
        agents={AGENT_ID: Agent(agent_id=AGENT_ID)},
        seed=SEED,
        mechanisms=registry,
        run_config={
            "experiment": "ENVIRONMENTAL_PERTURBATION_PACK_V022",
            "condition": pack.pack_id,
            "effective_tick": EFFECTIVE_TICK,
            "ticks": TICKS,
        },
    )


def _row(result) -> dict[str, Any]:
    world = result.state_after.world.variables
    psyche = result.state_after.agents[AGENT_ID].mechanism_states[
        MECHANISM_ID
    ]["psyche"]
    whole = result.signals[AGENT_ID][MECHANISM_ID]["whole_psyche"]
    selection = whole.get("selection", {})
    action = result.actions[AGENT_ID].kind
    return {
        "tick": int(result.state_before.tick),
        "action": str(action),
        "position": tuple(world["agent_position"]),
        "consequence": deepcopy(world.get("last_consequence") or {}),
        "environment_effects": deepcopy(
            world.get("last_environment_effects") or {}
        ),
        "total_progress": float(world.get("total_progress", 0.0)),
        "internal": deepcopy(psyche["internal"]),
        "prediction_error": float(
            psyche["prediction_errors"].get("magnitude", 0.0)
        ),
        "tension": float(
            psyche["global_state"].get("tension", 0.0)
        ),
        "selection_reason": str(selection.get("reason") or ""),
    }


def _category(action: str) -> str:
    if action.startswith("MOVE:"):
        return "MOVE"
    if action.startswith("USE:"):
        return "USE"
    return action


def _mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def _first_tick(
    rows: list[dict[str, Any]],
    predicate,
    *,
    start_tick: int,
) -> int | None:
    for row in rows:
        if row["tick"] >= start_tick and predicate(row):
            return int(row["tick"])
    return None


def _count_after(
    rows: list[dict[str, Any]],
    predicate,
    *,
    start_tick: int,
) -> int:
    return sum(
        1
        for row in rows
        if row["tick"] >= start_tick and predicate(row)
    )


def _condition_metrics(
    rows: list[dict[str, Any]],
    final_world: dict[str, Any],
    final_psyche: dict[str, Any],
) -> dict[str, Any]:
    pre = [row for row in rows if row["tick"] < EFFECTIVE_TICK]
    post = [row for row in rows if row["tick"] >= EFFECTIVE_TICK]

    pre_actions = [row["action"] for row in pre]
    post_actions = [row["action"] for row in post]
    pre_categories = Counter(_category(action) for action in pre_actions)
    post_categories = Counter(_category(action) for action in post_actions)

    pre_progress = (
        pre[-1]["total_progress"] if pre else 0.0
    )
    post_progress = float(final_world.get("total_progress", 0.0)) - pre_progress

    post_prediction_errors = [
        float(row["prediction_error"]) for row in post
    ]
    post_tension = [float(row["tension"]) for row in post]
    post_hydration = [
        float(row["internal"].get("hydration", 0.0))
        for row in post
    ]
    post_energy = [
        float(row["internal"].get("energy", 0.0))
        for row in post
    ]
    post_fatigue = [
        float(row["internal"].get("fatigue", 0.0))
        for row in post
    ]

    use_counts_pre = Counter(
        action.split(":", 1)[1]
        for action in pre_actions
        if action.startswith("USE:")
    )
    use_counts_post = Counter(
        action.split(":", 1)[1]
        for action in post_actions
        if action.startswith("USE:")
    )

    return {
        "pre": {
            "action_categories": dict(pre_categories),
            "object_use_counts": dict(use_counts_pre),
            "progress": pre_progress,
        },
        "post": {
            "action_categories": dict(post_categories),
            "object_use_counts": dict(use_counts_post),
            "progress": post_progress,
            "mean_prediction_error": _mean(post_prediction_errors),
            "max_prediction_error": max(post_prediction_errors, default=None),
            "mean_tension": _mean(post_tension),
            "min_hydration": min(post_hydration, default=None),
            "min_energy": min(post_energy, default=None),
            "max_fatigue": max(post_fatigue, default=None),
        },
        "final": {
            "position": deepcopy(final_world.get("agent_position")),
            "total_progress": float(final_world.get("total_progress", 0.0)),
            "unique_positions": len(final_world.get("visited_positions", [])),
            "object_use_counts": deepcopy(
                final_world.get("object_use_counts", {})
            ),
            "internal": deepcopy(final_psyche.get("internal", {})),
            "known_objects": deepcopy(
                final_psyche.get("memory", {})
                .get("spatial", {})
                .get("objects", {})
            ),
        },
    }


def _condition_specific(
    name: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    if name == "RELOCATION":
        old_position = (7, 5)
        new_position = (1, 5)
        first_new_visit = _first_tick(
            rows,
            lambda row: row["position"] == new_position,
            start_tick=EFFECTIVE_TICK,
        )
        first_use = _first_tick(
            rows,
            lambda row: row["action"] == "USE:OBJ-23",
            start_tick=EFFECTIVE_TICK,
        )
        return {
            "old_position_visits_after": _count_after(
                rows,
                lambda row: row["position"] == old_position,
                start_tick=EFFECTIVE_TICK,
            ),
            "first_new_position_visit_tick": first_new_visit,
            "first_relocated_object_use_tick": first_use,
            "reacquisition_latency": (
                first_use - EFFECTIVE_TICK
                if first_use is not None
                else None
            ),
        }

    if name == "DEPLETION":
        old_position = (4, 3)
        return {
            "depleted_site_visits_after": _count_after(
                rows,
                lambda row: row["position"] == old_position,
                start_tick=EFFECTIVE_TICK,
            ),
            "depleted_object_uses_after": _count_after(
                rows,
                lambda row: row["action"] == "USE:OBJ-04",
                start_tick=EFFECTIVE_TICK,
            ),
            "first_alternative_object_use_tick": _first_tick(
                rows,
                lambda row: row["action"].startswith("USE:")
                and row["action"] != "USE:OBJ-04",
                start_tick=EFFECTIVE_TICK,
            ),
        }

    if name == "OUTCOME_NOISE":
        noisy_rows = [
            row
            for row in rows
            if row["tick"] >= EFFECTIVE_TICK
            and row["action"] == "USE:OBJ-31"
        ]
        return {
            "noisy_object_uses_after": len(noisy_rows),
            "noise_effect_observations": sum(
                1
                for row in noisy_rows
                if row["environment_effects"].get("outcome_noise")
            ),
            "mean_error_on_noisy_use": _mean(
                [row["prediction_error"] for row in noisy_rows]
            ),
        }

    if name == "AMBIENT_PRESSURE":
        post = [row for row in rows if row["tick"] >= EFFECTIVE_TICK]
        hydration_uses = sum(
            row["action"] == "USE:OBJ-23" for row in post
        )
        return {
            "hydration_resource_uses_after": hydration_uses,
            "ambient_effect_observations": sum(
                1
                for row in post
                if row["environment_effects"].get("ambient_load")
            ),
        }

    if name == "UTILITY_CONFLICT":
        post = [row for row in rows if row["tick"] >= EFFECTIVE_TICK]
        progress_uses = sum(
            row["action"] == "USE:OBJ-31" for row in post
        )
        return {
            "progress_site_uses_after": progress_uses,
            "first_progress_site_use_after": _first_tick(
                rows,
                lambda row: row["action"] == "USE:OBJ-31",
                start_tick=EFFECTIVE_TICK,
            ),
        }

    return {}


def run_condition(
    name: str,
    pack: EnvironmentalPerturbationPack,
) -> dict[str, Any]:
    engine = _build_engine(pack)
    rows = []
    for _ in range(TICKS):
        rows.append(_row(engine.step()))

    final_world = engine.state.world.variables
    final_psyche = engine.state.agents[AGENT_ID].mechanism_states[
        MECHANISM_ID
    ]["psyche"]

    return {
        "condition": name,
        "pack": pack.manifest(),
        "rows": rows,
        "actions": [row["action"] for row in rows],
        "perturbation_log": deepcopy(
            final_world.get("perturbation_log", [])
        ),
        "metrics": _condition_metrics(
            rows,
            final_world,
            final_psyche,
        ),
        "specific_metrics": _condition_specific(name, rows),
    }


def observer_contract_smoke() -> dict[str, Any]:
    canonical = InMemorySink()
    archon = InMemoryArchonSink()
    observer = PsychologyObserver(
        CompositeSink((canonical, ArchonAdapterSink(archon)))
    )
    registry = MechanismRegistry()
    registry.register(
        SingleAgentPsycheV01(
            modules=build_life_modules(),
            initial_state=PsycheState.initial_life_v01(),
        )
    )
    engine = Engine(
        world=PerturbedSingleAgentLifeWorld(
            perturbation_pack=canonical_environmental_conditions(
                effective_tick=4
            )["RELOCATION"]
        ),
        agents={AGENT_ID: Agent(agent_id=AGENT_ID)},
        seed=SEED,
        mechanisms=registry,
        observer=observer,
    )
    engine.run(6)
    engine.close()
    return {
        "ticks": len(canonical.records),
        "archon_observations": len(archon.observations),
        "archon_events": len(archon.events),
        "perturbation_receipts": len(
            engine.state.world.variables.get("perturbation_log", [])
        ),
    }


def _delta(a: Any, b: Any) -> float | None:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return float(a) - float(b)
    return None


def main() -> None:
    conditions = canonical_environmental_conditions(
        effective_tick=EFFECTIVE_TICK
    )
    results: dict[str, dict[str, Any]] = {}
    for name, pack in conditions.items():
        print(f"[EPP] running {name}...", file=sys.stderr, flush=True)
        results[name] = run_condition(name, pack)
        print(f"[EPP] completed {name}", file=sys.stderr, flush=True)
    control = results["CONTROL"]

    comparisons: dict[str, Any] = {}
    control_prefix = control["actions"][:EFFECTIVE_TICK]
    for name, result in results.items():
        if name == "CONTROL":
            continue
        comparisons[name] = {
            "matched_pre_intervention_actions": (
                result["actions"][:EFFECTIVE_TICK]
                == control_prefix
            ),
            "delta_final_progress": _delta(
                result["metrics"]["final"]["total_progress"],
                control["metrics"]["final"]["total_progress"],
            ),
            "delta_post_mean_prediction_error": _delta(
                result["metrics"]["post"]["mean_prediction_error"],
                control["metrics"]["post"]["mean_prediction_error"],
            ),
            "delta_post_mean_tension": _delta(
                result["metrics"]["post"]["mean_tension"],
                control["metrics"]["post"]["mean_tension"],
            ),
            "delta_post_min_hydration": _delta(
                result["metrics"]["post"]["min_hydration"],
                control["metrics"]["post"]["min_hydration"],
            ),
        }

    compact_conditions = {}
    for name, result in results.items():
        compact_conditions[name] = {
            key: value
            for key, value in result.items()
            if key not in {"rows", "actions"}
        }

    report = {
        "schema_version": (
            "mechanistic-mind.environmental-perturbation-pack/0.2.2"
        ),
        "experiment": "ENVIRONMENTAL_PERTURBATION_PACK_V022",
        "design": {
            "agent_count": 1,
            "seed": SEED,
            "ticks": TICKS,
            "effective_tick": EFFECTIVE_TICK,
            "control": "CONTROL",
            "matching": "same_initial_state_same_seed_same_psyche",
            "intervention_visibility": (
                "observer-only; agent receives only changed observations "
                "and experienced consequences"
            ),
        },
        "independent_variable": "environmental perturbation condition",
        "dependent_variables": [
            "behavioral action trajectory",
            "resource/object use",
            "spatial reacquisition latency",
            "prediction error",
            "homeostatic tension",
            "internal resource minima",
            "progress",
        ],
        "conditions": compact_conditions,
        "matched_control_comparisons": comparisons,
        "observer_contract_smoke": observer_contract_smoke(),
        "interpretation_policy": (
            "These runs establish intervention mechanics and observed effects. "
            "They do not by themselves identify a unique psychological mechanism."
        ),
    }

    output = ROOT / "experiments/environmental_perturbation_pack_v022_result.json"
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
