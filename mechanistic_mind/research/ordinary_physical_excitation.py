"""Update 4.49 — measure whether existing world physics writes 4.41 u.

Does not add a world→u bridge. Does not inject researcher X as ordinary.
"""
from __future__ import annotations

import json
import re
from typing import Any

from mechanistic_mind.body.adaptive_internal_coupling import AdaptiveInternalState, step as w_step
from mechanistic_mind.body.endogenous_signaling import EndogenousSignalState, evolve_signal
from mechanistic_mind.body.sensorimotor_dynamics import SensorimotorState, evolve
from mechanistic_mind.research import body_coupled_development as bcd
from mechanistic_mind.research import endogenous_dynamic_range as edr
from mechanistic_mind.research import endogenous_motor_access as ema
from mechanistic_mind.research import intrinsic_sensorimotor_dynamics as ism
from mechanistic_mind.world_engine.background_fields import (
    default_field_spec, init_background_state, local_body_coupling, sample_local_fields,
)

POS_A = (4, 3)
POS_B = (14, 12)
POS_FAR = (0, 0)
MAP = (20, 16)
STAGED_STEPS = 32
WALK_STEPS = 96
FORBIDDEN = bcd.FORBIDDEN + (
    "PREFERRED", "URGENCY", "AROUSAL", "SALIENCE", "BOOST", "BIOGRAPHY",
    "SELF", "SIGNIFICANT_EVENT", "HIGH_N_EVENT", "USEFUL_INPUT", "IMPORTANCE",
)


def world_state(*, seed: int, enabled: bool = True) -> dict[str, Any]:
    spec = default_field_spec()
    spec["enabled"] = bool(enabled)
    bg = init_background_state(width=MAP[0], height=MAP[1], spec=spec, seed=seed)
    return {"background_fields": bg}


def advance(state: dict[str, Any]) -> None:
    bg = state["background_fields"]
    if isinstance(bg, dict) and bg.get("enabled"):
        bg["tick"] = int(bg.get("tick") or 0) + 1


def sample(state: dict[str, Any], pos: tuple[int, int]) -> dict[str, float]:
    return sample_local_fields(state, position=pos)


def body_delta(state: dict[str, Any], pos: tuple[int, int]) -> dict[str, float]:
    return local_body_coupling(state, position=pos)


def run_position(*, seed: int, pos: tuple[int, int], enabled: bool, steps: int,
                 RA, RB, dR, d_probe_L2: float) -> list[dict[str, Any]]:
    """Ordinary physics at a location. u is never written from the field."""
    st = world_state(seed=seed, enabled=enabled)
    q = AdaptiveInternalState()
    I = EndogenousSignalState()
    N = SensorimotorState()
    body = ism.body(0.50, 0.50)
    rows = []
    for t in range(steps):
        advance(st)
        fields = sample(st, pos) if enabled else {}
        coupling = body_delta(st, pos) if enabled else {}
        q = w_step(q, physical_input=(), plasticity=False)  # empty u — no bridge
        I = evolve_signal(I, perturbation=q.q)
        rv = ((seed * 29 + t * 13) % 101) / 100.0
        N = evolve(N, body=body, sensory=(0.5, 0.5), random_value=rv,
                   endogenous=I.channels, endogenous_coupling=True)
        u = (0.0, 0.0, 0.0)
        drv = ema.matvec(dR, N.channels)
        a = ema.apply_motor(N.channels, RA)
        b = ema.apply_motor(N.channels, RB)
        from mechanistic_mind.research.acquired_sensorimotor_coupling import prob_l1
        obs = prob_l1(a["probs"], b["probs"])
        rel = ema.l2(drv) / d_probe_L2 if d_probe_L2 > 1e-15 else 0.0
        rows.append({
            "t": t, "pos": pos, "enabled": enabled,
            "fields": fields, "body_coupling": coupling,
            "u": u, "q": q.q, "I": I.channels, "N": N.channels,
            "n_L2": ema.l2(N.channels), "u_L2": ema.l2(u),
            "q_L2": ema.l2(q.q), "I_L2": ema.l2(I.channels),
            "dR_L2": ema.l2(drv), "rel_drive": rel,
            "pred": rel * edr.PROBE_DP, "obs": obs,
            "field_chem1": float(fields.get("chemical_1") or 0.0),
            "klass": "PHYSICALLY_ORDINARY_STAGED",
        })
    return rows


def spontaneous_walk(*, seed: int, RA, RB, dR, d_probe_L2: float) -> list[dict[str, Any]]:
    """Unconstrained walk; does not steer toward region A."""
    st = world_state(seed=seed, enabled=True)
    q = AdaptiveInternalState()
    I = EndogenousSignalState()
    N = SensorimotorState()
    body = ism.body(0.50, 0.50)
    x, y = 9, 8
    rows = []
    for t in range(WALK_STEPS):
        advance(st)
        # existing-style raster walk, not a hunt for region A
        x = (x + 1) % MAP[0]
        if x == 0:
            y = (y + 1) % MAP[1]
        fields = sample(st, (x, y))
        q = w_step(q, physical_input=(), plasticity=False)
        I = evolve_signal(I, perturbation=q.q)
        rv = ((seed * 31 + t * 17) % 101) / 100.0
        N = evolve(N, body=body, sensory=(0.5, 0.5), random_value=rv,
                   endogenous=I.channels, endogenous_coupling=True)
        u = (0.0, 0.0, 0.0)
        drv = ema.matvec(dR, N.channels)
        from mechanistic_mind.research.acquired_sensorimotor_coupling import prob_l1
        obs = prob_l1(ema.apply_motor(N.channels, RA)["probs"],
                      ema.apply_motor(N.channels, RB)["probs"])
        rel = ema.l2(drv) / d_probe_L2 if d_probe_L2 > 1e-15 else 0.0
        rows.append({
            "t": t, "pos": (x, y), "fields": fields, "u": u,
            "N": N.channels, "n_L2": ema.l2(N.channels), "u_L2": 0.0,
            "dR_L2": ema.l2(drv), "rel_drive": rel,
            "pred": rel * edr.PROBE_DP, "obs": obs,
            "field_chem1": float(fields.get("chemical_1") or 0.0),
            "klass": "NATURAL_RUNTIME",
        })
    return rows


def u_writers() -> list[dict[str, str]]:
    return [
        {"writer": "acquired_internal_dynamics", "class": "RESEARCHER_PROBE"},
        {"writer": "body_coupled_development", "class": "EXISTING_CONTROLLED"},
        {"writer": "world_body_biography", "class": "EXISTING_CONTROLLED"},
        {"writer": "psyche/body/world engine", "class": "NONE"},
    ]


def cognition_leaks(payload: Any) -> list[str]:
    text = json.dumps(payload, sort_keys=True, default=str).upper()
    return [x for x in FORBIDDEN if re.search(rf"(?<![A-Z]){re.escape(x)}(?![A-Z])", text)]
