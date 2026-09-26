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
    assert.ok(expTabs.includes("{ id: 'vision', label: 'Vision' }"));
    assert.ok(expTabs.indexOf("{ id: 'model', label: 'Model' }") < expTabs.indexOf("{ id: 'vision', label: 'Vision' }"));
    assert.ok(app.includes("tabId === 'vision'"));
    assert.ok(app.includes('data-testid="experiment-vision-config"'));
    const visionBlock = app.slice(app.indexOf("tabId === 'vision'"), app.indexOf("tabId === 'model'"));
    assert.ok(visionBlock.includes('VisionExperimenterControl'));
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
      js.includes('{id:`model`,label:`Model`},{id:`vision`,label:`Vision`}'),
      'built SPA missing Experiment Vision tab after Model',
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
