"""Update 4.30 - Unavoidable state transition under non-intervention.

WAIT = no active intervention. Physical field/body evolution continues.
No UNCERTAINTY/URGENCY/WAIT_COST/DELIBERATION/INFORMATION_GAIN in cognition.
Uses existing 4.23 learn_transition + 4.26 ordinary_state_value -> action_logits.
Does not retune EMA or add variance to logits (preserves 4.26 C4 / 4.29 C3 NULLs).
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from mechanistic_mind.research import prospective_composition as pc
from mechanistic_mind.research import prospective_consequence_influence as pci

FORBIDDEN = (
    "DOUBT", "UNCERTAINTY", "CONFIDENCE", "INDECISION", "DELIBERATION", "URGENCY",
    "PRESSURE", "TIME_PRESSURE", "DECISION_COST", "WAIT_COST", "COST_OF_DELAY",
    "FEAR", "RISK", "PATIENCE", "IMPATIENCE", "INFORMATION_GAIN", "CURIOSITY",
    "NEED_MORE_EVIDENCE", "MUST_DECIDE", "WORLD_CHANGED", "CLOCK",
    "WAITING_FOR_EVIDENCE", "UNCERTAIN", "DECISION_PENDING", "FUTURE_INFO",
    "REVEAL", "INFORMATIVE", "UNINFORMATIVE", "TIME_LEFT", "DEADLINE",
    "CORRECT_ACTION", "PAUSE",
)

# Researcher phase index only — never written into cognition features as TIME.
N_FIELD_PHASES = 8


def audit_forbidden(payload: Any) -> list[str]:
    return [t for t in FORBIDDEN if t in str(payload)]


def empty_world(*, freeze_field: bool = False, informative: bool = True) -> dict[str, Any]:
    """Minimal physical situation: autonomous field source + body loads.

    field_level evolves every tick unless freeze_field (control B).
    When informative=False, field still moves but is decorrelated from distal maps.
    """
    return {
        "field_level": 0.10,          # autonomous physical source (0..1)
        "field_rate": 0.12,           # per-tick drift under non-intervention
        "freeze_field": bool(freeze_field),
        "informative": bool(informative),
        "body": {
            "energy_signal": 0.55,
            "hydration_signal": 0.70,
            "fatigue_signal": 0.22,
            "discomfort_signal": 0.06,
        },
        "tick_researcher": 0,         # researcher-only
        "last_action": None,
    }


def accessible_evidence(world: dict[str, Any]) -> dict[str, float]:
    """Agent-accessible physical signals (no TIME/CLOCK)."""
    body = dict(world["body"])
    # Local field reading is ordinary sensory — not a reveal token.
    body["field_signal"] = float(world["field_level"])
    return body


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def step_physics(world: dict[str, Any], action: str) -> dict[str, Any]:
    """One ordinary physical step. WAIT does not freeze dynamics.

    A1: active intervention — pulls field toward low regime.
    B1: active intervention — pulls field toward high regime.
    WAIT: no active intervention; field continues at field_rate (unless frozen).
    """
    w = deepcopy(world)
    w["tick_researcher"] = int(w.get("tick_researcher") or 0) + 1
    w["last_action"] = action
    body = w["body"]

    # Body always metabolizes a little (ordinary continuing evolution).
    body["energy_signal"] = _clamp01(float(body["energy_signal"]) - 0.008)
    body["fatigue_signal"] = _clamp01(float(body["fatigue_signal"]) + 0.004)
    body["hydration_signal"] = _clamp01(float(body["hydration_signal"]) - 0.003)

    fl = float(w["field_level"])
    if action == "A1":
        # Active: drive field down (intervention)
        fl = _clamp01(fl - 0.18)
        body["energy_signal"] = _clamp01(float(body["energy_signal"]) - 0.02)
        body["fatigue_signal"] = _clamp01(float(body["fatigue_signal"]) + 0.015)
    elif action == "B1":
        # Active: drive field up
        fl = _clamp01(fl + 0.18)
        body["energy_signal"] = _clamp01(float(body["energy_signal"]) - 0.02)
        body["fatigue_signal"] = _clamp01(float(body["fatigue_signal"]) + 0.015)
    elif action == "WAIT":
        # NO ACTIVE INTERVENTION — field continues unless freeze control
        if not w.get("freeze_field"):
            fl = _clamp01(fl + float(w.get("field_rate") or 0.12))
        # mild recovery-like body drift (non-semantic)
        body["fatigue_signal"] = _clamp01(float(body["fatigue_signal"]) - 0.002)
    else:
        if not w.get("freeze_field"):
            fl = _clamp01(fl + float(w.get("field_rate") or 0.12))

    w["field_level"] = fl
    w["body"] = body
    return w


def distal_from_field(field_level: float, *, informative: bool = True) -> dict[str, float]:
    """Physical distal body consequence associated with field regime.

    High field -> B_PLUS-like; low field -> B_MINUS-like.
    If not informative, return fixed mid outcome (decorrelated).
    """
    if not informative:
        return {
            "energy_signal": 0.45,
            "hydration_signal": 0.70,
            "fatigue_signal": 0.25,
            "discomfort_signal": 0.08,
        }
    # Interpolate between depleted and restored by field
    t = _clamp01(field_level)
    lo = pci.B_MINUS()
    hi = pci.B_PLUS()
    return {k: (1.0 - t) * float(lo[k]) + t * float(hi[k]) for k in lo}


def evidence_state(ev: dict[str, float]) -> dict[str, float]:
    """Antecedent fragment for prospective learning (body+field signals)."""
    # Use energy/fatigue/field as accessible state — quantized later by pc.
    return {
        "energy_signal": float(ev.get("energy_signal", 0.5)),
        "hydration_signal": float(ev.get("hydration_signal", 0.7)),
        "fatigue_signal": float(ev.get("fatigue_signal", 0.2)),
        "discomfort_signal": float(ev.get("discomfort_signal", 0.05)),
        # fold field into discomfort channel proxy? Better: use energy as carrier
        # Field is separate key — prospective_composition will include it in sig.
        "field_signal": float(ev.get("field_signal", 0.0)),
    }


def train_prior_prospective(store: dict[str, Any], *, n: int = 40, seed: int = 0) -> dict[str, Any]:
    """Acquire A/B/WAIT fragment structures with end-to-end exposure = 0.

    Prior: from low-field start, A1 chain ends depleted-ish; B1 ends restored-ish.
    Uses synthetic mid hops compatible with 4.23 composition (pci S1/S2 etc).
    """
    # Seed prior at low field regime associations
    for i in range(n):
        t = i + 1
        # A chain -> depleted distal (stable)
        pc.learn_transition(store, tick=t, antecedent=pci.S0(), action="A1", consequent=pci.S1())
        pc.learn_transition(store, tick=t, antecedent=pci.S1(), action="A2", consequent=pci.S2())
        pc.learn_transition(store, tick=t, antecedent=pci.S2(), action="A3", consequent=pci.B_MINUS())
        # B chain initially also depleted/mid — WRONG for later high-field regime.
        # Continuing-world high-field evidence can revise B3 toward restored.
        pc.learn_transition(store, tick=t, antecedent=pci.S0(), action="B1", consequent=pci.S3())
        pc.learn_transition(store, tick=t, antecedent=pci.S3(), action="B2", consequent=pci.S4())
        pc.learn_transition(store, tick=t, antecedent=pci.S4(), action="B3", consequent=pci.B_MINUS())
        # WAIT one-step: mild local body drift (not freeze)
        wait_next = {
            "energy_signal": 0.54,
            "hydration_signal": 0.70,
            "fatigue_signal": 0.23,
            "discomfort_signal": 0.06,
        }
        pc.learn_transition(store, tick=t, antecedent=pci.S0(), action="WAIT", consequent=wait_next)
    pc.record_full_sequence_exposure(store, pattern_id="S0_A1_A2_A3", experienced=False)
    pc.record_full_sequence_exposure(store, pattern_id="S0_B1_B2_B3", experienced=False)
    return {
        "n": n,
        "full_A": int((store.get("full_sequence_patterns") or {}).get("S0_A1_A2_A3", {}).get("count") or 0),
        "full_B": int((store.get("full_sequence_patterns") or {}).get("S0_B1_B2_B3", {}).get("count") or 0),
    }


def online_learn_from_step(
    store: dict[str, Any],
    *,
    ev_before: dict[str, float],
    action: str,
    ev_after: dict[str, float],
    tick: int,
    ablate_revision: bool = False,
) -> None:
    """Ordinary experience: antecedent evidence --action--> consequent evidence."""
    if ablate_revision:
        return
    pc.learn_transition(
        store,
        tick=tick,
        antecedent=evidence_state(ev_before),
        action=action,
        consequent=evidence_state(ev_after),
    )


def revise_distal_from_field_experience(
    store: dict[str, Any],
    *,
    field_level: float,
    informative: bool,
    tick: int,
    n_boost: int = 20,
    ablate_revision: bool = False,
    evidence_changed: bool = True,
) -> None:
    """Ordinary regime-conditioned distal learning from new accessible field evidence.

    Requires evidence_changed (no tick-only revision). No WORLD_CHANGED token.
    High field (>=0.5): experience B3->restored-like, A3->depleted.
    Mid/low without change: no-op.
    Non-informative worlds: no distal remapping (decorrelated control).
    """
    if ablate_revision or not evidence_changed:
        return
    if not informative:
        return
    if field_level < 0.5:
        # New evidence still low-regime: do not overwrite prior B->PLUS with low-field noise.
        return
    distal = distal_from_field(field_level, informative=True)
    for i in range(n_boost):
        t = tick + i
        # Ordinary experience in high-field regime: B terminal restored-like.
        pc.learn_transition(store, tick=t, antecedent=pci.S4(), action="B3", consequent=pci.B_PLUS())


def snapshot_predictions(store: dict[str, Any], goals: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for label, seq in (("A", ["A1", "A2", "A3"]), ("B", ["B1", "B2", "B3"])):
        comp = pci.compose_action_distal(store, seq)
        pred = comp.get("predicted_distal")
        ev = pci.evaluate_distal(pci.S0(), pred, goals)
        out[label] = {
            "status": comp.get("status"),
            "predicted_distal": pred,
            "ordinary_value": ev.get("ordinary_value"),
        }
    return out


def action_probe(store: dict[str, Any], goals: dict[str, Any], *, seed: int, use_distal: bool = True) -> dict[str, Any]:
    logits = pci.action_logits(store=store, goals=goals, use_distal=use_distal)
    probs = logits.get("probs") or {}
    return {
        "probs": probs,
        "P_A": float(probs.get("A1", 0.0)),
        "P_B": float(probs.get("B1", 0.0)),
        "P_WAIT": float(probs.get("WAIT", 0.0)),
        "logits": {a: (logits.get("actions") or {}).get(a, {}).get("logit") for a in probs},
        "distal_values": {a: (logits.get("actions") or {}).get(a, {}).get("distal_value") for a in probs},
        "use_distal": use_distal,
    }


def run_wait_trajectory(
    *,
    store: dict[str, Any],
    world: dict[str, Any],
    goals: dict[str, Any],
    n_wait: int = 5,
    ablate_revision: bool = False,
    learn_field_distal: bool = True,
    seed: int = 0,
) -> dict[str, Any]:
    """Execute n_wait WAIT steps with continuing physics; optional online revision."""
    timeline = []
    pred0 = snapshot_predictions(store, goals)
    act0 = action_probe(store, goals, seed=seed)
    w = deepcopy(world)
    for i in range(n_wait):
        ev_b = accessible_evidence(w)
        w2 = step_physics(w, "WAIT")
        ev_a = accessible_evidence(w2)
        online_learn_from_step(
            store, ev_before=ev_b, action="WAIT", ev_after=ev_a,
            tick=10000 + i, ablate_revision=ablate_revision,
        )
        if learn_field_distal:
            revise_distal_from_field_experience(
                store,
                field_level=float(w2["field_level"]),
                informative=bool(w2.get("informative", True)),
                tick=20000 + i * 10,
                ablate_revision=ablate_revision,
                evidence_changed=bool(
                    abs(float(ev_a.get("field_signal", 0)) - float(ev_b.get("field_signal", 0))) > 1e-9
                ),
            )
        timeline.append({
            "step": i,
            "action": "WAIT",
            "field_before": float(w["field_level"]),
            "field_after": float(w2["field_level"]),
            "body_energy_before": float(w["body"]["energy_signal"]),
            "body_energy_after": float(w2["body"]["energy_signal"]),
            "evidence_field": float(ev_a.get("field_signal", 0.0)),
            "state_changed": abs(float(w2["field_level"]) - float(w["field_level"])) > 1e-9
            or abs(float(w2["body"]["energy_signal"]) - float(w["body"]["energy_signal"])) > 1e-9,
            "evidence_changed": abs(float(ev_a.get("field_signal", 0)) - float(ev_b.get("field_signal", 0))) > 1e-9,
        })
        w = w2
    pred1 = snapshot_predictions(store, goals)
    act1 = action_probe(store, goals, seed=seed + 1)
    return {
        "timeline": timeline,
        "prediction_before": pred0,
        "prediction_after": pred1,
        "action_before": act0,
        "action_after": act1,
        "world_final": {
            "field_level": w["field_level"],
            "body": w["body"],
            "tick_researcher": w["tick_researcher"],
        },
        "field_delta": float(w["field_level"]) - float(world["field_level"]),
        "body_energy_delta": float(w["body"]["energy_signal"]) - float(world["body"]["energy_signal"]),
    }
