import assert from 'node:assert/strict';
import test from 'node:test';
import {
  ANALYZER_EXPORT_SCHEMA,
  buildAnalyzerExportBundle,
  exportFilenames,
  formatJsonExport,
  formatMarkdownReport,
} from './analyzerExport.ts';
import type { RunAnalysis } from './types.ts';

function stubAnalysis(overrides: Partial<RunAnalysis> = {}): RunAnalysis {
  const base: RunAnalysis = {
    identity: {
      runtime: 'TwoAgentRuntime',
      seed: 1,
      generation: 7,
      map_width: 32,
      map_height: 32,
      boundary: 'WRAP',
      start_tick: 0,
      end_tick: 10,
      duration_ticks: 10,
      agent_count: 1,
      agents: [{ agent_id: 'agent_0', body_id: 'body-0', seed: 1 }],
      cognition_enabled: true,
      experimental_overrides: {},
      active_mechanisms: [],
      status: 'STOPPED',
      analysis_mode: 'FINAL',
    },
    lifecycle: {
      phase: 'COMPLETE',
      banner: 'ANALYSIS: COMPLETE',
      analyzed_start: 0,
      analyzed_end: 10,
      live_runtime_tick: null,
      agents: 1,
      events_observed: 3,
      frames_sampled: 0,
      coverage: 'COMPLETE',
      coverage_reason: 'test',
      insufficient: false,
    },
    agents: [],
    comparison: null,
    interactions: {
      first_contact_tick: 'NOT AVAILABLE',
      contact_ticks: 0,
      contact_episodes: [],
      contact_triggered_emissions: 0,
      cross_agent_contributions: 0,
      causal_snippets: [],
      notes: [],
    } as any,
    important_events: [],
    causal_chains: [],
    phases: [],
    overview: [],
    keyframes: [],
    coverage: {
      level: 'COMPLETE',
      reason: 'test',
      unique_simulation_ticks: 11,
      timeline_samples: 11,
      body: 'NOT AVAILABLE',
      cognition: 'NOT AVAILABLE',
      signals: 'NOT AVAILABLE',
      resources: 'NOT AVAILABLE',
    } as any,
    analysis_log: 'MECHANISTIC MIND — RUN ANALYSIS\n',
    generated_at_tick: 10,
    evidence_meta: {
      analyzer_version: 'test',
      analysis_timestamp: '2026-01-01T00:00:00Z',
      run_id: 'psyweb-test-run',
      runtime_status: 'STOPPED',
      analysis_cutoff_tick: 10,
      scientific_tick_range: [0, 10],
      coverage: 'COMPLETE',
      complete_tick_level_reanalysis: true,
      evidence_files: ['scientific_timeline.jsonl'],
      evidence_counts: { scientific_timeline: 11 },
      used_cumulative_runtime_summaries: false,
      cumulative_runtime_summaries: [],
      source: 'saved',
      note: null,
    },
  };
  return { ...base, ...overrides };
}

test('markdown and json export deterministic identity', () => {
  const a = stubAnalysis();
  const md1 = formatMarkdownReport(a);
  const md2 = formatMarkdownReport(a);
  assert.equal(md1, md2);
  assert.match(md1, /export_schema: mm\.analyzer\.export\.v2/);
  assert.match(md1, /analysis_source: saved/);
  assert.match(md1, /run_id: psyweb-test-run/);
  assert.match(md1, /NOT AVAILABLE|MECHANISTIC MIND/);

  const j1 = formatJsonExport(a);
  const j2 = formatJsonExport(a);
  assert.equal(j1, j2);
  const parsed = JSON.parse(j1);
  assert.equal(parsed.export_schema, ANALYZER_EXPORT_SCHEMA);
  assert.equal(parsed.identity.generation, 7);
  assert.equal(parsed.evidence_meta.run_id, 'psyweb-test-run');
});

test('copy markdown equals formatMarkdownReport content', () => {
  const a = stubAnalysis();
  const bundle = buildAnalyzerExportBundle(a);
  assert.equal(bundle.analysis_log_markdown, formatMarkdownReport(a));
  assert.equal(bundle.analysis_source, 'saved');
  assert.equal(bundle.run_id, 'psyweb-test-run');
});

test('filenames sanitized', () => {
  const a = stubAnalysis();
  const names = exportFilenames(a);
  assert.match(names.md, /^mechanistic-mind-analysis-psyweb-test-run-10\.md$/);
  assert.match(names.json, /\.json$/);
});

test('export controls gating helpers', async () => {
  const fs = await import('node:fs');
  const path = await import('node:path');
  const text = fs.readFileSync(
    path.join(path.dirname(new URL(import.meta.url).pathname), '../components/AnalyzeResultsPanel.tsx'),
    'utf8',
  );
  for (const id of [
    'analyzer-copy-report',
    'analyzer-save-markdown',
    'analyzer-save-json',
    'analyzer-status-failed',
    'analyzer-status-idle',
    'analyzer-status-running',
  ]) {
    assert.match(text, new RegExp(id));
  }
  assert.match(text, /ANALYSIS: FAILED/);
  assert.match(text, /ANALYSIS: IDLE/);
  assert.doesNotMatch(text, /ANALYSIS: waiting/);
});
