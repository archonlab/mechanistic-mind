import assert from 'node:assert/strict';
import { describe, it, beforeEach } from 'node:test';
import {
  mergeGeoTransportIntoFrame,
  resetGeoEmpiricalCache,
} from './geoCache.ts';

function frameWith(trav: any, transport: any) {
  return {
    geometry_interpretation: {
      traversability: trav,
      geo_transport: transport,
    },
    geo_transport: transport,
  };
}

describe('geoCache stale GEO invalidation', () => {
  beforeEach(() => {
    resetGeoEmpiricalCache();
  });

  it('marks LIVE unavailable and clears grids when n_observations is 0', () => {
    const out = mergeGeoTransportIntoFrame(frameWith(
      { status: 'AVAILABLE', n_observations: 0, class_grid: null },
      { static_version: 1, empirical_version: 0, runtime_generation: 2, geo_source: 'LIVE', n_observations: 0 },
    ));
    const trav = out.geometry_interpretation.traversability;
    assert.equal(trav.status, 'LIVE_GEO_UNAVAILABLE');
    assert.equal(trav.class_grid, null);
    assert.match(String(trav.note || ''), /LIVE GEO unavailable|Not falling back/);
  });

  it('does not reuse cached grids across static_version bump (Apply/reset)', () => {
    const grid = [[1, 2], [3, 4]];
    mergeGeoTransportIntoFrame(frameWith(
      { status: 'AVAILABLE', n_observations: 10, class_grid: grid, empirical_version: 3 },
      {
        static_version: 1,
        empirical_version: 3,
        runtime_generation: 1,
        geo_source: 'LIVE',
        empirical_inline: true,
        n_observations: 10,
      },
    ));
    // Compact stub after Apply: new static_version, same empirical_version number possible
    const stub = mergeGeoTransportIntoFrame(frameWith(
      { status: 'CACHED', n_observations: 10, empirical_version: 3 },
      {
        static_version: 2,
        empirical_version: 3,
        runtime_generation: 1,
        geo_source: 'LIVE',
        empirical_inline: false,
        n_observations: 10,
      },
    ));
    const trav = stub.geometry_interpretation.traversability;
    assert.equal(trav.class_grid, undefined);
    assert.notEqual(trav.class_grid, grid);
  });

  it('does not reuse cached grids across runtime_generation change', () => {
    const grid = [[9]];
    mergeGeoTransportIntoFrame(frameWith(
      { status: 'AVAILABLE', n_observations: 4, class_grid: grid, empirical_version: 1 },
      {
        static_version: 5,
        empirical_version: 1,
        runtime_generation: 1,
        geo_source: 'LIVE',
        empirical_inline: true,
        n_observations: 4,
      },
    ));
    const next = mergeGeoTransportIntoFrame(frameWith(
      { status: 'CACHED', n_observations: 4, empirical_version: 1 },
      {
        static_version: 5,
        empirical_version: 1,
        runtime_generation: 2,
        geo_source: 'LIVE',
        empirical_inline: false,
        n_observations: 4,
      },
    ));
    assert.equal(next.geometry_interpretation.traversability.class_grid, undefined);
  });

  it('does not reuse LIVE cache when switching to SAVED source', () => {
    const liveGrid = [[1]];
    mergeGeoTransportIntoFrame(frameWith(
      { status: 'AVAILABLE', n_observations: 2, class_grid: liveGrid, empirical_version: 7 },
      {
        static_version: 3,
        empirical_version: 7,
        runtime_generation: 1,
        geo_source: 'LIVE',
        empirical_inline: true,
        n_observations: 2,
      },
    ));
    const saved = mergeGeoTransportIntoFrame(frameWith(
      {
        status: 'AVAILABLE',
        n_observations: 8,
        class_grid: [[2]],
        empirical_version: 7,
        provenance: { run_id: 'hist-1', experiment_seed: 99 },
      },
      {
        static_version: 4,
        empirical_version: 7,
        runtime_generation: 1,
        geo_source: 'SAVED',
        empirical_inline: true,
        n_observations: 8,
        provenance: { run_id: 'hist-1' },
      },
    ));
    assert.equal(saved.geometry_interpretation.traversability.geo_source, 'SAVED');
    assert.deepEqual(saved.geometry_interpretation.traversability.class_grid, [[2]]);
    assert.notDeepEqual(saved.geometry_interpretation.traversability.class_grid, liveGrid);
  });

  it('preserves provenance on LIVE frames', () => {
    const prov = {
      runtime_generation: 4,
      experiment_seed: 17,
      terrain_checksum: 'abc',
      ambient_checksum: 'def',
    };
    const out = mergeGeoTransportIntoFrame(frameWith(
      { status: 'AVAILABLE', n_observations: 1, class_grid: [[0]], empirical_version: 1 },
      {
        static_version: 1,
        empirical_version: 1,
        runtime_generation: 4,
        geo_source: 'LIVE',
        empirical_inline: true,
        n_observations: 1,
        provenance: prov,
        terrain_checksum: 'abc',
        ambient_checksum: 'def',
      },
    ));
    assert.equal(out.geometry_interpretation.traversability.provenance.terrain_checksum, 'abc');
    assert.equal(out.geo_transport.terrain_checksum, 'abc');
  });
});
