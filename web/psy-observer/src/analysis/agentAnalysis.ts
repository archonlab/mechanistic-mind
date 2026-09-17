import type { AnalysisState } from './aggregates.ts';
import type { AgentAnalysis, NaMetric } from './types.ts';

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
      const wait = Number(agg.action_counts.WAIT || 0);
      const move = Object.entries(agg.action_counts)
        .filter(([k]) => k.startsWith('MOVE'))
        .reduce((s, [, v]) => s + Number(v), 0);
      const total = Object.values(agg.action_counts).reduce((s, v) => s + Number(v), 0) || wait + move;
      const moveDist: Record<string, number> = {};
      for (const [k, v] of Object.entries(agg.action_counts)) {
        if (k.startsWith('MOVE')) moveDist[k] = Number(v);
      }
      const uniqueRuntime = (agg as any)._unique_cells_runtime as number | undefined;
      const unique = uniqueRuntime != null ? Math.max(uniqueRuntime, agg.unique_cells.size) : agg.unique_cells.size;
      const net = agg.start_xy && agg.last_xy
        ? Math.hypot(agg.last_xy.x - agg.start_xy.x, agg.last_xy.y - agg.start_xy.y)
        : null;
      return {
        agent_id: agg.agent_id,
        seed: naNum(agg.seed),
        body_id: agg.body_id,
        ticks_observed: Math.max(agg.ticks, total),
        actions: {
          wait_count: total ? wait : naNum(null),
          wait_pct: pct(wait, total),
          move_count: total ? move : naNum(null),
          move_pct: pct(move, total),
          move_distribution: Object.keys(moveDist).length ? moveDist : 'NOT AVAILABLE',
          action_transitions: Object.keys(agg.action_transitions).length ? { ...agg.action_transitions } : 'NOT AVAILABLE',
          longest_wait_streak: agg.longest_wait_streak || (wait ? 0 : 'NOT AVAILABLE'),
          longest_move_streak: agg.longest_move_streak || (move ? 0 : 'NOT AVAILABLE'),
        },
        movement: {
          distance_travelled: agg.distance > 0 || unique > 0 ? agg.distance : naNum(agg.distance === 0 ? 0 : null),
          net_displacement: naNum(net),
          mean_speed: agg.speed_n ? agg.speed_sum / agg.speed_n : 'NOT AVAILABLE',
          max_speed: agg.max_speed > 0 ? agg.max_speed : 'NOT AVAILABLE',
          rotation_accumulated: agg.rotation_accum > 0 ? agg.rotation_accum : 'NOT AVAILABLE',
          unique_cells: unique > 0 ? unique : 'NOT AVAILABLE',
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
          prediction_count: naNum(agg.prediction_count),
          prediction_error: naNum(agg.prediction_error),
          prospective_compositions: naNum(agg.prospective),
          novel_compositions: naNum(agg.novel),
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
