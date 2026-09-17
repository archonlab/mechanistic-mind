import { BOUNDS, pushBounded } from './aggregates.ts';
import type { AnalysisState } from './aggregates.ts';
import type { ImportantEvent, KeyFrameRef } from './types.ts';
import { hasSufficientObservation, isMeaningfulExtrema } from './lifecycle.ts';

export function pushImportant(state: AnalysisState, ev: ImportantEvent) {
  pushBounded(state.important, ev, BOUNDS.important_events);
}

export function maybeAddKeyframe(
  state: AnalysisState,
  tick: number,
  reason: string,
  agents: Array<{ agent_id: string; x: number; y: number }>,
  contact: boolean,
  world_w: number | null,
  world_h: number | null,
) {
  if (state.keyframes.some((k) => k.tick === tick && k.reason === reason)) return;
  const kf: KeyFrameRef = {
    tick,
    reason,
    agents: agents.map((a) => ({ agent_id: a.agent_id, x: a.x, y: a.y })),
    contact,
    world_w,
    world_h,
  };
  // Hierarchical: keep firsts + spread evenly if over cap
  pushBounded(state.keyframes, kf, BOUNDS.keyframes);
  if (state.keyframes.length > BOUNDS.keyframes) {
    state.keyframes = selectRepresentativeKeyframes(state.keyframes, BOUNDS.keyframes);
  }
}

export function selectRepresentativeKeyframes(frames: KeyFrameRef[], max: number): KeyFrameRef[] {
  if (frames.length <= max) return frames;
  const sorted = [...frames].sort((a, b) => a.tick - b.tick);
  const out: KeyFrameRef[] = [];
  const first = sorted[0];
  const last = sorted[sorted.length - 1];
  out.push(first);
  const inner = max - 2;
  for (let i = 1; i <= inner; i++) {
    const idx = Math.round((i * (sorted.length - 1)) / (inner + 1));
    const f = sorted[idx];
    if (f && !out.some((o) => o.tick === f.tick && o.reason === f.reason)) out.push(f);
  }
  if (!out.some((o) => o.tick === last.tick && o.reason === last.reason)) out.push(last);
  return out.slice(0, max);
}

export function buildImportantEvents(state: AnalysisState): ImportantEvent[] {
  const out: ImportantEvent[] = [...state.important];
  // Extrema → important only when meaningful (suppress tick-0 zeros / empty window)
  for (const [key, ex] of Object.entries(state.extrema)) {
    if (!isMeaningfulExtrema(key, ex, state)) continue;
    out.push({
      tick: ex.tick,
      category: 'EXTREMA',
      kind: key.toUpperCase(),
      title: key.replaceAll('_', ' ').toUpperCase(),
      reason: `Extrema rule: ${key}=${ex.value} at tick ${ex.tick}.`,
      evidence_class: 'DERIVED',
      refs: { value: ex.value },
    });
  }
  if (!hasSufficientObservation(state)) {
    // Keep FIRST markers only if any; otherwise empty → UI shows INSUFFICIENT DATA
    return out.filter((e) => e.category === 'FIRST').slice(0, BOUNDS.important_events);
  }
  // Anomalies: long wait
  for (const agg of Object.values(state.agents)) {
    if (agg.longest_wait_streak >= 50) {
      out.push({
        tick: state.end_tick ?? 0,
        category: 'ANOMALY',
        kind: 'LONG_WAIT_STREAK',
        title: `LONG WAIT STREAK (${agg.agent_id})`,
        reason: `${agg.agent_id} longest WAIT streak = ${agg.longest_wait_streak} (≥50 rule).`,
        evidence_class: 'DERIVED',
        agent_ids: [agg.agent_id],
      });
    }
    if (agg.work_limited >= 10) {
      out.push({
        tick: state.end_tick ?? 0,
        category: 'ANOMALY',
        kind: 'REPEATED_WORK_LIMITATION',
        title: `REPEATED WORK LIMITATION (${agg.agent_id})`,
        reason: `${agg.work_limited} work-limitation events (≥10 rule).`,
        evidence_class: 'OBSERVED',
        agent_ids: [agg.agent_id],
      });
    }
  }
  // Deduplicate by tick+kind
  const seen = new Set<string>();
  const dedup: ImportantEvent[] = [];
  for (const ev of out.sort((a, b) => a.tick - b.tick)) {
    const k = `${ev.tick}|${ev.kind}|${(ev.agent_ids || []).join(',')}`;
    if (seen.has(k)) continue;
    seen.add(k);
    dedup.push(ev);
  }
  return dedup.slice(0, BOUNDS.important_events);
}
