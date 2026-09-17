"""Physical signal provenance: emitter ≠ observer; contact pair; continuum honesty."""
from __future__ import annotations

import hashlib

import numpy as np
import pytest

from mechanistic_mind.physical_system import PhysicalSystemConfig, TwoAgentRuntime
from mechanistic_mind.planet.config import PlanetConfig, default_planet_config
from mechanistic_mind.ui.psy_observer_web.serialize import collect_observer_events, enrich_structured_event


def _cfg_12() -> PhysicalSystemConfig:
    planet = default_planet_config()
    planet.width = 12
    planet.height = 12
    return PhysicalSystemConfig(planet=planet)


def _ta143(**kw) -> TwoAgentRuntime:
    kw.setdefault("seed", 143)
    kw.setdefault("config", _cfg_12())
    # Overlapping-ish starts on 12x12 encourage contact over long runs
    kw.setdefault("starts", ((3, 3), (4, 3)))
    kw.setdefault("signal_enabled", True)
    kw.setdefault("contact_enabled", True)
    return TwoAgentRuntime(**kw)


def _events(ta: TwoAgentRuntime, limit: int = 500) -> list[dict]:
    return collect_observer_events(ta, limit=limit)


def test_body_contact_emission_preserves_physical_emitter_and_contact_pair():
    ta = _ta143(starts=((5, 5), (5, 5)))  # force contact
    ta.step(3)
    emits = []
    for slot in ta.slots:
        for ev in slot.structured_events.list(limit=100):
            if ev.get("type") == "PHYSICAL_SIGNAL_EMITTED":
                emits.append(ev)
    contact_emits = [e for e in emits if (e.get("evidence") or {}).get("trigger") == "body_contact"]
    assert contact_emits, "expected body_contact emissions when bodies overlap"
    for e in contact_emits:
        ev = e["evidence"]
        assert ev.get("emitter_agent_id") in {"agent_0", "agent_1"}
        assert ev.get("emitter_body_id") in {"body-0", "body-1"}
        assert ev.get("emitter_agent_id") != "UNKNOWN"
        assert ev.get("emitter_body_id") != "UNKNOWN"
        assert ev.get("observer_source_id") in {"agent_0", "agent_1"}
        # Physical emitter may equal observer stream for that body's deposit — but must be set from slot, not guessed.
        assert ev.get("slot") is not None
        assert ev.get("emitter_agent_id") == f"agent_{int(ev['slot'])}"
        assert ev.get("origin_kind") == "BODY_BODY_CONTACT"
        assert ev.get("contact_entity_a_id") == "body-0"
        assert ev.get("contact_entity_b_id") == "body-1"
        assert ev.get("emission_id")
        assert ev.get("channel") == "B"


def test_enrich_never_promotes_observer_to_emitter():
    raw = {
        "type": "PHYSICAL_SIGNAL_EMITTED",
        "tick": 9,
        "evidence": {
            "channel": "B",
            "trigger": "body_contact",
            "observer_source_id": "agent_1",
            # Intentionally missing emitter — must stay UNKNOWN, not become agent_1
        },
    }
    row = enrich_structured_event(dict(raw), agent_id="agent_1", body_id="body-1")
    assert row["observer_source_id"] == "agent_1"
    assert row["emitter_agent_id"] == "UNKNOWN"
    assert row["evidence"]["emitter_agent_id"] == "UNKNOWN"
    assert row["evidence"].get("source_agent_id") != "agent_1" or row["emitter_agent_id"] == "UNKNOWN"


def test_received_records_contributing_emissions_without_unique_source_claim():
    ta = _ta143(starts=((5, 5), (5, 5)))
    ta.step(2)
    recvs = []
    for slot in ta.slots:
        for ev in slot.structured_events.list(limit=100):
            if ev.get("type") == "PHYSICAL_SIGNAL_RECEIVED":
                recvs.append(ev)
    assert recvs
    for e in recvs:
        ev = e["evidence"]
        assert ev.get("receiver_agent_id") in {"agent_0", "agent_1"}
        assert ev.get("receiver_body_id") in {"body-0", "body-1"}
        assert ev.get("source_agent_id") == "UNKNOWN"
        assert ev.get("source_attribution") in {"NOT_UNIQUELY_ATTRIBUTABLE", "MIXED"}
        assert isinstance(ev.get("contributing_emissions_this_tick"), list)
        assert isinstance(ev.get("causal_parent_ids"), list)


def test_seed_143_forensics_batch():
    ta = _ta143()
    emits, recvs = [], []
    # Run long enough to accumulate contact/motion signal events
    for _ in range(800):
        ta.step(1)
        for i, slot in enumerate(ta.slots):
            for ev in slot.structured_events.list(limit=40):
                et = ev.get("type")
                if et == "PHYSICAL_SIGNAL_EMITTED":
                    emits.append((i, ev))
                elif et == "PHYSICAL_SIGNAL_RECEIVED":
                    recvs.append((i, ev))
        if len(emits) >= 10 and len(recvs) >= 10:
            break
    assert len(emits) >= 10, f"only {len(emits)} emissions"
    assert len(recvs) >= 10, f"only {len(recvs)} receptions"

    for buf_i, e in emits[-10:]:
        ev = e["evidence"]
        # observer stream is buffer owner when recorded into that slot
        assert ev.get("observer_source_id") in {"agent_0", "agent_1"}
        if ev.get("trigger") in {"body_contact", "body_motion"}:
            assert ev.get("emitter_agent_id") == f"agent_{int(ev['slot'])}"
            assert ev.get("emitter_body_id") == f"body-{int(ev['slot'])}"
            assert ev.get("emitter_agent_id") != "UNKNOWN"
        if ev.get("trigger") == "body_contact":
            assert {ev.get("contact_entity_a_id"), ev.get("contact_entity_b_id")} == {"body-0", "body-1"}

    for buf_i, e in recvs[-10:]:
        ev = e["evidence"]
        assert ev.get("receiver_body_id") == f"body-{buf_i}"
        assert ev.get("source_agent_id") == "UNKNOWN"
        # Must not treat observer as emitter/source
        assert ev.get("source_agent_id") != ev.get("observer_source_id") or ev.get("source_agent_id") == "UNKNOWN"


def test_cross_agent_signal_transfer_report():
    """Search for agent_i emission contributing to agent_j reception same tick. Report only."""
    ta = _ta143()
    traces = []
    for _ in range(600):
        ta.step(1)
        tick = int(ta.tick)
        emits = []
        recvs = []
        for i, slot in enumerate(ta.slots):
            for ev in slot.structured_events.list(limit=30):
                if int(ev.get("tick") or -1) != tick:
                    continue
                if ev.get("type") == "PHYSICAL_SIGNAL_EMITTED":
                    emits.append((i, ev))
                elif ev.get("type") == "PHYSICAL_SIGNAL_RECEIVED":
                    recvs.append((i, ev))
        for ri, recv in recvs:
            parents = set((recv.get("evidence") or {}).get("causal_parent_ids") or [])
            for ei, emit in emits:
                eid = (emit.get("evidence") or {}).get("emission_id")
                if not eid or eid not in parents:
                    continue
                if ei == ri:
                    continue
                # Cross-agent: emission recorded on agent_ei buffer, reception on agent_ri
                traces.append({
                    "tick": tick,
                    "emission_id": eid,
                    "emitter": (emit.get("evidence") or {}).get("emitter_agent_id"),
                    "emitter_body": (emit.get("evidence") or {}).get("emitter_body_id"),
                    "origin_kind": (emit.get("evidence") or {}).get("origin_kind"),
                    "origin_id": (emit.get("evidence") or {}).get("origin_id"),
                    "channel": (emit.get("evidence") or {}).get("channel"),
                    "receiver": (recv.get("evidence") or {}).get("receiver_agent_id"),
                    "receiver_body": (recv.get("evidence") or {}).get("receiver_body_id"),
                    "source_attribution": (recv.get("evidence") or {}).get("source_attribution"),
                })
        if traces:
            break
    # Honest report: observed or not — do not fabricate
    if not traces:
        pytest.skip("CROSS_AGENT_SIGNAL_TRANSFER: NOT_OBSERVED")
    t0 = traces[0]
    assert t0["emitter"] != t0["receiver"]
    assert t0["emission_id"]
    assert t0["source_attribution"] in {"NOT_UNIQUELY_ATTRIBUTABLE", "MIXED"}


def test_determinism_fields_and_actions_unchanged_by_provenance():
    """Same seed → identical fields and action sequences (provenance is observational)."""

    def run_once():
        ta = _ta143(starts=((3, 3), (6, 3)))
        actions = []
        for _ in range(40):
            ta.step(1)
            actions.append((ta.slots[0].last_selected_action, ta.slots[1].last_selected_action))
        fa = np.asarray(ta.world.FIELD_A)
        fb = np.asarray(ta.world.FIELD_B)
        return actions, fa.copy(), fb.copy(), float(fa.sum()), float(fb.sum())

    a1, fa1, fb1, sa1, sb1 = run_once()
    a2, fa2, fb2, sa2, sb2 = run_once()
    assert a1 == a2
    assert sa1 == sa2 and sb1 == sb2
    assert np.allclose(fa1, fa2) and np.allclose(fb1, fb2)
    h1 = hashlib.sha256(fa1.tobytes() + fb1.tobytes()).hexdigest()
    h2 = hashlib.sha256(fa2.tobytes() + fb2.tobytes()).hexdigest()
    assert h1 == h2


def test_observer_events_distinguish_emitter_and_observer():
    ta = _ta143(starts=((5, 5), (5, 5)))
    ta.step(2)
    events = _events(ta, limit=200)
    emitted = [e for e in events if e.get("type") == "PHYSICAL_SIGNAL_EMITTED"]
    assert emitted
    for e in emitted:
        ev = e["evidence"]
        assert e.get("emitter_agent_id") == ev.get("emitter_agent_id")
        assert e.get("observer_source_id")
        # Compact identity: body known for body_contact/motion
        if ev.get("trigger") == "body_contact":
            assert e.get("emitter_body_id") in {"body-0", "body-1"}
            assert e.get("body_id") in {"body-0", "body-1"}
            assert e.get("body_id") != "UNKNOWN"
