/** SELECTED_ORGANISM_VOLUMETRIC_VISION_VIEW_V1 — researcher reconstruction of VW6.

Read-only. Uses exact backend traces. Does not raycast VW7, inspect pixels,
or recompute LOS in the browser.
*/

import { useEffect, useMemo, useState } from 'react';
import { useFrameStore } from '../observer/useExternalStore';

type ViewMode = 'RECEPTOR' | 'VOLUMETRIC' | 'CAUSAL';

const BANNER_LINES = [
  'SELECTED ORGANISM VOLUMETRIC VISION',
  'RESEARCHER RECONSTRUCTION OF AUTHORITATIVE VISUAL SAMPLES',
  'NOT A CAMERA · NOT RENDERER PIXELS · NOT MIND READING',
];

function clamp01(v: number): number {
  if (!Number.isFinite(v)) return 0;
  return Math.max(0, Math.min(1, v));
}

function depthStyle(dist: number | null | undefined, maxDist: number): { opacity: number; r: number } {
  const d = Number(dist);
  if (!Number.isFinite(d) || maxDist <= 0) return { opacity: 0.85, r: 7 };
  const t = clamp01(d / maxDist);
  return { opacity: 0.35 + 0.55 * (1 - t), r: 10 - 5 * t };
}

function rejectionColor(cls: string, visible: boolean): string {
  if (visible) return '#3d9a5f';
  switch (cls) {
    case 'BLOCKED_BY_VW1_OCCUPANCY':
      return '#a05050';
    case 'OUTSIDE_HORIZONTAL_FOV':
      return '#7060a0';
    case 'OUTSIDE_VERTICAL_FOV':
      return '#6070a0';
    case 'BEYOND_RANGE':
      return '#887040';
    case 'OCCLUDED_SPATIAL':
      return '#905050';
    default:
      return '#666';
  }
}

export function SelectedOrganismVolumetricVisionPanel({
  agentFilter,
  initialMode = 'VOLUMETRIC',
}: {
  /** When set (A0/A1 layout), prefer that agent; otherwise frame selected agent. */
  agentFilter?: string | null;
  initialMode?: ViewMode;
}) {
  const frame = useFrameStore();
  const world = frame?.world || {};
  const raw = world.selected_organism_volumetric_vision_view;
  const selectedFromFrame =
    agentFilter ||
    raw?.selected_agent_id ||
    frame?.header?.selected_agent_id ||
    'agent_0';

  const [mode, setMode] = useState<ViewMode>(initialMode);
  useEffect(() => {
    setMode(initialMode);
  }, [initialMode]);
  const [showLos, setShowLos] = useState(false);
  const [showRejected, setShowRejected] = useState(false);
  const [showBins, setShowBins] = useState(true);
  const [selectedSample, setSelectedSample] = useState<string | null>(null);

  // Prefer the frame payload for the selected agent; if agentFilter differs and
  // we only have one selected payload, show unavailable rather than mixing.
  const view = raw;
  const latest = view?.latest;
  const agentOk = !agentFilter || String(latest?.agent_id || view?.selected_agent_id) === String(agentFilter) || !latest;
  const available = Boolean(view?.available && latest && agentOk);
  const geometric = Boolean(view?.geometric_trace_available && latest?.geometric_trace_available);

  const samples = useMemo(() => {
    const rows = Array.isArray(latest?.samples) ? latest.samples : [];
    return rows;
  }, [latest?.trace_id, latest?.samples]);

  const displaySamples = useMemo(() => {
    if (showRejected) return samples;
    return samples.filter((s: any) => s?.organism_visible);
  }, [samples, showRejected]);

  const maxDist = useMemo(() => {
    let m = 1;
    for (const s of samples) {
      const d = Number(s?.distance_3d);
      if (Number.isFinite(d) && d > m) m = d;
    }
    return m;
  }, [samples]);

  const fovH = Number(latest?.horizontal_fov_deg || 120);
  const fovV = Number(latest?.vertical_half_angle_deg || 90) * 2;
  const cogn = latest?.cognition_accessible || {};
  const counts = latest?.counts || {};

  const W = 280;
  const H = 200;
  const cx = W / 2;
  const cy = H / 2;

  function project(s: any): { x: number; y: number } | null {
    const az = Number(s?.azimuth_deg);
    const el = Number(s?.elevation_deg);
    if (!Number.isFinite(az) || !Number.isFinite(el)) return null;
    const halfH = Math.max(1e-6, fovH / 2);
    const halfV = Math.max(1e-6, fovV / 2);
    const nx = clamp01((az + halfH) / (2 * halfH));
    const ny = clamp01(1 - (el + halfV) / (2 * halfV));
    return { x: 12 + nx * (W - 24), y: 12 + ny * (H - 24) };
  }

  if (!view) {
    return (
      <div className="panel" data-testid="sovv-panel" data-available="false">
        <div className="subtle">Volumetric vision view unavailable (no researcher payload).</div>
      </div>
    );
  }

  return (
    <div className="panel sovv-panel" data-testid="sovv-panel" data-available={String(available)}>
      <div className="section-label" data-testid="sovv-banner">
        {BANNER_LINES.map((l) => (
          <div key={l}>{l}</div>
        ))}
      </div>
      <div className="subtle" data-testid="sovv-schema">
        {view.schema} · {view.profile}
      </div>
      <div className="subtle" data-testid="sovv-agent">
        Selected agent: <strong>{String(selectedFromFrame)}</strong>
        {latest?.agent_id ? ` · trace agent ${latest.agent_id}` : ''}
        {latest?.perception_tick != null ? ` · perception tick ${latest.perception_tick}` : ''}
      </div>
      <div className="eye-dock-toolbar" data-testid="sovv-modes">
        {(['RECEPTOR', 'VOLUMETRIC', 'CAUSAL'] as ViewMode[]).map((m) => (
          <button
            key={m}
            type="button"
            className={mode === m ? 'active' : ''}
            data-testid={`sovv-mode-${m.toLowerCase()}`}
            onClick={() => setMode(m)}
          >
            {m === 'CAUSAL' ? 'CAUSAL SPLIT' : m === 'RECEPTOR' ? 'RECEPTOR VIEW' : 'VOLUMETRIC VIEW'}
          </button>
        ))}
      </div>
      <div className="eye-dock-toolbar" data-testid="sovv-controls">
        <label className="subtle">
          <input
            type="checkbox"
            data-testid="sovv-show-los"
            checked={showLos}
            onChange={(e) => setShowLos(e.target.checked)}
          />{' '}
          LOS rays (researcher-only)
        </label>
        <label className="subtle">
          <input
            type="checkbox"
            data-testid="sovv-show-rejected"
            checked={showRejected}
            onChange={(e) => setShowRejected(e.target.checked)}
          />{' '}
          Audit rejected
        </label>
        <label className="subtle">
          <input
            type="checkbox"
            data-testid="sovv-show-bins"
            checked={showBins}
            onChange={(e) => setShowBins(e.target.checked)}
          />{' '}
          Receptor bins
        </label>
      </div>
      {showRejected ? (
        <div className="subtle" data-testid="sovv-rejected-warning" style={{ color: '#a60', fontWeight: 700 }}>
          AUDIT REJECTED CANDIDATES · NOT AVAILABLE TO ORGANISM
        </div>
      ) : null}
      <div className="subtle" data-testid="sovv-counts">
        candidates={counts.candidates ?? '—'} · visible={counts.visible ?? '—'} · blocked={counts.blocked ?? '—'} ·
        rejected={counts.rejected ?? '—'} · evicted={view.evicted_count ?? 0}
      </div>
      <div className="subtle">
        PHYSICAL SAMPLE GEOMETRY · RECEPTOR/PHENOTYPE VALUES · COGNITION-ACCESSIBLE VISUAL INPUT · RESEARCHER-ONLY
        PROVENANCE — display-only controls (no organism motors).
      </div>

      {!available ? (
        <div className="subtle" data-testid="sovv-unavailable">
          {view.fallback || 'UNAVAILABLE'} — no exact VW6 scientific trace for this selection.
        </div>
      ) : null}

      {(mode === 'VOLUMETRIC' || mode === 'CAUSAL') && available && geometric ? (
        <div data-testid="sovv-volumetric-plot">
          <div className="subtle">
            Projection: azimuth (H) × elevation (V) · depth = exact VW6 distance_3d · NOT a perspective camera
          </div>
          <svg
            width={W}
            height={H}
            viewBox={`0 0 ${W} ${H}`}
            data-testid="sovv-svg"
            style={{ background: '#1a1c20', border: '1px solid #444', display: 'block', marginTop: 4 }}
          >
            {/* FOV frame */}
            <rect x={12} y={12} width={W - 24} height={H - 24} fill="none" stroke="#445" strokeDasharray="3 3" />
            <line x1={cx} y1={12} x2={cx} y2={H - 12} stroke="#333" />
            <line x1={12} y1={cy} x2={W - 12} y2={cy} stroke="#333" />
            <text x={14} y={22} fill="#778" fontSize={9}>
              +elev
            </text>
            <text x={14} y={H - 16} fill="#778" fontSize={9}>
              −elev
            </text>
            <text x={W - 40} y={cy - 4} fill="#778" fontSize={9}>
              +az
            </text>
            {showLos
              ? displaySamples.map((s: any) => {
                  const p = project(s);
                  if (!p) return null;
                  return (
                    <line
                      key={`ray-${s.target_id}`}
                      x1={cx}
                      y1={cy}
                      x2={p.x}
                      y2={p.y}
                      stroke={s.organism_visible ? '#3d9a5f55' : '#a0505055'}
                      strokeWidth={1}
                      data-testid="sovv-los-ray"
                    />
                  );
                })
              : null}
            {displaySamples.map((s: any) => {
              const p = project(s);
              if (!p) return null;
              const ds = depthStyle(s.distance_3d, maxDist);
              const col = rejectionColor(String(s.rejection_class || ''), !!s.organism_visible);
              const sel = selectedSample === s.target_id;
              return (
                <g
                  key={s.target_id}
                  data-testid={`sovv-sample-${s.target_id}`}
                  data-visible={String(!!s.organism_visible)}
                  data-rejection={s.rejection_class}
                  onClick={() => setSelectedSample(s.target_id)}
                  style={{ cursor: 'pointer' }}
                >
                  <circle
                    cx={p.x}
                    cy={p.y}
                    r={sel ? ds.r + 2 : ds.r}
                    fill={col}
                    opacity={s.organism_visible ? ds.opacity : showRejected ? 0.35 : 0}
                    stroke={sel ? '#fff' : '#0000'}
                    strokeWidth={1}
                  />
                  {showBins && s.receptor_sector ? (
                    <text x={p.x + 6} y={p.y - 6} fill="#ccc" fontSize={8}>
                      {s.receptor_sector}
                      {s.spatial_bin ? `/${s.spatial_bin}` : ''}
                    </text>
                  ) : null}
                </g>
              );
            })}
          </svg>
          <div className="subtle" data-testid="sovv-legend">
            Depth: nearer = larger/more opaque · Color = false-color status · Glyph size ≠ physical size
          </div>
        </div>
      ) : null}

      {(mode === 'RECEPTOR' || mode === 'CAUSAL') && available ? (
        <div data-testid="sovv-receptor-block" style={{ marginTop: 8 }}>
          <div className="section-label">COGNITION-ACCESSIBLE VISUAL INPUT</div>
          <div className="subtle">Exact existing visual values at the organism boundary (no Z / blocker / target IDs).</div>
          <div data-testid="sovv-exo-values" className="subtle">
            {Object.entries(cogn.fragments || {}).map(([k, v]) => (
              <div key={k}>
                {k} = {Number(v).toFixed(4)}
              </div>
            ))}
            {Object.keys(cogn.fragments || {}).length === 0 ? <div>(no exo fragments in trace)</div> : null}
          </div>
          {Object.keys(cogn.spatial_fragments || {}).length ? (
            <div data-testid="sovv-spatial-values" className="subtle">
              {Object.entries(cogn.spatial_fragments || {}).map(([k, v]) => (
                <div key={k}>
                  {k} = {Number(v).toFixed(4)}
                </div>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}

      {mode === 'CAUSAL' && available ? (
        <div data-testid="sovv-causal-panel" style={{ marginTop: 8 }}>
          <div className="section-label">CAUSAL TRACE (researcher provenance)</div>
          <div className="subtle">
            eye pose → sample → XYZ → FOV/range → VW1 LOS → receptor bin → phenotype → cognition boundary
          </div>
          {selectedSample ? (
            (() => {
              const s = samples.find((x: any) => x.target_id === selectedSample);
              if (!s) return <div className="subtle">Select a sample glyph.</div>;
              return (
                <div data-testid="sovv-causal-detail" className="subtle">
                  <div>target_id (researcher) {s.target_id}</div>
                  <div>
                    dx={s.dx?.toFixed?.(3)} dy={s.dy?.toFixed?.(3)} dz={s.dz?.toFixed?.(3)} dist3d=
                    {s.distance_3d?.toFixed?.(3)}
                  </div>
                  <div>
                    az={s.azimuth_deg?.toFixed?.(1)}° el={s.elevation_deg?.toFixed?.(1)}° H-FOV={s.horizontal_fov}{' '}
                    V-FOV={s.vertical_fov}
                  </div>
                  <div>
                    LOS={s.los_status} rejection={s.rejection_class} sector={s.receptor_sector || '—'} bin=
                    {s.spatial_bin || '—'}
                  </div>
                  <div>
                    final_contribution={s.final_contribution} detectable={String(s.detectable)}
                  </div>
                  {s.blocker && showLos ? (
                    <div data-testid="sovv-blocker-prov">
                      blocker cell ({s.blocker.cell_x},{s.blocker.cell_y}) z∈({s.blocker.z_min},{s.blocker.z_max}]
                    </div>
                  ) : null}
                </div>
              );
            })()
          ) : (
            <div className="subtle">Click a sample to expand causal provenance.</div>
          )}
        </div>
      ) : null}

      {available && !geometric ? (
        <div className="subtle" data-testid="sovv-receptor-fallback">
          RECEPTOR_ONLY_FALLBACK — geometric VW6 trace unavailable; cognition floats shown without volumetric plot.
        </div>
      ) : null}
    </div>
  );
}
