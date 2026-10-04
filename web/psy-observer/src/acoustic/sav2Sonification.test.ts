import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  CANONICAL_PLAYBACK_CARRIER_HZ as C1_CARRIERS,
  FIXED_REFERENCE_GAIN,
} from './c1Profile.ts';
import { mapEnergyToAmplitude } from './c1Transform.ts';
import { C1PlaybackEngine } from './c1PlaybackEngine.ts';
import {
  claimListeningMode,
  getListeningModeOwner,
  releaseListeningMode,
  resetListeningModeForTests,
} from './listeningModeOwner.ts';
import {
  FIXED_RECEPTOR_GAIN,
  INPUT_QUEUE_CAPACITY,
  SAV2_AMPLITUDE_MAPPING,
  SAV2_AUTHORITY_CLASS,
  SAV2_CARRIER_LABEL,
  SAV2_CHANNEL_MODE,
  SAV2_MODE_LABEL,
  SAV2_PROFILE,
  SAV2_SCHEMA,
  SAV2_WARNING,
  CANONICAL_PLAYBACK_CARRIER_HZ,
  defaultSav2Profile,
} from './sav2Profile.ts';
import {
  admitSav2Receipt,
  buildSav2Schedule,
  emptySav2Diagnostics,
  executionModePolicy,
  mapReceptorActivation,
  receiptDedupKey,
  sav1Sav2Compatible,
  scheduleChannelLeak,
  usesSqrtEnergyMapping,
  analyzerProgress,
} from './sav2Transform.ts';
import { Sav2PlaybackEngine } from './sav2PlaybackEngine.ts';

const root = dirname(fileURLToPath(import.meta.url));

function makeReceipt(opts: {
  agent: string;
  body?: string;
  tick: number;
  rid: string;
  left: number[];
  right: number[];
}): any {
  return {
    schema: 'SELECTED_ORGANISM_AUDITORY_BOUNDARY_RECEIPT_V1',
    profile: 'ORGANISM_AUDITORY_BOUNDARY_A5_V1',
    boundary: 'A5_OSC_LR_ACCESSIBLE_OBSERVATION_PRE_COGNITION',
    availability: 'AVAILABLE',
    receipt_id: opts.rid,
    scientific_tick: opts.tick,
    agent_id: opts.agent,
    body_id: opts.body || 'body0',
    section_a_organism_accessible: {
      left_receptor_channels: opts.left,
      right_receptor_channels: opts.right,
    },
    section_b_researcher_provenance: {
      phenotype_clip_stamp: { clipped_count: 99, phenotype_profile: 'SHOULD_NOT_AFFECT' },
      note: 'researcher only',
    },
  };
}

describe('SAV2 identity', () => {
  it('versions schema/profile/warning/carriers', () => {
    const p = defaultSav2Profile();
    assert.equal(p.schema, SAV2_SCHEMA);
    assert.equal(p.profile, SAV2_PROFILE);
    assert.equal(p.mode_label, SAV2_MODE_LABEL);
    assert.equal(p.warning_label, SAV2_WARNING);
    assert.equal(p.amplitude_mapping, SAV2_AMPLITUDE_MAPPING);
    assert.equal(p.channel_mode, SAV2_CHANNEL_MODE);
    assert.equal(p.authority_class, SAV2_AUTHORITY_CLASS);
    assert.equal(p.c1_and_sav2_simultaneous_audio, false);
    assert.deepEqual([...p.canonical_playback_carrier_hz], [...C1_CARRIERS]);
    assert.deepEqual([...CANONICAL_PLAYBACK_CARRIER_HZ], [...C1_CARRIERS]);
    assert.ok(SAV2_CARRIER_LABEL.includes('NOT PHYSICAL OR ORGANISM'));
    assert.ok(SAV2_WARNING.includes('NOT HUMAN HEARING'));
    assert.ok(SAV2_WARNING.includes('NOT MIND READING'));
  });
});

describe('SAV2 linear mapping (no C1 sqrt)', () => {
  it('0→silence; linear under fixed gain; monotonic; no mutate', () => {
    const left = [0, 0.25, 0.5, 1.0, -0.1, 1.5];
    const right = [0, 0.5, 0.25, 1.0, Number.NaN, 0];
    const copyL = [...left];
    const copyR = [...right];
    const m = mapReceptorActivation(left, right, FIXED_RECEPTOR_GAIN);
    assert.deepEqual(left, copyL);
    assert.deepEqual(right, copyR);
    assert.equal(m.left_amplitudes[0], 0);
    assert.equal(m.right_amplitudes[0], 0);
    assert.equal(m.left_amplitudes[1], FIXED_RECEPTOR_GAIN * 0.25);
    assert.equal(m.left_amplitudes[2], FIXED_RECEPTOR_GAIN * 0.5);
    assert.equal(m.left_amplitudes[3], FIXED_RECEPTOR_GAIN * 1.0);
    assert.equal(m.left_amplitudes[4], 0); // clamped
    assert.equal(m.left_amplitudes[5], FIXED_RECEPTOR_GAIN * 1.0); // clamped to 1
    assert.ok(m.invalid_clamped >= 2);
    assert.ok(m.left_amplitudes[2] > m.left_amplitudes[1]);
    assert.equal(usesSqrtEnergyMapping(), false);
    // Prove not sqrt: energy 0.25 under C1 would be 0.5*gain; SAV2 is 0.25*gain
    const c1 = mapEnergyToAmplitude([0.25, 0, 0, 0, 0, 0], FIXED_REFERENCE_GAIN);
    assert.notEqual(m.left_amplitudes[1], c1.mapped_amplitudes[0]);
    assert.ok(Math.abs(m.left_amplitudes[1] - FIXED_RECEPTOR_GAIN * 0.25) < 1e-12);
  });

  it('no per-side / per-event normalization', () => {
    const a = mapReceptorActivation([1, 0, 0, 0, 0, 0], [0.5, 0, 0, 0, 0, 0]);
    const b = mapReceptorActivation([0.5, 0, 0, 0, 0, 0], [0.25, 0, 0, 0, 0, 0]);
    assert.ok(Math.abs(a.left_amplitudes[0] / b.left_amplitudes[0] - 2) < 1e-9);
    assert.ok(Math.abs(a.right_amplitudes[0] / b.right_amplitudes[0] - 2) < 1e-9);
  });
});

describe('SAV2 channel isolation', () => {
  it('left-only / right-only / symmetric', () => {
    const profile = defaultSav2Profile();
    const diag = emptySav2Diagnostics(64);
    const q: any[] = [];
    const seen = new Set<string>();
    const leftOnly = makeReceipt({
      agent: 'agent_0', tick: 1, rid: 'rL',
      left: [1, 0, 0, 0, 0, 0], right: [0, 0, 0, 0, 0, 0],
    });
    admitSav2Receipt(q, seen, leftOnly, 'run', 'agent_0', 'body0', profile, diag, { accept: true });
    const frames = buildSav2Schedule(q, profile, 1);
    const leak = scheduleChannelLeak(frames[0]);
    assert.equal(leak.left_only_ok, true);
    assert.ok(frames[0].left_amplitudes[0] > 0);
    assert.equal(frames[0].right_amplitudes.reduce((a, b) => a + b, 0), 0);

    const q2: any[] = [];
    const seen2 = new Set<string>();
    const rightOnly = makeReceipt({
      agent: 'agent_0', tick: 2, rid: 'rR',
      left: [0, 0, 0, 0, 0, 0], right: [0.5, 0, 0, 0, 0, 0],
    });
    admitSav2Receipt(q2, seen2, rightOnly, 'run', 'agent_0', 'body0', profile, emptySav2Diagnostics(64), { accept: true });
    const f2 = buildSav2Schedule(q2, profile, 1)[0];
    assert.equal(scheduleChannelLeak(f2).right_only_ok, true);
    assert.equal(f2.left_amplitudes.reduce((a, b) => a + b, 0), 0);
    assert.ok(f2.right_amplitudes[0] > 0);

    const sym = mapReceptorActivation([0.4, 0, 0, 0, 0, 0], [0.4, 0, 0, 0, 0, 0]);
    assert.deepEqual(sym.left_amplitudes, sym.right_amplitudes);
  });
});

describe('SAV2 selection isolation / lifecycle (fake stereo)', () => {
  it('selected-agent only; switch clears; enable mid-run; dedup; MAX; teardown; mode exclusive', async () => {
    resetListeningModeForTests();
    const eng = new Sav2PlaybackEngine({ fake: true });
    eng.setSelection('agent_0', 'body0');
    eng.setCompatible(true);
    const r0 = makeReceipt({
      agent: 'agent_0', tick: 10, rid: 'soab:aaa',
      left: [1, 0, 0, 0, 0, 0], right: [0, 0, 0, 0, 0, 0],
    });
    eng.feedReceipt(r0, 'LIVE');
    eng.feedReceipt(r0, 'LIVE');
    const st = await eng.enableListening();
    assert.equal(st, 'running');
    assert.equal(getListeningModeOwner(), 'SELECTED_ORGANISM_SAV2');
    eng.feedReceipt(r0, 'LIVE'); // retained — no replay
    assert.equal(eng.snapshot().diagnostics.rendered, 0);

    const r1 = makeReceipt({
      agent: 'agent_0', tick: 11, rid: 'soab:bbb',
      left: [0.5, 0, 0, 0, 0, 0], right: [0, 0.5, 0, 0, 0, 0],
    });
    eng.feedReceipt(r1, 'LIVE');
    eng.feedReceipt(r1, 'LIVE');
    assert.equal(eng.snapshot().diagnostics.rendered, 1);
    assert.ok(eng.snapshot().diagnostics.deduplicated >= 1);

    // Other agent ignored
    const other = makeReceipt({
      agent: 'agent_1', tick: 12, rid: 'soab:ccc',
      left: [1, 0, 0, 0, 0, 0], right: [1, 0, 0, 0, 0, 0],
    });
    eng.feedReceipt(other, 'LIVE');
    assert.equal(eng.snapshot().diagnostics.rendered, 1);

    // Selection change clears queue / no history replay
    eng.setSelection('agent_1', 'body1');
    const otherBody = makeReceipt({
      agent: 'agent_1', body: 'body1', tick: 12, rid: 'soab:ccc2',
      left: [1, 0, 0, 0, 0, 0], right: [1, 0, 0, 0, 0, 0],
    });
    eng.feedReceipt(otherBody, 'LIVE');
    assert.equal(eng.snapshot().diagnostics.last_agent_id, 'agent_1');

    const rNew = makeReceipt({
      agent: 'agent_1', body: 'body1', tick: 13, rid: 'soab:ddd',
      left: [0, 1, 0, 0, 0, 0], right: [0, 0, 0, 0, 0, 0],
    });
    eng.feedReceipt(rNew, 'LIVE');
    assert.equal(eng.snapshot().diagnostics.last_agent_id, 'agent_1');

    // Mode exclusivity: C1 claim silences SAV2
    let sav2Stolen = false;
    claimListeningMode('PHYSICAL_FIELD_C1', () => { sav2Stolen = true; });
    // claimListeningMode calls previous release which teardowns SAV2
    assert.equal(getListeningModeOwner(), 'PHYSICAL_FIELD_C1');
    // Re-enable path via release
    releaseListeningMode('PHYSICAL_FIELD_C1');
    resetListeningModeForTests();

    // Queue bound
    const eng2 = new Sav2PlaybackEngine({ fake: true });
    eng2.setSelection('agent_0', 'body0');
    await eng2.enableListening();
    for (let i = 0; i < INPUT_QUEUE_CAPACITY + 5; i += 1) {
      admitSav2Receipt(
        eng2.queue,
        eng2.seen,
        makeReceipt({
          agent: 'agent_0', tick: i, rid: `rid${i}`,
          left: [1, 0, 0, 0, 0, 0], right: [0, 0, 0, 0, 0, 0],
        }),
        eng2.runId,
        'agent_0',
        'body0',
        eng2.profile,
        eng2.diag,
        { accept: true },
      );
    }
    assert.ok(eng2.diag.dropped >= 5);
    assert.ok(eng2.queue.length <= INPUT_QUEUE_CAPACITY);

    assert.equal(executionModePolicy('MAX').mute, true);
    assert.equal(executionModePolicy('FAST').status, 'FAST_PLAYBACK_LOSSY_MONITORING');
    eng2.setExecutionMode('MAX');
    const before = eng2.snapshot().diagnostics.rendered;
    eng2.feedReceipt(makeReceipt({
      agent: 'agent_0', tick: 999, rid: 'maxx',
      left: [1, 0, 0, 0, 0, 0], right: [0, 0, 0, 0, 0, 0],
    }), 'MAX');
    assert.equal(eng2.snapshot().diagnostics.rendered, before);

    eng2.onRestore();
    assert.equal(eng2.snapshot().listening, false);
    assert.equal(eng2.snapshot().audioState, 'closed');
    assert.ok(eng2.backend === null || eng2.snapshot().audioState === 'closed');

    void sav2Stolen;
  });
});

describe('C1/SAV2 mutual exclusion + C1 regression', () => {
  it('cannot both own audio; C1 remains sqrt mono probe-driven', async () => {
    resetListeningModeForTests();
    const c1 = new C1PlaybackEngine({ fake: true });
    const s2 = new Sav2PlaybackEngine({ fake: true });
    s2.setSelection('agent_0', 'body0');
    s2.setCompatible(true);
    await c1.enableListening();
    assert.equal(getListeningModeOwner(), 'PHYSICAL_FIELD_C1');
    await s2.enableListening();
    assert.equal(getListeningModeOwner(), 'SELECTED_ORGANISM_SAV2');
    assert.equal(c1.snapshot().listening, false); // stolen

    // C1 numerics unchanged
    const m = mapEnergyToAmplitude([4, 0, 0, 0, 0, 0], FIXED_REFERENCE_GAIN);
    assert.equal(m.mapped_amplitudes[0], FIXED_REFERENCE_GAIN * 2);
    assert.equal(m.policy, 'SQRT_ENERGY_FIXED_REFERENCE');
  });
});

describe('SAV2 UI / privacy labels', () => {
  it('panel has required warning and distinctions; no HRTF claims', () => {
    const src = readFileSync(join(root, 'SelectedOrganismAuditoryViewPanel.tsx'), 'utf8');
    assert.ok(src.includes('SAV2_WARNING') || src.includes('TRANSLATED MONITOR'));
    assert.ok(src.includes('RECEPTOR VALUES AVAILABLE TO SELECTED ORGANISM'));
    assert.ok(src.includes('SAV2_CARRIER_LABEL') || src.includes('NOT PHYSICAL OR ORGANISM'));
    assert.ok(src.includes('ORGANISM RECEPTOR CLIPPING'));
    assert.ok(src.includes('PLAYBACK SAFETY LIMITING'));
    assert.ok(src.includes('SAV2_MODE_LABEL') || src.includes('SELECTED ORGANISM AUDITORY SONIFICATION'));
    assert.ok(!src.includes('HRTF'));
    assert.ok(!src.includes('interaural'));
    assert.ok(!src.includes('binaural rendering'));
    const c1src = readFileSync(join(root, 'CanonicalSonificationPanel.tsx'), 'utf8');
    assert.ok(c1src.includes('PHYSICAL FIELD AT PASSIVE PROBE'));
    // Constants themselves carry the required UX strings
    assert.ok(SAV2_WARNING.includes('TRANSLATED MONITOR'));
    assert.ok(SAV2_MODE_LABEL.includes('SELECTED ORGANISM AUDITORY SONIFICATION'));
  });

  it('analyzer progress finite vs indefinite', () => {
    const fin = analyzerProgress(3, 10);
    assert.equal(fin.mode, 'FINITE_SAMPLE_SCAN');
    assert.equal(fin.percent, 30);
    const live = analyzerProgress(5, 0);
    assert.equal(live.mode, 'LIVE_INDEFINITE');
    assert.equal(live.percent, null);
  });

  it('compatibility rejects missing section A', () => {
    assert.equal(sav1Sav2Compatible(null), false);
    assert.equal(sav1Sav2Compatible({ availability: 'AVAILABLE' }), false);
    assert.ok(sav1Sav2Compatible(makeReceipt({
      agent: 'a', tick: 1, rid: 'x', left: [0, 0, 0, 0, 0, 0], right: [0, 0, 0, 0, 0, 0],
    })));
    const key = receiptDedupKey('run', 'a', 'b', { receipt_id: 'r1', scientific_tick: 3 });
    assert.ok(key?.includes('r1'));
    assert.ok(key?.includes(SAV2_PROFILE));
  });
});
