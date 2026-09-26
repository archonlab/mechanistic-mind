"""Beta 3.1 optical → PSC causal trace. Production functions only. No science change."""
from __future__ import annotations

from experiments.run_beta31_optical_to_psc import (
    base_obs,
    mean_l1_q,
    profile_x,
    profile_y,
    q5,
    q_smc,
    run,
    smc_sig,
    surface_only,
)
from mechanistic_mind.physical_system import sensorimotor_consequence as smc
from mechanistic_mind.research import predictive_compression as pc
from mechanistic_mind.research import prospective_composition as pr


def test_quantization_pairs_empirical():
    assert q5(0.10) != q5(0.50)
    assert q5(0.21) == q5(0.29) == 1
    assert q_smc(0.21) == q_smc(0.29)


def test_smc_aliases_pair_b_not_pair_a():
    a0, a1 = dict(base_obs()), dict(base_obs())
    a0["surface_c0_1"], a1["surface_c0_1"] = 0.10, 0.50
    b0, b1 = dict(base_obs()), dict(base_obs())
    b0["surface_c0_1"], b1["surface_c0_1"] = 0.21, 0.29
    ka = smc._sig_key(smc_sig(a0), "M", smc.SENSORY_CHANNELS)
    kb = smc._sig_key(smc_sig(a1), "M", smc.SENSORY_CHANNELS)
    k0 = smc._sig_key(smc_sig(b0), "M", smc.SENSORY_CHANNELS)
    k1 = smc._sig_key(smc_sig(b1), "M", smc.SENSORY_CHANNELS)
    assert ka != kb
    assert k0 == k1
    assert pc._sig(b0) != pc._sig(b1)


def test_multichannel_l1_vs_thresholds():
    x, y = profile_x(), profile_y()
    d = mean_l1_q(x, y)
    assert d <= smc.SIM_THRESHOLD
    assert d > pr.MATCH_TOL
    assert surface_only(x) != surface_only(y)


def test_harness_classifications_and_boundary():
    art = run()
    cl = art["classifications"]
    assert cl["SURFACE_C_REACHES_ACCESSIBLE_OBSERVATION"] == "YES"
    assert cl["SURFACE_C_REACHES_SMC"] == "YES"
    assert cl["SURFACE_C_REACHES_PE"] == "YES"
    assert cl["RAW_OPTICAL_DISTINCTIONS_SURVIVE_PE"] == "PARTIAL"
    assert cl["V3_PSC_OPTICAL_OBSERVABILITY"] == "PARTIAL"
    assert cl["PSC_CAN_USE_OPTICAL_HISTORY_ACCUMULATED_WHILE_OFF"] == "YES"
    diff = art["psc_candidate_diff"]
    assert diff["x"]["status"] == "SELECTED"
    assert diff["y"]["status"] == "SELECTED"
    assert diff["o_prime_optical_carry_distinct"] is True
    naive = art["naive_empty_history"]
    assert naive["x"]["compression_sig"] != naive["y"]["compression_sig"]
    assert art["mapping_sanity"]["CORRELATED"]["n_surface_c"] == 9
    assert art["v3_compact_obs_has_surface"] is True
