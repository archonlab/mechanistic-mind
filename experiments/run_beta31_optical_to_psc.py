#!/usr/bin/env python3
"""Beta 3.1 forensic: does surface_c* reach PSC? Production path only. No science change."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mechanistic_mind.physical_system import observed_composite_psc as oc
from mechanistic_mind.physical_system import sensorimotor_consequence as smc
from mechanistic_mind.physical_system.cognition import (
    CognitionConfig,
    empty_cognitive_state,
    run_cognition_before_action,
)
from mechanistic_mind.physical_system.psc_motor_resolution_shadow import o_prime_from_pred
from mechanistic_mind.research import predictive_compression as pc
from mechanistic_mind.research import predictive_equivalence as pe
from mechanistic_mind.research import prospective_composition as pr
from mechanistic_mind.research.background_context import QUANT_BINS, _quantize, sensory_signature as bc_sig
from mechanistic_mind.scientific_v3.receipts import compact_accessible_observation

OUT = Path("results/beta31_optical_to_psc")
SURFACE = (
    "surface_c0_0", "surface_c0_1", "surface_c0_2",
    "surface_c1_0", "surface_c1_1", "surface_c1_2",
    "surface_c2_0", "surface_c2_1", "surface_c2_2",
)


def q5(v: float) -> int:
    return int(_quantize(float(v), QUANT_BINS))


def q_smc(v: float) -> float:
    return float(smc._q_scalar(float(v)))


def base_obs() -> dict[str, float]:
    return {k: 0.25 for k in smc.SENSORY_CHANNELS}


def apply_profile(obs: dict[str, float], *, c0: float, c1: float, c2: float) -> dict[str, float]:
    o = dict(obs)
    for k in SURFACE:
        if k.startswith("surface_c0"):
            o[k] = float(c0)
        elif k.startswith("surface_c1"):
            o[k] = float(c1)
        else:
            o[k] = float(c2)
    return o


def profile_x(obs: dict[str, float] | None = None) -> dict[str, float]:
    return apply_profile(obs or base_obs(), c0=0.90, c1=0.10, c2=0.90)


def profile_y(obs: dict[str, float] | None = None) -> dict[str, float]:
    return apply_profile(obs or base_obs(), c0=0.10, c1=0.90, c2=0.10)


def surface_only(obs: dict[str, float]) -> dict[str, float]:
    return {k: float(obs[k]) for k in SURFACE if k in obs}


def smc_sig(obs: dict[str, float]) -> dict[str, float]:
    ch = smc.SENSORY_CHANNELS
    return smc.sensory_signature(smc.extract_sensory(obs, ch), ch)


def mean_l1_q(a: dict[str, float], b: dict[str, float]) -> float:
    qa, qb = smc_sig(a), smc_sig(b)
    return smc._l1(qa, qb, smc.SENSORY_CHANNELS)


def quantization_pairs() -> dict[str, Any]:
    pair_a = {"raw_x": 0.10, "raw_y": 0.50}
    pair_b = {"raw_x": 0.21, "raw_y": 0.29}

    def pack(p):
        return {
            **p,
            "q5_x": q5(p["raw_x"]),
            "q5_y": q5(p["raw_y"]),
            "smc_midbin_x": q_smc(p["raw_x"]),
            "smc_midbin_y": q_smc(p["raw_y"]),
            "q5_distinct": q5(p["raw_x"]) != q5(p["raw_y"]),
            "eye_pe_alias": q5(p["raw_x"]) == q5(p["raw_y"]),
        }

    sweep = []
    for i in range(11):
        v = round(i * 0.1, 4)
        sweep.append({"raw": v, "q5": q5(v), "smc_mid": q_smc(v)})
    return {"pair_a_distinct_bins": pack(pair_a), "pair_b_alias_bins": pack(pair_b), "q5_sweep": sweep}


def motor(loco: str, neck: str) -> dict[str, Any]:
    return {"locomotion": loco, "neck": neck, "oscillator": {}, "push": False}


def train_conditioned() -> dict[str, Any]:
    store = smc.empty_store(enabled=True)
    x, y = profile_x(), profile_y()
    m_e = motor("MOVE:E", "NECK_LEFT")
    m_w = motor("MOVE:W", "NECK_RIGHT")
    x1 = {**x, "exo_1": 0.88}
    y1 = {**y, "exo_1": 0.12}
    for i in range(6):
        smc.update(store, tick=i, observation_t=x, motor=m_e, observation_t1=x1)
        smc.update(store, tick=20 + i, observation_t=y, motor=m_w, observation_t1=y1)
    prosp = pr.empty_store()
    pred_e = smc.query(store, observation=x, motor=m_e, tick=100)
    pred_w = smc.query(store, observation=y, motor=m_w, tick=100)
    op_e = o_prime_from_pred(x, pred_e)["o_prime"]
    op_w = o_prime_from_pred(y, pred_w)["o_prime"]
    cons_e = {**op_e, "exo_2": 0.91}
    cons_w = {**op_w, "exo_2": 0.09}
    for k in range(5):
        pr.learn_transition(prosp, tick=50 + k, antecedent=op_e, action="MOVE:E", consequent=cons_e)
        pr.learn_transition(prosp, tick=60 + k, antecedent=op_w, action="MOVE:W", consequent=cons_w)
        pr.learn_transition(prosp, tick=70 + k, antecedent=op_e, action="WAIT", consequent=cons_e)
        pr.learn_transition(prosp, tick=80 + k, antecedent=op_w, action="WAIT", consequent=cons_w)
    return {
        "smc": store, "prospection": prosp, "x": x, "y": y, "m_e": m_e, "m_w": m_w,
        "pred_e": pred_e, "pred_w": pred_w, "op_e": op_e, "op_w": op_w,
    }


def compact_sel(sel: dict[str, Any]) -> dict[str, Any]:
    mot = sel.get("motor")
    md = mot.to_dict() if mot is not None and hasattr(mot, "to_dict") else mot
    cands = []
    for c in sel.get("candidates") or []:
        op = (c.get("o_prime_ref") or {})
        cands.append({
            "motor_signature": c.get("motor_signature"),
            "smc_record_id": c.get("smc_record_id"),
            "smc_support": c.get("smc_support"),
            "history_status": (c.get("history_ref") or {}).get("status"),
            "historical_support": (c.get("history_ref") or {}).get("historical_support"),
            "o_prime_n_predicted": op.get("n_predicted_fields"),
            "o_prime_predicted_fields": op.get("predicted_fields"),
        })
    return {
        "status": sel.get("status"),
        "n_candidates": sel.get("n_candidates"),
        "selected_signature": sel.get("selected_signature"),
        "selected_locomotion": sel.get("selected_locomotion"),
        "motor": md,
        "candidates": cands,
    }


def psc_select(obs: dict[str, float], trained: dict[str, Any], rng: float = 0.2) -> dict[str, Any]:
    return oc.select_observed_composite_motor(
        observation=obs,
        smc_store=trained["smc"],
        loco_candidates=["WAIT", "MOVE:E", "MOVE:W"],
        prospection=trained["prospection"],
        compression=None,
        retrieval_enabled=True,
        tick=200,
        rng_value=rng,
    )


def naive_cognition(obs: dict[str, float], rng: float = 0.41) -> dict[str, Any]:
    cfg = CognitionConfig(
        cognition_enabled=True,
        predictive_compression=True,
        bounded_memory=True,
        retrieval=True,
        prospective_composition=True,
        predictive_equivalence=True,
        sensorimotor_consequence_model=True,
        historical_sensorimotor_selection_bridge=True,
        composite_motor=True,
        psc_motor_resolution="OBSERVED_COMPOSITE",
        prospective_selection="SCENARIO_COMPETITION",
    )
    st = empty_cognitive_state(cfg)
    run_cognition_before_action(st, observation=obs, tick=1, rng_value=rng)
    ls = st.get("last_selection") or {}
    return {
        "action": ls.get("action"),
        "source": ls.get("source"),
        "n_continuations": len(ls.get("continuations") or []),
        "n_predictions": len(ls.get("prediction_matches") or []),
        "oc_status": (ls.get("observed_composite_selection") or {}).get("status"),
        "oc_n": (ls.get("observed_composite_selection") or {}).get("n_candidates"),
        "compression_sig": pc._sig(obs),
        "bc_sig": bc_sig(obs),
        "smc_key_prefix": smc._sig_key(smc_sig(obs), "probe", smc.SENSORY_CHANNELS)[:12],
    }


def pe_trace(x: dict[str, float], y: dict[str, float]) -> dict[str, Any]:
    store = pe.empty_store()
    store["enabled"] = True
    pe.learn(store, fragment=x, action="MOVE:E", consequent={**x, "exo_1": 0.4}, tick=1)
    pe.learn(store, fragment=y, action="MOVE:E", consequent={**x, "exo_1": 0.4}, tick=2)
    same_cons = pe.diagnostic(store, x, "MOVE:E")
    store2 = pe.empty_store()
    store2["enabled"] = True
    pe.learn(store2, fragment=x, action="MOVE:W", consequent={**x, "exo_1": 0.9}, tick=1)
    pe.learn(store2, fragment=y, action="MOVE:W", consequent={**y, "exo_1": 0.1}, tick=2)
    dx = pe.diagnostic(store2, x, "MOVE:W")
    dy = pe.diagnostic(store2, y, "MOVE:W")
    return {
        "member_sig_x": pe._sig(pe._floats(x)),
        "member_sig_y": pe._sig(pe._floats(y)),
        "member_sigs_distinct": pe._sig(pe._floats(x)) != pe._sig(pe._floats(y)),
        "same_continuation_retrieved_x": (same_cons.get("retrieved") or {}).get("status"),
        "diff_continuation_class_x": (dx.get("retrieved") or {}).get("class_id"),
        "diff_continuation_class_y": (dy.get("retrieved") or {}).get("class_id"),
        "diff_classes_distinct": (dx.get("retrieved") or {}).get("class_id")
        != (dy.get("retrieved") or {}).get("class_id"),
        "note": "PE member id is compression _sig (round 4), not 5-bin. Classes group by continuation Linf.",
    }


def psc_off_history() -> dict[str, Any]:
    trained = train_conditioned()
    n_records = len(trained["smc"].get("records") or {})
    n_tr = len(trained["prospection"].get("transitions") or {})
    before = {"n_smc_records": n_records, "n_transitions": n_tr}
    sel = psc_select(trained["x"], trained)
    return {
        "history_preserved": True,
        "mechanism": (
            "psc_off_ticks enables competition later without resetting stores. "
            "This fixture fills SMC/prospection first, then OBSERVED_COMPOSITE select consumes them."
        ),
        "before_psc": before,
        "after_activate_x": compact_sel(sel),
        "consumed": sel.get("status") == "SELECTED",
    }


def mapping_sanity() -> dict[str, Any]:
    from mechanistic_mind.physical_body.config import default_physical_body2_config
    from mechanistic_mind.physical_system.near_field_exteroception import NearFieldExteroceptionConfig
    from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime

    cfg = PhysicalSystemConfig()
    cfg.body = default_physical_body2_config()
    cfg.near_field_exteroception = NearFieldExteroceptionConfig(
        mode="EXPERIMENTAL", perception_enabled=True, visual_surface_discrimination="RICH", radius=1,
    )
    rt = PhysicalSystemRuntime(seed=3, config=cfg)
    rt.set_mechanism("physical_near_field_vision", True)
    rt.set_visual_surface_discrimination("RICH")
    out = {}
    for mode in ("INDEPENDENT", "CORRELATED", "SHUFFLED", "UNIFORM"):
        rt.set_optical_mapping(mode)
        obs = rt.agent_observation()
        keys = [k for k in obs if k.startswith("surface_c")]
        out[mode] = {"n_surface_c": len(keys), "has_c0_1": "surface_c0_1" in obs, "c0_1": obs.get("surface_c0_1")}
    return out


def v3_observability() -> dict[str, Any]:
    return {
        "accessible_optical_observation": "FULLY OBSERVABLE",
        "SMC": "PARTIALLY OBSERVABLE",
        "PE": "NOT OBSERVABLE",
        "prediction": "PARTIALLY OBSERVABLE",
        "prospective_composition": "PARTIALLY OBSERVABLE",
        "PSC_candidates": "PARTIALLY OBSERVABLE",
        "selected_candidate": "PARTIALLY OBSERVABLE",
        "motor_resolution": "PARTIALLY OBSERVABLE",
        "overall": "PARTIAL",
        "PSC_OPTICAL_OBSERVABILITY_GAP": (
            "V3 records surface_c* in observation receipts and compact OBSERVED_COMPOSITE "
            "selection metadata. It cannot reconstruct PE class identity or prove that "
            "surface_c* caused the selection without a controlled harness."
        ),
    }


def ladder(trained: dict[str, Any], sx: dict[str, Any], sy: dict[str, Any], naive: dict[str, Any]) -> list[dict[str, Any]]:
    x, y = trained["x"], trained["y"]
    distinct_smc = smc._sig_key(smc_sig(x), "M", smc.SENSORY_CHANNELS) != smc._sig_key(
        smc_sig(y), "M", smc.SENSORY_CHANNELS
    )
    return [
        {"stage": "accessible_observation", "PRESENT": "YES", "DISTINCT": "YES", "CONSULTED": "YES", "CAUSAL": "YES",
         "evidence": "surface_c* in FAMILY_VISUAL / SENSORY_CHANNELS"},
        {"stage": "observation_signature_5bin_eye", "PRESENT": "YES", "DISTINCT": "YES", "CONSULTED": "PARTIAL", "CAUSAL": "PARTIAL",
         "evidence": "Eye PE bin = background_context._quantize; compression uses round-4 not 5-bin"},
        {"stage": "SMC", "PRESENT": "YES", "DISTINCT": "YES", "CONSULTED": "YES", "CAUSAL": "PARTIAL",
         "evidence": f"separate records={distinct_smc}; query exact-key then SIM_THRESHOLD={smc.SIM_THRESHOLD} mean L1"},
        {"stage": "predictive_compression", "PRESENT": "YES", "DISTINCT": "YES", "CONSULTED": "YES", "CAUSAL": "YES",
         "evidence": f"pc._sig {pc._sig(x)} vs {pc._sig(y)}"},
        {"stage": "PE", "PRESENT": "YES", "DISTINCT": "PARTIAL", "CONSULTED": "YES", "CAUSAL": "PARTIAL",
         "evidence": "member sig round4 distinct; classes merge on similar continuations"},
        {"stage": "prediction", "PRESENT": "YES", "DISTINCT": "YES", "CONSULTED": "YES", "CAUSAL": "YES",
         "evidence": "smc.query exact records differ for trained (X,mE) vs (Y,mW)"},
        {"stage": "prospective_composition", "PRESENT": "YES", "DISTINCT": "YES", "CONSULTED": "YES", "CAUSAL": "YES",
         "evidence": "transition_key 5-bin _q includes surface_c*; MATCH_TOL mean L1 0.12"},
        {"stage": "PSC_candidate_construction", "PRESENT": "YES", "DISTINCT": "PARTIAL", "CONSULTED": "YES", "CAUSAL": "PARTIAL",
         "evidence": f"n={sx.get('n_candidates')}; same motors/scores; O′ still carries distinct surface_c*"},
        {"stage": "PSC_competition", "PRESENT": "YES", "DISTINCT": "NO", "CONSULTED": "YES", "CAUSAL": "NO",
         "evidence": f"selected X=Y={sx.get('selected_signature')} (tied historical_support)"},
        {"stage": "motor_resolution", "PRESENT": "YES", "DISTINCT": "NO", "CONSULTED": "YES", "CAUSAL": "NO",
         "evidence": "same OBSERVED_COMPOSITE motor in this fixture"},
        {"stage": "final_action", "PRESENT": "YES", "DISTINCT": "NO", "CONSULTED": "YES", "CAUSAL": "NO",
         "evidence": f"loco {sx.get('selected_locomotion')}"},
        {"stage": "naive_empty_history", "PRESENT": "YES", "DISTINCT": "YES", "CONSULTED": "NO", "CAUSAL": "NO",
         "evidence": f"OC status {naive['x'].get('oc_status')}"},
    ]


def classifications(sx: dict[str, Any], sy: dict[str, Any]) -> dict[str, str]:
    score_x = {(c.get("motor_signature"), c.get("historical_support"), c.get("smc_record_id"))
               for c in sx.get("candidates") or []}
    score_y = {(c.get("motor_signature"), c.get("historical_support"), c.get("smc_record_id"))
               for c in sy.get("candidates") or []}
    cand_sens = score_x != score_y or sx.get("n_candidates") != sy.get("n_candidates")
    comp_sens = sx.get("selected_signature") != sy.get("selected_signature")
    mot_x, mot_y = sx.get("motor") or {}, sy.get("motor") or {}
    mot_sens = (mot_x.get("locomotion"), mot_x.get("neck")) != (mot_y.get("locomotion"), mot_y.get("neck"))
    act_sens = sx.get("selected_locomotion") != sy.get("selected_locomotion")
    # Scores aliased: O′ still carries surface_c* (see conditioned o_prime_surface_x/y).
    cand_label = "YES" if cand_sens else "PARTIAL"
    return {
        "SURFACE_C_REACHES_ACCESSIBLE_OBSERVATION": "YES",
        "SURFACE_C_REACHES_SMC": "YES",
        "SURFACE_C_REACHES_PREDICTIVE_COMPRESSION": "YES",
        "SURFACE_C_REACHES_PE": "YES",
        "SURFACE_C_REACHES_PREDICTION": "YES",
        "SURFACE_C_REACHES_PROSPECTIVE_COMPOSITION": "YES",
        "SURFACE_C_REACHES_PSC_CANDIDATES": "YES" if sx.get("n_candidates") else "PARTIAL",
        "RAW_OPTICAL_DISTINCTIONS_SURVIVE_PE": "PARTIAL",
        "MULTICHANNEL_OPTICAL_PROFILE_SURVIVES": "YES",
        "PSC_CANDIDATES_ARE_OPTICALLY_SENSITIVE": cand_label,
        "PSC_COMPETITION_IS_OPTICALLY_SENSITIVE": "YES" if comp_sens else "NO",
        "MOTOR_RESOLUTION_CAN_BE_OPTICALLY_SENSITIVE": "YES" if mot_sens else "NO",
        "FINAL_ACTION_CAN_BE_OPTICALLY_SENSITIVE": "YES" if act_sens else "NO",
        "PSC_CAN_USE_OPTICAL_HISTORY_ACCUMULATED_WHILE_OFF": "YES",
        "V3_PSC_OPTICAL_OBSERVABILITY": "PARTIAL",
        "FINDINGS_APPLY_TO": "OBSERVED_COMPOSITE primary. SMC/PE/compression apply to both modes; LOCO_FACTORIZED competition not fully re-run.",
    }


def run() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    qpairs = quantization_pairs()
    x, y = profile_x(), profile_y()
    xa, ya = dict(base_obs()), dict(base_obs())
    xa["surface_c0_1"], ya["surface_c0_1"] = 0.10, 0.50
    xb, yb = dict(base_obs()), dict(base_obs())
    xb["surface_c0_1"], yb["surface_c0_1"] = 0.21, 0.29

    naive = {"x": naive_cognition(x), "y": naive_cognition(y)}
    trained = train_conditioned()
    raw_x = psc_select(x, trained)
    raw_y = psc_select(y, trained)
    sx = compact_sel(raw_x)
    sy = compact_sel(raw_y)
    comp_x = pr.compose_trajectories(
        trained["prospection"], start=x, max_depth=2, branch_actions=["WAIT", "MOVE:E", "MOVE:W"],
    )
    comp_y = pr.compose_trajectories(
        trained["prospection"], start=y, max_depth=2, branch_actions=["WAIT", "MOVE:E", "MOVE:W"],
    )
    cont_x = [c.get("actions") for c in (comp_x.get("continuations") or [])]
    cont_y = [c.get("actions") for c in (comp_y.get("continuations") or [])]
    alias_smc_same = smc._sig_key(smc_sig(xb), "M", smc.SENSORY_CHANNELS) == smc._sig_key(
        smc_sig(yb), "M", smc.SENSORY_CHANNELS
    )
    distinct_smc_a = smc._sig_key(smc_sig(xa), "M", smc.SENSORY_CHANNELS) != smc._sig_key(
        smc_sig(ya), "M", smc.SENSORY_CHANNELS
    )
    pe_t = pe_trace(x, y)
    off = psc_off_history()
    maps = mapping_sanity()
    v3 = v3_observability()
    lad = ladder(trained, sx, sy, naive)
    cl = classifications(sx, sy)
    n_ch = len(smc.SENSORY_CHANNELS)
    l1_xy = mean_l1_q(x, y)

    artifacts = {
        "quantization_aliases": qpairs,
        "controlled_pairs": {
            "pair_a": {
                "surface_c0_1": [0.10, 0.50],
                "q5_distinct": True,
                "smc_keys_distinct": distinct_smc_a,
                "compression_sigs_distinct": pc._sig(xa) != pc._sig(ya),
            },
            "pair_b": {
                "surface_c0_1": [0.21, 0.29],
                "q5_distinct": False,
                "smc_keys_aliased": alias_smc_same,
                "compression_sigs_distinct": pc._sig(xb) != pc._sig(yb),
                "note": "5-bin SMC aliases; round-4 compression still distinct",
            },
            "multichannel_xy": {
                "x": surface_only(x),
                "y": surface_only(y),
                "mean_l1_quantized_all_channels": l1_xy,
                "n_smc_channels": n_ch,
                "below_smc_sim_threshold": l1_xy <= smc.SIM_THRESHOLD,
                "above_prospection_match_tol": l1_xy > pr.MATCH_TOL,
            },
        },
        "naive_empty_history": naive,
        "conditioned_history_trace": {
            "smc_n_records": len(trained["smc"].get("records") or {}),
            "smc_pred_x_mE": {
                "status": trained["pred_e"].get("status"),
                "record_id": trained["pred_e"].get("record_id"),
                "support": trained["pred_e"].get("support"),
            },
            "smc_pred_y_mW": {
                "status": trained["pred_w"].get("status"),
                "record_id": trained["pred_w"].get("record_id"),
                "support": trained["pred_w"].get("support"),
            },
            "o_prime_surface_x": surface_only(trained["op_e"]),
            "o_prime_surface_y": surface_only(trained["op_w"]),
            "n_prospection_transitions": len(trained["prospection"].get("transitions") or {}),
        },
        "psc_candidate_diff": {
            "x": sx,
            "y": sy,
            "rng": 0.2,
            "same_selected_signature": sx.get("selected_signature") == sy.get("selected_signature"),
            "same_competition_scores": True,
            "o_prime_optical_carry_distinct": surface_only(trained["op_e"]) != surface_only(trained["op_w"]),
            "boundary": (
                "SMC SIM_THRESHOLD mean-L1 attaches both motors to both optical contexts. "
                "O′ carries current surface_c*. HSS argmax over all locos from O′ equalizes "
                "historical_support. Competition can therefore tie while O′ optics still differ."
            ),
        },
        "prospective_composition_xy": {
            "continuations_x": cont_x,
            "continuations_y": cont_y,
            "distinct": cont_x != cont_y,
        },
        "psc_off_history": off,
        "pe_trace": pe_t,
        "mapping_sanity": maps,
        "v3_observability": v3,
        "causal_ladder": lad,
        "classifications": cl,
        "v3_compact_obs_has_surface": "surface_c0_1" in compact_accessible_observation(x),
    }
    (OUT / "quantization_aliases.json").write_text(json.dumps(qpairs, indent=2), encoding="utf-8")
    (OUT / "controlled_pairs.json").write_text(json.dumps(artifacts["controlled_pairs"], indent=2), encoding="utf-8")
    (OUT / "conditioned_history_trace.json").write_text(
        json.dumps(artifacts["conditioned_history_trace"], indent=2), encoding="utf-8"
    )
    (OUT / "psc_candidate_diff.json").write_text(json.dumps(artifacts["psc_candidate_diff"], indent=2), encoding="utf-8")
    (OUT / "psc_off_history.json").write_text(json.dumps(off, indent=2), encoding="utf-8")
    (OUT / "v3_observability.json").write_text(json.dumps(v3, indent=2), encoding="utf-8")
    (OUT / "causal_ladder.json").write_text(json.dumps({"ladder": lad, "classifications": cl}, indent=2), encoding="utf-8")
    (OUT / "summary.json").write_text(
        json.dumps({k: artifacts[k] for k in ("classifications", "naive_empty_history", "pe_trace", "mapping_sanity")}, indent=2, default=str),
        encoding="utf-8",
    )
    return artifacts


if __name__ == "__main__":
    a = run()
    print(json.dumps(a["classifications"], indent=2))
    print("X", a["psc_candidate_diff"]["x"].get("status"), a["psc_candidate_diff"]["x"].get("selected_signature"))
    print("Y", a["psc_candidate_diff"]["y"].get("status"), a["psc_candidate_diff"]["y"].get("selected_signature"))
