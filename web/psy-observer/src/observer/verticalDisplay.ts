/** OBSERVER_VERTICAL_DISPLAY_CONTRACT_V1 / V1_1 — researcher display types (read-only). */

export const VERTICAL_DISPLAY_SCHEMA = 'OBSERVER_VERTICAL_DISPLAY_CONTRACT_V1';
export const VERTICAL_DISPLAY_SCHEMA_V1_1 = 'OBSERVER_VERTICAL_DISPLAY_CONTRACT_V1_1';
export const VERTICAL_DISPLAY_SLICE = 'OBSERVER_TERRAIN_RELIEF_AND_FREE_SPACE_MARKERS_V1';
export const VERTICAL_TRAIL_PROFILE = 'OBSERVER_ENTITY_HEIGHT_FALL_TRAILS_V1';

export type TerrainDisplayMode = 'OPTICAL' | 'ELEVATION' | 'DELTA';
export type TrailDisplayMode = 'OFF' | 'SELECTED' | 'UNSUPPORTED';
export type TrailLengthMode = 'SHORT' | 'NORMAL' | 'LONG';

export const TRAIL_LENGTH_SAMPLES: Record<TrailLengthMode, number> = {
  SHORT: 16,
  NORMAL: 32,
  LONG: 48,
};

export type VerticalSparseDelta = {
  cell_x: number;
  cell_y: number;
  baseline_elevation: number;
  current_elevation: number;
  signed_delta: number;
  revision: number;
  delta_id?: string;
  baseline_checksum?: string;
  resolved_checksum?: string;
  transaction_id?: string | null;
  source?: string;
  authority?: string;
};

export type VerticalEntityState = {
  kind: string;
  id: string;
  x: number;
  y: number;
  base_z?: number | null;
  centre_z?: number | null;
  vertical_half_extent?: number | null;
  support_z?: number | null;
  clearance?: number | null;
  below_support?: boolean;
  vertical_out_of_slice?: boolean;
  vx?: number | null;
  vy?: number | null;
  vz?: number | null;
  grounded?: boolean | null;
  support_state?: string | null;
  physical_state?: string | null;
  held_constrained?: boolean;
  collision_radius?: number | null;
  optical_radius?: number | null;
  optical_radius_is_not_collision_radius?: boolean;
  glyph_is_not_physics?: boolean;
  holder_body_id?: string | null;
  manipulator_id?: string | null;
  dynamics_eligible_tick?: number | null;
  detached_terrain_provenance?: Record<string, unknown> | null;
  z_available?: boolean;
  authority?: string;
};

export type VerticalEventMarker = {
  event_class: 'RELEASE' | 'SUPPORT_LOSS' | 'LANDING_RESPONSE' | 'ACOUSTIC_EMISSION' | string;
  tick: number;
  entity_id?: string | null;
  x?: number | null;
  y?: number | null;
  z?: number | null;
  receipt_kind?: string;
  receipt_ref?: Record<string, unknown>;
  display_lifetime_ticks?: number;
  authority?: string;
  impulse_magnitude?: number;
  dissipated_energy?: number;
  emitted_energy?: number;
  band_profile?: string;
  label?: string;
  excavation_induced?: boolean;
  entity_z_unchanged?: boolean;
  dynamics_eligible_tick?: number;
  release_tick?: number;
  audio_playback?: boolean;
  creates_impact?: boolean;
  creates_sound?: boolean;
};

export type VerticalTrailSample = {
  tick: number;
  entity_id: string;
  entity_kind?: string;
  x: number;
  y: number;
  base_z: number;
  centre_z?: number | null;
  support_z?: number | null;
  clearance?: number | null;
  vz?: number | null;
  support_state?: string | null;
  physical_state?: string | null;
  held_constrained?: boolean;
  authoritative_source?: string;
  authority?: string;
  discontinuity?: boolean;
  discontinuity_reason?: string;
  release_tick?: number | null;
  support_loss_tick?: number | null;
  landing_response_key?: string | null;
  acoustic_source_id?: string | null;
};

export type VerticalTrailSegment = {
  segment_id?: string;
  entity_id: string;
  entity_kind?: string;
  start_reason?: string;
  start_tick?: number;
  end_tick?: number | null;
  end_reason?: string | null;
  active?: boolean;
  sample_count?: number;
  sample_policy?: string;
  z_min?: number | null;
  z_max?: number | null;
  clearance_min?: number | null;
  clearance_max?: number | null;
  vz_min?: number | null;
  vz_max?: number | null;
  release_tick?: number | null;
  support_loss_tick?: number | null;
  landing_tick?: number | null;
  acoustic_tick?: number | null;
  discontinuity_reason?: string | null;
  authority?: string;
  samples?: VerticalTrailSample[];
};

export type ElevationGrid = {
  height: number;
  width: number;
  order?: string;
  coordinate?: string;
  sample_policy?: string;
  data?: number[][] | null;
  elev_min?: number | null;
  elev_max?: number | null;
  authority?: string;
  subsurface_serialized?: boolean;
  unavailable_reason?: string;
};

export type VerticalDisplayContract = {
  schema_version?: string;
  schema_compatible_with?: string[];
  display_slice?: string;
  display_profiles?: string[];
  display_contract?: string;
  display_profile?: string;
  researcher_only?: boolean;
  agent_accessible?: boolean;
  width?: number;
  height?: number;
  topology?: string;
  surface_generation?: number;
  deltas_checksum?: string;
  manifest_checksum?: string;
  elev_min?: number | null;
  elev_max?: number | null;
  cell_centre_elevation?: ElevationGrid | null;
  sparse_deltas?: VerticalSparseDelta[];
  entities_vertical?: VerticalEntityState[];
  events_recent?: VerticalEventMarker[];
  trail_segments?: VerticalTrailSegment[];
  trail_contract?: string;
  trail_sample_authority?: string;
  trail_sample_source?: string;
  samples_per_entity_default?: number;
  samples_per_entity_hard_max?: number;
  visible_trail_entity_cap?: number;
  total_sample_hard_cap?: number;
  event_history_cap?: number;
  event_display_lifetime_ticks?: number;
  cache_hit?: boolean;
  dense_subsurface_serialized?: boolean;
  classification?: Record<string, string[]>;
  not_modelled?: string[];
  interpolation_default?: string;
  fast_max_sampling_policy?: string;
  headless_display_cost_policy?: string;
};

export const DEFAULT_VERTICAL_EXAGGERATION = 2;
export const VERTICAL_EXAGGERATION_LABEL = 'DISPLAY EXAGGERATION';
export const TRAIL_RESEARCHER_LABEL = 'AUTHORITATIVE SAMPLES · DISPLAY-SPACE HEIGHT · RESEARCHER ONLY';

const ACCEPTED_SCHEMAS = new Set([VERTICAL_DISPLAY_SCHEMA, VERTICAL_DISPLAY_SCHEMA_V1_1]);

/** Deterministic elevation false-color ramp (researcher view — not agent perception). */
export function elevationColor(v: number, lo: number, hi: number, alpha = 0.72): string {
  const span = Math.max(1e-12, hi - lo);
  const t = Math.max(0, Math.min(1, (v - lo) / span));
  const r = Math.floor(20 + 200 * t);
  const g = Math.floor(90 + 100 * (1 - Math.abs(t - 0.45)));
  const b = Math.floor(140 * (1 - t) + 30);
  return `rgba(${r},${g},${b},${alpha})`;
}

/** Sparse delta color: negative = excavated (cool), positive = raised (warm), ~0 transparent. */
export function deltaColor(d: number, maxAbs: number, alpha = 0.78): string {
  const m = Math.max(1e-12, maxAbs);
  const t = Math.max(-1, Math.min(1, d / m));
  if (Math.abs(t) < 0.02) return 'rgba(0,0,0,0)';
  if (t < 0) {
    const u = -t;
    return `rgba(${Math.floor(30 + 40 * u)},${Math.floor(80 + 100 * u)},${Math.floor(160 + 80 * u)},${alpha})`;
  }
  return `rgba(${Math.floor(160 + 70 * t)},${Math.floor(90 + 40 * t)},${Math.floor(40)},${alpha})`;
}

export function readVerticalDisplay(world: any): VerticalDisplayContract | null {
  const vd = world?.vertical_display;
  if (!vd || typeof vd !== 'object') return null;
  if (vd.schema_version && !ACCEPTED_SCHEMAS.has(String(vd.schema_version))) {
    const compat = Array.isArray(vd.schema_compatible_with) ? vd.schema_compatible_with : [];
    if (!compat.some((s: string) => ACCEPTED_SCHEMAS.has(String(s)))) return null;
  }
  return vd as VerticalDisplayContract;
}

export function elevationGridValid(vd: VerticalDisplayContract | null): boolean {
  const g = vd?.cell_centre_elevation;
  if (!g || !Array.isArray(g.data) || !g.data.length) return false;
  if (!Array.isArray(g.data[0]) || !g.data[0].length) return false;
  return Number.isFinite(Number(g.elev_min ?? vd?.elev_min)) && Number.isFinite(Number(g.elev_max ?? vd?.elev_max));
}

export function sparseDeltasValid(vd: VerticalDisplayContract | null): boolean {
  return Array.isArray(vd?.sparse_deltas);
}

export function trailSegmentsValid(vd: VerticalDisplayContract | null): boolean {
  return Array.isArray(vd?.trail_segments);
}

/** Stem / trail display-height in pixels from clearance (display-only). */
export function clearanceStemPx(clearance: number | null | undefined, cell: number, exaggeration: number): number {
  if (clearance == null || !Number.isFinite(clearance) || clearance <= 1e-9) return 0;
  return Math.max(0, clearance) * cell * Math.max(1, exaggeration);
}

/** Filter packed segments for researcher trail mode. */
export function filterTrailSegments(
  segments: VerticalTrailSegment[] | undefined,
  mode: TrailDisplayMode,
  selectedEntityId: string | null | undefined,
  maxSamples: number,
): VerticalTrailSegment[] {
  if (mode === 'OFF' || !Array.isArray(segments)) return [];
  let list = segments;
  if (mode === 'SELECTED') {
    const sid = String(selectedEntityId || '');
    list = sid ? segments.filter((s) => String(s.entity_id) === sid) : [];
  } else if (mode === 'UNSUPPORTED') {
    list = segments.filter((s) => {
      const samples = s.samples || [];
      const last = samples[samples.length - 1];
      return (
        s.active
        || String(last?.support_state || '') === 'UNSUPPORTED'
        || s.start_reason === 'SUPPORT_LOSS'
        || s.start_reason === 'RELEASE'
      );
    });
  }
  return list.map((s) => ({
    ...s,
    samples: Array.isArray(s.samples) ? s.samples.slice(-Math.max(1, maxSamples)) : [],
  }));
}

/** Split polyline where WRAP would span the world or missing-tick discontinuity. */
export function splitTrailOnWrap(
  samples: VerticalTrailSample[],
  worldW: number,
  worldH: number,
): VerticalTrailSample[][] {
  if (!samples.length) return [];
  const out: VerticalTrailSample[][] = [];
  let cur: VerticalTrailSample[] = [samples[0]];
  for (let i = 1; i < samples.length; i++) {
    const a = samples[i - 1];
    const b = samples[i];
    const dx = Math.abs(Number(b.x) - Number(a.x));
    const dy = Math.abs(Number(b.y) - Number(a.y));
    if (
      dx > worldW * 0.5
      || dy > worldH * 0.5
      || (b.discontinuity && b.discontinuity_reason === 'MISSING_TICK_GAP')
    ) {
      out.push(cur);
      cur = [b];
    } else {
      cur.push(b);
    }
  }
  out.push(cur);
  return out;
}
