"""SURFACE TRACTION EXPERIENCE. Reads TRACTION_EXPERIENCE receipts only."""
from __future__ import annotations

from typing import Any

_EVENT = "TRACTION_EXPERIENCE"

LEARNING_ESTABLISHED = "NOT_ESTABLISHED"
INSTRUMENTAL_USE = "NOT_ESTABLISHED"
MATERIAL_RECOGNITION = "NOT_ESTABLISHED"
SYMBOLIC_SENSOR = "NOT_IMPLEMENTED"
SPECIAL_CASE_LEARNER = "NOT_IMPLEMENTED"


def _f(row: dict[str, Any], key: str) -> float:
    value = row.get(key)
    if isinstance(value, (list, tuple)) and value:
        return float(value[0])
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _band(row: dict[str, Any]) -> str:
    researcher = row.get("researcher_only_fields") or {}
    deposit = str(researcher.get("deposit_id") or "NONE")
    if deposit in {"", "NONE", "None"}:
        return "empty"
    mult = float(researcher.get("traction_multiplier") or 1.0)
    if abs(mult - 1.0) <= 1e-9:
        return "neutral"
    return "non_neutral"


def _error_decrease(statuses: list[dict[str, Any]]) -> str:
    numeric = [
        float(row["prediction_error_abs_l1"])
        for row in statuses
        if row.get("prediction_error_status") == "OBSERVED"
        and row.get("prediction_error_abs_l1") is not None
    ]
    if len(numeric) < 2:
        return "NOT_AVAILABLE"
    if numeric[-1] < numeric[0] - 1e-6:
        return "OBSERVED"
    return "NOT_OBSERVED"


def summarize_traction_experience(events: list[dict[str, Any]] | None) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for event in events or []:
        if not isinstance(event, dict):
            continue
        kind = str(event.get("event") or event.get("type") or "")
        evidence = event.get("evidence") if isinstance(event.get("evidence"), dict) else event
        if kind != _EVENT and str(evidence.get("event") or "") != _EVENT:
            continue
        rows.append(evidence if evidence is not event else event)

    bands = {"empty": 0, "neutral": 0, "non_neutral": 0}
    commands: list[str] = []
    agents: set[str] = set()
    latencies: list[int] = []
    displacements: list[float] = []
    velocities: list[float] = []
    by_band_disp: dict[str, list[float]] = {"empty": [], "neutral": [], "non_neutral": []}
    pe_statuses: list[dict[str, Any]] = []
    memory_refs: list[Any] = []
    endogenous = 0
    intervention = 0
    visible_names: set[str] = set()
    researcher_names: set[str] = set()
    for row in rows:
        band = _band(row)
        bands[band] = bands.get(band, 0) + 1
        command = str(row.get("selected_motor_command") or "")
        commands.append(command)
        if row.get("agent_id"):
            agents.add(str(row["agent_id"]))
        if row.get("body_id"):
            agents.add(str(row["body_id"]))
        if row.get("action_tick") is not None and row.get("consequence_observation_tick") is not None:
            latencies.append(int(row["consequence_observation_tick"]) - int(row["action_tick"]))
        disp = _f(row, "displacement")
        vel = _f(row, "velocity_after")
        displacements.append(disp)
        velocities.append(vel)
        by_band_disp.setdefault(band, []).append(disp)
        pe_statuses.append({
            "action_tick": row.get("action_tick"),
            "prediction_error_status": row.get("prediction_error_status") or "NOT_AVAILABLE",
            "prediction_error_abs_l1": row.get("prediction_error_abs_l1"),
        })
        if row.get("memory_reference"):
            memory_refs.append(row.get("memory_reference"))
        if str(row.get("action_provenance") or "") == "INTERVENTION":
            intervention += 1
        elif str(row.get("action_provenance") or "") == "ENDOGENOUS":
            endogenous += 1
        for name in row.get("agent_visible_field_names") or []:
            visible_names.add(str(name))
        researcher = row.get("researcher_only_fields") or {}
        if isinstance(researcher, dict):
            researcher_names.update(str(k) for k in researcher)

    neutral_mean = (
        sum(by_band_disp["neutral"]) / len(by_band_disp["neutral"])
        if by_band_disp["neutral"] else None
    )
    empty_mean = (
        sum(by_band_disp["empty"]) / len(by_band_disp["empty"])
        if by_band_disp["empty"] else None
    )
    non_neutral_mean = (
        sum(by_band_disp["non_neutral"]) / len(by_band_disp["non_neutral"])
        if by_band_disp["non_neutral"] else None
    )
    matched = None
    if neutral_mean is not None and (empty_mean is not None or non_neutral_mean is not None):
        matched = {
            "neutral_mean_displacement": neutral_mean,
            "empty_minus_neutral": None if empty_mean is None else empty_mean - neutral_mean,
            "non_neutral_minus_neutral": (
                None if non_neutral_mean is None else non_neutral_mean - neutral_mean
            ),
        }
    same_command = len(set(commands)) <= 1 if commands else None
    pe_available = sum(1 for row in pe_statuses if row["prediction_error_status"] == "OBSERVED")
    decrease = _error_decrease(pe_statuses)
    return {
        "section": "SURFACE TRACTION EXPERIENCE",
        "exposure_episodes": len(rows),
        "action_consequence_latency_ticks": latencies,
        "nominally_matched_move_count": len(rows) if same_command else sum(
            1 for command in commands if command == (commands[0] if commands else "")
        ),
        "same_nominal_action": same_command,
        "distribution": bands,
        "realized_displacement": displacements,
        "realized_velocity_after": velocities,
        "matched_control_difference": matched,
        "prediction_error_observed_count": pe_available,
        "prediction_error_trajectory": pe_statuses,
        "prediction_error_decrease_across_repetition": decrease,
        "memory_references": memory_refs,
        "endogenous_action_count": endogenous,
        "intervention_action_count": intervention,
        "agent_visible_fields": sorted(visible_names),
        "researcher_only_causal_fields": sorted(researcher_names),
        "affected_agent_ids": sorted(agents),
        "OBSERVED": {
            "exposure_episodes": len(rows),
            "motor_commands": commands,
            "displacement": displacements,
            "prediction_error_statuses": [row["prediction_error_status"] for row in pe_statuses],
            "memory_reference_count": len(memory_refs),
        },
        "DERIVED": {
            "matched_control_difference": matched,
            "same_nominal_action": same_command,
            "prediction_error_decrease_across_repetition": decrease,
        },
        "NOT_AVAILABLE": [
            name for name, status in (
                ("prediction_error", "NOT_AVAILABLE" if pe_available == 0 and rows else None),
            ) if status == "NOT_AVAILABLE"
        ],
        "NOT_ESTABLISHED": [
            "material recognition",
            "affinity comprehension",
            "intentional surface creation",
            "instrumental use",
            "learning",
        ],
        "LEARNING_ESTABLISHED": LEARNING_ESTABLISHED,
        "INSTRUMENTAL_USE": INSTRUMENTAL_USE,
        "MATERIAL_RECOGNITION": MATERIAL_RECOGNITION,
        "AGENT_SYMBOLIC_TRACTION_SENSOR": SYMBOLIC_SENSOR,
        "SPECIAL_CASE_MATERIAL_LEARNER": SPECIAL_CASE_LEARNER,
        "mixed_with_resource_change": False,
        "note": (
            "OBSERVED motor command, body consequence, and any ordinary prediction "
            "error or memory reference. LEARNING_ESTABLISHED = NOT_ESTABLISHED. "
            "A smaller error is not recognition or instrumental use."
        ),
    }
