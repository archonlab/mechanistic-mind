#!/usr/bin/env python3
"""Beta 3.1: search for an optical-only OBSERVED_COMPOSITE PSC competition counterexample.

Production path only. Does not change SMC / MATCH_TOL / PE / PSC / scoring.
GIT_PUSH=NO.
"""
from __future__ import annotations

import copy
import json
import resource
import time
from pathlib import Path
from typing import Any

from mechanistic_mind.physical_system import observed_composite_psc as oc
from mechanistic_mind.physical_system import o_prime_history_bridge as oph
from mechanistic_mind.physical_system import sensorimotor_consequence as smc
from mechanistic_mind.physical_system.cognition import (
    CognitionConfig,
    empty_cognitive_state,
    run_cognition_before_action,
)
from mechanistic_mind.research import predictive_compression as pc
from mechanistic_mind.research import prospective_composition as pr
from mechanistic_mind.scientific_v3.receipts import compact_accessible_observation

OUT = Path("results/beta31_optical_psc_counterexample")

SURFACE: tuple[str, ...] = (
    "surface_c0_0", "surface_c0_1", "surface_c0_2",
    "surface_c1_0", "surface_c1_1", "surface_c1_2",
    "surface_c2_0", "surface_c2_1", "surface_c2_2",
)
# All non-optical SMC channels. Nine exo/vest/prop channels cannot push
# quantized mean L1 past MATCH_TOL=0.12 when a pre-consequence antecedent
# at the current non-optical state is also in prospection (production learning).
CONSEQ: tuple[str, ...] = tuple(k for k in smc.SENSORY_CHANNELS if not str(k).startswith("surface_c"))
LOCOS = ["WAIT", "MOVE:E", "MOVE:W"]
RNG = 0.2
TICK_Q = 9000


def rss_mb() -> float | None:
    try:
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    except Exception:
        return None


def base_obs() -> dict[str, float]:
    return {k: 0.25 for k in smc.SENSORY_CHANNELS}


def set_surface(obs: dict[str, float], profile: dict[str, float]) -> dict[str, float]:
    o = dict(obs)
    for k in SURFACE:
        o[k] = float(profile[k])
    return o


def uniform_profile(v: float) -> dict[str, float]:
    return {k: float(v) for k in SURFACE}


def channel_profile(base: float, **overrides: float) -> dict[str, float]:
    p = uniform_profile(base)
    p.update({k: float(v) for k, v in overrides.items()})
    return p


def apply_conseq(obs: dict[str, float], *, high: bool) -> dict[str, float]:
    o = dict(obs)
    v = 0.90 if high else 0.10
    for k in CONSEQ:
        o[k] = v
    return o


def non_optical_diff_count(a: dict[str, float], b: dict[str, float]) -> int:
    keys = set(a) | set(b)
    n = 0
    for k in keys:
        if k in SURFACE:
            continue
        av, bv = a.get(k), b.get(k)
        if av is None or bv is None:
            n += 1
            continue
        if abs(float(av) - float(bv)) > 1e-12:
            n += 1
    return n


def motor(loco: str, neck: str) -> dict[str, Any]:
    return {"locomotion": loco, "neck": neck, "oscillator": {}, "push": False}


ME = motor("MOVE:E", "NECK_LEFT")
MW = motor("MOVE:W", "NECK_RIGHT")


def smc_sig(obs: dict[str, float], ch: tuple[str, ...] | None = None) -> dict[str, float]:
    keys = ch or smc.SENSORY_CHANNELS
    return smc.sensory_signature(smc.extract_sensory(obs, keys), keys)


def mean_l1_q(a: dict[str, float], b: dict[str, float], ch: tuple[str, ...] | None = None) -> float:
    keys = ch or smc.SENSORY_CHANNELS
    return smc._l1(smc_sig(a, keys), smc_sig(b, keys), keys)


def pr_l1(a: dict[str, float], b: dict[str, float]) -> float:
    return pr._frag_distance(pr._q(a), pr._q(b))


def clone_store(obj: Any) -> Any:
    return copy.deepcopy(obj)


def optical_pairs() -> dict[str, tuple[dict[str, float], dict[str, float]]]:
    """Systematic X/Y optical profiles (non-optical held in base_obs)."""
    mid = 0.50
    return {
        "bin_cross_0.19_0.21": (
            channel_profile(mid, surface_c0_0=0.19),
            channel_profile(mid, surface_c0_0=0.21),
        ),
        "bin_cross_0.39_0.41": (
            channel_profile(mid, surface_c0_0=0.39),
            channel_profile(mid, surface_c0_0=0.41),
        ),
        "bin_cross_0.59_0.61": (
            channel_profile(mid, surface_c0_0=0.59),
            channel_profile(mid, surface_c0_0=0.61),
        ),
        "bin_cross_0.79_0.81": (
            channel_profile(mid, surface_c0_0=0.79),
            channel_profile(mid, surface_c0_0=0.81),
        ),
        "same_bin_0.21_0.29": (
            channel_profile(mid, surface_c0_0=0.21),
            channel_profile(mid, surface_c0_0=0.29),
        ),
        "multichannel_c0c1_swap": (
            channel_profile(0.50, **{k: 0.90 for k in SURFACE if k.startswith("surface_c0")},
                            **{k: 0.10 for k in SURFACE if k.startswith("surface_c1")}),
            channel_profile(0.50, **{k: 0.10 for k in SURFACE if k.startswith("surface_c0")},
                            **{k: 0.90 for k in SURFACE if k.startswith("surface_c1")}),
        ),
        "sector_left_vs_right": (
            channel_profile(0.10, surface_c0_0=0.90, surface_c1_0=0.90, surface_c2_0=0.90),
            channel_profile(0.10, surface_c0_2=0.90, surface_c1_2=0.90, surface_c2_2=0.90),
        ),
        "high_sep_8ch": (
            {k: (0.90 if i < 8 else 0.50) for i, k in enumerate(SURFACE)},
            {k: (0.10 if i < 8 else 0.50) for i, k in enumerate(SURFACE)},
        ),
        "high_sep_9ch": (uniform_profile(0.90), uniform_profile(0.10)),
        "c0c1c2_swap": (
            channel_profile(0.50, **{k: 0.90 for k in SURFACE if "c0" in k or "c2" in k},
                            **{k: 0.10 for k in SURFACE if "c1" in k}),
            channel_profile(0.50, **{k: 0.10 for k in SURFACE if "c0" in k or "c2" in k},
                            **{k: 0.90 for k in SURFACE if "c1" in k}),
        ),
    }


def quantizer_table() -> dict[str, Any]:
    rows = []
    for raw in (0.19, 0.21, 0.29, 0.39, 0.41, 0.59, 0.61, 0.79, 0.81, 0.10, 0.90):
        rows.append({
            "raw": raw,
            "smc_mid": smc._q_scalar(raw),
            "pr_q": pr._q({"v": raw})["v"],
        })
    return {"bins": 5, "midpoints": [smc._q_scalar(i / 5 + 1e-6) for i in range(5)], "samples": rows}


def smc_optical_bound() -> dict[str, Any]:
    ch = smc.SENSORY_CHANNELS
    n = len(ch)
    optical = [k for k in ch if k.startswith("surface_c")]
    n_opt = len(optical)
    assert n_opt == 9
    q0 = smc._q_scalar(0.0)
    q1 = smc._q_scalar(0.999)
    max_per = abs(q1 - q0)
    raw_naive = n_opt / n
    q_max = n_opt * max_per / n
    x = set_surface(base_obs(), uniform_profile(0.0))
    y = set_surface(base_obs(), uniform_profile(1.0))
    emp = mean_l1_q(x, y, ch)
    store = smc.empty_store(enabled=True)
    ch_store = smc.channels_for_store(store)
    always = (q_max <= smc.SIM_THRESHOLD) and (len(ch_store) == n)
    return {
        "n_smc_channels": n,
        "n_optical_surface_c": n_opt,
        "optical_keys": list(optical),
        "channels_for_empty_store": len(ch_store),
        "equal_weight_mean_l1": True,
        "quantized_max_per_channel": max_per,
        "theoretical_quantized_max_mean_l1": q_max,
        "naive_raw_01_max_mean_l1": raw_naive,
        "empirical_0_vs_1_quantized_mean_l1": emp,
        "SIM_THRESHOLD": smc.SIM_THRESHOLD,
        "MATCH_TOL": pr.MATCH_TOL,
        "SMC_ALWAYS_GENERALIZES_ACROSS_OPTICAL_ONLY_DIFFERENCES": always,
        "SMC_OPTICAL_ONLY_SEPARATION_IMPOSSIBLE": always,
        "note": (
            "Mean L1 = sum_i |Δq_i| / 48. Nine surface_c* channels, quantized travel "
            "at most 0.8, contribute at most 7.2/48=0.15 < 0.22. Raw [0,1] bound "
            "9/48=0.1875 is also < 0.22. Missing keys fill as 0 then quantize to 0.1."
        ),
    }


def compact_sel(sel: dict[str, Any]) -> dict[str, Any]:
    mot = sel.get("motor")
    md = mot.to_dict() if mot is not None and hasattr(mot, "to_dict") else mot
    cands = []
    for c in sel.get("candidates") or []:
        hr = c.get("history_ref") or {}
        cands.append({
            "motor_signature": c.get("motor_signature"),
            "smc_support": c.get("smc_support"),
            "smc_record_id": c.get("smc_record_id"),
            "history_status": hr.get("status"),
            "historical_support": hr.get("historical_support"),
            "reliability": hr.get("reliability"),
            "depth": hr.get("depth"),
        })
    comp = sel.get("competition") or {}
    return {
        "status": sel.get("status"),
        "n_candidates": sel.get("n_candidates"),
        "candidate_signatures": sel.get("candidate_signatures"),
        "selected_signature": sel.get("selected_signature"),
        "selected_locomotion": sel.get("selected_locomotion"),
        "reason": sel.get("reason"),
        "compete_source": sel.get("compete_source"),
        "outcome_class": comp.get("outcome_class"),
        "selection_reason": comp.get("selection_reason"),
        "tie_resolution": comp.get("tie_resolution"),
        "motor": md,
        "candidates": cands,
    }


def level_of(cx: dict[str, Any], cy: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    sx, sy = compact_sel(cx), compact_sel(cy)
    set_x = tuple(sorted(sx.get("candidate_signatures") or [c["motor_signature"] for c in sx["candidates"]]))
    set_y = tuple(sorted(sy.get("candidate_signatures") or [c["motor_signature"] for c in sy["candidates"]]))
    scores_x = {c["motor_signature"]: (c.get("historical_support"), c.get("reliability")) for c in sx["candidates"]}
    scores_y = {c["motor_signature"]: (c.get("historical_support"), c.get("reliability")) for c in sy["candidates"]}
    order_x = [c["motor_signature"] for c in sorted(
        sx["candidates"], key=lambda c: (-int(c.get("historical_support") or 0), -float(c.get("reliability") or 0))
    )]
    order_y = [c["motor_signature"] for c in sorted(
        sy["candidates"], key=lambda c: (-int(c.get("historical_support") or 0), -float(c.get("reliability") or 0))
    )]
    win_x, win_y = sx.get("selected_signature"), sy.get("selected_signature")
    loco_x, loco_y = sx.get("selected_locomotion"), sy.get("selected_locomotion")
    mx, my = sx.get("motor") or {}, sy.get("motor") or {}
    motor_changed = (mx.get("locomotion") != my.get("locomotion")
                     or mx.get("neck") != my.get("neck")
                     or bool(mx.get("push")) != bool(my.get("push")))
    action_changed = (mx.get("legacy_token") or mx.get("locomotion")) != (
        my.get("legacy_token") or my.get("locomotion")
    )
    set_changed = set_x != set_y or sx.get("n_candidates") != sy.get("n_candidates")
    score_changed = scores_x != scores_y
    order_changed = order_x != order_y
    winner_changed = win_x != win_y and None not in (win_x, win_y)
    fallback_pair = {sx.get("status"), sy.get("status")} == {"SELECTED", "FALLBACK_LOCO"}
    if fallback_pair:
        winner_changed = True
        if sx.get("status") != sy.get("status"):
            motor_changed = True
            action_changed = True
    level = 0
    if set_changed or score_changed:
        level = 1
    if order_changed:
        level = 2
    if winner_changed:
        level = 3
    if motor_changed:
        level = 4
    if action_changed and motor_changed:
        level = 5
    alias = bool(winner_changed and not motor_changed)
    return level, {
        "set_changed": set_changed,
        "score_changed": score_changed,
        "order_changed": order_changed,
        "winner_changed": winner_changed,
        "motor_changed": motor_changed,
        "action_changed": action_changed,
        "motor_aliasing": alias,
        "set_x": list(set_x),
        "set_y": list(set_y),
        "order_x": order_x,
        "order_y": order_y,
        "win_x": win_x,
        "win_y": win_y,
        "status_x": sx.get("status"),
        "status_y": sy.get("status"),
        "compact_x": sx,
        "compact_y": sy,
    }


def psc_select(obs: dict[str, float], smc_store: dict, prosp: dict, compression=None, rng: float = RNG) -> dict:
    return oc.select_observed_composite_motor(
        observation=obs,
        smc_store=smc_store,
        loco_candidates=list(LOCOS),
        prospection=prosp,
        compression=compression,
        retrieval_enabled=compression is not None,
        tick=TICK_Q,
        rng_value=rng,
    )


def train_family(
    *,
    ox: dict[str, float],
    oy: dict[str, float],
    family: str,
    depth: int,
    ratio_x: int,
    ratio_y: int,
) -> dict[str, Any]:
    """Build SMC + prospection via production update/learn_transition APIs."""
    store = smc.empty_store(enabled=True)
    prosp = pr.empty_store()
    x1 = apply_conseq(ox, high=True)
    y1 = apply_conseq(oy, high=False)
    x1_same = apply_conseq(ox, high=True)
    y1_same = apply_conseq(oy, high=True)
    tick = 0

    def learn_smc(o0, mot, o1, n):
        nonlocal tick
        for _ in range(n):
            smc.update(store, tick=tick, observation_t=o0, motor=mot, observation_t1=o1)
            tick += 1

    def learn_pr(ant, action, cons, n):
        nonlocal tick
        for _ in range(n):
            pr.learn_transition(prosp, tick=tick, antecedent=ant, action=action, consequent=cons)
            tick += 1

    nx = max(0, int(depth * ratio_x))
    ny = max(0, int(depth * ratio_y))
    n_sym = max(nx, 1)

    if family == "empty":
        pass
    elif family == "symmetric":
        learn_smc(ox, ME, x1, n_sym)
        learn_smc(oy, ME, y1_same, n_sym)
        learn_smc(ox, MW, apply_conseq(ox, high=False), n_sym)
        learn_smc(oy, MW, y1, n_sym)
        learn_pr(x1, "MOVE:E", {**x1, "exo_2": 0.91}, max(n_sym, 3))
        learn_pr(y1_same, "MOVE:E", {**y1_same, "exo_2": 0.91}, max(n_sym, 3))
        learn_pr(apply_conseq(ox, high=False), "MOVE:W", {**apply_conseq(ox, high=False), "exo_2": 0.09}, max(n_sym, 3))
        learn_pr(y1, "MOVE:W", {**y1, "exo_2": 0.09}, max(n_sym, 3))
    elif family == "conditioned_separated":
        # X+E → high-conseq basin; Y+W → low-conseq basin. Competing motors.
        learn_smc(ox, ME, x1, max(nx, 1))
        learn_smc(oy, MW, y1, max(ny, 1))
        learn_pr(x1, "MOVE:E", {**x1, "local.T": 0.92}, max(nx, 3))
        learn_pr(y1, "MOVE:W", {**y1, "local.T": 0.08}, max(ny, 3))
    elif family == "unequal_support":
        learn_smc(ox, ME, x1, max(nx, 1))
        learn_smc(oy, MW, y1, max(ny, 1))
        learn_pr(x1, "MOVE:E", {**x1, "local.T": 0.92}, max(nx, 3))
        learn_pr(y1, "MOVE:W", {**y1, "local.T": 0.08}, max(ny, 3))
    elif family == "competing_motors":
        learn_smc(ox, ME, x1, max(nx, 1))
        learn_smc(ox, MW, apply_conseq(ox, high=False), max(1, nx // 4))
        learn_smc(oy, MW, y1, max(ny, 1))
        learn_smc(oy, ME, apply_conseq(oy, high=True), max(1, ny // 4))
        learn_pr(x1, "MOVE:E", {**x1, "local.T": 0.92}, max(nx, 3))
        learn_pr(y1, "MOVE:W", {**y1, "local.T": 0.08}, max(ny, 3))
    elif family == "pe_merge":
        # Similar consequences (both high) — merge pressure.
        learn_smc(ox, ME, x1, max(nx, 1))
        learn_smc(oy, MW, apply_conseq(oy, high=True), max(ny, 1))
        learn_pr(x1, "MOVE:E", dict(x1), max(nx, 3))
        learn_pr(apply_conseq(oy, high=True), "MOVE:W", apply_conseq(oy, high=True), max(ny, 3))
    elif family == "pe_separation":
        learn_smc(ox, ME, x1, max(nx, 1))
        learn_smc(oy, MW, y1, max(ny, 1))
        learn_pr(x1, "MOVE:E", {**x1, "local.T": 0.95}, max(nx, 3))
        learn_pr(y1, "MOVE:W", {**y1, "local.T": 0.05}, max(ny, 3))
    else:
        raise ValueError(family)

    return {"smc": store, "prospection": prosp, "x1": x1, "y1": y1}


def hss_trace(obs: dict[str, float], trained: dict[str, Any]) -> dict[str, Any]:
    store = clone_store(trained["smc"])
    prosp = trained["prospection"]
    rows = []
    for mot, label in ((ME, "MOVE:E"), (MW, "MOVE:W")):
        pred = smc.query(store, observation=obs, motor=mot, tick=TICK_Q)
        meta = oph.construct_o_prime(obs, pred.get("predicted_delta"))
        hist = oph.query_history_on_o_prime(
            prospection=prosp,
            compression=None,
            o_prime=meta["o_prime"],
            actions=list(LOCOS),
            retrieval_enabled=False,
        )
        op_surf = {k: float((meta["o_prime"] or {}).get(k) or 0.0) for k in SURFACE}
        rows.append({
            "candidate": label,
            "smc_status": pred.get("status"),
            "smc_support": pred.get("support"),
            "smc_record_id": pred.get("record_id"),
            "predicted_fields": meta.get("predicted_fields"),
            "o_prime_surface": op_surf,
            "hss_status": hist.get("status"),
            "hss_support": hist.get("historical_support"),
            "hss_best": hist.get("best_match"),
            "hss_matches": hist.get("matches"),
            "aggregation": hist.get("aggregation"),
        })
    return {"observation_surface": {k: float(obs[k]) for k in SURFACE}, "per_candidate": rows}


def earliest_divergence(ox: dict[str, float], oy: dict[str, float], trained: dict[str, Any]) -> str:
    if mean_l1_q(ox, oy) <= 1e-15:
        return "NONE"
    sx, sy = smc_sig(ox), smc_sig(oy)
    if sx != sy:
        stage = "SMC_5BIN_SIGNATURE"
    else:
        stage = "SMC_ALIASED"
    if pc._sig(ox) != pc._sig(oy):
        if stage == "SMC_ALIASED":
            stage = "COMPRESSION_ROUND4"
    qx, qy = pr._q(ox), pr._q(oy)
    if pr._sig(qx) != pr._sig(qy):
        if stage in {"SMC_ALIASED", "COMPRESSION_ROUND4"}:
            stage = stage + "+TRANSITION_KEY_DISTINCT"
        else:
            stage = stage + "+TRANSITION_KEY"
    if pr_l1(ox, oy) > pr.MATCH_TOL:
        stage = stage + "+PROSPECTIVE_MATCH_TOL_SEPARABLE"
    else:
        stage = stage + "+PROSPECTIVE_SOFT_MATCH"
    return stage


def evaluate_pair(
    pair_name: str,
    px: dict[str, float],
    py: dict[str, float],
    family: str,
    depth: int,
    ratio_x: int,
    ratio_y: int,
) -> dict[str, Any]:
    ox = set_surface(base_obs(), px)
    oy = set_surface(base_obs(), py)
    nod = non_optical_diff_count(ox, oy)
    trained = train_family(ox=ox, oy=oy, family=family, depth=depth, ratio_x=ratio_x, ratio_y=ratio_y)
    smc_x = clone_store(trained["smc"])
    smc_y = clone_store(trained["smc"])
    pr_x = clone_store(trained["prospection"])
    pr_y = clone_store(trained["prospection"])
    sel_x = psc_select(ox, smc_x, pr_x)
    sel_y = psc_select(oy, smc_y, pr_y)
    # order invariance
    smc_x2 = clone_store(trained["smc"])
    smc_y2 = clone_store(trained["smc"])
    pr_x2 = clone_store(trained["prospection"])
    pr_y2 = clone_store(trained["prospection"])
    sel_y_first = psc_select(oy, smc_y2, pr_y2)
    sel_x_second = psc_select(ox, smc_x2, pr_x2)
    lvl, meta = level_of(sel_x, sel_y)
    lvl2, _ = level_of(sel_x_second, sel_y_first)
    order_ok = (
        compact_sel(sel_x)["selected_signature"] == compact_sel(sel_x_second)["selected_signature"]
        and compact_sel(sel_y)["selected_signature"] == compact_sel(sel_y_first)["selected_signature"]
        and compact_sel(sel_x)["status"] == compact_sel(sel_x_second)["status"]
        and compact_sel(sel_y)["status"] == compact_sel(sel_y_first)["status"]
    )
    return {
        "pair": pair_name,
        "family": family,
        "depth": depth,
        "ratio": [ratio_x, ratio_y],
        "non_optical_diff_count": nod,
        "smc_mean_l1": mean_l1_q(ox, oy),
        "pr_mean_l1": pr_l1(ox, oy),
        "earliest_stage": earliest_divergence(ox, oy, trained),
        "level": lvl,
        "level_order_swapped": lvl2,
        "order_invariance": order_ok,
        "rng": RNG,
        **meta,
        "hss_x": hss_trace(ox, trained),
        "hss_y": hss_trace(oy, trained),
        "n_smc_records": len(trained["smc"].get("records") or {}),
        "n_transitions": len(trained["prospection"].get("transitions") or {}),
    }


def empty_history_control(px, py) -> dict[str, Any]:
    ox = set_surface(base_obs(), px)
    oy = set_surface(base_obs(), py)
    trained = train_family(ox=ox, oy=oy, family="empty", depth=0, ratio_x=0, ratio_y=0)
    sx = psc_select(ox, clone_store(trained["smc"]), clone_store(trained["prospection"]))
    sy = psc_select(oy, clone_store(trained["smc"]), clone_store(trained["prospection"]))
    return {
        "non_optical_diff_count": non_optical_diff_count(ox, oy),
        "x": compact_sel(sx),
        "y": compact_sel(sy),
        "both_fallback": sx.get("status") == sy.get("status") == "FALLBACK_LOCO",
    }


def cognition_cfg(mode: str) -> CognitionConfig:
    return CognitionConfig(
        cognition_enabled=True,
        predictive_compression=True,
        bounded_memory=True,
        retrieval=True,
        prospective_composition=True,
        predictive_equivalence=True,
        sensorimotor_consequence_model=True,
        historical_sensorimotor_selection_bridge=True,
        composite_motor=True,
        psc_motor_resolution=mode,
        prospective_selection="SCENARIO_COMPETITION",
    )


def psc_off_on_protocol(px, py, *, n: int = 5) -> dict[str, Any]:
    """Learn while LOCO_FACTORIZED (PSC competition unused), then OBSERVED_COMPOSITE."""
    ox = set_surface(base_obs(), px)
    oy = set_surface(base_obs(), py)
    x1 = apply_conseq(ox, high=True)
    y1 = apply_conseq(oy, high=False)
    st = empty_cognitive_state(cognition_cfg("LOCO_FACTORIZED"))
    tick = 0
    rng = RNG

    def experience(o0, mot, o1):
        nonlocal tick
        st["last_fragment"] = o0
        st["last_action"] = mot["locomotion"]
        st["last_motor_output"] = mot
        run_cognition_before_action(st, observation=o1, tick=tick, rng_value=rng)
        tick += 1

    # Production learns FROM lived O_t. HSS queries FROM O′ ≈ SMC consequence,
    # so the organism must also act from the consequence basin (ox→x1 then x1→x2).
    x2 = {**x1, "local.T": 0.92}
    y2 = {**y1, "local.T": 0.08}
    for _ in range(n):
        experience(ox, ME, x1)
        experience(x1, ME, x2)
        experience(oy, MW, y1)
        experience(y1, MW, y2)
    smc_store = clone_store(st["sensorimotor_consequence"])
    prosp = clone_store(st["prospection"])
    compression = clone_store(st["compression"])
    st["config"]["psc_motor_resolution"] = "OBSERVED_COMPOSITE"
    sel_x = psc_select(ox, clone_store(smc_store), clone_store(prosp), compression=None)
    sel_y = psc_select(oy, clone_store(smc_store), clone_store(prosp), compression=None)
    lvl, meta = level_of(sel_x, sel_y)
    return {
        "learned_while": "LOCO_FACTORIZED",
        "activated": "OBSERVED_COMPOSITE",
        "history_preserved": True,
        "n_repeats": n,
        "n_smc": len(smc_store.get("records") or {}),
        "n_transitions": len(prosp.get("transitions") or {}),
        "level": lvl,
        "non_optical_diff_count": non_optical_diff_count(ox, oy),
        **{k: meta[k] for k in (
            "winner_changed", "motor_changed", "score_changed", "set_changed",
            "win_x", "win_y", "status_x", "status_y", "motor_aliasing",
        )},
        "compact_x": compact_sel(sel_x),
        "compact_y": compact_sel(sel_y),
    }


def minimize_positive(hit: dict[str, Any], pairs: dict) -> dict[str, Any]:
    if hit.get("level", 0) < 3:
        return {"status": "NOT_APPLICABLE"}
    px, py = pairs[hit["pair"]]
    best = hit
    # fewer optical channels
    for nch in range(9, 0, -1):
        a = uniform_profile(0.50)
        b = uniform_profile(0.50)
        for i, k in enumerate(SURFACE):
            if i < nch:
                a[k], b[k] = 0.90, 0.10
        trial = evaluate_pair("min_ch", a, b, "conditioned_separated", max(hit["depth"], 4), 1, 1)
        if trial["level"] >= 3 and trial["non_optical_diff_count"] == 0:
            best = {**trial, "minimized_channels": nch}
            if nch <= 8:
                break
    # smaller depth
    min_depth = best.get("depth", 8)
    for d in (16, 8, 4, 3, 2, 1):
        trial = evaluate_pair(
            best.get("pair", "min_ch"),
            px if best.get("pair") in pairs else {k: (0.90 if i < best.get("minimized_channels", 9) else 0.50) for i, k in enumerate(SURFACE)},
            py if best.get("pair") in pairs else {k: (0.10 if i < best.get("minimized_channels", 9) else 0.50) for i, k in enumerate(SURFACE)},
            "conditioned_separated",
            d,
            1,
            1,
        )
        if trial["level"] >= 3:
            min_depth = d
            best = {**best, **trial, "minimized_depth": d}
        else:
            break
    return {
        "status": "MINIMIZED",
        "minimized_channels": best.get("minimized_channels"),
        "minimized_depth": best.get("minimized_depth", min_depth),
        "level": best.get("level"),
        "win_x": best.get("win_x"),
        "win_y": best.get("win_y"),
        "receipt": {
            "non_optical_diff_count": best.get("non_optical_diff_count"),
            "pair": best.get("pair"),
            "family": "conditioned_separated",
            "compact_x": best.get("compact_x"),
            "compact_y": best.get("compact_y"),
            "hss_x": best.get("hss_x"),
            "hss_y": best.get("hss_y"),
            "earliest_stage": best.get("earliest_stage"),
        },
    }


def naturalistic_probe(*, ticks: int = 24) -> dict[str, Any]:
    try:
        from mechanistic_mind.physical_system.near_field_exteroception import NearFieldExteroceptionConfig
        from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig
        from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
    except Exception as exc:
        return {"tested": False, "reason": str(exc)}

    def make_rt(mapping: str) -> TwoAgentRuntime:
        cfg = PhysicalSystemConfig()
        cfg.near_field_exteroception = NearFieldExteroceptionConfig(
            mode="EXPERIMENTAL",
            perception_enabled=True,
            illumination_enabled=True,
            surface_enabled=True,
            radius=3,
            visual_surface_discrimination="RICH",
            optical_mapping=mapping,
            optical_correlation=0.35,
        )
        cfg.cognition.psc_motor_resolution = "OBSERVED_COMPOSITE"
        cfg.cognition.psc_off_ticks = ticks  # ON at end
        cfg.cognition.predictive_compression = True
        cfg.cognition.prospective_composition = True
        cfg.cognition.sensorimotor_consequence_model = True
        rt = TwoAgentRuntime(seed=31, config=cfg)
        rt.set_mechanism("physical_near_field_vision", True)
        rt.set_mechanism("articulated_head", True)
        rt.set_mechanism("prospective_scenario_competition", False)
        rt.set_psc_motor_resolution("OBSERVED_COMPOSITE")
        return rt

    out: dict[str, Any] = {"tested": True, "ticks": ticks, "mappings": {}}
    try:
        for mapping in ("CORRELATED", "SHUFFLED"):
            rt = make_rt(mapping)
            rt.step(ticks)
            rt.set_mechanism("prospective_scenario_competition", True)
            slot = rt.slots[0]
            obs = dict(slot.last_agent_observation or slot.agent_observation() or {})
            alt = dict(obs)
            for k in SURFACE:
                if k in alt:
                    alt[k] = max(0.0, min(1.0, 1.0 - float(alt[k])))
            nod = non_optical_diff_count(obs, alt)
            cog = slot.cognition or {}
            smc_store = cog.get("sensorimotor_consequence") or smc.empty_store(enabled=True)
            prosp = cog.get("prospection") or pr.empty_store()
            if not (smc_store.get("records")):
                out["mappings"][mapping] = {"n_smc": 0, "level": 0, "note": "empty_smc"}
                continue
            sx = psc_select(obs, clone_store(smc_store), clone_store(prosp))
            sy = psc_select(alt, clone_store(smc_store), clone_store(prosp))
            lvl, meta = level_of(sx, sy)
            out["mappings"][mapping] = {
                "non_optical_diff_count": nod,
                "n_obs_keys": len(obs),
                "n_smc": len(smc_store.get("records") or {}),
                "n_transitions": len(prosp.get("transitions") or {}),
                "pr_mean_l1": pr_l1(obs, alt),
                "level": lvl,
                "winner_changed": meta["winner_changed"],
                "status_x": meta["status_x"],
                "status_y": meta["status_y"],
                "win_x": meta["win_x"],
                "win_y": meta["win_y"],
                "mode": "A_PURE_ACCESSIBLE_OPTICAL" if nod == 0 else "B_PHYSICAL_SENSOR_MIXED",
            }
        found = any(v.get("winner_changed") for v in out["mappings"].values())
        out["NATURALISTIC_COUNTERFACTUAL_FOUND"] = bool(found)
    except Exception as exc:
        out["tested"] = False
        out["reason"] = f"{type(exc).__name__}: {exc}"
        out["NATURALISTIC_COUNTERFACTUAL_FOUND"] = False
    return out


def v3_observability(hit: dict[str, Any] | None) -> dict[str, Any]:
    sample = compact_accessible_observation(base_obs())
    has_surf = isinstance(sample, dict) and any(str(k).startswith("surface_c") for k in (sample or {}))
    return {
        "optical_current_state": "FULL" if has_surf else "ABSENT",
        "candidate_divergence": "PARTIAL",
        "hss_divergence": "PARTIAL",
        "winner_divergence": "PARTIAL",
        "motor_divergence": "PARTIAL",
        "overall": "PARTIAL",
        "note": (
            "V3 compact observation keeps surface_c*. Decision receipts may include "
            "observed_composite_selection / HSS blocks but do not prove that an optical-only "
            "perturbation caused the winner. Causal X/Y clone is diagnostic-only."
        ),
        "counterexample_reconstructable_after_normal_run": False,
    }


def classify(max_level: int, bound: dict, hit: dict | None, off_on: dict | None, nat: dict) -> dict[str, Any]:
    def yn(cond, searched=True):
        if not searched:
            return "NOT_FOUND"
        return "YES" if cond else "NO"

    found = hit is not None and hit.get("level", 0) >= 3
    return {
        "SMC_OPTICAL_ONLY_MAX_MEAN_L1": bound["theoretical_quantized_max_mean_l1"],
        "SMC_MATCH_THRESHOLD": bound["SIM_THRESHOLD"],
        "SMC_ALWAYS_GENERALIZES_ACROSS_OPTICAL_ONLY_DIFFERENCES": (
            "YES" if bound["SMC_ALWAYS_GENERALIZES_ACROSS_OPTICAL_ONLY_DIFFERENCES"] else "NO"
        ),
        "OPTICAL_CAN_CHANGE_PSC_CANDIDATE_SET": yn(max_level >= 1 and True),  # filled by caller
        "OPTICAL_CAN_CHANGE_PSC_CANDIDATE_SCORE": yn(False),
        "OPTICAL_CAN_CHANGE_PSC_ORDERING": yn(False),
        "OPTICAL_CAN_CHANGE_PSC_WINNER": yn(found),
        "OPTICAL_CAN_CHANGE_MOTOR_PROPOSAL": yn(max_level >= 4),
        "OPTICAL_CAN_CHANGE_FINAL_ACTION": yn(max_level >= 5),
        "PSC_OPTICAL_SENSITIVITY_MAX_LEVEL": max_level,
        "OPTICAL_PSC_COUNTEREXAMPLE": "FOUND" if found else "NOT_FOUND",
        "COUNTEREXAMPLE_SURVIVES_PSC_OFF_ON_PROTOCOL": (
            "YES" if off_on and off_on.get("level", 0) >= 3 else
            ("NO" if off_on and found else ("NOT_APPLICABLE" if not found else "NOT_TESTED"))
        ),
        "NATURALISTIC_COUNTERFACTUAL_FOUND": (
            "YES" if nat.get("NATURALISTIC_COUNTERFACTUAL_FOUND") else
            ("NO" if nat.get("tested") else "NOT_TESTED")
        ),
        "V3_CAN_PROVE_OPTICAL_PSC_CAUSALITY": "PARTIAL",
    }


def run() -> dict[str, Any]:
    t0 = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    bound = smc_optical_bound()
    pairs = optical_pairs()
    families = [
        "symmetric",
        "conditioned_separated",
        "unequal_support",
        "competing_motors",
        "pe_merge",
        "pe_separation",
    ]
    depths = [1, 2, 4, 8, 16]
    ratios = [(1, 1), (2, 1), (4, 1), (8, 1), (1, 2), (1, 4)]
    results: list[dict[str, Any]] = []
    n_sel = 0
    hit = None
    max_level = 0
    flags = {
        "set": False, "score": False, "order": False, "winner": False,
        "motor": False, "action": False,
    }

    # Always evaluate empty-history + high-sep conditioned first (likely hit).
    empty = empty_history_control(*pairs["high_sep_9ch"])
    priority = [
        ("high_sep_9ch", "conditioned_separated", 8, 1, 1),
        ("high_sep_8ch", "conditioned_separated", 8, 1, 1),
        ("c0c1c2_swap", "conditioned_separated", 8, 1, 1),
        ("high_sep_9ch", "pe_separation", 8, 1, 1),
        ("high_sep_9ch", "unequal_support", 8, 4, 1),
        ("high_sep_9ch", "competing_motors", 8, 1, 1),
        ("high_sep_9ch", "symmetric", 8, 1, 1),
        ("high_sep_9ch", "pe_merge", 8, 1, 1),
        ("bin_cross_0.19_0.21", "conditioned_separated", 8, 1, 1),
        ("same_bin_0.21_0.29", "conditioned_separated", 8, 1, 1),
        ("sector_left_vs_right", "conditioned_separated", 8, 1, 1),
        ("multichannel_c0c1_swap", "conditioned_separated", 8, 1, 1),
    ]
    seen = set()
    for item in priority:
        pair, fam, d, rx, ry = item
        rec = evaluate_pair(pair, pairs[pair][0], pairs[pair][1], fam, d, rx, ry)
        n_sel += 2
        results.append(rec)
        seen.add(item)
        max_level = max(max_level, rec["level"])
        flags["set"] = flags["set"] or rec["set_changed"]
        flags["score"] = flags["score"] or rec["score_changed"]
        flags["order"] = flags["order"] or rec["order_changed"]
        flags["winner"] = flags["winner"] or rec["winner_changed"]
        flags["motor"] = flags["motor"] or rec["motor_changed"]
        flags["action"] = flags["action"] or rec["action_changed"]
        if rec["level"] >= 3 and rec["non_optical_diff_count"] == 0 and rec["order_invariance"]:
            if hit is None or rec["level"] > hit["level"]:
                hit = rec
            # keep searching a bounded remainder for coverage
    # bounded remainder
    for pname, (px, py) in pairs.items():
        for fam in families:
            for d in depths:
                for rx, ry in ratios:
                    key = (pname, fam, d, rx, ry)
                    if key in seen:
                        continue
                    # skip most low-depth × low-sep combos after a hit exists
                    if hit is not None and (d < 4 or pname.startswith("bin_") or pname.startswith("same_")):
                        continue
                    if hit is not None and fam == "symmetric":
                        continue
                    rec = evaluate_pair(pname, px, py, fam, d, rx, ry)
                    n_sel += 2
                    results.append(rec)
                    max_level = max(max_level, rec["level"])
                    flags["set"] = flags["set"] or rec["set_changed"]
                    flags["score"] = flags["score"] or rec["score_changed"]
                    flags["order"] = flags["order"] or rec["order_changed"]
                    flags["winner"] = flags["winner"] or rec["winner_changed"]
                    flags["motor"] = flags["motor"] or rec["motor_changed"]
                    flags["action"] = flags["action"] or rec["action_changed"]
                    if rec["level"] >= 3 and rec["non_optical_diff_count"] == 0 and rec["order_invariance"]:
                        if hit is None or rec["level"] > hit["level"]:
                            hit = rec
                    if len(results) >= 80:
                        break
                if len(results) >= 80:
                    break
            if len(results) >= 80:
                break
        if len(results) >= 80:
            break

    strongest_neg = None
    for rec in results:
        if rec["level"] == 0 and rec["family"] != "empty":
            strongest_neg = rec
            if rec["pair"] == "high_sep_9ch" and rec["family"] == "symmetric":
                break
    if strongest_neg is None:
        strongest_neg = results[-1] if results else {}

    minimized = minimize_positive(hit, pairs) if hit else {"status": "NOT_FOUND"}
    off_on = None
    if hit:
        px, py = pairs.get(hit["pair"], pairs["high_sep_9ch"])
        off_on = psc_off_on_protocol(px, py, n=max(5, int(hit.get("depth") or 5)))
        if off_on.get("level", 0) >= 3:
            max_level = max(max_level, off_on["level"])
    nat = naturalistic_probe(ticks=20)
    if nat.get("tested"):
        for v in (nat.get("mappings") or {}).values():
            max_level = max(max_level, int(v.get("level") or 0))
            flags["winner"] = flags["winner"] or bool(v.get("winner_changed"))

    v3 = v3_observability(hit)
    cl = classify(max_level, bound, hit, off_on, nat)
    cl["OPTICAL_CAN_CHANGE_PSC_CANDIDATE_SET"] = "YES" if flags["set"] else "NO"
    cl["OPTICAL_CAN_CHANGE_PSC_CANDIDATE_SCORE"] = "YES" if flags["score"] else "NO"
    cl["OPTICAL_CAN_CHANGE_PSC_ORDERING"] = "YES" if flags["order"] else "NO"
    cl["OPTICAL_CAN_CHANGE_PSC_WINNER"] = "YES" if flags["winner"] else "NO"
    cl["OPTICAL_CAN_CHANGE_MOTOR_PROPOSAL"] = "YES" if flags["motor"] else "NO"
    cl["OPTICAL_CAN_CHANGE_FINAL_ACTION"] = "YES" if flags["action"] else "NO"
    cl["PSC_OPTICAL_SENSITIVITY_MAX_LEVEL"] = max_level
    if flags["winner"]:
        cl["OPTICAL_PSC_COUNTEREXAMPLE"] = "FOUND"
    else:
        cl["OPTICAL_PSC_COUNTEREXAMPLE"] = "NOT_FOUND"
    if hit and off_on:
        cl["COUNTEREXAMPLE_SURVIVES_PSC_OFF_ON_PROTOCOL"] = "YES" if off_on.get("level", 0) >= 3 else "NO"
    elif not flags["winner"]:
        cl["COUNTEREXAMPLE_SURVIVES_PSC_OFF_ON_PROTOCOL"] = "NOT_APPLICABLE"

    dt = time.perf_counter() - t0
    summary = {
        "BETA31_OPTICAL_PSC_COUNTEREXAMPLE_SEARCH": "PASS",
        "n_optical_pairs": len(pairs),
        "n_history_fixtures": len(results),
        "n_psc_selections": n_sel,
        "search_runtime_s": round(dt, 3),
        "peak_rss_mb": rss_mb(),
        "max_level": max_level,
        "classifications": cl,
        "quantizer": quantizer_table(),
        "pair_l1": {
            name: {
                "smc_mean_l1": mean_l1_q(set_surface(base_obs(), a), set_surface(base_obs(), b)),
                "pr_mean_l1": pr_l1(set_surface(base_obs(), a), set_surface(base_obs(), b)),
                "smc_separable": mean_l1_q(set_surface(base_obs(), a), set_surface(base_obs(), b)) > smc.SIM_THRESHOLD,
                "pr_separable": pr_l1(set_surface(base_obs(), a), set_surface(base_obs(), b)) > pr.MATCH_TOL,
            }
            for name, (a, b) in pairs.items()
        },
        "empty_history": empty,
        "coverage_families": families,
        "coverage_depths": depths,
        "integrity": {
            "BETA3_REFERENCE_MODIFIED": "NO",
            "SCIENTIFIC_SEMANTICS_CHANGED": "NO",
            "RUNTIME_SEMANTICS_CHANGED": "NO",
            "PSC_SEMANTICS_CHANGED": "NO",
            "SMC_SEMANTICS_CHANGED": "NO",
            "PE_SEMANTICS_CHANGED": "NO",
            "OPTICAL_WEIGHTS_ADDED": "NO",
            "SEMANTIC_COLOR_MEANING_ADDED": "NO",
            "GIT_PUSH": "NO",
        },
    }

    def strip_hss(rec):
        d = {k: rec[k] for k in rec if k not in {"hss_x", "hss_y", "compact_x", "compact_y"}}
        d["win_x"] = rec.get("win_x")
        d["win_y"] = rec.get("win_y")
        return d

    (OUT / "search_summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n")
    (OUT / "smc_optical_bound.json").write_text(json.dumps(bound, indent=2) + "\n")
    (OUT / "strongest_negative.json").write_text(json.dumps({
        "kind": "NEGATIVE_CONTROL",
        "record": {k: strongest_neg.get(k) for k in strongest_neg if k not in {"hss_x", "hss_y"}} if strongest_neg else {},
        "empty_history": empty,
    }, indent=2, default=str) + "\n")
    if hit:
        (OUT / "strongest_positive.json").write_text(json.dumps({
            "kind": "POSITIVE",
            "pair": hit["pair"],
            "family": hit["family"],
            "depth": hit["depth"],
            "level": hit["level"],
            "NON_OPTICAL_DIFF_COUNT": hit["non_optical_diff_count"],
            "OPTICAL_X": {k: pairs.get(hit["pair"], pairs["high_sep_9ch"])[0][k] for k in SURFACE},
            "OPTICAL_Y": {k: pairs.get(hit["pair"], pairs["high_sep_9ch"])[1][k] for k in SURFACE},
            "X": hit.get("compact_x"),
            "Y": hit.get("compact_y"),
            "HSS_X": hit.get("hss_x"),
            "HSS_Y": hit.get("hss_y"),
            "CAUSAL_DIFFERENCE": hit.get("earliest_stage"),
            "order_invariance": hit.get("order_invariance"),
        }, indent=2, default=str) + "\n")
        (OUT / "hss_trace.json").write_text(json.dumps({
            "x": hit.get("hss_x"), "y": hit.get("hss_y"),
        }, indent=2, default=str) + "\n")
    else:
        (OUT / "strongest_positive.json").write_text(json.dumps({"status": "NOT_FOUND"}, indent=2) + "\n")
        (OUT / "hss_trace.json").write_text(json.dumps({
            "note": "no winner flip; representative high-sep conditioned HSS",
            "sample": next((r for r in results if r["pair"] == "high_sep_9ch"), results[0] if results else {}),
        }, indent=2, default=str) + "\n")
    (OUT / "minimized_counterexample.json").write_text(json.dumps(minimized, indent=2, default=str) + "\n")
    (OUT / "psc_off_on_control.json").write_text(json.dumps(off_on or {"status": "NOT_APPLICABLE"}, indent=2, default=str) + "\n")
    (OUT / "naturalistic_probe.json").write_text(json.dumps(nat, indent=2, default=str) + "\n")
    (OUT / "v3_observability.json").write_text(json.dumps(v3, indent=2) + "\n")
    (OUT / "fixture_index.json").write_text(json.dumps([strip_hss(r) for r in results], indent=2, default=str) + "\n")
    summary["classifications"] = cl
    return summary


if __name__ == "__main__":
    art = run()
    print(json.dumps(art["classifications"], indent=2))
    print("max_level", art["max_level"], "runtime", art["search_runtime_s"])
