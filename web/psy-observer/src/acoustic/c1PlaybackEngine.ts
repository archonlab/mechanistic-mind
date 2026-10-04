/** C1 playback engine — Observer-only; no physics mutation APIs. */
import { createFakeAudioBackend, createWebAudioBackend, type AudioBackend } from './c1AudioBackend.ts';
import { type C1Profile, defaultC1Profile, MASTER_DEFAULT_VOLUME } from './c1Profile.ts';
import {
  admitSample,
  buildProvenanceRecord,
  buildSchedule,
  emptyDiagnostics,
  executionModePolicy,
  type ProbeSampleLike,
  type QueueDiagnostics,
  type QueuedSample,
  type ScheduleFrame,
} from './c1Transform.ts';
import {
  claimListeningMode,
  releaseListeningMode,
  getListeningModeOwner,
} from './listeningModeOwner.ts';
import { registerResearcherAudio } from './researcherAudio.ts';

export type PlaybackControls = {
  listening: boolean;
  muted: boolean;
  volume: number;
  playbackTimeScale: number;
  paused: boolean;
};

export type EngineSnapshot = {
  listening: boolean;
  muted: boolean;
  volume: number;
  playbackTimeScale: number;
  audioState: string;
  sampleRate: number;
  diagnostics: QueueDiagnostics;
  modeStatus: string;
  lastProvenance: Record<string, unknown> | null;
  provenanceHistory: Record<string, unknown>[];
  scheduledHorizon: number;
  compatible: boolean;
};

const PROVENANCE_CAP = 32;

export class C1PlaybackEngine {
  profile: C1Profile;
  backend: AudioBackend | null = null;
  queue: QueuedSample[] = [];
  seen = new Set<string>();
  /** Keys present at enable time — ignored so mid-run does not replay history. */
  ignoreAtEnable = new Set<string>();
  diag: QueueDiagnostics;
  controls: PlaybackControls = {
    listening: false,
    muted: false,
    volume: MASTER_DEFAULT_VOLUME,
    playbackTimeScale: 1.0,
    paused: false,
  };
  runId = 'unset';
  modeStatus = 'BOUNDED_QUEUE_SCHEDULE';
  lastProvenance: Record<string, unknown> | null = null;
  provenanceHistory: Record<string, unknown>[] = [];
  compatible = true;
  private scheduleHorizonEnd = 0;
  private useFake: boolean;

  constructor(opts?: { fake?: boolean; profile?: C1Profile }) {
    this.profile = opts?.profile || defaultC1Profile();
    this.diag = emptyDiagnostics(this.profile.input_queue_capacity);
    this.useFake = !!opts?.fake;
    registerResearcherAudio(this);
  }

  stop() {
    this.teardownPlayback('application_exit');
  }

  setProfile(p: C1Profile) {
    this.profile = p;
    this.diag.queue_capacity = p.input_queue_capacity;
  }

  setCompatible(ok: boolean) {
    this.compatible = ok;
    if (!ok && this.controls.listening) this.disable();
  }

  setRunId(runId: string) {
    if (runId !== this.runId) {
      this.teardownPlayback('runtime_switch');
      this.runId = runId;
    }
  }

  setExecutionMode(mode: string) {
    const pol = executionModePolicy(mode);
    this.modeStatus = pol.status;
    if (pol.mute && this.controls.listening) {
      this.backend?.silence(0.02);
      this.diag.muted += 1;
    }
  }

  setPaused(paused: boolean) {
    if (paused && !this.controls.paused) {
      this.backend?.silence(0.02);
      this.queue = [];
      this.diag.queue_length = 0;
    }
    this.controls.paused = paused;
  }

  async enableListening(): Promise<string> {
    if (!this.compatible) return 'INCOMPATIBLE_C0_C1';
    claimListeningMode('PHYSICAL_FIELD_C1', () => {
      this.teardownPlayback('mode_stolen');
    });
    // Snapshot currently seen keys so retained history is not consumed.
    this.ignoreAtEnable = new Set(this.seen);
    this.queue = [];
    this.diag.queue_length = 0;
    if (!this.backend) {
      this.backend = this.useFake
        ? createFakeAudioBackend()
        : createWebAudioBackend(this.profile.canonical_playback_carrier_hz);
    }
    const st = await this.backend.resume();
    if (st === 'suspended') {
      this.controls.listening = false;
      releaseListeningMode('PHYSICAL_FIELD_C1');
      return 'SUSPENDED';
    }
    if (st === 'unavailable' || st === 'closed') {
      this.controls.listening = false;
      releaseListeningMode('PHYSICAL_FIELD_C1');
      return st === 'unavailable' ? 'UNAVAILABLE' : 'CLOSED';
    }
    this.controls.listening = true;
    this.applyMaster();
    if (this.controls.muted) this.backend.setMasterGain(0, 0.01);
    return st;
  }

  disable() {
    this.teardownPlayback('disable');
    releaseListeningMode('PHYSICAL_FIELD_C1');
  }

  setMute(muted: boolean) {
    this.controls.muted = muted;
    this.applyMaster();
  }

  setVolume(v: number) {
    this.controls.volume = Math.max(0, Math.min(1, v));
    this.applyMaster();
  }

  setPlaybackTimeScale(s: number) {
    // Affects future scheduling only.
    this.controls.playbackTimeScale = s;
  }

  clearDiagnostics() {
    const cap = this.diag.queue_capacity;
    const lastKey = this.diag.last_consumed_key;
    const lastTick = this.diag.last_consumed_tick;
    this.diag = emptyDiagnostics(cap);
    this.diag.last_consumed_key = lastKey;
    this.diag.last_consumed_tick = lastTick;
    this.provenanceHistory = [];
    // Do not clear stream/probe scientific evidence — those are backend.
  }

  onProbeMoveOrDisable() {
    this.queue = [];
    this.diag.queue_length = 0;
    this.backend?.silence(0.02);
    // Keep seen so old-location keys cannot replay; new samples get new sample_keys.
  }

  onRestore() {
    this.teardownPlayback('restore');
    releaseListeningMode('PHYSICAL_FIELD_C1');
  }

  /** Exposed for mode-ownership diagnostics (does not alter C1 numerics). */
  listeningModeOwner(): string {
    return getListeningModeOwner();
  }

  feedLatest(sample: ProbeSampleLike | null | undefined, executionMode: string) {
    if (!sample) return;
    const pol = executionModePolicy(executionMode);
    this.modeStatus = pol.status;
    if (!this.controls.listening || this.controls.paused || !pol.admit) {
      if (pol.mute) this.diag.muted += 1;
      // Still observe for dedupe of future identical polls when listening resumes? No —
      // when not listening we should still mark seen of *delivered* frames only after enable.
      // Before enable: track keys in seen so enable mid-run can ignore them.
      const key = `${this.runId}|${sample.probe_id || 'observer-acoustic-probe-0'}|${sample.sample_key || ''}`;
      if (sample.sample_key) this.seen.add(key);
      return;
    }
    if (pol.mute) {
      this.backend?.silence(0.01);
      this.diag.muted += 1;
      return;
    }
    const dedupPreview = `${this.runId}|${sample.probe_id || 'observer-acoustic-probe-0'}|${sample.sample_key || ''}`;
    if (this.ignoreAtEnable.has(dedupPreview)) {
      this.diag.deduplicated += 1;
      this.seen.add(dedupPreview);
      return;
    }
    const result = admitSample(
      this.queue,
      this.seen,
      sample,
      this.runId,
      this.profile,
      this.diag,
      { accept: true },
    );
    if (result.admitted) this.drainSchedule();
  }

  private drainSchedule() {
    if (!this.backend || !this.controls.listening) return;
    const tickDur = this.profile.canonical_seconds_per_tick * this.controls.playbackTimeScale;
    const ramp = Math.max(0.001, tickDur * this.profile.envelope_fraction_of_tick);
    const now = this.backend.currentTime();
    const horizon = now + this.profile.scheduled_horizon_seconds;
    while (this.queue.length > 0) {
      if (this.scheduleHorizonEnd > horizon) break;
      const item = this.queue.shift()!;
      this.diag.queue_length = this.queue.length;
      const start = Math.max(now, this.scheduleHorizonEnd);
      const frames: ScheduleFrame[] = buildSchedule(
        [item],
        this.profile,
        this.controls.playbackTimeScale,
      );
      const frame = frames[0];
      const gains = this.controls.muted ? [0, 0, 0, 0, 0, 0] : frame.mapped_amplitudes;
      // Soft clamp per-band for device safety (playback only)
      const clamped = gains.map((g) => Math.min(g, this.profile.limiter_threshold));
      if (clamped.some((g, i) => g < gains[i])) this.diag.limiter_activations += 1;
      this.backend.setBandGains(clamped, ramp, start);
      // Schedule return toward silence at end of tick unless next follows immediately
      this.backend.setBandGains([0, 0, 0, 0, 0, 0], ramp, start + frame.duration_seconds);
      this.scheduleHorizonEnd = start + frame.duration_seconds;
      this.diag.rendered += 1;
      this.diag.last_consumed_key = item.sample_key;
      this.diag.last_consumed_tick = item.scientific_tick;
      const prev = this.backend.limiterActivations();
      this.diag.limiter_activations = Math.max(this.diag.limiter_activations, prev);
      const prov = buildProvenanceRecord(frame, {
        device_sample_rate: this.backend.sampleRate(),
        audio_context_state: this.backend.state(),
        queue_drop: false,
        run_id: this.runId,
      });
      this.lastProvenance = prov;
      this.provenanceHistory.push(prov);
      while (this.provenanceHistory.length > PROVENANCE_CAP) this.provenanceHistory.shift();
    }
    if (this.queue.length === 0 && this.diag.rendered > 0) {
      // underrun if horizon starved unexpectedly — counted when feed finds empty after lag
    }
  }

  private applyMaster() {
    if (!this.backend) return;
    const g = this.controls.muted || !this.controls.listening ? 0 : this.controls.volume;
    this.backend.setMasterGain(g, 0.02);
  }

  private teardownPlayback(_reason: string) {
    this.controls.listening = false;
    this.queue = [];
    this.diag.queue_length = 0;
    this.scheduleHorizonEnd = 0;
    this.ignoreAtEnable = new Set();
    if (this.backend) {
      this.backend.silence(0.01);
      this.backend.teardown();
      this.backend = null;
    }
  }

  snapshot(): EngineSnapshot {
    return {
      listening: this.controls.listening,
      muted: this.controls.muted,
      volume: this.controls.volume,
      playbackTimeScale: this.controls.playbackTimeScale,
      audioState: this.backend?.state() || 'closed',
      sampleRate: this.backend?.sampleRate() || 0,
      diagnostics: { ...this.diag },
      modeStatus: this.modeStatus,
      lastProvenance: this.lastProvenance,
      provenanceHistory: [...this.provenanceHistory],
      scheduledHorizon: this.profile.scheduled_horizon_seconds,
      compatible: this.compatible,
    };
  }
}
