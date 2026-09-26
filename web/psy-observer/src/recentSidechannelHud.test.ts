/**
 * RECENT side-channel HUD: wall-clock persistence of applied non-locomotor motors.
 */
import assert from 'node:assert/strict';
import { describe, it, beforeEach } from 'node:test';
import {
  RECENT_WINDOW_MS,
  formatRecentSidechannelLabel,
  ingestFrameRecentSidechannels,
  ingestRecentSidechannels,
  observerSessionKey,
  resetRecentSidechannelHud,
  sidechannelTokensFromComposite,
  visibleRecentSidechannels,
} from './recentSidechannelHud.ts';

beforeEach(() => {
  resetRecentSidechannelHud();
});

describe('recent side-channel HUD', () => {
  it('primary tokens parse; locomotion is not recent', () => {
    assert.deepEqual(sidechannelTokensFromComposite('MOVE:E + NECK_LEFT'), ['NECK_LEFT']);
    assert.deepEqual(sidechannelTokensFromComposite('MOVE:E'), []);
    assert.deepEqual(sidechannelTokensFromComposite('WAIT'), []);
    assert.deepEqual(sidechannelTokensFromComposite('WAIT + NECK_HOLD'), ['NECK_HOLD']);
  });

  it('test1: current NECK on primary; recent survives locomotion-only then expires', () => {
    ingestRecentSidechannels({
      sessionKey: 's1', agentId: 'agent_0',
      compositeDisplay: 'MOVE:E + NECK_LEFT', now: 1000,
    });
    assert.deepEqual(visibleRecentSidechannels('agent_0', 1000), ['NECK_LEFT']);
    ingestRecentSidechannels({
      sessionKey: 's1', agentId: 'agent_0',
      compositeDisplay: 'MOVE:E', now: 1100,
    });
    assert.deepEqual(visibleRecentSidechannels('agent_0', 1100), ['NECK_LEFT']);
    assert.deepEqual(visibleRecentSidechannels('agent_0', 1000 + RECENT_WINDOW_MS), []);
  });

  it('test2: OSC_EMIT and OSC_FREQ expire independently', () => {
    ingestRecentSidechannels({
      sessionKey: 's1', agentId: 'agent_0',
      compositeDisplay: 'WAIT + OSC_EMIT', now: 0,
    });
    ingestRecentSidechannels({
      sessionKey: 's1', agentId: 'agent_0',
      compositeDisplay: 'WAIT + OSC_FREQ_UP', now: 400,
    });
    assert.deepEqual(visibleRecentSidechannels('agent_0', 400), ['OSC_EMIT', 'OSC_FREQ_UP']);
    assert.deepEqual(visibleRecentSidechannels('agent_0', 1000), ['OSC_FREQ_UP']);
    assert.deepEqual(visibleRecentSidechannels('agent_0', 1400), []);
  });

  it('test3: NECK_RIGHT replaces NECK_LEFT in the same domain', () => {
    ingestRecentSidechannels({
      sessionKey: 's1', agentId: 'agent_0',
      compositeDisplay: 'MOVE:E + NECK_LEFT', now: 0,
    });
    ingestRecentSidechannels({
      sessionKey: 's1', agentId: 'agent_0',
      compositeDisplay: 'MOVE:E + NECK_RIGHT', now: 200,
    });
    assert.deepEqual(visibleRecentSidechannels('agent_0', 200), ['NECK_RIGHT']);
  });

  it('test4: NECK_HOLD is retained', () => {
    ingestRecentSidechannels({
      sessionKey: 's1', agentId: 'agent_0',
      compositeDisplay: 'WAIT + NECK_HOLD', now: 0,
    });
    assert.deepEqual(visibleRecentSidechannels('agent_0', 0), ['NECK_HOLD']);
    assert.equal(formatRecentSidechannelLabel(['NECK_HOLD']), 'RECENT  NECK_HOLD');
  });

  it('test5: PUSH appears', () => {
    ingestRecentSidechannels({
      sessionKey: 's1', agentId: 'agent_0',
      compositeDisplay: 'MOVE:E + PUSH', now: 0,
    });
    assert.deepEqual(visibleRecentSidechannels('agent_0', 0), ['PUSH']);
  });

  it('test6: two agents stay isolated', () => {
    ingestRecentSidechannels({
      sessionKey: 's1', agentId: 'agent_0',
      compositeDisplay: 'MOVE:E + NECK_LEFT + OSC_EMIT', now: 0,
    });
    ingestRecentSidechannels({
      sessionKey: 's1', agentId: 'agent_1',
      compositeDisplay: 'MOVE:N + NECK_RIGHT + PUSH', now: 0,
    });
    assert.deepEqual(visibleRecentSidechannels('agent_0', 0), ['NECK_LEFT', 'OSC_EMIT']);
    assert.deepEqual(visibleRecentSidechannels('agent_1', 0), ['NECK_RIGHT', 'PUSH']);
  });

  it('test7: new session key clears RECENT', () => {
    ingestRecentSidechannels({
      sessionKey: 'gen1|50', agentId: 'agent_0',
      compositeDisplay: 'MOVE:E + OSC_EMIT', now: 0,
    });
    ingestFrameRecentSidechannels({
      header: { runtime_generation: 2, seed: 50 },
      agents_observer: [{ observer_id: 'agent_0', composite_action_display: 'MOVE:E' }],
    }, 10);
    assert.deepEqual(visibleRecentSidechannels('agent_0', 10), []);
    assert.equal(observerSessionKey({ header: { runtime_generation: 2, seed: 50 } }), '2|50|');
  });

  it('test8: locomotion-only never creates RECENT', () => {
    ingestRecentSidechannels({
      sessionKey: 's1', agentId: 'agent_0',
      compositeDisplay: 'MOVE:W', now: 0,
    });
    assert.deepEqual(visibleRecentSidechannels('agent_0', 0), []);
    ingestRecentSidechannels({
      sessionKey: 's1', agentId: 'agent_0',
      compositeDisplay: 'WAIT', now: 0,
    });
    assert.deepEqual(visibleRecentSidechannels('agent_0', 0), []);
  });

  it('identical paused republish does not refresh expiry', () => {
    const frame = {
      header: { runtime_generation: 1, seed: 7, tick: 40, display_tick: 40 },
      agents_observer: [{ observer_id: 'agent_0', composite_action_display: 'MOVE:E + OSC_EMIT' }],
    };
    ingestFrameRecentSidechannels(frame, 0);
    assert.equal(ingestFrameRecentSidechannels(frame, 900), false);
    assert.deepEqual(visibleRecentSidechannels('agent_0', 900), ['OSC_EMIT']);
    assert.deepEqual(visibleRecentSidechannels('agent_0', 1000), []);
  });
});
