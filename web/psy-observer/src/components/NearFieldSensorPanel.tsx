/** Observer Sensors → Vision (PHYSICAL_PERCEPTION_01). Three epistemic levels. */

type Props = {
  physical?: any;
  agentObservation?: Record<string, number> | null;
  mechanisms?: any[];
  onToggleMechanism?: (m: any) => void;
  onSetVisionRadius?: (radius: number) => void;
};

function KV({ name, value }: { name: string; value: any }) {
  return (
    <div className="metric">
      <span>{name}</span>
      <strong>{value === undefined || value === null || value === '' ? '—' : String(value)}</strong>
    </div>
  );
}

const RADIUS_OPTIONS = [
  { radius: 1, label: 'R=1 · max 8 cells' },
  { radius: 2, label: 'R=2 · max 24 cells' },
  { radius: 3, label: 'R=3 · max 48 cells' },
];

export function NearFieldSensorPanel({
  physical,
  agentObservation,
  mechanisms,
  onToggleMechanism,
  onSetVisionRadius,
}: Props) {
  const nf = physical?.near_field_exteroception;
  const visionMech = (mechanisms || []).find((m: any) => m.id === 'physical_near_field_vision');
  const illumMech = (mechanisms || []).find((m: any) => m.id === 'illumination_cycle');
  const cogn = agentObservation || {};
  const exoKeys = ['exo_0', 'exo_1', 'exo_2'];
  const visionOn =
    visionMech?.enabled === true
    || nf?.vision_contributes === true
    || nf?.perception_enabled === true;
  const radius = Number(nf?.vision_radius ?? nf?.radius ?? 1);
  const maxCand = Number(nf?.max_candidates ?? (radius === 2 ? 24 : radius === 3 ? 48 : 8));

  return (
    <div className="panel science-card">
      <h3>VISION</h3>
      <div className="subtle">Physical near-field optical transduction · not semantic vision</div>
      <div className="na">
        ACTIVE_SENSOR_ORIENTATION = {String(nf?.ACTIVE_SENSOR_ORIENTATION || physical?.orientation?.ACTIVE_SENSOR_ORIENTATION || 'NOT_AVAILABLE')}
        {' · '}no LOOK_AT / TRACK / ATTENTION semantics
      </div>
      {(nf?.articulated_head_enabled || physical?.orientation?.articulated_head_enabled) ? (
        <div className="subtle" style={{ marginTop: 4 }}>
          body θ={Number(nf?.body_theta ?? physical?.orientation?.theta ?? 0).toFixed(3)}
          {' · '}head_rel={Number(nf?.head_relative_angle ?? physical?.orientation?.head_relative_angle ?? 0).toFixed(3)}
          {' · '}head_world={Number(nf?.head_world_heading ?? physical?.orientation?.head_world_heading ?? 0).toFixed(3)}
          {' · '}neck_motor={Number(nf?.neck_motor ?? physical?.orientation?.neck_motor ?? 0).toFixed(2)}
        </div>
      ) : null}

      <div className="section-label" style={{ marginTop: 8 }}>Authority (LIVE)</div>
      {visionMech ? (
        <div className="metric" style={{ alignItems: 'center' }}>
          <span>Physical near-field vision</span>
          <button type="button" disabled={!onToggleMechanism} title={!onToggleMechanism ? 'Control not wired' : 'LIVE mutable'} onClick={() => onToggleMechanism?.(visionMech)}>
            {visionMech.enabled ? 'ON' : 'OFF'}
          </button>
        </div>
      ) : (
        <div className="na">Vision mechanism not in registry snapshot</div>
      )}
      {illumMech ? (
        <div className="metric" style={{ alignItems: 'center' }}>
          <span>Illumination cycle</span>
          <button type="button" disabled={!onToggleMechanism} title={!onToggleMechanism ? 'Control not wired' : 'LIVE mutable'} onClick={() => onToggleMechanism?.(illumMech)}>
            {illumMech.enabled ? 'ON' : 'OFF'}
          </button>
        </div>
      ) : null}
      <div className="metric" style={{ alignItems: 'center', flexWrap: 'wrap', gap: 6 }}>
        <span>Vision radius</span>
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
          {RADIUS_OPTIONS.map((opt) => (
            <button
              key={opt.radius}
              type="button"
              disabled={!onSetVisionRadius || !visionOn}
              aria-pressed={radius === opt.radius}
              style={{
                fontWeight: radius === opt.radius ? 700 : 400,
                outline: radius === opt.radius ? '2px solid currentColor' : undefined,
              }}
              title={!onSetVisionRadius ? 'Vision radius control not wired' : !visionOn ? 'Vision OFF — enable the mechanism first' : 'LIVE — Moore candidate neighborhood, not eyesight quality'}
              onClick={() => onSetVisionRadius?.(opt.radius)}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>
      <div className="subtle">
        R expands candidate cells only. FOV / distance / illumination filters unchanged.
        Default new experiment R=3 (Public Beta cap).
      </div>
      <div className="subtle">Vision OFF removes exo_* only. Illumination OFF freezes intensity.</div>

      {!nf ? (
        <div className="availability" style={{ marginTop: 8 }}>
          Package OFF — no surface / FOV sample in this frame
        </div>
      ) : (
        <>
          <div className="section-label" style={{ marginTop: 10 }}>A · WORLD / OBSERVER GT</div>
          <KV name="Vision radius" value={`R=${radius}`} />
          <KV name="Maximum candidate cells" value={maxCand} />
          <KV name="FOV" value={`${nf.fov_deg}°`} />
          <KV name="θ body" value={`${Number(nf.body_theta).toFixed(3)} rad`} />
          <KV name="θ sensor (FOV)" value={`${Number(nf.sensor_forward_axis ?? nf.head_world_heading ?? nf.body_theta).toFixed(3)} rad`} />
          <KV name="head_relative" value={nf.head_relative_angle != null ? `${Number(nf.head_relative_angle).toFixed(3)} rad` : '—'} />
          <KV name="Illumination" value={Number(nf.illumination).toFixed(4)} />
          <KV name="Illumination dynamics" value={nf.illumination_enabled === false ? 'FROZEN' : 'CYCLING'} />
          <KV name="Candidates (Moore)" value={nf.n_candidates ?? '—'} />
          <KV name="Inside FOV" value={nf.n_inside_fov} />
          <KV name="Surface checksum" value={String(nf.surface_checksum || nf.surface_meta?.checksum || '—').slice(0, 12)} />

          <div className="section-label" style={{ marginTop: 10 }}>B · PHYSICAL SENSOR</div>
          <div className="subtle">What survived FOV / angular / distance / illumination filtering</div>
          <KV name="Detectable sources" value={nf.n_detectable} />
          <KV name="Cells with body optical" value={nf.n_body_optical_cells ?? 0} />
          <KV name="Body optics gate" value={nf.body_optical_enabled ? 'ON' : 'OFF'} />
          <KV name="Aggregate intensity" value={Number(nf.aggregate_intensity).toFixed(4)} />
          <div className="subtle">env = surface_response · body = foreign optical_response · cmp = soft-OR</div>
          {(nf.neighbors || []).slice(0, Math.max(8, Number(nf.n_candidates) || 8)).map((r: any, i: number) => (
            <div key={i} className="subtle" style={{ marginBottom: 3, fontSize: 11 }}>
              [{r.cell?.[0]},{r.cell?.[1]}] d={Number(r.distance).toFixed(2)} ∠={Number(r.relative_angle_deg).toFixed(0)}°
              {' '}FOV={r.inside_fov ? 'IN' : 'OUT'}
              {' '}env={Number(r.surface_response).toFixed(2)}
              {' '}body={Number(r.body_optical ?? 0).toFixed(2)}
              {' '}cmp={Number(r.composed_optical ?? r.surface_response).toFixed(2)}
              {' '}→ {Number(r.final_contribution).toFixed(3)}
              {r.detectable ? ' DET' : ''}
            </div>
          ))}

          <div className="section-label" style={{ marginTop: 10 }}>C · AGENT-ACCESSIBLE</div>
          <div className="subtle">Anonymous channels only (Observer labels L/F/R are documentation, not cognition keys)</div>
          {exoKeys.map((k, i) => {
            const label = i === 0 ? 'L' : i === 1 ? 'F' : 'R';
            const v = cogn[k];
            const frag = nf.fragments?.[k];
            const shown =
              v !== undefined
                ? Number(v).toFixed(4)
                : frag !== undefined
                  ? Number(frag).toFixed(4)
                  : visionOn
                    ? '0.0000'
                    : '—';
            return (
              <KV
                key={k}
                name={`${k} (${label})`}
                value={shown}
              />
            );
          })}
          {visionOn && !nf.vision_contributes && !nf.perception_enabled ? (
            <div className="na">Vision authority ON but sample lacks contributes flag</div>
          ) : null}
          {!visionOn && (
            <div className="na">Vision ablated — cognition receives no exo_*</div>
          )}
          {visionOn && exoKeys.every((k) => Number(cogn[k] ?? nf.fragments?.[k] ?? 0) === 0) && (
            <div className="subtle">VISION ON · current optical contribution = 0 (not OFF)</div>
          )}
        </>
      )}
      <div className="availability" style={{ marginTop: 8 }}>
        No FOOD / RESOURCE / TERRAIN_CLASS / AGENT / EXPERIMENTER labels in cognition.
      </div>
    </div>
  );
}
