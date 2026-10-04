import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  BAND_COUNT,
  C1_PROFILE,
  C1_SCHEMA,
  C1_WARNING,
  CANONICAL_PLAYBACK_CARRIER_HZ,
  CARRIER_LABEL,
  FIXED_REFERENCE_GAIN,
  INPUT_QUEUE_CAPACITY,
  REQUIRED_C0_PROFILE,
  defaultC1Profile,
} from './c1Profile.ts';
import {
  admitSample,
  analyzerProgress,
  buildSchedule,
  c0c1Compatible,
  emptyDiagnostics,
  executionModePolicy,
  mapEnergyToAmplitude,
} from './c1Transform.ts';
import { C1PlaybackEngine } from './c1PlaybackEngine.ts';

describe('C1 profile identity', () => {
  it('versions schema/profile and references C0/probe', () => {
    const p = defaultC1Profile();
    assert.equal(p.schema, C1_SCHEMA);
    assert.equal(p.profile, C1_PROFILE);
    assert.equal(p.required_c0_profile, REQUIRED_C0_PROFILE);
    assert.equal(p.required_probe_schema, 'OBSERVER_ACOUSTIC_PROBE_V1');
    assert.equal(p.carrier_hz_are_physical, false);
    assert.equal(p.band_count, BAND_COUNT);
    assert.equal(p.canonical_playback_carrier_hz.length, 6);
    assert.ok(C1_WARNING.includes('NOT PHYSICAL Hz'));
    assert.ok(CARRIER_LABEL.includes('NOT PHYSICAL'));
  });
});

describe('C1 amplitude mapping', () => {
  it('zero → silence; monotonic sqrt; clamps invalid; does not mutate input', () => {
    const input = [0, 1, 4, -1, Number.NaN, 9];
    const copy = [...input];
    const m = mapEnergyToAmplitude(input, FIXED_REFERENCE_GAIN);
    assert.deepEqual(input, copy);
    assert.equal(m.mapped_amplitudes[0], 0);
    assert.equal(m.mapped_amplitudes[1], FIXED_REFERENCE_GAIN * 1);
    assert.equal(m.mapped_amplitudes[2], FIXED_REFERENCE_GAIN * 2);
    assert.equal(m.mapped_amplitudes[3], 0);
    assert.equal(m.mapped_amplitudes[4], 0);
    assert.equal(m.mapped_amplitudes[5], FIXED_REFERENCE_GAIN * 3);
    assert.ok(m.invalid_clamped >= 2);
    assert.ok(m.mapped_amplitudes[2] > m.mapped_amplitudes[1]);
  });

  it('no per-event normalization — relative energy preserved', () => {
    const a = mapEnergyToAmplitude([1, 0, 0, 0, 0, 0]);
    const b = mapEnergyToAmplitude([4, 0, 0, 0, 0, 0]);
    assert.ok(Math.abs(b.mapped_amplitudes[0] / a.mapped_amplitudes[0] - 2) < 1e-9);
  });
});

describe('C1 carriers', () => {
  it('six distinct playback carriers', () => {
    const set = new Set(CANONICAL_PLAYBACK_CARRIER_HZ);
    assert.equal(set.size, 6);
    assert.ok(c0c1Compatible(REQUIRED_C0_PROFILE, 'OBSERVER_ACOUSTIC_PROBE_V1'));
    assert.equal(c0c1Compatible('OTHER', 'OBSERVER_ACOUSTIC_PROBE_V1'), false);
  });
});

describe('C1 schedule determinism', () => {
  it('identical samples → identical schedule', () => {
    const profile = defaultC1Profile();
    const diag = emptyDiagnostics(64);
    const q1: any[] = [];
    const q2: any[] = [];
    const s1 = new Set<string>();
    const s2 = new Set<string>();
    const samples = [
      { sample_key: 'k1', scientific_tick: 1, anonymous_band_energies: [1, 0, 0, 0, 0, 0] },
      { sample_key: 'k2', scientific_tick: 2, anonymous_band_energies: [0, 4, 0, 0, 0, 0] },
    ];
    for (const s of samples) {
      admitSample(q1, s1, s, 'runA', profile, diag, { accept: true });
      admitSample(q2, s2, s, 'runA', profile, emptyDiagnostics(64), { accept: true });
    }
    assert.deepEqual(buildSchedule(q1, profile, 1), buildSchedule(q2, profile, 1));
  });
});

describe('C1 queue / modes / lifecycle (fake audio)', () => {
  it('dedupes polling; enable mid-run skips history; queue drop-oldest; MAX mute; teardown', async () => {
    const eng = new C1PlaybackEngine({ fake: true });
    const sample = {
      sample_key: 'OBSERVER_ACOUSTIC_PROBE_V1:10:p:0:0:g1',
      scientific_tick: 10,
      probe_id: 'observer-acoustic-probe-0',
      anonymous_band_energies: [1, 0, 0, 0, 0, 0],
    };
    // Before enable — retained history tracking
    eng.feedLatest(sample, 'LIVE');
    eng.feedLatest(sample, 'LIVE'); // poll dup into seen
    const st = await eng.enableListening();
    assert.equal(st, 'running');
    // Same retained sample must not play
    eng.feedLatest(sample, 'LIVE');
    assert.equal(eng.snapshot().diagnostics.rendered, 0);

    const next = {
      ...sample,
      sample_key: 'OBSERVER_ACOUSTIC_PROBE_V1:11:p:0:0:g1',
      scientific_tick: 11,
      anonymous_band_energies: [4, 0, 0, 0, 0, 0],
    };
    eng.feedLatest(next, 'LIVE');
    eng.feedLatest(next, 'LIVE'); // poll dedup
    assert.equal(eng.snapshot().diagnostics.rendered, 1);
    assert.ok(eng.snapshot().diagnostics.deduplicated >= 1);

    // Queue bound
    eng.disable();
    const eng2 = new C1PlaybackEngine({ fake: true });
    await eng2.enableListening();
    for (let i = 0; i < INPUT_QUEUE_CAPACITY + 5; i += 1) {
      admitSample(
        eng2.queue,
        eng2.seen,
        {
          sample_key: `k${i}`,
          scientific_tick: i,
          anonymous_band_energies: [1, 0, 0, 0, 0, 0],
        },
        eng2.runId,
        eng2.profile,
        eng2.diag,
        { accept: true },
      );
    }
    assert.ok(eng2.diag.dropped >= 5);
    assert.ok(eng2.queue.length <= INPUT_QUEUE_CAPACITY);

    // MAX policy
    assert.equal(executionModePolicy('MAX').mute, true);
    assert.equal(executionModePolicy('FAST').status, 'FAST_PLAYBACK_LOSSY_MONITORING');

    eng2.setExecutionMode('MAX');
    const before = eng2.snapshot().diagnostics.rendered;
    eng2.feedLatest({
      sample_key: 'max1',
      scientific_tick: 99,
      anonymous_band_energies: [9, 0, 0, 0, 0, 0],
    }, 'MAX');
    assert.equal(eng2.snapshot().diagnostics.rendered, before);

    // Pause / step semantics
    const eng3 = new C1PlaybackEngine({ fake: true });
    await eng3.enableListening();
    eng3.setPaused(true);
    eng3.feedLatest({
      sample_key: 'p1', scientific_tick: 1, anonymous_band_energies: [1, 0, 0, 0, 0, 0],
    }, 'LIVE');
    assert.equal(eng3.snapshot().diagnostics.rendered, 0);
    eng3.setPaused(false);
    // resume does not replay
    eng3.feedLatest({
      sample_key: 'p1', scientific_tick: 1, anonymous_band_energies: [1, 0, 0, 0, 0, 0],
    }, 'LIVE');
    // p1 was seen while paused → treated as history in seen; enable mid-run style
    // Actually while paused, feedLatest adds to seen without ignore — so p1 won't play. Good for no replay.
    eng3.feedLatest({
      sample_key: 'p2', scientific_tick: 2, anonymous_band_energies: [1, 0, 0, 0, 0, 0],
    }, 'LIVE');
    assert.equal(eng3.snapshot().diagnostics.rendered, 1);

    eng3.onRestore();
    assert.equal(eng3.snapshot().listening, false);
    assert.equal(eng3.snapshot().audioState, 'closed');
    assert.ok((eng3.backend as any) == null);
  });

  it('restore / runtime switch tears down; no autoplay without enable', () => {
    const eng = new C1PlaybackEngine({ fake: true });
    assert.equal(eng.snapshot().listening, false);
    assert.equal(eng.snapshot().audioState, 'closed');
    eng.setRunId('run-1');
    eng.onRestore();
    eng.setRunId('run-2');
    assert.equal(eng.snapshot().listening, false);
  });
});

describe('C1 analyzer progress', () => {
  it('finite has percent; indefinite null', () => {
    const a = analyzerProgress(3, 10);
    assert.equal(a.percent, 30);
    const b = analyzerProgress(5, 0);
    assert.equal(b.percent, null);
  });
});
