/**
 * Timeline agent filter must retain agent_1 cognition events when present.
 * Mirrors App.tsx eventCategory + agent filter semantics (observer-only).
 */
import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

function eventCategory(type: string) {
  const t = String(type || '').toUpperCase();
  if (t.includes('SIGNAL') || t.includes('FIELD')) return 'SIGNAL';
  if (t.includes('RESOURCE') || t.includes('WORK') || t.includes('CONVERT')) return 'RESOURCE';
  if (t.includes('BODY') || t.includes('DEFORM') || t.includes('SITE') || t.includes('MOTOR')) return 'BODY';
  if (t.includes('ACTION') || t.includes('DISCRETE')) return 'ACTION';
  if (t.includes('SCENARIO') || t.includes('PREDICTION') || t.includes('OBSERVATION')) return 'COGNITION';
  if (t.includes('MATERIAL')) return 'MATERIAL';
  return 'BODY';
}

function filterEvents(
  events: Array<Record<string, any>>,
  eventFilter: string,
  agentEventFilter: string,
) {
  return events.filter((e) => {
    if (eventFilter !== 'ALL' && eventCategory(e.type || e.kind) !== eventFilter) return false;
    if (agentEventFilter === 'ALL AGENTS') return true;
    const want = agentEventFilter === 'AGENT_0' ? 'agent_0' : 'agent_1';
    const id = e.actor_agent_id || e.agent_id || e.emitter_agent_id || e.receiver_agent_id;
    return id === want;
  });
}

describe('timeline agent cognition filter', () => {
  const events = [
    { type: 'SCENARIO_SELECTED', tick: 1, agent_id: 'agent_0', actor_agent_id: 'agent_0' },
    { type: 'SCENARIO_SELECTED', tick: 2, agent_id: 'agent_1', actor_agent_id: 'agent_1' },
    { type: 'DISCRETE_ACTION_SELECTED', tick: 3, agent_id: 'agent_1', actor_agent_id: 'agent_1' },
    { type: 'BODY_MOVED', tick: 4, agent_id: 'agent_0', actor_agent_id: 'agent_0' },
  ];

  it('ALL AGENTS keeps both agents cognition', () => {
    const vis = filterEvents(events, 'COGNITION', 'ALL AGENTS');
    assert.equal(vis.length, 2);
    assert.deepEqual(vis.map((e) => e.agent_id).sort(), ['agent_0', 'agent_1']);
  });

  it('AGENT_1 filter does not discard agent_1 cognition', () => {
    const vis = filterEvents(events, 'COGNITION', 'AGENT_1');
    assert.equal(vis.length, 1);
    assert.equal(vis[0].agent_id, 'agent_1');
  });

  it('AGENT_0 filter excludes agent_1 (by design, not a drop bug)', () => {
    const vis = filterEvents(events, 'COGNITION', 'AGENT_0');
    assert.equal(vis.length, 1);
    assert.equal(vis[0].agent_id, 'agent_0');
  });
});
