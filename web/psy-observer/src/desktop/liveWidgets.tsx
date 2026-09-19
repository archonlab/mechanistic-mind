/** Compact live near-field vision bars from exo_0..exo_2 (agent-accessible). */

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

/** Compact physical signal sequence from recent events (not language). */
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
      <div className="subtle">OBSERVED PHYSICAL SEQUENCE</div>
      <div className="seq-row"><span>FIELD_A</span><code>{fieldA || '········'}</code></div>
      <div className="seq-row"><span>FIELD_B</span><code>{fieldB || '········'}</code></div>
      {actions ? <div className="seq-row"><span>ACTION</span><code className="actions">{actions}</code></div> : null}
      <div className="subtle">Physical signals ≠ messages. Reception ≠ interpretation.</div>
    </div>
  );
}
