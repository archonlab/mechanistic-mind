"""PHYSICAL SURFACE OPTICAL COATING. Reads coating observation receipts only."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

EVENT = "SURFACE_OPTICAL_COATING_OBSERVED"


def _rows(events: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    found = []
    for event in events or []:
        if not isinstance(event, dict):
            continue
        evidence = event.get("evidence") if isinstance(event.get("evidence"), dict) else event
        kind = str(event.get("event") or event.get("kind") or evidence.get("event") or "")
        if kind not in {EVENT, "traction_surface_optical_coating"} and evidence.get("event") != EVENT:
            if event.get("kind") != "surface_optical_coating":
                continue
        found.append(evidence if evidence.get("event") or evidence.get("coverage") is not None else event)
    return found


def summarize_surface_optical(events: list[dict[str, Any]] | None) -> dict[str, Any]:
    rows = _rows(events)
    coverages = []
    visible = 0
    occluded = 0
    for row in rows:
        if row.get("coverage") is not None:
            coverages.append(float(row["coverage"]))
        if row.get("occluded") or row.get("visibility") == "OCCLUDED":
            occluded += 1
        elif row.get("visibility") == "VISIBLE" or row.get("inside_fov"):
            visible += 1
    discrimination = str((events and isinstance(events, list) and None) or "NOT_AVAILABLE")
    # Caller may attach an already-decided status on a sentinel row.
    for row in rows:
        if row.get("pre_action_context_discrimination"):
            discrimination = str(row["pre_action_context_discrimination"])
    return {
        "section": "PHYSICAL SURFACE OPTICAL COATING",
        "causal_sequence": "deposition at T → coated surface at observation T+1",
        "coating_observation_ticks": len(rows),
        "coverage_values": [round(value, 6) for value in coverages[:12]],
        "visible_count": visible,
        "occluded_count": occluded,
        "agent_symbolic_label": False,
        "traction_encoded_directly": False,
        "material_identity_exposed": False,
        "pre_action_context_discrimination": discrimination if rows else "NOT_AVAILABLE",
        "perceptually_conditioned_prediction": "NOT_ESTABLISHED",
        "material_identity_recognition": "NOT_ESTABLISHED",
        "instrumental_use_established": "NOT_ESTABLISHED",
        "OBSERVED": ["coated_surface_sample"] if rows else [],
        "DERIVED": ["coverage"],
        "NOT_AVAILABLE": [] if rows else ["coating_observation"],
        "NOT_ESTABLISHED": [
            "material_identity_recognition",
            "instrumental_use",
            "preference",
            "autonomous_deposition",
        ],
        "notes": (
            "Anonymous optical channels can differ before movement. "
            "That is not material identity and not instrumental use."
        ),
    }


def format_surface_optical_section(summary: dict[str, Any] | None) -> str:
    summary = summary or {}
    return "\n".join([
        "PHYSICAL SURFACE OPTICAL COATING",
        f"  causal_sequence: {summary.get('causal_sequence')}",
        f"  coating_observation_ticks: {summary.get('coating_observation_ticks')}",
        f"  coverage: {summary.get('coverage_values')}",
        f"  visible_count: {summary.get('visible_count')}",
        f"  occluded_count: {summary.get('occluded_count')}",
        f"  PRE_ACTION_CONTEXT_DISCRIMINATION = {summary.get('pre_action_context_discrimination')}",
        f"  PERCEPTUALLY_CONDITIONED_PREDICTION = {summary.get('perceptually_conditioned_prediction')}",
        "  MATERIAL_IDENTITY_RECOGNITION = NOT_ESTABLISHED",
        "  INSTRUMENTAL_USE = NOT_ESTABLISHED",
        "  OBSERVED: " + ", ".join(summary.get("OBSERVED") or ["NOT_AVAILABLE"]),
        "  DERIVED: " + ", ".join(summary.get("DERIVED") or []),
        "  NOT_ESTABLISHED: " + ", ".join(summary.get("NOT_ESTABLISHED") or []),
    ])


def receipts_from_consequences(run_dir: Path) -> list[dict[str, Any]]:
    path = Path(run_dir) / "scientific_consequences.jsonl"
    found: list[dict[str, Any]] = []
    if not path.exists():
        return found
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            for ref in row.get("event_refs") or []:
                if isinstance(ref, dict) and ref.get("kind") == "surface_optical_coating":
                    found.append(ref)
    return found
