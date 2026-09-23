/**
 * Scientific evidence package + FULL/PARTIAL Analyzer regression tests.
 */
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  analyzeEvidencePackage,
  reanalyzeEvidence,
  scientificCoreFingerprint,
} from './scientificEvidence.ts';
import { analyzeObserverData } from './runAnalysis.ts';

function makeFullPkg(nTicks: number, agents = 2) {
  const scientific_rows: any[] = [];
  for (let t = 1; t <= nTicks; t++) {
    for (let a = 0; a < agents; a++) {
      scientific_rows.push({
        tick: t,
        agent_id: `agent_${a}`,
        body_id: `body-${a}`,
        action: a === 0 && t % 5 === 0 ? 'MOVE:N' : 'WAIT',
        action_source: 'FALLBACK',
        x: a,
        y: t * 0.01,
        contact: false,
        work: 1,
        resource_A: 10,
        resource_B: 10,
        agent_seed: 88 + a,
      });
    }
  }
  const timeline: any[] = [];
  for (let t = 1; t <= nTicks; t++) {
    timeline.push({
      tick: t,
      contact: false,
      bodies: scientific_rows.filter((r) => r.tick === t).map((r) => ({
        agent_id: r.agent_id,
        x: r.x,
        y: r.y,
        action: r.action,
        action_source: r.action_source,
      })),
      source: 'scientific_timeline',
    });
  }
  return {
    analyzer_version: '1.1.0',
    run_id: 'psyweb-test',
    source: 'saved',
    runtime_status: 'STOPPED',
    analysis_cutoff_tick: nTicks,
    scientific_tick_range: [1, nTicks] as [number, number],
    coverage: 'FULL',
    coverage_detail: {
      coverage: 'FULL',
      complete_tick_level_reanalysis: true,
      reason: 'complete',
      scientific_timeline_available: `1–${nTicks}`,
    },
    complete_tick_level_reanalysis: true,
    evidence_files: ['scientific_timeline.jsonl'],
    evidence_counts: { scientific_rows: scientific_rows.length, timeline_events: timeline.length, events: 0 },
    identity: { runtime_type: 'TwoAgentRuntime', seed: 88, agent_count: agents },
    timeline,
    scientific_rows,
    events: [],
    cumulative_runtime_summaries: [],
    used_cumulative_runtime_summaries: false,
  };
}

describe('scientific evidence Analyzer', () => {
  it('TEST4: saved full run → Coverage FULL', () => {
    const pkg = makeFullPkg(50);
    const a = analyzeEvidencePackage(pkg);
    assert.equal(a.evidence_meta?.coverage, 'FULL');
    assert.equal(a.evidence_meta?.complete_tick_level_reanalysis, true);
    assert.ok((a.coverage.unique_simulation_ticks || 0) >= 50);
  });

  it('TEST5: legacy partial → PARTIAL, no full claim', () => {
    const timeline = [];
    for (let t = 19875; t <= 19900; t++) {
      timeline.push({
        tick: t,
        contact: false,
        bodies: [
          { agent_id: 'agent_0', x: 1, y: 1, action: 'WAIT' },
          { agent_id: 'agent_1', x: 2, y: 2, action: 'WAIT' },
        ],
      });
    }
    const pkg = {
      coverage: 'PARTIAL',
      coverage_detail: {
        reason: 'No scientific_timeline.jsonl; only bounded session_timeline',
        scientific_timeline_available: '19875–19900',
        full_runtime_cumulative_counters_available: true,
        complete_tick_level_reanalysis: false,
      },
      complete_tick_level_reanalysis: false,
      analysis_cutoff_tick: 23970,
      scientific_tick_range: [19875, 19900] as [number, number],
      runtime_status: 'STOPPED',
      timeline,
      events: [],
      evidence_files: ['session_timeline.jsonl'],
      cumulative_runtime_summaries: [
        { agent_id: 'agent_0', action_counts: { WAIT: 10000 }, evidence_class: 'CUMULATIVE_RUNTIME_SUMMARY' },
      ],
      used_cumulative_runtime_summaries: true,
      identity: { agent_count: 2, seed: 88, runtime_type: 'TwoAgentRuntime' },
    };
    const a = analyzeEvidencePackage(pkg);
    assert.equal(a.evidence_meta?.coverage, 'PARTIAL');
    assert.equal(a.evidence_meta?.complete_tick_level_reanalysis, false);
    assert.ok(a.analysis_log.includes('PARTIAL') || a.analysis_log.includes('Complete tick-level re-analysis: NO'));
    assert.ok(a.analysis_log.includes('CUMULATIVE') || a.evidence_meta?.used_cumulative_runtime_summaries);
  });

  it('TEST6: cumulative exposed separately, not as tick history in log', () => {
    const pkg = makeFullPkg(10);
    pkg.cumulative_runtime_summaries = [
      { agent_id: 'agent_0', action_counts: { WAIT: 9999 }, evidence_class: 'CUMULATIVE_RUNTIME_SUMMARY' },
    ];
    pkg.used_cumulative_runtime_summaries = true;
    const a = analyzeEvidencePackage(pkg);
    // Tick-level WAIT for agent_0 from scientific rows is ~8-10, not 9999
    const a0 = a.agents.find((x) => x.agent_id === 'agent_0');
    assert.ok(a0);
    assert.notEqual(a0!.actions.wait_count, 9999);
    assert.ok(a.analysis_log.includes('NOT tick-level'));
  });

  it('TEST7: repeated re-analysis identical core fingerprint', () => {
    const pkg = makeFullPkg(30);
    const a = reanalyzeEvidence(pkg);
    const b = reanalyzeEvidence(pkg);
    assert.equal(scientificCoreFingerprint(a), scientificCoreFingerprint(b));
  });

  it('TEST9: LIVE-style ingest vs evidence package agree on tick metrics', () => {
    const pkg = makeFullPkg(40);
    const offline = analyzeEvidencePackage(pkg);
    const live = analyzeObserverData({
      timeline: pkg.timeline,
      events: [],
      mode: 'FINAL',
      scientificEvidence: true,
      skipLiveCumulativeActions: true,
      frame: {
        header: {
          tick: 40,
          status: 'STOPPED',
          seed: 88,
          runtime_model: 'TwoAgentRuntime',
          agent_count: 2,
        },
      },
    });
    assert.equal(
      offline.agents.find((x) => x.agent_id === 'agent_0')?.actions.wait_count,
      live.agents.find((x) => x.agent_id === 'agent_0')?.actions.wait_count,
    );
    assert.equal(
      offline.agents.find((x) => x.agent_id === 'agent_1')?.actions.move_count,
      live.agents.find((x) => x.agent_id === 'agent_1')?.actions.move_count,
    );
  });

  it('cutoff metadata present for running status', () => {
    const pkg = makeFullPkg(20);
    pkg.runtime_status = 'RUNNING';
    pkg.analysis_cutoff_tick = 20;
    const a = analyzeEvidencePackage(pkg);
    assert.equal(a.evidence_meta?.analysis_cutoff_tick, 20);
    assert.equal(a.evidence_meta?.runtime_status, 'RUNNING');
    assert.ok(a.analysis_log.includes('Runtime status: RUNNING'));
    assert.ok(a.analysis_log.includes('Analysis cutoff tick: 20'));
  });

  it('FULL metadata with zero consumed ticks is not FULL', () => {
    const pkg = {
      coverage: 'FULL',
      complete_tick_level_reanalysis: true,
      scientific_tick_range: [1, 2034] as [number, number],
      analysis_cutoff_tick: 2034,
      runtime_status: 'PAUSED',
      evidence_counts: { scientific_rows: 4068, timeline_events: 0, events: 0 },
      timeline: [],
      events: [],
      scientific_rows: [],
      scientific_v3_core: null,
      behavioral_reconstruction: null,
      identity: { agent_count: 2, seed: 177, runtime_type: 'TwoAgentRuntime' },
    };
    const a = analyzeEvidencePackage(pkg, {
      frame: { header: { tick: 2034, status: 'PAUSED', agent_count: 2 } },
    });
    assert.notEqual(a.evidence_meta?.coverage, 'FULL');
    assert.equal(a.evidence_meta?.complete_tick_level_reanalysis, false);
    assert.equal(a.coverage.unique_simulation_ticks, 0);
    assert.equal(a.identity.start_tick, 1);
    assert.equal(a.identity.end_tick, 2034);
    assert.equal((a.coverage as any).runtime_span, '1–2034');
    assert.match(a.analysis_log, /NOT_AVAILABLE/);
    assert.match(a.analysis_log, /SCIENTIFIC_V3 CORE RECONSTRUCTION[\s\S]*NOT_RECORDED/);
  });

  it('Analyze Current job summary reconstructs ticks without scientific_rows', () => {
    const pkg = {
      coverage: 'FULL',
      complete_tick_level_reanalysis: true,
      unique_simulation_ticks: 2034,
      scientific_tick_range: [1, 2034] as [number, number],
      analysis_cutoff_tick: 2034,
      tick_stories_count: 4068,
      complete_odmc_count: 4068,
      complete_odmc: '4068 / 4068',
      runtime_status: 'PAUSED',
      timeline: [],
      events: [],
      scientific_rows: [],
      canonical_history: {
        unique_simulation_ticks: 2034,
        tick_min: 1,
        tick_max: 2034,
        scientific_tick_range: [1, 2034],
        agents: {
          agent_0: {
            ticks_observed: 2034, wait_count: 1000, move_count: 1034,
            move_distribution: { 'MOVE:E': 1034 }, pose_ticks: 2034,
            signal_emissions: 10, signal_receptions: 12, visual_exposure_ticks: 8,
          },
          agent_1: {
            ticks_observed: 2034, wait_count: 900, move_count: 1134,
            move_distribution: { 'MOVE:W': 1134 }, pose_ticks: 2034,
            signal_emissions: 11, signal_receptions: 9, visual_exposure_ticks: 7,
          },
        },
      },
      join_summary: { event_ticks_indexed: 40, vision_joins: 15, signal_joins: 20 },
      scientific_v3_core: {
        evidence_version: 'SCIENTIFIC_V3',
        status: 'AVAILABLE',
        decision_receipts: 4068,
        complete_odmc_chains: '4068 / 4068',
        complete_odmc_count: 4068,
        tick_range: [1, 2034],
      },
      behavioral_reconstruction: {
        status: 'AVAILABLE',
        report_text: 'BEHAVIORAL RECONSTRUCTION\nstatus: AVAILABLE\n',
        tick_stories_count: 4068,
        complete_odmc: '4068 / 4068',
      },
      identity: { agent_count: 2, runtime_type: 'TwoAgentRuntime' },
    };
    const a = analyzeEvidencePackage(pkg, {
      frame: { header: { tick: 2034, status: 'PAUSED', agent_count: 2 } },
    });
    assert.equal(a.evidence_meta?.coverage, 'FULL');
    assert.equal(a.coverage.unique_simulation_ticks, 2034);
    assert.equal(a.identity.start_tick, 1);
    assert.equal(a.identity.end_tick, 2034);
    assert.equal((a.coverage as any).runtime_span, '1–2034');
    const a0 = a.agents.find((x) => x.agent_id === 'agent_0');
    assert.ok(Number(a0?.actions.move_count) > 0);
    assert.ok(a.analysis_log.includes('BEHAVIORAL RECONSTRUCTION'));
    assert.ok(a.analysis_log.includes('DecisionReceipts: 4068') || a.analysis_log.includes('4068 / 4068'));
    assert.equal(String(a0?.movement.unique_cells), 'NOT AVAILABLE');
    assert.equal(String(a0?.movement.distance_travelled), 'NOT AVAILABLE');
  });

  it('canonical_history path metrics populate movement instead of misleading zeros', () => {
    const pkg = {
      coverage: 'FULL',
      complete_tick_level_reanalysis: true,
      unique_simulation_ticks: 10,
      scientific_tick_range: [1, 10] as [number, number],
      timeline: [],
      scientific_rows: [],
      canonical_history: {
        unique_simulation_ticks: 10,
        scientific_tick_range: [1, 10],
        agents: {
          agent_0: {
            ticks_observed: 10,
            wait_count: 2,
            move_count: 8,
            move_distribution: { 'MOVE:E': 8 },
            pose_ticks: 10,
            distance_manhattan_wrap: 4.5,
            path_length_euclidean: 3.2,
            unique_cells: 7,
            path_available: true,
          },
        },
      },
      identity: { agent_count: 1, runtime_type: 'TwoAgentRuntime' },
    };
    const a = analyzeEvidencePackage(pkg as any);
    const a0 = a.agents.find((x) => x.agent_id === 'agent_0');
    assert.equal(Number(a0?.movement.distance_travelled), 4.5);
    assert.equal(Number((a0?.movement as any).path_length_euclidean), 3.2);
    assert.equal(Number(a0?.movement.unique_cells), 7);
  });
});
