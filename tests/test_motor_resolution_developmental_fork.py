"""Fork identity + developmental fork scaffolding tests."""
from __future__ import annotations

import copy
import hashlib
import json

from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig
from mechanistic_mind.physical_system import observed_composite_psc as oc


def _snapshot_hash(payload: dict) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:24]


def _prep_session(seed: int, ticks: int, psc_on_after: int | None = None):
    s = ObserverSession(SessionConfig(seed=seed, evidence_mode="SEARCH_COMPACT"))
    s.apply_experiment({"seed": seed, "agent_count": 2})
    s.set_observer_detail_preset("MINIMAL")
    for mech in (
        "sensorimotor_consequence_model",
        "sensorimotor_consequence_bilateral",
        "historical_sensorimotor_selection_bridge",
        "prospective_composition",
        "composite_motor",
        "retrieval",
    ):
        try:
            s.set_mechanism(mech, True)
        except Exception:
            pass
    s.set_mechanism("prospective_scenario_competition", False)
    s.set_psc_motor_resolution("LOCO_FACTORIZED")
    for i in range(ticks):
        if psc_on_after is not None and i == psc_on_after:
            s.set_mechanism("prospective_scenario_competition", True)
        s.step()
    return s


def test_fork_identity_exact_match():
    s = _prep_session(17, 40)
    snap = s.runtime.snapshot()
    h = _snapshot_hash(snap)
    a = TwoAgentRuntime.restore(copy.deepcopy(snap))
    b = TwoAgentRuntime.restore(copy.deepcopy(snap))
    # identical LOCO mode continuation
    for rt in (a, b):
        for slot in rt.slots:
            slot.set_psc_motor_resolution("LOCO_FACTORIZED")
            try:
                slot.set_mechanism("prospective_scenario_competition", True)
            except Exception:
                pass
    motors_a, motors_b = [], []
    for _ in range(15):
        a.step()
        b.step()
        motors_a.append(json.dumps(a.slots[0].cognition.get("last_motor_output"), sort_keys=True, default=str))
        motors_b.append(json.dumps(b.slots[0].cognition.get("last_motor_output"), sort_keys=True, default=str))
    assert motors_a == motors_b
    assert _snapshot_hash(snap) == h  # parent snapshot unchanged


def test_fork_snapshot_hash_stable():
    s = _prep_session(111, 30)
    snap = s.runtime.snapshot()
    assert _snapshot_hash(snap) == _snapshot_hash(copy.deepcopy(snap))


def test_differing_modes_allowed_after_fork():
    s = _prep_session(733, 50)
    snap = s.runtime.snapshot()
    loco = TwoAgentRuntime.restore(copy.deepcopy(snap))
    obs = TwoAgentRuntime.restore(copy.deepcopy(snap))
    for slot in loco.slots:
        slot.set_psc_motor_resolution("LOCO_FACTORIZED")
        try:
            slot.set_mechanism("prospective_scenario_competition", True)
        except Exception:
            pass
    for slot in obs.slots:
        slot.set_psc_motor_resolution("OBSERVED_COMPOSITE")
        try:
            slot.set_mechanism("prospective_scenario_competition", True)
        except Exception:
            pass
    # Pre-step: configs differ only by mode
    assert oc.normalize_mode(loco.slots[0].config.cognition.psc_motor_resolution) == "LOCO_FACTORIZED"
    assert oc.normalize_mode(obs.slots[0].config.cognition.psc_motor_resolution) == "OBSERVED_COMPOSITE"
    # Run a few steps — divergence is allowed; identity of shared parent holds
    for _ in range(10):
        loco.step()
        obs.step()
    assert loco.tick == obs.tick
