"""Analyzer Next — sensorimotor consequence gates (target run f82f5a38)."""
from __future__ import annotations

from pathlib import Path

import pytest

from mechanistic_mind.scientific_v3.analyzer_next.geometry import approach_decomposition, toroidal_distance
from mechanistic_mind.scientific_v3.analyzer_next.pipeline import build_behavioral_reconstruction
from mechanistic_mind.scientific_v3.analyzer_next.sensorimotor import (
    build_sensorimotor_steps,
    detect_motor_reversals,
    find_receding_while_watching,
)

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "results/psychology_observer/psy_observer_web/.live-psyweb-20260921T064313.398170Z-f82f5a38"
V2 = ROOT / "results/mm_analyzer_next_phase1/v2_only_fixture"


@pytest.fixture(scope="module")
def full_payload():
    if not LIVE.is_dir():
        pytest.skip("live run missing")
    return build_behavioral_reconstruction(LIVE, max_tick=None, write_artifacts=False)


def test_gate1_odmc_complete(full_payload):
    assert full_payload["status"] == "AVAILABLE"
    assert full_payload["complete_odmc_count"] == full_payload["tick_stories_count"]
    assert full_payload["tick_stories_count"] >= 7042


def test_gate2_tickstory_per_autonomous_tick(full_payload):
    assert full_payload["tick_stories_count"] >= 7042


def test_gate3_4_vision_signal_joins(full_payload):
    js = full_payload["join_summary"]
    assert js["vision_joins"] > 0
    assert js["signal_joins"] > 0


def test_gate5_decision_receipts_authoritative(full_payload):
    text = full_payload["report_text"]
    assert "Decision evidence authority: SCIENTIFIC_V3 DecisionReceipts" in text
    assert "Legacy SCENARIO_SELECTED" in text


def test_gate6_composite_motor(full_payload):
    assert "COMPOSITE_MOTOR_V1" in full_payload["report_text"]


def test_gate7_8_wrap_and_decomposition():
    assert abs(toroidal_distance(1, 0, 31, 0, 32, 32) - 2.0) < 1e-9
    d = approach_decomposition(
        agent_xy_t=(0, 0), agent_xy_t1=(2, 0),
        source_xy_t=(8, 0), source_xy_t1=(8, 0),
        width=32, height=32,
    )
    assert d["dominant_mover"] == "AGENT"
    assert d["delta_distance"] < 0


def test_gate9_approach_or_withdrawal(full_payload):
    counts = full_payload["episode_counts"]
    assert counts.get("APPROACH", 0) + counts.get("WITHDRAWAL", 0) > 0


def test_gate10_focus_region(full_payload):
    focus = full_payload.get("focus_3250_3315") or {}
    assert focus.get("interval") == [3250, 3315]
    agents = focus.get("agents") or {}
    assert "agent_0" in agents and "agent_1" in agents
    assert len(agents["agent_0"]) > 0


def test_gate11_12_recede_and_reversals_measured(full_payload):
    assert "receding_while_watching" in full_payload
    assert isinstance(full_payload["receding_while_watching"], list)
    assert full_payload["motor_reversals_count"] >= 0
    assert full_payload["sensorimotor_trend_reversals_count"] >= 0
    assert "SENSORIMOTOR CONSEQUENCE ANALYSIS" in (full_payload.get("sensorimotor_report_text") or "")


def test_gate13_longitudinal(full_payload):
    longit = full_payload.get("longitudinal") or {}
    assert longit.get("label") == "LONGITUDINAL_CHANGE"
    assert "EARLY" in (longit.get("windows") or {})


def test_gate14_asymmetry_explained(full_payload):
    asym = full_payload.get("visual_asymmetry") or {}
    assert "per_agent" in asym
    assert len(asym.get("candidate_explanations") or []) >= 1


def test_gate15_report_sections(full_payload):
    assert full_payload["report_text"].startswith("BEHAVIORAL RECONSTRUCTION") or "WHAT HAPPENED" in full_payload["report_text"]
    assert "SENSORIMOTOR CONSEQUENCE ANALYSIS" in full_payload["sensorimotor_report_text"]
    src = (ROOT / "web/psy-observer/src/analysis/analysisLog.ts").read_text()
    assert "sensorimotor_report_text" in src


def test_gate16_v2_degraded():
    if not V2.is_dir():
        pytest.skip("v2 fixture missing")
    p = build_behavioral_reconstruction(V2, write_artifacts=False)
    assert p["status"] == "NOT_RECORDED"


def test_specific_causation_not_established(full_payload):
    assert "NOT_ESTABLISHED" in full_payload["report_text"]
    assert "NOT_ESTABLISHED" in full_payload["sensorimotor_report_text"]


def test_no_gt_leak_words_as_facts(full_payload):
    # Recognition must not appear outside NOT ESTABLISHED / boundary
    for block in full_payload["report_text"].split("OBSERVED"):
        head = block.split("NOT ESTABLISHED")[0] if "NOT ESTABLISHED" in block else block
        if "recognized" in head.lower():
            pytest.fail("recognition leaked into OBSERVED")
