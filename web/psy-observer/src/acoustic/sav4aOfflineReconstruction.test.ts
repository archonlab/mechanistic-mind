import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { describe, it } from 'node:test';
import { fileURLToPath } from 'node:url';
import {
  SAV4A_SCHEMA,
  SAV4A_TITLE,
  SAV4A_WARNING_GAPS,
  SAV4A_WARNING_NO_AUDIO,
  SAV4A_WARNING_TICK,
  authorityBadge,
} from './sav4aOffline.ts';

const root = dirname(fileURLToPath(import.meta.url));

describe('SAV4A offline reconstruction UI', () => {
  it('exports schema and read-only warnings', () => {
    assert.equal(SAV4A_SCHEMA, 'SELECTED_ORGANISM_AUDITORY_OFFLINE_RECONSTRUCTION_SAV4A_V1');
    assert.ok(SAV4A_TITLE.includes('SAV4A'));
    assert.ok(SAV4A_WARNING_GAPS.includes('GAPS'));
    assert.ok(SAV4A_WARNING_TICK.includes('not physical'));
    assert.ok(SAV4A_WARNING_NO_AUDIO.includes('SAV4B'));
    assert.equal(authorityBadge('OATT_EXACT_TRACE'), 'OATT');
    assert.equal(authorityBadge('LEGACY_OSC_A5_ONLY'), 'LEGACY A5');
    assert.equal(authorityBadge(null), 'UNAVAILABLE');
  });

  it('Hearing workspace mounts SAV4A after SAV3; SAV4B player is separate section', () => {
    const hw = readFileSync(join(root, 'HearingWorkspacePanel.tsx'), 'utf8');
    assert.ok(hw.includes('SelectedOrganismAuditoryOfflineReconstructionPanel'));
    assert.ok(hw.includes('SelectedOrganismPhysicalFieldComparisonPanel'));
    const panel = readFileSync(
      join(root, 'SelectedOrganismAuditoryOfflineReconstructionPanel.tsx'),
      'utf8',
    );
    assert.ok(panel.includes('hearing-sav4a-section'));
    assert.ok(panel.includes('hearing-sav4b-section'));
    assert.ok(panel.includes('hearing-sav4b-play'));
    assert.equal(panel.includes('new AudioContext'), false);
    assert.equal(panel.includes('OfflineAudioContext'), false);
    assert.ok(panel.includes('LEGACY A5'));
    assert.ok(panel.includes('SAV4A_WARNING_GAPS') || panel.includes(SAV4A_WARNING_GAPS));
  });

  it('Analyzer panel exposes genuine phase progress without invented percent', () => {
    const ar = readFileSync(join(root, '../components/AnalyzeResultsPanel.tsx'), 'utf8');
    assert.ok(ar.includes('analyze-sav4a-section'));
    assert.ok(ar.includes('analyze-sav4a-progress'));
    assert.ok(ar.includes('indeterminate'));
    assert.ok(ar.includes('no invented'));
  });

  it('does not create OfflineAudioContext or WAV export in SAV4A/B panel source', () => {
    const panel = readFileSync(
      join(root, 'SelectedOrganismAuditoryOfflineReconstructionPanel.tsx'),
      'utf8',
    );
    assert.equal(panel.includes('new AudioContext'), false);
    assert.equal(panel.includes('OfflineAudioContext'), false);
    assert.ok(panel.includes('No WAV'));
  });
});
