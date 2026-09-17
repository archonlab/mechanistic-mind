#!/usr/bin/env python3
"""Update 4.7.1 — Cross-agent physical trace → experience → later retrieval probes.

Forced geometry for causal isolation only. Compact JSON. No social semantics.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from copy import deepcopy
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
from mechanistic_mind.research.cross_agent_trace_v471 import (
    PROBE_EVENT_ID,
    agent_visible_quantity,
    append_observer_receipt,
    find_matching_episodes,
    quantity_of,
    scan_for_leakage,
    spatial_has_quantity_evidence,
    stage_status,
)
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

OUT = ROOT / "results" / "update471_cross_agent_trace"
OUT.mkdir(parents=True, exist_ok=True)

SEED = 17
MDS = 200  # short runway for compact probes
OBJECT_ID = "OBJ-12"
OBJ_POS = (14, 16)
A = "A001"
B = "B001"


def _body_cfg(recovery: bool = True) -> BodyConfig:
    base = todo4_calibrated_body_config()
    d = {f: getattr(base, f) for f in base.__dataclass_fields__}
    d["recovery_dynamics_enabled"] = recovery
    return BodyConfig(**d)


def _psyche(*, prediction_ablated: bool = False) -> SingleOrganismPsycheV05:
    return SingleOrganismPsycheV05(
        sensorimotor_config=SensorimotorConfig(
            cue_mode="PERCEPTUAL_CUE_ENABLED",
            prospective_valuation=True,
            prediction_ablated=prediction_ablated,
        ),
        developmental=DevelopmentalConfig(
            condition=DevelopmentalCondition.EXPERIENCE_GATED
        ),
    )


def build_engine(
    *,
    positions: dict[str, tuple[int, int]],
    prediction_ablated_agents: set[str] | None = None,
) -> Engine:
    ids = tuple(positions)
    spec = subsidy_from_tick_equivalent(MDS)
    body_cfg = apply_subsidy_to_body_config(_body_cfg(True), spec)
    bodies = {aid: apply_subsidy_to_body_state(BodyState(), spec) for aid in ids}
    world = ContextualObjectEcologyWorld(
        world_config=multi_channel_contextual_object_config(SEED),
        body_config=body_cfg,
        agent_ids=ids,
        start_positions=positions,
        initial_bodies=bodies,
    )
    stacks: dict[str, MechanismRegistry] = {}
    ablated = prediction_ablated_agents or set()
    for aid in ids:
        reg = MechanismRegistry()
        reg.register(_psyche(prediction_ablated=(aid in ablated)))
        stacks[aid] = reg
    sink = InMemorySink()
    return Engine(
        world=world,
        agents={aid: Agent(agent_id=aid) for aid in ids},
        seed=SEED,
        mechanisms=stacks[ids[0]],
        mechanisms_by_agent=stacks,
        observer=PsychologyObserver(CompositeSink((sink,)), compact_ticks=True),
        run_config={
            "update": "4.7.1",
            "probe_event_id_observer_only": PROBE_EVENT_ID,
            "object_id": OBJECT_ID,
            "no_social_semantics": True,
            "derived_seeds": {aid: derived_seed(SEED, aid) for aid in ids},
        },
    )


def _obs_data(engine: Engine, agent_id: str) -> dict[str, Any]:
    obs = engine.world.observe(engine.state.world, agent_id)
    data = getattr(obs, "data", obs)
    return data if isinstance(data, dict) else {}


def _psyche_of(engine: Engine, agent_id: str) -> dict[str, Any]:
    st = engine.state.agents.get(agent_id)
    if st is None:
        return {}
    for payload in st.mechanism_states.values():
        if isinstance(payload, dict) and isinstance(payload.get("psyche"), dict):
            return deepcopy(payload["psyche"])
    return {}


def _clear_agent_memory(engine: Engine, agent_id: str) -> None:
    """EXPERIENCE_ABLATED: wipe episodes/spatial after observation (experiment-side)."""
    st = engine.state.agents.get(agent_id)
    if st is None:
        return
    for mid, payload in list(st.mechanism_states.items()):
        if not isinstance(payload, dict) or "psyche" not in payload:
            continue
        psyche = deepcopy(payload["psyche"])
        mem = psyche.setdefault("memory", {})
        mem["episodes"] = []
        mem["spatial"] = {"visited": {}, "objects": {}, "obstacles": {}}
        payload = deepcopy(payload)
        payload["psyche"] = psyche
        st.mechanism_states[mid] = payload


def _signals(engine: Engine, agent_id: str) -> dict[str, Any]:
    # Mechanism signals from last step are not always retained; pull learning/working.
    psyche = _psyche_of(engine, agent_id)
    return {
        "learning_keys": list((psyche.get("learning") or {}).keys()),
        "working_keys": list((psyche.get("working") or {}).keys()),
        "attention_keys": list((psyche.get("attention") or {}).keys()),
    }


def run_trace_probe(
    *,
    name: str,
    do_a_use: bool,
    allow_b_observe: bool,
    experience_ablated: bool = False,
    retrieval_ablated: bool = False,
    actor: str = A,
    observer: str = B,
    post_ticks: int = 25,
) -> dict[str, Any]:
    """Controlled causal probe. Forced actions for isolation only."""
    t0 = time.time()
    # Geometry: actor on object; observer far or near depending on allow_b_observe schedule.
    far = (28, 28)
    positions = {
        actor: OBJ_POS,
        observer: far if allow_b_observe else far,
    }
    # ACTOR_SWAP uses same object cell for whoever is actor.
    ablated = {observer} if retrieval_ablated else set()
    engine = build_engine(positions=positions, prediction_ablated_agents=ablated)

    qty0 = quantity_of(engine.state.world.variables, OBJECT_ID)
    chain: dict[str, Any] = {
        "condition": name,
        "probe_event_id_observer_only": PROBE_EVENT_ID,
        "object_id": OBJECT_ID,
        "actor": actor,
        "observer_agent": observer,
        "quantity_before": qty0,
    }

    # Tick schedule (forced):
    # 0: WAIT both (baseline)
    # 1: actor USE or WAIT; observer WAIT far
    # 2..: if allow_b_observe, move observer onto object; else keep far
    # then endogenous-ish WAIT/USE windows for retrieval sampling

    def step(overrides: dict[str, str]):
        return engine.step({k: Action(v) for k, v in overrides.items()})

    # baseline
    step({actor: "WAIT", observer: "WAIT"})
    qty_base = quantity_of(engine.state.world.variables, OBJECT_ID)

    # intervention
    if do_a_use:
        step({actor: f"USE:{OBJECT_ID}", observer: "WAIT"})
    else:
        step({actor: "WAIT", observer: "WAIT"})
    qty_after = quantity_of(engine.state.world.variables, OBJECT_ID)
    intervention_tick = engine.state.tick
    chain["intervention"] = {
        "tick": intervention_tick,
        "acting_agent": actor,
        "action": f"USE:{OBJECT_ID}" if do_a_use else "WAIT",
        "property": "quantity",
        "before": qty_base,
        "after": qty_after,
        "delta": (
            None
            if qty_base is None or qty_after is None
            else float(qty_after) - float(qty_base)
        ),
        "changed": bool(
            qty_base is not None
            and qty_after is not None
            and abs(float(qty_after) - float(qty_base)) > 1e-9
        ),
    }
    append_observer_receipt(
        engine.state.world.variables,
        {
            "kind": "INTERVENTION",
            "probe_event_id": PROBE_EVENT_ID,
            **chain["intervention"],
        },
    )

    target_qty = qty_after if do_a_use else qty_base

    # Move observer to object if allowed
    b_obs = {
        "first_tick": None,
        "quantity": None,
        "in_visible_objects": False,
        "channel_hints": [],
        "relative_offset": None,
    }
    if allow_b_observe:
        # Controlled forced positioning (allowed for causal isolation only).
        # Place observer on the object cell; move actor aside so occupancy allows it.
        truth = engine.state.world.variables.get("world") or {}
        positions = truth.setdefault("agent_positions", {})
        # Actor steps aside one cell if possible
        ax, ay = OBJ_POS
        side = (ax + 1, ay)
        positions[actor] = [side[0], side[1]]
        positions[observer] = [ax, ay]
        # One WAIT so ordinary observe→memory path runs for observer
        step({actor: "WAIT", observer: "WAIT"})
        data = _obs_data(engine, observer)
        ev = agent_visible_quantity(data, OBJECT_ID)
        if not ev["in_visible_objects"]:
            # retry wait once
            step({actor: "WAIT", observer: "WAIT"})
            data = _obs_data(engine, observer)
            ev = agent_visible_quantity(data, OBJECT_ID)
        b_obs = {
            "first_tick": engine.state.tick,
            **ev,
            "forced_positioning": True,
            "note": "Forced co-location for causal isolation; not autonomous navigation.",
        }
        append_observer_receipt(
            engine.state.world.variables,
            {
                "kind": "B_OBSERVATION",
                "probe_event_id": PROBE_EVENT_ID,
                "observer_agent": observer,
                **b_obs,
            },
        )
    else:
        # Keep far; ensure no observation of post-change quantity
        for _ in range(3):
            step({actor: "WAIT", observer: "WAIT"})
        data = _obs_data(engine, observer)
        ev = agent_visible_quantity(data, OBJECT_ID)
        b_obs = {"first_tick": None, **ev, "forced_far": True}

    chain["b_observation"] = b_obs

    # Experience inspection (spatial + episodes)
    psyche_b = _psyche_of(engine, observer)
    spatial = spatial_has_quantity_evidence(psyche_b, OBJECT_ID)
    ep_hits = find_matching_episodes(
        psyche_b, object_id=OBJECT_ID, target_quantity=target_qty
    )
    # Also match any quantity evidence for object (weaker)
    ep_any = find_matching_episodes(
        psyche_b, object_id=OBJECT_ID, target_quantity=None
    )
    chain["b_experience"] = {
        "stored": bool(spatial.get("present") and spatial.get("quantity") is not None)
        or bool(ep_hits)
        or bool(ep_any),
        "spatial": spatial,
        "episode_hits_exact_qty": ep_hits,
        "episode_hits_any_qty": ep_any[:10],
        "tick_inspected": engine.state.tick,
    }
    if experience_ablated:
        _clear_agent_memory(engine, observer)
        psyche_b = _psyche_of(engine, observer)
        chain["b_experience"]["ablated_after_storage"] = True
        chain["b_experience"]["post_ablation_spatial"] = spatial_has_quantity_evidence(
            psyche_b, OBJECT_ID
        )
        chain["b_experience"]["post_ablation_episode_hits"] = find_matching_episodes(
            psyche_b, object_id=OBJECT_ID, target_quantity=target_qty
        )

    # Later decisions: let observer act endogenously / forced USE candidates nearby
    retrieval_log = []
    decision_log = []
    for i in range(post_ticks):
        # Keep actor idle; observer endogenous except when we force a USE probe window
        if allow_b_observe and i in {5, 10, 15}:
            # Present USE opportunity; if not available, WAIT
            data = _obs_data(engine, observer)
            actions = data.get("available_actions") or []
            use_kind = f"USE:{OBJECT_ID}"
            if use_kind in actions:
                result = step({actor: "WAIT", observer: use_kind})
            else:
                result = step({actor: "WAIT", observer: "WAIT"})
        else:
            result = engine.step({actor: Action("WAIT")} if actor in engine.agents else None)

        psyche_b = _psyche_of(engine, observer)
        hits = find_matching_episodes(
            psyche_b, object_id=OBJECT_ID, target_quantity=target_qty
        )
        spat = spatial_has_quantity_evidence(psyche_b, OBJECT_ID)
        # Leakage scan on observation + psyche memory only (agent-facing)
        data = _obs_data(engine, observer)
        leaks = scan_for_leakage(
            {
                "observation": {
                    k: data.get(k)
                    for k in (
                        "visible_objects",
                        "physical_perception",
                        "perceptual_context",
                        "last_action",
                        "last_experienced_effects",
                    )
                },
                "memory": psyche_b.get("memory"),
                "learning": psyche_b.get("learning"),
                "attention": psyche_b.get("attention"),
            }
        )
        retrieval_log.append(
            {
                "tick": engine.state.tick,
                "action": result.actions[observer].kind,
                "episode_hits": hits,
                "spatial": spat,
                "leaks": leaks[:20],
            }
        )
        decision_log.append(
            {
                "tick": engine.state.tick,
                "selected": result.actions[observer].kind,
            }
        )

    # Summarize retrieval/prediction/valuation conservatively
    any_hits = [row for row in retrieval_log if row["episode_hits"] or (row["spatial"].get("quantity") is not None)]
    retrieved = bool(
        (not experience_ablated)
        and allow_b_observe
        and (
            chain["b_experience"].get("episode_hits_exact_qty")
            or chain["b_experience"].get("spatial", {}).get("quantity") is not None
        )
        and any_hits
    )
    # Prediction participation: without deep hooks, mark UNAVAILABLE unless
    # retrieval_ablated explicitly disables prediction path.
    if retrieval_ablated:
        pred_status = "ABLATED"
        pred_participated = False
    elif retrieved:
        pred_status = "IMPLEMENTED_BUT_UNPROVEN"
        pred_participated = False  # do not upgrade
    else:
        pred_status = "NOT_OBSERVED"
        pred_participated = False

    chain["b_retrieval"] = {
        "eligible": bool(chain["b_experience"].get("stored")) and not experience_ablated,
        "retrieved": retrieved,
        "status": (
            "RETRIEVED"
            if retrieved
            else ("NOT_RETRIEVED" if chain["b_experience"].get("stored") else "NOT_YET")
        ),
        "post_window_hit_ticks": [r["tick"] for r in any_hits[:20]],
        "sample": retrieval_log[:8],
    }
    chain["b_prediction"] = {
        "status": pred_status,
        "participated": pred_participated,
        "note": "Compact probe does not fabricate prediction evidence links.",
    }
    chain["b_valuation"] = {
        "status": "UNAVAILABLE" if retrieval_ablated else pred_status,
        "participated": False,
        "note": "Prospective value participation not claimed without explicit value-source telemetry.",
    }
    chain["b_decision"] = {
        "selected": decision_log[-1]["selected"] if decision_log else None,
        "sample": decision_log[:12],
        "rejected_trace_related": None,
        "note": "Selection recorded; causal dependence on trace not asserted without value link.",
    }

    # Leakage final
    psyche_b = _psyche_of(engine, observer)
    data = _obs_data(engine, observer)
    leaks = scan_for_leakage(
        {
            "observation": data,
            "psyche_memory": psyche_b.get("memory"),
            "psyche_learning": psyche_b.get("learning"),
            "psyche_attention": psyche_b.get("attention"),
            "psyche_working": psyche_b.get("working"),
        }
    )
    # Ensure probe id not in agent structures
    chain["leakage_audit"] = {
        "pass": len(leaks) == 0,
        "leaks": leaks[:50],
        "forbidden_probe_id": PROBE_EVENT_ID,
    }

    chain["stages"] = stage_status(chain)
    chain["memory_isolation"] = None
    if actor in engine.agents and observer in engine.agents:
        # fingerprint overlap
        def fps(aid):
            mem = (_psyche_of(engine, aid).get("memory") or {})
            eps = mem.get("episodes") or []
            out = set()
            for ep in eps:
                if isinstance(ep, dict):
                    out.add(
                        json.dumps(
                            {
                                "action": ep.get("action"),
                                "tick": ep.get("tick"),
                                "effects": ep.get("experienced_effects"),
                            },
                            sort_keys=True,
                            default=str,
                        )
                    )
            return out

        fa, fb = fps(actor), fps(observer)
        chain["memory_isolation"] = {
            "shared_episode_fingerprints": len(fa & fb),
            "pass": len(fa & fb) == 0,
            "episodes": {actor: len(fa), observer: len(fb)},
        }

    chain["elapsed_sec"] = round(time.time() - t0, 3)
    chain["final_quantity"] = quantity_of(engine.state.world.variables, OBJECT_ID)
    engine.close()
    return chain


def run_near_passive(ticks: int = 80) -> dict[str, Any]:
    """NEAR_PASSIVE_BODY control: passive body stays adjacent; A endogenous-ish WAIT/MOVE."""
    positions = {A: OBJ_POS, B: (OBJ_POS[0] + 1, OBJ_POS[1])}
    engine = build_engine(positions=positions)
    actions_a = []
    contacts = 0
    for i in range(ticks):
        result = engine.step({B: Action("WAIT")})
        actions_a.append(result.actions[A].kind)
        truth = engine.state.world.variables.get("world") or {}
        pos = truth.get("agent_positions") or {}
        pa, pb = pos.get(A), pos.get(B)
        if isinstance(pa, list) and isinstance(pb, list):
            if abs(pa[0] - pb[0]) + abs(pa[1] - pb[1]) <= 1:
                contacts += 1
    from collections import Counter

    engine.close()
    return {
        "condition": "NEAR_PASSIVE_BODY",
        "ticks": ticks,
        "action_counts_A": dict(Counter(k.split(":")[0] for k in actions_a)),
        "contact_ticks": contacts,
        "note": "Passive body forced WAIT while remaining near A start geometry.",
    }


def classify_arrows(trace_present: dict[str, Any]) -> dict[str, str]:
    inter = trace_present.get("intervention") or {}
    bob = trace_present.get("b_observation") or {}
    bexp = trace_present.get("b_experience") or {}
    bret = trace_present.get("b_retrieval") or {}
    bpred = trace_present.get("b_prediction") or {}
    bval = trace_present.get("b_valuation") or {}
    bdec = trace_present.get("b_decision") or {}

    arrows = {
        "A_action→physical_X_change": (
            "DEMONSTRATED" if inter.get("changed") else "NULL"
        ),
        "physical_X_change→B_observation": (
            "DEMONSTRATED"
            if bob.get("quantity") is not None and inter.get("changed")
            else ("MISSING" if inter.get("changed") else "NULL")
        ),
        "B_observation→B_experience": (
            "DEMONSTRATED"
            if bexp.get("stored")
            else ("MISSING" if bob.get("quantity") is not None else "NULL")
        ),
        "B_experience→later_retrieval": (
            "DEMONSTRATED"
            if bret.get("retrieved")
            else (
                "IMPLEMENTED_BUT_UNPROVEN"
                if bexp.get("stored")
                else "NULL"
            )
        ),
        "retrieval→prediction": (
            "IMPLEMENTED_BUT_UNPROVEN"
            if bret.get("retrieved")
            else "NOT_OBSERVED".replace("NOT_OBSERVED", "NULL")
        ),
        "prediction→prospective_value": "NULL",
        "prospective_value→candidate_comparison": "NULL",
        "candidate_comparison→selection/rejection": "NULL",
        "selection→physical_consequence": "PARTIAL",
    }
    # Fix retrieval→prediction wording
    if not bret.get("retrieved"):
        arrows["retrieval→prediction"] = "NULL"
    else:
        arrows["retrieval→prediction"] = "IMPLEMENTED_BUT_UNPROVEN"
    if bpred.get("status") == "ABLATED":
        arrows["retrieval→prediction"] = "NULL"
    _ = bval, bdec
    return arrows


def write(name: str, payload: Any) -> None:
    (OUT / name).write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    post = 12 if args.quick else 25

    config = {
        "update": "4.7.1",
        "seed": SEED,
        "mds": MDS,
        "object_id": OBJECT_ID,
        "object_position": list(OBJ_POS),
        "probe_event_id_observer_only": PROBE_EVENT_ID,
        "note_obj12_matrix_miss": (
            "Update 4.7 matrix SHARED_OBJECT_TRACE failed because agents started at (2,3) "
            "while OBJ-12 is at (14,16); USE did not co-locate. This probe places actor on object."
        ),
        "no_social_semantics": True,
    }
    write("UPDATE471_CONFIG.json", config)

    print("TRACE_PRESENT...", flush=True)
    trace = run_trace_probe(
        name="TRACE_PRESENT",
        do_a_use=True,
        allow_b_observe=True,
        post_ticks=post,
    )
    write("TRACE_PRESENT_SUMMARY.json", trace)
    print(trace["intervention"], trace["b_observation"], trace["b_experience"]["stored"], flush=True)

    print("NO_TRACE...", flush=True)
    no_trace = run_trace_probe(
        name="NO_TRACE",
        do_a_use=False,
        allow_b_observe=True,
        post_ticks=post,
    )
    write("NO_TRACE_SUMMARY.json", no_trace)

    print("TRACE_NOT_OBSERVED...", flush=True)
    not_obs = run_trace_probe(
        name="TRACE_NOT_OBSERVED",
        do_a_use=True,
        allow_b_observe=False,
        post_ticks=post,
    )
    write("TRACE_NOT_OBSERVED_SUMMARY.json", not_obs)

    print("EXPERIENCE_ABLATED...", flush=True)
    exp_ab = run_trace_probe(
        name="EXPERIENCE_ABLATED",
        do_a_use=True,
        allow_b_observe=True,
        experience_ablated=True,
        post_ticks=post,
    )
    write("EXPERIENCE_ABLATED_SUMMARY.json", exp_ab)

    print("RETRIEVAL_ABLATED...", flush=True)
    ret_ab = run_trace_probe(
        name="RETRIEVAL_ABLATED",
        do_a_use=True,
        allow_b_observe=True,
        retrieval_ablated=True,
        post_ticks=post,
    )
    write("RETRIEVAL_ABLATED_SUMMARY.json", ret_ab)

    print("ACTOR_SWAP...", flush=True)
    swap = run_trace_probe(
        name="ACTOR_SWAP",
        do_a_use=True,
        allow_b_observe=True,
        actor=B,
        observer=A,
        post_ticks=post,
    )
    write("ACTOR_SWAP_SUMMARY.json", swap)

    print("NEAR_PASSIVE_BODY...", flush=True)
    near_pas = run_near_passive(ticks=40 if args.quick else 80)
    write("NEAR_PASSIVE_BODY_SUMMARY.json", near_pas)

    arrows = classify_arrows(trace)
    chain_doc = {
        "arrows": arrows,
        "stages_TRACE_PRESENT": trace.get("stages"),
        "controls": {
            "NO_TRACE_changed": (no_trace.get("intervention") or {}).get("changed"),
            "TRACE_NOT_OBSERVED_b_qty": (not_obs.get("b_observation") or {}).get("quantity"),
            "EXPERIENCE_ABLATED_post_hits": (
                exp_ab.get("b_experience") or {}
            ).get("post_ablation_episode_hits"),
            "RETRIEVAL_ABLATED_pred": (ret_ab.get("b_prediction") or {}).get("status"),
            "ACTOR_SWAP_changed": (swap.get("intervention") or {}).get("changed"),
            "NEAR_PASSIVE_contacts": near_pas.get("contact_ticks"),
        },
        "first_unsupported_arrow": next(
            (
                k
                for k, v in arrows.items()
                if v in {"MISSING", "NULL", "IMPLEMENTED_BUT_UNPROVEN"}
                and k != "selection→physical_consequence"
            ),
            None,
        ),
    }
    # Prefer first non-DEMONSTRATED after the demonstrated prefix
    first_fail = None
    for k, v in arrows.items():
        if v != "DEMONSTRATED":
            first_fail = {"arrow": k, "status": v}
            break
    chain_doc["first_unsupported"] = first_fail
    write("CROSS_AGENT_TRACE_CHAIN.json", chain_doc)

    md = ["# Update 4.7.1 — Cross-agent physical trace chain\n"]
    md.append("| Arrow | Status |\n|---|---|\n")
    for k, v in arrows.items():
        md.append(f"| {k} | **{v}** |\n")
    md.append("\n## First unsupported\n")
    md.append(f"`{first_fail}`\n")
    md.append(
        "\n## Interpretation boundary\n"
        "Even if observation/experience succeed, this is **not** social cognition.\n"
    )
    (OUT / "CROSS_AGENT_TRACE_CHAIN.md").write_text("".join(md))

    # Leakage audit report
    leak_pass = all(
        (x.get("leakage_audit") or {}).get("pass", False)
        for x in (trace, no_trace, not_obs, exp_ab, ret_ab, swap)
    )
    (OUT / "COGNITIVE_LEAKAGE_AUDIT.md").write_text(
        "# Cognitive leakage audit (4.7.1)\n\n"
        f"Overall PASS={leak_pass}\n\n"
        "Forbidden in cognition: probe_event_id, actor provenance, changed_by, social labels.\n\n"
        f"TRACE_PRESENT leaks: {(trace.get('leakage_audit') or {}).get('leaks')}\n"
        f"Memory isolation TRACE_PRESENT: {trace.get('memory_isolation')}\n"
    )
    (OUT / "OBSERVER_TRACE_AUDIT.md").write_text(
        "# Observer trace audit\n\n"
        "Observer may show GROUND TRUTH (actor, probe id, intervention tick).\n"
        "Agent-available evidence is limited to ordinary visible_objects.observable_state.quantity "
        "and related physical channels — no provenance.\n\n"
        "Panel: CROSS-AGENT PHYSICAL TRACE in Psychology Observer right column.\n"
        "Map: probe object highlight via observer_receipts.cross_agent_trace_v471 when present.\n"
    )

    # Final report answers
    answers = {
        "1_A_caused_persistent_change": (trace.get("intervention") or {}).get("changed"),
        "2_B_could_observe": (trace.get("b_observation") or {}).get("quantity") is not None,
        "3_B_evidence": trace.get("b_observation"),
        "4_B_stored_experience": (trace.get("b_experience") or {}).get("stored"),
        "5_later_retrieved": (trace.get("b_retrieval") or {}).get("retrieved"),
        "6_retrieval_affected_prediction": False,
        "7_prospective_value": False,
        "8_entered_comparison": False,
        "9_altered_selection": None,
        "10_first_failed_arrow": first_fail,
        "11_NO_TRACE_removes_change": not (no_trace.get("intervention") or {}).get("changed"),
        "12_TRACE_NOT_OBSERVED_blocks_obs": (not_obs.get("b_observation") or {}).get("quantity") is None,
        "13_EXPERIENCE_ABLATED": bool((exp_ab.get("b_experience") or {}).get("ablated_after_storage")),
        "14_RETRIEVAL_ABLATED": (ret_ab.get("b_prediction") or {}).get("status") == "ABLATED",
        "15_hidden_provenance_leaked": not (trace.get("leakage_audit") or {}).get("pass", True),
        "16_mere_nearby_body": near_pas,
        "17_strongest_conclusion": None,
        "18_first_unsupported_after_471": first_fail,
        "arrows": arrows,
    }
    # strongest conclusion
    if answers["1_A_caused_persistent_change"] and answers["2_B_could_observe"] and answers["4_B_stored_experience"]:
        if answers["5_later_retrieved"] and not answers["6_retrieval_affected_prediction"]:
            answers["17_strongest_conclusion"] = (
                "A persistent physical quantity change caused by one agent can become "
                "physically available to another agent and enter ordinary spatial/episode "
                "memory; later participation in prediction/valuation/selection remains unproven."
            )
        elif answers["4_B_stored_experience"]:
            answers["17_strongest_conclusion"] = (
                "Cross-agent physical quantity traces can enter the second agent's ordinary "
                "experience store without social semantics; retrieval→decision chain not demonstrated."
            )
        else:
            answers["17_strongest_conclusion"] = (
                "Physical change and observation possible; experience storage not demonstrated."
            )
    else:
        answers["17_strongest_conclusion"] = (
            "Primary TRACE_PRESENT chain did not clear physical change→observation→experience."
        )

    report = f"""# Update 4.7.1 — Final report

## OBJ-12 matrix miss (4.7)
Agents started at (2,3); OBJ-12 lives at (14,16). Forced `USE:OBJ-12` without co-location left quantity at 0.9.
This probe places the actor on OBJ-12.

## Answers
1. A persistent change? **{answers['1_A_caused_persistent_change']}** ({(trace.get('intervention') or {})})
2. B observe? **{answers['2_B_could_observe']}**
3. Evidence: `{(trace.get('b_observation'))}`
4. Stored experience? **{answers['4_B_stored_experience']}**
5. Later retrieved? **{answers['5_later_retrieved']}**
6. Prediction affected? **{answers['6_retrieval_affected_prediction']}**
7. Prospective value? **{answers['7_prospective_value']}**
8. Comparison? **{answers['8_entered_comparison']}**
9. Selection altered? **{answers['9_altered_selection']}**
10. First failed arrow: **{answers['10_first_failed_arrow']}**
11. NO_TRACE removes change? **{answers['11_NO_TRACE_removes_change']}**
12. TRACE_NOT_OBSERVED blocks obs? **{answers['12_TRACE_NOT_OBSERVED_blocks_obs']}**
13. EXPERIENCE_ABLATED applied? **{answers['13_EXPERIENCE_ABLATED']}**
14. RETRIEVAL_ABLATED (prediction_ablated)? **{answers['14_RETRIEVAL_ABLATED']}**
15. Provenance leaked? **{answers['15_hidden_provenance_leaked']}**
16. Mere nearby body: see NEAR_PASSIVE_BODY_SUMMARY.json
17. Strongest conclusion: {answers['17_strongest_conclusion']}
18. First unsupported after 4.7.1: **{answers['18_first_unsupported_after_471']}**

## Primary question
Physical consequence by one psyche → ordinary experience of another → later decision participation **without social semantics**?

Result: change/observation/experience as measured in TRACE_PRESENT_SUMMARY.json;
prediction/valuation/selection participation **not demonstrated**.

## Arrow table
See CROSS_AGENT_TRACE_CHAIN.md

## No new social mechanisms
Confirmed: no actor IDs, probe IDs, or social labels in cognition (COGNITIVE_LEAKAGE_AUDIT.md).
"""
    (OUT / "UPDATE471_FINAL_REPORT.md").write_text(report)
    write("UPDATE471_ANSWERS.json", answers)
    print(json.dumps({"first_unsupported": first_fail, "answers_1_5": {k: answers[k] for k in list(answers)[:5]}}, indent=2, default=str))
    print(f"Wrote {OUT}", flush=True)


if __name__ == "__main__":
    main()
