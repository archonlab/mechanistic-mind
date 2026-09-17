from mechanistic_mind.body.models import BodyConfig
from mechanistic_mind.body.acquired_sensorimotor_coupling import LEARNING_RATE
from mechanistic_mind.body.sensorimotor_dynamics import BASE_NON_WAIT
from mechanistic_mind.research import early_physical_ecology as epe


def test_defaults_unchanged():
    assert BodyConfig().persistent_process_config is None
    assert LEARNING_RATE == 0.075
    assert BASE_NON_WAIT == 0.08


def test_d1_changes_body_without_u():
    d1 = epe.develop(seed=17, kind="D1", duration=24)
    assert d1["max_a"] > 0.26
    assert d1["u_always_empty"] is True
    assert d1["W_l1_from_zero"] == 0.0


def test_d4_matches_d1_body_and_R():
    d1 = epe.develop(seed=17, kind="D1", duration=24)
    d4 = epe.develop(seed=17, kind="D4", duration=24, replay=d1["body_tr"])
    assert d1["body_tr"] == d4["body_tr"]
    from mechanistic_mind.body.acquired_sensorimotor_coupling import l1
    assert l1(d1["R"], d4["R"]) == 0.0


def test_no_cognition_leaks():
    assert epe.cognition_leaks({"u": (0, 0, 0), "N": (0.1, 0.0, 0.0), "R": True}) == []
