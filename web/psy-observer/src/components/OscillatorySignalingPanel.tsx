/** Observer — Oscillatory signaling (WORLD GT vs AGENT-ACCESSIBLE). */

type Props = {
  physical?: any;
  agentObservation?: Record<string, number> | null;
  mechanisms?: any[];
  onToggleMechanism?: (m: any) => void;
  cognitionEnabled?: boolean;
};

function KV({ name, value }: { name: string; value: any }) {
  const missing = value === undefined || value === null || value === '';
  return (
    <div className="metric">
      <span>{name}</span>
      <strong>{missing ? 'NOT AVAILABLE' : String(value)}</strong>
    </div>
  );
}

function fmt(v: any, digits = 4) {
  if (v === undefined || v === null || Number.isNaN(Number(v))) return null;
  return Number(v).toFixed(digits);
}

export function OscillatorySignalingPanel({
  physical,
  agentObservation,
  mechanisms,
  onToggleMechanism,
  cognitionEnabled = true,
}: Props) {
  const osc = physical?.oscillatory_signaling;
  const cogn = agentObservation || {};
  const mech = (mechanisms || []).find((m: any) => m.id === 'oscillatory_signaling');
  const gt = osc?.WORLD_GT || {};
  const agent = osc?.AGENT_ACCESSIBLE || {};
  const channels = (Array.isArray(agent.channels) ? agent.channels : []) as string[];

  return (
    <div className="panel science-card" style={{ marginTop: 12 }}>
      <h3>OSCILLATORY SIGNALING</h3>
      <div className="subtle">
        Physical banded emission/reception · not language · not messages · no source identity
      </div>

      <div className="section-label" style={{ marginTop: 8 }}>Mechanism (LIVE)</div>
      {mech ? (
        <div className="metric" style={{ alignItems: 'center' }}>
          <span>Physical oscillatory signaling</span>
          <button type="button" onClick={() => onToggleMechanism?.(mech)}>
            {mech.enabled ? 'ON' : 'OFF'}
          </button>
        </div>
      ) : (
        <div className="na">Oscillatory mechanism not in registry</div>
      )}

      <div className="section-label" style={{ marginTop: 10 }}>A. WORLD / BODY GROUND TRUTH</div>
      <KV name="Emit active" value={gt.emit_active == null ? null : gt.emit_active ? 'YES' : 'NO'} />
      <KV name="Frequency" value={fmt(gt.frequency)} />
      <KV name="Amplitude" value={fmt(gt.amplitude)} />
      <KV name="Remaining ticks" value={gt.remaining} />
      <KV name="freq_u / amp_u" value={
        gt.osc_freq_u == null ? null : `${fmt(gt.osc_freq_u)} / ${fmt(gt.osc_amp_u)}`
      } />
      <KV name="Receptor L xy" value={
        Array.isArray(gt.receptor_left_xy) ? gt.receptor_left_xy.map((x: number) => Number(x).toFixed(2)).join(', ') : null
      } />
      <KV name="Receptor R xy" value={
        Array.isArray(gt.receptor_right_xy) ? gt.receptor_right_xy.map((x: number) => Number(x).toFixed(2)).join(', ') : null
      } />
      <KV name="Finite propagation" value={gt.finite_propagation || 'NOT_IMPLEMENTED'} />

      <div className="section-label" style={{ marginTop: 10 }}>B. AGENT-ACCESSIBLE</div>
      <KV name="Status" value={cognitionEnabled ? (agent.status || 'NOT AVAILABLE') : 'NOT AVAILABLE'} />
      {(cognitionEnabled ? channels : []).slice(0, 12).map((ch: string) => (
        <KV
          key={ch}
          name={ch}
          value={fmt(cogn[ch] ?? agent[ch])}
        />
      ))}
      {!cognitionEnabled ? (
        <div className="na">Cognition-free body: agent-accessible osc channels NOT AVAILABLE</div>
      ) : null}
    </div>
  );
}
