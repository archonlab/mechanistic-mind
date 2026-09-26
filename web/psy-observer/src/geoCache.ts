/** OBS-05: versioned GEO empirical cache for compact LIVE frames.

Cache is keyed by static_version + runtime_generation + empirical_version.
Never reuse grids across Apply/reset (static_version bump) or runtime generation.
Never silently fall back to older-run geometry when LIVE GEO is missing.
*/

export type GeoTransport = {
  static_version?: number;
  empirical_version?: number;
  empirical_inline?: boolean;
  n_observations?: number;
  runtime_generation?: number;
  geo_source?: string;
  experiment_seed?: number;
  terrain_checksum?: string | null;
  ambient_checksum?: string | null;
  provenance?: Record<string, unknown>;
};

function unflattenGrid(payload: any): number[][] | null {
  if (!payload) return null;
  if (Array.isArray(payload)) return payload as number[][];
  if (typeof payload !== 'object') return null;
  const h = Number(payload.h || 0);
  const w = Number(payload.w || 0);
  const data = payload.data;
  if (!Array.isArray(data) || h <= 0 || w <= 0) return null;
  const out: number[][] = [];
  for (let y = 0; y < h; y++) {
    const row: number[] = [];
    const base = y * w;
    for (let x = 0; x < w; x++) row.push(Number(data[base + x]));
    out.push(row);
  }
  return out;
}

function normalizeTraversability(trav: any): any {
  if (!trav || typeof trav !== 'object') return trav;
  if (trav.grids_encoding !== 'flat' && !trav.class_grid?.data) return trav;
  return {
    ...trav,
    class_grid: unflattenGrid(trav.class_grid) ?? trav.class_grid,
    opposing_rate_grid: unflattenGrid(trav.opposing_rate_grid) ?? trav.opposing_rate_grid,
    worst_alignment_grid: unflattenGrid(trav.worst_alignment_grid) ?? trav.worst_alignment_grid,
    attempt_grid: unflattenGrid(trav.attempt_grid) ?? trav.attempt_grid,
    grids_encoding: 'nested',
  };
}

let empiricalCache: {
  version: number;
  staticVersion: number;
  runtimeGeneration: number;
  geoSource: string;
  data: any;
} | null = null;

export function resetGeoEmpiricalCache() {
  empiricalCache = null;
}

function cacheKeyMatch(transport: GeoTransport, ver: number): boolean {
  if (!empiricalCache) return false;
  const staticVer = Number(transport.static_version ?? 0);
  const gen = Number(transport.runtime_generation ?? 0);
  const src = String(transport.geo_source || 'LIVE').toUpperCase();
  return (
    empiricalCache.version === ver
    && empiricalCache.staticVersion === staticVer
    && empiricalCache.runtimeGeneration === gen
    && empiricalCache.geoSource === src
  );
}

export function mergeGeoTransportIntoFrame(frame: any): any {
  if (!frame || typeof frame !== 'object') return frame;
  const transport: GeoTransport =
    frame.geo_transport ||
    frame.geometry_interpretation?.geo_transport ||
    {};
  const gi = frame.geometry_interpretation;
  if (!gi || typeof gi !== 'object') return frame;

  let trav = gi.traversability;
  const ver = Number(transport.empirical_version ?? trav?.empirical_version ?? -1);
  const staticVer = Number(transport.static_version ?? 0);
  const gen = Number(transport.runtime_generation ?? 0);
  const src = String(transport.geo_source || trav?.geo_source || 'LIVE').toUpperCase();
  const inline = transport.empirical_inline !== false && trav?.status !== 'CACHED' && trav?.class_grid;

  // Explicit unavailable — never paste old grids.
  if (trav?.status === 'LIVE_GEO_UNAVAILABLE' || (src === 'LIVE' && Number(trav?.n_observations || transport.n_observations || 0) <= 0 && !trav?.class_grid)) {
    empiricalCache = null;
    const unavailable = {
      ...(trav || {}),
      status: 'LIVE_GEO_UNAVAILABLE',
      geo_source: src,
      provenance: trav?.provenance || transport.provenance,
      note: trav?.note || 'LIVE GEO unavailable — not falling back to older runs.',
      class_grid: null,
      opposing_rate_grid: null,
      worst_alignment_grid: null,
      attempt_grid: null,
      n_observations: Number(trav?.n_observations || transport.n_observations || 0),
    };
    return {
      ...frame,
      geometry_interpretation: { ...gi, traversability: unavailable, geo_transport: transport },
      geo_transport: transport,
    };
  }

  if (inline && trav) {
    const normalized = normalizeTraversability({
      ...trav,
      geo_source: src,
      provenance: trav.provenance || transport.provenance,
    });
    empiricalCache = {
      version: ver,
      staticVersion: staticVer,
      runtimeGeneration: gen,
      geoSource: src,
      data: normalized,
    };
    return {
      ...frame,
      geometry_interpretation: { ...gi, traversability: normalized, geo_transport: transport },
      geo_transport: transport,
    };
  }

  // Cached stub — restore grids only when static_version + generation + source match.
  if (cacheKeyMatch(transport, ver) && empiricalCache) {
    const mergedTrav = {
      ...empiricalCache.data,
      ...trav,
      class_grid: empiricalCache.data.class_grid,
      opposing_rate_grid: empiricalCache.data.opposing_rate_grid,
      worst_alignment_grid: empiricalCache.data.worst_alignment_grid,
      attempt_grid: empiricalCache.data.attempt_grid,
      status: trav?.status === 'LIVE_GEO_UNAVAILABLE' ? 'LIVE_GEO_UNAVAILABLE' : 'AVAILABLE',
      empirical_version: ver,
      geo_source: src,
      provenance: trav?.provenance || transport.provenance || empiricalCache.data.provenance,
    };
    return {
      ...frame,
      geometry_interpretation: { ...gi, traversability: mergedTrav, geo_transport: transport },
      geo_transport: transport,
    };
  }

  // Version miss / generation change: do not keep stale grids.
  if (empiricalCache && !cacheKeyMatch(transport, ver)) {
    empiricalCache = null;
  }

  return {
    ...frame,
    geometry_interpretation: {
      ...gi,
      traversability: trav
        ? { ...trav, geo_source: src, provenance: trav.provenance || transport.provenance }
        : trav,
      geo_transport: transport,
    },
    geo_transport: transport,
  };
}

export async function fetchEmpiricalIfMissing(frame: any): Promise<any> {
  const transport: GeoTransport = frame?.geo_transport || frame?.geometry_interpretation?.geo_transport || {};
  const ver = Number(transport.empirical_version ?? -1);
  if (ver < 0) return frame;
  if (String(transport.geo_source || 'LIVE').toUpperCase() === 'LIVE'
    && Number(transport.n_observations || 0) <= 0) {
    return mergeGeoTransportIntoFrame(frame);
  }
  if (cacheKeyMatch(transport, ver)) {
    return mergeGeoTransportIntoFrame(frame);
  }
  try {
    const r = await fetch('/api/geometry/empirical');
    if (!r.ok) return frame;
    const body = await r.json();
    if (body?.traversability) {
      const normalized = normalizeTraversability(body.traversability);
      const bodyTransport: GeoTransport = {
        static_version: Number(body.static_version ?? transport.static_version ?? 0),
        empirical_version: Number(body.empirical_version ?? normalized.empirical_version ?? ver),
        runtime_generation: Number(body.runtime_generation ?? transport.runtime_generation ?? 0),
        geo_source: String(body.geo_source || transport.geo_source || 'LIVE'),
        provenance: body.provenance || transport.provenance,
      };
      // Reject empirical fetch from a different runtime generation.
      if (
        Number(transport.runtime_generation ?? 0) > 0
        && Number(bodyTransport.runtime_generation ?? 0) > 0
        && Number(bodyTransport.runtime_generation) !== Number(transport.runtime_generation)
      ) {
        return mergeGeoTransportIntoFrame(frame);
      }
      empiricalCache = {
        version: Number(bodyTransport.empirical_version),
        staticVersion: Number(bodyTransport.static_version),
        runtimeGeneration: Number(bodyTransport.runtime_generation ?? 0),
        geoSource: String(bodyTransport.geo_source || 'LIVE').toUpperCase(),
        data: {
          ...normalized,
          provenance: bodyTransport.provenance,
          geo_source: bodyTransport.geo_source,
        },
      };
      return mergeGeoTransportIntoFrame({
        ...frame,
        geo_transport: { ...transport, ...bodyTransport, empirical_inline: false },
      });
    }
  } catch {
    /* ignore */
  }
  return frame;
}
