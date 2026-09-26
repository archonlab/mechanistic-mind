"""Beta 3.1 optical → PSC competition counterexample search. Production path only."""
from __future__ import annotations

from experiments.run_beta31_optical_psc_counterexample import (
    base_obs,
    empty_history_control,
    evaluate_pair,
    mean_l1_q,
    optical_pairs,
    psc_off_on_protocol,
    run,
    set_surface,
    smc_optical_bound,
)
from mechanistic_mind.physical_system import sensorimotor_consequence as smc
from mechanistic_mind.research import prospective_composition as pr


def test_smc_optical_only_bound_below_threshold():
    b = smc_optical_bound()
    assert b["n_smc_channels"] == 48
    assert b["n_optical_surface_c"] == 9
    assert b["theoretical_quantized_max_mean_l1"] == 0.15
    assert abs(b["empirical_0_vs_1_quantized_mean_l1"] - 0.15) < 1e-12
    assert b["naive_raw_01_max_mean_l1"] == 9 / 48
    assert b["theoretical_quantized_max_mean_l1"] < smc.SIM_THRESHOLD
    assert b["SMC_ALWAYS_GENERALIZES_ACROSS_OPTICAL_ONLY_DIFFERENCES"] is True


def test_empty_history_fallback_independent_of_optics():
    pairs = optical_pairs()
    empty = empty_history_control(*pairs["high_sep_9ch"])
    assert empty["both_fallback"] is True
    assert empty["non_optical_diff_count"] == 0


def test_conditioned_history_winner_flip_production_path():
    pairs = optical_pairs()
    rec = evaluate_pair("high_sep_9ch", pairs["high_sep_9ch"][0], pairs["high_sep_9ch"][1],
                        "conditioned_separated", 8, 1, 1)
    assert rec["non_optical_diff_count"] == 0
    assert rec["order_invariance"] is True
    assert rec["level"] >= 3
    assert rec["winner_changed"] is True
    assert rec["win_x"] != rec["win_y"]
    assert rec["status_x"] == rec["status_y"] == "SELECTED"
    ox = set_surface(base_obs(), pairs["high_sep_9ch"][0])
    oy = set_surface(base_obs(), pairs["high_sep_9ch"][1])
    assert mean_l1_q(ox, oy) <= smc.SIM_THRESHOLD
    assert pr._frag_distance(pr._q(ox), pr._q(oy)) > pr.MATCH_TOL


def test_psc_off_on_protocol_preserves_flip():
    pairs = optical_pairs()
    off = psc_off_on_protocol(pairs["high_sep_9ch"][0], pairs["high_sep_9ch"][1], n=5)
    assert off["history_preserved"] is True
    assert off["non_optical_diff_count"] == 0
    assert off["level"] >= 3
    assert off["win_x"] != off["win_y"]


def test_search_classifications():
    art = run()
    cl = art["classifications"]
    assert cl["SMC_ALWAYS_GENERALIZES_ACROSS_OPTICAL_ONLY_DIFFERENCES"] == "YES"
    assert cl["OPTICAL_PSC_COUNTEREXAMPLE"] == "FOUND"
    assert cl["PSC_OPTICAL_SENSITIVITY_MAX_LEVEL"] >= 3
    assert cl["COUNTEREXAMPLE_SURVIVES_PSC_OFF_ON_PROTOCOL"] == "YES"
    assert art["empty_history"]["both_fallback"] is True
    assert art["integrity"]["GIT_PUSH"] == "NO"
    assert art["integrity"]["PSC_SEMANTICS_CHANGED"] == "NO"
