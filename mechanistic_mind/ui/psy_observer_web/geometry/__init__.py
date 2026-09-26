"""Observer-only geometry / traversability interpretation (BETA2-GEO-01).

This package never mutates cognition, physics, or agent-accessible state.
All derived labels are human-facing physical descriptions, not agent semantics.
"""
from __future__ import annotations

from mechanistic_mind.ui.psy_observer_web.geometry.metrics import (
    action_alignment,
    action_direction_unit,
    realized_displacement,
    traversal_outcome_class,
)
from mechanistic_mind.ui.psy_observer_web.geometry.context import geometry_context
from mechanistic_mind.ui.psy_observer_web.geometry.live_summary import (
    geometry_live_compact_summary,
)

__all__ = [
    "action_alignment",
    "action_direction_unit",
    "realized_displacement",
    "traversal_outcome_class",
    "geometry_context",
    "geometry_live_compact_summary",
]
