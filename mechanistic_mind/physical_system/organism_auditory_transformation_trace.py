"""ORGANISM_AUDITORY_TRANSFORMATION_TRACE_V1 — durable A3→A5 scientific linkage.

Researcher-only. Copies exact A3 from tick-stamped LPS ``st.auditory`` at the
SAV1/observation seam and links to the exact A5 vectors frozen in SAV1.
Does not re-run LPS, receptor geometry, attenuation, or phenotype for agent input.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any

SCHEMA = "ORGANISM_AUDITORY_TRANSFORMATION_TRACE_V1"
RECEIPT_FAMILY = "ORGANISM_AUDITORY_TRANSFORMATION_TRACE"
PROFILE = "AUDITORY_A3_TO_A5_TRANSFORMATION_TRACE_V1"
A3_BOUNDARY = "A3_RAW_LR_RECEPTOR_BAND_ENERGY_PRE_PHENOTYPE"
A4_TRANSFORM = "A4_SENSOR_SCALE_CLIP_V1"
TARGET_A5_SCHEMA = "SELECTED_ORGANISM_AUDITORY_BOUNDARY_RECEIPT_V1"
A5_BOUNDARY = "A5_OSC_LR_ACCESSIBLE_OBSERVATION_PRE_COGNITION"
AUTHORITY = "RESEARCHER_SCIENTIFIC_TRACE_READ_ONLY"
STATE_SCHEMA = "ORGANISM_AUDITORY_TRANSFORMATION_TRACE_STATE_V1"
WORLD_ATTR = "organism_auditory_transformation_trace_state"
CAPABILITY = "organism_auditory_transformation_trace"

STATUS_LINKED = "LINKED_COMPLETE"
STATUS_A5_UNAVAILABLE = "A5_UNAVAILABLE"
STATUS_TICK_MISMATCH = "TICK_IDENTITY_MISMATCH"
STATUS_EXPERIMENTER_NA = "EXPERIMENTER_AUDITORY_TRANSFORMATION_TRACE_NOT_AVAILABLE"
STATUS_MISMATCH = "A3_A4_A5_TRANSFORM_MISMATCH"
LEGACY_UNAVAILABLE = "ORGANISM_AUDITORY_TRANSFORMATION_TRACE_UNAVAILABLE_LEGACY_EVIDENCE"

BAND_COUNT = 6
BAND_IDENTIFIERS = tuple(f"band_{i}" for i in range(BAND_COUNT))
HISTORY_CAPACITY_DEFAULT = 128
RESIDUAL_TOLERANCE = 1e-12
A2_GATE_NOTE = "A2_GATE_AGGREGATE_NOT_CAPTURED_V1"
CONTRIBUTOR_POLICY = "CONTRIBUTOR_DECOMPOSITION_NOT_AVAILABLE_AFTER_SUMMATION"
GEOMETRY_POS_NOTE = "RECEPTOR_POSITIONS_NOT_RECOMPUTED_V1"

NE = "NOT_ESTABLISHED"
NA = "NOT_AVAILABLE"

LIMITATIONS = (
    "XY_ONLY_LPS",
    "NO_Z_DISTANCE",
    "NO_INTERAURAL_TIME_DELAY",
    "NO_HRTF",
    "NO_OCCLUSION",
    "NO_REFLECTION",
    "NO_REVERB",
    CONTRIBUTOR_POLICY,
    "NO_SUBJECTIVE_EXPERIENCE_CLAIM",
    "A3_RESEARCHER_ONLY",
    "NOT_PASSIVE_PROBE",
    "NOT_A5_INVERSION",
)


@dataclass
class OrganismAuditoryTransformationTraceState:
    schema_version: str = STATE_SCHEMA
    capacity: int = HISTORY_CAPACITY_DEFAULT
    traces: list[dict[str, Any]] = field(default_factory=list)
    evicted_count: int = 0
    completed_count: int = 0
    orphaned_count: int = 0  # reserved; atomic capture leaves this at 0
    mismatch_count: int = 0
    deduplicated_count: int = 0
    capture_count: int = 0
    last_trace_id: str | None = None
    last_capture_tick: int | None = None


def ensure_state(world: Any) -> OrganismAuditoryTransformationTraceState:
    st = getattr(world, WORLD_ATTR, None)
    if isinstance(st, OrganismAuditoryTransformationTraceState):
        return st
    st = OrganismAuditoryTransformationTraceState()
    setattr(world, WORLD_ATTR, st)
    return st


def state_of(world: Any) -> OrganismAuditoryTransformationTraceState | None:
    st = getattr(world, WORLD_ATTR, None)
    return st if isinstance(st, OrganismAuditoryTransformationTraceState) else None


def clip01(x: float) -> float:
    return float(max(0.0, min(1.0, float(x))))


def expected_a5_from_a3(
    left: list[float],
    right: list[float],
    sensor_scale: float,
) -> tuple[list[float], list[float], list[bool], list[bool], list[bool], list[bool], int]:
    """Researcher-only A4 verification. Does not supply agent observation."""
    scale = max(1e-9, float(sensor_scale))
    el: list[float] = []
    er: list[float] = []
    lower_l: list[bool] = []
    upper_l: list[bool] = []
    lower_r: list[bool] = []
    upper_r: list[bool] = []
    clip_n = 0
    for i in range(BAND_COUNT):
        rl = float(left[i]) if i < len(left) else 0.0
        rr = float(right[i]) if i < len(right) else 0.0
        pre_l = rl / scale
        pre_r = rr / scale
        ul = pre_l > 1.0 + 1e-15
        ll = pre_l < -1e-15
        ur = pre_r > 1.0 + 1e-15
        lr = pre_r < -1e-15
        # Also count saturation at bound after clip when raw/scale outside [0,1]
        if ul or ll:
            clip_n += 1
        if ur or lr:
            clip_n += 1
        upper_l.append(bool(ul))
        lower_l.append(bool(ll))
        upper_r.append(bool(ur))
        lower_r.append(bool(lr))
        el.append(clip01(pre_l))
        er.append(clip01(pre_r))
    return el, er, lower_l, upper_l, lower_r, upper_r, clip_n


def residual_vectors(
    expected_l: list[float],
    expected_r: list[float],
    actual_l: list[float],
    actual_r: list[float],
) -> dict[str, Any]:
    res_l = [abs(float(expected_l[i]) - float(actual_l[i])) for i in range(BAND_COUNT)]
    res_r = [abs(float(expected_r[i]) - float(actual_r[i])) for i in range(BAND_COUNT)]
    max_r = max(res_l + res_r) if res_l or res_r else 0.0
    return {
        "per_band_abs_residual_left": res_l,
        "per_band_abs_residual_right": res_r,
        "max_abs_residual": float(max_r),
        "within_tolerance": bool(max_r <= RESIDUAL_TOLERANCE),
        "tolerance": float(RESIDUAL_TOLERANCE),
    }


def per_band_loss_rows(
    a3_l: list[float],
    a3_r: list[float],
    a5_l: list[float],
    a5_r: list[float],
    sensor_scale: float,
    lower_l: list[bool],
    upper_l: list[bool],
    lower_r: list[bool],
    upper_r: list[bool],
    res_l: list[float],
    res_r: list[float],
) -> list[dict[str, Any]]:
    scale = max(1e-9, float(sensor_scale))
    rows: list[dict[str, Any]] = []
    for i in range(BAND_COUNT):
        for side, a3, a5, lo, up, res in (
            ("left", a3_l[i], a5_l[i], lower_l[i], upper_l[i], res_l[i]),
            ("right", a3_r[i], a5_r[i], lower_r[i], upper_r[i], res_r[i]),
        ):
            scaled = float(a3) / scale
            rows.append(
                {
                    "band": BAND_IDENTIFIERS[i],
                    "side": side,
                    "raw_a3": float(a3),
                    "scaled_pre_clip": float(scaled),
                    "final_a5": float(a5),
                    "scale_ratio": float(1.0 / scale),
                    "lower_clipped": bool(lo),
                    "upper_clipped": bool(up),
                    "zero_preserved": bool(float(a3) == 0.0 and float(a5) == 0.0),
                    "residual": float(res),
                }
            )
    return rows


def _sensor_scale(world: Any, config: Any) -> float:
    lps = getattr(world, "local_signal_transport", None) if world is not None else None
    if lps is not None:
        return float(getattr(getattr(lps, "config", None), "sensor_scale", 2.0) or 2.0)
    osc = getattr(config, "oscillatory_signaling", None) if config is not None else None
    if osc is not None:
        return float(getattr(osc, "field_cap", 2.0) or 2.0)
    return 2.0


def _heading_stamp(config: Any, body: Any) -> dict[str, Any]:
    head_cfg = getattr(config, "articulated_head", None) if config is not None else None
    head_on = bool(getattr(head_cfg, "enabled", False)) if head_cfg else False
    body_heading = float(getattr(body, "theta", 0.0) or 0.0) if body is not None else NE
    head_heading: Any = NE
    if head_on and body is not None:
        try:
            from mechanistic_mind.physical_system.oscillatory_signaling import head_world_heading

            head_heading = float(head_world_heading(body))
        except Exception:
            head_heading = NE
    return {
        "heading_authority": "HEAD_WORLD_HEADING" if head_on else "BODY_THETA",
        "articulated_head_enabled": head_on,
        "body_heading": body_heading,
        "head_heading": head_heading,
        "left_receptor_position": GEOMETRY_POS_NOTE,
        "right_receptor_position": GEOMETRY_POS_NOTE,
        "receptor_geometry_profile": "OSC_RECEPTOR_OFFSET_HEAD_LINKED_V1",
    }


def _config_digest(*, sensor_scale: float, heading_authority: str, receptor_offset: Any) -> str:
    src = {
        "sensor_scale": sensor_scale,
        "heading_authority": heading_authority,
        "receptor_offset": receptor_offset,
        "band_count": BAND_COUNT,
        "clip_range": [0.0, 1.0],
        "a4_transform": A4_TRANSFORM,
        "profile": PROFILE,
    }
    return hashlib.sha256(
        json.dumps(src, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:16]


def read_a3_from_auditory_buffer(
    world: Any,
    *,
    body: Any,
    body_id: str,
    observation_tick: int,
) -> dict[str, Any]:
    """Copy exact A3 from LPS auditory buffer. No LPS/receptor recompute."""
    lps = getattr(world, "local_signal_transport", None)
    if lps is None:
        return {
            "status": "LPS_INACTIVE",
            "reception_tick": None,
            "left": [0.0] * BAND_COUNT,
            "right": [0.0] * BAND_COUNT,
            "accepted_contributor_count": 0,
            "tick_match": False,
            "source_buffer_authority": "NONE",
            "raw_vector_finite": True,
        }
    bid = getattr(body, "_lps_body_id", None) if body is not None else None
    if bid is None:
        bid = body_id
    entry = (getattr(lps, "auditory", None) or {}).get(str(bid))
    world_tick = int(getattr(world, "tick", -2))
    if entry is None:
        # Same semantics as auditory_fragments: absent → zero energy this tick.
        return {
            "status": "NO_RECEPTION_ENTRY",
            "reception_tick": int(observation_tick),
            "left": [0.0] * BAND_COUNT,
            "right": [0.0] * BAND_COUNT,
            "accepted_contributor_count": 0,
            "tick_match": int(world_tick) == int(observation_tick),
            "source_buffer_authority": "LPS_AUDITORY_ABSENT_EQUALS_ZERO",
            "raw_vector_finite": True,
        }
    recv_tick = int(entry.get("tick", -1))
    left_raw = list(entry.get("left") or [])
    right_raw = list(entry.get("right") or [])
    left = [float(left_raw[i]) if i < len(left_raw) else 0.0 for i in range(BAND_COUNT)]
    right = [float(right_raw[i]) if i < len(right_raw) else 0.0 for i in range(BAND_COUNT)]
    finite = all(math.isfinite(v) for v in left + right)
    tick_match = recv_tick == int(observation_tick) and world_tick == int(observation_tick)
    return {
        "status": "CAPTURED" if tick_match else "TICK_MISMATCH",
        "reception_tick": recv_tick,
        "left": left,
        "right": right,
        "accepted_contributor_count": int(entry.get("n", 0) or 0),
        "tick_match": bool(tick_match),
        "source_buffer_authority": "LPS_AUDITORY_BUFFER_ST_AUDITORY",
        "raw_vector_finite": bool(finite),
    }


def a3_capture_key(
    *,
    run_id: str,
    body_id: str,
    reception_tick: int,
) -> str:
    raw = f"{SCHEMA}|A3|{run_id}|{body_id}|{int(reception_tick)}"
    return f"oatt-a3:{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"


def trace_id(
    *,
    run_id: str,
    agent_id: str,
    body_id: str,
    reception_tick: int,
    observation_tick: int,
    observation_key: str,
    sav1_receipt_id: str,
) -> str:
    raw = (
        f"{SCHEMA}|{run_id}|{agent_id}|{body_id}|"
        f"{int(reception_tick)}|{int(observation_tick)}|{observation_key}|{sav1_receipt_id}"
    )
    return f"oatt:{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:20]}"


def extract_a5_from_sav1_or_observation(
    sav1_receipt: dict[str, Any] | None,
    observation: dict[str, Any] | None,
) -> dict[str, Any]:
    if isinstance(sav1_receipt, dict):
        sec = sav1_receipt.get("section_a_organism_accessible") or {}
        left = list(sec.get("left_receptor_channels") or [])
        right = list(sec.get("right_receptor_channels") or [])
        if len(left) >= BAND_COUNT and len(right) >= BAND_COUNT:
            return {
                "present": True,
                "left": [float(left[i]) for i in range(BAND_COUNT)],
                "right": [float(right[i]) for i in range(BAND_COUNT)],
                "sav1_receipt_id": sav1_receipt.get("receipt_id"),
            }
    obs = observation if isinstance(observation, dict) else {}
    left: list[float] = []
    right: list[float] = []
    present = False
    for i in range(BAND_COUNT):
        lk, rk = f"osc_l_{i}", f"osc_r_{i}"
        if lk in obs or rk in obs:
            present = True
        try:
            lv = float(obs.get(lk, 0.0) or 0.0) if lk in obs else 0.0
        except (TypeError, ValueError):
            lv = 0.0
        try:
            rv = float(obs.get(rk, 0.0) or 0.0) if rk in obs else 0.0
        except (TypeError, ValueError):
            rv = 0.0
        left.append(lv)
        right.append(rv)
    return {
        "present": present,
        "left": left,
        "right": right,
        "sav1_receipt_id": None,
    }


def build_linked_trace(
    *,
    world: Any,
    observation: dict[str, Any],
    scientific_tick: int,
    agent_id: str,
    body_id: str,
    agent_slot: int | None,
    run_id: str,
    observation_key: str,
    config: Any = None,
    body: Any = None,
    sav1_receipt: dict[str, Any] | None = None,
    experimenter: bool = False,
) -> dict[str, Any] | None:
    """Build one completed A3↔A5 linkage trace. Researcher-only."""
    a5 = extract_a5_from_sav1_or_observation(sav1_receipt, observation)
    if not a5["present"]:
        if experimenter:
            return {
                "schema": SCHEMA,
                "receipt_family": RECEIPT_FAMILY,
                "profile": PROFILE,
                "availability": STATUS_EXPERIMENTER_NA,
                "completion_status": STATUS_EXPERIMENTER_NA,
                "scientific_tick": int(scientific_tick),
                "observation_tick": int(scientific_tick),
                "agent_id": str(agent_id),
                "body_id": str(body_id),
                "agent_slot": agent_slot,
                "researcher_only": True,
                "agent_accessible": False,
                "physical_mechanism": False,
                "authority": AUTHORITY,
            }
        return None

    a3 = read_a3_from_auditory_buffer(
        world, body=body, body_id=str(body_id), observation_tick=int(scientific_tick)
    )
    reception_tick = int(a3["reception_tick"] if a3["reception_tick"] is not None else scientific_tick)
    observation_tick = int(scientific_tick)
    causal_delay = int(observation_tick - reception_tick)

    completion = STATUS_LINKED
    if not a3.get("tick_match", False) and a3.get("status") == "TICK_MISMATCH":
        completion = STATUS_TICK_MISMATCH
        causal_delay = int(observation_tick - reception_tick)

    sensor_scale = _sensor_scale(world, config)
    osc = getattr(config, "oscillatory_signaling", None) if config is not None else None
    receptor_offset = float(getattr(osc, "receptor_offset", 0.55) or 0.55) if osc is not None else NE
    heading = _heading_stamp(config, body)
    digest = _config_digest(
        sensor_scale=sensor_scale,
        heading_authority=str(heading["heading_authority"]),
        receptor_offset=receptor_offset,
    )

    a3_l = list(a3["left"])
    a3_r = list(a3["right"])
    a5_l = list(a5["left"])
    a5_r = list(a5["right"])
    exp_l, exp_r, lo_l, up_l, lo_r, up_r, clip_n = expected_a5_from_a3(a3_l, a3_r, sensor_scale)
    resid = residual_vectors(exp_l, exp_r, a5_l, a5_r)
    if not resid["within_tolerance"]:
        completion = STATUS_MISMATCH

    sav1_id = str(
        a5.get("sav1_receipt_id")
        or (sav1_receipt or {}).get("receipt_id")
        or NA
    )
    tid = trace_id(
        run_id=str(run_id),
        agent_id=str(agent_id),
        body_id=str(body_id),
        reception_tick=reception_tick,
        observation_tick=observation_tick,
        observation_key=str(observation_key),
        sav1_receipt_id=sav1_id,
    )
    a3_key = a3_capture_key(run_id=str(run_id), body_id=str(body_id), reception_tick=reception_tick)

    loss_rows = per_band_loss_rows(
        a3_l, a3_r, a5_l, a5_r, sensor_scale, lo_l, up_l, lo_r, up_r,
        resid["per_band_abs_residual_left"], resid["per_band_abs_residual_right"],
    )

    return {
        "schema": SCHEMA,
        "receipt_family": RECEIPT_FAMILY,
        "profile": PROFILE,
        "capability": CAPABILITY,
        "authority": AUTHORITY,
        "trace_id": tid,
        "run_id": str(run_id),
        "agent_id": str(agent_id),
        "body_id": str(body_id),
        "agent_slot": agent_slot,
        "reception_tick": reception_tick,
        "observation_tick": observation_tick,
        "scientific_tick": observation_tick,
        "causal_delay_ticks": causal_delay,
        "a3_capture_key": a3_key,
        "observation_key": str(observation_key),
        "sav1_receipt_id": sav1_id,
        "completion_status": completion,
        "availability": "AVAILABLE" if completion in (STATUS_LINKED, STATUS_MISMATCH) else completion,
        "capture_seam": "begin_tick_atomic_read_of_tick_stamped_lps_auditory_buffer",
        "pending_policy": "NOT_USED_ATOMIC_CAPTURE_V1",
        "a3": {
            "boundary": A3_BOUNDARY,
            "authority_class": "AUTHORITATIVE_PHYSICAL_RECEPTOR_STATE_RESEARCHER_ONLY",
            "left_receptor_band_energy": a3_l,
            "right_receptor_band_energy": a3_r,
            "band_count": BAND_COUNT,
            "band_identifiers": list(BAND_IDENTIFIERS),
            "source_buffer_authority": a3["source_buffer_authority"],
            "buffer_status": a3["status"],
            "accepted_contributor_count": int(a3["accepted_contributor_count"]),
            "body_centre_acceptance_count": int(a3["accepted_contributor_count"]),
            "raw_vector_finite": bool(a3["raw_vector_finite"]),
            "normalized": False,
            "agent_accessible": False,
            **heading,
            "sensor_configuration_digest": digest,
            "receptor_offset": receptor_offset,
        },
        "a2_gate_metadata": {
            "status": A2_GATE_NOTE,
            "accepted_contributor_count": int(a3["accepted_contributor_count"]),
            "note": "Compact count from auditory['n'] only; no second reception pass.",
        },
        "a4": {
            "transform": A4_TRANSFORM,
            "authority_class": "DETERMINISTIC_RESEARCHER_DERIVATION",
            "formula": "A5[k]=clip(A3[k]/sensor_scale,0,1)",
            "sensor_scale": float(sensor_scale),
            "clip_lower": 0.0,
            "clip_upper": 1.0,
            "phenotype_config_digest": digest,
            "expected_a5_left": exp_l,
            "expected_a5_right": exp_r,
            "per_band_lower_clipped_left": lo_l,
            "per_band_upper_clipped_left": up_l,
            "per_band_lower_clipped_right": lo_r,
            "per_band_upper_clipped_right": up_r,
            "clipping_count": int(clip_n),
            "transform_residual": resid,
            "per_band_loss_accounting": loss_rows,
            "agent_accessible": False,
        },
        "a5": {
            "boundary": A5_BOUNDARY,
            "target_schema": TARGET_A5_SCHEMA,
            "authority_class": "AUTHORITATIVE_ORGANISM_ACCESSIBLE_OBSERVATION",
            "organism_accessible": True,
            "left_receptor_channels": a5_l,
            "right_receptor_channels": a5_r,
            "sav1_receipt_id": sav1_id,
            "exact_equality_to_expected": bool(resid["within_tolerance"]),
            "tolerance_status": (
                "WITHIN_TOLERANCE" if resid["within_tolerance"] else STATUS_MISMATCH
            ),
        },
        "contributor_policy": CONTRIBUTOR_POLICY,
        "contributor_list": [],
        "contributor_capacity": 0,
        "limitations": list(LIMITATIONS),
        "researcher_only": True,
        "agent_accessible": False,
        "physical_mechanism": False,
        "physical_preset": False,
        "playback": False,
        "mind_reading": False,
        "semantic_interpretation": False,
        "provenance_authority_class": "RESEARCHER_ONLY",
    }


def capture_linked_to_sav1(
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
    sav1_receipt: dict[str, Any] | None = None,
    experimenter: bool = False,
) -> dict[str, Any] | None:
    """Append at most one completed trace per observation identity. Idempotent."""
    if not isinstance(observation, dict):
        return None
    st = ensure_state(world)
    from mechanistic_mind.scientific_v3.ids import observation_id as _oid

    okey = observation_key or _oid(str(run_id), int(scientific_tick), str(agent_id))
    sav1_id = str((sav1_receipt or {}).get("receipt_id") or NA)
    # Provisional id uses reception≈observation under atomic policy for dedup probe
    tid_probe = trace_id(
        run_id=str(run_id),
        agent_id=str(agent_id),
        body_id=str(body_id),
        reception_tick=int(scientific_tick),
        observation_tick=int(scientific_tick),
        observation_key=str(okey),
        sav1_receipt_id=sav1_id,
    )
    for tr in st.traces:
        if tr.get("trace_id") == tid_probe:
            st.deduplicated_count += 1
            return tr
        # Also dedup by observation_key + agent (polling)
        if (
            tr.get("observation_key") == okey
            and tr.get("agent_id") == str(agent_id)
            and tr.get("body_id") == str(body_id)
            and tr.get("observation_tick") == int(scientific_tick)
        ):
            st.deduplicated_count += 1
            return tr

    tr = build_linked_trace(
        world=world,
        observation=observation,
        scientific_tick=int(scientific_tick),
        agent_id=str(agent_id),
        body_id=str(body_id),
        agent_slot=agent_slot,
        run_id=str(run_id),
        observation_key=str(okey),
        config=config,
        body=body,
        sav1_receipt=sav1_receipt,
        experimenter=experimenter,
    )
    if tr is None:
        return None
    # Re-check actual trace_id (may differ if reception_tick ≠ observation under mismatch)
    for existing in st.traces:
        if existing.get("trace_id") == tr.get("trace_id"):
            st.deduplicated_count += 1
            return existing

    st.traces.append(tr)
    st.capture_count += 1
    if tr.get("completion_status") == STATUS_LINKED:
        st.completed_count += 1
    if tr.get("completion_status") == STATUS_MISMATCH:
        st.mismatch_count += 1
        st.completed_count += 1
    st.last_trace_id = tr.get("trace_id")
    st.last_capture_tick = int(scientific_tick)
    while len(st.traces) > int(st.capacity):
        st.traces.pop(0)
        st.evicted_count += 1
    return tr


def serialize_state(st: OrganismAuditoryTransformationTraceState | None) -> dict[str, Any] | None:
    if st is None:
        return None
    return {
        "schema_version": STATE_SCHEMA,
        "researcher_configuration": True,
        "physical_state": False,
        "capacity": int(st.capacity),
        "traces": list(st.traces),
        "evicted_count": int(st.evicted_count),
        "completed_count": int(st.completed_count),
        "orphaned_count": int(st.orphaned_count),
        "mismatch_count": int(st.mismatch_count),
        "deduplicated_count": int(st.deduplicated_count),
        "capture_count": int(st.capture_count),
        "last_trace_id": st.last_trace_id,
        "last_capture_tick": st.last_capture_tick,
        "pending_policy": "NOT_USED_ATOMIC_CAPTURE_V1",
        "no_replay_into_cognition": True,
        "playback": False,
        "authority": AUTHORITY,
    }


def restore_state(
    world: Any, data: dict[str, Any] | None
) -> OrganismAuditoryTransformationTraceState | None:
    """Restore scientific history only. Never regenerates A3, SAV1, or LPS."""
    if not data:
        return None
    if str(data.get("schema_version") or "") not in (STATE_SCHEMA, SCHEMA):
        return None
    st = OrganismAuditoryTransformationTraceState(
        schema_version=STATE_SCHEMA,
        capacity=int(data.get("capacity", HISTORY_CAPACITY_DEFAULT) or HISTORY_CAPACITY_DEFAULT),
        traces=[copy.deepcopy(t) for t in (data.get("traces") or []) if isinstance(t, dict)],
        evicted_count=int(data.get("evicted_count", 0) or 0),
        completed_count=int(data.get("completed_count", 0) or 0),
        orphaned_count=int(data.get("orphaned_count", 0) or 0),
        mismatch_count=int(data.get("mismatch_count", 0) or 0),
        deduplicated_count=int(data.get("deduplicated_count", 0) or 0),
        capture_count=int(data.get("capture_count", 0) or 0),
        last_trace_id=data.get("last_trace_id"),
        last_capture_tick=(
            int(data["last_capture_tick"]) if data.get("last_capture_tick") is not None else None
        ),
    )
    setattr(world, WORLD_ATTR, st)
    return st


def observer_compact_status(world: Any) -> dict[str, Any]:
    """Minimal HEARING status line payload (optional UI)."""
    st = state_of(world)
    if st is None:
        return {
            "schema": SCHEMA,
            "active": False,
            "status": LEGACY_UNAVAILABLE,
            "retained": 0,
            "mismatches": 0,
        }
    return {
        "schema": SCHEMA,
        "profile": PROFILE,
        "active": True,
        "status": "A3_TRACE_ACTIVE",
        "retained": len(st.traces),
        "capacity": int(st.capacity),
        "completed": int(st.completed_count),
        "mismatches": int(st.mismatch_count),
        "evicted": int(st.evicted_count),
        "orphaned": int(st.orphaned_count),
        "deduplicated": int(st.deduplicated_count),
        "last_trace_id": st.last_trace_id,
        "authority": AUTHORITY,
        "playback": False,
        "label": (
            f"SAV3 trace prerequisite: A3 trace active · retained {len(st.traces)} · "
            f"mismatches {int(st.mismatch_count)}"
        ),
    }


def profile_reference() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "profile": PROFILE,
        "a3_boundary": A3_BOUNDARY,
        "a4_transform": A4_TRANSFORM,
        "target_a5_schema": TARGET_A5_SCHEMA,
        "authority": AUTHORITY,
        "residual_tolerance": RESIDUAL_TOLERANCE,
        "history_capacity": HISTORY_CAPACITY_DEFAULT,
        "pending_policy": "NOT_USED_ATOMIC_CAPTURE_V1",
        "contributor_policy": CONTRIBUTOR_POLICY,
        "limitations": list(LIMITATIONS),
    }
