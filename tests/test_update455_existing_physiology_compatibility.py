from mechanistic_mind.body.models import BodyConfig
from mechanistic_mind.body.acquired_sensorimotor_coupling import LEARNING_RATE
from mechanistic_mind.body.sensorimotor_dynamics import BASE_NON_WAIT
from mechanistic_mind.research import existing_physiology_compatibility as epc


def test_defaults_unchanged():
    assert BodyConfig().persistent_process_config is None
    assert LEARNING_RATE == 0.075
    assert BASE_NON_WAIT == 0.08


def test_projection_family_is_direct_identity():
    rec = {"fatigue": [0.2, 0.8], "energy_reserve": [0.7, 0.4], "hydration": [0.6, 0.5]}
    a, c = epc.project("FAT_A", rec)
    assert a == [0.2, 0.8] and c == [0.5, 0.5]
    a, c = epc.project("CONST", rec)
    assert a == [0.5, 0.5] and c == [0.5, 0.5]


def test_replay_is_researcher_only_and_bounded():
    rows = epc.replay_N([0.2, 0.8], [0.5, 0.5], seed=17)
    assert len(rows) == 2
    assert all(len(r) == 3 for r in rows)
    assert all(all(-1.0 <= x <= 1.0 for x in r) for r in rows)


def test_no_cognition_leaks():
    assert epc.cognition_leaks({
        "u": (0, 0, 0), "N": (0.1, 0.0, 0.0),
        "fatigue": 0.2, "energy_reserve": 0.7, "hydration": 0.7,
    }) == []
