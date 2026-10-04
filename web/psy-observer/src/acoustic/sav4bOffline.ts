/** SAV4B constants — pure TS for node --test (no JSX). */
import {
  CANONICAL_PLAYBACK_CARRIER_HZ,
  CANONICAL_SECONDS_PER_TICK,
  ENVELOPE_FRACTION_OF_TICK,
  FIXED_RECEPTOR_GAIN,
  LIMITER_THRESHOLD,
  SCHEDULED_HORIZON_SECONDS,
  SAV2_PROFILE,
} from './sav2Profile.ts';

export const SAV4B_SCHEMA = 'SELECTED_ORGANISM_AUDITORY_OFFLINE_PLAYER_SAV4B_V1';
export const SAV4B_CAPABILITY = 'selected_organism_auditory_offline_playback';
export const SAV4B_PROFILE = 'SAV4A_SCHEDULE_TRANSLATED_STEREO_OFFLINE_PLAYER_SAV4B_V1';
export const SAV4B_AUTHORITY = 'RESEARCHER_DERIVED_PLAYBACK_OVER_SAV4A_SCHEDULE';
export const SAV4B_TITLE = 'OFFLINE SAVED-RUN AUDITORY RECONSTRUCTION · SAV4B';
export const SAV4B_WARNING =
  'DERIVED TRANSLATED MONITOR OF RECORDED ORGANISM RECEPTOR CHANNELS · NOT PHYSICAL AUDIO · NOT LITERAL ORGANISM HEARING';
export const SAV4B_WARNING_GAPS = 'GAPS ARE NOT SILENCE';
export const SAV4B_WARNING_TICK = '0.05 s/tick is canonical playback timing, not physical time';
export const SAV4B_INPUT = 'SAV4A_DETERMINISTIC_SCHEDULE_ONLY';
export const SAV4B_OWNER = 'OFFLINE_SAV4B';

export {
  CANONICAL_PLAYBACK_CARRIER_HZ,
  CANONICAL_SECONDS_PER_TICK,
  ENVELOPE_FRACTION_OF_TICK,
  FIXED_RECEPTOR_GAIN,
  LIMITER_THRESHOLD,
  SCHEDULED_HORIZON_SECONDS,
  SAV2_PROFILE,
};

/** Schedule item shape produced by SAV4A (consumed as-is; not re-derived from evidence). */
export type Sav4aScheduleItem = {
  schedule_item_id?: string;
  source_normalized_record_id?: string;
  segment_id?: string;
  observation_tick?: number;
  canonical_start_seconds?: number;
  canonical_duration_seconds?: number;
  envelope_fraction_of_tick?: number;
  left_input?: number[];
  right_input?: number[];
  left_amplitudes?: number[];
  right_amplitudes?: number[];
  fixed_receptor_gain?: number;
  limiter_threshold?: number;
  carriers_hz?: number[];
  true_zero?: boolean;
  authority_class?: string;
  compatibility_class?: string;
  gap_boundary?: boolean;
  canonical_seconds_per_tick?: number;
  canonical_seconds_per_tick_is_physical?: boolean;
};

export type Sav4aSegmentLike = {
  segment_id?: string;
  schedule_available?: boolean;
  completeness?: string;
  authority_badge?: string;
  compatibility_class?: string;
  first_tick?: number | null;
  last_tick?: number | null;
  gap_count?: number;
  run_id?: string;
  runtime_generation?: string;
  agent_id?: string;
  body_id?: string;
};

export type Sav4aPayloadLike = {
  schedule_available?: boolean;
  schedule_digest?: string;
  schedule_items?: Sav4aScheduleItem[];
  schedule_items_preview?: Sav4aScheduleItem[];
  identity_segments?: Sav4aSegmentLike[];
  run_id?: string;
  normalized_record_digest?: string;
  truncated?: { schedule?: boolean; schedule_total?: number };
};

export function playbackEnabledForSegment(
  sav4a: Sav4aPayloadLike | null | undefined,
  seg: Sav4aSegmentLike | null | undefined,
): { enabled: boolean; reason: string } {
  if (!sav4a) return { enabled: false, reason: 'NO_SAV4A_PAYLOAD' };
  if (!seg) return { enabled: false, reason: 'NO_SEGMENT' };
  if (seg.schedule_available === false) {
    return { enabled: false, reason: String(seg.completeness || 'SCHEDULE_UNAVAILABLE') };
  }
  if (String(seg.completeness || '') === 'PROFILE_UNKNOWN_OR_INCOMPATIBLE') {
    return { enabled: false, reason: 'PROFILE_UNKNOWN_OR_INCOMPATIBLE' };
  }
  if (String(seg.completeness || '') === 'UNAVAILABLE') {
    return { enabled: false, reason: 'UNAVAILABLE' };
  }
  if (String(seg.completeness || '') === 'CONFLICTING_DUPLICATE') {
    return { enabled: false, reason: 'CONFLICTING_DUPLICATE' };
  }
  if (!sav4a.schedule_available && seg.schedule_available !== true) {
    return { enabled: false, reason: 'SCHEDULE_UNAVAILABLE' };
  }
  const items = scheduleItemsForSegment(sav4a, String(seg.segment_id || ''));
  if (!items.length) return { enabled: false, reason: 'EMPTY_SCHEDULE' };
  return { enabled: true, reason: 'OK' };
}

export function scheduleItemsForSegment(
  sav4a: Sav4aPayloadLike,
  segmentId: string,
): Sav4aScheduleItem[] {
  const raw = Array.isArray(sav4a.schedule_items) && sav4a.schedule_items.length
    ? sav4a.schedule_items
    : (sav4a.schedule_items_preview || []);
  const sid = String(segmentId || '');
  const filtered = sid
    ? raw.filter((it) => String(it.segment_id || '') === sid)
    : [...raw];
  return filtered
    .filter((it) => Array.isArray(it.left_amplitudes) && Array.isArray(it.right_amplitudes))
    .slice()
    .sort((a, b) => Number(a.observation_tick ?? 0) - Number(b.observation_tick ?? 0));
}

export function segmentDurationSeconds(items: Sav4aScheduleItem[]): number {
  if (!items.length) return 0;
  let maxEnd = 0;
  for (const it of items) {
    const start = Number(it.canonical_start_seconds ?? 0);
    const dur = Number(it.canonical_duration_seconds ?? CANONICAL_SECONDS_PER_TICK);
    maxEnd = Math.max(maxEnd, start + dur);
  }
  return maxEnd;
}

export function indexForTick(items: Sav4aScheduleItem[], tick: number): number {
  if (!items.length) return 0;
  let best = 0;
  for (let i = 0; i < items.length; i += 1) {
    if (Number(items[i].observation_tick ?? 0) <= tick) best = i;
    else break;
  }
  return best;
}
