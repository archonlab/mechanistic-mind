/**
 * Stereo playback audio backend — SAV2 translated L/R receptor monitor.
 * Separate from mono C1 AudioBackend; does not change C1 numerics.
 */
import type { AudioBackendState } from './c1AudioBackend.ts';

export type StereoAudioBackend = {
  kind: 'web' | 'fake';
  state(): AudioBackendState;
  sampleRate(): number;
  resume(): Promise<AudioBackendState>;
  /** Independent left/right band gains (6 each). No crossfeed. */
  setStereoBandGains(
    leftGains: number[],
    rightGains: number[],
    rampSeconds: number,
    when?: number,
  ): void;
  setMasterGain(gain: number, rampSeconds?: number): void;
  silence(rampSeconds: number): void;
  currentTime(): number;
  teardown(): void;
  limiterActivations(): number;
  _log?: Array<Record<string, unknown>>;
};

export type FakeStereoAudioBackend = StereoAudioBackend & {
  _log: Array<Record<string, unknown>>;
  _left: number[];
  _right: number[];
  _master: number;
  _state: AudioBackendState;
  _time: number;
  _limiter: number;
};

const Z6 = () => [0, 0, 0, 0, 0, 0];

export function createFakeStereoAudioBackend(): FakeStereoAudioBackend {
  const fake: FakeStereoAudioBackend = {
    kind: 'fake',
    _log: [],
    _left: Z6(),
    _right: Z6(),
    _master: 0,
    _state: 'suspended',
    _time: 0,
    _limiter: 0,
    state() { return fake._state; },
    sampleRate() { return 48000; },
    async resume() {
      fake._state = 'running';
      fake._log.push({ op: 'resume' });
      return fake._state;
    },
    setStereoBandGains(leftGains, rightGains, rampSeconds, when) {
      fake._left = leftGains.map((g) => Math.max(0, Number(g) || 0));
      fake._right = rightGains.map((g) => Math.max(0, Number(g) || 0));
      const peak =
        (fake._left.reduce((a, b) => a + b, 0) + fake._right.reduce((a, b) => a + b, 0))
        * Math.max(0, fake._master);
      if (peak > 0.95) fake._limiter += 1;
      fake._log.push({
        op: 'setStereoBandGains',
        left: [...fake._left],
        right: [...fake._right],
        rampSeconds,
        when,
      });
    },
    setMasterGain(gain, rampSeconds = 0.01) {
      fake._master = Math.max(0, Math.min(1, Number(gain) || 0));
      fake._log.push({ op: 'setMasterGain', gain: fake._master, rampSeconds });
    },
    silence(rampSeconds) {
      fake._left = Z6();
      fake._right = Z6();
      fake._log.push({ op: 'silence', rampSeconds });
    },
    currentTime() { return fake._time; },
    teardown() {
      fake._state = 'closed';
      fake._left = Z6();
      fake._right = Z6();
      fake._log.push({ op: 'teardown' });
    },
    limiterActivations() { return fake._limiter; },
  };
  return fake;
}

/**
 * Graph: 6 shared-frequency oscillators → L gain + R gain each → ChannelMerger(2)
 * → master → limiter → destination. No HRTF, crossfeed, or ITD.
 */
export function createWebStereoAudioBackend(carriersHz: number[]): StereoAudioBackend {
  const AC = (typeof window !== 'undefined'
    ? (window.AudioContext || (window as any).webkitAudioContext)
    : null) as (typeof AudioContext) | null;
  if (!AC) {
    return {
      kind: 'web',
      state: () => 'unavailable',
      sampleRate: () => 0,
      async resume() { return 'unavailable'; },
      setStereoBandGains() {},
      setMasterGain() {},
      silence() {},
      currentTime: () => 0,
      teardown() {},
      limiterActivations: () => 0,
    };
  }
  const ctx = new AC();
  const oscillators: OscillatorNode[] = [];
  const leftGains: GainNode[] = [];
  const rightGains: GainNode[] = [];
  const merger = ctx.createChannelMerger(2);
  const master = ctx.createGain();
  master.gain.value = 0;
  let limiterCount = 0;
  const limiter = ctx.createDynamicsCompressor();
  limiter.threshold.value = -3;
  limiter.knee.value = 6;
  limiter.ratio.value = 12;
  limiter.attack.value = 0.003;
  limiter.release.value = 0.1;
  merger.connect(master);
  master.connect(limiter);
  limiter.connect(ctx.destination);

  for (let i = 0; i < carriersHz.length; i += 1) {
    const osc = ctx.createOscillator();
    osc.type = 'sine';
    osc.frequency.value = carriersHz[i];
    const gL = ctx.createGain();
    const gR = ctx.createGain();
    gL.gain.value = 0;
    gR.gain.value = 0;
    osc.connect(gL);
    osc.connect(gR);
    gL.connect(merger, 0, 0); // left channel
    gR.connect(merger, 0, 1); // right channel
    osc.start();
    oscillators.push(osc);
    leftGains.push(gL);
    rightGains.push(gR);
  }

  const rampParam = (param: AudioParam, target: number, t: number, ramp: number) => {
    param.cancelScheduledValues(t);
    param.setValueAtTime(param.value, t);
    param.linearRampToValueAtTime(target, t + ramp);
  };

  const backend: StereoAudioBackend = {
    kind: 'web',
    state() { return ctx.state as AudioBackendState; },
    sampleRate() { return ctx.sampleRate; },
    async resume() {
      try {
        if (ctx.state === 'closed') return 'closed';
        await ctx.resume();
      } catch { /* autoplay */ }
      return ctx.state as AudioBackendState;
    },
    setStereoBandGains(lIn, rIn, rampSeconds, when) {
      const t = when ?? ctx.currentTime;
      const ramp = Math.max(0.001, rampSeconds);
      let sum = 0;
      for (let i = 0; i < leftGains.length; i += 1) {
        const tl = Math.max(0, Number(lIn[i]) || 0);
        const tr = Math.max(0, Number(rIn[i]) || 0);
        sum += tl + tr;
        rampParam(leftGains[i].gain, tl, t, ramp);
        rampParam(rightGains[i].gain, tr, t, ramp);
      }
      if (sum * master.gain.value > 0.95) limiterCount += 1;
    },
    setMasterGain(gain, rampSeconds = 0.02) {
      const t = ctx.currentTime;
      const target = Math.max(0, Math.min(1, Number(gain) || 0));
      rampParam(master.gain, target, t, Math.max(0.001, rampSeconds));
    },
    silence(rampSeconds) {
      backend.setStereoBandGains(Z6(), Z6(), rampSeconds);
    },
    currentTime() { return ctx.currentTime; },
    teardown() {
      try {
        for (const g of [...leftGains, ...rightGains]) {
          g.gain.cancelScheduledValues(0);
          g.gain.value = 0;
        }
        master.gain.value = 0;
        for (const o of oscillators) {
          try { o.stop(); } catch { /* */ }
          try { o.disconnect(); } catch { /* */ }
        }
        for (const g of [...leftGains, ...rightGains]) {
          try { g.disconnect(); } catch { /* */ }
        }
        try { merger.disconnect(); } catch { /* */ }
        try { master.disconnect(); } catch { /* */ }
        try { limiter.disconnect(); } catch { /* */ }
        void ctx.close();
      } catch { /* */ }
    },
    limiterActivations() { return limiterCount; },
  };
  return backend;
}
