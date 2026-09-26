"""Action-conditioned sensorimotor consequence model (generic ΔS learning).

Learns empirical regularities:
  (accessible sensory signature S_t, self motor signature M_t) → ΔS_(t→t+1)

No seeking / approach / reward / target / utility.
Observer GT never enters.
Selection influence, if any, is only via existing PSC MATCH support/reliability
when predictions are written into the prospective transition store — not via
valuing ΔS direction.
"""
from __future__ import annotations

import math
from typing import Any

# --- Agent-accessible channels used for consequence learning (documented) ---
# Chosen because they are (a) already in accessible_observation, (b) change with
# self motion / head / fields, (c) bounded in [0,1] or near it after observation
# normalization. Interoceptive body.* / internal.* omitted from the compact
# consequence vector to keep capacity focused on exteroceptive sensorimotor
# calibration (head→exo, loco→exo/FIELD). They remain in full PSC fragments.
# --- Sensory channel families (allowlist only; never auto-ingest ObservationReceipt) ---
# Provenance: mechanistic_mind/physical_system/observation.py accessible_observation keys.

FAMILY_VISUAL: tuple[str, ...] = (
    "exo_0", "exo_1", "exo_2",
    "surface_c0_0", "surface_c0_1", "surface_c0_2",
    "surface_c1_0", "surface_c1_1", "surface_c1_2",
    "surface_c2_0", "surface_c2_1", "surface_c2_2",
)
# Additive Phase 4 bins. Default family flag OFF so LEGACY SMC denominator stays 48.
FAMILY_SPATIAL_VISUAL: tuple[str, ...] = tuple(
    [f"spatial_exo_a{k}" for k in range(5)]
    + [f"spatial_surface_c{c}_a{k}" for c in range(3) for k in range(5)]
)
FAMILY_FIELD: tuple[str, ...] = ("local.FIELD_A", "local.FIELD_B")
FAMILY_VESTIBULAR: tuple[str, ...] = ("vest_0", "vest_1")
FAMILY_PROPRIOCEPTIVE: tuple[str, ...] = ("prop_neck_0", "prop_neck_1")
OSC_BAND_COUNT = 6
FAMILY_BILATERAL: tuple[str, ...] = tuple(
    f"osc_l_{i}" for i in range(OSC_BAND_COUNT)
) + tuple(
    f"osc_r_{i}" for i in range(OSC_BAND_COUNT)
)
# Local climate / flow at body site (agent-accessible scalars).
FAMILY_LOCAL_WORLD: tuple[str, ...] = (
    "local.T", "local.M0", "local.M1", "local.M2", "local.vx", "local.vy",
)
# Embodied body sensors (agent-accessible; not Observer GT).
FAMILY_BODY: tuple[str, ...] = (
    "body.B0", "body.B1", "body.B2", "body.T", "body.mech", "body.vx", "body.vy",
)
# Internal medium channel means (agent-owned; anonymous).
FAMILY_INTERNAL: tuple[str, ...] = (
    "internal.c0", "internal.c1", "internal.c2", "internal.c3", "internal.c4",
)

FAMILY_CHANNELS: dict[str, tuple[str, ...]] = {
    "visual": FAMILY_VISUAL,
    "spatial_visual": FAMILY_SPATIAL_VISUAL,
    "field": FAMILY_FIELD,
    "vestibular": FAMILY_VESTIBULAR,
    "proprioceptive": FAMILY_PROPRIOCEPTIVE,
    "bilateral": FAMILY_BILATERAL,
    "local_world": FAMILY_LOCAL_WORLD,
    "body": FAMILY_BODY,
    "internal": FAMILY_INTERNAL,
}

# Legacy aliases
OSC_SENSORY_CHANNELS = FAMILY_BILATERAL
BASE_SENSORY_CHANNELS: tuple[str, ...] = (
    FAMILY_VISUAL + FAMILY_FIELD + FAMILY_VESTIBULAR + FAMILY_PROPRIOCEPTIVE
)

# Default full embodied allowlist (all audited physical families).
SENSORY_CHANNELS: tuple[str, ...] = (
    FAMILY_VISUAL
    + FAMILY_FIELD
    + FAMILY_VESTIBULAR
    + FAMILY_PROPRIOCEPTIVE
    + FAMILY_BILATERAL
    + FAMILY_LOCAL_WORLD
    + FAMILY_BODY
    + FAMILY_INTERNAL
)

DEFAULT_FAMILY_ENABLED: dict[str, bool] = {name: True for name in FAMILY_CHANNELS}
DEFAULT_FAMILY_ENABLED["spatial_visual"] = False


def channels_from_families(enabled: dict[str, bool] | None = None) -> tuple[str, ...]:
    """Build allowlist from family flags (WITHHELD = family False)."""
    flags = dict(DEFAULT_FAMILY_ENABLED)
    if enabled:
        flags.update({str(k): bool(v) for k, v in enabled.items()})
    out: list[str] = []
    for name, chans in FAMILY_CHANNELS.items():
        if flags.get(name, True):
            out.extend(chans)
    return tuple(out)

SCHEMA = "mm.sensorimotor_consequence.v1"
DEFAULT_CAPACITY = 256
QUANT_BINS = 5
DELTA_CLIP = 1.0
SIM_THRESHOLD = 0.22  # mean L1 on quantized S; below → similar context
UNKNOWN = "UNKNOWN"
LOW_SUPPORT = "LOW_SUPPORT"
MATCH = "MATCH"

FORBIDDEN_FEATURE_TOKENS = (
    "ground_truth",
    "toroidal",
    "bearing",
    "approach",
    "withdrawal",
    "source_body",
    "agent_id",
    "OTHER_AGENT",
    "distance_to",
    "Analyzer",
)


def channels_for_store(store: dict[str, Any] | None = None) -> tuple[str, ...]:
    """Active SMC channel set for this store (family WITHHELD may omit bands)."""
    if isinstance(store, dict):
        cl = store.get("channel_list")
        if isinstance(cl, (list, tuple)) and cl:
            return tuple(str(x) for x in cl)
        fam = store.get("families")
        if isinstance(fam, dict):
            return channels_from_families(fam)
    return SENSORY_CHANNELS


def empty_store(
    *,
    capacity: int = DEFAULT_CAPACITY,
    enabled: bool = False,
    bilateral: bool = True,
    families: dict[str, bool] | None = None,
) -> dict[str, Any]:
    """Create SMC store. Family flags WITHHOLD sensory families from SMC/O′ only."""
    fam = dict(DEFAULT_FAMILY_ENABLED)
    if families:
        fam.update({str(k): bool(v) for k, v in families.items()})
    fam["bilateral"] = bool(bilateral) if "bilateral" not in (families or {}) else bool(fam.get("bilateral", True))
    # honor explicit bilateral kwarg unless families overrides
    if families is None:
        fam["bilateral"] = bool(bilateral)
    channels = list(channels_from_families(fam))
    return {
        "schema": SCHEMA,
        "enabled": bool(enabled),
        "capacity": int(capacity),
        "records": {},  # key -> record
        "ticks": 0,
        "updates": 0,
        "queries": 0,
        "matched_queries": 0,
        "unknown_queries": 0,
        "evictions": 0,
        "next_id": 1,
        "last_update": None,
        "last_query": None,
        "shuffle_motor_labels": False,  # experiment control
        "metrics_affect_cognition": False,
        "bilateral": bool(fam.get("bilateral", True)),
        "families": fam,
        "channel_list": channels,
    }


# Derived SMC indexes — reconstructible from ``records``. Not scientific identity.
_SMC_DERIVED_KEYS = ("_ix_motor", "_ix_loco", "_ix_gen", "_ix_built_gen")


def invalidate_indexes(store: dict[str, Any]) -> None:
    store["_ix_gen"] = int(store.get("_ix_gen") or 0) + 1
    for k in ("_ix_motor", "_ix_loco", "_ix_built_gen"):
        store.pop(k, None)


def _loco_from_motor_signature(ms: str) -> str | None:
    if not ms.startswith("L:"):
        return None
    return ms[2:].split("|", 1)[0]


def rebuild_indexes(store: dict[str, Any]) -> None:
    """motor_signature → record keys; locomotion → record keys (records insertion order)."""
    motor_ix: dict[str, list[str]] = {}
    loco_ix: dict[str, list[str]] = {}
    for key, row in (store.get("records") or {}).items():
        if not isinstance(row, dict):
            continue
        ms = str(row.get("motor_signature") or "")
        motor_ix.setdefault(ms, []).append(str(key))
        loco = _loco_from_motor_signature(ms)
        if loco is not None:
            loco_ix.setdefault(loco, []).append(str(key))
    store["_ix_motor"] = motor_ix
    store["_ix_loco"] = loco_ix
    store["_ix_built_gen"] = int(store.get("_ix_gen") or 0)


def ensure_indexes(store: dict[str, Any]) -> None:
    if store.get("_ix_built_gen") != int(store.get("_ix_gen") or 0) or "_ix_loco" not in store:
        rebuild_indexes(store)


def _index_drop_key(store: dict[str, Any], key: str, row: dict[str, Any] | None) -> None:
    if not row:
        return
    ensure_indexes(store)
    ms = str(row.get("motor_signature") or "")
    lst = (store.get("_ix_motor") or {}).get(ms)
    if lst:
        try:
            lst.remove(str(key))
        except ValueError:
            pass
        if not lst:
            (store.get("_ix_motor") or {}).pop(ms, None)
    loco = _loco_from_motor_signature(ms)
    if loco is not None:
        ll = (store.get("_ix_loco") or {}).get(loco)
        if ll:
            try:
                ll.remove(str(key))
            except ValueError:
                pass
            if not ll:
                (store.get("_ix_loco") or {}).pop(loco, None)


def _index_add_key(store: dict[str, Any], key: str, row: dict[str, Any]) -> None:
    ensure_indexes(store)
    sk = str(key)
    ms = str(row.get("motor_signature") or "")
    ml = store.setdefault("_ix_motor", {}).setdefault(ms, [])
    if sk not in ml:
        ml.append(sk)
    loco = _loco_from_motor_signature(ms)
    if loco is not None:
        ll = store.setdefault("_ix_loco", {}).setdefault(loco, [])
        if sk not in ll:
            ll.append(sk)


def iter_records_for_loco(store: dict[str, Any], loco: str):
    """Yield records whose motor_signature starts with ``L:{loco}|`` (index)."""
    ensure_indexes(store)
    records = store.get("records") or {}
    for key in (store.get("_ix_loco") or {}).get(str(loco) or "") or ():
        row = records.get(key)
        if isinstance(row, dict):
            yield row


def iter_records_for_motor(store: dict[str, Any], motor_signature: str):
    ensure_indexes(store)
    records = store.get("records") or {}
    for key in (store.get("_ix_motor") or {}).get(str(motor_signature) or "") or ():
        row = records.get(key)
        if isinstance(row, dict):
            yield row


def set_bilateral(store: dict[str, Any], bilateral: bool) -> None:
    """Hot-toggle bilateral participation in SMC (does not clear records or touch the receiver)."""
    fam = dict(store.get("families") or DEFAULT_FAMILY_ENABLED)
    fam["bilateral"] = bool(bilateral)
    store["families"] = fam
    store["bilateral"] = bool(bilateral)
    store["channel_list"] = list(channels_from_families(fam))


def set_families(store: dict[str, Any], **family_flags: bool) -> None:
    """WITHHOLD/enable sensory families without touching physical sensors or receipts."""
    fam = dict(store.get("families") or DEFAULT_FAMILY_ENABLED)
    for k, v in family_flags.items():
        if k in FAMILY_CHANNELS:
            fam[k] = bool(v)
    store["families"] = fam
    store["bilateral"] = bool(fam.get("bilateral", True))
    store["channel_list"] = list(channels_from_families(fam))


def _clip(x: float, lo: float = -DELTA_CLIP, hi: float = DELTA_CLIP) -> float:
    return float(lo if x < lo else hi if x > hi else x)


def _q_scalar(v: float, bins: int = QUANT_BINS) -> float:
    x = max(0.0, min(0.999999, float(v)))
    q = int(x * bins)
    return (q + 0.5) / bins


def extract_sensory(
    observation: dict[str, float] | None,
    channels: tuple[str, ...] | None = None,
) -> dict[str, float]:
    obs = observation or {}
    keys = channels or SENSORY_CHANNELS
    out: dict[str, float] = {}
    for k in keys:
        if k in obs and isinstance(obs[k], (int, float)) and not isinstance(obs[k], bool):
            out[k] = float(obs[k])
    return out


def sensory_signature(
    s: dict[str, float],
    channels: tuple[str, ...] | None = None,
) -> dict[str, float]:
    keys = channels or SENSORY_CHANNELS
    return {k: _q_scalar(s.get(k, 0.0)) for k in keys}


def sensory_delta(
    before: dict[str, float],
    after: dict[str, float],
    channels: tuple[str, ...] | None = None,
) -> dict[str, float]:
    keys = channels or SENSORY_CHANNELS
    d: dict[str, float] = {}
    for k in keys:
        a = float(before.get(k, 0.0))
        b = float(after.get(k, 0.0))
        d[k] = _clip(b - a)
    return d


def motor_signature_from_composite(motor: dict[str, Any] | None, *, shuffle_salt: int | None = None) -> str:
    """Authoritative COMPOSITE_MOTOR_V1 signature (not legacy single token)."""
    m = motor or {}
    loco = str(m.get("locomotion") or "WAIT")
    neck = str(m.get("neck") or "NONE")
    osc = m.get("oscillator") or {}
    if isinstance(osc, dict):
        emit = 1 if osc.get("emit_trigger") else 0
        fd = int(osc.get("frequency_delta") or 0)
        ad = int(osc.get("amplitude_delta") or 0)
    else:
        emit, fd, ad = 0, 0, 0
    push = 1 if m.get("push") else 0
    sig = f"L:{loco}|N:{neck}|E:{emit}|F:{fd}|A:{ad}|P:{push}"
    if shuffle_salt is not None:
        # Deterministic permutation of signature string for control experiments
        # (breaks action conditioning while preserving update rate / capacity).
        chars = list(sig)
        n = len(chars)
        for i in range(n - 1, 0, -1):
            j = (shuffle_salt * (i + 3) + 17) % (i + 1)
            chars[i], chars[j] = chars[j], chars[i]
        sig = "SHUF:" + "".join(chars)
    return sig


def motor_signature_loco_only(loco: str) -> str:
    return f"L:{loco}|N:ANY|E:ANY|F:ANY|A:ANY|P:ANY"


def motor_signature_neck_only(neck: str) -> str:
    return f"L:ANY|N:{neck}|E:ANY|F:ANY|A:ANY|P:ANY"


def _sig_key(
    s_sig: dict[str, float],
    m_sig: str,
    channels: tuple[str, ...] | None = None,
) -> str:
    # Deterministic compact key
    keys = channels or SENSORY_CHANNELS
    parts = [f"{k}:{s_sig.get(k, 0.0):.3f}" for k in keys]
    return hash_stable("|".join(parts) + "||" + m_sig)


def hash_stable(text: str) -> str:
    # FNV-1a 64-bit hex — deterministic, no hashlib dependency surprises
    h = 14695981039346656037
    for ch in text.encode("utf-8"):
        h ^= ch
        h = (h * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return f"{h:016x}"


def _l1(
    a: dict[str, float],
    b: dict[str, float],
    channels: tuple[str, ...] | None = None,
) -> float:
    keys = channels or SENSORY_CHANNELS
    return sum(abs(float(a.get(k, 0.0)) - float(b.get(k, 0.0))) for k in keys) / max(1, len(keys))


def update(
    store: dict[str, Any],
    *,
    tick: int,
    observation_t: dict[str, float],
    motor: dict[str, Any] | None,
    observation_t1: dict[str, float],
    observation_id: str | None = None,
    motor_id: str | None = None,
    verification_observation_id: str | None = None,
) -> dict[str, Any] | None:
    """Record (S_t, M_t) → ΔS. Returns compact update receipt or None if disabled."""
    if not store.get("enabled"):
        return None
    store["ticks"] = int(tick)
    ch = channels_for_store(store)
    s0 = extract_sensory(observation_t, ch)
    s1 = extract_sensory(observation_t1, ch)
    if not s0 and not s1:
        return None
    delta = sensory_delta(s0, s1, ch)
    s_sig = sensory_signature(s0, ch)
    salt = int(tick) if store.get("shuffle_motor_labels") else None
    m_sig = motor_signature_from_composite(motor, shuffle_salt=salt)
    key = _sig_key(s_sig, m_sig, ch)
    records = store.setdefault("records", {})
    row = records.get(key)
    if row is None:
        if len(records) >= int(store.get("capacity") or DEFAULT_CAPACITY):
            # Evict lowest support, then oldest tick
            victim = min(
                records.items(),
                key=lambda kv: (int(kv[1].get("support") or 0), int(kv[1].get("last_tick") or 0)),
            )[0]
            old = records.get(victim)
            _index_drop_key(store, victim, old if isinstance(old, dict) else None)
            del records[victim]
            store["evictions"] = int(store.get("evictions") or 0) + 1
        rid = f"SMC{int(store.get('next_id') or 1)}"
        store["next_id"] = int(store.get("next_id") or 1) + 1
        row = {
            "record_id": rid,
            "key": key,
            "motor_signature": m_sig,
            "context_signature": s_sig,
            "sum_delta": {k: 0.0 for k in ch},
            "var_sum": {k: 0.0 for k in ch},
            "n": 0.0,
            "support": 0,
            "last_tick": tick,
            "source_observation_ids": [],
            "source_motor_ids": [],
            "verification_observation_ids": [],
        }
        records[key] = row
        _index_add_key(store, key, row)
    n = float(row["n"])
    for k, v in delta.items():
        prev = float(row["sum_delta"].get(k, 0.0))
        mean_old = prev / max(n, 1e-9) if n > 0 else float(v)
        row["sum_delta"][k] = prev + float(v)
        n_new = n + 1.0
        mean_new = row["sum_delta"][k] / n_new
        row["var_sum"][k] = float(row["var_sum"].get(k, 0.0)) + (float(v) - mean_old) * (float(v) - mean_new)
    row["n"] = n + 1.0
    row["support"] = int(row["support"]) + 1
    row["last_tick"] = int(tick)
    if observation_id:
        ids = row.setdefault("source_observation_ids", [])
        ids.append(observation_id)
        row["source_observation_ids"] = ids[-8:]
    if motor_id:
        mids = row.setdefault("source_motor_ids", [])
        mids.append(motor_id)
        row["source_motor_ids"] = mids[-8:]
    if verification_observation_id:
        vids = row.setdefault("verification_observation_ids", [])
        vids.append(verification_observation_id)
        row["verification_observation_ids"] = vids[-8:]
    store["updates"] = int(store.get("updates") or 0) + 1
    mean = mean_delta(row)
    receipt = {
        "kind": "SENSORIMOTOR_CONSEQUENCE_UPDATED",
        "schema": SCHEMA,
        "tick": tick,
        "record_id": row["record_id"],
        "motor_signature": m_sig,
        "support": row["support"],
        "mean_delta": mean,
        "source_observation_id": observation_id,
        "source_motor_id": motor_id,
        "verification_observation_id": verification_observation_id,
    }
    store["last_update"] = receipt
    return receipt


def mean_delta(row: dict[str, Any]) -> dict[str, float]:
    n = max(1e-9, float(row.get("n") or 1.0))
    return {k: float(v) / n for k, v in (row.get("sum_delta") or {}).items()}


def reliability(row: dict[str, Any]) -> float:
    n = max(1e-9, float(row.get("n") or 1.0))
    if n < 2:
        return 0.5
    vars_ = []
    for vs in (row.get("var_sum") or {}).values():
        vars_.append(max(0.0, float(vs) / max(n - 1.0, 1e-9)))
    if not vars_:
        return 0.5
    std = sum(math.sqrt(v) for v in vars_) / len(vars_)
    return float(max(0.0, min(1.0, 1.0 - std)))


def _find_row(store: dict[str, Any], s_sig: dict[str, float], m_sig: str) -> dict[str, Any] | None:
    records = store.get("records") or {}
    key = _sig_key(s_sig, m_sig, channels_for_store(store))
    if key in records:
        return records[key]
    # Similarity generalization: same motor, nearby context
    best = None
    best_d = 1e9
    ch = channels_for_store(store)
    for row in iter_records_for_motor(store, m_sig):
        d = _l1(s_sig, row.get("context_signature") or {}, ch)
        if d < best_d:
            best_d = d
            best = row
    if best is not None and best_d <= SIM_THRESHOLD:
        return best
    return None


def query(
    store: dict[str, Any],
    *,
    observation: dict[str, float],
    motor: dict[str, Any] | None = None,
    motor_signature: str | None = None,
    tick: int | None = None,
) -> dict[str, Any]:
    """Predict ΔS for (O, M). status: MATCH | LOW_SUPPORT | UNKNOWN."""
    store["queries"] = int(store.get("queries") or 0) + 1
    if not store.get("enabled"):
        out = {
            "kind": "SENSORIMOTOR_CONSEQUENCE_PREDICTED",
            "status": UNKNOWN,
            "reason": "disabled",
            "predicted_delta": None,
            "support": 0,
            "reliability": None,
            "record_id": None,
        }
        store["unknown_queries"] = int(store.get("unknown_queries") or 0) + 1
        store["last_query"] = out
        return out
    ch = channels_for_store(store)
    s_sig = sensory_signature(extract_sensory(observation, ch), ch)
    m_sig = motor_signature or motor_signature_from_composite(motor)
    row = _find_row(store, s_sig, m_sig)
    if row is None:
        store["unknown_queries"] = int(store.get("unknown_queries") or 0) + 1
        out = {
            "kind": "SENSORIMOTOR_CONSEQUENCE_PREDICTED",
            "status": UNKNOWN,
            "reason": "no_record",
            "motor_signature": m_sig,
            "predicted_delta": None,
            "support": 0,
            "reliability": None,
            "record_id": None,
            "tick": tick,
        }
        store["last_query"] = out
        return out
    support = int(row.get("support") or 0)
    status = MATCH if support >= 3 else LOW_SUPPORT
    store["matched_queries"] = int(store.get("matched_queries") or 0) + 1
    pred = mean_delta(row)
    out = {
        "kind": "SENSORIMOTOR_CONSEQUENCE_PREDICTED",
        "status": status,
        "reason": "exact_or_similar_context",
        "motor_signature": m_sig,
        "predicted_delta": pred,
        "support": support,
        "reliability": reliability(row),
        "record_id": row.get("record_id"),
        "tick": tick,
        "available_to_prospection": True,
    }
    store["last_query"] = out
    return out


def query_candidates(
    store: dict[str, Any],
    *,
    observation: dict[str, float],
    loco_candidates: list[str],
    tick: int | None = None,
) -> list[dict[str, Any]]:
    """Query locomotion candidates (neck ANY) for PSC attachment."""
    store["queries"] = int(store.get("queries") or 0)  # query() increments
    results = []
    for loco in loco_candidates:
        # Build a composite-like motor with only loco specified
        motor = {"locomotion": loco, "neck": "NONE", "oscillator": {}, "push": False}
        # Prefer loco-only generalized signature match first
        ch = channels_for_store(store)
        s_sig = sensory_signature(extract_sensory(observation, ch), ch)
        # Try full then loco-only rows by scanning
        pred = query(store, observation=observation, motor=motor, tick=tick)
        if pred.get("status") == UNKNOWN:
            # soft: any record with same loco prefix
            best = None
            for row in iter_records_for_loco(store, loco):
                if best is None or int(row.get("support") or 0) > int(best.get("support") or 0):
                    best = row
            if best is not None:
                pred = {
                    "kind": "SENSORIMOTOR_CONSEQUENCE_PREDICTED",
                    "status": MATCH if int(best.get("support") or 0) >= 3 else LOW_SUPPORT,
                    "reason": "loco_prefix_aggregate",
                    "motor_signature": best.get("motor_signature"),
                    "predicted_delta": mean_delta(best),
                    "support": int(best.get("support") or 0),
                    "reliability": reliability(best),
                    "record_id": best.get("record_id"),
                    "tick": tick,
                    "available_to_prospection": True,
                    "candidate_locomotion": loco,
                }
                store["matched_queries"] = int(store.get("matched_queries") or 0) + 1
            else:
                pred = {**pred, "candidate_locomotion": loco}
        else:
            pred = {**pred, "candidate_locomotion": loco}
        results.append(pred)
    return results


def prediction_error(
    predicted_delta: dict[str, float] | None,
    actual_delta: dict[str, float],
    channels: tuple[str, ...] | None = None,
) -> float | None:
    if not predicted_delta:
        return None
    keys = channels or SENSORY_CHANNELS
    return sum(abs(float(predicted_delta.get(k, 0.0)) - float(actual_delta.get(k, 0.0))) for k in keys) / max(1, len(keys))


def apply_predicted_to_observation(observation: dict[str, float], predicted_delta: dict[str, float] | None) -> dict[str, float]:
    """Construct O' = clip01(O + Δ̂) for PSC fragment enrichment (not a value)."""
    if not predicted_delta:
        return dict(observation)
    out = dict(observation)
    for k, d in predicted_delta.items():
        if k in out:
            out[k] = max(0.0, min(1.0, float(out[k]) + float(d)))
        else:
            # only write known sensory channels
            if k in SENSORY_CHANNELS:
                out[k] = max(0.0, min(1.0, float(d)))
    return out


def snapshot(store: dict[str, Any]) -> dict[str, Any]:
    import json
    return json.loads(json.dumps(store, default=str))


def diagnostic(store: dict[str, Any]) -> dict[str, Any]:
    recs = store.get("records") or {}
    supports = [int(r.get("support") or 0) for r in recs.values()]
    return {
        "schema": SCHEMA,
        "enabled": bool(store.get("enabled")),
        "occupancy": len(recs),
        "capacity": int(store.get("capacity") or 0),
        "updates": int(store.get("updates") or 0),
        "queries": int(store.get("queries") or 0),
        "matched_queries": int(store.get("matched_queries") or 0),
        "unknown_queries": int(store.get("unknown_queries") or 0),
        "evictions": int(store.get("evictions") or 0),
        "mean_support": (sum(supports) / len(supports)) if supports else 0.0,
        "shuffle_motor_labels": bool(store.get("shuffle_motor_labels")),
        "channels": list(store.get("channel_list") or SENSORY_CHANNELS),
        "last_update": store.get("last_update"),
        "last_query": store.get("last_query"),
    }


def audit_no_gt(payload: Any) -> list[str]:
    text = repr(payload)
    return [t for t in FORBIDDEN_FEATURE_TOKENS if t in text]
