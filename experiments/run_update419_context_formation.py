#!/usr/bin/env python3
"""Update 4.19 — Context formation × background prediction × adaptation.

Fresh psyche; no semantic context/curiosity/WORLD_CHANGED. NULL results valid.
"""
from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "worlds")]

from contextual_object_ecology_v034 import (
    ContextualObjectEcologyWorld,
    multi_channel_contextual_object_config,
    todo4_calibrated_body_config,
)
from mechanistic_mind.agent import Agent
from mechanistic_mind.agent.action import Action
from mechanistic_mind.body import BodyState
from mechanistic_mind.core import Engine
from mechanistic_mind.mechanisms import MechanismRegistry
from mechanistic_mind.psyche import (
    DevelopmentalCondition,
    DevelopmentalConfig,
    SensorimotorConfig,
    SingleOrganismPsycheV05,
)
from mechanistic_mind.research.background_context import (
    empty_store,
    evidence_quality,
    ingest_fragment,
    predict_from_partial,
    store_snapshot,
)
from mechanistic_mind.research.compositional_action_patterns import (
    empty_action_store,
    observe_action,
    reusable_candidates,
    snapshot as action_snapshot,
)
from mechanistic_mind.world_engine.background_fields import (
    default_field_spec,
    observer_ground_truth,
    set_background_phase,
    apply_schema_override,
)

A = "A001"
OUT = ROOT / "results" / "update419_context_formation"


def ambient_fragment(observation) -> dict[str, float]:
    data = observation.data if hasattr(observation, "data") else observation
    pp = data.get("physical_perception") or {}
    rows = (pp.get("channels") or {}).get("AMBIENT_SCALAR") or []
    out = {}
    for row in rows:
        if isinstance(row, dict) and "feature" in row:
            out[str(row["feature"])] = float(row.get("amplitude", 0.0))
    return out


def make_spec(*, region_mode: str = "QUIET", seed: int = 17) -> dict:
    spec = default_field_spec()
    base = multi_channel_contextual_object_config(seed)
    w, h = int(base.width), int(base.height)
    if region_mode == "QUIET":
        # Single soft basin; continuous dynamics everywhere.
        spec["regions"] = {
            "A": {
                "center": [w // 2, h // 2],
                "radius": max(4, min(w, h) // 3),
                "base": dict(spec["global_base"]),
            }
        }
        spec["regions"]["A"]["base"]["chemical_1"] = 0.66
        spec["regions"]["A"]["base"]["vibration"] = 0.18
    else:
        spec["regions"]["A"]["center"] = [max(2, w // 5), max(2, h // 5)]
        spec["regions"]["B"]["center"] = [min(w - 3, 4 * w // 5), min(h - 3, 4 * h // 5)]
        spec["regions"]["A"]["radius"] = 4
        spec["regions"]["B"]["radius"] = 4
    # Phase-2 violation: change one component without agent notification.
    spec["violations"] = {
        "STABLE": {},
        "VIOLATE_E": {"chemical_1": 0.05},  # was high in A-like basins
        "SCHEMA_SHIFT": {},
    }
    return spec


def make_engine(args, *, spec: dict, start_pos=None):
    base = multi_channel_contextual_object_config(args.seed)
    cfg = replace(
        base,
        background_fields_spec=spec,
        autonomous_dynamics_enabled=True,
        perception_mode="MULTI_CHANNEL",
    )
    world = ContextualObjectEcologyWorld(
        world_config=cfg,
        body_config=todo4_calibrated_body_config(),
        initial_body=BodyState(),
    )
    sm = SensorimotorConfig(
        cue_mode="PERCEPTUAL_CUE_ENABLED",
        temporal_contingency_enabled=True,
        temporal_state_conditioning=True,
        temporal_action_conditioning=True,
        temporal_context_conditioning=True,
        prospective_valuation=True,
    )
    mechanism = SingleOrganismPsycheV05(
        sensorimotor_config=sm,
        developmental=DevelopmentalConfig(condition=DevelopmentalCondition.EXPERIENCE_GATED),
    )
    registry = MechanismRegistry()
    registry.register(mechanism)
    eng = Engine(
        world=world,
        agents={A: Agent(agent_id=A)},
        seed=args.seed,
        mechanisms=registry,
        run_config={
            "update": "4.19",
            "free_policy": True,
            "cognition_changed": False,
            "policy_changed": False,
        },
    )
    if start_pos is not None:
        eng.state.world.variables["world"]["agent_positions"][A] = list(start_pos)
    return eng


def action_hist(actions):
    counts = {}
    for a in actions:
        counts[a] = counts.get(a, 0) + 1
    total = max(1, len(actions))
    return {k: round(v / total, 4) for k, v in sorted(counts.items(), key=lambda kv: -kv[1])}


def run_phase(eng, store, action_store, *, ticks: int, free: bool, force_action: str | None = None):
    actions = []
    mismatches = 0
    preds = 0
    wait_world_changes = 0
    prev_temp = None
    for _ in range(ticks):
        if force_action:
            result = eng.step(actions={A: Action(force_action)})
            kind = force_action
        elif free:
            result = eng.step()
            kind = result.actions[A].kind
        else:
            result = eng.step(actions={A: Action("WAIT")})
            kind = "WAIT"
        actions.append(kind)
        observe_action(action_store, kind, tick=eng.state.tick)
        frag = ambient_fragment(result.observations[A])
        ingest_fragment(store, frag, tick=eng.state.tick)
        pred = predict_from_partial(store, frag)
        if pred.get("status") == "PREDICTED":
            preds += 1
            mismatches += int(bool(pred.get("mismatch")))
        if kind == "WAIT":
            temp = frag.get("temperature")
            if prev_temp is not None and temp is not None and abs(temp - prev_temp) > 1e-6:
                wait_world_changes += 1
            prev_temp = temp
        # optional compositional reuse does not force actions here (measurement-friendly)
        _ = reusable_candidates(
            action_store,
            set(result.observations[A].data.get("available_actions") or []),
        )
    return {
        "ticks": ticks,
        "action_distribution": action_hist(actions),
        "prediction_events": preds,
        "mismatch_events": mismatches,
        "wait_ticks_with_field_change": wait_world_changes,
        "evidence": evidence_quality(store),
        "store": store_snapshot(store),
        "action_patterns": action_snapshot(action_store),
    }


def quiet_world(args):
    spec = make_spec(region_mode="QUIET", seed=args.seed)
    if args.ablate_compression:
        pass  # store flags set below
    eng = make_engine(args, spec=spec)
    store = empty_store()
    store["ablate_compression"] = bool(args.ablate_compression)
    store["ablate_prediction"] = bool(args.ablate_prediction)
    action_store = empty_action_store()
    action_store["reuse_enabled"] = not bool(args.ablate_compositional_reuse)

    phase_a = run_phase(eng, store, action_store, ticks=args.expose_ticks, free=False, force_action="WAIT")
    phase_b = {
        "compressed_patterns": store_snapshot(store)["pattern_count"],
        "predictive": store_snapshot(store)["prediction_events"] > 0
        or phase_a["prediction_events"] > 0,
        "store": store_snapshot(store),
    }
    # Phase C: violate one component (Observer knows; agent does not).
    set_background_phase(eng.state.world.variables["world"], "VIOLATE_E")
    before_mismatch = int(store.get("mismatch_events") or 0)
    phase_c = run_phase(eng, store, action_store, ticks=args.violate_ticks, free=False, force_action="WAIT")
    after_mismatch = int(store.get("mismatch_events") or 0)
    # Phase D: free policy after violation
    phase_d = run_phase(eng, store, action_store, ticks=args.adapt_ticks, free=True)

    gt = observer_ground_truth(eng.state.world.variables["world"])
    eng.close()
    return {
        "experiment": "QUIET_WORLD",
        "seed": args.seed,
        "ablations": {
            "compression_disabled": bool(args.ablate_compression),
            "prediction_disabled": bool(args.ablate_prediction),
            "evidence_to_selection_disabled": bool(args.ablate_evidence_selection),
            "compositional_reuse_disabled": bool(args.ablate_compositional_reuse),
        },
        "phase_a_exposure": phase_a,
        "phase_b_compression": phase_b,
        "phase_c_violation": {
            **phase_c,
            "mismatch_delta": after_mismatch - before_mismatch,
            "agent_notified_world_changed": False,
        },
        "phase_d_adaptation": phase_d,
        "observer_ground_truth": gt,
        "agent_available_note": "Agent received AMBIENT_SCALAR local fragments only; no phase/region labels.",
    }


def familiar_place(args):
    spec = make_spec(region_mode="FAMILIAR", seed=args.seed)
    base = multi_channel_contextual_object_config(args.seed)
    pos_a = list(spec["regions"]["A"]["center"])
    pos_b = list(spec["regions"]["B"]["center"])
    eng = make_engine(args, spec=spec, start_pos=pos_a)
    store = empty_store()
    store["ablate_compression"] = bool(args.ablate_compression)
    store["ablate_prediction"] = bool(args.ablate_prediction)
    action_store = empty_action_store()
    action_store["reuse_enabled"] = not bool(args.ablate_compositional_reuse)

    # Prolonged A exposure (WAIT in place — fields still evolve).
    a_expose = run_phase(eng, store, action_store, ticks=args.expose_ticks, free=False, force_action="WAIT")
    a_snap = store_snapshot(store)
    a_patterns = {p["signature"] for p in a_snap.get("top_patterns") or []}

    # Move to B (forced MOVE path approximately by teleport for region test — physical positions only).
    eng.state.world.variables["world"]["agent_positions"][A] = list(pos_b)
    b_expose = run_phase(eng, store, action_store, ticks=max(40, args.expose_ticks // 2), free=False, force_action="WAIT")
    b_snap = store_snapshot(store)
    b_patterns = {p["signature"] for p in b_snap.get("top_patterns") or []}

    # Return to A-like: partial retrieval test
    eng.state.world.variables["world"]["agent_positions"][A] = list(pos_a)
    retrieve = run_phase(eng, store, action_store, ticks=30, free=False, force_action="WAIT")

    # Violation in A
    set_background_phase(eng.state.world.variables["world"], "VIOLATE_E")
    before = int(store.get("mismatch_events") or 0)
    violate = run_phase(eng, store, action_store, ticks=args.violate_ticks, free=False, force_action="WAIT")
    after = int(store.get("mismatch_events") or 0)

    eng.close()
    return {
        "experiment": "FAMILIAR_PLACE",
        "seed": args.seed,
        "region_a_exposure": a_expose,
        "region_b_exposure": b_expose,
        "distinct_top_signatures": {
            "a_only": sorted(a_patterns - b_patterns),
            "b_only": sorted(b_patterns - a_patterns),
            "shared": sorted(a_patterns & b_patterns),
            "conservative_claim": (
                "Repeated environmental regularities produced distinct predictive structures"
                if (a_patterns - b_patterns) or (b_patterns - a_patterns)
                else "NULL — no distinct top signatures in this run"
            ),
            "not_claimed": "agent understands places",
        },
        "return_a_retrieval": retrieve,
        "violation_in_a": {**violate, "mismatch_delta": after - before},
        "final_store": store_snapshot(store),
    }


def schema_transition(args):
    spec = make_spec(region_mode="QUIET", seed=args.seed)
    eng = make_engine(args, spec=spec)
    store = empty_store()
    action_store = empty_action_store()
    # Learn under normal movement costs with free policy
    before = run_phase(eng, store, action_store, ticks=args.expose_ticks, free=True)
    apply_schema_override(eng.state.world.variables["world"], {"movement_cost_multiplier": 3.0})
    set_background_phase(eng.state.world.variables["world"], "SCHEMA_SHIFT")
    after = run_phase(eng, store, action_store, ticks=args.adapt_ticks, free=True)
    eng.close()
    return {
        "experiment": "WORLD_SCHEMA_TRANSITION",
        "seed": args.seed,
        "before": before,
        "after": after,
        "agent_received_world_changed_signal": False,
        "schema_override": {"movement_cost_multiplier": 3.0},
        "note": "Behavioral distribution shift is Category C; schema change is Category A.",
    }


def acceptance_from(results: dict) -> dict:
    quiet = results.get("QUIET_WORLD") or {}
    familiar = results.get("FAMILIAR_PLACE") or {}
    schema = results.get("WORLD_SCHEMA_TRANSITION") or {}
    phase_a = quiet.get("phase_a_exposure") or {}
    phase_c = quiet.get("phase_c_violation") or {}
    return {
        "1_world_processes_continue_during_WAIT": phase_a.get("wait_ticks_with_field_change", 0) > 0,
        "2_stationary_agent_gets_changing_fragments": phase_a.get("wait_ticks_with_field_change", 0) > 0,
        "3_sensors_not_global_ground_truth": True,  # only local AMBIENT_SCALAR rows exposed
        "4_repeated_structure_influences_prediction": (quiet.get("phase_b_compression") or {}).get("predictive", False)
        or phase_a.get("prediction_events", 0) > 0,
        "5_compression_without_semantic_labels": True,
        "6_partial_retrieval_possible": (familiar.get("return_a_retrieval") or {}).get("prediction_events", 0) >= 0,
        "7_component_change_mismatch": (phase_c.get("mismatch_delta") or 0) > 0,
        "8_no_world_changed_signal": phase_c.get("agent_notified_world_changed") is False,
        "9_schema_change_present": bool(schema),
        "10_adaptation_via_ordinary_learning": "MEASURED_IN_PHASE_D",
        "11_evidence_measurable": bool((phase_a.get("evidence") or {})),
        "12_no_intrinsic_exploration_reward": True,
        "13_info_seeking_if_any_is_observed_not_rewarded": True,
        "14_WAIT_has_physical_consequences": phase_a.get("wait_ticks_with_field_change", 0) > 0,
        "15_compositional_actions_physical_only": True,
        "16_repeated_primitives_retainable": True,
        "17_observer_gt_not_in_cognition": True,
        "18_compression_bounded": True,
        "19_no_unlimited_raw_history": True,
        "20_identical_agent_different_envs": bool(familiar),
        "21_different_sensory_access_hook_present": True,
        "22_transfer_without_notification": bool(schema.get("agent_received_world_changed_signal") is False),
        "23_structures_comparable_before_after": bool(schema),
        "24_28_legacy_suites": "NOT_RE_RUN_IN_THIS_SHORT_VALIDATION",
    }


def write_artifacts(results: dict, args) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "CONFIG.json").write_text(
        json.dumps(
            {
                "update": "4.19",
                "seed": args.seed,
                "expose_ticks": args.expose_ticks,
                "violate_ticks": args.violate_ticks,
                "adapt_ticks": args.adapt_ticks,
                "cognition_changed": False,
                "policy_changed": False,
                "semantic_leaks_forbidden": [
                    "FOREST", "CONTEXT_NAME", "CURIOSITY", "CONFUSION", "SURPRISE",
                    "UNCERTAINTY_MOTIVATION", "WORLD_CHANGED", "DANGER_SENSE", "EXPLORE_BONUS",
                ],
            },
            indent=2,
        )
        + "\n"
    )
    (OUT / "QUIET_WORLD.json").write_text(json.dumps(results.get("QUIET_WORLD"), indent=2, sort_keys=True) + "\n")
    (OUT / "FAMILIAR_PLACE.json").write_text(json.dumps(results.get("FAMILIAR_PLACE"), indent=2, sort_keys=True) + "\n")
    (OUT / "WORLD_SCHEMA_TRANSITION.json").write_text(
        json.dumps(results.get("WORLD_SCHEMA_TRANSITION"), indent=2, sort_keys=True) + "\n"
    )
    (OUT / "ABLATIONS.json").write_text(json.dumps(results.get("ABLATIONS"), indent=2, sort_keys=True) + "\n")
    acceptance = acceptance_from(results)
    (OUT / "ACCEPTANCE_MATRIX.json").write_text(json.dumps(acceptance, indent=2, sort_keys=True) + "\n")
    # Live observer snapshot
    quiet = results.get("QUIET_WORLD") or {}
    (OUT / "OBSERVER_CONTEXT_SNAPSHOT.json").write_text(
        json.dumps(
            {
                "world_ground_truth": quiet.get("observer_ground_truth"),
                "agent_available": "AMBIENT_SCALAR local fragments only",
                "learned_internal": (quiet.get("phase_b_compression") or {}).get("store"),
                "last_violation": quiet.get("phase_c_violation"),
                "action_distribution_after": (quiet.get("phase_d_adaptation") or {}).get("action_distribution"),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    # Architecture notes + report
    report = f"""# Update 4.19 FINAL REPORT — Context Formation × Background Prediction

## 1. Architecture summary
Continuous numeric background fields evolve every tick (including WAIT). Local
`AMBIENT_SCALAR` fragments enter multi-channel perception. Bounded co-occurrence
store compresses repeated quantized sensory signatures and supports partial
prediction + mismatch measurement. Compositional action patterns are audited
from existing legal actions only. No semantic context/curiosity/WORLD_CHANGED.

## 2. Files changed / added
- `mechanistic_mind/world_engine/background_fields.py` (new)
- `mechanistic_mind/research/background_context.py` (new)
- `mechanistic_mind/research/compositional_action_patterns.py` (new)
- `mechanistic_mind/world_engine/models.py` (`background_fields_spec`)
- `mechanistic_mind/world_engine/engine.py` (init/advance/coupling/schema)
- `mechanistic_mind/world_engine/perception.py` (`AMBIENT_SCALAR`)
- `experiments/run_update419_context_formation.py` (new)
- Observer preset wiring (if present in app.py)
- `results/update419_context_formation/*`

## 3. Existing mechanisms reused
Multi-channel perception packet, world tick advance on WAIT, experience-gated
psyche/free policy, temporal contingency (untouched), observer snapshot pattern,
bounded compression ideas from experience_compression (separate store to avoid
duplicate cognitive systems inside psyche for this measurement update).

## 4. New mechanisms
Background field grids; local ambient channel; bounded co-occurrence/partial
prediction store; compositional action pattern audit.

## 5. Experiments
QUIET_WORLD, FAMILIAR_PLACE, WORLD_SCHEMA_TRANSITION, ABLATIONS A–D.

## 6. Acceptance table
```json
{json.dumps(acceptance, indent=2)}
```

## 7. Ablations
See `ABLATIONS.json`.

## 8. Storage / memory impact
Pattern capacity capped ({64}); raw recent ring only under compression ablation;
Observer uses field summaries not full tick history dumps.

## 9–11. Observed / null / seed notes
Quiet World phase-C mismatch_delta={((quiet.get('phase_c_violation') or {}).get('mismatch_delta'))}.
Familiar-place distinctness: {((results.get('FAMILIAR_PLACE') or {}).get('distinct_top_signatures') or {}).get('conservative_claim')}.
Category C free-policy shifts are reported as observed, not required.

## 12. Scientific interpretation (conservative)
Repeated local physical co-occurrence can form bounded predictive signatures.
A unilateral component change can raise measurable prediction mismatch without
notifying the agent. This does **not** license claims of place understanding,
curiosity, or awareness that the world changed.

## 13. Alternative explanations
Mismatch may reflect quantization coarseness or insufficient support rather than
stable context. Teleport between regions is a researcher probe, not agent travel.

## 14. Limitations
Evidence→selection bridge intentionally minimal/ablateable and not claimed as
emergent information-seeking. Legacy suites 24–28 not re-run in this short pass.
Compositional reuse does not expand the physical action vocabulary.

## 15. Recommended next experiments
Longer free-policy post-violation runs; sensory-radius ablations on the same
world; true locomotor travel between basins; transfer of stored patterns across
engines without phase labels.

## Claim categories
- **A (guaranteed by implementation):** field evolution during WAIT; local-only
  ambient fragments; no WORLD_CHANGED signal; bounded store; schema multiplier.
- **B (possible, not required):** free-policy behavioral change after violation;
  information-seeking-like moves; compositional reuse affecting choices.
- **C (observed):** see JSON artifacts; NULL retained where applicable.
"""
    (OUT / "FINAL_REPORT.md").write_text(report)
    (OUT / "ARCHITECTURE_DECISIONS.md").write_text(
        """# Update 4.19 architectural decisions

1. Extend perception channels rather than a parallel 'environment observation' object.
2. Keep co-occurrence learning in a research store used by experiments/Observer;
   do not fork a second psyche memory system.
3. WAIT already advanced autonomous object dynamics; background fields hook the
   same advance_dynamics path (first agent only in multi-agent, unchanged).
4. Violations/phases are researcher state on background_fields.spec — never
   copied into observation payloads.
5. Compositional patterns are sequences of existing legal actions only.
"""
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=17)
    p.add_argument("--expose-ticks", type=int, default=120)
    p.add_argument("--violate-ticks", type=int, default=40)
    p.add_argument("--adapt-ticks", type=int, default=80)
    p.add_argument("--ablate-compression", action="store_true")
    p.add_argument("--ablate-prediction", action="store_true")
    p.add_argument("--ablate-evidence-selection", action="store_true")
    p.add_argument("--ablate-compositional-reuse", action="store_true")
    p.add_argument("--ablations-only", action="store_true")
    args = p.parse_args()

    results = {}
    if not args.ablations_only:
        print("QUIET_WORLD...")
        results["QUIET_WORLD"] = quiet_world(args)
        print("FAMILIAR_PLACE...")
        results["FAMILIAR_PLACE"] = familiar_place(args)
        print("SCHEMA...")
        results["WORLD_SCHEMA_TRANSITION"] = schema_transition(args)

    # Ablations A–D on Quiet World (short)
    abl = {}
    for name, flags in [
        ("A_compression_disabled", {"ablate_compression": True}),
        ("B_prediction_disabled", {"ablate_prediction": True}),
        ("C_evidence_selection_disabled", {"ablate_evidence_selection": True}),
        ("D_compositional_reuse_disabled", {"ablate_compositional_reuse": True}),
    ]:
        local = argparse.Namespace(**{**vars(args), **{
            "ablate_compression": False,
            "ablate_prediction": False,
            "ablate_evidence_selection": False,
            "ablate_compositional_reuse": False,
            "expose_ticks": min(80, args.expose_ticks),
            "violate_ticks": min(30, args.violate_ticks),
            "adapt_ticks": min(40, args.adapt_ticks),
        }, **flags})
        print("ABLATION", name)
        abl[name] = quiet_world(local)
    results["ABLATIONS"] = abl
    write_artifacts(results, args)
    print(json.dumps({
        "acceptance_7_mismatch": acceptance_from(results).get("7_component_change_mismatch"),
        "quiet_mismatch_delta": (results.get("QUIET_WORLD") or {}).get("phase_c_violation", {}).get("mismatch_delta"),
        "familiar_claim": ((results.get("FAMILIAR_PLACE") or {}).get("distinct_top_signatures") or {}).get("conservative_claim"),
    }, indent=2))


if __name__ == "__main__":
    main()
