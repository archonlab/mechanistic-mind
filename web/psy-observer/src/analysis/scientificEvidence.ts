/**
 * Scientific evidence package → Analyzer input (shared LIVE / offline path).
 */
import {
  ingestAnalysisInput,
  buildRunAnalysis,
} from './runAnalysis.ts';
import type { AnalysisInput } from './runAnalysis.ts';
import { createAnalysisState, ensureAgent } from './aggregates.ts';
import type { AnalysisMode, CoverageLevel, RunAnalysis } from './types.ts';
import { formatAnalysisLog } from './analysisLog.ts';
import { buildCompositeMotorForensics } from './compositeMotorForensics.ts';

export type EvidencePackage = {
  schema?: string;
  analyzer_version?: string;
  telemetry_schema?: string;
  telemetry_mode?: string | null;
  event_exhaustiveness?: Record<string, any> | null;
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
  scientific_v3_core?: Record<string, any> | null;
  behavioral_reconstruction?: Record<string, any> | null;
  v3_evidence_health?: Record<string, any> | null;
  unique_simulation_ticks?: number;
  canonical_history?: Record<string, any> | null;
};

export const ANALYZER_VERSION = '1.2.0';

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

  const hist: any = (pkg as any).canonical_history || {};
  const backendUnique = Number(
    hist.unique_simulation_ticks
    ?? (pkg as any).unique_simulation_ticks
    ?? 0,
  );
  const backendRange: [number | null, number | null] = (
    (hist.scientific_tick_range as [number | null, number | null] | undefined)
    || pkg.scientific_tick_range
    || [hist.tick_min ?? null, hist.tick_max ?? null]
  );
  if (backendRange[0] != null) {
    const a = Number(backendRange[0]);
    const b = Number(backendRange[1] ?? backendRange[0]);
    if (state.start_tick == null || a < state.start_tick) state.start_tick = a;
    if (state.end_tick == null || b > state.end_tick) state.end_tick = b;
  }
  if (backendUnique > 0) {
    const lo = Number(backendRange[0] ?? 1);
    const hi = Number(backendRange[1] ?? (lo + backendUnique - 1));
    if (Number.isFinite(lo) && Number.isFinite(hi) && hi >= lo && hi - lo + 1 <= 500_000) {
      for (let t = lo; t <= hi; t += 1) state.unique_simulation_ticks.add(t);
    }
  }
  const histAgents = hist.agents || {};
  for (const [aid, row] of Object.entries(histAgents) as [string, any][]) {
    const agg = ensureAgent(state, aid, row.body_id);
    agg.ticks = Number(row.ticks_observed || agg.ticks || 0);
    if (row.wait_count) agg.action_counts.WAIT = Number(row.wait_count);
    const md = row.move_distribution || {};
    for (const [k, v] of Object.entries(md)) {
      agg.action_counts[String(k)] = Number(v);
    }
    if (row.pose_ticks) agg.unique_position_ticks = Number(row.pose_ticks);
    if (row.distance_manhattan_wrap != null && Number.isFinite(Number(row.distance_manhattan_wrap))) {
      agg.distance = Number(row.distance_manhattan_wrap);
    }
    if (row.path_length_euclidean != null && Number.isFinite(Number(row.path_length_euclidean))) {
      agg.path_length_euclidean = Number(row.path_length_euclidean);
    }
    if (row.unique_cells != null && Number.isFinite(Number(row.unique_cells))) {
      (agg as any)._canonical_unique_cells = Number(row.unique_cells);
    }
    if (row.path_available === false && (row.unique_cells == null || Number(row.unique_cells) === 0)) {
      (agg as any)._canonical_path_unavailable = true;
    }
    if (row.visual_exposure_ticks) {
      (agg as any).foreign_body_exposure_ticks = Number(row.visual_exposure_ticks);
    }
  }
  const join = (pkg as any).join_summary || {};
  if (join.event_ticks_indexed) state.event_samples = Number(join.event_ticks_indexed);

  const analysis = buildRunAnalysis(state, mode, {
    scientific_rows: pkg.scientific_rows,
    frame,
  });
  (analysis as any).composite_motor = buildCompositeMotorForensics(
    pkg.scientific_rows,
    pkg.events,
    pkg.analysis_cutoff_tick,
  );
  (analysis as any).motor_schema = (analysis as any).composite_motor?.schema;
  const covLevel = mapCoverage(pkg.coverage);
  const detail = pkg.coverage_detail || {};
  const range: [number | null, number | null] = (
    pkg.scientific_tick_range
    || backendRange
    || [null, null]
  );
  const uniqueAfter = analysis.coverage.unique_simulation_ticks || 0;
  let reported = covLevel;
  let completeRe = !!pkg.complete_tick_level_reanalysis;
  if (uniqueAfter <= 0) {
    reported = 'INSUFFICIENT';
    completeRe = false;
  }

  analysis.coverage.level = reported === 'FULL' ? 'FULL' : reported;
  analysis.coverage.reason = String(
    uniqueAfter <= 0
      ? 'Reconstruction consumed zero unique simulation ticks — FULL coverage is not allowed.'
      : (detail.reason
        || (reported === 'FULL'
          ? 'Complete scientific_timeline evidence through analysis cutoff'
          : 'Partial or legacy evidence — not a full tick-level reconstruction')),
  );
  (analysis.coverage as any).runtime_span =
    range[0] != null && range[1] != null ? `${range[0]}–${range[1]}` : (analysis.coverage as any).runtime_span;
  analysis.identity.start_tick = Number(range[0] ?? analysis.identity.start_tick);
  analysis.identity.end_tick = Number(range[1] ?? analysis.identity.end_tick);
  analysis.identity.duration_ticks =
    analysis.identity.end_tick - analysis.identity.start_tick;
  analysis.lifecycle.coverage = analysis.coverage.level;
  analysis.lifecycle.coverage_reason = analysis.coverage.reason;
  analysis.lifecycle.analyzed_start = range[0] ?? analysis.lifecycle.analyzed_start;
  analysis.lifecycle.analyzed_end = range[1] ?? analysis.lifecycle.analyzed_end;
  analysis.lifecycle.events_observed = Number(
    (pkg as any).join_summary?.event_ticks_indexed
    ?? analysis.lifecycle.events_observed
    ?? 0,
  );

  if (String(pkg.runtime_status || '').toUpperCase() === 'RUNNING') {
    analysis.lifecycle.phase = 'LIVE';
    analysis.lifecycle.banner = 'ANALYSIS: RUNNING (cutoff snapshot)';
    analysis.lifecycle.live_runtime_tick = pkg.analysis_cutoff_tick ?? analysis.lifecycle.live_runtime_tick;
  } else if (reported === 'FULL') {
    analysis.lifecycle.phase = 'COMPLETE';
    analysis.lifecycle.banner = 'ANALYSIS: COMPLETE (FULL scientific evidence)';
  } else if (reported === 'PARTIAL') {
    analysis.lifecycle.phase = 'COMPLETE';
    analysis.lifecycle.banner = 'ANALYSIS: COMPLETE (PARTIAL evidence)';
  } else if (uniqueAfter <= 0) {
    analysis.lifecycle.phase = 'INSUFFICIENT_DATA';
    analysis.lifecycle.banner = 'ANALYSIS: INSUFFICIENT (zero ticks consumed)';
  }

  analysis.evidence_meta = {
    analyzer_version: pkg.analyzer_version || ANALYZER_VERSION,
    analysis_timestamp: new Date().toISOString(),
    run_id: pkg.run_id || null,
    runtime_status: pkg.runtime_status || null,
    analysis_cutoff_tick: pkg.analysis_cutoff_tick ?? null,
    scientific_tick_range: range,
    coverage: reported,
    complete_tick_level_reanalysis: completeRe,
    evidence_files: pkg.evidence_files || [],
    evidence_counts: pkg.evidence_counts || {},
    used_cumulative_runtime_summaries: !!pkg.used_cumulative_runtime_summaries,
    cumulative_runtime_summaries: pkg.cumulative_runtime_summaries || [],
    source: pkg.source || null,
    note: pkg.note || null,
    telemetry_schema: pkg.telemetry_schema || 'V1_FULL',
    telemetry_mode: pkg.telemetry_mode || null,
  };

  const v3 = pkg.scientific_v3_core || null;
  (analysis as any).scientific_v3_core = v3;
  (analysis as any).behavioral_reconstruction = pkg.behavioral_reconstruction || null;
  (analysis as any).v3_evidence_health = pkg.v3_evidence_health || null;
  (analysis as any).beta31_vision_report_text = (pkg as any).beta31_vision_report_text || null;
  (analysis as any).beta31_vision_summary = (pkg as any).beta31_vision_summary || (pkg as any).beta31_vision?.vision_summary || null;
  (analysis as any).canonical_history_agents = histAgents;
  // DecisionReceipts are authoritative tick-level cognition evidence for V3 CORE.
  // Do not leave "structured cognition events: NOT AVAILABLE" when V3 decisions exist.
  const v3Decisions = Number((v3 as any)?.decision_receipts || 0);
  if (v3 && (v3 as any).evidence_version === 'SCIENTIFIC_V3' && v3Decisions > 0) {
    (analysis.coverage as any).structured_cognition_events =
      `AVAILABLE via SCIENTIFIC_V3 DecisionReceipts (${v3Decisions})`;
  } else if (v3 && (v3 as any).status === 'NOT_RECORDED') {
    // leave existing SCENARIO_SELECTED-based coverage; V3 honestly absent
  }

  let vis = 0;
  let sig = 0;
  let pose = 0;
  let moves = 0;
  for (const row of Object.values(histAgents) as any[]) {
    vis += Number(row.visual_exposure_ticks || 0);
    sig += Number(row.signal_emissions || 0) + Number(row.signal_receptions || 0);
    pose += Number(row.pose_ticks || 0);
    moves += Number(row.move_count || 0);
  }
  if (pose > 0) analysis.coverage.body = 'AVAILABLE (TickStory pose / trajectory stream)';
  if (sig > 0) analysis.coverage.signals = 'AVAILABLE (TickStory signal joins)';
  if (vis > 0) (analysis.coverage as any).vision = 'AVAILABLE (VISION_EXPOSURE joins)';
  if (moves > 0 && analysis.coverage.cognition === 'NOT AVAILABLE') {
    analysis.coverage.cognition = 'AVAILABLE (MotorReceipt locomotion occupancy)';
  }

  // Phase 1: do not leave agent VISION as NOT AVAILABLE when reconstruction counted exposure ticks.
  analysis.agents = analysis.agents.map((a) => {
    const row = (histAgents as any)[a.agent_id];
    const n = Number(row?.visual_exposure_ticks ?? row?.legacy_body_visual_exposure_ticks ?? 0);
    if (!n) return a;
    const cur = a.vision?.foreign_body_exposure_ticks;
    const missing = cur == null || cur === 'NOT AVAILABLE';
    if (!missing) return a;
    return {
      ...a,
      vision: {
        ...(a.vision || {
          observed_exposure_episodes: 'NOT AVAILABLE',
          vision_only_episodes: 'NOT AVAILABLE',
          peak_body_optical_contribution: 'NOT AVAILABLE',
          exo_body_derived_delta: 'NOT AVAILABLE',
          next_action_observations: 'NOT AVAILABLE',
          cognition_linkage: 'NOT_ESTABLISHED',
        }),
        foreign_body_exposure_ticks: n,
        cognition_linkage: a.vision?.cognition_linkage || 'NOT_ESTABLISHED',
      },
    };
  });

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
