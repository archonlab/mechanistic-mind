/**
 * Regression: HUD action strip treats agent_0 / index 0 as valid.
 * Root cause class: agents_observer missing for N=1 + body.selected_action absent.
 */
import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { hudActionRows } from './observerHudAction.ts';

describe('single-agent HUD action strip', () => {
  it('shows action from agents_observer for agent_0', () => {
    const rows = hudActionRows({
      agents_observer: [{ observer_id: 'agent_0', selected_action: 'MOVE:S' }],
      physical: { selected_action: 'WAIT' },
      header: {},
      body: {},
    }, 'agent_0');
    assert.equal(rows.length, 1);
    assert.equal(rows[0].id, 'agent_0');
    assert.equal(rows[0].actionLabel, 'MOVE:S');
  });

  it('falls back to physical.selected_action when agents_observer empty (legacy)', () => {
    const rows = hudActionRows({
      agents_observer: [],
      physical: { selected_action: 'OSC_EMIT' },
      header: { selected_action: 'WAIT' },
      body: {},
    }, 'agent_0');
    assert.equal(rows[0].actionLabel, 'OSC_EMIT');
  });

  it('does not treat index 0 / agent_0 as missing', () => {
    const rows = hudActionRows({
      agents_observer: [{ observer_id: 'agent_0', selected_action: 'WAIT' }],
      physical: {},
      header: {},
      body: {},
    }, 'agent_0');
    assert.ok(rows[0].id);
    assert.notEqual(rows[0].actionLabel, '—');
  });

  it('preserves two-agent strip', () => {
    const rows = hudActionRows({
      agents_observer: [
        { observer_id: 'agent_0', selected_action: 'MOVE:S' },
        { observer_id: 'agent_1', selected_action: 'NECK_RIGHT' },
      ],
      physical: { selected_action: 'MOVE:S' },
      header: {},
      body: {},
    }, 'agent_0');
    assert.equal(rows.length, 2);
    assert.equal(rows[1].actionLabel, 'NECK_RIGHT');
  });

  it('prefers composite_action_display over locomotor selected_action', () => {
    const rows = hudActionRows({
      agents_observer: [{
        observer_id: 'agent_0',
        selected_action: 'MOVE:W',
        composite_action_display: 'MOVE:W + NECK_RIGHT + OSC_FREQ_UP + OSC_AMP_DOWN + OSC_EMIT + PUSH',
      }],
      physical: { selected_action: 'MOVE:W' },
      header: {},
      body: {},
    }, 'agent_0');
    assert.equal(
      rows[0].actionLabel,
      'MOVE:W + NECK_RIGHT + OSC_FREQ_UP + OSC_AMP_DOWN + OSC_EMIT + PUSH',
    );
  });

  it('keeps two-agent composite motors independent', () => {
    const rows = hudActionRows({
      agents_observer: [
        { observer_id: 'agent_0', selected_action: 'MOVE:E', composite_action_display: 'MOVE:E' },
        { observer_id: 'agent_1', selected_action: 'WAIT', composite_action_display: 'WAIT + NECK_HOLD' },
      ],
      physical: { selected_action: 'MOVE:E' },
      header: {},
      body: {},
    }, 'agent_0');
    assert.equal(rows[0].actionLabel, 'MOVE:E');
    assert.equal(rows[1].actionLabel, 'WAIT + NECK_HOLD');
  });
});
