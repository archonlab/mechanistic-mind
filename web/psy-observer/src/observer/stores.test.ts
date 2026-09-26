import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { interestFor } from './interest.ts';
import {
  clockStore,
  frameStore,
  noteRender,
  renderCounts,
  resetRenderCounts,
  slimStatusFromFrame,
  statusStore,
  workspaceStore,
} from './stores.ts';

describe('workspace interest', () => {
  it('RUN does not request diagnostics or shadow', () => {
    const p = interestFor('RUN', 'BODY');
    assert.equal(p.preset, 'MINIMAL');
    assert.equal(p.pscShadow, 'never');
    assert.equal(p.analyzePolling, false);
    assert.deepEqual(p.diagnostics, []);
  });
  it('INSPECT SIGNALS requests signal diagnostics, shadow remains opt-in', () => {
    const p = interestFor('INSPECT', 'SIGNALS');
    assert.ok(p.products.includes('signal_sensorimotor'));
    assert.equal(p.pscShadow, 'opt-in');
  });
  it('ANALYZE does not bind HOT diagnostics', () => {
    const p = interestFor('ANALYZE', 'BODY');
    assert.equal(p.analyzePolling, true);
    assert.equal(p.preset, 'MINIMAL');
    assert.deepEqual(p.diagnostics, []);
  });
});

describe('store isolation', () => {
  it('frame notify does not require status listener', () => {
    let frames = 0;
    let statuses = 0;
    const u1 = frameStore.subscribe(() => { frames += 1; });
    const u2 = statusStore.subscribe(() => { statuses += 1; });
    frameStore.setLive({ header: { tick: 1 } });
    assert.equal(frames, 1);
    assert.equal(statuses, 0);
    u1(); u2();
  });
  it('clock notify is independent of frames', () => {
    let clocks = 0;
    let frames = 0;
    const u1 = clockStore.subscribe(() => { clocks += 1; });
    const u2 = frameStore.subscribe(() => { frames += 1; });
    clockStore.set(Date.now());
    assert.equal(clocks, 1);
    assert.equal(frames, 0);
    u1(); u2();
  });
  it('slim status frozen fields survive HEADLESS headers', () => {
    const s = slimStatusFromFrame({
      header: { display_frozen: true, display_tick: 12, sim_tick: 99, execution_mode: 'HEADLESS', status: 'RUNNING' },
    });
    assert.equal(s.displayFrozen, true);
    assert.equal(s.displayTick, 12);
    assert.equal(s.simTick, 99);
    assert.equal(s.executionMode, 'HEADLESS');
  });
  it('workspace switch is not a science field', () => {
    workspaceStore.set({ workspace: 'INSPECT', inspector: 'PREDICTIVE', inspectorOpen: true });
    assert.equal(workspaceStore.get().workspace, 'INSPECT');
    workspaceStore.set({ workspace: 'RUN', inspector: 'BODY', inspectorOpen: true });
  });
});

describe('render probe helper', () => {
  it('counts named renders', () => {
    resetRenderCounts();
    noteRender('WorldPane');
    noteRender('WorldPane');
    noteRender('App');
    assert.equal(renderCounts.WorldPane, 2);
    assert.equal(renderCounts.App, 1);
  });
});
