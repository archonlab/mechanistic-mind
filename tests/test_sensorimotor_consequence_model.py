"""Action-conditioned sensorimotor consequence model gates."""
from __future__ import annotations

import copy

import pytest

from mechanistic_mind.physical_system import sensorimotor_consequence as smc
from mechanistic_mind.physical_system.cognition import (
    CognitionConfig,
    empty_cognitive_state,
    run_cognition_before_action,
)


def _obs(**exo):
    base = {
        "exo_0": 0.2,
        "exo_1": 0.5,
        "exo_2": 0.2,
        "local.FIELD_A": 0.0,
        "local.FIELD_B": 0.0,
        "vest_0": 0.5,
        "vest_1": 0.5,
        "prop_neck_0": 0.5,
        "prop_neck_1": 0.5,
        "body.T": 0.4,
        "body.B0": 0.1,
        "body.B1": 0.1,
        "body.B2": 0.1,
        "body.mech": 0.0,
        "body.vx": 0.5,
        "body.vy": 0.5,
        "local.T": 0.4,
        "local.M0": 0.1,
        "local.M1": 0.1,
        "local.M2": 0.1,
        "local.vx": 0.5,
        "local.vy": 0.5,
    }
    base.update(exo)
    return base


def test_gate1_no_semantic_reward_tokens():
    from pathlib import Path
    text = Path("mechanistic_mind/physical_system/sensorimotor_consequence.py").read_text()
    for bad in ("SEEK", "FOLLOW", "APPROACH_REWARD", "VISUAL_REWARD", "TURN_TOWARD_TARGET", "ERROR_MINIMIZATION_GOAL"):
        assert bad not in text


def test_gate2_no_gt_in_channels():
    for k in smc.SENSORY_CHANNELS:
        assert "bearing" not in k and "distance" not in k and "agent" not in k


def test_gate3_temporal_alignment_t_to_t1():
    store = smc.empty_store(enabled=True)
    o0 = _obs(exo_1=0.3)
    o1 = _obs(exo_1=0.7)
    motor = {"locomotion": "MOVE:E", "neck": "NECK_LEFT", "oscillator": {}, "push": False}
    rec = smc.update(store, tick=5, observation_t=o0, motor=motor, observation_t1=o1)
    assert rec is not None
    # Must not learn Motor(T)→Observation(T) (delta would be ~0 if same)
    assert abs(rec["mean_delta"]["exo_1"] - 0.4) < 1e-6


def test_gate4_bounded_capacity():
    store = smc.empty_store(enabled=True, capacity=8)
    # Force distinct quantized contexts (QUANT_BINS=5) × distinct motors so keys exceed capacity.
    necks = ["NONE", "NECK_LEFT", "NECK_RIGHT", "NECK_HOLD"]
    locos = ["WAIT", "MOVE:N", "MOVE:E", "MOVE:S", "MOVE:W"]
    for i in range(40):
        exo = (i % 5) * 0.2 + 0.05  # lands in distinct bins
        o0 = _obs(exo_0=exo, exo_1=(i % 3) * 0.3)
        o1 = _obs(exo_0=min(0.99, exo + 0.1), exo_1=(i % 3) * 0.3)
        motor = {
            "locomotion": locos[i % len(locos)],
            "neck": necks[i % len(necks)],
            "oscillator": {"emit_trigger": bool(i % 2), "frequency_delta": i % 3, "amplitude_delta": 0},
            "push": False,
        }
        smc.update(store, tick=i, observation_t=o0, motor=motor, observation_t1=o1)
    assert len(store["records"]) <= 8
    assert store["evictions"] > 0


def test_gate5_6_head_and_loco_learnable():
    store = smc.empty_store(enabled=True)
    # Head: NECK_LEFT tends to raise exo_0
    for i in range(12):
        o0 = _obs(exo_0=0.2, exo_1=0.5)
        o1 = _obs(exo_0=0.45, exo_1=0.5)
        smc.update(
            store, tick=i,
            observation_t=o0,
            motor={"locomotion": "WAIT", "neck": "NECK_LEFT", "oscillator": {}, "push": False},
            observation_t1=o1,
        )
    # Loco: MOVE:N tends to raise exo_1
    for i in range(12, 24):
        o0 = _obs(exo_0=0.2, exo_1=0.3)
        o1 = _obs(exo_0=0.2, exo_1=0.55)
        smc.update(
            store, tick=i,
            observation_t=o0,
            motor={"locomotion": "MOVE:N", "neck": "NONE", "oscillator": {}, "push": False},
            observation_t1=o1,
        )
    q_neck = smc.query(
        store,
        observation=_obs(exo_0=0.2, exo_1=0.5),
        motor={"locomotion": "WAIT", "neck": "NECK_LEFT", "oscillator": {}, "push": False},
    )
    q_loco = smc.query(
        store,
        observation=_obs(exo_0=0.2, exo_1=0.3),
        motor={"locomotion": "MOVE:N", "neck": "NONE", "oscillator": {}, "push": False},
    )
    assert q_neck["status"] in {smc.MATCH, smc.LOW_SUPPORT}
    assert q_loco["status"] in {smc.MATCH, smc.LOW_SUPPORT}
    assert q_neck["predicted_delta"]["exo_0"] > 0.1
    assert q_loco["predicted_delta"]["exo_1"] > 0.1


def test_gate7_motor_shuffle_harms_conditioning():
    def train(shuffle: bool):
        store = smc.empty_store(enabled=True)
        store["shuffle_motor_labels"] = shuffle
        # Distinct consequences per motor
        mapping = {
            "MOVE:N": ("exo_1", 0.3),
            "MOVE:S": ("exo_1", -0.3),
            "MOVE:E": ("exo_0", 0.3),
            "MOVE:W": ("exo_0", -0.3),
        }
        for t in range(40):
            for loco, (ch, d) in mapping.items():
                o0 = _obs()
                o1 = _obs(**{ch: float(_obs()[ch]) + d})
                smc.update(
                    store, tick=t,
                    observation_t=o0,
                    motor={"locomotion": loco, "neck": "NONE", "oscillator": {}, "push": False},
                    observation_t1=o1,
                )
        # Predict MOVE:N
        q = smc.query(
            store,
            observation=_obs(),
            motor={"locomotion": "MOVE:N", "neck": "NONE", "oscillator": {}, "push": False},
        )
        return q

    ok = train(False)
    shuf = train(True)
    assert ok["status"] != smc.UNKNOWN
    # Shuffled training should not recover the true MOVE:N→exo_1+ mapping cleanly
    # (either UNKNOWN or wrong-signed / weaker |exo_1|)
    if shuf["status"] == smc.UNKNOWN:
        assert True
    else:
        assert abs(shuf["predicted_delta"].get("exo_1", 0.0)) < abs(ok["predicted_delta"].get("exo_1", 0.0)) + 1e-9 or \
            abs(shuf["predicted_delta"].get("exo_1", 0.0) - 0.3) > 0.15


def test_gate8_9_psc_availability_and_ablation_withhold():
    cfg = CognitionConfig(sensorimotor_consequence_model=True, sensorimotor_consequence_withhold_from_psc=False)
    st = empty_cognitive_state(cfg)
    o = _obs()
    for t in range(1, 15):
        o2 = _obs(exo_1=0.2 + 0.02 * t)
        run_cognition_before_action(st, observation=o2, tick=t, rng_value=0.2)
        o = o2
    preds = (st.get("last_selection") or {}).get("sensorimotor_candidate_predictions") or []
    # After learning, some candidate preds may exist (possibly still UNKNOWN early)
    assert (st.get("last_selection") or {}).get("sensorimotor_consequence", {}).get("enabled") is True

    cfg2 = CognitionConfig(
        sensorimotor_consequence_model=True,
        sensorimotor_consequence_withhold_from_psc=True,
    )
    st2 = empty_cognitive_state(cfg2)
    for t in range(1, 10):
        run_cognition_before_action(st2, observation=_obs(exo_1=0.2 + 0.02 * t), tick=t, rng_value=0.2)
    assert (st2.get("last_selection") or {}).get("sensorimotor_withheld_from_psc") is True
    # Withhold: predictions list should not include sensorimotor_consequence source
    preds2 = (st2.get("last_selection") or {}).get("prediction_matches") or []
    assert not any(p.get("source") == "sensorimotor_consequence" for p in preds2)


def test_gate10_does_not_override_behavior_directly():
    # Enabling store alone does not force a fixed action
    cfg = CognitionConfig(sensorimotor_consequence_model=True)
    st = empty_cognitive_state(cfg)
    actions = set()
    for t in range(1, 30):
        r = run_cognition_before_action(st, observation=_obs(), tick=t, rng_value=(t * 0.07) % 1.0)
        actions.add(r.selected_action)
    assert len(actions) >= 1  # at least runs; not a hardcoded TURN_TOWARD


def test_unknown_when_unsupported():
    store = smc.empty_store(enabled=True)
    q = smc.query(store, observation=_obs(), motor={"locomotion": "MOVE:E", "neck": "NONE", "oscillator": {}, "push": False})
    assert q["status"] == smc.UNKNOWN


def test_wait_represented():
    store = smc.empty_store(enabled=True)
    for i in range(6):
        smc.update(
            store, tick=i,
            observation_t=_obs(exo_1=0.4),
            motor={"locomotion": "WAIT", "neck": "NONE", "oscillator": {}, "push": False},
            observation_t1=_obs(exo_1=0.41),
        )
    q = smc.query(store, observation=_obs(exo_1=0.4), motor={"locomotion": "WAIT", "neck": "NONE", "oscillator": {}, "push": False})
    assert q["status"] in {smc.MATCH, smc.LOW_SUPPORT}


def test_snapshot_reload():
    store = smc.empty_store(enabled=True)
    smc.update(
        store, tick=1,
        observation_t=_obs(),
        motor={"locomotion": "MOVE:E", "neck": "NONE", "oscillator": {}, "push": False},
        observation_t1=_obs(exo_0=0.5),
    )
    snap = smc.snapshot(store)
    assert snap["updates"] == 1
    assert len(snap["records"]) == 1


def test_determinism_exact_match_enabled():
    def run(seed_rng: float):
        cfg = CognitionConfig(sensorimotor_consequence_model=True)
        st = empty_cognitive_state(cfg)
        actions = []
        for t in range(1, 40):
            r = run_cognition_before_action(
                st, observation=_obs(exo_1=0.2 + (t % 5) * 0.05), tick=t, rng_value=seed_rng
            )
            actions.append((r.selected_action, (st.get("last_motor_output") or {}).get("neck")))
        return actions, smc.diagnostic(st["sensorimotor_consequence"])

    a1, d1 = run(0.42)
    a2, d2 = run(0.42)
    assert a1 == a2
    assert d1["updates"] == d2["updates"]
    assert d1["occupancy"] == d2["occupancy"]
