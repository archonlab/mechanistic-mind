from mechanistic_mind.body.models import BodyConfig
from mechanistic_mind.body.acquired_sensorimotor_coupling import LEARNING_RATE
from mechanistic_mind.body.sensorimotor_dynamics import BASE_NON_WAIT
from mechanistic_mind.research import ordinary_physical_ecology as ope


def test_defaults_unchanged():
    assert BodyConfig().persistent_process_config is None
    assert LEARNING_RATE == 0.075
    assert BASE_NON_WAIT == 0.08


def test_ordinary_wait_does_not_write_439():
    row = ope.run_mode(seed=17, mode="WAIT", steps=16)
    assert row["config_final_none"] is True
    assert row["internal_a_present"] is False
    assert row["load_c_present"] is False
    assert row["load_keys"] == []
    assert row["a_class"] == "STATIC"


def test_439_inputs_still_only_a_and_c():
    import inspect
    from mechanistic_mind.body import sensorimotor_dynamics as sd
    src = inspect.getsource(sd.evolve)
    assert 'body.get("internal_a"' in src
    assert 'body.get("load_c"' in src


def test_no_cognition_leaks():
    assert ope.cognition_leaks({
        "u": (0, 0, 0), "N": (0.0, 0.0, 0.0), "internal_loads": {},
    }) == []
