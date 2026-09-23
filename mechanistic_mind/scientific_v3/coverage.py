"""Multidimensional coverage matrix — MISSING ≠ ZERO."""
from __future__ import annotations

from typing import Any

COMPLETE = "COMPLETE"
PARTIAL = "PARTIAL"
AGGREGATE_ONLY = "AGGREGATE_ONLY"
EVENT_ONLY = "EVENT_ONLY"
CHECKPOINT_ONLY = "CHECKPOINT_ONLY"
SPARSE = "SPARSE"
NOT_RECORDED = "NOT_RECORDED"
NOT_AVAILABLE = "NOT_AVAILABLE"
NOT_APPLICABLE = "NOT_APPLICABLE"

CORE_DIMENSIONS = (
    "identity",
    "tick_history",
    "observation",
    "decision",
    "composite_motor",
    "consequence",
    "trajectory",
    "resources",
    "vision",
    "signals",
    "cognition",
    "interaction",
    "experimenter",
)


def empty_coverage(*, tier: str = "CORE") -> dict[str, Any]:
    dims = {d: NOT_RECORDED for d in CORE_DIMENSIONS}
    return {
        "schema": "mm.scientific_v3.coverage.v1",
        "evidence_tier": tier,
        "dimensions": dims,
        "note": "MISSING≠ZERO: NOT_RECORDED/NOT_AVAILABLE must not display as numeric zero for absence.",
    }


def mark(coverage: dict[str, Any], dimension: str, state: str) -> None:
    dims = coverage.setdefault("dimensions", {})
    dims[str(dimension)] = str(state)
