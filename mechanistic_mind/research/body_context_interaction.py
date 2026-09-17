"""Update 4.44 — body × acquired-history interaction. Readout unchanged."""
from __future__ import annotations

import json
import math
import re
from typing import Any

from mechanistic_mind.body.adaptive_internal_coupling import AdaptiveInternalState, representation, step
from mechanistic_mind.body.endogenous_signaling import EndogenousSignalState, evolve_signal
from mechanistic_mind.body.sensorimotor_dynamics import SensorimotorState, evolve, motor_distribution
from mechanistic_mind.research import distal_consequence as dc
from mechanistic_mind.research import body_coupled_development as bcd

BODIES = {
    "B_LOW": {"internal_a": 0.25, "load_c": 0.70},
    "B_MID": {"internal_a": 0.55, "load_c": 0.45},
    "B_HIGH": {"internal_a": 0.80, "load_c": 0.25},
}
SPAN_MIN = 0.008
RESIDUAL_MIN = 0.004
T_DOWN = [{"internal_a": 0.70, "load_c": 0.30}, {"internal_a": 0.62, "load_c": 0.36}, {"internal_a": 0.55, "load_c": 0.45}]
T_UP = [{"internal_a": 0.40, "load_c": 0.60}, {"internal_a": 0.48, "load_c": 0.52}, {"internal_a": 0.55, "load_c": 0.45}]
FORBIDDEN = dc.FORBIDDEN + (
    "CONTEXT", "SITUATION", "IMPROVING", "WORSENING", "URGENCY", "SALIENCE_VALUE",
    "REASON_TO_ACT", "INTERVENTION_NEED", "PREFERRED_STATE", "HOMEOSTATIC_GOAL",
)


def develop_histories(seed: int, trials: int = 36):
    h0, _, st0 = dc.develop("H0", trials=trials, seed=seed)
    h1, raw1, st1 = dc.develop("H1", trials=trials, seed=seed)
    h1b, _, st1b = dc.develop("H1B", trials=trials, seed=seed)
    h2, raw2, st2 = dc.develop("H2", trials=trials, seed=seed, delay=dc.PRIMARY_DELAY)
    return {"H0": h0, "H1": h1, "H1B": h1b, "H2": h2}, {"H0": st0, "H1": st1, "H1B": st1b, "H2": st2}, raw2


def probe_cell(state: AdaptiveInternalState, body: dict[str, float], *, seed: int, **kw) -> dict[str, Any]:
    return bcd.autonomous_probe(state, bcd.X, seed=seed, body=dict(body), n_samples=kw.pop("n_samples", 48), **kw)


def last_vec(probe: dict, key: str) -> tuple[float, ...]:
    return tuple(probe["trajectory"][-1][key])


def l1(a, b) -> float:
    return sum(abs(x - y) for x, y in zip(a, b))


def additive_model(cells: dict[str, dict[str, float]]) -> dict[str, Any]:
    """cells[history][body] = P(A). Researcher-side only."""
    hs = list(cells)
    bs = list(next(iter(cells.values())))
    vals = [cells[h][b] for h in hs for b in bs]
    mu = sum(vals) / len(vals)
    body_main = {b: sum(cells[h][b] for h in hs) / len(hs) - mu for b in bs}
    hist_main = {h: sum(cells[h][b] for b in bs) / len(bs) - mu for h in hs}
    pred = {h: {b: mu + body_main[b] + hist_main[h] for b in bs} for h in hs}
    resid = {h: {b: cells[h][b] - pred[h][b] for b in bs} for h in hs}
    max_abs = max(abs(resid[h][b]) for h in hs for b in bs)
    deltas = {b: cells["H2"][b] - cells["H1"][b] for b in bs}
    span = max(deltas.values()) - min(deltas.values())
    return {"mu": mu, "body_main": body_main, "hist_main": hist_main, "pred": pred,
            "residual": resid, "max_abs_residual": max_abs, "delta_history": deltas, "span": span}


def trajectory_then_probe(state: AdaptiveInternalState, path: list[dict[str, float]], *, seed: int,
                          reset_internal: bool = False) -> dict[str, Any]:
    """Walk body path into N (no new memory). Then X probe. If reset_internal, wipe q/I/N at the end of the path."""
    s = AdaptiveInternalState(weights=state.weights)
    I = EndogenousSignalState()
    N = SensorimotorState()
    for i, body in enumerate(path):
        s = step(s, physical_input=dc.ZERO, plasticity=False)
        I = evolve_signal(I, perturbation=s.q)
        N = evolve(N, body=body, sensory=(0.5, 0.5),
                   random_value=((seed * 17 + i * 7) % 101) / 100.0,
                   endogenous=I.channels, endogenous_coupling=True)
    if reset_internal:
        s = AdaptiveInternalState(weights=state.weights)
        I = EndogenousSignalState()
        N = SensorimotorState()
    # X probe ticks from retained (or reset) state
    traj = []
    body_final = path[-1]
    for t in range(8):
        s = step(s, physical_input=dc.X if t == 0 else dc.ZERO, plasticity=False)
        I = evolve_signal(I, perturbation=s.q)
        N = evolve(N, body=body_final, sensory=(0.5, 0.5),
                   random_value=((seed * 29 + t * 13) % 101) / 100.0,
                   endogenous=I.channels, endogenous_coupling=True)
        traj.append({"q": s.q, "I": I.channels, "N": N.channels})
    motor = motor_distribution(N)
    return {"q": s.q, "I": I.to_dict(), "N": N.to_dict(), "motor": motor,
            "p_A": float(motor["probs"]["M1"]), "trajectory": traj, "body_final": dict(body_final)}


def cognition_leaks(payload: Any) -> list[str]:
    text = json.dumps(payload, sort_keys=True, default=str).upper()
    return [x for x in FORBIDDEN if re.search(rf"(?<![A-Z]){re.escape(x)}(?![A-Z])", text)]
