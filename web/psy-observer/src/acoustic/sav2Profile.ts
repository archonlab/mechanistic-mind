/**
 * SAV2 profile — SELECTED_ORGANISM_AUDITORY_SONIFICATION_V1.
 * Carriers reference C1 CANONICAL_PLAYBACK_CARRIER_HZ (not redefined).
 */
import {
  BAND_COUNT,
  CANONICAL_PLAYBACK_CARRIER_HZ,
  CANONICAL_SECONDS_PER_TICK,
  ENVELOPE_FRACTION_OF_TICK,
  INPUT_QUEUE_CAPACITY,
  MASTER_DEFAULT_VOLUME,
  PLAYBACK_TIME_SCALE_DEFAULT,
  PLAYBACK_TIME_SCALE_OPTIONS,
  REQUIRED_C0_PROFILE,
  SCHEDULED_HORIZON_SECONDS,
  LIMITER_THRESHOLD,
} from './c1Profile.ts';

export const SAV2_SCHEMA = 'SELECTED_ORGANISM_AUDITORY_SONIFICATION_V1';
export const SAV2_PROFILE = 'CANONICAL_ORGANISM_RECEPTOR_SONIFICATION_SAV2_V1';
export const SAV2_CAPABILITY = 'selected_organism_auditory_sonification';
export const SAV2_MODE = 'SELECTED_ORGANISM_AUDITORY_SONIFICATION';
export const SAV2_MODE_LABEL = 'SELECTED ORGANISM AUDITORY SONIFICATION';
export const SAV2_WARNING =
  'TRANSLATED MONITOR OF ORGANISM RECEPTOR CHANNELS · POST-PHENOTYPE · PRE-COGNITION · NOT HUMAN HEARING · NOT MIND READING';
export const SAV2_INPUT_BOUNDARY = 'A5_OSC_LR_ACCESSIBLE_OBSERVATION_PRE_COGNITION';
export const SAV2_AUTHORITY_CLASS = 'PLAYBACK_DERIVED_TRANSLATED_RECEPTOR_MONITOR';
export const SAV2_AMPLITUDE_MAPPING = 'LINEAR_RECEPTOR_ACTIVATION_FIXED_REFERENCE_V1';
export const SAV2_CHANNEL_MODE = 'TRANSLATED_STEREO_LR_RECEPTOR_MONITOR_V1';
export const SAV2_CARRIER_LABEL =
  'PLAYBACK CARRIERS — NOT PHYSICAL OR ORGANISM FREQUENCIES';
export const SAV2_LISTENING_OWNERSHIP = 'MUTUALLY_EXCLUSIVE_LISTENING_MODES';
export const REQUIRED_SAV1_PROFILE = 'ORGANISM_AUDITORY_BOUNDARY_A5_V1';
export const REQUIRED_SAV1_SCHEMA = 'SELECTED_ORGANISM_AUDITORY_BOUNDARY_RECEIPT_V1';
export const FIXED_RECEPTOR_GAIN = 0.35;
export const SAV2_LEGACY_UNAVAILABLE =
  'SELECTED_ORGANISM_AUDITORY_SONIFICATION_UNAVAILABLE_LEGACY_EVIDENCE';
export const C1_CARRIER_AUTHORITY = 'CANONICAL_ABSTRACT_BAND_SONIFICATION_C1_V1';

export {
  BAND_COUNT,
  CANONICAL_PLAYBACK_CARRIER_HZ,
  CANONICAL_SECONDS_PER_TICK,
  ENVELOPE_FRACTION_OF_TICK,
  INPUT_QUEUE_CAPACITY,
  MASTER_DEFAULT_VOLUME,
  PLAYBACK_TIME_SCALE_DEFAULT,
  PLAYBACK_TIME_SCALE_OPTIONS,
  REQUIRED_C0_PROFILE,
  SCHEDULED_HORIZON_SECONDS,
  LIMITER_THRESHOLD,
};

export type Sav2Profile = {
  schema: string;
  profile: string;
  capability: string;
  mode: string;
  mode_label: string;
  warning_label: string;
  input_boundary: string;
  authority_class: string;
  amplitude_mapping: string;
  fixed_receptor_gain: number;
  channel_mode: string;
  band_count: number;
  canonical_playback_carrier_hz: number[];
  carrier_label: string;
  carrier_authority: string;
  carrier_hz_are_physical: boolean;
  carrier_hz_are_organism_frequencies: boolean;
  canonical_seconds_per_tick: number;
  canonical_seconds_per_tick_is_physical: boolean;
  input_queue_capacity: number;
  scheduled_horizon_seconds: number;
  envelope_fraction_of_tick: number;
  master_default_volume: number;
  limiter_threshold: number;
  required_sav1_profile: string;
  required_c0_profile: string;
  listening_mode_ownership: string;
  c1_and_sav2_simultaneous_audio: boolean;
};

export function defaultSav2Profile(): Sav2Profile {
  return {
    schema: SAV2_SCHEMA,
    profile: SAV2_PROFILE,
    capability: SAV2_CAPABILITY,
    mode: SAV2_MODE,
    mode_label: SAV2_MODE_LABEL,
    warning_label: SAV2_WARNING,
    input_boundary: SAV2_INPUT_BOUNDARY,
    authority_class: SAV2_AUTHORITY_CLASS,
    amplitude_mapping: SAV2_AMPLITUDE_MAPPING,
    fixed_receptor_gain: FIXED_RECEPTOR_GAIN,
    channel_mode: SAV2_CHANNEL_MODE,
    band_count: BAND_COUNT,
    // Shared C1 carrier table — not an independent divergent copy intent.
    canonical_playback_carrier_hz: [...CANONICAL_PLAYBACK_CARRIER_HZ],
    carrier_label: SAV2_CARRIER_LABEL,
    carrier_authority: C1_CARRIER_AUTHORITY,
    carrier_hz_are_physical: false,
    carrier_hz_are_organism_frequencies: false,
    canonical_seconds_per_tick: CANONICAL_SECONDS_PER_TICK,
    canonical_seconds_per_tick_is_physical: false,
    input_queue_capacity: INPUT_QUEUE_CAPACITY,
    scheduled_horizon_seconds: SCHEDULED_HORIZON_SECONDS,
    envelope_fraction_of_tick: ENVELOPE_FRACTION_OF_TICK,
    master_default_volume: MASTER_DEFAULT_VOLUME,
    limiter_threshold: LIMITER_THRESHOLD,
    required_sav1_profile: REQUIRED_SAV1_PROFILE,
    required_c0_profile: REQUIRED_C0_PROFILE,
    listening_mode_ownership: SAV2_LISTENING_OWNERSHIP,
    c1_and_sav2_simultaneous_audio: false,
  };
}

export function sav2ProfileFromWorld(world: any | null | undefined): Sav2Profile {
  const raw = world?.selected_organism_auditory_sonification
    || world?.selected_organism_auditory_sonification_profile;
  const base = defaultSav2Profile();
  if (!raw || typeof raw !== 'object') return base;
  return {
    ...base,
    schema: String(raw.schema || base.schema),
    profile: String(raw.profile || base.profile),
    fixed_receptor_gain: Number(raw.fixed_receptor_gain ?? base.fixed_receptor_gain),
    canonical_playback_carrier_hz: Array.isArray(raw.canonical_playback_carrier_hz)
      ? raw.canonical_playback_carrier_hz.map(Number)
      : base.canonical_playback_carrier_hz,
    input_queue_capacity: Number(raw.input_queue_capacity ?? base.input_queue_capacity),
    canonical_seconds_per_tick: Number(
      raw.canonical_seconds_per_tick ?? base.canonical_seconds_per_tick,
    ),
    envelope_fraction_of_tick: Number(
      raw.envelope_fraction_of_tick ?? base.envelope_fraction_of_tick,
    ),
    limiter_threshold: Number(raw.limiter_threshold ?? base.limiter_threshold),
    master_default_volume: Number(raw.master_default_volume ?? base.master_default_volume),
  };
}
