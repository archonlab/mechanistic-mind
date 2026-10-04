/** S7C destination-depth polish regressions (no simulation). */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { describe, it } from 'node:test';
import { resolve } from 'node:path';
import { OBSERVATION_DESTINATIONS } from './layoutShell.ts';

const root = resolve('src');

describe('S7C destination-depth polish', () => {
  it('Organism owns central workspace with primary state first', () => {
    const org = readFileSync(resolve(root, 'destinations/OrganismCentralWorkspace.tsx'), 'utf8');
    assert.ok(org.includes('organism-central-primary'));
    assert.ok(org.includes('organism-state-card'));
    assert.ok(org.includes("id: 'authority'"));
    assert.ok(org.includes('NOT</strong> anatomy'));
    assert.ok(org.includes('onSelectAgent'));
  });

  it('Hearing owns center with receptor phenomenon and LPS/OATT distinct', () => {
    const h = readFileSync(resolve(root, 'workspaces/ObservationCentralWorkspaces.tsx'), 'utf8');
    assert.ok(h.includes('hearing-phenomenon-card'));
    assert.ok(h.includes('LPS transport timing remains distinct from OATT'));
    assert.ok(h.includes('HearingWorkspacePanel'));
    assert.ok(h.includes("id: 'playback'"));
  });

  it('Events bounded stream with filters and no invented narrative', () => {
    const ev = readFileSync(resolve(root, 'destinations/EventsCentralWorkspace.tsx'), 'utf8');
    assert.ok(ev.includes('DISPLAY_CAP'));
    assert.ok(ev.includes('events-stream-list'));
    assert.ok(ev.includes('Other/Unclassified'));
    assert.ok(ev.includes('LIVE_FE_EVENTS_DISPLAY_MAX'));
    assert.ok(!ev.includes('intentional signaling'));
  });

  it('Simulation Info separate from World setup', () => {
    const s = readFileSync(resolve(root, 'destinations/SimulationInfoWorkspace.tsx'), 'utf8');
    assert.ok(s.includes('not World/Model setup'));
    assert.ok(s.includes('siminfo-empty-selection'));
    assert.ok(s.includes('Select a cell, surface, object or organism'));
  });

  it('Scientific Tools landing lists existing tools only', () => {
    const landing = readFileSync(resolve(root, 'destinations/ScientificToolsLanding.tsx'), 'utf8');
    for (const id of ['analyze', 'experiment', 'sensors', 'signals', 'intervention', 'world_status', 'runs']) {
      assert.ok(landing.includes(`id: '${id}'`), id);
    }
    const side = readFileSync(resolve(root, 'chrome/LeftSidebar.tsx'), 'utf8');
    const blockStart = side.indexOf("id === 'SCIENTIFIC_TOOLS'");
    const block = side.slice(blockStart, blockStart + 280);
    assert.ok(block.includes("workspace: 'INSPECT'"));
    assert.ok(!block.includes("applyRailDestination('analyze'"));
  });

  it('InspectWorkspace center ownership includes Simulation Info and Tools', () => {
    const inspect = readFileSync(resolve(root, 'workspaces/InspectWorkspace.tsx'), 'utf8');
    assert.ok(inspect.includes("dest === 'SIMULATION_INFO'"));
    assert.ok(inspect.includes("dest === 'SCIENTIFIC_TOOLS'"));
  });

  it('public destinations and models unchanged', () => {
    assert.equal(OBSERVATION_DESTINATIONS[0].id, 'WORLD');
    assert.equal(OBSERVATION_DESTINATIONS[1].id, 'MODEL');
    const presets = readFileSync(resolve(root, 'observer/modelPreset.ts'), 'utf8');
    assert.ok(presets.includes('UI_PRESET_ACANTHOSTEGA_BETA4'));
  });

  it('bottom drawer is destination-aware', () => {
    const bottom = readFileSync(resolve(root, 'chrome/BottomEvidencePanel.tsx'), 'utf8');
    assert.ok(bottom.includes('observationDest'));
    assert.ok(bottom.includes('bottom-context-hint'));
  });
});
