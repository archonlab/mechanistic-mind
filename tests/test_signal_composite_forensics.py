"""Signal Forensics V2 × Composite Motor Forensics — current-run integration tests."""
from __future__ import annotations

import json
from pathlib import Path

from mechanistic_mind.ui.psy_observer_web.signal_context.analyze_run import (
    analyze_signal_from_rows_events,
    analyze_signal_run,
)
from mechanistic_mind.ui.psy_observer_web.signal_context.composite_signal_forensics import (
    MOTOR_SCHEMA_COMPOSITE,
    MOTOR_SCHEMA_LEGACY,
    detect_motor_schema,
    reconstruct_osc_episodes,
    run_composite_signal_forensics,
)
from mechanistic_mind.ui.psy_observer_web.signal_context.intervention import (
    fingerprint_equal,
    scientific_fingerprint,
)
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = (
    _PROJECT_ROOT / "results" / "psychology_observer" / "psy_observer_web"
    / "psyweb-20260920T073337.352222Z-32f435bb"
)
OUT = _PROJECT_ROOT / "results" / "signal_composite_forensics"
if FIXTURE.is_dir():
    OUT.mkdir(parents=True, exist_ok=True)
REFERENCE_FIXTURE_ID = "psyweb-20260918T021911.211579Z-b3cd1135"


def _load_fixture(cutoff: int = 6643):
    if not FIXTURE.is_dir():
        import pytest
        pytest.skip(f"optional local fixture not packaged: {FIXTURE}")
    rows = []
    for ln in (FIXTURE / "scientific_timeline.jsonl").open():
        r = json.loads(ln)
        if int(r.get("tick", -1)) <= cutoff:
            rows.append(r)
    events = []
    for ln in (FIXTURE / "scientific_events.jsonl").open():
        ev = json.loads(ln)
        if int(ev.get("tick", -1)) <= cutoff:
            events.append(ev)
    meta = json.loads((FIXTURE / "scientific_meta.json").read_text())
    return rows, events, meta


def test_current_run_never_silent_fixture():
    rows, events, meta = _load_fixture()
    r = analyze_signal_from_rows_events(
        rows=rows,
        events=events,
        run_id=meta["run_id"],
        generation=meta.get("runtime_generation"),
        source_label="CURRENT_RUN",
        cutoff_tick=6643,
        meta=meta,
        seed=meta.get("seed"),
        telemetry_schema=meta.get("schema"),
    )
    assert r["analysis_source"] == "CURRENT_RUN"
    assert r["run_id"] == meta["run_id"]
    assert REFERENCE_FIXTURE_ID not in str(r["run_id"])
    assert r.get("fixture_mixed") is False
    assert r["honesty"]["reference_fixture_not_auto_loaded"] is True
    assert r["cutoff_tick"] == 6643


def test_run_id_and_cutoff_match():
    rows, events, meta = _load_fixture()
    rid = meta["run_id"]
    r = analyze_signal_from_rows_events(
        rows=rows, events=events, run_id=rid, cutoff_tick=6643,
        source_label="CURRENT_RUN", meta=meta, seed=meta.get("seed"),
    )
    assert r["run_id"] == rid
    assert r["source"]["run_id"] == rid
    assert r["cutoff_tick"] == 6643
    assert r["source"]["cutoff_tick"] == 6643


def test_composite_motor_v1_detected():
    rows, events, meta = _load_fixture()
    schema = detect_motor_schema(rows=rows, events=events, meta=meta)
    assert schema == MOTOR_SCHEMA_COMPOSITE
    pkg = run_composite_signal_forensics(
        rows=rows, events=events, meta=meta, run_id=meta["run_id"], cutoff_tick=6643,
    )
    assert pkg["source"]["motor_schema"] == MOTOR_SCHEMA_COMPOSITE
    assert pkg["composite_motor"]["authoritative"] is True


def test_osc_episodes_and_control_vs_active():
    rows, events, meta = _load_fixture()
    eps = reconstruct_osc_episodes(rows, cutoff=6643)
    assert len(eps) > 0
    pkg = run_composite_signal_forensics(
        rows=rows, events=events, meta=meta, cutoff_tick=6643, run_id=meta["run_id"],
    )
    a1 = pkg["composite_motor"]["agents"]["agent_1"]
    assert a1["control_vs_effector"]["OSC_EMIT_selections"] >= 1
    assert a1["control_vs_effector"]["emission_active_ticks"] > a1["control_vs_effector"]["OSC_EMIT_selections"]
    # one selection may produce N active ticks
    assert a1["control_vs_effector"]["emission_active_ticks"] > 1


def test_move_neck_osc_combinations():
    rows, events, meta = _load_fixture()
    pkg = run_composite_signal_forensics(
        rows=rows, events=events, meta=meta, cutoff_tick=6643, run_id=meta["run_id"],
    )
    named = pkg["composite_motor"]["named_combinations"]
    assert named.get("MOVE+NECK", 0) > 0
    # agent_1 uses OSC_EMIT as legacy token often — MOVE+OSC may appear via events
    assert (
        named.get("MOVE+OSC_EMIT", 0) > 0
        or named.get("MOVE+NECK+OSC", 0) > 0
        or pkg["composite_motor"]["agents"]["agent_1"]["emission_trigger_ticks"] > 0
    )
    assert named.get("MOVE+PUSH", 0) > 0 or pkg["composite_motor"]["agents"]["agent_1"]["push_ticks"] > 0
    assert pkg["composite_motor"]["cartesian_tokens"] is False


def test_full_duplex_and_no_semantics():
    rows, events, meta = _load_fixture()
    pkg = run_composite_signal_forensics(
        rows=rows, events=events, meta=meta, cutoff_tick=6643, run_id=meta["run_id"],
    )
    assert pkg["full_duplex"]["half_duplex_rule"] is False
    assert pkg["full_duplex"]["turn_taking_inferred"] is False
    assert pkg["full_duplex"]["speaker_listener_roles"] is False
    for p in pkg["spectrotemporal_patterns"]:
        assert p["pattern_id"].startswith("OSC_PATTERN_")
        assert "CALL" not in p["pattern_id"]
        assert "WORD" not in p["pattern_id"]
        assert "GREETING" not in p["pattern_id"]
    # Narrative fields must not invent semantic labels
    for a in pkg["candidate_associations"]:
        q = str(a.get("question") or "").lower()
        assert "speaker" not in q and "listener" not in q and "conversation" not in q
        assert a.get("causation") == "NOT_ESTABLISHED" or a.get("evidence_label") in {
            "TEMPORALLY_ASSOCIATED", "CANDIDATE_ASSOCIATION", "NOT_AVAILABLE", "OBSERVED", "DERIVED",
        }


def test_legacy_schema_preserved():
    rows = [
        {"tick": 1, "agent_id": "agent_0", "action": "WAIT", "action_source": "ENDOGENOUS_VARIATION"},
        {"tick": 2, "agent_id": "agent_0", "action": "MOVE:E", "action_source": "RETAINED_PREDICTION"},
    ]
    schema = detect_motor_schema(rows=rows, events=[], meta={})
    assert schema == MOTOR_SCHEMA_LEGACY
    pkg = run_composite_signal_forensics(rows=rows, events=[], cutoff_tick=2, run_id="legacy-test")
    assert pkg["composite_motor"]["authoritative"] is False
    assert pkg["composite_motor"]["schema"] == MOTOR_SCHEMA_LEGACY


def test_passive_perception_independent():
    rows, events, meta = _load_fixture()
    # Vision / vest / prop present while acting
    acting = [
        r for r in rows
        if str(r.get("action", "")).startswith("MOVE:")
        and (r.get("vision_optical") or r.get("vest_0") is not None or r.get("prop_neck_0") is not None)
    ]
    assert len(acting) > 0


def test_user_triggered_not_polling_flag():
    rows, events, meta = _load_fixture(cutoff=200)
    r = analyze_signal_from_rows_events(
        rows=rows, events=events, run_id=meta["run_id"], cutoff_tick=200,
        source_label="CURRENT_RUN", meta=meta,
    )
    assert r["user_triggered"] is True
    assert r["polling_on_refresh"] is False


def test_scientific_fingerprint_exact_match():
    """Observer forensics must not alter runtime dynamics fingerprint."""
    rt = TwoAgentRuntime(seed=99)
    fp0 = scientific_fingerprint(rt)
    # Import forensics modules (side-effect free)
    from mechanistic_mind.ui.psy_observer_web.signal_context import composite_signal_forensics as csf
    _ = csf.run_composite_signal_forensics(rows=[], events=[], run_id="x")
    rt2 = TwoAgentRuntime(seed=99)
    for _ in range(5):
        rt.step()
        rt2.step()
    assert fingerprint_equal(scientific_fingerprint(rt), scientific_fingerprint(rt2))
    # Fresh identical seeds still match baseline shape after no-op import
    assert fingerprint_equal(fp0, scientific_fingerprint(TwoAgentRuntime(seed=99)))


def test_fixture_integration_write_artifacts():
    rows, events, meta = _load_fixture()
    r = analyze_signal_from_rows_events(
        rows=rows,
        events=events,
        run_id=meta["run_id"],
        generation=meta.get("runtime_generation"),
        cutoff_tick=6643,
        source_label="CURRENT_RUN",
        meta=meta,
        seed=meta.get("seed"),
        telemetry_schema=str(meta.get("schema")),
        coverage="FULL",
    )
    (OUT / "acceptance.json").write_text(json.dumps({
        "marker": "SIGNAL_COMPOSITE_FORENSICS_ACCEPTED",
        "run_id": r["run_id"],
        "cutoff": r["cutoff_tick"],
        "motor_schema": r["motor_schema"],
        "n_osc_episodes": r["n_oscillatory_episodes"],
        "composite": {
            "MOVE+NECK": r["composite_motor"]["named_combinations"].get("MOVE+NECK"),
            "agent_1_emit_triggers": r["composite_motor"]["agents"]["agent_1"]["control_vs_effector"]["OSC_EMIT_selections"],
            "agent_1_emission_active": r["composite_motor"]["agents"]["agent_1"]["control_vs_effector"]["emission_active_ticks"],
        },
        "full_duplex": r["full_duplex"]["two_agent"],
        "fixture_mixed": r["fixture_mixed"],
    }, indent=2) + "\n")
    (OUT / "final_summary.md").write_text(
        "# SIGNAL COMPOSITE FORENSICS\n\n"
        "SIGNAL_COMPOSITE_FORENSICS_ACCEPTED\n\n"
        f"run_id={r['run_id']} cutoff={r['cutoff_tick']} motor={r['motor_schema']}\n"
    )
    assert r["motor_schema"] == MOTOR_SCHEMA_COMPOSITE
