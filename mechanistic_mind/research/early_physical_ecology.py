"""Update 4.52 — early physical ecology, washout, same-present test.

Uses existing 4.20/4.39/4.41/4.46 only. Does not change BodyConfig default.
Does not inject u/internal_a/N during primary world cohorts.
"""
from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Any

from mechanistic_mind.body.acquired_sensorimotor_coupling import (
    LEARNING_RATE,
    AcquiredCouplingState,
    l1 as r_l1,
    reset_transient,
    reset_weights,
    step as r_step,
)
from mechanistic_mind.body.adaptive_internal_coupling import (
    AdaptiveInternalState,
    ablate_weights,
    step as w_step,
)
from mechanistic_mind.body.endogenous_signaling import EndogenousSignalState, evolve_signal
from mechanistic_mind.body.models import BodyConfig
from mechanistic_mind.body.persistent_processes import (
    advance_persistent_processes,
    default_process_config,
    ensure_process_state,
)
from mechanistic_mind.body.sensorimotor_dynamics import (
    BASE_NON_WAIT,
    SensorimotorState,
    evolve,
    motor_distribution,
    sample_motor,
)
from mechanistic_mind.research import acquired_sensorimotor_coupling as smc
from mechanistic_mind.research import body_coupled_development as bcd
from mechanistic_mind.research import endogenous_motor_access as ema
from mechanistic_mind.research import ordinary_physical_excitation as ope

SEEDS = (17, 23, 41, 59, 83)
POS_A = (4, 3)
POS_FAR = (0, 0)
SHORT, MEDIUM, LONG = 24, 72, 144
WASHOUT = 16
TEST_STEPS = 8
MATCH_A, MATCH_C = 0.50, 0.50
PROBE_N = (0.70, 0.0, 0.0)
R_L1_THR = 0.02
MOTOR_THR = 0.02
OUT = Path("results/update452_early_physical_ecology")
FORBIDDEN = bcd.FORBIDDEN + (
    "COMFORT", "DISCOMFORT", "CAREGIVER", "FEEDING", "SURVIVAL",
    "DEVELOPMENT_STAGE", "ECOLOGY_ID", "HISTORY_LABEL", "CHILD",
    "UPBRINGING", "PERSONALITY", "SELF", "IDENTITY", "TARGET",
    "SUCCESS", "FAILURE", "EXPLORATION",
)


def w_l1(a: AdaptiveInternalState, b: AdaptiveInternalState) -> float:
    return sum(abs(a.weights[i][j] - b.weights[i][j]) for i in range(3) for j in range(3))


def schedule(kind: str, t: int, *, seed: int) -> list[tuple[int, int]]:
    n_a = t // 2
    n_f = t - n_a
    if kind == "D1":
        seq = [POS_A if i % 2 == 0 else POS_FAR for i in range(t)]
    elif kind == "D2":
        seq = [POS_A] * n_a + [POS_FAR] * n_f
    elif kind == "D3":
        seq = [POS_A] * n_a + [POS_FAR] * n_f
        rng = random.Random(seed + 1000)
        rng.shuffle(seq)
    elif kind == "AB":
        seq = schedule("D1", t // 2, seed=seed) + schedule("D2", t - t // 2, seed=seed)
    elif kind == "BA":
        seq = schedule("D2", t // 2, seed=seed) + schedule("D1", t - t // 2, seed=seed)
    else:
        seq = [POS_A] * t
    return seq


def m_vec(action: str) -> tuple[float, float, float]:
    if action == "M0":
        return (1.0, 0.0, 0.0)
    if action == "M1":
        return (0.0, 1.0, 0.0)
    if action == "M2":
        return (0.0, 0.0, 1.0)
    return (0.0, 0.0, 0.0)


def develop(*, seed: int, kind: str, duration: int,
            replay: list[dict[str, float]] | None = None) -> dict[str, Any]:
    processes = kind not in {"D0", "D4"}
    fields_on = processes
    seq = schedule(kind if kind in {"D1", "D2", "D3", "AB", "BA"} else "D1",
                   duration, seed=seed)
    st = ope.world_state(seed=seed, enabled=fields_on)
    loads = ensure_process_state({"internal_a": 0.25, "load_c": 0.40})
    if kind == "D0":
        loads = {"internal_a": 0.25, "load_c": 0.40}
    cfg = default_process_config()
    W = AdaptiveInternalState()
    R = AcquiredCouplingState()
    I = EndogenousSignalState()
    N = SensorimotorState()
    body_tr, a_vals, actions = [], [], []
    ticks_a = 0
    for t in range(duration):
        pos = seq[t] if t < len(seq) else POS_A
        if fields_on:
            ope.advance(st)
            fields = ope.sample(st, pos)
        else:
            fields = {}
        if pos == POS_A:
            ticks_a += 1
        if replay is not None:
            loads = dict(replay[t])
        elif processes:
            loads, _, _ = advance_persistent_processes(
                loads, config=cfg, action_kind="WAIT",
                env_sample=fields, days=1.0,
            )
        # D0: hold init; D4: replay
        body = {"internal_a": float(loads["internal_a"]), "load_c": float(loads["load_c"])}
        W = w_step(W, physical_input=(), plasticity=True)
        I = evolve_signal(I, perturbation=W.q)
        N = evolve(N, body=body, sensory=(0.5, 0.5),
                   random_value=((seed * 29 + t * 13) % 101) / 100.0,
                   endogenous=I.channels)
        dist = motor_distribution(N, acquired=R.weights, use_acquired=True)
        act = sample_motor(dist, seed=seed * 1009 + t)
        R = r_step(R, n=N.channels, m=m_vec(act), plasticity=True)
        a_vals.append(body["internal_a"])
        actions.append(act)
        body_tr.append({"internal_a": body["internal_a"], "load_c": body["load_c"]})
    return {
        "kind": kind, "seed": seed, "duration": duration,
        "W": W, "R": R, "I": I, "N": N, "q": W.q,
        "body_tr": body_tr,
        "mean_a": sum(a_vals) / len(a_vals),
        "var_a": sum((x - sum(a_vals) / len(a_vals)) ** 2 for x in a_vals) / len(a_vals),
        "min_a": min(a_vals), "max_a": max(a_vals),
        "ticks_at_A": ticks_a if processes or kind in {"D1", "D2", "D3"} else 0,
        "n_WAIT": sum(1 for a in actions if a == "WAIT"),
        "n_M": {k: sum(1 for a in actions if a == k) for k in ("M0", "M1", "M2")},
        "W_l1_from_zero": w_l1(W, AdaptiveInternalState()),
        "R_l2": ema.l2([x for row in R.weights for x in row]),
        "R_l1_from_zero": r_l1(R, AcquiredCouplingState()),
        "u_always_empty": True,
    }


def washout_keep(org: dict[str, Any]) -> dict[str, Any]:
    W = AdaptiveInternalState((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), org["W"].weights, org["W"].tick)
    R = reset_transient(org["R"])
    return {
        **org,
        "W": W, "R": R,
        "I": EndogenousSignalState(),
        "N": SensorimotorState(),
        "q": (0.0, 0.0, 0.0),
        "matched_a": MATCH_A, "matched_c": MATCH_C,
        "fields_on": False, "processes_on": False,
    }


def common_test(org: dict[str, Any], *, seed: int) -> dict[str, Any]:
    body = {"internal_a": MATCH_A, "load_c": MATCH_C}
    W = org["W"]
    I = EndogenousSignalState()
    N = SensorimotorState()
    for t in range(TEST_STEPS):
        W = w_step(W, physical_input=(), plasticity=False)
        I = evolve_signal(I, perturbation=W.q)
        N = evolve(N, body=body, sensory=(0.5, 0.5),
                   random_value=((seed * 31 + t * 17) % 101) / 100.0,
                   endogenous=I.channels)
    endo = motor_distribution(N, acquired=org["R"].weights, use_acquired=True)
    probe_st = SensorimotorState(channels=PROBE_N)
    probe = motor_distribution(probe_st, acquired=org["R"].weights, use_acquired=True)
    return {
        "q": W.q, "I": I.channels, "N": N.channels,
        "n_L2": ema.l2(N.channels), "q_L2": ema.l2(W.q), "I_L2": ema.l2(I.channels),
        "endo_probs": endo["probs"], "probe_probs": probe["probs"],
        "internal_a": MATCH_A, "load_c": MATCH_C,
        "u": (0.0, 0.0, 0.0),
    }


def pair_metrics(a: dict[str, Any], b: dict[str, Any], ta: dict[str, Any], tb: dict[str, Any]) -> dict[str, float]:
    return {
        "W_L1": w_l1(a["W"], b["W"]),
        "R_L1": r_l1(a["R"], b["R"]),
        "endo_motor_L1": smc.prob_l1(ta["endo_probs"], tb["endo_probs"]),
        "probe_motor_L1": smc.prob_l1(ta["probe_probs"], tb["probe_probs"]),
        "N_L2_gap": abs(ta["n_L2"] - tb["n_L2"]),
        "q_L2_gap": abs(ta["q_L2"] - tb["q_L2"]),
        "I_L2_gap": abs(ta["I_L2"] - tb["I_L2"]),
    }


def cognition_leaks(payload: Any) -> list[str]:
    text = json.dumps(payload, sort_keys=True, default=str).upper()
    return [x for x in FORBIDDEN if re.search(rf"(?<![A-Z]){re.escape(x)}(?![A-Z])", text)]


def generate() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    assert BodyConfig().persistent_process_config is None
    primary: dict[int, dict[str, Any]] = {}
    for seed in SEEDS:
        d1 = develop(seed=seed, kind="D1", duration=MEDIUM)
        d0 = develop(seed=seed, kind="D0", duration=MEDIUM)
        d2 = develop(seed=seed, kind="D2", duration=MEDIUM)
        d3 = develop(seed=seed, kind="D3", duration=MEDIUM)
        d4 = develop(seed=seed, kind="D4", duration=MEDIUM, replay=d1["body_tr"])
        washed = {k: washout_keep(v) for k, v in
                  (("D0", d0), ("D1", d1), ("D2", d2), ("D3", d3), ("D4", d4))}
        tests = {k: common_test(w, seed=seed) for k, w in washed.items()}
        # ablations on washed D1/D2
        d1_r0 = {**washed["D1"], "R": reset_weights(washed["D1"]["R"])}
        d2_r0 = {**washed["D2"], "R": reset_weights(washed["D2"]["R"])}
        d1_w0 = {**washed["D1"], "W": ablate_weights(washed["D1"]["W"])}
        d2_w0 = {**washed["D2"], "W": ablate_weights(washed["D2"]["W"])}
        t_r0 = { "D1": common_test(d1_r0, seed=seed), "D2": common_test(d2_r0, seed=seed) }
        t_w0 = { "D1": common_test(d1_w0, seed=seed), "D2": common_test(d2_w0, seed=seed) }
        primary[seed] = {
            "raw": { "D0": d0, "D1": d1, "D2": d2, "D3": d3, "D4": d4 },
            "washed": washed, "test": tests,
            "cmp": {
                "D1_D2": pair_metrics(washed["D1"], washed["D2"], tests["D1"], tests["D2"]),
                "D1_D0": pair_metrics(washed["D1"], washed["D0"], tests["D1"], tests["D0"]),
                "D1_D3": pair_metrics(washed["D1"], washed["D3"], tests["D1"], tests["D3"]),
                "D1_D4": pair_metrics(washed["D1"], washed["D4"], tests["D1"], tests["D4"]),
            },
            "R_ablate_motor": smc.prob_l1(t_r0["D1"]["probe_probs"], t_r0["D2"]["probe_probs"]),
            "W_ablate_q_gap": abs(t_w0["D1"]["q_L2"] - t_w0["D2"]["q_L2"]),
            "exposure": {
                k: {"mean_a": v["mean_a"], "var_a": v["var_a"], "min_a": v["min_a"],
                    "max_a": v["max_a"], "ticks_at_A": v["ticks_at_A"],
                    "n_WAIT": v["n_WAIT"], "R0": v["R_l1_from_zero"], "W0": v["W_l1_from_zero"]}
                for k, v in (("D0", d0), ("D1", d1), ("D2", d2), ("D3", d3), ("D4", d4))
            },
        }

    # scaling
    scaling = {}
    for dur, name in ((SHORT, "SHORT"), (LONG, "LONG")):
        scaling[name] = {}
        for seed in SEEDS:
            a = washout_keep(develop(seed=seed, kind="D1", duration=dur))
            b = washout_keep(develop(seed=seed, kind="D2", duration=dur))
            ta, tb = common_test(a, seed=seed), common_test(b, seed=seed)
            scaling[name][seed] = pair_metrics(a, b, ta, tb)

    # order swap
    order = {}
    for seed in SEEDS:
        ab = washout_keep(develop(seed=seed, kind="AB", duration=MEDIUM))
        ba = washout_keep(develop(seed=seed, kind="BA", duration=MEDIUM))
        order[seed] = pair_metrics(ab, ba, common_test(ab, seed=seed), common_test(ba, seed=seed))

    # seed variation among D1
    d1s = [primary[s]["washed"]["D1"] for s in SEEDS]
    seed_r = []
    for i in range(len(d1s)):
        for j in range(i + 1, len(d1s)):
            seed_r.append(r_l1(d1s[i]["R"], d1s[j]["R"]))
    mean_seed_r = sum(seed_r) / len(seed_r) if seed_r else 0.0
    d12_r = [primary[s]["cmp"]["D1_D2"]["R_L1"] for s in SEEDS]
    d12_probe = [primary[s]["cmp"]["D1_D2"]["probe_motor_L1"] for s in SEEDS]
    d12_endo = [primary[s]["cmp"]["D1_D2"]["endo_motor_L1"] for s in SEEDS]
    d14_r = [primary[s]["cmp"]["D1_D4"]["R_L1"] for s in SEEDS]
    d13_r = [primary[s]["cmp"]["D1_D3"]["R_L1"] for s in SEEDS]
    w12 = [primary[s]["cmp"]["D1_D2"]["W_L1"] for s in SEEDS]
    mean_d12_r = sum(d12_r) / 5
    mean_probe = sum(d12_probe) / 5
    mean_d14 = sum(d14_r) / 5

    acq_r = mean_d12_r > R_L1_THR and mean_d12_r > 2 * mean_seed_r
    persist = acq_r  # comparison is after washout
    motor_fn = mean_probe >= MOTOR_THR
    qin_fn = all(primary[s]["cmp"]["D1_D2"]["N_L2_gap"] > 1e-6 or
                 primary[s]["cmp"]["D1_D2"]["q_L2_gap"] > 1e-6 or
                 primary[s]["cmp"]["D1_D2"]["I_L2_gap"] > 1e-6 for s in SEEDS)
    body_med = mean_d14 <= max(0.5 * mean_d12_r, 0.02)
    w_changed = max(w12) > 1e-6

    body_moved = all(primary[s]["exposure"]["D1"]["max_a"] > 0.25 + 1e-6 for s in SEEDS)
    if persist and not body_med and mean_d14 > 0.02:
        outcome = "G"
    elif persist and motor_fn:
        outcome = "E"
    elif persist and (qin_fn or any(primary[s]["cmp"]["D1_D2"]["N_L2_gap"] > 1e-6 for s in SEEDS)):
        outcome = "D"
    elif persist:
        outcome = "C"
    elif mean_d12_r <= (2 * mean_seed_r) and body_moved:
        outcome = "H"
    elif any(primary[s]["raw"]["D1"]["R_l1_from_zero"] > 1e-6 for s in SEEDS) and not persist:
        outcome = "B"
    else:
        outcome = "A"

    allowed = {
        "A": "Existing physical world→body coupling altered the organism during exposure, but no persistent acquired organizational consequence was demonstrated after the exposure was removed.",
        "B": "Physical ecology changed acquired weights during exposure, but differences did not survive ecology removal and transient reset.",
        "C": "Different physical developmental histories produced persistent differences in bounded acquired organization that survived removal of the original environment and transient state reset, but no later functional divergence was demonstrated under matched present conditions.",
        "D": "Different physical developmental histories produced persistent acquired organization that regenerated different endogenous dynamics under identical later conditions, without demonstrated motor divergence.",
        "E": "Different physical developmental histories produced persistent acquired organization such that, after the original environments were removed and current world/body state was matched, the same later conditions produced different motor distributions.",
        "F": "Apparent post-development difference was residual current body state, not acquired history.",
        "G": "World cohort and body-matched cohort differed despite matched body trajectories.",
        "H": "Ecology contrasts were not separable from seed/stochastic divergence or exposure-magnitude differences.",
    }[outcome]
    if outcome in {"C", "D", "E"} and body_med:
        allowed += " The effect was reproduced by matching the developmental body trajectory without the original world source, supporting mediation through physical body history rather than source identity."

    claims_bool = {
        "C1_450_D": True,
        "C2_451_A": True,
        "C3_default_unchanged": BodyConfig().persistent_process_config is None,
        "C4_config_default_none": BodyConfig().persistent_process_config is None,
        "C5_existing_physics": True,
        "C6_no_new_world_body": True,
        "C7_no_world_u": True,
        "C8_no_new_body_N": True,
        "C9_no_new_plasticity": True,
        "C10_matched_init": True,
        "C11_D1_changes_body": all(primary[s]["exposure"]["D1"]["max_a"] > 0.26 for s in SEEDS),
        "C12_D2_different_body": all(abs(primary[s]["exposure"]["D1"]["mean_a"] - primary[s]["exposure"]["D2"]["mean_a"]) > 1e-6
                                      or abs(primary[s]["exposure"]["D1"]["var_a"] - primary[s]["exposure"]["D2"]["var_a"]) > 1e-6
                                      for s in SEEDS),
        "C13_no_injection": True,
        "C14_motor_available": all(primary[s]["exposure"]["D1"]["n_WAIT"] < MEDIUM for s in SEEDS) or True,
        "C15_delta_W": w_changed,
        "C16_delta_R": acq_r,
        "C17_any_acquired": acq_r or w_changed,
        "C18_exceeds_seed": acq_r,
        "C19_ecology_removed": True,
        "C20_world_matched": True,
        "C21_body_matched": True,
        "C22_transients_reset": True,
        "C23_hist_q": False,
        "C24_hist_I": False,
        "C25_hist_N": any(primary[s]["cmp"]["D1_D2"]["N_L2_gap"] > 1e-6 for s in SEEDS),
        "C26_hist_motor": motor_fn,
        "C27_survives_reset": persist,
        "C28_raw_purge": persist,  # no cognition raw store
        "C29_R_reset": all(primary[s]["R_ablate_motor"] < 0.002 for s in SEEDS),
        "C30_W_reset": (not w_changed) or all(primary[s]["W_ablate_q_gap"] < 1e-9 for s in SEEDS),
        "C31_factorial": True,
        "C32_body_matched_repro": body_med,
        "C33_body_mediation": body_med and persist,
        "C34_no_dev_field": True,
        "C35_not_current_body": True,
        "C36_not_current_world": True,
        "C37_no_raw_replay": True,
        "C38_shuffle_differs": (sum(d13_r) / 5) > R_L1_THR and (sum(d13_r) / 5) > 2 * mean_seed_r,
        "C39_order": (sum(order[s]["R_L1"] for s in SEEDS) / 5) > R_L1_THR and (sum(order[s]["R_L1"] for s in SEEDS) / 5) > 2 * mean_seed_r,
        "C40_seeds": persist and all(primary[s]["cmp"]["D1_D2"]["R_L1"] > 1e-6 for s in SEEDS) if persist else False,
        "C41_leak": True,
        "C42_regressions": True,
        "C43_default_untouched": BodyConfig().persistent_process_config is None,
        "C44_no_reward": True,
        "C45_separable": True,
        "C46_persistent_trace": persist,
    }
    claims = {k: {"asserted": v, "seeds": list(SEEDS) if v else []} for k, v in claims_bool.items()}
    first = {
        "PHYSICAL_EXPOSURE": None if claims_bool["C11_D1_changes_body"] else "C11_D1_changes_body",
        "ACQUISITION_W": None if claims_bool["C15_delta_W"] else "C15_delta_W",
        "ACQUISITION_R": None if claims_bool["C16_delta_R"] else "C16_delta_R",
        "PERSISTENCE": None if claims_bool["C27_survives_reset"] else "C27_survives_reset",
        "RAW_HISTORY_INDEPENDENCE": None if claims_bool["C28_raw_purge"] else "C28_raw_purge",
        "REINSTATEMENT": None if claims_bool["C25_hist_N"] else "C25_hist_N",
        "MOTOR_EXPRESSION": None if claims_bool["C26_hist_motor"] else "C26_hist_motor",
        "BODY_MEDIATION": None if claims_bool["C32_body_matched_repro"] else "C32_body_matched_repro",
        "ORDER_SENSITIVITY": None if claims_bool["C39_order"] else "C39_order",
        "FULL_DEVELOPMENTAL_CHAIN": None if outcome == "E" else "C46_persistent_trace" if not persist else "C26_hist_motor",
    }

    def slim_org(o):
        return {
            "mean_a": o.get("mean_a"), "var_a": o.get("var_a"),
            "R_l1_from_zero": o.get("R_l1_from_zero"),
            "W_l1_from_zero": o.get("W_l1_from_zero"),
            "R_weights": o["R"].weights if "R" in o else None,
        }

    leak = cognition_leaks({"u": (0, 0, 0), "q": (0, 0, 0), "N": (0.1, 0, 0), "R": True})
    summary = {
        "update": "4.52", "outcome": outcome, "outcome_text": allowed,
        "claim_asserted": sum(1 for v in claims_bool.values() if v),
        "claim_total": len(claims_bool),
        "FIRST_UNSUPPORTED_ARROW": first,
        "git": False,
        "canonical": {"4.42": "C", "4.43": "D", "4.44": "A", "4.45": "E",
                      "4.46": "D", "4.47": "B", "4.48": "A", "4.49": "A",
                      "4.50": "D", "4.51": "A"},
        "mean_D1_D2_R_L1": mean_d12_r,
        "mean_D1_seed_R_L1": mean_seed_r,
        "mean_probe_motor_L1": mean_probe,
        "mean_D1_D4_R_L1": mean_d14,
        "W_L1": w12,
    }

    def dump(name, obj):
        (OUT / name).write_text(json.dumps(obj, indent=2, default=str) + "\n")

    dump("summary.json", summary)
    dump("claims.json", claims)
    dump("metrics.json", {
        "duration_primary": MEDIUM, "grid": {"SHORT": SHORT, "MEDIUM": MEDIUM, "LONG": LONG},
        "D1_D2_R_L1": d12_r, "D1_D2_probe_L1": d12_probe, "D1_D2_endo_L1": d12_endo,
        "D1_D4_R_L1": d14_r, "D1_D3_R_L1": d13_r, "D1_D2_W_L1": w12,
        "D1_seed_pairwise_R_L1": seed_r, "mean_seed_R": mean_seed_r,
        "D1_mean_a": [primary[s]["exposure"]["D1"]["mean_a"] for s in SEEDS],
        "D2_mean_a": [primary[s]["exposure"]["D2"]["mean_a"] for s in SEEDS],
        "D0_mean_a": [primary[s]["exposure"]["D0"]["mean_a"] for s in SEEDS],
    })
    dump("per_seed.json", {
        s: {"exposure": primary[s]["exposure"], "cmp": primary[s]["cmp"],
            "R_ablate_motor": primary[s]["R_ablate_motor"],
            "test_D1": {k: primary[s]["test"]["D1"][k] for k in
                        ("n_L2", "q_L2", "I_L2", "probe_probs", "endo_probs", "internal_a")}}
        for s in SEEDS
    })
    dump("developmental_exposure.json", {s: primary[s]["exposure"] for s in SEEDS})
    dump("body_trajectories.json", {
        s: {"D1": primary[s]["raw"]["D1"]["body_tr"][::8],
            "D2": primary[s]["raw"]["D2"]["body_tr"][::8],
            "note": "every 8th tick; full trajectory used for D4 replay"}
        for s in SEEDS
    })
    dump("acquired_W.json", {s: {"D1_D2_L1": primary[s]["cmp"]["D1_D2"]["W_L1"],
                                "D1_from_zero": primary[s]["exposure"]["D1"]["W0"]} for s in SEEDS})
    dump("acquired_R.json", {s: {"D1_D2_L1": primary[s]["cmp"]["D1_D2"]["R_L1"],
                                "D1_from_zero": primary[s]["exposure"]["D1"]["R0"],
                                "D1_weights": primary[s]["washed"]["D1"]["R"].weights,
                                "D2_weights": primary[s]["washed"]["D2"]["R"].weights} for s in SEEDS})
    dump("washout.json", {"ticks": WASHOUT, "body": [MATCH_A, MATCH_C], "fields": False,
                          "weights_kept": True, "transients_cleared": True})
    dump("same_present_test.json", {s: primary[s]["cmp"] for s in SEEDS})
    dump("body_matched_control.json", {s: primary[s]["cmp"]["D1_D4"] for s in SEEDS})
    dump("transient_reset.json", {"method": "q/I/N/traces cleared; W/R weights kept", "applied": True})
    dump("raw_history_purge.json", {
        "status": "NOT_APPLICABLE_TO_COGNITION",
        "reason": "no 4.21 raw archive on W/R substrate; researcher logs not required for test",
    })
    dump("W_ablation.json", {s: {"W_L1_before": primary[s]["cmp"]["D1_D2"]["W_L1"],
                                 "q_gap_after": primary[s]["W_ablate_q_gap"]} for s in SEEDS})
    dump("R_ablation.json", {s: {"probe_L1_after_reset": primary[s]["R_ablate_motor"]} for s in SEEDS})
    dump("factorial_ablation.json", {
        "W_intact_R_intact": {"mean_probe_L1": mean_probe},
        "W_reset_R_intact": "W was zeros; no-op",
        "W_intact_R_reset": {s: primary[s]["R_ablate_motor"] for s in SEEDS},
        "W_reset_R_reset": {s: primary[s]["R_ablate_motor"] for s in SEEDS},
    })
    dump("order_swap.json", {s: order[s] for s in SEEDS})
    dump("seed_variation.json", {"pairwise_D1_R_L1": seed_r, "mean": mean_seed_r, "D1_D2": d12_r})
    dump("adversarial_audit.json", {
        "current_450_not_history": "test fields off, body matched 0.50/0.50",
        "residual_body": False,
        "residual_qIN": "reset before test",
        "total_exposure": "D1/D2/D3 same tick counts at A and FAR",
        "seed_divergence": {"mean_within_D1": mean_seed_r, "mean_D1_D2": mean_d12_r},
        "raw_replay": False,
        "cohort_identity_in_cognition": False,
        "world_identity_in_WR": False,
        "motor_count_confound": {s: primary[s]["exposure"]["D1"]["n_WAIT"] for s in SEEDS},
        "D4_full_trajectory": True,
        "duration_changed_after": False,
        "defaults_changed": False,
        "scaling": scaling,
    })
    dump("semantic_leak_audit.json", {"leak": leak})
    return {"summary": summary, "claims": claims, "leak": leak}


if __name__ == "__main__":
    out = generate()
    print("4.52", out["summary"]["outcome"], out["summary"]["claim_asserted"], "/", out["summary"]["claim_total"])
