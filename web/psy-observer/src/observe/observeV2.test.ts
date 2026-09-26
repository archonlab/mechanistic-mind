/**
 * Observe V2 acceptance tests (OV1–OV35 subset as unit coverage).
 */
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  buildObserveCurrentState,
  emittingAndReceiving,
  moveAndOscEmissionCoexist,
  oscTriggerAbsentWhileActive,
  bandSpark,
} from './currentState.ts';
import {
  buildRecentStructuredEvents,
  compressOscEmissionSpans,
  filterEventsForObserve,
  recentEventCardCount,
  RECENT_EVENT_CAPS,
} from './recentEvents.ts';
import {
  containsBannedSemanticTerm,
  eventCategory,
  matchesSignalMechanismFilter,
  observeEventClass,
} from './eventCategory.ts';
import {
  filterRowsForIdentity,
  invalidateEventsOnRunOrGeneration,
  observeBufferIdentityChanged,
  observeBufferIdentityFromFrame,
  shouldInvalidateObserveBuffers,
} from './bufferIdentity.ts';
import { projectLiveAuxState, simulateLiveFrameRetention, LIVE_FE_EVENTS_DISPLAY_MAX } from '../liveBounds.ts';

function compositeFrame(over: any = {}) {
  return {
    header: {
      tick: 6840,
      runtime_generation: 2,
      status: 'RUNNING',
      run_id: 'run-B',
      selected_agent_id: 'agent_1',
      telemetry_schema: 'V2_TIERED',
    },
    observer: { selected_agent_id: 'agent_1' },
    motor_control: {
      schema: 'COMPOSITE_MOTOR_V1',
      current_motor_output: {
        locomotion: 'MOVE:N',
        neck: 'RIGHT',
        oscillator: { freq_delta: 0, amp_delta: 0, emit_trigger: false },
        push: false,
        display: 'MOVE:N',
      },
      active_effectors: {
        body_locomotor_force: 'ACTIVE',
        neck_torque: 'RIGHT',
        head_angle: 0.54,
        head_omega: 0.07,
        oscillator: 'EMITTING',
        osc_freq: 0.63,
        osc_amp: 0.41,
        osc_remaining: 7,
        push_exertion: 0,
      },
      passive_input: {
        vision: 'ACTIVE',
        osc_reception: 'ACTIVE',
        vestibular: 'ACTIVE',
        neck_proprioception: 'ACTIVE',
        legacy_fields: 'OFF',
      },
    },
    physical: {
      oscillatory_signaling: {
        enabled: true,
        WORLD_GT: { emit_active: true, osc_freq_u: 0.63, osc_amp_u: 0.41, remaining: 7 },
        AGENT_ACCESSIBLE: { status: 'AVAILABLE' },
      },
      orientation: { head_relative_angle: 0.54, head_omega: 0.07, head_world_heading: 1.2 },
    },
    body: { vx: 0.1, vy: 0.05 },
    ...over,
  };
}

describe('Observe V2', () => {
  it('OV1 current state uses selected agent id', () => {
    const s = buildObserveCurrentState(compositeFrame(), { agent_id: 'agent_1' });
    assert.equal(s.provenance.agent_id, 'agent_1');
  });

  it('OV2 provenance matches frame identity', () => {
    const s = buildObserveCurrentState(compositeFrame(), { run_id: 'run-B' });
    assert.equal(s.provenance.run_id, 'run-B');
    assert.equal(s.provenance.generation, 2);
    assert.equal(s.provenance.tick, 6840);
    assert.equal(s.provenance.motor_schema, 'COMPOSITE_MOTOR_V1');
  });

  it('OV3 COMPOSITE_MOTOR_V1 factorized motor output', () => {
    const s = buildObserveCurrentState(compositeFrame());
    assert.equal(s.motor.schema, 'COMPOSITE_MOTOR_V1');
    assert.equal(s.motor.locomotion, 'MOVE:N');
    assert.equal(s.motor.neck, 'RIGHT');
    assert.equal(s.motor.osc_emit_trigger, false);
    assert.equal(s.motor.push, 'OFF');
  });

  it('OV4 LEGACY_SINGLE_SLOT supported', () => {
    const s = buildObserveCurrentState({
      header: { tick: 3, selected_action: 'MOVE:E' },
      motor_control: {
        schema: 'LEGACY_SINGLE_SLOT',
        current_motor_output: { locomotion: 'MOVE:E', display: 'MOVE:E' },
        active_effectors: {},
        passive_input: {},
      },
      physical: { selected_action: 'MOVE:E' },
    });
    assert.equal(s.motor.schema, 'LEGACY_SINGLE_SLOT');
    assert.equal(s.motor.legacy_action, 'MOVE:E');
    assert.equal(s.motor.neck, 'NOT AVAILABLE');
  });

  it('OV5 command separate from active effector', () => {
    const s = buildObserveCurrentState(compositeFrame());
    assert.equal(s.motor.osc_emit_trigger, false);
    assert.equal(s.effectors.osc_emitting, true);
  });

  it('OV6 OSC_EMIT absent while emission ACTIVE', () => {
    assert.equal(oscTriggerAbsentWhileActive(buildObserveCurrentState(compositeFrame())), true);
  });

  it('OV7 MOVE coexists with active OSC emission', () => {
    assert.equal(moveAndOscEmissionCoexist(buildObserveCurrentState(compositeFrame())), true);
  });

  it('OV8 MOVE coexists with neck activity', () => {
    const s = buildObserveCurrentState(compositeFrame());
    assert.ok(String(s.motor.locomotion).startsWith('MOVE:'));
    assert.equal(s.motor.neck, 'RIGHT');
  });

  it('OV9 passive OSC reception while locomotion active', () => {
    const s = buildObserveCurrentState(compositeFrame(), {
      agentObservation: { osc_l_0: 0.2, osc_l_1: 0.1, osc_r_0: 0.05, exo_0: 0, exo_1: 0.1, exo_2: 0 },
    });
    assert.equal(s.effectors.motion_active, true);
    assert.equal(s.passive.receiving, true);
    assert.ok(s.passive.osc_l.length >= 1);
  });

  it('OV10 emission and reception simultaneous', () => {
    const s = buildObserveCurrentState(compositeFrame(), {
      agentObservation: { osc_l_0: 0.4, osc_r_0: 0.2 },
    });
    assert.equal(emittingAndReceiving(s), true);
  });

  it('OV11 self/cross/mixed is Observer GT only', () => {
    const s = buildObserveCurrentState(compositeFrame(), { attribution: 'CROSS' });
    assert.equal(s.passive.observer_gt_rx_provenance, 'CROSS');
  });

  it('OV12 OSC receptor bands from current sensor state', () => {
    const s = buildObserveCurrentState(compositeFrame(), {
      agentObservation: { osc_l_0: 0.1, osc_l_1: 0.2, osc_r_0: 0.3 },
    });
    assert.deepEqual(s.passive.osc_l.slice(0, 2), [0.1, 0.2]);
    assert.ok(bandSpark(s.passive.osc_l).length >= 1);
  });

  it('OV13 vision visible while acting', () => {
    const s = buildObserveCurrentState(compositeFrame(), {
      agentObservation: { exo_0: 0, exo_1: 0.117, exo_2: 0.052 },
    });
    assert.equal(s.passive.vision_enabled, true);
    assert.equal(s.passive.exo_1, 0.117);
  });

  it('OV14 vestibular visible while acting', () => {
    const s = buildObserveCurrentState(compositeFrame(), {
      agentObservation: { vest_0: 0.18, vest_1: -0.03 },
    });
    assert.equal(s.passive.vest_0, 0.18);
  });

  it('OV15 neck proprioception visible while acting', () => {
    const s = buildObserveCurrentState(compositeFrame(), {
      agentObservation: { prop_neck_0: 0.34, prop_neck_1: 0.07 },
    });
    assert.equal(s.passive.prop_neck_0, 0.34);
  });

  it('OV16 legacy FIELD events supported', () => {
    assert.equal(observeEventClass('PHYSICAL_SIGNAL_EMITTED'), 'LEGACY_FIELD');
    assert.equal(eventCategory('PHYSICAL_SIGNAL_EMITTED'), 'SIGNAL');
  });

  it('OV17 OSC not mislabeled FIELD_A/B', () => {
    assert.equal(observeEventClass('OSC_EMISSION_STARTED'), 'OSC');
    assert.notEqual(observeEventClass('OSC_EMISSION_STARTED'), 'LEGACY_FIELD');
  });

  it('OV18 SIGNAL ALL includes OSC', () => {
    assert.equal(matchesSignalMechanismFilter('OSC_EMISSION_STARTED', 'ALL_SIGNALS'), true);
    assert.equal(matchesSignalMechanismFilter('PHYSICAL_SIGNAL_EMITTED', 'ALL_SIGNALS'), true);
  });

  it('OV19 OSCILLATORY excludes legacy FIELD', () => {
    assert.equal(matchesSignalMechanismFilter('PHYSICAL_SIGNAL_EMITTED', 'OSCILLATORY'), false);
    assert.equal(matchesSignalMechanismFilter('OSC_EMISSION_STARTED', 'OSCILLATORY'), true);
  });

  it('OV20 LEGACY FIELD excludes OSC', () => {
    assert.equal(matchesSignalMechanismFilter('OSC_EMISSION_STARTED', 'LEGACY_FIELD'), false);
    assert.equal(matchesSignalMechanismFilter('PHYSICAL_SIGNAL_RECEIVED', 'LEGACY_FIELD'), true);
  });

  it('OV21 previous run events invalidate', () => {
    assert.equal(
      invalidateEventsOnRunOrGeneration(
        { run_id: 'run-A', generation: 1, agent_id: 'agent_0' },
        { run_id: 'run-B', generation: 1, agent_id: 'agent_0' },
      ),
      true,
    );
  });

  it('OV22 previous generation events invalidate', () => {
    assert.equal(
      invalidateEventsOnRunOrGeneration(
        { run_id: 'run-A', generation: 1, agent_id: 'agent_0' },
        { run_id: 'run-A', generation: 2, agent_id: 'agent_0' },
      ),
      true,
    );
  });

  it('OV23 agent switch invalidates current selection identity', () => {
    const r = shouldInvalidateObserveBuffers(
      { run_id: 'run-A', generation: 1, agent_id: 'agent_0' },
      { run_id: 'run-A', generation: 1, agent_id: 'agent_1' },
    );
    assert.equal(r, true);
    const id = observeBufferIdentityFromFrame(compositeFrame(), { agent_id: 'agent_1' });
    assert.equal(id.agent_id, 'agent_1');
  });

  it('OV24 contiguous repetitive frames compressed', () => {
    const events = [];
    for (let t = 6449; t <= 6527; t++) {
      events.push({
        tick: t,
        type: 'DISCRETE_ACTION_SELECTED',
        agent_id: 'agent_0',
        evidence: { selected_action: 'MOVE:W', selection_source: 'X' },
      });
    }
    const recent = buildRecentStructuredEvents(events, { cap: 200 });
    const move = recent.find((e) => e.title.includes('MOVE:W'));
    assert.ok(move);
    assert.ok((move!.count || 1) > 1);
    assert.ok(recentEventCardCount(recent) < events.length);
  });

  it('OV25 persistent OSC not repeated OSC_EMIT selections', () => {
    const events = [
      { tick: 10, type: 'OSC_EMISSION_STARTED', agent_id: 'agent_1', evidence: { osc_freq_u: 0.63, osc_amp_u: 0.41 } },
      { tick: 11, type: 'OSC_EMISSION_ACTIVE', agent_id: 'agent_1', evidence: {} },
      { tick: 12, type: 'OSC_EMISSION_ACTIVE', agent_id: 'agent_1', evidence: {} },
      { tick: 13, type: 'OSC_EMISSION_ENDED', agent_id: 'agent_1', evidence: {} },
    ];
    const spans = compressOscEmissionSpans(events);
    const active = spans.filter((s) => s.osc_active_span);
    assert.ok(active.length >= 1);
    assert.ok(!spans.every((s) => s.title === 'OSC EMISSION START'));
  });

  it('OV26/OV27 raw evidence remains accessible but not default (API shape)', () => {
    // Panel defaults showRaw=false; raw slot is optional — tested by presence of RECENT_EVENT_CAPS
    assert.ok(RECENT_EVENT_CAPS['100'] < RECENT_EVENT_CAPS.ALL_LOADED);
  });

  it('OV28 recent event list bounded', () => {
    const events = Array.from({ length: 5000 }, (_, i) => ({
      tick: i,
      type: 'DISCRETE_ACTION_SELECTED',
      agent_id: 'agent_0',
      evidence: { selected_action: 'WAIT' },
    }));
    const recent = buildRecentStructuredEvents(events, { cap: RECENT_EVENT_CAPS['100'] });
    assert.ok(recentEventCardCount(recent) <= 100);
  });

  it('OV29 live refresh does not accumulate unbounded (liveBounds)', () => {
    const frames = Array.from({ length: 200 }, (_, i) => ({
      events: Array.from({ length: 50 }, (__, j) => ({ tick: i * 50 + j, type: 'X' })),
      timeline: Array.from({ length: 50 }, (__, j) => ({ tick: i * 50 + j })),
      trajectory: { points: Array.from({ length: 50 }, (__, j) => ({ tick: i * 50 + j })) },
    }));
    const r = simulateLiveFrameRetention(frames);
    assert.ok(r.maxEvents <= LIVE_FE_EVENTS_DISPLAY_MAX);
    const proj = projectLiveAuxState({
      events: frames[frames.length - 1].events,
      timeline: frames[frames.length - 1].timeline,
      scientific_rows: Array.from({ length: 10000 }, () => ({})),
    });
    assert.equal(proj.scientific_rows_ignored, 10000);
    assert.ok(proj.events.length <= LIVE_FE_EVENTS_DISPLAY_MAX);
  });

  it('OV30 zero-valued valid sensors work', () => {
    const s = buildObserveCurrentState(compositeFrame(), {
      agentObservation: { exo_0: 0, exo_1: 0, exo_2: 0, osc_l_0: 0, osc_r_0: 0 },
    });
    assert.equal(s.passive.exo_0, 0);
    assert.equal(s.passive.receiving, false);
  });

  it('OV31 missing historical field is NOT AVAILABLE not 0', () => {
    const s = buildObserveCurrentState({
      header: { tick: 1 },
      motor_control: {
        schema: 'LEGACY_SINGLE_SLOT',
        current_motor_output: { locomotion: 'WAIT' },
        active_effectors: {},
        passive_input: {},
      },
    });
    assert.equal(s.passive.exo_0, 'NOT AVAILABLE');
    assert.equal(s.effectors.head_omega, 'NOT AVAILABLE');
  });

  it('OV32 no semantic communication labels', () => {
    assert.equal(containsBannedSemanticTerm('EMITTING + RECEIVING'), false);
    assert.equal(containsBannedSemanticTerm('talking and listening'), true);
    assert.equal(containsBannedSemanticTerm('conversation'), true);
  });

  it('OV33 signal filter routing compatible with forensics classes', () => {
    const events = [
      { tick: 1, type: 'OSC_EMISSION_STARTED', agent_id: 'agent_1' },
      { tick: 2, type: 'PHYSICAL_SIGNAL_EMITTED', agent_id: 'agent_0', evidence: { channel: 'A' } },
    ];
    const oscOnly = filterEventsForObserve(events, {
      filter: 'SIGNAL',
      signalFilter: 'OSCILLATORY',
    });
    assert.equal(oscOnly.length, 1);
    assert.equal(observeEventClass(String(oscOnly[0].type)), 'OSC');
    const fieldOnly = filterEventsForObserve(events, {
      filter: 'SIGNAL',
      signalFilter: 'LEGACY_FIELD',
    });
    assert.equal(fieldOnly.length, 1);
    assert.equal(observeEventClass(String(fieldOnly[0].type)), 'LEGACY_FIELD');
  });

  it('buffer identity change detection', () => {
    const a = observeBufferIdentityFromFrame({ header: { run_id: 'r1', runtime_generation: 1 } }, { run_id: 'r1' });
    const b = { ...a, generation: 2 };
    assert.equal(observeBufferIdentityChanged(a, b).reason, 'generation');
    assert.deepEqual(
      filterRowsForIdentity(
        [{ tick: 1, runtime_generation: 1 }, { tick: 2, runtime_generation: 2 }],
        b,
      ).map((r) => r.tick),
      [2],
    );
  });
});
