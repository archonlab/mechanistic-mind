from mechanistic_mind.body.acquired_sensorimotor_coupling import LEARNING_RATE
from mechanistic_mind.body.models import BodyConfig
from mechanistic_mind.body.sensorimotor_dynamics import BASE_NON_WAIT, DECAY
from mechanistic_mind.research import world_body_motor_access as wbma


def test_architecture_constants_unchanged():
    assert LEARNING_RATE == 0.075
    assert BASE_NON_WAIT == 0.08
    assert DECAY == 0.72


def test_default_runtime_does_not_enable_processes():
    assert BodyConfig().persistent_process_config is None


def test_world_fields_do_not_write_u():
    RA, RB, dR, d_probe = wbma.acquire_pair(17)
    rows = wbma.run_trace(
        seed=17, pos=wbma.POS_A, fields_on=True, processes_on=True,
        steps=8, RA=RA, RB=RB, dR=dR, d_probe=d_probe,
        klass="PHYSICALLY_ORDINARY_STAGED",
    )
    assert all(r["u_L2"] == 0.0 for r in rows)
    assert rows[-1]["internal_a"] > 0.25 + 1e-6


def test_body_matched_reproduces_N():
    b = wbma.seed_bundle(17)
    assert b["WORLD_A"]["N"] == b["BODY_MATCHED"]["N"]
    assert b["WORLD_A"]["obs"] == b["BODY_MATCHED"]["obs"]
    assert b["WORLD_A"]["u_L2"] == 0.0


def test_no_cognition_leaks():
    assert wbma.cognition_leaks({
        "u": (0, 0, 0),
        "N": (0.2, -0.1, 0.06),
        "internal_a": 0.88,
    }) == []
