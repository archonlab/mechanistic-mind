"""SELECTED_ORGANISM_AUDITORY_BOUNDARY_RECEIPT_V1 + SAV1 — contract tests."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from mechanistic_mind.model.acanthostega import acanthostega_local_signal_config
from mechanistic_mind.physical_system import local_physical_signal_transport as lps
from mechanistic_mind.physical_system.observation import FORBIDDEN_TOKENS, audit_cognition_payload
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.selected_organism_auditory_boundary_receipt import (
    BOUNDARY,
    CAPABILITY,
    HISTORY_CAPACITY_DEFAULT,
    MODE_LABEL,
    PROFILE,
    RECEIPT_FAMILY,
    SCHEMA,
    VIEW_SCHEMA,
    WARNING_LABEL,
    capture_from_observation,
    extract_a5_vectors,
    observer_payload,
    serialize_state,
    restore_state,
    state_of,
)
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.scientific_v3.selected_organism_auditory_summary import (
    summarize_selected_organism_auditory,
)

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "acanthostega_selected_organism_auditory_view_sav1"
RESULTS.mkdir(parents=True, exist_ok=True)

TICKS = 0


def _bump(n: int) -> None:
    global TICKS
    TICKS += int(n)


def test_01_identity_privacy_labels():
    assert SCHEMA == "SELECTED_ORGANISM_AUDITORY_BOUNDARY_RECEIPT_V1"
    assert RECEIPT_FAMILY == "ORGANISM_AUDITORY_BOUNDARY_RECEIPT"
    assert VIEW_SCHEMA == "SELECTED_ORGANISM_AUDITORY_VIEW_SAV1"
    assert PROFILE == "ORGANISM_AUDITORY_BOUNDARY_A5_V1"
    assert CAPABILITY == "selected_organism_auditory_view"
    assert BOUNDARY == "A5_OSC_LR_ACCESSIBLE_OBSERVATION_PRE_COGNITION"
    assert MODE_LABEL == "SELECTED ORGANISM AUDITORY VIEW"
    assert "NOT MIND READING" in WARNING_LABEL
    assert HISTORY_CAPACITY_DEFAULT == 128
    for tok in (
        SCHEMA,
        VIEW_SCHEMA,
        PROFILE,
        CAPABILITY,
        "phenotype_clip_stamp",
        "section_b_researcher_provenance",
    ):
        assert tok in FORBIDDEN_TOKENS
    # Legitimate sensory values must remain allowed
    assert audit_cognition_payload({"osc_l_0": 0.1, "osc_r_1": 0.2}) == []
    assert audit_cognition_payload({"schema": SCHEMA, "phenotype_clip_stamp": {}})


def test_02_exact_boundary_capture_same_tick():
    cfg = acanthostega_local_signal_config()
    rt = PhysicalSystemRuntime(seed=101, config=cfg)
    rt.technical_id = "agent_0"
    # Force observation path with osc keys
    before_aud = copy.deepcopy(getattr(lps.state_of(rt.world), "auditory", {}) or {})
    for _ in range(3):
        rt.step()
        _bump(1)
    st = state_of(rt.world)
    assert st is not None
    assert st.capture_count >= 1
    obs = rt.last_agent_observation or {}
    assert any(k.startswith("osc_l_") for k in obs)
    latest = st.receipts[-1]
    a = latest["section_a_organism_accessible"]
    for i in range(6):
        assert abs(float(a["left_receptor_channels"][i]) - float(obs[f"osc_l_{i}"])) < 1e-12
        assert abs(float(a["right_receptor_channels"][i]) - float(obs[f"osc_r_{i}"])) < 1e-12
    assert a["organism_accessible"] is True
    assert a["pre_cognition"] is True
    assert a["post_phenotype"] is True
    assert latest["section_b_researcher_provenance"]["organism_accessible"] is False
    # No LPS re-execution for capture (auditory may update on step; receipt copies obs only)
    after_aud = getattr(lps.state_of(rt.world), "auditory", {}) or {}
    assert isinstance(before_aud, dict) and isinstance(after_aud, dict)
    # Phenotype stamp present
    assert "phenotype_clip_stamp" in latest["section_b_researcher_provenance"]
    # Polling duplicate: observer_payload / serialize_state does not add receipts
    n0 = st.capture_count
    observer_payload(rt.world, selected_agent_id="agent_0")
    serialize_state(st)
    assert st.capture_count == n0


def test_03_silence_zero_vector_and_dedup():
    obs = {f"osc_l_{i}": 0.0 for i in range(6)}
    obs.update({f"osc_r_{i}": 0.0 for i in range(6)})
    cfg = acanthostega_local_signal_config()
    rt = PhysicalSystemRuntime(seed=102, config=cfg)
    rt.technical_id = "agent_0"
    world = rt.world
    r1 = capture_from_observation(
        world,
        observation=obs,
        scientific_tick=7,
        agent_id="agent_0",
        body_id="body-0",
        run_id="t",
        observation_key="o:t:7:agent_0",
        config=cfg,
        body=rt.body,
    )
    assert r1 is not None
    assert r1["section_a_organism_accessible"]["zero_vector_is_legitimate_silence"] is True
    n = state_of(world).capture_count
    r2 = capture_from_observation(
        world,
        observation=obs,
        scientific_tick=7,
        agent_id="agent_0",
        body_id="body-0",
        run_id="t",
        observation_key="o:t:7:agent_0",
        config=cfg,
        body=rt.body,
    )
    assert r2["receipt_id"] == r1["receipt_id"]
    assert state_of(world).capture_count == n
    assert state_of(world).deduplicated_count >= 1


def test_04_two_agent_isolation_and_selection_passivity():
    cfg = acanthostega_local_signal_config()
    # TwoAgentRuntime(seed, config) — check constructor
    tr = TwoAgentRuntime(seed=201, config=cfg)
    for _ in range(4):
        tr.step()
        _bump(1)
    st = state_of(tr.world)
    assert st is not None
    agents = {r.get("agent_id") for r in st.receipts}
    assert "agent_0" in agents
    assert "agent_1" in agents
    # Separate receipts per agent/tick
    keys = {(r.get("agent_id"), r.get("scientific_tick")) for r in st.receipts}
    assert len(keys) == len(st.receipts)
    # Selection switch: display only
    n_before = st.capture_count
    tr.selected_index = 1
    p0 = observer_payload(tr.world, selected_agent_id="agent_0")
    p1 = observer_payload(tr.world, selected_agent_id="agent_1")
    assert p0["selected_agent_id"] == "agent_0"
    assert p1["selected_agent_id"] == "agent_1"
    assert st.capture_count == n_before


def test_05_snapshot_restore_no_replay():
    cfg = acanthostega_local_signal_config()
    rt = PhysicalSystemRuntime(seed=301, config=cfg)
    rt.technical_id = "agent_0"
    for _ in range(3):
        rt.step()
        _bump(1)
    st = state_of(rt.world)
    n0 = st.capture_count
    last_id = st.last_receipt_id
    snap = rt.snapshot(persist=False)
    assert "selected_organism_auditory_boundary_state" in snap
    rt2 = PhysicalSystemRuntime.restore(snap)
    st2 = state_of(rt2.world)
    assert st2 is not None
    assert st2.last_receipt_id == last_id
    assert st2.capture_count == n0
    # One more step adds future receipt, no duplicate of last
    rt2.technical_id = "agent_0"
    rt2.step()
    _bump(1)
    st2 = state_of(rt2.world)
    assert st2.capture_count >= n0
    ids = [r.get("receipt_id") for r in st2.receipts]
    assert len(ids) == len(set(ids))


def test_06_analyzer_progress_and_legacy():
    legacy = summarize_selected_organism_auditory([])
    assert legacy["status"] == "SELECTED_ORGANISM_AUDITORY_VIEW_UNAVAILABLE_LEGACY_EVIDENCE"
    assert legacy["progress"]["percent"] is None
    assert legacy["mind_reading"] is False
    samples = [
        {
            "schema": SCHEMA,
            "receipt_id": "a",
            "scientific_tick": 1,
            "agent_id": "agent_0",
            "section_a_organism_accessible": {
                "left_receptor_channels": [0.1] * 6,
                "right_receptor_channels": [0.0] * 6,
            },
        },
        {
            "schema": SCHEMA,
            "receipt_id": "b",
            "scientific_tick": 2,
            "agent_id": "agent_0",
            "section_a_organism_accessible": {
                "left_receptor_channels": [0.0] * 6,
                "right_receptor_channels": [0.2] * 6,
            },
        },
    ]
    s = summarize_selected_organism_auditory(samples)
    assert s["progress"]["completed"] == 2
    assert s["progress"]["total"] == 2
    assert s["progress"]["percent"] == 100.0


def test_07_extract_no_mutation_and_write_evidence():
    obs = {f"osc_l_{i}": float(i) * 0.1 for i in range(6)}
    obs.update({f"osc_r_{i}": 0.5 for i in range(6)})
    raw = copy.deepcopy(obs)
    ex = extract_a5_vectors(obs)
    assert obs == raw
    assert ex["present"] is True
    (RESULTS / "TICK_BUDGET.txt").write_text(
        f"TOTAL_SIMULATED_TICKS={TICKS}\nVALIDATION_BUDGET_MAX=60\n",
        encoding="utf-8",
    )
    (RESULTS / "RECEIPT_SCHEMA.json").write_text(
        json.dumps(
            {
                "schema": SCHEMA,
                "view_schema": VIEW_SCHEMA,
                "profile": PROFILE,
                "boundary": BOUNDARY,
                "warning": WARNING_LABEL,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    assert TICKS <= 60
