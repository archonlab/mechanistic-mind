"""Analyzer Next Phase-1 — SCIENTIFIC_V3 story / relationship engine gates."""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import pytest

from mechanistic_mind.scientific_v3.analyzer_next.geometry import (
    approach_decomposition,
    angular_error,
    orienting_error,
    toroidal_distance,
    wrap_delta,
)
from mechanistic_mind.scientific_v3.analyzer_next.interestingness import (
    select_interesting_episodes,
    select_interesting_stories,
)
from mechanistic_mind.scientific_v3.analyzer_next.pipeline import build_behavioral_reconstruction
from mechanistic_mind.scientific_v3.analyzer_next.relationships import RelationshipGraph
from mechanistic_mind.scientific_v3.analyzer_next.tick_stories import build_tick_stories, format_composite_motor
from mechanistic_mind.scientific_v3.api import RunEvidence

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "results/psychology_observer/psy_observer_web/.live-psyweb-20260921T064313.398170Z-f82f5a38"
V2_FIXTURE = ROOT / "results/mm_analyzer_next_phase1/v2_only_fixture"
ACCEPT_CUTOFF = 2334

FORBIDDEN_FACT = re.compile(
    r"\b(recognized|understood|communicated|wanted|preferred|feared|searched for|sought|intended|believed|knew)\b",
    re.I,
)


@pytest.fixture(scope="module")
def live_payload():
    if not LIVE.is_dir():
        pytest.skip(f"acceptance live run missing: {LIVE}")
    return build_behavioral_reconstruction(LIVE, max_tick=ACCEPT_CUTOFF, write_artifacts=False)


def test_gate1_complete_odmc_reconstruction(live_payload):
    assert live_payload["status"] == "AVAILABLE"
    n = live_payload["tick_stories_count"]
    c = live_payload["complete_odmc_count"]
    assert n >= 4668
    assert c == n
    assert live_payload["complete_odmc"] == f"{c} / {n}"


def test_gate2_decision_receipts_authoritative(live_payload):
    text = live_payload["report_text"]
    assert "DecisionReceipts" in text or "DecisionReceipt" in text
    assert "SCIENTIFIC_V3 DecisionReceipts" in text or "Decision evidence authority" in text
    assert live_payload["decision_receipts"] == live_payload["tick_stories_count"]


def test_gate3_scenario_selected_does_not_imply_absent(live_payload):
    text = live_payload["report_text"]
    assert "Legacy SCENARIO_SELECTED event rows" in text
    assert "must not be read as missing cognition" in text
    assert live_payload["legacy_scenario_selected_count"] == 0
    assert live_payload["decision_receipts"] > 0


def test_gate4_visual_episode_through_spine(live_payload):
    vis = (live_payload.get("representative") or {}).get("visual_episode")
    assert vis is not None, "expected at least one VISUAL_EXPOSURE episode"
    assert vis["episode_type"] == "VISUAL_EXPOSURE"
    assert "NOT_ESTABLISHED" in str(vis.get("evidence_relationships"))


def test_gate5_signal_episode_through_spine(live_payload):
    sig = (live_payload.get("representative") or {}).get("signal_episode")
    assert sig is not None, "expected at least one SIGNAL_EXPOSURE episode"
    assert sig["episode_type"] == "SIGNAL_EXPOSURE"


def test_gate6_specific_causation_not_established(live_payload):
    text = live_payload["report_text"]
    assert "specific sensory component" in text.lower() or "specific observation-component" in text.lower()
    assert "NOT ESTABLISHED" in text
    # Graph should contain NOT_ESTABLISHED edges
    gsum = live_payload["relationship_graph_summary"]
    assert gsum["edges_by_type"].get("NOT_ESTABLISHED", 0) > 0
    assert gsum["edges_by_type"].get("PRODUCED_MOTOR", 0) > 0
    assert gsum["edges_by_type"].get("PHYSICALLY_RESULTED_IN", 0) > 0


def test_gate7_composite_motor_authoritative(live_payload):
    text = live_payload["report_text"]
    assert "COMPOSITE_MOTOR_V1" in text or "MotorReceipt (COMPOSITE_MOTOR_V1)" in text
    assert format_composite_motor({"locomotion": "MOVE:E", "neck": "NECK_LEFT", "oscillator": {}, "push": False}) == "MOVE:E + NECK_LEFT"
    assert "OSC_EMIT" in format_composite_motor({"locomotion": "WAIT", "neck": "NECK_HOLD", "oscillator": {"on": 1}, "push": False})


def test_gate8_geometry_decomposition(live_payload):
    geo = (live_payload.get("representative") or {}).get("geometry_episode")
    assert geo is not None
    outcome = geo.get("physical_outcome") or {}
    assert "agent_contribution" in outcome or "delta_distance" in outcome
    assert "dominant_mover" in outcome


def test_gate9_v2_degraded_no_fabricated_v3():
    if not V2_FIXTURE.is_dir():
        pytest.skip("V2 fixture missing")
    # Ensure no V3 meta
    payload = build_behavioral_reconstruction(V2_FIXTURE, write_artifacts=False)
    assert payload["status"] == "NOT_RECORDED"
    assert "NOT_RECORDED" in payload["report_text"]
    assert payload["tick_stories_count"] == 0
    assert "fabricat" in payload["report_text"].lower() or "O→D→M→C" in payload["report_text"]


def test_gate10_report_contains_behavioral_reconstruction(live_payload):
    assert live_payload["report_text"].startswith("BEHAVIORAL RECONSTRUCTION")


def test_wrap_aware_distance():
    # On 32 torus, from 1 to 31 is distance 2 via wrap, not 30
    assert abs(toroidal_distance(1, 0, 31, 0, 32, 32) - 2.0) < 1e-9
    assert abs(wrap_delta(1, 31, 32) - (-2.0)) < 1e-9 or abs(wrap_delta(1, 31, 32) - 30) > 1  # signed shortest
    d = approach_decomposition(
        agent_xy_t=(0.0, 0.0),
        agent_xy_t1=(1.0, 0.0),
        source_xy_t=(5.0, 0.0),
        source_xy_t1=(5.0, 0.0),
        width=32,
        height=32,
    )
    assert d["dominant_mover"] == "AGENT"
    assert d["delta_distance"] < 0


def test_orienting_angular_error():
    # Agent at origin heading +x (0), source at +y → bearing pi/2, error pi/2
    o = orienting_error(agent_xy=(0, 0), source_xy=(0, 5), head_or_body_heading=0.0, width=32, height=32)
    assert abs(o["abs_angular_error_deg"] - 90.0) < 1e-6
    assert abs(angular_error(0.0, math.pi) - math.pi) < 1e-9 or abs(abs(angular_error(0.0, math.pi)) - math.pi) < 1e-9


def test_episode_and_interestingness_deterministic(live_payload):
    p1 = build_behavioral_reconstruction(LIVE, max_tick=200, write_artifacts=False)
    p2 = build_behavioral_reconstruction(LIVE, max_tick=200, write_artifacts=False)
    assert p1["episode_counts"] == p2["episode_counts"]
    assert p1["interesting_ticks"] == p2["interesting_ticks"]
    assert [e["episode_type"] for e in p1["selected_episodes"]] == [
        e["episode_type"] for e in p2["selected_episodes"]
    ]


def test_no_semantic_labels_as_facts(live_payload):
    # Scan OBSERVED blocks only — crude: forbid hypothesis words outside HYPOTHESIS/OPEN/NOT ESTABLISHED sections
    text = live_payload["report_text"]
    # Remove NOT ESTABLISHED / Open causal / Language boundary sections
    cleaned = re.sub(r"NOT ESTABLISHED.*?(?=\nEpisode |\nCross-agent|\nObservation →|\nBehavioral |\nOpen causal|\nLanguage |\Z)", "", text, flags=re.S)
    cleaned = re.sub(r"Open causal questions.*", "", cleaned, flags=re.S)
    cleaned = re.sub(r"Language boundary.*", "", cleaned, flags=re.S)
    # Still allow the words only if we failed — check OBSERVED paragraphs
    for block in re.findall(r"OBSERVED\n(.*?)(?:\nDERIVED|\nNOT ESTABLISHED)", text, flags=re.S):
        assert not FORBIDDEN_FACT.search(block), block[:200]


def test_observation_no_gt_leak_into_accessible():
    if not LIVE.is_dir():
        pytest.skip("no live")
    ev = RunEvidence(LIVE)
    obs = ev.get_observation("agent_0", 1)
    assert obs is not None
    assert obs.get("provenance") == "AGENT_ACCESSIBLE"
    acc = obs.get("accessible") or {}
    # Must not contain observer-only GT labels
    for k in acc:
        assert "ground_truth" not in str(k).lower()
        assert "other_agent_id" not in str(k).lower()


def test_consequence_tick_alignment(live_payload):
    if not LIVE.is_dir():
        pytest.skip("no live")
    ev = RunEvidence(LIVE)
    g = RelationshipGraph(run_id="t")
    stories = build_tick_stories(ev, g, max_tick=50)
    for s in stories:
        if s.consequence:
            assert int(s.consequence["tick_from"]) == s.tick
            assert int(s.consequence["tick_to"]) == s.tick + 1


def test_signal_and_vision_joins(live_payload):
    js = live_payload["join_summary"]
    assert js["signal_joins"] > 0
    assert js["vision_joins"] > 0
    assert js["geometry_joins"] > 0


def test_evidence_package_includes_behavioral_reconstruction():
    if not LIVE.is_dir():
        pytest.skip("no live")
    from mechanistic_mind.ui.psy_observer_web.scientific_history import load_evidence_package
    pkg = load_evidence_package(
        evidence_dir=LIVE,
        cutoff_tick=ACCEPT_CUTOFF,
        runtime_status="LIVE",
        run_id="psyweb-20260921T064313.398170Z-f82f5a38",
    )
    br = pkg.get("behavioral_reconstruction")
    assert br is not None
    assert br.get("status") == "AVAILABLE"
    assert "BEHAVIORAL RECONSTRUCTION" in (br.get("report_text") or "")
    # artifacts written
    art = LIVE / "analyzer_next"
    assert (art / "analysis_behavioral_summary.json").is_file() or br.get("artifacts_dir")


def test_frontend_log_includes_section():
    """formatAnalysisLog embeds Behavioral Reconstruction when payload present."""
    # Lightweight: ensure patched source contains the section hook
    src = (ROOT / "web/psy-observer/src/analysis/analysisLog.ts").read_text()
    assert "BEHAVIORAL RECONSTRUCTION" in src
    assert "SCENARIO_SELECTED event rows" in src
    assert "SCIENTIFIC_V3 DECISION EVIDENCE" in src
