"""Update 4.10 — Bounded temporal contingency acquisition (valence-neutral).

Learns: context + action → later ordinary observable change at lag L.
Does NOT learn value, reward, preference, or what should be done.
Default: disabled via SensorimotorConfig.temporal_contingency_enabled.
"""
from __future__ import annotations

from copy import deepcopy
from math import log1p
from typing import Any


DEFAULT_LAGS = (0, 1, 2, 3)
MAX_PENDING = 32
MAX_CONTINGENCIES = 256
MIN_SUPPORT_KNOWN = 3.0


def _numeric(mapping: Any) -> dict[str, float]:
    if not isinstance(mapping, dict):
        return {}
    out: dict[str, float] = {}
    for k, v in mapping.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out[str(k)] = float(v)
    return out


def intero_of(obs: dict[str, Any]) -> dict[str, float]:
    return _numeric(obs.get("interoception") if isinstance(obs, dict) else None)


def delta_map(before: dict[str, float], after: dict[str, float]) -> dict[str, float]:
    keys = set(before) | set(after)
    return {k: float(after.get(k, 0.0)) - float(before.get(k, 0.0)) for k in keys}


def quantize_signature(delta: dict[str, float], *, step: float = 0.02) -> str:
    """Nonsemantic coarse signature for indexing (not value)."""
    parts = []
    for k in sorted(delta):
        v = float(delta[k])
        if abs(v) < step * 0.5:
            continue
        q = int(round(v / step))
        if q != 0:
            parts.append(f"{k}:{q:+d}")
    return "|".join(parts) if parts else "NULL"


def consequence_from_observations(
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, Any]:
    b = intero_of(before)
    a = intero_of(after)
    body_delta = delta_map(b, a)
    # perceptual cheap flag: visible id set change
    def _vis(obs: dict[str, Any]) -> frozenset[str]:
        ids = []
        for item in obs.get("visible_objects") or ():
            if isinstance(item, dict) and item.get("id"):
                ids.append(str(item["id"]))
        return frozenset(ids)

    visual_changed = _vis(before) != _vis(after)
    return {
        "body_delta": body_delta,
        "signature": quantize_signature(body_delta),
        "visual_changed": visual_changed,
        "magnitude": float(sum(abs(v) for v in body_delta.values())),
    }


def temporal_cue_bucket(cue: dict[str, Any] | None) -> str:
    """Context key for temporal contingencies.

    Reuses ordinary cue parts but **omits body_bands**, which change after
    interoceptive consequences and otherwise fragment keys so support never
    accumulates (Update 4.10 engine finding). Visible + perceptual features only.
    """
    if not isinstance(cue, dict):
        return "*"
    visible = tuple(item[0] for item in (cue.get("visible") or ())[:4])
    percept = tuple(cue.get("perceptual_features") or ())[:12]
    return repr((visible, percept))


def normalize_action(action: str) -> str:
    """Coarse action token for contingency keys.

    Absolute MOVE:x,y destinations otherwise never re-occur, so support cannot
    accumulate across a trajectory. MOVE collapses to MOVE; USE keeps object id.
    """
    a = str(action or "")
    if a.startswith("MOVE:"):
        return "MOVE"
    if a.startswith("PUSH:"):
        return "PUSH:" + a.split(":", 2)[1] if ":" in a else "PUSH"
    return a



# Update 4.11 — cognition-visible coarse body state (L/M/H). Only signals already
# present in ordinary interoception / context_cue body_bands. Avoids full-band
# fragmentation by restricting to energy/hydration/fatigue.
COARSE_STATE_SIGNALS = ("energy_signal", "hydration_signal", "fatigue_signal")


def _band(val: float) -> str:
    v = float(val)
    if v < 1.0 / 3.0:
        return "L"
    if v < 2.0 / 3.0:
        return "M"
    return "H"


def coarse_body_state_key(
    observation_or_signals: dict[str, Any] | None,
    *,
    from_interoception: bool = True,
) -> str:
    """Bounded state key from cognition-available body signals only.

    Accepts either an observation dict (reads interoception) or a flat signal map.
    """
    if not isinstance(observation_or_signals, dict):
        return "S?"
    body: dict[str, float]
    if from_interoception and "interoception" in observation_or_signals:
        body = intero_of(observation_or_signals)
    elif any(k.endswith("_signal") for k in observation_or_signals):
        body = _numeric(observation_or_signals)
    else:
        body = intero_of(observation_or_signals) or _numeric(observation_or_signals)
    parts = []
    for k in COARSE_STATE_SIGNALS:
        if k in body:
            parts.append(f"{k[0]}{_band(body[k])}")  # eL / hM / fH compact
        else:
            parts.append(f"{k[0]}?")
    return "S:" + "".join(parts)


def predicted_organism_state(
    current_signals: dict[str, float],
    mean_body_delta: dict[str, float] | None,
) -> dict[str, float] | None:
    """current + cumulative delta → predicted state. None if delta missing."""
    if not isinstance(mean_body_delta, dict) or not mean_body_delta:
        return None
    cur = _numeric(current_signals)
    out = dict(cur)
    for k, v in mean_body_delta.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out[str(k)] = float(cur.get(str(k), 0.0)) + float(v)
    return out


def temporal_key(bucket: str, action: str, lag: int, state_key: str | None = None) -> str:
    act = normalize_action(str(action)) if action else ""
    sk = str(state_key) if state_key else ""
    if sk:
        return f"TC||{bucket}||{sk}||{act}||L{int(lag)}"
    return f"TC||{bucket}||{act}||L{int(lag)}"



def empty_temporal_state() -> dict[str, Any]:
    return {
        "pending": [],
        "contingencies": {},
        "index": {},  # bucket -> [keys]
        "tick_counter": 0,
        "updates": 0,
        "last_diag": {},
    }


def ensure_temporal(store_dict: dict[str, Any]) -> dict[str, Any]:
    tc = store_dict.get("temporal_contingency")
    if not isinstance(tc, dict):
        tc = empty_temporal_state()
        store_dict["temporal_contingency"] = tc
    tc.setdefault("pending", [])
    tc.setdefault("contingencies", {})
    tc.setdefault("index", {})
    tc.setdefault("tick_counter", 0)
    tc.setdefault("updates", 0)
    return tc


def _ema(old: float, new: float, n: float) -> float:
    if n <= 1:
        return float(new)
    return (float(old) * (n - 1.0) + float(new)) / n


def _update_record(
    record: dict[str, Any],
    *,
    consequence: dict[str, Any],
    action_conditioning: bool,
) -> dict[str, Any]:
    support = float(record.get("support", 0.0)) + 1.0
    body = consequence["body_delta"]
    mean = dict(record.get("mean_body_delta") or {})
    for k, v in body.items():
        mean[k] = _ema(float(mean.get(k, 0.0)), float(v), support)
    # consistency: cosine-like agreement with running mean
    mag_m = sum(abs(x) for x in mean.values()) + 1e-9
    mag_b = sum(abs(x) for x in body.values()) + 1e-9
    dot = sum(float(mean.get(k, 0.0)) * float(body.get(k, 0.0)) for k in set(mean) | set(body))
    agree = max(0.0, min(1.0, (dot / (mag_m * mag_b) + 1.0) / 2.0))
    consistency = _ema(float(record.get("consistency", 0.5)), agree, support)
    contrad = 1.0 - agree
    contradiction = _ema(float(record.get("contradiction", 0.0)), contrad, support)
    # predictive confidence (NOT value)
    conf = min(
        1.0,
        consistency
        * min(1.0, log1p(support) / log1p(MIN_SUPPORT_KNOWN + 5.0))
        * (1.0 - 0.5 * contradiction),
    )
    if support < MIN_SUPPORT_KNOWN:
        status = "UNKNOWN"
        conf = 0.0
    elif contradiction > 0.55 and support >= MIN_SUPPORT_KNOWN:
        status = "WEAK"
        conf *= 0.5
    else:
        status = "KNOWN"
    record.update(
        {
            "support": support,
            "mean_body_delta": mean,
            "consistency": consistency,
            "contradiction": contradiction,
            "confidence": conf,
            "status": status,
            "last_signature": consequence["signature"],
            "last_magnitude": consequence["magnitude"],
            "observations": int(record.get("observations", 0)) + 1,
            "action_conditioning": bool(action_conditioning),
        }
    )
    return record


def open_pending(
    tc: dict[str, Any],
    *,
    action: str,
    bucket: str,
    observation: dict[str, Any],
    lags: tuple[int, ...] = DEFAULT_LAGS,
    action_conditioning: bool = True,
    context_conditioning: bool = True,
) -> None:
    pending = list(tc.get("pending") or [])
    state_key = coarse_body_state_key(observation if isinstance(observation, dict) else {})
    pending.append(
        {
            "action": (normalize_action(str(action)) if action_conditioning else ""),
            "bucket": str(bucket) if context_conditioning else "*",
            "state_key": state_key,
            "obs_before": deepcopy(observation),
            "age": -1,  # first settle_pending increments to 0
            "lags": tuple(int(x) for x in lags),
            "action_conditioning": bool(action_conditioning),
            "context_conditioning": bool(context_conditioning),
        }
    )
    tc["pending"] = pending[-MAX_PENDING:]


def settle_pending(
    tc: dict[str, Any],
    *,
    observation: dict[str, Any],
    lags: tuple[int, ...] = DEFAULT_LAGS,
) -> dict[str, Any]:
    """Advance pending traces by one observation; update contingencies at matching lags."""
    updated_keys: list[str] = []
    still: list[dict[str, Any]] = []
    max_lag = max(lags) if lags else 0
    for trace in list(tc.get("pending") or []):
        age = int(trace.get("age", -1)) + 1
        trace["age"] = age
        if age in set(trace.get("lags") or lags):
            cons = consequence_from_observations(trace["obs_before"], observation)
            sk = str(trace.get("state_key") or coarse_body_state_key(trace.get("obs_before") or {}))
            key = temporal_key(str(trace["bucket"]), str(trace["action"]), age, state_key=sk)
            rec = tc["contingencies"].get(key)
            if rec is None:
                rec = {
                    "key": key,
                    "bucket": trace["bucket"],
                    "state_key": sk,
                    "action": trace["action"],
                    "lag": age,
                    "support": 0.0,
                    "mean_body_delta": {},
                    "consistency": 0.5,
                    "contradiction": 0.0,
                    "confidence": 0.0,
                    "status": "UNKNOWN",
                    "observations": 0,
                    "baseline_wait_magnitude": None,
                    "action_specific_strength": 0.0,
                }
            _update_record(
                rec,
                consequence=cons,
                action_conditioning=bool(trace.get("action_conditioning", True)),
            )
            # Update 4.14: shadow multi-consequence groups (does not alter EMA / policy)
            try:
                from mechanistic_mind.research.multiple_consequences import update_multi_consequence
                update_multi_consequence(tc, key, cons.get("body_delta") or {})
            except Exception:
                pass
            # Background: compare to WAIT same bucket/lag if present
            wait_key = temporal_key(str(trace["bucket"]), "WAIT", age, state_key=sk)
            wait_rec = tc["contingencies"].get(wait_key)
            if wait_rec is None:
                # fallback: any WAIT same bucket/lag
                for wk, wr in (tc.get("contingencies") or {}).items():
                    if (
                        isinstance(wr, dict)
                        and str(wr.get("action")) == "WAIT"
                        and int(wr.get("lag", -1)) == int(age)
                        and str(wr.get("bucket")) == str(trace["bucket"])
                    ):
                        wait_rec = wr
                        break
            if isinstance(wait_rec, dict) and float(wait_rec.get("support", 0)) >= 1:
                wmag = float(wait_rec.get("last_magnitude") or 0.0)
                # running baseline
                prev = wait_rec.get("mean_body_delta") or {}
                wmag = float(sum(abs(v) for v in prev.values()))
                rec["baseline_wait_magnitude"] = wmag
                amag = float(sum(abs(v) for v in (rec.get("mean_body_delta") or {}).values()))
                # action-specific strength: excess magnitude vs WAIT (not value)
                strength = max(0.0, amag - wmag)
                rec["action_specific_strength"] = strength
                if wmag > 1e-6 and amag <= wmag * 1.05 and float(rec.get("support", 0)) >= MIN_SUPPORT_KNOWN:
                    # consequence equally under WAIT → weaken action-specificity
                    rec["confidence"] = float(rec["confidence"]) * 0.35
                    if strength < 1e-4:
                        rec["status"] = "UNKNOWN"
                        rec["confidence"] = 0.0
            tc["contingencies"][key] = rec
            idx = tc["index"].setdefault(str(trace["bucket"]), [])
            if key not in idx:
                idx.append(key)
                tc["index"][str(trace["bucket"])] = idx[-64:]
            updated_keys.append(key)
        if age < max_lag:
            still.append(trace)
    tc["pending"] = still[-MAX_PENDING:]
    # prune contingencies
    cont = tc["contingencies"]
    if len(cont) > MAX_CONTINGENCIES:
        ranked = sorted(
            cont.items(),
            key=lambda kv: (float(kv[1].get("support", 0.0)), float(kv[1].get("confidence", 0.0))),
        )
        for k, _ in ranked[: len(cont) - MAX_CONTINGENCIES]:
            cont.pop(k, None)
    tc["updates"] = int(tc.get("updates", 0)) + 1
    tc["tick_counter"] = int(tc.get("tick_counter", 0)) + 1
    diag = {"updated_keys": updated_keys[:12], "pending": len(tc["pending"]), "n": len(tc["contingencies"])}
    tc["last_diag"] = diag
    return diag


def retrieve_temporal(
    tc: dict[str, Any],
    *,
    bucket: str,
    available_actions: set[str],
    action_conditioning: bool = True,
    context_conditioning: bool = True,
    min_support: float = MIN_SUPPORT_KNOWN,
    state_key: str | None = None,
    state_conditioning: bool = True,
) -> list[dict[str, Any]]:
    """Eligible temporal contingencies for decision-time prediction (not scores).

    Update 4.11: prefer records matching coarse cognition-visible state_key;
    fall back to same context/action/lag with other/legacy state (PARTIAL match).
    """
    b = str(bucket) if context_conditioning else "*"
    keys = list((tc.get("index") or {}).get(b, ()))
    if not keys:
        keys = [
            k
            for k in list((tc.get("contingencies") or {}).keys())[:120]
            if k.startswith(f"TC||{b}||") or (not context_conditioning)
        ]
    # Always scan contingencies for this bucket to catch state-keyed records
    for k in list((tc.get("contingencies") or {}).keys()):
        if k.startswith(f"TC||{b}||") and k not in keys:
            keys.append(k)
    hits = []
    want_state = str(state_key) if (state_conditioning and state_key) else ""
    for key in keys:
        rec = (tc.get("contingencies") or {}).get(key)
        if not isinstance(rec, dict):
            continue
        action = str(rec.get("action") or "")
        if action_conditioning:
            if action:
                if action not in available_actions:
                    if action == "MOVE":
                        if not any(str(a).startswith("MOVE:") for a in available_actions):
                            continue
                    elif action.startswith("USE:"):
                        if action not in available_actions:
                            continue
                    elif action == "WAIT":
                        if "WAIT" not in available_actions:
                            continue
                    else:
                        continue
        rec_state = str(rec.get("state_key") or "")
        state_match = "NONE"
        if not want_state:
            state_match = "UNCONDITIONAL"
        elif rec_state == want_state:
            state_match = "EXACT"
        elif not rec_state:
            state_match = "LEGACY"
        else:
            state_match = "OTHER_STATE"
        if state_conditioning and want_state and state_match == "OTHER_STATE":
            # keep as fallback but mark; still eligible
            pass
        row = deepcopy(rec)
        row["_state_match"] = state_match
        hits.append(row)
    # Prefer exact state, then legacy, then other; within that confidence/support/lag
    rank = {"EXACT": 0, "LEGACY": 1, "UNCONDITIONAL": 1, "OTHER_STATE": 2, "NONE": 3}
    hits.sort(
        key=lambda r: (
            rank.get(str(r.get("_state_match")), 9),
            -float(r.get("confidence", 0.0)),
            -float(r.get("support", 0.0)),
            int(r.get("lag", 99)),
        )
    )
    return hits[:24]


def predictions_by_lag_for_action(
    hits: list[dict[str, Any]],
    action: str,
    *,
    lags: tuple[int, ...] = (1, 2, 3),
) -> dict[int, dict[str, Any] | None]:
    """One best record per lag for an action (state preference already in hits order)."""
    want = normalize_action(str(action))
    out: dict[int, dict[str, Any] | None] = {int(L): None for L in lags}
    for L in lags:
        cand = [
            h
            for h in hits
            if str(h.get("action")) == want and int(h.get("lag", -1)) == int(L)
        ]
        if not cand:
            out[int(L)] = None
            continue
        # Prefer EXACT state match already sorted; among same lag take first
        known = [h for h in cand if h.get("status") == "KNOWN"]
        pick = (known or cand)[0]
        out[int(L)] = pick
    return out


def build_prospective_trajectory(
    *,
    action: str,
    current_signals: dict[str, float],
    hits: list[dict[str, Any]],
    lags: tuple[int, ...] = (1, 2, 3),
) -> dict[str, Any]:
    """Bounded prospective organism-state trajectory for one candidate action.

    Does NOT aggregate horizons into one value. Does NOT add habit value.
    """
    by_lag = predictions_by_lag_for_action(hits, action, lags=lags)
    horizons = {}
    for L, rec in by_lag.items():
        if rec is None:
            horizons[int(L)] = {
                "status": "UNKNOWN",
                "support": 0.0,
                "confidence": 0.0,
                "mean_body_delta": None,
                "predicted_state": None,
                "state_match": None,
            }
            continue
        delta = rec.get("mean_body_delta") or {}
        st = predicted_organism_state(current_signals, delta if delta else None)
        horizons[int(L)] = {
            "status": rec.get("status") or "UNKNOWN",
            "support": float(rec.get("support") or 0.0),
            "confidence": float(rec.get("confidence") or 0.0),
            "contradiction": float(rec.get("contradiction") or 0.0),
            "mean_body_delta": delta,
            "predicted_state": st,
            "state_match": rec.get("_state_match"),
            "key": rec.get("key"),
            "record_state_key": rec.get("state_key"),
        }
    return {
        "action": normalize_action(str(action)),
        "horizons": horizons,
        "note": "predicted_state = current_signals + cumulative_delta; horizons separate",
    }


def intervention_difference(
    traj_a: dict[str, Any],
    traj_wait: dict[str, Any],
    *,
    lags: tuple[int, ...] = (1, 2, 3),
) -> dict[int, dict[str, Any]]:
    """A − WAIT predicted-state difference. Only when both sides known with states."""
    out: dict[int, dict[str, Any]] = {}
    ha = (traj_a or {}).get("horizons") or {}
    hw = (traj_wait or {}).get("horizons") or {}
    for L in lags:
        a = ha.get(int(L)) or {}
        w = hw.get(int(L)) or {}
        sa = a.get("predicted_state")
        sw = w.get("predicted_state")
        if (
            a.get("status") not in ("KNOWN", "WEAK")
            or w.get("status") not in ("KNOWN", "WEAK")
            or not isinstance(sa, dict)
            or not isinstance(sw, dict)
        ):
            out[int(L)] = {"status": "UNKNOWN", "delta": None, "reason": "MISSING_SIDE"}
            continue
        keys = set(sa) | set(sw)
        out[int(L)] = {
            "status": "KNOWN",
            "delta": {k: float(sa.get(k, 0.0)) - float(sw.get(k, 0.0)) for k in keys},
            "reason": "A_MINUS_WAIT_PREDICTED_STATE",
            "not_value": True,
        }
    return out



def best_prediction_for_action(
    hits: list[dict[str, Any]],
    action: str,
) -> dict[str, Any] | None:
    want = normalize_action(str(action))
    cand = [h for h in hits if str(h.get("action")) == want]
    if not cand:
        return None
    # Prefer lowest lag with KNOWN status
    known = [h for h in cand if h.get("status") == "KNOWN"]
    pool = known or cand
    return min(pool, key=lambda h: (0 if h.get("status") == "KNOWN" else 1, int(h.get("lag", 99))))
