/**
 * Tick-level action occupancy vs selection-event / cumulative accounting.
 */
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  analyzeObserverData,
  buildRunAnalysis,
  ingestAnalysisInput,
} from './runAnalysis.ts';
import { createAnalysisState, ingestAction, makeAgentAgg } from './aggregates.ts';
import { analyzeEvidencePackage, reanalyzeEvidence, scientificCoreFingerprint } from './scientificEvidence.ts';

function frameAt(tick: number, extra: any = {}) {
  return {
    header: {
      tick,
      seed: 88,
      runtime_generation: 1,
      runtime_model: 'TwoAgentRuntime',
      status: 'RUNNING',
      agent_count: 2,
      agent_body_mapping: [
        { agent_id: 'agent_0', body_id: 'body-0', agent_seed: 88 },
        { agent_id: 'agent_1', body_id: 'body-1', agent_seed: 89 },
      ],
      ...(extra.header || {}),
    },
    world: { width: 12, height: 12 },
    agents_observer: extra.agents_observer,
    ...(extra.frame || {}),
  };
}

function tlRow(tick: number, a0: string, a1: string) {
  return {
    tick,
    contact: false,
    bodies: [
      { agent_id: 'agent_0', x: tick * 0.01, y: 1, action: a0 },
      { agent_id: 'agent_1', x: 2, y: 1, action: a1 },
    ],
  };
}

describe('tick-level action occupancy accounting', () => {
  it('TEST1: repeated Observer samples do not increase tick-level occupancy', () => {
    const row = tlRow(5, 'WAIT', 'MOVE:N');
    const timeline = [row, row, row, row, row];
    const a = analyzeObserverData({
      frame: frameAt(5, {
        agents_observer: [
          { observer_id: 'agent_0', action_counts: { WAIT: 999 } },
          { observer_id: 'agent_1', action_counts: { 'MOVE:N': 999 } },
        ],
      }),
      timeline,
      events: [],
      mode: 'LIVE',
    });
    const a0 = a.agents.find((x) => x.agent_id === 'agent_0')!;
    const a1 = a.agents.find((x) => x.agent_id === 'agent_1')!;
    assert.equal(a0.ticks_observed, 1);
    assert.equal(Number(a0.actions.wait_count), 1);
    assert.equal(a0.actions.occupancy_total, 1);
    assert.equal(a1.ticks_observed, 1);
    assert.equal(Number(a1.actions.move_count), 1);
  });

  it('TEST2: WAIT+MOVE == agent ticks with valid actions', () => {
    const timeline = [];
    for (let t = 1; t <= 40; t++) {
      timeline.push(tlRow(t, t % 3 === 0 ? 'MOVE:E' : 'WAIT', 'WAIT'));
    }
    const a = analyzeObserverData({ frame: frameAt(40), timeline, events: [], mode: 'FINAL' });
    const a0 = a.agents.find((x) => x.agent_id === 'agent_0')!;
    assert.equal(a0.ticks_observed, 40);
    assert.equal(a0.actions.occupancy_total, 40);
    assert.equal(Number(a0.actions.wait_count) + Number(a0.actions.move_count), 40);
  });

  it('TEST3: occupancy cannot exceed unique observed agent ticks', () => {
    const timeline = [];
    for (let t = 0; t < 50; t++) {
      const row = tlRow(t, 'WAIT', 'MOVE:N');
      timeline.push(row, row, row);
    }
    const a = analyzeObserverData({
      frame: frameAt(49, {
        agents_observer: [
          { observer_id: 'agent_0', action_counts: { WAIT: 5000, 'MOVE:N': 5000 } },
          { observer_id: 'agent_1', action_counts: { WAIT: 5000 } },
        ],
      }),
      timeline,
      mode: 'LIVE',
    });
    for (const ag of a.agents) {
      assert.ok(ag.actions.occupancy_total <= ag.ticks_observed);
      assert.ok(Number(ag.actions.wait_count || 0) + Number(ag.actions.move_count || 0) <= ag.ticks_observed);
    }
  });

  it('TEST4: WAIT streak of 20 requires 20 unique WAIT ticks', () => {
    const timeline = [];
    for (let t = 0; t < 7; t++) timeline.push(tlRow(t, 'WAIT', 'WAIT'));
    const a = analyzeObserverData({ frame: frameAt(6), timeline, mode: 'LIVE' });
    assert.ok(Number(a.agents[0].actions.longest_wait_streak) <= 7);
    assert.ok(!a.important_events.some((e) => e.kind === 'SUSTAINED_WAIT'));

    for (let t = 7; t < 20; t++) timeline.push(tlRow(t, 'WAIT', 'WAIT'));
    const b = analyzeObserverData({ frame: frameAt(19), timeline, mode: 'LIVE' });
    assert.equal(Number(b.agents[0].actions.longest_wait_streak), 20);
    const ev = b.important_events.find((e) => e.kind === 'SUSTAINED_WAIT');
    assert.ok(ev);
    assert.equal(ev!.tick, 19); // threshold-reaching tick
    assert.ok(String(ev!.reason).includes('t0–t19'));
    assert.ok(String(ev!.reason).includes('at t19'));
  });

  it('TEST5: multiple SCENARIO_SELECTED in one tick do not inflate occupancy/streaks', () => {
    const timeline = [tlRow(10, 'WAIT', 'WAIT')];
    const events = [];
    for (let i = 0; i < 15; i++) {
      events.push({
        type: 'SCENARIO_SELECTED',
        tick: 10,
        agent_id: 'agent_0',
        evidence: {
          selected_action: 'WAIT',
          selection_source: 'PROSPECTIVE_SCENARIO',
          event_id: `sc-${i}`,
        },
      });
    }
    const a = analyzeObserverData({ frame: frameAt(10), timeline, events, mode: 'LIVE' });
    const a0 = a.agents.find((x) => x.agent_id === 'agent_0')!;
    assert.equal(a0.ticks_observed, 1);
    assert.equal(Number(a0.actions.wait_count), 1);
    assert.equal(Number(a0.actions.longest_wait_streak), 1);
    assert.equal(Number(a0.cognition.scenario_selected), 15);
  });

  it('TEST6: selection-event counts remain separately reportable', () => {
    const a = analyzeObserverData({
      frame: frameAt(3),
      timeline: [tlRow(1, 'WAIT', 'WAIT'), tlRow(2, 'MOVE:N', 'WAIT'), tlRow(3, 'WAIT', 'WAIT')],
      events: [
        {
          type: 'SCENARIO_SELECTED', tick: 2, agent_id: 'agent_0',
          evidence: { selected_action: 'MOVE:N', selection_source: 'PROSPECTIVE_SCENARIO', event_id: 's1' },
        },
        {
          type: 'DISCRETE_ACTION_SELECTED', tick: 3, agent_id: 'agent_0',
          evidence: { selected_action: 'WAIT', selection_source: 'FALLBACK', event_id: 'd1' },
        },
      ],
    });
    const a0 = a.agents.find((x) => x.agent_id === 'agent_0')!;
    assert.equal(a0.actions.occupancy_total, 3);
    assert.equal(Number(a0.cognition.scenario_selected), 1);
    assert.equal(Number(a0.cognition.fallback_wait_selections), 1);
    assert.ok(a.analysis_log.includes('STRUCTURED COGNITIVE EVENTS'));
  });

  it('TEST7: runtime cumulative cannot overwrite canonical scientific tick counts', () => {
    const timeline = [];
    for (let t = 1; t <= 20; t++) timeline.push(tlRow(t, 'WAIT', 'WAIT'));
    const a = analyzeObserverData({
      frame: frameAt(20, {
        agents_observer: [
          { observer_id: 'agent_0', action_counts: { WAIT: 500, 'MOVE:N': 500 } },
          { observer_id: 'agent_1', action_counts: { WAIT: 999 } },
        ],
      }),
      timeline,
      mode: 'LIVE',
    });
    const a0 = a.agents.find((x) => x.agent_id === 'agent_0')!;
    assert.equal(Number(a0.actions.wait_count), 20);
    assert.equal(a0.actions.occupancy_total, 20);
    assert.notEqual(a0.cumulative_runtime_action_counts, 'NOT AVAILABLE');
    assert.equal((a0.cumulative_runtime_action_counts as any).WAIT, 500);
  });

  it('TEST8: legacy cumulative-only does not fabricate streaks/transitions', () => {
    const a = analyzeObserverData({
      frame: frameAt(100, {
        agents_observer: [
          { observer_id: 'agent_0', action_counts: { WAIT: 80, 'MOVE:N': 20 } },
          { observer_id: 'agent_1', action_counts: { WAIT: 100 } },
        ],
      }),
      timeline: [],
      events: [],
      mode: 'FINAL',
    });
    const a0 = a.agents.find((x) => x.agent_id === 'agent_0')!;
    assert.equal(a0.ticks_observed, 0);
    assert.equal(a0.actions.wait_count, 'NOT AVAILABLE');
    assert.equal(a0.actions.longest_wait_streak, 'NOT AVAILABLE');
    assert.equal(a0.actions.action_transitions, 'NOT AVAILABLE');
    assert.equal((a0.cumulative_runtime_action_counts as any).WAIT, 80);
  });

  it('TEST9: LIVE vs evidence-package agree on tick-level metrics at cutoff', () => {
    const timeline = [];
    const scientific_rows = [];
    for (let t = 1; t <= 30; t++) {
      timeline.push(tlRow(t, t % 4 === 0 ? 'MOVE:N' : 'WAIT', 'WAIT'));
      scientific_rows.push(
        { tick: t, agent_id: 'agent_0', action: t % 4 === 0 ? 'MOVE:N' : 'WAIT', x: 0, y: 0, contact: false },
        { tick: t, agent_id: 'agent_1', action: 'WAIT', x: 1, y: 0, contact: false },
      );
    }
    const live = analyzeObserverData({
      frame: frameAt(30, {
        agents_observer: [
          { observer_id: 'agent_0', action_counts: { WAIT: 999 } },
          { observer_id: 'agent_1', action_counts: { WAIT: 999 } },
        ],
      }),
      timeline,
      mode: 'LIVE',
      scientificEvidence: true,
      skipLiveCumulativeActions: true,
    });
    const offline = analyzeEvidencePackage({
      coverage: 'FULL',
      complete_tick_level_reanalysis: true,
      analysis_cutoff_tick: 30,
      scientific_tick_range: [1, 30],
      runtime_status: 'STOPPED',
      timeline,
      scientific_rows,
      events: [],
      identity: { agent_count: 2, seed: 88, runtime_type: 'TwoAgentRuntime' },
    });
    const l0 = live.agents.find((x) => x.agent_id === 'agent_0')!;
    const o0 = offline.agents.find((x) => x.agent_id === 'agent_0')!;
    assert.equal(l0.actions.wait_count, o0.actions.wait_count);
    assert.equal(l0.actions.move_count, o0.actions.move_count);
    assert.equal(l0.actions.longest_wait_streak, o0.actions.longest_wait_streak);
  });

  it('TEST10: TwoAgentRuntime independent (tick, agent_id) accounting', () => {
    const timeline = [];
    for (let t = 0; t < 10; t++) {
      timeline.push(tlRow(t, 'MOVE:N', 'WAIT'));
    }
    const a = analyzeObserverData({ frame: frameAt(9), timeline, mode: 'LIVE' });
    const a0 = a.agents.find((x) => x.agent_id === 'agent_0')!;
    const a1 = a.agents.find((x) => x.agent_id === 'agent_1')!;
    assert.equal(Number(a0.actions.move_count), 10);
    assert.equal(Number(a0.actions.wait_count), 0);
    assert.equal(Number(a1.actions.wait_count), 10);
    assert.equal(Number(a1.actions.move_count), 0);
  });

  it('TEST11: transitions only across ordered unique simulation ticks', () => {
    const timeline = [
      tlRow(1, 'WAIT', 'WAIT'),
      tlRow(1, 'WAIT', 'WAIT'), // dup
      tlRow(2, 'MOVE:N', 'WAIT'),
      tlRow(2, 'MOVE:N', 'WAIT'),
      tlRow(3, 'WAIT', 'WAIT'),
    ];
    const a = analyzeObserverData({ frame: frameAt(3), timeline, mode: 'LIVE' });
    const a0 = a.agents.find((x) => x.agent_id === 'agent_0')!;
    const tr = a0.actions.action_transitions as Record<string, number>;
    assert.equal(tr['WAIT→MOVE:N'], 1);
    assert.equal(tr['MOVE:N→WAIT'], 1);
    assert.equal(a0.actions.occupancy_total, 3);
  });

  it('TEST12: re-analysis read-only and deterministic', () => {
    const timeline = [];
    for (let t = 1; t <= 15; t++) timeline.push(tlRow(t, 'WAIT', 'MOVE:E'));
    const pkg = {
      coverage: 'FULL' as const,
      complete_tick_level_reanalysis: true,
      analysis_cutoff_tick: 15,
      scientific_tick_range: [1, 15] as [number, number],
      runtime_status: 'STOPPED',
      timeline,
      events: [],
      identity: { agent_count: 2, seed: 88 },
    };
    const a = reanalyzeEvidence(pkg);
    const b = reanalyzeEvidence(pkg);
    assert.equal(scientificCoreFingerprint(a), scientificCoreFingerprint(b));
    assert.equal(a.agents[0].actions.occupancy_total, 15);
  });

  it('evidence gap breaks streak (consecutive-tick rule)', () => {
    const agg = makeAgentAgg('agent_0', 'body-0');
    for (let t = 1; t <= 5; t++) assert.equal(ingestAction(agg, 'WAIT', t), true);
    assert.equal(agg.wait_streak, 5);
    // Gap: tick 10 after tick 5
    assert.equal(ingestAction(agg, 'WAIT', 10), true);
    assert.equal(agg.wait_streak, 1);
    assert.equal(agg.longest_wait_streak, 5);
    assert.equal(agg.ticks, 6);
  });

  it('incremental LIVE re-ingest with inflated cumulative stays consistent', () => {
    const timeline = [];
    for (let t = 0; t < 25; t++) timeline.push(tlRow(t, 'WAIT', 'WAIT'));
    const state = createAnalysisState();
    for (let i = 0; i < 8; i++) {
      ingestAnalysisInput(state, {
        frame: frameAt(24, {
          agents_observer: [
            { observer_id: 'agent_0', action_counts: { WAIT: 100 + i * 10 } },
            { observer_id: 'agent_1', action_counts: { WAIT: 200 } },
          ],
        }),
        timeline,
        events: [],
        mode: 'LIVE',
      });
    }
    const a = buildRunAnalysis(state, 'LIVE');
    const a0 = a.agents.find((x) => x.agent_id === 'agent_0')!;
    assert.equal(a0.ticks_observed, 25);
    assert.equal(Number(a0.actions.wait_count), 25);
    assert.equal(a0.actions.occupancy_total, 25);
    assert.ok(Number(a0.actions.longest_wait_streak) >= 20);
    assert.ok(a0.actions.occupancy_total <= a0.ticks_observed);
  });
});
