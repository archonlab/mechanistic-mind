"""SELECTED_ORGANISM_PHYSICAL_FIELD_COMPARISON_SAV3_V1 — contract tests (≤30 ticks)."""
from __future__ import annotations

from pathlib import Path

from mechanistic_mind.model.acanthostega import acanthostega_local_signal_config
from mechanistic_mind.physical_system.observation import FORBIDDEN_TOKENS, audit_cognition_payload
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.selected_organism_physical_field_comparison import (
    AUTHORITY,
    CAPABILITY,
    LEGACY_UNAVAILABLE,
    PROFILE,
    SCHEMA,
    TITLE,
    WARNING,
    observer_comparison_payload,
    profile_reference,
)
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.scientific_v3.selected_organism_physical_field_comparison_summary import (
    summarize_sav3_comparison,
)

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "acanthostega_selected_organism_physical_field_comparison_sav3_v1"
RESULTS.mkdir(parents=True, exist_ok=True)

TICKS = 0


def _bump(n: int) -> None:
    global TICKS
    TICKS += int(n)


def test_01_identity_privacy():
    assert SCHEMA == "SELECTED_ORGANISM_PHYSICAL_FIELD_COMPARISON_SAV3_V1"
    assert CAPABILITY == "selected_organism_physical_field_comparison"
    assert PROFILE == "A3_TO_A5_CAUSAL_COMPARISON_SAV3_V1"
    assert AUTHORITY == "RESEARCHER_COMPARISON_OVER_AUTHORITATIVE_TRACE"
    assert TITLE == "PHYSICAL FIELD → ORGANISM RECEPTORS"
    assert "ONLY A5 IS ORGANISM-ACCESSIBLE" in WARNING
    assert SCHEMA in FORBIDDEN_TOKENS
    assert CAPABILITY in FORBIDDEN_TOKENS
    assert audit_cognition_payload({"osc_l_0": 0.2, "osc_r_0": 0.1}) == []
    assert audit_cognition_payload({"schema": SCHEMA, "a3": {}})


def test_02_selected_agent_trace_matrix_fields():
    cfg = acanthostega_local_signal_config()
    rt = PhysicalSystemRuntime(seed=401, config=cfg)
    rt.technical_id = "agent_0"
    for _ in range(5):
        rt.step()
        _bump(1)
    payload = observer_comparison_payload(
        rt.world, selected_agent_id="agent_0", run_id=str(getattr(rt, "seed", "live"))
    )
    assert payload["authoritative_input"] == "ORGANISM_AUDITORY_TRANSFORMATION_TRACE_V1"
    assert payload["latest_for_selected"] is not None
    tr = payload["latest_for_selected"]
    assert len(tr["a3"]["left_receptor_band_energy"]) == 6
    assert len(tr["a3"]["right_receptor_band_energy"]) == 6
    assert len(tr["a5"]["left_receptor_channels"]) == 6
    assert len(tr["a5"]["right_receptor_channels"]) == 6
    assert "sensor_scale" in tr["a4"]
    assert "transform_residual" in tr["a4"]
    assert tr["a5"]["organism_accessible"] is True
    assert tr["a3"]["agent_accessible"] is False
    # Wrong agent: no cross-mix
    empty = observer_comparison_payload(rt.world, selected_agent_id="agent_1")
    assert empty["latest_for_selected"] is None


def test_03_two_agent_isolation_and_restore():
    cfg = acanthostega_local_signal_config()
    ta = TwoAgentRuntime(seed=402, config=cfg)
    for _ in range(5):
        ta.step()
        _bump(1)
    p0 = observer_comparison_payload(ta.world, selected_agent_id="agent_0")
    p1 = observer_comparison_payload(ta.world, selected_agent_id="agent_1")
    assert p0["latest_for_selected"]["agent_id"] == "agent_0"
    assert p1["latest_for_selected"]["agent_id"] == "agent_1"
    assert p0["latest_for_selected"]["trace_id"] != p1["latest_for_selected"]["trace_id"]
    n = p0["retained_count"]
    snap = ta.slots[0].snapshot(persist=True)
    # World shared — restore via slot 0
    rt2 = PhysicalSystemRuntime.restore(snap)
    p2 = observer_comparison_payload(rt2.world, selected_agent_id="agent_0")
    assert p2["retained_count"] == n
    assert p2["latest_for_selected"]["trace_id"] == p0["latest_for_selected"]["trace_id"]


def test_04_analyzer_progress_legacy():
    legacy = summarize_sav3_comparison([])
    assert legacy["status"] == LEGACY_UNAVAILABLE
    assert legacy["progress"]["percent"] is None
    assert legacy["mind_reading"] is False
    fake = {
        "agent_id": "agent_0",
        "body_id": "b",
        "observation_tick": 1,
        "reception_tick": 1,
        "completion_status": "LINKED_COMPLETE",
        "a3": {
            "left_receptor_band_energy": [0.0] * 6,
            "right_receptor_band_energy": [0.0] * 6,
            "agent_accessible": False,
        },
        "a4": {"clipping_count": 0, "transform_residual": {"max_abs_residual": 0.0}},
        "a5": {
            "left_receptor_channels": [0.0] * 6,
            "right_receptor_channels": [0.0] * 6,
            "organism_accessible": True,
        },
    }
    s = summarize_sav3_comparison([fake])
    assert s["progress"]["mode"] == "FINITE_TRACE_SCAN"
    assert s["progress"]["completed"] == 1
    assert s["progress"]["total"] == 1
    assert s["progress"]["percent"] == 100.0
    assert s["passive_probe_authority"] is False


def test_zz_budget():
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "TICK_BUDGET.txt").write_text(f"TOTAL_SIMULATED_TICKS={TICKS}\n", encoding="utf-8")
    (RESULTS / "profile.json").write_text(
        __import__("json").dumps(profile_reference(), indent=2), encoding="utf-8"
    )
    assert TICKS <= 30, TICKS
