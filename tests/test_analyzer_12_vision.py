"""Analyzer 1.2 — Beta 3.1 spatial/optical vision scientific fixtures."""
from __future__ import annotations

import json
import resource
from pathlib import Path
from types import SimpleNamespace

import pytest

from mechanistic_mind.scientific_v3.analyzer_next.job import compact_http_result
from mechanistic_mind.scientific_v3.analyzer_next.pipeline import build_behavioral_reconstruction
from mechanistic_mind.scientific_v3.analyzer_next.vision_analysis import (
    EVIDENCE_MATRIX,
    analyze_beta31_vision,
    write_vision_artifacts,
)

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "results/psychology_observer/psy_observer_web/.live-psyweb-20260921T064313.398170Z-f82f5a38"
ARCH_5K = ROOT / "results/mm_scientific_v3_phase1_core/benchmark_slim/v3_10000"
FORBIDDEN = (
    "sees in 3d",
    "understands depth",
    "recognizes terrain",
    "recognizes the other",
    "understands colors",
    "intentionally approaches",
    "communicates",
    "learned to use vision",
    "slingshot strategy",
    "active vision",
)


def _wjsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def _story(
    aid: str,
    tick: int,
    *,
    neck: str = "NECK_HOLD",
    loco: str = "WAIT",
    x: float = 0.0,
    y: float = 0.0,
    theta: float = 0.0,
    head: float = 0.0,
    dist: float | None = None,
    selected: str = "WAIT",
    path: str = "FALLBACK",
    candidate_count: int = 2,
    candidate_id: str = "c0",
) -> SimpleNamespace:
    derived = [
        {"kind": "POSE_STATE", "x": x, "y": y, "theta": theta, "head_world_heading": head},
    ]
    if dist is not None:
        derived.append({"kind": "RELATIVE_GEOMETRY", "toroidal_distance": dist})
    return SimpleNamespace(
        cognitive_agent_id=aid,
        tick=tick,
        motor={"components": {"neck": neck, "locomotion": loco}},
        derived_changes=derived,
        decision={
            "selected_action_legacy": selected,
            "selection_path": path,
            "candidate_count": candidate_count,
            "selected_candidate_id": candidate_id,
        },
        external_context=[],
    )


def _acc(tick: int, aid: str, accessible: dict) -> dict:
    return {"tick": tick, "cognitive_agent_id": aid, "accessible": accessible}


def _run(tmp: Path, obs: list, decisions: list | None = None, events: list | None = None):
    _wjsonl(tmp / "scientific_observations.jsonl", obs)
    _wjsonl(tmp / "scientific_decisions.jsonl", decisions or [])
    _wjsonl(tmp / "scientific_events.jsonl", events or [])
    stories = []
    for row in obs:
        aid = row["cognitive_agent_id"]
        t = row["tick"]
        stories.append(_story(aid, t))
    return analyze_beta31_vision(tmp, stories, out_dir=tmp / "vision_out")


def test_phase0_evidence_matrix_classes():
    classes = {r["field"]: r["class"] for r in EVIDENCE_MATRIX}
    assert classes["exo_0/1/2"] == "AGENT_ACCESSIBLE"
    assert classes["surface_c*"] == "AGENT_ACCESSIBLE"
    assert classes["spatial_exo_a*"] == "AGENT_ACCESSIBLE"
    assert classes["other-agent pose"] == "RESEARCHER_ONLY"
    assert classes["occlusion provenance / sample receipts"] == "RESEARCHER_ONLY"
    assert classes["terrain / world geometry"] == "RESEARCHER_ONLY"
    pe = [r for r in EVIDENCE_MATRIX if r["field"].startswith("PE")][0]
    assert "NOT_RECORDED" in pe["historical"]


def test_1_same_nonvisual_different_surface(tmp_path: Path):
    nv = {"vest_0": 0.1, "vest_1": 0.0, "prop_neck_0": 0.0, "prop_neck_1": 0.0, "local.FIELD_A": 0.0, "local.FIELD_B": 0.0}
    obs = [
        _acc(1, "agent_0", {**nv, "surface_c0_0": 0.1, "exo_0": 0.2}),
        _acc(2, "agent_0", {**nv, "surface_c0_0": 0.9, "exo_0": 0.2}),
    ]
    out = _run(tmp_path, obs)
    surf = out["beta31_vision"]["optical_occupancy"]["agent_0"]["SURFACE"]["surface_c0_0"]
    assert surf["quantized_state_diversity"] >= 2
    assert out["publication"]["SURFACE_CHANNELS_ANALYZED"] == "YES"


def test_2_same_nonvisual_different_spatial_exo(tmp_path: Path):
    nv = {"vest_0": 0.2, "local.FIELD_A": 0.0}
    obs = [
        _acc(1, "agent_0", {**nv, **{f"spatial_exo_a{k}": (0.22 if k == 0 else 0.0) for k in range(5)}}),
        _acc(2, "agent_0", {**nv, **{f"spatial_exo_a{k}": (0.22 if k == 4 else 0.0) for k in range(5)}}),
    ]
    stories = [_story("agent_0", 1), _story("agent_0", 2, neck="NECK_LEFT", head=0.2)]
    _wjsonl(tmp_path / "scientific_observations.jsonl", obs)
    out = analyze_beta31_vision(tmp_path, stories)
    st = out["beta31_vision"]["spatial_transitions"]["agent_0"]
    assert st["spatial_state_diversity"] >= 2
    assert st["transforms"].get("ANGULAR_SHIFT", 0) >= 1


def test_3_head_rotation_changes_spatial_bins(tmp_path: Path):
    test_2_same_nonvisual_different_spatial_exo(tmp_path)
    # coupling classified from dL1 after NECK_LEFT vs WAIT; two ticks only → may be NOT_TESTABLE
    coup = analyze_beta31_vision(
        tmp_path,
        [_story("agent_0", 1), _story("agent_0", 2, neck="NECK_LEFT", head=0.3)],
    )["beta31_vision"]["head_motion_coupling"]["agent_0"]
    assert coup["n_neck"] >= 1
    assert "intention" not in (coup.get("note") or "").lower() or "not" in coup["note"].lower()


def test_4_body_translation_changes_spatial(tmp_path: Path):
    acc0 = {f"spatial_exo_a{k}": 0.1 * (k + 1) for k in range(5)}
    acc1 = {f"spatial_exo_a{k}": 0.2 * (k + 1) for k in range(5)}
    obs = [_acc(1, "agent_0", acc0), _acc(2, "agent_0", acc1)]
    stories = [
        _story("agent_0", 1, loco="WAIT", x=0, y=0),
        _story("agent_0", 2, loco="MOVE:N", x=0, y=0.5, selected="MOVE:N"),
    ]
    _wjsonl(tmp_path / "scientific_observations.jsonl", obs)
    out = analyze_beta31_vision(tmp_path, stories)
    att = out["beta31_vision"]["spatial_transitions"]["agent_0"]["attribution"]
    assert att.get("SELF_TRANSLATION", 0) + att.get("MIXED", 0) >= 1


def test_5_occlusion_disocclusion(tmp_path: Path):
    def spat(*vals):
        return {f"spatial_exo_a{i}": vals[i] for i in range(5)}
    obs = [
        _acc(1, "agent_0", spat(0.5, 0.4, 0.3, 0.2, 0.1)),
        _acc(2, "agent_0", spat(0.0, 0.0, 0.3, 0.2, 0.1)),
        _acc(3, "agent_0", spat(0.5, 0.4, 0.3, 0.2, 0.1)),
    ]
    stories = [_story("agent_0", t) for t in (1, 2, 3)]
    _wjsonl(tmp_path / "scientific_observations.jsonl", obs)
    out = analyze_beta31_vision(tmp_path, stories)
    seq = out["beta31_vision"]["occlusion_sequences"]
    assert seq["reconstruction"] == "PARTIAL"
    assert seq["counts"]["agent_0"] >= 1
    kinds = {e["kind"] for e in seq["episodes"]["agent_0"]}
    assert "OCCLUSION_TRANSITION" in kinds


def test_6_visual_distinction_survives_smc(tmp_path: Path):
    obs = [_acc(1, "agent_0", {"spatial_exo_a0": 0.4, "exo_0": 0.1})]
    decisions = [{
        "tick": 1,
        "cognitive_agent_id": "agent_0",
        "selected_action_legacy": "MOVE:N",
        "selection_path": "PSC",
        "candidate_count": 2,
        "sensorimotor_consequence": {
            "last_update": {"mean_delta": {"spatial_exo_a0": 0.1}},
            "predictions": [
                {"motor": "MOVE:N", "status": "MATCH", "predicted_delta": {"spatial_exo_a0": 0.2}},
                {"motor": "MOVE:N", "status": "MATCH", "predicted_delta": {"spatial_exo_a0": -0.3}},
            ],
        },
    }]
    out = _run(tmp_path, obs, decisions)
    smc = out["beta31_vision"]["smc_visual_differentiation"]
    assert smc["updates_with_spatial"] >= 1
    assert smc["same_motor_visual_differentiation_ticks"] >= 1
    assert out["publication"]["NATURALISTIC_SPATIAL_SMC_DIFFERENTIATION"] in ("YES", "PARTIAL")


def test_7_8_pe_not_invented(tmp_path: Path):
    obs = [_acc(1, "agent_0", {"exo_0": 0.5, "spatial_exo_a0": 0.2})]
    decisions = [{
        "tick": 1,
        "cognitive_agent_id": "agent_0",
        "sensorimotor_consequence": {
            "predictions": [{"motor": "WAIT", "status": "MATCH", "predicted_delta": {"exo_0": 0.0}}],
        },
        "predictive_equivalence": {"class_id": "invented"},  # must not be treated as V3 CORE PE internals
    }]
    out = _run(tmp_path, obs, decisions)
    pe = out["beta31_vision"]["pe_visual_survival"]
    assert pe["status"] == "PARTIAL"
    assert pe["RAW_VISUAL_STATE_COUNT"] == "NOT_RECORDED"
    assert pe["PE_VISUAL_MERGE_RATE"] == "NOT_RECORDED"
    assert out["publication"]["PE_VISUAL_FORENSICS"] == "PARTIAL"


def test_9_prospective_visual_diff(tmp_path: Path):
    obs = [_acc(1, "agent_0", {"spatial_exo_a0": 0.7})]
    decisions = [{
        "tick": 1,
        "cognitive_agent_id": "agent_0",
        "historical_sensorimotor_selection": {
            "candidates": [
                {"predicted_fields": ["spatial_exo_a0"], "history_support": 4},
                {"predicted_fields": ["exo_0"], "history_support": 1},
            ],
        },
    }]
    out = _run(tmp_path, obs, decisions)
    assert out["publication"]["PROSPECTIVE_VISUAL_DIFFERENTIATION"] == "YES"


def test_10_visual_difference_psc_structure(tmp_path: Path):
    nv = {"vest_0": 0.3, "vest_1": 0.0, "prop_neck_0": 0.0, "prop_neck_1": 0.0, "local.FIELD_A": 0.0, "local.FIELD_B": 0.0}
    obs = [
        _acc(1, "agent_0", {**nv, "spatial_exo_a0": 0.9, **{f"spatial_exo_a{k}": 0.0 for k in range(1, 5)}}),
        _acc(2, "agent_0", {**nv, "spatial_exo_a0": 0.0, "spatial_exo_a4": 0.9, **{f"spatial_exo_a{k}": 0.0 for k in range(1, 4)}}),
    ]
    stories = [
        _story("agent_0", 1, selected="WAIT", path="PSC", candidate_count=3, candidate_id="a"),
        _story("agent_0", 2, selected="MOVE:E", path="PSC", candidate_count=3, candidate_id="b"),
    ]
    _wjsonl(tmp_path / "scientific_observations.jsonl", obs)
    _wjsonl(tmp_path / "scientific_decisions.jsonl", [])
    out = analyze_beta31_vision(tmp_path, stories)
    pub = out["publication"]
    assert pub["NATURALISTIC_PSC_VISUAL_SENSITIVITY_MAX_LEVEL"] >= 4
    assert pub["NATURALISTIC_PSC_VISUAL_SENSITIVITY_CANDIDATE"] == "FOUND"
    text = out["beta31_vision_report_text"].lower()
    assert "not causal" in text


def test_11_matched_pair_negative_control(tmp_path: Path):
    nv = {"vest_0": 0.3, "local.FIELD_A": 0.0}
    spat = {f"spatial_exo_a{k}": 0.1 for k in range(5)}
    obs = [_acc(1, "agent_0", {**nv, **spat}), _acc(2, "agent_0", {**nv, **spat})]
    stories = [
        _story("agent_0", 1, selected="WAIT", path="PSC", candidate_id="a"),
        _story("agent_0", 2, selected="MOVE:N", path="PSC", candidate_id="b"),
    ]
    _wjsonl(tmp_path / "scientific_observations.jsonl", obs)
    out = analyze_beta31_vision(tmp_path, stories)
    pairs = out["beta31_vision"]["psc_visual_candidates"].get("observation_matched_pairs") or []
    assert pairs == []


def test_12_distance_reversal_positive(tmp_path: Path):
    obs = []
    stories = []
    dists = list(range(0, 12)) + list(range(11, -1, -1))
    for i, d in enumerate(dists, start=1):
        obs.append(_acc(i, "agent_0", {"exo_0": 0.1, "spatial_exo_a0": 0.2}))
        stories.append(_story("agent_0", i, loco="MOVE:E", x=float(i), selected="MOVE:E", dist=float(d)))
    _wjsonl(tmp_path / "scientific_observations.jsonl", obs)
    out = analyze_beta31_vision(tmp_path, stories)
    seqs = out["beta31_vision"]["distance_reversal_sequences"]["sequences"]
    assert len(seqs) >= 1
    assert seqs[0]["kind"] == "DISTANCE_REVERSAL_SEQUENCE"
    assert seqs[0]["DISTANCE_TREND_REVERSAL"] is True
    assert seqs[0].get("TERRAIN_ASSISTED_DISTANCE_REVERSAL_CANDIDATE") is True
    assert seqs[0].get("alias") == "slingshot"
    assert "not planning" in seqs[0]["note"].lower()


def test_13_distance_reversal_negative(tmp_path: Path):
    obs = []
    stories = []
    for i in range(1, 30):
        obs.append(_acc(i, "agent_0", {"exo_0": 0.1}))
        stories.append(_story("agent_0", i, dist=float(i) * 0.2))
    _wjsonl(tmp_path / "scientific_observations.jsonl", obs)
    out = analyze_beta31_vision(tmp_path, stories)
    assert out["beta31_vision"]["distance_reversal_sequences"]["sequences"] == []


def test_14_regime_boundary(tmp_path: Path):
    obs = [_acc(t, "agent_0", {"exo_0": 0.1}) for t in range(1, 8)]
    events = [{"type": "WORLD_INTERVENTION", "tick": 4, "changes": {"psc": "ON"}}]
    out = _run(tmp_path, obs, events=events)
    regimes = out["beta31_vision"]["vision_summary"]["regimes"]
    assert len(regimes) >= 2
    assert out["publication"]["REGIME_AWARE"] == "YES"


def test_15_signal_vision_stratification(tmp_path: Path):
    obs = [
        _acc(1, "agent_0", {"exo_0": 0.4, "local.FIELD_A": 0.0, "local.FIELD_B": 0.0}),
        _acc(2, "agent_0", {"exo_0": 0.4, "local.FIELD_A": 0.4, "local.FIELD_B": 0.0}),
        _acc(3, "agent_0", {"exo_0": 0.0, "local.FIELD_A": 0.5, "local.FIELD_B": 0.0}),
        _acc(4, "agent_0", {"exo_0": 0.0, "local.FIELD_A": 0.0}),
    ]
    out = _run(tmp_path, obs)
    joint = out["beta31_vision"]["signal_vision_context"]["agent_0"]["joint"]
    assert joint.get("VISUAL_ONLY", 0) >= 1
    assert joint.get("VISUAL_PLUS_SIGNAL", 0) >= 1
    assert joint.get("SIGNAL_ONLY", 0) >= 1
    assert joint.get("NEITHER", 0) >= 1
    assert out["publication"]["SIGNAL_VISION_CONFOUND_ANALYZED"] == "YES"


def test_16_legacy_without_beta31_channels(tmp_path: Path):
    obs = [_acc(1, "agent_0", {"exo_0": 0.2, "exo_1": 0.0, "exo_2": 0.1})]
    out = _run(tmp_path, obs)
    pub = out["publication"]
    assert pub["BETA31_VISUAL_CHANNELS_DETECTED"] == "YES"
    assert pub["SURFACE_CHANNELS_ANALYZED"] == "NO"
    assert pub["SPATIAL_CHANNELS_ANALYZED"] == "NO"
    assert pub["OPTICAL_OCCUPANCY_ANALYSIS"] == "PASS"


def test_does_not_invent_causal_claims(tmp_path: Path):
    obs = [_acc(1, "agent_0", {"spatial_exo_a0": 0.9, "exo_0": 0.2})]
    out = _run(tmp_path, obs)
    blob = (out["beta31_vision_report_text"] + json.dumps(out["publication"])).lower()
    for w in FORBIDDEN:
        assert w not in blob, w


def test_artifacts_compact(tmp_path: Path):
    obs = [_acc(1, "agent_0", {"exo_0": 0.2, "spatial_exo_a0": 0.1})]
    out = _run(tmp_path, obs)
    names = [
        "vision_summary.json", "optical_occupancy.json", "spatial_transitions.json",
        "occlusion_sequences.json", "head_motion_coupling.json",
        "smc_visual_differentiation.json", "pe_visual_survival.json",
        "prospective_visual_trace.json", "psc_visual_candidates.json",
        "spatial_motifs.json", "distance_reversal_sequences.json",
        "signal_vision_context.json",
    ]
    for n in names:
        assert (tmp_path / "vision_out" / n).is_file()
    assert "tick_stories" not in json.dumps(out["beta31_vision"]["vision_summary"])


def test_compact_http_keeps_vision_summary(tmp_path: Path):
    obs = [_acc(1, "agent_0", {"exo_0": 0.2})]
    vis = _run(tmp_path, obs)
    payload = {
        "status": "AVAILABLE",
        "tick_stories_count": 2,
        "complete_odmc_count": 2,
        "canonical_history": {"unique_simulation_ticks": 1},
        "analyzer_version": "1.2.0",
        "beta31_vision": vis["beta31_vision"],
        "beta31_vision_report_text": vis["beta31_vision_report_text"],
        "beta31_vision_publication": vis["publication"],
        "report_text": "BEHAVIORAL RECONSTRUCTION\n",
    }
    c = compact_http_result(payload)
    assert c["coverage"] == "FULL"
    assert c["beta31_vision_summary"]["analyzer_version"] == "1.2.0"
    assert "scientific_rows" in c and c["scientific_rows"] == []


def test_rss_synthetic_short(tmp_path: Path):
    obs = []
    stories = []
    for t in range(1, 80):
        for a in ("agent_0", "agent_1"):
            acc = {f"spatial_exo_a{k}": (0.01 * ((t + k) % 5)) for k in range(5)}
            acc["exo_0"] = 0.05
            obs.append(_acc(t, a, acc))
            stories.append(_story(a, t, loco="WAIT" if t % 3 else "MOVE:N", dist=float(t % 11)))
    _wjsonl(tmp_path / "scientific_observations.jsonl", obs)
    rss0 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    analyze_beta31_vision(tmp_path, stories, out_dir=tmp_path / "out")
    rss1 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # Linux ru_maxrss is KB
    peak_mb = rss1 / 1024.0 if rss1 > 10000 else rss1
    assert peak_mb < 2048


@pytest.mark.skipif(not ARCH_5K.is_dir(), reason="archived ~10k V3 run missing")
def test_rss_and_regression_archived_run():
    rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    payload = build_behavioral_reconstruction(ARCH_5K, max_tick=2500, write_artifacts=False)
    rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_kb = max(rss_before, rss_after)
    peak_mb = peak_kb / 1024.0
    assert payload["status"] == "AVAILABLE"
    assert payload["complete_odmc_count"] == payload["tick_stories_count"]
    assert payload["tick_stories_count"] >= 4000
    assert "BETA 3.1 VISION ANALYSIS" in payload["report_text"]
    assert payload.get("analyzer_version") == "1.2.0"
    assert payload.get("beta31_vision_publication", {}).get("OPTICAL_OCCUPANCY_ANALYSIS") == "PASS"
    assert payload.get("beta31_vision_publication", {}).get("PE_VISUAL_FORENSICS") == "PARTIAL"
    blob = payload["report_text"].lower()
    for w in FORBIDDEN:
        assert w not in blob
    assert peak_mb < 4096
    outp = ROOT / "results" / "analyzer_12_vision_rss.json"
    outp.write_text(
        json.dumps({
            "PEAK_ANALYZER_RSS_MB": round(peak_mb, 2),
            "ru_maxrss_kb": peak_kb,
            "max_tick": 2500,
            "tick_stories": payload["tick_stories_count"],
            "complete_odmc": payload["complete_odmc"],
            "publication": payload.get("beta31_vision_publication"),
        }, indent=2),
        encoding="utf-8",
    )


@pytest.mark.skipif(not LIVE.is_dir(), reason="original 5k live acceptance run missing")
def test_rss_original_live_acceptance():
    payload = build_behavioral_reconstruction(LIVE, max_tick=2334, write_artifacts=False)
    assert payload["complete_odmc_count"] == payload["tick_stories_count"]
    assert payload["tick_stories_count"] >= 4668
