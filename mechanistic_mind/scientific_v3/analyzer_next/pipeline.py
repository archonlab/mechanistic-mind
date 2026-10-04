"""Orchestrate Analyzer Next — TickStory + sensorimotor consequence + report."""
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

from mechanistic_mind.scientific_v3.api import RunEvidence

from .action_streaks import compute_agent_action_metrics
from .contrasts import build_contrasts
from .episodes import Episode, episode_counts, extract_episodes
from .interestingness import select_interesting_episodes, select_interesting_stories
from .joins import apply_joins
from .relationships import RelationshipGraph
from .report import SECTION_TITLE, format_behavioral_reconstruction, format_sensorimotor_section, format_action_conditioned_model_section, format_historical_sensorimotor_selection_section
from .smc_hss_from_decisions import aggregate_sensorimotor_consequence_model, aggregate_historical_sensorimotor_selection
from .signal_conditioned_selection import aggregate_signal_conditioned_selection
from .signal_conditioned_selection_report import format_signal_conditioned_selection
from .full_embodied_predictive_model import aggregate_full_embodied_predictive_model, format_full_embodied_predictive_model
from .full_composite_psc_shadow import aggregate_full_composite_psc_shadow, format_full_composite_psc_shadow
from .psc_motor_resolution_developmental import aggregate_psc_motor_resolution_developmental, format_psc_motor_resolution_developmental
from .vision_analysis import analyze_beta31_vision
from .volumetric_physical_causal_reconstruction import (
    build_volumetric_physical_causal_reconstruction,
    format_volumetric_physical_causal_section,
)
from mechanistic_mind.scientific_v3.traction_prediction_summary import (
    format_traction_prediction_section,
    receipts_from_consequences,
    summarize_traction_prediction,
)
from mechanistic_mind.scientific_v3.surface_optical_summary import (
    format_surface_optical_section,
    receipts_from_consequences as optical_receipts_from_consequences,
    summarize_surface_optical,
)
from mechanistic_mind.scientific_v3.world_material_summary import (
    format_world_material_section,
    receipts_from_consequences as material_tx_receipts_from_consequences,
    summarize_world_material,
)
from mechanistic_mind.scientific_v3.procedural_surface_columns_summary import (
    format_procedural_surface_columns_section,
    receipts_from_consequences as column_receipts_from_consequences,
    summarize_procedural_surface_columns,
)
from mechanistic_mind.scientific_v3.free_object_kinematics_summary import (
    format_free_object_kinematics_section,
    free_object_receipts_from_consequences,
    summarize_free_object_kinematics,
)
from mechanistic_mind.scientific_v3.body_object_impulse_summary import (
    body_object_impulse_receipts_from_consequences,
    format_body_object_impulse_section,
    summarize_body_object_impulse,
)
from mechanistic_mind.scientific_v3.body_object_impact_acoustics_summary import (
    body_object_impact_acoustic_receipts_from_consequences,
    format_body_object_impact_acoustics_section,
    summarize_body_object_impact_acoustics,
)
from mechanistic_mind.scientific_v3.held_foreign_body_contact_summary import (
    format_held_foreign_body_contact_section,
    held_foreign_body_receipts_from_consequences,
    summarize_held_foreign_body_contact,
)
from mechanistic_mind.scientific_v3.held_resource_object_terrain_contact_summary import (
    format_held_resource_object_terrain_contact_section,
    held_resource_object_terrain_contact_receipts_from_consequences,
    summarize_held_resource_object_terrain_contact,
)
from mechanistic_mind.scientific_v3.held_resource_object_terrain_mechanical_transmission_summary import (
    format_held_resource_object_terrain_mechanical_transmission_section,
    held_resource_object_terrain_mechanical_transmission_receipts_from_consequences,
    summarize_held_resource_object_terrain_mechanical_transmission,
)
from mechanistic_mind.scientific_v3.held_mediated_surface_exertion_integration_summary import (
    format_held_mediated_surface_exertion_integration_section,
    held_mediated_surface_exertion_integration_receipts_from_consequences,
    summarize_held_mediated_surface_exertion_integration,
)
from mechanistic_mind.scientific_v3.detached_terrain_material_initial_placement_summary import (
    format_detached_terrain_material_initial_placement_section,
    detached_terrain_material_initial_placement_receipts_from_consequences,
    summarize_detached_terrain_material_initial_placement,
)
from mechanistic_mind.scientific_v3.bnlt_move_breakaway_locomotion_repair_summary import (
    format_bnlt_move_breakaway_locomotion_repair_section,
    bnlt_move_breakaway_locomotion_repair_receipts_from_consequences,
    summarize_bnlt_move_breakaway_locomotion_repair,
)
from mechanistic_mind.scientific_v3.repeated_conservative_surface_column_separation_summary import (
    format_repeated_conservative_surface_column_separation_section,
    repeated_conservative_surface_column_separation_receipts_from_consequences,
    summarize_repeated_conservative_surface_column_separation,
)
from mechanistic_mind.scientific_v3.event_driven_crowded_placement_retry_contract_summary import (
    format_crowded_placement_retry_section,
    crowded_placement_retry_receipts_from_consequences,
    summarize_crowded_placement_retry,
)
from mechanistic_mind.scientific_v3.detached_material_amount_scaled_collision_radius_summary import (
    format_detached_material_size_geometry_section,
    detached_material_size_geometry_receipts_from_consequences,
    summarize_detached_material_size_geometry,
)
from mechanistic_mind.scientific_v3.held_combine_radius_resize_transaction_summary import (
    format_held_combine_radius_resize_section,
    held_combine_radius_resize_receipts_from_consequences,
    summarize_held_combine_radius_resize,
)
from mechanistic_mind.scientific_v3.held_deposition_radius_shrink_transaction_summary import (
    format_held_deposition_radius_shrink_section,
    held_deposition_radius_shrink_receipts_from_consequences,
    summarize_held_deposition_radius_shrink,
)
from mechanistic_mind.scientific_v3.free_space_state_and_pe_authority_contract_summary import (
    format_free_space_state_and_pe_authority_section,
    free_space_state_and_pe_authority_receipts_from_consequences,
    summarize_free_space_state_and_pe_authority,
)
from mechanistic_mind.scientific_v3.vertical_terrain_landing_contact_response_summary import (
    format_vertical_terrain_landing_contact_response_section,
    vertical_terrain_landing_receipts_from_consequences,
    summarize_vertical_terrain_landing_contact_response,
)
from mechanistic_mind.scientific_v3.vertical_impact_acoustic_emission_summary import (
    format_vertical_impact_acoustic_emission_section,
    vertical_impact_acoustic_receipts_from_consequences,
    summarize_vertical_impact_acoustic_emission,
)
from mechanistic_mind.scientific_v3.authoritative_physical_acoustic_stream_summary import (
    format_authoritative_physical_acoustic_stream_section,
    acoustic_stream_records_from_consequences,
    summarize_authoritative_physical_acoustic_stream,
)
from mechanistic_mind.scientific_v3.observer_acoustic_probe_summary import (
    format_observer_acoustic_probe_section,
    probe_samples_from_consequences,
    summarize_observer_acoustic_probe,
)
from mechanistic_mind.scientific_v3.physical_frequency_amplitude_calibration_summary import (
    format_acoustic_calibration_section,
    calibration_records_from_consequences,
    summarize_acoustic_calibration,
)
from mechanistic_mind.scientific_v3.canonical_physical_field_sonification_summary import (
    format_canonical_sonification_section,
    summarize_canonical_sonification,
)
from mechanistic_mind.scientific_v3.selected_organism_auditory_summary import (
    auditory_boundary_receipts_from_consequences,
    format_selected_organism_auditory_section,
    summarize_selected_organism_auditory,
)
from mechanistic_mind.scientific_v3.selected_organism_auditory_sonification_summary import (
    format_selected_organism_auditory_sonification_section,
    summarize_selected_organism_auditory_sonification,
)
from mechanistic_mind.scientific_v3.organism_auditory_transformation_trace_summary import (
    format_organism_auditory_transformation_trace_section,
    summarize_organism_auditory_transformation_traces,
    transformation_traces_from_consequences,
)
from mechanistic_mind.scientific_v3.selected_organism_physical_field_comparison_summary import (
    format_sav3_comparison_section,
    summarize_sav3_comparison,
)
from mechanistic_mind.scientific_v3.selected_organism_auditory_offline_reconstruction_sav4a_summary import (
    format_sav4a_section,
    summarize_sav4a_offline_reconstruction,
)
from mechanistic_mind.scientific_v3.release_and_excavation_support_loss_summary import (
    format_release_and_excavation_support_loss_section,
    release_excavation_support_loss_receipts_from_consequences,
    summarize_release_and_excavation_support_loss,
)
from mechanistic_mind.scientific_v3.elevation_free_space_visualization_summary import (
    format_elevation_free_space_section,
    summarize_elevation_free_space_story,
)
from mechanistic_mind.scientific_v3.held_translational_impulse_summary import (
    format_held_translational_impulse_section,
    held_translational_impulse_receipts_from_consequences,
    summarize_held_translational_impulse,
)
from mechanistic_mind.scientific_v3.effector_work_held_load_summary import (
    format_effector_work_held_load_section,
    effector_work_held_load_receipts_from_consequences,
    summarize_effector_work_held_load,
)
from mechanistic_mind.scientific_v3.surface_elevation_support_summary import (
    format_surface_elevation_support_section,
    surface_elevation_support_receipts_from_consequences,
    summarize_surface_elevation_support,
)
from mechanistic_mind.scientific_v3.flat_ground_gravity_summary import (
    format_flat_ground_gravity_section,
    flat_ground_gravity_receipts_from_consequences,
    summarize_flat_ground_gravity,
)
from mechanistic_mind.scientific_v3.free_object_ground_friction_summary import (
    format_free_object_ground_friction_section,
    free_object_ground_friction_receipts_from_consequences,
    summarize_free_object_ground_friction,
)
from mechanistic_mind.scientific_v3.body_normal_load_traction_summary import (
    format_body_normal_load_traction_section,
    body_normal_load_traction_receipts_from_consequences,
    summarize_body_normal_load_traction,
)
from mechanistic_mind.scientific_v3.continuous_surface_geometry_summary import (
    format_continuous_surface_geometry_section,
    continuous_surface_geometry_receipts_from_consequences,
    summarize_continuous_surface_geometry,
)
from mechanistic_mind.scientific_v3.body_static_traction_summary import (
    format_body_static_traction_section,
    body_static_traction_receipts_from_consequences,
    summarize_body_static_traction,
)
from mechanistic_mind.scientific_v3.free_resource_object_static_traction_summary import (
    format_free_resource_object_static_traction_section,
    free_resource_object_static_traction_receipts_from_consequences,
    summarize_free_resource_object_static_traction,
)
from mechanistic_mind.scientific_v3.ses_decomposition_contract_summary import (
    format_ses_decomposition_contract_section,
    summarize_ses_decomposition_contract_run,
)
from mechanistic_mind.scientific_v3.ses_runtime_transition_classifier_summary import (
    format_ses_runtime_transition_classifier_section,
    summarize_ses_runtime_transition_classifier_run,
)
from mechanistic_mind.scientific_v3.radius_aware_face_sweep_summary import (
    format_radius_aware_face_sweep_section,
    summarize_radius_aware_face_sweep_run,
)
from mechanistic_mind.scientific_v3.diagnostic_normal_load_shadow_summary import (
    format_diagnostic_normal_load_shadow_section,
    summarize_diagnostic_normal_load_shadow_run,
)
from mechanistic_mind.scientific_v3.continuous_gravitational_pe_diagnostic_shadow_summary import (
    format_continuous_gravitational_pe_diagnostic_shadow_section,
    summarize_continuous_gravitational_pe_diagnostic_shadow_run,
)
from mechanistic_mind.scientific_v3.radius_aware_support_summary import (
    format_radius_aware_support_section,
    radius_aware_support_receipts_from_consequences,
    summarize_radius_aware_support,
)
from mechanistic_mind.scientific_v3.resource_object_pair_impact_acoustics_summary import (
    resource_object_pair_impact_acoustic_receipts_from_consequences,
    format_resource_object_pair_impact_acoustics_section,
    summarize_resource_object_pair_impact_acoustics,
)

from mechanistic_mind.scientific_v3.resource_object_pair_contact_summary import (
    format_resource_object_pair_contact_section,
    resource_object_pair_contact_receipts_from_consequences,
    summarize_resource_object_pair_contact,
)
from mechanistic_mind.scientific_v3.resource_object_pair_impulse_summary import (
    format_resource_object_pair_impulse_section,
    resource_object_pair_impulse_receipts_from_consequences,
    summarize_resource_object_pair_impulse,
)
from mechanistic_mind.scientific_v3.body_object_contact_summary import (
    body_object_receipts_from_consequences,
    format_body_object_contact_section,
    summarize_body_object_contact,
)
from mechanistic_mind.scientific_v3.physical_contact_acoustic_summary import (
    contact_receipts_from_consequences,
    format_physical_contact_acoustic_section,
    summarize_physical_contact_acoustics,
)
from mechanistic_mind.scientific_v3.local_physical_signal_summary import (
    format_local_physical_signal_section,
    receipts_from_consequences as local_signal_receipts_from_consequences,
    summarize_local_physical_signal,
)
from mechanistic_mind.scientific_v3.surface_column_transfer_summary import (
    format_surface_column_transfer_section,
    receipts_from_consequences as transfer_receipts_from_consequences,
    summarize_surface_column_transfer,
)
from mechanistic_mind.scientific_v3.spatial_contents_summary import (
    format_spatial_contents_section,
    receipts_from_consequences as spatial_receipts_from_consequences,
    summarize_spatial_contents,
)
from .sensorimotor import (
    TARGET_INTERVALS,
    build_sensorimotor_steps,
    detect_motor_reversals,
    detect_sensorimotor_trend_reversals,
    explain_visual_asymmetry,
    find_receding_while_watching,
    longitudinal_comparison,
    reconstruct_interval,
    summarize_steps,
)
from .tick_stories import TickStory, build_tick_stories


def _pose_from_story(s: TickStory) -> dict[str, Any] | None:
    for d in s.derived_changes:
        if d.get("kind") == "POSE_STATE":
            return d
    return None


def _peer_geom(s: TickStory) -> dict[str, Any] | None:
    for d in s.derived_changes:
        if d.get("kind") == "RELATIVE_GEOMETRY":
            return d
    return None


def _signal_state(s: TickStory) -> dict[str, Any]:
    emitted = False
    received = False
    for c in s.external_context:
        k = c.get("kind")
        if k == "SIGNAL_EMISSION":
            emitted = True
        elif k == "SIGNAL_RECEPTION":
            received = True
    return {"emitted": emitted, "received": received}


def _terrain_assisted_candidate(s: TickStory) -> dict[str, Any]:
    """Operational: displacement not collinear with selected locomotion. Not intent."""
    pose_delta = ((s.consequence or {}).get("pose_delta") or {}) if s.consequence else {}
    dx = float(pose_delta.get("dx") or 0.0)
    dy = float(pose_delta.get("dy") or 0.0)
    loco = str(((s.motor or {}).get("components") or {}).get("locomotion") or "WAIT")
    axis = {
        "MOVE:E": (1.0, 0.0), "MOVE:W": (-1.0, 0.0),
        "MOVE:N": (0.0, 1.0), "MOVE:S": (0.0, -1.0),
        "E": (1.0, 0.0), "W": (-1.0, 0.0), "N": (0.0, 1.0), "S": (0.0, -1.0),
    }
    vec = axis.get(loco) or axis.get(loco.replace("MOVE:", ""))
    mag = (dx * dx + dy * dy) ** 0.5
    if vec is None or mag < 1e-9:
        return {
            "label": "NO_TERRAIN_ASSISTED_CANDIDATE",
            "displacement_mag": mag,
            "locomotion": loco,
        }
    align = (dx * vec[0] + dy * vec[1]) / mag
    assisted = mag >= 0.02 and align < 0.5
    return {
        "label": "TERRAIN_ASSISTED_DISPLACEMENT" if assisted else "MOTOR_ALIGNED_DISPLACEMENT",
        "displacement_mag": mag,
        "alignment_with_loco": round(align, 6),
        "locomotion": loco,
        "pose_delta": {"dx": dx, "dy": dy},
    }


def _iter_trajectory_records(stories: list[TickStory]):
    for s in stories:
        pose = _pose_from_story(s) or {}
        geom = _peer_geom(s) or {}
        vis = any(c.get("kind") == "VISION_EXPOSURE" for c in s.external_context)
        yield {
            "tick": s.tick,
            "agent_id": s.cognitive_agent_id,
            "physical_body_id": s.physical_body_id,
            "position": {"x": pose.get("x"), "y": pose.get("y")},
            "velocity": {"vx": pose.get("vx"), "vy": pose.get("vy")},
            "selected_action": pose.get("action") or (s.decision or {}).get("selected_action_legacy"),
            "motor_contribution": (s.motor or {}).get("components"),
            "head_orientation": {
                "theta": pose.get("theta"),
                "head_world_heading": pose.get("head_world_heading"),
                "head_relative_angle": pose.get("head_relative_angle"),
            },
            "signal_state": _signal_state(s),
            "other_agent_distance": geom.get("toroidal_distance"),
            "other_agent_visible": vis,
            "season_geology_reference": "NOT_RECORDED_PER_TICK",
            "terrain_world_contribution": _terrain_assisted_candidate(s),
            "psc_selected": {
                "selection_path": (s.decision or {}).get("selection_path"),
                "selection_source": (s.decision or {}).get("selection_source"),
                "selected_candidate_id": (s.decision or {}).get("selected_candidate_id"),
            },
        }


def _legacy_scenario_selected_count(run_dir: Path, max_tick: int | None) -> int:
    path = run_dir / "scientific_events.jsonl"
    if not path.is_file():
        return 0
    n = 0
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (o.get("type") or o.get("kind")) != "SCENARIO_SELECTED":
                continue
            if max_tick is not None and int(o.get("tick", 0)) > int(max_tick):
                continue
            n += 1
    return n


def _loco_token(s: TickStory) -> str:
    return str(((s.motor or {}).get("components") or {}).get("locomotion") or "WAIT")


def _is_wait(loco: str) -> bool:
    return str(loco).upper() in ("WAIT", "NONE", "")


def _wrap_delta(a: float, b: float, size: float) -> float:
    d = b - a
    half = size / 2.0
    if d > half:
        d -= size
    elif d < -half:
        d += size
    return d


def _canonical_history(
    stories: list[TickStory],
    *,
    world_w: float | None = None,
    world_h: float | None = None,
) -> dict[str, Any]:
    """Bounded ingest summary for Analyzer UI — not a second copy of JSONL."""
    ticks: set[int] = set()
    agents: dict[str, dict[str, Any]] = {}
    sequences: dict[str, list[tuple[int, str]]] = {}
    last_xy: dict[str, tuple[float, float]] = {}
    last_tick: dict[str, int] = {}
    cells: dict[str, set[str]] = {}
    w = float(world_w) if world_w and world_w > 0 else None
    h = float(world_h) if world_h and world_h > 0 else None
    for s in stories:
        ticks.add(int(s.tick))
        ag = agents.setdefault(
            s.cognitive_agent_id,
            {
                "agent_id": s.cognitive_agent_id,
                "body_id": s.physical_body_id,
                "ticks_observed": 0,
                "wait_count": 0,
                "move_count": 0,
                "move_distribution": {},
                "pose_ticks": 0,
                "signal_emissions": 0,
                "signal_receptions": 0,
                "visual_exposure_ticks": 0,
                "distance_manhattan_wrap": 0.0,
                "path_length_euclidean": 0.0,
                "unique_cells": 0,
                "path_available": False,
            },
        )
        ag["ticks_observed"] += 1
        loco = _loco_token(s)
        sequences.setdefault(s.cognitive_agent_id, []).append((int(s.tick), loco))
        if _is_wait(loco):
            ag["wait_count"] += 1
        else:
            ag["move_count"] += 1
            dist = ag["move_distribution"]
            dist[loco] = int(dist.get(loco, 0)) + 1
        pose = _pose_from_story(s) or {}
        x, y = pose.get("x"), pose.get("y")
        if x is not None and y is not None:
            ag["pose_ticks"] += 1
            fx, fy = float(x), float(y)
            if w is not None and h is not None:
                cx = int(fx) % int(w) if w else int(fx)
                cy = int(fy) % int(h) if h else int(fy)
            else:
                cx, cy = int(fx), int(fy)
            cells.setdefault(s.cognitive_agent_id, set()).add(f"{cx},{cy}")
            prev = last_xy.get(s.cognitive_agent_id)
            pt = last_tick.get(s.cognitive_agent_id)
            tick = int(s.tick)
            if prev is not None and pt is not None and tick == pt + 1:
                if w is not None and h is not None:
                    dx = _wrap_delta(prev[0], fx, w)
                    dy = _wrap_delta(prev[1], fy, h)
                else:
                    dx, dy = fx - prev[0], fy - prev[1]
                ag["distance_manhattan_wrap"] += abs(dx) + abs(dy)
                ag["path_length_euclidean"] += (dx * dx + dy * dy) ** 0.5
                ag["path_available"] = True
            last_xy[s.cognitive_agent_id] = (fx, fy)
            last_tick[s.cognitive_agent_id] = tick
        sig = _signal_state(s)
        if sig.get("emitted"):
            ag["signal_emissions"] += 1
        if sig.get("received"):
            ag["signal_receptions"] += 1
        if any(c.get("kind") == "VISION_EXPOSURE" for c in s.external_context):
            ag["visual_exposure_ticks"] += 1
    for aid, ag in agents.items():
        metrics = compute_agent_action_metrics(sequences.get(aid) or [])
        ag["longest_wait_streak"] = metrics["longest_wait_streak"]
        ag["longest_move_streak"] = metrics["longest_move_streak"]
        ag["action_transitions"] = metrics["action_transitions"]
        ag["gap_ticks_missing"] = metrics["gap_ticks_missing"]
        ag["duplicates_ignored"] = metrics["duplicates_ignored"]
        ag["sequence_coverage"] = metrics["sequence_coverage"]
        ag["canonical_ticks"] = metrics["canonical_ticks"]
        ag["wait_count"] = int(metrics["wait_count"])
        ag["move_count"] = int(metrics["move_count"])
        ag["ticks_observed"] = int(metrics["canonical_ticks"])
        ag["decision_receipts"] = int(metrics["canonical_ticks"])
        ag["decision_receipts_unit"] = "per-agent DecisionReceipts (agent-ticks)"
        n_cells = len(cells.get(aid, set()))
        ag["unique_cells"] = n_cells
        if ag.get("pose_ticks") and not ag.get("path_available") and n_cells == 0:
            ag["distance_manhattan_wrap"] = None
            ag["path_length_euclidean"] = None
            ag["unique_cells"] = None
        else:
            ag["distance_manhattan_wrap"] = round(float(ag["distance_manhattan_wrap"]), 6)
            ag["path_length_euclidean"] = round(float(ag["path_length_euclidean"]), 6)
    tmin = min(ticks) if ticks else None
    tmax = max(ticks) if ticks else None
    return {
        "unique_simulation_ticks": len(ticks),
        "tick_min": tmin,
        "tick_max": tmax,
        "scientific_tick_range": [tmin, tmax],
        "tick_stories": len(stories),
        "world_size": [w, h] if w is not None and h is not None else None,
        "agents": agents,
    }


def _agent_summaries(stories: list[TickStory]) -> list[dict[str, Any]]:
    by: dict[str, list[TickStory]] = {}
    for s in stories:
        by.setdefault(s.cognitive_agent_id, []).append(s)
    out = []
    for agent, seq in sorted(by.items()):
        wait = 0
        motors = Counter()
        paths = Counter()
        vis = 0
        for s in seq:
            loco = ((s.motor or {}).get("components") or {}).get("locomotion")
            if loco is None or str(loco).upper() in ("WAIT", "NONE", ""):
                wait += 1
            motors[s.composite_motor_summary or "?"] += 1
            paths[str((s.decision or {}).get("selection_path") or "?")] += 1
            if any(c.get("kind") == "VISION_EXPOSURE" for c in s.external_context):
                vis += 1
        n = len(seq) or 1
        out.append({
            "agent": agent,
            "body": seq[0].physical_body_id if seq else None,
            "n_stories": len(seq),
            "wait_p": round(wait / n, 4),
            "visual_exposure_ticks": vis,
            "top_motor": motors.most_common(1)[0][0] if motors else None,
            "selection_paths": dict(paths),
        })
    return out


def _what_happened_summary(payload_bits: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    sm = payload_bits.get("sensorimotor_summary") or {}
    asym = payload_bits.get("visual_asymmetry") or {}
    recede = payload_bits.get("receding_while_watching") or []
    rev = payload_bits.get("motor_reversals") or []
    sm_rev = payload_bits.get("sensorimotor_trend_reversals") or []
    agents = (sm.get("agents") or {})
    lines.append("WHAT HAPPENED (evidence summary — not anthropomorphic narrative)")
    latest = payload_bits.get("analysis_cutoff_tick")
    lines.append(f"- Latest analyzed complete tick: {latest}")
    lines.append(f"- TickStories / complete O→D→M→C: {payload_bits.get('complete_odmc')}")
    for aid, st in sorted(agents.items()):
        lines.append(
            f"- {aid}: visual_steps={st.get('visual_steps')}, "
            f"closure_under_vision={st.get('closure_steps_under_vision')} "
            f"(focal_dominant={st.get('closure_focal_dominant')}, "
            f"source_dominant={st.get('closure_source_dominant')}), "
            f"mean_bearing_error_under_vision={st.get('mean_bearing_error_under_vision')}, "
            f"responses={st.get('response_under_vision')}"
        )
    pa = (asym.get("per_agent") or {})
    if pa:
        lines.append("- Visual exposure asymmetry (DERIVED geometric diagnostics):")
        for aid, v in sorted(pa.items()):
            lines.append(
                f"  {aid}: exposure_ticks={v.get('visual_exposure_ticks')}, "
                f"ticks_within_r3={v.get('ticks_within_vision_radius_3')}, "
                f"exposure/near={v.get('exposure_as_fraction_of_near')}, "
                f"mean_err={v.get('mean_bearing_error_during_exposure')}"
            )
        for e in asym.get("candidate_explanations") or []:
            lines.append(f"  candidate: {e}")
    g = sm.get("global") or {}
    lines.append(
        f"- Under visual exposure, after distance INCREASE: n={((g.get('after_distance_increase') or {}).get('n'))}, "
        f"next_response={((g.get('after_distance_increase') or {}).get('next_response'))}"
    )
    lines.append(
        f"- Under visual exposure, after distance DECREASE: n={((g.get('after_distance_decrease') or {}).get('n'))}, "
        f"next_response={((g.get('after_distance_decrease') or {}).get('next_response'))}"
    )
    lines.append(f"- MOTOR_REVERSAL events (cardinal opposite loco): {len(rev)}")
    lines.append(f"- SENSORIMOTOR_TREND_REVERSAL candidates: {len(sm_rev)} (causation NOT_ESTABLISHED)")
    lines.append(f"- RECEDING_WHILE_WATCHING episodes matched: {len(recede)}")
    if recede:
        r0 = recede[0]
        lines.append(
            f"  example: {r0.get('agent')} t{r0.get('start_tick')}–t{r0.get('end_tick')} "
            f"dist {r0.get('initial_distance')}→{r0.get('final_distance')} "
            f"reversed_at={r0.get('locomotion_reversed_at')}"
        )
    focus = (payload_bits.get("target_intervals") or {}).get("3250-3315")
    if focus:
        lines.append("- Focus region t3250–3315: see TARGET INTERVAL reconstruction (agents became close again).")
    lines.append(
        "- Unresolved: whether any specific exo/FIELD component caused a selection; "
        "recognition; intentional approach/withdrawal; learning."
    )
    return lines


def _progress(
    on_progress: Any | None,
    phase: str,
    n: int = 0,
    total: int = 0,
    *,
    status_text: str | None = None,
    operation: str | None = None,
    unit_label: str | None = None,
) -> None:
    if not on_progress:
        return
    try:
        on_progress(
            phase,
            int(n),
            int(total or 0),
            status_text=status_text,
            operation=operation,
            unit_label=unit_label,
        )
    except TypeError:
        on_progress(phase, int(n), int(total or 0))


def build_behavioral_reconstruction(
    run_dir: str | Path,
    *,
    max_tick: int | None = None,
    write_artifacts: bool = False,
    artifact_dir: str | Path | None = None,
    on_progress: Any | None = None,
    snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    run_dir = Path(run_dir)
    t0 = time.perf_counter()
    version = RunEvidence.detect_evidence_version(run_dir)
    if version != "SCIENTIFIC_V3":
        payload = {
            "section": SECTION_TITLE,
            "status": "NOT_RECORDED",
            "evidence_version": version,
            "run_id": None,
            "note": (
                "V2-only or pre-V3 run. Behavioral Reconstruction operates in degraded mode: "
                "O→D→M→C relationships are NOT_RECORDED. Use existing V2 analysis paths; "
                "do not interpret missing V3 as zero cognition."
            ),
            "tick_stories_count": 0,
            "complete_odmc": "NOT_RECORDED",
            "episode_counts": {},
            "report_text": None,
            "sensorimotor_report_text": None,
        }
        from .report import format_behavioral_reconstruction as fmt
        payload["report_text"] = fmt(payload)
        payload["sensorimotor_report_text"] = (
            "SENSORIMOTOR CONSEQUENCE ANALYSIS\n"
            "=================================\n\n"
            "status: NOT_RECORDED (no SCIENTIFIC_V3 spine)\n"
        )
        return payload

    ev = RunEvidence(run_dir, snapshot=snapshot)
    try:
        run_id = (ev.meta or {}).get("run_id") or run_dir.name.replace(".live-", "")
        if max_tick is None:
            if snapshot and snapshot.get("snapshot_terminal_tick") is not None:
                max_tick = int(snapshot["snapshot_terminal_tick"])
            else:
                max_tick = ev.spine_max_tick()
        _progress(on_progress, "RECONSTRUCTING", 0, max_tick or 0, status_text="Building tick stories", unit_label="ticks")

        graph = RelationshipGraph(run_id=run_id)
        stories = build_tick_stories(ev, graph, max_tick=max_tick, on_progress=on_progress)
    finally:
        ev.close()
    join_summary = apply_joins(stories, graph, run_dir=run_dir, max_tick=max_tick)
    _progress(on_progress, "EPISODES", len(stories), max_tick or 0, status_text="Extracting episodes", unit_label="stories")
    width, height = (join_summary.get("world_size") or [32.0, 32.0])

    steps = build_sensorimotor_steps(stories, width=float(width), height=float(height))
    sm_summary = summarize_steps(steps)
    motor_revs = detect_motor_reversals(stories)
    sm_revs = detect_sensorimotor_trend_reversals(steps)
    stories_by_key = {(s.cognitive_agent_id, s.tick): s for s in stories}
    recede = find_receding_while_watching(steps, stories_by_key)
    asym = explain_visual_asymmetry(stories, steps)
    longit = longitudinal_comparison(stories, steps, int(max_tick or 0))

    episodes = extract_episodes(stories)
    # attach motor / sensorimotor reversal episodes
    for mr in motor_revs:
        episodes.append(Episode(
            episode_type="MOTOR_REVERSAL",
            start_tick=mr["start_tick"],
            end_tick=mr["end_tick"],
            agent=mr["agent"],
            motor_summary={"from": mr.get("from_loco"), "to": mr.get("to_loco")},
            evidence_class="OBSERVED",
            confidence="RECORDED",
            meta=mr,
        ))
    for sr in sm_revs:
        episodes.append(Episode(
            episode_type="SENSORIMOTOR_TREND_REVERSAL",
            start_tick=sr["start_tick"],
            end_tick=sr["end_tick"],
            agent=sr["agent"],
            participants=[sr.get("peer")] if sr.get("peer") else [],
            evidence_class="DERIVED",
            confidence=sr.get("evidence_strength", "WEAK"),
            meta=sr,
            evidence_relationships=[{"rel": "DERIVED_ASSOCIATION", "note": "trend reversal candidate"},
                                    {"rel": "NOT_ESTABLISHED", "note": "intentional correction"}],
        ))
    counts = episode_counts(episodes)
    # BUILD_SUMMARIES: nested work units (stories) — do not leave one static count.
    summary_total = max(1, int(len(stories) or max_tick or 1))
    summary_done = 0

    def _sum_prog(done: int, *, op: str, text: str | None = None) -> None:
        nonlocal summary_done
        summary_done = max(summary_done, int(done))
        _progress(
            on_progress,
            "AGGREGATING",
            summary_done,
            summary_total,
            status_text=text or f"Building summaries · {op}",
            operation=op,
            unit_label="stories",
        )

    _sum_prog(0, op="select_interesting", text="Phase 6/8 · Building summaries")
    selected_eps = select_interesting_episodes(episodes, limit=18)
    interesting = select_interesting_stories(stories, limit=12)
    n_stories_local = len(stories)

    def _contrast_progress(done: int, total: int, substage: str) -> None:
        # Honest subprogress: items scanned / candidate comparisons — not heartbeat.
        _sum_prog(
            max(1, min(summary_total // 12, max(1, int(summary_total * (done / max(total, 1)) / 12)))),
            op="contrasts_and_selection",
            text=f"Building summaries · contrasts · {substage} · {done}/{total}",
        )
        if on_progress and hasattr(on_progress, "emit"):
            try:
                on_progress.emit(
                    "AGGREGATING",
                    n=done,
                    total=total,
                    status_text=f"contrasts_and_selection · {substage}",
                    operation="contrasts_and_selection",
                    unit_label="stories_scanned",
                )
            except Exception:
                pass

    _sum_prog(1, op="contrasts_and_selection", text="Building summaries · contrasts · scanning")
    contrasts = build_contrasts(stories, on_progress=_contrast_progress if n_stories_local else None)
    _sum_prog(max(1, summary_total // 12), op="contrasts_and_selection", text="Building summaries · contrasts complete")

    complete = sum(1 for s in stories if s.evidence_quality.get("odmc_complete"))
    hist = _canonical_history(stories, world_w=float(width), world_h=float(height))
    tmin, tmax = hist.get("tick_min"), hist.get("tick_max")
    n_obs = sum(1 for s in stories if s.observation_id)
    n_dec = sum(1 for s in stories if s.decision_id)
    n_mot = sum(1 for s in stories if s.motor_id)
    n_cons = sum(1 for s in stories if s.consequence_id)

    target_intervals: dict[str, Any] = {}
    for a, b in TARGET_INTERVALS:
        key = f"{a}-{b}"
        target_intervals[key] = reconstruct_interval(stories, steps, a, b)

    odmc_examples: list[TickStory] = []
    for item in interesting:
        s = stories_by_key.get((item["agent"], item["tick"]))
        if s:
            odmc_examples.append(s)
        if len(odmc_examples) >= 5:
            break

    visual_ep = next((e for e in selected_eps if e.episode_type == "VISUAL_EXPOSURE"), None)
    signal_ep = next((e for e in selected_eps if e.episode_type == "SIGNAL_EXPOSURE"), None)
    approach_ep = next((e for e in selected_eps if e.episode_type in ("APPROACH", "WITHDRAWAL")), None)

    open_questions = [
        "Which accessible observation components, if any, are causally necessary for specific selection outcomes? (ablation)",
        "Does bearing-error reduction after exposure exceed matched no-exposure baselines?",
        "When distance closes under vision, how often is focal movement dominant across the full run?",
        "Do SENSORIMOTOR_TREND_REVERSAL candidates exceed chance under reshuffled motor sequences?",
        "Is RECEDING_WHILE_WATCHING followed by geometry-improving motors more often than matched controls?",
    ]

    bits = {
        "analysis_cutoff_tick": max_tick,
        "complete_odmc": f"{complete} / {len(stories)}",
        "sensorimotor_summary": sm_summary,
        "visual_asymmetry": asym,
        "receding_while_watching": recede,
        "motor_reversals": motor_revs,
        "sensorimotor_trend_reversals": sm_revs,
        "target_intervals": target_intervals,
    }
    what = _what_happened_summary(bits)

    payload: dict[str, Any] = {
        "section": SECTION_TITLE,
        "status": "AVAILABLE",
        "evidence_version": "SCIENTIFIC_V3",
        "run_id": run_id,
        "analysis_cutoff_tick": max_tick,
        "tick_stories_count": len(stories),
        "complete_odmc_count": complete,
        "complete_odmc": f"{complete} / {len(stories)}",
        "unique_simulation_ticks": hist.get("unique_simulation_ticks") or 0,
        "scientific_tick_range": [tmin, tmax],
        "canonical_history": hist,
        "scientific_v3_core": {
            "section": "SCIENTIFIC_V3 CORE RECONSTRUCTION",
            "evidence_version": "SCIENTIFIC_V3",
            "status": "AVAILABLE",
            "decision_receipts": n_dec,
            "observation_receipts": n_obs,
            "motor_receipts": n_mot,
            "consequence_receipts": n_cons,
            "complete_odmc_count": complete,
            "complete_odmc_chains": f"{complete} / {len(stories)}",
            "incomplete_odmc_chains": max(0, len(stories) - complete),
            "ticks_expected": len(stories),
            "tick_range": [tmin, tmax],
            "chain_completeness_pct": round(100.0 * complete / len(stories), 1) if stories else 0.0,
        },
        "world_size": join_summary.get("world_size"),
        "join_summary": join_summary,
        "legacy_scenario_selected_count": _legacy_scenario_selected_count(run_dir, max_tick),
        "decision_receipts": len(stories),
        "agent_summaries": _agent_summaries(stories),
        "episode_counts": counts,
        "selected_episodes": [e.to_dict() for e in selected_eps],
        "interesting_ticks": interesting,
        "contrasts": contrasts,
        "open_questions": open_questions,
        "relationship_graph_summary": graph.summary(),
        "representative": {
            "visual_episode": visual_ep.to_dict() if visual_ep else None,
            "signal_episode": signal_ep.to_dict() if signal_ep else None,
            "geometry_episode": approach_ep.to_dict() if approach_ep else None,
        },
        "what_happened": what,
        "sensorimotor_summary": sm_summary,
        "sensorimotor_steps_count": len(steps),
        "motor_reversals_count": len(motor_revs),
        "sensorimotor_trend_reversals_count": len(sm_revs),
        "receding_while_watching": recede,
        "visual_asymmetry": asym,
        "longitudinal": longit,
        "target_intervals": {
            k: {
                "interval": v.get("interval"),
                "approach_history_200_pre": v.get("approach_history_200_pre"),
                "agent_tick_counts": {aid: len(rows) for aid, rows in (v.get("agents") or {}).items()},
                "sample_ticks": {
                    aid: rows[:12] for aid, rows in (v.get("agents") or {}).items()
                },
            }
            for k, v in target_intervals.items()
        },
        "focus_3250_3315": target_intervals.get("3250-3315"),
        "elapsed_s": None,
        "analyzer_version": "1.2.0",
    }

    report_payload = dict(payload)
    report_payload["selected_episodes"] = selected_eps
    report_payload["odmc_examples"] = odmc_examples
    report_payload["_stories_by_key"] = stories_by_key
    payload["report_text"] = format_behavioral_reconstruction(report_payload)
    payload["sensorimotor_report_text"] = format_sensorimotor_section(payload, steps_sample=steps[:40])
    # SMC / O′ historical-selection: aggregate from DecisionReceipts (Tier 0 evidence).
    sm_model = aggregate_sensorimotor_consequence_model(run_dir)
    payload["sensorimotor_consequence_model"] = sm_model
    payload["action_conditioned_model_report_text"] = format_action_conditioned_model_section(sm_model)
    hss_model = aggregate_historical_sensorimotor_selection(run_dir)
    payload["historical_sensorimotor_selection"] = hss_model
    payload["historical_sensorimotor_selection_report_text"] = format_historical_sensorimotor_selection_section(hss_model)
    sig_model = aggregate_signal_conditioned_selection(run_dir)
    payload["signal_conditioned_sensorimotor_selection"] = sig_model
    payload["signal_conditioned_report_text"] = format_signal_conditioned_selection(sig_model)
    emb_model = aggregate_full_embodied_predictive_model(run_dir)
    payload["full_embodied_predictive_model"] = emb_model
    payload["full_embodied_report_text"] = format_full_embodied_predictive_model(emb_model)
    fc_shadow = aggregate_full_composite_psc_shadow(run_dir)
    payload["full_composite_psc_shadow"] = fc_shadow
    payload["full_composite_psc_shadow_report_text"] = format_full_composite_psc_shadow(fc_shadow)
    fork_dev = aggregate_psc_motor_resolution_developmental(run_dir)
    payload["psc_motor_resolution_developmental"] = fork_dev
    payload["psc_motor_resolution_developmental_report_text"] = format_psc_motor_resolution_developmental(fork_dev)

    vis = analyze_beta31_vision(
        run_dir, stories, max_tick=max_tick,
        out_dir=Path(artifact_dir) if write_artifacts and artifact_dir else None,
    )
    # Model-aware: remove false 2D-world limitation for Acanthostega Beta 4.0.
    try:
        from .volumetric_physical_causal_reconstruction import _model_authority

        _ma = _model_authority(Path(run_dir))
        vs = ((vis.get("beta31_vision") or {}).get("vision_summary") or {})
        lims = list(vs.get("limitations") or [])
        if _ma.get("world_dimensionality") == "VOLUMETRIC_XYZ":
            lims = [
                x for x in lims
                if "WORLD remains 2D" not in str(x) and "no depth/z channel" not in str(x)
            ]
            lims.insert(0, "WORLD is volumetric (VW1 occupancy / XYZ); Beta 3.1 vision channels remain planar optical bins.")
            vs["limitations"] = lims
            vs["WORLD_REMAINS_2D"] = False
            vs["WORLD_VOLUMETRIC_XYZ"] = True
            if isinstance(vis.get("beta31_vision"), dict):
                vis["beta31_vision"]["vision_summary"] = vs
            # Refresh report text limitations if present
            rt = str(vis.get("beta31_vision_report_text") or "")
            if "WORLD remains 2D" in rt:
                vis["beta31_vision_report_text"] = rt.replace(
                    "WORLD remains 2D; no depth/z channel.",
                    "WORLD is volumetric (VW1/XYZ); optical c0/c1/c2 remain anonymous planar channels.",
                )
    except Exception:
        pass
    payload["beta31_vision"] = vis.get("beta31_vision")
    payload["beta31_vision_report_text"] = vis.get("beta31_vision_report_text")
    payload["beta31_vision_publication"] = vis.get("publication")

    from .metadata_authority import resolve_run_metadata
    from .psc_regime import reconstruct_psc_regime, format_psc_regime_section
    from .layered_coverage import build_layered_coverage
    from .report_consistency import validate_report_consistency
    from .development_fixture_text import DEVELOPMENT_FIXTURE_SECTION
    from .vision_analysis import apply_model_aware_vision_title

    meta_auth = resolve_run_metadata(Path(run_dir))
    payload["metadata_authority"] = meta_auth
    payload["identity"] = meta_auth.get("identity") or {}
    payload["evidence_files"] = meta_auth.get("evidence_files") or []
    psc = reconstruct_psc_regime(Path(run_dir), cutoff_tick=max_tick)
    payload["psc_regime"] = psc
    payload["psc_regime_report_text"] = format_psc_regime_section(psc)
    vis_text = apply_model_aware_vision_title(
        str(payload.get("beta31_vision_report_text") or ""),
        payload.get("identity") or {},
    )
    payload["beta31_vision_report_text"] = vis_text
    sig_n = 0
    for _aid, _row in (hist.get("agents") or {}).items():
        sig_n += int(_row.get("signal_emissions") or 0) + int(_row.get("signal_receptions") or 0)
    vis_seen = bool(((vis.get("beta31_vision") or {}).get("vision_summary") or {}).get("channels_seen"))
    layered = build_layered_coverage(
        complete_odmc=int(complete),
        expected_odmc=len(stories),
        unique_simulation_ticks=int(hist.get("unique_simulation_ticks") or 0),
        metadata=meta_auth,
        psc_regime=psc,
        vision_channels_seen=vis_seen,
        signal_receipts=sig_n,
        observer_timeline_samples=0,
        world_size_present=bool(hist.get("world_size") or (payload.get("identity") or {}).get("map_width")),
    )
    payload["layered_coverage"] = layered
    payload["development_fixture_section"] = DEVELOPMENT_FIXTURE_SECTION
    payload["report_consistency"] = validate_report_consistency(payload)
    payload["decision_receipts"] = n_dec
    payload["decision_receipts_unit"] = "global DecisionReceipts (all agents, agent-ticks)"


    vpc = build_volumetric_physical_causal_reconstruction(stories, run_dir=run_dir)
    payload["volumetric_physical_causal_reconstruction"] = vpc
    payload["volumetric_physical_causal_report_text"] = format_volumetric_physical_causal_section(vpc)
    odmc_n = int(payload.get("complete_odmc_count") or 0)
    stories_n = int(payload.get("tick_stories_count") or 0)
    payload["publication_gate"] = {
        "ANALYZER_VERSION": payload.get("analyzer_version") or "1.2.0",
        "SCIENTIFIC_V3_RECONSTRUCTION": "PASS" if payload.get("status") == "AVAILABLE" else "FAIL",
        "ODMC_COMPLETE": f"{odmc_n} / {stories_n}",
        **(vis.get("publication") or {}),
        "BOUNDED_MEMORY": "YES",
        "ANALYZER_ONLY_CHANGE": "YES",
    }
    # Phase 1: propagate reconstruction exposure into canonical_history agents.
    hist_agents = (payload.get("canonical_history") or {}).get("agents") or {}
    legacy_exp = ((vis.get("beta31_vision") or {}).get("vision_summary") or {}).get("legacy_body_visual_exposure") or {}
    for aid, n in legacy_exp.items():
        if aid in hist_agents:
            hist_agents[aid]["legacy_body_visual_exposure_ticks"] = n
            if not hist_agents[aid].get("visual_exposure_ticks"):
                hist_agents[aid]["visual_exposure_ticks"] = n

    _sum_prog(max(summary_done, summary_total // 6), op="canonical_history", text="Building summaries · canonical history")
    prediction_summary = summarize_traction_prediction(receipts_from_consequences(run_dir))
    payload["surface_traction_prediction_adaptation"] = prediction_summary
    prediction_text = ""
    if int(prediction_summary.get("exposure_episodes") or 0) > 0:
        prediction_text = format_traction_prediction_section(prediction_summary)
    payload["surface_traction_prediction_adaptation_report_text"] = prediction_text
    optical_summary = summarize_surface_optical(optical_receipts_from_consequences(run_dir))
    payload["physical_surface_optical_coating"] = optical_summary
    optical_text = ""
    if int(optical_summary.get("coating_observation_ticks") or 0) > 0:
        optical_text = format_surface_optical_section(optical_summary)
    payload["physical_surface_optical_coating_report_text"] = optical_text
    material_tx_summary = summarize_world_material(material_tx_receipts_from_consequences(run_dir))
    payload["world_material_transactions"] = material_tx_summary
    material_tx_text = ""
    if int(material_tx_summary.get("planned_count") or 0) > 0:
        material_tx_text = format_world_material_section(material_tx_summary)
    payload["world_material_transactions_report_text"] = material_tx_text
    try:
        from mechanistic_mind.physical_system.abstract_spectral_light_source_and_direct_transport import (
            build_abstract_spectral_light_causal_reconstruction,
            format_abstract_spectral_light_section,
        )

        o3_evidence: dict[str, Any] = {}
        for name in ("scientific_v3_meta.json", "scientific_meta.json", "identity_map.json", "snapshot.json"):
            pth = Path(run_dir) / name
            if not pth.is_file():
                continue
            try:
                raw = json.loads(pth.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(raw, dict):
                o3_evidence = raw
                break
        _sum_prog(max(summary_done, summary_total // 4), op="abstract_spectral_light", text="Building summaries · spectral light")
        o3_light = build_abstract_spectral_light_causal_reconstruction(
            o3_evidence, on_progress=on_progress
        )
        payload["abstract_spectral_light_causal_reconstruction"] = o3_light
        payload["abstract_spectral_light_causal_report_text"] = format_abstract_spectral_light_section(
            o3_light
        )
        _sum_prog(max(summary_done, summary_total // 3), op="abstract_spectral_light_done")
    except Exception:
        payload["abstract_spectral_light_causal_reconstruction"] = {
            "organism_saw_light": False,
            "organism_reception": False,
            "status": "UNAVAILABLE",
        }
    try:
        from mechanistic_mind.physical_system.object_body_held_optical_surfaces import (
            build_object_body_held_optical_causal_reconstruction,
            format_object_body_held_optical_section,
        )

        o3a_evidence: dict[str, Any] = {}
        for name in ("scientific_v3_meta.json", "scientific_meta.json", "identity_map.json", "snapshot.json"):
            pth = Path(run_dir) / name
            if not pth.is_file():
                continue
            try:
                raw = json.loads(pth.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(raw, dict):
                o3a_evidence = raw
                break
        o3a = build_object_body_held_optical_causal_reconstruction(o3a_evidence, on_progress=on_progress)
        payload["object_body_held_optical_causal_reconstruction"] = o3a
        payload["object_body_held_optical_causal_report_text"] = format_object_body_held_optical_section(o3a)
    except Exception:
        payload["object_body_held_optical_causal_reconstruction"] = {
            "organism_saw_light": False,
            "organism_reception": False,
            "status": "UNAVAILABLE",
        }
    try:
        from mechanistic_mind.physical_system.organism_physical_optical_reception import (
            build_o4_analyzer_reconstruction,
            format_o4_section,
        )

        o4_evidence: dict[str, Any] = {}
        for name in ("scientific_v3_meta.json", "scientific_meta.json", "identity_map.json", "snapshot.json"):
            pth = Path(run_dir) / name
            if not pth.is_file():
                continue
            try:
                raw = json.loads(pth.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(raw, dict):
                o4_evidence = raw.get("organism_physical_optical_reception") or raw
                break
        _sum_prog(max(summary_done, summary_total // 2), op="o4_optical_reception", text="Building summaries · O4 reception")
        o4 = build_o4_analyzer_reconstruction(o4_evidence, on_progress=on_progress)
        _sum_prog(max(summary_done, (summary_total * 2) // 3), op="o4_optical_reception_done")
        payload["organism_physical_optical_causal_reconstruction"] = o4
        payload["organism_physical_optical_causal_report_text"] = format_o4_section(o4)
    except Exception:
        payload["organism_physical_optical_causal_reconstruction"] = {
            "physical_signal_reached_receptor": False,
            "conscious_seeing_claimed": False,
            "status": "UNAVAILABLE",
        }

    try:
        from mechanistic_mind.physical_system.sensory_modality_temporal_alignment import (
            build_o5_analyzer_reconstruction,
            derive_envelope_from_saved_evidence,
            format_o5_section,
        )

        o5_evidence: dict[str, Any] = {}
        for name in ("scientific_v3_meta.json", "scientific_meta.json", "identity_map.json", "snapshot.json"):
            pth = Path(run_dir) / name
            if not pth.is_file():
                continue
            try:
                raw = json.loads(pth.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(raw, dict):
                o5_evidence = (
                    raw.get("sensory_modality_temporal_alignment")
                    or raw.get("sensory_modality_temporal_alignment_state")
                    or raw
                )
                break
        derived = derive_envelope_from_saved_evidence(o5_evidence if isinstance(o5_evidence, dict) else {})
        _sum_prog(max(summary_done, (summary_total * 3) // 4), op="o5_temporal_alignment", text="Building summaries · O5 timing")
        o5 = build_o5_analyzer_reconstruction(derived, on_progress=on_progress)
        o5["legacy_policy"] = derived.get("legacy_policy")
        o5["same_observation_means_same_physical_time"] = False
        payload["sensory_modality_temporal_alignment_reconstruction"] = o5
        payload["sensory_modality_temporal_alignment_report_text"] = format_o5_section(o5)
    except Exception:
        payload["sensory_modality_temporal_alignment_reconstruction"] = {
            "same_observation_means_same_physical_time": False,
            "status": "UNAVAILABLE",
        }

    try:
        from mechanistic_mind.physical_system.researcher_physical_optical_audit_view import (
            build_o6_analyzer_summary,
            derive_from_saved_evidence,
            format_o6_section,
        )

        o6_evidence: dict[str, Any] = {}
        for name in ("scientific_v3_meta.json", "scientific_meta.json", "identity_map.json", "snapshot.json"):
            pth = Path(run_dir) / name
            if not pth.is_file():
                continue
            try:
                raw = json.loads(pth.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(raw, dict):
                o6_evidence = raw.get("researcher_physical_optical_audit_view") or raw
                break
        derived = derive_from_saved_evidence(o6_evidence if isinstance(o6_evidence, dict) else {})
        o6 = build_o6_analyzer_summary(derived, on_progress=on_progress)
        payload["researcher_physical_optical_audit_reconstruction"] = o6
        payload["researcher_physical_optical_audit_report_text"] = format_o6_section(o6)
    except Exception:
        payload["researcher_physical_optical_audit_reconstruction"] = {
            "uses_rendered_pixels": False,
            "status": "UNAVAILABLE",
        }
    spatial_summary = summarize_spatial_contents(spatial_receipts_from_consequences(run_dir))
    payload["multi_content_spatial_index"] = spatial_summary
    spatial_text = ""
    if int(spatial_summary.get("event_count") or 0) > 0:
        spatial_text = format_spatial_contents_section(spatial_summary)
    payload["multi_content_spatial_index_report_text"] = spatial_text
    column_summary = summarize_procedural_surface_columns(column_receipts_from_consequences(run_dir))
    payload["procedural_surface_columns"] = column_summary
    column_text = ""
    if int(column_summary.get("event_count") or 0) > 0:
        column_text = format_procedural_surface_columns_section(column_summary)
    payload["procedural_surface_columns_report_text"] = column_text
    transfer_summary = summarize_surface_column_transfer(transfer_receipts_from_consequences(run_dir))
    payload["conservative_surface_column_transfer"] = transfer_summary
    transfer_text = ""
    if int(transfer_summary.get("event_count") or 0) > 0:
        transfer_text = format_surface_column_transfer_section(transfer_summary)
    payload["conservative_surface_column_transfer_report_text"] = transfer_text
    local_signal_summary = summarize_local_physical_signal(local_signal_receipts_from_consequences(run_dir))
    payload["local_physical_signal_transport"] = local_signal_summary
    local_signal_text = ""
    if int(local_signal_summary.get("event_count") or 0) > 0:
        local_signal_text = format_local_physical_signal_section(local_signal_summary)
    payload["local_physical_signal_transport_report_text"] = local_signal_text
    contact_summary = summarize_physical_contact_acoustics(*contact_receipts_from_consequences(run_dir))
    payload["physical_contact_acoustic_events"] = contact_summary
    contact_text = ""
    if int(contact_summary.get("contact_impulses_measured") or 0) + int(contact_summary.get("emissions_created") or 0) > 0:
        contact_text = format_physical_contact_acoustic_section(contact_summary)
    payload["physical_contact_acoustic_events_report_text"] = contact_text
    free_object_summary = summarize_free_object_kinematics(free_object_receipts_from_consequences(run_dir))
    payload["free_resource_object_kinematics"] = free_object_summary
    free_object_text = ""
    if int(free_object_summary.get("event_count") or 0) > 0:
        free_object_text = format_free_object_kinematics_section(free_object_summary)
    payload["free_resource_object_kinematics_report_text"] = free_object_text
    boc_summary = summarize_body_object_contact(body_object_receipts_from_consequences(run_dir))
    payload["body_resource_object_contact"] = boc_summary
    boc_text = ""
    if int(boc_summary.get("event_count") or 0) > 0:
        boc_text = format_body_object_contact_section(boc_summary)
    payload["body_resource_object_contact_report_text"] = boc_text
    boi_summary = summarize_body_object_impulse(body_object_impulse_receipts_from_consequences(run_dir))
    payload["body_resource_object_contact_response"] = boi_summary
    boi_text = ""
    if int(boi_summary.get("event_count") or 0) > 0:
        boi_text = format_body_object_impulse_section(boi_summary)
    payload["body_resource_object_contact_response_report_text"] = boi_text
    oia_summary = summarize_body_object_impact_acoustics(
        *body_object_impact_acoustic_receipts_from_consequences(run_dir)
    )
    payload["body_object_impact_acoustics"] = oia_summary
    oia_text = ""
    if int(oia_summary.get("event_count") or 0) > 0:
        oia_text = format_body_object_impact_acoustics_section(oia_summary)
    payload["body_object_impact_acoustics_report_text"] = oia_text
    ooc_summary = summarize_resource_object_pair_contact(
        resource_object_pair_contact_receipts_from_consequences(run_dir)
    )
    payload["resource_object_pair_contact"] = ooc_summary
    ooc_text = ""
    if int(ooc_summary.get("event_count") or 0) > 0:
        ooc_text = format_resource_object_pair_contact_section(ooc_summary)
    payload["resource_object_pair_contact_report_text"] = ooc_text
    ooi_summary = summarize_resource_object_pair_impulse(
        resource_object_pair_impulse_receipts_from_consequences(run_dir)
    )
    payload["resource_object_pair_contact_response"] = ooi_summary
    ooi_text = ""
    if int(ooi_summary.get("event_count") or 0) > 0:
        ooi_text = format_resource_object_pair_impulse_section(ooi_summary)
    payload["resource_object_pair_contact_response_report_text"] = ooi_text
    ooia_summary = summarize_resource_object_pair_impact_acoustics(
        *resource_object_pair_impact_acoustic_receipts_from_consequences(run_dir)
    )
    payload["resource_object_pair_impact_acoustics"] = ooia_summary
    ooia_text = ""
    if int(ooia_summary.get("event_count") or 0) > 0:
        ooia_text = format_resource_object_pair_impact_acoustics_section(ooia_summary)
    payload["resource_object_pair_impact_acoustics_report_text"] = ooia_text
    hfc_summary = summarize_held_foreign_body_contact(
        held_foreign_body_receipts_from_consequences(run_dir)
    )
    payload["held_resource_object_foreign_body_contact"] = hfc_summary
    hfc_text = ""
    if int(hfc_summary.get("event_count") or 0) > 0:
        hfc_text = format_held_foreign_body_contact_section(hfc_summary)
    payload["held_resource_object_foreign_body_contact_report_text"] = hfc_text
    hotc_summary = summarize_held_resource_object_terrain_contact(
        held_resource_object_terrain_contact_receipts_from_consequences(run_dir)
    )
    payload["held_resource_object_terrain_contact"] = hotc_summary
    hotc_text = ""
    if int(hotc_summary.get("event_count") or 0) > 0:
        hotc_text = format_held_resource_object_terrain_contact_section(hotc_summary)
    payload["held_resource_object_terrain_contact_report_text"] = hotc_text
    hotmt_summary = summarize_held_resource_object_terrain_mechanical_transmission(
        held_resource_object_terrain_mechanical_transmission_receipts_from_consequences(run_dir)
    )
    payload["held_resource_object_terrain_mechanical_transmission"] = hotmt_summary
    hotmt_text = ""
    if int(hotmt_summary.get("event_count") or 0) > 0:
        hotmt_text = format_held_resource_object_terrain_mechanical_transmission_section(
            hotmt_summary
        )
    payload["held_resource_object_terrain_mechanical_transmission_report_text"] = hotmt_text
    hmsi_summary = summarize_held_mediated_surface_exertion_integration(
        held_mediated_surface_exertion_integration_receipts_from_consequences(run_dir)
    )
    payload["held_mediated_surface_exertion_integration"] = hmsi_summary
    hmsi_text = ""
    if int(hmsi_summary.get("event_count") or 0) > 0:
        hmsi_text = format_held_mediated_surface_exertion_integration_section(hmsi_summary)
    payload["held_mediated_surface_exertion_integration_report_text"] = hmsi_text
    dtip_summary = summarize_detached_terrain_material_initial_placement(
        detached_terrain_material_initial_placement_receipts_from_consequences(run_dir)
    )
    payload["detached_terrain_material_initial_placement"] = dtip_summary
    dtip_text = ""
    if dtip_summary.get("receipt_count"):
        dtip_text = format_detached_terrain_material_initial_placement_section(dtip_summary)
    payload["detached_terrain_material_initial_placement_report_text"] = dtip_text
    bnlt_rep_summary = summarize_bnlt_move_breakaway_locomotion_repair(
        bnlt_move_breakaway_locomotion_repair_receipts_from_consequences(run_dir)
    )
    payload["bnlt_move_breakaway_locomotion_repair"] = bnlt_rep_summary
    bnlt_rep_text = ""
    if bnlt_rep_summary.get("receipt_count"):
        bnlt_rep_text = format_bnlt_move_breakaway_locomotion_repair_section(bnlt_rep_summary)
    payload["bnlt_move_breakaway_locomotion_repair_report_text"] = bnlt_rep_text
    rcss_summary = summarize_repeated_conservative_surface_column_separation(
        repeated_conservative_surface_column_separation_receipts_from_consequences(run_dir)
    )
    payload["repeated_conservative_surface_column_separation"] = rcss_summary
    rcss_text = ""
    if rcss_summary.get("receipt_count"):
        rcss_text = format_repeated_conservative_surface_column_separation_section(rcss_summary)
    payload["repeated_conservative_surface_column_separation_report_text"] = rcss_text
    crowded_summary = summarize_crowded_placement_retry(
        crowded_placement_retry_receipts_from_consequences(run_dir)
    )
    payload["event_driven_crowded_placement_retry_contract"] = crowded_summary
    crowded_text = ""
    if crowded_summary.get("receipt_count"):
        crowded_text = format_crowded_placement_retry_section(crowded_summary)
    payload["event_driven_crowded_placement_retry_contract_report_text"] = crowded_text
    size_geo_summary = summarize_detached_material_size_geometry(
        detached_material_size_geometry_receipts_from_consequences(run_dir)
    )
    payload["detached_material_amount_scaled_collision_radius"] = size_geo_summary
    size_geo_text = ""
    if size_geo_summary.get("receipt_count"):
        size_geo_text = format_detached_material_size_geometry_section(size_geo_summary)
    payload["detached_material_amount_scaled_collision_radius_report_text"] = size_geo_text
    held_combine_summary = summarize_held_combine_radius_resize(
        held_combine_radius_resize_receipts_from_consequences(run_dir)
    )
    payload["held_combine_radius_resize_transaction"] = held_combine_summary
    held_combine_text = ""
    if held_combine_summary.get("receipt_count"):
        held_combine_text = format_held_combine_radius_resize_section(held_combine_summary)
    payload["held_combine_radius_resize_transaction_report_text"] = held_combine_text
    held_deposition_summary = summarize_held_deposition_radius_shrink(
        held_deposition_radius_shrink_receipts_from_consequences(run_dir)
    )
    payload["held_deposition_radius_shrink_transaction"] = held_deposition_summary
    held_deposition_text = ""
    if held_deposition_summary.get("receipt_count"):
        held_deposition_text = format_held_deposition_radius_shrink_section(held_deposition_summary)
    payload["held_deposition_radius_shrink_transaction_report_text"] = held_deposition_text
    free_space_summary = summarize_free_space_state_and_pe_authority(
        free_space_state_and_pe_authority_receipts_from_consequences(run_dir)
    )
    payload["free_space_state_and_pe_authority_contract"] = free_space_summary
    free_space_text = ""
    if free_space_summary.get("receipt_count"):
        free_space_text = format_free_space_state_and_pe_authority_section(free_space_summary)
    payload["free_space_state_and_pe_authority_contract_report_text"] = free_space_text
    landing_summary = summarize_vertical_terrain_landing_contact_response(
        vertical_terrain_landing_receipts_from_consequences(run_dir)
    )
    payload["vertical_terrain_landing_contact_response"] = landing_summary
    landing_text = ""
    if landing_summary.get("receipt_count"):
        landing_text = format_vertical_terrain_landing_contact_response_section(landing_summary)
    payload["vertical_terrain_landing_contact_response_report_text"] = landing_text
    via_summary = summarize_vertical_impact_acoustic_emission(
        vertical_impact_acoustic_receipts_from_consequences(run_dir)
    )
    payload["vertical_impact_acoustic_emission"] = via_summary
    via_text = ""
    if via_summary.get("receipt_count"):
        via_text = format_vertical_impact_acoustic_emission_section(via_summary)
    payload["vertical_impact_acoustic_emission_report_text"] = via_text
    apas_records, apas_meta = acoustic_stream_records_from_consequences(run_dir)
    apas_summary = summarize_authoritative_physical_acoustic_stream(
        apas_records, meta=apas_meta
    )
    payload["authoritative_physical_acoustic_stream"] = apas_summary
    apas_text = ""
    if apas_summary.get("record_count"):
        apas_text = format_authoritative_physical_acoustic_stream_section(apas_summary)
    payload["authoritative_physical_acoustic_stream_report_text"] = apas_text
    oap_samples, oap_meta = probe_samples_from_consequences(run_dir)
    oap_summary = summarize_observer_acoustic_probe(oap_samples, meta=oap_meta)
    payload["observer_acoustic_probe"] = oap_summary
    oap_text = ""
    if oap_summary.get("sample_count"):
        oap_text = format_observer_acoustic_probe_section(oap_summary)
    payload["observer_acoustic_probe_report_text"] = oap_text
    cal_records = calibration_records_from_consequences(run_dir)
    cal_summary = summarize_acoustic_calibration(cal_records)
    payload["physical_frequency_amplitude_calibration"] = cal_summary
    cal_text = format_acoustic_calibration_section(cal_summary)
    payload["physical_frequency_amplitude_calibration_report_text"] = cal_text
    c1_summary = summarize_canonical_sonification(oap_samples)
    payload["canonical_physical_field_sonification"] = c1_summary
    c1_text = ""
    if c1_summary.get("available"):
        c1_text = format_canonical_sonification_section(c1_summary)
    payload["canonical_physical_field_sonification_report_text"] = c1_text
    soab_receipts = auditory_boundary_receipts_from_consequences(run_dir)
    # Prefer full receipt bodies from world state if present in package tip
    soab_summary = summarize_selected_organism_auditory(soab_receipts)
    payload["selected_organism_auditory_view"] = soab_summary
    soab_text = ""
    if soab_summary.get("available") or soab_summary.get("status"):
        soab_text = format_selected_organism_auditory_section(soab_summary)
    payload["selected_organism_auditory_view_report_text"] = soab_text
    sav2_summary = summarize_selected_organism_auditory_sonification(soab_receipts)
    payload["selected_organism_auditory_sonification"] = sav2_summary
    sav2_text = ""
    if sav2_summary.get("available") or sav2_summary.get("status"):
        sav2_text = format_selected_organism_auditory_sonification_section(sav2_summary)
    payload["selected_organism_auditory_sonification_report_text"] = sav2_text
    oatt_traces = transformation_traces_from_consequences(run_dir)
    oatt_summary = summarize_organism_auditory_transformation_traces(oatt_traces)
    payload["organism_auditory_transformation_trace"] = oatt_summary
    oatt_text = ""
    if oatt_summary.get("available") or oatt_summary.get("status"):
        oatt_text = format_organism_auditory_transformation_trace_section(oatt_summary)
    payload["organism_auditory_transformation_trace_report_text"] = oatt_text
    sav3_summary = summarize_sav3_comparison(oatt_traces)
    payload["selected_organism_physical_field_comparison"] = sav3_summary
    sav3_text = ""
    if sav3_summary.get("available") or sav3_summary.get("status"):
        sav3_text = format_sav3_comparison_section(sav3_summary)
    payload["selected_organism_physical_field_comparison_report_text"] = sav3_text
    sav4a_summary = summarize_sav4a_offline_reconstruction(run_dir)
    payload["selected_organism_auditory_offline_reconstruction"] = sav4a_summary
    sav4a_text = ""
    if sav4a_summary.get("available") or sav4a_summary.get("status"):
        sav4a_text = format_sav4a_section(sav4a_summary)
    payload["selected_organism_auditory_offline_reconstruction_report_text"] = sav4a_text
    resli_summary = summarize_release_and_excavation_support_loss(
        release_excavation_support_loss_receipts_from_consequences(run_dir)
    )
    payload["release_and_excavation_support_loss_integration"] = resli_summary
    resli_text = ""
    if resli_summary.get("receipt_count"):
        resli_text = format_release_and_excavation_support_loss_section(resli_summary)
    payload["release_and_excavation_support_loss_integration_report_text"] = resli_text
    # Display-aware story (no pixel-inferred elevation; progress bar remains text-only).
    elev_story = summarize_elevation_free_space_story(
        vertical_display=None,  # saved runs may lack dense elev; receipts still reconstruct narrative
        release_receipts=[
            r for r in (resli_summary.get("timeline") or resli_summary.get("receipts") or [])
            if str((r or {}).get("event_class") or "") == "RELEASE_ENTRY"
        ],
        support_loss_receipts=[
            r for r in (resli_summary.get("timeline") or resli_summary.get("receipts") or [])
            if str((r or {}).get("event_class") or "") == "SUPPORT_LOST"
        ],
        landing_receipts=list(landing_summary.get("timeline") or landing_summary.get("receipts") or []),
        acoustic_receipts=list(via_summary.get("timeline") or via_summary.get("receipts") or []),
    )
    payload["elevation_excavation_free_space_story"] = elev_story
    payload["elevation_excavation_free_space_story_report_text"] = format_elevation_free_space_section(elev_story)
    hti_summary = summarize_held_translational_impulse(
        held_translational_impulse_receipts_from_consequences(run_dir)
    )
    payload["held_resource_object_translational_impulse_mediation"] = hti_summary
    hti_text = ""
    if int(hti_summary.get("contact_measurements") or 0) > 0:
        hti_text = format_held_translational_impulse_section(hti_summary)
    payload["held_resource_object_translational_impulse_mediation_report_text"] = hti_text
    ehl_summary = summarize_effector_work_held_load(
        effector_work_held_load_receipts_from_consequences(run_dir)
    )
    payload["effector_work_and_held_load_inertia_accounting"] = ehl_summary
    ehl_text = ""
    if int(ehl_summary.get("event_count") or 0) > 0:
        ehl_text = format_effector_work_held_load_section(ehl_summary)
    payload["effector_work_and_held_load_inertia_accounting_report_text"] = ehl_text
    fgg_summary = summarize_flat_ground_gravity(
        flat_ground_gravity_receipts_from_consequences(run_dir)
    )
    payload["flat_ground_gravity"] = fgg_summary
    fogf_summary = summarize_free_object_ground_friction(
        free_object_ground_friction_receipts_from_consequences(run_dir)
    )
    payload["free_object_ground_friction"] = fogf_summary
    fgg_text = ""
    if int(fgg_summary.get("event_count") or 0) > 0 or int(fgg_summary.get("landing_count") or 0) > 0:
        fgg_text = format_flat_ground_gravity_section(fgg_summary)
    payload["flat_ground_gravity_report_text"] = fgg_text

    ses_summary = summarize_surface_elevation_support(
        surface_elevation_support_receipts_from_consequences(run_dir)
    )
    payload["surface_elevation_support"] = ses_summary
    ses_text = ""
    if ses_summary.get("n_receipts"):
        ses_text = format_surface_elevation_support_section(ses_summary)
    payload["surface_elevation_support_report_text"] = ses_text
    fogf_text = ""
    if fogf_summary.get("n_receipts"):
        fogf_text = format_free_object_ground_friction_section(fogf_summary)
    payload["free_object_ground_friction_report_text"] = fogf_text
    bnlt_summary = summarize_body_normal_load_traction(
        body_normal_load_traction_receipts_from_consequences(run_dir)
    )
    payload["body_normal_load_traction"] = bnlt_summary
    bnlt_text = ""
    if bnlt_summary.get("n_receipts"):
        bnlt_text = format_body_normal_load_traction_section(bnlt_summary)
    payload["body_normal_load_traction_report_text"] = bnlt_text
    csg_summary = summarize_continuous_surface_geometry(
        continuous_surface_geometry_receipts_from_consequences(run_dir)
    )
    payload["continuous_surface_geometry"] = csg_summary
    csg_text = ""
    if csg_summary.get("n_receipts"):
        csg_text = format_continuous_surface_geometry_section(csg_summary)
    payload["continuous_surface_geometry_report_text"] = csg_text
    bst_summary = summarize_body_static_traction(
        body_static_traction_receipts_from_consequences(run_dir)
    )
    payload["body_static_traction"] = bst_summary
    bst_text = ""
    if bst_summary.get("n_receipts"):
        bst_text = format_body_static_traction_section(bst_summary)
    payload["body_static_traction_report_text"] = bst_text
    fost_summary = summarize_free_resource_object_static_traction(
        free_resource_object_static_traction_receipts_from_consequences(run_dir)
    )
    payload["free_resource_object_static_traction"] = fost_summary
    fost_text = ""
    if fost_summary.get("n_receipts"):
        fost_text = format_free_resource_object_static_traction_section(fost_summary)
    payload["free_resource_object_static_traction_report_text"] = fost_text
    rasp_summary = summarize_radius_aware_support(
        radius_aware_support_receipts_from_consequences(run_dir)
    )
    payload["radius_aware_support"] = rasp_summary
    rasp_text = ""
    if rasp_summary.get("n_receipts"):
        rasp_text = format_radius_aware_support_section(rasp_summary)
    payload["radius_aware_support_report_text"] = rasp_text
    sdc_summary = summarize_ses_decomposition_contract_run(run_dir)
    payload["ses_decomposition_contract"] = sdc_summary
    sdc_text = ""
    if sdc_summary.get("n_receipts"):
        sdc_text = format_ses_decomposition_contract_section(sdc_summary)
    payload["ses_decomposition_contract_report_text"] = sdc_text
    srtc_summary = summarize_ses_runtime_transition_classifier_run(run_dir)
    payload["ses_runtime_transition_classifier"] = srtc_summary
    srtc_text = ""
    if srtc_summary.get("n_receipts"):
        srtc_text = format_ses_runtime_transition_classifier_section(srtc_summary)
    payload["ses_runtime_transition_classifier_report_text"] = srtc_text
    rafs_summary = summarize_radius_aware_face_sweep_run(run_dir)
    payload["radius_aware_face_sweep"] = rafs_summary
    rafs_text = ""
    if rafs_summary.get("attempts_evaluated"):
        rafs_text = format_radius_aware_face_sweep_section(rafs_summary)
    payload["radius_aware_face_sweep_report_text"] = rafs_text
    dnls_summary = summarize_diagnostic_normal_load_shadow_run(run_dir)
    payload["diagnostic_normal_load_shadow"] = dnls_summary
    dnls_text = ""
    if dnls_summary.get("queries"):
        dnls_text = format_diagnostic_normal_load_shadow_section(dnls_summary)
    payload["diagnostic_normal_load_shadow_report_text"] = dnls_text
    cgpe_summary = summarize_continuous_gravitational_pe_diagnostic_shadow_run(run_dir)
    payload["continuous_gravitational_pe_diagnostic_shadow"] = cgpe_summary
    cgpe_text = ""
    if cgpe_summary.get("queries"):
        cgpe_text = format_continuous_gravitational_pe_diagnostic_shadow_section(cgpe_summary)
    payload["continuous_gravitational_pe_diagnostic_shadow_report_text"] = cgpe_text
    payload["report_text"] = (
        (payload.get("report_text") or "")
        + "\n\n" + payload["action_conditioned_model_report_text"]
        + "\n\n" + payload["historical_sensorimotor_selection_report_text"]
        + "\n\n" + (payload.get("signal_conditioned_report_text") or "")
        + "\n\n" + (payload.get("full_embodied_report_text") or "")
        + "\n\n" + (payload.get("beta31_vision_report_text") or "")
        + (("\n\n" + (payload.get("volumetric_physical_causal_report_text") or "")) if payload.get("volumetric_physical_causal_report_text") else "")
        + (("\n\n" + prediction_text) if prediction_text else "")
        + (("\n\n" + optical_text) if optical_text else "")
        + (("\n\n" + material_tx_text) if material_tx_text else "")
        + (("\n\n" + spatial_text) if spatial_text else "")
        + (("\n\n" + column_text) if column_text else "")
        + (("\n\n" + transfer_text) if transfer_text else "")
        + (("\n\n" + local_signal_text) if local_signal_text else "")
        + (("\n\n" + contact_text) if contact_text else "")
        + (("\n\n" + free_object_text) if free_object_text else "")
        + (("\n\n" + boc_text) if boc_text else "")
        + (("\n\n" + boi_text) if boi_text else "")
        + (("\n\n" + oia_text) if oia_text else "")
        + (("\n\n" + ooc_text) if ooc_text else "")
        + (("\n\n" + ooi_text) if ooi_text else "")
        + (("\n\n" + ooia_text) if ooia_text else "")
        + (("\n\n" + hfc_text) if hfc_text else "")
        + (("\n\n" + hotc_text) if hotc_text else "")
        + (("\n\n" + hti_text) if hti_text else "")
        + (("\n\n" + ehl_text) if ehl_text else "")
        + (("\n\n" + fgg_text) if fgg_text else "")
        + (("\n\n" + ses_text) if ses_text else "")
        + (("\n\n" + fogf_text) if fogf_text else "")
        + (("\n\n" + bnlt_text) if bnlt_text else "")
        + (("\n\n" + csg_text) if csg_text else "")
        + (("\n\n" + bst_text) if bst_text else "")
        + (("\n\n" + fost_text) if fost_text else "")
        + (("\n\n" + rasp_text) if rasp_text else "")
        + (("\n\n" + sdc_text) if sdc_text else "")
        + (("\n\n" + srtc_text) if srtc_text else "")
        + (("\n\n" + rafs_text) if rafs_text else "")
        + (("\n\n" + dnls_text) if dnls_text else "")
    )
    from .report_consistency import validate_report_consistency as _validate_report
    from .truthful_markdown import format_truthful_markdown
    from .export_bundle import finalize_markdown_counts

    payload["report_consistency"] = _validate_report(payload)
    payload["elapsed_s"] = round(time.perf_counter() - t0, 4)
    payload["elapsed_source"] = "analyzer_pipeline"
    payload["truthful_markdown"] = finalize_markdown_counts(format_truthful_markdown(payload))

    if write_artifacts:
        _sum_prog(summary_total, op="summaries_complete", text="Building summaries · complete")
        if on_progress:
            on_progress("WRITING", len(stories), max_tick or 0)
        out = Path(artifact_dir) if artifact_dir else run_dir
        write_behavioral_artifacts(
            out, payload, graph=graph, stories=stories, episodes=episodes, steps=steps,
            motor_revs=motor_revs, sm_revs=sm_revs,
        )

    return payload


def write_behavioral_artifacts(
    out_dir: Path,
    payload: dict[str, Any],
    *,
    graph: RelationshipGraph | None = None,
    stories: list[TickStory] | None = None,
    episodes: list[Episode] | None = None,
    steps: list | None = None,
    motor_revs: list | None = None,
    sm_revs: list | None = None,
) -> dict[str, str]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}

    summary = {k: v for k, v in payload.items() if k not in ("report_text", "sensorimotor_report_text", "focus_3250_3315")}
    # keep a compact focus pointer
    focus = payload.get("focus_3250_3315") or {}
    summary["focus_3250_3315_compact"] = {
        "interval": focus.get("interval"),
        "approach_history_200_pre": focus.get("approach_history_200_pre"),
        "agent_tick_counts": {aid: len(rows) for aid, rows in (focus.get("agents") or {}).items()},
    }
    p = out_dir / "analysis_behavioral_summary.json"
    p.write_text(json.dumps(summary, indent=2, sort_keys=True, default=str))
    paths["analysis_behavioral_summary.json"] = str(p)

    if graph is not None:
        gp = out_dir / "analysis_relationship_graph.json"
        gp.write_text(json.dumps(graph.to_export(max_edges=8000), indent=2, sort_keys=True, default=str))
        paths["analysis_relationship_graph.json"] = str(gp)

    if stories is not None:
        sp = out_dir / "analysis_tick_stories.jsonl"
        with sp.open("w", encoding="utf-8") as f:
            for s in stories:
                f.write(json.dumps(s.to_dict(include_receipts=False), sort_keys=True, default=str) + "\n")
        paths["analysis_tick_stories.jsonl"] = str(sp)
        tp = out_dir / "analysis_derived_trajectory.jsonl"
        with tp.open("w", encoding="utf-8") as f:
            for rec in _iter_trajectory_records(stories):
                f.write(json.dumps(rec, sort_keys=True, default=str) + "\n")
        paths["analysis_derived_trajectory.jsonl"] = str(tp)

    if episodes is not None:
        ep = out_dir / "analysis_episodes.json"
        ep.write_text(json.dumps({
            "schema": "mm.analyzer_next.episodes.v1",
            "counts": episode_counts(episodes),
            "episodes": [e.to_dict() for e in episodes],
        }, indent=2, sort_keys=True, default=str))
        paths["analysis_episodes.json"] = str(ep)

    smp = out_dir / "analysis_sensorimotor_consequence.json"
    smp.write_text(json.dumps({
        "schema": "mm.analyzer_next.sensorimotor_consequence.v1",
        "summary": payload.get("sensorimotor_summary"),
        "steps_count": payload.get("sensorimotor_steps_count"),
        "motor_reversals": motor_revs or [],
        "sensorimotor_trend_reversals": sm_revs or [],
        "receding_while_watching": payload.get("receding_while_watching"),
        "visual_asymmetry": payload.get("visual_asymmetry"),
        "longitudinal": payload.get("longitudinal"),
        "steps_sample": [s.to_dict() if hasattr(s, "to_dict") else s for s in (steps or [])[:200]],
    }, indent=2, sort_keys=True, default=str))
    paths["analysis_sensorimotor_consequence.json"] = str(smp)

    rt = out_dir / "BEHAVIORAL_RECONSTRUCTION.txt"
    rt.write_text((payload.get("report_text") or "") + "\n" + (payload.get("sensorimotor_report_text") or ""))
    paths["BEHAVIORAL_RECONSTRUCTION.txt"] = str(rt)
    return paths
