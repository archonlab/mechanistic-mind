import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  analyzeObserverData,
  buildRunAnalysis,
  createAnalysisState,
  ingestAnalysisInput,
  BOUNDS,
  selectRepresentativeKeyframes,
  detectPhases,
  formatAnalysisLog,
} from './index.ts';

function tl(tick: number, action: string, agent = 'agent_0', x = 1, y = 1, contact = false, bodies?: any[]) {
  return {
    tick,
    action,
    agent_id: agent,
    body_xy: { x, y },
    contact,
    bodies: bodies || [{ agent_id: agent, x, y, action }],
  };
}

describe('run analysis', () => {
  it('single-agent analysis from timeline', () => {
    const timeline = [];
    for (let t = 0; t < 30; t++) timeline.push(tl(t, t < 5 ? 'WAIT' : 'MOVE:E', 'agent_0', t * 0.2, 1));
    const analysis = analyzeObserverData({
      frame: {
        header: { tick: 29, seed: 17, runtime_model: 'PhysicalSystemRuntime', status: 'PAUSED', agent_count: 1, selected_body_id: 'body-0' },
        world: { width: 32, height: 32 },
        mind: { metrics: { action_counts: { WAIT: 5, 'MOVE:E': 25 }, prediction_count: 3 } },
        body: { x: 5, y: 1 },
      },
      timeline,
      events: [],
      mode: 'LIVE',
    });
    assert.equal(analysis.agents.length, 1);
    assert.equal(analysis.agents[0].agent_id, 'agent_0');
    assert.equal(analysis.comparison, null);
    assert.ok(Number(analysis.agents[0].actions.move_count) >= 1);
    assert.ok(analysis.important_events.some((e) => e.kind === 'FIRST_MOVE'));
    assert.ok(analysis.analysis_log.includes('MECHANISTIC MIND'));
  });

  it('two-agent analysis + comparison', () => {
    const timeline = [];
    for (let t = 0; t < 40; t++) {
      timeline.push({
        tick: t,
        action: t % 3 === 0 ? 'WAIT' : 'MOVE:N',
        agent_id: 'agent_0',
        contact: t >= 10 && t <= 12,
        bodies: [
          { agent_id: 'agent_0', x: 3 + t * 0.1, y: 3, action: t % 3 === 0 ? 'WAIT' : 'MOVE:N' },
          { agent_id: 'agent_1', x: 4, y: 3, action: 'WAIT' },
        ],
      });
    }
    const analysis = analyzeObserverData({
      frame: {
        header: {
          tick: 39, seed: 143, runtime_generation: 2, runtime_model: 'TwoAgentRuntime', status: 'PAUSED', agent_count: 2,
          agent_body_mapping: [
            { agent_id: 'agent_0', body_id: 'body-0', agent_seed: 143 },
            { agent_id: 'agent_1', body_id: 'body-1', agent_seed: 144 },
          ],
        },
        world: { width: 12, height: 12 },
        agents_observer: [
          { observer_id: 'agent_0', agent_seed: 143, distance_travelled: 4, wait_count: 10, move_count: 30, action_counts: { WAIT: 10, 'MOVE:N': 30 } },
          { observer_id: 'agent_1', agent_seed: 144, distance_travelled: 0.1, wait_count: 40, move_count: 0, action_counts: { WAIT: 40 } },
        ],
      },
      timeline,
      events: [
        {
          type: 'PHYSICAL_SIGNAL_EMITTED', tick: 10, emitter_agent_id: 'agent_0',
          evidence: { emission_id: 'e10-B-s0-body_contact-0', channel: 'B', trigger: 'body_contact', emitter_agent_id: 'agent_0', emitter_body_id: 'body-0', contact_entity_a_id: 'body-0', contact_entity_b_id: 'body-1' },
        },
        {
          type: 'PHYSICAL_SIGNAL_RECEIVED', tick: 10, receiver_agent_id: 'agent_1', agent_id: 'agent_1',
          evidence: {
            receiver_agent_id: 'agent_1', receiver_body_id: 'body-1', source_attribution: 'MIXED',
            'local.FIELD_B': 0.5,
            causal_parent_ids: ['e10-B-s0-body_contact-0'],
            contributing_emissions_this_tick: [{ emission_id: 'e10-B-s0-body_contact-0', emitter_agent_id: 'agent_0', channel: 'B' }],
          },
        },
      ],
      mode: 'FINAL',
    });
    assert.equal(analysis.agents.length, 2);
    assert.ok(analysis.comparison);
    assert.ok(analysis.important_events.some((e) => e.kind === 'FIRST_BODY_BODY_CONTACT'));
    assert.ok(analysis.important_events.some((e) => e.kind === 'FIRST_CROSS_AGENT_CONTRIBUTION'));
    assert.ok(analysis.interactions.cross_agent_contributions >= 1);
    assert.equal(analysis.agents.find((a) => a.agent_id === 'agent_1')?.signals.reception_attribution.mixed, 1);
    assert.ok(analysis.causal_chains.length >= 1);
    assert.ok(analysis.overview.length >= 1);
    assert.ok(analysis.analysis_log.includes('AGENT COMPARISON'));
  });

  it('first-event and streak detection', () => {
    const timeline = [];
    for (let t = 0; t < 25; t++) timeline.push(tl(t, 'WAIT'));
    for (let t = 25; t < 45; t++) timeline.push(tl(t, 'MOVE:S', 'agent_0', t, 2));
    const a = analyzeObserverData({
      frame: { header: { tick: 44, seed: 1, status: 'PAUSED' }, world: { width: 16, height: 16 } },
      timeline,
      events: [],
    });
    assert.ok(a.important_events.some((e) => e.kind === 'FIRST_MOVE' && e.tick === 25));
    assert.ok(a.important_events.some((e) => e.kind === 'SUSTAINED_WAIT'));
    assert.ok(Number(a.agents[0].actions.longest_wait_streak) >= 20);
  });

  it('phase compression and overview cards bounded', () => {
    const timeline = [];
    for (let t = 0; t < 200; t++) {
      timeline.push({
        tick: t,
        contact: t >= 50 && t <= 60,
        bodies: [
          { agent_id: 'agent_0', x: t * 0.01, y: 1, action: t < 40 ? 'WAIT' : 'MOVE:E' },
          { agent_id: 'agent_1', x: 2, y: 1, action: 'WAIT' },
        ],
      });
    }
    const a = analyzeObserverData({
      frame: {
        header: { tick: 199, seed: 143, agent_count: 2, runtime_model: 'TwoAgentRuntime', status: 'STOPPED',
          agent_body_mapping: [
            { agent_id: 'agent_0', body_id: 'body-0', agent_seed: 143 },
            { agent_id: 'agent_1', body_id: 'body-1', agent_seed: 144 },
          ] },
        world: { width: 12, height: 12 },
      },
      timeline,
      events: [],
      mode: 'FINAL',
    });
    assert.ok(a.phases.length >= 1);
    assert.ok(a.overview.length <= BOUNDS.max_overview_cards);
    assert.ok(a.overview.some((c) => c.kind === 'QUIET' || c.kind === 'PHASE' || c.kind === 'KEY'));
  });

  it('missing telemetry stays NOT AVAILABLE', () => {
    const a = analyzeObserverData({
      frame: { header: { tick: 0, seed: 9, status: 'PAUSED' }, world: { width: 8, height: 8 } },
      timeline: [],
      events: [],
    });
    assert.equal(a.agents[0].cognition.prediction_count, 'NOT AVAILABLE');
    assert.ok(a.coverage.cognition.includes('NOT AVAILABLE') || a.coverage.cognition.includes('sparse'));
  });

  it('keyframe selection is bounded', () => {
    const frames = Array.from({ length: 200 }, (_, i) => ({
      tick: i, reason: `r${i}`, agents: [{ agent_id: 'agent_0', x: i, y: 0 }], contact: false, world_w: 12, world_h: 12,
    }));
    const sel = selectRepresentativeKeyframes(frames, 50);
    assert.ok(sel.length <= 50);
    assert.equal(sel[0].tick, 0);
  });

  it('switching selected agent does not change analysis identity', () => {
    const input = {
      frame: {
        header: { tick: 10, seed: 143, selected_agent_id: 'agent_0', agent_count: 2, runtime_model: 'TwoAgentRuntime',
          agent_body_mapping: [
            { agent_id: 'agent_0', body_id: 'body-0', agent_seed: 143 },
            { agent_id: 'agent_1', body_id: 'body-1', agent_seed: 144 },
          ] },
        world: { width: 12, height: 12 },
        agents_observer: [
          { observer_id: 'agent_0', agent_seed: 143, action_counts: { WAIT: 5 } },
          { observer_id: 'agent_1', agent_seed: 144, action_counts: { WAIT: 5 } },
        ],
      },
      timeline: [tl(1, 'WAIT', 'agent_0'), tl(1, 'WAIT', 'agent_1')],
      events: [],
    };
    const a = analyzeObserverData(input);
    input.frame.header.selected_agent_id = 'agent_1';
    const b = analyzeObserverData(input);
    assert.equal(a.agents.length, b.agents.length);
    assert.deepEqual(
      a.agents.map((x) => x.agent_id),
      b.agents.map((x) => x.agent_id),
    );
  });

  it('incremental ingest stays bounded for long runs', () => {
    const state = createAnalysisState();
    for (let batch = 0; batch < 50; batch++) {
      const timeline = [];
      for (let i = 0; i < 100; i++) {
        const t = batch * 100 + i;
        timeline.push(tl(t, t % 7 === 0 ? 'MOVE:W' : 'WAIT', 'agent_0', t % 12, 1, t % 40 === 0));
      }
      ingestAnalysisInput(state, {
        frame: { header: { tick: (batch + 1) * 100 - 1, seed: 7, status: 'RUNNING', runtime_generation: 1 }, world: { width: 12, height: 12 } },
        timeline,
        events: [],
      });
    }
    const analysis = buildRunAnalysis(state, 'LIVE');
    assert.ok(state.important.length <= BOUNDS.important_events);
    assert.ok(state.keyframes.length <= BOUNDS.keyframes);
    assert.ok(analysis.overview.length <= BOUNDS.max_overview_cards);
    assert.ok(state.seen_event_keys.size <= 4000);
  });

  it('clipboard text generation via analysis log', () => {
    const a = analyzeObserverData({
      frame: { header: { tick: 3, seed: 143, status: 'STOPPED' }, world: { width: 12, height: 12 } },
      timeline: [tl(0, 'WAIT'), tl(1, 'MOVE:E'), tl(2, 'MOVE:E')],
      events: [],
      mode: 'FINAL',
    });
    const text = formatAnalysisLog(a);
    assert.ok(text.includes('DATA COVERAGE:'));
    assert.ok(text.includes('SCIENTIFIC BOUNDARY'));
    assert.equal(text, a.analysis_log);
  });

  it('phase detection returns measurable names', () => {
    const state = createAnalysisState();
    ingestAnalysisInput(state, {
      frame: { header: { tick: 100, seed: 1, status: 'PAUSED' }, world: { width: 8, height: 8 } },
      timeline: Array.from({ length: 100 }, (_, t) => tl(t, t < 20 ? 'WAIT' : 'MOVE:N', 'agent_0', t * 0.1, 1, t > 40 && t < 50)),
      events: [],
    });
    const phases = detectPhases(state);
    assert.ok(phases.every((p) => !/fear|curiosity|boredom|friendship/i.test(p.name)));
  });
});
