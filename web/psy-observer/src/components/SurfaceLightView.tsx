/** O6 SURFACE / LIGHT — researcher exposed-surface audit view.
 * Consumes O2 facets + O3 illumination + O3A samples from frame payload.
 * Display transform only — never organism vision / never physical authority.
 * P3: persistent static terrain geometry buffers; dynamic optical/entity updates.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  defaultOrbitCamera,
  projectPoint,
  simToRender,
  type OrbitCamera,
} from '../observer/occupancyVolumeProjection';
import {
  CAUSAL_DISPLAY_COLORS,
  O6_LABELS,
  expandColumnarFacets,
  facetFillColor,
  resolveSurfaceDisplay,
  type DisplayMode,
} from '../observer/surfaceLightProjection';
import { timeSync } from '../observer/browserRenderPerf';

type Props = {
  audit: any;
  onSelectSurface?: (info: any) => void;
  /** P1: when true, skip geometry rebuild / canvas draw (tab hidden or pending). */
  suspended?: boolean;
};

type HeldStatic = {
  static_payload_id: string;
  facets_columnar_static: any;
  world_tile?: any;
  counts_by_face?: any;
};

async function ackHeldStatic(id: string | null) {
  try {
    await fetch('/api/observer/detail', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ surface_static_payload_id: id }),
    });
  } catch {
    /* best-effort */
  }
}

export function SurfaceLightView({ audit, onSelectSurface, suspended = false }: Props) {
  const ref = useRef<HTMLCanvasElement | null>(null);
  const camRef = useRef<OrbitCamera>(defaultOrbitCamera(32, 32));
  const drag = useRef<{ x: number; y: number; mode: 'orbit' | 'pan' } | null>(null);
  const heldStaticRef = useRef<HeldStatic | null>(null);
  const cornersCacheRef = useRef<{ staticId: string; facets: ReturnType<typeof expandColumnarFacets> } | null>(null);
  const [camTick, setCamTick] = useState(0);
  const [mode, setMode] = useState<DisplayMode>('CAUSAL_STATE');
  const [bandIndex, setBandIndex] = useState(0);
  const [opacity, setOpacity] = useState(0.92);
  const [wireframe, setWireframe] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const pickRef = useRef<Array<{ id: string; kind: string; u: number; v: number; depth: number; payload: any }>>([]);
  const [rejectNotice, setRejectNotice] = useState<string | null>(null);

  const resolved = useMemo(
    () => resolveSurfaceDisplay(audit, heldStaticRef.current),
    [audit],
  );

  // Persist / replace static base when FULL/RESET arrives with geometry.
  useEffect(() => {
    const inc = (audit?.observer_surface_incremental)
      || (audit?.display?.observer_surface_incremental)
      || null;
    const kind = String(inc?.kind || audit?.incremental_wire_kind || resolved.kind || 'FULL');
    if (kind === 'RESET' || kind === 'FULL') {
      const st = inc?.surface_static;
      const display = audit?.display || audit || {};
      const staticCol = st?.facets_columnar_static
        || (display?.facets_columnar_static_omitted ? null : display?.facets_columnar);
      const sid = String(st?.static_payload_id || display?.static_payload_id || resolved.staticPayloadId || '');
      if (sid && staticCol && !staticCol.static_omitted && staticCol.facet_id) {
        // Strip optical keys for held static persistence.
        const geom = { ...staticCol };
        delete geom.state_class;
        delete geom.incident;
        delete geom.reflected;
        geom.encoding = geom.encoding?.includes('STATIC') ? geom.encoding : 'O6_COLUMNAR_FACETS_STATIC_V1';
        heldStaticRef.current = {
          static_payload_id: sid,
          facets_columnar_static: geom,
          world_tile: st?.world_tile || display?.world_tile,
          counts_by_face: st?.counts_by_face || display?.counts_by_face,
        };
        cornersCacheRef.current = null;
        void ackHeldStatic(sid);
        setRejectNotice(null);
      }
    }
    if (resolved.rejected) {
      setRejectNotice(resolved.rejected);
      if (resolved.rejected === 'MISSING_BASE' || resolved.rejected === 'STALE_DELTA') {
        heldStaticRef.current = null;
        cornersCacheRef.current = null;
        void ackHeldStatic(null);
      }
    }
  }, [audit, resolved.kind, resolved.rejected, resolved.staticPayloadId]);

  const display = resolved.display || {};
  const available = Boolean(display?.available ?? audit?.available);
  const status = String(display?.status || audit?.status || 'UNAVAILABLE');
  const tile = display?.world_tile || heldStaticRef.current?.world_tile || { width: 32, height: 32 };
  const staticId = resolved.staticPayloadId || heldStaticRef.current?.static_payload_id || '';
  const dynRev = String(
    audit?.dynamic_revision
    || audit?.display?.dynamic_revision
    || audit?.observer_surface_incremental?.surface_dynamic?.dynamic_revision
    || '',
  );
  const digest = `${staticId}:${dynRev || display?.o3_result_checksum || ''}`;

  const facets = useMemo(() => {
    const col = display?.facets_columnar;
    if (cornersCacheRef.current && cornersCacheRef.current.staticId === staticId && col) {
      // Reuse corner geometry; refresh optical attributes only.
      const base = cornersCacheRef.current.facets;
      const n = Number(col.n) || base.length;
      const out = base.slice(0, n).map((f, i) => ({
        ...f,
        state_class: String(col.state_class?.[i] || f.state_class || 'NOT_EVALUATED'),
        incident: (col.incident || []).slice(i * 6, i * 6 + 6).length
          ? (col.incident || []).slice(i * 6, i * 6 + 6)
          : f.incident,
        reflected: (col.reflected || []).slice(i * 6, i * 6 + 6).length
          ? (col.reflected || []).slice(i * 6, i * 6 + 6)
          : f.reflected,
      }));
      return out;
    }
    const expanded = expandColumnarFacets(col);
    if (staticId && expanded.length) {
      cornersCacheRef.current = { staticId, facets: expanded };
    }
    return expanded;
  }, [digest, display?.facets_columnar, staticId]);

  const entities = resolved.entities;
  const source = display?.source || audit?.source || {};
  const organism = display?.organism_comparison || audit?.organism_comparison || {};
  const o5 = display?.o5_timing || audit?.o5_timing || {};
  const perf = display?.performance || audit?.performance || {};

  // Camera resets only when static base / tile identity changes — never for orbit or dynamic-only frames.
  useEffect(() => {
    if (suspended) return;
    camRef.current = defaultOrbitCamera(Number(tile.width) || 32, Number(tile.height) || 32);
    setCamTick((t) => t + 1);
    setSelectedId(null);
  }, [tile.width, tile.height, staticId, suspended]);

  useEffect(() => {
    if (suspended) return;
    const canvas = ref.current;
    if (!canvas) return;
    const parent = canvas.parentElement;
    const W = Math.max(320, parent?.clientWidth || 640);
    const H = Math.max(240, parent?.clientHeight || 420);
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    canvas.width = Math.floor(W * dpr);
    canvas.height = Math.floor(H * dpr);
    canvas.style.width = `${W}px`;
    canvas.style.height = `${H}px`;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const t0 = performance.now();
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = '#10141a';
    ctx.fillRect(0, 0, W, H);

    if (!available || status === 'UNAVAILABLE_NO_O2') {
      ctx.fillStyle = '#9aa3ad';
      ctx.font = '13px sans-serif';
      ctx.fillText(`SURFACE / LIGHT · ${status}`, 16, 28);
      ctx.fillText('No blank authority invented · O2 exposed facets required', 16, 48);
      return;
    }

    const cam = camRef.current;
    const w = Number(tile.width) || 32;
    const h = Number(tile.height) || 32;
    const ground = [
      simToRender(0, 0, 0),
      simToRender(w, 0, 0),
      simToRender(w, h, 0),
      simToRender(0, h, 0),
    ].map((p) => projectPoint(p, cam, W, H));
    ctx.strokeStyle = '#2a3340';
    ctx.beginPath();
    ground.forEach((p, i) => (i ? ctx.lineTo(p.u, p.v) : ctx.moveTo(p.u, p.v)));
    ctx.closePath();
    ctx.stroke();

    const picks: typeof pickRef.current = [];
    const scored = timeSync('surface_project_sort', () => {
      const rows = facets.map((f) => {
        const depthKey = f.corners.reduce((s, c) => s + projectPoint(c, cam, W, H).depth, 0) / Math.max(1, f.corners.length);
        return { f, depthKey };
      });
      rows.sort((a, b) => a.depthKey - b.depthKey);
      return rows;
    }, { facet_count: facets.length });

    timeSync('surface_draw_fill', () => {
      for (const { f, depthKey } of scored) {
        const pts = f.corners.map((c) => projectPoint(c, cam, W, H));
        if (pts.some((p) => p.depth <= 0.05)) continue;
        ctx.beginPath();
        pts.forEach((p, i) => (i ? ctx.lineTo(p.u, p.v) : ctx.moveTo(p.u, p.v)));
        ctx.closePath();
        const fill = facetFillColor(f, mode, bandIndex);
        ctx.fillStyle = fill;
        ctx.globalAlpha = opacity;
        ctx.fill();
        ctx.globalAlpha = 1;
        if (wireframe || f.facet_id === selectedId) {
          ctx.strokeStyle = f.facet_id === selectedId ? '#ffffff' : 'rgba(200,210,220,0.25)';
          ctx.lineWidth = f.facet_id === selectedId ? 2 : 1;
          ctx.stroke();
        }
        const cu = pts.reduce((s, p) => s + p.u, 0) / pts.length;
        const cv = pts.reduce((s, p) => s + p.v, 0) / pts.length;
        picks.push({ id: f.facet_id, kind: 'O2_EXPOSED_FACET', u: cu, v: cv, depth: depthKey, payload: f });
      }
    }, { facet_count: scored.length });

    timeSync('surface_draw_entities', () => {
      for (const e of entities) {
        const c = e.entity_centre || e.centre || [0, 0, 0];
        const centre = simToRender(Number(c[0]), Number(c[1]), Number(c[2]));
        const p = projectPoint(centre, cam, W, H);
        if (p.depth <= 0.05) continue;
        const rPhys = Number(e.geometry_radius) || 0.25;
        const r = Math.max(3, rPhys * (70 / Math.max(0.5, p.depth)));
        const state = String(e.state_class || 'NOT_EVALUATED');
        ctx.fillStyle = CAUSAL_DISPLAY_COLORS[state] || '#888';
        ctx.beginPath();
        ctx.arc(p.u, p.v, r, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = e.held ? '#f0c35a' : 'rgba(220,230,240,0.5)';
        ctx.stroke();
        ctx.fillStyle = '#d7ecff';
        ctx.font = '10px sans-serif';
        ctx.fillText(`${e.entity_class || 'ENT'}·analytic`, p.u + r + 2, p.v);
        picks.push({ id: String(e.sample_id), kind: 'O3A_ANALYTIC_SAMPLE', u: p.u, v: p.v, depth: p.depth, payload: e });
      }
    }, { entity_count: entities.length });

    // Source direction glyph (overlay only)
    if (Array.isArray(source.direction) && source.direction.length >= 3) {
      const origin = simToRender(w * 0.5, h * 0.5, 8);
      const d = source.direction;
      const tip = simToRender(w * 0.5 + Number(d[0]) * 4, h * 0.5 + Number(d[1]) * 4, 8 + Number(d[2]) * 4);
      const a = projectPoint(origin, cam, W, H);
      const b = projectPoint(tip, cam, W, H);
      ctx.strokeStyle = '#7ec8ff';
      ctx.beginPath();
      ctx.moveTo(a.u, a.v);
      ctx.lineTo(b.u, b.v);
      ctx.stroke();
      ctx.fillStyle = '#7ec8ff';
      ctx.font = '11px sans-serif';
      ctx.fillText('SOURCE DIR · research overlay · not entity', b.u + 4, b.v);
    }

    ctx.fillStyle = '#c5d0dc';
    ctx.font = '12px sans-serif';
    ctx.fillText(O6_LABELS.join(' · '), 12, 18);
    ctx.fillText(
      `SURFACE/LIGHT · ${status} · facets=${facets.length} · entities=${entities.length} · mode=${mode}`
      + (mode === 'BAND_AUDIT' ? ` · band_${bandIndex}` : '')
      + ` · wireframe=${wireframe ? 'DISPLAY-ONLY' : 'off'}`,
      12,
      36,
    );
    if (status === 'UNAVAILABLE_NO_O3') {
      ctx.fillText('O3 light unavailable · geometry from O2 only', 12, 54);
    }
    pickRef.current = picks;
    void (performance.now() - t0);
    void camTick;
  }, [available, status, facets, entities, mode, bandIndex, opacity, wireframe, selectedId, camTick, source, tile, suspended]);

  const selected = useMemo(() => {
    if (!selectedId) return null;
    const f = facets.find((x) => x.facet_id === selectedId);
    if (f) return { kind: 'O2_EXPOSED_FACET', ...f };
    const e = entities.find((x) => String(x.sample_id) === selectedId);
    if (e) return { kind: 'O3A_ANALYTIC_SAMPLE', ...e };
    return null;
  }, [selectedId, facets, entities]);

  useEffect(() => {
    if (selected) onSelectSurface?.(selected);
  }, [selected, onSelectSurface]);

  const onPointerDown = (ev: React.PointerEvent) => {
    const canvas = ref.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = ev.clientX - rect.left;
    const y = ev.clientY - rect.top;
    if (ev.button === 0 && !ev.shiftKey) {
      // pick nearest
      let best: (typeof pickRef.current)[0] | null = null;
      let bestD = 18;
      for (const p of pickRef.current) {
        const d = Math.hypot(p.u - x, p.v - y);
        if (d < bestD || (best && d < bestD + 2 && p.depth < best.depth)) {
          best = p;
          bestD = d;
        }
      }
      if (best) {
        setSelectedId(best.id);
        onSelectSurface?.(best.payload);
      }
    }
    drag.current = { x: ev.clientX, y: ev.clientY, mode: ev.shiftKey || ev.button === 2 ? 'pan' : 'orbit' };
    (ev.target as HTMLElement).setPointerCapture?.(ev.pointerId);
  };
  const onPointerMove = (ev: React.PointerEvent) => {
    if (!drag.current) return;
    const dx = ev.clientX - drag.current.x;
    const dy = ev.clientY - drag.current.y;
    drag.current.x = ev.clientX;
    drag.current.y = ev.clientY;
    const cam = camRef.current;
    if (drag.current.mode === 'orbit') {
      cam.yaw += dx * 0.01;
      cam.pitch = Math.max(0.05, Math.min(Math.PI * 0.49, cam.pitch + dy * 0.01));
    } else {
      cam.target.x -= dx * 0.02;
      cam.target.z += dy * 0.02;
    }
    setCamTick((t) => t + 1);
  };
  const onPointerUp = () => { drag.current = null; };
  const onWheel = (ev: React.WheelEvent) => {
    ev.preventDefault();
    const cam = camRef.current;
    cam.distance = Math.max(4, Math.min(200, cam.distance * (ev.deltaY > 0 ? 1.08 : 0.92)));
    setCamTick((t) => t + 1);
  };

  return (
    <div className="surface-light-view" data-testid="o6-surface-light-view" data-render-suspended={suspended ? '1' : '0'} data-static-payload-id={staticId || ''} data-incremental-kind={resolved.kind} style={{ position: 'relative', width: '100%', height: '100%', minHeight: 320 }}>
      {rejectNotice ? (
        <div className="subtle" data-testid="o6-incremental-reject" style={{ padding: 6 }}>
          SURFACE incremental rejected · {rejectNotice} · requesting full base
        </div>
      ) : null}
      <div className="toolbar-row" data-testid="o6-surface-controls" style={{ gap: 6, flexWrap: 'wrap', padding: 6 }}>
        {(['CAUSAL_STATE', 'BAND_AUDIT', 'COMPOSITE_FALSE_COLOR', 'MATERIAL_REFLECTANCE'] as DisplayMode[]).map((m) => (
          <button
            key={m}
            type="button"
            data-testid={`o6-display-mode-${m}`}
            className={mode === m ? 'active' : ''}
            aria-pressed={mode === m}
            onClick={() => setMode(m)}
          >
            {m.replace(/_/g, ' ')}
          </button>
        ))}
        {mode === 'BAND_AUDIT' && (
          <label className="subtle">
            band
            <select data-testid="o6-band-select" value={bandIndex} onChange={(e) => setBandIndex(Number(e.target.value))}>
              {[0, 1, 2, 3, 4, 5].map((i) => <option key={i} value={i}>{`optical_band_${i}`}</option>)}
            </select>
          </label>
        )}
        <label className="subtle">opacity<input type="range" min={0.2} max={1} step={0.05} value={opacity} onChange={(e) => setOpacity(Number(e.target.value))} /></label>
        <label className="check"><input type="checkbox" checked={wireframe} onChange={(e) => setWireframe(e.target.checked)} />wireframe (display-only)</label>
        <button type="button" data-testid="o6-reset-camera" onClick={() => {
          camRef.current = defaultOrbitCamera(Number(tile.width) || 32, Number(tile.height) || 32);
          setCamTick((t) => t + 1);
        }}>Reset camera</button>
      </div>
      <canvas
        ref={ref}
        data-testid="o6-surface-canvas"
        style={{ width: '100%', height: 'calc(100% - 40px)', touchAction: 'none', cursor: 'grab' }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onWheel={onWheel}
        onContextMenu={(e) => e.preventDefault()}
      />
      <div className="subtle" data-testid="o6-surface-legend" style={{ padding: '4px 8px' }}>
        {O6_LABELS.join(' · ')} · COMPOSITE = fixed 6→RGB display transform · wireframe ≠ O3 light
        {' '}· source={source.source_id || '—'} enabled={String(source.enabled)}
        {' '}· org_trace={organism.uses_exact_o4_trace ? 'EXACT_O4' : (organism.status || '—')}
        {' '}· o5={o5.alignment_status || o5.status || '—'}
        {' '}· cache_hit={String(perf.cache_hit)} · prims={facets.length + entities.length}
      </div>
      {selected && (
        <div className="panel" data-testid="o6-surface-inspector" style={{ position: 'absolute', right: 8, top: 48, maxWidth: 340, maxHeight: '70%', overflow: 'auto', background: 'rgba(12,16,22,0.92)', padding: 8 }}>
          <div className="section-label">SURFACE INSPECTOR · researcher-only</div>
          <div className="subtle">id={selected.facet_id || selected.sample_id}</div>
          <div className="subtle">kind={selected.kind}</div>
          <div className="subtle">state={selected.state_class}</div>
          <div className="subtle">face/class={selected.face_class || selected.entity_class || '—'}</div>
          <div className="subtle">cell=({selected.cell_x},{selected.cell_y}) area={selected.area ?? selected.area_weight ?? '—'}</div>
          <div className="subtle">o1={selected.o1_status ?? '—'}</div>
          <div className="subtle">incident=[{(selected.incident || selected.incident_spectrum || []).map((x: number) => Number(x).toFixed(3)).join(', ')}]</div>
          <div className="subtle">reflected=[{(selected.reflected || selected.reflected_spectral_exitance_proxy || []).map((x: number) => Number(x).toFixed(3)).join(', ')}]</div>
          <div className="subtle">reflectance=[{(selected.reflectance || selected.spectral_reflectance || []).map((x: number) => Number(x).toFixed(3)).join(', ')}]</div>
          {selected.geometry_radius != null && <div className="subtle">analytic r={selected.geometry_radius} · not glyph/optical radius</div>}
          <div className="subtle">obs_tick={organism.organism_observation_tick ?? '—'} · receptor_tick={organism.receptor_sample_tick ?? '—'} · o5_obs={o5.organism_observation_tick ?? '—'}</div>
          <div className="subtle">camera ≠ organism eye · not cognition</div>
        </div>
      )}
    </div>
  );
}
