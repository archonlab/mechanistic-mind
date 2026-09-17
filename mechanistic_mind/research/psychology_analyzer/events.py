"""Compatibility wrapper; v0.2 events are intentionally non-recursive."""

from .meaningful_events import EventDetector, MeaningfulEventDetector

__all__ = ["EventDetector", "MeaningfulEventDetector"]
