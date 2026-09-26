/** FPV = diagnostic reconstruction of canonical pre-aggregation samples. */

export type FpvSample = {
  fwd: number;
  left: number;
  status: string;
  sector: string | null;
  sector_index: number | null;
  spatial_sector_index?: number | null;
  spatial_sector_label?: string | null;
  visibility?: string | null;
  occluded_by?: number[] | null;
  visible_contribution?: number | null;
  dist_f: number | null;
  illumination: number | null;
  surface_response?: number;
  body_optical?: number;
  composed?: number;
  final: number;
  c0?: number;
  c1?: number;
  c2?: number;
  surface_channels?: string;
  world_cell?: number[];
  temporal?: string | null;
  note?: string;
};

export type EyeLink = {
  sector: 'LEFT' | 'FORWARD' | 'RIGHT' | string;
  channel: 'exo' | 'c0' | 'c1' | 'c2' | 'spatial';
  spatialIndex?: number;
} | null;

export function falseColorRgb(s: FpvSample, disc: string): string {
  const d = String(disc || 'OFF').toUpperCase();
  if (d === 'OFF' || s.surface_channels === 'ABSENT') {
    const v = Math.max(0, Math.min(1, Number(s.composed ?? s.final ?? 0)));
    const g = Math.round(v * 220);
    return `rgb(${g},${g},${g})`;
  }
  const c0 = Math.max(0, Math.min(1, Number(s.c0 || 0)));
  if (d === 'LOW') {
    const g = Math.round(c0 * 255);
    return `rgb(${g},${Math.round(g * 0.85)},${Math.round(g * 0.55)})`;
  }
  const c1 = Math.max(0, Math.min(1, Number(s.c1 || 0)));
  const c2 = Math.max(0, Math.min(1, Number(s.c2 || 0)));
  return `rgb(${Math.round(c0 * 255)},${Math.round(c1 * 255)},${Math.round(c2 * 255)})`;
}

const SPATIAL_RGB = [
  '96,165,250',
  '167,139,250',
  '251,191,36',
  '52,211,153',
  '244,114,182',
];

export function contributionFill(s: FpvSample, spatialVision?: string): string {
  const v = Math.max(0, Math.min(1, Number(s.final || 0)));
  if (s.status === 'occluded') return `rgba(248,113,113,${0.12 + 0.4 * v})`;
  const spatial = String(spatialVision || 'LEGACY').toUpperCase() !== 'LEGACY';
  if (spatial && s.spatial_sector_index != null) {
    const rgb = SPATIAL_RGB[Math.max(0, Math.min(4, Number(s.spatial_sector_index)))] || SPATIAL_RGB[0];
    return `rgba(${rgb},${0.15 + 0.85 * v})`;
  }
  const sector = String(s.sector || '');
  if (sector === 'LEFT') return `rgba(96,165,250,${0.15 + 0.85 * v})`;
  if (sector === 'FORWARD') return `rgba(251,191,36,${0.15 + 0.85 * v})`;
  if (sector === 'RIGHT') return `rgba(52,211,153,${0.15 + 0.85 * v})`;
  return `rgba(148,163,184,${0.12 + 0.5 * v})`;
}

export function spatialBinLabel(s: FpvSample): string {
  if (s.spatial_sector_label) return String(s.spatial_sector_label).toUpperCase();
  if (s.spatial_sector_index == null) return '';
  return `A${Number(s.spatial_sector_index)}`;
}

export function gridIndex(fwd: number, left: number, radius: number): { row: number; col: number } {
  const r = Math.max(1, Math.min(3, radius));
  const col = Math.max(0, Math.min(2 * r, r - Math.round(left)));
  const row = Math.max(0, Math.min(2 * r, r - Math.round(fwd)));
  return { row, col };
}

export function sampleMatchesLink(s: FpvSample, link: EyeLink): boolean {
  if (!link) return false;
  if (link.channel === 'spatial') {
    return s.spatial_sector_index === link.spatialIndex && s.status === 'accepted';
  }
  if (!s.sector) return false;
  return s.sector === link.sector;
}
