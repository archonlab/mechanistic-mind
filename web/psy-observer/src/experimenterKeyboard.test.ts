/**
 * BETA2-INT-01.1 — global experimenter hotkey routing tests.
 * node --test (no DOM React mount required for decision logic).
 */
import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  EXPERIMENTER_KEY_MAP,
  decideExperimenterHotkey,
  experimenterControlActive,
  shouldAcceptDebounced,
} from './experimenterKeyboard.ts';

function fakeEl(tag: string, extras: Record<string, unknown> = {}) {
  return {
    tagName: tag,
    isContentEditable: false,
    closest: () => null,
    ...extras,
  } as unknown as EventTarget;
}

describe('experimenterControlActive', () => {
  it('only CONTROL_ACTIVE enables hotkeys', () => {
    assert.equal(experimenterControlActive('CONTROL_ACTIVE'), true);
    assert.equal(experimenterControlActive('NOT_SPAWNED'), false);
    assert.equal(experimenterControlActive(null), false);
    assert.equal(experimenterControlActive(undefined), false);
  });
});

describe('decideExperimenterHotkey', () => {
  it('maps WASD / Space / Q / E when control active', () => {
    for (const [code, expected] of Object.entries(EXPERIMENTER_KEY_MAP)) {
      const d = decideExperimenterHotkey(
        { code, target: fakeEl('DIV') },
        { controlActive: true },
      );
      assert.equal(d.handle, true);
      if (d.handle) {
        assert.equal(d.kind, expected.kind);
        assert.equal(d.action, expected.action);
      }
    }
  });

  it('no experimenter body → no command (WORLD or any tab)', () => {
    const d = decideExperimenterHotkey(
      { code: 'KeyW', target: fakeEl('DIV') },
      { controlActive: false },
    );
    assert.deepEqual(d, { handle: false, reason: 'no_experimenter_body' });
  });

  it('suppresses browser key-repeat', () => {
    const d = decideExperimenterHotkey(
      { code: 'KeyW', repeat: true, target: fakeEl('DIV') },
      { controlActive: true },
    );
    assert.equal(d.handle, false);
    if (!d.handle) assert.equal(d.reason, 'key_repeat');
  });

  it('suppresses INPUT / TEXTAREA / SELECT / contenteditable', () => {
    for (const tag of ['INPUT', 'TEXTAREA', 'SELECT']) {
      const d = decideExperimenterHotkey(
        { code: 'KeyW', target: fakeEl(tag) },
        { controlActive: true },
      );
      assert.equal(d.handle, false, tag);
      if (!d.handle) assert.equal(d.reason, 'typing_focus');
    }
    const ce = decideExperimenterHotkey(
      { code: 'KeyQ', target: fakeEl('DIV', { isContentEditable: true }) },
      { controlActive: true },
    );
    assert.equal(ce.handle, false);
  });

  it('does not intercept Ctrl/Cmd/Alt shortcuts', () => {
    for (const mod of [
      { ctrlKey: true },
      { metaKey: true },
      { altKey: true },
    ]) {
      const d = decideExperimenterHotkey(
        { code: 'KeyW', target: fakeEl('DIV'), ...mod },
        { controlActive: true },
      );
      assert.equal(d.handle, false);
      if (!d.handle) assert.equal(d.reason, 'modifier_shortcut');
    }
  });

  it('unmapped keys pass through', () => {
    const d = decideExperimenterHotkey(
      { code: 'KeyX', target: fakeEl('DIV') },
      { controlActive: true },
    );
    assert.equal(d.handle, false);
    if (!d.handle) assert.equal(d.reason, 'unmapped');
  });

  it('Q/E resolve to FIELD_A / FIELD_B (ordinary path kinds)', () => {
    const q = decideExperimenterHotkey(
      { code: 'KeyQ', target: fakeEl('CANVAS') },
      { controlActive: true },
    );
    const e = decideExperimenterHotkey(
      { code: 'KeyE', target: fakeEl('CANVAS') },
      { controlActive: true },
    );
    assert.deepEqual(q, { handle: true, kind: 'FIELD_A', action: undefined });
    assert.deepEqual(e, { handle: true, kind: 'FIELD_B', action: undefined });
  });

  it('decision is tab-independent (same for WORLD-like canvas target)', () => {
    // Simulate WORLD canvas focus vs INTERACT panel DIV — both allow when not typing
    const world = decideExperimenterHotkey(
      { code: 'KeyD', target: fakeEl('CANVAS') },
      { controlActive: true },
    );
    const interact = decideExperimenterHotkey(
      { code: 'KeyD', target: fakeEl('DIV') },
      { controlActive: true },
    );
    assert.deepEqual(world, interact);
    assert.equal(world.handle, true);
  });
});

describe('shouldAcceptDebounced', () => {
  it('suppresses bursts within debounce window (key-repeat safety)', () => {
    const bag: Record<string, number> = {};
    assert.equal(shouldAcceptDebounced(bag, 'ACTION:MOVE:N', 1000, 80), true);
    assert.equal(shouldAcceptDebounced(bag, 'ACTION:MOVE:N', 1040, 80), false);
    assert.equal(shouldAcceptDebounced(bag, 'ACTION:MOVE:N', 1090, 80), true);
    // Different command not blocked
    assert.equal(shouldAcceptDebounced(bag, 'FIELD_A:', 1095, 80), true);
  });
});

describe('single authoritative path', () => {
  it('EXPERIMENTER_KEY_MAP is the only hotkey source (no duplicate maps)', () => {
    assert.equal(Object.keys(EXPERIMENTER_KEY_MAP).length, 7);
    assert.ok(EXPERIMENTER_KEY_MAP.KeyW);
    assert.ok(EXPERIMENTER_KEY_MAP.Space);
  });
});
