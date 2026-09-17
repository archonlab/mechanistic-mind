#!/usr/bin/env python3
"""Continuous Integrated Psyche v1 run (additional preset, not an experiment replacement)."""
from __future__ import annotations

import argparse
from dataclasses import fields, replace
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "worlds"))

from mechanistic_mind.agent import Agent
from mechanistic_mind.body import BodyConfig, BodyState
from mechanistic_mind.body.persistent_processes import default_process_config
from mechanistic_mind.core import Engine
from mechanistic_mind.integrated import IntegratedConfig, IntegratedPsycheV1, load_snapshot, save_snapshot
from mechanistic_mind.mechanisms import MechanismRegistry
from mechanistic_mind.observer import JSONLSink, PsychologyObserver
from mechanistic_mind.world_engine.background_fields import default_field_spec
from contextual_object_ecology_v034 import ContextualObjectEcologyWorld, dynamic_contextual_object_config, todo4_calibrated_body_config


def build_engine(*, seed: int, config: IntegratedConfig, jsonl: Path | None = None) -> Engine:
    wc = replace(dynamic_contextual_object_config(seed), perception_mode="MULTI_CHANNEL",
                 background_fields_spec=default_field_spec(), autonomous_dynamics_enabled=True)
    base = todo4_calibrated_body_config()
    body_values = {f.name: getattr(base, f.name) for f in fields(base)}
    body_values["persistent_process_config"] = default_process_config()
    body = BodyConfig(**body_values)
    world = ContextualObjectEcologyWorld(world_config=wc, body_config=body, initial_body=BodyState())
    registry = MechanismRegistry()
    registry.register(IntegratedPsycheV1(config))
    observer = PsychologyObserver(JSONLSink(jsonl), compact_ticks=True) if jsonl else None
    return Engine(world=world, agents={"A001": Agent(agent_id="A001")}, seed=seed,
                  mechanisms=registry, observer=observer,
                  run_config={"preset": "Integrated Psyche v1", "mechanisms": config.to_dict(),
                              "ground_truth_agent_visible": False, "continuous": True,
                              "bounded_telemetry": True})


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--ticks", type=int, default=1000)
    p.add_argument("--seed", type=int, default=17)
    p.add_argument("--jsonl", type=Path, default=Path("telemetry/integrated_psyche_v1.jsonl"))
    p.add_argument("--snapshot", type=Path)
    p.add_argument("--resume", type=Path)
    p.add_argument("--snapshot-every", type=int, default=0)
    p.add_argument("--ablate", action="append", choices=("predictive-compression", "multiscale-prediction",
                   "prospective-composition", "instrumental-observation", "bounded-memory", "retrieval"), default=[])
    a = p.parse_args()
    cuts = set(a.ablate)
    cfg = IntegratedConfig(predictive_compression="predictive-compression" not in cuts,
                           multiscale_prediction="multiscale-prediction" not in cuts,
                           prospective_composition="prospective-composition" not in cuts,
                           instrumental_observation="instrumental-observation" not in cuts,
                           bounded_memory="bounded-memory" not in cuts, retrieval="retrieval" not in cuts)
    engine = build_engine(seed=a.seed, config=cfg, jsonl=a.jsonl)
    if a.resume:
        load_snapshot(engine, a.resume)
    for _ in range(a.ticks):
        engine.step()
        if a.snapshot_every and engine.state.tick % a.snapshot_every == 0:
            save_snapshot(engine, a.snapshot or Path("snapshots/integrated_psyche_v1.json"))
    if a.snapshot:
        save_snapshot(engine, a.snapshot)
    engine.close()
    print(f"Integrated Psyche v1 tick={engine.state.tick} telemetry={a.jsonl}")


if __name__ == "__main__":
    main()
