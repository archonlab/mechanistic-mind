"""Layered Analyzer coverage — core chains vs auxiliary authority layers."""
from __future__ import annotations

from typing import Any


def classify_layer(complete: bool, partial: bool, present: bool) -> str:
    if complete:
        return "COMPLETE"
    if partial:
        return "PARTIAL"
    if present:
        return "PARTIAL"
    return "UNAVAILABLE"


def build_layered_coverage(
    *,
    complete_odmc: int,
    expected_odmc: int,
    unique_simulation_ticks: int,
    metadata: dict[str, Any] | None,
    psc_regime: dict[str, Any] | None,
    vision_channels_seen: bool,
    signal_receipts: int,
    observer_timeline_samples: int,
    world_size_present: bool,
) -> dict[str, Any]:
    core_full = expected_odmc > 0 and complete_odmc == expected_odmc
    meta_ok = bool((metadata or {}).get("identity", {}).get("seed") not in (None, "NOT AVAILABLE"))
    psc_ok = bool((psc_regime or {}).get("regimes"))
    layers = {
        "CORE_CAUSAL_CHAIN_COVERAGE": {
            "status": "FULL" if core_full else ("PARTIAL" if complete_odmc else "UNAVAILABLE"),
            "complete_chains": complete_odmc,
            "expected_chains": expected_odmc,
            "unit": "agent-ticks / O→D→M→C receipts",
        },
        "RUN_METADATA_COVERAGE": classify_layer(meta_ok, False, meta_ok),
        "WORLD_PHYSICAL_COVERAGE": classify_layer(world_size_present, False, world_size_present),
        "VISION_PROVENANCE_COVERAGE": "PARTIAL" if vision_channels_seen else "UNAVAILABLE",
        "SIGNAL_PROVENANCE_COVERAGE": "PARTIAL" if signal_receipts > 0 else "UNAVAILABLE",
        "RUNTIME_TRANSITION_COVERAGE": "COMPLETE" if psc_ok else "PARTIAL",
        "OBSERVER_TIMELINE_COVERAGE": "PARTIAL" if observer_timeline_samples > 0 else "UNAVAILABLE",
    }
    aux_statuses = [
        layers["RUN_METADATA_COVERAGE"],
        layers["WORLD_PHYSICAL_COVERAGE"],
        layers["VISION_PROVENANCE_COVERAGE"],
        layers["SIGNAL_PROVENANCE_COVERAGE"],
        layers["RUNTIME_TRANSITION_COVERAGE"],
        layers["OBSERVER_TIMELINE_COVERAGE"],
    ]
    if all(s == "COMPLETE" for s in aux_statuses):
        aux = "COMPLETE"
    elif any(s != "UNAVAILABLE" for s in aux_statuses):
        aux = "PARTIAL"
    else:
        aux = "UNAVAILABLE"
    banner = (
        "ANALYSIS COMPLETE — CORE CHAINS FULL, AUXILIARY COVERAGE PARTIAL"
        if core_full and aux == "PARTIAL"
        else (
            "ANALYSIS COMPLETE — CORE CHAINS FULL"
            if core_full and aux == "COMPLETE"
            else "ANALYSIS COMPLETE — PARTIAL EVIDENCE"
        )
    )
    return {
        "schema": "mm.analyzer.layered_coverage.v1",
        "banner": banner,
        "auxiliary": aux,
        "unique_simulation_ticks": unique_simulation_ticks,
        "layers": layers,
    }
