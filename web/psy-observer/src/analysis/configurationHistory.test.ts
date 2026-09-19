import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  buildConfigurationHistory,
  collectWorldInterventions,
  formatConfigurationHistoryLog,
} from './configurationHistory.ts';

describe('configurationHistory Beta 2', () => {
  it('STATIC when no interventions', () => {
    const r = buildConfigurationHistory([], { start_tick: 0, end_tick: 100, initial_fingerprint: 'AAA' });
    assert.equal(r.configuration_history, 'STATIC');
    assert.equal(r.n_regimes, 1);
    assert.equal(r.n_interventions, 0);
  });

  it('MULTI_REGIME with regime boundaries', () => {
    const events = [
      {
        type: 'WORLD_INTERVENTION',
        event_id: 'a',
        simulation_tick: 10,
        category: 'ecology',
        changes: { 'climate_ecology.enabled': { old: false, new: true } },
        effective_world_fingerprint_before: 'AAA',
        effective_world_fingerprint_after: 'BBB',
        history_reset: false,
        cognition_reset: false,
        body_reset: false,
      },
      {
        type: 'WORLD_INTERVENTION',
        event_id: 'b',
        simulation_tick: 30,
        category: 'mechanism',
        changes: { 'mechanism.x': { old: true, new: false } },
        effective_world_fingerprint_before: 'BBB',
        effective_world_fingerprint_after: 'CCC',
        history_reset: false,
        cognition_reset: false,
        body_reset: false,
      },
    ];
    const r = buildConfigurationHistory(events, { start_tick: 0, end_tick: 50, initial_fingerprint: 'AAA' });
    assert.equal(r.configuration_history, 'MULTI_REGIME');
    assert.equal(r.n_interventions, 2);
    assert.equal(r.n_regimes, 3);
    assert.equal(r.regimes[0].tick_end, 9);
    assert.equal(r.regimes[1].tick_start, 10);
    assert.equal(r.regimes[2].tick_start, 30);
    const log = formatConfigurationHistoryLog(r).join('\n');
    assert.match(log, /CONFIGURATION HISTORY: MULTI-REGIME/);
    assert.match(log, /must not be treated/);
  });

  it('collects from frame.world_interventions', () => {
    const got = collectWorldInterventions({
      frame: {
        world_interventions: [{ type: 'WORLD_INTERVENTION', event_id: '1', simulation_tick: 5, changes: {} }],
      },
      events: [{ type: 'OTHER', tick: 1 }],
    });
    assert.equal(got.length, 1);
  });
});
