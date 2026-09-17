"""Update 4.39 research probes for reactive and predictive sensorimotor chains."""
from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any

from mechanistic_mind.body.sensorimotor_dynamics import SensorimotorState, evolve, motor_distribution
from mechanistic_mind.research import predictive_generalization as pg

MAX_RECENT = 96
FORBIDDEN = (
    "NERVOUS_SYSTEM", "NEURON", "HUNGER", "FOOD", "EAT", "THIRST", "PAIN",
    "PLEASURE", "FEAR", "GOOD", "BAD", "REWARD", "PUNISHMENT", "NEED",
    "WANT", "DESIRE", "MOTIVATION", "DRIVE", "CURIOSITY", "EXPLORATION",
    "SURVIVAL", "SELF_PRESERVATION", "HOMEOSTASIS_GOAL", "UTILITY", "VALUE",
    "EXPECTED_VALUE", "RISK", "URGENCY", "SEEK", "AVOID", "BENEFICIAL",
    "HARMFUL", "DISCOMFORT", "SATIETY", "RELIEF",
)


def architecture_inspection() -> dict[str, Any]:
    return {
        "A_438_probability": "BASELINE_NON_WAIT=0.08 in psyche_incubation.action_distribution; sampled at research action selection",
        "B_stochastic_location": "research action selection in 4.38; generic proposal ordering also exists in psyche.sensorimotor",
        "C_body_to_execution": "existing body engine supplies costs/loads; no generic body-to-motor dynamical state found",
        "D_body_to_action_probability": "legacy paths only through body target-error evaluation; 4.38 baseline is body-independent",
        "E_value_path": "predicted body -> ordinary_state_value -> action_logits in 4.26",
        "F_existing_physics": "action costs, body process evolution, intake/loads and WAIT evolution exist; no shared bounded N layer",
        "G_generic_intermediate": False,
        "H_predicted_body_to_intermediate_without_value": False,
        "I_conclusion": "No suitable layer existed. Added the smallest actual-body-coupled bounded substrate; no predicted-body input port.",
        "category_A": "bounded N evolution, mixed actual-body coupling, N-to-motor conversion",
        "category_B": "stochastic emission may or may not produce a non-WAIT sample",
    }


def body(level_a: float = .5, level_c: float = .5) -> dict[str, float]:
    return {"internal_a": float(level_a), "load_c": float(level_c)}


def cue(x: float, y: float) -> dict[str, float]:
    return {"field_x": float(x), "field_y": float(y)}


def empty_store() -> dict[str, Any]:
    return {"cue_to_body": pg.empty_store(), "body_to_n": pg.empty_store(),
            "action_to_body": pg.empty_store(), "recent": [], "predicted_body_input_enabled": False}


def reactive_probe(actual_body: dict[str, float], *, seed: int, steps: int = 10,
                   body_coupling: bool = True, signal_visible: bool = True,
                   dynamics_enabled: bool = True) -> dict[str, Any]:
    state = SensorimotorState(); trajectory = []
    for t in range(steps):
        rv = ((seed * 37 + t * 19) % 101) / 100.0
        state = evolve(state, body=actual_body, sensory=(.5, .5), random_value=rv,
                       body_coupling=body_coupling, dynamics_enabled=dynamics_enabled)
        trajectory.append(state.to_dict())
    dist = motor_distribution(state)
    return {"actual_body": actual_body, "accessible_signal": actual_body if signal_visible else {},
            "state": state.to_dict(), "trajectory": trajectory, "motor": dist,
            "ablations": {"body_coupling": not body_coupling, "signal_hidden": not signal_visible,
                          "dynamics": not dynamics_enabled},
            "ordinary_state_value_contribution": 0.0, "legacy_action_logits_contribution": 0.0}


def observe_chain(store: dict[str, Any], *, precursor: dict[str, float], future_body: dict[str, float],
                  future_state: SensorimotorState, action_features: dict[str, float] | None = None) -> None:
    pg.observe(store["cue_to_body"], precursor, future_body)
    pg.observe(store["body_to_n"], future_body, {f"channel_{i}": x for i, x in enumerate(future_state.channels)})
    if action_features is not None: pg.observe(store["action_to_body"], action_features, future_body)
    store["recent"].append({"precursor": precursor, "future_body": future_body, "future_n": future_state.to_dict()})
    del store["recent"][:-MAX_RECENT]


def acquire(store: dict[str, Any], *, exposures: int, seed: int, shuffled: bool = False,
            passive: bool = True) -> None:
    patterns = [(cue(.62, .68), body(.80, .30)), (cue(.65, .70), body(.76, .34)), (cue(.68, .64), body(.82, .28))]
    for i in range(exposures):
        precursor, future_body = patterns[i % 3]
        if shuffled: future_body = patterns[(i * 2 + 1) % 3][1]
        future = reactive_probe(future_body, seed=seed + i, steps=6)["state"]
        state = SensorimotorState(channels=tuple(future["channels"]), previous_output=tuple(future["previous_output"]), tick=future["tick"])
        observe_chain(store, precursor=precursor, future_body=future_body, future_state=state,
                      action_features=None if passive else {"motor_0": .8, "motor_1": .2})


def predict_chain(store: dict[str, Any], precursor: dict[str, float]) -> dict[str, Any]:
    pb = pg.predict(store["cue_to_body"], precursor)
    pn = pg.predict(store["body_to_n"], pb["predicted"]) if pb.get("predicted") else {"status": "NO_MATCH", "predicted": None}
    return {"body": pb, "sensorimotor": pn, "composed": pb.get("predicted") is not None and pn.get("predicted") is not None}


def anticipatory_probe(store: dict[str, Any], precursor: dict[str, float], *, current_body: dict[str, float], seed: int,
                       prediction_ablation: bool = False, value_neutralized: bool = False) -> dict[str, Any]:
    prediction = {"body": {"status": "ABLATION", "predicted": None}, "sensorimotor": {"status": "ABLATION", "predicted": None}, "composed": False} if prediction_ablation else predict_chain(store, precursor)
    # Critical NULL: predicted states are inspected, never injected into current N.
    current = reactive_probe(current_body, seed=seed)
    current["prediction"] = prediction
    current["predicted_state_contribution"] = 0.0
    current["value_neutralized"] = value_neutralized
    return current


def purge_recent(store: dict[str, Any]) -> int:
    n = len(store["recent"]); store["recent"] = []; return n


def memory_snapshot(store: dict[str, Any]) -> dict[str, int]:
    structures = sum(len(store[name].get(k) or {}) for name in ("cue_to_body", "body_to_n", "action_to_body") for k in ("exact", "single", "pair"))
    return {"recent": len(store["recent"]), "structures": structures,
            "bytes": len(json.dumps(store, sort_keys=True, default=str).encode())}


def cognition_leaks(payload: Any) -> list[str]:
    text = json.dumps(payload, sort_keys=True, default=str).upper()
    return [x for x in FORBIDDEN if re.search(rf"(?<![A-Z]){re.escape(x)}(?![A-Z])", text)]
