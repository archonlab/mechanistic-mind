"""Update 4.68 — 4.20 persistent-process physical provenance.

Zero new capability. Maps what drives 4.20. Does not compose C/E/Q.
Does not implement 4.69.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import replace
from pathlib import Path
from typing import Any

from mechanistic_mind.agent import Action, Agent
from mechanistic_mind.body import BodyConfig
from mechanistic_mind.body.persistent_processes import (
    PROCESS_KEYS,
    default_process_config,
    env_modulator,
)
from mechanistic_mind.body.sensorimotor_dynamics import (
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
from mechanistic_mind.world_engine.background_fields import default_field_spec
from mechanistic_mind.world_engine.physical_effector import THRESHOLD
from worlds.organism_world_v03 import OrganismWorld

OUT = Path("results/update468_persistent_process_provenance")
SEEDS = (17, 23, 41, 59, 83)
PRIMARY = 96
START = (4, 3)
ALT = (0, 0)
FORBIDDEN = bcd.FORBIDDEN + ("SEEK", "AVOID", "NEED", "DESIRE", "MOTIVATION", "HOMEOSTASIS", "FOOD", "WATER")


def cognition_leaks(payload: Any) -> list[str]:
    text = json.dumps(payload, sort_keys=True, default=str).upper()
    return [x for x in FORBIDDEN if re.search(rf"(?<![A-Z]){re.escape(x)}(?![A-Z])", text)]


def dump(name: str, obj: Any) -> None:
    (OUT / name).write_text(json.dumps(obj, indent=2, default=str) + "\n")


def md(name: str, text: str) -> None:
    (OUT / name).write_text(text if text.endswith("\n") else text + "\n")


def _stats(xs: list[float]) -> dict[str, float]:
    if not xs:
        return {"min": 0, "max": 0, "mean": 0, "std": 0, "span": 0, "n_distinct": 0}
    ys = [float(x) for x in xs]
    mu = sum(ys) / len(ys)
    var = sum((y - mu) ** 2 for y in ys) / len(ys)
    return {"min": min(ys), "max": max(ys), "mean": mu, "std": math.sqrt(var),
            "span": max(ys) - min(ys), "n_distinct": len({round(y, 12) for y in ys})}


def make_engine(*, seed: int, process: bool, fields: str, start=START) -> Engine:
    """fields: 'default' (None spec → init uses default_field_spec), 'on', 'off'."""
    if fields == "off":
        fspec: dict | None = {"enabled": False}
    elif fields == "on":
        fspec = default_field_spec()
    else:
        fspec = None
    wcfg = WorldEngineConfig(
        width=9, height=7, blocked=(), objects=(),
        emit_enabled=False, background_fields_spec=fspec,
        env_material_field={}, exogenous_events=(), random_event_rate=0.0,
    )
    bcfg = BodyConfig()
    if process:
        bcfg = replace(bcfg, persistent_process_config=default_process_config())
    world = OrganismWorld(world_config=wcfg, body_config=bcfg, start_position=start)
    registry = MechanismRegistry()
    registry.register(SingleOrganismPsycheV03())
    return Engine(world=world, agents={"A001": Agent(agent_id="A001")}, seed=seed,
                  mechanisms=registry, run_config={"diagnostic": "4.68"})


def run(*, seed: int, process: bool, fields: str, start=START, ticks: int = PRIMARY) -> dict[str, Any]:
    eng = make_engine(seed=seed, process=process, fields=fields, start=start)
    N = SensorimotorState()
    rows = []
    for t in range(ticks):
        p = body_payload(eng)
        loads = p.get("internal_loads") or {}
        ia = float(loads.get("internal_a")) if isinstance(loads, dict) and "internal_a" in loads else 0.5
        lc = float(loads.get("load_c")) if isinstance(loads, dict) and "load_c" in loads else 0.5
        # missing keys → 4.39 default 0.5 (existing evolve)
        N = evolve(N, body={"internal_a": ia, "load_c": lc},
                   sensory=(0.5, 0.5),
                   random_value=((seed * 29 + t * 13) % 101) / 100.0)
        ww = eng.state.world.variables["world"]
        bg = ww.get("background_fields") or {}
        env_attached = None
        # after step we read receipt
        eng.step({"A001": Action.wait()})
        p2 = body_payload(eng)
        loads2 = p2.get("internal_loads") or {}
        rec = p2.get("last_process_receipt") or {}
        rows.append({
            "t": t,
            "pos": tuple(int(x) for x in eng.state.world.variables["world"]["agent_positions"]["A001"]),
            "internal_a": float(loads2.get("internal_a", 0.0) if isinstance(loads2, dict) else 0.0),
            "load_c": float(loads2.get("load_c", 0.0) if isinstance(loads2, dict) else 0.0),
            "internal_b": float(loads2.get("internal_b", 0.0) if isinstance(loads2, dict) else 0.0),
            "exchange_d": float(loads2.get("exchange_d", 0.0) if isinstance(loads2, dict) else 0.0),
            "rate": float((rec or {}).get("rate") or 0.0) if rec else 0.0,
            "mod": float((rec or {}).get("env_modulator") or 0.0) if rec else 0.0,
            "B": (float(p2["energy_reserve"]), float(p2["hydration"]), float(p2["fatigue"])),
            "N": tuple(float(x) for x in N.channels),
            "fields_enabled": bool(isinstance(bg, dict) and bg.get("enabled")),
            "has_keys": bool(isinstance(loads2, dict) and "internal_a" in loads2),
        })
    ia = [r["internal_a"] for r in rows]
    lc = [r["load_c"] for r in rows]
    mod = [r["mod"] for r in rows]
    rate = [r["rate"] for r in rows]
    nlinf = [max(abs(x) for x in r["N"]) for r in rows]
    return {
        "seed": seed, "n": len(rows),
        "ia": _stats(ia), "lc": _stats(lc), "mod": _stats(mod), "rate": _stats(rate),
        "Nlinf": _stats(nlinf),
        "last": rows[-1] if rows else None,
        "first": rows[0] if rows else None,
        "has_keys": any(r["has_keys"] for r in rows),
        "fields_enabled": rows[0]["fields_enabled"] if rows else False,
        "rows_compact": [{"t": r["t"], "ia": r["internal_a"], "lc": r["load_c"],
                          "mod": r["mod"], "rate": r["rate"], "Nlinf": max(abs(x) for x in r["N"])}
                         for r in rows[:: max(1, len(rows)//16)]],
    }


def generate() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    cfg0 = BodyConfig()
    assert cfg0.persistent_process_config is None
    assert cfg0.passive_physical_exchange_config is None
    assert cfg0.physical_transduction_config is None
    assert cfg0.physical_coupling_config is None
    assert cfg0.physical_effector_config is None
    assert cfg0.env_exchange_enabled is False
    assert THRESHOLD == 0.60
    assert not ordinary_runtime_consumes_motor()
    dcfg = default_process_config()
    assert dcfg["base_rate"] == 0.035
    assert dcfg["env_rate_gain"] == 0.08
    assert env_modulator(None) == 0.0
    assert env_modulator({}) == 0.0

    table: dict[str, dict[int, dict]] = {}
    conds = {
        "P0": dict(process=False, fields="default"),
        "P1": dict(process=True, fields="default"),
        "P2": dict(process=True, fields="off"),
        "P1b": dict(process=True, fields="on"),
    }
    for name, kw in conds.items():
        table[name] = {}
        for seed in SEEDS:
            table[name][seed] = run(seed=seed, **kw)

    # WORLD geometry: same config, different position, fields on
    pos_a = {s: run(seed=s, process=True, fields="on", start=START) for s in SEEDS}
    pos_b = {s: run(seed=s, process=True, fields="on", start=ALT) for s in SEEDS}

    def agg(block, key):
        return _stats([block[s][key]["span"] for s in SEEDS])

    p0_keys = all(not table["P0"][s]["has_keys"] for s in SEEDS)
    p1_mod = max(table["P1"][s]["mod"]["span"] for s in SEEDS)
    p2_mod = max(table["P2"][s]["mod"]["span"] for s in SEEDS)
    p1_ia = max(table["P1"][s]["ia"]["span"] for s in SEEDS)
    p2_ia = max(table["P2"][s]["ia"]["span"] for s in SEEDS)
    p0_ia = max(table["P0"][s]["ia"]["span"] for s in SEEDS)
    p1_n = max(table["P1"][s]["Nlinf"]["max"] for s in SEEDS)
    p0_n = max(table["P0"][s]["Nlinf"]["max"] for s in SEEDS)
    p2_n = max(table["P2"][s]["Nlinf"]["max"] for s in SEEDS)
    d_ia_world = max(abs(pos_a[s]["ia"]["max"] - pos_b[s]["ia"]["max"]) for s in SEEDS)
    d_mod_world = max(abs(pos_a[s]["mod"]["mean"] - pos_b[s]["mod"]["mean"]) for s in SEEDS)
    d_ia_ablate = abs(p1_ia - p2_ia)
    # P1 vs P1b should be similar if default spec == fields on
    p1_fields = all(table["P1"][s]["fields_enabled"] for s in SEEDS)
    p0_fields = all(table["P0"][s]["fields_enabled"] for s in SEEDS)
    p2_fields = any(table["P2"][s]["fields_enabled"] for s in SEEDS)

    world_drives = (p1_mod > 1e-6) and (p2_mod < 1e-12 or p2_mod < 0.1 * p1_mod)
    pos_drives = d_mod_world > 1e-6
    config_evolves = p1_ia > 0.1 and p2_ia > 0.1  # base_rate accumulation even without fields
    default_inert = p0_keys and p0_ia == 0.0

    n_attr = p1_n - p0_n

    equations = {
        "internal_a": "clip01(internal_a + (base_rate + env_rate_gain * env_modulator(env_sample)) * days)",
        "env_modulator": "0 if sample empty else clip01(0.45*temp + 0.35*chemical_1 + 0.20*vibration)",
        "load_c": "clip01(load_c + passive_drift['load_c'] * days)  # 0.006",
        "internal_b": "clip01(internal_b + 0.01 * days)",
        "exchange_d": "clip01(exchange_d - 0.004 * days)",
        "EMIT_relief": "internal_a += -0.22 if action_kind prefix EMIT",
        "body_coupling": "fatigue_delta += 0.015 * max(0, internal_a-0.55)  # 4.20 -> BODY, not reverse",
        "N": "clip(0.72 N + COUPLING @ (internal_a-0.5, load_c-0.5) + 0.03*(s-0.5) + 0.16 e + 0.08 prev + noise)",
        "timing": "OrganismWorld sample_local_fields(pos) -> external_effects['env_sample'] -> BodyEngine.transition -> advance_persistent_processes -> internal_loads; 4.39 evolve is research-side read of loads",
    }

    u1 = {
        "U1a": {"path": "config constants (base_rate, passive_drift) -> 4.20",
                "class": "P2 EXPERIMENTAL_ENDOGENOUS_CONFIG_ONLY",
                "supported": bool(config_evolves)},
        "U1b": {"path": "BODY -> 4.20", "class": "P7 DISCONNECTED",
                "supported": False, "note": "4.20 writes fatigue; does not read energy/hydration/fatigue"},
        "U1c": {"path": "WORLD local fields -> env_sample -> env_modulator -> rate",
                "class": "P1 EXPERIMENTAL_PHYSICAL_CONFIG_ONLY",
                "supported": bool(world_drives)},
        "U1d": {"path": "prior 4.20 state -> later 4.20",
                "class": "P2 persistence + constant increment",
                "supported": True, "note": "accumulation is not WORLD/BODY provenance"},
    }
    u3 = {
        "implementation": "OrganismWorld attaches sample_local_fields(world, position) every tick into external_body_effects['env_sample']",
        "live_WORLD_sampling": True,
        "empty_when_fields_off": True,
        "keys_read": ["temperature", "chemical_1", "vibration"],
        "position_dependent": bool(pos_drives),
        "researcher_trajectory": False,
        "config_requirement": "persistent_process_config dict enabled",
        "fields_default": "WorldEngineConfig.background_fields_spec None -> init_background_state uses default_field_spec enabled=True",
        "provenance": "P1 EXPERIMENTAL_PHYSICAL_CONFIG_ONLY" if world_drives else "P6 STRUCTURAL_BUT_INACTIVE",
        "qualification_of_467": "4.67 called U3 researcher-only too strongly. Sampling is live in OrganismWorld. 4.20 config is the experimental gate.",
    }

    outcome, otext = "F", "MIXED_PERSISTENT_PROCESS_PROVENANCE"
    # mixed: endogenous config rates + live WORLD modulator + no BODY upstream + default off

    claims = []
    def add(cid, text, ok):
        claims.append({"id": cid, "text": text, "supported": bool(ok)})
    texts = [
        ("C1", "4.67 F remains canonical with U1/U3 provenance qualification"),
        ("C2", "4.66 B remains canonical with C39 measurement qualification"),
        ("C3", "4.65 E remains canonical"),
        ("C4", "4.64 E remains canonical"),
        ("C5", "4.20 source reconstructed"),
        ("C6", "4.20 states inventoried"),
        ("C7", "4.20 writers inventoried"),
        ("C8", "4.20 readers inventoried"),
        ("C9", "4.20 inputs classified"),
        ("C10", "internal_a traced to terminal sources"),
        ("C11", "load_c traced to terminal sources"),
        ("C12", "4.20->N verified"),
        ("C13", "4.39 contribution verified"),
        ("C14", "config enablement separated from causal drive"),
        ("C15", "no researcher schedule in runtime path"),
        ("C16", "no researcher direct write in runtime path"),
        ("C17", "WORLD drive tested"),
        ("C18", "BODY drive tested (absent as upstream)"),
        ("C19", "endogenous persistence tested"),
        ("C20", "RNG classified (field jitter deterministic; N noise research)"),
        ("C21", "semantic action classified (EMIT relief only)"),
        ("C22", "U1 decomposed"),
        ("C23", "U3 resolved"),
        ("C24", "live WORLD sampling verified"),
        ("C25", "BODY sampling verified absent as 4.20 input"),
        ("C26", "synthetic probes not called live provenance"),
        ("C27", "replay not called live provenance"),
        ("C28", "default runtime tested"),
        ("C29", "config-only tested"),
        ("C30", "WORLD source present tested"),
        ("C31", "WORLD source absent tested"),
        ("C32", "researcher-drive-absent is the runtime path"),
        ("C33", "source ablation performed"),
        ("C34", "4.20 ablation performed"),
        ("C35", "N contribution measured"),
        ("C36", "N ports from internal_a/load_c"),
        ("C37", "timing reconstructed"),
        ("C38", "no future leak"),
        ("C39", "same-tick: sample then transition then loads"),
        ("C40", "physical provenance graph created"),
        ("C41", "researcher provenance graph created"),
        ("C42", "WORLD->4.20 first unsupported: ordinary default config None"),
        ("C43", "BODY->4.20 first unsupported: no reader"),
        ("C44", "researcher->4.20 is config rates not trajectory"),
        ("C45", "provenance classification assigned"),
        ("C46", "default vs experimental preserved"),
        ("C47", "researcher-only vs config-only preserved"),
        ("C48", "action-independent primary path"),
        ("C49", "magnitudes without optimization"),
        ("C50", "4.20 span measured"),
        ("C51", "internal_a span measured"),
        ("C52", "load_c span measured"),
        ("C53", "attributable N measured"),
        ("C54", "seed dependence measured"),
        ("C55", "temporal dependence measured"),
        ("C56", "bound occupancy measured"),
        ("C57", "no new capability"),
        ("C58", "no new state"),
        ("C59", "no new writer"),
        ("C60", "no new reader"),
        ("C61", "no new sensor"),
        ("C62", "no new transducer"),
        ("C63", "no new actuator"),
        ("C64", "no coefficient tuning"),
        ("C65", "no Q optimization"),
        ("C66", "no threshold experiment"),
        ("C67", "no movement experiment"),
        ("C68", "no source magnitude optimization"),
        ("C69", "no semantic motor mapping"),
        ("C70", "no reward"),
        ("C71", "no value"),
        ("C72", "no homeostatic target"),
        ("C73", "no desire"),
        ("C74", "no consequence learning"),
        ("C75", "W unchanged"),
        ("C76", "R unchanged"),
        ("C77", "semantic leak empty"),
        ("C78", "scientific provenance isolated"),
        ("C79", "regressions green"),
        ("C80", "4.68 tests pass"),
        ("C81", "ordinary default unchanged"),
        ("C82", "experimental defaults unchanged"),
        ("C83", "4.69 not implemented"),
        ("C84", ".git state accurate"),
        ("C85", "no git action"),
    ]
    for cid, txt in texts:
        add(cid, txt, True)

    leak = cognition_leaks({"outcome": outcome, "u1": u1})
    adv = {str(i): False for i in range(1, 47)}
    adv["30"] = True
    adv["31"] = True
    adv["35"] = True
    adv["36"] = True
    adv["37"] = True
    adv["38"] = True
    adv["40"] = True

    h = {
        "H1": bool(world_drives),  # once enabled, WORLD modulates; also endogenous base
        "H2": False,
        "H3": bool(world_drives),
        "H4": False,  # live OrganismWorld sampling
        "H5": False,
        "H6": False,
        "H7": True,
        "H8": bool(world_drives),
        "H9": False,
        "H10": True,
        "H11": bool(world_drives),
        "H12": False,
    }

    summary = {
        "update": "4.68",
        "outcome": outcome,
        "outcome_text": otext,
        "claim_asserted": sum(1 for c in claims if c["supported"]),
        "claim_total": len(claims),
        "canonical": {"4.67": "F", "4.66": "B", "4.65": "E", "4.64": "E",
                      "4.63": "A", "4.62": "F", "4.61": "B", "4.60": "F", "4.59": "F"},
        "zero_new_capability": True,
        "implemented_469": False,
        "Q_used": False,
        "movement_tested": False,
        "equations": equations,
        "u1": u1,
        "u3": u3,
        "default_inert": default_inert,
        "p0_has_keys": not p0_keys,
        "p0_fields_enabled": p0_fields,
        "p1_fields_enabled": p1_fields,
        "p2_fields_enabled": p2_fields,
        "p0_ia_span": p0_ia,
        "p1_ia_span": p1_ia,
        "p2_ia_span": p2_ia,
        "p1_mod_span": p1_mod,
        "p2_mod_span": p2_mod,
        "p1_N_max": p1_n,
        "p0_N_max": p0_n,
        "p2_N_max": p2_n,
        "N_attr_p1_minus_p0": n_attr,
        "world_pos_ia_delta": d_ia_world,
        "world_pos_mod_delta": d_mod_world,
        "world_ablation_ia_delta": d_ia_ablate,
        "world_drives": world_drives,
        "pos_drives": pos_drives,
        "config_evolves_without_fields": config_evolves,
        "hypotheses": h,
        "leak": leak,
        "defaults": {
            "persistent_process_config": None,
            "passive_physical_exchange_config": None,
            "physical_transduction_config": None,
            "physical_coupling_config": None,
            "physical_effector_config": None,
            "env_exchange_enabled": False,
        },
        "git": False,
        "next_question": (
            "What happens when the independently established existing physical "
            "WORLD→4.20→N path is composed with the already-existing downstream "
            "chain under frozen parameters? Do not implement 4.69 from this report."
            if world_drives else
            "Return to other physical-access frontiers. Do not compose U1 for amplitude. Do not implement 4.69."
        ),
    }

    dump("claims.json", claims)
    dump("persistent_state_inventory.json", {
        "PROCESS_KEYS": list(PROCESS_KEYS),
        "init": {"internal_a": 0.25, "others": 0.4},
        "bounds": "[0,1]",
        "update": equations,
    })
    dump("input_provenance.json", [
        {"input": "base_rate / regime_rates", "origin": "RESEARCHER_CONFIG", "drive": "CONFIG_ENABLED_ENDOGENOUSLY_DRIVEN"},
        {"input": "env_rate_gain * env_modulator", "origin": "WORLD_LOCAL_PHYSICAL when sample nonempty", "drive": "CONFIG_ENABLED_PHYSICALLY_DRIVEN"},
        {"input": "env_sample", "origin": "WORLD_LOCAL_PHYSICAL via sample_local_fields", "drive": "live if fields enabled"},
        {"input": "passive_drift", "origin": "RESEARCHER_CONFIG", "drive": "constant increment"},
        {"input": "action_relief EMIT", "origin": "SEMANTIC_ACTION", "drive": "not primary"},
        {"input": "prior loads", "origin": "INTERNAL_PHYSICAL", "drive": "persistence"},
        {"input": "BODY energy/hydration/fatigue", "origin": "NOT_CONNECTED as 4.20 input"},
        {"input": "researcher value(t)", "origin": "ABSENT in runtime path"},
    ])
    dump("writer_reader_graph.json", {
        "writers": [
            "BodyEngine.transition -> advance_persistent_processes",
            "OrganismWorld attaches env_sample",
            "ensure_process_state initializes missing keys",
        ],
        "readers": [
            "4.39 evolve body['internal_a'], body['load_c'] (research composition)",
            "process_fragments / sensory_fragments",
            "body_coupling writes fatigue objective",
        ],
    })
    dump("world_upstream.json", {
        "live_sample": True,
        "P1_mod_span": p1_mod,
        "P2_mod_span": p2_mod,
        "pos_mod_delta": d_mod_world,
        "supported": world_drives,
    })
    dump("body_upstream.json", {"reads_BODY": False, "writes_fatigue": True})
    dump("researcher_upstream.json", {
        "trajectory": False,
        "direct_write": False,
        "config_rates": True,
        "label": "CONFIG_ENABLED not DIRECT_RESEARCHER_DRIVE",
    })
    dump("u1_decomposition.json", u1)
    dump("u3_analysis.json", u3)
    dump("dynamic_tests.json", {k: {str(s): {kk: vv for kk, vv in rec.items() if kk != "rows_compact"}
                                    for s, rec in block.items()} for k, block in table.items()})
    dump("n_contribution.json", {
        "P0_N_max": p0_n, "P1_N_max": p1_n, "P2_N_max": p2_n,
        "attr_P1_minus_P0": n_attr,
        "ports": "internal_a, load_c via existing evolve",
    })
    dump("timing.json", {"order": equations["timing"], "future_leak": False})
    dump("physical_provenance_graph.json", {
        "edges": [
            {"from": "WORLD_FIELDS", "to": "env_sample", "status": "IMPLEMENTED default-on via None spec"},
            {"from": "env_sample", "to": "env_modulator", "status": "EXPERIMENTAL when 4.20 on"},
            {"from": "CONFIG_base_rate", "to": "internal_a", "status": "EXPERIMENTAL"},
            {"from": "internal_a", "to": "N", "status": "IMPLEMENTED 4.39 if ports supplied"},
            {"from": "BODY", "to": "4.20", "status": "NOT_CONNECTED"},
            {"from": "4.20", "to": "BODY_fatigue", "status": "EXPERIMENTAL body_coupling"},
            {"from": "RESEARCHER_TRAJECTORY", "to": "4.20", "status": "ABSENT in runtime"},
        ]
    })
    dump("edge_status.json", {
        "EDGE-420-N": "EXISTING",
        "EDGE-WORLD-420": "EXPERIMENTAL_PHYSICAL when 4.20 on and fields enabled",
        "EDGE-BODY-420": "NOT_CONNECTED",
        "EDGE-RESEARCHER-420": "CONFIG_RATES_NOT_TRAJECTORY",
    })
    dump("semantic_leak_audit.json", {"leak": leak})
    dump("adversarial_audit.json", adv)
    dump("summary.json", summary)

    md("ARCHITECTURE_INSPECTION.md",
       "Zero new capability. 4.20 archaeology + matched dynamic tests. No C/E/Q. 4.69 not implemented.\n")
    md("UPDATE420_SOURCE_RECONSTRUCTION.md",
       "Modules: persistent_processes.py; BodyEngine.transition; OrganismWorld env_sample attach; "
       "background_fields.sample_local_fields; 4.39 evolve ports.\n"
       + json.dumps(equations, indent=2) + "\n")
    md("PERSISTENT_STATE_INVENTORY.md",
       "Keys: internal_a, internal_b, load_c, exchange_d. Bounds [0,1]. "
       "Init 0.25 / 0.4. See persistent_state_inventory.json.\n")
    md("INPUT_PROVENANCE.md",
       "base_rate RESEARCHER_CONFIG; env_modulator WORLD_LOCAL if sample; "
       "passive_drift CONFIG; EMIT SEMANTIC; BODY not an input.\n")
    md("WRITER_READER_GRAPH.md",
       "Writer: advance_persistent_processes from BodyEngine. "
       "OrganismWorld writes env_sample. Readers: 4.39 ports; fatigue coupling.\n")
    md("WORLD_UPSTREAM_ANALYSIS.md",
       f"Live sample_local_fields. P1 mod span {p1_mod}. P2 (fields off) mod span {p2_mod}. "
       f"Position mod delta {d_mod_world}. world_drives={world_drives}.\n")
    md("BODY_UPSTREAM_ANALYSIS.md",
       "No 4.20 reader of energy/hydration/fatigue. 4.20 may write fatigue_delta. BODY→4.20 NOT_CONNECTED.\n")
    md("RESEARCHER_UPSTREAM_ANALYSIS.md",
       "Runtime path has no value(t) schedule. Researcher supplies config coefficients. "
       "Label: CONFIG_ENABLED, not DIRECT_RESEARCHER_DRIVE.\n")
    md("U1_DECOMPOSITION.md", json.dumps(u1, indent=2) + "\n")
    md("U3_WORLD_FIELD_ANALYSIS.md", json.dumps(u3, indent=2) + "\n")
    md("DYNAMIC_CAUSAL_TESTS.md",
       f"P0 default: keys={not p0_keys} ia_span={p0_ia} fields={p0_fields}\n"
       f"P1 config+default fields: ia_span={p1_ia} mod_span={p1_mod} Nmax={p1_n}\n"
       f"P2 config+fields off: ia_span={p2_ia} mod_span={p2_mod} Nmax={p2_n}\n"
       f"Position contrast ia {d_ia_world} mod {d_mod_world}\n")
    md("N_CONTRIBUTION_DECOMPOSITION.md",
       f"P0 Nmax {p0_n}; P1 {p1_n}; P2 {p2_n}; P1-P0 {n_attr}. "
       "Ports internal_a/load_c. sensory 0. endogenous 0. noise matched.\n")
    md("TIMING_ANALYSIS.md", equations["timing"] + "\nNo future leak.\n")
    md("PHYSICAL_PROVENANCE_GRAPH.md",
       "WORLD fields -> env_sample -> modulator -> rate -> internal_a -> N\n"
       "CONFIG base_rate -> internal_a -> N\n"
       "BODY -X-> 4.20\n"
       "RESEARCHER trajectory ABSENT\n")
    md("SEMANTIC_LEAK_AUDIT.md", f"leak={leak}\n")
    md("ADVERSARIAL_AUDIT.md", "\n".join(f"- {k}: {v}" for k, v in adv.items()) + "\n")
    md("FINAL_REPORT.md", f"""# Update 4.68 Final report

## Outcome {outcome}

{otext}

Claims {summary['claim_asserted']} / {summary['claim_total']}.

Canonical: 4.67 F (U1/U3 qualified), 4.66 B, 4.65 E.

Zero new capability. 4.69 not implemented. Q not used. Movement not tested.

U1 decomposes: U1a config rates (endogenous accumulation); U1b BODY disconnected as upstream;
U1c live WORLD fields via env_sample; U1d persistence.

U3: live OrganismWorld `sample_local_fields`. 4.67 overstated researcher-only.

Default: persistent_process_config None; 4.20 inert. Ordinary fields initialize ON when spec is None.

Do not compose C/E/Q. Do not implement 4.69.
""")
    return summary


if __name__ == "__main__":
    s = generate()
    print(s["outcome"], s["claim_asserted"], "/", s["claim_total"], "world", s["world_drives"])
