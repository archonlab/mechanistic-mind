/** S7E compact primary toolbar — source contract tests. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { describe, it } from 'node:test';
import { fileURLToPath } from 'node:url';

const root = dirname(fileURLToPath(import.meta.url));
const header = () => readFileSync(join(root, '../chrome/ObserverHeader.tsx'), 'utf8');
const theme = () => readFileSync(join(root, '../chrome/ThemeControl.tsx'), 'utf8');
const clock = () => readFileSync(join(root, '../chrome/RuntimeClock.tsx'), 'utf8');

describe('S7E Observer top toolbar simplification', () => {
  it('primary toolbar hides Full Sci/Compact, density presets, and Panels', () => {
    const src = header();
    assert.match(src, /data-s7e-toolbar/);
    assert.match(src, /toolbar-transport-stack/);
    assert.match(src, /toolbar-speed-stack/);
    assert.match(src, /toolbar-more-menu/);
    // Primary region must not render permanent Full Sci / Compact buttons
    assert.doesNotMatch(src, /className=\{evid === m \? 'active' : ''\}[\s\S]{0,80}Full Sci/);
    assert.ok(!src.includes(">Full Sci<"));
    assert.ok(src.includes('more-evidence-capture'));
    assert.ok(src.includes('more-observer-density'));
    assert.ok(!src.includes('Panels ▾'));
    assert.ok(!src.includes('ObserverDetailControl'));
    // Only one primary speed selector (execution mode)
    assert.equal((src.match(/data-testid="toolbar-speed-selector"/g) || []).length, 1);
    assert.ok(src.includes('more-speed-multiplier'));
  });

  it('tick sits under transport; sim/s under speed', () => {
    const src = header();
    const transportIdx = src.indexOf('toolbar-transport-stack');
    const tickIdx = src.indexOf('app-toolbar-tick');
    const speedIdx = src.indexOf('toolbar-speed-stack');
    const rateIdx = src.indexOf('toolbar-sim-rate');
    assert.ok(transportIdx > 0 && tickIdx > transportIdx && tickIdx < speedIdx);
    assert.ok(speedIdx > 0 && rateIdx > speedIdx);
    assert.match(src, /tick \{tick/);
    assert.match(src, /sim\/s/);
  });

  it('More menu relocates evidence, density, multiplier, layout products, runtime info', () => {
    const src = header();
    assert.match(src, /more-evidence-\$\{/);
    assert.match(src, /more-density-\$\{p\.toLowerCase\(\)\}/);
    assert.match(src, /more-execution-timing/);
    assert.match(src, /more-layout-products/);
    assert.match(src, /more-runtime-info/);
    assert.match(src, /evidence-mode/);
    assert.match(src, /Escape/);
    assert.match(src, /aria-expanded=\{moreOpen\}/);
  });

  it('theme visible label is Aquatic; internal key aquatic preserved', () => {
    const t = theme();
    assert.match(t, /label: 'Aquatic'/);
    assert.doesNotMatch(t, /Aquatic Glass/);
    assert.match(t, /id: 'aquatic'/);
  });

  it('heartbeat detail hidden from primary; stale warning compact', () => {
    const c = clock();
    assert.match(c, /compact/);
    assert.match(c, /forceDetail/);
    assert.match(c, /runtime-clock-stale/);
    const src = header();
    assert.match(src, /RuntimeClock compact/);
    assert.match(src, /forceDetail/);
  });

  it('Inspector and Drawer remain primary shell controls', () => {
    const src = header();
    assert.match(src, /toolbar-toggle-right/);
    assert.match(src, /toolbar-toggle-bottom/);
    assert.match(src, /Inspector/);
    assert.match(src, /Drawer/);
  });
});
