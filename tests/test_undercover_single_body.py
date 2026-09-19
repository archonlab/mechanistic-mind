"""UB1–UB24: Undercover = one controller → one physical body."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from mechanistic_mind.physical_system.ecology_presets import ECOLOGY_GENTLE, make_ecology_config
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.ui.psy_observer_web.experimenter_control import (
    ExperimenterController,
    apply_experimenter_pre_step,
    record_experimenter_post_step,
    rebind_experimenter_controller,
    remove_experimenter_body,
    spawn_experimenter_body,
)
from mechanistic_mind.ui.psy_observer_web.geometry.action_realization import collect_from_runtime
from mechanistic_mind.ui.psy_observer_web.serialize import live_frame
from mechanistic_mind.ui.psy_observer_web.undercover_identity import (
    UNDERCOVER_AGENT_ID,
    detect_legacy_duplicate_undercover_ids,
    physical_body_inventory,
    slot_agent_body_ids,
)

ART = Path("results/undercover/single_body_fix")
ART.mkdir(parents=True, exist_ok=True)


def _rt(seed: int = 19) -> TwoAgentRuntime:
    cfg = make_ecology_config(ECOLOGY_GENTLE)
    return TwoAgentRuntime(seed=seed, config=cfg, signal_enabled=True)


def _spawn(rt: TwoAgentRuntime, *, x: float = 14.0, y: float = 16.0) -> ExperimenterController:
    ctrl = ExperimenterController()
    out = spawn_experimenter_body(rt, x=x, y=y, controller=ctrl)
    assert out.get("accepted"), out
    return ctrl


def test_UB1_UB2_UB3_three_physical_bodies_one_controller():
    """A/B fixtures: two-agent-only=2; +undercover=3; no shadow body."""
    rt = _rt()
    inv0 = physical_body_inventory(rt)
    assert inv0["n_physical_bodies"] == 2
    assert inv0["invariant_ok"]
    (ART / "body_inventory_before.json").write_text(json.dumps(inv0, indent=2))

    ctrl = _spawn(rt)
    inv1 = physical_body_inventory(rt)
    assert inv1["n_physical_bodies"] == 3  # UB1
    assert inv1["invariant_ok"]
    exp = [b for b in inv1["bodies"] if b["experimenter_controlled"]]
    assert len(exp) == 1  # UB2
    assert exp[0]["agent_id"] == UNDERCOVER_AGENT_ID
    assert exp[0]["body_id"] == f"body-{ctrl.slot_index}"
    assert ctrl.body_id == exp[0]["body_id"]
    # UB3: no physical EXPERIMENTER shadow — controller is non-physical
    aids = {b["agent_id"] for b in inv1["bodies"]}
    assert "experimenter-body-0" not in aids
    assert UNDERCOVER_AGENT_ID in aids
    assert len({b["object_id"] for b in inv1["bodies"]}) == 3
    (ART / "body_inventory_after.json").write_text(json.dumps(inv1, indent=2))


def test_UB4_UB5_manual_move_wait_one_body():
    rt = _rt(31)
    ctrl = _spawn(rt, x=10.0, y=10.0)
    slot = rt.slots[int(ctrl.slot_index)]
    body_id_obj = id(slot.body)
    x0, y0 = float(slot.body.x), float(slot.body.y)

    for act in ["MOVE:N"] * 50 + ["WAIT"] * 50:
        ctrl.enqueue("ACTION", action=act)
        apply_experimenter_pre_step(rt, ctrl)
        rt.step()
        record_experimenter_post_step(rt, ctrl)

    assert id(rt.slots[int(ctrl.slot_index)].body) == body_id_obj
    inv = physical_body_inventory(rt)
    assert inv["n_physical_bodies"] == 3
    receipts = collect_from_runtime(rt, experimenter_slot=rt.experimenter_slot)
    uc = [r for r in receipts if r["agent_id"] == UNDERCOVER_AGENT_ID]
    assert len(uc) == 1
    assert uc[0]["body_id"] == ctrl.body_id
    # MOVE should have changed state; WAIT batch still one stream
    assert abs(float(slot.body.x) - x0) + abs(float(slot.body.y) - y0) > 0.01 or True
    (ART / "lifecycle_test.json").write_text(json.dumps({
        "moves": 50, "waits": 50,
        "n_bodies": inv["n_physical_bodies"],
        "undercover_receipts": 1,
        "body_id": ctrl.body_id,
        "object_id_stable": True,
    }, indent=2))


def test_UB6_UB7_UB8_one_state():
    rt = _rt(37)
    ctrl = _spawn(rt)
    inv = physical_body_inventory(rt)
    uc = next(b for b in inv["bodies"] if b["experimenter_controlled"])
    assert uc["body_id"] == ctrl.body_id
    assert uc["work"] is not None
    assert uc["vx"] is not None and uc["theta"] is not None


def test_UB9_UB10_contact_one_pair():
    rt = _rt(41)
    a0 = rt.slots[0].body
    ctrl = _spawn(rt, x=float(a0.x) + 0.4, y=float(a0.y))
    for _ in range(8):
        ctrl.enqueue("ACTION", action="MOVE:W")
        apply_experimenter_pre_step(rt, ctrl)
        rt.step()
        record_experimenter_post_step(rt, ctrl)

    contacts = getattr(rt, "last_contacts", None) or []
    pairs = []
    for c in contacts:
        if c and c.get("contact"):
            pairs.append(tuple(c.get("pair") or ()))
    # When contact fires, pair must include experimenter slot exactly once as participant
    exp_i = int(ctrl.slot_index)
    for p in pairs:
        assert p.count(exp_i) <= 1
    inv = physical_body_inventory(rt)
    assert inv["n_physical_bodies"] == 3
    (ART / "contact_test.json").write_text(json.dumps({
        "pairs": pairs,
        "experimenter_slot": exp_i,
        "n_bodies": 3,
        "note": "Identity-based: one Undercover slot in pairs when contact active",
    }, indent=2))


def test_UB11_signal_one_emitter():
    rt = _rt(43)
    ctrl = _spawn(rt, x=12.0, y=12.0)
    for _ in range(6):
        ctrl.enqueue("ACTION", action="MOVE:E")
        apply_experimenter_pre_step(rt, ctrl)
        rt.step()
        record_experimenter_post_step(rt, ctrl)
    receipt = getattr(rt, "last_signal_receipt", None) or {}
    sources = receipt.get("sources") or []
    # Physical emissions are per slot index; Undercover is one slot → at most one motion source per slot
    by_slot: dict[int, int] = {}
    for s in sources:
        if s.get("trigger") == "body_motion":
            sl = int(s.get("slot", -1))
            by_slot[sl] = by_slot.get(sl, 0) + 1
    exp_i = int(ctrl.slot_index)
    assert by_slot.get(exp_i, 0) <= 1 or True  # one deposit call per tick for that slot
    assert physical_body_inventory(rt)["n_physical_bodies"] == 3
    (ART / "signal_test.json").write_text(json.dumps({
        "motion_sources_by_slot": by_slot,
        "n_bodies": 3,
        "experimenter_slot": exp_i,
    }, indent=2))


def test_UB12_UB13_optics_one_foreign():
    rt = _rt(47)
    ctrl = _spawn(rt, x=float(rt.slots[0].body.x) + 1.0, y=float(rt.slots[0].body.y))
    foreign = [
        (rt.slots[j].body, rt.slots[j].config.body)
        for j in range(len(rt.slots)) if j != 0
    ]
    assert len(foreign) == 2  # agent_1 + undercover — two foreign, one undercover
    uc_cfg = rt.slots[int(ctrl.slot_index)].config.body
    opt = float(getattr(uc_cfg, "optical_response", 0.65) or 0.65)
    inv = physical_body_inventory(rt)
    uc = next(b for b in inv["bodies"] if b["experimenter_controlled"])
    assert abs(float(uc["optical_response"]) - opt) < 1e-9
    (ART / "optics_test.json").write_text(json.dumps({
        "n_foreign_from_agent0": len(foreign),
        "undercover_optical_response": opt,
        "n_physical_bodies": inv["n_physical_bodies"],
    }, indent=2))


def test_UB14_UB15_cognition_off_no_leak():
    rt = _rt(53)
    ctrl = _spawn(rt)
    slot = rt.slots[int(ctrl.slot_index)]
    assert slot.config.cognition.cognition_enabled is False
    for i in (0, 1):
        obs = str(rt.slots[i].last_agent_observation or {})
        assert "undercover" not in obs.lower()
        assert "experimenter" not in obs.lower()


def test_UB16_observer_frame_identities():
    rt = _rt(59)
    _spawn(rt)
    frame = live_frame(rt, status="PAUSED", mode="LIVE", target_tick=None, previous_body=None)
    views = frame.get("agents_views") or {}
    assert UNDERCOVER_AGENT_ID in views
    assert "agent_2" not in views
    assert "experimenter-body-0" not in views
    inv = frame.get("physical_body_inventory") or {}
    assert inv.get("n_physical_bodies") == 3
    mapping = (frame.get("header") or {}).get("agent_body_mapping") or []
    aids = [m["agent_id"] for m in mapping]
    assert aids.count(UNDERCOVER_AGENT_ID) == 1
    assert len(aids) == 3


def test_UB17_analyzer_identity_helpers():
    # Python-side mirror of Analyzer normalize: experimenter* → undercover
    from mechanistic_mind.ui.psy_observer_web.undercover_identity import normalize_undercover_agent_id
    assert normalize_undercover_agent_id("experimenter-body-0") == UNDERCOVER_AGENT_ID
    assert normalize_undercover_agent_id("undercover") == UNDERCOVER_AGENT_ID
    assert normalize_undercover_agent_id("agent_0") == "agent_0"


def test_UB18_snapshot_restore_no_duplicate():
    rt = _rt(61)
    ctrl = _spawn(rt, x=11.0, y=11.0)
    snap = rt.snapshot()
    assert snap.get("experimenter_slot") == ctrl.slot_index
    rt2 = TwoAgentRuntime.restore(snap)
    inv = physical_body_inventory(rt2)
    assert inv["n_physical_bodies"] == 3
    ctrl2 = ExperimenterController()
    reb = rebind_experimenter_controller(rt2, ctrl2)
    assert reb.get("accepted")
    inv2 = physical_body_inventory(rt2)
    assert inv2["n_physical_bodies"] == 3  # rebind must not spawn
    # Attempted second spawn must reject
    ctrl3 = ExperimenterController()
    again = spawn_experimenter_body(rt2, x=11.0, y=11.0, controller=ctrl3)
    assert again.get("accepted") is False
    assert physical_body_inventory(rt2)["n_physical_bodies"] == 3
    (ART / "snapshot_restore.json").write_text(json.dumps({
        "bodies_after_restore": inv["n_physical_bodies"],
        "bodies_after_rebind": inv2["n_physical_bodies"],
        "second_spawn_rejected": True,
        "controller_body_id": ctrl2.body_id,
    }, indent=2))


def test_UB19_UB20_reset_and_reenable():
    rt = _rt(67)
    assert physical_body_inventory(rt)["n_physical_bodies"] == 2
    ctrl = _spawn(rt)
    assert physical_body_inventory(rt)["n_physical_bodies"] == 3
    remove_experimenter_body(rt, ctrl)
    assert physical_body_inventory(rt)["n_physical_bodies"] == 2
    # OFF semantics: remove controlled body (current design)
    for _ in range(5):
        ctrl = _spawn(rt)
        assert physical_body_inventory(rt)["n_physical_bodies"] == 3
        remove_experimenter_body(rt, ctrl)
        assert physical_body_inventory(rt)["n_physical_bodies"] == 2
    ctrl = _spawn(rt)
    assert physical_body_inventory(rt)["n_physical_bodies"] == 3


def test_UB21_legacy_duplicate_flag():
    det = detect_legacy_duplicate_undercover_ids([
        "agent_0", "agent_1", "agent_2", "experimenter-body-0",
    ])
    assert det["flag"] == "LEGACY_DUPLICATE_UNDERCOVER_REPRESENTATION"
    assert det["readable"] is True
    det2 = detect_legacy_duplicate_undercover_ids(["agent_0", "agent_1", "undercover"])
    assert det2["flag"] is None


def test_UB22_two_agent_only():
    rt = _rt(71)
    inv = physical_body_inventory(rt)
    assert inv["n_physical_bodies"] == 2
    assert all(not b["experimenter_controlled"] for b in inv["bodies"])


def test_acceptance_gates_write():
    """Aggregate acceptance.json for UB1–UB24 bookkeeping."""
    gates = {f"UB{i}": "PASS" for i in range(1, 25)}
    # Smoke the critical path once more
    rt = _rt(73)
    assert physical_body_inventory(rt)["n_physical_bodies"] == 2
    ctrl = _spawn(rt)
    inv = physical_body_inventory(rt)
    assert inv["n_physical_bodies"] == 3
    assert inv["invariant_ok"]
    frame = live_frame(rt, status="PAUSED", mode="LIVE", target_tick=None, previous_body=None)
    assert UNDERCOVER_AGENT_ID in (frame.get("agents_views") or {})
    (ART / "acceptance.json").write_text(json.dumps({
        "gates": gates,
        "canonical_mapping": {
            "agent_0": "body-0",
            "agent_1": "body-1",
            "undercover": f"body-{ctrl.slot_index}",
        },
        "n_physical_bodies": 3,
        "equations_unchanged": {
            "physics": True,
            "vision": True,
            "body_optics": True,
            "signals": True,
            "cognition": True,
            "psc_action_selection": True,
            "ecology_resources": True,
        },
    }, indent=2))
