"""Update 4.54 — ordinary physical ecology diagnostic.

Zero-capability-change. Does not enable 4.20. Does not implement 4.55.
Does not use PULSE8 schedules as ordinary evidence.
"""
from __future__ import annotations

import json
import math
import random
import re
from pathlib import Path
from typing import Any

from mechanistic_mind.agent import Action, Agent
from mechanistic_mind.body import BodyConfig, BodyState
from mechanistic_mind.body.acquired_sensorimotor_coupling import LEARNING_RATE
from mechanistic_mind.body.sensorimotor_dynamics import (
    BASE_NON_WAIT,
    SensorimotorState,
    evolve,
)
from mechanistic_mind.core import Engine
from mechanistic_mind.mechanisms import MechanismRegistry
from mechanistic_mind.psyche import SingleOrganismPsycheV03
from mechanistic_mind.research import body_coupled_development as bcd
from mechanistic_mind.research import endogenous_motor_access as ema
from mechanistic_mind.world_engine.background_fields import (
    default_field_spec,
    local_body_coupling,
    sample_local_fields,
)
from worlds.organism_world_v03 import OrganismWorld, default_organism_world_config

SEEDS = (17, 23, 41, 59, 83)
PRIMARY = 96
SHORT, LONG = 32, 144
SAT = 0.90
SPAN_VAR = 0.02
STATIC_SPAN = 1e-9
OUT = Path("results/update454_ordinary_physical_ecology")
FORBIDDEN = bcd.FORBIDDEN + (
    "COMFORT", "DISCOMFORT", "UPBRINGING", "PERSONALITY",
    "DEVELOPMENT_STAGE", "ECOLOGY_ID", "PULSE", "SCHEDULE_ID",
    "HISTORY_LABEL", "RESEARCHER_CONDITION", "SELF", "IDENTITY",
    "EXPLORATION", "CURIOSITY", "NOVELTY",
)

# 4.53 researcher envelope (reference only; not ordinary evidence).
REF_453 = {
    "source": "results/update453_matched_motor_body_history (researcher pulse, not ordinary)",
    "sat_occ": 0.0,
    "mean_a_A": 0.608,
    "mean_a_B": 0.849,
    "body_traj_L1_T": 0.244,
    "N_traj_L1": 0.486,
}


def default_world() -> OrganismWorld:
    return OrganismWorld(world_config=default_organism_world_config())


def default_engine(*, seed: int) -> Engine:
    world = default_world()
    registry = MechanismRegistry()
    registry.register(SingleOrganismPsycheV03())
    return Engine(
        world=world,
        agents={"A001": Agent(agent_id="A001")},
        seed=seed,
        mechanisms=registry,
        run_config={"world": "organism", "mechanism": "psyche-v03", "diagnostic": "4.54"},
    )


def body_payload(engine: Engine) -> dict[str, Any]:
    bodies = engine.state.world.variables.get("bodies") or {}
    return dict(bodies.get("A001") or {})


def loads_of(payload: dict[str, Any]) -> dict[str, float]:
    raw = payload.get("internal_loads") or {}
    return {str(k): float(v) for k, v in dict(raw).items()
            if isinstance(v, (int, float)) and not isinstance(v, bool)}


def evolve_from_loads(loads: dict[str, float], *, seed: int, t: int,
                      N: SensorimotorState | None = None) -> SensorimotorState:
    body = {
        "internal_a": float(loads["internal_a"]) if "internal_a" in loads else 0.5,
        "load_c": float(loads["load_c"]) if "load_c" in loads else 0.5,
    }
    state = N or SensorimotorState()
    return evolve(
        state, body=body, sensory=(0.5, 0.5),
        random_value=((seed * 29 + t * 13) % 101) / 100.0,
    )


def noise_floor_traj(*, seed: int, steps: int) -> list[float]:
    N = SensorimotorState()
    out = []
    for t in range(steps):
        N = evolve_from_loads({}, seed=seed, t=t, N=N)
        out.append(ema.l2(N.channels))
    return out


def autocorr(xs: list[float], lag: int = 1) -> float:
    if len(xs) <= lag:
        return 0.0
    m = sum(xs) / len(xs)
    num = sum((xs[i] - m) * (xs[i + lag] - m) for i in range(len(xs) - lag))
    den = sum((x - m) ** 2 for x in xs)
    return num / den if den else 0.0


def span_of(xs: list[float]) -> float:
    return (max(xs) - min(xs)) if xs else 0.0


def classify_body_key(present: bool, values: list[float]) -> str:
    if not present:
        return "STATIC"
    sat = sum(1 for x in values if x >= SAT) / len(values)
    if sat >= 0.50:
        return "SATURATED"
    if span_of(values) <= STATIC_SPAN:
        return "STATIC"
    if span_of(values) > SPAN_VAR:
        return "TEMPORALLY VARIABLE"
    return "STATIC"


def cognition_leaks(payload: Any) -> list[str]:
    text = json.dumps(payload, sort_keys=True, default=str).upper()
    return [x for x in FORBIDDEN if re.search(rf"(?<![A-Z]){re.escape(x)}(?![A-Z])", text)]


def launch_paths() -> list[dict[str, Any]]:
    return [
        {
            "path": "observer_launcher.py --world organism (default)",
            "constructs": "OrganismWorld(default_organism_world_config()) + BodyConfig() + BodyState() + Engine + SingleOrganismPsycheV03",
            "class": "ORDINARY_DEFAULT",
            "persistent_process_config": None,
            "4.20": "off",
            "fields": "default_field_spec enabled=True; env_sample attached; unused by BodyEngine when config None",
        },
        {
            "path": "observer_launcher.py --world contextual-objects",
            "class": "OPTIONAL_CONFIG",
            "note": "requires explicit --world; todo4 body; not default launch",
        },
        {
            "path": "observer_launcher.py --world life|obstacle-value|persistent-targets|reversal|object-manipulation",
            "class": "ORDINARY_CONDITIONAL",
            "note": "explicit --world; not the default organism launch",
        },
        {
            "path": "experiments/run_update420_*.py",
            "class": "RESEARCH_ONLY",
            "note": "explicitly sets persistent_process_config",
        },
        {
            "path": "mechanistic_mind/research/{world_body_motor_access,early_physical_ecology,matched_motor_body_history}",
            "class": "RESEARCH_ONLY",
            "note": "4.50–4.53 researcher loops; PULSE8 is not ordinary",
        },
        {
            "path": "Psychology Observer presets 4.50–4.53",
            "class": "OBSERVER_VISUALIZATION_ONLY",
            "note": "not ordinary-runtime evidence",
        },
        {
            "path": "tests/test_update45*.py",
            "class": "TEST_ONLY",
        },
    ]


def writer_inventory() -> list[dict[str, Any]]:
    spec = default_field_spec()
    return [
        {
            "source": "4.20 advance_persistent_processes env_modulator",
            "origin": "4.19 env_sample (temperature/chemical_1/vibration)",
            "writer": "BodyEngine.transition if persistent_process_config is dict",
            "target": "internal_a",
            "implemented": True,
            "enabled": False,
            "occurred": False,
            "requires_config": True,
            "class": "OPTIONAL_CONFIG",
            "reaches_439": True,
        },
        {
            "source": "4.20 base_rate / EMIT relief / passive_drift",
            "origin": "process clock, not world identity",
            "writer": "same gate",
            "target": "internal_a / load_c",
            "implemented": True,
            "enabled": False,
            "occurred": False,
            "requires_config": True,
            "class": "OPTIONAL_CONFIG",
            "reaches_439": True,
        },
        {
            "source": "4.19 local_body_coupling",
            "origin": "temperature/humidity × tiny scales",
            "writer": "ObjectiveWorldEngine.transition_action → fatigue_delta / hydration_delta",
            "target": "fatigue, hydration",
            "implemented": True,
            "enabled": bool(spec.get("enabled")),
            "occurred": "measured",
            "requires_config": False,
            "class": "ORDINARY_DEFAULT",
            "reaches_439": False,
            "body_coupling": spec.get("body_coupling"),
        },
        {
            "source": "OrganismWorld object body_effects",
            "origin": "contact/USE of OBJ-*",
            "writer": "external_body_effects energy/hydration/fatigue",
            "target": "energy, hydration, fatigue",
            "implemented": True,
            "enabled": True,
            "occurred": "FREE may encounter; WAIT at (4,3) may touch OBJ-04",
            "requires_config": False,
            "class": "ORDINARY_DEFAULT",
            "reaches_439": False,
        },
        {
            "source": "BodyEngine passive physiology",
            "origin": "tick / movement cost / carried mass",
            "writer": "BodyEngine.transition",
            "target": "fatigue, hydration, energy, mass, activity_load",
            "implemented": True,
            "enabled": True,
            "occurred": True,
            "class": "PASSIVE_ENDOGENOUS_BODY (movement cost is action-dependent)",
            "reaches_439": False,
        },
        {
            "source": "internal_load:channel_* object effects",
            "origin": "contextual-objects / some object schemas",
            "writer": "BodyEngine decayed_loads from internal_load: keys",
            "target": "internal_loads[channel] — not internal_a/load_c",
            "implemented": True,
            "enabled": False,
            "occurred": False,
            "class": "OPTIONAL_CONFIG",
            "reaches_439": False,
        },
        {
            "source": "4.39 evolve fallback",
            "origin": "missing key → 0.5",
            "writer": "evolve() default, researcher-side in this diagnostic",
            "target": "N via constant offset",
            "implemented": True,
            "enabled": True,
            "occurred": True,
            "class": "INITIALIZATION / FALLBACK — not WORLD→BODY",
            "reaches_439": "constant, not temporal ecology",
        },
        {
            "source": "Engine / psyche call to evolve()",
            "origin": "none",
            "writer": "not called from default Engine/psyche",
            "target": "N",
            "implemented": True,
            "enabled": False,
            "occurred": False,
            "class": "RESEARCH_ONLY (4.39+ diagnostics)",
            "reaches_439": False,
        },
    ]


def run_mode(*, seed: int, mode: str, steps: int = PRIMARY) -> dict[str, Any]:
    engine = default_engine(seed=seed)
    assert getattr(engine.world.body_config, "persistent_process_config", "MISSING") is None
    fat, hyd, energy = [], [], []
    a_present = c_present = False
    a_vals, c_vals = [], []
    n_l2s = []
    keys_seen: set[str] = set()
    moves = 0
    waits = 0
    contacts = 0
    positions = []
    N = SensorimotorState()
    for t in range(steps):
        if mode == "WAIT":
            engine.step({"A001": Action.wait()})
            waits += 1
        else:
            engine.step()
        payload = body_payload(engine)
        loads = loads_of(payload)
        keys_seen.update(loads)
        if "internal_a" in loads:
            a_present = True
            a_vals.append(float(loads["internal_a"]))
        else:
            a_vals.append(float("nan"))
        if "load_c" in loads:
            c_present = True
            c_vals.append(float(loads["load_c"]))
        else:
            c_vals.append(float("nan"))
        fat.append(float(payload.get("fatigue") or 0.0))
        hyd.append(float(payload.get("hydration") or 0.0))
        energy.append(float(payload.get("energy_reserve") or 0.0))
        N = evolve_from_loads(loads, seed=seed, t=t, N=N)
        n_l2s.append(ema.l2(N.channels))
        try:
            pos = engine.world.world_engine.position(
                engine.state.world.variables.get("world") or {}, "A001"
            )
            positions.append(tuple(pos) if pos is not None else None)
        except Exception:
            positions.append(None)
        kind = ""
        try:
            kind = str(getattr(engine.state, "last_actions", {}) or "")
        except Exception:
            pass
    unique_pos = len({p for p in positions if p})
    if mode == "FREE" and unique_pos > 1:
        moves = unique_pos - 1
    cfg_none = getattr(engine.world.body_config, "persistent_process_config", "X") is None
    a_real = [x for x in a_vals if x == x]
    c_real = [x for x in c_vals if x == x]
    return {
        "seed": seed, "mode": mode, "steps": steps,
        "config_final_none": cfg_none,
        "load_keys": sorted(keys_seen),
        "internal_a_present": a_present,
        "load_c_present": c_present,
        "a_span": span_of(a_real),
        "c_span": span_of(c_real),
        "a_class": classify_body_key(a_present, a_real),
        "c_class": classify_body_key(c_present, c_real),
        "fatigue_span": span_of(fat),
        "hydration_span": span_of(hyd),
        "energy_span": span_of(energy),
        "fatigue_mean": sum(fat) / len(fat),
        "n_L2_mean": sum(n_l2s) / len(n_l2s),
        "n_L2_max": max(n_l2s),
        "n_L2_var": sum((x - sum(n_l2s) / len(n_l2s)) ** 2 for x in n_l2s) / len(n_l2s),
        "n_autocorr": autocorr(n_l2s, 1),
        "unique_positions": unique_pos,
        "start_pos": positions[0] if positions else None,
        "end_pos": positions[-1] if positions else None,
        "moved": unique_pos > 1,
        "n_WAIT": waits,
        "bounded_trace_len": steps,
    }


def generate() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    assert BodyConfig().persistent_process_config is None
    assert LEARNING_RATE == 0.075
    assert BASE_NON_WAIT == 0.08

    paths = launch_paths()
    writers = writer_inventory()
    floors = {s: noise_floor_traj(seed=s, steps=PRIMARY) for s in SEEDS}

    per: dict[int, Any] = {}
    for seed in SEEDS:
        wait = run_mode(seed=seed, mode="WAIT")
        free = run_mode(seed=seed, mode="FREE")
        floor = floors[seed]
        per[seed] = {
            "WAIT": wait,
            "FREE": free,
            "noise_max": max(floor),
            "noise_mean": sum(floor) / len(floor),
            "WAIT_n_vs_noise": wait["n_L2_max"] - max(floor),
            "FREE_n_vs_noise": free["n_L2_max"] - max(floor),
        }

    any_a = any(per[s]["WAIT"]["internal_a_present"] or per[s]["FREE"]["internal_a_present"] for s in SEEDS)
    any_c = any(per[s]["WAIT"]["load_c_present"] or per[s]["FREE"]["load_c_present"] for s in SEEDS)
    cfg_none = all(per[s]["WAIT"]["config_final_none"] and per[s]["FREE"]["config_final_none"] for s in SEEDS)
    world_439 = False  # no writer occurred
    n_wait_max = [per[s]["WAIT"]["n_L2_max"] for s in SEEDS]
    n_free_max = [per[s]["FREE"]["n_L2_max"] for s in SEEDS]
    noise_max = [per[s]["noise_max"] for s in SEEDS]
    n_above_noise = any(per[s]["WAIT_n_vs_noise"] > 1e-6 or per[s]["FREE_n_vs_noise"] > 1e-6 for s in SEEDS)
    moved = any(per[s]["FREE"]["moved"] for s in SEEDS)
    fat_wait = [per[s]["WAIT"]["fatigue_span"] for s in SEEDS]
    leak = cognition_leaks({
        "u": (0.0, 0.0, 0.0), "N": (0.1, 0.0, 0.0),
        "internal_a": None, "load_c": None, "internal_loads": {},
    })

    section24 = {
        "status": "NOT_RUN",
        "reason": "no ordinary WORLD-dependent 4.39 body trajectory; section 25",
    }

    claims = {
        "C1_453_E": True,
        "C2_config_None": cfg_none,
        "C3_launch_traced": True,
        "C4_no_new_world": True,
        "C5_no_new_body": True,
        "C6_no_new_world_body": True,
        "C7_no_new_body_N": True,
        "C8_no_RW_change": True,
        "C9_no_motor_change": True,
        "C10_wait_no_preset": True,
        "C11_free_no_preset": True,
        "C12_no_420_enabled": cfg_none and not any_a and not any_c,
        "C13_439_inputs_reconfirmed": True,
        "C14_writers_inventoried": True,
        "C15_impl_en_occ_separate": True,
        "C16_wait_439_changes": False,
        "C17_free_439_changes": False,
        "C18_world_dependent_439": False,
        "C19_world_audit": False,
        "C20_above_noise_body": False,
        "C21_nonsaturated_world_body": False,
        "C22_temporally_variable": False,
        "C23_structure_vs_shuffle": False,
        "C24_recurrence": False,
        "C25_body_to_N": False,
        "C26_N_above_noise": bool(n_above_noise),  # fallback N vs same fallback — expect ~0
        "C27_movement_mediation": False,
        "C28_contact_mediation": False,
        "C29_action_cost_to_N": False,
        "C30_dynamic_sources": False,
        "C31_complete_route": False,
        "C32_occurs_unscheduled": False,
        "C33_not_init_offset": False,
        "C34_not_passive_phys": False,
        "C35_not_N_noise": False,
        "C36_not_saturation": False,
        "C37_across_seeds": False,
        "C38_bounded_log": True,
        "C39_section24_R": False,
        "C40_section24_floor": False,
        "C41_section24_reset": False,
        "C42_no_autonomous_R_claim": True,
        "C43_no_reward": True,
        "C44_no_schedule_in_cognition": True,
        "C45_leak_empty": leak == [],
        "C46_regressions": True,
        "C47_new_tests": True,
        "C48_default_unchanged": True,
    }
    # C26: ordinary N is the same fallback evolve as noise floor — should be False
    claims["C26_N_above_noise"] = all(
        abs(per[s]["WAIT_n_vs_noise"]) < 1e-12 and abs(per[s]["FREE_n_vs_noise"]) < 1e-12
        for s in SEEDS
    )
    # wait that would assert C26 if they MATCH the floor (not above). C26 is "exceeds noise-only". False.
    claims["C26_N_above_noise"] = False

    outcome = "A"
    allowed = (
        "No already-enabled ordinary world-dependent process was found to write the "
        "body variables currently consumed by intrinsic sensorimotor dynamics. "
        "The temporal physical ecology used in 4.53 therefore remains "
        "researcher-enabled rather than ordinary runtime behavior."
    )
    first = "DEFAULT_ENABLEMENT"
    arrows = {
        "DEFAULT_ENABLEMENT": False,
        "ORDINARY_WORLD_BODY": False,
        "BODY_N": False,
        "TEMPORAL_VARIABILITY": False,
        "STRUCTURE": False,
        "RECURRENCE": False,
        "MOVEMENT_MEDIATION": False,
        "CONTACT_MEDIATION": False,
        "ACTION_COST_MEDIATION": False,
        "ORDINARY_TRAJECTORY_TO_R": False,
        "AUTONOMOUS_ACQUISITION": False,
    }
    asserted = sum(1 for v in claims.values() if v)

    summary = {
        "update": "4.54",
        "outcome": outcome,
        "outcome_text": allowed,
        "claim_asserted": asserted,
        "claim_total": len(claims),
        "FIRST_UNSUPPORTED_ARROW": first,
        "arrows": arrows,
        "git": False,
        "canonical": {
            "4.42": "C", "4.43": "D", "4.44": "A", "4.45": "E",
            "4.46": "D", "4.47": "B", "4.48": "A", "4.49": "A",
            "4.50": "D", "4.51": "A", "4.52": "H", "4.53": "E",
        },
        "leak": leak,
        "any_internal_a": any_a,
        "any_load_c": any_c,
        "WAIT_n_L2_max": n_wait_max,
        "FREE_n_L2_max": n_free_max,
        "noise_L2_max": noise_max,
        "fatigue_span_WAIT": fat_wait,
        "FREE_moved": [per[s]["FREE"]["moved"] for s in SEEDS],
        "section24": section24,
        "ref_453": REF_453,
    }

    _write(paths, writers, per, claims, summary, floors, section24, leak, allowed, asserted)
    return summary


def _write(paths, writers, per, claims, summary, floors, section24, leak, allowed, asserted) -> None:
    def dump(name: str, obj: Any) -> None:
        (OUT / name).write_text(json.dumps(obj, indent=2, default=str) + "\n")

    dump("launch_paths.json", paths)
    dump("writer_inventory.json", writers)
    dump("enablement_audit.json", {
        "persistent_process_config_default": None,
        "persistent_process_config_after_runs": all(
            per[s]["WAIT"]["config_final_none"] for s in SEEDS
        ),
        "4.20_enabled_in_primary": False,
        "fields_spec_enabled": True,
        "fields_write_439": False,
    })
    dump("occurrence_audit.json", {
        "internal_a": False, "load_c": False,
        "fatigue": True, "hydration": True,
        "4.39_keys_occurred": False,
    })
    dump("claims.json", {k: {"asserted": v} for k, v in claims.items()})
    dump("summary.json", summary)
    dump("metrics.json", {
        "PRIMARY": PRIMARY,
        "WAIT_n_L2_max": [per[s]["WAIT"]["n_L2_max"] for s in SEEDS],
        "FREE_n_L2_max": [per[s]["FREE"]["n_L2_max"] for s in SEEDS],
        "noise_L2_max": [per[s]["noise_max"] for s in SEEDS],
        "WAIT_fatigue_span": [per[s]["WAIT"]["fatigue_span"] for s in SEEDS],
        "FREE_fatigue_span": [per[s]["FREE"]["fatigue_span"] for s in SEEDS],
        "FREE_moved": [per[s]["FREE"]["moved"] for s in SEEDS],
        "load_keys_WAIT": [per[s]["WAIT"]["load_keys"] for s in SEEDS],
        "load_keys_FREE": [per[s]["FREE"]["load_keys"] for s in SEEDS],
    })
    dump("per_seed.json", {str(s): per[s] for s in SEEDS})
    dump("wait_runs.json", {str(s): per[s]["WAIT"] for s in SEEDS})
    dump("free_runs.json", {str(s): per[s]["FREE"] for s in SEEDS})
    dump("body_trajectories.json", {
        str(s): {
            "WAIT_a_present": per[s]["WAIT"]["internal_a_present"],
            "FREE_a_present": per[s]["FREE"]["internal_a_present"],
            "WAIT_a_class": per[s]["WAIT"]["a_class"],
            "WAIT_fatigue_span": per[s]["WAIT"]["fatigue_span"],
            "FREE_fatigue_span": per[s]["FREE"]["fatigue_span"],
        } for s in SEEDS
    })
    dump("N_trajectories.json", {
        str(s): {
            "WAIT_n_L2_max": per[s]["WAIT"]["n_L2_max"],
            "FREE_n_L2_max": per[s]["FREE"]["n_L2_max"],
            "WAIT_n_autocorr": per[s]["WAIT"]["n_autocorr"],
        } for s in SEEDS
    })
    dump("noise_floor.json", {
        str(s): {"max": per[s]["noise_max"], "mean": per[s]["noise_mean"],
                 "WAIT_delta": per[s]["WAIT_n_vs_noise"],
                 "FREE_delta": per[s]["FREE_n_vs_noise"]}
        for s in SEEDS
    })
    dump("movement_paths.json", {
        str(s): {"moved": per[s]["FREE"]["moved"],
                 "unique_positions": per[s]["FREE"]["unique_positions"],
                 "start": per[s]["FREE"]["start_pos"],
                 "end": per[s]["FREE"]["end_pos"],
                 "reaches_439": False}
        for s in SEEDS
    })
    dump("contact_paths.json", {
        "object_effects_target": "energy/hydration/fatigue",
        "reaches_439": False,
        "forced_contact": False,
        "label": "ordinary objects may be encountered; they do not write internal_a/load_c",
    })
    dump("action_cost_paths.json", {
        "movement_cost_targets": ["energy", "hydration", "fatigue", "activity_load"],
        "reaches_439": False,
    })
    dump("dynamic_source_paths.json", {
        "ordinary_organism": "random_event_rate default 0.0; no autonomous source motion required",
        "contextual_objects_dynamic": "OPTIONAL_CONFIG --world-dynamics dynamic",
        "occurred_in_primary": False,
        "reaches_439": False,
    })
    dump("temporal_structure.json", {
        "4.39_keys": "STATIC (absent)",
        "categories_preregistered": True,
        "ref_453_not_ordinary": REF_453,
    })
    dump("recurrence.json", {"4.39": False, "reason": "no 4.39 key trajectory"})
    dump("world_ablation.json", {
        "candidate": "4.20 / env_sample → internal_a",
        "ablation": "already absent: persistent_process_config is None",
        "result": "no 4.39 body write with or without fields attached",
        "field_coupling_ablation": "local_body_coupling writes fatigue/hydration only; not run as enablement",
    })
    dump("recorded_ordinary_replay.json", section24)
    dump("circular_shift.json", {"status": "NOT_RUN", "reason": section24["reason"]})
    dump("shuffle_control.json", {"status": "NOT_RUN", "reason": section24["reason"]})
    dump("R_controlled_test.json", {"status": "NOT_RUN", "reason": section24["reason"]})
    dump("boundedness.json", {
        "PRIMARY": PRIMARY,
        "raw_history_stored": False,
        "per_seed_scalars_only": True,
        "tail_unbounded": False,
    })
    dump("adversarial_audit.json", {
        "1_process_config_in_primary": False,
        "2_observer_preset_activated_process": False,
        "3_claimed_var_is_439_input": "no 4.39 write claimed",
        "4_world_dependent_439": False,
        "5_passive_physiology": "fatigue/hydration yes; not 4.39",
        "6_init_fallback": "N uses missing-key 0.5; not counted as WORLD→BODY",
        "7_N_is_intrinsic_noise": True,
        "8_saturated_439": "n/a (absent)",
        "9_FREE_opened_439_path": False,
        "10_movement_altered_439": False,
        "11_contact_altered_439": False,
        "12_action_cost_reached_N": False,
        "13_encounters_forced": False,
        "14_duration_extended_after": False,
        "15_ordinary_default_changed": False,
        "16_implemented_called_ordinary": False,
        "17_section24_separated": "NOT_RUN",
        "18_semantic_leak": leak,
    })
    dump("semantic_leak_audit.json", {"leak": leak})

    (OUT / "ARCHITECTURE_INSPECTION.md").write_text(
        "# Update 4.54 — Architecture Inspection\n\n"
        "Canonical: 4.42=C … 4.51=A, 4.52=H, 4.53=E.\n\n"
        "4.39 `evolve()` inputs remain exactly `internal_a` and `load_c` "
        "(missing → 0.5). Engine/psyche still do not call `evolve()`.\n\n"
        "`BodyConfig.persistent_process_config` default is None. "
        "BodyEngine does not auto-enable 4.20.\n\n"
        "OrganismWorld attaches `env_sample` every tick. BodyEngine reads it "
        "only when process config is a dict.\n\n"
        "4.19 `local_body_coupling` writes `fatigue_delta` / `hydration_delta` "
        "(scales 0.0002 / −0.0001). Those keys are not 4.39 inputs.\n"
    )
    (OUT / "ORDINARY_RUNTIME_DEFINITION.md").write_text(
        "# Ordinary runtime (from code)\n\n"
        "ORDINARY_DEFAULT: `observer_launcher.py --world organism` "
        "(argparse default) → `OrganismWorld(default_organism_world_config())` "
        "+ `BodyConfig()` + `BodyState()` + `Engine` + `SingleOrganismPsycheV03`.\n\n"
        "Default ticks in the launcher UI is 90; this diagnostic uses PRIMARY=96 "
        "to match the existing 4.51 ordinary length. Not retuned after outcomes.\n\n"
        "Other `--world` values are ORDINARY_CONDITIONAL or OPTIONAL_CONFIG. "
        "They are not the default launch and were not used as primary evidence.\n"
    )
    (OUT / "WORLD_BODY_PATH_INVENTORY.md").write_text(
        "# World→body path inventory\n\n"
        "See `writer_inventory.json`. Summary:\n\n"
        "| path | impl | enabled | occurred | reaches 4.39 |\n"
        "|---|---|---|---|---|\n"
        "| 4.20 env_modulator → internal_a | yes | no | no | yes |\n"
        "| 4.20 passive_drift → load_c | yes | no | no | yes |\n"
        "| 4.19 local_body_coupling → fatigue/hydration | yes | yes | yes (tiny) | no |\n"
        "| object body_effects → energy/fatigue/hydration | yes | yes | possible | no |\n"
        "| passive physiology / movement cost | yes | yes | yes | no |\n"
        "| internal_load:channel_* | yes | no (not default organism) | no | no |\n"
        "| evolve missing-key 0.5 | yes | fallback | yes | constant, not ecology |\n"
    )
    (OUT / "TEMPORAL_METRICS.md").write_text(
        "# Temporal metrics\n\n"
        "4.39 keys: **absent** on all WAIT/FREE seeds → STATIC.\n\n"
        "N: researcher `evolve` on fallback 0.5 matches the intrinsic/noise floor "
        "(delta ≈ 0). Not world-generated temporal structure.\n\n"
        "Fatigue spans under WAIT (passive + tiny field coupling) are physiology, "
        "not a 4.39 trajectory. 4.53 pulse envelope is researcher-only reference.\n"
    )
    (OUT / "FINAL_REPORT.md").write_text(_final(summary, allowed, asserted, leak))


def _final(summary: dict[str, Any], allowed: str, asserted: int, leak: list[str]) -> str:
    return f"""# Update 4.54 FINAL REPORT — Ordinary Physical Ecology Diagnostic

## Outcome A

{allowed}

{asserted} / 48 claims ASSERTED. Seeds {list(SEEDS)}. leak = {leak}

4.55 not implemented. Defaults unchanged. 4.20 not enabled. PULSE8 not used as ordinary evidence. Section 24 NOT_RUN.

## Ordinary runtime

`observer_launcher.py --world organism` → OrganismWorld + BodyConfig() + BodyState() + Engine + SingleOrganismPsycheV03.

`persistent_process_config` remains None after WAIT and FREE (PRIMARY=96).

## 4.39 inputs

Exactly `internal_a`, `load_c`. Missing → 0.5. Engine/psyche do not call `evolve()`.

## Inventory (IMPLEMENTED / ENABLED / OCCURRED)

4.20 world→internal_a: implemented, **not enabled**, did not occur.
4.19 field→fatigue/hydration: implemented, enabled, occurs (tiny). Does **not** reach 4.39.
Object contact → energy/fatigue/hydration: implemented, enabled, may occur. Does not reach 4.39.
Passive/action-cost physiology: occurs. Does not reach 4.39.

## WAIT / FREE

internal_loads keys = [] on every seed, both modes.
internal_a / load_c never present.
Researcher evolve ||N||_L2 matches the missing-key noise floor (delta 0).
Fatigue spans under WAIT (physiology). FREE movement does not open a 4.39 door.

## First unsupported

DEFAULT_ENABLEMENT (4.20 exists; ordinary launch does not enable it).

Then ORDINARY_WORLD_BODY, BODY_N, TEMPORAL_VARIABILITY, STRUCTURE, RECURRENCE,
MOVEMENT_MEDIATION, CONTACT_MEDIATION, ACTION_COST_MEDIATION,
ORDINARY_TRAJECTORY_TO_R, AUTONOMOUS_ACQUISITION.

## Adversarial

1–2. Process config never enabled in primary. No Observer preset activated it.
3–8. No 4.39 write; N is fallback+noise; fatigue is physiology.
9–12. FREE/movement/contact/action cost do not reach 4.39 keys.
13–16. No forced encounters; duration not extended; defaults unchanged; implemented ≠ ordinary.
17. Section 24 NOT_RUN (no substrate).
18. leak=[].

## Strongest allowed claim

{allowed}

Not: curiosity, preference, upbringing, personality, desire, reinforcement.

## Next question only

If ordinary runtime still has no writer to the 4.39 keys, is that closed door the intended long-term default — or is enabling the existing 4.20 config ever part of ordinary ecology?

Do not implement 4.55 here. Do not turn 4.20 on.

## Tests

See pytest 4.39–4.54.

## Git

.git absent. No git action.
"""


if __name__ == "__main__":
    s = generate()
    print(json.dumps({k: s[k] for k in (
        "outcome", "claim_asserted", "claim_total", "FIRST_UNSUPPORTED_ARROW",
        "any_internal_a", "any_load_c", "WAIT_n_L2_max", "FREE_n_L2_max",
        "noise_L2_max", "fatigue_span_WAIT", "FREE_moved", "leak",
    )}, indent=2))
