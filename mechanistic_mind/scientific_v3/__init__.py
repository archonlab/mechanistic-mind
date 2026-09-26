"""SCIENTIFIC_V3 Phase-1 CORE — observation infrastructure only.

Does not change physics, cognition, PSC, sensors, selection, RNG, or tick order.
"""
from __future__ import annotations

SCHEMA_VERSION = "mm.scientific_v3.core.v1"
EVIDENCE_MODE = "SCIENTIFIC_V3"
EVIDENCE_TIER = "CORE"

__all__ = [
    "SCHEMA_VERSION",
    "EVIDENCE_MODE",
    "EVIDENCE_TIER",
]
