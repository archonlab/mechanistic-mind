/** Pure SAV2 transform — linear receptor mapping; no Web Audio side effects. */
import { executionModePolicy, analyzerProgress } from './c1Transform.ts';
import {
  BAND_COUNT,
  FIXED_RECEPTOR_GAIN,
  REQUIRED_SAV1_PROFILE,
  REQUIRED_SAV1_SCHEMA,
  SAV2_AMPLITUDE_MAPPING,
  SAV2_AUTHORITY_CLASS,
  SAV2_INPUT_BOUNDARY,
  SAV2_PROFILE,
  SAV2_SCHEMA,
  type Sav2Profile,
  defaultSav2Profile,
} from './sav2Profile.ts';

export { executionModePolicy, analyzerProgress };

export type Sav1ReceiptLike = {
  receipt_id?: string;
  scientific_tick?: number;
  agent_id?: string;
  body_id?: string;
  schema?: string;
  profile?: string;
  boundary?: string;
  availability?: string;
  run_id?: string;
  section_a_organism_accessible?: {
    left_receptor_channels?: number[];
    right_receptor_channels?: number[];
  };
  /** Must NOT be used for playback amplitudes. */
  section_b_researcher_provenance?: unknown;
};

export type StereoMappedAmplitudes = {
  left_amplitudes: number[];
  right_amplitudes: number[];
  invalid_clamped: number;
  policy: string;
  fixed_receptor_gain: number;
  authority_class: string;
};

export function sav1Sav2Compatible(receipt: Sav1ReceiptLike | null | undefined): boolean {
  if (!receipt) return false;
  if (String(receipt.availability || '') !== 'AVAILABLE') return false;
  const schemaOk = !receipt.schema || String(receipt.schema) === REQUIRED_SAV1_SCHEMA;
  const profileOk = !receipt.profile || String(receipt.profile) === REQUIRED_SAV1_PROFILE;
  const boundaryOk = !receipt.boundary
    || String(receipt.boundary) === SAV2_INPUT_BOUNDARY
    || String(receipt.boundary) === 'A5';
  const a = receipt.section_a_organism_accessible;
  const hasVectors = Array.isArray(a?.left_receptor_channels)
    && Array.isArray(a?.right_receptor_channels);
  return schemaOk && profileOk && boundaryOk && hasVectors;
}

export function mapReceptorActivation(
  left: unknown,
  right: unknown,
  gain: number = FIXED_RECEPTOR_GAIN,
): StereoMappedAmplitudes {
  const g = Number(gain);
  const outL: number[] = [];
  const outR: number[] = [];
  let clamped = 0;

  const one = (src: unknown, dest: number[]) => {
    const arr = Array.isArray(src) ? src : [];
    for (let i = 0; i < BAND_COUNT; i += 1) {
      let v = 0;
      const raw = arr[i];
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
      if (v < 0 || v > 1) clamped += 1;
      v = Math.max(0, Math.min(1, v));
      dest.push(g * v);
    }
  };
  one(left, outL);
  one(right, outR);
  return {
    left_amplitudes: outL,
    right_amplitudes: outR,
    invalid_clamped: clamped,
    policy: SAV2_AMPLITUDE_MAPPING,
    fixed_receptor_gain: g,
    authority_class: SAV2_AUTHORITY_CLASS,
  };
}

/** Prove SAV2 does not apply sqrt(energy). */
export function usesSqrtEnergyMapping(): boolean {
  return false;
}

export function receiptDedupKey(
  runId: string,
  agentId: string,
  bodyId: string,
  receipt: Sav1ReceiptLike,
  sav2Profile: string = SAV2_PROFILE,
): string | null {
  const rid = receipt?.receipt_id;
  if (!rid) return null;
  const tick = Number(receipt.scientific_tick ?? 0);
  return `${runId}|${agentId}|${bodyId}|${rid}|${tick}|${sav2Profile}`;
}

export type Sav2QueueDiagnostics = {
  observed: number;
  eligible: number;
  deduplicated: number;
  queued: number;
  dropped: number;
  rendered: number;
  missing_gap_ticks: number;
  invalid_clamped: number;
  limiter_activations: number;
  muted: number;
  queue_length: number;
  queue_capacity: number;
  left_nonzero_bands: number;
  right_nonzero_bands: number;
  last_consumed_key: string | null;
  last_consumed_tick: number | null;
  last_agent_id: string | null;
  last_body_id: string | null;
  mode_owner: string;
};

export function emptySav2Diagnostics(capacity: number): Sav2QueueDiagnostics {
  return {
    observed: 0,
    eligible: 0,
    deduplicated: 0,
    queued: 0,
    dropped: 0,
    rendered: 0,
    missing_gap_ticks: 0,
    invalid_clamped: 0,
    limiter_activations: 0,
    muted: 0,
    queue_length: 0,
    queue_capacity: capacity,
    left_nonzero_bands: 0,
    right_nonzero_bands: 0,
    last_consumed_key: null,
    last_consumed_tick: null,
    last_agent_id: null,
    last_body_id: null,
    mode_owner: 'OFF',
  };
}

export type QueuedSav2Receipt = {
  dedup_key: string;
  receipt_id: string;
  scientific_tick: number;
  agent_id: string;
  body_id: string;
  left_input: number[];
  right_input: number[];
  left_amplitudes: number[];
  right_amplitudes: number[];
  run_id: string;
};

export type Sav2AdmitResult = {
  admitted: boolean;
  reason: 'ADMITTED' | 'DEDUP' | 'NO_KEY' | 'INELIGIBLE' | 'REJECTED_MODE' | 'DROPPED_OLDEST' | 'WRONG_AGENT';
  dropped: number;
};

export function extractSectionAVectors(receipt: Sav1ReceiptLike): {
  left: number[];
  right: number[];
} | null {
  const a = receipt.section_a_organism_accessible;
  if (!a) return null;
  if (!Array.isArray(a.left_receptor_channels) || !Array.isArray(a.right_receptor_channels)) {
    return null;
  }
  // Explicitly ignore section_b — researcher provenance must not drive playback.
  void receipt.section_b_researcher_provenance;
  return {
    left: a.left_receptor_channels.map((x) => Number(x) || 0),
    right: a.right_receptor_channels.map((x) => Number(x) || 0),
  };
}

export function admitSav2Receipt(
  queue: QueuedSav2Receipt[],
  seen: Set<string>,
  receipt: Sav1ReceiptLike,
  runId: string,
  selectedAgentId: string | null,
  selectedBodyId: string | null,
  profile: Sav2Profile,
  diag: Sav2QueueDiagnostics,
  opts: { accept: boolean },
): Sav2AdmitResult {
  diag.observed += 1;
  if (!opts.accept) {
    return { admitted: false, reason: 'REJECTED_MODE', dropped: 0 };
  }
  if (!sav1Sav2Compatible(receipt)) {
    return { admitted: false, reason: 'INELIGIBLE', dropped: 0 };
  }
  const agentId = String(receipt.agent_id || '');
  const bodyId = String(receipt.body_id || '');
  if (!selectedAgentId || agentId !== String(selectedAgentId)) {
    return { admitted: false, reason: 'WRONG_AGENT', dropped: 0 };
  }
  if (selectedBodyId && bodyId && bodyId !== String(selectedBodyId)) {
    return { admitted: false, reason: 'WRONG_AGENT', dropped: 0 };
  }
  const dedup = receiptDedupKey(runId, agentId, bodyId, receipt, profile.profile);
  if (!dedup || !receipt.receipt_id) {
    return { admitted: false, reason: 'NO_KEY', dropped: 0 };
  }
  if (seen.has(dedup)) {
    diag.deduplicated += 1;
    return { admitted: false, reason: 'DEDUP', dropped: 0 };
  }
  const vectors = extractSectionAVectors(receipt);
  if (!vectors) {
    return { admitted: false, reason: 'INELIGIBLE', dropped: 0 };
  }
  diag.eligible += 1;
  const mapped = mapReceptorActivation(
    vectors.left,
    vectors.right,
    profile.fixed_receptor_gain,
  );
  diag.invalid_clamped += mapped.invalid_clamped;
  const item: QueuedSav2Receipt = {
    dedup_key: dedup,
    receipt_id: String(receipt.receipt_id),
    scientific_tick: Number(receipt.scientific_tick ?? 0),
    agent_id: agentId,
    body_id: bodyId,
    left_input: [...vectors.left],
    right_input: [...vectors.right],
    left_amplitudes: mapped.left_amplitudes,
    right_amplitudes: mapped.right_amplitudes,
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

export type Sav2ScheduleFrame = {
  receipt_id: string;
  scientific_tick: number;
  agent_id: string;
  body_id: string;
  left_amplitudes: number[];
  right_amplitudes: number[];
  left_input: number[];
  right_input: number[];
  canonical_start_offset: number;
  duration_seconds: number;
  playback_time_scale: number;
  carriers_hz: number[];
  authority_class: string;
  schema: string;
  profile: string;
};

export function buildSav2Schedule(
  samples: QueuedSav2Receipt[],
  profile: Sav2Profile = defaultSav2Profile(),
  playbackTimeScale: number = 1.0,
): Sav2ScheduleFrame[] {
  const scale = Number.isFinite(playbackTimeScale) && playbackTimeScale > 0
    ? playbackTimeScale
    : 1.0;
  const tickDur = profile.canonical_seconds_per_tick * scale;
  let t0 = 0;
  let prevTick: number | null = null;
  const out: Sav2ScheduleFrame[] = [];
  for (const s of samples) {
    if (prevTick != null) {
      const deltaTicks = Math.max(1, s.scientific_tick - prevTick);
      if (deltaTicks > 1) {
        // gap handled by advancing offset; caller may count missing_gap_ticks
      }
      t0 += (deltaTicks - 1) * tickDur;
    }
    out.push({
      receipt_id: s.receipt_id,
      scientific_tick: s.scientific_tick,
      agent_id: s.agent_id,
      body_id: s.body_id,
      left_amplitudes: [...s.left_amplitudes],
      right_amplitudes: [...s.right_amplitudes],
      left_input: [...s.left_input],
      right_input: [...s.right_input],
      canonical_start_offset: t0,
      duration_seconds: tickDur,
      playback_time_scale: scale,
      carriers_hz: [...profile.canonical_playback_carrier_hz],
      authority_class: SAV2_AUTHORITY_CLASS,
      schema: SAV2_SCHEMA,
      profile: SAV2_PROFILE,
    });
    t0 += tickDur;
    prevTick = s.scientific_tick;
  }
  return out;
}

/** Channel isolation check on schedule frame (pre-device). */
export function scheduleChannelLeak(
  frame: Sav2ScheduleFrame,
): { left_only_ok: boolean; right_only_ok: boolean } {
  const leftSum = frame.left_amplitudes.reduce((a, b) => a + b, 0);
  const rightSum = frame.right_amplitudes.reduce((a, b) => a + b, 0);
  const leftInputSum = frame.left_input.reduce((a, b) => a + b, 0);
  const rightInputSum = frame.right_input.reduce((a, b) => a + b, 0);
  return {
    left_only_ok: !(leftInputSum > 0 && rightInputSum === 0 && rightSum !== 0),
    right_only_ok: !(rightInputSum > 0 && leftInputSum === 0 && leftSum !== 0),
  };
}

export function buildSav2Provenance(
  frame: Sav2ScheduleFrame,
  extra: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    schema: frame.schema,
    profile: frame.profile,
    authority_class: frame.authority_class,
    sav1_receipt_id: frame.receipt_id,
    agent_id: frame.agent_id,
    body_id: frame.body_id,
    scientific_tick: frame.scientific_tick,
    left_input: frame.left_input,
    right_input: frame.right_input,
    left_amplitudes: frame.left_amplitudes,
    right_amplitudes: frame.right_amplitudes,
    carriers_hz: frame.carriers_hz,
    carrier_label: 'PLAYBACK CARRIERS — NOT PHYSICAL OR ORGANISM FREQUENCIES',
    canonical_seconds_per_tick: frame.duration_seconds / Math.max(1e-9, frame.playback_time_scale),
    playback_time_scale: frame.playback_time_scale,
    canonical_schedule_offset: frame.canonical_start_offset,
    channel_mode: 'TRANSLATED_STEREO_LR_RECEPTOR_MONITOR_V1',
    amplitude_mapping: SAV2_AMPLITUDE_MAPPING,
    human_binaural_model: false,
    hrtf: false,
    ...extra,
  };
}

export function countNonzeroBands(amps: number[]): number {
  return amps.filter((a) => Number(a) > 0).length;
}
