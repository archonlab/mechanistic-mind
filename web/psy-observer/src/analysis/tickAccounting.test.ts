/**
 * Regression: Observer sample multiplicity must not inflate simulation-tick metrics.
 */
import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  analyzeObserverData,
  buildRunAnalysis,
  createAnalysisState,
  ingestAnalysisInput,
  sanitizeContactEpisode,
  episodesFromContactTicks,
  structuredEventKey,
} from './index.ts';

function tl(
  tick: number,
  action: string,
  agent = 'agent_0',
  x = 1,
  y = 1,
  contact = false,
  bodies?: any[],
) {
  return {
    tick,
    action,
    agent_id: agent,
    body_xy: { x, y },
    contact,
    bodies: bodies || [{ agent_id: agent, x, y, action }],
  };
}

function frameAt(tick: number, extras: any = {}) {
  return {
    header: {
      tick,
      seed: 17,
      runtime_model: extras.runtime || 'PhysicalSystemRuntime',
      status: extras.status || 'PAUSED',
      agent_count: extras.agent_count || 1,
      ...(extras.header || {}),
    },
    world: { width: 32, height: 32 },
    ...(extras.frame || {}),
  };
}

describe('tick vs Observer-sample accounting', () => {
  it('TEST1: repeated timeline samples → unique simulation ticks', () => {
    const timeline = [
      tl(100, 'WAIT'),
      tl(100, 'WAIT'),
      tl(100, 'WAIT'),
      tl(101, 'WAIT'),
      tl(101, 'WAIT'),
      tl(102, 'MOVE:E', 'agent_0', 2, 1),
    ];
    const a = analyzeObserverData({
      frame: frameAt(102),
      timeline,
      events: [],
      mode: 'LIVE',
    });
    assert.equal(a.coverage.unique_simulation_ticks, 3);
    assert.equal(a.coverage.timeline_samples, 6);
    assert.equal(a.agents[0].ticks_observed, 3);
  });

  it('TEST2: repeated identical MOVE event → count 1', () => {
    const move = tl(100, 'MOVE:N', 'agent_0', 3, 3);
    const timeline = [move, move, move, move];
    const a = analyzeObserverData({ frame: frameAt(100), timeline, events: [], mode: 'LIVE' });
    assert.equal(Number(a.agents[0].actions.move_count), 1);
    assert.equal(a.agents[0].ticks_observed, 1);
  });

  it('TEST3: two distinct structured events same tick both retained', () => {
    const events = [
      {
        type: 'PHYSICAL_SIGNAL_EMITTED',
        tick: 100,
        emitter_agent_id: 'agent_0',
        evidence: { emission_id: 'e100-A', channel: 'A', trigger: 'body_motion', emitter_agent_id: 'agent_0' },
      },
      {
        type: 'PHYSICAL_SIGNAL_EMITTED',
        tick: 100,
        emitter_agent_id: 'agent_0',
        evidence: { emission_id: 'e100-B', channel: 'B', trigger: 'body_contact', emitter_agent_id: 'agent_0' },
      },
      // duplicate of first — must not double-count
      {
        type: 'PHYSICAL_SIGNAL_EMITTED',
        tick: 100,
        emitter_agent_id: 'agent_0',
        evidence: { emission_id: 'e100-A', channel: 'A', trigger: 'body_motion', emitter_agent_id: 'agent_0' },
      },
    ];
    const a = analyzeObserverData({
      frame: frameAt(100, { agent_count: 1 }),
      timeline: [tl(100, 'WAIT')],
      events,
      mode: 'LIVE',
    });
    assert.equal(a.agents[0].signals.emissions_A, 1);
    assert.equal(a.agents[0].signals.emissions_B, 1);
    assert.equal(a.coverage.event_samples, 2);
    assert.notEqual(structuredEventKey(events[0]), structuredEventKey(events[1]));
  });

  it('TEST4: duplicate samples do not inflate action streak', () => {
    const timeline = [];
    for (let i = 0; i < 10; i++) timeline.push(tl(50, 'WAIT'));
    for (let t = 51; t <= 55; t++) {
      for (let i = 0; i < 5; i++) timeline.push(tl(t, 'WAIT'));
    }
    const a = analyzeObserverData({ frame: frameAt(55), timeline, events: [], mode: 'LIVE' });
    // ticks 50–55 = 6 unique WAIT selections
    assert.equal(Number(a.agents[0].actions.wait_count), 6);
    assert.equal(Number(a.agents[0].actions.longest_wait_streak), 6);
    assert.ok(Number(a.agents[0].actions.longest_wait_streak) < 30);
  });

  it('TEST5: contact unique ticks + one episode', () => {
    const timeline = [
      tl(100, 'WAIT', 'agent_0', 1, 1, true),
      tl(100, 'WAIT', 'agent_0', 1, 1, true),
      tl(101, 'WAIT', 'agent_0', 1, 1, true),
      tl(101, 'WAIT', 'agent_0', 1, 1, true),
      tl(102, 'WAIT', 'agent_0', 1, 1, true),
      tl(103, 'WAIT', 'agent_0', 1, 1, false),
    ];
    const a = analyzeObserverData({
      frame: frameAt(103, {
        agent_count: 2,
        header: {
          agent_body_mapping: [
            { agent_id: 'agent_0', body_id: 'body-0' },
            { agent_id: 'agent_1', body_id: 'body-1' },
          ],
        },
      }),
      timeline,
      events: [],
      mode: 'LIVE',
    });
    assert.equal(a.interactions.contact_ticks, 3);
    assert.equal(a.interactions.contact_episodes.length, 1);
    assert.equal(a.interactions.contact_episodes[0].start, 100);
    assert.equal(a.interactions.contact_episodes[0].end, 102);
    assert.equal(a.interactions.contact_episodes[0].ticks, 3);
  });

  it('TEST6: repeated body states do not inflate movement distance', () => {
    const timeline = [
      tl(1, 'MOVE:E', 'agent_0', 0, 0),
      tl(1, 'MOVE:E', 'agent_0', 0, 0),
      tl(2, 'MOVE:E', 'agent_0', 1, 0),
      tl(2, 'MOVE:E', 'agent_0', 1, 0),
      tl(2, 'MOVE:E', 'agent_0', 1, 0),
      tl(3, 'MOVE:E', 'agent_0', 2, 0),
    ];
    const a = analyzeObserverData({ frame: frameAt(3), timeline, events: [], mode: 'LIVE' });
    // Manhattan |1|+|1| = 2
    assert.equal(Number(a.agents[0].movement.distance_travelled), 2);
  });

  it('TEST7: LIVE idempotence — duplicated samples leave scientific metrics identical', () => {
    const baseTimeline = [];
    for (let t = 10; t <= 30; t++) {
      baseTimeline.push(tl(t, t % 4 === 0 ? 'WAIT' : 'MOVE:S', 'agent_0', t * 0.1, 2, t >= 15 && t <= 17));
    }
    const events = [
      {
        type: 'PHYSICAL_SIGNAL_EMITTED',
        tick: 15,
        emitter_agent_id: 'agent_0',
        evidence: { emission_id: 'e15', channel: 'B', trigger: 'body_contact', emitter_agent_id: 'agent_0' },
      },
    ];
    const once = analyzeObserverData({
      frame: frameAt(30),
      timeline: baseTimeline,
      events,
      mode: 'LIVE',
    });
    const dupTimeline = baseTimeline.flatMap((row) => [row, row, row, row, row]);
    const dupEvents = [...events, ...events, ...events];
    const many = analyzeObserverData({
      frame: frameAt(30),
      timeline: dupTimeline,
      events: dupEvents,
      mode: 'LIVE',
    });
    assert.equal(once.agents[0].ticks_observed, many.agents[0].ticks_observed);
    assert.equal(once.agents[0].actions.wait_count, many.agents[0].actions.wait_count);
    assert.equal(once.agents[0].actions.move_count, many.agents[0].actions.move_count);
    assert.equal(once.agents[0].actions.longest_wait_streak, many.agents[0].actions.longest_wait_streak);
    assert.equal(once.agents[0].movement.distance_travelled, many.agents[0].movement.distance_travelled);
    assert.equal(once.interactions.contact_ticks, many.interactions.contact_ticks);
    assert.equal(once.agents[0].signals.emissions_B, many.agents[0].signals.emissions_B);
    assert.equal(once.coverage.unique_simulation_ticks, many.coverage.unique_simulation_ticks);
    // Diagnostic sample counts may differ
    assert.ok(many.coverage.timeline_samples > once.coverage.timeline_samples);
  });

  it('TEST8: different Observer sampling multiplicities → invariant science', () => {
    const mk = (mult: number) => {
      const timeline = [];
      for (let t = 0; t < 20; t++) {
        for (let m = 0; m < mult; m++) {
          timeline.push(tl(t, t < 10 ? 'WAIT' : 'MOVE:E', 'agent_0', t, 0));
        }
      }
      return analyzeObserverData({ frame: frameAt(19), timeline, events: [], mode: 'FINAL' });
    };
    const a1 = mk(1);
    const a8 = mk(8);
    assert.equal(a1.agents[0].ticks_observed, a8.agents[0].ticks_observed);
    assert.equal(a1.agents[0].actions.wait_pct, a8.agents[0].actions.wait_pct);
    assert.equal(a1.agents[0].movement.distance_travelled, a8.agents[0].movement.distance_travelled);
    assert.equal(a1.coverage.unique_simulation_ticks, 20);
    assert.equal(a8.coverage.unique_simulation_ticks, 20);
  });

  it('TEST9: contact episode sanity start <= end', () => {
    assert.equal(sanitizeContactEpisode(10, 5), null);
    const ok = sanitizeContactEpisode(10, 12);
    assert.ok(ok);
    assert.ok(ok!.start <= ok!.end);
    const eps = episodesFromContactTicks([5, 6, 7, 20, 21]);
    for (const ep of eps) assert.ok(ep.start <= ep.end, JSON.stringify(ep));
    assert.equal(eps.length, 2);
    assert.equal(eps[0].start, 5);
    assert.equal(eps[0].end, 7);
  });

  it('TEST10: TwoAgentRuntime per-agent accounting with duplicates', () => {
    const timeline = [];
    for (let t = 0; t < 30; t++) {
      const row = {
        tick: t,
        contact: t >= 10 && t <= 12,
        bodies: [
          { agent_id: 'agent_0', x: t * 0.2, y: 1, action: t % 2 === 0 ? 'WAIT' : 'MOVE:N' },
          { agent_id: 'agent_1', x: 5, y: 1, action: 'WAIT' },
        ],
      };
      timeline.push(row);
      timeline.push(row); // duplicate Observer sample
      timeline.push(row);
    }
    const state = createAnalysisState();
    // Simulate LIVE re-ingestion of the same window
    for (let i = 0; i < 5; i++) {
      ingestAnalysisInput(state, {
        frame: frameAt(29, {
          agent_count: 2,
          runtime: 'TwoAgentRuntime',
          header: {
            runtime_model: 'TwoAgentRuntime',
            agent_body_mapping: [
              { agent_id: 'agent_0', body_id: 'body-0', agent_seed: 143 },
              { agent_id: 'agent_1', body_id: 'body-1', agent_seed: 144 },
            ],
          },
          frame: {
            agents_observer: [
              { observer_id: 'agent_0', agent_seed: 143, action_counts: { WAIT: 15, 'MOVE:N': 15 } },
              { observer_id: 'agent_1', agent_seed: 144, action_counts: { WAIT: 30 } },
            ],
          },
        }),
        timeline,
        events: [
          {
            type: 'PHYSICAL_SIGNAL_RECEIVED',
            tick: 10,
            receiver_agent_id: 'agent_1',
            evidence: {
              emission_id: 'recv-parent',
              receiver_agent_id: 'agent_1',
              'local.FIELD_B': 0.2,
              source_attribution: 'UNKNOWN_NOT_UNIQUE',
              contributing_emissions_this_tick: [
                { emission_id: 'e10', emitter_agent_id: 'agent_0', channel: 'B' },
              ],
            },
          },
        ],
        mode: 'LIVE',
      });
    }
    const a = buildRunAnalysis(state, 'LIVE');
    assert.equal(a.coverage.unique_simulation_ticks, 30);
    assert.equal(a.interactions.contact_ticks, 3);
    const a0 = a.agents.find((x) => x.agent_id === 'agent_0')!;
    const a1 = a.agents.find((x) => x.agent_id === 'agent_1')!;
    assert.equal(a0.ticks_observed, 30);
    assert.equal(a1.ticks_observed, 30);
    assert.ok(Number(a0.actions.move_count) >= 1);
    assert.equal(Number(a1.actions.wait_pct) > 90 || Number(a1.actions.wait_count) >= 15, true);
    assert.equal(a1.interaction.cross_agent_signal_contributions, 1);
    for (const ep of a.interactions.contact_episodes) {
      assert.ok(ep.start <= ep.end);
    }
  });

  it('incremental ingest of the same tick thrice is idempotent', () => {
    const state = createAnalysisState();
    const row = tl(100, 'MOVE:E', 'agent_0', 1, 1);
    for (let i = 0; i < 3; i++) {
      ingestAnalysisInput(state, { frame: frameAt(100), timeline: [row], events: [], mode: 'LIVE' });
    }
    const a = buildRunAnalysis(state, 'LIVE');
    assert.equal(a.agents[0].ticks_observed, 1);
    assert.equal(Number(a.agents[0].actions.move_count), 1);
    assert.equal(a.coverage.timeline_samples, 3);
    assert.equal(a.coverage.unique_simulation_ticks, 1);
  });
});
