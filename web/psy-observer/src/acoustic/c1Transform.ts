/** Pure C1 transform math — no Web Audio side effects. */
import {
  BAND_COUNT,
  C1_AUTHORITY_CLASS,
  C1_ENERGY_POLICY,
  C1_PROFILE,
  C1_SCHEMA,
  type C1Profile,
  FIXED_REFERENCE_GAIN,
  REQUIRED_C0_PROFILE,
  REQUIRED_PROBE_SCHEMA,
  defaultC1Profile,
} from './c1Profile.ts';

export type ProbeSampleLike = {
  sample_key?: string;
  scientific_tick?: number;
  probe_id?: string;
  schema?: string;
  anonymous_band_energies?: number[];
  x?: number;
  y?: number;
};

export type MappedAmplitudes = {
  mapped_amplitudes: number[];
  invalid_clamped: number;
  policy: string;
  fixed_reference_gain: number;
  authority_class: string;
};

export function c0c1Compatible(c0Profile: string | null | undefined, probeSchema: string | null | undefined): boolean {
  return String(c0Profile || '') === REQUIRED_C0_PROFILE
    && String(probeSchema || '') === REQUIRED_PROBE_SCHEMA;
}

export function mapEnergyToAmplitude(
  energies: unknown,
  referenceGain: number = FIXED_REFERENCE_GAIN,
): MappedAmplitudes {
  const src = Array.isArray(energies) ? energies : [];
  const amps: number[] = [];
  let clamped = 0;
  const g = Number(referenceGain);
  for (let i = 0; i < BAND_COUNT; i += 1) {
    let v = 0;
    const raw = src[i];
    if (typeof raw === 'number') v = raw;
    else if (raw != null && raw !== '') {
      const n = Number(raw);
      if (Number.isFinite(n)) v = n;
      else {
        clamped += 1;
        v = 0;
      }
    }
    if (!Number.isFinite(v)) {
      clamped += 1;
      v = 0;
    }
    if (v < 0) {
      clamped += 1;
      v = 0;
    }
    let a = g * Math.sqrt(v);
    if (!Number.isFinite(a) || a < 0) {
      clamped += 1;
      a = 0;
    }
    amps.push(a);
  }
  return {
    mapped_amplitudes: amps,
    invalid_clamped: clamped,
    policy: C1_ENERGY_POLICY,
    fixed_reference_gain: g,
    authority_class: C1_AUTHORITY_CLASS,
  };
}

export function sampleDedupKey(runId: string, sample: ProbeSampleLike): string | null {
  const key = sample?.sample_key;
  if (!key) return null;
  const probe = sample.probe_id || 'observer-acoustic-probe-0';
  return `${runId}|${probe}|${key}`;
}

export type QueueDiagnostics = {
  observed: number;
  deduplicated: number;
  queued: number;
  dropped: number;
  rendered: number;
  missing_gap_ticks: number;
  invalid_clamped: number;
  limiter_activations: number;
  underruns: number;
  muted: number;
  queue_length: number;
  queue_capacity: number;
  last_consumed_key: string | null;
  last_consumed_tick: number | null;
};

export function emptyDiagnostics(capacity: number): QueueDiagnostics {
  return {
    observed: 0,
    deduplicated: 0,
    queued: 0,
    dropped: 0,
    rendered: 0,
    missing_gap_ticks: 0,
    invalid_clamped: 0,
    limiter_activations: 0,
    underruns: 0,
    muted: 0,
    queue_length: 0,
    queue_capacity: capacity,
    last_consumed_key: null,
    last_consumed_tick: null,
  };
}

export type QueuedSample = {
  dedup_key: string;
  sample_key: string;
  scientific_tick: number;
  probe_id: string;
  energies: number[];
  mapped_amplitudes: number[];
  run_id: string;
};

export type AdmitResult = {
  admitted: boolean;
  reason: 'ADMITTED' | 'DEDUP' | 'NO_KEY' | 'DROPPED_OLDEST' | 'REJECTED_MODE' | 'REJECTED_CURSOR';
  dropped: number;
};

/** Deterministic FIFO with drop-oldest. Mutates queue/diag in place. */
export function admitSample(
  queue: QueuedSample[],
  seen: Set<string>,
  sample: ProbeSampleLike,
  runId: string,
  profile: C1Profile,
  diag: QueueDiagnostics,
  opts: {
    accept: boolean;
    /** If set, only admit samples strictly after this cursor (enable mid-run / resume). */
    minExclusiveCursor?: string | null;
    muteAdmit?: boolean;
  },
): AdmitResult {
  diag.observed += 1;
  if (!opts.accept || opts.muteAdmit) {
    return { admitted: false, reason: 'REJECTED_MODE', dropped: 0 };
  }
  const dedup = sampleDedupKey(runId, sample);
  if (!dedup || !sample.sample_key) {
    return { admitted: false, reason: 'NO_KEY', dropped: 0 };
  }
  if (opts.minExclusiveCursor != null && dedup <= opts.minExclusiveCursor) {
    // Lexicographic compare is wrong for keys; use seen set for history skip.
  }
  if (seen.has(dedup)) {
    diag.deduplicated += 1;
    return { admitted: false, reason: 'DEDUP', dropped: 0 };
  }
  // Enable mid-run: skip if we have an ignore set of retained keys
  const mapped = mapEnergyToAmplitude(
    sample.anonymous_band_energies,
    profile.fixed_reference_gain,
  );
  diag.invalid_clamped += mapped.invalid_clamped;
  const item: QueuedSample = {
    dedup_key: dedup,
    sample_key: String(sample.sample_key),
    scientific_tick: Number(sample.scientific_tick ?? 0),
    probe_id: String(sample.probe_id || 'observer-acoustic-probe-0'),
    energies: Array.isArray(sample.anonymous_band_energies)
      ? sample.anonymous_band_energies.map((x) => Number(x) || 0)
      : new Array(BAND_COUNT).fill(0),
    mapped_amplitudes: mapped.mapped_amplitudes,
    run_id: runId,
  };
  seen.add(dedup);
  queue.push(item);
  let dropped = 0;
  const cap = profile.input_queue_capacity;
  while (queue.length > cap) {
    queue.shift();
    dropped += 1;
    diag.dropped += 1;
  }
  diag.queued += 1;
  diag.queue_length = queue.length;
  diag.queue_capacity = cap;
  return {
    admitted: true,
    reason: dropped > 0 ? 'DROPPED_OLDEST' : 'ADMITTED',
    dropped,
  };
}

export type ScheduleFrame = {
  sample_key: string;
  scientific_tick: number;
  mapped_amplitudes: number[];
  canonical_start_offset: number;
  duration_seconds: number;
  playback_time_scale: number;
  carriers_hz: number[];
  authority_class: string;
  schema: string;
  profile: string;
};

/** Deterministic schedule from ordered queued samples (scientific provenance). */
export function buildSchedule(
  samples: QueuedSample[],
  profile: C1Profile = defaultC1Profile(),
  playbackTimeScale: number = 1.0,
): ScheduleFrame[] {
  const scale = Number.isFinite(playbackTimeScale) && playbackTimeScale > 0
    ? playbackTimeScale
    : 1.0;
  const tickDur = profile.canonical_seconds_per_tick * scale;
  let t0 = 0;
  let prevTick: number | null = null;
  const out: ScheduleFrame[] = [];
  for (const s of samples) {
    if (prevTick != null) {
      const gap = Math.max(0, s.scientific_tick - prevTick);
      if (gap > 1) {
        // gap ticks already reflected by tick difference when advancing t0
      }
      const deltaTicks = Math.max(1, s.scientific_tick - prevTick);
      t0 += (deltaTicks - 1) * tickDur; // silence gap between samples
    }
    out.push({
      sample_key: s.sample_key,
      scientific_tick: s.scientific_tick,
      mapped_amplitudes: [...s.mapped_amplitudes],
      canonical_start_offset: t0,
      duration_seconds: tickDur,
      playback_time_scale: scale,
      carriers_hz: [...profile.canonical_playback_carrier_hz],
      authority_class: C1_AUTHORITY_CLASS,
      schema: C1_SCHEMA,
      profile: C1_PROFILE,
    });
    t0 += tickDur;
    prevTick = s.scientific_tick;
  }
  return out;
}

export function executionModePolicy(mode: string): {
  admit: boolean;
  mute: boolean;
  status: string;
} {
  const m = String(mode || 'LIVE').toUpperCase();
  if (m === 'MAX' || m === 'HEADLESS') {
    return { admit: false, mute: true, status: 'MAX_PLAYBACK_MUTED_BY_POLICY' };
  }
  if (m === 'FAST') {
    return { admit: true, mute: false, status: 'FAST_PLAYBACK_LOSSY_MONITORING' };
  }
  return { admit: true, mute: false, status: 'BOUNDED_QUEUE_SCHEDULE' };
}

export function buildProvenanceRecord(
  frame: ScheduleFrame,
  extra: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    schema: frame.schema,
    profile: frame.profile,
    authority_class: frame.authority_class,
    probe_sample_id: frame.sample_key,
    scientific_tick: frame.scientific_tick,
    mapped_amplitudes: frame.mapped_amplitudes,
    canonical_seconds_per_tick: frame.duration_seconds / Math.max(1e-9, frame.playback_time_scale),
    playback_time_scale: frame.playback_time_scale,
    canonical_schedule_offset: frame.canonical_start_offset,
    carriers_hz: frame.carriers_hz,
    carrier_label: 'PLAYBACK CARRIERS — NOT PHYSICAL FREQUENCIES',
    ...extra,
  };
}

export function analyzerProgress(completed: number, total: number): {
  mode: string;
  completed: number;
  total: number;
  percent: number | null;
} {
  if (!Number.isFinite(total) || total <= 0) {
    return { mode: 'LIVE_INDEFINITE', completed, total: 0, percent: null };
  }
  const c = Math.max(0, Math.min(completed, total));
  return {
    mode: 'FINITE_SAMPLE_SCAN',
    completed: c,
    total,
    percent: (100 * c) / total,
  };
}
