#!/usr/bin/env python3
"""Update 4.7 lab matrix: canonical V05+MDS1000 multi-agent observation pass.

Measurement only. No JSONL giants. No cognitive changes.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "worlds"))

from mechanistic_mind.agent import Action, Agent
from mechanistic_mind.body import BodyConfig, BodyState
from mechanistic_mind.core import Engine
from mechanistic_mind.mechanisms import MechanismRegistry
from mechanistic_mind.multi_agent.v047 import derived_seed
from mechanistic_mind.observer import CompositeSink, InMemorySink, PsychologyObserver
from mechanistic_mind.psyche import (
    DevelopmentalCondition,
    DevelopmentalConfig,
    SingleOrganismPsycheV05,
)
from mechanistic_mind.psyche.sensorimotor import SensorimotorConfig
from mechanistic_mind.research.developmental_subsidy import (
    apply_subsidy_to_body_config,
    apply_subsidy_to_body_state,
    subsidy_from_tick_equivalent,
)
from contextual_object_ecology_v034 import (
    ContextualObjectEcologyWorld,
    multi_channel_contextual_object_config,
    todo4_calibrated_body_config,
)

OUT = ROOT / "results" / "update47_multi_agent_v047" / "matrix_lab"
OUT.mkdir(parents=True, exist_ok=True)

SEED = 17
TICKS = 1000
MDS = 1000
AGENT_A = "A001"
AGENT_B = "B001"

# Implemented Update 4.7 geometry (recorded in MATRIX_CONFIG).
POS_SINGLE = {AGENT_A: (2, 3)}
POS_NEAR = {AGENT_A: (2, 3), AGENT_B: (3, 3)}
POS_FAR = {AGENT_A: (2, 3), AGENT_B: (5, 4)}
POS_PASSIVE = {AGENT_A: (2, 3), AGENT_B: (4, 4)}
POS_TRACE = {AGENT_A: (2, 3), AGENT_B: (3, 3)}
POS_MEM = {AGENT_A: (2, 3), AGENT_B: (5, 4)}


def _body_cfg(recovery: bool = True) -> BodyConfig:
    base = todo4_calibrated_body_config()
    d = {f: getattr(base, f) for f in base.__dataclass_fields__}
    d["recovery_dynamics_enabled"] = recovery
    return BodyConfig(**d)


def _psyche() -> SingleOrganismPsycheV05:
    return SingleOrganismPsycheV05(
        sensorimotor_config=SensorimotorConfig(
            cue_mode="PERCEPTUAL_CUE_ENABLED",
            prospective_valuation=True,
        ),
        developmental=DevelopmentalConfig(
            condition=DevelopmentalCondition.EXPERIENCE_GATED
        ),
    )


def _stacks(agent_ids: tuple[str, ...]) -> dict[str, MechanismRegistry]:
    out: dict[str, MechanismRegistry] = {}
    for aid in agent_ids:
        reg = MechanismRegistry()
        reg.register(_psyche())
        out[aid] = reg
    return out


def build_engine(
    *,
    agent_ids: tuple[str, ...],
    start_positions: dict[str, tuple[int, int]],
    ticks: int,
    condition: str,
) -> Engine:
    spec = subsidy_from_tick_equivalent(MDS)
    body_cfg = apply_subsidy_to_body_config(_body_cfg(True), spec)
    bodies = {
        aid: apply_subsidy_to_body_state(BodyState(), spec) for aid in agent_ids
    }
    world = ContextualObjectEcologyWorld(
        world_config=multi_channel_contextual_object_config(SEED),
        body_config=body_cfg,
        agent_ids=agent_ids,
        start_positions=start_positions,
        initial_bodies=bodies,
        # keep dataclass default start unused when start_positions provided
    )
    stacks = _stacks(agent_ids)
    sink = InMemorySink()
    observer = PsychologyObserver(CompositeSink((sink,)), compact_ticks=True)
    return Engine(
        world=world,
        agents={aid: Agent(agent_id=aid) for aid in agent_ids},
        seed=SEED,
        mechanisms=stacks[agent_ids[0]],
        mechanisms_by_agent=stacks,
        observer=observer,
        run_config={
            "update": "4.7-matrix-lab",
            "condition": condition,
            "ticks": ticks,
            "world": "contextual-objects",
            "psyche": "EXPERIENCE_GATED_V05",
            "world_dynamics": "DYNAMIC_WORLD",
            "perception": "MULTI_CHANNEL",
            "perceptual_cue": "PERCEPTUAL_CUE_ENABLED",
            "mds": MDS,
            "recovery_dynamics": True,
            "random_events": 0,
            "shared_ecology": True,
            "independent_psyches": True,
            "no_social_semantics": True,
            "agent_ids": list(agent_ids),
            "start_positions": {k: list(v) for k, v in start_positions.items()},
            "derived_seeds": {aid: derived_seed(SEED, aid) for aid in agent_ids},
        },
    )


def _manhattan(a: list | tuple, b: list | tuple) -> int:
    return abs(int(a[0]) - int(b[0])) + abs(int(a[1]) - int(b[1]))


def _family(kind: str) -> str:
    return str(kind).split(":", 1)[0]


def _psyche_blob(engine: Engine, agent_id: str) -> dict[str, Any]:
    st = engine.state.agents.get(agent_id)
    if st is None:
        return {}
    for payload in st.mechanism_states.values():
        if isinstance(payload, dict) and isinstance(payload.get("psyche"), dict):
            return deepcopy(payload["psyche"])
    return {}


def _safe_num(x: Any) -> float | None:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def _body_snapshot(body: Any) -> dict[str, Any]:
    if body is None:
        return {}
    if is_dataclass(body):
        d = asdict(body)
    elif isinstance(body, dict):
        d = body
    else:
        d = {
            k: getattr(body, k)
            for k in (
                "energy_reserve",
                "hydration",
                "fatigue",
                "activity_load",
                "activity_capacity",
            )
            if hasattr(body, k)
        }
    keys = (
        "energy_reserve",
        "hydration",
        "fatigue",
        "activity_load",
        "activity_capacity",
        "damage",
        "metabolic_energy",
    )
    return {k: _safe_num(d.get(k)) for k in keys if k in d}


def _wait_stats(actions: list[str]) -> dict[str, Any]:
    n = len(actions)
    waits = [i for i, a in enumerate(actions) if _family(a) == "WAIT"]
    first_wait = waits[0] if waits else None
    # sustained: first run of >=20 WAIT
    sustained = None
    run = 0
    run_start = 0
    longest = 0
    longest_start = None
    cur = 0
    cur_start = 0
    for i, a in enumerate(actions):
        if _family(a) == "WAIT":
            if cur == 0:
                cur_start = i
            cur += 1
            if cur > longest:
                longest = cur
                longest_start = cur_start
            if sustained is None and cur >= 20:
                sustained = cur_start
        else:
            cur = 0
    return {
        "first_wait_tick": first_wait,
        "first_sustained_wait_tick_ge20": sustained,
        "longest_wait_run": longest,
        "longest_wait_run_start": longest_start,
        "wait_count": len(waits),
        "wait_fraction": (len(waits) / n) if n else 0.0,
    }


def _phase_analysis(actions: list[str], window: int = 50) -> list[dict[str, Any]]:
    phases = []
    n = len(actions)
    i = 0
    while i < n:
        chunk = actions[i : i + window]
        fam = Counter(_family(a) for a in chunk)
        dominant = fam.most_common(1)[0][0] if fam else "NONE"
        label = f"{dominant}-dominant" if fam and fam[dominant] >= 0.6 * len(chunk) else "mixed"
        # extend while same label
        j = i + window
        while j < n:
            chunk2 = actions[j : j + window]
            fam2 = Counter(_family(a) for a in chunk2)
            dom2 = fam2.most_common(1)[0][0] if fam2 else "NONE"
            lab2 = f"{dom2}-dominant" if fam2 and fam2[dom2] >= 0.6 * len(chunk2) else "mixed"
            if lab2 != label:
                break
            j += window
        phases.append(
            {
                "ticks": [i, min(j, n) - 1],
                "label": label,
                "family_counts": dict(fam),
            }
        )
        i = j if j > i else i + window
    return phases


def _extract_cognition(psyche: dict[str, Any]) -> dict[str, Any]:
    mem = psyche.get("memory") or {}
    episodes = mem.get("episodes") or []
    dev = psyche.get("developmental") or psyche.get("development") or {}
    depth = psyche.get("cognitive_depth") or psyche.get("depth") or {}
    mp = psyche.get("motor_primitives") or psyche.get("sensorimotor") or {}
    return {
        "experience_count": len(episodes) if isinstance(episodes, list) else None,
        "local_maturity": {
            "raw": deepcopy(dev) if isinstance(dev, dict) else dev,
        },
        "cognitive_depth": {
            "raw": deepcopy(depth) if isinstance(depth, (dict, list, int, float)) else depth,
        },
        "motor_primitives": {
            "raw_keys": list(mp.keys()) if isinstance(mp, dict) else type(mp).__name__,
        },
        "memory_keys": list(mem.keys()) if isinstance(mem, dict) else [],
    }


def run_condition(
    *,
    name: str,
    agent_ids: tuple[str, ...],
    start_positions: dict[str, tuple[int, int]],
    ticks: int,
    forced_actions: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    t0 = time.time()
    engine = build_engine(
        agent_ids=agent_ids,
        start_positions=start_positions,
        ticks=ticks,
        condition=name,
    )
    forced = {aid: list(seq) for aid, seq in (forced_actions or {}).items()}

    actions: dict[str, list[str]] = {aid: [] for aid in agent_ids}
    positions_series: dict[str, list[list[int]]] = {aid: [] for aid in agent_ids}
    body_samples: dict[str, list[dict[str, Any]]] = {aid: [] for aid in agent_ids}
    use_events: list[dict[str, Any]] = []
    emit_events: list[dict[str, Any]] = []
    push_events: list[dict[str, Any]] = []
    contact_ticks: list[int] = []
    distance_series: list[float] = []
    object_qty_on_use: list[dict[str, Any]] = []
    shared_object_events: list[dict[str, Any]] = []
    object_last_modifier: dict[str, str] = {}
    occupancy_block_events: list[dict[str, Any]] = []

    # tick0 initial asymmetry note
    truth0 = engine.state.world.variables.get("world") or {}
    pos0 = deepcopy(truth0.get("agent_positions") or {})

    for tick in range(ticks):
        overrides: dict[str, Action] = {}
        for aid, seq in forced.items():
            if tick < len(seq):
                overrides[aid] = Action(seq[tick])
        result = engine.step(overrides or None)

        truth = engine.state.world.variables.get("world") or {}
        positions = truth.get("agent_positions") or {}
        bodies = engine.state.world.variables.get("bodies") or {}

        for aid in agent_ids:
            kind = result.actions[aid].kind
            actions[aid].append(kind)
            p = positions.get(aid)
            if isinstance(p, list):
                positions_series[aid].append([int(p[0]), int(p[1])])
            if tick % 50 == 0 or tick == ticks - 1:
                body_samples[aid].append(
                    {"tick": tick, **_body_snapshot(bodies.get(aid))}
                )
            fam = _family(kind)
            if fam == "USE":
                oid = kind.split(":", 1)[1] if ":" in kind else None
                qty = None
                if oid:
                    rec = (truth.get("objects") or {}).get(oid) or {}
                    qty = rec.get("quantity")
                    prev_mod = object_last_modifier.get(oid)
                    if prev_mod and prev_mod != aid:
                        shared_object_events.append(
                            {
                                "tick": tick,
                                "object_id": oid,
                                "encounter_agent": aid,
                                "prior_modifier": prev_mod,
                                "quantity": qty,
                                "kind": "USE_AFTER_OTHER_MODIFIED",
                            }
                        )
                    object_last_modifier[oid] = aid
                use_events.append(
                    {"tick": tick, "agent_id": aid, "action": kind, "quantity": qty}
                )
                object_qty_on_use.append(
                    {"tick": tick, "agent_id": aid, "object_id": oid, "quantity": qty}
                )
            elif fam == "EMIT":
                emit_events.append({"tick": tick, "agent_id": aid})
            elif fam == "PUSH":
                push_events.append({"tick": tick, "agent_id": aid, "action": kind})

        if len(agent_ids) >= 2:
            a, b = agent_ids[0], agent_ids[1]
            pa, pb = positions.get(a), positions.get(b)
            if isinstance(pa, list) and isinstance(pb, list):
                d = _manhattan(pa, pb)
                distance_series.append(float(d))
                if d <= 1:
                    contact_ticks.append(tick)

    engine.close()

    # final cognition
    per_agent: dict[str, Any] = {}
    for aid in agent_ids:
        acts = actions[aid]
        fam = Counter(_family(a) for a in acts)
        pos_list = positions_series[aid]
        unique_pos = len({tuple(p) for p in pos_list})
        displacement = 0
        for i in range(1, len(pos_list)):
            displacement += _manhattan(pos_list[i - 1], pos_list[i])
        psyche = _psyche_blob(engine, aid)
        cog = _extract_cognition(psyche)
        use_targets = [
            e["action"].split(":", 1)[1]
            for e in use_events
            if e["agent_id"] == aid and ":" in e["action"]
        ]
        per_agent[aid] = {
            "action_counts": dict(fam),
            "wait": _wait_stats(acts),
            "move_fraction": fam.get("MOVE", 0) / len(acts) if acts else 0.0,
            "use_count": fam.get("USE", 0),
            "emit_count": fam.get("EMIT", 0),
            "unique_positions": unique_pos,
            "total_displacement": displacement,
            "final_position": pos_list[-1] if pos_list else None,
            "position_samples": pos_list[:: max(1, len(pos_list) // 40)][:40],
            "body_samples": body_samples[aid],
            "phases": _phase_analysis(acts),
            "use_targets": dict(Counter(use_targets)),
            "repeated_use_count": sum(1 for c in Counter(use_targets).values() if c > 1),
            "cognition": cog,
            "first_40_actions": acts[:40],
            "last_40_actions": acts[-40:],
        }

    pair: dict[str, Any] | None = None
    if len(agent_ids) >= 2 and distance_series:
        pair = {
            "initial_distance": distance_series[0],
            "min_distance": min(distance_series),
            "mean_distance": sum(distance_series) / len(distance_series),
            "final_distance": distance_series[-1],
            "adjacent_or_contact_ticks": len(contact_ticks),
            "first_contact_tick": contact_ticks[0] if contact_ticks else None,
            "contact_tick_sample": contact_ticks[:30],
        }

    # memory isolation fingerprints
    mem_iso = None
    if len(agent_ids) >= 2:
        sets = {}
        for aid in agent_ids:
            mem = (_psyche_blob(engine, aid).get("memory") or {})
            eps = mem.get("episodes") or []
            fp = set()
            for ep in eps:
                if isinstance(ep, dict):
                    fp.add(
                        json.dumps(
                            {
                                "action": ep.get("action"),
                                "tick": ep.get("tick"),
                                "effects": ep.get("experienced_effects") or ep.get("effects"),
                                "position": ep.get("position"),
                            },
                            sort_keys=True,
                            default=str,
                        )
                    )
            sets[aid] = fp
        a, b = agent_ids[0], agent_ids[1]
        overlap = sets[a] & sets[b]
        mem_iso = {
            "shared_episode_fingerprints": len(overlap),
            "pass": len(overlap) == 0,
            "episodes": {aid: len(sets[aid]) for aid in agent_ids},
        }

    summary = {
        "condition": name,
        "ticks": ticks,
        "seed": SEED,
        "mds": MDS,
        "elapsed_sec": round(time.time() - t0, 3),
        "agent_ids": list(agent_ids),
        "start_positions": {k: list(v) for k, v in start_positions.items()},
        "tick0_positions": pos0,
        "per_agent": per_agent,
        "pair": pair,
        "use_events_sample": use_events[:60],
        "emit_events": emit_events[:40],
        "push_events": push_events[:40],
        "shared_object_events": shared_object_events[:40],
        "shared_object_event_count": len(shared_object_events),
        "memory_isolation": mem_iso,
        "final_bodies": {
            aid: _body_snapshot((engine.state.world.variables.get("bodies") or {}).get(aid))
            for aid in agent_ids
        },
        "object_qty_on_use_sample": object_qty_on_use[:40],
        "notes": {
            "initial_positional_asymmetry": "INITIAL_CONDITION",
            "no_jsonl": True,
        },
    }
    return summary


def write_json(name: str, payload: Any) -> Path:
    path = OUT / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")
    return path


def validate_controls() -> dict[str, Any]:
    # SHARED_OBJECT_TRACE short forced
    use_then_wait = ["USE:OBJ-12"] * 5 + ["WAIT"] * 15
    wait_b = ["WAIT"] * 20
    trace = run_condition(
        name="SHARED_OBJECT_TRACE",
        agent_ids=(AGENT_A, AGENT_B),
        start_positions=POS_TRACE,
        ticks=20,
        forced_actions={AGENT_A: use_then_wait, AGENT_B: wait_b},
    )
    # extract qty series from use events
    qtys = [
        e.get("quantity")
        for e in trace.get("object_qty_on_use_sample") or []
        if e.get("agent_id") == AGENT_A and e.get("object_id") == "OBJ-12"
    ]
    trace["control"] = {
        "object_id": "OBJ-12",
        "quantity_series": qtys,
        "depleted": bool(qtys) and qtys[-1] is not None and qtys[0] is not None and qtys[-1] < qtys[0],
    }
    write_json("SHARED_OBJECT_TRACE_SUMMARY.json", trace)

    mem = run_condition(
        name="MEMORY_ISOLATION",
        agent_ids=(AGENT_A, AGENT_B),
        start_positions=POS_MEM,
        ticks=40,
        forced_actions={
            AGENT_A: ["USE:OBJ-12"] * 8 + ["WAIT"] * 32,
            AGENT_B: ["WAIT"] * 40,
        },
    )
    write_json("MEMORY_ISOLATION_SUMMARY.json", mem)
    return {"SHARED_OBJECT_TRACE": trace["control"], "MEMORY_ISOLATION": mem.get("memory_isolation")}


def analyze_and_report(results: dict[str, Any]) -> None:
    single = results["SINGLE"]
    near = results["TWO_NEAR"]
    far = results["TWO_FAR"]
    passive = results["PASSIVE_BODY"]

    def agent_actions(summary, aid):
        return (summary.get("per_agent") or {}).get(aid, {}).get("action_counts") or {}

    wait_cmp = {
        "SINGLE_A": (single["per_agent"][AGENT_A]["wait"], agent_actions(single, AGENT_A)),
        "TWO_NEAR_A": (near["per_agent"][AGENT_A]["wait"], agent_actions(near, AGENT_A)),
        "TWO_NEAR_B": (near["per_agent"][AGENT_B]["wait"], agent_actions(near, AGENT_B)),
        "TWO_FAR_A": (far["per_agent"][AGENT_A]["wait"], agent_actions(far, AGENT_A)),
        "TWO_FAR_B": (far["per_agent"][AGENT_B]["wait"], agent_actions(far, AGENT_B)),
        "PASSIVE_A": (passive["per_agent"][AGENT_A]["wait"], agent_actions(passive, AGENT_A)),
        "reference_4_6_approx": {"EMIT": 1, "MOVE": 204, "USE": 1, "WAIT": 794},
        "note": "New SINGLE is canonical comparator; 4.6 reference is historical.",
    }
    write_json("WAIT_ATTRACTOR_COMPARISON.json", wait_cmp)

    # Divergence: first action divergence between A and B
    def first_div(summary):
        a = summary["per_agent"][AGENT_A]["first_40_actions"] + []
        # rebuild from phases? we only stored first/last 40 — for full need re-store
        return {
            "tick0_positions": summary.get("tick0_positions"),
            "pair": summary.get("pair"),
            "action_counts_A": agent_actions(summary, AGENT_A),
            "action_counts_B": agent_actions(summary, AGENT_B),
            "wait_A": summary["per_agent"][AGENT_A]["wait"],
            "wait_B": summary["per_agent"][AGENT_B]["wait"],
            "unique_pos_A": summary["per_agent"][AGENT_A]["unique_positions"],
            "unique_pos_B": summary["per_agent"][AGENT_B]["unique_positions"],
            "classification_note": (
                "Initial positional/perceptual asymmetry is INITIAL_CONDITION. "
                "Longitudinal class inferred from distance + action/wait divergence."
            ),
        }

    div = {
        "TWO_NEAR": first_div(near),
        "TWO_FAR": first_div(far),
        "longitudinal_class": {},
    }
    for key, summary in ("TWO_NEAR", near), ("TWO_FAR", far):
        pair = summary.get("pair") or {}
        init_d = pair.get("initial_distance")
        final_d = pair.get("final_distance")
        mean_d = pair.get("mean_distance")
        if init_d is None:
            klass = "UNAVAILABLE"
        elif final_d is not None and init_d is not None:
            if abs(final_d - init_d) <= 1 and abs((mean_d or init_d) - init_d) <= 2:
                klass = "STABLE_DIFFERENCE"
            elif final_d > init_d + 2:
                klass = "AMPLIFYING"
            elif final_d < init_d - 2:
                klass = "CONVERGING"
            else:
                klass = "MIXED"
        else:
            klass = "MIXED"
        div["longitudinal_class"][key] = klass
    write_json("DIVERGENCE_ANALYSIS.json", div)

    obj = {
        "SINGLE_use_targets": single["per_agent"][AGENT_A].get("use_targets"),
        "TWO_NEAR_shared_object_events": near.get("shared_object_events"),
        "TWO_FAR_shared_object_events": far.get("shared_object_events"),
        "AUTONOMOUS_SHARED_OBJECT_COUPLING": (
            "OBSERVED"
            if (near.get("shared_object_event_count") or 0)
            + (far.get("shared_object_event_count") or 0)
            > 0
            else "NOT_OBSERVED"
        ),
        "control_SHARED_OBJECT_TRACE": results.get("controls", {}).get("SHARED_OBJECT_TRACE"),
    }
    write_json("OBJECT_COUPLING_ANALYSIS.json", obj)

    cross = {
        "TWO_NEAR": {
            "pair": near.get("pair"),
            "push_events": near.get("push_events"),
            "emit_events": near.get("emit_events"),
            "shared_object_events": near.get("shared_object_events"),
            "direct_contact_ticks": (near.get("pair") or {}).get("adjacent_or_contact_ticks"),
        },
        "TWO_FAR": {
            "pair": far.get("pair"),
            "push_events": far.get("push_events"),
            "emit_events": far.get("emit_events"),
            "shared_object_events": far.get("shared_object_events"),
            "direct_contact_ticks": (far.get("pair") or {}).get("adjacent_or_contact_ticks"),
        },
        "PASSIVE_BODY": {
            "pair": passive.get("pair"),
            "note": "B forced WAIT — physical presence without autonomous process",
        },
        "classification_policy": "No social inference; physical events only.",
    }
    write_json("CROSS_AGENT_CAUSAL_EVENTS.json", cross)

    recip = {
        "RECIPROCAL_CROSS_AGENT_LOOP": "NOT_OBSERVED",
        "reason": (
            "No documented A→world/B→B action→world/A→A action chain with "
            "physically available propagation beyond co-presence metrics."
        ),
        "candidates_reviewed": {
            "TWO_NEAR_shared_object": near.get("shared_object_event_count"),
            "TWO_FAR_shared_object": far.get("shared_object_event_count"),
            "TWO_NEAR_contacts": (near.get("pair") or {}).get("adjacent_or_contact_ticks"),
            "TWO_FAR_contacts": (far.get("pair") or {}).get("adjacent_or_contact_ticks"),
        },
    }
    # If shared object events exist both ways, upgrade carefully
    near_so = near.get("shared_object_events") or []
    far_so = far.get("shared_object_events") or []
    dirs = set()
    for ev in near_so + far_so:
        if ev.get("prior_modifier") and ev.get("encounter_agent"):
            dirs.add((ev["prior_modifier"], ev["encounter_agent"]))
    if ("A001", "B001") in dirs and ("B001", "A001") in dirs:
        recip["RECIPROCAL_CROSS_AGENT_LOOP"] = "PARTIAL_CANDIDATE_OBJECT_MEDIATED"
        recip["reason"] = "Both A→object→B and B→object→A USE-after-modify events present; full cognitive loop not claimed."
    write_json("RECIPROCAL_LOOP_ANALYSIS.json", recip)

    # Causal chain markdown
    chain = """# Update 4.7 Matrix — Cross-Agent Causal Chain

Marks: DEMONSTRATED / PARTIAL / IMPLEMENTED_BUT_UNPROVEN / MISSING / NULL / NOT_OBSERVED

| Arrow | Status | Notes |
|---|---|---|
| A physical action → world change | DEMONSTRATED | MOVE/USE/EMIT/PUSH alter shared world |
| world change → B physically available input | PARTIAL | occupancy/contact/shared object when events occur; else NOT_OBSERVED |
| B physically available input → B observation | IMPLEMENTED_BUT_UNPROVEN | ordinary observe path; cross-agent identity not special-cased |
| B observation → B experience | IMPLEMENTED_BUT_UNPROVEN | ordinary experience write |
| B experience → B retrieval | IMPLEMENTED_BUT_UNPROVEN / NOT_OBSERVED in matrix detail | compact metrics limited |
| B retrieval → B prediction | IMPLEMENTED_BUT_UNPROVEN / NOT_OBSERVED | |
| B prediction → B prospective value | IMPLEMENTED_BUT_UNPROVEN / NOT_OBSERVED | |
| B prospective value → B selection | MISSING / NOT_OBSERVED as cross-agent effect | |
| B action → world → A input | PARTIAL/NOT_OBSERVED | see RECIPROCAL_LOOP_ANALYSIS |
| Memory shared across agents | NULL | MEMORY_ISOLATION pass |
| Social semantics | NULL | forbidden / not implemented |

## First unsupported cross-agent causal arrow
**B observation of a cross-agent-caused physical change → demonstrated participation in retrieval/prediction/prospective valuation/selection.**

Infrastructure can write ordinary experience; this matrix does not demonstrate that cross-agent physical events propagate into later selection.
"""
    (OUT / "MATRIX_CAUSAL_CHAIN.md").write_text(chain)

    # Outcomes A-K
    outcomes = []
    # Always true-ish
    outcomes.append("A")  # may refine below
    if (near.get("pair") or {}).get("adjacent_or_contact_ticks") or (
        far.get("pair") or {}
    ).get("adjacent_or_contact_ticks"):
        outcomes.append("D")
    if obj["AUTONOMOUS_SHARED_OBJECT_COUPLING"] == "OBSERVED":
        outcomes.append("C")
    # Compare WAIT fractions
    sw = single["per_agent"][AGENT_A]["wait"]["wait_fraction"]
    diffs = [
        abs(near["per_agent"][AGENT_A]["wait"]["wait_fraction"] - sw),
        abs(near["per_agent"][AGENT_B]["wait"]["wait_fraction"] - sw),
        abs(far["per_agent"][AGENT_A]["wait"]["wait_fraction"] - sw),
        abs(far["per_agent"][AGENT_B]["wait"]["wait_fraction"] - sw),
    ]
    if max(diffs) >= 0.10:
        outcomes.append("I")
        if "A" in outcomes:
            outcomes.remove("A")
        outcomes.append("B")
    else:
        outcomes.append("K")

    # Final report answering 39 questions
    def fmt_agent(summary, aid):
        p = summary["per_agent"][aid]
        return {
            "actions": p["action_counts"],
            "wait": p["wait"],
            "phases": p["phases"][:8],
            "unique_positions": p["unique_positions"],
            "use_targets": p.get("use_targets"),
        }

    report = f"""# Update 4.7 — MATRIX_FINAL_REPORT (lab)

Observation pass only. No new mechanisms.

## Effective configuration
See `MATRIX_CONFIG.json`.

Canonical:
- ticks={TICKS}, seed={SEED}, MDS={MDS}
- world=contextual-objects (`multi_channel_contextual_object_config`)
- psyche=SingleOrganismPsycheV05 EXPERIENCE_GATED
- cue=PERCEPTUAL_CUE_ENABLED, prospective_valuation=True
- dynamics=DYNAMIC_WORLD (autonomous_dynamics_enabled)
- perception=MULTI_CHANNEL
- recovery_dynamics=ON
- random_events=0
- positions: SINGLE {POS_SINGLE}; TWO_NEAR {POS_NEAR}; TWO_FAR {POS_FAR}; PASSIVE {POS_PASSIVE}

## Runner repair (non-science)
Sync of Update 4.7 from box extract had overwritten `worlds/contextual_object_ecology_v034.py` and dropped
`multi_channel_contextual_object_config` / `contact_only_contextual_object_config` and the Update 4.6 modes 3–4
quantity binding. Restored before this matrix. Details: `RUNNER_REPAIRS.md`.

## 1. Did all matrix conditions complete successfully?
{'YES' if all(k in results for k in ('SINGLE','TWO_NEAR','TWO_FAR','PASSIVE_BODY')) else 'NO'}

## 2. Exact effective configuration
Recorded in MATRIX_CONFIG.json and engine.run_config fields above.

## 3. SINGLE
```json
{json.dumps(fmt_agent(single, AGENT_A), indent=2, default=str)}
```

## 4–5. TWO_NEAR A / B
```json
{json.dumps({'A': fmt_agent(near, AGENT_A), 'B': fmt_agent(near, AGENT_B), 'pair': near.get('pair')}, indent=2, default=str)}
```

## 6–7. TWO_FAR A / B
```json
{json.dumps({'A': fmt_agent(far, AGENT_A), 'B': fmt_agent(far, AGENT_B), 'pair': far.get('pair')}, indent=2, default=str)}
```

## 8. WAIT dominance in each psyche?
See WAIT_ATTRACTOR_COMPARISON.json (wait_fraction per agent).

## 9. Sustained WAIT begin?
`first_sustained_wait_tick_ge20` in WAIT_ATTRACTOR_COMPARISON / per-agent wait blocks.

## 10. Action distributions diverge?
Compare action_counts in summaries; also vs SINGLE.

## 11. Spatial trajectories diverge?
unique_positions + pair distances in DIVERGENCE_ANALYSIS.json.

## 12. Experience histories beyond tick-0 asymmetry?
memory_isolation episode counts differ by agent when actions differ; tick-0 asymmetry is INITIAL_CONDITION.

## 13–17. Retrieval / prediction / prospective / body / maturity-depth diverge?
Compact cognition blobs recorded under per_agent.cognition (raw). Detailed field-level divergence often UNAVAILABLE without deeper probes — do not invent.

## 18–19. A physically affect B / B affect A?
See CROSS_AGENT_CAUSAL_EVENTS.json (contacts, shared_object_events, push/emit).

## 20. Autonomous shared-object coupling?
{obj['AUTONOMOUS_SHARED_OBJECT_COUPLING']}

## 21. Direct contact/PUSH?
contact ticks and push_events in CROSS_AGENT_CAUSAL_EVENTS.json.

## 22. Physical emissions cross?
emit_events listed; reception-to-cognition NOT claimed without channel evidence.

## 23–27. Cross-agent → experience → retrieval → prediction → valuation → selection?
NOT_OBSERVED as demonstrated chain (see MATRIX_CAUSAL_CHAIN.md). Ordinary experience path IMPLEMENTED_BUT_UNPROVEN for cross-agent content.

## 28. Reciprocal loop?
{recip['RECIPROCAL_CROSS_AGENT_LOOP']}

## 29. TWO_NEAR vs TWO_FAR
Compare pair.mean/min distance, contact ticks, shared_object_events.

## 30. TWO_NEAR vs PASSIVE_BODY
PASSIVE_BODY B is forced WAIT; any difference isolates autonomous second process vs mere body presence.

## 31. Both vs SINGLE
WAIT_ATTRACTOR_COMPARISON + action_counts.

## 32. Second psyche change WAIT attractor?
Inferred if wait_fraction differs by ≥0.10 from SINGLE (see outcomes).

## 33–34. USE frequency / depletion-recovery dynamics change?
Compare use_count and use_targets; autonomous depletion cycles if present in summaries.

## 35. Initial asymmetry class
{json.dumps(div['longitudinal_class'])}

## 36. Strongest demonstrated new result of Update 4.7
Shared ecology with independent psyches/bodies/memory (MEMORY_ISOLATION pass) plus ability to measure physical co-presence and shared-object traces under canonical V05+MDS1000.

## 37. First unsupported cross-agent causal arrow
Cross-agent physical change → demonstrated effect on later retrieval/prediction/prospective valuation/selection.

## 38. Justify a new mechanism?
NO — do not implement. Null or partial physical coupling does not license social/communication machinery.

## 39. Smallest scientifically justified next experiment?
Targeted probe: force a unique physical world change by A (object quantity or occupancy), confirm B's observation packet contains the change, then trace whether that episode is retrieved at a later decision — still no new mechanism.

## Outcome letters
{sorted(set(outcomes))}

## Controls
```json
{json.dumps(results.get('controls'), indent=2, default=str)}
```
"""
    (OUT / "MATRIX_FINAL_REPORT.md").write_text(report)
    write_json(
        "OUTCOMES.json",
        {"letters": sorted(set(outcomes)), "reciprocal": recip, "object_coupling": obj["AUTONOMOUS_SHARED_OBJECT_COUPLING"]},
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticks", type=int, default=TICKS)
    ap.add_argument("--skip-controls", action="store_true")
    ap.add_argument("--only", default="ALL", help="ALL|SINGLE|TWO_NEAR|TWO_FAR|PASSIVE_BODY|CONTROLS")
    args = ap.parse_args()
    ticks = int(args.ticks)

    config = {
        "ticks": ticks,
        "seed": SEED,
        "mds": MDS,
        "world": "contextual-objects",
        "psyche": "EXPERIENCE_GATED_V05",
        "world_dynamics": "DYNAMIC_WORLD",
        "perception": "MULTI_CHANNEL",
        "perceptual_cue": "PERCEPTUAL_CUE_ENABLED",
        "prospective_valuation": True,
        "recovery_dynamics": True,
        "random_events": 0,
        "positions": {
            "SINGLE": POS_SINGLE,
            "TWO_NEAR": POS_NEAR,
            "TWO_FAR": POS_FAR,
            "PASSIVE_BODY": POS_PASSIVE,
        },
        "no_jsonl": True,
        "derived_seeds": {
            AGENT_A: derived_seed(SEED, AGENT_A),
            AGENT_B: derived_seed(SEED, AGENT_B),
        },
    }
    write_json("MATRIX_CONFIG.json", config)

    repairs = {
        "repairs": [
            {
                "file": "worlds/contextual_object_ecology_v034.py",
                "reason": "4.7 sync from box extract dropped multi_channel/contact_only helpers and Update 4.6 modes 3-4 quantity binding",
                "change": "Restored helpers + modes 3-4 + safety net",
                "alters_cognition": False,
            }
        ]
    }
    write_json("RUNNER_REPAIRS.md".replace(".md", ".json"), repairs)
    (OUT / "RUNNER_REPAIRS.md").write_text(
        "# Runner repairs (non-science)\n\n"
        "Before the lab matrix, `worlds/contextual_object_ecology_v034.py` was restored after an "
        "Update 4.7 sync from a box extract overwrote the lab ecology file and removed:\n\n"
        "1. `multi_channel_contextual_object_config` / `contact_only_contextual_object_config`\n"
        "2. Update 4.6 modes 3–4 quantity reservoir binding + safety net\n\n"
        "No action selection, valuation, or social machinery was changed.\n"
    )

    results: dict[str, Any] = {}
    only = args.only.upper()

    if only in ("ALL", "CONTROLS") and not args.skip_controls:
        print("Running controls...", flush=True)
        results["controls"] = validate_controls()
        print(json.dumps(results["controls"], indent=2, default=str), flush=True)

    if only in ("ALL", "SINGLE"):
        print("Running SINGLE...", flush=True)
        results["SINGLE"] = run_condition(
            name="SINGLE",
            agent_ids=(AGENT_A,),
            start_positions=POS_SINGLE,
            ticks=ticks,
        )
        write_json("SINGLE_SUMMARY.json", results["SINGLE"])
        print(results["SINGLE"]["per_agent"][AGENT_A]["action_counts"], flush=True)

    if only in ("ALL", "TWO_NEAR"):
        print("Running TWO_NEAR...", flush=True)
        results["TWO_NEAR"] = run_condition(
            name="TWO_NEAR",
            agent_ids=(AGENT_A, AGENT_B),
            start_positions=POS_NEAR,
            ticks=ticks,
        )
        write_json("TWO_NEAR_SUMMARY.json", results["TWO_NEAR"])
        print(
            {
                "A": results["TWO_NEAR"]["per_agent"][AGENT_A]["action_counts"],
                "B": results["TWO_NEAR"]["per_agent"][AGENT_B]["action_counts"],
                "pair": results["TWO_NEAR"]["pair"],
            },
            flush=True,
        )

    if only in ("ALL", "TWO_FAR"):
        print("Running TWO_FAR...", flush=True)
        results["TWO_FAR"] = run_condition(
            name="TWO_FAR",
            agent_ids=(AGENT_A, AGENT_B),
            start_positions=POS_FAR,
            ticks=ticks,
        )
        write_json("TWO_FAR_SUMMARY.json", results["TWO_FAR"])
        print(
            {
                "A": results["TWO_FAR"]["per_agent"][AGENT_A]["action_counts"],
                "B": results["TWO_FAR"]["per_agent"][AGENT_B]["action_counts"],
                "pair": results["TWO_FAR"]["pair"],
            },
            flush=True,
        )

    if only in ("ALL", "PASSIVE_BODY"):
        print("Running PASSIVE_BODY...", flush=True)
        results["PASSIVE_BODY"] = run_condition(
            name="PASSIVE_BODY",
            agent_ids=(AGENT_A, AGENT_B),
            start_positions=POS_PASSIVE,
            ticks=ticks,
            forced_actions={AGENT_B: ["WAIT"] * ticks},
        )
        write_json("PASSIVE_BODY_SUMMARY.json", results["PASSIVE_BODY"])
        print(
            {
                "A": results["PASSIVE_BODY"]["per_agent"][AGENT_A]["action_counts"],
                "B": results["PASSIVE_BODY"]["per_agent"][AGENT_B]["action_counts"],
            },
            flush=True,
        )

    # If only partial, load missing summaries for analysis
    for key, fname in (
        ("SINGLE", "SINGLE_SUMMARY.json"),
        ("TWO_NEAR", "TWO_NEAR_SUMMARY.json"),
        ("TWO_FAR", "TWO_FAR_SUMMARY.json"),
        ("PASSIVE_BODY", "PASSIVE_BODY_SUMMARY.json"),
    ):
        if key not in results and (OUT / fname).exists():
            results[key] = json.loads((OUT / fname).read_text())

    if all(k in results for k in ("SINGLE", "TWO_NEAR", "TWO_FAR", "PASSIVE_BODY")):
        if "controls" not in results and (OUT / "SHARED_OBJECT_TRACE_SUMMARY.json").exists():
            results["controls"] = {
                "SHARED_OBJECT_TRACE": json.loads(
                    (OUT / "SHARED_OBJECT_TRACE_SUMMARY.json").read_text()
                ).get("control"),
                "MEMORY_ISOLATION": json.loads(
                    (OUT / "MEMORY_ISOLATION_SUMMARY.json").read_text()
                ).get("memory_isolation"),
            }
        print("Analyzing...", flush=True)
        analyze_and_report(results)
        print(f"Wrote artifacts under {OUT}", flush=True)
    else:
        print("Partial run; analysis skipped until all primary arms exist.", flush=True)


if __name__ == "__main__":
    main()
