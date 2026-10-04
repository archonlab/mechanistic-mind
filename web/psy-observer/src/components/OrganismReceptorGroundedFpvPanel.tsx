/** ORGANISM_RECEPTOR_GROUNDED_3D_FPV_V1 — researcher reconstruction over exact O4.

Never raycasts VW7, never recomputes light/LOS, never invents samples.
Missing trace ≠ darkness. True zero exact trace may render empty/dark.
*/

import { useEffect, useMemo, useRef, useState } from 'react';
import { useFrameStore } from '../observer/useExternalStore';

export type FpvSubMode = 'RECEPTOR_FPV' | 'COGNITION_FPV';
export type FpvChrome = 'full' | 'primary' | 'compact';

const BANNER = [
  'RESEARCHER RECONSTRUCTION',
  'EXACT O4 RECEPTOR EVIDENCE',
  'NOT A CAMERA',
  'NOT HUMAN RGB',
  'NOT CONSCIOUS EXPERIENCE',
];

const BASE_W = 320;
const BASE_H = 220;
const COMPACT_W = 200;
const COMPACT_H = 138;

function clamp01(v: number): number {
  if (!Number.isFinite(v)) return 0;
  return Math.max(0, Math.min(1, v));
}

function rgbCss(rgb: number[] | undefined, intensity = 1): string {
  const r = Math.round(255 * clamp01((rgb?.[0] ?? 0) * intensity));
  const g = Math.round(255 * clamp01((rgb?.[1] ?? 0) * intensity));
  const b = Math.round(255 * clamp01((rgb?.[2] ?? 0) * intensity));
  return `rgb(${r},${g},${b})`;
}

export function OrganismReceptorGroundedFpvPanel({
  agentFilter,
  initialMode = 'RECEPTOR_FPV',
  hidden = false,
  chrome = 'full',
  fillParent = false,
  externalTrace = null,
  controlledMode,
  displaySmooth = false,
  onRenderMs,
}: {
  agentFilter?: string | null;
  initialMode?: FpvSubMode;
  /** When true, suspend canvas draws (P1-style hidden suspension). */
  hidden?: boolean;
  /** full = dock chrome; primary = canvas-first for central workspace; compact = dual Eye cards. */
  chrome?: FpvChrome;
  /** Scale canvas to container while preserving aspect (no projection change). */
  fillParent?: boolean;
  /**
   * Explicit exact O4 trace for this agent (Eye dual monitor).
   * When set, does not fall back to selected `view.latest` (prevents cross-agent mixing).
   */
  externalTrace?: any | null;
  /** Dock-level Receptor/Cognition mode (controlled). */
  controlledMode?: FpvSubMode;
  /** Shared display-smooth flag (display-only). */
  displaySmooth?: boolean;
  onRenderMs?: (ms: number) => void;
}) {
  const frame = useFrameStore();
  const world = frame?.world || {};
  const view = world.organism_receptor_grounded_3d_fpv;
  const selected =
    agentFilter ||
    (externalTrace && externalTrace.agent_id) ||
    view?.selected_agent_id ||
    frame?.header?.selected_agent_id ||
    'agent_0';

  const [mode, setMode] = useState<FpvSubMode>(controlledMode || initialMode);
  const [smooth, setSmooth] = useState(false); // OFF by default; labelled display-only
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const hostRef = useRef<HTMLDivElement | null>(null);
  const [renderMs, setRenderMs] = useState<number | null>(null);
  const [size, setSize] = useState({ w: BASE_W, h: BASE_H });
  const compact = chrome === 'compact';
  /** Compact dual cards always key off explicit per-agent trace (may be null = UNAVAILABLE). */
  const useExternal = compact || externalTrace != null;

  useEffect(() => {
    if (controlledMode) setMode(controlledMode);
    else setMode(initialMode);
  }, [initialMode, controlledMode]);

  useEffect(() => {
    if (compact) setSmooth(Boolean(displaySmooth));
  }, [compact, displaySmooth]);

  useEffect(() => {
    if (!fillParent || !hostRef.current) return;
    const el = hostRef.current;
    const apply = () => {
      const cw = Math.max(BASE_W, Math.floor(el.clientWidth || BASE_W));
      const aspect = BASE_H / BASE_W;
      const ch = Math.max(BASE_H, Math.floor(cw * aspect));
      // Cap height so angular reading stays usable in the center column
      const maxH = Math.max(BASE_H, Math.floor((el.clientHeight || ch) - 8));
      const h = Math.min(ch, maxH);
      const w = Math.floor(h / aspect);
      setSize({ w: Math.min(cw, Math.max(BASE_W, w)), h: Math.max(BASE_H, h) });
    };
    apply();
    const ro = new ResizeObserver(apply);
    ro.observe(el);
    return () => ro.disconnect();
  }, [fillParent]);

  const latest = useExternal
    ? (externalTrace && typeof externalTrace === 'object' ? externalTrace : null)
    : view?.latest;
  const available = useExternal
    ? Boolean(latest && String(latest.agent_id || selected) === String(selected))
    : Boolean(view?.available && latest);
  const missing = useExternal
    ? (latest ? null : 'TRACE_UNAVAILABLE_FOR_AGENT')
    : (view?.missing_reason || (!view ? 'NO_PAYLOAD' : null));
  const contribs = useMemo(
    () => (Array.isArray(latest?.accepted_contributions) ? latest.accepted_contributions : []),
    [latest?.trace_id, latest?.accepted_contributions],
  );
  const cognBins = useMemo(
    () => (Array.isArray(latest?.cognition_fpv_bins) ? latest.cognition_fpv_bins : []),
    [latest?.trace_id, latest?.cognition_fpv_bins],
  );

  const fovH = Number(latest?.fov_deg || 120);
  const fovV = Number(latest?.vertical_half_angle_deg || 90) * 2;
  const W = compact ? COMPACT_W : fillParent ? size.w : BASE_W;
  const H = compact ? COMPACT_H : fillParent ? size.h : BASE_H;
  const primary = chrome === 'primary';

  useEffect(() => {
    if (hidden) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const t0 = performance.now();
    const dpr = 1; // fixed; do not silently reduce as optimization
    canvas.width = W * dpr;
    canvas.height = H * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = '#0e1014';
    ctx.fillRect(0, 0, W, H);

    if (!available) {
      // Missing ≠ darkness: hatch + label
      ctx.fillStyle = '#1a1e28';
      ctx.fillRect(0, 0, W, H);
      ctx.strokeStyle = '#445';
      for (let i = -H; i < W + H; i += 12) {
        ctx.beginPath();
        ctx.moveTo(i, 0);
        ctx.lineTo(i + H, H);
        ctx.stroke();
      }
      ctx.fillStyle = '#c9a227';
      ctx.font = '12px monospace';
      ctx.fillText('TRACE UNAVAILABLE', 16, H / 2 - 8);
      ctx.fillStyle = '#aaa';
      ctx.fillText(String(missing || 'MISSING'), 16, H / 2 + 10);
      ctx.fillText('NOT RENDERED AS DARKNESS', 16, H / 2 + 28);
      const ms = performance.now() - t0;
      setRenderMs(ms);
      onRenderMs?.(ms);
      return;
    }

    // FOV frame — same projection as BASE; only canvas pixel extent scales
    ctx.strokeStyle = '#445';
    ctx.setLineDash([4, 3]);
    ctx.strokeRect(10, 10, W - 20, H - 20);
    ctx.setLineDash([]);
    ctx.strokeStyle = '#333';
    ctx.beginPath();
    ctx.moveTo(W / 2, 10);
    ctx.lineTo(W / 2, H - 10);
    ctx.moveTo(10, H / 2);
    ctx.lineTo(W - 10, H / 2);
    ctx.stroke();

    const halfH = Math.max(1e-6, fovH / 2);
    const halfV = Math.max(1e-6, fovV / 2);
    const project = (az: number, el: number) => {
      const nx = clamp01((az + halfH) / (2 * halfH));
      const ny = clamp01(1 - (el + halfV) / (2 * halfV));
      return { x: 10 + nx * (W - 20), y: 10 + ny * (H - 20) };
    };

    let maxDist = 1;
    for (const c of contribs) {
      const d = Number(c?.distance_3d);
      if (Number.isFinite(d) && d > maxDist) maxDist = d;
    }

    const scale = Math.min(W / BASE_W, H / BASE_H);

    if (mode === 'RECEPTOR_FPV') {
      if (contribs.length === 0 && latest?.true_zero_exact_trace) {
        ctx.fillStyle = '#050608';
        ctx.fillRect(12, 12, W - 24, H - 24);
        ctx.fillStyle = '#888';
        ctx.font = '11px monospace';
        ctx.fillText('TRUE ZERO · exact O4 trace · no accepted contribution', 16, H / 2);
      }
      for (const c of contribs) {
        const az = Number(c.azimuth_deg);
        const el = Number(c.elevation_deg);
        if (!Number.isFinite(az) || !Number.isFinite(el)) continue;
        const p = project(az, el);
        const dist = Number(c.distance_3d);
        const depthT = Number.isFinite(dist) ? clamp01(dist / maxDist) : 0.5;
        const ang = Number(c.angular_weight ?? 0.5);
        const r = (3 + 8 * clamp01(ang) * (1 - 0.4 * depthT)) * scale;
        const inten = clamp01(Number(c.raw_intensity_sum) * 4);
        ctx.globalAlpha = 0.35 + 0.65 * (1 - depthT);
        ctx.fillStyle = rgbCss(c.display_rgb_nonphysical, 0.35 + 0.65 * inten);
        ctx.beginPath();
        ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
        ctx.fill();
        if (smooth) {
          // Labelled display-only blur — does not invent samples
          ctx.globalAlpha = 0.15;
          ctx.beginPath();
          ctx.arc(p.x, p.y, r * 1.8, 0, Math.PI * 2);
          ctx.fill();
        }
      }
      ctx.globalAlpha = 1;
    } else {
      // COGNITION FPV — only surviving bin resolution (no discarded detail restored)
      for (const b of cognBins) {
        const az = Number(b.azimuth_deg);
        const el = Number(b.elevation_deg) || 0;
        const p = project(az, el);
        const inten = clamp01(Number(b.post_clip_intensity));
        const rw = (W - 20) / Math.max(1, cognBins.length);
        ctx.fillStyle = `rgb(${Math.round(inten * 220)},${Math.round(inten * 220)},${Math.round(inten * 200)})`;
        ctx.globalAlpha = 0.85;
        ctx.fillRect(p.x - rw / 2, 14, rw * 0.9, H - 28);
        if (b.clipped) {
          ctx.strokeStyle = '#c9a227';
          ctx.strokeRect(p.x - rw / 2, 14, rw * 0.9, H - 28);
        }
        ctx.fillStyle = '#9ab';
        ctx.font = '10px monospace';
        ctx.fillText(String(b.bin_label || b.angular_bin), p.x - 14, H - 16);
      }
      ctx.globalAlpha = 1;
    }

    ctx.fillStyle = '#778';
    ctx.font = '9px monospace';
    ctx.fillText(`FOV H=${fovH}° V=${fovV}° · bins=${mode === 'RECEPTOR_FPV' ? contribs.length : cognBins.length}`, 12, 9);
    const ms = performance.now() - t0;
    setRenderMs(ms);
    onRenderMs?.(ms);
  }, [
    hidden,
    available,
    missing,
    mode,
    smooth,
    contribs,
    cognBins,
    latest?.trace_id,
    latest?.true_zero_exact_trace,
    fovH,
    fovV,
    W,
    H,
    onRenderMs,
  ]);

  if (!view && !useExternal) {
    return (
      <div className="panel" data-testid="o4-fpv-panel" data-available="false">
        <div className="subtle">Receptor-grounded FPV payload absent.</div>
      </div>
    );
  }

  if (compact) {
    return (
      <div
        className="o4-fpv-panel o4-fpv-compact"
        data-testid="o4-fpv-panel"
        data-available={String(available)}
        data-missing={String(missing || '')}
        data-mode={mode}
        data-hidden={String(hidden)}
        data-chrome="compact"
        data-agent={String(selected)}
        data-trace-id={latest?.trace_id ? String(latest.trace_id) : ''}
      >
        {!hidden ? (
          <canvas
            ref={canvasRef}
            width={W}
            height={H}
            data-testid="o4-fpv-canvas"
            style={{
              display: 'block',
              border: '1px solid var(--line, #444)',
              background: '#0e1014',
              maxWidth: '100%',
              width: '100%',
              height: 'auto',
              aspectRatio: `${COMPACT_W} / ${COMPACT_H}`,
            }}
          />
        ) : (
          <div className="subtle" data-testid="o4-fpv-suspended">Hidden — render suspended</div>
        )}
      </div>
    );
  }

  return (
    <div
      ref={hostRef}
      className={`panel o4-fpv-panel ${primary ? 'o4-fpv-primary' : ''}`}
      data-testid="o4-fpv-panel"
      data-available={String(available)}
      data-missing={String(missing || '')}
      data-mode={mode}
      data-hidden={String(hidden)}
      data-chrome={chrome}
    >
      {!primary ? (
        <>
          <div className="section-label" data-testid="o4-fpv-banner">
            {BANNER.map((l) => (
              <div key={l}>{l}</div>
            ))}
          </div>
          <div className="subtle" data-testid="o4-fpv-schema">
            {view.schema} · {view.profile} · {view.classification}
          </div>
          <div className="subtle" data-testid="o4-fpv-meta">
            agent=<strong>{String(selected)}</strong>
            {latest?.observation_tick != null ? ` · obs_tick=${latest.observation_tick}` : ''}
            {latest?.receptor_tick != null ? ` · receptor_tick=${latest.receptor_tick}` : ''}
            {latest?.runtime_generation != null ? ` · gen=${latest.runtime_generation}` : ''}
            {latest?.trace_id ? ` · trace=${String(latest.trace_id).slice(0, 10)}` : ''}
          </div>
          <div className="eye-dock-toolbar" data-testid="o4-fpv-modes">
            {(['RECEPTOR_FPV', 'COGNITION_FPV'] as FpvSubMode[]).map((m) => (
              <button
                key={m}
                type="button"
                className={mode === m ? 'active' : ''}
                data-testid={`o4-fpv-mode-${m.toLowerCase()}`}
                onClick={() => setMode(m)}
              >
                {m === 'RECEPTOR_FPV' ? 'RECEPTOR FPV' : 'COGNITION FPV'}
              </button>
            ))}
            <label className="subtle">
              <input
                type="checkbox"
                data-testid="o4-fpv-smooth"
                checked={smooth}
                onChange={(e) => setSmooth(e.target.checked)}
              />{' '}
              display smooth (OFF default · no new samples)
            </label>
          </div>
          <div className="subtle">
            Display RGB transform: {view.display_band_transform || latest?.display_band_transform || '—'} ·{' '}
            <strong>NONPHYSICAL</strong> · depth = exact distance_3d · blob size = angular support
          </div>
        </>
      ) : (
        <div className="eye-dock-toolbar o4-fpv-primary-tools">
          <span className="subtle">agent=<strong>{String(selected)}</strong></span>
          <label className="subtle">
            <input
              type="checkbox"
              data-testid="o4-fpv-smooth"
              checked={smooth}
              onChange={(e) => setSmooth(e.target.checked)}
            />{' '}
            display smooth (OFF · researcher-only · no new samples)
          </label>
        </div>
      )}
      {!available ? (
        <div className="subtle" data-testid="o4-fpv-unavailable" style={{ color: '#c9a227' }}>
          UNAVAILABLE · {String(missing)} · not rendered as organism darkness
        </div>
      ) : (
        <div className="subtle" data-testid="o4-fpv-counts">
          accepted={latest?.accepted_count ?? contribs.length} · rejected_excluded_from_fpv=true ·
          exo_bins={cognBins.length} · evicted_hist={view?.evicted_count ?? 0}
          {renderMs != null ? ` · render=${renderMs.toFixed(2)}ms` : ''}
        </div>
      )}
      {!hidden ? (
        <canvas
          ref={canvasRef}
          width={W}
          height={H}
          data-testid="o4-fpv-canvas"
          style={{
            display: 'block',
            marginTop: 6,
            border: '1px solid #444',
            background: '#0e1014',
            maxWidth: '100%',
            height: 'auto',
          }}
        />
      ) : (
        <div className="subtle" data-testid="o4-fpv-suspended">
          Hidden — render suspended
        </div>
      )}
      {!primary ? (
        mode === 'COGNITION_FPV' ? (
          <div className="subtle" data-testid="o4-fpv-cogn-note">
            COGNITION FPV shows only phenotype/clip/6→3 fold survivors — cannot restore discarded receptor detail.
          </div>
        ) : (
          <div className="subtle" data-testid="o4-fpv-rec-note">
            RECEPTOR FPV · exact accepted O4 contributions before final cognition fold · rejected/occluded absent
          </div>
        )
      ) : null}
    </div>
  );
}
