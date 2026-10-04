import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { classifyHearingPlayback } from './hearingPlaybackStatus.ts';

describe('honest hearing playback classification', () => {
  it('stopped when not listening', () => {
    const c = classifyHearingPlayback({ listening: false, sourceMode: 'World', sourceAvailable: true });
    assert.equal(c.status, 'STOPPED');
  });

  it('suspended AudioContext is not silent success', () => {
    const c = classifyHearingPlayback({
      listening: true,
      audioContextState: 'suspended',
      sourceAvailable: true,
      sourceMode: 'World',
      mappedAmplitudes: [0.4],
    });
    assert.equal(c.status, 'AUDIO CONTEXT SUSPENDED');
  });

  it('nonzero mapped source with running context is LIVE · SIGNAL', () => {
    const c = classifyHearingPlayback({
      listening: true,
      audioContextState: 'running',
      sourceAvailable: true,
      sourceMode: 'agent_0',
      mappedAmplitudes: [0.2, 0.0],
      masterVolume: 0.7,
    });
    assert.equal(c.status, 'LIVE · SIGNAL');
    assert.ok(c.signalLevel > 0);
  });

  it('true zero is labelled, not silent success', () => {
    const c = classifyHearingPlayback({
      listening: true,
      audioContextState: 'running',
      sourceAvailable: true,
      trueZero: true,
      mappedAmplitudes: [0, 0],
      sourceMode: 'World',
    });
    assert.equal(c.status, 'LIVE · TRUE ZERO');
  });

  it('missing source is NO SOURCE / UNAVAILABLE, not silence', () => {
    const live = classifyHearingPlayback({
      listening: true,
      audioContextState: 'running',
      sourceAvailable: false,
      sourceMode: 'agent_1',
    });
    assert.equal(live.status, 'LIVE · NO SOURCE');
    const stopped = classifyHearingPlayback({
      listening: false,
      sourceAvailable: false,
      sourceMode: 'agent_1',
    });
    assert.equal(stopped.status, 'STOPPED');
  });

  it('output error is distinct', () => {
    const c = classifyHearingPlayback({
      listening: true,
      outputError: true,
      sourceMode: 'World',
    });
    assert.equal(c.status, 'OUTPUT ERROR');
  });
});
