/**
 * Bounded incremental aggregates for Observer analysis.
 * Sublinear / capped memory — never retain every raw tick forever.
 * Scientific counters must be based on unique simulation ticks / event IDs,
 * not Observer sample multiplicity.
 */
import type { AgentId, KeyFrameRef } from './types.ts';
import { rememberKey, timelineAgentKey } from './dedup.ts';

export const BOUNDS = {
  important_events: 120,
  keyframes: 50,
  contact_episodes: 40,
  action_transition_keys: 64,
  streak_samples: 32,
  quiet_episode_merge_gap: 25,
  max_overview_cards: 80,
  max_causal_chains: 40,
};

export type AgentAgg = {
  agent_id: AgentId;
  body_id: string;
  seed: number | null;
  ticks: number;
  action_counts: Record<string, number>;
  action_transitions: Record<string, number>;
  last_action: string | null;
  wait_streak: number;
  move_streak: number;
  longest_wait_streak: number;
  longest_move_streak: number;
  /** Simulation tick where the current WAIT streak began (streak length 1). */
  wait_streak_start_tick: number | null;
  /** Simulation tick where the current MOVE streak began (streak length 1). */
  move_streak_start_tick: number | null;
  /** True after SUSTAINED WAIT threshold event emitted for the current streak. */
  sustained_wait_threshold_emitted: boolean;
  /** True after SUSTAINED MOVE threshold event emitted for the current streak. */
  sustained_move_threshold_emitted: boolean;
  distance: number;
  /** WRAP-aware Euclidean path length (unique ticks only). */
  path_length_euclidean: number;
  /** WRAP-aware Manhattan path (unique ticks); legacy `distance` may still mix runtime. */
  path_length_manhattan_wrap: number;
  unwrapped_dx: number;
  unwrapped_dy: number;
  unique_cells: Set<string>;
  last_xy: { x: number; y: number } | null;
  start_xy: { x: number; y: number } | null;
  /** Display-only pose from LIVE frame — must NEVER poison path baseline. */
  live_pose_xy: { x: number; y: number } | null;
  /** Unwrapped trajectory cursor (starts at first sample). */
  unwrapped_xy: { x: number; y: number } | null;
  unwrapped_min: { x: number; y: number } | null;
  unwrapped_max: { x: number; y: number } | null;
  max_excursion_from_start: number;
  boundary_crossings_x: number;
  boundary_crossings_y: number;
  cell_boundary_crossings: number;
  unique_position_ticks: number;
  duplicate_observer_samples_ignored: number;
  trajectory_gaps_skipped: number;
  path_during_requested_WAIT: number;
  path_during_requested_MOVE: number;
  unwrapped_dx_during_WAIT: number;
  unwrapped_dy_during_WAIT: number;
  unwrapped_dx_during_MOVE: number;
  unwrapped_dy_during_MOVE: number;
  neighborhood_replacements: number;
  last_center_cell: string | null;
  realized_displacement_sum: number;
  max_speed: number;
  speed_sum: number;
  speed_n: number;
  theta_start: number | null;
  theta_last: number | null;
  rotation_accum: number;
  selection_sources: Record<string, number>;
  /** SCENARIO_SELECTED events (prospective / prior non-WAIT instrumentation). */
  scenario_selected: number;
  scenario_selected_wait: number;
  scenario_selected_move: number;
  /** WAIT with selection_source in PROSPECTIVE_* (from SCENARIO_SELECTED). */
  cognitive_wait_selections: number;
  /** WAIT with ENDOGENOUS_VARIATION / COGNITION_DISABLED / missing scenario event. */
  fallback_wait_selections: number;
  discrete_action_selected: number;
  // resources from telemetry (selected agent series — may be partial for multi)
  resA: { start: number | null; end: number | null; min: number | null; max: number | null };
  resB: { start: number | null; end: number | null; min: number | null; max: number | null };
  work: { start: number | null; end: number | null; min: number | null; max: number | null };
  // signals
  emit_A: number;
  emit_B: number;
  recv_A: number;
  recv_B: number;
  emit_contact: number;
  emit_motion: number;
  recv_mixed: number;
  recv_not_unique: number;
  recv_unknown: number;
  cross_agent_contrib: number;
  collision_ticks: number;
  // cognition snapshots
  prediction_count: number | null;
  prediction_error: number | null;
  prospective: number | null;
  novel: number | null;
  // body/work events
  deform_events: number;
  work_limited: number;
  limiting_events: number;
  conversion_events: number;
  first_move_tick: number | null;
  first_wait_after_move_tick: number | null;
  /** Last simulation tick for which action selection was counted (dedupe). */
  last_action_tick: number | null;
  /** Last simulation tick for which XY/distance was applied (dedupe). */
  last_xy_tick: number | null;
};

export type AnalysisState = {
  generation: number | null;
  start_tick: number | null;
  end_tick: number | null;
  runtime: string;
  seed: number | null;
  map_w: number | null;
  map_h: number | null;
  boundary: string;
  agent_count: number;
  cognition_enabled: boolean | null;
  experimental_overrides: Record<string, any>;
  active_mechanisms: string[];
  status: string;
  agents: Record<string, AgentAgg>;
  firsts: Record<string, { tick: number; meta?: any }>;
  extrema: Record<string, { tick: number; value: number; meta?: any }>;
  /** Unique simulation ticks with contact present (scientific). */
  contact_ticks: number;
  contact_tick_set: Set<number>;
  /** Unique ticks for which contact FSM already advanced. */
  contact_fsm_ticks: Set<string>;
  contact_active: boolean;
  contact_episode_start: number | null;
  contact_episodes: Array<{ start: number; end: number; ticks: number }>;
  first_contact_tick: number | null;
  important: any[];
  keyframes: KeyFrameRef[];
  seen_event_keys: Set<string>;
  /** Timeline agent-state keys already applied scientifically (tick|agent). */
  seen_timeline_agent_keys: Set<string>;
  /** Unique simulation ticks represented in timeline ingestion. */
  unique_simulation_ticks: Set<number>;
  last_processed_timeline_tick: number;
  /** Last live-summary frame tick applied (rotation / selection_source increments). */
  last_live_summary_tick: number | null;
  telemetry_samples: number;
  event_samples: number;
  /** Raw Observer timeline sample count (diagnostic; not simulation duration). */
  timeline_samples: number;
  causal_pairs: Array<{ tick: number; parent: string; child: string; meta?: any }>;
  /** Beta 2 WORLD_INTERVENTION provenance for configuration history. */
  world_interventions: any[];
  initial_world_fingerprint: string | null;
};

export function emptyResource() {
  return { start: null as number | null, end: null as number | null, min: null as number | null, max: null as number | null };
}

export function makeAgentAgg(agent_id: string, body_id: string, seed: number | null = null): AgentAgg {
  return {
    agent_id,
    body_id,
    seed,
    ticks: 0,
    action_counts: {},
    action_transitions: {},
    last_action: null,
    wait_streak: 0,
    move_streak: 0,
    longest_wait_streak: 0,
    longest_move_streak: 0,
    wait_streak_start_tick: null,
    move_streak_start_tick: null,
    sustained_wait_threshold_emitted: false,
    sustained_move_threshold_emitted: false,
    distance: 0,
    path_length_euclidean: 0,
    path_length_manhattan_wrap: 0,
    unwrapped_dx: 0,
    unwrapped_dy: 0,
    unique_cells: new Set(),
    last_xy: null,
    start_xy: null,
    live_pose_xy: null,
    unwrapped_xy: null,
    unwrapped_min: null,
    unwrapped_max: null,
    max_excursion_from_start: 0,
    boundary_crossings_x: 0,
    boundary_crossings_y: 0,
    cell_boundary_crossings: 0,
    unique_position_ticks: 0,
    duplicate_observer_samples_ignored: 0,
    trajectory_gaps_skipped: 0,
    path_during_requested_WAIT: 0,
    path_during_requested_MOVE: 0,
    unwrapped_dx_during_WAIT: 0,
    unwrapped_dy_during_WAIT: 0,
    unwrapped_dx_during_MOVE: 0,
    unwrapped_dy_during_MOVE: 0,
    neighborhood_replacements: 0,
    last_center_cell: null,
    realized_displacement_sum: 0,
    max_speed: 0,
    speed_sum: 0,
    speed_n: 0,
    theta_start: null,
    theta_last: null,
    rotation_accum: 0,
    selection_sources: {},
    scenario_selected: 0,
    scenario_selected_wait: 0,
    scenario_selected_move: 0,
    cognitive_wait_selections: 0,
    fallback_wait_selections: 0,
    discrete_action_selected: 0,
    resA: emptyResource(),
    resB: emptyResource(),
    work: emptyResource(),
    emit_A: 0,
    emit_B: 0,
    recv_A: 0,
    recv_B: 0,
    emit_contact: 0,
    emit_motion: 0,
    recv_mixed: 0,
    recv_not_unique: 0,
    recv_unknown: 0,
    cross_agent_contrib: 0,
    collision_ticks: 0,
    prediction_count: null,
    prediction_error: null,
    prospective: null,
    novel: null,
    deform_events: 0,
    work_limited: 0,
    limiting_events: 0,
    conversion_events: 0,
    first_move_tick: null,
    first_wait_after_move_tick: null,
    last_action_tick: null,
    last_xy_tick: null,
  };
}

export function createAnalysisState(): AnalysisState {
  return {
    generation: null,
    start_tick: null,
    end_tick: null,
    runtime: 'UNKNOWN',
    seed: null,
    map_w: null,
    map_h: null,
    boundary: 'WRAP_PERIODIC',
    agent_count: 1,
    cognition_enabled: null,
    experimental_overrides: {},
    active_mechanisms: [],
    status: 'UNKNOWN',
    agents: {},
    firsts: {},
    extrema: {},
    contact_ticks: 0,
    contact_tick_set: new Set(),
    contact_fsm_ticks: new Set(),
    contact_active: false,
    contact_episode_start: null,
    contact_episodes: [],
    first_contact_tick: null,
    important: [],
    keyframes: [],
    seen_event_keys: new Set(),
    seen_timeline_agent_keys: new Set(),
    unique_simulation_ticks: new Set(),
    last_processed_timeline_tick: -1,
    last_live_summary_tick: null,
    telemetry_samples: 0,
    event_samples: 0,
    timeline_samples: 0,
    causal_pairs: [],
    world_interventions: [],
    initial_world_fingerprint: null,
  };
}

export function ensureAgent(state: AnalysisState, agent_id: string, body_id?: string, seed?: number | null) {
  const aid = normalizeAgentId(agent_id);
  const bid = body_id || canonicalBody(aid);
  if (!state.agents[aid]) {
    state.agents[aid] = makeAgentAgg(aid, bid, seed ?? null);
  } else {
    if (body_id) state.agents[aid].body_id = body_id;
    else if (!state.agents[aid].body_id || state.agents[aid].body_id === 'body-0') {
      state.agents[aid].body_id = bid;
    }
    if (seed != null) state.agents[aid].seed = seed;
  }
  return state.agents[aid];
}

/** Normalize legacy experimenter-body-* onto canonical undercover (new runs). */
export function normalizeAgentId(agentId: string) {
  const id = String(agentId || '');
  if (id === 'undercover' || id.startsWith('experimenter')) return 'undercover';
  return id;
}

export function canonicalBody(agentId: string) {
  const id = normalizeAgentId(agentId);
  const m = /^agent_(\d+)$/.exec(id);
  if (m) return `body-${m[1]}`;
  if (id === 'undercover') {
    const emb = /body-(\d+)/.exec(String(agentId || ''));
    if (emb) return `body-${emb[1]}`;
    return 'body-2';
  }
  if (/^body-\d+$/.test(id)) return id;
  return 'body-0';
}

export function recordFirst(state: AnalysisState, key: string, tick: number, meta?: any) {
  if (state.firsts[key] != null) return false;
  state.firsts[key] = { tick, meta };
  return true;
}

export function recordExtrema(state: AnalysisState, key: string, tick: number, value: number, prefer: 'max' | 'min', meta?: any) {
  const cur = state.extrema[key];
  if (!cur) {
    state.extrema[key] = { tick, value, meta };
    return true;
  }
  if (prefer === 'max' && value > cur.value) {
    state.extrema[key] = { tick, value, meta };
    return true;
  }
  if (prefer === 'min' && value < cur.value) {
    state.extrema[key] = { tick, value, meta };
    return true;
  }
  return false;
}

export function pushBounded<T>(arr: T[], item: T, max: number) {
  arr.push(item);
  if (arr.length > max) arr.splice(0, arr.length - max);
}

export function updateResourceSeries(
  box: { start: number | null; end: number | null; min: number | null; max: number | null },
  value: number | null | undefined,
) {
  if (value == null || !Number.isFinite(Number(value))) return;
  const v = Number(value);
  if (box.start == null) box.start = v;
  box.end = v;
  box.min = box.min == null ? v : Math.min(box.min, v);
  box.max = box.max == null ? v : Math.max(box.max, v);
}

/** Tick-level sustained-action thresholds (consecutive simulation ticks). */
export const SUSTAINED_WAIT_THRESHOLD = 20;
export const SUSTAINED_MOVE_THRESHOLD = 10;

/**
 * Count one canonical action per (agent, simulation tick) — tick-level occupancy.
 * Returns false if this tick was already counted (repeated Observer sample).
 * Streaks require consecutive simulation ticks; gaps reset streak counters.
 */
export function ingestAction(agg: AgentAgg, action: string | null | undefined, tick: number): boolean {
  if (!action) return false;
  if (agg.last_action_tick != null && tick === agg.last_action_tick) return false;
  // Out-of-order duplicate of an older tick — ignore for streaks/counts.
  if (agg.last_action_tick != null && tick < agg.last_action_tick) return false;
  // Evidence gap: streak is consecutive-tick occupancy, not a count of any WAIT rows.
  if (agg.last_action_tick != null && tick > agg.last_action_tick + 1) {
    resetStreakState(agg);
  }
  const prevAction = agg.last_action;
  agg.last_action_tick = tick;
  agg.ticks += 1;
  agg.action_counts[action] = (agg.action_counts[action] || 0) + 1;
  if (prevAction && prevAction !== action) {
    const key = `${prevAction}→${action}`;
    const keys = Object.keys(agg.action_transitions);
    if (keys.length < BOUNDS.action_transition_keys || key in agg.action_transitions) {
      agg.action_transitions[key] = (agg.action_transitions[key] || 0) + 1;
    }
  }
  const isWait = action === 'WAIT';
  const isMove = String(action).startsWith('MOVE');
  if (isWait) {
    if (agg.wait_streak === 0) {
      agg.wait_streak_start_tick = tick;
      agg.sustained_wait_threshold_emitted = false;
    }
    agg.wait_streak += 1;
    agg.move_streak = 0;
    agg.move_streak_start_tick = null;
    agg.sustained_move_threshold_emitted = false;
    agg.longest_wait_streak = Math.max(agg.longest_wait_streak, agg.wait_streak);
    if (agg.first_move_tick != null && agg.first_wait_after_move_tick == null && agg.wait_streak >= 5) {
      agg.first_wait_after_move_tick = tick - agg.wait_streak + 1;
    }
  } else if (isMove) {
    if (agg.move_streak === 0) {
      agg.move_streak_start_tick = tick;
      agg.sustained_move_threshold_emitted = false;
    }
    agg.move_streak += 1;
    agg.wait_streak = 0;
    agg.wait_streak_start_tick = null;
    agg.sustained_wait_threshold_emitted = false;
    agg.longest_move_streak = Math.max(agg.longest_move_streak, agg.move_streak);
    if (agg.first_move_tick == null) agg.first_move_tick = tick;
  } else {
    resetStreakState(agg);
  }
  agg.last_action = action;
  return true;
}

function resetStreakState(agg: AgentAgg) {
  agg.wait_streak = 0;
  agg.move_streak = 0;
  agg.wait_streak_start_tick = null;
  agg.move_streak_start_tick = null;
  agg.sustained_wait_threshold_emitted = false;
  agg.sustained_move_threshold_emitted = false;
}

/**
 * Periodic minimum-image displacement on one axis (WRAP_PERIODIC).
 * 31.9 → 0.1 on L=32 → +0.2; 0.1 → 31.9 → −0.2.
 */
export function wrapDelta(a: number, b: number, size: number): number {
  let d = b - a;
  const half = size / 2;
  if (d > half) d -= size;
  else if (d < -half) d += size;
  return d;
}

function centerCellKey(x: number, y: number, w?: number | null, h?: number | null): string {
  let cx = Math.floor(x);
  let cy = Math.floor(y);
  if (w != null && w > 0) cx = ((cx % w) + w) % w;
  if (h != null && h > 0) cy = ((cy % h) + h) % h;
  return `${cx},${cy}`;
}

/**
 * Apply body position once per simulation tick.
 * Repeated samples of the same tick must not inflate distance.
 * Evidence gaps (tick jumps > 1) rebase without inventing multi-wrap path.
 * When worldW/worldH are provided, accumulate WRAP-aware Euclidean / Manhattan
 * and unwrapped displacement. Raw non-wrap Manhattan retained only as
 * `distance` legacy label when dims missing.
 */
export function ingestXy(
  agg: AgentAgg,
  x: number,
  y: number,
  speed?: number,
  tick?: number,
  worldW?: number,
  worldH?: number,
): boolean {
  if (!Number.isFinite(x) || !Number.isFinite(y)) return false;
  const w = worldW != null && Number.isFinite(worldW) && worldW > 0 ? worldW : null;
  const h = worldH != null && Number.isFinite(worldH) && worldH > 0 ? worldH : null;
  if (tick != null && Number.isFinite(tick)) {
    if (agg.last_xy_tick != null && tick === agg.last_xy_tick) {
      // Same tick re-sample: keep latest coords without adding distance.
      agg.duplicate_observer_samples_ignored += 1;
      agg.last_xy = { x, y };
      return false;
    }
    if (agg.last_xy_tick != null && tick < agg.last_xy_tick) return false;
    // Evidence gap: rebase path baseline; do not invent displacement across missing ticks.
    // Do NOT count cell_boundary_crossings across gaps — that would invent crossings.
    if (agg.last_xy_tick != null && tick > agg.last_xy_tick + 1) {
      agg.trajectory_gaps_skipped += 1;
      agg.last_xy = { x, y };
      agg.last_xy_tick = tick;
      agg.unique_position_ticks += 1;
      const cell = centerCellKey(x, y, w, h);
      if (agg.last_center_cell != null && agg.last_center_cell !== cell) {
        // Observed sample landed in a different cell after a gap — not a measured crossing.
        agg.neighborhood_replacements += 1;
      }
      agg.last_center_cell = cell;
      agg.unique_cells.add(cell);
      if (speed != null && Number.isFinite(speed)) {
        agg.max_speed = Math.max(agg.max_speed, speed);
        agg.speed_sum += speed;
        agg.speed_n += 1;
      }
      return true;
    }
    agg.last_xy_tick = tick;
  }
  if (!agg.start_xy) agg.start_xy = { x, y };
  if (!agg.unwrapped_xy) {
    agg.unwrapped_xy = { x, y };
    agg.unwrapped_min = { x, y };
    agg.unwrapped_max = { x, y };
  }
  agg.unique_position_ticks += 1;
  if (agg.last_xy) {
    let dx: number;
    let dy: number;
    if (w != null && h != null) {
      const rawDx = x - agg.last_xy.x;
      const rawDy = y - agg.last_xy.y;
      dx = wrapDelta(agg.last_xy.x, x, w);
      dy = wrapDelta(agg.last_xy.y, y, h);
      if (Math.abs(rawDx - dx) > 1e-12) agg.boundary_crossings_x += 1;
      if (Math.abs(rawDy - dy) > 1e-12) agg.boundary_crossings_y += 1;
      // Legacy field: keep name but prefer wrap-aware Manhattan when dims known.
      agg.distance += Math.abs(dx) + Math.abs(dy);
      agg.path_length_manhattan_wrap += Math.abs(dx) + Math.abs(dy);
      const step = Math.hypot(dx, dy);
      agg.path_length_euclidean += step;
      const act = agg.last_action;
      if (act === 'WAIT') {
        agg.path_during_requested_WAIT += step;
        agg.unwrapped_dx_during_WAIT += dx;
        agg.unwrapped_dy_during_WAIT += dy;
      } else if (act && String(act).startsWith('MOVE')) {
        agg.path_during_requested_MOVE += step;
        agg.unwrapped_dx_during_MOVE += dx;
        agg.unwrapped_dy_during_MOVE += dy;
      }
      if (agg.unwrapped_xy) {
        agg.unwrapped_xy = { x: agg.unwrapped_xy.x + dx, y: agg.unwrapped_xy.y + dy };
        agg.unwrapped_dx = agg.unwrapped_xy.x - (agg.start_xy?.x ?? x);
        agg.unwrapped_dy = agg.unwrapped_xy.y - (agg.start_xy?.y ?? y);
        const exc = Math.hypot(agg.unwrapped_dx, agg.unwrapped_dy);
        if (exc > agg.max_excursion_from_start) agg.max_excursion_from_start = exc;
        if (agg.unwrapped_min && agg.unwrapped_max) {
          agg.unwrapped_min.x = Math.min(agg.unwrapped_min.x, agg.unwrapped_xy.x);
          agg.unwrapped_min.y = Math.min(agg.unwrapped_min.y, agg.unwrapped_xy.y);
          agg.unwrapped_max.x = Math.max(agg.unwrapped_max.x, agg.unwrapped_xy.x);
          agg.unwrapped_max.y = Math.max(agg.unwrapped_max.y, agg.unwrapped_xy.y);
        }
      }
    } else {
      // Dims unknown: raw deltas only (explicitly non-WRAP; may inflate on torus).
      dx = x - agg.last_xy.x;
      dy = y - agg.last_xy.y;
      agg.distance += Math.abs(dx) + Math.abs(dy);
    }
  }
  const cell = centerCellKey(x, y, w, h);
  if (agg.last_center_cell != null && agg.last_center_cell !== cell) {
    agg.neighborhood_replacements += 1;
    agg.cell_boundary_crossings += 1;
  }
  agg.last_center_cell = cell;
  agg.last_xy = { x, y };
  agg.unique_cells.add(cell);
  if (speed != null && Number.isFinite(speed)) {
    agg.max_speed = Math.max(agg.max_speed, speed);
    agg.speed_sum += speed;
    agg.speed_n += 1;
    if (agg.last_xy_tick != null) {
      // One-tick realized displacement proxy from reported speed.
      agg.realized_displacement_sum += Math.abs(speed);
    }
  }
  return true;
}

/** Mark a timeline agent-state as scientifically consumed; false if duplicate. */
export function claimTimelineAgentState(
  state: AnalysisState,
  tick: number,
  agentId: string,
): boolean {
  return rememberKey(state.seen_timeline_agent_keys, timelineAgentKey(tick, agentId));
}
