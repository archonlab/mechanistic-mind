/** Unified EXPERIMENT draft vs active runtime configuration. */

export type VisionDraft = {
  enabled: boolean;
  radius: number;
  visual_surface_discrimination: 'OFF' | 'LOW' | 'RICH';
  optical_mapping: 'INDEPENDENT' | 'CORRELATED' | 'SHUFFLED' | 'UNIFORM';
  spatial_vision: 'LEGACY' | 'ANGULAR' | 'OCCLUSION' | 'TEMPORAL_SPATIAL';
  fov_deg?: number;
};

export type ExperimentSnapshot = {
  seed: number;
  width: number;
  height: number;
  ecology_preset: string;
  cognition_enabled: boolean;
  pe_cold_history_eviction: boolean;
  agent_count: number;
  body_mass: number;
  body_v_max: number;
  public_preset?: string;
  psc_motor_resolution?: string;
  /** PSC auto-enable schedule (ticks). Distinct from initial PSC ON/OFF. null = MANUAL. */
  psc_off_ticks?: number | null;
  mechanisms: Record<string, boolean>;
  vision: VisionDraft;
  terrain_seed?: number | null;
  target_tick?: number | null;
  ui_hz?: number;
  buffer_capacity?: number;
};

export type ApplyStatus = 'SAVED' | 'UNAPPLIED' | 'APPLYING' | 'FAILED';

export type FieldProvenance =
  | 'MODEL_DEFAULT'
  | 'USER_OVERRIDE'
  | 'CONDITION_OVERRIDE'
  | 'LIVE_INTERVENTION';

export function overlayMechanismEnabled(
  catalog: Array<{ id?: string; enabled?: boolean }>,
  draft: Record<string, boolean>,
): Array<{ id?: string; enabled?: boolean } & Record<string, unknown>> {
  return (catalog || []).map((m) => ({
    ...m,
    enabled: m.id && Object.prototype.hasOwnProperty.call(draft, m.id)
      ? Boolean(draft[m.id])
      : Boolean(m.enabled),
  }));
}

export function mechanismMapFromCatalog(catalog: Array<{ id?: string; enabled?: boolean }>): Record<string, boolean> {
  const out: Record<string, boolean> = {};
  for (const m of catalog || []) {
    if (m && m.id) out[String(m.id)] = Boolean(m.enabled);
  }
  return out;
}

export function snapshotsEqual(a: ExperimentSnapshot | null, b: ExperimentSnapshot | null): boolean {
  if (a === b) return true;
  if (!a || !b) return false;
  return JSON.stringify(canonicalize(a)) === JSON.stringify(canonicalize(b));
}

/** True when editor fields differ from the named preset's last-loaded canonical defaults. */
export function draftPresetModified(
  draft: ExperimentSnapshot | null,
  baseline: ExperimentSnapshot | null,
): boolean {
  if (!draft?.public_preset || !baseline) return false;
  const a = canonicalize({ ...draft, public_preset: draft.public_preset });
  const b = canonicalize({ ...baseline, public_preset: draft.public_preset });
  return JSON.stringify(a) !== JSON.stringify(b);
}

function canonicalize(s: ExperimentSnapshot): ExperimentSnapshot {
  const mechKeys = Object.keys(s.mechanisms || {}).sort();
  const mechanisms: Record<string, boolean> = {};
  for (const k of mechKeys) mechanisms[k] = Boolean(s.mechanisms[k]);
  return {
    seed: Number(s.seed),
    width: Number(s.width),
    height: Number(s.height),
    ecology_preset: String(s.ecology_preset || ''),
    cognition_enabled: Boolean(s.cognition_enabled),
    pe_cold_history_eviction: Boolean(s.pe_cold_history_eviction),
    agent_count: Number(s.agent_count),
    body_mass: Number(s.body_mass),
    body_v_max: Number(s.body_v_max),
    public_preset: s.public_preset || undefined,
    psc_motor_resolution: s.psc_motor_resolution || undefined,
    psc_off_ticks: s.psc_off_ticks === undefined ? undefined : (s.psc_off_ticks == null ? null : Number(s.psc_off_ticks)),
    mechanisms,
    vision: {
      enabled: Boolean(s.vision?.enabled),
      radius: Number(s.vision?.radius || 1),
      visual_surface_discrimination: s.vision?.visual_surface_discrimination || 'OFF',
      optical_mapping: s.vision?.optical_mapping || 'INDEPENDENT',
      spatial_vision: s.vision?.spatial_vision || 'LEGACY',
      fov_deg: s.vision?.fov_deg,
    },
    terrain_seed: s.terrain_seed ?? null,
    target_tick: s.target_tick ?? null,
    ui_hz: s.ui_hz,
    buffer_capacity: s.buffer_capacity,
  };
}

export function applyStatusFor(draft: ExperimentSnapshot | null, active: ExperimentSnapshot | null, applying: boolean, failed: boolean): ApplyStatus {
  if (applying) return 'APPLYING';
  if (failed) return 'FAILED';
  if (!active) return snapshotsEqual(draft, active) ? 'SAVED' : 'UNAPPLIED';
  return snapshotsEqual(draft, active) ? 'SAVED' : 'UNAPPLIED';
}

export function mergeCanonicalIntoSnapshot(
  current: ExperimentSnapshot,
  canonical: Record<string, any>,
): ExperimentSnapshot {
  const vis = canonical.vision || {};
  const body = canonical.agent_body || {};
  const world = canonical.world || {};
  const sched = canonical.psc_schedule && typeof canonical.psc_schedule === 'object'
    ? canonical.psc_schedule
    : {};
  const offTicks = canonical.psc_off_ticks !== undefined
    ? canonical.psc_off_ticks
    : (sched.psc_off_ticks !== undefined ? sched.psc_off_ticks : current.psc_off_ticks);
  return {
    ...current,
    seed: canonical.seed != null ? Number(canonical.seed) : current.seed,
    width: world.width != null ? Number(world.width) : current.width,
    height: world.height != null ? Number(world.height) : current.height,
    ecology_preset: String(canonical.ecology_preset || current.ecology_preset),
    cognition_enabled: canonical.cognition_enabled != null ? Boolean(canonical.cognition_enabled) : current.cognition_enabled,
    pe_cold_history_eviction: canonical.pe_cold_history_eviction != null
      ? Boolean(canonical.pe_cold_history_eviction)
      : current.pe_cold_history_eviction,
    agent_count: canonical.agent_count != null ? Number(canonical.agent_count) : current.agent_count,
    body_mass: body.mass != null ? Number(body.mass) : current.body_mass,
    body_v_max: body.v_max != null ? Number(body.v_max) : current.body_v_max,
    public_preset: canonical.public_preset || current.public_preset,
    psc_motor_resolution: canonical.psc_motor_resolution || current.psc_motor_resolution,
    psc_off_ticks: offTicks === undefined ? current.psc_off_ticks : (offTicks == null ? null : Number(offTicks)),
    mechanisms: { ...current.mechanisms, ...(canonical.mechanisms || {}) },
    vision: {
      enabled: vis.enabled != null ? Boolean(vis.enabled) : current.vision.enabled,
      radius: vis.radius != null ? Number(vis.radius) : current.vision.radius,
      visual_surface_discrimination: vis.visual_surface_discrimination || current.vision.visual_surface_discrimination,
      optical_mapping: vis.optical_mapping || current.vision.optical_mapping,
      spatial_vision: vis.spatial_vision || current.vision.spatial_vision,
      fov_deg: vis.fov_deg != null ? Number(vis.fov_deg) : current.vision.fov_deg,
    },
  };
}

export function buildCanonicalApplyPayload(snap: ExperimentSnapshot): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    seed: snap.seed,
    cognition_enabled: snap.cognition_enabled,
    pe_cold_history_eviction: snap.pe_cold_history_eviction,
    ecology_preset: snap.ecology_preset,
    world: {
      width: snap.width,
      height: snap.height,
      boundary_mode: 'WRAP_PERIODIC',
    },
    agent_body: { mass: snap.body_mass, v_max: snap.body_v_max },
    agent_count: snap.agent_count,
    mechanisms: { ...snap.mechanisms },
    vision: { ...snap.vision },
  };
  if (snap.public_preset) payload.public_preset = snap.public_preset;
  if (snap.psc_motor_resolution) payload.psc_motor_resolution = snap.psc_motor_resolution;
  if (snap.psc_off_ticks !== undefined) {
    payload.psc_off_ticks = snap.psc_off_ticks;
    payload.psc_schedule = { psc_off_ticks: snap.psc_off_ticks };
  }
  if (snap.target_tick != null && Number.isFinite(snap.target_tick)) payload.target_tick = snap.target_tick;
  if (snap.ui_hz != null && Number.isFinite(snap.ui_hz)) payload.ui_hz = snap.ui_hz;
  if (snap.buffer_capacity != null && Number.isFinite(snap.buffer_capacity)) {
    payload.buffer_capacity = Math.max(8, snap.buffer_capacity);
  }
  if (snap.terrain_seed != null && Number.isFinite(snap.terrain_seed)) {
    payload.terrain_seed = snap.terrain_seed;
    (payload.world as Record<string, unknown>).terrain_seed = snap.terrain_seed;
  }
  return payload;
}

export function snapshotFromEditors(fields: {
  seed: string;
  width: string;
  height: string;
  ecologyPreset: string;
  cognitionEnabled: boolean;
  peColdHistoryEviction: boolean;
  twoAgentExperimental: boolean;
  bodyMass: string;
  bodyVMax: string;
  publicPreset?: string;
  pscMotorResolution?: string;
  pscOffTicks?: number | null;
  mechanisms: Record<string, boolean>;
  vision: VisionDraft;
  terrainSeedOverride?: string;
  targetTick?: string;
  uiHz?: string;
  bufferCapacity?: string;
}): ExperimentSnapshot {
  const terrain = fields.terrainSeedOverride?.trim();
  const target = fields.targetTick?.trim();
  return {
    seed: Number(fields.seed),
    width: Number(fields.width),
    height: Number(fields.height),
    ecology_preset: fields.ecologyPreset,
    cognition_enabled: fields.cognitionEnabled,
    pe_cold_history_eviction: fields.peColdHistoryEviction,
    agent_count: fields.twoAgentExperimental ? 2 : 1,
    body_mass: Number(fields.bodyMass),
    body_v_max: Number(fields.bodyVMax),
    public_preset: fields.publicPreset,
    psc_motor_resolution: fields.pscMotorResolution,
    psc_off_ticks: fields.pscOffTicks === undefined ? undefined : fields.pscOffTicks,
    mechanisms: { ...fields.mechanisms },
    vision: { ...fields.vision },
    terrain_seed: terrain && Number.isFinite(+terrain) ? +terrain : null,
    target_tick: target && Number.isFinite(+target) ? +target : null,
    ui_hz: fields.uiHz != null && Number.isFinite(+fields.uiHz) ? +fields.uiHz : undefined,
    buffer_capacity: fields.bufferCapacity != null && Number.isFinite(+fields.bufferCapacity)
      ? +fields.bufferCapacity
      : undefined,
  };
}

/** Apply snapshot values onto the Observer editor field bag. */
export function uiFieldsFromSnapshot(snap: ExperimentSnapshot): {
  seed: string;
  width: string;
  height: string;
  ecologyPreset: string;
  cognitionEnabled: boolean;
  peColdHistoryEviction: boolean;
  twoAgentExperimental: boolean;
  bodyMass: string;
  bodyVMax: string;
  publicPreset?: string;
  pscMotorResolution?: string;
  pscOffTicks?: number | null;
  mechanisms: Record<string, boolean>;
  vision: VisionDraft;
  terrainSeedOverride: string;
  targetTick: string;
  uiHz: string;
  bufferCapacity: string;
} {
  return {
    seed: String(snap.seed),
    width: String(snap.width),
    height: String(snap.height),
    ecologyPreset: snap.ecology_preset,
    cognitionEnabled: snap.cognition_enabled,
    peColdHistoryEviction: snap.pe_cold_history_eviction,
    twoAgentExperimental: Number(snap.agent_count) >= 2,
    bodyMass: String(snap.body_mass),
    bodyVMax: String(snap.body_v_max),
    publicPreset: snap.public_preset,
    pscMotorResolution: snap.psc_motor_resolution,
    pscOffTicks: snap.psc_off_ticks,
    mechanisms: { ...snap.mechanisms },
    vision: { ...snap.vision },
    terrainSeedOverride: snap.terrain_seed != null ? String(snap.terrain_seed) : '',
    targetTick: snap.target_tick != null ? String(snap.target_tick) : '',
    uiHz: snap.ui_hz != null ? String(snap.ui_hz) : '10',
    bufferCapacity: snap.buffer_capacity != null ? String(snap.buffer_capacity) : '512',
  };
}

export function visionDraftFromPhysical(
  physical: Record<string, any> | null | undefined,
  visionEnabled: boolean,
  fallbackRadius = 3,
): VisionDraft {
  const nfe = physical?.near_field_exteroception || {};
  const radius = Math.max(1, Math.min(3, Number(
    nfe.vision_radius ?? nfe.radius ?? fallbackRadius,
  )));
  const surf = String(nfe.visual_surface_discrimination || 'OFF').toUpperCase();
  const opt = String(nfe.optical_mapping || 'INDEPENDENT').toUpperCase();
  const spat = String(nfe.spatial_vision || 'LEGACY').toUpperCase();
  return {
    enabled: Boolean(visionEnabled),
    radius,
    visual_surface_discrimination: (surf === 'LOW' || surf === 'RICH' ? surf : 'OFF'),
    optical_mapping: (
      opt === 'CORRELATED' || opt === 'SHUFFLED' || opt === 'UNIFORM' ? opt : 'INDEPENDENT'
    ),
    spatial_vision: (
      spat === 'ANGULAR' || spat === 'OCCLUSION' || spat === 'TEMPORAL_SPATIAL' ? spat : 'LEGACY'
    ),
    fov_deg: nfe.fov_deg != null ? Number(nfe.fov_deg) : undefined,
  };
}

export function snapshotFromCanonical(canonical: Record<string, any> | null | undefined): ExperimentSnapshot | null {
  if (!canonical || typeof canonical !== 'object') return null;
  if (canonical.ecology_preset == null && canonical.mechanisms == null && canonical.vision == null) {
    return null;
  }
  const vis = canonical.vision || {};
  const body = canonical.agent_body || {};
  const world = canonical.world || {};
  const mechs = canonical.mechanisms && typeof canonical.mechanisms === 'object'
    ? Object.fromEntries(Object.entries(canonical.mechanisms).map(([k, v]) => [k, Boolean(v)]))
    : {};
  const surf = String(vis.visual_surface_discrimination || 'OFF').toUpperCase();
  const opt = String(vis.optical_mapping || 'INDEPENDENT').toUpperCase();
  const spat = String(vis.spatial_vision || 'LEGACY').toUpperCase();
  const sched = canonical.psc_schedule && typeof canonical.psc_schedule === 'object'
    ? canonical.psc_schedule
    : {};
  const rawOff = canonical.psc_off_ticks !== undefined
    ? canonical.psc_off_ticks
    : sched.psc_off_ticks;
  return {
    seed: Number(canonical.seed ?? 17),
    width: Number(world.width ?? 32),
    height: Number(world.height ?? 32),
    ecology_preset: String(canonical.ecology_preset || 'BASELINE_CLIMATE_DEFAULT'),
    cognition_enabled: canonical.cognition_enabled != null ? Boolean(canonical.cognition_enabled) : true,
    pe_cold_history_eviction: canonical.pe_cold_history_eviction != null
      ? Boolean(canonical.pe_cold_history_eviction)
      : true,
    agent_count: Number(canonical.agent_count || 1),
    body_mass: Number(body.mass ?? 2),
    body_v_max: Number(body.v_max ?? 0.3),
    public_preset: canonical.public_preset || undefined,
    psc_motor_resolution: String(canonical.psc_motor_resolution || 'LOCO_FACTORIZED'),
    psc_off_ticks: rawOff === undefined ? undefined : (rawOff == null ? null : Number(rawOff)),
    mechanisms: mechs,
    vision: {
      enabled: vis.enabled != null ? Boolean(vis.enabled) : true,
      radius: Number(vis.radius ?? vis.vision_radius ?? 3),
      visual_surface_discrimination: (surf === 'LOW' || surf === 'RICH' ? surf : 'OFF'),
      optical_mapping: (
        opt === 'CORRELATED' || opt === 'SHUFFLED' || opt === 'UNIFORM' ? opt : 'INDEPENDENT'
      ),
      spatial_vision: (
        spat === 'ANGULAR' || spat === 'OCCLUSION' || spat === 'TEMPORAL_SPATIAL' ? spat : 'LEGACY'
      ),
      fov_deg: vis.fov_deg != null ? Number(vis.fov_deg) : undefined,
    },
    terrain_seed: canonical.terrain_seed != null
      ? Number(canonical.terrain_seed)
      : (world.terrain_seed != null ? Number(world.terrain_seed) : null),
    target_tick: canonical.target_tick != null ? Number(canonical.target_tick) : null,
    ui_hz: canonical.ui_hz != null ? Number(canonical.ui_hz) : undefined,
    buffer_capacity: canonical.buffer_capacity != null ? Number(canonical.buffer_capacity) : undefined,
  };
}

export function canonicalSourceFromApplyResponse(f: any): Record<string, any> | null {
  const direct = f?.active_experiment || f?.canonical_active_experiment
    || f?.experiment?.active_experiment;
  if (direct && typeof direct === 'object') return direct;
  const receiptRt = f?.applied_configuration?.runtime;
  if (receiptRt && receiptRt.ecology_preset && receiptRt.psc_motor_resolution) return receiptRt;
  return null;
}

export function snapshotFromRuntimeFrame(
  f: any,
  mechanisms: Array<{ id?: string; enabled?: boolean }>,
  extras?: { vision?: VisionDraft; pscMotorResolution?: string; pscOffTicks?: number | null },
): ExperimentSnapshot {
  const bodyCfg = f?.experiment?.agent_body || {};
  const obs = f?.experiment?.observer || {};
  const eco = String(
    f?.experiment?.ecology_preset
    || f?.experiment?.observer_ground_truth?.ecology_preset
    || f?.header?.ecology_preset
    || 'BASELINE_CLIMATE_DEFAULT',
  );
  const visOn = Boolean((mechanisms || []).find((m) => m.id === 'physical_near_field_vision')?.enabled);
  const vision = extras?.vision || visionDraftFromPhysical(f?.physical, visOn);
  const psc = extras?.pscMotorResolution
    || f?.experiment?.runtime?.psc_motor_resolution
    || f?.header?.psc_motor_resolution
    || 'LOCO_FACTORIZED';
  const rawOff = extras?.pscOffTicks !== undefined
    ? extras.pscOffTicks
    : (
      f?.experiment?.runtime?.psc_off_ticks
      ?? f?.experiment?.psc_schedule?.psc_off_ticks
      ?? f?.header?.psc_off_ticks
      ?? f?.active_experiment?.psc_off_ticks
    );
  return {
    seed: Number(f?.header?.seed ?? 17),
    width: Number(f?.world?.width ?? 32),
    height: Number(f?.world?.height ?? 32),
    ecology_preset: eco,
    cognition_enabled: Boolean(f?.experiment?.runtime?.cognition_enabled ?? f?.header?.cognition_enabled ?? true),
    pe_cold_history_eviction: Boolean(
      f?.experiment?.pe_cold_history_eviction?.applied
      ?? f?.experiment?.runtime?.pe_cold_history_eviction
      ?? f?.header?.pe_cold_history_eviction
      ?? true,
    ),
    agent_count: Number(f?.experiment?.runtime?.agent_count || 1),
    body_mass: Number(bodyCfg.mass ?? 2),
    body_v_max: Number(bodyCfg.v_max ?? 0.3),
    public_preset: f?.header?.public_preset || f?.experiment?.runtime?.public_preset,
    psc_motor_resolution: String(psc),
    psc_off_ticks: rawOff === undefined ? undefined : (rawOff == null ? null : Number(rawOff)),
    mechanisms: mechanismMapFromCatalog(mechanisms),
    vision,
    target_tick: f?.header?.target_tick != null ? Number(f.header.target_tick) : null,
    ui_hz: obs.ui_hz != null ? Number(obs.ui_hz) : undefined,
    buffer_capacity: obs.buffer_capacity != null ? Number(obs.buffer_capacity) : undefined,
    terrain_seed: f?.experiment?.observer_ground_truth?.terrain?.seed != null
      ? Number(f.experiment.observer_ground_truth.terrain.seed)
      : null,
  };
}

export function applyStatusLabel(status: ApplyStatus): string {
  if (status === 'SAVED') return 'SAVED / ACTIVE';
  if (status === 'UNAPPLIED') return 'UNAPPLIED CHANGES';
  if (status === 'APPLYING') return 'APPLYING';
  return 'APPLY FAILED';
}

/** Review recipe sections from a draft snapshot (UI presentation only). */
export function buildReviewRecipe(snap: ExperimentSnapshot, extras?: {
  baseline?: ExperimentSnapshot | null;
  liveInterventionNote?: string;
}): Record<string, unknown> {
  const mechs = snap.mechanisms || {};
  const modified = draftPresetModified(snap, extras?.baseline || null);
  return {
    WORLD: {
      seed: snap.seed,
      size: `${snap.width}×${snap.height}`,
      topology_boundary: 'WRAP_PERIODIC',
      target_tick: snap.target_tick ?? null,
      observer_hz: snap.ui_hz ?? null,
      buffer_capacity: snap.buffer_capacity ?? null,
    },
    ECOLOGY: {
      selected_preset: snap.ecology_preset,
      explicit_overrides: extras?.baseline && snap.ecology_preset !== extras.baseline.ecology_preset
        ? [snap.ecology_preset]
        : [],
    },
    MODEL: {
      public_model: snap.public_preset || null,
      agent_count: snap.agent_count,
      canonical_profile_status: modified ? 'OVERRIDDEN' : 'CANONICAL',
    },
    BODY: {
      mass: snap.body_mass,
      v_max: snap.body_v_max,
    },
    PSC: {
      initial_state: mechs.prospective_scenario_competition ? 'ON' : 'OFF',
      auto_enable_tick: snap.psc_off_ticks == null ? 'MANUAL' : snap.psc_off_ticks,
      motor_resolution: snap.psc_motor_resolution || 'LOCO_FACTORIZED',
    },
    SIGNALING_AND_MECHANISMS: {
      experimental_physical_signal: Boolean(mechs.experimental_physical_signal),
      physical_oscillatory_signaling: Boolean(mechs.oscillatory_signaling),
      cognition_enabled: snap.cognition_enabled,
      pe_cold_history_eviction: snap.pe_cold_history_eviction,
    },
    VISION: {
      enabled: snap.vision.enabled,
      range: snap.vision.radius,
      surface_discrimination: snap.vision.visual_surface_discrimination,
      optical_mapping: snap.vision.optical_mapping,
      spatial_mode: snap.vision.spatial_vision,
    },
    APPLY_CONSEQUENCE: 'starts a new runtime at tick 0',
    Canonical_model_defaults: extras?.baseline ? 'see baseline snapshot' : 'none loaded',
    Explicit_experimental_overrides: modified,
    Live_interventions_not_included: extras?.liveInterventionNote || 'Live PSC schedule interventions are not part of next Apply unless mirrored in draft',
  };
}
