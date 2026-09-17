/**
 * Stable identity helpers for Analyzer ingestion.
 * Simulation tick ≠ Observer sample — scientific metrics must dedupe by event/tick identity.
 */

const DEFAULT_SEEN_CAP = 8000;

/** Return true if `key` is newly recorded; false if already seen. Bound set size. */
export function rememberKey(seen: Set<string>, key: string, cap = DEFAULT_SEEN_CAP): boolean {
  if (seen.has(key)) return false;
  seen.add(key);
  if (seen.size > cap) {
    // Drop oldest half (Set iteration order = insertion order).
    const drop = seen.size - Math.floor(cap / 2);
    let i = 0;
    for (const k of seen) {
      seen.delete(k);
      if (++i >= drop) break;
    }
  }
  return true;
}

export function rememberNumber(seen: Set<number>, value: number, cap = DEFAULT_SEEN_CAP): boolean {
  if (seen.has(value)) return false;
  seen.add(value);
  if (seen.size > cap) {
    const drop = seen.size - Math.floor(cap / 2);
    let i = 0;
    for (const k of seen) {
      seen.delete(k);
      if (++i >= drop) break;
    }
  }
  return true;
}

/** Per-agent timeline state / action selection identity at a simulation tick. */
export function timelineAgentKey(tick: number, agentId: string): string {
  return `tl|${tick}|${agentId}`;
}

/** Unique simulation tick marker (shared world clock). */
export function simulationTickKey(tick: number): string {
  return `tick|${tick}`;
}

export function contactTickKey(tick: number): string {
  return `contact|${tick}`;
}

export function liveSummaryKey(tick: number): string {
  return `live|${tick}`;
}

export function telemetryRowKey(tick: number, seriesHint = 'primary'): string {
  return `tel|${seriesHint}|${tick}`;
}

/**
 * Prefer explicit runtime IDs; fall back to a conservative compound identity.
 * Never collapses two distinct IDs that share a tick.
 */
export function structuredEventKey(ev: any): string {
  const evidence = ev?.evidence || {};
  const tick = Number(ev?.tick);
  const et = String(ev?.type || ev?.kind || '');
  const explicit =
    ev?.event_id
    || ev?.receipt_id
    || evidence.event_id
    || evidence.receipt_id
    || evidence.emission_id
    || ev?.emission_id
    || evidence.reception_id
    || ev?.id;
  if (explicit != null && String(explicit).length > 0) {
    return `ev|${tick}|${et}|${String(explicit)}`;
  }
  const agent =
    ev?.actor_agent_id
    || ev?.emitter_agent_id
    || ev?.receiver_agent_id
    || ev?.agent_id
    || evidence.actor_agent_id
    || evidence.emitter_agent_id
    || evidence.receiver_agent_id
    || '';
  const action = evidence.selected_action || evidence.action || ev?.action || '';
  const source = evidence.selection_source || evidence.trigger || '';
  const channel = evidence.channel || '';
  return `ev|${tick}|${et}|${agent}|${action}|${source}|${channel}|${evidence.emission_id || ''}`;
}

/** Normalize contact episodes: drop inverted ranges; recompute tick span. */
export function sanitizeContactEpisode(
  start: number,
  end: number,
): { start: number; end: number; ticks: number } | null {
  if (!Number.isFinite(start) || !Number.isFinite(end)) return null;
  if (end < start) return null;
  return { start, end, ticks: Math.max(1, end - start + 1) };
}

/** Build contiguous episodes from a set of unique contact simulation ticks. */
export function episodesFromContactTicks(
  ticks: Iterable<number>,
  maxEpisodes = 40,
): Array<{ start: number; end: number; ticks: number }> {
  const sorted = [...new Set(ticks)].filter((t) => Number.isFinite(t)).sort((a, b) => a - b);
  const episodes: Array<{ start: number; end: number; ticks: number }> = [];
  let start: number | null = null;
  let prev: number | null = null;
  for (const t of sorted) {
    if (start == null) {
      start = t;
      prev = t;
      continue;
    }
    if (prev != null && t === prev + 1) {
      prev = t;
      continue;
    }
    const ep = sanitizeContactEpisode(start, prev!);
    if (ep) episodes.push(ep);
    start = t;
    prev = t;
  }
  if (start != null && prev != null) {
    const ep = sanitizeContactEpisode(start, prev);
    if (ep) episodes.push(ep);
  }
  if (episodes.length > maxEpisodes) return episodes.slice(-maxEpisodes);
  return episodes;
}
