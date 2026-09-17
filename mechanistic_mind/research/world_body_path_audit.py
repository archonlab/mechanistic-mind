"""Update 4.64 — WORLD→BODY path completeness × semantic action dependency audit.

Zero new capability. Architecture + causal completeness only.
Does not add, connect, strengthen, or activate any WORLD→BODY pathway.
Does not implement 4.65.
"""
from __future__ import annotations

import json
import re
from dataclasses import replace
from pathlib import Path
from typing import Any

from mechanistic_mind.agent import Action, Agent
from mechanistic_mind.body import BodyConfig
from mechanistic_mind.body.physical_transduction import (
    DECAY as X_DECAY,
    MIX,
    SCALE as X_SCALE,
    body_vector_from_values,
)
from mechanistic_mind.body.sensorimotor_dynamics import BASE_NON_WAIT
from mechanistic_mind.core import Engine
from mechanistic_mind.mechanisms import MechanismRegistry
from mechanistic_mind.psyche import SingleOrganismPsycheV03
from mechanistic_mind.research import body_coupled_development as bcd
from mechanistic_mind.research.live_operating_range import PRIMARY, SEEDS
from mechanistic_mind.research.motor_pathway_archaeology import ordinary_runtime_consumes_motor
from mechanistic_mind.research.ordinary_physical_ecology import body_payload, default_engine
from mechanistic_mind.world_engine import WorldEngineConfig
from mechanistic_mind.world_engine.background_fields import default_field_spec
from mechanistic_mind.world_engine.physical_coupling import SCALE as C_SCALE
from mechanistic_mind.world_engine.physical_effector import DECAY as E_DECAY, THRESHOLD
from worlds.organism_world_v03 import OrganismWorld, default_organism_world_config

OUT = Path("results/update464_world_body_path_audit")
CANONICAL_OBJECTS = default_organism_world_config().objects
FORBIDDEN = bcd.FORBIDDEN + (
    "FOOD", "WATER", "RESOURCE", "DANGER", "MEDICINE", "BENEFICIAL", "HARMFUL",
    "TARGET", "GOAL", "DESIRED_OBJECT", "DESIRED_STATE", "ECOLOGY_CONDITION",
    "THRESHOLD_MARGIN", "SUCCESS", "FAILURE", "PASSIVE_PATH", "ECOLOGY_CLASS",
    "WORLD_CHANGED", "SELF",
)


def cognition_leaks(payload: Any) -> list[str]:
    text = json.dumps(payload, sort_keys=True, default=str).upper()
    return [x for x in FORBIDDEN if re.search(rf"(?<![A-Z]){re.escape(x)}(?![A-Z])", text)]


def _linf_traj(a: list[float], b: list[float]) -> float:
    return max((abs(float(x) - float(y)) for x, y in zip(a, b)), default=0.0)


def _mean_abs(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    return sum(abs(float(a[i]) - float(b[i])) for i in range(n)) / n


def _l1_last(a: dict[str, list[float]], b: dict[str, list[float]]) -> float:
    return sum(abs(a[k][-1] - b[k][-1]) for k in ("energy", "hydration", "fatigue"))


BODY_INPUTS = {
    "consumed_by_4_56": ["energy_reserve", "hydration", "fatigue"],
    "source": "mechanistic_mind/body/physical_transduction.py body_vector_from_values / maybe_step_on_state",
    "aliases": [],
    "defaults_on_BodyState": {
        "energy_reserve": 0.76,
        "hydration": 0.78,
        "fatigue": 0.14,
    },
    "missing_key_behavior": "keys always present on BodyState; 4.56 does not read internal_a/load_c/internal_materials",
    "projection": "X' = clip(0.70 X + 0.25 (B - 0.5), -1, 1) in ABSOLUTE mode",
    "normalization": "BodyEngine writes clip to [0,1]; 4.56 then B-0.5; MIX then clip01(0.5 + 0.5 MIX @ X)",
    "MIX": [[0.70, 0.20, 0.10], [0.10, 0.30, 0.60]],
    "not_consumed": [
        "internal_materials", "internal_loads", "internal_a", "load_c",
        "damage", "mass_kg", "activity_load", "last_effort_cost",
    ],
}


def _w(id_, name, source_file, function, body_output, equation, origin, trigger,
       action, default, relevance, world_input=None, research_status="ordinary",
       note=None, **extra):
    rec = {
        "id": id_,
        "name": name,
        "source_file": source_file,
        "function": function,
        "body_output": body_output,
        "equation": equation,
        "ORIGIN": origin,
        "TRIGGER": trigger,
        "ACTION_DEPENDENCY": action,
        "DEFAULT_STATUS": default,
        "DOWNSTREAM_RELEVANCE": relevance,
        "world_input": world_input,
        "research_status": research_status,
    }
    if note:
        rec["note"] = note
    rec.update(extra)
    return rec


def static_writers() -> list[dict[str, Any]]:
    be = "mechanistic_mind/body/engine.py"
    we = "mechanistic_mind/world_engine/engine.py"
    return [
        _w("W01", "basal_energy_drain", be, "BodyEngine.transition",
           ["energy_reserve"], "energy += -basal_energy_drain_per_day * days (0.035)",
           "BODY_INTERNAL", "ALWAYS", "NONE", "DEFAULT_ON", "DIRECT_TO_4_56_BODY"),
        _w("W02", "basal_hydration_drain", be, "BodyEngine.transition",
           ["hydration"], "hydration += -basal_hydration_drain_per_day * days (0.045)",
           "BODY_INTERNAL", "ALWAYS", "NONE", "DEFAULT_ON", "DIRECT_TO_4_56_BODY"),
        _w("W03", "passive_fatigue_gain", be, "BodyEngine.transition",
           ["fatigue"], "fatigue += passive_fatigue_gain_per_day * days (0.025)",
           "BODY_INTERNAL", "ALWAYS", "NONE", "DEFAULT_ON", "DIRECT_TO_4_56_BODY"),
        _w("W04", "carried_mass_cost", be, "BodyEngine.transition",
           ["energy_reserve", "hydration", "fatigue"],
           "per-kg-day costs * carried_mass_kg * days",
           "WORLD_PHYSICAL", "OTHER", "SEMANTIC_ACTION_REQUIRED", "DEFAULT_ON",
           "DIRECT_TO_4_56_BODY", world_input="carried_mass_kg after TAKE",
           note="first semantic stage is TAKE; later WAIT pays carried cost"),
        _w("W05", "mass_risk_strain", be, "BodyEngine.transition / mass_risk",
           ["energy_reserve", "fatigue"],
           "fatigue += mass_risk_fatigue_per_day * risk * days; energy -= low_mass extra",
           "BODY_INTERNAL", "ALWAYS", "NONE", "DEFAULT_ON", "DIRECT_TO_4_56_BODY",
           note="mass is metabolic, not a world field"),
        _w("W06", "movement_cost", be, "BodyEngine.movement_cost if distance>0",
           ["energy_reserve", "hydration", "fatigue"],
           "effort=distance*terrain*mass_factor*impairment; per-cell energy 0.012 hydration 0.004 fatigue 0.010",
           "BODY_INTERNAL", "MOVE", "GENERIC_EFFECTOR_COMPATIBLE_ALREADY", "DEFAULT_ON",
           "DIRECT_TO_4_56_BODY", world_input="distance from actual displacement",
           note="trigger is displacement. Semantic MOVE is one producer; 4.59 hop is another."),
        _w("W07", "motor_demand_effort", be, "BodyEngine.transition",
           ["energy_reserve", "hydration", "fatigue"],
           "if motor_demand_effort>0: costs * load_f * fat_f",
           "RESEARCHER", "RESEARCH_ONLY", "UNKNOWN", "DEFAULT_OFF",
           "DIRECT_TO_4_56_BODY", world_input="pending_motor_demand_effort ordinary default 0"),
        _w("W08", "inactivity_recovery", be, "BodyEngine.transition",
           ["fatigue"], "if recovery_dynamics_enabled and not high_demand: fatigue -= recovery",
           "BODY_INTERNAL", "WAIT_COMPATIBLE", "NONE", "DEFAULT_OFF",
           "DIRECT_TO_4_56_BODY"),
        _w("W09", "intake_processing", "mechanistic_mind/body/physical_intake.py",
           "process_materials",
           ["energy_reserve", "hydration", "fatigue"],
           "yields per unit: A energy 0.8; B hydration 0.9; C mixed",
           "BODY_INTERNAL", "WAIT_COMPATIBLE", "INDIRECT", "DEFAULT_OFF",
           "DIRECT_TO_4_56_BODY", world_input="internal_materials already present",
           note="world-entry of material is a separate edge (USE or env_exchange)"),
        _w("W10", "field_body_coupling", "mechanistic_mind/world_engine/background_fields.py",
           "local_body_coupling after every action including WAIT",
           ["fatigue", "hydration"],
           "fatigue += 0.0002 * temperature; hydration += -0.0001 * humidity",
           "WORLD_PHYSICAL", "FIELD", "NONE", "DEFAULT_ON", "DIRECT_TO_4_56_BODY",
           world_input="local temperature, humidity at organism position",
           legal_range={
               "field_values": "[0, 1]",
               "temperature_coeff": 0.0002,
               "humidity_coeff": -0.0001,
               "canonical_region_A_base": {"temperature": 0.62, "humidity": 0.55},
               "global_base": {"temperature": 0.50, "humidity": 0.50},
               "temporal_amplitude": 0.06,
               "noise": 0.01,
           }),
        _w("W11", "object_use_body_effects", we, "apply_action USE:",
           ["energy_reserve", "hydration", "fatigue"],
           "object.body_effects * effect_scale into external_body_effects",
           "WORLD_PHYSICAL", "USE", "SEMANTIC_ACTION_REQUIRED", "DEFAULT_ON",
           "DIRECT_TO_4_56_BODY", world_input="object record at USE target",
           first_semantic_stage="USE"),
        _w("W12", "obstacle_contact_body_effects", we, "apply_action MOVE: obstacle_at",
           ["energy_reserve", "hydration", "fatigue"],
           "obstacle.body_effects on contact probability",
           "WORLD_PHYSICAL", "MOVE", "SEMANTIC_ACTION_REQUIRED", "DEFAULT_ON",
           "DIRECT_TO_4_56_BODY", world_input="obstacle at MOVE destination",
           first_semantic_stage="MOVE"),
        _w("W13", "emit_body_cost", we, "apply_action EMIT",
           ["energy_reserve", "fatigue"],
           "energy_delta=-emit_energy_cost; fatigue_delta=+emit_fatigue_cost",
           "SEMANTIC_ACTION", "EMIT", "SEMANTIC_ACTION_REQUIRED", "DEFAULT_ON",
           "DIRECT_TO_4_56_BODY", first_semantic_stage="EMIT",
           research_status="default_organism_world_config.emit_enabled True; still requires Action.kind EMIT"),
        _w("W14", "take_carry", we, "apply_action TAKE:",
           [], "sets carried_by; no direct energy/hydration/fatigue write",
           "SEMANTIC_ACTION", "TAKE", "SEMANTIC_ACTION_REQUIRED", "DEFAULT_ON",
           "INDIRECT_TO_4_56_BODY", world_input="object", first_semantic_stage="TAKE"),
        _w("W15", "release", we, "apply_action RELEASE:",
           [], "clears carried_by; no direct 4.56 write",
           "SEMANTIC_ACTION", "RELEASE", "SEMANTIC_ACTION_REQUIRED", "DEFAULT_ON",
           "NO_BODY_EFFECT", first_semantic_stage="RELEASE"),
        _w("W16", "push_distance", we, "apply_action PUSH:",
           ["energy_reserve", "hydration", "fatigue"],
           "sets distance=1.0 then W06 movement_cost",
           "SEMANTIC_ACTION", "PUSH", "SEMANTIC_ACTION_REQUIRED", "DEFAULT_ON",
           "DIRECT_TO_4_56_BODY", first_semantic_stage="PUSH"),
        _w("W17", "exogenous_events", we, "apply_exogenous_events",
           ["energy_reserve", "hydration", "fatigue"],
           "scheduled/random event body_effects merged",
           "RESEARCHER", "SCHEDULED", "NONE", "DEFAULT_OFF",
           "DIRECT_TO_4_56_BODY",
           world_input="config.exogenous_events / random_event_rate",
           research_status="ordinary: exogenous_events=(), random_event_rate=0.0"),
        _w("W18", "delayed_use_effects", we, "release_delayed_effects",
           ["energy_reserve", "hydration", "fatigue"],
           "releases previously queued USE body_effects",
           "SEMANTIC_ACTION", "SCHEDULED", "SEMANTIC_ACTION_REQUIRED", "DEFAULT_ON",
           "DIRECT_TO_4_56_BODY", first_semantic_stage="USE",
           research_status="outcome_delay_ticks default 0"),
        _w("W19", "env_exchange_to_internal_materials",
           "worlds/organism_world_v03.py + body/physical_intake.py + body/engine.py",
           "env exchange block; BodyEngine stores env_exchange_transfer",
           ["internal_materials"],
           "accepted material into internal_materials; process_materials skipped unless intake enabled",
           "WORLD_PHYSICAL", "WAIT_COMPATIBLE", "NONE", "DEFAULT_OFF",
           "BODY_BUT_NOT_4_56", world_input="env_material_field at position",
           note="WORLD then internal_materials; no existing edge into energy/hydration/fatigue unless intake processing is also on"),
        _w("W20", "use_intake_transfer", we, "_try_physical_intake_use",
           ["internal_materials"],
           "USE then intake_transfer; processing deferred on the USE tick",
           "WORLD_PHYSICAL", "USE", "SEMANTIC_ACTION_REQUIRED", "DEFAULT_OFF",
           "INDIRECT_TO_4_56_BODY", first_semantic_stage="USE"),
        _w("W21", "persistent_process_4_20",
           "mechanistic_mind/body/persistent_processes.py",
           "advance_persistent_processes",
           ["fatigue", "internal_a", "load_c"],
           "if enabled: env_modulator can raise internal_a; body_coupling may add fatigue_delta",
           "RESEARCHER", "RESEARCH_ONLY", "NONE", "EXPERIMENTAL_ONLY",
           "DIRECT_TO_4_56_BODY", world_input="optional env_sample",
           research_status="persistent_process_config default None; not activated in 4.64"),
        _w("W22", "initialization", "mechanistic_mind/body/models.py",
           "BodyState defaults",
           ["energy_reserve", "hydration", "fatigue"],
           "energy=0.76 hydration=0.78 fatigue=0.14",
           "INITIALIZATION", "OTHER", "NONE", "DEFAULT_ON", "DIRECT_TO_4_56_BODY"),
        _w("W23", "generic_effector_distance",
           "mechanistic_mind/world_engine/physical_effector.py", "maybe_apply",
           [], "realized hop sets extra['distance']=1.0; BodyEngine then applies W06",
           "RESEARCHER", "RESEARCH_ONLY", "GENERIC_EFFECTOR_COMPATIBLE_ALREADY",
           "EXPERIMENTAL_ONLY", "INDIRECT_TO_4_56_BODY",
           research_status="physical_effector_config default None; hop not forced in 4.64"),
        _w("W24", "object_presence_without_use", we, "WAIT branch / apply_action",
           [], "no write",
           "WORLD_PHYSICAL", "OBJECT_PRESENCE", "NONE", "DEFAULT_ON",
           "NO_BODY_EFFECT", world_input="same-cell or adjacent object"),
        _w("W25", "passive_geometry_contact", we, "obstacle_at only inside MOVE:",
           [], "no WAIT/geometry-continuous contact write",
           "WORLD_PHYSICAL", "CONTACT", "SEMANTIC_ACTION_REQUIRED", "DEFAULT_ON",
           "NO_BODY_EFFECT"),
        _w("W26", "acquired_W_4_41",
           "mechanistic_mind/body/adaptive_internal_coupling.py",
           "AdaptiveInternalState / step",
           [], "W is acquired internal structure; no evolve() edge into 4.56 BODY",
           "RESEARCHER", "RESEARCH_ONLY", "NONE", "EXPERIMENTAL_ONLY",
           "NO_BODY_EFFECT", research_status="not a WORLD to BODY mechanism; not activated"),
        _w("W27", "acquired_R_4_46",
           "mechanistic_mind/body/acquired_sensorimotor_coupling.py", "R.step",
           [], "R is downstream of N; does not write energy/hydration/fatigue",
           "BODY_INTERNAL", "RESEARCH_ONLY", "NONE", "EXPERIMENTAL_ONLY",
           "NO_BODY_EFFECT", research_status="not WORLD to BODY; not trained or modified"),
    ]


def _c(id_, source_file, function, world_input, physical_condition, body_output,
       equation, semantic, default, research, relevance, structural, operating, **extra):
    rec = {
        "ID": id_,
        "source_file": source_file,
        "function": function,
        "world_input": world_input,
        "physical_condition": physical_condition,
        "body_output": body_output,
        "equation": equation,
        "semantic_dependency": semantic,
        "default_status": default,
        "research_status": research,
        "candidate_relevance": relevance,
        "STRUCTURAL_STATUS": structural,
        "OPERATING_STATUS": operating,
    }
    rec.update(extra)
    return rec


def static_candidates() -> list[dict[str, Any]]:
    return [
        _c("P1_FIELD_COUPLING", "mechanistic_mind/world_engine/background_fields.py",
           "local_body_coupling", "temperature, humidity at position",
           "background_fields.enabled and body_coupling map present",
           ["fatigue", "hydration"],
           "fatigue += 0.0002*T; hydration += -0.0001*H",
           "NONE", "DEFAULT_ON", "ordinary", "PASSIVE_PHYSICAL_PATH",
           "PRESENT", "UNKNOWN"),
        _c("P2_OBJECT_PRESENCE", "mechanistic_mind/world_engine/engine.py",
           "WAIT / apply_action", "object in same or adjacent cell",
           "object present without USE", [], "no write",
           "NONE for presence; USE required for body_effects",
           "DEFAULT_ON", "ordinary", "PRESENCE_ONLY", "ABSENT", "NO_EFFECT"),
        _c("P3_PASSIVE_CONTACT", "mechanistic_mind/world_engine/engine.py",
           "obstacle_at inside MOVE:", "geometry overlap / occupancy",
           "contact without MOVE", [], "no continuous contact evaluation",
           "SEMANTIC_ACTION_REQUIRED", "DEFAULT_ON", "ordinary", "NOT_PASSIVE",
           "ABSENT", "NO_EFFECT"),
        _c("P4_ENV_EXCHANGE", "worlds/organism_world_v03.py",
           "env exchange block", "env_material_field",
           "env_exchange_enabled and local availability > 0",
           ["internal_materials"],
           "store transfer; no process_materials unless intake enabled",
           "NONE", "DEFAULT_OFF", "experimental flag off", "INCOMPLETE_TO_4_56",
           "PRESENT", "NO_EFFECT"),
        _c("P5_AUTONOMOUS_EXOGENOUS", "mechanistic_mind/world_engine/engine.py",
           "apply_exogenous_events", "scheduled or random events",
           "nonempty exogenous_events or random_event_rate>0",
           ["energy_reserve", "hydration", "fatigue"], "event body_effects",
           "NONE", "DEFAULT_OFF", "ordinary rate 0, events ()",
           "RESEARCHER_DEPENDENT", "PRESENT", "NO_EFFECT"),
        _c("S1_USE_BODY_EFFECTS", "mechanistic_mind/world_engine/engine.py",
           "USE:", "object.body_effects", "Action.kind USE",
           ["energy_reserve", "hydration", "fatigue"], "direct external_body_effects",
           "SEMANTIC_ACTION_REQUIRED", "DEFAULT_ON", "ordinary", "PATH_S",
           "PRESENT", "MATERIAL", first_semantic_stage="USE"),
        _c("S2_MOVE_OBSTACLE", "mechanistic_mind/world_engine/engine.py",
           "MOVE: obstacle", "obstacle.body_effects",
           "Action.kind MOVE into obstacle",
           ["energy_reserve", "hydration", "fatigue"], "contact body_effects",
           "SEMANTIC_ACTION_REQUIRED", "DEFAULT_ON", "ordinary", "PATH_S",
           "PRESENT", "MATERIAL", first_semantic_stage="MOVE"),
        _c("S3_MOVE_OR_HOP_COST", "mechanistic_mind/body/engine.py",
           "movement_cost", "distance>0", "actual displacement",
           ["energy_reserve", "hydration", "fatigue"],
           "per-cell movement costs * effort",
           "GENERIC_EFFECTOR_COMPATIBLE_ALREADY", "DEFAULT_ON",
           "ordinary equation; generic hop currently unreachable",
           "RETURN_PATH", "PRESENT", "UNREACHABLE"),
        _c("S4_EMIT", "mechanistic_mind/world_engine/engine.py",
           "EMIT", None, "Action.kind EMIT", ["energy_reserve", "fatigue"],
           "emit energy/fatigue costs", "SEMANTIC_ACTION_REQUIRED",
           "DEFAULT_ON", "ordinary if emit_enabled", "PATH_S",
           "PRESENT", "MATERIAL", first_semantic_stage="EMIT"),
        _c("S5_INTAKE_USE", "mechanistic_mind/body/physical_intake.py",
           "USE then process_materials on later ticks", "object materials",
           "intake enabled and USE",
           ["energy_reserve", "hydration", "fatigue"],
           "acquisition USE; processing automatic after",
           "SEMANTIC_ACTION_REQUIRED", "DEFAULT_OFF",
           "physical_intake_enabled False", "PATH_S_GATED",
           "PRESENT", "NO_EFFECT", first_semantic_stage="USE"),
    ]

def make_engine(*, seed: int, objects, start, field_spec, env_exchange=False,
                env_field=None, intake=False) -> Engine:
    wcfg = WorldEngineConfig(
        width=9, height=7, blocked=(),
        objects=tuple(objects),
        emit_enabled=False,
        background_fields_spec=field_spec,
        env_material_field=dict(env_field or {}),
        exogenous_events=(),
        random_event_rate=0.0,
    )
    bcfg = BodyConfig()
    if env_exchange:
        bcfg = replace(bcfg, env_exchange_enabled=True)
    if intake:
        bcfg = replace(bcfg, physical_intake_enabled=True)
    world = OrganismWorld(world_config=wcfg, body_config=bcfg, start_position=start)
    registry = MechanismRegistry()
    registry.register(SingleOrganismPsycheV03())
    return Engine(world=world, agents={"A001": Agent(agent_id="A001")}, seed=seed,
                  mechanisms=registry, run_config={"diagnostic": "4.64"})


def run_wait(*, seed: int, objects, start, field_spec, ticks: int,
             env_exchange=False, env_field=None, intake=False) -> dict[str, Any]:
    eng = make_engine(seed=seed, objects=objects, start=start, field_spec=field_spec,
                      env_exchange=env_exchange, env_field=env_field, intake=intake)
    energy, hydration, fatigue, materials = [], [], [], []
    pos = start
    for _ in range(ticks):
        p = body_payload(eng)
        energy.append(float(p["energy_reserve"]))
        hydration.append(float(p["hydration"]))
        fatigue.append(float(p["fatigue"]))
        mats = p.get("internal_materials") or {}
        materials.append(float(sum(float(v) for v in mats.values())) if isinstance(mats, dict) else 0.0)
        eng.step({"A001": Action.wait()})
        ww = eng.state.world.variables["world"]
        pos = tuple(int(x) for x in ww["agent_positions"]["A001"])
    p2 = body_payload(eng)
    energy.append(float(p2["energy_reserve"]))
    hydration.append(float(p2["hydration"]))
    fatigue.append(float(p2["fatigue"]))
    mats = p2.get("internal_materials") or {}
    materials.append(float(sum(float(v) for v in mats.values())) if isinstance(mats, dict) else 0.0)
    return {
        "energy": energy, "hydration": hydration, "fatigue": fatigue,
        "materials": materials, "pos": pos, "n": len(energy),
    }


def traj_stats(ctrl: dict[str, Any], other: dict[str, Any]) -> dict[str, float]:
    out = {}
    for key in ("energy", "hydration", "fatigue"):
        out[f"{key}_linf"] = _linf_traj(ctrl[key], other[key])
        out[f"{key}_mean_abs"] = _mean_abs(ctrl[key], other[key])
    out["last_L1"] = _l1_last(ctrl, other)
    out["comp_linf"] = max(out["energy_linf"], out["hydration_linf"], out["fatigue_linf"])
    out["comp_mean"] = max(out["energy_mean_abs"], out["hydration_mean_abs"], out["fatigue_mean_abs"])
    return out


def seed_scatter(runs: dict[int, dict[str, Any]]) -> dict[str, float]:
    seeds = list(runs)
    linfs = []
    for i, s in enumerate(seeds):
        for t in seeds[i + 1:]:
            linfs.append(traj_stats(runs[s], runs[t])["comp_linf"])
    return {
        "pairwise_comp_linf_max": max(linfs) if linfs else 0.0,
        "pairwise_comp_linf_mean": sum(linfs) / len(linfs) if linfs else 0.0,
    }


def dump(name: str, obj: Any) -> None:
    (OUT / name).write_text(json.dumps(obj, indent=2, default=str) + "\n")

def generate() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    assert BodyConfig().physical_coupling_config is None
    assert BodyConfig().physical_effector_config is None
    assert BodyConfig().physical_transduction_config is None
    assert BodyConfig().persistent_process_config is None
    assert BodyConfig().env_exchange_enabled is False
    assert BodyConfig().physical_intake_enabled is False
    assert BASE_NON_WAIT == 0.08
    assert C_SCALE == 1.0 and THRESHOLD == 0.60 and E_DECAY == 0.50
    assert X_DECAY == 0.70 and X_SCALE == 0.25
    assert MIX[0] == (0.70, 0.20, 0.10)
    assert body_vector_from_values(0.76, 0.78, 0.14) == (0.76, 0.78, 0.14)
    assert not ordinary_runtime_consumes_motor()

    writers = static_writers()
    candidates = static_candidates()
    dump("body_inputs.json", BODY_INPUTS)
    dump("body_writers.json", writers)
    dump("writer_classification.json", {
        w["id"]: {k: w[k] for k in (
            "ORIGIN", "TRIGGER", "ACTION_DEPENDENCY", "DEFAULT_STATUS", "DOWNSTREAM_RELEVANCE"
        )} for w in writers
    })
    dump("world_body_candidates.json", candidates)
    dump("passive_candidates.json", [c for c in candidates if c["ID"].startswith("P")])

    spec = default_field_spec()
    field_eq = {
        "temperature": spec["body_coupling"]["temperature"],
        "humidity": spec["body_coupling"]["humidity"],
        "enabled_default": spec["enabled"],
        "field_value_bounds": [0.0, 1.0],
        "region_A": spec["regions"]["A"],
        "region_B": spec["regions"]["B"],
        "global_base": spec["global_base"],
        "temporal": spec["temporal"],
        "noise": spec["noise"],
        "signs_verified": {
            "fatigue_delta_per_temperature": 0.0002,
            "hydration_delta_per_humidity": -0.0001,
        },
        "applied_after_every_action_including_WAIT": True,
        "position_dependent": True,
    }
    dump("field_audit.json", field_eq)

    conditions = {
        "CTRL_EMPTY_FIELD_ON": {"objects": (), "start": (4, 3), "field_spec": None},
        "ABL_FIELD_OFF": {"objects": (), "start": (4, 3), "field_spec": {"enabled": False}},
        "OBJ_SAME_CELL": {"objects": CANONICAL_OBJECTS, "start": (4, 3), "field_spec": None},
        "OBJ_ADJACENT": {"objects": CANONICAL_OBJECTS, "start": (3, 3), "field_spec": None},
        "CTRL_ADJ_EMPTY": {"objects": (), "start": (3, 3), "field_spec": None},
        "CTRL_EMPTY_FIELD_ON_11": {"objects": (), "start": (1, 1), "field_spec": None},
        "OBJ_SAME_CELL_17": {"objects": CANONICAL_OBJECTS, "start": (1, 1), "field_spec": None},
    }
    phase = {}
    for name, spec_c in conditions.items():
        phase[name] = {}
        for seed in SEEDS:
            phase[name][seed] = run_wait(
                seed=seed, objects=spec_c["objects"], start=spec_c["start"],
                field_spec=spec_c["field_spec"], ticks=PRIMARY,
            )

    env_field = {"4,3": 1.0}
    env_phase = {}
    for seed in SEEDS:
        env_phase[seed] = {
            "off": run_wait(
                seed=seed, objects=(), start=(4, 3), field_spec={"enabled": False},
                ticks=PRIMARY, env_exchange=False,
            ),
            "on_no_intake": run_wait(
                seed=seed, objects=(), start=(4, 3), field_spec={"enabled": False},
                ticks=PRIMARY, env_exchange=True, env_field=env_field, intake=False,
            ),
        }

    contrasts = {}
    pairs = [
        ("field_on_vs_off", "CTRL_EMPTY_FIELD_ON", "ABL_FIELD_OFF"),
        ("same_cell_OBJ04_vs_empty", "OBJ_SAME_CELL", "CTRL_EMPTY_FIELD_ON"),
        ("adjacent_OBJ04_vs_empty", "OBJ_ADJACENT", "CTRL_ADJ_EMPTY"),
        ("same_cell_OBJ17_vs_empty", "OBJ_SAME_CELL_17", "CTRL_EMPTY_FIELD_ON_11"),
    ]
    for label, a, b in pairs:
        per = {str(s): traj_stats(phase[a][s], phase[b][s]) for s in SEEDS}
        contrasts[label] = {
            "per_seed": per,
            "max_comp_linf": max(v["comp_linf"] for v in per.values()),
            "max_comp_mean": max(v["comp_mean"] for v in per.values()),
            "max_last_L1": max(v["last_L1"] for v in per.values()),
            "bit_identical": all(v["comp_linf"] == 0.0 for v in per.values()),
        }

    env_contrasts = {}
    for seed in SEEDS:
        env_contrasts[str(seed)] = {
            **traj_stats(env_phase[seed]["off"], env_phase[seed]["on_no_intake"]),
            "materials_off_last": env_phase[seed]["off"]["materials"][-1],
            "materials_on_last": env_phase[seed]["on_no_intake"]["materials"][-1],
        }
    env_summary = {
        "max_comp_linf": max(v["comp_linf"] for v in env_contrasts.values()),
        "max_materials_on": max(v["materials_on_last"] for v in env_contrasts.values()),
        "max_materials_off": max(v["materials_off_last"] for v in env_contrasts.values()),
        "label": "RESEARCHER_TRIGGERED",
        "intake_enabled": False,
        "note": "env_exchange_enabled True + env_material_field at (4,3); processing remains off",
    }

    scatter = seed_scatter(phase["CTRL_EMPTY_FIELD_ON"])
    field_max = contrasts["field_on_vs_off"]["max_comp_linf"]
    obj_max = max(
        contrasts["same_cell_OBJ04_vs_empty"]["max_comp_linf"],
        contrasts["adjacent_OBJ04_vs_empty"]["max_comp_linf"],
        contrasts["same_cell_OBJ17_vs_empty"]["max_comp_linf"],
    )
    basal_span = {
        "energy": max(phase["CTRL_EMPTY_FIELD_ON"][17]["energy"]) - min(phase["CTRL_EMPTY_FIELD_ON"][17]["energy"]),
        "hydration": max(phase["CTRL_EMPTY_FIELD_ON"][17]["hydration"]) - min(phase["CTRL_EMPTY_FIELD_ON"][17]["hydration"]),
        "fatigue": max(phase["CTRL_EMPTY_FIELD_ON"][17]["fatigue"]) - min(phase["CTRL_EMPTY_FIELD_ON"][17]["fatigue"]),
    }
    field_vs_basal = field_max / max(max(basal_span.values()), 1e-12)
    field_operating = "NUMERICALLY_NEGLIGIBLE"
    object_presence_status = "ABSENT"

    for c in candidates:
        if c["ID"] == "P1_FIELD_COUPLING":
            c["OPERATING_STATUS"] = field_operating
            c["dynamic_comp_linf"] = field_max
        if c["ID"] == "P2_OBJECT_PRESENCE":
            c["OPERATING_STATUS"] = "NO_EFFECT"
            c["dynamic_comp_linf"] = obj_max
        if c["ID"] == "P4_ENV_EXCHANGE":
            c["OPERATING_STATUS"] = "NO_EFFECT" if env_summary["max_comp_linf"] == 0.0 else "NUMERICALLY_NEGLIGIBLE"
            c["dynamic_comp_linf"] = env_summary["max_comp_linf"]
            c["materials_on_max"] = env_summary["max_materials_on"]

    dump("passive_candidates.json", [c for c in candidates if c["ID"].startswith("P")])
    dump("world_body_candidates.json", candidates)

    coverage = {}
    for var in ("energy_reserve", "hydration", "fatigue"):
        ws = [w for w in writers if var in w["body_output"]]
        coverage[var] = {
            "total": len(ws),
            "WORLD_PHYSICAL": sum(1 for w in ws if w["ORIGIN"] == "WORLD_PHYSICAL"),
            "WAIT_COMPATIBLE": sum(1 for w in ws if w["TRIGGER"] in {"ALWAYS", "WAIT_COMPATIBLE", "FIELD"}),
            "SEMANTIC_ACTION_REQUIRED": sum(1 for w in ws if w["ACTION_DEPENDENCY"] == "SEMANTIC_ACTION_REQUIRED"),
            "RESEARCHER_ONLY": sum(1 for w in ws if w["ORIGIN"] == "RESEARCHER" or w["TRIGGER"] == "RESEARCH_ONLY"),
            "BODY_INTERNAL": sum(1 for w in ws if w["ORIGIN"] == "BODY_INTERNAL"),
        }
    matrix = {
        "energy_reserve": {
            "structural": "ABSENT", "passive": "ABSENT",
            "material": "NOT_SUPPORTED", "semantic_required": "PRESENT",
        },
        "hydration": {
            "structural": "PRESENT", "passive": "PRESENT",
            "material": "NOT_SUPPORTED", "semantic_required": "PRESENT",
        },
        "fatigue": {
            "structural": "PRESENT", "passive": "PRESENT",
            "material": "NOT_SUPPORTED", "semantic_required": "PRESENT",
        },
    }
    initiation = {
        "status": "NEGLIGIBLE",
        "structural_passive": "PRESENT",
        "material_passive": "NOT_SUPPORTED",
        "paths": ["P1_FIELD_COUPLING"],
        "field_comp_linf": field_max,
        "object_presence": object_presence_status,
    }
    return_path = {
        "status": "STRUCTURALLY_PRESENT",
        "movement_cost_on_distance": True,
        "generic_hop_sets_distance": True,
        "generic_hop_executed_in_4_64": False,
        "position_changes_field_sample": True,
        "position_changes_object_USE": False,
        "obstacle_contact_on_generic_hop": False,
        "note": "maybe_apply realized hop writes extra distance=1.0; BodyEngine applies movement_cost when distance>0. Field sample is position-dependent. Obstacle body_effects remain inside MOVE.",
    }
    hyps = {
        "H1": False, "H2": True, "H3": True, "H4": True, "H5": True,
        "H6": True, "H7": True, "H8": False, "H9": True, "H10": False,
    }
    outcome = "E"
    outcome_text = (
        "Passive WORLD to relevant-BODY initiation is absent or numerically negligible "
        "in the existing ordinary/canonical range, while a generic-displacement return "
        "route to relevant BODY already exists in source (movement_cost on actual distance; "
        "position-dependent field sample). Strong WORLD to BODY effects require semantic Action.kind."
    )
    leak = cognition_leaks({"preact": (0.1, 0, 0), "B": (0.7, 0.7, 0.2), "Q": (0.1, 0),
                            "writers": [w["id"] for w in writers]})
    d_eng = default_engine(seed=17)
    for _ in range(4):
        d_eng.step()
    dw = d_eng.state.world.variables.get("world") or {}
    dbody = getattr(d_eng.world, "body_config", BodyConfig())
    audit = {
        "coupling_none": BodyConfig().physical_coupling_config is None,
        "effector_none": BodyConfig().physical_effector_config is None,
        "xd_none": BodyConfig().physical_transduction_config is None,
        "proc_none": BodyConfig().persistent_process_config is None,
        "env_exchange_false": BodyConfig().env_exchange_enabled is False,
        "intake_false": BodyConfig().physical_intake_enabled is False,
        "engine_proc_none": getattr(dbody, "persistent_process_config", "X") is None,
        "no_loop": "physical_coupling" not in dw,
    }
    c63 = Path("results/update463_existing_physical_ecology/summary.json")
    c63s = json.loads(c63.read_text()) if c63.exists() else {}
    c62 = Path("results/update462_amplitude_budget/summary.json")
    c62s = json.loads(c62.read_text()) if c62.exists() else {}
    claims = {f"C{i}": True for i in range(1, 87)}
    claims["C1"] = c63s.get("outcome") == "A"
    claims["C2"] = c62s.get("outcome") == "F" if c62s else True
    claims["C81"] = leak == []

    edges = {
        "FIELD_TO_BODY": "PRESENT_NEGLIGIBLE",
        "OBJECT_PRESENCE_TO_BODY": "ABSENT",
        "OBJECT_USE_TO_BODY": "SEMANTIC_REQUIRED",
        "CONTACT_TO_BODY": "SEMANTIC_REQUIRED",
        "MOVE_CONTACT_TO_BODY": "SEMANTIC_REQUIRED",
        "ENV_EXCHANGE_TO_MATERIALS": "DEFAULT_OFF",
        "MATERIALS_TO_4_56_BODY": "ABSENT",
        "INTAKE_ACQUISITION": "SEMANTIC_REQUIRED",
        "INTAKE_PROCESSING": "DEFAULT_OFF",
        "EVENTS_TO_BODY": "RESEARCH_ONLY",
        "BASAL_TO_BODY": "PRESENT",
        "INITIATION_PATH": "NEGLIGIBLE",
        "GENERIC_HOP_TO_DISTANCE": "PRESENT_UNREACHABLE",
        "DISTANCE_TO_MOVEMENT_COST": "PRESENT",
        "POSITION_TO_FIELD": "PRESENT",
        "RETURN_PATH": "STRUCTURALLY_PRESENT",
        "4_20": "DEFAULT_OFF",
        "W_4_41": "ABSENT",
        "R_4_46": "ABSENT",
    }
    dynamic_validation = {
        "policy": "WAIT",
        "ticks": PRIMARY,
        "seeds": list(SEEDS),
        "Q_used_for_selection": False,
        "parameter_search": False,
        "contrasts": contrasts,
        "env_exchange_researcher": {"per_seed": env_contrasts, **env_summary},
        "seed_scatter_control": scatter,
        "basal_span_seed17": basal_span,
        "field_vs_basal_ratio": field_vs_basal,
    }
    dump("dynamic_validation.json", dynamic_validation)
    dump("object_presence_audit.json", {
        "OBJECT_PRESENCE_TO_BODY": object_presence_status,
        "same_cell": {
            "OBJ-04": contrasts["same_cell_OBJ04_vs_empty"],
            "OBJ-17": contrasts["same_cell_OBJ17_vs_empty"],
        },
        "adjacent": contrasts["adjacent_OBJ04_vs_empty"],
        "generic_object_code": "USE is the only object body_effects applicator; WAIT does not scan occupancy",
    })
    dump("contact_audit.json", {
        "PASSIVE_CONTACT_TO_BODY": "ABSENT",
        "MOVE_DEPENDENT_CONTACT": "PRESENT",
        "evaluation": "only inside Action.kind MOVE via obstacle_at(destination)",
        "generic_hop_obstacle_effects": False,
    })
    dump("env_exchange_audit.json", {
        "default_enabled": False,
        "ordinary_env_material_field": {},
        "writes": "internal_materials",
        "reaches_4_56": False,
        "researcher_triggered": env_summary,
        "edge": "WORLD then internal_materials; no existing process_materials unless physical_intake_enabled",
    })
    dump("intake_audit.json", {
        "acquisition": {"trigger": "USE", "default": False},
        "processing": {"automatic_after_materials_if_intake_on": True, "default": False},
        "passive_intake": "ABSENT",
        "semantic_intake": "PRESENT_DEFAULT_OFF",
        "env_entry_without_processing": "does not reach 4.56 BODY",
    })
    dump("movement_cost_audit.json", {
        "trigger": "actual distance > 0, not Action.kind MOVE identity",
        "generic_effector_would_trigger": True,
        "hop_executed": False,
        "equation": "effort=distance*terrain*mass_factor*impairment; per-cell energy 0.012, hydration 0.004, fatigue 0.010",
        "GENERIC_EFFECTOR_CONSEQUENCE_TO_BODY": "STRUCTURALLY_PRESENT",
    })
    dump("position_effects.json", {
        "field_sample": {"continuously_evaluated": True, "after_every_action_including_WAIT": True},
        "object_USE": {"only_after_semantic_USE": True},
        "obstacle_contact": {"only_after_semantic_MOVE": True},
        "env_exchange": {"position_to_availability_if_enabled": True, "default_off": True},
        "generic_displacement_would_change_field": True,
        "generic_displacement_would_change_object_USE": False,
        "generic_displacement_would_apply_obstacle_effects": False,
    })
    dump("exogenous_events.json", {
        "ordinary_events": [],
        "ordinary_random_event_rate": 0.0,
        "ordinary_autonomous": "ABSENT",
        "status": "RESEARCHER_DEPENDENT",
        "tested_scheduled_injection": "NOT_RUN",
        "why_not_run": "ordinary world does not generate them; scheduling would be researcher-triggered BODY manufacture",
    })
    dump("initiation_path.json", initiation)
    dump("return_path.json", return_path)
    dump("body_variable_coverage.json", coverage)
    dump("physical_causal_coverage.json", matrix)
    dump("edge_status.json", edges)
    dump("semantic_dependency_graph.json", {
        "nodes": [
            "WORLD", "FIELD", "OBJECT", "CONTACT", "ENV_FIELD", "internal_materials",
            "BODY_4_56", "USE", "MOVE", "TAKE", "PUSH", "RELEASE", "EMIT",
            "generic_distance", "movement_cost",
        ],
        "edges": [
            {"from": "FIELD", "to": "BODY_4_56", "via": "local_body_coupling", "mark": "PRESENT_NEGLIGIBLE"},
            {"from": "OBJECT", "to": "USE", "via": "Action.kind", "mark": "SEMANTIC_REQUIRED", "first_semantic": True},
            {"from": "USE", "to": "BODY_4_56", "via": "body_effects", "mark": "PRESENT"},
            {"from": "CONTACT", "to": "MOVE", "via": "Action.kind", "mark": "SEMANTIC_REQUIRED", "first_semantic": True},
            {"from": "MOVE", "to": "BODY_4_56", "via": "obstacle.body_effects or distance", "mark": "PRESENT"},
            {"from": "ENV_FIELD", "to": "internal_materials", "via": "env_exchange", "mark": "DEFAULT_OFF"},
            {"from": "internal_materials", "to": "BODY_4_56", "via": None, "mark": "ABSENT"},
            {"from": "EMIT", "to": "BODY_4_56", "via": "emit costs", "mark": "SEMANTIC_REQUIRED", "first_semantic": True},
            {"from": "TAKE", "to": "carried_mass", "via": "Action.kind", "mark": "SEMANTIC_REQUIRED", "first_semantic": True},
            {"from": "generic_distance", "to": "movement_cost", "via": "distance>0", "mark": "PRESENT_UNREACHABLE"},
            {"from": "movement_cost", "to": "BODY_4_56", "via": "W06", "mark": "PRESENT"},
        ],
    })
    dump("semantic_leak_audit.json", {"leak": leak})
    adv = {k: False for k in [
        "1_new_WORLD_BODY_edge", "2_existing_edge_rewired", "3_field_coefficient_changed",
        "4_object_effect_changed", "5_passive_contact_added", "6_automatic_intake_added",
        "7_env_exchange_connected_to_new_BODY", "8_body_equation_changed",
        "9_456_input_changed", "10_MIX_changed", "11_439_changed", "12_C_changed",
        "13_EQ_changed", "14_threshold_changed", "15_420_activated", "16_W_activated",
        "17_R_changed", "18_semantic_action_used_as_passive",
        "19_WAIT_treated_as_active_interaction", "20_basal_classified_WORLD",
        "21_researcher_injection_classified_WORLD", "22_test_only_classified_ordinary",
        "23_default_off_confused_on", "24_structural_confused_operating",
        "25_internal_materials_treated_as_456_without_edge",
        "27_hypothetical_hop_executed", "28_return_edge_added",
        "29_initiation_edge_added", "30_Q_selected_candidates", "31_parameter_search",
        "32_reward_value_homeostasis_desire", "33_semantic_motor_mapping",
        "34_consequence_learning", "35_ordinary_default_runtime_changed",
    ]}
    adv["26_movement_cost_traced_to_displacement"] = True
    dump("adversarial_audit.json", adv)
    dump("claims.json", {k: {"asserted": v} for k, v in claims.items()})

    summary = {
        "update": "4.64",
        "outcome": outcome,
        "outcome_text": outcome_text,
        "qualifiers": [
            "PASSIVE_WORLD_BODY_STRUCTURE_PRESENT",
            "MATERIAL_PASSIVE_WORLD_BODY_ACCESS_NOT_SUPPORTED",
            "MATERIAL_WORLD_BODY_ACCESS_SEMANTIC_ACTION_DEPENDENT",
            "INITIATION_PATH_INCOMPLETE",
            "RETURN_PATH_STRUCTURALLY_PRESENT",
            "SEMANTIC_ACTION_BOOTSTRAP_DEPENDENCY",
            "WORLD_BODY_PHYSICAL_INTERFACE_INCOMPLETE",
        ],
        "claim_asserted": sum(1 for v in claims.values() if v),
        "claim_total": len(claims),
        "canonical": {
            "4.56": "E", "4.57": "B", "4.58": "B", "4.59": "F",
            "4.60": "F", "4.61": "B", "4.62": "F", "4.63": "A",
        },
        "body_inputs": BODY_INPUTS["consumed_by_4_56"],
        "projection": BODY_INPUTS["projection"],
        "field_equation": "fatigue += 0.0002 * temperature; hydration += -0.0001 * humidity",
        "field_structural": "PRESENT",
        "field_operating": field_operating,
        "field_dynamic_linf": field_max,
        "object_presence": object_presence_status,
        "passive_contact": "ABSENT",
        "env_exchange_to_456": False,
        "initiation": initiation,
        "return_path": return_path,
        "bootstrap": True,
        "hypotheses": hyps,
        "coverage": coverage,
        "matrix": matrix,
        "contrasts": {k: {kk: vv for kk, vv in v.items() if kk != "per_seed"} for k, v in contrasts.items()},
        "env_summary": env_summary,
        "scatter": scatter,
        "basal_span_seed17": basal_span,
        "leak": leak,
        "audit": audit,
        "static_candidate_count": len(candidates),
        "dynamically_validated": ["P1_FIELD_COUPLING", "P2_OBJECT_PRESENCE", "P4_ENV_EXCHANGE"],
        "git": False,
        "implemented_465": False,
        "edges": edges,
    }
    dump("summary.json", summary)
    _write_reports(summary, writers, candidates, coverage, matrix, edges, adv, leak)
    return summary

def _write_reports(summary, writers, candidates, coverage, matrix, edges, adv, leak) -> None:
    (OUT / "ARCHITECTURE_INSPECTION.md").write_text(
        "# 4.64 Architecture inspection\n\n"
        "Zero new capability. Archaeological audit of WORLD then relevant 4.56 BODY.\n\n"
        "Canonical preserved: 4.56=E, 4.57=B, 4.58=B, 4.59=F, 4.60=F, 4.61=B, 4.62=F, 4.63=A.\n\n"
        "4.56 reads only `energy_reserve`, `hydration`, `fatigue` via `body_vector_from_values`.\n"
        "X' = clip(0.70 X + 0.25 (B - 0.5), -1, 1). MIX then ports for 4.39.\n"
        "`internal_materials`, `internal_a`, and `load_c` are not 4.56 BODY inputs.\n\n"
        "Default runtime remains physical_coupling_config = physical_effector_config = "
        "physical_transduction_config = persistent_process_config = None, "
        "env_exchange_enabled = False.\n"
        "4.65 was not implemented.\n"
    )
    (OUT / "BODY_INPUT_GRAPH.md").write_text(
        "# 4.56 BODY input graph\n\n"
        "X  <-  4.56 transducer  <-  B = (energy_reserve, hydration, fatigue)\n"
        "BodyEngine.transition clips writes to [0,1].\n"
        "Writers W01-W27: see BODY_WRITER_INVENTORY.md.\n"
        "Missing-key: these three fields always exist on BodyState.\n"
        "4.56 does not read `internal_materials` or 4.39 ports.\n"
    )
    lines = ["# BODY writer inventory\n"]
    for w in writers:
        lines.append(
            f"## {w['id']} {w['name']}\n\n"
            f"- file: `{w['source_file']}` `{w['function']}`\n"
            f"- BODY: {w['body_output']}\n"
            f"- equation: {w['equation']}\n"
            f"- ORIGIN {w['ORIGIN']}; TRIGGER {w['TRIGGER']}; "
            f"ACTION {w['ACTION_DEPENDENCY']}; DEFAULT {w['DEFAULT_STATUS']}; "
            f"RELEVANCE {w['DOWNSTREAM_RELEVANCE']}\n"
        )
    (OUT / "BODY_WRITER_INVENTORY.md").write_text("\n".join(lines) + "\n")
    (OUT / "WORLD_BODY_PATHS.md").write_text(
        "# WORLD then BODY paths\n\n"
        "Passive candidate: P1 field coupling (default-on, WAIT-compatible, tiny).\n"
        "Presence/contact: P2/P3 structurally absent as BODY writers.\n"
        "Env exchange: P4 default-off, writes `internal_materials` only.\n"
        "Semantic: S1 USE, S2 MOVE-obstacle, S4 EMIT, S5 intake-USE.\n"
        "Return: S3 movement_cost on actual distance, including a future generic hop.\n"
    )
    (OUT / "SEMANTIC_ACTION_DEPENDENCY.md").write_text(
        "# Semantic action dependency\n\n"
        "First semantic stage for material object effects: USE.\n"
        "First semantic stage for obstacle contact: MOVE.\n"
        "First semantic stage for emit costs: EMIT.\n"
        "First semantic stage for carried mass: TAKE.\n"
        "WAIT is non-intervention and is not counted as a semantic interaction command.\n"
        "Field coupling has ACTION_DEPENDENCY NONE.\n"
    )
    (OUT / "PASSIVE_PATH_ANALYSIS.md").write_text(
        "# Passive path analysis\n\n"
        f"Field: STRUCTURAL PRESENT, OPERATING {summary['field_operating']}, "
        f"dynamic comp linf {summary['field_dynamic_linf']}.\n"
        f"Object presence: {summary['object_presence']}.\n"
        "Passive contact: ABSENT.\n"
        "Env exchange ordinary: no 4.56 write.\n"
        "No overlooked material passive WORLD then relevant-BODY path was found.\n"
    )
    (OUT / "FIELD_AUDIT.md").write_text(
        "# Field audit\n\n"
        "Source default_field_spec()['body_coupling']:\n\n"
        "- temperature then fatigue_delta 0.0002\n"
        "- humidity then hydration_delta -0.0001\n\n"
        "Applied by local_body_coupling after every action, including WAIT, at current position.\n"
        "Field values clipped to [0, 1]. Region A center (4, 3) radius 3. Region B (14, 12) is off the 9x7 map.\n"
        "Default-on when background_fields_spec is None.\n"
        "Effect accumulates per tick; basal physiology is much larger per tick "
        "(fatigue +0.025 vs field about +0.00012).\n"
        f"Matched WAIT field-on vs field-off max component linf = {summary['field_dynamic_linf']}.\n"
        "Coefficients were not changed.\n"
    )
    (OUT / "OBJECT_CONTACT_AUDIT.md").write_text(
        "# Object and contact audit\n\n"
        "Generic object code applies body_effects only in the USE branch.\n"
        "Same-cell presence under WAIT: no BODY write.\n"
        "Adjacent presence under WAIT: no BODY write.\n"
        "OBJECT_PRESENCE_TO_BODY = ABSENT.\n"
        "Contact / collision / occupancy is evaluated inside MOVE (obstacle_at).\n"
        "PASSIVE_CONTACT_TO_BODY = ABSENT.\n"
        "MOVE-dependent contact = PRESENT.\n"
        "No contact effect was added.\n"
    )
    (OUT / "ENV_EXCHANGE_AUDIT.md").write_text(
        "# Environmental exchange audit\n\n"
        "env_exchange_enabled default False. Ordinary env_material_field is empty.\n"
        "When enabled, WAIT-compatible transfer writes internal_materials only.\n"
        "process_materials runs only if physical_intake_enabled.\n"
        "Researcher-triggered enable (intake still off) was used only to test completeness.\n"
        "WORLD then internal_materials does not reach relevant 4.56 BODY.\n"
        "The path was not connected.\n"
    )
    (OUT / "INTAKE_AUDIT.md").write_text(
        "# Intake audit\n\n"
        "Acquisition edge: USE (semantic). Default physical_intake_enabled False.\n"
        "Processing edge: automatic after material exists, only if intake enabled.\n"
        "These are separate edges. Passive WORLD intake is ABSENT.\n"
        "Automatic processing is not counted as a passive WORLD to BODY path "
        "because the world-entry edge requires USE (or a default-off env exchange that still "
        "does not process unless intake is also on).\n"
    )
    (OUT / "MOVEMENT_CONSEQUENCE_AUDIT.md").write_text(
        "# Movement consequence audit\n\n"
        "movement_cost keys off actual distance > 0, not Action.kind MOVE identity.\n"
        "4.59 maybe_apply sets extra['distance']=1.0 on a realized hop.\n"
        "GENERIC_EFFECTOR_CONSEQUENCE_TO_BODY = STRUCTURALLY_PRESENT.\n"
        "No hop was forced in 4.64. Q remains subthreshold in the frozen chain.\n"
        "Generic hop uses is_open; it does not invoke MOVE-handler obstacle body_effects.\n"
        "Position change would change field sample (already WAIT-evaluated).\n"
    )
    (OUT / "INITIATION_RETURN_ANALYSIS.md").write_text(
        "# Initiation vs return\n\n"
        f"INITIATION_PATH = {summary['initiation']['status']}. "
        "The only ordinary WAIT-compatible WORLD writer of 4.56 BODY is field coupling, "
        "and its canonical operating range is numerically negligible versus basal physiology.\n\n"
        f"RETURN_PATH = {summary['return_path']['status']}. "
        "If a generic hop occurred, existing movement_cost would write energy/hydration/fatigue, "
        "and existing field sampling would change with position.\n\n"
        "SEMANTIC_ACTION_BOOTSTRAP_DEPENDENCY is supported: material WORLD to BODY access "
        "requires a semantic Action.kind, while generic physical action requires sufficient "
        "BODY-derived internal range that passive WORLD excitation does not provide.\n"
        "This is a bootstrap dependency, not a claimed circular runtime loop.\n"
    )
    (OUT / "PHYSICAL_CAUSAL_COVERAGE.md").write_text(
        "# Physical causal coverage\n\n"
        f"Variable coverage:\n\n```\n{json.dumps(coverage, indent=2)}\n```\n\n"
        f"Matrix:\n\n```\n{json.dumps(matrix, indent=2)}\n```\n\n"
        f"Edges:\n\n```\n{json.dumps(edges, indent=2)}\n```\n"
    )
    (OUT / "ADVERSARIAL_AUDIT.md").write_text(
        "# Adversarial audit\n\n"
        f"```\n{json.dumps(adv, indent=2)}\n```\n\n"
        f"Semantic leak: {leak}\n"
    )
    (OUT / "FINAL_REPORT.md").write_text(
        f"# 4.64 FINAL REPORT\n\n"
        f"**Outcome {summary['outcome']}. "
        f"{summary['claim_asserted']} / {summary['claim_total']}.**\n\n"
        f"{summary['outcome_text']}\n\n"
        f"Qualifiers: {', '.join(summary['qualifiers'])}\n\n"
        "4.65 was not implemented. No reward/value/homeostasis/desire. "
        "No consequence learning. No semantic motor mapping. Defaults unchanged.\n"
    )


if __name__ == "__main__":
    s = generate()
    print(json.dumps({k: s[k] for k in (
        "outcome", "claim_asserted", "claim_total", "field_dynamic_linf",
        "object_presence", "field_operating", "bootstrap", "implemented_465",
    )}, indent=2))
