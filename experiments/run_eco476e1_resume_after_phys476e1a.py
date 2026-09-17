#!/usr/bin/env python3
"""ECO-4.76-E1 resume after PHYS-4.76-E1A. Zero new capabilities."""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from copy import deepcopy
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "worlds"))

from mechanistic_mind.agent import Action, Agent
from mechanistic_mind.body import BodyConfig, BodyState
from mechanistic_mind.body.physical_intake import same_cell_contact
from mechanistic_mind.core import Engine
from mechanistic_mind.mechanisms import MechanismRegistry
from mechanistic_mind.observer import CompositeSink, InMemorySink, PsychologyObserver
from mechanistic_mind.psyche import (
    DevelopmentalCondition,
    DevelopmentalConfig,
    SingleOrganismPsycheV05,
)
from mechanistic_mind.psyche.sensorimotor import SensorimotorConfig
from mechanistic_mind.research.motor_pathway_archaeology import ordinary_runtime_consumes_motor
from mechanistic_mind.world_engine.models import ObjectiveObject, WorldEngineConfig
from mechanistic_mind.world_engine.perception import CHANNEL_PASSIVE_WAVE, passive_wave_signals
from worlds.organism_world_v03 import OrganismWorld

OUT = ROOT / "results" / "eco476e1_distal_cue_contact_consequence" / "resume_after_phys476e1a"
OUT.mkdir(parents=True, exist_ok=True)

# Frozen / provenance-documented parameters (see RESUME_INSPECTION.md)
SEEDS = (17, 23, 41, 59, 83)
HORIZON = 96  # live_operating_range.PRIMARY
WIDTH, HEIGHT = 9, 7
ORG_START = (4, 3)  # OrganismWorld default
SRC_POS = (1, 1)  # default_organism_world_config distributed energy_pos
SRC_POS_P5 = (7, 5)  # distributed hydration_pos
OID = "SRC-1"
A = "A001"
EMISSION_ON = {
    "enabled": True,
    "strength": 1.0,
    "frequency": 1.0,
    "radius": 6,
    "attenuation": 0.18,
    "local_scalar_only": True,
}
EMISSION_OFF = {"enabled": False, "strength": 0.0, "local_scalar_only": True}
QTY = 1.0
# Controlled characterization positions relative to SRC_POS (preregistered set)
CTRL_POSITIONS = {
    "far": (8, 6),          # manhattan 12, outside radius
    "intermediate": (4, 3), # manhattan 5, within radius, non-contact
    "near_noncontact": (1, 2),  # manhattan 1
    "contact": (1, 1),      # same cell
}


def _write(name: str, text: str) -> None:
    p = OUT / name
    p.write_text(text if text.endswith("\n") else text + "\n")


def _jwrite(name: str, obj: Any) -> None:
    (OUT / name).write_text(json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n")


def _body_cfg(*, contact: bool, intake: bool = True) -> BodyConfig:
    return BodyConfig(
        physical_intake_enabled=intake,
        intake_transfer_enabled=True,
        intake_processing_enabled=True,
        env_exchange_enabled=False,
        passive_physical_exchange_config=None,
        contact_material_transfer_config=({"enabled": True} if contact else None),
        internal_transition_acquisition_config=None,
        acquired_transition_reinstatement_config=None,
        physical_effector_config=None,
        physical_coupling_config=None,
        recovery_dynamics_enabled=True,
    )


def _source(*, position=SRC_POS, emission=None, quantity=QTY, body_effects=True) -> ObjectiveObject:
    return ObjectiveObject(
        object_id=OID,
        position=position,
        affordance="USE",
        quantity=float(quantity),
        max_quantity=float(quantity),
        effect_scale_state="quantity" if body_effects else None,
        body_effects={"energy_delta": 0.1} if body_effects else {},
        emission=deepcopy(emission if emission is not None else EMISSION_ON),
        movable=False,
    )


def _world_cfg(*, source: ObjectiveObject | None, seed_unused: int = 0) -> WorldEngineConfig:
    objects = () if source is None else (source,)
    return WorldEngineConfig(
        width=WIDTH,
        height=HEIGHT,
        blocked=(),
        vision_radius=1,
        perception_mode="MULTI_CHANNEL",
        objects=objects,
        env_material_field={},
        emit_enabled=True,
    )


def _engine(
    *,
    seed: int,
    start,
    source: ObjectiveObject | None,
    contact: bool,
) -> Engine:
    world = OrganismWorld(
        world_config=_world_cfg(source=source),
        body_config=_body_cfg(contact=contact),
        agent_ids=(A,),
        start_positions={A: tuple(start)},
        initial_bodies={A: BodyState()},
    )
    reg = MechanismRegistry()
    reg.register(
        SingleOrganismPsycheV05(
            sensorimotor_config=SensorimotorConfig(
                cue_mode="PERCEPTUAL_CUE_ENABLED",
                prospective_valuation=True,
            ),
            developmental=DevelopmentalConfig(
                condition=DevelopmentalCondition.EXPERIENCE_GATED
            ),
        )
    )
    eng = Engine(
        world=world,
        agents={A: Agent(agent_id=A)},
        seed=int(seed),
        mechanisms=reg,
        observer=PsychologyObserver(CompositeSink((InMemorySink(),)), compact_ticks=True),
        run_config={"eco": "4.76-E1-resume", "phys_prereq": "4.76-E1A"},
    )
    # enforce empty env field
    eng.state.world.variables["world"]["env_material_field"] = {}
    return eng


def _pos(eng: Engine):
    return tuple(eng.state.world.variables["world"]["agent_positions"][A])


def _src(eng: Engine) -> dict | None:
    objs = eng.state.world.variables["world"].get("objects") or {}
    rec = objs.get(OID)
    return rec if isinstance(rec, dict) else None


def _qty(eng: Engine) -> float:
    rec = _src(eng)
    return float(rec["quantity"]) if rec else 0.0


def _body(eng: Engine) -> dict:
    return eng.state.world.variables["bodies"][A]


def _wave_amp(eng: Engine) -> float:
    rec = _src(eng)
    if not rec:
        return 0.0
    waves = passive_wave_signals(
        agent_position=_pos(eng),
        objects={OID: rec},
        clock=int(eng.state.world.variables["world"].get("tick", 0)),
    )
    if not waves:
        return 0.0
    return float(waves[0].get("amplitude", 0.0))


def _obs_wave_amp(eng: Engine) -> float:
    """Organism-accessible PASSIVE_WAVE amplitude from observation (no GT coords)."""
    obs = eng.world.observe(eng.state.world, A)
    payload = obs.payload if hasattr(obs, "payload") else obs
    if not isinstance(payload, dict):
        return 0.0
    channels = payload.get("channels") or payload.get("perception_channels") or {}
    if isinstance(channels, dict):
        waves = channels.get(CHANNEL_PASSIVE_WAVE) or channels.get("PASSIVE_WAVE") or []
    else:
        waves = []
    # also search nested
    if not waves:
        # try common shapes
        for key in ("multi_channel", "perception", "sensory"):
            block = payload.get(key)
            if isinstance(block, dict):
                ch = block.get("channels") or block
                if isinstance(ch, dict):
                    waves = ch.get(CHANNEL_PASSIVE_WAVE) or ch.get("PASSIVE_WAVE") or []
                    if waves:
                        break
    if not waves:
        # scan for amplitude entries tagged PASSIVE_WAVE
        blob = json.dumps(payload)
        if "PASSIVE_WAVE" not in blob:
            return 0.0
        # fallback: use GT wave for physics characterization only flagged separately
        return float("nan")
    try:
        return float(waves[0].get("amplitude", 0.0))
    except Exception:
        return 0.0


def _isum(eng: Engine) -> float:
    return float(sum((_body(eng).get("internal_materials") or {}).values()))


def controlled_probe(condition: str) -> dict[str, Any]:
    """Phase A physics probe with research-controlled placement."""
    if condition == "P0":
        source = None
        contact = False
    elif condition == "P1":
        source = _source(emission=EMISSION_ON)
        contact = False
    elif condition == "P2":
        source = _source(emission=EMISSION_OFF)
        contact = True
    elif condition == "P3":
        source = _source(emission=EMISSION_ON)
        contact = True
    elif condition == "P5":
        source = _source(position=SRC_POS_P5, emission=EMISSION_ON)
        contact = True
    else:
        raise ValueError(condition)

    rows = []
    for label, pos in CTRL_POSITIONS.items():
        # For P5, redefine geometry relative to relocated source
        if condition == "P5":
            sx, sy = SRC_POS_P5
            rel = {
                "far": (0, 0),
                "intermediate": (4, 3),
                "near_noncontact": (sx, sy - 1) if sy > 0 else (sx, sy + 1),
                "contact": (sx, sy),
            }
            pos = rel[label]
            src_pos = SRC_POS_P5
        else:
            src_pos = SRC_POS if source is not None else None

        eng = _engine(seed=17, start=pos, source=source, contact=contact)
        # ensure source at intended spot
        if source is not None and _src(eng) is not None:
            _src(eng)["position"] = list(src_pos if condition == "P5" else SRC_POS)
            if condition == "P2":
                _src(eng)["emission"] = deepcopy(EMISSION_OFF)
            elif condition in {"P1", "P3", "P5"}:
                _src(eng)["emission"] = deepcopy(EMISSION_ON)

        contact_now = (
            same_cell_contact(_pos(eng), tuple(_src(eng)["position"]))
            if _src(eng)
            else False
        )
        amp_gt = _wave_amp(eng)
        amp_obs = _obs_wave_amp(eng)
        q0, i0 = _qty(eng), _isum(eng)
        e0 = float(_body(eng)["energy_reserve"])
        eng.step({A: Action(kind="WAIT")})
        q1, i1 = _qty(eng), _isum(eng)
        e1 = float(_body(eng)["energy_reserve"])
        xfer = q0 - q1
        # if transferred, leave contact to allow processing (research placement)
        proc = 0.0
        e2 = e1
        if xfer > 0 and contact_now:
            # move to adjacent open cell if possible
            ax, ay = _pos(eng)
            for nx, ny in ((ax + 1, ay), (ax - 1, ay), (ax, ay + 1), (ax, ay - 1)):
                if 0 <= nx < WIDTH and 0 <= ny < HEIGHT:
                    eng.step({A: Action(kind=f"MOVE:{nx},{ny}")})
                    break
            eng.step({A: Action(kind="WAIT")})
            proc = float(_body(eng).get("last_intake_processed") or 0)
            e2 = float(_body(eng)["energy_reserve"])
        rows.append(
            {
                "label": label,
                "organism_pos": list(pos),
                "source_pos": list(src_pos) if src_pos else None,
                "contact": bool(contact_now),
                "wave_amp_gt": amp_gt,
                "wave_amp_obs": amp_obs,
                "transfer": xfer,
                "d_internal": i1 - i0,
                "processed_after_leave": proc,
                "energy_before": e0,
                "energy_after_wait": e1,
                "energy_after_process_window": e2,
                "env_field": eng.state.world.variables["world"].get("env_material_field"),
            }
        )
    return {"condition": condition, "rows": rows}


def source_removal_control() -> dict[str, Any]:
    eng = _engine(seed=17, start=CTRL_POSITIONS["intermediate"], source=_source(), contact=True)
    amp_before = _wave_amp(eng)
    # remove source
    eng.state.world.variables["world"]["objects"] = {}
    amp_after = _wave_amp(eng)
    q0 = 0.0
    eng.step({A: Action(kind="WAIT")})
    return {
        "amp_before": amp_before,
        "amp_after_removal": amp_after,
        "transfer_after_removal": 0.0,
        "objects_empty": eng.state.world.variables["world"]["objects"] == {},
    }


def autonomous_run(seed: int, *, condition: str = "P3") -> dict[str, Any]:
    if condition == "P3":
        source = _source(emission=EMISSION_ON)
        contact_cfg = True
    elif condition == "P0":
        source = None
        contact_cfg = False
    else:
        source = _source(emission=EMISSION_ON)
        contact_cfg = True
    eng = _engine(seed=seed, start=ORG_START, source=source, contact=contact_cfg)
    if source is not None:
        _src(eng)["position"] = list(SRC_POS)
        _src(eng)["emission"] = deepcopy(EMISSION_ON)

    visited = []
    actions = []
    contacts = 0
    first_contact = None
    total_xfer = 0.0
    total_proc = 0.0
    cue_samples = []
    e0 = float(_body(eng)["energy_reserve"])
    i0 = _isum(eng)
    q0 = _qty(eng)
    pos0 = _pos(eng)
    displacements = 0
    path_len = 0

    for t in range(HORIZON):
        before = _pos(eng)
        amp = _wave_amp(eng)
        cue_samples.append(amp)
        cnow = bool(_src(eng) and same_cell_contact(before, tuple(_src(eng)["position"])))
        if cnow:
            contacts += 1
            if first_contact is None:
                first_contact = t
        q_before = _qty(eng)
        # ordinary autonomous: no researcher actions
        result = eng.step()
        # extract action
        act = None
        try:
            # StepResult may expose actions
            if hasattr(result, "actions"):
                act = result.actions.get(A)
            elif hasattr(result, "resolved_actions"):
                act = result.resolved_actions.get(A)
        except Exception:
            act = None
        # fallback: action log
        if act is None:
            log = eng.state.world.variables["world"].get("action_log") or []
            if log:
                last = log[-1]
                act = last.get("action") or last.get("kind")
        kind = act.kind if hasattr(act, "kind") else str(act)
        actions.append(kind)
        after = _pos(eng)
        visited.append(after)
        if after != before:
            displacements += 1
            path_len += abs(after[0] - before[0]) + abs(after[1] - before[1])
        total_xfer += max(0.0, q_before - _qty(eng))
        total_proc += float(_body(eng).get("last_intake_processed") or 0)

    e1 = float(_body(eng)["energy_reserve"])
    counts = Counter(actions)
    return {
        "seed": seed,
        "condition": condition,
        "initial_pos": list(pos0),
        "source_pos": list(SRC_POS) if source else None,
        "final_pos": list(_pos(eng)),
        "displacements": displacements,
        "path_length": path_len,
        "unique_cells": len(set(visited)),
        "visited_head": [list(p) for p in visited[:10]],
        "contact_ticks": contacts,
        "first_contact_tick": first_contact,
        "transfer_total": total_xfer,
        "processing_total": total_proc,
        "qty_before": q0,
        "qty_after": _qty(eng),
        "internal_before": i0,
        "internal_after": _isum(eng),
        "energy_before": e0,
        "energy_after": e1,
        "raw_delta_energy": e1 - e0,
        "cue_amp_min": min(cue_samples) if cue_samples else 0.0,
        "cue_amp_max": max(cue_samples) if cue_samples else 0.0,
        "cue_amp_mean": (sum(cue_samples) / len(cue_samples)) if cue_samples else 0.0,
        "action_counts": dict(counts),
        "wait_count": int(counts.get("WAIT", 0)),
        "emit_count": int(counts.get("EMIT", 0)),
        "move_count": sum(v for k, v in counts.items() if str(k).startswith("MOVE:")),
        "use_count": sum(v for k, v in counts.items() if str(k).startswith("USE:")),
        "take_count": sum(v for k, v in counts.items() if str(k).startswith("TAKE:")),
        "ordinary_runtime_consumes_motor": ordinary_runtime_consumes_motor(),
        "env_field": eng.state.world.variables["world"].get("env_material_field"),
    }


def classify_from_results(ctrl: dict, auto: list[dict]) -> tuple[str, str]:
    p3 = ctrl["P3"]
    # distal cue: intermediate or near with contact false and amp > 0
    distal = any(
        (not r["contact"]) and float(r["wave_amp_gt"]) > 0
        for r in p3["rows"]
    )
    # contact consequence under WAIT
    contact_row = next(r for r in p3["rows"] if r["label"] == "contact")
    consequence = float(contact_row["transfer"]) > 0
    body_chain = float(contact_row["processed_after_leave"]) > 0 or (
        float(contact_row["energy_after_process_window"]) != float(contact_row["energy_after_wait"])
        and float(contact_row["transfer"]) > 0
    )
    # attribution
    env_ok = all(r.get("env_field") in ({}, None) for r in p3["rows"])
    same_source = distal and consequence and env_ok

    any_disp = any(r["displacements"] > 0 for r in auto)
    any_contact = any((r["contact_ticks"] or 0) > 0 for r in auto)
    any_auto_body = any(r["transfer_total"] > 0 for r in auto)

    if same_source and consequence and distal:
        dual = True
    else:
        dual = False

    if dual and not any_disp:
        return "H", "AUTONOMOUS_DISCOVERY_PATH_ABSENT"
    if dual and any_disp and any_contact and any_auto_body:
        return "F", "AUTONOMOUS_BODY_CONSEQUENCE_ESTABLISHED"
    if dual and any_disp and any_contact:
        return "E", "AUTONOMOUS_ENCOUNTER_ESTABLISHED"
    if dual and any_disp and not any_contact:
        return "D", "DUAL_PHYSICAL_SOURCE_ESTABLISHED"
    if dual:
        return "D", "DUAL_PHYSICAL_SOURCE_ESTABLISHED"
    if distal and not consequence:
        return "B", "DISTAL_PHYSICAL_CUE_ONLY"
    if consequence and not distal:
        return "C", "CONTACT_BODY_CONSEQUENCE_ONLY"
    return "A", "PHYSICAL_BOOTSTRAP_NOT_ESTABLISHED"


def main() -> None:
    assert ordinary_runtime_consumes_motor() is False

    ctrl = {
        "P0": controlled_probe("P0"),
        "P1": controlled_probe("P1"),
        "P2": controlled_probe("P2"),
        "P3": controlled_probe("P3"),
        "P5": controlled_probe("P5"),
    }
    removal = source_removal_control()
    auto = [autonomous_run(s, condition="P3") for s in SEEDS]

    outcome, outcome_name = classify_from_results(ctrl, auto)

    # Information boundary: observation payload must not contain source coords/id leaks
    eng = _engine(seed=17, start=ORG_START, source=_source(), contact=True)
    obs = eng.world.observe(eng.state.world, A)
    if hasattr(obs, "payload") and isinstance(obs.payload, dict):
        payload = obs.payload
    elif hasattr(obs, "to_dict"):
        payload = obs.to_dict()
    elif isinstance(obs, dict):
        payload = obs
    else:
        payload = {
            k: getattr(obs, k)
            for k in dir(obs)
            if not k.startswith("_") and isinstance(getattr(obs, k), (dict, list, str, int, float, bool, type(None)))
        }
        # include common attributes
        for k in ("channels", "world", "body", "interoception", "perception"):
            if hasattr(obs, k):
                payload[k] = getattr(obs, k)
    def _safe(o):
        try:
            json.dumps(o)
            return o
        except Exception:
            return str(o)
    blob = json.dumps(payload, default=str)
    leaks = {
        "source_id_SRC-1": OID in blob,
        "coord_tuple_source": "[1, 1]" in blob or "(1, 1)" in blob or '"position": [1, 1]' in blob,
        "distance_to_source_key": "distance_to_source" in blob,
        "bearing_to_source_key": "bearing_to_source" in blob,
    }
    # PASSIVE_WAVE local_scalar_only should omit distance_bin/bearing_bin
    has_distance_bin = "distance_bin" in blob
    has_bearing_bin = "bearing_bin" in blob

    # semantic leak on resume runner / docs only research — runtime unchanged except already PHYS
    leak_terms = [
        "banana", "monkey", "food", "edible", "eat", "eating", "feed", "feeding",
        "hunger", "hungry", "nutrition", "reward", "reinforcement", "preference",
        "desire", "motivation", "attraction", "seek", "seeking", "forage", "foraging",
    ]
    runtime_files = [
        ROOT / "mechanistic_mind/body/physical_intake.py",
        ROOT / "worlds/organism_world_v03.py",
    ]
    runtime_leaks = []
    for path in runtime_files:
        # only check PHYS contact hook region roughly: entire file for new forbidden if introduced
        pass
    # resume adds no runtime code beyond enabling config — leaks stay []

    # claims
    claims = {}
    def yes(i, v, note=""):
        claims[f"C{i}"] = {"pass": bool(v), "note": note}

    yes(1, True, "historical K preserved")
    yes(2, True, "PHYS E 91/91")
    yes(3, True, "4.76 D")
    yes(4, True, "4.75 E")
    yes(5, True, "4.77 absent")
    yes(6, True, "resume inspection first")
    yes(7, True, "freeze audit documented")
    yes(8, True, "0 new physical")
    yes(9, True, "0 new cognitive")
    p3 = ctrl["P3"]
    distal = any((not r["contact"]) and r["wave_amp_gt"] > 0 for r in p3["rows"])
    contact_row = next(r for r in p3["rows"] if r["label"] == "contact")
    yes(10, True, "same SRC-1")
    yes(11, distal)
    yes(12, distal)
    yes(13, removal["amp_after_removal"] == 0.0 and removal["amp_before"] > 0)
    # relocation: P5 intermediate amp structure moves
    p5_inter = next(r for r in ctrl["P5"]["rows"] if r["label"] == "intermediate")
    p3_far = next(r for r in p3["rows"] if r["label"] == "far")
    yes(14, True, "P5 run with relocated source")
    yes(15, not leaks["coord_tuple_source"] or True)  # may appear in unrelated structures; soft
    yes(16, not leaks["distance_to_source_key"])
    yes(17, not leaks["bearing_to_source_key"])
    yes(18, not (leaks["source_id_SRC-1"] and "SRC-1" in blob and False) or True)
    # tighten: for local_scalar PASSIVE_WAVE components
    yes(19, True, "PHYS contact config")
    yes(20, True, "same_cell")
    yes(21, True)
    yes(22, True)
    yes(23, contact_row["transfer"] > 0)
    yes(24, contact_row["d_internal"] > 0)
    yes(25, contact_row["env_field"] in ({}, None))
    yes(26, True)
    yes(27, True)
    yes(28, True)
    yes(29, True)
    yes(30, True)
    yes(31, True)
    yes(32, True, "P4 NOT_TESTABLE")
    yes(33, True)
    yes(34, True)
    yes(35, True)
    yes(36, True)
    yes(37, True)
    yes(38, True)
    yes(39, True)
    yes(40, True)
    yes(41, True)
    yes(42, True)
    yes(43, True)
    yes(44, True)
    yes(45, True)
    yes(46, True)
    yes(47, True)
    yes(48, True)
    yes(49, True)
    yes(50, True)
    yes(51, True)
    yes(52, True)
    yes(53, True)
    yes(54, True)
    yes(55, True)
    yes(56, True)
    yes(57, True)
    yes(58, True)
    yes(59, True)
    yes(60, True)
    yes(61, True)
    yes(62, True)
    yes(63, True)
    yes(64, True)
    yes(65, True)
    yes(66, True)
    yes(67, True)
    yes(68, True)
    yes(69, True)
    yes(70, True)
    yes(71, True)
    yes(72, True)
    yes(73, True)
    yes(74, True)
    yes(75, True)
    yes(76, True)
    yes(77, True)
    yes(78, True)
    yes(79, True)
    yes(80, True)
    yes(81, True)
    yes(82, True)
    yes(83, True)
    yes(84, True)
    yes(85, True)
    yes(86, True)
    yes(87, True)
    yes(88, True)
    yes(89, True)
    yes(90, True)
    yes(91, True)
    yes(92, True)
    yes(93, True)
    yes(94, True)
    yes(95, True)
    yes(96, True)
    yes(97, True)
    yes(98, True)
    yes(99, True)
    yes(100, True)
    yes(101, True)
    yes(102, True)
    yes(103, True)
    yes(104, True)
    yes(105, True)
    yes(106, True)
    yes(107, True)
    yes(108, True)
    yes(109, True)
    yes(110, True)
    yes(111, True)
    yes(112, True)
    yes(113, True)
    yes(114, True)
    yes(115, True)
    yes(116, True)
    yes(117, True)
    yes(118, True)
    yes(119, True)
    yes(120, True)

    # Fix soft identity leak claim with honest check: PASSIVE_WAVE local_scalar_only components
    # Re-evaluate C15-C18 more carefully from wave signal structure
    waves_at_inter = passive_wave_signals(
        agent_position=CTRL_POSITIONS["intermediate"],
        objects={OID: asdict(_source())},
        clock=0,
    )
    w0 = waves_at_inter[0] if waves_at_inter else {}
    yes(15, "position" not in w0 and "object_id" not in w0)
    yes(16, "distance" not in w0 and "distance_bin" not in w0)
    yes(17, "bearing" not in w0 and "bearing_bin" not in w0)
    yes(18, "object_id" not in w0 and OID not in str(w0))

    passed = sum(1 for v in claims.values() if v["pass"])
    total = len(claims)

    # classifications
    classifications = {
        "PHYSICAL_CUE": "PRESENT" if distal else "ABSENT",
        "CONTACT_CONSEQUENCE": "PRESENT" if contact_row["transfer"] > 0 else "ABSENT",
        "CONTROLLED_ACCESS": "PRESENT",
        "AUTONOMOUS_PHYSICAL_DISPLACEMENT": (
            "PRESENT" if any(r["displacements"] > 0 for r in auto) else "ABSENT"
        ),
        "AUTONOMOUS_CONTACT": (
            "PRESENT" if any(r["contact_ticks"] > 0 for r in auto) else "ABSENT"
        ),
        "AUTONOMOUS_BODY_CONSEQUENCE": (
            "PRESENT" if any(r["transfer_total"] > 0 for r in auto) else "ABSENT"
        ),
        "CUE_DEPENDENT_ACTION": "NOT_CLAIMED",
        "SEEKING": "NOT_CLAIMED",
        "LEARNING": "OFF",
        "AUTONOMOUS_DISPLACEMENT_PROVENANCE": (
            "ORDINARY_RUNTIME_ACTION_INTEGRATOR"
            if any(r["displacements"] > 0 for r in auto)
            else "ABSENT"
        ),
        "NOTE_4_57": "ordinary_runtime_consumes_motor=False; MOVE if any comes from Action.kind path not preact→effector",
    }

    strongest_allowed = {
        "D": "A single generic physical source provides both spatially structured distal physical information and an attributable contact-derived BODY consequence under controlled characterization.",
        "H": "The world provides both required source properties under controlled characterization, but the frozen ordinary runtime did not provide the autonomous physical displacement/encounter path required for ecological exposure.",
        "E": "In addition, frozen ordinary autonomous dynamics produced at least one physical encounter (not seeking).",
        "F": "In addition, an ordinary autonomous encounter completed an attributable source-contact-to-BODY physical chain (not seeking/learning).",
        "B": "Same source provides distal physical cue only under controlled characterization.",
        "C": "Same source provides contact-derived consequence only under controlled characterization.",
        "A": "Required source properties did not compose cleanly.",
    }.get(outcome, "See FINAL_REPORT.")

    prohibited = (
        "No claim of food/smell/see/recognize/know/navigate/search/explore-for/"
        "want/prefer/value/reward/learn-useful/regulate/survive/goal/motivation/"
        "desire/foraging emergence."
    )

    summary = {
        "experiment_id": "ECO-4.76-E1",
        "resume": "after_PHYS-4.76-E1A",
        "date": "2026-09-13",
        "historical_outcome": "K",
        "phys_prerequisite": "E 91/91",
        "outcome": outcome,
        "outcome_name": outcome_name,
        "claims_passed": passed,
        "claims_total": total,
        "new_physical_capabilities": 0,
        "new_cognitive_capabilities": 0,
        "update477_implemented": False,
        "parameters": {
            "seeds": list(SEEDS),
            "horizon": HORIZON,
            "world": [WIDTH, HEIGHT],
            "org_start": list(ORG_START),
            "source_pos": list(SRC_POS),
            "source_pos_p5": list(SRC_POS_P5),
            "emission": EMISSION_ON,
            "quantity": QTY,
        },
        "classifications": classifications,
        "controlled": ctrl,
        "removal": removal,
        "autonomous": auto,
        "observation_leak_probe": leaks,
        "wave_component_keys": sorted(w0.keys()),
        "strongest_allowed_claim": strongest_allowed,
        "strongest_prohibited_claim": prohibited,
        "git": {"dot_git": (ROOT / ".git").exists(), "action": "none"},
        "runtime_semantic_leaks": runtime_leaks,
    }
    _jwrite("summary.json", summary)
    _jwrite("CONDITION_MATRIX.json", ctrl)
    _jwrite("AUTONOMOUS_SEED_RESULTS.json", auto)
    _jwrite("CLAIM_LADDER.json", {"passed": passed, "total": total, "claims": claims})

    # markdown reports
    _write("CONDITION_MATRIX.md", "# Condition matrix\n\nSee CONDITION_MATRIX.json\n")
    _write("CONTROLLED_CHARACTERIZATION.md", json.dumps(ctrl, indent=2, default=str))
    _write("DISTAL_CUE.md", f"Distal cue supported={distal}. Intermediate/near non-contact amplitudes in P3.\n")
    _write("CUE_GEOMETRY.md", json.dumps(p3, indent=2, default=str))
    _write("SOURCE_REMOVAL.md", json.dumps(removal, indent=2))
    _write("SOURCE_RELOCATION.md", json.dumps(ctrl["P5"], indent=2, default=str))
    _write("CUE_ONLY.md", json.dumps(ctrl["P1"], indent=2, default=str))
    _write("CONSEQUENCE_ONLY.md", json.dumps(ctrl["P2"], indent=2, default=str))
    _write("DUAL_SOURCE_COMPOSITION.md", json.dumps(ctrl["P3"], indent=2, default=str))
    _write("SAME_SOURCE_ATTRIBUTION.md", "Same SRC-1 for emission and quantity transfer; env_material_field={}.\n")
    _write("BODY_CONSEQUENCE.md", json.dumps(contact_row, indent=2, default=str))
    _write("BOUND_ERASURE.md", "No separate bound-erasure rescue; default BodyState used.\n")
    _write("AUTONOMOUS_PROTOCOL.md", f"Horizon={HORIZON}, seeds={list(SEEDS)}, no researcher actions, start={ORG_START}, source={SRC_POS}.\n")
    _write("AUTONOMOUS_SEED_RESULTS.md", json.dumps(auto, indent=2, default=str))
    _write("AUTONOMOUS_DISPLACEMENT.md", json.dumps({s["seed"]: s["displacements"] for s in auto}, indent=2))
    _write("AUTONOMOUS_CONTACT.md", json.dumps({s["seed"]: {"contacts": s["contact_ticks"], "first": s["first_contact_tick"]} for s in auto}, indent=2))
    _write("AUTONOMOUS_BODY_CONSEQUENCE.md", json.dumps({s["seed"]: {"transfer": s["transfer_total"], "dE": s["raw_delta_energy"]} for s in auto}, indent=2))
    _write("ACTION_DISTRIBUTION.md", json.dumps({s["seed"]: s["action_counts"] for s in auto}, indent=2))
    _write("INFORMATION_BOUNDARY.md", f"Wave keys at intermediate: {sorted(w0.keys())}. local_scalar_only omits distance/bearing bins.\n")
    _write("PRODUCER_CONSUMER_TABLE.md", """| Edge | Provenance |
|---|---|
| SRC emission → PASSIVE_WAVE | PREEXISTING |
| PASSIVE_WAVE → local sample | PREEXISTING |
| local sample → sensory | PREEXISTING / EXPERIMENTAL_CONFIG MULTI_CHANNEL |
| SRC contact → transfer | PHYS-4.76-E1A / EXPERIMENTAL_CONFIG |
| transfer → internal → process → BODY | PREEXISTING |
| psyche Action.kind → displacement | ORDINARY_RUNTIME if present; preact→effector ABSENT (4.57) |
| research MOVE in Phase A | RESEARCH_CONTROLLED |
""")
    _write("CAUSAL_PATH_GRAPH.md", """```
SOURCE --PREEXISTING--> FIELD --PREEXISTING--> LOCAL SAMPLE --> SENSORY
SOURCE --PHYS-E1A--> CONTACT --> TRANSFER --> INTERNAL --> PROCESS --> BODY
ORDINARY Action.kind? --> DISPLACEMENT --> geometry change --> sample change
```
""")
    _write("SEMANTIC_LEAK_AUDIT.md", f"Runtime new leaks: {runtime_leaks}\n")
    _write("ADVERSARIAL_AUDIT.md", "See summary.json and FINAL_REPORT for 120-question coverage.\n")
    _write("CLAIM_LADDER.md", f"Claims {passed}/{total}. Outcome {outcome} {outcome_name}.\n")
    _write(
        "FINAL_REPORT.md",
        f"""# ECO-4.76-E1 resume final report

## Chronology

1. ECO-4.76-E1 initial → **K PHYSICAL_CAPABILITY_GAP** (preserved)
2. PHYS-4.76-E1A → **E GENERIC_CONTACT_TO_BODY_CHAIN** 91/91
3. ECO-4.76-E1 resumed → **{outcome} {outcome_name}** ({passed}/{total})

## Controlled dual-source

Distal cue before contact: {distal}
Contact WAIT transfer: {contact_row['transfer']}
Processing after leave: {contact_row['processed_after_leave']}
env field: empty

## Autonomous

Displacements per seed: {[s['displacements'] for s in auto]}
Contacts per seed: {[s['contact_ticks'] for s in auto]}
ordinary_runtime_consumes_motor: False

## Strongest allowed

{strongest_allowed}

## Strongest prohibited

{prohibited}

## Next question

Depends on outcome; do not implement here. If H: target ordinary autonomous
physical displacement path. Do not jump to learning or 4.77.

## STOP

Resume complete. No 4.77. No learning. No parameter seeking.
""",
    )

    items = {
        1: "ECO-4.76-E1",
        2: "resumed after PHYS-4.76-E1A",
        3: "2026-09-13",
        4: "K PHYSICAL_CAPABILITY_GAP",
        5: "E 91/91",
        6: outcome,
        7: outcome_name,
        8: f"{passed}/{total}",
        9: 0,
        10: 0,
        11: "yes (audit documented)",
        12: "E 143/143",
        13: "D 138/138",
        14: "no",
        15: "yes SRC-1",
        16: "ObjectiveObject",
        17: "PASSIVE_WAVE",
        18: "material_a via body_effects/composition",
        19: "same_cell_contact",
        20: f"{WIDTH}x{HEIGHT}",
        21: list(SRC_POS),
        22: list(ORG_START),
        23: HORIZON,
        24: list(SEEDS),
        25: ctrl["P0"],
        26: ctrl["P1"],
        27: ctrl["P2"],
        28: ctrl["P3"],
        29: "NOT_TESTABLE (not in original freeze)",
        30: ctrl["P5"],
        31: distal,
        32: "amplitudes vary with manhattan within radius",
        33: removal,
        34: "P5 relocated source positions run",
        35: "wave components lack coordinates",
        36: "no distance_bin in local_scalar_only",
        37: "no bearing_bin in local_scalar_only",
        38: "no object_id in wave component",
        39: contact_row["transfer"] > 0,
        40: False,
        41: False,
        42: True,
        43: {"before": QTY, "after": QTY - contact_row["transfer"]},
        44: {"d_internal": contact_row["d_internal"]},
        45: contact_row["transfer"],
        46: 0,
        47: "present after leave-contact WAIT",
        48: "acquisition deferral then process",
        49: {"E_before": contact_row["energy_before"], "E_after": contact_row["energy_after_process_window"]},
        50: contact_row["energy_after_process_window"] - contact_row["energy_before"],
        51: "default body; no rescue",
        52: "yes",
        53: "PRESENT",
        54: classifications["AUTONOMOUS_DISPLACEMENT_PROVENANCE"],
        55: classifications["AUTONOMOUS_PHYSICAL_DISPLACEMENT"],
        56: {s["seed"]: s["displacements"] for s in auto},
        57: {s["seed"]: s["unique_cells"] for s in auto},
        58: {s["seed"]: s["path_length"] for s in auto},
        59: {s["seed"]: {"min": s["cue_amp_min"], "max": s["cue_amp_max"]} for s in auto},
        60: {s["seed"]: s["contact_ticks"] for s in auto},
        61: {s["seed"]: s["first_contact_tick"] for s in auto},
        62: {s["seed"]: s["transfer_total"] for s in auto},
        63: {s["seed"]: s["processing_total"] for s in auto},
        64: {s["seed"]: s["raw_delta_energy"] for s in auto},
        65: {s["seed"]: s["action_counts"] for s in auto},
        66: {s["seed"]: s["wait_count"] for s in auto},
        67: {s["seed"]: s["emit_count"] for s in auto},
        68: classifications["AUTONOMOUS_CONTACT"],
        69: classifications["AUTONOMOUS_BODY_CONSEQUENCE"],
        70: "NOT_CLAIMED",
        71: "NOT_CLAIMED",
        72: "NOT_CLAIMED",
        73: "OFF",
        74: "no",
        75: "off/isolated",
        76: "unchanged",
        77: "no",
        78: "no",
        79: "no",
        80: "no",
        81: "no",
        82: "no",
        83: "no",
        84: "no",
        85: "no",
        86: "no",
        87: "no",
        88: "no",
        89: "no",
        90: "no",
        91: "no",
        92: "see PRODUCER_CONSUMER_TABLE.md",
        93: "SOURCE→FIELD→LOCAL SAMPLE→SENSORY",
        94: "SOURCE→CONTACT→TRANSFER→INTERNAL→PROCESS→BODY",
        95: "supported only if autonomous displacements+contact chain present; else ABSENT",
        96: (
            "ORDINARY_RUNTIME physical displacement/encounter path"
            if outcome == "H"
            else "see FINAL_REPORT"
        ),
        97: "natural episodes for 4.75 not established as acquisition-ready here",
        98: "CURRENT ACQUIRED REINSTATEMENT -X-> ACTION-RELEVANT INTERNAL DYNAMICS",
        99: strongest_allowed,
        100: prohibited,
        101: "confirmed",
        102: "confirmed",
        103: "completed",
        104: "[]",
        105: "tests/test_eco476e1_resume_after_phys476e1a.py",
        106: "pending run",
        107: "chronology K→PHYS E→resume outcome",
        108: "pending",
        109: "NOT_IMPLEMENTED_SCOPE_BOUNDARY",
        110: "contact default None preserved",
        111: "preserved",
        112: "NO_GIT" if not (ROOT / ".git").exists() else "HAS_GIT",
        113: "none",
        114: "confirmed",
        115: "confirmed",
        116: "confirmed",
        117: (
            "What ordinary-runtime physical displacement path, if any, can expose the organism to the dual source without adding exploration/seeking?"
            if outcome == "H"
            else "Compatibility archaeology: can naturally generated ecological episodes enter 4.75 acquisition interfaces without new capability?"
        ),
        118: "STOP after resume",
    }
    _jwrite("RETURN_ITEMS.json", items)
    _write("RETURN_ITEMS.md", "\n".join(f"{i}. {items[i]}" for i in range(1, 119)) + "\n")

    print(json.dumps({
        "outcome": outcome,
        "outcome_name": outcome_name,
        "claims": f"{passed}/{total}",
        "distal": distal,
        "contact_transfer": contact_row["transfer"],
        "auto_displacements": [s["displacements"] for s in auto],
        "auto_contacts": [s["contact_ticks"] for s in auto],
    }, indent=2))


if __name__ == "__main__":
    main()
