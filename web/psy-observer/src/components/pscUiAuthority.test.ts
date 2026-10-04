import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  currentRuntimePresentation,
  deferredMotorStatus,
  liveMotorStatus,
  nextRunInitialLabel,
  nextRunScheduleLabel,
} from './pscUiAuthority.ts';

describe('PSC UI authority helpers', () => {
  it('missing live overlay is unavailable, not inferred from draft', () => {
    const p = currentRuntimePresentation(null);
    assert.equal(p.unavailable, true);
    assert.equal(p.pscLabel, 'unavailable');
    assert.equal(p.summary, 'unavailable');
  });

  it('runtime OFF + armed schedule before tick 1000', () => {
    const p = currentRuntimePresentation({
      psc: 'OFF', schedule: 1000, armed: true, withhold_opened: false,
    });
    assert.equal(p.pscLabel, 'OFF');
    assert.equal(p.summary, 'OFF · scheduled at tick 1000');
    assert.equal(p.armedLabel, 'armed');
    assert.equal(p.scheduleLabel, 'Tick 1000');
  });

  it('runtime ON after tick 1000 with enabled-at and transition count', () => {
    const p = currentRuntimePresentation({
      psc: 'ON',
      schedule: 1000,
      armed: false,
      activated_tick: 1000,
      transition_count: 1,
      withhold_opened: true,
    });
    assert.equal(p.pscLabel, 'ON');
    assert.equal(p.summary, 'ON · enabled at tick 1000');
    assert.equal(p.transitionCount, '1');
    assert.equal(p.armedLabel, 'disarmed');
    assert.equal(p.withholdLabel, 'open');
  });

  it('MANUAL and schedule 0 and 5000 are represented', () => {
    assert.equal(currentRuntimePresentation({ psc: 'OFF', schedule: 'MANUAL', armed: false }).summary, 'no schedule applied');
    assert.equal(currentRuntimePresentation({ psc: 'OFF', schedule: 0, armed: true }).summary, 'OFF · scheduled at tick 0');
    assert.equal(currentRuntimePresentation({ psc: 'OFF', schedule: 5000, armed: true }).summary, 'OFF · scheduled at tick 5000');
  });

  it('draft OFF is explicitly next-run and does not replace runtime ON', () => {
    assert.equal(nextRunInitialLabel(false), 'OFF (next run)');
    assert.equal(nextRunScheduleLabel(1000), 'scheduled at tick 1000');
    assert.equal(deferredMotorStatus(false), 'NEXT RUN · INITIAL OFF');
    const live = currentRuntimePresentation({
      psc: 'ON', activated_tick: 1000, transition_count: 1, schedule: 1000, armed: false,
    });
    assert.equal(live.pscLabel, 'ON');
    assert.notEqual(live.summary, nextRunInitialLabel(false));
  });

  it('live motor status never uses unqualified READY — PSC OFF', () => {
    assert.equal(liveMotorStatus({ pscCurrentlyOn: false, observedComposite: true }), 'CURRENT RUNTIME · PSC OFF');
    assert.equal(liveMotorStatus({ pscCurrentlyOn: true, observedComposite: true }), 'CURRENT RUNTIME · EXPERIMENTAL');
    assert.doesNotMatch(liveMotorStatus({ pscCurrentlyOn: false, observedComposite: true }), /READY — PSC OFF/);
  });
});
