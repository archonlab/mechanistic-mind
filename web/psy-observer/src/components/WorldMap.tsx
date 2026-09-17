import { useEffect, useMemo, useRef, useState } from 'react';
import { occupancyCounts, periodicSegments, scalarGrid } from '../rendererMath';

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
  onHoverCell?: (info: { ix: number; iy: number; value: number | null; field: string } | null) => void;
  onSelectCell?: (info: { ix: number; iy: number; value: number | null; field: string } | null) => void;
  layers?: Record<string, boolean>;
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
  trajectory = [], onHoverCell,
  onSelectCell,
  layers = { body: true, sites: true, trajectory: true, velocity: true, orientation: true, deformation: true, occupancy: false, force: false },
}: Props) {
  const ref = useRef<HTMLCanvasElement | null>(null);
  const [cam, setCam] = useState({ x: 0, y: 0, zoom: 1 });
  const drag = useRef<{ x: number; y: number; cx: number; cy: number } | null>(null);
  const boundary = world?.boundary;
  const topo = boundary?.spatial_topology || 'WRAP_PERIODIC';

  const scalarIds = useMemo(() => {
    if (renderMode === 'COMPOSITE') return compositeLayers.length ? compositeLayers : [layer];
    return [layer];
  }, [renderMode, compositeLayers, layer]);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas || !world) return;
    const parent = canvas.parentElement!;
    const W = parent.clientWidth;
    const H = parent.clientHeight;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    canvas.width = Math.floor(W * dpr);
    canvas.height = Math.floor(H * dpr);
    canvas.style.width = `${W}px`;
    canvas.style.height = `${H}px`;
    const ctx = canvas.getContext('2d')!;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = '#070b10';
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
      ctx.fillStyle = 'rgba(7,11,16,0.55)';
      ctx.fillRect(0, 0, W, H);
      ctx.fillStyle = '#d7e0ea';
      ctx.font = '12px ui-monospace, monospace';
      let ty = 22;
      ctx.fillText('AGENT PERCEPTION — accessible scalars only', 12, ty); ty += 16;
      ctx.fillStyle = '#94a3b8';
      ctx.fillText('Backdrop: WORLD GROUND TRUTH (dimmed, not agent-visible maps)', 12, ty); ty += 18;
      ctx.fillStyle = '#22c55e';
      ctx.fillText('AGENT ACCESSIBLE:', 12, ty); ty += 14;
      const obs = perception?.agent_observation || {};
      Object.entries(obs).forEach(([k, v]) => {
        ctx.fillStyle = '#e2e8f0';
        ctx.fillText(`  ${k} = ${Number(v).toFixed(5)}`, 12, ty);
        ty += 13;
      });
      ty += 6;
      ctx.fillStyle = '#f59e0b';
      ctx.fillText('NOT OBSERVED / NOT AVAILABLE:', 12, ty); ty += 14;
      (perception?.unavailable || []).forEach((u: string) => {
        ctx.fillText(`  ${u}`, 12, ty); ty += 13;
      });
      drawBoundaryChrome(ctx, W, H, ox, oy, gw * cell, gh * cell, topo);
      if (layers.body) {
        drawBody(ctx, body, ox, oy, cell, layers);
        (world.entities?.bodies || []).forEach((b: any, i: number) => {
          if (i === 0) return;
          drawBody(ctx, { ...body, x: b.x, y: b.y, theta: b.theta || 0 }, ox, oy, cell, { ...layers, sites: false, deformation: false }, '#f97316');
        });
      }
      return;
    }

    if (viewMode === 'PREDICTED') {
      ctx.fillStyle = '#e2e8f0';
      ctx.font = '12px monospace';
      ctx.fillText('PREDICTED spatial field: NOT AVAILABLE in Current MM', 12, 24);
      ctx.fillStyle = '#f59e0b';
      ctx.fillText('Use MIND / causal PREDICTION for structure snapshots (not a second world map).', 12, 44);
      return;
    }
    if (viewMode === 'DIFFERENCE') {
      ctx.fillStyle = '#f59e0b';
      ctx.font = '12px monospace';
      ctx.fillText('DIFFERENCE: NOT AVAILABLE unless two comparable buffered frames are selected', 12, 24);
      return;
    }

    const primary = getScalar(world, scalarIds[0] || 'T');
    const gh = primary?.length || world.height || 32;
    const gw = primary?.[0]?.length || world.width || 32;
    const cell = Math.min(W / gw, H / gh) * cam.zoom;
    const ox = (W - gw * cell) / 2 + cam.x;
    const oy = (H - gh * cell) / 2 + cam.y;

    // field render
    if (renderMode === 'COMPOSITE') {
      const alphas = [opacity, opacity * 0.55, opacity * 0.4];
      scalarIds.slice(0, 3).forEach((id, idx) => {
        const g = getScalar(world, id);
        if (!g) return;
        const { lo, hi } = rangeOf(g, autoScale, scaleMin, scaleMax);
        drawField(ctx, g, ox, oy, cell, renderMode === 'COMPOSITE' ? 'SMOOTH' : renderMode, lo, hi, alphas[idx] ?? 0.4, contourLevels);
      });
    } else if (renderMode === 'VECTOR') {
      // optional scalar backdrop
      if (primary) {
        const { lo, hi } = rangeOf(primary, autoScale, scaleMin, scaleMax);
        drawField(ctx, primary, ox, oy, cell, 'SMOOTH', lo, hi, Math.min(0.35, opacity), contourLevels);
      }
      drawVectors(ctx, world, ox, oy, cell, vectorDensity, opacity);
    } else if (primary) {
      const { lo, hi } = rangeOf(primary, autoScale, scaleMin, scaleMax);
      drawField(ctx, primary, ox, oy, cell, renderMode, lo, hi, opacity, contourLevels);
    }

    if (showGrid && cell > 6) {
      ctx.strokeStyle = 'rgba(255,255,255,0.06)';
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

    // trajectory
    if (layers.trajectory && trajectory.length > 1) {
      ctx.strokeStyle = 'rgba(96,165,250,0.85)';
      ctx.lineWidth = 1.5;
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

    drawBoundaryChrome(ctx, W, H, ox, oy, gw * cell, gh * cell, topo);
    if (layers.body) {
      drawBody(ctx, body, ox, oy, cell, layers);
      (world.entities?.bodies || []).forEach((b: any, i: number) => {
        if (i === 0) return;
        drawBody(ctx, { ...body, x: b.x, y: b.y, theta: b.theta || 0 }, ox, oy, cell, { ...layers, sites: false, deformation: false }, '#f97316');
      });
    }

    // labels
    ctx.fillStyle = 'rgba(226,232,240,0.85)';
    ctx.font = '11px ui-monospace, monospace';
    ctx.fillText(`${world.width}×${world.height} · ${topo} · ${renderMode} · field=${scalarIds.join('+')}`, 10, H - 10);
  }, [world, body, layer, viewMode, perception, renderMode, opacity, showGrid, vectorDensity, contourLevels, autoScale, scaleMin, scaleMax, scalarIds, cam, trajectory, topo, layers]);

  function clientToCell(e: React.MouseEvent) {
    const canvas = ref.current;
    if (!canvas || !world) return null;
    const rect = canvas.getBoundingClientRect();
    const primary = getScalar(world, scalarIds[0] || 'T');
    const gh = primary?.length || world.height || 32;
    const gw = primary?.[0]?.length || world.width || 32;
    const W = rect.width;
    const H = rect.height;
    const cell = Math.min(W / gw, H / gh) * cam.zoom;
    const ox = (W - gw * cell) / 2 + cam.x;
    const oy = (H - gh * cell) / 2 + cam.y;
    const x = (e.clientX - rect.left - ox) / cell;
    const y = (e.clientY - rect.top - oy) / cell;
    const ix = Math.floor(x);
    const iy = Math.floor(y);
    if (ix < 0 || iy < 0 || ix >= gw || iy >= gh || !primary) return { ix, iy, value: null as number | null, field: scalarIds[0] };
    return { ix, iy, value: Number(primary[iy][ix]), field: scalarIds[0] };
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
        onHoverCell?.(clientToCell(e));
      }}
      onMouseUp={() => { drag.current = null; }}
      onClick={(e) => onSelectCell?.(clientToCell(e))}
      onMouseLeave={() => { drag.current = null; onHoverCell?.(null); }}
    >
      <canvas className="map" ref={ref} />
    </div>
  );
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
    ctx.strokeStyle = `rgba(255,255,255,${0.35 * alpha})`;
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
  const vx = world.vx; const vy = world.vy;
  if (!vx || !vy) return;
  const gh = vx.length; const gw = vx[0].length;
  const step = Math.max(1, Math.round(1 / Math.max(0.05, Math.min(1, density))));
  ctx.strokeStyle = `rgba(226,232,240,${0.75 * alpha})`;
  ctx.fillStyle = `rgba(226,232,240,${0.75 * alpha})`;
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

function drawBody(
  ctx: CanvasRenderingContext2D, body: any, ox: number, oy: number,
  cell: number, layers: Record<string, boolean>,
  fill = '#3b82f6',
) {
  if (!body) return;
  const bx = ox + Number(body.x) * cell;
  const by = oy + Number(body.y) * cell;
  const r = Math.max(4, cell * 0.4);
  ctx.beginPath();
  ctx.arc(bx, by, r + 3, 0, Math.PI * 2);
  ctx.strokeStyle = 'rgba(255,255,255,0.85)';
  ctx.lineWidth = 1.5;
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(bx, by, r, 0, Math.PI * 2);
  ctx.fillStyle = fill;
  ctx.fill();
  if (layers.orientation) {
    const theta = Number(body.theta || 0);
    ctx.strokeStyle = '#fbbf24';
    ctx.beginPath(); ctx.moveTo(bx, by);
    ctx.lineTo(bx + Math.cos(theta) * (r + 10), by + Math.sin(theta) * (r + 10));
    ctx.stroke();
    const omega = Number(body.omega || 0);
    if (Math.abs(omega) > 1e-6) {
      ctx.strokeStyle = 'rgba(251,191,36,0.7)';
      ctx.beginPath();
      ctx.arc(bx, by, r + 14, theta, theta + Math.max(-Math.PI / 2, Math.min(Math.PI / 2, omega * 4)), omega < 0);
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
      ctx.strokeStyle = 'rgba(255,255,255,.6)'; ctx.stroke();
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
        ctx.setLineDash([3, 3]); ctx.strokeStyle = 'rgba(226,232,240,0.55)';
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
  ctx.fillStyle = '#e2e8f0';
  ctx.font = '11px sans-serif';
  ctx.fillText('body-0', bx + r + 4, by - 4);
}

function drawBoundaryChrome(
  ctx: CanvasRenderingContext2D, _W: number, _H: number,
  ox: number, oy: number, ww: number, hh: number, topo: string,
) {
  if (topo === 'WRAP_PERIODIC') {
    // subtle wrap indicators on opposite edges
    ctx.strokeStyle = 'rgba(56,189,248,0.55)';
    ctx.setLineDash([4, 4]);
    ctx.lineWidth = 1.5;
    ctx.strokeRect(ox + 0.5, oy + 0.5, ww - 1, hh - 1);
    ctx.setLineDash([]);
    ctx.fillStyle = 'rgba(56,189,248,0.8)';
    ctx.font = '10px sans-serif';
    ctx.fillText('WRAP ↔ periodic edges', ox + 6, oy + 12);
  } else if (topo === 'CLOSED') {
    ctx.strokeStyle = 'rgba(248,113,113,0.9)';
    ctx.lineWidth = 2;
    ctx.strokeRect(ox + 1, oy + 1, ww - 2, hh - 2);
  } else if (topo === 'OPEN') {
    // open edges: no closed room frame; fade edges
    // just corner ticks
    ctx.strokeStyle = 'rgba(148,163,184,0.5)';
    ctx.lineWidth = 1;
    const t = 10;
    // corners only
    [[ox, oy, 1, 0, 0, 1], [ox + ww, oy, -1, 0, 0, 1], [ox, oy + hh, 1, 0, 0, -1], [ox + ww, oy + hh, -1, 0, 0, -1]].forEach((c) => {
      const [x, y, dx, dy, ex, ey] = c as number[];
      ctx.beginPath();
      ctx.moveTo(x, y);
      ctx.lineTo(x + dx * t, y + dy * t);
      ctx.moveTo(x, y);
      ctx.lineTo(x + ex * t, y + ey * t);
      ctx.stroke();
    });
    ctx.fillStyle = 'rgba(148,163,184,0.8)';
    ctx.font = '10px sans-serif';
    ctx.fillText('OPEN edges', ox + 6, oy + 12);
  }
}
