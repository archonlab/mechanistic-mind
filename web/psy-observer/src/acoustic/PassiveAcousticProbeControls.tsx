/** Passive probe controls — shared by left HEARING workspace (research API only). */
import { configureAcousticProbe } from '../api/client.ts';

export function PassiveAcousticProbeControls({
  frame,
  selectedCell,
}: {
  frame: any;
  selectedCell?: any;
}) {
  const p = frame?.world?.observer_acoustic_probe || {};
  const banner = frame?.world?.observer_acoustic_probe_banner
    || 'PASSIVE ACOUSTIC PROBE · PHYSICAL FIELD · XY POINT SAMPLE · NO AUDIO PLAYBACK';
  const latest = p.latest_sample || {};
  const bands = Array.isArray(latest.anonymous_band_energies)
    ? latest.anonymous_band_energies.map((b: number) => Number(b).toFixed(3)).join(',')
    : '—';
  const contrib = Array.isArray(latest.contributors) ? latest.contributors : [];
  const cellX = selectedCell?.ix ?? selectedCell?.position?.[0];
  const cellY = selectedCell?.iy ?? selectedCell?.position?.[1];

  if (!frame?.world?.observer_acoustic_probe && !frame?.world?.local_signal_summary
    && !frame?.world?.authoritative_physical_acoustic_stream) {
    return null;
  }

  return (
    <div className="panel hearing-section" data-testid="observer-acoustic-probe-panel" style={{ marginTop: 8 }}>
      <div data-testid="observer-acoustic-probe-banner" className="observer-banner researcher-only">{banner}</div>
      <div className="subtle" style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginTop: 4 }}>
        <label>
          Enable{' '}
          <input
            data-testid="observer-acoustic-probe-enabled"
            type="checkbox"
            checked={!!p.enabled}
            onChange={async (e) => {
              await configureAcousticProbe({ enabled: e.target.checked, x: p.x, y: p.y });
            }}
          />
        </label>
        <label>
          X{' '}
          <input
            data-testid="observer-acoustic-probe-x"
            type="number"
            step="0.1"
            defaultValue={Number(p.x ?? 0)}
            style={{ width: 72 }}
            id="oap-x"
          />
        </label>
        <label>
          Y{' '}
          <input
            data-testid="observer-acoustic-probe-y"
            type="number"
            step="0.1"
            defaultValue={Number(p.y ?? 0)}
            style={{ width: 72 }}
            id="oap-y"
          />
        </label>
        <button
          data-testid="observer-acoustic-probe-apply"
          type="button"
          onClick={async () => {
            const xi = document.getElementById('oap-x') as HTMLInputElement | null;
            const yi = document.getElementById('oap-y') as HTMLInputElement | null;
            await configureAcousticProbe({
              enabled: true,
              x: xi ? Number(xi.value) : Number(p.x || 0),
              y: yi ? Number(yi.value) : Number(p.y || 0),
            });
          }}
        >
          Apply/Move
        </button>
        <button
          data-testid="observer-acoustic-probe-from-cell"
          type="button"
          disabled={!Number.isFinite(Number(cellX)) || !Number.isFinite(Number(cellY))}
          onClick={async () => {
            await configureAcousticProbe({
              enabled: true,
              x: Number(cellX) + 0.5,
              y: Number(cellY) + 0.5,
            });
          }}
        >
          Use selected cell
        </button>
        <button
          data-testid="observer-acoustic-probe-clear"
          type="button"
          onClick={async () => {
            await configureAcousticProbe({ clear_history: true });
          }}
        >
          Clear sample history
        </button>
      </div>
      <div className="subtle" data-testid="observer-acoustic-probe-meta">
        id={p.probe_id ?? 'observer-acoustic-probe-0'} · enabled={String(!!p.enabled)} · mode={p.sampling_mode ?? 'POINT_MONO_V1'} · xy=({p.x != null ? Number(p.x).toFixed(3) : '—'},{p.y != null ? Number(p.y).toFixed(3) : '—'}) · capacity={p.history_capacity ?? 64} · retained={p.retained_count ?? 0} · evicted={p.evicted_count ?? 0} · playback=NO · hz=NOT_ESTABLISHED · mass=NO · collision=NO
      </div>
      {(() => {
        const cal = p.acoustic_calibration_status || frame?.world?.acoustic_calibration_status;
        if (!cal) return null;
        return (
          <div className="subtle" data-testid="observer-acoustic-probe-calibration" style={{ marginTop: 2 }}>
            cal={cal.profile ?? '—'} · stage={cal.authority_stage ?? '—'} · bands={cal.band_count ?? 6} · next={cal.next_honest_listening_mode ?? 'CANONICAL PHYSICAL-FIELD SONIFICATION'} · ORIGINAL=NO
          </div>
        );
      })()}
      <div className="subtle" data-testid="observer-acoustic-probe-latest">
        tick={latest.scientific_tick ?? '—'} · E={latest.total_received_energy != null ? Number(latest.total_received_energy).toFixed(4) : '—'} · bands=[{bands}] · contrib={latest.contributor_count_total ?? 0}/{latest.contributor_count_retained ?? 0} trunc={latest.contributor_count_truncated ?? 0} · examined={latest.active_signals_examined ?? '—'} · zero={String(!!latest.zero_field)} · limits={(latest.limitations || p.limitations || []).slice(0, 6).join(',')}
      </div>
      <div className="subtle" data-testid="observer-acoustic-probe-contributors" style={{ maxHeight: 100, overflow: 'auto' }}>
        {contrib.length === 0 ? (
          <div>no accepted contributors this sample</div>
        ) : (
          contrib.map((c: any) => (
            <div key={String(c.emission_id)} style={{ marginTop: 2 }}>
              emission={c.emission_id ?? '—'} · stream={c.stream_record_id ?? '—'} · d={c.toroidal_distance != null ? Number(c.toroidal_distance).toFixed(3) : '—'} · att={c.attenuation != null ? Number(c.attenuation).toFixed(4) : '—'} · E={c.total_received_energy != null ? Number(c.total_received_energy).toFixed(4) : '—'}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
