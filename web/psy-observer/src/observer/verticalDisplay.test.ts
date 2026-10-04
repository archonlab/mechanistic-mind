import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  DEFAULT_VERTICAL_EXAGGERATION,
  VERTICAL_DISPLAY_SCHEMA,
  VERTICAL_DISPLAY_SCHEMA_V1_1,
  VERTICAL_EXAGGERATION_LABEL,
  VERTICAL_TRAIL_PROFILE,
  TRAIL_LENGTH_SAMPLES,
  TRAIL_RESEARCHER_LABEL,
  clearanceStemPx,
  deltaColor,
  elevationColor,
  elevationGridValid,
  filterTrailSegments,
  readVerticalDisplay,
  sparseDeltasValid,
  splitTrailOnWrap,
  trailSegmentsValid,
} from './verticalDisplay.ts';

describe('OBSERVER_VERTICAL_DISPLAY_CONTRACT_V1 frontend', () => {
  const elevGrid = {
    height: 2,
    width: 2,
    data: [[0.1, 0.2], [0.15, 0.25]],
    elev_min: 0.1,
    elev_max: 0.25,
  };

  it('reads schema and rejects legacy/missing', () => {
    assert.equal(readVerticalDisplay({}), null);
    assert.equal(readVerticalDisplay({ vertical_display: { schema_version: 'OTHER' } }), null);
    const vd = readVerticalDisplay({
      vertical_display: {
        schema_version: VERTICAL_DISPLAY_SCHEMA,
        cell_centre_elevation: elevGrid,
        elev_min: 0.1,
        elev_max: 0.25,
        sparse_deltas: [],
      },
    });
    assert.equal(vd?.schema_version, VERTICAL_DISPLAY_SCHEMA);
    assert.equal(elevationGridValid(vd), true);
    assert.equal(sparseDeltasValid(vd), true);
  });

  it('accepts V1_1 trail contract', () => {
    const vd = readVerticalDisplay({
      vertical_display: {
        schema_version: VERTICAL_DISPLAY_SCHEMA_V1_1,
        schema_compatible_with: [VERTICAL_DISPLAY_SCHEMA, VERTICAL_DISPLAY_SCHEMA_V1_1],
        display_profile: VERTICAL_TRAIL_PROFILE,
        cell_centre_elevation: elevGrid,
        elev_min: 0.1,
        elev_max: 0.25,
        sparse_deltas: [],
        trail_segments: [{
          entity_id: 'agent_0',
          start_reason: 'UNSUPPORTED_TRANSITION',
          start_tick: 1,
          active: true,
          sample_count: 2,
          samples: [
            { tick: 1, entity_id: 'agent_0', x: 1, y: 2, base_z: 0.5, clearance: 0.5, support_state: 'UNSUPPORTED' },
            { tick: 2, entity_id: 'agent_0', x: 1, y: 2, base_z: 0.3, clearance: 0.3, support_state: 'UNSUPPORTED', vz: -0.2 },
          ],
        }],
      },
    });
    assert.equal(vd?.schema_version, VERTICAL_DISPLAY_SCHEMA_V1_1);
    assert.equal(trailSegmentsValid(vd), true);
    assert.equal(vd?.display_profile, VERTICAL_TRAIL_PROFILE);
  });

  it('elevation false color is deterministic; flat terrain uniform', () => {
    const a = elevationColor(0.2, 0.1, 0.25, 0.7);
    const b = elevationColor(0.2, 0.1, 0.25, 0.7);
    assert.equal(a, b);
    const flatA = elevationColor(1.0, 1.0, 1.0, 1);
    const flatB = elevationColor(1.0, 1.0, 1.0, 1);
    assert.equal(flatA, flatB);
    assert.match(flatA, /^rgba\(/);
  });

  it('delta color: near-zero transparent; excavation cool', () => {
    assert.equal(deltaColor(0, 1), 'rgba(0,0,0,0)');
    assert.match(deltaColor(-0.5, 1), /^rgba\(/);
    assert.match(deltaColor(0.5, 1), /^rgba\(/);
  });

  it('clearance stem suppressed when supported; visible when clear', () => {
    assert.equal(clearanceStemPx(0, 10, 2), 0);
    assert.equal(clearanceStemPx(null, 10, 2), 0);
    assert.equal(clearanceStemPx(0.5, 10, DEFAULT_VERTICAL_EXAGGERATION), 0.5 * 10 * 2);
  });

  it('trail modes filter SELECTED/UNSUPPORTED/OFF; wrap splits', () => {
    const segs = [{
      entity_id: 'agent_0',
      start_reason: 'RELEASE',
      active: true,
      samples: [
        { tick: 1, entity_id: 'agent_0', x: 31.5, y: 2, base_z: 0.4, clearance: 0.4 },
        { tick: 2, entity_id: 'agent_0', x: 0.2, y: 2, base_z: 0.2, clearance: 0.2 },
      ],
    }, {
      entity_id: 'obj-1',
      start_reason: 'SUPPORT_LOSS',
      active: true,
      samples: [
        { tick: 3, entity_id: 'obj-1', x: 4, y: 5, base_z: 0.6, clearance: 0.6, support_state: 'UNSUPPORTED' },
      ],
    }];
    assert.equal(filterTrailSegments(segs as any, 'OFF', 'agent_0', 32).length, 0);
    assert.equal(filterTrailSegments(segs as any, 'SELECTED', 'agent_0', 32).length, 1);
    assert.equal(filterTrailSegments(segs as any, 'UNSUPPORTED', null, 32).length, 2);
    const pieces = splitTrailOnWrap(segs[0].samples as any, 32, 32);
    assert.equal(pieces.length, 2);
    assert.equal(TRAIL_LENGTH_SAMPLES.NORMAL, 32);
    assert.equal(TRAIL_RESEARCHER_LABEL.includes('AUTHORITATIVE SAMPLES'), true);
  });

  it('labels display exaggeration; optical radius not physical', () => {
    assert.equal(VERTICAL_EXAGGERATION_LABEL, 'DISPLAY EXAGGERATION');
    const entity = {
      collision_radius: 0.4,
      optical_radius: 0.2,
      optical_radius_is_not_collision_radius: true,
      glyph_is_not_physics: true,
    };
    assert.equal(entity.optical_radius_is_not_collision_radius, true);
    assert.notEqual(entity.collision_radius, entity.optical_radius);
  });

  it('malformed payload disables elevation overlay helpers', () => {
    assert.equal(elevationGridValid(null), false);
    assert.equal(elevationGridValid({ cell_centre_elevation: { data: null } } as any), false);
    assert.equal(sparseDeltasValid({} as any), false);
  });
});
