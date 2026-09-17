from mechanistic_mind.research import psyche_incubation as pi
from experiments.run_update438_psyche_incubation import run_seed


def test_clean_start_and_passive_learning_has_no_action_label():
    org = pi.empty_organism(17)
    assert pi.passive_prediction(org, "X4")["status"] == "NO_MATCH"
    pi.develop(org, exposures=12)
    assert org["external_count"] == 12
    assert all(row["cause"] == "EXTERNAL" for row in org["raw"])
    assert pi.passive_prediction(org, "X4")["predicted"] is not None
    assert org["forced_by_object"].get("X4", 0) == 0


def test_prediction_does_not_become_action_influence():
    learned = pi.empty_organism(23); pi.develop(learned, exposures=36)
    clean = pi.empty_organism(23)
    assert pi.passive_prediction(learned, "X4")["predicted"] is not None
    assert pi.action_distribution(learned, "X4")["probs"] == pi.action_distribution(clean, "X4")["probs"]
    assert pi.action_distribution(learned, "X4")["acquired_structure_contribution_to_logits"] == 0.0


def test_selective_ablations_and_raw_purge():
    org = pi.empty_organism(41); pi.develop(org, exposures=36)
    before = pi.passive_prediction(org, "X4")
    assert pi.purge_raw(org)["purged"] > 0
    assert pi.passive_prediction(org, "X4")["predicted"] == before["predicted"]
    assert pi.passive_prediction(pi.ablate_acquired(org), "X4")["predicted"] is None


def test_claim_boundary_and_semantic_audit():
    row = run_seed(59)
    assert row["claims"]["C1_passive_experience_acquisition"]
    assert row["claims"]["C5_passive_generalization"]
    assert not row["claims"]["C10_acquired_action_influence"]
    assert row["novel_exposure_audit_before_probe"]["interaction_exposure_count"] == 0
    assert row["leak"] == []


def test_memory_is_bounded():
    org = pi.empty_organism(83); pi.develop(org, exposures=500)
    snap = pi.memory_snapshot(org)
    assert snap["recent_buffer"] <= pi.MAX_RAW
    assert snap["provenance_size"] <= len(org["provenance"]) * pi.MAX_PROVENANCE
