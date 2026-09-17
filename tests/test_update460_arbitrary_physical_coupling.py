from mechanistic_mind.body.models import BodyConfig
from mechanistic_mind.body.acquired_sensorimotor_coupling import LEARNING_RATE
from mechanistic_mind.body.sensorimotor_dynamics import BASE_NON_WAIT
from mechanistic_mind.research.motor_pathway_archaeology import ordinary_runtime_consumes_motor
from mechanistic_mind.world_engine.physical_coupling import (
    C0, C1, FAMILY, PREACT_DIM, SCALE, drive_from_preact, g_drive,
)
from mechanistic_mind.world_engine.physical_effector import N_SITES
from mechanistic_mind.research import arbitrary_physical_coupling as apc


def test_defaults_unchanged():
    assert BodyConfig().physical_coupling_config is None
    assert BodyConfig().physical_effector_config is None
    assert BodyConfig().physical_transduction_config is None
    assert BodyConfig().persistent_process_config is None
    assert LEARNING_RATE == 0.075
    assert BASE_NON_WAIT == 0.08


def test_dims_unchanged():
    assert PREACT_DIM == 3
    assert N_SITES == 4
    assert all(len(FAMILY[k]) == 4 and len(FAMILY[k][0]) == 3 for k in FAMILY)


def test_still_no_ordinary_motor_consumer():
    assert ordinary_runtime_consumes_motor() is False


def test_zero_preact_and_c0():
    assert drive_from_preact((0, 0, 0), C1)["D"] == (0.0, 0.0, 0.0, 0.0)
    assert drive_from_preact((0.7, 0, 0), C0)["D"] == (0.0, 0.0, 0.0, 0.0)


def test_g_identical_and_clips():
    assert g_drive((2.0, -1.0, 0.3, 0.0)) == (1.0, 0.0, 0.3, 0.0)
    assert SCALE == 1.0


def test_basis_joint_perm_preserves_Z():
    p = (0.0, 0.7, 0.0)
    z0 = drive_from_preact(p, C1)["Z"]
    z1 = drive_from_preact(apc.permute_p(p), apc.C_for_perm(C1))["Z"]
    assert all(abs(z0[i] - z1[i]) < 1e-12 for i in range(4))


def test_no_cognition_leaks():
    assert apc.cognition_leaks({"preact": (0.7, 0, 0), "Z": (0.1, 0.7, 0, 0.3), "D": (0.1, 0.7, 0, 0.3)}) == []
