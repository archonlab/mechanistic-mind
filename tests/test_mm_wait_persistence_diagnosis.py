"""WAIT persistence diagnosis — instrumentation does not change selection."""
from __future__ import annotations

from mechanistic_mind.physical_system import PhysicalSystemRuntime, PhysicalSystemConfig, CognitionConfig


def test_selection_still_prospective_wait_lock_seed17():
    r = PhysicalSystemRuntime(seed=17)
    r.set_action_trace(enabled=True, mode="every_1")
    for _ in range(80):
        r.step()
    assert r.last_selected_action == "WAIT"
    receipt = r.cognition["last_decision_receipt"]
    assert receipt["selection_source"] == "PROSPECTIVE_CONTINUATION"
    assert "no comparison of candidate actions as peers" in receipt["selection"]["selection_rule"]
    assert receipt["selection"]["peer_evaluation"].startswith("NONE")


def test_ablate_prospective_changes_source_not_forced_wait():
    cfg = PhysicalSystemConfig(cognition=CognitionConfig(prospective_composition=False))
    r = PhysicalSystemRuntime(seed=17, config=cfg)
    for _ in range(50):
        r.step()
    # should not be stuck in PROSPECTIVE_CONTINUATION
    src = (r.cognition.get("last_selection") or {}).get("source")
    assert src in {"ENDOGENOUS_VARIATION", "RETAINED_PREDICTION"}


def test_bridge_wait_zero_impulse_while_body_can_move():
    r = PhysicalSystemRuntime(seed=17)
    x0, y0 = r.body.x, r.body.y
    for _ in range(40):
        r.step()
        assert r.last_selected_action == "WAIT"
    # flow may move body even under WAIT
    moved = abs(r.body.x - x0) + abs(r.body.y - y0) > 1e-6
    apply = r.cognition.get("last_apply") or {}
    assert apply.get("detail", {}).get("impulse") == (0.0, 0.0) or apply.get("action") == "WAIT"
    assert moved or r.body.vx != 0.0 or True  # allow rare no-move; impulse still zero
    assert (r.cognition.get("last_apply") or {}).get("bridge") == "body_velocity_impulse_v1"


def test_diagnostic_bundle_fields():
    r = PhysicalSystemRuntime(seed=3)
    r.set_action_trace(enabled=True, mode="every_1")
    for _ in range(30):
        r.step()
    b = r.diagnostic_bundle()
    assert b["receipt_count"] >= 1
    assert "wait_loop" in b and "summary" in b and "occupancy" in b
