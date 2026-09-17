/**
 * Scientific evidence package → Analyzer input (shared LIVE / offline path).
 */
import {
  ingestAnalysisInput,
  buildRunAnalysis,
} from './runAnalysis.ts';
import type { AnalysisInput } from './runAnalysis.ts';
import { createAnalysisState } from './aggregates.ts';
import type { AnalysisMode, CoverageLevel, RunAnalysis } from './types.ts';
import { formatAnalysisLog } from './analysisLog.ts';

export type EvidencePackage = {
  schema?: string;
  analyzer_version?: string;
  run_id?: string | null;
  source?: string;
  runtime_status?: string;
  analysis_cutoff_tick?: number | null;
  scientific_tick_range?: [number | null, number | null] | null;
  coverage?: string;
  coverage_detail?: Record<string, any>;
  complete_tick_level_reanalysis?: boolean;
  evidence_files?: string[];
  evidence_counts?: Record<string, number>;
  identity?: Record<string, any>;
  timeline?: any[];
  events?: any[];
  scientific_rows?: any[];
  cumulative_runtime_summaries?: any[];
  used_cumulative_runtime_summaries?: boolean;
  note?: string;
  run_dir?: string;
  manifest?: Record<string, any>;
  frame?: any;
};

export const ANALYZER_VERSION = '1.1.0';

function mapCoverage(level: string | undefined): CoverageLevel {
  const u = String(level || '').toUpperCase();
  if (u === 'FULL') return 'FULL';
  if (u === 'PARTIAL') return 'PARTIAL';
  if (u === 'COMPLETE') return 'COMPLETE';
  if (u === 'INSUFFICIENT') return 'INSUFFICIENT';
  if (u === 'LIVE') return 'LIVE';
  if (u === 'INCREMENTAL') return 'INCREMENTAL';
  return 'PARTIAL';
}

/** Build RunAnalysis from a backend evidence package (read-only). */
export function analyzeEvidencePackage(
  pkg: EvidencePackage,
  opts?: { mode?: AnalysisMode; frame?: any; mechanisms?: any[] },
): RunAnalysis {
  const mode: AnalysisMode =
    opts?.mode
    || (String(pkg.runtime_status || '').toUpperCase() === 'RUNNING' ? 'LIVE' : 'FINAL');

  const frame = opts?.frame || pkg.frame || {
    header: {
      tick: pkg.analysis_cutoff_tick ?? pkg.scientific_tick_range?.[1] ?? 0,
      status: pkg.runtime_status || 'UNKNOWN',
      seed: pkg.identity?.seed ?? pkg.manifest?.seed,
      runtime_generation: pkg.identity?.runtime_generation,
      runtime_model: pkg.identity?.runtime_type || pkg.manifest?.runtime_type,
      agent_count: pkg.identity?.agent_count || pkg.manifest?.agent_count || 1,
    },
    experiment: {
      runtime: {
        type: pkg.identity?.runtime_type || pkg.manifest?.runtime_type || 'UNKNOWN',
        agent_count: pkg.identity?.agent_count || 1,
      },
    },
  };

  const input: AnalysisInput = {
    frame,
    timeline: pkg.timeline || [],
    events: pkg.events || [],
    mechanisms: opts?.mechanisms,
    mode,
    // Scientific path: do not fold cumulative action_counts into tick aggregates.
    scientificEvidence: true,
    skipLiveCumulativeActions: true,
  };

  const state = createAnalysisState();
  ingestAnalysisInput(state, input);
  // Enrich from scientific rows (action_source / resources) when bodies lack them
  if (pkg.scientific_rows?.length) {
    for (const row of pkg.scientific_rows) {
      const aid = String(row.agent_id || 'agent_0');
      const agg = state.agents[aid];
      if (!agg) continue;
      if (row.action_source && row.tick != null) {
        // Already counted via timeline bodies if action_source present; ensure seed
      }
      if (row.agent_seed != null && agg.seed == null) agg.seed = Number(row.agent_seed);
      if (row.prediction_count != null) agg.prediction_count = Number(row.prediction_count);
      if (row.prospective_compositions != null) agg.prospective = Number(row.prospective_compositions);
    }
  }

  const analysis = buildRunAnalysis(state, mode);
  const covLevel = mapCoverage(pkg.coverage);
  const detail = pkg.coverage_detail || {};
  const range = pkg.scientific_tick_range || [null, null];

  analysis.coverage.level = covLevel === 'FULL' ? 'FULL' : covLevel;
  analysis.coverage.reason = String(
    detail.reason
    || (covLevel === 'FULL'
      ? 'Complete scientific_timeline evidence through analysis cutoff'
      : 'Partial or legacy evidence — not a full tick-level reconstruction'),
  );
  analysis.lifecycle.coverage = analysis.coverage.level;
  analysis.lifecycle.coverage_reason = analysis.coverage.reason;
  analysis.lifecycle.analyzed_start = range[0] ?? analysis.lifecycle.analyzed_start;
  analysis.lifecycle.analyzed_end = range[1] ?? analysis.lifecycle.analyzed_end;

  if (String(pkg.runtime_status || '').toUpperCase() === 'RUNNING') {
    analysis.lifecycle.phase = 'LIVE';
    analysis.lifecycle.banner = 'ANALYSIS: RUNNING (cutoff snapshot)';
    analysis.lifecycle.live_runtime_tick = pkg.analysis_cutoff_tick ?? analysis.lifecycle.live_runtime_tick;
  } else if (covLevel === 'FULL') {
    analysis.lifecycle.phase = 'COMPLETE';
    analysis.lifecycle.banner = 'ANALYSIS: COMPLETE (FULL scientific evidence)';
  } else if (covLevel === 'PARTIAL') {
    analysis.lifecycle.phase = 'COMPLETE';
    analysis.lifecycle.banner = 'ANALYSIS: COMPLETE (PARTIAL evidence)';
  }

  analysis.evidence_meta = {
    analyzer_version: pkg.analyzer_version || ANALYZER_VERSION,
    analysis_timestamp: new Date().toISOString(),
    run_id: pkg.run_id || null,
    runtime_status: pkg.runtime_status || null,
    analysis_cutoff_tick: pkg.analysis_cutoff_tick ?? null,
    scientific_tick_range: range,
    coverage: covLevel,
    complete_tick_level_reanalysis: !!pkg.complete_tick_level_reanalysis,
    evidence_files: pkg.evidence_files || [],
    evidence_counts: pkg.evidence_counts || {},
    used_cumulative_runtime_summaries: !!pkg.used_cumulative_runtime_summaries,
    cumulative_runtime_summaries: pkg.cumulative_runtime_summaries || [],
    source: pkg.source || null,
    note: pkg.note || null,
  };

  analysis.analysis_log = formatAnalysisLog(analysis);
  return analysis;
}

/** Pure re-analysis helper used by tests — same core as UI Analyze button. */
export function reanalyzeEvidence(pkg: EvidencePackage): RunAnalysis {
  return analyzeEvidencePackage(pkg, { mode: 'FINAL' });
}

export function scientificCoreFingerprint(analysis: RunAnalysis): string {
  /** Stable scientific payload excluding timestamps / output paths. */
  const payload = {
    coverage: analysis.coverage.level,
    range: [analysis.lifecycle.analyzed_start, analysis.lifecycle.analyzed_end],
    agents: analysis.agents.map((a) => ({
      id: a.agent_id,
      wait: a.actions.wait_count,
      move: a.actions.move_count,
      dist: a.movement.distance_travelled,
      wait_streak: a.actions.longest_wait_streak,
      move_streak: a.actions.longest_move_streak,
      sources: a.cognition.selected_action_sources,
    })),
    contact_ticks: analysis.interactions.contact_ticks,
    first_contact: analysis.interactions.first_contact_tick,
    unique_ticks: analysis.coverage.unique_simulation_ticks,
  };
  return JSON.stringify(payload);
}

// re-export for convenience
export { ingestAnalysisInput, buildRunAnalysis };
export { createAnalysisState };
