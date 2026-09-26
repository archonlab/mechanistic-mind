/**
 * Beta 2 M1–M24 measurement integrity fixtures (Analyzer-only).
 */
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  createAnalysisState,
  ingestAction,
  ingestXy,
  makeAgentAgg,
} from './aggregates.ts';
import { ingestAnalysisInput, buildRunAnalysis, analyzeObserverData } from './runAnalysis.ts';
import { buildAgentAnalyses } from './agentAnalysis.ts';
import {
  classifySequenceCoverage,
  resolveCognitionAggregate,
  resolveStreakReport,
  classifyPathVsVelocity,
} from './measurementIntegrity.ts';
import { buildConfigurationHistory } from './configurationHistory.ts';

function timelineFrom(
  rows: Array<{ tick: number; action: string; x: number; y: number; agent?: string }>,
) {
  return rows.map((r) => ({
    tick: r.tick,
    bodies: [{
      agent_id: r.agent || 'agent_0',
      action: r.action,
      x: r.x,
      y: r.y,
      speed: 0.01,
    }],
  }));
}

describe('M1–M6 action/streak integrity', () => {
  it('M1/M2 unique tick identity; duplicates do not inflate occupancy', () => {
    const state = createAnalysisState();
    state.map_w = 32;
    state.map_h = 32;
    const tl = timelineFrom([
      { tick: 1, action: 'WAIT', x: 1, y: 1 },
      { tick: 1, action: 'WAIT', x: 1, y: 1 }, // dup
      { tick: 2, action: 'WAIT', x: 1.01, y: 1 },
    ]);
    // Claim path uses claimTimelineAgentState — ingest twice via two batches
    ingestAnalysisInput(state, {
      frame: { header: { tick: 2, seed: 1, status: 'RUNNING' }, world: { width: 32, height: 32 } },
      timeline: tl,
      mode: 'LIVE',
    });
    const a = state.agents.agent_0;
    assert.equal(a.ticks, 2);
    assert.equal(a.action_counts.WAIT, 2);
  });

  it('M3/M5 sparse ticks are not consecutive; true streak NOT AVAILABLE', () => {
    const agg = makeAgentAgg('a', 'b');
    for (const t of [0, 2, 4, 6, 8]) {
      ingestAction(agg, 'WAIT', t);
    }
    assert.equal(agg.longest_wait_streak, 1);
    assert.equal(agg.action_counts.WAIT, 5);
    const cov = classifySequenceCoverage({
      uniqueTicks: 5,
      gapsSkipped: 4,
      startTick: 0,
      endTick: 8,
    });
    assert.equal(cov, 'SPARSE');
    const r = resolveStreakReport(agg.longest_wait_streak, cov, true);
    assert.equal(r.observed, 1);
    assert.equal(r.true, 'NOT AVAILABLE');
  });

  it('M4 COMPLETE_WAIT contiguous streak = 5', () => {
    const agg = makeAgentAgg('a', 'b');
    for (let t = 0; t <= 4; t++) ingestAction(agg, 'WAIT', t);
    assert.equal(agg.longest_wait_streak, 5);
    assert.equal(agg.action_counts.WAIT, 5);
    const cov = classifySequenceCoverage({
      uniqueTicks: 5, gapsSkipped: 0, startTick: 0, endTick: 4,
    });
    assert.equal(cov, 'CONTIGUOUS');
    const r = resolveStreakReport(5, cov, true);
    assert.equal(r.true, 5);
  });

  it('M6 MIXED_CONTIGUOUS streaks and occupancy', () => {
    const agg = makeAgentAgg('a', 'b');
    const seq = ['WAIT', 'WAIT', 'MOVE:E', 'MOVE:E', 'MOVE:E', 'WAIT', 'WAIT', 'WAIT', 'WAIT', 'WAIT'];
    seq.forEach((act, t) => ingestAction(agg, act, t));
    assert.equal(agg.longest_wait_streak, 5);
    assert.equal(agg.longest_move_streak, 3);
    assert.equal(agg.action_counts.WAIT, 7);
  });
});

describe('M7–M14 trajectory integrity', () => {
  it('M7 WRAP minimum-image', () => {
    const agg = makeAgentAgg('a', 'b');
    ingestXy(agg, 31.9, 10, 0, 1, 32, 32);
    ingestXy(agg, 0.1, 10, 0, 2, 32, 32);
    assert.ok(Math.abs(agg.path_length_euclidean - 0.2) < 1e-6);
  });

  it('M8/M9 net <= path; max_exc compatible (SHORT_LOCAL)', () => {
    const state = createAnalysisState();
    state.map_w = 32;
    state.map_h = 32;
    const rows = [];
    for (let t = 0; t < 10; t++) {
      rows.push({ tick: t, action: 'WAIT', x: 16 + t * 0.005, y: 16 });
    }
    ingestAnalysisInput(state, {
      frame: {
        header: { tick: 9, seed: 1, status: 'RUNNING', cognition_enabled: true },
        world: { width: 32, height: 32, boundary: 'WRAP_PERIODIC' },
      },
      timeline: timelineFrom(rows),
      mode: 'LIVE',
    });
    const built = buildAgentAnalyses(state)[0];
    const path = Number(built.movement.path_length_euclidean);
    const net = Number(built.movement.net_displacement);
    const exc = Number((built.movement as any).max_excursion_from_start);
    assert.ok(path < 0.1);
    assert.ok(net <= path + 1e-9);
    assert.ok(exc <= path + 1e-6);
    assert.ok(Number((built.movement as any).cell_boundary_crossings) <= 1);
  });

  it('M10 zero MOVE → zero MOVE-attributed path', () => {
    const state = createAnalysisState();
    state.map_w = 32;
    state.map_h = 32;
    const rows = [];
    for (let t = 0; t < 5; t++) rows.push({ tick: t, action: 'WAIT', x: 5 + t * 0.1, y: 5 });
    ingestAnalysisInput(state, {
      frame: { header: { tick: 4, seed: 1 }, world: { width: 32, height: 32 } },
      timeline: timelineFrom(rows),
      mode: 'LIVE',
    });
    const built = buildAgentAnalyses(state)[0];
    assert.equal(built.actions.move_count, 0);
    assert.equal((built.movement as any).path_during_requested_MOVE, 0);
  });

  it('M11 LIVE pose does not contaminate net', () => {
    const state = createAnalysisState();
    state.map_w = 32;
    state.map_h = 32;
    const rows = [];
    for (let t = 1; t <= 8; t++) {
      rows.push({ tick: t, action: 'WAIT', x: 16 + t * 0.01, y: 16 });
    }
    ingestAnalysisInput(state, {
      frame: {
        header: { tick: 100, seed: 17, status: 'RUNNING' },
        world: { width: 32, height: 32, boundary: 'WRAP_PERIODIC' },
        agents_observer: [{ observer_id: 'agent_0', x: 24.0, y: 8.0, vx: 0, vy: 0, prediction_count: 0 }],
      },
      timeline: timelineFrom(rows),
      mode: 'LIVE',
    });
    const built = buildAgentAnalyses(state)[0];
    const path = Number(built.movement.path_length_euclidean);
    const net = Number(built.movement.net_displacement);
    assert.ok(path < 0.2, `path ${path}`);
    assert.ok(net <= path + 1e-6, `net ${net} > path ${path}`);
    assert.ok(net < 1.0, `LIVE-poisoned net ${net}`);
  });

  it('M12/M13/M14 net definition; cell_cross not across gaps', () => {
    const agg = makeAgentAgg('a', 'b');
    ingestXy(agg, 1.2, 1.2, 0, 1, 32, 32);
    ingestXy(agg, 1.4, 1.2, 0, 2, 32, 32);
    ingestXy(agg, 20.5, 20.5, 0, 50, 32, 32); // gap — different cell
    assert.equal(agg.trajectory_gaps_skipped, 1);
    assert.equal(agg.cell_boundary_crossings, 0); // no invented gap crossing
    assert.ok(agg.unique_cells.size >= 2);
  });
});

describe('M15–M20 cognition / events / coverage', () => {
  it('M15 sparse → path_vs_velocity NOT_COMPARABLE', () => {
    const r = classifyPathVsVelocity({
      pathEuclid: 0.09,
      meanSpeed: 0.5,
      uniquePositionTicks: 100,
      gapsSkipped: 50,
      sequenceCoverage: 'SPARSE',
    });
    assert.equal(r.class, 'NOT_COMPARABLE_DUE_TO_COVERAGE');
  });

  it('M16 missing aggregate + structured events → NOT AVAILABLE', () => {
    const v = resolveCognitionAggregate(0, {
      structuredCognitiveEvidence: true,
      sequenceCoverage: 'SPARSE',
      cognitionEnabled: true,
    });
    assert.equal(v, 'NOT AVAILABLE');
  });

  it('M17 true zero cognition aggregate', () => {
    const v = resolveCognitionAggregate(0, {
      structuredCognitiveEvidence: false,
      sequenceCoverage: 'CONTIGUOUS',
      cognitionEnabled: true,
    });
    assert.equal(v, 0);
  });

  it('M18 structured events remain independent in report', () => {
    const state = createAnalysisState();
    state.cognition_enabled = true;
    state.map_w = 32;
    state.map_h = 32;
    const rows = [];
    for (let t = 0; t < 5; t++) rows.push({ tick: t * 2, action: 'WAIT', x: 1, y: 1 });
    ingestAnalysisInput(state, {
      frame: {
        header: { tick: 8, seed: 1, status: 'RUNNING', cognition_enabled: true },
        world: { width: 32, height: 32 },
        agents_observer: [{
          observer_id: 'agent_0', x: 1, y: 1, prediction_count: 0, prospective_compositions: 0,
        }],
      },
      timeline: timelineFrom(rows),
      events: [
        { type: 'SCENARIO_SELECTED', tick: 2, agent_id: 'agent_0', evidence: { selected_action: 'WAIT' } },
        { type: 'SCENARIO_SELECTED', tick: 4, agent_id: 'agent_0', evidence: { selected_action: 'WAIT' } },
      ],
      mode: 'LIVE',
    });
    const analysis = buildRunAnalysis(state, 'LIVE');
    const a0 = analysis.agents[0];
    assert.ok(Number(a0.cognition.scenario_selected) >= 2);
    assert.equal(a0.cognition.prediction_count, 'NOT AVAILABLE');
    assert.match(analysis.analysis_log, /COGNITION AGGREGATES/);
    assert.match(analysis.analysis_log, /STRUCTURED COGNITIVE EVENTS/);
  });

  it('M19 FIRST OBSERVED MOVE labeling', () => {
    const analysis = analyzeObserverData({
      frame: { header: { tick: 3, seed: 1 }, world: { width: 32, height: 32 } },
      timeline: timelineFrom([
        { tick: 1, action: 'WAIT', x: 1, y: 1 },
        { tick: 2, action: 'MOVE:E', x: 1.2, y: 1 },
      ]),
      mode: 'LIVE',
    });
    const first = analysis.important_events.find((e) => e.kind === 'FIRST_MOVE');
    assert.ok(first);
    assert.match(first!.title, /FIRST OBSERVED MOVE/);
  });

  it('M20 sustained requires consecutive ticks (gap resets)', () => {
    const agg = makeAgentAgg('a', 'b');
    for (let t = 0; t < 15; t++) ingestAction(agg, 'WAIT', t);
    assert.equal(agg.wait_streak, 15);
    ingestAction(agg, 'WAIT', 20); // gap
    assert.equal(agg.wait_streak, 1);
  });
});

describe('M21–M22 multi-regime + fixtures export shape', () => {
  it('M21/M22 MULTI_REGIME boundaries survive', () => {
    const report = buildConfigurationHistory([
      {
        type: 'WORLD_INTERVENTION',
        event_id: '1',
        simulation_tick: 100,
        category: 'ecology',
        changes: { a: { old: 1, new: 2 } },
        effective_world_fingerprint_before: 'A',
        effective_world_fingerprint_after: 'B',
        history_reset: false,
        cognition_reset: false,
        body_reset: false,
      },
    ], { start_tick: 0, end_tick: 200, initial_fingerprint: 'A' });
    assert.equal(report.configuration_history, 'MULTI_REGIME');
    assert.equal(report.interventions[0].tick, 100);
    assert.equal(report.n_regimes, 2);
  });
});
