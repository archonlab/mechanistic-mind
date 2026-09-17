"""Update 4.4 — sensorimotor fragments, contingencies, neutral motor primitives.

Primitives get IDs like MP-0001 with NO semantics.
Discovery = repeatability / predictive consistency, NOT valuation / reward.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any


def _quantize(seq: list[float], bins: float = 0.1) -> tuple[int, ...]:
    return tuple(int(round(float(x) / bins)) for x in seq)


def fragment_key(
    *,
    actuator_delta: list[float],
    context_bucket: str,
) -> str:
    return repr((_quantize(actuator_delta), str(context_bucket)))


@dataclass
class SensorimotorFragment:
    tick: int
    actuator_before: list[float]
    actuator_delta: list[float]
    actuator_after: list[float]
    proprio_before: dict[str, Any]
    proprio_after: dict[str, Any]
    perceptual_delta_tokens: tuple[str, ...]
    body_delta: dict[str, float]
    resistance: float
    contact: float
    displacement: tuple[int, int] | None
    effect_kind: str
    context_bucket: str

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["perceptual_delta_tokens"] = list(self.perceptual_delta_tokens)
        d["displacement"] = list(self.displacement) if self.displacement else None
        return d


@dataclass
class ContingencyRecord:
    key: str
    support: float = 0.0
    displace_rate: float = 0.0
    contact_rate: float = 0.0
    resist_rate: float = 0.0
    contradiction: float = 0.0
    last_tick: int = -1
    first_tick: int | None = None
    effect_hist: dict[str, int] = field(default_factory=dict)
    last_displacement: tuple[int, int] | None = None
    displace_count: float = 0.0
    mean_body_delta: dict[str, float] = field(default_factory=dict)
    body_delta_samples: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MotorPrimitiveCandidate:
    primitive_id: str
    key: str
    first_occurrence: int
    recurrence: int = 1
    support: float = 1.0
    sequence_length: int = 1
    contradiction_rate: float = 0.0
    predictive_support: float = 0.0
    first_recognition_tick: int | None = None
    first_reuse_tick: int | None = None
    reuse_count: int = 0
    context_support: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SensorimotorBootstrapStore:
    contingencies: dict[str, ContingencyRecord] = field(default_factory=dict)
    primitives: dict[str, MotorPrimitiveCandidate] = field(default_factory=dict)
    recent_fragments: list[dict[str, Any]] = field(default_factory=list)
    next_primitive_index: int = 1
    # Bounded buffers
    max_recent: int = 64
    max_contingencies: int = 256
    # Formation thresholds (diagnostic; not rewards)
    min_support_for_primitive: float = 4.0
    max_contradiction_for_primitive: float = 0.35
    # Ablation: if False, store fragments but do not retrieve (Experiment D)
    retrieval_enabled: bool = True
    variation_event_count: int = 0
    no_effect_count: int = 0
    displace_count: int = 0
    contact_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "contingencies": {k: v.to_dict() for k, v in self.contingencies.items()},
            "primitives": {k: v.to_dict() for k, v in self.primitives.items()},
            "recent_fragments": list(self.recent_fragments[- self.max_recent :]),
            "next_primitive_index": self.next_primitive_index,
            "max_recent": self.max_recent,
            "max_contingencies": self.max_contingencies,
            "min_support_for_primitive": self.min_support_for_primitive,
            "max_contradiction_for_primitive": self.max_contradiction_for_primitive,
            "retrieval_enabled": self.retrieval_enabled,
            "variation_event_count": self.variation_event_count,
            "no_effect_count": self.no_effect_count,
            "displace_count": self.displace_count,
            "contact_count": self.contact_count,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> "SensorimotorBootstrapStore":
        data = raw or {}
        store = cls()
        for k, v in (data.get("contingencies") or {}).items():
            if isinstance(v, dict):
                store.contingencies[str(k)] = ContingencyRecord(**{
                    kk: v[kk] for kk in ContingencyRecord.__dataclass_fields__ if kk in v
                })
        for k, v in (data.get("primitives") or {}).items():
            if isinstance(v, dict):
                store.primitives[str(k)] = MotorPrimitiveCandidate(**{
                    kk: v[kk] for kk in MotorPrimitiveCandidate.__dataclass_fields__ if kk in v
                })
        store.recent_fragments = list(data.get("recent_fragments") or [])
        store.next_primitive_index = int(data.get("next_primitive_index") or 1)
        store.retrieval_enabled = bool(data.get("retrieval_enabled", True))
        for attr in (
            "variation_event_count",
            "no_effect_count",
            "displace_count",
            "contact_count",
            "max_recent",
            "max_contingencies",
        ):
            if attr in data:
                setattr(store, attr, int(data[attr]))
        return store


def ingest_fragment(store: SensorimotorBootstrapStore, frag: SensorimotorFragment) -> dict[str, Any]:
    """Update contingencies / maybe form neutral primitive. No valuation."""
    store.variation_event_count += 1
    if frag.effect_kind in ("NONE", "NO_DISPLACE"):
        store.no_effect_count += 1
    if frag.displacement:
        store.displace_count += 1
    if frag.contact > 0:
        store.contact_count += 1

    key = fragment_key(
        actuator_delta=frag.actuator_delta,
        context_bucket=frag.context_bucket,
    )
    rec = store.contingencies.get(key)
    if rec is None:
        if len(store.contingencies) >= store.max_contingencies:
            # Drop lowest-support
            weakest = min(store.contingencies.items(), key=lambda kv: kv[1].support)
            store.contingencies.pop(weakest[0], None)
        rec = ContingencyRecord(key=key, first_tick=frag.tick)
        store.contingencies[key] = rec

    prev_support = rec.support
    rec.support += 1.0
    # Running rates
    disp = 1.0 if frag.displacement else 0.0
    cont = 1.0 if frag.contact > 0 else 0.0
    resist = 1.0 if frag.resistance > 0 else 0.0
    n = rec.support
    rec.displace_rate += (disp - rec.displace_rate) / n
    rec.contact_rate += (cont - rec.contact_rate) / n
    rec.resist_rate += (resist - rec.resist_rate) / n
    hist = dict(rec.effect_hist)
    hist[frag.effect_kind] = int(hist.get(frag.effect_kind, 0)) + 1
    rec.effect_hist = hist
    if frag.displacement:
        rec.last_displacement = tuple(frag.displacement)
        rec.displace_count += 1.0
    # Running mean of physical body deltas (energy/hydration/fatigue...)
    bd = {
        str(k): float(v)
        for k, v in (frag.body_delta or {}).items()
        if isinstance(v, (int, float)) and not isinstance(v, bool)
    }
    if bd:
        rec.body_delta_samples += 1.0
        n = rec.body_delta_samples
        mean = dict(rec.mean_body_delta)
        for k, v in bd.items():
            prev = float(mean.get(k, 0.0))
            mean[k] = prev + (v - prev) / n
        rec.mean_body_delta = mean
    # Contradiction: dominant effect share inverse
    total_h = sum(hist.values()) or 1
    dominant = max(hist.values()) / total_h
    rec.contradiction = float(1.0 - dominant)
    rec.last_tick = frag.tick

    store.recent_fragments.append(frag.to_dict())
    if len(store.recent_fragments) > store.max_recent:
        store.recent_fragments = store.recent_fragments[-store.max_recent :]

    formed = None
    if (
        rec.support >= store.min_support_for_primitive
        and rec.contradiction <= store.max_contradiction_for_primitive
    ):
        # Find existing primitive for key or create
        existing = next((p for p in store.primitives.values() if p.key == key), None)
        if existing is None:
            pid = f"MP-{store.next_primitive_index:04d}"
            store.next_primitive_index += 1
            existing = MotorPrimitiveCandidate(
                primitive_id=pid,
                key=key,
                first_occurrence=int(rec.first_tick if rec.first_tick is not None else frag.tick),
                recurrence=int(rec.support),
                support=float(rec.support),
                contradiction_rate=float(rec.contradiction),
                predictive_support=float(1.0 - rec.contradiction),
                first_recognition_tick=frag.tick,
                context_support=1,
            )
            store.primitives[pid] = existing
            formed = existing.primitive_id
        else:
            existing.recurrence = int(rec.support)
            existing.support = float(rec.support)
            existing.contradiction_rate = float(rec.contradiction)
            existing.predictive_support = float(1.0 - rec.contradiction)
            if existing.first_reuse_tick is None and prev_support >= store.min_support_for_primitive:
                existing.first_reuse_tick = frag.tick
            if prev_support >= store.min_support_for_primitive:
                existing.reuse_count += 1

    return {
        "key": key,
        "support": rec.support,
        "contradiction": rec.contradiction,
        "primitive_formed_or_updated": formed or (
            next((p.primitive_id for p in store.primitives.values() if p.key == key), None)
        ),
        "observer_note": "OBSERVER ONLY — NOT AVAILABLE TO COGNITION",
    }


def retrieve_contingencies(
    store: SensorimotorBootstrapStore,
    *,
    actuator_delta: list[float] | None = None,
    context_bucket: str | None = None,
    by_context_only: bool = False,
) -> list[dict[str, Any]]:
    """Return matching contingency records. Empty if retrieval ablated.

    If by_context_only, match any contingency whose key embeds this context_bucket.
    """
    if not store.retrieval_enabled:
        return []
    if by_context_only and context_bucket is not None:
        hits = []
        for key, rec in store.contingencies.items():
            if str(context_bucket) in key or key.endswith(repr(str(context_bucket))):
                hits.append(rec.to_dict())
            elif context_bucket and context_bucket in key:
                hits.append(rec.to_dict())
        return hits
    if actuator_delta is None or context_bucket is None:
        return []
    key = fragment_key(actuator_delta=actuator_delta, context_bucket=context_bucket)
    rec = store.contingencies.get(key)
    if rec is None:
        return []
    return [rec.to_dict()]


def retrieve_primitive_executables(
    store: SensorimotorBootstrapStore,
    *,
    position: tuple[int, int] | None,
    available_actions: set[str],
    context_bucket: str,
) -> list[dict[str, Any]]:
    """Map acquired MPs to physically available executable actions.

    Availability only — does NOT assign ordinary value / reward.
    """
    if not store.retrieval_enabled:
        return []
    out: list[dict[str, Any]] = []
    for mp in store.primitives.values():
        rec = store.contingencies.get(mp.key)
        if rec is None:
            continue
        # Prefer context-related primitives (soft filter)
        if context_bucket and context_bucket not in mp.key and repr(context_bucket) not in mp.key:
            # still allow if same quantized motor family appeared often
            pass
        disp = rec.last_displacement
        action = None
        if disp is not None and position is not None:
            dest = (int(position[0]) + int(disp[0]), int(position[1]) + int(disp[1]))
            cand = f"MOVE:{dest[0]},{dest[1]}"
            if cand in available_actions:
                action = cand
        if action is None:
            continue
        status = "SUPPORTED" if mp.support >= 4 and mp.contradiction_rate <= 0.35 else "INSUFFICIENT_EVIDENCE"
        out.append(
            {
                "primitive_id": mp.primitive_id,
                "action": action,
                "support": float(mp.support),
                "contradiction_rate": float(mp.contradiction_rate),
                "predictive_support": float(mp.predictive_support),
                "prediction_status": status,
                "predicted_displacement": list(disp) if disp else None,
                "effect_hist": dict(rec.effect_hist),
                "mean_body_delta": dict(rec.mean_body_delta),
                "body_delta_samples": float(rec.body_delta_samples),
                "contradiction_rate": float(mp.contradiction_rate),
                "key": mp.key,
            }
        )
    return out


def microvariation_telemetry(store: SensorimotorBootstrapStore) -> dict[str, Any]:
    v = max(1, store.variation_event_count)
    return {
        "variation_events": store.variation_event_count,
        "no_effect_rate": store.no_effect_count / v,
        "displace_rate": store.displace_count / v,
        "contact_rate": store.contact_count / v,
        "contingency_count": len(store.contingencies),
        "primitive_count": len(store.primitives),
        "unique_fragment_keys": len(store.contingencies),
        "observer_note": "OBSERVER ONLY — NOT AVAILABLE TO COGNITION",
    }
