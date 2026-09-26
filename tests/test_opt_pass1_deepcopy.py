"""OPT PASS 1: causal_trace trim semantics + copy isolation."""
from __future__ import annotations

from copy import deepcopy

from mechanistic_mind.integrated.causal_trace import edge, empty_trace, event, _trim
from mechanistic_mind.integrated.copy_opt import capture_flat_mapping, jsonish_copy
from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system import PhysicalSystemRuntime, TwoAgentRuntime
from mechanistic_mind.physical_system.ecology_presets import ECOLOGY_STRUCTURED_TERRAIN, make_ecology_config


def test_trim_noop_under_capacity():
    tr = empty_trace(64)
    e1 = event(tr, tick=1, kind="A", mechanism="m", payload={"x": 1})
    edges_before = tr["edges"]
    _trim(tr)  # explicit
    assert tr["edges"] is edges_before  # no rebuild when under caps
    assert len(tr["events"]) == 1
    assert tr["events"][0]["id"] == e1


def test_trim_retention_matches_capacity():
    cap = 32
    tr = empty_trace(cap)
    ids = []
    for i in range(80):
        ids.append(event(tr, tick=i, kind="X", mechanism="m", payload={"i": i}))
        if i > 0:
            edge(
                tr,
                source=ids[i - 1],
                target=ids[i],
                tick=i,
                mechanism="m",
                provenance={"i": i},
            )
    assert len(tr["events"]) == cap
    # Newest survivors
    assert tr["events"][0]["payload"]["i"] == 80 - cap
    assert tr["events"][-1]["payload"]["i"] == 79
    # Edges must not reference removed events
    live = {e["id"] for e in tr["events"]}
    for row in tr["edges"]:
        assert row["source"] in live
        assert row["target"] in live
    assert len(tr["edges"]) <= cap * 3


def test_payload_capture_isolates_flat_dict():
    src = {"a": 1, "b": "x"}
    got = capture_flat_mapping(src)
    assert got == src and got is not src
    src["a"] = 99
    assert got["a"] == 1


def test_jsonish_copy_isolates_nested():
    src = {"k": [{"z": 1.0}], "t": (1, 2)}
    got = jsonish_copy(src)
    src["k"][0]["z"] = 0.0
    assert got["k"][0]["z"] == 1.0


def test_receipt_stable_after_further_ticks():
    cfg = tiktaalik_config()
    cfg.cognition.cognition_enabled = True
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    rt.step(5)
    receipt = deepcopy(rt.cognition.get("last_decision_receipt"))
    rt.step(10)
    assert receipt is not rt.cognition.get("last_decision_receipt")
    assert receipt == deepcopy(receipt)


def test_two_agent_actions_deterministic():
    cfg = make_ecology_config(ECOLOGY_STRUCTURED_TERRAIN)
    cfg.cognition.cognition_enabled = True
    a = TwoAgentRuntime(seed=17, config=cfg, signal_enabled=True)
    b = TwoAgentRuntime(seed=17, config=deepcopy(cfg), signal_enabled=True)
    for mid in ("physical_near_field_vision", "illumination_cycle", "physical_body_optical_response"):
        a.set_mechanism(mid, True)
        b.set_mechanism(mid, True)
    seq_a, seq_b = [], []
    for _ in range(40):
        a.step(1)
        b.step(1)
        seq_a.append((a.slots[0].last_selected_action, a.slots[1].last_selected_action))
        seq_b.append((b.slots[0].last_selected_action, b.slots[1].last_selected_action))
    assert seq_a == seq_b


def test_snapshot_restore_deterministic_continuation():
    cfg = make_ecology_config(ECOLOGY_STRUCTURED_TERRAIN)
    cfg.cognition.cognition_enabled = True
    rt = TwoAgentRuntime(seed=17, config=cfg, signal_enabled=True)
    for _ in range(20):
        rt.step(1)
    snap = rt.snapshot()
    rt2 = TwoAgentRuntime.restore(snap)
    for _ in range(15):
        rt.step(1)
        rt2.step(1)
    assert rt.slots[0].last_selected_action == rt2.slots[0].last_selected_action
    assert abs(rt.slots[0].body.x - rt2.slots[0].body.x) < 1e-12
    assert abs(rt.slots[0].body.y - rt2.slots[0].body.y) < 1e-12
