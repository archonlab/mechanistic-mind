/** Focused S7B layout-shell tests (no simulation). */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { describe, it } from 'node:test';
import { resolve } from 'node:path';
import {
  allPanelCombinations,
  DEFAULT_LAYOUT_SHELL,
  LAYOUT_SHELL_STORAGE_KEY,
  layoutShellClassName,
  layoutShellStore,
} from '../observer/layoutShell.ts';

describe('S7B layout shell', () => {
  it('enumerates all 8 independent panel combinations', () => {
    const combos = allPanelCombinations();
    assert.equal(combos.length, 8);
    const keys = new Set(combos.map((c) => `${c.leftOpen}:${c.rightOpen}:${c.bottomOpen}`));
    assert.equal(keys.size, 8);
  });

  it('layoutShellClassName encodes open/closed tracks', () => {
    const c = layoutShellClassName({ leftOpen: false, rightOpen: true, bottomOpen: false });
    assert.ok(c.includes('shell-left-closed'));
    assert.ok(c.includes('shell-right-open'));
    assert.ok(c.includes('shell-bottom-closed'));
  });

  it('store patch is UI-only and does not reference simulation keys', () => {
    layoutShellStore.set({ ...DEFAULT_LAYOUT_SHELL });
    layoutShellStore.patch({ bottomOpen: false });
    assert.equal(layoutShellStore.get().bottomOpen, false);
    assert.equal(LAYOUT_SHELL_STORAGE_KEY.includes('observer'), true);
    assert.equal(LAYOUT_SHELL_STORAGE_KEY.includes('scientific'), false);
  });

  it('App mounts S7B shell regions without legacy strip or ControlDevice rail', () => {
    const app = readFileSync(resolve('src/App.tsx'), 'utf8');
    assert.ok(app.includes('LeftSidebar'));
    assert.ok(app.includes('BottomEvidencePanel'));
    assert.ok(app.includes('BottomDrawerAffordance'));
    assert.ok(app.includes('rightPanelOpen={layoutShell.rightOpen}'));
    assert.ok(app.includes('layoutShellClassName'));
    assert.ok(app.includes('s7b-shell-body'));
    assert.ok(!app.includes('observation-nav-strip'));
    assert.ok(!app.includes("from './desktop/ControlDevice'"));
    assert.ok(!app.includes('<ControlDevice'));
    assert.ok(!app.includes('Show left') && !app.includes('Hide right'));
  });

  it('InspectWorkspace preserves InspectorDock and icon inspector toggle', () => {
    const src = readFileSync(resolve('src/workspaces/InspectWorkspace.tsx'), 'utf8');
    assert.ok(src.includes('InspectorDock'));
    assert.ok(src.includes('rightPanelOpen'));
    assert.ok(src.includes('observer-right-inspector'));
    assert.ok(src.includes('shell-toggle-right'));
    assert.ok(!src.includes('Show right') && !src.includes('Hide right'));
    assert.ok(!src.includes('PanelCollapseToggle'));
  });

  it('WorldPane mode bar contracts unchanged', () => {
    const pane = readFileSync(resolve('src/chrome/WorldPane.tsx'), 'utf8');
    assert.ok(pane.includes('aria-pressed={volumeWorkspace === \'MAP\'}'));
    assert.ok(pane.includes('world-viewport-mode-bar'));
    assert.ok(pane.includes('MAP / 2D'));
    assert.ok(pane.includes('VOLUME / X-RAY'));
    assert.ok(pane.includes('SURFACE / LIGHT'));
  });

  it('toolbar and left sidebar expose aria-expanded panel controls', () => {
    const header = readFileSync(resolve('src/chrome/ObserverHeader.tsx'), 'utf8');
    assert.ok(header.includes('data-s7b-toolbar'));
    assert.ok(header.includes('toolbar-toggle-right'));
    assert.ok(header.includes('toolbar-toggle-bottom'));
    const side = readFileSync(resolve('src/chrome/LeftSidebar.tsx'), 'utf8');
    assert.ok(side.includes('data-s7b-sidebar'));
    assert.ok(side.includes('aria-expanded={open}'));
    assert.ok(side.includes('obs-dest-${d.id}') || side.includes('data-testid={`obs-dest-'));
  });

  it('CSS reserves shell tracks, aquatic theme, and reduced-motion', () => {
    const css = readFileSync(resolve('src/styles/app.css'), 'utf8');
    assert.ok(css.includes('shell-center-column'));
    assert.ok(css.includes('bottom-drawer'));
    assert.ok(css.includes('prefers-reduced-motion'));
    assert.ok(css.includes('world-viewport-mode-bar'));
    assert.ok(css.includes('data-theme="aquatic"'));
    assert.ok(css.includes('app-toolbar'));
    assert.ok(css.includes('left-sidebar'));
  });

  it('scientific claim boundary not overclaimed in bottom panel', () => {
    const bottom = readFileSync(resolve('src/chrome/BottomEvidencePanel.tsx'), 'utf8');
    assert.ok(bottom.includes('scientific revalidation pending'));
    assert.ok(!bottom.includes('fully validated'));
    assert.ok(!bottom.includes('conscious'));
  });

  it('rejects photorealistic / fabricated ecology as rendering target', () => {
    const theme = readFileSync(resolve('src/observer/theme.ts'), 'utf8');
    assert.ok(theme.includes("'aquatic'"));
    const css = readFileSync(resolve('src/styles/app.css'), 'utf8');
    assert.ok(css.includes('Aquatic'));
    const bottom = readFileSync(resolve('src/chrome/BottomEvidencePanel.tsx'), 'utf8');
    assert.ok(!bottom.toLowerCase().includes('foraging'));
    assert.ok(!bottom.toLowerCase().includes('oxygen'));
    assert.ok(!bottom.toLowerCase().includes('temperature'));
    const themeCtrl = readFileSync(resolve('src/chrome/ThemeControl.tsx'), 'utf8');
    assert.ok(themeCtrl.includes("label: 'Aquatic'"));
    assert.ok(!themeCtrl.includes('Aquatic Glass'));
  });
});
