/** Audio backend adapter — real Web Audio or fake for tests. */

export type AudioBackendState = 'closed' | 'suspended' | 'running' | 'unavailable';

export type AudioBackend = {
  kind: 'web' | 'fake';
  state(): AudioBackendState;
  sampleRate(): number;
  resume(): Promise<AudioBackendState>;
  setBandGains(gains: number[], rampSeconds: number, when?: number): void;
  setMasterGain(gain: number, rampSeconds?: number): void;
  silence(rampSeconds: number): void;
  currentTime(): number;
  teardown(): void;
  limiterActivations(): number;
  /** Fake-only schedule log */
  _log?: Array<Record<string, unknown>>;
};

export type FakeAudioBackend = AudioBackend & {
  _log: Array<Record<string, unknown>>;
  _gains: number[];
  _master: number;
  _state: AudioBackendState;
  _time: number;
  _limiter: number;
};

export function createFakeAudioBackend(): FakeAudioBackend {
  const fake: FakeAudioBackend = {
    kind: 'fake',
    _log: [],
    _gains: [0, 0, 0, 0, 0, 0],
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
    setBandGains(gains, rampSeconds, when) {
      fake._gains = gains.map((g) => Math.max(0, Number(g) || 0));
      const peak = fake._gains.reduce((a, b) => a + b, 0) * Math.max(0, fake._master);
      if (peak > 0.95) fake._limiter += 1;
      fake._log.push({ op: 'setBandGains', gains: [...fake._gains], rampSeconds, when });
    },
    setMasterGain(gain, rampSeconds = 0.01) {
      fake._master = Math.max(0, Math.min(1, Number(gain) || 0));
      fake._log.push({ op: 'setMasterGain', gain: fake._master, rampSeconds });
    },
    silence(rampSeconds) {
      fake._gains = [0, 0, 0, 0, 0, 0];
      fake._log.push({ op: 'silence', rampSeconds });
    },
    currentTime() { return fake._time; },
    teardown() {
      fake._state = 'closed';
      fake._gains = [0, 0, 0, 0, 0, 0];
      fake._log.push({ op: 'teardown' });
    },
    limiterActivations() { return fake._limiter; },
  };
  return fake;
}

export function createWebAudioBackend(carriersHz: number[]): AudioBackend {
  const AC = (typeof window !== 'undefined'
    ? (window.AudioContext || (window as any).webkitAudioContext)
    : null) as (typeof AudioContext) | null;
  if (!AC) {
    return {
      kind: 'web',
      state: () => 'unavailable',
      sampleRate: () => 0,
      async resume() { return 'unavailable'; },
      setBandGains() {},
      setMasterGain() {},
      silence() {},
      currentTime: () => 0,
      teardown() {},
      limiterActivations: () => 0,
    };
  }
  const ctx = new AC();
  const oscillators: OscillatorNode[] = [];
  const bandGains: GainNode[] = [];
  const master = ctx.createGain();
  master.gain.value = 0;
  let limiterCount = 0;
  // DynamicsCompressor as conservative playback limiter
  const limiter = ctx.createDynamicsCompressor();
  limiter.threshold.value = -3;
  limiter.knee.value = 6;
  limiter.ratio.value = 12;
  limiter.attack.value = 0.003;
  limiter.release.value = 0.1;
  master.connect(limiter);
  limiter.connect(ctx.destination);

  for (let i = 0; i < carriersHz.length; i += 1) {
    const osc = ctx.createOscillator();
    osc.type = 'sine';
    osc.frequency.value = carriersHz[i];
    const g = ctx.createGain();
    g.gain.value = 0;
    osc.connect(g);
    g.connect(master);
    osc.start();
    oscillators.push(osc);
    bandGains.push(g);
  }

  const backend: AudioBackend = {
    kind: 'web',
    state() {
      return ctx.state as AudioBackendState;
    },
    sampleRate() { return ctx.sampleRate; },
    async resume() {
      try {
        if (ctx.state === 'closed') return 'closed';
        await ctx.resume();
      } catch {
        /* autoplay rejection */
      }
      return ctx.state as AudioBackendState;
    },
    setBandGains(gains, rampSeconds, when) {
      const t = when ?? ctx.currentTime;
      const ramp = Math.max(0.001, rampSeconds);
      let sum = 0;
      for (let i = 0; i < bandGains.length; i += 1) {
        const target = Math.max(0, Number(gains[i]) || 0);
        sum += target;
        const param = bandGains[i].gain;
        param.cancelScheduledValues(t);
        param.setValueAtTime(param.value, t);
        param.linearRampToValueAtTime(target, t + ramp);
      }
      if (sum * master.gain.value > 0.95) limiterCount += 1;
    },
    setMasterGain(gain, rampSeconds = 0.02) {
      const t = ctx.currentTime;
      const target = Math.max(0, Math.min(1, Number(gain) || 0));
      master.gain.cancelScheduledValues(t);
      master.gain.setValueAtTime(master.gain.value, t);
      master.gain.linearRampToValueAtTime(target, t + Math.max(0.001, rampSeconds));
    },
    silence(rampSeconds) {
      backend.setBandGains([0, 0, 0, 0, 0, 0], rampSeconds);
    },
    currentTime() { return ctx.currentTime; },
    teardown() {
      try {
        for (const g of bandGains) {
          g.gain.cancelScheduledValues(0);
          g.gain.value = 0;
        }
        master.gain.value = 0;
        for (const o of oscillators) {
          try { o.stop(); } catch { /* */ }
          try { o.disconnect(); } catch { /* */ }
        }
        for (const g of bandGains) {
          try { g.disconnect(); } catch { /* */ }
        }
        try { master.disconnect(); } catch { /* */ }
        try { limiter.disconnect(); } catch { /* */ }
        void ctx.close();
      } catch { /* */ }
    },
    limiterActivations() { return limiterCount; },
  };
  return backend;
}
