/** Pure display helpers for Tiktaalik Eye — no WorldMap RGB. */

export type SectorCell = {
  present: boolean;
  raw: number | null;
  saturated: boolean;
  pe_bin: { index: number; bins: number; label: string } | null;
  delta: number | null;
};

export function fmtRaw(cell: SectorCell | undefined): string {
  if (!cell || !cell.present || cell.raw == null) return 'ABSENT';
  return Number(cell.raw).toFixed(3);
}

export function fmtDelta(cell: SectorCell | undefined): string {
  if (!cell || !cell.present || cell.delta == null) return '—';
  const d = Number(cell.delta);
  const sign = d > 0 ? '+' : '';
  return `${sign}${d.toFixed(3)}`;
}

export function hasFakeDepth(payload: any): boolean {
  const txt = JSON.stringify(payload || {});
  return /"depth"|metres|terrain_height|slope_vision/i.test(txt);
}
