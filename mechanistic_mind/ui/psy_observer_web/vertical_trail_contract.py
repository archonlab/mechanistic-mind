"""OBSERVER_ENTITY_HEIGHT_FALL_TRAILS_V1 — display-only vertical trail packing.

DERIVED_OBSERVER_CACHE_NON_AUTHORITATIVE. Never mutates physics.
Updated only when Observer vertical_display is built (no headless cost otherwise).
Samples are projections of authoritative per-tick entity state + receipt linkage.
"""
from __future__ import annotations

import math
from typing import Any

DISPLAY_PROFILE = "OBSERVER_ENTITY_HEIGHT_FALL_TRAILS_V1"
TRAIL_CONTRACT = "OBSERVER_VERTICAL_DISPLAY_CONTRACT_V1_1"
TRAIL_CACHE_ATTR = "_observer_vertical_trail_cache"
CACHE_CLASS = "DERIVED_OBSERVER_CACHE_NON_AUTHORITATIVE"

SAMPLES_PER_ENTITY_DEFAULT = 32
SAMPLES_PER_ENTITY_HARD_MAX = 64
VISIBLE_TRAIL_ENTITY_CAP = 8
TOTAL_SAMPLE_HARD_CAP = 256
COMPLETED_SEGMENT_LIFETIME_TICKS = 48
MISSING_TICK_GAP_THRESHOLD = 2

TRAIL_LENGTH_SHORT = 16
TRAIL_LENGTH_NORMAL = 32
TRAIL_LENGTH_LONG = 48

STATE_UNSUPPORTED = "UNSUPPORTED"
STATE_TERRAIN_INTERSECT = "TERRAIN_INTERSECT"
STATE_SUPPORTED = "SUPPORTED"
STATE_HELD = "CONSTRAINED_HELD_NOT_INDEPENDENT"

START_RELEASE = "RELEASE"
START_SUPPORT_LOSS = "SUPPORT_LOSS"
START_UNSUPPORTED = "UNSUPPORTED_TRANSITION"
START_RESTORE = "RESTORE_BOUNDARY"
END_LANDING = "LANDING"
END_SUPPORTED_REST = "SUPPORTED_REST"
END_HELD = "HELD"
END_REMOVED = "REMOVED"
END_RESTORE = "RESTORE_BOUNDARY"


def invalidate_vertical_trail_cache(world: Any) -> None:
    if world is None:
        return
    if hasattr(world, TRAIL_CACHE_ATTR):
        try:
            delattr(world, TRAIL_CACHE_ATTR)
        except Exception:
            setattr(world, TRAIL_CACHE_ATTR, None)


def _empty_cache(*, generation: int = 0, restore_boundary: bool = False) -> dict[str, Any]:
    return {
        "class": CACHE_CLASS,
        "display_profile": DISPLAY_PROFILE,
        "runtime_generation": int(generation),
        "last_tick": None,
        "segments": {},  # entity_id -> list[segment]
        "active": {},  # entity_id -> segment_id
        "seen_ids": set(),
        "restore_pending": bool(restore_boundary),
        "seq": 0,
    }


def _get_cache(world: Any) -> dict[str, Any]:
    raw = getattr(world, TRAIL_CACHE_ATTR, None)
    if isinstance(raw, dict) and raw.get("display_profile") == DISPLAY_PROFILE:
        return raw
    cache = _empty_cache()
    try:
        setattr(world, TRAIL_CACHE_ATTR, cache)
    except Exception:
        pass
    return cache


def _finite(v: Any) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _event_index(events: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for ev in events or []:
        eid = str(ev.get("entity_id") or "")
        if not eid:
            continue
        out.setdefault(eid, []).append(ev)
    return out


def _events_at(by_id: dict[str, list[dict[str, Any]]], eid: str, tick: int, cls: str) -> list[dict[str, Any]]:
    return [
        e for e in by_id.get(eid, [])
        if int(e.get("tick") or -1) == int(tick) and str(e.get("event_class") or "") == cls
    ]


def _new_segment(
    cache: dict[str, Any],
    *,
    entity_id: str,
    entity_kind: str,
    tick: int,
    reason: str,
) -> dict[str, Any]:
    cache["seq"] = int(cache.get("seq") or 0) + 1
    seg_id = f"trail-{entity_id}-{cache['seq']}"
    return {
        "segment_id": seg_id,
        "entity_id": str(entity_id),
        "entity_kind": str(entity_kind),
        "start_reason": reason,
        "start_tick": int(tick),
        "end_tick": None,
        "end_reason": None,
        "active": True,
        "samples": [],
        "release_tick": None,
        "support_loss_tick": None,
        "landing_tick": None,
        "acoustic_tick": None,
        "discontinuity_reason": reason if reason == START_RESTORE else None,
        "authority": CACHE_CLASS,
        "sample_authority": "AUTHORITATIVE_SIMULATION_STATE",
        "sample_source": "per_tick_entity_vertical_plus_receipt_linkage",
    }


def _sample_from_entity(ent: dict[str, Any], *, tick: int, provenance: str) -> dict[str, Any] | None:
    if not ent or not ent.get("z_available"):
        return None
    base_z = _finite(ent.get("base_z"))
    if base_z is None:
        return None
    clearance = _finite(ent.get("clearance"))
    support_z = _finite(ent.get("support_z"))
    return {
        "tick": int(tick),
        "entity_id": str(ent.get("id") or ""),
        "entity_kind": str(ent.get("kind") or ""),
        "x": float(ent.get("x") or 0.0),
        "y": float(ent.get("y") or 0.0),
        "base_z": base_z,
        "centre_z": _finite(ent.get("centre_z")),
        "support_z": support_z,
        "clearance": clearance,
        "vz": _finite(ent.get("vz")),
        "support_state": ent.get("support_state"),
        "physical_state": ent.get("physical_state"),
        "held_constrained": bool(ent.get("held_constrained")),
        "integration_eligibility": ent.get("dynamics_eligible_tick"),
        "authoritative_source": provenance,
        "authority": "AUTHORITATIVE_SAMPLE",
        "discontinuity": False,
        "release_tick": None,
        "support_loss_tick": None,
        "landing_response_key": None,
        "acoustic_source_id": None,
    }


def _close_segment(seg: dict[str, Any], *, tick: int, reason: str) -> None:
    seg["active"] = False
    seg["end_tick"] = int(tick)
    seg["end_reason"] = reason


def _append_sample(seg: dict[str, Any], sample: dict[str, Any]) -> None:
    samples = seg.setdefault("samples", [])
    # Dedup same tick.
    if samples and int(samples[-1].get("tick") or -1) == int(sample["tick"]):
        samples[-1] = sample
    else:
        samples.append(sample)
    if len(samples) > SAMPLES_PER_ENTITY_HARD_MAX:
        seg["samples"] = samples[-SAMPLES_PER_ENTITY_HARD_MAX:]


def update_trail_cache_from_entities(
    world: Any,
    *,
    tick: int,
    entities: list[dict[str, Any]],
    events: list[dict[str, Any]],
    runtime_generation: int | None = None,
) -> dict[str, Any]:
    """Append bounded authoritative samples. Observer-serialization path only."""
    cache = _get_cache(world)
    if runtime_generation is not None and cache.get("runtime_generation") not in (None, int(runtime_generation)):
        # Apply/reset generation change — wipe.
        cache = _empty_cache(generation=int(runtime_generation), restore_boundary=True)
        try:
            setattr(world, TRAIL_CACHE_ATTR, cache)
        except Exception:
            pass
    elif runtime_generation is not None:
        cache["runtime_generation"] = int(runtime_generation)

    last = cache.get("last_tick")
    gap = None if last is None else int(tick) - int(last)
    if gap is not None and gap < 0:
        # Clock rewind / restore — boundary.
        cache = _empty_cache(
            generation=int(cache.get("runtime_generation") or 0),
            restore_boundary=True,
        )
        try:
            setattr(world, TRAIL_CACHE_ATTR, cache)
        except Exception:
            pass
        gap = None

    by_ev = _event_index(events)
    current_ids = {str(e.get("id") or "") for e in entities if e and e.get("id")}
    # Terminate removed entities.
    for eid, seg_id in list((cache.get("active") or {}).items()):
        if eid not in current_ids:
            segs = (cache.get("segments") or {}).get(eid) or []
            for seg in segs:
                if seg.get("segment_id") == seg_id and seg.get("active"):
                    _close_segment(seg, tick=int(tick), reason=END_REMOVED)
            cache["active"].pop(eid, None)

    restore_pending = bool(cache.pop("restore_pending", False)) if "restore_pending" in cache else False

    for ent in entities:
        eid = str(ent.get("id") or "")
        if not eid:
            continue
        kind = str(ent.get("kind") or "")
        held = bool(ent.get("held_constrained")) or str(ent.get("physical_state") or "") == "HELD"
        support_state = str(ent.get("support_state") or "")
        clearance = _finite(ent.get("clearance"))
        grounded = ent.get("grounded")
        # Infer unsupported when free-space label missing but clearance/grounded say so.
        if not support_state:
            if held:
                support_state = STATE_HELD
            elif grounded is False or (clearance is not None and clearance > 1e-6):
                support_state = STATE_UNSUPPORTED
            elif grounded is True and (clearance is None or clearance <= 1e-6):
                support_state = STATE_SUPPORTED
        sample = _sample_from_entity(
            ent,
            tick=tick,
            provenance="entities_vertical_authoritative_projection",
        )
        if sample is not None and not sample.get("support_state"):
            sample["support_state"] = support_state or None

        releases = _events_at(by_ev, eid, tick, "RELEASE")
        losses = _events_at(by_ev, eid, tick, "SUPPORT_LOSS")
        landings = _events_at(by_ev, eid, tick, "LANDING_RESPONSE")
        acoustics = _events_at(by_ev, eid, tick, "ACOUSTIC_EMISSION")

        active_id = (cache.get("active") or {}).get(eid)
        segs = cache.setdefault("segments", {}).setdefault(eid, [])
        active = next((s for s in segs if s.get("segment_id") == active_id and s.get("active")), None)

        # HELD: end any free trail; do not independently trail held objects.
        if held and not releases:
            if active is not None:
                _close_segment(active, tick=int(tick), reason=END_HELD)
                cache["active"].pop(eid, None)
            continue

        start_reason = None
        if restore_pending:
            start_reason = START_RESTORE
        elif releases:
            start_reason = START_RELEASE
        elif losses:
            start_reason = START_SUPPORT_LOSS
        elif active is None and support_state == STATE_UNSUPPORTED:
            start_reason = START_UNSUPPORTED
        elif active is not None and gap is not None and gap > MISSING_TICK_GAP_THRESHOLD:
            # Missing ticks — close and reopen with gap flag.
            _close_segment(active, tick=int(last), reason="MISSING_TICK_GAP")
            cache["active"].pop(eid, None)
            active = None
            start_reason = START_UNSUPPORTED if support_state == STATE_UNSUPPORTED else None

        if start_reason and (active is None or start_reason in (START_RELEASE, START_SUPPORT_LOSS, START_RESTORE)):
            if active is not None and active.get("active"):
                _close_segment(active, tick=int(tick), reason=start_reason)
            seg = _new_segment(cache, entity_id=eid, entity_kind=kind, tick=tick, reason=start_reason)
            if releases:
                seg["release_tick"] = int(releases[0].get("tick") or tick)
            if losses:
                seg["support_loss_tick"] = int(losses[0].get("tick") or tick)
            segs.append(seg)
            # Bound completed segments per entity.
            if len(segs) > 4:
                cache["segments"][eid] = segs[-4:]
                segs = cache["segments"][eid]
            cache.setdefault("active", {})[eid] = seg["segment_id"]
            active = seg

        if active is None:
            continue

        # Append while unsupported / terrain-intersect / release tick / support-loss tick.
        append = False
        if support_state in (STATE_UNSUPPORTED, STATE_TERRAIN_INTERSECT):
            append = True
        if releases or losses:
            append = True
        if landings:
            append = True
        if active.get("active") and support_state == STATE_SUPPORTED and (
            landings or active.get("landing_tick") is not None
        ):
            # Short supported terminal sample after landing.
            append = True

        if sample is not None and append:
            if releases:
                sample["release_tick"] = int(releases[0].get("tick") or tick)
                active["release_tick"] = sample["release_tick"]
            if losses:
                sample["support_loss_tick"] = int(losses[0].get("tick") or tick)
                active["support_loss_tick"] = sample["support_loss_tick"]
            if landings:
                ref = (landings[0].get("receipt_ref") or {})
                sample["landing_response_key"] = ref.get("response_key") or landings[0].get("event_class")
                active["landing_tick"] = int(landings[0].get("tick") or tick)
            if acoustics:
                ref = (acoustics[0].get("receipt_ref") or {})
                sample["acoustic_source_id"] = ref.get("source_id") or acoustics[0].get("source_id")
                active["acoustic_tick"] = int(acoustics[0].get("tick") or tick)
            if gap is not None and gap > MISSING_TICK_GAP_THRESHOLD:
                sample["discontinuity"] = True
                sample["discontinuity_reason"] = "MISSING_TICK_GAP"
            _append_sample(active, sample)

        # Terminate after landing + supported rest, or stable supported without activity.
        if landings and support_state == STATE_SUPPORTED:
            _close_segment(active, tick=int(tick), reason=END_LANDING)
            cache["active"].pop(eid, None)
        elif (
            active.get("active")
            and support_state == STATE_SUPPORTED
            and not releases
            and not losses
            and active.get("landing_tick") is None
            and len(active.get("samples") or []) >= 1
            and str((active.get("samples") or [{}])[-1].get("support_state") or "") == STATE_SUPPORTED
        ):
            # Stable supported rest — stop extending (do not grow indefinitely).
            _close_segment(active, tick=int(tick), reason=END_SUPPORTED_REST)
            cache["active"].pop(eid, None)

    # Expire old completed segments.
    lo = int(tick) - int(COMPLETED_SEGMENT_LIFETIME_TICKS)
    for eid, segs in list((cache.get("segments") or {}).items()):
        kept = []
        for seg in segs:
            if seg.get("active"):
                kept.append(seg)
            else:
                et = seg.get("end_tick")
                if et is None or int(et) >= lo:
                    kept.append(seg)
        cache["segments"][eid] = kept

    cache["last_tick"] = int(tick)
    cache["seen_ids"] = set(current_ids)
    return cache


def pack_trail_segments(
    cache: dict[str, Any] | None,
    *,
    tick: int,
    max_entities: int = VISIBLE_TRAIL_ENTITY_CAP,
    max_samples_per_entity: int = SAMPLES_PER_ENTITY_DEFAULT,
) -> list[dict[str, Any]]:
    """Bounded packed segments for Observer frame (backend-derived)."""
    if not isinstance(cache, dict):
        return []
    max_samples_per_entity = max(1, min(int(max_samples_per_entity), SAMPLES_PER_ENTITY_HARD_MAX))
    # Prefer active / recently ended unsupported-related segments.
    candidates: list[dict[str, Any]] = []
    for eid, segs in (cache.get("segments") or {}).items():
        for seg in segs:
            samples = list(seg.get("samples") or [])
            if not samples:
                continue
            candidates.append(seg)

    def _score(seg: dict[str, Any]) -> tuple:
        return (
            0 if seg.get("active") else 1,
            -int(seg.get("end_tick") or seg.get("start_tick") or 0),
            str(seg.get("entity_id") or ""),
        )

    candidates.sort(key=_score)
    out: list[dict[str, Any]] = []
    total_samples = 0
    for seg in candidates:
        if len(out) >= int(max_entities):
            break
        samples = list(seg.get("samples") or [])[-max_samples_per_entity:]
        if total_samples + len(samples) > TOTAL_SAMPLE_HARD_CAP:
            remain = TOTAL_SAMPLE_HARD_CAP - total_samples
            if remain <= 0:
                break
            samples = samples[-remain:]
        zs = [float(s["base_z"]) for s in samples if _finite(s.get("base_z")) is not None]
        cs = [float(s["clearance"]) for s in samples if _finite(s.get("clearance")) is not None]
        vs = [float(s["vz"]) for s in samples if _finite(s.get("vz")) is not None]
        packed = {
            "segment_id": seg.get("segment_id"),
            "entity_id": seg.get("entity_id"),
            "entity_kind": seg.get("entity_kind"),
            "start_reason": seg.get("start_reason"),
            "start_tick": seg.get("start_tick"),
            "end_tick": seg.get("end_tick"),
            "end_reason": seg.get("end_reason"),
            "active": bool(seg.get("active")),
            "sample_count": len(samples),
            "sample_policy": "AUTHORITATIVE_PER_TICK_BOUNDED",
            "z_min": min(zs) if zs else None,
            "z_max": max(zs) if zs else None,
            "clearance_min": min(cs) if cs else None,
            "clearance_max": max(cs) if cs else None,
            "vz_min": min(vs) if vs else None,
            "vz_max": max(vs) if vs else None,
            "release_tick": seg.get("release_tick"),
            "support_loss_tick": seg.get("support_loss_tick"),
            "landing_tick": seg.get("landing_tick"),
            "acoustic_tick": seg.get("acoustic_tick"),
            "discontinuity_reason": seg.get("discontinuity_reason"),
            "authority": CACHE_CLASS,
            "samples": samples,
        }
        out.append(packed)
        total_samples += len(samples)
    return out


def trail_payload_fragment(
    world: Any,
    *,
    tick: int,
    entities: list[dict[str, Any]],
    events: list[dict[str, Any]],
    runtime_generation: int | None = None,
) -> dict[str, Any]:
    cache = update_trail_cache_from_entities(
        world,
        tick=tick,
        entities=entities,
        events=events,
        runtime_generation=runtime_generation,
    )
    segments = pack_trail_segments(cache, tick=tick)
    return {
        "display_profile": DISPLAY_PROFILE,
        "trail_contract": TRAIL_CONTRACT,
        "trail_sample_authority": "AUTHORITATIVE_SIMULATION_STATE",
        "trail_sample_source": "per_tick_entity_vertical_plus_receipt_linkage",
        "trail_cache_class": CACHE_CLASS,
        "samples_per_entity_default": SAMPLES_PER_ENTITY_DEFAULT,
        "samples_per_entity_hard_max": SAMPLES_PER_ENTITY_HARD_MAX,
        "visible_trail_entity_cap": VISIBLE_TRAIL_ENTITY_CAP,
        "total_sample_hard_cap": TOTAL_SAMPLE_HARD_CAP,
        "completed_segment_lifetime_ticks": COMPLETED_SEGMENT_LIFETIME_TICKS,
        "missing_tick_gap_threshold": MISSING_TICK_GAP_THRESHOLD,
        "interpolation_default": "OFF",
        "trail_segments": segments,
        "trail_entity_count": len(segments),
        "trail_sample_count": sum(int(s.get("sample_count") or 0) for s in segments),
        "researcher_only": True,
        "agent_accessible": False,
        "fast_max_sampling_policy": (
            "SCIENTIFIC_TICK_SAMPLES_WHEN_OBSERVER_SERIALIZES; "
            "frontend may skip painted frames; trail history is not render-cadence"
        ),
        "headless_display_cost_policy": (
            "TRAIL_CACHE_UPDATED_ONLY_ON_OBSERVER_VERTICAL_DISPLAY_BUILD; "
            "no cost when Observer/capture does not serialize vertical_display"
        ),
    }
