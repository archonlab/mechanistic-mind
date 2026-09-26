"""Typed relationship graph — reuse canonical SCIENTIFIC_RELATIONSHIP_GRAPH edge names."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Iterator


# Canonical edge types (prefer existing design names; extend only when required).
RELATIONSHIP_TYPES = (
    "AVAILABLE_TO_AGENT",
    "PART_OF_OBSERVATION",
    "PART_OF_DECISION_CONTEXT",
    "SELECTED",
    "PRODUCED_MOTOR",
    "PHYSICALLY_RESULTED_IN",
    "RECEIVED_FROM",
    "PHYSICALLY_CONTRIBUTED_TO",
    "OBSERVED_AS",
    "TEMPORALLY_FOLLOWED",
    "DERIVED_ASSOCIATION",
    "NOT_ESTABLISHED",
    "NOT_RECORDED",
)

NODE_FAMILIES = (
    "WORLD_EVENT",
    "PHYSICAL_SOURCE",
    "OBSERVATION",
    "OBSERVATION_COMPONENT",
    "DECISION",
    "MOTOR",
    "CONSEQUENCE",
    "BODY_STATE",
    "RESOURCE_STATE",
    "VISION_EXPOSURE",
    "SURFACE_EXPOSURE",
    "SIGNAL_EMISSION",
    "SIGNAL_RECEPTION",
    "CONTACT",
    "ECOLOGY_EVENT",
)

# Strength / why-it-exists classes for report honesty
EVIDENCE_STRENGTH = (
    "DIRECT_CAUSAL_LINK",
    "AVAILABLE_TO_AGENT",
    "PART_OF_DECISION_CONTEXT",
    "PRODUCED_MOTOR",
    "PHYSICALLY_RESULTED_IN",
    "TEMPORALLY_FOLLOWED",
    "DERIVED_ASSOCIATION",
    "NOT_ESTABLISHED",
    "NOT_RECORDED",
)


@dataclass(frozen=True)
class NodeRef:
    family: str
    node_id: str
    run_id: str
    tick: int | None = None
    agent_id: str | None = None
    body_id: str | None = None
    source_file: str | None = None
    receipt_id: str | None = None
    evidence_class: str = "OBSERVED"  # OBSERVED | DERIVED | HYPOTHESIS
    agent_accessible: bool | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None and v != {}}


@dataclass(frozen=True)
class Relationship:
    rel_type: str
    src: str  # node_id
    dst: str
    why: str
    strength: str
    evidence_layer: str = "EVIDENCE_GRAPH"  # EVIDENCE | DERIVED | HYPOTHESIS
    tick: int | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None and v != {}}


class RelationshipGraph:
    """Typed graph with bounded resident samples; counts are lossless."""

    def __init__(self, run_id: str, *, sample_nodes: int = 200, sample_edges: int = 8000) -> None:
        self.run_id = run_id
        self.nodes: dict[str, NodeRef] = {}
        self.edges: list[Relationship] = []
        self._sample_nodes = int(sample_nodes)
        self._sample_edges = int(sample_edges)
        self._node_count = 0
        self._edge_count = 0
        self._family_counts: dict[str, int] = {}
        self._type_counts: dict[str, int] = {}

    def note_family(self, family: str, n: int = 1) -> None:
        self._node_count += int(n)
        self._family_counts[family] = self._family_counts.get(family, 0) + int(n)

    def note_edges(self, rel_type: str, n: int = 1) -> None:
        self._edge_count += int(n)
        self._type_counts[rel_type] = self._type_counts.get(rel_type, 0) + int(n)

    def add_node(self, node: NodeRef) -> str:
        if node.node_id not in self.nodes:
            self.note_family(node.family, 1)
            if len(self.nodes) < self._sample_nodes:
                self.nodes[node.node_id] = node
        elif len(self.nodes) < self._sample_nodes:
            self.nodes[node.node_id] = node
        return node.node_id

    def add_edge(
        self,
        *,
        rel_type: str,
        src: str,
        dst: str,
        why: str,
        strength: str,
        evidence_layer: str = "EVIDENCE_GRAPH",
        tick: int | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        self._edge_count += 1
        self._type_counts[rel_type] = self._type_counts.get(rel_type, 0) + 1
        if len(self.edges) < self._sample_edges:
            self.edges.append(
                Relationship(
                    rel_type=rel_type,
                    src=src,
                    dst=dst,
                    why=why,
                    strength=strength,
                    evidence_layer=evidence_layer,
                    tick=tick,
                    meta=meta or {},
                )
            )

    def iter_edges(self, rel_type: str | None = None) -> Iterator[Relationship]:
        for e in self.edges:
            if rel_type is None or e.rel_type == rel_type:
                yield e

    def summary(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "node_count": self._node_count,
            "edge_count": self._edge_count,
            "nodes_by_family": dict(self._family_counts),
            "edges_by_type": dict(self._type_counts),
            "resident_node_sample": len(self.nodes),
            "resident_edge_sample": len(self.edges),
        }

    def to_export(self, *, max_edges: int = 5000) -> dict[str, Any]:
        """Bounded export — summary + capped edge sample, not full duplication."""
        edges_sorted = sorted(self.edges, key=lambda e: (e.tick if e.tick is not None else -1, e.rel_type, e.src, e.dst))
        return {
            "schema": "mm.analyzer_next.relationship_graph.v1",
            "summary": self.summary(),
            "nodes_sample": [n.to_dict() for n in list(self.nodes.values())[:200]],
            "edges": [e.to_dict() for e in edges_sorted[:max_edges]],
            "edges_truncated": max(0, len(edges_sorted) - max_edges),
        }


# Action-conditioned model edges (prediction availability — not preference / reward)
CONDITIONED_ON_MOTOR = "CONDITIONED_ON_MOTOR"
PREDICTED_CONSEQUENCE = "PREDICTED_CONSEQUENCE"
SENSORY_DELTA_OBSERVED = "SENSORY_DELTA_OBSERVED"
