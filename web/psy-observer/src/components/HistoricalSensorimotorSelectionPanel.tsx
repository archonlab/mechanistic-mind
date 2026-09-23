import { useEffect, useState } from 'react';

type AgentRow = {
  slot?: number;
  agent_id?: string | number;
  bridge_enabled?: boolean;
  psc_enabled?: boolean;
  ui_state?: string;
  last_bridge_meta?: Record<string, unknown> | null;
};

type Payload = {
  ui_state?: string;
  bridge_enabled?: boolean;
  psc_enabled?: boolean;
  experience_ticks?: number | null;
  psc_enabled_after_ticks?: number | null;
  agents?: AgentRow[];
};

export function HistoricalSensorimotorSelectionPanel() {
  const [data, setData] = useState<Payload | null>(null);

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const r = await fetch('/api/diagnostics/historical-sensorimotor-selection');
        if (!r.ok) return;
        const j = await r.json();
        if (alive) setData(j);
      } catch {
        /* ignore */
      }
    };
    tick();
    const id = setInterval(() => {
      if (typeof document !== "undefined" && document.visibilityState === "hidden") return;
      tick();
    }, 1000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  const state = data?.ui_state || 'OFF';
  const ticks = data?.experience_ticks;
  const after = data?.psc_enabled_after_ticks;

  return (
    <div className="panel">
      <h3>CURRENT MM — HISTORICAL SENSORIMOTOR SELECTION</h3>
      <div className="subtle">
        Predicted sensory consequences of candidate actions are queried against accumulated history;
        continuation evidence can participate in prospective scenario competition. No reward or goal.
      </div>
      <div className="metric"><span>State</span><strong>{state}</strong></div>
      <div className="metric"><span>Bridge</span><strong>{String(!!data?.bridge_enabled)}</strong></div>
      <div className="metric"><span>PSC</span><strong>{data?.psc_enabled ? 'ON' : 'OFF'}</strong></div>
      {ticks != null && (
        <div className="metric">
          <span>{data?.psc_enabled ? 'Experience ticks' : 'Experience accumulating'}</span>
          <strong>{ticks}</strong>
        </div>
      )}
      {after != null && data?.psc_enabled && (
        <div className="metric"><span>PSC enabled after</span><strong>{after} experience ticks</strong></div>
      )}
      {state === 'READY' && (
        <div className="subtle">History/SMC accumulation continues. Bridge does not change selection while PSC is OFF.</div>
      )}
      {state === 'ACTIVE' && (
        <div className="subtle">O′ historical evidence may participate in PSC competition when eligible.</div>
      )}
      {(data?.agents || []).map((a, i) => (
        <div key={i} className="block" style={{ marginTop: 6 }}>
          <div className="subtle">
            agent {String(a.agent_id ?? a.slot ?? i)} — {a.ui_state}
            {a.last_bridge_meta && a.last_bridge_meta.enabled
              ? ` · hist_match=${String(a.last_bridge_meta.n_history_match ?? '—')}`
                + (a.last_bridge_meta.selection_differs_from_withheld_cf ? ' · CFΔ' : '')
              : ''}
          </div>
        </div>
      ))}
    </div>
  );
}
