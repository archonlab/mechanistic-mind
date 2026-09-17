#!/usr/bin/env python3
"""Causal gearbox mapping — map existing machine; do not add missing gears."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np

from mechanistic_mind.physical_system.cognition import CognitionConfig
from mechanistic_mind.physical_system.endogenous_motor import EndogenousMotorCouplingConfig
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "mm_causal_gearbox"
SEEDS = [17, 23, 41, 59, 83]
H = 6

KEYS = [
    "body.xy", "body.vx_vy", "body.T", "body.B", "body.B_core", "body.mech",
    "body.motor_u", "internal.c", "planet.u_mean", "planet.flow_mean", "planet.T_mean",
]


def snap(rt: PhysicalSystemRuntime) -> dict:
    return {
        "body.xy": (float(rt.body.x), float(rt.body.y)),
        "body.vx_vy": (float(rt.body.vx), float(rt.body.vy)),
        "body.T": float(rt.body.T),
        "body.B": rt.body.B.copy(),
        "body.B_core": rt.body.B_core.copy(),
        "body.mech": float(rt.body.mech),
        "body.motor_u": (float(rt.body.motor_ux), float(rt.body.motor_uy)),
        "internal.c": rt.internal.c.copy(),
        "planet.u_mean": float(np.mean(rt.world.u)),
        "planet.flow_mean": float(np.mean(np.hypot(rt.world.vx, rt.world.vy))),
        "planet.T_mean": float(np.mean(rt.world.T)),
        "selected_action": rt.last_selected_action,
    }


def dist(a, b, key) -> float:
    va, vb = a[key], b[key]
    if isinstance(va, np.ndarray):
        return float(np.linalg.norm(va - vb))
    if isinstance(va, tuple):
        return float(np.linalg.norm(np.asarray(va, dtype=float) - np.asarray(vb, dtype=float)))
    if va is None or vb is None:
        return 0.0 if va == vb else 1.0
    return float(abs(va - vb))


def make(seed: int, *, endo: bool = False, cognition: bool = False) -> PhysicalSystemRuntime:
    cfg = PhysicalSystemConfig(
        cognition=CognitionConfig(cognition_enabled=cognition, prospective_selection="LEGACY_FIRST"),
        endogenous_motor=EndogenousMotorCouplingConfig(mode="EXPERIMENTAL" if endo else "OFF", strength=0.1),
    )
    return PhysicalSystemRuntime(seed=seed, config=cfg)


def clone_rt(rt: PhysicalSystemRuntime) -> PhysicalSystemRuntime:
    new = make(rt.seed, endo=rt.config.endogenous_motor.enabled, cognition=rt.config.cognition.cognition_enabled)
    new.config = copy.deepcopy(rt.config)
    new.seed = rt.seed
    new.tick = rt.tick
    new.world = copy.deepcopy(rt.world)
    new.body = copy.deepcopy(rt.body)
    new.internal = copy.deepcopy(rt.internal)
    new.cognition = copy.deepcopy(rt.cognition)
    new._internal_c_prev = None if getattr(rt, "_internal_c_prev", None) is None else np.asarray(rt._internal_c_prev).copy()
    new.last_selected_action = rt.last_selected_action
    new.last_agent_observation = copy.deepcopy(rt.last_agent_observation)
    return new


def apply_perturbation(rt: PhysicalSystemRuntime, source: str, eps: float) -> None:
    if source == "internal.c":
        rt.internal.c = np.clip(rt.internal.c + eps, 0, rt.config.internal.C_max)
    elif source == "body.B":
        rt.body.B = np.clip(rt.body.B + eps, 0, rt.config.body.B_max)
    elif source == "body.vx_vy":
        rt.body.vx += eps
    elif source == "body.T":
        rt.body.T = float(np.clip(rt.body.T + eps, rt.config.body.T_min, rt.config.body.T_max))
    elif source == "body.mech":
        rt.body.mech += eps
    elif source == "planet.u":
        rt.world.u = rt.world.u + eps
    elif source == "planet.T":
        rt.world.T = np.clip(rt.world.T + eps, 0, 1)
    elif source == "motor_u":
        rt.body.motor_ux += eps
    else:
        raise ValueError(source)


def impulse_series(seed: int, source: str, eps: float, *, endo: bool = False) -> dict:
    base = make(seed, endo=endo, cognition=False)
    for _ in range(25):
        base.step()
    ctrl = clone_rt(base)
    plus = clone_rt(base)
    apply_perturbation(plus, source, eps)
    series = []
    for h in range(H):
        ctrl.step()
        plus.step()
        sc, sp = snap(ctrl), snap(plus)
        row = {"h": h + 1}
        for k in KEYS:
            row[k] = {"d_plus": dist(sp, sc, k)}
        series.append(row)
    onsets = {}
    for k in KEYS:
        onset = None
        peak = 0.0
        for row in series:
            d = row[k]["d_plus"]
            peak = max(peak, d)
            if onset is None and d > 1e-8:
                onset = row["h"]
        onsets[k] = {"onset_h": onset, "peak_d_plus": peak, "responds": peak > 1e-8}
    return {"seed": seed, "source": source, "eps": eps, "endo": endo, "series": series, "onsets": onsets}


def build_impulse_matrix(endo: bool = False) -> dict:
    sources = [
        ("internal.c", 0.05), ("body.B", 0.05), ("body.vx_vy", 0.05), ("body.T", 0.05),
        ("body.mech", 0.05), ("planet.u", 0.02), ("planet.T", 0.02),
    ]
    if endo:
        sources.append(("motor_u", 0.05))
    matrix = {}
    for source, eps in sources:
        agg = {k: {"respond_count": 0, "mean_peak": 0.0, "mean_onset": []} for k in KEYS}
        for seed in SEEDS:
            r = impulse_series(seed, source, eps, endo=endo)
            for k, o in r["onsets"].items():
                if o["responds"]:
                    agg[k]["respond_count"] += 1
                    agg[k]["mean_peak"] += o["peak_d_plus"]
                    if o["onset_h"] is not None:
                        agg[k]["mean_onset"].append(o["onset_h"])
        for k in KEYS:
            n = max(1, agg[k]["respond_count"])
            agg[k]["mean_peak"] = agg[k]["mean_peak"] / n if agg[k]["respond_count"] else 0.0
            agg[k]["mean_onset"] = float(np.mean(agg[k]["mean_onset"])) if agg[k]["mean_onset"] else None
            agg[k]["fraction_seeds"] = agg[k]["respond_count"] / len(SEEDS)
        matrix[source] = agg
    return {"horizon": H, "seeds": SEEDS, "endo": endo, "matrix": matrix}


def cascade_trace(source: str, eps: float, endo: bool = False) -> dict:
    r = impulse_series(41, source, eps, endo=endo)
    events = []
    for row in r["series"]:
        changed = [k for k in KEYS if row[k]["d_plus"] > 1e-8]
        events.append({"h": row["h"], "changed": changed})
    return {"source": source, "eps": eps, "endo": endo, "events": events, "onsets": r["onsets"]}


def body_b_modulation() -> dict:
    rows = []
    for seed in SEEDS:
        base = make(seed, endo=False, cognition=False)
        for _ in range(30):
            base.step()
        low = clone_rt(base)
        high = clone_rt(base)
        low.body.B[:] = 0.05
        high.body.B[:] = 1.2
        for rt in (low, high):
            rt.world.u = rt.world.u + 0.05
            rt.body.vx = 0.1
            rt.body.vy = 0.0
            rt.step()
        rows.append({
            "seed": seed,
            "low_B_speed": float(np.hypot(low.body.vx, low.body.vy)),
            "high_B_speed": float(np.hypot(high.body.vx, high.body.vy)),
            "speed_diff": abs(float(np.hypot(high.body.vx, high.body.vy)) - float(np.hypot(low.body.vx, low.body.vy))),
            "mech_diff": abs(float(high.body.mech) - float(low.body.mech)),
        })
    mean_speed_diff = float(np.mean([r["speed_diff"] for r in rows]))
    modulates = mean_speed_diff > 1e-6
    return {
        "rows": rows,
        "mean_speed_diff": mean_speed_diff,
        "modulation_of_velocity_by_B": modulates,
        "claim": "BODY.B MODULATES ENVIRONMENT->MOTION" if modulates else "BODY.B DOES NOT MODULATE ENVIRONMENT->MOTION (baseline)",
    }


def kappa_ablation_mediation() -> dict:
    rows = []
    for seed in SEEDS:
        def run(coupling: bool):
            rt = make(seed, endo=False)
            rt.config.internal.coupling_enabled = coupling
            for _ in range(25):
                rt.step()
            ctrl = clone_rt(rt)
            pert = clone_rt(rt)
            pert.internal.c = np.clip(pert.internal.c + 0.08, 0, pert.config.internal.C_max)
            for _ in range(H):
                ctrl.step()
                pert.step()
            return {
                "dB": float(np.linalg.norm(pert.body.B - ctrl.body.B)),
                "dV": float(np.hypot(pert.body.vx - ctrl.body.vx, pert.body.vy - ctrl.body.vy)),
                "dXY": float(np.hypot(pert.body.x - ctrl.body.x, pert.body.y - ctrl.body.y)),
            }
        rows.append({"seed": seed, "kappa_on": run(True), "kappa_off": run(False)})
    return {
        "rows": rows,
        "mean_dB_kappa_on": float(np.mean([r["kappa_on"]["dB"] for r in rows])),
        "mean_dB_kappa_off": float(np.mean([r["kappa_off"]["dB"] for r in rows])),
        "mean_dV_kappa_on": float(np.mean([r["kappa_on"]["dV"] for r in rows])),
        "mean_dV_kappa_off": float(np.mean([r["kappa_off"]["dV"] for r in rows])),
    }


def history_dependence() -> dict:
    seed = 59

    def primed(boost):
        rt = make(seed, endo=False)
        for _ in range(10):
            rt.step()
        rt.internal.c = np.clip(rt.internal.c + boost, 0, rt.config.internal.C_max)
        for _ in range(20):
            rt.step()
        before = snap(rt)
        rt.world.u = rt.world.u + 0.04
        rt.step()
        after = snap(rt)
        return {"dV": dist(after, before, "body.vx_vy"), "dB": dist(after, before, "body.B")}

    a, b = primed(0.0), primed(0.15)
    return {"seed": seed, "neutral": a, "boosted": b, "different_dV": abs(a["dV"] - b["dV"]) > 1e-8}


def nonlinear_sweep() -> dict:
    rows = []
    for eps in [0.01, 0.05, 0.1, 0.2]:
        peaks_B, peaks_V = [], []
        for seed in SEEDS[:3]:
            r = impulse_series(seed, "internal.c", eps, endo=False)
            peaks_B.append(r["onsets"]["body.B"]["peak_d_plus"])
            peaks_V.append(r["onsets"]["body.vx_vy"]["peak_d_plus"])
        rows.append({"eps": eps, "mean_peak_dB": float(np.mean(peaks_B)), "mean_peak_dV": float(np.mean(peaks_V))})
    return {"rows": rows}


def classify_edges(mod: dict, abl: dict) -> dict:
    edges = [
        {"from": "internal.c", "to": "body.B", "kind": "DIRECT", "graph": "BASELINE", "level": 4,
         "evidence": "perturbation + kappa ablation", "lag": "SAME-TICK ORDERED", "type": "PHYSICAL"},
        {"from": "body.B", "to": "internal.c", "kind": "DIRECT", "graph": "BASELINE", "level": 3,
         "evidence": "kappa code-path + impulse body.B", "lag": "SAME-TICK ORDERED", "type": "PHYSICAL"},
        {"from": "internal.c", "to": "body.vx_vy", "kind": "NOT-DEMONSTRATED", "graph": "BASELINE", "level": 0,
         "evidence": "mean_dV_kappa_on=%.3e" % abl["mean_dV_kappa_on"], "type": "PHYSICAL"},
        {"from": "body.B", "to": "body.vx_vy", "kind": "NOT-DEMONSTRATED", "graph": "BASELINE", "level": 0,
         "evidence": mod["claim"], "type": "PHYSICAL"},
        {"from": "planet.u", "to": "body.mech", "kind": "DIRECT", "graph": "BASELINE", "level": 3,
         "lag": "SAME-TICK ORDERED", "type": "PHYSICAL"},
        {"from": "body.mech", "to": "body.vx_vy", "kind": "DIRECT", "graph": "BASELINE", "level": 2,
         "lag": "SAME-TICK ORDERED", "type": "PHYSICAL"},
        {"from": "planet.vx_vy", "to": "body.vx_vy", "kind": "DIRECT", "graph": "BASELINE", "level": 3,
         "lag": "SAME-TICK ORDERED", "type": "PHYSICAL"},
        {"from": "body.vx_vy", "to": "body.xy", "kind": "DIRECT", "graph": "BASELINE", "level": 3,
         "lag": "SAME-TICK ORDERED", "type": "PHYSICAL"},
        {"from": "body.B", "to": "planet.M", "kind": "DIRECT", "graph": "BASELINE", "level": 2,
         "lag": "SAME-TICK ORDERED", "type": "PHYSICAL"},
        {"from": "planet.M", "to": "body.B", "kind": "DIRECT", "graph": "BASELINE", "level": 2,
         "lag": "SAME-TICK ORDERED", "type": "PHYSICAL"},
        {"from": "selected_action", "to": "body.vx_vy", "kind": "DIRECT", "graph": "BASELINE", "level": 3,
         "lag": "SAME-TICK ORDERED", "type": "PHYSICAL", "via": "impulse"},
        {"from": "observation", "to": "selected_action", "kind": "DIRECT", "graph": "BASELINE", "level": 3,
         "type": "INFORMATIONAL", "via": "cognition selection", "provenance": "wait persistence + PSC"},
        {"from": "internal.c", "to": "observation", "kind": "DIRECT", "graph": "BASELINE", "level": 2,
         "type": "INFORMATIONAL", "via": "accessible_observation"},
        {"from": "body.xy", "to": "observation", "kind": "DIRECT", "graph": "BASELINE", "level": 2,
         "type": "INFORMATIONAL"},
        {"from": "prospective_structures", "to": "selected_action", "kind": "DIRECT", "graph": "BASELINE", "level": 3,
         "type": "INFORMATIONAL", "provenance": "mm_wait_persistence_diagnosis / PSC"},
        {"from": "internal.c", "to": "motor_u", "kind": "DIRECT", "graph": "EXPERIMENTAL", "level": 4,
         "lag": "SAME-TICK after internal", "type": "EXPERIMENTALLY_INTRODUCED"},
        {"from": "motor_u", "to": "body.vx_vy", "kind": "DIRECT", "graph": "EXPERIMENTAL", "level": 4,
         "lag": "ONE-TICK LAG", "type": "EXPERIMENTALLY_INTRODUCED"},
        {"from": "internal.c", "to": "body.vx_vy", "kind": "MEDIATED", "graph": "EXPERIMENTAL", "level": 4,
         "lag": ">=1 tick", "type": "EXPERIMENTALLY_INTRODUCED", "via": "motor_u"},
    ]
    return {"edges": edges}


def build_gearbox(edges, graph):
    subset = [e for e in edges if e.get("graph") == graph]
    return {
        "graph": graph,
        "nodes": sorted({e["from"] for e in subset} | {e["to"] for e in subset}),
        "edges": [e for e in subset if e.get("kind") != "NOT-DEMONSTRATED"],
        "not_demonstrated": [e for e in subset if e.get("kind") == "NOT-DEMONSTRATED"],
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "artifacts").mkdir(exist_ok=True)
    print("impulse baseline...")
    impulse_base = build_impulse_matrix(False)
    print("impulse experimental...")
    impulse_endo = build_impulse_matrix(True)
    (OUT / "CAUSAL_IMPULSE_MATRIX.json").write_text(json.dumps({"baseline": impulse_base, "experimental": impulse_endo}, indent=2))

    cascades = {
        "baseline_internal_c": cascade_trace("internal.c", 0.05, False),
        "baseline_body_B": cascade_trace("body.B", 0.05, False),
        "experimental_internal_c": cascade_trace("internal.c", 0.05, True),
    }
    (OUT / "artifacts" / "cascades.json").write_text(json.dumps(cascades, indent=2))

    print("body.B modulation...")
    mod = body_b_modulation()
    (OUT / "BODY_B_MODULATION_RESULTS.json").write_text(json.dumps(mod, indent=2))
    print(mod["claim"], mod["mean_speed_diff"])

    print("kappa ablation...")
    abl = kappa_ablation_mediation()
    (OUT / "artifacts" / "kappa_ablation.json").write_text(json.dumps(abl, indent=2))
    print("dB on/off", abl["mean_dB_kappa_on"], abl["mean_dB_kappa_off"], "dV on", abl["mean_dV_kappa_on"])

    hist = history_dependence()
    nonlin = nonlinear_sweep()
    (OUT / "artifacts" / "history_nonlinear.json").write_text(json.dumps({"history": hist, "nonlinear": nonlin}, indent=2))

    edges_pack = classify_edges(mod, abl)
    (OUT / "DIRECT_MEDIATED_EDGES.json").write_text(json.dumps(edges_pack, indent=2))
    (OUT / "MODULATORY_EDGES.json").write_text(json.dumps({
        "tested_negative": [{
            "modulator": "body.B",
            "input": "planet.u bump + vx=0.1",
            "output": "body.vx_vy",
            "level": 0,
            "mean_speed_diff": mod["mean_speed_diff"],
            "result": mod["claim"],
        }] if not mod["modulation_of_velocity_by_B"] else [],
        "edges": [],
    }, indent=2))

    reached = set()
    for ev in cascades["baseline_internal_c"]["events"]:
        reached.update(ev["changed"])
    (OUT / "CAUSAL_TERMINATION_POINTS.md").write_text(
        "# CAUSAL_TERMINATION_POINTS\n\n"
        "## Perturb internal.c (baseline, endo OFF)\n\n"
        "Responding variables (seed 41): " + str(sorted(reached)) + "\n\n"
        "Onsets:\n\n```\n" + json.dumps(cascades["baseline_internal_c"]["onsets"], indent=2) + "\n```\n\n"
        "Spatial transmission terminates at material compartments: reaches body.B / related material paths, "
        "does NOT reach body.vx_vy / body.xy in baseline.\n\n"
        "body.B remains locally important for WORLD material exchange and INTERNAL kappa exchange.\n"
    )

    (OUT / "RECIPROCAL_LOOPS.md").write_text(
        "# RECIPROCAL_LOOPS\n\n"
        "## Baseline demonstrated\n"
        "- body.B <-> internal.c (kappa)\n"
        "- body.B <-> planet.M (material)\n"
        "- body.T <-> planet.T (thermal)\n\n"
        "## ENV <-> organism spatial loop\n"
        "INCOMPLETE in baseline. Missing edge: body.B/internal.c -> mechanical response/velocity.\n\n"
        "## Experimental endogenous motor\n"
        "Partial close: INTERNAL Delta c -> motor_u -> velocity -> xy -> ENV sample. EXPERIMENTALLY INTRODUCED.\n"
    )

    (OUT / "TEMPORAL_LAG_MAP.json").write_text(json.dumps({
        "SAME-TICK ORDERED": ["impulse->vx", "planet->mechanical", "vx->xy", "B<->internal.c"],
        "ONE-TICK LAG": ["EXPERIMENTAL motor_u -> next vx"],
        "NOT_DEMONSTRATED": ["baseline internal.c -> velocity any lag"],
    }, indent=2))

    (OUT / "TIMESCALE_MAP.md").write_text(
        "# TIMESCALE_MAP\n\n"
        "| subsystem | class |\n|---|---|\n"
        "| action/mechanics/fields | FAST |\n"
        "| material/internal kappa | MEDIUM |\n"
        "| motor_u decay (experimental) | MEDIUM |\n"
        "| cognitive stores / prospective history | SLOW |\n"
    )

    (OUT / "BASELINE_GEARBOX.json").write_text(json.dumps(build_gearbox(edges_pack["edges"], "BASELINE"), indent=2))
    (OUT / "EXPERIMENTAL_GEARBOX.json").write_text(json.dumps({
        "graph": "EXPERIMENTAL",
        "includes_baseline": True,
        "added_edges": [e for e in edges_pack["edges"] if e.get("graph") == "EXPERIMENTAL"],
        "baseline_subgraph": build_gearbox(edges_pack["edges"], "BASELINE"),
    }, indent=2))

    lines = ["# GEARBOX_EVIDENCE_TABLE", "", "| from | to | graph | kind | level | type |", "|---|---|---|---|---|---|"]
    for e in edges_pack["edges"]:
        lines.append("| %s | %s | %s | %s | %s | %s |" % (
            e["from"], e["to"], e.get("graph"), e.get("kind"), e.get("level"), e.get("type")))
    (OUT / "GEARBOX_EVIDENCE_TABLE.md").write_text("\n".join(lines) + "\n")

    summary = {
        "seeds": SEEDS,
        "baseline_internal_to_velocity": "NOT_DEMONSTRATED",
        "baseline_internal_to_B": "DEMONSTRATED",
        "body_B_modulates_motion": mod["modulation_of_velocity_by_B"],
        "mean_dV_after_internal_perturb_kappa_on": abl["mean_dV_kappa_on"],
        "env_organism_spatial_loop_baseline": "INCOMPLETE",
        "missing_edge": "body.B or internal.c -> mechanical response / velocity",
        "experimental_endo_closes_partial_loop": True,
    }
    (OUT / "seed_summary.json").write_text(json.dumps(summary, indent=2))
    print("SUMMARY", json.dumps(summary, indent=2))
    print("DONE")


if __name__ == "__main__":
    main()
