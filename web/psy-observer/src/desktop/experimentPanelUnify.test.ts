import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, it } from 'node:test';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const distAssets = join(root, '../../../mechanistic_mind/ui/psy_observer_web/web_dist/assets');

describe('EXPERIMENT panel unified draft + one Apply', () => {
  it('deviceBody experiment tabs have no per-tab Apply buttons', () => {
    const app = readFileSync(join(root, 'App.tsx'), 'utf8');
    const start = app.indexOf('function deviceBody');
    const end = app.indexOf('function floatBody');
    assert.ok(start > 0 && end > start);
    const device = app.slice(start, end);
    assert.equal(device.includes('APPLY LIVE'), false);
    assert.equal(device.includes('APPLY & RESET WORLD'), false);
    assert.equal(device.includes('APPLY &amp; RESET WORLD'), false);
    assert.equal(device.includes('applyLiveFromDevice'), false);
    assert.equal(device.includes('onClick={applyFromDevice}'), false);
  });

  it('one APPLY EXPERIMENT control lives on Review / Apply only, not category panels', () => {
    const app = readFileSync(join(root, 'App.tsx'), 'utf8');
    const dock = readFileSync(join(root, 'inspectors/InspectorDock.tsx'), 'utf8');
    assert.ok(dock.includes('experiment-apply-bar'));
    assert.ok(dock.includes('experimentApplyBar'));
    assert.ok(dock.includes("activeTab === 'review'"));
    assert.ok(app.includes('data-testid="apply-experiment"'));
    assert.ok(app.includes('Apply configuration and start a new run at tick 0'));
    assert.ok(app.includes('experimentDraftSnap'));
    assert.ok(app.includes('activeExperiment'));
    assert.ok(app.includes('buildCanonicalApplyPayload'));
  });

  it('production web_dist has the shared apply bar', () => {
    const files = readdirSync(distAssets).filter((f) => f.startsWith('index-') && f.endsWith('.js'));
    assert.ok(files.length > 0, 'web_dist index JS missing — rebuild Observer UI');
    const js = readFileSync(join(distAssets, files[0]), 'utf8');
    assert.ok(js.includes('experiment-apply-bar'), 'built SPA missing experiment-apply-bar');
    assert.ok(
      js.includes('Apply configuration and start a new run at tick 0') || js.includes('APPLY EXPERIMENT'),
      'built SPA missing Apply control label',
    );
    assert.ok(js.includes('Acanthostega Phase A Material Properties'), 'built SPA missing material properties preset');
    assert.ok(js.includes('passive — no consequence kernel'), 'built SPA missing passive property status');
    assert.ok(js.includes('Acanthostega Phase A Surface Deposition'), 'built SPA missing surface deposition preset');
    assert.ok(js.includes('APPLY TO SURFACE'), 'built SPA missing surface deposition probe');
    assert.ok(js.includes('no terrain consequence yet'), 'built SPA missing deposit status');
    assert.ok(js.includes('Acanthostega Phase A Surface Traction'), 'built SPA missing surface traction preset');
    assert.ok(js.includes('continuous physical law'), 'built SPA missing traction law label');
    assert.ok(js.includes('not a recipe'), 'built SPA missing traction recipe label');
    assert.ok(js.includes('Acanthostega Phase A Traction Experience'), 'built SPA missing traction experience preset');
    assert.ok(js.includes('Acanthostega Phase A Traction Adaptation'), 'built SPA missing traction adaptation preset');
    assert.ok(js.includes('Acanthostega Phase A Surface Optical'), 'built SPA missing surface optical preset');
    assert.ok(js.includes('Acanthostega Phase B World Material Transactions'), 'built SPA missing material transaction preset');
    assert.ok(js.includes('Acanthostega Phase B Multi-Content Index'), 'built SPA missing multi-content index preset');
    assert.ok(js.includes('not a traction label'), 'built SPA missing coating boundary');
    assert.ok(js.includes('not agent-accessible'), 'built SPA missing experience access label');
    assert.ok(js.includes('researcher-only'), 'built SPA missing researcher-only label');
  });

  it('Model hosts cognition enablement; Cognition primary tab removed', () => {
    const app = readFileSync(join(root, 'App.tsx'), 'utf8');
    const presets = readFileSync(join(root, 'observer/modelPreset.ts'), 'utf8');
    const start = app.indexOf('function deviceBody');
    const end = app.indexOf('function floatBody');
    const device = app.slice(start, end);
    assert.equal(device.includes("tabId === 'model' || tabId === 'cognition'"), false);
    assert.ok(device.includes("tabId === 'model'"));
    assert.equal(device.includes("tabId === 'cognition'"), false);
    assert.ok(device.includes('experiment-model-config'));
    assert.equal(device.includes('experiment-cognition-config'), false);
    assert.ok(device.includes('experiment-cognition-enabled'));
    assert.ok(device.includes('experiment-model-preset'));
    assert.ok(device.includes('experiment-preset-status'));
    assert.ok(device.includes('experiment-preset-identity'));
    assert.ok(app.includes('PUBLIC_MODEL_PRESETS.map'));
    assert.ok(presets.includes('UI_PRESET_ACANTHOSTEGA_MATERIALS'));
    assert.ok(presets.includes('UI_PRESET_ACANTHOSTEGA_MATERIAL_VISION'));
    assert.ok(presets.includes('UI_PRESET_ACANTHOSTEGA_SINGLE_GRASP'));
  });

  it('does not auto-switch the model selector to CUSTOM on field edits', () => {
    const app = readFileSync(join(root, 'App.tsx'), 'utf8');
    assert.equal(app.includes("setPreset('CUSTOM')"), false);
    assert.ok(app.includes('draftPresetModified'));
    assert.ok(app.includes('presetModifiedStatusLabel'));
  });

  it('WorldMap draws researcher-only resource object glyphs', () => {
    const map = readFileSync(join(root, 'components/WorldMap.tsx'), 'utf8');
    assert.ok(map.includes('drawResourceObjects'));
    assert.ok(map.includes('drawManipulators'));
    assert.ok(map.includes('researcher-only overlay — not a recognition claim'));
    assert.ok(map.includes('resource-object-tooltip'));
    assert.ok(map.includes('compliance'));
    assert.ok(map.includes('surface_affinity'));
    assert.ok(map.includes('not agent-accessible'));
    assert.ok(map.includes('passive — no consequence kernel'));
    const app = readFileSync(join(root, 'App.tsx'), 'utf8');
    const presets = readFileSync(join(root, 'observer/modelPreset.ts'), 'utf8');
    assert.ok(presets.includes('UI_PRESET_ACANTHOSTEGA_MATERIAL_PROPERTIES'));
    assert.ok(presets.includes('UI_PRESET_ACANTHOSTEGA_SURFACE_DEPOSITION'));
    assert.ok(presets.includes('UI_PRESET_ACANTHOSTEGA_SURFACE_TRACTION'));
    assert.ok(app.includes('model-phase-notes'));
    assert.ok(app.includes('Phase A/B material'));
    assert.ok(presets.includes('UI_PRESET_ACANTHOSTEGA_TRACTION_EXPERIENCE'));
    assert.ok(app.includes('grasp') || app.includes('Phase A/B material'));
    assert.ok(presets.includes('UI_PRESET_ACANTHOSTEGA_TRACTION_ADAPTATION'));
    assert.ok(app.includes('surface-optical') || app.includes('Phase A/B material'));
    assert.ok(presets.includes('UI_PRESET_ACANTHOSTEGA_SURFACE_OPTICAL'));
    assert.ok(presets.includes('UI_PRESET_ACANTHOSTEGA_WORLD_MATERIAL'));
    assert.ok(presets.includes('UI_PRESET_ACANTHOSTEGA_MULTI_CONTENT'));
    assert.ok(presets.includes('UI_PRESET_ACANTHOSTEGA_PROCEDURAL_COLUMNS'));
    assert.ok(presets.includes('UI_PRESET_ACANTHOSTEGA_COLUMN_TRANSFER'));
    assert.ok(presets.includes('UI_PRESET_ACANTHOSTEGA_LOCAL_SIGNAL'));
    assert.ok(presets.includes('UI_PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS'));
    assert.ok(app.includes('contact-acoustic-overlay'));
    assert.ok(presets.includes('UI_PRESET_ACANTHOSTEGA_FREE_OBJECT_KINEMATICS'));
    assert.ok(app.includes('free-object-kinematics-overlay'));
    assert.ok(app.includes('collision physics: not implemented'));
    assert.ok(!app.includes('PROJECTILE') && !app.includes('THROWN_TOOL') && !app.includes('THROW probe'));
    assert.ok(!app.includes('BODY_SOUND') && !app.includes('PUSH_SOUND') && !app.includes('COLLISION_SOUND'));
    assert.ok(app.includes('local-signal-overlay'));
    assert.ok(app.includes('not a semantic message'));
    assert.ok(app.includes('finite propagation delay'));
    assert.ok(app.includes('finite range'));
    assert.ok(!app.includes('source_direction'));
    assert.ok(!app.includes('source_distance'));
    assert.ok(app.includes('surface-column-transfer-inspector'));
    assert.ok(!app.includes('surface-column-transfer-button'));
    assert.ok(app.includes('surface-column-inspector'));
        assert.ok(app.includes('volumetric-occupancy-inspector'));
    assert.ok(app.includes('occupancy-support-contact-inspector'));
    assert.ok(app.includes('volumetric-material-separation-inspector'));
    assert.ok(app.includes('vw6-vision-3d-inspector'));
    const pane = readFileSync(join(root, 'chrome/WorldPane.tsx'), 'utf8');
    assert.ok(pane.includes('OccupancyVolumeView') || pane.includes('occupancy-volume-view'));
    assert.ok(pane.includes('world-view-volume'));
    assert.ok(pane.includes('world-viewport-mode-bar'));
    assert.ok(app.includes('VW6 MINIMAL VISION 3D'));
    assert.ok(app.includes('VW3 VOLUMETRIC SEPARATION'));
    assert.ok(app.includes('VW2 SUPPORT / CONTACT'));
    assert.ok(app.includes('contradicts legacy surface') || app.includes('LEGACY / DERIVED SURFACE PROJECTION'));
    assert.ok(app.includes('AUTHORITATIVE VOLUMETRIC OCCUPANCY'));
    assert.ok(app.includes('LEGACY / DERIVED SURFACE PROJECTION'));
    assert.ok(app.includes('not agent-accessible · geometry metadata only'));
    // Phase notes remain researcher-only; Multi-Content co-location prose lives in capability banners/docs.
    assert.ok(app.includes('researcher-only'));
    assert.ok(app.includes('not agent-accessible'));
    assert.ok(map.includes('no terrain consequence yet'));
    assert.ok(map.includes('continuous physical law'));
    assert.ok(map.includes('not a recipe'));
    assert.ok(map.includes('drawSurfaceDeposits'));
    assert.equal((app.match(/Model line/g) || []).length, 0);
  });
});
