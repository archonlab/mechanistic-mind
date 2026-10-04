import assert from 'node:assert/strict';
import test from 'node:test';
import { formatAnalysisLog } from './analysisLog.ts';
import type { RunAnalysis } from './types.ts';

test('truthful markdown short-circuit and evidence files never NONE when streams exist', () => {
  const a = {
    identity: { runtime: 'UNKNOWN', seed: null, generation: null, map_width: null, map_height: null, boundary: 'NOT AVAILABLE', start_tick: 0, end_tick: 1, duration_ticks: 1, agent_count: 2, agents: [], cognition_enabled: 'NOT AVAILABLE', experimental_overrides: {}, active_mechanisms: [], status: 'UNKNOWN', analysis_mode: 'FINAL' },
    lifecycle: { phase: 'COMPLETE', banner: 'ANALYSIS COMPLETE — CORE CHAINS FULL, AUXILIARY COVERAGE PARTIAL', analyzed_start: 0, analyzed_end: 1122, live_runtime_tick: null, agents: 2, events_observed: 0, frames_sampled: 0, coverage: 'COMPLETE', coverage_reason: 'core', insufficient: false },
    agents: [],
    comparison: null,
    interactions: { first_contact_tick: 'NOT AVAILABLE', contact_ticks: 0, contact_episodes: [], contact_triggered_emissions: 0, cross_agent_contributions: 0, causal_snippets: [], notes: [] },
    important_events: [],
    causal_chains: [],
    phases: [],
    overview: [],
    keyframes: [],
    coverage: { world: 'PARTIAL', body: 'AVAILABLE', cognition: 'AVAILABLE', signals: 'PARTIAL', causal_provenance: 'PARTIAL', timeline_samples: 0, unique_simulation_ticks: 1123, event_samples: 0, telemetry_samples: 0, level: 'COMPLETE', reason: 'core' },
    analysis_log: '',
    generated_at_tick: 1122,
    evidence_meta: {
      analyzer_version: '1.2.0',
      analysis_timestamp: 'x',
      run_id: 'psyweb-test',
      runtime_status: 'STOPPED',
      analysis_cutoff_tick: 1122,
      scientific_tick_range: [0, 1122],
      coverage: 'CORE_FULL_AUX_PARTIAL',
      complete_tick_level_reanalysis: true,
      evidence_files: ['scientific_decisions.jsonl', 'run.json'],
      evidence_counts: { tick_stories: 2246 },
      used_cumulative_runtime_summaries: false,
      cumulative_runtime_summaries: [],
      source: 'saved',
      note: null,
    },
  } as unknown as RunAnalysis;
  (a as any).truthful_markdown = 'ACANTHOSTEGA BETA 4 VISION ANALYSIS\nDEVELOPMENT FIXTURES / ONTOLOGY BOUNDARY\nresource-*';
  const text = formatAnalysisLog(a);
  assert.match(text, /ACANTHOSTEGA BETA 4 VISION ANALYSIS/);
  assert.doesNotMatch(text, /Evidence files: NONE/);
  assert.match(text, /DEVELOPMENT FIXTURES/);
});
