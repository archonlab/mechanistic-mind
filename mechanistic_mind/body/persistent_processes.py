"""Update 4.20 — Persistent generic body processes (no semantic physiology labels).

Variables are researcher-named only. Cognition receives bounded numeric fragments.
"""
from __future__ import annotations

from typing import Any


PROCESS_KEYS = ("internal_a", "internal_b", "load_c", "exchange_d")


def default_process_config() -> dict[str, Any]:
    return {
        "enabled": True,
        # Accumulation of internal_a toward 1.0 at base_rate, modulated by env.
        "base_rate": 0.035,
        "env_rate_gain": 0.08,  # added from env modulator in [0,1]
        "action_relief": {
            # action prefix -> delta applied to process key
            "EMIT": {"internal_a": -0.22},
            "WAIT": {},
        },
        "passive_drift": {
            "internal_b": 0.01,
            "load_c": 0.006,
            "exchange_d": -0.004,
        },
        "body_coupling": {
            # high internal_a weakly raises fatigue via ordinary deltas
            "internal_a": {"fatigue_delta": 0.015},
        },
        "development": {
            "enabled": False,
            "action_cost_drift_per_tick": 0.0,
            "rate_drift_per_tick": 0.0,
        },
        "regime": "REGIME_A",  # researcher only
        "regime_rates": {
            "REGIME_A": 0.035,  # ~ every ~20 ticks to high if no relief
            "REGIME_B": 0.09,   # faster
            "REGIME_RANDOM": 0.05,
        },
        "sensory_keys": list(PROCESS_KEYS),  # which fragments agent may sense
    }


def ensure_process_state(loads: dict[str, float] | None) -> dict[str, float]:
    out = {str(k): float(v) for k, v in dict(loads or {}).items()}
    for key in PROCESS_KEYS:
        out.setdefault(key, 0.25 if key == "internal_a" else 0.4)
    return out


def env_modulator(env_sample: dict[str, float] | None) -> float:
    """Map local ambient fragments to a unit-ish rate modulator (no labels)."""
    if not isinstance(env_sample, dict) or not env_sample:
        return 0.0
    # Use a few ambient channels if present; otherwise 0.
    temp = float(env_sample.get("temperature", 0.5))
    chem = float(env_sample.get("chemical_1", 0.4))
    vib = float(env_sample.get("vibration", 0.2))
    return max(0.0, min(1.0, 0.45 * temp + 0.35 * chem + 0.20 * vib))


def advance_persistent_processes(
    loads: dict[str, float],
    *,
    config: dict[str, Any],
    action_kind: str,
    env_sample: dict[str, float] | None,
    days: float = 1.0,
) -> tuple[dict[str, float], dict[str, float], dict[str, Any]]:
    """Return (new_loads, body_objective_deltas, receipt)."""
    cfg = config or {}
    if not cfg.get("enabled", True):
        return dict(loads or {}), {}, {"enabled": False}
    state = ensure_process_state(loads)
    regime = str(cfg.get("regime") or "REGIME_A")
    base = float((cfg.get("regime_rates") or {}).get(regime, cfg.get("base_rate", 0.035)))
    mod = env_modulator(env_sample)
    rate = (base + float(cfg.get("env_rate_gain", 0.0)) * mod) * float(days)
    # developmental drift of rate
    dev = cfg.get("development") or {}
    if dev.get("enabled"):
        rate += float(dev.get("rate_drift_per_tick", 0.0)) * float(days)
        rate = max(0.0, rate)

    before = dict(state)
    state["internal_a"] = max(0.0, min(1.0, float(state["internal_a"]) + rate))
    for key, drift in (cfg.get("passive_drift") or {}).items():
        state[str(key)] = max(0.0, min(1.0, float(state.get(key, 0.0)) + float(drift) * float(days)))

    relief = (cfg.get("action_relief") or {}).get(str(action_kind).split(":")[0], {})
    # also allow full action kind match
    if not relief:
        relief = (cfg.get("action_relief") or {}).get(str(action_kind), {})
    for key, delta in dict(relief or {}).items():
        state[str(key)] = max(0.0, min(1.0, float(state.get(key, 0.0)) + float(delta)))

    objective: dict[str, float] = {}
    for key, mapping in (cfg.get("body_coupling") or {}).items():
        level = float(state.get(key, 0.0))
        if not isinstance(mapping, dict):
            continue
        for body_key, scale in mapping.items():
            # couple only when elevated
            drive = max(0.0, level - 0.55)
            objective[str(body_key)] = objective.get(str(body_key), 0.0) + float(scale) * drive

    receipt = {
        "enabled": True,
        "regime": regime,  # Observer only — must not be copied into cognition
        "rate": rate,
        "env_modulator": mod,
        "before": before,
        "after": dict(state),
        "action": action_kind,
        "objective_deltas": dict(objective),
    }
    return state, objective, receipt


def sensory_fragments(loads: dict[str, float], *, config: dict[str, Any] | None = None) -> dict[str, float]:
    """Bounded agent-facing fragments — generic keys only, no regime/need labels."""
    cfg = config or default_process_config()
    keys = list(cfg.get("sensory_keys") or PROCESS_KEYS)
    state = ensure_process_state(loads)
    return {f"{k}_signal": round(float(state.get(k, 0.0)), 5) for k in keys}


def observer_body_truth(loads: dict[str, float], receipt: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "process_state": ensure_process_state(loads),
        "last_receipt": {
            k: v
            for k, v in dict(receipt or {}).items()
            if k in {"enabled", "regime", "rate", "env_modulator", "action", "before", "after", "objective_deltas"}
        },
    }
