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
  distance: number;
  unique_cells: Set<string>;
  last_xy: { x: number; y: number } | null;
  start_xy: { x: number; y: number } | null;
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
    distance: 0,
    unique_cells: new Set(),
    last_xy: null,
    start_xy: null,
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
  };
}

export function ensureAgent(state: AnalysisState, agent_id: string, body_id?: string, seed?: number | null) {
  if (!state.agents[agent_id]) {
    state.agents[agent_id] = makeAgentAgg(agent_id, body_id || canonicalBody(agent_id), seed ?? null);
  } else {
    if (body_id) state.agents[agent_id].body_id = body_id;
    if (seed != null) state.agents[agent_id].seed = seed;
  }
  return state.agents[agent_id];
}

export function canonicalBody(agentId: string) {
  const m = /^agent_(\d+)$/.exec(String(agentId));
  return m ? `body-${m[1]}` : 'body-0';
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
    agg.wait_streak = 0;
    agg.move_streak = 0;
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
    agg.wait_streak += 1;
    agg.move_streak = 0;
    agg.longest_wait_streak = Math.max(agg.longest_wait_streak, agg.wait_streak);
    if (agg.first_move_tick != null && agg.first_wait_after_move_tick == null && agg.wait_streak >= 5) {
      agg.first_wait_after_move_tick = tick - agg.wait_streak + 1;
    }
  } else if (isMove) {
    agg.move_streak += 1;
    agg.wait_streak = 0;
    agg.longest_move_streak = Math.max(agg.longest_move_streak, agg.move_streak);
    if (agg.first_move_tick == null) agg.first_move_tick = tick;
  } else {
    agg.wait_streak = 0;
    agg.move_streak = 0;
  }
  agg.last_action = action;
  return true;
}

/**
 * Apply body position once per simulation tick.
 * Repeated samples of the same tick must not inflate distance.
 */
export function ingestXy(agg: AgentAgg, x: number, y: number, speed?: number, tick?: number): boolean {
  if (!Number.isFinite(x) || !Number.isFinite(y)) return false;
  if (tick != null && Number.isFinite(tick)) {
    if (agg.last_xy_tick != null && tick === agg.last_xy_tick) {
      // Same tick re-sample: keep latest coords without adding distance.
      agg.last_xy = { x, y };
      return false;
    }
    if (agg.last_xy_tick != null && tick < agg.last_xy_tick) return false;
    agg.last_xy_tick = tick;
  }
  if (!agg.start_xy) agg.start_xy = { x, y };
  if (agg.last_xy) {
    agg.distance += Math.abs(x - agg.last_xy.x) + Math.abs(y - agg.last_xy.y);
  }
  agg.last_xy = { x, y };
  agg.unique_cells.add(`${Math.floor(x)},${Math.floor(y)}`);
  if (speed != null && Number.isFinite(speed)) {
    agg.max_speed = Math.max(agg.max_speed, speed);
    agg.speed_sum += speed;
    agg.speed_n += 1;
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
