import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, it } from 'node:test';
import {
  PUBLIC_MODEL_PRESETS,
  UI_PRESET_ACANTHOSTEGA_BETA4,
  UI_PUBLIC_LABEL_TIKTAALIK_BETA31,
} from './modelPreset.ts';

const root = resolve('src');

describe('FINAL_BETA4_ENGINEERING_DEFAULTS_UX_AND_RELEASE_GATE UI contracts', () => {
  it('public selector has exactly two models', () => {
    assert.equal(PUBLIC_MODEL_PRESETS.length, 2);
    assert.ok(PUBLIC_MODEL_PRESETS.includes(UI_PUBLIC_LABEL_TIKTAALIK_BETA31));
    assert.ok(PUBLIC_MODEL_PRESETS.includes(UI_PRESET_ACANTHOSTEGA_BETA4));
  });

  it('primary experiment tab order ends with Review / Apply and drops Perception/Cognition/Predictive', () => {
    const dock = readFileSync(resolve(root, 'inspectors/InspectorDock.tsx'), 'utf8');
    const expTabs = dock.slice(dock.indexOf('EXPERIMENT: ['), dock.indexOf('SENSORS: ['));
    const ids = [...expTabs.matchAll(/\{ id: '([^']+)'/g)].map((m) => m[1]);
    assert.deepEqual(ids, [
      'world', 'ecology', 'model', 'body', 'psc', 'ablations', 'vision', 'review',
    ]);
    assert.equal(ids.includes('perception'), false);
    assert.equal(ids.includes('cognition'), false);
    assert.equal(ids.includes('predictive'), false);
    assert.equal(ids[ids.length - 1], 'review');
  });

  it('App wires PSC draft schedule, Review recipe, and scientific status', () => {
    const app = readFileSync(resolve(root, 'App.tsx'), 'utf8');
    const sim = readFileSync(resolve(root, 'destinations/SimulationInfoWorkspace.tsx'), 'utf8');
    assert.ok(app.includes('buildReviewRecipe'));
    assert.ok(app.includes('pscOffTicksDraft'));
    assert.ok(app.includes('experiment-psc-config'));
    assert.ok(app.includes('restoreModelDefaultsIntoDraft'));
    assert.ok(sim.includes('Beta 4: partially validated — bounded supported claims'));
    assert.ok(sim.includes('GEN_POST_V1B_VERTICAL_SUPPORT_ESCAPE_REPAIR'));
  });
});
