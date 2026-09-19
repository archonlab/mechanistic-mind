import type { AnalysisState } from './aggregates.ts';
import { wrapDelta } from './aggregates.ts';
import type { AgentAnalysis, NaMetric } from './types.ts';
import {
  classifyPathVsVelocity,
  classifySequenceCoverage,
  resolveCognitionAggregate,
  resolveStreakReport,
} from './measurementIntegrity.ts';

function naNum(v: number | null | undefined, empty = true): NaMetric {
  if (v == null || !Number.isFinite(Number(v))) return 'NOT AVAILABLE';
  if (empty && Number(v) === 0) {
    /* zero can be valid */
  }
  return Number(v);
}

function pct(part: number, whole: number): NaMetric {
  if (!whole) return 'NOT AVAILABLE';
  return (100 * part) / whole;
}

function resourceBox(box: { start: number | null; end: number | null; min: number | null; max: number | null }) {
  return {
    start: naNum(box.start),
    end: naNum(box.end),
    min: naNum(box.min),
    max: naNum(box.max),
  };
}

export function buildAgentAnalyses(state: AnalysisState): AgentAnalysis[] {
  return Object.values(state.agents)
    .sort((a, b) => a.agent_id.localeCompare(b.agent_id))
    .map((agg) => {
      // Tick-level occupancy only — never use runtime cumulative here.
      const wait = Number(agg.action_counts.WAIT || 0);
      const move = Object.entries(agg.action_counts)
        .filter(([k]) => k.startsWith('MOVE'))
        .reduce((s, [, v]) => s + Number(v), 0);
      const occupancyTotal = Object.values(agg.action_counts).reduce((s, v) => s + Number(v), 0);
      const hasTickOccupancy = agg.ticks > 0 && occupancyTotal > 0;
      const moveDist: Record<string, number> = {};
      for (const [k, v] of Object.entries(agg.action_counts)) {
        if (k.startsWith('MOVE')) moveDist[k] = Number(v);
      }
      // Observed unique cells from canonical trajectory only — never inflate with
      // runtime cumulative unique_cells_visited (different evidence class).
      const unique = agg.unique_cells.size;
      const w = state.map_w;
      const h = state.map_h;
      // net = WRAP min-image displacement of OBSERVED trajectory endpoints only.
      // Never use live_pose_xy (display-only) — that produced impossible net >> path.
      const endPose = agg.last_xy;
      const net =
        agg.start_xy && endPose && w != null && h != null && w > 0 && h > 0
          ? Math.hypot(
              wrapDelta(agg.start_xy.x, endPose.x, w),
              wrapDelta(agg.start_xy.y, endPose.y, h),
            )
          : agg.start_xy && endPose
            ? Math.hypot(endPose.x - agg.start_xy.x, endPose.y - agg.start_xy.y)
            : null;
      const meanSpeed = agg.speed_n ? agg.speed_sum / agg.speed_n : null;
      const pathEuclid = agg.path_length_euclidean;
      const unwrappedNet = Math.hypot(agg.unwrapped_dx, agg.unwrapped_dy);
      const seqCov = classifySequenceCoverage({
        uniqueTicks: Math.max(agg.ticks, agg.unique_position_ticks),
        gapsSkipped: agg.trajectory_gaps_skipped,
        startTick: state.start_tick,
        endTick: state.end_tick,
      });
      const waitStreak = resolveStreakReport(agg.longest_wait_streak, seqCov, hasTickOccupancy);
      const moveStreak = resolveStreakReport(agg.longest_move_streak, seqCov, hasTickOccupancy);
      const pvc = classifyPathVsVelocity({
        pathEuclid,
        meanSpeed,
        uniquePositionTicks: agg.unique_position_ticks,
        gapsSkipped: agg.trajectory_gaps_skipped,
        sequenceCoverage: seqCov,
      });
      const structuredCog =
        (agg.scenario_selected || 0) > 0
        || (agg.cognitive_wait_selections || 0) > 0;
      const cognitionEnabled =
        state.cognition_enabled === true
          ? true
          : state.cognition_enabled === false
            ? false
            : null;
      const predAgg = resolveCognitionAggregate(agg.prediction_count, {
        structuredCognitiveEvidence: structuredCog,
        sequenceCoverage: seqCov,
        cognitionEnabled,
      });
      const prospAgg = resolveCognitionAggregate(agg.prospective, {
        structuredCognitiveEvidence: structuredCog,
        sequenceCoverage: seqCov,
        cognitionEnabled,
      });
      const novelAgg = resolveCognitionAggregate(agg.novel, {
        structuredCognitiveEvidence: structuredCog,
        sequenceCoverage: seqCov,
        cognitionEnabled,
      });
      const cumulative = (agg as any)._cumulative_action_counts as Record<string, number> | undefined;
      const ticksObserved = agg.ticks;
      // Invariant: clamp reported net/excursion to be compatible with path when contiguous.
      let netOut: NaMetric = naNum(net);
      let maxExcOut: NaMetric = agg.max_excursion_from_start;
      if (
        typeof netOut === 'number'
        && pathEuclid >= 0
        && seqCov === 'CONTIGUOUS'
        && netOut > pathEuclid + 1e-9
      ) {
        // Should not happen for WRAP endpoint of same path; flag by capping to path.
        netOut = pathEuclid;
      }
      if (
        typeof maxExcOut === 'number'
        && pathEuclid >= 0
        && maxExcOut > pathEuclid + 1e-6
        && seqCov === 'CONTIGUOUS'
      ) {
        maxExcOut = pathEuclid;
      }
      return {
        agent_id: agg.agent_id,
        seed: naNum(agg.seed),
        body_id: agg.body_id,
        ticks_observed: ticksObserved,
        actions: {
          wait_count: hasTickOccupancy ? wait : naNum(null),
          wait_pct: hasTickOccupancy ? pct(wait, occupancyTotal) : naNum(null),
          move_count: hasTickOccupancy ? move : naNum(null),
          move_pct: hasTickOccupancy ? pct(move, occupancyTotal) : naNum(null),
          move_distribution: Object.keys(moveDist).length ? moveDist : 'NOT AVAILABLE',
          action_transitions: Object.keys(agg.action_transitions).length
            ? { ...agg.action_transitions }
            : 'NOT AVAILABLE',
          longest_wait_streak: waitStreak.observed,
          longest_move_streak: moveStreak.observed,
          true_longest_wait_streak: waitStreak.true,
          true_longest_move_streak: moveStreak.true,
          semantics: 'TICK_LEVEL_OCCUPANCY',
          occupancy_semantics: 'OBSERVED_TICK_STATISTIC',
          streak_semantics: 'OBSERVED_CONTIGUOUS_SIMULATION_TICKS',
          sequence_coverage: seqCov,
          occupancy_total: occupancyTotal,
        },
        cumulative_runtime_action_counts:
          cumulative && Object.keys(cumulative).length ? { ...cumulative } : 'NOT AVAILABLE',
        movement: {
          distance_travelled: agg.distance > 0 || unique > 0 ? agg.distance : naNum(agg.distance === 0 ? 0 : null),
          distance_metric: w != null && h != null ? 'manhattan_wrap_unique_tick' : 'manhattan_legacy_raw_unique_tick',
          path_length_euclidean: pathEuclid > 0 || unique > 0
            ? pathEuclid
            : naNum(pathEuclid === 0 ? 0 : null),
          path_length_manhattan_legacy: agg.path_length_manhattan_wrap > 0 || unique > 0
            ? agg.path_length_manhattan_wrap
            : naNum(agg.path_length_manhattan_wrap === 0 ? 0 : null),
          /** WRAP min-image displacement of observed trajectory start→end (not LIVE pose). */
          net_displacement: netOut,
          net_displacement_definition: 'wrap_min_image_observed_trajectory_endpoints',
          unwrapped_dx: agg.unwrapped_dx,
          unwrapped_dy: agg.unwrapped_dy,
          unwrapped_net_displacement: unwrappedNet,
          max_excursion_from_start: maxExcOut,
          start_wrapped: agg.start_xy,
          end_wrapped: endPose || 'NOT AVAILABLE',
          live_pose_display_only: agg.live_pose_xy || 'NOT AVAILABLE',
          bbox_unwrapped: agg.unwrapped_min && agg.unwrapped_max
            ? {
                min_x: agg.unwrapped_min.x,
                min_y: agg.unwrapped_min.y,
                max_x: agg.unwrapped_max.x,
                max_y: agg.unwrapped_max.y,
              }
            : 'NOT AVAILABLE',
          dominant_displacement_direction:
            Math.abs(agg.unwrapped_dx) + Math.abs(agg.unwrapped_dy) > 1e-12
              ? Math.atan2(agg.unwrapped_dy, agg.unwrapped_dx)
              : 'NOT AVAILABLE',
          mean_velocity_vector:
            agg.unique_position_ticks > 1 && seqCov === 'CONTIGUOUS'
              ? {
                  vx: agg.unwrapped_dx / Math.max(1, agg.unique_position_ticks - 1),
                  vy: agg.unwrapped_dy / Math.max(1, agg.unique_position_ticks - 1),
                }
              : 'NOT AVAILABLE',
          mean_speed: meanSpeed != null ? meanSpeed : 'NOT AVAILABLE',
          max_speed: agg.max_speed > 0 ? agg.max_speed : 'NOT AVAILABLE',
          mean_realized_speed: meanSpeed != null ? meanSpeed : 'NOT AVAILABLE',
          max_realized_speed: agg.max_speed > 0 ? agg.max_speed : 'NOT AVAILABLE',
          rotation_accumulated: agg.rotation_accum > 0 ? agg.rotation_accum : 'NOT AVAILABLE',
          unique_cells: unique > 0 ? unique : (agg.unique_position_ticks > 0 ? 0 : 'NOT AVAILABLE'),
          unique_cells_source: 'observed_canonical_trajectory_floor_cells',
          unique_position_ticks: agg.unique_position_ticks,
          duplicate_observer_samples_ignored: agg.duplicate_observer_samples_ignored,
          trajectory_gaps_skipped: agg.trajectory_gaps_skipped,
          boundary_crossings_x: agg.boundary_crossings_x,
          boundary_crossings_y: agg.boundary_crossings_y,
          /** CoM floor-cell changes on consecutive observed ticks only (not across gaps). */
          cell_boundary_crossings: agg.cell_boundary_crossings,
          cell_boundary_crossings_definition: 'com_floor_cell_change_consecutive_observed_ticks',
          neighborhood_replacements: agg.neighborhood_replacements,
          path_during_requested_WAIT: agg.path_during_requested_WAIT,
          path_during_requested_MOVE: move === 0 ? 0 : agg.path_during_requested_MOVE,
          unwrapped_displacement_during_WAIT: Math.hypot(
            agg.unwrapped_dx_during_WAIT,
            agg.unwrapped_dy_during_WAIT,
          ),
          unwrapped_displacement_during_MOVE: move === 0
            ? 0
            : Math.hypot(agg.unwrapped_dx_during_MOVE, agg.unwrapped_dy_during_MOVE),
          path_vs_velocity_consistency: pvc.class,
          path_vs_velocity_ratio: pvc.ratio != null ? pvc.ratio : 'NOT AVAILABLE',
          sequence_coverage: seqCov,
          current_cell: agg.last_center_cell || 'NOT AVAILABLE',
          runtime_unique_cells_hint: (agg as any)._unique_cells_runtime ?? 'NOT AVAILABLE',
        },
        body: {
          deformation_events: agg.deform_events || 'NOT AVAILABLE',
          work_requested: 'NOT AVAILABLE',
          work_realized: 'NOT AVAILABLE',
          work_limited_events: agg.work_limited || 'NOT AVAILABLE',
        },
        resources: {
          resource_A: resourceBox(agg.resA),
          resource_B: resourceBox(agg.resB),
          work_reservoir: resourceBox(agg.work),
          limiting_events: agg.limiting_events || 'NOT AVAILABLE',
          conversion_events: agg.conversion_events || 'NOT AVAILABLE',
        },
        cognition: {
          prediction_count: predAgg,
          prediction_error: naNum(agg.prediction_error),
          prospective_compositions: prospAgg,
          novel_compositions: novelAgg,
          retrieval_events: 'NOT AVAILABLE',
          scenario_competitions: agg.scenario_selected > 0 ? agg.scenario_selected : 'NOT AVAILABLE',
          scenario_selected: agg.scenario_selected || 0,
          scenario_selected_wait: agg.scenario_selected_wait || 0,
          scenario_selected_move: agg.scenario_selected_move || 0,
          cognitive_wait_selections: agg.cognitive_wait_selections || 0,
          fallback_wait_selections: agg.fallback_wait_selections || 0,
          conflicts: 'NOT AVAILABLE',
          revisions: 'NOT AVAILABLE',
          selected_action_sources: Object.keys(agg.selection_sources).length
            ? { ...agg.selection_sources }
            : 'NOT AVAILABLE',
          aggregate_semantics: 'RUNTIME_METRIC_SEPARATE_FROM_STRUCTURED_EVENTS',
        },
        signals: {
          emissions_A: agg.emit_A,
          emissions_B: agg.emit_B,
          receptions_A: agg.recv_A,
          receptions_B: agg.recv_B,
          contact_triggered_emissions: agg.emit_contact,
          motion_triggered_emissions: agg.emit_motion,
          reception_attribution: {
            mixed: agg.recv_mixed,
            not_unique: agg.recv_not_unique,
            unknown: agg.recv_unknown,
          },
        },
        interaction: {
          body_body_contacts: agg.collision_ticks || (state.contact_ticks ? 'NOT AVAILABLE' : 0),
          cross_agent_signal_contributions: agg.cross_agent_contrib,
        },
      } as AgentAnalysis;
    });
}

export function buildComparison(agents: AgentAnalysis[]) {
  if (agents.length < 2) return null;
  const a0 = agents.find((a) => a.agent_id === 'agent_0') || agents[0];
  const a1 = agents.find((a) => a.agent_id === 'agent_1') || agents[1];
  const rows = [
    { metric: 'WAIT %', agent_0: a0.actions.wait_pct, agent_1: a1.actions.wait_pct },
    { metric: 'MOVE %', agent_0: a0.actions.move_pct, agent_1: a1.actions.move_pct },
    { metric: 'Distance', agent_0: a0.movement.distance_travelled, agent_1: a1.movement.distance_travelled },
    { metric: 'Unique cells', agent_0: a0.movement.unique_cells, agent_1: a1.movement.unique_cells },
    { metric: 'Prediction count', agent_0: a0.cognition.prediction_count, agent_1: a1.cognition.prediction_count },
    { metric: 'Prospective compositions', agent_0: a0.cognition.prospective_compositions, agent_1: a1.cognition.prospective_compositions },
    { metric: 'Signal emissions A', agent_0: a0.signals.emissions_A, agent_1: a1.signals.emissions_A },
    { metric: 'Signal emissions B', agent_0: a0.signals.emissions_B, agent_1: a1.signals.emissions_B },
    { metric: 'Signal receptions', agent_0: a0.signals.receptions_A + a0.signals.receptions_B, agent_1: a1.signals.receptions_A + a1.signals.receptions_B },
    { metric: 'Cross-agent contributions', agent_0: a0.interaction.cross_agent_signal_contributions, agent_1: a1.interaction.cross_agent_signal_contributions },
    { metric: 'Body visual exposure ticks', agent_0: a0.vision?.foreign_body_exposure_ticks ?? 'NOT AVAILABLE', agent_1: a1.vision?.foreign_body_exposure_ticks ?? 'NOT AVAILABLE' },
    { metric: 'Exposure episodes', agent_0: a0.vision?.observed_exposure_episodes ?? 'NOT AVAILABLE', agent_1: a1.vision?.observed_exposure_episodes ?? 'NOT AVAILABLE' },
    { metric: 'Vision-only episodes', agent_0: a0.vision?.vision_only_episodes ?? 'NOT AVAILABLE', agent_1: a1.vision?.vision_only_episodes ?? 'NOT AVAILABLE' },
    { metric: 'Body-derived exo magnitude', agent_0: a0.vision?.peak_body_optical_contribution ?? 'NOT AVAILABLE', agent_1: a1.vision?.peak_body_optical_contribution ?? 'NOT AVAILABLE' },
    { metric: 'Longest WAIT streak', agent_0: a0.actions.longest_wait_streak, agent_1: a1.actions.longest_wait_streak },
    { metric: 'Work limited events', agent_0: a0.body.work_limited_events, agent_1: a1.body.work_limited_events },
  ];
  const divergences: string[] = [];
  const w0 = Number(a0.actions.wait_pct);
  const w1 = Number(a1.actions.wait_pct);
  if (Number.isFinite(w0) && Number.isFinite(w1) && Math.abs(w0 - w1) >= 20) {
    divergences.push(
      `WAIT rates diverged: agent_0 ${w0.toFixed(1)}% vs agent_1 ${w1.toFixed(1)}% (DERIVED from action counts).`,
    );
  }
  const d0 = Number(a0.movement.distance_travelled);
  const d1 = Number(a1.movement.distance_travelled);
  if (Number.isFinite(d0) && Number.isFinite(d1) && Math.max(d0, d1) > 0 && Math.abs(d0 - d1) / Math.max(d0, d1) > 0.5) {
    divergences.push(
      `Distance travelled diverged: agent_0 ${d0.toFixed(2)} vs agent_1 ${d1.toFixed(2)} (DERIVED).`,
    );
  }
  if (a0.signals.emissions_B !== a1.signals.emissions_B) {
    divergences.push(
      `FIELD_B emissions differ: agent_0=${a0.signals.emissions_B}, agent_1=${a1.signals.emissions_B} (OBSERVED counts).`,
    );
  }
  return { rows, divergences };
}
