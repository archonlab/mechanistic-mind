"""Canonical per-agent / per-tick TickStory reconstruction from V3 spine."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Iterator

from mechanistic_mind.scientific_v3.api import RunEvidence

from .relationships import NodeRef, RelationshipGraph


FORBIDDEN_FACT_WORDS = (
    "recognized", "understood", "communicated", "wanted", "preferred",
    "feared", "searched for", "sought", "intended", "believed", "knew",
)


@dataclass
class TickStory:
    run_id: str
    tick: int
    cognitive_agent_id: str
    physical_body_id: str
    observation_id: str | None
    decision_id: str | None
    motor_id: str | None
    consequence_id: str | None
    observation: dict[str, Any] | None = None
    decision: dict[str, Any] | None = None
    motor: dict[str, Any] | None = None
    consequence: dict[str, Any] | None = None
    observation_components: list[dict[str, Any]] = field(default_factory=list)
    relationships: list[dict[str, Any]] = field(default_factory=list)
    external_context: list[dict[str, Any]] = field(default_factory=list)
    derived_changes: list[dict[str, Any]] = field(default_factory=list)
    evidence_quality: dict[str, Any] = field(default_factory=dict)
    composite_motor_summary: str | None = None

    def to_dict(self, *, include_receipts: bool = False) -> dict[str, Any]:
        d = {
            "run_id": self.run_id,
            "tick": self.tick,
            "cognitive_agent_id": self.cognitive_agent_id,
            "physical_body_id": self.physical_body_id,
            "observation_id": self.observation_id,
            "decision_id": self.decision_id,
            "motor_id": self.motor_id,
            "consequence_id": self.consequence_id,
            "observation_components": self.observation_components,
            "relationships": self.relationships,
            "external_context": self.external_context,
            "derived_changes": self.derived_changes,
            "evidence_quality": self.evidence_quality,
            "composite_motor_summary": self.composite_motor_summary,
        }
        if include_receipts:
            d["observation"] = self.observation
            d["decision"] = self.decision
            d["motor"] = self.motor
            d["consequence"] = self.consequence
        else:
            # compact decision/motor facts without dumping full maps
            if self.decision:
                d["decision_summary"] = {
                    "selection_path": self.decision.get("selection_path"),
                    "selection_source": self.decision.get("selection_source"),
                    "selection_mode": self.decision.get("selection_mode"),
                    "selected_action_legacy": self.decision.get("selected_action_legacy"),
                    "selected_candidate_id": self.decision.get("selected_candidate_id"),
                    "candidate_count": self.decision.get("candidate_count"),
                    "fallback_reason": self.decision.get("fallback_reason"),
                }
            if self.motor:
                d["motor_summary"] = {
                    "motor_schema": self.motor.get("motor_schema"),
                    "components": self.motor.get("components"),
                    "legacy_token": self.motor.get("legacy_token"),
                    "legacy_token_provenance": self.motor.get("legacy_token_provenance"),
                }
            if self.consequence:
                d["consequence_summary"] = {
                    "tick_from": self.consequence.get("tick_from"),
                    "tick_to": self.consequence.get("tick_to"),
                    "pose_delta": self.consequence.get("pose_delta"),
                    "orientation_delta": self.consequence.get("orientation_delta"),
                    "resource_delta": self.consequence.get("resource_delta"),
                    "attribution": self.consequence.get("attribution"),
                }
        return d


def _parse_observation_components(obs: dict[str, Any]) -> list[dict[str, Any]]:
    acc = obs.get("accessible") or {}
    out: list[dict[str, Any]] = []
    interesting_prefixes = (
        "local.FIELD_", "exo_", "surface_c", "spatial_", "body.", "internal.", "vest_", "prop_neck_", "osc_"
    )
    for k, v in sorted(acc.items()):
        if not any(k.startswith(p) for p in interesting_prefixes):
            continue
        try:
            fv = float(v)
        except (TypeError, ValueError):
            fv = None
        out.append({
            "key": k,
            "value": fv if fv is not None else v,
            "layer": "OBSERVED",
            "agent_accessible": True,
        })
    return out


def format_composite_motor(components: dict[str, Any] | None) -> str:
    if not components:
        return "WAIT/NONE"
    parts: list[str] = []
    loco = components.get("locomotion")
    if loco and str(loco).upper() not in ("WAIT", "NONE", ""):
        parts.append(str(loco) if str(loco).startswith("MOVE") else f"MOVE:{loco}" if loco not in ("WAIT",) else "WAIT")
        if str(loco).upper() == "WAIT":
            parts = ["WAIT"]
        else:
            # normalize
            s = str(loco)
            parts = [s if s.startswith("MOVE") or s == "WAIT" else s]
    else:
        parts.append("WAIT/NONE")
    neck = components.get("neck")
    if neck and str(neck).upper() not in ("NECK_HOLD", "HOLD", "NONE", ""):
        parts.append(str(neck))
    osc = components.get("oscillator") or {}
    if isinstance(osc, dict) and any(osc.values()):
        parts.append("OSC_EMIT")
    elif osc and not isinstance(osc, dict):
        parts.append(f"OSC:{osc}")
    if components.get("push"):
        parts.append("PUSH")
    # de-dupe WAIT/NONE if other activity
    if len(parts) > 1 and parts[0] in ("WAIT/NONE", "WAIT"):
        parts = parts[1:]
    return " + ".join(parts) if parts else "WAIT/NONE"


def _compact_decision(dec: dict[str, Any] | None) -> dict[str, Any] | None:
    if not dec:
        return None
    keys = (
        "selection_path", "selection_source", "selection_mode", "selection_rule",
        "selected_action_legacy", "selected_candidate_id", "candidate_count",
        "fallback_reason", "observation_id", "decision_id", "motor_id",
        "physical_body_id",
    )
    return {k: dec.get(k) for k in keys}


def _compact_motor(mot: dict[str, Any] | None) -> dict[str, Any] | None:
    if not mot:
        return None
    return {
        "motor_schema": mot.get("motor_schema"),
        "components": mot.get("components"),
        "legacy_token": mot.get("legacy_token"),
        "legacy_token_provenance": mot.get("legacy_token_provenance"),
        "decision_id": mot.get("decision_id"),
        "motor_id": mot.get("motor_id"),
    }


def _compact_consequence(cons: dict[str, Any] | None) -> dict[str, Any] | None:
    if not cons:
        return None
    return {
        "tick_from": cons.get("tick_from"),
        "tick_to": cons.get("tick_to"),
        "pose_delta": cons.get("pose_delta"),
        "orientation_delta": cons.get("orientation_delta"),
        "resource_delta": cons.get("resource_delta"),
        "attribution": cons.get("attribution"),
        "motor_id": cons.get("motor_id"),
        "consequence_id": cons.get("consequence_id"),
    }


def build_tick_stories(
    ev: RunEvidence,
    graph: RelationshipGraph,
    *,
    max_tick: int | None = None,
    on_progress: Any | None = None,
) -> list[TickStory]:
    stories: list[TickStory] = []
    run_id = (ev.meta or {}).get("run_id") or graph.run_id
    n = 0
    for spine in ev.iter_spine():
        tick = int(spine["tick"])
        if max_tick is not None and tick > int(max_tick):
            continue
        agent = spine.get("cognitive_agent_id")
        body = spine.get("physical_body_id")
        if not agent or not body:
            continue
        obs = ev.get_observation(agent, tick)
        dec = ev.get_decision(agent, tick)
        mot = ev.get_motor(agent, tick)
        cons = ev.get_consequence(body, tick)

        oid = (obs or {}).get("observation_id") or spine.get("observation_id")
        did = (dec or {}).get("decision_id") or spine.get("decision_id")
        mid = (mot or {}).get("motor_id") or spine.get("motor_id")
        cid = (cons or {}).get("consequence_id") or spine.get("consequence_id")

        # nodes (refs only)
        if oid:
            graph.add_node(NodeRef(
                family="OBSERVATION", node_id=oid, run_id=run_id, tick=tick,
                agent_id=agent, body_id=body, source_file="scientific_observations.jsonl",
                receipt_id=oid, evidence_class="OBSERVED", agent_accessible=True,
            ))
        if did:
            graph.add_node(NodeRef(
                family="DECISION", node_id=did, run_id=run_id, tick=tick,
                agent_id=agent, body_id=body, source_file="scientific_decisions.jsonl",
                receipt_id=did, evidence_class="OBSERVED", agent_accessible=False,
            ))
        if mid:
            graph.add_node(NodeRef(
                family="MOTOR", node_id=mid, run_id=run_id, tick=tick,
                agent_id=agent, body_id=body, source_file="scientific_motors.jsonl",
                receipt_id=mid, evidence_class="OBSERVED", agent_accessible=False,
            ))
        if cid:
            graph.add_node(NodeRef(
                family="CONSEQUENCE", node_id=cid, run_id=run_id, tick=tick,
                agent_id=agent, body_id=body, source_file="scientific_consequences.jsonl",
                receipt_id=cid, evidence_class="OBSERVED", agent_accessible=False,
            ))

        def _edge(rel_type: str, src: str, dst: str, why: str, strength: str, layer: str = "EVIDENCE_GRAPH") -> None:
            graph.add_edge(rel_type=rel_type, src=src, dst=dst, why=why, strength=strength, evidence_layer=layer, tick=tick)

        # V3 causal spine — ID-validated
        if oid and did:
            if dec and dec.get("observation_id") == oid:
                _edge("AVAILABLE_TO_AGENT", oid, did,
                      "DecisionReceipt.observation_id matches ObservationReceipt",
                      "AVAILABLE_TO_AGENT")
                _edge("PART_OF_DECISION_CONTEXT", oid, did,
                      "Same-tick observation linked as decision context (not specific-component causation)",
                      "PART_OF_DECISION_CONTEXT")
            else:
                _edge("NOT_ESTABLISHED", oid or "obs?", did or "dec?",
                      "observation_id mismatch or missing",
                      "NOT_ESTABLISHED")
        if did and mid:
            if (dec and dec.get("motor_id") == mid) or (mot and mot.get("decision_id") == did):
                _edge("PRODUCED_MOTOR", did, mid,
                      "DecisionReceipt.motor_id / MotorReceipt.decision_id",
                      "PRODUCED_MOTOR")
                _edge("SELECTED", did, mid,
                      "Selected motor output for this tick",
                      "SELECTED")
            else:
                _edge("NOT_ESTABLISHED", did, mid, "motor/decision id mismatch", "NOT_ESTABLISHED")
        if mid and cid:
            if cons and cons.get("motor_id") == mid:
                _edge("PHYSICALLY_RESULTED_IN", mid, cid,
                      "ConsequenceReceipt.motor_id matches MotorReceipt; tick_from=T",
                      "PHYSICALLY_RESULTED_IN")
            else:
                _edge("NOT_ESTABLISHED", mid, cid, "consequence/motor id mismatch", "NOT_ESTABLISHED")

        # Explicit: specific sensory component → decision causation remains NOT_ESTABLISHED
        if oid and did:
            _edge("NOT_ESTABLISHED", f"{oid}#component", did,
                  "No receipt proves a specific observation component uniquely caused this decision",
                  "NOT_ESTABLISHED", layer="HYPOTHESIS_FORENSIC_LAYER")

        components = _parse_observation_components(obs) if obs else []
        if components:
            graph.note_family("OBSERVATION_COMPONENT", len(components))
            if oid:
                graph.note_edges("PART_OF_OBSERVATION", len(components))

        broken = []
        if obs is None:
            broken.append("missing_observation")
        if dec is None:
            broken.append("missing_decision")
        if mot is None:
            broken.append("missing_motor")
        if cons is None:
            broken.append("missing_consequence")
        if dec and obs and dec.get("observation_id") != obs.get("observation_id"):
            broken.append("decision_observation_mismatch")
        if mot and dec and mot.get("decision_id") != dec.get("decision_id"):
            broken.append("motor_decision_mismatch")
        if cons and mot and cons.get("motor_id") != mot.get("motor_id"):
            broken.append("consequence_motor_mismatch")
        if cons and int(cons.get("tick_from", -1)) != tick:
            broken.append("consequence_tick_misaligned")

        motor_summary = format_composite_motor((mot or {}).get("components"))
        story = TickStory(
            run_id=run_id,
            tick=tick,
            cognitive_agent_id=agent,
            physical_body_id=body,
            observation_id=oid,
            decision_id=did,
            motor_id=mid,
            consequence_id=cid,
            observation=None,
            decision=_compact_decision(dec),
            motor=_compact_motor(mot),
            consequence=_compact_consequence(cons),
            observation_components=components,
            relationships=[],
            evidence_quality={
                "odmc_complete": len(broken) == 0,
                "broken_reasons": broken,
                "motor_schema": (mot or {}).get("motor_schema"),
                "consequence_attribution": (cons or {}).get("attribution"),
            },
            composite_motor_summary=motor_summary,
        )
        stories.append(story)
        n += 1
        if on_progress is not None and n % 500 == 0:
            on_progress("RECONSTRUCTING", n, tick)
    stories.sort(key=lambda s: (s.tick, s.cognitive_agent_id))
    return stories
