from mechanistic_mind.body import BodyConfig, BodyState
from mechanistic_mind.body.acquired_sensorimotor_coupling import LEARNING_RATE
from mechanistic_mind.body.sensorimotor_dynamics import BASE_NON_WAIT
from mechanistic_mind.research import default_runtime_body_access as drba
from worlds.organism_world_v03 import OrganismWorld


def test_architecture_constants_unchanged():
    assert LEARNING_RATE == 0.075
    assert BASE_NON_WAIT == 0.08
    assert BodyConfig().persistent_process_config is None
    assert BodyState().internal_loads == {}


def test_default_organism_does_not_enable_processes():
    world = drba.default_world()
    assert isinstance(world, OrganismWorld)
    assert world.body_config.persistent_process_config is None
    assert world.initial_body.internal_loads == {}


def test_default_wait_does_not_write_439_keys():
    row = drba.run_mode(seed=17, mode="WAIT")
    assert row["config_final_none"] is True
    assert row["internal_a_present"] is False
    assert row["load_c_present"] is False
    assert row["load_keys"] == []
    assert row["fatigue_span"] > 1e-6


def test_no_cognition_leaks():
    assert drba.cognition_leaks({"u": (0, 0, 0), "internal_loads": {}, "N": (0.0, 0.0, 0.0)}) == []
