import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { gridRange, occupancyCounts, periodicSegments, scalarGrid } from './rendererMath.ts';

describe('runtime-backed renderer math', () => {
  it('extracts only transported runtime fields', () => {
    const world = { scalars: { T: [[1, 2], [3, 4]], R_A: [[0, 1], [0, 0]] } };
    assert.deepEqual(scalarGrid(world, 'T'), [[1, 2], [3, 4]]);
    assert.deepEqual(scalarGrid(world, 'R_A'), [[0, 1], [0, 0]]);
    assert.equal(scalarGrid(world, 'invented'), null);
  });

  it('computes deterministic field range', () => {
    assert.deepEqual(gridRange([[3, 1], [4, 2]]), { lo: 1, hi: 4 });
  });

  it('splits periodic wrap crossings', () => {
    const points = [
      { tick: 1, x: 31.8, y: 4 },
      { tick: 2, x: 0.1, y: 4.1 },
      { tick: 3, x: 0.3, y: 4.2 },
    ];
    const segments = periodicSegments(points, 32, 32);
    assert.equal(segments.length, 2);
    assert.equal(segments[0].length, 1);
    assert.equal(segments[1].length, 2);
  });

  it('counts occupancy from recorded trajectory cells', () => {
    const counts = occupancyCounts([
      { x: 1.2, y: 2.8 },
      { x: 1.9, y: 2.1 },
      { x: 4, y: 4 },
    ]);
    assert.equal(counts.get('1,2'), 2);
    assert.equal(counts.get('4,4'), 1);
  });
});

