import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { createAnalysisState, ingestXy, makeAgentAgg, wrapDelta } from './aggregates.ts';
import { ingestAnalysisInput } from './runAnalysis.ts';

describe('WRAP minimum-image wrapDelta', () => {
  it('east and west crossings have correct sign', () => {
    assert.ok(Math.abs(wrapDelta(31.9, 0.1, 32) - 0.2) < 1e-9);
    assert.ok(Math.abs(wrapDelta(0.1, 31.9, 32) + 0.2) < 1e-9);
  });

  it('north and south crossings', () => {
    assert.ok(Math.abs(wrapDelta(31.9, 0.1, 32) - 0.2) < 1e-9);
    assert.ok(Math.abs(wrapDelta(0.1, 31.9, 32) + 0.2) < 1e-9);
  });

  it('does not invent a 32-cell jump', () => {
    assert.ok(Math.abs(wrapDelta(31.9, 0.1, 32)) < 1.0);
  });
});

describe('unwrapped unique-tick trajectory', () => {
  it('does not inflate path on duplicate Observer samples', () => {
    const agg = makeAgentAgg('agent_0', 'body-0');
    ingestXy(agg, 1, 1, 0.1, 10, 32, 32);
    ingestXy(agg, 2, 1, 0.1, 11, 32, 32);
    const once = agg.path_length_euclidean;
    ingestXy(agg, 2.1, 1, 0.1, 11, 32, 32); // duplicate tick
    assert.equal(agg.path_length_euclidean, once);
    assert.equal(agg.duplicate_observer_samples_ignored, 1);
    assert.ok(agg.path_length_manhattan_wrap > 0);
  });

  it('unwraps WRAP_PERIODIC eastward crossing', () => {
    const agg = makeAgentAgg('agent_0', 'body-0');
    ingestXy(agg, 30, 5, 0, 1, 32, 32);
    ingestXy(agg, 31, 5, 0, 2, 32, 32);
    ingestXy(agg, 0.5, 5, 0, 3, 32, 32);
    assert.ok(agg.unwrapped_dx > 2.0);
    assert.ok(agg.path_length_euclidean > 2.0);
    assert.ok(agg.path_length_euclidean < 5.0);
    assert.ok(Math.abs(agg.unwrapped_dy) < 1e-9);
    assert.ok(agg.boundary_crossings_x >= 1);
  });

  it('unwraps west, north, south, diagonal', () => {
    const west = makeAgentAgg('a', 'b');
    ingestXy(west, 0.3, 5, 0, 1, 32, 32);
    ingestXy(west, 31.9, 5, 0, 2, 32, 32);
    assert.ok(west.unwrapped_dx < -0.2);

    const north = makeAgentAgg('a', 'b');
    ingestXy(north, 5, 31.8, 0, 1, 32, 32);
    ingestXy(north, 5, 0.2, 0, 2, 32, 32);
    assert.ok(north.unwrapped_dy > 0.3);

    const south = makeAgentAgg('a', 'b');
    ingestXy(south, 5, 0.2, 0, 1, 32, 32);
    ingestXy(south, 5, 31.8, 0, 2, 32, 32);
    assert.ok(south.unwrapped_dy < -0.3);

    const diag = makeAgentAgg('a', 'b');
    ingestXy(diag, 31.8, 31.8, 0, 1, 32, 32);
    ingestXy(diag, 0.2, 0.2, 0, 2, 32, 32);
    assert.ok(diag.unwrapped_dx > 0);
    assert.ok(diag.unwrapped_dy > 0);
    assert.ok(diag.path_length_euclidean < 2);
  });

  it('multiple wraps accumulate without 32-cell jumps', () => {
    const agg = makeAgentAgg('a', 'b');
    let tick = 1;
    ingestXy(agg, 31.5, 10, 0, tick++, 32, 32);
    for (let i = 0; i < 5; i++) {
      ingestXy(agg, 0.2, 10, 0, tick++, 32, 32);
      ingestXy(agg, 31.6, 10, 0, tick++, 32, 32);
    }
    assert.ok(agg.path_length_euclidean < 20);
    assert.ok(agg.boundary_crossings_x >= 5);
  });

  it('skips path across evidence gaps', () => {
    const agg = makeAgentAgg('a', 'b');
    ingestXy(agg, 1, 1, 0, 1, 32, 32);
    ingestXy(agg, 2, 1, 0, 2, 32, 32);
    const mid = agg.path_length_euclidean;
    ingestXy(agg, 20, 20, 0, 50, 32, 32); // gap
    assert.equal(agg.path_length_euclidean, mid);
    assert.equal(agg.trajectory_gaps_skipped, 1);
  });

  it('attributes path to requested WAIT vs MOVE', () => {
    const agg = makeAgentAgg('a', 'b');
    agg.last_action = 'WAIT';
    ingestXy(agg, 1, 1, 0.1, 1, 32, 32);
    ingestXy(agg, 1.5, 1, 0.1, 2, 32, 32);
    assert.ok(agg.path_during_requested_WAIT > 0.4);
    agg.last_action = 'MOVE:E';
    ingestXy(agg, 2.5, 1, 0.2, 3, 32, 32);
    assert.ok(agg.path_during_requested_MOVE > 0.9);
  });

  it('tracks neighborhood replacement on cell change', () => {
    const agg = makeAgentAgg('a', 'b');
    ingestXy(agg, 5.2, 5.2, 0, 1, 32, 32);
    ingestXy(agg, 6.2, 5.2, 0, 2, 32, 32);
    assert.equal(agg.neighborhood_replacements, 1);
    assert.equal(agg.cell_boundary_crossings, 1);
  });
});

describe('LIVE last_xy must not poison trajectory', () => {
  it('path stays local when LIVE frame is ahead of timeline', () => {
    const state = createAnalysisState();
    const timeline1 = [];
    for (let t = 1; t <= 10; t++) {
      timeline1.push({
        tick: t,
        bodies: [{ agent_id: 'agent_0', x: 16 + t * 0.01, y: 16, action: 'WAIT', speed: 0.01 }],
      });
    }
    ingestAnalysisInput(state, {
      frame: {
        header: { tick: 50, seed: 17 },
        world: { width: 32, height: 32, boundary: 'WRAP_PERIODIC' },
        agents_observer: [{ observer_id: 'agent_0', x: 16.5, y: 10.0, vx: 0, vy: 0 }],
      },
      timeline: timeline1,
      mode: 'LIVE',
    });
    const timeline2 = [];
    for (let t = 1; t <= 20; t++) {
      timeline2.push({
        tick: t,
        bodies: [{ agent_id: 'agent_0', x: 16 + t * 0.01, y: 16, action: 'WAIT', speed: 0.01 }],
      });
    }
    ingestAnalysisInput(state, {
      frame: {
        header: { tick: 60, seed: 17 },
        world: { width: 32, height: 32, boundary: 'WRAP_PERIODIC' },
        agents_observer: [{ observer_id: 'agent_0', x: 16.6, y: 8.0, vx: 0, vy: 0 }],
      },
      timeline: timeline2,
      mode: 'LIVE',
    });
    const a = state.agents['agent_0'];
    assert.ok(a.path_length_euclidean < 0.5, `path inflated: ${a.path_length_euclidean}`);
    assert.ok(Math.abs(a.unwrapped_dy) < 0.5, `unwrapped_dy poisoned: ${a.unwrapped_dy}`);
    assert.ok(a.live_pose_xy != null);
    assert.equal(a.live_pose_xy!.y, 8.0);
  });
});
