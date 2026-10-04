import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, it } from 'node:test';
import { EXPERIMENT_MENU } from './types.ts';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const distAssets = join(root, '../../../mechanistic_mind/ui/psy_observer_web/web_dist/assets');

describe('Experiment Vision tab hosts the only vision editors', () => {
  it('lists Vision on the Experiment menu', () => {
    assert.ok(EXPERIMENT_MENU.some((s) => s.id === 'set_vision' && s.label === 'Vision'));
  });

  it('App Experiment Vision tab mounts VisionExperimenterControl; Sensors does not', () => {
    const app = readFileSync(join(root, 'App.tsx'), 'utf8');
    const dock = readFileSync(join(root, 'inspectors/InspectorDock.tsx'), 'utf8');
    const expTabs = dock.slice(dock.indexOf('EXPERIMENT: ['), dock.indexOf('SENSORS: ['));
    const vStart = app.indexOf("tabId === 'vision'");
    const afterVisionCandidates = [
      app.indexOf("\n      if (tabId === 'model')", vStart + 1),
      app.indexOf("\n      if (tabId === 'psc')", vStart + 1),
      app.indexOf("\n      if (tabId === 'ablations')", vStart + 1),
      app.indexOf("\n      if (tabId === 'ecology')", vStart + 1),
      app.indexOf("\n    if (which === 'intervention')", vStart + 1),
    ].filter((i) => i > vStart);
    const vEnd = Math.min(...afterVisionCandidates);
    const visionOnly = app.slice(vStart, vEnd);
    assert.ok(visionOnly.includes('VisionExperimenterControl'));
    assert.ok(expTabs.includes("{ id: 'vision', label: 'Vision' }"));
    assert.ok(expTabs.includes("{ id: 'review', label: 'Review / Apply' }"));
    assert.ok(expTabs.indexOf("{ id: 'vision', label: 'Vision' }") < expTabs.indexOf("{ id: 'review', label: 'Review / Apply' }"));
    assert.ok(app.includes("tabId === 'vision'"));
    assert.ok(app.includes('data-testid="experiment-vision-config"'));
    const sensorsBlock = app.slice(app.indexOf("which === 'sensors'"), app.indexOf("which === 'signals'"));
    assert.equal(sensorsBlock.includes('VisionExperimenterControl'), false);
    assert.equal(dock.includes('<VisionExperimenterControl'), false);
  });

  it('production web_dist includes clickable Experiment Vision tab + config panel', () => {
    const files = readdirSync(distAssets).filter((f) => f.startsWith('index-') && f.endsWith('.js'));
    assert.ok(files.length > 0, 'web_dist index JS missing — rebuild Observer UI');
    const js = readFileSync(join(distAssets, files[0]), 'utf8');
    assert.ok(js.includes('experiment-vision-config'), 'built SPA missing experiment-vision-config');
    assert.ok(
      js.includes('{id:`vision`,label:`Vision`},{id:`review`,label:`Review / Apply`}')
      || (js.includes('Vision') && js.includes('Review / Apply')),
      'built SPA missing Experiment Vision tab before Review / Apply',
    );
  });

  it('Tiktaalik Eye panel keeps diagnostics only', () => {
    const eye = readFileSync(join(root, 'components/TiktaalikEyePanel.tsx'), 'utf8');
    assert.ok(eye.includes('SENSOR SPACE'));
    assert.ok(eye.includes('FPV'));
    assert.ok(eye.includes('2FPS') || eye.includes('2 FPS'));
    assert.equal(eye.includes('onSetRadius'), false);
    assert.equal(eye.includes('onSetSpatialVision'), false);
  });
});
