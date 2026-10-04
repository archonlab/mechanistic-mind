"""SAV4A — saved evidence normalization + deterministic schedule (0 simulation ticks)."""
from __future__ import annotations

import json
from pathlib import Path

from mechanistic_mind.physical_system.observation import FORBIDDEN_TOKENS, audit_cognition_payload
from mechanistic_mind.physical_system.selected_organism_auditory_offline_reconstruction_sav4a import (
    AUTH_LEGACY,
    AUTH_OATT,
    AUTH_SAV1,
    AUTHORITY,
    CAPABILITY,
    PHASES,
    PROFILE,
    SCHEMA,
    discover_evidence_files,
    reconstruct_from_candidate_lists,
    reconstruct_from_run_dir,
)
from mechanistic_mind.physical_system.selected_organism_auditory_sonification import (
    FIXED_RECEPTOR_GAIN,
    map_receptor_activation,
)

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "acanthostega_selected_organism_auditory_offline_reconstruction_sav4a_v1"
FIXTURES = ROOT / "tests" / "fixtures" / "sav4a"
RESULTS.mkdir(parents=True, exist_ok=True)
FIXTURES.mkdir(parents=True, exist_ok=True)

TICKS = 0


def _a5(v: float) -> list[float]:
    return [float(v)] + [0.0] * 5


def _oatt(tick: int, left: float, *, agent="a0", body="b0", gen="1", run="r1", profile=None):
    return {
        "schema": "ORGANISM_AUDITORY_TRANSFORMATION_TRACE_V1",
        "profile": profile or "AUDITORY_A3_TO_A5_TRANSFORMATION_TRACE_V1",
        "trace_id": f"tr-{gen}-{tick}",
        "observation_tick": tick,
        "agent_id": agent,
        "body_id": body,
        "run_id": run,
        "runtime_generation": gen,
        "a5_left": _a5(left),
        "a5_right": _a5(left * 0.5),
        "a3_left": _a5(left * 10),
        "a3_right": _a5(left * 5),
        "a4_sensor_scale": 10.0,
    }


def _sav1(tick: int, left: float, *, agent="a0", body="b0", gen="1", run="r1", profile=None):
    return {
        "schema": "SELECTED_ORGANISM_AUDITORY_BOUNDARY_RECEIPT_V1",
        "profile": profile or "ORGANISM_AUDITORY_BOUNDARY_A5_V1",
        "receipt_id": f"rc-{gen}-{tick}",
        "scientific_tick": tick,
        "agent_id": agent,
        "body_id": body,
        "run_id": run,
        "runtime_generation": gen,
        "availability": "AVAILABLE",
        "section_a_organism_accessible": {
            "left_receptor_channels": _a5(left),
            "right_receptor_channels": _a5(left * 0.5),
        },
    }


def _legacy(tick: int, left: float, *, agent="a0", body="b0", gen="1", run="r1", drop_channel=False, zeros=False):
    acc = {}
    for i in range(6):
        v = 0.0 if zeros else (left if i == 0 else 0.0)
        acc[f"osc_l_{i}"] = v
        if not (drop_channel and i == 5):
            acc[f"osc_r_{i}"] = 0.0 if zeros else (left * 0.5 if i == 0 else 0.0)
    return {
        "schema": "mm.scientific_v3.observation.core.v1",
        "observation_id": f"obs-{gen}-{tick}",
        "tick": tick,
        "run_id": run,
        "runtime_generation": gen,
        "cognitive_agent_id": agent,
        "physical_body_id": body,
        "accessible": acc,
    }


def test_01_identity_and_privacy():
    assert SCHEMA == "SELECTED_ORGANISM_AUDITORY_OFFLINE_RECONSTRUCTION_SAV4A_V1"
    assert CAPABILITY == "selected_organism_auditory_offline_reconstruction"
    assert PROFILE == "SAVED_EVIDENCE_NORMALIZATION_AND_DETERMINISTIC_SCHEDULE_SAV4A_V1"
    assert AUTHORITY == "RESEARCHER_DERIVED_READ_ONLY_OVER_SAVED_AUTHORITATIVE_EVIDENCE"
    assert SCHEMA in FORBIDDEN_TOKENS
    assert CAPABILITY in FORBIDDEN_TOKENS
    assert AUTHORITY in FORBIDDEN_TOKENS
    assert audit_cognition_payload({"osc_l_0": 0.1, "osc_r_0": 0.2}) == []
    leaks = audit_cognition_payload(
        {
            "schema": SCHEMA,
            "normalized_record_digest": "abc",
            "schedule_digest": "def",
            "identity_segments": [],
        }
    )
    assert leaks


def test_02_oatt_preferred_over_sav1_and_legacy():
    out = reconstruct_from_candidate_lists(
        oatt_traces=[_oatt(3, 0.8)],
        sav1_receipts=[_sav1(3, 0.1)],
        legacy_observations=[_legacy(3, 0.2)],
    )
    recs = out.get("normalized_records") or out["normalized_records_preview"]
    assert len(recs) == 1
    assert recs[0]["source_authority_class"] == AUTH_OATT
    assert recs[0]["a5_left"][0] == 0.8
    assert out["superseded_total"] >= 2


def test_03_sav1_preferred_when_oatt_absent():
    out = reconstruct_from_candidate_lists(
        oatt_traces=[],
        sav1_receipts=[_sav1(1, 0.4)],
        legacy_observations=[_legacy(1, 0.9)],
    )
    recs = out.get("normalized_records") or out["normalized_records_preview"]
    assert recs[0]["source_authority_class"] == AUTH_SAV1
    assert recs[0]["a5_left"][0] == 0.4


def test_04_legacy_complete_twelve_channel():
    out = reconstruct_from_candidate_lists(legacy_observations=[_legacy(0, 0.3)])
    recs = out.get("normalized_records") or out["normalized_records_preview"]
    assert recs[0]["source_authority_class"] == AUTH_LEGACY
    assert recs[0]["legacy_label"] is True
    assert recs[0]["never_upgraded_to_oatt_or_sav1"] is True
    assert out["schedule_available"] is True


def test_05_missing_legacy_channel_is_gap_not_zero():
    out = reconstruct_from_candidate_lists(
        legacy_observations=[_legacy(0, 0.3, drop_channel=True)]
    )
    recs = out.get("normalized_records") or out["normalized_records_preview"]
    assert recs[0]["source_authority_class"] == "UNAVAILABLE"
    assert recs[0]["a5_left"] is None
    assert recs[0]["true_zero"] is False


def test_06_exact_all_zero_is_true_silence():
    out = reconstruct_from_candidate_lists(legacy_observations=[_legacy(2, 0.0, zeros=True)])
    recs = out.get("normalized_records") or out["normalized_records_preview"]
    assert recs[0]["true_zero"] is True
    assert all(v == 0.0 for v in recs[0]["a5_left"] + recs[0]["a5_right"])
    items = out.get("schedule_items") or out["schedule_items_preview"]
    assert items and all(a == 0.0 for a in items[0]["left_amplitudes"])


def test_07_forbidden_authorities_never_used():
    fake = {
        "tick": 1,
        "cognitive_agent_id": "a0",
        "physical_body_id": "b0",
        "accessible": {"stream_energy": 9.9, "probe_sample": 1.0},
        "cognition": {"thought": 1},
    }
    out = reconstruct_from_candidate_lists(legacy_observations=[fake])
    assert out["normalized_record_count"] == 0
    assert out["stream_used_as_a5_authority"] is False
    assert out["probe_used_as_a5_authority"] is False
    assert out["cognition_used_as_a5_authority"] is False
    assert out["pixels_used_as_a5_authority"] is False


def test_08_runtime_generations_separated():
    out = reconstruct_from_candidate_lists(
        oatt_traces=[_oatt(1, 0.2, gen="1"), _oatt(1, 0.9, gen="2")],
    )
    segs = out["identity_segments"]
    gens = {s["runtime_generation"] for s in segs}
    assert gens == {"1", "2"}
    assert len(segs) == 2


def test_09_agent_body_lifetimes_separated():
    out = reconstruct_from_candidate_lists(
        sav1_receipts=[
            _sav1(1, 0.1, agent="a0", body="b0"),
            _sav1(1, 0.2, agent="a1", body="b1"),
        ],
    )
    assert len(out["identity_segments"]) == 2


def test_10_canonical_ordering_invariant_to_input_order():
    a = reconstruct_from_candidate_lists(
        oatt_traces=[_oatt(2, 0.2), _oatt(1, 0.1), _oatt(3, 0.3)],
    )
    b = reconstruct_from_candidate_lists(
        oatt_traces=[_oatt(3, 0.3), _oatt(1, 0.1), _oatt(2, 0.2)],
    )
    assert a["normalized_record_digest"] == b["normalized_record_digest"]
    assert a["schedule_digest"] == b["schedule_digest"]


def test_11_exact_duplicates_keep_first():
    out = reconstruct_from_candidate_lists(
        sav1_receipts=[_sav1(5, 0.5), _sav1(5, 0.5)],
    )
    assert out["normalized_record_count"] == 1
    assert out["duplicate_count"] >= 1


def test_12_conflicting_duplicates_never_averaged():
    r1 = _sav1(7, 0.1)
    r2 = _sav1(7, 0.9)
    r2["receipt_id"] = "other"
    out = reconstruct_from_candidate_lists(sav1_receipts=[r1, r2])
    recs = out.get("normalized_records") or out["normalized_records_preview"]
    assert recs[0]["a5_left"][0] == 0.1
    assert recs[0]["conflict_status"] == "CONFLICT_VISIBLE_NO_AVERAGE"
    assert out["conflict_count"] >= 1
    assert recs[0]["a5_left"][0] != 0.5


def test_13_tick_gaps_segment_schedule_no_zero_fill():
    out = reconstruct_from_candidate_lists(
        oatt_traces=[_oatt(1, 0.2), _oatt(2, 0.3), _oatt(5, 0.4)],
    )
    assert out["gap_count"] >= 2
    assert len(out["identity_segments"]) >= 2
    items = out.get("schedule_items") or out["schedule_items_preview"]
    ticks = [i["observation_tick"] for i in items]
    assert 3 not in ticks and 4 not in ticks


def test_14_empty_event_refs_do_not_erase_observation_evidence():
    pkg = FIXTURES / "empty_refs_with_legacy"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "scientific_meta.json").write_text(
        json.dumps({"run_id": "empty-refs", "runtime_generation": 1}), encoding="utf-8"
    )
    with (pkg / "scientific_consequences.jsonl").open("w", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "consequence_id": "c0",
                    "run_id": "empty-refs",
                    "tick_from": 0,
                    "tick_to": 0,
                    "cognitive_agent_id": "a0",
                    "physical_body_id": "b0",
                    "event_refs": [],
                }
            )
            + "\n"
        )
    with (pkg / "scientific_observations.jsonl").open("w", encoding="utf-8") as fh:
        fh.write(json.dumps(_legacy(0, 0.25, run="empty-refs")) + "\n")
    out = reconstruct_from_run_dir(pkg)
    assert out["empty_event_refs_rows"] >= 1
    assert out["empty_event_refs_means"].startswith("NO_REFERENCES")
    assert out["normalized_record_count"] >= 1
    recs = out.get("normalized_records") or out["normalized_records_preview"]
    assert recs[0]["source_authority_class"] == AUTH_LEGACY


def test_15_scientific_consequences_alias_accepted():
    pkg = FIXTURES / "sci_cons_alias"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "scientific_meta.json").write_text(
        json.dumps({"run_id": "alias", "runtime_generation": 0}), encoding="utf-8"
    )
    row = {
        "consequence_id": "c1",
        "run_id": "alias",
        "tick_from": 1,
        "tick_to": 1,
        "cognitive_agent_id": "a0",
        "physical_body_id": "b0",
        "event_refs": [
            {
                "kind": "ORGANISM_AUDITORY_BOUNDARY_RECEIPT",
                **{k: v for k, v in _sav1(1, 0.55, run="alias", gen="0").items()},
            }
        ],
    }
    (pkg / "scientific_consequences.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    inv = discover_evidence_files(pkg)
    names = {a["filename"] for a in inv["accepted"]}
    assert "scientific_consequences.jsonl" in names
    out = reconstruct_from_run_dir(pkg)
    assert out["normalized_record_count"] >= 1


def test_16_compatible_profile_produces_schedule():
    out = reconstruct_from_candidate_lists(sav1_receipts=[_sav1(0, 0.7)])
    assert out["schedule_available"] is True
    assert out["schedule_item_count"] == 1


def test_17_incompatible_profile_blocks_schedule_keeps_evidence():
    out = reconstruct_from_candidate_lists(
        sav1_receipts=[_sav1(0, 0.7, profile="ANCIENT_UNKNOWN_PROFILE_V0")],
    )
    assert out["normalized_record_count"] == 1
    assert out["schedule_available"] is False
    segs = out["identity_segments"]
    assert segs[0]["completeness"] == "PROFILE_UNKNOWN_OR_INCOMPATIBLE"


def test_18_schedule_matches_sav2_mapping_numerically():
    left, right = _a5(0.5), _a5(0.25)
    out = reconstruct_from_candidate_lists(
        sav1_receipts=[
            {
                **_sav1(0, 0.5),
                "section_a_organism_accessible": {
                    "left_receptor_channels": left,
                    "right_receptor_channels": right,
                },
            }
        ]
    )
    mapped = map_receptor_activation(left, right)
    item = (out.get("schedule_items") or out["schedule_items_preview"])[0]
    assert item["left_amplitudes"] == mapped["left_amplitudes"]
    assert item["right_amplitudes"] == mapped["right_amplitudes"]
    assert item["fixed_receptor_gain"] == FIXED_RECEPTOR_GAIN
    assert item["canonical_seconds_per_tick"] == 0.05
    assert item["canonical_seconds_per_tick_is_physical"] is False


def test_19_determinism_digests():
    kwargs = dict(
        oatt_traces=[_oatt(1, 0.2), _oatt(2, 0.3)],
        sav1_receipts=[_sav1(3, 0.4)],
        legacy_observations=[_legacy(4, 0.1)],
    )
    a = reconstruct_from_candidate_lists(**kwargs)
    b = reconstruct_from_candidate_lists(**kwargs)
    assert a["normalized_record_digest"] == b["normalized_record_digest"]
    assert a["schedule_digest"] == b["schedule_digest"]
    dig = {
        "normalized_record_digest": a["normalized_record_digest"],
        "schedule_digest": a["schedule_digest"],
        "schema": SCHEMA,
        "profile": PROFILE,
    }
    (RESULTS / "determinism_digests.json").write_text(json.dumps(dig, indent=2), encoding="utf-8")
    (FIXTURES / "determinism_digests.json").write_text(json.dumps(dig, indent=2), encoding="utf-8")


def test_20_no_audio_flags():
    out = reconstruct_from_candidate_lists(sav1_receipts=[_sav1(0, 0.1)])
    assert out["audio_playback_implemented"] is False
    assert out["pcm_rendering_implemented"] is False
    assert out["wav_export_implemented"] is False
    assert out["offline_playback_owner_created"] is False
    assert out["bit_identical_pcm_claimed"] is False
    assert out["profile_compatibility"]["current_profile_silently_applied_to_legacy"] is False


def test_21_progress_phases_genuine():
    events = []
    reconstruct_from_candidate_lists(
        oatt_traces=[_oatt(1, 0.1)],
        progress=lambda e: events.append(e),
    )
    names = [e["phase"] for e in events]
    for ph in PHASES:
        assert ph in names
    for e in events:
        if e.get("total") is None:
            assert e.get("percent") is None


def test_22_mixed_authority_and_tick_budget():
    out = reconstruct_from_candidate_lists(
        oatt_traces=[_oatt(1, 0.8)],
        sav1_receipts=[_sav1(2, 0.4)],
        legacy_observations=[_legacy(3, 0.2)],
    )
    assert out["authority_matrix"][AUTH_OATT] >= 1
    assert out["authority_matrix"][AUTH_SAV1] >= 1
    assert out["authority_matrix"][AUTH_LEGACY] >= 1
    assert TICKS == 0
