"""SURFACE TRACTION PREDICTION ADAPTATION. Reads adaptation receipts only."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mechanistic_mind.physical_system.surface_traction_prediction import (
    ADAPTATION_K,
    ADAPTATION_N,
    ADAPTATION_OBSERVED,
    EVENT_ADAPTATION,
    INSUFFICIENT_VALID_EPISODES,
    NO_ADAPTATION_OBSERVED,
    PREDICTION_NOT_AVAILABLE,
)

INSTRUMENTAL_USE = "NOT_ESTABLISHED"
CONTEXT_DISCRIMINATION_ESTABLISHED = "NOT_ESTABLISHED"
MATERIAL_RECOGNITION = "NOT_ESTABLISHED"
SYMBOLIC_SENSOR = "NOT_IMPLEMENTED"
SPECIAL_CASE_LEARNER = "NOT_IMPLEMENTED"


def _median(values: list[float]) -> float:
    ordered = sorted(float(v) for v in values)
    count = len(ordered)
    mid = count // 2
    if count % 2:
        return ordered[mid]
    return 0.5 * (ordered[mid - 1] + ordered[mid])


def adaptation_status(errors: list[float]) -> str:
    """Fixed criterion. K and N are not refit per seed."""
    usable = [float(value) for value in errors if value is not None]
    if not usable:
        return PREDICTION_NOT_AVAILABLE
    if len(usable) < ADAPTATION_N:
        return INSUFFICIENT_VALID_EPISODES
    early = _median(usable[:ADAPTATION_K])
    late = _median(usable[-ADAPTATION_K:])
    if late + 1e-6 < early:
        return ADAPTATION_OBSERVED
    return NO_ADAPTATION_OBSERVED


def _rows(events: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for event in events or []:
        if not isinstance(event, dict):
            continue
        kind = str(event.get("event") or event.get("type") or "")
        evidence = event.get("evidence") if isinstance(event.get("evidence"), dict) else event
        if kind != EVENT_ADAPTATION and str(evidence.get("event") or "") != EVENT_ADAPTATION:
            continue
        found.append(evidence)
    return found


def _multiplier(row: dict[str, Any]) -> float | None:
    researcher = row.get("researcher_only_fields") or {}
    try:
        return float(researcher.get("traction_multiplier"))
    except (TypeError, ValueError):
        return None


def _band(row: dict[str, Any]) -> str:
    researcher = row.get("researcher_only_fields") or {}
    deposit = str(researcher.get("deposit_id") or "NONE")
    if deposit in {"", "NONE", "None"}:
        return "empty"
    mult = _multiplier(row)
    if mult is None or abs(mult - 1.0) <= 1e-9:
        return "neutral"
    return "non_neutral"


def summarize_traction_prediction(events: list[dict[str, Any]] | None) -> dict[str, Any]:
    rows = _rows(events)
    phases: dict[str, list[dict[str, Any]]] = {}
    endogenous = 0
    intervention = 0
    excluded = 0
    entered = 0
    available = 0
    revisions = 0
    agents: set[str] = set()
    memory_refs: list[Any] = []
    context_by_band: dict[str, set[str]] = {}
    for row in rows:
        phase = str(row.get("exposure_phase") or "UNSPECIFIED")
        phases.setdefault(phase, []).append(row)
        if str(row.get("action_provenance") or "") == "INTERVENTION":
            intervention += 1
        elif str(row.get("action_provenance") or "") == "ENDOGENOUS":
            endogenous += 1
        if row.get("entered_adaptation_statistics"):
            entered += 1
        else:
            excluded += 1
        if row.get("prediction_availability") == "OBSERVED":
            available += 1
        if row.get("revision_applied"):
            revisions += 1
        if row.get("agent_id"):
            agents.add(str(row["agent_id"]))
        if row.get("memory_reference"):
            memory_refs.append(row.get("memory_reference"))
        signature = row.get("context_signature")
        if signature:
            context_by_band.setdefault(_band(row), set()).add(str(signature))

    def _errors(phase_rows: list[dict[str, Any]]) -> list[float]:
        baseline = None
        values: list[float] = []
        for row in phase_rows:
            if row.get("exclusion_reason") == "VELOCITY_NOT_CONTROLLED":
                continue
            if row.get("exclusion_reason") == "CONTACT_OR_PUSH":
                continue
            if not str(row.get("selected_motor_command") or "").startswith("MOVE:"):
                continue
            signature = row.get("context_signature")
            if baseline is None and signature:
                baseline = signature
            elif signature and baseline is not None and signature != baseline:
                row["exclusion_reason"] = row.get("exclusion_reason") or "CONTEXT_DRIFT"
                row["entered_adaptation_statistics"] = False
                continue
            if row.get("prediction_availability") != "OBSERVED":
                continue
            if row.get("aggregate_error") is None:
                continue
            values.append(float(row["aggregate_error"]))
        return values

    phase_reports = {}
    for name, phase_rows in phases.items():
        errors = _errors(phase_rows) if name != "INTERLEAVED" else [
            float(row["aggregate_error"])
            for row in phase_rows
            if row.get("prediction_availability") == "OBSERVED" and row.get("aggregate_error") is not None
        ]
        phase_reports[name] = {
            "episodes": len(phase_rows),
            "valid_errors": [round(value, 8) for value in errors],
            "early_error": None if len(errors) < ADAPTATION_K else round(_median(errors[:ADAPTATION_K]), 8),
            "late_error": None if len(errors) < ADAPTATION_K else round(_median(errors[-ADAPTATION_K:]), 8),
            "adaptation_status": (
                "NOT_APPLIED"
                if name == "INTERLEAVED"
                else adaptation_status(errors)
            ),
            "commands": sorted({str(row.get("selected_motor_command") or "") for row in phase_rows}),
        }

    stable = phase_reports.get("NON_NEUTRAL_STABLE", {}).get("adaptation_status", PREDICTION_NOT_AVAILABLE)
    if "NON_NEUTRAL_STABLE" not in phase_reports:
        stable = PREDICTION_NOT_AVAILABLE
    high_errors = phase_reports.get("NON_NEUTRAL_STABLE", {}).get("valid_errors") or []
    return_errors = phase_reports.get("RETURN_NEUTRAL", {}).get("valid_errors") or []
    unseen_errors = phase_reports.get("UNSEEN_MAGNITUDE", {}).get("valid_errors") or []
    reversal = "NOT_AVAILABLE"
    if high_errors and return_errors:
        reversal = "OBSERVED" if return_errors[0] > high_errors[-1] + 1e-6 else "NOT_OBSERVED"
    unseen = "NOT_AVAILABLE"
    if unseen_errors and (return_errors or high_errors):
        prior = return_errors[-1] if return_errors else high_errors[-1]
        unseen = "OBSERVED" if unseen_errors[0] > prior + 1e-6 else "NOT_OBSERVED"
    interleaved_errors = phase_reports.get("INTERLEAVED", {}).get("valid_errors") or []
    interleaved = "NOT_AVAILABLE"
    if interleaved_errors:
        interleaved = "SWITCH_ERROR_PERSISTS" if min(interleaved_errors) > 0.005 else "NOT_OBSERVED"

    signatures = [set(values) for values in context_by_band.values() if values]
    shared = False
    for index, left in enumerate(signatures):
        for right in signatures[index + 1:]:
            if left & right:
                shared = True
    discrimination = "NOT_AVAILABLE" if shared or len(signatures) < 2 else "NOT_ESTABLISHED"

    return {
        "section": "SURFACE TRACTION PREDICTION ADAPTATION",
        "causal_sequence": "action → prediction → physical outcome → error → revision",
        "criterion": {
            "K": ADAPTATION_K,
            "N": ADAPTATION_N,
            "rule": "median(last K) < median(first K) on valid matched episodes",
        },
        "exposure_episodes": len(rows),
        "prediction_availability_rate": (available / len(rows)) if rows else 0.0,
        "valid_exposure_count": entered,
        "excluded_exposure_count": excluded,
        "phases": phase_reports,
        "revision_count": revisions,
        "memory_references": memory_refs[-8:],
        "endogenous_action_count": endogenous,
        "intervention_action_count": intervention,
        "affected_agent_ids": sorted(agents),
        "pre_action_context_discrimination": discrimination,
        "stable_regime_adaptation": stable,
        "reversal": reversal,
        "unseen_magnitude_first_error_exceeds_prior": unseen,
        "interleaved_regime": interleaved,
        "OBSERVED": [
            item for item in (
                "prediction_availability" if available else None,
                "revision_applied" if revisions else None,
                "stable_regime_error_decrease" if stable == ADAPTATION_OBSERVED else None,
            )
            if item
        ],
        "DERIVED": [
            "early_error",
            "late_error",
            "adaptation_status",
            "reversal",
            "interleaved_regime",
        ],
        "NOT_AVAILABLE": [
            item for item in (
                "pre_action_context_discrimination" if discrimination == "NOT_AVAILABLE" else None,
                "symbolic_material_input",
            )
            if item
        ],
        "NOT_ESTABLISHED": [
            "material_recognition",
            "affinity_comprehension",
            "pre_action_surface_discrimination",
            "intentional_surface_creation",
            "instrumental_use",
            "learning_as_understanding",
        ],
        "instrumental_use_established": INSTRUMENTAL_USE,
        "context_discrimination_established": CONTEXT_DISCRIMINATION_ESTABLISHED,
        "material_recognition": MATERIAL_RECOGNITION,
        "symbolic_sensor": SYMBOLIC_SENSOR,
        "special_case_learner": SPECIAL_CASE_LEARNER,
        "notes": (
            "A smaller error is adaptation of the existing running mean. "
            "It is not recognition, affinity comprehension, or instrumental use."
        ),
    }


def receipts_from_consequences(run_dir: Path) -> list[dict[str, Any]]:
    """Bounded refs already stored on consequence receipts. No payload copy."""
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
                if isinstance(ref, dict) and ref.get("kind") == "traction_prediction_adaptation":
                    found.append(ref)
    return found


def format_traction_prediction_section(summary: dict[str, Any] | None) -> str:
    summary = summary or {}
    phases = summary.get("phases") or {}
    lines = [
        "SURFACE TRACTION PREDICTION ADAPTATION",
        f"  causal_sequence: {summary.get('causal_sequence') or 'action → prediction → physical outcome → error → revision'}",
        f"  prediction_availability_rate: {summary.get('prediction_availability_rate')}",
        f"  valid_exposure_count: {summary.get('valid_exposure_count')}",
        f"  excluded_exposure_count: {summary.get('excluded_exposure_count')}",
        f"  revision_count: {summary.get('revision_count')}",
        f"  intervention_action_count: {summary.get('intervention_action_count')}",
        f"  endogenous_action_count: {summary.get('endogenous_action_count')}",
        f"  memory_references: {summary.get('memory_references')}",
        f"  PRE_ACTION_CONTEXT_DISCRIMINATION = {summary.get('pre_action_context_discrimination')}",
        f"  STABLE_REGIME_ADAPTATION = {summary.get('stable_regime_adaptation')}",
        f"  reversal: {summary.get('reversal')}",
        f"  interleaved_regime: {summary.get('interleaved_regime')}",
        f"  unseen_magnitude: {summary.get('unseen_magnitude_first_error_exceeds_prior')}",
        f"  LEARNING_AS_UNDERSTANDING = NOT_ESTABLISHED",
        f"  CONTEXT_DISCRIMINATION = {summary.get('context_discrimination_established')}",
        f"  INSTRUMENTAL_USE = {summary.get('instrumental_use_established')}",
        "  OBSERVED: " + ", ".join(summary.get("OBSERVED") or ["NOT_AVAILABLE"]),
        "  DERIVED: " + ", ".join(summary.get("DERIVED") or []),
        "  NOT_AVAILABLE: " + ", ".join(summary.get("NOT_AVAILABLE") or []),
        "  NOT_ESTABLISHED: " + ", ".join(summary.get("NOT_ESTABLISHED") or []),
    ]
    for name in (
        "NEUTRAL_BASELINE",
        "NON_NEUTRAL_STABLE",
        "RETURN_NEUTRAL",
        "UNSEEN_MAGNITUDE",
        "INTERLEAVED",
    ):
        phase = phases.get(name)
        if not isinstance(phase, dict):
            continue
        lines.append(
            "  phase {name}: episodes={episodes} early={early} late={late} status={status}".format(
                name=name,
                episodes=phase.get("episodes"),
                early=phase.get("early_error"),
                late=phase.get("late_error"),
                status=phase.get("adaptation_status"),
            )
        )
        errors = phase.get("valid_errors") or []
        if errors:
            lines.append("    error_by_episode: " + ", ".join(str(value) for value in errors[:12]))
    return "\n".join(lines)
