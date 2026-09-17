"""Update 4.31 - Evidence-producing physical action (no information seeking).

Reuses 4.25 WORLD->MEDIATOR->BODY transduction.
Forced chain: CONTACT_M -> observability -> evidence -> revision -> later action (4.26).
Autonomous CONTACT_M selection is tested separately; may NULL (like 4.25 C3).

No INFORMATION/CURIOSITY/UNCERTAINTY/EPISTEMIC_VALUE in cognition.
No variance/reliability in action logits (4.29 NULL preserved).
"""
from __future__ import annotations

import math
import random
from copy import deepcopy
from typing import Any

from mechanistic_mind.research import instrumental_observation as io
from mechanistic_mind.research import prospective_composition as pc
from mechanistic_mind.research import prospective_consequence_influence as pci
from mechanistic_mind.research.composed_future_value import ordinary_state_value

FORBIDDEN = (
    "INFORMATION", "INFORMATION_GAIN", "EXPECTED_INFORMATION_GAIN", "UNCERTAINTY",
    "CONFIDENCE", "DOUBT", "AMBIGUITY", "ENTROPY", "VARIANCE_AVERSION",
    "RELIABILITY_PREFERENCE", "CURIOSITY", "EXPLORATION", "INSPECT", "OBSERVE",
    "MEASURE", "CHECK", "QUERY", "INVESTIGATE", "RESOLVE", "DISAMBIGUATE",
    "KNOWLEDGE", "EPISTEMIC_VALUE", "EPISTEMIC_REWARD", "FUTURE_INFORMATION",
    "SENSOR_VALUE", "NEED_MORE_EVIDENCE", "HIDDEN_STATE", "CORRECT_STATE",
    "INFORMATIVE", "REVEAL", "MEDIATOR_USEFUL", "CORRECT_ACTION", "TOOL",
)

# Physical action name: contact with mediator object (not OBSERVE).
ACTION_CONTACT = "CONTACT_M"
ACTION_CONTROL = "PUSH_X"   # matched physical interaction, useless mediator path
ACTION_WAIT = "WAIT"
ACTION_LO = "A1"            # later consequence-sensitive choice
ACTION_HI = "B1"

MATCHED_IMM_COST = {
    "energy_signal": 0.42,
    "hydration_signal": 0.71,
    "fatigue_signal": 0.24,
    "discomfort_signal": 0.07,
}


def audit_forbidden(payload: Any) -> list[str]:
    return [t for t in FORBIDDEN if t in str(payload)]


def future_to_body(fut: dict[str, float] | None) -> dict[str, float] | None:
    """Map 4.25 future {e,f} into body-signal channels for ordinary_state_value."""
    if not fut:
        return None
    e = float(fut.get("e", 0.5))
    f = float(fut.get("f", 0.5))
    return {
        "energy_signal": e,
        "hydration_signal": 0.65 + 0.1 * e,
        "fatigue_signal": f,
        "discomfort_signal": 0.05 + 0.2 * f,
    }


def empty_world(
    *,
    kind: str = "A",
    contact: bool = False,
    mode: str = "useful",
    ablate_world_to_m: bool = False,
    ablate_m_to_body: bool = False,
) -> dict[str, Any]:
    """Researcher physics. kind is GT only — never cognition-visible as identity."""
    return {
        "w": io.world_state(kind),
        "kind_gt": kind,  # researcher-only
        "contact": bool(contact),
        "mode": mode,
        "ablate_world_to_m": bool(ablate_world_to_m),
        "ablate_m_to_body": bool(ablate_m_to_body),
        "m_state": {"m0": 0.5, "m1": 0.5},
        "tick_researcher": 0,
    }


def accessible_signal(world: dict[str, Any], *, rng=None) -> dict[str, float]:
    """Agent-accessible body/sensor only — no GT kind."""
    return io.mediated_observation(
        world["w"],
        mode=str(world.get("mode") or "useful"),
        ablate_world_to_m=bool(world.get("ablate_world_to_m")),
        ablate_m_to_body=bool(world.get("ablate_m_to_body")),
        contact=bool(world.get("contact")),
        rng=rng,
    )


def step_physical(world: dict[str, Any], action: str, *, rng=None) -> dict[str, Any]:
    """Ordinary physical step. CONTACT_M engages mediator; no REVEAL."""
    w = deepcopy(world)
    w["tick_researcher"] = int(w.get("tick_researcher") or 0) + 1
    if action == ACTION_CONTACT:
        w["contact"] = True
        w["m_state"] = io.transducer_response(
            w["w"],
            mode=str(w.get("mode") or "useful"),
            ablate_world_to_m=bool(w.get("ablate_world_to_m")),
            rng=rng,
        )
    elif action == ACTION_CONTROL:
        # Matched physical interaction with useless coupling (mode forced useless for this act)
        w["contact"] = True
        # Interact but use useless transducer surface for this control action's effect
        w["m_state"] = io.transducer_response(w["w"], mode="useless", rng=rng)
        # Do not enable useful mediated path
        w["mode"] = "useless"
    elif action == ACTION_WAIT:
        pass  # no intervention; mediator coupling unchanged
    return w


def train_mediated_predictions(
    store: dict[str, Any],
    *,
    n: int = 30,
    seed: int = 0,
    mode: str = "useful",
) -> dict[str, Any]:
    """Acquire obs->future via ordinary mediated contact experience (both kinds)."""
    rng = random.Random(seed)
    for i in range(n):
        for kind in ("A", "B"):
            ww = empty_world(kind=kind, contact=True, mode=mode)
            obs = accessible_signal(ww, rng=rng)
            fut = io.future_consequence(ww["w"], strength="large")
            io.learn_prediction(store, obs, fut)
            store["exposure"]["M_encounters"] = int(store["exposure"].get("M_encounters", 0)) + 1
            store["exposure"]["M_interactions"] = int(store["exposure"].get("M_interactions", 0)) + 1
            store["exposure"][f"mediated_{kind}"] = int(store["exposure"].get(f"mediated_{kind}", 0)) + 1
            store["exposure"][f"W_{kind}"] = int(store["exposure"].get(f"W_{kind}", 0)) + 1
    # Never count full end-to-end as experienced in free composition sense
    store["exposure"]["full_mediated_sequence"] = 0
    return {"n_per_kind": n, "full_mediated_sequence": 0}


def train_later_action_composition(pc_store: dict[str, Any], *, n: int = 40) -> None:
    """Independent A/B distal chains initially matched (neutral distal).

    Evidence-driven revision later differentiates A3/B3 terminals.
    """
    mid = {
        "energy_signal": 0.45,
        "hydration_signal": 0.70,
        "fatigue_signal": 0.25,
        "discomfort_signal": 0.08,
    }
    for i in range(n):
        t = i + 1
        pc.learn_transition(pc_store, tick=t, antecedent=pci.S0(), action="A1", consequent=pci.S1())
        pc.learn_transition(pc_store, tick=t, antecedent=pci.S1(), action="A2", consequent=pci.S2())
        pc.learn_transition(pc_store, tick=t, antecedent=pci.S2(), action="A3", consequent=mid)
        pc.learn_transition(pc_store, tick=t, antecedent=pci.S0(), action="B1", consequent=pci.S3())
        pc.learn_transition(pc_store, tick=t, antecedent=pci.S3(), action="B2", consequent=pci.S4())
        pc.learn_transition(pc_store, tick=t, antecedent=pci.S4(), action="B3", consequent=dict(mid))
        pc.learn_transition(pc_store, tick=t, antecedent=pci.S0(), action="WAIT",
                            consequent=pci.immediate_consequence("WAIT"))
    pc.record_full_sequence_exposure(pc_store, pattern_id="S0_A1_A2_A3", experienced=False)
    pc.record_full_sequence_exposure(pc_store, pattern_id="S0_B1_B2_B3", experienced=False)


def revise_later_distal_from_prediction(
    pc_store: dict[str, Any],
    predicted_future: dict[str, float] | None,
    *,
    tick: int = 50000,
    n: int = 40,
    ablate_revision: bool = False,
) -> None:
    """Ordinary learn: if predicted body future is high-energy regime, reinforce B3->PLUS; else A-favoring.

    No WORLD_CHANGED. Uses predicted physical future fragment only.
    """
    if ablate_revision or not predicted_future:
        return
    body = future_to_body(predicted_future)
    if not body:
        return
    # High e => favor B distal PLUS; low e => keep/push B toward MINUS and A already MINUS
    e = float(predicted_future.get("e", 0.5))
    for i in range(n):
        t = tick + i
        if e >= 0.55:
            pc.learn_transition(pc_store, tick=t, antecedent=pci.S4(), action="B3", consequent=pci.B_PLUS())
            pc.learn_transition(pc_store, tick=t, antecedent=pci.S2(), action="A3", consequent=pci.B_MINUS())
        else:
            pc.learn_transition(pc_store, tick=t, antecedent=pci.S4(), action="B3", consequent=pci.B_MINUS())
            pc.learn_transition(pc_store, tick=t, antecedent=pci.S2(), action="A3", consequent=pci.B_PLUS())


def later_action_probe(pc_store: dict[str, Any], goals: dict[str, Any], *, seed: int, use_distal: bool = True) -> dict[str, Any]:
    logits = pci.action_logits(store=pc_store, goals=goals, use_distal=use_distal)
    probs = logits.get("probs") or {}
    return {
        "probs": probs,
        "P_A": float(probs.get("A1", 0.0)),
        "P_B": float(probs.get("B1", 0.0)),
        "P_WAIT": float(probs.get("WAIT", 0.0)),
        "delta_P_B_minus_A": float(probs.get("B1", 0.0)) - float(probs.get("A1", 0.0)),
        "distal_values": {a: (logits.get("actions") or {}).get(a, {}).get("distal_value") for a in probs},
        "use_distal": use_distal,
    }


def predict_from_signal(io_store: dict[str, Any], signal: dict[str, float]) -> dict[str, Any]:
    return io.predict(io_store, signal)


def discriminability(kind_signals: dict[str, list[dict[str, float]]]) -> float:
    a = kind_signals.get("A") or []
    b = kind_signals.get("B") or []
    return io.mean_l1_pairs(a, b)


def forced_contact_chain(
    *,
    kind: str,
    seed: int,
    mode: str = "useful",
    ablate_world_to_m: bool = False,
    ablate_m_to_body: bool = False,
    ablate_revision: bool = False,
    use_distal: bool = True,
) -> dict[str, Any]:
    """QUESTION A: externally force CONTACT_M; measure observability→revision→later action."""
    rng = random.Random(seed)
    goals = pci.default_goals()
    io_store = io.empty_store()
    train_mediated_predictions(io_store, n=30, seed=seed, mode=mode)
    pc_store = pc.empty_store()
    train_later_action_composition(pc_store, n=40)

    world = empty_world(
        kind=kind, contact=False, mode=mode,
        ablate_world_to_m=ablate_world_to_m, ablate_m_to_body=ablate_m_to_body,
    )
    sig_before = accessible_signal(world, rng=rng)
    pred_before = predict_from_signal(io_store, sig_before)
    # Baseline later action before evidence
    act_before = later_action_probe(pc_store, goals, seed=seed, use_distal=use_distal)

    # Force CONTACT_M
    world2 = step_physical(world, ACTION_CONTACT, rng=rng)
    sig_after = accessible_signal(world2, rng=rng)
    pred_after = predict_from_signal(io_store, sig_after)

    # Revision into later distal composition
    revise_later_distal_from_prediction(
        pc_store, pred_after.get("predicted"),
        tick=60000, n=40, ablate_revision=ablate_revision,
    )
    act_after = later_action_probe(pc_store, goals, seed=seed + 1, use_distal=use_distal)

    # Observability audit samples
    samples = {"A": [], "B": []}
    for k in ("A", "B"):
        for _ in range(20):
            ww = empty_world(kind=k, contact=False, mode=mode,
                             ablate_world_to_m=ablate_world_to_m, ablate_m_to_body=ablate_m_to_body)
            samples[k].append(accessible_signal(ww, rng=rng))
    d_direct = discriminability(samples)
    samples_m = {"A": [], "B": []}
    for k in ("A", "B"):
        for _ in range(20):
            ww = empty_world(kind=k, contact=True, mode=mode,
                             ablate_world_to_m=ablate_world_to_m, ablate_m_to_body=ablate_m_to_body)
            samples_m[k].append(accessible_signal(ww, rng=rng))
    d_med = discriminability(samples_m)

    return {
        "kind_gt": kind,
        "mode": mode,
        "signal_before": sig_before,
        "signal_after": sig_after,
        "signal_changed": io.l1(sig_before, sig_after) > 1e-6,
        "mediator_after": world2.get("m_state"),
        "contact_after": world2.get("contact"),
        "pred_before": pred_before,
        "pred_after": pred_after,
        "prediction_revised": (
            pred_before.get("predicted") != pred_after.get("predicted")
            and pred_after.get("status") == "MATCH"
        ),
        "pred_l1_change": io.l1(pred_before.get("predicted"), pred_after.get("predicted")),
        "act_before": act_before,
        "act_after": act_after,
        "delta_P_B": act_after["P_B"] - act_before["P_B"],
        "delta_P_A": act_after["P_A"] - act_before["P_A"],
        "direct_discriminability": d_direct,
        "mediated_discriminability": d_med,
        "full_mediated_sequence_exposure": int(io_store["exposure"].get("full_mediated_sequence", 0)),
        "ablations": {
            "world_to_m": ablate_world_to_m,
            "m_to_body": ablate_m_to_body,
            "revision": ablate_revision,
            "use_distal": use_distal,
        },
    }


def free_action_probe(
    *,
    kind: str,
    seed: int,
    n_samples: int = 400,
    mode: str = "useful",
) -> dict[str, Any]:
    """QUESTION B: free selection among CONTACT_M / PUSH_X / WAIT with matched immediate costs.

    Logits use only immediate ordinary_state_value of matched body consequences —
    no information-gain term. Distal benefit of evidence is NOT composed into CONTACT_M
    (architecture limitation expected → C6/C7 may NULL).
    """
    goals = pci.default_goals()
    # Immediate consequences matched for CONTACT_M and PUSH_X
    actions = [ACTION_CONTACT, ACTION_CONTROL, ACTION_WAIT]
    rows = {}
    for a in actions:
        if a == ACTION_WAIT:
            imm = pci.immediate_consequence("WAIT")
        else:
            imm = dict(MATCHED_IMM_COST)
        ev = ordinary_state_value(start=pci.S0(), terminal=imm, goals=goals)
        rows[a] = {"immediate_value": float(ev.get("ordinary_value") or 0.0), "logit": float(ev.get("ordinary_value") or 0.0)}
    # softmax
    T = pci.DEFAULT_TEMPERATURE
    xs = [rows[a]["logit"] / max(1e-6, T) for a in actions]
    m = max(xs)
    exps = [math.exp(x - m) for x in xs]
    z = sum(exps) or 1.0
    probs = {a: exps[i] / z for i, a in enumerate(actions)}
    # empirical
    rng = random.Random(seed)
    counts = {a: 0 for a in actions}
    acts = list(actions)
    weights = [probs[a] for a in acts]
    for _ in range(n_samples):
        u = rng.random()
        cum = 0.0
        chosen = acts[-1]
        for a, w in zip(acts, weights):
            cum += w
            if u <= cum:
                chosen = a
                break
        counts[chosen] += 1
    empir = {a: counts[a] / n_samples for a in acts}
    return {
        "kind_gt": kind,
        "probs": probs,
        "empirical": empir,
        "P_CONTACT_M": float(probs.get(ACTION_CONTACT, 0.0)),
        "P_PUSH_X": float(probs.get(ACTION_CONTROL, 0.0)),
        "P_WAIT": float(probs.get(ACTION_WAIT, 0.0)),
        "matched_immediate": True,
        "information_term_in_logits": False,
        "note": "CONTACT_M has no distal evidence-value in logits; only matched immediate cost",
    }


def compose_contact_trajectory_audit(pc_store: dict[str, Any]) -> dict[str, Any]:
    """Try compose CONTACT_M → ... without teaching full sequence (expect limited)."""
    # Learn fragments only: S0--CONTACT_M--> mid contact state; mid --WAIT--> signal-like
    # Not a full epistemic chain representation.
    for i in range(15):
        pc.learn_transition(
            pc_store, tick=90000 + i,
            antecedent=pci.S0(), action=ACTION_CONTACT,
            consequent=MATCHED_IMM_COST,
        )
    pc.record_full_sequence_exposure(pc_store, pattern_id="S0_CONTACT_M_full", experienced=False)
    one = pc.predict_one_step(pc_store, pci.S0(), ACTION_CONTACT)
    return {
        "one_step_status": one.get("status"),
        "full_sequence_exposure_count": int(
            (pc_store.get("full_sequence_patterns") or {}).get("S0_CONTACT_M_full", {}).get("count") or 0
        ),
        "note": "No composed evidence→revision→later-action value for CONTACT_M in logits",
    }
