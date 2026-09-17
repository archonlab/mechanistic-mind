/**
 * SUSTAINED WAIT/MOVE IMPORTANT EVENTS — one threshold crossing per continuous streak.
 */
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  analyzeObserverData,
  buildRunAnalysis,
  ingestAnalysisInput,
} from './runAnalysis.ts';
import { createAnalysisState } from './aggregates.ts';
import { analyzeEvidencePackage, reanalyzeEvidence, scientificCoreFingerprint } from './scientificEvidence.ts';

function frameAt(tick: number, extra: any = {}) {
  return {
    header: {
      tick,
      seed: 17,
      runtime_generation: 3,
      runtime_model: 'TwoAgentRuntime',
      status: 'RUNNING',
      agent_count: 2,
      agent_body_mapping: [
        { agent_id: 'agent_0', body_id: 'body-0', agent_seed: 17 },
        { agent_id: 'agent_1', body_id: 'body-1', agent_seed: 18 },
      ],
      ...(extra.header || {}),
    },
    world: { width: 10, height: 10, boundary: 'WRAP_PERIODIC' },
    agents_observer: extra.agents_observer,
  };
}

function row(tick: number, a0: string, a1: string) {
  return {
    tick,
    contact: false,
    bodies: [
      { agent_id: 'agent_0', x: 0, y: 0, action: a0 },
      { agent_id: 'agent_1', x: 1, y: 0, action: a1 },
    ],
  };
}

function sustained(kind: string, analysis: { important_events: any[] }, agent = 'agent_1') {
  return analysis.important_events.filter(
    (e) => e.kind === kind && (e.agent_ids || []).includes(agent),
  );
}

describe('sustained streak IMPORTANT EVENTS', () => {
  it('TEST1: no derived event tick < 0 when run starts at 0', () => {
    const timeline = [];
    for (let t = 0; t < 30; t++) timeline.push(row(t, 'WAIT', 'MOVE:N'));
    // Also inject incomplete single-agent rows that previously froze streaks
    for (let t = 0; t < 30; t++) {
      timeline.push({ tick: t, agent_id: 'agent_0', action: 'WAIT', body_xy: { x: 0, y: 0 } });
    }
    const a = analyzeObserverData({ frame: frameAt(29), timeline, mode: 'LIVE' });
    for (const ev of a.important_events) {
      assert.ok(ev.tick >= 0, `event tick ${ev.tick} kind=${ev.kind}`);
      if (ev.refs?.streak_start != null) assert.ok(Number(ev.refs.streak_start) >= 0);
      assert.ok(!String(ev.reason).includes('t-'));
    }
  });

  it('TEST2: MOVE t44–t53 → exactly one threshold-10 event at t53 span t44–t53', () => {
    const timeline = [];
    for (let t = 0; t < 44; t++) timeline.push(row(t, 'WAIT', 'WAIT'));
    for (let t = 44; t <= 53; t++) timeline.push(row(t, 'WAIT', 'MOVE:N'));
    const a = analyzeObserverData({ frame: frameAt(53), timeline, mode: 'FINAL' });
    const moves = sustained('SUSTAINED_MOVE', a);
    assert.equal(moves.length, 1);
    assert.equal(moves[0].tick, 53);
    assert.equal(moves[0].refs.streak_start, 44);
    assert.equal(moves[0].refs.threshold_tick, 53);
    assert.ok(moves[0].reason.includes('at t53'));
    assert.ok(moves[0].reason.includes('t44–t53'));
    const first = a.important_events.find((e) => e.kind === 'FIRST_MOVE' && e.agent_ids?.includes('agent_1'));
    assert.equal(first?.tick, 44);
  });

  it('TEST3: MOVE t44–t96 still exactly one threshold-10 event', () => {
    const timeline = [];
    for (let t = 0; t < 44; t++) timeline.push(row(t, 'WAIT', 'WAIT'));
    for (let t = 44; t <= 96; t++) timeline.push(row(t, 'WAIT', 'MOVE:S'));
    const a = analyzeObserverData({ frame: frameAt(96), timeline, mode: 'FINAL' });
    const moves = sustained('SUSTAINED_MOVE', a);
    assert.equal(moves.length, 1);
    assert.equal(moves[0].tick, 53);
    assert.equal(Number(a.agents.find((x) => x.agent_id === 'agent_1')!.actions.longest_move_streak), 53);
  });

  it('TEST4: two independent MOVE streaks → two threshold events', () => {
    const timeline = [];
    for (let t = 44; t <= 53; t++) timeline.push(row(t, 'WAIT', 'MOVE:N'));
    timeline.push(row(54, 'WAIT', 'WAIT'));
    for (let t = 55; t <= 64; t++) timeline.push(row(t, 'WAIT', 'MOVE:E'));
    const a = analyzeObserverData({ frame: frameAt(64), timeline, mode: 'FINAL' });
    const moves = sustained('SUSTAINED_MOVE', a);
    assert.equal(moves.length, 2);
    assert.equal(moves[0].tick, 53);
    assert.equal(moves[0].refs.streak_start, 44);
    assert.equal(moves[1].tick, 64);
    assert.equal(moves[1].refs.streak_start, 55);
  });

  it('TEST5: missing simulation tick breaks the streak', () => {
    const timeline = [];
    for (let t = 0; t < 9; t++) timeline.push(row(t, 'WAIT', 'MOVE:N'));
    // gap: skip tick 9
    for (let t = 10; t < 20; t++) timeline.push(row(t, 'WAIT', 'MOVE:N'));
    const a = analyzeObserverData({ frame: frameAt(19), timeline, mode: 'FINAL' });
    const moves = sustained('SUSTAINED_MOVE', a);
    // First streak 0–8 = 9 ticks (<10); second 10–19 = 10 ticks → one event at 19
    assert.equal(moves.length, 1);
    assert.equal(moves[0].tick, 19);
    assert.equal(moves[0].refs.streak_start, 10);
  });

  it('TEST6: repeated Observer samples do not extend streaks or duplicate events', () => {
    const timeline = [];
    for (let t = 44; t <= 53; t++) {
      const r = row(t, 'WAIT', 'MOVE:N');
      timeline.push(r, r, r);
    }
    const a = analyzeObserverData({ frame: frameAt(53), timeline, mode: 'LIVE' });
    assert.equal(sustained('SUSTAINED_MOVE', a).length, 1);
    assert.equal(Number(a.agents.find((x) => x.agent_id === 'agent_1')!.actions.longest_move_streak), 10);
  });

  it('TEST7: repeated LIVE refreshes do not duplicate threshold event', () => {
    const timeline = [];
    for (let t = 0; t < 44; t++) timeline.push(row(t, 'WAIT', 'WAIT'));
    for (let t = 44; t <= 60; t++) timeline.push(row(t, 'WAIT', 'MOVE:N'));
    const state = createAnalysisState();
    for (let i = 0; i < 12; i++) {
      ingestAnalysisInput(state, { frame: frameAt(60), timeline, events: [], mode: 'LIVE' });
    }
    const a = buildRunAnalysis(state, 'LIVE');
    assert.equal(sustained('SUSTAINED_MOVE', a).length, 1);
  });

  it('TEST8: FIRST MOVE tick is never later than start of MOVE streak event', () => {
    const timeline = [];
    for (let t = 0; t < 44; t++) timeline.push(row(t, 'WAIT', 'WAIT'));
    for (let t = 44; t <= 70; t++) timeline.push(row(t, 'WAIT', 'MOVE:N'));
    const a = analyzeObserverData({ frame: frameAt(70), timeline, mode: 'FINAL' });
    const first = a.important_events.find((e) => e.kind === 'FIRST_MOVE' && e.agent_ids?.includes('agent_1'))!;
    for (const ev of sustained('SUSTAINED_MOVE', a)) {
      assert.ok(first.tick <= ev.refs.streak_start);
    }
  });

  it('TEST9: no SUSTAINED MOVE before first canonical MOVE', () => {
    const timeline = [];
    for (let t = 0; t < 44; t++) timeline.push(row(t, 'WAIT', 'WAIT'));
    for (let t = 44; t <= 53; t++) timeline.push(row(t, 'WAIT', 'MOVE:N'));
    // Incomplete other-agent-only rows at early ticks (regression for frozen-streak spam)
    for (let t = 0; t < 20; t++) {
      timeline.push({ tick: t, agent_id: 'agent_0', action: 'WAIT', bodies: [{ agent_id: 'agent_0', x: 0, y: 0, action: 'WAIT' }] });
    }
    const a = analyzeObserverData({ frame: frameAt(53), timeline, mode: 'LIVE' });
    const first = a.important_events.find((e) => e.kind === 'FIRST_MOVE' && e.agent_ids?.includes('agent_1'))!;
    assert.equal(first.tick, 44);
    for (const ev of sustained('SUSTAINED_MOVE', a)) {
      assert.ok(ev.tick >= first.tick);
      assert.ok(ev.refs.streak_start >= first.tick);
    }
  });

  it('TEST10: WAIT threshold 20 follows the same rules', () => {
    const timeline = [];
    for (let t = 5; t <= 24; t++) timeline.push(row(t, 'WAIT', 'MOVE:N'));
    for (let t = 25; t <= 50; t++) timeline.push(row(t, 'WAIT', 'MOVE:N'));
    const a = analyzeObserverData({ frame: frameAt(50), timeline, mode: 'FINAL' });
    const waits = sustained('SUSTAINED_WAIT', a, 'agent_0');
    assert.equal(waits.length, 1);
    assert.equal(waits[0].tick, 24);
    assert.equal(waits[0].refs.streak_start, 5);
    assert.ok(waits[0].reason.includes('t5–t24'));
  });

  it('TEST11: longest streak aggregate agrees with canonical sequence', () => {
    const timeline = [];
    for (let t = 44; t <= 96; t++) timeline.push(row(t, 'WAIT', 'MOVE:N'));
    const a = analyzeObserverData({ frame: frameAt(96), timeline, mode: 'FINAL' });
    assert.equal(Number(a.agents.find((x) => x.agent_id === 'agent_1')!.actions.longest_move_streak), 53);
    assert.equal(sustained('SUSTAINED_MOVE', a).length, 1);
  });

  it('TEST12: LIVE and saved FULL re-analysis agree on threshold events at cutoff', () => {
    const timeline = [];
    for (let t = 0; t < 44; t++) timeline.push(row(t, 'WAIT', 'WAIT'));
    for (let t = 44; t <= 70; t++) timeline.push(row(t, 'WAIT', 'MOVE:N'));
    const live = analyzeObserverData({ frame: frameAt(70), timeline, mode: 'LIVE' });
    const offline = analyzeEvidencePackage({
      coverage: 'FULL',
      complete_tick_level_reanalysis: true,
      analysis_cutoff_tick: 70,
      scientific_tick_range: [0, 70],
      runtime_status: 'STOPPED',
      timeline,
      events: [],
      identity: { agent_count: 2, seed: 17, runtime_type: 'TwoAgentRuntime' },
    });
    const l = sustained('SUSTAINED_MOVE', live).map((e) => ({ t: e.tick, s: e.refs.streak_start }));
    const o = sustained('SUSTAINED_MOVE', offline).map((e) => ({ t: e.tick, s: e.refs.streak_start }));
    assert.deepEqual(l, o);
  });

  it('TEST13: PARTIAL evidence does not fabricate streak start before coverage', () => {
    // Available window starts at 100; MOVE 100–109 → event at 109 span 100–109 (not 90–109)
    const timeline = [];
    for (let t = 100; t <= 109; t++) timeline.push(row(t, 'WAIT', 'MOVE:N'));
    const a = analyzeObserverData({ frame: frameAt(109), timeline, mode: 'LIVE' });
    const moves = sustained('SUSTAINED_MOVE', a);
    assert.equal(moves.length, 1);
    assert.equal(moves[0].refs.streak_start, 100);
    assert.equal(moves[0].tick, 109);
    assert.ok(moves[0].refs.streak_start >= 100);
  });

  it('TEST14: SCENARIO_SELECTED cannot create/extend canonical streaks', () => {
    const timeline = [row(10, 'WAIT', 'WAIT')];
    const events = [];
    for (let i = 0; i < 20; i++) {
      events.push({
        type: 'SCENARIO_SELECTED',
        tick: 10,
        agent_id: 'agent_1',
        evidence: { selected_action: 'MOVE:N', selection_source: 'PROSPECTIVE_SCENARIO', event_id: `s${i}` },
      });
    }
    const a = analyzeObserverData({ frame: frameAt(10), timeline, events, mode: 'LIVE' });
    assert.equal(sustained('SUSTAINED_MOVE', a).length, 0);
    assert.equal(Number(a.agents.find((x) => x.agent_id === 'agent_1')!.actions.longest_move_streak), 0);
  });

  it('TEST15: re-analysis read-only and deterministic', () => {
    const timeline = [];
    for (let t = 44; t <= 60; t++) timeline.push(row(t, 'WAIT', 'MOVE:N'));
    const pkg = {
      coverage: 'FULL' as const,
      complete_tick_level_reanalysis: true,
      analysis_cutoff_tick: 60,
      scientific_tick_range: [44, 60] as [number, number],
      runtime_status: 'STOPPED',
      timeline,
      events: [],
      identity: { agent_count: 2, seed: 17 },
    };
    const a = reanalyzeEvidence(pkg);
    const b = reanalyzeEvidence(pkg);
    assert.equal(scientificCoreFingerprint(a), scientificCoreFingerprint(b));
    assert.deepEqual(
      sustained('SUSTAINED_MOVE', a).map((e) => e.tick),
      sustained('SUSTAINED_MOVE', b).map((e) => e.tick),
    );
  });
});
