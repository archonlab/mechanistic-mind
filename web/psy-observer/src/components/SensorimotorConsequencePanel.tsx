import { useEffect, useState } from 'react';

type Pred = {
  motor?: string;
  status?: string;
  support?: number;
  predicted_sensory_delta?: Record<string, number> | null;
};

type AgentRow = {
  slot?: number;
  agent_id?: string;
  diagnostic?: Record<string, any>;
  candidate_predictions?: Pred[];
  withheld_from_psc?: boolean;
  selected_action?: string;
};

export function SensorimotorConsequencePanel() {
  const [data, setData] = useState<{ agents?: AgentRow[] } | null>(null);

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const r = await fetch('/api/diagnostics/sensorimotor-consequence');
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

  const agents = data?.agents || [];
  return (
    <div className="panel">
      <h3>CURRENT MM — SENSORIMOTOR CONSEQUENCES</h3>
      <div className="subtle">
        Action-conditioned accessible ΔS predictions. No good/bad/target labels.
      </div>
      {!agents.length && <div className="na">NOT AVAILABLE</div>}
      {agents.map((a, i) => {
        const d = a.diagnostic || {};
        return (
          <div key={i} className="block" style={{ marginTop: 8 }}>
            <div className="metric">
              <span>Agent</span>
              <strong>{a.agent_id ?? `slot ${a.slot ?? i}`}</strong>
            </div>
            <div className="metric"><span>Enabled</span><strong>{String(d.enabled)}</strong></div>
            <div className="metric"><span>Occupancy</span><strong>{d.occupancy}/{d.capacity}</strong></div>
            <div className="metric"><span>Updates / queries</span><strong>{d.updates} / {d.queries}</strong></div>
            <div className="metric"><span>Matched / unknown</span><strong>{d.matched_queries} / {d.unknown_queries}</strong></div>
            <div className="metric"><span>Mean support</span><strong>{d.mean_support != null ? Number(d.mean_support).toFixed(2) : '—'}</strong></div>
            <div className="metric"><span>Withheld from PSC</span><strong>{String(!!a.withheld_from_psc)}</strong></div>
            <div className="metric"><span>Selected</span><strong>{a.selected_action ?? '—'}</strong></div>
            <div style={{ marginTop: 6 }}>
              <div className="subtle">Candidate predictions</div>
              {(a.candidate_predictions || []).length === 0 && <div className="na">none</div>}
              {(a.candidate_predictions || []).map((p, j) => (
                <div key={j} className="subtle" style={{ fontFamily: 'monospace', fontSize: 12 }}>
                  {p.motor} status={p.status} support={p.support}
                  {p.predicted_sensory_delta
                    ? ' Δ ' + Object.entries(p.predicted_sensory_delta)
                        .filter(([, v]) => Math.abs(Number(v)) > 0.01)
                        .map(([k, v]) => `${k}:${Number(v).toFixed(2)}`)
                        .join(' ')
                    : ''}
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
