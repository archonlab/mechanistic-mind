"""Update 4.32 - Learning-mediated futures (no information seeking).

Tests whether an endogenous predictive-organization transition can participate
in prospective evaluation of a present action (CONTACT_M), without adding
INFORMATION/CURIOSITY/LEARNING_VALUE.

Expected architectural boundary (from 4.31 code path):
  free_action_probe / present CONTACT_M logits use only matched immediate
  ordinary_state_value; pci.action_logits distal paths are A1/B1/WAIT only;
  composition has no node for predictive-state transition.
"""
from __future__ import annotations

import math
import random
from copy import deepcopy
from typing import Any

from mechanistic_mind.research import evidence_producing_action as epa
from mechanistic_mind.research import instrumental_observation as io
from mechanistic_mind.research import prospective_composition as pc
from mechanistic_mind.research import prospective_consequence_influence as pci
from mechanistic_mind.research.composed_future_value import ordinary_state_value

FORBIDDEN = (
    "SELF_MODEL", "MY_MODEL", "BELIEF", "KNOWLEDGE", "LEARNING", "LEARNING_STATE",
    "MODEL_CHANGE", "FUTURE_ME", "FUTURE_BELIEF", "FUTURE_KNOWLEDGE", "METACOGNITION",
    "SELF_PREDICTION", "COGNITIVE_STATE_VALUE", "INFORMATION", "INFORMATION_GAIN",
    "UNCERTAINTY", "CONFIDENCE", "CURIOSITY", "EPISTEMIC", "LEARNING_VALUE",
    "MODEL_VALUE", "INSPECT", "OBSERVE", "MEASURE", "CORRECT_ACTION", "CORRECT_MODEL",
)

ACTION_DELTA_TOL = 0.03
VALUE_TOL = 0.02
AUTO_PREF_TOL = 0.05


def audit_forbidden(payload: Any) -> list[str]:
    return [t for t in FORBIDDEN if t in str(payload)]


def predictive_structure_snapshot(io_store: dict[str, Any]) -> dict[str, Any]:
    """Researcher view of acquired obs->future organization (not cognition sensor)."""
    pred = io_store.get("pred") or {}
    rows = []
    for key, row in list(pred.items())[:32]:
        n = max(1, int(row.get("n") or 1))
        rows.append({
            "key": key,
            "support": int(row.get("support") or 0),
            "mean": {k: float(v) / n for k, v in (row.get("sum") or {}).items()},
        })
    return {"n_structures": len(pred), "rows": rows}


def structure_l1(a: dict[str, Any], b: dict[str, Any]) -> float:
    """Compare predictive organizations by matching keys' mean futures."""
    ma = {r["key"]: r["mean"] for r in (a.get("rows") or [])}
    mb = {r["key"]: r["mean"] for r in (b.get("rows") or [])}
    keys = set(ma) | set(mb)
    if not keys:
        return 0.0
    total = 0.0
    for k in keys:
        total += io.l1(ma.get(k), mb.get(k))
    return total / len(keys)


def build_matched_pc_prior() -> dict[str, Any]:
    store = pc.empty_store()
    epa.train_later_action_composition(store, n=40)
    return store


def run_endogenous_transition(
    *,
    kind: str,
    seed: int,
    ablate_revision: bool = False,
    use_distal: bool = True,
    mode: str = "useful",
) -> dict[str, Any]:
    """Phase 1: evidence -> predictive-org change -> later action (reuse 4.31 path)."""
    chain = epa.forced_contact_chain(
        kind=kind, seed=seed, mode=mode,
        ablate_revision=ablate_revision, use_distal=use_distal,
    )
    # Also snapshot io store structure by replaying training+probe lightly
    rng = random.Random(seed)
    io_before = io.empty_store()
    epa.train_mediated_predictions(io_before, n=30, seed=seed, mode=mode)
    snap_before = predictive_structure_snapshot(io_before)
    # After contact, prediction uses same store (structures unchanged by predict);
    # revision in 4.31 changes pc_store distal, not io_store tables.
    # Endogenous predictive transition for C1: io MATCH appears + predicted future present.
    # For C1 we also compare later-action distal values before/after revision in pc_store.
    return {
        "chain": chain,
        "io_structure_before": snap_before,
        "pred_before_status": chain["pred_before"].get("status"),
        "pred_after_status": chain["pred_after"].get("status"),
        "pred_after": chain["pred_after"].get("predicted"),
        "rel_shift": (
            chain["act_after"]["delta_P_B_minus_A"] - chain["act_before"]["delta_P_B_minus_A"]
        ),
        "delta_P_B": chain["delta_P_B"],
        "act_before": chain["act_before"],
        "act_after": chain["act_after"],
    }


def distal_consequence_from_action_dist(
    act: dict[str, Any],
    *,
    f_plus: dict[str, float] | None = None,
    f_minus: dict[str, float] | None = None,
) -> dict[str, float]:
    """Expected distal body under later action distribution (researcher)."""
    f_plus = f_plus or pci.B_PLUS()
    f_minus = f_minus or pci.B_MINUS()
    # WAIT / mid
    f_mid = {
        "energy_signal": 0.45,
        "hydration_signal": 0.70,
        "fatigue_signal": 0.25,
        "discomfort_signal": 0.08,
    }
    pa, pb, pw = act["P_A"], act["P_B"], act["P_WAIT"]
    keys = set(f_plus) | set(f_minus) | set(f_mid)
    return {
        k: pa * float(f_minus.get(k, 0.0)) + pb * float(f_plus.get(k, 0.0)) + pw * float(f_mid.get(k, 0.0))
        for k in keys
    }


def evaluate_expected_distal(body: dict[str, float], goals: dict[str, Any]) -> float:
    ev = ordinary_state_value(start=pci.S0(), terminal=body, goals=goals)
    return float(ev.get("ordinary_value") or 0.0)


def prospective_contact_evaluation(
    *,
    pc_store_full: dict[str, Any],
    pc_store_rev_off: dict[str, Any],
    goals: dict[str, Any],
) -> dict[str, Any]:
    """Phase 2/3: Can existing prospection treat learning-mediated future?

    Test A — composition of CONTACT_M physical one-step only (existing machinery):
      predict_one_step(CONTACT_M) / compose [CONTACT_M] — no revision node.

    Test B — researcher counterfactual: expected F under later-action dist from
      FULL vs REVISION-OFF stores (simulates learning-mediated branch externally).

    Test C — does present CONTACT_M logit differ if we *were* to blend those
      counterfactual distal values? (diagnostic only — not wired into cognition
      unless composition already produces them)

    C4 requires Test A (or native composition) to distinguish FULL vs REVISION-OFF.
    Injecting counterfactual F into logits would be a forbidden bridge.
    """
    # Native composition attempts
    one_full = pc.predict_one_step(pc_store_full, pci.S0(), epa.ACTION_CONTACT)
    one_off = pc.predict_one_step(pc_store_rev_off, pci.S0(), epa.ACTION_CONTACT)
    # Multi-step sequences that skip the predictive-state branch (invalid as learning-mediated)
    seq_b = [epa.ACTION_CONTACT, "B1", "B2", "B3"]
    seq_a = [epa.ACTION_CONTACT, "A1", "A2", "A3"]
    # May fail if CONTACT_M not linked into A/B antecedents
    comp_b_full = pc.distal_prediction(pc_store_full, start=pci.S0(), action_seq=seq_b)
    comp_b_off = pc.distal_prediction(pc_store_rev_off, start=pci.S0(), action_seq=seq_b)
    comp_a_full = pc.distal_prediction(pc_store_full, start=pci.S0(), action_seq=seq_a)
    comp_a_off = pc.distal_prediction(pc_store_rev_off, start=pci.S0(), action_seq=seq_a)

    # Native predicted distal for CONTACT_M alone
    native_full = one_full.get("predicted")
    native_off = one_off.get("predicted")
    native_differs = io.l1(native_full, native_off) > 1e-6 if (native_full and native_off) else False

    # Later-action distributions under the two stores (endogenous path exists downstream)
    act_full = epa.later_action_probe(pc_store_full, goals, seed=1)
    act_off = epa.later_action_probe(pc_store_rev_off, goals, seed=1)
    exp_full = distal_consequence_from_action_dist(act_full)
    exp_off = distal_consequence_from_action_dist(act_off)
    val_full = evaluate_expected_distal(exp_full, goals)
    val_off = evaluate_expected_distal(exp_off, goals)
    counterfactual_differs = abs(val_full - val_off) >= VALUE_TOL

    # Present CONTACT_M value under existing free-probe rule (immediate only)
    imm = dict(epa.MATCHED_IMM_COST)
    v_imm = float(ordinary_state_value(start=pci.S0(), terminal=imm, goals=goals).get("ordinary_value") or 0.0)
    # Same under FULL vs REVISION-OFF by construction
    present_value_full = v_imm
    present_value_off = v_imm
    present_differs = abs(present_value_full - present_value_off) >= VALUE_TOL

    return {
        "one_step_full": one_full,
        "one_step_off": one_off,
        "native_contact_predicted_differs": native_differs,
        "compose_CONTACT_B_full": {
            "status": comp_b_full.get("status"),
            "predicted": comp_b_full.get("predicted_distal"),
        },
        "compose_CONTACT_B_off": {
            "status": comp_b_off.get("status"),
            "predicted": comp_b_off.get("predicted_distal"),
        },
        "compose_CONTACT_A_full": {"status": comp_a_full.get("status")},
        "compose_CONTACT_A_off": {"status": comp_a_off.get("status")},
        "researcher_counterfactual": {
            "expected_F_full": exp_full,
            "expected_F_off": exp_off,
            "ordinary_value_full": val_full,
            "ordinary_value_off": val_off,
            "differs": counterfactual_differs,
            "note": "External simulation of learning-mediated branch; NOT native prospection",
        },
        "present_CONTACT_M_value_full": present_value_full,
        "present_CONTACT_M_value_off": present_value_off,
        "present_value_differs": present_differs,
        "prospective_represents_learning_mediated_future": False,  # set by caller from native tests
        "full_sequence_exposure_CONTACT_chain": int(
            (pc_store_full.get("full_sequence_patterns") or {}).get("S0_CONTACT_M_full", {}).get("count") or 0
        ),
    }


def prepare_stores_for_prospection(*, kind: str, seed: int) -> dict[str, Any]:
    """Build FULL (revision on) and REVISION-OFF pc stores after CONTACT_M evidence path.

    Also teach CONTACT_M one-step physical transition (matched immediate body).
    """
    goals = pci.default_goals()
    # FULL
    full = epa.forced_contact_chain(kind=kind, seed=seed, ablate_revision=False)
    # Need the actual pc stores — forced_contact_chain doesn't return them.
    # Rebuild explicitly:
    def _build(ablate_revision: bool) -> dict[str, Any]:
        rng = random.Random(seed)
        io_store = io.empty_store()
        epa.train_mediated_predictions(io_store, n=30, seed=seed)
        pc_store = build_matched_pc_prior()
        # Teach CONTACT_M one-step
        for i in range(20):
            pc.learn_transition(
                pc_store, tick=80000 + i,
                antecedent=pci.S0(), action=epa.ACTION_CONTACT,
                consequent=dict(epa.MATCHED_IMM_COST),
            )
        for i in range(20):
            pc.learn_transition(
                pc_store, tick=81000 + i,
                antecedent=pci.S0(), action=epa.ACTION_CONTROL,
                consequent=dict(epa.MATCHED_IMM_COST),
            )
        world = epa.empty_world(kind=kind, contact=False)
        world2 = epa.step_physical(world, epa.ACTION_CONTACT, rng=rng)
        sig = epa.accessible_signal(world2, rng=rng)
        pred = epa.predict_from_signal(io_store, sig)
        epa.revise_later_distal_from_prediction(
            pc_store, pred.get("predicted"),
            tick=60000, n=40, ablate_revision=ablate_revision,
        )
        pc.record_full_sequence_exposure(pc_store, pattern_id="S0_CONTACT_M_full", experienced=False)
        return {"io_store": io_store, "pc_store": pc_store, "pred": pred, "sig": sig}

    full_b = _build(False)
    off_b = _build(True)
    return {"full": full_b, "rev_off": off_b, "goals": goals, "forced_summary": full}


def present_action_probs(goals: dict[str, Any], *, seed: int = 0) -> dict[str, Any]:
    """Existing 4.31 free probe — immediate-only CONTACT_M evaluation."""
    return epa.free_action_probe(kind="B", seed=seed)


def why_431_autonomous_failed() -> dict[str, Any]:
    return {
        "code_path": "evidence_producing_action.free_action_probe",
        "mechanism": (
            "CONTACT_M and PUSH_X logits = ordinary_state_value(MATCHED_IMM_COST) only; "
            "no distal composition for CONTACT_M; pci.action_logits only attaches distal "
            "for A1/B1 sequences; no information-gain / revision-benefit term"
        ),
        "measured": "P_CONTACT_M == P_PUSH_X under matched immediate",
        "bottleneck": "future evidence/revision benefit -X-> present CONTACT_M value",
    }
