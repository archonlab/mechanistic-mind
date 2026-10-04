/** CANONICAL_PHYSICAL_FIELD_SONIFICATION_V1 — shared C1 profile constants.
 * Must match mechanistic_mind/physical_system/canonical_physical_field_sonification.py
 * Prefer frame.world.canonical_physical_field_sonification when present.
 */
export const C1_SCHEMA = 'CANONICAL_PHYSICAL_FIELD_SONIFICATION_V1';
export const C1_PROFILE = 'CANONICAL_ABSTRACT_BAND_SONIFICATION_C1_V1';
export const C1_CAPABILITY = 'canonical_physical_field_sonification';
export const C1_MODE = 'CANONICAL_PHYSICAL_FIELD_SONIFICATION';
export const C1_MODE_LABEL = 'CANONICAL PHYSICAL-FIELD SONIFICATION';
export const C1_WARNING =
  'TRANSFORMED PLAYBACK OF ABSTRACT PHYSICAL FIELD · NOT PHYSICAL Hz · NOT SPL · NOT ORIGINAL HUMAN-AUDIBLE';
export const C1_TRANSFORM = 'SIX_FIXED_OSCILLATOR_CARRIERS';
export const C1_ENERGY_POLICY = 'SQRT_ENERGY_FIXED_REFERENCE';
export const C1_AUTHORITY_CLASS = 'PLAYBACK_DERIVED_NON_PHYSICAL';
export const REQUIRED_C0_PROFILE = 'ABSTRACT_ACOUSTIC_AUTHORITY_C0_V1';
export const REQUIRED_PROBE_SCHEMA = 'OBSERVER_ACOUSTIC_PROBE_V1';
export const BAND_COUNT = 6;
export const BAND_IDENTIFIERS = ['band_0', 'band_1', 'band_2', 'band_3', 'band_4', 'band_5'] as const;
/** Playback coordinates only — NOT physical frequencies. */
export const CANONICAL_PLAYBACK_CARRIER_HZ = [120, 200, 320, 480, 720, 1000] as const;
export const CARRIER_LABEL = 'PLAYBACK CARRIERS — NOT PHYSICAL FREQUENCIES';
export const FIXED_REFERENCE_GAIN = 0.25;
export const CANONICAL_SECONDS_PER_TICK = 0.05;
export const PLAYBACK_TIME_SCALE_DEFAULT = 1.0;
export const PLAYBACK_TIME_SCALE_OPTIONS = [0.25, 0.5, 1.0, 2.0] as const;
export const INPUT_QUEUE_CAPACITY = 64;
export const SCHEDULED_HORIZON_SECONDS = 0.5;
export const ENVELOPE_FRACTION_OF_TICK = 0.2;
export const MASTER_DEFAULT_VOLUME = 0.35;
export const LIMITER_THRESHOLD = 0.95;
export const MAX_POLICY = 'MAX_PLAYBACK_MUTED_BY_POLICY';
export const FAST_POLICY = 'FAST_PLAYBACK_LOSSY_MONITORING';
export const LEGACY_UNAVAILABLE = 'CANONICAL_SONIFICATION_UNAVAILABLE_LEGACY_EVIDENCE';

export type C1Profile = {
  schema: string;
  profile: string;
  capability: string;
  mode: string;
  mode_label: string;
  warning_label: string;
  transform: string;
  band_count: number;
  canonical_playback_carrier_hz: number[];
  carrier_label: string;
  carrier_hz_are_physical: boolean;
  energy_to_amplitude_policy: string;
  fixed_reference_gain: number;
  canonical_seconds_per_tick: number;
  canonical_seconds_per_tick_is_physical: boolean;
  input_queue_capacity: number;
  scheduled_horizon_seconds: number;
  envelope_fraction_of_tick: number;
  master_default_volume: number;
  limiter_threshold: number;
  max_policy: string;
  fast_policy: string;
  authority_class: string;
  required_c0_profile: string;
  required_probe_schema: string;
};

export function defaultC1Profile(): C1Profile {
  return {
    schema: C1_SCHEMA,
    profile: C1_PROFILE,
    capability: C1_CAPABILITY,
    mode: C1_MODE,
    mode_label: C1_MODE_LABEL,
    warning_label: C1_WARNING,
    transform: C1_TRANSFORM,
    band_count: BAND_COUNT,
    canonical_playback_carrier_hz: [...CANONICAL_PLAYBACK_CARRIER_HZ],
    carrier_label: CARRIER_LABEL,
    carrier_hz_are_physical: false,
    energy_to_amplitude_policy: C1_ENERGY_POLICY,
    fixed_reference_gain: FIXED_REFERENCE_GAIN,
    canonical_seconds_per_tick: CANONICAL_SECONDS_PER_TICK,
    canonical_seconds_per_tick_is_physical: false,
    input_queue_capacity: INPUT_QUEUE_CAPACITY,
    scheduled_horizon_seconds: SCHEDULED_HORIZON_SECONDS,
    envelope_fraction_of_tick: ENVELOPE_FRACTION_OF_TICK,
    master_default_volume: MASTER_DEFAULT_VOLUME,
    limiter_threshold: LIMITER_THRESHOLD,
    max_policy: MAX_POLICY,
    fast_policy: FAST_POLICY,
    authority_class: C1_AUTHORITY_CLASS,
    required_c0_profile: REQUIRED_C0_PROFILE,
    required_probe_schema: REQUIRED_PROBE_SCHEMA,
  };
}

export function profileFromWorld(world: any | null | undefined): C1Profile {
  const raw = world?.canonical_physical_field_sonification
    || world?.canonical_physical_field_sonification_profile;
  const base = defaultC1Profile();
  if (!raw || typeof raw !== 'object') return base;
  return {
    ...base,
    schema: String(raw.schema || base.schema),
    profile: String(raw.profile || base.profile),
    capability: String(raw.capability || base.capability),
    mode: String(raw.mode || base.mode),
    mode_label: String(raw.mode_label || base.mode_label),
    warning_label: String(raw.warning_label || base.warning_label),
    transform: String(raw.transform || base.transform),
    band_count: Number(raw.band_count ?? base.band_count),
    canonical_playback_carrier_hz: Array.isArray(raw.canonical_playback_carrier_hz)
      ? raw.canonical_playback_carrier_hz.map(Number)
      : base.canonical_playback_carrier_hz,
    carrier_label: String(raw.carrier_label || base.carrier_label),
    carrier_hz_are_physical: false,
    energy_to_amplitude_policy: String(raw.energy_to_amplitude_policy || base.energy_to_amplitude_policy),
    fixed_reference_gain: Number(raw.fixed_reference_gain ?? base.fixed_reference_gain),
    canonical_seconds_per_tick: Number(raw.canonical_seconds_per_tick ?? base.canonical_seconds_per_tick),
    canonical_seconds_per_tick_is_physical: false,
    input_queue_capacity: Number(raw.input_queue_capacity ?? base.input_queue_capacity),
    scheduled_horizon_seconds: Number(raw.scheduled_horizon_seconds ?? base.scheduled_horizon_seconds),
    envelope_fraction_of_tick: Number(
      raw.envelope?.fraction_of_tick ?? raw.envelope_fraction_of_tick ?? base.envelope_fraction_of_tick,
    ),
    master_default_volume: Number(raw.master_default_volume ?? base.master_default_volume),
    limiter_threshold: Number(raw.limiter_threshold ?? base.limiter_threshold),
    max_policy: String(raw.max_policy || base.max_policy),
    fast_policy: String(raw.fast_policy || base.fast_policy),
    authority_class: String(raw.authority_class || base.authority_class),
    required_c0_profile: String(raw.required_c0_profile || base.required_c0_profile),
    required_probe_schema: String(raw.required_probe_schema || base.required_probe_schema),
  };
}
