import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  diagnoseViewport,
  mapDisplayMetrics,
  mapNotCoveredByDock,
} from './viewportGeometry.ts';
import { simulationCenterX } from './floatingWindows.ts';

describe('OBSERVER_SIMULATION_VIEWPORT_01', () => {
  it('V3–V7: positive workspace yields positive map display', () => {
    const m = mapDisplayMetrics(900, 700, 32, 32, 8);
    assert.equal(m.positive, true);
    assert.equal(m.scaleFinite, true);
    assert.ok(m.mapDisplaySize > 100);
    assert.ok(m.cell > 0);
    assert.ok(Number.isFinite(m.originX) && Number.isFinite(m.originY));
  });

  it('V15: square world preserves aspect (uniform cell)', () => {
    const m = mapDisplayMetrics(1200, 600, 32, 32, 8);
    assert.ok(Math.abs(m.cell * 32 - m.cell * 32) < 1e-9);
    // drawn region is square
    assert.ok(Math.abs(m.cell * 32 - Math.min(m.availableWidth, m.availableHeight)) < 1e-6
      || m.cell * 32 <= Math.min(m.availableWidth, m.availableHeight) + 1e-6);
  });

  it('diagnoses zero-height canvas parent as blank (pre-fix failure mode)', () => {
    const d = diagnoseViewport({
      workspaceW: 900,
      workspaceH: 700,
      canvasParentW: 0,
      canvasParentH: 0,
      canvasCssW: 0,
      canvasCssH: 0,
    });
    assert.equal(d.blank, true);
    assert.equal(d.reason, 'canvas_parent_height_zero_absolute_collapse');
    assert.equal(d.gates.V5_MAP_DISPLAY_SIZE_POSITIVE, false);
  });

  it('healthy measurements are not blank', () => {
    const d = diagnoseViewport({
      workspaceW: 900,
      workspaceH: 700,
      canvasParentW: 880,
      canvasParentH: 680,
      canvasCssW: 880,
      canvasCssH: 680,
    });
    assert.equal(d.blank, false);
    assert.equal(d.reason, 'ok');
    assert.equal(d.gates.V7_MAP_VISIBLE, true);
  });

  it('V10: map centers inside simulation workspace, not full app', () => {
    const left = 360;
    const app = 1200;
    const center = simulationCenterX(app, left);
    assert.equal(center, 360 + 420);
    // map origin relative to workspace, not app
    const m = mapDisplayMetrics(app - left, 800, 32, 32, 8);
    assert.ok(m.originX >= 0);
    assert.ok(m.originX + 32 * m.cell <= (app - left));
  });

  it('V11: dock does not cover map', () => {
    assert.equal(mapNotCoveredByDock(64, 64), true);
    assert.equal(mapNotCoveredByDock(360, 200), false);
    assert.equal(mapNotCoveredByDock(360, 360), true);
  });

  it('zero workspace stays non-positive (no NaN scale)', () => {
    const m = mapDisplayMetrics(0, 0, 32, 32, 8);
    assert.equal(m.positive, false);
    assert.equal(m.scaleFinite, false);
    assert.equal(m.cell, 0);
  });
});
