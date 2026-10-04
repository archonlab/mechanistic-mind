"""SELECTED_ORGANISM_AUDITORY_BOUNDARY_RECEIPT_V1 — A5 pre-cognition capture.

Observational only. Copies osc_l/r from the exact observation dict bound to cognition.
Does not re-run LPS, phenotype, or alter observation/cognition.
"""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

SCHEMA = "SELECTED_ORGANISM_AUDITORY_BOUNDARY_RECEIPT_V1"
RECEIPT_FAMILY = "ORGANISM_AUDITORY_BOUNDARY_RECEIPT"
VIEW_SCHEMA = "SELECTED_ORGANISM_AUDITORY_VIEW_SAV1"
CAPABILITY = "selected_organism_auditory_view"
BOUNDARY = "A5_OSC_LR_ACCESSIBLE_OBSERVATION_PRE_COGNITION"
PROFILE = "ORGANISM_AUDITORY_BOUNDARY_A5_V1"
STATE_SCHEMA = "SELECTED_ORGANISM_AUDITORY_BOUNDARY_STATE_V1"
WORLD_ATTR = "selected_organism_auditory_boundary_state"
NE = "NOT_ESTABLISHED"
NA = "NOT_AVAILABLE"
NAPP = "NOT_APPLICABLE"
LEGACY_UNAVAILABLE = "SELECTED_ORGANISM_AUDITORY_VIEW_UNAVAILABLE_LEGACY_EVIDENCE"
LEGACY_PARTIAL = "LEGACY_A5_VALUES_PRESENT_PROVENANCE_PARTIAL"
EXPERIMENTER_UNAVAILABLE = "EXPERIMENTER_AUDITORY_BOUNDARY_NOT_AVAILABLE"

BAND_COUNT = 6
BAND_IDENTIFIERS = tuple(f"band_{i}" for i in range(BAND_COUNT))
HISTORY_CAPACITY_DEFAULT = 128  # total across agents (FIFO)

MODE_LABEL = "SELECTED ORGANISM AUDITORY VIEW"
WARNING_LABEL = (
    "ORGANISM SENSORY CHANNEL MONITOR · POST-PHENOTYPE · PRE-COGNITION · "
    "NOT HUMAN HEARING · NOT MIND READING"
)
PLAYBACK_DEFERRED = "AUDITORY PLAYBACK: DEFERRED TO SELECTED_ORGANISM_AUDITORY_SONIFICATION_V1"

LIMITATIONS = (
    "XY_ONLY_LPS",
    "NO_Z_DISTANCE",
    "NO_OCCLUSION",
    "NO_REFLECTION",
    "NO_REVERB",
    "NO_HUMAN_BINAURAL",
    "NO_INTERAURAL_TIME_DELAY",
    "NO_HRTF",
    "ANONYMOUS_BANDS_NOT_HZ",
    "POST_PHENOTYPE_CLIPPED_ACTIVATION",
    "PRE_COGNITION_ONLY",
    "NO_SEMANTIC_INTERPRETATION",
    "SAV1_VISUAL_ONLY_NO_PLAYBACK",
)


@dataclass
class SelectedOrganismAuditoryBoundaryState:
    schema_version: str = STATE_SCHEMA
    capacity: int = HISTORY_CAPACITY_DEFAULT
    receipts: list[dict[str, Any]] = field(default_factory=list)
    evicted_count: int = 0
    capture_count: int = 0
    deduplicated_count: int = 0
    last_receipt_id: str | None = None
    last_capture_tick: int | None = None


def ensure_state(world: Any) -> SelectedOrganismAuditoryBoundaryState:
    st = getattr(world, WORLD_ATTR, None)
    if isinstance(st, SelectedOrganismAuditoryBoundaryState):
        return st
    st = SelectedOrganismAuditoryBoundaryState()
    setattr(world, WORLD_ATTR, st)
    return st


def state_of(world: Any) -> SelectedOrganismAuditoryBoundaryState | None:
    st = getattr(world, WORLD_ATTR, None)
    return st if isinstance(st, SelectedOrganismAuditoryBoundaryState) else None


def _f(v: Any) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if x != x or x in (float("inf"), float("-inf")):
        return None
    return x


def extract_a5_vectors(observation: dict[str, Any] | None) -> dict[str, Any]:
    """Copy osc_l/r from observation. No phenotype recompute."""
    obs = observation if isinstance(observation, dict) else {}
    left: list[float] = []
    right: list[float] = []
    present = False
    anomalies: list[str] = []
    for i in range(BAND_COUNT):
        lk, rk = f"osc_l_{i}", f"osc_r_{i}"
        if lk in obs or rk in obs:
            present = True
        lv = _f(obs.get(lk)) if lk in obs else None
        rv = _f(obs.get(rk)) if rk in obs else None
        if lk in obs and lv is None:
            anomalies.append(lk)
            lv = 0.0
        if rk in obs and rv is None:
            anomalies.append(rk)
            rv = 0.0
        left.append(0.0 if lv is None else float(lv))
        right.append(0.0 if rv is None else float(rv))
    return {
        "present": present,
        "left": left,
        "right": right,
        "anomalies": anomalies,
    }


def phenotype_clip_stamp(
    *,
    config: Any,
    world: Any,
    body: Any,
    left: list[float],
    right: list[float],
) -> dict[str, Any]:
    """Config + optional compare to existing LPS auditory buffer. No phenotype re-run for values."""
    osc = getattr(config, "oscillatory_signaling", None) if config is not None else None
    head_cfg = getattr(config, "articulated_head", None) if config is not None else None
    head_on = bool(getattr(head_cfg, "enabled", False)) if head_cfg else False
    lps = getattr(world, "local_signal_transport", None) if world is not None else None
    sensor_scale = NE
    if lps is not None:
        sensor_scale = float(getattr(getattr(lps, "config", None), "sensor_scale", 2.0) or 2.0)
    elif osc is not None:
        sensor_scale = float(getattr(osc, "field_cap", 2.0) or 2.0)
    offset = float(getattr(osc, "receptor_offset", 0.55) or 0.55) if osc is not None else NE
    heading_authority = "HEAD_WORLD_HEADING" if head_on else "BODY_THETA"

    at_ceiling_l = [bool(v >= 1.0 - 1e-12) for v in left]
    at_ceiling_r = [bool(v >= 1.0 - 1e-12) for v in right]
    at_floor_l = [bool(v <= 1e-12) for v in left]
    at_floor_r = [bool(v <= 1e-12) for v in right]

    # Optional researcher clip inference from existing A3 buffer (read-only).
    clip_flags_l: list[Any] = [NE] * BAND_COUNT
    clip_flags_r: list[Any] = [NE] * BAND_COUNT
    clipped_count = 0
    clip_source = NE
    if lps is not None and isinstance(sensor_scale, float):
        bid = getattr(body, "_lps_body_id", None)
        entry = (getattr(lps, "auditory", None) or {}).get(str(bid)) if bid is not None else None
        tick_w = int(getattr(world, "tick", -2))
        if isinstance(entry, dict) and int(entry.get("tick", -1)) == tick_w:
            clip_source = "COMPARE_EXISTING_LPS_AUDITORY_BUFFER"
            scale = max(1e-9, float(sensor_scale))
            raw_l = list(entry.get("left") or [])
            raw_r = list(entry.get("right") or [])
            for i in range(BAND_COUNT):
                rl = float(raw_l[i]) if i < len(raw_l) else 0.0
                rr = float(raw_r[i]) if i < len(raw_r) else 0.0
                # Would clip if raw/scale outside [0,1]
                cl = rl / scale > 1.0 + 1e-12 or rl / scale < -1e-12
                cr = rr / scale > 1.0 + 1e-12 or rr / scale < -1e-12
                clip_flags_l[i] = bool(cl)
                clip_flags_r[i] = bool(cr)
                if cl:
                    clipped_count += 1
                if cr:
                    clipped_count += 1

    digest_src = {
        "sensor_scale": sensor_scale,
        "receptor_offset": offset,
        "heading_authority": heading_authority,
        "band_count": BAND_COUNT,
        "clip_range": [0.0, 1.0],
        "profile": PROFILE,
    }
    digest = hashlib.sha256(
        json.dumps(digest_src, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:16]

    return {
        "phenotype_profile": PROFILE,
        "phenotype_config_digest": digest,
        "sensor_scale": sensor_scale,
        "clipping_range": [0.0, 1.0],
        "receptor_offset": offset,
        "heading_authority": heading_authority,
        "articulated_head_enabled": head_on,
        "values_are_post_clip_bounded": True,
        "per_band_at_ceiling_left": at_ceiling_l,
        "per_band_at_ceiling_right": at_ceiling_r,
        "per_band_at_floor_left": at_floor_l,
        "per_band_at_floor_right": at_floor_r,
        "per_band_clipped_left": clip_flags_l,
        "per_band_clipped_right": clip_flags_r,
        "clipped_count": clipped_count if clip_source != NE else NE,
        "clip_inference_source": clip_source,
        "band_count": BAND_COUNT,
    }


def receipt_id(
    *,
    run_id: str,
    scientific_tick: int,
    agent_id: str,
    body_id: str,
    observation_key: str,
) -> str:
    raw = (
        f"{SCHEMA}|{run_id}|{int(scientific_tick)}|{agent_id}|{body_id}|{observation_key}"
    )
    return f"soab:{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:20]}"


def build_receipt(
    *,
    observation: dict[str, Any],
    scientific_tick: int,
    agent_id: str,
    body_id: str,
    agent_slot: int | None,
    run_id: str,
    observation_key: str,
    config: Any = None,
    world: Any = None,
    body: Any = None,
    experimenter: bool = False,
) -> dict[str, Any] | None:
    """Build one A5 receipt from observation. Returns None if auditory channels absent."""
    extracted = extract_a5_vectors(observation)
    if not extracted["present"]:
        if experimenter:
            return {
                "schema": SCHEMA,
                "receipt_family": RECEIPT_FAMILY,
                "profile": PROFILE,
                "boundary": BOUNDARY,
                "availability": EXPERIMENTER_UNAVAILABLE,
                "scientific_tick": int(scientific_tick),
                "agent_id": str(agent_id),
                "body_id": str(body_id),
                "agent_slot": agent_slot,
                "organism_accessible_section": None,
                "researcher_only": True,
                "agent_accessible": False,
                "physical_mechanism": False,
            }
        return None

    left = list(extracted["left"])
    right = list(extracted["right"])
    stamp = phenotype_clip_stamp(
        config=config, world=world, body=body, left=left, right=right,
    )
    rid = receipt_id(
        run_id=str(run_id),
        scientific_tick=int(scientific_tick),
        agent_id=str(agent_id),
        body_id=str(body_id),
        observation_key=str(observation_key),
    )
    section_a = {
        "organism_accessible": True,
        "boundary": "A5",
        "pre_cognition": True,
        "post_phenotype": True,
        "label": "WHAT THE ORGANISM RECEIVED",
        "left_receptor_channels": left,
        "right_receptor_channels": right,
        "band_identifiers": list(BAND_IDENTIFIERS),
        "band_count": BAND_COUNT,
        "channel_labels": {
            "left": "ORGANISM LEFT RECEPTOR CHANNELS",
            "right": "ORGANISM RIGHT RECEPTOR CHANNELS",
        },
        "clipping_range": [0.0, 1.0],
        "zero_vector_is_legitimate_silence": all(v == 0.0 for v in left + right),
    }
    section_b = {
        "organism_accessible": False,
        "researcher_only": True,
        "label": "RESEARCHER CAUSAL PROVENANCE",
        "phenotype_clip_stamp": stamp,
        "capture_seam": "begin_tick_after_observation_bound_to_cognition",
        "observation_key": observation_key,
        "c0_profile_reference": "ABSTRACT_ACOUSTIC_AUTHORITY_C0_V1",
        "limitations": list(LIMITATIONS),
        "anomalies": list(extracted["anomalies"]),
        "human_binaural_model": False,
        "interaural_time_delay": False,
        "playback": PLAYBACK_DEFERRED,
        "note": (
            "Vectors copied from cognition-bound observation; not recomputed from LPS/stream/probe."
        ),
    }
    return {
        "schema": SCHEMA,
        "receipt_family": RECEIPT_FAMILY,
        "profile": PROFILE,
        "capability": CAPABILITY,
        "boundary": BOUNDARY,
        "view_schema": VIEW_SCHEMA,
        "receipt_id": rid,
        "scientific_tick": int(scientific_tick),
        "run_id": str(run_id),
        "agent_id": str(agent_id),
        "body_id": str(body_id),
        "agent_slot": agent_slot,
        "observation_key": str(observation_key),
        "availability": "AVAILABLE",
        "band_count": BAND_COUNT,
        "band_identifiers": list(BAND_IDENTIFIERS),
        "section_a_organism_accessible": section_a,
        "section_b_researcher_provenance": section_b,
        "researcher_only": True,
        "agent_accessible": False,  # receipt metadata is researcher-only; osc numerics already in obs
        "physical_mechanism": False,
        "physical_preset": False,
        "acoustic_source": False,
        "playback": False,
        "mind_reading": False,
        "semantic_interpretation": False,
    }


def capture_from_observation(
    world: Any,
    *,
    observation: dict[str, Any] | None,
    scientific_tick: int,
    agent_id: str,
    body_id: str,
    agent_slot: int | None = None,
    run_id: str = "live",
    observation_key: str | None = None,
    config: Any = None,
    body: Any = None,
    experimenter: bool = False,
) -> dict[str, Any] | None:
    """Append at most one receipt for this observation identity. Idempotent."""
    if not isinstance(observation, dict):
        return None
    st = ensure_state(world)
    from mechanistic_mind.scientific_v3.ids import observation_id as _oid

    okey = observation_key or _oid(str(run_id), int(scientific_tick), str(agent_id))
    # Dedup by deterministic receipt id
    rid_probe = receipt_id(
        run_id=str(run_id),
        scientific_tick=int(scientific_tick),
        agent_id=str(agent_id),
        body_id=str(body_id),
        observation_key=str(okey),
    )
    if st.receipts and st.receipts[-1].get("receipt_id") == rid_probe:
        st.deduplicated_count += 1
        return st.receipts[-1]
    for r in st.receipts:
        if r.get("receipt_id") == rid_probe:
            st.deduplicated_count += 1
            return r

    rec = build_receipt(
        observation=observation,
        scientific_tick=int(scientific_tick),
        agent_id=str(agent_id),
        body_id=str(body_id),
        agent_slot=agent_slot,
        run_id=str(run_id),
        observation_key=str(okey),
        config=config,
        world=world,
        body=body,
        experimenter=experimenter,
    )
    if rec is None:
        return None
    st.receipts.append(rec)
    st.capture_count += 1
    st.last_receipt_id = rec.get("receipt_id")
    st.last_capture_tick = int(scientific_tick)
    while len(st.receipts) > int(st.capacity):
        st.receipts.pop(0)
        st.evicted_count += 1
    return rec


def serialize_state(st: SelectedOrganismAuditoryBoundaryState | None) -> dict[str, Any] | None:
    if st is None:
        return None
    return {
        "schema_version": STATE_SCHEMA,
        "researcher_configuration": True,
        "physical_state": False,
        "capacity": int(st.capacity),
        "receipts": list(st.receipts),
        "evicted_count": int(st.evicted_count),
        "capture_count": int(st.capture_count),
        "deduplicated_count": int(st.deduplicated_count),
        "last_receipt_id": st.last_receipt_id,
        "last_capture_tick": st.last_capture_tick,
        "no_replay_into_cognition": True,
        "playback": False,
    }


def restore_state(world: Any, data: dict[str, Any] | None) -> SelectedOrganismAuditoryBoundaryState | None:
    if not data:
        return None
    if str(data.get("schema_version") or "") not in (STATE_SCHEMA, SCHEMA):
        return None
    st = SelectedOrganismAuditoryBoundaryState(
        capacity=int(data.get("capacity") or HISTORY_CAPACITY_DEFAULT),
        receipts=[dict(r) for r in (data.get("receipts") or []) if isinstance(r, dict)],
        evicted_count=int(data.get("evicted_count") or 0),
        capture_count=int(data.get("capture_count") or 0),
        deduplicated_count=int(data.get("deduplicated_count") or 0),
        last_receipt_id=data.get("last_receipt_id"),
        last_capture_tick=data.get("last_capture_tick"),
    )
    setattr(world, WORLD_ATTR, st)
    return st


def observer_payload(
    world: Any,
    *,
    selected_agent_id: str | None = None,
) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    receipts = list(st.receipts)
    selected = None
    if selected_agent_id:
        for r in reversed(receipts):
            if str(r.get("agent_id")) == str(selected_agent_id):
                selected = r
                break
    elif receipts:
        selected = receipts[-1]
    agent_hist = [
        r for r in receipts
        if selected_agent_id is None or str(r.get("agent_id")) == str(selected_agent_id)
    ]
    agent_ids = sorted({str(r.get("agent_id")) for r in receipts if r.get("agent_id")})
    latest_by_agent: dict[str, Any] = {}
    for r in receipts:
        aid = str(r.get("agent_id") or "")
        if aid:
            latest_by_agent[aid] = r
    return {
        "schema": VIEW_SCHEMA,
        "capability": CAPABILITY,
        "mode_label": MODE_LABEL,
        "warning_label": WARNING_LABEL,
        "boundary": BOUNDARY,
        "profile": PROFILE,
        "receipt_schema": SCHEMA,
        "researcher_only": True,
        "agent_accessible": False,
        "playback": False,
        "playback_status": PLAYBACK_DEFERRED,
        "mind_reading": False,
        "history_capacity": st.capacity,
        "retained_count": len(receipts),
        "evicted_count": st.evicted_count,
        "capture_count": st.capture_count,
        "deduplicated_count": st.deduplicated_count,
        "selected_agent_id": selected_agent_id,
        "available_agent_ids": agent_ids,
        "latest_by_agent": latest_by_agent,
        "latest_for_selected": selected,
        "recent_for_selected": agent_hist[-12:],
        "channel_labels": {
            "left": "ORGANISM LEFT RECEPTOR CHANNELS",
            "right": "ORGANISM RIGHT RECEPTOR CHANNELS",
        },
        "limitations": list(LIMITATIONS),
    }


def profile_reference() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "receipt_family": RECEIPT_FAMILY,
        "view_schema": VIEW_SCHEMA,
        "profile": PROFILE,
        "capability": CAPABILITY,
        "boundary": BOUNDARY,
        "mode_label": MODE_LABEL,
        "warning_label": WARNING_LABEL,
        "band_count": BAND_COUNT,
        "history_capacity_default": HISTORY_CAPACITY_DEFAULT,
        "playback": False,
        "researcher_only": True,
        "agent_accessible": False,
    }
