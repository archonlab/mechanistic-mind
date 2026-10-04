/** S7D Eye dock dual-agent FPV + compact Hearing — source contract tests. */

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { describe, it } from 'node:test';
import { fileURLToPath } from 'node:url';

const root = dirname(fileURLToPath(import.meta.url));
const src = (...p: string[]) => readFileSync(join(root, ...p), 'utf8');

describe('S7D Eye dock dual-agent FPV', () => {
  it('dual workspace renders two cards, isolates traces, and does not passively select', () => {
    const dual = src('EyeDockVisionWorkspace.tsx');
    assert.match(dual, /eye-dual-fpv-card-agent_0|eye-dual-fpv-card-\$\{agentId\}/);
    assert.match(dual, /latest_exact_by_agent/);
    assert.match(dual, /latest_exact_by_agent|traceForAgent|retainedExactByAgent/);
    const life = src('eyeDockDualFpvLifecycle.ts');
    assert.match(life, /Never cross-copy agents|selected-latest match only/);
    assert.match(dual, /onSelectAgent/);
    assert.match(dual, /Open detailed FPV/);
    assert.match(dual, /MAX_VISIBLE_CARDS = 2/);
    assert.match(dual, /No active agents/);
    assert.match(dual, /eye-dual-mode-receptor/);
    assert.match(dual, /eye-dual-mode-cognition/);
    assert.match(dual, /AUTHORITY AND LIMITATIONS/);
    assert.match(dual, /PhenomenonDetails/);
    assert.match(dual, /SettingInfoHelp/);
    assert.doesNotMatch(dual, /APPLY_AND_RESET|postControl\(['"]apply/);
  });

  it('compact FPV panel accepts externalTrace without falling back across agents', () => {
    const panel = src('OrganismReceptorGroundedFpvPanel.tsx');
    assert.match(panel, /chrome === 'compact'|chrome\?: FpvChrome/);
    assert.match(panel, /externalTrace/);
    assert.match(panel, /useExternal/);
    assert.match(panel, /TRACE_UNAVAILABLE_FOR_AGENT/);
  });

  it('dock gates dual payload subscription by dock-open (not Vision subtab) and suspends paint', () => {
    const dock = src('TiktaalikEyeDock.tsx');
    assert.match(dock, /syncEyeDockDualFpvSubscription/);
    assert.match(dock, /wantEyeDockDualFpvSubscription/);
    assert.doesNotMatch(dock, /want = open && centralOwnsSensory !== 'VISION'/);
    assert.doesNotMatch(dock, /syncEyeDockDualFpvSubscription\(false\)/);
    assert.doesNotMatch(dock, /want\s*=\s*[\s\S]{0,80}sensory === 'VISION'/);
    assert.match(dock, /dockHidden=\{visionSuspended\}/);
    assert.match(dock, /onOpenDetailedFpv/);
    assert.match(dock, /compact/);
    const interest = src('../observer/interest.ts');
    assert.match(interest, /eye_dock_dual_fpv/);
    assert.match(interest, /Vision or Hearing/);
  });

  it('App wires explicit card selection and detailed FPV navigation without local Apply', () => {
    const app = src('../App.tsx');
    assert.match(app, /onOpenDetailedFpv/);
    assert.match(app, /setObservationDest\('FPV_VISION'\)/);
    assert.match(app, /onEditVisionConfig/);
  });

  it('Hearing compact: primary playback controls, collapsed details, single engine', () => {
    const hw = src('../acoustic/HearingWorkspacePanel.tsx');
    assert.match(hw, /data-compact/);
    assert.match(hw, /hearing-primary-controls/);
    assert.match(hw, /Listen World/);
    assert.match(hw, /Listen Agent/);
    assert.match(hw, /hearing-master-volume/);
    assert.match(hw, /classifyHearingPlayback/);
    assert.match(hw, /LPS \/ OATT timing/);
    assert.match(hw, /PhenomenonDetails/);
    assert.match(hw, /CanonicalSonificationPanel/);
    assert.match(hw, /SelectedOrganismAuditoryViewPanel/);
    assert.match(hw, /does not change the globally selected simulation agent/);
    assert.doesNotMatch(hw, /APPLY_AND_RESET/);
  });
});
