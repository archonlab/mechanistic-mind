"""Compatibility wrapper: v0.2 replaces phases with behavioral epochs."""

from .epochs import BehavioralEpochDetector, PhaseDetector

__all__ = ["BehavioralEpochDetector", "PhaseDetector"]
