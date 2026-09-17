#!/usr/bin/env python3
"""Update 4.5 — Prospective consequence valuation decisive matrix.

No curiosity / novelty / MP bonus / confidence-as-value.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
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
except Exception:
    from mechanistic_mind.body import BodyConfig

    def _body_cfg(recovery: bool = True):
        return BodyConfig(recovery_dynamics_enabled=recovery)


OUT = ROOT / "results" / "update45_prospective_valuation_v045"


def _spec(te):
    if not te:
        return baseline_unsubsidized_spec()
    return subsidy_from_tick_equivalent(int(te))


def _engine(seed, spec, *, prospective=True, prediction_ablated=False, bridge=True):
    world = ContextualObjectEcologyWorld(
        world_config=multi_channel_contextual_object_config(seed),
        body_config=apply_subsidy_to_body_config(_body_cfg(True), spec),
        initial_body=apply_subsidy_to_body_state(BodyState(), spec),
    )
    reg = MechanismRegistry()
    reg.register(
        SingleOrganismPsycheV05(
            sensorimotor_config=SensorimotorConfig(
                cue_mode="PERCEPTUAL_CUE_ENABLED",
                motor_primitive_bridge=bridge,
                prospective_valuation=prospective,
                prediction_ablated=prediction_ablated,
            ),
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
        run_config={
            "update": "4.5",
            "prospective_valuation": prospective,
            "prediction_ablated": prediction_ablated,
        },
    ), world


def _inject(eng, store):
    try:
        psy = eng.state.agents["A001"].mechanism_states["PSYCHE-SENSORIMOTOR-V05"]["psyche"]
        psy.setdefault("memory", {})["sensorimotor_bootstrap"] = store.to_dict()
    except Exception:
        pass


def _trace(eng):
    try:
        psy = eng.state.agents["A001"].mechanism_states["PSYCHE-SENSORIMOTOR-V05"]["psyche"]
        working = psy.get("working") or {}
        sel = working.get("last_selection") or {}
        bridge = working.get("mp_bridge") or {}
        rows = bridge.get("rows") or []
        cands = sel.get("candidates") or []
        mp_actions = []
        for c in cands:
            if not isinstance(c, dict):
                continue
            src = str(c.get("source", ""))
            if "MOTOR_PRIMITIVE" in src or c.get("mp_bridge"):
                mp_actions.append(c.get("action"))
        return {
            "selected": sel.get("action"),
            "reason": sel.get("reason"),
            "score": sel.get("score"),
            "n_candidates": len(cands),
            "mp_candidate_actions": mp_actions,
            "bridge_rows": rows,
            "prospective_values": [
                r.get("ordinary_value") for r in rows if isinstance(r, dict)
            ],
            "epistemic_statuses": [
                r.get("epistemic_status") for r in rows if isinstance(r, dict)
            ],
            "value_sources": [r.get("value_source") for r in rows if isinstance(r, dict)],
            "predicted_deltas": [
                r.get("predicted_signal_deltas") for r in rows if isinstance(r, dict)
            ],
        }
    except Exception as e:
        return {"error": str(e)}


def run_bootstrap_then_free(
    *,
    seed: int,
    ticks: int,
    bootstrap_ticks: int,
    subsidy_te: int,
    retrieval: bool,
    prospective: bool,
    prediction_ablated: bool,
    arm_name: str,
):
    spec = _spec(subsidy_te)
    eng, world = _engine(
        seed, spec, prospective=prospective, prediction_ablated=prediction_ablated, bridge=True
    )
    mcfg = MotorControlConfig()
    mstate = MotorControlState.from_dict(None, n=2)
    store = SensorimotorBootstrapStore(retrieval_enabled=retrieval)
    actions = []
    effects = Counter()
    phase2 = []
    traces = []
    t0 = time.time()
    b = min(bootstrap_ticks, ticks)
    for tick in range(b):
        try:
            obs_b = dict(world.observe(eng.state, "A001").data)
        except Exception:
            obs_b = {"position": [0, 0], "visible_objects": [], "interoception": {}}
        step = step_motor_variation(
            world=world,
            state=eng.state,
            agent_id="A001",
            motor_state=mstate,
            store=store,
            config=mcfg,
            seed=seed,
            tick=tick,
            observation_before=obs_b,
            apply_world_move=True,
        )
        mstate = step["motor_state"]
        effects[step["effect_kind"]] += 1
        forced = {"A001": Action(step["move_action"] or "WAIT")}
        result = eng.step(actions=forced)
        actions.append(result.actions["A001"].kind)
        try:
            obs_a = dict(result.observations["A001"].data)
        except Exception:
            obs_a = obs_b
        if not step.get("fragment", {}).get("skipped"):
            finalize_fragment_perception(store, step["fragment"], obs_b, obs_a)

    store.retrieval_enabled = retrieval
    for tick in range(b, ticks):
        _inject(eng, store)
        result = eng.step()
        a = result.actions["A001"].kind
        actions.append(a)
        phase2.append(a)
        if tick < b + 20 or tick == ticks - 1:
            tr = _trace(eng)
            tr["tick"] = tick
            tr["executed"] = a
            traces.append(tr)
    eng.close()
    fam = Counter(x.split(":")[0] for x in actions)
    fam2 = Counter(x.split(":")[0] for x in phase2)
    mp_cand_ticks = sum(1 for t in traces if t.get("mp_candidate_actions"))
    mp_sel = sum(
        1
        for t in traces
        if t.get("selected") in (t.get("mp_candidate_actions") or [])
    )
    prosp_nonzero = sum(
        1
        for t in traces
        for v in (t.get("prospective_values") or [])
        if isinstance(v, (int, float)) and abs(float(v)) > 1e-12
    )
    return {
        "arm": arm_name,
        "seed": seed,
        "ticks": ticks,
        "bootstrap_ticks": b,
        "retrieval": retrieval,
        "prospective": prospective,
        "prediction_ablated": prediction_ablated,
        "subsidy_te": subsidy_te,
        "elapsed_sec": time.time() - t0,
        "action_families": dict(fam),
        "phase2_families": dict(fam2),
        "effect_kinds": dict(effects),
        "microvariation": microvariation_telemetry(store),
        "primitives": {k: v.to_dict() for k, v in store.primitives.items()},
        "contingency_sample": {
            k: {
                "support": v.support,
                "mean_body_delta": v.mean_body_delta,
                "last_displacement": v.last_displacement,
                "contradiction": v.contradiction,
            }
            for k, v in list(store.contingencies.items())[:5]
        },
        "bridge_summary": {
            "traces_n": len(traces),
            "mp_candidate_ticks": mp_cand_ticks,
            "mp_selected_ticks": mp_sel,
            "prospective_nonzero_count": prosp_nonzero,
        },
        "bridge_traces": traces,
        "phase2_first_25": phase2[:25],
    }


def run_high_level(seed, ticks, subsidy_te):
    spec = _spec(subsidy_te)
    eng, _ = _engine(seed, spec, prospective=True, prediction_ablated=False, bridge=True)
    acts = []
    t0 = time.time()
    for _ in range(ticks):
        acts.append(eng.step().actions["A001"].kind)
    eng.close()
    fam = Counter(a.split(":")[0] for a in acts)
    return {
        "arm": "HIGH_LEVEL",
        "seed": seed,
        "ticks": ticks,
        "subsidy_te": subsidy_te,
        "elapsed_sec": time.time() - t0,
        "action_families": dict(fam),
        "first_25": acts[:25],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", default="MATRIX_DECISIVE", choices=["MATRIX_DECISIVE", "MDS_REGRESSION"])
    ap.add_argument("--ticks", type=int, default=100)
    ap.add_argument("--bootstrap-ticks", type=int, default=40)
    ap.add_argument("--seed", type=int, default=17)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    results = {}
    if args.arm == "MATRIX_DECISIVE":
        results["A_update44_style"] = run_bootstrap_then_free(
            seed=args.seed, ticks=args.ticks, bootstrap_ticks=args.bootstrap_ticks,
            subsidy_te=0, retrieval=True, prospective=False, prediction_ablated=False,
            arm_name="UPDATE44_BASELINE_NO_PROSPECTIVE",
        )
        results["B_prospective"] = run_bootstrap_then_free(
            seed=args.seed, ticks=args.ticks, bootstrap_ticks=args.bootstrap_ticks,
            subsidy_te=0, retrieval=True, prospective=True, prediction_ablated=False,
            arm_name="PROSPECTIVE_VALUATION",
        )
        results["C_retained"] = run_bootstrap_then_free(
            seed=args.seed, ticks=args.ticks, bootstrap_ticks=args.bootstrap_ticks,
            subsidy_te=0, retrieval=True, prospective=True, prediction_ablated=False,
            arm_name="EXPERIENCE_RETAINED",
        )
        results["D_ablated"] = run_bootstrap_then_free(
            seed=args.seed, ticks=args.ticks, bootstrap_ticks=args.bootstrap_ticks,
            subsidy_te=0, retrieval=False, prospective=True, prediction_ablated=False,
            arm_name="EXPERIENCE_ABLATED",
        )
        results["E_pred_ablated"] = run_bootstrap_then_free(
            seed=args.seed, ticks=args.ticks, bootstrap_ticks=args.bootstrap_ticks,
            subsidy_te=0, retrieval=True, prospective=True, prediction_ablated=True,
            arm_name="PREDICTION_ABLATED",
        )
    if args.arm == "MDS_REGRESSION":
        results["H0"] = run_high_level(args.seed, 40, 0)
        results["H1000"] = run_high_level(args.seed, 40, 1000)

    path = OUT / f"arm_{args.arm.lower()}_seed{args.seed}_t{args.ticks}.json"
    path.write_text(json.dumps(results, indent=2, default=str))
    brief = {}
    for k, v in results.items():
        brief[k] = {
            "arm": v.get("arm"),
            "families": v.get("action_families"),
            "phase2": v.get("phase2_families"),
            "bridge": v.get("bridge_summary"),
            "effects": v.get("effect_kinds"),
            "first10_phase2": (v.get("phase2_first_25") or v.get("first_25") or [])[:10],
            "contingency_sample": v.get("contingency_sample"),
        }
    print(json.dumps(brief, indent=2, default=str))
    print("wrote", path)


if __name__ == "__main__":
    main()
