/** SAV2 playback engine — researcher-only; never mutates SAV1/osc/cognition. */
import {
  createFakeStereoAudioBackend,
  createWebStereoAudioBackend,
  type StereoAudioBackend,
} from './stereoAudioBackend.ts';
import {
  MASTER_DEFAULT_VOLUME,
  defaultSav2Profile,
  type Sav2Profile,
} from './sav2Profile.ts';
import {
  admitSav2Receipt,
  buildSav2Provenance,
  buildSav2Schedule,
  countNonzeroBands,
  emptySav2Diagnostics,
  executionModePolicy,
  type QueuedSav2Receipt,
  type Sav1ReceiptLike,
  type Sav2QueueDiagnostics,
  type Sav2ScheduleFrame,
} from './sav2Transform.ts';
import {
  claimListeningMode,
  releaseListeningMode,
  getListeningModeOwner,
} from './listeningModeOwner.ts';
import { registerResearcherAudio } from './researcherAudio.ts';

export type Sav2PlaybackControls = {
  listening: boolean;
  muted: boolean;
  volume: number;
  playbackTimeScale: number;
  paused: boolean;
};

export type Sav2EngineSnapshot = {
  listening: boolean;
  muted: boolean;
  volume: number;
  playbackTimeScale: number;
  audioState: string;
  sampleRate: number;
  diagnostics: Sav2QueueDiagnostics;
  modeStatus: string;
  modeOwner: string;
  lastProvenance: Record<string, unknown> | null;
  provenanceHistory: Record<string, unknown>[];
  scheduledHorizon: number;
  compatible: boolean;
  selectedAgentId: string | null;
  selectedBodyId: string | null;
  availability: string;
  lastMapped: { left: number[]; right: number[] } | null;
  lastInput: { left: number[]; right: number[] } | null;
};

const PROVENANCE_CAP = 32;
const Z6 = () => [0, 0, 0, 0, 0, 0];

export class Sav2PlaybackEngine {
  profile: Sav2Profile;
  backend: StereoAudioBackend | null = null;
  queue: QueuedSav2Receipt[] = [];
  seen = new Set<string>();
  ignoreAtEnable = new Set<string>();
  diag: Sav2QueueDiagnostics;
  controls: Sav2PlaybackControls = {
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
  selectedAgentId: string | null = null;
  selectedBodyId: string | null = null;
  availability = 'NO_SELECTION';
  lastMapped: { left: number[]; right: number[] } | null = null;
  lastInput: { left: number[]; right: number[] } | null = null;
  private scheduleHorizonEnd = 0;
  private useFake: boolean;

  constructor(opts?: { fake?: boolean; profile?: Sav2Profile }) {
    this.profile = opts?.profile || defaultSav2Profile();
    this.diag = emptySav2Diagnostics(this.profile.input_queue_capacity);
    this.useFake = !!opts?.fake;
    registerResearcherAudio(this);
  }

  stop() {
    this.teardownPlayback('application_exit');
  }

  setProfile(p: Sav2Profile) {
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
      this.seen = new Set();
    }
  }

  setSelection(agentId: string | null, bodyId: string | null) {
    const a = agentId ? String(agentId) : null;
    const b = bodyId ? String(bodyId) : null;
    if (a === this.selectedAgentId && b === this.selectedBodyId) return;
    this.selectedAgentId = a;
    this.selectedBodyId = b;
    this.queue = [];
    this.diag.queue_length = 0;
    this.scheduleHorizonEnd = 0;
    this.ignoreAtEnable = new Set(this.seen);
    this.backend?.silence(0.02);
    this.lastMapped = null;
    this.lastInput = null;
    if (!a) this.availability = 'NO_SELECTION';
  }

  setAvailability(status: string) {
    this.availability = status;
    if (status !== 'AVAILABLE' && this.controls.listening) {
      this.backend?.silence(0.02);
      this.queue = [];
      this.diag.queue_length = 0;
    }
  }

  setExecutionMode(mode: string) {
    const pol = executionModePolicy(mode);
    this.modeStatus = pol.status;
    if (pol.mute && this.controls.listening) {
      this.backend?.silence(0.02);
      this.diag.muted += 1;
      this.queue = [];
      this.diag.queue_length = 0;
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
    if (!this.compatible) return 'INCOMPATIBLE_SAV1';
    if (!this.selectedAgentId) return 'NO_SELECTION';
    claimListeningMode('SELECTED_ORGANISM_SAV2', () => {
      this.teardownPlayback('mode_stolen');
    });
    this.ignoreAtEnable = new Set(this.seen);
    this.queue = [];
    this.diag.queue_length = 0;
    this.scheduleHorizonEnd = 0;
    if (!this.backend) {
      this.backend = this.useFake
        ? createFakeStereoAudioBackend()
        : createWebStereoAudioBackend(this.profile.canonical_playback_carrier_hz);
    }
    const st = await this.backend.resume();
    if (st === 'suspended') {
      this.controls.listening = false;
      releaseListeningMode('SELECTED_ORGANISM_SAV2');
      return 'SUSPENDED';
    }
    if (st === 'unavailable' || st === 'closed') {
      this.controls.listening = false;
      releaseListeningMode('SELECTED_ORGANISM_SAV2');
      return st === 'unavailable' ? 'UNAVAILABLE' : 'CLOSED';
    }
    this.controls.listening = true;
    this.diag.mode_owner = getListeningModeOwner();
    this.applyMaster();
    if (this.controls.muted) this.backend.setMasterGain(0, 0.01);
    return st;
  }

  disable() {
    this.teardownPlayback('disable');
    releaseListeningMode('SELECTED_ORGANISM_SAV2');
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
    this.controls.playbackTimeScale = s;
  }

  clearDiagnostics() {
    const cap = this.diag.queue_capacity;
    const lastKey = this.diag.last_consumed_key;
    const lastTick = this.diag.last_consumed_tick;
    const lastAgent = this.diag.last_agent_id;
    const lastBody = this.diag.last_body_id;
    this.diag = emptySav2Diagnostics(cap);
    this.diag.last_consumed_key = lastKey;
    this.diag.last_consumed_tick = lastTick;
    this.diag.last_agent_id = lastAgent;
    this.diag.last_body_id = lastBody;
    this.diag.mode_owner = getListeningModeOwner();
    this.provenanceHistory = [];
  }

  onRestore() {
    this.teardownPlayback('restore');
    releaseListeningMode('SELECTED_ORGANISM_SAV2');
    this.seen = new Set();
  }

  feedReceipt(receipt: Sav1ReceiptLike | null | undefined, executionMode: string) {
    if (!receipt) return;
    const pol = executionModePolicy(executionMode);
    this.modeStatus = pol.status;
    const agentId = String(receipt.agent_id || '');
    const bodyId = String(receipt.body_id || '');
    const preview = `${this.runId}|${agentId}|${bodyId}|${receipt.receipt_id || ''}|${Number(receipt.scientific_tick ?? 0)}|${this.profile.profile}`;

    if (!this.controls.listening || this.controls.paused || !pol.admit) {
      if (pol.mute) this.diag.muted += 1;
      if (receipt.receipt_id) this.seen.add(preview);
      return;
    }
    if (pol.mute) {
      this.backend?.silence(0.01);
      this.diag.muted += 1;
      this.queue = [];
      this.diag.queue_length = 0;
      return;
    }
    if (this.ignoreAtEnable.has(preview)) {
      this.diag.deduplicated += 1;
      this.seen.add(preview);
      return;
    }
    const result = admitSav2Receipt(
      this.queue,
      this.seen,
      receipt,
      this.runId,
      this.selectedAgentId,
      this.selectedBodyId,
      this.profile,
      this.diag,
      { accept: true },
    );
    if (result.admitted) {
      const last = this.queue[this.queue.length - 1];
      if (last) {
        this.lastInput = { left: [...last.left_input], right: [...last.right_input] };
        this.lastMapped = { left: [...last.left_amplitudes], right: [...last.right_amplitudes] };
      }
      this.drainSchedule();
    }
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
      const frames: Sav2ScheduleFrame[] = buildSav2Schedule(
        [item],
        this.profile,
        this.controls.playbackTimeScale,
      );
      const frame = frames[0];
      const left = this.controls.muted
        ? Z6()
        : frame.left_amplitudes.map((g) => Math.min(g, this.profile.limiter_threshold));
      const right = this.controls.muted
        ? Z6()
        : frame.right_amplitudes.map((g) => Math.min(g, this.profile.limiter_threshold));
      if (
        left.some((g, i) => g < frame.left_amplitudes[i])
        || right.some((g, i) => g < frame.right_amplitudes[i])
      ) {
        this.diag.limiter_activations += 1;
      }
      this.backend.setStereoBandGains(left, right, ramp, start);
      this.backend.setStereoBandGains(Z6(), Z6(), ramp, start + frame.duration_seconds);
      this.scheduleHorizonEnd = start + frame.duration_seconds;
      this.diag.rendered += 1;
      this.diag.last_consumed_key = item.receipt_id;
      this.diag.last_consumed_tick = item.scientific_tick;
      this.diag.last_agent_id = item.agent_id;
      this.diag.last_body_id = item.body_id;
      this.diag.left_nonzero_bands = countNonzeroBands(frame.left_amplitudes);
      this.diag.right_nonzero_bands = countNonzeroBands(frame.right_amplitudes);
      this.diag.limiter_activations = Math.max(
        this.diag.limiter_activations,
        this.backend.limiterActivations(),
      );
      const prov = buildSav2Provenance(frame, {
        device_sample_rate: this.backend.sampleRate(),
        audio_context_state: this.backend.state(),
        mode_owner: getListeningModeOwner(),
        playback_limiter_activated: this.diag.limiter_activations > 0,
        run_id: this.runId,
      });
      this.lastProvenance = prov;
      this.provenanceHistory.push(prov);
      while (this.provenanceHistory.length > PROVENANCE_CAP) this.provenanceHistory.shift();
    }
    this.diag.mode_owner = getListeningModeOwner();
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
    this.diag.mode_owner = getListeningModeOwner() === 'SELECTED_ORGANISM_SAV2'
      ? 'OFF'
      : getListeningModeOwner();
    if (this.backend) {
      this.backend.silence(0.01);
      this.backend.teardown();
      this.backend = null;
    }
  }

  snapshot(): Sav2EngineSnapshot {
    return {
      listening: this.controls.listening,
      muted: this.controls.muted,
      volume: this.controls.volume,
      playbackTimeScale: this.controls.playbackTimeScale,
      audioState: this.backend?.state() || 'closed',
      sampleRate: this.backend?.sampleRate() || 0,
      diagnostics: { ...this.diag, mode_owner: getListeningModeOwner() },
      modeStatus: this.modeStatus,
      modeOwner: getListeningModeOwner(),
      lastProvenance: this.lastProvenance,
      provenanceHistory: [...this.provenanceHistory],
      scheduledHorizon: this.profile.scheduled_horizon_seconds,
      compatible: this.compatible,
      selectedAgentId: this.selectedAgentId,
      selectedBodyId: this.selectedBodyId,
      availability: this.availability,
      lastMapped: this.lastMapped,
      lastInput: this.lastInput,
    };
  }
}
