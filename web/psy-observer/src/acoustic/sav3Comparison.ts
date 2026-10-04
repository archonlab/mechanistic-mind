/**
 * SAV3 — pure display helpers over ORGANISM_AUDITORY_TRANSFORMATION_TRACE_V1.
 * Does not recompute phenotype/A5 authority. Bar widths are display-derived only.
 */

export const SAV3_SCHEMA = 'SELECTED_ORGANISM_PHYSICAL_FIELD_COMPARISON_SAV3_V1';
export const SAV3_CAPABILITY = 'selected_organism_physical_field_comparison';
export const SAV3_PROFILE = 'A3_TO_A5_CAUSAL_COMPARISON_SAV3_V1';
export const SAV3_TITLE = 'PHYSICAL FIELD → ORGANISM RECEPTORS';
export const SAV3_WARNING =
  'RESEARCHER CAUSAL COMPARISON · ONLY A5 IS ORGANISM-ACCESSIBLE · NOT SUBJECTIVE EXPERIENCE';
export const SAV3_A3_BADGE = 'AUTHORITATIVE PHYSICAL RECEPTOR STATE · RESEARCHER-ONLY';
export const SAV3_A4_BADGE = 'DETERMINISTIC RESEARCHER VERIFICATION';
export const SAV3_A5_BADGE = 'AUTHORITATIVE ORGANISM-ACCESSIBLE OBSERVATION';
export const SAV3_RENDER_BADGE = 'DISPLAY-DERIVED · NOT SCIENTIFIC STATE';

export const BAND_COUNT = 6;

/** Fixed A5 display scale [0,1]. A3 uses clip_upper as unit + overflow mark. */
export const A5_BAR_MAX = 1.0;

export type Sav3Status =
  | 'TRACE_AVAILABLE'
  | 'TRACE_NOT_YET_AVAILABLE'
  | 'TRACE_MISMATCH'
  | 'A5_LINK_UNAVAILABLE'
  | 'SELECTED_BODY_UNAVAILABLE'
  | 'EXPERIMENTER_AUDITORY_COMPARISON_NOT_AVAILABLE'
  | 'LEGACY_TRACE_UNAVAILABLE'
  | 'INCOMPATIBLE_TRACE_PROFILE'
  | string;

export function num(v: unknown, fallback = 0): number {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

export function isFiniteNum(v: unknown): boolean {
  const n = Number(v);
  return Number.isFinite(n);
}

/** Display width for A5 in [0,1] fixed scale. Does not alter scientific values. */
export function a5BarWidthPx(value: unknown, maxPx = 48): number {
  if (!isFiniteNum(value)) return 0;
  const v = Math.max(0, Math.min(A5_BAR_MAX, Number(value)));
  return Math.max(0, Math.round(v * maxPx));
}

/**
 * A3/scaled bar: unit = clip_upper (usually 1). Overflow (>1) saturates bar and flags overflow.
 * Not per-trace normalization.
 */
export function a3BarWidthPx(value: unknown, unitMax = 1.0, maxPx = 48): { width: number; overflow: boolean } {
  if (!isFiniteNum(value)) return { width: 0, overflow: false };
  const v = Number(value);
  const u = Math.max(1e-12, Number(unitMax) || 1);
  const overflow = v > u + 1e-12;
  const clipped = Math.max(0, Math.min(u, v));
  return { width: Math.max(0, Math.round((clipped / u) * maxPx)), overflow };
}

export function clipLabel(lower: boolean | undefined, upper: boolean | undefined): string {
  if (upper) return 'UPPER';
  if (lower) return 'LOWER';
  return 'NONE';
}

export function asymmetryA5(left: number[], right: number[]): number[] {
  const out: number[] = [];
  for (let i = 0; i < BAND_COUNT; i += 1) {
    out.push(num(left[i]) - num(right[i]));
  }
  return out;
}

export function totalActivation(vals: number[]): number {
  return vals.reduce((a, b) => a + num(b), 0);
}

export function transformPass(residual: any): { pass: boolean; max: number; tol: number } {
  const max = num(residual?.max_abs_residual, NaN);
  const tol = num(residual?.tolerance, 1e-12);
  const within = residual?.within_tolerance;
  if (typeof within === 'boolean') {
    return { pass: within, max: Number.isFinite(max) ? max : 0, tol };
  }
  if (!Number.isFinite(max)) return { pass: false, max: NaN, tol };
  return { pass: max <= tol, max, tol };
}

export function bandRowFromTrace(tr: any, i: number) {
  const a3 = tr?.a3 || {};
  const a4 = tr?.a4 || {};
  const a5 = tr?.a5 || {};
  const loss = Array.isArray(a4.per_band_loss_accounting) ? a4.per_band_loss_accounting : [];
  const leftLoss = loss.find((r: any) => r?.band === `band_${i}` && r?.side === 'left');
  const rightLoss = loss.find((r: any) => r?.band === `band_${i}` && r?.side === 'right');
  const a3L = a3.left_receptor_band_energy?.[i];
  const a3R = a3.right_receptor_band_energy?.[i];
  const scale = num(a4.sensor_scale, 2);
  const scaledL = leftLoss?.scaled_pre_clip ?? (isFiniteNum(a3L) ? Number(a3L) / Math.max(1e-9, scale) : NaN);
  const scaledR = rightLoss?.scaled_pre_clip ?? (isFiniteNum(a3R) ? Number(a3R) / Math.max(1e-9, scale) : NaN);
  return {
    band: `band_${i}`,
    a3L: a3L,
    a3R: a3R,
    scaledL,
    scaledR,
    a5L: a5.left_receptor_channels?.[i],
    a5R: a5.right_receptor_channels?.[i],
    clipL: clipLabel(a4.per_band_lower_clipped_left?.[i], a4.per_band_upper_clipped_left?.[i]),
    clipR: clipLabel(a4.per_band_lower_clipped_right?.[i], a4.per_band_upper_clipped_right?.[i]),
    resL: a4.transform_residual?.per_band_abs_residual_left?.[i],
    resR: a4.transform_residual?.per_band_abs_residual_right?.[i],
  };
}
