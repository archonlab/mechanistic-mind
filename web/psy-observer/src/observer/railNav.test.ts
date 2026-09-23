import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { HOME_TOOLS } from '../desktop/types.ts';
import { applyRailDestination, railDestination, railSelectedTool } from './railNav.ts';

describe('rail navigation contract', () => {
  it('maps every HOME_TOOLS icon to a reachable destination', () => {
    const expected: Record<string, string> = {
      experiment: 'EXPERIMENT',
      intervention: 'INTERVENTION',
      observe: 'OBSERVE',
      sensors: 'SENSORS',
      signals: 'SIGNALS',
      runs: 'RUNS',
      world_status: 'WORLD_STATUS',
    };
    for (const t of HOME_TOOLS) {
      const d = railDestination(t.id);
      assert.equal(d.deviceTool, t.id);
      assert.equal(d.deviceCollapsed, true);
      if (t.id === 'analyze') {
        assert.equal(d.workspace, 'ANALYZE');
      } else {
        assert.equal(d.workspace, 'INSPECT');
        assert.equal(d.inspector, expected[t.id]);
        assert.equal(d.inspectorOpen, true);
      }
    }
  });

  it('click BODY-equivalent Sensors from RUN enters INSPECT/SENSORS', () => {
    const { nextWorkspace } = applyRailDestination('sensors', {
      workspace: 'RUN', inspector: 'BODY', inspectorOpen: true,
    });
    assert.equal(nextWorkspace.workspace, 'INSPECT');
    assert.equal(nextWorkspace.inspector, 'SENSORS');
    assert.equal(nextWorkspace.inspectorOpen, true);
  });

  it('click SIGNALS from ANALYZE enters INSPECT/SIGNALS', () => {
    const { nextWorkspace } = applyRailDestination('signals', {
      workspace: 'ANALYZE', inspector: 'BODY', inspectorOpen: false,
    });
    assert.equal(nextWorkspace.workspace, 'INSPECT');
    assert.equal(nextWorkspace.inspector, 'SIGNALS');
  });

  it('click ANALYZE from INSPECT enters ANALYZE', () => {
    const { nextWorkspace } = applyRailDestination('analyze', {
      workspace: 'INSPECT', inspector: 'PREDICTIVE', inspectorOpen: true,
    });
    assert.equal(nextWorkspace.workspace, 'ANALYZE');
  });

  it('inspector-to-inspector via rail', () => {
    const { nextWorkspace } = applyRailDestination('signals', {
      workspace: 'INSPECT', inspector: 'SENSORS', inspectorOpen: true,
    });
    assert.equal(nextWorkspace.inspector, 'SIGNALS');
    assert.equal(nextWorkspace.workspace, 'INSPECT');
  });

  it('selected state is truthful for ANALYZE and INSPECT sections', () => {
    assert.equal(railSelectedTool({ workspace: 'ANALYZE', inspector: 'BODY', inspectorOpen: true }, 'experiment', true), 'analyze');
    assert.equal(railSelectedTool({ workspace: 'INSPECT', inspector: 'SIGNALS', inspectorOpen: true }, 'home', true), 'signals');
    assert.equal(railSelectedTool({ workspace: 'INSPECT', inspector: 'BODY', inspectorOpen: true }, 'home', true), 'sensors');
    assert.equal(railSelectedTool({ workspace: 'INSPECT', inspector: 'EXPERIMENT', inspectorOpen: true }, 'home', true), 'experiment');
  });
});
