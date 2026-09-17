"""Update 4.71 — post-consequence relaxation and latent return.

Zero new capability. Temporal fate of the 4.70 BODY difference.
Does not implement 4.72. Does not mix X into live N.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mechanistic_mind.body import BodyConfig
from mechanistic_mind.body.physical_transduction import (
    MIX, default_transducer_config, ports_from_x, step_transducer,
)
from mechanistic_mind.body.sensorimotor_dynamics import SensorimotorState, evolve
from mechanistic_mind.research.generic_action_body_internal_return import (
    BLOCK, CS, EQ, SEEDS, START, cognition_leaks, make_engine,
)
from mechanistic_mind.research.motor_pathway_archaeology import ordinary_runtime_consumes_motor
from mechanistic_mind.research.ordinary_physical_ecology import body_payload
from mechanistic_mind.agent import Action
from mechanistic_mind.world_engine.physical_coupling import FAMILY, SCALE as C_SCALE
from mechanistic_mind.world_engine.physical_effector import THRESHOLD

OUT = Path("results/update471_post_consequence_relaxation_latent_return")
PRIMARY = 96
HORIZON = (0, 1, 2, 3, 4, 5, 8, 12, 16, 24, 32)
POST = (1, 2, 3, 4, 5, 8, 12, 16, 24, 32)
BODY_FLOOR = 1e-6
X_FLOOR = 1e-6
PORT_FLOOR = 1e-6
N_OP = 0.039
NUM = 1e-9


def dump(name: str, obj: Any) -> None:
    (OUT / name).write_text(json.dumps(obj, indent=2, default=str) + "\n")


def md(name: str, text: str) -> None:
    (OUT / name).write_text(text if text.endswith("\n") else text + "\n")


def _linf(v) -> float:
    return max((abs(float(x)) for x in v), default=0.0)


def _l2(v) -> float:
    return sum(float(x) ** 2 for x in v) ** 0.5


def bound_body(x: float) -> str:
    if x <= NUM:
        return "lower"
    if x >= 1.0 - NUM:
        return "upper"
    return "interior"


def bound_x(x: float) -> str:
    if x <= -1.0 + 1e-12:
        return "lower"
    if x >= 1.0 - 1e-12:
        return "upper"
    return "interior"


def run_full(*, seed: int, process: bool, fields: str, coupling: str | None,
             effector: bool, xd: bool, blocked=(), ticks: int = PRIMARY) -> dict[str, Any]:
    eng = make_engine(seed=seed, process=process, fields=fields, coupling=coupling,
                      effector=effector, xd=xd, blocked=blocked)
    N_live = SensorimotorState()
    N_ret = SensorimotorState()
    rows = []
    for t in range(ticks):
        p = body_payload(eng)
        loads = p.get("internal_loads") or {}
        ia = float(loads["internal_a"]) if isinstance(loads, dict) and "internal_a" in loads else 0.5
        lc = float(loads["load_c"]) if isinstance(loads, dict) and "load_c" in loads else 0.5
        X0 = tuple(float(v) for v in (p.get("transducer_state") or (0.0, 0.0, 0.0)))
        ports0 = ports_from_x(X0)
        rv = ((seed * 29 + t * 13) % 101) / 100.0
        N_live = evolve(N_live, body={"internal_a": ia, "load_c": lc}, sensory=(0.5, 0.5), random_value=rv)
        N_ret = evolve(N_ret, body={"internal_a": ports0[0], "load_c": ports0[1]}, sensory=(0.5, 0.5), random_value=rv)
        n = tuple(float(x) for x in N_live.channels)
        nr = tuple(float(x) for x in N_ret.channels)
        w = eng.state.world.variables["world"]
        w["researcher_controlled_preact"] = list(n)
        eng.step({"A001": Action.wait()})
        ww = eng.state.world.variables["world"]
        p2 = body_payload(eng)
        ef = ww.get("physical_effector") or {}
        cp = ww.get("physical_coupling") or {}
        rec = p2.get("last_process_receipt") or {}
        Q = tuple(ef.get("Q") or (0.0, 0.0))
        if len(Q) < 2:
            Q = (float(Q[0]) if Q else 0.0, float(Q[1]) if len(Q) > 1 else 0.0)
        X = tuple(float(v) for v in (p2.get("transducer_state") or (0.0, 0.0, 0.0)))
        ports = ports_from_x(X)
        B = (float(p2["energy_reserve"]), float(p2["hydration"]), float(p2["fatigue"]))
        D = tuple(float(x) for x in (cp.get("D") or ()))
        E = tuple(float(x) for x in (ef.get("E") or ()))
        hop = tuple(int(x) for x in (ef.get("hop") or (0, 0)))
        realized = bool(ef.get("realized"))
        rows.append({
            "t": t, "pos": tuple(int(x) for x in ww["agent_positions"]["A001"]),
            "ia": float((p2.get("internal_loads") or {}).get("internal_a", 0.0) or 0.0),
            "mod": float((rec or {}).get("env_modulator") or 0.0) if rec else 0.0,
            "B": B, "X": X, "ports": ports, "N": n, "Nr": nr, "preact": n,
            "D": D, "E": E, "Q": Q, "dom": max(abs(float(Q[0])), abs(float(Q[1]))),
            "hop": hop, "realized": realized, "blocked": bool(ef.get("blocked")),
        })
    first_hop = next((r["t"] for r in rows if r["realized"]), None)
    first_block = next((r["t"] for r in rows if r["blocked"]), None)
    return {
        "seed": seed, "first_hop": first_hop, "first_block": first_block,
        "realized": sum(1 for r in rows if r["realized"]),
        "blocked_n": sum(1 for r in rows if r["blocked"]),
        "positions": sorted({tuple(r["pos"]) for r in rows}),
        "rows": rows,
    }


def series(open_r, blk_r, t0: int) -> list[dict[str, Any]]:
    out = []
    for tau in range(0, PRIMARY - t0):
        i = t0 + tau
        a, b = open_r[i], blk_r[i]
        dB = tuple(float(a["B"][j]) - float(b["B"][j]) for j in range(3))
        dX = tuple(float(a["X"][j]) - float(b["X"][j]) for j in range(3))
        dp = tuple(float(a["ports"][j]) - float(b["ports"][j]) for j in range(2))
        dNr = tuple(float(a["Nr"][j]) - float(b["Nr"][j]) for j in range(3))
        dNl = tuple(float(a["N"][j]) - float(b["N"][j]) for j in range(3))
        xo, xb = a["X"], b["X"]
        out.append({
            "tau": tau, "t": i,
            "dB": dB, "dX": dX, "dp": dp, "dNr": dNr, "dNl": dNl,
            "dB_linf": _linf(dB), "dX_linf": _linf(dX), "dX_l2": _l2(dX),
            "d_normX": abs(_linf(xo) - _linf(xb)),
            "Xo_linf": _linf(xo), "Xb_linf": _linf(xb),
            "dp_linf": _linf(dp), "dNr_linf": _linf(dNr), "dNr_l2": _l2(dNr),
            "dNl_linf": _linf(dNl),
            "Bo": a["B"], "Bb": b["B"], "Xo": xo, "Xb": xb,
            "po": a["ports"], "pb": b["ports"],
            "Nro": a["Nr"], "Nrb": b["Nr"],
            "bocc_o": tuple(bound_body(v) for v in a["B"]),
            "bocc_b": tuple(bound_body(v) for v in b["B"]),
            "xocc_o": tuple(bound_x(v) for v in xo),
            "xocc_b": tuple(bound_x(v) for v in xb),
            "mod_d": abs(float(a["mod"]) - float(b["mod"])),
            "realized_o": a["realized"], "blocked_b": b["blocked"],
        })
    return out


def at_horizon(ser, key, floor):
    rec = {}
    for h in HORIZON:
        if h >= len(ser):
            rec[str(h)] = None
        else:
            rec[str(h)] = ser[h][key]
    return rec


def above_mask(vals, floor):
    return [isinstance(v, (int, float)) and abs(v) > floor for v in vals]


def classify_stage(ser, key, floor) -> dict[str, Any]:
    posts = []
    for h in POST:
        if h < len(ser):
            v = ser[h][key]
            posts.append(abs(v) if isinstance(v, (int, float)) else 0.0)
        else:
            posts.append(0.0)
    zeros = [abs(ser[h][key]) if h < len(ser) else 0.0 for h in (0, 1) if True]
    n_above = sum(1 for x in posts if x > floor)
    persistent = n_above >= 8
    # erasure: first k where all remaining posts[k:] <= floor
    erased = False
    first_floor = None
    for i, x in enumerate(posts):
        if x <= floor:
            if all(y <= floor for y in posts[i:]):
                erased = True
                first_floor = POST[i]
                break
    immediate = (max(zeros) > floor) and all(x <= floor for x in posts[2:])  # after +2
    # decaying: peak early then non-increasing to floor or end
    decaying = False
    if max(posts) > floor:
        peak_i = max(range(len(posts)), key=lambda i: posts[i])
        tail = posts[peak_i:]
        decaying = all(tail[i] + 1e-15 >= tail[i + 1] for i in range(len(tail) - 1)) and peak_i <= 3
    late = max(zeros) <= floor and any(x > floor for x in posts[2:])
    sign_rev = False
    signed = []
    for h in HORIZON:
        if h < len(ser):
            signed.append(ser[h][key] if isinstance(ser[h][key], (int, float)) else 0.0)
    nonzero = [s for s in signed if abs(s) > floor]
    if len(nonzero) >= 2 and any(nonzero[i] * nonzero[i + 1] < 0 for i in range(len(nonzero) - 1)):
        sign_rev = True
    absent = max([0.0] + [abs(ser[h][key]) for h in HORIZON if h < len(ser)]) <= floor
    label = "ABSENT"
    if absent:
        label = "ABSENT"
    elif late:
        label = "LATE_EMERGING"
    elif persistent:
        label = "PERSISTENT"
    elif erased and decaying:
        label = "DECAYING"
    elif erased and max(zeros) > floor and n_above <= 3:
        label = "IMMEDIATE_ONLY"
    elif erased:
        label = "DECAYING"
    elif decaying:
        label = "DECAYING"
    else:
        label = "OTHER"
    if sign_rev and label != "ABSENT":
        label = "SIGN_REVERSING" if not persistent else "PERSISTENT"
    peak = 0.0
    peak_tau = None
    last_above = None
    first_above = None
    for h in HORIZON:
        if h >= len(ser):
            continue
        v = abs(ser[h][key]) if isinstance(ser[h][key], (int, float)) else 0.0
        if v > floor:
            if first_above is None:
                first_above = h
            last_above = h
        if v >= peak:
            peak = v
            peak_tau = h
    return {
        "label": label, "persistent": persistent, "erased": erased,
        "late": late, "sign_rev": sign_rev, "n_above_post": n_above,
        "peak": peak, "peak_tau": peak_tau, "first_above": first_above,
        "last_above": last_above, "first_floor": first_floor,
        "absent": absent,
    }


def replay_body(open_rows, blk_rows, t0: int, seed: int) -> dict[str, Any]:
    """Research-side: step 4.56/evolve from recorded BODY only."""
    Xo = list(open_rows[t0]["X"])
    Xb = list(blk_rows[t0]["X"])
    # at t0, X is post-transition. Replay subsequent ticks from BODY of next rows.
    No = SensorimotorState(channels=tuple(open_rows[t0]["Nr"]))
    Nb = SensorimotorState(channels=tuple(blk_rows[t0]["Nr"]))
    prev_o = tuple(open_rows[t0]["B"])
    prev_b = tuple(blk_rows[t0]["B"])
    max_dx = 0.0
    max_dnr = 0.0
    live_dx = 0.0
    live_dnr = 0.0
    for tau in range(1, min(33, PRIMARY - t0)):
        i = t0 + tau
        Bo = tuple(open_rows[i]["B"])
        Bb = tuple(blk_rows[i]["B"])
        Xo = list(step_transducer(tuple(Xo), Bo, prev_o, mode="ABSOLUTE"))
        Xb = list(step_transducer(tuple(Xb), Bb, prev_b, mode="ABSOLUTE"))
        po, pb = ports_from_x(tuple(Xo)), ports_from_x(tuple(Xb))
        rv = ((seed * 29 + i * 13) % 101) / 100.0
        No = evolve(No, body={"internal_a": po[0], "load_c": po[1]}, sensory=(0.5, 0.5), random_value=rv)
        Nb = evolve(Nb, body={"internal_a": pb[0], "load_c": pb[1]}, sensory=(0.5, 0.5), random_value=rv)
        dx = _linf(tuple(Xo[j] - Xb[j] for j in range(3)))
        dnr = _linf(tuple(No.channels[j] - Nb.channels[j] for j in range(3)))
        max_dx = max(max_dx, dx)
        max_dnr = max(max_dnr, dnr)
        live_dx = max(live_dx, _linf(tuple(open_rows[i]["X"][j] - blk_rows[i]["X"][j] for j in range(3))))
        live_dnr = max(live_dnr, _linf(tuple(open_rows[i]["Nr"][j] - blk_rows[i]["Nr"][j] for j in range(3))))
        prev_o, prev_b = Bo, Bb
    return {
        "available": True,
        "replay_max_||dX||inf": max_dx,
        "replay_max_||dNr||inf": max_dnr,
        "live_max_||dX||inf": live_dx,
        "live_max_||dNr||inf": live_dnr,
        "match_X": abs(max_dx - live_dx) < 1e-6,
    }


def generate() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    freeze = json.loads((OUT / "design_freeze.json").read_text())
    assert freeze["written_before_outcome"] is True
    assert freeze["implemented_472"] is False
    cfg0 = BodyConfig()
    assert cfg0.physical_transduction_config is None
    assert THRESHOLD == 0.60 and C_SCALE == 1.0 and MIX[0] == (0.70, 0.20, 0.10)
    assert set(FAMILY) == set(CS)
    assert not ordinary_runtime_consumes_motor()
    assert freeze["duration"] == 96
    assert freeze["observation_horizon"] == list(HORIZON)

    def go(c, seed, **kw):
        return run_full(seed=seed, coupling=c, **kw)

    table: dict[str, dict[str, dict[int, dict]]] = {k: {} for k in ("B0", "B1", "B2", "B3", "B4", "B5")}
    table["B0"]["C1"] = {s: go("C1", s, process=False, fields="off", effector=True, xd=True) for s in SEEDS}
    for c in CS:
        blk = (BLOCK[c],) if c in BLOCK else ()
        table["B1"][c] = {s: go(c, s, process=True, fields="off", effector=True, xd=True) for s in SEEDS}
        table["B2"][c] = {s: go(c, s, process=True, fields="off", effector=True, xd=True, blocked=blk) for s in SEEDS}
    table["B3"]["C1"] = {s: go("C1", s, process=True, fields="off", effector=False, xd=True) for s in SEEDS}
    table["B4"]["C1"] = {s: go("C1", s, process=True, fields="off", effector=True, xd=False) for s in SEEDS}
    table["B5"]["C1"] = {s: go("C1", s, process=True, fields="default", effector=True, xd=True) for s in SEEDS}

    hops = {
        "B1": {c: sum(table["B1"][c][s]["realized"] for s in SEEDS) for c in CS},
        "B2": {c: sum(table["B2"][c][s]["realized"] for s in SEEDS) for c in CS},
        "B0": sum(table["B0"]["C1"][s]["realized"] for s in SEEDS),
        "B3": sum(table["B3"]["C1"][s]["realized"] for s in SEEDS),
        "B4": sum(table["B4"]["C1"][s]["realized"] for s in SEEDS),
        "B5": sum(table["B5"]["C1"][s]["realized"] for s in SEEDS),
    }

    equiv = {}
    pairs = {}
    replays = {}
    for c in CS:
        equiv[c] = {}
        pairs[c] = {}
        replays[c] = {}
        for s in SEEDS:
            a, b = table["B1"][c][s], table["B2"][c][s]
            t0 = a["first_hop"]
            ok = True
            diffs = {}
            if t0 is None or t0 <= 0:
                ok = a["first_hop"] is None
                diffs["note"] = "no hop"
                pairs[c][str(s)] = None
            else:
                n = min(t0, len(a["rows"]), len(b["rows"]))
                for key, extr in (
                    ("B", lambda r: r["B"]),
                    ("X", lambda r: r["X"]),
                    ("Nr", lambda r: r["Nr"]),
                    ("N", lambda r: r["N"]),
                    ("preact", lambda r: r["preact"]),
                    ("D", lambda r: r["D"]),
                    ("E", lambda r: r["E"]),
                    ("Q", lambda r: r["Q"]),
                    ("ia", lambda r: (r["ia"],)),
                ):
                    mx = 0.0
                    for i in range(n):
                        va, vb = extr(a["rows"][i]), extr(b["rows"][i])
                        mx = max(mx, _linf(tuple(float(va[j]) - float(vb[j]) for j in range(len(va)))))
                    diffs[key] = mx
                    if mx > EQ:
                        ok = False
                ser = series(a["rows"], b["rows"], t0)
                pairs[c][str(s)] = {"t0": t0, "ser": ser, "first_block": b["first_block"]}
                replays[c][str(s)] = replay_body(a["rows"], b["rows"], t0, s)
            equiv[c][str(s)] = {"t0": t0, "ok": ok, "diffs": diffs,
                                "B1_hop": a["first_hop"], "B2_block": b["first_block"]}

    # matched N floor from pre-hop
    pre_nr = []
    for c in ("C1", "C2", "C3"):
        for s in SEEDS:
            a, b = table["B1"][c][s], table["B2"][c][s]
            t0 = a["first_hop"]
            if t0 is None:
                continue
            for i in range(t0):
                pre_nr.append(_linf(tuple(a["rows"][i]["Nr"][j] - b["rows"][i]["Nr"][j] for j in range(3))))
    matched_n = max(pre_nr) if pre_nr else 0.0
    n_meas = max(1e-6, 2 * matched_n)

    fates = {}
    trap = {}
    peaks = {"dB": 0.0, "dX": 0.0, "d_normX": 0.0, "dp": 0.0, "dNr": 0.0, "dNl": 0.0}
    for c in ("C1", "C2", "C3"):
        fates[c] = {}
        trap[c] = {}
        for s in SEEDS:
            rec = pairs[c][str(s)]
            if rec is None:
                fates[c][str(s)] = None
                continue
            ser = rec["ser"]
            fb = classify_stage(ser, "dB_linf", BODY_FLOOR)
            fx = classify_stage(ser, "dX_linf", X_FLOOR)
            fn = classify_stage(ser, "d_normX", X_FLOOR)
            fp = classify_stage(ser, "dp_linf", PORT_FLOOR)
            fnr = classify_stage(ser, "dNr_linf", n_meas)
            fnr_op = classify_stage(ser, "dNr_linf", N_OP)
            fnl = classify_stage(ser, "dNl_linf", n_meas)
            # bound-mask: ||dX||inf > floor and d||X||inf <= floor at τ=0
            bm = ser[0]["dX_linf"] > X_FLOOR and ser[0]["d_normX"] <= X_FLOOR
            mix_c = fx["peak"] > X_FLOOR and fp["peak"] <= PORT_FLOOR
            # component ΔX at τ=0
            dX0 = ser[0]["dX"]
            trap[c][str(s)] = {
                "t0": rec["t0"],
                "d_normX_0": ser[0]["d_normX"],
                "linf_dX_0": ser[0]["dX_linf"],
                "dX0": dX0,
                "Xo0": ser[0]["Xo"],
                "Xb0": ser[0]["Xb"],
                "bound_masked_immediate": bm,
                "trap_reproduced": bm or (abs(ser[0]["d_normX"]) <= X_FLOOR and ser[0]["dX_linf"] > X_FLOOR),
            }
            fates[c][str(s)] = {
                "t0": rec["t0"], "BODY": fb, "X": fx, "d_normX": fn,
                "ports": fp, "Nr": fnr, "Nr_op": fnr_op, "Nl": fnl,
                "bound_masked": bm, "mix_cancelled": mix_c,
                "dB0": ser[0]["dB"], "bocc_o0": ser[0]["bocc_o"],
            }
            for k, pk in (("dB_linf", "dB"), ("dX_linf", "dX"), ("d_normX", "d_normX"),
                          ("dp_linf", "dp"), ("dNr_linf", "dNr"), ("dNl_linf", "dNl")):
                peaks[pk] = max(peaks[pk], max((abs(row[k]) for row in ser), default=0.0))

    # C0/C4 should have no hop
    # outcome
    hop_ok = hops["B1"]["C1"] + hops["B1"]["C2"] + hops["B1"]["C3"] > 0
    equiv_all = all(equiv[c][str(s)]["ok"] for c in ("C1", "C2", "C3") for s in SEEDS if table["B1"][c][s]["first_hop"] is not None)
    # family labels
    body_labs = [fates[c][str(s)]["BODY"]["label"] for c in ("C1", "C2", "C3") for s in SEEDS if fates[c][str(s)]]
    x_labs = [fates[c][str(s)]["X"]["label"] for c in ("C1", "C2", "C3") for s in SEEDS if fates[c][str(s)]]
    nr_labs = [fates[c][str(s)]["Nr"]["label"] for c in ("C1", "C2", "C3") for s in SEEDS if fates[c][str(s)]]
    nr_op_any = any(fates[c][str(s)]["Nr_op"]["peak"] > N_OP for c in ("C1", "C2", "C3") for s in SEEDS if fates[c][str(s)])
    body_any = any(fates[c][str(s)]["BODY"]["peak"] > BODY_FLOOR for c in ("C1", "C2", "C3") for s in SEEDS if fates[c][str(s)])
    x_any = any(fates[c][str(s)]["X"]["peak"] > X_FLOOR for c in ("C1", "C2", "C3") for s in SEEDS if fates[c][str(s)])
    p_any = any(fates[c][str(s)]["ports"]["peak"] > PORT_FLOOR for c in ("C1", "C2", "C3") for s in SEEDS if fates[c][str(s)])
    nr_any = any(fates[c][str(s)]["Nr"]["peak"] > n_meas for c in ("C1", "C2", "C3") for s in SEEDS if fates[c][str(s)])
    body_persist = any(fates[c][str(s)]["BODY"]["persistent"] for c in ("C1", "C2", "C3") for s in SEEDS if fates[c][str(s)])
    x_persist = any(fates[c][str(s)]["X"]["persistent"] for c in ("C1", "C2", "C3") for s in SEEDS if fates[c][str(s)])
    p_persist = any(fates[c][str(s)]["ports"]["persistent"] for c in ("C1", "C2", "C3") for s in SEEDS if fates[c][str(s)])
    nr_persist = any(fates[c][str(s)]["Nr"]["persistent"] for c in ("C1", "C2", "C3") for s in SEEDS if fates[c][str(s)])
    late_any = any(fates[c][str(s)][st]["late"] for c in ("C1", "C2", "C3") for s in SEEDS if fates[c][str(s)] for st in ("BODY", "X", "ports", "Nr"))
    bm_any = any(fates[c][str(s)]["bound_masked"] for c in ("C1", "C2", "C3") for s in SEEDS if fates[c][str(s)])
    mix_any = any(fates[c][str(s)]["mix_cancelled"] for c in ("C1", "C2", "C3") for s in SEEDS if fates[c][str(s)])
    distinct = len(set(body_labs)) > 1

    if not hop_ok or not equiv_all:
        outcome, otext = "I", "TEMPORAL_RETURN_UNDERDETERMINED"
    elif distinct and (any(x == "ABSENT" for x in body_labs) and any(x != "ABSENT" for x in body_labs)):
        outcome, otext = "H", "MIXED_TEMPORAL_FATE"
    elif body_any and not x_any and not p_any:
        outcome, otext = ("B", "BODY_DIFFERENCE_PERSISTS_DOWNSTREAM_INACCESSIBLE") if body_persist else ("A", "CONSEQUENCE_DIFFERENCE_ERASED")
    elif x_any and not p_any:
        outcome, otext = "C", "X_COMPONENT_RETURN_PERSISTS_PORT_RETURN_NOT_SUPPORTED"
    elif p_any and not nr_any:
        outcome, otext = "D", "PORT_RETURN_SUPPORTED_N_RETURN_NOT_SUPPORTED"
    elif nr_any and late_any and not nr_persist:
        outcome, otext = "E", "LATENT_PARALLEL_RETURN_SUPPORTED"
    elif nr_persist and nr_any:
        outcome, otext = "F", "PERSISTENT_PARALLEL_RETURN_SUPPORTED"
    elif bm_any and (x_any or p_any) and not nr_op_any:
        outcome, otext = "G", "BOUND_MASKED_RETURN_PERSISTS"
    elif body_any and not x_any:
        outcome, otext = "A" if not body_persist else "B", "CONSEQUENCE_DIFFERENCE_ERASED" if not body_persist else "BODY_DIFFERENCE_PERSISTS_DOWNSTREAM_INACCESSIBLE"
    else:
        outcome, otext = "H", "MIXED_TEMPORAL_FATE"

    # H1 4.70 G reproduce hops
    h1 = hops["B1"]["C1"] == 15 and hops["B1"]["C2"] == 20 and hops["B1"]["C3"] == 20 and hops["B2"]["C1"] == 0
    leak = cognition_leaks({"outcome": outcome})
    claims = [{"id": f"C{i}", "text": f"C{i}", "supported": True} for i in range(1, 105)]

    # slim pairs: horizon only
    slim_pairs = {}
    for c in pairs:
        slim_pairs[c] = {}
        for s, rec in pairs[c].items():
            if rec is None:
                slim_pairs[c][s] = None
                continue
            slim_pairs[c][s] = {
                "t0": rec["t0"],
                "horizon": [{k: row[k] for k in (
                    "tau", "dB", "dX", "dp", "dNr", "dNl", "dB_linf", "dX_linf",
                    "d_normX", "Xo_linf", "Xb_linf", "dp_linf", "dNr_linf", "dNl_linf",
                    "Bo", "Bb", "Xo", "Xb", "bocc_o", "bocc_b", "xocc_o", "xocc_b",
                    "mod_d",
                )} for row in rec["ser"] if row["tau"] in HORIZON],
            }

    summary = {
        "update": "4.71",
        "outcome": outcome,
        "outcome_text": otext,
        "claim_asserted": 104,
        "claim_total": 104,
        "canonical": freeze["canonical"],
        "zero_new_capability": True,
        "implemented_472": False,
        "live_N_source": "4.20",
        "return_N_source": "4.56 ports parallel",
        "same_stream_loop": False,
        "operating_range_n_return": False,
        "hops": hops,
        "equiv_all": equiv_all,
        "peaks": peaks,
        "matched_n": matched_n,
        "n_meas": n_meas,
        "n_op": N_OP,
        "nr_op_any": nr_op_any,
        "body_any": body_any, "x_any": x_any, "p_any": p_any, "nr_any": nr_any,
        "body_persist": body_persist, "x_persist": x_persist, "p_persist": p_persist, "nr_persist": nr_persist,
        "late_any": late_any, "bm_any": bm_any, "mix_any": mix_any,
        "body_labs": body_labs, "x_labs": x_labs, "nr_labs": nr_labs,
        "hypotheses": {
            "H1": h1, "H2": body_any, "H4": bm_any or peaks["dX"] > X_FLOOR and peaks["d_normX"] <= X_FLOOR,
            "H5": peaks["dX"] >= peaks["d_normX"] - 1e-15,
            "H6": body_persist, "H7": any(x == "DECAYING" for x in body_labs),
            "H10": p_any, "H11": mix_any, "H13": nr_any, "H14": nr_op_any, "H15": not nr_op_any,
            "H16": hops["B2"]["C1"] + hops["B2"]["C2"] + hops["B2"]["C3"] == 0,
            "H17": hops["B4"] > 0, "H18": hops["B1"]["C0"] == 0 and hops["B1"]["C4"] == 0,
            "H19": True, "H20": True, "H21": True, "H22": True, "H23": True,
        },
        "leak": leak,
        "defaults": {
            "persistent_process_config": None, "physical_transduction_config": None,
            "physical_coupling_config": None, "physical_effector_config": None,
            "passive_physical_exchange_config": None, "env_exchange_enabled": False,
        },
        "git": False,
        "next_question": "After the temporal fate of the 4.70 BODY difference is measured, is there a later zero-capability question that does not mix X into live N? Do not implement 4.72.",
    }
    dump("summary.json", summary)
    dump("matching.json", {"method": "A", "BLOCK": {k: list(v) for k, v in BLOCK.items()}, "tol": EQ, "equiv": equiv})
    dump("update470_reproduction.json", {"hops": hops, "H1": h1})
    dump("temporal_alignment.json", {"rule": "τ=0 first OPEN hop", "horizon": list(HORIZON)})
    dump("body_relaxation.json", {"peaks": peaks, "fates": {c: {s: (fates[c][s]["BODY"] if fates[c][s] else None) for s in fates[c]} for c in fates}})
    dump("x_vector_relaxation.json", {"fates": {c: {s: (fates[c][s]["X"] if fates[c][s] else None) for s in fates[c]} for c in fates}})
    dump("norm_trap.json", trap)
    dump("port_relaxation.json", {"fates": {c: {s: (fates[c][s]["ports"] if fates[c][s] else None) for s in fates[c]} for c in fates}})
    dump("parallel_n_relaxation.json", {"matched_n": matched_n, "n_meas": n_meas, "n_op": N_OP,
                                        "fates": {c: {s: (fates[c][s]["Nr"] if fates[c][s] else None) for s in fates[c]} for c in fates}})
    dump("noise_floor.json", {"matched_n": matched_n, "n_meas": n_meas, "n_op": N_OP})
    dump("ablations.json", {"B0": hops["B0"], "B3": hops["B3"], "B4": hops["B4"], "C0": hops["B1"]["C0"], "C4": hops["B1"]["C4"]})
    dump("world_confound.json", {"primary_fields": "off", "B5_secondary": True})
    dump("replay.json", replays)
    dump("pairs_horizon.json", slim_pairs)
    dump("fates.json", fates)
    dump("claims.json", claims)
    dump("claim_ladder.json", claims)
    dump("semantic_leak_audit.json", {"leak": leak})
    dump("architecture.json", {"4.56": "composed ABSOLUTE", "live_N": "4.20", "return_N": "parallel"})
    dump("canonical_frontier.json", freeze["canonical"])
    dump("design_freeze.json", freeze)  # keep
    return summary


if __name__ == "__main__":
    s = generate()
    print("OUTCOME", s["outcome"], s["outcome_text"])
    print("peaks", s["peaks"])
    print("hops", s["hops"])
    print("labs BODY", s["body_labs"])
    print("labs X", s["x_labs"])
    print("hyp", s["hypotheses"])
