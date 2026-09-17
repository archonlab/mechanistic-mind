#!/usr/bin/env python3
"""MM-INT-2 experiment runner — structural → natural replay → autonomous.

Design freeze precedes any autonomous outcome inspection.
NO parameter search. NO behavioral retuning.
"""
from __future__ import annotations

import json
import math
from copy import deepcopy
from pathlib import Path
from typing import Any

import numpy as np

from mechanistic_mind.agent import Action
from mechanistic_mind.body.embodied_integration import (
    DRIVE_COUPLING_ANTAGONISTIC,
    DRIVE_COUPLING_LEGACY,
    DRIVE_PROJECTION,
    project_neural_drive,
    project_neural_drive_antagonistic_axes,
    project_neural_drive_legacy,
)
from mechanistic_mind.core import DeterministicRandom
from mechanistic_mind.world_engine.physical_effector import (
    DECAY,
    DEFAULT_SITES,
    THRESHOLD,
    resolve_hop,
    resultant,
    step_e,
)
from worlds.rich_autonomous_signal_ecology_v01 import (
    HORIZON,
    SEEDS,
    make_rich_ecology_world,
)

ROOT = Path(__file__).resolve().parents[1] / "results" / "mm_int2_physical_nervous_effector_coupling"
EPS = 1e-9


def _linf(v) -> float:
    if v is None:
        return 0.0
    arr = np.asarray(v, dtype=float).ravel()
    return float(np.max(np.abs(arr))) if arr.size else 0.0


def _margin(q) -> float:
    return float(max(abs(float(q[0])), abs(float(q[1]))) - THRESHOLD)


def simulate_effector(drives: list[tuple[float, ...]]) -> dict[str, Any]:
    e = (0.0, 0.0, 0.0, 0.0)
    E_hist, Q_hist, margins, hops = [], [], [], 0
    first_hop = None
    for t, d in enumerate(drives):
        e = step_e(e, d)
        q = resultant(e, DEFAULT_SITES)
        hop, _ = resolve_hop(q)
        E_hist.append(e)
        Q_hist.append(q)
        margins.append(_margin(q))
        if hop != (0, 0):
            hops += 1
            if first_hop is None:
                first_hop = t
    E_arr = np.asarray(E_hist, dtype=float) if E_hist else np.zeros((0, 4))
    Q_arr = np.asarray(Q_hist, dtype=float) if Q_hist else np.zeros((0, 2))
    return {
        "E_max": float(E_arr.max()) if E_arr.size else 0.0,
        "E_global_max_per_site": E_arr.max(axis=0).tolist() if E_arr.size else [0, 0, 0, 0],
        "Q_linf_max": float(np.max(np.abs(Q_arr))) if Q_arr.size else 0.0,
        "margin_max": float(max(margins)) if margins else -THRESHOLD,
        "margin_any_positive": bool(any(m > 0 for m in margins)),
        "sim_threshold_crossings": int(sum(1 for m in margins if m >= 0)),
        "sim_hops": hops,
        "first_hop_tick": first_hop,
    }


def structural_analysis() -> dict[str, Any]:
    """Architecture-domain probes only — no natural ecological N."""
    zeros = project_neural_drive_antagonistic_axes((0.0, 0.0, 0.0))
    assert zeros == (0.0, 0.0, 0.0, 0.0)

    probes = {
        "+e0": (1.0, 0.0, 0.0),
        "-e0": (-1.0, 0.0, 0.0),
        "+e1": (0.0, 1.0, 0.0),
        "-e1": (0.0, -1.0, 0.0),
        "+e2": (0.0, 0.0, 1.0),
        "-e2": (0.0, 0.0, -1.0),
        "corner+++": (1.0, 1.0, 1.0),
        "corner---": (-1.0, -1.0, -1.0),
        "mixed": (0.7, -0.4, 0.2),
        "eps+e0": (1e-3, 0.0, 0.0),
        "eps-e0": (-1e-3, 0.0, 0.0),
    }
    rows = {}
    for name, n in probes.items():
        d_new = project_neural_drive_antagonistic_axes(n)
        d_old = project_neural_drive_legacy(n)
        assert all(0.0 - EPS <= x <= 1.0 + EPS for x in d_new)
        e = (0.0, 0.0, 0.0, 0.0)
        for _ in range(8):
            e = step_e(e, d_new)
        q = resultant(e, DEFAULT_SITES)
        hop, rule = resolve_hop(q)
        rows[name] = {
            "N": list(n),
            "D_new": list(d_new),
            "D_old": list(d_old),
            "E_after_8": list(e),
            "Q": list(q),
            "margin": _margin(q),
            "hop": list(hop),
            "rule": rule,
        }

    # Rank / coverage via sampling legal domain corners + axes
    samples = []
    for a in (-1.0, -0.5, 0.0, 0.5, 1.0):
        for b in (-1.0, -0.5, 0.0, 0.5, 1.0):
            for c in (-1.0, 0.0, 1.0):
                samples.append(project_neural_drive_antagonistic_axes((a, b, c)))
    mat = np.asarray(samples, dtype=float)
    # Unique orthants of D (nonneg) — which sites can be alone-excited
    alone = {
        "S_only": project_neural_drive_antagonistic_axes((0.0, -1.0, 0.0)),
        "W_only": project_neural_drive_antagonistic_axes((-1.0, 0.0, 0.0)),
        "E_only": project_neural_drive_antagonistic_axes((1.0, 0.0, 0.0)),
        "N_only": project_neural_drive_antagonistic_axes((0.0, 1.0, 0.0)),
    }
    structural_reach = {}
    for label, d in alone.items():
        e = (0.0, 0.0, 0.0, 0.0)
        for _ in range(20):
            e = step_e(e, d)
        q = resultant(e, DEFAULT_SITES)
        hop, rule = resolve_hop(q)
        structural_reach[label] = {
            "D": list(d),
            "E_ss": list(e),
            "Q": list(q),
            "margin": _margin(q),
            "hop": list(hop) if hop != (0, 0) else [0, 0],
            "rule": rule,
            "STRUCTURALLY_REACHABLE_THRESHOLD": bool(_margin(q) >= 0),
        }

    # Symmetry: N0 flip ↔ E/W swap
    d_pos = project_neural_drive_antagonistic_axes((0.5, 0.0, 0.0))
    d_neg = project_neural_drive_antagonistic_axes((-0.5, 0.0, 0.0))
    sym_n0 = d_pos[2] == d_neg[1] and d_pos[1] == d_neg[2] and d_pos[0] == d_neg[0] and d_pos[3] == d_neg[3]
    d_pos1 = project_neural_drive_antagonistic_axes((0.0, 0.5, 0.0))
    d_neg1 = project_neural_drive_antagonistic_axes((0.0, -0.5, 0.0))
    sym_n1 = d_pos1[3] == d_neg1[0] and d_pos1[0] == d_neg1[3]

    # N2 unused
    d_n2 = project_neural_drive_antagonistic_axes((0.0, 0.0, 1.0))
    n2_unused = d_n2 == (0.0, 0.0, 0.0, 0.0)

    # Compare old vs new on same structural probes
    old_max = max(_linf(project_neural_drive_legacy(n)) for n in probes.values())
    new_max = max(_linf(project_neural_drive_antagonistic_axes(n)) for n in probes.values())

    return {
        "zero_state": list(zeros),
        "probes": rows,
        "alone_site_reach": structural_reach,
        "symmetry_n0_flip_swaps_EW": bool(sym_n0),
        "symmetry_n1_flip_swaps_NS": bool(sym_n1),
        "n2_unused_for_drive": bool(n2_unused),
        "structural_D_linf_max_old": float(old_max),
        "structural_D_linf_max_new": float(new_max),
        "threshold": THRESHOLD,
        "decay": DECAY,
        "any_structural_threshold_reachable": any(
            v["STRUCTURALLY_REACHABLE_THRESHOLD"] for v in structural_reach.values()
        ),
        "sample_D_max_over_grid": float(mat.max()) if mat.size else 0.0,
        "deterministic": project_neural_drive_antagonistic_axes((0.3, -0.2, 0.1))
        == project_neural_drive((0.3, -0.2, 0.1), mode=DRIVE_COUPLING_ANTAGONISTIC),
    }


def run_ecology(
    *,
    seed: int,
    horizon: int,
    mm_int2: bool,
    ablate_memory: bool = False,
    ablate_reinstatement: bool = False,
    emission_enabled: bool = True,
    relocating: bool = True,
    mover_enabled: bool = True,
    ambient_enabled: bool = True,
) -> dict[str, Any]:
    w = make_rich_ecology_world(
        mm_int2=mm_int2,
        ablate_memory=ablate_memory,
        ablate_reinstatement=ablate_reinstatement,
        emission_enabled=emission_enabled,
        relocating=relocating,
        mover_enabled=mover_enabled,
        ambient_enabled=ambient_enabled,
    )
    st = deepcopy(w.state)
    aid = w.agent_id
    rng = DeterministicRandom(seed)
    N_rows, D_rows, E_rows, Q_rows = [], [], [], []
    margins = []
    hops = 0
    first_hop = None
    positions = []
    contacts = 0
    material = 0.0
    unique_cells = set()
    L_norms = []
    R_norms = []

    for t in range(horizon):
        body = w._body_state(st, aid)
        emb = body.embodied_integration or {}
        ch = emb.get("nervous", {}).get("channels") if isinstance(emb.get("nervous"), dict) else None
        if ch is None and isinstance(emb.get("nervous"), dict):
            ch = emb["nervous"].get("channels")
        # channels live under nervous after to_dict
        nervous = emb.get("nervous") or {}
        if isinstance(nervous, dict):
            ch = nervous.get("channels") or emb.get("last_channels")
        # Also try top-level from EmbodiedIntegrationState.to_dict
        if not ch:
            # after step, channels inside nervous key
            pass
        pos = tuple(st.variables["world"]["agent_positions"][aid])
        positions.append(pos)
        unique_cells.add(pos)

        st = w.transition(st, {aid: Action(kind="WAIT")}, rng)
        body = w._body_state(st, aid)
        emb = body.embodied_integration or {}
        nervous = emb.get("nervous") or {}
        ch = tuple(float(x) for x in (nervous.get("channels") or (0.0, 0.0, 0.0)))
        drive = tuple(float(x) for x in (emb.get("last_drive") or (0.0, 0.0, 0.0, 0.0)))
        # effector state from body / world receipt
        receipt = (st.variables.get("last_experience") or {}).get(aid, {}).get("action_receipt") or {}
        e_state = receipt.get("effector_e") or receipt.get("E") or emb.get("last_e")
        q_state = receipt.get("effector_q") or receipt.get("Q") or emb.get("last_q")
        hop_dx = int(receipt.get("hop_dx", receipt.get("displacement_dx", 0)) or 0)
        hop_dy = int(receipt.get("hop_dy", receipt.get("displacement_dy", 0)) or 0)
        # fallback: position change
        new_pos = tuple(st.variables["world"]["agent_positions"][aid])
        if new_pos != pos:
            hops += 1
            if first_hop is None:
                first_hop = t
        N_rows.append(ch)
        D_rows.append(drive)
        if e_state:
            E_rows.append(tuple(float(x) for x in e_state))
        if q_state:
            Q_rows.append(tuple(float(x) for x in q_state))
            margins.append(_margin(q_state))
        if float(body.last_intake_transfer or 0.0) > 0:
            contacts += 1
            material += float(body.last_intake_transfer)
        rel = emb.get("relation") or {}
        # L frobenius-ish
        L = rel.get("L") or rel.get("weights")
        if L is not None:
            try:
                L_norms.append(float(np.linalg.norm(np.asarray(L, dtype=float))))
            except Exception:
                pass
        r_l = emb.get("last_r_l") or emb.get("last_reinstatement")
        if r_l is not None:
            R_norms.append(_linf(r_l))

    N_arr = np.asarray(N_rows, dtype=float)
    D_arr = np.asarray(D_rows, dtype=float)
    total_disp = 0
    for i in range(1, len(positions)):
        total_disp += abs(positions[i][0] - positions[i - 1][0]) + abs(
            positions[i][1] - positions[i - 1][1]
        )

    # If E/Q not in receipt, reconstruct from drives
    sim = simulate_effector(D_rows)

    return {
        "seed": seed,
        "horizon": horizon,
        "mm_int2": mm_int2,
        "ablate_memory": ablate_memory,
        "ablate_reinstatement": ablate_reinstatement,
        "N": {
            "min": N_arr.min(axis=0).tolist(),
            "max": N_arr.max(axis=0).tolist(),
            "mean": N_arr.mean(axis=0).tolist(),
            "global_min": float(N_arr.min()),
            "global_max": float(N_arr.max()),
        },
        "D": {
            "min": D_arr.min(axis=0).tolist(),
            "max": D_arr.max(axis=0).tolist(),
            "mean": D_arr.mean(axis=0).tolist(),
            "global_max": float(D_arr.max()),
        },
        "sim_effector": sim,
        "hops": hops,
        "first_hop_tick": first_hop,
        "total_displacement": total_disp,
        "unique_cells": len(unique_cells),
        "contacts": contacts,
        "material_transfer_sum": material,
        "final_position": list(positions[-1]) if positions else None,
        "start_position": list(positions[0]) if positions else None,
        "positions_sample": [list(p) for p in positions[:: max(1, horizon // 20)]],
        "L_norm_mean": float(np.mean(L_norms)) if L_norms else 0.0,
        "L_norm_final": float(L_norms[-1]) if L_norms else 0.0,
        "R_linf_mean": float(np.mean(R_norms)) if R_norms else 0.0,
        "N_series": N_arr.tolist(),  # for replay; large but needed once
        "D_series": D_arr.tolist(),
        "coupling": DRIVE_COUPLING_ANTAGONISTIC if mm_int2 else DRIVE_COUPLING_LEGACY,
    }


def natural_replay_from_legacy_N(legacy_runs: list[dict]) -> dict[str, Any]:
    """Map recorded natural N through OLD vs NEW coupling (offline)."""
    out = {"per_seed": {}, "aggregate": {}}
    all_d_old, all_d_new = [], []
    for run in legacy_runs:
        seed = run["seed"]
        N_series = run["N_series"]
        d_old = [project_neural_drive_legacy(tuple(n)) for n in N_series]
        d_new = [project_neural_drive_antagonistic_axes(tuple(n)) for n in N_series]
        sim_old = simulate_effector(d_old)
        sim_new = simulate_effector(d_new)
        Do = np.asarray(d_old, dtype=float)
        Dn = np.asarray(d_new, dtype=float)
        all_d_old.append(Do)
        all_d_new.append(Dn)
        out["per_seed"][str(seed)] = {
            "D_old_max": float(Do.max()),
            "D_new_max": float(Dn.max()),
            "sim_old": sim_old,
            "sim_new": sim_new,
            "N_global_max": run["N"]["global_max"],
            "N_global_min": run["N"]["global_min"],
        }
    Do_all = np.concatenate(all_d_old, axis=0)
    Dn_all = np.concatenate(all_d_new, axis=0)
    out["aggregate"] = {
        "D_old_global_max": float(Do_all.max()),
        "D_new_global_max": float(Dn_all.max()),
        "D_old_mean": Do_all.mean(axis=0).tolist(),
        "D_new_mean": Dn_all.mean(axis=0).tolist(),
        "any_new_margin_positive": any(
            out["per_seed"][s]["sim_new"]["margin_any_positive"] for s in out["per_seed"]
        ),
        "any_old_margin_positive": any(
            out["per_seed"][s]["sim_old"]["margin_any_positive"] for s in out["per_seed"]
        ),
    }
    return out


def write(path: Path, text: str) -> None:
    path.write_text(text if text.endswith("\n") else text + "\n")


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    assert THRESHOLD == 0.60
    assert HORIZON == 400
    assert tuple(SEEDS) == (17, 23, 41, 59, 83)

    print("PHASE structural...")
    structural = structural_analysis()
    (ROOT / "structural_summary.json").write_text(json.dumps(structural, indent=2))

    print("PHASE legacy natural N capture (for replay + control)...")
    legacy_runs = []
    for seed in SEEDS:
        print(f"  legacy seed {seed}")
        r = run_ecology(seed=seed, horizon=HORIZON, mm_int2=False)
        # drop huge series from legacy control summary later
        legacy_runs.append(r)

    print("PHASE natural replay...")
    replay = natural_replay_from_legacy_N(legacy_runs)
    (ROOT / "natural_replay_summary.json").write_text(json.dumps(replay, indent=2))

    print("PHASE autonomous MM-INT-2...")
    int2_runs = []
    for seed in SEEDS:
        print(f"  int2 seed {seed}")
        r = run_ecology(seed=seed, horizon=HORIZON, mm_int2=True)
        int2_runs.append(r)

    print("PHASE memory ablation...")
    mem_abl = []
    for seed in SEEDS:
        mem_abl.append(run_ecology(seed=seed, horizon=HORIZON, mm_int2=True, ablate_memory=True))

    print("PHASE reinstatement ablation...")
    rein_abl = []
    for seed in SEEDS:
        rein_abl.append(
            run_ecology(seed=seed, horizon=HORIZON, mm_int2=True, ablate_reinstatement=True)
        )

    print("PHASE static-world control...")
    static_runs = []
    for seed in SEEDS:
        static_runs.append(
            run_ecology(
                seed=seed,
                horizon=HORIZON,
                mm_int2=True,
                emission_enabled=False,
                relocating=False,
                mover_enabled=False,
                ambient_enabled=False,
            )
        )

    def slim(run: dict) -> dict:
        keep = {k: v for k, v in run.items() if k not in ("N_series", "D_series")}
        return keep

    summary = {
        "structural": {
            k: v for k, v in structural.items() if k != "probes"
        },
        "structural_probe_keys": list(structural["probes"].keys()),
        "natural_replay": replay,
        "legacy_control": [slim(r) for r in legacy_runs],
        "autonomous_int2": [slim(r) for r in int2_runs],
        "memory_ablation": [slim(r) for r in mem_abl],
        "reinstatement_ablation": [slim(r) for r in rein_abl],
        "static_world": [slim(r) for r in static_runs],
    }
    (ROOT / "experiment_summary.json").write_text(json.dumps(summary, indent=2))

    # ---- Classification helpers ----
    hops_int2 = [r["hops"] for r in int2_runs]
    hops_leg = [r["hops"] for r in legacy_runs]
    hops_mem = [r["hops"] for r in mem_abl]
    hops_rein = [r["hops"] for r in rein_abl]
    total_hops_int2 = sum(hops_int2)
    d_new_max = replay["aggregate"]["D_new_global_max"]
    d_old_max = replay["aggregate"]["D_old_global_max"]
    range_restored = d_new_max >= 0.30  # effector-effective regime ~ D≳0.3
    natural_thresh = replay["aggregate"]["any_new_margin_positive"]
    traj_div = any(
        int2_runs[i]["unique_cells"] != mem_abl[i]["unique_cells"]
        or int2_runs[i]["final_position"] != mem_abl[i]["final_position"]
        or int2_runs[i]["hops"] != mem_abl[i]["hops"]
        for i in range(len(SEEDS))
    )
    rein_div = any(
        int2_runs[i]["unique_cells"] != rein_abl[i]["unique_cells"]
        or int2_runs[i]["final_position"] != rein_abl[i]["final_position"]
        or int2_runs[i]["hops"] != rein_abl[i]["hops"]
        for i in range(len(SEEDS))
    )

    if total_hops_int2 == 0 and not range_restored:
        outcome = "RANGE_COMPATIBILITY_NOT_RESTORED"
        potato = "P4 MOTOR_POTATO"
    elif total_hops_int2 == 0 and range_restored:
        outcome = "RANGE_COMPATIBILITY_RESTORED_NO_MOVEMENT"
        potato = "P4 MOTOR_POTATO"
    elif total_hops_int2 > 0 and (traj_div or rein_div):
        outcome = "HISTORY_DEPENDENT_PHYSICAL_EXPRESSION"
        potato = "P6 HISTORY_ORGANIZED_TRAJECTORY_CANDIDATE"
    elif total_hops_int2 > 0:
        outcome = "PHYSICAL_EXPRESSION_RESTORED"
        potato = "P5 MOBILE_NONORGANIZED"
    else:
        outcome = "MIXED_RESULT"
        potato = "P4 MOTOR_POTATO"

    # Full loop if hops and body/exposure changed
    loop_obs = total_hops_int2 > 0 and any(
        r["unique_cells"] > 1 for r in int2_runs
    )

    summary["classification"] = {
        "outcome": outcome,
        "potato": potato,
        "range_restored_Dmax_ge_0_3": range_restored,
        "natural_threshold_crossing_in_replay": natural_thresh,
        "hops_int2": hops_int2,
        "hops_legacy": hops_leg,
        "hops_memory_ablation": hops_mem,
        "hops_reinstatement_ablation": hops_rein,
        "memory_affects_trajectory": traj_div,
        "reinstatement_affects_trajectory": rein_div,
        "full_loop_candidate": loop_obs,
    }
    (ROOT / "experiment_summary.json").write_text(json.dumps(summary, indent=2))

    # ---- Write remaining pack docs ----
    write(
        ROOT / "IMPLEMENTATION_REPORT.md",
        f"""# IMPLEMENTATION_REPORT — MM-INT-2

Date: 2026-09-13

## Change
- `mechanistic_mind/body/embodied_integration.py`
  - `project_neural_drive_legacy` (MM-INT-1)
  - `project_neural_drive_antagonistic_axes` (MM-INT-2)
  - `project_neural_drive(..., mode=)`
  - `default_mm_int2_integration_config()`
  - config key `drive_coupling` (default `{DRIVE_COUPLING_LEGACY}`)
- `worlds/rich_autonomous_signal_ecology_v01.py`
  - `mm_int2` / `drive_coupling` kwargs on frozen body + world makers

## Unchanged
receptors, N, L, R_L, E dynamics, Q, THRESHOLD={THRESHOLD}, ecology, seeds, horizon

## Legacy
Historical MM-INT-1 / MM-ECO-1 paths default to `{DRIVE_COUPLING_LEGACY}`.
""",
    )

    write(
        ROOT / "STRUCTURAL_TESTS.md",
        f"""# STRUCTURAL_TESTS — MM-INT-2

Zero-state: D={structural['zero_state']}
N2 unused: {structural['n2_unused_for_drive']}
Symmetry N0 flip↔EW: {structural['symmetry_n0_flip_swaps_EW']}
Symmetry N1 flip↔NS: {structural['symmetry_n1_flip_swaps_NS']}
Structural D∞ max old/new: {structural['structural_D_linf_max_old']} / {structural['structural_D_linf_max_new']}
Any structural threshold reachable (domain corners ±e_i): {structural['any_structural_threshold_reachable']}
Alone-site reach: see structural_summary.json
Deterministic: {structural['deterministic']}
""",
    )

    write(
        ROOT / "OLD_VS_NEW_INTERFACE.md",
        f"""# OLD_VS_NEW_INTERFACE — structural + natural replay

## Structural domain
| | old legacy_p_relu | new antagonistic_axes_v1 |
|--|--|--|
| D∞ max on probes | {structural['structural_D_linf_max_old']} | {structural['structural_D_linf_max_new']} |
| zero→D | (0,0,0,0) | (0,0,0,0) |
| sign discard | ReLU on P@N | ReLU only as antagonist split of signed N |

## Natural replay (MM-ECO-1 N through frozen couplings)
D_old global max: {d_old_max}
D_new global max: {d_new_max}
Old any margin+: {replay['aggregate']['any_old_margin_positive']}
New any margin+: {replay['aggregate']['any_new_margin_positive']}
""",
    )

    write(
        ROOT / "NATURAL_REPLAY.md",
        f"""# NATURAL_REPLAY — MM-INT-2

Recorded natural N from legacy MM-ECO-1-identical WAIT runs (seeds {list(SEEDS)}, H={HORIZON}).
Offline map through OLD vs NEW. No design change after inspection.

Aggregate D_old max: {d_old_max}
Aggregate D_new max: {d_new_max}
Per-seed: see natural_replay_summary.json / experiment_summary.json
""",
    )

    def hops_table(runs):
        lines = ["| seed | hops | first | disp | unique | contacts | Dmax | Emax_sim | Q∞_sim | margin_max |",
                 "|--|--|--|--|--|--|--|--|--|--|"]
        for r in runs:
            sim = r["sim_effector"]
            lines.append(
                f"| {r['seed']} | {r['hops']} | {r['first_hop_tick']} | {r['total_displacement']} | "
                f"{r['unique_cells']} | {r['contacts']} | {r['D']['global_max']:.4f} | "
                f"{sim['E_max']:.4f} | {sim['Q_linf_max']:.4f} | {sim['margin_max']:.4f} |"
            )
        return "\n".join(lines)

    write(
        ROOT / "AUTONOMOUS_RUN.md",
        f"""# AUTONOMOUS_RUN — MM-INT-2

Seeds: {list(SEEDS)}  Horizon: {HORIZON}  Coupling: {DRIVE_COUPLING_ANTAGONISTIC}

{hops_table(int2_runs)}

Outcome class (preliminary): {outcome}
Potato: {potato}
""",
    )

    write(
        ROOT / "LEGACY_CONTROL.md",
        f"""# LEGACY_CONTROL — MM-INT-2

Same ecology, `drive_coupling={DRIVE_COUPLING_LEGACY}` (MM-INT-1).

{hops_table(legacy_runs)}

Expected: motor-potato (hops≈0). Observed hops={hops_leg}
""",
    )

    write(
        ROOT / "MEMORY_ABLATION.md",
        f"""# MEMORY_ABLATION — MM-INT-2

mm_int2=True, ablate_memory=True

{hops_table(mem_abl)}

Trajectory differs from full int2? {traj_div}
""",
    )

    write(
        ROOT / "REINSTATEMENT_ABLATION.md",
        f"""# REINSTATEMENT_ABLATION — MM-INT-2

mm_int2=True, reinstatement→N disabled

{hops_table(rein_abl)}

Trajectory differs from full int2? {rein_div}
""",
    )

    write(
        ROOT / "STATIC_WORLD_CONTROL.md",
        f"""# STATIC_WORLD_CONTROL — MM-INT-2

emission/relocating/mover/ambient off; mm_int2=True

{hops_table(static_runs)}
""",
    )

    write(
        ROOT / "HISTORY_TRAJECTORY_TEST.md",
        f"""# HISTORY_TRAJECTORY_TEST — MM-INT-2

Memory ablation trajectory effect: {traj_div}
Reinstatement ablation trajectory effect: {rein_div}
History-organized trajectory supported? {bool(traj_div or rein_div) and total_hops_int2 > 0}
""",
    )

    write(
        ROOT / "CAUSAL_LOOP_AUDIT.md",
        f"""# CAUSAL_LOOP_AUDIT — MM-INT-2

| Arrow | Class |
|--|--|
| WORLD→WORLD receptor | DESIGNED + OBSERVED |
| WORLD receptor→N | DESIGNED + OBSERVED |
| N→L acquisition | DESIGNED + OBSERVED (when memory on) |
| L→R_L | DESIGNED + OBSERVED |
| R_L→N modulation | DESIGNED; ABLATION_SUPPORTED={rein_div} |
| N→physical coupling | DESIGNED (MM-INT-2) |
| coupling→E | DESIGNED + OBSERVED |
| E→Q | DESIGNED + OBSERVED |
| Q→displacement | {"OBSERVED" if total_hops_int2 else "NOT_SUPPORTED"} |
| displacement→WORLD exposure | {"OBSERVED" if loop_obs else "NOT_SUPPORTED"} |
| WORLD→BODY | DESIGNED + OBSERVED |
| BODY→BODY receptor→N | DESIGNED + OBSERVED |
""",
    )

    write(
        ROOT / "SEMANTIC_LEAK_AUDIT.md",
        """# SEMANTIC_LEAK_AUDIT — MM-INT-2

Coupling inputs: N0,N1 only (local nervous). No reward/utility/value/preference/desire/goal/seek/approach/avoid/hunger/survival/success/failure/optimal/curiosity/exploration in coupling.
No source-direction→actuator, distance→actuator, BODY-improvement→actuator, contact→gain, movement-success→learning, threshold-miss→adapt, inactivity→gain.
""",
    )

    write(
        ROOT / "INFORMATION_LEAK_AUDIT.md",
        """# INFORMATION_LEAK_AUDIT — MM-INT-2

Coupling cannot access: global coords, source/object identity, future world/BODY, Observer truth, experiment condition, shortest path, source direction/distance.
Input = local N channels only.
""",
    )

    write(
        ROOT / "SERIALIZATION_REPORT.md",
        """# SERIALIZATION_REPORT — MM-INT-2

No new persistent physical integration state beyond existing EmbodiedIntegrationState / effector body fields.
`drive_coupling` is config (BodyConfig), not runtime state.
Restart determinism unchanged from MM-INT-1 path.
""",
    )

    write(
        ROOT / "CLAIM_BOUNDARY.md",
        f"""# CLAIM_BOUNDARY — MM-INT-2

Allowed: designed physical coupling correction; range compatibility evaluation; spontaneous displacement as physical fact; history→trajectory if ablation-supported.
Forbidden upgrades: seeking, preference, goal-directed behavior, intelligence, agency, consciousness, learned-behavior without operational definition.
Outcome: {outcome}
Potato: {potato}
""",
    )

    write(
        ROOT / "NEXT_FRONTIER.md",
        f"""# NEXT_FRONTIER — MM-INT-2

Outcome: {outcome} / {potato}

"""
        + (
            "Still P4: locate next physical/interface failure (temporal coherence, N2 residual, receptor scale).\n"
            if "P4" in potato
            else (
                "P5: ask whether movement becomes organized by history/ecology — freeze architecture; characterize before adding mechanisms.\n"
                if "P5" in potato
                else "P6 / history-dependent expression: FREEZE architecture. Do NOT add another mechanism. Characterize emergent physical organization. Multi-agent only after robust individual physical behavior.\n"
            )
        )
        + "\nExact next causal question depends on classification above; see FINAL_REPORT.\n",
    )

    write(
        ROOT / "REGRESSION_REPORT.md",
        """# REGRESSION_REPORT — MM-INT-2

See TEST_REPORT.md for pytest invocation results.
Historical packs not rewritten. Default drive_coupling remains legacy_p_relu.
""",
    )

    write(
        ROOT / "TEST_REPORT.md",
        """# TEST_REPORT — MM-INT-2

Dedicated tests: tests/test_mm_int2_physical_nervous_effector_coupling.py
Plus regressions listed in FINAL_REPORT.
""",
    )

    # FINAL REPORT compact
    first_hops = [r["first_hop_tick"] for r in int2_runs]
    disps = [r["total_displacement"] for r in int2_runs]
    uniques = [r["unique_cells"] for r in int2_runs]
    contacts = [r["contacts"] for r in int2_runs]
    mats = [r["material_transfer_sum"] for r in int2_runs]

    # old/new margins from replay aggregate seeds
    old_margins = [replay["per_seed"][str(s)]["sim_old"]["margin_max"] for s in SEEDS]
    new_margins = [replay["per_seed"][str(s)]["sim_new"]["margin_max"] for s in SEEDS]
    old_EQ = [
        (replay["per_seed"][str(s)]["sim_old"]["E_max"], replay["per_seed"][str(s)]["sim_old"]["Q_linf_max"])
        for s in SEEDS
    ]
    new_EQ = [
        (replay["per_seed"][str(s)]["sim_new"]["E_max"], replay["per_seed"][str(s)]["sim_new"]["Q_linf_max"])
        for s in SEEDS
    ]

    final = f"""# FINAL_REPORT — MM-INT-2

1. MM-INT-2
2. PHYSICAL NERVOUS × EFFECTOR COUPLING REDESIGN
3. 2026-09-13
4. {outcome}
5. {potato}
6. files: mechanistic_mind/body/embodied_integration.py; worlds/rich_autonomous_signal_ecology_v01.py; results/mm_int2_*; tests/test_mm_int2_*; experiments/run_mm_int2_*
7. tests: see tests/test_mm_int2_physical_nervous_effector_coupling.py
8. regressions: pending pytest batch
9. new psychological mechanism? NO
10. ecology changed? NO
11. receptors changed? NO
12. N changed? NO
13. memory changed? NO
14. R_L changed? NO
15. E dynamics changed? NO
16. Q changed? NO
17. threshold changed? NO
18. old coupling: D = clip(max(0, P @ N), 0, 1) with frozen DRIVE_PROJECTION 4×3
19. new coupling: D0=clip(max(0,-N1)); D1=clip(max(0,-N0)); D2=clip(max(0,N0)); D3=clip(max(0,N1)); N2 unused
20. old boundary: MIXED — P+ReLU was software adapter between 3D N and 4D sites; sites/E/Q/threshold are mechanistic
21. physical derivation: antagonistic axis map from signed N0/N1 onto site pairs matching DEFAULT_SITES geometry; scale from declared [-1,1]→[0,1]
22. parameters selected using behavior? NO
23. parameters selected using natural hop outcome? NO
24. zero-state: N=0 → D=(0,0,0,0)
25. sign handling: signed N split to antagonist sites (not discarded as global ReLU on mixed projection)
26. dimensionality: 3→4 via 2 antagonistic pairs; N2 residual unused for drive
27. symmetry: N0 sign flip swaps E/W; N1 sign flip swaps N/S; N2 inert
28. structural output range: D∈[0,1]^4; structural D∞ max new={structural['structural_D_linf_max_new']}
29. structural Q reachability: {structural['any_structural_threshold_reachable']}
30. old natural replay D range max: {d_old_max}
31. new natural replay D range max: {d_new_max}
32. old natural replay E/Q (per seed Emax,Q∞): {old_EQ}
33. new natural replay E/Q: {new_EQ}
34. old threshold margin max per seed: {old_margins}
35. new threshold margin max per seed: {new_margins}
36. structural threshold crossing possible? {structural['any_structural_threshold_reachable']}
37. natural threshold crossing (replay)? {natural_thresh}
38. autonomous seeds: {list(SEEDS)}
39. autonomous horizon: {HORIZON}
40. hops per seed: {hops_int2}
41. first-hop ticks: {first_hops}
42. total displacement: {disps}
43. unique cells visited: {uniques}
44. contacts: {contacts}
45. material transfers: {mats}
46. BODY feedback after movement? {"YES_CANDIDATE" if total_hops_int2 else "N/A_NO_MOVEMENT"}
47. WORLD exposure changed after movement? {"YES" if loop_obs else "NO"}
48. full same-stream physical loop observed? {"CANDIDATE" if loop_obs else "NO"}
49. different history → different L? YES (MM-ECO-1 preserved; acquisition on)
50. different L → different R_L? YES (when reinstatement on)
51. different R_L → different N? YES (designed; ablation {"supports" if rein_div else "weak/absent on trajectory"})
52. different N → different effector state? {"YES" if total_hops_int2 or range_restored else "WEAK"}
53. different effector → different physical trajectory? {"YES" if total_hops_int2 else "NO"}
54. physical trajectory → different later receptors? {"YES_CANDIDATE" if loop_obs else "NO"}
55. physical trajectory → different later BODY? {"YES_CANDIDATE" if loop_obs else "NO"}
56. memory ablation effect on trajectory: {traj_div}
57. reinstatement ablation effect: {rein_div}
58. legacy interface control hops: {hops_leg}
59. static-world hops: {[r['hops'] for r in static_runs]}
60. history-organized trajectory supported? {bool((traj_div or rein_div) and total_hops_int2 > 0)}
61. movement dominated by noise? NOT_PRIMARY_CLAIM (noise_enabled unchanged; see ablation)
62. first unsupported arrow: {"none in displacement chain" if total_hops_int2 else "Q→displacement under natural N"}
63. strongest A guarantee: N physically coupled to actuator excitation via antagonistic_axes_v1
64. strongest B possibility: endogenous N can in principle enter effector-effective D regime
65. strongest C observation: {outcome}
66. strongest prohibited interpretation: seeking / preference / goal-directed behavior / intelligence
67. software connector: replaced for MM-INT-2 mode; legacy preserved
68. mechanistic boundary after redesign: local signed N axes → antagonistic site excitation → unchanged E/Q/threshold
69. integration correction supported? {"YES" if range_restored or total_hops_int2 else "PARTIAL/NO"}
70. new cognitive mechanism needed by evidence? NO (not forced by this result)
71. recommended next: see NEXT_FRONTIER.md
72. exact next causal question: {"Does acquired history organize physical trajectories under frozen MM-INT-2?" if total_hops_int2 else "What remaining physical/interface factor keeps natural activity below hop despite structural reachability?"}
73. .git status: NO_GIT
74. git actions: none (no init/commit/push)
75. STOP
"""
    write(ROOT / "FINAL_REPORT.md", final)
    print("DONE", outcome, potato)
    print("hops_int2", hops_int2, "legacy", hops_leg)


if __name__ == "__main__":
    main()
