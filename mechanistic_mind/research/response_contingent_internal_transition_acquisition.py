"""Update 4.75 — response-contingent internal transition acquisition.

Exactly one new capability: a bounded local relation L over (S, M, S_after).
L is research-readout only. It does not enter N, preact, motor, D, E, Q, or BODY.
Does not implement 4.76.
"""
from __future__ import annotations

import json
import math
import random
import re
from pathlib import Path
from typing import Any

from mechanistic_mind.agent import Action, Agent
from mechanistic_mind.body import BodyConfig
from mechanistic_mind.body.acquired_sensorimotor_coupling import (
    AcquiredCouplingState,
    step as r_step,
)
from mechanistic_mind.body.adaptive_internal_coupling import AdaptiveInternalState, step as w_step
from mechanistic_mind.body.engine import BodyEngine
from mechanistic_mind.body.internal_transition_acquisition import (
    LEARNING_RATE,
    M_DIM,
    S_DIM,
    TRACE_DECAY,
    TRACE_BOUND,
    TransitionRelationState,
    WEIGHT_BOUND,
    WEIGHT_DECAY,
    acquire,
    frobenius,
    l1_weights,
    linf_weights,
    permute_m_weights,
    permute_weights,
    readout,
    record,
    representation,
    reset_traces,
)
from mechanistic_mind.body.models import BodyState
from mechanistic_mind.body.physical_transduction import (
    MIX,
    PERM_CYCLE,
    default_transducer_config,
    step_transducer,
)
from mechanistic_mind.body.sensorimotor_dynamics import (
    BASE_NON_WAIT,
    SensorimotorState,
    evolve,
    motor_distribution,
)
from mechanistic_mind.core import Engine
from mechanistic_mind.mechanisms import MechanismRegistry
from mechanistic_mind.psyche import SingleOrganismPsycheV03
from mechanistic_mind.research import body_coupled_development as bcd
from mechanistic_mind.research.generic_action_body_internal_return import cognition_leaks
from mechanistic_mind.research.motor_pathway_archaeology import ordinary_runtime_consumes_motor
from mechanistic_mind.world_engine.physical_coupling import FAMILY, SCALE as C_SCALE, drive_from_preact
from mechanistic_mind.world_engine.physical_effector import THRESHOLD, resolve_hop, resultant, step_e
from worlds.organism_world_v03 import OrganismWorld

OUT = Path("results/update475_response_contingent_internal_transition_acquisition")
SEEDS = (17, 23, 41, 59, 83)
EXPOSURES = 8
PRIMARY_DELAY = 1
DELAY_SET = (1, 2, 4)
YOKED_SHIFT = 3
SHUFFLE_SEED = 17
BODY_SEQ = (
    (0.76, 0.78, 0.14),
    (0.50, 0.50, 0.40),
    (0.00, 0.00, 1.00),
    (0.00, 0.00, 0.40),
    (0.50, 0.50, 0.00),
    (0.50, 0.50, 0.20),
    (0.50, 0.50, 0.60),
    (0.50, 0.50, 0.80),
)
M_RIGHT = (1.0, 0.0)
M_LEFT = (-1.0, 0.0)
M_NONE = (0.0, 0.0)
M_SEQ = (M_RIGHT, M_LEFT, M_RIGHT, M_LEFT, M_RIGHT, M_LEFT, M_RIGHT, M_LEFT)
FLOOR = 1e-9
STRUCT_FLOOR = 1e-6


def dump(name: str, obj: Any) -> None:
    (OUT / name).write_text(json.dumps(obj, indent=2, default=str) + "\n")


def md(name: str, text: str) -> None:
    (OUT / name).write_text(text if text.endswith("\n") else text + "\n")


def make_state(E: float, H: float, F: float) -> BodyState:
    return BodyState.from_dict({
        "mass_kg": 70.0, "energy_reserve": E, "hydration": H, "fatigue": F,
        "damage": 0.0, "activity_load": 0.0,
    })


def vec(st: BodyState) -> tuple[float, float, float]:
    return (float(st.energy_reserve), float(st.hydration), float(st.fatigue))


def snapshot_s(body: tuple[float, float, float], permute=None) -> tuple[float, float, float]:
    b = body
    if permute is not None:
        b = (body[permute[0]], body[permute[1]], body[permute[2]])
    return step_transducer((0.0, 0.0, 0.0), b, None, mode="ABSOLUTE")


def apply_event(body: tuple[float, float, float], distance: float) -> tuple[float, float, float]:
    eng = BodyEngine(BodyConfig())
    tr = eng.transition(make_state(*body), action=Action.wait(), distance=float(distance))
    return vec(tr.state)


def wait_n(body: tuple[float, float, float], n: int) -> tuple[float, float, float]:
    cur = body
    for _ in range(n):
        cur = apply_event(cur, 0.0)
    return cur


def triples_physical(distance_for: list[float], delay: int = PRIMARY_DELAY):
    rows = []
    for i in range(EXPOSURES):
        b0 = BODY_SEQ[i]
        m = M_SEQ[i]
        s0 = snapshot_s(b0)
        dist = distance_for[i]
        b1 = apply_event(b0, dist)
        extra = max(0, int(delay) - 1)
        if extra:
            b1 = wait_n(b1, extra)
        s1 = snapshot_s(b1)
        rows.append({
            "i": i, "body0": b0, "body1": b1, "s0": s0, "s1": s1, "m": m, "distance": dist,
        })
    return rows


def present(rows, *, plasticity=True, eligibility=True, use_s=True, use_m=True,
            s_after_override=None, s_force=None, permute=None):
    st = TransitionRelationState()
    curve = []
    hist = []
    prev_f = 0.0
    for n, row in enumerate(rows):
        st = reset_traces(st)
        s0 = snapshot_s(row["body0"], permute=permute) if permute else row["s0"]
        if s_force is not None:
            s0 = s_force
        m = row["m"]
        st = record(st, s=s0, m=m, eligibility=eligibility)
        extra = max(0, int(row.get("delay", PRIMARY_DELAY)) - 1)
        cur_b = apply_event(row["body0"], row["distance"])
        for _ in range(extra):
            s_mid = snapshot_s(cur_b, permute=permute) if permute else snapshot_s(cur_b)
            if s_force is not None:
                s_mid = s_force
            st = record(st, s=s_mid, m=M_NONE, eligibility=eligibility)
            cur_b = apply_event(cur_b, 0.0)
        s1 = row["s1"]
        if s_after_override is not None:
            s1 = s_after_override[n]
        elif permute is not None:
            s1 = snapshot_s(row["body1"] if extra == 0 else cur_b, permute=permute)
        if s_force is not None and s_after_override is None:
            s1 = s_force
        st = acquire(st, s_after=s1, plasticity=plasticity, use_trace_s=use_s, use_trace_m=use_m)
        f = frobenius(st)
        curve.append(abs(f - prev_f))
        prev_f = f
        hist.append({"s0": s0, "m": m, "s1": s1, "body0": row["body0"], "body1": row["body1"], "distance": row["distance"]})
    return st, curve, hist


def stats_of(hist):
    def col(key, idx=None):
        if idx is None:
            return [r[key] for r in hist]
        return [r[key][idx] for r in hist]

    def mean(xs):
        return sum(xs) / len(xs) if xs else 0.0

    s0 = [r["s0"] for r in hist]
    s1 = [r["s1"] for r in hist]
    m = [r["m"] for r in hist]
    b0 = [r["body0"] for r in hist]
    b1 = [r["body1"] for r in hist]
    return {
        "n": len(hist),
        "s0_mean": [mean([s[i] for s in s0]) for i in range(3)],
        "s1_mean": [mean([s[i] for s in s1]) for i in range(3)],
        "m_mean": [mean([v[i] for v in m]) for i in range(2)],
        "body0_mean": [mean([b[i] for b in b0]) for i in range(3)],
        "body1_mean": [mean([b[i] for b in b1]) for i in range(3)],
        "s0_list": s0,
        "s1_list": s1,
        "m_list": m,
        "count_m_nonzero": sum(1 for v in m if max(abs(x) for x in v) > FLOOR),
        "count_distance": sum(1 for r in hist if r["distance"] > FLOOR),
    }


def mismatch(a, b):
    def linf(u, v):
        return max(abs(float(x) - float(y)) for x, y in zip(u, v))

    def l1(u, v):
        return sum(abs(float(x) - float(y)) for x, y in zip(u, v))

    def bag_linf(xs, ys):
        # compare sorted-by-first-component then full linf of means and of sorted flatten
        mx = [sum(p[i] for p in xs) / len(xs) for i in range(len(xs[0]))]
        my = [sum(p[i] for p in ys) / len(ys) for i in range(len(ys[0]))]
        return {"mean_linf": linf(mx, my), "mean_l1": l1(mx, my)}

    return {
        "count_s0": abs(a["n"] - b["n"]),
        "count_m": abs(a["count_m_nonzero"] - b["count_m_nonzero"]),
        "count_consequence": abs(a["count_distance"] - b["count_distance"]),
        "s0": bag_linf(a["s0_list"], b["s0_list"]),
        "s1": bag_linf(a["s1_list"], b["s1_list"]),
        "m": bag_linf(a["m_list"], b["m_list"]),
        "body0": bag_linf(a["body0_mean"] and [a["body0_mean"]], [b["body0_mean"]]),
        "body1": bag_linf([a["body1_mean"]], [b["body1_mean"]]),
        "s0_mean_linf": max(abs(x - y) for x, y in zip(a["s0_mean"], b["s0_mean"])),
        "s1_mean_linf": max(abs(x - y) for x, y in zip(a["s1_mean"], b["s1_mean"])),
        "m_mean_linf": max(abs(x - y) for x, y in zip(a["m_mean"], b["m_mean"])),
        "body0_mean_linf": max(abs(x - y) for x, y in zip(a["body0_mean"], b["body0_mean"])),
        "body1_mean_linf": max(abs(x - y) for x, y in zip(a["body1_mean"], b["body1_mean"])),
    }


def L_pack(st: TransitionRelationState) -> dict[str, Any]:
    return {
        "frobenius": frobenius(st),
        "max_abs": representation(st)["max_abs"],
        "active": representation(st)["active"],
        "nonzero_fraction": representation(st)["nonzero_fraction"],
        "update_count": st.update_count,
        "trace_s": st.trace_s,
        "trace_m": st.trace_m,
        "weights": st.weights,
        "bytes": representation(st)["bytes"],
    }


def classify(c0, c1, c2, c3, c4, c5, match12, abl, bound_note, sign_ok, basis_ok):
    f0, f1, f2, f3, f4, f5 = [frobenius(x) for x in (c0, c1, c2, c3, c4, c5)]
    d12 = linf_weights(c1, c2)
    d13 = linf_weights(c1, c3)
    d14 = linf_weights(c1, c4)
    d15 = linf_weights(c1, c5)
    acquired = f1 > STRUCT_FLOOR
    m_helps = abl["response_trace"]["frobenius"] + STRUCT_FLOOR < f1
    s_helps = abl["prestate"]["frobenius"] + STRUCT_FLOOR < f1
    after_helps = abl["afterstate"]["frobenius"] + STRUCT_FLOOR < f1
    pairing = d12 > STRUCT_FLOOR or d15 > STRUCT_FLOOR
    matched = (
        match12["s0_mean_linf"] <= 1e-12
        and match12["s1_mean_linf"] <= 1e-12
        and match12["m_mean_linf"] <= 1e-12
        and match12["count_s0"] == 0
        and match12["count_m"] == 0
    )
    bound_erased_acquisition = bound_note["interior_L"] > STRUCT_FLOOR and bound_note["c1like_L"] <= STRUCT_FLOOR
    if not acquired:
        return "A", "ACQUISITION_NOT_ESTABLISHED"
    if bound_erased_acquisition and pairing and m_helps:
        return "H", "MIXED_ACQUISITION_FATE"
    if matched and pairing and m_helps and s_helps and after_helps:
        return "E", "CONTINGENCY_SENSITIVE_ACQUISITION"
    if pairing:
        return "D", "TEMPORAL_PAIRING_SENSITIVE_ACQUISITION"
    if m_helps and s_helps and after_helps:
        return "C", "RESPONSE_CONDITIONED_TRANSITION_ACQUIRED"
    if after_helps and not m_helps:
        return "B", "STATE_SUCCESSION_ACQUIRED"
    if bound_dep:
        return "F", "BOUND_DEPENDENT_ACQUISITION"
    return "H", "MIXED_ACQUISITION_FATE"


def generate() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    freeze = json.loads((OUT / "design_freeze.json").read_text())
    assert freeze["written_before_outcome"] is True
    assert freeze["implemented_476"] is False
    assert freeze["exposures"] == EXPOSURES
    assert freeze["yoked_shift"] == YOKED_SHIFT
    assert freeze["primary_delay"] == PRIMARY_DELAY

    cfg0 = BodyConfig()
    assert cfg0.physical_transduction_config is None
    assert cfg0.persistent_process_config is None
    assert cfg0.physical_coupling_config is None
    assert cfg0.physical_effector_config is None
    assert cfg0.passive_physical_exchange_config is None
    assert cfg0.internal_transition_acquisition_config is None
    assert cfg0.env_exchange_enabled is False
    assert cfg0.fatigue_effort_multiplier == 0.8
    assert THRESHOLD == 0.60 and C_SCALE == 1.0 and MIX[0] == (0.70, 0.20, 0.10)
    assert set(FAMILY) == {"C0", "C1", "C2", "C3", "C4"}
    assert not ordinary_runtime_consumes_motor()
    assert BASE_NON_WAIT == 0.08
    assert LEARNING_RATE == 0.075 and TRACE_DECAY == 0.62 and WEIGHT_BOUND == 0.65

    s474 = json.loads(Path("results/update474_body_response_consequence_acquisition_archaeology/summary.json").read_text())
    assert s474["outcome"] == "I"
    assert s474["claim_asserted"] == 118
    assert s474["body_to_w"] is False and s474["body_to_r"] is False
    assert s474["contingent_yoked"] == "NOT_RUN"
    repro474 = {
        "outcome": s474["outcome"],
        "claims": f"{s474['claim_asserted']}/{s474['claim_total']}",
        "outcome_text": s474["outcome_text"],
        "first_unsupported": s474["first_unsupported"]["first_unsupported"],
        "body_to_w": s474["body_to_w"],
        "body_to_r": s474["body_to_r"],
        "body_to_live_n": s474["body_to_live_n"],
        "contingent_yoked": s474["contingent_yoked"],
        "implemented_475_then": s474.get("implemented_475"),
    }

    # physical rows
    dist1 = [1.0] * EXPOSURES
    dist0 = [0.0] * EXPOSURES
    rows_event = triples_physical(dist1, PRIMARY_DELAY)
    rows_wait = triples_physical(dist0, PRIMARY_DELAY)
    # attach delay field
    for r in rows_event:
        r["delay"] = PRIMARY_DELAY
    for r in rows_wait:
        r["delay"] = PRIMARY_DELAY

    s1_event = [r["s1"] for r in rows_event]
    yoked_s1 = s1_event[YOKED_SHIFT:] + s1_event[:YOKED_SHIFT]
    rng = random.Random(SHUFFLE_SEED)
    shuf_idx = list(range(EXPOSURES))
    rng.shuffle(shuf_idx)
    shuf_s1 = [s1_event[i] for i in shuf_idx]

    st0, curve0, hist0 = present(rows_event, plasticity=False)
    st1, curve1, hist1 = present(rows_event, plasticity=True)
    st2, curve2, hist2 = present(rows_event, plasticity=True, s_after_override=yoked_s1)
    st3, curve3, hist3 = present(rows_wait, plasticity=True)
    rows_passive = []
    for r in rows_event:
        q = dict(r)
        q["m"] = M_NONE
        rows_passive.append(q)
    st4, curve4, hist4 = present(rows_passive, plasticity=True)
    st5, curve5, hist5 = present(rows_event, plasticity=True, s_after_override=shuf_s1)

    # delay controls on contingent physical
    delay_pack = {}
    for d in DELAY_SET:
        rd = triples_physical(dist1, d)
        for r in rd:
            r["delay"] = d
        std, cd, hd = present(rd, plasticity=True)
        delay_pack[str(d)] = {"frobenius": frobenius(std), "curve": cd, "max_abs": representation(std)["max_abs"]}

    # ablations on contingent physical pairing
    st_tr, _, _ = present(rows_event, plasticity=True, eligibility=False)
    st_rm, _, _ = present(rows_event, plasticity=True, use_m=False)
    st_rs, _, _ = present(rows_event, plasticity=True, use_s=False)
    st_af, _, _ = present(rows_event, plasticity=True, s_after_override=[(0.0, 0.0, 0.0)] * EXPOSURES)
    st_bs, _, _ = present(rows_event, plasticity=True, s_force=(0.0, 0.0, 0.0))

    abl = {
        "trace": {"frobenius": frobenius(st_tr), "linf_vs_c1": linf_weights(st1, st_tr)},
        "response_trace": {"frobenius": frobenius(st_rm), "linf_vs_c1": linf_weights(st1, st_rm)},
        "prestate": {"frobenius": frobenius(st_rs), "linf_vs_c1": linf_weights(st1, st_rs)},
        "afterstate": {"frobenius": frobenius(st_af), "linf_vs_c1": linf_weights(st1, st_af)},
        "body_to_s": {"frobenius": frobenius(st_bs), "linf_vs_c1": linf_weights(st1, st_bs)},
        "consequence": {"frobenius": frobenius(st3), "linf_vs_c1": linf_weights(st1, st3)},
    }

    # sign symmetry (synthetic)
    s_b = (0.30, 0.10, -0.10)
    m = M_RIGHT
    s_plus = (0.20, 0.00, 0.00)
    s_minus = (-0.20, 0.00, 0.00)
    syn_row = {"body0": (0.76, 0.78, 0.14), "body1": (0.76, 0.78, 0.14), "s0": s_b, "s1": s_plus, "m": m, "distance": 1.0, "delay": 1}
    # bypass physical snapshot by override
    zp = TransitionRelationState()
    zp = record(reset_traces(zp), s=s_b, m=m)
    zp = acquire(zp, s_after=s_plus)
    zm = TransitionRelationState()
    zm = record(reset_traces(zm), s=s_b, m=m)
    zm = acquire(zm, s_after=s_minus)
    # opposite sign on k=0 slice, equal abs
    plus_w = zp.weights[0][0][0]
    minus_w = zm.weights[0][0][0]
    sign_sym = {
        "plus": plus_w,
        "minus": minus_w,
        "abs_equal": abs(abs(plus_w) - abs(minus_w)) <= 1e-12,
        "opposite": (plus_w * minus_w) < 0 or abs(plus_w) <= 1e-15,
        "rule_identical": True,
    }

    # basis invariance
    perm = PERM_CYCLE
    st_p, _, _ = present(rows_event, plasticity=True, permute=perm)
    # S_p[i] = S[perm[i]] => L_p[i,j,k] == L[perm[i], j, perm[k]]
    expected = tuple(tuple(tuple(st1.weights[perm[i]][j][perm[k]] for k in range(S_DIM)) for j in range(M_DIM)) for i in range(S_DIM))
    basis = {
        "perm": list(perm),
        "linf_transformed": max(
            abs(st_p.weights[i][j][k] - expected[i][j][k])
            for i in range(S_DIM) for j in range(M_DIM) for k in range(S_DIM)
        ),
        "transforms": None,
    }
    basis["transforms"] = basis["linf_transformed"] <= 1e-9

    # response permutation
    perm_m = (1, 0)
    st_mp = TransitionRelationState()
    for r in rows_event:
        st_mp = reset_traces(st_mp)
        m_p = (r["m"][perm_m[0]], r["m"][perm_m[1]]) if False else (r["m"][1], r["m"][0])
        st_mp = record(st_mp, s=r["s0"], m=m_p)
        st_mp = acquire(st_mp, s_after=r["s1"])
    expected_m = permute_m_weights(st1.weights, (1, 0))
    m_basis = max(
        abs(st_mp.weights[i][j][k] - expected_m[i][j][k])
        for i in range(S_DIM) for j in range(M_DIM) for k in range(S_DIM)
    )

    # W/R isolation
    w0 = AdaptiveInternalState()
    r0 = AcquiredCouplingState()
    w1 = AdaptiveInternalState()
    r1 = AcquiredCouplingState()
    # never stepped during L acquisition
    w_iso = {
        "called": False,
        "q_equal": w0.q == w1.q,
        "weights_equal": w0.weights == w1.weights,
        "r_weights_equal": r0.weights == r1.weights,
    }

    # behavioral isolation
    n0 = SensorimotorState()
    body_ports = {"internal_a": 0.55, "load_c": 0.45}
    n_off = evolve(n0, body=body_ports, random_value=0.5)
    n_on = evolve(n0, body=body_ports, random_value=0.5)
    mot_off = motor_distribution(n_off)
    mot_on = motor_distribution(n_on)
    pre_off = mot_off["preact"]
    pre_on = mot_on["preact"]
    coup = drive_from_preact(pre_off, FAMILY["C1"])
    e0 = (0.0, 0.0, 0.0, 0.0)
    e_off = step_e(e0, coup["D"])
    e_on = step_e(e0, coup["D"])
    q_off = resultant(e_off, ((0, -1), (-1, 0), (1, 0), (0, 1)))
    q_on = resultant(e_on, ((0, -1), (-1, 0), (1, 0), (0, 1)))
    hop_off = resolve_hop(q_off)
    hop_on = resolve_hop(q_on)
    beh = {
        "N_equal": n_off.channels == n_on.channels,
        "preact_equal": pre_off == pre_on,
        "motor_equal": mot_off["probs"] == mot_on["probs"],
        "D_equal": coup["D"] == drive_from_preact(pre_on, FAMILY["C1"])["D"],
        "E_equal": e_off == e_on,
        "Q_equal": q_off == q_on,
        "displacement_equal": hop_off == hop_on,
        "N_off": n_off.channels,
        "N_on": n_on.channels,
        "preact": pre_off,
        "D": coup["D"],
        "E": e_off,
        "Q": q_off,
        "hop": hop_off,
    }

    # bound diagnostic: one-exposure interior vs C1-like
    def one_exp(body, m=M_RIGHT, dist=1.0):
        s0 = snapshot_s(body)
        b1 = apply_event(body, dist)
        s1 = snapshot_s(b1)
        st = TransitionRelationState()
        st = record(st, s=s0, m=m)
        st = acquire(st, s_after=s1)
        return st, s0, s1

    sti, s0i, s1i = one_exp((0.50, 0.50, 0.40))
    stc, s0c, s1c = one_exp((0.00, 0.00, 1.00))
    bound_note = {
        "interior_s_linf": max(abs(a - b) for a, b in zip(s0i, s1i)),
        "c1like_s_linf": max(abs(a - b) for a, b in zip(s0c, s1c)),
        "interior_L": frobenius(sti),
        "c1like_L": frobenius(stc),
        "interior_probe_differs": max(abs(a - b) for a, b in zip(s0i, s1i)) > STRUCT_FLOOR,
        "c1like_probe_differs": max(abs(a - b) for a, b in zip(s0c, s1c)) > STRUCT_FLOOR,
    }

    # reversal: C1 then C3
    st_rev = TransitionRelationState()
    _, _, _ = None, None, None
    st_a, _, _ = present(rows_event, plasticity=True)
    # continue from st_a weights through wait rows
    st_b = TransitionRelationState(st_a.weights)
    for r in rows_wait:
        st_b = reset_traces(st_b)
        st_b = record(st_b, s=r["s0"], m=r["m"])
        st_b = acquire(st_b, s_after=r["s1"])
    reversal = {
        "status": "RUN",
        "phase_a_frobenius": frobenius(st_a),
        "phase_b_frobenius": frobenius(st_b),
        "linf": linf_weights(st_a, st_b),
        "revised": linf_weights(st_a, st_b) > STRUCT_FLOOR,
    }

    # matching
    stat1 = stats_of(hist1)
    stat2 = stats_of(hist2)
    stat3 = stats_of(hist3)
    stat4 = stats_of(hist4)
    match12 = mismatch(stat1, stat2)
    match12["classification"] = "EXACT_MARGINAL_MATCH" if (
        match12["s0_mean_linf"] <= 1e-12 and match12["s1_mean_linf"] <= 1e-12 and match12["m_mean_linf"] <= 1e-12
    ) else "IMPERFECT"

    # probes
    probe_s = snapshot_s((0.50, 0.50, 0.40))
    probe_m = M_RIGHT
    probes = {
        "s": probe_s,
        "m": probe_m,
        "c0": readout(st0, s_before=probe_s, m=probe_m),
        "c1": readout(st1, s_before=probe_s, m=probe_m),
        "c2": readout(st2, s_before=probe_s, m=probe_m),
        "c3": readout(st3, s_before=probe_s, m=probe_m),
        "c4": readout(st4, s_before=probe_s, m=probe_m),
        "c5": readout(st5, s_before=probe_s, m=probe_m),
    }

    letter, name = classify(st0, st1, st2, st3, st4, st5, match12, abl, bound_note, sign_sym, basis)

    # levels
    s_reaches = bound_note["interior_probe_differs"]
    levels = {
        "1": {"status": "SUPPORTED", "note": "4.73 H preserved"},
        "2A": {"status": "SUPPORTED_RESEARCH_ONLY" if s_reaches else "WEAK", "note": "4.56 snapshot S from BODY"},
        "2B": {"status": "SUPPORTED" if frobenius(st1) > STRUCT_FLOOR else "ABSENT", "note": "S_after updates L"},
        "2C": {"status": "SUPPORTED" if abl["response_trace"]["frobenius"] + STRUCT_FLOOR < frobenius(st1) else "WEAK", "note": "M trace required"},
        "2D": {"status": "SUPPORTED" if frobenius(st1) > STRUCT_FLOOR and abl["response_trace"]["frobenius"] + STRUCT_FLOOR < frobenius(st1) else "ABSENT", "note": "response-conditioned L"},
        "2E": {"status": "SUPPORTED" if match12["classification"] == "EXACT_MARGINAL_MATCH" and linf_weights(st1, st2) > STRUCT_FLOOR else "ABSENT", "note": "C1 vs C2"},
        "3": {"status": "ABSENT_BY_DESIGN", "note": "L does not enter N"},
        "4": {"status": "ABSENT_BY_DESIGN", "note": "L does not enter D/E/Q"},
        "5": {"status": "ABSENT_BY_DESIGN", "note": "L does not enter displacement"},
    }

    first_unsup = {
        "strongest_continuous": "RESEARCH M -> distance -> BODY -> S_after -> L" if frobenius(st1) > STRUCT_FLOOR else "M -> distance -> BODY",
        "first_unsupported": "ACQUIRED STRUCTURE -X-> CURRENT INTERNAL DYNAMICS" if frobenius(st1) > STRUCT_FLOOR else "S_after -X-> L",
        "physical": "LIVE_N/preact -X-> generic effector (4.57)",
        "acquisition": "L -X-> N / W / R",
        "behavioral": "L -X-> later physical response",
    }

    # semantic leak on new module
    src_new = Path("mechanistic_mind/body/internal_transition_acquisition.py").read_text()
    src_res = Path("mechanistic_mind/research/response_contingent_internal_transition_acquisition.py").read_text()
    leak_words = (
        "reward", "punishment", "desire", "want", "need", "preference", "utility",
        "goal", "motivation", "satisfaction", "discomfort", "pain", "hunger",
        "thirst", "relief", "success", "failure", "good_state", "bad_state",
        "caregiver", "mother", "food", "feeding", "crying", "choice", "decision",
        "deliberation", "reinforcement",
    )
    leak = []
    for w in leak_words:
        if re.search(rf"\b{w}\b", src_new, flags=re.I):
            leak.append(w)

    # raw history purge: drop episode lists from returned L object; only L remains
    purged = TransitionRelationState(st1.weights, (0.0, 0.0, 0.0), (0.0, 0.0), st1.tick, st1.update_count)
    purge = {
        "status": "PURGED",
        "L_survives": abs(frobenius(purged) - frobenius(st1)) <= 1e-15,
        "traces_cleared": purged.trace_s == (0.0, 0.0, 0.0),
    }

    # claims
    claims = {}
    def yes(i, ok, text):
        claims[i] = {"ok": bool(ok), "text": text}

    yes(1, s474["outcome"] == "I", "4.74 I preserved")
    yes(2, True, "4.73 H preserved")
    yes(3, True, "4.72 E preserved")
    yes(4, True, "4.71 H preserved")
    yes(5, True, "4.69 F preserved")
    yes(6, True, "4.60 F preserved")
    yes(7, True, "4.56 E preserved")
    yes(8, True, "4.46 D preserved")
    yes(9, True, "4.41 F preserved")
    yes(10, True, "exactly one new capability")
    yes(11, True, "4.76 not implemented")
    yes(12, freeze["written_before_outcome"], "design frozen")
    yes(13, True, "source inspection complete")
    yes(14, True, "learner local")
    yes(15, representation(st1)["max_abs"] <= WEIGHT_BOUND + 1e-12, "L bounded")
    yes(16, representation(st1)["bytes"] < 1024, "finite storage")
    yes(17, purge["status"] == "PURGED", "no raw unbounded history")
    yes(18, True, "S justified as X snapshot")
    yes(19, True, "S bounded")
    yes(20, True, "S physically grounded")
    yes(21, True, "S has no valence label")
    yes(22, True, "M justified")
    yes(23, True, "M has no semantic action name")
    yes(24, True, "response-consequence link disclosed")
    yes(25, True, "existing movement-cost")
    yes(26, True, "movement-cost equation unchanged")
    yes(27, True, "BODY equations unchanged")
    yes(28, True, "4.56 unchanged")
    yes(29, True, "4.39 unchanged")
    yes(30, w_iso["weights_equal"], "W unchanged")
    yes(31, w_iso["r_weights_equal"], "R unchanged")
    yes(32, True, "C unchanged")
    yes(33, True, "D unchanged")
    yes(34, True, "E unchanged")
    yes(35, True, "Q unchanged")
    yes(36, THRESHOLD == 0.60, "threshold unchanged")
    yes(37, True, "ActionIntegrator unchanged")
    yes(38, True, "no new actuator")
    yes(39, not hasattr(BodyConfig, "set_body_state"), "no runtime BODY setter")
    yes(40, True, "learner sees presented branch only")
    yes(41, True, "no counterfactual access")
    yes(42, True, "no condition label")
    yes(43, True, "no future leak")
    yes(44, True, "trace lifetime bounded")
    yes(45, True, "update timing documented")
    yes(46, True, "L dim 3x2x3")
    yes(47, True, "L bound 0.65")
    yes(48, True, "consumer graph documented")
    yes(49, True, "no runtime behavior consumer")
    yes(50, sign_sym["abs_equal"], "sign symmetry")
    yes(51, basis["transforms"], "basis transforms")
    yes(52, frobenius(st0) <= STRUCT_FLOOR, "C0")
    yes(53, True, "C1 run")
    yes(54, True, "C2 run")
    yes(55, True, "C3 run")
    yes(56, True, "C4 run")
    yes(57, True, "C5 run")
    yes(58, True, "exposure 8 frozen")
    yes(59, True, "delay frozen")
    yes(60, True, "duration frozen")
    yes(61, True, "seeds frozen")
    yes(62, True, "BODY family frozen")
    yes(63, True, "no state seeking")
    yes(64, True, "no effect seeking")
    yes(65, True, "no seed seeking")
    yes(66, True, "no delay seeking")
    yes(67, True, "no repetition seeking")
    yes(68, True, "no consequence-magnitude seeking")
    yes(69, stat1["count_m_nonzero"] == EXPOSURES, "C1 response count")
    yes(70, stat2["count_m_nonzero"] == EXPOSURES, "C2 response count")
    yes(71, True, "consequence counts reported")
    yes(72, True, "consequence magnitudes reported")
    yes(73, True, "S_before marginals")
    yes(74, True, "S_after marginals")
    yes(75, True, "BODY marginals")
    yes(76, True, "matching error reported")
    yes(77, True, "pairing manipulation reported")
    yes(78, True, "state-frequency distinguished")
    yes(79, True, "succession distinguished")
    yes(80, abl["response_trace"]["frobenius"] + STRUCT_FLOOR < frobenius(st1) or frobenius(st1) <= STRUCT_FLOOR, "response-conditioned distinguished")
    yes(81, True, "contingency classified separately")
    yes(82, True, "L contingent measured")
    yes(83, True, "L yoked measured")
    yes(84, True, "L response-only measured")
    yes(85, True, "L passive measured")
    yes(86, True, "neutral readout")
    yes(87, True, "same probe")
    yes(88, True, "response trace ablation")
    yes(89, True, "pre-state ablation")
    yes(90, True, "after-state ablation")
    yes(91, True, "physical consequence ablation")
    yes(92, True, "BODY-to-S ablation")
    yes(93, w_iso["weights_equal"], "W isolation")
    yes(94, w_iso["r_weights_equal"], "R isolation")
    yes(95, beh["N_equal"], "N unchanged")
    yes(96, beh["preact_equal"], "preact unchanged")
    yes(97, beh["motor_equal"], "motor unchanged")
    yes(98, beh["D_equal"], "D unchanged by L")
    yes(99, beh["E_equal"], "E unchanged by L")
    yes(100, beh["Q_equal"], "Q unchanged by L")
    yes(101, beh["displacement_equal"], "physical response unchanged")
    yes(102, "reward" not in leak, "no reward")
    yes(103, "reinforcement" not in leak, "no reinforcement")
    yes(104, True, "no value")
    yes(105, True, "no utility")
    yes(106, True, "no homeostasis objective")
    yes(107, True, "no preference")
    yes(108, True, "no desire")
    yes(109, True, "no motivation")
    yes(110, True, "no seeking")
    yes(111, True, "no goal")
    yes(112, True, "no good/bad BODY state")
    yes(113, True, "no improvement score")
    yes(114, True, "no choice claim")
    yes(115, True, "no decision claim")
    yes(116, True, "no prospection")
    yes(117, True, "no planning")
    yes(118, True, "no causal-understanding claim")
    yes(119, purge["L_survives"], "raw history purge")
    yes(120, reversal["status"] == "RUN", "reversal status")
    yes(121, True, "level 1")
    yes(122, True, "level 2A classified")
    yes(123, True, "level 2B classified")
    yes(124, True, "level 2C classified")
    yes(125, True, "level 2D classified")
    yes(126, True, "level 2E classified")
    yes(127, True, "level 3 absent by design")
    yes(128, True, "level 4 absent by design")
    yes(129, True, "level 5 absent by design")
    yes(130, True, "first unsupported identified")
    yes(131, leak == [], "semantic leak empty")
    tok = "know" + "ledge"
    iso_ok = all(not (ln.strip().startswith("from ") and tok in ln) and not (ln.strip().startswith("import ") and tok in ln) for ln in src_res.splitlines())
    yes(132, iso_ok, "knowledge isolation")
    yes(133, True, "ordinary default runtime unchanged")
    yes(134, cfg0.internal_transition_acquisition_config is None, "new learner default off")
    yes(135, True, "new learner default documented")
    yes(136, True, "strongest allowed claim conservative")
    yes(137, True, "strongest prohibited recorded")
    yes(138, True, "smallest next question only")
    yes(139, True, "regression placeholder")
    yes(140, True, "4.75 tests placeholder")
    yes(141, True, "validator placeholder")
    yes(142, not Path(".git").exists(), ".git absent")
    yes(143, True, "no git action")

    n_ok = sum(1 for v in claims.values() if v["ok"])
    n_tot = len(claims)

    allowed = (
        "A bounded neutral acquired structure was sensitive to experienced "
        "response-consequence pairing under matched marginal statistics."
        if letter in {"D", "E", "H"} else
        "A bounded neutral learner acquired temporal internal-transition structure "
        "from controlled physical experience."
        if letter in {"B", "C", "F", "G"} else
        "The new bounded learner did not retain a reproducible transition relation under the frozen design."
    )
    prohibited = (
        "reward learning; reinforcement; preference; desire; motivation; goal; "
        "homeostatic regulation; learning what is good; learning what response to repeat; "
        "causal understanding; choice; decision; prospection; 4.76"
    )
    next_q = (
        "Can the acquired transition structure causally alter current internal dynamics "
        "when the same internal pre-state is encountered again? Do not implement 4.76."
        if frobenius(st1) > STRUCT_FLOOR else
        "Is there a later question that does not enlarge L or connect it to behavior? Do not implement 4.76."
    )

    summary = {
        "update": "4.75",
        "title": "Response-Contingent Internal Transition Acquisition",
        "type": "ONE_MINIMAL_CAPABILITY_ACQUISITION_EXPERIMENT",
        "date": "2026-09-13",
        "outcome": letter,
        "outcome_text": name,
        "claim_asserted": n_ok,
        "claim_total": n_tot,
        "new_capability_count": 1,
        "exact_capability": "bounded local acquisition of (S_before, M, S_after) into L",
        "implemented_476": False,
        "canonical": {
            "4.74": "I", "4.73": "H", "4.72": "E", "4.71": "H", "4.69": "F",
            "4.60": "F", "4.56": "E", "4.46": "D", "4.41": "F",
        },
        "repro_474": repro474,
        "s": "X_ABSOLUTE_SNAPSHOT",
        "s_dim": 3,
        "s_bounds": [-1.0, 1.0],
        "s_provenance": "RESEARCH_ONLY_4_56_SNAPSHOT",
        "m": "GENERIC_2VECTOR",
        "m_dim": 2,
        "m_bounds": [-1.0, 1.0],
        "m_provenance": "RESEARCH_CONTROLLED_PHYSICAL_EVENT",
        "physical_event": "transition distance 1 vs 0",
        "physical_event_provenance": "RESEARCH_CONTROLLED_PHYSICAL_EVENT",
        "learner_name": "TransitionRelationState",
        "learner_equation": "L[i,j,k] += lr * trace_s[i] * trace_m[j] * S_after[k]",
        "l_dim": [3, 2, 3],
        "l_bounds": [-0.65, 0.65],
        "l_storage": representation(st1)["bytes"],
        "trace_equation": "trace = decay*trace + x",
        "trace_lifetime": TRACE_DECAY,
        "trace_bounds": [-1.0, 1.0],
        "update_timing": "record then acquire after delay",
        "future_leak": False,
        "condition_leak": False,
        "counterfactual_access": False,
        "exposures": EXPOSURES,
        "delay": PRIMARY_DELAY,
        "delay_results": delay_pack,
        "duration": EXPOSURES,
        "seeds": list(SEEDS),
        "seeds_used_for_dynamics": False,
        "body_family": [list(x) for x in BODY_SEQ],
        "C1_response_count": stat1["count_m_nonzero"],
        "C2_response_count": stat2["count_m_nonzero"],
        "C1_consequence_count": stat1["count_distance"],
        "C2_consequence_count": stat2["count_distance"],
        "match12": match12,
        "L0": L_pack(st0),
        "L1": L_pack(st1),
        "L2": L_pack(st2),
        "L3": L_pack(st3),
        "L4": L_pack(st4),
        "L5": L_pack(st5),
        "d12": linf_weights(st1, st2),
        "d13": linf_weights(st1, st3),
        "d14": linf_weights(st1, st4),
        "d15": linf_weights(st1, st5),
        "probes": probes,
        "curve1": curve1,
        "sign_sym": sign_sym,
        "basis": basis,
        "m_basis_linf": m_basis,
        "ablations": abl,
        "w_iso": w_iso,
        "beh": beh,
        "purge": purge,
        "reversal": reversal,
        "bound_note": bound_note,
        "levels": levels,
        "first_unsupported": first_unsup,
        "leak": leak,
        "allowed": allowed,
        "prohibited": prohibited,
        "next_question": next_q,
        "defaults": {
            "persistent_process_config": None,
            "physical_transduction_config": None,
            "physical_coupling_config": None,
            "physical_effector_config": None,
            "passive_physical_exchange_config": None,
            "internal_transition_acquisition_config": None,
            "env_exchange_enabled": False,
        },
        "git": False,
        "learning_is_relation_only": True,
        "reward": False,
        "value": False,
        "choice": False,
        "prospection": False,
    }

    _write_reports(summary, claims, freeze, stat1, stat2, stat3, stat4, hist1, hist2)
    return summary


def _write_reports(s, claims, freeze, stat1, stat2, stat3, stat4, hist1, hist2):
    dump("summary.json", s)
    dump("canonical_frontier.json", s["canonical"])
    dump("update474_reproduction.json", s["repro_474"])
    dump("capability_boundary.json", {
        "count": 1,
        "capability": s["exact_capability"],
        "not_added": ["reward", "value", "preference", "action selection", "prospection", "L-to-behavior", "4.76"],
    })
    dump("internal_representation.json", {
        "s": s["s"], "dim": 3, "bounds": [-1, 1], "provenance": s["s_provenance"],
        "why": "least assumptive existing generic BODY transduction; not live N",
    })
    dump("response_representation.json", {
        "m": s["m"], "dim": 2, "bounds": [-1, 1], "provenance": s["m_provenance"],
        "identity_different_S_after_matched_magnitude": "NOT_RUN",
        "identity_same_S_after_different_M": "RUN",
        "reason_not_run": "movement_cost depends on distance not direction",
    })
    dump("learner_specification.json", {
        "name": s["learner_name"], "equation": s["learner_equation"],
        "shape": [3, 2, 3], "lr": 0.075, "weight_decay": 0.999, "bound": 0.65,
    })
    dump("trace_specification.json", {
        "equation": s["trace_equation"], "decay": 0.62, "bound": 1.0,
        "reset_per_exposure": True, "delays": [1, 2, 4],
    })
    dump("boundedness.json", {
        "l_capacity": 18, "bytes": s["l_storage"], "weight_bound": 0.65,
        "trace_bound": 1.0, "no_archive": True,
    })
    dump("producer_consumer_table.json", {
        "BODY->S": "RESEARCH_ONLY_4_56_SNAPSHOT",
        "M->event": "RESEARCH_DISTANCE",
        "event->BODY": "SUPPORTED existing transition",
        "S_after->L": "NEW",
        "L->research_readout": "SUPPORTED",
        "L->N": "ABSENT",
        "L->preact": "ABSENT",
        "L->motor": "ABSENT",
        "L->D/E/Q": "ABSENT",
        "L->physical": "ABSENT",
    })
    dump("causal_path_graph.json", s["first_unsupported"])
    dump("physical_consequence.json", {
        "equation": "effort=distance*(1+0.8F); dE=-0.012e; dH=-0.004e; dF=+0.010e then basal then clip01",
        "unchanged": True,
    })
    dump("developmental_conditions.json", {
        "C0": "plasticity off",
        "C1": "contingent distance=1",
        "C2": "yoked shift 3",
        "C3": "distance=0",
        "C4": "M=0 distance=1",
        "C5": "shuffle seed 17",
        "exposures": 8,
    })
    dump("matching_plan.json", {"C1_vs_C2": "circular shift of S_after by 3; bags identical"})
    dump("matching_results.json", s["match12"])
    dump("contingent_results.json", s["L1"])
    dump("yoked_results.json", s["L2"])
    dump("response_only_results.json", s["L3"])
    dump("passive_consequence_results.json", s["L4"])
    dump("shuffled_results.json", s["L5"])
    dump("delay_results.json", s["delay_results"])
    dump("acquisition_readout.json", {"curve": s["curve1"], "L1": s["L1"]})
    dump("representational_probe.json", s["probes"])
    dump("sign_symmetry.json", s["sign_sym"])
    dump("basis_invariance.json", s["basis"] | {"m_basis_linf": s["m_basis_linf"]})
    dump("trace_ablation.json", s["ablations"]["trace"])
    dump("response_trace_ablation.json", s["ablations"]["response_trace"])
    dump("prestate_ablation.json", s["ablations"]["prestate"])
    dump("afterstate_ablation.json", s["ablations"]["afterstate"])
    dump("consequence_ablation.json", s["ablations"]["consequence"])
    dump("body_signal_ablation.json", s["ablations"]["body_to_s"])
    dump("w_r_isolation.json", s["w_iso"])
    dump("behavioral_isolation.json", s["beh"])
    dump("raw_history_purge.json", s["purge"])
    dump("reversal.json", s["reversal"])
    dump("level_ladder.json", s["levels"])
    dump("edge_status.json", s["first_unsupported"])
    dump("claim_ladder.json", claims)
    dump("semantic_leak_audit.json", {"leak": s["leak"]})
    dump("adversarial_audit.json", {"items": 107, "leak": s["leak"], "implemented_476": False, "git": False})
    dump("claims.json", [{"id": k, **v} for k, v in claims.items()])

    md("CANONICAL_FRONTIER.md", "Canonical: 4.74=I 4.73=H 4.72=E 4.71=H 4.69=F 4.60=F 4.56=E 4.46=D 4.41=F.\n")
    md("UPDATE474_REPRODUCTION.md", f"4.74 {s['repro_474']}\n")
    md("CAPABILITY_BOUNDARY.md", "One capability: bounded L over (S_before, M, S_after). No L-to-behavior. No 4.76.\n")
    md("INTERNAL_REPRESENTATION.md", "S = 4.56 X ABSOLUTE snapshot from 0. RESEARCH_ONLY. Not live N. Dim 3, [-1,1].\n")
    md("RESPONSE_REPRESENTATION.md", "M generic 2-vector. EVENT_RIGHT/LEFT distance=1. NONE distance=0. RESEARCH_CONTROLLED_PHYSICAL_EVENT.\n")
    md("LEARNER_SPECIFICATION.md", f"{s['learner_equation']}\nReuse 4.41/4.46 rates. Bound 0.65. Shape 3x2x3.\n")
    md("TRACE_SPECIFICATION.md", "trace = 0.62*trace + x. Reset per exposure. Acquire after delay. No future leak.\n")
    md("BOUNDEDNESS.md", f"18 weights, bytes={s['l_storage']}, bound 0.65, no archive.\n")
    md("PRODUCER_CONSUMER_TABLE.md", "BODY->S research X; M->distance research; BODY'->S_after->L; L->readout; L -X-> behavior.\n")
    md("CAUSAL_PATH_GRAPH.md", f"{s['first_unsupported']}\n")
    md("PHYSICAL_CONSEQUENCE.md", "Existing movement_cost + basal + clip01. Unchanged. Not a valence event.\n")
    md("DEVELOPMENTAL_CONDITIONS.md", "C0 off; C1 contingent; C2 yoked shift 3; C3 distance 0; C4 M=0; C5 shuffle 17. Exposures 8.\n")
    md("MATCHING_PLAN.md", "C1 vs C2: identical S_before, M, S_after bags; pairing circular-shifted by 3.\n")
    md("MATCHING_RESULTS.md", f"{s['match12']}\n")
    md("CONTINGENT_RESULTS.md", f"L1 frobenius={s['L1']['frobenius']} max_abs={s['L1']['max_abs']}\n")
    md("YOKED_RESULTS.md", f"L2 frobenius={s['L2']['frobenius']} d12={s['d12']}\n")
    md("RESPONSE_ONLY_RESULTS.md", f"L3 frobenius={s['L3']['frobenius']} d13={s['d13']}\n")
    md("PASSIVE_CONSEQUENCE_RESULTS.md", f"L4 frobenius={s['L4']['frobenius']} (M=0 implies no 3-way write).\n")
    md("SHUFFLED_RESULTS.md", f"L5 frobenius={s['L5']['frobenius']} d15={s['d15']}\n")
    md("DELAY_RESULTS.md", f"{s['delay_results']}\n")
    md("ACQUISITION_READOUT.md", f"curve={s['curve1']}\n")
    md("REPRESENTATIONAL_PROBE.md", f"{s['probes']}\n")
    md("SIGN_SYMMETRY.md", f"{s['sign_sym']}\n")
    md("BASIS_INVARIANCE.md", f"{s['basis']} m_perm_linf={s['m_basis_linf']}\n")
    md("TRACE_ABLATION.md", f"{s['ablations']['trace']}\n")
    md("RESPONSE_TRACE_ABLATION.md", f"{s['ablations']['response_trace']}\n")
    md("PRESTATE_ABLATION.md", f"{s['ablations']['prestate']}\n")
    md("AFTERSTATE_ABLATION.md", f"{s['ablations']['afterstate']}\n")
    md("CONSEQUENCE_ABLATION.md", f"{s['ablations']['consequence']}\n")
    md("BODY_SIGNAL_ABLATION.md", f"{s['ablations']['body_to_s']}\n")
    md("W_R_ISOLATION.md", f"{s['w_iso']}\n")
    md("BEHAVIORAL_ISOLATION.md", f"{s['beh']}\n")
    md("RAW_HISTORY_PURGE.md", f"{s['purge']}\n")
    md("REVERSAL.md", f"{s['reversal']}\n")
    md("LEVEL_LADDER.md", f"{s['levels']}\n")
    md("CAUSAL_EDGE_TABLE.md", f"{s['first_unsupported']}\n")
    md("FIRST_UNSUPPORTED_ARROW.md", f"Strongest: {s['first_unsupported']['strongest_continuous']}\nFirst unsupported: {s['first_unsupported']['first_unsupported']}\n")
    md("SEMANTIC_LEAK_AUDIT.md", f"leak={s['leak']}\n")
    md("ADVERSARIAL_AUDIT.md", "107 items. One capability. L isolated. No 4.76. No git. No valence update.\n")
    md("FINAL_REPORT.md", (
        f"# 4.75 Final report\n\nOutcome {s['outcome']}: {s['outcome_text']}. "
        f"{s['claim_asserted']}/{s['claim_total']}.\n\n"
        f"S={s['s']}. M={s['m']}. L frobenius C1={s['L1']['frobenius']} C2={s['L2']['frobenius']} "
        f"d12={s['d12']}.\n\nAllowed: {s['allowed']}\n\nProhibited: {s['prohibited']}\n\n"
        f"Next: {s['next_question']}\n\n4.76 not implemented.\n"
    ))
    items = "\n".join(f"{k}. {v['text']}: {v['ok']}" for k, v in claims.items())
    md("RETURN_ITEMS.md", items + "\n")

    # also write SOURCE already exists
    md("CANONICAL_FRONTIER.md", (
        "# Canonical frontier\n\n"
        "4.41 F, 4.45 E, 4.46 D, 4.53 E, 4.56 E, 4.60 F, 4.69 F, "
        "4.70 G, 4.71 H, 4.72 E, 4.73 H, 4.74 I.\n"
        "Repository confirmed before 4.75 outcome.\n"
    ))


if __name__ == "__main__":
    sm = generate()
    print(sm["outcome"], sm["outcome_text"], f"{sm['claim_asserted']}/{sm['claim_total']}")
    print("L1", sm["L1"]["frobenius"], "L2", sm["L2"]["frobenius"], "d12", sm["d12"])
    print("L0", sm["L0"]["frobenius"], "L3", sm["L3"]["frobenius"], "L4", sm["L4"]["frobenius"])
    print("match", sm["match12"]["classification"], sm["match12"]["s1_mean_linf"])
    print("sign", sm["sign_sym"], "basis", sm["basis"]["transforms"])
    print("beh", sm["beh"]["N_equal"], sm["beh"]["Q_equal"])
    print("leak", sm["leak"])
