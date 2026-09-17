"""Update 4.38 — externally acquired consequence structure.

Research harness only.  Passive observations are learned without inventing an
agent action token.  The autonomous probe deliberately preserves the existing
absence of a passive-prediction -> present-action interface.
"""
from __future__ import annotations

import json
import math
import random
import re
from copy import deepcopy
from typing import Any

from mechanistic_mind.research import predictive_generalization as pg
from mechanistic_mind.research.composed_future_value import ordinary_state_value
from mechanistic_mind.research.prospective_consequence_influence import default_goals

MAX_RAW = 96
MAX_PROVENANCE = 16
BASELINE_NON_WAIT = 0.08

FORBIDDEN_COGNITION = (
    "INCUBATION", "CHILDHOOD", "PARENT", "FEED", "FOOD", "HUNGER", "EAT",
    "EDIBLE", "NUTRITION", "GOOD", "BAD", "BENEFIT", "HARM", "REWARD",
    "PUNISHMENT", "PLEASURE", "PAIN", "NEED", "WANT", "DESIRE",
    "MOTIVATION", "DRIVE", "INTEREST", "CURIOSITY", "EXPLORATION",
    "NOVELTY", "BOREDOM", "SURVIVAL", "SELF_PRESERVATION", "PREFERENCE",
    "GOAL", "PURPOSE", "REASON_TO_ACT", "MATURATION", "PERSONALITY",
)


def architecture_inspection() -> dict[str, Any]:
    return {
        "A_non_wait_without_learning": "sensorimotor endogenous variation / stochastic proposal order",
        "B_baseline_distribution": {"WAIT": 1.0 - BASELINE_NON_WAIT, "INTERACT": BASELINE_NON_WAIT},
        "C_intrinsic_non_wait": True,
        "D_body_to_logits": "ordinary_state_value uses inherited signal targets/weights in 4.26 pathways",
        "E_inherited_preference": {
            "present": True,
            "variables": ["energy_signal", "hydration_signal", "fatigue_signal", "discomfort_signal"],
            "mapping": "squared target-error reduction; signs and weights are inherited",
        },
        "F_passive_learning": "supported here through ordinary feature/consequence observation; no action label",
        "G_external_to_later_body": True,
        "H_novel_instance_generalization": "4.27 physical feature conjunctions can support it",
        "I_passive_to_present_action_without_value": False,
        "J_preimplementation_conclusion": "NO CAUSAL ROUTE; none added by Update 4.38",
        "wait_semantics": "no intervention; body dynamics continue",
        "historical_437": "predict_continuations/propagate_continuations and C18 NULL untouched",
    }


def initial_body() -> dict[str, float]:
    return {"energy_signal": .45, "hydration_signal": .70, "fatigue_signal": .20, "discomfort_signal": .05}


def sources() -> dict[str, dict[str, float]]:
    return {
        "X1": {"surface_a": .62, "surface_b": .67, "mass": .20},
        "X2": {"surface_a": .65, "surface_b": .70, "mass": .28},
        "X3": {"surface_a": .68, "surface_b": .64, "mass": .24},
        "X4": {"surface_a": .66, "surface_b": .68, "mass": .32},
        "Y":  {"surface_a": .12, "surface_b": .88, "mass": .32},
    }


def consequence(features: dict[str, float], family: str = "A") -> dict[str, float]:
    """Generic physical transform; family is researcher-side experimental routing."""
    if family == "B":
        return {"energy_signal": .31, "hydration_signal": .62, "fatigue_signal": .34, "discomfort_signal": .13}
    return {"energy_signal": .67, "hydration_signal": .73, "fatigue_signal": .15, "discomfort_signal": .04}


def empty_organism(seed: int) -> dict[str, Any]:
    return {
        "seed": seed, "body": initial_body(), "predictive": pg.empty_store(),
        "raw": [], "provenance": {}, "external_count": 0,
        "forced_by_object": {}, "endogenous_by_object": {}, "tick": 0,
    }


def external_transition(org: dict[str, Any], object_id: str, *, future: dict[str, float]) -> None:
    """Record a world-initiated transition.  No endogenous action is fabricated."""
    feat = sources()[object_id]
    org["tick"] += 1
    org["external_count"] += 1
    org["forced_by_object"][object_id] = org["forced_by_object"].get(object_id, 0) + 1
    before = dict(org["body"])
    pg.observe(org["predictive"], feat, future)
    sig = pg.feature_sig(feat)
    ids = org["provenance"].setdefault(sig, [])
    ids.append(f"external:{org['tick']}:{object_id}")
    del ids[:-MAX_PROVENANCE]
    org["raw"].append({"tick": org["tick"], "cause": "EXTERNAL", "features": feat,
                       "before": before, "after": dict(future)})
    del org["raw"][:-MAX_RAW]
    org["body"] = dict(future)


def develop(org: dict[str, Any], *, exposures: int, mode: str = "structured", family: str = "A") -> None:
    rng = random.Random(org["seed"])
    ids = ("X1", "X2", "X3")
    outcomes = [consequence(sources()[x], family) for x in ids]
    for i in range(exposures):
        oid = ids[i % len(ids)]
        if mode == "decorrelated":
            future = dict(outcomes[rng.randrange(len(outcomes))])
            # Equal marginal variation, with deterministic channel permutations.
            vals = list(future.values()); rng.shuffle(vals)
            future = dict(zip(future, vals))
        else:
            future = dict(consequence(sources()[oid], family))
        external_transition(org, oid, future=future)


def passive_prediction(org: dict[str, Any], object_id: str) -> dict[str, Any]:
    return pg.predict(org["predictive"], sources()[object_id])


def action_distribution(org: dict[str, Any], object_id: str, *, acquired_ablation: bool = False,
                        value_neutralized: bool = False) -> dict[str, Any]:
    """Existing baseline only: passive predictions are diagnostic, not action input."""
    pred = passive_prediction(org, object_id) if not acquired_ablation else {"status": "ABLATION", "predicted": None}
    p = BASELINE_NON_WAIT
    value = None
    if pred.get("predicted") is not None and not value_neutralized:
        value = ordinary_state_value(start=org["body"], terminal=pred["predicted"], goals=default_goals())
    return {
        "probs": {"WAIT": 1.0 - p, f"INTERACT:{object_id}": p},
        "logits": {"WAIT": math.log(1.0 - p), f"INTERACT:{object_id}": math.log(p)},
        "prediction": pred, "ordinary_state_value_diagnostic": value,
        "ordinary_state_value_contribution_to_logits": 0.0,
        "acquired_structure_contribution_to_logits": 0.0,
        "stochastic_contribution": "baseline endogenous variation",
    }


def first_intervention(org: dict[str, Any], object_id: str, *, max_ticks: int = 80,
                       acquired_ablation: bool = False, value_neutralized: bool = False) -> dict[str, Any] | None:
    dist = action_distribution(org, object_id, acquired_ablation=acquired_ablation,
                               value_neutralized=value_neutralized)
    rng = random.Random(org["seed"] + 438000 + org["tick"])
    start = org["tick"]
    for offset in range(1, max_ticks + 1):
        org["tick"] += 1
        # WAIT changes the physical body even when no intervention occurs.
        org["body"]["energy_signal"] = max(0.0, org["body"]["energy_signal"] - .001)
        org["body"]["fatigue_signal"] = min(1.0, org["body"]["fatigue_signal"] + .001)
        if rng.random() < BASELINE_NON_WAIT:
            org["endogenous_by_object"][object_id] = org["endogenous_by_object"].get(object_id, 0) + 1
            return {"incubation_end_tick": start, "tick": org["tick"], "latency": offset,
                    "action": f"INTERACT:{object_id}", "target": object_id,
                    "body": dict(org["body"]), "observation": dict(sources()[object_id]), **dist}
    return None


def purge_raw(org: dict[str, Any]) -> dict[str, int]:
    n = len(org["raw"]); org["raw"] = []
    return {"purged": n, "predictive_retained": len(org["predictive"].get("pair") or {})}


def ablate_acquired(org: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(org); out["predictive"] = pg.empty_store(); return out


def memory_snapshot(org: dict[str, Any]) -> dict[str, int]:
    p = org["predictive"]
    return {"recent_buffer": len(org["raw"]), "compressed_structure_count": len(p.get("pair") or {}),
            "context_count": 0, "predictive_structure_count": sum(len(p.get(k) or {}) for k in ("exact", "single", "pair")),
            "provenance_size": sum(len(x) for x in org["provenance"].values()),
            "memory_bytes": len(json.dumps({"p": p, "raw": org["raw"], "prov": org["provenance"]}, default=str).encode())}


def cognition_leaks(org: dict[str, Any]) -> list[str]:
    payload = {"predictive": org["predictive"], "raw": org["raw"]}
    text = json.dumps(payload, sort_keys=True).upper()
    return [token for token in FORBIDDEN_COGNITION if re.search(rf"(?<![A-Z]){re.escape(token)}(?![A-Z])", text)]
