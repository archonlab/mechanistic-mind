"""OBSERVER_ACOUSTIC_PROBE_V1 — passive researcher mono point sample of LPS field.

Not a physical mechanism / preset. Not a body / receiver / source.
Samples the shared pre-phenotype point-field law from local_physical_signal_transport.
Never mutates LPS, stream records, organism hearing, or cognition.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA = "OBSERVER_ACOUSTIC_PROBE_V1"
CONTRACT_ID = "observer_acoustic_probe"
RECEIPT_KIND = "OBSERVER_ACOUSTIC_PROBE_SAMPLE"
STATE_SCHEMA = "OBSERVER_ACOUSTIC_PROBE_STATE_V1"
PROBE_ID = "observer-acoustic-probe-0"
SAMPLING_MODE = "POINT_MONO_V1"
WORLD_ATTR = "observer_acoustic_probe_state"

HISTORY_CAPACITY_DEFAULT = 64
CONTRIBUTOR_CAP_DEFAULT = 16

LIMITATIONS = (
    "XY_ONLY",
    "NO_Z_DISTANCE",
    "NO_OCCLUSION",
    "NO_REFLECTION",
    "NO_REVERB",
    "NO_HUMAN_FREQUENCY_MAPPING",
    "STATIC_POINT_WAVEFRONT_CROSSING",
    "PRE_PHENOTYPE_MONO_NOT_LR",
)

BANNER = (
    "PASSIVE ACOUSTIC PROBE · PHYSICAL FIELD · XY POINT SAMPLE · NO AUDIO PLAYBACK"
)


@dataclass
class ObserverAcousticProbeState:
    schema_version: str = STATE_SCHEMA
    enabled: bool = False
    probe_id: str = PROBE_ID
    x: float = 0.0
    y: float = 0.0
    sampling_mode: str = SAMPLING_MODE
    capacity: int = HISTORY_CAPACITY_DEFAULT
    contributor_cap: int = CONTRIBUTOR_CAP_DEFAULT
    samples: list[dict[str, Any]] = field(default_factory=list)
    last_sample_tick: int | None = None
    last_sample_key: str | None = None
    evicted_count: int = 0
    sample_computation_count: int = 0
    deduplicated_read_count: int = 0
    clear_count: int = 0


def ensure_probe_state(world: Any) -> ObserverAcousticProbeState:
    st = getattr(world, WORLD_ATTR, None)
    if isinstance(st, ObserverAcousticProbeState):
        return st
    st = ObserverAcousticProbeState()
    setattr(world, WORLD_ATTR, st)
    return st


def state_of(world: Any) -> ObserverAcousticProbeState | None:
    st = getattr(world, WORLD_ATTR, None)
    return st if isinstance(st, ObserverAcousticProbeState) else None


def configure_probe(
    world: Any,
    *,
    enabled: bool | None = None,
    x: float | None = None,
    y: float | None = None,
    clear_history: bool = False,
) -> dict[str, Any]:
    """Researcher-only configuration. Does not sample, emit, or enqueue LPS."""
    st = ensure_probe_state(world)
    if clear_history:
        st.samples.clear()
        st.last_sample_tick = None
        st.last_sample_key = None
        st.clear_count += 1
    if enabled is not None:
        st.enabled = bool(enabled)
    width = height = 32
    t = getattr(world, "T", None)
    if t is not None and getattr(t, "shape", None) is not None:
        height, width = int(t.shape[0]), int(t.shape[1])
    from mechanistic_mind.planet.topology import wrap_coord

    if x is not None:
        st.x = float(wrap_coord(float(x), width))
    if y is not None:
        st.y = float(wrap_coord(float(y), height))
    return {
        "accepted": True,
        "researcher_only": True,
        "agent_action": False,
        "enabled": st.enabled,
        "probe_id": st.probe_id,
        "x": st.x,
        "y": st.y,
        "sampling_mode": st.sampling_mode,
        "cleared_history": bool(clear_history),
        "physics_effect": False,
        "lps_effect": False,
    }


def _sample_key(*, tick: int, probe_id: str, x: float, y: float, lps_generation: int) -> str:
    return f"{SCHEMA}:{int(tick)}:{probe_id}:{x:.6f}:{y:.6f}:g{int(lps_generation)}"


def _lps_generation(world: Any) -> int:
    lps = getattr(world, "local_signal_transport", None)
    if lps is None:
        return -1
    return int(getattr(lps, "last_processed_tick", -1) or -1)


def sample_observer_acoustic_probe(
    world: Any,
    *,
    scientific_tick: int | None = None,
) -> dict[str, Any]:
    """Sample after LPS step for current tick. Idempotent per (tick, pose, LPS generation)."""
    st = state_of(world)
    if st is None or not st.enabled:
        return {"status": "DISABLED", "researcher_only": True}
    from mechanistic_mind.physical_system.local_physical_signal_transport import (
        MEDIUM_VERSION,
        sample_point_field_passive,
        state_of as lps_state_of,
    )

    lps = lps_state_of(world)
    if lps is None:
        return {"status": "LPS_INACTIVE", "researcher_only": True}

    A = int(lps.last_processed_tick if scientific_tick is None else scientific_tick)
    gen = _lps_generation(world)
    key = _sample_key(tick=A, probe_id=st.probe_id, x=st.x, y=st.y, lps_generation=gen)
    if st.last_sample_key == key and st.samples and int(st.samples[-1].get("scientific_tick", -1)) == A:
        st.deduplicated_read_count += 1
        return {"status": "DEDUPED", "sample": st.samples[-1], "researcher_only": True}

    raw = sample_point_field_passive(
        world,
        x=st.x,
        y=st.y,
        arrival_tick=A,
        contributor_cap=int(st.contributor_cap),
    )
    st.sample_computation_count += 1

    contributors = []
    for c in list(raw.get("contributors") or []):
        if not c.get("accepted"):
            continue
        contributors.append(
            {
                "emission_id": c.get("emission_id"),
                "stream_record_id": (
                    f"apas:{c.get('emission_id')}" if c.get("emission_id") else None
                ),
                "emission_tick": c.get("emission_tick"),
                "toroidal_distance": c.get("toroidal_distance"),
                "attenuation": c.get("attenuation"),
                "total_received_energy": c.get("total_received_energy"),
                "selection_provenance": c.get("selection_provenance"),
                "graph_source_label": c.get("graph_source_label"),
            }
        )
    # Accepteds may be fewer than crossing events; recompute retained from accepted.
    accepted_all = [
        c for c in list(raw.get("contributors") or []) if c.get("accepted")
    ]
    # raw contributors already include rejected; count totals from raw
    sample = {
        "schema": SCHEMA,
        "receipt_kind": RECEIPT_KIND,
        "sample_key": key,
        "scientific_tick": A,
        "probe_id": st.probe_id,
        "x": float(raw.get("point_x", st.x)),
        "y": float(raw.get("point_y", st.y)),
        "sampling_mode": SAMPLING_MODE,
        "transport_profile": "LOCAL_PHYSICAL_SIGNAL_TRANSPORT_V1",
        "transport_medium": MEDIUM_VERSION,
        "anonymous_band_energies": list(raw.get("anonymous_band_energies") or []),
        "total_received_energy": float(raw.get("total_received_energy") or 0.0),
        "contributors": contributors[: int(st.contributor_cap)],
        "contributor_count_total": int(raw.get("accepted_contributor_count") or len(accepted_all)),
        "contributor_count_retained": min(len(accepted_all), int(st.contributor_cap)),
        "contributor_count_truncated": max(
            0, len(accepted_all) - int(st.contributor_cap)
        ),
        "crossing_events_total": int(raw.get("contributor_count_total") or 0),
        "active_signals_examined": int(raw.get("active_signals_examined") or 0),
        "field_authority": "PRE_PHENOTYPE_MONO_POINT_FIELD_V1",
        "limitations": list(LIMITATIONS),
        "audio_playback": False,
        "human_hz_mapping": "NOT_ESTABLISHED",
        "researcher_only": True,
        "agent_accessible": False,
        "is_physical_source": False,
        "zero_field": float(raw.get("total_received_energy") or 0.0) <= 0.0,
    }

    # Replace same-tick sample if pose changed after prior sample this tick.
    if st.samples and int(st.samples[-1].get("scientific_tick", -1)) == A:
        st.samples[-1] = sample
    else:
        st.samples.append(sample)
        while len(st.samples) > int(st.capacity):
            st.samples.pop(0)
            st.evicted_count += 1
    st.last_sample_tick = A
    st.last_sample_key = key
    return {"status": "SAMPLED", "sample": sample, "researcher_only": True}


def serialize_state(st: ObserverAcousticProbeState | None) -> dict[str, Any] | None:
    if st is None:
        return None
    return {
        "schema_version": STATE_SCHEMA,
        "contract": CONTRACT_ID,
        "researcher_configuration": True,
        "physical_state": False,
        "enabled": bool(st.enabled),
        "probe_id": st.probe_id,
        "x": float(st.x),
        "y": float(st.y),
        "sampling_mode": st.sampling_mode,
        "capacity": int(st.capacity),
        "contributor_cap": int(st.contributor_cap),
        "samples": list(st.samples),
        "last_sample_tick": st.last_sample_tick,
        "last_sample_key": st.last_sample_key,
        "evicted_count": int(st.evicted_count),
        "sample_computation_count": int(st.sample_computation_count),
        "deduplicated_read_count": int(st.deduplicated_read_count),
        "clear_count": int(st.clear_count),
        "no_resample_on_restore": True,
        "audio_playback": False,
    }


def restore_state(world: Any, data: dict[str, Any] | None) -> ObserverAcousticProbeState | None:
    if not data:
        return None
    if str(data.get("schema_version") or "") not in (STATE_SCHEMA, SCHEMA):
        return None
    st = ObserverAcousticProbeState(
        enabled=bool(data.get("enabled", False)),
        probe_id=str(data.get("probe_id") or PROBE_ID),
        x=float(data.get("x") or 0.0),
        y=float(data.get("y") or 0.0),
        sampling_mode=str(data.get("sampling_mode") or SAMPLING_MODE),
        capacity=int(data.get("capacity") or HISTORY_CAPACITY_DEFAULT),
        contributor_cap=int(data.get("contributor_cap") or CONTRIBUTOR_CAP_DEFAULT),
        samples=[dict(s) for s in (data.get("samples") or []) if isinstance(s, dict)],
        last_sample_tick=data.get("last_sample_tick"),
        last_sample_key=data.get("last_sample_key"),
        evicted_count=int(data.get("evicted_count") or 0),
        sample_computation_count=int(data.get("sample_computation_count") or 0),
        deduplicated_read_count=int(data.get("deduplicated_read_count") or 0),
        clear_count=int(data.get("clear_count") or 0),
    )
    setattr(world, WORLD_ATTR, st)
    return st


def researcher_summary(world: Any) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    from mechanistic_mind.physical_system.physical_frequency_amplitude_calibration_contract import (
        c0_calibration_reference,
        observer_calibration_status,
    )

    latest = st.samples[-1] if st.samples else None
    return {
        "schema": SCHEMA,
        "contract": CONTRACT_ID,
        "banner": BANNER,
        "researcher_only": True,
        "agent_accessible": False,
        "audio_playback": False,
        "enabled": st.enabled,
        "probe_id": st.probe_id,
        "x": st.x,
        "y": st.y,
        "sampling_mode": st.sampling_mode,
        "history_capacity": st.capacity,
        "retained_count": len(st.samples),
        "evicted_count": st.evicted_count,
        "sample_computation_count": st.sample_computation_count,
        "deduplicated_read_count": st.deduplicated_read_count,
        "last_sample_tick": st.last_sample_tick,
        "latest_sample": latest,
        "recent_samples": list(st.samples[-12:]),
        "limitations": list(LIMITATIONS),
        "acoustic_calibration": c0_calibration_reference(),
        "acoustic_calibration_status": observer_calibration_status(),
        "labels": [
            "PASSIVE ACOUSTIC PROBE",
            "PHYSICAL FIELD",
            "XY POINT SAMPLE",
            "NO AUDIO PLAYBACK",
            "RESEARCHER-ONLY",
            "NOT A BODY",
            "NOT A SOURCE",
        ],
        "map_glyph": {
            "kind": "OBSERVER_ACOUSTIC_PROBE",
            "probe_id": st.probe_id,
            "x": st.x,
            "y": st.y,
            "enabled": st.enabled,
            "is_entity": False,
            "is_source": False,
            "hearing_radius": None,
        },
    }


def observer_payload(world: Any) -> dict[str, Any] | None:
    return researcher_summary(world)
