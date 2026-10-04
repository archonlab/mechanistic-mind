/** S7C Destination-depth — Events stream owns center.

Bounded chronological list from existing live events authority.
Selection is display-only; details belong in the right inspector.
*/

import { useMemo, useState } from 'react';
import { compressConsecutiveEvents, compressedEventSummary } from '../eventCompression';
import { observeEventClass, type ObserveEventClass } from '../observe/eventCategory';
import { LIVE_FE_EVENTS_DISPLAY_MAX } from '../liveBounds';
import { PhenomenonDetails } from '../components/PhenomenonDetails';

const FILTERS: { id: string; label: string; match: (c: ObserveEventClass, type: string) => boolean }[] = [
  { id: 'ALL', label: 'All', match: () => true },
  { id: 'PHYSICAL', label: 'Physical', match: (c) => c === 'BODY' || c === 'WORK' || c === 'WORLD' },
  { id: 'SENSORY', label: 'Sensory', match: (c) => c === 'VISION' || c === 'OSC' || c === 'LEGACY_FIELD' },
  { id: 'MOTOR', label: 'Motor', match: (c) => c === 'MOTOR' },
  { id: 'CONTACT', label: 'Contact', match: (c) => c === 'CONTACT' },
  { id: 'MATERIAL', label: 'Material', match: (c) => c === 'RESOURCE' || c === 'WORLD' },
  { id: 'ACOUSTIC', label: 'Acoustic', match: (c, t) => c === 'OSC' || /ACOUSTIC|AUDITORY|SOUND/i.test(t) },
  { id: 'OPTICAL', label: 'Optical', match: (c) => c === 'VISION' },
  { id: 'RUNTIME', label: 'Experiment/runtime', match: (c, t) => c === 'WORLD' || /EXPERIMENT|RUNTIME|CONFIG/i.test(t) },
  { id: 'ERROR', label: 'Errors/warnings', match: (_c, t) => /ERROR|WARN|FAIL/i.test(t) },
  { id: 'OTHER', label: 'Other/Unclassified', match: (c) => c === 'OTHER' || c === 'COGNITION' },
];

const DISPLAY_CAP = Math.min(120, LIVE_FE_EVENTS_DISPLAY_MAX);

type Props = {
  events: any[];
  selectedEvent: any | null;
  onSelectEvent: (e: any) => void;
  selectedAgentId: string;
  tick: number | string;
  generation: number | string;
};

function concise(e: any): string {
  return compressedEventSummary(e)
    || String(e?.evidence?.selected_action || e?.evidence?.action || e?.summary || '')
    || String(e?.type || e?.kind || 'event');
}

export function EventsCentralWorkspace({
  events,
  selectedEvent,
  onSelectEvent,
  selectedAgentId,
  tick,
  generation,
}: Props) {
  const [filter, setFilter] = useState('ALL');
  const genNum = generation != null && generation !== '—' ? Number(generation) : null;

  const bounded = useMemo(() => {
    const raw = Array.isArray(events) ? events : [];
    // Bound + same-generation preference when generation present on events
    const sameGen = genNum != null && Number.isFinite(genNum)
      ? raw.filter((e) => e?.runtime_generation == null || Number(e.runtime_generation) === genNum)
      : raw;
    const sliced = sameGen.length > DISPLAY_CAP ? sameGen.slice(-DISPLAY_CAP) : sameGen;
    return compressConsecutiveEvents(sliced);
  }, [events, genNum]);

  const filtered = useMemo(() => {
    const f = FILTERS.find((x) => x.id === filter) || FILTERS[0];
    return bounded.filter((e) => {
      const type = String(e?.type || e?.kind || '');
      const c = observeEventClass(type);
      return f.match(c, type);
    });
  }, [bounded, filter]);

  const categories = [
    {
      id: 'filters',
      title: 'Filters and classification',
      summary: `${filtered.length} shown · cap=${DISPLAY_CAP} · live ≠ saved evidence`,
      children: (
        <div className="subtle">
          Filters use existing observeEventClass mappings. Unmapped types appear as Other/Unclassified.
          No semantic narratives. No polling-created events.
        </div>
      ),
    },
    {
      id: 'authority',
      title: 'Scientific authority and limitations',
      summary: 'bounded live stream · generation-aware · not Analyzer reconstruction',
      children: (
        <div className="subtle">
          <div>raw_buffer ≤ {LIVE_FE_EVENTS_DISPLAY_MAX}</div>
          <div>display_cap = {DISPLAY_CAP}</div>
          <div>selected_agent context = {String(selectedAgentId)}</div>
          <div>Selecting an event opens details in the right inspector — does not mutate simulation.</div>
          <div>Saved evidence packages are distinct (Scientific Tools → Saved Runs / Analyzer).</div>
        </div>
      ),
    },
  ];

  return (
    <div
      className="events-central-workspace"
      data-testid="events-central-workspace"
      data-owns-center="true"
      aria-label="Events observation"
    >
      <header className="fpv-central-header">
        <strong>EVENTS</strong>
        <span className="subtle">
          Live stream · tick={String(tick)} · gen={String(generation)} · selected={String(selectedAgentId).toUpperCase()}
        </span>
      </header>

      <div className="events-filter-row" role="toolbar" aria-label="Event filters">
        {FILTERS.map((f) => (
          <button
            key={f.id}
            type="button"
            className={filter === f.id ? 'active' : ''}
            data-testid={`events-filter-${f.id.toLowerCase()}`}
            onClick={() => setFilter(f.id)}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="events-central-primary" data-testid="events-central-primary">
        {filtered.length === 0 ? (
          <div className="empty" data-testid="events-empty">No matching live events in the bounded window.</div>
        ) : (
          <ul className="events-stream-list" role="listbox" aria-label="Live event stream">
            {filtered.map((e, i) => {
              const type = String(e?.type || e?.kind || 'event');
              const cls = observeEventClass(type);
              const label = cls === 'OTHER' ? 'Other/Unclassified' : cls;
              const key = `${e._tick_start ?? e.tick}-${type}-${e.agent_id ?? ''}-${i}`;
              const selected = selectedEvent
                && (selectedEvent === e
                  || (selectedEvent.tick === e.tick && (selectedEvent.type || selectedEvent.kind) === type));
              return (
                <li key={key}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={!!selected}
                    className={`events-stream-item ${selected ? 'active' : ''}`}
                    data-testid="events-stream-item"
                    onClick={() => onSelectEvent(e)}
                  >
                    <span className="events-stream-tick">
                      t{e._count && e._count > 1 ? `${e._tick_start}–${e._tick_end}` : e.tick}
                    </span>
                    <span className="events-stream-class">{label}</span>
                    <span className="events-stream-type">{type}</span>
                    <span className="events-stream-agent">
                      {String(e.actor_agent_id || e.agent_id || e.emitter_agent_id || '—')}
                    </span>
                    <span className="events-stream-desc">{concise(e)}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <PhenomenonDetails categories={categories} testIdPrefix="events" />
    </div>
  );
}
