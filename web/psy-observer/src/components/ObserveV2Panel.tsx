/**
 * Observe V2 — CURRENT STATE × RECENT EVENTS × RAW EVIDENCE
 * Presentation only. Does not invoke full-run forensics on live refresh.
 */
import { useEffect, useMemo, useState, type ReactNode } from 'react';
import {
  bandSpark,
  buildObserveCurrentState,
  type ObserveCurrentState,
} from '../observe/currentState';
import {
  buildRecentStructuredEvents,
  RECENT_EVENT_CAPS,
  type RecentCapKey,
  type StructuredObserveEvent,
} from '../observe/recentEvents';
import type { ObserveFilter, SignalMechanismFilter } from '../observe/eventCategory';

export type ObserveSection = 'agent' | 'body' | 'environment' | 'cognition' | 'predictive';

type Props = {
  frame: any;
  events: any[];
  timeline: any[];
  runId?: string | null;
  agentId?: string | null;
  agentObservation?: Record<string, number> | null;
  attribution?: string | null;
  onSelectEvent?: (e: any) => void;
  /** Legacy timeline/raw content rendered only when showRaw is true. */
  rawEvidenceSlot?: ReactNode;
  /** When set, render only that Inspector tab slice — never the full dump. */
  section?: ObserveSection;
};

function fmt(v: unknown, digits = 3): string {
  if (v === null || v === undefined || v === 'NOT AVAILABLE') return 'NOT AVAILABLE';
  if (typeof v === 'boolean') return v ? 'YES' : 'NO';
  if (typeof v === 'number') {
    if (!Number.isFinite(v)) return 'NOT AVAILABLE';
    return Number.isInteger(v) ? String(v) : v.toFixed(digits);
  }
  return String(v);
}

function deg(v: unknown): string {
  if (v === 'NOT AVAILABLE' || v == null) return 'NOT AVAILABLE';
  const n = Number(v);
  if (!Number.isFinite(n)) return 'NOT AVAILABLE';
  return `${(n * (180 / Math.PI)).toFixed(1)}°`;
}

function Metric({ name, value }: { name: string; value: unknown }) {
  return (
    <div className="metric">
      <span>{name}</span>
      <strong>{fmt(value)}</strong>
    </div>
  );
}

function EventRow({
  ev,
  onClick,
}: {
  ev: StructuredObserveEvent;
  onClick?: () => void;
}) {
  const tickLabel =
    ev.tick_start === ev.tick_end
      ? `t${ev.tick_start}`
      : `t${ev.tick_start}–${ev.tick_end}`;
  return (
    <button type="button" className="observe-event-row" onClick={onClick}>
      <span className="observe-event-tick">{tickLabel}</span>
      <b>{ev.title}</b>
      <small>
        {ev.agent_id || '—'}
        {ev.count > 1 ? ` · ${ev.count} ticks` : ''}
        {ev.detail ? ` · ${ev.detail}` : ''}
        {ev.mechanism && ev.mechanism !== 'OTHER' ? ` · ${ev.mechanism}` : ''}
      </small>
    </button>
  );
}

const SECTION_EVENT_FILTER: Record<ObserveSection, ObserveFilter> = {
  agent: 'MOTOR',
  body: 'BODY',
  environment: 'WORLD',
  cognition: 'ALL',
  predictive: 'SIGNAL',
};

export function ObserveV2Panel({
  frame,
  events,
  timeline,
  runId,
  agentId,
  agentObservation,
  attribution,
  onSelectEvent,
  rawEvidenceSlot,
  section,
}: Props) {
  const sectionFilter = section ? SECTION_EVENT_FILTER[section] : 'ALL';
  const [filter, setFilter] = useState<ObserveFilter>(sectionFilter);
  const [signalFilter, setSignalFilter] = useState<SignalMechanismFilter>('ALL_SIGNALS');
  const [agentFilter, setAgentFilter] = useState<'ALL AGENTS' | 'AGENT_0' | 'AGENT_1'>('ALL AGENTS');
  const [capKey, setCapKey] = useState<RecentCapKey>('100');
  const [showRaw, setShowRaw] = useState(false);
  const [compact, setCompact] = useState(true);

  const state: ObserveCurrentState = useMemo(
    () =>
      buildObserveCurrentState(frame, {
        run_id: runId,
        agent_id: agentId,
        agentObservation,
        attribution,
      }),
    [frame, runId, agentId, agentObservation, attribution],
  );

  const recent = useMemo(
    () =>
      buildRecentStructuredEvents(events || [], {
        filter,
        signalFilter: filter === 'SIGNAL' || filter === 'OSC' ? signalFilter : 'ALL_SIGNALS',
        agentFilter,
        cap: RECENT_EVENT_CAPS[capKey],
      }),
    [events, filter, signalFilter, agentFilter, capKey],
  );

  useEffect(() => {
    if (section) setFilter(SECTION_EVENT_FILTER[section]);
  }, [section]);

  const p = state.provenance;
  const m = state.motor;
  const e = state.effectors;
  const s = state.passive;

  const showAll = !section;
  const showAgent = showAll || section === 'agent';
  const showBody = showAll || section === 'body' || section === 'agent';
  const showEnv = showAll || section === 'environment';
  const showEvents = true;
  const showRawBlock = showAll || section === 'cognition';
  const eventFilters: ObserveFilter[] = showAll
    ? ['ALL', 'MOTOR', 'OSC', 'SIGNAL', 'VISION', 'CONTACT', 'BODY', 'WORLD']
    : section === 'agent'
      ? ['ALL', 'MOTOR']
      : section === 'body'
        ? ['ALL', 'BODY', 'CONTACT']
        : section === 'environment'
          ? ['ALL', 'WORLD', 'VISION', 'CONTACT']
          : section === 'predictive'
            ? ['ALL', 'SIGNAL', 'OSC']
            : ['ALL', 'MOTOR', 'OSC', 'SIGNAL', 'VISION', 'CONTACT', 'BODY', 'WORLD'];

  return (
    <div className="observe-v2" data-observe-section={section || 'all'}>
      {showAll ? (
      <header className="observe-v2-header">
        <h3>OBSERVE</h3>
        <div className="observe-v2-prov">
          <span>RUN <b>{String(p.run_id).slice(0, 28)}</b></span>
          <span>GEN <b>{fmt(p.generation, 0)}</b></span>
          <span>TICK <b>{fmt(p.tick, 0)}</b></span>
          <span>AGENT <b>{p.agent_id}</b></span>
          <span>MOTOR <b>{p.motor_schema}</b></span>
          <span>TELEMETRY <b>{p.telemetry_schema}</b></span>
          <span className={`badge ${String(p.status).toLowerCase()}`}>{p.status}</span>
        </div>
      </header>
      ) : (
        <div className="observe-v2-prov">
          <span>TICK <b>{fmt(p.tick, 0)}</b></span>
          <span>AGENT <b>{p.agent_id}</b></span>
          <span className={`badge ${String(p.status).toLowerCase()}`}>{p.status}</span>
        </div>
      )}

      {(showAgent || showBody || showEnv) ? (
      <section className="observe-v2-section">
        <div className="observe-v2-section-head">
          <h4>{section === 'body' ? 'BODY / EFFECTORS' : 'CURRENT STATE'}</h4>
          <button type="button" onClick={() => setCompact((c) => !c)}>
            {compact ? 'DETAIL' : 'COMPACT'}
          </button>
        </div>

        <div className="observe-v2-grid">
          {showAgent ? (
          <div className="observe-v2-card">
            <div className="section-label">A · MOTOR OUTPUT</div>
            {m.schema === 'LEGACY_SINGLE_SLOT' ? (
              <>
                <Metric name="Schema" value={m.schema} />
                <Metric name="ACTION" value={m.legacy_action} />
              </>
            ) : (
              <>
                <Metric name="Schema" value={m.schema} />
                <Metric name="LOCOMOTION" value={m.locomotion} />
                <Metric name="NECK" value={m.neck} />
                <Metric name="OSC emit trigger" value={m.osc_emit_trigger} />
                {!compact ? (
                  <>
                    <Metric name="OSC freq Δ" value={m.osc_freq_delta} />
                    <Metric name="OSC amp Δ" value={m.osc_amp_delta} />
                  </>
                ) : null}
                <Metric name="PUSH" value={m.push} />
              </>
            )}
            <div className="subtle">{m.summary_line}</div>
          </div>
          ) : null}

          {showBody ? (
          <div className="observe-v2-card">
            <div className="section-label">B · ACTIVE PHYSICAL EFFECTORS</div>
            <Metric name="MOTION" value={e.motion_active ? 'ACTIVE' : 'IDLE'} />
            <Metric name="speed" value={e.speed} />
            {!compact ? (
              <>
                <Metric name="vx" value={e.vx} />
                <Metric name="vy" value={e.vy} />
              </>
            ) : null}
            <div className="section-label" style={{ marginTop: 6 }}>HEAD</div>
            <Metric name="angle" value={deg(e.head_relative_angle)} />
            <Metric name="omega" value={e.head_omega} />
            {!compact ? <Metric name="world heading" value={deg(e.head_world_heading)} /> : null}
            <Metric name="neck" value={e.neck_torque} />
            <div className="section-label" style={{ marginTop: 6 }}>OSCILLATOR</div>
            <Metric name="emission" value={e.osc_emitting ? 'ACTIVE' : 'IDLE'} />
            <Metric name="frequency" value={e.osc_freq_u} />
            <Metric name="amplitude" value={e.osc_amp_u} />
            <Metric name="remaining" value={e.osc_remaining} />
            <Metric name="PUSH" value={e.push_active ? 'ACTIVE' : 'OFF'} />
            <Metric name="contact" value={e.contact_active} />
            <div className="subtle">
              Command ≠ effector persistence · OSC_EMIT once may leave emission ACTIVE for N ticks
            </div>
          </div>
          ) : null}

          {showEnv ? (
          <div className="observe-v2-card">
            <div className="section-label">C · PASSIVE SENSORY INPUT</div>
            <div className="section-label">VISION</div>
            <Metric name="enabled" value={s.vision_enabled ? 'ON' : 'OFF'} />
            <div className="subtle">
              L {fmt(s.exo_0)} · F {fmt(s.exo_1)} · R {fmt(s.exo_2)}
            </div>
            <div className="section-label" style={{ marginTop: 6 }}>OSCILLATORY RECEPTION</div>
            <div className="subtle">L {bandSpark(s.osc_l) || 'NO EVIDENCE YET'}</div>
            <div className="subtle">R {bandSpark(s.osc_r) || 'NO EVIDENCE YET'}</div>
            {!compact && s.osc_l.length ? (
              <div className="subtle">L bands [{s.osc_l.map((v) => v.toFixed(2)).join(', ')}]</div>
            ) : null}
            {!compact && s.osc_r.length ? (
              <div className="subtle">R bands [{s.osc_r.map((v) => v.toFixed(2)).join(', ')}]</div>
            ) : null}
            {(s.legacy_fields_present || !compact) ? (
              <>
                <div className="section-label" style={{ marginTop: 6 }}>LEGACY PHYSICAL FIELDS</div>
                <Metric name="FIELD_A" value={s.field_a} />
                <Metric name="FIELD_B" value={s.field_b} />
              </>
            ) : null}
            <div className="section-label" style={{ marginTop: 6 }}>VESTIBULAR</div>
            <Metric name="vest_0" value={s.vest_0} />
            <Metric name="vest_1" value={s.vest_1} />
            <div className="section-label" style={{ marginTop: 6 }}>NECK PROPRIOCEPTION</div>
            <Metric name="prop_neck_0" value={s.prop_neck_0} />
            <Metric name="prop_neck_1" value={s.prop_neck_1} />
            <div className="section-label" style={{ marginTop: 6 }}>FULL-DUPLEX (physical)</div>
            <Metric name="EMITTING" value={s.emitting ? 'YES' : 'NO'} />
            <Metric name="RECEIVING" value={s.receiving ? 'YES' : 'NO'} />
            <div className="section-label" style={{ marginTop: 6 }}>OBSERVER GT</div>
            <Metric name="RX provenance" value={s.observer_gt_rx_provenance} />
            <div className="subtle">SELF/CROSS/MIXED are Observer GT only — not cognition.</div>
          </div>
          ) : null}
        </div>
      </section>
      ) : null}

      {showEvents ? (
      <section className="observe-v2-section">
        <div className="observe-v2-section-head">
          <h4>RECENT EVENTS</h4>
          <div className="toolbar-row" style={{ gap: 4, flexWrap: 'wrap' }}>
            {(['100', '500', 'ALL_LOADED'] as RecentCapKey[]).map((k) => (
              <button
                key={k}
                type="button"
                style={{ opacity: capKey === k ? 1 : 0.65 }}
                onClick={() => setCapKey(k)}
              >
                {k === 'ALL_LOADED' ? 'ALL LOADED' : k}
              </button>
            ))}
          </div>
        </div>
        <div className="toolbar-row" style={{ gap: 4, flexWrap: 'wrap', marginBottom: 6 }}>
          {eventFilters.map(
            (f) => (
              <button
                key={f}
                type="button"
                className={filter === f ? 'active' : ''}
                onClick={() => setFilter(f)}
              >
                {f}
              </button>
            ),
          )}
        </div>
        {(filter === 'SIGNAL' || filter === 'OSC') ? (
          <div className="toolbar-row" style={{ gap: 4, flexWrap: 'wrap', marginBottom: 6 }}>
            {(
              [
                ['ALL_SIGNALS', 'ALL SIGNALS'],
                ['OSCILLATORY', 'OSCILLATORY'],
                ['LEGACY_FIELD', 'LEGACY FIELD'],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                style={{ opacity: signalFilter === id ? 1 : 0.65 }}
                onClick={() => setSignalFilter(id)}
              >
                {label}
              </button>
            ))}
          </div>
        ) : null}
        <div className="toolbar-row" style={{ gap: 4, flexWrap: 'wrap', marginBottom: 6 }}>
          {(['ALL AGENTS', 'AGENT_0', 'AGENT_1'] as const).map((a) => (
            <button
              key={a}
              type="button"
              className={agentFilter === a ? 'active' : ''}
              onClick={() => setAgentFilter(a)}
            >
              {a}
            </button>
          ))}
        </div>
        <div className="subtle">
          Bounded structured timeline · {recent.length} cards · not full scientific history
        </div>
        <div className="event-list observe-v2-events" style={{ maxHeight: 280 }}>
          {recent.length ? (
            recent
              .slice()
              .reverse()
              .map((ev, i) => (
                <EventRow
                  key={`${ev.raw_type}-${ev.tick_start}-${ev.tick_end}-${i}`}
                  ev={ev}
                  onClick={() =>
                    onSelectEvent?.({
                      type: ev.raw_type,
                      tick: ev.tick_end,
                      agent_id: ev.agent_id,
                    })
                  }
                />
              ))
          ) : (
            <div className="na">NO RECENT EVENTS IN WINDOW</div>
          )}
        </div>
      </section>
      ) : null}

      {showRawBlock ? (
      <section className="observe-v2-section">
        <div className="observe-v2-section-head">
          <h4>RAW EVIDENCE</h4>
          <button type="button" onClick={() => setShowRaw((v) => !v)}>
            {showRaw ? 'HIDE RAW FRAMES' : 'SHOW RAW FRAMES'}
          </button>
        </div>
        <div className="subtle">
          Exact frames/events for debugging · not the default presentation · timeline rows{' '}
          {(timeline || []).length}
        </div>
        {showRaw ? (
          <div className="observe-v2-raw">{rawEvidenceSlot || <div className="na">No raw slot</div>}</div>
        ) : (
          <div className="na">Raw evidence collapsed — open to inspect exact tick cards.</div>
        )}
      </section>
      ) : null}
    </div>
  );
}
