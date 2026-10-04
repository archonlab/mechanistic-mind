import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { describe, it } from 'node:test';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = dirname(fileURLToPath(import.meta.url));

describe('SAV1 UI labelling', () => {
  it('panel contains required SAV1 warning and section split', () => {
    const src = readFileSync(join(root, 'SelectedOrganismAuditoryViewPanel.tsx'), 'utf8');
    assert.ok(src.includes('SELECTED ORGANISM AUDITORY VIEW'));
    assert.ok(src.includes('NOT HUMAN HEARING'));
    assert.ok(src.includes('NOT MIND READING'));
    assert.ok(src.includes('ORGANISM LEFT RECEPTOR CHANNELS'));
    assert.ok(src.includes('ORGANISM RIGHT RECEPTOR CHANNELS'));
    assert.ok(src.includes('WHAT THE ORGANISM RECEIVED'));
    assert.ok(src.includes('RESEARCHER CAUSAL PROVENANCE'));
    assert.ok(src.includes('SAV2_MODE_LABEL') || src.includes('SELECTED ORGANISM AUDITORY SONIFICATION'));
    assert.ok(src.includes('NOT SAV2 amplitude source'));
    assert.equal(/recognized an impact|threatening|understood the signal/i.test(src), false);
  });
});
