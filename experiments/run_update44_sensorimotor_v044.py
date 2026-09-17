#!/usr/bin/env python3
"""Update 4.4 experiment matrix (A–G core). No curiosity/exploration rewards."""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "worlds"))

from contextual_object_ecology_v034 import (  # noqa: E402
    ContextualObjectEcologyWorld,
    multi_channel_contextual_object_config,
)
from mechanistic_mind.agent import Action, Agent
from mechanistic_mind.body import BodyState
from mechanistic_mind.core import Engine
from mechanistic_mind.mechanisms import MechanismRegistry
from mechanistic_mind.observer import CompositeSink, InMemorySink, PsychologyObserver
from mechanistic_mind.psyche import (
    DevelopmentalCondition,
    DevelopmentalConfig,
    SingleOrganismPsycheV05,
)
from mechanistic_mind.psyche.sensorimotor import SensorimotorConfig
from mechanistic_mind.research.developmental_subsidy import (
    apply_subsidy_to_body_config,
    apply_subsidy_to_body_state,
    baseline_unsubsidized_spec,
    subsidy_from_tick_equivalent,
)
from mechanistic_mind.research.motor_control import MotorControlConfig, MotorControlState
from mechanistic_mind.research.sensorimotor_bootstrap import (
    SensorimotorBootstrapStore,
    microvariation_telemetry,
)
from mechanistic_mind.research.sensorimotor_physics import (
    finalize_fragment_perception,
    step_motor_variation,
)

try:
    from experiments.run_update42_mds_v042 import _body_cfg
except Exception:  # pragma: no cover
    from mechanistic_mind.body import BodyConfig

    def _body_cfg(recovery: bool = True) -> BodyConfig:
        return BodyConfig(recovery_dynamics_enabled=recovery)


OUT = ROOT / "results" / "update44_sensorimotor_bootstrap_v044"

def _inject_bootstrap_store(engine: Engine, store: SensorimotorBootstrapStore) -> None:
    """Persist bootstrap store into ordinary psyche memory for later retrieval/bridge."""
    try:
        ag = engine.state.agents["A001"]
        ms = ag.mechanism_states.get("PSYCHE-SENSORIMOTOR-V05")
        if not isinstance(ms, dict):
            return
        psyche = ms.setdefault("psyche", {})
        memory = psyche.setdefault("memory", {})
        memory["sensorimotor_bootstrap"] = store.to_dict()
    except Exception:
        pass


def _read_bridge_trace(engine: Engine) -> dict:
    try:
        ag = engine.state.agents["A001"]
        ms = ag.mechanism_states.get("PSYCHE-SENSORIMOTOR-V05") or {}
        psyche = ms.get("psyche") or {}
        working = psyche.get("working") or {}
        last_sel = working.get("last_selection") or {}
        bridge = working.get("mp_bridge") or {}
        cands = last_sel.get("candidates") or []
        mp_cands = [
            c for c in cands
            if isinstance(c, dict) and (
                c.get("source") == "MOTOR_PRIMITIVE_BRIDGE"
                or (isinstance(c.get("proposal_source"), str) and "MOTOR_PRIMITIVE" in str(c.get("proposal_source")))
            )
        ]
        # also detect via metadata mirrored into selection candidates
        for c in cands:
            if isinstance(c, dict) and str(c.get("source", "")).endswith("BRIDGE"):
                if c not in mp_cands:
                    mp_cands.append(c)
        return {
            "selected": last_sel.get("action"),
            "reason": last_sel.get("reason"),
            "score": last_sel.get("score"),
            "bridge": bridge,
            "candidate_actions": [c.get("action") for c in cands if isinstance(c, dict)],
            "mp_candidate_actions": [
                c.get("action") for c in cands
                if isinstance(c, dict) and (
                    "MOTOR_PRIMITIVE" in str(c.get("source", ""))
                    or c.get("mp_bridge")
                )
            ],
            "n_candidates": len(cands),
        }
    except Exception as e:
        return {"error": str(e)}



def _spec(subsidy_te: int | None):
    if subsidy_te is None or subsidy_te <= 0:
        return baseline_unsubsidized_spec()
    return subsidy_from_tick_equivalent(int(subsidy_te))


def _world(seed: int, spec, *, dynamic: bool = True):
    from dataclasses import replace as dc_replace

    cfg = multi_channel_contextual_object_config(seed)
    # Runtime-verified binding: multi_channel starts DYNAMIC; STATIC clears flag + object autonomy.
    if not dynamic:
        new_objects = []
        for obj in cfg.objects:
            try:
                new_objects.append(dc_replace(obj, autonomous=None))
            except TypeError:
                new_objects.append(obj)
        cfg = dc_replace(
            cfg,
            autonomous_dynamics_enabled=False,
            objects=tuple(new_objects),
        )
    # Verify intervention actually stuck
    assert bool(getattr(cfg, "autonomous_dynamics_enabled", None)) is bool(dynamic), (
        cfg,
        dynamic,
    )
    return ContextualObjectEcologyWorld(
        world_config=cfg,
        body_config=apply_subsidy_to_body_config(_body_cfg(True), spec),
        initial_body=apply_subsidy_to_body_state(BodyState(), spec),
    )


def _engine(world, seed: int, arm: str, **run_extra):
    reg = MechanismRegistry()
    reg.register(
        SingleOrganismPsycheV05(
            sensorimotor_config=SensorimotorConfig(cue_mode="PERCEPTUAL_CUE_ENABLED"),
            developmental=DevelopmentalConfig(
                condition=DevelopmentalCondition.EXPERIENCE_GATED
            ),
        )
    )
    return Engine(
        world=world,
        agents={"A001": Agent(agent_id="A001")},
        seed=seed,
        mechanisms=reg,
        observer=PsychologyObserver(CompositeSink([InMemorySink()]), compact_ticks=True),
        run_config={"update": "4.4", "arm": arm, "cue_mode": "PERCEPTUAL_CUE_ENABLED", **run_extra},
    )


def _stash_research(engine: Engine, motor: MotorControlState, store: SensorimotorBootstrapStore) -> None:
    try:
        variables = engine.state.world.variables
        if not isinstance(variables, dict):
            return
        prims = store.primitives
        latest = None
        latest_support = None
        latest_contra = None
        latest_reuse = None
        if prims:
            latest_p = sorted(prims.values(), key=lambda p: p.first_recognition_tick or 0)[-1]
            latest = latest_p.primitive_id
            latest_support = latest_p.support
            latest_contra = latest_p.contradiction_rate
            latest_reuse = latest_p.reuse_count
        variables["research_u44"] = {
            "motor_control": motor.to_dict(),
            "sensorimotor_bootstrap": {
                "variation_event_count": store.variation_event_count,
                "contingency_count": len(store.contingencies),
                "primitive_count": len(store.primitives),
                "latest_primitive": latest,
                "latest_support": latest_support,
                "latest_contradiction": latest_contra,
                "latest_reuse": latest_reuse,
                "last_perceptual_delta": (
                    (store.recent_fragments[-1] or {}).get("perceptual_delta_tokens")
                    if store.recent_fragments
                    else None
                ),
                "last_ingest_key": (
                    (store.recent_fragments[-1] or {}).get("context_bucket")
                    if store.recent_fragments
                    else None
                ),
                "last_retrieval": "ENABLED" if store.retrieval_enabled else "ABLATED",
                "observer_note": "OBSERVER ONLY — NOT AVAILABLE TO COGNITION",
            },
        }
    except Exception:
        pass


def run_high_level(seed: int, ticks: int, subsidy_te: int | None, *, dynamic: bool = True) -> dict:
    spec = _spec(subsidy_te)
    eng = _engine(_world(seed, spec, dynamic=dynamic), seed, "HIGH_LEVEL_BASELINE", dynamic=dynamic)
    actions = []
    t0 = time.time()
    for _ in range(ticks):
        actions.append(eng.step().actions["A001"].kind)
    eng.close()
    fam = Counter(a.split(":", 1)[0] for a in actions)
    return {
        "arm": "HIGH_LEVEL_BASELINE",
        "seed": seed,
        "ticks": ticks,
        "subsidy_te": subsidy_te or 0,
        "dynamic": dynamic,
        "elapsed_sec": time.time() - t0,
        "action_families": dict(fam),
        "first_25": actions[:25],
        "emit_rate": fam.get("EMIT", 0) / max(1, ticks),
        "move_rate": fam.get("MOVE", 0) / max(1, ticks),
        "wait_rate": fam.get("WAIT", 0) / max(1, ticks),
    }


def run_sensorimotor(
    seed: int,
    ticks: int,
    subsidy_te: int | None,
    *,
    variation: bool = True,
    retrieval: bool = True,
    reduced_resistance: bool = False,
    dynamic: bool = True,
    arm_name: str = "SENSORIMOTOR_VARIATION_ONLY",
    free_policy_after: int | None = None,
) -> dict:
    """B/C/D/E/F/G family.

    free_policy_after: if set, phase1 motor-only for N ticks then free policy (C).
    """
    spec = _spec(subsidy_te)
    eng = _engine(
        _world(seed, spec, dynamic=dynamic),
        seed,
        arm_name,
        motor_variation=variation,
        retrieval_enabled=retrieval,
        reduced_resistance=reduced_resistance,
        dynamic=dynamic,
    )
    mcfg = MotorControlConfig(
        endogenous_variation=variation,
        enabled=variation,
        # F diagnostic: lower threshold → more attempts; reduced_resistance bypasses block
        displace_threshold=0.35 if reduced_resistance else 0.55,
    )
    mstate = MotorControlState.from_dict(None, n=mcfg.n_channels)
    store = SensorimotorBootstrapStore(retrieval_enabled=retrieval)
    applied = []
    effects = Counter()
    phase2_actions = []
    bridge_traces = []
    t0 = time.time()

    # Monkey-patch is_open for reduced resistance diagnostic if needed
    world = eng.world
    original_is_open = getattr(world, "is_open", None)

    def open_always(state, dest, **kwargs):
        return True

    if reduced_resistance and original_is_open is not None:
        world.is_open = open_always  # type: ignore

    phase1 = ticks if free_policy_after is None else int(free_policy_after)
    phase1 = min(phase1, ticks)

    for tick in range(phase1):
        try:
            obs_before = dict(world.observe(eng.state, "A001").data)
        except Exception:
            obs_before = {"position": [0, 0], "visible_objects": [], "interoception": {}}
        # For reduced resistance, physics helper still calls is_open — already patched
        step = step_motor_variation(
            world=world,
            state=eng.state,
            agent_id="A001",
            motor_state=mstate,
            store=store,
            config=mcfg,
            seed=seed,
            tick=tick,
            observation_before=obs_before,
            apply_world_move=True,
        )
        mstate = step["motor_state"]
        effects[step["effect_kind"]] += 1
        _stash_research(eng, mstate, store)
        if step.get("move_action"):
            forced = {"A001": Action(step["move_action"])}
        else:
            forced = {"A001": Action("WAIT")}
        result = eng.step(actions=forced)
        applied.append(result.actions["A001"].kind)
        try:
            obs_after = dict(result.observations["A001"].data)
        except Exception:
            obs_after = obs_before
        finalize_fragment_perception(store, step["fragment"], obs_before, obs_after)

    # Phase 2 free policy (C/D) — inject store into psyche memory; bridge may emit candidates.
    bridge_traces = []
    if free_policy_after is not None and phase1 < ticks:
        if original_is_open is not None:
            world.is_open = original_is_open  # type: ignore
        _inject_bootstrap_store(eng, store)
        for tick in range(phase1, ticks):
            _inject_bootstrap_store(eng, store)
            _stash_research(eng, mstate, store)
            result = eng.step()
            a = result.actions["A001"].kind
            applied.append(a)
            phase2_actions.append(a)
            if tick < phase1 + 15 or tick in (phase1 + 25, ticks - 1):
                tr = _read_bridge_trace(eng)
                tr["tick"] = tick
                tr["executed"] = a
                bridge_traces.append(tr)

    if original_is_open is not None and reduced_resistance:
        try:
            world.is_open = original_is_open  # type: ignore
        except Exception:
            pass

    eng.close()
    fam = Counter(a.split(":", 1)[0] for a in applied)
    fam2 = Counter(a.split(":", 1)[0] for a in phase2_actions) if phase2_actions else {}
    return {
        "arm": arm_name,
        "seed": seed,
        "ticks": ticks,
        "subsidy_te": subsidy_te or 0,
        "variation": variation,
        "retrieval_enabled": retrieval,
        "reduced_resistance": reduced_resistance,
        "dynamic": dynamic,
        "dynamic_verified": bool(
            getattr(getattr(world, "config", None), "autonomous_dynamics_enabled", dynamic)
        ),
        "free_policy_after": free_policy_after,
        "elapsed_sec": time.time() - t0,
        "action_families": dict(fam),
        "phase2_families": dict(fam2),
        "effect_kinds": dict(effects),
        "first_25_actions": applied[:25],
        "phase2_first_25": phase2_actions[:25],
        "microvariation": microvariation_telemetry(store),
        "primitives": {k: v.to_dict() for k, v in store.primitives.items()},
        "contingency_count": len(store.contingencies),
        "motor_final": mstate.to_dict(),
        "bridge_traces": bridge_traces if free_policy_after is not None else [],
        "bridge_summary": {
            "phase2_ticks": len(phase2_actions),
            "traces_n": len(bridge_traces) if free_policy_after is not None else 0,
            "mp_candidate_ticks": sum(
                1 for t in (bridge_traces if free_policy_after is not None else [])
                if t.get("mp_candidate_actions")
            ),
            "mp_selected_ticks": sum(
                1
                for t in (bridge_traces if free_policy_after is not None else [])
                if t.get("selected") in (t.get("mp_candidate_actions") or [])
            ),
            "retrieval_enabled": retrieval,
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--arm",
        default="MATRIX_CORE",
        choices=[
            "HIGH_LEVEL_BASELINE",
            "SENSORIMOTOR_VARIATION_ONLY",
            "BOOTSTRAP_THEN_FREE",
            "EXPERIENCE_ABLATION",
            "MOTOR_VARIATION_ABLATION",
            "REDUCED_RESISTANCE",
            "STATIC_WORLD",
            "DYNAMIC_WORLD",
            "MATRIX_CORE",
            "MATRIX_DECISIVE",
            "SMOKE_BOTH",
            "MDS_AUDIT",
        ],
    )
    ap.add_argument("--ticks", type=int, default=100)
    ap.add_argument("--seed", type=int, default=17)
    ap.add_argument("--subsidy-ticks", type=int, default=0)
    ap.add_argument("--bootstrap-ticks", type=int, default=40)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    results: dict = {}
    seed, ticks = args.seed, args.ticks
    sub = args.subsidy_ticks

    if args.arm in ("HIGH_LEVEL_BASELINE", "MATRIX_CORE", "SMOKE_BOTH"):
        results["A_unsubsidized"] = run_high_level(seed, ticks, 0, dynamic=True)
        if args.arm == "MATRIX_CORE":
            results["A_mds1000"] = run_high_level(seed, ticks, 1000, dynamic=True)

    if args.arm in ("SENSORIMOTOR_VARIATION_ONLY", "MATRIX_CORE", "SMOKE_BOTH"):
        results["B"] = run_sensorimotor(
            seed, ticks, sub, variation=True, retrieval=True, arm_name="SENSORIMOTOR_VARIATION_ONLY"
        )

    if args.arm in ("BOOTSTRAP_THEN_FREE", "MATRIX_CORE"):
        results["C"] = run_sensorimotor(
            seed,
            ticks,
            sub,
            variation=True,
            retrieval=True,
            free_policy_after=args.bootstrap_ticks,
            arm_name="BOOTSTRAP_THEN_FREE",
        )

    if args.arm in ("EXPERIENCE_ABLATION", "MATRIX_CORE"):
        results["D"] = run_sensorimotor(
            seed,
            ticks,
            sub,
            variation=True,
            retrieval=False,
            free_policy_after=args.bootstrap_ticks,
            arm_name="EXPERIENCE_ABLATION",
        )

    if args.arm in ("MOTOR_VARIATION_ABLATION", "MATRIX_CORE"):
        results["E"] = run_sensorimotor(
            seed, ticks, sub, variation=False, retrieval=True, arm_name="MOTOR_VARIATION_ABLATION"
        )

    if args.arm in ("REDUCED_RESISTANCE", "MATRIX_CORE"):
        results["F_reduced"] = run_sensorimotor(
            seed,
            ticks,
            sub,
            variation=True,
            reduced_resistance=True,
            arm_name="REDUCED_RESISTANCE",
        )

    if args.arm in ("STATIC_WORLD", "MATRIX_CORE"):
        results["G_static"] = run_sensorimotor(
            seed, ticks, sub, variation=True, dynamic=False, arm_name="STATIC_WORLD"
        )
    if args.arm in ("DYNAMIC_WORLD", "MATRIX_CORE"):
        results["G_dynamic"] = run_sensorimotor(
            seed, ticks, sub, variation=True, dynamic=True, arm_name="DYNAMIC_WORLD"
        )

    if args.arm == "MATRIX_DECISIVE":
        # Smallest decisive set after bridge: C vs D + verified G + unsubsidized A
        results["A_unsubsidized"] = run_high_level(seed, ticks, 0, dynamic=True)
        results["C"] = run_sensorimotor(
            seed, ticks, sub, variation=True, retrieval=True,
            free_policy_after=args.bootstrap_ticks, arm_name="BOOTSTRAP_THEN_FREE",
        )
        results["D"] = run_sensorimotor(
            seed, ticks, sub, variation=True, retrieval=False,
            free_policy_after=args.bootstrap_ticks, arm_name="EXPERIENCE_ABLATION",
        )
        results["G_static"] = run_sensorimotor(
            seed, min(ticks, 60), sub, variation=True, dynamic=False, arm_name="STATIC_WORLD"
        )
        results["G_dynamic"] = run_sensorimotor(
            seed, min(ticks, 60), sub, variation=True, dynamic=True, arm_name="DYNAMIC_WORLD"
        )

    if args.arm == "MDS_AUDIT":
        results["A0"] = run_high_level(seed, ticks, 0, dynamic=True)
        results["A1000"] = run_high_level(seed, ticks, 1000, dynamic=True)

    path = OUT / f"arm_{args.arm.lower()}_seed{seed}_t{ticks}_sub{sub}.json"
    path.write_text(json.dumps(results, indent=2, default=str))

    brief = {}
    for k, v in results.items():
        brief[k] = {
            "arm": v.get("arm"),
            "subsidy_te": v.get("subsidy_te"),
            "families": v.get("action_families"),
            "phase2": v.get("phase2_families"),
            "effects": v.get("effect_kinds"),
            "primitives": len(v.get("primitives") or {}),
            "contingencies": v.get("contingency_count"),
            "micro": {
                kk: (v.get("microvariation") or {}).get(kk)
                for kk in ("variation_events", "displace_rate", "no_effect_rate", "contact_rate")
            },
            "bridge": v.get("bridge_summary"),
            "dynamic_verified": v.get("dynamic_verified"),
            "first25": (v.get("first_25") or v.get("first_25_actions") or [])[:10],
            "phase2_first10": (v.get("phase2_first_25") or [])[:10],
        }
    print(json.dumps(brief, indent=2))
    print("wrote", path)


if __name__ == "__main__":
    main()
