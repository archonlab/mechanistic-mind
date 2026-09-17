from dataclasses import replace

from mechanistic_mind.body.models import BodyConfig
from mechanistic_mind.body.acquired_sensorimotor_coupling import LEARNING_RATE
from mechanistic_mind.body.sensorimotor_dynamics import BASE_NON_WAIT
from mechanistic_mind.research.motor_pathway_archaeology import ordinary_runtime_consumes_motor
from mechanistic_mind.world_engine.physical_effector import (
    N_SITES,
    default_effector_config,
    resolve_hop,
    resultant,
    step_e,
)
from mechanistic_mind.research import generic_physical_effector as gpe


def test_defaults_unchanged():
    assert BodyConfig().physical_effector_config is None
    assert BodyConfig().physical_transduction_config is None
    assert BodyConfig().persistent_process_config is None
    assert LEARNING_RATE == 0.075
    assert BASE_NON_WAIT == 0.08


def test_still_no_ordinary_motor_consumer():
    assert ordinary_runtime_consumes_motor() is False


def test_effector_dim_from_lattice_not_preact():
    assert N_SITES == 4
    cfg = default_effector_config()
    assert len(cfg["sites"]) == 4


def test_step_e_decays_and_clips():
    e = step_e((0, 0, 0, 0), (1, 0, 0, 0))
    assert e[0] == 1.0
    z = step_e(e, (0, 0, 0, 0))
    assert z[0] == 0.5
    clipped = step_e((0, 0, 0, 0), (4, 4, 4, 4))
    assert clipped == (1.0, 1.0, 1.0, 1.0)


def test_balanced_resultant_is_zero():
    q = resultant((1.0, 0.0, 0.0, 1.0), ((0, -1), (-1, 0), (1, 0), (0, 1)))
    assert q == (0.0, 0.0)
    hop, rule = resolve_hop(q)
    assert hop == (0, 0)


def test_no_cognition_leaks():
    assert gpe.cognition_leaks({"E": (0.5, 0, 0, 0), "Q": (0.0, -0.5), "N": (0.7, 0, 0)}) == []


def test_source_does_not_read_internal_motor():
    src = gpe.source_audit()
    assert src["physical_effector_reads_internal_motor"] == []
    assert src["hook_reads_preact"] is False
