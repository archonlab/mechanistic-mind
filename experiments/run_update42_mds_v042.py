#!/usr/bin/env python3
"""Update 4.2: MDS sweep, physiology controls, forced-diversity diagnostic.

Does NOT retune action economics. Initial physical reserve only.
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "worlds"))

from contextual_object_ecology_v034 import (  # noqa: E402
    ContextualObjectEcologyWorld,
    multi_channel_contextual_object_config,
    todo4_calibrated_body_config,
)
from mechanistic_mind.agent import Action, Agent
from mechanistic_mind.body import BodyConfig, BodyState
from mechanistic_mind.core import Engine
from mechanistic_mind.mechanisms import MechanismRegistry
from mechanistic_mind.observer import CompositeSink, InMemorySink, PsychologyObserver
from mechanistic_mind.psyche import (
    DevelopmentalCondition,
    DevelopmentalConfig,
    SingleOrganismPsycheV05,
)
from mechanistic_mind.psyche.sensorimotor import SensorimotorConfig
from mechanistic_mind.research.developmental_metrics import (
    RunSeries,
    attractor_episodes,
    classify_acquisition_stage,
    learning_runway_before_depletion,
    time_to_policy_collapse,
    window_report,
)
from mechanistic_mind.research.developmental_subsidy import (
    MDS_LADDER_TICK_EQUIVALENT,
    apply_subsidy_to_body_config,
    apply_subsidy_to_body_state,
    baseline_unsubsidized_spec,
    subsidy_from_tick_equivalent,
)
from mechanistic_mind.research.forced_diversity import build_forced_actions_for_tick
from mechanistic_mind.research.long_run_telemetry import LongRunResearchSink


def _body_cfg(recovery: bool = True) -> BodyConfig:
    base = todo4_calibrated_body_config()
    return BodyConfig(
        **{
            **{f.name: getattr(base, f.name) for f in base.__dataclass_fields__.values()},
            "recovery_dynamics_enabled": recovery,
        }
    )


def _extract_row(result, agent_id: str = "A001") -> dict:
    action = result.actions[agent_id].kind
    state_after = result.state_after
    bodies = getattr(state_after, "variables", None)
    # SimulationState layout
    variables = None
    if hasattr(state_after, "world"):
        # try common patterns
        pass
    # Engine stores bodies on world variables via organism world — read from observations + mechanism
    obs = result.observations[agent_id].data
    intero = obs.get("interoception") if isinstance(obs.get("interoception"), dict) else {}
    # body truth from state_after.variables if dict-like
    body = {}
    sa = state_after
    try:
        world_state = getattr(sa, "world", None)
        wvars = getattr(world_state, "variables", None) if world_state is not None else None
        if isinstance(wvars, dict) and isinstance(wvars.get("bodies"), dict):
            body = dict(wvars["bodies"].get(agent_id) or {})
    except Exception:
        body = {}
    if not body:
        # fallback: signals only (lossy)
        body = {
            "energy_reserve": intero.get("energy_signal"),
            "hydration": intero.get("hydration_signal"),
            "fatigue": intero.get("fatigue_signal"),
        }

    working = {}
    agents = getattr(sa, "agents", None)
    if isinstance(agents, dict):
        ag = agents.get(agent_id)
        ms = getattr(ag, "mechanism_states", None) if ag is not None else None
        if ms is None and isinstance(ag, dict):
            ms = ag.get("mechanism_states")
        if isinstance(ms, dict):
            for st in ms.values():
                if not isinstance(st, dict):
                    continue
                psyche = st.get("psyche") if isinstance(st.get("psyche"), dict) else st
                if isinstance(psyche.get("working"), dict):
                    working = psyche["working"]
                    break

    gen = working.get("sensorimotor_generation") if isinstance(working.get("sensorimotor_generation"), dict) else {}
    sel = working.get("last_selection") if isinstance(working.get("last_selection"), dict) else {}
    cue_summary = gen.get("cue_summary") if isinstance(gen.get("cue_summary"), dict) else {}
    # physical transfers from last experience / receipt if present
    last_exp = None
    try:
        wvars = getattr(getattr(sa, "world", None), "variables", None)
        if isinstance(wvars, dict):
            le = wvars.get("last_experience") or {}
            if isinstance(le, dict):
                last_exp = le.get(agent_id)
    except Exception:
        last_exp = None
    energy_pos = False
    hyd_pos = False
    if isinstance(last_exp, dict):
        effects = last_exp.get("experienced_effects") or last_exp.get("body_effects") or {}
        if isinstance(effects, dict):
            if float(effects.get("energy_delta") or 0) > 0:
                energy_pos = True
            if float(effects.get("hydration_delta") or 0) > 0:
                hyd_pos = True
    # also objective effects on body transition receipts
    return {
        "action": action,
        "body": body,
        "cue_mode": gen.get("cue_mode"),
        "perceptual_token_count": cue_summary.get("perceptual_token_count"),
        "retrieval_match": gen.get("retrieval_match") if isinstance(gen.get("retrieval_match"), dict) else {},
        "cognitive_depth": gen.get("cognitive_depth"),
        "cognitive_depth_status": gen.get("cognitive_depth_status"),
        "local_experience_maturity": gen.get("local_experience_maturity"),
        "developmental_stage": gen.get("developmental_stage"),
        "developmental_gate_factor": gen.get("developmental_gate_factor"),
        "selection_reason": sel.get("reason"),
        "decision_source": sel.get("decision_source"),
        "energy_transfer_positive": energy_pos,
        "hydration_transfer_positive": hyd_pos,
    }


def run_simulation(
    *,
    seed: int,
    ticks: int,
    subsidy_tick_equivalent: int | None,
    forced_diversity_ticks: int = 0,
    recovery: bool = True,
    long_run_path: Path | None = None,
    mode: str = "FREE_POLICY",
) -> dict:
    if subsidy_tick_equivalent is None or subsidy_tick_equivalent <= 0:
        spec = baseline_unsubsidized_spec()
    else:
        spec = subsidy_from_tick_equivalent(subsidy_tick_equivalent)

    body_config = apply_subsidy_to_body_config(_body_cfg(recovery), spec)
    initial_body = apply_subsidy_to_body_state(BodyState(), spec)

    world = ContextualObjectEcologyWorld(
        world_config=multi_channel_contextual_object_config(seed),
        body_config=body_config,
        initial_body=initial_body,
    )
    psyche = SingleOrganismPsycheV05(
        sensorimotor_config=SensorimotorConfig(cue_mode="PERCEPTUAL_CUE_ENABLED"),
        developmental=DevelopmentalConfig(condition=DevelopmentalCondition.EXPERIENCE_GATED),
    )
    registry = MechanismRegistry()
    registry.register(psyche)

    sinks = []
    mem = InMemorySink()
    sinks.append(mem)
    long_sink = None
    if long_run_path is not None:
        long_sink = LongRunResearchSink(long_run_path)
        sinks.append(long_sink)

    observer = PsychologyObserver(CompositeSink(sinks), compact_ticks=True)
    engine = Engine(
        world=world,
        agents={"A001": Agent(agent_id="A001")},
        seed=seed,
        mechanisms=registry,
        observer=observer,
        run_config={
            "update": "4.2",
            "cue_mode": "PERCEPTUAL_CUE_ENABLED",
            "perception_mode": "MULTI_CHANNEL",
            "autonomous_dynamics_enabled": True,
            "recovery_dynamics_enabled": recovery,
            "developmental_subsidy": spec.to_dict(),
            "mode": mode,
            "forced_diversity_ticks": forced_diversity_ticks,
        },
    )

    series = RunSeries()
    t0 = time.time()
    for tick in range(ticks):
        forced = None
        if mode == "FORCED_DIVERSITY" and tick < forced_diversity_ticks:
            # availability from last observation if any
            available = ["WAIT", "EMIT"]
            if tick > 0:
                prev = engine  # noqa — use observation from last step stored? 
            # get available from world observe cheaply via last step; first tick use defaults
            obs_actions = None
            try:
                # peek world observation
                from mechanistic_mind.core.state import SimulationState  # noqa
            except Exception:
                pass
            # Use world.observe on current state
            try:
                o = world.observe(world.state, "A001")
                available = list(o.data.get("available_actions") or available)
            except Exception:
                available = ["WAIT", "EMIT"]
            act = build_forced_actions_for_tick(
                tick=tick, available=available, phase_length=forced_diversity_ticks
            )
            forced = {"A001": act}
        result = engine.step(actions=forced)
        row = _extract_row(result)
        series.append_tick(row)
    engine.close()
    elapsed = time.time() - t0

    collapse = time_to_policy_collapse(series.actions)
    attractors = attractor_episodes(series.actions, min_residence=20)
    stage = classify_acquisition_stage(series)
    runway = learning_runway_before_depletion(series)
    windows = window_report(
        series,
        [(0, 100), (100, 500), (500, 1000), (1000, 2000), (2000, 3000), (3000, 4000), (4000, 5000)],
    )
    families = Counter()
    for a in series.actions:
        families[a.split(":", 1)[0]] += 1

    out = {
        "seed": seed,
        "ticks": ticks,
        "mode": mode,
        "subsidy": spec.to_dict(),
        "elapsed_sec": elapsed,
        "action_families": dict(families),
        "emit_rate": families.get("EMIT", 0) / max(1, ticks),
        "wait_rate": families.get("WAIT", 0) / max(1, ticks),
        "move_rate": families.get("MOVE", 0) / max(1, ticks),
        "interaction_rate": sum(families.get(k, 0) for k in ("USE", "TAKE", "PUSH", "RELEASE"))
        / max(1, ticks),
        "collapse": collapse,
        "attractors_top": attractors[:8],
        "acquisition_stage": stage,
        "learning_runway": runway,
        "windows": windows,
        "final_body": {
            "energy": series.energy[-1] if series.energy else None,
            "hydration": series.hydration[-1] if series.hydration else None,
            "fatigue": series.fatigue[-1] if series.fatigue else None,
            "mass": series.mass[-1] if series.mass else None,
        },
        "final_depth": series.depth[-1] if series.depth else None,
        "final_maturity": series.maturity[-1] if series.maturity else None,
        "mean_tokens": (
            sum(x for x in series.tokens if x is not None)
            / max(1, sum(1 for x in series.tokens if x is not None))
        ),
        "long_run_bytes": getattr(long_sink, "_bytes_written", None) if long_sink else None,
    }
    return out


def physiology_controls(ticks: int = 800) -> dict:
    """Body-only schedules without psyche (isolates physics)."""
    from mechanistic_mind.body import BodyEngine
    from mechanistic_mind.agent import Action as Act

    body_config = _body_cfg(True)
    engine = BodyEngine(body_config)
    ambient = {"energy_delta": -0.0008, "hydration_delta": -0.0007, "fatigue_delta": 0.0005}
    emit_extra = {"energy_delta": -0.004, "fatigue_delta": 0.003}

    def run(name, schedule):
        s = BodyState()
        hist = []
        for t in range(1, ticks + 1):
            kind = schedule(t)
            ext = dict(ambient)
            if kind == "EMIT":
                ext["energy_delta"] += emit_extra["energy_delta"]
                ext["fatigue_delta"] += emit_extra["fatigue_delta"]
            dist = 1.0 if kind.startswith("MOVE") else 0.0
            s = engine.transition(s, action=Act(kind), distance=dist, external_effects=ext).state
            if t in (100, 200, 400, 600, 800) or s.energy_reserve <= 0 or s.hydration <= 0:
                hist.append(
                    {
                        "t": t,
                        "E": round(s.energy_reserve, 4),
                        "H": round(s.hydration, 4),
                        "F": round(s.fatigue, 4),
                        "mass": round(s.mass_kg, 2),
                    }
                )
        return {"name": name, "final": hist[-1] if hist else None, "markers": hist}

    return {
        "WAIT": run("WAIT", lambda t: "WAIT"),
        "EMIT": run("EMIT", lambda t: "EMIT"),
        "MOVE": run("MOVE", lambda t: "MOVE:1,1"),
        "MIXED": run("MIXED", lambda t: ("WAIT", "EMIT", "MOVE:1,1", "WAIT")[t % 4]),
    }


def main() -> None:
    out_dir = ROOT / "results" / "update42_mds_v042"
    out_dir.mkdir(parents=True, exist_ok=True)

    controls = physiology_controls(800)
    (out_dir / "physiology_controls.json").write_text(
        json.dumps(controls, indent=2, sort_keys=True)
    )

    # Seed-17 baseline replay (canonical unsubsidized) with LONG-RUN telemetry
    baseline = run_simulation(
        seed=17,
        ticks=400,
        subsidy_tick_equivalent=None,
        long_run_path=out_dir / "seed17_baseline_longrun.jsonl",
        mode="FREE_POLICY",
    )
    (out_dir / "seed17_baseline_2000.json").write_text(
        json.dumps(baseline, indent=2, sort_keys=True, default=str)
    )

    # MDS sweep: ladder × seeds (diagnostic scale — first pass)
    seeds = list(range(17, 17 + 3))  # 3 seeds first pass
    ladder = (250, 500, 1000, 2000)
    sweep = []
    for te in ladder:
        for seed in seeds:
            row = run_simulation(
                seed=seed,
                ticks=400,
                subsidy_tick_equivalent=te,
                mode="FREE_POLICY",
            )
            sweep.append(row)
            print(
                f"MDS te={te} seed={seed} collapse={row['collapse'].get('tick')} "
                f"dom={row['collapse'].get('dominant_action')} stage={row['acquisition_stage']['stage']} "
                f"wait={row['wait_rate']:.3f} emit={row['emit_rate']:.3f}"
            )

    # Forced diversity diagnostic at baseline subsidy
    forced = run_simulation(
        seed=17,
        ticks=400,
        subsidy_tick_equivalent=1000,
        forced_diversity_ticks=80,
        mode="FORCED_DIVERSITY",
    )
    free_cmp = run_simulation(
        seed=17,
        ticks=400,
        subsidy_tick_equivalent=1000,
        mode="FREE_POLICY",
    )

    summary = {
        "update": "4.2",
        "physiology_controls": controls,
        "seed17_baseline_2000": baseline,
        "mds_sweep": sweep,
        "forced_vs_free": {
            "forced": forced,
            "free": free_cmp,
            "maturity_forced": forced.get("final_maturity"),
            "maturity_free": free_cmp.get("final_maturity"),
            "depth_forced": forced.get("final_depth"),
            "depth_free": free_cmp.get("final_depth"),
            "runway_forced": forced.get("learning_runway"),
            "runway_free": free_cmp.get("learning_runway"),
        },
        "notes": [
            "Action economics unchanged.",
            "Subsidy = initial physical reserve/capacity only.",
            "First diagnostic pass: 5 seeds, ladder 250/500/1000/2000, 1500 ticks.",
        ],
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, default=str)
    )
    print("wrote", out_dir / "summary.json")


if __name__ == "__main__":
    main()
