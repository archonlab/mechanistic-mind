import { useEffect, useMemo, useRef, useState } from 'react';
import { occupancyCounts, periodicSegments, scalarGrid } from '../rendererMath';
import { resolvedWorldTheme, worldChrome, type WorldChrome } from '../observer/worldPresentation';
import {
  clearanceStemPx,
  DEFAULT_VERTICAL_EXAGGERATION,
  deltaColor,
  elevationColor,
  elevationGridValid,
  filterTrailSegments,
  readVerticalDisplay,
  sparseDeltasValid,
  splitTrailOnWrap,
  TRAIL_LENGTH_SAMPLES,
  TRAIL_RESEARCHER_LABEL,
  VERTICAL_EXAGGERATION_LABEL,
  type TerrainDisplayMode,
  type TrailDisplayMode,
  type TrailLengthMode,
  type VerticalDisplayContract,
  type VerticalTrailSample,
} from '../observer/verticalDisplay';


type Props = {
  world: any;
  body: any;
  layer: string;
  viewMode: string;
  perception: any;
  renderMode: string;
  opacity: number;
  showGrid: boolean;
  vectorDensity: number;
  contourLevels: number;
  autoScale: boolean;
  scaleMin: number;
  scaleMax: number;
  compositeLayers: string[];
  trajectory?: { x: number; y: number }[];
  geometryInterpretation?: any;
  onHoverCell?: (info: { ix: number; iy: number; value: number | null; field: string } | null) => void;
  onSelectCell?: (info: { ix: number; iy: number; value: number | null; field: string } | null) => void;
  layers?: Record<string, boolean>;
  agentsObserver?: Array<Record<string, unknown>>;
  agentsViews?: Record<string, any> | null;
  fovOverlay?: { show: boolean; showCandidates: boolean; agents: Record<string, boolean> } | null;
  interactionTargetId?: string | null;
  nearFieldSensor?: any;
  followXY?: { x: number; y: number } | null;
  showManipulatorReach?: boolean;
  showObjectVelocity?: boolean;
  /** RESEARCHER VIEW terrain display — never agent perception. */
  terrainMode?: TerrainDisplayMode;
  showClearanceStems?: boolean;
  showEventMarkers?: boolean;
  showElevationContours?: boolean;
  verticalExaggeration?: number;
  currentTick?: number;
  trailMode?: TrailDisplayMode;
  trailLengthMode?: TrailLengthMode;
  selectedTrailEntityId?: string | null;
};

function clamp01(t: number) {
  return Math.max(0, Math.min(1, t));
}

function heatColor(v: number, lo: number, hi: number, alpha = 1): string {
  const t = clamp01((v - lo) / Math.max(1e-12, hi - lo));
  // scientific blue→cyan→yellow→red
  const r = Math.floor(30 + 220 * Math.pow(t, 0.85));
  const g = Math.floor(60 + 160 * Math.sin(Math.PI * t));
  const b = Math.floor(200 * (1 - t) + 40);
  return `rgba(${r},${g},${b},${alpha})`;
}

function sampleGrid(grid: number[][], x: number, y: number, mode: 'nearest' | 'bilinear'): number {
  const h = grid.length;
  const w = grid[0]?.length || 1;
  if (h < 1 || w < 1) return 0;
  if (mode === 'nearest') {
    const ix = Math.max(0, Math.min(w - 1, Math.floor(x)));
    const iy = Math.max(0, Math.min(h - 1, Math.floor(y)));
    return Number(grid[iy][ix]);
  }
  // bilinear — VISUAL ONLY
  const x0 = Math.max(0, Math.min(w - 2, Math.floor(x)));
  const y0 = Math.max(0, Math.min(h - 2, Math.floor(y)));
  const fx = x - x0;
  const fy = y - y0;
  const v00 = Number(grid[y0][x0]);
  const v10 = Number(grid[y0][x0 + 1]);
  const v01 = Number(grid[y0 + 1][x0]);
  const v11 = Number(grid[y0 + 1][x0 + 1]);
  return v00 * (1 - fx) * (1 - fy) + v10 * fx * (1 - fy) + v01 * (1 - fx) * fy + v11 * fx * fy;
}

function getScalar(world: any, id: string): number[][] | null {
  return scalarGrid(world, id);
}

function rangeOf(grid: number[][] | null, auto: boolean, lo: number, hi: number) {
  if (!auto && Number.isFinite(lo) && Number.isFinite(hi) && hi > lo) return { lo, hi };
  if (!grid || !grid.length) return { lo: 0, hi: 1 };
  let mn = Infinity;
  let mx = -Infinity;
  for (const row of grid) for (const v of row) {
    const n = Number(v);
    if (n < mn) mn = n;
    if (n > mx) mx = n;
  }
  if (!Number.isFinite(mn) || !Number.isFinite(mx) || mn === mx) return { lo: mn || 0, hi: (mx || 0) + 1e-6 };
  return { lo: mn, hi: mx };
}

export function WorldMap({
  world, body, layer, viewMode, perception, renderMode, opacity, showGrid,
  vectorDensity, contourLevels, autoScale, scaleMin, scaleMax, compositeLayers,
  trajectory = [], geometryInterpretation = null, onHoverCell,
  onSelectCell,
  layers = { body: true, sites: true, trajectory: true, velocity: true, orientation: true, deformation: true, occupancy: false, force: false },
  agentsObserver = [],
  agentsViews = null,
  fovOverlay = null,
  interactionTargetId = null,
  nearFieldSensor = null,
  followXY = null,
  showManipulatorReach = true,
  showObjectVelocity = false,
  terrainMode = 'OPTICAL',
  showClearanceStems = true,
  showEventMarkers = true,
  showElevationContours = false,
  verticalExaggeration = DEFAULT_VERTICAL_EXAGGERATION,
  currentTick = 0,
  trailMode = 'OFF',
  trailLengthMode = 'NORMAL',
  selectedTrailEntityId = null,
}: Props) {
  const ref = useRef<HTMLCanvasElement | null>(null);
  const heatCache = useRef<{
    key: string;
    canvas: HTMLCanvasElement;
  } | null>(null);
  const [cam, setCam] = useState({ x: 0, y: 0, zoom: 1 });
  const drag = useRef<{ x: number; y: number; cx: number; cy: number } | null>(null);
  const [viewport, setViewport] = useState({ w: 0, h: 0 });
  const [themeTick, setThemeTick] = useState(0);
  const [objectTip, setObjectTip] = useState<{
    x: number;
    y: number;
    object_id: string;
    mass: number;
    quantity: number;
    composition: string;
    physical_state: string;
    holder_body_id?: string | null;
    optical_radius: number;
    collision_radius: number | null;
    optical_c0: number;
    optical_c1: number;
    optical_c2: number;
    agent_optics: boolean;
    compliance: number | null;
    surface_affinity: number | null;
    derivation_version: string | null;
    passive_status: string | null;
  } | null>(null);
  const [depositTip, setDepositTip] = useState<{
    x: number;
    y: number;
    deposit_id: string;
    cell: string;
    mass: number;
    quantity: number;
    composition: string;
    compliance: number;
    surface_affinity: number;
    derivation_version: string;
    traction_multiplier: number | null;
    traction_eligible: boolean | null;
    optical_c0: number | null;
    optical_c1: number | null;
    optical_c2: number | null;
    coverage: number | null;
  } | null>(null);
  const [contentsTip, setContentsTip] = useState<{ x: number; y: number; cell: string; lines: string[] } | null>(null);
  const boundary = world?.boundary;
  const topo = boundary?.spatial_topology || 'WRAP_PERIODIC';

  const scalarIds = useMemo(() => {
    if (renderMode === 'COMPOSITE') return compositeLayers.length ? compositeLayers : [layer];
    return [layer];
  }, [renderMode, compositeLayers, layer]);

  // Remeasure when simulation workspace / left dock layout changes (avoid 0×0 race).
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const parent = canvas.parentElement;
    if (!parent) return;
    const measure = () => {
      const w = parent.clientWidth;
      const h = parent.clientHeight;
      setViewport((prev) => (prev.w === w && prev.h === h ? prev : { w, h }));
    };
    measure();
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(measure) : null;
    ro?.observe(parent);
    window.addEventListener('resize', measure);
    const onTheme = () => setThemeTick((n) => n + 1);
    window.addEventListener('mm-theme-change', onTheme);
    return () => {
      ro?.disconnect();
      window.removeEventListener('resize', measure);
      window.removeEventListener('mm-theme-change', onTheme);
    };
  }, []);

  useEffect(() => {
    if (!followXY || !world || viewport.w < 2) return;
    const gw = world.width || 32;
    const gh = world.height || 32;
    const W = viewport.w;
    const H = viewport.h;
    setCam((c) => {
      const cell = Math.min(W / gw, H / gh) * c.zoom;
      return {
        ...c,
        x: W / 2 - (W - gw * cell) / 2 - Number(followXY.x) * cell,
        y: H / 2 - (H - gh * cell) / 2 - Number(followXY.y) * cell,
      };
    });
  }, [followXY?.x, followXY?.y, viewport.w, viewport.h, world?.width, world?.height]);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas || !world) return;
    const parent = canvas.parentElement!;
    const W = parent.clientWidth;
    const H = parent.clientHeight;
    if (W < 2 || H < 2) {
      // Layout not ready — wait for ResizeObserver; do not bake a 0×0 backing store.
      return;
    }
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    canvas.width = Math.floor(W * dpr);
    canvas.height = Math.floor(H * dpr);
    canvas.style.width = `${W}px`;
    canvas.style.height = `${H}px`;
    const ctx = canvas.getContext('2d')!;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const chrome = worldChrome(resolvedWorldTheme(document.documentElement));
    ctx.fillStyle = chrome.stage;
    ctx.fillRect(0, 0, W, H);

    if (viewMode === 'AGENT_PERCEPTION') {
      // Distinguish WORLD GROUND TRUTH (dim) vs AGENT ACCESSIBLE vs NOT OBSERVED
      const grid = getScalar(world, 'T');
      const gh = grid?.length || world.height || 32;
      const gw = grid?.[0]?.length || world.width || 32;
      const cell = Math.min(W / gw, H / gh) * cam.zoom;
      const ox = (W - gw * cell) / 2 + cam.x;
      const oy = (H - gh * cell) / 2 + cam.y;
      // dim world truth backdrop
      if (grid) {
        const { lo, hi } = rangeOf(grid, true, 0, 1);
        for (let y = 0; y < gh; y++) for (let x = 0; x < gw; x++) {
          ctx.fillStyle = heatColor(Number(grid[y][x]), lo, hi, 0.18);
          ctx.fillRect(ox + x * cell, oy + y * cell, cell + 0.5, cell + 0.5);
        }
      }
      ctx.fillStyle = chrome.veil;
      ctx.fillRect(0, 0, W, H);
      ctx.fillStyle = chrome.annotate;
      ctx.font = chrome.fontUi;
      let ty = 22;
      ctx.fillText('Agent perception — accessible scalars only', 12, ty); ty += 16;
      ctx.fillStyle = chrome.annotateMuted;
      ctx.fillText('Backdrop: world ground truth (dimmed, not agent-visible maps)', 12, ty); ty += 18;
      ctx.fillStyle = chrome.annotateOk;
      ctx.fillText('Agent accessible:', 12, ty); ty += 14;
      const obs = perception?.agent_observation || {};
      Object.entries(obs).forEach(([k, v]) => {
        ctx.fillStyle = chrome.annotate;
        ctx.font = chrome.fontMono;
        ctx.fillText(`  ${k} = ${Number(v).toFixed(5)}`, 12, ty);
        ty += 13;
      });
      ty += 6;
      ctx.font = chrome.fontUi;
      ctx.fillStyle = chrome.annotateWarn;
      ctx.fillText('Not observed / not available:', 12, ty); ty += 14;
      (perception?.unavailable || []).forEach((u: string) => {
        ctx.fillText(`  ${u}`, 12, ty); ty += 13;
      });
      drawBoundaryChrome(ctx, W, H, ox, oy, gw * cell, gh * cell, topo, chrome);
      if (layers.body) {
        drawBody(ctx, body, ox, oy, cell, layers, '#3b82f6', nearFieldSensor, 'agent_0', chrome);
        (world.entities?.bodies || []).forEach((b: any, i: number) => {
          if (i === 0) return;
          drawBody(ctx, { ...body, x: b.x, y: b.y, theta: b.theta || 0 }, ox, oy, cell, { ...layers, sites: false, deformation: false }, '#f97316', null, `agent_${i}`, chrome);
        });
        drawMultiAgentFov(ctx, ox, oy, cell, { body, nearFieldSensor, agentsObserver, agentsViews, fovOverlay }, chrome);
        drawResourceObjects(ctx, world, ox, oy, cell, chrome, showObjectVelocity);
        drawSurfaceDeposits(ctx, world, ox, oy, cell);
        drawManipulators(ctx, world, ox, oy, cell, chrome, showManipulatorReach);
      }
      return;
    }

    if (viewMode === 'PREDICTED') {
      ctx.fillStyle = chrome.annotate;
      ctx.font = chrome.fontUi;
      ctx.fillText('Predicted spatial field: not available in Current MM', 12, 24);
      ctx.fillStyle = chrome.annotateWarn;
      ctx.fillText('Use MIND / causal PREDICTION for structure snapshots (not a second world map).', 12, 44);
      return;
    }
    if (viewMode === 'DIFFERENCE') {
      ctx.fillStyle = chrome.annotateWarn;
      ctx.font = chrome.fontUi;
      ctx.fillText('Difference: not available unless two comparable buffered frames are selected', 12, 24);
      return;
    }

    const primary = getScalar(world, scalarIds[0] || 'T');
    const trav = (geometryInterpretation && geometryInterpretation.traversability) || null;
    const geoTransport = geometryInterpretation?.geo_transport || {};
    const geoSource = String(trav?.geo_source || geoTransport.geo_source || 'LIVE').toUpperCase();
    const liveGeoUnavailable = trav?.status === 'LIVE_GEO_UNAVAILABLE'
      || (geoSource === 'LIVE' && !trav?.class_grid && Number(trav?.n_observations || geoTransport.n_observations || 0) <= 0);
    const classGrid = liveGeoUnavailable ? null : trav?.class_grid;
    const gh = classGrid?.length || primary?.length || world.height || 32;
    const gw = classGrid?.[0]?.length || primary?.[0]?.length || world.width || 32;
    const cell = Math.min(W / gw, H / gh) * cam.zoom;
    const ox = (W - gw * cell) / 2 + cam.x;
    const oy = (H - gh * cell) / 2 + cam.y;
    const geoModes = ['TRAVERSABILITY', 'DEFLECTION', 'FLOW', 'TRAJECTORY'];
    const isGeo = geoModes.includes(viewMode);
    const empVer = Number(
      trav?.empirical_version ??
      geometryInterpretation?.geo_transport?.empirical_version ??
      -1,
    );
    const staticVer = Number(
      geoTransport.static_version ?? trav?.provenance?.geo_static_version ?? 0,
    );

    // field render — PHYSICAL vs geometry landscape modes
    // OBS-05: cache TRAVERSABILITY/DEFLECTION heatmaps; blit when only bodies move.
    // Include static_version + geo_source so Apply/reset / LIVE↔SAVED never blit stale maps.
    if ((viewMode === 'TRAVERSABILITY' && classGrid) || (viewMode === 'DEFLECTION' && trav && !liveGeoUnavailable)) {
      const heatKey = [
        viewMode,
        empVer,
        staticVer,
        geoSource,
        Math.round(ox * 10),
        Math.round(oy * 10),
        Math.round(cell * 100),
        Math.round(opacity * 100),
        W,
        H,
        chrome.stage,
      ].join('|');
      let cached = heatCache.current;
      if (!cached || cached.key !== heatKey) {
        const off = document.createElement('canvas');
        off.width = Math.floor(W * dpr);
        off.height = Math.floor(H * dpr);
        const octx = off.getContext('2d')!;
        octx.setTransform(dpr, 0, 0, dpr, 0, 0);
        octx.fillStyle = chrome.stage;
        octx.fillRect(0, 0, W, H);
        if (primary) {
          const { lo, hi } = rangeOf(primary, true, 0, 1);
          drawField(octx, primary, ox, oy, cell, 'CELL', lo, hi, viewMode === 'TRAVERSABILITY' ? 0.12 : 0.1, contourLevels);
        }
        if (viewMode === 'TRAVERSABILITY' && classGrid) {
          drawClassGrid(octx, classGrid, ox, oy, cell, opacity, chrome.classColors);
        } else if (trav) {
          const metric = trav.opposing_rate_grid || trav.worst_alignment_grid;
          drawMetricGrid(octx, metric, ox, oy, cell, opacity, 'opposing');
        }
        cached = { key: heatKey, canvas: off };
        heatCache.current = cached;
      }
      ctx.drawImage(cached.canvas, 0, 0, W, H);
    } else if (viewMode === 'FLOW') {
      if (primary) {
        const { lo, hi } = rangeOf(primary, autoScale, scaleMin, scaleMax);
        drawField(ctx, primary, ox, oy, cell, 'SMOOTH', lo, hi, Math.min(0.35, opacity), contourLevels);
      }
      drawVectors(ctx, world, ox, oy, cell, Math.max(0.25, vectorDensity), opacity);
    } else if (viewMode === 'TRAJECTORY') {
      if (primary) {
        const { lo, hi } = rangeOf(primary, true, 0, 1);
        drawField(ctx, primary, ox, oy, cell, 'CELL', lo, hi, 0.15, contourLevels);
      }
    } else if (renderMode === 'COMPOSITE') {
      const alphas = [opacity, opacity * 0.55, opacity * 0.4];
      scalarIds.slice(0, 3).forEach((id, idx) => {
        const g = getScalar(world, id);
        if (!g) return;
        const { lo, hi } = rangeOf(g, autoScale, scaleMin, scaleMax);
        drawField(ctx, g, ox, oy, cell, 'SMOOTH', lo, hi, alphas[idx] ?? 0.4, contourLevels);
      });
    } else if (renderMode === 'VECTOR') {
      if (primary) {
        const { lo, hi } = rangeOf(primary, autoScale, scaleMin, scaleMax);
        drawField(ctx, primary, ox, oy, cell, 'SMOOTH', lo, hi, Math.min(0.35, opacity), contourLevels);
      }
      drawVectors(ctx, world, ox, oy, cell, vectorDensity, opacity);
    } else if (primary) {
      const { lo, hi } = rangeOf(primary, autoScale, scaleMin, scaleMax);
      drawField(ctx, primary, ox, oy, cell, renderMode, lo, hi, opacity, contourLevels);
    }

    // Independent Observer-only terrain overlays (do not replace base field).
    const terrainOverlays: Array<{ key: string; field: string; alpha: number }> = [];
    if (layers.terrain_potential) terrainOverlays.push({ key: 'terrain_potential', field: 'terrain_potential', alpha: 0.42 });
    if (layers.terrain_drag) terrainOverlays.push({ key: 'terrain_drag', field: 'terrain_drag', alpha: 0.40 });
    if (layers.terrain_grad) terrainOverlays.push({ key: 'terrain_grad', field: 'terrain_grad_mag', alpha: 0.38 });
    for (const ov of terrainOverlays) {
      const g = getScalar(world, ov.field);
      if (!g) continue;
      const { lo, hi } = rangeOf(g, true, 0, 1);
      drawField(ctx, g, ox, oy, cell, 'SMOOTH', lo, hi, ov.alpha * opacity, 0);
    }
    if (layers.ambient_magnitude) {
      const g = getScalar(world, 'ambient_magnitude');
      if (g) {
        const { lo, hi } = rangeOf(g, true, 0, 1);
        drawField(ctx, g, ox, oy, cell, 'SMOOTH', lo, hi, 0.35 * opacity, 0);
      }
    }
    if (layers.ambient_force) {
      drawAmbientForceArrows(ctx, world, ox, oy, cell, opacity);
    }

    // OBSERVER_VERTICAL_DISPLAY_CONTRACT_V1 — researcher terrain overlays (display-only).
    const vd = readVerticalDisplay(world);
    const elevOk = elevationGridValid(vd);
    const deltaOk = sparseDeltasValid(vd);
    if (terrainMode === 'ELEVATION' && elevOk && vd) {
      drawElevationOverlay(ctx, vd, ox, oy, cell, opacity);
      if (showElevationContours) drawElevationContours(ctx, vd, ox, oy, cell);
      drawVerticalLegend(ctx, W, H, 'ELEVATION', Number(vd.elev_min), Number(vd.elev_max), verticalExaggeration);
    } else if (terrainMode === 'DELTA' && deltaOk && vd) {
      drawDeltaOverlay(ctx, vd, ox, oy, cell, opacity);
      drawVerticalLegend(ctx, W, H, 'DELTA', Number(vd.elev_min ?? 0), Number(vd.elev_max ?? 0), verticalExaggeration, vd);
    } else if (terrainMode !== 'OPTICAL' && vd == null) {
      ctx.fillStyle = chrome.annotateWarn;
      ctx.font = chrome.fontUi;
      ctx.fillText('ELEVATION VISUALIZATION NOT AVAILABLE FOR THIS FRAME', 12, 22);
    }

    if (showGrid && cell > 6) {
      ctx.strokeStyle = chrome.grid;
      ctx.lineWidth = 1;
      for (let x = 0; x <= gw; x++) {
        ctx.beginPath();
        ctx.moveTo(ox + x * cell, oy);
        ctx.lineTo(ox + x * cell, oy + gh * cell);
        ctx.stroke();
      }
      for (let y = 0; y <= gh; y++) {
        ctx.beginPath();
        ctx.moveTo(ox, oy + y * cell);
        ctx.lineTo(ox + gw * cell, oy + y * cell);
        ctx.stroke();
      }
    }

    // trajectory — WRAP_PERIODIC aware (no map-spanning jumps)
    if ((layers.trajectory || viewMode === 'TRAJECTORY') && trajectory.length > 1) {
      ctx.strokeStyle = viewMode === 'TRAJECTORY' ? chrome.trajectoryHi : chrome.trajectory;
      ctx.lineWidth = viewMode === 'TRAJECTORY' ? 2.2 : 1.5;
      periodicSegments(trajectory as any, gw, gh).forEach((segment) => {
        ctx.beginPath();
        segment.forEach((p, i) => {
          const px = ox + p.x * cell;
          const py = oy + p.y * cell;
          if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
        });
        ctx.stroke();
      });
    }

    // Empirical directional glyphs (not ground-truth flow)
    if (isGeo && Array.isArray(trav?.glyphs)) {
      for (const g of trav.glyphs) {
        const align = Number(g.mean_align);
        const conf = Math.min(1, Number(g.attempts || 0) / 12);
        const col = Number.isFinite(align)
          ? (align >= 0.4 ? `rgba(74,222,128,${0.35 + 0.55 * conf})`
            : align <= -0.3 ? `rgba(248,113,113,${0.4 + 0.55 * conf})`
            : `rgba(251,191,36,${0.35 + 0.5 * conf})`)
          : `rgba(148,163,184,${0.4 * conf})`;
        const ax = ox + Number(g.x) * cell;
        const ay = oy + Number(g.y) * cell;
        const len = cell * (0.35 + 0.35 * conf);
        ctx.strokeStyle = col;
        ctx.fillStyle = col;
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(ax, ay);
        ctx.lineTo(ax + Number(g.ux) * len, ay + Number(g.uy) * len);
        ctx.stroke();
      }
    }

    // Geometry event markers
    if (isGeo && Array.isArray(trav?.events)) {
      for (const ev of trav.events) {
        const ex = ox + Number(ev.x) * cell;
        const ey = oy + Number(ev.y) * cell;
        const kind = String(ev.kind || '');
        ctx.fillStyle = kind.includes('STRONG') ? 'rgba(248,113,113,0.9)'
          : kind.includes('REVERSAL') ? 'rgba(251,146,60,0.85)'
          : kind.includes('CONTACT') ? 'rgba(244,114,182,0.85)'
          : 'rgba(167,139,250,0.8)';
        ctx.beginPath();
        ctx.arc(ex, ey, Math.max(2.5, cell * 0.18), 0, Math.PI * 2);
        ctx.fill();
      }
    }

    if (layers.occupancy && trajectory.length) {
      const counts = occupancyCounts(trajectory as any);
      let mx = 1;
      counts.forEach((n) => { if (n > mx) mx = n; });
      counts.forEach((n, key) => {
        const [ix, iy] = key.split(',').map(Number);
        ctx.fillStyle = `rgba(244,114,182,${0.12 + 0.45 * (n / mx)})`;
        ctx.fillRect(ox + ix * cell, oy + iy * cell, cell, cell);
      });
    }

    drawBoundaryChrome(ctx, W, H, ox, oy, gw * cell, gh * cell, topo, chrome);

    if (showClearanceStems && vd) {
      drawClearanceStems(ctx, vd, ox, oy, cell, verticalExaggeration);
    }
    if (trailMode !== 'OFF' && vd) {
      drawVerticalTrails(
        ctx,
        vd,
        ox,
        oy,
        cell,
        verticalExaggeration,
        trailMode,
        trailLengthMode,
        selectedTrailEntityId,
        Number(world?.width || gw),
        Number(world?.height || gh),
      );
    }
    if (showEventMarkers && vd) {
      drawVerticalEventMarkers(ctx, vd, ox, oy, cell, Number(currentTick || world?.tick || 0));
    }
    drawObserverAcousticProbeGlyph(ctx, world, ox, oy, cell);

    if (layers.body) {
      drawBody(ctx, body, ox, oy, cell, layers, '#3b82f6', nearFieldSensor, 'agent_0', chrome);
      (world.entities?.bodies || []).forEach((b: any, i: number) => {
        if (i === 0) return;
        drawBody(ctx, { ...body, x: b.x, y: b.y, theta: b.theta || 0 }, ox, oy, cell, { ...layers, sites: false, deformation: false }, '#f97316', null, `agent_${i}`, chrome);
      });
      // Observer-only: experimenter YOU + target ring (never in agent observation)
      for (const a of agentsObserver) {
        if (!a || a.observer_experimenter !== true) continue;
        const bx = ox + Number(a.x) * cell;
        const by = oy + Number(a.y) * cell;
        const r = Math.max(4, cell * 0.4);
        ctx.beginPath();
        ctx.arc(bx, by, r + 6, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(250,204,21,0.95)';
        ctx.lineWidth = 2;
        ctx.stroke();
        ctx.fillStyle = 'rgba(250,204,21,0.95)';
        ctx.font = chrome.fontUi;
        ctx.fillText('YOU', bx + r + 6, by - 4);
        drawBody(
          ctx,
          { x: a.x, y: a.y, theta: a.theta, vx: a.vx, vy: a.vy },
          ox, oy, cell,
          { ...layers, sites: false, deformation: false },
          '#eab308',
          null,
          String(a.observer_id || 'YOU'),
          chrome,
        );
      }
      drawMultiAgentFov(ctx, ox, oy, cell, { body, nearFieldSensor, agentsObserver, agentsViews, fovOverlay }, chrome);
      drawResourceObjects(ctx, world, ox, oy, cell, chrome, showObjectVelocity);
      drawSurfaceDeposits(ctx, world, ox, oy, cell);
      drawManipulators(ctx, world, ox, oy, cell, chrome, showManipulatorReach);
      if (interactionTargetId) {
        const t = agentsObserver.find(a => String(a.observer_id) === String(interactionTargetId));
        if (t) {
          const bx = ox + Number(t.x) * cell;
          const by = oy + Number(t.y) * cell;
          const r = Math.max(4, cell * 0.4);
          ctx.beginPath();
          ctx.arc(bx, by, r + 8, 0, Math.PI * 2);
          ctx.strokeStyle = 'rgba(52,211,153,0.9)';
          ctx.lineWidth = 2;
          ctx.setLineDash([4, 3]);
          ctx.stroke();
          ctx.setLineDash([]);
        }
      }
    }

    // Observer-only geometry vectors (requested / realized / local flow / GT flow overlay)
    const geo = geometryInterpretation;
    if (geo && typeof geo === 'object') {
      const showFlowOv = viewMode === 'FLOW' || viewMode === 'PHYSICAL' || (!isGeo && geo.flow_overlay);
      const flowOv = geo.flow_overlay;
      if (showFlowOv && flowOv?.status === 'AVAILABLE' && Array.isArray(flowOv.vectors)) {
        ctx.strokeStyle = chrome.wrap;
        ctx.fillStyle = chrome.wrap;
        ctx.lineWidth = 1.2;
        const scale = cell * 2.8;
        for (const v of flowOv.vectors) {
          const x0 = ox + Number(v.x) * cell;
          const y0 = oy + Number(v.y) * cell;
          const mag = Math.max(1e-6, Number(v.mag) || Math.hypot(Number(v.vx), Number(v.vy)));
          const x1 = x0 + (Number(v.vx) / mag) * scale * Math.min(1.2, mag * 4);
          const y1 = y0 + (Number(v.vy) / mag) * scale * Math.min(1.2, mag * 4);
          ctx.beginPath();
          ctx.moveTo(x0, y0);
          ctx.lineTo(x1, y1);
          ctx.stroke();
        }
      }
      const agents = Array.isArray(geo.agents) ? geo.agents : [];
      for (const a of agents) {
        const ax = ox + Number(a.x) * cell;
        const ay = oy + Number(a.y) * cell;
        const arrow = (ux: number, uy: number, color: string, len: number, width = 2.5) => {
          const x1 = ax + ux * len;
          const y1 = ay + uy * len;
          ctx.strokeStyle = color;
          ctx.fillStyle = color;
          ctx.lineWidth = width;
          ctx.beginPath();
          ctx.moveTo(ax, ay);
          ctx.lineTo(x1, y1);
          ctx.stroke();
          ctx.beginPath();
          ctx.arc(x1, y1, 3, 0, Math.PI * 2);
          ctx.fill();
        };
        if (Array.isArray(a.requested_unit) && a.requested_unit.length === 2) {
          // dashed feel via two-tone: requested = yellow thick
          arrow(Number(a.requested_unit[0]), Number(a.requested_unit[1]), 'rgba(250,204,21,0.98)', cell * 1.55, 3);
        }
        const since = a.since_prev_capture;
        if (since && Number(since.mag ?? since.displacement_mag) > 1e-6) {
          const dx = Number(since.dx);
          const dy = Number(since.dy);
          const mag = Math.hypot(dx, dy) || 1;
          arrow(dx / mag, dy / mag, 'rgba(52,211,153,0.98)', cell * 1.55, 3);
        }
        if ((viewMode === 'FLOW' || viewMode === 'PHYSICAL') && a.local_flow?.status === 'AVAILABLE' && Number(a.local_flow.mag) > 1e-6) {
          arrow(Number(a.local_flow.vx) / Number(a.local_flow.mag), Number(a.local_flow.vy) / Number(a.local_flow.mag), 'rgba(56,189,248,0.95)', cell * 1.15, 2);
        }
      }
    }

    // labels
    ctx.fillStyle = chrome.annotate;
    ctx.font = chrome.fontUi;
    const modeLabel = isGeo ? viewMode : `${renderMode} · field=${scalarIds.join('+')}`;
    ctx.fillText(`${world.width}×${world.height} · ${topo} · ${modeLabel}`, 10, H - 10);
    if (liveGeoUnavailable && (viewMode === 'TRAVERSABILITY' || viewMode === 'DEFLECTION')) {
      ctx.fillStyle = chrome.annotateWarn;
      ctx.font = chrome.fontUi;
      ctx.fillText('LIVE GEO unavailable', 12, 22);
      ctx.font = chrome.fontUi;
      ctx.fillStyle = chrome.annotateMuted;
      ctx.fillText('No current-runtime empirical samples — not showing older runs', 12, 38);
    } else if (viewMode === 'TRAVERSABILITY') {
      if (geoSource === 'SAVED') {
        ctx.fillStyle = chrome.annotateWarn;
        ctx.fillText('SAVED GEO (historical) — not LIVE runtime', 10, H - 52);
        ctx.fillStyle = chrome.annotate;
      }
      ctx.fillText('empirical class: gray=low evidence  green=easy  amber=mixed  orange=difficult  red=strong deflection', 10, H - 24);
      ctx.fillText('glyphs=requested dir colored by mean alignment · NOT walls · Observer-only', 10, H - 38);
    } else if (viewMode === 'DEFLECTION') {
      ctx.fillText('deflection: opposing_rate heatmap · low evidence left dark · Observer empirical', 10, H - 24);
    } else if (viewMode === 'FLOW') {
      ctx.fillText('GROUND TRUTH flow (−∇T) cyan · yellow=requested · green=realized · distinct from empirical', 10, H - 24);
    } else if (viewMode === 'TRAJECTORY') {
      ctx.fillText('trajectory WRAP-aware · markers=STRONG DEFLECTION/REVERSAL · no intention labels', 10, H - 24);
    } else if (geo && typeof geo === 'object') {
      ctx.fillText('yellow=requested  green=realized  cyan=local/GT flow', 10, H - 24);
    }
    if (terrainMode !== 'OPTICAL') {
      ctx.fillStyle = chrome.annotateWarn;
      ctx.font = chrome.fontUi;
      ctx.fillText('RESEARCHER VIEW · NOT AGENT PERCEPTION · TERRAIN:' + terrainMode, 10, 18);
      if (showClearanceStems) {
        ctx.fillStyle = chrome.annotateMuted;
        ctx.fillText(`${VERTICAL_EXAGGERATION_LABEL} stems ×${verticalExaggeration} (display only)`, 10, 34);
      }
    }
    if (trailMode !== 'OFF') {
      ctx.fillStyle = chrome.annotateWarn;
      ctx.font = chrome.fontUi;
      const y0 = terrainMode !== 'OPTICAL' ? 50 : 18;
      ctx.fillText(`${TRAIL_RESEARCHER_LABEL} · ${trailMode}/${trailLengthMode}`, 10, y0);
    }
  }, [world, body, layer, viewMode, perception, renderMode, opacity, showGrid, vectorDensity, contourLevels, autoScale, scaleMin, scaleMax, scalarIds, cam, trajectory, topo, layers, geometryInterpretation, agentsObserver, agentsViews, fovOverlay, interactionTargetId, nearFieldSensor, viewport, themeTick, terrainMode, showClearanceStems, showEventMarkers, showElevationContours, verticalExaggeration, currentTick, trailMode, trailLengthMode, selectedTrailEntityId]);

  function clientToCell(e: React.MouseEvent) {
    const canvas = ref.current;
    if (!canvas || !world) return null;
    const rect = canvas.getBoundingClientRect();
    const trav = geometryInterpretation?.traversability;
    const primary = getScalar(world, scalarIds[0] || 'T');
    const gh = trav?.class_grid?.length || primary?.length || world.height || 32;
    const gw = trav?.class_grid?.[0]?.length || primary?.[0]?.length || world.width || 32;
    const W = rect.width;
    const H = rect.height;
    const cell = Math.min(W / gw, H / gh) * cam.zoom;
    const ox = (W - gw * cell) / 2 + cam.x;
    const oy = (H - gh * cell) / 2 + cam.y;
    const x = (e.clientX - rect.left - ox) / cell;
    const y = (e.clientY - rect.top - oy) / cell;
    const ix = Math.floor(x);
    const iy = Math.floor(y);
    if (ix < 0 || iy < 0 || ix >= gw || iy >= gh) return { ix, iy, value: null as number | null, field: scalarIds[0] };
    const classCode = trav?.class_grid?.[iy]?.[ix];
    const fieldVal = primary ? Number(primary[iy][ix]) : null;
    return {
      ix, iy,
      value: classCode != null ? Number(classCode) : fieldVal,
      field: trav?.class_grid ? 'trav_class' : scalarIds[0],
    };
  }

  return (
    <div className="canvas-wrap"
      onWheel={(e) => {
        e.preventDefault();
        setCam((c) => ({ ...c, zoom: Math.max(0.4, Math.min(12, c.zoom * (e.deltaY > 0 ? 0.9 : 1.1))) }));
      }}
      onMouseDown={(e) => { drag.current = { x: e.clientX, y: e.clientY, cx: cam.x, cy: cam.y }; }}
      onMouseMove={(e) => {
        if (drag.current) {
          setCam((c) => ({
            ...c,
            x: drag.current!.cx + (e.clientX - drag.current!.x),
            y: drag.current!.cy + (e.clientY - drag.current!.y),
          }));
        }
        const cellInfo = clientToCell(e);
        onHoverCell?.(cellInfo);
        const canvas = ref.current;
        if (!canvas || !world) {
          setObjectTip(null);
          setDepositTip(null);
          return;
        }
        const rect = canvas.getBoundingClientRect();
        const trav = geometryInterpretation?.traversability;
        const primary = getScalar(world, scalarIds[0] || 'T');
        const gh = trav?.class_grid?.length || primary?.length || world.height || 32;
        const gw = trav?.class_grid?.[0]?.length || primary?.[0]?.length || world.width || 32;
        const W = rect.width;
        const H = rect.height;
        const cell = Math.min(W / gw, H / gh) * cam.zoom;
        const ox = (W - gw * cell) / 2 + cam.x;
        const oy = (H - gh * cell) / 2 + cam.y;
        const wx = (e.clientX - rect.left - ox) / cell;
        const wy = (e.clientY - rect.top - oy) / cell;
        const objs = listResourceObjects(world);
        const hit = objs.find((o) => {
          const dx = wx - Number(o.x);
          const dy = wy - Number(o.y);
          return dx * dx + dy * dy <= 0.35 * 0.35;
        });
        if (hit) {
          const comps = Array.isArray(hit.composition)
            ? hit.composition.map((c: any) => `${c.component_id}:${Number(c.amount).toFixed(3)}`).join(', ')
            : String(hit.composition || '');
          const opt = hit.optical_response || {};
          const props = hit.passive_material_properties || null;
          setObjectTip({
            x: e.clientX - rect.left,
            y: e.clientY - rect.top,
            object_id: String(hit.object_id || ''),
            mass: Number(hit.mass),
            quantity: Number(hit.quantity),
            composition: comps,
            physical_state: String(hit.physical_state || ''),
            holder_body_id: hit.holder_body_id ? String(hit.holder_body_id) : null,
            optical_radius: Number(hit.optical_radius || 0),
            collision_radius: Number.isFinite(Number(hit.collision_radius)) ? Number(hit.collision_radius) : null,
            optical_c0: Number(opt.c0 ?? opt[0] ?? 0),
            optical_c1: Number(opt.c1 ?? opt[1] ?? 0),
            optical_c2: Number(opt.c2 ?? opt[2] ?? 0),
            agent_optics: Boolean(hit.agent_optical_contribution_enabled),
            compliance: props && Number.isFinite(Number(props.compliance)) ? Number(props.compliance) : null,
            surface_affinity: props && Number.isFinite(Number(props.surface_affinity)) ? Number(props.surface_affinity) : null,
            derivation_version: props ? String(props.derivation_version || props.derivation || '') : null,
            passive_status: props ? 'passive — no consequence kernel' : null,
          });
          setDepositTip(null);
          setContentsTip(null);
        } else {
          setObjectTip(null);
          const deposits = listSurfaceDeposits(world);
          const hitDeposit = deposits.find((d: any) => Math.floor(wx) === Number(d.cell_x) && Math.floor(wy) === Number(d.cell_y));
          if (hitDeposit) {
            const comps = Array.isArray(hitDeposit.composition)
              ? hitDeposit.composition.map((c: any) => `${c.component_id}:${Number(c.amount).toFixed(3)}`).join(', ')
              : '';
            setDepositTip({
              x: e.clientX - rect.left,
              y: e.clientY - rect.top,
              deposit_id: String(hitDeposit.deposit_id || ''),
              cell: `${hitDeposit.cell_x},${hitDeposit.cell_y}`,
              mass: Number(hitDeposit.mass),
              quantity: Number(hitDeposit.quantity),
              composition: comps,
              compliance: Number(hitDeposit.compliance),
              surface_affinity: Number(hitDeposit.surface_affinity),
              derivation_version: String(hitDeposit.derivation_version || ''),
              traction_multiplier: Number.isFinite(Number(hitDeposit.traction_multiplier)) ? Number(hitDeposit.traction_multiplier) : null,
              traction_eligible: hitDeposit.traction_eligible == null ? null : Boolean(hitDeposit.traction_eligible),
              optical_c0: Number.isFinite(Number(hitDeposit.optical_c0)) ? Number(hitDeposit.optical_c0) : null,
              optical_c1: Number.isFinite(Number(hitDeposit.optical_c1)) ? Number(hitDeposit.optical_c1) : null,
              optical_c2: Number.isFinite(Number(hitDeposit.optical_c2)) ? Number(hitDeposit.optical_c2) : null,
              coverage: Number.isFinite(Number(hitDeposit.coverage)) ? Number(hitDeposit.coverage) : null,
            });
          } else {
            setDepositTip(null);
          }
          const contents = Array.isArray(world?.spatial_cell_contents) ? world.spatial_cell_contents : [];
          const hitContents = contents.find((row: any) => Number(row.cell_x) === Math.floor(wx) && Number(row.cell_y) === Math.floor(wy));
          if (hitContents && Array.isArray(hitContents.refs)) {
            setContentsTip({
              x: e.clientX - rect.left,
              y: e.clientY - rect.top,
              cell: `${hitContents.cell_x}, ${hitContents.cell_y}`,
              lines: hitContents.refs.map((ref: any) => `${ref.entity_kind} ${ref.entity_id}`),
            });
          } else {
            setContentsTip(null);
          }
        }
      }}
      onMouseUp={() => { drag.current = null; }}
      onClick={(e) => onSelectCell?.(clientToCell(e))}
      onMouseLeave={() => { drag.current = null; onHoverCell?.(null); setObjectTip(null); setDepositTip(null); setContentsTip(null); }}
    >
      <canvas className="map" ref={ref} />
      {objectTip ? (
        <div
          className="resource-object-tooltip"
          data-testid="resource-object-tooltip"
          style={{
            position: 'absolute',
            left: objectTip.x + 10,
            top: objectTip.y + 10,
            pointerEvents: 'none',
            background: 'rgba(15,23,42,0.92)',
            color: '#e2e8f0',
            padding: '6px 8px',
            fontSize: 11,
            borderRadius: 4,
            zIndex: 4,
            maxWidth: 240,
          }}
        >
          <div><strong>{objectTip.object_id}</strong></div>
          <div>mass {objectTip.mass.toFixed(3)} · quantity {objectTip.quantity.toFixed(3)}</div>
          <div>{objectTip.composition}</div>
          <div>{objectTip.physical_state}{objectTip.holder_body_id ? ` holder=${objectTip.holder_body_id}` : ''}</div>
          <div>optical_radius {objectTip.optical_radius.toFixed(3)} (world cells, not collision, not glyph size)</div>
          {objectTip.collision_radius != null ? (
            <div>collision_radius {objectTip.collision_radius.toFixed(3)} (physical contact · not optical · not glyph)</div>
          ) : null}
          <div>c0 {objectTip.optical_c0.toFixed(3)} · c1 {objectTip.optical_c1.toFixed(3)} · c2 {objectTip.optical_c2.toFixed(3)}</div>
          <div>agent optical contribution: {objectTip.agent_optics ? 'enabled (anonymous channels)' : 'off'}</div>
          {objectTip.compliance != null && objectTip.surface_affinity != null ? (
            <>
              <div>compliance {objectTip.compliance.toFixed(3)}</div>
              <div>surface_affinity {objectTip.surface_affinity.toFixed(3)}</div>
              <div>derivation {objectTip.derivation_version}</div>
              <div>researcher-only</div>
              <div>not agent-accessible</div>
              <div>{objectTip.passive_status}</div>
            </>
          ) : null}
          <div>researcher-only overlay — not a recognition claim</div>
        </div>
      ) : null}
      {contentsTip ? (
        <div
          className="spatial-contents-tooltip"
          data-testid="spatial-contents-tooltip"
          style={{
            position: 'absolute',
            left: contentsTip.x + 10,
            top: contentsTip.y + 28,
            pointerEvents: 'none',
            background: 'rgba(15,23,42,0.92)',
            color: '#e2e8f0',
            padding: '6px 8px',
            fontSize: 11,
            borderRadius: 4,
            zIndex: 5,
            maxWidth: 280,
          }}
        >
          <div>Cell ({contentsTip.cell})</div>
          <div>Physical contents: {contentsTip.lines.length}</div>
          {contentsTip.lines.map(line => <div key={line}>{line}</div>)}
          <div>researcher-only</div>
          <div>not agent-accessible</div>
          <div>co-location is not collision</div>
          <div>no vertical ordering</div>
        </div>
      ) : null}
      {depositTip ? (
        <div
          className="surface-deposit-tooltip"
          data-testid="surface-deposit-tooltip"
          style={{
            position: 'absolute',
            left: depositTip.x + 10,
            top: depositTip.y + 10,
            pointerEvents: 'none',
            background: 'rgba(15,23,42,0.92)',
            color: '#e2e8f0',
            padding: '6px 8px',
            fontSize: 11,
            borderRadius: 4,
            zIndex: 4,
            maxWidth: 260,
          }}
        >
          <div><strong>{depositTip.deposit_id}</strong></div>
          <div>cell {depositTip.cell}</div>
          <div>mass {depositTip.mass.toFixed(3)} · quantity {depositTip.quantity.toFixed(3)}</div>
          <div>{depositTip.composition}</div>
          <div>compliance {depositTip.compliance.toFixed(3)}</div>
          <div>surface_affinity {depositTip.surface_affinity.toFixed(3)}</div>
          <div>derivation {depositTip.derivation_version}</div>
          {depositTip.optical_c0 != null ? (
            <>
              <div>c0 {depositTip.optical_c0.toFixed(3)} · c1 {depositTip.optical_c1?.toFixed(3)} · c2 {depositTip.optical_c2?.toFixed(3)}</div>
              <div>coverage {depositTip.coverage == null ? '—' : depositTip.coverage.toFixed(3)}</div>
              <div>researcher-only</div>
              <div>agent receives anonymous optical consequence</div>
              <div>not a material identity</div>
              <div>not a traction label</div>
              <div>not a recipe</div>
            </>
          ) : null}
          {depositTip.traction_multiplier != null ? (
            <>
              <div>traction_multiplier {depositTip.traction_multiplier.toFixed(3)}</div>
              <div>eligible {depositTip.traction_eligible ? 'yes' : 'no'}</div>
              <div>researcher-only</div>
              <div>not agent-accessible</div>
              <div>continuous physical law</div>
              <div>not a recipe</div>
            </>
          ) : (
            <>
              <div>researcher-only</div>
              <div>not agent-accessible</div>
              <div>no terrain consequence yet</div>
            </>
          )}
        </div>
      ) : null}
    </div>
  );
}

function drawClassGrid(
  ctx: CanvasRenderingContext2D,
  grid: number[][],
  ox: number, oy: number, cell: number, alpha: number,
  colors: string[],
) {
  // 0 UNKNOWN, 1 LOW_EVIDENCE, 2 EASY, 3 MIXED, 4 DIFFICULT, 5 STRONG_DEFLECTION
  const gh = grid.length;
  const gw = grid[0]?.length || 0;
  for (let y = 0; y < gh; y++) {
    for (let x = 0; x < gw; x++) {
      const code = Math.max(0, Math.min(5, Number(grid[y][x]) | 0));
      if (code === 0) continue;
      ctx.fillStyle = colors[code].replace(/[\d.]+\)$/, `${(0.35 + 0.4 * alpha).toFixed(2)})`);
      // simpler: use fixed colors with alpha multiply
      ctx.globalAlpha = Math.min(1, 0.25 + alpha * 0.7);
      ctx.fillStyle = colors[code];
      ctx.fillRect(ox + x * cell, oy + y * cell, cell + 0.5, cell + 0.5);
      ctx.globalAlpha = 1;
    }
  }
}

function drawMetricGrid(
  ctx: CanvasRenderingContext2D,
  grid: (number | null)[][] | null | undefined,
  ox: number, oy: number, cell: number, alpha: number, kind: string,
) {
  if (!grid || !grid.length) return;
  const gh = grid.length;
  const gw = grid[0]?.length || 0;
  for (let y = 0; y < gh; y++) {
    for (let x = 0; x < gw; x++) {
      const v = grid[y][x];
      if (v == null || !Number.isFinite(Number(v))) continue;
      const n = Number(v);
      let t = 0;
      if (kind === 'opposing') t = clamp01(n);
      else t = clamp01((-n + 1) / 2); // alignment −1..1 → red..green inverted for deflection
      ctx.fillStyle = `rgba(${Math.floor(30 + 220 * t)},${Math.floor(60 + 80 * (1 - t))},${Math.floor(40 + 40 * (1 - t))},${0.25 + 0.55 * alpha * t})`;
      ctx.fillRect(ox + x * cell, oy + y * cell, cell + 0.5, cell + 0.5);
    }
  }
}

function drawField(
  ctx: CanvasRenderingContext2D,
  grid: number[][],
  ox: number, oy: number, cell: number,
  mode: string, lo: number, hi: number, alpha: number, contourLevels: number,
) {
  const gh = grid.length;
  const gw = grid[0].length;
  if (mode === 'CELL') {
    for (let y = 0; y < gh; y++) for (let x = 0; x < gw; x++) {
      ctx.fillStyle = heatColor(Number(grid[y][x]), lo, hi, alpha);
      ctx.fillRect(ox + x * cell, oy + y * cell, cell + 0.5, cell + 0.5);
    }
    return;
  }
  // SMOOTH: supersample with bilinear
  const scale = Math.max(2, Math.min(8, Math.ceil(cell)));
  const imgW = gw * scale;
  const imgH = gh * scale;
  const img = ctx.createImageData(imgW, imgH);
  for (let py = 0; py < imgH; py++) {
    for (let px = 0; px < imgW; px++) {
      const gx = px / scale;
      const gy = py / scale;
      const v = sampleGrid(grid, gx - 0.5, gy - 0.5, 'bilinear');
      const t = clamp01((v - lo) / Math.max(1e-12, hi - lo));
      const i = (py * imgW + px) * 4;
      img.data[i] = Math.floor(30 + 220 * Math.pow(t, 0.85));
      img.data[i + 1] = Math.floor(60 + 160 * Math.sin(Math.PI * t));
      img.data[i + 2] = Math.floor(200 * (1 - t) + 40);
      img.data[i + 3] = Math.floor(255 * alpha);
    }
  }
  const off = document.createElement('canvas');
  off.width = imgW; off.height = imgH;
  off.getContext('2d')!.putImageData(img, 0, 0);
  ctx.imageSmoothingEnabled = true;
  ctx.drawImage(off, ox, oy, gw * cell, gh * cell);

  if (mode === 'CONTOUR') {
    const light = resolvedWorldTheme(document.documentElement) === 'light';
    ctx.strokeStyle = light ? `rgba(32,48,64,${0.38 * alpha})` : `rgba(255,255,255,${0.35 * alpha})`;
    ctx.lineWidth = 1;
    const levels = Math.max(2, Math.min(24, contourLevels | 0));
    for (let li = 1; li < levels; li++) {
      const thr = lo + ((hi - lo) * li) / levels;
      // marching-squares-lite: horizontal/vertical edge crossings
      for (let y = 0; y < gh - 1; y++) {
        for (let x = 0; x < gw - 1; x++) {
          const v00 = Number(grid[y][x]);
          const v10 = Number(grid[y][x + 1]);
          const v01 = Number(grid[y + 1][x]);
          if ((v00 - thr) * (v10 - thr) < 0) {
            const t = (thr - v00) / (v10 - v00 + 1e-12);
            ctx.beginPath();
            ctx.moveTo(ox + (x + t) * cell, oy + y * cell);
            ctx.lineTo(ox + (x + t) * cell, oy + (y + 0.5) * cell);
            ctx.stroke();
          }
          if ((v00 - thr) * (v01 - thr) < 0) {
            const t = (thr - v00) / (v01 - v00 + 1e-12);
            ctx.beginPath();
            ctx.moveTo(ox + x * cell, oy + (y + t) * cell);
            ctx.lineTo(ox + (x + 0.5) * cell, oy + (y + t) * cell);
            ctx.stroke();
          }
        }
      }
    }
  }
}

function drawVectors(
  ctx: CanvasRenderingContext2D, world: any, ox: number, oy: number, cell: number, density: number, alpha: number,
) {
  const vx = scalarGrid(world, 'vx');
  const vy = scalarGrid(world, 'vy');
  if (!vx || !vy) return;
  const gh = vx.length; const gw = vx[0].length;
  const step = Math.max(1, Math.round(1 / Math.max(0.05, Math.min(1, density))));
  const light = resolvedWorldTheme(document.documentElement) === 'light';
  ctx.strokeStyle = light ? `rgba(30,45,62,${0.55 * alpha})` : `rgba(226,232,240,${0.75 * alpha})`;
  ctx.fillStyle = ctx.strokeStyle;
  ctx.lineWidth = 1;
  for (let y = step / 2; y < gh; y += step) {
    for (let x = step / 2; x < gw; x += step) {
      const ix = Math.floor(x); const iy = Math.floor(y);
      const u = Number(vx[iy][ix]); const v = Number(vy[iy][ix]);
      const mag = Math.hypot(u, v);
      if (mag < 1e-6) continue;
      const len = Math.min(cell * step * 0.85, mag * cell * 8);
      const cx = ox + (ix + 0.5) * cell;
      const cy = oy + (iy + 0.5) * cell;
      const dx = (u / mag) * len;
      const dy = (v / mag) * len;
      ctx.beginPath();
      ctx.moveTo(cx - dx * 0.3, cy - dy * 0.3);
      ctx.lineTo(cx + dx * 0.7, cy + dy * 0.7);
      ctx.stroke();
    }
  }
}

/** Observer GT sparse ambient force arrows (not planet flow). */
function drawAmbientForceArrows(
  ctx: CanvasRenderingContext2D, world: any, ox: number, oy: number, cell: number, alpha: number,
) {
  const fx = scalarGrid(world, 'ambient_fx');
  const fy = scalarGrid(world, 'ambient_fy');
  if (!fx || !fy) return;
  const gh = fx.length; const gw = fx[0].length;
  const step = Math.max(2, Math.round(Math.max(gw, gh) / 12));
  ctx.strokeStyle = `rgba(251,191,36,${0.85 * alpha})`;
  ctx.lineWidth = 1.4;
  for (let y = Math.floor(step / 2); y < gh; y += step) {
    for (let x = Math.floor(step / 2); x < gw; x += step) {
      const u = Number(fx[y][x]); const v = Number(fy[y][x]);
      const mag = Math.hypot(u, v);
      if (mag < 1e-7) continue;
      const len = Math.min(cell * step * 0.7, mag * cell * 40);
      const cx = ox + (x + 0.5) * cell;
      const cy = oy + (y + 0.5) * cell;
      const dx = (u / mag) * len;
      const dy = (v / mag) * len;
      ctx.beginPath();
      ctx.moveTo(cx - dx * 0.2, cy - dy * 0.2);
      ctx.lineTo(cx + dx * 0.8, cy + dy * 0.8);
      ctx.stroke();
    }
  }
}

function fovPalette(index: number, chrome: WorldChrome) {
  return chrome.fov[index % chrome.fov.length];
}

function drawMultiAgentFov(
  ctx: CanvasRenderingContext2D,
  ox: number, oy: number, cell: number,
  opts: {
    body: any;
    nearFieldSensor: any;
    agentsObserver: Array<Record<string, unknown>>;
    agentsViews: Record<string, any> | null;
    fovOverlay: { show: boolean; showCandidates: boolean; sectorAttribution?: boolean; agents: Record<string, boolean> } | null;
  },
  chrome: WorldChrome,
) {
  const overlay = opts.fovOverlay;
  if (!overlay || overlay.show === false) return;
  const views = opts.agentsViews || {};
  const ids = Object.keys(views).length
    ? Object.keys(views)
    : (opts.agentsObserver || []).map((a) => String(a.observer_id || a.agent_id || '')).filter(Boolean);
  const list = ids.length ? ids : ['agent_0'];
  list.forEach((id, i) => {
    if (overlay.agents[id] === false) return;
    const view = views[id] || {};
    const nf = view.physical?.near_field_exteroception
      || (i === 0 ? opts.nearFieldSensor : null);
    const b = view.body
      || opts.agentsObserver.find((a) => String(a.observer_id || a.agent_id) === id)
      || (i === 0 ? opts.body : null);
    if (!b || !nf || Number(nf.fov_deg) <= 0) return;
    drawAgentFov(ctx, b, nf, ox, oy, cell, fovPalette(i, chrome), overlay.showCandidates, id, overlay.sectorAttribution, chrome);
  });
}

function listResourceObjects(world: any): any[] {
  const a = world?.resource_objects;
  const b = world?.entities?.resource_objects;
  if (Array.isArray(a) && a.length) return a;
  if (Array.isArray(b)) return b;
  return [];
}

function listSurfaceDeposits(world: any): any[] {
  const a = world?.surface_material_deposits;
  const b = world?.entities?.surface_material_deposits;
  if (Array.isArray(a) && a.length) return a;
  if (Array.isArray(b)) return b;
  return [];
}

function drawSurfaceDeposits(
  ctx: CanvasRenderingContext2D,
  world: any,
  ox: number,
  oy: number,
  cell: number,
) {
  for (const deposit of listSurfaceDeposits(world)) {
    const px = ox + (Number(deposit.cell_x) + 0.5) * cell;
    const py = oy + (Number(deposit.cell_y) + 0.5) * cell;
    const s = Math.max(3, cell * 0.28);
    const multiplier = Number(deposit.traction_multiplier);
    const c0 = Number(deposit.optical_c0);
    const c1 = Number(deposit.optical_c1);
    const c2 = Number(deposit.optical_c2);
    let fill = 'rgba(100,116,139,0.55)';
    if (Number.isFinite(c0) && Number.isFinite(c1) && Number.isFinite(c2)) {
      const r = Math.round(Math.max(0, Math.min(1, c0)) * 255);
      const g = Math.round(Math.max(0, Math.min(1, c1)) * 255);
      const b = Math.round(Math.max(0, Math.min(1, c2)) * 255);
      fill = `rgba(${r},${g},${b},0.85)`;
    } else if (Number.isFinite(multiplier)) {
      if (multiplier < 0.999) fill = 'rgba(71,85,105,0.75)';
      else if (multiplier > 1.001) fill = 'rgba(148,163,184,0.88)';
    }
    ctx.fillStyle = fill;
    ctx.strokeStyle = 'rgba(51,65,85,0.9)';
    ctx.lineWidth = 1;
    ctx.fillRect(px - s / 2, py - s / 2, s, s);
    ctx.strokeRect(px - s / 2, py - s / 2, s, s);
  }
}

function drawResourceObjects(
  ctx: CanvasRenderingContext2D,
  world: any,
  ox: number,
  oy: number,
  cell: number,
  chrome: WorldChrome,
  showObjectVelocity = false,
) {
  void chrome;
  const objs = listResourceObjects(world);
  for (const o of objs) {
    const bx = ox + Number(o.x) * cell;
    const by = oy + Number(o.y) * cell;
    const s = Math.max(3.5, cell * 0.22);
    ctx.beginPath();
    ctx.moveTo(bx, by - s);
    ctx.lineTo(bx + s, by);
    ctx.lineTo(bx, by + s);
    ctx.lineTo(bx - s, by);
    ctx.closePath();
    const held = String(o.physical_state || '') === 'HELD';
    const moving = String(o.motion_status || '') === 'MOVING';
    ctx.fillStyle = held ? 'rgba(245,158,11,0.92)' : (moving ? 'rgba(96,165,250,0.92)' : 'rgba(148,163,184,0.92)');
    ctx.strokeStyle = held ? 'rgba(146,64,14,0.95)' : 'rgba(51,65,85,0.95)';
    ctx.lineWidth = 1.25;
    ctx.fill();
    ctx.stroke();
    const pairOn = listManipulators(world).some((m: any) => m && m.kind === 'pair_state');
    const ir = Number(o.interaction_radius);
    if (pairOn && Number.isFinite(ir) && ir > 0) {
      ctx.beginPath();
      ctx.arc(bx, by, Math.max(2, ir * cell), 0, Math.PI * 2);
      ctx.setLineDash([2, 2]);
      ctx.strokeStyle = 'rgba(34,197,94,0.7)';
      ctx.lineWidth = 1;
      ctx.stroke();
      ctx.setLineDash([]);
    }
    // Researcher-only physical collision circle (not glyph size, not optical_radius).
    const boc = world?.body_object_contact_overlay || world?.body_object_contact;
    const vdOn = !!world?.vertical_display;
    if (boc || vdOn) {
      const cr = Number(o.collision_radius);
      if (Number.isFinite(cr) && cr > 0) {
        ctx.beginPath();
        ctx.arc(bx, by, Math.max(1.5, cr * cell), 0, Math.PI * 2);
        ctx.setLineDash([3, 2]);
        ctx.strokeStyle = 'rgba(244,63,94,0.85)';
        ctx.lineWidth = 1.25;
        ctx.stroke();
        ctx.setLineDash([]);
      }
    }
    // Researcher velocity vector: drawn from the authoritative object velocity (display only, never fed back).
    const vx = Number(o.vx);
    const vy = Number(o.vy);
    if (showObjectVelocity && o.motion_status && Number.isFinite(vx) && Number.isFinite(vy) && (vx !== 0 || vy !== 0)) {
      const ex = bx + vx * 3 * cell;
      const ey = by + vy * 3 * cell;
      ctx.beginPath();
      ctx.moveTo(bx, by);
      ctx.lineTo(ex, ey);
      const ang = Math.atan2(ey - by, ex - bx);
      ctx.lineTo(ex - 5 * Math.cos(ang - 0.4), ey - 5 * Math.sin(ang - 0.4));
      ctx.moveTo(ex, ey);
      ctx.lineTo(ex - 5 * Math.cos(ang + 0.4), ey - 5 * Math.sin(ang + 0.4));
      ctx.strokeStyle = 'rgba(37,99,235,0.95)';
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }
    const label = String(o.held_overlay_label || o.object_id || '');
    if (label) {
      ctx.fillStyle = 'rgba(15,23,42,0.85)';
      ctx.font = `${Math.max(8, cell * 0.22)}px sans-serif`;
      ctx.fillText(label, bx + s + 2, by);
    }
  }
  // Debug overlay: body contact geometry (same physical radius as body/object contact fact).
  const boc = world?.body_object_contact_overlay || world?.body_object_contact;
  if (boc) {
    const br = Number(boc.body_contact_radius ?? boc.active?.body_contact_radius ?? 0.575);
    const bodies = Array.isArray(world?.bodies) ? world.bodies
      : (Array.isArray(world?.agents) ? world.agents.map((a: any) => a.body || a).filter(Boolean) : []);
    // Prefer researcher agents_observer / entities when present
    const agentBodies: any[] = [];
    const ao = world?.agents_observer || world?.observer_agents;
    if (Array.isArray(ao)) {
      for (const a of ao) {
        const b = a?.body || a;
        if (b && Number.isFinite(Number(b.x)) && Number.isFinite(Number(b.y))) agentBodies.push(b);
      }
    }
    const list = agentBodies.length ? agentBodies : bodies;
    if (Number.isFinite(br) && br > 0) {
      for (const b of list) {
        const bx = ox + Number(b.x) * cell;
        const by = oy + Number(b.y) * cell;
        ctx.beginPath();
        ctx.arc(bx, by, Math.max(2, br * cell), 0, Math.PI * 2);
        ctx.setLineDash([4, 3]);
        ctx.strokeStyle = 'rgba(56,189,248,0.55)';
        ctx.lineWidth = 1;
        ctx.stroke();
        ctx.setLineDash([]);
      }
    }
    // Active contact pairs highlight
    const active = boc.active?.active_episodes || boc.active_episodes || [];
    if (Array.isArray(active)) {
      for (const ep of active) {
        const oid = String(ep.object_id || '');
        const obj = listResourceObjects(world).find((o: any) => String(o.object_id) === oid);
        if (!obj) continue;
        const oxp = ox + Number(obj.x) * cell;
        const oyp = oy + Number(obj.y) * cell;
        ctx.beginPath();
        ctx.arc(oxp, oyp, Math.max(4, cell * 0.12), 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(244,63,94,0.95)';
        ctx.lineWidth = 2;
        ctx.stroke();
      }
    }
  }
  // Researcher-only impulse vectors (response overlay; display only).
  const bio = world?.body_object_impulse_overlay || world?.body_object_impulse;
  if (bio) {
    const responses = bio.summary?.last_step?.responses
      || bio.last_step?.responses
      || bio.last_step?.applied
      || [];
    if (Array.isArray(responses)) {
      for (const r of responses) {
        if (!r || !(Number(r.clamped_impulse ?? r.impulse) > 0)) continue;
        const n = r.normal || r.contact_normal;
        const bx = Number((r.body_pose || r.corrected_body_pose || [])[0]);
        const by = Number((r.body_pose || r.corrected_body_pose || [])[1]);
        if (!Array.isArray(n) || !Number.isFinite(bx) || !Number.isFinite(by)) continue;
        const scale = cell * 2.5 * Math.min(1.5, Math.abs(Number(r.clamped_impulse ?? r.impulse) || 0));
        const x0 = ox + bx * cell;
        const y0 = oy + by * cell;
        // normal
        ctx.beginPath();
        ctx.moveTo(x0, y0);
        ctx.lineTo(x0 + Number(n[0]) * cell * 1.2, y0 + Number(n[1]) * cell * 1.2);
        ctx.strokeStyle = 'rgba(14,165,233,0.85)';
        ctx.lineWidth = 1.5;
        ctx.stroke();
        // impulse on body (−n direction of j on body)
        const jv = r.impulse_on_body || (Array.isArray(n) ? [-Number(n[0]) * Number(r.clamped_impulse || 0), -Number(n[1]) * Number(r.clamped_impulse || 0)] : null);
        if (jv) {
          ctx.beginPath();
          ctx.moveTo(x0, y0);
          ctx.lineTo(x0 + Number(jv[0]) * scale, y0 + Number(jv[1]) * scale);
          ctx.strokeStyle = 'rgba(34,197,94,0.9)';
          ctx.lineWidth = 2;
          ctx.stroke();
        }
      }
    }
  }
}

function listManipulators(world: any): any[] {
  const a = world?.manipulators;
  const b = world?.entities?.manipulators;
  if (Array.isArray(a) && a.length) return a;
  if (Array.isArray(b)) return b;
  return [];
}

function drawManipulators(
  ctx: CanvasRenderingContext2D,
  world: any,
  ox: number,
  oy: number,
  cell: number,
  chrome: WorldChrome,
  showReach: boolean,
) {
  void chrome;
  const rows = listManipulators(world);
  for (const m of rows) {
    const bx = ox + Number(m.effector_x) * cell;
    const by = oy + Number(m.effector_y) * cell;
    const mid = String(m.manipulator_id || '');
    const left = mid === 'LEFT';
    const right = mid === 'RIGHT';
    if (m.kind === 'pair_state') continue;
    if (showReach) {
      const r = Math.max(2, Number(m.grasp_radius || 0.4) * cell);
      ctx.beginPath();
      ctx.arc(bx, by, r, 0, Math.PI * 2);
      ctx.strokeStyle = left ? 'rgba(56,189,248,0.55)' : right ? 'rgba(244,114,182,0.55)' : 'rgba(14,165,233,0.55)';
      ctx.setLineDash([4, 3]);
      ctx.lineWidth = 1;
      ctx.stroke();
      ctx.setLineDash([]);
    }
    const mark = Math.max(2.5, cell * 0.12);
    ctx.beginPath();
    if (right) {
      ctx.rect(bx - mark, by - mark, mark * 2, mark * 2);
    } else {
      ctx.arc(bx, by, mark, 0, Math.PI * 2);
    }
    ctx.fillStyle = m.occupied
      ? 'rgba(245,158,11,0.95)'
      : (left ? 'rgba(56,189,248,0.95)' : right ? 'rgba(244,114,182,0.95)' : 'rgba(56,189,248,0.95)');
    ctx.fill();
    ctx.strokeStyle = 'rgba(15,23,42,0.9)';
    ctx.lineWidth = 1;
    ctx.stroke();
    if (left || right) {
      ctx.fillStyle = 'rgba(15,23,42,0.9)';
      ctx.font = `${Math.max(8, cell * 0.2)}px sans-serif`;
      ctx.fillText(mid, bx + mark + 2, by);
    }
  }
}

function drawAgentFov(
  ctx: CanvasRenderingContext2D,
  body: any,
  nf: any,
  ox: number, oy: number, cell: number,
  pal: { fill: string; stroke: string; label: string },
  showCandidates: boolean,
  label: string,
  sectorAttribution?: boolean,
  chrome?: WorldChrome,
) {
  const bx = ox + Number(body.x) * cell;
  const by = oy + Number(body.y) * cell;
  const bodyTheta = Number(body.theta ?? nf.body_theta ?? 0);
  const headTheta = Number(
    nf.head_world_heading
      ?? nf.sensor_forward_axis
      ?? body.head_world_heading
      ?? (bodyTheta + Number(body.head_relative_angle || nf.head_relative_angle || 0)),
  );
  const fov = Number(nf.fov_deg) * Math.PI / 180;
  const half = fov / 2;
  const visionR = Math.max(1, Math.min(3, Number(nf.vision_radius ?? nf.radius ?? 1)));
  const reach = cell * (visionR + 0.15);
  ctx.beginPath();
  ctx.moveTo(bx, by);
  ctx.arc(bx, by, reach, headTheta - half, headTheta + half);
  ctx.closePath();
  ctx.fillStyle = pal.fill;
  ctx.fill();
  ctx.strokeStyle = pal.stroke;
  ctx.lineWidth = 1.25;
  ctx.stroke();
  ctx.fillStyle = pal.label;
  ctx.font = chrome?.fontUi || '10px Inter, ui-sans-serif, system-ui, sans-serif';
  ctx.fillText(String(label).replace(/_/g, ' '), bx + 8, by - 10);
  if (!showCandidates) return;
  const neighbors = nf.neighbors || [];
  for (const nb of neighbors) {
    const c = nb.cell;
    if (!c) continue;
    const nx = ox + (Number(c[0]) + 0.5) * cell;
    const ny = oy + (Number(c[1]) + 0.5) * cell;
    const contrib = Number(nb.final_contribution || 0);
    const det = Boolean(nb.detectable) && contrib > 0;
    ctx.beginPath();
    ctx.arc(nx, ny, Math.max(2, cell * (det ? 0.18 : 0.13)), 0, Math.PI * 2);
    const bodyOpt = Number(nb.body_optical || 0);
    const relDeg = Number(
      nb.relative_angle_deg
      ?? (nb.relative_angle_rad != null ? Number(nb.relative_angle_rad) * 180 / Math.PI : 0),
    );
    let sector = String(nb.sector || '');
    if (!sector && nb.inside_fov) {
      const u = (relDeg + 60) / 120;
      const bi = Math.max(0, Math.min(2, Math.floor(u * 3)));
      sector = ['LEFT', 'FORWARD', 'RIGHT'][bi];
    }
    if (det) {
      let fill = bodyOpt > 0
        ? `rgba(251, 191, 36, ${Math.min(0.85, 0.28 + contrib)})`
        : `rgba(52, 211, 153, ${Math.min(0.85, 0.28 + contrib)})`;
      if (sectorAttribution) {
        if (sector === 'LEFT') fill = `rgba(96, 165, 250, ${Math.min(0.9, 0.35 + contrib)})`;
        else if (sector === 'FORWARD') fill = `rgba(251, 191, 36, ${Math.min(0.9, 0.35 + contrib)})`;
        else if (sector === 'RIGHT') fill = `rgba(52, 211, 153, ${Math.min(0.9, 0.35 + contrib)})`;
      }
      ctx.fillStyle = fill;
      ctx.fill();
      ctx.strokeStyle = pal.stroke;
      ctx.lineWidth = 1.2;
    } else if (nb.inside_fov) {
      ctx.strokeStyle = pal.stroke;
      ctx.lineWidth = 1.1;
    } else {
      ctx.strokeStyle = 'rgba(148, 163, 184, 0.4)';
      ctx.lineWidth = 1;
    }
    ctx.stroke();
  }
}

function drawBody(
  ctx: CanvasRenderingContext2D, body: any, ox: number, oy: number,
  cell: number, layers: Record<string, boolean>,
  fill = '#3b82f6',
  nearFieldSensor: any = null,
  _label = 'body',
  chrome?: WorldChrome,
) {
  if (!body) return;
  const bx = ox + Number(body.x) * cell;
  const by = oy + Number(body.y) * cell;
  const r = Math.max(4, cell * 0.4);
  const light = resolvedWorldTheme(document.documentElement) === 'light';
  ctx.beginPath();
  ctx.arc(bx, by, r + 3, 0, Math.PI * 2);
  ctx.strokeStyle = light ? 'rgba(26,35,48,0.72)' : 'rgba(255,255,255,0.85)';
  ctx.lineWidth = 1.5;
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(bx, by, r, 0, Math.PI * 2);
  ctx.fillStyle = fill;
  ctx.fill();
  if (layers.orientation) {
    const bodyTheta = Number(body.theta || 0);
    const headTheta = Number(
      nearFieldSensor?.head_world_heading
        ?? nearFieldSensor?.sensor_forward_axis
        ?? body.head_world_heading
        ?? (bodyTheta + Number(body.head_relative_angle || 0)),
    );
    // Body heading (amber)
    ctx.strokeStyle = '#fbbf24';
    ctx.beginPath(); ctx.moveTo(bx, by);
    ctx.lineTo(bx + Math.cos(bodyTheta) * (r + 10), by + Math.sin(bodyTheta) * (r + 10));
    ctx.stroke();
    // Head / sensor axis (cyan) when distinct
    if (Math.abs(headTheta - bodyTheta) > 1e-4) {
      ctx.strokeStyle = '#22d3ee';
      ctx.lineWidth = 2;
      ctx.beginPath(); ctx.moveTo(bx, by);
      ctx.lineTo(bx + Math.cos(headTheta) * (r + 14), by + Math.sin(headTheta) * (r + 14));
      ctx.stroke();
      ctx.lineWidth = 1.5;
    }
    const omega = Number(body.omega || 0);
    if (Math.abs(omega) > 1e-6) {
      ctx.strokeStyle = 'rgba(251,191,36,0.7)';
      ctx.beginPath();
      ctx.arc(bx, by, r + 14, bodyTheta, bodyTheta + Math.max(-Math.PI / 2, Math.min(Math.PI / 2, omega * 4)), omega < 0);
      ctx.stroke();
    }
  }
  if (layers.sites && Array.isArray(body.sites)) {
    body.sites.forEach((site: any) => {
      const sx = ox + Number(site.world?.[0]) * cell;
      const sy = oy + Number(site.world?.[1]) * cell;
      const b = Math.max(0, Math.min(1, Number(site.B_site || 0)));
      ctx.beginPath();
      ctx.arc(sx, sy, Math.max(2.5, cell * 0.12), 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${Math.round(80 + 175 * b)},${Math.round(180 - 80 * b)},80,0.95)`;
      ctx.fill();
      ctx.strokeStyle = light ? 'rgba(26,35,48,0.45)' : 'rgba(255,255,255,.6)'; ctx.stroke();
    });
  }
  if (layers.deformation) {
    const dm = body.deformation_diagnostics;
    const rest = dm?.rest_geometry || [];
    const actual = dm?.actual_geometry || [];
    const theta = Number(body.theta || 0);
    const c = Math.cos(theta), s = Math.sin(theta);
    const point = (p: number[]) => ({
      x: bx + (c * Number(p[0]) - s * Number(p[1])) * cell,
      y: by + (s * Number(p[0]) + c * Number(p[1])) * cell,
    });
    if (rest.length && actual.length === rest.length) {
      rest.forEach((p: number[], i: number) => {
        const rp = point(p), ap = point(actual[i]);
        ctx.setLineDash([3, 3]); ctx.strokeStyle = chrome?.vector || 'rgba(226,232,240,0.55)';
        ctx.strokeRect(rp.x - 2, rp.y - 2, 4, 4);
        ctx.setLineDash([]); ctx.strokeStyle = '#f59e0b';
        ctx.beginPath(); ctx.moveTo(rp.x, rp.y); ctx.lineTo(ap.x, ap.y); ctx.stroke();
        ctx.beginPath(); ctx.arc(ap.x, ap.y, 3, 0, Math.PI * 2); ctx.stroke();
      });
    }
  }
  // heading from velocity if present
  const hvx = Number(body.vx || 0); const hvy = Number(body.vy || 0);
  if (layers.velocity && Math.hypot(hvx, hvy) > 1e-6) {
    const m = Math.hypot(hvx, hvy);
    ctx.strokeStyle = '#93c5fd';
    ctx.beginPath();
    ctx.moveTo(bx, by);
    ctx.lineTo(bx + (hvx / m) * (r + 8), by + (hvy / m) * (r + 8));
    ctx.stroke();
  }
  if (layers.force) {
    const env = body.force_contributions?.environmental_site || body.force_contributions?.environment;
    const fx = Number(Array.isArray(env) ? env[0] : env?.ax || 0);
    const fy = Number(Array.isArray(env) ? env[1] : env?.ay || 0);
    if (Math.hypot(fx, fy) > 1e-9) {
      const m = Math.hypot(fx, fy);
      ctx.strokeStyle = '#fb7185';
      ctx.beginPath();
      ctx.moveTo(bx, by);
      ctx.lineTo(bx + (fx / m) * (r + 16), by + (fy / m) * (r + 16));
      ctx.stroke();
    }
  }
  ctx.fillStyle = chrome?.annotate || '#e2e8f0';
  ctx.font = chrome?.fontUi || '11px Inter, ui-sans-serif, system-ui, sans-serif';
  ctx.fillText(String(_label).replace(/_/g, ' '), bx + r + 4, by - 4);
}

function drawBoundaryChrome(
  ctx: CanvasRenderingContext2D, _W: number, _H: number,
  ox: number, oy: number, ww: number, hh: number, topo: string,
  chrome: WorldChrome,
) {
  if (topo === 'WRAP_PERIODIC') {
    // subtle wrap indicators on opposite edges
    ctx.strokeStyle = chrome.wrap;
    ctx.setLineDash([4, 4]);
    ctx.lineWidth = 1.5;
    ctx.strokeRect(ox + 0.5, oy + 0.5, ww - 1, hh - 1);
    ctx.setLineDash([]);
    ctx.fillStyle = chrome.wrapLabel;
    ctx.font = chrome.fontUi;
    ctx.fillText('WRAP ↔ periodic edges', ox + 6, oy + 12);
  } else if (topo === 'CLOSED') {
    ctx.strokeStyle = 'rgba(248,113,113,0.9)';
    ctx.lineWidth = 2;
    ctx.strokeRect(ox + 1, oy + 1, ww - 2, hh - 2);
  } else if (topo === 'OPEN') {
    ctx.strokeStyle = chrome.annotateMuted;
    ctx.lineWidth = 1;
    const t = 10;
    [[ox, oy, 1, 0, 0, 1], [ox + ww, oy, -1, 0, 0, 1], [ox, oy + hh, 1, 0, 0, -1], [ox + ww, oy + hh, -1, 0, 0, -1]].forEach((c) => {
      const [x, y, dx, dy, ex, ey] = c as number[];
      ctx.beginPath();
      ctx.moveTo(x, y);
      ctx.lineTo(x + dx * t, y + dy * t);
      ctx.moveTo(x, y);
      ctx.lineTo(x + ex * t, y + ey * t);
      ctx.stroke();
    });
    ctx.fillStyle = chrome.annotateMuted;
    ctx.font = chrome.fontUi;
    ctx.fillText('OPEN edges', ox + 6, oy + 12);
  }
}

function drawElevationOverlay(
  ctx: CanvasRenderingContext2D,
  vd: VerticalDisplayContract,
  ox: number,
  oy: number,
  cell: number,
  opacity: number,
) {
  const grid = vd.cell_centre_elevation?.data;
  if (!grid) return;
  const lo = Number(vd.elev_min ?? vd.cell_centre_elevation?.elev_min ?? 0);
  const hi = Number(vd.elev_max ?? vd.cell_centre_elevation?.elev_max ?? 1);
  const gh = grid.length;
  const gw = grid[0]?.length || 0;
  for (let y = 0; y < gh; y++) {
    for (let x = 0; x < gw; x++) {
      const v = Number(grid[y][x]);
      if (!Number.isFinite(v)) continue;
      ctx.fillStyle = elevationColor(v, lo, hi, Math.min(0.85, 0.35 + opacity * 0.5));
      ctx.fillRect(ox + x * cell, oy + y * cell, cell + 0.5, cell + 0.5);
    }
  }
}

function drawDeltaOverlay(
  ctx: CanvasRenderingContext2D,
  vd: VerticalDisplayContract,
  ox: number,
  oy: number,
  cell: number,
  opacity: number,
) {
  const deltas = vd.sparse_deltas || [];
  let maxAbs = 1e-6;
  for (const d of deltas) {
    const a = Math.abs(Number(d.signed_delta) || 0);
    if (a > maxAbs) maxAbs = a;
  }
  for (const d of deltas) {
    const x = Number(d.cell_x);
    const y = Number(d.cell_y);
    const signed = Number(d.signed_delta);
    if (!Number.isFinite(signed)) continue;
    ctx.fillStyle = deltaColor(signed, maxAbs, Math.min(0.9, 0.4 + opacity * 0.5));
    ctx.fillRect(ox + x * cell, oy + y * cell, cell + 0.5, cell + 0.5);
    // Stronger indication for deeper revisions (display only).
    const rev = Math.max(1, Number(d.revision) || 1);
    if (rev > 1) {
      ctx.strokeStyle = `rgba(15,23,42,${Math.min(0.85, 0.25 + 0.12 * rev)})`;
      ctx.lineWidth = 1;
      ctx.strokeRect(ox + x * cell + 1, oy + y * cell + 1, cell - 2, cell - 2);
    }
  }
}

function drawElevationContours(
  ctx: CanvasRenderingContext2D,
  vd: VerticalDisplayContract,
  ox: number,
  oy: number,
  cell: number,
) {
  // RENDER_DERIVED_NON_AUTHORITATIVE — optional; never used for support/collision.
  const grid = vd.cell_centre_elevation?.data;
  if (!grid) return;
  const lo = Number(vd.elev_min ?? 0);
  const hi = Number(vd.elev_max ?? 1);
  if (!(hi > lo)) return;
  const levels = 6;
  ctx.strokeStyle = 'rgba(15,23,42,0.35)';
  ctx.lineWidth = 1;
  const gh = grid.length;
  const gw = grid[0]?.length || 0;
  for (let li = 1; li < levels; li++) {
    const level = lo + (hi - lo) * (li / levels);
    for (let y = 0; y < gh - 1; y++) {
      for (let x = 0; x < gw - 1; x++) {
        const v00 = Number(grid[y][x]);
        const v10 = Number(grid[y][x + 1]);
        const v01 = Number(grid[y + 1][x]);
        const crossH = (v00 - level) * (v10 - level) < 0;
        const crossV = (v00 - level) * (v01 - level) < 0;
        if (crossH) {
          const t = (level - v00) / ((v10 - v00) || 1e-12);
          ctx.beginPath();
          ctx.moveTo(ox + (x + t) * cell, oy + (y + 0.5) * cell);
          ctx.lineTo(ox + (x + t) * cell, oy + (y + 0.5) * cell + 0.01);
          ctx.stroke();
        }
        if (crossV) {
          const t = (level - v00) / ((v01 - v00) || 1e-12);
          ctx.beginPath();
          ctx.moveTo(ox + (x + 0.5) * cell, oy + (y + t) * cell);
          ctx.lineTo(ox + (x + 0.5) * cell + 0.01, oy + (y + t) * cell);
          ctx.stroke();
        }
      }
    }
  }
}

function drawVerticalLegend(
  ctx: CanvasRenderingContext2D,
  W: number,
  H: number,
  mode: 'ELEVATION' | 'DELTA',
  lo: number,
  hi: number,
  exaggeration: number,
  vd?: VerticalDisplayContract | null,
) {
  const x0 = W - 148;
  const y0 = 48;
  ctx.fillStyle = 'rgba(15,23,42,0.72)';
  ctx.fillRect(x0 - 8, y0 - 14, 140, mode === 'DELTA' ? 78 : 64);
  ctx.fillStyle = '#e2e8f0';
  ctx.font = '11px ui-monospace, monospace';
  ctx.fillText(mode === 'ELEVATION' ? 'ELEVATION (world z)' : 'TERRAIN Δ (world z)', x0, y0);
  if (mode === 'ELEVATION') {
    for (let i = 0; i < 48; i++) {
      const t = i / 47;
      const v = lo + (hi - lo) * t;
      ctx.fillStyle = elevationColor(v, lo, hi, 1);
      ctx.fillRect(x0 + i * 2, y0 + 8, 2, 10);
    }
    ctx.fillStyle = '#cbd5e1';
    ctx.fillText(`${lo.toFixed(3)} … ${hi.toFixed(3)}`, x0, y0 + 34);
    ctx.fillText('1× physical elev · false color', x0, y0 + 48);
  } else {
    const deltas = vd?.sparse_deltas || [];
    let maxAbs = 0;
    for (const d of deltas) maxAbs = Math.max(maxAbs, Math.abs(Number(d.signed_delta) || 0));
    ctx.fillStyle = '#94a3b8';
    ctx.fillText(`unchanged = transparent`, x0, y0 + 16);
    ctx.fillText(`excavated Δ min ${(-maxAbs).toFixed(3)}`, x0, y0 + 30);
    ctx.fillText(`raised Δ max ${maxAbs.toFixed(3)}`, x0, y0 + 44);
    ctx.fillText(`n=${deltas.length} · rev in tooltip`, x0, y0 + 58);
  }
  void exaggeration;
  void H;
}

function drawClearanceStems(
  ctx: CanvasRenderingContext2D,
  vd: VerticalDisplayContract,
  ox: number,
  oy: number,
  cell: number,
  exaggeration: number,
) {
  for (const e of vd.entities_vertical || []) {
    if (!e || e.z_available === false) continue;
    const clearance = Number(e.clearance);
    const bx = ox + Number(e.x) * cell;
    const by = oy + Number(e.y) * cell;
    // Ground-projection anchor at authoritative x/y (always).
    ctx.fillStyle = 'rgba(226,232,240,0.85)';
    ctx.beginPath();
    ctx.arc(bx, by, Math.max(1.5, cell * 0.06), 0, Math.PI * 2);
    ctx.fill();
    // Honest MAP diagnostic: feet below finite support (not an on-surface glyph).
    if (e.below_support === true || e.vertical_out_of_slice === true || (Number.isFinite(clearance) && clearance < -1e-9)) {
      ctx.strokeStyle = 'rgba(244,63,94,0.95)';
      ctx.lineWidth = 2;
      const r = Math.max(3, cell * 0.22);
      ctx.beginPath();
      ctx.arc(bx, by, r, 0, Math.PI * 2);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(bx - r * 0.6, by - r * 0.6);
      ctx.lineTo(bx + r * 0.6, by + r * 0.6);
      ctx.moveTo(bx + r * 0.6, by - r * 0.6);
      ctx.lineTo(bx - r * 0.6, by + r * 0.6);
      ctx.stroke();
    }
    const stem = clearanceStemPx(clearance, cell, exaggeration);
    if (stem <= 0.5) continue;
    const held = !!e.held_constrained || String(e.physical_state || '') === 'HELD';
    const unsupported = String(e.support_state || '') === 'UNSUPPORTED' || e.grounded === false;
    ctx.strokeStyle = held
      ? 'rgba(245,158,11,0.9)'
      : unsupported
        ? 'rgba(56,189,248,0.95)'
        : 'rgba(148,163,184,0.75)';
    ctx.lineWidth = held ? 2 : 1.5;
    ctx.beginPath();
    ctx.moveTo(bx, by);
    // Screen-space stem upward (display convention; not physical displacement of glyph).
    ctx.lineTo(bx, by - stem);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(bx, by - stem, Math.max(2, cell * 0.08), 0, Math.PI * 2);
    ctx.fillStyle = ctx.strokeStyle;
    ctx.fill();
    const vz = Number(e.vz);
    if (Number.isFinite(vz) && Math.abs(vz) > 1e-6) {
      const dir = vz < 0 ? 1 : -1; // falling → tip toward support
      ctx.strokeStyle = 'rgba(244,63,94,0.9)';
      ctx.beginPath();
      ctx.moveTo(bx + cell * 0.18, by - stem * 0.5);
      ctx.lineTo(bx + cell * 0.18, by - stem * 0.5 + dir * Math.min(cell * 0.35, 8 + Math.abs(vz) * cell * 2));
      ctx.stroke();
    }
  }
}

function drawObserverAcousticProbeGlyph(
  ctx: CanvasRenderingContext2D,
  world: any,
  ox: number,
  oy: number,
  cell: number,
) {
  const probe = world?.observer_acoustic_probe;
  if (!probe || !probe.enabled) return;
  const glyph = probe.map_glyph || probe;
  const x = Number(glyph.x ?? probe.x);
  const y = Number(glyph.y ?? probe.y);
  if (!Number.isFinite(x) || !Number.isFinite(y)) return;
  const px = ox + x * cell;
  const py = oy + y * cell;
  const r = Math.max(4, cell * 0.28);
  // Researcher-only listener marker — NOT an entity, source, or hearing radius.
  ctx.save();
  ctx.strokeStyle = 'rgba(244,114,182,0.95)';
  ctx.fillStyle = 'rgba(244,114,182,0.25)';
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(px, py - r);
  ctx.lineTo(px + r, py);
  ctx.lineTo(px, py + r);
  ctx.lineTo(px - r, py);
  ctx.closePath();
  ctx.fill();
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(px, py, 1.5, 0, Math.PI * 2);
  ctx.fillStyle = 'rgba(244,114,182,0.95)';
  ctx.fill();
  ctx.font = '9px sans-serif';
  ctx.fillStyle = 'rgba(244,114,182,0.9)';
  ctx.fillText('PROBE', px + r + 2, py - 2);
  ctx.restore();
}

function drawVerticalEventMarkers(
  ctx: CanvasRenderingContext2D,
  vd: VerticalDisplayContract,
  ox: number,
  oy: number,
  cell: number,
  tick: number,
) {
  const life = Number(vd.event_display_lifetime_ticks || 32);
  for (const ev of vd.events_recent || []) {
    const et = Number(ev.tick || 0);
    if (tick > 0 && et < tick - life) continue;
    const x = Number(ev.x);
    const y = Number(ev.y);
    if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
    const px = ox + x * cell;
    const py = oy + y * cell;
    const age = tick > 0 ? Math.max(0, tick - et) : 0;
    const fade = Math.max(0.25, 1 - age / Math.max(1, life));
    const cls = String(ev.event_class || '');
    let stroke = 'rgba(148,163,184,0.8)';
    let shape: 'diamond' | 'square' | 'triangle' | 'ring' = 'diamond';
    if (cls === 'RELEASE') {
      stroke = `rgba(251,191,36,${fade})`;
      shape = 'diamond';
    } else if (cls === 'SUPPORT_LOSS') {
      stroke = `rgba(168,85,247,${fade})`;
      shape = 'square';
    } else if (cls === 'LANDING_RESPONSE') {
      stroke = `rgba(34,197,94,${fade})`;
      shape = 'triangle';
    } else if (cls === 'ACOUSTIC_EMISSION') {
      stroke = `rgba(56,189,248,${fade})`;
      shape = 'ring';
    }
    const r = Math.max(3, cell * 0.22);
    ctx.strokeStyle = stroke;
    ctx.fillStyle = stroke;
    ctx.lineWidth = 1.5;
    if (shape === 'ring') {
      // Display-only pulse — NOT audio playback.
      ctx.beginPath();
      ctx.arc(px, py, r * (1.2 + 0.4 * fade), 0, Math.PI * 2);
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(px, py, r * 0.45, 0, Math.PI * 2);
      ctx.fill();
    } else if (shape === 'square') {
      ctx.strokeRect(px - r, py - r, r * 2, r * 2);
    } else if (shape === 'triangle') {
      ctx.beginPath();
      ctx.moveTo(px, py - r);
      ctx.lineTo(px + r, py + r);
      ctx.lineTo(px - r, py + r);
      ctx.closePath();
      ctx.stroke();
    } else {
      ctx.beginPath();
      ctx.moveTo(px, py - r);
      ctx.lineTo(px + r, py);
      ctx.lineTo(px, py + r);
      ctx.lineTo(px - r, py);
      ctx.closePath();
      ctx.stroke();
    }
  }
}

function trailSampleScreen(
  s: VerticalTrailSample,
  ox: number,
  oy: number,
  cell: number,
  exaggeration: number,
): { gx: number; gy: number; dx: number; dy: number } {
  const gx = ox + Number(s.x) * cell;
  const gy = oy + Number(s.y) * cell;
  const stem = clearanceStemPx(s.clearance, cell, exaggeration);
  return { gx, gy, dx: gx, dy: gy - stem };
}

function drawVerticalTrails(
  ctx: CanvasRenderingContext2D,
  vd: VerticalDisplayContract,
  ox: number,
  oy: number,
  cell: number,
  exaggeration: number,
  mode: TrailDisplayMode,
  lengthMode: TrailLengthMode,
  selectedEntityId: string | null,
  worldW: number,
  worldH: number,
) {
  const maxSamples = TRAIL_LENGTH_SAMPLES[lengthMode] || 32;
  const segments = filterTrailSegments(vd.trail_segments, mode, selectedEntityId, maxSamples);
  for (const seg of segments) {
    const samples = seg.samples || [];
    if (samples.length < 1) continue;
    const pieces = splitTrailOnWrap(samples, worldW, worldH);
    const n = Math.max(1, samples.length - 1);
    for (const piece of pieces) {
      if (piece.length < 1) continue;
      ctx.lineWidth = 1.5;
      ctx.lineJoin = 'round';
      for (let i = 1; i < piece.length; i++) {
        const a = piece[i - 1];
        const b = piece[i];
        const pa = trailSampleScreen(a, ox, oy, cell, exaggeration);
        const pb = trailSampleScreen(b, ox, oy, cell, exaggeration);
        const age = i / n;
        const alpha = 0.25 + 0.7 * age;
        const descending = (Number(b.clearance) || 0) > (Number(a.clearance) || 0) + 1e-9
          || (Number(b.vz) || 0) < -1e-6;
        ctx.strokeStyle = descending
          ? `rgba(56,189,248,${alpha})`
          : `rgba(148,163,184,${alpha})`;
        if (seg.start_reason === 'RELEASE' && i === 1) ctx.strokeStyle = `rgba(251,191,36,${alpha})`;
        if (seg.start_reason === 'SUPPORT_LOSS' && i === 1) ctx.strokeStyle = `rgba(168,85,247,${alpha})`;
        ctx.beginPath();
        ctx.moveTo(pa.dx, pa.dy);
        ctx.lineTo(pb.dx, pb.dy);
        ctx.stroke();
      }
      // Authoritative sample points (exact ticks) — not interpolated.
      for (let i = 0; i < piece.length; i++) {
        const s = piece[i];
        const p = trailSampleScreen(s, ox, oy, cell, exaggeration);
        // Ground projection marker at authoritative x/y.
        ctx.fillStyle = 'rgba(226,232,240,0.55)';
        ctx.beginPath();
        ctx.arc(p.gx, p.gy, Math.max(1.2, cell * 0.04), 0, Math.PI * 2);
        ctx.fill();
        const isStart = i === 0;
        const isEnd = i === piece.length - 1;
        const clearance = Number(s.clearance);
        const atSupport = !Number.isFinite(clearance) || clearance <= 1e-9;
        ctx.fillStyle = isStart && seg.start_reason === 'RELEASE'
          ? 'rgba(251,191,36,0.95)'
          : isStart && seg.start_reason === 'SUPPORT_LOSS'
            ? 'rgba(168,85,247,0.95)'
            : isEnd && atSupport
              ? 'rgba(34,197,94,0.95)'
              : 'rgba(125,211,252,0.9)';
        ctx.beginPath();
        ctx.arc(p.dx, p.dy, Math.max(1.8, cell * 0.07), 0, Math.PI * 2);
        ctx.fill();
      }
    }
  }
}
