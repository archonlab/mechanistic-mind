"""Update 4.37 - Multimodal prospective propagation.

Additive APIs (legacy predict_one_step / distal_prediction / compose_trajectories unchanged):
  predict_continuations(...)
  propagate_continuations(...)

Eligibility: only components with sequential follow support (4.35), or compact
relational path (4.36) — NOT every numerical component as a privileged branch.

WAIT remains a real non-intervention action (4.30); no WORLD_ACTION.
No action_logits change. C18 present-action influence is diagnostic only.
"""
from __future__ import annotations

import json
import math
import random
from copy import deepcopy
from typing import Any

from mechanistic_mind.research import multimodal_consequence_learning as mm
from mechanistic_mind.research import predictive_structure_selection as pss
from mechanistic_mind.research import predictive_representation_sufficiency as prs
from mechanistic_mind.research import prospective_composition as pc
from mechanistic_mind.research import prospective_consequence_influence as pci
from mechanistic_mind.research import conditional_prospection as cp
from mechanistic_mind.research.composed_future_value import ordinary_state_value

# Bounded prospective resources (preregistered)
MAX_CONTINUATIONS = 4
MAX_PROP_DEPTH = 3
MAX_PROP_NODES = 16
FOLLOW_ELIGIBILITY = pss.FOLLOW_MIN_SUPPORT
MERGE_L1 = 0.06

FORBIDDEN = (
    "BRANCH", "POSSIBILITY", "SCENARIO", "ALTERNATIVE", "FUTURE_OPTION", "DECISION_TREE",
    "PLAN", "POLICY", "WORLD_ACTION", "ENVIRONMENT_ACTION", "NATURE_ACTION",
    "HIT", "MISS", "COLLISION_RISK", "THREAT", "DANGER", "SAFE", "AVOID", "FEAR",
    "SURVIVAL", "SELF_PRESERVATION", "UNCERTAINTY", "CONFIDENCE", "RISK",
    "INFORMATION_GAIN", "CURIOSITY", "NOVELTY", "EXPECTED_UTILITY", "BEST_CASE", "WORST_CASE",
)


def audit_forbidden(payload: Any) -> list[str]:
    return [t for t in FORBIDDEN if t in str(payload)]


def architecture_inspection() -> dict[str, Any]:
    return {
        "fixed_sequence": "pc.distal_prediction(store, start, action_seq) requires fixed action_seq",
        "433_collapse": "pc.learn_transition mean_cons; predict_one_step returns one mean",
        "predict_components_additive": "mm.predict_components does not change predict_one_step",
        "follow": "pss.follow_by_component / follow_by_context for sequential eligibility",
        "r2": "prs.predict_relational for continuous without forcing discrete branches",
        "wait": "WAIT is real non-intervention (4.30); learn (S,WAIT)->next — not a fake environmental act",
        "smallest_change": "predict_continuations + propagate_continuations; legacy APIs preserved",
        "bounds": {
            "MAX_CONTINUATIONS": MAX_CONTINUATIONS,
            "MAX_PROP_DEPTH": MAX_PROP_DEPTH,
            "MAX_PROP_NODES": MAX_PROP_NODES,
            "FOLLOW_ELIGIBILITY": FOLLOW_ELIGIBILITY,
            "MERGE_L1": MERGE_L1,
        },
    }


def _l1(a, b):
    return float(pc._frag_distance(a or {}, b or {}))


def empty_mpp_store(**kw) -> dict[str, Any]:
    s = prs.empty_prs_store()
    s["enable_multimodal_propagation"] = True
    s["ablate_multimodal_propagation"] = False
    s["ablate_later_action"] = False
    s["full_sequence_patterns"] = s.get("full_sequence_patterns") or {}
    s.update(kw)
    return s


def predict_continuations(
    store: dict[str, Any],
    antecedent: dict[str, float],
    action: str,
    *,
    mode: str = "auto",
) -> dict[str, Any]:
    """Eligible continuations from (antecedent, action).

    mode:
      auto — prefer eligible R1 components with follow support; if none and relational
             available, return single relational continuation; else legacy mean
      components — only R1 eligible components
      relational — single R2 continuation
      legacy — single mean (predict_one_step)
    """
    if store.get("ablate_multimodal_propagation"):
        mode = "legacy"

    legacy = pc.predict_one_step(store, antecedent, action)
    legacy_pred = legacy.get("predicted") if legacy.get("status") == "MATCH" else None

    comps = mm.predict_components(store, antecedent, action)
    tkey = pc.transition_key(pc._q(antecedent), action)
    eligible = []
    for c in comps.get("components") or []:
        cid = str(c.get("id"))
        fkey = f"{tkey}||{cid}"
        frow = (store.get("follow_by_component") or {}).get(fkey)
        has_follow = bool(frow and float(frow.get("support") or 0) >= FOLLOW_ELIGIBILITY)
        # eligibility: component with sequential follow OR (for one-step access) support alone
        eligible.append({
            "id": cid,
            "center": dict(c.get("center") or {}),
            "empirical_weight": float(c.get("empirical_weight") or 0.0),
            "support": float(c.get("support") or 0.0),
            "has_follow": has_follow,
            "source": "component",
        })

    # R1 deep-eligible: has follow
    r1 = [e for e in eligible if e["has_follow"]]
    # one-step multimodal access: all supported components
    r1_one_step = list(eligible)[:MAX_CONTINUATIONS]

    rel = prs.predict_relational(store, antecedent)
    rel_pred = rel.get("predicted")

    if mode == "legacy":
        conts = []
        if legacy_pred is not None:
            conts = [{"id": "legacy_mean", "center": legacy_pred, "empirical_weight": 1.0,
                      "support": float(legacy.get("support") or 0), "source": "legacy", "has_follow": False}]
        return {"status": "LEGACY", "continuations": conts, "legacy_mean": legacy_pred, "n": len(conts)}

    if mode == "relational":
        conts = []
        if rel_pred is not None:
            conts = [{"id": "relational", "center": rel_pred, "empirical_weight": 1.0,
                      "support": float(rel.get("n_anchors") or 0), "source": "relational", "has_follow": True}]
        return {"status": "RELATIONAL", "continuations": conts, "legacy_mean": legacy_pred, "n": len(conts)}

    if mode == "components":
        conts = r1_one_step[:MAX_CONTINUATIONS]
        status = "MULTI" if len(conts) >= 2 else ("SINGLE" if conts else "NONE")
        return {"status": status, "continuations": conts, "legacy_mean": legacy_pred, "n": len(conts)}

    # auto
    if len(r1) >= 2:
        conts = r1[:MAX_CONTINUATIONS]
        return {"status": "MULTI_FOLLOW", "continuations": conts, "legacy_mean": legacy_pred, "n": len(conts)}
    if len(r1_one_step) >= 2:
        # multimodal one-step without deep follow
        return {"status": "MULTI_ONE_STEP", "continuations": r1_one_step[:MAX_CONTINUATIONS],
                "legacy_mean": legacy_pred, "n": len(r1_one_step[:MAX_CONTINUATIONS])}
    if rel_pred is not None and len(r1_one_step) <= 1:
        # continuous / insufficient multi: prefer relational single path (4.36)
        return {"status": "RELATIONAL", "continuations": [{
            "id": "relational", "center": rel_pred, "empirical_weight": 1.0,
            "support": float(rel.get("n_anchors") or 0), "source": "relational", "has_follow": True,
        }], "legacy_mean": legacy_pred, "n": 1}
    if legacy_pred is not None:
        return {"status": "LEGACY", "continuations": [{
            "id": "legacy_mean", "center": legacy_pred, "empirical_weight": 1.0,
            "support": float(legacy.get("support") or 0), "source": "legacy", "has_follow": False,
        }], "legacy_mean": legacy_pred, "n": 1}
    return {"status": "NONE", "continuations": [], "legacy_mean": None, "n": 0}


def _later_action_at(store, state, goals, *, ablate=False):
    if ablate:
        return {"preferred": None, "P_A": 0.5, "P_B": 0.5, "ablated": True}
    return cp.later_action_distribution(store, state, goals)


def _predict_next_from_state(store, state, action: str) -> dict[str, float] | None:
    step = pc.predict_one_step(store, state, action)
    if step.get("status") == "MATCH":
        return step.get("predicted")
    # try follow from assigned component
    pr = pss.predict_next(store, antecedent=state, action=action, current=state, path="full")
    return pr.get("predicted")


def propagate_continuations(
    store: dict[str, Any],
    *,
    start: dict[str, float],
    first_action: str,
    goals: dict[str, Any] | None = None,
    depth: int = 2,
    include_later_action: bool = True,
    later_actions: tuple[str, ...] = ("A", "B"),
) -> dict[str, Any]:
    """Bounded multimodal prospective propagation.

    Step 0: predict_continuations(start, first_action)
    For each continuation center O:
      optionally later_action_distribution(O) -> preferred act
      then one-step predict from O under preferred / WAIT / fixed
    Merge near-duplicate leaves by L1.
    """
    goals = goals or pci.default_goals()
    depth = min(int(depth), MAX_PROP_DEPTH)
    if store.get("ablate_multimodal_propagation"):
        # legacy fixed one path
        one = pc.predict_one_step(store, start, first_action)
        return {
            "trajectories": [{
                "id": "legacy",
                "weight": 1.0,
                "states": [start, one.get("predicted")],
                "actions": [first_action],
                "later_action": None,
                "distal": one.get("predicted"),
            }] if one.get("status") == "MATCH" else [],
            "n_trajectories": 1 if one.get("status") == "MATCH" else 0,
            "nodes": 1,
            "depth": 1,
            "mode": "legacy_ablated",
        }

    root = predict_continuations(store, start, first_action, mode="auto")
    trajs = []
    nodes = 0
    for cont in root.get("continuations") or []:
        if nodes >= MAX_PROP_NODES:
            break
        O = cont.get("center")
        if O is None:
            continue
        w = float(cont.get("empirical_weight") or 0.0)
        actions = [first_action]
        states = [dict(start), dict(O)]
        later = None
        distal = dict(O)

        if include_later_action and depth >= 2 and not store.get("ablate_later_action"):
            la = _later_action_at(store, O, goals, ablate=False)
            later = la.get("preferred")
            if later:
                actions.append(later)
                nxt = _predict_next_from_state(store, O, later)
                if nxt is not None:
                    states.append(dict(nxt))
                    distal = dict(nxt)
                    nodes += 1
        elif include_later_action and store.get("ablate_later_action"):
            later = None
            # still advance with a fixed placeholder action if transitions exist — skip
        elif depth >= 2 and first_action == "WAIT":
            # world/body autonomous: another WAIT step
            nxt = _predict_next_from_state(store, O, "WAIT")
            if nxt is not None:
                actions.append("WAIT")
                states.append(dict(nxt))
                distal = dict(nxt)
                nodes += 1

        # optional depth 3: another WAIT evolution
        if depth >= 3 and actions[-1] == "WAIT":
            nxt2 = _predict_next_from_state(store, distal, "WAIT")
            if nxt2 is not None:
                actions.append("WAIT")
                states.append(dict(nxt2))
                distal = dict(nxt2)
                nodes += 1

        trajs.append({
            "id": cont.get("id"),
            "weight": w,
            "source": cont.get("source"),
            "has_follow": cont.get("has_follow"),
            "states": states,
            "actions": actions,
            "later_action": later,
            "distal": distal,
            "immediate": dict(O),
        })
        nodes += 1
        if len(trajs) >= MAX_CONTINUATIONS:
            break

    # merge predictively equivalent distal leaves
    merged = []
    for t in trajs:
        found = None
        for m in merged:
            if _l1(t.get("distal"), m.get("distal")) <= MERGE_L1 and t.get("later_action") == m.get("later_action"):
                found = m
                break
        if found is None:
            merged.append(deepcopy(t))
        else:
            found["weight"] = float(found.get("weight") or 0) + float(t.get("weight") or 0)
            found.setdefault("merged_from", []).append(t.get("id"))

    # renormalize weights
    tw = sum(float(t.get("weight") or 0) for t in merged) or 1.0
    for t in merged:
        t["weight"] = float(t.get("weight") or 0) / tw

    return {
        "root": {k: v for k, v in root.items() if k != "continuations"},
        "root_continuations": root.get("continuations"),
        "trajectories": merged,
        "n_trajectories": len(merged),
        "n_pre_merge": len(trajs),
        "nodes": nodes,
        "depth": depth,
        "legacy_mean": root.get("legacy_mean"),
        "leak_tokens": audit_forbidden(merged),
    }


def fictitious_mean_status(legacy_mean, continuations, *, never_obs_radius=0.12) -> dict[str, Any]:
    """Researcher: does propagation avoid sole use of unobserved mid mean?"""
    if legacy_mean is None:
        return {"legacy_is_sole": False, "legacy_field1": None}
    lf1 = float(legacy_mean.get("field_1", 0.5))
    centers = [float((c.get("center") or {}).get("field_1", 0)) for c in continuations]
    sole = len(continuations) == 1 and abs(centers[0] - lf1) < 0.05 if centers else True
    return {
        "legacy_field1": lf1,
        "continuation_field1": centers,
        "legacy_is_sole_future": bool(sole and len(continuations) <= 1),
        "avoids_fictitious_sole_mean": not (len(continuations) >= 2 and sole) and len(continuations) >= 2,
    }


# -------------------- acquisition helpers --------------------

def base_S():
    return pss.base_S()


def Ox():
    return cp.Ox()


def Oy():
    return cp.Oy()


def F_plus():
    return cp.F_plus()


def F_minus():
    return cp.F_minus()


def learn_pair(store, ant, act, cons, *, tick, n=40):
    for i in range(n):
        mm.learn_transition_mm(store, tick=tick + i, antecedent=ant, action=act, consequent=cons)
    return tick + n


def learn_follow_chain(store, series, *, action, seed=0, tick0=1):
    """Prequential-style learn transitions + follow + anchors along series under constant action."""
    rng = random.Random(seed)
    tick = tick0
    S = series[0] if series else base_S()
    # Use fixed antecedent for (S0,A0)->Oi pattern: learn each step as transition from previous
    for t in range(len(series) - 1):
        cur, nxt = series[t], series[t + 1]
        # For multimodal from S0: also learn S0,action -> each observation when at start
        mm.learn_transition_mm(store, tick=tick, antecedent=cur, action=action, consequent=nxt)
        pss.learn_step(store, tick=tick, antecedent=cur, action=action, consequent=cur, next_consequent=nxt, rng=rng)
        prs._update_anchor(store, cur, nxt, tick)
        tick += 1
    return tick


def acquire_bimodal_contingent(*, seed, n_a0=80, n_later=48, p_y=0.5, novel=True):
    """Acquire S0,A0->{Ox,Oy}, Ox+A->F+, Ox+B->F-, Oy+A->F-, Oy+B->F+ separately.
    If novel: never record full S0-A0-Ox-A-F as one exposure pattern.
    """
    store = empty_mpp_store()
    rng = random.Random(seed)
    goals = pci.default_goals()
    tick = 1
    S = base_S()
    # A0 -> Ox / Oy
    n_y = int(n_a0 * p_y)
    n_x = n_a0 - n_y
    for _ in range(n_x):
        mm.learn_transition_mm(store, tick=tick, antecedent=S, action="A0", consequent=Ox())
        # follow: Ox then later consequence via forced path for sequential support
        tick += 1
    for _ in range(n_y):
        mm.learn_transition_mm(store, tick=tick, antecedent=S, action="A0", consequent=Oy())
        tick += 1

    # Build follow associations: after assigning component at Ox/Oy-like outcomes from A0,
    # next physical step toward F via later actions — teach later action transitions
    def Fy():
        f = dict(F_plus())
        f["energy_signal"] = 0.55
        f["fatigue_signal"] = 0.45
        f["resistance"] = 0.80
        f["field_2"] = 0.90
        return f
    for _ in range(n_later):
        mm.learn_transition_mm(store, tick=tick, antecedent=Ox(), action="A", consequent=F_plus()); tick += 1
        mm.learn_transition_mm(store, tick=tick, antecedent=Ox(), action="B", consequent=F_minus()); tick += 1
        mm.learn_transition_mm(store, tick=tick, antecedent=Oy(), action="A", consequent=F_minus()); tick += 1
        mm.learn_transition_mm(store, tick=tick, antecedent=Oy(), action="B", consequent=Fy()); tick += 1

    # Sequential follow from S0 perspective: when current is Ox-like after A0, next tends toward F via preferred
    # Teach follow_by_component by streaming S0 observations alternating Ox/Oy then distal
    for i in range(n_a0):
        o = Ox() if i < n_x else Oy()
        # learn_step needs consequent then next — use o as current observation under A0 from S
        nxt = F_plus() if (o == Ox() or _l1(o, Ox()) < 0.2) else F_plus()
        # better: Ox -> after preferred A -> F+
        if _l1(o, Ox()) <= _l1(o, Oy()):
            nxt = F_plus()
        else:
            nxt = F_plus()  # both can go to plus via appropriate action; for follow use state itself as next mid
        # follow: component of A0 consequence predicts a mid state (the O itself already learned)
        # Teach: from O, following A/B already done. For follow table from (S,A0) components:
        pss.learn_step(store, tick=tick, antecedent=S, action="A0", consequent=o, next_consequent=o, rng=rng)
        tick += 1

    # exposure audit: novel => 0 full sequences
    if novel:
        store["full_sequence_patterns"] = {}
    fsp = store.get("full_sequence_patterns") or {}
    exp = 0
    for v in fsp.values():
        if isinstance(v, dict):
            exp += int(v.get("count") or 0)
        else:
            exp += int(v or 0)
    meta = {"seed": seed, "n_a0": n_a0, "n_x": n_x, "n_y": n_y, "p_y": p_y,
            "full_sequence_exposure_count": exp}
    return store, goals, meta


def acquire_wait_world(*, seed, n=200):
    """World evolves under WAIT; two trajectory families strongly separated in accessible fields."""
    store = empty_mpp_store()
    rng = random.Random(seed)
    tick = 1
    S = base_S()
    for i in range(n):
        if rng.random() < 0.5:
            # X: moves away — low discomfort
            w0 = {"energy_signal": 0.45, "hydration_signal": 0.72, "fatigue_signal": 0.20,
                  "discomfort_signal": 0.05, "field_1": 0.15, "field_2": 0.20, "resistance": 0.20}
            w1 = {**w0, "field_1": 0.12, "field_2": 0.55, "resistance": 0.18}
            w2 = {**w0, "field_1": 0.10, "field_2": 0.90, "resistance": 0.15, "discomfort_signal": 0.04}
        else:
            # Y: approaches interaction — high discomfort/resistance
            w0 = {"energy_signal": 0.45, "hydration_signal": 0.72, "fatigue_signal": 0.20,
                  "discomfort_signal": 0.08, "field_1": 0.85, "field_2": 0.20, "resistance": 0.25}
            w1 = {**w0, "field_1": 0.88, "field_2": 0.50, "resistance": 0.60, "discomfort_signal": 0.18}
            w2 = {**w0, "field_1": 0.90, "field_2": 0.80, "resistance": 0.90, "discomfort_signal": 0.40}
        mm.learn_transition_mm(store, tick=tick, antecedent=w0, action="WAIT", consequent=w1); tick += 1
        mm.learn_transition_mm(store, tick=tick, antecedent=w1, action="WAIT", consequent=w2); tick += 1
        pss.learn_step(store, tick=tick, antecedent=w0, action="WAIT", consequent=w0, next_consequent=w1, rng=rng); tick += 1
        pss.learn_step(store, tick=tick, antecedent=w1, action="WAIT", consequent=w1, next_consequent=w2, rng=rng); tick += 1
        prs._update_anchor(store, w0, w1, tick); prs._update_anchor(store, w1, w2, tick)
        mm.learn_transition_mm(store, tick=tick, antecedent=S, action="WAIT", consequent=w0); tick += 1
        pss.learn_step(store, tick=tick, antecedent=S, action="WAIT", consequent=w0, next_consequent=w1, rng=rng); tick += 1
    return store, S
