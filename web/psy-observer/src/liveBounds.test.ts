/**
 * LIVE buffer retention + independence from scientific history length.
 */
import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  LIVE_FE_EVENTS_DISPLAY_MAX,
  LIVE_FE_TIMELINE_DISPLAY_MAX,
  LIVE_FE_TRAJECTORY_DISPLAY_MAX,
  projectLiveAuxState,
  retainRecent,
  simulateLiveFrameRetention,
} from './liveBounds.ts';
import { applyProjectionToFrame } from './observerProjection.ts';

function makeLiveFrame(tick: number, trajN = 80, eventN = 20) {
  const points = Array.from({ length: trajN }, (_, i) => ({ tick: tick - trajN + i, x: i, y: 0 }));
  const events = Array.from({ length: eventN }, (_, i) => ({
    tick: tick - eventN + i,
    type: 'TEST_EVENT',
    agent_id: 'agent_0',
  }));
  return {
    header: {
      tick,
      runtime_generation: 1,
      selected_agent_id: 'agent_0',
      status: 'RUNNING',
    },
    observer: { selected_agent_id: 'agent_0', inspected_tick: tick, runtime_generation: 1 },
    agents_views: {
      agent_0: {
        agent_id: 'agent_0',
        body_id: 'body-0',
        agent_seed: 17,
        tick,
        generation: 1,
        mind: { source_agent_id: 'agent_0', agent_id: 'agent_0', body_id: 'body-0', status: 'AVAILABLE' },
        body: { id: 'body-0', body_id: 'body-0', agent_id: 'agent_0', x: 1, y: 2 },
        physical: { source_agent_id: 'agent_0', body_id: 'body-0' },
        causal_chain: null,
        cognition_pipeline: null,
        prospection_view: null,
        perception: null,
      },
    },
    trajectory: { points, capacity: 2048, live_authority: 'live_recent_trajectory' },
    events,
    timeline: events.map((e) => ({ tick: e.tick, action: 'WAIT' })),
  };
}

describe('LIVE bounds', () => {
  it('retainRecent never exceeds cap', () => {
    const xs = Array.from({ length: 10_000 }, (_, i) => i);
    const out = retainRecent(xs, LIVE_FE_EVENTS_DISPLAY_MAX);
    assert.equal(out.length, LIVE_FE_EVENTS_DISPLAY_MAX);
    assert.equal(out[0], 10_000 - LIVE_FE_EVENTS_DISPLAY_MAX);
  });

  it('projectLiveAuxState ignores scientific_rows length (negative regression)', () => {
    const current = {
      timeline: Array.from({ length: 50 }, (_, i) => ({ tick: i })),
      events: Array.from({ length: 40 }, (_, i) => ({ tick: i, type: 'E' })),
      world_interventions: Array.from({ length: 10 }, (_, i) => ({ tick: i })),
    };
    const a = projectLiveAuxState({
      ...current,
      scientific_rows: Array.from({ length: 1_000 }, (_, i) => ({ tick: i })),
    });
    const b = projectLiveAuxState({
      ...current,
      scientific_rows: Array.from({ length: 100_000 }, (_, i) => ({ tick: i })),
    });
    assert.equal(a.timeline.length, b.timeline.length);
    assert.equal(a.events.length, b.events.length);
    assert.deepEqual(a.timeline, b.timeline);
    assert.deepEqual(a.events, b.events);
    assert.equal(a.scientific_rows_ignored, 1_000);
    assert.equal(b.scientific_rows_ignored, 100_000);
    assert.ok(a.timeline.length <= LIVE_FE_TIMELINE_DISPLAY_MAX);
    assert.ok(a.events.length <= LIVE_FE_EVENTS_DISPLAY_MAX);
  });

  it('repeated LIVE frames do not grow retained buffers unboundedly', () => {
    const frames = Array.from({ length: 5_000 }, (_, i) =>
      makeLiveFrame(i + 1, 200, 50),
    );
    const retained = simulateLiveFrameRetention(frames);
    assert.ok(retained.maxTrajectory <= LIVE_FE_TRAJECTORY_DISPLAY_MAX);
    assert.ok(retained.maxEvents <= LIVE_FE_EVENTS_DISPLAY_MAX);
    assert.ok(retained.maxTimeline <= LIVE_FE_TIMELINE_DISPLAY_MAX);
    assert.equal(retained.trajectory.length, Math.min(200, LIVE_FE_TRAJECTORY_DISPLAY_MAX));
  });

  it('applyProjectionToFrame result is independent of attached scientific_rows', () => {
    const base = makeLiveFrame(42);
    const withShort = {
      ...base,
      scientific_rows: Array.from({ length: 1_000 }, (_, i) => ({ tick: i, agent_id: 'agent_0' })),
    };
    const withLong = {
      ...base,
      scientific_rows: Array.from({ length: 100_000 }, (_, i) => ({ tick: i, agent_id: 'agent_0' })),
    };
    const p0 = applyProjectionToFrame(withShort, 'agent_0');
    const p1 = applyProjectionToFrame(withLong, 'agent_0');
    // Strip analyzer-only attachment; projection must match on live identity/body.
    assert.equal(p0.header?.tick, p1.header?.tick);
    assert.equal(p0.body?.x, p1.body?.x);
    assert.equal(p0.observer?.selected_agent_id, p1.observer?.selected_agent_id);
    assert.equal(p0.mind?.source_agent_id, p1.mind?.source_agent_id);
  });
});
