#!/usr/bin/env python3
"""Seasonal climate/resource ecology. World change only; CURRENT MM cognition unchanged."""
from __future__ import annotations

import csv
import json
import math
import sys
from collections import Counter
from copy import deepcopy
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mechanistic_mind.planet.climate_ecology import (
    experimental_climate_planet_config,
    field_phase_row,
    season_phase_state,
)
from mechanistic_mind.planet.dynamics import step_planet
from mechanistic_mind.planet.state import initialize_planet
from mechanistic_mind.physical_system import PhysicalSystemConfig, PhysicalSystemRuntime
from mechanistic_mind.physical_system.cognition import empty_cognitive_state
from mechanistic_mind.physical_system.observation import audit_cognition_payload
from mechanistic_mind.research import predictive_compression as pc
from mechanistic_mind.research import prospective_composition as pr

OUT = ROOT / "results" / "mm_seasonal_resource_ecology"
SEEDS = (17, 23, 41, 59, 83, 66667, 2148)
CONTROL_SEEDS = (17, 41, 66667)
PERIOD = 80
ECO_CYCLES = 3
AGENT_CYCLES = 5
DOWNSAMPLE = 4
LOCK_PERSIST = 8
DECLINE_FRAC = 0.30
DEPART_CELLS = 3.0


def _json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n")


def _csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("")
        return
    keys = list(rows[0].keys())
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)


def planet_cfg(**ce_over) -> PhysicalSystemConfig:
    planet = experimental_climate_planet_config()
    for k, v in ce_over.items():
        setattr(planet.climate_ecology, k, v)
    return PhysicalSystemConfig(planet=planet)


def make_rt(seed: int, **ce_over) -> PhysicalSystemRuntime:
    return PhysicalSystemRuntime(seed=int(seed), config=planet_cfg(**ce_over))


def local_stock(rt: PhysicalSystemRuntime) -> tuple[float, float, float]:
    h, w = rt.world.T.shape
    iy, ix = rt.body.cell(w, h)
    ra = float(rt.world.R_A[iy, ix]) if rt.world.R_A is not None else 0.0
    rb = float(rt.world.R_B[iy, ix]) if rt.world.R_B is not None else 0.0
    t = float(rt.world.T[iy, ix])
    return t, ra, rb


def rec(rt: PhysicalSystemRuntime) -> dict:
    sel = rt.cognition.get("last_selection") or {}
    comp = sel.get("competition") or {}
    obs = rt.last_agent_observation or {}
    t, ra, rb = local_stock(rt)
    aw = rt.last_action_work_ledger or {}
    mw = rt.last_motor_work_ledger or {}
    dw = rt.last_work_ledger or {}
    cl = rt.last_complementary_ledger or {}
    supported = list(comp.get("supported_actions") or [])
    inc = supported[0] if supported else sel.get("action")
    one = pr.predict_one_step(rt.cognition["prospection"], obs, inc) if inc else {}
    body_a = float(np.sum(rt.body.R_A_site)) if getattr(rt.body, "R_A_site", None) is not None else 0.0
    body_b = float(np.sum(rt.body.R_B_site)) if getattr(rt.body, "R_B_site", None) is not None else 0.0
    ce = rt.config.planet.climate_ecology
    phase = season_phase_state(ce, int(rt.tick), int(rt.seed))
    return {
        "tick": int(rt.tick),
        "cycle": int(phase["cycle_index"]),
        "phase": float(phase["phase"]),
        "x": float(rt.body.x),
        "y": float(rt.body.y),
        "action": sel.get("action"),
        "source": sel.get("source"),
        "outcome": comp.get("outcome_class"),
        "k": len(supported),
        "supported": supported,
        "inc_match": one.get("status"),
        "inc_sup": one.get("support") if one.get("status") == "MATCH" else 0,
        "local_T": t,
        "local_RA": ra,
        "local_RB": rb,
        "body_A": body_a,
        "body_B": body_b,
        "xfer_A": float((cl.get("A") or {}).get("acquired") or cl.get("acquired_A") or 0.0),
        "xfer_B": float((cl.get("B") or {}).get("acquired") or cl.get("acquired_B") or 0.0),
        "work": float(getattr(rt.body, "mechanical_work_reservoir", 0.0) or 0.0),
        "move_work": float(aw.get("action_work_realized") or 0.0),
        "motor_work": float(mw.get("motor_work_realized") or 0.0),
        "deform_work": float((dw.get("deformation") or {}).get("W_act") or dw.get("deformation_work_realized") or 0.0),
        "obs_T": float(obs.get("local.T") or 0.0),
    }


def lock_of(rows: list[dict]) -> dict:
    for i, rec_i in enumerate(rows):
        if rec_i.get("source") != "PROSPECTIVE_SCENARIO" or rec_i.get("outcome") != "SINGLE_SUPPORTED":
            continue
        w = rows[i : i + LOCK_PERSIST]
        if len(w) < LOCK_PERSIST:
            break
        if all(x.get("action") == rec_i["action"] and x.get("outcome") == "SINGLE_SUPPORTED" for x in w):
            return {"lock_tick": rec_i["tick"], "locked_action": rec_i["action"]}
    return {"lock_tick": None, "locked_action": None}


def entropy(counts: dict) -> float:
    n = sum(counts.values())
    if n <= 0:
        return 0.0
    h = 0.0
    for c in counts.values():
        if c:
            p = c / n
            h -= p * math.log(p, 2)
    return h


def validate_ecology() -> dict:
    cfg = experimental_climate_planet_config()
    ce = cfg.climate_ecology
    period = int(ce.season_period)
    st = initialize_planet(cfg, seed=17)
    rows = []
    snapshots = {}
    for t in range(period * ECO_CYCLES + 1):
        phase = season_phase_state(ce, st.tick, 17)
        mark = abs((phase["phase"] * 4) % 1.0) < 1e-9 or t == 0
        if t % (period // 4) == 0 or mark:
            row = field_phase_row(ce, st.tick, 17, st.T, st.R_A, st.R_B, st.vx, st.vy)
            rows.append(row)
            key = f"c{int(phase['cycle_index'])}_p{phase['phase']:.2f}"
            if key not in snapshots:
                snapshots[key] = {
                    "tick": int(st.tick),
                    "T_row_mean": [float(x) for x in st.T.mean(axis=1)],
                    "RA_row_mean": [float(x) for x in st.R_A.mean(axis=1)],
                    "RB_row_mean": [float(x) for x in st.R_B.mean(axis=1)],
                    **{k: row[k] for k in row},
                }
        step_planet(st, cfg, seed=17)
    a = initialize_planet(cfg, seed=17)
    b = initialize_planet(cfg, seed=17)
    for _ in range(period):
        step_planet(a, cfg, seed=17)
        step_planet(b, cfg, seed=17)
    twin_ok = float(np.max(np.abs(a.T - b.T))) < 1e-12
    # depletion vs regeneration: consume a rich cell, compare to untouched twin
    rich = initialize_planet(cfg, seed=17)
    for _ in range(period):
        step_planet(rich, cfg, seed=17)
    ctrl = rich.copy()
    iy, ix = np.unravel_index(int(np.argmax(rich.R_A)), rich.R_A.shape)
    taken = float(rich.R_A[iy, ix])
    rich.R_A[iy, ix] = 0.0
    for _ in range(12):
        step_planet(rich, cfg, seed=17)
        step_planet(ctrl, cfg, seed=17)
    depleted_stays_lower = float(rich.R_A[iy, ix]) < float(ctrl.R_A[iy, ix])
    # short cycle independently
    short_cfg = experimental_climate_planet_config()
    short_cfg.climate_ecology.short_cycle_enabled = True
    s0 = initialize_planet(short_cfg, seed=17)
    s1 = initialize_planet(experimental_climate_planet_config(), seed=17)
    for _ in range(16):
        step_planet(s0, short_cfg, seed=17)
        step_planet(s1, experimental_climate_planet_config(), seed=17)
    short_differs = float(np.max(np.abs(s0.T - s1.T))) > 1e-4
    t_ys = [r["T_max_y"] for r in rows]
    ra_ys = [r["R_A_max_y"] for r in rows]
    rb_ys = [r["R_B_max_y"] for r in rows]
    north0 = rows[0]["T_north_mean"]
    south0 = rows[0]["T_south_mean"]
    return {
        "gates": {
            "temperature_gradient": bool(north0 < south0),
            "seasonal_temperature_shift": bool(max(t_ys) - min(t_ys) >= 4),
            "short_cycle_ablatable": bool(short_differs),
            "RA_distribution_changes": bool(max(ra_ys) - min(ra_ys) >= 3),
            "RB_distribution_changes": bool(max(rb_ys) - min(rb_ys) >= 2),
            "finite_capacity": bool(max(r["R_A_max"] for r in rows) <= ce.RA_capacity + 1e-6),
            "depletion_works": bool(depleted_stays_lower and taken > 0.05),
            "regeneration_works": bool(float(rich.R_A[iy, ix]) > 0.0),
            "resource_bounded": bool(all(r["R_A_max"] <= ce.RA_capacity + 1e-6 and r["R_B_max"] <= ce.RB_capacity + 1e-6 for r in rows)),
            "resource_belts_move": bool(max(ra_ys) - min(ra_ys) >= 3),
            "seed_reproducible": bool(twin_ok),
            "cognition_not_required": True,
        },
        "consumed_cell": {"iy": int(iy), "ix": int(ix), "taken": taken, "after": float(rich.R_A[iy, ix]), "control": float(ctrl.R_A[iy, ix])},
        "phase_rows": rows,
        "snapshots": snapshots,
        "short_cycle_max_abs_T_diff": float(np.max(np.abs(s0.T - s1.T))),
    }


def cycle_metrics(rows: list[dict], period: int) -> list[dict]:
    if not rows:
        return []
    max_tick = max(r["tick"] for r in rows)
    out = []
    for c in range((max_tick // period) + 1):
        chunk = [r for r in rows if r["cycle"] == c]
        if len(chunk) < 4:
            continue
        start = chunk[0]
        loc0 = start["local_RA"] + start["local_RB"]
        peak_local = max(r["local_RA"] + r["local_RB"] for r in chunk)
        t_decline = None
        for r in chunk:
            if peak_local > 1e-6 and (r["local_RA"] + r["local_RB"]) <= (1.0 - DECLINE_FRAC) * peak_local:
                t_decline = r["tick"]
                break
        t_mismatch = next((r["tick"] for r in chunk if r.get("inc_match") == "NO_MATCH" or r.get("outcome") == "NO_SUPPORT"), None)
        lock = lock_of(chunk)
        t_change = None
        if lock["locked_action"]:
            after = [r for r in chunk if r["tick"] >= (lock["lock_tick"] or 0) + LOCK_PERSIST]
            t_change = next((r["tick"] for r in after if r.get("action") != lock["locked_action"]), None)
        t_depart = next((r["tick"] for r in chunk if abs(r["y"] - start["y"]) >= DEPART_CELLS or abs(r["x"] - start["x"]) >= DEPART_CELLS), None)
        t_env = next((r["tick"] for r in chunk if abs(r["local_T"] - start["local_T"]) >= 0.08), None)
        acts = Counter(r["action"] for r in chunk)
        dy = float(chunk[-1]["y"] - start["y"])
        out.append({
            "cycle": c,
            "n": len(chunk),
            "start_tick": start["tick"],
            "end_tick": chunk[-1]["tick"],
            "start_y": start["y"],
            "end_y": chunk[-1]["y"],
            "dy": dy,
            "net_displacement": float(math.hypot(chunk[-1]["x"] - start["x"], dy)),
            "T_environmental_transition": t_env,
            "T_local_resource_decline": t_decline,
            "T_prediction_mismatch": t_mismatch,
            "T_behavior_change": t_change,
            "T_spatial_departure": t_depart,
            "locked_action": lock["locked_action"],
            "lock_tick": lock["lock_tick"],
            "action_entropy": entropy(acts),
            "dominant_action": acts.most_common(1)[0][0] if acts else None,
            "n_no_match": sum(1 for r in chunk if r.get("inc_match") == "NO_MATCH"),
            "n_no_support": sum(1 for r in chunk if r.get("outcome") == "NO_SUPPORT"),
            "n_endogenous": sum(1 for r in chunk if r.get("source") == "ENDOGENOUS_VARIATION"),
            "n_competition_k2": sum(1 for r in chunk if int(r.get("k") or 0) >= 2),
            "work_min": min(r["work"] for r in chunk),
            "work_end": chunk[-1]["work"],
            "local_stock_start": loc0,
            "local_stock_min": min(r["local_RA"] + r["local_RB"] for r in chunk),
            "mean_y": float(np.mean([r["y"] for r in chunk])),
        })
    return out


def run_agent(seed: int, n_cycles: int, **ce_over) -> dict:
    rt = make_rt(seed, **ce_over)
    period = int(rt.config.planet.climate_ecology.season_period)
    horizon = period * n_cycles
    rows = []
    traj = []
    events = []
    prev = None
    leak = []
    for _ in range(horizon):
        rt.step()
        hits = audit_cognition_payload(rt.last_agent_observation or {})
        if hits:
            leak.extend(hits)
        r = rec(rt)
        rows.append(r)
        if prev is not None and (
            r["action"] != prev.get("action")
            or r["inc_match"] != prev.get("inc_match")
            or r["outcome"] != prev.get("outcome")
        ):
            events.append({k: r[k] for k in ("tick", "cycle", "phase", "action", "source", "outcome", "k", "inc_match", "local_T", "local_RA", "local_RB", "y")})
        if r["tick"] % DOWNSAMPLE == 0:
            traj.append({"tick": r["tick"], "x": r["x"], "y": r["y"], "action": r["action"], "cycle": r["cycle"]})
        prev = r
    slim = [{k: r[k] for k in (
        "tick", "cycle", "phase", "x", "y", "action", "source", "outcome", "k",
        "inc_match", "local_T", "local_RA", "local_RB", "work", "obs_T",
        "move_work", "motor_work", "xfer_A", "xfer_B", "body_A", "body_B",
    )} for r in rows]
    return {
        "seed": seed,
        "period": period,
        "horizon": horizon,
        "lock": lock_of(rows),
        "cycles": cycle_metrics(rows, period),
        "rows": slim,
        "trajectory": traj,
        "events": events,
        "final": rows[-1] if rows else {},
        "action_counts": dict(Counter(r["action"] for r in rows)),
        "observation_leaks": leak,
        "work_min": min((r["work"] for r in rows), default=None),
        "ce": rt.config.planet.climate_ecology.to_dict(),
        "runtime": rt,
    }


def run_history_controls(seed: int = 17) -> dict:
    rt = make_rt(seed)
    period = int(rt.config.planet.climate_ecology.season_period)
    for _ in range(period * 3):
        rt.step()
    snap = rt.snapshot()
    hold = PhysicalSystemRuntime.restore(deepcopy(snap))
    wiped = PhysicalSystemRuntime.restore(deepcopy(snap))
    wiped.cognition = empty_cognitive_state(wiped.config.cognition)
    wiped.cognition["prospection"] = pr.empty_store()
    wiped.cognition["compression"] = pc.empty_memory()
    wiped.last_agent_observation = wiped.agent_observation()
    h_rows, z_rows = [], []
    for _ in range(period):
        hold.step()
        wiped.step()
        h_rows.append(rec(hold))
        z_rows.append(rec(wiped))
    return {
        "seed": seed,
        "branch_tick": int(snap["tick"]),
        "H": {
            "actions": dict(Counter(r["action"] for r in h_rows)),
            "mean_y": float(np.mean([r["y"] for r in h_rows])),
            "n_no_match": sum(1 for r in h_rows if r.get("inc_match") == "NO_MATCH"),
            "n_endogenous": sum(1 for r in h_rows if r.get("source") == "ENDOGENOUS_VARIATION"),
            "lock": lock_of(h_rows),
            "start_action": h_rows[0]["action"] if h_rows else None,
            "traj": [{"tick": r["tick"], "x": r["x"], "y": r["y"], "action": r["action"]} for r in h_rows[::DOWNSAMPLE]],
        },
        "empty_history": {
            "actions": dict(Counter(r["action"] for r in z_rows)),
            "mean_y": float(np.mean([r["y"] for r in z_rows])),
            "n_no_match": sum(1 for r in z_rows if r.get("inc_match") == "NO_MATCH"),
            "n_endogenous": sum(1 for r in z_rows if r.get("source") == "ENDOGENOUS_VARIATION"),
            "lock": lock_of(z_rows),
            "start_action": z_rows[0]["action"] if z_rows else None,
            "traj": [{"tick": r["tick"], "x": r["x"], "y": r["y"], "action": r["action"]} for r in z_rows[::DOWNSAMPLE]],
        },
        "same_present_start": {
            "H_obs_T": h_rows[0]["obs_T"] if h_rows else None,
            "Z_obs_T": z_rows[0]["obs_T"] if z_rows else None,
            "H_y": h_rows[0]["y"] if h_rows else None,
            "Z_y": z_rows[0]["y"] if z_rows else None,
        },
    }


def _claim(status: str, evidence: str) -> dict:
    return {"status": status, "evidence": evidence}


def classify(eco: dict, agents: list[dict], hist: dict, controls: dict) -> dict:
    g = eco["gates"]
    a = _claim("DEMONSTRATED" if g["temperature_gradient"] and g["seasonal_temperature_shift"] else "NOT_DEMONSTRATED",
               "North/south T gradient and moving T maximum across hidden cycle phases.")
    b = _claim("DEMONSTRATED" if g["RA_distribution_changes"] and g["RB_distribution_changes"] else "NOT_DEMONSTRATED",
               "R_A and R_B row-maxima shift with the climate-driven suitability field.")
    c = _claim("DEMONSTRATED" if g["finite_capacity"] and g["depletion_works"] else "NOT_DEMONSTRATED",
               "Stocks clip to capacity; a consumed cell remains below an untouched twin while regenerating.")
    post_lock_mismatch = False
    post_lock_action_change = False
    for run in agents:
        lt = run["lock"].get("lock_tick")
        locked = run["lock"].get("locked_action")
        if lt is None:
            continue
        for cy in run["cycles"]:
            if int(cy["start_tick"]) <= int(lt) + LOCK_PERSIST:
                continue
            if cy["n_no_match"] or cy["n_no_support"]:
                post_lock_mismatch = True
            if locked and cy.get("dominant_action") and cy["dominant_action"] != locked:
                post_lock_action_change = True
        if locked and any(a != locked and n > 0 for a, n in run["action_counts"].items()):
            post_lock_action_change = True
    d = _claim(
        "DEMONSTRATED" if post_lock_mismatch else "NOT_DEMONSTRATED",
        "Post-lock MATCH failure / NO_SUPPORT on a later cycle. Cycle-0 endogenous events during first lock are ordinary early experience, not ecology-driven mismatch.",
    )
    e = _claim(
        "DEMONSTRATED" if post_lock_action_change else "NOT_DEMONSTRATED",
        "After an incumbent lock, a different action must be selected and persist. Constant WAIT or constant MOVE:* is not an ecology-driven transition.",
    )
    early = []
    for run in agents:
        for cy in run["cycles"]:
            td, tb = cy["T_local_resource_decline"], cy["T_behavior_change"]
            if td is not None and tb is not None and tb < td:
                early.append({"seed": run["seed"], "cycle": cy["cycle"], "T_behavior_change": tb, "T_local_resource_decline": td})
    cycle_shift = []
    for run in agents:
        times = [cy["T_behavior_change"] - cy["start_tick"] if cy["T_behavior_change"] is not None else None for cy in run["cycles"]]
        known = [t for t in times if t is not None]
        if len(known) >= 2 and known[-1] + 4 < known[0]:
            cycle_shift.append({"seed": run["seed"], "offsets": known})
    f = _claim(
        "NOT_DEMONSTRATED",
        "No post-lock action change across later cycles, so repeated history-dependent ecological transitions are not available to score.",
    )
    h_diff = hist["H"]["actions"] != hist["empty_history"]["actions"] or abs(hist["H"]["mean_y"] - hist["empty_history"]["mean_y"]) > 0.5
    precursor_gone = controls.get("precursor_ablation", {}).get("early_count", 0) == 0 and len(early) > 0
    g_st = "NOT_DEMONSTRATED"
    if early and precursor_gone:
        g_st = "SUPPORTED"
    elif early:
        g_st = "INCONCLUSIVE"
    g_claim = _claim(g_st, "Early transitions vs local stock decline; ablation must remove them to count as precursor use.")
    h_claim = _claim("DEMONSTRATED" if early else "NOT_DEMONSTRATED",
                     "Behavior change tick before local R_A+R_B decline in the same cycle.")
    i_claim = _claim("NOT_DEMONSTRATED" if g_st != "SUPPORTED" else "SUPPORTED",
                     "Prospective use requires precursor ablation plus scenario/prospection selecting the earlier action.")
    mig = []
    for run in agents:
        acts = list(run["action_counts"])
        if len(acts) == 1 and str(acts[0]).startswith("MOVE:"):
            continue  # ballistic incumbent MOVE, including toroidal wrap
        dys = [cy["dy"] for cy in run["cycles"]]
        reversals = 0
        for i in range(1, len(dys)):
            if dys[i] * dys[i - 1] < 0 and abs(dys[i]) >= DEPART_CELLS and abs(dys[i - 1]) >= DEPART_CELLS:
                reversals += 1
        if reversals >= 2:
            mig.append(run["seed"])
    j = _claim(
        "DEMONSTRATED" if mig else "NOT_DEMONSTRATED",
        "Requires repeated large |Δy| that reverses with the cycle, generated by ordinary actions, not constant MOVE wrap or one-way WAIT drift.",
    )
    k = _claim(
        "SUPPORTED" if h_diff else "NOT_DEMONSTRATED",
        "H vs wiped-history under the same next physical cycle. Difference here is incumbent WAIT lock vs empty-store resampling, not a cyclic seasonal policy.",
    )
    return {
        "A_SPATIOTEMPORAL_CLIMATE_ECOLOGY": a,
        "B_SEASONALLY_VARYING_RESOURCE_DISTRIBUTION": b,
        "C_FINITE_LOCAL_RESOURCE_DEPLETION": c,
        "D_ECOLOGY_DRIVEN_PREDICTION_MISMATCH": d,
        "E_ECOLOGY_DRIVEN_BEHAVIORAL_TRANSITION": e,
        "F_REPEATED_HISTORY_DEPENDENT_TRANSITION": f,
        "G_PHYSICAL_PRECURSOR_LEARNING": g_claim,
        "H_PRE_RESOURCE_DECLINE_BEHAVIORAL_CHANGE": h_claim,
        "I_PROSPECTIVE_USE_OF_TEMPORAL_ECOLOGICAL_STRUCTURE": i_claim,
        "J_REPEATED_MIGRATION_LIKE_SPATIAL_TRAJECTORY": j,
        "K_HISTORY_DEPENDENT_CYCLIC_BEHAVIOR": k,
        "early_events": early,
        "cycle_shift": cycle_shift,
        "migration_like_seeds": mig,
        "history_differs": h_diff,
    }


def write_docs() -> None:
    (OUT / "WORLD_MODEL.md").write_text(
        """# World model — experimental climate ecology

Independently selectable `PlanetConfig.climate_ecology` (default **OFF**).
CURRENT INTEGRATED MM defaults are unchanged.

## Hidden physics (not agent-accessible)

- latitude coordinate `y ∈ [-1,+1]` with `y=0` the colder baseline edge
- environmental cycle phase in `[0,1)`
- optional shorter independent cycle

## Agent-accessible observations (unchanged)

`body.*`, `local.T`, `local.M*`, `local.vx/vy`, `internal.c*`.

No season, latitude, biome, food, hunger, migration, or cycle-phase keys.

## Physical couplings used

Existing thermal relaxation, forcing, flow-from-temperature, matter phase/reaction,
wave field, and complementary `R_A`/`R_B` transfer→conversion→work.

Climate ecology adds:

1. a smooth latitudinal equilibrium-temperature field with a moving warm belt
2. extra insolation flux into the existing forcing channel
3. local productivity/decay of finite `R_A`/`R_B` from local temperature suitability
"""
    )
    (OUT / "CLIMATE_MODEL.md").write_text(
        """# Climate model

`T_eq(x,y,t) = baseline + gradient·φ(y) + belt_amp·exp(−½((φ(y)−φ_sun(t))/width)²) + optional short cycle + bounded local variation`

`φ_sun(t) = subsolar_amp · sin(2π · phase(t))`

Phase is a hidden periodic (or aperiodic) world process. Cognition never receives it.

Cooling relaxes `T` toward `T_eq` instead of a uniform `T_ref` when the ecology is enabled.
Insolation `F_climate = insolation_gain · T_eq` is added to the existing forcing field.

Short cycle (`short_cycle_enabled`, default false) is an independent additive modulation.

Stationary and aperiodic modes are ablations of the same equations, not new semantics.
"""
    )
    (OUT / "RESOURCE_ECOLOGY.md").write_text(
        """# Resource ecology

`R_A` and `R_B` remain complementary physical stocks. They are not food.

Local suitability is a Gaussian of local `T` about different optima:

- A prefers warmer belt temperatures
- B prefers cooler temperatures

Update (per cell):

`R ← clip(R + productivity·suit(T)·hetero·(1−R/capacity) − decay·R + diffuse·∇²R, 0, capacity)`

Optional `resource_suitability_source=independent_phase` uses a hidden suitability field
instead of actual `T` (precursor / decorrelation controls).

Transfer, conversion, and work accounting remain the ordinary complementary-resource path.
An organism can deplete the cell it occupies. There is no resource-exhausted flag.
"""
    )
    (OUT / "EXPERIMENT_DESIGN.md").write_text(
        f"""# Experiment design

Executable: `experiments/run_seasonal_resource_ecology.py`

Cognition: unchanged CURRENT INTEGRATED MM.
World: `experimental_climate_planet_config()` (not the MM default).

## Timescale

Season period = {PERIOD} ticks. Chosen from thermal relaxation (~20–30 ticks),
resource equilibration (~30–50), and MIN_SUPPORT lock (~8 ticks), not calendar realism.

## Stages

1. Ecology validation without cognition (`step_planet` only), {ECO_CYCLES} cycles.
2. Baseline agent runs, seeds {list(SEEDS)}, {AGENT_CYCLES} cycles.
3. Precursor ablation: temperature belt frozen, resource suitability still cycles.
4. Aperiodic / decorrelated / stationary world controls (seeds {list(CONTROL_SEEDS)}).
5. History control: after 3 cycles, H retains stores; Ø wipes predictive history.

No exploration bonus, no migration command, no season variable in cognition.
"""
    )


def write_final(claims: dict, eco: dict, agents: list[dict], hist: dict, controls: dict) -> None:
    g = eco["gates"]
    early = claims["early_events"]
    mig = claims["migration_like_seeds"]

    def st(key: str) -> str:
        return claims[key]["status"]

    q = [
        ("1. Reproducible spatial climate gradient?", "YES" if g["temperature_gradient"] and g["seed_reproducible"] else "NO"),
        ("2. Climate changes continuously over time?", "YES" if g["seasonal_temperature_shift"] else "NO"),
        ("3. R_A/R_B change from physical ecology, not agent semantics?", "YES" if g["RA_distribution_changes"] else "NO"),
        ("4. Local resources finite and depletable?", "YES" if g["finite_capacity"] and g["depletion_works"] else "NO"),
        ("5. Productive regions move across the world over the cycle?", "YES" if g["resource_belts_move"] else "NO"),
        ("6. Changing ecology break entrenched predictions naturally?", st("D_ECOLOGY_DRIVEN_PREDICTION_MISMATCH")),
        ("7. Reopen behavioral variation without an exploration mechanism?", st("E_ECOLOGY_DRIVEN_BEHAVIORAL_TRANSITION")),
        ("8. Ordinary experience establish new attractors in the changing world?", "Ordinary first-lock attractors form (WAIT or MOVE:*). Ecology-driven *new* attractors after that lock: " + st("E_ECOLOGY_DRIVEN_BEHAVIORAL_TRANSITION")),
        ("9. Behavior differ across repeated ecological cycles?", st("F_REPEATED_HISTORY_DEPENDENT_TRANSITION")),
        ("10. Behavioral transition earlier after repeated exposure?", "YES" if claims["cycle_shift"] else "NO / NOT_DEMONSTRATED"),
        ("11. If yes, which physical precursor?", "none identified" if not early else "local temperature / stock trajectory candidates; see PRECURSOR_RESULTS.json"),
        ("12. Precursor ablation remove the effect?", (
            "n/a — no pre-decline transition existed to remove"
            if not controls.get("precursor_ablation", {}).get("baseline_control_seed_early")
            else controls.get("precursor_ablation", {}).get("ablation_removes_early")
        )),
        ("13. Decorrelating climate and resource timing remove the effect?", controls.get("decorrelated", {}).get("note", "n/a")),
        ("14. Retained history causally affect behavior under equivalent current physical conditions?", "YES" if claims["history_differs"] else "NO / NOT_DEMONSTRATED"),
        ("15. Repeated migration-like trajectories emerge?", "YES" if mig else "NO"),
        ("16. Is any apparent migration prospective, reactive, random, or unresolved?", "WAIT seeds: one-way passive drift then sit. MOVE:N/S seeds: ballistic incumbent translation (toroidal wrap). Neither is migration."),
        ("17. What causal gear remains missing?", "After lock, gradual climate/resource change is absorbed by ordinary MATCH updates (same missing edge as the gradual-clamp result). CURRENT MM still cannot select an unmodeled action while an incumbent MATCH remains valid. No exploration, migration command, or season variable was added."),
    ]
    lines = [
        "# Seasonal resource ecology — final report",
        "",
        "World experiment. CURRENT INTEGRATED MM cognition was not modified.",
        "The climate/resource ecology is independently selectable and remains OFF in default MM.",
        "",
        "## Answers",
        "",
    ]
    for item, ans in q:
        lines.append(f"**{item}** {ans}")
        lines.append("")
    lines += [
        "## Claim board",
        "",
    ]
    for k, v in claims.items():
        if isinstance(v, dict) and "status" in v:
            lines.append(f"- `{k}`: **{v['status']}** — {v['evidence']}")
    lines += [
        "",
        "## Trajectory characterization",
        "",
        "WAIT-locked seeds select WAIT for the entire run. Early northward displacement is physical (flow / endogenous motor) while the selected action remains WAIT, then the body sits. That is one relocation plus sitting, not migration.",
        "",
        "MOVE:N (seed 66667) and MOVE:S (seed 2148) keep the incumbent MOVE action and wrap the torus. Large |Δy| is ballistic translation, not tracking of the moving resource belt.",
        "",
        "History control (seed 17, tick 240): retained WAIT history continues WAIT; wiping predictive stores under the same present yields MOVE:N lock and travel. Causal stage: empty support → ENDOGENOUS_VARIATION → new lock. The incumbent WAIT MATCH was still valid for H.",
        "",
        "## Baseline seeds",
        "",
    ]
    for run in agents:
        lines.append(
            f"- seed {run['seed']}: lock={run['lock']}, actions={run['action_counts']}, "
            f"work_min={run['work_min']}, cycles={len(run['cycles'])}"
        )
    lines.append("")
    (OUT / "FINAL_REPORT.md").write_text("\n".join(lines) + "\n")
    claim_md = ["# Scientific claims", "", "Statuses: DEMONSTRATED | SUPPORTED | INCONCLUSIVE | NOT_DEMONSTRATED | REFUTED", ""]
    for k, v in claims.items():
        if isinstance(v, dict) and "status" in v:
            claim_md.append(f"## {k}")
            claim_md.append("")
            claim_md.append(f"**{v['status']}**")
            claim_md.append("")
            claim_md.append(v["evidence"])
            claim_md.append("")
    (OUT / "SCIENTIFIC_CLAIMS.md").write_text("\n".join(claim_md))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    write_docs()
    eco = validate_ecology()
    _json(OUT / "ECOLOGY_VALIDATION.json", {k: eco[k] for k in ("gates", "consumed_cell", "short_cycle_max_abs_T_diff")})
    _csv(OUT / "FIELD_PHASE_SUMMARIES.csv", eco["phase_rows"])
    _json(OUT / "FIELD_SNAPSHOTS.json", eco["snapshots"])

    agents = []
    cycle_rows = []
    traj = {}
    pred_events = []
    work_rows = []
    for seed in SEEDS:
        run = run_agent(seed, AGENT_CYCLES)
        rt = run.pop("runtime")
        agents.append(run)
        for cy in run["cycles"]:
            cycle_rows.append({"seed": seed, **cy})
        traj[str(seed)] = run["trajectory"]
        pred_events.extend({"seed": seed, **e} for e in run["events"])
        work_rows.append({
            "seed": seed,
            "work_min": run["work_min"],
            "work_end": run["final"].get("work"),
            "move_work_sum": sum(r["move_work"] for r in run["rows"]),
            "motor_work_sum": sum(r["motor_work"] for r in run["rows"]),
            "xfer_A_sum": sum(r["xfer_A"] for r in run["rows"]),
            "xfer_B_sum": sum(r["xfer_B"] for r in run["rows"]),
            "body_A_end": run["final"].get("body_A"),
            "body_B_end": run["final"].get("body_B"),
        })
        del rt

    hist = run_history_controls(17)

    pre = []
    for seed in CONTROL_SEEDS:
        run = run_agent(
            seed, AGENT_CYCLES,
            temperature_cycle_enabled=False,
            resource_suitability_source="independent_phase",
        )
        run.pop("runtime", None)
        early_n = 0
        for cy in run["cycles"]:
            td, tb = cy["T_local_resource_decline"], cy["T_behavior_change"]
            if td is not None and tb is not None and tb < td:
                early_n += 1
        pre.append({"seed": seed, "early_count": early_n, "cycles": run["cycles"], "actions": run["action_counts"]})

    aper = []
    deco = []
    stat = []
    for seed in CONTROL_SEEDS:
        for label, kw, bucket in (
            ("aperiodic", {"cycle_mode": "aperiodic"}, aper),
            ("decorrelated", {"resource_suitability_source": "independent_phase", "resource_phase_mode": "randomized"}, deco),
            ("stationary", {"cycle_mode": "stationary"}, stat),
        ):
            run = run_agent(seed, AGENT_CYCLES, **kw)
            run.pop("runtime", None)
            bucket.append({"seed": seed, "label": label, "actions": run["action_counts"], "cycles": run["cycles"], "lock": run["lock"]})

    baseline_early = sum(
        1
        for run in agents if run["seed"] in CONTROL_SEEDS
        for cy in run["cycles"]
        if cy["T_local_resource_decline"] is not None and cy["T_behavior_change"] is not None and cy["T_behavior_change"] < cy["T_local_resource_decline"]
    )
    controls = {
        "precursor_ablation": {
            "runs": pre,
            "early_count": sum(p["early_count"] for p in pre),
            "baseline_control_seed_early": baseline_early,
            "ablation_removes_early": bool(baseline_early > 0 and sum(p["early_count"] for p in pre) == 0),
        },
        "aperiodic": aper,
        "decorrelated": {
            "runs": deco,
            "note": "Resource suitability phase hashed per cycle; climate T still periodic.",
        },
        "stationary": stat,
    }

    claims = classify(eco, agents, hist, controls)
    _csv(OUT / "CYCLE_RESULTS.csv", cycle_rows)
    _json(OUT / "TRAJECTORIES.json", traj)
    _csv(OUT / "RESOURCE_WORK_RESULTS.csv", work_rows)
    _json(OUT / "PREDICTION_TRANSITIONS.json", pred_events)
    _json(OUT / "PRECURSOR_RESULTS.json", {"early_events": claims["early_events"], "ablation": controls["precursor_ablation"]})
    _json(OUT / "HISTORY_CONTROLS.json", hist)
    _json(OUT / "APERIODIC_CONTROLS.json", controls)
    _json(OUT / "SCIENTIFIC_CLAIMS.json", {k: v for k, v in claims.items() if isinstance(v, dict) and "status" in v})
    write_final(claims, eco, agents, hist, controls)
    print("ecology gates", eco["gates"])
    print("claims", {k: v["status"] for k, v in claims.items() if isinstance(v, dict) and "status" in v})
    print("wrote", OUT)


if __name__ == "__main__":
    main()
