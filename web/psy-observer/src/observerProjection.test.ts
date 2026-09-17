import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  applyProjectionToFrame,
  compareViewsSameFrame,
  resolveSelectedProjection,
  shouldAcceptLiveFrame,
  validateAgentView,
} from './observerProjection.ts';

function view(agent: 'agent_0' | 'agent_1', seed: number, tick: number, generation: number, marker: string) {
  const body = agent === 'agent_0' ? 'body-0' : 'body-1';
  return {
    agent_id: agent,
    body_id: body,
    agent_seed: seed,
    tick,
    generation,
    mind: {
      source_agent_id: agent,
      agent_id: agent,
      body_id: body,
      agent_seed: seed,
      metrics: { observer_probe_marker: marker },
      memory: { keys: marker },
    },
    body: { id: body, body_id: body, agent_id: agent, x: agent === 'agent_0' ? 1 : 9 },
    physical: { source_agent_id: agent, body_id: body, selected_action: marker },
    causal_chain: { status: 'AVAILABLE' },
    cognition_pipeline: { status: 'AVAILABLE', stages: [] },
    prospection_view: { status: 'AVAILABLE', branches: [] },
    perception: { status: 'AVAILABLE' },
  };
}

function coherentFrame(tick = 10, generation = 3, baseSeed = 143) {
  return {
    header: {
      tick,
      runtime_generation: generation,
      seed: baseSeed,
      selected_agent_id: 'agent_0',
      selected_body_id: 'body-0',
      inspected_agent_seed: baseSeed,
    },
    observer: {
      selected_agent_id: 'agent_0',
      runtime_generation: generation,
      inspected_tick: tick,
    },
    mind: view('agent_0', baseSeed, tick, generation, 'A0').mind,
    body: view('agent_0', baseSeed, tick, generation, 'A0').body,
    agents_views: {
      agent_0: view('agent_0', baseSeed, tick, generation, 'FROM_AGENT_0'),
      agent_1: view('agent_1', baseSeed + 1, tick, generation, 'FROM_AGENT_1'),
    },
  };
}

describe('observer projection identity', () => {
  it('projects agent_0 and agent_1 with coherent identity tuples', () => {
    const frame = coherentFrame(10, 3, 143);
    const p0 = applyProjectionToFrame(frame, 'agent_0');
    const p1 = applyProjectionToFrame(frame, 'agent_1');
    assert.equal(p0.header.selected_agent_id, 'agent_0');
    assert.equal(p0.header.selected_body_id, 'body-0');
    assert.equal(p0.header.inspected_agent_seed, 143);
    assert.equal(p0.mind.source_agent_id, 'agent_0');
    assert.equal(p0.mind.metrics.observer_probe_marker, 'FROM_AGENT_0');
    assert.equal(p0.header.tick, 10);
    assert.equal(p0.header.runtime_generation, 3);

    assert.equal(p1.header.selected_agent_id, 'agent_1');
    assert.equal(p1.header.selected_body_id, 'body-1');
    assert.equal(p1.header.inspected_agent_seed, 144);
    assert.equal(p1.mind.source_agent_id, 'agent_1');
    assert.equal(p1.mind.metrics.observer_probe_marker, 'FROM_AGENT_1');
    assert.notEqual(p0.mind, p1.mind);
    assert.notDeepEqual(p0.mind.metrics, p1.mind.metrics);
  });

  it('A→B→A restores exact agent_0 mind metrics at same tick/generation', () => {
    const frame = coherentFrame(22, 5, 143);
    const a = applyProjectionToFrame(frame, 'agent_0');
    const b = applyProjectionToFrame(frame, 'agent_1');
    const a2 = applyProjectionToFrame(frame, 'agent_0');
    assert.deepEqual(a.mind.metrics, a2.mind.metrics);
    assert.equal(a.header.inspected_agent_seed, a2.header.inspected_agent_seed);
    assert.notEqual(b.mind.metrics.observer_probe_marker, a.mind.metrics.observer_probe_marker);
    const b2 = applyProjectionToFrame(frame, 'agent_1');
    assert.deepEqual(b.mind.metrics, b2.mind.metrics);
  });

  it('COMPARE uses same tick and generation for both sides', () => {
    const frame = coherentFrame(7, 2, 50);
    const cmp = compareViewsSameFrame(frame);
    assert.equal(cmp.ok, true);
    assert.equal(cmp.tick, 7);
    assert.equal(cmp.generation, 2);
    assert.equal(cmp.agent_0.tick, cmp.agent_1.tick);
    assert.equal(cmp.agent_0.generation, cmp.agent_1.generation);
    assert.equal(cmp.agent_0.agent_seed, 50);
    assert.equal(cmp.agent_1.agent_seed, 51);
  });

  it('negative: agent_1 selected but only agent_0 mind → NOT AVAILABLE, no leak', () => {
    const frame = coherentFrame(10, 1, 143) as any;
    delete frame.agents_views.agent_1;
    frame.header.selected_agent_id = 'agent_1';
    const p = applyProjectionToFrame(frame, 'agent_1');
    assert.equal(p.observer.projection_ok, false);
    assert.equal(p.mind.status, 'NOT AVAILABLE');
    assert.equal(p.mind.source_agent_id, 'agent_1');
    assert.equal(p.header.selected_agent_id, 'agent_1');
    assert.equal(p.header.selected_body_id, 'body-1');
    assert.equal(p.header.inspected_agent_seed, null);
    assert.equal(p.mind.metrics, undefined);
    assert.equal(p.mind.memory, undefined);
  });

  it('negative: wrong body_id / seed on agent_1 view is rejected', () => {
    const frame = coherentFrame(10, 1, 143) as any;
    frame.agents_views.agent_1.body_id = 'body-0';
    frame.agents_views.agent_1.body.body_id = 'body-0';
    const bad = validateAgentView(frame.agents_views.agent_1, 'agent_1', 10, 1);
    assert.equal(bad.ok, false);
    const p = resolveSelectedProjection(frame, 'agent_1');
    assert.equal(p.ok, false);
    assert.equal(p.mind.status, 'NOT AVAILABLE');
  });

  it('race: out-of-order live frame for old agent is rejected when selection pending', () => {
    const accept = shouldAcceptLiveFrame(
      { header: { selected_agent_id: 'agent_0' }, agents_views: {} },
      { desiredAgentId: 'agent_1', selectionSeq: 2, lastAcceptedSeq: 1, mode: 'LIVE' },
    );
    assert.equal(accept, false);
  });

  it('race: live frame with agents_views for desired agent is accepted and re-projectable', () => {
    const frame = coherentFrame();
    frame.header.selected_agent_id = 'agent_0';
    const accept = shouldAcceptLiveFrame(frame, {
      desiredAgentId: 'agent_1',
      selectionSeq: 2,
      lastAcceptedSeq: 1,
      mode: 'LIVE',
    });
    assert.equal(accept, true);
    const p = applyProjectionToFrame(frame, 'agent_1');
    assert.equal(p.mind.source_agent_id, 'agent_1');
    assert.equal(p.header.inspected_agent_seed, 144);
  });
});
