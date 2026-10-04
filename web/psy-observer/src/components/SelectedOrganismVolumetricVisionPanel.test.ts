/** Frontend: volumetric vision panel uses exact payload — no VW7 raycast / pixels. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, it } from 'node:test';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here); // this file lives in src/components

describe('SELECTED_ORGANISM_VOLUMETRIC_VISION_VIEW_V1 UI', () => {
  it('panel source forbids VW7 mesh raycast and pixel inference', () => {
    const src = readFileSync(
      join(root, 'SelectedOrganismVolumetricVisionPanel.tsx'),
      'utf8',
    );
    assert.match(src, /selected_organism_volumetric_vision_view/);
    assert.match(src, /NOT A CAMERA/);
    assert.match(src, /NOT RENDERER PIXELS/);
    assert.match(src, /AUDIT REJECTED CANDIDATES/);
    assert.match(src, /Does not raycast VW7/);
    assert.doesNotMatch(src, /\.raycast\(|Raycaster|getImageData|readPixels/);
    assert.doesNotMatch(src, /occupancy_volumes/);
  });

  it('TiktaalikEyePanel exposes DUAL / VOLUMETRIC / CAUSAL modes', () => {
    const src = readFileSync(join(root, 'TiktaalikEyePanel.tsx'), 'utf8');
    assert.match(src, /vision-mode-dual/);
    assert.match(src, /vision-mode-volumetric/);
    assert.match(src, /vision-mode-causal/);
    assert.match(src, /SelectedOrganismVolumetricVisionPanel/);
    assert.match(src, /EyeDockVisionWorkspace/);
  });

  it('left dock still hosts single VISION workspace', () => {
    const src = readFileSync(join(root, 'TiktaalikEyeDock.tsx'), 'utf8');
    assert.match(src, /left-vision-workspace/);
    assert.match(src, /left-sensory-hearing/);
    assert.match(src, /HearingWorkspacePanel/);
  });
});
