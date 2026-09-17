/**
 * Timeline compression + cognitive WAIT observability (observer presentation).
 */
import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { compressConsecutiveEvents, compressedEventSummary } from './eventCompression.ts';
import {
  buildRunAnalysis,
  createAnalysisState,
  ingestAnalysisInput,
} from './analysis/index.ts';

function eventCategory(type: string) {
  const t = String(type || '').toUpperCase();
  if (t.includes('SCENARIO') || t.includes('PREDICTION') || t.includes('OBSERVATION')) return 'COGNITION';
  if (t.includes('ACTION') || t.includes('DISCRETE')) return 'ACTION';
  return 'BODY';
}

function filterEvents(events: any[], eventFilter: string, agentEventFilter: string) {
  return events.filter((e) => {
    if (eventFilter !== 'ALL' && eventCategory(e.type || e.kind) !== eventFilter) return false;
    if (agentEventFilter === 'ALL AGENTS') return true;
    const want = agentEventFilter === 'AGENT_0' ? 'agent_0' : 'agent_1';
    const id = e.actor_agent_id || e.agent_id || e.emitter_agent_id || e.receiver_agent_id;
    return id === want;
  });
}

describe('cognitive WAIT timeline observability', () => {
  const events = [
    {
      type: 'SCENARIO_SELECTED', tick: 10, agent_id: 'agent_1', actor_agent_id: 'agent_1',
      evidence: { selected_action: 'WAIT', selection_source: 'PROSPECTIVE_SCENARIO', candidate_count: 5 },
    },
    {
      type: 'SCENARIO_SELECTED', tick: 11, agent_id: 'agent_1', actor_agent_id: 'agent_1',
      evidence: { selected_action: 'WAIT', selection_source: 'PROSPECTIVE_SCENARIO', candidate_count: 5 },
    },
    {
      type: 'SCENARIO_SELECTED', tick: 12, agent_id: 'agent_1', actor_agent_id: 'agent_1',
      evidence: { selected_action: 'WAIT', selection_source: 'PROSPECTIVE_SCENARIO', candidate_count: 5 },
    },
    {
      type: 'SCENARIO_SELECTED', tick: 10, agent_id: 'agent_0', actor_agent_id: 'agent_0',
      evidence: { selected_action: 'WAIT', selection_source: 'PROSPECTIVE_SCENARIO' },
    },
    {
      type: 'DISCRETE_ACTION_SELECTED', tick: 20, agent_id: 'agent_0', actor_agent_id: 'agent_0',
      evidence: { selected_action: 'WAIT', selection_source: 'ENDOGENOUS_VARIATION' },
    },
  ];

  it('F. Timeline COGNITION shows cognitive WAIT', () => {
    const vis = filterEvents(events, 'COGNITION', 'ALL AGENTS');
    assert.ok(vis.some((e) => e.evidence?.selected_action === 'WAIT' && e.type === 'SCENARIO_SELECTED'));
  });

  it('G. agent filter preserves correct identity', () => {
    const a1 = filterEvents(events, 'COGNITION', 'AGENT_1');
    assert.ok(a1.every((e) => (e.actor_agent_id || e.agent_id) === 'agent_1'));
    assert.equal(a1.length, 3);
  });

  it('J. long WAIT sequences compress for UI', () => {
    const vis = filterEvents(events, 'COGNITION', 'AGENT_1');
    const rows = compressConsecutiveEvents(vis);
    assert.equal(rows.length, 1);
    assert.equal(rows[0]._count, 3);
    assert.equal(rows[0]._tick_start, 10);
    assert.equal(rows[0]._tick_end, 12);
    const sum = compressedEventSummary(rows[0]);
    assert.match(sum, /WAIT/);
    assert.match(sum, /PROSPECTIVE_SCENARIO/);
    assert.match(sum, /3 consecutive/);
  });
});

describe('Analyze Results selection-source distinction', () => {
  it('I. cognitive WAIT counted separately from fallback WAIT', () => {
    const state = createAnalysisState();
    ingestAnalysisInput(state, {
      frame: {
        header: {
          tick: 50, seed: 143, runtime_generation: 1, runtime_model: 'TwoAgentRuntime',
          status: 'PAUSED', agent_count: 2,
          agent_body_mapping: [
            { agent_id: 'agent_0', body_id: 'body-0', agent_seed: 143 },
            { agent_id: 'agent_1', body_id: 'body-1', agent_seed: 144 },
          ],
        },
      },
      events: [
        {
          type: 'SCENARIO_SELECTED', tick: 1, agent_id: 'agent_1', actor_agent_id: 'agent_1',
          evidence: { selected_action: 'WAIT', selection_source: 'PROSPECTIVE_SCENARIO' },
        },
        {
          type: 'SCENARIO_SELECTED', tick: 2, agent_id: 'agent_1', actor_agent_id: 'agent_1',
          evidence: { selected_action: 'WAIT', selection_source: 'PROSPECTIVE_SCENARIO' },
        },
        {
          type: 'DISCRETE_ACTION_SELECTED', tick: 1, agent_id: 'agent_1', actor_agent_id: 'agent_1',
          evidence: { selected_action: 'WAIT', selection_source: 'PROSPECTIVE_SCENARIO' },
        },
        {
          type: 'DISCRETE_ACTION_SELECTED', tick: 2, agent_id: 'agent_1', actor_agent_id: 'agent_1',
          evidence: { selected_action: 'WAIT', selection_source: 'PROSPECTIVE_SCENARIO' },
        },
        {
          type: 'DISCRETE_ACTION_SELECTED', tick: 3, agent_id: 'agent_0', actor_agent_id: 'agent_0',
          evidence: { selected_action: 'WAIT', selection_source: 'ENDOGENOUS_VARIATION' },
        },
        {
          type: 'SCENARIO_SELECTED', tick: 4, agent_id: 'agent_0', actor_agent_id: 'agent_0',
          evidence: { selected_action: 'MOVE:N', selection_source: 'PROSPECTIVE_SCENARIO' },
        },
        {
          type: 'DISCRETE_ACTION_SELECTED', tick: 4, agent_id: 'agent_0', actor_agent_id: 'agent_0',
          evidence: { selected_action: 'MOVE:N', selection_source: 'PROSPECTIVE_SCENARIO' },
        },
      ],
      timeline: [],
    });
    const analysis = buildRunAnalysis(state, { status: 'PAUSED' });
    const a1 = analysis.agents.find((a) => a.agent_id === 'agent_1')!;
    const a0 = analysis.agents.find((a) => a.agent_id === 'agent_0')!;
    assert.equal(a1.cognition.cognitive_wait_selections, 2);
    assert.equal(a1.cognition.fallback_wait_selections, 0);
    assert.equal(a0.cognition.fallback_wait_selections, 1);
    assert.equal(a0.cognition.scenario_selected_move, 1);
    assert.equal(a1.cognition.scenario_selected_wait, 2);
  });
});
