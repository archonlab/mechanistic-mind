#!/usr/bin/env python3
"""STATIC_WORLD vs DYNAMIC_WORLD and passive WAIT diagnostics (Update 3).

Does not tune developmental gating. Does not claim DYNAMIC is superior.
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

from mechanistic_mind.agent import Action, Agent
from mechanistic_mind.core import Engine
from mechanistic_mind.mechanisms import MechanismRegistry
from mechanistic_mind.psyche import (
    DevelopmentalCondition,
    DevelopmentalConfig,
    SingleOrganismPsycheV05,
)
from mechanistic_mind.world_engine import measure_causal_experience
from contextual_object_ecology_v034 import (
    ContextualObjectEcologyWorld,
    dynamic_contextual_object_config,
    static_contextual_object_config,
)


def _visible_signature(observation) -> Any:
    data = observation.data if hasattr(observation, "data") else observation
    visible = data.get("visible_objects") or []
    return tuple(
        (
            str(item.get("id")),
            tuple(item.get("position") or ()),
            str(item.get("cue_signature")),
            str(item.get("interaction_state")),
            repr(item.get("observable_state") or {}),
        )
        for item in visible
        if isinstance(item, dict)
    )


def _body_signals(engine: Engine) -> dict[str, float]:
    bodies = engine.state.world.variables.get("bodies") or {}
    body = bodies.get("A001") or {}
    if hasattr(body, "to_dict"):
        body = body.to_dict()
    if not isinstance(body, dict):
        return {}
    out = {}
    for key, value in body.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            out[str(key)] = float(value)
    return out


def _gate(engine: Engine) -> dict[str, Any]:
    psyche = (
        engine.state.agents["A001"]
        .mechanism_states.get("PSYCHE-SENSORIMOTOR-V05", {})
        .get("psyche", {})
    )
    memory = psyche.get("memory", {}) if isinstance(psyche, dict) else {}
    gate = memory.get("developmental")
    return gate if isinstance(gate, dict) else {}


def _run(
    *,
    world_config,
    ticks: int,
    seed: int,
    force_wait: bool,
    developmental: DevelopmentalConfig,
    tag: str,
) -> dict[str, Any]:
    world = ContextualObjectEcologyWorld(world_config=world_config)
    registry = MechanismRegistry()
    registry.register(SingleOrganismPsycheV05(developmental=developmental))
    engine = Engine(
        world=world,
        agents={"A001": Agent(agent_id="A001")},
        seed=seed,
        mechanisms=registry,
        run_config={"experiment": "autonomous_world_dynamics_v03", "condition": tag},
    )
    actions: list[str] = []
    observations: list[Any] = []
    gates: list[dict[str, Any]] = []
    body_deltas: list[dict[str, float]] = []
    prev_body = _body_signals(engine)
    autonomous_events: list[dict[str, Any]] = []
    for _ in range(ticks):
        override = {"A001": Action.wait()} if force_wait else None
        # observe before step via engine internals after step we read state
        result = engine.step(override)
        action = result.actions["A001"].kind
        actions.append(action)
        observations.append(_visible_signature(result.observations["A001"]))
        gates.append(_gate(engine))
        body = _body_signals(engine)
        body_deltas.append(
            {key: body.get(key, 0.0) - prev_body.get(key, 0.0) for key in set(body) | set(prev_body)}
        )
        prev_body = body
        world_vars = engine.state.world.variables.get("world") or {}
        events = world_vars.get("autonomous_events")
        if isinstance(events, list):
            # keep only newly appended by tracking length — store full capped log at end
            autonomous_events = list(events)
    engine.close()
    causal = measure_causal_experience(
        observations=observations,
        actions=actions,
        autonomous_events=autonomous_events,
        body_deltas=body_deltas,
    )
    depths = [float(g.get("cognitive_depth", 0.0)) for g in gates if g]
    locals_ = [float(g.get("local_experience_maturity", 0.0)) for g in gates if g]
    counts = Counter(actions)
    return {
        "condition": tag,
        "force_wait": force_wait,
        "ticks": ticks,
        "causal_experience": causal,
        "action_counts": dict(counts),
        "repeated_action_concentration": (
            counts.most_common(1)[0][1] / max(1, len(actions)) if counts else 0.0
        ),
        "mean_cognitive_depth": round(sum(depths) / max(1, len(depths)), 6) if depths else None,
        "mean_local_maturity": round(sum(locals_) / max(1, len(locals_)), 6) if locals_ else None,
        "final_gate": gates[-1] if gates else {},
        "autonomous_events_logged": len(autonomous_events),
        "autonomous_event_kinds": dict(
            Counter(str(e.get("kind")) for e in autonomous_events if isinstance(e, dict))
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--ab-ticks", type=int, default=200)
    parser.add_argument("--passive-ticks", type=int, default=100)
    args = parser.parse_args()
    seed = args.seed
    # Keep experience-gated cognition identical across world conditions.
    developmental = DevelopmentalConfig(
        condition=DevelopmentalCondition.EXPERIENCE_GATED,
        min_ticks=50,
        target_ticks=100,
        max_ticks=200,
        target_fragments=40,
        target_transition_diversity=15,
        target_interaction_diversity=4,
        target_repeated_consequences=10,
        target_predictive_evidence=8,
    )
    static_cfg = static_contextual_object_config(seed)
    dynamic_cfg = dynamic_contextual_object_config(seed)
    out = {
        "experiment": "autonomous_world_dynamics_v03",
        "seed": seed,
        "claim_boundary": (
            "Separates (1) whether the experience stream changed from "
            "(2) whether agent behavior changed. No superiority claim."
        ),
        "A_static_vs_dynamic": {
            "STATIC_WORLD": _run(
                world_config=static_cfg,
                ticks=args.ab_ticks,
                seed=seed,
                force_wait=False,
                developmental=developmental,
                tag="STATIC_WORLD",
            ),
            "DYNAMIC_WORLD": _run(
                world_config=dynamic_cfg,
                ticks=args.ab_ticks,
                seed=seed,
                force_wait=False,
                developmental=developmental,
                tag="DYNAMIC_WORLD",
            ),
        },
        "B_passive_wait": {
            "STATIC_WORLD": _run(
                world_config=static_cfg,
                ticks=args.passive_ticks,
                seed=seed,
                force_wait=True,
                developmental=developmental,
                tag="PASSIVE_STATIC",
            ),
            "DYNAMIC_WORLD": _run(
                world_config=dynamic_cfg,
                ticks=args.passive_ticks,
                seed=seed,
                force_wait=True,
                developmental=developmental,
                tag="PASSIVE_DYNAMIC",
            ),
        },
        "C_action_vs_wait_prepared": {
            "note": (
                "Phase A=forced WAIT, Phase B=free policy; compare transition "
                "structure. Full long-horizon version left for later runs."
            ),
            "phase_a_wait": _run(
                world_config=dynamic_cfg,
                ticks=max(20, args.passive_ticks // 5),
                seed=seed,
                force_wait=True,
                developmental=developmental,
                tag="PHASE_A_WAIT",
            ),
            "phase_b_free": _run(
                world_config=dynamic_cfg,
                ticks=max(20, args.passive_ticks // 5),
                seed=seed,
                force_wait=False,
                developmental=developmental,
                tag="PHASE_B_FREE",
            ),
        },
        "observer_ui_integration": {
            "machine_readable": True,
            "fields": [
                "world.autonomous_events",
                "world.causal_provenance_tick",
                "action_receipt.autonomous_update_kinds",
                "action_receipt.causal_provenance_tick",
            ],
            "psychology_observer_ui": (
                "Not fully wired into Observer panels in this update; "
                "ground-truth fields are emitted on world state / receipts."
            ),
        },
    }
    path = ROOT / "experiments" / "autonomous_world_dynamics_v03_result.json"
    path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"wrote": str(path)}, indent=2))


if __name__ == "__main__":
    main()
