#!/usr/bin/env python3
"""Update 4 diagnostics: perception density, passive WAIT, EMIT, recovery."""
from __future__ import annotations

import json
import sys
from collections import Counter
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "worlds"))

from contextual_object_ecology_v034 import (  # noqa: E402
    ContextualObjectEcologyWorld,
    contact_only_contextual_object_config,
    multi_channel_contextual_object_config,
    todo4_calibrated_body_config,
)
from mechanistic_mind.agent import Action, Agent
from mechanistic_mind.body import BodyConfig
from mechanistic_mind.core import Engine
from mechanistic_mind.mechanisms import MechanismRegistry
from mechanistic_mind.observer import InMemorySink, PsychologyObserver
from mechanistic_mind.psyche import (
    DevelopmentalCondition,
    DevelopmentalConfig,
    SingleOrganismPsycheV05,
)


def _body(recovery: bool) -> BodyConfig:
    base = todo4_calibrated_body_config()
    return BodyConfig(
        **{
            **{f.name: getattr(base, f.name) for f in base.__dataclass_fields__.values()},
            "recovery_dynamics_enabled": recovery,
        }
    )


def _world(mode: str, dynamic: bool, recovery: bool) -> ContextualObjectEcologyWorld:
    if mode == "MULTI_CHANNEL":
        cfg = multi_channel_contextual_object_config(17)
        if not dynamic:
            cfg = cfg.__class__(
                **{
                    **{f.name: getattr(cfg, f.name) for f in cfg.__dataclass_fields__.values()},
                    "autonomous_dynamics_enabled": False,
                }
            )
    else:
        cfg = contact_only_contextual_object_config(17)
        if dynamic:
            cfg = cfg.__class__(
                **{
                    **{f.name: getattr(cfg, f.name) for f in cfg.__dataclass_fields__.values()},
                    "autonomous_dynamics_enabled": True,
                }
            )
    world = ContextualObjectEcologyWorld(world_config=cfg, body_config=_body(recovery))
    return world


def _run(*, mode: str, dynamic: bool, recovery: bool, ticks: int, force_wait: bool = False, force_emit_every: int | None = None):
    world = _world(mode, dynamic, recovery)
    psyche = SingleOrganismPsycheV05(
        developmental=DevelopmentalConfig(
            condition=DevelopmentalCondition.EXPERIENCE_GATED
        )
    )
    registry = MechanismRegistry()
    registry.register(psyche)
    sink = InMemorySink()
    engine = Engine(
        world=world,
        agents={"A001": Agent(agent_id="A001")},
        seed=17,
        mechanisms=registry,
        observer=PsychologyObserver(sink),
        run_config={
            "perception_mode": mode,
            "autonomous_dynamics_enabled": dynamic,
            "recovery_dynamics_enabled": recovery,
        },
    )
    actions = []
    observations = []
    depths = []
    for tick in range(ticks):
        if force_wait:
            forced = {"A001": Action("WAIT")}
        elif force_emit_every and tick % force_emit_every == 0:
            forced = {"A001": Action("EMIT")}
        else:
            forced = None
        result = engine.step(actions=forced)
        obs = result.observations["A001"].data
        observations.append(obs)
        actions.append(result.actions["A001"].kind)
        # depth from mechanism signals/memory if present
        depth = None
        outs = result.mechanism_outputs.get("A001", {})
        for out in outs.values() if isinstance(outs, dict) else ():
            if not isinstance(out, dict):
                continue
            sig = out.get("signals") or {}
            if isinstance(sig, dict) and isinstance(sig.get("developmental"), dict):
                depth = sig["developmental"].get("cognitive_depth")
        depths.append(depth)
    engine.close()

    def perception_signature(obs):
        pp = obs.get("physical_perception") or {}
        summary = pp.get("summary") or {}
        return tuple(
            (
                name,
                int((summary.get(name) or {}).get("active_count", 0)),
                round(float((summary.get(name) or {}).get("strength_sum", 0.0)), 4),
                int((summary.get(name) or {}).get("feature_diversity", 0)),
            )
            for name in (
                "DISTANT_STRUCTURAL",
                "PASSIVE_WAVE",
                "ACTIVE_RETURN",
                "NEAR_CONTACT",
            )
        )

    signatures = [perception_signature(obs) for obs in observations]
    unique_perception = len(set(signatures))
    action_counts = Counter(actions)
    return {
        "mode": mode,
        "dynamic": dynamic,
        "recovery": recovery,
        "ticks": ticks,
        "unique_perception_signatures": unique_perception,
        "action_counts": dict(action_counts),
        "action_diversity": len(action_counts),
        "wait_fraction": action_counts.get("WAIT", 0) / max(1, ticks),
        "emit_count": action_counts.get("EMIT", 0),
        "mean_depth": (
            sum(d for d in depths if d is not None)
            / max(1, sum(1 for d in depths if d is not None))
            if any(d is not None for d in depths)
            else None
        ),
        "final_perception_summary": (observations[-1].get("physical_perception") or {}).get(
            "summary"
        ),
    }


def main() -> None:
    out_dir = ROOT / "results" / "update4_multi_channel_v04"
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "experiment_A_perception_density": {
            "CONTACT_ONLY": _run(
                mode="CONTACT_ONLY", dynamic=True, recovery=False, ticks=40
            ),
            "MULTI_CHANNEL": _run(
                mode="MULTI_CHANNEL", dynamic=True, recovery=False, ticks=40
            ),
        },
        "experiment_B_passive_wait": {
            "static": _run(
                mode="MULTI_CHANNEL",
                dynamic=False,
                recovery=False,
                ticks=60,
                force_wait=True,
            ),
            "dynamic": _run(
                mode="MULTI_CHANNEL",
                dynamic=True,
                recovery=False,
                ticks=60,
                force_wait=True,
            ),
        },
        "experiment_C_emit_physics": _run(
            mode="MULTI_CHANNEL",
            dynamic=False,
            recovery=False,
            ticks=20,
            force_emit_every=4,
        ),
        "experiment_D_recovery": {
            "off": _run(
                mode="MULTI_CHANNEL", dynamic=True, recovery=False, ticks=60
            ),
            "on": _run(
                mode="MULTI_CHANNEL", dynamic=True, recovery=True, ticks=60
            ),
        },
        "experiment_E_prep": {
            "status": "runnable",
            "suggested_command": (
                "python3 experiments/run_multi_channel_perception_v04.py --long 10000"
            ),
            "note": "Not executed in this smoke; preserve raw outputs when run.",
        },
    }
    path = out_dir / "summary.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True)[:4000])
    print("wrote", path)


if __name__ == "__main__":
    main()
