/** Experiment preflight — CONFIGURED vs RUNTIME vs AVAILABLE. */

type Row = {
  mechanism?: string;
  configured?: boolean;
  runtime?: boolean;
  available?: boolean | null;
  status?: string;
  radius?: number | null;
  configured_radius?: number | null;
  runtime_radius?: number | null;
  provenance?: string;
};

type Props = {
  integrity?: {
    ready?: boolean;
    preflight_status?: string;
    fingerprint?: string | null;
    mismatch_n?: number;
    rows?: Row[];
    preflight?: {
      status?: string;
      rows?: Row[];
      mismatches?: Row[];
      resolved_fingerprint?: string;
    };
  } | null;
};

function flag(v: boolean | null | undefined) {
  if (v === null || v === undefined) return '—';
  return v ? 'ON' : 'OFF';
}

const LABELS: Record<string, string> = {
  physical_near_field_vision: 'Physical Vision',
  illumination_cycle: 'Illumination',
  physical_body_optical_response: 'Body Optical',
  articulated_head: 'Articulated Head',
  physical_vestibular_sensing: 'Vestibular',
  neck_proprioception: 'Neck Proprioception',
  physical_push: 'PUSH',
  experimental_physical_signal: 'Signals (legacy FIELD)',
  oscillatory_signaling: 'Oscillatory Signaling',
  resource_ecology_A: 'Resource Ecology A',
  resource_ecology_B: 'Resource Ecology B',
  spatiotemporal_climate_ecology: 'Climate Ecology',
  terrain_geography: 'Terrain',
  ambient_physical_dynamics: 'Ambient Dynamics',
  cognition: 'Cognition',
};

export function MechanismPreflightPanel({ integrity }: Props) {
  const pf = integrity?.preflight || integrity;
  const status = String(
    integrity?.preflight_status || (pf as any)?.status || 'UNKNOWN',
  ).toUpperCase();
  const rows: Row[] = (integrity?.rows || (pf as any)?.rows || []) as Row[];
  const ready = status === 'READY' || !!integrity?.ready;
  const fp = integrity?.fingerprint || (pf as any)?.resolved_fingerprint;

  const show = [
    'physical_near_field_vision',
    'articulated_head',
    'physical_vestibular_sensing',
    'neck_proprioception',
    'physical_push',
    'experimental_physical_signal',
    'oscillatory_signaling',
    'resource_ecology_A',
    'resource_ecology_B',
    'spatiotemporal_climate_ecology',
    'terrain_geography',
    'ambient_physical_dynamics',
    'illumination_cycle',
    'cognition',
  ];
  const byId = Object.fromEntries(rows.map((r) => [r.mechanism, r]));

  return (
    <div className="panel science-card" style={{ marginTop: 8 }}>
      <h3>EXPERIMENT PREFLIGHT</h3>
      <div className="metric">
        <span>Status</span>
        <strong style={{ color: ready ? undefined : '#b00020' }}>
          {ready ? 'READY' : status || 'FAILED'}
        </strong>
      </div>
      {fp ? (
        <div className="metric">
          <span>Config fingerprint</span>
          <strong className="mono">{fp}</strong>
        </div>
      ) : null}
      {!ready ? (
        <div className="pending-banner">
          CONFIGURATION MISMATCH — scientific run blocked until CONFIGURED and RUNTIME agree
        </div>
      ) : null}
      <div className="subtle" style={{ marginTop: 6 }}>
        CONFIGURED = requested · RUNTIME = verified authority · AVAILABLE = interface exists (zeros are valid)
      </div>
      <div style={{ marginTop: 8, display: 'grid', gap: 4 }}>
        {show.map((id) => {
          const r = byId[id];
          if (!r) return null;
          const bad = r.status && r.status !== 'READY';
          return (
            <div
              key={id}
              className="metric"
              style={{
                fontSize: 12,
                background: bad ? 'rgba(176,0,32,0.08)' : undefined,
                padding: '2px 4px',
              }}
            >
              <span>{LABELS[id] || id}</span>
              <strong>
                CONFIG {flag(r.configured)} · RUNTIME {flag(r.runtime)}
                {r.configured ? ` · AVAIL ${flag(!!r.available)}` : ''}
                {id === 'physical_near_field_vision' ? (
                  <>
                    {' · '}cfg R{r.configured_radius ?? r.radius ?? '—'}
                    {' / '}rt R{r.runtime_radius ?? r.radius ?? '—'}
                  </>
                ) : null}
                {' · '}
                {bad ? 'MISMATCH' : 'READY'}
              </strong>
            </div>
          );
        })}
      </div>
    </div>
  );
}
