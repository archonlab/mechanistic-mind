/** S7C ordinary World/Model navigation (no simulation). */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { describe, it } from 'node:test';
import { resolve } from 'node:path';
import { OBSERVATION_DESTINATIONS } from './layoutShell.ts';

describe('S7C World/Model task-flow navigation', () => {
  it('destination order is World → Model → … → Simulation Info → Scientific Tools', () => {
    const ids = OBSERVATION_DESTINATIONS.map((d) => d.id);
    assert.deepEqual(ids.slice(0, 2), ['WORLD', 'MODEL']);
    assert.ok(ids.includes('SIMULATION_INFO'));
    assert.equal(ids[ids.length - 1], 'SCIENTIFIC_TOOLS');
    assert.ok(ids.indexOf('WORLD') < ids.indexOf('MODEL'));
    assert.ok(ids.indexOf('MODEL') < ids.indexOf('ORGANISM'));
  });

  it('LeftSidebar World opens Experiment world setup, not WORLD status inspector', () => {
    const side = readFileSync(resolve('src/chrome/LeftSidebar.tsx'), 'utf8');
    assert.ok(side.includes("openExperimentInspectorTab('world'"));
    assert.ok(side.includes("openExperimentInspectorTab('model'"));
    assert.ok(side.includes("applyRailDestination('world_status'"));
    assert.ok(!side.includes("inspector: 'WORLD'"));
  });

  it('public selector remains exactly two models', () => {
    const presets = readFileSync(resolve('src/observer/modelPreset.ts'), 'utf8');
    assert.ok(presets.includes('PUBLIC_MODEL_PRESETS'));
    assert.ok(presets.includes('UI_PRESET_ACANTHOSTEGA_BETA4'));
    assert.ok(presets.includes('UI_PUBLIC_LABEL_TIKTAALIK_BETA31') || presets.includes('Tiktaalik Beta 3.1'));
  });
});
