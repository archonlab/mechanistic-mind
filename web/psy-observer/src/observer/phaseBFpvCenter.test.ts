/** S7C Phase B — FPV center, progressive disclosure, info popovers (no simulation). */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { describe, it } from 'node:test';
import { resolve } from 'node:path';

const root = resolve('src');
const results = resolve('../../results/s7c_observer_task_flow_and_progressive_disclosure_repair');

describe('S7C Phase B FPV center and progressive disclosure', () => {
  it('FPV destination owns center; World Map is not primary under FPV', () => {
    const inspect = readFileSync(resolve(root, 'workspaces/InspectWorkspace.tsx'), 'utf8');
    assert.ok(inspect.includes('observationCentral'));
    assert.ok(inspect.includes("dest === 'FPV_VISION'"));
    assert.ok(inspect.includes('observation-central-host'));
    assert.ok(inspect.includes("data-center-owner"));
    const side = readFileSync(resolve(root, 'chrome/LeftSidebar.tsx'), 'utf8');
    assert.ok(side.includes("eyeDockMode: 'CLOSED'"));
    assert.ok(side.includes("id === 'FPV_VISION'"));
  });

  it('central workspace reuses O4 panel — no second perception implementation', () => {
    const fpv = readFileSync(resolve(root, 'components/FpvObservationWorkspace.tsx'), 'utf8');
    assert.ok(fpv.includes('OrganismReceptorGroundedFpvPanel'));
    assert.ok(fpv.includes('CAUSAL_SPLIT'));
    assert.ok(fpv.includes('fpv-central-primary'));
    assert.ok(fpv.includes('no frontend raycast'));
    assert.ok(fpv.includes('PhenomenonDetails'));
  });

  it('progressive disclosure categories exist and default collapsed via details', () => {
    const details = readFileSync(resolve(root, 'components/PhenomenonDetails.tsx'), 'utf8');
    assert.ok(details.includes('<details'));
    assert.ok(details.includes('phenomenon-category'));
    const fpv = readFileSync(resolve(root, 'components/FpvObservationWorkspace.tsx'), 'utf8');
    for (const id of ['reached', 'spatial', 'spectral', 'occlusion', 'cognition', 'timing', 'authority']) {
      assert.ok(fpv.includes(`id: '${id}'`), id);
    }
    assert.ok(fpv.indexOf("id: 'authority'") > fpv.indexOf("id: 'reached'"));
  });

  it('info popovers are keyboard-accessible and not hover-only', () => {
    const help = readFileSync(resolve(root, 'components/SettingInfoHelp.tsx'), 'utf8');
    assert.ok(help.includes('Escape'));
    assert.ok(help.includes('aria-label'));
    assert.ok(help.includes('role="dialog"'));
    assert.ok(help.includes('onClick'));
    assert.ok(help.includes('focus()'));
    const vision = readFileSync(resolve(root, 'components/VisionExperimenterControl.tsx'), 'utf8');
    assert.ok(vision.includes('SettingInfoHelp'));
    assert.ok(vision.includes('info-vision-enabled'));
    assert.ok(vision.includes('info-spatial-vision'));
    assert.ok(!vision.includes('OFF matches Beta 3 (exo_* intensity only)'));
  });

  it('corrected canonical default authority is count=1 (not obsolete two-OFF)', () => {
    const audit = readFileSync(resolve(results, 'BETA4_MECHANISM_DEFAULT_AUDIT.json'), 'utf8');
    const j = JSON.parse(audit);
    assert.equal(j.corrected_authority?.CANONICAL_DEFAULT_OFF_COUNT, 1);
    assert.equal(j.corrected_authority?.PROSPECTIVE_SCENARIO_COMPETITION_DEFAULT, false);
    assert.equal(j.corrected_authority?.EXPERIMENTAL_PHYSICAL_SIGNAL_DEFAULT, true);
    assert.equal(j.corrected_authority?.R3_FORCED_CANONICAL, false);
    assert.equal(j.corrected_authority?.OCCLUSION_FORCED_CANONICAL, false);
  });

  it('display-only FPV modes do not invoke Apply', () => {
    const fpv = readFileSync(resolve(root, 'components/FpvObservationWorkspace.tsx'), 'utf8');
    assert.ok(!fpv.includes('applyExperiment'));
    assert.ok(!fpv.includes('APPLY EXPERIMENT'));
    assert.ok(!fpv.includes('applyFromDevice'));
  });
});
