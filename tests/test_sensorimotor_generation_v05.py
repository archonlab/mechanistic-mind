from __future__ import annotations

from copy import deepcopy

from mechanistic_mind.agent import Action, Observation
from mechanistic_mind.psyche.sensorimotor import (
    BUDGET_TOTAL,
    SensorimotorConfig,
    SensorimotorStore,
    action_is_physical,
    apply_consequence,
    available_actions,
    generate_proposals,
    remember_action,
    select_proposal,
    update_store,
)


def _obs(
    *,
    position=(2, 2),
    objects=None,
    actions=None,
    energy=0.8,
    hydration=0.8,
    fatigue=0.1,
    hidden=None,
) -> dict:
    objects = objects or [
        {
            "id": "OBJ-X",
            "position": [3, 2],
            "relative_offset": [1, 0],
            "cue_signature": "CUE-X",
            "interaction_state": "FREE",
        }
    ]
    actions = actions or ["MOVE:3,2", "PUSH:OBJ-X:4,2", "WAIT"]
    data = {
        "position": list(position),
        "visible_objects": objects,
        "available_actions": actions,
        "interoception": {
            "energy_signal": energy,
            "hydration_signal": hydration,
            "fatigue_signal": fatigue,
        },
        "visual_fragments": [
            {"kind": "OBJECT", "cue_signature": item["cue_signature"]}
            for item in objects
        ],
    }
    if hidden:
        data["hidden_truth"] = hidden
    return data


def _step_world(obs: dict, action: str, *, displace_x: bool = True) -> dict:
    nxt = deepcopy(obs)
    if action.startswith("MOVE:"):
        dest = action.split(":", 1)[1].split(",")
        nxt["position"] = [int(dest[0]), int(dest[1])]
        nxt["visual_fragments"] = list(obs.get("visual_fragments") or []) + [
            {"kind": "MOVE"}
        ]
    if action.startswith("PUSH:OBJ-X") and displace_x:
        for item in nxt["visible_objects"]:
            if item["id"] == "OBJ-X":
                item["position"] = [item["position"][0] + 1, item["position"][1]]
                item["relative_offset"] = [
                    item["position"][0] - nxt["position"][0],
                    item["position"][1] - nxt["position"][1],
                ]
    if action.startswith(("PUSH:", "TAKE:", "MOVE:")):
        nxt["interoception"]["fatigue_signal"] = min(
            1.0, float(nxt["interoception"]["fatigue_signal"]) + 0.02
        )
    return nxt


def _train(n: int = 8, displace_x: bool = True) -> SensorimotorStore:
    store = SensorimotorStore()
    config = SensorimotorConfig()
    obs = _obs()
    for _ in range(n):
        generated = generate_proposals(
            observation=obs, store=store, config=config, random_value=0.11
        )
        remember_action(store, "PUSH:OBJ-X:4,2", obs)
        nxt = _step_world(obs, "PUSH:OBJ-X:4,2", displace_x=displace_x)
        update_store(store, observation=nxt, config=config)
        obs = _obs()
    return store


def test_empty_memory_generates_lawful_motor_proposals() -> None:
    generated = generate_proposals(
        observation=_obs(),
        store=SensorimotorStore(),
        config=SensorimotorConfig(),
        random_value=0.2,
    )
    assert generated["proposals"]
    assert {item["action"] for item in generated["proposals"]} <= set(
        generated["available"]
    )
    assert any(item["source"] == "ENDOGENOUS_VARIATION" for item in generated["proposals"])


def test_endogenous_generation_never_proposes_impossible_or_hidden_targets() -> None:
    obs = _obs(actions=["WAIT", "PUSH:OBJ-HIDDEN:9,9", "PUSH:OBJ-X:4,2"])
    generated = generate_proposals(
        observation=obs,
        store=SensorimotorStore(),
        config=SensorimotorConfig(),
        random_value=0.0,
    )
    actions = {item["action"] for item in generated["proposals"]}
    assert "PUSH:OBJ-HIDDEN:9,9" not in actions
    assert "PUSH:OBJ-X:4,2" in generated["available"] or "WAIT" in actions
    assert action_is_physical("PUSH:OBJ-HIDDEN:9,9", set(obs["available_actions"]), frozenset({"OBJ-X"})) is False


def test_proposals_enter_selection_but_cannot_self_execute() -> None:
    generated = generate_proposals(
        observation=_obs(),
        store=SensorimotorStore(),
        config=SensorimotorConfig(),
        random_value=0.4,
    )
    chosen = select_proposal(generated, body={"energy_signal": 0.8}, random_value=0.1)
    assert chosen["action"] in {item["action"] for item in generated["proposals"]} | {"WAIT"}
    assert "execute" not in chosen["reason"].lower()


def test_wait_may_still_win_and_severe_physiology_can_suppress_interaction() -> None:
    generated = generate_proposals(
        observation=_obs(energy=0.05, hydration=0.05, fatigue=0.9),
        store=SensorimotorStore(),
        config=SensorimotorConfig(),
        random_value=0.0,
    )
    chosen = select_proposal(
        generated,
        body={"energy_signal": 0.05, "hydration_signal": 0.05, "fatigue_signal": 0.9},
        random_value=0.0,
    )
    assert chosen["action"] == "WAIT"
    assert chosen["reason"] in {"PHYSIOLOGY_SUPPRESSION", "ORDINARY_VALUE", "NO_CANDIDATES"}


def test_no_curiosity_novelty_information_or_controllability_reward() -> None:
    generated = generate_proposals(
        observation=_obs(),
        store=SensorimotorStore(),
        config=SensorimotorConfig(),
        random_value=0.3,
    )
    for item in generated["proposals"]:
        assert item["ordinary_action_value"] == 0.0
        assert "bonus" not in item


def test_unknown_has_no_positive_action_value() -> None:
    generated = generate_proposals(
        observation=_obs(),
        store=SensorimotorStore(),
        config=SensorimotorConfig(),
        random_value=0.15,
    )
    assert generated["evidence"]["unknown"] is True
    assert all(item["ordinary_action_value"] == 0.0 for item in generated["proposals"])


def test_learned_contingency_forms_from_accessible_evidence_only() -> None:
    store = _train(6, displace_x=True)
    records = list(store.contingencies.values())
    assert records
    assert records[0]["support"] >= 6
    assert records[0]["displace_rate"] == 1.0
    blob = str(store.to_dict())
    assert "hidden_truth" not in blob


def test_external_change_is_not_automatic_self_cause() -> None:
    store = SensorimotorStore()
    config = SensorimotorConfig()
    obs = _obs()
    remember_action(store, "WAIT", obs)
    moved = _step_world(obs, "PUSH:OBJ-X:4,2", displace_x=True)
    update_store(store, observation=moved, config=config)
    record = next(iter(store.contingencies.values()))
    assert record["action"] == "WAIT"
    assert record["causal_confidence"] == 0.0


def test_learned_contingency_can_structure_later_proposals() -> None:
    store = _train(8)
    generated = generate_proposals(
        observation=_obs(),
        store=store,
        config=SensorimotorConfig(),
        random_value=0.0,
    )
    sources = {item["action"]: item["source"] for item in generated["proposals"]}
    assert any(
        source in {"LEARNED_SENSORIMOTOR", "BOTH"} for source in sources.values()
    )


def test_learned_evidence_does_not_bypass_ordinary_valuation() -> None:
    store = _train(8)
    values = {"PUSH:OBJ-X:4,2": {"base_total": -1.0}, "WAIT": {"base_total": 0.2}}
    generated = generate_proposals(
        observation=_obs(),
        store=store,
        config=SensorimotorConfig(),
        random_value=0.0,
        values=values,
    )
    chosen = select_proposal(generated, body={"energy_signal": 0.8}, random_value=0.0)
    assert chosen["action"] == "WAIT"


def test_proposal_and_retrieval_remain_bounded() -> None:
    store = SensorimotorStore()
    config = SensorimotorConfig()
    for index in range(40):
        obs = _obs(position=(index % 5, 2))
        remember_action(store, "WAIT" if index % 2 else "PUSH:OBJ-X:4,2", obs)
        update_store(store, observation=_step_world(obs, "WAIT"), config=config)
    generated = generate_proposals(
        observation=_obs(), store=store, config=config, random_value=0.2
    )
    assert generated["evidence"]["inspected"] <= BUDGET_TOTAL
    assert len(generated["proposals"]) <= 12
    assert generated["evidence"]["budget"]["max_total_memory_candidates"] == 12


def test_same_seed_is_deterministic() -> None:
    def run(seed: float) -> list[str]:
        generated = generate_proposals(
            observation=_obs(),
            store=SensorimotorStore(),
            config=SensorimotorConfig(),
            random_value=seed,
        )
        return [item["action"] for item in generated["proposals"]]

    assert run(0.37) == run(0.37)


def test_different_history_can_change_proposal_structure() -> None:
    empty = generate_proposals(
        observation=_obs(),
        store=SensorimotorStore(),
        config=SensorimotorConfig(),
        random_value=0.0,
    )
    trained = generate_proposals(
        observation=_obs(),
        store=_train(8),
        config=SensorimotorConfig(),
        random_value=0.0,
    )
    assert [item["source"] for item in empty["proposals"]] != [
        item["source"] for item in trained["proposals"]
    ]


def test_no_global_age_tick_or_memory_switch() -> None:
    empty = SensorimotorStore()
    trained = _train(8)
    late_unfamiliar = generate_proposals(
        observation=_obs(objects=[{
            "id": "OBJ-Z",
            "position": [1, 1],
            "relative_offset": [-1, -1],
            "cue_signature": "CUE-Z",
            "interaction_state": "FREE",
        }], actions=["PUSH:OBJ-Z:0,1", "WAIT"]),
        store=trained,
        config=SensorimotorConfig(),
        random_value=0.0,
    )
    assert late_unfamiliar["evidence"]["unknown"] is True or late_unfamiliar["quality"] < 0.35
    assert generate_proposals(
        observation=_obs(), store=empty, config=SensorimotorConfig(), random_value=0.0
    )["proposals"]


def test_reversal_weakens_and_can_stop_structuring() -> None:
    store = _train(8, displace_x=True)
    config = SensorimotorConfig()
    before = max(float(item["confidence"]) for item in store.contingencies.values())
    obs = _obs()
    for _ in range(8):
        remember_action(store, "PUSH:OBJ-X:4,2", obs)
        update_store(store, observation=_step_world(obs, "PUSH:OBJ-X:4,2", displace_x=False), config=config)
    after = max(float(item["confidence"]) for item in store.contingencies.values())
    assert after < before
    generated = generate_proposals(
        observation=_obs(), store=store, config=config, random_value=0.0
    )
    learned = [
        item
        for item in generated["proposals"]
        if item["source"] in {"LEARNED_SENSORIMOTOR", "BOTH"}
        and item["action"].startswith("PUSH:")
    ]
    assert after < 0.35 or not learned or generated["quality"] < before


def test_ablations_keep_same_generator_pathway() -> None:
    obs = _obs()
    both = generate_proposals(
        observation=obs,
        store=_train(6),
        config=SensorimotorConfig(endogenous_variation=True, learned_structuring=True),
        random_value=0.2,
    )
    endogenous_only = generate_proposals(
        observation=obs,
        store=_train(6),
        config=SensorimotorConfig(endogenous_variation=True, learned_structuring=False),
        random_value=0.2,
    )
    learned_only = generate_proposals(
        observation=obs,
        store=_train(6),
        config=SensorimotorConfig(endogenous_variation=False, learned_structuring=True),
        random_value=0.2,
    )
    assert both["evidence"]["budget"] == endogenous_only["evidence"]["budget"]
    assert all(item["source"] == "ENDOGENOUS_VARIATION" for item in endogenous_only["proposals"])
    assert learned_only["proposals"]


def test_predictable_object_is_not_automatically_preferred() -> None:
    store = _train(8)
    generated = generate_proposals(
        observation=_obs(),
        store=store,
        config=SensorimotorConfig(),
        random_value=0.0,
        values={"PUSH:OBJ-X:4,2": {"base_total": 0.0}, "WAIT": {"base_total": 0.0}},
    )
    chosen = select_proposal(generated, body={"energy_signal": 0.8}, random_value=0.0)
    assert chosen["reason"] != "PREFER_CONTROLLABLE"


def test_same_body_world_different_history_can_differ() -> None:
    obs = _obs()
    newborn = generate_proposals(
        observation=obs, store=SensorimotorStore(), config=SensorimotorConfig(), random_value=0.1
    )
    experienced = generate_proposals(
        observation=obs, store=_train(8), config=SensorimotorConfig(), random_value=0.1
    )
    assert newborn["evidence"]["unknown"] is True
    assert experienced["evidence"]["unknown"] is False or experienced["quality"] > newborn["quality"]
