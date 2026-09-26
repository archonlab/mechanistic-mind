import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  clampWindow,
  closeWindow,
  configPending,
  focusWindow,
  nextZ,
  openOrFocusWindow,
  preferredOpenSize,
  simulationCenterX,
} from './floatingWindows.ts';

describe('OBSERVER_DESKTOP_01 floating windows', () => {
  it('opens, focuses, and closes with deterministic z-order', () => {
    const bounds = { width: 900, height: 700 };
    let wins = openOrFocusWindow([], 'analysis', bounds, 0);
    assert.equal(wins.length, 1);
    assert.equal(wins[0].z, 1);
    wins = openOrFocusWindow(wins, 'effective_world', bounds, 1);
    assert.equal(wins.length, 2);
    const z2 = wins.find((w) => w.id === 'effective_world')!.z;
    assert.ok(z2 > 1);
    wins = focusWindow(wins, 'analysis');
    const zA = wins.find((w) => w.id === 'analysis')!.z;
    assert.equal(zA, nextZ(wins.filter((w) => w.id !== 'analysis')));
    // Actually nextZ of all before focus was max+1; after focus analysis has highest
    assert.ok(zA >= z2);
    wins = closeWindow(wins, 'analysis');
    assert.equal(wins.length, 1);
    assert.equal(wins[0].id, 'effective_world');
  });

  it('clamps windows inside bounds', () => {
    const w = clampWindow(
      { id: 'raw', title: 'Raw', x: 5000, y: -100, w: 400, h: 300, z: 1 },
      { width: 800, height: 600 },
    );
    assert.ok(w.x < 800);
    assert.ok(w.y >= 0);
  });

  it('simulation center accounts for left workspace', () => {
    assert.equal(simulationCenterX(1000, 360), 360 + 320);
  });

  it('pending config detects edits', () => {
    assert.equal(configPending({ seed: '17' }, { seed: '17' }), false);
    assert.equal(configPending({ seed: '18' }, { seed: '17' }), true);
    assert.equal(configPending({ seed: '18' }, null), false);
  });

  it('tall-list panels prefer most of viewport height', () => {
    const tall = { width: 1200, height: 900 };
    const mech = preferredOpenSize('mechanisms', tall);
    assert.ok(mech.h >= Math.floor(900 * 0.88) - 1, `mechanisms h=${mech.h}`);
    assert.ok(mech.h <= 900 - 24);
    const compact = preferredOpenSize('geometry', tall);
    assert.equal(compact.h, 360);
    const short = preferredOpenSize('mechanisms', { width: 800, height: 280 });
    assert.ok(short.h <= 280 - 24);
    assert.ok(short.h >= 160);
  });

  it('openOrFocusWindow uses preferredOpenSize for mechanisms', () => {
    const bounds = { width: 1100, height: 800 };
    const wins = openOrFocusWindow([], 'mechanisms', bounds, 0);
    assert.ok(wins[0].h >= Math.floor(800 * 0.88) - 1);
  });
});
