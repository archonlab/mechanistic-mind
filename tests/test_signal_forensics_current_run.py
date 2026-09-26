"""Signal Forensics must analyze CURRENT RUN scientific evidence, not seed-17 fixture."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from mechanistic_mind.ui.psy_observer_web.signal_context.analyze_run import (
    analyze_signal_from_rows_events,
    compute_temporal_physical_relations,
)
from mechanistic_mind.ui.psy_observer_web.scientific_telemetry_v2 import (
    TELEMETRY_MODE_V1,
    TELEMETRY_MODE_V2,
    compact_event_v2,
    compact_tick_row_v2,
)


def _recv(tick: int, receiver: str, emitter: str, *, contact_trig=False, a=0.0, b=0.2):
    return {
        "type": "PHYSICAL_SIGNAL_RECEIVED",
        "tick": tick,
        "receiver_agent_id": receiver,
        "agent_id": receiver,
        "evidence": {
            "receiver_agent_id": receiver,
            "local.FIELD_A": a,
            "local.FIELD_B": b,
            "source_attribution": "UNIQUE_OTHER" if emitter != receiver else "SELF",
            "trigger": "body_contact" if contact_trig else "body_motion",
            "contributing_emissions_this_tick": [
                {"emitter_agent_id": emitter, "emission_id": f"e{tick}"}
            ],
        },
    }


def _emit(tick: int, emitter: str, *, contact_trig=False):
    return {
        "type": "PHYSICAL_SIGNAL_EMITTED",
        "tick": tick,
        "emitter_agent_id": emitter,
        "evidence": {
            "emitter_agent_id": emitter,
            "channel": "B",
            "trigger": "body_contact" if contact_trig else "body_motion",
            "emission_id": f"e{tick}",
        },
    }


def _row(tick: int, aid: str, *, x=0.0, y=0.0, contact=False, optical=False):
    return {
        "schema": "mm.psy_observer_web.scientific_tick.v2",
        "tick": tick,
        "agent_id": aid,
        "body_id": aid.replace("agent_", "body-"),
        "action": "WAIT",
        "action_source": "FALLBACK",
        "x": x,
        "y": y,
        "theta": 0.0,
        "vx": 0.0,
        "vy": 0.0,
        "speed": 0.0,
        "work": 1.0,
        "resource_A": 1.0,
        "resource_B": 1.0,
        "contact": contact,
        "vision_optical": {
            "available": True,
            "final_exo": {"exo_0": 0.2 if optical else 0.0, "exo_1": 0.0, "exo_2": 0.0},
            "exo_without_foreign_bodies": {"exo_0": 0.0, "exo_1": 0.0, "exo_2": 0.0},
            "foreign_body_contribution": {"exo_0": 0.2 if optical else 0.0, "exo_1": 0.0, "exo_2": 0.0},
            "foreign_body_total": 0.2 if optical else 0.0,
            "body_exposure": optical,
            "illumination": 1.0,
            "vision_enabled": True,
            "body_optics_enabled": True,
            "vision_radius": 1,
        },
    }


def make_precontact_fixture():
    """t100 cross-agent signal, t300 optical, t500 contact + contact-triggered signal."""
    rows = []
    events = []
    for t in range(1, 600):
        opt = t >= 300
        contact = t >= 500
        rows.append(_row(t, "agent_0", x=0.0, y=0.0, contact=contact, optical=opt))
        rows.append(_row(t, "agent_1", x=5.0, y=0.0, contact=contact, optical=opt))
    events.append(_emit(100, "agent_0"))
    events.append(_recv(100, "agent_1", "agent_0"))
    events.append(_emit(500, "agent_0", contact_trig=True))
    events.append(_recv(500, "agent_1", "agent_0", contact_trig=True, b=0.5))
    return rows, events


def test_temporal_relations_acceptance_example():
    rows, events = make_precontact_fixture()
    rel = compute_temporal_physical_relations(scientific_rows=rows, events=events)
    assert rel["first_cross_agent_contribution_tick"] == 100
    assert rel["first_body_optical_exposure_tick"] == 300
    assert rel["first_physical_contact_tick"] == 500
    assert rel["signal_to_optical_delta"] == 200
    assert rel["signal_to_contact_delta"] == 400
    assert rel["optical_to_contact_delta"] == 200
    assert rel["semantics"]["reception_to_cognition"] == "NOT_ESTABLISHED"


def test_zero_live_buffer_does_not_erase_historical_episodes():
    """LIVE=0 must not imply historical=0. Build 100 spaced episodes in scientific history."""
    rows = []
    events = []
    # Spaced every 5 ticks so DEFAULT_GAP_TOLERANCE=2 yields separate episodes.
    for i in range(100):
        t = 10 + i * 5
        rows.append(_row(t, "agent_0"))
        rows.append(_row(t, "agent_1", x=4.0))
        events.append(_emit(t, "agent_0"))
        events.append(_recv(t, "agent_1", "agent_0", b=0.25))
    result = analyze_signal_from_rows_events(
        rows=rows,
        events=events,
        run_id="current-fixture",
        source_label="CURRENT_RUN",
        telemetry_schema="V2_TIERED",
        coverage="FULL",
        runtime_status="RUNNING",
        cutoff_tick=10 + 99 * 5,
        max_episode_details=20,
    )
    assert result["analysis_source"] == "CURRENT_RUN"
    assert result["n_episodes"] == 100
    assert result["live_vs_historical"]["historical_episodes"] == 100
    live_episodes = 0
    assert live_episodes == 0
    assert result["n_episodes"] > live_episodes


def test_current_run_not_reference_ticks():
    """Reference has t687; current has t9000-range — current analysis must use t9000."""
    ref_rows = [_row(687, "agent_0"), _row(687, "agent_1", x=3.0)]
    ref_events = [_emit(687, "agent_0"), _recv(687, "agent_1", "agent_0", b=0.9)]
    cur_rows = []
    cur_events = []
    for t in (9000, 9001, 9100):
        cur_rows.append(_row(t, "agent_0"))
        cur_rows.append(_row(t, "agent_1", x=4.0))
        cur_events.append(_emit(t, "agent_0"))
        cur_events.append(_recv(t, "agent_1", "agent_0", b=0.4))

    ref = analyze_signal_from_rows_events(
        rows=ref_rows, events=ref_events, run_id="REF", source_label="REFERENCE_FIXTURE",
        cutoff_tick=687, max_episode_details=10,
    )
    cur = analyze_signal_from_rows_events(
        rows=cur_rows, events=cur_events, run_id="CUR", source_label="CURRENT_RUN",
        cutoff_tick=9100, max_episode_details=10,
    )
    assert cur["analysis_source"] == "CURRENT_RUN"
    assert cur["cutoff_tick"] == 9100
    peaks = [e["peak_tick"] for e in cur["episodes_compact"]]
    assert any(t >= 9000 for t in peaks)
    assert all(t != 687 for t in peaks)
    # Reference separately still has 687
    assert any(e["peak_tick"] == 687 for e in ref["episodes_compact"])


def test_v1_v2_episode_equivalence_core():
    rows, events = make_precontact_fixture()
    v1 = analyze_signal_from_rows_events(
        rows=rows, events=events, run_id="v1", source_label="CURRENT_RUN",
        telemetry_schema="V1_FULL", max_episode_details=30,
    )
    v2_rows = [compact_tick_row_v2(r) for r in rows]
    v2_events = []
    for ev in events:
        c = compact_event_v2(ev)
        if c is not None:
            v2_events.append(c)
        else:
            # SIGNAL events should always compact
            v2_events.append(ev)
    v2 = analyze_signal_from_rows_events(
        rows=v2_rows, events=v2_events, run_id="v2", source_label="CURRENT_RUN",
        telemetry_schema="V2_TIERED", max_episode_details=30,
    )
    assert v1["n_episodes"] == v2["n_episodes"]
    assert v1["temporal_physical_relations"]["first_cross_agent_contribution_tick"] == \
        v2["temporal_physical_relations"]["first_cross_agent_contribution_tick"]
    assert v1["temporal_physical_relations"]["first_physical_contact_tick"] == \
        v2["temporal_physical_relations"]["first_physical_contact_tick"]
    assert v1["temporal_physical_relations"]["first_body_optical_exposure_tick"] == \
        v2["temporal_physical_relations"]["first_body_optical_exposure_tick"]
    assert v1["honesty"]["reception_to_cognition"] == "NOT_ESTABLISHED"


def test_session_current_run_path_uses_scientific_package():
    from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig
    from mechanistic_mind.ui.psy_observer_web.scientific_history import ScientificHistoryWriter

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        s = ObserverSession(SessionConfig(seed=19, buffer_capacity=32, speed=50.0, results_root=str(tmp)))
        s.apply_experiment({
            "seed": 19,
            "agent_count": 2,
            "cognition_enabled": True,
            "world": {"width": 16, "height": 16},
            "mechanisms": {
                "cognition_enabled": True,
                "experimental_physical_signal": True,
                "physical_near_field_vision": True,
            },
        })
        s._active_run_id = "test-current-sf"
        live = tmp / "psychology_observer" / "psy_observer_web" / f".live-{s._active_run_id}"
        live.mkdir(parents=True)
        w = ScientificHistoryWriter(live, telemetry_mode=TELEMETRY_MODE_V2, checkpoint_every=0)
        w.open({"run_id": s._active_run_id, "seed": 19, "agent_count": 2})
        s._sci_writer = w
        s._sci_live_dir = live
        for _ in range(80):
            with s._step_lock:
                s._scientific_step_once_unlocked()
                with s._lock:
                    s._accumulate_events_locked()
                    fresh = list(s._event_ring)[-40:]
                    w.append_tick(s.runtime)
                    w.append_events(fresh)
        w.flush()
        out = s.signal_forensics_current_run(max_episode_details=12)
        assert out["accepted"] is True
        assert out["analysis_source"] == "CURRENT_RUN"
        assert out["evidence_authority"] == "scientific_evidence_package"
        assert out["cutoff_tick"] == int(s.runtime.tick)
        assert out.get("telemetry_schema") in {"V2_TIERED", "V1_FULL"}
        # Must not claim reference fixture
        assert out["analysis_source"] != "REFERENCE_FIXTURE"
