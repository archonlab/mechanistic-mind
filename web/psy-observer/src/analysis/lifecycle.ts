/**
 * Analysis lifecycle + coverage honesty (observer-only).
 */
import type { AnalysisState } from './aggregates.ts';
import type { AnalysisLifecycle, AnalysisMode, CoverageLevel, DataCoverage } from './types.ts';

const MIN_SAMPLES_FOR_ANALYSIS = 3;

export function hasSufficientObservation(state: AnalysisState): boolean {
  const span = (state.end_tick ?? 0) - (state.start_tick ?? 0);
  return state.timeline_samples >= MIN_SAMPLES_FOR_ANALYSIS
    || state.event_samples >= MIN_SAMPLES_FOR_ANALYSIS
    || span >= MIN_SAMPLES_FOR_ANALYSIS;
}

export function deriveCoverage(
  state: AnalysisState,
  mode: AnalysisMode,
  status: string,
): { level: CoverageLevel; reason: string } {
  if (!hasSufficientObservation(state)) {
    return {
      level: 'INSUFFICIENT',
      reason: 'INSUFFICIENT DATA — waiting for a sensible observation window',
    };
  }
  const st = String(status || '').toUpperCase();
  // Bounded buffers: if we have samples but start_tick > 0 after a long run, evidence may be truncated
  const partial = state.timeline_samples > 0
    && state.start_tick != null
    && state.end_tick != null
    && state.end_tick - state.start_tick + 1 > state.timeline_samples * 2
    && state.timeline_samples < 50;

  if (st === 'STOPPED' || st === 'COMPLETE' || mode === 'FINAL') {
    if (partial) {
      return {
        level: 'PARTIAL',
        reason: 'earlier evidence no longer retained in bounded Observer history',
      };
    }
    return {
      level: 'COMPLETE',
      reason: 'analysis covers retained Observer evidence for this completed run',
    };
  }
  if (st === 'PAUSED') {
    return {
      level: partial ? 'PARTIAL' : 'INCREMENTAL',
      reason: partial
        ? 'earlier evidence no longer retained'
        : 'LIVE / INCREMENTAL through current pause tick',
    };
  }
  return {
    level: partial ? 'PARTIAL' : 'LIVE',
    reason: partial
      ? 'earlier evidence no longer retained'
      : 'LIVE / INCREMENTAL automatic analysis',
  };
}

export function buildLifecycle(
  state: AnalysisState,
  mode: AnalysisMode,
  liveRuntimeTick?: number | null,
): AnalysisLifecycle {
  const status = String(state.status || '').toUpperCase();
  const { level, reason } = deriveCoverage(state, mode, status);
  const insufficient = !hasSufficientObservation(state);
  let phase: AnalysisLifecycle['phase'] = 'LIVE';
  if (insufficient) phase = 'INSUFFICIENT_DATA';
  else if (status === 'STOPPED' || status === 'COMPLETE' || mode === 'FINAL') phase = 'COMPLETE';
  else if (status === 'PAUSED') phase = 'PAUSED';
  else phase = 'LIVE';

  const banner =
    phase === 'INSUFFICIENT_DATA' ? 'ANALYSIS: INSUFFICIENT DATA'
      : phase === 'LIVE' ? 'ANALYSIS: LIVE'
        : phase === 'PAUSED' ? 'ANALYSIS: PAUSED'
          : 'ANALYSIS: COMPLETE';

  return {
    phase,
    banner,
    analyzed_start: state.start_tick,
    analyzed_end: state.end_tick,
    live_runtime_tick: liveRuntimeTick ?? state.end_tick,
    agents: Math.max(state.agent_count, Object.keys(state.agents).length || 1),
    events_observed: state.event_samples,
    frames_sampled: state.timeline_samples,
    coverage: level,
    coverage_reason: reason,
    insufficient,
  };
}

export function buildCoverageBlock(state: AnalysisState, mode: AnalysisMode): DataCoverage {
  const { level, reason } = deriveCoverage(state, mode, state.status);
  return {
    world: state.map_w && state.map_h ? `${state.map_w}×${state.map_h} ${state.boundary}` : 'PARTIAL / NOT AVAILABLE',
    body: state.timeline_samples > 0 ? `timeline positions (${state.timeline_samples} samples)` : 'NOT AVAILABLE',
    cognition: Object.values(state.agents).some((a) => a.prediction_count != null || a.prospective != null)
      ? 'metrics / structured events (partial)'
      : 'NOT AVAILABLE / sparse',
    signals: state.event_samples > 0 ? `structured signal events (${state.event_samples} ingested)` : 'NOT AVAILABLE',
    causal_provenance: state.causal_pairs.length
      ? `${state.causal_pairs.length} emission→reception parent refs`
      : 'NOT AVAILABLE / none observed',
    timeline_samples: state.timeline_samples,
    event_samples: state.event_samples,
    telemetry_samples: state.telemetry_samples,
    level,
    reason,
  };
}

/** Reject meaningless tick-0 / zero extrema before enough evidence exists. */
export function isMeaningfulExtrema(
  key: string,
  ex: { tick: number; value: number },
  state: AnalysisState,
): boolean {
  if (!hasSufficientObservation(state)) return false;
  if (ex.tick === 0 && Number(ex.value) === 0) return false;
  if (key.startsWith('max_') && Number(ex.value) <= 0) return false;
  if (key.startsWith('min_') && state.telemetry_samples < 3) return false;
  if (key.includes('velocity') && Number(ex.value) <= 0) return false;
  if (key.includes('signal') && Number(ex.value) <= 0) return false;
  return true;
}
