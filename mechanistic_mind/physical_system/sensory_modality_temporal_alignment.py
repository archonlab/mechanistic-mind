"""Acanthostega O5 · Sensory modality temporal alignment contract V1.

Schema: SENSORY_MODALITY_TEMPORAL_ALIGNMENT_CONTRACT_V1
Capability: sensory_modality_temporal_alignment
Profile: PHYSICAL_EVENT_RECEPTOR_OBSERVATION_TICK_ENVELOPE_O5_V1
Authority: RESEARCHER_AND_CAUSAL_METADATA_OVER_EXISTING_MODALITY_TIMING

Read-only per-agent observation envelope referencing existing modality timing.
Does NOT change O4/LPS/OATT/osc/exo numerics or cognition schema.
Does NOT merge modalities into a perception vector.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

SCHEMA = "SENSORY_MODALITY_TEMPORAL_ALIGNMENT_CONTRACT_V1"
CAPABILITY = "sensory_modality_temporal_alignment"
PROFILE = "PHYSICAL_EVENT_RECEPTOR_OBSERVATION_TICK_ENVELOPE_O5_V1"
AUTHORITY = "RESEARCHER_AND_CAUSAL_METADATA_OVER_EXISTING_MODALITY_TIMING"
MECHANISM_ID = CAPABILITY

# Availability taxonomy
AVAIL_NONZERO = "AVAILABLE_NONZERO"
AVAIL_TRUE_ZERO = "AVAILABLE_TRUE_ZERO"
MISSING_NOT_CAPTURED = "MISSING_NOT_CAPTURED"
MISSING_LEGACY = "MISSING_LEGACY_SCHEMA"
MISSING_INCOMPATIBLE = "MISSING_INCOMPATIBLE_PROFILE"
NOT_APPLICABLE = "NOT_APPLICABLE"
TRUNCATED_PROVENANCE = "TRUNCATED_PROVENANCE"

# Alignment statuses (Observer)
STATUS_ALIGNED_OBS = "EXPLICITLY_ALIGNED_AT_OBSERVATION"
STATUS_ALIGNED_DIFF_PHYS = "ALIGNED_OBSERVATION_DIFFERENT_PHYSICAL_EVENT_TIMES"
STATUS_PARTIAL = "PARTIAL_TIMING"
STATUS_LEGACY = "LEGACY_TIMING_UNAVAILABLE"
STATUS_GEN_MISMATCH = "GENERATION_MISMATCH"
STATUS_STALE_PREVENTED = "STALE_PAIRING_PREVENTED"

MAX_ENVELOPE_HISTORY = 64
MAX_SOURCE_EVENT_REFS = 8

AUTHORITY_FLAGS = {
    "schema": SCHEMA,
    "capability": CAPABILITY,
    "profile": PROFILE,
    "authority": AUTHORITY,
    "changes_sensory_numerics": False,
    "changes_cognition_schema": False,
    "researcher_only": True,
    "agent_accessible": False,
    "researcher_presentation_tick_is_scientific_authority": False,
    "oatt_delay_is_receptor_to_observation_not_lps_transport": True,
    "labels": [
        "SCIENTIFIC TICKS · NOT WALL TIME",
        "MODALITIES MAY REPRESENT DIFFERENT PHYSICAL EVENT TIMES",
        "OATT DELAY IS RECEPTOR→OBSERVATION, NOT LPS TRANSPORT",
    ],
}

WORLD_HISTORY_ATTR = "_o5_alignment_envelopes"
WORLD_LAST_ATTR = "_o5_last_alignment_envelope"
WORLD_COUNTERS_ATTR = "_o5_alignment_counters"


@dataclass
class SensoryModalityTemporalAlignmentConfig:
    enabled: bool = False
    schema: str = SCHEMA
    profile: str = PROFILE
    max_history: int = MAX_ENVELOPE_HISTORY

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "schema": str(self.schema),
            "profile": str(self.profile),
            "max_history": int(self.max_history),
            **AUTHORITY_FLAGS,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "SensoryModalityTemporalAlignmentConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        return cls(
            enabled=bool(data.get("enabled", False)),
            schema=str(data.get("schema") or SCHEMA),
            profile=str(data.get("profile") or PROFILE),
            max_history=int(data.get("max_history", MAX_ENVELOPE_HISTORY) or MAX_ENVELOPE_HISTORY),
        )


def sensory_modality_temporal_alignment_is_active(config: Any) -> bool:
    if config is None or str(getattr(config, "model_line", "") or "").upper() != "ACANTHOSTEGA":
        return False
    cfg = getattr(config, "sensory_modality_temporal_alignment", None)
    return bool(cfg is not None and getattr(cfg, "enabled", False))


def set_sensory_modality_temporal_alignment(config: Any, enabled: bool) -> None:
    if config is None:
        return
    on = bool(enabled) and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"
    cur = getattr(config, "sensory_modality_temporal_alignment", None)
    if cur is None:
        config.sensory_modality_temporal_alignment = SensoryModalityTemporalAlignmentConfig(enabled=on)
    else:
        cur.enabled = on
        cur.schema = SCHEMA
        cur.profile = PROFILE


def sensory_modality_temporal_alignment_catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "enabled": bool(enabled),
        "schema": SCHEMA,
        "profile": PROFILE,
        "authority": AUTHORITY,
        "researcher_only": True,
        "agent_accessible": False,
        "changes_sensory_numerics": False,
        "summary": "Read-only multimodal scientific-tick alignment envelope (O5).",
    }


def _avail_from_values(values: list[float] | None, *, present: bool) -> str:
    if not present:
        return MISSING_NOT_CAPTURED
    if values is None:
        return MISSING_NOT_CAPTURED
    if any(abs(float(v)) > 1e-15 for v in values):
        return AVAIL_NONZERO
    return AVAIL_TRUE_ZERO


def _vision_section(world: Any, observation_tick: int) -> dict[str, Any]:
    tr = getattr(world, "_o4_last_reception_trace", None)
    sample = None
    stash = getattr(world, "_sovv_last_near_field_by_body", None)
    if isinstance(stash, dict) and stash:
        # most recent sample dict
        for v in stash.values():
            if isinstance(v, dict) and v.get("o4_physical_optical_reception"):
                sample = v
                break
            if isinstance(v, dict):
                sample = v
    o4_compact = (sample or {}).get("o4_trace") if isinstance(sample, dict) else None
    if isinstance(tr, dict):
        receptor = tr.get("receptor_sample_tick")
        obs_t = tr.get("organism_observation_tick")
        delay = tr.get("visual_causal_delay_ticks")
        reached = bool(tr.get("physical_signal_reached_receptor"))
        fr = None
        if isinstance(sample, dict):
            fr = sample.get("fragments")
        avail = AVAIL_NONZERO if reached else (
            AVAIL_TRUE_ZERO if isinstance(tr.get("post_clip_intensity"), list) else MISSING_NOT_CAPTURED
        )
        if isinstance(fr, dict):
            avail = _avail_from_values(list(fr.values()), present=True)
        return {
            "modality": "vision",
            "profile": tr.get("profile") or (o4_compact or {}).get("schema"),
            "schema": tr.get("schema") or (o4_compact or {}).get("schema"),
            "physical_event_tick": NOT_APPLICABLE,  # static source — no fabricated emission
            "field_state_tick": (tr.get("generations") or {}).get("source_version"),
            "field_evaluation_tick": receptor,
            "receptor_sample_tick": receptor,
            "organism_observation_tick": obs_t if obs_t is not None else observation_tick,
            "causal_delay_ticks": delay if delay is not None else 0,
            "static_light_emission_event_fabricated": False,
            "o4_trace_ref": {
                "has_full_trace": True,
                "accepted": tr.get("accepted"),
                "physical_signal_reached_receptor": reached,
            },
            "availability": avail,
            "true_zero": avail == AVAIL_TRUE_ZERO,
            "missing_reason": None if avail.startswith("AVAILABLE") else avail,
            "timing_authority": "O4_ORGANISM_PHYSICAL_OPTICAL_RECEPTION",
        }
    if isinstance(o4_compact, dict):
        return {
            "modality": "vision",
            "schema": o4_compact.get("schema"),
            "receptor_sample_tick": observation_tick,
            "organism_observation_tick": observation_tick,
            "causal_delay_ticks": o4_compact.get("visual_causal_delay_ticks", 0),
            "static_light_emission_event_fabricated": False,
            "o4_trace_ref": {"has_full_trace": False, "compact": True},
            "availability": MISSING_NOT_CAPTURED if not o4_compact else (
                AVAIL_NONZERO if o4_compact.get("physical_signal_reached_receptor") else AVAIL_TRUE_ZERO
            ),
            "timing_authority": "O4_COMPACT_TRACE",
        }
    # Legacy near-field without O4
    if isinstance(sample, dict) and sample.get("fragments") is not None:
        return {
            "modality": "vision",
            "schema": "LEGACY_NEAR_FIELD",
            "receptor_sample_tick": sample.get("tick"),
            "organism_observation_tick": observation_tick,
            "causal_delay_ticks": None,
            "availability": MISSING_LEGACY,
            "missing_reason": MISSING_LEGACY,
            "static_light_emission_event_fabricated": False,
            "timing_authority": "LEGACY_NEAR_FIELD",
        }
    return {
        "modality": "vision",
        "availability": MISSING_NOT_CAPTURED,
        "missing_reason": MISSING_NOT_CAPTURED,
        "static_light_emission_event_fabricated": False,
        "timing_authority": "NONE",
    }


def _hearing_section(world: Any, body: Any, observation_tick: int, body_id: str) -> dict[str, Any]:
    # LPS auditory stamp + reception_history (bounded distinct source refs)
    reception_tick = None
    source_refs: list[dict[str, Any]] = []
    transport_delays: list[int] = []
    try:
        st = getattr(world, "local_signal_transport", None)
        auditory = getattr(st, "auditory", None) if st is not None else None
        if isinstance(auditory, dict):
            row = auditory.get(str(body_id))
            if row is None:
                for k, v in auditory.items():
                    if str(k) == str(body_id):
                        row = v
                        break
            if isinstance(row, dict):
                reception_tick = row.get("tick")
        hist = list(getattr(st, "reception_history", None) or []) if st is not None else []
        for rec in reversed(hist):
            if not isinstance(rec, dict):
                continue
            if str(rec.get("receiver_body_id") or "") != str(body_id):
                continue
            if reception_tick is not None and int(rec.get("arrival_tick", -1)) != int(reception_tick):
                # Prefer receipts matching current auditory stamp tick
                if int(rec.get("arrival_tick", -1)) != int(observation_tick):
                    continue
            if not rec.get("accepted", True):
                continue
            et = rec.get("emission_tick")
            eid = rec.get("emission_id")
            delay = rec.get("propagation_delay")
            if et is None:
                continue
            if delay is None and reception_tick is not None:
                delay = int(reception_tick) - int(et)
            if delay is None:
                continue
            delay_i = int(delay)
            if delay_i < 1:
                continue
            source_refs.append({
                "emission_id": eid,
                "physical_event_tick": int(et),
                "source_to_receptor_propagation_delay_ticks": delay_i,
            })
            transport_delays.append(delay_i)
            if len(source_refs) >= MAX_SOURCE_EVENT_REFS:
                break
        source_refs.reverse()
        transport_delays.reverse()
    except Exception:
        pass

    # OATT state (researcher history)
    oatt = None
    try:
        oatt_st = getattr(world, "organism_auditory_transformation_trace_state", None)
        traces = list(getattr(oatt_st, "traces", None) or []) if oatt_st is not None else []
        if not traces and isinstance(oatt_st, dict):
            traces = list(oatt_st.get("traces") or [])
        for tr in reversed(traces):
            if not isinstance(tr, dict):
                continue
            if str(tr.get("body_id") or "") != str(body_id):
                continue
            if int(tr.get("observation_tick", -1)) == int(observation_tick):
                oatt = tr
                break
            if oatt is None:
                oatt = tr
    except Exception:
        pass

    a3_to_obs = None
    a3_reception = reception_tick
    if isinstance(oatt, dict):
        if oatt.get("reception_tick") is not None:
            a3_reception = oatt.get("reception_tick")
        a3_to_obs = oatt.get("causal_delay_ticks")
        if a3_to_obs is None and oatt.get("observation_tick") is not None and a3_reception is not None:
            a3_to_obs = int(oatt["observation_tick"]) - int(a3_reception)

    if a3_reception is None and oatt is None:
        avail = MISSING_NOT_CAPTURED
    else:
        avail = AVAIL_TRUE_ZERO
        if isinstance(oatt, dict):
            a5 = oatt.get("a5") or {}
            vals: list[float] = []
            if isinstance(a5, dict):
                for key in ("left_receptor_channels", "right_receptor_channels", "left", "right"):
                    v = a5.get(key)
                    if isinstance(v, (list, tuple)):
                        vals.extend(float(x) for x in v)
            if vals:
                avail = _avail_from_values(vals, present=True)

    return {
        "modality": "hearing",
        "physical_event_ticks": [r["physical_event_tick"] for r in source_refs],
        "source_event_refs": source_refs,
        "field_state_tick": a3_reception,
        "lps_reception_tick": a3_reception,
        "receptor_sample_tick": a3_reception,
        "organism_observation_tick": observation_tick,
        "source_to_receptor_propagation_delay_ticks": (
            min(transport_delays) if transport_delays else None
        ),
        "source_to_receptor_propagation_delay_ticks_all": transport_delays[:MAX_SOURCE_EVENT_REFS],
        "receptor_to_observation_delay_ticks": a3_to_obs,
        "oatt_causal_delay_ticks": a3_to_obs,
        "lps_transport_delay_overwritten_by_oatt": False,
        "oatt_zero_delay_meaning": "A3_RECEPTOR_TO_A5_OBSERVATION_ALIGNMENT_NOT_LPS_TRANSPORT",
        "oatt_ref": {
            "trace_id": (oatt or {}).get("trace_id") if isinstance(oatt, dict) else None,
            "sav1_receipt_id": (oatt or {}).get("sav1_receipt_id") if isinstance(oatt, dict) else None,
            "present": oatt is not None,
        },
        "availability": avail,
        "true_zero": avail == AVAIL_TRUE_ZERO,
        "missing_reason": None if str(avail).startswith("AVAILABLE") else avail,
        "timing_authority": "LPS_PLUS_OATT" if oatt is not None else ("LPS" if a3_reception is not None else "NONE"),
    }


def _body_support_section(body: Any, observation_tick: int) -> dict[str, Any]:
    pose_tick = getattr(body, "tick", None)
    return {
        "modality": "body_support",
        "physical_state_tick": int(pose_tick) if pose_tick is not None else observation_tick,
        "organism_observation_tick": observation_tick,
        "grounded": bool(getattr(body, "grounded", True)),
        "z": float(getattr(body, "z", 0.0) or 0.0),
        "availability": AVAIL_NONZERO if pose_tick is not None else MISSING_NOT_CAPTURED,
        "timing_authority": "PHYSICAL_BODY_STATE",
    }


def _motor_context_section(runtime: Any, observation_tick: int) -> dict[str, Any]:
    """References only — no adjacent-tick causal inference."""
    decision = getattr(runtime, "last_decision", None) or getattr(runtime, "last_selected_action", None)
    decision_tick = getattr(runtime, "last_decision_tick", None)
    actuation_tick = getattr(runtime, "last_actuation_tick", None)
    consequence_tick = getattr(runtime, "last_consequence_tick", None)
    # Prefer explicit receipt refs if present
    ebae = getattr(runtime, "last_ebae_receipt", None) or getattr(getattr(runtime, "world", None), "last_ebae_receipt", None)
    etc = getattr(runtime, "last_etc_receipt", None) or getattr(getattr(runtime, "world", None), "last_effector_terrain_contact", None)
    links = {
        "observation_tick": observation_tick,
        "motor_decision_tick": int(decision_tick) if decision_tick is not None else None,
        "actuation_tick": int(actuation_tick) if actuation_tick is not None else (
            int(ebae.get("tick")) if isinstance(ebae, dict) and ebae.get("tick") is not None else None
        ),
        "physical_consequence_tick": int(consequence_tick) if consequence_tick is not None else (
            int(etc.get("tick")) if isinstance(etc, dict) and etc.get("tick") is not None else None
        ),
        "decision_ref_present": decision is not None,
        "ebae_ref_present": ebae is not None,
        "etc_ref_present": etc is not None,
        "adjacent_ticks_alone_used_as_causal_proof": False,
        "causal_chain_established": bool(
            decision_tick is not None and (actuation_tick is not None or isinstance(ebae, dict))
        ),
    }
    return {
        "modality": "motor_context",
        "links": links,
        "availability": AVAIL_NONZERO if links["causal_chain_established"] else MISSING_NOT_CAPTURED,
        "timing_authority": "EXPLICIT_RECEIPTS_ONLY",
    }


def _alignment_status(vision: dict[str, Any], hearing: dict[str, Any], obs_tick: int) -> str:
    v_ok = str(vision.get("availability") or "").startswith("AVAILABLE")
    h_ok = str(hearing.get("availability") or "").startswith("AVAILABLE")
    if vision.get("timing_authority") == "NONE" and hearing.get("timing_authority") == "NONE":
        return STATUS_LEGACY
    if not v_ok and not h_ok:
        return STATUS_PARTIAL
    v_obs = vision.get("organism_observation_tick")
    h_obs = hearing.get("organism_observation_tick")
    if v_obs is not None and h_obs is not None and int(v_obs) == int(h_obs) == int(obs_tick):
        # Same observation tick — check physical event times
        h_phys = hearing.get("physical_event_ticks") or []
        v_delay = vision.get("causal_delay_ticks")
        h_transport = hearing.get("source_to_receptor_propagation_delay_ticks")
        if h_phys or (h_transport is not None and int(h_transport) >= 1) or (v_delay == 0 and h_transport):
            return STATUS_ALIGNED_DIFF_PHYS
        return STATUS_ALIGNED_OBS
    if v_obs is not None and h_obs is not None and int(v_obs) != int(h_obs):
        return STATUS_STALE_PREVENTED
    return STATUS_PARTIAL


def build_alignment_envelope(
    *,
    world: Any,
    body: Any,
    config: Any,
    observation: dict[str, Any] | None,
    observation_tick: int,
    agent_id: str,
    body_id: str,
    run_id: str,
    runtime_generation: Any,
    runtime: Any | None = None,
    researcher_presentation_tick: int | None = None,
) -> dict[str, Any]:
    """Build one researcher-only envelope. Does not mutate observation dict."""
    # Refine hearing availability from observation osc keys without copying values into envelope as authority
    vision = _vision_section(world, observation_tick)
    hearing = _hearing_section(world, body, observation_tick, body_id)
    if isinstance(observation, dict):
        osc_vals = [float(v) for k, v in observation.items() if str(k).startswith("osc_l_") or str(k).startswith("osc_r_")]
        if osc_vals:
            hearing["availability"] = _avail_from_values(osc_vals, present=True)
            hearing["true_zero"] = hearing["availability"] == AVAIL_TRUE_ZERO
            hearing["missing_reason"] = None
        exo_vals = [float(v) for k, v in observation.items() if str(k).startswith("exo_")]
        if exo_vals and vision.get("timing_authority") not in ("NONE",):
            vision["availability"] = _avail_from_values(exo_vals, present=True)
            vision["true_zero"] = vision["availability"] == AVAIL_TRUE_ZERO

    body_sec = _body_support_section(body, observation_tick)
    motor = _motor_context_section(runtime, observation_tick) if runtime is not None else {
        "modality": "motor_context",
        "availability": MISSING_NOT_CAPTURED,
        "links": {"adjacent_ticks_alone_used_as_causal_proof": False},
    }
    status = _alignment_status(vision, hearing, observation_tick)
    return {
        "schema": SCHEMA,
        "capability": CAPABILITY,
        "profile": PROFILE,
        "authority": AUTHORITY,
        "observation_identity": {
            "run_id": str(run_id),
            "runtime_generation": runtime_generation,
            "agent_id": str(agent_id),
            "body_id": str(body_id),
            "organism_observation_tick": int(observation_tick),
        },
        "vision": vision,
        "hearing": hearing,
        "body_support": body_sec,
        "motor_context": motor,
        "alignment_status": status,
        "researcher_presentation_tick": researcher_presentation_tick,
        "researcher_presentation_tick_is_scientific_authority": False,
        "labels": list(AUTHORITY_FLAGS["labels"]),
        "zero_fill_used": False,
        "interpolation_used": False,
        "last_value_carried_as_current": False,
        "stale_audio_fresh_vision_pairing_prevented": status == STATUS_STALE_PREVENTED,
        "same_observation_tick_means_same_physical_time": False,
        "feeds_cognition": False,
        "researcher_only": True,
    }


def finalize_alignment_envelope(
    *,
    world: Any,
    body: Any,
    config: Any,
    observation: dict[str, Any] | None,
    observation_tick: int,
    agent_id: str,
    body_id: str,
    run_id: str,
    runtime_generation: Any,
    runtime: Any | None = None,
) -> dict[str, Any] | None:
    if not sensory_modality_temporal_alignment_is_active(config):
        return None
    env = build_alignment_envelope(
        world=world,
        body=body,
        config=config,
        observation=observation,
        observation_tick=observation_tick,
        agent_id=agent_id,
        body_id=body_id,
        run_id=run_id,
        runtime_generation=runtime_generation,
        runtime=runtime,
        researcher_presentation_tick=None,
    )
    hist = getattr(world, WORLD_HISTORY_ATTR, None)
    if not isinstance(hist, list):
        hist = []
        setattr(world, WORLD_HISTORY_ATTR, hist)
    # One envelope per agent observation: replace same tick+agent+generation if duplicate finalize
    key = (
        str(agent_id),
        int(observation_tick),
        str(runtime_generation),
    )
    hist[:] = [
        e for e in hist
        if (
            str((e.get("observation_identity") or {}).get("agent_id")),
            int((e.get("observation_identity") or {}).get("organism_observation_tick", -1)),
            str((e.get("observation_identity") or {}).get("runtime_generation")),
        ) != key
    ]
    hist.append(env)
    cfg = getattr(config, "sensory_modality_temporal_alignment", None)
    max_h = int(getattr(cfg, "max_history", MAX_ENVELOPE_HISTORY) or MAX_ENVELOPE_HISTORY)
    truncated = 0
    if len(hist) > max_h:
        truncated = len(hist) - max_h
        del hist[:-max_h]
    counters = getattr(world, WORLD_COUNTERS_ATTR, None)
    if not isinstance(counters, dict):
        counters = {"envelopes": 0, "truncated": 0, "poll_skips": 0}
        setattr(world, WORLD_COUNTERS_ATTR, counters)
    counters["envelopes"] = int(counters.get("envelopes", 0)) + 1
    counters["truncated"] = int(counters.get("truncated", 0)) + truncated
    setattr(world, WORLD_LAST_ATTR, env)
    return env


def note_observer_poll_skip(world: Any) -> None:
    counters = getattr(world, WORLD_COUNTERS_ATTR, None)
    if not isinstance(counters, dict):
        counters = {"envelopes": 0, "truncated": 0, "poll_skips": 0}
        setattr(world, WORLD_COUNTERS_ATTR, counters)
    counters["poll_skips"] = int(counters.get("poll_skips", 0)) + 1


def researcher_summary(world: Any, config: Any) -> dict[str, Any]:
    last = getattr(world, WORLD_LAST_ATTR, None)
    counters = getattr(world, WORLD_COUNTERS_ATTR, None) or {}
    if not isinstance(last, dict):
        return {
            "enabled": sensory_modality_temporal_alignment_is_active(config),
            "schema": SCHEMA,
            "has_envelope": False,
            "labels": list(AUTHORITY_FLAGS["labels"]),
            "counters": counters,
        }
    oid = last.get("observation_identity") or {}
    return {
        "enabled": True,
        "schema": SCHEMA,
        "profile": PROFILE,
        "authority": AUTHORITY,
        "labels": last.get("labels"),
        "alignment_status": last.get("alignment_status"),
        "organism_observation_tick": oid.get("organism_observation_tick"),
        "agent_id": oid.get("agent_id"),
        "vision_receptor_sample_tick": (last.get("vision") or {}).get("receptor_sample_tick"),
        "vision_causal_delay_ticks": (last.get("vision") or {}).get("causal_delay_ticks"),
        "hearing_lps_reception_tick": (last.get("hearing") or {}).get("lps_reception_tick"),
        "hearing_source_to_receptor_delay": (last.get("hearing") or {}).get(
            "source_to_receptor_propagation_delay_ticks"
        ),
        "hearing_receptor_to_observation_delay": (last.get("hearing") or {}).get(
            "receptor_to_observation_delay_ticks"
        ),
        "body_support_tick": (last.get("body_support") or {}).get("physical_state_tick"),
        "motor_links": (last.get("motor_context") or {}).get("links"),
        "vision_availability": (last.get("vision") or {}).get("availability"),
        "hearing_availability": (last.get("hearing") or {}).get("availability"),
        "same_observation_means_same_physical_time": False,
        "counters": counters,
        "feeds_cognition": False,
        "researcher_only": True,
    }


def build_o5_analyzer_reconstruction(evidence: dict[str, Any] | None = None, *, on_progress: Any = None) -> dict[str, Any]:
    ev = evidence if isinstance(evidence, dict) else {}
    if on_progress:
        on_progress("INDEX_PHYSICAL_RECEIPTS", 0, 1)
        on_progress("AGGREGATING", 1, 1)
    return {
        "schema": SCHEMA,
        "capability": CAPABILITY,
        "profile": PROFILE,
        "section": "SENSORY MODALITY TEMPORAL ALIGNMENT (O5)",
        "causal_chains": [
            "physical_event → field → receptor → observation",
            "observation → decision → actuation → consequence",
        ],
        "same_observation_means_same_physical_time": False,
        "oatt_delay_is_not_lps_transport": True,
        "alignment_status": ev.get("alignment_status"),
        "vision_delay": (ev.get("vision") or {}).get("causal_delay_ticks"),
        "audio_transport_delay": (ev.get("hearing") or {}).get("source_to_receptor_propagation_delay_ticks"),
        "audio_oatt_delay": (ev.get("hearing") or {}).get("receptor_to_observation_delay_ticks"),
        "researcher_only": True,
        "labels": list(AUTHORITY_FLAGS["labels"]),
    }


def format_o5_section(summary: dict[str, Any] | None) -> str:
    s = summary or {}
    return "\n".join([
        "SENSORY MODALITY TEMPORAL ALIGNMENT (O5)",
        f"  alignment_status: {s.get('alignment_status')}",
        f"  vision_delay: {s.get('vision_delay')}",
        f"  audio_transport_delay: {s.get('audio_transport_delay')}",
        f"  audio_oatt_delay: {s.get('audio_oatt_delay')}",
        "  same_observation_means_same_physical_time: False",
        "  oatt_delay_is_not_lps_transport: True",
    ])



def serialize_state(world: Any) -> dict[str, Any] | None:
    """Researcher evidence only. Never organism-accessible."""
    hist = getattr(world, WORLD_HISTORY_ATTR, None)
    counters = getattr(world, WORLD_COUNTERS_ATTR, None)
    last = getattr(world, WORLD_LAST_ATTR, None)
    if not isinstance(hist, list) and not isinstance(last, dict):
        return None
    return {
        "schema": SCHEMA,
        "profile": PROFILE,
        "researcher_only": True,
        "physical_state": False,
        "no_replay_into_cognition": True,
        "history": list(hist) if isinstance(hist, list) else [],
        "last": last if isinstance(last, dict) else None,
        "counters": dict(counters) if isinstance(counters, dict) else {},
        "restored_as_evidence_only": False,
    }


def restore_state(world: Any, data: dict[str, Any] | None) -> None:
    """Restore researcher history only. Does NOT create new envelopes or replay reception."""
    if not isinstance(data, dict) or not data:
        setattr(world, WORLD_HISTORY_ATTR, [])
        setattr(world, WORLD_LAST_ATTR, None)
        setattr(world, WORLD_COUNTERS_ATTR, {"envelopes": 0, "truncated": 0, "poll_skips": 0, "restored": 1})
        return
    if str(data.get("schema") or "") not in (SCHEMA, ""):
        # Incompatible → partial empty with flag
        setattr(world, WORLD_HISTORY_ATTR, [])
        setattr(world, WORLD_LAST_ATTR, None)
        setattr(world, WORLD_COUNTERS_ATTR, {
            "envelopes": 0, "truncated": 0, "poll_skips": 0,
            "restored": 1, "legacy_incompatible": 1,
        })
        return
    hist = list(data.get("history") or [])
    # Mark restored envelopes as researcher evidence — do not treat as live finalize
    for e in hist:
        if isinstance(e, dict):
            e["restored_researcher_evidence_only"] = True
            e["restored_as_live_envelope"] = False
    setattr(world, WORLD_HISTORY_ATTR, hist)
    # Keep last for researcher display; not a newly finalized live envelope
    last = data.get("last")
    if isinstance(last, dict):
        last = dict(last)
        last["restored_researcher_evidence_only"] = True
        last["restored_as_live_envelope"] = False
    setattr(world, WORLD_LAST_ATTR, last if isinstance(last, dict) else None)
    counters = dict(data.get("counters") or {})
    counters["restored"] = int(counters.get("restored", 0)) + 1
    counters["live_envelopes_created_on_restore"] = 0
    setattr(world, WORLD_COUNTERS_ATTR, counters)


def derive_envelope_from_saved_evidence(evidence: dict[str, Any] | None) -> dict[str, Any]:
    """Saved-run Analyzer: exact / compatible / partial — never silent current-rule rewrite."""
    ev = evidence if isinstance(evidence, dict) else {}
    if ev.get("schema") == SCHEMA and isinstance(ev.get("observation_identity"), dict):
        out = dict(ev)
        out["legacy_policy"] = "CURRENT_O5_EXACT_ENVELOPE"
        out["authority_label"] = AUTHORITY
        return out
    if isinstance(ev.get("organism_physical_optical_reception"), dict) or isinstance(ev.get("oatt"), dict):
        return {
            "schema": SCHEMA,
            "profile": PROFILE,
            "legacy_policy": "COMPATIBLE_DERIVED_FROM_O4_OATT",
            "authority_label": "DERIVED_COMPATIBLE_TIMING_NOT_LIVE_ENVELOPE",
            "vision": {"availability": MISSING_NOT_CAPTURED, "timing_authority": "DERIVED"},
            "hearing": {"availability": MISSING_NOT_CAPTURED, "timing_authority": "DERIVED"},
            "same_observation_tick_means_same_physical_time": False,
            "partial": True,
        }
    return {
        "schema": SCHEMA,
        "profile": PROFILE,
        "legacy_policy": "LEGACY_PARTIAL_UNKNOWN",
        "authority_label": "LEGACY_TIMING_UNAVAILABLE",
        "availability": MISSING_LEGACY,
        "partial": True,
        "same_observation_tick_means_same_physical_time": False,
    }


PRIVACY_DENYLIST_TOKENS = (
    CAPABILITY,
    SCHEMA,
    PROFILE,
    AUTHORITY,
    "sensory_modality_temporal_alignment",
    "alignment_envelope",
    "source_event_refs",
    "source_to_receptor_propagation_delay_ticks",
    "receptor_to_observation_delay_ticks",
    "ALIGNED_OBSERVATION_DIFFERENT_PHYSICAL_EVENT_TIMES",
)
