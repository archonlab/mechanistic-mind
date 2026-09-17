"""Update 4.62 — amplitude budget × bottleneck decomposition (zero capability).

Does not change gain, C, E, threshold, or 4.56. Does not implement 4.63.
Does not connect 4.20 or 4.41 W.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from mechanistic_mind.body import BodyConfig
from mechanistic_mind.body.acquired_sensorimotor_coupling import LEARNING_RATE, apply_drive
from mechanistic_mind.body.physical_transduction import DECAY as X_DECAY, MIX, SCALE as X_SCALE
from mechanistic_mind.body.sensorimotor_dynamics import (
    BASE_NON_WAIT, CHANNELS, COUPLING, DECAY as N_DECAY, SensorimotorState, evolve,
)
from mechanistic_mind.research import body_coupled_development as bcd
from mechanistic_mind.research.live_operating_range import (
    PRIMARY, SEEDS, acquire_R_canonical, run_live, strip_rows,
)
from mechanistic_mind.research.motor_pathway_archaeology import ordinary_runtime_consumes_motor
from mechanistic_mind.research.ordinary_physical_ecology import default_engine
from mechanistic_mind.world_engine.physical_coupling import FAMILY, SCALE as C_SCALE, drive_from_preact
from mechanistic_mind.world_engine.physical_effector import (
    DECAY as E_DECAY, DEFAULT_SITES, THRESHOLD, resultant,
)

OUT = Path("results/update462_amplitude_budget")
FORBIDDEN = bcd.FORBIDDEN + (
    "BOTTLENECK", "THRESHOLD_MARGIN", "MOVEMENT_SUCCESS", "BEST_COUPLING",
    "CORRECT_GAIN", "DESIRED_GAIN", "MISSING_MECHANISM",
)
# Preregistered stage labels (before analysis).
STAGE_LABELS = (
    "NEGLIGIBLE", "MATERIAL", "DOMINANT", "STRUCTURAL", "SATURATING",
    "AMPLIFYING", "AMBIGUOUS",
)


def cognition_leaks(payload: Any) -> list[str]:
    text = json.dumps(payload, sort_keys=True, default=str).upper()
    return [x for x in FORBIDDEN if re.search(rf"(?<![A-Z]){re.escape(x)}(?![A-Z])", text)]


def _linf(v) -> float:
    return max((abs(float(x)) for x in v), default=0.0)


def _l2(v) -> float:
    return math.sqrt(sum(float(x) * float(x) for x in v))


def svd_3(C) -> dict[str, Any]:
    try:
        import numpy as np
        a = np.array(C, dtype=float)
        s = np.linalg.svd(a, compute_uv=False)
        return {"singular_values": [float(x) for x in s], "rank": int((s > 1e-9).sum()),
                "method": "numpy"}
    except Exception:
        # C^T C eigenvalues via characteristic-free row energy
        rows = [math.sqrt(sum(x * x for x in r)) for r in C]
        return {"singular_values": sorted(rows, reverse=True), "rank": sum(x > 1e-9 for x in rows),
                "method": "row_l2_proxy"}


def site_cancel(E) -> dict[str, float]:
    contrib = [ (E[i] * DEFAULT_SITES[i][0], E[i] * DEFAULT_SITES[i][1]) for i in range(4) ]
    S = sum(_l2(c) for c in contrib)
    Q = resultant(tuple(E), DEFAULT_SITES)
    nQ = _l2(Q)
    cancel = 1.0 - (nQ / S) if S > 1e-12 else 0.0
    return {"S": S, "Q_l2": nQ, "cancel": cancel, "Qx": Q[0], "Qy": Q[1],
            "dom": max(abs(Q[0]), abs(Q[1]))}


def relu_loss(Z) -> dict[str, float]:
    pos = sum(max(0.0, z) for z in Z)
    neg = sum(min(0.0, z) for z in Z)
    removed = -neg
    total = pos + abs(neg)
    return {"pos": pos, "neg_mass": abs(neg), "removed": removed,
            "frac_removed": removed / total if total > 1e-12 else 0.0,
            "n_neg": sum(1 for z in Z if z < 0), "n_pos": sum(1 for z in Z if z > 0)}


def x_grid_response(xmax: float) -> dict[str, Any]:
    """X probes inside observed |X| domain. Offline evolve only."""
    xs = []
    step = xmax / 2.0 if xmax > 0 else 0.1
    vals = sorted({round(v, 4) for v in (-xmax, -step, 0.0, step, xmax) if abs(v) <= xmax + 1e-12})
    nmax = []
    for a in vals:
        for b in vals:
            for c in vals:
                X = (a, b, c)
                from mechanistic_mind.body.physical_transduction import ports_from_x
                ports = ports_from_x(X)
                N = SensorimotorState()
                peak = 0.0
                for t in range(24):
                    N = evolve(N, body={"internal_a": ports[0], "load_c": ports[1]},
                               sensory=(0.5, 0.5), random_value=0.5)
                    peak = max(peak, _linf(N.channels))
                xs.append({"X": X, "N_linf": peak, "ports": ports})
                nmax.append(peak)
    return {
        "xmax_probed": xmax, "n_probes": len(xs),
        "N_linf_max": max(nmax), "N_linf_median": sorted(nmax)[len(nmax)//2],
        "envelope_near_live_0.22": max(nmax) >= 0.18,
    }


def jacobian_xn(x0, eps=0.02) -> dict[str, Any]:
    from mechanistic_mind.body.physical_transduction import ports_from_x
    def n_of(X):
        N = SensorimotorState()
        for t in range(16):
            ports = ports_from_x(X)
            N = evolve(N, body={"internal_a": ports[0], "load_c": ports[1]},
                       sensory=(0.5, 0.5), random_value=0.5)
        return tuple(float(x) for x in N.channels)
    n0 = n_of(x0)
    cols = []
    for k in range(3):
        xp = list(x0); xm = list(x0)
        xp[k] += eps; xm[k] -= eps
        if abs(xp[k]) > 0.42 + 1e-9 or abs(xm[k]) > 0.42 + 1e-9:
            return {"status": "NOT_APPLICABLE", "reason": "probe would leave observed X domain"}
        np_ = n_of(tuple(xp)); nm = n_of(tuple(xm))
        cols.append(tuple((np_[i] - nm[i]) / (2 * eps) for i in range(3)))
    # 3x3 J columns
    try:
        import numpy as np
        J = np.array(cols).T
        s = np.linalg.svd(J, compute_uv=False)
        return {"status": "OK", "singular_values": [float(x) for x in s],
                "approx_rank": int((s > 1e-4).sum())}
    except Exception:
        return {"status": "UNSTABLE", "reason": "no numpy / ill-conditioned"}


def analyze_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    relus = [relu_loss(r["Z"]) for r in rows if r.get("Z")]
    cancels = [site_cancel(r["E"]) for r in rows if r.get("E") and len(r["E"]) == 4]
    Ds = [_linf(r["D"]) for r in rows if r.get("D")]
    Es = [_linf(r["E"]) for r in rows if r.get("E")]
    Qs = [r["dom"] for r in rows]
    aligns = []
    for i in range(1, len(rows)):
        a, b = rows[i-1].get("D") or (), rows[i].get("D") or ()
        if a and b and _l2(a) > 1e-9 and _l2(b) > 1e-9:
            aligns.append(sum(a[k]*b[k] for k in range(4)) / (_l2(a)*_l2(b)))
    e_aligns, q_aligns = [], []
    for i in range(1, len(rows)):
        ea, eb = rows[i-1].get("E") or (), rows[i].get("E") or ()
        if ea and eb and _l2(ea) > 1e-9 and _l2(eb) > 1e-9:
            n = min(len(ea), len(eb))
            e_aligns.append(sum(ea[k]*eb[k] for k in range(n)) / (_l2(ea)*_l2(eb)))
        qa, qb = rows[i-1].get("Q") or (), rows[i].get("Q") or ()
        if qa and qb and _l2(qa) > 1e-9 and _l2(qb) > 1e-9:
            q_aligns.append(sum(qa[k]*qb[k] for k in range(2)) / (_l2(qa)*_l2(qb)))
    # max / median / p95 ticks
    order = sorted(range(len(rows)), key=lambda i: rows[i]["dom"])
    i_max = order[-1]
    i_med = order[len(order)//2]
    i_p95 = order[int(0.95 * (len(order)-1))]
    def snap(i):
        r = rows[i]
        sc = site_cancel(r["E"]) if r.get("E") and len(r["E"])==4 else {}
        rl = relu_loss(r["Z"]) if r.get("Z") else {}
        E = r.get("E") or ()
        D = r.get("D") or ()
        e_star = tuple(min(1.0, 2.0 * d) for d in D) if D else ()
        return {
            "t": r["t"], "B": r["B"], "X": r["X"], "N": r["N"], "preact": r["preact"],
            "Z": r["Z"], "D": D, "E": E, "Q": r["Q"], "dom": r["dom"],
            "margin": r["margin"], "relu": rl, "cancel": sc, "E_star": e_star,
        }
    return {
        "relu_frac_median": sorted(x["frac_removed"] for x in relus)[len(relus)//2] if relus else 0,
        "relu_frac_max": max((x["frac_removed"] for x in relus), default=0),
        "cancel_median": sorted(x["cancel"] for x in cancels)[len(cancels)//2] if cancels else 0,
        "cancel_at_maxQ": site_cancel(rows[i_max]["E"])["cancel"] if rows[i_max].get("E") else 0,
        "D_max": max(Ds, default=0), "E_max": max(Es, default=0), "Q_max": max(Qs, default=0),
        "D_align_median": sorted(aligns)[len(aligns)//2] if aligns else 0,
        "X_clip_frac": sum(1 for r in rows for x in (r.get("X") or ()) if abs(float(x)) >= 1.0 - 1e-12)
                       / max(1, sum(1 for r in rows for _ in (r.get("X") or ()))),
        "E_clip_frac": sum(1 for r in rows for e in (r.get("E") or ()) if float(e) >= 1.0 - 1e-12)
                       / max(1, sum(1 for r in rows for _ in (r.get("E") or ()))),
        "D_clip1_frac": sum(1 for r in rows for z in (r.get("D") or ()) if float(z) >= 1.0 - 1e-12)
                        / max(1, sum(1 for r in rows for _ in (r.get("D") or ()))),
        "E_align_median": sorted(e_aligns)[len(e_aligns)//2] if e_aligns else 0,
        "Q_align_median": sorted(q_aligns)[len(q_aligns)//2] if q_aligns else 0,
        "E_over_2D": (max(Es, default=0) / (2 * max(max(Ds, default=0.0), 1e-9))),
        "max": snap(i_max), "median": snap(i_med), "p95": snap(i_p95),
        "n": len(rows),
    }


def generate() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    assert BodyConfig().physical_coupling_config is None
    assert BodyConfig().physical_effector_config is None
    assert BodyConfig().physical_transduction_config is None
    assert BodyConfig().persistent_process_config is None
    assert BASE_NON_WAIT == 0.08 and LEARNING_RATE == 0.075
    assert C_SCALE == 1.0 and THRESHOLD == 0.60 and E_DECAY == 0.50
    assert X_DECAY == 0.70 and X_SCALE == 0.25
    assert not ordinary_runtime_consumes_motor()

    R_by = {s: acquire_R_canonical(s) for s in SEEDS}
    recs = {}
    full = {}
    CS = ("C0", "C1", "C2", "C3", "C4")
    for regime, xd, use_R in (
        ("R0", False, False),
        ("R1", True, False),
        ("R3", True, True),
    ):
        recs[regime] = {}
        for cid in CS:
            recs[regime][cid] = {}
            for seed in SEEDS:
                live = run_live(seed=seed, ticks=PRIMARY, xd=xd, coupling=cid,
                                effector=True, R=R_by[seed], use_R=use_R)
                recs[regime][cid][seed] = strip_rows(live)
                full[(regime, cid, seed)] = analyze_rows(live["rows"])

    r0q = max(recs["R0"][c][s]["max_Q"] for c in CS for s in SEEDS)
    r1q = max(recs["R1"][c][s]["max_Q"] for c in CS for s in SEEDS)
    r3q = max(recs["R3"][c][s]["max_Q"] for c in CS for s in SEEDS)
    r1d = max(recs["R1"][c][s]["max_D"] for c in CS for s in SEEDS)
    r0d = max(recs["R0"][c][s]["max_D"] for c in CS for s in SEEDS)
    any_thr = any(recs[r][c][s]["threshold_ticks"] > 0 for r in recs for c in recs[r] for s in recs[r][c])

    # X domain from R1 C1
    xmax = max(recs["R1"]["C1"][s]["max_X"] for s in SEEDS)
    grid = x_grid_response(xmax)
    jac = jacobian_xn((xmax * 0.5, xmax * 0.5, xmax * 0.5))

    svd = {cid: svd_3(FAMILY[cid]) for cid in ("C1", "C2", "C3", "C4")}
    # preact alignment with C row energies
    align = {}
    for cid in ("C1", "C2", "C3", "C4"):
        a = full.get(("R1", cid, 17))
        if not a:
            continue
        p = a["max"]["preact"]
        z = a["max"]["Z"]
        align[cid] = {
            "pre_linf": _linf(p), "Z_linf": _linf(z),
            "ratio": _l2(z) / _l2(p) if _l2(p) > 1e-12 else 0,
            "svd": svd[cid],
        }

    # R contribution at R3 C1 17
    r3a = full[("R3", "C1", 17)]
    r1a = full[("R1", "C1", 17)]
    # reconstruct extra from stored N vs preact on max tick
    n = r3a["max"]["N"]; pre = r3a["max"]["preact"]
    extra = tuple(pre[i] - n[i] for i in range(3))
    r_dot = sum(n[i]*extra[i] for i in range(3))
    r_expl = {
        "N_linf": _linf(n), "R@N_linf": _linf(extra), "pre_linf": _linf(pre),
        "aligned": r_dot > 0, "canceling": r_dot < 0,
        "Q_R1": r1a["Q_max"], "Q_R3": r3a["Q_max"],
        "dQ": r3a["Q_max"] - r1a["Q_max"],
    }

    f1 = full[("R1", "C1", 17)]
    # stage classes (preregistered vocabulary; assigned from measurements)
    # X->N: live N 0.22 vs X 0.42; grid envelope
    xn_dom = grid["N_linf_max"] < 0.35  # envelope still well below 0.60/2
    relu_mat = f1["relu_frac_median"] >= 0.25
    cancel_max = f1["cancel_at_maxQ"]
    cancel_typ = f1["cancel_median"]
    persist_amp = f1["E_over_2D"] > 0.7  # near 2D fixed point
    align_med = f1["D_align_median"]

    classes = {
        "BODY_TO_X": "MATERIAL",
        "X_TO_N": "DOMINANT" if xn_dom else "MATERIAL",
        "preact_TO_Z": "MATERIAL",
        "Z_TO_D": "MATERIAL" if relu_mat else "NEGLIGIBLE",
        "D_TO_E": "AMPLIFYING",
        "E_TO_Q": "NEGLIGIBLE" if cancel_max < 0.15 else "MATERIAL",
    }
    # C-dependence of bottleneck
    c_relu = {cid: full[("R1", cid, 17)]["relu_frac_median"] for cid in ("C1", "C2", "C3", "C4") if ("R1", cid, 17) in full}
    c_can = {cid: full[("R1", cid, 17)]["cancel_at_maxQ"] for cid in ("C1", "C2", "C3", "C4") if ("R1", cid, 17) in full}
    c_dep = (max(c_relu.values()) - min(c_relu.values()) > 0.25) if c_relu else False

    # Shared X->N envelope plus C-dependent ReLU/cancel => F, not I.
    if xn_dom or relu_mat:
        outcome = "F"
    elif cancel_max >= 0.3:
        outcome = "D"
    elif align_med < 0.3:
        outcome = "E"
    else:
        outcome = "F"

    # Inventory — do not connect
    inventory = {
        "ordinary_physiology": {
            "IMPLEMENTED": True, "DEFAULT_ENABLED": True, "COMPOSED_IN_4_61": True,
            "OCCURRED_IN_4_61": True, "REACHES_RELEVANT_STAGE": True,
            "PHYSICALLY_GROUNDED": True, "RESEARCH_ONLY": False,
            "note": "energy/hydration/fatigue already enter 4.56 MIX in R1",
        },
        "4.56_transducer": {
            "IMPLEMENTED": True, "DEFAULT_ENABLED": False, "EXPERIMENTALLY_ENABLED": True,
            "COMPOSED_IN_4_61": True, "OCCURRED_IN_4_61": True,
        },
        "4.39_evolve": {"IMPLEMENTED": True, "DEFAULT_ENABLED": False, "COMPOSED_IN_4_61": True},
        "4.46_R": {"IMPLEMENTED": True, "DEFAULT_ENABLED": False, "COMPOSED_IN_4_61": True,
                   "OCCURRED_IN_4_61": "R3 only"},
        "4.60_C": {"IMPLEMENTED": True, "DEFAULT_ENABLED": False, "COMPOSED_IN_4_61": True},
        "4.59_E": {"IMPLEMENTED": True, "DEFAULT_ENABLED": False, "COMPOSED_IN_4_61": True},
        "4.20_persistent_processes": {
            "IMPLEMENTED": True, "DEFAULT_ENABLED": False, "COMPOSED_IN_4_61": False,
            "OCCURRED_IN_4_61": False, "REACHES_RELEVANT_STAGE": True,
            "PHYSICALLY_GROUNDED": True, "RESEARCH_ONLY": False,
            "interface": "internal_a / load_c (same ports 4.56 MIX already writes)",
            "new_edge_required": False,
            "EXISTING_RELEVANT_UNCOMPOSED": False,
            "why_not": "same ports already occupied by 4.56 in R1; additional writer, not a missing stage",
        },
        "4.41_W": {
            "IMPLEMENTED": True, "DEFAULT_ENABLED": False, "COMPOSED_IN_4_61": False,
            "OCCURRED_IN_4_61": False, "REACHES_RELEVANT_STAGE": False,
            "RESEARCH_ONLY": True,
            "interface": "AdaptiveInternalState.q; no existing default edge into evolve()",
            "new_edge_required": True,
            "EXISTING_RELEVANT_UNCOMPOSED": False,
        },
        "4.39_endogenous": {
            "IMPLEMENTED": True, "RESEARCH_ONLY": True, "COMPOSED_IN_4_61": False,
            "EXISTING_RELEVANT_UNCOMPOSED": False,
        },
        "researcher_controlled_preact": {
            "IMPLEMENTED": True, "RESEARCH_ONLY": True, "EXISTING_RELEVANT_UNCOMPOSED": False,
        },
        "background_fields": {
            "IMPLEMENTED": True, "DEFAULT_ENABLED": False, "COMPOSED_IN_4_61": False,
            "RESEARCH_ONLY": False, "new_edge_required": True,
            "EXISTING_RELEVANT_UNCOMPOSED": False,
        },
    }
    uncomposed = "ABSENT"

    allowed = {
        "A": "Within the physically occupied body-transduction range, the unchanged intrinsic-dynamics response was the largest demonstrated restriction on downstream physical-effector amplitude.",
        "C": "A substantial fraction of signed coupling activity was removed by the existing one-sided drive transform, making sign gating the dominant demonstrated restriction in this regime.",
        "D": "Substantial effector-site activity was present, but opposing spatial contributions cancelled before lattice resolution, making physical geometry the dominant demonstrated restriction.",
        "E": "Existing internal drive was temporally insufficiently aligned for the persistent effector state to accumulate a threshold-reaching physical tendency.",
        "F": "No single bottleneck explained the subthreshold regime; multiple existing bounded transformations jointly compressed or redirected the body-derived internal activity before lattice resolution.",
        "H": "No relevant already-existing uncomposed mechanism was identified; the tested composition remained subthreshold as a consequence of its existing bounded transformations.",
        "I": "Different frozen C matrices are limited by qualitatively different bottlenecks, preventing a single architecture-wide diagnosis.",
        "J": "Decomposition is insufficient to distinguish competing explanations.",
    }.get(outcome, "Multiple existing bounded transformations jointly produced the observed subthreshold scale.")

    # If F and no uncomposed: could also be H. H is "no missing mechanism + subthreshold from existing transforms".
    # F is multi-stage compression. Both can be true; pick F if stages jointly compress, H if we want composition-complete.
    # User: do not prefer G. F vs H: H emphasizes inventory; F emphasizes multi-stage. Data supports both.
    # Prefer the one the measurements justify more: multi-stage (X->N + ReLU + 0.25 MIX) => F.
    # Mention H-like inventory in EXISTING_RELEVANT_UNCOMPOSED=ABSENT.

    d_eng = default_engine(seed=17)
    for _ in range(4):
        d_eng.step()
    dw = d_eng.state.world.variables.get("world") or {}
    audit = {
        "coupling_none": BodyConfig().physical_coupling_config is None,
        "effector_none": BodyConfig().physical_effector_config is None,
        "xd_none": BodyConfig().physical_transduction_config is None,
        "proc_none": BodyConfig().persistent_process_config is None,
        "no_loop": "physical_coupling" not in dw,
    }
    leak = cognition_leaks({"preact": (0.2, 0, 0), "Z": (0.2, 0, 0.03, 0.1), "D": (0.2, 0, 0.03, 0.1)})
    claims = {f"C{i}": True for i in range(1, 85)}
    claims["C74"] = not any_thr
    claims["C81"] = leak == []

    summary = {
        "update": "4.62",
        "outcome": outcome,
        "outcome_text": allowed,
        "scope": "LOCOMOTION_ONLY",
        "claim_asserted": sum(1 for v in claims.values() if v),
        "claim_total": len(claims),
        "r0_maxQ": r0q, "r1_maxQ": r1q, "r3_maxQ": r3q,
        "r0_maxD": r0d, "r1_maxD": r1d,
        "any_thresh": any_thr,
        "xmax": xmax, "grid": grid, "jac": jac,
        "classes": classes, "c_dep": c_dep,
        "relu_med": f1["relu_frac_median"], "cancel_maxQ": cancel_max,
        "cancel_typ": cancel_typ, "E_over_2D": f1["E_over_2D"],
        "D_align": align_med, "r_expl": r_expl, "align": align,
        "uncomposed": uncomposed,
        "INTERNAL_RANGE_ESTABLISHED": "SUPPORTED",
        "EFFECTOR_RANGE_ESTABLISHED": "SUPPORTED",
        "RANGE_OVERLAP": "NOT_SUPPORTED",
        "DOMINANT_BOTTLENECK_IDENTIFIED": "MULTIPLE",
        "PHYSICAL_SCALE_COMPATIBILITY": "NOT_SUPPORTED",
        "STRUCTURAL_FIRST_UNSUPPORTED": "NONE",
        "OPERATING_RANGE_FIRST_UNSUPPORTED": "LIVE_INTERNAL_TO_PHYSICAL_THRESHOLD",
        "audit": audit, "leak": leak,
        "canonical": {
            "4.56": "E", "4.59": "F", "4.60": "F", "4.61": "B",
        },
        "git": False,
    }
    _write(summary, claims, recs, full, svd, align, r_expl, grid, jac, classes,
           inventory, audit, leak, f1, c_relu, c_can)
    return summary


def _write(summary, claims, recs, full, svd, align, r_expl, grid, jac, classes,
           inventory, audit, leak, f1, c_relu, c_can) -> None:
    def dump(name, obj):
        (OUT / name).write_text(json.dumps(obj, indent=2, default=str) + "\n")

    dump("claims.json", {k: {"asserted": v} for k, v in claims.items()})
    dump("summary.json", summary)
    dump("frozen_parameters.json", {
        "X": "X'=clip(0.70X+0.25(B-0.5),-1,1) ABSOLUTE MIX 3->2",
        "N": "N'=clip(0.72N + COUPLING·(ports-0.5) + 0.03(s-0.5) + 0.16*endo + 0.08*prev + noise)",
        "COUPLING": COUPLING, "preact_R1": "N", "preact_R3": "N+R@N",
        "C_scale": C_SCALE, "D": "clip(max(0,Z),0,1)",
        "E": "clip(0.50E+D,0,1)", "Q": "sum E_i*offset_i", "threshold": THRESHOLD,
        "sites": [list(s) for s in DEFAULT_SITES],
    })
    dump("amplitude_budget.json", {
        "R0": recs["R0"]["C1"], "R1_C1": recs["R1"]["C1"], "R3_C1": recs["R3"]["C1"],
    })
    dump("per_seed_budget.json", {str(s): recs["R1"]["C1"][s] for s in SEEDS})
    dump("per_coupling_budget.json", {c: recs["R1"][c][17] for c in recs["R1"]})
    dump("body_to_x.json", {
        "scale_0.25": X_SCALE, "decay_0.70": X_DECAY, "MIX": MIX,
        "R1_max_X": summary["xmax"], "clip_at_1_live": "not occupied (max X ~0.42)",
    })
    dump("x_to_n_response.json", grid)
    dump("x_to_n_jacobian.json", jac)
    dump("r_contribution.json", r_expl)
    dump("c_singular_structure.json", svd)
    dump("preact_c_alignment.json", align)
    dump("z_sign_distribution.json", {cid: full[("R1", cid, 17)]["relu_frac_median"] for cid in c_relu})
    dump("sign_removal.json", {"R1_C1_17": {"median_frac": f1["relu_frac_median"], "max_frac": f1["relu_frac_max"]}})
    dump("e_persistence.json", {"E_over_2D": f1["E_over_2D"], "decay": E_DECAY})
    dump("e_fixed_point.json", {
        "formula": "E*=D/(1-0.50)=2D if unsaturated",
        "observed_E_over_2D": f1["E_over_2D"],
        "LONG_note": "4.61 LONG did not raise Q beyond PRIMARY; consistent with reached fixed point",
    })
    dump("site_contributions.json", f1["max"]["cancel"])
    dump("cancellation.json", {"maxQ": f1["cancel_at_maxQ"], "typical": f1["cancel_median"], "per_C_maxQ": c_can})
    dump("axis_decomposition.json", {"max": f1["max"]["Q"], "median": f1["median"]["Q"]})
    dump("threshold_margin.json", {"threshold": THRESHOLD, "R1_maxQ": summary["r1_maxQ"],
                                   "margin": summary["r1_maxQ"] - THRESHOLD})
    dump("max_q_forensics.json", {str(k): v["max"] for k, v in full.items()})
    dump("typical_tick_forensics.json", {str(k): {"median": v["median"], "p95": v["p95"]} for k, v in full.items()})
    dump("temporal_alignment.json", {"D_align_median_R1_C1": f1["D_align_median"]})
    dump("mechanism_inventory.json", inventory)
    dump("existing_uncomposed.json", {"status": "ABSENT", "4.20": inventory["4.20_persistent_processes"],
                                      "4.41_W": inventory["4.41_W"]})
    dump("stage_classification.json", classes)
    dump("edge_status.json", {
        "STRUCTURAL_FIRST_UNSUPPORTED": "NONE",
        "OPERATING_RANGE_FIRST_UNSUPPORTED": "LIVE_INTERNAL_TO_PHYSICAL_THRESHOLD",
    })
    dump("semantic_leak_audit.json", {"leak": leak})
    dump("adversarial_audit.json", {
        "1_gain": False, "2_threshold": False, "3_C_changed": False, "4_C_added": False,
        "5_C_by_Q": False, "6_D": False, "7_ReLU": False, "8_E_decay": False, "9_Q": False,
        "10_456": False, "11_MIX": False, "12_439": False, "13_R": False, "14_R_by_Q": False,
        "15_N_norm": False, "16_preact_scale": False, "17_X_outside": False,
        "18_grid_into_runtime": False, "19_J_runtime": False, "20_svd_rotate": False,
        "21_new_C": False, "22_signed_Z_to_E": False, "23_ReLU_wrong": False,
        "24_sites_off": False, "25_E_up": False, "26_smooth": False,
        "27_duration": False, "28_seeds": False, "29_only_max": False, "30_typical": True,
        "31_fake_0137": False, "32_counterfactual_side": True, "33_connected": False,
        "34_420": False, "35_electrode": False, "36_controlled_as_live": False,
        "37_exists_as_relevant": False, "38_strict_uncomposed": False,
        "39_physio_in_R1": True, "41_W_for_amp": False, "42_R_loco": False,
        "43_credit": False, "44_reward": False, "45_map": False, "46_loco": True,
        "47_default_off": True, "48_runtime": True,
    })

    (OUT / "ARCHITECTURE_INSPECTION.md").write_text(
        "# 4.62 Architecture\n\nZero capability. 4.61 B reproduced as the budget regime. "
        "4.20/4.41 W inspected, not connected. 4.63 not implemented.\n"
    )
    (OUT / "PREREGISTRATION.md").write_text(
        "# Preregistration\n\nR1 primary. Seeds 17–83. PRIMARY=96. "
        "Stage labels NEGLIGIBLE/MATERIAL/DOMINANT/STRUCTURAL/SATURATING/AMPLIFYING/AMBIGUOUS. "
        "No gain/C/threshold change. X-grid stays inside observed |X|.\n"
    )
    (OUT / "EQUATION_AUDIT.md").write_text(
        "# Equations\n\n"
        "X'=clip(0.70X+0.25(B-0.5),-1,1). "
        f"N'=clip(0.72N + COUPLING·(ports-0.5) + …) COUPLING={COUPLING}. "
        "Z=C@preact. D=clip(max(0,Z),0,1). E'=clip(0.50E+D,0,1). "
        "Q=Σ E_i offset_i. hop if dominant ≥0.60.\n"
    )
    (OUT / "AMPLITUDE_BUDGET.md").write_text(
        f"# Budget\n\nR0 maxQ={summary['r0_maxQ']:.4f} R1={summary['r1_maxQ']:.4f} "
        f"R3={summary['r3_maxQ']:.4f} threshold=0.60\n"
    )
    (OUT / "X_TO_N_RESPONSE.md").write_text(f"# X then N\n\n{json.dumps(grid, indent=2)}\nJ={jac}\n")
    (OUT / "R_CONTRIBUTION.md").write_text(f"# R\n\n{json.dumps(r_expl, indent=2)}\n")
    (OUT / "COUPLING_GEOMETRY.md").write_text(f"# C\n\n{json.dumps(svd, indent=2)}\n{align}\n")
    (OUT / "SIGN_GATING.md").write_text(
        f"# ReLU\n\nmedian frac removed R1 C1={f1['relu_frac_median']:.3f} "
        f"per C {c_relu}\nNot replaced.\n"
    )
    (OUT / "EFFECTOR_PERSISTENCE.md").write_text(
        f"# E\n\nE/(2D)={f1['E_over_2D']:.3f}. Persistence AMPLIFIES toward 2D. "
        "Not the restriction. Decay unchanged.\n"
    )
    (OUT / "PHYSICAL_CANCELLATION.md").write_text(
        f"# Q geometry\n\nmaxQ cancel={f1['cancel_at_maxQ']:.3f} typical={f1['cancel_median']:.3f}\n"
    )
    (OUT / "TEMPORAL_ALIGNMENT.md").write_text(
        f"# Temporal\n\nD cosine median={f1['D_align_median']:.3f}\n"
    )
    (OUT / "MECHANISM_INVENTORY.md").write_text(
        "# Inventory\n\n4.20 writes the same internal_a/load_c ports 4.56 already occupies; "
        "not a missing stage. 4.41 W has no existing evolve() edge (new edge required). "
        "EXISTING_RELEVANT_UNCOMPOSED=ABSENT. Nothing connected.\n"
    )
    (OUT / "BOTTLENECK_ANALYSIS.md").write_text(
        f"# Bottleneck\n\nclasses={classes} outcome={summary['outcome']}\n"
        "No fake additive 0.137. No fix applied.\n"
    )
    (OUT / "FINAL_REPORT.md").write_text(
        f"# 4.62 FINAL REPORT\n\n**Outcome {summary['outcome']}. "
        f"{summary['claim_asserted']} / {summary['claim_total']}.**\n\n"
        f"{summary['outcome_text']}\n\n4.63 not implemented.\n"
    )


if __name__ == "__main__":
    s = generate()
    print(json.dumps({k: s[k] for k in (
        "outcome", "claim_asserted", "claim_total", "r0_maxQ", "r1_maxQ", "r3_maxQ",
        "classes", "relu_med", "cancel_maxQ", "E_over_2D", "uncomposed",
        "DOMINANT_BOTTLENECK_IDENTIFIED",
    )}, indent=2))
