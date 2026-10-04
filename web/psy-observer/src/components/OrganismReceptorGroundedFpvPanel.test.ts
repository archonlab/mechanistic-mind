import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { describe, it } from 'node:test';
import { fileURLToPath } from 'node:url';

const root = dirname(fileURLToPath(import.meta.url));

describe('organism receptor grounded 3D FPV panel', () => {
  it('panel + eye dock modes reference O4 FPV schema', () => {
    const panel = readFileSync(join(root, 'OrganismReceptorGroundedFpvPanel.tsx'), 'utf8');
    assert.match(panel, /ORGANISM_RECEPTOR_GROUNDED_3D_FPV|RECEPTOR_FPV|COGNITION_FPV/);
    assert.match(panel, /NOT A CAMERA/);
    assert.match(panel, /NOT HUMAN RGB/);
    assert.match(panel, /render_as_darkness|TRACE UNAVAILABLE|not rendered as/);
    assert.match(panel, /display smooth/);
    assert.match(panel, /organism_receptor_grounded_3d_fpv/);
    const eye = readFileSync(join(root, 'TiktaalikEyePanel.tsx'), 'utf8');
    assert.match(eye, /EyeDockVisionWorkspace/);
    assert.match(eye, /DUAL FPV/);
    const dual = readFileSync(join(root, 'EyeDockVisionWorkspace.tsx'), 'utf8');
    assert.match(dual, /RECEPTOR_FPV/);
    assert.match(dual, /COGNITION_FPV/);
    assert.match(dual, /OrganismReceptorGroundedFpvPanel/);
    assert.match(dual, /latest_exact_by_agent/);
  });

  it('rerenders on FPV frame/trace identity, not only mount', () => {
    const panel = readFileSync(join(root, 'OrganismReceptorGroundedFpvPanel.tsx'), 'utf8');
    assert.match(panel, /latest\?\.trace_id/);
    assert.match(panel, /obs_tick=\$\{latest\.observation_tick\}/);
    assert.match(panel, /receptor_tick=\$\{latest\.receptor_tick\}/);
  });
});
