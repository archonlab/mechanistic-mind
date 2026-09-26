import { useEffect, useState } from 'react';

type Cand = {
  motor?: string;
  status?: string;
  support?: number;
  signal_predicted_delta?: Record<string, number> | null;
  osc_predicted_delta?: Record<string, number> | null;
  L_prime?: number[] | null;
  R_prime?: number[] | null;
  delta_asymmetry_derived?: number | null;
};

type Payload = {
  status?: string;
  reason?: string;
  tick?: number;
  agent_id?: string;
  note?: string;
  bilateral_smc?: { status?: string; enabled?: boolean; predictions_available?: boolean };
  signal_input?: {
    FIELD_A?: number;
    FIELD_B?: number;
    L_bands?: number[];
    R_bands?: number[];
    derived_display_only?: {
      TOTAL_L?: number;
      TOTAL_R?: number;
      ASYMMETRY?: number;
      label?: string;
    };
  };
  recent_accessible_signal?: { points?: { tick?: number; FIELD_A?: number; FIELD_B?: number }[] };
  embodied_prediction?: {
    sensory_coverage?: Record<string, { modeled?: number; total?: number }>;
    allowlist_n?: number;
    smc_action_signature?: string;
    warning?: string | null;
    motor?: Record<string, unknown>;
  };
  psc?: {
    enabled?: boolean;
    selected_action?: string;
    status_line?: string;
    signal_candidates?: Cand[];
    hss_meta?: Record<string, unknown> | null;
  };
  psc_motor_resolution?: string;
  motor_resolution_production?: {
    mode?: string;
    experimental?: boolean;
    label?: string;
    candidate_count?: number;
    selected_composite?: string | null;
    selection_source?: string;
    match_provenance?: string;
  };
  motor_resolution_shadow?: {
    status?: string;
    label?: string;
    banner?: string | null;
    classification?: string;
    production?: { selected_loco?: string; realized_composite?: string };
    full_composite_shadow?: { candidate_count?: number; winning_composite?: string };
    adaptive_shadow?: { refined?: boolean; candidate_count?: number };
  };
};

function miniBars(vals: number[] | undefined | null, color: string) {
  const v = vals || [];
  if (!v.length) return <span className="subtle">—</span>;
  return (
    <span style={{ display: 'inline-flex', gap: 1, alignItems: 'flex-end', height: 16, verticalAlign: 'middle' }}>
      {v.map((x, i) => (
        <span
          key={i}
          style={{
            display: 'inline-block',
            width: 4,
            height: Math.max(1, Math.min(16, Math.round(Math.abs(x) * 16))),
            background: color,
            opacity: 0.8,
          }}
        />
      ))}
    </span>
  );
}

export function SignalSensorimotorPanel() {
  const [data, setData] = useState<Payload | null>(null);
  const [includeShadow, setIncludeShadow] = useState(false);

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      if (typeof document !== 'undefined' && document.visibilityState === 'hidden') return;
      try {
        const q = includeShadow ? '?include_shadow=true' : '';
        const r = await fetch(`/api/diagnostics/signal-sensorimotor${q}`);
        if (!r.ok) return;
        const j = await r.json();
        if (alive) setData(j);
      } catch {
        /* ignore */
      }
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [includeShadow]);

  if (data?.status === 'DEFERRED') {
    return (
      <div className="panel">
        <h3>SIGNAL → PREDICTION → PSC</h3>
        <div className="subtle">Unsubscribed (MINIMAL / panel off) — scientific evidence still recorded.</div>
      </div>
    );
  }

  const sig = data?.signal_input;
  const der = sig?.derived_display_only;
  const psc = data?.psc;
  const bil = data?.bilateral_smc;
  const emb = data?.embodied_prediction;
  const cands = psc?.signal_candidates || [];
  const selected = cands.find((c) => psc?.selected_action && String(c.motor || '').includes(String(psc.selected_action)));

  return (
    <div className="panel">
      <h3>SIGNAL → PREDICTION → PSC</h3>
      <div className="subtle">
        Agent {String(data?.agent_id ?? '—')} · t{data?.tick ?? '—'}
      </div>
      <label className="check">
        <input type="checkbox" checked={includeShadow} onChange={e => setIncludeShadow(e.target.checked)} />
        Compute PSC shadow (analysis only — does not affect agent)
      </label>

      <div className="metric">
        <span>BILATERAL SMC</span>
        <strong>{bil?.status || 'NOT AVAILABLE'}</strong>
      </div>
      <div className="metric">
        <span>Chain</span>
        <strong>{psc?.status_line || '—'}</strong>
      </div>

      {emb && (
        <>
          <h4>EMBODIED PREDICTION</h4>
          <div className="subtle">allowlist {emb.allowlist_n ?? '—'} channels</div>
          {emb.warning && <div className="subtle">⚠ {emb.warning}</div>}
          <div className="subtle">SMC ACTION SIGNATURE: {emb.smc_action_signature || '—'}</div>
          {Object.entries(emb.sensory_coverage || {}).map(([fam, v]) => (
            <div key={fam} className="metric">
              <span>{fam}</span>
              <strong>{v.modeled}/{v.total}</strong>
            </div>
          ))}
          <h4>MOTOR RESOLUTION</h4>
          <div className="metric"><span>PRODUCTION MODE</span>
            <strong>{(data.motor_resolution_production?.mode || data.psc_motor_resolution || 'LOCO_FACTORIZED').toString().replace(/_/g, ' ')}</strong>
          </div>
          {(data.motor_resolution_production?.experimental || data.psc_motor_resolution === 'OBSERVED_COMPOSITE') && (
            <div className="subtle">OBSERVED COMPOSITE · EXPERIMENTAL</div>
          )}
          {data.motor_resolution_production?.selected_composite && (
            <div className="subtle">selected {data.motor_resolution_production.selected_composite} n={data.motor_resolution_production.candidate_count ?? '—'}</div>
          )}
          {data.motor_resolution_production?.selection_source && (
            <div className="subtle">source {data.motor_resolution_production.selection_source}</div>
          )}
          {data?.motor_resolution_shadow && (
            <>
              <div className="subtle">SHADOW: {data.motor_resolution_shadow.label || 'ANALYSIS ONLY — DOES NOT AFFECT AGENT'}</div>
              {data.motor_resolution_shadow.status === 'DEFERRED' ? (
                <div className="subtle">DEFERRED (MINIMAL)</div>
              ) : (
                <>
                  {data.motor_resolution_shadow.banner && (
                    <div className="subtle"><strong>{data.motor_resolution_shadow.banner}</strong></div>
                  )}
                  <div className="metric"><span>PRODUCTION LOCO_ONLY</span>
                    <strong>{data.motor_resolution_shadow.production?.selected_loco || '—'}</strong></div>
                  <div className="subtle">realized {data.motor_resolution_shadow.production?.realized_composite || '—'}</div>
                  <div className="metric"><span>FULL COMPOSITE SHADOW</span>
                    <strong>n={data.motor_resolution_shadow.full_composite_shadow?.candidate_count ?? '—'}</strong></div>
                  <div className="subtle">win {data.motor_resolution_shadow.full_composite_shadow?.winning_composite || '—'}</div>
                  <div className="metric"><span>ADAPTIVE SHADOW</span>
                    <strong>{data.motor_resolution_shadow.adaptive_shadow?.refined ? 'REFINED' : 'COARSE'} n={data.motor_resolution_shadow.adaptive_shadow?.candidate_count ?? '—'}</strong></div>
                  <div className="subtle">class {data.motor_resolution_shadow.classification || '—'}</div>
                </>
              )}
            </>
          )}
        </>
      )}

      <h4>SIGNAL INPUT</h4>
      <div className="metric">
        <span>FIELD_A / FIELD_B</span>
        <strong>
          {sig?.FIELD_A != null ? Number(sig.FIELD_A).toFixed(4) : '—'} /{' '}
          {sig?.FIELD_B != null ? Number(sig.FIELD_B).toFixed(4) : '—'}
        </strong>
      </div>
      <div className="subtle">LEFT RECEIVER {miniBars(sig?.L_bands, '#6af')}</div>
      <div className="subtle">RIGHT RECEIVER {miniBars(sig?.R_bands, '#fa6')}</div>
      <div className="subtle" style={{ marginTop: 4 }}>
        {der?.label}
      </div>
      <div className="metric">
        <span>ASYMMETRY (derived)</span>
        <strong>{der?.ASYMMETRY != null ? Number(der.ASYMMETRY).toFixed(3) : '—'}</strong>
      </div>

      <h4>PREDICTED CONSEQUENCE (selected)</h4>
      {selected?.L_prime ? (
        <>
          <div className="subtle">NOW L {miniBars(sig?.L_bands, '#6af')} → L′ {miniBars(selected.L_prime, '#6af')}</div>
          <div className="subtle">NOW R {miniBars(sig?.R_bands, '#fa6')} → R′ {miniBars(selected.R_prime, '#fa6')}</div>
          <div className="subtle">
            ΔASYM {selected.delta_asymmetry_derived != null ? Number(selected.delta_asymmetry_derived).toFixed(3) : '—'}{' '}
            [DERIVED]
          </div>
        </>
      ) : (
        <div className="subtle">No bilateral prediction for selected motor yet</div>
      )}

      <h4>PSC CANDIDATES</h4>
      {!psc?.enabled && <div className="subtle">PSC OFF — accumulating sensorimotor history</div>}
      {cands.map((c, i) => {
        const isSel = psc?.selected_action && String(c.motor || '').includes(String(psc.selected_action));
        const fa = c.signal_predicted_delta?.['local.FIELD_A'];
        return (
          <div key={i} className="block" style={{ marginTop: 6, outline: isSel ? '1px solid var(--accent,#6af)' : undefined }}>
            <div>
              <strong>{c.motor || '—'}</strong>
              {isSel ? ' · SELECTED' : ''}
            </div>
            <div className="subtle">
              FIELD_A {fa != null ? (fa >= 0 ? '+' : '') + Number(fa).toFixed(3) : 'NOT_AVAILABLE'}
            </div>
            <div className="subtle">L′ {miniBars(c.L_prime, '#6af')} R′ {miniBars(c.R_prime, '#fa6')}</div>
            <div className="subtle">
              ΔASYM{' '}
              {c.delta_asymmetry_derived != null
                ? (c.delta_asymmetry_derived >= 0 ? '+' : '') + Number(c.delta_asymmetry_derived).toFixed(3)
                : '—'}{' '}
              [DERIVED] · status={String(c.status)} support={String(c.support)}
            </div>
          </div>
        );
      })}
      {psc?.hss_meta && (
        <div className="subtle" style={{ marginTop: 6 }}>
          HSS enabled={String(psc.hss_meta.enabled)} withheld={String(psc.hss_meta.withheld_from_psc)} CFΔ=
          {String(psc.hss_meta.selection_differs_from_withheld_cf)}
        </div>
      )}
    </div>
  );
}
