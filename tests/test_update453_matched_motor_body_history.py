from mechanistic_mind.body.models import BodyConfig
from mechanistic_mind.body.acquired_sensorimotor_coupling import LEARNING_RATE
from mechanistic_mind.body.sensorimotor_dynamics import BASE_NON_WAIT
from mechanistic_mind.research import matched_motor_body_history as mm


def test_defaults_unchanged():
    assert BodyConfig().persistent_process_config is None
    assert LEARNING_RATE == 0.075
    assert BASE_NON_WAIT == 0.08


def test_selection_is_physical_pulse_pair():
    cands = mm.characterize_all(duration=72, seed=17)
    sel = mm.select_pair(cands)
    assert sel["selected_A"] == "PULSE8_DIST"
    assert sel["selected_B"] == "PULSE8_BLOCK"
    assert sel["PHYSICAL_BODY_CONTRAST"] is True
    d1 = next(c for c in cands if c["name"] == "D1_INTERLEAVE")
    assert d1["sat_occ"] > 0.8


def test_characterize_has_no_R_keys():
    row = mm.characterize_one("PULSE8_DIST", duration=24, seed=17)
    blob = str(row.keys())
    assert "R" not in row
    assert "delta_R" not in blob


def test_matched_motor_zero_mismatch_and_repeat_floor():
    M = mm.make_motor_stream(17, 24)
    a = mm.develop(stream=17, kind="PULSE8_DIST", duration=24, motor_seq=M)
    b = mm.develop(stream=17, kind="PULSE8_BLOCK", duration=24, motor_seq=M)
    a2 = mm.develop(stream=17, kind="PULSE8_DIST", duration=24, motor_seq=M)
    replay = mm.develop(stream=17, kind="PULSE8_DIST", duration=24, motor_seq=M, replay=a["body_tr"])
    assert a["mismatch"] == 0 and b["mismatch"] == 0
    assert a["seq_hash"] == b["seq_hash"] == mm.seq_hash(M)
    from mechanistic_mind.body.acquired_sensorimotor_coupling import l1
    assert l1(a["R"], a2["R"]) == 0.0
    assert l1(a["R"], replay["R"]) == 0.0
    assert a["u_always_empty"] is True
    assert a["W_l1_from_zero"] == 0.0


def test_no_cognition_leaks():
    assert mm.cognition_leaks({
        "u": (0, 0, 0), "N": (0.1, 0.0, 0.0), "R": True,
        "internal_a": 0.5, "load_c": 0.4,
    }) == []
