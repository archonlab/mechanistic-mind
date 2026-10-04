/** O6 SURFACE/LIGHT display transforms — researcher-only, not physical authority. */

import { simToRender, type Vec3 } from './occupancyVolumeProjection.ts';

export const O6_LABELS = [
  'RESEARCHER TRANSFORM',
  'ABSTRACT NON-SI OPTICAL BANDS',
  'NOT HUMAN RGB',
  'NOT ORGANISM VISION',
] as const;

export const CAUSAL_DISPLAY_COLORS: Record<string, string> = {
  DIRECT_ILLUMINATED: '#f2d27a',
  BACK_FACING_ZERO: '#4a5560',
  OCCLUDED_ZERO: '#2a3544',
  SOURCE_DISABLED_ZERO: '#1a2030',
  UNKNOWN_MATERIAL_RESPONSE: '#c45c8a',
  NOT_EVALUATED: '#666666',
  UNAVAILABLE: '#333333',
};

/** Fixed documented 6→display-RGB (not wavelength / not organism vision). */
export function compositeFalseColor(bands: number[] | null | undefined): [number, number, number] {
  const b = [...(bands || [0, 0, 0, 0, 0, 0])];
  while (b.length < 6) b.push(0);
  const clip = (x: number) => Math.max(0, Math.min(1, x));
  return [clip(0.5 * (b[0] + b[1])), clip(0.5 * (b[2] + b[3])), clip(0.5 * (b[4] + b[5]))];
}

export function rgbCss(rgb: [number, number, number], alpha = 0.92): string {
  const r = Math.round(rgb[0] * 255);
  const g = Math.round(rgb[1] * 255);
  const bl = Math.round(rgb[2] * 255);
  return `rgba(${r},${g},${bl},${alpha})`;
}

export type DisplayMode = 'CAUSAL_STATE' | 'BAND_AUDIT' | 'COMPOSITE_FALSE_COLOR' | 'MATERIAL_REFLECTANCE';

export type FacetDraw = {
  facet_id: string;
  face_class: string;
  cell_x: number;
  cell_y: number;
  corners: Vec3[];
  centre: Vec3;
  state_class: string;
  incident: number[];
  reflected: number[];
  reflectance: number[];
  area: number;
  span_lower: number;
  span_upper: number;
  o1_status: string | null;
};

export function facetCornersSim(f: {
  face_class: string;
  cell_x: number;
  cell_y: number;
  span_lower: number;
  span_upper: number;
  boundary_plane_coordinate: number;
}): Vec3[] {
  const face = String(f.face_class || '');
  const cx = Number(f.cell_x) || 0;
  const cy = Number(f.cell_y) || 0;
  const zLo = Number(f.span_lower) || 0;
  const zHi = Number(f.span_upper) || 0;
  const plane = Number(f.boundary_plane_coordinate);
  const toR = (x: number, y: number, z: number) => simToRender(x, y, z);
  if (face === 'FACE_TOP') {
    const z = Number.isFinite(plane) ? plane : zHi;
    return [toR(cx, cy, z), toR(cx + 1, cy, z), toR(cx + 1, cy + 1, z), toR(cx, cy + 1, z)];
  }
  if (face === 'FACE_BOTTOM') {
    const z = Number.isFinite(plane) ? plane : zLo;
    return [toR(cx, cy, z), toR(cx, cy + 1, z), toR(cx + 1, cy + 1, z), toR(cx + 1, cy, z)];
  }
  if (face === 'FACE_EAST') {
    const x = Number.isFinite(plane) ? plane : cx + 1;
    return [toR(x, cy, zLo), toR(x, cy + 1, zLo), toR(x, cy + 1, zHi), toR(x, cy, zHi)];
  }
  if (face === 'FACE_WEST') {
    const x = Number.isFinite(plane) ? plane : cx;
    return [toR(x, cy, zLo), toR(x, cy, zHi), toR(x, cy + 1, zHi), toR(x, cy + 1, zLo)];
  }
  if (face === 'FACE_SOUTH') {
    const y = Number.isFinite(plane) ? plane : cy + 1;
    return [toR(cx, y, zLo), toR(cx + 1, y, zLo), toR(cx + 1, y, zHi), toR(cx, y, zHi)];
  }
  if (face === 'FACE_NORTH') {
    const y = Number.isFinite(plane) ? plane : cy;
    return [toR(cx, y, zLo), toR(cx, y, zHi), toR(cx + 1, y, zHi), toR(cx + 1, y, zLo)];
  }
  return [toR(cx + 0.5, cy + 0.5, 0.5 * (zLo + zHi))];
}

export function expandColumnarFacets(col: any): FacetDraw[] {
  if (!col) return [];
  const enc = String(col.encoding || '');
  if (enc !== 'O6_COLUMNAR_FACETS_V1' && enc !== 'O6_COLUMNAR_FACETS_STATIC_V1') return [];
  const n = Number(col.n) || 0;
  const out: FacetDraw[] = [];
  for (let i = 0; i < n; i++) {
    const face_class = String(col.face_class?.[i] || '');
    const cell_x = Number(col.cell_x?.[i]) || 0;
    const cell_y = Number(col.cell_y?.[i]) || 0;
    const span_lower = Number(col.span_lower?.[i]) || 0;
    const span_upper = Number(col.span_upper?.[i]) || 0;
    const boundary_plane_coordinate = Number(col.boundary_plane_coordinate?.[i]) || 0;
    const c0 = col.centre?.[i * 3] ?? 0;
    const c1 = col.centre?.[i * 3 + 1] ?? 0;
    const c2 = col.centre?.[i * 3 + 2] ?? 0;
    const incident = (col.incident || []).slice(i * 6, i * 6 + 6);
    const reflected = (col.reflected || []).slice(i * 6, i * 6 + 6);
    const reflectance = (col.reflectance || []).slice(i * 6, i * 6 + 6);
    out.push({
      facet_id: String(col.facet_id?.[i] || `f${i}`),
      face_class,
      cell_x,
      cell_y,
      corners: facetCornersSim({
        face_class,
        cell_x,
        cell_y,
        span_lower,
        span_upper,
        boundary_plane_coordinate,
      }),
      centre: simToRender(c0, c1, c2),
      state_class: String(col.state_class?.[i] || 'NOT_EVALUATED'),
      incident,
      reflected,
      reflectance,
      area: Number(col.area?.[i]) || 0,
      span_lower,
      span_upper,
      o1_status: col.o1_status?.[i] ?? null,
    });
  }
  return out;
}

/** P3: merge held static geometry columns with dynamic optical columns. */
export function mergeStaticOpticalColumnar(staticCol: any, opticalCol: any): any {
  const st = staticCol || {};
  const op = opticalCol || {};
  return {
    encoding: 'O6_COLUMNAR_FACETS_V1',
    n: Number(st.n || op.n) || 0,
    facet_id: st.facet_id,
    face_class: st.face_class,
    cell_x: st.cell_x,
    cell_y: st.cell_y,
    interval_id: st.interval_id,
    centre: st.centre,
    normal: st.normal,
    area: st.area,
    span_lower: st.span_lower,
    span_upper: st.span_upper,
    boundary_plane_coordinate: st.boundary_plane_coordinate,
    o1_status: st.o1_status,
    reflectance: st.reflectance,
    state_class: op.state_class,
    incident: op.incident,
    reflected: op.reflected,
  };
}

/** P3: resolve display payload from incremental envelope + held static base. */
export function resolveSurfaceDisplay(audit: any, heldStatic: any | null): {
  display: any;
  entities: any[];
  staticPayloadId: string | null;
  kind: string;
  rejected: string | null;
} {
  const root = audit || {};
  const display = root.display || root;
  const inc = root.observer_surface_incremental || display?.observer_surface_incremental || null;
  const kind = String(inc?.kind || root.incremental_wire_kind || 'FULL');
  const staticId = String(
    inc?.surface_static?.static_payload_id
    || inc?.surface_dynamic?.static_payload_id
    || display?.static_payload_id
    || root.static_payload_id
    || '',
  ) || null;

  if (kind === 'DYNAMIC') {
    const heldId = heldStatic?.static_payload_id ? String(heldStatic.static_payload_id) : null;
    const dynId = inc?.surface_dynamic?.static_payload_id
      ? String(inc.surface_dynamic.static_payload_id)
      : staticId;
    if (!heldStatic || !heldId) {
      return { display, entities: display?.entity_samples || [], staticPayloadId: staticId, kind, rejected: 'MISSING_BASE' };
    }
    if (dynId && heldId !== dynId) {
      return { display, entities: display?.entity_samples || [], staticPayloadId: staticId, kind, rejected: 'STALE_DELTA' };
    }
    const staticCol = heldStatic.facets_columnar_static
      || (display?.facets_columnar_static_omitted ? null : null)
      || heldStatic.facets_columnar;
    const opticalCol = inc?.surface_dynamic?.facets_columnar_optical
      || {
        encoding: 'O6_COLUMNAR_FACETS_OPTICAL_V1',
        n: display?.facets_columnar?.n,
        state_class: display?.facets_columnar?.state_class,
        incident: display?.facets_columnar?.incident,
        reflected: display?.facets_columnar?.reflected,
      };
    const merged = mergeStaticOpticalColumnar(staticCol, opticalCol);
    const entities = list(inc?.surface_dynamic?.entity_samples ?? display?.entity_samples);
    const tomb = list(inc?.surface_dynamic?.entity_tombstones);
    const dead = new Set(tomb.map((t: any) => String(t.entity_id || '')));
    const filtered = entities.filter((e: any) => !dead.has(String(e.entity_id || e.sample_id || '')));
    return {
      display: {
        ...display,
        ...heldStatic,
        facets_columnar: merged,
        entity_samples: filtered,
        state_counts: inc?.surface_dynamic?.state_counts || display?.state_counts,
        source: inc?.surface_dynamic?.source || display?.source,
        organism_comparison: inc?.surface_dynamic?.organism_comparison || display?.organism_comparison,
        o5_timing: inc?.surface_dynamic?.o5_timing || display?.o5_timing,
        available: true,
      },
      entities: filtered,
      staticPayloadId: heldId,
      kind,
      rejected: null,
    };
  }

  // FULL / RESET / legacy
  const stBlock = inc?.surface_static || null;
  return {
    display,
    entities: list(display?.entity_samples),
    staticPayloadId: staticId || (stBlock?.static_payload_id ? String(stBlock.static_payload_id) : null),
    kind,
    rejected: null,
  };
}

function list(x: any): any[] {
  return Array.isArray(x) ? x : [];
}

export function bandScalarColor(v: number): string {
  const t = Math.max(0, Math.min(1, Number(v) || 0));
  // Scalar false-color: dark → cyan (display-only)
  const r = Math.round(20 + 40 * t);
  const g = Math.round(40 + 180 * t);
  const b = Math.round(50 + 200 * t);
  return `rgba(${r},${g},${b},0.9)`;
}

export function facetFillColor(f: FacetDraw, mode: DisplayMode, bandIndex: number): string {
  if (mode === 'CAUSAL_STATE') {
    return CAUSAL_DISPLAY_COLORS[f.state_class] || CAUSAL_DISPLAY_COLORS.NOT_EVALUATED;
  }
  if (mode === 'BAND_AUDIT') {
    const src = f.reflected.some((x) => Math.abs(x) > 1e-12) ? f.reflected : f.incident;
    return bandScalarColor(src[bandIndex] ?? 0);
  }
  if (mode === 'MATERIAL_REFLECTANCE') {
    return rgbCss(compositeFalseColor(f.reflectance), 0.88);
  }
  // COMPOSITE_FALSE_COLOR
  const src = f.reflected.some((x) => Math.abs(x) > 1e-12) ? f.reflected : f.incident;
  return rgbCss(compositeFalseColor(src));
}
