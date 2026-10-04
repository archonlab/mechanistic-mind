/** S7C Apply effect / reset placement regressions (no simulation). */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { describe, it } from 'node:test';
import { resolve } from 'node:path';

describe('S7C Apply effect and reset UX', () => {
  it('Vision category has no global Apply button mount', () => {
    const dock = readFileSync(resolve('src/inspectors/InspectorDock.tsx'), 'utf8');
    assert.ok(dock.includes("activeTab === 'review'"));
    assert.ok(dock.includes('showGlobalApply'));
    assert.ok(dock.includes('experiment-apply-hint'));
    assert.ok(dock.includes('{ id: \'review\', label: \'Review / Apply\' }'));
  });

  it('global Apply label names tick-0 reset and lives only on Review', () => {
    const app = readFileSync(resolve('src/App.tsx'), 'utf8');
    assert.ok(app.includes('Apply configuration and start a new run at tick 0'));
    assert.ok(app.includes('experiment-review-apply'));
    assert.ok(app.includes('Changes saved to experiment draft — current run unchanged'));
    assert.ok(app.includes('window.confirm'));
    assert.ok(app.includes('tickNow > 0'));
    assert.equal((app.match(/data-testid="apply-experiment"/g) || []).length, 1);
  });

  it('Experiment Vision tab is deferred draft-only', () => {
    const app = readFileSync(resolve('src/App.tsx'), 'utf8');
    const start = app.indexOf("if (tabId === 'vision')");
    const end = app.indexOf("if (tabId === 'model')");
    assert.ok(start > 0 && end > start);
    const vision = app.slice(start, end);
    assert.ok(vision.includes('deferred'));
    assert.ok(vision.includes('setVisionDraft'));
    assert.ok(!vision.includes('setSpatialVision('));
    assert.ok(!vision.includes('/api/vision'));
    assert.ok(vision.includes('experiment-draft-hint'));
  });

  it('audit artifact classifies APPLY_AND_RESET_WORLD', () => {
    const audit = readFileSync(
      resolve('../../results/s7c_observer_task_flow_and_progressive_disclosure_repair/APPLY_EFFECT_AND_RESET_AUDIT.json'),
      'utf8',
    );
    assert.ok(audit.includes('APPLY_AND_RESET_WORLD'));
    assert.ok(audit.includes('MISLEADING_LOCAL_PLACEMENT'));
    assert.ok(audit.includes('"class": "C"'));
  });
});
