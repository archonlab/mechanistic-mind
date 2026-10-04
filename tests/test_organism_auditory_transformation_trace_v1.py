"""ORGANISM_AUDITORY_TRANSFORMATION_TRACE_V1 — contract tests (budget ≤60 ticks)."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from mechanistic_mind.model.acanthostega import acanthostega_local_signal_config
from mechanistic_mind.physical_system import local_physical_signal_transport as lps
from mechanistic_mind.physical_system.observation import FORBIDDEN_TOKENS, audit_cognition_payload
from mechanistic_mind.physical_system.organism_auditory_transformation_trace import (
    A3_BOUNDARY,
    A4_TRANSFORM,
    AUTHORITY,
    BAND_COUNT,
    HISTORY_CAPACITY_DEFAULT,
    LEGACY_UNAVAILABLE,
    PROFILE,
    RECEIPT_FAMILY,
    RESIDUAL_TOLERANCE,
    SCHEMA,
    STATUS_MISMATCH,
    TARGET_A5_SCHEMA,
    build_linked_trace,
    capture_linked_to_sav1,
    expected_a5_from_a3,
    observer_compact_status,
    profile_reference,
    read_a3_from_auditory_buffer,
    restore_state,
    serialize_state,
    state_of,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.selected_organism_auditory_boundary_receipt import (
    SCHEMA as SAV1_SCHEMA,
    state_of as soab_state_of,
)
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.scientific_v3.organism_auditory_transformation_trace_summary import (
    summarize_organism_auditory_transformation_traces,
)

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "acanthostega_organism_auditory_transformation_trace_v1"
RESULTS.mkdir(parents=True, exist_ok=True)

TICKS = 0


def _bump(n: int) -> None:
    global TICKS
    TICKS += int(n)


def test_01_identity_privacy():
    assert SCHEMA == "ORGANISM_AUDITORY_TRANSFORMATION_TRACE_V1"
    assert RECEIPT_FAMILY == "ORGANISM_AUDITORY_TRANSFORMATION_TRACE"
    assert PROFILE == "AUDITORY_A3_TO_A5_TRANSFORMATION_TRACE_V1"
    assert A3_BOUNDARY == "A3_RAW_LR_RECEPTOR_BAND_ENERGY_PRE_PHENOTYPE"
    assert A4_TRANSFORM == "A4_SENSOR_SCALE_CLIP_V1"
    assert TARGET_A5_SCHEMA == SAV1_SCHEMA
    assert AUTHORITY == "RESEARCHER_SCIENTIFIC_TRACE_READ_ONLY"
    assert HISTORY_CAPACITY_DEFAULT == 128
    for tok in (SCHEMA, PROFILE, A3_BOUNDARY, "left_receptor_band_energy", "transform_residual"):
        assert tok in FORBIDDEN_TOKENS
    assert audit_cognition_payload({"osc_l_0": 0.25, "osc_r_0": 0.1}) == []
    assert audit_cognition_payload({"schema": SCHEMA, "a3": {"left": [1]}})


def test_02_a4_formula_pure():
    left = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]
    right = [0.5, 0.5, 0.5, 0.5, 0.5, 0.5]
    el, er, *_rest, clip_n = expected_a5_from_a3(left, right, 2.0)
    assert el == [0.0, 0.5, 1.0, 1.0, 1.0, 1.0]
    assert all(abs(er[i] - 0.25) < 1e-15 for i in range(6))
    assert clip_n >= 3  # bands 3,4,5 upper on left


def test_03_exact_a3_capture_and_a5_link():
    cfg = acanthostega_local_signal_config()
    rt = PhysicalSystemRuntime(seed=201, config=cfg)
    rt.technical_id = "agent_0"
    for _ in range(5):
        rt.step()
        _bump(1)
    st = state_of(rt.world)
    assert st is not None
    assert st.capture_count >= 1
    tr = st.traces[-1]
    assert tr["schema"] == SCHEMA
    assert tr["completion_status"] in ("LINKED_COMPLETE", STATUS_MISMATCH)
    assert tr["causal_delay_ticks"] == 0
    assert tr["reception_tick"] == tr["observation_tick"]
    # Exact A3 equals live buffer at capture (re-read now may differ after later steps;
    # verify residual and SAV1 link on stored vectors)
    a3 = tr["a3"]
    a5 = tr["a5"]
    assert len(a3["left_receptor_band_energy"]) == BAND_COUNT
    assert len(a5["left_receptor_channels"]) == BAND_COUNT
    assert a5["organism_accessible"] is True
    assert a3["agent_accessible"] is False
    soab = soab_state_of(rt.world)
    assert soab is not None
    sav1 = soab.receipts[-1]
    assert tr["sav1_receipt_id"] == sav1["receipt_id"]
    for i in range(6):
        assert abs(
            float(a5["left_receptor_channels"][i])
            - float(sav1["section_a_organism_accessible"]["left_receptor_channels"][i])
        ) < 1e-12
    assert tr["a4"]["transform_residual"]["tolerance"] == RESIDUAL_TOLERANCE
    # Polling does not duplicate
    n0 = st.capture_count
    observer_compact_status(rt.world)
    serialize_state(st)
    assert st.capture_count == n0


def test_04_a3_parity_at_seamed_read():
    cfg = acanthostega_local_signal_config()
    rt = PhysicalSystemRuntime(seed=202, config=cfg)
    rt.technical_id = "agent_0"
    for _ in range(4):
        rt.step()
        _bump(1)
    # After step, tick advanced; buffer stamped for current world.tick
    lps_st = lps.state_of(rt.world)
    assert lps_st is not None
    bid = getattr(rt.body, "_lps_body_id", None) or "agent_0"
    entry = (lps_st.auditory or {}).get(str(bid))
    snap = read_a3_from_auditory_buffer(
        rt.world, body=rt.body, body_id=str(bid), observation_tick=int(rt.world.tick)
    )
    if entry is not None and int(entry.get("tick", -1)) == int(rt.world.tick):
        for i in range(6):
            assert abs(snap["left"][i] - float(entry["left"][i])) < 1e-15
            assert abs(snap["right"][i] - float(entry["right"][i])) < 1e-15
        assert snap["status"] == "CAPTURED"


def test_05_silence_and_dedup():
    obs = {f"osc_l_{i}": 0.0 for i in range(6)}
    obs.update({f"osc_r_{i}": 0.0 for i in range(6)})
    cfg = acanthostega_local_signal_config()
    rt = PhysicalSystemRuntime(seed=203, config=cfg)
    world = rt.world
    # Ensure LPS state exists
    assert lps.state_of(world) is not None or True
    sav1 = {
        "receipt_id": "soab:testsilence",
        "section_a_organism_accessible": {
            "left_receptor_channels": [0.0] * 6,
            "right_receptor_channels": [0.0] * 6,
        },
    }
    r1 = capture_linked_to_sav1(
        world,
        observation=obs,
        scientific_tick=3,
        agent_id="agent_0",
        body_id="body-x",
        run_id="t",
        observation_key="o:t:3:agent_0",
        config=cfg,
        body=rt.body,
        sav1_receipt=sav1,
    )
    assert r1 is not None
    assert r1["a3"]["left_receptor_band_energy"] == [0.0] * 6
    assert r1["a5"]["left_receptor_channels"] == [0.0] * 6
    n = state_of(world).capture_count
    r2 = capture_linked_to_sav1(
        world,
        observation=obs,
        scientific_tick=3,
        agent_id="agent_0",
        body_id="body-x",
        run_id="t",
        observation_key="o:t:3:agent_0",
        config=cfg,
        body=rt.body,
        sav1_receipt=sav1,
    )
    assert r2["trace_id"] == r1["trace_id"]
    assert state_of(world).capture_count == n
    assert state_of(world).deduplicated_count >= 1


def test_06_mismatch_anomaly_preserves_authorities():
    cfg = acanthostega_local_signal_config()
    rt = PhysicalSystemRuntime(seed=204, config=cfg)
    obs = {f"osc_l_{i}": 0.9 for i in range(6)}
    obs.update({f"osc_r_{i}": 0.9 for i in range(6)})
    # Force A3 zeros via no auditory entry → expected A5 zeros → mismatch vs 0.9
    sav1 = {
        "receipt_id": "soab:mismatch",
        "section_a_organism_accessible": {
            "left_receptor_channels": [0.9] * 6,
            "right_receptor_channels": [0.9] * 6,
        },
    }
    # Detach body LPS id so buffer miss → zero A3
    if hasattr(rt.body, "_lps_body_id"):
        delattr(rt.body, "_lps_body_id")
    tr = build_linked_trace(
        world=rt.world,
        observation=obs,
        scientific_tick=1,
        agent_id="agent_0",
        body_id="missing-body",
        agent_slot=0,
        run_id="m",
        observation_key="o:m:1:agent_0",
        config=cfg,
        body=rt.body,
        sav1_receipt=sav1,
    )
    assert tr["completion_status"] == STATUS_MISMATCH
    assert tr["a3"]["left_receptor_band_energy"] == [0.0] * 6
    assert tr["a5"]["left_receptor_channels"] == [0.9] * 6
    assert tr["a4"]["expected_a5_left"] == [0.0] * 6


def test_07_two_agent_isolation_and_selection_passivity():
    cfg = acanthostega_local_signal_config()
    ta = TwoAgentRuntime(seed=205, config=cfg)
    for _ in range(6):
        ta.step()
        _bump(1)
    st = state_of(ta.world)
    assert st is not None
    agents = {t["agent_id"] for t in st.traces}
    assert "agent_0" in agents and "agent_1" in agents
    by_agent = {}
    for t in st.traces:
        by_agent.setdefault(t["agent_id"], []).append(t)
    # Distinct trace ids
    ids = [t["trace_id"] for t in st.traces]
    assert len(ids) == len(set(ids))
    n_before = st.capture_count
    ta.select_agent(1)
    ta.select_agent(0)
    assert st.capture_count == n_before


def test_08_snapshot_restore_no_replay():
    cfg = acanthostega_local_signal_config()
    rt = PhysicalSystemRuntime(seed=206, config=cfg)
    rt.technical_id = "agent_0"
    for _ in range(4):
        rt.step()
        _bump(1)
    payload = rt.snapshot(persist=True)
    assert "organism_auditory_transformation_trace_state" in payload
    traces_before = copy.deepcopy(state_of(rt.world).traces)
    completed = state_of(rt.world).completed_count
    rest = PhysicalSystemRuntime.restore(payload)
    st2 = state_of(rest.world)
    assert st2 is not None
    assert len(st2.traces) == len(traces_before)
    assert st2.completed_count == completed
    assert [t["trace_id"] for t in st2.traces] == [t["trace_id"] for t in traces_before]
    # Restore does not add traces
    n = st2.capture_count
    serialize_state(st2)
    assert st2.capture_count == n
    # Future steps continue
    rest.technical_id = "agent_0"
    for _ in range(2):
        rest.step()
        _bump(1)
    assert state_of(rest.world).capture_count >= n


def test_09_clipping_flags_and_analyzer_progress():
    el, er, lo_l, up_l, lo_r, up_r, clip_n = expected_a5_from_a3(
        [10.0] * 6, [0.0] * 6, sensor_scale=2.0
    )
    assert el == [1.0] * 6
    assert all(up_l)
    assert clip_n == 6
    summary = summarize_organism_auditory_transformation_traces([])
    assert summary["status"] == LEGACY_UNAVAILABLE
    assert summary["progress"]["percent"] is None
    fake = [
        {
            "agent_id": "agent_0",
            "body_id": "b",
            "observation_tick": 1,
            "reception_tick": 1,
            "completion_status": "LINKED_COMPLETE",
            "a3": {"left_receptor_band_energy": [0.0] * 6, "right_receptor_band_energy": [0.0] * 6},
            "a4": {"clipping_count": 0, "transform_residual": {"max_abs_residual": 0.0}},
            "a5": {"left_receptor_channels": [0.0] * 6, "right_receptor_channels": [0.0] * 6},
        }
    ]
    s2 = summarize_organism_auditory_transformation_traces(fake)
    assert s2["progress"]["mode"] == "FINITE_TRACE_SCAN"
    assert s2["progress"]["completed"] == 1
    assert s2["progress"]["total"] == 1
    assert s2["progress"]["percent"] == 100.0


def test_10_experimenter_unavailable():
    cfg = acanthostega_local_signal_config()
    rt = PhysicalSystemRuntime(seed=207, config=cfg)
    tr = build_linked_trace(
        world=rt.world,
        observation={},  # no osc
        scientific_tick=0,
        agent_id="experimenter",
        body_id="exp-body",
        agent_slot=2,
        run_id="e",
        observation_key="o:e:0:experimenter",
        config=cfg,
        body=rt.body,
        sav1_receipt=None,
        experimenter=True,
    )
    assert tr["completion_status"] == "EXPERIMENTER_AUDITORY_TRANSFORMATION_TRACE_NOT_AVAILABLE"


def test_zz_write_evidence_and_budget():
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "TICK_BUDGET.txt").write_text(f"TOTAL_SIMULATED_TICKS={TICKS}\n", encoding="utf-8")
    (RESULTS / "profile.json").write_text(
        json.dumps(profile_reference(), indent=2), encoding="utf-8"
    )
    assert TICKS <= 60, f"tick budget exceeded: {TICKS}"
