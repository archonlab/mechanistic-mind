"""OBSERVER_ACOUSTIC_PROBE_V1 — focused contract tests."""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import pytest

from mechanistic_mind.model.acanthostega import acanthostega_local_signal_config
from mechanistic_mind.physical_system import local_physical_signal_transport as lps
from mechanistic_mind.physical_system.observer_acoustic_probe import (
    CONTRACT_ID,
    PROBE_ID,
    RECEIPT_KIND,
    SAMPLING_MODE,
    SCHEMA,
    configure_probe,
    ensure_probe_state,
    sample_observer_acoustic_probe,
    serialize_state,
    restore_state,
    state_of,
)
from mechanistic_mind.physical_system.observation import FORBIDDEN_TOKENS, audit_cognition_payload
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.authoritative_physical_acoustic_stream_contract import (
    state_of as stream_state_of,
)

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "acanthostega_observer_acoustic_probe_v1"
RESULTS.mkdir(parents=True, exist_ok=True)

TICKS = 0


def _bump(n: int) -> None:
    global TICKS
    TICKS += int(n)


def _phys_fingerprint(rt: PhysicalSystemRuntime) -> dict:
    w = rt.world
    lps_st = lps.state_of(w)
    body = rt.body
    stream = stream_state_of(w)
    return {
        "tick": int(rt.tick),
        "body": (float(body.x), float(body.y), float(getattr(body, "vx", 0) or 0), float(getattr(body, "vy", 0) or 0)),
        "osc_emit_remaining": int(getattr(body, "osc_emit_remaining", 0) or 0),
        "lps_active": None if lps_st is None else sorted(e.emission_id for e in lps_st.active),
        "lps_steps": None if lps_st is None else int(lps_st.counters.get("steps", 0)),
        "lps_emissions": None if lps_st is None else int(lps_st.counters.get("emissions", 0)),
        "auditory": None if lps_st is None else {
            k: (list(v.get("left") or []), list(v.get("right") or []))
            for k, v in sorted((lps_st.auditory or {}).items())
        },
        "stream_ids": None if stream is None else [r.get("stream_record_id") for r in stream.records],
        "stream_n": None if stream is None else len(stream.records),
    }


def test_01_identity_and_privacy():
    assert SCHEMA == "OBSERVER_ACOUSTIC_PROBE_V1"
    assert CONTRACT_ID == "observer_acoustic_probe"
    assert RECEIPT_KIND == "OBSERVER_ACOUSTIC_PROBE_SAMPLE"
    assert SAMPLING_MODE == "POINT_MONO_V1"
    assert PROBE_ID == "observer-acoustic-probe-0"
    for tok in (
        "OBSERVER_ACOUSTIC_PROBE_V1",
        "observer_acoustic_probe",
        "OBSERVER_ACOUSTIC_PROBE_SAMPLE",
        "observer-acoustic-probe-0",
        "POINT_MONO_V1",
    ):
        assert tok in FORBIDDEN_TOKENS
    assert audit_cognition_payload({"osc_l_0": 0.1, "osc_r_0": 0.2}) == []
    assert audit_cognition_payload({"schema": SCHEMA, "probe_id": PROBE_ID, "x": 1.0})


def test_02_shared_point_field_matches_body_center_reception():
    """Probe at static body XY matches body-centre received bands (pre L/R phenotype)."""
    cfg = acanthostega_local_signal_config()
    rt = PhysicalSystemRuntime(seed=31, config=cfg)
    bx, by = float(rt.body.x), float(rt.body.y)
    sx, sy = bx + 2.0, by
    lps.queue_researcher_emission(
        rt.world, cfg, x=sx, y=sy, band_energies=[0.5] * 6, researcher_id="probe_test"
    )
    rt.body.vx = 0.0
    rt.body.vy = 0.0
    configure_probe(rt.world, enabled=True, x=bx, y=by)
    matched = False
    for _ in range(5):
        prev_n = len(lps.state_of(rt.world).reception_history or [])
        rt.step()
        _bump(1)
        lps_st = lps.state_of(rt.world)
        recs = list(lps_st.reception_history or [])
        if len(recs) <= prev_n:
            continue
        last = recs[-1]
        if not last.get("accepted"):
            continue
        A = int(last["arrival_tick"])
        rx, ry = last["receiver_position_at_reception"]
        # Sample on the same arrival tick while the wavefront crossing is still the law.
        raw = lps.sample_point_field_passive(rt.world, x=float(rx), y=float(ry), arrival_tick=A)
        match = next(
            (
                c
                for c in raw["contributors"]
                if c["emission_id"] == last["emission_id"] and c.get("accepted")
            ),
            None,
        )
        assert match is not None, (raw, last)
        for a, b in zip(match["received_band_energies"], last["received_band_energies"]):
            assert abs(float(a) - float(b)) < 1e-9
        matched = True
        break
    assert matched, "no accepted body reception observed for equivalence check"


def test_03_attenuation_and_delay_and_torus():
    cfg = acanthostega_local_signal_config()
    rt = PhysicalSystemRuntime(seed=41, config=cfg)
    # Emit at (10.5, 10.5)
    lps.queue_researcher_emission(
        rt.world, cfg, x=10.5, y=10.5, band_energies=[1.0] * 6, researcher_id="att"
    )
    rt.step(); _bump(1)  # emission created at te=tick-1 after step
    # Near and far static probes — sample via passive query after wavefront exists.
    # Step enough for near arrival.
    for _ in range(5):
        rt.step(); _bump(1)
    near = lps.sample_point_field_passive(rt.world, x=12.5, y=10.5)
    far = lps.sample_point_field_passive(rt.world, x=16.5, y=10.5)
    # At least one of the positions may have crossed this tick; compute analytical att for any accepted.
    for sample, expected_d in ((near, 2.0), (far, 6.0)):
        for c in sample.get("contributors") or []:
            if not c.get("accepted"):
                continue
            assert abs(float(c["toroidal_distance"]) - expected_d) < 1e-6
            att = lps.attenuation(expected_d, 0.08)
            assert abs(float(c["attenuation"]) - att) < 1e-9
            assert abs(float(c["received_band_energies"][0]) - att * 1.0) < 1e-9
    # Toroidal wrap: source near edge, probe across wrap.
    rt2 = PhysicalSystemRuntime(seed=42, config=cfg)
    lps.queue_researcher_emission(
        rt2.world, cfg, x=0.5, y=10.5, band_energies=[1.0] * 6, researcher_id="wrap"
    )
    for _ in range(6):
        rt2.step(); _bump(1)
    wrap = lps.sample_point_field_passive(rt2.world, x=31.5, y=10.5)
    d_expect, wraps = lps.toroidal_distance(0.5, 10.5, 31.5, 10.5, 32, 32)
    assert wraps is True
    for c in wrap.get("contributors") or []:
        if c.get("accepted"):
            assert abs(float(c["toroidal_distance"]) - d_expect) < 1e-6
            assert c.get("wraps_torus") is True


def test_04_silence_is_zero_sample_not_source():
    cfg = acanthostega_local_signal_config()
    rt = PhysicalSystemRuntime(seed=51, config=cfg)
    configure_probe(rt.world, enabled=True, x=20.0, y=20.0)
    stream_before = 0
    st_stream = stream_state_of(rt.world)
    if st_stream:
        stream_before = len(st_stream.records)
    for _ in range(3):
        rt.step(); _bump(1)
    st = state_of(rt.world)
    assert st is not None and st.samples
    latest = st.samples[-1]
    assert latest["zero_field"] is True
    assert float(latest["total_received_energy"]) == 0.0
    assert latest["is_physical_source"] is False
    st_stream2 = stream_state_of(rt.world)
    after = 0 if st_stream2 is None else len(st_stream2.records)
    assert after == stream_before  # silence does not create stream records


def test_05_passivity_probe_off_vs_on():
    cfg = acanthostega_local_signal_config()

    def run(enabled: bool):
        rt = PhysicalSystemRuntime(seed=61, config=cfg)
        rt.body.osc_emit_remaining = 2
        rt.body.osc_amp_u = 0.6
        if enabled:
            configure_probe(rt.world, enabled=True, x=float(rt.body.x) + 3.0, y=float(rt.body.y))
        else:
            ensure_probe_state(rt.world)
            configure_probe(rt.world, enabled=False, x=0.0, y=0.0)
        for _ in range(4):
            rt.step()
        return rt, _phys_fingerprint(rt)

    rt_off, fp_off = run(False)
    rt_on, fp_on = run(True)
    _bump(8)
    assert fp_off == fp_on
    # Probe samples exist only when enabled
    assert not state_of(rt_off.world).samples or not state_of(rt_off.world).enabled
    assert state_of(rt_on.world).enabled
    assert state_of(rt_on.world).samples


def test_06_move_probe_and_dedup_and_restore():
    cfg = acanthostega_local_signal_config()
    rt = PhysicalSystemRuntime(seed=71, config=cfg)
    lps.queue_researcher_emission(
        rt.world, cfg, x=10.5, y=10.5, band_energies=[0.8] * 6, researcher_id="move"
    )
    configure_probe(rt.world, enabled=True, x=12.5, y=10.5)
    for _ in range(4):
        rt.step(); _bump(1)
    st = state_of(rt.world)
    n0 = len(st.samples)
    # Polling dedup
    for _ in range(5):
        sample_observer_acoustic_probe(rt.world, scientific_tick=int(lps.state_of(rt.world).last_processed_tick))
    assert len(st.samples) == n0
    assert st.deduplicated_read_count >= 1
    # Move probe — changes future samples only
    fp_before = _phys_fingerprint(rt)
    configure_probe(rt.world, enabled=True, x=14.5, y=10.5)
    assert _phys_fingerprint(rt) == fp_before
    rt.step(); _bump(1)
    assert len(st.samples) >= n0
    # Restore
    snap = json.loads(json.dumps(rt.snapshot()))
    assert "observer_acoustic_probe_state" in snap["world"] or "observer_acoustic_probe_state" in snap
    n_before = len(st.samples)
    ids = [s["sample_key"] for s in st.samples]
    rt2 = PhysicalSystemRuntime.restore(snap)
    st2 = state_of(rt2.world)
    assert st2 is not None
    assert len(st2.samples) == n_before
    assert [s["sample_key"] for s in st2.samples] == ids
    # No re-sample on restore alone
    assert st2.sample_computation_count == st.sample_computation_count


def test_07_write_budget():
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "TICK_BUDGET.txt").write_text(f"TOTAL_SIMULATED_TICKS={TICKS}\n", encoding="utf-8")
    assert TICKS <= 100
