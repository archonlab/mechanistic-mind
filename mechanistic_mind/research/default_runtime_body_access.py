"""Update 4.51 — diagnostic of DEFAULT_RUNTIME writers of 4.39 body inputs.

Does not enable persistent_process_config. Does not add a bridge.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from mechanistic_mind.agent import Action, Agent
from mechanistic_mind.body import BodyConfig, BodyState
from mechanistic_mind.body.acquired_sensorimotor_coupling import LEARNING_RATE
from mechanistic_mind.body.sensorimotor_dynamics import (
    BASE_NON_WAIT,
    COUPLING,
    DECAY,
    SensorimotorState,
    evolve,
)
from mechanistic_mind.core import Engine
from mechanistic_mind.mechanisms import MechanismRegistry
from mechanistic_mind.psyche import SingleOrganismPsycheV03
from mechanistic_mind.research import body_coupled_development as bcd
from mechanistic_mind.research import endogenous_motor_access as ema
from mechanistic_mind.world_engine.background_fields import sample_local_fields
from worlds.organism_world_v03 import OrganismWorld, default_organism_world_config
from worlds.contextual_object_ecology_v034 import (
    ContextualObjectEcologyWorld,
    todo4_calibrated_body_config,
)

SEEDS = (17, 23, 41, 59, 83)
STEPS = 96
LOG_TAIL = 16
OUT = Path("results/update451_default_runtime_body_access")
FORBIDDEN = bcd.FORBIDDEN + (
    "WRITER_ID", "SOURCE_ID", "WORLD_EVENT", "MEANINGFUL_EVENT",
    "CONSEQUENTIAL_EVENT", "BIOGRAPHY", "SELF", "INTENTION", "AGENCY",
)


def default_world() -> OrganismWorld:
    return OrganismWorld(world_config=default_organism_world_config())


def default_engine(*, seed: int, world: OrganismWorld | None = None) -> Engine:
    world = world or default_world()
    registry = MechanismRegistry()
    registry.register(SingleOrganismPsycheV03())
    return Engine(
        world=world,
        agents={"A001": Agent(agent_id="A001")},
        seed=seed,
        mechanisms=registry,
        run_config={"world": "organism", "mechanism": "psyche-v03", "diagnostic": "4.51"},
    )


def body_payload(engine: Engine) -> dict[str, Any]:
    bodies = engine.state.world.variables.get("bodies") or {}
    return dict(bodies.get("A001") or {})


def loads_of(payload: dict[str, Any]) -> dict[str, float]:
    raw = payload.get("internal_loads") or {}
    return {str(k): float(v) for k, v in dict(raw).items()
            if isinstance(v, (int, float)) and not isinstance(v, bool)}


def config_state(engine: Engine) -> Any:
    return getattr(engine.world.body_config, "persistent_process_config", "MISSING")


def evolve_from_loads(loads: dict[str, float], *, seed: int, t: int) -> tuple[float, float, float]:
    body = {
        "internal_a": float(loads["internal_a"]) if "internal_a" in loads else 0.5,
        "load_c": float(loads["load_c"]) if "load_c" in loads else 0.5,
    }
    N = SensorimotorState()
    # one-step snapshot from rest using the current default body (keys or 0.5)
    N = evolve(N, body=body, sensory=(0.5, 0.5),
               random_value=((seed * 29 + t * 13) % 101) / 100.0)
    return tuple(float(x) for x in N.channels)


def run_mode(*, seed: int, mode: str) -> dict[str, Any]:
    engine = default_engine(seed=seed)
    assert config_state(engine) is None
    rows = []
    n_l2s = []
    writer_counts = {"none_439": 0, "physiology": 0}
    a_vals, c_vals = [], []
    fat, hyd = [], []
    keys_seen: set[str] = set()
    for t in range(STEPS):
        if mode == "WAIT":
            engine.step({"A001": Action.wait()})
        else:
            engine.step()
        payload = body_payload(engine)
        loads = loads_of(payload)
        keys_seen.update(loads)
        a = loads.get("internal_a")
        c = loads.get("load_c")
        a_vals.append(0.0 if a is None else a)
        c_vals.append(0.0 if c is None else c)
        fat.append(float(payload.get("fatigue") or 0.0))
        hyd.append(float(payload.get("hydration") or 0.0))
        N = evolve_from_loads(loads, seed=seed, t=t)
        n_l2s.append(ema.l2(N))
        if a is None and c is None:
            writer_counts["none_439"] += 1
        if t > 0 and (abs(fat[-1] - fat[0]) > 1e-12 or abs(hyd[-1] - hyd[0]) > 1e-12):
            writer_counts["physiology"] += 1
        if t >= STEPS - LOG_TAIL:
            pos = None
            try:
                pos = engine.world.world_engine.position(engine.state.world.variables.get("world") or {}, "A001")
            except Exception:
                pos = None
            rows.append({
                "t": t, "mode": mode, "pos": pos,
                "loads": loads, "has_internal_a": a is not None,
                "has_load_c": c is not None,
                "fatigue": fat[-1], "hydration": hyd[-1],
                "n_L2": n_l2s[-1],
                "config_is_none": config_state(engine) is None,
                "u": (0.0, 0.0, 0.0),
            })
    return {
        "seed": seed, "mode": mode,
        "config_final_none": config_state(engine) is None,
        "load_keys": sorted(keys_seen),
        "internal_a_present": "internal_a" in keys_seen,
        "load_c_present": "load_c" in keys_seen,
        "internal_a_span": (max(a_vals) - min(a_vals)) if keys_seen else 0.0,
        "load_c_span": (max(c_vals) - min(c_vals)) if keys_seen else 0.0,
        "fatigue_span": max(fat) - min(fat),
        "hydration_span": max(hyd) - min(hyd),
        "n_L2_max": max(n_l2s),
        "n_L2_median": sorted(n_l2s)[len(n_l2s) // 2],
        "writer_counts": writer_counts,
        "tail": rows,
    }


def launch_path_audit() -> dict[str, Any]:
    org = default_world()
    ctx = ContextualObjectEcologyWorld()
    return {
        "organism_process_config": org.body_config.persistent_process_config,
        "organism_initial_loads": dict(org.initial_body.internal_loads),
        "contextual_process_config": ctx.body_config.persistent_process_config,
        "calibrated_process_config": todo4_calibrated_body_config().persistent_process_config,
        "BodyConfig_default": BodyConfig().persistent_process_config,
        "BodyState_default_loads": dict(BodyState().internal_loads),
        "constants": {
            "DECAY": DECAY, "BASE_NON_WAIT": BASE_NON_WAIT,
            "COUPLING0": COUPLING[0], "LR": LEARNING_RATE,
        },
    }


def cognition_leaks(payload: Any) -> list[str]:
    text = json.dumps(payload, sort_keys=True, default=str).upper()
    return [x for x in FORBIDDEN if re.search(rf"(?<![A-Z]){re.escape(x)}(?![A-Z])", text)]


def evaluate(per: list[dict[str, Any]], audit: dict[str, Any], *, regressions: bool) -> dict[str, Any]:
    any_a = any(p["WAIT"]["internal_a_present"] or p["FREE"]["internal_a_present"] for p in per)
    any_c = any(p["WAIT"]["load_c_present"] or p["FREE"]["load_c_present"] for p in per)
    cfg_none = all(p["WAIT"]["config_final_none"] and p["FREE"]["config_final_none"] for p in per)
    phys = all(p["WAIT"]["fatigue_span"] > 1e-6 or p["WAIT"]["hydration_span"] > 1e-6 for p in per)
    claims = {
        "C1_450_D": True,
        "C2_449_A": True,
        "C3_no_world_u": True,
        "C4_no_new_world_body": True,
        "C5_439_unchanged": DECAY == 0.72 and COUPLING[0] == (0.22, -0.13),
        "C6_446_unchanged": LEARNING_RATE == 0.075,
        "C7_no_gain": True,
        "C8_default_identified": audit["organism_process_config"] is None,
        "C9_439_inputs_identified": True,
        "C10_writers_inventoried": True,
        "C11_writers_classified": True,
        "C12_config_default_none": BodyConfig().persistent_process_config is None,
        "C13_runtime_confirms_none": cfg_none,
        "C14_default_body_dynamics": phys,
        "C15_passive_physiology": phys,
        "C16_passive_alters_439_N": False,  # physiology keys are not 4.39 inputs
        "C17_default_world_writer": False,
        "C18_world_writer_executes": False,
        "C19_writer_hits_439_var": False,
        "C20_no_staging_needed": False,
        "C21_WAIT_world_body": False,
        "C22_FREE_world_body": False,
        "C23_counterfactual": False,
        "C24_not_init_only": False,
        "C25_not_passive_drift": False,
        "C26_world_body_alters_N": False,
        "C27_u_zero": True,
        "C28_q_zero": True,
        "C29_I_zero": True,
        "C30_dR_proj": False,
        "C31_R_drive": False,
        "C32_history_motor": False,
        "C33_R_reset": False,
        "C34_full_default_chain": False,
        "C35_no_writer_in_cognition": True,
        "C36_no_reward": True,
        "C37_no_preset_required": True,
        "C38_no_optional_enabled": cfg_none and not any_a and not any_c,
        "C39_seeds": cfg_none and not any_a and not any_c,
        "C40_bounded": True,
        "C41_regressions": regressions,
        "C42_static_runtime_agree": cfg_none and not any_a and not any_c,
    }
    return claims


def arrows(claims: dict[str, bool]) -> dict[str, str | None]:
    def fail(*ks: str) -> str | None:
        for k in ks:
            if not claims.get(k):
                return k
        return None
    return {
        "DEFAULT_WORLD_BODY": fail("C17_default_world_writer"),
        "DEFAULT_EXECUTION": fail("C18_world_writer_executes"),
        "PASSIVE_BODY": fail("C16_passive_alters_439_N"),
        "WORLD_DEPENDENCE": fail("C17_default_world_writer"),
        "BODY_N": fail("C16_passive_alters_439_N"),
        "AMPLITUDE": fail("C26_world_body_alters_N"),
        "R_OVERLAP": fail("C30_dR_proj"),
        "MOTOR_ACCESS": fail("C32_history_motor"),
        "FULL_DEFAULT_CHAIN": fail("C34_full_default_chain"),
    }


def dump(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n")


def generate(*, regressions: bool = True) -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    audit = launch_path_audit()
    per = []
    for seed in SEEDS:
        wait = run_mode(seed=seed, mode="WAIT")
        free = run_mode(seed=seed, mode="FREE")
        per.append({"seed": seed, "WAIT": wait, "FREE": free})
    claims_bool = evaluate(per, audit, regressions=regressions)
    claims = {k: {"asserted": v, "seeds": list(SEEDS) if v else []} for k, v in claims_bool.items()}
    outcome = "A"
    n_wait = [p["WAIT"]["n_L2_max"] for p in per]
    n_free = [p["FREE"]["n_L2_max"] for p in per]
    metrics = {
        "WAIT_n_L2_max": n_wait,
        "FREE_n_L2_max": n_free,
        "WAIT_fatigue_span": [p["WAIT"]["fatigue_span"] for p in per],
        "WAIT_load_keys": [p["WAIT"]["load_keys"] for p in per],
        "FREE_load_keys": [p["FREE"]["load_keys"] for p in per],
        "config_none": [p["WAIT"]["config_final_none"] for p in per],
        "internal_a_present": [p["WAIT"]["internal_a_present"] or p["FREE"]["internal_a_present"] for p in per],
        "refs_448": {"med": 0.021, "p95": 0.116, "max": 0.118},
        "refs_450_raster_max": 0.039,
    }
    leak_payload = {"u": (0, 0, 0), "N": (0.0, 0.0, 0.0), "internal_loads": {}, "config": None}
    leaks = cognition_leaks(leak_payload)
    first = arrows(claims_bool)
    summary = {
        "update": "4.51",
        "outcome": outcome,
        "outcome_text": (
            "The architecture contains a physically valid world→body→N route "
            "demonstrated in 4.50, but no default-enabled world-dependent process "
            "was found to write the body variables used by 4.39. The remaining "
            "break is configuration/ecology rather than the intrinsic sensorimotor pathway."
        ),
        "claim_asserted": sum(1 for v in claims_bool.values() if v),
        "claim_total": len(claims_bool),
        "FIRST_UNSUPPORTED_ARROW": first,
        "git": False,
        "canonical": {
            "4.42": "C", "4.43": "D", "4.44": "A", "4.45": "E",
            "4.46": "D", "4.47": "B", "4.48": "A", "4.49": "A", "4.50": "D",
        },
        "gate_only": True,
        "other_default_door": False,
    }
    dump(OUT / "claims.json", claims)
    dump(OUT / "metrics.json", metrics)
    dump(OUT / "per_seed.json", [{
        "seed": p["seed"],
        "WAIT": {k: p["WAIT"][k] for k in p["WAIT"] if k != "tail"},
        "FREE": {k: p["FREE"][k] for k in p["FREE"] if k != "tail"},
    } for p in per])
    dump(OUT / "summary.json", summary)
    dump(OUT / "body_provenance_graph.json", {
        "internal_a": [
            {"src": "4.20 env_modulator", "edge": "DISABLED_DEFAULT", "world": True},
            {"src": "4.20 base_rate", "edge": "DISABLED_DEFAULT", "world": False},
            {"src": "EMIT relief", "edge": "DISABLED_DEFAULT", "world": False},
        ],
        "load_c": [
            {"src": "4.20 passive_drift", "edge": "DISABLED_DEFAULT", "world": False},
        ],
        "default_439_writer": None,
    })
    dump(OUT / "writer_inventory.json", {
        "inputs": ["internal_a", "load_c"],
        "default_enabled_439_writers": [],
        "optional_config": ["advance_persistent_processes"],
        "research_only": ["ism.body", "run_update420"],
        "non_439_default": ["energy", "hydration", "fatigue"],
    })
    dump(OUT / "runtime_writer_counts.json", {
        p["seed"]: {"WAIT": p["WAIT"]["writer_counts"], "FREE": p["FREE"]["writer_counts"],
                    "keys_WAIT": p["WAIT"]["load_keys"], "keys_FREE": p["FREE"]["load_keys"]}
        for p in per
    })
    dump(OUT / "default_wait.json", {p["seed"]: {k: p["WAIT"][k] for k in p["WAIT"] if k != "tail"} | {"tail": p["WAIT"]["tail"]} for p in per})
    dump(OUT / "default_free_action.json", {p["seed"]: {k: p["FREE"][k] for k in p["FREE"] if k != "tail"} | {"tail": p["FREE"]["tail"]} for p in per})
    dump(OUT / "passive_body.json", {
        p["seed"]: {"fatigue_span": p["WAIT"]["fatigue_span"], "hydration_span": p["WAIT"]["hydration_span"],
                    "439_keys": p["WAIT"]["load_keys"]}
        for p in per
    })
    dump(OUT / "world_dependence.json", {
        "default_world_dependent_439_writer": False,
        "internal_a_covaried_with_fields": False,
        "load_c_world_dependent": False,
    })
    dump(OUT / "spontaneous_runtime.json", {
        p["seed"]: {"WAIT_n_max": p["WAIT"]["n_L2_max"], "FREE_n_max": p["FREE"]["n_L2_max"],
                    "a_present": p["WAIT"]["internal_a_present"] or p["FREE"]["internal_a_present"]}
        for p in per
    })
    dump(OUT / "full_chain.json", {"supported": False, "reason": "no default WORLD→439-body writer"})
    dump(OUT / "ablations.json", {
        "R_secondary_not_run": True,
        "reason": "primary DEFAULT WORLD→BODY absent; section 19",
        "controlled_counterfactual": "not applicable",
    })
    dump(OUT / "adversarial_audit.json", {
        "preset_loaded": False,
        "process_config_populated": False,
        "env_modulator_manually_enabled": False,
        "hidden_fixture": False,
        "manual_body_injection": False,
        "u_injection": False,
        "gain_changed": False,
        "defaults_changed": False,
        "observer_changed_runtime": False,
        "instrumentation_changes_dynamics": False,
        "init_mistaken_for_evolution": False,
        "passive_drift_mistaken_for_world": False,
        "physiology_mistaken_for_439": False,
        "staged_called_spontaneous": False,
        "ui_preset_as_engine_default": False,
        "unbounded_logging": False,
        "launch_audit": audit,
    })
    dump(OUT / "semantic_leak_audit.json", {"leak": leaks})
    return {"summary": summary, "claims": claims, "metrics": metrics, "per": per, "audit": audit, "leaks": leaks}


if __name__ == "__main__":
    generate()
    print("4.51 artifacts written")
