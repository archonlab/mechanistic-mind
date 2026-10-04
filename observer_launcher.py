#!/usr/bin/env python3
"""Standalone Mechanistic Mind Psychology Observer launcher."""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "worlds"))

from mechanistic_mind.adapters.archon import ArchonAdapterSink, JSONLArchonSink
from mechanistic_mind.agent import Agent
from mechanistic_mind.body import BodyConfig, BodyState
from mechanistic_mind.core import Engine
from mechanistic_mind.experiments import (
    CompressionConfig,
    ExperienceCompressionMechanism,
    MemoryMode,
)
from mechanistic_mind.mechanisms import MechanismRegistry
from mechanistic_mind.observer import (
    CompositeSink,
    ConsoleSink,
    JSONLSink,
    PsychologyObserver,
)
from mechanistic_mind.psyche import (
    SensorimotorConfig,
    DevelopmentalCondition,
    DevelopmentalConfig,
    PsycheState,
    SingleAgentPsycheV01,
    SingleOrganismPsycheV03,
    SingleOrganismPsycheV05,
    build_life_modules,
)
from mechanistic_mind.research.developmental_subsidy import (
    apply_subsidy_to_body_config,
    apply_subsidy_to_body_state,
    baseline_unsubsidized_spec,
    subsidy_from_tick_equivalent,
)
from mechanistic_mind.research.long_run_telemetry import LongRunResearchSink

from contextual_object_ecology_v034 import (
    ContextualObjectEcologyWorld,
    ObjectManipulationAcceptanceWorld,
    contact_only_contextual_object_config,
    default_contextual_object_config,
    dynamic_contextual_object_config,
    multi_channel_contextual_object_config,
    todo4_calibrated_body_config,
)
from environmental_perturbations import (
    PerturbedSingleAgentLifeWorld,
    canonical_environmental_conditions,
)
from obstacle_value_world_v032 import ObstacleValueWorld
from organism_world_v03 import OrganismWorld, default_organism_world_config
from persistent_targets_world_v033 import PersistentTargetsWorld
from mechanistic_mind.research.physical_object_demo import PhysicalObjectProtocol
from reversal_yield import ReversalYieldWorld
from two_choice_yield import TwoChoiceYieldWorld


def build_life_perturbation(*, condition: str, perturbation_tick: int):
    packs = canonical_environmental_conditions(effective_tick=perturbation_tick)
    if condition not in packs:
        raise KeyError(f"Unknown life condition: {condition!r}")
    return packs[condition]


MECHANISMS = {
    "psyche-v01": SingleAgentPsycheV01,
    "psyche-v03": SingleOrganismPsycheV03,
    "psyche-v05-experience-gated": SingleOrganismPsycheV05,
    "psyche-v05-adult": SingleOrganismPsycheV05,
    "psyche-v05-developmental": SingleOrganismPsycheV05,
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Standalone Mechanistic Mind Psychology Observer"
    )
    parser.add_argument(
        "--world",
        choices=(
            "stationary",
            "reversal",
            "life",
            "organism",
            "obstacle-value",
            "persistent-targets",
            "contextual-objects",
            "object-manipulation",
        ),
        default="organism",
    )
    parser.add_argument(
        "--mechanism",
        default="psyche-v03",
        help="Mechanism id / memory architecture",
    )
    parser.add_argument("--ticks", type=int, default=90)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument(
        "--jsonl",
        default="telemetry/psychology_observer.jsonl",
    )
    parser.add_argument(
        "--archon-jsonl",
        default="telemetry/archon_bridge.jsonl",
    )
    parser.add_argument(
        "--world-dynamics",
        choices=("static", "dynamic"),
        default="static",
        help="Autonomous world dynamics for contextual-objects",
    )
    parser.add_argument(
        "--perception-mode",
        choices=("contact-only", "multi-channel"),
        default="contact-only",
        help="Physical perception mode for contextual-objects",
    )
    parser.add_argument(
        "--recovery-dynamics",
        action="store_true",
        help="Enable activity-recovery body dynamics",
    )
    parser.add_argument(
        "--cue-mode",
        choices=("legacy", "perceptual"),
        default="legacy",
        help="Update 4.1 context_cue mode: legacy vs perceptual uptake",
    )
    parser.add_argument(
        "--developmental-subsidy-ticks",
        type=int,
        default=0,
        help="Update 4.2 MDS tick-equivalent initial physical reserve (0=baseline)",
    )
    parser.add_argument(
        "--long-run-telemetry",
        action="store_true",
        help="Update 4.2 LONG-RUN aggregated research telemetry",
    )
    parser.add_argument("--no-signals", action="store_true")
    parser.add_argument(
        "--tick-delay-ms",
        type=int,
        default=0,
        help="Optional display pacing; does not alter simulation state",
    )
    parser.add_argument("--resource-layout", default="distributed")
    parser.add_argument(
        "--random-event-rate",
        type=float,
        default=0.0,
        help="Per-tick exogenous random-event probability for --world organism",
    )
    parser.add_argument("--obstacle-condition", default="HAZARD")
    parser.add_argument("--persistent-condition", default="BROKEN")
    parser.add_argument("--life-condition", default="CONTROL")
    parser.add_argument("--perturbation-tick", type=int, default=30)
    parser.add_argument("--reversal-after", type=int, default=40)
    args = parser.parse_args()

    life_pack = None
    if args.world == "life":
        life_pack = build_life_perturbation(
            condition=args.life_condition,
            perturbation_tick=args.perturbation_tick,
        )
        world = PerturbedSingleAgentLifeWorld(perturbation_pack=life_pack)
    elif args.world == "contextual-objects":
        if args.mechanism not in {
            "psyche-v03",
            "bounded-compressed",
            "bounded-raw",
            "bounded-forgetful",
            "psyche-v05-experience-gated",
            "psyche-v05-adult",
            "psyche-v05-developmental",
        }:
            parser.error(
                "--world contextual-objects requires psyche-v03, psyche-v05, "
                "or a bounded memory mechanism"
            )
        perception = getattr(args, "perception_mode", "contact-only")
        dynamics = getattr(args, "world_dynamics", "static")
        if perception == "multi-channel":
            world_config = multi_channel_contextual_object_config(args.seed)
            if dynamics == "static":
                world_config = world_config.__class__(
                    **{
                        **{
                            f.name: getattr(world_config, f.name)
                            for f in world_config.__dataclass_fields__.values()
                        },
                        "autonomous_dynamics_enabled": False,
                    }
                )
        elif dynamics == "dynamic":
            world_config = dynamic_contextual_object_config(args.seed)
            world_config = world_config.__class__(
                **{
                    **{
                        f.name: getattr(world_config, f.name)
                        for f in world_config.__dataclass_fields__.values()
                    },
                    "perception_mode": "CONTACT_ONLY",
                }
            )
        else:
            world_config = contact_only_contextual_object_config(args.seed)
        recovery = bool(getattr(args, "recovery_dynamics", False))
        body_kwargs: dict = {}
        base = todo4_calibrated_body_config()
        body_cfg = BodyConfig(
            **{
                **{f.name: getattr(base, f.name) for f in base.__dataclass_fields__.values()},
                "recovery_dynamics_enabled": recovery,
            }
        )
        subsidy_ticks = int(getattr(args, "developmental_subsidy_ticks", 0) or 0)
        if subsidy_ticks > 0:
            subsidy = subsidy_from_tick_equivalent(subsidy_ticks)
        else:
            subsidy = baseline_unsubsidized_spec()
        body_kwargs["body_config"] = apply_subsidy_to_body_config(body_cfg, subsidy)
        body_kwargs["initial_body"] = apply_subsidy_to_body_state(BodyState(), subsidy)
        world = ContextualObjectEcologyWorld(
            world_config=world_config,
            **body_kwargs,
        )
    elif args.world == "object-manipulation":
        if args.mechanism != "physical-demo":
            parser.error(
                "--world object-manipulation requires --mechanism physical-demo"
            )
        world = ObjectManipulationAcceptanceWorld()
    elif args.world == "organism":
        if args.mechanism != "psyche-v03":
            parser.error("--world organism requires --mechanism psyche-v03")
        if args.life_condition != "CONTROL":
            parser.error(
                "--life-condition belongs to the legacy v0.2.2 life world"
            )
        if not (0.0 <= args.random_event_rate <= 1.0):
            parser.error("--random-event-rate must be in [0, 1]")
        world = OrganismWorld(
            world_config=default_organism_world_config(
                resource_layout=args.resource_layout,
                random_event_rate=args.random_event_rate,
            )
        )
    elif args.world == "obstacle-value":
        if args.mechanism != "psyche-v03":
            parser.error(
                "--world obstacle-value requires --mechanism psyche-v03"
            )
        world = ObstacleValueWorld(condition=args.obstacle_condition)
    elif args.world == "persistent-targets":
        if args.mechanism != "psyche-v03":
            parser.error(
                "--world persistent-targets requires --mechanism psyche-v03"
            )
        world = PersistentTargetsWorld(condition=args.persistent_condition)
    else:
        if args.mechanism in {"psyche-v01", "psyche-v03"}:
            parser.error(
                "whole-psyche mechanisms require their matching world"
            )
        if args.life_condition != "CONTROL":
            parser.error("--life-condition is valid only for --world life")
        world = (
            TwoChoiceYieldWorld()
            if args.world == "stationary"
            else ReversalYieldWorld(reversal_after=args.reversal_after)
        )

    if args.world == "life":
        mechanism = SingleAgentPsycheV01(
            modules=build_life_modules(),
            initial_state=PsycheState.initial_life_v01(),
        )
    elif args.world == "contextual-objects" and args.mechanism.startswith(
        "bounded-"
    ):
        memory_mode = {
            "bounded-compressed": MemoryMode.COMPRESSED,
            "bounded-raw": MemoryMode.RAW,
            "bounded-forgetful": MemoryMode.FORGETFUL,
        }[args.mechanism]
        mechanism = ExperienceCompressionMechanism(
            CompressionConfig(
                mode=memory_mode,
                exploration_gain=0.0,
                perceptual_dynamics_enabled=True,
                cue_schema_version="bounded-multimodal-cue-v2",
            )
        )
    elif args.mechanism.startswith("psyche-v05"):
        condition = {
            "psyche-v05-experience-gated": DevelopmentalCondition.EXPERIENCE_GATED,
            "psyche-v05-adult": DevelopmentalCondition.ADULT_FROM_TICK_0,
            "psyche-v05-developmental": DevelopmentalCondition.DEVELOPMENTAL,
        }[args.mechanism]
        cue_arg = getattr(args, "cue_mode", "legacy")
        cue_mode = {
            "legacy": "LEGACY_CUE_ONLY",
            "perceptual": "PERCEPTUAL_CUE_ENABLED",
            "LEGACY_CUE_ONLY": "LEGACY_CUE_ONLY",
            "PERCEPTUAL_CUE_ENABLED": "PERCEPTUAL_CUE_ENABLED",
        }.get(str(cue_arg), "LEGACY_CUE_ONLY")
        mechanism = SingleOrganismPsycheV05(
            sensorimotor_config=SensorimotorConfig(cue_mode=cue_mode),
            developmental=DevelopmentalConfig(condition=condition),
        )
    elif args.world in {
        "organism",
        "obstacle-value",
        "persistent-targets",
        "contextual-objects",
    }:
        mechanism = SingleOrganismPsycheV03()
    elif args.world == "object-manipulation":
        mechanism = PhysicalObjectProtocol()
    else:
        mechanism = MECHANISMS[args.mechanism]()

    registry = MechanismRegistry()
    registry.register(mechanism)

    psychology_jsonl = Path(args.jsonl)
    archon_jsonl = Path(args.archon_jsonl)
    for path in (psychology_jsonl, archon_jsonl):
        if path.exists():
            path.unlink()

    sinks = [
        ConsoleSink(show_signals=not args.no_signals),
        JSONLSink(psychology_jsonl),
        ArchonAdapterSink(JSONLArchonSink(archon_jsonl)),
    ]
    long_run_path = None
    if getattr(args, "long_run_telemetry", False):
        long_run_path = psychology_jsonl.with_name(
            psychology_jsonl.stem + "_longrun.jsonl"
        )
        if long_run_path.exists():
            long_run_path.unlink()
        sinks.append(LongRunResearchSink(long_run_path))

    observer = PsychologyObserver(
        CompositeSink(tuple(sinks)),
        compact_ticks=(
            args.world == "contextual-objects"
            and args.mechanism.startswith("bounded-")
        )
        or bool(getattr(args, "long_run_telemetry", False)),
    )

    run_config = {
        "standalone_observer": True,
        "world": args.world,
        "persistent_condition": getattr(args, "persistent_condition", None),
        "mechanism": args.mechanism,
        "ticks": args.ticks,
    }
    if life_pack is not None:
        run_config.update(
            {
                "environmental_perturbation_pack": life_pack.manifest(),
                "life_condition": args.life_condition,
                "perturbation_tick": args.perturbation_tick,
            }
        )
    if args.world == "obstacle-value":
        run_config.update(
            {
                "organism_world_foundation": "0.3.2",
                "obstacle_value_ecology": True,
                "obstacle_condition": args.obstacle_condition,
                "preset_avoidance": False,
                "preset_object_value": False,
            }
        )
    if args.world == "organism":
        run_config.update(
            {
                "organism_world_foundation": "0.3",
                "resource_layout": args.resource_layout,
                "random_event_rate": args.random_event_rate,
                "body_truth_agent_visible": False,
                "exogenous_event_receipts_agent_visible": False,
            }
        )
    if args.world == "contextual-objects":
        run_config.update(
            {
                "milestone": "Contextual Object Ecology x Compositional World",
                "preset_combination_knowledge": False,
                "privileged_sequence_model": False,
                "persistent_object_motion": True,
                "ecology_seed": args.seed,
                "world_dimensions": [32, 32],
                "object_count": len(world.world_config.objects),
                "finite_object_state": True,
                "memory_architecture": args.mechanism,
                "bounded_cognition": args.mechanism.startswith("bounded-"),
                "experience_gated_cognition": args.mechanism.startswith(
                    "psyche-v05"
                ),
                "world_dynamics": getattr(args, "world_dynamics", "static"),
                "autonomous_dynamics_enabled": getattr(
                    args, "world_dynamics", "static"
                )
                == "dynamic",
                "perception_mode": getattr(
                    args, "perception_mode", "contact-only"
                ),
                "recovery_dynamics_enabled": bool(
                    getattr(args, "recovery_dynamics", False)
                ),
                "developmental_subsidy_ticks": int(
                    getattr(args, "developmental_subsidy_ticks", 0) or 0
                ),
                "cue_mode": {
                    "legacy": "LEGACY_CUE_ONLY",
                    "perceptual": "PERCEPTUAL_CUE_ENABLED",
                }.get(
                    getattr(args, "cue_mode", "legacy"),
                    getattr(args, "cue_mode", "LEGACY_CUE_ONLY"),
                ),
                "memory_parameters": (
                    mechanism.config.to_dict()
                    if isinstance(mechanism, ExperienceCompressionMechanism)
                    else None
                ),
                "developmental": (
                    {"condition": args.mechanism}
                    if args.mechanism.startswith("psyche-v05")
                    else None
                ),
            }
        )
    if args.world == "object-manipulation":
        run_config.update(
            {
                "acceptance_protocol": "objective-object-manipulation",
                "real_runtime": True,
                "ui_authoritative": False,
            }
        )

    engine = Engine(
        world=world,
        agents={"A001": Agent(agent_id="A001")},
        seed=args.seed,
        mechanisms=registry,
        observer=observer,
        run_config=run_config,
    )

    for _ in range(args.ticks):
        engine.step()
        if args.tick_delay_ms:
            time.sleep(args.tick_delay_ms / 1000.0)
    engine.close()

    print(f"[Observer] psychology JSONL: {psychology_jsonl}")
    print(f"[Observer] ARCHON bridge JSONL: {archon_jsonl}")
    if long_run_path is not None:
        print(f"[Observer] LONG-RUN telemetry: {long_run_path}")
    if life_pack is not None:
        print(
            "[Observer] life condition: "
            f"{args.life_condition} pack={life_pack.pack_id} "
            f"effective_tick={args.perturbation_tick}"
        )


if __name__ == "__main__":
    main()
