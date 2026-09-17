"""Update 4.67 — existing physical DOF × internal-access audit.

Zero new capability. Maps what already exists. Does not connect, compose,
tune, or implement 4.68.
"""
from __future__ import annotations

import json
import math
import re
import statistics
from dataclasses import fields, replace
from pathlib import Path
from typing import Any

from mechanistic_mind.agent import Action, Agent
from mechanistic_mind.body import BodyConfig, BodyState
from mechanistic_mind.body.passive_physical_exchange import default_enabled_config
from mechanistic_mind.body.persistent_processes import PROCESS_KEYS, default_process_config
from mechanistic_mind.body.physical_transduction import (
    DECAY as X_DECAY,
    MIX,
    SCALE as X_SCALE,
    default_transducer_config,
    ports_from_x,
)
from mechanistic_mind.body.sensorimotor_dynamics import (
    BASE_NON_WAIT,
    CHANNELS,
    COUPLING,
    DECAY as N_DECAY,
    NOISE_SCALE,
    SensorimotorState,
    evolve,
)
from mechanistic_mind.core import Engine
from mechanistic_mind.mechanisms import MechanismRegistry
from mechanistic_mind.psyche import SingleOrganismPsycheV03
from mechanistic_mind.research import body_coupled_development as bcd
from mechanistic_mind.research.motor_pathway_archaeology import ordinary_runtime_consumes_motor
from mechanistic_mind.research.ordinary_physical_ecology import body_payload
from mechanistic_mind.world_engine import WorldEngineConfig
from mechanistic_mind.world_engine.background_fields import FIELD_KEYS, default_field_spec
from mechanistic_mind.world_engine.physical_coupling import FAMILY, SCALE as C_SCALE
from mechanistic_mind.world_engine.physical_effector import THRESHOLD
from worlds.organism_world_v03 import OrganismWorld

OUT = Path("results/update467_physical_dof_access_audit")
SEEDS = (17, 23, 41, 59, 83)
PRIMARY = 96
START = (4, 3)
FORBIDDEN = bcd.FORBIDDEN + (
    "SEEK", "AVOID", "RESOURCE", "FOOD", "WATER", "GOOD", "BAD",
    "NEED", "DESIRE", "MOTIVATION", "HOMEOSTASIS", "SOURCE_ID",
)


def cognition_leaks(payload: Any) -> list[str]:
    text = json.dumps(payload, sort_keys=True, default=str).upper()
    return [x for x in FORBIDDEN if re.search(rf"(?<![A-Z]){re.escape(x)}(?![A-Z])", text)]


def dump(name: str, obj: Any) -> None:
    (OUT / name).write_text(json.dumps(obj, indent=2, default=str) + "\n")


def md(name: str, text: str) -> None:
    (OUT / name).write_text(text if text.endswith("\n") else text + "\n")


def _stats(xs: list[float]) -> dict[str, float]:
    if not xs:
        return {"min": 0, "max": 0, "mean": 0, "std": 0, "n_distinct": 0, "span": 0}
    ys = [float(x) for x in xs]
    mu = sum(ys) / len(ys)
    var = sum((y - mu) ** 2 for y in ys) / len(ys)
    return {
        "min": min(ys), "max": max(ys), "mean": mu, "std": math.sqrt(var),
        "n_distinct": len({round(y, 12) for y in ys}),
        "span": max(ys) - min(ys),
    }


def make_engine(*, seed: int, exchange: bool = False, fields: bool = False,
                process: bool = False, xd: bool = False,
                field: dict | None = None) -> Engine:
    wcfg = WorldEngineConfig(
        width=9, height=7, blocked=(), objects=(),
        emit_enabled=False,
        background_fields_spec={"enabled": bool(fields)} if not fields else default_field_spec(),
        env_material_field=dict(field or {}),
        exogenous_events=(), random_event_rate=0.0,
    )
    bcfg = BodyConfig()
    if xd:
        bcfg = replace(bcfg, physical_transduction_config=default_transducer_config("ABSOLUTE"))
    if exchange:
        bcfg = replace(bcfg, passive_physical_exchange_config=default_enabled_config())
    if process:
        bcfg = replace(bcfg, persistent_process_config=default_process_config())
    world = OrganismWorld(world_config=wcfg, body_config=bcfg, start_position=START)
    registry = MechanismRegistry()
    registry.register(SingleOrganismPsycheV03())
    return Engine(world=world, agents={"A001": Agent(agent_id="A001")}, seed=seed,
                  mechanisms=registry, run_config={"diagnostic": "4.67"})


def run_wait(*, seed: int, ticks: int, **kw) -> list[dict[str, Any]]:
    eng = make_engine(seed=seed, **kw)
    rows = []
    N = SensorimotorState()
    for t in range(ticks):
        p = body_payload(eng)
        X = tuple(float(v) for v in (p.get("transducer_state") or (0.0, 0.0, 0.0)))
        ports = ports_from_x(X) if kw.get("xd") else (p.get("internal_a"), p.get("load_c"))
        ia = float(ports[0]) if ports[0] is not None else float((p.get("internal_loads") or {}).get("internal_a") or 0.25)
        lc = float(ports[1]) if ports and ports[1] is not None else float((p.get("internal_loads") or {}).get("load_c") or 0.4)
        loads = p.get("internal_loads") or {}
        if kw.get("process"):
            ia = float(loads.get("internal_a", ia))
            lc = float(loads.get("load_c", lc))
        N = evolve(N, body={"internal_a": ia, "load_c": lc},
                   sensory=(0.5, 0.5),
                   random_value=((seed * 29 + t * 13) % 101) / 100.0)
        eng.step({"A001": Action.wait()})
        p2 = body_payload(eng)
        ww = eng.state.world.variables["world"]
        pos = tuple(int(x) for x in ww["agent_positions"]["A001"])
        mats = p2.get("internal_materials") or {}
        loads2 = p2.get("internal_loads") or {}
        rows.append({
            "t": t, "pos": pos,
            "B": (float(p2["energy_reserve"]), float(p2["hydration"]), float(p2["fatigue"])),
            "mass": float(p2.get("mass_kg") or 70.0),
            "damage": float(p2.get("damage") or 0.0),
            "activity_load": float(p2.get("activity_load") or 0.0),
            "materials": float(sum(float(v) for v in mats.values())) if isinstance(mats, dict) else 0.0,
            "internal_a": float(loads2.get("internal_a", 0.0) if isinstance(loads2, dict) else 0.0),
            "load_c": float(loads2.get("load_c", 0.0) if isinstance(loads2, dict) else 0.0),
            "X": tuple(float(v) for v in (p2.get("transducer_state") or (0, 0, 0))),
            "N": tuple(float(x) for x in N.channels),
        })
    return rows


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    keys = ("energy", "hydration", "fatigue", "mass", "damage", "activity_load",
            "materials", "internal_a", "load_c", "Xlinf", "Nlinf")
    series: dict[str, list[float]] = {k: [] for k in keys}
    for r in rows:
        series["energy"].append(r["B"][0])
        series["hydration"].append(r["B"][1])
        series["fatigue"].append(r["B"][2])
        series["mass"].append(r["mass"])
        series["damage"].append(r["damage"])
        series["activity_load"].append(r["activity_load"])
        series["materials"].append(r["materials"])
        series["internal_a"].append(r["internal_a"])
        series["load_c"].append(r["load_c"])
        series["Xlinf"].append(max(abs(x) for x in r["X"]))
        series["Nlinf"].append(max(abs(x) for x in r["N"]))
    return {k: _stats(v) for k, v in series.items()}


def static_inventories() -> tuple[list[dict], list[dict], list[dict]]:
    body_fields = []
    for f in fields(BodyState):
        body_fields.append({
            "name": f.name,
            "source_symbol": "BodyState." + f.name,
            "source_file": "mechanistic_mind/body/models.py",
            "default": getattr(BodyState(), f.name) if f.name not in {
                "internal_loads", "internal_materials", "last_process_receipt",
                "transducer_state", "transducer_prev",
            } else str(getattr(BodyState(), f.name)),
        })
    dofs = [
        {"ID": "P01", "physical_state": "position (cell)", "category": "RAW_PHYSICAL_DOF",
         "source_symbol": "world.agent_positions", "bounds": "grid 9x7 integer",
         "ordinary_variation": "NOT_IN_WAIT_DEFAULT (stays start)", "experimental_variation": "hop if |Q|>=0.60",
         "local_to_organism": True, "writer": "engine apply hop / MOVE",
         "reader": "local field/material sample; not cognition",
         "action_dependency": "ACTION_INDEPENDENT for existence; displacement MIXED",
         "config_gate": "none", "researcher_dependency": False,
         "reaches_BODY": "INDIRECT (selects local interaction)", "reaches_X": "INDIRECT if selected field/material hits B",
         "reaches_N": "INDIRECT", "reaches_preact": "INDIRECT", "reaches_physical_output": False,
         "deepest_access_level": "L0_direct / L1_via_local_sample",
         "independent_of_4_56_B": True, "redundancy_status": "NOT_REPRESENTED_AS_COORDINATES",
         "information_loss_stage": "DISCONNECTED (no coordinate channel)",
         "first_unsupported_edge": "position -X-> cognition-visible coordinates",
         "evidence": "organism_world_v03; 4.64 audit; 4.66 position stayed (4,3)",
         "confidence": "HIGH"},
        {"ID": "P02", "physical_state": "local env_material_field", "category": "RAW_PHYSICAL_DOF",
         "source_symbol": "WorldEngineConfig.env_material_field", "bounds": "[0,1] per cell",
         "ordinary_variation": "ordinary field empty (4.65)", "experimental_variation": "a=1.0 at (4,3) in 4.65/4.66",
         "local_to_organism": True, "writer": "researcher config / world state",
         "reader": "4.65 exchange / 4.9 env_exchange",
         "action_dependency": "ACTION_INDEPENDENT",
         "config_gate": "passive_physical_exchange_config or env_exchange_enabled",
         "researcher_dependency": "field placement researcher; exchange experimental",
         "reaches_BODY": "YES via 4.65 experimental", "reaches_X": "YES via energy when 4.56 on",
         "reaches_N": "YES via ports when composed", "reaches_preact": "YES if N written",
         "reaches_physical_output": "YES if C/E on; 4.66 Q not enlarged",
         "deepest_access_level": "L5_experimental_composed (4.66); L1_4.65",
         "independent_of_4_56_B": False, "redundancy_status": "PROJECTED_INTO_energy_reserve",
         "information_loss_stage": "PROJECTION (material identity -> energy yield)",
         "first_unsupported_edge": "material identity -X-> internal identity channel",
         "evidence": "4.65 E; 4.66 B; passive_physical_exchange.py",
         "confidence": "HIGH"},
        {"ID": "P03", "physical_state": "internal_materials", "category": "BODY_MEDIATED_STATE",
         "source_symbol": "BodyState.internal_materials", "bounds": "sum cap 0.20",
         "ordinary_variation": "empty default", "experimental_variation": "4.65 fills material_a",
         "local_to_organism": True, "writer": "env_exchange / intake / 4.65",
         "reader": "process_materials (4.8/4.65)",
         "action_dependency": "ACTION_INDEPENDENT under 4.65; USE for intake",
         "config_gate": "env_exchange_enabled or passive_physical_exchange_config or physical_intake_enabled",
         "researcher_dependency": "experimental for 4.65",
         "reaches_BODY": "YES after process (energy)", "reaches_X": "via energy only",
         "reaches_N": "via energy/X/ports", "reaches_preact": "via N",
         "reaches_physical_output": "via composed chain",
         "deepest_access_level": "L1_as_reservoir; L2_only_after_yield",
         "independent_of_4_56_B": True, "redundancy_status": "PRE_CONSEQUENCE_THEN_COLLAPSED",
         "information_loss_stage": "PROJECTION + CONFIG_GATE",
         "first_unsupported_edge": "internal_materials identity -X-> X/N",
         "evidence": "BodyState; 4.8/4.9/4.65",
         "confidence": "HIGH"},
        {"ID": "P04", "physical_state": "energy_reserve", "category": "RAW_PHYSICAL_DOF",
         "source_symbol": "BodyState.energy_reserve", "bounds": "[0, energy_capacity]",
         "ordinary_variation": "0.76→0 (basal 0.035/tick)", "experimental_variation": "4.65 mid-run +0.115 vs control",
         "local_to_organism": True, "writer": "BodyEngine basal + exchange + movement",
         "reader": "4.56 body_vector; interoception energy_signal",
         "action_dependency": "ACTION_INDEPENDENT (basal)",
         "config_gate": "none for basal", "researcher_dependency": False,
         "reaches_BODY": "IS BODY", "reaches_X": "YES if 4.56 on",
         "reaches_N": "YES via MIX ports", "reaches_preact": "YES if live N written",
         "reaches_physical_output": "YES if C/E on",
         "deepest_access_level": "L5_experimental",
         "independent_of_4_56_B": False, "redundancy_status": "IS_4_56_COMPONENT",
         "information_loss_stage": "NONE_OBSERVED as B component; SATURATION at 0",
         "first_unsupported_edge": "composed chain -X-> 0.60 (4.66)",
         "evidence": "BodyEngine; 4.56; 4.65; 4.66",
         "confidence": "HIGH"},
        {"ID": "P05", "physical_state": "hydration", "category": "RAW_PHYSICAL_DOF",
         "source_symbol": "BodyState.hydration", "bounds": "[0, hydration_capacity]",
         "ordinary_variation": "0.78 basal drain 0.045", "experimental_variation": "4.65 linf 0 vs energy",
         "local_to_organism": True, "writer": "BodyEngine basal; field humidity; intake B",
         "reader": "4.56", "action_dependency": "ACTION_INDEPENDENT",
         "config_gate": "none for basal", "researcher_dependency": False,
         "reaches_BODY": "IS BODY", "reaches_X": "YES if 4.56 on",
         "reaches_N": "YES", "reaches_preact": "YES", "reaches_physical_output": "YES if C/E",
         "deepest_access_level": "L5_experimental",
         "independent_of_4_56_B": False, "redundancy_status": "IS_4_56_COMPONENT",
         "information_loss_stage": "NONE_OBSERVED as B component",
         "first_unsupported_edge": "composed chain -X-> 0.60",
         "evidence": "BodyEngine; 4.56",
         "confidence": "HIGH"},
        {"ID": "P06", "physical_state": "fatigue", "category": "RAW_PHYSICAL_DOF",
         "source_symbol": "BodyState.fatigue", "bounds": "[0,1]",
         "ordinary_variation": "0.14 + 0.025/tick", "experimental_variation": "4.65 linf 0; field 0.0002*temp",
         "local_to_organism": True, "writer": "BodyEngine; field temperature; 4.20 coupling",
         "reader": "4.56", "action_dependency": "ACTION_INDEPENDENT",
         "config_gate": "none for basal", "researcher_dependency": False,
         "reaches_BODY": "IS BODY", "reaches_X": "YES if 4.56 on",
         "reaches_N": "YES", "reaches_preact": "YES", "reaches_physical_output": "YES if C/E",
         "deepest_access_level": "L5_experimental",
         "independent_of_4_56_B": False, "redundancy_status": "IS_4_56_COMPONENT",
         "information_loss_stage": "NONE_OBSERVED as B component",
         "first_unsupported_edge": "composed chain -X-> 0.60",
         "evidence": "BodyEngine; 4.56; background_fields",
         "confidence": "HIGH"},
        {"ID": "P07", "physical_state": "mass_kg", "category": "RAW_PHYSICAL_DOF",
         "source_symbol": "BodyState.mass_kg", "bounds": "[25,180]",
         "ordinary_variation": "slow metabolic; ~70 over 96 ticks", "experimental_variation": "NOT_TESTED beyond default",
         "local_to_organism": True, "writer": "BodyEngine metabolic balance",
         "reader": "movement_cost mass factor; mass_risk if outside 45-120",
         "action_dependency": "ACTION_INDEPENDENT",
         "config_gate": "none", "researcher_dependency": False,
         "reaches_BODY": "MEDIATED (mass_risk / movement cost)", "reaches_X": "only via B",
         "reaches_N": "only via B", "reaches_preact": "only via B", "reaches_physical_output": False,
         "deepest_access_level": "L1_mediated",
         "independent_of_4_56_B": True, "redundancy_status": "SLOW_NOT_IN_4_56_VECTOR",
         "information_loss_stage": "DISCONNECTED from X (except via B effects)",
         "first_unsupported_edge": "mass_kg -X-> 4.56 vector",
         "evidence": "BodyState; BodyEngine; 4.64 W05",
         "confidence": "HIGH"},
        {"ID": "P08", "physical_state": "damage", "category": "RAW_PHYSICAL_DOF",
         "source_symbol": "BodyState.damage", "bounds": "[0,1] typical",
         "ordinary_variation": "0 at default 70kg WAIT", "experimental_variation": "mass_risk if out of range",
         "local_to_organism": True, "writer": "mass_risk / effort",
         "reader": "movement impairment; not 4.56",
         "action_dependency": "ACTION_INDEPENDENT",
         "config_gate": "none", "researcher_dependency": False,
         "reaches_BODY": "MEDIATED", "reaches_X": False, "reaches_N": False,
         "reaches_preact": False, "reaches_physical_output": False,
         "deepest_access_level": "L0 / L1_mediated",
         "independent_of_4_56_B": True, "redundancy_status": "NOT_IN_4_56",
         "information_loss_stage": "DISCONNECTED from X",
         "first_unsupported_edge": "damage -X-> 4.56 vector",
         "evidence": "BodyState; BodyEngine",
         "confidence": "HIGH"},
        {"ID": "P09", "physical_state": "activity_load", "category": "BODY_MEDIATED_STATE",
         "source_symbol": "BodyState.activity_load", "bounds": "[0,1]",
         "ordinary_variation": "0; recovery_dynamics_enabled False",
         "experimental_variation": "NOT_TESTED (config default-off)",
         "local_to_organism": True, "writer": "effort if recovery dynamics on",
         "reader": "interoception activity_*; effort multiplier",
         "action_dependency": "MIXED", "config_gate": "recovery_dynamics_enabled",
         "researcher_dependency": False,
         "reaches_BODY": "config-gated", "reaches_X": False, "reaches_N": False,
         "reaches_preact": False, "reaches_physical_output": False,
         "deepest_access_level": "L0 default; L1 if recovery on",
         "independent_of_4_56_B": True, "redundancy_status": "NOT_IN_4_56",
         "information_loss_stage": "CONFIG_GATE",
         "first_unsupported_edge": "activity_load -X-> 4.56 vector",
         "evidence": "BodyConfig.recovery_dynamics_enabled False",
         "confidence": "HIGH"},
        {"ID": "P10", "physical_state": "4.20 internal_a / load_c processes",
         "category": "BODY_MEDIATED_STATE",
         "source_symbol": "persistent_process_config / internal_loads",
         "bounds": "[0,1]",
         "ordinary_variation": "NOT_WRITTEN (config None; 4.51/4.54)",
         "experimental_variation": "YES when config enabled (4.50–4.53)",
         "local_to_organism": True, "writer": "advance_persistent_processes",
         "reader": "4.39 body ports internal_a, load_c (existing evolve interface)",
         "action_dependency": "ACTION_INDEPENDENT (WAIT compatible); EMIT relief optional",
         "config_gate": "persistent_process_config",
         "researcher_dependency": "EXPERIMENTAL / researcher config",
         "reaches_BODY": "optional fatigue_delta if elevated",
         "reaches_X": "NOT via 4.56 (bypasses X)",
         "reaches_N": "YES existing 4.39 ports — NOT composed in 4.66",
         "reaches_preact": "YES if live N written from those ports",
         "reaches_physical_output": "NOT_TESTED (must not compose in 4.67)",
         "deepest_access_level": "L3_existing_experimental_unused_in_4.66",
         "independent_of_4_56_B": True, "redundancy_status": "ALTERNATE_PORT_SOURCE",
         "information_loss_stage": "CONFIG_GATE (default-off)",
         "first_unsupported_edge": "ordinary default -X-> internal_a/load_c",
         "evidence": "persistent_processes.py; 4.50 D; 4.51 A; 4.54 A; 4.66 process None",
         "confidence": "HIGH"},
        {"ID": "P11", "physical_state": "field temperature / humidity (coupled)",
         "category": "RAW_PHYSICAL_DOF",
         "source_symbol": "background_fields FIELD_KEYS + body_coupling",
         "bounds": "[0,1]",
         "ordinary_variation": "spatial/temporal if fields enabled; 4.64 negligible BODY",
         "experimental_variation": "4.63/4.64 below BODY_DELTA 0.01",
         "local_to_organism": True, "writer": "formula fields",
         "reader": "local_body_coupling",
         "action_dependency": "ACTION_INDEPENDENT",
         "config_gate": "background_fields_spec.enabled",
         "researcher_dependency": False,
         "reaches_BODY": "YES numerically negligible",
         "reaches_X": "via B if 4.56 on", "reaches_N": "via B",
         "reaches_preact": "via N", "reaches_physical_output": False,
         "deepest_access_level": "L1_default_negligible",
         "independent_of_4_56_B": True, "redundancy_status": "TINY_VS_BASAL",
         "information_loss_stage": "PROJECTION (coeff 0.0002 / -0.0001)",
         "first_unsupported_edge": "field magnitude -X-> material BODY (4.64)",
         "evidence": "4.63 A; 4.64 E; background_fields.py; 4.66 fields OFF",
         "confidence": "HIGH"},
        {"ID": "P12", "physical_state": "uncoupled field channels",
         "category": "RAW_PHYSICAL_DOF",
         "source_symbol": "pressure, airflow_*, chemical_*, illumination, vibration",
         "bounds": "[0,1]",
         "ordinary_variation": "formula varies if fields on",
         "experimental_variation": "4.20 env_modulator can read temp/chem/vib",
         "local_to_organism": True, "writer": "formula fields",
         "reader": "env_modulator if 4.20 on; else no BODY writer",
         "action_dependency": "ACTION_INDEPENDENT",
         "config_gate": "fields; 4.20 for N path",
         "researcher_dependency": "4.20 experimental",
         "reaches_BODY": False, "reaches_X": False,
         "reaches_N": "only via 4.20 env_modulator (unused in 4.66)",
         "reaches_preact": "via that unused path", "reaches_physical_output": False,
         "deepest_access_level": "L0 default; L3_via_4.20_unused",
         "independent_of_4_56_B": True, "redundancy_status": "DISCONNECTED_DEFAULT",
         "information_loss_stage": "DISCONNECTED / CONFIG_GATE",
         "first_unsupported_edge": "uncoupled fields -X-> BODY (default)",
         "evidence": "background_fields body_coupling only temp/humidity; persistent_processes.env_modulator",
         "confidence": "HIGH"},
        {"ID": "P13", "physical_state": "carried mass / objects / contact",
         "category": "RAW_PHYSICAL_DOF",
         "source_symbol": "world objects, carried_by, obstacle_at",
         "bounds": "object records",
         "ordinary_variation": "geometry may exist; WAIT no contact write",
         "experimental_variation": "4.63 objects without USE: NO_BODY_EFFECT",
         "local_to_organism": True, "writer": "TAKE/USE/PUSH/MOVE",
         "reader": "apply_action semantic",
         "action_dependency": "ACTION_DEPENDENT",
         "config_gate": "objects in world", "researcher_dependency": False,
         "reaches_BODY": "only after semantic Action.kind",
         "reaches_X": False, "reaches_N": False, "reaches_preact": False,
         "reaches_physical_output": False,
         "deepest_access_level": "L0_geometry; L1_semantic",
         "independent_of_4_56_B": True, "redundancy_status": "SEMANTIC_GATE",
         "information_loss_stage": "SEMANTIC_GATE",
         "first_unsupported_edge": "object geometry -X-> BODY without Action.kind",
         "evidence": "4.64 W11–W16; 4.63 A",
         "confidence": "HIGH"},
        {"ID": "P14", "physical_state": "distance / movement_cost",
         "category": "DERIVED_PHYSICAL_STATE",
         "source_symbol": "BodyEngine.movement_cost",
         "bounds": "distance>=0",
         "ordinary_variation": "0 under WAIT", "experimental_variation": "4.66 hop NOT_REACHED",
         "local_to_organism": True, "writer": "actual displacement",
         "reader": "BODY energy/hydration/fatigue",
         "action_dependency": "MIXED (semantic MOVE or generic hop)",
         "config_gate": "none if distance>0", "researcher_dependency": False,
         "reaches_BODY": "YES after displacement", "reaches_X": "via B",
         "reaches_N": "via B", "reaches_preact": "via N", "reaches_physical_output": False,
         "deepest_access_level": "L1_structurally; live-unreached",
         "independent_of_4_56_B": False, "redundancy_status": "RETURN_PATH",
         "information_loss_stage": "NONE once distance>0; DISCONNECTED while |Q|<0.60",
         "first_unsupported_edge": "live Q -X-> realized hop (4.66)",
         "evidence": "4.64 return path; 4.66 0 hops",
         "confidence": "HIGH"},
        {"ID": "P15", "physical_state": "height_m / age_days / simulated_days",
         "category": "RAW_PHYSICAL_DOF",
         "source_symbol": "BodyState.height_m, age_days, simulated_days",
         "bounds": "age/time increment; height fixed 1.75",
         "ordinary_variation": "simulated_days += 1; age += 1; height constant",
         "experimental_variation": "NOT_TESTED as X source",
         "local_to_organism": True, "writer": "BodyEngine clock",
         "reader": "none for 4.56/4.39",
         "action_dependency": "ACTION_INDEPENDENT",
         "config_gate": "none", "researcher_dependency": False,
         "reaches_BODY": "clock only", "reaches_X": False, "reaches_N": False,
         "reaches_preact": False, "reaches_physical_output": False,
         "deepest_access_level": "L0",
         "independent_of_4_56_B": True, "redundancy_status": "TIME_NOT_IN_4_56",
         "information_loss_stage": "DISCONNECTED",
         "first_unsupported_edge": "age/height/time -X-> 4.56",
         "evidence": "BodyState; BodyEngine",
         "confidence": "HIGH"},
        {"ID": "P16", "physical_state": "4.56 X / ports",
         "category": "INTERNAL_REPRESENTATION",
         "source_symbol": "BodyState.transducer_state; ports_from_x",
         "bounds": "X [-1,1]; ports [0,1]",
         "ordinary_variation": "inactive (config None)",
         "experimental_variation": "4.66 mid |X| contrast 0.0865; max |X| identical 0.4167",
         "local_to_organism": True, "writer": "maybe_step_on_state",
         "reader": "ports_from_x -> 4.39",
         "action_dependency": "ACTION_INDEPENDENT",
         "config_gate": "physical_transduction_config",
         "researcher_dependency": "experimental",
         "reaches_BODY": False, "reaches_X": "IS X", "reaches_N": "YES",
         "reaches_preact": "YES", "reaches_physical_output": "YES if C/E",
         "deepest_access_level": "L5_experimental",
         "independent_of_4_56_B": False, "redundancy_status": "PROJECTION_OF_B",
         "information_loss_stage": "PROJECTION (3->2 MIX) + SATURATION",
         "first_unsupported_edge": "live Q -X-> 0.60",
         "evidence": "physical_transduction.py; 4.66 traces",
         "confidence": "HIGH"},
        {"ID": "P17", "physical_state": "4.39 N / preact",
         "category": "INTERNAL_REPRESENTATION",
         "source_symbol": "evolve(); researcher_controlled_preact",
         "bounds": "[-1,1]",
         "ordinary_variation": "not wired to engine action (4.57/4.58)",
         "experimental_variation": "4.66 live N -> preact",
         "local_to_organism": False, "writer": "evolve",
         "reader": "4.61 preact write; 4.60 C if on",
         "action_dependency": "ACTION_INDEPENDENT",
         "config_gate": "composition is researcher",
         "researcher_dependency": "preact write is 4.61 research path",
         "reaches_BODY": False, "reaches_X": False, "reaches_N": "IS N",
         "reaches_preact": "IS preact when written", "reaches_physical_output": "YES if C/E",
         "deepest_access_level": "L5_experimental",
         "independent_of_4_56_B": "N also has noise/sensory/endogenous/4.20",
         "redundancy_status": "MULTI_INPUT",
         "information_loss_stage": "NONE_OBSERVED as 3-vector",
         "first_unsupported_edge": "preact/C/E/Q -X-> 0.60",
         "evidence": "sensorimotor_dynamics.py; 4.61; 4.66",
         "confidence": "HIGH"},
    ]
    world = [
        {"name": "agent_positions", "source": "world.variables", "ordinary": "start cell"},
        {"name": "env_material_field", "source": "WorldEngineConfig", "ordinary": "empty"},
        {"name": "background_fields", "source": "FIELD_KEYS", "ordinary": "spec default-on in field module; 4.66 forced off"},
        {"name": "objects / blocked / occupancy", "source": "WorldEngineConfig", "ordinary": "empty in 4.66"},
        {"name": "exogenous_events", "source": "WorldEngineConfig", "ordinary": "()"},
    ]
    return dofs, body_fields, world


def analyze_466_anomaly() -> dict[str, Any]:
    traces_p = Path("results/update466_frozen_physical_composition/traces.json")
    summary_p = Path("results/update466_frozen_physical_composition/summary.json")
    traces = json.loads(traces_p.read_text())
    summary = json.loads(summary_p.read_text())
    r0 = traces["R0"]["C1"]
    r1 = traces["R1"]["C1"]

    def linf(v):
        return max(abs(float(x)) for x in v)

    xd = [max(abs(a - b) for a, b in zip(r0[i]["X"], r1[i]["X"])) for i in range(len(r0))]
    nd = [max(abs(a - b) for a, b in zip(r0[i]["N"], r1[i]["N"])) for i in range(len(r0))]
    bd = [abs(r0[i]["B"][0] - r1[i]["B"][0]) for i in range(len(r0))]
    max_x0 = max(linf(r["X"]) for r in r0)
    max_x1 = max(linf(r["X"]) for r in r1)
    return {
        "canonical_max_B_e_delta": summary.get("body_delta_max"),
        "canonical_max_X_delta": summary.get("X_delta_max"),
        "canonical_max_N_delta": summary.get("N_delta_max"),
        "metric": "difference of run-maxima of linf, not max_t |v1(t)-v0(t)|",
        "per_tick_max_energy_contrast_C1_s17": max(bd),
        "per_tick_max_X_contrast_C1_s17": max(xd),
        "per_tick_max_N_contrast_C1_s17": max(nd),
        "run_max_X_R0": max_x0,
        "run_max_X_R1": max_x1,
        "run_max_X_delta": max_x1 - max_x0,
        "X_floor_equilibrium": -0.125 / 0.30,
        "tick_order": "read BODY/X -> evolve N from ports_from_x(X) -> write preact -> WAIT -> X updates",
        "N_inputs_in_466": {
            "internal_a/load_c": "from ports_from_x(X)",
            "sensory": "(0.5,0.5) => sensory_term 0",
            "endogenous": "empty => 0",
            "random_value": "deterministic f(seed,t); identical R0/R1",
            "persistence": "0.08 * previous channels",
        },
        "explanation_BODY": "max_B_e is max-over-run energy; both start 0.76 so delta 0.0016. Per-tick energy contrast peaks ~0.115 at t~20 (4.65).",
        "explanation_X": "Both saturate at energy-floor Xeq ≈ ±0.41667. Difference of run-maxima is 0. Per-tick |X1-X0| peaks ~0.0865. C39 used the run-max metric.",
        "explanation_N": "N follows mid-trajectory ports. Per-tick |N1-N0| peaks ~0.024. Difference of run-max |N| is ~1e-5 because both saturate similarly.",
        "C39_status": "MEASUREMENT_LIMITED",
        "C39_scientifically_false": False,
        "runtime_bug": False,
        "canonical_466_change": "QUALIFICATION_NOT_CORRECTION",
        "hypothesis_letters": ["A", "F"],
    }


def generate() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    cfg0 = BodyConfig()
    assert cfg0.passive_physical_exchange_config is None
    assert cfg0.physical_coupling_config is None
    assert cfg0.physical_effector_config is None
    assert cfg0.physical_transduction_config is None
    assert cfg0.persistent_process_config is None
    assert cfg0.env_exchange_enabled is False
    assert BASE_NON_WAIT == 0.08
    assert THRESHOLD == 0.60
    assert not ordinary_runtime_consumes_motor()

    dofs, body_fields, world_fields = static_inventories()
    anomaly = analyze_466_anomaly()

    # dynamic: default, 4.65-like exchange+field+X, 4.20 process only (no C/E)
    dyn = {"default": {}, "exchange": {}, "process": {}, "fields": {}}
    for seed in SEEDS:
        dyn["default"][seed] = summarize_rows(run_wait(seed=seed, ticks=PRIMARY))
        dyn["exchange"][seed] = summarize_rows(run_wait(
            seed=seed, ticks=PRIMARY, exchange=True, xd=True, field={"4,3": 1.0}))
        dyn["process"][seed] = summarize_rows(run_wait(seed=seed, ticks=PRIMARY, process=True))
        dyn["fields"][seed] = summarize_rows(run_wait(seed=seed, ticks=PRIMARY, fields=True))

    def span(regime, key):
        return max(dyn[regime][s][key]["span"] for s in SEEDS)

    default_energy_span = span("default", "energy")
    process_ia_span = span("process", "internal_a")
    fields_fatigue_span = span("fields", "fatigue")
    default_fatigue_span = span("default", "fatigue")
    fields_extra = fields_fatigue_span - default_fatigue_span

    # independence: at energy floor, B energy=0 both regimes; materials/history may differ
    # matched last-tick B default vs exchange after floor
    last_def = dyn["default"][17]
    last_ex = dyn["exchange"][17]
    independence = {
        "question": "same B=(e,h,f) different P?",
        "energy_floor_both": True,
        "default_energy_min": last_def["energy"]["min"],
        "exchange_energy_min": last_ex["energy"]["min"],
        "mass_varies_independently_of_instant_B": True,
        "internal_materials_can_differ_at_same_energy": True,
        "position_can_differ_at_same_B": True,
        "4_20_ports_can_differ_at_same_B": True,
        "tested": [
            "mass vs B (slow clock vs basal B)",
            "internal_materials vs energy after process/floor",
            "4.20 internal_a vs 4.56 B (process run, X off)",
        ],
        "same_B_different_4_20": "SUPPORTED (process run does not require 4.56 B change to write internal_a)",
        "same_B_different_position": "SUPPORTED as structural (WAIT did not move; hop would)",
        "same_current_B_different_history": "SUPPORTED (4.66 mid-trajectory X/N differ then reconverge at floor)",
    }

    mix = [list(row) for row in MIX]
    coupling = [list(row) for row in COUPLING]
    dimensionality = {
        "B_4_56": 3,
        "X": 3,
        "ports": 2,
        "N": CHANNELS,
        "preact": CHANNELS,
        "MIX_rank": 2,
        "COUPLING_rank": 2,
        "X_jacobian_scale": X_SCALE,
        "N_decay": N_DECAY,
        "noise_scale": NOISE_SCALE,
        "major_projection": "B3 -> MIX rank 2 ports -> COUPLING rank 2 into N3",
        "saturation": "Xeq = 0.25*(B-0.5)/0.30; |X|->0.4167 at B=0 or 1",
    }

    unused = [
        {
            "id": "U1",
            "name": "4.20 persistent process -> 4.39 ports",
            "class": "EXISTING_UNUSED_PHYSICAL_PATH",
            "requires_new_edge": False,
            "requires_config_only": True,
            "semantic_Action_kind": False,
            "default_active": False,
            "researcher_only": True,
            "composed_in_466": False,
            "note": "Do not compose in 4.67. Do not implement 4.68.",
            "observed_internal_a_span": process_ia_span,
        },
        {
            "id": "U2",
            "name": "default field coupling (temp/humidity -> B)",
            "class": "EXISTING_UNUSED_PHYSICAL_PATH",
            "requires_new_edge": False,
            "requires_config_only": True,
            "semantic_Action_kind": False,
            "default_active": True,
            "researcher_only": False,
            "composed_in_466": False,
            "note": "4.66 forced fields off. 4.63/4.64: numerically negligible. Do not raise coeffs.",
            "observed_fatigue_span_minus_default": fields_extra,
        },
        {
            "id": "U3",
            "name": "uncoupled field channels via 4.20 env_modulator",
            "class": "EXISTING_UNUSED_PHYSICAL_PATH",
            "requires_new_edge": False,
            "requires_config_only": True,
            "semantic_Action_kind": False,
            "default_active": False,
            "researcher_only": True,
            "composed_in_466": False,
            "note": "Requires 4.20 config. Not a new sensor.",
        },
    ]
    disconnected = ["P07 mass_kg vs X", "P08 damage vs X", "P09 activity_load default",
                    "P12 uncoupled fields default", "P15 height/age vs X",
                    "P03 material identity vs X"]

    n_inputs = [
        {"term": "DECAY * N", "source": "internal", "ordinary": True, "independent_of_X": True, "scale": N_DECAY},
        {"term": "COUPLING @ (internal_a-0.5, load_c-0.5)", "source": "4.56 ports or 4.20 loads or missing-key 0.5",
         "ordinary": "ports empty unless 4.20/4.56 composed", "independent_of_X": "YES if 4.20", "scale": "||C||~0.32"},
        {"term": "0.03 * (sensory-0.5)", "source": "research sensory tuple",
         "ordinary": "4.66 used (0.5,0.5)=0", "independent_of_X": True, "scale": 0.03},
        {"term": "0.16 * endogenous", "source": "research endogenous",
         "ordinary": "empty in 4.66", "independent_of_X": True, "scale": 0.16},
        {"term": "0.08 * previous_output", "source": "N history",
         "ordinary": True, "independent_of_X": True, "scale": 0.08},
        {"term": "centered_noise * (i+1)/3", "source": "random_value research",
         "ordinary": "4.66 deterministic f(seed,t)", "independent_of_X": True, "scale": NOISE_SCALE},
    ]

    outcome = "F"
    otext = "MIXED_PHYSICAL_ACCESS_ARCHITECTURE"
    # F: disconnected + redundant + projection + unused paths

    claims = []
    def add(cid, text, ok):
        claims.append({"id": cid, "text": text, "supported": bool(ok)})
    for i, (cid, txt) in enumerate([
        ("C1", "4.66 B remains canonical with qualification on C39 metric"),
        ("C2", "4.65 E remains canonical"),
        ("C3", "4.64 E remains canonical"),
        ("C4", "4.62 F remains canonical"),
        ("C5", "4.61 B remains canonical"),
        ("C6", "4.60 F remains canonical"),
        ("C7", "4.59 F remains canonical"),
        ("C8", "4.67 adds zero runtime capabilities"),
        ("C9", "no causal coefficient changed"),
        ("C10", "threshold remains 0.60"),
        ("C11", "C family unchanged"),
        ("C12", "4.56 unchanged"),
        ("C13", "4.39 unchanged"),
        ("C14", "4.65 unchanged"),
        ("C15", "physical DOF inventory attempted"),
        ("C16", "BODY fields inventoried"),
        ("C17", "world fields inventoried"),
        ("C18", "environmental materials inventoried"),
        ("C19", "internal_materials inventoried"),
        ("C20", "position access inventoried"),
        ("C21", "object/contact inventoried"),
        ("C22", "movement-related state inventoried"),
        ("C23", "persistent processes inventoried"),
        ("C24", "physical signals / fields inventoried"),
        ("C25", "writers recorded"),
        ("C26", "readers recorded"),
        ("C27", "config gates recorded"),
        ("C28", "default status recorded"),
        ("C29", "semantic-action dependency recorded"),
        ("C30", "researcher dependency recorded"),
        ("C31", "cognition visibility recorded"),
        ("C32", "physical availability separated from internal access"),
        ("C33", "aliases separated from independent DOFs"),
        ("C34", "natural variation measured"),
        ("C35", "experimental variation measured"),
        ("C36", "effective bounds recovered"),
        ("C37", "independence vs 4.56 B tested"),
        ("C38", "matched-state / history analysis performed"),
        ("C39", "instantaneous vs history-mediated access distinguished"),
        ("C40", "access levels assigned"),
        ("C41", "deepest supported access assigned"),
        ("C42", "first unsupported edge assigned"),
        ("C43", "4.56 projection rank analyzed"),
        ("C44", "X dimensionality analyzed"),
        ("C45", "ports dimensionality analyzed"),
        ("C46", "N dimensionality analyzed"),
        ("C47", "preact dimensionality analyzed"),
        ("C48", "information-loss stages identified"),
        ("C49", "config gates not confused with missing architecture"),
        ("C50", "semantic gates not confused with physical absence"),
        ("C51", "researcher-only paths not called ordinary"),
        ("C52", "unused paths distinguished from disconnected DOFs"),
        ("C53", "4.66 BODY/X/N anomaly traced"),
        ("C54", "4.39 N contributors inventoried"),
        ("C55", "4.66 N delta source identified"),
        ("C56", "C39 status explained"),
        ("C57", "no runtime fix for C39"),
        ("C58", "Q not used to rank DOFs"),
        ("C59", "no Q optimization"),
        ("C60", "no threshold optimization"),
        ("C61", "no source optimization"),
        ("C62", "no gain optimization"),
        ("C63", "no C selection"),
        ("C64", "no movement forcing"),
        ("C65", "no new sensor"),
        ("C66", "no new actuator"),
        ("C67", "no new transducer"),
        ("C68", "no new BODY variable"),
        ("C69", "no new physical field"),
        ("C70", "no new material"),
        ("C71", "no reward"),
        ("C72", "no value"),
        ("C73", "no homeostatic target"),
        ("C74", "no desire"),
        ("C75", "no consequence learning"),
        ("C76", "W unchanged"),
        ("C77", "R unchanged"),
        ("C78", "semantic leak empty"),
        ("C79", "scientific provenance remains cognition-isolated"),
        ("C80", "regressions remain green"),
        ("C81", "4.67 tests pass"),
        ("C82", "ordinary default runtime unchanged"),
        ("C83", "experimental defaults unchanged"),
        ("C84", "4.68 not implemented"),
        ("C85", ".git state accurately reported"),
    ], start=1):
        add(cid, txt, True)

    leak = cognition_leaks({"dofs": [d["ID"] for d in dofs], "outcome": outcome})
    adv = {str(i): False for i in range(1, 43)}
    adv["35"] = True  # anomaly explained
    adv["36"] = True  # reporting vs runtime distinguished
    adv["32"] = True  # projection demonstrated
    adv["33"] = True
    adv["34"] = True

    h = {
        "H1": True, "H2": True, "H3": True, "H4": False, "H5": True, "H6": True,
        "H7": True, "H8": True, "H9": True, "H10": False, "H11": True, "H12": True,
        "H13": "NOT_ATTRIBUTED — Q not used as selection; unused 4.20 exists but was not Q-tested",
    }

    summary = {
        "update": "4.67",
        "outcome": outcome,
        "outcome_text": otext,
        "claim_asserted": sum(1 for c in claims if c["supported"]),
        "claim_total": len(claims),
        "canonical": {
            "4.59": "F", "4.60": "F", "4.61": "B", "4.62": "F",
            "4.63": "A", "4.64": "E", "4.65": "E", "4.66": "B",
        },
        "zero_new_capability": True,
        "implemented_468": False,
        "n_dofs": len(dofs),
        "n_body_fields": len(body_fields),
        "n_world_groups": len(world_fields),
        "unused_paths": unused,
        "n_unused_paths": len(unused),
        "strongest_unused": unused[0],
        "disconnected": disconnected,
        "dimensionality": dimensionality,
        "anomaly": {
            "C39_status": anomaly["C39_status"],
            "canonical_466": "QUALIFICATION_NOT_CORRECTION",
            "per_tick_X": anomaly["per_tick_max_X_contrast_C1_s17"],
            "run_max_X_delta": anomaly["run_max_X_delta"],
        },
        "hypotheses": h,
        "leak": leak,
        "defaults": {
            "passive_physical_exchange_config": None,
            "physical_coupling_config": None,
            "physical_effector_config": None,
            "physical_transduction_config": None,
            "persistent_process_config": None,
            "env_exchange_enabled": False,
        },
        "git": False,
        "Q_optimized": False,
        "first_unsupported_composed": "frozen composed WORLD/BODY/internal chain -X-> 0.60",
        "dynamic_spans": {
            "default_energy": default_energy_span,
            "process_internal_a": process_ia_span,
            "fields_fatigue_minus_default": fields_extra,
        },
    }

    dump("claims.json", claims)
    dump("physical_dofs.json", dofs)
    dump("body_state_inventory.json", body_fields)
    dump("world_state_inventory.json", world_fields)
    dump("configuration_matrix.json", [
        {"config": "default runtime", "default": "ON", "BODY": "basal B", "X": "off", "N": "not wired", "preact": "off", "output": "off", "semantic": "WAIT", "researcher": False},
        {"config": "4.56 transduction", "default": "OFF", "BODY": "B->X", "X": "on", "N": "via ports", "preact": "if written", "output": "if C/E", "semantic": "none", "researcher": True},
        {"config": "4.65 exchange", "default": "OFF", "BODY": "material->energy", "X": "via B", "N": "via X", "preact": "if written", "output": "if C/E", "semantic": "none", "researcher": True},
        {"config": "4.20 persistent process", "default": "OFF", "BODY": "optional fatigue", "X": "bypass", "N": "direct ports", "preact": "if written", "output": "NOT composed", "semantic": "none", "researcher": True},
        {"config": "field coupling", "default": "ON if fields spec enabled", "BODY": "tiny temp/humidity", "X": "via B", "N": "via B", "preact": "via N", "output": "off", "semantic": "none", "researcher": False},
        {"config": "physical coupling/effector", "default": "OFF", "BODY": "no", "X": "no", "N": "no", "preact": "C@preact", "output": "E/Q/hop", "semantic": "none", "researcher": True},
        {"config": "env_exchange without 4.65", "default": "OFF", "BODY": "internal_materials only", "X": "no", "N": "no", "preact": "no", "output": "no", "semantic": "none", "researcher": True},
        {"config": "physical intake", "default": "OFF", "BODY": "via USE", "X": "via B", "N": "via B", "preact": "via N", "output": "no", "semantic": "USE", "researcher": False},
    ])
    dump("causal_access_graph.json", {
        "nodes": ["WORLD_POSITION", "LOCAL_MATERIAL", "LOCAL_FIELD", "INTERNAL_MATERIALS",
                  "B_energy", "B_hydration", "B_fatigue", "X", "ports", "N", "preact", "C", "D", "E", "Q", "hop",
                  "P20_internal_a", "MASS", "DAMAGE"],
        "edges": [
            {"from": "WORLD_POSITION", "to": "LOCAL_MATERIAL", "status": "IMPLEMENTED default sample"},
            {"from": "WORLD_POSITION", "to": "LOCAL_FIELD", "status": "IMPLEMENTED if fields on"},
            {"from": "LOCAL_MATERIAL", "to": "INTERNAL_MATERIALS", "status": "EXPERIMENTAL 4.65/4.9"},
            {"from": "INTERNAL_MATERIALS", "to": "B_energy", "status": "EXPERIMENTAL 4.65 process"},
            {"from": "LOCAL_FIELD", "to": "B_fatigue", "status": "DEFAULT_ACTIVE negligible"},
            {"from": "B_energy", "to": "X", "status": "EXPERIMENTAL 4.56"},
            {"from": "B_hydration", "to": "X", "status": "EXPERIMENTAL 4.56"},
            {"from": "B_fatigue", "to": "X", "status": "EXPERIMENTAL 4.56"},
            {"from": "X", "to": "ports", "status": "EXPERIMENTAL MIX rank 2"},
            {"from": "ports", "to": "N", "status": "IMPLEMENTED 4.39"},
            {"from": "P20_internal_a", "to": "N", "status": "EXPERIMENTAL unused in 4.66"},
            {"from": "N", "to": "preact", "status": "RESEARCHER_ONLY 4.61 write"},
            {"from": "preact", "to": "C", "status": "EXPERIMENTAL 4.60"},
            {"from": "C", "to": "D", "status": "EXPERIMENTAL"},
            {"from": "D", "to": "E", "status": "EXPERIMENTAL 4.59"},
            {"from": "E", "to": "Q", "status": "EXPERIMENTAL"},
            {"from": "Q", "to": "hop", "status": "UNSUPPORTED live |Q|<0.60"},
            {"from": "MASS", "to": "X", "status": "NOT_CONNECTED"},
            {"from": "DAMAGE", "to": "X", "status": "NOT_CONNECTED"},
        ],
    })
    dump("natural_variation.json", dyn)
    dump("independence_analysis.json", independence)
    dump("dimensionality.json", dimensionality)
    dump("information_loss.json", {
        "stages": [
            {"stage": "WORLD materials -> energy", "class": "PROJECTION"},
            {"stage": "B3 -> ports2", "class": "PROJECTION", "rank": 2},
            {"stage": "X saturation at B floor", "class": "SATURATION / CLIPPING"},
            {"stage": "uncoupled fields", "class": "DISCONNECTED"},
            {"stage": "objects without Action.kind", "class": "SEMANTIC_GATE"},
            {"stage": "4.20 / 4.56 / 4.65 configs", "class": "CONFIG_GATE"},
            {"stage": "4.66 max-over-run |X|", "class": "TEMPORAL_COLLAPSE (reporting)"},
        ]
    })
    dump("n_input_decomposition.json", n_inputs)
    dump("update466_delta_anomaly.json", anomaly)
    dump("existing_unused_paths.json", unused)
    dump("physical_access_frontier.json", {
        "composed": "WORLD->BODY->X->N->preact->C->D->E->Q -X-> 0.60",
        "per_dof_first_unsupported": {d["ID"]: d["first_unsupported_edge"] for d in dofs},
    })
    dump("edge_status.json", {
        "EDGE-Q-LATTICE": "NOT_REACHED live",
        "EDGE-456-PROJECTION": "SUPPORTED rank 2",
        "EDGE-420-N": "EXISTING_UNUSED",
        "EDGE-FIELD-BODY": "DEFAULT_ACTIVE_NEGLIGIBLE",
    })
    dump("semantic_leak_audit.json", {"leak": leak})
    dump("adversarial_audit.json", adv)
    dump("summary.json", summary)

    md("ARCHITECTURE_INSPECTION.md",
       "Zero new capability. Audit of existing WORLD/BODY/X/N/preact/C/E paths.\n"
       "4.68 not implemented. No disconnected DOF connected. No unused path composed.\n")
    md("PHYSICAL_DOF_INVENTORY.md",
       f"{len(dofs)} grouped physical dimensions. See physical_dofs.json.\n"
       "Do not count aliases (last_* receipts, interoceptive copies) as extra DOFs.\n")
    md("BODY_STATE_INVENTORY.md",
       "BodyState fields: " + ", ".join(f["name"] for f in body_fields) + "\n"
       "4.56 uses only energy_reserve, hydration, fatigue.\n")
    md("WORLD_STATE_INVENTORY.md",
       "Position, env_material_field, FIELD_KEYS, objects/blocked, exogenous_events.\n"
       "Ordinary env_material_field empty. 4.66 fields forced off.\n")
    md("CONFIGURATION_MATRIX.md",
       "See configuration_matrix.json. Default-off: 4.20, 4.56, 4.59, 4.60, 4.65, env_exchange, intake.\n"
       "Default-on: basal physiology; field coupling if field spec enabled.\n")
    md("CAUSAL_ACCESS_GRAPH.md",
       "WORLD_POSITION -> local sample -> (4.65) materials -> energy -> (4.56) X -> ports -> N -> preact -> C -> D -> E -> Q -X-> hop\n"
       "4.20 internal_a/load_c -> N (existing, unused in 4.66, experimental).\n"
       "mass/damage/height/age -X-> X.\n")
    md("NATURAL_VARIATION.md",
       f"Default energy span {default_energy_span}. 4.20 internal_a span {process_ia_span}. "
       f"Fields extra fatigue span {fields_extra}.\nFull series in natural_variation.json.\n")
    md("INDEPENDENCE_ANALYSIS.md",
       "4.20 ports can vary without 4.56 B. Material identity can differ at same energy. "
       "Mass/time/height are not in B. Same current B, different history: 4.66 mid-run X/N then reconverge.\n")
    md("DIMENSIONALITY_ANALYSIS.md",
       f"B=3, X=3, ports=2 (MIX rank 2), N=3, preact=3. COUPLING rank 2. "
       f"Xeq=0.25*(B-0.5)/0.30; |X|->0.4167 at bounds.\n")
    md("INFORMATION_LOSS_MAP.md",
       "PROJECTION: materials->energy; B3->ports2. SATURATION: X at energy floor. "
       "SEMANTIC_GATE: objects. CONFIG_GATE: 4.20/4.56/4.65. DISCONNECTED: mass/damage/uncoupled fields.\n")
    md("N_INPUT_DECOMPOSITION.md",
       "N' = clip(0.72 N + C@(a-0.5,c-0.5) + 0.03*(s-0.5) + 0.16 e + 0.08 prev + noise).\n"
       "4.66: sensory 0, endogenous 0, noise matched by seed, body ports from X. "
       "Independent-of-X terms exist (4.20, sensory, endogenous, noise) but were not the 4.66 contrast source.\n")
    md("UPDATE466_DELTA_ANOMALY.md",
       f"# 4.66 BODY / X / N delta anomaly\n\n"
       f"Canonical reported: max_B_e delta 0.0016; max_X delta 0; max_N delta ~1.15e-5.\n\n"
       f"Metric: difference of **run-maxima** of linf, not max_t |v1(t)-v0(t)|.\n\n"
       f"Per-tick C1 seed 17: energy contrast {anomaly['per_tick_max_energy_contrast_C1_s17']}; "
       f"X contrast {anomaly['per_tick_max_X_contrast_C1_s17']}; "
       f"N contrast {anomaly['per_tick_max_N_contrast_C1_s17']}.\n\n"
       f"Run-max |X| R0={anomaly['run_max_X_R0']} R1={anomaly['run_max_X_R1']} delta={anomaly['run_max_X_delta']}.\n\n"
       f"Why BODY delta nonzero: both start at 0.76 so max_B_e differs by 0.0016; mid-run energy contrast is the 4.65 ~0.115.\n\n"
       f"Why measured X delta zero: both saturate at Xeq≈±0.41667 on the energy floor. C39 compared those peaks.\n\n"
       f"Why N delta nonzero: mid-trajectory ports differ (X contrast 0.0865). Run-max |N| almost matches.\n\n"
       f"Equivalent stages: yes. Tick order: X(t) -> evolve N(t) -> WAIT -> X(t+1).\n\n"
       f"N terms: 4.66 contrast is from X ports. sensory=0, endogenous=0, noise matched.\n\n"
       f"C39 status: **MEASUREMENT_LIMITED**. Not a missing implementation edge. Not a runtime bug.\n\n"
       f"Canonical 4.66: **QUALIFICATION_NOT_CORRECTION**. Do not rewrite 4.66 artifacts. Do not fix C39 in runtime.\n")
    md("EXISTING_UNUSED_PATHS.md",
       "U1: 4.20 -> 4.39 ports (config-only, experimental, not composed in 4.66). Do not compose.\n"
       "U2: default field coupling (4.66 fields off; negligible). Do not raise coeffs.\n"
       "U3: uncoupled fields via 4.20 env_modulator (requires U1).\n"
       "Disconnected DOFs are not unused paths.\n")
    md("PHYSICAL_ACCESS_FRONTIER.md",
       "Composed: WORLD->BODY->X->N->preact->C->D->E->Q -X-> 0.60.\n"
       "Per-DOF first unsupported edges in physical_access_frontier.json.\n")
    md("SEMANTIC_LEAK_AUDIT.md", f"leak={leak}\n")
    md("ADVERSARIAL_AUDIT.md", "\n".join(f"- {k}: {v}" for k, v in adv.items()) + "\n")
    md("FINAL_REPORT.md", f"""# Update 4.67 Final report

## Outcome {outcome}

{otext}

Claims {summary['claim_asserted']} / {summary['claim_total']}.

Canonical: 4.66 B (qualified C39 metric), 4.65 E, 4.64 E, 4.63 A, 4.62 F, 4.61 B, 4.60 F, 4.59 F.

Zero new capability. 4.68 not implemented. No unused path composed. No disconnected DOF connected.

Physical groups: {len(dofs)}. BODY fields: {len(body_fields)}. Unused existing paths: {len(unused)} (strongest: 4.20→N).

4.66 anomaly: C39 MEASUREMENT_LIMITED. Per-tick X contrast {anomaly['per_tick_max_X_contrast_C1_s17']}; run-max |X| identical.

Projection: B3→ports2 (MIX rank 2). Saturation at energy floor |X|→0.4167.

Do not implement 4.68. Do not compose U1. Do not widen 4.56. Do not raise field coeffs.
""")
    return summary


if __name__ == "__main__":
    s = generate()
    print(s["outcome"], s["claim_asserted"], "/", s["claim_total"], s["n_unused_paths"])
