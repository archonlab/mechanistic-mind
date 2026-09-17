"""Update 4.14 — Bounded multiple acquired consequences (shadow / researcher path).

Keeps legacy single-EMA untouched. Modes are experience-grounded body-delta groups.
No value, ranking, probability-as-calibrated-P, surprise, or policy coupling.

Minimum representation: online consequence groups with EMA center + support + MAD spread.
Individual unlimited history is NOT retained.
"""
from __future__ import annotations

from typing import Any

from mechanistic_mind.psyche.temporal_contingency import (
    COARSE_STATE_SIGNALS,
    MIN_SUPPORT_KNOWN,
    predicted_organism_state,
)

# Bounds (explicit)
MAX_MODES_PER_KEY = 4
# Separation floor on L1(body delta over cognition-visible signals).
# Units: absolute signal-delta L1. Architecture-general floor, not an X/Y label.
# Must exceed ordinary unimodal numerical jitter; must not reference fixture labels.
SEP_L1_FLOOR = 0.006
# Merge radius = max(SEP_L1_FLOOR, SEP_SPREAD_MULT * mode_MAD)
SEP_SPREAD_MULT = 3.0
# Match radius for violation "compatible with supported consequence"
MATCH_L1 = 0.006


def _num(d: Any) -> dict[str, float]:
    if not isinstance(d, dict):
        return {}
    return {
        str(k): float(v)
        for k, v in d.items()
        if isinstance(v, (int, float)) and not isinstance(v, bool)
    }


def delta_l1(a: dict[str, float] | None, b: dict[str, float] | None, keys=COARSE_STATE_SIGNALS) -> float:
    aa, bb = _num(a), _num(b)
    return float(sum(abs(float(aa.get(k, 0.0)) - float(bb.get(k, 0.0))) for k in keys))


def ensure_multi(tc: dict[str, Any]) -> dict[str, Any]:
    mc = tc.get("multi_consequences")
    if not isinstance(mc, dict):
        mc = {"by_key": {}, "updates": 0, "config": semantics_config()}
        tc["multi_consequences"] = mc
    mc.setdefault("by_key", {})
    mc.setdefault("updates", 0)
    mc.setdefault("config", semantics_config())
    return mc


def semantics_config() -> dict[str, Any]:
    return {
        "MAX_MODES_PER_KEY": MAX_MODES_PER_KEY,
        "SEP_L1_FLOOR": SEP_L1_FLOOR,
        "SEP_SPREAD_MULT": SEP_SPREAD_MULT,
        "MATCH_L1": MATCH_L1,
        "MIN_SUPPORT_KNOWN": MIN_SUPPORT_KNOWN,
        "distance": "L1 over COARSE_STATE_SIGNALS body deltas",
        "no_value_ranking": True,
        "no_calibrated_probability": True,
        "rationale": (
            "EMA discards samples needed for mode separation; bounded online groups "
            "are the minimum sufficient statistic retaining multiple centers + support + MAD."
        ),
    }


def _merge_radius(mode: dict[str, Any]) -> float:
    mad = float(mode.get("spread_mad") or 0.0)
    return max(float(SEP_L1_FLOOR), float(SEP_SPREAD_MULT) * mad)


def _new_mode(body: dict[str, float], mode_id: str) -> dict[str, Any]:
    return {
        "id": mode_id,
        "center_delta": dict(body),
        "support": 1.0,
        "spread_mad": 0.0,  # mean abs deviation from center (L1/n_dims proxy updated online)
        "updates": 1,
        "provenance": "acquired",
    }


def update_multi_consequence(tc: dict[str, Any], key: str, body_delta: dict[str, float]) -> dict[str, Any]:
    """Assign observation to nearest mode or spawn/replace under capacity. Shadow only."""
    mc = ensure_multi(tc)
    body = {k: float((_num(body_delta)).get(k, 0.0)) for k in COARSE_STATE_SIGNALS}
    entry = mc["by_key"].setdefault(str(key), {"modes": [], "next_id": 1, "n_obs": 0})
    modes: list[dict[str, Any]] = list(entry.get("modes") or [])
    entry["n_obs"] = int(entry.get("n_obs") or 0) + 1

    best_i = None
    best_d = None
    for i, m in enumerate(modes):
        d = delta_l1(body, m.get("center_delta"))
        if best_d is None or d < best_d:
            best_d = d
            best_i = i

    if best_i is not None and best_d is not None and best_d <= _merge_radius(modes[best_i]):
        m = modes[best_i]
        n = float(m.get("support") or 0.0) + 1.0
        center = dict(m.get("center_delta") or {})
        for k in COARSE_STATE_SIGNALS:
            old = float(center.get(k, 0.0))
            center[k] = (old * (n - 1.0) + float(body.get(k, 0.0))) / n
        # online MAD of L1 distance to previous center (approx)
        prev_mad = float(m.get("spread_mad") or 0.0)
        mad = (prev_mad * (n - 1.0) + float(best_d)) / n
        m.update({"center_delta": center, "support": n, "spread_mad": mad, "updates": int(m.get("updates") or 0) + 1})
        modes[best_i] = m
    else:
        mid = f"C{int(entry.get('next_id') or 1)}"
        entry["next_id"] = int(entry.get("next_id") or 1) + 1
        if len(modes) < MAX_MODES_PER_KEY:
            modes.append(_new_mode(body, mid))
        else:
            # bounded: replace lowest-support mode (epistemic capacity, not value preference for rare)
            victim = min(range(len(modes)), key=lambda i: float(modes[i].get("support") or 0.0))
            modes[victim] = _new_mode(body, mid)

    entry["modes"] = modes
    mc["by_key"][str(key)] = entry
    mc["updates"] = int(mc.get("updates") or 0) + 1
    return entry


def list_modes(tc: dict[str, Any], key: str) -> list[dict[str, Any]]:
    mc = ensure_multi(tc)
    entry = (mc.get("by_key") or {}).get(str(key)) or {}
    return list(entry.get("modes") or [])


def supported_modes(tc: dict[str, Any], key: str, *, min_support: float = MIN_SUPPORT_KNOWN) -> list[dict[str, Any]]:
    out = []
    for m in list_modes(tc, key):
        if float(m.get("support") or 0.0) >= float(min_support):
            out.append(m)
    # deterministic order by id — NOT by support (avoid frequency→ranking presentation bias in default order)
    # Actually for display, sorting by id is fine; support shown separately without ranking for policy
    return sorted(out, key=lambda m: str(m.get("id")))


def prospective_consequences(
    *,
    tc: dict[str, Any],
    key: str,
    current_signals: dict[str, float],
    min_support: float = MIN_SUPPORT_KNOWN,
) -> dict[str, Any]:
    modes = supported_modes(tc, key, min_support=min_support)
    if not modes:
        raw = list_modes(tc, key)
        return {
            "status": "UNKNOWN",
            "n_supported": 0,
            "n_raw_modes": len(raw),
            "consequences": [],
            "reason": "NO_SUPPORTED_CONSEQUENCE" if not raw else "INSUFFICIENT_SUPPORT",
        }
    cons = []
    for m in modes:
        delta = m.get("center_delta") or {}
        cons.append(
            {
                "id": m.get("id"),
                "support": float(m.get("support") or 0.0),
                "spread_mad": float(m.get("spread_mad") or 0.0),
                "mean_body_delta": delta,
                "predicted_state": predicted_organism_state(current_signals, delta),
                "provenance": m.get("provenance") or "acquired",
                "status": "KNOWN" if float(m.get("support") or 0) >= MIN_SUPPORT_KNOWN else "UNKNOWN",
            }
        )
    status = "SINGLE" if len(cons) == 1 else "MULTIPLE"
    return {"status": status, "n_supported": len(cons), "n_raw_modes": len(list_modes(tc, key)), "consequences": cons}


def classify_realization_vs_modes(
    *,
    realized_delta: dict[str, float] | None = None,
    realized_state: dict[str, float] | None = None,
    current_signals: dict[str, float] | None = None,
    consequences: list[dict[str, Any]],
    match_l1: float = MATCH_L1,
) -> dict[str, Any]:
    """Researcher diagnostic for 4.13×4.14. No surprise variable."""
    if not consequences:
        return {"status": "NO_PREDICTIVE_BASELINE", "matches": [], "distances": {}}
    dists = {}
    matches = []
    for c in consequences:
        if realized_delta is not None:
            d = delta_l1(realized_delta, c.get("mean_body_delta"))
        else:
            d = delta_l1(realized_state, c.get("predicted_state"))
        dists[str(c.get("id"))] = d
        if d <= float(match_l1):
            matches.append(c.get("id"))
    if matches:
        return {"status": "MATCHES_SUPPORTED_CONSEQUENCE", "matches": matches, "distances": dists}
    return {"status": "VIOLATES_SUPPORTED_CONSEQUENCES", "matches": [], "distances": dists}


def memory_stats(tc: dict[str, Any]) -> dict[str, Any]:
    mc = ensure_multi(tc)
    by = mc.get("by_key") or {}
    n_modes = sum(len((e or {}).get("modes") or []) for e in by.values())
    return {
        "n_keys": len(by),
        "n_modes_total": n_modes,
        "max_modes_per_key": MAX_MODES_PER_KEY,
        "updates": mc.get("updates"),
        "approx_bytes_hint": n_modes * 200 + len(by) * 64,
    }
