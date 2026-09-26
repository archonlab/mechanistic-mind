/** PSC auto-ON schedule — Experiment / Predictive. Not Tiktaalik Eye. */

import { useCallback, useEffect, useState } from 'react';

const PRESETS = [
  { id: 'MANUAL', label: 'MANUAL' },
  { id: '0', label: '0' },
  { id: '1000', label: '1000' },
  { id: '5000', label: '5000' },
] as const;

type Status = {
  psc?: string;
  schedule?: string | number;
  auto_on_tick?: number | null;
  activated_tick?: number | null;
  history_preserved?: boolean;
  mode?: string;
};

export function PscOffTicksControl() {
  const [st, setSt] = useState<Status>({});
  const [custom, setCustom] = useState('2000');

  const load = useCallback(async () => {
    try {
      const r = await fetch('/api/config/psc-off-ticks');
      setSt(await r.json());
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function apply(value: string) {
    await fetch('/api/config/psc-off-ticks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ value }),
    });
    await load();
  }

  const psc = String(st.psc || 'OFF');
  const sched = st.schedule;
  return (
    <div className="panel science-card">
      <div className="section-label">PSC OFF TICKS</div>
      <div className="subtle">
        MANUAL = experimenter toggle. Numeric = deterministic ON at tick ≥ N without history reset.
      </div>
      <div className="metric">
        <span>PSC</span>
        <strong>{psc}</strong>
      </div>
      {psc === 'OFF' && sched !== 'MANUAL' && sched != null ? (
        <div className="metric">
          <span>AUTO-ON</span>
          <strong>tick {String(sched)}</strong>
        </div>
      ) : null}
      {st.activated_tick != null ? (
        <>
          <div className="metric">
            <span>ACTIVATED</span>
            <strong>tick {String(st.activated_tick)}</strong>
          </div>
          <div className="metric">
            <span>HISTORY</span>
            <strong>{st.history_preserved ? 'PRESERVED' : '—'}</strong>
          </div>
        </>
      ) : null}
      <div className="metric" style={{ flexWrap: 'wrap', gap: 4 }}>
        {PRESETS.map((p) => (
          <button
            key={p.id}
            type="button"
            className={String(sched) === p.id || (p.id === 'MANUAL' && sched === 'MANUAL') ? 'active' : ''}
            onClick={() => void apply(p.id)}
          >
            {p.label}
          </button>
        ))}
      </div>
      <div className="metric" style={{ gap: 6 }}>
        <span>CUSTOM</span>
        <input
          style={{ width: 80 }}
          value={custom}
          onChange={(e) => setCustom(e.target.value)}
        />
        <button type="button" onClick={() => void apply(custom)}>APPLY</button>
      </div>
    </div>
  );
}
