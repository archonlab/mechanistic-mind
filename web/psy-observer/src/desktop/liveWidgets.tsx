/** Compact live near-field vision bars from exo_0..exo_2 (agent-accessible). */

import { useState } from 'react';

export type VisionBarsProps = {
  observation?: Record<string, number> | null;
  /** Mechanism / package authority — independent of whether current exo is zero. */
  visionEnabled?: boolean | null;
  agentLabel?: string;
};

export function VisionBars({
  observation,
  visionEnabled,
  agentLabel,
}: VisionBarsProps) {
  const hasKeys =
    !!observation
    && ('exo_0' in observation || 'exo_1' in observation || 'exo_2' in observation);
  const authorityOn =
    visionEnabled === true
    || (visionEnabled == null && hasKeys);
  const exo0 = Number(observation?.exo_0 ?? 0);
  const exo1 = Number(observation?.exo_1 ?? 0);
  const exo2 = Number(observation?.exo_2 ?? 0);
  const max = Math.max(exo0, exo1, exo2, 1e-9);
  const bar = (v: number) => {
    const n = Math.max(0, Math.min(8, Math.round((v / max) * 8)));
    return '█'.repeat(n) + '░'.repeat(8 - n);
  };
  const prefix = agentLabel ? `${agentLabel} · ` : '';
  if (!authorityOn) {
    return (
      <div className="vision-bars na">
        {prefix}VISION · OFF / no exo_*
      </div>
    );
  }
  // Vision ON with zeros is physically different from vision OFF.
  return (
    <div className="vision-bars" title="Agent-accessible exo fragments — not World GT">
      <div className="vision-label">
        {prefix}VISION ON <span className="info-kind kind-AGENT_ACCESSIBLE">AGENT</span>
      </div>
      <div className="vision-row"><span>L</span><code>{bar(exo0)}</code><span className="vnum">{exo0.toFixed(3)}</span></div>
      <div className="vision-row"><span>F</span><code>{bar(exo1)}</code><span className="vnum">{exo1.toFixed(3)}</span></div>
      <div className="vision-row"><span>R</span><code>{bar(exo2)}</code><span className="vnum">{exo2.toFixed(3)}</span></div>
      <div className="subtle">exo_0={exo0.toFixed(3)} exo_1={exo1.toFixed(3)} exo_2={exo2.toFixed(3)}</div>
    </div>
  );
}

/** Compact physical signal sequence from recent events (not language). Legacy FIELD only. */
export function SignalSequence({ events }: { events: any[] }) {
  const recent = (events || []).slice(-24);
  const glyph = (e: any) => {
    const t = String(e?.type || e?.kind || '');
    const ev = e?.evidence || {};
    if (t.includes('SIGNAL_EMITTED')) {
      const ch = String(ev.channel || e.channel || '');
      return ch.includes('B') ? '■' : '▲';
    }
    if (t.includes('SIGNAL_RECEIVED')) return '·';
    return '';
  };
  const fieldA = recent.map((e) => {
    const t = String(e?.type || '');
    const ch = String(e?.evidence?.channel || e?.channel || '');
    if (t.includes('SIGNAL_EMITTED') && ch.includes('A')) return '▲';
    return '·';
  }).join('');
  const fieldB = recent.map((e) => {
    const t = String(e?.type || '');
    const ch = String(e?.evidence?.channel || e?.channel || '');
    if (t.includes('SIGNAL_EMITTED') && ch.includes('B')) return '■';
    return '·';
  }).join('');
  const actions = recent
    .filter((e) => String(e?.type || '').includes('ACTION') || e?.selected_action)
    .slice(-8)
    .map((e) => e.selected_action || e?.evidence?.action || glyph(e) || '·')
    .join(' ');
  return (
    <div className="signal-seq">
      <div className="subtle">
        LEGACY FIELD SEQUENCE <span className="info-kind kind-WORLD_GT">LIVE / HISTORICAL EVENTS</span>
      </div>
      <div className="seq-row"><span>FIELD_A</span><code>{fieldA || '········'}</code></div>
      <div className="seq-row"><span>FIELD_B</span><code>{fieldB || '········'}</code></div>
      {actions ? <div className="seq-row"><span>ACTION</span><code className="actions">{actions}</code></div> : null}
      <div className="subtle">Physical signals ≠ messages. Reception ≠ interpretation.</div>
    </div>
  );
}

type SignalsView = 'ALL' | 'OSCILLATORY' | 'LEGACY_FIELD';

function fmtNum(v: unknown, digits = 4): string {
  if (v === undefined || v === null || Number.isNaN(Number(v))) return 'NOT AVAILABLE';
  return Number(v).toFixed(digits);
}

/** Band rows: one band per line (avoids cramped overlapping strings). */
function BandRows({
  obs,
  prefix,
  label,
}: {
  obs: Record<string, number> | null | undefined;
  prefix: string;
  label: string;
}) {
  if (!obs) {
    return (
      <div className="signal-band-block">
        <div className="metric"><span>{label}</span><strong>NOT AVAILABLE</strong></div>
      </div>
    );
  }
  const keys = Object.keys(obs).filter((k) => k.startsWith(prefix)).sort();
  if (!keys.length) {
    return (
      <div className="signal-band-block">
        <div className="metric"><span>{label}</span><strong>NO EVIDENCE YET</strong></div>
      </div>
    );
  }
  return (
    <div className="signal-band-block">
      <div className="subtle">{label}</div>
      {keys.map((k) => (
        <div key={k} className="signal-band-row">
          <span className="band-id">{k.replace(prefix, 'b')}</span>
          <code className="band-val">{fmtNum(obs[k], 3)}</code>
        </div>
      ))}
    </div>
  );
}

/** Mechanism-aware SIGNALS task: OSC + legacy FIELD, not FIELD-only. */
export function MechanismAwareSignals({
  events,
  physical,
  mechanisms,
  agentObservation,
  attribution,
}: {
  events: any[];
  physical?: any;
  mechanisms?: any[];
  agentObservation?: Record<string, number> | null;
  /** Observer GT only — SELF / CROSS / MIXED when present. */
  attribution?: string | null;
}) {
  const [view, setView] = useState<SignalsView>('ALL');
  const oscMech = (mechanisms || []).find((m: any) => m.id === 'oscillatory_signaling');
  const oscEnabled =
    oscMech?.enabled === true
    || physical?.oscillatory_signaling?.enabled === true;
  const gt = physical?.oscillatory_signaling?.WORLD_GT || {};
  const agent = physical?.oscillatory_signaling?.AGENT_ACCESSIBLE || {};
  const emitActive = gt.emit_active === true;
  const recvObs = agentObservation || agent;
  const hasOscEvidence =
    emitActive
    || Number(gt.amplitude || 0) > 0
    || Number(gt.remaining || 0) > 0
    || Object.keys(recvObs || {}).some((k) => k.startsWith('osc_l_') || k.startsWith('osc_r_'));
  const gtContrib = attribution
    ? String(attribution).toUpperCase()
    : 'NOT AVAILABLE';

  return (
    <div className="signal-seq signal-live-panel">
      <div className="subtle">
        LIVE SIGNAL MONITOR · physical only · not communication
        {' '}
        <span className="info-kind kind-WORLD_GT">LIVE RUNTIME</span>
      </div>
      <div className="signal-flow-legend subtle">
        AGENT → EMITS → PHYSICAL FIELD → RECEIVER → OBSERVED INPUT
      </div>
      <div className="toolbar-row" style={{ marginTop: 6, gap: 6, flexWrap: 'wrap' }}>
        {([
          ['ALL', 'ALL SIGNALS'],
          ['OSCILLATORY', 'OSCILLATORY'],
          ['LEGACY_FIELD', 'LEGACY FIELD'],
        ] as const).map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => setView(id)}
            style={{ opacity: view === id ? 1 : 0.65 }}
          >
            {label}
          </button>
        ))}
      </div>

      {(view === 'ALL' || view === 'OSCILLATORY') ? (
        <div className="signal-section" style={{ marginTop: 8 }}>
          <div className="section-label">
            OSCILLATORY
            {' '}
            <span className="info-kind kind-WORLD_GT">LIVE</span>
            {' '}
            <span className="info-kind kind-AGENT_ACCESSIBLE">AGENT RECEPTION</span>
          </div>
          {!oscEnabled ? (
            <div className="na">Mechanism OFF / not configured</div>
          ) : !hasOscEvidence ? (
            <div className="na">NO EVIDENCE YET</div>
          ) : (
            <>
              <div className="signal-flow-block">
                <div className="signal-flow-step">1 · EMITS</div>
                <div className="metric"><span>emission</span><strong>{emitActive ? 'active' : 'inactive'}</strong></div>
                <div className="metric">
                  <span>frequency <span className="info-kind kind-WORLD_GT">GT</span></span>
                  <strong>{fmtNum(gt.frequency)}</strong>
                </div>
                <div className="metric">
                  <span>amplitude <span className="info-kind kind-WORLD_GT">GT</span></span>
                  <strong>{fmtNum(gt.amplitude)}</strong>
                </div>
              </div>
              <div className="signal-flow-block">
                <div className="signal-flow-step">2 · RECEIVER (agent-accessible bands)</div>
                <BandRows obs={recvObs} prefix="osc_l_" label="L bands" />
                <BandRows obs={recvObs} prefix="osc_r_" label="R bands" />
              </div>
              <div className="signal-flow-block">
                <div className="signal-flow-step">3 · OBSERVER GT attribution</div>
                <div className="metric">
                  <span>contribution <span className="info-kind kind-WORLD_GT">GT ONLY</span></span>
                  <strong>{gtContrib}</strong>
                </div>
                <div className="subtle">SELF/CROSS/MIXED are Observer GT — never cognition labels. Not messages.</div>
              </div>
            </>
          )}
        </div>
      ) : null}

      {(view === 'ALL' || view === 'LEGACY_FIELD') ? (
        <div className="signal-section" style={{ marginTop: 10 }}>
          <div className="section-label">
            LEGACY FIELD
            {' '}
            <span className="info-kind kind-WORLD_GT">LIVE / EVENTS</span>
          </div>
          <SignalSequence events={events} />
        </div>
      ) : null}
    </div>
  );
}
