import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

describe('VW7 main viewport entrypoint', () => {
  const pane = readFileSync(resolve('src/chrome/WorldPane.tsx'), 'utf8');
  const css = readFileSync(resolve('src/styles/app.css'), 'utf8');
  const app = readFileSync(resolve('src/App.tsx'), 'utf8');
  const inspect = readFileSync(resolve('src/workspaces/InspectWorkspace.tsx'), 'utf8');
  const run = readFileSync(resolve('src/workspaces/RunWorkspace.tsx'), 'utf8');

  it('A. default volumeWorkspace is MAP', () => {
    assert.ok(pane.includes("volumeWorkspace = 'MAP'"));
    assert.ok(app.includes("useState<'MAP' | 'VOLUME' | 'SURFACE'>('MAP')"));
  });

  it('B/C. WorldPane switches OccupancyVolumeView vs WorldMap from volumeWorkspace', () => {
    assert.ok(pane.includes("volumeWorkspace === 'VOLUME'"));
    assert.ok(pane.includes('<OccupancyVolumeView'));
    assert.ok(pane.includes('<WorldMap'));
    assert.ok(pane.includes('world-main-viewport'));
  });

  it('D. single main viewport branch in WorldPane (no second competing tree in App)', () => {
    assert.equal((pane.match(/data-testid="world-main-viewport"/g) || []).length, 1);
    assert.equal((pane.match(/<OccupancyVolumeView/g) || []).length, 1);
    assert.equal((pane.match(/data-testid="world-viewport-mode-bar"/g) || []).length, 1);
    assert.ok(!app.includes('const worldTab'));
    assert.ok(!app.includes('worldWithInspector'));
    assert.ok(!app.includes('void worldWithInspector'));
    assert.ok(!app.includes('OccupancyVolumeView'));
  });

  it('E. VOLUME control is on WorldPane chrome without Overlays', () => {
    assert.ok(pane.includes('world-viewport-mode-bar'));
    assert.ok(pane.includes('data-testid="world-view-volume"'));
    assert.ok(pane.includes('data-testid="world-view-map"'));
    assert.ok(inspect.includes('volumeWorkspace={volumeWorkspace}'));
    assert.ok(run.includes('volumeWorkspace={volumeWorkspace}'));
    assert.ok(app.includes('onVolumeWorkspaceChange={setVolumeWorkspace}'));
  });

  it('F. unavailable OccupancyVolumeView path preserved (no heightfield fabricate)', () => {
    assert.ok(pane.includes('observer_camera_occupancy_consumer'));
    assert.ok(pane.includes("available: false"));
    const view = readFileSync(resolve('src/components/OccupancyVolumeView.tsx'), 'utf8');
    assert.ok(view.includes('VOLUME VIEW UNAVAILABLE') || view.includes('vw7-unavailable'));
  });

  it('G. view-mode handlers are local UI state only (no sim mutation API)', () => {
    assert.ok(pane.includes('onVolumeWorkspaceChange?.('));
    assert.ok(!pane.includes('fetch('));
    assert.ok(!pane.includes('/api/'));
    assert.ok(!pane.includes('applyExperiment'));
    assert.ok(!pane.includes('step('));
  });

  it('Overlays buttons reuse same App volumeWorkspace state when present', () => {
    assert.ok(app.includes("setVolumeWorkspace('VOLUME')") || app.includes('setVolumeWorkspace'));
  });

  it('layout: mode bar is outside dedicated absolute-fill content host', () => {
    assert.ok(pane.includes('world-viewport-content-host'));
    assert.ok(pane.includes('data-testid="world-viewport-content-host"'));
    // Mode bar appears before content host in source order
    const barIdx = pane.indexOf('data-testid="world-viewport-mode-bar"');
    const hostIdx = pane.indexOf('data-testid="world-viewport-content-host"');
    assert.ok(barIdx > 0 && hostIdx > barIdx);
    // Absolute fill scoped to content host — not to wrapper+layout together
    assert.ok(css.includes('.sim-map-host .world-viewport-content-host .world-layout.map-only'));
    assert.ok(css.includes('.sim-map-host .world-viewport-content-host .world-center'));
    assert.ok(!css.includes('.sim-map-host .world-click-wrapper,\n.sim-map-host .world-layout.map-only'));
    assert.ok(css.includes('display:flex;flex-direction:column'));
    assert.ok(css.includes('.sim-map-host .world-viewport-mode-bar'));
    assert.ok(css.includes('pointer-events:auto'));
  });

  it('RUN and INSPECT both mount WorldPane with shared volumeWorkspace props', () => {
    assert.ok(inspect.includes('<WorldPane'));
    assert.ok(run.includes('<WorldPane'));
    assert.ok(inspect.includes('onVolumeWorkspaceChange={onVolumeWorkspaceChange}'));
    assert.ok(run.includes('onVolumeWorkspaceChange={onVolumeWorkspaceChange}'));
    assert.equal((app.match(/onVolumeWorkspaceChange=\{setVolumeWorkspace\}/g) || []).length >= 2, true);
  });

  it('stable button labels and aria-pressed for active mode', () => {
    assert.ok(pane.includes('MAP / 2D'));
    assert.ok(pane.includes('VOLUME / X-RAY'));
    assert.ok(pane.includes('SURFACE / LIGHT'));
    assert.ok(pane.includes('aria-pressed={volumeWorkspace === \'MAP\'}'));
    assert.ok(pane.includes('aria-pressed={volumeWorkspace === \'VOLUME\'}'));
    assert.ok(pane.includes('aria-pressed={volumeWorkspace === \'SURFACE\'}'));
  });

  it('exposes SURFACE / LIGHT mode alongside MAP and VOLUME/X-RAY', () => {
    assert.ok(pane.includes('world-view-surface'));
    assert.ok(pane.includes('SURFACE / LIGHT'));
    assert.ok(pane.includes('SurfaceLightView'));
    assert.ok(app.includes("useState<'MAP' | 'VOLUME' | 'SURFACE'>('MAP')"));
  });
});
