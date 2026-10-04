/**
 * SAV4B offline playback engine — consumes SAV4A schedule items only.
 * Does not parse OATT/SAV1/legacy evidence or use the live SAV2 queue.
 */
import {
  createFakeStereoAudioBackend,
  createWebStereoAudioBackend,
  type StereoAudioBackend,
} from './stereoAudioBackend.ts';
import {
  claimListeningMode,
  releaseListeningMode,
  getListeningModeOwner,
} from './listeningModeOwner.ts';
import {
  CANONICAL_PLAYBACK_CARRIER_HZ,
  CANONICAL_SECONDS_PER_TICK,
  ENVELOPE_FRACTION_OF_TICK,
  LIMITER_THRESHOLD,
  SCHEDULED_HORIZON_SECONDS,
  FIXED_RECEPTOR_GAIN,
  SAV4B_AUTHORITY,
  SAV4B_PROFILE,
  SAV4B_SCHEMA,
  type Sav4aScheduleItem,
} from './sav4bOffline.ts';
import { MASTER_DEFAULT_VOLUME } from './sav2Profile.ts';
import { registerResearcherAudio } from './researcherAudio.ts';

const Z6 = () => [0, 0, 0, 0, 0, 0];

export type Sav4bEngineStatus =
  | 'IDLE'
  | 'PLAYING'
  | 'PAUSED'
  | 'GAP_BOUNDARY'
  | 'ENDED'
  | 'UNAVAILABLE'
  | 'SUSPENDED'
  | 'AUTOPLAY_DENIED';

export type Sav4bEngineSnapshot = {
  schema: string;
  profile: string;
  authority: string;
  status: Sav4bEngineStatus;
  playing: boolean;
  cursor_index: number;
  current_tick: number | null;
  segment_id: string | null;
  schedule_digest: string | null;
  item_count: number;
  duration_seconds: number;
  position_seconds: number;
  mode_owner: string;
  audio_state: string;
  lookahead_seconds: number;
  scheduled_ahead: number;
  uses_live_sav2_queue: false;
  pcm_rendering: false;
  wav_export: false;
  true_zero_at_cursor: boolean;
  gap_boundary: boolean;
  last_error: string | null;
  carriers_hz: number[];
  fixed_receptor_gain: number;
  envelope_fraction_of_tick: number;
  canonical_seconds_per_tick: number;
  canonical_seconds_per_tick_is_physical: false;
  evidence_mutated: false;
  backends_created: number;
  scheduled_event_count: number;
};

export class Sav4bPlaybackEngine {
  backend: StereoAudioBackend | null = null;
  items: Sav4aScheduleItem[] = [];
  cursorIndex = 0;
  /** Inclusive last index pushed into lookahead. */
  scheduledThrough = -1;
  /** Absolute audio-clock end time per scheduled item index. */
  itemAbsoluteEnds: number[] = [];
  playing = false;
  status: Sav4bEngineStatus = 'IDLE';
  segmentId: string | null = null;
  scheduleDigest: string | null = null;
  durationSeconds = 0;
  lastError: string | null = null;
  volume = MASTER_DEFAULT_VOLUME;
  backendsCreated = 0;
  scheduledEventCount = 0;
  /** When true, reaching end of this segment's items reports GAP_BOUNDARY (multi-segment). */
  treatEndAsGapBoundary = false;
  private useFake: boolean;
  private scheduleHorizonEnd = 0;
  private timer: ReturnType<typeof setInterval> | null = null;
  private carriers: number[] = [...CANONICAL_PLAYBACK_CARRIER_HZ];

  constructor(opts?: { fake?: boolean }) {
    this.useFake = !!opts?.fake;
    registerResearcherAudio(this);
  }

  setSchedule(
    items: Sav4aScheduleItem[],
    meta?: {
      segmentId?: string | null;
      scheduleDigest?: string | null;
      treatEndAsGapBoundary?: boolean;
    },
  ) {
    this.stopInternal(false);
    this.items = Array.isArray(items) ? items.slice() : [];
    this.cursorIndex = 0;
    this.scheduledThrough = -1;
    this.itemAbsoluteEnds = [];
    this.segmentId = meta?.segmentId != null ? String(meta.segmentId) : null;
    this.scheduleDigest = meta?.scheduleDigest != null ? String(meta.scheduleDigest) : null;
    this.treatEndAsGapBoundary = !!meta?.treatEndAsGapBoundary;
    this.durationSeconds = 0;
    for (const it of this.items) {
      const start = Number(it.canonical_start_seconds ?? 0);
      const dur = Number(it.canonical_duration_seconds ?? CANONICAL_SECONDS_PER_TICK);
      this.durationSeconds = Math.max(this.durationSeconds, start + dur);
      if (Array.isArray(it.carriers_hz) && it.carriers_hz.length === 6) {
        this.carriers = it.carriers_hz.map((x) => Number(x));
      }
    }
    this.status = this.items.length ? 'IDLE' : 'UNAVAILABLE';
    this.lastError = this.items.length ? null : 'EMPTY_SCHEDULE';
  }

  clearSchedule() {
    this.stop();
    this.items = [];
    this.segmentId = null;
    this.scheduleDigest = null;
    this.durationSeconds = 0;
    this.status = 'UNAVAILABLE';
  }

  async play(): Promise<Sav4bEngineStatus> {
    if (!this.items.length) {
      this.status = 'UNAVAILABLE';
      this.lastError = 'EMPTY_SCHEDULE';
      return this.status;
    }
    if (this.cursorIndex >= this.items.length) {
      this.status = this.treatEndAsGapBoundary ? 'GAP_BOUNDARY' : 'ENDED';
      return this.status;
    }
    claimListeningMode('OFFLINE_SAV4B', () => {
      this.teardownStolen();
    });
    if (!this.backend) {
      this.backend = this.useFake
        ? createFakeStereoAudioBackend()
        : createWebStereoAudioBackend(this.carriers);
      this.backendsCreated += 1;
    }
    const st = await this.backend.resume();
    if (st === 'suspended') {
      this.playing = false;
      this.status = 'SUSPENDED';
      this.lastError = 'AUTOPLAY_OR_SUSPENDED';
      releaseListeningMode('OFFLINE_SAV4B');
      return this.status;
    }
    if (st === 'unavailable' || st === 'closed') {
      this.playing = false;
      this.status = 'AUTOPLAY_DENIED';
      this.lastError = String(st);
      releaseListeningMode('OFFLINE_SAV4B');
      return this.status;
    }
    this.playing = true;
    this.status = 'PLAYING';
    this.lastError = null;
    this.applyMaster();
    this.drainLookahead();
    this.ensureTimer();
    return this.status;
  }

  pause() {
    this.playing = false;
    if (this.status !== 'GAP_BOUNDARY' && this.status !== 'ENDED' && this.status !== 'UNAVAILABLE') {
      this.status = 'PAUSED';
    }
    this.clearFutureAudio();
    this.stopTimer();
  }

  /** Seek by index. Clears future audio. Does not auto-resume. Never touches simulation. */
  seekIndex(index: number) {
    if (!this.items.length) return;
    const i = Math.max(0, Math.min(this.items.length - 1, Math.floor(index)));
    this.clearFutureAudio();
    this.cursorIndex = i;
    this.scheduledThrough = i - 1;
    this.itemAbsoluteEnds = [];
    this.playing = false;
    this.status = 'PAUSED';
    this.stopTimer();
  }

  seekTick(tick: number) {
    if (!this.items.length) return;
    let best = 0;
    for (let i = 0; i < this.items.length; i += 1) {
      if (Number(this.items[i].observation_tick ?? 0) <= tick) best = i;
      else break;
    }
    this.seekIndex(best);
  }

  stop() {
    this.stopInternal(true);
  }

  /** Test/helper: advance fake clock and progress cursor. */
  tickLookahead(fakeAdvanceSeconds = 0) {
    if (this.useFake && this.backend) {
      const fake = this.backend as { _time?: number };
      if (typeof fake._time === 'number') fake._time += fakeAdvanceSeconds;
    }
    if (this.playing) {
      this.drainLookahead();
      this.advanceCursor();
    }
  }

  snapshot(): Sav4bEngineSnapshot {
    const cur = this.items[this.cursorIndex];
    const pos = cur
      ? Number(cur.canonical_start_seconds ?? this.cursorIndex * CANONICAL_SECONDS_PER_TICK)
      : (this.cursorIndex >= this.items.length ? this.durationSeconds : 0);
    return {
      schema: SAV4B_SCHEMA,
      profile: SAV4B_PROFILE,
      authority: SAV4B_AUTHORITY,
      status: this.status,
      playing: this.playing,
      cursor_index: this.cursorIndex,
      current_tick: cur ? Number(cur.observation_tick ?? null) : null,
      segment_id: this.segmentId,
      schedule_digest: this.scheduleDigest,
      item_count: this.items.length,
      duration_seconds: this.durationSeconds,
      position_seconds: pos,
      mode_owner: getListeningModeOwner(),
      audio_state: this.backend?.state() ?? 'closed',
      lookahead_seconds: SCHEDULED_HORIZON_SECONDS,
      scheduled_ahead: Math.max(0, this.scheduledThrough - this.cursorIndex + 1),
      uses_live_sav2_queue: false,
      pcm_rendering: false,
      wav_export: false,
      true_zero_at_cursor: Boolean(cur?.true_zero),
      gap_boundary: this.status === 'GAP_BOUNDARY',
      last_error: this.lastError,
      carriers_hz: [...this.carriers],
      fixed_receptor_gain: FIXED_RECEPTOR_GAIN,
      envelope_fraction_of_tick: ENVELOPE_FRACTION_OF_TICK,
      canonical_seconds_per_tick: CANONICAL_SECONDS_PER_TICK,
      canonical_seconds_per_tick_is_physical: false,
      evidence_mutated: false,
      backends_created: this.backendsCreated,
      scheduled_event_count: this.scheduledEventCount,
    };
  }

  private drainLookahead() {
    if (!this.backend || !this.playing) return;
    const tickDur = CANONICAL_SECONDS_PER_TICK;
    const now = this.backend.currentTime();
    const horizon = now + SCHEDULED_HORIZON_SECONDS;
    const maxAhead = Math.max(2, Math.ceil(SCHEDULED_HORIZON_SECONDS / tickDur) + 1);
    let next = Math.max(this.scheduledThrough + 1, this.cursorIndex);
    while (next < this.items.length) {
      if (next - this.cursorIndex >= maxAhead) break;
      if (this.scheduleHorizonEnd > horizon && this.scheduledThrough >= this.cursorIndex) break;

      const it = this.items[next];
      const leftRaw = Array.isArray(it.left_amplitudes) ? it.left_amplitudes : Z6();
      const rightRaw = Array.isArray(it.right_amplitudes) ? it.right_amplitudes : Z6();
      const lim = Number(it.limiter_threshold ?? LIMITER_THRESHOLD);
      const left = leftRaw.map((g) => Math.min(Math.max(0, Number(g) || 0), lim));
      const right = rightRaw.map((g) => Math.min(Math.max(0, Number(g) || 0), lim));
      const start = Math.max(now, this.scheduleHorizonEnd);
      const dur = Number(it.canonical_duration_seconds ?? tickDur);
      const envFrac = Number(it.envelope_fraction_of_tick ?? ENVELOPE_FRACTION_OF_TICK);
      const ramp = Math.max(0.001, dur * envFrac);
      this.backend.setStereoBandGains(left, right, ramp, start);
      this.backend.setStereoBandGains(Z6(), Z6(), ramp, start + dur);
      this.scheduleHorizonEnd = start + dur;
      this.itemAbsoluteEnds[next] = start + dur;
      this.scheduledEventCount += 2;
      this.scheduledThrough = next;
      next += 1;
    }
  }

  private advanceCursor() {
    if (!this.backend) return;
    const t = this.backend.currentTime();
    while (this.cursorIndex < this.items.length && this.cursorIndex <= this.scheduledThrough) {
      const end = this.itemAbsoluteEnds[this.cursorIndex];
      if (end == null || t < end - 1e-9) break;
      this.cursorIndex += 1;
    }
    if (this.cursorIndex >= this.items.length) {
      this.playing = false;
      this.status = this.treatEndAsGapBoundary ? 'GAP_BOUNDARY' : 'ENDED';
      this.clearFutureAudio();
      this.stopTimer();
      releaseListeningMode('OFFLINE_SAV4B');
      return;
    }
    if (this.playing) this.drainLookahead();
  }

  private clearFutureAudio() {
    this.scheduleHorizonEnd = 0;
    this.scheduledThrough = this.cursorIndex - 1;
    this.itemAbsoluteEnds = [];
    try { this.backend?.silence(0.02); } catch { /* */ }
  }

  private applyMaster() {
    if (!this.backend) return;
    this.backend.setMasterGain(this.playing ? this.volume : 0, 0.02);
  }

  private ensureTimer() {
    if (this.timer || this.useFake) return;
    this.timer = setInterval(() => {
      if (!this.playing) return;
      this.drainLookahead();
      this.advanceCursor();
    }, 40);
  }

  private stopTimer() {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }

  private stopInternal(releaseOwner: boolean) {
    this.playing = false;
    this.clearFutureAudio();
    this.stopTimer();
    this.cursorIndex = 0;
    this.scheduledThrough = -1;
    this.itemAbsoluteEnds = [];
    this.status = this.items.length ? 'IDLE' : 'UNAVAILABLE';
    if (releaseOwner) releaseListeningMode('OFFLINE_SAV4B');
    if (this.backend) {
      try { this.backend.teardown(); } catch { /* */ }
      this.backend = null;
    }
  }

  private teardownStolen() {
    this.playing = false;
    this.clearFutureAudio();
    this.stopTimer();
    this.status = this.items.length ? 'PAUSED' : 'UNAVAILABLE';
    if (this.backend) {
      try { this.backend.teardown(); } catch { /* */ }
      this.backend = null;
    }
  }
}
