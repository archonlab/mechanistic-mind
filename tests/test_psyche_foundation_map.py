from mechanistic_mind.psyche import FOUNDATION_MAP


def test_foundation_map_has_unique_candidate_roles():
    keys = [spec.mechanism_key for spec in FOUNDATION_MAP]
    assert len(keys) == len(set(keys))
    assert {
        "internal_regulation",
        "perception",
        "attention",
        "learning",
        "memory",
        "prediction",
        "prediction_error",
        "uncertainty",
        "goals",
        "global_modulation",
        "self_model",
        "habit",
        "valuation",
        "action_generation",
        "action_selection",
    } <= set(keys)


def test_foundation_map_does_not_claim_established_ontology():
    assert all(
        spec.status == "FOUNDATION_CANDIDATE"
        for spec in FOUNDATION_MAP
    )
