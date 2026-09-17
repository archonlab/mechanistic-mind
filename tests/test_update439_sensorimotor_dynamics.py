from mechanistic_mind.body.sensorimotor_dynamics import SensorimotorState, evolve, motor_distribution
from mechanistic_mind.research import intrinsic_sensorimotor_dynamics as ism
from experiments.run_update439_sensorimotor_dynamics import run_seed


def test_state_is_bounded_and_intrinsic():
    state=SensorimotorState()
    for i in range(1000): state=evolve(state,body=ism.body(.9,.1),random_value=(i%11)/10)
    assert all(-1 <= x <= 1 for x in state.channels)
    assert motor_distribution(state)["provenance"]["ordinary_state_value"] == 0.0


def test_actual_body_couples_but_visible_signal_alone_does_not():
    a=ism.reactive_probe(ism.body(.2,.8),seed=17); b=ism.reactive_probe(ism.body(.8,.2),seed=17)
    assert a["state"]["channels"] != b["state"]["channels"]
    off_a=ism.reactive_probe(ism.body(.2,.8),seed=17,body_coupling=False)
    off_b=ism.reactive_probe(ism.body(.8,.2),seed=17,body_coupling=False)
    assert off_a["state"]["channels"] == off_b["state"]["channels"]
    hidden=ism.reactive_probe(ism.body(.8,.2),seed=17,signal_visible=False)
    assert hidden["state"] == b["state"]


def test_prediction_composes_but_does_not_reenter_present_state():
    store=ism.empty_store(); ism.acquire(store,exposures=36,seed=23)
    chain=ism.predict_chain(store,ism.cue(.62,.68)); assert chain["composed"]
    learned=ism.anticipatory_probe(store,ism.cue(.62,.68),current_body=ism.body(),seed=23)
    clean=ism.anticipatory_probe(ism.empty_store(),ism.cue(.62,.68),current_body=ism.body(),seed=23)
    assert learned["prediction"]["composed"]
    assert learned["state"] == clean["state"]
    assert learned["motor"] == clean["motor"]


def test_claim_boundary_and_leak_audit():
    row=run_seed(41)
    assert all(row["claims"][f"C{i}_"+next(k.split(f"C{i}_",1)[1] for k in row["claims"] if k.startswith(f"C{i}_"))] for i in range(1,13))
    assert not row["claims"]["C13_matched_state_anticipatory_modulation"]
    assert not row["claims"]["C14_anticipatory_motor_influence"]
    assert row["leak"] == []
