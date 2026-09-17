#!/usr/bin/env python3
"""Update 4.6 — stateful object resources / interaction saturation diagnostics.

No familiarity / novelty / repetition penalties.
Compact JSON artifacts only.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "worlds"))

from mechanistic_mind.agent import Action, Agent
from mechanistic_mind.body import BodyConfig, BodyEngine, BodyState
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
    subsidy_from_tick_equivalent,
)
from mechanistic_mind.research.prospective_valuation import prospective_ordinary_value
from mechanistic_mind.world_engine.engine import ObjectiveWorldEngine
from contextual_object_ecology_v034 import (
    ContextualObjectEcologyWorld,
    multi_channel_contextual_object_config,
    todo4_calibrated_body_config,
)

OUT = ROOT / "results" / "update46_object_resources_v046"


def _body_cfg(recovery: bool = True) -> BodyConfig:
    base = todo4_calibrated_body_config()
    d = {f: getattr(base, f) for f in base.__dataclass_fields__}
    d["recovery_dynamics_enabled"] = recovery
    return BodyConfig(**d)


def depletion_test(seed: int = 17) -> dict:
    cfg = multi_channel_contextual_object_config(seed)
    we = ObjectiveWorldEngine(cfg)
    # Prefer hydration or energy with quantity scale
    targets = []
    for o in cfg.objects:
        be = dict(o.body_effects or {})
        if o.effect_scale_state == "quantity" and (
            float(be.get("energy_delta", 0) or 0) > 0
            or float(be.get("hydration_delta", 0) or 0) > 0
        ):
            targets.append(o)
    rows_by_obj = {}
    for obj in targets[:4]:
        st = we.initial_state(agent_id="A001", start_position=tuple(obj.position))
        series = []
        for i in range(25):
            rec = st["objects"][obj.object_id]
            q_before = float(rec.get("quantity") or 0)
            scale = we._effect_scale(rec)
            avail = we._effect_available(rec)
            result = we.transition_action(
                st,
                agent_id="A001",
                action=Action(f"USE:{obj.object_id}"),
                rng=random.Random(seed + i),
                body_context={"fatigue": 0.2},
            )
            st = result.state
            eff = dict(result.external_body_effects or {})
            q_after = float(st["objects"][obj.object_id].get("quantity") or 0)
            series.append(
                {
                    "use_i": i + 1,
                    "quantity_before": q_before,
                    "quantity_after": q_after,
                    "scale": scale,
                    "effect_available": avail,
                    "energy_delta": eff.get("energy_delta"),
                    "hydration_delta": eff.get("hydration_delta"),
                    "transfer_keys": sorted(eff.keys()),
                }
            )
            if q_after <= 1e-12 and not avail and i > 0:
                # continue a few exhausted uses
                if i > 3 and all(s.get("energy_delta") in (None, 0) and s.get("hydration_delta") in (None, 0) for s in series[-2:]):
                    break
        nonzero = [
            s
            for s in series
            if (s.get("energy_delta") or 0) not in (0, None)
            or (s.get("hydration_delta") or 0) not in (0, None)
        ]
        rows_by_obj[obj.object_id] = {
            "position": list(obj.position),
            "body_effects": dict(obj.body_effects or {}),
            "delta_chunk": dict(obj.interaction_state_deltas or {}),
            "series": series,
            "effective_use_count": len(nonzero),
            "quantity_changed": any(
                abs(s["quantity_before"] - s["quantity_after"]) > 1e-12 for s in series
            ),
            "effect_diminished_or_zeroed": any(
                (s.get("energy_delta") in (None, 0) and s.get("hydration_delta") in (None, 0))
                for s in series[1:]
            ),
        }
    return {
        "seed": seed,
        "objects_tested": list(rows_by_obj.keys()),
        "by_object": rows_by_obj,
        "outcome_A_object_depletion": all(
            v["quantity_changed"] and v["effect_diminished_or_zeroed"]
            for v in rows_by_obj.values()
        )
        if rows_by_obj
        else False,
    }


def organism_state_control() -> dict:
    """Same predicted physical transfer, different organism states → prospective value."""
    goals = {
        "signal_targets": {
            "energy_signal": 0.70,
            "hydration_signal": 0.70,
            "fatigue_signal": 0.15,
        },
        "signal_weights": {
            "energy_signal": 1.0,
            "hydration_signal": 1.0,
            "fatigue_signal": 1.0,
        },
    }
    predicted = {
        "energy_delta": 0.10,
        "hydration_delta": 0.0,
        "fatigue_delta": 0.0,
    }
    # map to signal deltas approx capacity 1
    cases = {
        "low_energy": {"energy_signal": 0.25, "hydration_signal": 0.70, "fatigue_signal": 0.20},
        "high_energy": {"energy_signal": 0.85, "hydration_signal": 0.70, "fatigue_signal": 0.20},
        "low_hydration": {"energy_signal": 0.70, "hydration_signal": 0.25, "fatigue_signal": 0.20},
        "high_hydration": {"energy_signal": 0.70, "hydration_signal": 0.85, "fatigue_signal": 0.20},
    }
    out = {}
    for name, signals in cases.items():
        # Convert reserve-like predicted deltas using prospective helper
        from mechanistic_mind.research.prospective_valuation import (
            map_reserve_deltas_to_signal_deltas,
            target_gain_from_predicted_deltas,
        )
        sig_delta = map_reserve_deltas_to_signal_deltas(predicted)
        val = target_gain_from_predicted_deltas(sig_delta, signals, goals)
        out[name] = {"signals": signals, "prospective_regulation": val, "predicted": predicted}
    return {
        "predicted_physical_transfer": predicted,
        "cases": out,
        "outcome_B_organism_state_matters": (
            abs(out["low_energy"]["prospective_regulation"] - out["high_energy"]["prospective_regulation"])
            > 1e-9
        ),
    }


def knowledge_control() -> dict:
    """Frozen physical prediction; only support/confidence varies → value must not track familiarity."""
    goals = {
        "signal_targets": {"energy_signal": 0.7, "hydration_signal": 0.7, "fatigue_signal": 0.15},
        "signal_weights": {"energy_signal": 1.0, "hydration_signal": 1.0, "fatigue_signal": 1.0},
    }
    signals = {"energy_signal": 0.4, "hydration_signal": 0.5, "fatigue_signal": 0.2}
    body = {"energy_delta": 0.08, "hydration_delta": 0.0, "fatigue_delta": 0.01}
    vals = []
    for support in (1, 5, 20, 80):
        r = prospective_ordinary_value(
            mean_body_delta=body,
            body_delta_samples=float(support),
            contradiction=0.0,
            current_signals=signals,
            goals=goals,
            support=float(support),
            prediction_ablated=False,
        )
        vals.append(
            {
                "support": support,
                "ordinary_value": r.get("ordinary_value"),
                "confidence_used_as_value": r.get("confidence_used_as_value"),
                "reason": r.get("reason"),
            }
        )
    numbers = [v["ordinary_value"] for v in vals if v["ordinary_value"] is not None]
    stable = max(numbers) - min(numbers) <= 1e-12 if numbers else False
    return {
        "rows": vals,
        "value_invariant_to_support": stable,
        "outcome_D_or_E_invalid_coupling": (not stable),
        "outcome_C_prediction_path_exists": all(v["ordinary_value"] is not None for v in vals),
    }


def recovery_test(seed: int = 17) -> dict:
    cfg = multi_channel_contextual_object_config(seed)
    we = ObjectiveWorldEngine(cfg)
    regen_objs = [
        o
        for o in cfg.objects
        if o.regeneration_rates
        and o.effect_scale_state == "quantity"
        and float((o.body_effects or {}).get("energy_delta", 0) or 0) > 0
    ]
    if not regen_objs:
        regen_objs = [o for o in cfg.objects if o.regeneration_rates]
    if not regen_objs:
        return {"status": "NO_REGEN_OBJECT", "outcome_recovery": False}
    obj = regen_objs[0]
    st = we.initial_state(agent_id="A001", start_position=tuple(obj.position))
    # deplete
    for i in range(40):
        rec = st["objects"][obj.object_id]
        if float(rec.get("quantity") or 0) <= 0:
            break
        st = we.transition_action(
            st, agent_id="A001", action=Action(f"USE:{obj.object_id}"),
            rng=random.Random(i), body_context={"fatigue": 0.2},
        ).state
    q_depleted = float(st["objects"][obj.object_id].get("quantity") or 0)
    # wait / regenerate via advance_object_states many ticks
    for _ in range(200):
        we.advance_object_states(st)
        # tick bump if present
        st["tick"] = int(st.get("tick", 0)) + 1
    q_after = float(st["objects"][obj.object_id].get("quantity") or 0)
    # interact again
    result = we.transition_action(
        st, agent_id="A001", action=Action(f"USE:{obj.object_id}"),
        rng=random.Random(99), body_context={"fatigue": 0.2},
    )
    eff = dict(result.external_body_effects or {})
    return {
        "object_id": obj.object_id,
        "regeneration_rates": dict(obj.regeneration_rates or {}),
        "quantity_depleted": q_depleted,
        "quantity_after_wait": q_after,
        "recovered": q_after > q_depleted + 1e-9,
        "post_recovery_effects": eff,
        "outcome_recovery": q_after > q_depleted + 1e-9,
    }


def autonomous_run(ticks: int = 1000, seed: int = 17, subsidy_te: int = 1000) -> dict:
    spec = subsidy_from_tick_equivalent(subsidy_te)
    body_cfg = apply_subsidy_to_body_config(_body_cfg(True), spec)
    world = ContextualObjectEcologyWorld(
        world_config=multi_channel_contextual_object_config(seed),
        body_config=body_cfg,
        initial_body=apply_subsidy_to_body_state(BodyState(), spec),
    )
    reg = MechanismRegistry()
    reg.register(
        SingleOrganismPsycheV05(
            sensorimotor_config=SensorimotorConfig(
                cue_mode="PERCEPTUAL_CUE_ENABLED",
                prospective_valuation=True,
            ),
            developmental=DevelopmentalConfig(
                condition=DevelopmentalCondition.EXPERIENCE_GATED
            ),
        )
    )
    sink = InMemorySink()
    eng = Engine(
        world=world,
        agents={"A001": Agent(agent_id="A001")},
        seed=seed,
        mechanisms=reg,
        observer=PsychologyObserver(CompositeSink([sink]), compact_ticks=True),
        run_config={"update": "4.6", "ticks": ticks},
    )
    actions = []
    use_events = []
    t0 = time.time()
    for tick in range(ticks):
        result = eng.step()
        a = result.actions["A001"].kind
        actions.append(a)
        if a.startswith("USE:"):
            oid = a.split(":", 1)[1]
            # pull object quantity from world truth if available
            try:
                truth = world._world_truth(eng.state)
                rec = (truth.get("objects") or {}).get(oid) or {}
                qty = rec.get("quantity")
            except Exception:
                qty = None
            try:
                body = world._body_state(eng.state, "A001")
                e, h = body.energy_reserve, body.hydration
            except Exception:
                e = h = None
            use_events.append(
                {
                    "tick": tick,
                    "object_id": oid,
                    "quantity": qty,
                    "energy": e,
                    "hydration": h,
                }
            )
    eng.close()
    fam = Counter(x.split(":")[0] for x in actions)
    use_counts = Counter(e["object_id"] for e in use_events)
    depleted_seen = []
    for oid, evs in {}.items():
        pass
    # group by object
    by = {}
    for e in use_events:
        by.setdefault(e["object_id"], []).append(e)
    for oid, evs in by.items():
        qs = [x["quantity"] for x in evs if isinstance(x.get("quantity"), (int, float))]
        if qs and min(qs) <= max(qs) and (max(qs) - min(qs) > 1e-9 or min(qs) <= 1e-9):
            depleted_seen.append(
                {
                    "object_id": oid,
                    "uses": len(evs),
                    "qty_first": qs[0],
                    "qty_last": qs[-1],
                    "qty_min": min(qs),
                }
            )
    return {
        "ticks": ticks,
        "seed": seed,
        "subsidy_te": subsidy_te,
        "elapsed_sec": time.time() - t0,
        "action_families": dict(fam),
        "use_count": len(use_events),
        "use_by_object": dict(use_counts),
        "use_events_sample": use_events[:40],
        "objects_with_quantity_change_or_low": depleted_seen,
        "first_40_actions": actions[:40],
        "last_40_actions": actions[-40:],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", default="MATRIX", choices=["MATRIX", "AUTONOMOUS", "ALL"])
    ap.add_argument("--ticks", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=17)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    if args.arm in ("MATRIX", "ALL"):
        dep = depletion_test(args.seed)
        (OUT / "UPDATE46_DEPLETION_TEST.json").write_text(json.dumps(dep, indent=2))
        org = organism_state_control()
        (OUT / "UPDATE46_ORGANISM_STATE_CONTROL.json").write_text(json.dumps(org, indent=2))
        know = knowledge_control()
        (OUT / "UPDATE46_KNOWLEDGE_CONTROL.json").write_text(json.dumps(know, indent=2))
        rec = recovery_test(args.seed)
        (OUT / "UPDATE46_RECOVERY_TEST.json").write_text(json.dumps(rec, indent=2))
        print(json.dumps({
            "depletion_A": dep.get("outcome_A_object_depletion"),
            "organism_B": org.get("outcome_B_organism_state_matters"),
            "knowledge_stable": know.get("value_invariant_to_support"),
            "invalid_DE": know.get("outcome_D_or_E_invalid_coupling"),
            "recovery": rec.get("outcome_recovery"),
        }, indent=2))

    if args.arm in ("AUTONOMOUS", "ALL"):
        auto = autonomous_run(ticks=args.ticks, seed=args.seed, subsidy_te=1000)
        (OUT / "UPDATE46_AUTONOMOUS_RUN.json").write_text(json.dumps(auto, indent=2, default=str))
        print(json.dumps({
            "families": auto["action_families"],
            "use_count": auto["use_count"],
            "use_by_object": auto["use_by_object"],
            "depleted": auto["objects_with_quantity_change_or_low"],
        }, indent=2, default=str))


if __name__ == "__main__":
    main()
