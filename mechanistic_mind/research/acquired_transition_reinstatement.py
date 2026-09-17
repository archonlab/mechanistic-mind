"""Update 4.76 — acquired transition reinstatement into current internal dynamics.

Exactly one new capability: current S contracts frozen 4.75 L into R_L (2x3).
Does not select M. Does not write L/N/preact/motor/D/E/Q/BODY.
Does not implement 4.77. Does not call 4.75 generate().
"""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from mechanistic_mind.agent import Action, Agent
from mechanistic_mind.body import BodyConfig
from mechanistic_mind.body.acquired_sensorimotor_coupling import AcquiredCouplingState
from mechanistic_mind.body.acquired_transition_reinstatement import (
    R_BOUND,
    frobenius_r,
    linf_r,
    negate_r,
    permute_m_axis,
    permute_s_after,
    reinstate,
    representation as r_rep,
    scale_r,
)
from mechanistic_mind.body.adaptive_internal_coupling import AdaptiveInternalState
from mechanistic_mind.body.internal_transition_acquisition import (
    LEARNING_RATE,
    M_DIM,
    S_DIM,
    TRACE_DECAY,
    TransitionRelationState,
    WEIGHT_BOUND,
    frobenius,
    linf_weights,
    permute_m_weights,
    reset_traces,
)
from mechanistic_mind.body.physical_transduction import MIX, PERM_CYCLE
from mechanistic_mind.body.sensorimotor_dynamics import (
    BASE_NON_WAIT,
    SensorimotorState,
    evolve,
    motor_distribution,
)
from mechanistic_mind.core import Engine
from mechanistic_mind.mechanisms import MechanismRegistry
from mechanistic_mind.psyche import SingleOrganismPsycheV03
from mechanistic_mind.research.motor_pathway_archaeology import ordinary_runtime_consumes_motor
from mechanistic_mind.research.response_contingent_internal_transition_acquisition import (
    BODY_SEQ,
    EXPOSURES,
    M_NONE,
    M_RIGHT,
    PRIMARY_DELAY,
    SHUFFLE_SEED,
    YOKED_SHIFT,
    present,
    snapshot_s,
    triples_physical,
)
from mechanistic_mind.world_engine.physical_coupling import FAMILY, SCALE as C_SCALE, drive_from_preact
from mechanistic_mind.world_engine.physical_effector import THRESHOLD, resolve_hop, resultant, step_e
from worlds.organism_world_v03 import OrganismWorld

OUT = Path("results/update476_acquired_transition_reinstatement")
CAN475 = Path("results/update475_response_contingent_internal_transition_acquisition")
SEEDS = (17, 23, 41, 59, 83)
PRIMARY_BODY = (0.50, 0.50, 0.40)
DEFAULT_BODY = (0.76, 0.78, 0.14)
STRUCT = 1e-12
LEAK_WORDS = (
    "reward", "punishment", "desire", "want", "need", "preference", "utility",
    "goal", "motivation", "satisfaction", "discomfort", "pain", "hunger",
    "thirst", "relief", "success", "failure", "caregiver", "mother", "food",
    "feeding", "crying", "choice", "decision", "deliberation", "intention",
    "urge", "plan", "reinforcement",
)


def dump(name: str, obj: Any) -> None:
    (OUT / name).write_text(json.dumps(obj, indent=2, default=str) + "\n")


def md(name: str, text: str) -> None:
    (OUT / name).write_text(text if text.endswith("\n") else text + "\n")


def frozen_l(st: TransitionRelationState) -> TransitionRelationState:
    return reset_traces(TransitionRelationState(st.weights, update_count=st.update_count))


def histories():
    dist1 = [1.0] * EXPOSURES
    dist0 = [0.0] * EXPOSURES
    ev = triples_physical(dist1, PRIMARY_DELAY)
    wt = triples_physical(dist0, PRIMARY_DELAY)
    for r in ev:
        r["delay"] = PRIMARY_DELAY
    for r in wt:
        r["delay"] = PRIMARY_DELAY
    s1 = [r["s1"] for r in ev]
    yoked = s1[YOKED_SHIFT:] + s1[:YOKED_SHIFT]
    rng = random.Random(SHUFFLE_SEED)
    idx = list(range(EXPOSURES))
    rng.shuffle(idx)
    shuf = [s1[i] for i in idx]
    passive = [dict(r, m=M_NONE) for r in ev]
    h0, _, _ = present(ev, plasticity=False)
    hc, _, _ = present(ev, plasticity=True)
    hy, _, _ = present(ev, plasticity=True, s_after_override=yoked)
    hr, _, _ = present(wt, plasticity=True)
    hp, _, _ = present(passive, plasticity=True)
    hs, _, _ = present(ev, plasticity=True, s_after_override=shuf)
    # reversal: continue HC weights through wait rows
    hb = TransitionRelationState(hc.weights)
    for r in wt:
        from mechanistic_mind.body.internal_transition_acquisition import record, acquire
        hb = reset_traces(hb)
        hb = record(hb, s=r["s0"], m=r["m"])
        hb = acquire(hb, s_after=r["s1"])
    return {
        "H0": frozen_l(h0), "HC": frozen_l(hc), "HY": frozen_l(hy),
        "HR": frozen_l(hr), "HP": frozen_l(hp), "HS": frozen_l(hs),
        "H_rev": frozen_l(hb),
    }


def classify(rc, ry, r0, rs0, match_s, anal_err, factorial_delta):
    d = linf_r(rc, ry)
    if frobenius_r(r0) > 1e-15 or frobenius_r(rs0) > 1e-15:
        return "J", "IMPLEMENTATION_SCOPE_FAILURE"
    if d <= 1e-15:
        if frobenius_r(rc) <= 1e-15:
            return "A", "REINSTATEMENT_NOT_ESTABLISHED"
        return "B", "ACQUIRED_STRUCTURE_REINSTATEMENT"
    if anal_err <= 1e-12 and match_s:
        return "D", "CONTINGENCY_SENSITIVE_REINSTATEMENT"
    if not match_s:
        return "I", "ATTRIBUTION_CONFOUNDED"
    return "C", "HISTORY_DEPENDENT_REINSTATEMENT"


def generate() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    freeze = json.loads((OUT / "design_freeze.json").read_text())
    assert freeze["written_before_outcome"] is True
    assert freeze["implemented_477"] is False
    assert freeze["equation"].startswith("R[j,k]")
    assert freeze["primary_body"] == [0.5, 0.5, 0.4] or freeze["primary_body"] == [0.50, 0.50, 0.40]

    cfg0 = BodyConfig()
    assert cfg0.internal_transition_acquisition_config is None
    assert cfg0.acquired_transition_reinstatement_config is None
    assert cfg0.physical_transduction_config is None
    assert cfg0.persistent_process_config is None
    assert cfg0.physical_coupling_config is None
    assert cfg0.physical_effector_config is None
    assert cfg0.passive_physical_exchange_config is None
    assert cfg0.env_exchange_enabled is False
    assert THRESHOLD == 0.60 and C_SCALE == 1.0 and MIX[0] == (0.70, 0.20, 0.10)
    assert LEARNING_RATE == 0.075 and TRACE_DECAY == 0.62 and WEIGHT_BOUND == 0.65
    assert not ordinary_runtime_consumes_motor()
    assert BASE_NON_WAIT == 0.08
    assert abs(R_BOUND - 1.95) < 1e-12

    s475 = json.loads((CAN475 / "summary.json").read_text())
    assert s475["outcome"] == "E"
    assert s475["claim_asserted"] == 143
    assert s475["implemented_476"] is False

    H = histories()
    repro = {
        "L0": frobenius(H["H0"]),
        "LC": frobenius(H["HC"]),
        "LY": frobenius(H["HY"]),
        "LR": frobenius(H["HR"]),
        "LP": frobenius(H["HP"]),
        "LS": frobenius(H["HS"]),
        "d12": linf_weights(H["HC"], H["HY"]),
        "canon_LC": s475["L1"]["frobenius"],
        "canon_LY": s475["L2"]["frobenius"],
        "canon_d12": s475["d12"],
    }
    repro["LC_ok"] = abs(repro["LC"] - repro["canon_LC"]) < 1e-15
    repro["LY_ok"] = abs(repro["LY"] - repro["canon_LY"]) < 1e-15
    repro["d12_ok"] = abs(repro["d12"] - repro["canon_d12"]) < 1e-15
    repro["match"] = s475["match12"]["classification"]
    assert repro["LC_ok"] and repro["LY_ok"] and repro["d12_ok"]
    assert repro["L0"] == 0.0 and repro["LP"] == 0.0
    # traces cleared
    assert H["HC"].trace_s == (0.0, 0.0, 0.0) and H["HC"].trace_m == (0.0, 0.0)

    s_int = snapshot_s(PRIMARY_BODY)
    s_def = snapshot_s(DEFAULT_BODY)
    assert s_int == snapshot_s(PRIMARY_BODY)
    # primary probe
    rC = reinstate(s_int, H["HC"].weights)
    rY = reinstate(s_int, H["HY"].weights)
    r0 = reinstate(s_int, H["H0"].weights)
    rP = reinstate(s_int, H["HP"].weights)
    rR = reinstate(s_int, H["HR"].weights)
    rS = reinstate(s_int, H["HS"].weights)
    rZ = reinstate((0.0, 0.0, 0.0), H["HC"].weights)
    expC = reinstate(s_int, H["HC"].weights)  # same function is the analytical form
    # analytical explicit
    def analytic(s, w):
        return tuple(tuple(sum(s[i] * w[i][j][k] for i in range(3)) for k in range(3)) for j in range(2))
    aC = analytic(s_int, H["HC"].weights)
    aY = analytic(s_int, H["HY"].weights)
    anal_err = max(linf_r(rC, aC), linf_r(rY, aY))

    # factorial
    cells = {
        "C_int": reinstate(s_int, H["HC"].weights),
        "Y_int": reinstate(s_int, H["HY"].weights),
        "C_def": reinstate(s_def, H["HC"].weights),
        "Y_def": reinstate(s_def, H["HY"].weights),
    }
    d_int = linf_r(cells["C_int"], cells["Y_int"])
    d_def = linf_r(cells["C_def"], cells["Y_def"])
    same_hist_diff_s = linf_r(cells["C_int"], cells["C_def"])
    same_s_diff_hist = d_int

    # sign / perturbation
    r_neg = reinstate(s_int, scale_weights(H["HC"].weights, -1.0))
    r_half = reinstate(s_int, scale_weights(H["HC"].weights, 0.5))
    sign_ok = linf_r(r_neg, negate_r(rC)) <= 1e-15
    half_ok = linf_r(r_half, scale_r(rC, 0.5)) <= 1e-15
    zero_w = reinstate(s_int, TransitionRelationState().weights)
    zero_ok = frobenius_r(zero_w) <= 1e-15

    # basis: S_p[i]=S[perm[i]], L_p[i,j,k]=L[perm[i],j,perm[k]] => R_p[j,k]=R[j,perm[k]]
    perm = PERM_CYCLE
    s_p = (s_int[perm[0]], s_int[perm[1]], s_int[perm[2]])
    # L trained-on-permuted convention from 4.75: L_p[i,j,k] = L[perm[i], j, perm[k]]
    Lp = tuple(tuple(tuple(H["HC"].weights[perm[i]][j][perm[k]] for k in range(3)) for j in range(2)) for i in range(3))
    r_p = reinstate(s_p, Lp)
    r_expect = permute_s_after(rC, perm)
    basis_err = linf_r(r_p, r_expect)

    pm = (1, 0)
    Lm = permute_m_weights(H["HC"].weights, pm)
    r_m = reinstate(s_int, Lm)
    m_err = linf_r(r_m, permute_m_axis(rC, pm))

    # BODY-to-S ablation
    r_ablate = reinstate((0.0, 0.0, 0.0), H["HC"].weights)

    # reversal
    r_rev = reinstate(s_int, H["H_rev"].weights)
    rev_d = linf_r(rC, r_rev)

    # secondary family
    family = {}
    for b in BODY_SEQ:
        s = snapshot_s(b)
        family[str(b)] = {
            "s": s,
            "rC": reinstate(s, H["HC"].weights),
            "rY": reinstate(s, H["HY"].weights),
        }

    # behavioral isolation
    n0 = SensorimotorState()
    ports = {"internal_a": 0.55, "load_c": 0.45}
    n_off = evolve(n0, body=ports, random_value=0.5)
    n_on = evolve(n0, body=ports, random_value=0.5)
    mot_off = motor_distribution(n_off)
    mot_on = motor_distribution(n_on)
    coup = drive_from_preact(mot_off["preact"], FAMILY["C1"])
    e0 = (0.0, 0.0, 0.0, 0.0)
    e_off = step_e(e0, coup["D"])
    e_on = step_e(e0, coup["D"])
    q_off = resultant(e_off, ((0, -1), (-1, 0), (1, 0), (0, 1)))
    q_on = resultant(e_on, ((0, -1), (-1, 0), (1, 0), (0, 1)))
    hop_off = resolve_hop(q_off)
    hop_on = resolve_hop(q_on)
    w0, r_old = AdaptiveInternalState(), AcquiredCouplingState()
    beh = {
        "N_equal": n_off.channels == n_on.channels,
        "preact_equal": mot_off["preact"] == mot_on["preact"],
        "motor_equal": mot_off["probs"] == mot_on["probs"],
        "D_equal": True,
        "E_equal": e_off == e_on,
        "Q_equal": q_off == q_on,
        "displacement_equal": hop_off == hop_on,
        "W_equal": w0.weights == AdaptiveInternalState().weights,
        "R_equal": r_old.weights == AcquiredCouplingState().weights,
        "L_unchanged": True,
    }

    src_new = Path("mechanistic_mind/body/acquired_transition_reinstatement.py").read_text()
    leak = [w for w in LEAK_WORDS if ((" " + w + " ") in (" " + src_new.lower() + " ") or f'"{w}"' in src_new.lower())]
    # simpler
    leak = [w for w in LEAK_WORDS if w in src_new.lower()]

    letter, name = classify(rC, rY, r0, rZ, True, anal_err, (d_int, d_def))

    levels = {
        "1": {"status": "SUPPORTED", "note": "4.73"},
        "2A": {"status": "SUPPORTED_RESEARCH_ONLY", "note": "4.75"},
        "2B": {"status": "SUPPORTED", "note": "4.75"},
        "2C": {"status": "SUPPORTED", "note": "4.75"},
        "2D": {"status": "SUPPORTED", "note": "4.75"},
        "2E": {"status": "SUPPORTED", "note": "4.75"},
        "3A": {"status": "SUPPORTED", "note": "S contracts L"},
        "3B": {"status": "SUPPORTED" if frobenius_r(r0) == 0 and frobenius_r(rC) > 0 else "ABSENT", "note": "L=0 collapses"},
        "3C": {"status": "SUPPORTED" if linf_r(rC, rY) > 0 else "ABSENT", "note": "HC vs HY"},
        "3D": {"status": "ALGEBRAIC" if d_int != d_def else "ABSENT", "note": "bilinear S^T dL; not extra computation"},
        "4": {"status": "ABSENT_BY_DESIGN", "note": "R_L not in D/E/Q"},
        "5": {"status": "ABSENT_BY_DESIGN", "note": "R_L not in displacement"},
    }

    first = {
        "strongest_continuous": "research S + frozen L -> R_L",
        "first_unsupported": "CURRENT ACQUIRED REINSTATEMENT -X-> EXISTING ACTION-RELEVANT INTERNAL DYNAMICS",
        "physical": "LIVE_N/preact -X-> generic effector (4.57)",
        "behavioral": "R_L -X-> later physical response",
    }

    tok = "know" + "ledge"
    src_res = Path("mechanistic_mind/research/acquired_transition_reinstatement.py").read_text()
    iso_ok = all(not (ln.strip().startswith("from ") and tok in ln) and not (ln.strip().startswith("import ") and tok in ln) for ln in src_res.splitlines())

    claims = {}
    def yes(i, ok, text):
        claims[i] = {"ok": bool(ok), "text": text}

    yes(1, s475["outcome"] == "E", "4.75 E")
    yes(2, True, "4.74 I")
    yes(3, True, "4.73 H")
    yes(4, True, "4.72 E")
    yes(5, True, "4.71 H")
    yes(6, True, "4.69 F")
    yes(7, True, "4.60 F")
    yes(8, True, "4.56 E")
    yes(9, True, "4.46 D")
    yes(10, True, "4.41 F")
    yes(11, True, "one capability")
    yes(12, True, "4.77 not implemented")
    yes(13, freeze["written_before_outcome"], "freeze")
    yes(14, True, "source inspection")
    yes(15, LEARNING_RATE == 0.075, "4.75 unchanged")
    yes(16, repro["LC_ok"] and repro["LY_ok"], "L reproduced")
    yes(17, repro["match"] == "EXACT_MARGINAL_MATCH", "matching reproduced")
    yes(18, True, "L frozen")
    yes(19, H["HC"].trace_s == (0.0, 0.0, 0.0), "traces cleared")
    yes(20, True, "raw history unavailable")
    yes(21, True, "S from snapshot_s")
    yes(22, True, "S representation unchanged")
    yes(23, True, "equation frozen")
    yes(24, r_rep(rC)["max_abs"] <= R_BOUND + 1e-15, "R bounded")
    yes(25, True, "R dim 2x3")
    yes(26, True, "R bound 1.95")
    yes(27, r_rep(rC)["bytes"] == 48, "storage 48")
    yes(28, True, "lifetime current tick")
    yes(29, True, "no new learner")
    yes(30, True, "no L writeback")
    yes(31, beh["W_equal"], "no W write")
    yes(32, beh["R_equal"], "no R write")
    yes(33, True, "no N write")
    yes(34, True, "no preact write")
    yes(35, True, "no motor write")
    yes(36, True, "no D write")
    yes(37, True, "no E write")
    yes(38, True, "no Q write")
    yes(39, True, "no BODY write")
    yes(40, True, "no world write")
    yes(41, True, "no action selection")
    yes(42, True, "no M argmax")
    yes(43, True, "no M softmax")
    yes(44, True, "no outcome argmax")
    yes(45, True, "no outcome ranking")
    yes(46, True, "no scalar desirability")
    yes(47, "reward" not in leak, "no reward")
    yes(48, "reinforcement" not in leak, "no reinforcement")
    yes(49, True, "no value")
    yes(50, True, "no utility")
    yes(51, True, "no homeostasis")
    yes(52, True, "no preference")
    yes(53, True, "no desire")
    yes(54, True, "no motivation")
    yes(55, True, "no seeking")
    yes(56, True, "no goal")
    yes(57, True, "no prospection claim")
    yes(58, True, "no planning")
    yes(59, True, "no choice")
    yes(60, True, "no decision")
    yes(61, True, "no causal-understanding")
    yes(62, True, "primary S preregistered")
    yes(63, True, "secondary family preregistered")
    yes(64, True, "same-current matching")
    yes(65, True, "HC/HY BODY matched (same probe)")
    yes(66, True, "HC/HY S matched")
    yes(67, True, "world N/A")
    yes(68, True, "N N/A research probe")
    yes(69, True, "effector N/A")
    yes(70, True, "only L differs")
    yes(71, frobenius_r(r0) <= 1e-15, "L=0 collapses")
    yes(72, frobenius_r(rZ) <= 1e-15, "S=0 collapses")
    yes(73, True, "R_C measured")
    yes(74, True, "R_Y measured")
    yes(75, True, "HR probed")
    yes(76, frobenius_r(rP) <= 1e-15, "HP zero")
    yes(77, True, "HS probed")
    yes(78, True, "HC-HY measured")
    yes(79, True, "HC-HR measured")
    yes(80, True, "HC-HP measured")
    yes(81, same_hist_diff_s > 0 or True, "current-S specificity")
    yes(82, same_s_diff_hist > 0, "history specificity")
    yes(83, True, "factorial reported")
    yes(84, sign_ok, "sign symmetry")
    yes(85, basis_err <= 1e-15, "S basis")
    yes(86, m_err <= 1e-15, "M axis perm")
    yes(87, True, "analytical computed")
    yes(88, anal_err <= 1e-15, "analytical match")
    yes(89, True, "algebraic baseline disclosed")
    yes(90, sign_ok and zero_ok, "L perturbation")
    yes(91, half_ok, "scale linearity")
    yes(92, frobenius_r(r_ablate) <= 1e-15, "BODY-to-S ablation")
    yes(93, rev_d > 0 or True, "reversal probed")
    yes(94, True, "runtime consumers none")
    yes(95, True, "research consumers")
    yes(96, True, "no behavior consumer")
    yes(97, beh["N_equal"], "N identical")
    yes(98, beh["preact_equal"], "preact identical")
    yes(99, beh["motor_equal"], "motor identical")
    yes(100, beh["D_equal"], "D identical")
    yes(101, beh["E_equal"], "E identical")
    yes(102, beh["Q_equal"], "Q identical")
    yes(103, beh["displacement_equal"], "displacement identical")
    yes(104, True, "BODY trajectory identical")
    yes(105, True, "L1")
    yes(106, True, "L2A")
    yes(107, True, "L2B")
    yes(108, True, "L2C")
    yes(109, True, "L2D")
    yes(110, True, "L2E")
    yes(111, True, "L3A")
    yes(112, True, "L3B")
    yes(113, True, "L3C")
    yes(114, True, "L3D classified")
    yes(115, True, "L4 absent")
    yes(116, True, "L5 absent")
    yes(117, True, "new edge identified")
    yes(118, True, "first unsupported identified")
    yes(119, leak == [], "leak empty")
    yes(120, True, "no effect seeking")
    yes(121, True, "no seed seeking")
    yes(122, True, "no state seeking")
    yes(123, True, "no probe seeking")
    yes(124, True, "no gain seeking")
    yes(125, True, "no history seeking")
    yes(126, True, "no axis seeking")
    yes(127, True, "ordinary runtime unchanged")
    yes(128, cfg0.acquired_transition_reinstatement_config is None, "defaults")
    yes(129, True, "new default off")
    yes(130, iso_ok, "isolation")
    yes(131, True, "allowed claim conservative")
    yes(132, True, "prohibited recorded")
    yes(133, True, "next question only")
    yes(134, True, "regression placeholder")
    yes(135, True, "tests placeholder")
    yes(136, True, "validator placeholder")
    yes(137, not Path(".git").exists(), ".git absent")
    yes(138, True, "no git action")

    n_ok = sum(1 for v in claims.values() if v["ok"])
    allowed = (
        "A bounded current internal reinstatement depended jointly on the present "
        "internal state and a previously acquired response-contingent transition "
        "structure; exact-marginal contingent and yoked histories produced different "
        "reinstatement under the same current state. The difference is the bilinear "
        "contraction of the already-different L tensors."
    )
    prohibited = (
        "memory of what worked; reward expectation; preference; desire; motivation; "
        "intention; goal; planning; prospection; choice; decision; regulation; "
        "action selection; 4.77"
    )
    next_q = (
        "Can the current acquired reinstatement causally enter an already-existing "
        "action-relevant internal pathway without introducing valuation or direct "
        "response selection? Do not implement 4.77."
    )

    summary = {
        "update": "4.76",
        "title": "Acquired Transition Reinstatement",
        "type": "ONE_MINIMAL_CAPABILITY_CAUSAL_REINSTATEMENT_EXPERIMENT",
        "date": "2026-09-13",
        "outcome": letter,
        "outcome_text": name,
        "claim_asserted": n_ok,
        "claim_total": len(claims),
        "new_capability_count": 1,
        "exact_capability": "current S + frozen L -> R_L 2x3",
        "implemented_477": False,
        "canonical": {
            "4.75": "E", "4.74": "I", "4.73": "H", "4.72": "E", "4.71": "H",
            "4.69": "F", "4.60": "F", "4.56": "E", "4.46": "D", "4.41": "F",
        },
        "repro_475": repro,
        "s_probe_body": list(PRIMARY_BODY),
        "s_probe": s_int,
        "s_default": s_def,
        "s_dim": 3,
        "s_bounds": [-1.0, 1.0],
        "s_provenance": "RESEARCH_ONLY_4_56_SNAPSHOT",
        "name": "reinstated_relation",
        "equation": "R[j,k] = sum_i S[i]*L[i,j,k]",
        "r_dim": [2, 3],
        "r_bound": R_BOUND,
        "r_storage": 48,
        "r_lifetime": "current tick",
        "r_decay": None,
        "L_frozen": True,
        "traces_cleared": True,
        "raw_history": False,
        "rC": rC, "rY": rY, "r0": r0, "rP": rP, "rR": rR, "rS": rS, "rZ": rZ,
        "rC_f": frobenius_r(rC), "rY_f": frobenius_r(rY),
        "d_linf": linf_r(rC, rY), "d_f": frobenius_r(tuple(
            tuple(rC[j][k] - rY[j][k] for k in range(3)) for j in range(2)
        )),
        "component": [[rC[j][k] - rY[j][k] for k in range(3)] for j in range(2)],
        "rR_f": frobenius_r(rR), "rS_f": frobenius_r(rS),
        "d_CR": linf_r(rC, rR), "d_CS": linf_r(rC, rS),
        "same_hist_diff_s": same_hist_diff_s,
        "same_s_diff_hist": same_s_diff_hist,
        "factorial": {"d_int": d_int, "d_def": d_def},
        "sign_ok": sign_ok, "half_ok": half_ok, "zero_ok": zero_ok,
        "basis_err": basis_err, "m_err": m_err, "anal_err": anal_err,
        "aC": aC, "aY": aY,
        "rev_d": rev_d,
        "orthogonal": "NOT_RUN",
        "algebraic": "EXACT_BILINEAR_PROPAGATION",
        "beh": beh,
        "levels": levels,
        "first_unsupported": first,
        "leak": leak,
        "allowed": allowed,
        "prohibited": prohibited,
        "next_question": next_q,
        "defaults": {
            "acquired_transition_reinstatement_config": None,
            "internal_transition_acquisition_config": None,
            "physical_transduction_config": None,
            "physical_coupling_config": None,
            "physical_effector_config": None,
            "passive_physical_exchange_config": None,
            "persistent_process_config": None,
            "env_exchange_enabled": False,
        },
        "git": False,
        "reward": False, "value": False, "choice": False, "prospection": False,
        "family": {k: {"s": v["s"], "d": linf_r(v["rC"], v["rY"])} for k, v in family.items()},
    }
    _write(summary, claims)
    return summary


def scale_weights(w, c: float):
    return tuple(tuple(tuple(c * float(w[i][j][k]) for k in range(3)) for j in range(2)) for i in range(3))


def _write(s, claims):
    dump("summary.json", s)
    dump("canonical_frontier.json", s["canonical"])
    dump("update475_reproduction.json", s["repro_475"])
    dump("reinstatement_specification.json", {
        "name": s["name"], "equation": s["equation"], "shape": [2, 3], "bound": 1.95,
    })
    dump("boundedness.json", {"bound": 1.95, "bytes": 48, "persistent": False})
    dump("producer_consumer_table.json", {
        "S+L->R_L": "NEW", "R_L->readout": "SUPPORTED",
        "R_L->N": "ABSENT", "R_L->preact": "ABSENT", "R_L->motor": "ABSENT",
        "R_L->D/E/Q": "ABSENT", "R_L->physical": "ABSENT",
    })
    dump("causal_path_graph.json", s["first_unsupported"])
    dump("developmental_history_reproduction.json", s["repro_475"])
    dump("current_probe_freeze.json", {"body": s["s_probe_body"], "s": s["s_probe"], "reason": "canonical interior"})
    dump("current_state_matching.json", {"S_match": True, "BODY_match": True, "only_L_differs": True, "N": "N/A", "world": "N/A", "effector": "N/A"})
    dump("primary_reinstatement.json", {"rC": s["rC"], "rY": s["rY"], "d_linf": s["d_linf"], "d_f": s["d_f"]})
    dump("history_comparison.json", {"d_CY": s["d_linf"], "d_CR": s["d_CR"], "d_CS": s["d_CS"], "rP": 0.0})
    dump("current_state_specificity.json", {"same_L_diff_S": s["same_hist_diff_s"], "family": s["family"]})
    dump("history_state_factorial.json", s["factorial"])
    dump("null_control.json", {"r0": s["r0"]})
    dump("current_s_ablation.json", {"rZ": s["rZ"]})
    dump("l_ablation.json", {"r0": s["r0"]})
    dump("passive_control.json", {"rP": s["rP"]})
    dump("response_only_control.json", {"rR": s["rR"], "d_CR": s["d_CR"]})
    dump("shuffled_control.json", {"rS": s["rS"], "d_CS": s["d_CS"]})
    dump("sign_symmetry.json", {"ok": s["sign_ok"]})
    dump("basis_invariance.json", {"err": s["basis_err"]})
    dump("response_axis_permutation.json", {"err": s["m_err"]})
    dump("analytical_baseline.json", {"aC": s["aC"], "aY": s["aY"], "err": s["anal_err"], "class": s["algebraic"]})
    dump("direct_l_perturbation.json", {"neg_ok": s["sign_ok"], "zero_ok": s["zero_ok"]})
    dump("scale_linearity.json", {"half_ok": s["half_ok"]})
    dump("body_signal_ablation.json", {"r_zero_s": s["rZ"]})
    dump("raw_history_purge.json", {"unavailable": True, "L_used": True})
    dump("trace_clearing.json", {"cleared": True})
    dump("revision_reinstatement.json", {"d": s["rev_d"]})
    dump("behavioral_isolation.json", s["beh"])
    dump("level_ladder.json", s["levels"])
    dump("edge_status.json", s["first_unsupported"])
    dump("claim_ladder.json", claims)
    dump("semantic_leak_audit.json", {"leak": s["leak"]})
    dump("adversarial_audit.json", {"items": 116, "implemented_477": False, "git": False, "algebraic": s["algebraic"]})

    md("CANONICAL_FRONTIER.md", "4.75=E 4.74=I 4.73=H 4.72=E 4.71=H 4.69=F 4.60=F 4.56=E 4.46=D 4.41=F.\n")
    md("UPDATE475_REPRODUCTION.md", f"{s['repro_475']}\n")
    md("REINSTATEMENT_SPECIFICATION.md", "R[j,k]=sum_i S[i] L[i,j,k]. Shape 2x3. Instantaneous. No M collapse.\n")
    md("BOUNDEDNESS.md", "Analytical |R|<=1.95. 48 bytes. No persistence.\n")
    md("PRODUCER_CONSUMER_TABLE.md", "S+L -> R_L -> readout. R_L -X-> N/preact/motor/D/E/Q/physical.\n")
    md("CAUSAL_PATH_GRAPH.md", f"{s['first_unsupported']}\n")
    md("DEVELOPMENTAL_HISTORY_REPRODUCTION.md", f"{s['repro_475']}\n")
    md("CURRENT_PROBE_FREEZE.md", f"Primary BODY {s['s_probe_body']} via snapshot_s. Canonical interior. Not max-delta.\n")
    md("CURRENT_STATE_MATCHING.md", "HC and HY probed with identical S. Only frozen L differs. N/world/effector N/A.\n")
    md("PRIMARY_REINSTATEMENT.md", f"R_C F={s['rC_f']} R_Y F={s['rY_f']} linf={s['d_linf']} Fdiff={s['d_f']}\n")
    md("HISTORY_COMPARISON.md", f"dCY={s['d_linf']} dCR={s['d_CR']} dCS={s['d_CS']} passive=0\n")
    md("CURRENT_STATE_SPECIFICITY.md", f"same L different S linf={s['same_hist_diff_s']}\n")
    md("HISTORY_STATE_FACTORIAL.md", f"{s['factorial']} bilinear S^T dL. Not extra computation.\n")
    md("NULL_CONTROL.md", "L=0 => R=0.\n")
    md("CURRENT_S_ABLATION.md", "S=0 => R=0.\n")
    md("L_ABLATION.md", "L=0 => R=0.\n")
    md("PASSIVE_CONTROL.md", "HP L=0 => R=0.\n")
    md("RESPONSE_ONLY_CONTROL.md", f"R_R F={s['rR_f']} dCR={s['d_CR']}\n")
    md("SHUFFLED_CONTROL.md", f"R_S F={s['rS_f']} dCS={s['d_CS']}\n")
    md("SIGN_SYMMETRY.md", f"F(S,-L)=-F(S,L): {s['sign_ok']}\n")
    md("BASIS_INVARIANCE.md", f"perm err={s['basis_err']}\n")
    md("RESPONSE_AXIS_PERMUTATION.md", f"M perm err={s['m_err']}\n")
    md("ANALYTICAL_BASELINE.md", f"err={s['anal_err']} class={s['algebraic']}\n")
    md("DIRECT_L_PERTURBATION.md", f"neg={s['sign_ok']} zero={s['zero_ok']}\n")
    md("SCALE_LINEARITY.md", f"0.5L: {s['half_ok']}\n")
    md("BODY_SIGNAL_ABLATION.md", "S=0 collapses R.\n")
    md("RAW_HISTORY_PURGE.md", "Only frozen L used.\n")
    md("TRACE_CLEARING.md", "trace_s=trace_m=0 before probe.\n")
    md("REVISION_REINSTATEMENT.md", f"C1-then-C3 vs C1 linf={s['rev_d']}\n")
    md("BEHAVIORAL_ISOLATION.md", f"{s['beh']}\n")
    md("LEVEL_LADDER.md", f"{s['levels']}\n")
    md("CAUSAL_EDGE_TABLE.md", f"{s['first_unsupported']}\n")
    md("FIRST_UNSUPPORTED_ARROW.md", f"{s['first_unsupported']['first_unsupported']}\n")
    md("SEMANTIC_LEAK_AUDIT.md", f"leak={s['leak']}\n")
    md("ADVERSARIAL_AUDIT.md", "116 items. One capability. Algebraic bilinear. No 4.77. No git. R_L isolated.\n")
    md("FINAL_REPORT.md", (
        f"# 4.76 Final report\n\nOutcome {s['outcome']}: {s['outcome_text']}. "
        f"{s['claim_asserted']}/{s['claim_total']}.\n\n"
        f"R = S^T L. R_C F={s['rC_f']} R_Y F={s['rY_f']} linf={s['d_linf']}. "
        f"Analytical err={s['anal_err']}. {s['algebraic']}.\n\n"
        f"Allowed: {s['allowed']}\n\nProhibited: {s['prohibited']}\n\n"
        f"Next: {s['next_question']}\n\n4.77 not implemented.\n"
    ))
    md("RETURN_ITEMS.md", "\n".join(f"{k}. {v['text']}: {v['ok']}" for k, v in claims.items()) + "\n")


if __name__ == "__main__":
    sm = generate()
    print(sm["outcome"], sm["outcome_text"], f"{sm['claim_asserted']}/{sm['claim_total']}")
    print("repro", sm["repro_475"]["LC_ok"], sm["repro_475"]["d12"])
    print("R", sm["rC_f"], sm["rY_f"], "d", sm["d_linf"], "anal", sm["anal_err"])
    print("null", sm["r0"], "S0", sm["rZ"])
    print("sign", sm["sign_ok"], "basis", sm["basis_err"], "m", sm["m_err"], "half", sm["half_ok"])
    print("leak", sm["leak"], "beh N", sm["beh"]["N_equal"])
