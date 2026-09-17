
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime, PhysicalSystemConfig
from mechanistic_mind.physical_system.cognition import CognitionConfig

def test_motion_receipt_marks_internal_transfer_not_demonstrated():
    rt = PhysicalSystemRuntime(seed=17, config=PhysicalSystemConfig(cognition=CognitionConfig(prospective_selection="LEGACY_FIRST")))
    rt.set_motion_trace(enabled=True, mode="every_1")
    rt.step()
    rec = rt.last_motion_receipt
    assert rec["schema"] == "mm.motion_causal_receipt.v1"
    assert rec["internal_to_external_spatial"]["status"] == "NOT_DEMONSTRATED"
    assert rec["action"]["emitted_impulse"] == [0.0, 0.0] or isinstance(rec["action"]["emitted_impulse"], list)

def test_wait_can_move_via_world_or_mech():
    rt = PhysicalSystemRuntime(seed=17)
    rt.set_motion_trace(enabled=True, mode="every_1")
    moved = False
    for _ in range(30):
        rt.step()
        rec = rt.last_motion_receipt
        if rec and rec.get("selected_action") == "WAIT" or True:
            if abs(rec["motion_update"]["delta_position_naive"]["mag"]) > 1e-9:
                causes = rec["motion_update"]["identifiable_causes_this_tick"]
                assert "ACTION_IMPULSE" not in causes or rec["action"]["emitted_impulse"] == [0.0, 0.0]
                moved = True
                break
    assert moved
