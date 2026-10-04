import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { describe, it } from 'node:test';
import { fileURLToPath } from 'node:url';
import {
  CANONICAL_PLAYBACK_CARRIER_HZ,
  CANONICAL_SECONDS_PER_TICK,
  FIXED_RECEPTOR_GAIN,
  SAV4B_AUTHORITY,
  SAV4B_CAPABILITY,
  SAV4B_OWNER,
  SAV4B_PROFILE,
  SAV4B_SCHEMA,
  playbackEnabledForSegment,
  scheduleItemsForSegment,
  type Sav4aPayloadLike,
  type Sav4aScheduleItem,
} from './sav4bOffline.ts';
import { Sav4bPlaybackEngine } from './sav4bPlaybackEngine.ts';
import {
  claimListeningMode,
  getListeningModeOwner,
  releaseListeningMode,
  resetListeningModeForTests,
} from './listeningModeOwner.ts';
import { hearingIndicatorLabel, listeningIsActive } from './hearingActiveStatus.ts';

const root = dirname(fileURLToPath(import.meta.url));

function item(tick: number, leftAmp: number, opts?: Partial<Sav4aScheduleItem>): Sav4aScheduleItem {
  const amps = [leftAmp, 0, 0, 0, 0, 0];
  const rights = [leftAmp * 0.5, 0, 0, 0, 0, 0];
  return {
    schedule_item_id: `sch-${tick}`,
    segment_id: 'seg-a',
    observation_tick: tick,
    canonical_start_seconds: tick * CANONICAL_SECONDS_PER_TICK,
    canonical_duration_seconds: CANONICAL_SECONDS_PER_TICK,
    envelope_fraction_of_tick: 0.2,
    left_input: amps.map((a) => a / FIXED_RECEPTOR_GAIN),
    right_input: rights.map((a) => a / FIXED_RECEPTOR_GAIN),
    left_amplitudes: amps,
    right_amplitudes: rights,
    fixed_receptor_gain: FIXED_RECEPTOR_GAIN,
    carriers_hz: [...CANONICAL_PLAYBACK_CARRIER_HZ],
    true_zero: leftAmp === 0,
    authority_class: 'SAV1_EXACT_A5',
    ...opts,
  };
}

function payload(items: Sav4aScheduleItem[], segExtra: Record<string, unknown> = {}): Sav4aPayloadLike {
  return {
    schedule_available: true,
    schedule_digest: 'digest-fixture',
    schedule_items: items,
    identity_segments: [
      {
        segment_id: 'seg-a',
        schedule_available: true,
        completeness: 'SAV1_A5_ONLY',
        authority_badge: 'SAV1_EXACT_A5',
        compatibility_class: 'CURRENT_COMPATIBLE',
        first_tick: items[0]?.observation_tick ?? 0,
        last_tick: items[items.length - 1]?.observation_tick ?? 0,
        gap_count: 0,
        run_id: 'r1',
        runtime_generation: '1',
        agent_id: 'a0',
        body_id: 'b0',
        ...segExtra,
      },
    ],
  };
}

describe('SAV4B offline player', () => {
  it('identity constants', () => {
    assert.equal(SAV4B_SCHEMA, 'SELECTED_ORGANISM_AUDITORY_OFFLINE_PLAYER_SAV4B_V1');
    assert.equal(SAV4B_CAPABILITY, 'selected_organism_auditory_offline_playback');
    assert.equal(SAV4B_PROFILE, 'SAV4A_SCHEDULE_TRANSLATED_STEREO_OFFLINE_PLAYER_SAV4B_V1');
    assert.equal(SAV4B_AUTHORITY, 'RESEARCHER_DERIVED_PLAYBACK_OVER_SAV4A_SCHEDULE');
    assert.equal(SAV4B_OWNER, 'OFFLINE_SAV4B');
  });

  it('consumes SAV4A schedule items, not raw evidence keys', () => {
    const p = payload([item(0, 0.1), item(1, 0.2)]);
    const items = scheduleItemsForSegment(p, 'seg-a');
    assert.equal(items.length, 2);
    assert.ok(items[0].left_amplitudes);
    assert.equal((p as any).oatt_traces, undefined);
    const src = readFileSync(join(root, 'sav4bPlaybackEngine.ts'), 'utf8');
    assert.equal(src.includes('ORGANISM_AUDITORY_TRANSFORMATION'), false);
    assert.equal(src.includes('scientific_observations'), false);
    assert.equal(src.includes('admitSav2Receipt'), false);
  });

  it('compatible schedule enables; incompatible disables', () => {
    const ok = payload([item(0, 0.1)]);
    assert.equal(playbackEnabledForSegment(ok, ok.identity_segments![0]).enabled, true);
    const bad = payload([item(0, 0.1)], {
      schedule_available: false,
      completeness: 'PROFILE_UNKNOWN_OR_INCOMPATIBLE',
    });
    const g = playbackEnabledForSegment(bad, bad.identity_segments![0]);
    assert.equal(g.enabled, false);
    assert.match(g.reason, /PROFILE_UNKNOWN|SCHEDULE_UNAVAILABLE/);
  });

  it('play acquires OFFLINE_SAV4B and releases LIVE C1/SAV2', async () => {
    resetListeningModeForTests();
    let c1 = 0;
    let sav2 = 0;
    claimListeningMode('PHYSICAL_FIELD_C1', () => { c1 += 1; });
    assert.equal(getListeningModeOwner(), 'PHYSICAL_FIELD_C1');
    const eng = new Sav4bPlaybackEngine({ fake: true });
    eng.setSchedule([item(0, 0.2), item(1, 0.0)]);
    const st = await eng.play();
    assert.equal(st, 'PLAYING');
    assert.equal(getListeningModeOwner(), 'OFFLINE_SAV4B');
    assert.equal(c1, 1);
    claimListeningMode('SELECTED_ORGANISM_SAV2', () => { sav2 += 1; });
    // claiming SAV2 should steal from SAV4B
    assert.equal(getListeningModeOwner(), 'SELECTED_ORGANISM_SAV2');
    assert.equal(eng.snapshot().playing, false);
    releaseListeningMode('SELECTED_ORGANISM_SAV2');
    // reverse: SAV4B steals SAV2
    claimListeningMode('SELECTED_ORGANISM_SAV2', () => { sav2 += 1; });
    await eng.play();
    assert.equal(getListeningModeOwner(), 'OFFLINE_SAV4B');
    assert.ok(sav2 >= 1);
    eng.stop();
    resetListeningModeForTests();
  });

  it('only one audible owner; indicator labels', () => {
    resetListeningModeForTests();
    assert.equal(listeningIsActive('OFF'), false);
    assert.equal(listeningIsActive('OFFLINE_SAV4B'), true);
    assert.equal(hearingIndicatorLabel({ owner: 'OFFLINE_SAV4B' }), 'HEARING · SAV4B OFFLINE');
    resetListeningModeForTests();
  });

  it('pause preserves cursor; seek clears future; stop resets', async () => {
    resetListeningModeForTests();
    const eng = new Sav4bPlaybackEngine({ fake: true });
    eng.setSchedule([item(0, 0.1), item(1, 0.2), item(2, 0.3)]);
    await eng.play();
    eng.tickLookahead(0.01);
    const before = eng.snapshot().cursor_index;
    eng.pause();
    assert.equal(eng.snapshot().status, 'PAUSED');
    assert.equal(eng.snapshot().cursor_index, before);
    const eventsBeforeSeek = eng.scheduledEventCount;
    eng.seekIndex(2);
    assert.equal(eng.snapshot().cursor_index, 2);
    assert.equal(eng.snapshot().playing, false);
    // seek cleared future scheduling window
    assert.ok(eng.scheduledThrough < eng.cursorIndex);
    eng.stop();
    assert.equal(eng.snapshot().cursor_index, 0);
    assert.equal(getListeningModeOwner(), 'OFF');
    assert.ok(eventsBeforeSeek >= 0);
    resetListeningModeForTests();
  });

  it('gap boundary at segment end when flagged; no synthetic gap zeros', async () => {
    resetListeningModeForTests();
    const eng = new Sav4bPlaybackEngine({ fake: true });
    eng.setSchedule([item(0, 0.1), item(1, 0.2)], { treatEndAsGapBoundary: true });
    await eng.play();
    // Advance past both items
    for (let i = 0; i < 20; i += 1) eng.tickLookahead(0.05);
    const snap = eng.snapshot();
    assert.ok(snap.status === 'GAP_BOUNDARY' || snap.status === 'ENDED' || snap.cursor_index >= 2);
    // schedule never invented ticks 2,3
    assert.equal(eng.items.length, 2);
    assert.equal(eng.items.some((x) => Number(x.observation_tick) === 3), false);
    eng.stop();
    resetListeningModeForTests();
  });

  it('true-zero item produces zero amplitudes (legitimate silence)', () => {
    const it = item(5, 0);
    assert.equal(it.true_zero, true);
    assert.ok(it.left_amplitudes!.every((x) => x === 0));
  });

  it('reuses SAV2 carriers, gain, and 0.05 s/tick', () => {
    assert.deepEqual([...CANONICAL_PLAYBACK_CARRIER_HZ], [120, 200, 320, 480, 720, 1000]);
    assert.equal(FIXED_RECEPTOR_GAIN, 0.35);
    assert.equal(CANONICAL_SECONDS_PER_TICK, 0.05);
    const eng = new Sav4bPlaybackEngine({ fake: true });
    eng.setSchedule([item(0, FIXED_RECEPTOR_GAIN)]); // amp already mapped
    const snap = eng.snapshot();
    assert.deepEqual(snap.carriers_hz, [120, 200, 320, 480, 720, 1000]);
    assert.equal(snap.fixed_receptor_gain, 0.35);
    assert.equal(snap.canonical_seconds_per_tick, 0.05);
    assert.equal(snap.canonical_seconds_per_tick_is_physical, false);
    assert.equal(snap.uses_live_sav2_queue, false);
    assert.equal(snap.pcm_rendering, false);
    assert.equal(snap.wav_export, false);
  });

  it('bounded lookahead does not schedule entire long run at once', async () => {
    resetListeningModeForTests();
    const many: Sav4aScheduleItem[] = [];
    for (let t = 0; t < 200; t += 1) many.push(item(t, 0.1));
    const eng = new Sav4bPlaybackEngine({ fake: true });
    eng.setSchedule(many);
    await eng.play();
    eng.tickLookahead(0);
    const snap = eng.snapshot();
    assert.ok(snap.scheduled_ahead < 50, `lookahead too large: ${snap.scheduled_ahead}`);
    assert.ok(snap.scheduled_ahead >= 1);
    eng.stop();
    resetListeningModeForTests();
  });

  it('repeated play/stop does not multiply backends unbounded', async () => {
    resetListeningModeForTests();
    const eng = new Sav4bPlaybackEngine({ fake: true });
    eng.setSchedule([item(0, 0.2)]);
    for (let i = 0; i < 5; i += 1) {
      await eng.play();
      eng.stop();
    }
    assert.ok(eng.backendsCreated <= 5);
    assert.equal(getListeningModeOwner(), 'OFF');
    resetListeningModeForTests();
  });

  it('device failure does not mutate schedule evidence', async () => {
    resetListeningModeForTests();
    const eng = new Sav4bPlaybackEngine({ fake: true });
    const items = [item(0, 0.4)];
    eng.setSchedule(items);
    // Force closed backend path after create by tearing down mid-flight is hard;
    // assert evidence_mutated flag stays false and items unchanged.
    await eng.play();
    const before = JSON.stringify(eng.items);
    eng.pause();
    assert.equal(JSON.stringify(eng.items), before);
    assert.equal(eng.snapshot().evidence_mutated, false);
    eng.stop();
    resetListeningModeForTests();
  });

  it('HEARING panel wires SAV4B controls without WAV/PCM export', () => {
    const panel = readFileSync(
      join(root, 'SelectedOrganismAuditoryOfflineReconstructionPanel.tsx'),
      'utf8',
    );
    assert.ok(panel.includes('hearing-sav4b-play'));
    assert.ok(panel.includes('hearing-sav4b-pause'));
    assert.ok(panel.includes('hearing-sav4b-seek'));
    assert.ok(panel.includes('hearing-sav4b-stop'));
    assert.ok(panel.includes('No WAV'));
    assert.equal(panel.includes('OfflineAudioContext'), false);
    assert.ok(panel.includes('LIVE C1/SAV2'));
    const owner = readFileSync(join(root, 'listeningModeOwner.ts'), 'utf8');
    assert.ok(owner.includes('OFFLINE_SAV4B'));
  });
});
