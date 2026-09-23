"""Scientific Telemetry V2 — tiered long-run evidence (storage architecture).

Levels:
  0 META / static authorities — once + on regime change
  1 COMPACT TIMELINE — per-(tick, agent) scalars + minimal vision
  2 STRUCTURAL EVENTS — Analyzer-relevant events with compact payloads
  3 CHECKPOINTS — periodic full GEO/cognition snapshots (optional)

Does NOT alter physics, cognition, PSC, vision, or signal semantics.
Does NOT invent psychological events.

Exhaustiveness:
  V2 event stream is NOT exhaustive for every runtime structured event.
  Absent bookkeeping types (e.g. SITE_GEOMETRY_CHANGED) mean NOT_RECORDED_IN_V2,
  not "did not occur". Analyzer-relevant families below are exhaustively captured
  when emitted by the runtime (compacted, not dropped).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

# --- Schema / mode -----------------------------------------------------------

TELEMETRY_MODE_V1 = "SCIENTIFIC_V1_REFERENCE"
TELEMETRY_MODE_V2 = "SCIENTIFIC_V2_TIERED"

SCHEMA_TICK_V1 = "mm.psy_observer_web.scientific_tick.v1"
SCHEMA_TICK_V2 = "mm.psy_observer_web.scientific_tick.v2"
SCHEMA_EVENT_V1 = "mm.psy_observer_web.scientific_event.v1"
SCHEMA_EVENT_V2 = "mm.psy_observer_web.scientific_event.v2"
SCHEMA_META_V2 = "mm.psy_observer_web.scientific_meta.v2"
SCHEMA_CHECKPOINT_V2 = "mm.psy_observer_web.scientific_checkpoint.v2"

TELEMETRY_MAJOR = 2
TELEMETRY_MINOR = 0

DEFAULT_CHECKPOINT_EVERY = 10_000
SEEN_KEY_TICK_WINDOW = 8

ANALYZER_EXHAUSTIVE_EVENT_PREFIXES = (
    "SCENARIO_",
    "DISCRETE_ACTION_",
    "PREDICTION_",
    "OBSERVATION_ACQUIRED",
    "DEFORM",
    "WORK_LIMIT",
    "WORK_UNAVAILABLE",
    "LIMITING",
    "CONVERSION",
    "RESOURCE_CONVERTED",
    "PHYSICAL_SIGNAL_",
    "SIGNAL_",
    "WORLD_INTERVENTION",
    "EXPERIMENTER_",
    "CONTACT",
    "NECK_",
    "PUSH_",
)

V2_OMIT_EVENT_TYPES = frozenset({
    "SITE_GEOMETRY_CHANGED",
    "BODY_MOVED",
    "BODY_ROTATED",
    "LOCAL_MATERIAL_CHANGED",
    "WORK_TRANSFERRED",
    "WORK_ALLOCATED",
    "MOTOR_IMPULSE",
    "FORCE_APPLIED",
    "ENVIRONMENTAL_FORCE",
    "RESOURCE_TRANSFER",
    "INTERNAL_MEDIUM_UPDATE",
})


def event_exhaustiveness_policy() -> dict[str, Any]:
    return {
        "telemetry_mode": TELEMETRY_MODE_V2,
        "analyzer_exhaustive_families": list(ANALYZER_EXHAUSTIVE_EVENT_PREFIXES),
        "omitted_types_mean": "NOT_RECORDED_IN_V2",
        "omitted_types_do_not_mean": "DID_NOT_OCCUR",
        "omitted_examples": sorted(V2_OMIT_EVENT_TYPES),
        "scenario_payload": "COMPACT_SUMMARY_RICH_GRAPH_NOT_STORED",
        "geo_receipts_on_timeline": "CHECKPOINT_ONLY",
    }


def evidence_requirements_matrix() -> list[dict[str, Any]]:
    rows = [
        ("seed / world dims / boundary", "STATIC_METADATA", ["Analyzer", "replay"]),
        ("vision radius (unchanged)", "STATIC_METADATA", ["Analyzer", "VF"]),
        ("vision radius change", "EVENT_ONLY_SUFFICIENT", ["Analyzer", "VF", "interventions"]),
        ("body x,y,theta,vx,vy,speed", "EVERY_TICK_REQUIRED", ["Analyzer", "trajectory"]),
        ("action / action_source", "EVERY_TICK_REQUIRED", ["Analyzer", "action"]),
        ("work / resource_A/B / contact", "EVERY_TICK_REQUIRED", ["Analyzer", "resources", "interaction"]),
        ("prediction_count / prospective_compositions", "EVERY_TICK_REQUIRED", ["Analyzer", "cognition"]),
        ("vision_optical final_exo / body_exposure", "EVERY_TICK_REQUIRED", ["Visual Forensics"]),
        ("vision_optical neighbors_optical", "EVERY_TICK_REQUIRED", ["Visual Forensics"]),
        ("vision note/semantics strings", "STATIC_METADATA", ["debug only"]),
        ("action_realization / work_ecology / locomotor", "CHECKPOINT_SUFFICIENT", ["geometry offline", "debug"]),
        ("SCENARIO_SELECTED counts + action", "EVENT_ONLY_SUFFICIENT", ["Analyzer cognition"]),
        ("SCENARIO composition_path graphs", "CHECKPOINT_SUFFICIENT", ["deep cognition forensics"]),
        ("DISCRETE_ACTION_SELECTED", "EVENT_ONLY_SUFFICIENT", ["Analyzer"]),
        ("DEFORM / CONVERSION / WORK_LIMIT", "EVENT_ONLY_SUFFICIENT", ["Analyzer"]),
        ("PHYSICAL_SIGNAL emit/receive", "EVENT_ONLY_SUFFICIENT", ["Signal Forensics"]),
        ("WORLD_INTERVENTION", "EVENT_ONLY_SUFFICIENT", ["regime history"]),
        ("SITE_GEOMETRY_CHANGED / BODY_MOVED forces", "CHECKPOINT_SUFFICIENT", ["geometry offline"]),
        ("schema string per row", "STATIC_METADATA", ["versioning"]),
    ]
    return [{"field": f, "class": c, "consumers": cons} for f, c, cons in rows]


def compact_vision_optical_v2(vo: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(vo, dict):
        return None
    if not vo.get("available", True) and vo.get("reason"):
        return {
            "available": False,
            "reason": vo.get("reason"),
            "vision_enabled": bool(vo.get("vision_enabled", False)),
            "body_optics_enabled": bool(vo.get("body_optics_enabled", False)),
            "identity_layer": "OBSERVER_GT_ONLY",
        }
    exo = vo.get("final_exo") or vo.get("exo") or {}
    neighbors = vo.get("neighbors_optical") or []
    sources = vo.get("source_bodies_gt") or []
    keep_neighbors = any(
        float(n.get("body_optical") or 0.0) > 0.0 for n in neighbors if isinstance(n, dict)
    )
    out: dict[str, Any] = {
        "available": True,
        "final_exo": {k: float(exo.get(k) or 0.0) for k in ("exo_0", "exo_1", "exo_2")},
        "exo_without_foreign_bodies": vo.get("exo_without_foreign_bodies"),
        "foreign_body_contribution": vo.get("foreign_body_contribution"),
        "foreign_body_total": vo.get("foreign_body_total"),
        "body_exposure": vo.get("body_exposure"),
        "illumination": vo.get("illumination"),
        "vision_enabled": vo.get("vision_enabled", vo.get("vision_contributes", True)),
        "body_optics_enabled": vo.get("body_optics_enabled", vo.get("body_optical_enabled", True)),
        "vision_radius": vo.get("vision_radius", vo.get("radius")),
        "field_reception": bool(vo.get("field_reception")),
        "identity_layer": "OBSERVER_GT_ONLY",
    }
    if keep_neighbors:
        out["neighbors_optical"] = neighbors
        out["source_bodies_gt"] = sources
    elif vo.get("body_exposure"):
        out["source_bodies_gt"] = sources
    return out


def compact_tick_row_v2(row: dict[str, Any]) -> dict[str, Any]:
    vo = compact_vision_optical_v2(
        row.get("vision_optical") if isinstance(row.get("vision_optical"), dict) else None
    )
    return {
        "schema": SCHEMA_TICK_V2,
        "telemetry_tier": "LEVEL_1_COMPACT_TIMELINE",
        "tick": row.get("tick"),
        "agent_id": row.get("agent_id"),
        "body_id": row.get("body_id"),
        "action": row.get("action"),
        "action_source": row.get("action_source"),
        "x": row.get("x"),
        "y": row.get("y"),
        "theta": row.get("theta"),
        "omega": row.get("omega"),
        "body_alpha": row.get("body_alpha"),
        "head_relative_angle": row.get("head_relative_angle"),
        "head_world_heading": row.get("head_world_heading"),
        "head_omega": row.get("head_omega"),
        "vest_0": row.get("vest_0"),
        "vest_1": row.get("vest_1"),
        "prop_neck_0": row.get("prop_neck_0"),
        "prop_neck_1": row.get("prop_neck_1"),
        "osc_emit_active": row.get("osc_emit_active"),
        "osc_frequency": row.get("osc_frequency"),
        "osc_amplitude": row.get("osc_amplitude"),
        "osc_emit_remaining": row.get("osc_emit_remaining"),
        "osc_l_energy": row.get("osc_l_energy"),
        "osc_r_energy": row.get("osc_r_energy"),
        "vx": row.get("vx"),
        "vy": row.get("vy"),
        "speed": row.get("speed"),
        "work": row.get("work"),
        "resource_A": row.get("resource_A"),
        "resource_B": row.get("resource_B"),
        "contact": row.get("contact"),
        "prediction_count": row.get("prediction_count"),
        "prospective_compositions": row.get("prospective_compositions"),
        "work_action_allocated": row.get("work_action_allocated"),
        "agent_seed": row.get("agent_seed"),
        "vision_optical": vo,
        "observer_undercover": row.get("observer_undercover"),
    }


def _event_type(ev: dict[str, Any]) -> str:
    return str(ev.get("type") or ev.get("kind") or "")


def should_record_event_v2(ev: dict[str, Any]) -> bool:
    et = _event_type(ev)
    if not et:
        return False
    if et in V2_OMIT_EVENT_TYPES:
        return False
    upper = et.upper()
    for prefix in ANALYZER_EXHAUSTIVE_EVENT_PREFIXES:
        if upper.startswith(prefix) or prefix.rstrip("_") in upper:
            return True
    return False


def compact_scenario_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    selected = evidence.get("selected_scenario") if isinstance(evidence.get("selected_scenario"), dict) else {}
    return {
        "selected_action": evidence.get("selected_action") or selected.get("action") or evidence.get("action"),
        "action": evidence.get("action") or selected.get("action"),
        "selection_source": evidence.get("selection_source") or selected.get("selection_source"),
        "actor_agent_id": evidence.get("actor_agent_id"),
        "body_id": evidence.get("body_id"),
        "scenario_id": selected.get("scenario_id") or selected.get("id") or evidence.get("scenario_id"),
        "score": selected.get("score") or selected.get("total_score") or evidence.get("score"),
        "v2_payload": "COMPACT_SUMMARY",
        "rich_composition_path": "NOT_STORED_IN_V2_EVENTS",
    }


def compact_signal_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    keep_keys = (
        "channel", "trigger", "emission_id", "receipt_id", "intensity", "realized",
        "local.FIELD_A", "local.FIELD_B", "source_attribution",
        "emitter_agent_id", "receiver_agent_id", "emitter_body_id", "receiver_body_id",
        "contributing_emissions_this_tick", "field",
    )
    return {k: evidence[k] for k in keep_keys if k in evidence}


def compact_event_v2(ev: dict[str, Any]) -> dict[str, Any] | None:
    if not should_record_event_v2(ev):
        return None
    et = _event_type(ev)
    evidence = ev.get("evidence") if isinstance(ev.get("evidence"), dict) else {}
    payload: dict[str, Any] = {
        "schema": SCHEMA_EVENT_V2,
        "telemetry_tier": "LEVEL_2_STRUCTURAL_EVENT",
        "type": et,
        "kind": ev.get("kind", et),
        "tick": ev.get("tick"),
        "agent_id": ev.get("agent_id"),
        "actor_agent_id": ev.get("actor_agent_id"),
        "emitter_agent_id": ev.get("emitter_agent_id"),
        "receiver_agent_id": ev.get("receiver_agent_id"),
        "event_id": ev.get("event_id"),
        "emission_id": ev.get("emission_id"),
        "receipt_id": ev.get("receipt_id"),
    }
    payload = {k: v for k, v in payload.items() if v is not None}

    if et == "SCENARIO_SELECTED" or et.startswith("SCENARIO_"):
        payload["evidence"] = compact_scenario_evidence(evidence)
    elif "SIGNAL" in et.upper():
        payload["evidence"] = compact_signal_evidence(evidence)
    elif et == "WORLD_INTERVENTION" or et.startswith("WORLD_INTERVENTION"):
        keep = (
            "category", "path", "old", "new", "old_value", "new_value",
            "fingerprint_before", "fingerprint_after", "source",
            "requires_reset", "generation", "runtime_generation", "changes",
        )
        payload["evidence"] = {k: evidence[k] for k in keep if k in evidence}
        for k in ("category", "path", "old", "new", "fingerprint_before", "fingerprint_after", "source"):
            if k in ev and k not in payload:
                payload[k] = ev[k]
    elif et == "DISCRETE_ACTION_SELECTED":
        payload["evidence"] = {
            "selected_action": evidence.get("selected_action") or evidence.get("action"),
            "action": evidence.get("action"),
            "selection_source": evidence.get("selection_source"),
            "actor_agent_id": evidence.get("actor_agent_id"),
            "body_id": evidence.get("body_id"),
        }
    else:
        lean = {}
        for k in (
            "selected_action", "action", "selection_source", "agent_id", "body_id",
            "work", "amount", "resource", "channel", "outcome",
        ):
            if k in evidence:
                lean[k] = evidence[k]
        payload["evidence"] = lean
    return payload


def build_checkpoint_v2(
    *,
    tick: int,
    full_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema": SCHEMA_CHECKPOINT_V2,
        "telemetry_tier": "LEVEL_3_CHECKPOINT",
        "tick": int(tick),
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "rows": full_rows,
        "note": (
            "Observer/geometry forensic snapshot. Not required for ordinary Analyzer "
            "aggregates. Deterministic resume requires separate RNG/runtime snapshot."
        ),
    }


def detect_telemetry_schema(
    meta: dict[str, Any] | None, sample_row: dict[str, Any] | None = None
) -> str:
    if isinstance(meta, dict):
        mode = str(meta.get("telemetry_mode") or "")
        if mode == TELEMETRY_MODE_V2 or str(meta.get("schema") or "").endswith(".v2"):
            return "V2_TIERED"
        if meta.get("telemetry_schema_major") == 2:
            return "V2_TIERED"
    if isinstance(sample_row, dict):
        sch = str(sample_row.get("schema") or "")
        if "tick.v2" in sch or sample_row.get("telemetry_tier"):
            return "V2_TIERED"
    return "V1_FULL"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
