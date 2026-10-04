import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { describe, it } from 'node:test';
import { fileURLToPath } from 'node:url';
import {
  hearingIndicatorLabel,
  hearingIndicatorKind,
  listeningIsActive,
} from './hearingActiveStatus.ts';
import {
  claimListeningMode,
  getListeningModeOwner,
  releaseListeningMode,
  resetListeningModeForTests,
} from './listeningModeOwner.ts';

const root = dirname(fileURLToPath(import.meta.url));

describe('OBSERVER_LEFT_HEARING_WORKSPACE_V1', () => {
  it('indicator labels derive from owner/mute without fabricating modes', () => {
    assert.equal(hearingIndicatorLabel({ owner: 'OFF' }), 'HEARING · OFF');
    assert.equal(hearingIndicatorLabel({ owner: 'PHYSICAL_FIELD_C1' }), 'HEARING · C1 ACTIVE');
    assert.equal(hearingIndicatorLabel({ owner: 'SELECTED_ORGANISM_SAV2' }), 'HEARING · SAV2 ACTIVE');
    assert.equal(hearingIndicatorLabel({ owner: 'PHYSICAL_FIELD_C1', muted: true }), 'HEARING · MUTED');
    assert.equal(hearingIndicatorKind({ owner: 'PHYSICAL_FIELD_C1' }), 'C1_ACTIVE');
    assert.equal(listeningIsActive('OFF'), false);
    assert.equal(listeningIsActive('PHYSICAL_FIELD_C1'), true);
  });

  it('mutual exclusion: claiming SAV2 releases C1 owner callback', () => {
    resetListeningModeForTests();
    let c1Released = 0;
    let savReleased = 0;
    claimListeningMode('PHYSICAL_FIELD_C1', () => { c1Released += 1; });
    assert.equal(getListeningModeOwner(), 'PHYSICAL_FIELD_C1');
    claimListeningMode('SELECTED_ORGANISM_SAV2', () => { savReleased += 1; });
    assert.equal(getListeningModeOwner(), 'SELECTED_ORGANISM_SAV2');
    assert.equal(c1Released, 1);
    assert.equal(savReleased, 0);
    releaseListeningMode('SELECTED_ORGANISM_SAV2');
    assert.equal(getListeningModeOwner(), 'OFF');
    resetListeningModeForTests();
  });

  it('left dock source mounts VISION|HEARING and single hearing host', () => {
    const dock = readFileSync(join(root, '../components/TiktaalikEyeDock.tsx'), 'utf8');
    assert.ok(dock.includes('left-sensory-vision'));
    assert.ok(dock.includes('left-sensory-hearing'));
    assert.ok(dock.includes('HearingWorkspacePanel'));
    assert.ok(dock.includes('left-hearing-workspace-host'));
    // Single host keep-alive comment / one HearingWorkspacePanel JSX occurrence
    const mounts = dock.split('<HearingWorkspacePanel').length - 1;
    assert.equal(mounts, 1, 'exactly one HearingWorkspacePanel mount for single-engine keep-alive');
    assert.ok(dock.includes('does not stop listening') || dock.includes('MUTE'));
  });

  it('App World layers no longer mounts C1/SAV panels; links to HEARING', () => {
    const app = readFileSync(join(root, '../App.tsx'), 'utf8');
    assert.ok(app.includes('hearing-moved-notice'));
    assert.ok(app.includes('open-left-hearing-workspace'));
    assert.ok(app.includes('openLeftHearingWorkspace'));
    assert.equal(app.includes('<CanonicalSonificationPanel'), false);
    assert.equal(app.includes('<SelectedOrganismAuditoryViewPanel'), false);
    assert.ok(app.includes('<TiktaalikEyeDock'));
  });

  it('Hearing workspace embeds probe + C1 + SAV and required warnings via panels', () => {
    const hw = readFileSync(join(root, 'HearingWorkspacePanel.tsx'), 'utf8');
    assert.ok(hw.includes('PassiveAcousticProbeControls'));
    assert.ok(hw.includes('CanonicalSonificationPanel'));
    assert.ok(hw.includes('SelectedOrganismAuditoryViewPanel'));
    assert.ok(hw.includes('OBSERVER_LEFT_HEARING_WORKSPACE_V1'));
    assert.ok(hw.includes('hearing-listening-mode'));
    const c1 = readFileSync(join(root, 'CanonicalSonificationPanel.tsx'), 'utf8');
    const sav = readFileSync(join(root, 'SelectedOrganismAuditoryViewPanel.tsx'), 'utf8');
    assert.ok(c1.includes('C1_WARNING') || c1.includes('NOT PHYSICAL Hz'));
    assert.ok(sav.includes('SAV2_WARNING') || sav.includes('NOT HUMAN HEARING'));
    assert.ok(c1.includes('PHYSICAL FIELD') && c1.includes('PASSIVE PROBE'));
    assert.ok(hw.includes('SelectedOrganismAuditoryOfflineReconstructionPanel'));
  });

  it('stores expose leftSensoryMode default VISION and openLeftHearingWorkspace', () => {
    const stores = readFileSync(join(root, '../observer/stores.ts'), 'utf8');
    assert.ok(stores.includes("leftSensoryMode: 'VISION'"));
    assert.ok(stores.includes('openLeftHearingWorkspace'));
    assert.ok(stores.includes("leftSensoryMode: 'HEARING'"));
  });
});
