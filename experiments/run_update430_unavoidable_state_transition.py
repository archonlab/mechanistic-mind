#!/usr/bin/env python3
"""Update 4.30 - Unavoidable state transition under non-intervention."""
from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "worlds"), str(ROOT / "experiments")]

from mechanistic_mind.research import unavoidable_state_transition as ust
from mechanistic_mind.research import prospective_composition as pc
from mechanistic_mind.research import prospective_consequence_influence as pci

OUT = ROOT / "results" / "update430_unavoidable_state_transition"
SEEDS = [17, 23, 41, 59, 83]
N_WAIT = 5
VALUE_REV_TOL = 0.02   # pre-registered: prediction revision in ordinary_value
ACTION_DELTA_TOL = 0.03  # pre-registered: action distribution shift


def dump(name, obj):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n")


def value_shift(before: dict, after: dict, key: str = "B") -> float | None:
    vb = (before.get(key) or {}).get("ordinary_value")
    va = (after.get(key) or {}).get("ordinary_value")
    if vb is None or va is None:
        return None
    return float(va) - float(vb)


def run_seed(seed: int, n_wait: int = N_WAIT) -> dict:
    goals = pci.default_goals()
    out: dict = {"seed": seed}

    # --- A. Continuing-world WAIT ---
    store = pc.empty_store()
    prior = ust.train_prior_prospective(store, n=40, seed=seed)
    world = ust.empty_world(freeze_field=False, informative=True)
    # start at low field
    world["field_level"] = 0.10
    traj = ust.run_wait_trajectory(
        store=store, world=world, goals=goals, n_wait=n_wait,
        ablate_revision=False, learn_field_distal=True, seed=seed,
    )
    out["prior"] = prior
    out["continuing_world"] = {
        "timeline": traj["timeline"],
        "prediction_before": traj["prediction_before"],
        "prediction_after": traj["prediction_after"],
        "action_before": traj["action_before"],
        "action_after": traj["action_after"],
        "field_delta": traj["field_delta"],
        "body_energy_delta": traj["body_energy_delta"],
        "world_final": traj["world_final"],
        "value_shift_B": value_shift(traj["prediction_before"], traj["prediction_after"], "B"),
        "value_shift_A": value_shift(traj["prediction_before"], traj["prediction_after"], "A"),
        "delta_P_B": traj["action_after"]["P_B"] - traj["action_before"]["P_B"],
        "delta_P_A": traj["action_after"]["P_A"] - traj["action_before"]["P_A"],
        "delta_P_WAIT": traj["action_after"]["P_WAIT"] - traj["action_before"]["P_WAIT"],
    }

    # C1: physical evolution under WAIT
    c1 = all(step["state_changed"] for step in traj["timeline"]) and abs(traj["field_delta"]) > 1e-6
    out["C1_continuing_physical_evolution_under_WAIT"] = bool(c1)

    # C2: new accessible evidence (field_signal changes) without reveal action
    c2 = all(step["evidence_changed"] for step in traj["timeline"])
    out["C2_passive_acquisition_of_new_accessible_evidence"] = bool(c2)

    # --- B. Frozen-world control ---
    store_f = pc.empty_store()
    ust.train_prior_prospective(store_f, n=40, seed=seed)
    world_f = ust.empty_world(freeze_field=True, informative=True)
    world_f["field_level"] = 0.10
    traj_f = ust.run_wait_trajectory(
        store=store_f, world=world_f, goals=goals, n_wait=n_wait,
        ablate_revision=False, learn_field_distal=True, seed=seed + 10,
    )
    out["frozen_world_control"] = {
        "field_delta": traj_f["field_delta"],
        "value_shift_B": value_shift(traj_f["prediction_before"], traj_f["prediction_after"], "B"),
        "delta_P_B": traj_f["action_after"]["P_B"] - traj_f["action_before"]["P_B"],
        "evidence_changed_any": any(s["evidence_changed"] for s in traj_f["timeline"]),
        "state_field_static": abs(traj_f["field_delta"]) < 1e-9,
    }

    # --- C. Non-informative evolution ---
    store_ni = pc.empty_store()
    ust.train_prior_prospective(store_ni, n=40, seed=seed)
    world_ni = ust.empty_world(freeze_field=False, informative=False)
    world_ni["field_level"] = 0.10
    traj_ni = ust.run_wait_trajectory(
        store=store_ni, world=world_ni, goals=goals, n_wait=n_wait,
        ablate_revision=False, learn_field_distal=True, seed=seed + 20,
    )
    out["noninformative_evolution_control"] = {
        "field_delta": traj_ni["field_delta"],
        "value_shift_B": value_shift(traj_ni["prediction_before"], traj_ni["prediction_after"], "B"),
        "delta_P_B": traj_ni["action_after"]["P_B"] - traj_ni["action_before"]["P_B"],
    }

    # --- D/E. ACTION_A / ACTION_B controls from matched start ---
    def run_active(action: str, sseed: int) -> dict:
        st = pc.empty_store()
        ust.train_prior_prospective(st, n=40, seed=seed)
        w = ust.empty_world(freeze_field=False, informative=True)
        w["field_level"] = 0.10
        timeline = []
        for i in range(n_wait):
            eb = ust.accessible_evidence(w)
            w2 = ust.step_physics(w, action)
            ea = ust.accessible_evidence(w2)
            ust.online_learn_from_step(st, ev_before=eb, action=action, ev_after=ea, tick=30000 + i)
            ust.revise_distal_from_field_experience(
                st, field_level=float(w2["field_level"]), informative=True,
                tick=31000 + i * 10,
            )
            timeline.append({
                "field_before": float(w["field_level"]),
                "field_after": float(w2["field_level"]),
            })
            w = w2
        pred = ust.snapshot_predictions(st, goals)
        act = ust.action_probe(st, goals, seed=sseed)
        return {"timeline": timeline, "prediction": pred, "action": act, "field_final": w["field_level"]}

    out["action_A_control"] = run_active("A1", seed + 30)
    out["action_B_control"] = run_active("B1", seed + 40)

    # --- F. Revision ablation ---
    store_ra = pc.empty_store()
    ust.train_prior_prospective(store_ra, n=40, seed=seed)
    world_ra = ust.empty_world(freeze_field=False, informative=True)
    world_ra["field_level"] = 0.10
    traj_ra = ust.run_wait_trajectory(
        store=store_ra, world=world_ra, goals=goals, n_wait=n_wait,
        ablate_revision=True, learn_field_distal=True, seed=seed + 50,
    )
    out["revision_ablation"] = {
        "field_delta": traj_ra["field_delta"],
        "evidence_changed_any": any(s["evidence_changed"] for s in traj_ra["timeline"]),
        "value_shift_B": value_shift(traj_ra["prediction_before"], traj_ra["prediction_after"], "B"),
        "delta_P_B": traj_ra["action_after"]["P_B"] - traj_ra["action_before"]["P_B"],
    }

    # --- G. Consequence-to-action ablation (use_distal=False after revision) ---
    store_ca = pc.empty_store()
    ust.train_prior_prospective(store_ca, n=40, seed=seed)
    world_ca = ust.empty_world(freeze_field=False, informative=True)
    world_ca["field_level"] = 0.10
    # run with revision, but measure action without distal
    traj_ca = ust.run_wait_trajectory(
        store=store_ca, world=world_ca, goals=goals, n_wait=n_wait,
        ablate_revision=False, learn_field_distal=True, seed=seed + 60,
    )
    act_off_before = ust.action_probe(store_ca, goals, seed=seed + 61, use_distal=False)
    # re-probe: we need before/after with distal off — approximate using final store only vs prior clone
    store_prior_only = pc.empty_store()
    ust.train_prior_prospective(store_prior_only, n=40, seed=seed)
    act_off_prior = ust.action_probe(store_prior_only, goals, seed=seed + 62, use_distal=False)
    act_off_after = ust.action_probe(store_ca, goals, seed=seed + 63, use_distal=False)
    out["consequence_action_ablation"] = {
        "prediction_value_shift_B": value_shift(traj_ca["prediction_before"], traj_ca["prediction_after"], "B"),
        "delta_P_B_distal_off": act_off_after["P_B"] - act_off_prior["P_B"],
        "delta_P_B_distal_on": traj_ca["action_after"]["P_B"] - traj_ca["action_before"]["P_B"],
    }

    # --- H. Shuffled / already covered by noninformative ---
    out["shuffled_decorrelated"] = out["noninformative_evolution_control"]

    # --- Claim evaluation ---
    vs_b = out["continuing_world"]["value_shift_B"]
    # C3: prediction revises under continuing informative WAIT; frozen should not (or much less);
    # revision ablation should remove it; noninformative should weaken.
    c3 = (
        vs_b is not None
        and abs(float(vs_b)) >= VALUE_REV_TOL
        and (
            out["frozen_world_control"]["value_shift_B"] is None
            or abs(float(out["frozen_world_control"]["value_shift_B"] or 0)) < abs(float(vs_b)) - 0.005
            or out["frozen_world_control"]["state_field_static"]
        )
        and abs(float(out["revision_ablation"]["value_shift_B"] or 0)) < VALUE_REV_TOL
    )
    # If frozen still revises via learn_field_distal using static field - need check.
    # With field stuck at 0.10, revise_distal uses low-field branch — may still update.
    # Require continuing informative shift larger than frozen shift.
    frozen_vs = abs(float(out["frozen_world_control"]["value_shift_B"] or 0))
    cont_vs = abs(float(vs_b or 0))
    ni_vs = abs(float(out["noninformative_evolution_control"]["value_shift_B"] or 0))
    ab_vs = abs(float(out["revision_ablation"]["value_shift_B"] or 0))
    c3 = (
        vs_b is not None
        and cont_vs >= VALUE_REV_TOL
        and frozen_vs < VALUE_REV_TOL  # no new field evidence => no regime revision
        and ab_vs < 1e-9
        and ni_vs < VALUE_REV_TOL  # decorrelated: no distal remapping
    )
    out["C3_evidence_driven_prediction_revision"] = bool(c3)
    out["C3_diagnostics"] = {
        "continuing_value_shift_B": vs_b,
        "frozen_value_shift_B": out["frozen_world_control"]["value_shift_B"],
        "noninfo_value_shift_B": out["noninformative_evolution_control"]["value_shift_B"],
        "ablation_value_shift_B": out["revision_ablation"]["value_shift_B"],
        "VALUE_REV_TOL": VALUE_REV_TOL,
    }

    # C4: revised prediction -> revised action via 4.26 pathway
    dpb = out["continuing_world"]["delta_P_B"]
    c4 = bool(
        c3
        and abs(float(dpb)) >= ACTION_DELTA_TOL
        and abs(float(out["consequence_action_ablation"]["delta_P_B_distal_off"])) < ACTION_DELTA_TOL
    )
    out["C4_revised_prediction_to_revised_action"] = bool(c4)
    out["C4_diagnostics"] = {
        "delta_P_B": dpb,
        "ACTION_DELTA_TOL": ACTION_DELTA_TOL,
        "distal_off_delta_P_B": out["consequence_action_ablation"]["delta_P_B_distal_off"],
        "note": "Does not retune EMA; does not rewrite historical 4.26 C4 NULL",
    }

    # C5: complete loop
    c5 = bool(c1 and c2 and c3 and c4)
    out["C5_complete_continuing_world_loop"] = bool(c5)

    # First unsupported arrow
    chain = [
        ("WAIT_to_continuing_physical_evolution", c1),
        ("continuing_evolution_to_new_accessible_evidence", c2),
        ("new_accessible_evidence_to_prediction_revision", c3),
        ("revised_prediction_to_revised_action_distribution", c4),
    ]
    first = None
    for name, ok in chain:
        if not ok:
            first = name
            break
    out["first_unsupported_arrow"] = first or "NONE_ALL_SUPPORTED"
    out["claim_chain"] = chain

    out["leak_tokens"] = ust.audit_forbidden({
        "timeline_keys": list(traj["timeline"][0].keys()) if traj["timeline"] else [],
        "store_keys": list(store.keys()),
    })

    out["relation_426_C4"] = {
        "historical_4_26_C4": "NOT ASSERTED",
        "this_update_C4": c4,
        "ema_retuned": False,
    }
    out["relation_429"] = {
        "historical_4_29_C3": "NOT ASSERTED",
        "action_change_attributed_to_mean_ordinary_value_not_variance": True,
        "variance_added_to_logits": False,
    }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", nargs="*", type=int, default=SEEDS)
    ap.add_argument("--ticks", type=int, default=N_WAIT)
    args = ap.parse_args()
    seeds = args.seeds or SEEDS
    n_wait = int(args.ticks)

    OUT.mkdir(parents=True, exist_ok=True)
    dump("CONFIG.json", {
        "update": "4.30",
        "seeds": seeds,
        "N_WAIT": n_wait,
        "VALUE_REV_TOL": VALUE_REV_TOL,
        "ACTION_DELTA_TOL": ACTION_DELTA_TOL,
        "WAIT_semantics": "no active intervention; field/body continue unless freeze control",
        "no_uncertainty_semantics": True,
        "ema_retuned": False,
        "variance_in_logits": False,
        "DISTAL_BLEND": pci.DISTAL_BLEND,
        "DEFAULT_TEMPERATURE": pci.DEFAULT_TEMPERATURE,
    })

    per = [run_seed(s, n_wait=n_wait) for s in seeds]
    dump("per_seed_results.json", per)

    def sw(pred):
        return [str(r["seed"]) for r in per if pred(r)]

    claim = {
        "C1_continuing_physical_evolution_under_WAIT": {
            "asserted": all(r["C1_continuing_physical_evolution_under_WAIT"] for r in per),
            "seeds": sw(lambda r: r["C1_continuing_physical_evolution_under_WAIT"]),
        },
        "C2_passive_acquisition_of_new_accessible_evidence": {
            "asserted": all(r["C2_passive_acquisition_of_new_accessible_evidence"] for r in per),
            "seeds": sw(lambda r: r["C2_passive_acquisition_of_new_accessible_evidence"]),
        },
        "C3_evidence_driven_prediction_revision": {
            "asserted": all(r["C3_evidence_driven_prediction_revision"] for r in per),
            "seeds": sw(lambda r: r["C3_evidence_driven_prediction_revision"]),
        },
        "C4_revised_prediction_to_revised_action": {
            "asserted": all(r["C4_revised_prediction_to_revised_action"] for r in per),
            "seeds": sw(lambda r: r["C4_revised_prediction_to_revised_action"]),
        },
        "C5_complete_continuing_world_loop": {
            "asserted": all(r["C5_complete_continuing_world_loop"] for r in per),
            "seeds": sw(lambda r: r["C5_complete_continuing_world_loop"]),
        },
    }
    dump("claim_matrix.json", claim)
    dump("summary.json", {
        "claims": claim,
        "first_unsupported_arrows": [r["first_unsupported_arrow"] for r in per],
        "per_seed_deltas": {
            str(r["seed"]): {
                "field_delta": r["continuing_world"]["field_delta"],
                "value_shift_B": r["continuing_world"]["value_shift_B"],
                "delta_P_B": r["continuing_world"]["delta_P_B"],
            }
            for r in per
        },
    })
    dump("timelines.json", {str(r["seed"]): r["continuing_world"]["timeline"] for r in per})
    dump("controls.json", {str(r["seed"]): {
        "frozen": r["frozen_world_control"],
        "noninformative": r["noninformative_evolution_control"],
        "action_A": {"field_final": r["action_A_control"]["field_final"]},
        "action_B": {"field_final": r["action_B_control"]["field_final"]},
        "revision_ablation": r["revision_ablation"],
        "consequence_ablation": r["consequence_action_ablation"],
    } for r in per})
    dump("predictions_before_after.json", {str(r["seed"]): {
        "before": r["continuing_world"]["prediction_before"],
        "after": r["continuing_world"]["prediction_after"],
        "action_before": r["continuing_world"]["action_before"],
        "action_after": r["continuing_world"]["action_after"],
    } for r in per})
    dump("leak_audit.json", {
        "per_seed": [{"seed": r["seed"], "tokens": r["leak_tokens"]} for r in per],
        "any_leak": any(r["leak_tokens"] for r in per),
    })
    dump("ACCEPTANCE_MATRIX.json", {k: v["asserted"] for k, v in claim.items()} | {
        "no_forbidden": not any(r["leak_tokens"] for r in per),
    })
    dump("BASELINE_REGRESSION.json", {
        "preserve_4_25_C3_NOT_ASSERTED": True,
        "preserve_4_26_C4_NOT_ASSERTED": True,
        "preserve_4_28_C2_C3_C4_NOT_ASSERTED": True,
        "preserve_4_29_C3_C4_C5_NOT_ASSERTED": True,
        "ema_retuned": False,
        "status": "NOT_FULLY_RE_RUN_IN_SMOKE",
    })
    dump("INTEGRATION_PRESERVE.json", {
        "metrics_affect_cognition": False,
        "WAIT_is_no_active_intervention_not_pause": True,
        "no_uncertainty_urgency_wait_cost": True,
        "unchanged_DISTAL_BLEND": pci.DISTAL_BLEND,
        "unchanged_T": pci.DEFAULT_TEMPERATURE,
    })

    obs = {
        "update": "4.30",
        "preset": "4.30 Unavoidable State Transition",
        "WAIT_semantics": "NO ACTIVE INTERVENTION (not PAUSE)",
        "claim_matrix": claim,
        "REVISED_PREDICTION_TO_REVISED_ACTION": (
            "OBSERVED" if claim["C4_revised_prediction_to_revised_action"]["asserted"] else "NOT OBSERVED"
        ),
        "COMPLETE_LOOP": (
            "OBSERVED" if claim["C5_complete_continuing_world_loop"]["asserted"] else "NOT OBSERVED"
        ),
        "per_seed": {
            str(r["seed"]): {
                "field_delta": r["continuing_world"]["field_delta"],
                "value_shift_B": r["continuing_world"]["value_shift_B"],
                "delta_P_B": r["continuing_world"]["delta_P_B"],
                "P_B_before": r["continuing_world"]["action_before"]["P_B"],
                "P_B_after": r["continuing_world"]["action_after"]["P_B"],
                "first_unsupported": r["first_unsupported_arrow"],
            }
            for r in per
        },
        "first_unsupported_arrows": [r["first_unsupported_arrow"] for r in per],
        "layers": {
            "WORLD_BODY_EVOLUTION": "autonomous field_rate under WAIT; body metabolizes",
            "ACCESSIBLE_EVIDENCE": "field_signal + body signals (no REVEAL)",
            "PREDICTION_BEFORE_AFTER": "4.23 compose + ordinary_state_value",
            "ORDINARY_STATE_VALUE": "unchanged 4.26 scalar pathway",
            "ACTION_DISTRIBUTION_BEFORE_AFTER": "softmax; no urgency/wait cost",
        },
    }
    dump("OBSERVER_TRANSITION_SNAPSHOT.json", obs)

    lines = [
        "# Update 4.30 FINAL REPORT - Unavoidable State Transition",
        "",
        "## Architecture",
        "WAIT = no active intervention. Autonomous field + body continue evolving.",
        "No UNCERTAINTY/URGENCY/WAIT_COST/DELIBERATION. No EMA retune. No variance in logits.",
        "Online revision via ordinary learn_transition on field-conditioned distal outcomes.",
        "Action via unchanged 4.26 ordinary_state_value → softmax.",
        "",
        "## WAIT semantics",
        "NOT pause/freeze/deliberate. Physical field_rate advances; body metabolizes.",
        "Frozen-world control sets freeze_field=True for comparison only.",
        "",
        "## Claims",
    ]
    for k, v in claim.items():
        st = "ASSERTED" if v["asserted"] else "NOT ASSERTED"
        lines.append(f"- {k}: **{st}** seeds={v['seeds']}")
    lines += ["", "## Per seed"]
    for r in per:
        cw = r["continuing_world"]
        lines.append(
            f"- seed {r['seed']}: fieldΔ={cw['field_delta']:.3f} "
            f"valΔB={cw['value_shift_B']} ΔP_B={cw['delta_P_B']:.4f} "
            f"C1={r['C1_continuing_physical_evolution_under_WAIT']} "
            f"C2={r['C2_passive_acquisition_of_new_accessible_evidence']} "
            f"C3={r['C3_evidence_driven_prediction_revision']} "
            f"C4={r['C4_revised_prediction_to_revised_action']} "
            f"C5={r['C5_complete_continuing_world_loop']} "
            f"first={r['first_unsupported_arrow']}"
        )
    lines += [
        "",
        "## First unsupported arrow",
        f"{[r['first_unsupported_arrow'] for r in per]}",
        "",
        "## Relation to 4.26 C4",
        "Historical 4.26 C4 remains NOT ASSERTED. EMA not retuned.",
        "4.30 C4 is a separate physical-evidence trajectory probe.",
        "",
        "## Relation to 4.29",
        "No variance/reliability term added to action. Any action shift must come from",
        "revised mean distal ordinary_value (4.26 pathway).",
        "",
        "## NOT claimed",
        "deliberation / uncertainty / waiting for evidence / information seeking /",
        "curiosity / metacognition / temporal awareness / urgency",
        "",
        "## Recommended next (deferred §29)",
        "Evidence-producing active action → discriminating evidence → revision → later action",
        "(connect 4.25 observability with continuing-world revision) — not implemented here.",
        "",
    ]
    (OUT / "FINAL_REPORT.md").write_text("\n".join(lines) + "\n")
    print(json.dumps(claim, indent=2))
    print("first", [r["first_unsupported_arrow"] for r in per])
    print("wrote", OUT)


if __name__ == "__main__":
    main()
