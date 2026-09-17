/**
 * Compress consecutive identical cognition / action events for Timeline presentation.
 * Raw event buffers remain unchanged — this is display-only.
 */
export type CompressibleEvent = Record<string, any>;

export type CompressedEventRow = CompressibleEvent & {
  _compressed?: boolean;
  _count?: number;
  _tick_start?: number;
  _tick_end?: number;
};

function eventIdentityKey(e: CompressibleEvent): string {
  const et = String(e.type || e.kind || '');
  const ev = e.evidence || {};
  const aid = e.actor_agent_id || e.agent_id || '';
  const act = ev.selected_action || ev.action || '';
  const src = ev.selection_source || '';
  return `${et}|${aid}|${act}|${src}`;
}

/** Merge consecutive same-type/agent/action/source rows into a single display row. */
export function compressConsecutiveEvents(events: CompressibleEvent[]): CompressedEventRow[] {
  const out: CompressedEventRow[] = [];
  for (const e of events) {
    const key = eventIdentityKey(e);
    const tick = Number(e.tick);
    const prev = out[out.length - 1];
    if (
      prev
      && eventIdentityKey(prev) === key
      && Number.isFinite(tick)
      && Number(prev._tick_end ?? prev.tick) + 1 === tick
    ) {
      prev._compressed = true;
      prev._count = (prev._count || 1) + 1;
      prev._tick_end = tick;
      prev._tick_start = prev._tick_start ?? Number(prev.tick);
      continue;
    }
    out.push({
      ...e,
      _compressed: false,
      _count: 1,
      _tick_start: tick,
      _tick_end: tick,
    });
  }
  return out;
}

export function compressedEventSummary(e: CompressedEventRow): string {
  const ev = e.evidence || {};
  const aid = e.actor_agent_id || e.agent_id || '';
  const act = ev.selected_action || ev.action || '';
  const src = ev.selection_source || '';
  const et = String(e.type || e.kind || '');
  if (et === 'SCENARIO_SELECTED') {
    const base = [aid, act, src ? `source: ${src}` : ''].filter(Boolean).join(' · ');
    if ((e._count || 1) > 1) {
      return `${base} · ticks ${e._tick_start}–${e._tick_end} · ${e._count} consecutive selections`;
    }
    return base;
  }
  if (et === 'DISCRETE_ACTION_SELECTED') {
    const base = [aid, act, src ? `source: ${src}` : ''].filter(Boolean).join(' · ');
    if ((e._count || 1) > 1) {
      return `${base} · ticks ${e._tick_start}–${e._tick_end} · ${e._count}×`;
    }
    return base;
  }
  return '';
}
