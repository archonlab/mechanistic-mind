"""Cross-mechanism joins: vision, signals, contact, resources, orientation."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .geometry import approach_decomposition, orienting_error, toroidal_distance
from .relationships import NodeRef, RelationshipGraph
from .tick_stories import TickStory


def _iter_jsonl(path: Path):
    if not path.is_file():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def load_timeline_index(run_dir: Path, *, max_tick: int | None = None) -> dict[tuple[str, int], dict[str, Any]]:
    idx: dict[tuple[str, int], dict[str, Any]] = {}
    for row in _iter_jsonl(run_dir / "scientific_timeline.jsonl") or []:
        if not isinstance(row, dict) or "tick" not in row:
            continue
        t = int(row["tick"])
        if max_tick is not None and t > int(max_tick):
            continue
        aid = str(row.get("agent_id") or "")
        idx[(aid, t)] = _compact_timeline_row(row)
    return idx


def _compact_timeline_row(row: dict[str, Any]) -> dict[str, Any]:
    vo = row.get("vision_optical") if isinstance(row.get("vision_optical"), dict) else {}
    return {
        "tick": row.get("tick"),
        "agent_id": row.get("agent_id"),
        "body_id": row.get("body_id"),
        "x": row.get("x"),
        "y": row.get("y"),
        "vx": row.get("vx"),
        "vy": row.get("vy"),
        "theta": row.get("theta"),
        "omega": row.get("omega"),
        "speed": row.get("speed"),
        "head_world_heading": row.get("head_world_heading"),
        "head_relative_angle": row.get("head_relative_angle"),
        "contact": row.get("contact"),
        "resource_A": row.get("resource_A"),
        "resource_B": row.get("resource_B"),
        "work": row.get("work"),
        "action": row.get("action"),
        "action_source": row.get("action_source"),
        "vision_optical": {
            "body_exposure": vo.get("body_exposure"),
            "foreign_body_total": vo.get("foreign_body_total"),
            "foreign_body_contribution": vo.get("foreign_body_contribution"),
            "final_exo": vo.get("final_exo"),
            "exo_without_foreign_bodies": vo.get("exo_without_foreign_bodies"),
            "neighbors_optical": vo.get("neighbors_optical"),
            "source_bodies_gt": vo.get("source_bodies_gt"),
            "identity_layer": vo.get("identity_layer"),
        } if vo else None,
    }


_JOIN_EVENT_TYPES = {
    "PHYSICAL_SIGNAL_RECEIVED",
    "PHYSICAL_SIGNAL_EMITTED",
    "CONTACT",
}


def load_events_by_tick(run_dir: Path, *, max_tick: int | None = None) -> dict[int, list[dict[str, Any]]]:
    by: dict[int, list[dict[str, Any]]] = {}
    for ev in _iter_jsonl(run_dir / "scientific_events.jsonl") or []:
        if not isinstance(ev, dict) or "tick" not in ev:
            continue
        et = ev.get("type") or ev.get("kind")
        if et not in _JOIN_EVENT_TYPES:
            continue
        t = int(ev["tick"])
        if max_tick is not None and t > int(max_tick):
            continue
        evid = ev.get("evidence") if isinstance(ev.get("evidence"), dict) else {}
        by.setdefault(t, []).append({
            "tick": t,
            "type": et,
            "kind": et,
            "agent_id": ev.get("agent_id"),
            "receiver_agent_id": ev.get("receiver_agent_id"),
            "emitter_agent_id": ev.get("emitter_agent_id"),
            "evidence": {
                "receiver_agent_id": evid.get("receiver_agent_id"),
                "emitter_agent_id": evid.get("emitter_agent_id"),
                "local.FIELD_A": evid.get("local.FIELD_A"),
                "source_attribution": evid.get("source_attribution"),
                "contributing_emissions_this_tick": evid.get("contributing_emissions_this_tick"),
                "channel": evid.get("channel"),
                "trigger": evid.get("trigger"),
                "emission_id": evid.get("emission_id"),
            },
        })
    return by


def infer_world_size(timeline_idx: dict[tuple[str, int], dict[str, Any]], default: float = 32.0) -> tuple[float, float]:
    xs = [float(r["x"]) for r in timeline_idx.values() if "x" in r]
    ys = [float(r["y"]) for r in timeline_idx.values() if "y" in r]
    if not xs or not ys:
        return default, default
    # Planet worlds in this project are typically integer grids; coords in [0, W)
    w = max(default, float(int(max(xs)) + 1))
    h = max(default, float(int(max(ys)) + 1))
    # Prefer classic 32 if data fits
    if max(xs) < 32.0 and max(ys) < 32.0:
        return 32.0, 32.0
    return w, h


def apply_joins(
    stories: list[TickStory],
    graph: RelationshipGraph,
    *,
    run_dir: Path,
    max_tick: int | None = None,
) -> dict[str, Any]:
    """Enrich TickStories with vision/signal/contact/geometry external_context."""
    timeline = load_timeline_index(run_dir, max_tick=max_tick)
    events = load_events_by_tick(run_dir, max_tick=max_tick)
    width, height = infer_world_size(timeline)
    run_id = graph.run_id

    # Index stories
    by_key = {(s.cognitive_agent_id, s.tick): s for s in stories}
    agents = sorted({s.cognitive_agent_id for s in stories})
    bodies = {s.cognitive_agent_id: s.physical_body_id for s in stories}

    vision_joins = 0
    signal_joins = 0
    contact_joins = 0
    geometry_joins = 0

    for s in stories:
        ctx: list[dict[str, Any]] = []
        derived: list[dict[str, Any]] = list(s.derived_changes)
        t = s.tick
        row = timeline.get((s.cognitive_agent_id, t)) or timeline.get((s.cognitive_agent_id, t + 1))
        # Vision: Observer optical provenance → accessible exo_*
        vo = (row or {}).get("vision_optical") if row else None
        if isinstance(vo, dict) and vo.get("body_exposure"):
            nid = f"vision:{run_id}:{t}:{s.cognitive_agent_id}"
            graph.add_node(NodeRef(
                family="VISION_EXPOSURE", node_id=nid, run_id=run_id, tick=t,
                agent_id=s.cognitive_agent_id, body_id=s.physical_body_id,
                source_file="scientific_timeline.jsonl", evidence_class="OBSERVED",
                agent_accessible=False,  # Observer GT exposure flag
                meta={"body_exposure": True},
            ))
            exo_keys = [c for c in s.observation_components if str(c.get("key", "")).startswith("exo_")]
            if s.observation_id and exo_keys:
                graph.add_edge(
                    rel_type="PHYSICALLY_CONTRIBUTED_TO",
                    src=nid,
                    dst=s.observation_id,
                    why="Observer body_exposure true and exo_* present in accessible observation",
                    strength="DIRECT_CAUSAL_LINK",
                    tick=t,
                )
                graph.add_edge(
                    rel_type="OBSERVED_AS",
                    src=nid,
                    dst=s.observation_id,
                    why="Optical contribution reflected in agent-accessible exo_* components",
                    strength="AVAILABLE_TO_AGENT",
                    tick=t,
                )
                if s.decision_id:
                    graph.add_edge(
                        rel_type="PART_OF_DECISION_CONTEXT",
                        src=nid,
                        dst=s.decision_id,
                        why="Vision-linked observation is part of same-tick decision context",
                        strength="PART_OF_DECISION_CONTEXT",
                        tick=t,
                    )
                    graph.add_edge(
                        rel_type="NOT_ESTABLISHED",
                        src=nid,
                        dst=s.decision_id,
                        why="Specific optical component causation of selected continuation not evidenced",
                        strength="NOT_ESTABLISHED",
                        evidence_layer="HYPOTHESIS_FORENSIC_LAYER",
                        tick=t,
                    )
                vision_joins += 1
                ctx.append({
                    "kind": "VISION_EXPOSURE",
                    "layer": "OBSERVED",
                    "body_exposure": True,
                    "exo_components": [c["key"] for c in exo_keys],
                    "foreign_body_total": vo.get("foreign_body_total"),
                    "foreign_body_contribution": vo.get("foreign_body_contribution"),
                    "final_exo": vo.get("final_exo"),
                    "exo_without_foreign_bodies": vo.get("exo_without_foreign_bodies"),
                    "neighbors_optical": vo.get("neighbors_optical"),
                    "source_bodies_gt": vo.get("source_bodies_gt"),
                    "identity_layer": vo.get("identity_layer"),
                    "optical_provenance": "OBSERVER_GT",
                    "chain": [
                        "PHYSICAL_SOURCE/body",
                        "DIRECT_CAUSAL_LINK",
                        "optical contribution",
                        "DIRECT_CAUSAL_LINK",
                        "accessible exo_*",
                        "RECORDED_CONTEXT",
                        "DecisionReceipt",
                        "PRODUCED_MOTOR",
                        "MotorReceipt",
                        "PHYSICALLY_RESULTED_IN",
                        "ConsequenceReceipt",
                    ],
                    "specific_causation": "NOT_ESTABLISHED",
                    "note_A": "Sensory component available to agent: RECORDED when exo_* in ObservationReceipt",
                    "note_B": "Specific component caused decision: NOT_ESTABLISHED",
                })

        # Signals
        for ev in events.get(t, []):
            et = ev.get("type") or ev.get("kind")
            if et == "PHYSICAL_SIGNAL_RECEIVED":
                evid = ev.get("evidence") or {}
                recv = evid.get("receiver_agent_id") or ev.get("receiver_agent_id") or ev.get("agent_id")
                if recv and recv != s.cognitive_agent_id:
                    continue
                rid = f"sig_rx:{run_id}:{t}:{s.cognitive_agent_id}:{evid.get('local.FIELD_A')}"
                graph.add_node(NodeRef(
                    family="SIGNAL_RECEPTION", node_id=rid, run_id=run_id, tick=t,
                    agent_id=s.cognitive_agent_id, body_id=s.physical_body_id,
                    source_file="scientific_events.jsonl", evidence_class="OBSERVED",
                    agent_accessible=False,
                    meta={"source_attribution": evid.get("source_attribution")},
                ))
                field_comps = [c for c in s.observation_components if str(c.get("key", "")).startswith("local.FIELD_")]
                if s.observation_id and field_comps:
                    graph.add_edge(
                        rel_type="RECEIVED_FROM",
                        src=rid,
                        dst=s.observation_id,
                        why="PHYSICAL_SIGNAL_RECEIVED local.FIELD_* joins accessible ObservationReceipt FIELD keys",
                        strength="DIRECT_CAUSAL_LINK",
                        tick=t,
                    )
                    if s.decision_id:
                        graph.add_edge(
                            rel_type="PART_OF_DECISION_CONTEXT",
                            src=rid,
                            dst=s.decision_id,
                            why="Field-linked observation is decision context this tick",
                            strength="PART_OF_DECISION_CONTEXT",
                            tick=t,
                        )
                        graph.add_edge(
                            rel_type="NOT_ESTABLISHED",
                            src=rid,
                            dst=s.decision_id,
                            why="FIELD_* presence does not prove it uniquely caused the selected continuation",
                            strength="NOT_ESTABLISHED",
                            evidence_layer="HYPOTHESIS_FORENSIC_LAYER",
                            tick=t,
                        )
                    signal_joins += 1
                    ctx.append({
                        "kind": "SIGNAL_RECEPTION",
                        "layer": "OBSERVED",
                        "source_attribution": evid.get("source_attribution"),
                        "field_components": [c["key"] for c in field_comps],
                        "contributing_emissions": evid.get("contributing_emissions_this_tick"),
                        "warnings": [
                            "Physical signal ≠ message",
                            "Reception ≠ interpretation",
                            "Emission ≠ intentional communication",
                        ],
                        "specific_causation": "NOT_ESTABLISHED",
                    })
            elif et == "PHYSICAL_SIGNAL_EMITTED":
                evid = ev.get("evidence") or {}
                emitter = evid.get("emitter_agent_id") or ev.get("emitter_agent_id") or ev.get("agent_id")
                if emitter != s.cognitive_agent_id:
                    continue
                eid = f"sig_tx:{run_id}:{t}:{s.cognitive_agent_id}:{evid.get('emission_id')}"
                graph.add_node(NodeRef(
                    family="SIGNAL_EMISSION", node_id=eid, run_id=run_id, tick=t,
                    agent_id=s.cognitive_agent_id, body_id=s.physical_body_id,
                    source_file="scientific_events.jsonl", evidence_class="OBSERVED",
                    meta={"trigger": evid.get("trigger"), "channel": evid.get("channel")},
                ))
                ctx.append({
                    "kind": "SIGNAL_EMISSION",
                    "layer": "OBSERVED",
                    "channel": evid.get("channel"),
                    "trigger": evid.get("trigger"),
                    "emission_id": evid.get("emission_id"),
                })
            elif et == "CONTACT":
                # Prefer per-body timeline contact flag; avoid attributing observer-global CONTACT to every agent.
                row_c = timeline.get((s.cognitive_agent_id, t))
                if row_c is not None and not bool(row_c.get("contact")):
                    continue
                nid = f"contact:{run_id}:{t}:{s.cognitive_agent_id}"
                graph.add_node(NodeRef(
                    family="CONTACT", node_id=nid, run_id=run_id, tick=t,
                    agent_id=s.cognitive_agent_id, body_id=s.physical_body_id,
                    source_file="scientific_events.jsonl", evidence_class="OBSERVED",
                ))
                contact_joins += 1
                ctx.append({"kind": "CONTACT", "layer": "OBSERVED", "tick": t, "event": et})

        # Multi-agent geometry vs other bodies
        for other in agents:
            if other == s.cognitive_agent_id:
                continue
            me = timeline.get((s.cognitive_agent_id, t))
            ot = timeline.get((other, t))
            me1 = timeline.get((s.cognitive_agent_id, t + 1))
            ot1 = timeline.get((other, t + 1))
            if not (me and ot and "x" in me and "x" in ot):
                continue
            a0 = (float(me["x"]), float(me["y"]))
            s0 = (float(ot["x"]), float(ot["y"]))
            dist = toroidal_distance(*a0, *s0, width, height)
            heading = float(me.get("head_world_heading") if me.get("head_world_heading") is not None else me.get("theta") or 0.0)
            ori = orienting_error(agent_xy=a0, source_xy=s0, head_or_body_heading=heading, width=width, height=height)
            geom: dict[str, Any] = {
                "kind": "RELATIVE_GEOMETRY",
                "layer": "DERIVED",
                "other_agent": other,
                "other_body": bodies.get(other),
                "toroidal_distance": dist,
                "orienting": ori,
                "world_size": [width, height],
            }
            if me1 and ot1 and "x" in me1 and "x" in ot1:
                decomp = approach_decomposition(
                    agent_xy_t=a0,
                    agent_xy_t1=(float(me1["x"]), float(me1["y"])),
                    source_xy_t=s0,
                    source_xy_t1=(float(ot1["x"]), float(ot1["y"])),
                    width=width,
                    height=height,
                )
                geom["approach"] = decomp
                geometry_joins += 1
            derived.append(geom)
            ctx.append({"kind": "PEER_GEOMETRY", "other": other, "distance": dist})

        # Resource state from timeline (accessible via body resources when present)
        if row:
            derived.append({
                "kind": "RESOURCE_STATE",
                "layer": "OBSERVED",
                "resource_A": row.get("resource_A"),
                "resource_B": row.get("resource_B"),
                "work": row.get("work"),
            })
            derived.append({
                "kind": "POSE_STATE",
                "layer": "OBSERVED",
                "x": row.get("x"),
                "y": row.get("y"),
                "vx": row.get("vx"),
                "vy": row.get("vy"),
                "theta": row.get("theta"),
                "head_world_heading": row.get("head_world_heading"),
                "head_relative_angle": row.get("head_relative_angle"),
                "speed": row.get("speed"),
                "action": row.get("action"),
                "action_source": row.get("action_source"),
                "contact": row.get("contact"),
            })

        s.external_context = ctx
        s.derived_changes = derived

    return {
        "world_size": [width, height],
        "vision_joins": vision_joins,
        "signal_joins": signal_joins,
        "contact_joins": contact_joins,
        "geometry_joins": geometry_joins,
        "timeline_rows_indexed": len(timeline),
        "event_ticks_indexed": len(events),
    }
