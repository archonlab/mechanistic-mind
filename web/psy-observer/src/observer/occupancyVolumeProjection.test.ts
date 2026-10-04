import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  simToRender,
  assertNoSolidFillAcrossGap,
  COORDINATE_TRANSFORM,
  prismFaces,
  defaultOrbitCamera,
  projectPoint,
} from './occupancyVolumeProjection.ts';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

describe('VW7 occupancy volume projection', () => {
  it('uses explicit sim→render transform', () => {
    assert.equal(COORDINATE_TRANSFORM.render_x, 'simulation_x');
    assert.equal(COORDINATE_TRANSFORM.render_y, 'simulation_z');
    assert.equal(COORDINATE_TRANSFORM.render_z, 'simulation_y');
    assert.deepEqual(simToRender(1, 2, 3), { x: 1, y: 3, z: 2 });
  });

  it('cavity gap has no solid fill prism', () => {
    const volumes = [
      { cell_x: 4, cell_y: 4, sim_x0: 4, sim_x1: 5, sim_y0: 4, sim_y1: 5, sim_z_min: 0, sim_z_max: 3 },
      { cell_x: 4, cell_y: 4, sim_x0: 4, sim_x1: 5, sim_y0: 4, sim_y1: 5, sim_z_min: 7, sim_z_max: 10 },
    ];
    assert.equal(assertNoSolidFillAcrossGap(volumes, 4, 4, 3, 7), true);
    const bad = [{ cell_x: 4, cell_y: 4, sim_x0: 4, sim_x1: 5, sim_y0: 4, sim_y1: 5, sim_z_min: 0, sim_z_max: 10 }];
    assert.equal(assertNoSolidFillAcrossGap(bad, 4, 4, 3, 7), false);
  });

  it('isolated intervals stay separate faces', () => {
    const a = prismFaces({ cell_x: 1, cell_y: 1, sim_x0: 1, sim_x1: 2, sim_y0: 1, sim_y1: 2, sim_z_min: 0, sim_z_max: 2 });
    const b = prismFaces({ cell_x: 1, cell_y: 1, sim_x0: 1, sim_x1: 2, sim_y0: 1, sim_y1: 2, sim_z_min: 5, sim_z_max: 6 });
    assert.equal(a.length, 6);
    assert.equal(b.length, 6);
    assert.notEqual(a[0].z_max, b[0].z_min);
  });

  it('projectPoint is finite for orbit camera', () => {
    const cam = defaultOrbitCamera(32, 32);
    const p = projectPoint(simToRender(16, 16, 2), cam, 640, 400);
    assert.ok(Number.isFinite(p.u) && Number.isFinite(p.v));
  });

  it('WorldPane exposes MAP/VOLUME switch and OccupancyVolumeView', () => {
    const pane = readFileSync(resolve('src/chrome/WorldPane.tsx'), 'utf8');
    assert.ok(pane.includes('OccupancyVolumeView'));
    assert.ok(pane.includes('world-view-volume'));
    assert.ok(pane.includes('VOLUME / X-RAY') || pane.includes('VOLUME / 3D'));
    assert.ok(pane.includes('MAP / 2D'));
    assert.ok(pane.includes('SURFACE / LIGHT'));
    assert.ok(pane.includes('world-viewport-mode-bar'));
    const view = readFileSync(resolve('src/components/OccupancyVolumeView.tsx'), 'utf8');
    assert.ok(view.includes('NOT ORGANISM VISION'));
    assert.ok(view.includes('OBSERVER_RENDER_LIGHTING_ONLY'));
    assert.ok(view.includes('occupancy-volume-view'));
  });
});
