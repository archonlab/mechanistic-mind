/**
 * LIVE Observer display retention caps — UI only.
 *
 * These are NOT scientific constants, NOT agent memory, and NOT Analyzer evidence.
 * Scientific history is loaded intentionally by Analyze Current / evidence APIs.
 */

export const LIVE_FE_TRAJECTORY_DISPLAY_DEFAULT = 500;
export const LIVE_FE_TRAJECTORY_DISPLAY_MAX = 2000;
export const LIVE_FE_EVENTS_DISPLAY_MAX = 500;
export const LIVE_FE_TIMELINE_DISPLAY_MAX = 400;
export const LIVE_FE_SIGNAL_SAMPLES_MAX = 1000;
export const LIVE_FE_COGNITION_CONTEXT_MAX = 200;
export const LIVE_FE_INTERVENTION_DISPLAY_MAX = 64;

/** Retain only the most recent `cap` items (latest-state semantics). */
export function retainRecent<T>(items: T[] | null | undefined, cap: number): T[] {
  if (!items || items.length === 0) return [];
  const n = Math.max(0, Math.floor(cap));
  if (n <= 0) return [];
  if (items.length <= n) return items.slice();
  return items.slice(-n);
}

/**
 * Project aux LIVE lists into bounded retained state.
 * Explicitly ignores any attached scientific_rows / scientific_history.
 */
export function projectLiveAuxState(input: {
  timeline?: any[];
  events?: any[];
  world_interventions?: any[];
  /** Must be ignored by LIVE projection — Analyzer-only. */
  scientific_rows?: any[];
  scientific_history?: any[];
}): {
  timeline: any[];
  events: any[];
  world_interventions: any[];
  scientific_rows_ignored: number;
} {
  const sciN =
    (Array.isArray(input.scientific_rows) ? input.scientific_rows.length : 0) +
    (Array.isArray(input.scientific_history) ? input.scientific_history.length : 0);
  return {
    timeline: retainRecent(input.timeline, LIVE_FE_TIMELINE_DISPLAY_MAX),
    events: retainRecent(input.events, LIVE_FE_EVENTS_DISPLAY_MAX),
    world_interventions: retainRecent(
      input.world_interventions,
      LIVE_FE_INTERVENTION_DISPLAY_MAX,
    ),
    scientific_rows_ignored: sciN,
  };
}

/** Simulate repeated LIVE frame arrivals; retained arrays must stay capped. */
export function simulateLiveFrameRetention(
  frames: any[],
  caps = {
    trajectory: LIVE_FE_TRAJECTORY_DISPLAY_MAX,
    events: LIVE_FE_EVENTS_DISPLAY_MAX,
    timeline: LIVE_FE_TIMELINE_DISPLAY_MAX,
  },
): {
  trajectory: any[];
  events: any[];
  timeline: any[];
  maxTrajectory: number;
  maxEvents: number;
  maxTimeline: number;
} {
  let trajectory: any[] = [];
  let events: any[] = [];
  let timeline: any[] = [];
  let maxTrajectory = 0;
  let maxEvents = 0;
  let maxTimeline = 0;
  for (const f of frames) {
    const pts = f?.trajectory?.points;
    if (Array.isArray(pts) && pts.length) {
      trajectory = retainRecent([...trajectory, ...pts], caps.trajectory);
    } else if (Array.isArray(pts)) {
      trajectory = retainRecent(pts, caps.trajectory);
    }
    // Ordinary LIVE: replace from frame embed (server already tailed); do not accumulate forever.
    if (Array.isArray(f?.trajectory?.points)) {
      trajectory = retainRecent(f.trajectory.points, caps.trajectory);
    }
    if (Array.isArray(f?.events)) {
      events = retainRecent(f.events, caps.events);
    }
    if (Array.isArray(f?.timeline)) {
      timeline = retainRecent(f.timeline, caps.timeline);
    }
    maxTrajectory = Math.max(maxTrajectory, trajectory.length);
    maxEvents = Math.max(maxEvents, events.length);
    maxTimeline = Math.max(maxTimeline, timeline.length);
  }
  return { trajectory, events, timeline, maxTrajectory, maxEvents, maxTimeline };
}
