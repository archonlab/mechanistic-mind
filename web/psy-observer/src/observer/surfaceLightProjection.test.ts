/** O6 SURFACE/LIGHT projection unit tests (Node). */
import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  CAUSAL_DISPLAY_COLORS,
  compositeFalseColor,
  expandColumnarFacets,
  facetCornersSim,
  facetFillColor,
} from '../observer/surfaceLightProjection.ts';

describe('O6 surfaceLightProjection', () => {
  it('composite transform is fixed 6→RGB and clips', () => {
    const rgb = compositeFalseColor([1, 1, 0, 0, 0.5, 0.5]);
    assert.equal(rgb[0], 1);
    assert.equal(rgb[1], 0);
    assert.equal(rgb[2], 0.5);
  });

  it('expands columnar facets and builds top corners', () => {
    const col = {
      encoding: 'O6_COLUMNAR_FACETS_V1',
      n: 1,
      facet_id: ['f1'],
      face_class: ['FACE_TOP'],
      cell_x: [2],
      cell_y: [3],
      interval_id: ['i'],
      centre: [2.5, 3.5, 1],
      normal: [0, 0, 1],
      area: [1],
      span_lower: [1],
      span_upper: [1],
      boundary_plane_coordinate: [1],
      o1_status: ['OK'],
      state_class: ['DIRECT_ILLUMINATED'],
      incident: [1, 0, 0, 0, 0, 0],
      reflected: [0.5, 0, 0, 0, 0, 0],
      reflectance: [1, 1, 1, 1, 1, 1],
    };
    const facets = expandColumnarFacets(col);
    assert.equal(facets.length, 1);
    assert.equal(facets[0].corners.length, 4);
    assert.equal(facetFillColor(facets[0], 'CAUSAL_STATE', 0), CAUSAL_DISPLAY_COLORS.DIRECT_ILLUMINATED);
    const c = facetCornersSim({
      face_class: 'FACE_TOP',
      cell_x: 0,
      cell_y: 0,
      span_lower: 2,
      span_upper: 2,
      boundary_plane_coordinate: 2,
    });
    assert.equal(c.length, 4);
  });
});
