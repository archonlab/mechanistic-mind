import type { TrajectoryPoint } from './types';

export function scalarGrid(world: any, id: string): number[][] | null {
  if (world?.scalars?.[id]) return world.scalars[id];
  if (id === 'flow_mag' && world?.vx && world?.vy) {
    return world.vx.map((r: number[], y: number) =>
      r.map((v, x) => Math.hypot(Number(v), Number(world.vy[y][x]))));
  }
  if (id.startsWith('M') && world?.M) return world.M[Number(id.slice(1))] || null;
  return world?.[id] || null;
}

export function gridRange(grid: number[][] | null, lo?: number, hi?: number) {
  if (Number.isFinite(lo) && Number.isFinite(hi) && Number(hi) > Number(lo)) {
    return { lo: Number(lo), hi: Number(hi) };
  }
  const values = (grid || []).flat().map(Number).filter(Number.isFinite);
  if (!values.length) return { lo: 0, hi: 1 };
  const min = Math.min(...values), max = Math.max(...values);
  return { lo: min, hi: max > min ? max : min + 1e-9 };
}

export function periodicSegments(
  points: TrajectoryPoint[], width: number, height: number,
): TrajectoryPoint[][] {
  if (!points.length) return [];
  const out: TrajectoryPoint[][] = [[points[0]]];
  for (let i = 1; i < points.length; i++) {
    const a = points[i - 1], b = points[i];
    if (Math.abs(b.x - a.x) > width / 2 || Math.abs(b.y - a.y) > height / 2) {
      out.push([b]);
    } else {
      out[out.length - 1].push(b);
    }
  }
  return out.filter((s) => s.length > 0);
}

export function occupancyCounts(points: { x: number; y: number }[]) {
  const counts = new Map<string, number>();
  for (const p of points) {
    const key = `${Math.floor(Number(p.x))},${Math.floor(Number(p.y))}`;
    counts.set(key, (counts.get(key) || 0) + 1);
  }
  return counts;
}

