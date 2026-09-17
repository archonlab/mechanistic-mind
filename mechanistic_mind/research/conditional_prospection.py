"""Update 4.33 - Acquired conditional prospection (no planner / no info-gain).

Tests whether ordinary acquired predictive structures can support:
  S0 --A0--> future physical state in {Ox-like, Oy-like}
               then state-dependent later action -> distal consequence

without symbolic BRANCH/PLAN objects and without learning-mediated self-change.

Architectural priors (verified in prospective_composition / pci):
  - learn_transition aggregates consequents for (antecedent, action) into ONE mean
  - distal_prediction / compose_trajectories require fixed action sequences
  - action_logits attaches distal only along fixed A1/B1 chains
"""
from __future__ import annotations

import math
import random
from copy import deepcopy
from typing import Any

from mechanistic_mind.research import prospective_composition as pc
from mechanistic_mind.research import prospective_consequence_influence as pci
from mechanistic_mind.research.composed_future_value import ordinary_state_value

FORBIDDEN = (
    "BRANCH", "BRANCH_ID", "CONDITION", "CONDITIONAL", "IF_STATE", "POLICY",
    "POLICY_TREE", "PLAN", "PLAN_TREE", "CONTINGENCY", "FUTURE_CASE", "OPTION",
    "CHOICE_POINT", "DECISION_NODE", "CORRECT_ACTION", "BEST_ACTION", "OPTIMAL_ACTION",
    "EXPECTED_VALUE", "INFORMATION", "INFORMATION_GAIN", "UNCERTAINTY", "NOVELTY",
    "CURIOSITY", "EXPLORATION", "EXPECTED_BRANCH", "BRANCH_UTILITY", "CONTINGENCY_VALUE",
)

ACTION_DELTA = 0.03
VALUE_TOL = 0.02
DEFAULT_TEMP = 1.25


def audit_forbidden(payload: Any) -> list[str]:
    return [t for t in FORBIDDEN if t in str(payload)]


def architecture_limitation() -> dict[str, Any]:
    return {
        "fixed_sequence": (
            "pc.distal_prediction(store, start, action_seq) and compose_trajectories "
            "expand a pre-specified action list / branch_actions; they do not select "
            "later actions via ordinary_state_value on predicted future fragments."
        ),
        "mean_collapse": (
            "pc.learn_transition keys by (quantized_antecedent, action) and stores "
            "one mean consequent; A0->Ox and A0->Oy from the same S0 collapse."
        ),
        "relation_to_432": (
            "4.32 C4 NULL: composition could chain CONTACT_M + pre-specified A/B "
            "but could not represent revision-gated A-vs-B. 4.33 removes learning "
            "mediation and tests the more primitive physical contingent future."
        ),
        "compose_trajectories_note": (
            "branch_actions enumerates candidate next actions but does not gate "
            "them on predicted observation identity via acquired valuation."
        ),
    }


def S0() -> dict[str, float]:
    s = dict(pci.S0())
    s["field_1"] = 0.50
    s["field_2"] = 0.50
    s["resistance"] = 0.40
    return s


def Ox() -> dict[str, float]:
    """Researcher label Ox only — agent sees generic fields."""
    return {
        "energy_signal": 0.46,
        "hydration_signal": 0.71,
        "fatigue_signal": 0.21,
        "discomfort_signal": 0.05,
        "field_1": 0.90,
        "field_2": 0.10,
        "resistance": 0.25,
    }


def Oy() -> dict[str, float]:
    return {
        "energy_signal": 0.44,
        "hydration_signal": 0.70,
        "fatigue_signal": 0.22,
        "discomfort_signal": 0.06,
        "field_1": 0.10,
        "field_2": 0.90,
        "resistance": 0.75,
    }


def blind_obs() -> dict[str, float]:
    """Non-discriminating observation (hidden-state ablation)."""
    return {
        "energy_signal": 0.45,
        "hydration_signal": 0.705,
        "fatigue_signal": 0.215,
        "discomfort_signal": 0.055,
        "field_1": 0.50,
        "field_2": 0.50,
        "resistance": 0.50,
    }


def F_plus() -> dict[str, float]:
    f = dict(pci.B_PLUS())
    f["field_1"] = 0.55
    f["field_2"] = 0.55
    f["resistance"] = 0.35
    return f


def F_minus() -> dict[str, float]:
    f = dict(pci.B_MINUS())
    f["field_1"] = 0.45
    f["field_2"] = 0.45
    f["resistance"] = 0.55
    return f


def control_out() -> dict[str, float]:
    return {
        "energy_signal": 0.45,
        "hydration_signal": 0.70,
        "fatigue_signal": 0.25,
        "discomfort_signal": 0.08,
        "field_1": 0.50,
        "field_2": 0.50,
        "resistance": 0.40,
    }


def later_action_distribution(
    store: dict[str, Any],
    present: dict[str, float],
    goals: dict[str, Any],
    *,
    actions: tuple[str, ...] = ("A", "B"),
    temperature: float = DEFAULT_TEMP,
    use_prediction: bool = True,
) -> dict[str, Any]:
    """Select later actions from an actual/predicted present fragment.

    One-step predict_one_step -> ordinary_state_value -> softmax.
    No fixed multi-step sequence. No researcher-chosen action.
    """
    rows: dict[str, Any] = {}
    for a in actions:
        if use_prediction:
            step = pc.predict_one_step(store, present, a)
        else:
            step = {"status": "NO_MATCH"}
        if step.get("status") == "MATCH" and step.get("predicted") is not None:
            ev = ordinary_state_value(start=present, terminal=step["predicted"], goals=goals)
            val = float(ev.get("ordinary_value") or 0.0)
            pred = step["predicted"]
            status = "MATCH"
        else:
            val = 0.0
            pred = None
            status = "NO_MATCH"
        rows[a] = {"ordinary_value": val, "predicted": pred, "status": status, "logit": val}
    xs = [rows[a]["logit"] / max(1e-6, temperature) for a in actions]
    m = max(xs) if xs else 0.0
    exps = [math.exp(x - m) for x in xs]
    z = sum(exps) or 1.0
    probs = {a: exps[i] / z for i, a in enumerate(actions)}
    pref = max(actions, key=lambda a: probs[a]) if actions else None
    return {
        "probs": probs,
        "rows": rows,
        "preferred": pref,
        "P_A": float(probs.get("A", 0.0)),
        "P_B": float(probs.get("B", 0.0)),
        "leak_tokens": audit_forbidden(rows),
    }


def _cons_map(mode: str, reverse: bool) -> dict[tuple[str, str], dict[str, float]]:
    """Map (state_tag, action) -> consequent. state_tag researcher-only."""
    if reverse:
        return {
            ("x", "A"): F_minus(),
            ("x", "B"): F_plus(),
            ("y", "A"): F_plus(),
            ("y", "B"): F_minus(),
        }
    return {
        ("x", "A"): F_plus(),
        ("x", "B"): F_minus(),
        ("y", "A"): F_minus(),
        ("y", "B"): F_plus(),
    }


def acquire(
    *,
    seed: int,
    n_later: int = 48,
    n_a0: int = 48,
    mode: str = "full",
    reverse: bool = False,
    shuffle: bool = False,
    single_branch: bool = False,
    unstructured: bool = False,
    hide_state: bool = False,
    ablate_composition: bool = False,
    teach_fixed_seq: bool = True,
) -> dict[str, Any]:
    """Acquire relations via ordinary pc.learn_transition only."""
    rng = random.Random(seed)
    store = pc.empty_store()
    store["ablate_composition"] = bool(ablate_composition)
    tick = 1
    cmap = _cons_map(mode, reverse)
    pairs = [("x", "A"), ("x", "B"), ("y", "A"), ("y", "B")]
    consequents = [cmap[p] for p in pairs]
    if shuffle:
        shuffled = list(consequents)
        rng.shuffle(shuffled)
        cmap = {pairs[i]: shuffled[i] for i in range(4)}
    if unstructured:
        # decorrelate: random F+/F- independent of state×action
        for p in pairs:
            cmap[p] = F_plus() if rng.random() < 0.5 else F_minus()

    ox_ant = blind_obs() if hide_state else Ox()
    oy_ant = blind_obs() if hide_state else Oy()
    ants = {"x": ox_ant, "y": oy_ant}

    # Later action-consequence acquisition
    for _ in range(n_later):
        for tag, act in pairs:
            pc.learn_transition(
                store, tick=tick, antecedent=ants[tag], action=act, consequent=cmap[(tag, act)]
            )
            tick += 1

    # A0 -> future physical states
    full_contingent = 0
    n_ox = n_a0 // 2
    n_oy = n_a0 - n_ox
    if single_branch:
        n_ox, n_oy = n_a0, 0
    for _ in range(n_ox):
        pc.learn_transition(store, tick=tick, antecedent=S0(), action="A0", consequent=Ox())
        tick += 1
    for _ in range(n_oy):
        pc.learn_transition(store, tick=tick, antecedent=S0(), action="A0", consequent=Oy())
        tick += 1

    # CONTROL immediate
    for _ in range(max(12, n_a0 // 4)):
        pc.learn_transition(store, tick=tick, antecedent=S0(), action="CONTROL", consequent=control_out())
        tick += 1

    # Optional fixed-sequence positive-control fragments (A0->Ox->A and A0->Oy->B chains)
    # Taught as separate edges already; record full-seq exposure = 0 for novel composition.
    if teach_fixed_seq:
        # also teach intermediate continuity for distal_prediction([A0, A]) style:
        # after Ox, A already taught; after predicting mean of A0 we may not reach Ox.
        pass

    meta = {
        "seed": seed,
        "mode": mode,
        "reverse": reverse,
        "shuffle": shuffle,
        "single_branch": single_branch,
        "unstructured": unstructured,
        "hide_state": hide_state,
        "n_later": n_later,
        "n_a0": n_a0,
        "n_a0_ox": n_ox,
        "n_a0_oy": n_oy,
        "full_contingent_trajectory_exposure_count": full_contingent,
        "ticks": tick,
    }
    return {"store": store, "meta": meta, "cmap_tags": {f"{a}_{b}": True for a, b in pairs}}


def reactive_probe(store: dict[str, Any], goals: dict[str, Any]) -> dict[str, Any]:
    dx = later_action_distribution(store, Ox(), goals)
    dy = later_action_distribution(store, Oy(), goals)
    ok = (
        dx["P_A"] - dx["P_B"] >= ACTION_DELTA
        and dy["P_B"] - dy["P_A"] >= ACTION_DELTA
    )
    return {
        "Ox": {"P_A": dx["P_A"], "P_B": dx["P_B"], "preferred": dx["preferred"]},
        "Oy": {"P_A": dy["P_A"], "P_B": dy["P_B"], "preferred": dy["preferred"]},
        "conditional_reactive": bool(ok),
        "leak_tokens": audit_forbidden({"x": dx, "y": dy}),
    }


def a0_continuations(store: dict[str, Any]) -> dict[str, Any]:
    """Native A0 prediction from S0 — expect mean collapse (one continuation)."""
    step = pc.predict_one_step(store, S0(), "A0")
    pred = step.get("predicted")
    key = pc.transition_key(pc._q(S0()), "A0")
    row = (store.get("transitions") or {}).get(key)
    # Distance of mean to Ox / Oy
    d_ox = pc._frag_distance(pc._q(pred or {}), pc._q(Ox())) if pred else None
    d_oy = pc._frag_distance(pc._q(pred or {}), pc._q(Oy())) if pred else None
    # Discrete native continuations retained by predict_one_step: always 0 or 1
    native_discrete = 1 if step.get("status") == "MATCH" else 0
    # Researcher: evidence log may show both consequents historically
    elog = store.get("exposure_log") or []
    seen_ox = seen_oy = 0
    for e in elog:
        if e.get("action") != "A0":
            continue
        cons = e.get("cons") or {}
        if pc._frag_distance(cons, pc._q(Ox())) < 0.15:
            seen_ox += 1
        if pc._frag_distance(cons, pc._q(Oy())) < 0.15:
            seen_oy += 1
    var_sum = (row or {}).get("var_sum") or {}
    return {
        "status": step.get("status"),
        "predicted_mean": pred,
        "support": None if row is None else int(row.get("support") or 0),
        "native_discrete_continuation_count": native_discrete,
        "retains_both_Ox_and_Oy_as_discrete": False,
        "distance_mean_to_Ox": d_ox,
        "distance_mean_to_Oy": d_oy,
        "researcher_evidence_ox_count": seen_ox,
        "researcher_evidence_oy_count": seen_oy,
        "researcher_evidence_shows_both": bool(seen_ox > 0 and seen_oy > 0),
        "var_sum": var_sum,
        "mean_collapse": True,
    }


def continuation_specific_from_fragments(
    store: dict[str, Any], goals: dict[str, Any]
) -> dict[str, Any]:
    """Apply agent later-action machinery to Ox and Oy fragments (not researcher picks)."""
    dx = later_action_distribution(store, Ox(), goals)
    dy = later_action_distribution(store, Oy(), goals)
    return {
        "from_Ox_preferred": dx["preferred"],
        "from_Oy_preferred": dy["preferred"],
        "Ox_probs": dx["probs"],
        "Oy_probs": dy["probs"],
        "agent_prefers_A_on_Ox_and_B_on_Oy": bool(
            dx["preferred"] == "A" and dy["preferred"] == "B"
            and dx["P_A"] - dx["P_B"] >= ACTION_DELTA
            and dy["P_B"] - dy["P_A"] >= ACTION_DELTA
        ),
    }


def fixed_sequence_controls(store: dict[str, Any]) -> dict[str, Any]:
    """4.23-style fixed sequences: A0 then A; A0 then B."""
    # Teach bridging: need Ox as intermediate for [A0,A] only if mean is Ox-like.
    # For positive control under single_branch or after forcing learn S0-A0-Ox and Ox-A-F+
    r_a = pc.distal_prediction(store, start=S0(), action_seq=["A0", "A"])
    r_b = pc.distal_prediction(store, start=S0(), action_seq=["A0", "B"])
    # Also compose from Ox / Oy with fixed later action (known working pattern)
    r_ox_a = pc.distal_prediction(store, start=Ox(), action_seq=["A"])
    r_oy_b = pc.distal_prediction(store, start=Oy(), action_seq=["B"])
    composed = pc.compose_trajectories(
        store, start=S0(), actions_horizon=["A0", "A"], max_depth=2, branch_actions=["A0", "A", "B", "CONTROL"]
    )
    return {
        "distal_A0_A": {"status": r_a.get("status"), "depth": r_a.get("depth"), "predicted": r_a.get("predicted_distal")},
        "distal_A0_B": {"status": r_b.get("status"), "depth": r_b.get("depth"), "predicted": r_b.get("predicted_distal")},
        "distal_Ox_A": {"status": r_ox_a.get("status"), "predicted": r_ox_a.get("predicted_distal")},
        "distal_Oy_B": {"status": r_oy_b.get("status"), "predicted": r_oy_b.get("predicted_distal")},
        "fixed_seq_Ox_A_works": r_ox_a.get("status") in ("MATCH", "COMPOSED"),
        "fixed_seq_Oy_B_works": r_oy_b.get("status") in ("MATCH", "COMPOSED"),
        "compose_n_continuations": len(composed.get("continuations") or []),
        "compose_max_depth": composed.get("max_depth_reached"),
        "compose_expansions": composed.get("expansion_count"),
    }


def conditional_prospection_probe(store: dict[str, Any], goals: dict[str, Any]) -> dict[str, Any]:
    """Does native machinery from S0+A0 yield contingent later actions?

    Native path: predict A0 -> single mean M -> later_action_distribution(M).
    That cannot produce two different later actions for Ox vs Oy.
    Researcher path (NOT C4): separately evaluate Ox and Oy.
    """
    cont = a0_continuations(store)
    mean = cont.get("predicted_mean")
    from_mean = None
    if mean is not None:
        from_mean = later_action_distribution(store, mean, goals)
    agent_on_truth = continuation_specific_from_fragments(store, goals)
    # Unified contingent representation? Native APIs never return a pair of
    # (continuation, later_action) without a fixed action_seq.
    native_unified = False
    return {
        "native_discrete_continuations": cont["native_discrete_continuation_count"],
        "retains_both": cont["retains_both_Ox_and_Oy_as_discrete"],
        "later_action_from_A0_mean": None if from_mean is None else {
            "P_A": from_mean["P_A"], "P_B": from_mean["P_B"], "preferred": from_mean["preferred"]
        },
        "researcher_truth_fragments_agent_prefs": agent_on_truth,
        "native_unified_contingent_structure": native_unified,
        "note": (
            "Fixed-sequence distal_prediction(A0,A) vs (A0,B) are separate researcher queries, "
            "not continuation-dependent action selection."
        ),
    }


def present_a0_evaluation(
    store: dict[str, Any],
    goals: dict[str, Any],
    *,
    use_prediction: bool = True,
) -> dict[str, Any]:
    """Present A0 vs CONTROL using only available one-step / fixed-seq machinery.

    No expected_branch_value. Distal for A0 is predict_one_step mean only
    (or fixed seq if MATCH) — cannot integrate Ox->A and Oy->B.
    """
    actions = ("A0", "CONTROL")
    rows: dict[str, Any] = {}
    for a in actions:
        step = pc.predict_one_step(store, S0(), a) if use_prediction else {"status": "NO_MATCH"}
        if step.get("status") == "MATCH" and step.get("predicted") is not None:
            ev = ordinary_state_value(start=S0(), terminal=step["predicted"], goals=goals)
            val = float(ev.get("ordinary_value") or 0.0)
        else:
            val = 0.0
        # Optional fixed-seq distal (researcher may attach) — still fixed, not contingent
        fixed = None
        if a == "A0" and use_prediction:
            # try A0->A and A0->B fixed; do not blend as EV planning — record only
            fa = pc.distal_prediction(store, start=S0(), action_seq=["A0", "A"])
            fb = pc.distal_prediction(store, start=S0(), action_seq=["A0", "B"])
            fixed = {"A0_A": fa.get("status"), "A0_B": fb.get("status")}
        rows[a] = {"ordinary_value": val, "logit": val, "fixed_seq_status": fixed}
    xs = [rows[a]["logit"] / DEFAULT_TEMP for a in actions]
    m = max(xs)
    exps = [math.exp(x - m) for x in xs]
    z = sum(exps) or 1.0
    probs = {a: exps[i] / z for i, a in enumerate(actions)}
    return {"probs": probs, "rows": rows, "P_A0": probs["A0"], "P_CONTROL": probs["CONTROL"]}


def boundedness_probe(store: dict[str, Any]) -> dict[str, Any]:
    c = pc.compose_trajectories(
        store, start=S0(), max_depth=pc.MAX_DEPTH,
        branch_actions=["A0", "A", "B", "CONTROL"],
    )
    return {
        "MAX_DEPTH": pc.MAX_DEPTH,
        "MAX_BRANCH": pc.MAX_BRANCH,
        "MAX_WORKSPACE": pc.MAX_WORKSPACE,
        "MAX_EXPANSIONS": pc.MAX_EXPANSIONS,
        "expansion_count": c.get("expansion_count"),
        "workspace_peak": c.get("workspace_peak"),
        "n_continuations_returned": len(c.get("continuations") or []),
        "max_depth_reached": c.get("max_depth_reached"),
    }


def linear_vs_conditional_diagnostic(
    *,
    c1: bool,
    c2: bool,
    c3: bool,
    fixed_seq_ok: bool,
) -> dict[str, Any]:
    if c3 and c2:
        kind = "C"
        text = (
            "genuine acquired continuation-dependent future action in prospective structure"
        )
    elif c2 and not c3:
        kind = "B"
        text = (
            "multiple possible physical continuations retained, but no "
            "continuation-dependent action in prospection"
        )
    else:
        kind = "A"
        text = (
            "primarily fixed action sequences; discrete multi-continuation from one "
            "action not retained (mean collapse); reactive state-dependent action "
            f"{'works' if c1 else 'does not work'}; fixed-seq composition "
            f"{'works' if fixed_seq_ok else 'fails'}"
        )
    return {"class": kind, "description": text}
