import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { buildCompositeMotorForensics } from './compositeMotorForensics.ts';

describe('compositeMotorForensics', () => {
  it('detects COMPOSITE_MOTOR_V1 and MOVE+NECK same tick via neck event', () => {
    const rows = [
      { tick: 10, agent_id: 'agent_1', action: 'MOVE:E', action_source: 'COMPOSITE_FACTORIZED', osc_emit_active: false, head_omega: 0.1 },
      { tick: 11, agent_id: 'agent_1', action: 'OSC_EMIT', action_source: 'COMPOSITE_FACTORIZED', osc_emit_active: true, osc_emit_remaining: 5 },
      { tick: 12, agent_id: 'agent_1', action: 'MOVE:E', action_source: 'COMPOSITE_FACTORIZED', osc_emit_active: true, osc_emit_remaining: 4 },
    ];
    const events = [
      { tick: 10, type: 'NECK_MOTOR_APPLIED', agent_id: 'agent_1', evidence: { neck_motor: -1 } },
      { tick: 11, type: 'OSC_EMISSION_STARTED', agent_id: 'agent_1', evidence: {} },
    ];
    const cm = buildCompositeMotorForensics(rows, events, 12);
    assert.equal(cm.schema, 'COMPOSITE_MOTOR_V1');
    assert.equal(cm.authoritative, true);
    assert.ok(cm.named_combinations['MOVE+NECK'] >= 1);
    const a1 = cm.agents.agent_1;
    assert.equal(a1.control_vs_effector.OSC_EMIT_selections, 1);
    assert.ok(a1.control_vs_effector.emission_active_ticks >= 2);
    assert.notEqual(a1.control_vs_effector.emission_active_ticks, a1.control_vs_effector.OSC_EMIT_selections);
  });

  it('keeps legacy schema without composite sources', () => {
    const cm = buildCompositeMotorForensics(
      [{ tick: 1, agent_id: 'agent_0', action: 'WAIT', action_source: 'ENDOGENOUS_VARIATION' }],
      [],
      1,
    );
    assert.equal(cm.schema, 'LEGACY_SINGLE_SLOT');
    assert.equal(cm.authoritative, false);
  });
});
