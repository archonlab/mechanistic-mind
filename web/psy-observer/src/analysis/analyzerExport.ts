/** Deterministic Analyzer export from completed structured RunAnalysis (not DOM scrape). */

import type { RunAnalysis } from './types.ts';
import { formatAnalysisLog } from './analysisLog.ts';

export const ANALYZER_EXPORT_SCHEMA = 'mm.analyzer.export.v2';
export const ANALYZER_EXPORT_VERSION = 2;

export type AnalyzerExportBundle = {
  export_schema: string;
  export_version: number;
  generated_at: string;
  analysis_source: string | null;
  run_id: string | null;
  runtime_generations: Array<number | null>;
  public_model: string | null;
  model_line: string | null;
  analysis_cutoff: number | null;
  analyzer_job_status: 'COMPLETE' | 'PARTIAL' | 'FAILED' | 'IDLE';
  evidence_inventory: string[];
  evidence_schemas: string[];
  warnings: string[];
  limitations: string[];
  identity: RunAnalysis['identity'];
  lifecycle: RunAnalysis['lifecycle'];
  evidence_meta: RunAnalysis['evidence_meta'] | null;
  coverage: RunAnalysis['coverage'];
  volumetric_physical_causal: any | null;
  scientific_v3_summary: any | null;
  signal_context: any | null;
  counts: Record<string, number>;
  analysis_log_markdown: string;
  /** Exact structured snapshot for JSON export (no UI state). */
  structured: Record<string, unknown>;
};

function sanitizeFilenamePart(s: string): string {
  return String(s || 'unknown')
    .replace(/[^a-zA-Z0-9._-]+/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_|_$/g, '')
    .slice(0, 120) || 'unknown';
}

export function exportFilenames(analysis: RunAnalysis): { md: string; json: string } {
  const meta = analysis.evidence_meta;
  const runId = sanitizeFilenamePart(meta?.run_id || analysis.identity.runtime || 'current-run');
  const cutoff = meta?.analysis_cutoff_tick ?? analysis.identity.end_tick ?? 'na';
  const base = `mechanistic-mind-analysis-${runId}-${cutoff}`;
  return { md: `${base}.md`, json: `${base}.json` };
}

function buildRuntimeRegimes(analysis: RunAnalysis): Record<string, unknown> {
  const psc = (analysis as any).psc_regime || {};
  const eff = psc.effective_runtime_state || {};
  const cfg = psc.configured_schedule || {};
  const regimes = (psc.regimes || []).map((r: any) => ({
    tick_start: r.tick_start,
    tick_end: r.tick_end,
    ticks: r.ticks,
    effective_state: r.effective_psc,
    withhold_gate: String(r.smc_withhold || '').includes('OPEN')
      ? 'OPEN'
      : (String(r.smc_withhold || '').includes('CLOSED') ? 'CLOSED' : r.smc_withhold),
    smc_withhold: r.smc_withhold,
  }));
  return {
    psc: {
      initial_state: eff.initially_off ? 'OFF' : 'UNKNOWN',
      scheduled_tick: cfg.psc_off_ticks ?? null,
      enabled_at_tick: eff.enabled_at_tick ?? null,
      transition_count: eff.transition_count ?? null,
      provenance: [
        'scientific_decisions.jsonl',
        'physical_system_snapshot.json#psc_schedule',
      ],
      regimes,
    },
    world_intervention_configuration: {
      configuration_history: analysis.configuration_history?.configuration_history ?? 'STATIC',
      n_interventions: analysis.configuration_history?.n_interventions ?? 0,
      note: 'WORLD_INTERVENTION layer — not PSC mechanism regime history',
      authority_layer: 'WORLD_INTERVENTION',
    },
  };
}

export function buildAnalyzerExportBundle(analysis: RunAnalysis): AnalyzerExportBundle {
  const meta = analysis.evidence_meta || null;
  const vpc = (analysis as any).volumetric_physical_causal_reconstruction
    || (analysis as any).volumetric_physical_causal
    || (analysis as any).behavioral_reconstruction?.volumetric_physical_causal_reconstruction
    || null;
  const sci = (analysis as any).scientific_v3_core
    || (analysis as any).scientific_v3
    || null;
  const signal = (analysis as any).signal_context
    || (analysis as any).signal_conditioned_sensorimotor_selection
    || null;
  const warnings: string[] = [];
  const limitations: string[] = [];
  if (meta && !meta.complete_tick_level_reanalysis) {
    limitations.push('Complete tick-level re-analysis: NO (PARTIAL reconstruction)');
  }
  if (meta?.used_cumulative_runtime_summaries) {
    warnings.push('Cumulative runtime summaries are not tick-level history');
  }
  const markdown = formatMarkdownReport(analysis);
  const complete = Number((sci as any)?.complete_odmc_count || (sci as any)?.decision_receipts || 0);
  const expected = Number((sci as any)?.ticks_expected || complete || 0);
  const epContact = Number((analysis.interactions as any).reconstructed_contact_episode_count
    ?? (analysis as any).episode_counts?.CONTACT
    ?? null);
  const runtimeStatus = meta?.runtime_status || analysis.identity.status || null;

  const structured: Record<string, unknown> = (analysis as any).export_json || {
    export_schema: ANALYZER_EXPORT_SCHEMA,
    export_version: ANALYZER_EXPORT_VERSION,
    run_identity: {
      ...analysis.identity,
      runtime_status: runtimeStatus,
      status: analysis.identity.status,
    },
    identity: analysis.identity,
    lifecycle: analysis.lifecycle,
    evidence_meta: { ...meta, runtime_status: runtimeStatus },
    evidence_inventory: meta?.evidence_files || [],
    layered_coverage: (analysis as any).layered_coverage || null,
    runtime_regimes: buildRuntimeRegimes(analysis),
    counts_and_units: {
      unique_simulation_ticks: analysis.coverage.unique_simulation_ticks || 0,
      agent_ticks: expected || null,
      complete_odmc_chains: complete,
      expected_odmc_chains: expected,
      incomplete_odmc_chains: Math.max(0, expected - complete),
    },
    per_agent_action: Object.fromEntries(
      analysis.agents.map((a) => [a.agent_id, {
        wait_count: a.actions.wait_count,
        move_count: a.actions.move_count,
        longest_wait_streak: a.actions.longest_wait_streak,
        longest_move_streak: a.actions.longest_move_streak,
        action_transitions: a.actions.action_transitions,
        ticks_observed: a.ticks_observed,
        unit: 'agent-ticks',
      }]),
    ),
    interactions: {
      body_body_contact_ticks: analysis.interactions.contact_ticks,
      reconstructed_contact_episode_count: Number.isFinite(epContact) ? epContact : null,
      reconstructed_contact_episode_class: 'CONTACT',
      contact_authority: (analysis.interactions as any).contact_authority || 'mixed',
      contact_semantics: (analysis.interactions as any).contact_semantics
        || 'CONTACT episodes ≠ Observer timeline body-body contact_ticks',
      contact_episodes: analysis.interactions.contact_episodes,
      notes: analysis.interactions.notes,
    },
    vision_summary: (analysis as any).beta31_vision_summary || analysis.vision_forensics || null,
    signal_context: signal ?? {
      status: 'NOT_AVAILABLE',
      omission_reason: 'signal_context not attached to RunAnalysis',
    },
    volumetric_physical_causal: vpc,
    scientific_v3: sci,
    ontology_boundaries: {
      resource_entities: {
        classification: 'DEVELOPMENT_FIXTURE',
        present_in_runtime: true,
        claimed_canonical: false,
        runtime_effects_included: true,
        replacement_scope: 'future Ecology + spherical-world + Causality Generator',
        replacement_requires_new_fingerprint_and_revalidation: true,
      },
    },
    causal_chains: {
      status: complete > 0 && complete === expected ? 'FULL' : (complete > 0 ? 'PARTIAL' : 'UNAVAILABLE'),
      expected_agent_ticks: expected,
      complete_chains: complete,
      incomplete_chains: Math.max(0, expected - complete),
      details_inlined: false,
      external_artifact: 'analysis_tick_stories.jsonl',
      schema: 'SCIENTIFIC_V3 TickStory O→D→M→C',
      inline_legacy_frontend_chains: analysis.causal_chains,
    },
    keyframes: {
      status: analysis.keyframes.length ? 'POPULATED' : 'NOT_POPULATED_IN_COMPACT_ANALYZER_NEXT_EXPORT',
      items: analysis.keyframes,
    },
    phases: {
      status: analysis.phases.length ? 'POPULATED' : 'NOT_POPULATED_IN_COMPACT_ANALYZER_NEXT_EXPORT',
      items: analysis.phases,
    },
    configuration_history: analysis.configuration_history ?? null,
    coverage: analysis.coverage,
    agents: analysis.agents,
    comparison: analysis.comparison,
    important_events: analysis.important_events,
    overview: analysis.overview,
    composite_motor: (analysis as any).composite_motor ?? null,
    generated_at_tick: analysis.generated_at_tick,
    limitations: [
      'CORE FULL ≠ complete auxiliary coverage',
      'World-intervention STATIC ≠ PSC regime history',
      'Detailed ODMC chains externalized to analysis_tick_stories.jsonl',
    ],
  };

  return {
    export_schema: ANALYZER_EXPORT_SCHEMA,
    export_version: ANALYZER_EXPORT_VERSION,
    generated_at: new Date().toISOString(),
    analysis_source: meta?.source ?? null,
    run_id: meta?.run_id ?? null,
    runtime_generations: [analysis.identity.generation],
    public_model: null,
    model_line: null,
    analysis_cutoff: meta?.analysis_cutoff_tick ?? null,
    analyzer_job_status: meta?.complete_tick_level_reanalysis ? 'COMPLETE' : 'PARTIAL',
    evidence_inventory: meta?.evidence_files || [],
    evidence_schemas: Object.keys(meta?.evidence_counts || {}),
    warnings,
    limitations,
    identity: analysis.identity,
    lifecycle: analysis.lifecycle,
    evidence_meta: meta,
    coverage: analysis.coverage,
    volumetric_physical_causal: vpc,
    scientific_v3_summary: sci,
    signal_context: signal,
    counts: {
      agents: analysis.agents.length,
      important_events: analysis.important_events.length,
      complete_odmc_chains: complete,
      phases: analysis.phases.length,
      unique_simulation_ticks: analysis.coverage.unique_simulation_ticks || 0,
      reconstructed_contact_episodes: Number.isFinite(epContact) ? epContact : 0,
    },
    analysis_log_markdown: markdown,
    structured,
  };
}

/** Deterministic Markdown from structured completed result (same content as COPY REPORT). */
export function formatMarkdownReport(analysis: RunAnalysis): string {
  const body = formatAnalysisLog(analysis);
  if (body.includes('END OF ANALYZER REPORT')) {
    // Authoritative complete report already includes export integrity footer.
    const meta = analysis.evidence_meta;
    const header = [
      '# Mechanistic Mind — Analyzer Report',
      '',
      `- export_schema: ${ANALYZER_EXPORT_SCHEMA}`,
      `- export_version: ${ANALYZER_EXPORT_VERSION}`,
      `- analysis_source: ${meta?.source ?? 'NOT_AVAILABLE'}`,
      `- run_id: ${meta?.run_id ?? 'NOT_AVAILABLE'}`,
      `- cutoff: ${meta?.analysis_cutoff_tick ?? analysis.identity.end_tick}`,
      `- generation: ${analysis.identity.generation ?? 'NOT_AVAILABLE'}`,
      `- status: ${analysis.lifecycle.banner || analysis.identity.status}`,
      '',
      '---',
      '',
    ].join('\n');
    return `${header}${body}`;
  }
  const meta = analysis.evidence_meta;
  const header = [
    '# Mechanistic Mind — Analyzer Report',
    '',
    `- export_schema: ${ANALYZER_EXPORT_SCHEMA}`,
    `- export_version: ${ANALYZER_EXPORT_VERSION}`,
    `- analysis_source: ${meta?.source ?? 'NOT_AVAILABLE'}`,
    `- run_id: ${meta?.run_id ?? 'NOT_AVAILABLE'}`,
    `- cutoff: ${meta?.analysis_cutoff_tick ?? analysis.identity.end_tick}`,
    `- generation: ${analysis.identity.generation ?? 'NOT_AVAILABLE'}`,
    `- status: ${analysis.lifecycle.banner || analysis.identity.status}`,
    '',
    '---',
    '',
  ].join('\n');
  return `${header}${body}`;
}

export function formatJsonExport(analysis: RunAnalysis): string {
  const bundle = buildAnalyzerExportBundle(analysis);
  return `${JSON.stringify(bundle.structured, null, 2)}\n`;
}

export function downloadBlob(filename: string, mime: string, text: string): void {
  const blob = new Blob([text], { type: mime });
  const url = URL.createObjectURL(blob);
  try {
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.rel = 'noopener';
    document.body.appendChild(a);
    a.click();
    a.remove();
  } finally {
    URL.revokeObjectURL(url);
  }
}
