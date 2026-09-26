/**
 * Beta 2 LIVE measurement integrity — coverage & honesty helpers.
 * Analyzer-only. No runtime physics/cognition changes.
 */

export type SequenceCoverage =
  | 'CONTIGUOUS'
  | 'SPARSE'
  | 'PARTIAL'
  | 'UNAVAILABLE';

export type PathVsVelocityClass =
  | 'CONSISTENT'
  | 'INCONSISTENT'
  | 'NOT_COMPARABLE_DUE_TO_COVERAGE'
  | 'NOT_AVAILABLE';

export type AgentCoverageMeta = {
  observed_unique_action_ticks: number;
  observed_unique_position_ticks: number;
  trajectory_gaps_skipped: number;
  sequence_coverage: SequenceCoverage;
  longest_observed_contiguous_wait: number;
  longest_observed_contiguous_move: number;
  /** True longest streak across full runtime span — only when CONTIGUOUS. */
  true_longest_wait_streak: number | 'NOT AVAILABLE';
  true_longest_move_streak: number | 'NOT AVAILABLE';
  occupancy_semantics: 'OBSERVED_TICK_STATISTIC';
  streak_semantics: 'OBSERVED_CONTIGUOUS_SIMULATION_TICKS';
};

export function classifySequenceCoverage(opts: {
  uniqueTicks: number;
  gapsSkipped: number;
  startTick: number | null;
  endTick: number | null;
}): SequenceCoverage {
  const { uniqueTicks, gapsSkipped, startTick, endTick } = opts;
  if (uniqueTicks <= 0) return 'UNAVAILABLE';
  if (gapsSkipped <= 0) {
    if (startTick != null && endTick != null) {
      const span = endTick - startTick + 1;
      if (span > uniqueTicks * 2 && uniqueTicks < span) return 'PARTIAL';
    }
    return 'CONTIGUOUS';
  }
  // Any skipped simulation-tick gap → sparse for sequence-dependent metrics.
  return 'SPARSE';
}

export function resolveStreakReport(
  longestObserved: number,
  coverage: SequenceCoverage,
  hasOccupancy: boolean,
): { observed: number | 'NOT AVAILABLE'; true: number | 'NOT AVAILABLE' } {
  if (!hasOccupancy) return { observed: 'NOT AVAILABLE', true: 'NOT AVAILABLE' };
  const observed = longestObserved || 0;
  if (coverage === 'CONTIGUOUS') {
    return { observed, true: observed };
  }
  // Sparse/partial: observed contiguous is a lower bound on what we saw;
  // true longest across the full span is unknown.
  return { observed, true: 'NOT AVAILABLE' };
}

/**
 * Cognition aggregate honesty: numeric 0 is only valid as MEASURED ZERO.
 * When structured cognitive events exist but aggregate is 0/null under
 * incomplete LIVE coverage, report NOT AVAILABLE — never fake zero.
 */
export function resolveCognitionAggregate(
  value: number | null | undefined,
  opts: {
    structuredCognitiveEvidence: boolean;
    sequenceCoverage: SequenceCoverage;
    cognitionEnabled: boolean | null;
  },
): number | 'NOT AVAILABLE' {
  if (opts.cognitionEnabled === false) {
    if (value == null || !Number.isFinite(Number(value))) return 0;
    return Number(value);
  }
  if (value == null || !Number.isFinite(Number(value))) return 'NOT AVAILABLE';
  const n = Number(value);
  if (
    n === 0
    && opts.structuredCognitiveEvidence
    && (opts.sequenceCoverage === 'SPARSE' || opts.sequenceCoverage === 'PARTIAL')
  ) {
    return 'NOT AVAILABLE';
  }
  if (n === 0 && opts.structuredCognitiveEvidence && opts.sequenceCoverage !== 'CONTIGUOUS') {
    return 'NOT AVAILABLE';
  }
  return n;
}

export function classifyPathVsVelocity(opts: {
  pathEuclid: number;
  meanSpeed: number | null;
  uniquePositionTicks: number;
  gapsSkipped: number;
  sequenceCoverage: SequenceCoverage;
}): { class: PathVsVelocityClass; ratio: number | null } {
  const { pathEuclid, meanSpeed, uniquePositionTicks, gapsSkipped, sequenceCoverage } = opts;
  if (meanSpeed == null || !Number.isFinite(meanSpeed) || uniquePositionTicks <= 1) {
    return { class: 'NOT_AVAILABLE', ratio: null };
  }
  if (gapsSkipped > 0 || sequenceCoverage === 'SPARSE' || sequenceCoverage === 'PARTIAL') {
    return { class: 'NOT_COMPARABLE_DUE_TO_COVERAGE', ratio: null };
  }
  const speedPathEst = meanSpeed * (uniquePositionTicks - 1);
  if (speedPathEst <= 0.05 || pathEuclid <= 0.05) {
    return { class: 'NOT_AVAILABLE', ratio: null };
  }
  const ratio = pathEuclid / speedPathEst;
  if (ratio > 3 || ratio < 0.25) return { class: 'INCONSISTENT', ratio };
  return { class: 'CONSISTENT', ratio };
}

export function buildRunCoverageSummary(state: {
  start_tick: number | null;
  end_tick: number | null;
  unique_simulation_ticks: Set<number> | { size: number };
  timeline_samples: number;
  agents: Record<string, {
    trajectory_gaps_skipped: number;
    ticks: number;
    unique_position_ticks: number;
    prediction_count: number | null;
    prospective: number | null;
    scenario_selected: number;
  }>;
}): {
  runtime_span: string;
  unique_simulation_ticks_observed: number;
  coverage_class: SequenceCoverage;
  gap_count_agents_max: number;
  body_trajectory: SequenceCoverage;
  action_occupancy: string;
  continuous_streaks: string;
  cognition_aggregates: string;
  structured_cognition_events: string;
} {
  const unique = state.unique_simulation_ticks.size;
  const agents = Object.values(state.agents);
  const maxGaps = agents.reduce((m, a) => Math.max(m, a.trajectory_gaps_skipped || 0), 0);
  const cov = classifySequenceCoverage({
    uniqueTicks: unique,
    gapsSkipped: maxGaps,
    startTick: state.start_tick,
    endTick: state.end_tick,
  });
  const hasScenario = agents.some((a) => (a.scenario_selected || 0) > 0);
  const hasAgg = agents.some((a) => a.prediction_count != null || a.prospective != null);
  let cogAgg = 'NOT AVAILABLE';
  if (hasAgg && cov === 'CONTIGUOUS') cogAgg = 'AVAILABLE';
  else if (hasAgg || hasScenario) cogAgg = 'PARTIAL / NOT AVAILABLE';
  return {
    runtime_span:
      state.start_tick != null && state.end_tick != null
        ? `${state.start_tick}–${state.end_tick}`
        : 'NOT AVAILABLE',
    unique_simulation_ticks_observed: unique,
    coverage_class: cov,
    gap_count_agents_max: maxGaps,
    body_trajectory: cov,
    action_occupancy: 'OBSERVED-TICK STATISTIC',
    continuous_streaks:
      cov === 'CONTIGUOUS' ? 'CONTIGUOUS' : 'PARTIAL / LOWER BOUND (observed contiguous only)',
    cognition_aggregates: cogAgg,
    structured_cognition_events: hasScenario ? 'AVAILABLE' : 'NOT AVAILABLE',
  };
}
