/** Eye Hearing compact playback primary surface contracts. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { describe, it } from 'node:test';
import { fileURLToPath } from 'node:url';

const root = dirname(fileURLToPath(import.meta.url));
const hw = readFileSync(join(root, 'HearingWorkspacePanel.tsx'), 'utf8');

describe('BETA4 Eye Hearing playback primary', () => {
  it('exposes World/Agent Live-Stop, agent selector, and one master volume', () => {
    assert.match(hw, /Listen World/);
    assert.match(hw, /Listen Agent/);
    assert.match(hw, /hearing-world-live/);
    assert.match(hw, /hearing-world-stop/);
    assert.match(hw, /hearing-agent-live/);
    assert.match(hw, /hearing-agent-stop/);
    assert.match(hw, /hearing-listen-agent-select/);
    assert.match(hw, /hearing-master-volume-slider/);
    assert.match(hw, /MASTER_VOLUME|masterVolume|Master researcher playback volume/);
  });

  it('does not mutate global selected agent from listen selector', () => {
    assert.match(hw, /does not change the globally selected simulation agent/);
    assert.doesNotMatch(hw, /onSelectAgent\(/);
    assert.doesNotMatch(hw, /selectObserverAgent/);
  });

  it('uses honest playback status and distinguishes TRUE ZERO / NO SOURCE / UNAVAILABLE', () => {
    assert.match(hw, /classifyHearingPlayback/);
    assert.match(hw, /TRUE ZERO|trueZero/);
    assert.match(hw, /UNAVAILABLE|NO SOURCE|sourceAvailable/);
    assert.match(hw, /hearingPlaybackStatus/);
    assert.doesNotMatch(hw, /HEARING OFF/);
  });

  it('documents exclusive World/Agent limitation and no Apply', () => {
    assert.match(hw, /mutually exclusive/);
    assert.doesNotMatch(hw, /APPLY_AND_RESET|postControl\(['"]apply/);
  });

  it('suspends playback when dock hidden and keeps engines mounted', () => {
    assert.match(hw, /dockVisible/);
    assert.match(hw, /Suspend researcher playback/);
    assert.match(hw, /CanonicalSonificationPanel/);
    assert.match(hw, /SelectedOrganismAuditoryViewPanel/);
  });
});
