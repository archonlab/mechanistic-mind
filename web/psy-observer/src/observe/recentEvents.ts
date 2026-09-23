/**
 * Observe V2 — RECENT STRUCTURED EVENTS (bounded, compressed).
 * Display-only; does not invent semantic communication events.
 */

import { compressConsecutiveEvents, type CompressibleEvent, type CompressedEventRow } from '../eventCompression.ts';
import {
  matchesObserveFilter,
  matchesSignalMechanismFilter,
  observeEventClass,
  type ObserveFilter,
  type SignalMechanismFilter,
} from './eventCategory.ts';

export type StructuredObserveEvent = {
  class: string;
  title: string;
  tick_start: number;
  tick_end: number;
  count: number;
  agent_id: string;
  detail: string;
  raw_type: string;
  mechanism?: 'OSCILLATORY' | 'LEGACY_FIELD' | 'OTHER';
  /** When true, this is a compressed OSC ACTIVE span — not repeated OSC_EMIT. */
  osc_active_span?: boolean;
};

export const RECENT_EVENT_CAPS = {
  '100': 100,
  '500': 500,
  ALL_LOADED: 2000,
} as const;

export type RecentCapKey = keyof typeof RECENT_EVENT_CAPS;

function agentOf(e: CompressibleEvent): string {
  return String(
    e.actor_agent_id || e.agent_id || e.emitter_agent_id || e.receiver_agent_id || '',
  );
}

function titleFor(e: CompressibleEvent): string {
  const t = String(e.type || e.kind || 'EVENT');
  const cls = observeEventClass(t);
  if (cls === 'OSC') {
    if (t.includes('STARTED') || t.includes('START')) return 'OSC EMISSION START';
    if (t.includes('ENDED') || t.includes('END')) return 'OSC EMISSION END';
    if (t.includes('RECEPTION')) return 'OSC RECEPTION CHANGE';
    return 'OSC EVENT';
  }
  if (cls === 'LEGACY_FIELD') {
    if (t.includes('EMITTED')) return 'LEGACY FIELD EMITTED';
    if (t.includes('RECEIVED')) return 'LEGACY FIELD RECEIVED';
    return 'LEGACY FIELD EVENT';
  }
  if (cls === 'MOTOR') {
    const act = e.evidence?.selected_action || e.evidence?.action || e.selected_action;
    if (act) return `MOTOR · ${act}`;
    return 'MOTOR CHANGE';
  }
  if (cls === 'VISION') return 'VISION EVENT';
  if (cls === 'CONTACT') return t.includes('PUSH') ? 'PUSH' : 'CONTACT EVENT';
  if (cls === 'WORLD') return 'WORLD INTERVENTION';
  return t.replace(/_/g, ' ');
}

function detailFor(e: CompressibleEvent): string {
  const ev = e.evidence || {};
  const parts: string[] = [];
  const act = ev.selected_action || ev.action;
  if (act) parts.push(String(act));
  if (ev.channel) parts.push(`ch=${ev.channel}`);
  if (ev.frequency != null) parts.push(`f=${Number(ev.frequency).toFixed(2)}`);
  if (ev.amplitude != null) parts.push(`a=${Number(ev.amplitude).toFixed(2)}`);
  if (ev.osc_freq_u != null) parts.push(`f=${Number(ev.osc_freq_u).toFixed(2)}`);
  if (ev.osc_amp_u != null) parts.push(`a=${Number(ev.osc_amp_u).toFixed(2)}`);
  if (ev.intensity != null) parts.push(`inten=${Number(ev.intensity).toFixed(3)}`);
  return parts.join(' · ');
}

/**
 * Compress contiguous OSC_EMIT control selections into start/active/end style
 * when remaining/active markers are present; otherwise use identity compression.
 */
export function compressOscEmissionSpans(
  events: CompressibleEvent[],
): StructuredObserveEvent[] {
  const sorted = [...events].sort((a, b) => Number(a.tick) - Number(b.tick));
  const out: StructuredObserveEvent[] = [];
  let i = 0;
  while (i < sorted.length) {
    const e = sorted[i];
    const t = String(e.type || e.kind || '');
    const cls = observeEventClass(t);
    if (cls === 'OSC' && (t.includes('STARTED') || t.includes('START'))) {
      const aid = agentOf(e);
      const start = Number(e.tick);
      let end = start;
      let j = i + 1;
      // Consume following OSC active-ish rows for same agent until END or non-OSC
      while (j < sorted.length) {
        const n = sorted[j];
        const nt = String(n.type || n.kind || '');
        const ncls = observeEventClass(nt);
        if (agentOf(n) !== aid) break;
        if (ncls !== 'OSC') break;
        if (nt.includes('ENDED') || nt.includes('END')) {
          end = Number(n.tick);
          j++;
          break;
        }
        // Do not treat every active tick as a new OSC_EMIT selection card
        if (
          nt.includes('ACTIVE')
          || nt.includes('EMISSION')
          || Number(n.tick) === end + 1
        ) {
          end = Number(n.tick);
          j++;
          continue;
        }
        break;
      }
      out.push({
        class: 'OSC',
        title: 'OSC EMISSION START',
        tick_start: start,
        tick_end: start,
        count: 1,
        agent_id: aid,
        detail: detailFor(e),
        raw_type: t,
        mechanism: 'OSCILLATORY',
      });
      if (end > start) {
        out.push({
          class: 'OSC',
          title: 'OSC EMISSION ACTIVE',
          tick_start: start + 1,
          tick_end: end,
          count: end - start,
          agent_id: aid,
          detail: `${end - start} ticks`,
          raw_type: 'OSC_EMISSION_ACTIVE',
          mechanism: 'OSCILLATORY',
          osc_active_span: true,
        });
        out.push({
          class: 'OSC',
          title: 'OSC EMISSION END',
          tick_start: end,
          tick_end: end,
          count: 1,
          agent_id: aid,
          detail: '',
          raw_type: 'OSC_EMISSION_ENDED',
          mechanism: 'OSCILLATORY',
        });
      }
      i = j;
      continue;
    }
    // Skip raw mid-emission duplicates that would look like repeated OSC_EMIT
    if (
      cls === 'OSC'
      && !t.includes('STARTED')
      && !t.includes('START')
      && !t.includes('ENDED')
      && !t.includes('END')
      && !t.includes('RECEPTION')
      && (t.includes('ACTIVE') || t.includes('OSC_EMIT'))
    ) {
      i++;
      continue;
    }
    const mech =
      cls === 'OSC' ? 'OSCILLATORY' : cls === 'LEGACY_FIELD' ? 'LEGACY_FIELD' : 'OTHER';
    out.push({
      class: cls,
      title: titleFor(e),
      tick_start: Number(e.tick),
      tick_end: Number(e.tick),
      count: 1,
      agent_id: agentOf(e),
      detail: detailFor(e),
      raw_type: t,
      mechanism: mech,
    });
    i++;
  }
  return out;
}

export function filterEventsForObserve(
  events: CompressibleEvent[],
  opts: {
    filter?: ObserveFilter;
    signalFilter?: SignalMechanismFilter;
    agentFilter?: 'ALL AGENTS' | 'AGENT_0' | 'AGENT_1';
  } = {},
): CompressibleEvent[] {
  const filter = opts.filter || 'ALL';
  const signalFilter = opts.signalFilter || 'ALL_SIGNALS';
  const agentFilter = opts.agentFilter || 'ALL AGENTS';
  return events.filter((e) => {
    const t = String(e.type || e.kind || '');
    if (!matchesObserveFilter(t, filter)) return false;
    if (filter === 'SIGNAL' || filter === 'OSC') {
      if (filter === 'SIGNAL' && !matchesSignalMechanismFilter(t, signalFilter)) return false;
    }
    if (filter === 'ALL' && opts.signalFilter && opts.signalFilter !== 'ALL_SIGNALS') {
      // Optional mechanism narrowing even on ALL when explicitly set from SIGNAL UI
      if (observeEventClass(t) === 'OSC' || observeEventClass(t) === 'LEGACY_FIELD') {
        if (!matchesSignalMechanismFilter(t, signalFilter)) return false;
      }
    }
    if (agentFilter !== 'ALL AGENTS') {
      const want = agentFilter === 'AGENT_0' ? 'agent_0' : 'agent_1';
      if (agentOf(e) !== want) return false;
    }
    return true;
  });
}

export function buildRecentStructuredEvents(
  events: CompressibleEvent[],
  opts: {
    filter?: ObserveFilter;
    signalFilter?: SignalMechanismFilter;
    agentFilter?: 'ALL AGENTS' | 'AGENT_0' | 'AGENT_1';
    cap?: number;
  } = {},
): StructuredObserveEvent[] {
  const cap = opts.cap ?? RECENT_EVENT_CAPS['100'];
  const filtered = filterEventsForObserve(events, opts);
  const bounded = filtered.length > cap ? filtered.slice(-cap) : filtered;
  // First compress generic consecutive identity (MOVE:W × N)
  const compressed = compressConsecutiveEvents(bounded);
  // Map to structured; then OSC span compression on OSC subset
  const oscRaw = bounded.filter((e) => observeEventClass(String(e.type || e.kind || '')) === 'OSC');
  const oscStructured = compressOscEmissionSpans(oscRaw);
  const nonOsc = compressed.filter(
    (e) => observeEventClass(String(e.type || e.kind || '')) !== 'OSC',
  );
  const mapped: StructuredObserveEvent[] = nonOsc.map((e: CompressedEventRow) => {
    const t = String(e.type || e.kind || '');
    const cls = observeEventClass(t);
    return {
      class: cls,
      title: titleFor(e),
      tick_start: Number(e._tick_start ?? e.tick),
      tick_end: Number(e._tick_end ?? e.tick),
      count: Number(e._count || 1),
      agent_id: agentOf(e),
      detail:
        (e._count || 1) > 1
          ? `${detailFor(e)} · ${e._count} ticks`.trim()
          : detailFor(e),
      raw_type: t,
      mechanism:
        cls === 'OSC' ? 'OSCILLATORY' : cls === 'LEGACY_FIELD' ? 'LEGACY_FIELD' : 'OTHER',
    };
  });
  const merged = [...mapped, ...oscStructured].sort(
    (a, b) => a.tick_start - b.tick_start || a.tick_end - b.tick_end,
  );
  return merged.length > cap ? merged.slice(-cap) : merged;
}

/** Count of DOM-facing cards — must stay bounded. */
export function recentEventCardCount(events: StructuredObserveEvent[]): number {
  return events.length;
}
